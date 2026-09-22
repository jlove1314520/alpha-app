# -*- coding: utf-8 -*-
"""原子.六：籌碼depth-1原子IC地圖——聚合層（研究帽，2026-09-20）。

讀`chip_atom_ic_map.py`存下的逐snapshot IC（`chip_atom_ic_snapshots_A_h{20|60}.parquet`），
依`ATOM_CHIP_IC_MAP_SPEC.md`第5~7節事前綁定口徑聚合，輸出`chip_atom_ic_map_aggregate.json`
與`CHIP_ATOM_IC_MAP.md`。**本檔只聚合、不下判定**（做與判分離：第7節判定與試驗登記由驗證帽輪次做）。

**禁令（規格第7節末）**：只出零件層級分布；**不列任何單一表達式名稱為「表現好的」**；
高階篩選只報「通過數」與「通過者分成幾個獨立族」。

口徑（規格已寫死者照做；規格未寫死、本檔自行裁量者標`[自行裁量]`）：
- 樣本不足：TRAIN或VAL有效snapshot數<8 → 不進任何同號比例分母（沿用原子.五的兩段都要>=8）。
- 危機窗：沿用`atom_ic_map.py::CRISIS_WINDOWS`5窗；窗內符號＝窗內snapshot IC平均的正負；
  K＝窗內至少有1個有值snapshot的窗數；**K<3只描述、不做「全窗同號」判定；不同K不混進同一分母**。
- 樸素基準＝2×0.5^K（K=5→6.25%、K=4→12.5%）。
- 條件1（規格第7節）：K>=4且n_snap達標者，「全窗同號」比例對**各表達式自己的樸素基準**做單尾檢定。
  `[自行裁量]`規格寫「單尾二項檢定…按K混合，不混K」→採**Poisson-binomial精確單尾**（每個表達式
  用自己K對應的基準，等於把K=4與K=5各自的二項檢定合併成一個精確檢定，不把K混成單一基準），
  並另列每個K的二項p供對照。
- 高階篩選（原子.二四條件，限K>=4）：TRAIN/VAL同號＋全窗同號＋逐年同號率>=0.7＋|VAL IC|>0.02。
  樸素期望通過數（上界）＝Σ 0.5×基準_K×P(逐年同號率>=0.7|該式年數，公平硬幣)，略去|VAL IC|>0.02項
  （所以是上界，對「通過數超過期望」這個判準偏嚴）。
- 共線分群：逐snapshot IC向量兩兩相關（重疊>=8）|r|>0.7連通成分＝一族（規格第6節）。
- 分年份：每年「有效表達式中年平均IC為正的占比」與該年有效表達式數（報每年n，規格第5節）。

用法：python research/chip_atom_ic_map_aggregate.py
"""
from __future__ import annotations

import argparse
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
CRISIS_WINDOWS = [  # 來源：atom_ic_map.py::CRISIS_WINDOWS／REGIME_OVERLAY_PROTOCOL.md第2節
    ("2011歐債危機", "2011-07-01", "2011-12-31"),
    ("2015中國股災", "2015-06-01", "2015-09-30"),
    ("2018Q4貿易戰", "2018-10-01", "2018-12-31"),
    ("2020Q1新冠崩盤", "2020-02-01", "2020-04-30"),
    ("2022全年空頭", "2022-01-01", "2022-12-31"),
]
FAMILY_OF = {"foreign": "T86", "trust": "T86", "dealer": "T86", "total": "T86",
             "margin_bal": "融資融券", "short_bal": "融資融券", "margin_util": "融資融券", "short_margin": "融資融券",
             "sbl_sales": "借券賣出", "sbl_bal": "借券賣出", "sbl_short": "借券賣出"}  # Tier B（2026-09-22補）


def family(expr: str) -> str:
    parts = expr.split("__")
    key = parts[1] if len(parts) > 1 else ""
    return FAMILY_OF.get(key, "其他")


def naive(k: int) -> float:
    return 2 * 0.5 ** k


def p_year_rate_ge(y: int, thr: float = 0.7) -> float:
    if y <= 0:
        return 0.0
    return float(sum(math.comb(y, k) for k in range(y + 1) if max(k, y - k) / y >= thr) / 2 ** y)


