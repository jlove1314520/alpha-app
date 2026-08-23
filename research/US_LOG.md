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

## 2026-08-23T13:00:00+08:00 — 馬拉松第二輪：SEC EDGAR PIT 資料源文件調查

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 2 項：查證 SEC EDGAR 公開 JSON API 能不能拿到申報日期（filing date）。**這輪完全是文件調查，沒有寫程式碼、沒有實際打過 `data.sec.gov` 的任何 API 請求。**

查到：submissions API（`data.sec.gov/submissions/CIK{cik}.json`）文件顯示每筆申報記錄同時有 `filingDate`（申報日）跟 `reportDate`（財報期間結束日）兩個獨立欄位；XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）據稱每個數值點也帶 `filed` 欄位。如果實測驗證屬實，美股 PIT 可以比台股「+45天保守假設」精確很多。查證來源是第三方 wrapper 文件（`sec-edgar-api.readthedocs.io`），因為 `www.sec.gov` 本身的網頁對本環境的 fetch 工具回傳 403（原因未查明），只能先參考轉述來源，**還沒有一手驗證**。完整細節、還沒查的部分（rate limit 官方原文、資料回溯深度等）寫進 `DATA.md`「美股 PIT 資料源調查」小節。

**沒做的**：完全沒有實際呼叫任何 SEC EDGAR API，欄位結構是否真的如文件所述、能不能順利解析，都還是假設——下一輪建議直接對 AAPL（CIK=0000320193）打一次 submissions API 驗證。美股存活者偏差、成本模型也還沒碰。

`is_holdout_consumed()` 確認為 `False`（本輪完全沒有觸碰任何 FinMind 或 alpha.db 資料，純網路文件查證）。

## 2026-08-23T13:35:00+08:00 — 馬拉松第三輪：SEC EDGAR API 實測驗證

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 1 項：把第二輪的文件調查升級成真實 API 呼叫。寫了 `research/sec_edgar_probe.py`，先手動確認 `data.sec.gov` 沒有 `robots.txt`（404，等於沒有額外爬取限制）、`www.sec.gov/robots.txt` 沒有 disallow 相關路徑，再對三檔股票（AAPL、MSFT、PLTR——刻意加一檔非巨型股避免重蹈第一輪只測兩檔大型股的偏差）打了 `www.sec.gov/files/company_tickers.json` 跟 `data.sec.gov/submissions/CIK{cik}.json`。

**結果：全部驗證通過。** `filingDate`/`reportDate` 欄位確實存在（三檔都200 OK），ticker→CIK對照表也可用（10403筆）。新發現：10-K/10-Q 的 filingDate−reportDate 天數差因公司而異，AAPL平均33.1天、MSFT平均27.5天，但PLTR平均41.5天（範圍34–57天）——比兩檔大型股寬不少，代表未來設計「找不到精確filingDate時的保守預設值」不能只用大型股估。另外發現 `filings.files[]` 分頁機制可以拿到更早期申報記錄（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有抓分頁內容。完整數字寫進 `DATA.md`「美股 PIT 資料源調查」小節（已從「文件調查」升級為「已驗證」，原第二輪記錄摺疊保留在該小節底部作對照）。

**沒做的**：XBRL company facts API（據稱有更細的 `filed` 欄位）完全沒測；`filings.files[]` 分頁檔案內容沒抓；美股存活者偏差、成本模型都還沒碰；`sec_edgar_probe.py` 目前只是探測腳本，還沒包裝成可重用的 fetch 函式。這不是一次統計檢定（沒有因子/策略假說被測試），所以 `TRIALS_LEDGER.md` 不需要加列，跟 `MARATHON_PROTOCOL.md` 第1c節「地基工作」的精神一致。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。
