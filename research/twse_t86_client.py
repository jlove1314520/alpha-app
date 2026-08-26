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

import time
from pathlib import Path

import pandas as pd
import requests

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
        return pd.read_parquet(path)

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
        out.to_parquet(path, index=False)
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
    out.to_parquet(path, index=False)
    return out


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
    """
    from validation.holdout import VAL_END

    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    frames = []
    for p in sorted(DATA_DIR.glob("T86_*.parquet")):
        date_str = p.stem.replace("T86_", "")
        iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        if iso < start_date or iso > effective_end:
            continue
        day = pd.read_parquet(p)
        if day.empty:
            continue
        row = day[day["stock_id"] == stock_id]
        if not row.empty:
            frames.append(row)
    if not frames:
        return pd.DataFrame(columns=["date", "foreign_net", "trust_net", "dealer_net", "total_net"])
    out = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
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
