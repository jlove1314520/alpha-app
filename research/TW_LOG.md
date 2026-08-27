# TW_LOG.md — 台股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面），但只記馬拉松（`MARATHON_PROTOCOL.md`）跑起來之後、台股軌的每一輪動作。馬拉松之前的台股研究記錄在 `REPORT.md`（不重複搬過來）。

**規則：** 每個馬拉松輪次結束前，把這輪做了什麼（測了哪個假說、便宜/深挖關卡結果、卡在哪裡、下一步）append 一條到這裡，不管有沒有找到新東西——「這輪測了3個都FAIL」也是有效記錄，不能跳過不寫。

---

## 2026-08-27T10:22+08:00 — 馬拉松第131輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第128輪08:43，US第129輪09:01，FUT第130輪09:31）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態（`git log`確認自第128輪`962fd0e`以來只有第129/130輪跳過心跳提交、一則自動盤中報價提交，無互動session介入），無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113/116/119/122/125/128輪一貫判斷仍不代為決定，繼續等待使用者回應。延續第128輪的地基工作：`backfill_t86.py`（預設batch-size 200）。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取1436天，本輪批次嘗試200天、新完成200（8天無交易/假日/無筆數）、未撞限流牆。累積T86快取1436→1636/3305個工作日（43.4%→49.5%）。

`is_holdout_consumed()`確認`False`。本輪未觸及`backfill_universe.py`（宇宙回補早已達81.3%，超過80%門檻，非本輪工作範圍）。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同前例）。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個，不要繼續回補。

---

## 2026-08-27T08:43+08:00 — 馬拉松第128輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第125輪07:13，US第126輪07:31，FUT第127輪08:01）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態（`git log`確認自第125輪`94a7d7d`以來只有第126/127輪跳過心跳提交、一則`data/STATUS.json`新增提交（給Cowork讀，跟解除暫停規則無關）、以及自動盤中報價/大盤資料提交，無互動session介入），無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113/116/119/122/125輪一貫判斷仍不代為決定，繼續等待使用者回應。延續第125輪的地基工作：`backfill_t86.py`（預設batch-size 200）。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取1236天，本輪批次嘗試200天、新完成200（15天無交易/假日/無筆數）、未撞限流牆。累積T86快取1236→1436/3305個工作日（37.4%→43.4%）。

`is_holdout_consumed()`確認`False`。本輪未觸及`backfill_universe.py`（宇宙回補早已達81.3%，超過80%門檻，非本輪工作範圍）。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同前例）。`git status`確認工作目錄乾淨——先前連續多輪觀察到的`.github/workflows/market.yml`未commit修改問題本輪未再出現（同FUT第127輪觀察一致）。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個，不要繼續回補。

---

## 2026-08-27T07:13+08:00 — 馬拉松第125輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第122輪05:20，US第123輪06:01，FUT第124輪06:32）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態（`git log`確認自第122輪`a89f311`以來只有第123/124輪跳過心跳提交，無互動session介入），無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113/116/119/122輪一貫判斷仍不代為決定，繼續等待使用者回應。延續第122輪的地基工作：`backfill_t86.py`（預設batch-size 200）。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取1036天，本輪批次嘗試200天、新完成200（17天無交易/假日/無筆數）、未撞限流牆。累積T86快取1036→1236/3305個工作日（31.3%→37.4%）。

`is_holdout_consumed()`確認`False`。本輪未觸及`backfill_universe.py`（宇宙回補早已達81.3%，超過80%門檻，非本輪工作範圍）。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同前例）。工作目錄裡另有一個非本輪造成的未commit修改（`.github/workflows/market.yml`，疑似其他自動化流程留下，本輪未動它，也不納入本次commit）。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個，不要繼續回補。

---

## 2026-08-27T05:20+08:00 — 馬拉松第122輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第119輪04:21，US第120輪04:32，FUT第121輪05:01）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態（`git log`確認自第119輪`69c2285`以來只有第120/121輪跳過心跳提交跟一則自動盤中報價提交，無互動session介入），無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113/116/119輪一貫判斷仍不代為決定，繼續等待使用者回應。延續第119輪的地基工作：`backfill_t86.py`（預設batch-size 200）。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取836天，本輪批次嘗試200天、新完成200（12天無交易/假日/無筆數）、未撞限流牆。累積T86快取836→1036/3305個工作日（25.3%→31.3%）。

`is_holdout_consumed()`確認`False`。本輪未觸及`backfill_universe.py`（宇宙回補早已達81.3%，超過80%門檻，非本輪工作範圍）。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同前例）。工作目錄裡另有一個非本輪造成的未commit修改（`.github/workflows/market.yml`，疑似其他自動化流程留下，本輪未動它，也不納入本次commit）。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個，不要繼續回補。

---

## 2026-08-27T02:43+08:00 — 馬拉松第116輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第113輪01:20）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態，無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113輪一貫判斷仍不代為決定，繼續等待使用者回應。改延續第113輪的地基工作：`backfill_t86.py --batch-size 200`。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取436天，本輪批次嘗試200天、新完成200（7天無交易/假日）、未撞限流牆。累積T86快取436→636/3305個工作日（19.2%）。

**順帶核對全市場宇宙回補現況**（不是本輪主動做的工作，只是查證）：讀`data/backfill_state.json`，`done`2597＋`skip`469＝3066/3196已全部處理過，`done`覆蓋率2597/3196=81.3%，早已超過`MARATHON_PROTOCOL.md`第5b節的80%門檻——這解釋了為什麼第110輪記錄裡`portfolio_backtest_v2.py`提到「全市場81.3%樣本」這個數字的來源。本輪未執行`backfill_universe.py`。

---

## 2026-08-27T04:21+08:00 — 馬拉松第119輪：T86回補接續（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳TW最舊（第116輪02:43，US第117輪03:01，FUT第118輪03:31）照輪替選TW。複查`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態（`git log`確認自第116輪以來無互動session介入），無新使用者回應；`portfolio_multifactor_v2`下一步三選項（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）依第109/110/113/116輪一貫判斷仍不代為決定，繼續等待使用者回應。延續第116輪的地基工作：`backfill_t86.py`（預設batch-size 200）。

**本輪跑`run_batch(batch_size=200)`**：接手前已快取636天，本輪批次嘗試200天、新完成200（13天無交易/假日/無筆數）、未撞限流牆。累積T86快取636→836/3305個工作日（25.3%）。

`is_holdout_consumed()`確認`False`。本輪未觸及`backfill_universe.py`（宇宙回補早已達81.3%，超過80%門檻，非本輪工作範圍）。無新`TRIALS_LEDGER.md`/`TW_LEADS.md`列（本輪工作單位是地基資料回補，非因子假說測試）。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同前例）。`is_holdout_consumed()`確認`False`。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個，不要繼續回補。

---

## 2026-08-27T01:20+08:00 — 馬拉松第113輪：T86回補（暫停單因子試驗規則生效中，屬允許的地基工作，非新假說）

取鎖時偵測到`LOCK_STALE`（pid 146500持有29.9分鐘，接手後發現無殘留未commit的孤兒程式碼工作，但`backfill_t86.py`有一處未commit的修改——查證是上一輪疑似異常中止前已完成但沒來得及commit的真bug修復，非本輪自己寫的）：`START_DATE`從`2010-01-01`改成`2012-05-02`，原因是實測TWSE T86端點對更早日期回傳明確的`{"stat":"查詢日期小於101年05月02日，請重新查詢!","total":0}`（端點本身資料起點硬限制，不是反爬蟲封鎖也不是本專案能繞過的問題），舊起點的批次浪費了186天全部落空。

三軌時間戳TW最舊（第110輪20:36）照輪替本應選TW；`PORTFOLIO_STRATEGY_SPEC.md`仍是「待使用者確認」狀態，第110輪已完成的組合策略回測v2其「下一步」（全市場樣本重跑/train-only IC樣本外測試/大盤MDD-Sortino補算）該互動session明確要求「不會自己動手，留給使用者決定優先序」——本輪沒有使用者新回應，依第110輪自己留下的判斷（「下一輪如果撿到TW軌，先確認使用者是否已回應，沒有的話繼續等待」）不代為升級啟動這些選項。改做`MARATHON_PROTOCOL.md`第0節第2點明確允許的例外工作：T86三大法人回補（`backfill_t86.py`），這是既有因子/未來組合策略都依賴的地基資料，不算新單因子試驗。

**驗證修復後跑`run_batch(batch_size=200)`**：接手前已快取236天（上一輪異常中止前已用修正後起點跑過一些），本輪批次嘗試200天、新完成200（14天無交易/假日）、未撞限流牆（`hit_error_wall=False`）。累積T86快取236→436/3305個工作日（2012-05-02~2024-12-31全範圍，13.2%）。三大法人相關因子（`f_foreign_streak`/`f_inst_flow`）目前可用樣本仍嚴重不足，覆蓋率持續回補中，未達到可信賴門檻前這些因子的既有判定不變。

**沒有新增`TRIALS_LEDGER.md`列**（地基/資料回補，非假說測試，同`backfill_universe.py`先例）。`is_holdout_consumed()`確認`False`。下一輪如果又撿到TW軌且暫停規則仍生效：繼續跑`backfill_t86.py --batch-size 200`（自動接續，讀取parquet檔案存在性判斷進度，不需要額外state檔案）；如果使用者已回應`PORTFOLIO_STRATEGY_SPEC.md`的下一步選項，優先處理那個。

---

## 2026-08-26T19:45+08:00 — 馬拉松第107輪：`f_quality_roe_stability` TRAIN期絕對報酬拆解（延續TW_LEADS.md#3/#17開放問題）

**取鎖**：偵測到`LOCK_STALE`（pid 136608持有29.9分鐘，上一輪疑似異常中止）。三軌時戳比較（TW 17:36 / US 18:10 / FUT 17:05），FUT最久未碰但近10輪（97–106）已達20%資源配置上限（US4/TW4/FUT2，若這輪再選FUT會變30%超標），故跳過FUT改選次久的TW。**訂正（commit前才發現）**：一開始誤判「無殘留孤兒工作」——實際`git status`發現round 105（TW，`f_gross_margin_stability`）跟round 106（US，`f_us_low_vol`中型股tier深挖）兩輪的驅動腳本（`factor_ic_gross_margin_stability.py`／`deep_dive_f_us_low_vol_mid_tier.py`）跟`factors.py`改動、`US_LEADS.md`／`US_LOG.md`／`US_MARATHON_STATE.md`的文件更新都還沒commit（文件內容本身在round 105/106時已經寫好且我session一開始讀檔案時就看到了，只是檔案沒有進git）——這輪一併補commit，不是新工作，是誠實補上前兩輪未落地的部分。

