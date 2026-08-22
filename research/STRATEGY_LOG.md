# 策略研究日誌

依 `CONSTITUTION.md`「地基先行」原則的執行紀錄，記里程碑等級的敘事與決策脈絡。最新在最上面。誠實記錄，包含負面/未完成結果——不做的、還沒做的都要寫，不能只記做成的部分。

**2026-08-22 起**：顆粒度更細的單一動作記錄（一個函式寫完測完、一個 bug 修好）改記到 [`REPORT.md`](./REPORT.md)（append-only）。現在整體卡在哪、下一步是什麼，看 [`MARATHON_STATE.md`](./MARATHON_STATE.md)。策略候選的最終判定記在 [`LEADS.md`](./LEADS.md)；**因子**的 IC 檢定判定記在 [`FACTORS.md`](./FACTORS.md)（策略跟因子是兩種不同單位，分開記）。這份 `STRATEGY_LOG.md` 繼續當里程碑級的主線敘事，不會被取代。

---

## 2026-08-23 — Cowork 五點覆核回應：因子候選從 1 個增加到 4 個（PIT二次確認、Bonferroni校正、擴大重驗、擴充因子庫）

Cowork 針對上一輪唯一通過的 `f_eps_growth` 提出 5 點要求，逐一誠實回應：

**1. PIT 正確性二次確認：** 逐日比對 2330 的 `f_eps_growth` 因子值變動日跟 `pit.py` 算出的揭露日，包含一筆春節連假案例（`pit_date=2024-02-14` 卡假期，因子值到下個交易日 `02-15` 才變）驗證無誤。**確認本來就是對的，不需要重算**——這跟「抓到 bug 修好」是不同種類的結論，這裡明確區分開來。

**2. 多重比較校正：** 6 個因子同批測，Bonferroni 校正把通過門檻從 90 百分位拉到 98.3 百分位（`factor_ic.py` 新增 `bonferroni_n` 參數，`N_SHUFFLES` 也從 200 提高到 1000 以撐住這個精確度）。用當前程式碼重新完整跑一次：5 個原 FAIL 因子結論不變，**`f_eps_growth` 校正後依然通過**——不是壓線擦邊的 1/6，是拉高門檻後仍站得住腳的結果。

**3. 全市場/更長橫斷面重驗：** 誠實限制——FinMind 免費額度流量上限被真實觸發（HTTP 402），完整擴大到全市場 3,196 檔或穩定拿到 400 檔新樣本都沒有達成。在限制內做了能做的部分：橫截面歷史從 121 個（2015起）延長到 184 個（2008起，多涵蓋一段完整景氣循環，樣本雖只到 83/400 檔），`f_eps_growth` val IC +0.0742，打散對照 100 百分位，依然 PASS。**擴大樣本數這個目標沒有達成，明確記錄，不是藏起來。**

**4. 擴充因子庫：** 新增 6 個候選——分點集中度調查後確認 FinMind 免費層無可用端點，直接排除不測；PB/PE、ROE穩定度因流量限制完全無法測試（100 檔樣本每一檔都被擋），誠實標記「未測試」而非「FAIL」；EPS意外/營收意外(SUE 方法論)、低波動三個成功測試，**全部通過**（`f_eps_surprise` val+0.073、`f_revenue_surprise` val+0.050、`f_low_vol` val+0.118，都在校正後的 98.3 高門檻下過關，`f_low_vol` 是目前 val IC 最強、也是唯一零 PIT 風險的因子）。過程中意外發現並修好一個真實脆弱點：`prepare_factors()` 原本一個新資料集被 402 擋下就會讓整檔股票（連同其他 9 個已算好的因子）一起被丟棄，改成 try/except 隔離後才不會互相拖累。

**5. 累積現況：** 通過因子從 1 個增加到 **4 個**（`f_eps_growth`、`f_eps_surprise`、`f_revenue_surprise`、`f_low_vol`），橫跨基本面成長/意外跟純價格波動度兩類不同資料，不是同一訊號的變形版本。**依然不會自己進 `score.py`**：3 個新因子完全未測（等流量解除）、4 個已通過因子彼此的相關性/共線性也還沒查（可能高度相關、實質是同一訊號被算了三次），這些都要先確認才能談計分權重。

完整逐因子數字、判定表格、已知限制見 `FACTORS.md`（已大幅更新）；技術細節、驗證過程見 `REPORT.md` 對應條目。`is_holdout_consumed()` 複查為 `False`。**任務在此停下，等 Cowork／使用者審完再決定要不要進步驟 3。**

---

## 2026-08-22 — Cowork 修正兩個方法論缺陷後重跑：無偏宇宙 + 配對式控制組，結果 EXPERIMENTAL（train/val 全過，未碰 holdout）

Cowork 確認上一輪 `weinstein_stage2_pilot_v1` 的 `FAIL` 判定本身是對的（「贏不過隨機對照＝賺的是 beta 不是 alpha」），但指出測試方法有兩個問題，修好才有效：靜態買進持有對照組不是策略機制的公平對照；手選大型股宇宙本身帶存活者/選擇偏差。這輪把兩個都修了，重跑同一套 Weinstein 第二階段訊號。

**控制組修正**（`validation/control_group.py` 新增 `run_matched_control_group()`）：不再用「隨機抽 N 檔靜態持有」，改成「拿策略真實跑出來的進出場日期表（同樣的再平衡頻率、同樣的部位數、同樣的持有天數分布），200 次隨機重抽只換掉每筆交易的股票代號，其他（進場日、出場日、部位大小、成本公式）完全比照真實策略」。這是機制上真正對應的隨機對照。

