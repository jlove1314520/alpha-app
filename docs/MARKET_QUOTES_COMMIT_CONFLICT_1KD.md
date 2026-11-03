# 先.一三五-1kd　market.yml／quotes.yml Commit 失敗查因＋其餘 workflow 失敗班清點＋提案

2026-11-04 DevQueue 20261104-070101（維運帽；唯讀查因、零外部資料請求）。只用 `gh api` 讀 GitHub Actions 中繼資料（本輪共 28 次，未登入額度 60／小時——本機 `gh` 的 token 已失效，見第四節）與本機 `git log origin/main`。

## 一、清點（2026-10-21 起，`status=failure`）

| workflow | 失敗班數 | 失敗步驟 | 分類 |
|---|---|---|---|
| market.yml | 4（另 1kc 數到的總數 37） | 全是「Commit 市場資料 JSON」 | 1 班 exit 128（已修）、3 班 rebase 衝突（推論，見下） |
| quotes.yml | 1 | 「Commit 報價 JSON」 | rebase 衝突（與本機盤中報價備援同檔） |
| smoke_cloud.yml | 11 | 「冒煙未通過就讓這個 job 顯示紅燈」 | 不是 commit 問題：冒煙第 146 項在雲端不穩（13 班壞 11 班），見第三節 |
| tw_data_landed_check.yml | 0 | — | — |
| us_financials.yml | 0 | — | — |

（audit.yml 3 班已由 1ka 修、news_events.yml 3 班由 1kc 查，不重複。）

## 二、market.yml／quotes.yml 的 Commit 失敗

| 失敗班（run id） | Commit 步驟 | annotation | 同時段 main 上的 commit（UTC） | 重疊的檔 |
|---|---|---|---|---|
| market 10/21（39519487399） | 00:14:11Z | 只有 exit 1 | `0462a197b6a` 00:12:44Z 互動視窗「先.一二五-1 缺 Q1 基準…」 | `data/by_code/*.json`（market 的 `git add` 清單有 `data/by_code/`） |
| market 10/27（40529812272） | 15:24:58Z | 只有 exit 1 | `040b1b5e4e3` 15:23:02Z「收件匣 025…」、`72e4a88fffe` 15:23:37Z | `PENDING_QUEUE.md`、`data/trials_index.json` |
| market 10/28（40610674543） | 00:50:09Z | 只有 exit 1 | `377adf1ea14` 00:38:42Z、`45dd92e466e` 00:45:24Z（DevQueue） | `PENDING_QUEUE.md`、`data/STATUS.json`、`research/PROGRESS_HEARTBEAT.jsonl` |
| market 10/28（40707442076） | 14:40:37Z | **exit 128** | — | 停資停券資料夾不存在讓 `git add -A` fatal 128；**已由 先.一四〇-1z（`592c508d671`）修好**，不再處理 |
| quotes 10/30（40996322880） | 03:16:02Z（2 秒就失敗） | 只有 exit 1、**沒有**「重試 5 次仍失敗」warning | `5beb9af1ddb` 03:15:23Z「盤中報價：本機備援補抓（雲端 30 分鐘未更新，先.八十二-4）」 | `data/quotes_tw.json` |

**判斷依據與證據等級**
- 失敗步驟（`gh api .../runs/{id}/jobs`）是直接證據。
- market 那 3 班都**早於** rebase 衝突 annotation（先.一三八-8，10/28 09:17Z）與重試耗盡 annotation（先.一四〇-11，10/28 16:36Z）上線，所以 annotation 分不出是哪一種；判「衝突」靠的是：每個失敗窗都恰好有人改了 market 也會寫的共用追蹤檔（直接證據），git 錯誤原文看不到（run log 要 admin 權限）。**「CONFLICT」為推論。**
- quotes 那班在重試耗盡 annotation 上線後，卻沒有那條 warning、而且 2 秒就結束——只剩「rebase 衝突、abort、exit 1」這條路徑（quotes 這條路徑當時沒寫 annotation）。
- 先.一四〇-11 上線（10/28 16:36Z）後到今天，market.yml 沒有再失敗。

**為什麼補重試救不了**：兩支的 push 重試迴圈（5 次）本來就有；衝突時 `git rebase origin/main` 每次都撞同一處內容衝突，迴圈直接 exit 1。

