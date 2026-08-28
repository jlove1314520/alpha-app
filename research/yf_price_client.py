"""yfinance price client -- primary TW price/volume source (2026-08-26).

FinMind's free tier hit a hard 402 (quota exhausted) wall on 2026-08-26,
blocking every downstream research task that needs price history. Per the
user's explicit decision that day: price/volume history switches to
yfinance as the PRIMARY source. yfinance is free, has no comparable rate
limit for this project's request volume, and -- unlike FinMind's free tier
(TaiwanStockPriceAdj is paid-only, see DATA.md) -- returns already
dividend/split-adjusted closes via `auto_adjust=True`, so this also
sidesteps the manual back-adjustment adjust.py had to reconstruct from raw
TaiwanStockPrice + TaiwanStockDividend.

TW-listed (TWSE) tickers use the `.TW` suffix; OTC (TPEx) tickers use
`.TWO`. This module doesn't know in advance which a given stock_id is, so
it tries `.TW` first, then `.TWO` -- exactly one of the two normally
returns data. Delisted names are frequently NOT carried on Yahoo Finance at
all (both suffixes come back empty); callers should treat an empty result
here as "fall back to the FinMind-based reconstruction in adjust.py", not
as an error.

Caching mirrors finmind_client.py's convention: keyed on the exact
(stock_id, start_date, end_date) request, dumb-but-trustworthy, one parquet
file per request under research/data/raw_yf/.

Holdout discipline: capped at VAL_END via validation.holdout.cap_to_dev(),
same as every other data source in this pipeline -- yfinance itself has no
concept of "dev period", so this module enforces it the same way
finmind_client.load_dev() does for FinMind.
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import yfinance as yf


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
    的，兩個process同時fetch同一個尚未快取的組合會互相interleave寫入，
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

DATA_DIR = Path(__file__).parent / "data" / "raw_yf"
DATA_DIR.mkdir(parents=True, exist_ok=True)

_SUFFIXES = (".TW", ".TWO")


def _cache_path(stock_id: str, start_date: str, end_date: str | None) -> Path:
    end_part = end_date or "latest"
    return DATA_DIR / f"{stock_id}__{start_date}__{end_part}.parquet"


def _fetch_one_suffix(stock_id: str, suffix: str, start_date: str, end_date: str | None,
                       max_retries: int = 2) -> pd.DataFrame:
    ticker = f"{stock_id}{suffix}"
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            df = yf.Ticker(ticker).history(
                start=start_date, end=end_date, auto_adjust=True, raise_errors=False,
            )
            return df
        except Exception as e:  # noqa: BLE001 -- transient network errors worth a retry
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    return pd.DataFrame()


def fetch_yf_adjusted(
    stock_id: str,
    start_date: str = "2010-01-01",
    end_date: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Adjusted daily OHLCV for a TW stock_id, capped at VAL_END.

    Returns columns: date, open, high, low, close, volume, source
    (source is always 'yfinance' here -- callers combining this with the
    FinMind fallback should stamp their own 'source' column when they fall
    back, so the two are distinguishable downstream).

    Empty DataFrame (not an exception) if neither `.TW` nor `.TWO` has any
    rows in range -- this is the normal, expected outcome for names not
    carried on Yahoo Finance (many delisted tickers), not a bug.
    """
    from validation.holdout import VAL_END

    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    path = _cache_path(stock_id, start_date, effective_end)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    df = pd.DataFrame()
    for suffix in _SUFFIXES:
        df = _fetch_one_suffix(stock_id, suffix, start_date, effective_end)
        if not df.empty:
            break

    if df.empty:
        out = pd.DataFrame(columns=[
            "date", "stock_id", "open", "high", "low", "close", "volume", "source",
            "max", "min", "Trading_Volume", "Trading_money",
        ])
    else:
        df = df.reset_index()
        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)
        out = pd.DataFrame({
            "date": pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d"),
            "stock_id": stock_id,
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": close,
            "volume": volume,
            "source": "yfinance",
            # FinMind-schema aliases, so every consumer written against
            # finmind_client's TaiwanStockPrice column names (prepare_factors()
            # in factors.py, backtest/engine.py's limit-up/down check) keeps
            # working unchanged regardless of which source served the row.
            "max": df["High"].astype(float),
            "min": df["Low"].astype(float),
            "Trading_Volume": volume,
            # FinMind's Trading_money is the day's actual traded NT$ value
            # (intraday price x volume, summed tick by tick). yfinance only
            # gives us the daily close, so this is close*volume -- a same-
            # order-of-magnitude approximation, not the exact figure. Only
            # consumed here as a 20-day rolling-average normalizer (f_inst_flow),
            # where this approximation is immaterial; do not rely on it for
            # anything that needs the precise traded value.
            "Trading_money": close * volume,
        })
        # Belt-and-suspenders: yfinance's `end` param is already <= effective_end,
        # but re-filter defensively (same pattern as finmind_client.load_dev()).
        out = out[out["date"] <= effective_end].reset_index(drop=True)

    _atomic_to_parquet(out, path)
    return out


def fetch_yf_index(
    ticker: str = "^TWII",
    start_date: str = "2010-01-01",
    end_date: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Same idea as fetch_yf_adjusted() but for an INDEX ticker (TAIEX = ^TWII
    on Yahoo Finance), not a stock_id -- indices don't get the .TW/.TWO
    suffix treatment. Used by generate_scores_v2.py's real-time path
    (see realtime_asof.py) to get the market/gate series without depending
    on FinMind's TaiwanStockPrice/TAIEX, which is subject to the same 402
    quota wall as everything else on that side.

    Returns columns: date, open, high, low, close, volume -- deliberately
    NOT the FinMind-alias columns fetch_yf_adjusted() adds (max/min/
    Trading_Volume/Trading_money), since the only consumer
    (strategies/weinstein_stage2.py's prepare_market_data()) only reads
    date/close.
    """
    from validation.holdout import VAL_END

    effective_end = end_date if (end_date and end_date <= VAL_END) else VAL_END
    path = DATA_DIR / f"INDEX_{ticker.lstrip('^')}__{start_date}__{effective_end}.parquet"
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    df = _fetch_one_suffix(ticker, "", start_date, effective_end)  # empty suffix: ticker used as-is
    if df.empty:
        out = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    else:
        df = df.reset_index()
        out = pd.DataFrame({
            "date": pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d"),
            "open": df["Open"].astype(float),
            "high": df["High"].astype(float),
            "low": df["Low"].astype(float),
            "close": df["Close"].astype(float),
            "volume": df["Volume"].astype(float),
        })
        out = out[out["date"] <= effective_end].reset_index(drop=True)

    _atomic_to_parquet(out, path)
    return out


def clear_cache(pattern: str = "*") -> int:
    n = 0
    for p in DATA_DIR.glob(f"{pattern}.parquet"):
        p.unlink()
        n += 1
    return n