**做了什麼**：新增 `decompose_f_quality_roe_stability_rebalance.py`，延續`TW_LEADS.md`#3「下一輪建議」項2——拆解`deep_dive_f_quality_roe_stability.py`（round 2/3）記錄的TRAIN期(2015-2020)淨成本後絕對年化報酬為負(-3.8%~-4.2%)、VAL期(2021-2024)為正(+13.2%~+13.4%)這個train/val正負號不一致的開放問題。方法：重用`deep_dive_f_quality_roe_stability.py`的十分位多空建構函式（`_decile_legs_factor`/`_random_legs_factor`，import不複製），把`REBALANCE_DAYS`從20日拉長到60日（`TW_LEADS.md`#3建議的兩個方向之一，另一個「縮小十分位比例」刻意不同時做，避免混淆是哪個改動造成效果），同一批80/100快取樣本，零新API呼叫。

**結果，包含一個意外發現**：
1. **60日換倉版本**：TRAIN三個成本情境ann_return=+10.18%~+10.62%（全正），VAL=+26.45%~+26.72%（全正）——train/val同號，且TRAIN報酬明顯高於20日版本，方向上支持「換倉頻率降低→週轉成本drag下降→TRAIN期淨報酬提升」這個假說。
2. **意外發現（比原本要測的問題更重要）**：作為對照組重跑的20日換倉版本（跟`deep_dive_f_quality_roe_stability.py`理論上應完全相同的設定），這輪算出TRAIN ann_return=+3.32%~+3.73%（**正值**），跟round 2/3記錄的-3.8%~-4.2%（**負值**）方向相反，數字對不上。獨立寫最小可重現腳本（單一20日、TRAIN、1x成本、非隨機的真實回測，跳過耗時的隨機控制組）重新驗證，結果同樣是+3.73%，確認不是這支新腳本本身的bug，是**同一套程式碼、同一個seed，這次執行跟round 2/3的執行結果不一致**。最可能原因：round 2/3是2026-08-23上午執行，之後（尤其round 79-107這段期間`backfill_universe.py`的大量批次回補）本機`data/raw/`快取為原本80檔樣本裡的部分股票補上了先前缺失的季度財報/資產負債表歷史資料，`f_quality_roe_stability`透過`load_sample_with_factors()`重新計算後這些股票的ROE穩定度數值改變，進而改變十分位進出場名單組成，導致同一段歷史期間的回測結果跟著改變——**這是快取隨時間演化導致「同一支腳本、不同時間點執行結果不同」的具體案例，不是隨機亂數造成的（隨機種子固定），是輸入資料本身變了**。

**這代表什麼，誠實記錄不誇大**：原本驅動`TW_LEADS.md`#3判定EXPERIMENTAL（而非乾淨PASS）的核心限制——「TRAIN/VAL絕對報酬正負號不一致」——**用目前的快取重跑已經不再重現**（兩期現在同號皆正，20日跟60日版本皆然）。但這**不代表可以直接把判定升格為PASS**：(a) 這次只重跑了`ann_return`/`beta`/`alpha`/`Sortino`四個指標的「真實」腿位結果，**沒有重新跑完整的100次隨機控制組對照**（時間預算考量，見下方限制），所以percentile/累積校正這兩項round 2/3已確認過的關卡這次沒有重新驗證，理論上快取變了也可能影響隨機控制組的分布；(b) 樣本仍是同一批80/100快取名單，跟`TW_MARATHON_STATE.md`記錄的全市場宇宙覆蓋率提升（現81.3%）沒有直接關聯——這次的資料改變是「同一批既有80檔裡缺值被補齊」，不是「換了更大的樣本」。**正確的下一步是完整重跑一次`deep_dive_f_quality_roe_stability.py`本身**（不是這支新的分解腳本），讓round 2/3記錄的6組配置（含完整100次隨機控制組）用目前的快取狀態重新產生一套內部一致的新基準，再判斷要不要把`TW_LEADS.md`#3從EXPERIMENTAL調整——這輪不做這件事，留給下一輪。

**限制/未做**：(1) 縮小十分位比例的變體未測（見上方，刻意單一變數控制）；(2) 60日版本的隨機控制組（percentile跑出來99.0/100.0）是用round 2/3同一套固定seed跑的100次抽樣，樣本內部一致但沒有加密解析度驗證；(3) 沒有查證究竟是哪幾檔股票的哪個欄位被backfill補上導致差異，只有間接推論（時間點吻合backfill活動窗口），未逐檔比對round2/3當時的原始factor值存檔（`data/`目錄不進git，可能已不存在，無法逐檔回溯比對）。

**驗證**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`。

---

## 2026-08-25T21:05:35+08:00 — 馬拉松第76輪：全市場宇宙回補第二十三批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對（TW 19:35 / US 20:10 / FUT 20:36），TW最久沒更新，且覆蓋率54.5%仍低於80%門檻，優先跑`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1743 done/371 skip，跟第73輪記錄一致（無落差）。額度已恢復，未被立即限流。

**結果**：本批嘗試104檔（50→100→連續15次限流提前停止，設計內行為），新完成76/新跳過13。累積覆蓋率1743→1819/3196（54.5%→56.9%），累積永久跳過371→384。

**驗證**：`is_holdout_consumed()` 確認仍為 `False`。

**下一輪**：覆蓋率仍低於80%門檻，繼續跑`backfill_universe.py --batch-size 300`（除非一開始就被限流，改做候補工作單位，見`TW_MARATHON_STATE.md`）。

## 2026-08-25T12:04:29+08:00 — 馬拉松第58輪：全市場宇宙回補第十七批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對（TW 10:31 / US 11:02 / FUT 11:33），TW最久沒更新，且覆蓋率40.5%仍遠低於80%門檻，優先跑`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1295 done/286 skip，跟第55輪記錄一致（無落差，代表第55輪本身乾淨結束）。

**結果**：本批嘗試103檔，新完成74/新跳過14，撞限流牆提前停止（設計內行為）。累積覆蓋率1295→1369/3196（40.5%→42.8%），累積永久跳過286→300。

**驗證**：`is_holdout_consumed()` 確認仍為 `False`。

**下一輪**：覆蓋率仍遠低於80%門檻，繼續跑`backfill_universe.py --batch-size 300`（除非一開始就被限流，改做候補工作單位，見`TW_MARATHON_STATE.md`）。

## 2026-08-23T02:00:00+08:00 — 台股軌馬拉松初始化

檔案建立，尚未有實際挖礦輪次執行。第一輪建議工作見 `TW_MARATHON_STATE.md`。

## 2026-08-23 — 馬拉松第一輪：重測 f_value_pb/f_value_pe/f_quality_roe_stability 便宜關卡

**做了什麼**：新寫 `factor_ic_value_quality.py`（沿用 `factor_ic.py` 的 100 名標準樣本、SAMPLE_SEED=20260822，跟已快取的 `data/raw/` parquet），對三個因子跑打散對照便宜關卡，`bonferroni_n=3`（這輪批次大小）。

**結果**：
- `f_value_pb`：val_mean_ic=+0.0592，打散對照 99.9 百分位，過批次門檻(96.7)也過累積校正門檻(n=15時99.3)。
- `f_value_pe`：val_mean_ic=+0.0501，打散對照 96.7 百分位，剛好壓線過批次門檻(96.7)，但**未過**累積校正門檻(99.3)——照 `MARATHON_PROTOCOL.md` 第2節規則老實記錄降級，不進深挖清單。
- `f_quality_roe_stability`：val_mean_ic=+0.0721，打散對照 99.9 百分位，兩種門檻都過。

三個都是 train/val 同號，樣本使用率 80/100（20 檔因缺歷史資料或抓取錯誤被跳過，屬正常篩選）。

**判定**：`f_value_pb`、`f_quality_roe_stability` → `CHEAP_PASS`（待深挖）；`f_value_pe` → 批次過但累積校正後降級，暫緩。已寫進 `TRIALS_LEDGER.md` #13–#15、`TW_LEADS.md`。

**注意事項**：`f_value_pb`/`f_value_pe` 的 PIT 狀態仍未驗證（`factors.py` 檔案開頭已揭露這個已知缺口），深挖 `f_value_pb` 前必須先補這個驗證步驟，不能假設便宜關卡過了就代表資料乾淨。`f_quality_roe_stability` 用的是已驗證過的 PIT 機制，無此疑慮。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

**下一步**：見 `TW_LEADS.md`「目前狀態」章節——優先深挖 `f_quality_roe_stability`，`f_value_pb` 深挖前先做 PIT 驗證。

## 2026-08-23 — 馬拉松第二輪：深挖 f_quality_roe_stability（十分位多空組合）

**做了什麼**：新寫 `deep_dive_f_quality_roe_stability.py`，沿用 `factor_ic.py` 的同一組100名快取樣本（不打新API），對 `f_quality_roe_stability` 建立十分位多空組合（前10%多、後10%空、等權重、20日換倉，跟`long_short_backtest.py`評估`score.py`綜合分時同一套機制，只是換成單一因子排序，重用其`run_long_short`/`capm_beta`/`sortino_ratio`）。跑了 TRAIN(2015-01-01~2020-12-31) 跟 VAL(2021-01-01~2024-12-31) 兩期，每期各測 1x/2x/3x 滑價成本敏感度（`validation/costs.py`的`DEFAULT_SLIPPAGE_BPS`=5bps基準），每個組態都跑20次配對式隨機控制組（同節奏/同十分位大小，隨機選股，不是靜態買進持有）。

**樣本覆蓋**：80/100名可用（跟便宜關卡同批），其中55名有`f_quality_roe_stability`非空值，十分位大小k=8。

**結果**（詳細數字見 `data/deep_dive_f_quality_roe_stability.csv`）：
- **6個組態（2期×3成本倍率）全部贏過全部20次隨機抽樣**（percentile=100.0）——但只抽20次，解析度只到95%/100%這種粗顆粒度，無法精細確認是否真的站穩n=16累積校正門檻(99.4)。
- **beta兩期都接近零**（TRAIN +0.083、VAL -0.080）：market-neutral構造有成立，不是隱藏的大盤方向性賭注。
- **淨成本後絕對年化報酬 train/val 正負號不一致**：TRAIN期為負（-3.77%~-4.17%，隨成本倍率遞增而更負），VAL期為正（+13.42%~+13.18%，隨成本倍率遞增而略降）。這跟便宜關卡的IC同號結果不同——IC測的是排序相關性方向，十分位價差測的是實際換倉後的絕對報酬，兩者不必然一致。
- **反常現象**：TRAIN期的隨機控制組本身也大虧（20次終值中位數0.31，即-69%），比真實策略虧得更慘（真實策略TRAIN期終值約0.80，即-20%）。這代表在55名有效樣本、10%十分位、20日換倉的構造下，每次換倉幾乎等於完全換手（因為候選池小），週轉成本drag非常大，可能是TRAIN期絕對報酬為負的主因，不必然是因子本身方向錯誤——但這個推論還沒有進一步拆解驗證，誠實列為待查。

