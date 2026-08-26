# REPORT.md — append-only 主日誌

「Session 是消耗品，檔案才是本體」：這份檔案是這個專案唯一不會因為換 session、換機器、換 agent 而消失的執行記錄。

**規則：**
- **只往下 append，不覆寫、不刪除舊條目。** 發現舊條目寫錯了，加一條新的訂正，不要回頭改。
- 每條目格式：`## <ISO 8601 時間戳> — <一行摘要>`，內容至少包含「做了什麼」跟「驗證結果」兩項——沒驗證過的事不能寫得像驗證過。
- 這份檔案記的是**顆粒度細的單一動作**（一個函式寫完測完、一個 bug 修好、一次資料驗證）。里程碑等級的敘事跟決策脈絡記在 [`STRATEGY_LOG.md`](./STRATEGY_LOG.md)；現在整體卡在哪、下一步是什麼，看 [`MARATHON_STATE.md`](./MARATHON_STATE.md)——換 session 接手時**先看 MARATHON_STATE.md**，這份是給「我怎麼走到這裡」找細節用的。
- 策略候選的最終判定記在 [`LEADS.md`](./LEADS.md)，不要跟一般開發記錄混在一起。

---
## 第 120 輪 · 2026-08-27T04:32+08:00 · US（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 04:21(第119輪，最新)/US 03:01(第117輪，最舊)/FUT 03:31(第118輪)，正常輪替選US，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」（`git log`確認自`69c2285`第119輪以來無互動session介入），暫停規則仍完全生效中；US軌無組合策略相關工作（規格書全部圍繞TAIEX/TWSE台股樣本，跟US軌無關），round108/111遺留(a)(b)(c)三項本質仍是為單因子鋪路，同round111/114/117判斷邏輯保守跳過 · 本輪未做任何實質工作，`is_holdout_consumed()`確認`False`，無新`TRIALS_LEDGER.md`列 · 見`US_MARATHON_STATE.md`/`US_LOG.md`本輪附記

## 第 119 輪 · 2026-08-27T04:21+08:00 · TW · T86三大法人回補接續（暫停單因子試驗規則生效中，屬允許的地基工作）· 跑`backfill_t86.py`預設批次(200)，新完成200天（13天無資料），未撞限流；累積T86快取636→836/3305（25.3%）。`is_holdout_consumed()`確認`False`。`PORTFOLIO_STRATEGY_SPEC.md`仍待使用者確認，未代為決定`portfolio_multifactor_v2`下一步。見`TW_LOG.md`/`TW_MARATHON_STATE.md`第119輪記錄。

## 第 118 輪 · 2026-08-27T03:31+08:00 · FUT（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 02:43(第116輪)/US 03:01(第117輪，最新)/FUT 02:01(第115輪，最舊)，正常輪替選FUT，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」（自第117輪以來無互動session介入），暫停規則仍完全生效中；FUT軌唯一明確待辦（`fut_day_gap_continuation`高解析度重測或全新因子家族）本質仍是單因子相關工作，跟round109/112/115判斷邏輯一致保守跳過 · 本輪未做任何實質工作，`is_holdout_consumed()`確認`False`，無新`TRIALS_LEDGER.md`列 · 見`FUT_MARATHON_STATE.md`/`FUT_LOG.md`本輪附記

## 第 117 輪 · 2026-08-27T03:01+08:00 · US（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 02:43(第116輪，最新)/US 01:31(最舊)/FUT 02:01，正常輪替選US，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」（`git log`確認自`bf7895a`第116輪以來無互動session介入），暫停規則仍完全生效中；US軌無組合策略相關工作（規格書全部圍繞TAIEX/TWSE台股樣本，跟US軌無關），round108/111遺留(a)(b)(c)三項本質仍是為單因子鋪路，同round111/114判斷邏輯保守跳過 · 本輪未做任何實質工作，`is_holdout_consumed()`確認`False`，無新`TRIALS_LEDGER.md`列 · 見`US_MARATHON_STATE.md`/`US_LOG.md`本輪附記

## 第 116 輪 · 2026-08-27T02:43+08:00 · TW · 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 01:20(第113輪，最舊)/US 01:31/FUT 02:01，正常輪替選TW，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」且無新使用者回應，`portfolio_multifactor_v2`下一步三選項依round109/110/113一貫判斷不代為決定，延續暫停規則允許的地基工作 · 跑`backfill_t86.run_batch(200)`：200嘗試/200成功/7空(假日)，未撞限流牆 · 累積T86快取436→636/3305個工作日（19.2%）· 順帶核對確認全市場宇宙回補（`backfill_universe.py`）已達2597/3196=81.3%，早超過80%門檻，本輪未動它 · 無新`TRIALS_LEDGER.md`列（地基工作非假說測試），`is_holdout_consumed()`確認`False` · 見`TW_LOG.md`/`TW_MARATHON_STATE.md`本輪記錄

## 第 115 輪 · 2026-08-27T02:01+08:00 · FUT（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 01:20/US 01:31/FUT 21:32(Aug26，最舊)，正常輪替本應選FUT，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」，FUT軌唯一待辦（`fut_day_gap_continuation`邊界候選N=2000高解析度重測）本質是1b深挖、屬單因子相關工作，跟round112/111/114判斷邏輯一致，本輪保守跳過 · 無新判定，`is_holdout_consumed()`確認`False` · 見`FUT_MARATHON_STATE.md`/`FUT_LOG.md`本輪附記

## 第 114 輪 · 2026-08-27T01:31+08:00 · US（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳US 21:02(最舊)/FUT 21:32/TW 01:20(第113輪剛更新)，正常輪替本應選US，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」、`TW_LOG.md`第113輪記錄TW軌下一步也要等使用者回應才接續，暫停規則整體仍完全生效中；US軌無組合策略相關工作可做，round108/111遺留三項待辦皆為單一因子鋪路性質，比照第111輪判斷保守跳過 · 無新判定，`is_holdout_consumed()`確認`False` · 見`US_MARATHON_STATE.md`/`US_LOG.md`本輪附記

## 第 113 輪 · 2026-08-27T01:20+08:00 · TW · 取鎖時偵測到`LOCK_STALE`（pid 146500持有29.9分鐘，接手發現上一輪已修好`backfill_t86.py`的`START_DATE`真bug（TWSE端點2012-05-02前無資料回傳明確錯誤訊息、非反爬蟲封鎖）但未commit）；TW最舊照輪替應選TW，`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」且無新使用者回應，第110輪「下一步」留給使用者決定優先序的高成本重跑選項本輪不代為升級；改做暫停規則明確允許的T86三大法人回補地基工作 · 驗證修復後跑`backfill_t86.run_batch(200)`：200嘗試/200成功/14空(假日)，未撞限流牆 · 累積T86快取236→436/3305個工作日（13.2%）· 無新`TRIALS_LEDGER.md`列（地基工作非假說測試），`is_holdout_consumed()`確認`False` · 見`TW_LOG.md`/`TW_MARATHON_STATE.md`本輪記錄

## 第 112 輪 · 2026-08-26T21:32+08:00 · （跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳TW 20:37/US 21:03(第111輪剛更新)/FUT 19:34(最舊)，正常輪替本應選FUT，但FUT唯一明確待辦（`fut_day_gap_continuation`邊界候選N=2000高解析度重測）本質是1b深挖，屬單因子相關工作，比照第111輪處理US round108待辦的判斷邏輯保守跳過；`PORTFOLIO_STRATEGY_SPEC.md`跟FUT軌無關，本輪無組合策略工作可做 · 無新判定，`is_holdout_consumed()`確認`False` · 見`FUT_MARATHON_STATE.md`/`FUT_LOG.md`本輪附記

## 第 111 輪 · 2026-08-26T21:02+08:00 · （跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌輪替本應選US（時間戳最舊19:05），但US無組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`仍是TW專屬的台股多因子規格，跟US的1c地基工作無關）；FUT（19:34）同樣無組合策略相關工作；TW（20:36）是三軌中最晚更新，本輪不輪到TW；依`MARATHON_PROTOCOL.md`暫停規則第3點，本輪判斷US/FUT皆無工作可做，直接跳過整輪，不代為決定要不要啟動TW那邊留給使用者的高成本重跑選項 · 無新判定，`is_holdout_consumed()`確認`False` · 見`US_MARATHON_STATE.md`/`US_LOG.md`本輪附記

## 第 110 輪 · 2026-08-26T20:36+08:00 · （跳過，暫停規則生效中）· 取鎖時`LOCK_STALE`（pid 154480約30分鐘，查證後非異常中止——是同時段互動session跑`portfolio_backtest_v2.py`太久沒更新鎖檔心跳，該session已自行commit+push`fa369b9`，跟本輪取鎖幾乎同時，屬鎖機制邊界案例非資料損毀）；SPEC+v2回測(12組合)已由該session完成並push，最佳兩組alpha p=0.053接近顯著未過關，其「下一步」建議明確留給使用者決定；US本應輪到但無組合策略相關工作，依暫停規則跳過新工作 · 無新判定，僅核對狀態+補`TW_MARATHON_STATE.md` · 詳見`TW_LOG.md`本輪記錄

## 第 109 輪 · 2026-08-26T19:34+08:00 · FUT · 取鎖乾淨（非陳舊鎖檔）；FUT時間戳最舊（17:05）且近10輪窗口僅佔10%（未超額），選FUT；延續round104`FUT_LEADS.md`#23明確待辦，盤別效應家族第三批——夜盤收盤(T)→日盤開盤(T)跳空反轉/順勢（`fut_cheap_gate.py`新增`hyp_day_gap_reversal`/`hyp_day_gap_continuation`，零新API） · 反轉版FAIL（percentile=0.5，方向嚴重不對）；順勢版**邊界模糊**（percentile=99.5，單測+本批皆過，但累積FUT家族FDR校正未過，差距0.15個百分點落在N=200排列解析度以內，疑似測量雜訊，不排入待深挖清單，建議下一輪N=2000高解析度重測） · 盤別效應家族三種跳空/報酬構造至此窮盡（6假說：5FAIL+1邊界候選）· 見`TRIALS_LEDGER.md`#70/#71、`FUT_LEADS.md`#24/#25

## 第 108 輪 · 2026-08-26T19:05+08:00 · US · 取鎖乾淨（非陳舊鎖檔）；FUT最舊但近10輪已達20%資源配置上限（比照第107輪先例）跳過，選次舊US；價值/品質因子地基第一步——新增`us_fundamentals.py`（XBRL company-facts可重用wrapper） · 確認`StockholdersEquity`+`CommonStockSharesOutstanding`(us-gaap)三檔(AAPL/MSFT/PLTR)皆有資料，PB因子輸入可行性確認；`dei`備援股數標籤PLTR查不到；`gap_days`早期異常值尚未查證，誠實標記待下一輪 · 1c地基工作，不加`TRIALS_LEDGER.md`列 · 見`DATA.md`「美股 PIT 資料源調查（六續）」、`US_MARATHON_STATE.md`#13
## 第 107 輪 · 2026-08-26T19:45+08:00 · TW · 取鎖偵測到LOCK_STALE（上一輪疑似異常中止，無殘留孤兒工作）；FUT本應輪到但近10輪已達20%資源配置上限改選TW；`f_quality_roe_stability` TRAIN期絕對報酬拆解——60日換倉版本TRAIN/VAL同號皆正，但重跑20日對照組意外發現不再重現round2/3的TRAIN負值（推論為backfill_universe.py期間快取演化所致），尚未升格判定，下一輪需完整重跑deep_dive確認新基準 · 見`TRIALS_LEDGER.md`#69、`TW_LEADS.md`#3

## 第 106 輪 · 2026-08-26T18:10:00+08:00 · US · 深挖`f_us_low_vol`中型股tier（#7 CHEAP_PASS）完整1b驗證，取鎖時偵測到LOCK_STALE · FAIL（TRAIN期未過隨機控制組門檻，四個樣本版本全部跑完，`f_us_low_vol`因子家族結案）

## 第 105 輪 · 2026-08-26T17:36+08:00 · TW · 取鎖時偵測到`LOCK_STALE`（pid 148680持有約30.1分鐘，上一輪疑似異常中止，`git status`乾淨、無殘留孤兒工作）；三軌時間戳TW最舊（102輪16:06），選TW；新測`f_gross_margin_stability`（毛利率穩定度，Novy-Marx精神品質異常變體，`MARATHON_PROTOCOL.md`第3節明列但尚未測過的項目），重用`quarterly_pit`同快取鍵零新API · **FAIL**——train/val同號但強度不足，null percentile=70.7（門檻90.0）；順帶訂正TW軌第102輪「f_value_pb是唯一待深挖候選」的過時字句（實際上第85輪已深挖完成，判定EXPERIMENTAL）；`TRIALS_LEDGER.md`#67、`TW_LEADS.md`#11

## 第 104 輪 · 2026-08-26 17:05 · FUT · 取鎖乾淨（非陳舊鎖檔）；FUT時間戳最舊（第98輪13:05，TW第102輪16:06、US第103輪16:38），且近10輪窗口FUT只佔20%（未超額），選FUT；延續第98輪「下一輪建議」(a)項，盤別效應家族第二批——日盤收盤(T-1)→夜盤開盤(T)跳空反轉/順勢，`fut_cheap_gate.py`新增`hyp_night_gap_reversal`/`hyp_night_gap_continuation` · **兩個都FAIL**——反轉版percentile=17.5（方向不對）、順勢版percentile=82.5（方向對但未過90.0單測門檻，跟round98`fut_night_session_reversal`(81.0)同款）；盤別效應家族累計4個假說（round98+本輪）全部FAIL；`TRIALS_LEDGER.md`#65/#66、`FUT_LEADS.md`#22/#23

## 第 103 輪 · 2026-08-26 16:38 · US · 取鎖乾淨（非陳舊鎖檔）；FUT時間戳最舊（13:05）但其自身`FUT_LEADS.md`明確建議近幾輪讓給TW/US（近10輪已佔30%資源上限），故選次舊的US（14:05）；延續第99輪「下一步」建議首選，深挖`f_us_low_vol`小型股tier（#10 CHEAP_PASS）完整1b驗證 · **FAIL**——TRAIN(2015-2020,1x) ann_return=-61.57% beta=+0.260；VAL(2020-2024,1x) ann_return=+280.63% beta=-0.587，train/val正負號翻轉+beta正負號也翻轉，跟round 84不分層版深挖FAIL同款警訊且更嚴重（疑似微型生技/殼股樣本+k=3/leg小decile放大波動）。US軌至今累計13筆試驗、0筆深挖後仍成立的PASS/EXPERIMENTAL；`TRIALS_LEDGER.md`#64、`US_LEADS.md`#13、`deep_dive_f_us_low_vol_small_tier.py`（新增）

## 第 100 輪 · 2026-08-26 14:05 · US · 取鎖乾淨（非陳舊鎖檔）；US時間戳最舊（12:15，FUT 13:05、TW 13:35），選US；延續第97輪「下一步」建議首選，small tier分層重測（四個樣本版本全測完） · `f_us_low_vol`小型股tier**CHEAP_PASS**（percentile=100.0，US軌至今第三個CHEAP_PASS，val IC隨規模遞增，跟leverage-constraint文獻方向一致，但train期IR弱、跟#1深挖FAIL前形狀相似）；`f_us_momentum_12m`FAIL（same_sign未過，四次測試出現三種方向排列，坐實小樣本雜訊）；`f_us_reversal_1m`FAIL（14.4，四版本最差一次，家族結案）；`TRIALS_LEDGER.md`#57/#58/#59、`US_LEADS.md`#10/#11/#12

## 第 99 輪 · 2026-08-26 13:35 · TW · 取鎖時偵測到`LOCK_STALE`（pid 149044持有30.2分鐘，查證後發現第98輪其實已寫完所有記錄檔，只是commit/push前當機，已補commit`1c32ae1`+push，非真正遺失工作）；TW時間戳最舊（12:08）且FUT近10輪已達30%資源配置上限，選TW；TW軌覆蓋率已達81.3%>80%門檻，優先序回到深挖，執行第96輪標記的`f_idio_vol`深挖前置作業 · `check_idio_vol_low_vol_overlap.py`：跟`f_low_vol`相關性=+0.982、多頭腿Jaccard=0.789、空頭腿=0.835，**HIGH OVERLAP，不進深挖，家族結案**，`TW_LEADS.md`#7判定改列「CHEAP_PASS但降級」

## 第 98 輪 · 2026-08-26 13:05 · FUT · 取鎖乾淨（非陳舊鎖檔）；FUT最舊，選FUT（近10輪FUT佔20%，選後30%，仍可接受）；盤別效應家族第一批——夜盤自身open→close報酬順勢/反轉，交易同date日盤日內報酬 · `fut_night_session_momentum`FAIL（19.0，方向不對）、`fut_night_session_reversal`FAIL（81.0，方向對但未過90門檻），盤別效應第一批結案0 PASS，`TRIALS_LEDGER.md`#55/#56、`FUT_LEADS.md`#20/#21

## 第 97 輪 · 2026-08-26 12:38 · US · 取鎖時偵測到`LOCK_STALE`（pid 148860持有31.4分鐘，上一輪疑似異常中止，但沒有留下未commit的孤兒工作需要接手）；US軌時間戳最舊且未受FUT 20%上限問題影響，選US；`us_factor_ic_by_size.py`把`TIER`切成`"mid"`重測三個既有因子（大型股tier已於第95輪測完） · `f_us_low_vol`/`f_us_momentum_12m`中型股tier**CHEAP_PASS**（percentile 100.0/99.9，US軌至今第一批），`f_us_reversal_1m`FAIL（78.4，三個tier全FAIL）；`f_us_momentum_12m`信心等級低（三次tier方向互不相同，疑似樣本雜訊），`TRIALS_LEDGER.md`#52/#53/#54、`US_LEADS.md`#7/#8/#9

## 第 96 輪 · 2026-08-26 12:08 · TW · 取鎖乾淨（非陳舊鎖檔）；FUT最舊但依資源配置20%上限（近10輪已佔40%）跳過，選TW · 低風險/流動性家族第一批2個假說：`f_amihud_illiq`FAIL（方向與文獻相反）；`f_idio_vol`**CHEAP_PASS**（percentile=100.0，TW軌至今單測解析度最強候選之一），排入待深挖清單，`TRIALS_LEDGER.md`#50/#51、`TW_LEADS.md`#6/#7

## 心跳記錄（Heartbeat Log）

## 第 102 輪 · 2026-08-26T16:06+08:00 · TW（reconciliation） · 補齊`f_bab`/`f_asset_growth`/`f_accruals`未commit的積壓工作（驅動腳本`factor_ic_bab.py`/`factor_ic_asset_growth.py`＋`TW_LEADS.md`#8/#9/#10＋主線`LEADS.md`/`STRATEGY_LOG.md`的weinstein_alpha_gate文字紀錄＋`quotes.yml`CI健壯性小改），非新假說測試 · 完整性缺口修復，`TRIALS_LEDGER.md`#61/#62/#63的結果本身不變，只是讓其重新可重複執行

## 第 101 輪 · 2026-08-26T15:36+08:00 · TW · f_accruals（Sloan 1996資產負債表法應計項目）便宜關卡測試 · FAIL，percentile=13.5，TRIALS_LEDGER.md#63

**2026-08-23 新增，使用者要求：「每一輪馬拉松都要編號並留心跳，這樣使用者一眼能看出它有沒有在跳。」**

**跟本檔案其餘部分的慣例不同：這個區塊是新的插最上面（最新的在最上面），不是往下 append。** 目的是讓人打開檔案第一眼就看到馬拉松最近有沒有在跑，不用捲到檔案最底找最新進度。本檔案其餘章節（下面「主日誌」的顆粒度細記錄）維持原本規則不變：只往下 append。

**輪號規則：** 從第 1 輪開始，跨 TW/US/FUT 三軌共用一個全局遞增計數器（不是各軌 commit message 裡各自的輪號，那是另一套、各軌獨立的標籤，兩者不要混淆）。每次 `run-marathon-cycle.ps1` 真正啟動一次 headless 執行（不含「鎖檔被佔用、正常跳過什麼都沒做」那種，見 `MARATHON_PROTOCOL.md` 第 0 節），不管這輪做了什麼、有沒有成功、有沒有 commit，都要算一輪、留一筆記錄——連「這輪什麼都沒做出來」本身都是要誠實記下的訊號，不能因為沒有實質進度就跳過不記。目前輪號存在 `MARATHON_STATE.md` 最上面，每輪從那裡讀「目前是第幾輪」、+1、寫這裡的一筆、再把 `MARATHON_STATE.md` 那行改成新的輪號。

格式：`## 第 N 輪 · YYYY-MM-DD HH:MM · 軌道(TW/US/FUT) · 這輪做了什麼 · 結果/判定`

**第 1–25 輪是 2026-08-23 這次診斷時，用 `marathon_cycle.log`（實際執行的 start/end 時間戳＋輸出摘要）逐筆比對當天 `git log` 的 commit 時間跟訊息回填的，不是從一開始就有記錄——這個機制本身是這次才建立的，回填只到有可靠原始紀錄（`marathon_cycle.log`）涵蓋的範圍為止，不會回填到更早、log 檔案沒有記到的日期。第 25 輪之後（第 26 輪起）才是照這份新規則、由馬拉松自己即時寫的。**

## 第 95 輪 · 2026-08-26 11:34 · US · 取鎖乾淨（非陳舊鎖檔）；規模分層重測三個既有FAIL純價格因子（`f_us_low_vol`/`f_us_momentum_12m`/`f_us_reversal_1m`）大型股tier · 新增`us_factor_ic_by_size.py`，29檔大型股樣本，**三個全部FAIL**（percentile 83.4/66.8/53.4，門檻96.7）；最有資訊量的發現是`f_us_momentum_12m`分層前後train/val反轉方向剛好相反，代表反轉是樣本雜訊不是穩定的規模效應。US軌累積6筆試驗全FAIL，仍無PASS/EXPERIMENTAL候選。`TRIALS_LEDGER.md`#47/#48/#49、`US_LEADS.md`#4/#5/#6

## 第 94 輪 · 2026-08-26 11:03 · TW · 取鎖乾淨（非陳舊鎖檔）；補齊主線`LEADS.md`待辦——`f_rel_strength_regime_switch`那一列從第83輪就已完成策略層深挖判定FAIL，但因互動session其他檔案dirty狀態被連續數輪刻意跳過未同步，本輪把`data/regime_switch_f_rel_strength.csv`（本機既有）的實際數字（TRAIN三成本情境全負報酬/alpha/Sortino，隨機控制組僅84.0~89.0；VAL 1x略正2x/3x轉負，隨機控制組93.0~94.0）寫進`LEADS.md`該列，PENDING→FAIL · 純文件同步工作，不算新假說檢定，`TRIALS_LEDGER.md`不加新列（#40已是權威記錄）

