# -*- coding: utf-8 -*-
"""先.一二九-2①（2026-10-22，收件匣 011）：f_dividend_yield_ttm 修正的自測 3 項。離線（擋網路、只讀本機快取）、
只讀 load_dev（截在 VAL_END）、不跑回測、不計 N。

1. 窗口只取一年份：合成資料（年配除息日提前、季配、半年配、重複列）＋ 2412 實際資料（2012 年不再重複計入）。
2. 分母＝原始收盤：2884、1101（yfinance 路徑）每年最後一個交易日，因子值 == 近 12 月股利 ÷ FinMind 原始收盤；
   2412（FinMind 路徑）== 近 12 月股利 ÷ close。
3. 不看未來：把股利表與價格表都截在 T 之前重算，T 以前的因子值逐列相同。

跑法：cd research && python selftest_dividend_yield_fix.py
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (先.一二九-2 selftest)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import adjust  # noqa: E402
import factors  # noqa: E402
from finmind_client import load_dev  # noqa: E402

START = "2010-01-01"
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def ttm_at(div, date):
    t = factors._dividend_yield_ttm_cash_from_df(div)
    t = t[pd.to_datetime(t["pit_date"]) <= pd.Timestamp(date)]
    return float(t["ttm_cash_dividend"].iloc[-1]) if len(t) else float("nan")


def ev(ex, cash, period):
    return {"CashExDividendTradingDate": ex, "CashEarningsDistribution": cash, "year": period}


# ---- 1. 窗口只取一年份 ----
annual = pd.DataFrame([ev("2011-07-21", 5.0, "99年"), ev("2012-07-17", 6.0, "100年")])
check("1a 年配除息日提前（相隔 362 天）只算最新一年", ttm_at(annual, "2012-12-31") == 6.0, f"={ttm_at(annual, '2012-12-31')}")
quarterly = pd.DataFrame([ev(d, 1.0 + i, f"{111 + (i + 2) // 4}年第{(i + 2) % 4 + 1}季")
                          for i, d in enumerate(["2023-03-16", "2023-06-15", "2023-09-14", "2023-12-14", "2024-03-14"])])
check("1b 季配只算最新 4 季", ttm_at(quarterly, "2024-03-31") == 2 + 3 + 4 + 5, f"={ttm_at(quarterly, '2024-03-31')}")
half = pd.DataFrame([ev("2023-01-10", 1.0, "111年前半年度"), ev("2023-07-10", 2.0, "111年後半年度"),
                     ev("2024-01-05", 3.0, "112年前半年度")])
check("1c 半年配只算最新 2 個半年", ttm_at(half, "2024-01-31") == 5.0, f"={ttm_at(half, '2024-01-31')}")
dup = pd.DataFrame([ev("2024-07-04", 4.0, "112年"), ev("2024-07-04", 4.0, "112年"), ev("2024-07-04", 0.5, "112年")])
check("1d 完全相同的列只計一次、同期間不同金額的列都算", ttm_at(dup, "2024-12-31") == 4.5, f"={ttm_at(dup, '2024-12-31')}")
div2412 = load_dev("TaiwanStockDividend", "2412", START)
v = ttm_at(div2412, "2012-12-28")
check("1e 2412 2012-12-28 不再重複計入（舊版 10.985）", 5.0 < v < 6.0, f"={v:.4f}")

# ---- 2. 分母＝原始收盤 ----
for sid in ["2884", "1101", "2412"]:
    px = adjust.adjusted_price_series(sid, START)
    src = str(px["source"].iloc[-1])
    d = px.sort_values("date").reset_index(drop=True).copy()
    d = factors._asof_join(d, factors._dividend_yield_ttm_cash(sid, START), "ttm_cash_dividend", "ttm")
    raw = factors._raw_close_for_yield(d, sid, START)
    d["f"] = np.where(raw > 0, d["ttm"] / raw, np.nan)
    rawp = load_dev("TaiwanStockPrice", sid, START)[["date", "close"]].rename(columns={"close": "raw_close"})
    rawp["date"] = rawp["date"].astype(str).str[:10]
    d["date"] = d["date"].astype(str).str[:10]
    m = d.merge(rawp, on="date", how="left")
    bad = []
    for y in (2012, 2016, 2020, 2024):
        r = m[m["date"].str[:4] == str(y)].dropna(subset=["raw_close", "ttm"]).tail(1)
        if r.empty:
            continue
        exp = float(r["ttm"].iloc[0]) / float(r["raw_close"].iloc[0])
        got = float(r["f"].iloc[0])
        if abs(got - exp) > 1e-12:
            bad.append((y, got, exp))
        print(f"     {sid}({src}) {r['date'].iloc[0]} 股利 {float(r['ttm'].iloc[0]):.3f} ÷ 原始收盤 {float(r['raw_close'].iloc[0]):.2f}"
              f" = {got:.2%}（還原價 {float(r['close'].iloc[0]):.2f}）")
    check(f"2 {sid}（{src} 路徑）因子分母＝原始收盤", not bad, str(bad) if bad else "")

# ---- 3. 不看未來 ----
T = "2016-06-30"
for sid in ["2884", "2330"]:
    px = adjust.adjusted_price_series(sid, START)
    div = load_dev("TaiwanStockDividend", sid, START)

    def yields(div_df, px_df):
        d = px_df.sort_values("date").reset_index(drop=True).copy()
        d = factors._asof_join(d, factors._dividend_yield_ttm_cash_from_df(div_df), "ttm_cash_dividend", "ttm")
        raw = factors._raw_close_for_yield(d, sid, START)
        return pd.Series(np.where(raw > 0, d["ttm"] / raw, np.nan), index=d["date"].astype(str).str[:10])

    full = yields(div, px)
    cut = yields(div[div["CashExDividendTradingDate"].astype(str) <= T],
                 px[px["date"].astype(str).str[:10] <= T])
    a = full[full.index <= T]
    same = len(a) == len(cut) and np.allclose(a.to_numpy(), cut.to_numpy(), equal_nan=True, rtol=0, atol=0)
    check(f"3 {sid} 截在 {T} 重算，之前 {len(a)} 列逐列相同", same, f"非 NaN {int(a.notna().sum())} 列")

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
