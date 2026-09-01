# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-09-02T06:31+08:00（馬拉松第286輪，取鎖乾淨）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 05:01（第283輪，最舊）、FUT 05:31（第284輪）、US 06:02（第285輪，最新）——依輪替選TW。獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。兩項允許的背景工作也獨立複查仍已達標（`data/backfill_state.json`檔案mtime未變、鍵數3066筆，跟上一輪口徑一致，遠高於80%門檻；T86回補自第164輪起維持100%完成記錄）。**TW軌沒有已知的剩餘允許工作項目，本輪整輪跳過，未做任何實質工作。**`is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅既有12個未追蹤log/腳本殘留（同前幾輪記錄的性質，另一互動session留下），未觸碰、未納入本輪commit。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約177輪、跨度約153.9小時（約6.41天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。** 詳見`REPORT.md`第286輪條目、`TW_LOG.md`本輪記錄。


**上一則保留（第283輪，供對照）**：2026-09-02T05:01+08:00（馬拉松第283輪）——取鎖乾淨，依輪替選TW。複查三個解除條件皆未成立，兩項地基工作複查仍已達標，沒有已知的剩餘工作項目，本輪整輪跳過。完整見`TW_LOG.md`第283輪記錄。

**上一則保留（第280輪，供對照）**：2026-09-02T03:31+08:00（馬拉松第280輪）——取鎖乾淨，依輪替選TW。複查三個解除條件皆未成立，兩項地基工作複查仍已達標，沒有已知的剩餘工作項目，本輪整輪跳過。完整見`TW_LOG.md`第280輪記錄。

（第256輪起～第110輪暫停規則生效期間，共約38則同性質「跳過」對照條目已於第277輪精簡移除，完整逐輪細節見`TW_LOG.md`對應輪次記錄，未遺失任何資訊，僅本檔案不再重複保留。）

**上一則保留（第110輪，供對照）**：2026-08-26T20:36+08:00（馬拉松第110輪）**——**🛑 使用者於2026-08-26晚裁示暫停所有新單因子IC試驗，見`MARATHON_PROTOCOL.md`最上方；本輪之前已有互動session完成`PORTFOLIO_STRATEGY_SPEC.md`（規格書，狀態「待使用者確認」）＋`portfolio_backtest_v2.py`（12組合：因子版本A/B×等權/IC加權/情境加權×月/季頻，全部套`PORTFOLIO_STRATEGY_SPEC.md`規格：20檔/15%停損/流動性門檻/全成本），並已完成commit+push（`fa369b9`）——完整結果見`LEADS.md`的`portfolio_multifactor_v2`列、`REPORT.md`2026-08-26T20:35條目。判定FAIL（alpha顯著性關卡，12組合p值皆>0.05），但兩個最佳組合（A/B兩版皆為IC加權+季頻）p=0.053明確標記「接近顯著、值得追蹤」。**本輪（第110輪）取鎖時偵測到`LOCK_STALE`（pid 154480約30分鐘）——查證後這不是異常中止，是上述互動session跑`portfolio_backtest_v2.py`耗時較久沒更新鎖檔心跳，該session自己完成commit+push跟本輪取鎖幾乎同時發生，屬鎖機制設計沒完全涵蓋的邊界情況（時間型鎖檔對「活著但慢」跟「真的死了」無法區分），沒有資料損毀，但下一輪／後續維護者應注意這個案例。**三軌正常輪替本應選US（時間戳最舊），但US無組合策略相關工作可做；SPEC本身標記「待使用者確認」、且該互動session的「下一步」建議明確寫「不會自己動手，留給使用者決定優先序」（含：換全市場81.3%樣本重跑IC加權+季頻、train-only IC權重的更嚴格樣本外測試、大盤MDD/Sortino基準補算）——本輪判斷不宜代為決定要不要啟動這些高成本重跑，依暫停規則本輪不開始新工作，只核對狀態、補寫這份state檔案。下一輪如果撿到TW軌，先確認使用者是否已回應這些「下一步」選項之一，有明確指示才動手；沒有的話，繼續等待，不要自行升級。**