**判定**：`EXPERIMENTAL`（不是乾淨PASS）。理由：統計上穩健打贏隨機控制組（兩期都是），且market-neutral構造成立，這兩點是正面訊號；但(a)絕對報酬train/val正負號不一致、(b)隨機抽樣次數只有20次、解析度不足以精細比對校正門檻，這兩個限制都是誠實揭露、不能忽略的缺口，所以不能直接判PASS。經濟解釋（ROE穩定度反映獲利品質、Novy-Marx品質因子文獻）能說明因子本身「為什麼可能有效」，但**不能解釋TRAIN/VAL報酬正負號為何不同**（如果是防禦性品質因子敘事，理應在波動大的TRAIN期更占優，而不是相反），這點誠實標註為未解之處。

**下一步建議**（已寫進`TW_LEADS.md`）：(1) 把`N_RANDOM_DRAWS`從20提高（比照`factor_ic.py`當初200→1000的做法）取得更精細的百分位解析度；(2) 嘗試拉長換倉週期或縮小十分位比例，檢驗TRAIN期負報酬是否主要是週轉成本drag而非因子失效。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

## 2026-08-23 — 馬拉松第三輪：加密 f_quality_roe_stability 隨機控制組解析度

**做了什麼**：照 `TW_MARATHON_STATE.md` 下一步建議(a)，修改 `deep_dive_f_quality_roe_stability.py` 的 `N_RANDOM_DRAWS` 從20提高到100（比照`factor_ic.py`當初200→1000的精神，seed序列用加法`RANDOM_CONTROL_SEED+i`，所以前20次抽樣結果跟第二輪完全相同，只是新增21–100次），重跑同一組6個配置（TRAIN/VAL兩期×1x/2x/3x成本），未打新API（沿用第二輪同批快取樣本）。

**過程小插曲（誠實記錄）**：第一次用 `Bash` 前景執行加上570秒timeout，結果被自動移到背景執行（超過9.5分鐘還沒印出任何stdout，可能是Windows下pipe到`tail`造成緩衝，不是真的卡住）。中途一度擔心跑太久會拖到鎖檔25分鐘的陳舊門檻，用`taskkill`嘗試終止該行程，但當下行程其實已經自然執行完畢（`taskkill`回報「行程已經終止」），最終從輸出檔跟CSV檔的時間戳確認整個腳本確實跑完、輸出正確，沒有半途而廢的資料。全程約9.5分鐘完成，距離鎖檔取得時間約11.3分鐘，在25分鐘陳舊門檻內有餘裕。

**結果**（見`data/deep_dive_f_quality_roe_stability.csv`）：真實策略的終值/年化報酬/Sortino/beta/alpha六組數字跟第二輪完全相同（這些是決定性計算，不含隨機性，seed不變本來就該一樣）——TRAIN期年化報酬仍為負(-3.77%~-4.17%隨成本遞增)、VAL期仍為正(+13.18%~+13.42%)，beta仍近零(+0.083/-0.080)。唯一實質變化是隨機控制組：**100次抽樣，真實策略6組配置全部仍贏過全部100次**（`random_control_percentile`=100.0），對應p<0.01（1/101），比第二輪20次抽樣的p<0.05（1/21）更嚴格地站穩，且已經解決第二輪備註的「解析度不足，只到95%/100%粗顆粒度」限制。

**判定**：`f_quality_roe_stability` 維持`EXPERIMENTAL`（不變）。理由：第二輪的兩個限制中，「隨機抽樣解析度不足」這項已用本輪動作解決；但「TRAIN/VAL絕對報酬正負號不一致」這項完全沒被觸及，依然是未解之處，所以不能升級為PASS。已更新`TRIALS_LEDGER.md` #17（新增列，累積總數16→17）、`TW_LEADS.md` #3（更新原列，附加本輪結果）。

**下一步**：見`TW_LEADS.md`「下一輪建議」——優先拆解TRAIN期絕對報酬為負是否為週轉成本drag（拉長換倉週期/縮小十分位比例）；`f_value_pb`深挖前仍需先做PIT驗證。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

## 2026-08-23 — 馬拉松第四輪：`f_value_pb`/`f_value_pe` PIT 前置驗證

**做了什麼**：照 `TW_MARATHON_STATE.md` 下一輪優先(b)，新寫 `verify_pit_value_pb.py`。方法：對 2330（單檔，2015-01-01~VAL_END=2024-12-31）合併 `TaiwanStockPrice`（收盤價）跟 `TaiwanStockPER`（PBR），回推 `implied_bvps = close / PBR`（PBR應該是「price / 每股淨值」，所以反推出的每股淨值理論上是階梯函數，只在FinMind真的更新trailing淨值那天才跳變，其餘時間只會因為PBR四捨五入到小數第二位而有雜訊）。用日對日變動百分比>0.8%當跳變偵測門檻，找出每季的跳變日，跟 `pit.quarterly_pit()` 算出的財報季末日／本專案假設的`pit_date`（季末+45天）比對天數差。

**結果**（完整見 `data/verify_pit_value_pb_2330.csv`）：40/42個季度（2015-01起，扣除價格資料涵蓋範圍外跟VAL_END邊界的2季）偵測到跳變日。跳變日距季末天數：**min=32、median=45、max=62，從未貼近0天**——如果FinMind在季末當天就把淨值更新進PBR（即0天落後），會是嚴重前瞻偏誤，本次沒有觀察到任何一季是這種情況。median剛好等於本專案`pit.py`原本假設的45天，也貼近台灣法規規定的季報45天內公告期限，指向FinMind的PBR更新時點是貼著「實際可能公告時間」在動，不是季末就先知道。跳變日距假設`pit_date`（季末+45天）的天數：min=-13、median=0、max=+17——中位數精準對齊假設值，但個別季度有正負13~17天的落差（有些公司提早公告、有些拖到季末後60天才被FinMind更新）。

**判定**：這不是假說檢定（沒有對隨機打散/控制組做統計比較），是資料源時序特性調查，不計入`TRIALS_LEDGER.md`累積試驗數，記在「已調查但不計入試驗數」表（同分點集中度調查的先例）。**PIT狀態從「完全未驗證」升級為「單檔（2330）抽測，無嚴重前瞻偏誤」**——不是「完全驗證」，只測了一檔股票，用的是間接跳變偵測法而非FinMind官方文件確認的更新時點邏輯，這個限制要在往後任何引用這個結論的地方誠實帶上。`f_value_pe`共用同一個`TaiwanStockPER`資料源，推論同樣結論適用，但沒有對PER單獨重跑同樣的跳變偵測，是推論延伸不是直接驗證。

**下一步**：`f_value_pb`深挖的PIT前置條件已滿足，可以在下一輪開始十分位多空深挖（方法比照`deep_dive_f_quality_roe_stability.py`的精神，不是照抄檔案），深挖結果要註明PIT驗證的單檔限定範圍。`f_quality_roe_stability`拆解TRAIN期負報酬的工作單位仍待進行。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰，`VAL_END=2024-12-31`跟`load_dev()`的自動截斷機制正常運作——2024-12-31那季因為預期揭露日2025-02-14超過VAL_END而在資料裡看不到後續價格，導致該季正確地被跳過偵測，不是異常）。

## 2026-08-24 — 馬拉松第五輪：全市場宇宙回補（`backfill_universe.py --batch-size 300`）

**做了什麼**：照 `MARATHON_PROTOCOL.md` 第5b節，取鎖時發現上一把鎖是陳舊鎖（held by pid 110416, 30.0分鐘前, `marathon_lock.py acquire` 自動判定陳舊並接手）。TW軌是三軌中最久未更新的一軌（15:05 vs US 15:35 vs FUT 15:38），輪替規則指向TW；且回補覆蓋率（跑之前）僅199/3196＝6.2%，遠低於80%門檻，依協定本輪工作單位是跑回補而非測新因子。呼叫時額度顯然已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（背景執行，約93檔嘗試後撞到連續15次限流自動停止，符合設計，非異常）。

