# -*- coding: utf-8 -*-
"""原子.五：財報depth-1素材IC地圖——聚合層（研究帽，2026-09-20）。

讀`fin_atom_ic_map.py`存下的逐snapshot IC（`fin_atom_ic_snapshots_{A|B}_h{20|60}.parquet`），
依`ATOM_FIN_IC_MAP_SPEC.md`第5~7節事前綁定的口徑聚合，輸出`FIN_ATOM_IC_MAP.md`
與`fin_atom_ic_map_aggregate.json`。**本檔不改任何判定口徑**；口徑裡SPEC沒寫死、
本檔自行裁量的地方都標`[自行裁量]`。

**禁令（SPEC第0節）**：只出零件層級分布；**不列任何單一表達式名稱為「表現好的」**；
高階篩選只報「通過數」與「通過者分成幾個獨立族」，不列名單。

口徑摘要：
- 樣本不足：TRAIN或VAL的有效snapshot數<8 → 不進任何同號比例分母（`[自行裁量]`：
  SPEC寫「n_snap低於8者」，未明說TRAIN/VAL哪一段，取兩段都要≥8才算足夠）。
- 危機窗：沿用`atom_ic_map.py::CRISIS_WINDOWS`同一份5窗（複製常數，不import該檔以免
  拉進價量宇宙的重型相依）；窗內符號＝窗內snapshot IC平均的正負；K＝有值窗數。
- 「五窗全同號」樸素基準＝2×0.5^K（K=5為6.25%），**不同K不混進同一分母**。
- 條件1的分母＝K=5且n_snap達標者；二項檢定：單尾、H0比例=6.25%。
- 高階篩選（原子.二四條件，限K=5者`[自行裁量]`——避免不同K混分母）：
  TRAIN/VAL同號＋五窗同號＋逐年同號率≥0.7＋|VAL IC|>0.02。
- 樸素期望通過數（上界）＝Σ 0.5×P(五窗同號=0.0625)×P(逐年同號率≥0.7|該式年數，公平硬幣)；
  **略去|VAL IC|>0.02這一項（≤1，所以期望值是上界，對「通過數超過期望」這個判準偏嚴）**。
- 共線分群：以逐snapshot IC向量兩兩相關（重疊≥8個snapshot）|r|>0.7連通成分＝一族。

用法：python research/fin_atom_ic_map_aggregate.py
"""
from __future__ import annotations

import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
HORIZONS = (20, 60)
TRAIN_END = pd.Timestamp("2020-12-31")
VAL_END = pd.Timestamp("2024-12-31")
MIN_SNAP = 8
NAIVE_5 = 2 * 0.5 ** 5
CRISIS_WINDOWS = [  # 來源：atom_ic_map.py::CRISIS_WINDOWS／REGIME_OVERLAY_PROTOCOL.md第2節
    ("2011歐債危機", "2011-07-01", "2011-12-31"),
    ("2015中國股災", "2015-06-01", "2015-09-30"),
    ("2018Q4貿易戰", "2018-10-01", "2018-12-31"),
    ("2020Q1新冠崩盤", "2020-02-01", "2020-04-30"),
    ("2022全年空頭", "2022-01-01", "2022-12-31"),
]


def p_year_rate_ge(y: int, thr: float = 0.7) -> float:
    """y個獨立公平硬幣年份符號，「多數方向占比≥thr」的機率。"""
    if y <= 0:
        return 0.0
    return float(sum(math.comb(y, k) for k in range(y + 1) if max(k, y - k) / y >= thr) / 2 ** y)


def crisis_signs(s: pd.Series) -> dict[str, int]:
    out = {}
    for name, a, b in CRISIS_WINDOWS:
        v = s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))].dropna()
        if len(v):
            m = float(v.mean())
            if m != 0:
                out[name] = 1 if m > 0 else -1
    return out


def clusters(snap: pd.DataFrame, cols: list[str], thr: float = 0.7) -> dict[str, int]:
    """|r|>thr（重疊≥MIN_SNAP）連通成分；回傳{表達式: 族編號}。"""
    parent = {c: c for c in cols}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    sub = snap[cols]
    for a, b in combinations(cols, 2):
        both = sub[[a, b]].dropna()
        if len(both) >= MIN_SNAP and both[a].std() > 0 and both[b].std() > 0:
            if abs(both[a].corr(both[b])) > thr:
                parent[find(a)] = find(b)
    roots = {c: find(c) for c in cols}
    ids = {r: i for i, r in enumerate(sorted(set(roots.values())))}
    return {c: ids[r] for c, r in roots.items()}


