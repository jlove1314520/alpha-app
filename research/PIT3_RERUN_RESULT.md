# 財報PIT.三：Q4前視修正對 portfolio_multifactor_v2 alpha 的影響（重跑結果）

來源：`pit3_rerun_v2_corrected.py`（設計凍結於檔頭）→`data/pit3_rerun_v2_corrected.csv`。本檔由`pit3_summarize_register.py`產生。

- 樣本：`safe_pool_ids()`前300檔，實際載入 295 檔；A_4pass三成分（eps_family/revenue_surprise/low_vol）；1x成本、無隨機對照組（quick scan）
- VAL alpha p值：修正臂最小 **0.083**（12組中 p<0.06 有 0 組、p<0.10 有 2 組）；legacy臂VAL最小 0.170（p<0.06 有 0 組）
- alpha為負的組數（兩臂全部48列）：0
- 原設計兩個「寫死舊IC常數」的最佳組合對應列（ic_weighted_hardcoded，monthly）：修正臂 VAL p=0.0998、legacy臂 VAL p=0.2170

| 權重模式 | 頻率 | 修正臂 TRAIN alpha%(p) | 修正臂 VAL alpha%(p) | legacy臂 TRAIN alpha%(p) | legacy臂 VAL alpha%(p) |
|---|---|---|---|---|---|
| equal | monthly | +3.70(0.271) | +4.56(0.270) | +3.94(0.256) | +3.64(0.367) |
| equal | quarterly | +2.11(0.485) | +1.58(0.692) | +1.81(0.548) | +1.91(0.635) |
| ic_weighted_hardcoded | monthly | +4.85(0.114) | +6.08(0.100) | +4.76(0.127) | +5.22(0.217) |
| ic_weighted_hardcoded | quarterly | +3.12(0.204) | +3.43(0.360) | +2.66(0.273) | +3.47(0.357) |
| regime_weighted_hardcoded | monthly | +4.38(0.218) | +4.77(0.202) | +5.32(0.132) | +4.06(0.346) |
| regime_weighted_hardcoded | quarterly | +1.88(0.495) | +5.16(0.146) | +1.31(0.633) | +4.87(0.170) |
| ic_weighted_valIC | monthly | +2.94(0.353) | +2.16(0.557) | +5.07(0.130) | +3.67(0.369) |
| ic_weighted_valIC | quarterly | +3.56(0.253) | +4.68(0.230) | +2.23(0.457) | +2.68(0.504) |
| regime_weighted_valIC | monthly | +4.13(0.212) | +3.15(0.403) | +4.68(0.205) | +2.69(0.552) |
| regime_weighted_valIC | quarterly | +2.91(0.344) | +4.34(0.283) | +2.56(0.409) | +2.42(0.541) |
| ic_weighted_train_only | monthly | +3.68(0.234) | +5.78(0.083) | +4.17(0.224) | +4.09(0.349) |
| ic_weighted_train_only | quarterly | +2.34(0.351) | +5.35(0.138) | +2.95(0.253) | +1.85(0.595) |

## 判定（依交辦原文分支）

- **不觸發分支(b)**：修正臂12組VAL中沒有任何一組 p<0.06，不存在「不依賴前視的alpha殘存」的證據。
- **落在交辦分支(a)(p>0.1)與(b)(p<0.06)之間的灰色帶（誠實揭露）**：修正臂VAL最小p=0.083(ic_weighted_train_only/monthly)，原設計對應組合(ic_weighted寫死常數/月頻)VAL p=0.0998(貼著0.10邊界，嚴格說不>0.1)。**[自行裁量]歸(a)側**：理由——LEADS該列的判讀依據是「p≈0.053接近顯著」，修正後最好也只有0.083、且是12組取最小(未校正多重比較，Bonferroni門檻約0.004)，已不支持該判讀。→ LEADS.md該列改標「證據作廢」(可推翻)。alpha沒有轉負(48列全正)。
- **重要範圍界定**：LEADS/GRAVEYARD記載的p=0.053來自**原80檔驗證樣本**（A/IC加權/季頻與B/IC加權/季頻，alpha +10.4%/+10.3%），不是本次重跑的295檔bigsample；bigsample本來就已判「樣本越大越明確不顯著」。本次交辦指定重跑的是bigsample（A_4pass，季頻優先、月頻其次），所以**本重跑沒有直接重測那個80檔樣本**——80檔樣本的p=0.053是否受Q4前視影響，仍未被直接量化（若要量化須另跑`portfolio_backtest_v2.py`的80檔設定）。
- **無法量化「p=0.053有多少來自前視」（誠實揭露）**：legacy臂（同程式碼、只把Q4可得日改回舊的2/14）本身**也沒有重現p≈0.05**（VAL最小p=0.170；且legacy臂VAL alpha在12組中約10組比修正臂低，方向與「前視灌水」相反）。另外legacy臂對照既有`portfolio_backtest_v2_bigsample300_quick_scan.csv`的重現檢查也不吻合（例：equal/monthly/TRAIN 舊p=0.0089 vs legacy臂p=0.256）。可能的差異來源（**未逐一驗證，僅列出**）：2026-09-19成本模型更正（手續費折數/滑價）、樣本檔數295 vs 298、其他PIT函式（月營收/資產負債表）改動、程式碼版本漂移。**因此結論是「目前管線與資料下，原先p=0.053的說法無法成立」，而不是「Q4前視造成了X%的alpha」**——後者需要先把舊快照的數字重現出來才能做。
- 多重比較：本次修正臂12個參數點已登記進`TRIALS_REGISTRY.jsonl`（legacy臂為對照複本，不另計N）。