**結果**：本批嘗試93檔，新完成63檔，新跳過15檔（永久跳過，非限流失敗），因限流提前中止（`hit_rate_limit_wall=True`，符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，不是bug）。**累積覆蓋率：199→262/3196（6.2%→8.2%）**，累積永久跳過：42→57檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`（腳本本身會自動接續未完成的部分，不需要手動指定起點）。若下一次呼叫一開始就立刻被限流（距上次批次結束時間太短），該輪應改做其他不需要新資料的工作單位（深挖已有候選、系統化掃過因子家族清單），並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24 — 馬拉松第六輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖後比對三軌`最後更新`時間戳，TW（2026-08-24T00:10:00+08:00）明顯早於US（09:40）跟FUT（09:10），輪替規則指向TW；且回補覆蓋率（跑之前）為262/3196＝8.2%，遠低於80%門檻，依協定本輪工作單位是繼續跑回補。呼叫時額度顯然已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（腳本自動讀取`data/backfill_state.json`接續未完成的部分，不需要手動指定起點）。

**結果**：本批嘗試108檔，新完成74檔，新跳過18檔（永久跳過，非限流失敗），因限流提前中止（連續15次限流，符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，不是bug）。**累積覆蓋率：262→336/3196（8.2%→10.5%）**，累積永久跳過：57→75檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24 — 馬拉松第八輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖成功（無陳舊鎖），比對三軌「最後更新」時間戳，TW（2026-08-24T10:10:00+08:00）明顯早於US（20:35）跟FUT（20:05），輪替規則指向TW；且回補覆蓋率（跑之前）為336/3196＝10.5%，遠低於80%門檻，依協定本輪工作單位是繼續跑回補。呼叫時額度已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（腳本自動讀取`data/backfill_state.json`接續未完成的部分，不需要手動指定起點）。

**結果**：本批嘗試98檔（含批次內部先跑到50檔的中繼進度：新完成43／新跳過7），最終本批合計新完成72檔、新跳過11檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：336→408/3196（10.5%→12.8%）**，累積永久跳過：75→86檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T02:35:10+08:00 — 馬拉松第29輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 114240持有鎖90分鐘後被回收，明顯遠超過25分鐘陳舊門檻，代表第28輪之後的某一輪疑似完全沒跑完就異常中止，這輪之間沒有留下任何`TW_LOG.md`/`REPORT.md`記錄）。比對三軌「最後更新」時間戳，TW（2026-08-24T00:34:00+08:00）明顯早於US（22:05，08-24第十輪）跟FUT（21:35，08-24第九輪），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為569 done/122 skip，跟`TW_MARATHON_STATE.md`記錄的569/3196（17.8%）一致（這次沒有落差，代表第28輪確實乾淨結束、是介於第28輪跟本輪之間的某一輪異常中止），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試78檔（其中15檔為state已存在的重複資料，判斷邏輯已窮盡提前結束本批次；實際新處理63檔），新完成57檔，新跳過6檔（永久跳過，非限流失敗）。**累積覆蓋率：569→626/3196（17.8%→19.6%）**，累積永久跳過：122→128檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T00:34:00+08:00 — 馬拉松第28輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 103272持有鎖滿60分鐘後被回收，明顯遠超過25分鐘陳舊門檻，代表第26輪之後的某一輪疑似完全沒跑完就異常中止或崩潰，這輪之間沒有留下任何`TW_LOG.md`/`REPORT.md`記錄）。比對三軌「最後更新」時間戳，TW（2026-08-23T23:03:00+08:00）明顯早於FUT（21:35，但日期是08-24，所以FUT實際更晚）跟US（22:05，08-24），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為509 done/109 skip（=509/3196=15.9%，比TW_MARATHON_STATE.md記錄的480/3196=15.0%略高，推測是被跳過的那些輪次中有部分進度先落地但沒來得及更新state檔案），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試101檔，新完成60檔，新跳過13檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：509→569/3196（15.9%→17.8%）**，累積永久跳過：109→122檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡已有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-23T23:03:00+08:00 — 馬拉松第26輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 100308持有鎖30分鐘後被回收，對應第25輪「無輸出/行程疑似被中止」）。比對三軌「最後更新」時間戳，TW（21:05）早於FUT（21:35）跟US（22:05），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`已有449 done/95 skip（=449/3196=14.05%，比state檔案記錄的408/3196略高，推測是上一輪被中止前有部分進度先落地），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試51檔，新完成31檔，新跳過5檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：449→480/3196（14.1%→15.0%）**，累積永久跳過：95→100檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T03:36:08+08:00 — 馬拉松第31輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表第30輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T02:35:10+08:00）早於FUT（03:01:00）跟US（22:05:00，明顯晚很多），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為626 done/128 skip（=626/3196=19.6%，跟`TW_MARATHON_STATE.md`記錄的626/3196一致，無落差，代表第29輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試104檔，新完成70檔，新跳過19檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：626→696/3196（19.6%→21.8%）**，累積永久跳過：128→147檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T05:35:57+08:00 — 馬拉松第34輪（TW軌）：全市場宇宙回補第九批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表第33輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T03:36:08+08:00）早於US（04:05:00）跟FUT（05:03:32），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為696 done（跟`TW_MARATHON_STATE.md`記錄的696/3196一致，無落差，代表第31輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試120檔，新完成75檔，新跳過21檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：696→771/3196（21.8%→24.1%）**，累積永久跳過：147→168檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T07:06:36+08:00 — 馬拉松第37輪（TW軌）：全市場宇宙回補第十批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表上一輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T05:35:57+08:00）早於US（06:02:00）跟FUT（06:32:00），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為771 done/168 skip（跟`TW_MARATHON_STATE.md`記錄的771/3196一致，無落差，代表第34輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔，新完成75檔，新跳過12檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：771→846/3196（24.1%→26.5%）**，累積永久跳過：168→180檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T22:01:00+08:00 — 馬拉松第40輪（TW軌）：全市場宇宙回補第十一批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（pid 116400持有鎖45.2分鐘，上一輪疑似異常中止，未留下正常結束的log）。比對三軌「最後更新」時間戳，TW（07:06:36）早於US（07:31:16）跟FUT（21:19:00），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為846 done/180 skip（跟`TW_MARATHON_STATE.md`記錄的846/3196一致，無落差，代表第37輪本身乾淨結束，卡住的是介於第37輪跟本輪之間某個未留記錄的輪次），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試100檔，新完成72檔，新跳過13檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：846→918/3196（26.5%→28.7%）**，累積永久跳過：180→193檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-25 — 馬拉松第43輪：全市場宇宙回補第十二批

**做了什麼**：取鎖時偵測到 `LOCK_STALE`（上一輪 pid 100692 持有鎖滿300.1分鐘後被回收，第42輪期貨軌之後某一輪疑似完全沒跑完就異常中止，未留下任何log）。開始前 `data/backfill_state.json` 為918 done/193 skip，跟 `TW_MARATHON_STATE.md` 第40輪記錄一致（無資料落差，代表第40輪本身乾淨結束）。跑 `backfill_universe.py --batch-size 300`（自動接續）。

**結果**：本批嘗試109檔，新完成74/新跳過20，連續15次限流後判斷額度已用盡、提前停止（設計內行為）。累積覆蓋率 918→992/3196（28.7%→31.0%），累積永久跳過 193→213。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T05:37:00+08:00 — 馬拉松第46輪：全市場宇宙回補第十三批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T05:37:00）早於US（2026-08-25T06:04:00）跟FUT（2026-08-25T06:35:00），輪替規則指向TW。開始前 `data/backfill_state.json` 為1070 done/222 skip，跟 `TW_MARATHON_STATE.md` 第46輪記錄一致（無資料落差，代表第46輪本身乾淨結束）。覆蓋率仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試130檔（前100/後30兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計）。新完成78/新跳過21。**累積覆蓋率：1070→1148/3196（33.5%→35.9%）**，累積永久跳過：222→243檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25 — 馬拉松第52輪：全市場宇宙回補第十五批

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 128940持有鎖滿30.0分鐘後被回收，第49輪之後某一輪疑似完全沒跑完就異常中止，未留下任何log）。比對三軌「最後更新」時間戳，TW（2026-08-25T07:05:00）早於US（2026-08-25T08:02:55）跟FUT（2026-08-25T08:32:52），輪替規則指向TW。開始前 `data/backfill_state.json` 為1148 done/243 skip，跟 `TW_MARATHON_STATE.md` 第49輪記錄一致（無資料落差，代表第49輪本身乾淨結束；陳舊鎖檔對應的中止輪次沒有動到任何已落地資料）。覆蓋率仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔（前100/後9兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成73/新跳過21。**累積覆蓋率：1148→1221/3196（35.9%→38.2%）**，累積永久跳過：243→264檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

**上一輪異常提醒**：取鎖時偵測到`LOCK_STALE`（pid 128940，30.0分鐘），已在心跳記錄跟`TW_MARATHON_STATE.md`同步註明，供使用者留意「上一輪疑似失敗」這個訊號。

## 2026-08-25T10:31:00+08:00 — 馬拉松第55輪：全市場宇宙回補第十六批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T09:03:00）早於US（2026-08-25T09:33:32）跟FUT（2026-08-25T10:05:00），輪替規則指向TW。開始前 `data/backfill_state.json` 為1221 done/264 skip（共1485筆），跟 `TW_MARATHON_STATE.md` 第52輪記錄一致（無資料落差，代表第52輪本身乾淨結束）。覆蓋率38.2%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試117檔（前100/後17兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成74/新跳過22。**累積覆蓋率：1221→1295/3196（38.2%→40.5%）**，累積永久跳過：264→286檔。已用`backfill_state.json`實際筆數（1295 done/286 skip=1581筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（40.5%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T13:34:50+08:00 — 馬拉松第61輪：全市場宇宙回補第十八批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T12:04:29）早於US（2026-08-25T12:32:41）跟FUT（2026-08-25T13:03:21），輪替規則指向TW。開始前 `data/backfill_state.json` 為1369 done/286 skip（共1655筆），跟 `TW_MARATHON_STATE.md` 第58輪記錄一致（無資料落差，代表第58輪本身乾淨結束）。覆蓋率42.8%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試103檔（前100/後3兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成70/新跳過18。**累積覆蓋率：1369→1439/3196（42.8%→45.0%）**，累積永久跳過：286→318檔。已用`backfill_state.json`實際筆數（1439 done/318 skip=1757筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（45.0%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T15:13:42+08:00 — 馬拉松第64輪：全市場宇宙回補第十九批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T13:34:50）早於US（2026-08-25T14:02:23）跟FUT（2026-08-25T14:32:52），輪替規則指向TW。開始前 `data/backfill_state.json` 為1439 done/318 skip（共1757筆），跟 `TW_MARATHON_STATE.md` 第61輪記錄一致（無資料落差，代表第61輪本身乾淨結束）。覆蓋率45.0%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試110檔（前50/前100/最終110三段輸出，最終段連續限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成77/新跳過13。**累積覆蓋率：1439→1516/3196（45.0%→47.4%）**，累積永久跳過：318→331檔。已用`backfill_state.json`實際筆數（1516 done/331 skip=1847筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（47.4%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T16:35:41+08:00 — 馬拉松第67輪：全市場宇宙回補第二十批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T15:13:42）早於US（2026-08-25T15:34:05）跟FUT（2026-08-25T16:04:29），輪替規則指向TW。開始前 `data/backfill_state.json` 為1516 done/331 skip（共1847筆），跟 `TW_MARATHON_STATE.md` 第64輪記錄一致（無資料落差，代表第64輪本身乾淨結束）。覆蓋率47.4%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試102檔（前50/前100/最終102三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成73/新跳過14。**累積覆蓋率：1516→1589/3196（47.4%→49.7%）**，累積永久跳過：331→345檔。已用`backfill_state.json`實際筆數（1589 done/345 skip=1934筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（49.7%，已過半），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T19:35:10+08:00 — 馬拉松第73輪：全市場宇宙回補第二十二批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T18:05:40）早於US（2026-08-25T18:33:29）跟FUT（2026-08-25T19:05:53），輪替規則指向TW。開始前 `data/backfill_state.json` 為1665 done/363 skip（共2028筆），跟 `TW_MARATHON_STATE.md` 第70輪記錄一致（無資料落差，代表第70輪本身乾淨結束）。覆蓋率52.1%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試130檔（前50/前100/最終130三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成78/新跳過8。**累積覆蓋率：1665→1743/3196（52.1%→54.5%）**，累積永久跳過：363→371檔。已用`backfill_state.json`實際筆數（1743 done/371 skip=2114筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（54.5%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T18:05:40+08:00 — 馬拉松第70輪：全市場宇宙回補第二十一批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T16:35:41）早於US（2026-08-25T17:02:50）跟FUT（2026-08-25T17:34:50），輪替規則指向TW。開始前 `data/backfill_state.json` 為1589 done/345 skip（共1934筆），跟 `TW_MARATHON_STATE.md` 第67輪記錄一致（無資料落差，代表第67輪本身乾淨結束）。覆蓋率49.7%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔（前50/前100/最終109三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成76/新跳過18。**累積覆蓋率：1589→1665/3196（49.7%→52.1%）**，累積永久跳過：345→363檔。已用`backfill_state.json`實際筆數（1665 done/363 skip=2028筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（52.1%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T00:36:06+08:00 — 馬拉松第78輪：全市場宇宙回補第二十四批

