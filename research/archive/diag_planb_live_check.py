"""評.B-2 一：線上方案B自我測試＋新舊榜對照（唯讀）。舊榜快照路徑由 argv[1] 給。"""
import json, sys, collections
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import generate_scores_live as g
from factors import LOW_VOL_WINDOW
root = Path(__file__).parent.parent
ph = json.load(open(root/"data/price_history.json", encoding="utf-8"))["prices"]
new = json.load(open(root/"scores.json", encoding="utf-8"))
# 1) 公式一致性：與 factors.py f_low_vol 參考式逐股比對
bad = n = 0
for c, rows in ph.items():
    v, comp = g.low_vol_from_price_rows(rows)
    if v is None: continue
    n += 1
    df = pd.DataFrame(sorted(rows, key=lambda r: r["date"]))
    ref = (-(df["adj_close"].pct_change().rolling(LOW_VOL_WINDOW, min_periods=LOW_VOL_WINDOW).std())).iloc[-1]
    if not np.isclose(v, ref, rtol=0, atol=1e-15): bad += 1
print(f"[公式] 與參考式比對 {n} 檔，不一致 {bad}")
# 2) 歷史不足/空窗不進榜
scored = {s["code"] if "code" in s else s.get("stock_id") for s in new["stocks"]}
leak = [c for c in scored if g.low_vol_from_price_rows(ph.get(c, []))[0] is None]
print(f"[不進榜] 榜上但 low_vol 為 None 的檔數 {len(leak)}")
print("[meta]", {k: new["meta"].get(k) for k in ("score_scheme","backtest_status","score_scheme_effective_from","weights_hash","eligibility")})
print("[weights]", new["weights"])
# 3) 新舊對照
def top(j, n=20):
    st = sorted([s for s in j["stocks"] if s.get("rank") is not None], key=lambda s: s["rank"])[:n]
    return st
def ind(st): return collections.Counter((s.get("industry") or "未分類") for s in st)
if len(sys.argv) > 1:
    old = json.load(open(sys.argv[1], encoding="utf-8"))
    o, nw = top(old), top(new)
    key = lambda s: s.get("code") or s.get("stock_id")
    print(f"舊榜 {len(old['stocks'])} 檔（有名次 {sum(1 for s in old['stocks'] if s.get('rank') is not None)}） / 新榜 {len(new['stocks'])} 檔（有名次 {sum(1 for s in new['stocks'] if s.get('rank') is not None)}）；前20重疊 {len({key(s) for s in o} & {key(s) for s in nw})} 檔")
    for lab, st in (("舊前20", o), ("新前20", nw)):
        print(lab); [print(f"  {s['rank']:>2} {key(s)} {s.get('name')} {s.get('industry')} {s['total_score']}") for s in st]
        print("  產業:", dict(ind(st).most_common()))
