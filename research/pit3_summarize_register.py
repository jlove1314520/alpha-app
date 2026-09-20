"""財報PIT.三 收尾：把`pit3_rerun_v2_corrected.py`已跑完的結果（`data/pit3_rerun_v2_corrected.csv`）
整理成兩臂對照表、判定分支，並把「修正臂」的12個參數點登記進試驗帳本。

**誠實記錄（登記時序瑕疵）**：交辦要求「先用register_trial()登記再跑」，但`pit3_rerun_v2_corrected.py`
在本腳本之前已由較早的輪次跑完（2026-09-20 15:03~15:25，job 20260920-150342-4659，exit 0）而沒有先登記。
設計（樣本、兩臂、6種權重模式、判定分支）在該腳本檔頭凍結，結果只由本機快取決定性算出，
本腳本沒有依結果改任何設計；補登記不會改變任何數字，只是登記發生在跑完之後。

登記口徑：12個參數點（6種權重模式×2種再平衡頻率）＝修正臂各一筆；legacy臂是「同程式碼、只換PIT日期」
的對照複本，不是新的搜尋，**不另計入N**（見登記備註）。每筆的TRAIN/VALIDATION是同一參數點的兩個評估區間。

用法：python pit3_summarize_register.py          # 只印表與判定
      python pit3_summarize_register.py --register  # 另外正式登記12筆（不可重複執行）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CSV = HERE / "data" / "pit3_rerun_v2_corrected.csv"
OUT_MD = HERE / "PIT3_RERUN_RESULT.md"


def _cell(df, arm, mode, cad, label):
    r = df[(df.arm == arm) & (df.weight_mode == mode) & (df.cadence == cad) & (df.label == label)].iloc[0]
    return r


def main(register: bool) -> int:
    df = pd.read_csv(CSV)
    modes = list(dict.fromkeys(df.weight_mode))
    cads = ["monthly", "quarterly"]
    lines = ["| 權重模式 | 頻率 | 修正臂 TRAIN alpha%(p) | 修正臂 VAL alpha%(p) | legacy臂 TRAIN alpha%(p) | legacy臂 VAL alpha%(p) |",
             "|---|---|---|---|---|---|"]
    trials = []
    for m in modes:
        for c in cads:
            ct, cv = _cell(df, "corrected", m, c, "TRAIN"), _cell(df, "corrected", m, c, "VALIDATION")
            lt, lv = _cell(df, "legacy_q4_lookahead", m, c, "TRAIN"), _cell(df, "legacy_q4_lookahead", m, c, "VALIDATION")
            f = lambda r: f"{r.alpha_ann_pct:+.2f}({r.alpha_pvalue:.3f})"
            lines.append(f"| {m} | {c} | {f(ct)} | {f(cv)} | {f(lt)} | {f(lv)} |")
            trials.append((m, c, ct, cv, lt, lv))
    v = df[(df.label == "VALIDATION")]
    corr, leg = v[v.arm == "corrected"], v[v.arm == "legacy_q4_lookahead"]
    summ = [
        f"- 樣本：`safe_pool_ids()`前300檔，實際載入 {int(df.n_stocks.iloc[0])} 檔；A_4pass三成分（eps_family/revenue_surprise/low_vol）；1x成本、無隨機對照組（quick scan）",
        f"- VAL alpha p值：修正臂最小 **{corr.alpha_pvalue.min():.3f}**（12組中 p<0.06 有 {(corr.alpha_pvalue < 0.06).sum()} 組、p<0.10 有 {(corr.alpha_pvalue < 0.10).sum()} 組）；"
        f"legacy臂VAL最小 {leg.alpha_pvalue.min():.3f}（p<0.06 有 {(leg.alpha_pvalue < 0.06).sum()} 組）",
        f"- alpha為負的組數（兩臂全部48列）：{int((df.alpha_ann_pct <= 0).sum())}",
        f"- 原設計兩個「寫死舊IC常數」的最佳組合對應列（ic_weighted_hardcoded，monthly）：修正臂 VAL p={_cell(df,'corrected','ic_weighted_hardcoded','monthly','VALIDATION').alpha_pvalue:.4f}"
        f"、legacy臂 VAL p={_cell(df,'legacy_q4_lookahead','ic_weighted_hardcoded','monthly','VALIDATION').alpha_pvalue:.4f}",
    ]
    md = ["# 財報PIT.三：Q4前視修正對 portfolio_multifactor_v2 alpha 的影響（重跑結果）", "",
          "來源：`pit3_rerun_v2_corrected.py`（設計凍結於檔頭）→`data/pit3_rerun_v2_corrected.csv`。"
          "本檔由`pit3_summarize_register.py`產生。", "", *summ, "", *lines, "",
          "## 判定（依交辦原文分支）", "",
          "- **不觸發分支(b)**：修正臂12組VAL中沒有任何一組 p<0.06，不存在「不依賴前視的alpha殘存」的證據。",
          f"- **落在交辦分支(a)(p>0.1)與(b)(p<0.06)之間的灰色帶（誠實揭露）**：修正臂VAL最小p={corr.alpha_pvalue.min():.3f}"
          "(ic_weighted_train_only/monthly)，原設計對應組合(ic_weighted寫死常數/月頻)VAL p=0.0998(貼著0.10邊界，嚴格說不>0.1)。"
          "**[自行裁量]歸(a)側**：理由——LEADS該列的判讀依據是「p≈0.053接近顯著」，修正後最好也只有0.083、且是12組取最小(未校正多重比較，"
          "Bonferroni門檻約0.004)，已不支持該判讀。→ LEADS.md該列改標「證據作廢」(可推翻)。alpha沒有轉負(48列全正)。",
          "- **重要範圍界定**：LEADS/GRAVEYARD記載的p=0.053來自**原80檔驗證樣本**（A/IC加權/季頻與B/IC加權/季頻，alpha +10.4%/+10.3%），"
          "不是本次重跑的295檔bigsample；bigsample本來就已判「樣本越大越明確不顯著」。本次交辦指定重跑的是bigsample（A_4pass，季頻優先、月頻其次），"
          "所以**本重跑沒有直接重測那個80檔樣本**——80檔樣本的p=0.053是否受Q4前視影響，仍未被直接量化（若要量化須另跑`portfolio_backtest_v2.py`的80檔設定）。",
          "- **無法量化「p=0.053有多少來自前視」（誠實揭露）**：legacy臂（同程式碼、只把Q4可得日改回舊的2/14）本身**也沒有重現p≈0.05**"
          "（VAL最小p=0.170；且legacy臂VAL alpha在12組中約10組比修正臂低，方向與「前視灌水」相反）。"
          "另外legacy臂對照既有`portfolio_backtest_v2_bigsample300_quick_scan.csv`的重現檢查也不吻合（例：equal/monthly/TRAIN 舊p=0.0089 vs legacy臂p=0.256）。"
          "可能的差異來源（**未逐一驗證，僅列出**）：2026-09-19成本模型更正（手續費折數/滑價）、樣本檔數295 vs 298、"
          "其他PIT函式（月營收/資產負債表）改動、程式碼版本漂移。**因此結論是「目前管線與資料下，原先p=0.053的說法無法成立」，"
          "而不是「Q4前視造成了X%的alpha」**——後者需要先把舊快照的數字重現出來才能做。",
          "- 多重比較：本次修正臂12個參數點已登記進`TRIALS_REGISTRY.jsonl`（legacy臂為對照複本，不另計N）。",
          ]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    if not register:
        return 0

    from trial_registry import register_trial
    ids = []
    for m, c, ct, cv, lt, lv in trials:
        design = (f"財報PIT.三(2026-09-20)：以修正後pit.quarterly_pit()(Q4=次年3/31)重跑portfolio_backtest_v2 A_4pass三成分"
                  f"(eps_family/revenue_surprise/low_vol)，權重模式={m}、再平衡={c}、樣本safe_pool前300檔(載入{int(ct.n_stocks)}檔)、1x成本、無隨機對照組(quick scan)；"
                  "對照臂legacy_q4_lookahead=同程式碼只把PIT改回期末+45日。**登記於跑完之後**(job 20260920-150342-4659)，設計凍結於pit3_rerun_v2_corrected.py檔頭。")
        result = (f"修正臂 TRAIN 報酬{ct.return_pct:+.2f}% alpha={ct.alpha_ann_pct:+.2f}%(p={ct.alpha_pvalue:.4f}) MDD={ct.mdd_pct:.2f}% beta={ct.beta:.2f}；"
                  f"VAL 報酬{cv.return_pct:+.2f}% alpha={cv.alpha_ann_pct:+.2f}%(p={cv.alpha_pvalue:.4f}) MDD={cv.mdd_pct:.2f}% beta={cv.beta:.2f}"
                  f"（大盤TRAIN{ct.buy_and_hold_index_pct:+.2f}%/VAL{cv.buy_and_hold_index_pct:+.2f}%）。"
                  f"legacy對照臂：TRAIN alpha={lt.alpha_ann_pct:+.2f}%(p={lt.alpha_pvalue:.4f})、VAL alpha={lv.alpha_ann_pct:+.2f}%(p={lv.alpha_pvalue:.4f})")
        notes = ("VAL alpha未達顯著(p>0.05)，FAIL維持；此為對原FAIL結論的重跑，非新候選。legacy臂為同參數點對照複本，不另計入N。"
                 "V(Sharpe離散度)不適用(無DSR輸入)。failed_gates標unknown：判死依據是組合層alpha顯著性，不在GATE_SEQUENCE六關值域內。"
                 "重跑未能重現舊快照數字(見PIT3_RERUN_RESULT.md)，故無法量化前視貢獻。")
        tid, _ = register_trial(track="TW", name=f"portfolio_multifactor_v2 A_4pass PIT修正重跑：{m}/{c}",
                                design=design, result=result, verdict="FAIL", notes=notes,
                                failed_gates=["unknown"], date="2026-09-20",
                                round_note="DevQueue交辦財報PIT.三(驗證帽)，非馬拉松輪次；DevQueue-Cycle 20260920-154601")
        ids.append(tid)
    print("已登記試驗編號：", ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--register" in sys.argv))
