"""先.一二七-B2a（收件匣 006，2026-10-21）：f_dividend_yield_ttm 分母稽核，只讀、離線。

量「factors.py 實際用的分母（price_df 的 close）」與「FinMind 原始收盤」算出的殖利率差多少。
adjusted_price_series() 走 yfinance 時 close＝還原價（adjust.py 文件），走 FinMind 時 close＝原始價。
擋網路（只讀本機快取），不改任何程式、不跑回測、不碰 holdout（load_dev 截在 VAL_END）。
跑法：cd research && python audit_b2a_dividend_yield_denominator.py
"""
import sys, socket, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
def _no_net(*a, **k): raise RuntimeError("network blocked (B2a offline probe)")
socket.socket.connect = _no_net
socket.create_connection = _no_net
import pandas as pd, numpy as np
import adjust, factors
from finmind_client import load_dev
out = {}
for sid in ["2412", "2884", "1101"]:
    p = adjust.adjusted_price_series(sid, "2010-01-01")
    src = p["source"].iloc[-1] if "source" in p.columns and len(p) else None
    raw = load_dev("TaiwanStockPrice", sid, "2010-01-01")[["date", "close"]].rename(columns={"close": "raw_close"})
    raw["date"] = pd.to_datetime(raw["date"]); p["date"] = pd.to_datetime(p["date"])
    div = factors._dividend_yield_ttm_cash(sid, "2010-01-01")
    div["pit_date"] = pd.to_datetime(div["pit_date"])
    m = p[["date", "close", "adj_close"]].merge(raw, on="date", how="left").sort_values("date")
    m = pd.merge_asof(m, div.sort_values("pit_date"), left_on="date", right_on="pit_date", direction="backward")
    rows = []
    for y in [2012, 2016, 2020, 2024]:
        r = m[m["date"].dt.year == y].dropna(subset=["raw_close"]).tail(1)
        if r.empty: continue
        r = r.iloc[0]
        ttm = r["ttm_cash_dividend"]
        y_fact = ttm / r["close"]; y_raw = ttm / r["raw_close"]
        rows.append(dict(date=str(r["date"].date()), ttm_cash=round(float(ttm), 4),
            factor_close=round(float(r["close"]), 3), raw_close=round(float(r["raw_close"]), 3),
            yield_factor_pct=round(float(y_fact) * 100, 2), yield_raw_pct=round(float(y_raw) * 100, 2),
            diff_pp=round(float(y_fact - y_raw) * 100, 2), ratio=round(float(y_fact / y_raw), 3)))
    out[sid] = dict(price_source=src, rows=rows)
print(json.dumps(out, ensure_ascii=False, indent=1))
