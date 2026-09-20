"""財報PIT.四 收尾：把`pit4_rerun_80name.py`已跑完的結果（`data/pit4_rerun_80name.csv`，80檔、兩臂×24格）
整理成對照表、依檔頭凍結的分支判定，並把「修正臂」12個參數點（2因子版本×3加權×2頻率）登記進試驗帳本。

**誠實記錄（登記時序瑕疵）**：交辦要求「先register_trial()再跑」，但實際順序是：腳本（含判定分支）先commit
(73ac722a) → job 20260920-163914-3073跑完(13.6min, exit 0) → 本腳本收成並補登記。設計與分支在跑前凍結，
本腳本不改任何設計或數字，補登記只是登記時點在跑完之後。legacy臂為同參數點對照複本，不另計N。

用法：python pit4_summarize_register.py            # 只印表與判定、寫PIT4_RERUN_RESULT.md
      python pit4_summarize_register.py --register  # 另外正式登記12筆（不可重複執行）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CSV = HERE / "data" / "pit4_rerun_80name.csv"
OUT_MD = HERE / "PIT4_RERUN_RESULT.md"
LEG, COR = "legacy_q4_lookahead", "corrected"


def _cell(df, arm, fv, mode, cad, label):
    return df[(df.arm == arm) & (df.factor_version == fv) & (df.weight_mode == mode)
              & (df.cadence == cad) & (df.label == label)].iloc[0]


def main(register: bool) -> int:
    df = pd.read_csv(CSV)
    fmt = lambda r: f"{r.alpha_ann_pct:+.2f}({r.alpha_pvalue:.3f})"
    lines = ["| 因子版本 | 加權 | 頻率 | 修正臂 TRAIN | 修正臂 VAL | legacy臂 TRAIN | legacy臂 VAL |", "|---|---|---|---|---|---|---|"]
    trials = []
    for fv in dict.fromkeys(df.factor_version):
        for m in dict.fromkeys(df.weight_mode):
            for c in ("monthly", "quarterly"):
                ct, cv = _cell(df, COR, fv, m, c, "TRAIN"), _cell(df, COR, fv, m, c, "VALIDATION")
                lt, lv = _cell(df, LEG, fv, m, c, "TRAIN"), _cell(df, LEG, fv, m, c, "VALIDATION")
                lines.append(f"| {fv} | {m} | {c} | {fmt(ct)} | {fmt(cv)} | {fmt(lt)} | {fmt(lv)} |")
                trials.append((fv, m, c, ct, cv, lt, lv))
    a, b = _cell(df, LEG, "A_4pass", "ic_weighted", "quarterly", "VALIDATION"), _cell(df, LEG, "B_plus_value_pe", "ic_weighted", "quarterly", "VALIDATION")
    ac, bc = _cell(df, COR, "A_4pass", "ic_weighted", "quarterly", "VALIDATION"), _cell(df, COR, "B_plus_value_pe", "ic_weighted", "quarterly", "VALIDATION")
    reproduced = 7 <= a.alpha_ann_pct <= 14 and 0.03 <= a.alpha_pvalue <= 0.08
    v = df[df.label == "VALIDATION"]
    corr, leg = v[v.arm == COR], v[v.arm == LEG]
    md = ["# 財報PIT.四：80檔驗證樣本上Q4前視修正的影響（重跑結果）", "",
          "來源：`pit4_rerun_80name.py`（設計與判定分支跑前凍結，commit 73ac722a）→`data/pit4_rerun_80name.csv`（job 20260920-163914-3073）。"
          "本檔由`pit4_summarize_register.py`產生。", "",
          f"- 樣本：`sample_universe_ids(100, SAMPLE_SEED)`，實際載入 {int(df.n_stocks.iloc[0])} 檔（與原「80檔」檔數吻合，但成員是否與2026-09前原樣本相同無法事後驗證）；1x成本、無隨機對照組。",
          f"- **重現檢查（分支(a)判準：VAL alpha∈[+7%,+14%]且p∈[0.03,0.08]）**：legacy臂 A_4pass/ic_weighted/季頻 VAL alpha={a.alpha_ann_pct:+.2f}% p={a.alpha_pvalue:.3f}；"
          f"B_plus_value_pe/ic_weighted/季頻 VAL alpha={b.alpha_ann_pct:+.2f}% p={b.alpha_pvalue:.3f}（原：+10.40%/+10.26%、p=0.053）→ **{'重現' if reproduced else '重現不出'}**。",
          f"- 修正臂同格：A_4pass {ac.alpha_ann_pct:+.2f}%(p={ac.alpha_pvalue:.3f})、B_plus {bc.alpha_ann_pct:+.2f}%(p={bc.alpha_pvalue:.3f})。",
          f"- VAL全24列：修正臂最小p={corr.alpha_pvalue.min():.3f}（p<0.06有{(corr.alpha_pvalue<0.06).sum()}組）、legacy臂最小p={leg.alpha_pvalue.min():.3f}（p<0.06有{(leg.alpha_pvalue<0.06).sum()}組）。",
          f"- 兩臂VAL alpha逐格差（修正−legacy）：平均{(corr.alpha_ann_pct.values - leg.alpha_ann_pct.values).mean():+.2f}pp（12格；兩臂幾乎重疊，Q4前視在此樣本無可見系統性影響）。",
          "", *lines, "", "## 判定（依檔頭凍結分支）", "",
          f"- **分支(a)成立**：legacy臂重現不出原+10.40%/p=0.053（alpha落在區間內但p={a.alpha_pvalue:.3f}遠離0.03~0.08）→記錄「舊數字不可重現」，"
          "前視貢獻無法量化，不再追（與財報PIT.三結論一致；若要追須先找回2026-09前的舊快照/程式版本）。",
          "- 兩臂在絕大多數格子差距很小、且方向不一致，**沒有證據顯示Q4前視是p≈0.05的主要來源**；p值差異更可能來自其他版本漂移（09-19成本模型更正等，未逐一驗證）。",
          "- **未觸發分支(c)**：唯一 p<0.06 的格子是A_4pass/ic_weighted/**月頻**與regime_weighted/月頻（修正臂p=0.049/0.052），且legacy臂在同格p=0.081/0.089——"
          "方向與「前視灌水」相反，但這是12個VAL格取最小、未做多重比較校正（Bonferroni門檻遠低於0.05，數值見SELECTION_BIAS_LEDGER.md），且不是預先指定的季頻格，**不得據此稱不依賴前視的alpha殘存，仍FAIL**。",
          "- 多重比較：修正臂12個參數點已登記進`TRIALS_REGISTRY.jsonl`（legacy臂為對照複本，不另計N）。"]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    if not register:
        return 0
    from trial_registry import register_trial
    ids = []
    for fv, m, c, ct, cv, lt, lv in trials:
        design = (f"財報PIT.四(2026-09-20)：80檔驗證樣本(sample_universe_ids(100,SAMPLE_SEED)，載入{int(ct.n_stocks)}檔)，因子版本={fv}、權重={m}(寫死舊IC常數)、"
                  f"再平衡={c}、1x成本、無隨機對照組；修正臂=現行pit.statutory_quarterly_pit_date(Q4=次年3/31)，對照臂legacy_q4_lookahead=期末+45日。"
                  "**登記於跑完之後**(job 20260920-163914-3073)，設計與判定分支凍結於pit4_rerun_80name.py檔頭(commit 73ac722a)。")
        result = (f"修正臂 TRAIN alpha={ct.alpha_ann_pct:+.2f}%(p={ct.alpha_pvalue:.4f}) 報酬{ct.return_pct:+.2f}% MDD={ct.mdd_pct:.2f}%；"
                  f"VAL alpha={cv.alpha_ann_pct:+.2f}%(p={cv.alpha_pvalue:.4f}) 報酬{cv.return_pct:+.2f}% MDD={cv.mdd_pct:.2f}% beta={cv.beta:.2f}。"
                  f"legacy對照臂：TRAIN alpha={lt.alpha_ann_pct:+.2f}%(p={lt.alpha_pvalue:.4f})、VAL alpha={lv.alpha_ann_pct:+.2f}%(p={lv.alpha_pvalue:.4f})")
        notes = ("VAL alpha無一達Bonferroni門檻，FAIL維持；此為對原FAIL結論的重跑，非新候選。legacy臂不另計N。"
                 "legacy臂重現不出原p=0.053（見PIT4_RERUN_RESULT.md）→前視貢獻不可量化。V不適用(無DSR輸入)。"
                 "failed_gates標unknown：判死依據是組合層alpha顯著性，不在GATE_SEQUENCE六關值域內。")
        tid, _ = register_trial(track="TW", name=f"portfolio_multifactor_v2 80檔PIT修正重跑：{fv}/{m}/{c}",
                                design=design, result=result, verdict="FAIL", notes=notes,
                                failed_gates=["unknown"], date="2026-09-20",
                                round_note="DevQueue交辦財報PIT.四(驗證帽)，非馬拉松輪次；DevQueue-Cycle 20260920-171601")
        ids.append(tid)
    print("已登記試驗編號：", ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--register" in sys.argv))