**上一則保留（第107輪，供對照）**：2026-08-26T19:45+08:00——取鎖時偵測到`LOCK_STALE`（pid 136608持有29.9分鐘，上一輪疑似異常中止；commit前發現實際上有殘留孤兒工作——round 105/106的驅動腳本跟US軌文件未commit，本輪一併補上）。延續`TW_LEADS.md`#3「TRAIN期絕對報酬拆解」開放問題：新增`decompose_f_quality_roe_stability_rebalance.py`，60日換倉版本TRAIN/VAL同號皆正（支持週轉成本drag假說），但**意外發現重跑20日對照組不再重現round2/3記錄的TRAIN負值**——推論是backfill_universe.py期間為樣本內部分股票補齊了先前缺失的財報歷史，改變了因子數值。**尚未升格判定**，下一輪最高優先（暫停規則解除後）：完整重跑`deep_dive_f_quality_roe_stability.py`本身（含100次隨機控制組）確認新基準。完整見`TW_LOG.md`第107輪記錄、`TW_LEADS.md`#3、`TRIALS_LEDGER.md`#69。

**上一則保留（第105輪，供對照）**：2026-08-26T17:36:36+08:00（馬拉松第105輪）——`f_gross_margin_stability`（毛利率穩定度，Novy-Marx精神品質異常變體）1a便宜關卡：**FAIL**（train/val同號但強度不足，null percentile=70.7/門檻90.0）。用`quarterly_pit`同快取鍵（跟`f_quality_roe_stability`/`f_asset_growth`/`f_accruals`同源），零新API。**訂正**：上一則（第102輪）「f_value_pb是唯一待深挖候選」的說法是誤植/過時字句——`TW_LEADS.md`#1確認`f_value_pb`深挖早在第85輪已完成（判定EXPERIMENTAL），本輪沒有照那句話重做。TW軌「品質」家族三個變體（ROE穩定度EXPERIMENTAL/accruals FAIL/毛利率穩定度本輪FAIL）、「低風險」（`f_low_vol`/`f_idio_vol`/`f_bab`）、「資產成長」全部至少測完第一批，**待深挖佇列目前為空**。下一輪建議：`f_quality_roe_stability`TRAIN期負報酬拆解（唯一EXPERIMENTAL懸案），或季節性/成長與預估上修/籌碼類（融資券，`MI_MARGN`端點尚未使用過，全新資料集需評估API額度）。完整見`TW_LEADS.md`#11、`TRIALS_LEDGER.md`#67、`TW_LOG.md`本輪記錄。

**上一則保留（第99輪，供對照）**：`f_idio_vol`深挖前置作業完成：跟`f_low_vol`相關性/持股重疊度檢查，`check_idio_vol_low_vol_overlap.py`（零新API，重用既有快取），結果mean Spearman correlation=+0.982、多頭腿Jaccard重疊0.789、空頭腿0.835，**HIGH OVERLAP**——`f_idio_vol`實質是`f_low_vol`高度共線變體，**決策不進深挖，家族結案**。判定從「CHEAP_PASS，待深挖」改列「CHEAP_PASS（但降級，不建議深挖）」。完整見`TW_LEADS.md`#7、`TW_LOG.md`第99輪記錄。（該輪另附帶完成：取鎖時發現`LOCK_STALE`，第98輪FUT工作其實已完整寫完只是commit前當機，已補commit+push，見`REPORT.md`/`FUT_MARATHON_STATE.md`。）

（上一版記錄，保留供對照）**2026-08-26（互動 session，非馬拉松自動輪次）——混合資料源架構上線，宇宙覆蓋率突破 80% 門檻**

