# DATA_SOURCE_MAP.md — 跨市場資料源原生性與查證紀錄

依 `CLAUDE.md`「各市場一律使用該市場的原生資料源」與「搜尋紀律：三來源查證」
兩條規則建立。每一筆條目記錄：原生市場、為何在這個市場可信、查證過程用了
哪些獨立來源。

---

## 全市場現股當沖逐檔成交量值（TWSE TWTASU）

**查證日期：2026-09-08（馬拉松馬拉松第432輪，TW軌，`HYPOTHESIS_QUEUE.md` #57）**

**背景**：`#57`（全市場當沖比重截面離散度速度）原本卡在「前置未備」——
`HYPOTHESIS_QUEUE.md` #57 條目寫「本輪尚未查證逐檔當沖端點的實際路徑」，
懷疑需要另找一個新的 TWSE 端點才能拿到「每檔股票」的當沖成交量值
（而不是全市場加總）。

**結論：不需要新端點。已在用的 `TWTASU` 端點本來就是逐檔資料，只是
`twse_day_trading_client.py::fetch_day_trading_ratio_day()`（`#37` 用）
刻意只取最後一列「合計」、逐檔列在記憶體裡直接丟棄、從未落地存檔。**

### 查證紀錄（四類來源查了三類）

1. **官方端點直接查證（本輪實測）**：
   `https://www.twse.com.tw/rwd/zh/afterTrading/TWTASU?date=20260904&response=json`
   （2026-09-08 直接呼叫）回傳 `stat=OK`，`data` 陣列 **1332 列**，
   第一列是個股列（例：`2330   台積電`，欄位依序為
   `[當沖賣出成交數量, 當沖賣出成交金額, 資券互抵成交數量, 資券互抵成交金額]`），
   最後一列才是 `合計`。往回測到 `date=20130102` 一樣有逐檔資料
   （`stat=OK`，863 列），確認歷史涵蓋遠早於 `TRAIN_START=2015-01-01`。

2. **官方 API 文件（openapi.twse.com.tw swagger，2026-09-08 查證）**：
   `https://openapi.twse.com.tw/v1/swagger.json` 裡跟「沖銷」相關只有
   3 個端點：`/exchangeReport/TWTB4U`（schema 只有
   `Date`/`Code`/`Name`/`Suspension` 四欄，是「當沖資格標的清單」，
   **不含量值**）、`/exchangeReport/TWTBAU1`、`/exchangeReport/TWTBAU2`
   （暫停先賣後買公告，也不含量值）。**這確認了 `TWTB4U` 不是我們要的
   端點**——名稱裡都有「當沖」容易搞混，但 `TWTB4U` 是資格清單、
   `TWTASU` 才是成交量值。`TWTASU` 本身不在 openapi 的 swagger 清單裡
   （它是 `www.twse.com.tw/rwd` 舊式端點，不是 openapi 新式端點），
   所以官方 API 文件查不到它的 schema，只能靠直接呼叫驗證（見上第1點）。

3. **GitHub／社群實作查證**：`github.com/twjackysu/TWSEMCPServer`
   （2026-09-08 clone 查證）的 `tools/trading/market.py` 明確把
   `/exchangeReport/TWTB4U` 標記為 `get_daily_day_trading_targets`
   （查詢「當日沖銷交易標的」資格清單），印證第 2 點的判斷——社群
   實作也沒有人把 `TWTB4U` 當成量值端點在用。

4. **其他供應商**：FinMind 有 `TaiwanStockDayTrading` 資料集（本輪呼叫
   免費層回傳 402 額度用盡，但錯誤訊息本身證明資料集存在，且
   `twse_day_trading_client.py` 既有 docstring 記載「該端點免費層只從
   2024-01-02 起有資料」）——印證這份資料本來就有人整理成商品在賣，
   不是我們自己首創的資料維度，只是免費層歷史不夠長，所以 `#37`/`#57`
   才選擇直接打 TWSE 官方原始端點。

### 對 #57 的影響

- **不必等待任何新端點查證或回填風險評估**——資料源已確認可得。
- **代價**：`#37` 既有回補（`backfill_day_trading_ratio.py`，
  2015-01-01~VAL_END 約 2,609 個交易日）的原始逐檔 JSON 從未保存，
  無法從已快取的彙總 parquet 反推回逐檔，必須重新呼叫一次 TWTASU
  端點（新增 `twse_day_trading_client.py::fetch_day_trading_detail_day()`
  ＋ `backfill_day_trading_detail.py`，獨立快取目錄
  `data/raw_twse_day_trading_detail/`，跟 `#37` 的單列彙總快取不共用、
  不互相影響）。
- 回補已於本輪（第432輪）用 `run_detached.py` 投遞
  （job `20260908-061051-6640`，`--batch-size 250`，同一套
  `SLEEP_BETWEEN_CALLS=2.0秒/次` 節流），預期需要多輪馬拉松才能跑完
  全部 2,609 個交易日（每批約 8~9 分鐘處理 250 天）。
