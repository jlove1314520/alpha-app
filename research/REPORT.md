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