**影響**
- market：衝突就**整班資料全丟**（下一班最多約 8 小時後），不像新聞（1kc）只是幾分鐘差異。14 天 37 班壞 3 班（約 8%），都是剛好有互動視窗／DevQueue 在同幾分鐘 push 共用追蹤檔。
- quotes：資料沒遺失（main 上已有本機備援那份同分鐘抓的報價），只是紅叉；跟 1kc 同形狀（雲端延遲 → 本機補班開跑 → 雲端那班也在跑）。

## 三、smoke_cloud 第 146 項（另立補件，非本提案範圍）

- 13 班（10/21～11/03）壞 11 班，失敗內容都是第 146 項「0 秒動畫下 animationend 沒觸發，閃色 class 沒被移除」；10/23～10/25 另有 65／131／132／142 幾項是當時資料問題，之後自行恢復。
- App 本身在「減少動態效果」下已經**不加閃色**（`app.js` `flashPriceEls()` 的 `!uiReducedMotion()`，先.九十六-R4），所以這個子檢查測的是「雲端 headless Chromium 對 0 秒動畫的 animationend 時序」，不是 App 的程式路徑；**使用者不會遇到閃色卡住**。
- 要改的是測試（開發帽，且不能放寬，要換成測 App 真正的路徑：減少動態時報價變動後元素沒有 flash class），已補件 先.一三五-1kd-b。

## 四、提案（送 `research/AWAITING_REVIEW.md`；適用 24 小時預設放行）

### market.yml

**甲（建議）：衝突時逐檔取捨後繼續 rebase，不丟整班**
- `git rebase origin/main` 失敗且 rebase 進行中（`.git/rebase-merge` 或 `.git/rebase-apply` 存在）時，對每個衝突檔：
  - 共用追蹤檔（`PENDING_QUEUE.md`、`data/STATUS.json`、`research/PROGRESS_HEARTBEAT.jsonl`、`data/trials_index.json`）→ 取 **main 上的版本**（rebase 中是 `git checkout --ours`），放棄雲端這班對它的改動（多半只是倒數行、心跳、索引重建，下一班會重寫）；
  - 其他資料檔 → 取**雲端本班版本**（`git checkout --theirs`）；
  - `git add` 後 `GIT_EDITOR=true git rebase --continue`，印 `::warning::` 列出每個檔取了哪一邊；任何一步失敗才 abort＋exit 1（照舊）。
- 理由：保住整班市場資料；共用追蹤檔讓人類／DevQueue 的編輯優先，避免雲端倒數行蓋掉交辦文字。
- 風險：被放棄的 PROGRESS_HEARTBEAT 一行、STATUS 心跳要等下一班；若衝突檔是資料檔而 main 那邊是互動視窗「修資料的程式＋重產資料」，取雲端版會把舊程式的產出蓋回去——但這跟「沒衝突時雲端照樣用舊程式產出覆蓋」是同一件事，下一班就會用新程式重產，不是新增風險。需在暫存 repo 自測三種情境（共用檔衝突→取 main、資料檔衝突→取雲端、網路錯→exit 1）。

**乙：衝突時放棄本班，exit 0＋警告**（比照 1kc-a 甲）——最簡單，但整班市場資料丟掉、要等下一班，市場資料比新聞貴。

**丙：不改 workflow，改流程**——互動視窗／DevQueue 避開 market.yml 三個班次的前後 10 分鐘 push 共用追蹤檔。靠人記得，不建議。

### quotes.yml

**甲（建議）：比照 1kc-a 的定案做法**——衝突時 abort、印 `::warning::`、exit 0（main 上已有本機備援同分鐘抓的報價，下一班 10～30 分鐘後蓋）；其他失敗照舊 exit 1。1kc-a 定案若改選乙／丙，quotes 一併照同一選項做本機備援端（`scripts/` 盤中報價備援）。
**乙**：不改，維持紅叉（每兩週約 1 次，資料沒丟）。

### 本輪已直接做的純 bug 修復（不用等裁示）
- quotes.yml rebase 衝突路徑補 `::warning::quotes.yml rebase衝突檔：…`（market.yml 在 先.一三八-8 已有、quotes 漏了，所以這次 10/30 那班看不出原因）。

### 附帶發現
- 本機 `gh auth status`：「The token in default is invalid」——`gh` 目前是未登入狀態（每小時 60 次），這就是 11/03 22:50Z 上一輪撞 403 的原因。git push 用的是 Windows 認證存放區的 PAT，不受影響。讀公開 repo 的 Actions 中繼資料用未登入額度就夠；要恢復 `gh` 登入需總司令提供新 PAT（不走瀏覽器登入，見 `C:\alpha\CLAUDE.md`）。
