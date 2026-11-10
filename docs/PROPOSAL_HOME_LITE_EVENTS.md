# 提案：首頁「今日事件＋研究狀態點」改讀精簡檔（先.一五五-3f）

DevQueue 20261110-220101，2026-11-10 22:1x。非投資建議。

## 一、量測（本機 8792、Playwright 393×852、無快取無 SW，`scripts/measure_first_load.mjs`）

**合計 336.8KB（58 個請求，未知 0）**，門檻 350KB（不調）。前 10 大（同網域＝本機檔 gzip 模擬 Pages 傳輸量）：

| # | 請求 | gzip KB | 首屏必要？ | 與 11/06 17:15（1lv 修完 334.5KB）比 |
|---|---|---|---|---|
| 1 | app.js | 139.6 | 是（程式本體；拆分見 1kh-o 已做） | +0.5 |
| 2 | index.html | 40.0 | 是 | +0.3 |
| 3 | Sora 字型 woff2（Google Fonts） | 25.8 | 是（標題字型） | 0 |
| 4 | data/listed_universe.json | 24.3 | 部分（只用名冊／停止交易判斷） | 0 |
| 5 | app.css | 17.9 | 是 | +0.1 |
| 6 | **data/research_radar.json** | **14.3** | **否：首頁只用 `dots`（2.7KB）**，`lists`（7.3KB）、`deep`、`industry_heat` 是研究室用的 | **+0.6** |
| 7 | **data/ir_events.json** | **12.1** | **否：只用近 2 天公告＋未來 7 天會議**（507 筆中約 140 筆在 11/01 後，歷史回到 09/11） | **+0.5** |
| 8 | **data/ex_dividend_events.json** | **10.0** | **否：只用未來 7 天除權息**（288 檔中 10 檔落在未來 14 天） | **+0.2** |
| 9 | data/quotes_tw.json | 6.7 | 是 | −0.1 |
| 10 | sw.js | 5.2 | 是 | — |

**結論：不是 bug，是正常累積**。11/06 以來首頁只長 2.3KB，主要來自 research_radar／ir_events／ex_dividend／events_by_code/_index 四個逐日長大的資料檔（合計 +1.7KB）；app.js／index.html 長 0.8KB。
1lv 修過的 intraday 精簡檔（`data/intraday_tw/*.spark.json`）這次 8 秒量測窗內只請求了 index.json（index 已指向 `2026-11-10.spark.json`，6.7KB 原始；未在窗內請求，可能是本機 live server 回 health 後走即時來源），就算請求也只約 2KB gzip，沒有又長大。
照目前每週約 +3～4KB 的速度，約 3～4 週會頂到 350KB。

## 二、選項

- **甲（建議）**：`scripts/build_research.py`（或新增一支零外部請求的小腳本）每班另寫 `data/home_lite.json`，只含
  ①research_radar 的 `dots`、②未來 14 天的除權息事件、③近 14 天＋標題含未來會議日的法說公告（欄位只留 code／name／date／title）。
  首頁 `_todayTwEvents()` 與研究狀態點改讀這一檔；個股頁、研究室、除權息頁照舊讀原檔（點到才載入）。
  - 本機試算：精簡檔 gzip 約 **7.3KB**，取代 36.4KB → 首頁約 **308KB**（省約 29KB，留 42KB 餘裕）。
  - 風險：多一個產出檔要進 `market.yml` commit 清單（十節）與停擺自檢；精簡檔缺/舊時要退回讀原檔（回退鏈，七節），冒煙加一項。
- **乙**：只把 research_radar 的 `dots` 拆出成 `data/research_dots.json`（省約 11.6KB → 約 325KB）。改動最小，但除權息／法說兩檔仍逐日長大，約 2 個月後又要處理。
- **丙**：不改，只把冒煙預警線設在 340KB（不動 350KB 門檻），到預警再做。

## 三、不做的影響

不做的話照目前成長速度約 3～4 週後冒煙 #78 會 FAIL，屆時所有 commit 被冒煙擋住（四節）。

## 四、心跳

AWAITING 一列；24 小時內無 Cowork 裁示，照零之二預設放行甲（純前端讀取路徑＋零外部請求產出檔，無真錢／刪除／付費／門檻變更）。