## 第 93 輪 · 2026-08-26 10:34 · FUT · 取鎖乾淨（非陳舊鎖檔）；夜盤感知連續序列建構（1c地基改動）——`continuous_contract.py`新增通用`load_session()`＋`build_continuous_series()`新增`session`參數（`session="after_market"`即為夜盤序列，日盤預設值不變、7個既有呼叫端零破壞性變更），依據第63輪（夜盤時序方向）＋第90輪（轉倉同步性）查證結果重用既有轉倉機制；新寫`fut_validate_night_continuous_series.py`獨立重跑第90輪方法交叉驗證 · **驗證通過**：92/92轉倉事件exact match零差異、1867列NaN/skipped/非正值皆為0；回歸測試確認日盤路徑數字完全不變（6185天/300次轉倉）。盤別效應家族地基至此完全就緒，下一輪可直接開始測第一批盤別效應假說，不需要新測試判定（1c地基類，同第39/60/63/90輪先例不加`TRIALS_LEDGER.md`列）

## 第 92 輪 · 2026-08-26 09:35 · TW · 取鎖時偵測到`LOCK_STALE`（pid 146212持有30.0分鐘，上一輪疑似異常中止）；接手孤兒工作——上一輪已完成`f_short_reversal_1m`（短期反轉，21交易日自身累積報酬取負號）1a便宜關卡測試並產出`factor_ic_short_reversal.py`/`factors.py`定義/`TRIALS_LEDGER.md`#46，但崩潰在完成前，`TW_LOG.md`/`TW_LEADS.md`都還沒補上記錄。本輪重跑腳本確認數字一致（零新API呼叫），補齊`TW_LOG.md`本輪記錄與`TW_LEADS.md`#5列 · **FAIL**（TRAIN mean_ic=+0.0496/VAL mean_ic=−0.0054方向不一致，null percentile=23.1遠未達90.0門檻）；短期反轉家族結案，本輪無新測試，僅補齊上一輪遺漏的文件記錄

## 第 91 輪 · 2026-08-26 09:04 · US · 取鎖乾淨（非陳舊鎖檔接手）；`f_us_reversal_1m`（US軌第三個因子，短期反轉，跟`f_us_momentum_12m`的`MOM_SKIP`用完全相同的21交易日窗口）1a便宜關卡測試（`us_factor_ic.py`沿用既有`evaluate_factor()`框架，同一批27/40可用隨機樣本，`ALREADY_VERDICTED`同步補上`f_us_momentum_12m`維持單因子bonferroni_n=1語義） · **FAIL**（TRAIN mean_ic=+0.0938/VAL mean_ic=−0.0198方向不一致，null percentile=49.5遠未達90.0門檻、甚至低於50，比第88輪動能因子的FAIL更明確，`TRIALS_LEDGER.md`#45）；US軌三個純price-only因子（低波動/動能/反轉）至此全數測完1a，全部FAIL，尚無PASS/EXPERIMENTAL候選

## 第 90 輪 · 2026-08-26 08:33 · FUT · 取鎖時偵測到`LOCK_STALE`（pid 145052持有26.6分鐘，上一輪疑似異常中止——已核實沒有留下未commit的殘留工作，乾淨崩潰）；盤別效應家族地基第二步，新寫`fut_probe_night_session_rollover.py`驗證夜盤轉倉時點是否與日盤同步 · **同步，零例外**：2017-05-16起92筆日盤轉倉事件跟92筆夜盤轉倉事件exact match（92/92），可直接沿用日盤H1轉倉規則到夜盤序列，第60/63輪標記的前置風險項解決，本輪無新增假說測試

## 第 89 輪 · 2026-08-26 07:33 · US · 取鎖時偵測到`LOCK_STALE`（pid 138560持有30.0分鐘，上一輪（第88輪）疑似異常中止在寫收工程序這一步——`MARATHON_STATE.md`計數器仍是87未被上一輪改到88，但`US_MARATHON_STATE.md`/`US_LEADS.md`/`TRIALS_LEDGER.md`已有完整第88輪內容，判斷是死在寫`US_LOG.md`/心跳/計數器這幾步）；核實其留下的孤兒工作（`us_factors.py`新增`f_us_momentum_12m`＋`us_factor_ic.py`＋`US_LEADS.md`#2＋`TRIALS_LEDGER.md`#44內容一致、holdout未受影響）後補齊第88輪缺漏`US_LOG.md`記錄＋心跳＋完成收工程序（commit+push） · 沿用第88輪判定：FAIL不變，本輪無新增假說測試

## 第 88 輪 · 2026-08-26 07:05 · US · `f_us_momentum_12m`（US軌第二個因子，12-1動能，Jegadeesh-Titman經典定義）1a便宜關卡測試（`us_factor_ic.py`沿用`f_us_low_vol`的`evaluate_factor()`框架，同一批27/40可用隨機樣本） · **FAIL**（TRAIN mean_ic=−0.0129/VAL mean_ic=+0.0613方向不一致，null percentile=94.6單測本身有過但same_sign檢查未過，不進深挖，`TRIALS_LEDGER.md`#44）

## 第 87 輪 · 2026-08-26 06:31 · FUT · 取鎖時偵測到`LOCK_STALE`（pid 140656持有30.0分鐘，上一輪疑似異常中止——`MARATHON_STATE.md`計數器已改86，但`REPORT.md`缺第86輪心跳條目，判斷是死在寫心跳這一步）；核實其留下的孤兒工作（`deep_dive_fut_basis_mean_reversion_60d.py`＋`FUT_LEADS.md`/`FUT_LOG.md`/`TRIALS_LEDGER.md`#43內容一致、holdout未受影響）後補齊第86輪缺漏心跳＋完成收工程序（commit+push） · 沿用第86輪判定：EXPERIMENTAL不變，本輪無新增假說測試

## 第 86 輪 · 2026-08-26 06:20 · FUT · `fut_basis_mean_reversion_60d`(#19)深挖(1b) · **EXPERIMENTAL**（VAL期贏隨機控制組中位數但未達單測門檻(83.5<90.0)、beta近零(0.0286，優於`fut_basis_carry`的0.36)、但LOYO集中度問題跟`fut_basis_carry`相近，介於乾淨PASS跟深挖FAIL之間），排入`TRIALS_LEDGER.md`#43

## 第 85 輪 · 2026-08-26 05:49 · TW · 執行互動session寫好未跑的`deep_dive_f_value_pb.py`（`f_value_pb`#1的1b深挖），61/80快取樣本零新API · **EXPERIMENTAL**：VAL(2021-2024)對配對式隨機控制組穩健勝出(99.0/100.0/100.0百分位)、TRAIN(2015-2020)較弱(88.0/96.0/97.0)，但絕對報酬train/val正負號不一致（TRAIN全負/VAL全正），跟`f_quality_roe_stability`同款模式第三例，證據比ROE更弱，未升格PASS（`TRIALS_LEDGER.md`#42）

## 第 84 輪 · 2026-08-26 05:02 · US · 取鎖時偵測到`LOCK_STALE`（pid 141036，29.9分鐘）——接手其留下的孤兒工作（`deep_dive_f_us_low_vol.py`＋`US_LEADS.md`/`TRIALS_LEDGER.md`已完成但未收工的1b深挖分析），核實後補齊`US_LOG.md`/`US_MARATHON_STATE.md`並收工 · `f_us_low_vol`深挖**FAIL**（TRAIN期對隨機控制組僅41-48百分位、VAL期beta驟降至−0.891暗示方向性曝險非橫斷面優勢），#39的CHEAP_PASS判定降級，US軌待深挖清單清空（TRIALS_LEDGER.md#41）

## 第 83 輪 · 2026-08-26 04:17 · TW · 執行互動session寫好但未跑的`regime_switch_f_rel_strength.py`（大盤位階開關+相對強度十分位多空策略），完成`f_rel_strength`情境切換候選的策略層深挖 · **FAIL**——TRAIN期三成本情境全負報酬/負alpha/負Sortino，VAL期對成本高度敏感，兩期對隨機控制組均僅84~94百分位（未達其他TW候選慣見99~100門檻），排入`TW_LEADS.md`#4/`TRIALS_LEDGER.md`#40；本輪commit刻意排除互動session其餘未commit的App/資料源架構變更
## 第 82 輪 · 2026-08-26 03:35 · US · 取鎖時偵測到LOCK_STALE（上一輪疑似異常中止）；TW軌仍有未commit互動session變更延續前例跳過不動；重跑`us_factor_ic.py`（第81輪的IP封鎖已解除）· `f_us_low_vol`第一次真正完成便宜關卡IC測試，**CHEAP_PASS**（percentile=100.0，US軌至今第一個通過便宜關卡的因子），排入待深挖清單
## 第 81 輪 · 2026-08-26 02:35 · US · 取鎖乾淨成功；TW軌有未commit互動session變更，延續第80輪判斷跳過不動；新寫`us_factor_ic.py`嘗試跑`f_us_low_vol`第一次1a便宜關卡IC測試 · 40檔隨機樣本全部撞FinMind IP封鎖（403 ip banned，非單純402），0/40可用樣本無法測試——資料可用性發現非因子判定；順手修好早停偵測沒接住403格式的bug（原本只認402/429，浪費39次多餘呼叫）
## 第 80 輪 · 2026-08-26 02:05 · FUT · 取鎖偵測到LOCK_STALE（上一輪疑似異常中止）；basis家族第三個假說`fut_basis_mean_reversion_60d`便宜關卡測試 · CHEAP_PASS（percentile=100.0），但跟`fut_basis_carry`同款極端放大模式，待深挖時需train/val切分優先驗證

## 第 79 輪 · 2026-08-26 01:03 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊但依裁示FUT佔比上限20%跳過，US次舊；依使用者「美股軌可以開始建因子管線」裁示，新寫`us_factors.py`第一版（僅一個純價格因子`f_us_low_vol`，跟TW版`f_low_vol`定義/窗口對齊，刻意不碰PIT）· 屬協定1c地基建設非1a假說測試。取鎖後撞FinMind 402（額度被TW軌用光），改用AAPL/MSFT既有快取檔完成smoke test零新增API呼叫，兩檔各8817列，warm-up 60列NaN符合預期，數值範圍合理。地基缺口全補齊（universe/pit/costs/factors都有第一版），下一輪候選：對`f_us_low_vol`跑第一個1a便宜關卡IC測試

## 第 78 輪 · 2026-08-26 00:36 · TW · 取鎖時偵測到`LOCK_STALE`（pid 132048持有30.1分鐘，**上一輪疑似異常中止**，未留下任何log）；三軌時間戳比對FUT最舊但依使用者裁示FUT軌佔比上限20%、選輪次時TW/US優先，改選次舊的TW；全市場宇宙回補第二十四批 · 本批嘗試137檔，新完成100/新跳過22，撞限流牆提前停止（設計內行為），累積覆蓋率1819→1919/3196（56.9%→60.0%），仍低於80%門檻

## 第 77 輪 · 2026-08-25 22:31 · US · 取鎖時偵測到`LOCK_STALE`（pid 131600持有60.1分鐘，**上一輪疑似異常中止**，未留下任何log，遺留未提交/未執行的`sec_edgar_filer_category_infer.py`）；接手完成第12項子步驟(b)(c)——filer category反推分類器實測+PLTR重測 · **第12項結案，負向結果**：AAPL/MSFT/PLTR全部財年分類`LAF`，PLTR跟`era_reliability()`既有的全市場LAF假設完全一致沒有分歧，代表第65輪PLTR 14/24 gap誤判不是filer category誤判造成的，真正原因未知；建議不再投入輪次救這條路（`DATA.md`「五續」、`US_LOG.md`本輪記錄）

## 第 76 輪 · 2026-08-25 21:05 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；全市場宇宙回補第二十三批 · 本批嘗試104檔，新完成76/新跳過13，撞限流牆提前停止（設計內行為），累積覆蓋率1743→1819/3196（54.5%→56.9%），仍低於80%門檻

## 第 75 輪 · 2026-08-25 20:36 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；`fut_basis_carry`深挖（1b），`deep_dive_fut_basis_carry.py`新增，四項檢查（train/val切分/leave-one-year-out/成本敏感度/beta對照） · **深挖FAIL**：val期percentile=46.0連隨機控制組都沒贏過，717x終值85%集中在2000-2002三年，beta=0.36非市場中性，第72輪CHEAP_PASS降級為FAIL不進候選清單（`TRIALS_LEDGER.md`#37、`FUT_LEADS.md`#17）

## 第 74 輪 · 2026-08-25 20:10 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；第12項子步驟(a)——WebSearch查證SEC accelerated/large accelerated filer公眾流通市值門檻歷史時間表 · 查到五個節點都附官方文件連結（2005 Release33-8644新增LAF、2020 Release34-88365調高exit門檻並新增營收測試、2026提案中尚未生效），發現反推邏輯複雜度主要在2020年營收測試而非門檻數字變動，子步驟(a)完成，(b)(c)留下一輪

## 第 73 輪 · 2026-08-25 19:35 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；全市場宇宙回補第二十二批 · 本批嘗試130檔，新完成78/新跳過8，撞限流牆提前停止（設計內行為），累積覆蓋率1665→1743/3196（52.1%→54.5%），仍低於80%門檻

## 第 72 輪 · 2026-08-25 19:05 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；basis家族第一批假說（水位carry+5日變化動能） · `fut_basis_carry`全通過單測/批次/累積校正三層便宜關卡，**期貨軌至今第一個乾淨全通過的候選**（終值717x極端，已排除純漂移artifact但保留「可能被少數大事件年份主導」警語，深挖時walk-forward優先驗證）；`fut_basis_change_momentum_5d`清楚FAIL（percentile 0.0）

## 第 71 輪 · 2026-08-25 18:33 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；探測`era_reliability()`個股逐年申報人分級資料（第12項） · `submissions`頂層`category`只是今天快照（不可用）；XBRL`EntityPublicFloat`確有逐年資料但門檻歷史表/反推邏輯未做，問題從「完全開放」推進到「有候選路徑」，未完全解決

## 第 70 輪 · 2026-08-25 18:05 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；全市場宇宙回補第二十一批 · 本批嘗試109檔，新完成76/新跳過18，撞限流牆提前停止（設計內行為），累積覆蓋率1589→1665/3196（49.7%→52.1%），仍低於80%門檻

## 第 69 輪 · 2026-08-25 17:34 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；basis家族地基第二步，`fut_basis_series.py`近月期貨×TAIEX現貨join算basis序列；意外撞到並修復`validation/holdout.py`的pandas 3.0.5相容性bug · 完成，join覆蓋率100%（6185/6185），basis分布合理（均值貼水-0.2%，唯二極端值在2008金融海嘯期間）；holdout.py修法是型態正規化（`Timestamp`統一轉型再比較），已smoke test驗證不影響既有字串dtype呼叫者、真實洩漏情境仍正確raise；地基工作非假說測試，未加`TRIALS_LEDGER.md`列

## 第 68 輪 · 2026-08-25 17:02 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；新寫美股成本模型`validation/us_costs.py`（`US_MARATHON_STATE.md`第8項） · 完成，SEC Section 31 fee+FINRA TAF兩監管費用WebSearch查證（$20.60/百萬美元、$0.000195/股），零售手續費預設$0，smoke test通過；誠實揭露費率僅當下快照未查證歷史範圍；地基工作非假說測試，未加`TRIALS_LEDGER.md`列

## 第 67 輪 · 2026-08-25 16:35 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；全市場宇宙回補第二十批 · 本批嘗試102檔，新完成73/新跳過14，撞限流牆提前停止（設計內行為），累積覆蓋率1516→1589/3196（47.4%→49.7%，已過半），仍低於80%門檻

## 第 66 輪 · 2026-08-25 16:04 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；basis家族地基第一步，確認TAIEX現貨指數資料源 · 完成，新增`fut_probe_spot_index.py`，實測3個FinMind候選（不採信兩次互相矛盾的WebSearch/WebFetch文件摘要）：`TaiwanStockPrice`/`TAIEX`是正解（全歷史6185列乾淨無異常，列數跟期貨連續序列樣本天數一致），排除`TaiwanVariousIndicators5Seconds`（不支援多日查詢）跟`TaiwanStockTotalReturnIndex`（回傳報酬指數非現貨價）；地基探測非假說測試，未加`TRIALS_LEDGER.md`列

## 第 65 輪 · 2026-08-25 15:34 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；`us_pit.py`接上`full_history`參數＋新增分期PIT reliability標記`era_reliability()`（`US_MARATHON_STATE.md`第11項） · 完成，門檻用WebSearch查證的SEC真實加速申報人分期時間表；smoke test實測AAPL/MSFT可信（超標率4%/1.5%）但PLTR不可信（58%超標，近期IPO股身分未知的已知限制被實測證實），已記錄新開放問題（第12項），地基工作非假說測試，`TRIALS_LEDGER.md`加一列非試驗調查記錄

## 第 64 輪 · 2026-08-25 15:13 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；全市場宇宙回補第十九批 · 本批嘗試110檔，新完成77/新跳過13，撞限流牆提前停止（設計內行為），累積覆蓋率1439→1516/3196（45.0%→47.4%），仍低於80%門檻

## 第 63 輪 · 2026-08-25 14:32 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；驗證夜盤`date`欄位時序假設（第60輪留下的未解決風險） · 完成，新增`fut_verify_night_session_timing.py`，用session邊界價格gap比對，證實night(T)實際落在day(T-1)與day(T)之間（不是原本直覺猜測的day(T)/day(T+1)之間），H_B在兩個邊界、多數列、mean/median全部一致支持，gap幅度明顯小於H_A且小於同日盤中波動，判定明確不模糊；地基探測非假說測試，未加`TRIALS_LEDGER.md`列

## 第 62 輪 · 2026-08-25 14:02 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；`sec_edgar_client.py`的`get_filing_dates()`新增`full_history=True`，分頁抓`filings.files[]` archive pointers（`US_MARATHON_STATE.md`第10項） · 完成，AAPL/MSFT視窗深度從2015/2020延伸到1994年理論上限，PLTR不變（無archive可分頁，符合預期）；新發現歷史filing gap上限比近年寬很多（AAPL 37→181天、MSFT 30→91天），未查證原因；`us_pit.py`尚未接上新參數，留給下一輪

## 第 61 輪 · 2026-08-25 13:34 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；覆蓋率42.8%仍遠低於80%門檻，跑`backfill_universe.py --batch-size 300`第十八批 · 本批嘗試103檔，新完成70/新跳過18，撞限流牆提前停止（設計內行為），累積覆蓋率1369→1439/3196（42.8%→45.0%）

## 第 60 輪 · 2026-08-25 13:03 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；接手盤別效應家族地基第一步，新寫`fut_probe_night_session.py`探測`after_market`夜盤原始資料形狀（零額外API呼叫） · 確認settlement_price/open_interest全歷史恆為0（升級自一個月樣本推論）、首日跟TAIFEX夜盤上線日只差一天；**發現關鍵未解決風險：夜盤date欄位代表的交易時段先後順序尚未驗證**，下一輪動`continuous_contract.py`前必須先確認，避免報酬方向顛倒

## 第 59 輪 · 2026-08-25 12:32 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；新寫`us_pit.py`（美股版PIT對齊，`US_MARATHON_STATE.md`第7項），用`sec_edgar_client.get_filing_dates()`真實filingDate建構`filing_pit()` · 完成，`pit_source`固定'real'；smoke test發現`filings.recent`視窗深度對長年掛牌股比理論上限淺很多（AAPL僅回溯2015-06、MSFT僅回溯2020-06），新增`coverage_probe()`診斷函式；刻意未套用pre-XBRL缺口flag（記錄為開放方法論問題，非漏做）

## 第 58 輪 · 2026-08-25 12:04 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；覆蓋率40.5%仍遠低於80%門檻，跑`backfill_universe.py --batch-size 300`第十七批 · 本批嘗試103檔，新完成74/新跳過14，撞限流牆提前停止（設計內行為），累積覆蓋率1295→1369/3196（40.5%→42.8%）

## 第 57 輪 · 2026-08-25 11:33 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；對`fut_intraday_gap_continuation`（第54輪percentile=92.0）做高解析度重測（N_SHUFFLES 200→2000，同第51輪先例） · percentile 89.60，跌破單測門檻90.0本身（不是逼近門檻，是明確下降），確認原本讀數偏高估；日內均值回歸家族第一批（反轉+順勢）完全結案，0 PASS

## 第 56 輪 · 2026-08-25 11:02 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；新寫`us_universe.py`（「下一輪建議工作單位」第6項） · 現存快照+手動維護5檔已驗證下市股合併成`universe()`，明確加`bias_correction`欄位標註非完整存活者偏差修正；驗證跑通6623列，5檔delisted全部正確保留，零額度消耗（沒打新API）

## 第 55 輪 · 2026-08-25 10:31 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；覆蓋率38.2%仍遠低於80%門檻，跑`backfill_universe.py --batch-size 300`第十六批 · 本批嘗試117檔，新完成74/新跳過22，撞限流牆提前停止（設計內行為），累積覆蓋率1221→1295/3196（38.2%→40.5%）

## 第 54 輪 · 2026-08-25 10:05 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；三大法人期貨部位家族結案後換日內均值回歸家族，地基確認不需要新資料源（`adj_open`現成），測隔夜跳空反轉/順勢兩個相反方向假說 · 反轉FAIL（percentile=8.0，方向嚴重不對）；順勢單測過(92.0)但未過本批次n=2校正門檻95.0，弱CHEAP_PASS不排入深挖清單

## 第 53 輪 · 2026-08-25 09:33 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；例行檢查發現孤兒未追蹤檔案`us_delisting_client.py`（某異常中止輪次的殘留產物，從未寫log/commit） · 驗證smoke test時發現分類邏輯bug（Form25/Form15混算導致正常下市誤判為「多重事件」），修復後5檔已知案例全部正確，正式納入版本控制

## 第 52 輪 · 2026-08-25 09:03 · TW · 偵測到`LOCK_STALE`（上一輪pid 128940疑似失敗，鎖held 30.0分鐘後被回收）；三軌時間戳比對TW最舊；覆蓋率35.9%仍遠低於80%門檻，跑`backfill_universe.py --batch-size 300`第十五批 · 本批嘗試109檔，新完成73/新跳過21，撞限流牆提前停止（設計內行為），累積覆蓋率1148→1221/3196（35.9%→38.2%）

## 第 51 輪 · 2026-08-25 08:32 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；高解析度重測`fut_inst_foreign/trust_net_position_change_5d`（N_SHUFFLES 200→2000） · 兩者percentile 97.40/97.80，都清楚低於n=31累積校正門檻99.68，確認非解析度問題、確定沒過；三大法人期貨部位家族（6假說）完全結案，0 PASS

## 第 50 輪 · 2026-08-25 08:02 · US · 偵測到`LOCK_STALE`（上一輪pid 57480疑似失敗，鎖held 30分鐘後被回收）；三軌時間戳比對US最舊；`us_probe_price_depth_smallmid.py`第四次嘗試（前三次都被FinMind 402擋掉） · 額度已恢復，10檔中小型股/近期IPO股全部測完無限流，日期缺口/首末日全部正常，里程碑1資料品質疑慮初步驗證通過；US軌「下一輪建議工作單位」第1–5項全部完成

## 第 49 輪 · 2026-08-25 07:05 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊；覆蓋率33.5%仍遠低於80%門檻，跑`backfill_universe.py --batch-size 300`第十四批 · 本批嘗試130檔，新完成78/新跳過21，撞限流牆提前停止（設計內行為），累積覆蓋率1070→1148/3196（33.5%→35.9%）

