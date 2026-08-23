# US_LOG.md — 美股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面）。美股軌是全新的，這份檔案從第一輪馬拉松開始就是美股軌唯一的執行記錄。

**規則：** 每個馬拉松輪次結束前 append 一條，包含地基搭建進度（美股軌前期主要是這個）跟之後的因子/策略測試結果，不管有沒有進展都要記錄。

---

## 2026-08-23T02:00:00+08:00 — 美股軌馬拉松初始化

檔案建立，尚未有實際輪次執行。地基完全未搭建，第一輪工作見 `US_MARATHON_STATE.md`。

## 2026-08-23T10:30:00+08:00 — 馬拉松第一輪：里程碑1資料驗證（歷史深度/更新頻率/代號涵蓋）

做了 `US_MARATHON_STATE.md` 建議的第一輪工作單位第 1 項：用 `research/us_probe_milestone1.py`（全部走 `load_dev()`，封頂 VAL_END）實測 `USStockPrice` 的歷史深度、更新頻率，跟 `USStockInfo`（`_fetch()` 直接呼叫，membership 快照，理由同 `universe.py` 對 `TaiwanStockInfo` 的處理）的代號涵蓋範圍。

結果：AAPL/MSFT 都有 1990-01-02 起 8817 筆逐日資料到 VAL_END，2024-06 抽測無漏交易日；`USStockInfo` 是 289 個時間快照疊出來的名單（不是上市日），distinct stock_id 18396 檔（5470 檔 ETF），最新快照（2026-08-22）12429 列。完整細節寫進 `DATA.md`「美股里程碑1」小節。

**沒做的**：美股存活者偏差（下市股名單/歷史價格）完全還沒測——這是這個工作單位刻意排除的部分（一輪只做一件事），留給下一輪。SEC EDGAR PIT 資料源、美股成本模型也都還沒碰。

`is_holdout_consumed()` 確認為 `False`（本輪全程只碰 <=VAL_END 的資料 + 一個不含日期時間序列語意的 membership 快照）。
