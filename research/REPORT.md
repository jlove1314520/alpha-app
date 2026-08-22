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
