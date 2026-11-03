# 先.一三五-1kc　news_events.yml Commit 步驟失敗查因＋提案

2026-11-04 DevQueue 20261104-063101（維運帽；唯讀查因、零外部資料請求，只用 `gh api` 讀 GitHub Actions 中繼資料與本機 git 歷史）。

## 一、結論：三班都是「跟本機新聞補班同時寫同一批檔」的 rebase 衝突，不是單純撞車

| 雲端失敗班（run id） | job 開始 | Commit 步驟開始 | 期間落到 main 的本機補班 commit | 該 commit 碰到的新聞事件檔 |
|---|---|---|---|---|
| 10/21（39553373413） | 06:06:10Z | 06:13:27Z | `3cf8b9247dc` 06:09:57Z「新聞與事件：本機補班更新（雲端排程 120 分鐘未觸發）」 | 1,738 個 |
| 10/25（40193890130） | 12:36:58Z | 12:37:43Z | `244893b9f4c` 12:36:40Z（commit 時間；push 落地應在 checkout 之後）「本機補班更新（90 分鐘未觸發）」 | 1,766 個 |
| 10/30（41060618571） | 13:07:26Z | 13:14:41Z | `f81b2970d3c` 13:12:59Z「本機補班更新（90 分鐘未觸發）」 | 1,823 個 |


查法：
- `gh api repos/.../actions/runs/{id}/jobs`：三班都是 `fetch` job 的 **Commit** 步驟失敗（其他步驟成功）。
- `gh run view --log-failed` 回 403（PAT 沒有 admin 權限讀 log），所以**沒有看到 git 錯誤原文**；annotations 只有「Process completed with exit code 1」。
- `git log origin/main --since/--until`（失敗班前後約 10 分鐘）：三個時間窗都**恰好有一筆**本機補班 commit，碰到的檔跟雲端 `git add` 清單（`data/news.json`、`data/events.json`、`data/events_by_code/` …）重疊 1,700 多個；其他 commit（連通性心跳、DevQueue log、STATUS 心跳）都不碰這些檔。
- 時間形狀一致：雲端排程延遲 90～120 分鐘 → 本機補班判定「雲端沒更新」開跑 → 雲端那班剛好也開始 → 本機先 commit+push → 雲端 `git pull --rebase` 時兩邊都改了同一批 JSON → 衝突 → exit 1。

**證據等級**：時間窗與檔案重疊是直接證據；「錯誤訊息是 CONFLICT」是推論（log 讀不到）。對照組：`local_schedule_watchdog.yml` 同樣「pull --rebase 一次、無重試」寫法 70 班全過——它寫的檔沒有其他寫入者，所以不衝突，符合本推論。

**為什麼補重試救不了**：重試只解決「push 時別人剛好先推（非快轉）」；這裡是內容衝突，`pull --rebase` 每次重試都會撞同一個衝突。

**為什麼本機既有防線沒擋到**：`scripts/news_local_fallback.py` 在 commit 前會再查一次雲端 `news.json` 年齡（`age2 < STALE_MIN` 就作廢本機這輪），但雲端那班當時**正在跑、還沒 commit**，所以查不到。

**影響**：資料沒有遺失（main 上已有本機那份幾分鐘內抓的新聞），只是 Actions 出現紅叉、該班的 schema 守門報告沒進 repo。69 班壞 3 班（約 4%），都發生在雲端排程嚴重延遲、觸發本機補班的時候。

## 二、提案（送 `research/AWAITING_REVIEW.md`；適用 24 小時預設放行）

### 甲（建議）：雲端 rebase 衝突時放棄本班、以 main 上的本機版為準，exit 0＋警告
- `news_events.yml` Commit 步驟改成：`git pull --rebase --autostash` 失敗 → `git rebase --abort` → 印 `::warning::本班與本機補班撞同一批檔，放棄本班、main 上已有本機補班版本（先.一三五-1kc）` → exit 0。
- 同時照 1ka 補 push 重試（非衝突的單純撞車，最多 3 次、每次先 pull --rebase）。
- 理由：只改一個檔、零新依賴、守門員失敗只降級成警告（十二節）；兩邊資料都是同一套腳本幾分鐘內抓的，差異只在幾分鐘，下一班 30 分鐘後會蓋上最新版。
- 風險：被放棄的那班若比本機版晚抓 1～5 分鐘，那幾分鐘的新增新聞要等下一班才出現；需要分辨「衝突」與「其他 pull 失敗」（網路錯）——做法：只有 `git status` 顯示 rebase 進行中（`.git/rebase-merge` 存在）才判衝突，其他失敗照舊 exit 1，不吞錯。

### 乙：本機補班開跑前／commit 前查雲端是否正有一班在跑，有就跳過
- `news_local_fallback.py` 呼叫 `gh run list --workflow=news_events.yml --status in_progress`（及 `queued`），有就不跑。
- 風險：依賴本機 `gh` 認證（PAT 過期時要 fail open 照跑，衝突就回來了）；多一次 GitHub API 呼叫；改的是本機常駐補班邏輯。

### 丙：甲＋乙並用
- 雙層，但改兩處、驗收兩處；以目前 4% 的發生率，甲單獨已足以消除紅叉。

## 三、定案後怎麼做（心跳：PENDING_QUEUE `先.一三五-1kc-a` 改 `- [x]`）
- 甲 → 改 `news_events.yml` Commit 步驟＋寫本機自測（用暫存 repo 製造「同檔衝突」與「單純非快轉」兩種情境，確認前者 exit 0＋警告、後者重試成功、網路錯仍 exit 1）。
- 乙 → 改 `news_local_fallback.py`＋自測（gh 失敗時 fail open）。
- 丙 → 兩者都做。
