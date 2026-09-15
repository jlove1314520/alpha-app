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

**分母改用 TWSE 官方端點，拔掉最後一個 FinMind 依賴（2026-09-15，「週六.四」
／「其餘」條目）**：原本以為 TWSE 沒有公布全市場加總的「融資金額(元)」，只有
逐股「融資餘額(張)」（`openapi.twse.com.tw/v1/exchangeReport/MI_MARGN`），
所以退而用 FinMind `TaiwanStockTotalMarginPurchaseShortSale` 當分母。
2026-09-15 重新查證發現：**這個判斷只查了 openapi.twse.com.tw 這一個端點
家族，沒查 www.twse.com.tw/rwd 這個端點家族**（跟 `fetch_market_tw.py` 的
T86 三大法人是同一個網站家族，本專案已有先例）。實測
`https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&date=YYYYMMDD&selectType=ALL`
的 `tables[0]`（標題「信用交易統計」）就有一列「融資金額(仟元)」，其「今日
餘額」欄位就是我們要的全市場融資金額——2026-09-11 實測值 587,871,180(仟元)
×1000＝587,871,180,000(元)，跟改版前 `data/margin_maintenance.json` 同一天
（2026-09-11）的 FinMind 舊值 587,871,180,000(元) 完全吻合，確認是同一個
統計口徑，不是巧合。

