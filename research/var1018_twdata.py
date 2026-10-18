"""先.一一三-B1 V4／V5 共用：只讀本機快取的台股日線＋股利還原報酬（零外部請求）。

- 價格：合併 `research/data/raw/TaiwanStockPrice__<代號>__*.parquet` 所有本機檔（不同起始日的快取），同日期去重。
  不呼叫 `adjust.adjusted_price_series()`——那支在本機沒有快取時會改打 yfinance／FinMind，單發試驗不得在跑的當下多發請求。
- 股利還原：本機 `TaiwanStockDividend__<代號>__*.parquet` 交給 `adjust._dividend_events_from_df()`（純函式，同一套
  現金股利／股票股利 ÷10／現金增資 ÷1000 公式）算每個除權息日的因子；除權息日報酬＝close_t ÷ (close_{t−1}×factor) − 1。
  分割、減資、面額變更沒有納入（2007～2024 期間少見；結果檔標示），屬已知簡化。
- 一律截到 holdout.VAL_END（2024-12-31）。
"""
from __future__ import annotations

import glob
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from adjust import _dividend_events_from_df
from validation import holdout

RAW = Path(__file__).parent / "data" / "raw"
VAL_END = pd.Timestamp(holdout.VAL_END)


def codes_with_price(pattern: str = r"^[1-9]\d{3}$") -> list[str]:
    """本機有日線檔的代號（預設只取 4 碼、非 0 開頭＝一般普通股，排除 ETF／權證）。"""
    out = set()
    for f in glob.glob(str(RAW / "TaiwanStockPrice__*__*.parquet")):
        m = re.match(r"TaiwanStockPrice__([^_]+)__", Path(f).name)
        if m and re.match(pattern, m.group(1)):
            out.add(m.group(1))
    return sorted(out)


def _read_all(prefix: str, code: str) -> pd.DataFrame:
    parts = []
    for f in glob.glob(str(RAW / f"{prefix}__{code}__*.parquet")):
        d = pd.read_parquet(f)
        if not d.empty and "date" in d.columns:
            parts.append(d)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


@lru_cache(maxsize=None)
def daily(code: str) -> pd.DataFrame:
    """date／open／high／low／close／money（成交值）／ret_adj（股利還原日報酬）。沒資料回空表。"""
    px = _read_all("TaiwanStockPrice", code)
    if px.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "money", "ret_adj"])
    px["date"] = pd.to_datetime(px["date"])
    px = px[(px["date"] <= VAL_END) & (px["close"] > 0)].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    px = px.rename(columns={"max": "high", "min": "low", "Trading_money": "money"})
    ret = px["close"].pct_change()
    div = _read_all("TaiwanStockDividend", code)
    n_adj = 0
    if not div.empty:
        tds = [d.strftime("%Y-%m-%d") for d in px["date"]]
        cbd = dict(zip(tds, px["close"]))
        try:
            ev = _dividend_events_from_df(div.drop_duplicates(), cbd, tds)
        except Exception:  # noqa: BLE001 —— 股利表格式異常就不還原，照實標示
            ev = []
        pos = {d: i for i, d in enumerate(tds)}
        for e in ev:
            i = pos.get(str(e["ex_date"])[:10])
            if i and i > 0 and e["factor"] > 0:
                ret.iloc[i] = px["close"].iloc[i] / (px["close"].iloc[i - 1] * e["factor"]) - 1
                n_adj += 1
    px["ret_adj"] = ret
    px.attrs["n_dividend_adjustments"] = n_adj
    return px[["date", "open", "high", "low", "close", "money", "ret_adj"]]


def cum_return(d: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """start 當天收盤買、end 當天收盤賣的還原報酬（兩天都要有價格）。"""
    s = d.set_index("date")
    if start not in s.index or end not in s.index:
        return None
    r = s.loc[(s.index > start) & (s.index <= end), "ret_adj"].fillna(0.0)
    return float(np.prod(1 + r.to_numpy()) - 1)


def market_calendar(codes: list[str], start: str, end: str, min_share: float = 0.5) -> list[pd.Timestamp]:
    """交易日＝當天有價格的股票數 ≥ 這段期間單日最多檔數的 min_share（避免零星資料日被當成交易日）。"""
    cnt: dict = {}
    for c in codes:
        for t in daily(c)["date"]:
            if pd.Timestamp(start) <= t <= pd.Timestamp(end):
                cnt[t] = cnt.get(t, 0) + 1
    if not cnt:
        return []
    mx = max(cnt.values())
    return sorted(t for t, n in cnt.items() if n >= mx * min_share)
