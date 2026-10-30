# 記憶體報告（先.一三八-B2，Cowork 收件匣 027）

2026-10-31 DevQueue 20261031-033102 產出。**只是報告與提案，本輪沒有改任何排程、沒有關任何程式。**

## 資料來源

- 取樣：`research/data/mem_profile_2026-10-28.jsonl`、`mem_profile_2026-10-29.jsonl`（先.一三八-B1，`scripts/mem_profile_sample.py`），
  兩個平日 18:31～21:22 各 18 筆、間隔 9～11 分鐘，每筆依程式名合併工作集取前 15 名＋可用／總實體記憶體。
  只記程式名與記憶體，不記命令列與視窗標題。本機檔，不進 repo。
- 排程：本機 `Get-ScheduledTask`（`Alpha*`、未停用）的觸發時間，2026-10-31 03:4x 讀取。
- 限制：取樣只有晚上 18:30～21:30，白天盤中（09:00～13:30）沒量；「工作集」不是承諾記憶體，加總不等於系統用量。

## 結論

| 項目 | 10/28（週三） | 10/29（週四） |
|---|---|---|
| 實體記憶體 | 32,189 MB | 32,189 MB |
| 可用記憶體最低 | **2,680 MB**（18:31） | 5,272 MB（20:42） |
| 可用記憶體最高 | 4,066 MB | 6,504 MB |

1. **兩天差約 2.5～3 GB 的主因是非 Alpha 程式**：10/28 那晚 ChatGPT（約 1,150 MB）、Steam（steamwebhelper 約 800 MB）、
   Riot Client（約 560 MB）、富途牛牛 FTNN（約 460 MB）、explorer 多開都在，10/29 這幾個都沒出現。照收件匣 027，**這些只告知、不關、不改**。
2. **常駐大戶（兩天 36/36 筆都在）**：chrome 約 5,050 MB、claude 約 3,360 MB、svchost 約 2,100 MB、msedgewebview2 約 1,650 MB、
   vmmem（WSL／虛擬機）1,428 MB、Dropbox 約 770 MB、Windows Terminal 約 520 MB、MsMpEng（防毒）約 520 MB。
   其中 Alpha 自己的是 claude（DevQueue／互動視窗）與 pythonw（常駐 live server／報價，約 800～990 MB）。
3. **Alpha 排程造成的尖峰（可用記憶體當筆明顯下降者）**：
   - `chrome-headless-shell`（冒煙測試的 Playwright 瀏覽器，750～910 MB）出現 4 次：10/28 19:12、20:12，10/29 19:12、20:42；
     這 4 筆就是當天可用記憶體最低或次低的幾筆（10/29 20:42 掉到 5,272 MB、19:12 掉到 5,423 MB）。
     來源是 DevQueue 輪次（每 30 分鐘，:01／:31 開工）跑 `node scripts/smoke_test.mjs`，以及 22:30 的 `AlphaPhoneRegression`（取樣時段外）。
   - `python` 1,363 MB（10/28 18:31，18:42 仍 537 MB）：同一分鐘觸發的是 `AlphaDisposalFlags`、`AlphaPaper9`（取樣只記程式名，無法確認是哪一支，推測是這兩支之一）。
   - `powershell` 400～680 MB 幾乎每筆都在：排程 wrapper（`run-*.ps1`），單支不大。
4. **晚上 Alpha 排程重疊時段**（本機排程，`schtasks` 觸發時間）：
   - **18:30**：`AlphaDisposalFlags`、`AlphaPaper9`（同一分鐘）
   - **19:30**：`AlphaMarginCkCheck`、`AlphaMarketCatchupLate`（同一分鐘）
   - **20:00～20:30**：`AlphaWeeklyReport`（只有週日）、`AlphaTelegram2015`（20:15）、`AlphaTwDataCheck`（20:30）
   - 一直在跑：`AlphaDevQueue`（30 分）、`AlphaConnectivity`（5 分）、`AlphaFinMindWarmup`（15 分）、`AlphaIbkrQuotes`（5 分）、
     `AlphaIbkrGateway`（15 分）、`AlphaShioajiQuotes`（2 分）、`AlphaLiveServer`（1 分）、`AlphaNewsFallback`（30 分）、`AlphaPaperSupplyV2`（1 小時）。
5. 兩晚最壞情況可用仍有 2.68 GB（約 8%），**取樣期間沒有出現記憶體不足中止**；10/22 那次「本機記憶體不足被系統中止」（CLAUDE.md V1 減資還原段）
   是手動長時間抓取（研究腳本），不是本次取樣的兩晚。

## 可延後／錯開的 Alpha 排程（只是提案，未改）

- **甲（建議）：維持現狀，不改排程。** 理由：晚上最低可用 2.68 GB 發生在非 Alpha 程式全開時，Alpha 端尖峰主要是冒煙測試的
  headless 瀏覽器（單次不到 1 GB、幾分鐘就關）；CLAUDE.md 四節已有「冒煙被記憶體不足中止 → 等 10 分鐘自動重跑一次」的長期許可兜底。
  改排程要動總司令的 Windows 排程設定（可能要再輸入開機密碼），成本大於目前看得到的效益。
- 乙：把同一分鐘的兩組錯開 10 分鐘——`AlphaPaper9` 18:30→18:40、`AlphaMarketCatchupLate` 19:30→19:40。
  效益：18:31 那筆 1.36 GB python 尖峰可望分散；風險：`AlphaMarketCatchupLate` 是補班，晚 10 分鐘會讓「19:30 前三層至少一層補到」的落地檢查
  （`AlphaTwDataCheck` 20:30）緩衝少 10 分鐘，仍有 50 分鐘。需總司令本人改排程觸發。
- 丙：白天盤中（09:00～13:30，`AlphaAutoRun0905`／`0940`／`AlphaQuotesFallback`／`AlphaShioajiQuotes` 同時在跑）另外量 2 個平日再決定。
  需要改 `mem_profile_sample.py` 的時段（可還原），不動排程。

## 非 Alpha 程式（只告知，不關、不改）

ChatGPT、Steam（steamwebhelper）、Riot Client、富途牛牛（FTNN）、PredatorSense、Dropbox、Chrome 分頁（約 5 GB、32 個程序）。
晚上要跑長時間抓取或冒煙前，關掉 Chrome 多餘分頁與遊戲平台，是總司令可以自己決定的事。