**這輪（互動 session，使用者直接下指示，不是排程觸發的馬拉松輪次）做的事，完整見 `DATA.md`/`REPORT.md` 2026-08-26 條目：**
1. **FinMind 額度這天完全用盡（連最小請求都 402），解除瓶頸為最高優先**。價量歷史改用 yfinance 為主（`yf_price_client.py`，`adjust.py::adjusted_price_series()` 已切換，FinMind 手動還原邏輯降為備援）；三大法人買賣超改用 TWSE T86 為主（`twse_t86_client.py`／`backfill_t86.py`，按日期快取，一次呼叫涵蓋全市場）；月營收/財報**實測確認 TWSE openapi 只有最新快照、無歷史區間查詢，MOPS 歷史頁有反爬蟲防護擋下**，這兩類暫時仍 100% 依賴 FinMind，已加降級處理（額度用盡時該因子留空，不讓整檔股票的其他因子一起報廢，見 `factors.py`/`score_v2.py` 的 try/except）。
2. **全市場宇宙回補（`backfill_universe.py`）done 判定改成只看價格**（財報/月營收變成盡力而為、不擋 done），一批 560 檔幾乎全部靠 yfinance 成功，**累積覆蓋率 60.0%→81.3%（2597/3196），一次性突破 80% 門檻**。`MAX_CONSECUTIVE_RATE_LIMITS` 從 15 調高到 60（舊門檻在新架構下太容易被「一串較舊下市股剛好連續失敗」誤觸發提早停止）。
3. **⚠️ TWSE T86 端點有自己的反爬蟲封鎖**：`backfill_t86.py` 第一次嘗試在約 30 次呼叫內就被封鎖（回傳「FOR SECURITY REASONS」HTML 頁而非 JSON，307 狀態碼），已加 `TWSEBlockedError` 偵測+立刻停止（不重試）、呼叫間隔從 0.4 秒調高到 2.0 秒（未驗證是否足夠，之後如果還是被擋要再拉長）。**目前 T86 快取只有 36 個交易日**（2015-01-09～2015-02-09 附近），三大法人相關因子（`f_foreign_streak`/`f_inst_flow`）目前實際上大部分日期還是要等 FinMind 額度恢復才有值，這不是已解決、是進行中，誠實記錄。
4. `generate_scores_v2.py`（App 選股頁）加上 `realtime_asof.py::as_of_today()`，基準日從固定 `VAL_END`（2024-12-31）改成即時最新交易日，機制是暫時性拉高 `validation.holdout.VAL_END` 這個模組屬性（不碰 holdout 鎖），詳見該檔案 docstring。過程中順便修好兩個真 bug：`score_v2.py::compute_scores_v2()` 全部股票都算不出分數時 `pd.DataFrame([]).set_index()` 會崩潰（空結果的邊界情況）；`_revenue_yoy_latest()`/`_revenue_growth_12m()` 沒有捕捉 FinMind 402 例外。

**地基狀態：✅ 完整可用，不需要額外搭建。** `universe.py`（全市場宇宙）、`adjust.py`（還原股價，現以 yfinance 為主）、`pit.py`（point-in-time）、`factors.py`（因子計算框架）、`factor_ic.py`（IC 檢定引擎，含 Bonferroni 校正）、`score.py`（綜合分引擎）、`long_short_backtest.py`（十分位多空回測引擎，含配對式隨機控制組/CAPM beta/成本模型）、`twse_t86_client.py`/`yf_price_client.py`（新增的混合資料源客戶端）全部可以直接重用。

**宇宙覆蓋率：81.3%（2597/3196），已達 80% 門檻。** 下一輪起工作單位優先序照 `MARATHON_PROTOCOL.md` 第5b節「達到門檻後改回測新因子/深挖候選為主」，回補變成背景待辦——但**財報/月營收欄位額度用盡時被跳過的股票（本輪560檔嘗試裡405檔屬於此類）需要之後找機會用 `backfill_universe.py` 重跑同一批 stock_id 補上，這批「price done但finrev缺」的名單目前沒有另外落地追蹤（設計上是每次呼叫因子計算時自動重試，不需要專門的回補清單，見 `backfill_universe.py` 2026-08-26 docstring）**。

