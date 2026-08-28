# -*- coding: utf-8 -*-
"""每日排程更新 data/margin_maintenance.json（大盤融資維持率），取代原本卡在
C:\\alpha\\alpha-data\\compute_margin_maintenance.py 的手動、無排程狀態（STATUS.json
列的 P1 項目：目前只有1筆、手動執行、會安靜過期）。

公式：大盤融資維持率 = 全市場融資擔保品市值 ÷ 全市場融資金額 × 100%。

**逐股融資擔保品市值（分子）改用 TWSE 官方開放資料，不用 FinMind**：
- `MI_MARGN`：全市場每檔股票的融資今日餘額（張）。
- `STOCK_DAY_ALL`：全市場每檔股票的當日收盤價。
兩個都是免金鑰、一次回傳全市場的官方端點（跟 `alpha-data/compute_margin_maintenance.py`
用的是同一組，這裡是自成一體的獨立複製，不跨目錄 import，同 `fetch_market_tw.py`
等既有慣例）。

**已知限制，誠實揭露，不是隱藏**：分母（全市場融資金額，即銀行/證金公司實際
貸出去的錢）目前沒有對應的 TWSE openapi 端點可以直接拿到——TWSE 只公布逐股
「融資餘額(張)」，沒有公布全市場加總的「融資金額(元)」。這裡仍然使用 FinMind
`TaiwanStockTotalMarginPurchaseShortSale`（免token）當分母來源，是這支腳本
唯一保留的 FinMind 依賴，風險遠低於之前逐股迴圈打 FinMind：**這裡一天只呼叫
一次、抓的是全市場單一加總數字，不是逐股歷史**，額度耗盡機率低很多。如果這
唯一一次呼叫還是失敗，腳本會誠實跳過今天這筆（不寫入錯誤或猜測值），讓
history 停在最後一筆有效資料，App 的診斷橫幅會偵測到超過3天沒更新並提示。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "margin_maintenance.json"
TW_TZ = timezone(timedelta(hours=8))

MI_MARGN_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"  # 上市公司基本資料（含金融股，不含ETF/權證）
# 2026-08-27新增（P1-新，補TPEx上櫃融資融券缺口）：TPEx官方對應端點，只用來
# 補stock_detail.json的個股「融資融券」分頁資料，**不**併入大盤融資維持率
# 分子/分母的計算（那個公式是TWSE市場專屬定義，不擴大範圍，維持原設計）。
TPEX_MARGIN_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance"
FINMIND_URL = (
    "https://api.finmindtrade.com/api/v4/data"
    "?dataset=TaiwanStockTotalMarginPurchaseShortSale&start_date={start}"
)
HISTORY_DAYS_KEEP = 60

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）。FinMind那一路刻意用跟
# finmind_client.py同一個source key "finmind"，讓兩邊互相看得到對方的封鎖
# 狀態，不會各自為政。
RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        try:
            return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    state = _load_rate_limit_state()
    src = state["sources"].get(source, {})
    now = time.time()
    blocked_until = src.get("blocked_until")
    if blocked_until and now < blocked_until:
        remain_min = round((blocked_until - now) / 60, 1)
        raise RuntimeError(
            f"{source} 目前處於封鎖冷卻中（還剩約{remain_min}分鐘，"
            f"原因：{src.get('block_reason', '未知')}），依「資料源禮儀」規則拒絕發送請求"
        )
    last = src.get("last_request_at")
    if last and (now - last) < RATE_LIMIT_MIN_INTERVAL_SEC:
        time.sleep(RATE_LIMIT_MIN_INTERVAL_SEC - (now - last))
    src["last_request_at"] = time.time()
    state["sources"][source] = src
    _save_rate_limit_state(state)


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _get_retry(url: str, source: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """同 update_stock_financials.py 的 _get_retry()——自成一體複製，不跨檔案
    import（既有慣例）。2026-08-27新增：端點逾時要重試，不能靜靜跳過。
    2026-08-28新增`source`：發送前先過跨process共用節流/斷路檢查。"""
    _rate_limit_wait_or_raise(source)
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if r.status_code in (402, 403, 428, 429):
            _rate_limit_record_block(source, r.status_code, r.text[:200])
            raise RuntimeError(f"{source}回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


def load_tse_company_codes() -> set[str] | None:
    """同fetch_market_tw.py的load_tse_company_codes()——自成一體的獨立複製，
    不跨腳本import（見既有慣例）。用來篩選merge進stock_detail.json的代碼，
    含金融股、不含ETF/權證。"""
    try:
        r = _get_retry(TSE_LIST_URL, "twse_openapi", timeout=15)
        r.raise_for_status()
        rows = r.json()
        codes = {row.get("公司代號") for row in rows if row.get("公司代號")}
        return codes if codes else None
    except Exception as e:
        print(f"抓上市公司清單失敗（改回不篩選代碼）：{e}")
        return None


def _num(v):
    if v in (None, "", "-", "--"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def fetch_margin_by_stock() -> tuple[dict[str, float], dict[str, dict]]:
    """回傳 (代號:融資今日餘額張數（給維持率算擔保品市值用）,
    代號:{today,prev,short_today}（給個股頁「融資融券」分頁用，merge進stock_detail.json）)。"""
    r = _get_retry(MI_MARGN_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("MI_MARGN 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    lots_only = {}
    per_stock = {}
    for row in rows:
        code = row.get("股票代號")
        lots = _num(row.get("融資今日餘額"))
        if code and lots is not None:
            lots_only[code] = lots
        if code:
            per_stock[code] = {
                "margin_balance_today": lots,
                "margin_balance_prev": _num(row.get("融資前日餘額")),
                "short_balance_today": _num(row.get("融券今日餘額")),
            }
    return lots_only, per_stock


def fetch_margin_by_stock_tpex() -> dict[str, dict]:
    """TPEx（上櫃）融資融券逐股資料，只給stock_detail.json的個股分頁用
    （不併入大盤維持率分子/分母，見TPEX_MARGIN_URL常數說明）。"""
    r = _get_retry(TPEX_MARGIN_URL, "tpex_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_mainboard_margin_balance 回傳非預期格式（可能是無效路徑回傳的HTML）")
    per_stock = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        if not code:
            continue
        per_stock[code] = {
            "margin_balance_today": _num(row.get("MarginPurchaseBalance")),
            "margin_balance_prev": _num(row.get("MarginPurchaseBalancePreviousDay")),
            "short_balance_today": _num(row.get("ShortSaleBalance")),
        }
    return per_stock


def fetch_close_by_stock() -> dict[str, float]:
    r = _get_retry(STOCK_DAY_ALL_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("STOCK_DAY_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("Code")
        px = _num(row.get("ClosingPrice"))
        if code and px is not None:
            out[code] = px
    return out


def fetch_market_margin_money() -> tuple[str, float]:
    start = (datetime.now(TW_TZ).date() - timedelta(days=10)).isoformat()
    r = _get_retry(FINMIND_URL.format(start=start), "finmind", timeout=30)
    r.raise_for_status()
    data = r.json()
    rows = data.get("data", [])
    money_rows = [row for row in rows if row.get("name") == "MarginPurchaseMoney"]
    if not money_rows:
        raise RuntimeError("FinMind 沒有回傳 MarginPurchaseMoney（額度用盡或資料集異常）")
    last = money_rows[-1]
    return last["date"], last["TodayBalance"]


def merge_stock_detail_margin(per_stock: dict[str, dict], tpex_codes: set[str] | None = None) -> None:
    """merge進 data/stock_detail.json（個股頁「融資融券」分頁用）。
    **2026-08-27修正**：原本用「已存在於stocks的代碼」（財報「一般業」名單）
    當篩選門檻，誤把金融股（有MI_MARGN資料，只是財報格式不同）也濾掉了。改用
    官方上市公司清單(t187ap03_L，含金融股)當篩選門檻，同fetch_market_tw.py的
    修正。**2026-08-27（續）再修正**：tse_codes只涵蓋TWSE上市，`tpex_codes`
    參數（呼叫端傳入TPEx來源的代碼集合）讓這些代碼跳過這個不適用的過濾，
    避免補了TPEx資料源卻在這裡自己濾掉，同fetch_market_tw.py的修正。"""
    detail_path = REPO_ROOT / "data" / "stock_detail.json"
    if not detail_path.exists():
        return
    try:
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
    except Exception:
        return
    stocks = detail.setdefault("stocks", {})
    tse_codes = load_tse_company_codes()
    tpex_codes = tpex_codes or set()
    matched = 0
    for code, row in per_stock.items():
        if code not in tpex_codes and tse_codes is not None and code not in tse_codes:
            continue
        stocks.setdefault(code, {})["margin"] = row
        matched += 1
    detail.setdefault("meta", {})["margin_source"] = (
        "TWSE MI_MARGN（同一次呼叫，跟大盤融資維持率共用，不額外打；只保留官方上市"
        "公司清單(t187ap03_L)內的代碼)+TPEx tpex_mainboard_margin_balance"
        "（2026-08-27新增，上櫃股票）"
    )
    detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"併入 {detail_path}：融資融券合併 {matched} 檔（含TPEx {len(tpex_codes)}檔）")


def main():
    margin_by_stock, margin_per_stock_detail = fetch_margin_by_stock()
    close_by_stock = fetch_close_by_stock()
    print(f"融資個股 {len(margin_by_stock)} 檔，收盤價個股 {len(close_by_stock)} 檔")

    collateral_value = 0.0
    matched = 0
    for code, lots in margin_by_stock.items():
        px = close_by_stock.get(code)
        if px is None or lots <= 0:
            continue
        collateral_value += lots * 1000 * px
        matched += 1
    print(f"可配對算擔保品市值的個股 {matched} 檔")

    tpex_codes = set()
    try:
        margin_per_stock_tpex = fetch_margin_by_stock_tpex()
        margin_per_stock_detail = {**margin_per_stock_detail, **margin_per_stock_tpex}
        tpex_codes = set(margin_per_stock_tpex.keys())
        print(f"TPEx融資融券 {len(margin_per_stock_tpex)} 檔")
    except Exception as e:
        print(f"TPEx融資融券 失敗：{e}")

    merge_stock_detail_margin(margin_per_stock_detail, tpex_codes)

    today = datetime.now(TW_TZ).date().isoformat()
    # 2026-08-27 修正（使用者要求）：分母（FinMind全市場融資金額）失敗時，改成
    # 寫入一筆「今天有資料，但不完整」的明確記錄（ratio_pct=None、
    # data_incomplete=True），不再直接跳過不寫——舊行為的問題是：跳過之後
    # history最後一筆仍是幾天前「看起來正常」的百分比，畫面上的日期雖然沒動，
    # 但一個正常大小的數字很容易被誤讀成「今天的維持率就是這樣」。現在即使
    # 分母失敗，也讓App知道「今天嘗試過，但這個數字不可信」，不是靜默沿用舊值。
    try:
        fm_date, margin_money = fetch_market_margin_money()
        data_incomplete = False
        incomplete_reason = None
    except Exception as e:
        print(f"分母（FinMind全市場融資金額）取得失敗：{e}")
        fm_date, margin_money = None, None
        data_incomplete = True
        incomplete_reason = f"FinMind全市場融資金額取得失敗：{e}"

    ratio = collateral_value / margin_money * 100 if margin_money else None
    record = {
        "date": today,
        "finmind_margin_money_date": fm_date,
        "collateral_value": round(collateral_value) if collateral_value else None,
        "margin_money": margin_money,
        "matched_stocks": matched,
        "ratio_pct": round(ratio, 2) if ratio is not None else None,
        "data_incomplete": data_incomplete,
        "incomplete_reason": incomplete_reason,
    }
    print(f"維持率估算：{record['ratio_pct']}%" if not data_incomplete else f"資料不完整：{incomplete_reason}")

    history = []
    if OUT_PATH.exists():
        try:
            history = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history = [h for h in history if h.get("date") != today]
    history.append(record)
    history.sort(key=lambda h: h["date"])
    history = history[-HISTORY_DAYS_KEEP:]
    OUT_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}（累積 {len(history)} 天）")


if __name__ == "__main__":
    main()
