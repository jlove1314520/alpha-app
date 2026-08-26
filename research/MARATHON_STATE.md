# MARATHON_STATE.md — 斷點狀態檔

**這份檔案永遠只描述「現在」，會被覆寫，不是 append-only。** 換 session／換機器／換 agent 接手 Phase 2（自動下單引擎）研究工作時，**先讀這份**，再視需要去查 `REPORT.md`（細節動作記錄）、`STRATEGY_LOG.md`（里程碑敘事）、`LEADS.md`（策略候選）、`FACTORS.md`（因子登記簿）。

**最後更新：2026-08-25T17:34:50+08:00**

**馬拉松全局輪次計數器（2026-08-23 新增，使用者要求）：目前累積 124 輪。最新一輪：第 124 輪 · 2026-08-27T06:32+08:00 · FUT（跳過，暫停規則生效中）· 取鎖乾淨（非陳舊鎖檔）；三軌時間戳FUT最舊（第121輪05:01），正常輪替選FUT，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「狀態：待使用者確認」且自第123輪以來無互動session介入，FUT軌唯一待辦（`fut_day_gap_continuation`高解析度重測）本質仍是單因子相關工作，同round109/112/115/118/121判斷邏輯保守跳過，本輪未做任何實質工作。`is_holdout_consumed()`為`False`，詳見`REPORT.md`第124輪條目、`FUT_MARATHON_STATE.md`/`FUT_LOG.md`本輪記錄。**

**上一則保留（第122輪，供對照）**：2026-08-27T05:20+08:00 · TW · 取鎖乾淨；三軌時間戳TW最舊（第119輪04:21），正常輪替選TW，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」且自第119輪以來無互動session介入，延續協定允許的地基工作`backfill_t86.py --batch-size 200`：200嘗試/200完成(12空)/未撞限流牆，累積T86快取836→1036/3305（25.3%→31.3%）。`is_holdout_consumed()`為`False`，詳見`REPORT.md`第122輪條目、`TW_MARATHON_STATE.md`/`TW_LOG.md`本輪記錄。

**上一則保留（第120輪，供對照）**：2026-08-27T04:32+08:00 · US（跳過，暫停規則生效中）· 取鎖乾淨；三軌時間戳US最舊（第117輪03:01），正常輪替選US，複查`PORTFOLIO_STRATEGY_SPEC.md`仍「待使用者確認」且自第119輪以來無互動session介入，US軌無組合策略相關工作（規格書全部圍繞TAIEX/TWSE台股樣本），round108/111遺留(a)(b)(c)三項本質仍是為單因子鋪路，同round111/114/117判斷邏輯保守跳過，本輪未做任何實質工作。`is_holdout_consumed()`為`False`，詳見`REPORT.md`第120輪條目、`US_MARATHON_STATE.md`/`US_LOG.md`本輪記錄。

**上一則保留（第110輪，供對照）**：2026-08-26T20:36+08:00 · （軌道判定見備註）· 取鎖時偵測到`LOCK_STALE`（pid 154480持有約30分鐘，但查證後這不是異常中止——是同時段一個互動session跑`portfolio_backtest_v2.py`耗時較長沒更新鎖檔心跳，該session最終自己完成commit+push`fa369b9`，跟本輪取鎖動作幾乎同時發生，無資料損毀但屬於鎖機制設計沒完全涵蓋的邊界案例，已在`TW_LOG.md`本輪記錄詳述、`MARATHON_PROTOCOL.md`可能需要後續補強）；使用者暫停單因子試驗規則生效中，`PORTFOLIO_STRATEGY_SPEC.md`+完整v2回測結果已由該互動session寫入`LEADS.md`/`REPORT.md`並push（12組合，最佳兩組alpha p=0.053接近顯著但未過關），本輪抵達前已完成，且該session的「下一步」建議明確留給使用者決定不自動繼續；三軌正常輪替本應選US（時間戳最舊18:xx）但US無組合策略相關工作可做，依暫停規則本輪跳過新工作，只做狀態核對/補寫`TW_MARATHON_STATE.md`。見`TW_LOG.md`本輪記錄。 這是跨 TW/US/FUT 三軌共用的單一遞增計數器，不是各軌自己 commit message 裡那種各軌獨立的輪號。**下一輪的義務：讀這行的數字 N，這輪結束前（見 `MARATHON_PROTOCOL.md` 第 6 節）在 `REPORT.md` 最上面的「心跳記錄」區塊插入一筆 `## 第 N+1 輪 · ...`，並把這行的數字改成 N+1。** 不管這輪做了什麼、有沒有成功，都要留這一筆，這樣任何人（包含使用者自己）打開 `REPORT.md` 最上面就能一眼看出馬拉松最近有沒有在跑、多久跑一次、有沒有卡住。

**▶ 目前狀態：AI 選股引擎 Phase A（步驟 1–4）全部完成並 push；Part 2 挖礦馬拉松已上線自動執行（已跑數輪，三軌都有進展）；Cowork 稽核多空中性結果，三次覆核（付費方案調查/alpha-beta拆解/多空擱置）也已完成並 push。**

