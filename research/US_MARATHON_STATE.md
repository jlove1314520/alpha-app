# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T02:00:00+08:00**（馬拉松設立時的初始快照，尚未有任何馬拉松輪次執行過）

**地基狀態：❌ 完全未搭建。** 沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`。**第一批馬拉松輪次的工作是搭地基，不是測因子**——見 `MARATHON_PROTOCOL.md` 第 5 節。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- 美股存活者偏差：完全沒測過，`DATA.md` 明確列為已知缺口。
- 美股 point-in-time 財報：`CLAUDE.md` 提過既有資料源清單裡有「美股財報（SEC EDGAR）」，但那是 `alpha-data/`（凍結區）裡的抓取邏輯，**只能參考公開的 SEC EDGAR API 文件跟資料結構重新寫一份給 `research/` 用，不能直接動用或複製凍結區的程式碼**。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。

**第一輪建議工作單位（只做其中一項，不要一次全做）：**
1. 用 `curl`／`_fetch()` 實測 `USStockPrice` 的歷史深度、涵蓋的股票代號範圍、資料更新頻率——不要用猜的，比照台股當初 `DATA.md` 里程碑1的做法（直接打 API 驗證）。
2. 調查 SEC EDGAR 公開 API（`https://www.sec.gov/cgi-bin/browse-edgar` 或其 JSON API）能不能拿到申報日期（filing date，不是財報期間），這是美股版 `pit.py` 的關鍵——美股通常有相對清楚的申報日期（10-Q/10-K 的 filing date），可能比台股的「保守假設 +45 天」更精確，值得優先查證。
3. 美股下市股名單資料源調查（存活者偏差處理需要）。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「第一輪建議工作單位」，一次只做一項。