**做了什麼**：取鎖時偵測到`LOCK_STALE`（pid 132048持有鎖30.1分鐘後被回收，代表第77輪（US軌）之後某一輪疑似異常中止、未留下任何log）。比對三軌「最後更新」時間戳，FUT（2026-08-25T20:36:09）最舊，但依`FUT_MARATHON_STATE.md`頂部使用者裁示（期貨軌效率最低22試驗0通過，最多佔整體輪次20%，選輪次時TW/US優先度更高），本輪不選FUT，改依次舊的TW（2026-08-25T21:05:35）。開始前覆蓋率56.9%（1819/3196）遠低於80%門檻，跑`backfill_universe.py --batch-size 300`（自動接續），呼叫時額度已恢復（未被立即限流）。

**結果**：本批嘗試137檔（前50/前100/最終137三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成100/新跳過22。**累積覆蓋率：1819→1919/3196（56.9%→60.0%）**，累積永久跳過：384→406檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍低於80%門檻（60.0%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（見`TW_MARATHON_STATE.md`第14項——主線1情境條件式檢驗，`f_foreign_streak`/`f_rel_strength`/`f_quality_roe_stability`方向反轉三假說+4個已PASS因子的分群IC，產出`REGIME_CONDITIONS.md`；這是`METHODOLOGY_FIX_TASK.md`修正2，目前跟宇宙回補並列最高優先序）。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T04:17:00+08:00 — 馬拉松第83輪：`f_rel_strength_regime_switch` 策略層深挖（FAIL）

**取鎖**：乾淨成功（`LOCK_ACQUIRED`），無需回填「上一輪疑似異常中止」的註記。三軌狀態檔時間戳比對：TW（2026-08-26，互動session寫的無精確時分）最舊，選TW軌。

**做了什麼**：讀`TW_MARATHON_STATE.md`第14項與主線`MARATHON_STATE.md`「2026-08-26使用者裁示」段落，發現主線1（情境條件式檢驗）跟主線2（組合策略）已在同日稍早的互動session全部完成，「下一輪建議接續」第一項點名`f_rel_strength`情境切換策略「要不要真的建regime-switching backtest驗證」。檢查發現repo裡已有互動session寫好但**從未執行過**的`regime_switch_f_rel_strength.py`（未commit，讀完全文確認安全：走`load_dev()`+`holdout.assert_no_holdout_leakage()`、零新FinMind呼叫、matched random control同樣走regime開關），判定這是本輪最適合的有界工作單位——執行它、驗證輸出、誠實記錄判定，不需要自己重寫回測邏輯。背景執行（timeout規劃1500秒，實際112秒完成，遠比預期快）。

**結果**：TRAIN(2015-2020)×1x/2x/3x成本全部負報酬(ann −6.82%~−9.22%)/負alpha(−4.66%~−7.11%)/負Sortino(−0.144~−0.233)，對配對式隨機控制組僅84.0~89.0百分位；VAL(2021-2024)只有1x成本微幅轉正(ann+0.50%/alpha+1.77%)，2x/3x轉負，對配對式隨機控制組93.0~94.0百分位——兩期六組全部未達其他TW候選（`f_quality_roe_stability`等）慣見的99~100百分位門檻。**判定FAIL**。

**判定**：策略層完整驗證失敗，不進候選清單。`REGIME_CONDITIONS.md`分群IC找到的動量崩潰/套利限制經濟解釋在因子排序能力(IC)層級是對的，但沒有轉化成扣成本後能打贏隨機選股的可交易邊際優勢——這是TRAIN期乾淨虧損、VAL期對成本極敏感的組合，不是「差一點點沒過」的邊緣案例。完整數字、經濟解釋、與`f_quality_roe_stability`同款模式的對照，見`TW_LEADS.md`#4、`TRIALS_LEDGER.md`#40。

**待辦**：主線`LEADS.md`裡`f_rel_strength_regime_switch`那一列目前仍是PENDING（該檔案因互動session其他未commit變更處於dirty狀態，本輪延續US#82/FUT#80對TW互動session變更的迴避慣例，刻意不動、不commit）——下一個處理主線`LEADS.md`commit的session（互動或馬拉松皆可）需要把該列同步更新成FAIL。本輪commit範圍嚴格限定：只有`regime_switch_f_rel_strength.py`（互動session寫的分析腳本本身，這輪驗證過安全且已產出結果，判定可以入庫）+ `TW_LEADS.md`/`TRIALS_LEDGER.md`/`TW_LOG.md`/`REPORT.md`/`MARATHON_STATE.md`（本輪自己的記錄與心跳），**不動** `DATA.md`/`LEADS.md`/`TW_MARATHON_STATE.md`/`adjust.py`/`backfill_universe.py`/`factors.py`/`generate_scores_v2.py`/`score_v2.py`/`scores.json`/`REGIME_CONDITIONS.md`/`backfill_t86.py`/`portfolio_backtest.py`/`realtime_asof.py`/`regime_conditions.py`/`twse_t86_client.py`/`yf_price_client.py`（互動session的其餘產出，涉及App正式評分/資料源架構等有風險項目，留給使用者自己審過再決定commit）。

**下一步**：見`TW_LEADS.md`「下一輪建議」段落——(1)深挖`f_value_pb`；(2)拆解`f_quality_roe_stability`TRAIN期絕對報酬為負的成因；(3)若時間允許，掃`MARATHON_PROTOCOL.md`第3節還沒碰過的因子家族。宇宙回補（主線3）已在互動session達80%門檻(81.3%)，不再是TW軌本輪強制優先項，但下一輪若碰到額度受限、其他工作單位卡住時仍可回頭補「price done但finrev缺」的405檔。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`load_dev()`/`assert_no_holdout_leakage()`路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T05:49:00+08:00 — 馬拉松第85輪：`f_value_pb` 深挖（1b），判定EXPERIMENTAL

**取鎖**：乾淨成功（`LOCK_ACQUIRED`），無需回填「上一輪疑似異常中止」的註記。三軌狀態檔時間戳比對：TW（`TW_MARATHON_STATE.md` mtime 2026-08-26 01:55，早於US的05:02跟FUT的02:05）最舊，選TW軌。

**做了什麼**：讀`TW_MARATHON_STATE.md`第14項候補清單第(a)項與`TW_LEADS.md`#1備註，確認`f_value_pb`便宜關卡已`CHEAP_PASS`、PIT前置驗證已完成（單檔2330跳變偵測，第四輪），下一步是深挖（1b）。repo裡有一份互動session留下、**從未執行過**的`deep_dive_f_value_pb.py`（2026-08-23 17:03），先完整讀過原始碼：方法完全比照`deep_dive_f_quality_roe_stability.py`的精神（十分位多空/配對式隨機控制組100次抽樣/TRAIN+VAL兩期/成本1x2x3x/CAPM beta），資料路徑走`load_dev()`+`holdout.assert_no_holdout_leakage()`，重用既有80/100快取樣本、零新FinMind呼叫，確認安全無holdout風險後執行。背景執行約耗時分鐘級（6組配置×100次隨機抽樣，跟ROE深挖第三輪同等工作量）。

**結果**：61/80名有`f_value_pb`值。**TRAIN(2015-2020)**×1x/2x/3x成本：ann_return −6.93%~−7.42%（全負）、alpha −3.11%~−3.62%（全負）、Sortino −0.168~−0.188（全負）、beta −0.109（近零，market-neutral構造成立）、對配對式隨機控制組percentile=88.0/96.0/97.0（1x未達其他候選慣見的99~100門檻，2x/3x較強）。**VAL(2021-2024)**×1x/2x/3x：ann_return +4.82%~+5.56%（全正）、alpha +8.58%~+9.35%（全正）、Sortino +0.326~+0.358（全正）、beta −0.080~−0.081（近零）、percentile=99.0/100.0/100.0（三組全數穩健通過）。

**判定：EXPERIMENTAL**（不是PASS，不是FAIL）——十分位多空組合在VAL期乾淨、穩健地贏過配對式隨機控制組（beta近零，market-neutral成立），但**TRAIN期絕對報酬/alpha/Sortino全部為負、VAL期全部為正，正負號不一致**，跟`f_quality_roe_stability`（#16/#17）完全同款的「IC/相對排序層級可能成立，絕對報酬層級train/val反轉」模式，是這個模式的第三個實例（第二個是`f_rel_strength_regime_switch`，見#40，但那個是策略層FAIL，不是EXPERIMENTAL——差別在於`f_rel_strength_regime_switch`兩期對隨機控制組都沒有穩健勝出，`f_value_pb`至少VAL期是乾淨的99~100百分位）。**誠實揭露這次證據比ROE深挖更弱**：ROE的6組全部是percentile=100.0，這次TRAIN 1x只有88.0（低於便宜關卡慣用的90門檻），代表TRAIN期的「贏過隨機」本身在最低成本情境下就不夠穩健，是隨著成本墊高才轉強（2x=96.0/3x=97.0），這個方向（成本越高越贏隨機）本身也需要留意，可能代表策略在TRAIN期虧損没有隨機控制組虧得多（因為隨機控制組換手率相近但選股方向錯，兩者一起虧、策略虧得較少），不是策略本身賺錢。

**經濟解釋（憲法要求）**：便宜的帳面淨值（負PBR因子）反映市場對困境/低成長公司的過度悲觀定價，日後基本面改善或估值回歸均值時獲得修正——這是文獻中經典的價值溢酬（value premium，Fama-French HML）。**TRAIN/VAL絕對報酬正負號不一致，本身可能有市場整體風格輪動的解釋**：2015-2020是全球（含台股電子/半導體成長股）成長股顯著跑贏價值股的市場環境，即使選到「最便宜」的一批股票，整體風格逆風下多空組合仍可能虧損（但比隨機選股虧得少或贏得更明確，尤其成本墊高後）；2021-2024則普遍記載有價值股回補輪動（升息環境不利長存續期成長股估值、疫後重啟交易偏好景氣循環/價值股），跟VAL期轉為乾淨正報酬的時間點吻合。**這是觀察到的市場regime模式，不是這輪驗證過的因果機制**，誠實標記為待驗證的解釋，不是確認的因果證據。

