# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T13:35:00+08:00**（馬拉松第三輪執行後）

**地基狀態：🟡 起步中，PIT資料源方向已確認可行。** 價格資料（`USStockPrice`）的深度/更新頻率已驗證可用；股票名單（`USStockInfo`）的形狀已摸清但還不能直接拿來建構無偏差宇宙；**SEC EDGAR 申報日期 API 已實測驗證可用**（見下方）。仍然沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`——**下一輪還是地基工作，還不能開始測因子**。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- `USStockPrice` 歷史深度／更新頻率（2026-08-23 馬拉松第一輪已驗證，見 `DATA.md`「美股里程碑1」小節、`US_LOG.md`）：AAPL/MSFT 兩檔巨型股回溯到 1990-01-02，逐日更新無漏交易日，欄位 `date, stock_id, Adj_Close, Close, High, Low, Open, Volume`。**只測了兩檔長年掛牌巨型股，中小型股/近年上市股深度未驗證，不能假設全市場都一樣長。**
- `USStockInfo`（2026-08-23 已驗證，見 `DATA.md`）：**這是名單快照，`date` 欄位是 FinMind 抓取這份名單的時間戳，不是股票上市日**（跟 `TaiwanStockInfo` 同款地雷，`universe.py` 已經處理過台股版本，美股要用類似精神但不能照抄邏輯，資料形狀不完全一樣）。289 個快照、18396 檔 distinct stock_id（5470 檔是 ETF）、最新快照（2026-08-22）12429 列可當現存股票+ETF基準。
- 美股存活者偏差（下市股名單/歷史價格）：完全沒測過，`DATA.md` 明確列為已知缺口。`USStockInfo` 快照之間的增減差異也許能反推粗略上下市窗，但這只是推測，還沒驗證。
- **SEC EDGAR 公開 JSON API（2026-08-23 馬拉松第三輪已實測驗證，見 `DATA.md`「美股 PIT 資料源調查」小節、`US_LOG.md`、`research/sec_edgar_probe.py`）**：`data.sec.gov/submissions/CIK{cik}.json` 對 AAPL/MSFT/PLTR 三檔都 200 OK，`filingDate`/`reportDate` 欄位確實存在。10-K/10-Q 的 filingDate−reportDate 天數差：AAPL平均33.1天、MSFT平均27.5天、PLTR平均41.5天（範圍34–57天，明顯比兩檔大型股寬——**這是新發現，設計保守預設值時不能只看大型股**）。`www.sec.gov/files/company_tickers.json`（ticker→CIK對照）也驗證可用。歷史回溯用 `filings.files[]` 分頁機制可以拿到（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有實際抓分頁內容。這是既有資料源清單「美股財報（SEC EDGAR）」的公開文件依據，凍結區`alpha-data/fetch.py`裡如果有類似邏輯，只能參考不能照抄。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。

**下一輪建議工作單位（只做其中一項，不要一次全做）：**
1. **美股存活者偏差**：調查下市/被下市美股的名單跟歷史價格資料源（`USStockInfo` 快照比對法先當假設試試看，不行的話找其他來源）。這是目前最大的地基缺口（PIT資料源方向已確認，存活者偏差完全還沒動）。
2. XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）實測——第三輪只測了 submissions API，company facts 據稱有更細的 `filed` 欄位但完全沒打過。
3. 中小型股/近期上市股的 `USStockPrice` 歷史深度抽測（本輪只測了 AAPL/MSFT 兩檔巨型股，不能假設全市場都一樣深）。
4. 把 `sec_edgar_probe.py` 的邏輯正式包裝成一個可重用的 fetch 函式，目前只是探測腳本，還不是可以被其他程式呼叫的模組。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。
