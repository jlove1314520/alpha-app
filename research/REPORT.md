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