## 第 48 輪 · 2026-08-25 06:35 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊；三大法人期貨部位家族最後一個類別（自營商）水位/動能各測1個 · 兩個都FAIL（percentile=42.5/25.0），跟外資/投信的動能版「批次過但累積校正未過」不同，自營商動能連批次都沒過；家族6假說全測完（4 FAIL+2不確定+0 PASS），沒有候選進入深挖清單

## 第 47 輪 · 2026-08-25 06:04 · US · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對US最舊；TW第46輪剛用完FinMind額度，跳過需額度的第4項，改接FDIC查詢邏輯包裝成可重用模組`fdic_client.py` · smoke test跟第44輪SBNY手動查詢一致，並解出第44輪留下的開放問題（FRC的FDIC CERT=59017）；過程中發現WebFetch摘要JSON會拉平API真實巢狀結構的方法論陷阱，已修正並記錄

## 第 46 輪 · 2026-08-25 05:37 · TW · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對TW最舊，全市場宇宙回補第十三批（`backfill_universe.py --batch-size 300`） · 本批嘗試105檔，新完成78/新跳過9，撞限流牆提前停止；累積覆蓋率992→1070/3196（31.0%→33.5%），仍低於80%門檻

## 第 45 輪 · 2026-08-25 05:02 · FUT · 取鎖乾淨成功（無陳舊鎖檔），三軌時間戳比對FUT最舊，接手三大法人期貨部位家族第二個類別（投信）水位/動能各測1個 · `fut_inst_trust_net_position_sign`（水位）FAIL（percentile 41.5，方向不對）；`fut_inst_trust_net_position_change_5d`（動能）批次過（96.5）但累積校正（n=27門檻99.63）後不確定，不排入深挖——跟外資動能假說（#25）同款模式，連續兩類別出現同樣現象值得留意但未下結論

## 第 44 輪 · 2026-08-25 04:31 · US · 原計畫接第4項（中小型股價格深度抽測）第一檔（XPER）又撞402（TW第43輪回補後4.5小時額度仍未恢復），優雅換方向接第2項 · 用FDIC BankFind Suite公開REST API（`api.fdic.gov`）獨立確認SBNY=Signature Bank（CERT 57053，2023-03-12倒閉，`RESTYPE=FAILURE`），跟第41輪SEC EDGAR側「第12(i)條銀行不歸SEC管」推論互相印證，原規劃的`efr.fdic.gov`逆向工程待辦可放棄

## 第 43 輪 · 2026-08-25 00:00 · TW · 取鎖時偵測到`LOCK_STALE`（上一輪pid 100692持有鎖滿300.1分鐘後被回收，疑似異常中止），全市場宇宙回補第十二批（`backfill_universe.py --batch-size 300`） · 本批嘗試109檔，新完成74/新跳過20，撞限流牆提前停止；累積覆蓋率918→992/3196（28.7%→31.0%），仍低於80%門檻（偵測到上一輪陳舊鎖檔，上一輪疑似失敗）

## 第 42 輪 · 2026-08-24 23:03 · FUT · 三大法人期貨部位第一批假說測試（外資水位/動能各1個，沿用第39輪地基）· `fut_inst_foreign_net_position_sign` FAIL（percentile 57.5）；`fut_inst_foreign_net_position_change_5d` 批次過（97.0）但累積校正後不確定，不排入深挖（**此筆為第43輪回溯補寫**：本輪確有實質進度且已寫入`FUT_MARATHON_STATE.md`/`FUT_LOG.md`/`FUT_LEADS.md`/`TRIALS_LEDGER.md`，但當時未留下心跳記錄即中止，直到第43輪取鎖時發現陳舊鎖檔才回填，內容來源為`FUT_MARATHON_STATE.md`第42輪段落）

## 第 41 輪 · 2026-08-24 22:37 · US · 找到FRC/SBNY查不到SEC CIK的根本原因（第12(i)條銀行申報主管機關規則）·  這類州立非聯準會會員銀行本來就不歸SEC EDGAR管、直接向FDIC申報，一次解釋第4–7輪所有異常，第六輪「FDIC接管型不走Form 25」假設應直接退役

## 第 40 輪 · 2026-08-24 22:01 · TW · 全市場宇宙回補第十一批（`backfill_universe.py --batch-size 300`）（偵測到上一輪陳舊鎖檔，上一輪疑似失敗） · 本批嘗試100檔，新完成72/新跳過13，撞限流牆提前停止；累積覆蓋率846→918/3196（26.5%→28.7%），仍低於80%門檻

## 第 39 輪 · 2026-08-24 21:19 · FUT · 取鎖乾淨成功，三大法人期貨部位地基探測（`fut_probe_institutional_positions.py`） · 資料集乾淨可用但發現全歷史範圍實際只從2018-06-05起有資料（1605/6191天，26%覆蓋率），跟聚合OI交叉核對初看異常追查後確認是方法論落差非資料問題

## 第 38 輪 · 2026-08-24 07:31 · US · 取鎖乾淨成功，第4項（價格深度抽測）第一檔又立刻撞402（同小時內TW回補用光額度），優雅換方向改做第5項 · 新增可重用模組`sec_edgar_client.py`，smoke test數字跟原探測腳本一致，驗證重構未改變邏輯

## 第 37 輪 · 2026-08-24 07:06 · TW · 取鎖乾淨成功，全市場宇宙回補第十批（`backfill_universe.py --batch-size 300`） · 本批嘗試109檔，新完成75/新跳過12，撞限流牆提前停止；累積覆蓋率771→846/3196（24.1%→26.5%），仍低於80%門檻

## 第 36 輪 · 2026-08-24 06:34 · FUT · 取鎖乾淨成功，換家族第一批：籌碼面`fut_oi_price_confirm_5d`（OI確認）+季節性`fut_weekday_effect`（週一效應）各測1個 · 兩個都FAIL（percentile 62.0/13.5，門檻90.0），累計6個假說全FAIL，剩餘候選家族都需先做小型地基工作

## 第 35 輪 · 2026-08-24 06:02 · US · 取鎖乾淨成功，接「中小型股/近期IPO USStockPrice深度抽測」工作單位，新寫`us_probe_price_depth_smallmid.py` · 第一檔就撞FinMind 402額度牆（被前幾輪台股回補用光），零檔測到，優雅收工；腳本已就緒待下輪額度恢復後直接跑

## 第 34 輪 · 2026-08-24 05:35 · TW · 全市場宇宙回補第九批（`backfill_universe.py --batch-size 300`，取鎖乾淨成功） · 本批嘗試120檔，新完成75/新跳過21，撞限流牆提前停止；累積覆蓋率696→771/3196（21.8%→24.1%），仍低於80%門檻

## 第 33 輪 · 2026-08-24 05:03 · FUT · 取鎖時偵測到`LOCK_STALE`（上一輪已完成2個假說測試但未收尾就中止，未commit），接手收尾並多測2個假說（均線交叉、波動regime過濾變體） · 4個技術訊號家族（動能多數決/通道突破/均線交叉/regime過濾變體）全部FAIL，`TRIALS_LEDGER.md`#18–#21，建議下一輪換方向（日內均值回歸/期現價差/籌碼面）（偵測到上一輪陳舊鎖檔，上一輪疑似失敗）

## 第 32 輪 · 2026-08-24 04:05 · US · XBRL company facts 修正後 gap 統計重算（同一end取最小filed去重） · 中位數大幅改善貼近submissions API水準，但發現兩類無法去重消除的殘留離群值（pre-XBRL標記缺口、pre-IPO歷史資料），細節見DATA.md/US_MARATHON_STATE.md/US_LOG.md

---

## 第 31 輪 · 2026-08-24 03:36 · TW · 取鎖乾淨成功（第30輪正常結束，非stale），全市場宇宙回補第七批（`backfill_universe.py --batch-size 300`） · 本批嘗試104檔，新完成70/新跳過19，因限流提前中止（設計內行為）；累積覆蓋率626→696/3196（19.6%→21.8%），仍遠低於80%門檻

## 第 30 輪 · 2026-08-24 03:01 · FUT · 累積漂移幅度實測（`fut_drift_probe.py`，比價法連續合約 vs 真實現價） · 樣本起點漂移-70.4%（比原假設嚴重很多，逐年單調收斂到0），但逐日核對證實報酬率本身未受污染（非轉倉日差異天數=0）；期貨軌地基完備，下一輪可開始測因子/策略

## 第 29 輪 · 2026-08-24 02:35 · TW · 取鎖時偵測到`LOCK_STALE`（第28輪之後某一輪疑似無輸出中止，未留下任何log，同第13/14/25/27輪失敗模式再現），全市場宇宙回補第六批（`backfill_universe.py --batch-size 300`） · 本批嘗試78檔（15檔重複資料，實際新處理63檔），新完成57/新跳過6，因限流提前中止（設計內行為）；累積覆蓋率569→626/3196（17.8%→19.6%），仍遠低於80%門檻（偵測到上一輪陳舊鎖檔，上一輪疑似失敗）

## 第 28 輪 · 2026-08-24 00:34 · TW · 取鎖時偵測到`LOCK_STALE`（第27輪鎖檔持有滿60分鐘後被回收，第27輪疑似無輸出中止，未留下任何log內容，同第13/14/25輪失敗模式再現），全市場宇宙回補第五批（`backfill_universe.py --batch-size 300`） · 本批嘗試101檔，新完成60/新跳過13，因限流提前中止（設計內行為）；累積覆蓋率509→569/3196（15.9%→17.8%），仍遠低於80%門檻

## 第 27 輪 · 2026-08-23 23:30 · 未知（沒有留下任何內容可判斷） · 這輪從觸發到結束沒有寫出任何一個字，`schtasks` 查證確實真的觸發過（`Last Run Time` 對得上）也確實真的已經結束（`Last Result` 已經是終止代碼，不是「執行中」的特殊值）· **無輸出／行程疑似被中止**（同第 13/14/25 輪的失敗模式，第 4 次出現；此筆是使用者這輪要求即時診斷時、用 `schtasks`／Windows 事件記錄手動查證後回填的，不是下一輪自動偵測到的——本輪本身沒有留下鎖檔陳舊痕跡給下一輪偵測，因為診斷當下鎖檔還沒過 25 分鐘陳舊門檻。完整鑑識細節見下方新增的診斷條目）

## 第 26 輪 · 2026-08-23 23:03 · TW · 取鎖時偵測到`LOCK_STALE`（第25輪陳舊鎖檔被回收，上一輪疑似失敗），全市場宇宙回補第四批（`backfill_universe.py --batch-size 300`） · 本批嘗試51檔，新完成31/新跳過5，因限流提前中止（設計內行為）；累積覆蓋率449→480/3196（14.1%→15.0%），仍遠低於80%門檻

## 第 25 輪 · 2026-08-23 22:30 · 未知（沒有留下任何內容可判斷） · 這輪從觸發到結束沒有寫出任何一個字——連 `marathon_cycle.log` 都只有開始時間戳、沒有內容、沒有結束時間戳 · **無輸出／行程疑似被中止**（Windows 工作排程器回報結束代碼 `STATUS_CONTROL_C_EXIT`，不是崩潰；鎖檔留下沒釋放，但 25 分鐘後會被下一輪自動判定陳舊並回收，不會永久卡死。完整診斷見下方 2026-08-23T22:46 條目）

## 第 24 輪 · 2026-08-23 22:00 · US · XBRL company facts API（SEC EDGAR）實測，探索比 TW 的「+45 天」更精準的 PIT 對齊方式 · 發現 `filed`/`end` 欄位在部分申報裡有「比較期重複揭露」陷阱（772/1034 筆需要進一步處理），已記錄尚未解決，PENDING

## 第 23 輪 · 2026-08-23 21:30 · FUT · `continuous_contract.py` 連續合約建構程式碼首版（比價法銜接 + H1 轉倉規則），對 2000–2024 全部 300 次月轉倉跑過 · 程式碼完成，尚未對照其他銜接方法做敏感度分析（留給下一輪）

## 第 22 輪 · 2026-08-23 21:00 · TW · 全市場宇宙回補第三批（`backfill_universe.py`） · 覆蓋率 336/3196（10.5%）→ 408/3196（12.8%），未達 80% 門檻，持續回補

## 第 21 輪 · 2026-08-23 20:30 · US · 重查 FRC（First Republic Bank）SEC CIK · 發現沿用到現在的 CIK（1132979）幾乎確定是錯的實體（全是 13G 申報、零 10-K/10-Q/8-K，不像銀行控股公司），正確 CIK 三種方法都沒查到，懸而未決；FDIC接管下市不走標準 Form 25 的假說因此被削弱

## 第 20 輪 · 2026-08-23 20:00 · FUT · 用既有快取驗證連續合約轉倉時點規則（H1 vs H2），零額外 API 呼叫 · 2000–2024 全部 300 次月轉倉都確認 H1（結算日轉倉）成立

## 第 19 輪 · 2026-08-23 19:30 · TW · 全市場宇宙回補第二批 · 覆蓋率 262/3196（8.2%）→ 336/3196（10.5%），未達 80% 門檻

## 第 18 輪 · 2026-08-23 19:00 · US · 第六輪重查 Signature Bank（SBNY）正確 SEC CIK（三種方法：公司名瀏覽、全文檢索、窮舉掃描 2023/3–6月全部 Form 25-NSE） · 正確 CIK 仍未找到，但排除了兩個先前用過的錯誤候選，並修正探測腳本一個有瑕疵的假設

## 第 17 輪 · 2026-08-23 18:30 · FUT · 查證 `institutional_investors` 欄位「亂碼」疑慮 · 確認是 Windows 主控台顯示層假象（原始 FinMind 回應本身是正確的 ASCII-safe `\uXXXX` JSON escape），不是真的資料/編碼 bug，不需要改 `finmind_client.py`

## 第 16 輪 · 2026-08-23 18:00 · US · 用 SEC EDGAR Form 25 申報獨立核實上一輪 5 檔已知下市股（TWTR/SIVB/SBNY/FRC/BBBY） · TWTR、SIVB 確認真下市；BBBY 代號重用獨立證實（連 SEC 自己的現行代號對照表都指向錯誤公司）；SBNY 的備援 CIK 查出是錯的；FRC 懸而未決

## 第 15 輪 · 2026-08-23 17:30 · TW · 全市場宇宙回補第一批 · 覆蓋率 199/3196（6.2%）→ 262/3196（8.2%），未達 80% 門檻

## 第 14 輪 · 2026-08-23 17:00 · 未知（沒有留下任何內容可判斷） · 這輪從觸發到結束沒有寫出任何一個字 · **無輸出／行程疑似被中止**（同第 13 輪，完整診斷見下方 2026-08-23T22:46 條目）

## 第 13 輪 · 2026-08-23 16:30 · 未知（沒有留下任何內容可判斷） · 這輪從觸發到結束沒有寫出任何一個字 · **無輸出／行程疑似被中止**（完整診斷見下方 2026-08-23T22:46 條目——這個時段跟使用者互動 session 正在做兩輪高強度 Cowork 覆核回應重疊，高度懷疑是資源競爭，證據不完整）

## 第 12 輪 · 2026-08-23 16:00 · FUT · 解開上一輪 `settlement_price`/`open_interest` 全零疑慮 · 確認這兩個欄位只在 `trading_session == "position"`（盤後結算快照）才有值，`after_market` 場次本來就是空的，篩 session 即可用，不是資料源壞掉

## 第 11 輪 · 2026-08-23 15:30 · US · 用 5 檔已知下市股（TWTR/SIVB/SBNY/FRC/BBBY）測試存活者偏差處理方法 · TW 那套「價格列存在與否」判斷法、跟 `USStockInfo` 快照比對法，兩種在美股都不可靠，誠實記錄負面結果

## 第 10 輪 · 2026-08-23 15:00 · TW · `f_value_pb`/`f_value_pe` 的 PIT（point-in-time）前置驗證（`verify_pit_value_pb.py`，用 2330 全部 42 筆歷史事件核對隱含每股淨值） · 40/42 筆對得上，PIT 正確性確認站得住腳

## 第 9 輪 · 2026-08-23 14:30 · FUT · FinMind IP 封鎖解除，重測期貨資料源 · `TaiwanFuturesDaily`／`TaiwanFuturesInstitutionalInvestors` 確認可用（2000–2024），同時誠實記下兩個待解欄位品質問題（settlement_price/open_interest 疑似全零、法人分類疑似亂碼）留給下一輪

## 第 8 輪 · 2026-08-23 14:00 · US · SEC EDGAR submissions API 從「只查文件」升級成「用 AAPL/MSFT/PLTR 實測驗證」 · `filingDate`/`reportDate` 欄位確認真實可用，且發現揭露延遲因公司而異（PLTR 34–37天 vs AAPL/MSFT 約25–27天）

## 第 7 輪 · 2026-08-23 13:30 · TW · 加密 `f_quality_roe_stability` 隨機控制組解析度（`N_RANDOM_DRAWS` 20→100） · 6 組設定全部仍打贏全部 100 次隨機抽樣（p<0.01），解決上一輪「解析度太粗」的限制，判定維持 `EXPERIMENTAL`

## 第 6 輪 · 2026-08-23 13:00 · FUT · 再次嘗試期貨資料探測 · 第一次呼叫就撞到新的 FinMind IP 封鎖（403），寫好下一輪可直接執行的探測腳本，記錄封鎖可能會重複延長、不是打完一次就一定解除

## 第 5 輪 · 2026-08-23 12:30 · US · 調查 SEC EDGAR 公開申報 API 是否能提供比 TW「+45天」更精準的 PIT 對齊 · 確認文件上 `filingDate`/`reportDate` 兩個獨立欄位存在（這輪只查文件，沒有實際打 API），下一輪要實測

## 第 4 輪 · 2026-08-23 12:00 · TW · 深挖 `f_quality_roe_stability`（decile 多空） · TRAIN/VAL 各測 1x/2x/3x 成本，beta 對照顯示接近 market-neutral，但 TRAIN/VAL 報酬正負號不一致，判定 `EXPERIMENTAL`（不是 `PASS`），誠實記錄矛盾未解決

## 第 3 輪 · 2026-08-23 11:30 · FUT · 連續合約銜接方法設計決策 · FinMind 期貨資料一開始撞到 403 IP 封鎖，改用既有快取資料完成設計（比價法 + 保留原始價格），寫進 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`；工作單位邊界外順手發現 repo 裡有未 commit 的其他人（互動 session）修改，誠實記錄看到但沒有動它

## 第 2 輪 · 2026-08-23 11:11 · US · US 軌地基探測：`USStockPrice`/`USStockInfo` 歷史深度、更新頻率、代號覆蓋 · 記錄進 `DATA.md`/`US_LOG.md`，建議下一輪接續存活者偏差或 SEC EDGAR PIT 或擴大價格深度抽樣

## 第 1 輪 · 2026-08-23 09:47 · TW · 重測 `f_value_pb`/`f_value_pe`/`f_quality_roe_stability` 便宜關卡（含累積 Bonferroni 校正，n=15） · `f_value_pb`、`f_quality_roe_stability` PASS；`f_value_pe` 批次內過關但累積校正後誠實降級

---

## 2026-08-22T11:00:00+08:00 — 建立檔案紀律本身（REPORT / LEADS / MARATHON_STATE / audit_ledgers.py）

**做了什麼：** 依使用者指示，把「session 是消耗品，檔案才是本體」的紀律正式建成四樣東西：
- 本檔案（`REPORT.md`）
- `LEADS.md`：策略候選登記簿，目前是空的（還沒有策略候選——里程碑 2 驗證框架都還沒接成能跑的骨架，鐵律規定框架完成前不挖策略）
- `MARATHON_STATE.md`：斷點狀態檔，內容是這個時間點專案的完整快照
- `audit_ledgers.py`：唯讀稽核腳本，目前有 2 條恆等式（每個平倉都有對應進場記錄、沒有 NaN 價格/股數），對著空的 `trades.csv`（還沒有任何交易，schema 先定義好）跑，全部 PASS（因為沒資料可違反，不是因為邏輯有問題——已用合成的壞資料手動驗證過這兩條檢查真的抓得到問題）。

**驗證結果：**
- `audit_ledgers.py` 對空 ledger 跑：兩條檢查都 PASS，0 筆交易。
- 用合成資料驗證檢查邏輯本身有效：故意造一筆「平倉但 entry_trade_id 指到不存在的 trade_id」的假資料，`check_every_position_has_entry` 正確抓到；故意造一筆 `price=NaN` 的假資料，`check_no_nan_prices` 正確抓到。（驗證腳本跑完即丟棄，沒有寫進 `trades.csv`，維持 ledger 乾淨。）

**下一步：** 見 `MARATHON_STATE.md`。

---

## 2026-08-22T12:00:00+08:00 — 把關者（Cowork）回報 .py 在 GitHub 上 404，逐項稽核

**做了什麼：** Cowork 回報 `research/` 底下只有 `.md` 讀得到，`holdout.py`／`costs.py` 等 `.py` 在 GitHub 上是 404，無法稽核。依使用者指示逐項排查：
1. 本機 `git status` 確認 working tree clean、`git log` 確認 5 個 research 相關 commit 都存在（含 `3ddac51` 那個明確 create 了 `research/validation/*.py` 的 commit）。
2. `git fetch origin` 後比對本機 `HEAD` 跟 `origin/main`，一致。
3. 對 10 個 `.py` 檔逐一 `curl raw.githubusercontent.com`，全部 HTTP 200。
4. 用 GitHub API `/repos/.../contents/research` 跟 `/contents/research/validation` 直接列出目錄內容（不透過 CDN 快取的路徑），跟本機 `git ls-tree` 結果逐檔比對，完全一致。
5. 用 GitHub API `/commits/main` 拿到的 SHA 跟本機 `git rev-parse HEAD` 逐字元比對，完全一致（`a237bcb59270a8f4baab6e27b4be0828ba11809a`）。
6. 順便檢查 App 端檔案（`index.html`／`PROGRESS.md`／`sw.js`／`manifest.webmanifest`／icon 檔）也都 curl 過，全部 200。
7. 檢查 `.gitignore`：只有 `research/data/`／`*.pyc`／`__pycache__/`，沒有任何會誤擋 `.py` 的規則；用 `git check-ignore` 對全部已追蹤 `.py` 檔跑過一輪，沒有一個被誤擋。依使用者要求追加防禦性規則 `*.parquet`／`*.db`／`fred_key.txt`／`.env`（目前這個 repo 裡都還沒有這些檔案，是預防性的），加完再跑一次 `check_ignore` 確認沒有連帶擋到任何已追蹤的 `.py`。

**驗證結果：** 四種獨立查證方式（本機 git、raw content CDN、GitHub API 目錄列表、GitHub API commit SHA）全部顯示一致——**這次稽核當下，`.py` 檔案確實都在 GitHub 上、確實讀得到**。Cowork 回報的 404 狀態沒有在這次稽核重現，判斷是查核當下抓到舊快照（可能在 `3ddac51` 那次 push 完成之前查的，或本地 clone 沒 pull 到最新），不是 push 流程本身有問題。

**已修正/補強：**
- `STRATEGY_LOG.md` 最上面加了 FILE MANIFEST 區塊，逐檔列出 repo 相對路徑＋用途，附上這次稽核的驗證方式跟時間戳，之後任何人都能照著同一套方法重新核對，不用回頭問。
- `.gitignore` 加了防禦性規則（`*.parquet`／`*.db`／`fred_key.txt`／`.env`）並附註解釋「不要加裸的 `*.py` 或 `research/`」，避免以後有人誤改成把整個資料夾擋掉。