def poisson_binomial_sf(x: int, ps: list[float]) -> float:
    """P(X>=x)，X＝獨立Bernoulli(p_i)之和（精確動態規劃）。"""
    dist = np.zeros(len(ps) + 1)
    dist[0] = 1.0
    for p in ps:
        new = dist * (1 - p)
        new[1:] += dist[:-1] * p
        dist = new
    return float(dist[x:].sum())


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


def aggregate_h(h: int, tag: str = "", tier: str = "A") -> dict | None:
    p = HERE / f"chip_atom_ic_snapshots_{tier}_h{h}{tag}.parquet"
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
        rows.append({
            "expr": e, "family": family(e), "ok": ok, "n_train": ntr, "n_val": nva,
            "train_ic": None if pd.isna(tm) else float(tm), "val_ic": None if pd.isna(vm) else float(vm),
            "tv_same": bool(ok and tm != 0 and vm != 0 and np.sign(tm) == np.sign(vm)),
            "K": len(cs), "crisis_same": bool(len(cs) >= 1 and len(set(cs.values())) == 1),
            "n_years": int(len(yrs)), "year_rate": None if pd.isna(yr_rate) else yr_rate,
        })
    d = pd.DataFrame(rows)
    valid = d[d["ok"]]
    kge4 = valid[valid["K"] >= 4]
    by_k = {}
    for kk, g in valid.groupby("K"):
        kk = int(kk)
        x, n = int(g["crisis_same"].sum()), int(len(g))
        by_k[kk] = {"n": n, "all_same": x, "naive_rate": naive(kk) if kk >= 1 else None,
                    "binom_p_greater": float(binomtest(x, n, naive(kk), alternative="greater").pvalue) if kk >= 4 and n else None}
    ps = [naive(int(k)) for k in kge4["K"]]
    x_all = int(kge4["crisis_same"].sum())
    p_pb = poisson_binomial_sf(x_all, ps) if len(kge4) else None
    exp_same = float(sum(ps))
    scr = kge4[kge4["tv_same"] & kge4["crisis_same"] & (kge4["year_rate"].fillna(0) >= 0.7)
               & (kge4["val_ic"].abs() > 0.02)]
    exp_pass = float(sum(0.5 * naive(int(k)) * p_year_rate_ge(int(y)) for k, y in zip(kge4["K"], kge4["n_years"])))
    cl = clusters(snap, list(valid["expr"])) if len(valid) else {}
    pass_clusters = len({cl[e] for e in scr["expr"]}) if len(scr) else 0
    yr = {}
    for y, g in snap.loc[:, list(valid["expr"])].groupby(snap.index.year):
        m = g.mean().dropna()
        yr[int(y)] = {"n_expr": int(len(m)), "n_snap": int(len(g)),
                      "positive_share": float((m > 0).mean()) if len(m) else None}
    fam = {}
    for f, g in valid.groupby("family"):
        fam[f] = {"n_valid": int(len(g)), "tv_same": int(g["tv_same"].sum()),
                  "K_dist": {int(k): int(c) for k, c in g["K"].value_counts().sort_index().items()},
                  "screen_pass": int(scr["family"].eq(f).sum()) if len(scr) else 0}

    def q(c):
        v = valid[c].dropna()
        return {f"p{int(x * 100)}": (None if v.empty else float(v.quantile(x))) for x in (0.25, 0.5, 0.75)}
    return {
        "horizon": h, "n_expr": int(len(d)), "n_valid": int(len(valid)), "n_insufficient": int((~d["ok"]).sum()),
        "n_snapshots_with_ic": int(len(snap)), "n_train_snap": int(len(tr)), "n_val_snap": int(len(va)),
        "train_ic_quartiles": q("train_ic"), "val_ic_quartiles": q("val_ic"),
        "val_positive_share": float((valid["val_ic"] > 0).mean()) if len(valid) else None,
        "tv_same_sign": int(valid["tv_same"].sum()),
        "K_dist": by_k, "n_Kge4": int(len(kge4)), "Kge4_all_same": x_all, "Kge4_naive_expected": exp_same,
        "poisson_binom_p_greater": p_pb,
        "screen_pass": int(len(scr)), "screen_naive_expected_upper": exp_pass, "screen_pass_clusters": pass_clusters,
        "effective_independent_clusters_all_valid": len(set(cl.values())),
        "by_family": fam, "by_year": yr,
    }


