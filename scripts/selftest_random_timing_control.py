# -*- coding: utf-8 -*-
"""先.一二七-C 自測：research/validation/random_timing_control.py（合成資料，不讀真實資料、不發請求）。"""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd  # noqa: E402
from validation.random_timing_control import run_random_timing_control  # noqa: E402
from validation.costs import round_trip_cost_pct  # noqa: E402

res = []
def check(n, ok):
    res.append(ok); print(("PASS " if ok else "FAIL ") + n)

dates = pd.bdate_range("2007-01-01", "2007-06-29")
# 鋸齒價：每月內先跌後漲，月中最低
px = [100 + 10 * math.cos(2 * math.pi * (d.day / 31)) for d in dates]
df = pd.DataFrame({"date": dates, "adj_open": px})
rates = {"buy": 0.001425, "sell": 0.001425 + 0.003}
# 完美時點：每月最低那天進、5 個交易日後出
trades = []
for m in range(1, 7):
    sub = df[df.date.dt.month == m]
    i = sub.adj_open.idxmin()
    trades.append({"stock_id": "A", "entry_date": df.date[i], "exit_date": df.date[i + 5]})
def equity(trs):
    tot = 0.0
    for t in trs:
        e = float(df.set_index("date").adj_open[t["entry_date"]]); x = float(df.set_index("date").adj_open[t["exit_date"]])
        sh = int(10000 // (e * (1 + rates["buy"])))
        tot += sh * x * (1 - rates["sell"]) - sh * e * (1 + rates["buy"])
    return 1e5 + tot
r = run_random_timing_control(trades, {"A": df}, equity(trades), 1e5, 10000, rates, n_random=300)
check(f"完美時點 → 百分位高（{r.percentile:.1f}）", r.percentile >= 95)
r2 = run_random_timing_control(trades, {"A": df}, equity(trades), 1e5, 10000, rates, n_random=300)
check("同 seed 可重現", r.random_metrics == r2.random_metrics)
# 最差時點：每月最高那天進
worst = []
for m in range(1, 7):
    sub = df[(df.date.dt.month == m)].iloc[:-6]
    i = sub.adj_open.idxmax()
    worst.append({"stock_id": "A", "entry_date": df.date[i], "exit_date": df.date[i + 5]})
r3 = run_random_timing_control(worst, {"A": df}, equity(worst), 1e5, 10000, rates, n_random=300)
check(f"最差時點 → 百分位低（{r3.percentile:.1f}）", r3.percentile <= 5)
# 同月沒有可抽的進場日（只有一個月的資料、持有天數長到出界）→ 保留原日期並計數
short = df[df.date.dt.month <= 2].reset_index(drop=True)
t_long = [{"stock_id": "A", "entry_date": short.date[0], "exit_date": short.date[len(short) - 1]}]
r4 = run_random_timing_control(t_long, {"A": short}, 1e5, 1e5, 10000, rates, n_random=20)
check("持有天數保持：唯一可抽的就是原進場日 → 每次抽樣都相同", len(set(r4.random_metrics)) == 1
      and all(k == 0 for k in r4.kept_original_per_draw))
short2 = short.copy(); short2.loc[0, "adj_open"] = float("nan")
r4b = run_random_timing_control(t_long, {"A": short2}, 1e5, 1e5, 10000, rates, n_random=20)
check("同月無有效進場日 → 保留原日期並計數", all(k == 1 for k in r4b.kept_original_per_draw))
# NaN 價格不污染
dfn = df.copy(); dfn.loc[10:20, "adj_open"] = float("nan")
r5 = run_random_timing_control(trades, {"A": dfn}, 1e5, 1e5, 10000, rates, n_random=50)
check("NaN 價格不讓結果變 NaN", all(not math.isnan(m) for m in r5.random_metrics))
# 持有天數保持：任一抽樣的交易數等於原交易數（間接：kept+抽樣都有算）
check("ControlGroupResult 欄位齊全", r.n_random == 300 and set(r.beats_random_at) == {50, 90, 95, 99})
sys.exit(0 if all(res) else 1)