**下一步：** 把這次稽核結果推上去，讓 Cowork 用同樣的驗證方式（GitHub API 或 raw content）重新確認一次。若 Cowork 之後還是看到 404，優先懷疑是它自己那端的 clone/快取沒更新，而不是 push 又漏了——但還是要重新走一次上面 7 步驟確認，不能假設。

---

## 2026-08-22T13:00:00+08:00 — 修真正的漏洞：holdout 資料在 fetch 層沒有預設截斷

**做了什麼：** Cowork 這次抓到一個真的架構漏洞（跟上一條的「查舊快照」誤會不同，這條是真的）：`finmind_client.fetch()` 預設回傳含 holdout 的完整歷史，`validation.holdout.cap_to_dev()` 只是選配——任何研究程式碼呼叫 `fetch()` 後忘記手動 cap，就會靜默拿到 holdout 資料，違反 `CONSTITUTION.md`「資料載入預設就截斷在 holdout 邊界前」。修法：

1. `finmind_client.py`：原本唯一的 `fetch()` 拆成三個：
   - `_fetch()`（原本的 `fetch()` 改名，加底線標記 internal，策略/分析程式碼不該直接呼叫）
   - `load_dev(dataset, data_id, start_date, end_date=None, date_col='date')`：**唯一正式入口**，內部呼叫 `_fetch()` 時把 `end_date` 強制夾在 `VAL_END`（`2024-12-31`）或更早，就算呼叫者傳更晚的 `end_date` 也會被夾住；拿到資料後再用 `date_col` 過濾一次（雙重保險，防萬一 FinMind API 哪天不理會 `end_date` 參數）；如果資料集根本沒有指定的 `date_col`，直接 `raise ValueError`，不會悄悄放行不截斷。
   - `load_full_history(dataset, data_id, start_date)`：唯一合法的無截斷路徑，明確標註「只能用來餵給 `unlock_holdout_once()`，不要拿來做一般分析」。
2. `validation/holdout.py` 新增 `assert_no_holdout_leakage(df, date_col, context)`：資料載入時的硬性斷言，`is_holdout_consumed()==False` 時若 `df` 裡有任何一列日期 `> VAL_END` 就立刻 `raise AssertionError`；holdout 已解鎖後這個檢查自動變 no-op（此時看到晚期日期是預期行為）。
3. `audit_ledgers.py` 新增第三條恆等式 `check_no_holdout_leakage(trades)`：檢查 `trades.csv` 本身有沒有日期晚於 `VAL_END` 但 holdout 沒解鎖的列，跟第 2 點的 `assert_no_holdout_leakage()` 是兩道獨立防線（一個在資料載入點、一個在帳本層，防止有交易繞過資料載入器直接寫進帳本的情況）。已加進 `CHECKS` 清單，自動跑。
4. 掃過全部 `research/*.py` 的 `fetch()` 呼叫點（用 grep 逐一列出，不是憑印象）：
   - `adjust.py`（`TaiwanStockDividend`、`TaiwanStockPrice` 兩處）、`pit.py`（`TaiwanStockFinancialStatements`、`TaiwanStockMonthRevenue` 兩處）→ 全部改用 `load_dev()`，因為這些都是餵給回測分析用的價量/財報時間序列。
   - `universe.py`（`TaiwanStockDelisting`、`TaiwanStockInfo` 兩處）→ **刻意保留** `_fetch()` 不改，因為這兩個是會員名單/參考資料，`date` 欄位是快照記錄日（幾乎都是「今天」），不是價量時間序列；已用測試證實如果誤改成 `load_dev()`，`TaiwanStockInfo` 會被 `VAL_END` 濾到全空，直接弄壞整個宇宙建構——這不是漏改，是刻意排除並在 `universe.py` docstring 裡寫清楚原因。

**驗證結果：**
- `load_dev('TaiwanStockPrice','2330','2024-01-01')`：回傳最大日期 `2024-12-31`（等於 `VAL_END`），正確截斷。
- `load_full_history('TaiwanStockPrice','2330','2026-08-01')`：回傳最大日期 `2026-08-21`，真實近期資料，確認無截斷路徑正常運作。
- `load_dev()` 對沒有 `date` 欄位的資料集（用 monkeypatch `_fetch()` 模擬）正確 `raise ValueError`，不會悄悄放行。
- `assert_no_holdout_leakage()` 三種情境都測過：乾淨資料不 raise；含未來日期資料在未解鎖時正確 raise；`unlock_holdout_once()` 解鎖後同一份資料不再 raise。
- `audit_ledgers.py` 新檢查：對空 ledger PASS；合成一筆日期 `2025-03-01`（晚於 `VAL_END`）且未解鎖 holdout 的交易，正確 FAIL 並精確指出是哪個 `trade_id`。
- 回歸測試 `adjust.py`／`pit.py`／`universe.py` 三個模組全部重新跑過：`adjust.py` 的除權息事件跟價格序列都正確截斷在 `2024-12-31`（且最後一列 `adj_close==close` 這個既有性質在截斷後依然成立）；`pit.py` 的季報跟月營收都正確截斷；`universe.py` 維持原本的 3,196 檔（2,974 現存 + 222 下市），沒有被誤傷。

**下一步：** 把這次修正推上去。里程碑 2 剩下的「把四個 validation 模組串成能跑的骨架」這件事，之後要串接時，記得資料進口一律走 `load_dev()`，不要圖方便直接叫 `_fetch()`。

---

## 2026-08-22T14:00:00+08:00 — 里程碑 4：回測引擎骨架 + Weinstein 第二階段第一次跑通（結果 FAIL）

**做了什麼：**

1. **`backtest/engine.py`**（新增）：通用回測引擎。核心函式 `run_backtest(signal_fn, price_data, market_df, config)`：
   - 逐日走 `market_df` 的交易日曆（不是逐週跳，這樣停損檢查可以每天做，不只在換股日）。
   - 每天先處理「今天該成交的排程」（`pending` 清單）：檢查 `validation/costs.limit_status()`，買單遇漲停鎖死、賣單遇跌停鎖死就順延到下一交易日重試，不強制成交。
   - 再做每天的三層風控檢查：Tier 1（收盤價跌破自身 150 日均線 `ma150` 就排程賣出）、Tier 3（跌破進場價 `stop_loss_pct`，預設 15%，就排程賣出）；Tier 2（部位上限）是在換股日決定新倉數量時直接限制，不是每天檢查的項目。
   - `config.rebalance_weekday`（預設週五）當天才呼叫 `signal_fn`，決定要不要換股。
   - 訊號用 T 日資料算出，成交排到 T+1（`EXECUTION_LAG_DAYS=1`），結構上不可能同一天訊號跟成交，不用另外提醒自己小心。
   - 成本：買方只收手續費+滑價，賣方收手續費+證交稅+滑價，數字全部從 `validation/costs.py` 的常數算，沒有自己另外編數字。
   - 資料進場前對每個 `price_data[sid]` 跟 `market_df` 都跑一次 `validation.holdout.assert_no_holdout_leakage()`。

2. **`strategies/weinstein_stage2.py`**（新增）：`prepare_price_data()` 用 `.rolling()`/`.shift()` 預先算好 `ma150`／`ma150_prev`（10 天前的均線值，用來判斷均線有沒有上揚）／`momentum`（60日報酬）三個欄位——這些 pandas rolling 運算本質上就是「只看當下與更早的資料」，用來查詢當天的值不會有 look-ahead 疑慮。`prepare_market_data()` 對加權指數算 `ma200`／`gate`（收盤>200日均線）。`stage2_signal()` 是插進引擎的 `signal_fn`：大盤 `gate` 關閉直接回傳空字典（不開新倉）；否則回傳通過篩選（收盤>ma150 且 ma150>ma150_prev）的股票，分數是 `momentum`，引擎自己排序取前 N 名。

3. **`strategies/run_weinstein_pilot.py`**（新增）：串起來的跑法。**試點宇宙 30 檔**（手選知名台股大型權值股，如 2330/2317/2454/2308/2412 等，橫跨半導體/電子/金融/傳產/航運/電信），起始資料日 `2010-01-01`（給均線暖機時間）。分別跑 train（2015-01-01～`TRAIN_END`）跟 validation（2021-01-01～`VAL_END`）兩段，各自算報酬率、最大回撤、交易數、跟加權指數買進持有比較；再對 validation 期做成本 1x/2x/3x 敏感度；再用 `validation/control_group.run_control_group()` 做隨機控制組（200 次抽樣，每次靜態等權買進持有 10 檔隨機試點宇宙成分股，比較策略跟隨機分布的百分位）。

**驗證結果：**
- 小規模驗證（3 檔股票、6 個月）先通過再跑大的，確認引擎本身沒有明顯 bug（有成交、有記錄、equity 曲線正確累積）。
- 全量跑（30 檔，`2015-01-01`～`2024-12-31`）：
  - Train：**324 筆交易**，report +168.42%，買進持有 +58.86%，贏；最大回撤 -13.66%。
  - Validation：**160 筆交易**，report +135.77%，買進持有 +54.58%，贏；最大回撤 -34.83%。
  - 成本敏感度（validation）：1x +135.77% → 2x +129.68% → 3x +123.58%，單調遞減但沒有翻負或崩潰，成本穩健。
  - **隨機控制組（validation）：策略期末權益 2,357,682，落在 200 次隨機抽樣（靜態等權買進持有 10 檔）分布的第 24.5 百分位，中位數 2,820,901 反而贏過策略——沒打贏。**
- **對真實跑出來的交易紀錄做二次驗證**：把 train（324 筆）跟 validation（160 筆）的交易 DataFrame 直接餵給 `audit_ledgers.run()`，兩批都 **ALL PASS**（每個平倉都有對應進場記錄、無 NaN 價格/股數、無 holdout 洩漏）——證明引擎自己的帳本邏輯是自洽的，validation 沒打贏控制組不是帳本算錯，是策略在這個試點宇宙條件下真的沒有相對隨機的優勢（解讀見 `STRATEGY_LOG.md` 對應條目——試點宇宙本身是後見之明式的贏家集中池，這是這輪方法論上最大的已知弱點）。
- 交易/權益曲線存成 CSV：`data/backtests/weinstein_stage2_pilot_{train,validation}_{trades,equity}.csv`（`.gitignore` 排除，本機保留供之後複查）。

**LEADS.md 記錄：** `weinstein_stage2_pilot_v1`，判定 **FAIL**（隨機控制組不過）。**完全沒有呼叫 `unlock_holdout_once()`**——`HOLDOUT_LOCK.json` 依然不存在，可用 `python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` 隨時複查（應該印 `False`）。

**已知簡化（誠實列出）：**
1. 隨機控制組用「靜態買進持有」對照，不是「動態週頻重抽」——後者才是嚴格對應策略機制的對照組，這輪先用較簡單可實作的版本。`control_group.py` 的通用 API 是為「靜態候選名單」設計的，跟本策略「每週動態重選」的機制不完全對應，這個落差是刻意的簡化，寫進了程式碼註解跟這裡。
2. 試點宇宙 30 檔是手選、非全市場——`universe.py` 的全市場掃描沒有在這輪執行（API 呼叫量/時間成本考量）。
3. `criteria.py` 沒有在這輪鎖定標準檔——train/val 層的通過標準已經是 `CONSTITUTION.md` 寫死的固定關卡，這個機制留給之後 holdout 評估用。

**下一步：** 等使用者決定後續方向（換宇宙建構方式重跑 / 升級隨機控制組成動態版本 / 全新參數當新候選）。無論哪個方向，都要走一輪新的 `LEADS.md` 記錄，不能直接改這條的判定。

---

## 2026-08-22T15:00:00+08:00 — Cowork 修正兩個方法論缺陷後重跑：無偏宇宙抽樣 + 配對式控制組，過程中抓到 3 個真 bug

**做了什麼：**

1. **`validation/control_group.py` 新增 `run_matched_control_group()` + `extract_trade_schedule()`**：`extract_trade_schedule(trades)` 從真實回測的 `trades` DataFrame 拉出每筆平倉對應的 `{entry_date, exit_date}`（用 `entry_trade_id` 配對買賣）。`run_matched_control_group()` 拿這個時間表，200 次隨機重抽：**每筆交易保留一模一樣的進場日／出場日，只把股票代號換成隨機抽的一檔**（限定當天有價格資料的候選），用完全相同的部位大小公式（`slot_allocation`）跟成本公式（`cost_rates` 參數直接從呼叫端傳入，不在這裡重新定義，確保跟真實回測用的是同一套費率）算出這筆交易的損益，累加得到這次重抽的期末權益。這樣重抽出來的 200 條軌跡，換股頻率、部位數隨時間的變化、持有天數分布，跟真實策略完全一樣，只有「選哪支股票」被隨機化——這正是 Cowork 要求的「同樣動作、隨機挑對象」。

   `buy_leg_rate()`／`sell_leg_rate()` 兩個原本是 `backtest/engine.py` 內底線開頭的私有函式，這次拿掉底線變成公開函式（給 `control_group.py` 呼叫端算 `cost_rates` 用），確保成本費率只有一個計算來源，不會兩邊各自維護一份公式、之後改了一邊忘記改另一邊。

   用合成資料驗證：3 支假股票（一支穩定上漲、一支持平、一支下跌）、2 筆交易排程，跑 500 次重抽，結果分布中位數落在接近打平（扣成本後略負），候選（120,000，相當於吃到上漲那支）落在第 89.4 百分位——分布形狀符合直覺，函式邏輯正確。

2. **`backtest/engine.py` 新增 `sortino_ratio` 屬性**：年化 Sortino ratio，MAR（最低可接受報酬）設為 0（明確標註是簡化假設，不是用無風險利率），下檔標準差只用負報酬的日子算。

3. **`strategies/run_weinstein_unbiased.py`（新增）**：`universe.py` 的 `universe()` 全市場（3,196 檔，post-2003+含下市股）用固定種子（`20260822`）隨機抽 100 檔，不再手選。跑 train/val/成本敏感度，控制組改用 `run_matched_control_group()`。

**跑的過程中，第一次全量執行就崩潰／出現大量資料錯誤，逐一排查抓到 3 個真的程式碼 bug（不是資料本身的問題）：**

- **`adjust.py` `adjustment_events()`**：`events` 列表為空時，`pd.DataFrame(events).sort_values("ex_date")` 對一個 0 欄位的空 DataFrame 呼叫 `.sort_values()`，丟出 `KeyError('ex_date')`。修法：`events` 為空時直接回傳跟 `div.empty` 分支一樣、欄位齊全的空 DataFrame，不要讓程式碼跑到 `.sort_values()` 那行。
- **`adjust.py` `adjusted_price_series()`**：原本寫成 `load_dev(...).sort_values("date").reset_index(drop=True)` 一路鏈式呼叫，如果 `load_dev()` 回傳空 DataFrame（0 欄位），`.sort_values("date")` 一樣丟 `KeyError('date')`——要先接住回傳值判斷 `.empty`，再決定要不要排序。
- **`backtest/engine.py` 執行成交那段**：`shares = int(slot_allocation // (fill_price * (1 + buy_leg_rate(config))))`，如果當天 `fill_price` 是 0（少數冷門/瀕臨資料邊界的股票偶爾會有異常列），分母變 0，`ZeroDivisionError` 直接讓整個回測崩潰。修法：在算 `shares`之前先檢查 `fill_price<=0` 或 `NaN`，是的話這筆成交順延到下一交易日重試，不強制成交也不崩潰。

三個 bug 都用先前會出錯的股票代號（`7822`／`2381`／`3499`／`8999`／`1606`／`1107`／`7418`／`7893`／`6958A`／`6232`／`00776`／`7912`）逐一重跑 `adjusted_price_series()` 驗證過，全部不再報錯（真的沒資料的正確回傳 0 列，不是假裝有資料）。

**這三個 bug 為什麼在手選 30 檔試點宇宙時沒被抓到：** 手選的都是知名大型權值股，資料完整、流動性好，不會踩到「近期上市資料太少」「除權息事件表剛好是空的」「個別交易日價格是 0」這種資料邊界情況。改成無偏隨機抽樣後，馬上就抽到好幾檔冷門/邊緣案例，逼出這些之前沒測到的路徑——這是全市場（或至少無偏抽樣）測試比手選清單更有價值的具體證據，不只是「避免選擇偏差」這個抽象理由。

**驗證結果（修好 bug 之後的完整跑法）：**
- 100 檔隨機抽樣（種子 `20260822`），82 檔有足夠資料（≥200 列）可用；其餘因資料太少或完全查無資料被過濾掉（過濾邏輯本身沒問題，見上段）。
- **Validation（2021–2024，276 筆交易）**：+145.39%，MDD −22.41%，Sortino 0.702，勝買進持有 +54.58%。
- **Train（2015–2020，514 筆交易）**：+99.46%，MDD −29.11%，Sortino 0.444，勝買進持有 +58.86%。
- 成本敏感度（validation）：1x +145.39% → 2x +136.36% → 3x +127.38%，單調遞減、沒有翻負，穩健。
- **配對式隨機控制組（validation，133 組進出場日期，200 次重抽）：策略期末權益 2,453,879，勝過 200 次重抽分布的第 99.5 百分位**（中位數 1,376,454），50/90/95/99 四個門檻全部達標。
- 交易紀錄二次稽核：train（514 筆）、validation（276 筆）都餵給 `audit_ledgers.run()`，全部 PASS（含新的 holdout 洩漏檢查）。買賣筆數對得上（143 買／133 賣，10 筆是期末仍持有未平倉，`extract_trade_schedule()` 正確只抽取已平倉的 133 組，數字互相印證沒有算錯）。

**LEADS.md 記錄：** 新增一列 `weinstein_stage2_unbiased`。判定 **`EXPERIMENTAL`**（不是 `PASS`）——雖然四項關卡（買進持有/成本敏感度/交易數/隨機控制組）全部通過，但 `LEADS.md` 自己訂的規則講明白 `PASS` 一定要包含 holdout 驗證，這輪完全沒有觸碰 holdout。`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` 複查為 `False`。是否要花掉這個專案唯一一次的 holdout 測試機會，不是這裡能自己決定的事。

**下一步：** 等使用者決定要不要對 `weinstein_stage2_unbiased` 做一次性 holdout 測試（需要明確授權，且測過即焚），或是先擴大抽樣規模／真的逐檔掃全市場來提高嚴謹度，或是先去處理其他背景待辦（美股成本模型、紙上前測影子帳本）。

---

## 2026-08-22T16:00:00+08:00 — AI 選股引擎 Phase A 步驟 1／2：factors.py + factor_ic.py

**做了什麼：**

1. **`factors.py`（新增）**：六個因子的計算函式。
   - `_institutional_daily_net()`：把 `TaiwanStockInstitutionalInvestorsBuySell` 的長表（每列一個法人類別）轉成寬表（每列一天，`foreign_net`/`trust_net`/`dealer_net`/`total_net` 四欄），驗證過欄位對應：`Foreign_Investor`→外資、`Investment_Trust`→投信、`Dealer_self`+`Dealer_Hedging`→自營商（合併算一欄，因為策略層面通常不細分自營商自行買賣跟避險），`Foreign_Dealer_Self` 抽樣觀察一直是 0，排除不算。
   - `_foreign_streak_strength()`：(c) 因子，逐日算「當前連續買超天數的累積買超量 / 20日均量」，本質是序列相依的計算（今天算不算連續，要看昨天），沒辦法用 pandas rolling 向量化，寫成明確的迴圈，逐列只依賴當列以前的資料，不會有 look-ahead。
   - `_asof_join()`：核心的 point-in-time 對齊機制，`pandas.merge_asof(direction='backward')` 鍵在 `pit_date`。**踩到一個 pandas 版本限制**：`merge_asof` 的 join key 不接受純字串欄位（就算兩邊型別一樣也不行，錯誤訊息是 `Incompatible merge dtype ... both sides must have numeric dtype`），要先轉成 `datetime64` 才能 join，join 完再把輔助欄位丟掉、保留原本字串格式的 `date` 欄位（因為 `validation/holdout.py` 的字串比較邏輯依賴這個慣例，不能把整個 pipeline 換成 datetime64）。
   - `_revenue_yoy_acceleration()` (a)、`_eps_yoy_growth()` (b)：分別用 `pit.month_revenue_pit()`／`pit.quarterly_pit()` 的輸出算 YoY，再算 YoY 的變化量（加速度）／直接用 YoY（EPS 成長）。
   - (d) 因子：`TaiwanStockMarketValue`（市值）確認過是付費資料集（回傳 `Your level is free...`），改用「20日三大法人淨買金額 / 20日均成交金額」當流動性正規化的替代版本，`factors.py` docstring 跟 `FACTORS.md` 都寫清楚這是替代不是原版。

   **Point-in-time 正確性驗證（不是空口保證）**：把 2330 的 (a) 因子逐日攤開，找出因子值變動的那幾天，逐一比對 `pit.month_revenue_pit()` 算出的 `pit_date`：`pit_date=2024-08-10`（週六）→ 因子值在下一個交易日 `2024-08-12` 才變；`pit_date=2024-10-10`（國慶日）→ 因子值在 `2024-10-11` 才變；`pit_date=2024-09-10`／`2024-12-10`（剛好是交易日）→ 因子值當天就變。全部符合「揭露日或之後第一個交易日才看得到，不會提早」的預期，沒有例外。

2. **`factor_ic.py`（新增）**：`build_snapshots()` 用交易日曆切出不重疊的 20 日窗口；`_cross_section()` 對每個 snapshot 收集有效的（因子值, 未來報酬）配對；`evaluate_factor()` 算 train/val 平均 IC、IC_IR、hit_rate，並用 200 次「打散因子值-股票對應（報酬不動）」重算 IC 當隨機對照組，算真實 val IC 的絕對值贏過幾 % 的打散結果。三個通過條件（val IC 絕對值 ≥0.02、train/val 同號、打散對照百分位 ≥90）任一沒過就是沒過。

**驗證結果：**
- 小規模冒煙測試（8 檔股票）：確認橫截面組裝機制、Spearman 計算本身正確（用同一組 8 檔資料手動跑 `scipy.stats.spearmanr` 得到一致數字）；8 檔小於 `n<10` 的門檻，`evaluate_factor()` 正確把這個 snapshot 排除，不是 bug。
- 全量跑（100 檔抽樣、80 檔可用，121 個 snapshot，2015–2024）：
  - `f_rev_accel`：train IC +0.0086、val IC +0.0249（同號），打散對照 84.5 百分位——**FAIL**（沒到 90 門檻，但很接近）。
  - `f_eps_growth`：train IC +0.0490、val IC +0.0730（同號、val 比 train 還強），打散對照 **100.0** 百分位——**PASS**。
  - `f_foreign_streak`：train IC +0.0568、val IC −0.0220（**正負號相反**），打散對照 76.0——**FAIL**。
  - `f_inst_flow`：train IC −0.0013、val IC −0.0198（太小），打散對照 76.5——**FAIL**。
  - `f_rel_strength`：train IC −0.0128、val IC +0.0094（**正負號相反**、太小），打散對照 38.5（比一半的隨機結果還差）——**FAIL**。
  - `f_ma_breakout`：train IC −0.0597、val IC −0.0033（太小），打散對照 15.0（隨機打散常常贏過真實訊號）——**FAIL**。
  - 重跑一次驗證數字可重現（固定種子 `20260822`/`20260822`，兩次執行結果逐位元一致）。
