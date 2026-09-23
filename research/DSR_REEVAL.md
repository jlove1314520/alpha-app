# DSR_REEVAL.md — 用 Deflated Sharpe 重評現存候選（Cowork.審視1.1）

**自動產生**：`research/dsr_reeval.py`（2026-09-23 20:20）。每次新增候選或新增回測輸出後重跑。

## 0. 一句話結論

帳本裡判定為 CHEAP_PASS／PASS／EXPERIMENTAL 的候選共 **103 筆**；其中 **3 筆湊得齊 DSR 的輸入**，**倒下 3 筆、撐住 0 筆**；剩下 **100 筆連 Sharpe 都沒有，無法計算**——**無法計算不等於通過**，這些一律不得提請審核。

## 1. 這次是怎麼把「算不出來」變成「算得出來」的

債務2.3 當時的結論是「帳本無 Sharpe，DSR 算不出來，不編數字」。這支照 `CLAUDE.md` 七、資料原則的回退鏈再找一次：

1. 主來源 `TRIALS_REGISTRY.jsonl` 的 `dsr_inputs` —— 債務2.4 才新增的欄位，只有新登記才有，歷史候選一筆都沒有。
2. 備援 `research/data/*.csv` —— **22 個檔案、216 列真的有 `sharpe` 數值**，用檔名 token 對回候選代碼。
3. 由已有欄位推導 T —— 有 `n_days` 就用，沒有就用 `start`/`end` 推交易日數。

**全部假設都刻意偏向「讓候選容易通過」**，所以「連這樣都倒下」才是穩健結論：

- skew=0、kurt=3（常態）。真實策略多半左偏厚尾，那會壓低 DSR。
- 同一個候選對到多列時取**最高**的 Sharpe。
- T 用扣週末不扣國定假日的估計值（偏高，DSR 偏高）。

## 2. 分母與試驗間 Sharpe 分布

| 項目 | 值 | 來源 |
|---|---|---|
| 試驗次數 N | 386 | 取兩口徑較大者（較保守）：trial_registry 386 列（排除 FDR 對照表）／selection_bias_ledger 386 列（含對照表）；口徑分歧待總司令裁示 |
| 實測試驗 Sharpe 筆數 | 216 | `research/data/*.csv` 的 `sharpe` 欄（已排除大盤基準 benchmark_taiex_stats.csv） |
| 試驗 Sharpe 平均（年化） | 0.7737 | 同上 |
| 試驗 Sharpe 標準差（年化） | 0.2526 | 同上 |
| V（日尺度變異數，DSR 用） | 0.000253 | 年化變異數 ÷ 252 |
| SR0＝期望最大 Sharpe（日） | 0.0473 | ＝年化 0.751 |

**怎麼讀**：就算所有策略的真實 Sharpe 都是 0，搜了 386 次之後，最好的那一個看起來也會有年化 0.75 的 Sharpe。候選的 Sharpe 沒有明顯超過這條線，它就只是搜尋次數的產物。

**誠實限制**：這 216 列 Sharpe 只涵蓋有寫出 CSV 的**組合/策略層**回測；因子層 IC 測試本來就沒有 Sharpe，所以 V 是「策略層試驗」的離散度，拿它當全部 386 次試驗的離散度是一個近似。V 估太小會**高估** DSR（門檻變鬆），所以下面每一列都附臨界 V。

## 3. V 敏感度：門檻對假設有多敏感

| 試驗 Sharpe 標準差（年化） | SR0（年化） |
|---:|---:|
| 0.10 | 0.297 |
| 0.25 | 0.743 |
| 0.50 | 1.487 |
| 0.75 | 2.230 |
| 1.00 | 2.974 |

## 4. 逐筆重評

「臨界 V」＝要讓這個候選剛好通過 DSR 0.95，試驗間 Sharpe 標準差最多只能多小。實測值是 0.253；臨界值**低於**實測值就是倒下，而且差越多倒得越徹底。

