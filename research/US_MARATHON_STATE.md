# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T09:40:00+08:00**（馬拉松第六輪執行後）

**地基狀態：🟡 起步中，PIT資料源方向已確認可行，存活者偏差方向已確認「兩個候選方法都不可靠」，且第五、六輪用 SEC EDGAR 獨立核實了部分下市案例（負面但重要的進展）。** 價格資料（`USStockPrice`）的深度/更新頻率已驗證可用；股票名單（`USStockInfo`）的形狀已摸清但還不能直接拿來建構無偏差宇宙；**SEC EDGAR 申報日期 API 已實測驗證可用**（見下方）；**美股存活者偏差：`universe.py` 的價格列存在法、`USStockInfo` 快照增減法，這輪實測後都證實不可靠**（見下方，細節在 `DATA.md`「美股存活者偏差調查」小節）；**第五輪用 SEC EDGAR Form 25 進一步核實：TWTR/SIVB 確認為真下市（跟第四輪憑記憶的日期大致吻合），BBBY 代號重用得到獨立確認且比第四輪證據更直接，SBNY 這輪失敗（我手寫的備援 CIK 猜錯，查到 Google 的資料，作廢），FRC 查不到 Form 25（未解決的開放問題）**。仍然沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`——**下一輪還是地基工作，還不能開始測因子**。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- `USStockPrice` 歷史深度／更新頻率（2026-08-23 馬拉松第一輪已驗證，見 `DATA.md`「美股里程碑1」小節、`US_LOG.md`）：AAPL/MSFT 兩檔巨型股回溯到 1990-01-02，逐日更新無漏交易日，欄位 `date, stock_id, Adj_Close, Close, High, Low, Open, Volume`。**只測了兩檔長年掛牌巨型股，中小型股/近年上市股深度未驗證，不能假設全市場都一樣長。**
- `USStockInfo`（2026-08-23 已驗證，見 `DATA.md`）：**這是名單快照，`date` 欄位是 FinMind 抓取這份名單的時間戳，不是股票上市日**（跟 `TaiwanStockInfo` 同款地雷，`universe.py` 已經處理過台股版本，美股要用類似精神但不能照抄邏輯，資料形狀不完全一樣）。289 個快照、18396 檔 distinct stock_id（5470 檔是 ETF）、最新快照（2026-08-22）12429 列可當現存股票+ETF基準。
- **美股存活者偏差（2026-08-23 馬拉松第四輪已實測，見 `DATA.md`「美股存活者偏差調查」小節、`US_LOG.md`、`research/us_survivorship_probe.py`）**：用 5 檔已知下市/出事美股（TWTR、SIVB、SBNY、FRC、BBBY）測了兩個候選方法，**都不可靠**——(a) 台股用的「價格列存在=地面真相」方法：TWTR/SIVB/FRC 三檔完全 EMPTY（資料直接消失，不是保留到下市日），SBNY/BBBY 兩檔的資料時間軸跟已知下市事件對不上（疑似代號重用或原本認知的下市日不準確，這輪沒查證是哪一種）；(b) `USStockInfo` 快照增減法：TWTR 289 個快照裡只出現過 1 次卻實際活躍交易到 2022 年，證明快照本身覆蓋率就不完整，跟下市無關。**結論：不能盲目用「有資料=活著」判斷美股上下市，代號重用（ticker reuse）是美股特有、台股沒有的陷阱，比「完全沒資料」更危險（會沉默地把兩家公司的歷史接成一條假的連續序列）。**下一步需要獨立的下市股名單來源（候選：SEC EDGAR Form 25/25-NSE 下市申報記錄，這輪沒有驗證，只是假設）。
- **SEC EDGAR 公開 JSON API（2026-08-23 馬拉松第三輪已實測驗證，見 `DATA.md`「美股 PIT 資料源調查」小節、`US_LOG.md`、`research/sec_edgar_probe.py`）**：`data.sec.gov/submissions/CIK{cik}.json` 對 AAPL/MSFT/PLTR 三檔都 200 OK，`filingDate`/`reportDate` 欄位確實存在。10-K/10-Q 的 filingDate−reportDate 天數差：AAPL平均33.1天、MSFT平均27.5天、PLTR平均41.5天（範圍34–57天，明顯比兩檔大型股寬——**這是新發現，設計保守預設值時不能只看大型股**）。`www.sec.gov/files/company_tickers.json`（ticker→CIK對照）也驗證可用。歷史回溯用 `filings.files[]` 分頁機制可以拿到（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有實際抓分頁內容。這是既有資料源清單「美股財報（SEC EDGAR）」的公開文件依據，凍結區`alpha-data/fetch.py`裡如果有類似邏輯，只能參考不能照抄。
- **SEC EDGAR Form 25 下市核實（2026-08-23 馬拉松第五輪已實測，見 `DATA.md`「美股存活者偏差調查（續）」小節、`US_LOG.md`、`research/sec_edgar_delisting_probe.py`）**：`TWTR`（25-NSE 2022-10-28）、`SIVB`（25-NSE 2023-05-02，另有 2017-2018 一組較早的申報，疑似不同證券類別下市，未分辨）確認為真下市，跟第四輪憑記憶的日期大致吻合。`BBBY` 現行 `company_tickers.json` 把 ticker 指向 CIK 1130713（公司名「NEIGHBORHOOD INTELLIGENCE, INC.」，不是 Bed Bath & Beyond）——**獨立確認代號重用是真的，且連 SEC 自己現行的 ticker 對照表都會被重用代號誤導，之後任何用「ticker→CIK/身分」單一對照表的設計都要考慮這個陷阱**。`FRC` 查不到 Form 25（`filings.recent` 視窗 43筆全無，可能要查 `filings.files[]` 分頁或 FDIC 接管走不同申報機制，未解決）。**重要更正（第六輪已在 `sec_edgar_delisting_probe.py` 的 docstring 跟 `FALLBACK_CIK` 註解裡修正）**：`sec_edgar_delisting_probe.py` 原本假設「手寫備援 CIK 比手寫日期安全」，第五輪 `SBNY` 案例（猜到 Google）證明這個假設錯——任何手寫、未經查證的識別碼都有猜錯風險，不是 CIK 就比較安全。
- **`SBNY` 正確 CIK 仍未查到（2026-08-24 馬拉松第六輪已嘗試，見 `DATA.md`「美股存活者偏差調查（再續）」小節、`US_LOG.md`）**：排除了兩個錯誤候選（1288776=Google、1288784=無關的 CO 小型銀行控股公司「Signature Bank Corp」），用 `browse-edgar` 公司名稱搜尋跟 `efts.sec.gov` 全文檢索（含逐頁掃完 2023-03-01～2023-06-30 全部 200 筆 Form 25-NSE 申報實體）都找不到任何名稱含「Signature」的申報實體。**發現：`browse-edgar` 的公司名稱搜尋在沒有精確符合時會自動跳到字母排序最近的單一公司（不是回傳候選清單），這輪之前誤以為它像搜尋引擎一樣會列多筆候選，這個假設是錯的，之後要查公司名稱優先用 `efts.sec.gov` 全文檢索的 entity 聚合，不要用 `browse-edgar` 名稱搜尋做探索式查詢。**`FALLBACK_CIK["SBNY"]` 已改成 `None` 並在腳本註解標記「已知錯誤待查，不要用猜的」。
- **新假設（未查證）：FDIC 接管型下市可能不走標準 Form 25**：`SBNY`（第六輪）跟 `FRC`（第五輪）兩個獨立案例都是「銀行被監管機關強制接管清算」，都查不到 Form 25/25-NSE；相對地 `TWTR`／`SIVB`（一般公司自願下市或被併購）都乾淨查到了。兩個案例同款結果不太像巧合，但這輪沒有進一步查證（例如查 FDIC BankFind Suite 或 Nasdaq 官方停牌公告），下一輪如果要繼續深挖可以驗證這個假設，或改用 SEC EDGAR 以外的資料源找銀行接管型下市案例的下市日。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。

**下一輪建議工作單位（只做其中一項，不要一次全做）：**
1. **驗證「FDIC 接管型下市不走 Form 25」假設，或改用非 SEC 資料源查 `SBNY`/`FRC` 下市日**：候選來源包括 FDIC BankFind Suite 公開資料庫、Nasdaq 官方停牌/下市公告——這兩個都不是 SEC EDGAR，第一次嘗試前要先確認公開可讀、不需登入（符合協定第3節規則）。
2. **`FRC` 查 `filings.files[]` 分頁檔案**：`filings.recent` 視窗裡沒有 Form 25，需要抓分頁檔案內容才能確定是視窗覆蓋不到，還是 FDIC 接管清算真的走不同申報機制（這跟上面第1項可能是同一個答案，但這項是純粹在 SEC EDGAR 內部查證，風險/複雜度較低，可以先做）。
3. XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）實測——第三輪只測了 submissions API，company facts 據稱有更細的 `filed` 欄位但完全沒打過。
4. 中小型股/近期上市股的 `USStockPrice` 歷史深度抽測（本輪只測了 AAPL/MSFT 兩檔巨型股，不能假設全市場都一樣深）。
5. 把 `sec_edgar_probe.py` 的邏輯正式包裝成一個可重用的 fetch 函式，目前只是探測腳本，還不是可以被其他程式呼叫的模組。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。