- 結果存到 `data/factor_ic_results.csv`（`.gitignore` 排除）跟 `FACTORS.md`（git 追蹤，人類可讀版本）。

**FACTORS.md 記錄：** 6 個因子，1 個 PASS（`f_eps_growth`）、5 個 FAIL，每個都寫清楚沒過的具體原因（不是籠統的「沒過」）。

**任務在此停下**，依使用者指示，步驟 3（`score.py` 計分）跟步驟 4（App 選股頁）要等 Cowork／使用者審完這批因子結果才會開始。

---

## 2026-08-23T00:20:00+08:00 — Cowork 五點覆核回應：PIT 二次確認、Bonferroni 校正、擴大樣本重驗、擴充因子庫

Cowork 針對唯一通過的 `f_eps_growth` 提出 5 點要求：(1) 確認真的用 PIT 揭露日不是財報期末日；(2) 多重比較校正；(3) 全市場/更長橫斷面重驗；(4) 擴充因子庫；(5) 累積多個因子再談計分。逐點記錄如下。

**第 1 點——PIT 正確性二次確認：** 逐日攤開 2330 的 `f_eps_growth`，比對 `pit.quarterly_pit()` 算出的 `pit_date` 跟因子值實際變動的交易日。找到一筆春節連假案例：`pit_date=2024-02-14`（週三，但剛好卡在農曆春節連假中），因子值在下一個交易日 `2024-02-15` 才變，不是 `02-14` 當天或之前就反映；其餘案例（`pit_date` 剛好落在交易日）因子值當天即變，沒有一筆提早。**結論：`f_eps_growth` 確實使用 `pit.py` 揭露延遲後的日期，不是財報所屬期末日，不需要重算。** 這跟「發現 bug 修好」是不同種類的結論，這裡明確區分：這次是「查證後確認本來就是對的」。

**第 2 點——多重比較校正（Bonferroni）：** `factor_ic.py` 新增 `required_percentile` 欄位跟 `bonferroni_n` 參數，`required_percentile = 100×(1 − BASE_ALPHA/bonferroni_n)`，`BASE_ALPHA=0.10` 對應原本「≥90 百分位」的單次檢定顯著水準。原始 6 因子同批測，`bonferroni_n=6`，門檻拉到 98.3 百分位。同時把 `N_SHUFFLES` 從 200 提高到 1000（200 次只能解析到 0.5% 粗細度，逼近 98–99 百分位的門檻不夠精確）。**用當前程式碼重新完整跑一次原始 6 因子批次**（不是沿用舊 CSV，因為舊 CSV 是校正邏輯加入前的產物，缺 `required_percentile` 欄位）：5 個原本 FAIL 的因子校正後結論不變（本來就沒到 90，98.3 更不可能過），`f_eps_growth` 校正後依然通過（見下方確認數字）。**判定標記從單純「PASS」改為「候選→確認」的區分**：`f_eps_growth` 現在是「確認」等級（通過多重比較校正），比原本「1/6 通過」更可信。

**第 3 點——全市場/更長橫斷面重驗：** 誠實記錄限制先行——FinMind 免費額度流量上限在這次驗證中被真實觸發（`_fetch()` 對未快取的股票代號回傳 HTTP 402），完整逐檔掃全市場 3,196 檔或穩定擴大到 400 檔新樣本都沒有達成，這是外部限制，不是繞過。分兩步在限制內做到能做的部分：
1. Cache-only 重算（零新增 API 呼叫，只延長橫截面起始日到 2011）：171 個橫截面，`f_eps_growth` val IC +0.0495，通過。
2. `factor_ic_eps_expanded.py`（新增）：嘗試 100 原樣本 + 300 新抽樣（種子 `20260823`，跟原本 `SAMPLE_SEED=20260822` 不同、不重複）、橫截面起始日延到 2008。實際執行到第 104/400 檔時撞到流量上限，之後 296 檔全部失敗，最終 83/400 檔可用——**擴大樣本數這個目標沒有達成**。但 83 檔仍把橫截面從 121 延長到 184 個（2008–2024，多涵蓋一段完整景氣循環），`f_eps_growth`：val IC **+0.0742**，打散對照 **100.0 百分位**（`bonferroni_n=1`，單一因子確認性重測，非探索性掃描，理由見該檔案 docstring），PASS。
背景執行紀錄在 `research/data/eps_expanded_output.txt`（`.gitignore` 排除）。

**第 4 點——擴充因子庫：** 依方向逐一實作，全部走同一套 IC+隨機對照+PIT 管線：
- **分點集中度：調查後確認無免費端點，不進入 IC 測試。** 直接對 FinMind 打 `TaiwanStockTradingDailyReport` 得到付費拒絕；`TaiwanSecuritiesTraderInfo` 只有券商基本資料，沒有逐股分點成交量。
- **`f_value_pb`/`f_value_pe`（`TaiwanStockPER` 的 PBR/PER）、`f_quality_roe_stability`（`pit.py` 新增 `balance_sheet_pit()`，同 `quarterly_pit()` 邏輯，+45天保守假設）：實作完成，`prepare_factors()` 對這兩個資料集的呼叫包 `try/except RuntimeError`，避免任何一個新資料集被擋時連累其他 9 個因子（驗證過：2330 在兩個新資料集都被 402 擋下時，其餘 9 個因子照樣正確算出，不會整檔股票的資料一起消失——這是這次意外發現並修好的一個真實脆弱點，修之前一次 402 會讓 `load_sample_with_factors()` 直接把整檔股票 drop 掉，等於損失全部因子，不只是新因子）。**IC 測試被流量限制完全擋下**：100 檔樣本裡沒有一檔成功拿到這兩個資料集（每一檔都是 402），無法產出任何 IC 數字，誠實標記「未測試」，跟「測了沒過」是不同狀態。另外這兩個因子的 PIT 正確性也還沒驗證（`TaiwanStockPER` 是 FinMind 自算的每日比率，用的 trailing EPS/淨值是否有內建的未揭露前瞻偏誤未知），即使流量解除，測試前也要先做跟 `f_eps_growth` 同等級的逐日 PIT 比對。
- **`f_eps_surprise`／`f_revenue_surprise`（SUE 方法論：本期 YoY 差 ÷ 過去 N 期 YoY 差的滾動標準差，Bernard-Thomas 標準化未預期盈餘的代理指標，用在沒有分析師共識資料的情況）、`f_low_vol`（−60日日報酬滾動標準差）：三個都成功測試**（100 檔樣本，80 可用，121 橫截面，2015–2024，`bonferroni_n=6`，門檻 98.3）：
  - `f_eps_surprise`：train +0.0481、val +0.0731（IR +0.519）、打散對照 100.0，**PASS**。
  - `f_revenue_surprise`：train +0.0534、val +0.0496（IR +0.319）、打散對照 99.0，**PASS**。
  - `f_low_vol`：train +0.0784、val +0.1177（IR +0.615，目前 val IC 最強）、打散對照 100.0，**PASS**。
  三個全部在校正後的 98.3 高門檻下通過，不是壓線擦邊。結果存在 `data/factor_ic_new_batch1.csv`（`.gitignore` 排除）。

**第 5 點——累積現況：** 目前通過（校正後）的因子共 **4 個**：`f_eps_growth`、`f_eps_surprise`、`f_revenue_surprise`、`f_low_vol`。橫跨兩類不同資料（基本面成長/意外、純價格波動度），不是同一訊號的變形。**仍不會自己往下做 `score.py`**——3 個新因子（PB/PE/ROE穩定度）完全未測，且 4 個已通過因子彼此的相關性/共線性也還沒檢查（如果 `f_eps_growth` 跟兩個 SUE 因子高度相關，可能實質是同一個「基本面動能」訊號被算了三次），這些都是計分動工前該先確認的事。

**完整逐因子數字、判定表格見 `FACTORS.md`（已更新）。已知限制（流量限制未解除、3 個因子未測、因子間相關性未查）逐一列在 `FACTORS.md` 對應段落。**

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，這輪五點覆核全程沒有呼叫任何跟 holdout 相關的函式。

**任務在此停下**，等 Cowork／使用者審完這批結果，依然不會自己往下做 `score.py` 或 App 選股頁。

---

## 2026-08-23T01:00:00+08:00 — Part 1「先收尾 AI 選股引擎」：因子去重 + score.py + 組合回測 + App 選股頁

使用者授權往下做（前一輪的「停下等審」解除），指示做完 push 才能設 Part 2 的排程。

**1. `factor_correlation.py`（新增）**：對 4 個通過 IC 檢定的因子算相關性矩陣，見 `FACTORS.md` 的完整表格跟判定。`f_eps_growth`／`f_eps_surprise` 相關 +0.831（同家族），其餘 5 對都 ≤0.27（獨立）。用跟 `factor_ic.py` 完全相同的樣本/快取，零額外 API 呼叫。第一次執行時意外撞上一個自製的 bug：`timeout 170 python factor_correlation.py` 這個 shell 包法本身有 170 秒硬上限，跟工具的背景化機制是兩回事，`timeout` 提前把還在跑的程式殺掉（誤判為「太慢」），改成不包 `timeout`、直接背景執行後正常跑完。

**2. `score.py`（新增）**：綜合分引擎。`load_industry_map()` 用 `_fetch()`（不透過 `load_dev()`，跟 `universe.py` 同樣理由：這是分類 metadata 不是價量時間序列）抓 `TaiwanStockInfo` 的 `industry_category`。`_zscore_within_group()` 做同產業 peer normalization，peer group <5 檔退回全樣本 z-score。`compute_scores_at_date()` 把 `f_eps_growth`／`f_eps_surprise` 各自算 peer z 後平均成 `eps_family`，`f_revenue_surprise`／`f_low_vol` 各自保留獨立 z，綜合分 = 3 個成分等權平均（用 `skipna=True`，缺某個成分不會被當 0 分懲罰，只用有的成分算）。加了 `MIN_COMPONENTS_FOR_RANKING=2` 過濾：實測發現 ETF（00844B/00923）因為沒有真實 EPS/營收資料，只用低波動一個成分就能排到前段班——ETF 結構性地比個股平滑，這是資料覆蓋率造成的假象不是選股訊號，加這道過濾後這兩檔正確被排除在排行榜外。

**流量限制解除的意外發現**：寫 `score.py` 測試過程中，`prepare_factors()` 對 100 檔樣本重新呼叫 `TaiwanStockPER`／`TaiwanStockBalanceSheet` 時，發現這兩個資料集**現在都正常回傳真實資料**（不再是 8/22 那批持續一整天的 402）。這代表 8/22 記錄為「完全未測」的 `f_value_pb`／`f_value_pe`／`f_quality_roe_stability` 現在其實可以重跑 IC 測試了——**這輪沒有補做**（不在使用者這輪指示範圍內），已記入 `FACTORS.md`／`MARATHON_STATE.md`，排進後續馬拉松軌道。

**3. `backtest/engine.py` 的一個真正 bug 修正（順手發現，不是刻意找）**：`run_backtest()` 原本把交易紀錄的 `book` 欄位寫死成 `"weinstein_stage2_pilot"`（兩處），這在只有 Weinstein 策略用這顆引擎時沒差，但這次要拿同一顆引擎重跑 `score.py` 的 top-N 策略時，帳本會錯誤標成 Weinstein 的書——`audit_ledgers.py` 之類的稽核工具會被誤導。修法：`BacktestConfig` 新增 `book_name: str = "weinstein_stage2_pilot"` 欄位（預設值保留舊行為，不影響既有呼叫端 `run_weinstein_pilot.py`／`run_weinstein_unbiased.py`，兩處都沒有明確設定這個欄位，驗證過不受影響），兩處寫死改成讀 `config.book_name`。

**4. `run_score_backtest.py`（新增）**：對 `score.py` 綜合分前 10 名做完整「扣成本+換手」組合回測。**發現 `backtest/engine.py` 的 `run_backtest()` 原生機制剛好完全符合需求，不用重寫一顆新引擎**——`signal_fn(price_data, as_of, market_df) -> {stock_id: score}` 這個介面，只要 signal_fn 回傳「已經篩到剩前 N 名」的字典，引擎既有的週頻檢查/T+1成交/只換真正進出榜名字（不強制全部重新等權）/成本扣除機制就完全可以重用，把 `score.compute_scores_at_date()`+`eligible_for_ranking()`+`.head(N)` 包成一個 `signal_fn` 傳進去即可。

隨機控制組（`make_random_signal_fn`）：跟 `weinstein_stage2_unbiased` 的配對式方法同精神——同樣的換股時點/檔數/成本模型，只把「挑哪些股票」隨機化，而不是像舊版靜態控制組那樣連換股頻率都不對應。**第一次嘗試（200 次重抽，照搬 Weinstein 前例的抽樣數）跑到明顯太慢被手動中止**：每次重抽都要重跑一次完整多年逐日回測，不是像 `control_group.py` 靜態版那樣只是抽樣算個百分位而已，200 次的計算量在合理時間內跑不完。優化：(a) 加一個 `_eligible_pool_cache`，同一個 `as_of` 日期的合格股票池只算一次、200 次抽樣共用（原本每次重抽都重新算一次完整的 z-score cross-section，浪費）；(b) 把抽樣數從 200 降到 60，誠實記錄這是比 Weinstein 前例更小的統計預算，因為計算成本結構不同（不是刻意壓低）。優化後在合理時間內跑完。

**組合回測結果（完整數字見 `LEADS.md` 的 `score_topn_v1` 列）**：
- Train（2015–2020，872 筆交易）：+131.65%，配對式隨機對照組 **100.0 百分位**（60 次重抽中位數期末權益僅 704,681，較起始 1,000,000 **倒賠約 30%**；真實策略達 2,316,487）。
- Validation（2021–2024，628 筆交易）：+97.58%，配對式隨機對照組 **100.0 百分位**（60 次重抽中位數 1,017,076，幾乎打平；真實策略達 1,975,796）。
- 成本 1x/2x/3x 全部維持正報酬、單調遞減、沒有翻負（val +97.58%→+75.63%→+53.77%）。
- **誠實記錄反直覺的一面**：兩期絕對報酬都輸給「零成本全樣本80檔買進持有、不換股」（val +269.53%、train +278.91%）。**這不是判定策略沒用的理由**——正確的判讀方式是看配對式隨機對照組（100.0 百分位，完勝），不是看跟零成本被動基準的差距。真正發生的事是：週頻檢查換股這個機制本身摩擦成本很高（隨機挑股票、同樣換股頻率，中位數表現在 train 期甚至倒賠），能把「這個機制下大概率會虧錢」扭轉成「顯著跑贏所有隨機對照組」的，正是綜合分真實的選股能力。這個教訓跟 `weinstein_stage2` 系列一模一樣，再一次證實「拿零成本被動基準當唯一比較對象」是會誤判的方法論陷阱。

**5. `scores.json`（新增，`alpha-app/` repo 根目錄，非 `research/data/`，進 git）**：`export_scores_json(VAL_END, ...)` 產生，前 30 名。**開發過程抓到一個真的 bug**：Python `json.dump()` 對 `float('nan')` 預設會輸出裸的 `NaN` token（Python 讀得回來，但不是合法 JSON，瀏覽器 `JSON.parse()` 正確拒絕）——第一次產生的檔案送進瀏覽器測試時，選股頁直接顯示「載入失敗：Unexpected token 'N' ... is not valid JSON」。修法：`DataFrame.where(cond, None)` 對 float64 欄位無效（pandas 會把指定的 `None` 自動轉回 `NaN`，這是 float64 dtype 的限制，不是程式碼邏輯錯），要在 `.to_dict(orient='records')` 轉成純 Python dict**之後**才能把 NaN 換成 None（純 Python 的 `dict`/`float` 沒有 pandas 那個 dtype 限制）。同時加 `allow_nan=False` 當第二道防線，之後如果又有 NaN 漏網會直接在產生階段噴出 `ValueError`，不會再悄悄寫出壞掉的 JSON 交給前端才發現。

**6. `index.html`（App 前端，新增「選股」分頁）**：新增第 3 個底部導覽項目（今日/市場/**選股**/交易/日誌/設定），`scr-picks` 畫面：AI 選股引擎說明卡（含研究/教育用途聲明）、綜合分排行榜（`fetch('scores.json')`，點列可展開因子拆解）、因子拆解卡（顯示 `eps_family`／`revenue_surprise`／`low_vol` 三個成分的 peer z-score，成分不足 3/3 時標註可信度較低）。完全複用既有的 `.card`／`.row`／`.dl` CSS 元件，沒有引入新的視覺語言，維持既有風格。

**瀏覽器實測（不是只看程式碼推論，真的開瀏覽器點過）**：起本機 `python -m http.server` 服務 `alpha-app/` 目錄（模擬 GitHub Pages 靜態託管，不是 `file://` 直接開檔案，避免 `fetch()` 的 CORS 假象），用 Claude in Chrome 工具導覽/點擊/截圖驗證：首頁正常載入真實 FinMind 資料（回歸測試，確認新分頁沒有弄壞既有功能）；點擊「選股」分頁正確顯示 30 檔排行榜（含產業別、綜合分）；點擊任一列正確展開因子拆解卡，數字跟 `scores.json` 原始內容逐位元對得上。過程中中途撞到兩次 CDP screenshot timeout（環境層面的暫時性問題，重試後正常，不是程式碼問題）跟一次因為 nav bar 在頁面未捲動時位於視窗外（`#app{height:100dvh}` 但工具截圖視窗高度小於實際 viewport 高度）導致誤點到自選股列表項目——都排除後正常運作。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，這輪全程沒有呼叫任何跟 holdout 相關的函式（`scores.json` 用 `VAL_END` 當基準日，不是 holdout 期間資料）。

**留下但誠實標註未解決的架構問題**：使用者原始設計書步驟 5（每日排程更新 `scores.json`）需要抓 `VAL_END` 之後到「今天」的資料，這段目前定義上算 holdout；用已驗證好的既有方法論去跑新資料（不調整任何權重/邏輯）產生每日選股，跟拿 holdout 資料去決定/調整策略設計是兩件不同的事，前者不會污染任何驗證結論。要不要開一條獨立於 `unlock_holdout_once()` 之外的「即時資料」路徑，留給使用者明確決定，這裡沒有自己決定或繞過去做。詳見 `FACTORS.md` 對應段落。

**下一步：** commit + push 完 Part 1，接著設 Part 2（30分鐘挖礦馬拉松，Windows 工作排程器）。

---

## 2026-08-24T13:40:00+08:00 — Cowork 稽核回應：多空市場中性評估取代長多前N名框架

**Cowork 的稽核（誠實記錄批評本身，不是只記回應）**：`score_topn_v1`（週頻長多前10名）打贏配對隨機對照組（100百分位）證明因子有真訊號，這點沒錯；但絕對報酬 +97.58% 輸給同批買進持有 +269.53%，代表「這個用法」（長多、集中、週頻換股）本身在真實摩擦下不是划算的策略形式；而且買進持有基準本身用的是 80 檔抽樣，帶著抽樣/存活者偏差，不是公平比較基準。**這個批評是對的，不是無理取鬧**——上一輪的 `REPORT.md`/`LEADS.md` 已經用「跟隨機對照組比才是正統」的邏輯自圓其說過，但沒有正面處理「這個具體實作形式本身沒有實用價值」這個獨立問題。

**修正方向（Cowork 指定，逐項對應）：**

**1. 改用多空市場中性設計**——新增 `long_short_backtest.py`。每期依綜合分排序，買前 decile（10%）、空後 decile，兩腳等權。多空價差報酬（`R_long − R_short`）結構上把因子的橫截面預測力跟大盤方向隔開（兩腳都跟著大盤漲跌，只有價差反映因子排對了沒排錯）。**Beta 是實測出來的（用 `numpy.polyfit` 對 TAIEX 日報酬做迴歸），不是假設**——多空不代表天生市場中性，這是稽核要求要驗證的東西，不是預設成立。**空頭成本模型是新加的**：`validation/costs.py` 新增 `short_round_trip_cost_pct()`（賣出開空的手續費+證交稅、買進回補的手續費、加上借券費用按持有天數比例計算，`BORROW_FEE_ANNUAL_PCT=2.0%` 是未經真實報價校準的占位假設，跟既有 `DEFAULT_SLIPPAGE_BPS` 同等級揭露；沒有模擬借券強制回補風險，誠實列為已知簡化）。

**2. 全部改用 universe.py 全市場無偏宇宙**——不再用原本 `SAMPLE_SEED=20260822` 的 80/100 檔偏差樣本。`main()` 對 `universe()` 的完整 3,196 檔列表做固定種子（`20260824`）隨機洗牌後嘗試逐檔抓取。**誠實記錄：沒有達成全市場 3,196 檔覆蓋率**——過程中連續撞到兩層 FinMind 流量限制：先是硬性 IP 封鎖（403 "ip banned"，`retry_after=1782` 秒≈30分鐘，跟同時間背景執行的挖礦馬拉松期貨軌獨立撞到同一道牆，證實是共用 IP 額度、不是單一程式的問題），封鎖解除後又持續撞到較軟的 402「額度用盡」（`DATA.md` 記錄的「每小時數百次」上限，這次因為手動測試+馬拉松並行消耗，額度被快速榨乾）。**最終達成覆蓋率：170/3,196 檔（≈5.3%）**——比原本 80/100 檔樣本略大，且是從完整宇宙重新隨機抽樣（不是同一批舊樣本），去除了原本因為固定種子只抽過一次的偏差疑慮，但**不是**使用者要求的真正全市場逐檔掃描，這個落差誠實揭露，不是繞過或藏起來。全市場覆蓋是否要繼續嘗試（例如等流量重置後排進挖礦馬拉松慢慢補），留給使用者決定。

**過程中另外抓到並修好三個真的程式碼 bug：**
1. `capm_beta()` 一開始寫 `market_df["adj_close"]`，但 `prepare_market_data()`（`strategies/weinstein_stage2.py`）只有 `close` 欄位——TAIEX 是指數不是個股，沒有股利/分割可還原，`adj_close` 從來沒被加過。冒煙測試時的 `KeyError` 抓到。
2. **小樣本異常值放大 bug**：冒煙測試（80檔樣本、decile=8檔/腳）第一次跑出「總報酬 +561,885%」這種不可能的數字。追出來是單一檔股票的資料異常（`adjust.py` 已知缺口：減資事件沒有處理，見 `STRATEGY_LOG.md`）造成單日「報酬」暴衝上千%，在只有 8 檔的等權平均裡被放大成整個投資組合的災難性/災難性正報酬。修法：`leg_return()` 加一道 `MAX_PLAUSIBLE_DAILY_RETURN=0.20`（20%，高於台股實際±10%漲跌停限制留一點緩衝，但足以濾掉減資級別的假暴衝）過濾，超過這個範圍的單日觀測值視為資料異常，該股票該天直接排除（不是整個回測中止）。
3. **淨值前後不一致 bug**：`capm_beta()`／`sortino_ratio()` 原本用未扣成本的 `spread_return` 欄位算 beta/alpha/Sortino，但換手成本只有乘進 `equity`、沒有寫回 `spread_return`——導致 alpha（+20%）跟真正扣成本後的年化報酬（+1.35%）對不上。修法：兩個函式都改成從 `equity.pct_change()`（已扣成本）算，不用原始 `spread_return` 欄位。
4. **效能 bug（同一個坑踩第二次）**：第一次跑全量評估時，40 次隨機對照重抽每次都重新算一次完整的橫截面綜合分（含產業 peer z-score），一個週期卡了 20 分鐘還沒跑完。這正是 `run_score_backtest.py` 已經抓過、修過的同一個問題（`_eligible_pool_cache`），這次寫新檔案時忘記把修法帶過來。補上 `_get_scored()` 快取（keyed by `id(data)` + `as_of`），同一份資料的同一天只算一次，40 次重抽共用。修完後 4 個週期（train/val × 週頻/月頻，各含 40 次重抽）從卡住 20 分鐘一個週期，變成全部 4 個週期在合理時間內跑完。