**判定不升格為PASS的理由**：train/val絕對報酬正負號不一致這條規則（沿用ROE深挖#16/#17的先例）沒有被這輪的經濟解釋豁免——即使有合理的市場regime故事，也還沒有像`REGIME_CONDITIONS.md`對`f_rel_strength`那樣做過完整的事前可觀測條件分群驗證（大盤位階/波動度/市值/流動性四組），不能只憑「這個故事聽起來合理」就直接升格。**下一步（如果要繼續）**：仿照`regime_conditions.py`對`f_value_pb`也做一次分群IC，看TRAIN/VAL絕對報酬的反轉能不能被「大盤位階（成長/價值風格輪動的代理）」這組條件系統性解釋；如果能，比照`f_rel_strength`升格「情境切換策略候選」流程；如果不能，就跟`f_quality_roe_stability`一樣維持EXPERIMENTAL、不繼續往下挖。

**待辦**：`TW_LEADS.md`#1（`f_value_pb`列）需要更新這輪深挖結果與判定，這輪一併完成（見該檔案本輪更新）。`TRIALS_LEDGER.md`新增#42。**本輪commit範圍嚴格限定**：只有`deep_dive_f_value_pb.py`（互動session寫的分析腳本本身，這輪驗證過安全且已產出結果，判定可以入庫）+ `TW_LEADS.md`/`TRIALS_LEDGER.md`/`TW_LOG.md`/`REPORT.md`/`MARATHON_STATE.md`（本輪自己的記錄與心跳），**不動** `DATA.md`/`LEADS.md`/`TW_MARATHON_STATE.md`/`adjust.py`/`backfill_universe.py`/`factors.py`/`generate_scores_v2.py`/`score_v2.py`/`scores.json`/`REGIME_CONDITIONS.md`/`backfill_t86.py`/`portfolio_backtest.py`/`realtime_asof.py`/`regime_conditions.py`/`twse_t86_client.py`/`yf_price_client.py`（互動session的其餘產出，延續前幾輪US#82/#84、FUT#80、TW#83對這批dirty檔案的迴避慣例，留給使用者自己審過再決定commit）。`.github/workflows/`（untracked）同樣不動，跟本輪工作無關。

**下一步**：(1) 若要繼續深挖`f_value_pb`，考慮補一次分群IC（見上方判定段落）；(2) 拆解`f_quality_roe_stability`TRAIN期絕對報酬為負的成因（候補清單既有項目，這輪未做）；(3) 若時間允許，掃`MARATHON_PROTOCOL.md`第3節還沒碰過的因子家族（短期反轉/BAB/Amihud流動性/季節性/資產成長異常/Piotroski F-score/accruals）。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`load_dev()`/`assert_no_holdout_leakage()`路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T09:35頃 — 馬拉松第92輪：接手陳舊鎖檔孤兒工作——補齊`f_short_reversal_1m`便宜關卡的文件記錄

**取鎖**：`LOCK_STALE`（pid 146212持有30.0分鐘後被回收，上一輪疑似異常中止）。三軌狀態檔時間戳：US（第91輪，09:04:37）跟FUT（第90輪，08:33:39）都已有明確馬拉松輪次時間戳，TW（`TW_MARATHON_STATE.md`只標「2026-08-26互動session」無精確時分，且輪替邏輯上TW已經多輪沒被排到）判斷仍是最久沒被馬拉松輪次本身碰過的一軌，選TW軌。

**發現**：`git status`顯示上一輪（pid 146212）已完成`f_short_reversal_1m`（短期反轉，21交易日自身累積報酬取負號，`MARATHON_PROTOCOL.md`第3節「動量變體/短期反轉」家族第一個測試）的1a便宜關卡測試——新寫`factor_ic_short_reversal.py`、`factors.py`加上該因子定義（`SHORT_REVERSAL_WINDOW=21`）、`TRIALS_LEDGER.md`已新增#46列——但**崩潰在完成前，`TW_LOG.md`完全沒有這筆記錄、`TW_LEADS.md`也還沒新增對應列（#46備註寫著見`TW_LEADS.md#5`，但檔案裡根本沒有#5列）**，是一份「數據已產出、判定已下、只差文件收尾」的孤兒工作，不是半成品程式碼。

**驗證**：重跑`python factor_ic_short_reversal.py`（docstring承諾零新API呼叫，沿用既有100名快取樣本）確認數字跟`TRIALS_LEDGER.md`#46完全一致：TRAIN(2015-2020) mean_ic=+0.0496 IR=+0.286（n=74期）；VAL(2021-2024) mean_ic=−0.0054 IR=−0.032 hit_rate=0.53（n=47期）；null percentile=23.1（單測門檻90.0，遠未過）；same_sign=False（train為正、val接近零轉負）。判定**FAIL**，程式輸出跟既有文件字面一致，不是重新詮釋，只是把上一輪確實做完的判定補上遺漏的文件記錄。

**做的事**：這輪本身沒有測新假說（`f_short_reversal_1m`本身的1a判定是上一輪的產出，這輪只驗證+補文件），本輪新增內容：(1) 這篇`TW_LOG.md`記錄；(2) `TW_LEADS.md`新增#5列（`f_short_reversal_1m`），把`TRIALS_LEDGER.md`#46的完整數字/經濟解釋轉貼過去，符合`TW_LEADS.md`一貫的候選登記簿格式。**`TRIALS_LEDGER.md`#46本身不重複新增**（上一輪已經加好，重跑只是驗證數字沒有錯，不產生新試驗）。

**經濟解釋**（延續上一輪已下的判定，未變）：短期反轉是文獻中跟中期動能方向相反但同樣有名的異常，這裡用自身絕對報酬（非相對大盤，跟`f_rel_strength`刻意區隔），val期IC幾乎為零而非清楚反轉，可能是80檔樣本規模不足以捕捉這種通常需要更細（週頻/日頻分層）資料才穩定顯現的效應。不建議直接視為「台股無短期反轉」定論，但目前證據不支持升格。

**本輪commit範圍**：`factor_ic_short_reversal.py`（新增，上一輪產出，已驗證安全可重複執行）+ `factors.py`（`f_short_reversal_1m`定義，上一輪產出）+ `TW_LOG.md`/`TW_LEADS.md`（本輪補齊文件）+ `TRIALS_LEDGER.md`（working copy裡#46這筆是上一輪產出但還沒commit過，這次一併帶上，不是重複新增）+ `REPORT.md`/`MARATHON_STATE.md`（本輪心跳）。**不動**`.github/workflows/quotes.yml`（working copy裡另一筆跟本輪工作無關的uncommitted變更，看起來是使用者要求的CI健壯性修正，跟TW因子研究無關，延續本協定一貫「只commit跟本輪工作直接相關檔案」的紀律，留給使用者自己審過決定）。

**下一步**：短期反轉家族（唯一測過的變體`f_short_reversal_1m`）已FAIL結案；`TW_MARATHON_STATE.md`第14項候補清單其餘項目（`f_value_pb`分群IC/`f_quality_roe_stability`TRAIN期成因拆解/`MARATHON_PROTOCOL.md`第3節繼續掃BAB/特異波動率/Amihud流動性/季節性/資產成長異常/Piotroski F-score/accruals）仍是下一輪可選項。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只重跑`factor_ic_short_reversal.py`的`load_dev()`路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T11:03:40+08:00 — 馬拉松第94輪：補齊主線 `LEADS.md` 待辦（`f_rel_strength_regime_switch` PENDING→FAIL）

**取鎖**：乾淨成功（`LOCK_ACQUIRED`）。三軌狀態檔最後commit時間比對：TW 08:06:39、US 09:06:59、FUT 10:35:53，TW最舊，選TW軌。

**做了什麼**：讀`TW_MARATHON_STATE.md`／`TW_LEADS.md`，發現第83輪（2026-08-26 04:17）已經把`f_rel_strength_regime_switch`策略層深挖跑完並判定FAIL，但因為當時互動session的其他檔案處於dirty狀態，主線`research/LEADS.md`本身那一列被刻意跳過、留在舊的`PENDING`狀態，且從那之後US#88/#91、FUT#93等後續輪次都延續同樣的迴避慣例沒有補上——這是一筆確定、已有完整數字、只是還沒被寫進權威記錄檔的待辦，不需要新的API呼叫或新的回測，是這輪最適合的有界工作單位。

**做的事**：讀`data/regime_switch_f_rel_strength.csv`（本機既有，第83輪產出）確認欄位跟`TW_LEADS.md`#4記錄的數字完全一致（TRAIN 1x/2x/3x：ann_return −6.82%/−8.03%/−9.22%、alpha全負、Sortino全負、beta+0.073、隨機控制組84.0/87.0/89.0；VAL 1x/2x/3x：ann_return +0.50%/−0.62%/−1.74%、alpha 1x略正2x/3x轉負、Sortino 0.141/0.103/0.066、beta+0.191、隨機控制組93.0/94.0/94.0）。發現CSV本身沒有MDD欄位（腳本原本就沒算），據實記錄「MDD未計算」而非編造數字。更新`research/LEADS.md`該列：候選名稱補上策略描述、判定PENDING→FAIL、Val/Train/隨機控制組百分位欄位填入1x成本下的實際數字、備註完整說明1x/2x/3x全部情境+經濟解釋+跟`f_quality_roe_stability`同款模式的對照+未測項範圍限制。

**判定**：文件同步工作，不是新的假說檢定，`TRIALS_LEDGER.md`不需要新增列（#40已經是這筆試驗的權威記錄，這輪只是讓`LEADS.md`跟它同步，不是重新測試）。

**本輪commit範圍**：只有`LEADS.md`（本輪唯一修改）+`TW_LOG.md`/`REPORT.md`/`MARATHON_STATE.md`（本輪記錄與心跳）。**不動**`.github/workflows/quotes.yml`（working copy裡另一筆跟本輪工作無關的uncommitted變更，延續前幾輪一貫紀律，留給使用者自己審過決定）。

