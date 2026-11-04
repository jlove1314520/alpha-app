# 提案：沒連電腦時自選股日內分時的資料來源（先.一四九-2）

2026-11-05 DevQueue 20261105-043102（維運帽）。**本文件只是提案，沒有改任何程式、沒有送任何外部請求。**

## 一、現況（讀本機檔實測）

- 自選股小圖只畫日內分時（先.一四八-4），來源只有本機 live server（手機要連得到家裡電腦）。電腦連不到就是「無日內資料」。
- 本機常駐 `research/shioaji_quotes.py` 已經把當日 1 分K（tick 聚合＋kbars 基底）寫進熱檔
  `research/.live_state_sinopac.json`（不進 repo）。11/04 收盤後實測：**49 個代號**（自選股 6 檔＋指數、類股指數、期貨近月），
  每檔中位數 272 根、最多 314 根；全部緊湊格式 518KB、gzip 122KB。
- 雲端 `data/quotes_tw.json` 每班一個點，`quotes.yml` 盤中每 10 分鐘一班，沒有序列。
- `data/quotes_sinopac.json` 目前只在每天 13:45 推一次（`run-shioaji-quotes-cycle.ps1`），裡面**已經含自選股代號**，
  所以把自選股日內分時推上公開 repo **不會新增曝露**。

## 二、選項

### 甲（建議）：本機每 15 分鐘從熱檔匯出 `data/intraday_tw/YYYY-MM-DD.json` 並推送
- 新腳本 `scripts/export_intraday_tw.py`：只讀熱檔，不碰 Shioaji、**零新增外部請求、不動 shioaji_quotes.py**（免重啟四步驗證）。
- 只匯出自選股（`.live_watchlist.json`）＋ TAIEX、TPEX（約 8 檔），格式 `{"date","generated_at","source":"shioaji-local","bars":{代號:[[HH:MM,開,高,低,收,量],...]}}`；
  收盤時整檔約 85KB（gzip 約 20KB，由 49 檔 518KB 等比估算，未實測）。
- 盤中 09:00～13:45 每 15 分鐘一次，每日約 19 個 commit（目前 repo 一天約 208 個 commit）；git 每日增加估約 1MB 以內。
  熱檔未更新（電腦關機／行程停）就不寫、不推，App 照實寫「本機資料停在 HH:MM」。
- 接在既有本機排程裡跑（不新建排程；掛哪一支放行後確認），新輸出路徑同步加進 `scripts/dev_queue_runner.py::MACHINE_WRITTEN`（十節）。
- App：自選股小圖先打本機 live server，連不到再讀 repo 這份當日檔；標「延遲最多約 15 分鐘（電腦端每 15 分鐘上傳）」。只留當日與前一交易日兩檔，舊檔每天刪（屬機器產出檔的例行輪替）。
- 限制：家裡電腦沒開或 Shioaji 沒連時一樣沒有；GitHub Pages 部署再加約 1～2 分鐘。

### 乙：雲端 quotes 排程把報價點 append 成當日序列
- 不依賴家裡電腦；但點很稀（每 10 分鐘一點、雲端排程常延遲 15～60 分），一天約 27 點，畫出來是折線不是分時。
- 要改雲端 workflow 與 `data/quotes_tw.json` 寫法。

### 丙：維持現狀照實標「無日內資料」

## 三、建議與預設放行

建議**甲**（資料真、零新增外部請求、改動只在新腳本＋App 讀取端）。照零之二，24 小時內無 Cowork 裁示即預設放行甲。
放行後先做匯出腳本＋自測，再改 App 讀取並加冒煙一項；推送頻率若日後要調（例如 10 分鐘）另提案。
