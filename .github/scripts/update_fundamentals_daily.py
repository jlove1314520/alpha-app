# -*- coding: utf-8 -*-
"""每日（排程）更新 data/fundamentals.json 的月營收/PER/PBR/殖利率快照，累積式寫回。

背景（2026-08-27）：`research/build_fundamentals_json.py` 產生的 `data/fundamentals.json`
是**手動一次性快照**——讀本機 `research/data/raw/` 底下的 FinMind parquet 快取整理
而成，但那份快取是 gitignored（`.gitignore`: `research/data/`），只存在互動 session
的本機，GitHub Actions runner 每次都是全新 checkout、拿不到，**不能把
`build_fundamentals_json.py` 原封不動掛進排程**（掛了也只會產出幾乎全空的檔案）。

這支腳本改用官方 TWSE openapi 的「最新一期全市場快照」端點（不需要 FinMind、
不需要本機快取），採跟 `fetch_market_tw.py` 的 `institutional_history` 一樣的
**累積式**寫法：讀 repo 裡已經 commit 的 `data/fundamentals.json`（起始種子是
2026-08-27 那次手動全量快照，已有 1749 檔 8 個月歷史）當底，每次執行只把「今天
的最新一筆」merge 進去（同年月覆蓋、新年月則 append 並捨棄超過 8 個月的舊資料），
跑得越久歷史就越完整，不需要一次補歷史區間。

資料源（全部官方開放資料，不需要金鑰，實測見 `research/DATA.md` 第474行附近）：
- 月營收：`openapi.twse.com.tw/v1/opendata/t187ap05_L`（TWSE上市）/
  `www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_OB`（TPEx上櫃，2026-08-27新增）
  ——全市場最新一期月營收快照，官方已經算好「去年同月增減(%)」，不需要自己拿
  前期資料做除法。
- 本益比/殖利率/淨值比：`openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`
  （TWSE上市）/ `www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis`
  （TPEx上櫃，2026-08-27新增）——全市場最新一期PER/PBR/殖利率快照。

**2026-08-27修正**：先前這裡誤記「TPEx上櫃股票無對應公開資料」，實際上
TPEx有對應的官方openapi端點（見上），已補上——**單點依賴一個市場的端點、
沒有先確認另一個市場是否也有對應資料源，是這裡先前的架構缺陷，不是
外部真的沒有資料**。
"""
from __future__ import annotations

import json
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "fundamentals.json"
TW_TZ = timezone(timedelta(hours=8))

REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
RATIOS_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
# 2026-08-27新增：TPEx（上櫃）官方對應端點，補上使用者指出的「上櫃股票缺口」——
# 這兩個端點欄位命名跟TWSE版本略有不同（見各自fetch函式），但語意對應。
TPEX_RATIOS_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
TPEX_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_OB"

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）。
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

MONTHS_TO_KEEP = 8  # App圖表用「近8月」，維持不變
# 2026-08-27新增：score_live.py的growth_quality因子需要「近12個月營收總和 vs
# 再前12個月營收總和」，24個月是硬性下限，跟research/build_fundamentals_json.py
# 的MONTHS_TO_KEEP=26保持一致（多留一點緩衝），存進獨立欄位revenue_history_scoring，
# 不影響既有month_revenue／App圖表。
SCORING_MONTHS_TO_KEEP = 26


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    """'1150825'（民國年3碼+月2碼+日2碼）-> '2026-08-25'。格式不符就回傳 None，不猜。"""
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def _roc_yearmonth(s: str) -> tuple[int, int] | None:
    """'11507'（民國年3碼+月2碼）-> (2026, 7)。"""
    s = str(s).strip()
    if len(s) != 5 or not s.isdigit():
        return None
    return int(s[:3]) + 1911, int(s[3:5])