def aggregate_tier_h(tier: str, h: int) -> dict | None:
    p = HERE / f"fin_atom_ic_snapshots_{tier}_h{h}.parquet"
    if not p.exists():
        return None
    snap = pd.read_parquet(p)
    snap.index = pd.to_datetime(snap.index)
    tr = snap[snap.index <= TRAIN_END]
    va = snap[(snap.index > TRAIN_END) & (snap.index <= VAL_END)]
    rows = []
    for e in snap.columns:
        ntr, nva = int(tr[e].count()), int(va[e].count())
        tm, vm = tr[e].mean(), va[e].mean()
        ok = ntr >= MIN_SNAP and nva >= MIN_SNAP
        s = snap[e].dropna()
        yrs = np.sign(s.groupby(s.index.year).mean())
        yrs = yrs[yrs != 0]
        yr_rate = float((yrs == yrs.mode().iloc[0]).mean()) if len(yrs) else np.nan
        cs = crisis_signs(snap[e])
        k = len(cs)
        rows.append({
            "expr": e, "ok": ok, "n_train": ntr, "n_val": nva,
            "train_ic": None if pd.isna(tm) else float(tm), "val_ic": None if pd.isna(vm) else float(vm),
            "tv_same": bool(ok and tm != 0 and vm != 0 and np.sign(tm) == np.sign(vm)),
            "K": k, "crisis_same": bool(k >= 1 and len(set(cs.values())) == 1),
            "n_years": int(len(yrs)), "year_rate": None if pd.isna(yr_rate) else yr_rate,
        })
    d = pd.DataFrame(rows)
    valid = d[d["ok"]]
    k5 = valid[valid["K"] == 5]
    n5, x5 = len(k5), int(k5["crisis_same"].sum())
    p_bin = float(binomtest(x5, n5, NAIVE_5, alternative="greater").pvalue) if n5 else None
    # K分布與各K的樸素基準（不同K不混分母）
    by_k = {}
    for kk, g in valid.groupby("K"):
        by_k[int(kk)] = {"n": int(len(g)), "all_same": int(g["crisis_same"].sum()),
                         "naive_rate": 2 * 0.5 ** int(kk) if kk >= 1 else None}
    # 高階篩選（K=5者）
    scr = k5[k5["tv_same"] & k5["crisis_same"] & (k5["year_rate"].fillna(0) >= 0.7)
             & (k5["val_ic"].abs() > 0.02)]
    exp_pass = float(sum(0.5 * NAIVE_5 * p_year_rate_ge(int(y)) for y in k5["n_years"]))
    cl = clusters(snap, list(valid["expr"])) if len(valid) else {}
    n_indep = len(set(cl.values()))
    pass_clusters = len({cl[e] for e in scr["expr"]}) if len(scr) else 0
    q = lambda c: {f"p{int(x*100)}": (None if valid[c].dropna().empty else float(valid[c].dropna().quantile(x)))
                   for x in (0.25, 0.5, 0.75)}
    tv_n = int(len(valid))
    return {
        "tier": tier, "horizon": h, "n_expr": int(len(d)), "n_valid": tv_n,
        "n_insufficient": int((~d["ok"]).sum()),
        "train_ic_quartiles": q("train_ic"), "val_ic_quartiles": q("val_ic"),
        "val_positive_share": float((valid["val_ic"] > 0).mean()) if tv_n else None,
        "tv_same_sign": int(valid["tv_same"].sum()), "tv_same_sign_share": float(valid["tv_same"].mean()) if tv_n else None,
        "K_dist": by_k, "n_K5": n5, "K5_all_same": x5,
        "K5_all_same_share": (x5 / n5) if n5 else None, "naive_K5": NAIVE_5, "binom_p_greater": p_bin,
        "screen_pass": int(len(scr)), "screen_naive_expected_upper": exp_pass, "screen_pass_clusters": pass_clusters,
        "effective_independent_clusters_all_valid": n_indep,
    }


def main() -> int:
    res = [r for t in ("A", "B") for h in HORIZONS if (r := aggregate_tier_h(t, h))]
    (HERE / "fin_atom_ic_map_aggregate.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