def write_md(res: list[dict], meta: dict, tag: str = "") -> None:
    L = [f"# CHIP_ATOM_IC_MAP{tag}（原子.六 Tier A 聚合，機器產生，未下判定）", "",
         "> 產生腳本：`research/chip_atom_ic_map_aggregate.py`；規格：`ATOM_CHIP_IC_MAP_SPEC.md`（事前登記）。",
         "> **本檔只呈現零件層級分布，不列任何單一表達式為「表現好的」；判定（規格第7節）與試驗登記由驗證帽輪次做。**",
         "> Tier B（借券賣出餘額族）**未檢驗**（SBL未回補，規格第7節：記未檢驗、不記FAIL）。",
         f"> 入樣：宇宙U請求{meta.get('n_stocks_requested')}檔、可用{meta.get('n_stocks_used')}檔，其中有T86者{meta.get('n_with_t86')}檔"
         f"（T86僅上市）；橫斷面<30檔跳過的snapshot：{meta.get('skipped_snapshots')}。", ""]
    for r in res:
        h = r["horizon"]
        L += [f"## horizon={h}日", "",
              f"- 有IC的snapshot：{r['n_snapshots_with_ic']}（TRAIN {r['n_train_snap']}／VAL {r['n_val_snap']}）；表達式{r['n_expr']}，"
              f"有效（兩段n_snap>=8）{r['n_valid']}，樣本不足{r['n_insufficient']}",
              f"- TRAIN IC四分位 {r['train_ic_quartiles']}；VAL IC四分位 {r['val_ic_quartiles']}；VAL IC為正占比 {r['val_positive_share']}",
              f"- TRAIN/VAL同號：{r['tv_same_sign']}／{r['n_valid']}（公平硬幣期望約50%）",
              f"- K分布與各K樸素基準（不混K）：{json.dumps(r['K_dist'], ensure_ascii=False)}",
              f"- 條件1：K>=4有效{r['n_Kge4']}個，全窗同號{r['Kge4_all_same']}個，樸素期望{r['Kge4_naive_expected']:.2f}個，"
              f"Poisson-binomial單尾p={r['poisson_binom_p_greater']}（門檻p<0.01）",
              f"- 高階篩選通過{r['screen_pass']}個（樸素期望上界{r['screen_naive_expected_upper']:.2f}），通過者分成{r['screen_pass_clusters']}個獨立族",
              f"- 全體有效表達式共線分群後**有效獨立表達式數＝{r['effective_independent_clusters_all_valid']}**（同號比例解讀以此為準）",
              "", "| 族 | 有效數 | TRAIN/VAL同號 | K分布 | 篩選通過 |", "|---|---|---|---|---|"]
        for f, v in r["by_family"].items():
            L.append(f"| {f} | {v['n_valid']} | {v['tv_same']} | {json.dumps(v['K_dist'])} | {v['screen_pass']} |")
        L += ["", "| 年 | snapshot數 | 有效表達式數 | 年平均IC為正占比 |", "|---|---|---|---|"]
        for y, v in sorted(r["by_year"].items()):
            ps_ = v["positive_share"]
            L.append(f"| {y} | {v['n_snap']} | {v['n_expr']} | {ps_ if ps_ is None else round(ps_, 3)} |")
        L.append("")
    (HERE / f"CHIP_ATOM_IC_MAP{tag}.md").write_text("\n".join(L), encoding="utf-8")


