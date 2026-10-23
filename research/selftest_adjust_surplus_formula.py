# -*- coding: utf-8 -*-
"""先.一三三-1d／收件匣 023 A（2026-10-23）自測：adjust.py FinMind 股利公式加資本公積配息／配股。離線、零請求、不算報酬。

1. 公式：合成一列「盈餘配息 0.35＋公積配息 2.12、前收 12.05」→ 係數＝(12.05−2.47)/12.05（2331 2012-08-15 官方參考價 9.58 的形狀）；
   只有公積配股 1 元（＝每股配 0.1 股）→ 係數＝1/1.1；只有公積、沒有盈餘的列不再被跳過。
2. 實際案例（從 data/adjust_surplus_fix_impact.json 取 2015 以後變動最大的 3 個事件）：新係數＝(前收−盈餘配息−公積配息)/(1+(盈餘配股+公積配股)/10)/前收，
   且除息日還原報酬 |r| < 11%（2015-06 後漲跌幅 ±10%）。
3. 回歸：固定種子 30 檔「沒有任何公積配發」的股票，修正前後 adj_close 全期逐值相同。
跑法：cd research && python selftest_adjust_surplus_formula.py <修正前 adjust.py 路徑>
"""
import importlib.util
import json
import random
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import adjust as NEW  # noqa: E402
from finmind_client import _cache_path, load_dev  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

START = "2010-01-01"
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def offline(mod):
    real = mod.load_dev

    def f(ds, sid, *a, **k):
        st = a[0] if a else START
        if ds in ("TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice", "TaiwanStockParValueChange") \
                and not _cache_path(ds, sid, st, VAL_END).exists():
            return pd.DataFrame()
        return real(ds, sid, *a, **k)
    mod.load_dev = f


offline(NEW)

# 1. 合成
cb = {"2012-08-14": 12.05, "2012-08-15": 9.6}
td = list(cb)
row = lambda **k: {"CashExDividendTradingDate": "2012-08-15", "StockExDividendTradingDate": "", "CashEarningsDistribution": 0.0,  # noqa: E731
                   "CashStatutorySurplus": 0.0, "StockEarningsDistribution": 0.0, "StockStatutorySurplus": 0.0,
                   "CashIncreaseSubscriptionRate": 0.0, "CashIncreaseSubscriptionpRrice": 0.0, **k}
e = NEW._dividend_events_from_df(pd.DataFrame([row(CashEarningsDistribution=0.35, CashStatutorySurplus=2.12)]), cb, td)
check("1a 盈餘＋公積配息", len(e) == 1 and abs(e[0]["factor"] - (12.05 - 2.47) / 12.05) < 1e-12, f"{e[0]['factor'] if e else None}")
e = NEW._dividend_events_from_df(pd.DataFrame([row(StockStatutorySurplus=1.0)]), cb, td)
check("1b 只有公積配股（不再被跳過）", len(e) == 1 and abs(e[0]["factor"] - 1 / 1.1) < 1e-12, f"{e[0]['factor'] if e else None}")
e = NEW._dividend_events_from_df(pd.DataFrame([row(CashStatutorySurplus=float("nan"), CashEarningsDistribution=0.5)]), cb, td)
check("1c 公積欄 NaN 當 0", len(e) == 1 and abs(e[0]["factor"] - (12.05 - 0.5) / 12.05) < 1e-12, f"{e[0]['factor'] if e else None}")

# 2. 實際案例
imp = json.loads((Path(__file__).parent / "data" / "adjust_surplus_fix_impact.json").read_text(encoding="utf-8"))
evs = []
for s in imp["stocks"]:
    for ev in s.get("events") or []:
        if ev["ex_date"] >= "2015-07-01" and ev.get("factor_new") and ev.get("factor_old") and ev["factor_new"] != ev["factor_old"]:
            evs.append((abs(ev["factor_new"] - ev["factor_old"]), s["stock_id"], ev))
for _, sid, ev in sorted(evs, reverse=True)[:3]:
    div = load_dev("TaiwanStockDividend", sid, START)
    raw = load_dev("TaiwanStockPrice", sid, START).sort_values("date")
    r = div[(div["CashExDividendTradingDate"].astype(str) == ev["ex_date"]) | (div["StockExDividendTradingDate"].astype(str) == ev["ex_date"])].iloc[0]
    pc = float(raw[raw["date"] < ev["ex_date"]]["close"].iloc[-1])
    n = lambda x: 0.0 if pd.isna(x) else float(x or 0)  # noqa: E731
    want = (pc - n(r["CashEarningsDistribution"]) - n(r["CashStatutorySurplus"]) + n(r["CashIncreaseSubscriptionpRrice"]) * n(r["CashIncreaseSubscriptionRate"]) / 1000) \
        / (1 + (n(r["StockEarningsDistribution"]) + n(r["StockStatutorySurplus"])) / 10 + n(r["CashIncreaseSubscriptionRate"]) / 1000) / pc
    f = NEW._finmind_adjusted_frame(sid, START).set_index("date")
    i = f.index.get_loc(ev["ex_date"])
    ret = f["adj_close"].iloc[i] / f["adj_close"].iloc[i - 1] - 1
    check(f"2 {sid} {ev['ex_date']}（公積配息 {ev['cash_surplus']}、配股 {ev['stock_surplus']}）", abs(ev["factor_new"] - round(want, 6)) < 2e-6 and abs(ret) < 0.11,
          f"係數 {ev['factor_old']}→{ev['factor_new']}（公式 {want:.6f}），除息日還原報酬 {ret:+.2%}")

# 3. 回歸
spec = importlib.util.spec_from_file_location("adjust_old", sys.argv[1])
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)
# 舊版放在暫存資料夾，補充檔路徑要指回 research/data（否則舊版會少了官方除權息／減資補充，比較到的不是公式差異）
OLD.SUPPLEMENTAL_REDUCTIONS, OLD.SUPPLEMENTAL_EXRIGHTS = NEW.SUPPLEMENTAL_REDUCTIONS, NEW.SUPPLEMENTAL_EXRIGHTS
offline(OLD)
with_s = {s["stock_id"] for s in imp["stocks"]}
pool = sorted({p.name.split("__")[1] for p in (Path(NEW.__file__).parent / "data" / "raw").glob(f"TaiwanStockDividend__*__{START}__*.parquet")} - with_s)
random.seed(20261023)
bad, n_ok = [], 0
for sid in random.sample([s for s in pool if len(s) == 4 and _cache_path("TaiwanStockPrice", s, START, VAL_END).exists()], 30):
    try:
        a, b = OLD._finmind_adjusted_frame(sid, START), NEW._finmind_adjusted_frame(sid, START)
    except Exception:  # noqa: BLE001
        continue
    if a.empty or b.empty:
        continue
    n_ok += 1
    if not np.array_equal(a["adj_close"].to_numpy(), b["adj_close"].to_numpy(), equal_nan=True):
        bad.append(sid)
check(f"3 沒有公積配發的 {n_ok} 檔：修正前後全期逐值相同", not bad and n_ok >= 20, str(bad[:10]))
print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
