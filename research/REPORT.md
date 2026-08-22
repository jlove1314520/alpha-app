# REPORT.md — append-only 主日誌

「Session 是消耗品，檔案才是本體」：這份檔案是這個專案唯一不會因為換 session、換機器、換 agent 而消失的執行記錄。

**規則：**
- **只往下 append，不覆寫、不刪除舊條目。** 發現舊條目寫錯了，加一條新的訂正，不要回頭改。
- 每條目格式：`## <ISO 8601 時間戳> — <一行摘要>`，內容至少包含「做了什麼」跟「驗證結果」兩項——沒驗證過的事不能寫得像驗證過。
- 這份檔案記的是**顆粒度細的單一動作**（一個函式寫完測完、一個 bug 修好、一次資料驗證）。里程碑等級的敘事跟決策脈絡記在 [`STRATEGY_LOG.md`](./STRATEGY_LOG.md)；現在整體卡在哪、下一步是什麼，看 [`MARATHON_STATE.md`](./MARATHON_STATE.md)——換 session 接手時**先看 MARATHON_STATE.md**，這份是給「我怎麼走到這裡」找細節用的。
- 策略候選的最終判定記在 [`LEADS.md`](./LEADS.md)，不要跟一般開發記錄混在一起。

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