跟 `T86_URL` 同一個網站家族，套用同一套風險控管：只抓「今天」一天（不回補
歷史）、獨立的 rate-limit 來源鍵（`twse_margn_rwd`，不跟 `twse_openapi` 共用
節流額度）、帶 `Referer`/`User-Agent`（同 `fetch_market_tw.py::
fetch_institutional_aggregate()` 的既有慣例）。**FinMind 呼叫已完全移除**，
這支腳本現在零 FinMind 依賴。
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
# 2026-09-15（週六.四／其餘）全市場融資金額分母，取代原本的FinMind依賴。
# 跟T86_URL（fetch_market_tw.py）同一個www.twse.com.tw/rwd網站家族，同樣的
# 反爬蟲風險考量：只抓「今天」一天、獨立rate-limit來源鍵、帶Referer/UA。
MARGIN_MONEY_RWD_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
HISTORY_DAYS_KEEP = 60

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟其他.github/scripts/*.py同一套schema/同一份共用狀態檔data/rate_limit_
# state.json，各自複製一份邏輯——跨repo/跨目錄不import是既有慣例）。
# 2026-09-15：本檔已拔掉FinMind依賴（見模組docstring），source key改用
# "twse_openapi"（既有）/"tpex_openapi"（既有）/"twse_margn_rwd"（新增，
# www.twse.com.tw/rwd家族獨立額度，不跟openapi家族共用），不再有"finmind"。
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


MARGIN_MONEY_LOOKBACK_DAYS = 5  # 假日/尚未發布時往回找，同FinMind舊版10天窗口的精神但範圍更小


def _fetch_margin_money_for_date(date_str: str, headers: dict) -> tuple[str, float] | None:
    """單日查詢，查無資料（假日/尚未發布）回 None，HTTP異常一律往上拋。"""
    _rate_limit_wait_or_raise("twse_margn_rwd")
    r = requests.get(MARGIN_MONEY_RWD_URL, params={
        "response": "json", "date": date_str, "selectType": "ALL",
    }, headers=headers, timeout=20)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block("twse_margn_rwd", r.status_code, r.text[:200])
        raise RuntimeError(f"twse_margn_rwd回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("tables"):
        return None
    table = body["tables"][0]
    fields = table.get("fields", [])
    try:
        today_idx = fields.index("今日餘額")
    except ValueError:
        raise RuntimeError(f"TWSE信用交易統計回應欄位變了，找不到「今日餘額」：{fields}")
    money_row = next((row for row in table.get("data", []) if row and row[0] == "融資金額(仟元)"), None)
    if money_row is None:
        raise RuntimeError(f"TWSE信用交易統計回應裡找不到「融資金額(仟元)」列：{table.get('data')}")
    money_thousand = _num(money_row[today_idx])
    if money_thousand is None:
        raise RuntimeError(f"「融資金額(仟元)」今日餘額解析失敗：{money_row}")
    raw_date = body["date"]  # "20260914" 格式，轉成跟其他欄位一致的ISO格式
    iso_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    return iso_date, int(round(money_thousand * 1000))


def fetch_market_margin_money() -> tuple[str, float]:
    """全市場融資金額（分母），改用TWSE官方www.twse.com.tw/rwd端點（見模組
    docstring 2026-09-15更新說明）。跟T86一樣「只抓今天」會在假日/當日尚未
    發布時直接失敗，比舊版FinMind（抓近10天取最後一筆）更容易誤報
    data_incomplete，所以往回找最多`MARGIN_MONEY_LOOKBACK_DAYS`天、取第一個
    有資料的日期，維持舊版的容錯精神（範圍縮小到5天，避免真的連續多天無
    資料時還一直往回掃）。"""
    headers = {
        "Referer": "https://www.twse.com.tw/zh/trading/margin/mi-margn.html",
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
    }
    last_err = None
    for back in range(MARGIN_MONEY_LOOKBACK_DAYS + 1):
        date_str = (datetime.now(TW_TZ).date() - timedelta(days=back)).strftime("%Y%m%d")
        try:
            result = _fetch_margin_money_for_date(date_str, headers)
        except Exception as e:
            last_err = e
            break  # HTTP層級異常（含封鎖）不繼續往回試，避免額外觸發風險
        if result is not None:
            return result
    if last_err:
        raise last_err
    raise RuntimeError(f"TWSE信用交易統計近{MARGIN_MONEY_LOOKBACK_DAYS + 1}天都查無資料")


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
    # 2026-08-27 修正（使用者要求）：分母（全市場融資金額）失敗時，改成
    # 寫入一筆「今天有資料，但不完整」的明確記錄（ratio_pct=None、
    # data_incomplete=True），不再直接跳過不寫——舊行為的問題是：跳過之後
    # history最後一筆仍是幾天前「看起來正常」的百分比，畫面上的日期雖然沒動，
    # 但一個正常大小的數字很容易被誤讀成「今天的維持率就是這樣」。現在即使
    # 分母失敗，也讓App知道「今天嘗試過，但這個數字不可信」，不是靜默沿用舊值。
    try:
        money_date, margin_money = fetch_market_margin_money()
        data_incomplete = False
        incomplete_reason = None
    except Exception as e:
        print(f"分母（TWSE全市場融資金額）取得失敗：{e}")
        money_date, margin_money = None, None
        data_incomplete = True
        incomplete_reason = f"TWSE全市場融資金額取得失敗：{e}"

    ratio = collateral_value / margin_money * 100 if margin_money else None
    record = {
        "date": today,
        "margin_money_date": money_date,
        "collateral_value": round(collateral_value) if collateral_value else None,
        "margin_money": margin_money,
        "matched_stocks": matched,
        "ratio_pct": round(ratio, 2) if ratio is not None else None,
        "data_incomplete": data_incomplete,
        "incomplete_reason": incomplete_reason,
        # 2026-09-03（P0三-三.3）：這個檔案頂層是list（App/舊解析器都依賴這個形狀，不改），
        # 時間戳與來源改寫進每一筆record，最後一筆的generated_at就是整份檔案的產生時間。
        "generated_at": datetime.now(TW_TZ).isoformat(),
        "source": "分子=TWSE官方MI_MARGN(逐股融資餘額)×STOCK_DAY_ALL(逐股收盤價)加總；分母=TWSE官方www.twse.com.tw/rwd信用交易統計「融資金額(仟元)」今日餘額×1000（一天一次，2026-09-15起拔掉FinMind依賴）",
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
