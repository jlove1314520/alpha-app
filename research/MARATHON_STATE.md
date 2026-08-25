# MARATHON_STATE.md — 斷點狀態檔

**這份檔案永遠只描述「現在」，會被覆寫，不是 append-only。** 換 session／換機器／換 agent 接手 Phase 2（自動下單引擎）研究工作時，**先讀這份**，再視需要去查 `REPORT.md`（細節動作記錄）、`STRATEGY_LOG.md`（里程碑敘事）、`LEADS.md`（策略候選）、`FACTORS.md`（因子登記簿）。

**最後更新：2026-08-25T17:34:50+08:00**

**馬拉松全局輪次計數器（2026-08-23 新增，使用者要求）：目前累積 71 輪。最新一輪：第 71 輪 · 2026-08-25 18:33 · US · 探測`era_reliability()`個股逐年申報人分級資料，`EntityPublicFloat`確有逐年資料但門檻歷史表/反推邏輯未做，問題推進但未解決。 這是跨 TW/US/FUT 三軌共用的單一遞增計數器，不是各軌自己 commit message 裡那種各軌獨立的輪號。**下一輪的義務：讀這行的數字 N，這輪結束前（見 `MARATHON_PROTOCOL.md` 第 6 節）在 `REPORT.md` 最上面的「心跳記錄」區塊插入一筆 `## 第 N+1 輪 · ...`，並把這行的數字改成 N+1。** 不管這輪做了什麼、有沒有成功，都要留這一筆，這樣任何人（包含使用者自己）打開 `REPORT.md` 最上面就能一眼看出馬拉松最近有沒有在跑、多久跑一次、有沒有卡住。

**▶ 目前狀態：AI 選股引擎 Phase A（步驟 1–4）全部完成並 push；Part 2 挖礦馬拉松已上線自動執行（已跑數輪，三軌都有進展）；Cowork 稽核多空中性結果，三次覆核（付費方案調查/alpha-beta拆解/多空擱置）也已完成並 push。**

**2026-08-24（傍晚）Cowork 三次覆核摘要：** Cowork 定調「純多前decile 是更穩健且可實際執行的方向，多空放空腿先擱置為研究備選」。(1) 查了 FinMind 完整定價（Free$0/Backer$699月/Sponsor$999月/SponsorPro$3330月，流量300~20000次/hr）跟 yfinance 免費備援（可用於價格但**不支援下市股+財報歷史太短**，只能局部緩解）——這是金流決策，回報資訊給使用者，不會自己付款。這次額度恢復過一次，累積到199/3,196（6.2%），維持標記不放寬。(2) 新增 `decompose_alpha_beta()`：**確認贏隨機是選股alpha不只是beta**——四期純alpha年化+15.22%~+24.31%，Sortino多數>1.0，MDD約−11%~−13%；成本敏感度四期在3x下全維持正值，但Validation(週頻)已相當薄弱（+6.17%）。(3) 全市場重跑純多——待宇宙達80%+才能做，這輪還不能開始。(4) `score_longshort_v1` 判定改為 `PENDING`（放空可行性＋券源確認後再議）。完整數字見 `LEADS.md`/`REPORT.md`/`STRATEGY_LOG.md` 2026-08-24（傍晚）條目。

**2026-08-24（下午）Cowork 二次覆核摘要：** 三關逐一處理——(1) 宇宙覆蓋率新增 `backfill_universe.py`（可斷點續傳，已整合進 `MARATHON_PROTOCOL.md` 5b節，TW軌最高優先序背景任務），這次 session 進度到 223/3,196（≈7.0%），**多空/decile結論一律標記「樣本不足、暫不採信」**（`LEADS.md` 新增這個判定類別）。(2) 月頻train/val不一致查到根源（複利被少數極端月份主導+換股名單不穩定），確認不是bug，但跨期一致關卡目前無法通過，多空框架維持降級。(3) 放空可行性查驗撞限流沒有可信結論（待重驗）；**但意外發現「純多前decile相對大盤」四期全部一致強勁（年化+23.77%~+33.67%，beta合理+0.6~+0.7，alpha顯著為正，贏隨機對照100百分位，沒有跨期不一致問題）**，是目前唯一馬上可執行、不依賴放空的候選雛形，同樣受宇宙覆蓋率限制標記「樣本不足、暫不採信」。**使用者從這輪起要求所有產出一律用繁體中文**，已全面遵守。完整數字見 `LEADS.md`/`REPORT.md`/`STRATEGY_LOG.md` 2026-08-24（下午）條目。

**2026-08-24 Cowork 稽核回應摘要：** `score_topn_v1`（長多前10名）雖贏配對隨機對照組，但絕對報酬輸買進持有、且買進持有基準本身有偏差——Cowork 指出這代表「這個實作形式」沒有實用價值。改用多空市場中性設計（`long_short_backtest.py`：買前decile/空後decile，實測 beta 而非假設，新增放空成本模型）+ 全市場隨機抽樣（非原本偏差樣本，但受 FinMind 流量限制只達 170/3,196 檔≈5.3%覆蓋率，誠實揭露）。**結果：四期（train/val×週/月頻）beta 全部接近零、配對隨機控制組全部 100.0 百分位——證實因子橫截面排序能力是真的**；誠實揭露 Train(月頻) 絕對報酬跟 Sortino 為負，沒有淡化。過程中修好 3 個真 bug（欄位名、小樣本異常值放大、beta/alpha 扣成本前後不一致）+ 1 個效能問題（忘記帶過之前已修過的快取優化）。完整數字見 `LEADS.md`/`REPORT.md` 2026-08-24 條目。**全市場覆蓋率的落差留給使用者決定是否要繼續補。**