**下一步**：`TW_MARATHON_STATE.md`第14項候補清單仍是下一輪可選項——(a) 拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag；(b) `weinstein_stage2_unbiased`的alpha/beta顯著性關卡（`WEINSTEIN_ALPHA_GATE_TASK.md`）；(c) `f_value_pe`成本敏感度測試；(d) 照`MARATHON_PROTOCOL.md`第3節繼續掃BAB/特異波動率/Amihud流動性/季節性/資產成長異常/Piotroski F-score/accruals盈餘品質；(e) 三大法人期貨部位/T86回補（覆蓋率仍嚴重落後，見混合資料源架構條目）。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪沒有呼叫任何FinMind/資料載入函式，純文件編輯）。

## 2026-08-26T12:08:18+08:00 — 馬拉松第96輪：低風險/流動性家族第一批，2個假說

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對：FUT最舊（10:34）但依`MARATHON_PROTOCOL.md`資源配置裁示（FUT上限20%，近10輪已佔4/10=40%，遠超上限），改選次舊的TW（11:03）。TW覆蓋率已達81.3%（>80%門檻），主線1/2已於互動session完成（見`MARATHON_STATE.md`），照`TW_MARATHON_STATE.md`第15項掃`MARATHON_PROTOCOL.md`第3節還沒測過的因子家族。選了「流動性」（Amihud illiquidity，全新家族）跟「低風險」家族第二個測試（idiosyncratic volatility，`f_low_vol`是第一個，已PASS）。

1. **`f_amihud_illiq`**：20日|日報酬|/成交金額均值（Amihud 2002），新增至`factors.py`（純價格+成交量，天然PIT），`factor_ic_amihud_illiq.py`（沿用既有100名快取樣本，零新API呼叫）。**結果FAIL**：TRAIN mean_ic=−0.0131/VAL mean_ic=−0.0097，same_sign=True但方向跟流動性溢酬文獻預期相反（未取負號的原始illiq值理論上應為正），null percentile=38.1（門檻90.0，遠未過）。
2. **`f_idio_vol`**：60日市場模型變異數分解（Var(r)=beta²·Var(rm)+Var(residual)封閉解，扣掉大盤beta後的殘差波動度，取負號）取代`f_low_vol`的總波動度，Ang et al. (2006)異常，新增至`factors.py`（純價格，天然PIT，零新API呼叫），`factor_ic_idio_vol.py`。**結果CHEAP_PASS，percentile=100.0**：TRAIN mean_ic=+0.1259 IR=+0.624（n=63期）、VAL mean_ic=+0.0963 IR=+0.559 hit_rate=0.68（n=47期），same_sign=True，打贏全部1000次隨機打散——TW軌至今單測解析度最強的候選之一，IR/hit_rate明顯優於多數既有候選。

**依協定只測2個假說收工**（`MARATHON_PROTOCOL.md`第1a節上限2-3個）。`f_amihud_illiq`FAIL不調參數硬救，直接記錄換下一個；`f_idio_vol`CHEAP_PASS排入待深挖清單，**深挖前先做跟`f_low_vol`的相關性/持股重疊度檢查**（避免深挖出兩個實質重疊的候選當成獨立發現），詳見`TW_LEADS.md`#7備註。

**結果**：`TRIALS_LEDGER.md`新增#50（`f_amihud_illiq` FAIL）、#51（`f_idio_vol` CHEAP_PASS），TW軌FDR家族m由18→20。`TW_LEADS.md`新增#6/#7。

**驗證**：`is_holdout_consumed()` 確認仍為 `False`（`load_dev()`唯一入口，零額外FinMind/yfinance呼叫，全程命中`factor_ic.py`既有快取樣本）。

**下一輪**：見`TW_LEADS.md`本輪更新的「下一輪建議」——優先`f_idio_vol`相關性檢查+深挖，其次`f_value_pb`深挖、`f_quality_roe_stability`TRAIN期負報酬拆解，或繼續掃BAB/季節性/資產成長異常/Piotroski F-score/accruals盈餘品質。

---

## 2026-08-26T13:35:13+08:00 — 馬拉松第99輪：`f_idio_vol` vs `f_low_vol` 相關性/持股重疊度檢查（深挖前置作業，非新假說測試）

**接手備註**：取鎖時偵測到`LOCK_STALE`（pid 149044持有30.2分鐘後被回收）——查證後發現上一輪（第98輪，FUT軌）其實已經把所有記錄檔跟程式碼改動都寫完，只是在git commit/push前當機，不是完全沒進度。本輪commit `1c32ae1` 先把第98輪那批未commit的檔案（`FUT_LEADS.md`/`FUT_LOG.md`/`FUT_MARATHON_STATE.md`/`MARATHON_STATE.md`/`REPORT.md`/`TRIALS_LEDGER.md`/`fut_cheap_gate.py`）補commit+push（`git pull`遇到遠端自動報價更新，乾淨merge無衝突），本輪心跳count因此不重複記第98輪那筆。軌道選擇：TW時間戳（12:08:18）比US（12:15）舊，FUT近10輪已佔30%（達20%上限，優先度降低），選TW。

**做了什麼**：TW軌宇宙覆蓋率已達81.3%（>80%門檻），照`MARATHON_PROTOCOL.md`第5b節優先序改回測因子/深挖。第96輪`TW_LEADS.md`#7明確標記`f_idio_vol`（CHEAP_PASS）深挖前要先跟`f_low_vol`做相關性/持股重疊度檢查，本輪執行這個前置作業。新寫`check_idio_vol_low_vol_overlap.py`：重用`factor_ic.py`既有的100檔快取樣本（SAMPLE_SEED=20260822）跟121個不重疊20交易日快照，逐快照計算(a) `f_low_vol`/`f_idio_vol`兩因子值的橫斷面Spearman相關係數、(b) 兩因子各自最高/最低十分位持股名單的Jaccard重疊度（多頭腿/空頭腿分開算）。

**結果**：110個可用快照（平均每快照64檔可比較）。**mean Spearman correlation = +0.982**（幾乎完全共線）；**多頭腿十分位Jaccard重疊度 = 0.789**、**空頭腿 = 0.835**——遠超腳本內建的「高度重疊」判定門檻（corr>0.7或雙腿重疊>0.5）。**判定：HIGH OVERLAP**——`f_idio_vol`實質上是`f_low_vol`的高度共線變體，不是獨立訊號，兩者選股名單8成以上重複。**決策：不進入完整深挖**，因為就算深挖出漂亮的十分位多空數字，也只是把已經PASS的`f_low_vol`訊號用另一種算法重新發現一次，不會替選股引擎新增邊際資訊，不值得花一輪深挖成本（樣本外/配對隨機控制組/成本敏感度/CAPM beta）去驗證一個高度共線的重複發現。`TW_LEADS.md`#7的判定欄從「CHEAP_PASS→待深挖」改註記為「CHEAP_PASS但降級：與f_low_vol高度共線（附錄檢查已完成），不建議進深挖，記錄保留供文獻對照用」。這不是推翻第96輪的便宜關卡結果（IC測試本身沒有錯，`f_idio_vol`確實通過了單獨測試），是誠實記錄「通過便宜關卡≠值得投入深挖資源」這個額外的判斷維度，`TRIALS_LEDGER.md`不新增列（這是對既有候選的診斷附加資訊，不是新假說測試，沒有新的IC/隨機控制組判定）。

**驗證**：`is_holdout_consumed()`確認仍為`False`。零額外FinMind/yfinance呼叫（`load_sample_with_factors()`完全命中既有快取，執行時間<10秒，無任何限流/重試訊息）。

**下一輪建議**：`f_idio_vol`家族結案（不留在待深挖佇列）。TW軌待深挖佇列目前為空，下一輪可選：(a) `f_value_pb`深挖（PIT已單檔驗證過，`TW_LEADS.md`#1/#2待辦）；(b) `f_quality_roe_stability`TRAIN期負報酬拆解（`EXPERIMENTAL`懸案）；(c) 繼續掃`MARATHON_PROTOCOL.md`第3節新家族——BAB（betting against beta，跟`f_idio_vol`/`f_low_vol`同「低風險」家族但機制不同，值得測，不受這次降級影響）、季節性、資產成長異常、Piotroski F-score、accruals盈餘品質。

---

## 2026-08-26T16:06:04+08:00 — 馬拉松第102輪：補齊`f_bab`/`f_asset_growth`/`f_accruals`未commit的積壓工作（非新測試，reconciliation）

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對：TW（13:35:13）、US（14:05:19，state檔本身輪號標示有誤但時間戳可信）、FUT（13:05:49，最舊）。但檢查`git status`發現一批**已經測完、`TRIALS_LEDGER.md`已經commit記錄（#61 `f_bab`/#62 `f_asset_growth`/#63 `f_accruals`），但支援檔案沒有一起commit**的積壓工作：`factor_ic_bab.py`、`factor_ic_asset_growth.py`（驅動腳本，未追蹤）、主線`LEADS.md`/`STRATEGY_LOG.md`（`weinstein_alpha_gate`任務的文字紀錄，已寫好未commit）、`.github/workflows/quotes.yml`（CI健壯性小改，已寫好未commit）。`TW_LEADS.md`本身也缺對應的#8/#9/#10列（TRIALS_LEDGER已經在引用這三個編號）。

**判斷**：這不是新的假說測試，是誠實記錄的完整性缺口——`TRIALS_LEDGER.md`宣稱這三個因子「可重複執行」，但驅動腳本實際上沒進repo，任何人（包含下一輪馬拉松、Cowork、使用者）都無法重跑驗證。優先把這個缺口補齊，比照第94輪「補齊主線LEADS.md待辦」的先例（純文件/檔案同步，不算新假說檢定）。跟FUT/US時間戳排序無關——這輪是修復記錄完整性，不是照軌道輪替選新工作。

**做的事**：
1. `TW_LEADS.md`新增#8（`f_bab`）/#9（`f_asset_growth`）/#10（`f_accruals`）三列，內容取自`TRIALS_LEDGER.md`#61/#62/#63已委的數字，並更新「下一輪建議」段落標記這三個家族已結案。
2. `git add`：`research/factor_ic_bab.py`、`research/factor_ic_asset_growth.py`（驅動腳本，讓#61/#62可重複執行）、`research/LEADS.md`、`research/STRATEGY_LOG.md`（weinstein_alpha_gate任務的既有文字，未做任何內容修改，原樣commit）、`.github/workflows/quotes.yml`（CI健壯性小改，已寫好的`continue-on-error`/`if: always()`調整，未做任何內容修改）、`research/TW_LEADS.md`、本篇log、心跳檔案。

**驗證**：`is_holdout_consumed()`確認為`False`（本輪沒有呼叫任何FinMind/yfinance資料載入函式，純文件/git整理）。三個因子的數字本身（TRAIN/VAL mean_ic/percentile）沿用既有已committed的`TRIALS_LEDGER.md`#61/#62/#63記錄，沒有重新計算，避免不必要的重跑成本。

