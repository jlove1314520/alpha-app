# 美股 IBKR 1 分K 可行性查證（先.八十一-29，2026-10-13）

> 只查證、寫結論；**沒有改程式**。個股頁美股 1 分K 維持誠實 501（`research/alpha_live_server.py` `/live/kbars`）。
> 要不要做、怎麼做，是新功能，照「提案先於執行」交總司令審閱。

## 一、要回答的兩個問題

1. `reqHistoricalData()` 跟 `ibkr_quotes.py` 既有的短命連線會不會衝突？
2. IBKR 歷史資料的頻率上限是多少？（已寫進 `C:\alpha\CLAUDE.md` 外部 API 頻率上限清單「IBKR TWS API 歷史資料」小節）

## 二、官方文件（三個來源）

| 來源 | 原文重點 |
|---|---|
| [historical_limitations](https://interactivebrokers.github.io/tws-api/historical_limitations.html) | 同時開著的歷史請求最多 50 個；30 秒以下小K：15 秒內不得重複同一請求、同合約 2 秒內不得 ≥6 次、10 分鐘內不得 >60 次；「barSize＝1 mins 以上的歷史資料限制已解除」，但仍有軟性負載平衡 |
| [introduction](https://interactivebrokers.github.io/tws-api/introduction.html) | Gateway 每秒最多收 50 則用戶端訊息，**所有連線的用戶端合計** |
| [connection](https://interactivebrokers.github.io/tws-api/connection.html) | 同一個 TWS／Gateway 最多 32 個用戶端，用 clientId 區分 |
| [historical_data](https://interactivebrokers.github.io/tws-api/historical_data.html) | 「API 取歷史資料需要 Level 1 即時串流訂閱」；SMART 路由的歷史請求需要該標的所有交易所的訂閱 |

新版文件站 `interactivebrokers.com/docs/tws-api/` 用工具抓會回 403，只能從目錄看到「Pacing Violations for Small Bars (30 secs or less)」同名章節，內容未能讀到全文，以上以 github.io 版為準。

## 三、實測（本機 IB Gateway，paper 帳戶，唯讀）

- 時間：2026-10-13 23:32（台北）＝ 11:32 ET，美股盤中。
- 腳本：一次性探測（不進 repo），`readonly=True`、先確認帳戶全為 `DU` 開頭才發請求、clientId 51（未被其他程式使用）。
- 請求：`AAPL` `Stock('AAPL','SMART','USD')`、`durationStr='1 D'`、`barSizeSetting='1 min'`、`whatToShow='TRADES'`、`useRTH=True`。
- 結果：**108 根，09:30～11:17 ET，最後收盤 346.24**；當下約 11:32 ET → **延遲約 15 分鐘**。
- Gateway 訊息：只有 2104／2106／2107／2158 這類「資料農場連線正常」通知，沒有錯誤碼。
- 同時並行：探測與 `python research/ibkr_quotes.py`（clientId 47）同一秒啟動，兩者都正常完成，`ibkr_quotes.py` exit 0、`data/quotes_ibkr.json` 寫入 9 檔（23:33:18）。
- 同時段 `data/quotes_ibkr.json` 的 5 檔美股與指數報價也都是 `DELAYED`——這個 paper 帳戶沒有美股即時訂閱。

## 四、結論

1. **不衝突**：只要用不同 clientId（目前 47／48／49 已用），`reqHistoricalData` 跟 `ibkr_quotes.py` 可以同時連同一個 Gateway。真正的共用上限是「所有連線合計每秒 50 則訊息」，`ibkr_quotes.py` 每 5 分鐘約 20 則，1 分K 每檔一次請求，遠低於上限。用**同一個** clientId 才會互踢，這點不能做。
2. **頻率**：1 分K 沒有硬性 pacing 限制，只有軟性負載平衡；保守做法是比照小K 規則自我約束（同一請求 15 秒內不重發、10 分鐘 ≤60 次）。
3. **但拿到的是延遲約 15 分鐘的資料**。官方文件寫需要 Level 1 即時訂閱，實測沒有即時訂閱仍回延遲資料——**文件與實測不一致，以實測為準，但這個行為未來可能改變**。
4. 所以「美股 1 分K」技術上可做，但只能標「延遲約 15 分鐘」，不能叫即時；要即時需要總司令另外申請 IBKR 美股即時行情訂閱（要花錢，屬停下條件，不在本項範圍）。
5. 另一個斷點照舊：IBKR 每週日 01:00 ET 需人工重新連線 Gateway（見 CLAUDE.md），週一早上前 1 分K 會拿不到，要誠實顯示。

## 五、若要做，可選做法（交總司令審閱，未實作）

| 做法 | 內容 | 優點 | 風險 |
|---|---|---|---|
| A（建議） | live server 收到美股 `/live/kbars` 時，用獨立 clientId（例如 50）短命連線 `reqHistoricalData('1 D','1 min')`，結果快取 60 秒，回應帶 `mode:"ibkr-historical-1m-delayed"` 與「延遲約 15 分鐘」 | 不動 `ibkr_quotes.py`；請求量隨使用者開頁面，很少 | 動 `alpha_live_server.py` 要照七之二重啟四步驗證；Gateway 沒開時要回清楚原因 |
| B | `ibkr_quotes.py` 每 5 分鐘順手抓自選美股 1 分K 寫熱檔 | 不多開連線 | 每輪多 5 次請求、拉長短命連線；資料最多再晚 5 分鐘 |
| C | 改常駐訂閱、用 tick 自己聚合（跟台股同一套） | 架構一致 | 沒即時訂閱時 tick 也是延遲的，工程量最大，沒有增益 |

[自行裁量] 本項只查證，不動 `alpha_live_server.py`，501 訊息也先不改（改了就要重啟常駐服務，等做法定案一起改）。