**Part 1 收尾摘要（2026-08-23）：** 因子相關性去重（`f_eps_growth`/`f_eps_surprise` 同家族合併，4 因子→3 獨立成分）；`score.py` 綜合分引擎（同產業 peer z-score，ETF 覆蓋率不足過濾）；`run_score_backtest.py` 扣成本+換手組合回測（train/val 隨機控制組皆 100.0 百分位，但絕對報酬輸給零成本買進持有——判讀方式見 `LEADS.md`/`FACTORS.md`，`score_topn_v1` 判定 `EXPERIMENTAL`）；App「選股」頁上線（`scores.json`，瀏覽器實測過）。**留下未解決的架構問題**：`scores.json` 目前用 `VAL_END` 當基準日（非即時），步驟5「每日排程」需要的即時資料路徑要不要獨立於 holdout 機制之外，待使用者決定。詳見 `FACTORS.md`/`STRATEGY_LOG.md`/`REPORT.md` 2026-08-23 條目。

**Part 2 挖礦馬拉松：✅ 已上線，Windows 工作排程器每 30 分鐘自動執行。** 協定文件 `MARATHON_PROTOCOL.md`＋三軌獨立檔案（`TW_LEADS.md`/`US_LEADS.md`/`FUT_LEADS.md` 等）＋跨軌累積試驗總帳 `TRIALS_LEDGER.md`（seed 12 筆，第一輪馬拉松後累積到 15 筆）＋檔案鎖 `marathon_lock.py`。**手動測試第一輪（09:47–09:53）完全成功**：正確讀協定、選 TW 軌、測試 `f_value_pb`/`f_value_pe`/`f_quality_roe_stability` 便宜關卡，正確執行「批次過但累積校正後降級」邏輯（`f_value_pe`），commit+push+釋放鎖檔全部正常，還自己扛過一次暫時性網路失敗並重試成功。使用者確認後已註冊 Windows 工作排程器任務 `AlphaMarathon`（`C:\alpha\run-marathon-cycle.ps1`，`--dangerously-skip-permissions` + 限縮工具集 + `--max-budget-usd 5`，只在使用者登入 Windows 時執行，重疊觸發自動略過，25分鐘執行上限）。**下一輪起會完全無人值守自動執行**，之後接手的 session 要定期用 `git log`／`TRIALS_LEDGER.md` 檢查馬拉松進度，不需要自己手動觸發。

**Cowork 五點覆核結果摘要（2026-08-23）：** (1) `f_eps_growth` 的 PIT 正確性二次確認為真，不需重算；(2) 加 Bonferroni 校正（門檻 90→98.3 百分位）後 `f_eps_growth` 依然通過，5 個原 FAIL 不變；(3) 全市場/400檔擴大重驗被 FinMind 流量限制擋下（未完成），但用已快取樣本延長橫截面歷史（121→184個，2008–2024）驗證仍過；(4) 擴充 6 個新因子候選——3 個成功測試且全部通過（`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`），2 個（PB/PE、ROE穩定度）因流量限制完全未測，1 個（分點集中度）確認無免費資料源；(5) 目前累積 **4 個** 通過的因子，但因子間相關性未查、3 個新因子未測，依然不進 `score.py`。詳見 `FACTORS.md`／`REPORT.md` 2026-08-23 條目。

**GitHub 稽核狀態：✅ 通過**（12:00 的 `.py` 檔案存在性問題是 Cowork 端舊快照；13:00 的 holdout 截斷漏洞是真的，已修復）。**如果又收到類似回報，先照 STRATEGY_LOG.md 的 FILE MANIFEST 重新走一次驗證，不要預設是自己這邊漏推，也不要預設對方一定錯。**

**Holdout 狀態：✅ 依然未被使用。** `is_holdout_consumed()` 複查為 `False`，`HOLDOUT_LOCK.json` 不存在。目前有一個候選（`weinstein_stage2_unbiased`）train/val 全部關卡都過，是否要花掉這個專案唯一一次 holdout 測試機會在它身上，**需要使用者明確授權，這裡不會自己決定**。

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

依使用者設計書分 5 步：因子庫→因子IC檢定→計分→App選股頁→每日排程。**目前狀態：步驟 1–4 全部完成。步驟 5（每日排程）留有一個未解決的架構問題（即時資料 vs holdout 邊界，見上方摘要與 `FACTORS.md`），需要使用者決定後才會動工，不會自己繞過去做。**

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

## 目前沒有在等待使用者回覆的事（下面兩項例外，**是**在等）

- `weinstein_stage2_unbiased` 是否進 holdout——**是**在等使用者，因為 holdout 一次性、不可逆。
- `scores.json` 即時資料路徑要不要獨立於 holdout 機制之外——**是**在等使用者決定。

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