def fetch_ratios() -> dict[str, dict]:
    r = _get_retry(RATIOS_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("BWIBBU_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("Code")
        if not code:
            continue
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        out[code] = {
            "date": date_iso,
            "per": _num(row.get("PEratio")),
            "pbr": _num(row.get("PBratio")),
            "dividend_yield": _num(row.get("DividendYield")),
        }
    return out


def fetch_revenue() -> dict[str, dict]:
    r = _get_retry(REVENUE_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap05_L 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("公司代號")
        ym = _roc_yearmonth(row.get("資料年月", ""))
        revenue_thousand = _num(row.get("營業收入-當月營收"))
        if not code or not ym or revenue_thousand is None:
            continue
        yoy_pct = _num(row.get("營業收入-去年同月增減(%)"))
        out[code] = {
            "year": ym[0],
            "month": ym[1],
            # TWSE官方單位是「仟元」，既有資料（來自FinMind parquet快取整理）是原始
            # 新台幣元，這裡乘1000對齊，否則前端圖表(/1e8換算成億)會整整差1000倍
            # ——實測驗證過：不轉換的話2330 2026/7會顯示成4.68億而不是正確的4676億。
            "revenue": revenue_thousand * 1000,
            "yoy": round(yoy_pct / 100, 4) if yoy_pct is not None else None,
        }
    return out


def fetch_ratios_tpex() -> dict[str, dict]:
    """TPEx（上櫃）版PER/PBR/殖利率，2026-08-27新增。欄位命名跟TWSE版
    （`fetch_ratios()`）不同：`SecuritiesCompanyCode`/`PriceEarningRatio`/
    `PriceBookRatio`/`YieldRatio`，語意對應但不是同一組鍵名。"""
    r = _get_retry(TPEX_RATIOS_URL, "tpex_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_mainboard_peratio_analysis 回傳非預期格式（可能是無效路徑回傳的HTML）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        if not code:
            continue
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        out[code] = {
            "date": date_iso,
            "per": _num(row.get("PriceEarningRatio")),
            "pbr": _num(row.get("PriceBookRatio")),
            "dividend_yield": _num(row.get("YieldRatio")),
        }
    return out


def fetch_revenue_tpex() -> dict[str, dict]:
    """TPEx（上櫃）版月營收，2026-08-27新增。欄位命名跟TWSE版
    （`fetch_revenue()`）完全相同（同屬MOPS財報格式），可以重用同一套解析邏輯。"""
    r = _get_retry(TPEX_REVENUE_URL, "tpex_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("mopsfin_t187ap05_OB 回傳非預期格式（可能是無效路徑回傳的HTML）")
    out: dict[str, dict] = {}
    for row in rows:
        code = row.get("公司代號")
        ym = _roc_yearmonth(row.get("資料年月", ""))
        revenue_thousand = _num(row.get("營業收入-當月營收"))
        if not code or not ym or revenue_thousand is None:
            continue
        yoy_pct = _num(row.get("營業收入-去年同月增減(%)"))
        out[code] = {
            "year": ym[0], "month": ym[1],
            "revenue": revenue_thousand * 1000,  # 同TWSE版一樣是「仟元」，見fetch_revenue()註解
            "yoy": round(yoy_pct / 100, 4) if yoy_pct is not None else None,
        }
    return out


def merge_revenue(existing: list[dict] | None, latest: dict, keep: int = MONTHS_TO_KEEP) -> list[dict]:
    rows = list(existing or [])
    rows = [r for r in rows if not (r.get("year") == latest["year"] and r.get("month") == latest["month"])]
    rows.append(latest)
    rows.sort(key=lambda r: (r["year"], r["month"]))
    return rows[-keep:]


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在——這支腳本設計上只做累積更新，"
              "第一次的完整快照要用 research/build_fundamentals_json.py 手動產生並 commit。")
        sys.exit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    fundamentals = payload.setdefault("fundamentals", {})

    errors = []
    ratios_updated = revenue_updated = 0
    ratios_updated_tpex = revenue_updated_tpex = 0

    try:
        ratios = fetch_ratios()
        for code, r in ratios.items():
            fundamentals.setdefault(code, {})["ratios"] = r
        ratios_updated = len(ratios)
    except Exception as e:
        print(f"PER/PBR/殖利率(TWSE) 更新失敗：{e}")
        errors.append(f"ratios_twse: {e}")

    try:
        revenue = fetch_revenue()
        for code, latest in revenue.items():
            entry = fundamentals.setdefault(code, {})
            entry["month_revenue"] = merge_revenue(entry.get("month_revenue"), latest)
            entry["revenue_history_scoring"] = merge_revenue(
                entry.get("revenue_history_scoring"), latest, keep=SCORING_MONTHS_TO_KEEP)
        revenue_updated = len(revenue)
    except Exception as e:
        print(f"月營收(TWSE) 更新失敗：{e}")
        errors.append(f"revenue_twse: {e}")

    # 2026-08-27新增：上櫃(TPEx)股票，使用者指出「上櫃股票一律加入TPEx自己的
    # openapi作為來源，不要只用TWSE端點」。TPEx代碼跟TWSE代碼不會重複（不同
    # 市場），直接setdefault合併不會互相覆蓋。
    try:
        ratios_tpex = fetch_ratios_tpex()
        for code, r in ratios_tpex.items():
            fundamentals.setdefault(code, {})["ratios"] = r
        ratios_updated_tpex = len(ratios_tpex)
    except Exception as e:
        print(f"PER/PBR/殖利率(TPEx) 更新失敗：{e}")
        errors.append(f"ratios_tpex: {e}")

    try:
        revenue_tpex = fetch_revenue_tpex()
        for code, latest in revenue_tpex.items():
            entry = fundamentals.setdefault(code, {})
            entry["month_revenue"] = merge_revenue(entry.get("month_revenue"), latest)
            entry["revenue_history_scoring"] = merge_revenue(
                entry.get("revenue_history_scoring"), latest, keep=SCORING_MONTHS_TO_KEEP)
        revenue_updated_tpex = len(revenue_tpex)
    except Exception as e:
        print(f"月營收(TPEx) 更新失敗：{e}")
        errors.append(f"revenue_tpex: {e}")

    payload["meta"] = {
        "generated_at": datetime.now(TW_TZ).isoformat(),
        # 2026-09-03（P0三-三.3）：每個資料檔的meta都要有source，跟generated_at一起讓STATUS.json/App設定頁能直接顯示來源與新鮮度
        "source": "TWSE openapi BWIBBU_ALL+t187ap05_L（上市）/ TPEx openapi tpex_mainboard_peratio_analysis+mopsfin_t187ap05_OB（上櫃），每日排程累積更新；起始種子=research/build_fundamentals_json.py（FinMind快取一次性快照）",
        "snapshot_note": (
            "起始種子是 2026-08-27 手動執行 build_fundamentals_json.py 的一次性快照"
            "（讀研究端FinMind歷史parquet快取整理，涵蓋TWSE+TPEx），此後由這支"
            "update_fundamentals_daily.py 排程改用官方openapi累積更新——"
            "月營收/PER/PBR/殖利率每次只更新官方端點回傳的「最新一期」，"
            "同年月覆蓋、新年月append且只保留近8個月。2026-08-27修正：TPEx上櫃股票"
            "改用TPEx自己的openapi（tpex_mainboard_peratio_analysis/"
            "mopsfin_t187ap05_OB）更新，之前誤記「無對應公開資料」，實際上有。"
        ),
        "ratios_updated_count": ratios_updated,
        "revenue_updated_count": revenue_updated,
        "ratios_updated_count_tpex": ratios_updated_tpex,
        "revenue_updated_count_tpex": revenue_updated_tpex,
        "errors": errors,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：PER/PBR/殖利率更新 TWSE {ratios_updated} 檔+TPEx {ratios_updated_tpex} 檔，"
          f"月營收更新 TWSE {revenue_updated} 檔+TPEx {revenue_updated_tpex} 檔"
          f"（合計 {len(fundamentals)} 檔有資料）")
    if errors:
        print(f"部分失敗（不中止，維持既有資料）：{errors}")


if __name__ == "__main__":
    main()
