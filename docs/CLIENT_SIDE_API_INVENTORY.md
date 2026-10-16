# App 端直打外部 API 盤點（先.一〇三-15e）

盤點時間：2026-10-16 12:16～12:23（DevQueue 20261016-120101）。只盤點、不改 App 行為。

對照規則：`BACKLOG.md`「架構紅線（2026-08-28使用者裁示）」第 1 條——
「一律走 GitHub Actions 排程→產出 repo JSON，App 只讀 JSON，禁止 client-side 直接打任何外部 API」；
以及 `CLAUDE.md` 七節「美股禁止用台灣資料商作為價格主來源」。

## 盤點方法（可重跑）

1. `grep -n -o "fm('[A-Za-z]*'" *.js`：App 打 FinMind 只有一個入口 `fm()`（`app-shared.js` 第 63 行，
   網址常數 `FM` 在 `app.js` 第 1109 行），全 repo 共 6 處呼叫。
2. `grep -n -o -E "https://[a-zA-Z0-9.-]+" *.js index.html`：其他外部網域。
3. 每一處都往上看「呼叫它的函式」，判斷 FinMind 是主來源還是讀不到 repo 檔才用的補充。
   （15b 只看到 `fm(` 就判「主來源」，判錯了一條，見下方第 2 列。）

## FinMind 呼叫（6 處）

| # | 位置 | 面板 | dataset | repo 檔優先？ | FinMind 角色 | 合紅線？ |
|---|---|---|---|---|---|---|
| 1 | `app-market.js` 第 359 行 `loadFutInst()` | 市場頁·期貨籌碼 | `TaiwanFuturesInstitutionalInvestors` | 是：`data/futures_institutional.json`（TAIFEX 官方，先.八十一-10） | 補充 | ✅ |
| 2 | `app-picks.js` 第 88 行 `fetchIndustryFlow()` | 市場頁·主流題材 chips | `TaiwanStockPrice`（8 大產業指數） | 是：`loadMainstreamIndustries()` 先讀 `data/industry_flow.json`（`scripts/build_industry_flow.py`） | 補充 | ✅ |
| 3 | `app.js` 第 2189 行 `twPxRepoFirst()` | 個股頁走勢圖（台股）、選股報告（台股） | `TaiwanStockPrice` | 是：`by_code` 小檔的 `price`（repo price_history） | 補充（repo 少於 2 筆才用） | ✅ |
| 4 | `app-stock.js` 第 560 行 `loadRevenueChart()` | 個股頁·營收圖的月底股價 | `TaiwanStockPrice` | 是：`by_code` 的 `monthly_close`（先.八十一-22） | 補充（只補缺的月份） | ✅ |
| 5 | `app-stock.js` 第 679 行 `openStock()` 美股分支 | 個股頁·總覽·走勢圖（美股） | `USStockPrice` | **否**：先打 FinMind，失敗才退回 `quotes_us` 近 20 日收盤 | **主來源** | ❌ 紅線第 1 條＋七節美股原生源 |
| 6 | `app-picks.js` 第 671 行 選股報告 | 選股報告·走勢（美股） | `USStockPrice` | **是**（2026-10-17 先.一〇八-1：美股改 `usPxRepoFirst`，先讀 `data/us_daily/<代號>.json`，讀不到才打 FinMind；分批計畫說明列標本次來源） | 補充（本站日線讀不到時） | ✅ 已改（冒煙 #166） |

結論：台股 4 處都已是「repo 為主、FinMind 補」；**美股 2 處仍以 FinMind（台灣資料商）為主來源**。
第 5 列已有提案條目 先.一〇三-15d；第 6 列與第 5 列是同一個問題（同一個 dataset、同一種退回邏輯缺口），
已併進 15d 的範圍（見 `PENDING_QUEUE.md` 15d 條目補記），不另立。

## 其他外部網域（皆不是資料 API）

| 網域 | 位置 | 用途 | 說明 |
|---|---|---|---|
| `cdn.jsdelivr.net` | `app-stock.js` 第 957 行 | 載入 lightweight-charts 圖表程式庫 | 程式庫不是資料；載不到退回折線（先.一〇五-1） |
| `fonts.googleapis.com`／`fonts.gstatic.com` | `index.html` 第 19～21 行 | 字型 | 不是資料 |
| `mopsov.twse.com.tw` | `app.js` 第 4698 行 `mopsIrUrl()` | 法說會連結，**使用者自己點開**，App 不 fetch | 依 `C:\alpha\CLAUDE.md`「MOPS 法說會」節，刻意不抓 |
| `www.twse.com.tw`、`www.nyse.com` | `app.js` 第 853、855 行 | 註解裡的出處網址 | 不是呼叫 |
| `LIVE.url`／`IBKR_ORDER_SERVER` | `app-settings.js`、`app-stock.js` | 本機自家伺服器（`data/live_endpoints.json`） | 不是外部第三方 API |