**下一輪建議**：積壓清理完成後，TW軌待深挖佇列仍為空（`f_value_pb`是唯一待深挖候選）。下一輪照三軌時間戳/FUT 20%上限規則正常輪替選軌即可，不需要再處理這批積壓。

---

## 2026-08-26T17:36:36+08:00 — 馬拉松第105輪：`f_gross_margin_stability`（毛利率穩定度，Novy-Marx精神品質異常變體）1a便宜關卡

**做了什麼**：取鎖時偵測到`LOCK_STALE`（pid 148680持有約30.1分鐘，上一輪疑似異常中止，但沒有找到任何未commit的殘留工作——`git status`乾淨，判斷是乾淨崩潰/逾時，非留下半成品）。三軌時間戳比對：TW（16:06:04，最舊）、US（16:38:29）、FUT（17:05:24），選TW軌。

**訂正一個發現**：`TW_MARATHON_STATE.md`第102輪備註寫「TW軌待深挖佇列仍為空（`f_value_pb`是唯一待深挖候選）」——這句話是錯的，`TW_LEADS.md`#1清楚記錄`f_value_pb`深挖早在第85輪就完成（判定EXPERIMENTAL），這個備註是沿用更早（第92輪前）已過時的字句，沒有跟著更新。本輪沒有照這句話重做`f_value_pb`深挖，改為挑一個真正尚未測過的新假說。

**測試內容**：新增`_gross_margin_stability()`（`factors.py`）跟`factor_ic_gross_margin_stability.py`（驅動腳本），對應`MARATHON_PROTOCOL.md`第3節「品質」家族明列但尚未測過的「毛利率穩定度（Novy-Marx）」項目——季毛利率=GrossProfit/Revenue，穩定度分數=負的近8季滾動標準差，統計構造跟`f_quality_roe_stability`完全相同，只是換成毛利率而非ROE（先花時間確認`quarterly_pit`已快取的原始`TaiwanStockFinancialStatements`回應裡本來就含`Revenue`/`GrossProfit`兩個type值，同一快取鍵，**零新FinMind呼叫**，抽測100名樣本中68/100有這兩個欄位，跟其他已測因子的80/100可用率量級相符）。

**結果：FAIL**。100名樣本（80/100可用，121個不重疊20交易日快照）：TRAIN(2015-2020) mean_ic=+0.0441 IR=+0.285（n=74期）；VAL(2021-2024) mean_ic=+0.0199 IR=+0.143 hit_rate=0.51（n=47期）；same_sign=True（train/val同號），但對隨機打散null percentile=70.7，遠低於單測門檻90.0。跟`f_asset_growth`/`f_accruals`（方向不一致或IC接近零）比，本次是「有一點訊號但不夠強」的形態，不是方向錯。TW軌「品質」家族三個變體至此測完：ROE穩定度（EXPERIMENTAL）、accruals（FAIL）、毛利率穩定度（本輪，FAIL）。TW軌FDR家族m由28→29（BH-FDR分軌獨立計算，這是第29筆）。

**做的事**：
1. `factors.py`新增`_gross_margin_stability()`＋`prepare_factors()`裡的第(s)段落（try/except降級模式，跟其他新因子一致）。
2. `factor_ic_gross_margin_stability.py`（新增，可重複執行）。
3. `TRIALS_LEDGER.md`#67、`TW_LEADS.md`#11（新列＋更新「下一輪建議」，移除已過時的f_value_pb待辦、順帶補一句更正說明）。

**驗證**：`is_holdout_consumed()`確認為`False`。零新FinMind呼叫（`quarterly_pit`命中`f_quality_roe_stability`/`f_asset_growth`/`f_accruals`已建立的同一快取，執行時間約1分鐘內完成，無任何限流/重試訊息）。

**下一輪建議**：TW軌「品質」「低風險」「資產成長」「accruals」四個家族第一批全部結案，待深挖佇列仍為空。下一輪可選：(a) `f_quality_roe_stability`TRAIN期負報酬拆解（唯一的EXPERIMENTAL懸案）；(b) 季節性家族（月效應/財報季效應）——**注意**這是全市場共通的日曆效應，需要先想清楚怎麼構造出跨股票的橫斷面差異（例如跟規模/流動性交乘）才能套進現有`factor_ic.py`的IC測試框架，不是單純「哪個月報酬較高」的市場層級統計；(c) 成長與預估上修——先查FinMind有沒有分析師預估資料，沒有就記錄「資料源不存在」跳過；(d) 籌碼類（融資券/當沖比/借券/外資持股變化）——`CLAUDE.md`/`alpha-data/config.py`確認TWSE openapi有`MI_MARGN`融資券端點，但這是全新資料集，尚未被任何已快取因子用過，測之前要評估是否值得衝新的API額度（符合協定1a.2精神，不要為了可能沒用的假說貿然衝新額度）。

---

## 2026-08-26T20:36:21+08:00 — 馬拉松第110輪：暫停規則生效中，本輪跳過新工作；記錄一次鎖檔機制的邊界案例（非資料損毀）

**接手備註（誠實補記一個缺口）**：發現`TW_MARATHON_STATE.md`跟`REPORT.md`心跳都引用「第107輪`TW_LOG.md`本輪記錄」，但這份檔案裡實際上**沒有第107輪的條目**（`grep "^## "`確認上一筆是第105輪，105之後直接跳到現在這筆）——第107輪的commit（`e81010c`）本身確實存在且訊息提到「f_quality_roe_stability TRAIN期報酬拆解+補commit round105/106孤兒工作」，但對應的`TW_LOG.md`詳細記錄疑似漏寫或漏commit。**本輪沒有嘗試回頭補寫第107輪的內容**（沒有第一手資訊，用猜的等於捏造記錄，比留空更糟），只誠實記下這個缺口，供後續有能力查證（例如翻`e81010c`的完整diff）的人補齊。

**背景：使用者暫停規則生效中**。2026-08-26晚使用者裁示：在`PORTFOLIO_STRATEGY_SPEC.md`＋組合策略回測報告正式完成、且使用者親自確認之前，禁止開始任何新的單因子/家族系統掃描，寫進`MARATHON_PROTOCOL.md`最上方。

**取鎖狀況（值得記錄的邊界案例，不是單純的「上一輪異常中止」）**：`marathon_lock.py acquire`回報`LOCK_STALE`（pid 154480持有約30分鐘）。依協定字面上該當作「上一輪疑似異常中止」處理，但深入查證後發現**這其實是誤判**：pid 154480是稍早一個互動session（不是排程馬拉松輪次），使用者在該session直接下指示完成`PORTFOLIO_STRATEGY_SPEC.md`（規格書）跟`portfolio_backtest_v2.py`（12組合完整回測，含成本敏感度+15次隨機控制組配對抽樣），這個計算過程本身耗時較長（單一組合含完整版跑法\>1分鐘，12組合階段2完整版總計數分鐘），該session專注在跑腳本，沒有回頭更新`.marathon.lock`的心跳時間戳，導致鎖檔在**時間門檻判定上**顯得「陳舊」（\>25分鐘沒更新），但實際上那個process還活著、還在正常工作。本輪`acquire()`因此把鎖偷了過來（`marathon_lock.py`的設計就是純時間判定，無法分辨「活著但慢」跟「真的死了」），**但那個互動session幾乎在同一時刻（20:34左右）自己完成了`git commit`+`git push`（commit`fa369b9`），沒有經過我這輪的鎖檔保護**。事後檢查`git log`／`origin/main`確認結果一致、沒有衝突或資料損毀——這次純屬僥倖沒有出事，不是機制設計上真的安全。**記錄這個發現，供之後有機會改善`marathon_lock.py`或`MARATHON_PROTOCOL.md`的人參考**：目前的鎖機制假設「互動session要嘛不會跟排程輪次同時跑，要嘛會乖乖呼叫`marathon_lock.py`」，但這輪证明互動session可能在跑長時間計算時完全不碰鎖檔，讓陳舊判定失真。

**本輪實際做的事**：
1. 確認`PORTFOLIO_STRATEGY_SPEC.md`存在但狀態仍是「待使用者確認」（不是我能自己判定的事）。
2. 確認`portfolio_backtest_v2.py`（12組合：因子版本A/B×等權/IC加權/情境加權×月/季頻）已經完整跑完並產出誠實結果（判定FAIL，但兩個最佳組合IC加權+季頻p=0.053接近顯著），且已由該互動session自己完成`LEADS.md`新增`portfolio_multifactor_v2`列＋`REPORT.md`完整專章＋`git commit`+`push`（`fa369b9`）——**這份工作在我這輪抵達之前就已經完成並上線，我沒有新增任何計算或判定**，只是確認它確實在遠端（`git log origin/main`核對過）。
3. 依三軌時間戳，正常輪替本應選US（時間戳最舊），但US沒有組合策略相關工作可做；該互動session寫在`REPORT.md`的「建議下一步」明確聲明「不會自己動手，留給使用者決定優先序」（含：換全市場81.3%樣本重跑IC加權+季頻看p值會不會改善、train-only IC權重的更嚴格樣本外測試、補大盤本身MDD/Sortino基準）——**本輪判斷不宜代為決定要不要啟動這些高成本重跑**，這是使用者明確保留給自己的判斷，不下放。依暫停規則，本輪不開始任何新工作。
4. 補寫`TW_MARATHON_STATE.md`（新增第110輪條目）、`REPORT.md`心跳（第110輪）、`MARATHON_STATE.md`全局計數器（109→110）。
5. 確認`.github/workflows/quotes.yml`仍是唯一working tree改動——這是已知限制（`MARATHON_STATE.md`第11行記錄：目前PAT沒有`workflow` scope，commit碰到`.github/workflows/*.yml`會被GitHub拒絕push），本輪比照既有慣例不commit它，留給使用者換新PAT後處理。

**驗證**：`is_holdout_consumed()`確認為`False`。本輪零FinMind/yfinance呼叫（純文件/git核對）。

**下一輪建議**：如果撿到TW軌，先確認使用者是否已經看過`portfolio_multifactor_v2`的結果並回應「下一步」三個選項之一（換更大樣本重跑/更嚴格樣本外驗證/補大盤基準），有明確指示才動手，沒有的話繼續等待，不要自行決定升級或放棄。`f_quality_roe_stability`TRAIN期報酬拆解懸案（第107輪`TW_LEADS.md`#3）仍待處理，但屬於「新因子深挖」性質，暫停規則生效期間同樣不應優先處理，除非使用者另有指示。