**⚠️ 2026-08-26 第102輪新發現的已知限制：目前的 GitHub PAT 沒有 `workflow` scope，任何 commit 只要碰到 `.github/workflows/*.yml` 就會被 GitHub 拒絕 push（`refusing to allow a Personal Access Token to create or update workflow without workflow scope`）。**這不是網路暫時性問題，重試無用。馬拉松輪次如果需要改動 workflow 檔案，commit 時要把該檔案排除在外（留在working tree不動，等使用者換有`workflow` scope的PAT），不要因為push失敗就以為是DNS/網路問題狂重試。這輪受影響的是 `.github/workflows/quotes.yml` 一個小的CI健壯性改動（`continue-on-error`/`if: always()`），已寫好但暫不commit，內容還留在working tree，等使用者處理。

**2026-08-24（傍晚）Cowork 三次覆核摘要：** Cowork 定調「純多前decile 是更穩健且可實際執行的方向，多空放空腿先擱置為研究備選」。(1) 查了 FinMind 完整定價（Free$0/Backer$699月/Sponsor$999月/SponsorPro$3330月，流量300~20000次/hr）跟 yfinance 免費備援（可用於價格但**不支援下市股+財報歷史太短**，只能局部緩解）——這是金流決策，回報資訊給使用者，不會自己付款。這次額度恢復過一次，累積到199/3,196（6.2%），維持標記不放寬。(2) 新增 `decompose_alpha_beta()`：**確認贏隨機是選股alpha不只是beta**——四期純alpha年化+15.22%~+24.31%，Sortino多數>1.0，MDD約−11%~−13%；成本敏感度四期在3x下全維持正值，但Validation(週頻)已相當薄弱（+6.17%）。(3) 全市場重跑純多——待宇宙達80%+才能做，這輪還不能開始。(4) `score_longshort_v1` 判定改為 `PENDING`（放空可行性＋券源確認後再議）。完整數字見 `LEADS.md`/`REPORT.md`/`STRATEGY_LOG.md` 2026-08-24（傍晚）條目。

**2026-08-24（下午）Cowork 二次覆核摘要：** 三關逐一處理——(1) 宇宙覆蓋率新增 `backfill_universe.py`（可斷點續傳，已整合進 `MARATHON_PROTOCOL.md` 5b節，TW軌最高優先序背景任務），這次 session 進度到 223/3,196（≈7.0%），**多空/decile結論一律標記「樣本不足、暫不採信」**（`LEADS.md` 新增這個判定類別）。(2) 月頻train/val不一致查到根源（複利被少數極端月份主導+換股名單不穩定），確認不是bug，但跨期一致關卡目前無法通過，多空框架維持降級。(3) 放空可行性查驗撞限流沒有可信結論（待重驗）；**但意外發現「純多前decile相對大盤」四期全部一致強勁（年化+23.77%~+33.67%，beta合理+0.6~+0.7，alpha顯著為正，贏隨機對照100百分位，沒有跨期不一致問題）**，是目前唯一馬上可執行、不依賴放空的候選雛形，同樣受宇宙覆蓋率限制標記「樣本不足、暫不採信」。**使用者從這輪起要求所有產出一律用繁體中文**，已全面遵守。完整數字見 `LEADS.md`/`REPORT.md`/`STRATEGY_LOG.md` 2026-08-24（下午）條目。

**2026-08-24 Cowork 稽核回應摘要：** `score_topn_v1`（長多前10名）雖贏配對隨機對照組，但絕對報酬輸買進持有、且買進持有基準本身有偏差——Cowork 指出這代表「這個實作形式」沒有實用價值。改用多空市場中性設計（`long_short_backtest.py`：買前decile/空後decile，實測 beta 而非假設，新增放空成本模型）+ 全市場隨機抽樣（非原本偏差樣本，但受 FinMind 流量限制只達 170/3,196 檔≈5.3%覆蓋率，誠實揭露）。**結果：四期（train/val×週/月頻）beta 全部接近零、配對隨機控制組全部 100.0 百分位——證實因子橫截面排序能力是真的**；誠實揭露 Train(月頻) 絕對報酬跟 Sortino 為負，沒有淡化。過程中修好 3 個真 bug（欄位名、小樣本異常值放大、beta/alpha 扣成本前後不一致）+ 1 個效能問題（忘記帶過之前已修過的快取優化）。完整數字見 `LEADS.md`/`REPORT.md` 2026-08-24 條目。**全市場覆蓋率的落差留給使用者決定是否要繼續補。**

**Part 1 收尾摘要（2026-08-23）：** 因子相關性去重（`f_eps_growth`/`f_eps_surprise` 同家族合併，4 因子→3 獨立成分）；`score.py` 綜合分引擎（同產業 peer z-score，ETF 覆蓋率不足過濾）；`run_score_backtest.py` 扣成本+換手組合回測（train/val 隨機控制組皆 100.0 百分位，但絕對報酬輸給零成本買進持有——判讀方式見 `LEADS.md`/`FACTORS.md`，`score_topn_v1` 判定 `EXPERIMENTAL`）；App「選股」頁上線（`scores.json`，瀏覽器實測過）。**留下未解決的架構問題**：`scores.json` 目前用 `VAL_END` 當基準日（非即時），步驟5「每日排程」需要的即時資料路徑要不要獨立於 holdout 機制之外，待使用者決定。詳見 `FACTORS.md`/`STRATEGY_LOG.md`/`REPORT.md` 2026-08-23 條目。