**3. 週頻 vs 月頻再平衡對照（Cowork 要求）：** 兩種都測了，完整數字如下。

| 週期 | 再平衡 | 總報酬(扣成本) | 年化報酬 | Beta(實測) | 年化 Alpha | Sortino | 隨機對照組百分位 |
|---|---|---|---|---|---|---|---|
| Train (2015-2020) | 週頻 | +27.15% | +4.21% | −0.105 | +6.58% | 0.342 | **100.0** |
| Validation (2021-2024) | 週頻 | +61.64% | +13.27% | −0.095 | +16.06% | 0.900 | **100.0** |
| Train (2015-2020) | 月頻 | **−9.66%** | **−1.73%** | −0.080 | +0.27% | −0.028 | **100.0** |
| Validation (2021-2024) | 月頻 | +66.54% | +14.15% | −0.048 | +16.17% | 0.976 | **100.0** |

**4. 誠實解讀（扣成本後、算出實測 beta 之後，到底有沒有非 beta 的 alpha）：**

- **Beta 全部接近零（−0.048 到 −0.105，四期一致）**——這不是假設出來的，是對 TAIEX 日報酬迴歸算出來的真實數字。**這證實多空中性設計真的做到了市場中性**，不像上一輪長多前10名策略的報酬混雜了大盤方向。
- **四期配對隨機控制組全部 100.0 百分位**——每一期都贏過全部 40 次「同樣換股時點/檔數/成本模型，只是隨機挑股票」的重抽。這是這次分析裡最重要的數字：**證明因子的橫截面排序能力是真的，不是隨機/巧合**，即使在 Train(月頻) 那期真實策略本身是虧錢的（−9.66%），隨機對照組虧得更慘（中位數期末權益倒賠 61.5%），說明「月頻多空機制本身」在那個期間對誰都不友善，但綜合分至少大幅減少了損失。
- **誠實的弱點，不是拿"贏隨機"當萬用擋箭牌**：Train(月頻) 的絕對報酬是真的負的（−9.66%/−1.73%年化），Sortino 也是負的（−0.028）。這代表月頻再平衡在 2015–2020 這段期間，即使因子排序能力還在（贏隨機對照組），也沒有轉換成真正賺錢的策略——跟上一輪 Cowork 指出的「贏隨機不等於這個用法有價值」是同一個道理，這裡不會因為其他三期數字好看就淡化這個負面結果。
- **相對而言，週頻表現更穩定**（四期中兩期都正報酬、Sortino 為正），**月頻在 Validation 期數字最亮眼但 Train 期最弱**——沒有一個再平衡頻率是「全面比較好」的，如實記錄兩種頻率的優劣互見，不挑對自己有利的講。
- **年化 alpha（+0.27% 到 +16.17%）比實際年化報酬普遍高**，因為 alpha 是迴歸截距，是「扣掉 beta 貢獻後」的部分，而 beta 本身是負的（放空腳結構性略強於做多腳，這點跟 `f_low_vol` 這個成分有關——低波動股票通常也是低 beta 股票，同時出現在多空兩腳的排序極端值，可能讓兩腳的平均 beta 不完全對稱），所以 alpha 略高於原始報酬本身也是一個誠實但需要進一步理解的現象，這裡先如實記錄數字，不過度解讀原因。

**已知限制（累積揭露）：**
- 宇宙覆蓋率 170/3,196（≈5.3%），非真正全市場逐檔掃描，見上方第2點的完整說明。
- 借券成本用未校準的 2%/年占位假設，沒有模擬強制回補風險。
- 只測了兩種再平衡頻率（週/月），沒有測更低頻（季）或波動率調整倉位。
- 因子成分（EPS成長/意外家族、營收意外、低波動）彼此的相關性/共線性上一輪已檢查過（`FACTORS.md`），但這次多空框架下沒有重新檢查是否因為多空兩腳的極端值分布而產生新的交互作用。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，全程沒有呼叫任何 holdout 相關函式。

**下一步：** commit + push 這輪修正。全市場覆蓋率的落差（170/3,196）留給使用者決定是否要繼續補（例如排進挖礦馬拉松的背景待辦，慢慢在流量許可時擴大樣本）。

---

## 2026-08-24T16:30:00+08:00 — Cowork 稽核多空中性結果：宇宙回補、跨期不一致調查、放空可行性

**Cowork 的評語**：近零 beta + 贏隨機對照 + 年化雙位數報酬，是這個專案第一個看起來像真 alpha 的結果，值得續查——但三關沒過，要求依序處理：(1) 宇宙覆蓋率太小（170/3,196）；(2) 月頻 train −9.66% vs val +66.5% 違反跨週期一致；(3) 空頭腳的放空可行性沒查過。**另外從這輪開始，使用者要求所有產出（文件/commit訊息/程式必要註解/終端說明）一律用繁體中文，不再用英文——這份記錄跟這輪新增的所有檔案都照辦。**

### 第 1 點：宇宙覆蓋率回補

新增 `backfill_universe.py`：可斷點續傳的全市場歷史回補腳本，進度存在 `research/data/backfill_state.json`（不進 git），每次呼叫處理一個有界批次，遇到連續限流就自動停止存檔、不空轉浪費時間。**這是一個橫跨多輪、甚至多天的背景任務，這次 session 沒有也不可能一次做完**——已經整合進 `MARATHON_PROTOCOL.md`（新增「5b. 宇宙全量回補」章節），列為 TW 軌現在最高優先序的工作單位，直到覆蓋率達到 80% 門檻之前優先於測新因子。

**這次 session 實際進度**：跑了第一批（300 檔上限），277 檔嘗試後撞到連續限流牆停止，本批新完成 198 檔，加上這次 session 之前跟馬拉松背景累積的資料，本機實際可用樣本達到 **223 檔**（≈7.0%，仍遠低於 80% 門檻）。**誠實標記：在覆蓋率明顯改善之前，本文件跟 `LEADS.md` 裡任何用當下樣本做的多空/decile 類回測結論，一律標記「樣本不足、暫不採信」**，只能當作探索性/診斷性的中間發現，不能當作可信的候選判定依據。

### 第 2 點：月頻 train/val 跨週期不一致調查

新增 `diagnose_monthly_inconsistency.py`，用當下已快取的樣本（跑的當下是 212 檔）把月頻多空的價差報酬逐月攤開來看：

| | 正報酬月數 | 平均月報酬 | 中位數 | 標準差 | 最差5個月合計貢獻 |
|---|---|---|---|---|---|
| TRAIN(月頻) | 45/72 | +1.35% | +1.27% | 5.03% | −38.50pp |
| VALIDATION(月頻) | 28/48 | +2.10% | +1.47% | 4.74% | −24.29pp |

**關鍵發現**：TRAIN(月頻) 逐月平均/中位數其實都是正的（跟原本用 170 檔算出來的複利總報酬 −9.66% 表面上矛盾），原因是複利機制對少數幾個極端壞月份（2019-12 −9.6%、2018-03 −8.8%、2017-08 −7.9%、2018-11 −6.7%、2017-02 −5.4%）特別敏感——這 5 個月合計 −38.5pp 的貢獻，遠超過整體平均報酬的量級，代表訓練期的複利結果被少數幾個月主導。換股名單穩定度也偏低（多頭腳相鄰月度重疊率平均 49.9%，空頭腳 56.2%，train 期只有 70 次月度換股決策點）——樣本規模小＋月頻換股次數少＋報酬分布右偏波動大，三個因素疊加，統計上本來就容易出現跨期方向不穩定，不需要假設是程式邏輯錯誤才能解釋。

**光看逐月統計還無法確定問題根源是「選股邏輯」還是「放空腳」，第 3 點的純多對照版本直接回答了這個問題（見下）。**

### 第 3 點：放空可行性 + 純多前decile可執行版本

**放空規則現況查證（網路搜尋，來源品質有限，非官方逐條確認）**：「平盤下不得放空」**不是**台股常態性的全面規則，是 2025 年 4 月市場劇烈波動（單日 930 多檔跌停）時金管會啟動的臨時限空令（收盤跌幅≥3.5%的股票隔日不得平盤下放空），已於 2025-05-26 撤除。常態性持續有效的放空限制是：股票必須列入可融資融券清單、且受融券限額（`ShortSaleLimit`）跟已用餘額約束。**這個結論不是官方公告逐條確認，是搜尋結果的間接歸納，之後若要真的執行放空策略，建議直接查 TWSE 官方公告核實。**

**融券資格實測查驗（`long_only_vs_market.py` 的 `check_shortability()`）**：對多空回測驗證期出現過的 174 檔空頭腳股票，逐一查 FinMind `TaiwanStockMarginPurchaseShortSale` 資料集。**結果：174/174 全部查不到資料，推估「不可空」100.0%。但這個數字不可信**——查驗當下 FinMind 額度仍處於限流狀態（同一時段的 `backfill_universe.py`／馬拉松都在撞牆），174 檔不可能真的全部沒有融資融券資格，這個結果幾乎肯定是查詢失敗被誤計成「查不到資料」，兩者在目前的程式邏輯裡無法區分。**誠實記錄：放空可行性目前沒有得到可信結論，需要在額度恢復後重新查驗，這是明確的待辦事項，不是這輪的結論。**

**純多前decile相對大盤（可實際執行、不依賴放空的版本）**：新增 `long_only_vs_market.py`，拿掉放空腳，只做多前 decile，基準改成 TAIEX 大盤指數本身（不是帶抽樣偏差的「同批買進持有」）。完整結果：

| 週期 | 年化報酬 | Beta(實測) | 年化Alpha | Sortino | 對大盤超額 | 隨機對照百分位 |
|---|---|---|---|---|---|---|
| Train (2015-2020) 週頻 | +24.12% | +0.692 | +17.78% | 1.425 | +193.31pp | **100.0** |
| Validation (2021-2024) 週頻 | +23.77% | +0.601 | +15.90% | 1.283 | +72.83pp | **100.0** |
| Train (2015-2020) 月頻 | +23.82% | +0.714 | +17.31% | 1.390 | +188.31pp | **100.0** |
| Validation (2021-2024) 月頻 | +33.67% | +0.611 | +25.12% | 1.694 | +151.39pp | **100.0** |

**這是這輪最重要的發現**：純多前decile在四期（train/val × 週/月頻）**全部一致強勁**，年化報酬 +23.77% 到 +33.67%，遠優於同期 TAIEX 本身（+54.58%～+58.86% 是六年/四年的總報酬，遠低於純多版本的年化複利效果），beta 落在 +0.6～+0.7（做多本來就該有的市場暴露，不是零，這裡沒有偽裝成市場中性）、alpha 仍然顯著為正、隨機對照組全部 100 百分位。**沒有出現多空版本裡 train/val 方向不一致的問題**——這強烈暗示第 2 點診斷出的跨期不一致，根源主要來自空頭腳（放空的後 decile）本身表現不穩定，不是綜合分選股邏輯（前 decile）有問題。**選股邏輯本身穩健；放空這個機制疊加上去之後才變得脆弱。**

### 綜合結論（誠實記錄，不誇大也不淡化）

1. **宇宙覆蓋率仍然不足（223/3,196，≈7.0%）**，所有多空/decile 結論依指示標記「樣本不足、暫不採信」，回補已排入馬拉松持續進行。
2. **月頻多空的 train/val 不一致，根源查到但沒有「修好」**——不是程式 bug，是小樣本＋放空腳高變異＋複利對極端月份敏感的疊加效應，跨週期一致關卡目前無法通過，多空框架維持降級/脆弱標記。
3. **放空可行性沒有可信結論**（查驗被限流污染），是明確待辦，不是這輪的結果。
4. **純多前decile相對大盤，是這輪最扎實的正面發現**：四期一致、實測 beta 合理（非零但可解釋）、alpha 顯著、贏過配對隨機對照組——**不靠放空，一樣有清楚的 alpha，而且比多空版本更穩健**。這個版本因為不需要放空，沒有融券資格/借券成本/強制回補的疑慮，是目前唯一「馬上可以真的執行」的版本雛形——但仍然受宇宙覆蓋率不足（第 1 點）的限制，一樣要標記「樣本不足、暫不採信」，等宇宙擴大後才能提升信心。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，全程沒有呼叫任何 holdout 相關函式。

**下一步：** commit + push 這輪。等宇宙回補（馬拉松持續進行）達到門檻、放空可行性重新查驗過，才能對多空/純多版本做更有信心的最終判定。

---

## 2026-08-24T16:55:00+08:00 — Cowork 三次覆核：付費方案調查、alpha/beta拆解、多空擱置為研究備選

Cowork 明確指出「純多前decile 是更穩健且可實際執行的方向，多空的放空腿在台股不穩又借不到券，先擱置為研究備選」，要求依序處理四件事。

### 第 1 點：解瓶頸——FinMind 付費方案調查 + yfinance 免費備援評估

**FinMind 付費方案（2026-08-24 官網實測查詢，完整表格）：**

| 方案 | 價格 | API/下載限制 | 資料集數 | 備註 |
|---|---|---|---|---|
| Free | $0 | 300次/小時（**註冊會員可提升至 600次/小時**） | 45種 | 目前這個專案用的方案 |
| Backer | $699/月 或 $5499/年 | 1,600次/小時 | 81種 | **含「台灣還原股價資料表」（FinMind 官方還原價，可能可以取代 `adjust.py` 自組邏輯，但這是後話，不影響這次的資料量瓶頸判斷）**；含單次下載特定日期所有股價/三大法人/融資券資料 |
| Sponsor（官網標示建議方案）| $999/月 或 $8888/年 | 6,000次/小時 | 96種 | 非商業用途授權 |
| Sponsor Pro | $3,330/月 或 $29,620/年 | 20,000次/小時 | 全部 | 商業授權（可整合進商業產品對外販售）|

單次付款、不自動扣款，到期自動失效；可隨時升級補差額（最低$100）。**這是金流/付費決策，不是我能替使用者決定或代為執行的事**（我不能輸入金融憑證、不能執行付款），只負責把資訊查清楚回報。

**用這次 session 實測到的速率換算完成全市場回補要多久**：全市場 3,196 檔 × 4 個資料集（價格/股利/財報/月營收）≈ 12,784 次呼叫（不含重試）。
- Free（600次/小時，需登入會員；這次 session 用匿名 `curl`/`requests` 沒有帶 token，實際額度可能比 600 更低，且跟馬拉松背景任務共用，這次 session 觀察到的實際窗口遠小於理論值——兩批回補分別在 277 次、16 次嘗試後就撞牆）：理論上限抓 12,784/600 ≈ **21.3 小時**的純呼叫時間，實際上因為額度窗口更小、跟馬拉松搶額度，**很可能要花好幾天**才能跑完，這是誠實推估，不是保證。
- Backer（1,600次/小時）：≈ **8 小時**。
- Sponsor（6,000次/小時）：≈ **2.1 小時**，一次性就能做完全市場回補。

**yfinance 免費備援評估（實測，不是猜測）**：
- ✅ 台股價格資料可用：`2330.TW` 抓 2010-2024 共 3,670 筆，含還原股價（`Adj Close`）、OHLCV，單檔約 1-7 秒，連續抓 5 檔沒有觀察到限流跡象。
- ❌ **完全不支援已下市股票**：實測 3 檔已下市股票（`1204.TW`／`1306.TW`／`0081.TW`）全部回傳「possibly delisted; no price data found」，連歷史資料都拿不到。**這代表如果用 yfinance 回補會系統性漏掉全部已下市股票（`universe.py` 的 222 檔），重新引入 `universe.py` 花大力氣處理過的存活者偏差問題**——這是嚴重限制，不是小問題。
- ❌ **財報資料歷史太短**：`yf.Ticker('2330.TW').quarterly_financials` 只有約 7 個季度的資料（Yahoo Finance 網站本身財報頁面的限制），遠不足以支撐 `score.py` 因子需要的 2015-2024 完整歷史。

**結論（誠實記錄）：yfinance 只能局部緩解，不是完整解方**——可以用來加速「現存股票的價格資料」回補（甚至可能比 FinMind 免費層快很多），但**無法**解決財報/月營收資料的瓶頸（因子計算的關鍵依賴），也**無法**用於下市股（存活者偏差處理的關鍵）。如果要用，只能是「價格資料的補充來源」，不能取代 FinMind 財報/月營收，也不能填補下市股缺口。

**這次 session 實際回補進度**：額度中途恢復過一次，立刻補跑一批，但很快（16 次嘗試）又撞牆。目前累積 **199/3,196（6.2%）**，遠低於 80% 門檻。`backfill_universe.py` 持續整合在 `MARATHON_PROTOCOL.md` 5b 節，是馬拉松 TW 軌現在最高優先序的背景任務。**在覆蓋率達到 80% 前，維持「樣本不足、不可採信」的標記，不會提前放寬。**

### 第 2 點：純多版本 alpha/beta 拆解（`decompose_alpha_beta()`，`long_only_vs_market.py` 新增）

方法：對每日淨值序列做 CAPM 迴歸拿到實測 beta，逐日算「純 alpha 報酬」= 策略當日報酬 − beta×大盤當日報酬（把系統性的大盤暴露部分扣掉），把這個序列複利成一條獨立的淨值曲線，在這條曲線上算年化報酬、Sortino、MDD——這樣才是回答「贏隨機是選股 alpha、不只是 beta」的直接證據，不是只看一個綜合的年化 alpha 數字。

**四期主結果（1x 成本）：**

| 週期 | Beta(實測) | 純Alpha年化 | Alpha Sortino | Alpha MDD |
|---|---|---|---|---|
| Train (週頻) | +0.692 | +17.24% | 1.717 | −12.32% |
| Validation (週頻) | +0.601 | +15.22% | 1.308 | −11.53% |
| Train (月頻) | +0.714 | +16.76% | 1.625 | −12.92% |
| Validation (月頻) | +0.611 | +24.31% | 1.965 | −13.10% |

**成本敏感度（純 alpha 報酬，1x/2x/3x，四期全部維持正值，沒有翻負）：**

| 週期 | 1x | 2x | 3x |
|---|---|---|---|
| Train (週頻) | +152.36% | +75.61% | +22.10% |
| Validation (週頻) | +72.51% | +35.37% | **+6.17%**（alpha_Sortino降到0.180，接近邊際） |
| Train (月頻) | +146.40% | +95.85% | +55.54% |
| Validation (月頻) | +131.10% | +98.89% | +71.08% |

**誠實解讀**：確認贏隨機對照組真的是選股 alpha，不只是搭上大盤順風車——四期的 alpha 都在合理的下檔風險（MDD 約 −11%~−17%）下維持顯著正值跟優異的 Sortino（多數 >1.0）。**但成本敏感度也誠實揭露了一個薄弱點**：Validation(週頻) 在 3x 成本假設下 alpha 已經相當薄弱（+6.17%，Sortino 只剩 0.180），不是全部組合在所有成本情境下都同樣穩健——**月頻的 alpha 對成本比週頻更有韌性**（換股次數少，摩擦成本累積得慢），這點跟前一輪發現的「月頻跨期不一致」放在一起看，兩者不衝突：alpha 存在且穩健，跟哪個再平衡頻率在扣成本後最划算，是兩個不同的問題。

### 第 3 點：全市場重跑純多版本——待第 1 點覆蓋率達標後才能做，這輪還不能做

誠實記錄：宇宙覆蓋率目前只有 6.2%，遠低於 80% 門檻，**這一步還不能開始**，留給馬拉松持續回補後的未來輪次。

### 第 4 點：多空市場中性版本標記調整

`LEADS.md` 的 `score_longshort_v1`（週頻/月頻）判定從「樣本不足、暫不採信」改為 **`PENDING`（放空可行性＋券源確認後再議）**——這個調整反映 Cowork 這輪的明確指示：多空版本先擱置為研究備選，不是繼續糾結覆蓋率問題（那是 `score_longonly_v1` 的主要限制），核心瓶頸是放空腿本身在台股的可行性沒有查清楚（上次因限流查驗失敗）。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，全程沒有呼叫任何 holdout 相關函式。

**下一步：** commit + push 這輪。等宇宙回補達到 80% 門檻，重跑純多前decile 看 alpha 是否仍成立（如實記錄，很可能會縮水）；放空可行性重新查驗（額度允許時）。全市場回補要不要考慮付費方案，留給使用者決定，這裡只負責把資訊查清楚，不會自己做金流決策。

---

## 2026-08-23T22:52:00+08:00 — 馬拉松排程診斷：有沒有在跑、多久跑一次、卡在哪（使用者要求）

**做了什麼：** 使用者懷疑「宣稱每 30 分自動跑，但實際輪次稀疏」，要求用 `schtasks`/`Get-ScheduledTask` 查真實排程狀態、判斷是否因「只在登入時執行＋電腦睡眠」而漏跑、確認每次觸發有沒有真的完成一輪並 push。同一輪也建立了上面的「心跳記錄」機制（第 1–25 輪回填）。

**排程本身的設定（`schtasks /query /tn AlphaMarathon /v /fo LIST` 原始輸出節錄）：**
```
Next Run Time:     2026/8/23 下午 11:00:35
Status:            Ready
Logon Mode:        Interactive only
Last Run Time:     2026/8/23 下午 10:30:36
Last Result:       -1073741510   ← 0xC000013A = STATUS_CONTROL_C_EXIT（行程被外部中止，不是程式崩潰）
Repeat: Every:     0 小時 30 分鐘
Stop Task If Runs X Hours and X Mins: 00:25:00
```
`Get-ScheduledTask` 補充：`MultipleInstances=IgnoreNew`（如果偵測到上一輪還在跑會直接略過這次，不會排隊）、`WakeToRun=False`（不會把睡眠中的電腦叫醒來跑）、`StartBoundary=2026-08-23T10:00:35`（這個排程本身是**今天早上 10:00 才重新註冊/生效**的，不是從很久以前就在跑）。

**Windows 工作排程器自己的詳細事件記錄（`Microsoft-Windows-TaskScheduler/Operational`）是關閉的**（`Get-WinEvent -ListLog` 確認 `IsEnabled=False`），所以沒辦法直接調閱「每一次觸發、每一次結果代碼」的完整歷史。改用兩個獨立、可交叉核對的來源重建真實時間軸：(1) `marathon_cycle.log`（`run-marathon-cycle.ps1` 自己寫的 start/end 時間戳＋claude 輸出），(2) `git log`（每輪真的做完事會 commit，時間戳來自 git，不受任何一方的敘述影響）。兩者逐筆比對完全吻合（見上方「心跳記錄」第 1–25 輪，每筆都有對應的 commit hash 或明確標記「無輸出」）。

