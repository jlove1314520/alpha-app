# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T13:00:00+08:00**（馬拉松第二輪執行後）

**地基狀態：🟡 起步中。** 價格資料（`USStockPrice`）的深度/更新頻率已驗證可用；股票名單（`USStockInfo`）的形狀已摸清但還不能直接拿來建構無偏差宇宙。仍然沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`——**下一輪還是地基工作，還不能開始測因子**。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- `USStockPrice` 歷史深度／更新頻率（2026-08-23 馬拉松第一輪已驗證，見 `DATA.md`「美股里程碑1」小節、`US_LOG.md`）：AAPL/MSFT 兩檔巨型股回溯到 1990-01-02，逐日更新無漏交易日，欄位 `date, stock_id, Adj_Close, Close, High, Low, Open, Volume`。**只測了兩檔長年掛牌巨型股，中小型股/近年上市股深度未驗證，不能假設全市場都一樣長。**
- `USStockInfo`（2026-08-23 已驗證，見 `DATA.md`）：**這是名單快照，`date` 欄位是 FinMind 抓取這份名單的時間戳，不是股票上市日**（跟 `TaiwanStockInfo` 同款地雷，`universe.py` 已經處理過台股版本，美股要用類似精神但不能照抄邏輯，資料形狀不完全一樣）。289 個快照、18396 檔 distinct stock_id（5470 檔是 ETF）、最新快照（2026-08-22）12429 列可當現存股票+ETF基準。
- 美股存活者偏差（下市股名單/歷史價格）：完全沒測過，`DATA.md` 明確列為已知缺口。`USStockInfo` 快照之間的增減差異也許能反推粗略上下市窗，但這只是推測，還沒驗證。
- 美股 point-in-time 財報：`CLAUDE.md` 提過既有資料源清單裡有「美股財報（SEC EDGAR）」，但那是 `alpha-data/`（凍結區）裡的抓取邏輯，**只能參考公開的 SEC EDGAR API 文件跟資料結構重新寫一份給 `research/` 用，不能直接動用或複製凍結區的程式碼**。
- **SEC EDGAR 公開 JSON API 文件調查（2026-08-23 馬拉松第二輪已做，見 `DATA.md`「美股 PIT 資料源調查」小節、`US_LOG.md`）**：查到 submissions API（`data.sec.gov/submissions/CIK{cik}.json`）每筆申報同時有 `filingDate`（真正申報日）跟 `reportDate`（財報期間），如果屬實會比台股「+45天保守假設」精確很多。**這是文件調查，不是實測**——還沒真的打過 API 驗證欄位結構，下一輪應該先實測 1–2 檔股票再繼續。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。

**下一輪建議工作單位（只做其中一項，不要一次全做）：**
1. **SEC EDGAR API 實測（優先，接續本輪）**：對 1–2 檔美股（例如 AAPL，CIK=0000320193）實際打一次 `data.sec.gov/submissions/CIK{cik}.json`，確認 `filingDate`/`reportDate` 欄位真的存在、User-Agent header 需求、能不能正常解析成可用的申報日期清單。驗證通過才能把 PIT 資料源從「文件調查」升級成「已驗證」。
2. 美股存活者偏差：調查下市/被下市美股的名單跟歷史價格資料源（`USStockInfo` 快照比對法先當假設試試看，不行的話找其他來源）。
3. 中小型股/近期上市股的 `USStockPrice` 歷史深度抽測（本輪只測了 AAPL/MSFT 兩檔巨型股，不能假設全市場都一樣深）。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。