**Part 2 挖礦馬拉松：✅ 已上線，Windows 工作排程器每 30 分鐘自動執行。** 協定文件 `MARATHON_PROTOCOL.md`＋三軌獨立檔案（`TW_LEADS.md`/`US_LEADS.md`/`FUT_LEADS.md` 等）＋跨軌累積試驗總帳 `TRIALS_LEDGER.md`（seed 12 筆，第一輪馬拉松後累積到 15 筆）＋檔案鎖 `marathon_lock.py`。**手動測試第一輪（09:47–09:53）完全成功**：正確讀協定、選 TW 軌、測試 `f_value_pb`/`f_value_pe`/`f_quality_roe_stability` 便宜關卡，正確執行「批次過但累積校正後降級」邏輯（`f_value_pe`），commit+push+釋放鎖檔全部正常，還自己扛過一次暫時性網路失敗並重試成功。使用者確認後已註冊 Windows 工作排程器任務 `AlphaMarathon`（`C:\alpha\run-marathon-cycle.ps1`，`--dangerously-skip-permissions` + 限縮工具集 + `--max-budget-usd 5`，只在使用者登入 Windows 時執行，重疊觸發自動略過，25分鐘執行上限）。**下一輪起會完全無人值守自動執行**，之後接手的 session 要定期用 `git log`／`TRIALS_LEDGER.md` 檢查馬拉松進度，不需要自己手動觸發。

**Cowork 五點覆核結果摘要（2026-08-23）：** (1) `f_eps_growth` 的 PIT 正確性二次確認為真，不需重算；(2) 加 Bonferroni 校正（門檻 90→98.3 百分位）後 `f_eps_growth` 依然通過，5 個原 FAIL 不變；(3) 全市場/400檔擴大重驗被 FinMind 流量限制擋下（未完成），但用已快取樣本延長橫截面歷史（121→184個，2008–2024）驗證仍過；(4) 擴充 6 個新因子候選——3 個成功測試且全部通過（`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`），2 個（PB/PE、ROE穩定度）因流量限制完全未測，1 個（分點集中度）確認無免費資料源；(5) 目前累積 **4 個** 通過的因子，但因子間相關性未查、3 個新因子未測，依然不進 `score.py`。詳見 `FACTORS.md`／`REPORT.md` 2026-08-23 條目。

**GitHub 稽核狀態：✅ 通過**（12:00 的 `.py` 檔案存在性問題是 Cowork 端舊快照；13:00 的 holdout 截斷漏洞是真的，已修復）。**如果又收到類似回報，先照 STRATEGY_LOG.md 的 FILE MANIFEST 重新走一次驗證，不要預設是自己這邊漏推，也不要預設對方一定錯。**

**Holdout 狀態：✅ 依然未被使用。** `is_holdout_consumed()` 複查為 `False`，`HOLDOUT_LOCK.json` 不存在。目前有一個候選（`weinstein_stage2_unbiased`）train/val 全部關卡都過，**使用者 2026-08-25 已給出明確的解鎖判準（見下方「2026-08-25 使用者解除卡關指令」區塊），不是還在等模糊的授權，而是等這個候選先通過 alpha/beta 拆解 + 顯著性關卡才能回報使用者決定要不要解鎖**——顯著性檢定的校正方法已改成 FDR（見下方「2026-08-25（晚）方法論重大修正」），不再是 Bonferroni；這個關卡本身還沒做，見 `WEINSTEIN_ALPHA_GATE_TASK.md`（任務規格）。

---

## 2026-08-25（晚）方法論重大修正——目前最高優先，凌駕於「繼續測新因子」之上

**使用者裁示，完整任務規格見 `METHODOLOGY_FIX_TASK.md`（新增）。在這份任務標記完成之前，馬拉松不要開新一輪的廣度優先掃因子家族；宇宙覆蓋率回補（TW軌）仍照舊優先，跟這份任務並行。**

四項修正摘要（細節、理由、精確做法全部在 `METHODOLOGY_FIX_TASK.md`，不要只看這裡的摘要就動手，去讀完整版）：
1. 多重比較校正從累積 Bonferroni 改成 **BH-FDR（q=0.10），三軌獨立分母**——已同步修訂 `MARATHON_PROTOCOL.md` 第2節；既有 `TRIALS_LEDGER.md` 37筆試驗要用新標準重新評分（不算新試驗，是套用新公式在既有數字上），尤其檢查使用者點名的 `#14`/`#25`/`#27`/`#30`/`#31`/`#33`/`#34`。
2. 每個因子加測「情境條件式」分群 IC（市場位階/波動度環境/市值規模/流動性），訓練驗證方向相反的試驗（使用者點名 `#3`/`#5`/`#11`）當成情境依賴證據重新調查，不直接算失敗；產出存 `research/REGIME_CONDITIONS.md`（新檔案，這份任務要建立）。
3. 策略級判定改用風險調整後標準（Sortino/MDD/alpha顯著性）為主，不再要求絕對報酬贏買進持有。
4. 把4個已PASS因子（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`）組成多因子策略測（等權/IC加權/情境條件式加權三版本），這才是真正的holdout候選。
5. 資源配置：FUT軌（22試驗0通過）降到最多佔輪次20%，主力轉TW軌情境條件化+覆蓋率回補。

**進度追蹤**：這份任務預期跨多輪才能做完，每輪做到哪個修正項目、下一輪接續哪裡，更新在這一段（覆寫，不要疊加流水帳）。**修正1（BH-FDR重新評分）已完成**——criteria_v2已鎖定（`CRITERIA_V2_LOCK.md`）、37筆既有試驗已用新標準重新評分完畢（完整對照表見`TRIALS_LEDGER.md`底部）。結果：TW軌1筆復活（`f_value_pe`，改列「待複驗候選CANDIDATE」）、FUT軌0筆復活（22次策略試驗維持全部FAIL/不確定）。**使用者2026-08-26已看過這個結果、裁示「門檻不是主因」，正式把火力轉向修正2跟修正4——完整新指示見下方「2026-08-26 使用者裁示：馬拉松繼續，跑到我喊停」區塊，之後每輪照那個區塊的三條主線走，不要再回頭做修正1的收尾（`f_value_pe`成本敏感度）除非那個區塊有提到。**

---

## 2026-08-26 使用者裁示：馬拉松繼續，跑到我喊停（三條主線，取代舊的「修正2/3/4」逐項清單）

**這是目前最高優先指示，完整原話見這輪對話紀錄。跟2026-08-25晚的方法論修正是同一條脈絡的延續，不是新方向——修正1(FDR)已經做完且使用者已確認結論，修正3（風險調整後標準）視為已定案(直接採用，不用再等)，修正2跟修正4合併成下面的主線1跟主線2，重新用更具體的規格描述。**

### 主線1（最高優先）情境條件式檢驗
- 把 `#3`（`f_foreign_streak`）、`#5`（`f_rel_strength`）、`#17`（`f_quality_roe_stability`深挖最終版，train/val反轉）**這三個train/val方向反轉的假說徹底調查**：算分群IC，找出它在哪些「事前可觀測」的條件下為正、哪些為負。**條件至少四組**：(a) 大盤位階（年線之上/之下）、(b) 波動度環境（高/低，可用大盤已實現波動度歷史分位數切）、(c) 市值規模（大/中/小型）、(d) 流動性/量能（高/低成交值）。
  - 若方向能被事前條件穩定區分 → 升格「情境切換策略候選」，記進 `LEADS.md`；不能穩定區分 → 正式否決（不是繼續掛著不確定）。