**結論——有沒有在跑：大部分有，而且從中午之後非常穩定。** 從 11:30 到 22:30 這 11 小時裡，排程精準地每 30 分鐘觸發一次，一次沒有偏差超過 2 秒（`Get-ScheduledTask` 的 `StartBoundary` + 30 分鐘重複規則，跟 `marathon_cycle.log` 的實際時間戳完全對得上）。25 次觸發裡，22 次真的做完一輪工作並 commit+push（含 3 次是做全市場宇宙回補、不是測新因子，這次也照新規則一起補上心跳），**3 次（第 13、14、25 輪，16:30／17:00／22:30）觸發了、也成功搶到鎖檔，但從頭到尾沒有寫出任何內容就結束了**——`marathon_cycle.log` 只有開始時間戳、連一個字的輸出都沒有，git 也沒有對應 commit。

**卡在哪（誠實分兩塊，一塊查得到根本原因、一塊查不到）：**

1. **今天早上兩次漏跑（10:00、10:30）：** 已排除「電腦睡眠」這個原因——`powercfg /query SUB_SLEEP STANDBYIDLE` 查證目前 AC／DC 睡眠逾時都是 `0x00000000`（從不睡眠），這台機器本來就不會自己睡著。比較可能的解釋是：這個排程今天 10:00 才剛設定/重新註冊（`StartBoundary=2026-08-23T10:00:35`），而 `Logon Mode: Interactive only` 代表**沒有人登入 Windows 的時候，排程直接不會跑，不會排隊等**——如果使用者今天早上還沒登入電腦，10:00 跟 10:30 這兩次自然就跳過了，`11:11:42` 這次可能就是使用者登入後、`StartWhenAvailable=True` 幫忙補跑的第一次（不是精準對齊 :00/:30 的整點，時間點吻合這個推測）。**這個原因無法 100% 證實**（Windows 沒留下「這次因為沒登入而跳過」的可查記錄，Operational log 又是關的），但目前掌握的證據都指向這個方向，而不是「電腦睡著了」。

2. **3 次悄悄失敗（第 13/14/25 輪）：** 排程本身確實觸發了、也真的搶到鎖檔（`marathon_lock.py` 有寫入鎖檔），但接下來 headless `claude.exe` 行程在寫出任何東西之前就終止了。Windows 回報的結束代碼 `STATUS_CONTROL_C_EXIT` 通常代表行程是被外部強制中止（`TerminateProcess`），不是自己當機——這點也用 Windows「Application」事件記錄交叉核對過：今天完全沒有任何 `claude.exe` 的 Application Error（當機）事件，排除了程式自己壞掉的可能。**高度懷疑、但無法 100%證實的根本原因：資源（記憶體／CPU）競爭。** 這台機器同時有多個 `claude.exe` 行程在跑（含這個互動對話本身、以及一個從 8/22 就沒關過的舊終端機視窗），而第 13、14 輪（16:30、17:00）失敗的時間點，剛好完全對應這個互動對話正在做兩輪高強度 Cowork 稽核回應分析（16:24 跟 16:49 的 commit）——時間點高度重疊，但因為 Task Scheduler 的詳細記錄關閉了，沒辦法拿到「當時記憶體/CPU 用量」這種硬證據，只能誠實記錄成「高度懷疑、證據不完整」，不誇大成「已證實」。第 25 輪（22:30，這次診斷進行中發生的那次）沒有這麼明確的重疊解釋，留待觀察是否再發生。

3. **自我修復機制沒有失效：** 悄悄失敗的那一輪會留下沒釋放的鎖檔，但 `marathon_lock.py` 設計了 25 分鐘陳舊回收（`STALE_MINUTES=25`，剛好對齊 Task Scheduler 自己的 25 分鐘執行上限），所以最多delay 一輪（≈25–30分鐘），不會永久卡死——這點從第 13/14 輪失敗後、第 15 輪（17:30）照常成功執行就能證實。

**額外side finding（沒被問到，但攸關這些檔案的可信度，順便誠實記一下）：** `MARATHON_STATE.md`／本檔案幾條較新的敘事條目標成「2026-08-24」，但用 `git log --date=iso` 核對，那些 commit 實際的時間戳都是「2026-08-23」——是內容裡的日期標錯了一天，不是系統時鐘真的跳來跳去。**沒有回頭改舊條目的日期**（維持 append-only 紀律，不竄改歷史），只在這裡誠實指出這個落差，之後新寫的條目一律用 `git log`／系統時鐘核對過的正確日期。

**已完成、已內建進協定的後續補強：**
- `MARATHON_STATE.md` 最上面新增全局輪次計數器（見該檔案），`MARATHON_PROTOCOL.md` 第 0/6 節新增「每輪結束前，不管做了什麼都要在 `REPORT.md` 心跳記錄區塊插入一筆」的硬性步驟，並要求：如果 `marathon_lock.py acquire` 印出 `LOCK_STALE`（代表接手了一個陳舊鎖檔），這輪的心跳要順便註明「上一輪疑似失敗」——這樣以後再發生類似第 13/14/25 輪的悄悄失敗，**下一輪會自動在心跳留下痕跡，不需要每次都靠人工重新做一次這種診斷**。

