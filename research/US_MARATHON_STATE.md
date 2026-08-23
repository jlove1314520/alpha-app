# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T15:35:00+08:00**（馬拉松第四輪執行後）

**地基狀態：🟡 起步中，PIT資料源方向已確認可行，存活者偏差方向已確認「兩個候選方法都不可靠」（負面但重要的進展）。** 價格資料（`USStockPrice`）的深度/更新頻率已驗證可用；股票名單（`USStockInfo`）的形狀已摸清但還不能直接拿來建構無偏差宇宙；**SEC EDGAR 申報日期 API 已實測驗證可用**（見下方）；**美股存活者偏差：`universe.py` 的價格列存在法、`USStockInfo` 快照增減法，這輪實測後都證實不可靠**（見下方，細節在 `DATA.md`「美股存活者偏差調查」小節）。仍然沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`——**下一輪還是地基工作，還不能開始測因子**。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- `USStockPrice` 歷史深度／更新頻率（2026-08-23 馬拉松第一輪已驗證，見 `DATA.md`「美股里程碑1」小節、`US_LOG.md`）：AAPL/MSFT 兩檔巨型股回溯到 1990-01-02，逐日更新無漏交易日，欄位 `date, stock_id, Adj_Close, Close, High, Low, Open, Volume`。**只測了兩檔長年掛牌巨型股，中小型股/近年上市股深度未驗證，不能假設全市場都一樣長。**
- `USStockInfo`（2026-08-23 已驗證，見 `DATA.md`）：**這是名單快照，`date` 欄位是 FinMind 抓取這份名單的時間戳，不是股票上市日**（跟 `TaiwanStockInfo` 同款地雷，`universe.py` 已經處理過台股版本，美股要用類似精神但不能照抄邏輯，資料形狀不完全一樣）。289 個快照、18396 檔 distinct stock_id（5470 檔是 ETF）、最新快照（2026-08-22）12429 列可當現存股票+ETF基準。
- **美股存活者偏差（2026-08-23 馬拉松第四輪已實測，見 `DATA.md`「美股存活者偏差調查」小節、`US_LOG.md`、`research/us_survivorship_probe.py`）**：用 5 檔已知下市/出事美股（TWTR、SIVB、SBNY、FRC、BBBY）測了兩個候選方法，**都不可靠**——(a) 台股用的「價格列存在=地面真相」方法：TWTR/SIVB/FRC 三檔完全 EMPTY（資料直接消失，不是保留到下市日），SBNY/BBBY 兩檔的資料時間軸跟已知下市事件對不上（疑似代號重用或原本認知的下市日不準確，這輪沒查證是哪一種）；(b) `USStockInfo` 快照增減法：TWTR 289 個快照裡只出現過 1 次卻實際活躍交易到 2022 年，證明快照本身覆蓋率就不完整，跟下市無關。**結論：不能盲目用「有資料=活著」判斷美股上下市，代號重用（ticker reuse）是美股特有、台股沒有的陷阱，比「完全沒資料」更危險（會沉默地把兩家公司的歷史接成一條假的連續序列）。**下一步需要獨立的下市股名單來源（候選：SEC EDGAR Form 25/25-NSE 下市申報記錄，這輪沒有驗證，只是假設）。
- **SEC EDGAR 公開 JSON API（2026-08-23 馬拉松第三輪已實測驗證，見 `DATA.md`「美股 PIT 資料源調查」小節、`US_LOG.md`、`research/sec_edgar_probe.py`）**：`data.sec.gov/submissions/CIK{cik}.json` 對 AAPL/MSFT/PLTR 三檔都 200 OK，`filingDate`/`reportDate` 欄位確實存在。10-K/10-Q 的 filingDate−reportDate 天數差：AAPL平均33.1天、MSFT平均27.5天、PLTR平均41.5天（範圍34–57天，明顯比兩檔大型股寬——**這是新發現，設計保守預設值時不能只看大型股**）。`www.sec.gov/files/company_tickers.json`（ticker→CIK對照）也驗證可用。歷史回溯用 `filings.files[]` 分頁機制可以拿到（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有實際抓分頁內容。這是既有資料源清單「美股財報（SEC EDGAR）」的公開文件依據，凍結區`alpha-data/fetch.py`裡如果有類似邏輯，只能參考不能照抄。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。

**下一輪建議工作單位（只做其中一項，不要一次全做）：**
1. **美股存活者偏差，接續上一輪**：用已驗證可用的 SEC EDGAR API（`company_tickers.json` + `submissions`）去查證 TWTR/SIVB/SBNY/FRC/BBBY 這幾檔的真實下市時間跟後續申報狀態（例如 Form 25），而不是繼續依賴人的記憶當「已知下市日」；如果 SEC EDGAR 也查不到明確的下市股清單，才考慮找其他來源（交易所公告等）。
2. XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）實測——第三輪只測了 submissions API，company facts 據稱有更細的 `filed` 欄位但完全沒打過。
3. 中小型股/近期上市股的 `USStockPrice` 歷史深度抽測（本輪只測了 AAPL/MSFT 兩檔巨型股，不能假設全市場都一樣深）。
4. 把 `sec_edgar_probe.py` 的邏輯正式包裝成一個可重用的 fetch 函式，目前只是探測腳本，還不是可以被其他程式呼叫的模組。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。
