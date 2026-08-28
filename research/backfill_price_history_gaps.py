"""一次性回補：research端FinMind本機parquet快取過舊的股票，補齊
data/price_history.json 的深度（2026-08-28新增，B23第一步）。

背景：動能榜（`generate_scores_momentum.py`）的量價因子（relative_strength/
volume_breakout/new_high_breakout/volume_price_coordination）至少要
60個交易日連續的OHLCV序列才能算。本輪查證發現：題材動能榜候選宇宙
（2375檔）裡有593檔目前 price_history.json 少於60列——根因是
`research/build_price_history.py` 讀的FinMind本機parquet快取對這些股票
已經停在很久以前（常見停在2024-12-31，跟動能榜還原權息那輪抓到的
「除權息日前一筆可用資料距離過遠」真bug是同一批受害股票），daily排程
（`.github/scripts/update_price_history.py`）一天只能累積一筆，單靠它要
再等好幾個月才會自然補滿。

**方法演進紀錄（誠實記錄本輪試過哪些路，符合「至少試三條路」的資料原則）**：
1. 先試TWSE官方 `exchangeReport/STOCK_DAY` 單股歷史日線端點——本輪實測
   （2026-08-28凌晨）**整批100%被反爬蟲擋下（53檔測試全部428，不是間歇性）**，
   放棄這條路，不是沒試就跳過。
2. 改用FinMind **即時線上API**（不是research端可能過期的本機parquet快取）
   直接補這些股票缺的區間——這裡刻意**不經過`finmind_client.load_dev()`/
   `load_full_history()`**：前者會把資料cap在`validation.holdout.VAL_END`
   （回測用途的holdout規則，這裡建置的是App正式上線即時資料不適用）；後者
   雖然可以看到完整歷史，但要求呼叫`unlock_holdout_once()`，那是「一次性、
   不可逆」的holdout解鎖機制，設計給正式回測評估用，不該為了這種即時資料
   建置需求去消耗它。跟`research/adjust.py`模組docstring說明的取捨原則
   一致：直接用requests打FinMind API，自成一體，不共用holdout邏輯。

**已知限制，誠實揭露**：
- 只補「還原前」的原始OHLCV，`adj_close`先等於`close`（不含這批新補歷史
  範圍內的除權息回溯調整——已知簡化，不影響「原本幾乎沒有歷史」到「現在
  有完整歷史但少數除息缺口未還原」這個net正向的改善，且之後
  `update_price_history.py`的除權息回溯機制對這些股票未來的新除權息事件
  一樣能正常運作）。
- FinMind免費層有流量上限（約每小時數百次），本輪約593次請求＋節流
  （每次間隔0.3秒），若中途真的撞到配額限制，個別股票補不到就跳過留待
  下次，不會讓整支腳本因為單一檔案失敗而中止。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).parent.parent
OUT_PATH = REPO_ROOT / "data" / "price_history.json"
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
COMPANY_INFO_PATH = REPO_ROOT / "data" / "company_info.json"

DEPTH_TARGET = 60  # relative_strength因子60日腳需要的最低列數
BACKFILL_START_DATE = "2026-04-01"  # 涵蓋近5個月，含週末/假日緩衝，足夠90個交易日視窗
PRICE_HISTORY_DAYS = 90

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
_NON_STOCK_CODE_PATTERN = re.compile(r"^00\d{2,4}[A-Z]?$")
NON_STOCK_INDUSTRIES = {
    "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
    "受益證券", "存託憑證", "Index", "大盤", "所有證券",
}

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則）：
# 跟`research/finmind_client.py`共用同一份跨process狀態檔（同一個source key
# "finmind"）——這支腳本本來就刻意不經過finmind_client.py（見模組docstring：
# 不走load_dev/holdout），但仍然打的是同一個FinMind API，必須共用同一套
# 節流/斷路狀態，不然這支腳本自己開的請求量還是會讓finmind_client.py那邊的
# 節流形同虛設（2026-08-27晚到2026-08-28整晚的實際incident就是因為好幾支
# 「各自獨立process」的腳本互相不知道對方在打同一個來源）。
RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
FINMIND_SOURCE_KEY = "finmind"


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


def _rate_limit_wait_or_raise(source: str = FINMIND_SOURCE_KEY) -> None:
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


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def fetch_finmind_price(code: str) -> list[dict]:
    """FinMind即時線上API（不經過本機parquet快取，也不經過load_dev/holdout，
    見模組docstring）。免token，回傳失敗/空資料就回傳[]，呼叫端try/except接住。
    2026-08-28新增：發送前先過共用的跨process節流/斷路檢查（見上方
    `_rate_limit_wait_or_raise()`），封鎖中會直接RuntimeError不發請求；
    收到額度/封鎖類狀態碼會立刻標記封鎖，不會重試。"""
    _rate_limit_wait_or_raise()
    r = requests.get(FINMIND_URL, params={
        "dataset": "TaiwanStockPrice", "data_id": code, "start_date": BACKFILL_START_DATE,
    }, timeout=20)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block(FINMIND_SOURCE_KEY, r.status_code, r.text[:200])
        raise RuntimeError(f"FinMind回應HTTP {r.status_code}，已標記封鎖{RATE_LIMIT_BLOCK_SECONDS//3600}小時：{r.text[:200]}")
    r.raise_for_status()
    d = r.json()
    if d.get("msg") != "success":
        return []
    out = []
    for row in d.get("data", []):
        close = _num(row.get("close"))
        date = row.get("date")
        if not date or close is None:
            continue
        out.append({
            "date": date,
            "open": _num(row.get("open")), "high": _num(row.get("max")), "low": _num(row.get("min")),
            "close": close, "adj_close": close,
            "volume": _num(row.get("Trading_Volume")), "turnover": _num(row.get("Trading_money")),
        })
    return out


def _has_calendar_gap(dates: list[str], max_ratio: float = 3.0) -> bool:
    """跟generate_scores_momentum.py同名函式同一條邏輯，這裡自成一體複製一份
    （2026-08-28新增，B23實測發現的真bug：只看列數不夠，還要看這些列是不是
    真的連續——1,649/2,270檔在90列視窗裡混進了巨大日曆天缺口，見
    generate_scores_momentum.py::_has_calendar_gap()完整說明）。"""
    if len(dates) < 2:
        return False
    from datetime import datetime
    d0 = datetime.strptime(dates[0], "%Y-%m-%d")
    d1 = datetime.strptime(dates[-1], "%Y-%m-%d")
    return (d1 - d0).days > len(dates) * max_ratio


def target_codes() -> list[str]:
    """複製generate_scores_momentum.py的候選宇宙/非個股過濾邏輯，篩出「動能榜
    會用到、但目前深度不足或有日曆缺口」的股票清單。**2026-08-28修正（真bug，
    這輪才發現）**：原本只檢查`len(prices)<DEPTH_TARGET`，但列數足夠不代表
    這些列是連續的最近交易日——例如2337有90列卻是89列2024年舊資料+1列
    2026年新資料，列數過關但視窗其實充滿缺口，算出來的因子是垃圾數字
    （實測創新高因子算出+375%）。改成「列數不足 OR 最近60列有日曆缺口」
    都算需要回補。"""
    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prices = payload.get("prices", {})

    fund = json.loads(FUNDAMENTALS_PATH.read_text(encoding="utf-8")).get("fundamentals", {}) if FUNDAMENTALS_PATH.exists() else {}
    sd = json.loads(STOCK_DETAIL_PATH.read_text(encoding="utf-8")).get("stocks", {}) if STOCK_DETAIL_PATH.exists() else {}
    company = json.loads(COMPANY_INFO_PATH.read_text(encoding="utf-8")).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}

    candidate = set(fund) | set(sd) | set(prices)
    non_stock = {c for c, v in company.items() if v.get("industry") in NON_STOCK_INDUSTRIES}
    non_stock |= {c for c in candidate if _NON_STOCK_CODE_PATTERN.match(c)}
    universe = candidate - non_stock

    def needs_backfill(code: str) -> bool:
        rows = prices.get(code, [])
        if len(rows) < DEPTH_TARGET:
            return True
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        window = rows_sorted[-(DEPTH_TARGET + 1):]
        return _has_calendar_gap([r["date"] for r in window])

    shallow = {c for c in universe if needs_backfill(c)}
    return sorted(shallow)


def merge_backfill(existing: list[dict] | None, backfill: list[dict]) -> list[dict]:
    """欄位級合併，既有(daily排程，較即時/較準確)資料優先——只補既有沒有的
    日期，不覆蓋任何既有列。跟build_price_history.py::merge_rows()同一個
    邏輯，這裡自成一體複製一份。"""
    by_date = {r["date"]: dict(r) for r in backfill}
    for r in (existing or []):
        date = r["date"]
        merged = dict(by_date.get(date, {}))
        merged.update(r)
        by_date[date] = merged
    rows = sorted(by_date.values(), key=lambda r: r["date"])
    return rows[-PRICE_HISTORY_DAYS:]


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在")
        raise SystemExit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prices = payload.setdefault("prices", {})
    prior_count = len(prices)

    codes = target_codes()
    print(f"候選宇宙中深度不足({DEPTH_TARGET}列)的股票：{len(codes)} 檔，開始用FinMind即時API回補"
          f"（TWSE STOCK_DAY本輪已實測被反爬蟲整批擋下，改走這條路，見模組docstring）")

    backfilled, failed, skipped_no_gain, blocked_skip = 0, 0, 0, 0
    for i, code in enumerate(codes):
        try:
            rows = fetch_finmind_price(code)  # 內部已含3秒節流，不用另外sleep
            if not rows:
                failed += 1
                continue
            before = prices.get(code, [])
            before_len = len(before)
            # 2026-08-28修正（真bug，這輪親自抓到）：原本只比「列數是否增加」
            # 判斷有沒有補到——但很多目標股票本來就已經在90列的cap，補齊
            # 缺口後列數不會變多（還是90列），只是內容從「有巨大日曆缺口」
            # 變成「真正連續」，這種情況原本被誤判成「無增益」，其實是這支
            # 腳本最主要的價值所在。改成同時看列數增加「或」缺口狀態改善
            # （修好了）才算真的有補到。
            before_gap = _has_calendar_gap(sorted(r["date"] for r in before)) if before else True
            prices[code] = merge_backfill(before, rows)
            after = prices[code]
            after_len = len(after)
            after_gap = _has_calendar_gap(sorted(r["date"] for r in after)) if after else True
            if after_len > before_len or (before_gap and not after_gap):
                backfilled += 1
            else:
                skipped_no_gain += 1
        except Exception as e:
            # 2026-08-28新增：一旦被斷路器判定為封鎖中，後面每一檔都會立刻拋出
            # 同樣的RuntimeError（不會真的發請求）——與其讓迴圈空轉幾百次徒增
            # 「失敗」計數造成誤導，這裡偵測到「封鎖中」的訊息就直接整批中止，
            # 剩下沒處理到的股票留給下次（額度/封鎖解除後）重跑，不硬撐跑完。
            if "封鎖冷卻中" in str(e):
                blocked_skip = len(codes) - i
                print(f"  偵測到{FINMIND_SOURCE_KEY}進入封鎖冷卻，中止本輪剩餘{blocked_skip}檔（留待下次）：{e}")
                break
            print(f"  {code} 補歷史失敗（跳過，不影響其他檔）：{e}")
            failed += 1
        if (i + 1) % 50 == 0:
            print(f"  進度 {i+1}/{len(codes)}（已補{backfilled}、失敗{failed}、無增益{skipped_no_gain}）")

    new_count = len(prices)
    if new_count < prior_count:
        raise RuntimeError(f"覆蓋率不應該下降，但從 {prior_count} 變成 {new_count}——已中止寫入")

    payload.setdefault("meta", {})
    payload["meta"]["gap_backfill_note"] = (
        f"2026-08-28一次性回補（B23第一步）：對動能榜候選宇宙中深度不足"
        f"（<{DEPTH_TARGET}列）的股票，改用FinMind即時線上API（不經過本機"
        f"parquet快取/holdout）從{BACKFILL_START_DATE}補齊——這批股票的"
        "research端FinMind本機快取已經過期很久，daily排程單靠一天一筆要等"
        "數月才會自然補滿。TWSE官方STOCK_DAY單股端點本輪先試過，實測被"
        "反爬蟲整批擋下（53檔測試全部428），才改走這條路（見模組docstring"
        "「方法演進紀錄」）。"
        f"本輪：目標{len(codes)}檔、成功補進{backfilled}檔、{failed}檔查詢"
        f"失敗（配額/無資料）、{skipped_no_gain}檔查到資料但沒有新增天數"
        + (f"、{blocked_skip}檔因偵測到FinMind進入封鎖冷卻而中止未處理（留待下次）。" if blocked_skip else "。")
    )
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：目標{len(codes)}檔，成功補進{backfilled}檔、失敗{failed}檔、無增益{skipped_no_gain}檔")


if __name__ == "__main__":
    main()