| 帳本# | 軌 | 代碼 | 帳本判定 | 年化 Sharpe | T | DSR | 臨界 Sharpe 標準差 | 結果 | Sharpe 來源 |
|---:|---|---|---|---:|---:|---:|---:|:-:|---|
| 133 | hypothesis_queue | `short_sale_utilization_portfolio_v1` | PASS | 0.849 | 1043 | 0.5785 | 0.013 | **倒下** | `short_sale_utilization_portfolio_v1` → `research/data/short_sale_utilization_portfolio_v1_results.csv`（VALIDATION，同檔取最高 Sharpe） |
| 98 | 未分軌 | `calibration_probe_momentum_12_1` | PASS | 0.508 | 1043 | 0.3107 | 過不了（與搜尋次數無關） | **倒下** | `calibration_probe_momentum_12_1` → `research/data/calibration_probe_momentum_12_1.csv`（VALIDATION／monthly，同檔取最高 Sharpe） |
| 75 | TW | `dividend_yield_portfolio_v1` | PASS | 1.221 | 1043 | 0.8302 | 0.138 | **倒下** | `dividend_yield_portfolio_v1` → `research/data/dividend_yield_portfolio_v1_results.csv`（VALIDATION，同檔取最高 Sharpe） |
| 381 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 375 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 368 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 357 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 356 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 355 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 354 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 353 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 352 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 351 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 350 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 344 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 343 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 342 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 341 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 340 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 339 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 338 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 335 | TW | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 332 | TW | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 323 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 322 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 270 | FUT | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 240 | TW | `(無代碼)` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 231 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 226 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 225 | hypothesis_queue | `f_lending_fee_spike` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 221 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 206 | US | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 191 | US | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 182 | hypothesis_queue | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 180 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 173 | TW | `f_value_pe` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 171 | US | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 170 | US | `f_us_value_bm` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 168 | hypothesis_queue | `adr_premium_assembly` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 166 | TW | `f_value_pe` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 165 | US | `f_us_value_bm` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 163 | US | `f_us_value_bm` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 158 | TW | `f_quality_roe_stability` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 156 | TW | `f_quality_roe_stability` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 151 | US | `f_us_low_vol` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 147 | TW | `copper_gold_ratio_gate` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 145 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 144 | US | `f_us_value_bm` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 142 | TW | `margin_debt_level_v1` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 141 | TW | `margin_debt_level_v1` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 140 | TW | `margin_debt_level_v1` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 136 | hypothesis_queue | `short_sale_utilization_gate9_regime_overlay` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 135 | hypothesis_queue | `short_sale_utilization_gate5_loo` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 134 | hypothesis_queue | `short_sale_utilization_gates` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 129 | hypothesis_queue | `f_short_sale_utilization` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 125 | hypothesis_queue | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 121 | TW | `option_pcr_gate` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 119 | US | `f_us_value_bm` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 117 | TW | `f_margin_utilization` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 116 | TW | `f_margin_utilization` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 112 | hypothesis_queue | `equal_weight_rebalance_leave_one_out_v1` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 111 | hypothesis_queue | `equal_weight_rebalance_costs_v1` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 110 | hypothesis_queue | `equal_weight_rebalance_plateau_v1` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 108 | hypothesis_queue | `equal_weight_rebalance_control_v1` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 107 | hypothesis_queue | `equal_weight_rebalance_sanity` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 106 | TW | `revenue_trend_surprise_low_attention` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 104 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 103 | hypothesis_queue | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 93 | hypothesis_queue | `(無代碼)` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 88 | 跨市場 | `spillover_overnight_gate` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 86 | TW | `f_52w_high_prox` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 85 | TW | `f_52w_high_prox` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 84 | TW | `f_52w_high_prox` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 74 | TW | `f_dividend_yield_ttm` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 71 | FUT | `fut_day_gap_continuation` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 61 | TW | `(無代碼)` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 57 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 53 | US | `f_us_momentum_12m` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 52 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 51 | TW | `f_idio_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 47 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 43 | FUT | `fut_basis_mean_reversion_60d` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 42 | TW | `f_value_pb` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 41 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 39 | US | `f_us_low_vol` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 38 | FUT | `fut_basis_mean_reversion_60d` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 37 | FUT | `fut_basis_carry` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 35 | FUT | `fut_basis_carry` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 33 | FUT | `fut_intraday_gap_continuation` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 31 | FUT | `fut_inst_trust_net_position_change_5d` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 27 | FUT | `fut_inst_trust_net_position_change_5d` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 25 | FUT | `fut_inst_foreign_net_position_change_5d` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 17 | TW | `f_quality_roe_stability` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 16 | TW | `f_quality_roe_stability` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 15 | TW | `f_quality_roe_stability` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 14 | TW | `f_value_pe` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 13 | TW | `f_value_pb` | CHEAP_PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 12 | TW | `score_topn_v1` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 11 | TW | `weinstein_stage2_unbiased` | EXPERIMENTAL | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 9 | TW | `f_low_vol` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 8 | TW | `f_revenue_surprise` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 7 | TW | `f_eps_surprise` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |
| 2 | TW | `f_eps_growth` | PASS | — | — | — | — | **無法計算** | 帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe |

## 5. 分軌統計

| 軌 | 候選數 | 倒下 | 撐住 | 無法計算 |
|---|---:|---:|---:|---:|
| FUT | 10 | 0 | 0 | 10 |
| TW | 52 | 1 | 0 | 51 |
| US | 17 | 0 | 0 | 17 |
| hypothesis_queue | 22 | 1 | 0 | 21 |
| 未分軌 | 1 | 1 | 0 | 0 |
| 跨市場 | 1 | 0 | 0 | 1 |

## 6. 誠實揭露

- **100/103 筆算不出 DSR**，因為當初的試驗根本沒有留下 Sharpe。這不是這支程式的缺陷，是登記欄位不足的存量債務；債務2.4 已讓 `register_trial()` 能收 Sharpe/T/skew/kurtosis，往後新登記的才算得出來。
- 算不出來的那些**既不能算撐住、也不能算倒下**，但依債務2.4 的規則**一律不得提請審核**——算不出來不等於通過。
- **覆蓋率是刻意壓低的**：只認名稱欄第一個代碼去對檔名。名稱欄常寫「比照 `xxx_portfolio_v1` 手法」這種對照引用，往下多找一個 token 就會多對到 2～3 筆，但其中有把別人的績效安到這一筆頭上的（實測過：#85 是52 週高點那條，卻會被配到股利率那支的 Sharpe）。**配錯比沒有數字更糟**，所以寧可少配。要提高覆蓋率的正解是登記時就記 Sharpe，不是放寬比對。
- 這裡的 Sharpe 是**用檔名對回來**的，不是登記當下記下來的。對錯與否可從「Sharpe 來源」欄逐筆覆核；有疑義的以帳本原文為準。
- V 的口徑（策略層 vs 全部試驗）與 N 的口徑（190 vs 223）都還沒有定論，所以第 3 節的敏感度表與第 4 節的臨界值比單一個 DSR 數字更該看。