**已知的立即可做工作（優先序）：**
1. ~~`f_value_pb`／`f_value_pe`／`f_quality_roe_stability` 重測~~ ✅ 第一輪（2026-08-23上午）已完成，見 `TW_LOG.md`／`TW_LEADS.md`／`TRIALS_LEDGER.md` #13–#15。
2. ~~深挖 `f_quality_roe_stability`~~ ✅ 第二輪（2026-08-23中午）已完成，新寫 `deep_dive_f_quality_roe_stability.py`。判定 `EXPERIMENTAL`（不是乾淨PASS）——十分位多空組合穩健贏過配對式隨機控制組、beta近零(market-neutral成立)，但淨成本後絕對報酬train/val正負號不一致，且隨機抽樣解析度不足。完整見 `TRIALS_LEDGER.md` #16、`TW_LEADS.md` #3、`TW_LOG.md` 該輪記錄、`data/deep_dive_f_quality_roe_stability.csv`。
3. ~~加密隨機控制組解析度~~ ✅ 第三輪（2026-08-23下午）已完成，`N_RANDOM_DRAWS` 20→100，6組配置全部仍贏過全部100次抽樣（percentile=100.0，p<0.01，比第二輪p<0.05更嚴格站穩）。判定維持 `EXPERIMENTAL`（train/val絕對報酬正負號不一致這個限制未被觸及，仍未解決）。完整見 `TRIALS_LEDGER.md` #17、`TW_LEADS.md` #3、`TW_LOG.md` 本輪記錄。**注意：跑100次抽樣耗時約9.5分鐘，若下一輪要再加抽樣次數，先評估時間預算（30分鐘鎖檔窗口），避免超時。**
4. ~~深挖 `f_value_pb` 前先補 PIT 驗證~~ ✅ 第四輪（2026-08-23下午）已完成，新寫 `verify_pit_value_pb.py`。2330單檔（2015–2024，40/42季度）跳變偵測：跳變日距季末天數min=32/median=45/max=62（從未貼近0天，無明顯前瞻偏誤），中位數貼近法規45天公告期限跟`pit.py`既有假設。**PIT狀態從「完全未驗證」升級為「單檔抽測無嚴重前瞻偏誤」**（不是完全驗證，只測1檔+間接跳變偵測法）。完整見`TRIALS_LEDGER.md`「已調查但不計入試驗數」表、`TW_LEADS.md`#1/#2、`TW_LOG.md`本輪記錄、`data/verify_pit_value_pb_2330.csv`。
5. ~~全市場宇宙回補第一批~~ ✅ 第五輪（2026-08-24凌晨）已完成，`backfill_universe.py --batch-size 300`。本批嘗試93檔（新完成63/新跳過15），撞限流牆提前停止（設計內行為）。累積覆蓋率199→262/3196（6.2%→8.2%）。完整見 `TW_LOG.md` 本輪記錄。
6. ~~全市場宇宙回補第二批~~ ✅ 第六輪（2026-08-24上午）已完成，`backfill_universe.py --batch-size 300`（自動接續）。本批嘗試108檔（新完成74/新跳過18），撞限流牆提前停止（設計內行為）。累積覆蓋率262→336/3196（8.2%→10.5%）。完整見 `TW_LOG.md` 本輪記錄。
7. ~~全市場宇宙回補第三批~~ ✅ 第八輪已完成，`backfill_universe.py --batch-size 300`（自動接續）。本批合計嘗試98檔（新完成72/新跳過11），撞限流牆提前停止（設計內行為）。累積覆蓋率336→408/3196（10.5%→12.8%）。完整見 `TW_LOG.md` 本輪記錄。
8. ~~全市場宇宙回補第四批~~ ✅ 第26輪（2026-08-23T23:03，取鎖時偵測到`LOCK_STALE`，第25輪因`STATUS_CONTROL_C_EXIT`無輸出）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案已有449 done（比第八輪記錄的408略高，推測第25輪中止前有部分進度先落地）。本批嘗試51檔（新完成31/新跳過5），撞限流牆提前停止（設計內行為）。累積覆蓋率449→480/3196（14.1%→15.0%）。完整見 `TW_LOG.md` 本輪記錄。
9. ~~全市場宇宙回補第五批~~ ✅ 第28輪（2026-08-24T00:34，取鎖時偵測到`LOCK_STALE`，上一輪pid 103272持有鎖滿60分鐘後被回收，中間某一輪疑似完全沒跑完就異常中止，未留下任何log）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為509 done/109 skip（比第26輪記錄的480略高，推測中止的那輪有部分進度先落地）。本批嘗試101檔（新完成60/新跳過13），撞限流牆提前停止（設計內行為）。累積覆蓋率509→569/3196（15.9%→17.8%）。完整見 `TW_LOG.md` 本輪記錄。
10. ~~全市場宇宙回補第六批~~ ✅ 第29輪（2026-08-24T02:35，取鎖時偵測到`LOCK_STALE`，上一輪pid 114240持有鎖滿90分鐘後被回收，第28輪之後某一輪疑似完全沒跑完就異常中止，未留下任何log）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為569 done/122 skip，跟state記錄一致（無落差，代表第28輪本身乾淨結束）。本批嘗試78檔（15檔為重複資料，實際新處理63檔），新完成57/新跳過6，撞限流牆提前停止（設計內行為）。累積覆蓋率569→626/3196（17.8%→19.6%）。完整見 `TW_LOG.md` 本輪記錄。
11. ~~全市場宇宙回補第七批~~ ✅ 第31輪（2026-08-24T03:36，取鎖乾淨成功，第30輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為626 done/128 skip，跟state記錄一致（無落差，代表第29輪本身乾淨結束）。本批嘗試104檔，新完成70/新跳過19，撞限流牆提前停止（設計內行為）。累積覆蓋率626→696/3196（19.6%→21.8%）。完整見 `TW_LOG.md` 本輪記錄。
12. ~~全市場宇宙回補第八批~~ ✅ 第34輪（2026-08-24T05:35，取鎖乾淨成功，第33輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為696 done，跟state記錄一致（無落差，代表第31輪本身乾淨結束）。本批嘗試120檔，新完成75/新跳過21，撞限流牆提前停止（設計內行為）。累積覆蓋率696→771/3196（21.8%→24.1%），累積永久跳過147→168。完整見 `TW_LOG.md` 本輪記錄。
13. ~~全市場宇宙回補第十一批~~ ✅ 第40輪（2026-08-24T22:01，取鎖時偵測到`LOCK_STALE`，上一輪pid 116400持有鎖45.2分鐘後被回收，第37輪之後某一輪疑似完全沒跑完就異常中止，未留下任何log）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為846 done/180 skip，跟state記錄一致（無落差，代表第37輪本身乾淨結束）。本批嘗試100檔，新完成72/新跳過13，撞限流牆提前停止（設計內行為）。累積覆蓋率846→918/3196（26.5%→28.7%），累積永久跳過180→193。完整見 `TW_LOG.md` 本輪記錄。
13b. ~~全市場宇宙回補第十二批~~ ✅ 第43輪（2026-08-25T00:00，取鎖時偵測到`LOCK_STALE`，上一輪pid 100692持有鎖滿300.1分鐘後被回收，第42輪期貨軌之後某一輪疑似完全沒跑完就異常中止，未留下任何log）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為918 done/193 skip，跟第40輪記錄一致（無落差）。本批嘗試109檔，新完成74/新跳過20，撞限流牆提前停止（設計內行為）。累積覆蓋率918→992/3196（28.7%→31.0%），累積永久跳過193→213。完整見 `TW_LOG.md` 本輪記錄。
13c. ~~全市場宇宙回補第十三批~~ ✅ 第46輪（2026-08-25T05:37，取鎖乾淨成功，第43輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為992 done/213 skip，跟第43輪記錄一致（無落差）。本批嘗試105檔，新完成78/新跳過9，撞限流牆提前停止（設計內行為）。累積覆蓋率992→1070/3196（31.0%→33.5%），累積永久跳過213→222。完整見 `TW_LOG.md` 本輪記錄。
13d. ~~全市場宇宙回補第十四批~~ ✅ 第49輪（2026-08-25T07:05，取鎖乾淨成功，第46輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1070 done/222 skip，跟第46輪記錄一致（無落差）。本批嘗試130檔，新完成78/新跳過21，撞限流牆提前停止（設計內行為）。累積覆蓋率1070→1148/3196（33.5%→35.9%），累積永久跳過222→243。完整見 `TW_LOG.md` 本輪記錄。
13e. ~~全市場宇宙回補第十五批~~ ✅ 第52輪（2026-08-25T09:03，取鎖時偵測到`LOCK_STALE`，上一輪pid 128940持有鎖滿30.0分鐘後被回收，第49輪之後某一輪疑似完全沒跑完就異常中止，未留下任何log）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1148 done/243 skip，跟第49輪記錄一致（無落差，代表第49輪本身乾淨結束）。本批嘗試109檔，新完成73/新跳過21，撞限流牆提前停止（設計內行為）。累積覆蓋率1148→1221/3196（35.9%→38.2%），累積永久跳過243→264。完整見 `TW_LOG.md` 本輪記錄。
13f. ~~全市場宇宙回補第十六批~~ ✅ 第55輪（2026-08-25T10:31，取鎖乾淨成功，第52輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1221 done/264 skip，跟第52輪記錄一致（無落差）。本批嘗試117檔，新完成74/新跳過22，撞限流牆提前停止（設計內行為）。累積覆蓋率1221→1295/3196（38.2%→40.5%），累積永久跳過264→286。完整見 `TW_LOG.md` 本輪記錄。
13g. ~~全市場宇宙回補第十七批~~ ✅ 第58輪（2026-08-25T12:04，取鎖乾淨成功，第55輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1295 done/286 skip，跟第55輪記錄一致（無落差）。本批嘗試103檔，新完成74/新跳過14，撞限流牆提前停止（設計內行為）。累積覆蓋率1295→1369/3196（40.5%→42.8%），累積永久跳過286→300。完整見 `TW_LOG.md` 本輪記錄。
13h. ~~全市場宇宙回補第十八批~~ ✅ 第61輪（2026-08-25T13:34，取鎖乾淨成功，第58輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1369 done/286 skip，跟第58輪記錄一致（無落差）。本批嘗試103檔，新完成70/新跳過18，撞限流牆提前停止（設計內行為）。累積覆蓋率1369→1439/3196（42.8%→45.0%），累積永久跳過286→318。完整見 `TW_LOG.md` 本輪記錄。
13i. ~~全市場宇宙回補第十九批~~ ✅ 第64輪（2026-08-25T15:13，取鎖乾淨成功，第61輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1439 done/318 skip，跟第61輪記錄一致（無落差）。本批嘗試110檔，新完成77/新跳過13，撞限流牆提前停止（設計內行為）。累積覆蓋率1439→1516/3196（45.0%→47.4%），累積永久跳過318→331。完整見 `TW_LOG.md` 本輪記錄。
13j. ~~全市場宇宙回補第二十批~~ ✅ 第67輪（2026-08-25T16:35，取鎖乾淨成功，第64輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1516 done/331 skip，跟第64輪記錄一致（無落差）。本批嘗試102檔，新完成73/新跳過14，撞限流牆提前停止（設計內行為）。累積覆蓋率1516→1589/3196（47.4%→49.7%，已過半），累積永久跳過331→345。完整見 `TW_LOG.md` 本輪記錄。
13k. ~~全市場宇宙回補第二十一批~~ ✅ 第70輪（2026-08-25T18:05，取鎖乾淨成功，第67輪正常結束）已完成，`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1589 done/345 skip，跟第67輪記錄一致（無落差）。本批嘗試109檔，新完成76/新跳過18，撞限流牆提前停止（設計內行為）。累積覆蓋率1589→1665/3196（49.7%→52.1%），累積永久跳過345→363。完整見 `TW_LOG.md` 本輪記錄。
14. **【2026-08-26使用者裁示更新】下一輪優先序，跟宇宙回補交錯進行，不是互斥**：(1) 覆蓋率仍遠低於80%門檻時繼續跑 `backfill_universe.py --batch-size 300`（撞限流就改做下列其一）；(2) **新增最高優先工作單位——主線1情境條件式檢驗**：`f_foreign_streak`(#3)/`f_rel_strength`(#5)/`f_quality_roe_stability`深挖最終版(#17，train/val反轉) 這三個方向反轉假說，算四組事前可觀測條件（大盤年線上下/波動度環境/市值規模/流動性量能）的分群IC，找方向能不能被條件穩定區分；同時對4個已PASS因子（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`）也各做一次同樣的分群IC。產出寫 `research/REGIME_CONDITIONS.md`。完整規格見 `MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。(3) 主線1做出結果後才輪到**主線2多因子組合策略**（等權/IC加權/情境條件式加權三版本，用Sortino/MDD/alpha顯著性判定，不用絕對報酬贏買進持有）——這是真正的holdout候選，不准自己解鎖。候補工作單位（優先度較低，主線1/2排不進時才做）：(a) 深挖 `f_value_pb`（PIT前置驗證已完成，`deep_dive_f_value_pb.py`未提交待驗證）；(b) 拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag；(c) `weinstein_stage2_unbiased` 的 alpha/beta 顯著性關卡（`WEINSTEIN_ALPHA_GATE_TASK.md`）；(d) `f_value_pe`（待複驗候選）的成本敏感度測試。
15. 覆蓋率達80%門檻、且上面候選都處理完之後，照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化掃過還沒碰過的因子家族：短期反轉、BAB/特異波動率、Amihud流動性、季節性、資產成長異常、Piotroski F-score、accruals盈餘品質。

**FinMind 資料集使用現況（避免重複調查已知資訊）：**
- 已驗證可用：`TaiwanStockPrice`／`TaiwanStockPER`／`TaiwanStockMonthRevenue`／`TaiwanStockFinancialStatements`／`TaiwanStockBalanceSheet`／`TaiwanStockInstitutionalInvestorsBuySell`／`TaiwanStockInfo`／`TaiwanStockDelisting`／`TaiwanStockDividend`。
- 已驗證付費/不可用：`TaiwanStockMarketValue`（市值，付費）、`TaiwanStockTradingDailyReport`（分點進出，付費）。
- 未驗證：融資券餘額、當沖比、借券餘額等籌碼資料集的確切 dataset 名稱跟免費層可用性——第一次要用到時要先用 curl 實測，不要用猜的。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`）。

---

## 下一步

見上方「已知的立即可做工作」。下一個馬拉松輪次接手時，先讀 `TW_LOG.md` 最新一條看上一輪實際做到哪裡（這份 state 檔案是快照，`TW_LOG.md` 才有完整過程）。
