"""#82 G0 檢定力前置關卡：0050成分股調整事件的最小可偵測效果(MDE)。
事前綁定見 HYPOTHESIS_QUEUE.md #82 SPEC（2026-10-12）。只讀 <=TRAIN_END 價格，不看任何納入/剔除股報酬。"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from scipy import stats
from adjust import adjusted_price_series
from factor_ic import START_DATE, SAMPLE_SIZE, SAMPLE_SEED, sample_universe_ids
from validation import holdout

EVENTS = {"2015-09": 1, "2016-06": 1, "2017-06": 1, "2019-03": 1, "2019-06": 1, "2019-09": 1, "2020-06": 1, "2020-09": 2}
N_INCL = sum(EVENTS.values())
EFFECT = 0.03; ALPHA = 0.05; POWER = 0.80; K_CTRL = 3

def eff_date(ym):  # 第三個週五後的下一個交易日（生效日代理，只用於估算截面波動窗口位置）
    y, m = map(int, ym.split("-")); d = pd.Timestamp(y, m, 1)
    fr = pd.date_range(d, d + pd.offsets.MonthEnd(0), freq="W-FRI")[2]
    return fr + pd.Timedelta(days=3)

ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
cols = {}
for sid in ids:
    try:
        px = adjusted_price_series(sid, START_DATE)
        s = px.set_index("date")["adj_close"].dropna(); s = s[s > 0]; s.index = pd.to_datetime(s.index)
        s = s[s.index <= pd.Timestamp(holdout.TRAIN_END)]
        if len(s) >= 500: cols[sid] = s
    except Exception:
        pass
P = pd.DataFrame(cols).sort_index()
sig = []
for ym in EVENTS:
    e = eff_date(ym); idx = P.index
    i = idx.searchsorted(e)
    if i < 1 or i + 5 >= len(idx): continue
    r = P.iloc[i + 5] / P.iloc[i - 1] - 1          # E-1收盤 -> E+5收盤
    r = r.dropna(); r = r[(r > -0.5) & (r < 1.0)]
    sig.append(float(r.std(ddof=1)))
s_cs = float(np.mean(sig))
s_car = s_cs * np.sqrt(1 + 1 / K_CTRL)   # 納入股 - 3檔等權控制組平均（特異風險獨立假設）
z = stats.norm.ppf(1 - ALPHA) + stats.norm.ppf(POWER)
mde = z * s_car / np.sqrt(N_INCL)
out = dict(n_universe=P.shape[1], n_events_used=len(sig), sigma_cs_per_event=sig, sigma_cs_mean=s_cs,
           sigma_car=s_car, n_inclusions=N_INCL, z=z, mde=mde, target_effect=EFFECT,
           verdict=("INVALID_NO_DATA" if not np.isfinite(mde) else ("G0_FAIL_UNDERPOWERED" if mde > EFFECT else "G0_PASS")),
           holdout_consumed=bool(holdout.is_holdout_consumed()))
Path(__file__).with_name("r82_g0_mde_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