**宇宙修正**：不再手選知名股，改用 `universe.py` 的全市場名單（post-2003 + 含下市股，3,196 檔）做固定種子隨機抽樣。**仍是抽樣（100 檔，82 檔有效資料），不是逐檔全市場掃描**——全市場的資料量在 FinMind 免費額度下會花太久，這輪先驗證「無偏抽樣」跟「偏差手選」的差異有多大，均勻隨機抽樣跟全市場逐檔掃描在統計性質上是不同層次的嚴謹度，但已經是很不一樣、也重要得多的修正，比繼續用手選清單好得多。

**跑的過程中意外抓到 3 個真的程式碼 bug**（不是資料問題），全部是「檢查空值前就先呼叫 `.sort_values()`」這個模式：`adjust.py` 的 `adjustment_events()` 在 `events` 列表為空時、`adjusted_price_series()` 在 `raw` 為空時，都會在檢查 `.empty` 之前就先鏈式呼叫 `.sort_values(...)`，導致對 0 欄位的空 DataFrame 呼叫時丟出 `KeyError`；另外 `backtest/engine.py` 在 `fill_price` 為 0（少數冷門/瀕臨下市個股的資料異常）時會除以零崩潰。三個都修好、也重新對修好前會出錯的股票代號逐一驗證過確實不再出錯。這是無偏隨機抽樣的價值之一——手選的知名大型股不會踩到這些冷門股票才有的資料邊界情況，全市場抽樣才會。

**結果（誠實記錄，這次是正面結果，但仍要照規矩標記）：**
- Validation（2021–2024，276 筆交易）：+145.4%，MDD −22.41%，Sortino 0.702，贏買進持有（+54.6%）。
- Train（2015–2020，514 筆交易）：+99.5%，MDD −29.11%，Sortino 0.444，贏買進持有（+58.9%）。
- 成本 1x/2x/3x 敏感度穩健：+145.4%→+136.4%→+127.4%，沒有翻負。
- **配對式隨機控制組：策略打贏 200 次重抽的第 99.5 百分位**，50/90/95/99 四個門檻全部達標。
- 用 `audit_ledgers.py` 對兩批真實交易紀錄（train 514、validation 276 筆）稽核，全部 PASS。

**這是目前唯一四項關卡全部通過的候選。但依 `LEADS.md` 既有規則，`PASS` 判定必須包含 holdout 驗證，這輪完全沒有碰 holdout（`is_holdout_consumed()` 複查為 `False`），所以正確的判定是 `EXPERIMENTAL`，不是 `PASS`。** 即使 train/val 表現很好，也不能因為結果好看就放寬自己訂的規則——這正是 `CONSTITUTION.md`「事前綁定標準,絕不事後移動門柱」要防的事。是否要進入一次性 holdout 測試（測過即焚），是需要使用者明確授權的決定，這裡不會自己決定。

完整技術細節、bug 修復過程、驗證步驟見 `REPORT.md` 對應條目；候選記錄見 `LEADS.md`。

---

## FILE MANIFEST（給稽核用，逐檔核對）

repo：`jlove1314520/alpha-app`，分支 `main`。**每次新增/刪除 `research/` 底下的檔案，這張表要跟著更新**——這張表本身如果跟 repo 實際內容對不上，就是一種未被記錄的漏洞，發現對不上要立刻修這張表，不能放著。

最後逐檔驗證時間：**2026-08-23T01:30:00+08:00**（承接 8/22 16:00 那次的驗證方式：`git ls-tree origin/main` + `raw.githubusercontent.com` HTTP 200 + GitHub API `contents`/`commits` 交叉核對）。

