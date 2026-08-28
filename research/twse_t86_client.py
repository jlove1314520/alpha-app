"""TWSE T86 client -- primary institutional-buy/sell (三大法人) source (2026-08-26).

Same 2026-08-26 hybrid-architecture switch as yf_price_client.py: FinMind's
free tier hit a hard 402 wall, so institutional buy/sell now comes
PRIMARILY from TWSE's own open `T86` endpoint
(https://www.twse.com.tw/rwd/zh/fund/T86), with FinMind's
TaiwanStockInstitutionalInvestorsBuySell kept as fallback.

Structurally this endpoint is the OPPOSITE shape from FinMind's: FinMind is
per-stock, arbitrary date range, one call covers one stock's whole history.
T86 is per-DATE, ALL stocks in the market in one call. That means the
caching unit here is one parquet file per trading date (all ~14,500
listed securities -- stocks, ETFs, warrants, etc. -- for that date), not
one file per stock. This is actually a big efficiency win for backfilling
the whole universe: one HTTP call serves every stock_id's institutional
data for that day at once, instead of one call per stock. The tradeoff is
that getting one stock's multi-year history means having pulled (and
cached) every trading date in that range at least once -- see
backfill_t86.py for the resumable, date-batched backfill loop that builds
this cache up over multiple marathon cycles.

Field mapping (自營商 = 三大法人 − 外資 − 投信, same rule as
alpha-data/parsers.py's t86() -- ported here as *logic only*, alpha-data is
a frozen directory per CLAUDE.md and is never imported from or edited):
  外陸資買賣超股數(不含外資自營商) -> foreign_net
  投信買賣超股數                   -> trust_net
  三大法人買賣超股數合計           -> total_net
  dealer_net = total_net - foreign_net - trust_net

Holdout discipline: fetch_t86_day() itself does not know about VAL_END (a
single date has no "cap" concept), but institutional_daily_net_t86(), the
per-stock aggregator callers should use, filters to <= VAL_END exactly like
finmind_client.load_dev() and yf_price_client.fetch_yf_adjusted() do.
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    """2026-08-29新增（determinism_self_test.py實測發現），跟
    `finmind_client.py::_atomic_read_parquet()`同一份修法，自成一體
    複製——讀取端偶爾在另一個process正在os.replace()換名的瞬間開檔
    會遇到Windows暫時性PermissionError（不是資料損毀），加短重試。"""
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """2026-08-29新增（可重現性稽核）：跟`finmind_client.py::_atomic_to_
    parquet()`同一份修法，自成一體複製——`df.to_parquet(path)`不是atomic
    的，兩個process同時fetch同一個尚未快取的date會互相interleave寫入，
    可能產生截斷parquet檔，是回測不可重現的根因候選之一。改成寫進pid+uuid
    專屬臨時檔，`os.replace()`原子性換名，並發讀取者只會讀到完整新檔或
    完整舊檔。"""
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    df.to_parquet(tmp_path, index=False)
    # 2026-08-29新增（determinism_self_test.py實測發現，跟finmind_client.py
    # 同一份修法）：Windows的os.replace()在併發下偶爾拋PermissionError（暫時性
    # 檔案鎖，不是資料損毀），加短重試。
    for attempt in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))

DATA_DIR = Path(__file__).parent / "data" / "raw_twse_t86"
DATA_DIR.mkdir(parents=True, exist_ok=True)

T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"

_COLS = ["date", "stock_id", "foreign_net", "trust_net", "dealer_net", "total_net"]


class TWSEBlockedError(RuntimeError):
    """TWSE's own anti-scraping protection blocked this request (not a normal
    network error -- see fetch_t86_day()'s docstring). Callers (backfill_t86.py)
    should treat this as "stop immediately", not "retry"."""


def _cache_path(date_str: str) -> Path:
    return DATA_DIR / f"T86_{date_str}.parquet"


def _find_col(fields: list[str], *subs: str) -> int | None:
    for want in subs:
        for i, f in enumerate(fields):
            if want in f:
                return i
    return None


def fetch_t86_day(date_str: str, force_refresh: bool = False, timeout: float = 15.0,
                   max_retries: int = 3) -> pd.DataFrame:
    """One trading date's institutional buy/sell for every listed security.

    date_str: 'YYYYMMDD'. Returns the empty-but-correctly-columned frame
    (not an exception) for non-trading days (weekends/holidays) -- TWSE's
    own response for those is `stat != 'OK'`, which is expected and cached
    so repeated calls for the same non-trading date don't re-hit the network.
    """
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(T86_URL, params={
                "response": "json", "date": date_str, "selectType": "ALL",
            }, timeout=timeout)
            # **2026-08-26 發現**：TWSE 這個 `rwd` 端點（跟 openapi.twse.com.tw 的正式開放
            # 資料 API 不同，比較像是網站本身用的內部 AJAX 端點）有自己的反爬蟲封鎖，短時間
            # 內密集呼叫會被擋（回傳 307 + 一個「FOR SECURITY REASONS...」的 HTML 頁面，不是
            # JSON），這是實測到的（見 REPORT.md/DATA.md 2026-08-26 條目），不是理論猜測。
            # 這種情況必須明確辨識並直接中止整個回補流程（不能重試，重試只會讓封鎖更久），
            # 不能讓它落入下面泛用的 except 分支被誤判成普通網路錯誤而繼續浪費重試次數。
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE T86 端點回傳反爬蟲封鎖頁（date={date_str}）——這是伺服器端主動封鎖，"
                    "不是暫時性網路錯誤，重試無用，需要停止呼叫並等待封鎖解除（未知冷卻時間，"
                    "沒有官方文件說明；保守作法是這次執行直接停止，下次執行前先手動測試單一日期"
                    "確認封鎖是否已解除）。"
                )
            resp.raise_for_status()
            body = resp.json()
            break
        except TWSEBlockedError:
            raise
        except Exception as e:  # noqa: BLE001 -- network/5xx/timeout: worth retrying
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"T86 fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("data"):
        out = pd.DataFrame(columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    fields = body["fields"]
    rows = body["data"]
    i_code = _find_col(fields, "證券代號", "股票代號")
    i_foreign = _find_col(fields, "外陸資買賣超股數(不含外資自營商)", "外資買賣超")
    i_trust = _find_col(fields, "投信買賣超股數")
    i_total = _find_col(fields, "三大法人買賣超股數合計", "三大法人買賣超股數")
    if i_code is None or i_total is None:
        raise RuntimeError(f"T86 response for {date_str} is missing expected columns: {fields}")

    def _num(v: str) -> float | None:
        s = str(v).replace(",", "").strip()
        if s in ("", "-", "--"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    out_rows = []
    for r in rows:
        code = str(r[i_code]).strip()
        foreign = _num(r[i_foreign]) if i_foreign is not None else None
        trust = _num(r[i_trust]) if i_trust is not None else None
        total = _num(r[i_total])
        if total is None:
            continue
        dealer = (total - foreign - trust) if (foreign is not None and trust is not None) else None
        out_rows.append({
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
            "stock_id": code, "foreign_net": foreign, "trust_net": trust,
            "dealer_net": dealer, "total_net": total,
        })

    out = pd.DataFrame(out_rows, columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


# 2026-08-29馬拉松第200輪新增：process內快取，見_load_all_t86_grouped()docstring。
_T86_GROUPED_CACHE: dict[str, pd.DataFrame] | None = None
_T86_GROUPED_CACHE_KEY: tuple[int, float] | None = None


def _load_all_t86_grouped() -> dict[str, pd.DataFrame]:
    """把DATA_DIR底下所有T86_*.parquet讀進來一次、依stock_id分組快取在
    這個process的記憶體裡，同一個process內重複查詢不同股票時只查dict，
    不必重新掃描/讀取全部檔案。

    背景（2026-08-29馬拉松第200輪，接續round197留下的效能問題）：
    `institutional_daily_net_t86()`原本每次呼叫都重新glob+逐檔
    `read_parquet`全部T86快取檔（100%回補後約3300+檔、288MB），對
    `load_sample_with_factors()`這種對N個股票逐一呼叫的迴圈等於把全部
    檔案重複讀了N次——實測診斷：單一股票（僅40列價格資料）光是
    `prepare_factors()`就要37秒，追到`_institutional_daily_net()`每次都
    重新掃描全部3319個T86檔案是根因。改成process內只讀一次（實測17.6秒）、
    依stock_id分組快取後，後續每檔股票查詢只是dict查找，總時間從
    N×(掃描全部檔案) 降為 (掃描全部檔案一次)+N×(dict查找)。

    快取有效性用「檔案數量+最新mtime」當key判斷是否需要重建——理論上
    `backfill_t86.py`不會跟這裡的分析腳本同時在跑，但保守起見還是加這個
    檢查，避免同一個process執行期間如果檔案有變動卻用到舊快取。
    """
    global _T86_GROUPED_CACHE, _T86_GROUPED_CACHE_KEY
    files = sorted(DATA_DIR.glob("T86_*.parquet"))
    if not files:
        return {}
    key = (len(files), max(p.stat().st_mtime for p in files))
    if _T86_GROUPED_CACHE is not None and _T86_GROUPED_CACHE_KEY == key:
        return _T86_GROUPED_CACHE
    frames = []
    for p in files:
        day = _atomic_read_parquet(p)
        if not day.empty:
            frames.append(day)
    if not frames:
        _T86_GROUPED_CACHE = {}
        _T86_GROUPED_CACHE_KEY = key
        return _T86_GROUPED_CACHE
    combined = pd.concat(frames, ignore_index=True)
    grouped = {sid: g for sid, g in combined.groupby("stock_id", sort=False)}
    _T86_GROUPED_CACHE = grouped
    _T86_GROUPED_CACHE_KEY = key
    return grouped


def institutional_daily_net_t86(stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
    """Per-stock time series, built from whatever T86 daily caches already
    exist in DATA_DIR for the requested range -- does NOT fetch missing
    dates itself (that is backfill_t86.py's job, run as its own bounded
    marathon work unit). Returns only the dates already cached; an empty
    result means "nothing cached yet for this range", not "no institutional
    activity". Callers needing a completeness guarantee should check
    backfill_t86.py's state file for cache coverage over the range first.

    Columns match factors.py's _institutional_daily_net() output shape:
    date, foreign_net, trust_net, dealer_net, total_net.

    2026-08-29起改走`_load_all_t86_grouped()`process內快取（見該函式
    docstring的效能背景），語意跟舊版逐檔掃描完全相同（同樣是「檔案的
    date欄位落在[start_date, effective_end]區間內」的那些列），只是不再
    每次呼叫都重新讀取全部檔案。
    """
    from validation.holdout import VAL_END

    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    empty = pd.DataFrame(columns=["date", "foreign_net", "trust_net", "dealer_net", "total_net"])
    grouped = _load_all_t86_grouped()
    g = grouped.get(stock_id)
    if g is None or g.empty:
        return empty
    sub = g[(g["date"] >= start_date) & (g["date"] <= effective_end)]
    if sub.empty:
        return empty
    out = sub.sort_values("date").reset_index(drop=True)
    return out[["date", "foreign_net", "trust_net", "dealer_net", "total_net"]]


def cached_date_range() -> tuple[str | None, str | None, int]:
    """(earliest cached date, latest cached date, count of cached date-files) -- for
    state reporting in backfill_t86.py / TW_MARATHON_STATE.md, not used by the
    per-stock aggregator itself."""
    files = sorted(DATA_DIR.glob("T86_*.parquet"))
    if not files:
        return None, None, 0
    dates = [f.stem.replace("T86_", "") for f in files]
    return min(dates), max(dates), len(files)