- **同時**把4個已通過因子（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`）**也各自做一次分群IC**（同樣四組條件），看它們是否在某些情境特別強——這是新增的，之前沒做過，不是重測已知結果。
- 產出寫進 `research/REGIME_CONDITIONS.md`（`METHODOLOGY_FIX_TASK.md`已規劃的新檔案，這輪要真的建立內容）。

### 主線2 組合策略（從未做過的一步，這才是真正的holdout候選）
- 用4個已通過因子 + `f_value_pe`（待複驗候選）組成多因子策略，**測三個版本**：等權、IC加權、情境條件式加權（用主線1做出來的分群結果決定權重）。
- 要有**完整交易規則**：換股頻率、持股檔數、進出場條件、單一部位上限、全成本假設。
- **評判標準**：Sortino、MDD、對大盤回歸後的alpha是否顯著為正——**不要用「絕對報酬贏買進持有」當唯一標準**（這條沿用修正3的裁定）。
- **這個組合策略才是真正的holdout候選，單一因子不是。未經使用者明確同意，不准解鎖holdout**——`unlock_holdout_once()`這條鐵律沒有例外，這裡再次重申。

### 主線3 宇宙回補（優先序不變，跟主線1/2並行）
- 台股涵蓋率繼續往80%補，這是統計檢定力不足、可能誤殺真edge的根源，跟主線1的情境分群樣本數也直接相關（分四組條件切下去，每組樣本更小，覆蓋率不夠會讓分群IC本身不可信）。

### 資源配置
- 期貨軌維持最多佔輪次20%（已22試驗0通過，效率最低）。
- **美股軌可以開始建因子管線**——這是新增的優先方向，US軌至今沒有任何統計檢定試驗（見`TRIALS_LEDGER.md`），可以參照TW軌`factor_ic.py`的方法論框架，找美股對應資料源後開始第一批便宜關卡測試。

### 紀律（不變，重申）
- 每輪照舊：編號+時間戳+heartbeat+git commit（繁中）。
- PIT資料、survivorship-free、全成本、FDR分軌校正、hash-lock預先綁定判準，全部維持不變。
- **樣本<100筆不下結論；涵蓋率低的結論一律標「待全市場複驗」**——這條在情境分群（主線1）尤其重要，四組條件切下去很容易某一組樣本掉到100以下，遇到這種情況誠實標記，不要硬下結論。

**進度追蹤（這一段之後每輪更新，覆寫不疊加）**：

**2026-08-26（互動session，使用者直接下指示，非排程馬拉松輪次）三條主線全部有實質進展，完整數字見`REGIME_CONDITIONS.md`/`LEADS.md`/`REPORT.md`同日條目：**
- **主線1（情境條件式檢驗）✅ 完成**：7個因子（3個反轉待查+4個已通過）全部做了四組分群IC。**`f_rel_strength`(#5)方向反轉被四組條件完全一致解釋**（多頭/小型股/低波動/低量能為正，反之為負，符合動量崩潰文獻），**升格「情境切換策略候選」**（`LEADS.md`新列，`PENDING`，還沒建regime-switching策略回測）。`f_foreign_streak`(#3)無法被解釋（IC全線偏弱，不是清楚反轉）。`f_quality_roe_stability`(#17)IC本身全部8組皆正、從未反轉——原本的train/val反轉是絕對報酬層級的現象，不是IC層級，兩者是不同指標，這個發現本身就是這輪的產出。4個已通過因子的情境敏感度也記錄了（`f_low_vol`/`f_value_pe`/`f_eps_growth`系列在低波動環境明顯更強，`f_revenue_surprise`相反在高波動更強）。
- **主線2（組合策略回測）✅ 完成，誠實負面結果**：`portfolio_backtest.py`（新增）測equal/ic_weighted/regime_weighted三版本，完整交易規則（週頻/前10名/15%停損/全成本）。**三版本在VALIDATION期alpha對大盤回歸後都不顯著**（p=0.133~0.537），只有`ic_weighted`在TRAIN期顯著(p=0.022)但val期不顯著，不符合本專案一貫的跨期一致性要求。**判定：三個版本都不夠格當holdout候選，沒有觸碰holdout、也不需要問使用者是否解鎖**（本來就沒先過關）。詳見`LEADS.md`新增的`portfolio_multifactor_v1`列。
- **主線3（宇宙回補）✅ 大幅推進**：60.0%→**81.3%（2597/3196）**，已達80%門檻，見下方「資料源混合架構」條目。
- **資源配置**：這輪沒有動FUT軌或US軌（互動session聚焦使用者這次的四項優先指示，沒有照輪替邏輯處理其他軌道）。

**下一輪（不論互動或馬拉松）建議接續**：(a) `f_rel_strength`情境切換策略要不要真的建regime-switching backtest驗證（目前只有因子層級證據，見`LEADS.md`）；(b) 情境條件式加權目前只用波動度單一維度，若要更完整可以嘗試多維度組合（風險：樣本會更快被切到<100，需要更大宇宙樣本才能支撐，跟主線3的持續回補直接相關）；(c) 三大法人相關因子（`f_foreign_streak`/`f_inst_flow`）的T86資料回補嚴重落後（僅36個交易日），且該端點有反爬蟲封鎖風險（見下方混合架構條目），需要更保守的節奏慢慢補；(d) 全市場更大樣本重跑這輪的情境分群+組合回測（目前都還是100檔驗證樣本，跟`factor_ic.py`既有抽樣一致，不是新宇宙覆蓋率下的重新抽樣）。

---

## 2026-08-25 使用者解除卡關指令（四項裁示，逐項記錄，之後每一輪都要遵守）

使用者這輪直接給了四個先前卡住/懸而未決的問題明確裁示，不是「等使用者授權」的模糊狀態了，以下逐項記錄成這裡的標準規則：

**1. `weinstein_stage2_unbiased` 解鎖 holdout 前，先做 alpha/beta 拆解關卡：** 不直接解鎖 holdout。要求：把 train/val 兩期的策略報酬對大盤指數（TAIEX）回歸，報告 alpha（截距）、beta、以及扣成本後有沒有贏買進持有；若 alpha 沒有明確為正、且沒有通過 Bonferroni 校正的顯著性關卡，直接判否決（判定為「這就是 beta，不是真的選股能力」），**不要**因為這樣就去解鎖 holdout（不能拿一個否決的候選去賭一次性的 holdout 機會）。只有确认是真 alpha（正值 + 通過累積 Bonferroni 校正）才回報使用者，由使用者決定是否解鎖——**這裡本身不會自己解鎖 holdout，不管 alpha 拆解結果多漂亮，`unlock_holdout_once()` 永遠只能由使用者明確指示才能呼叫**。**任務規格已寫成 `research/WEINSTEIN_ALPHA_GATE_TASK.md`，這是一個新的、跟平常「找新因子」性質不同的工作單位，下一個 TW 軌輪次撿到深挖候選類工作時可以挑這個做**（不是每輪都要做，是排進候補清單、跟 `deep_dive_f_value_pb.py`同一層級的優先度）。

**2. `fut_basis_carry`（717倍）已經照使用者要求的方式查完，結論完全符合使用者的期待，不需要重做：** 使用者這輪指示「當成有bug來查、不是戰果」「做walk-forward、檢查是否少數合約/轉倉日灌爆總報酬、補上轉倉成本、部位上限、拿掉極端後穩健才留dev觀察、717倍這種數字不准拿去解鎖holdout」——**這些第75輪（2026-08-25T20:36）的深挖（1b）全部都已經做過了**：train/val walk-forward切分（val期percentile=46.0，連隨機控制組中位數都沒贏過）、leave-one-year-out（確認717x有85%集中在2000-2002三年，拿掉後只剩107.9x）、成本敏感度1x/2x/3x、beta對照（0.36非市場中性）。**判定已經是深挖FAIL，從CHEAP_PASS降級，不進候選清單，本來就沒有被拿去解鎖holdout過（`unlock_holdout_once()`從未被呼叫，見上方Holdout狀態）。** 完整見 `FUT_LEADS.md` #17、`TRIALS_LEDGER.md` #37、`FUT_LOG.md` 第75輪記錄。**這是使用者的裁示剛好跟馬拉松已經自主做出的結論完全一致的案例，不需要任何新動作，下一輪不要重測或重查這個訊號。**

**3. `scores.json`（App「選股」頁用的十分制評分）用即時（VAL_END之後）資料算分，是合法的正式out-of-sample，不算碰研究holdout——這條規則解除了 Phase A 步驟5（每日排程）的架構卡關：**
   - **規則**：只要「因子定義」跟「權重」是在 dev 期（≤ `VAL_END`）鎖定、之後不再拿近期資料重新調整，那麼用當前（VAL_END之後）的最新資料去代入這個已凍結的公式算出分數、顯示在 App 上，屬於這個公式在真實世界的**正式（非研究用）out-of-sample 應用**，不是在動用研究用的 holdout 資料——holdout 保護的是「不能用它來挑選/調整策略」，不是「不能用今天的日期算數字」。
   - **注意**：這條規則是給 `research/score_v2.py`（App 選股頁十分制評分引擎，percentile-based，8大類別權重是使用者提供的設計小抄裡的固定常數）用的，**不是**放寬 `factor_ic.py`/`TRIALS_LEDGER.md` 那一套嚴謹的因子驗證框架的 holdout 規則——那一套仍然完全比照原本紀律，train/val/holdout 三層物理隔離不變，`score_v2.py` 走的是另一條「消費端資料整理排序產品」的路線，兩者是不同性質的東西（`score_v2.py`本身的docstring已經寫過這個區分，這裡再次確認、正式解除卡關）。
   - **影響**：Phase A 步驟5（每日排程）先前卡在「即時資料 vs holdout 邊界，需要使用者決定」，**現在這條已經解決，可以動工**——只要新的排程機制不去動 `score_v2.py` 的 `FACTOR_DEFS` 權重常數（那些是設計小抄給的固定值，不是從資料重新估計出來的，天然符合「凍結」的要求），單純把 `generate_scores_v2.py` 排程化（例如每天收盤後自動重跑一次、`data_asof` 自動跟著更新到最新交易日）就是合規的。**這裡不會自己安排定時排程機制**（涉及 App 對外顯示行為/資料時效性的產品決策，比較適合由互動 session 跟使用者一起做，不是馬拉松該自己動的範圍），但因子/權重凍結後拿最新資料算分這個核心疑慮已經解除，不用再卡在這個問題上。

**4. 繼續自走，重心放在「起漲股」因子家族 + 宇宙覆蓋率持續往80%補：** 使用者點名的五個方向（營收加速度、財報驚喜、籌碼集中、量能突破、事件驅動）**有些其實已經測過，不要當成全新方向誤判成沒測過**——已在 `MARATHON_PROTOCOL.md` 第3節新增「起漲股因子家族」小節逐一對照現況（哪些PASS、哪些FAIL、FAIL的可以測哪些變體），詳見該節。宇宙覆蓋率持續回補（現況見 `TW_MARATHON_STATE.md`，56.9%，最高優先序不變，這條使用者只是重申，不是新指示）。每輪照舊編號+時間戳+commit（`REPORT.md` 心跳機制已經在運作，這條也只是重申）。

---

## 現在做到哪

**里程碑 1（資料誠實度盤點）：✅ 完成。** 三顆地雷（台股還原股價、存活者偏差、財報 point-in-time）都已實測、記錄在 `DATA.md`，並且已經寫成程式碼修復（不只是文件）：
- `adjust.py` — 台股還原股價，用 2330 全部 42 筆歷史除權息事件驗證過
- `universe.py` — TW 回測宇宙限定 2003 年後 + 納入下市股（3,196 檔），殘餘偏差已記錄
- `pit.py` — 財報保守發布延遲假設（季報 +45 天、月營收優先真實 `create_time`）

**里程碑 2（驗證框架）：🟡 進行中，地基元件做完，還沒串成一個能跑的骨架。**
- ✅ `validation/holdout.py` — train/val/holdout 物理隔離，train≤2020、val 2021–2024、holdout 是之後到今天，`unlock_holdout_once()` 一次性鎖，鎖檔跟稽核日誌都進 git（`HOLDOUT_LOCK.json`／`HOLDOUT_LOG.md`，目前都還不存在，因為還沒真的用過）。**2026-08-22 追加 `assert_no_holdout_leakage()`**：資料載入時的硬性斷言，取代原本只能靠 `cap_to_dev()` 選配的弱防護
- ✅ `finmind_client.py` — **2026-08-22 重構**：`load_dev()` 現在是策略/分析程式碼唯一該用的資料入口，內建自動截斷在 `VAL_END`；`_fetch()`／`load_full_history()` 是不對外的底層路徑。修的是 Cowork 抓到的真漏洞：原本 `fetch()` 預設無截斷。
- ✅ `validation/costs.py` — 台股成本模型（手續費0.1425%×2/證交稅0.3%或0.15%/滑價）+ 漲跌停鎖死偵測（用真實資料 3231 在 2025-04-07 的跌停案例驗證過）
- ✅ `validation/control_group.py` — `run_control_group()`（靜態版，仍保留）+ **2026-08-22 新增 `run_matched_control_group()`**（配對式：同進出場日期只換股，機制上真正對應策略行為，Cowork 要求的修正）
- ✅ `validation/criteria.py` — 事前綁定標準（鎖檔+雜湊比對，防止事後移動門柱），驗證過鎖定/竄改偵測都正常
- ✅ `backtest/engine.py`（通用回測引擎，日曆逐日走、T日訊號→T+1成交、三層風控、`validation/costs.py` 成本、進場前 `assert_no_holdout_leakage()`）。已用真實策略實跑兩輪驗證過。**2026-08-22 追加 `sortino_ratio` 屬性**；`buy_leg_rate()`/`sell_leg_rate()` 拿掉底線變公開，給 `control_group.py` 重用（單一成本費率來源）
- ❌ **還沒做**：美股成本模型（價差/衝擊/借券/wash sale/PDT）——目前 `costs.py` 只有台股

**里程碑 3（紙上前測基礎設施）：🟡 剛起步，只有骨架先搭好，沒有真實資料流過。**
- ✅ `audit_ledgers.py` — 唯讀稽核腳本，3 條恆等式，對兩輪真實回測交易紀錄（共 4 批：train/val × pilot/unbiased）都實測 PASS
- ✅ `trades.csv` schema 已定義，`research/data/backtests/` 底下有兩輪真實回測的交易/權益曲線 CSV（`.gitignore` 排除，本機保留）——注意是**回測**輸出，不是紙上前測帳本
- ✅ `LEADS.md` — 2 列（`weinstein_stage2_pilot_v1` FAIL、`weinstein_stage2_unbiased` EXPERIMENTAL）
- ❌ **還沒做**：影子帳本本身（開一本空手起跑的 paper book，只認前向自己開的單）
- ❌ **還沒做**：`dashboard.html`（使用者說「必要時」才做）
- ❌ **還沒做**：每日/每三日自動健檢排程

**里程碑 4（Weinstein 第二階段 baseline）：✅ 兩輪跑完，第二輪（無偏宇宙+配對式控制組）train/val 全過，仍未進 holdout。**
- `strategies/weinstein_stage2.py`：股票層 150 日均線上揚突破 + 60 日動量排名；大盤層加權指數 200 日均線閘門（兩輪都用同一套訊號邏輯，沒有為了過關而改訊號）。
- **第一輪**（`strategies/run_weinstein_pilot.py`，30 檔手選試點宇宙）：買進持有/成本敏感度都過，**隨機控制組沒打贏**（第 24.5 百分位）。判定 `FAIL`。事後發現方法論有兩個缺陷（Cowork 指出）：靜態對照組不對應策略機制、手選宇宙有選擇偏差。
- **第二輪**（`strategies/run_weinstein_unbiased.py`，`universe.py` 全市場隨機抽樣 100 檔 + 配對式控制組）：四項關卡（買進持有 val+train/成本1x2x3x敏感度/交易數≥100/配對式隨機控制組）**全部通過**（控制組第 99.5 百分位）。判定 **`EXPERIMENTAL`**（規則要求 `PASS` 必須含 holdout 驗證，這輪沒碰）。過程中抓到並修好 3 個真 bug（`adjust.py` 兩處空值檢查順序錯、`engine.py` 除以零），詳見 `REPORT.md`。
- 完整結果、解讀、已知簡化見 `STRATEGY_LOG.md`／`REPORT.md` 2026-08-22T14:00 跟 T15:00 兩條。

**里程碑 5（挖策略）：未開始**——`weinstein_stage2_unbiased` 是否進 holdout 還沒決定，決定之前不會開新策略。

---

## AI 選股引擎 Phase A（新工作流，跟里程碑 1–5 平行，不是同一條線）

依使用者設計書分 5 步：因子庫→因子IC檢定→計分→App選股頁→每日排程。**目前狀態：步驟 1–4 全部完成。步驟 5（每日排程）原本卡的架構問題（即時資料 vs holdout 邊界）已於 2026-08-25 由使用者裁示解除，見最上方「2026-08-25 使用者解除卡關指令」第3點——只要 `score_v2.py` 的 `FACTOR_DEFS` 權重維持凍結（不拿近期資料重新調整），用當前資料算分是合法的正式 out-of-sample。實際排程機制怎麼接（cron/工作排程器/前端定時 fetch 等）留給互動 session 跟使用者決定，馬拉松不會自己動這塊。**

- ✅ `factors.py`：6 個因子全部實作，全部透過 `load_dev()`／`pit.py` 取資料，基本面因子用 `merge_asof(direction='backward')` 鍵在 `pit_date` 做 point-in-time 對齊，用真實資料逐日驗證過對齊時間點完全正確（不早於揭露日）。(d) 因子的「市值」用流動性正規化代替（`TaiwanStockMarketValue` 付費，已驗證確認），有明確揭露。
- ✅ `factor_ic.py`：跟 `weinstein_stage2_unbiased` 同一套無偏抽樣（100 檔種子`20260822`，80 檔可用）、121 個不重疊 20 日橫截面、train/val 分開、200 次隨機打散對照組。
- ✅ `FACTORS.md`：6 個因子的完整結果登記，原本 **只有 `f_eps_growth` 通過**（val IC +0.073，打散對照 100 百分位），其餘 5 個因子（月營收YoY加速度/外資連續買超/三大法人淨買/相對強度/站上季線量能）都沒過，原因逐一記錄（其中 2 個是 train/val 正負號相反，1 個差一點點沒到門檻）。

**2026-08-23 Cowork 五點覆核後追加：**
- ✅ `factor_ic.py`：新增 Bonferroni 校正（`required_percentile`/`bonferroni_n`），`N_SHUFFLES` 200→1000。原始 6 因子用當前程式碼重跑確認：5 FAIL 不變，`f_eps_growth` 校正後（門檻98.3）仍 PASS。
- ✅ `factor_ic_eps_expanded.py`（新增）：`f_eps_growth` 擴大樣本重驗，受流量限制只到 83/400 檔，但橫截面延長到 184 個（2008–2024），val IC +0.0742，PASS。
- ✅ `pit.py` 新增 `balance_sheet_pit()`；`factors.py` 擴充 6 個新因子候選（PB/PE、ROE穩定度、低波動、EPS/營收意外SUE、分點集中度）。
- ✅ 3 個新因子成功測試且全過（`f_eps_surprise` val+0.073、`f_revenue_surprise` val+0.050、`f_low_vol` val+0.118，門檻98.3）；2 個（PB/PE/ROE穩定度）因流量限制完全未測；分點集中度確認無免費端點。
- **目前累積 4 個通過因子**：`f_eps_growth`、`f_eps_surprise`、`f_revenue_surprise`、`f_low_vol`。詳見 `FACTORS.md`。

**2026-08-23 Part 1 收尾追加：**
- ✅ `factor_correlation.py`（新增）：4 因子相關性矩陣，`f_eps_growth`/`f_eps_surprise` 同家族（+0.831）去重，其餘獨立。4 因子→3 獨立計分成分。
- ✅ `score.py`（新增）：綜合分引擎，同產業 peer z-score，ETF 覆蓋率不足過濾（`MIN_COMPONENTS_FOR_RANKING`）。
- ✅ `run_score_backtest.py`（新增）：`score_topn_v1` 扣成本+換手回測，train/val 隨機控制組皆 100.0 百分位，判定 `EXPERIMENTAL`（詳見 `LEADS.md`）。
- ✅ `scores.json` + App「選股」頁：已上線，瀏覽器實測通過。
- **意外發現**：FinMind 流量限制已解除（`f_value_pb`/`f_value_pe`/`f_quality_roe_stability` 現在可測），排進馬拉松 TW 軌道，這輪沒有補測。

## 下一步（優先序，僅供接手者參考，實際順序看使用者當下指示）

1. **當下最優先（馬拉松持續進行中，不需要手動觸發）**：全市場宇宙回補（`backfill_universe.py`，`MARATHON_PROTOCOL.md` 5b節，覆蓋率門檻80%前是TW軌最高優先序）。目前 992/3,196（≈31.0%）。
2. 放空可行性重新查驗（`long_only_vs_market.py` 的 `check_shortability()`，上次因限流沒有可信結果，額度恢復後要重跑）。
3. 宇宙回補達到門檻後，重新跑 `long_short_backtest.py`／`long_only_vs_market.py`，看多空/純多結論在更大樣本下是否穩定。
4. `weinstein_stage2_unbiased` 要不要做一次性 holdout 測試（平行線，互不阻塞）——需要明確授權，這裡不會自己決定。
5. `scores.json` 即時資料路徑的架構問題（見上方摘要）——需要使用者決定。

背景待辦（優先度較低，不阻塞上面）：
1. 美股成本模型補到 `costs.py`。
2. 紙上前測影子帳本（里程碑 3 剩下的部分）。

## 目前沒有在等待使用者回覆的事（下面一項例外，**是**在等）

- `weinstein_stage2_unbiased` 是否進 holdout——**是**在等使用者，因為 holdout 一次性、不可逆；但現在不是單純「等授權」，是等 `WEINSTEIN_ALPHA_GATE_TASK.md` 這個 alpha/beta 拆解關卡做完、而且真的通過才會拿去問使用者（見上方「2026-08-25 使用者解除卡關指令」第1點）。
- ~~`scores.json` 即時資料路徑要不要獨立於 holdout 機制之外~~ **已於 2026-08-25 由使用者裁示解除**，見上方「2026-08-25 使用者解除卡關指令」第3點，不再是卡關項目。

其餘背景待辦（含挖礦馬拉松的三軌探索）不阻塞，可以先做。

---

## 檔案地圖

| 檔案 | 用途 | git 狀態 |
|---|---|---|
| `CONSTITUTION.md` | Phase 2 最高原則，違反即無效 | 進 git |
| `DATA.md` | 資料誠實度盤點結果（里程碑 1） | 進 git |
| `STRATEGY_LOG.md` | 里程碑等級敘事日誌 + FILE MANIFEST | 進 git |
| `REPORT.md` | 顆粒度細的 append-only 執行記錄 | 進 git |
| `LEADS.md` | 策略候選登記簿（3 列：`weinstein_stage2_pilot_v1` FAIL、`weinstein_stage2_unbiased` EXPERIMENTAL、`score_topn_v1` EXPERIMENTAL） | 進 git |
| `FACTORS.md` | 因子登記簿（4 個 PASS，去重後 3 個獨立成分） | 進 git |
| `MARATHON_STATE.md` | 本檔案，斷點狀態快照 | 進 git |
| `HOLDOUT_LOCK.json` / `HOLDOUT_LOG.md` | holdout 一次性鎖 + 稽核軌跡 | 進 git（尚未產生） |
| `criteria/*.json` | 鎖定的事前通過標準 | 進 git（尚未產生） |
| `finmind_client.py` / `adjust.py` / `universe.py` / `pit.py` | 資料層 | 進 git |
| `validation/*.py` | 驗證框架 | 進 git |
| `backtest/*.py` | 回測引擎骨架（里程碑 4 新增，2026-08-23 加 `book_name` 欄位） | 進 git |
| `strategies/*.py` | 策略訊號 + 跑法（里程碑 4 新增） | 進 git |
| `factors.py` / `factor_ic.py` / `factor_ic_eps_expanded.py` / `factor_correlation.py` | AI 選股引擎 Phase A 步驟 1/2 + 去重前置 | 進 git |
| `score.py` / `run_score_backtest.py` | AI 選股引擎 Phase A 步驟 3（綜合分 + 扣成本回測） | 進 git |
| `audit_ledgers.py` | 唯讀稽核腳本 | 進 git |
| `data/` | parquet 快取、`data/backtests/`、`data/factor_ic_results.csv`、`data/score_backtest_results.csv`、`data/ledger/trades.csv`、回測結果 | **不進 git**（`.gitignore`） |
| （repo 根目錄）`scores.json` | App「選股」頁資料，`score.py` 產生 | 進 git（跟 `research/data/` 不同層級） |
| （repo 根目錄）`index.html` | App 本體，2026-08-23 新增「選股」分頁 | 進 git |
