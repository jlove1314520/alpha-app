# 提案：app.js 再拆分，壓住首頁首次載入（先.一三五-1kh-o）

- 寫於：2026-11-04 16:3x，DevQueue 20261104-160102
- 狀態：**送審中**（`research/AWAITING_REVIEW.md` 一列）；**不改冒煙 #78 的 350KB 門檻**，本輪未改任何程式。

## 1. 量測（本機冒煙伺服器 8792、Playwright Chromium 390×844、首頁載入後等 6 秒、V8 block coverage）

| 項目 | 數字 |
|---|---|
| 首頁首次載入總量（冒煙 #78，16:18 那次） | **330.5KB**（門檻 350KB，餘裕 19.5KB） |
| `app.js` 原始大小 | 414,432 bytes（332,518 字元） |
| `app.js` gzip 後 | 150,780 bytes（約 147KB，占首次載入約 45%） |
| 首頁啟動實際執行到的 `app.js` | **148,041／332,518 字元＝44.5%**（其餘 55.5% 首頁用不到） |
| 首頁有沒有載入其他 `app-*.js` | **沒有**——`app-lab／market／picks／settings／shared／stock／trade／journal.js` 都已是點到才載入（`loadAppModule()`／`_lazyCall()`） |

首頁沒執行到、最大的頂層函式（字元數）：
`doSearch` 4,967、`loadMyHoldingsEvents` 4,675、`renderMethodBoard` 4,657、`renderStrategyCurves` 2,928、`scSvg` 2,628、`scHistSvg` 2,619、
`renderTrancheTimeline` 2,284、`renderBtProb` 2,134、`submitIbkrOrderUI` 1,942、`renderBtPath` 1,908、`renderAutoPreflight` 1,779、
`wlParseImport` 1,768、`_labDeep` 1,668、`autoTrancheTimeline` 1,661、`scBindTip` 1,596、`scHistModel` 1,591、`loadStrategyCurves` 1,514、
`renderLiveAccount` 1,512、`openMethodSheet` 1,343…

依名稱粗分（只是函式名關鍵字分類，**不精確**，「其他」占大宗）：方法頁約 8.1K 字元、研究室約 5.4K、交易／日誌約 4.0K、設定約 2.8K、
其他約 110K（含策略曲線 `sc*`、回測圖 `renderBt*`、分批時間軸 `*Tranche*`、搜尋 `doSearch`、自選匯入 `wlParseImport` 等）。
注意 coverage 是「首頁 6 秒內」，不含使用者之後點自選股、搜尋的路徑；`go`、`twCloseDateLabel` 這類在別的分頁才跑的也列在未執行裡，不代表能搬走。

## 2. 選項

### 甲（建議）：只搬研究室／方法頁／策略曲線群到延後載入檔
- 搬：`renderMethodBoard`／`openMethodSheet`（方法頁）、`renderStrategyCurves`／`loadStrategyCurves`／`sc*` 系列（策略曲線）、`renderBt*`（回測機率／路徑圖）、`_labDeep` 等研究室專用函式 → 併進既有 `app-lab.js`（或新建 `app-method.js`），呼叫端改 `_lazyCall('lab', ...)`。
- 估計省：這些函式合計約 25～35K 字元原始碼 → gzip 後約 **8～12KB**（以 app.js 整體壓縮比 150.8／414.4≈0.36 推估，**未實測**）。
- 風險：中低。沿用已驗證的 `_lazyCall` 機制（先.一四七-0 搬前向看板就是這樣做）；要逐一確認 `index.html` 的 onclick 呼叫（冒煙 #53 會抓到沒定義的處理器）。
- 驗收：冒煙 #78 實測數字下降、#53 全過、研究室／方法頁點開正常。

### 乙：全面拆（只留首頁執行到的 44.5% 在 app.js）
- 理論上 gzip 可省約 80KB，但要動 180K 字元、上百個函式，跨分頁共用函式（`go`、日期標籤…）很多，改A壞B 風險高，要分好幾輪。不建議一次做。

### 丙：不拆，只在冒煙加 320KB 預警線
- 零風險、零改程式；只是預警，不解決成長。320KB 線**現在就已經超過**（330.5KB），加了會立刻變黃。

## 3. 建議
**甲**，並把丙的預警線改成「距 350KB 不到 15KB 就在冒煙資訊欄提示」（只提示、不 FAIL、不改門檻），之後 app.js 再長時看得到。
24 小時內沒有裁示 → 照甲執行並標 [預設放行]（只動前端程式、git revert 可還原，不在零之二第 2 點排除清單內）。

## 4. 量測重跑方式
本機 `python scripts/ensure_smoke_server.py` 後，用 Playwright `page.coverage.startJSCoverage({resetOnNavigation:false})` 開首頁、等 6 秒、`stopJSCoverage()`，
對 `app.js` 的每個 range 依序標記 count>0 的字元（巢狀 range 後者覆蓋前者）再加總。本輪用的是一次性腳本（放在 repo 外、跑完刪除），實作甲時可一併收進 `scripts/`。
