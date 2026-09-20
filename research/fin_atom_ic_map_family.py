# -*- coding: utf-8 -*-
"""原子.五：族層級重算（驗證帽，2026-09-20）。

規則凍結於`PENDING_QUEUE.md`原子.五進度2026-09-20 17:4x（看過表層數字後由研究帽寫下、
取保守者[自行裁量]），本檔照抄不改：
- 每個含K=5成員的獨立族算1次試驗；成功＝該族**所有**K=5成員皆五窗全同號。
- 對6.25%做單尾二項檢定（族含多成員時真實零假設機率<=6.25%，故對6.25%檢定偏保守）。
- 20/60日兩個horizon做Bonferroni(x2)；SPEC第7節條件1門檻p<0.01（調整後）。
- Tier B的K皆為4，只與2x0.5^4=12.5%比、僅作輔助。
另報族層級高階篩選：有>=1個成員通過四條件的族數 vs 族層級樸素期望上界。
不列任何表達式名稱。
"""
from __future__ import annotations
import json, sys
import pandas as pd
from scipy.stats import binomtest
import fin_atom_ic_map_aggregate as g
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

out = []
for tier in ("A", "B"):
    for h in g.HORIZONS:
        snap = pd.read_parquet(g.HERE / f"fin_atom_ic_snapshots_{tier}_h{h}.parquet")
        snap.index = pd.to_datetime(snap.index)
        tr = snap[snap.index <= g.TRAIN_END]; va = snap[(snap.index > g.TRAIN_END) & (snap.index <= g.VAL_END)]
        cols = [c for c in snap.columns if tr[c].count() >= g.MIN_SNAP and va[c].count() >= g.MIN_SNAP]
        cl = g.clusters(snap, cols)
        Kmax = 5 if tier == "A" else 4
        fam = {}
        for e in cols:
            cs = g.crisis_signs(snap[e]); k = len(cs)
            s = snap[e].dropna(); yrs = s.groupby(s.index.year).mean().pipe(lambda x: x[x != 0])
            yr_sign = (yrs > 0)
            yr_rate = float(max(yr_sign.mean(), 1 - yr_sign.mean())) if len(yrs) else 0.0
            tm, vm = tr[e].mean(), va[e].mean()
            scr = (k == Kmax and len(set(cs.values())) == 1 and tm * vm > 0 and yr_rate >= 0.7 and abs(vm) > 0.02)
            fam.setdefault(cl[e], []).append({"k": k, "same": (k == Kmax and len(set(cs.values())) == 1),
                                              "scr": bool(scr), "ny": int(len(yrs))})
        kfam = {f: m for f, m in fam.items() if any(x["k"] == Kmax for x in m)}
        n = len(kfam)
        succ = sum(all(x["same"] for x in m if x["k"] == Kmax) for m in kfam.values())
        naive = 2 * 0.5 ** Kmax
        p = float(binomtest(succ, n, naive, alternative="greater").pvalue) if n else None
        scr_fam = sum(any(x["scr"] for x in m) for m in kfam.values())
        exp_fam = sum(0.5 * naive * g.p_year_rate_ge(max(x["ny"] for x in m)) for m in kfam.values())
        out.append({"tier": tier, "horizon": h, "n_valid_expr": len(cols), "n_families_all": len(set(cl.values())),
                    "n_families_K_full": n, "families_all_same": succ, "share": succ / n if n else None,
                    "naive": naive, "binom_p": p, "binom_p_bonferroni_x2": None if p is None else min(1.0, 2 * p),
                    "screen_pass_families": scr_fam, "screen_expected_upper_family": exp_fam})
(g.HERE / "fin_atom_ic_map_family.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