**沒有做、刻意留給使用者決定的事：** 把排程改成「不需要登入也能跑」（Windows 的 S4U 登入模式）技術上可行，但需要把使用者的 Windows 密碼存進工作排程器——這是安全性相關的取捨，這裡沒有自己決定要不要換，只誠實說明目前限制是「使用者登入時才會跑」。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`（這輪純屬排程診斷跟文件維護，沒有碰任何資料抓取或策略程式碼）。

**下一步：** 觀察第 26 輪起心跳記錄是否正常運作、悄悄失敗的情況有沒有減少；如果之後又發生「觸發了但完全沒輸出」，先看新一輪心跳有沒有自動標註「上一輪疑似失敗」，不用重新從頭診斷一次。是否要把排程改成 S4U（不需登入也能跑）留給使用者決定。

---

## 2026-08-23T23:44:00+08:00 — Cowork 二次稽核（TRIALS_LEDGER 按日批次非30分節奏）：拿鐵證、抓到第4次即時失敗、嘗試修login限制被權限擋下

**背景：** Cowork 這輪稽核指出 `TRIALS_LEDGER.md` 17 筆試驗全部按「日期」批次、不是 30 分鐘節奏，8/23 之後沒有新輪，研判排程沒有真的自動跑。使用者要求：(1) 原文貼出 `schtasks /query` 結果，(2) 查證並修正「只在登入時執行＋睡眠」，(3) 心跳/編號（已於上一輪完成，這輪加強），(4) 讓它自己再跑 3 輪，貼出真實時間戳證明。

**先澄清 Cowork 稽核本身的一個誤判**：`TRIALS_LEDGER.md` 本來就只在「真的測了一個假說、跑出統計結果」才加列（見該檔案文件說明），今天 25 輪裡有一半以上是全市場宇宙回補／資料源基礎建設／PIT前置驗證，本來就不會產生 `TRIALS_LEDGER.md` 新列——這個檔案「稀疏」是設計上的正常現象，不是排程沒在跑的證據。**已在 `TRIALS_LEDGER.md` 開頭加註說明，指向 `REPORT.md` 心跳記錄，避免以後又被誤判。** 但這不代表 Cowork 的核心懷疑「排程真的有在按時跑嗎」不值得認真查——下面是認真查的結果，而且這次查證過程中真的**當場抓到第 4 次悄悄失敗**，比上一輪的診斷更進一步。

**1. `schtasks /query /tn AlphaMarathon /v /fo LIST` 原文（2026-08-23 23:35 執行）：**
```
Folder: \
HostName:                             IVEN-DASKTOP
TaskName:                             \AlphaMarathon
Next Run Time:                        2026/8/24 上午 12:00:35
Status:                               Ready
Logon Mode:                           Interactive only
Last Run Time:                        2026/8/23 下午 11:30:36
Last Result:                          -1073741510
Author:                               N/A
Task To Run:                          powershell.exe -ExecutionPolicy Bypass -File "C:\alpha\run-marathon-cycle.ps1"
Start In:                             C:\alpha
Comment:                              30-minute AI research mining marathon for the Alpha project. Runs research/MARATHON_PROTOCOL.md via headless Claude Code. Only runs while user is logged on.
Scheduled Task State:                 Enabled
Idle Time:                            Disabled
Run As User:                          user
Stop Task If Runs X Hours and X Mins: 00:25:00
Schedule Type:                        One Time Only, Minute
Start Time:                           上午 10:00:35
Start Date:                           2026/8/23
Repeat: Every:                        0 Hour(s), 30 Minute(s)
Repeat: Until: Duration:              9999 Hour(s), 59 Minute(s)   ← 見下方第3點，這個數字這輪被我自己的指令意外改壞過又修回來
Repeat: Stop If Still Running:        Disabled
```
`Last Run Time: 23:30:36` 這個時間點，剛好就是 23:30 那次觸發——**排程本身確實按表操課，不是完全沒在跑**，跟 Cowork「8/23後無新輪」的印象不同。但 `Last Result` 顯示 `-1073741510`（即 `STATUS_CONTROL_C_EXIT`），代表這次觸發**執行了、也已經結束了，但沒有成功**——見第 2 點的鑑識結果。

**2. 即時抓到第 4 次「觸發了但完全沒輸出」（第 27 輪，23:30）——比之前更完整的鑑識：**
- `marathon_cycle.log` 只有 `Marathon cycle start: 2026-08-23 23:30:37`，沒有任何內容、沒有 `end` 時間戳。
- 重複查詢 `schtasks`（間隔數分鐘）`Last Result` 值穩定不變——不是「還在跑、查詢時抓到中間狀態」，是真的已經跑完並失敗。
- 查了三個獨立來源都排除「程式自己壞掉」：(a) 今天 Application 事件記錄裡**唯一**一筆 Error 是 09:20 的 Dropbox.exe 當機，完全跟 claude.exe 無關；(b) `Get-MpThreatDetection` 沒有任何今天的 Windows Defender 偵測記錄（沒有被防毒軟體攔截的跡象）；(c) 查詢當下可用記憶體 10.3GB／總 31.4GB，不是嚴重吃緊（雖然無法排除失敗當下那一刻有短暫尖峰）。
- **關鍵新發現**：`run-marathon-cycle.ps1` 的結構是 `& $claudeExe ... | Add-Content` 之後**無條件**接著寫 `end` 時間戳——這代表如果只是 `claude.exe` 這個子行程自己當機或被殺掉，外層 `powershell.exe` 應該還是會繼續往下執行、把 `end` 寫進 log。**但四次失敗全部連 `end` 都沒有**，代表死掉的不只是子行程，是整個行程樹（`powershell.exe` 連同它啟動的 `claude.exe`）一起被中止的——這個模式比較像是 Task Scheduler 自己對這次任務執行做了「整棵樹砍掉」的動作，不像單純的子行程當機或被系統資源不足個別殺掉。
- **目前最合理、但仍未 100% 證實的假說**：這台工作排程器目前設定是 `Compatibility: Win7`（舊版相容模式）+ `MultipleInstances: IgnoreNew`（偵測到重疊執行就處理掉），舊版排程引擎在「上一個執行個體被異常中止、狀態沒有乾淨收尾」之後，對下一次觸發的重疊判斷可能進入不一致的邊界情況，把新觸發的整個行程樹提前砍掉。這跟「使用者登入時才執行」（`Logon Mode: Interactive only`）綁定的機制也有關聯——如果登入 session 有任何短暫的狀態變化（螢幕鎖定/解鎖、UAC 提示搶走焦點等），Interactive 型工作有可能連帶被中止，S4U 型工作則完全不依賴這個機制、理論上不會受影響。**這只是目前證據指向最合理的方向，不是已證實的根本原因**——Windows 工作排程器自己的詳細操作記錄（`Microsoft-Windows-TaskScheduler/Operational`）整台機器都是關閉的，沒辦法拿到「當時 Task Scheduler 內部為什麼決定要中止」的直接證據。

**3. 嘗試修「只在登入時執行」被權限擋下，途中一個小意外已經修好：**
- 上一輪診斷（22:52 條目）誤寫「S4U 需要存密碼」——**這是錯的，已在這裡訂正**：S4U（Service for User）模式的設計本來就不需要存密碼，這正是它跟一般「不論登入與否都執行＋存密碼」模式的差別。
- 嘗試用 `Set-ScheduledTask` 把 `LogonType` 改成 `S4U`：失敗，`Access is denied`（HRESULT 0x80070005）——這個操作需要系統管理員權限的 PowerShell，目前這個互動 session 沒有。
- 改用不需要系統管理員權限的舊版 `schtasks /change` 指令嘗試：也無法乾淨完成 S4U 切換（`/change` 指令一旦帶 `/RU`，會互動式詢問密碼，而這裡的執行環境沒有終端機可以回答，且**輸入使用者密碼本來就是這裡絕對不會做的事**，不管是不是互動式詢問）。
- **過程中的意外（已修好，誠實記錄）**：測試 `schtasks /change` 時，即使沒有主動去改「重複結束時間」，這個指令本身把 `Repeat: Until: Duration` 從原本近似「無限期」的 `87600 Hour(s)`（約10年）意外改成只剩 `218 Hour(s) 40 Min`（約9天）——**代表如果不修，馬拉松排程會在大約9天後自動停止重複，不會再繼續跑**。當場發現、當場用 `schtasks /change /ri 30 /du 9999:59`（CLI 允許的最大值，約 416 天／1.14 年）修回接近原本的效果，修完立刻用 `Get-ScheduledTask` 逐欄位核對其餘設定（`Task To Run`／`Comment`／`Start In`／`Stop Task If Runs...`等）都沒有被連帶改壞。**這也是為什麼這裡沒有再繼續用 `schtasks` CLI 硬試其他修法**——已經證明這個工具在這個場景下會有意料外的副作用，風險大於用它去改 `LogonType` 這種更敏感的設定。
- **結論：「登入才會跑」這個限制目前沒有修成，原因是缺少系統管理員權限，不是不知道怎麼修。** 需要使用者二選一：(a) 開一個系統管理員權限的 PowerShell 視窗，把下面這段指令貼進去執行一次（不需要輸入密碼）：
  ```powershell
  $p = New-ScheduledTaskPrincipal -UserId "user" -LogonType S4U -RunLevel Limited
  Set-ScheduledTask -TaskName "AlphaMarathon" -Principal $p
  ```
  (b) 或使用者自己打開「工作排程器」圖形介面 → 找到 `AlphaMarathon` → 內容 → 一般 → 選「不論使用者是否登入均執行」+ 勾選「不要儲存密碼」（這個組合在 GUI 裡就是 S4U，不需要輸入密碼）。**限制說明**：不管哪種做法，都還是需要 Windows 本身是開機狀態（不能是真正關機/休眠），這台機器目前已確認電源設定為「從不睡眠」，所以只要電腦開著、有插電或電量足夠，S4U 模式下即使使用者登出也會繼續跑。

**4. 讓它自動再跑 3 輪，貼真實時間戳：** 已啟動一個背景監控（等 `marathon_cycle.log` 累積到 3 筆新的 `Marathon cycle start`），**沒有用任何方式手動觸發**，純粹等排程自然在 00:00／00:30／01:00 左右自動觸發。這則條目先 commit + push；等 3 輪真的跑完，會另外補一條新記錄，貼出實際時間戳（`schtasks` 跟 `marathon_cycle.log` 交叉核對），回報給使用者。

**Holdout 複查：** `is_holdout_consumed()` 確認為 `False`（本輪純屬排程診斷/文件維護）。

**下一步：** 等 3 輪自動觸發完成後回報實際時間戳。系統管理員權限的 S4U 切換動作留給使用者執行（見上方指令）。持續觀察悄悄失敗的模式是否在 `Compatibility`/`MultipleInstances` 不變的情況下持續發生——如果使用者之後決定要更進一步排除 Task-Scheduler-端誤殺的假說，下一步可以考慮（需要使用者同意）把 `MultipleInstances` 從 `IgnoreNew` 改成 `Parallel`（重疊防護完全交給已經運作正常的 `marathon_lock.py` 檔案鎖），但這也需要系統管理員權限，這裡目前做不到。

---

## 2026-08-24T00:48:00+08:00 — 第 4 點回報：背景監控到 3 輪以上真實自動觸發，貼時間戳

**做了什麼：** 上一輪結尾啟動的背景監控（純被動等 `marathon_cycle.log` 累積新的 start 記錄，全程沒有手動觸發任何一輪）跑完，直接用 `grep` 拿完整原始 log 內容核對，不是憑印象轉述。

**`marathon_cycle.log` 原文（2026-08-23 22:30 之後）：**
```
===== Marathon cycle start: 2026-08-23 22:30:37 =====
===== Marathon cycle start: 2026-08-23 23:00:37 =====
===== Marathon cycle end:   2026-08-23 23:05:07 =====
===== Marathon cycle start: 2026-08-23 23:30:37 =====
===== Marathon cycle start: 2026-08-24 00:00:37 =====
===== Marathon cycle start: 2026-08-24 00:30:37 =====
===== Marathon cycle end:   2026-08-24 00:36:39 =====
===== Marathon cycle start: 2026-08-24 01:00:37 =====
```
交叉核對 `git log`（commit 時間戳，不受這份 log 檔案本身任何問題影響）：
```
23:04:53  8fb819d  馬拉松第26輪(TW軌): 全市場宇宙回補第四批 449->480/3196 (15.0%)
00:36:25  4c31509  馬拉松第28輪(TW軌): 全市場宇宙回補第五批，覆蓋率509->569/3196(17.8%)
```

**結論：連續 6 次觸發，間隔精準都是 30 分鐘（22:30 → 23:00 → 23:30 → 00:00 → 00:30 → 01:00），全程沒有人手動介入——這段時間這裡專注在使用者交辦的 App 十分制評分引擎任務，完全沒有碰過 `schtasks`／`marathon_cycle.log`／手動執行 `run-marathon-cycle.ps1` 這類指令。** 這就是使用者要的鐵證：排程本身千真萬確是自動、準時在跑，不是手動偽造的。

**誠實補充一個沒有完全解開的小疑點**：22:30／23:30／00:00 這三輪都沒有留下 `end` 時間戳（延續同一個「悄悄失敗」模式），但 00:00 這輪（第28輪）**其實有真的完成工作並成功 commit**（`4c31509`，00:36:25），只是它自己的 `end` 標記沒有寫進 log、而且完成時間（00:36）已經比一般正常輪次（通常 3–10 分鐘內結束）明顯長，也超過了工作排程器設定的 25 分鐘執行上限。**這代表「沒寫 end 標記」不能simply 100% 等同「這輪失敗、沒做出東西」**——第28輪就是反例：沒寫 end，但確實做完事、確實 commit 了。目前唯一能確定的解讀是：偶爾會有幾輪跑得比平常久很多（可能又撞到 FinMind 限流在重試），跟這裡稍早懷疑的「行程樹被中止」不一定是同一種情況，需要更多樣本才能分開兩種失敗模式，這裡誠實記錄成「未完全解開，需要更多輪觀察」，不推測成已經證實的結論。

**Holdout 複查：** `is_holdout_consumed()` 確認為 `False`（本輪純屬觀察記錄，沒有碰資料或程式碼）。

**下一步：** 持續累積心跳記錄樣本，觀察「有 commit 但沒 end 標記」跟「完全無輸出」這兩種模式是否真的是同一個根因、還是兩個不同問題；S4U 權限切換仍等待使用者用系統管理員權限執行。

---

## 2026-08-25T22:10:00+08:00 — 方法論修正與全面重新評分（criteria_v2：BH-FDR取代累積Bonferroni）

**這是使用者直接指示、互動 session 完成的工作，不是排程自動觸發的馬拉松輪次，所以沒有計入上面的心跳記錄／全局輪次計數器（那個機制專屬 `run-marathon-cycle.ps1` 的無人值守執行）。**

**背景**：使用者診斷出現行方法論四個問題正在扼殺發現——(1) 累積式 Bonferroni 跨軌共用分母、隨試驗數無限墊高門檻；(2) 因子檢定全是整段歷史無條件平均，沒做情境分群；(3) 策略級判定要求絕對報酬贏買進持有，門檻結構性過嚴；(4) 4個已PASS因子從未組成過多因子策略測試。完整任務規格見新增的 `METHODOLOGY_FIX_TASK.md`；這一輪只完成修正1（FDR重新評分）的第一步。

**做了什麼（依使用者給的精確步驟）**：
1. **步驟0 鎖定criteria_v2**：新增 `CRITERIA_V2_LOCK.md`，寫死 BH-FDR公式（q=0.10，三軌獨立分母，家族大小=同一假說去重後的最新測量數）、p值還原規則（p≈1−百分位/100，percentile=100.0時用N=200近似上界p≈0.005）、A/B分類規則（B類=train/val方向反轉／報酬集中少數期間／隨機優於策略／樣本<100，其餘為A類）、用詞紀律（新顯著只能標「待複驗候選CANDIDATE」不可標PASS）。**先單獨commit這個規則檔案（`645731d`），再開始套用規則重算**，避免看到結果後回頭調參數。
2. **步驟1 還原p值**：對 `TRIALS_LEDGER.md` 現有37筆試驗（TW軌16個去重後假說、FUT軌17個，US軌目前0個統計檢定試驗故跳過），從已記錄的百分位還原p值，全部可還原（沒有「無法重算需重跑」的情形）。
3. **步驟2 A/B分類**：TW軌13筆A類+2筆反轉（#3/#5，轉步驟4）+1筆B類（#10方法論本身有缺陷）；FUT軌12筆A類+5筆B類（#23/#29/#32/#36/#37，全部符合「隨機優於策略」或「報酬集中少數期間」）。
4. **步驟3 BH-FDR重新評分並產出對照表**（完整表格見 `TRIALS_LEDGER.md` 底部新增的「2026-08-25 FDR重新評分對照表」區塊，這裡只列結論）：
   - **TW軌（m=16，BH最大顯著k=10）：`f_value_pe`（#14，p=0.033，排名第10剛好卡進k=10）從「CHEAP_PASS批次過、累積Bonferroni降級為不確定」翻盤為「待複驗候選（CANDIDATE）」——本次唯一復活項。** 其餘原PASS/CHEAP_PASS/EXPERIMENTAL項目（#2/#7/#8/#9/#11/#12/#13/#15/#17）在FDR下全部維持穩健，原FAIL項目（#1/#4/#6/#10）維持不顯著。
   - **FUT軌（m=17，BH最大顯著k=1）：0筆復活。** 即使換成比累積Bonferroni寬鬆的方法，FUT軌22次策略試驗（含已通過便宜關卡但深挖(1b)證實樣本外失敗的`fut_basis_carry`）依然全部維持FAIL或不確定——這是誠實的陰性結果，不是方法沒套對，是FUT軌至今真的沒有測出站得住腳的訊號。
5. **步驟4 方向反轉試驗另案處理**：`f_foreign_streak`（#3）、`f_rel_strength`（#5）、`f_quality_roe_stability`深挖（#16/#17，TRAIN期絕對報酬負、VAL期正）三個train/val方向不一致的假說，**不套用FDR公式復活，轉入`METHODOLOGY_FIX_TASK.md`修正2規劃的情境依賴候選調查（市場位階/波動度/市值/流動性四組條件分群），這輪只做了分類標記，實際的情境分群IC還沒有算，是下一步工作**。
6. **同步更新**：`MARATHON_PROTOCOL.md`第2節多重比較校正規則正式改寫為FDR版本；`TW_LEADS.md` #2（`f_value_pe`）備註新增FDR重新評分結果跟判定更新；`MARATHON_STATE.md`新增「方法論重大修正」區塊記錄進度。

**誠實揭露（使用者要求，原文照登）**：本次重新評分是更換多重比較校正方法的結果，不是新證據——沒有重新抓資料、沒有重新跑隨機控制組。**`f_value_pe` 目前只是「待複驗候選（CANDIDATE）」，不是PASS，還沒有做情境分群檢驗跟成本敏感度，這兩關沒過之前不能進深挖清單、不能上架到App、更不能碰holdout。**

**下一步**：(a) 情境分群IC框架（`METHODOLOGY_FIX_TASK.md`修正2）——這是`f_value_pe`跟三個方向反轉候選要走的下一關；(b) `f_value_pe`的成本敏感度測試；(c) 策略級風險調整後判定標準（修正3）；(d) 四個PASS因子組成多因子策略（修正4）。FUT軌配額調降至20%輪次、TW軌宇宙覆蓋率繼續往80%補（目前56.9%）維持既有優先序不變。

**Holdout複查：** `is_holdout_consumed()` 確認為 `False`，本輪未觸碰任何holdout機制。

---

## 2026-08-26T00:00:00+08:00（互動 session）— 混合資料源架構上線，宇宙覆蓋率破80%，App即時算分補完

**這是使用者直接指示、互動 session 完成的工作，不是排程自動觸發的馬拉松輪次，不計入心跳記錄/全局輪次計數器。**

**背景**：使用者這輪開場先確認 FinMind 免費層已完全用盡（實測連 1 筆最小請求都直接 402），裁示四項優先序：(1) 解除資料源瓶頸（最高優先）；(2) 情境條件式因子檢驗；(3) 組合策略回測；(4) App 選股頁改即時算分。

**做了什麼（依優先序）**：

**(1) 資料源混合架構**：
- 新增 `yf_price_client.py`：yfinance 台股價量客戶端（`{代號}.TW`/`.TWO` 兩後綴皆試），`auto_adjust=True` 直接拿還原股價，免費無明顯流量限制。輸出額外附加 FinMind 相容欄位別名（`max`/`min`/`Trading_Volume`/`Trading_money`），讓 `factors.py::prepare_factors()`／`backtest/engine.py` 不用改就能吃這個新來源。`Trading_money` 是 `close*volume` 近似值（FinMind 原始是逐筆成交值加總），已在程式碼註解揭露這個近似。
- `adjust.py::adjusted_price_series()` 改為 yfinance 優先，原本的 FinMind 手動還原邏輯降為備援（yfinance 兩後綴都查無資料時才用，主要是較舊下市股）。
- 新增 `twse_t86_client.py`＋`backfill_t86.py`：三大法人買賣超改用 TWSE T86 端點（`www.twse.com.tw/rwd/zh/fund/T86`）為主，這個端點**支援任意歷史日期查詢**（實測驗證），且**按日期查詢一次涵蓋全市場**（跟 FinMind「一檔股票任意區間」相反的資料形狀），對回補全市場歷史反而更有效率。`factors.py::_institutional_daily_net()` 改成「T86為主、FinMind補缺口、FinMind也失敗則誠實留空」三層降級，不讓一個資料源失敗就讓整檔股票的其他因子一起報廢。
- **⚠️ 意外發現：TWSE T86 端點有自己的反爬蟲封鎖**，`backfill_t86.py` 第一次嘗試（0.4秒間隔）在約30次呼叫內就被封鎖（307 + 「FOR SECURITY REASONS」HTML頁，非JSON）。已加 `TWSEBlockedError` 明確偵測＋立刻停止（不重試，重試只會延長封鎖），呼叫間隔調高到2.0秒（未驗證是否足夠）。目前 T86 快取只有約36個交易日，遠遠不足以支撐三大法人相關因子的完整分析，這是誠實揭露的進行中限制，不是已解決。
- **實測確認 TWSE openapi（`t187ap05_L`月營收／`t187ap06_L_ci`綜合損益表）跟 MOPS 官方歷史查詢頁都無法取代 FinMind 的月營收/財報歷史**：前者只回傳最新一期全市場快照、無歷史區間查詢參數（curl 直接驗證，所有列的資料年月/出表日期都相同）；後者有反爬蟲防護擋下直接呼叫（`t21sc03_114_7_0.html` 回傳「FOR SECURITY REASONS...」）。**這兩類資料的歷史回補仍100%依賴FinMind**，額度用盡時已加降級處理（`factors.py::prepare_factors()`四個因子區塊、`score_v2.py::_revenue_yoy_latest()`/`_revenue_growth_12m()`都補上try/except，額度用盡時該項留空但不讓整檔/整批失敗）。
- `backfill_universe.py`：done 判定改成只看價格（財報/月營收變成盡力而為、不擋 done），`MAX_CONSECUTIVE_RATE_LIMITS` 15→60（新架構下舊門檻太容易被少數舊下市股連續失敗誤觸發提早停止）。**實測結果：一批560檔，7分鐘內新完成405檔（0檔需要FinMind、405檔財報/月營收額度用盡待補），宇宙覆蓋率從60.0%推進到81.3%（2597/3196），突破80%門檻。**

**(2)/(3) 情境條件式檢驗＋組合策略回測**：見下一則條目（`regime_conditions.py`執行結果，這輪同時進行，另開條目記錄避免混在一起）。

**(4) App選股頁即時算分**：新增 `realtime_asof.py::as_of_today()`——一個只在 `generate_scores_v2.py` 抓資料範圍內生效的 context manager，暫時把 `validation.holdout.VAL_END` 這個模組屬性拉高到今天。因為這個專案所有資料層讀取（`load_dev()`/`fetch_yf_adjusted()`/`institutional_daily_net_t86()`）都是「執行當下才 import/讀取 VAL_END」的設計（local import 或屬性存取，不是 import 時snapshot），這個機制能一次讓所有下游資料層讀到新邊界，離開 context manager 後立刻還原。**這不是繞過holdout**：`HOLDOUT_LOCK.json`／`is_holdout_consumed()`完全沒被碰，`score_v2.py`的`FACTOR_DEFS`權重維持凍結不變——這正是使用者2026-08-25裁示「凍結權重＋當前資料＝合法正式out-of-sample」字面上要求的機制。過程中額外發現並修好兩個真bug：(a) `basis`用今天日曆日期比對`d["date"]==as_of`，今天還沒收盤/沒資料時全部篩空，改用大盤序列實際最後一筆日期當基準日；(b) `score_v2.py::compute_scores_v2()`空結果時`pd.DataFrame([]).set_index()`崩潰（沿用`adjust.py`已修過的同類bug模式）。**已用5/8/15檔小樣本測試跑通全流程**（FinMind目前仍402，只驗證了管線不崩潰、能產出誠實的部分結果，還沒有跑滿300檔的正式版本並寫回`scores.json`）。

**Holdout複查：** `is_holdout_consumed()` 確認為 `False`，本輪未觸碰任何holdout機制（`realtime_asof.py`的機制本身經過設計特別確認不會、也不需要碰它，見該檔案docstring）。

---

## 2026-08-26T20:35:00+08:00（互動 session）— 組合策略回測 v2 專章：規格書、完整交易規則、誠實負面（但接近顯著）結果

**這是使用者直接指示、互動session完成的工作，不是排程自動觸發的馬拉松輪次，不計入心跳記錄/全局輪次計數器。同時間使用者裁示「暫停所有新單因子IC試驗」，已寫進`MARATHON_PROTOCOL.md`最上方，見該檔案。**

### 背景與規格

使用者這輪明確要求「這不是評分，是策略」，規格必須先寫死。完整規格見新增的
`research/PORTFOLIO_STRATEGY_SPEC.md`：20檔持股、月頻/季頻雙版本、15%停損、
單檔部位上限1/20、資格池新增流動性門檻（20日均成交金額後10%分位數排除）、全成本
（手續費0.1425%×2+證交稅0.3%+滑價+漲跌停鎖死無法成交）。因子組成兩版本：
A（`f_eps_growth`/`f_eps_surprise`合併/`f_revenue_surprise`/`f_low_vol`，4個已通過
因子去重成3成分）、B（A+`f_value_pe`待複驗候選，4成分）。三種加權：等權/IC加權/
情境條件式加權（**改用第83輪`f_rel_strength_regime_switch`同一個大盤位階bull/bear
開關**，不是稍早v1用的波動度維度）。

`backtest/engine.py`新增`rebalance_every_n_days`欄位（純加法擴充，`None`預設完全
比照舊行為，不影響任何既有呼叫端），讓月/季頻換股可以直接重用引擎既有的成本/停損/
漲跌停鎖死機制，不用重寫一份新引擎。

### 對照組（全部三個都做了）

(a) 配對式隨機選股對照組（同資格池/持股數/換股頻率，15次重抽——時間預算有限，
誠實揭露這個縮小的抽樣數，見程式碼註解）；(b) 買進持有加權指數TAIEX（VAL期總報酬
+54.58%，零成本不換股）；(c) CAPM回歸（`scipy.stats.linregress`）報告alpha/beta/
p值。

### 完整結果（VALIDATION期，2021-01-01～2024-12-31，12組合全部跑過完整版：
成本1x/2x/3x+15次隨機控制組；TRAIN期只跑快速版，見`data/portfolio_backtest_v2_quick_scan.csv`）

| 因子版本 | 加權 | 頻率 | 報酬 | MDD | Sortino | Sharpe | alpha(年化) | p值 | 買進持有大盤 | 隨機對照組percentile |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 等權 | 月 | +45.32% | -14.40% | 0.707 | 0.826 | +5.48% | 0.320 | +54.58% | 93.3 |
| A | 等權 | 季 | +56.10% | -10.97% | 0.802 | 0.958 | +8.11% | 0.176 | +54.58% | 100.0 |
| A | IC加權 | 月 | +49.18% | -13.56% | 0.795 | 0.906 | +6.70% | 0.226 | +54.58% | 93.3 |
| **A** | **IC加權** | **季** | **+68.33%** | **-8.41%** | **1.029** | **1.218** | **+10.40%** | **0.053** | +54.58% | 100.0 |
| A | 情境加權 | 月 | +64.55% | -12.69% | 1.053 | 1.177 | +9.82% | 0.066 | +54.58% | 100.0 |
| A | 情境加權 | 季 | +49.49% | -14.92% | 0.740 | 0.926 | +7.23% | 0.197 | +54.58% | 93.3 |
| B | 等權 | 月 | +43.65% | -12.93% | 0.747 | 0.848 | +5.15% | 0.307 | +54.58% | 93.3 |
| B | 等權 | 季 | +55.14% | -10.60% | 0.812 | 0.979 | +7.79% | 0.167 | +54.58% | 93.3 |
| B | IC加權 | 月 | +53.57% | -13.03% | 0.855 | 0.995 | +7.37% | 0.161 | +54.58% | 100.0 |
| **B** | **IC加權** | **季** | **+68.42%** | **-8.65%** | **1.036** | **1.219** | **+10.26%** | **0.053** | +54.58% | 100.0 |
| B | 情境加權 | 月 | +61.69% | -12.21% | 0.952 | 1.106 | +9.15% | 0.094 | +54.58% | 100.0 |
| B | 情境加權 | 季 | +46.77% | -13.38% | 0.713 | 0.873 | +6.28% | 0.255 | +54.58% | 86.7 |

（成本1x/2x/3x敏感度、TRAIN期同一批12組合的快速版數字，見兩份CSV：
`data/portfolio_backtest_v2_results.csv`（VAL完整版）、
`data/portfolio_backtest_v2_quick_scan.csv`（TRAIN+VAL快速版，24組合）。）

### 依使用者裁定的評判順序逐項檢查

1. **淨利與MDD是否達標**：✅ 全部12組合、TRAIN+VAL兩期，報酬皆為正，MDD介於
   -8.4%～-18.7%（TRAIN較深，VAL較淺），沒有失控。
2. **Sortino**：季頻+IC加權（兩個因子版本皆約1.03）跟月頻+情境加權（A版1.053）
   是最佳組別，等權版本全部墊底（0.71~0.96）。
3. **alpha顯著性（p<0.05）**：**全部12組合都沒有嚴格通過**，但兩個表現最好的
   組合（A/B兩版的「IC加權+季頻」）**p值都是0.053，只差一點點沒有跨過0.05這條線**
   ——這是這輪最重要的誠實結果：不是隨便一個組合接近顯著，是**評判順序前段
   （淨利/MDD/Sortino）已經篩出來的最佳候選同時也最接近顯著**，比一個隨機組合
   剛好壓線更值得後續追蹤，但**依規則仍是不顯著，不能算通過**。
4. **Sharpe**（放最後）：季頻+IC加權兩版本最高（1.218/1.219），跟Sortino排名一致。
5. 勝率未計算（使用者明確排除）。

### 使用者特別要求的判讀原則：報酬輸買進持有但MDD明顯更低，也算有價值

**這輪的結果不需要動用這條原則就已經站得住腳**——「A/IC加權/季頻」跟「B/IC加權/
季頻」兩組合的絕對報酬（+68.33%/+68.42%）本身就**贏過**買進持有大盤（+54.58%），
同時MDD（-8.41%/-8.65%）遠優於一般個股集中投資組合的典型波動；等權版本裡表現
最弱的「A/等權/月頻」（+45.32%）雖然報酬略輸大盤，但MDD（-14.40%）跟大盤本身
的下檔風險相比並不誇張（大盤同期未計算MDD，這點留待下一步補上，見「已知限制」）。

### 參數敏感度（月頻 vs 季頻，等權 vs IC加權 vs 情境加權）

- **季頻穩定優於月頻**：12組合中季頻的Sortino/Sharpe/alpha三項指標幾乎全面優於
  對應的月頻版本（只有「情境加權」是例外，月頻>季頻）——季頻換手率低、交易成本
  拖累少，可能是主因（`cost_3x`欄位顯示月頻版本在3倍成本下報酬打折更重）。
- **IC加權/情境加權皆優於等權**：等權版本在兩個頻率下都是三種加權法裡Sortino
  最低的，符合直覺（4個成分裡`f_low_vol`跟`f_eps_growth`系列的IC本來就比
  `f_revenue_surprise`強不少，等權會稀釋掉這個差異）。
- **IC加權 vs 情境加權互有勝負**：季頻下IC加權完勝情境加權（1.029 vs 0.740）；
  月頻下情境加權完勝IC加權（1.053 vs 0.795）——沒有一種加權法在兩種頻率下都
  贏，這本身是誠實的訊號，不是挑對頻率就能通吃。
- **納入f_value_pe（版本B）影響很小**：A/B兩版本在同一組（加權,頻率）下的數字
  幾乎一樣（例如IC加權+季頻：A報酬+68.33% vs B+68.42%，差距在雜訊範圍內）——
  `f_value_pe`目前的IC權重（0.0533）在四個成分裡本來就偏低，加不加對結果影響有限，
  這也解釋了為什麼「待複驗候選」納入與否不是這次結果的關鍵變因。

### 權益曲線描述（`data/equity_curve_*.csv`，未進git，本機保留）

- **A/IC加權/季頻**（最佳候選之一）：VAL期(2021-01-04～2024-12-31，971個交易日)
  權益穩定爬升，25/50/75%時間點權益分別是106.3萬/115.8萬/146.1萬（初始100萬），
  **最大回撤發生在samples的最後一天（2024-12-31）**，代表這個策略目前正處在它
  歷史上最深的回撤點，不是中途穩定後才拉回——這點在「這個策略會失效的情況」一節
  進一步討論。
- **A/情境加權/月頻**：同期間權益路徑類似（25/50/75%: 108.2萬/116.1萬/150.3萬），
  但最大回撤發生在**2021-05-17**（VAL期開頭附近，-12.69%），之後大致穩定爬升到
  期末。兩者的回撤時機完全不同，暗示兩種加權機制對市場狀態的敏感度不同。

### 誠實的「這個策略會在什麼情況失效」討論（使用者要求的專章內容）

1. **alpha未達顯著，樣本外的說服力本質上有限**：p=0.053不是p=0.005，這代表用
   80檔驗證樣本、4年VALIDATION期的資料量，還不足以排除「這組報酬是運氣」的可能性
   在傳統5%門檻下。如果之後用更大樣本（`TW_MARATHON_STATE.md`已達81.3%全市場
   覆蓋率，這次沒有重新抽樣驗證）重跑後p值不進反退，應該視為這個策略本身邊際、
   不穩健的證據，而不是樣本問題。
2. **等權版本明確弱於IC/情境加權，代表「不知道怎麼加權」時這個策略不值得做**：
   如果使用者對三個成分的相對重要性沒有信心去用IC或情境加權（例如擔心IC加權是
   拿樣本內資料訓練出來的權重，某種程度上仍是「看過答案」），退回等權版本後
   Sortino/alpha都明顯轉弱，這個策略的吸引力主要建立在「敢用IC加權」這個判斷上。
3. **季頻優於月頻的結論建立在目前的成本假設上**：如果實際手續費折扣更低（使用者
   目前假設0.1425%全額，未打折）或滑價實際上更大（`DEFAULT_SLIPPAGE_BPS`本身
   是未經校準的估計值，見`validation/costs.py`），月頻的相對弱勢可能被放大或
   縮小，這個排序不是永久成立的物理定律，是這組成本假設下的結果。
4. **IC加權的權重本身是靜態的、用同一批train+val資料算出來的**：嚴格來說這不是
   「純粹樣本外」的權重設計——雖然沒有動用holdout，但IC加權用的數字（`FACTOR_DEFS`
   風格的靜態常數）是拿VALIDATION期本身的IC回頭訂出來的，某種程度上VAL期的
   「表現」跟「用來加權的資訊」有重疊，這是IC加權版本看起來比等權好的一部分原因，
   不是完全乾淨的樣本外測試。**這是這輪分析的一個方法論限制，誠實揭露，不是
   隱藏起來的漏洞。**
5. **這個策略在大盤持續空頭、且情境加權判斷錯誤的時期會特別脆弱**：`f_value_pe`
   跟`f_revenue_surprise`在空頭/高波動狀態下IC反而較強（見`REGIME_CONDITIONS.md`），
   但這個策略的情境加權版本目前只切換大盤位階(bull/bear)一個維度，如果空頭期正好
   撞上這兩個成分本身也失靈的環境（例如系統性流動性危機），情境加權不會有額外
   保護，跟其他版本一樣暴露在同樣風險下。
6. **樣本仍是100檔（80檔可用）驗證樣本，不是81.3%的全市場覆蓋率**：見
   `PORTFOLIO_STRATEGY_SPEC.md`第8節已揭露的限制，這裡重申——這是下一步最高
   優先的複驗方向。

### 判定與下一步

**判定：不通過（`FAIL`，依alpha顯著性這關），但兩個最佳組合（IC加權+季頻，
A/B兩版本皆p=0.053）明確標記為「接近顯著、值得追蹤」而非直接否決封存。**
未達成使用者裁定的評判順序第3關，**不構成holdout候選，未觸碰、也不需要問是否
解鎖holdout**。完整數字見`LEADS.md`新增的`portfolio_multifactor_v2`列。

**建議下一步（不會自己動手，留給使用者決定優先序）**：(a) 用81.3%覆蓋率的全市場
樣本重跑「IC加權+季頻」這一組合，看p值是否隨樣本擴大而改善；(b) 如果要驗證IC加權
是否有「用train怎麼看val」的隱性洩漏疑慮，可以測試「只用TRAIN期算出的IC權重，
套用到VAL期」這個更嚴格的樣本外版本；(c) 大盤本身同期MDD/Sortino的計算補上，
讓「MDD明顯更低」的判讀有一個明確的數字基準可以對照，不是質化描述。

**Holdout複查：** `is_holdout_consumed()` 確認為 `False`，本輪未觸碰任何holdout機制。

---

## 📚 教訓章節（使用者2026-08-26晚指示新增，這是本檔案第一次開這個專節）

**這個章節收錄跨候選、可重複套用的方法論教訓，不是單一候選的執行記錄——單一候選
的完整數字仍然只記在它自己原本的條目跟`LEADS.md`，這裡只提煉「下次遇到類似情況
要記得的規則」，避免同一個坑跨候選重複踩。**

### 教訓1：「贏隨機控制組」失敗時，先拆解報酬來源，不要只看百分位數字本身

**案例：`weinstein_stage2_pilot_v1`（2026-08-22，`LEADS.md`第一列）。** 判定
`FAIL`（隨機控制組僅24.5百分位，沒打贏）。使用者這輪覆核後給出的診斷：**成本
敏感度本身是穩健的（1x/2x/3x下策略都維持正報酬），但選股本身沒有alpha——報酬
主要來自兩個非選股來源**：(a) **大盤閘門**（加權指數200日均線總體開關，任何時候
指數在均線之下就整體出場，這是市場擇時/beta管理，不是「這支股票比那支股票更值得
持有」的選股判斷）；(b) **期間漂移**（試點涵蓋的2015-2024期間大盤本身長期向上，
剛好處在這個窗口就會有正報酬，跟選股邏輯無關）。**這兩者疊加起來造成「絕對報酬
好看，但換掉是隨機挑股票、同樣的大盤閘門/期間，結果差不多甚至更好」——這正是
隨機控制組百分位低的真正原因，不是引擎/回測機制有錯（`audit_ledgers.py`當時已經
確認交易記錄本身乾淨）。**

**規則（下次遇到類似情況要做的事）**：一個策略「贏了隨機控制組」不能只看總報酬
數字，一定要問「控制組本身跟真實策略是不是共用同一套市場擇時機制（大盤閘門/
只在特定期間交易）」——如果共用，那麼控制組沒打贏，代表擇時機制本身可能就是
主要的報酬來源，選股排序沒有貢獻，這時候的正確診斷不是「這個因子/策略沒用」
而是「這個因子/策略的選股部分沒有被證明有用，市場擇時部分才是報酬引擎」，
兩者要分開報告，不能混為一談算成同一個候選的功勞。**這正是`portfolio_backtest_v2.py`
（2026-08-26晚）為什麼要同時報告「(a)配對式隨機控制組百分位」跟「(c)對大盤回歸
的alpha/beta/顯著性」兩件事、不能只看其中一個的原因**——beta本身（`portfolio_multifactor_v2`
的beta落在+0.33~+0.40）代表策略確實承擔市場暴露，alpha（扣掉這個beta貢獻後剩下的
部分）才是真正該歸功於選股的部分，這正是把`weinstein_stage2_pilot_v1`的教訓正式
制度化進回測規格的具體做法，不是空泛的原則。

**保留紀錄，不重新判定**：`weinstein_stage2_pilot_v1`的`FAIL`判定本身正確，不需要
重跑或改判——這次覆核是加深對「為什麼FAIL」的理解，不是推翻原判定。
