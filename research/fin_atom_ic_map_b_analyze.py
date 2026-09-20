# -*- coding: utf-8 -*-
"""原子.五B：通道B聚合＋族層級檢定（驗證帽，2026-09-20）。

**口徑完全重用原子.五（`fin_atom_ic_map_aggregate.py`／`fin_atom_ic_map_family.py`），
不改任何一格**；只是把讀檔名改成`_chB`後綴。判定規則＝`ATOM_FIN_CHANNEL_B_SPEC.md`第4節：
Tier A、K=5、族層級「所有K=5成員五窗全同號」對6.25%單尾二項、×2 Bonferroni、p<0.01；
另報高階篩選（TRAIN/VAL同號＋五窗同號＋逐年同號率≥0.7＋|VAL IC|>0.02）通過的族數與
分群後獨立族數。Tier B的K皆<5時只與2×0.5^K比、僅作輔助。
**不列任何表達式名稱為「表現好的」**（SPEC第0節）。

另外把8群（B1~B8）各自的族層級同號數分列（只列群層級，不列表達式），供解讀時看
是哪一類算子在貢獻，但**判定不分群、不拿單群結果當通過依據**（避免事後切片挑選）。

用法：python research/fin_atom_ic_map_b_analyze.py
輸出：fin_atom_ic_map_b_family.json（機器可讀）＋ 印出摘要
"""
from __future__ import annotations

import json
import re
import sys

import pandas as pd
from scipy.stats import binomtest

import fin_atom_ic_map_aggregate as g

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TAG = "_chB"


def group_of(expr: str) -> str:
    """B1~B8（SPEC第2節表）。"""
    if expr.startswith("spread("):
        return "B8_spread"
    op = expr.split("(", 1)[0]
    on_yoy = expr.startswith(f"{op}(yoy(")
    base = {"surprise_naive": "surprise_naive", "surprise_drift": "surprise_drift",
            "zscore8": "zscore8", "accel": "accel"}[op]
    return f"{'G' if on_yoy else 'R'}_{base}"


def main() -> int:
    out = []
    for tier in ("A", "B"):
        for h in g.HORIZONS:
            p = g.HERE / f"fin_atom_ic_snapshots_{tier}_h{h}{TAG}.parquet"
            if not p.exists():
                print(f"缺檔：{p.name}（該tier/horizon略過）")
                continue
            snap = pd.read_parquet(p)
            snap.index = pd.to_datetime(snap.index)
            tr = snap[snap.index <= g.TRAIN_END]
            va = snap[(snap.index > g.TRAIN_END) & (snap.index <= g.VAL_END)]
            cols = [c for c in snap.columns if tr[c].count() >= g.MIN_SNAP and va[c].count() >= g.MIN_SNAP]
            cl = g.clusters(snap, cols)
            kmax = 5 if tier == "A" else 4
            fam: dict[int, list[dict]] = {}
            for e in cols:
                cs = g.crisis_signs(snap[e])
                k = len(cs)
                s = snap[e].dropna()
                yrs = s.groupby(s.index.year).mean().pipe(lambda x: x[x != 0])
                ys = yrs > 0
                yr_rate = float(max(ys.mean(), 1 - ys.mean())) if len(yrs) else 0.0
                tm, vm = tr[e].mean(), va[e].mean()
                same = bool(k == kmax and len(set(cs.values())) == 1)
                scr = bool(same and tm * vm > 0 and yr_rate >= 0.7 and abs(vm) > 0.02)
                fam.setdefault(cl[e], []).append({"k": k, "same": same, "scr": scr, "ny": int(len(yrs)),
                                                  "grp": group_of(e)})
            kfam = {f: m for f, m in fam.items() if any(x["k"] == kmax for x in m)}
            n = len(kfam)
            succ = sum(all(x["same"] for x in m if x["k"] == kmax) for m in kfam.values())
            naive = 2 * 0.5 ** kmax
            pv = float(binomtest(succ, n, naive, alternative="greater").pvalue) if n else None
            scr_fam = sum(any(x["scr"] for x in m) for m in kfam.values())
            exp_fam = sum(0.5 * naive * g.p_year_rate_ge(max(x["ny"] for x in m)) for m in kfam.values())
            # 群層級（僅描述）：各群含幾個K滿窗成員、其中幾個五窗同號（不列表達式名稱）
            by_grp: dict[str, list[int]] = {}
            for m in fam.values():
                for x in m:
                    if x["k"] == kmax:
                        r = by_grp.setdefault(x["grp"], [0, 0])
                        r[0] += 1
                        r[1] += int(x["same"])
            k_dist: dict[int, int] = {}
            for m in fam.values():
                for x in m:
                    k_dist[x["k"]] = k_dist.get(x["k"], 0) + 1
            out.append({"tier": tier, "horizon": h, "n_valid_expr": len(cols),
                        "K_dist_expr": {str(k): v for k, v in sorted(k_dist.items())},
                        "n_insufficient": int(snap.shape[1] - len(cols)),
                        "n_families_all": len(set(cl.values())), "n_families_K_full": n,
                        "families_all_same": succ, "share": succ / n if n else None, "naive": naive,
                        "binom_p": pv, "binom_p_bonferroni_x2": None if pv is None else min(1.0, 2 * pv),
                        "screen_pass_families": scr_fam, "screen_expected_upper_family": exp_fam,
                        "K_full_members_by_group": {k: {"members": v[0], "all_same": v[1]} for k, v in sorted(by_grp.items())}})
    (g.HERE / "fin_atom_ic_map_b_family.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
