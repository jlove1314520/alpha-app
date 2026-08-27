# -*- coding: utf-8 -*-
"""每日排程更新 data/price_history.json 的個股OHLCV歷史，累積式寫回（2026-08-27）。

背景：`research/generate_scores_live.py`（P1，JSON-only上線評分路徑）的
`technical`（技術型態）因子需要per股票的每日價量歷史才能算「站上60日均線×
20/60日均量比」——起始種子由 `research/build_price_history.py` 讀research端
FinMind歷史parquet快取一次回補（2101檔、90個交易日），這支腳本負責之後
每天累積式append「今天的最新一筆」，跟 `update_fundamentals_daily.py`/
`update_stock_financials.py` 同一套「累積式寫回」模式。

資料源（全部官方開放資料，免金鑰）：
- TWSE：`openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`——全市場上市
  股票最新一個交易日的OHLCV快照（含ETF/權證等非股票證券，這裡不特別過濾，
  跟fundamentals.json的做法一致：多存不影響評分，評分端只查有股票資料的代碼）。
- TPEx：`www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes`——上櫃股票對應版本，
  欄位命名不同（`Close`/`Open`/`High`/`Low`/`TradingShares`），語意對應。

**2026-08-27修正（P0 bug，使用者回報）：新增還原權息調整（`adj_close`）**。
背景：`close`是原始收盤價，除息當天會跳空下跌，被
`generate_scores_momentum.py`的`relative_strength`（相對強度/價格動能）因子
誤判成真實下跌，除息季會系統性扭曲題材動能榜排名。修法：每天呼叫TWSE官方
`rwd/zh/exRight/TWT48U`（除權除息預告表，免金鑰，跟T86同一個端點家族），
把新出現的除權息事件累積寫進`data/ex_dividend_events.json`；當某事件的
除權息日<=今天且尚未套用過，用TWSE官方參考價公式（跟`research/adjust.py`
同一條公式，來源改成這個官方端點，不必依賴FinMind——刻意維持「JSON-only
每日排程不呼叫FinMind」的既有架構原則）回溯調整該股在此日期之前所有列的
`adj_close`欄位。`close`本身永遠不變（保留原始值，供其他用途／稽核比對），
新增的`adj_close`才是還原權息後的收盤價，供動能榜等報酬率類因子改用。

**已知限制（實測發現，2026-08-27）**：TWT48U是「預告表」，只回傳當下未來
約5週內的事件，不支援歷史區間查詢——所以還原調整是「事件發生後才回溯套用」
的漸進累積過程，剛上線那幾週涵蓋率會逐漸提高，不是一次全部到位；對這支
腳本啟用之前就已經發生、且已經滾出90天視窗之外的除權息事件無法補回溯
（`adj_close`退回等於`close`，等同未還原，跟修正前狀態相同，不會更糟）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "price_history.json"
SNAPSHOT_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"
EX_DIVIDEND_EVENTS_PATH = REPO_ROOT / "data" / "ex_dividend_events.json"
TW_TZ = timezone(timedelta(hours=8))

STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
EX_RIGHT_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT48U"
PRICE_HISTORY_DAYS = 90


def _get_retry(url: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """同 update_fundamentals_daily.py 的 _get_retry()，自成一體複製（既有慣例）。"""
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def _roc_ymd_to_iso(s: str) -> str | None:
    """解析「115年09月01日」格式（TWT48U除權息預告表專用，跟上面
    `_roc_date_to_iso()`的7位數字格式(STOCK_DAY_ALL用)是不同來源的不同
    格式，故意不合併成一個函式，避免跨格式誤用）。"""
    m = re.match(r"^(\d{2,3})年(\d{2})月(\d{2})日$", str(s).strip())
    if not m:
        return None
    year = int(m.group(1)) + 1911
    return f"{year}-{m.group(2)}-{m.group(3)}"


def fetch_twse() -> dict[str, dict]:
    r = _get_retry(STOCK_DAY_ALL_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("STOCK_DAY_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("Code")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("ClosingPrice"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("OpeningPrice")),
            "high": _num(row.get("HighestPrice")),
            "low": _num(row.get("LowestPrice")),
            "close": close,
            "adj_close": close,  # 當天(最新一筆)永遠等於原始收盤，還原調整只回溯套用到更早的日期
            "volume": _num(row.get("TradeVolume")),
            "turnover": _num(row.get("TradeValue")),  # 2026-08-27新增：類股成分股清單功能要用
        }
    return out


def fetch_tpex() -> dict[str, dict]:
    r = _get_retry(TPEX_QUOTES_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_mainboard_quotes 回傳非預期格式（可能是無效路徑回傳的HTML）")
    out = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("Close"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("Open")),
            "high": _num(row.get("High")),
            "low": _num(row.get("Low")),
            "close": close,
            "adj_close": close,  # 同上：當天永遠等於原始收盤
            "volume": _num(row.get("TradingShares")),
            "turnover": _num(row.get("TransactionAmount")),
        }
    return out


def merge_rows(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = [r for r in (existing or []) if r.get("date") != latest["date"]]
    rows.append(latest)
    rows.sort(key=lambda r: r["date"])
    return rows[-PRICE_HISTORY_DAYS:]


def fetch_ex_dividend_announcements() -> list[dict]:
    """TWSE官方除權除息預告表（免金鑰，跟T86同一個www.twse.com.tw/rwd/家族
    端點）。**已知限制（實測發現，2026-08-27）**：這是「預告表」，只回傳
    當下未來約5週內的事件（實測：今天到約1個月後），不支援歷史區間查詢
    （試過startDate/endDate參數，回傳的107筆資料完全不變）——所以設計成
    「每天呼叫、累積寫進ex_dividend_events.json」，靠時間讓每一檔除權息
    事件至少在發生前幾週內被記錄到一次，不是一次性回補歷史。"""
    r = _get_retry(EX_RIGHT_URL, params={"response": "json"}, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return []
    fields = body["fields"]

    def _idx(want):
        for i, f in enumerate(fields):
            if want in f:
                return i
        return None

    i_date = _idx("除權除息日期")
    i_code = _idx("股票代號")
    i_stock_ratio = _idx("無償配股率")
    i_rights_ratio = _idx("現金增資配股率")
    i_rights_price = _idx("現金增資認購價")
    i_cash = _idx("現金股利")
    i_type = _idx("除權息")
    if None in (i_date, i_code, i_cash, i_stock_ratio, i_rights_ratio, i_rights_price):
        raise RuntimeError("TWT48U 欄位對應失敗（TWSE可能改版了欄位名稱），已知欄位名找不到")

    out = []
    for row in body["data"]:
        ex_date = _roc_ymd_to_iso(row[i_date])
        code = (row[i_code] or "").strip()
        if not ex_date or not code:
            continue
        cash = _num(row[i_cash]) or 0.0
        stock_ratio = _num(row[i_stock_ratio]) or 0.0
        rights_ratio = _num(row[i_rights_ratio]) or 0.0
        rights_price = _num(row[i_rights_price]) or 0.0
        if cash == 0 and stock_ratio == 0 and rights_ratio == 0:
            continue  # 預告表裡「純股票分割/減資」等其他列，這裡只處理現金股利/股票股利/現增
        out.append({
            "code": code, "ex_date": ex_date,
            "cash": cash, "stock_ratio": stock_ratio,
            "rights_ratio": rights_ratio, "rights_price": rights_price,
            "type": row[i_type] if i_type is not None else None,
        })
    return out


def load_ex_dividend_ledger() -> dict:
    if EX_DIVIDEND_EVENTS_PATH.exists():
        try:
            return json.loads(EX_DIVIDEND_EVENTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "events": {}}


def merge_ex_dividend_events(ledger: dict, announcements: list[dict], today_iso: str) -> int:
    """新事件併入ledger，已存在的(code, ex_date)不覆寫（保留原本的applied
    狀態，不能因為預告表重複回傳同一筆就讓已套用的事件被重置）。回傳新增筆數。"""
    events_by_code = ledger.setdefault("events", {})
    added = 0
    for ann in announcements:
        bucket = events_by_code.setdefault(ann["code"], [])
        if any(e["ex_date"] == ann["ex_date"] for e in bucket):
            continue
        bucket.append({
            "ex_date": ann["ex_date"], "cash": ann["cash"],
            "stock_ratio": ann["stock_ratio"], "rights_ratio": ann["rights_ratio"],
            "rights_price": ann["rights_price"], "type": ann["type"],
            "first_seen": today_iso, "applied": False,
        })
        added += 1
    return added


def _days_between(iso_a: str, iso_b: str) -> int:
    a = datetime.strptime(iso_a, "%Y-%m-%d")
    b = datetime.strptime(iso_b, "%Y-%m-%d")
    return abs((b - a).days)


MAX_PREV_CLOSE_GAP_DAYS = 10  # research端FinMind快取可能對少數股票已經過期很久（實測發現，見下）


def apply_dividend_adjustments(prices: dict, ledger: dict, today_iso: str) -> int:
    """對 ex_date<=today_iso 且尚未applied的事件，用TWSE官方除權息參考價公式
    （跟research/adjust.py同一條公式：ref_price=(前一日收盤-現金股利+現金增資
    認購價×認股比率)/(1+股票股利比率+認股比率)，factor=ref_price/前一日收盤）
    算出調整係數，回溯乘進該股所有date<ex_date列的adj_close。

    重要：factor永遠用「原始close」當前一日收盤的錨點（不是adj_close）——
    這樣不管每天累積套用的順序為何，多筆事件複合起來的結果都跟一次性從最新
    到最舊反向套用（research/adjust.py的做法）等價，見該模組docstring。

    **2026-08-27實測發現的真bug，這裡的守門是修正**：少數股票（例如2420）的
    research端FinMind parquet快取已經停在很久以前（實測發現停在2024-12-31），
    daily排程當天新增的一筆(2026-08-26)緊接在那筆stale資料後面，導致
    `date<ex_date`找到的「前一筆」其實是1年8個月前的舊資料，用它當
    prev_close錨點算出的factor完全不對(算出0.95但實際上下跌是完全不相干的
    兩個價格區間)。修法：前一筆資料的日期離除權息日超過`MAX_PREV_CLOSE_GAP_DAYS`
    天就判定「快取缺口過大、無法安全定錨」，不套用（adj_close維持=close，
    不會比修正前更差），並記錄skip_reason、標記applied=True避免每天重算。
    回傳這輪新套用的事件數。"""
    applied_count = 0
    for code, events in ledger.get("events", {}).items():
        rows = prices.get(code)
        if not rows:
            continue
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        for ev in events:
            if ev.get("applied") or ev["ex_date"] > today_iso:
                continue
            prior = [r for r in rows_sorted if r["date"] < ev["ex_date"]]
            if not prior:
                continue  # 這檔股票的歷史還沒涵蓋到除權息日前一天，等之後累積夠了再套用
            prior_date = prior[-1]["date"]
            if _days_between(prior_date, ev["ex_date"]) > MAX_PREV_CLOSE_GAP_DAYS:
                ev["applied"] = True
                ev["skip_reason"] = (
                    f"前一筆可用資料({prior_date})距離除權息日({ev['ex_date']})"
                    f"超過{MAX_PREV_CLOSE_GAP_DAYS}天，research端FinMind快取對這檔"
                    "股票可能已經過期太久，無法安全定錨調整係數，不套用。"
                )
                continue
            prev_close = prior[-1].get("close")
            if prev_close in (None, 0):
                continue
            numerator = prev_close - ev["cash"] + ev["rights_price"] * ev["rights_ratio"]
            denominator = 1 + ev["stock_ratio"] + ev["rights_ratio"]
            if denominator <= 0 or numerator <= 0:
                ev["applied"] = True
                ev["skip_reason"] = "numerator/denominator 非正值，判定資料異常，不套用"
                continue
            factor = (numerator / denominator) / prev_close
            for r in rows:
                if r["date"] < ev["ex_date"]:
                    base = r.get("adj_close")
                    if base is None:
                        base = r.get("close")
                    if base is not None:
                        r["adj_close"] = base * factor
            ev["applied"] = True
            ev["factor_applied"] = factor
            applied_count += 1
    return applied_count


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在——這支腳本設計上只做累積更新，"
              "第一次的完整快照要用 research/build_price_history.py 手動產生並 commit。")
        raise SystemExit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prices = payload.setdefault("prices", {})

    errors = []
    twse_updated = tpex_updated = 0

    # 2026-08-27新增：除權息回溯調整必須在「今天的原始收盤」merge進prices之前
    # 做——這樣factor的錨點(prev_close)才會是「昨天」已經存好的收盤，不會被
    # 今天還沒merge進去的資料影響（today_iso用twse抓到的實際交易日期，抓失敗
    # 才退回now()，處理假日補跑等邊界情況）。
    ex_div_applied = 0
    ex_div_added = 0
    twse = {}
    try:
        twse = fetch_twse()
        today_iso = next(iter(twse.values()))["date"] if twse else datetime.now(TW_TZ).strftime("%Y-%m-%d")
    except Exception as e:
        print(f"價量(TWSE) 抓取失敗，除權息判斷改用今天日期：{e}")
        errors.append(f"price_twse: {e}")
        today_iso = datetime.now(TW_TZ).strftime("%Y-%m-%d")

    try:
        ledger = load_ex_dividend_ledger()
        announcements = fetch_ex_dividend_announcements()
        ex_div_added = merge_ex_dividend_events(ledger, announcements, today_iso)
        ex_div_applied = apply_dividend_adjustments(prices, ledger, today_iso)
        ledger.setdefault("meta", {})
        ledger["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
        ledger["meta"]["last_fetch_count"] = len(announcements)
        EX_DIVIDEND_EVENTS_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    except Exception as e:
        print(f"除權息預告表(TWT48U) 更新失敗（不影響價量本身，adj_close退回等於close）：{e}")
        errors.append(f"ex_dividend: {e}")

    if twse:
        for code, latest in twse.items():
            prices[code] = merge_rows(prices.get(code), latest)
        twse_updated = len(twse)

    try:
        tpex = fetch_tpex()
        for code, latest in tpex.items():
            prices[code] = merge_rows(prices.get(code), latest)
        tpex_updated = len(tpex)
    except Exception as e:
        print(f"價量(TPEx) 更新失敗：{e}")
        errors.append(f"price_tpex: {e}")

    payload.setdefault("meta", {})
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["twse_updated_count"] = twse_updated
    payload["meta"]["tpex_updated_count"] = tpex_updated
    payload["meta"]["errors"] = errors
    payload["meta"]["ex_dividend_events_added"] = ex_div_added
    payload["meta"]["ex_dividend_events_applied"] = ex_div_applied
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：TWSE {twse_updated} 檔+TPEx {tpex_updated} 檔（合計 {len(prices)} 檔有資料），"
          f"除權息事件本輪新增 {ex_div_added} 筆、套用回溯調整 {ex_div_applied} 筆")
    if errors:
        print(f"部分失敗（不中止，維持既有資料）：{errors}")

    # 2026-08-27新增：類股成分股清單功能（B4）需要「全市場（不只自選股）最新
    # 一天的收盤價/漲跌%/成交值」，但price_history.json整份90天歷史太大
    # （32MB+），不適合每次client-side抓整份只為了取最新一天。這裡從剛更新
    # 的prices取每檔最後兩筆算出這個輕量快照，單獨寫一個小檔。
    snapshot = {}
    for code, rows in prices.items():
        if not rows:
            continue
        last = rows[-1]
        prev = rows[-2] if len(rows) >= 2 else None
        change_pct = None
        if prev and prev.get("close") not in (None, 0):
            change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100, 2)
        snapshot[code] = {
            "date": last["date"], "close": last["close"],
            "change_pct": change_pct, "turnover": last.get("turnover"),
        }
    SNAPSHOT_PATH.write_text(json.dumps({
        "meta": {"generated_at": datetime.now(TW_TZ).isoformat(),
                 "note": "從data/price_history.json每檔最後兩筆算出的輕量快照（收盤/漲跌%/成交值），"
                         "供類股成分股清單等只需要「今天」資料的功能用，不用載入整份90天歷史。"},
        "quotes": snapshot,
    }, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {SNAPSHOT_PATH}：{len(snapshot)} 檔輕量快照")


if __name__ == "__main__":
    main()