def append_md_tierB(res: list[dict], meta: dict) -> None:
    """Tier B聚合結果append進既有CHIP_ATOM_IC_MAP.md（不覆蓋Tier A內容）。

    規格第7節：Tier B「未達門檻記未檢驗，達門檻後僅可作輔助，不獨立判定pass/fail」——
    本函式只列數字分布，PASS/FAIL判定與登記在驗證帽輪次的register_trial()呼叫端。
    """
    L = ["", "---", "", "## Tier B 補充（借券賣出餘額族，僅供輔助，不獨立判定pass/fail）", "",
         "> 規格第7/9節：覆蓋率達U的60%後執行；判定規則—Tier B**不單獨判pass/fail**，"
         "只能輔助Tier A（#317/#328）已判的FAIL結論是否穩健。",
         f"> 入樣：宇宙U請求{meta.get('n_stocks_requested')}檔、可用{meta.get('n_stocks_used')}檔，"
         f"其中有T86者{meta.get('n_with_t86')}檔（此欄位對Tier B無意義，沿用共用meta結構）；"
         f"橫斷面<30檔跳過的snapshot：{meta.get('skipped_snapshots')}。", ""]
    for r in res:
        h = r["horizon"]
        L += [f"### horizon={h}日（Tier B）", "",
              f"- 有IC的snapshot：{r['n_snapshots_with_ic']}（TRAIN {r['n_train_snap']}／VAL {r['n_val_snap']}）；表達式{r['n_expr']}，"
              f"有效（兩段n_snap>=8）{r['n_valid']}，樣本不足{r['n_insufficient']}",
              f"- TRAIN IC四分位 {r['train_ic_quartiles']}；VAL IC四分位 {r['val_ic_quartiles']}；VAL IC為正占比 {r['val_positive_share']}",
              f"- TRAIN/VAL同號：{r['tv_same_sign']}／{r['n_valid']}（公平硬幣期望約50%）",
              f"- K分布與各K樸素基準（不混K）：{json.dumps(r['K_dist'], ensure_ascii=False)}",
              f"- 條件1：K>=4有效{r['n_Kge4']}個，全窗同號{r['Kge4_all_same']}個，樸素期望{r['Kge4_naive_expected']:.2f}個，"
              f"Poisson-binomial單尾p={r['poisson_binom_p_greater']}（門檻p<0.01）",
              f"- 高階篩選通過{r['screen_pass']}個（樸素期望上界{r['screen_naive_expected_upper']:.2f}），通過者分成{r['screen_pass_clusters']}個獨立族",
              f"- 全體有效表達式共線分群後**有效獨立表達式數＝{r['effective_independent_clusters_all_valid']}**（同號比例解讀以此為準）",
              "", "| 族 | 有效數 | TRAIN/VAL同號 | K分布 | 篩選通過 |", "|---|---|---|---|---|"]
        for f, v in r["by_family"].items():
            L.append(f"| {f} | {v['n_valid']} | {v['tv_same']} | {json.dumps(v['K_dist'])} | {v['screen_pass']} |")
        L += ["", "| 年 | snapshot數 | 有效表達式數 | 年平均IC為正占比 |", "|---|---|---|---|"]
        for y, v in sorted(r["by_year"].items()):
            ps_ = v["positive_share"]
            L.append(f"| {y} | {v['n_snap']} | {v['n_expr']} | {ps_ if ps_ is None else round(ps_, 3)} |")
        L.append("")
    path = HERE / "CHIP_ATOM_IC_MAP.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if "## Tier B 補充" in existing:
        raise RuntimeError("CHIP_ATOM_IC_MAP.md已含Tier B補充章節，避免重複append——如需重跑請先手動移除舊章節")
    path.write_text(existing.rstrip("\n") + "\n" + "\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="", help="讀/寫檔名後綴，對應chip_atom_ic_map.py同名參數，避免蓋掉原始結果")
    ap.add_argument("--tier", choices=("A", "B"), default="A", help="Tier A聚合成獨立md；Tier B聚合結果append進既有CHIP_ATOM_IC_MAP.md補充章節（規格第7節：僅供輔助）")
    a = ap.parse_args()
    res = [r for h in HORIZONS if (r := aggregate_h(h, a.tag, a.tier))]
    meta = {}
    mp = HERE / f"chip_atom_ic_map_result_{a.tier}{a.tag}.json"
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
        meta = {k: m.get(k) for k in ("n_stocks_requested", "n_stocks_used", "n_with_t86", "skipped_snapshots")}
    out_json = HERE / f"chip_atom_ic_map_aggregate{'_B' if a.tier == 'B' else ''}{a.tag}.json"
    out_json.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.tier == "B":
        append_md_tierB(res, meta)
        print(f"已輸出 {out_json.name}＋append進CHIP_ATOM_IC_MAP.md（{len(res)}個horizon）")
    else:
        write_md(res, meta, a.tag)
        print(f"已輸出 {out_json.name}＋CHIP_ATOM_IC_MAP{a.tag}.md（{len(res)}個horizon）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
