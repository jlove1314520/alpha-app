# -*- coding: utf-8 -*-
"""原子.五：產生FIN_ATOM_IC_MAP.md（驗證帽，2026-09-20）。只讀已存的聚合JSON與逐snapshot IC；不列任何表達式名。"""
import json, sys
import pandas as pd
import fin_atom_ic_map_aggregate as g
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
agg = {(r["tier"], r["horizon"]): r for r in json.loads((g.HERE/"fin_atom_ic_map_aggregate.json").read_text(encoding="utf-8"))}
fam = {(r["tier"], r["horizon"]): r for r in json.loads((g.HERE/"fin_atom_ic_map_family.json").read_text(encoding="utf-8"))}
L = ["# FIN_ATOM_IC_MAP.md — 原子.五 財報depth-1素材IC地圖（結果與判定）", "",
"**產生**：`fin_atom_ic_map_report.py`（2026-09-20，驗證帽輪次）。規格：`ATOM_FIN_IC_MAP_SPEC.md`（事前登記）。",
"計算：`fin_atom_ic_map.py`；聚合：`fin_atom_ic_map_aggregate.py`；族層級：`fin_atom_ic_map_family.py`。",
"**只列零件層級分布；不列任何表達式名稱為「表現好的」**（SPEC第0節禁令）。holdout全程未動。", "",
"## 1. 判定：**FAIL（分支b）**", "",
"SPEC第7節條件1（Tier A、K=5、族層級、Bonferroni×2後單尾二項p<0.01）**不成立**：",
f"20日調整後p={fam[('A',20)]['binom_p_bonferroni_x2']:.3f}、60日調整後p={fam[('A',60)]['binom_p_bonferroni_x2']:.4f}（60日未調整p={fam[('A',60)]['binom_p']:.4f}，亦>0.01）。",
"依SPEC「不設勉強過中間態」，判FAIL。**不泛化成「財報資訊沒用」**：只是depth-1單一時間序列/單季比值、季頻~48snapshot、IC地圖層級未達事前門檻。", "",
"## 2. 族層級檢定（決定性數字，含樸素基準）", "",
"| Tier | horizon | 有效表達式 | 獨立族(全) | 含K滿窗族 | 該族全成員五窗同號 | 占比 | 樸素基準 | 二項p(單尾) | ×2 Bonferroni |","|---|---|---|---|---|---|---|---|---|---|"]
for t in ("A","B"):
    for h in (20,60):
        r=fam[(t,h)]
        L.append(f"| {t} | {h} | {r['n_valid_expr']} | {r['n_families_all']} | {r['n_families_K_full']} | {r['families_all_same']} | {r['share']:.1%} | {r['naive']:.2%} | {r['binom_p']:.4f} | {r['binom_p_bonferroni_x2']:.4f} |")
L += ["", "Tier B所有表達式K=4（2011窗起點前資料不足），只與12.5%比、僅作輔助，不可單獨進depth-2/3。",
"**共同因子警語**：五個危機窗內的IC符號共享同一段市場行情（例如品質/規模在同一場危機同步反轉），「每窗獨立公平硬幣」的樸素基準因此**低估**同號機率，60日未調整p=0.0108若已略偏樂觀，這也是判FAIL而非邊緣過關的理由之一。", "",
"## 3. 表達式層級分布（僅供對照，判定以族層級為準）", "",
"| Tier | h | 表達式 | TRAIN IC中位 | VAL IC中位 | VAL為正占比 | TRAIN/VAL同號占比 | K=5五窗同號(占K=5) | 樸素6.25%二項p | 高階篩選通過(期望上界) | 通過者所屬族數 | 有效獨立族數 |","|---|---|---|---|---|---|---|---|---|---|---|---|"]
for t in ("A","B"):
    for h in (20,60):
        a=agg[(t,h)]
        k5 = f"{a['K5_all_same']}/{a['n_K5']}" if a['n_K5'] else "n/a(K=4)"
        pb = f"{a['binom_p_greater']:.4f}" if a['binom_p_greater'] is not None else "n/a"
        L.append(f"| {t} | {h} | {a['n_valid']} | {a['train_ic_quartiles']['p50']:+.4f} | {a['val_ic_quartiles']['p50']:+.4f} | {a['val_positive_share']:.1%} | {a['tv_same_sign_share']:.1%} | {k5} | {pb} | {a['screen_pass']} ({a['screen_naive_expected_upper']:.3f}) | {a['screen_pass_clusters']} | {a['effective_independent_clusters_all_valid']} |")
L += ["", "表達式層級的二項p假設57個表達式獨立，實際只有14~17個獨立族，**p值高估顯著性**，故不當判定依據。",
"高階篩選通過數看似遠超樸素期望上界，但該期望是上界的「獨立且每年公平硬幣」模型，未計共同市場行情；且SPEC條件1先不成立，條件2不再單獨構成過關理由。", ""]
# 逐年、危機窗（Tier A，正IC占比）
L += ["## 4. 分年份／牛熊段拆解（Tier A，各表達式平均IC為正的占比；n=該窗snapshot數）", ""]
for h in (20,60):
    snap=pd.read_parquet(g.HERE/f"fin_atom_ic_snapshots_A_h{h}.parquet"); snap.index=pd.to_datetime(snap.index)
    snap=snap[snap.index<=g.VAL_END]
    L += [f"### horizon={h}日", "", "| 危機窗 | snapshot數 | IC為正表達式占比 |","|---|---|---|"]
    for n,a,b in g.CRISIS_WINDOWS:
        w=snap[(snap.index>=pd.Timestamp(a))&(snap.index<=pd.Timestamp(b))]
        m=w.mean().dropna()
        L.append(f"| {n} | {len(w)} | {(m>0).mean():.1%} (n={len(m)}) |" if len(w) else f"| {n} | 0 | n/a |")
    L += ["", "| 年 | snapshot數 | IC為正表達式占比 |","|---|---|---|"]
    for y,gp in snap.groupby(snap.index.year):
        m=gp.mean().dropna(); L.append(f"| {y} | {len(gp)} | {(m>0).mean():.1%} |")
    L.append("")
L += ["每年僅約4個snapshot，解析度粗，只能看整體傾向，不能對單一年份下結論。", "",
"## 5. 限制（誠實揭露）", "",
"- Tier A宇宙＝抽樣300∩損益表有列＝206檔；Tier B＝三表齊全407檔。資產負債表/現金流原子覆蓋受本機快取限制（`FIN_ATOM_COVERAGE.md`），下市代理覆蓋更低→存活者偏誤方向：偏高估。`財報原子.補快取`因FinMind 402中斷，實測回補並未增加三表齊全檔數。",
"- 季頻每公布週期1個snapshot，有效樣本結構性偏小；獨立族僅14~21個，遠小於名目145表達式。",
"- 判定僅限depth-1；depth-2/3（原子.三）未開。", "",
"## 6. 後續","","依SPEC分支(b)：接**原子.六（籌碼原子家族）**，屆時先寫規格再跑。",""]
(g.HERE/"FIN_ATOM_IC_MAP.md").write_text("\n".join(L),encoding="utf-8"); print("ok",len(L))