| 路徑（repo 相對） | 用途 | 型態 |
|---|---|---|
| `research/MARATHON_PROTOCOL.md` | **2026-08-23 新增**：30分鐘挖礦馬拉松操作規則。每個無人值守的 headless 執行個體開工前必讀，是它唯一的記憶來源 | 文件 |
| `research/MARATHON_CONTINUATION_PROMPT.txt` | **2026-08-23 新增**：Windows 工作排程器每輪傳給 `claude -p` 的實際 prompt 文字（極簡，指向 `MARATHON_PROTOCOL.md`） | 文件 |
| `research/TRIALS_LEDGER.md` | **2026-08-23 新增**：跨三軌累積試驗總帳，多重比較校正的 `bonferroni_n` 從這裡讀（seed 12 筆歷史試驗） | 文件 |
| `research/TW_LEADS.md` / `research/US_LEADS.md` / `research/FUT_LEADS.md` | **2026-08-23 新增**：三軌各自的因子/策略候選登記簿（馬拉松開始後新增的候選，不重複馬拉松前的 `FACTORS.md`/`LEADS.md`） | 文件 |
| `research/TW_MARATHON_STATE.md` / `research/US_MARATHON_STATE.md` / `research/FUT_MARATHON_STATE.md` | **2026-08-23 新增**：三軌各自的斷點狀態快照（覆寫式） | 文件 |
| `research/TW_LOG.md` / `research/US_LOG.md` / `research/FUT_LOG.md` | **2026-08-23 新增**：三軌各自的 append-only 執行記錄 | 文件 |
| `research/marathon_lock.py` | **2026-08-23 新增**：防止兩輪馬拉松並行執行的檔案鎖（`.marathon.lock`，gitignore，含 25 分鐘陳舊鎖自動恢復） | 程式碼 |
| `research/CONSTITUTION.md` | Phase 2 最高原則（驗證紀律鐵律 + 股票 vs 加密貨幣本質差異） | 文件 |
| `research/DATA.md` | 里程碑 1：FinMind 資料誠實度盤點結果（還原股價/存活者偏差/PIT 財報三顆地雷） | 文件 |
| `research/STRATEGY_LOG.md` | 本檔案。里程碑等級敘事日誌 + 本 FILE MANIFEST | 文件 |
| `research/REPORT.md` | append-only 細顆粒執行記錄 | 文件 |
| `research/LEADS.md` | 策略候選登記簿（3 列：`weinstein_stage2_pilot_v1` FAIL、`weinstein_stage2_unbiased` EXPERIMENTAL、**2026-08-23 新增 `score_topn_v1` EXPERIMENTAL**） | 文件 |
| `research/FACTORS.md` | **2026-08-22 新增，2026-08-23 大幅更新**：因子登記簿 + 因子相關性去重 + score.py 方法論。累計 4 個通過（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`），去重後 3 個獨立計分成分 | 文件 |
| `research/MARATHON_STATE.md` | 斷點狀態快照（覆寫式，換 session 先讀這個） | 文件 |
| `research/finmind_client.py` | FinMind 抓取+快取層。`load_dev()` 是策略/分析程式碼**唯一**該用的入口（自動截斷在 `VAL_END`）；`load_full_history()` 是唯一合法的無截斷路徑（只能餵給 `unlock_holdout_once()`）；`_fetch()` 是底層 internal 函式，不該被外部直接呼叫 | 程式碼 |
| `research/adjust.py` | 台股還原股價（用 `TaiwanStockDividend` 自組，因為 `TaiwanStockPriceAdj` 要付費），透過 `load_dev()` 抓資料，自動截斷 | 程式碼 |
| `research/universe.py` | TW 回測宇宙建構（2003 年後 + 納入下市股，處理存活者偏差），刻意用 `_fetch()` 不截斷（會員名單非價量資料，理由見檔案內 docstring） | 程式碼 |
| `research/pit.py` | 財報/月營收/資產負債表 point-in-time 保守發布延遲假設，透過 `load_dev()` 抓資料，自動截斷（**2026-08-23 新增 `balance_sheet_pit()`**，同 `quarterly_pit()` 邏輯，供 ROE 穩定度因子用） | 程式碼 |
| `research/audit_ledgers.py` | 唯讀稽核腳本，對 `trades.csv` 跑 3 條恆等式檢查（含 holdout 洩漏偵測） | 程式碼 |
| `research/validation/__init__.py` | `validation` package 標記 | 程式碼 |
| `research/validation/holdout.py` | train/val/holdout 物理隔離、一次性解鎖機制、`assert_no_holdout_leakage()` 硬性斷言 | 程式碼 |
| `research/validation/costs.py` | 台股成本/摩擦模型（手續費/證交稅/滑價/漲跌停鎖死偵測） | 程式碼 |
| `research/validation/control_group.py` | 隨機控制組。`run_control_group()` 是原本的靜態版本（仍保留給其他簡單場景）；**2026-08-22 新增 `run_matched_control_group()`**——依 Cowork 要求，用策略真實進出場日期表只換股不換時間，才是機制上對應的隨機對照 | 程式碼 |
| `research/validation/criteria.py` | 事前綁定通過標準（雜湊鎖定，防止事後移動門柱） | 程式碼 |
| `research/backtest/__init__.py` | `backtest` package 標記 | 程式碼 |
| `research/backtest/engine.py` | 通用回測引擎骨架。走日曆逐日模擬，訊號 T 日收盤產生、T+1 收盤成交（零 look-ahead），三層風控（MA出場/部位上限/硬停損），成本走 `validation/costs.py`（`buy_leg_rate()`/`sell_leg_rate()` 是給 `control_group.py` 重用的單一事實來源），資料進場前用 `assert_no_holdout_leakage()` 檢查。`BacktestResult` 有 `max_drawdown_pct`／`sortino_ratio` 屬性（**2026-08-22 追加 Sortino**）。**2026-08-23**：`BacktestConfig` 新增 `book_name` 欄位（修正原本寫死 `"weinstein_stage2_pilot"` 的真 bug，重用同一顆引擎跑非 Weinstein 策略時帳本會被誤標） | 程式碼 |
| `research/strategies/__init__.py` | `strategies` package 標記 | 程式碼 |
| `research/strategies/weinstein_stage2.py` | Weinstein 第二階段訊號函式（150日均線上揚+站上、60日動量排名）+ 大盤200日均線總體閘門，插進 `backtest/engine.py` 用 | 程式碼 |
| `research/strategies/run_weinstein_pilot.py` | 第一輪跑法（手選 30 檔試點宇宙、靜態控制組）——**方法論已知有缺陷**（見 `weinstein_stage2_pilot_v1` 在 `LEADS.md` 的紀錄），保留是為了留下完整歷史，不是推薦用法 | 程式碼 |
| `research/strategies/run_weinstein_unbiased.py` | 修正版跑法（`universe.py` 全市場隨機抽樣 100 檔 + `run_matched_control_group()`），結果見 `LEADS.md` 的 `weinstein_stage2_unbiased` 列 | 程式碼 |
| `research/factors.py` | **2026-08-22 新增，2026-08-23 擴充**：AI 選股引擎 Phase A 步驟 1。原始 6 個 + 新增 6 個候選因子（價值PB/PE、品質ROE穩定度、低波動、EPS/營收意外SUE、分點集中度已調查確認不可行），全部透過 `load_dev()`／`pit.py` 的 `pit_date` 做 point-in-time 對齊（`merge_asof(direction='backward')`），`prepare_factors()` 對新資料集的呼叫包 try/except 避免單一資料集被擋時連累其他因子 | 程式碼 |
| `research/factor_ic.py` | **2026-08-22 新增，2026-08-23 加 Bonferroni 校正**：Phase A 步驟 2。因子 IC 檢定（Spearman 等級相關 vs 未來20日報酬，train/val 分開、隨機打散對照組，`required_percentile`/`bonferroni_n` 支援多重比較校正），結果見 `FACTORS.md` | 程式碼 |
| `research/factor_ic_eps_expanded.py` | **2026-08-23 新增**：Cowork 覆核第3點，`f_eps_growth` 擴大樣本/延長橫斷面重驗（受流量限制未達成 400 檔目標，見 `FACTORS.md`） | 程式碼 |
| `research/factor_correlation.py` | **2026-08-23 新增**：AI 選股引擎 Phase A 步驟 3 前置作業。4 個通過因子的相關性矩陣＋去重判定，結果見 `FACTORS.md` | 程式碼 |
| `research/score.py` | **2026-08-23 新增**：Phase A 步驟 3。綜合分引擎（同產業 peer z-score、去重後 3 個獨立成分等權平均、`export_scores_json()` 產生 App 用的 `scores.json`） | 程式碼 |
| `research/run_score_backtest.py` | **2026-08-23 新增**：對 `score.py` 綜合分前 N 名做扣成本+換手組合回測（重用 `backtest/engine.py`），含配對式隨機控制組，結果見 `LEADS.md` 的 `score_topn_v1` 列 | 程式碼 |
| `research/data/` | parquet 快取、`data/backtests/`（回測交易/權益曲線 CSV）、`data/factor_ic_results.csv`（因子IC原始數字）、`data/score_backtest_results.csv`、`data/ledger/trades.csv`（未來紙上帳本） | **不進 git**（`.gitignore`），內容只存在本機，Cowork 讀不到屬正常 |
| `research/HOLDOUT_LOCK.json` / `research/HOLDOUT_LOG.md` | holdout 一次性鎖 + 稽核軌跡 | 進 git，**尚未產生**（還沒用過 holdout） |
| `research/criteria/*.json` | 鎖定的事前通過標準檔 | 進 git，**尚未產生**（第一個候選這輪沒有鎖定標準檔，見 `LEADS.md` 備註） |
| `scores.json`（repo 根目錄，非 `research/` 底下） | **2026-08-23 新增**：App「選股」頁讀取的靜態排行榜資料，`research/score.py` 產生，基準日 `VAL_END`（2024-12-31，非即時，見下方架構問題備註） | 進 git（App 資料檔，跟 `research/data/` 不同層級） |
| `index.html`（repo 根目錄） | App 本體。**2026-08-23**：新增「選股」分頁（nav 第 3 項、`scr-picks` 畫面、`hydratePicks()`/`renderPicks()`/`showPickDetail()`） | 進 git |

---

## 2026-08-23 — Part 1 收尾：因子去重 + score.py 綜合分引擎 + 扣成本組合回測 + App 選股頁上線

前一輪 Cowork 五點覆核完成後，使用者授權往下做，指示「先做 Part 1 push 後，再設 Part 2 的排程」。這輪把 AI 選股引擎 Phase A 剩下的步驟（3：計分、4：App 選股頁）一次做完。

**去重（因子相關性矩陣，`factor_correlation.py`）**：`f_eps_growth`／`f_eps_surprise` 相關 +0.831，同家族去重合併成 `eps_family`；`f_revenue_surprise`／`f_low_vol` 跟其他都 ≤0.27，獨立保留。**4 個通過 IC 檢定的因子 → 3 個獨立計分成分**，完整表格見 `FACTORS.md`。

**`score.py`**：3 個成分各自算同產業（`TaiwanStockInfo` industry_category）peer z-score 後等權平均。發現並修好一個資料品質陷阱：ETF（00844B/00923）沒有真實 EPS/營收資料，只靠低波動一個成分就能排到前段班——加了「至少 2/3 成分有資料才進榜」的過濾器。**意外發現 FinMind 流量限制已解除**（`TaiwanStockPER`／`TaiwanStockBalanceSheet` 現在對整批樣本都能正常抓到），代表 8/22 記錄為「完全未測」的 3 個新因子現在可以重測了——這輪沒有補做，排進後續馬拉松軌道（見下）。

**組合回測（`run_score_backtest.py`）**：對綜合分前 10 名做完整扣成本+換手回測，重用 `backtest/engine.py` 既有機制（發現不需要重寫引擎，`signal_fn` 介面剛好適配）。**結果：train/val 兩期，配對式隨機控制組（同換股時點/檔數/成本，只換挑的股票）都是 100.0 百分位，完勝全部 60 次重抽**——這證實因子 IC 不只是紙上數字，扣除真實成本跟週頻換股摩擦後依然顯著優於同機制的隨機選股。**誠實揭露反直覺的一面**：絕對報酬輸給零成本全樣本買進持有（因為週頻換股機制本身摩擦成本很高，隨機對照組中位數在 train 期甚至倒賠約 30%），正確判讀方式是看隨機對照組百分位而非零成本被動基準的差距——這跟 `weinstein_stage2` 系列的教訓完全一致。過程中修好 `backtest/engine.py` 一個真 bug（`book` 欄位寫死成 Weinstein 的書名，重用引擎跑別的策略會誤標帳本）。判定 `score_topn_v1` **EXPERIMENTAL**（train/val 全過，未碰 holdout），完整數字見 `LEADS.md`。

**App「選股」頁上線**：新增第 3 個 nav 分頁，`score.py` 產生 `scores.json`（repo 根目錄，進 git，非 `research/data/`）給前端讀。**開發過程抓到並修好一個真的 bug**：`json.dump()` 對 `NaN` 輸出非合法 JSON 的 `NaN` token，瀏覽器正確拒絕解析——修成在轉成純 Python dict 後才把 NaN 換成 None（pandas float64 欄位無法直接持有 None），並加 `allow_nan=False` 當硬性防線。**用瀏覽器實測過**（本機 HTTP server 模擬 GitHub Pages 靜態託管，非 `file://`）：排行榜正確渲染、點列展開因子拆解正確顯示，首頁等既有功能沒有被破壞（回歸測試）。

**留下但誠實標註未解決的架構問題**：使用者原始設計書的步驟 5（每日排程更新 `scores.json`）需要 `VAL_END` 之後到「今天」的資料，這段目前架構上算 holdout；但「用已驗證方法論跑新資料產生每日選股」跟「拿 holdout 資料去決定/調整策略設計」是不同的事，前者不污染任何驗證結論。是否要開一條獨立於 `unlock_holdout_once()` 之外的即時資料路徑，留給使用者決定，這裡沒有自己決定或繞過。詳見 `FACTORS.md`／`REPORT.md` 對應段落。

**Holdout 複查：** `is_holdout_consumed()` 再次確認為 `False`，`scores.json` 用 `VAL_END` 當基準日，全程沒有觸碰任何 holdout 資料。

**下一步：** commit + push 完這輪，接著設 Part 2——30 分鐘挖礦馬拉松（Windows 工作排程器，三軌獨立：TW/US/期貨），詳見 `MARATHON_STATE.md` 跟新增的馬拉松協定文件。

---

## 2026-08-22 — AI 選股引擎 Phase A 步驟 1／2：因子庫 + IC 檢定，6 個因子只有 1 個過關

新任務啟動：AI 選股引擎（重運算在 Python 端、App 只當 viewer）。依使用者指示，這輪只做步驟 1（因子庫 `factors.py`）跟步驟 2（因子 IC 檢定 `factor_ic.py`），做完 push 後停下來等 Cowork／使用者審，**不會自己往下做步驟 3（計分 `score.py`）或步驟 4（App 選股頁）**。

**六個因子全部實作並跑出結果**（定義、point-in-time 處理方式見 `factors.py` docstring 跟下方 `FACTORS.md` 摘要）：(a) 月營收YoY加速度、(b) EPS成長、(c) 外資連續買超強度、(d) 三大法人淨買/流動性（**市值資料 `TaiwanStockMarketValue` 付費，用流動性正規化替代，見下方**）、(e) 相對強度(vs大盤60日)、(f) 站上季線+量能放大。全部資料透過 `load_dev()` 或 `pit.py` 取得，完全沒有呼叫 `_fetch()`。

**基本面/技術面資料的 point-in-time 對齊，用 `pandas.merge_asof(direction='backward')` 鍵在 `pit.py` 的 `pit_date`（不是財報所屬期間日）**——這是這次跟 `weinstein_stage2` 系列策略不同的新技術，因為因子需要「逐日」查詢「當時已知的最新財報數字」，不是策略那種「整批抓進來就好」。用真實資料驗證過這個對齊完全正確：把 2330 的月營收 YoY 加速度因子逐日攤開，因子值變動的那幾天，精確對應到 `pit.py` 算出來的揭露日（或揭露日是假日時，對應到之後第一個交易日），沒有提早一天。

**IC 檢定方法**（`factor_ic.py`）：跟 `weinstein_stage2_unbiased` 同一套無偏抽樣（`universe.py` 全市場、固定種子 `20260822`、100 檔抽樣、80 檔可用），121 個不重疊的 20 交易日橫截面（2015–2024），train/val 分開算 Spearman IC，並且對驗證期做「打散因子與股票對應關係」的隨機對照組（200 次），這是因子檢定版的隨機控制組——因子必須贏過至少 90% 的打散結果才算有訊號，不能只看 IC 數字本身好不好看。

**結果（誠實記錄，完整表格在 `FACTORS.md`）：**

| 因子 | Val IC | 打散對照百分位 | 判定 |
|---|---|---|---|
| (a) 月營收YoY加速度 | +0.0249 | 84.5 | FAIL（差一點，沒到90%門檻） |
| (b) EPS成長 | +0.0730 | **100.0** | **PASS** |
| (c) 外資連續買超強度 | −0.0220 | 76.0 | FAIL（train/val正負號相反） |
| (d) 三大法人淨買/流動性 | −0.0198 | 76.5 | FAIL |
| (e) 相對強度(vs大盤60日) | +0.0094 | 38.5 | FAIL（train/val正負號相反） |
| (f) 站上季線+量能放大 | −0.0033 | 15.0 | FAIL |

**6 個因子只有 1 個（EPS成長）通過。** 這不是實作失敗，是誠實測出的結果：這批以技術面/籌碼面為主的因子在無偏抽樣的台股樣本裡，大多數沒有穩定站得住腳的訊號，基本面因子（EPS 年增率）目前唯一撐得住。特別值得注意的是 (c) 跟 (e) 兩個因子 train 期跟 val 期正負號相反——如果只看 train 期會誤以為它們有效，這正是為什麼一定要拆開 train/val 分別看、不能只看合併後的單一 IC 數字。

**已知限制（誠實列出，`FACTORS.md` 有更完整版本）：** 樣本 80 檔非全市場逐檔掃描；驗證期只有 47 個不重疊橫截面，樣本數不算大；因子 (d) 用流動性代替市值（付費資料的已知替代）；只測了單一 20 日報酬窗口，沒有測其他持有期。

完整技術細節、point-in-time 驗證過程見 `REPORT.md` 對應條目；逐因子完整數字見 `FACTORS.md`。**任務在此停下，等 Cowork／使用者審完再決定要不要進步驟 3。**

---

## 2026-08-22 — 里程碑 4 開工：回測引擎骨架 + 第一個 baseline（Weinstein 第二階段），結果 FAIL

驗證框架通過 Cowork 逐行稽核後，進入里程碑 4：建可重用的回測引擎骨架，插入第一個策略訊號（Weinstein 第二階段掃描），跑完整穩健性關卡。**結果誠實記錄：這個候選沒有通過**（隨機控制組沒打贏），細節如下，不做美化。

**引擎骨架**（`backtest/engine.py`）：日曆逐日走，訊號 T 日收盤產生、T+1 收盤才成交（結構上不可能同根 K 用到未來），三層風控（150日均線出場／最大持倉數／硬停損），成本一律呼叫 `validation/costs.py`（不自訂數字），資料進來前一律先過 `assert_no_holdout_leakage()`。策略訊號跟引擎分離（`strategies/weinstein_stage2.py` 插入 `backtest/engine.py`），之後其他策略可以重用同一顆引擎。

**Weinstein 第二階段訊號**：股票層——收盤價 > 上揚的150日均線（日線近似30週線）；大盤層——加權指數 > 200日均線當總體閘門，關閉時不開新倉；動量——通過篩選的股票用60日報酬排名，週頻（週五）換股取前10名。價格用 `adjust.py` 還原價。

**試點宇宙的坦白：這輪不是全市場掃描。** 全市場（`universe.py` 的 3,196 檔）要抓的歷史資料量，用 FinMind 免費額度會撞到流量上限、也會花好幾個小時，這輪先用手選的 30 檔知名台股大型權值股驗證引擎本身對不對，**不是**真的「全市場」——這個限縮條件直接影響了下面隨機控制組沒打贏的解讀（見下段），沒有藏起來。

**結果（完整穩健性關卡，一次跑完，`LEADS.md` 有更完整版本）：**
- Train（2015–2020，324 筆交易）：+168.4% vs 買進持有 +58.9%，贏。
- Validation（2021–2024，160 筆交易）：+135.8% vs 買進持有 +54.6%，贏。
- 成本敏感度 1x/2x/3x：+135.8% → +129.7% → +123.6%，穩健，沒有翻負。
- **隨機控制組（validation 期）：沒打贏。** 策略期末權益在 200 次隨機抽樣（同宇宙、同部位數 10 檔、靜態買進持有）對照組裡只排第 24.5 百分位——中位數隨機組合反而比策略賺得多。

**為什麼會這樣（誠實的解讀，不是找藉口）：** 30 檔試點宇宙是手選的知名大型權值股，剛好是 2021–2024 台股 AI/半導體超級多頭的主要受惠者，這個宇宙本身已經帶著後見之明式的贏家集中——隨機抽 10 檔靜態持有就能吃到大部分漲幅。策略的週頻換股＋均線停損＋動能排名在這種單邊噴出格局裡，反而會因為停損出場、換股交易成本，錯過部分持續噴出的段落，輸給什麼都不做的靜態持有。用 `audit_ledgers.py` 對兩批真實跑出來的交易紀錄（train 324 筆、validation 160 筆）都跑過稽核，全部 PASS，帳本邏輯自洽——**這不是引擎的 bug，是策略在這個試點條件下真的沒有訊號優勢**。

**已知簡化，都是刻意的、寫清楚的，不是漏做：**
1. 隨機控制組比的是「靜態隨機買進持有」，不是「動態週頻隨機重抽」——後者才是跟策略機制完全對應的對照組，這輪先用比較好實作的靜態版本，正確性方向沒問題但嚴謹度打了折扣。
2. `criteria.py` 的事前鎖定標準這輪沒有用——那個機制的設計初衷是給 holdout 那種一次性、高風險評估用的，train/val 這層的通過標準本來就已經寫死在 `CONSTITUTION.md`（打贏控制組、通過成本敏感度、交易數≥100、贏買進持有），不需要再另外鎖一份雜湊檔。
3. 30 檔試點宇宙 ≠ 全市場，見上段。

**絕對沒有碰 holdout。** `research/HOLDOUT_LOCK.json` 依然不存在，`unlock_holdout_once()` 一次都沒被呼叫過。

**下一步：** 這個候選（`weinstein_stage2_pilot_v1`）判定 `FAIL`，不會直接拿去 holdout 測試。可能的後續方向（都還沒做，等使用者指示）：(a) 換一個沒有後見之明偏誤的宇宙建構方式（例如用 `universe.py` 全市場、或用某個歷史時點的市值排名而非「現在知名」來選股）重跑同一顆引擎；(b) 把隨機控制組升級成真正的動態週頻重抽版本；(c) 嘗試不同的訊號參數當一個全新候選（要走一輪全新的 `LEADS.md` 記錄，不能直接改這條）。詳細技術記錄見 `REPORT.md` 對應條目。

---

## 2026-08-22 — 修補 holdout 物理隔離的真正漏洞：fetch 層預設無截斷

Cowork 稽核抓到一個真的架構問題，跟同一天稍早那次「查到舊快照」的誤會不同——這次是真的漏洞：`holdout.py` 的一次性解鎖閘門設計沒問題，但 `finmind_client.fetch()` 這個所有資料集呼叫的共用入口，預設回傳完整歷史（含 holdout 期間），`cap_to_dev()` 只是選配、要呼叫者自己記得用。等於「資料載入預設就截斷在 holdout 邊界前」這條鐵律在實作上沒有真的落地，只是看起來落地了。

**修法核心：把截斷從「呼叫者自己記得做」改成「架構上不可能忘記」。** `fetch()` 改名 `_fetch()`（internal），新增 `load_dev()` 當唯一正式入口（自動夾在 `VAL_END`），`load_full_history()` 是唯一合法的無截斷路徑（明確標註只能餵給 `unlock_holdout_once()`）。另外在資料載入點跟帳本層各加一道獨立的稽核防線（`assert_no_holdout_leakage()`／`audit_ledgers.py` 新恆等式）。掃過全部既有呼叫點：`adjust.py`／`pit.py` 的價量/財報時間序列改走 `load_dev()`；`universe.py` 的會員名單資料**刻意**維持 `_fetch()` 不截斷（有明確理由，寫在該檔案 docstring 裡，也在下面 REPORT.md 條目驗證過誤改的後果）。

完整修改內容、驗證過程、每一項測試結果都記在 [`REPORT.md`](./REPORT.md) 2026-08-22T13:00 那條，不在這裡重複。FILE MANIFEST（上方）的用途說明已同步更新。

---

## 2026-08-22 — 里程碑 2 開工（驗證框架，第一批模組）+ 優先序調整為背景

**做了什麼：** 開始建驗證框架，四個模組都寫完並實測驗證過：

- **`research/validation/holdout.py`**——train/val/holdout 物理隔離。切分點：TRAIN ≤ 2020-12-31、VAL 2021-01-01～2024-12-31、HOLDOUT 是 2024-12-31 之後到「今天」（沒有固定終點，隨時間往前滾動，確保永遠是「真正還沒發生過的未來」）。`cap_to_dev()` 是一般研究程式碼該呼叫的函式，回傳的資料本來就不含 holdout 那段，不是「回傳了但不准看」。`unlock_holdout_once()` 是唯一能拿到 holdout 資料的入口，用鎖檔（`research/HOLDOUT_LOCK.json`，**進 git**，不是暫存檔，換機器/換 session 都還在）保證整個專案史上只能成功解鎖一次，每次呼叫（不管成功或被擋）都會寫進 `research/HOLDOUT_LOG.md`（也進 git）。用暫時重導向路徑測過：空白 reason 會被擋、第一次解鎖成功且拿到正確的 holdout 列、第二次解鎖正確被擋並記錄「已經被誰在什麼時候用什麼理由消耗掉了」。測試過程沒有動到真正的鎖檔（測完確認 `research/HOLDOUT_LOCK.json` 仍不存在）。

- **`research/validation/costs.py`**——台股成本/摩擦模型。`round_trip_cost_pct()`：手續費 0.1425%×2（買賣各一次）+ 證交稅（一般 0.3%／當沖減半 0.15%，只收賣方）+ 滑價（預設 5bp／腳，這個數字還沒校準過真實成交，先當佔位假設）。`limit_status()`：偵測「當天 開=高=低=收 都貼在漲跌停附近」這種真的鎖死無法成交的訊號（TW 漲跌停就是前收±10%）——用真實資料驗證過：3231（絕創）2025-04-07 那天實際跌停鎖死（open=high=low=close=90.9，前收101.0，跌幅剛好−10.00%），函式正確判斷 `limit_down=True`。

- **`research/validation/control_group.py`**——隨機控制組。`run_control_group()` 吃一個策略無關的 `evaluate_fn`（股票代號清單進、一個數字出），跑 N 次隨機抽樣當對照組，回傳候選在隨機分布裡的百分位。用合成資料驗證：真的排名前段的候選會落在第100百分位（完勝所有隨機組），普通/沒特別挑過的候選落在中段——區辨力符合預期。

- **`research/validation/criteria.py`**——事前綁定標準。`lock_criteria()` 把標準寫成檔案（進 `research/criteria/`，**進 git**）並回傳 SHA256 雜湊；**同名不能覆寫**（要新嘗試就要換名字，不能改舊的）。`verify_criteria()` 在真正跑 holdout 評估前重新算一次雜湊比對，改過的檔案會被抓到。驗證過：正常鎖定/驗證流程沒問題、竄改後驗證會正確報錯擋下來、`evaluate()` 對每一項標準（min_trades/beats_random_control/min_sharpe/max_drawdown/beats_buy_and_hold）分開回報通過與否，不會只丟一個「過/不過」蓋掉細節。

**優先序調整（使用者 2026-08-22 指示）：** App 前端改善轉為前景任務，里程碑 2 剩下的部分（把這四個模組串起來、接上一個能實際跑的回測骨架）先放背景，等前景任務空檔再推進。**目前狀態：驗證框架的地基元件都做好且測試通過，但還沒有任何策略碰過它們——鐵律沒被打破。**

**下一步（背景，有空再做，依使用者最新指示排序）：**
1. 台股還原股價交叉驗證：主線（`adjust.py` 自組還原價）不變，加裝 `yfinance` 抓 2330.TW 等的 Adjusted Close 當第二資料源，挑 5–10 檔含多次除權息的股票比對誤差，結果寫進 DATA.md；誤差在合理範圍才算通過。美股統一改用 yfinance 的 adjusted，解決台美目前分別用 FinMind 兩套邏輯不一致的問題。兩個資料源都免費，不需要付費方案。
2. 財報公布日缺口暫不處理，先沿用現有「期末日 +45 天」保守假設（`pit.py` 已實作）。
3. 把 holdout/costs/control_group/criteria 四個模組串成一個可以真正跑一次「假想策略」的骨架，驗證整條管線串起來沒問題，再進里程碑 3（紙上前測基礎設施）。

---

## 2026-08-22 — 研究程式碼位置決定 + 里程碑 1 三顆地雷修復

**決定：** 研究程式碼放在 `alpha-app` repo 的 `/research/` 底下，`.py`/`.md` 都進 git，`research/data/`（parquet 快取）進 `.gitignore` 不進 git。不另開 repo。

**做了什麼（針對里程碑 1 發現的三顆地雷逐一處理，都寫成程式碼並實測驗證過，不是只寫文件）：**

1. **`research/finmind_client.py`**——共用的 FinMind 抓取層，所有資料集呼叫都經過這裡，自動快取成 parquet（存在 `research/data/raw/`，不進 git）。4xx 錯誤（資料集打錯、要付費）直接快速失敗不重試，5xx/逾時才重試 3 次。

2. **`research/adjust.py`**——台股還原股價。用 TWSE 官方除權息參考價公式，把每次除權息事件換算成乘法調整係數，由近到遠往回套用。用 2330 全部 42 筆歷史除權息事件驗證：係數都落在合理區間（2005 年 50% 股票股利那筆係數 0.644，近年季配息都在 0.99 附近）；最新一筆 `adj_close==close`（今天不自我調整）；2025-06-12 除息日，原始報酬 −1.88% vs 調整後報酬 −1.46%，差 0.42pp，跟股利 4.5/1065=0.42% 的機械性影響幾乎完全吻合。**已知缺口**：減資（`TaiwanStockCapitalReductionReferencePrice`）還沒接進去。

3. **`research/universe.py`**——存活者偏差。TW 回測宇宙限定 2003-01-01 之後，納入 `TaiwanStockDelisting` 的下市股。實測組出 2,974 現存 + 222 下市（2003 後）= 3,196 檔，代號無重複。**殘餘偏差已記錄在 DATA.md**：2003 年前完全不涵蓋；222 檔下市股只驗證「名單存在」沒逐一驗證歷史價格覆蓋率；用「該股票某天有沒有價格資料列」間接判斷可交易性，不是真正的上市/停牌狀態欄位。

4. **`research/pit.py`**——財報 point-in-time。真實公告日拿到之前，一律採保守假設：季報 `pit_date` = 期末日 +45 天（`pit_source='assumed'`）；月營收優先用真實 `create_time`（近期資料有），沒有才退回「次月 10 日」規則假設。實測 2330：近期月營收（2026-03 起）全部拿到真實 `create_time`，更早的正確退回規則假設。提供 `any_assumed(df)` 檢查一份資料是否沾到假設值——**任何用到假設 PIT 的回測結果都要標記實驗性、不可採信**，純價格策略（Weinstein 第二階段、動能）不受此限制，因為它們不會呼叫這個模組。

完整驗證方式跟數字都寫進 [`DATA.md`](./DATA.md) 對應章節。

**下一步：**
里程碑 2——建驗證框架（train/val/holdout 物理隔離、隨機控制組、成本/稅/摩擦模型、事前綁定通過標準）。**框架完成前不會跑任何策略當真**，這是鐵律。

---

## 2026-08-22 — 里程碑 1：資料誠實度盤點（完成初版）

**做了什麼：**
用 curl 直接打 FinMind API 實測（不看文件、不用猜的），驗證了還原股價、存活者偏差、財報 point-in-time 這三項。完整結果寫在 [`DATA.md`](./DATA.md)。

**結論摘要（三個紅燈）：**
1. 台股還原股價（除權息調整）免費方案沒有，`TaiwanStockPrice` 是原始未還原價格；美股 `USStockPrice` 反而免費就有還原價格（`Adj_Close`）。這個不對稱容易在寫共用程式碼時被忽略。
2. 下市股名單免費且完整（723 檔，1995–2026），但歷史價格只有約 2003 年後下市的才查得到，更早的幾乎是空的——回測範圍往前推太多年會撞上存活者偏差。
3. **最危險的一項**：`TaiwanStockFinancialStatements`（季報）完全沒有公告日期欄位，只有財報所屬期間的期末日；如果直接拿期末日當「已知日」去跑訊號，會提早 1.5 個月看到財報，是嚴重未來函數。月營收（`TaiwanStockMonthRevenue`）好一些，近期資料有真實公告時間戳，但更早的也沒有。

**尚未完成（誠實列出）：**
- 除權息還原股價的自組邏輯還沒寫。
- 723 檔下市股只抽測 3 檔，覆蓋率沒有系統性驗證。
- 財報公告日缺口的替代資料源還沒研究（例如 MOPS 直接爬蟲是否可行）。
- 美股存活者偏差完全沒測。
- 期貨/選擇權的還原、歷史深度、存活者偏差沒測。
- 資料落地成 parquet 快取（避免每次重抓、避免撞 FinMind 流量上限）——這是里程碑 2/3 的工作範圍，這裡只是先點出來，還沒動手。

**下一步：**
里程碑 2——建驗證框架（train/val/holdout 物理隔離、隨機控制組、成本/摩擦模型、事前綁定通過標準）。**在驗證框架完成前，不會開始挖任何策略**，這是鐵律。

---

## 需要使用者決定（已解決的存檔）

- ~~這個 Python 研究/回測管線要放在哪裡？~~ **2026-08-22 已決定**：放在 `alpha-app` repo 的 `/research/` 底下，`.py`/`.md` 進 git，`research/data/`（parquet 快取）進 `.gitignore`。理由：現有 PAT 就能推、Cowork 也讀得到、GitHub Pages 只服務網站不受 `/research` 影響。
