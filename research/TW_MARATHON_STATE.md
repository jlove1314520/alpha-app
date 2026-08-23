# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T09:50:00+08:00**（馬拉松第一輪執行後）

**地基狀態：✅ 完整可用，不需要額外搭建。** `universe.py`（全市場宇宙）、`adjust.py`（還原股價）、`pit.py`（point-in-time）、`factors.py`（因子計算框架）、`factor_ic.py`（IC 檢定引擎，含 Bonferroni 校正）、`score.py`（綜合分引擎）全部可以直接重用。**這一軌可以直接從測新因子開始，不用等地基。**

**已知的立即可做工作（優先序）：**
1. ~~`f_value_pb`／`f_value_pe`／`f_quality_roe_stability` 重測~~ ✅ 第一輪（2026-08-23）已完成，見 `TW_LOG.md`／`TW_LEADS.md`／`TRIALS_LEDGER.md` #13–#15。結果：`f_value_pb`、`f_quality_roe_stability` 過便宜關卡（含累積校正），排進待深挖；`f_value_pe` 批次過但累積校正後降級，暫緩。
2. **下一輪優先**：深挖 `f_quality_roe_stability`（PIT機制已驗證，優先序最高，見 `TW_LEADS.md`）——樣本外/WFA、配對式隨機控制組、成本敏感度1x/2x/3x、beta對照、經濟解釋具體化。
3. 若要深挖 `f_value_pb`，**必須先補 PIT 驗證**（查 FinMind `TaiwanStockPER` 的 PBR 更新時點是否等到財報公告才變動），不能跳過直接深挖。
4. 完成上面之後，照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化掃過還沒碰過的因子家族：短期反轉、BAB/特異波動率、Amihud流動性、季節性、資產成長異常、Piotroski F-score、accruals盈餘品質。

**FinMind 資料集使用現況（避免重複調查已知資訊）：**
- 已驗證可用：`TaiwanStockPrice`／`TaiwanStockPER`／`TaiwanStockMonthRevenue`／`TaiwanStockFinancialStatements`／`TaiwanStockBalanceSheet`／`TaiwanStockInstitutionalInvestorsBuySell`／`TaiwanStockInfo`／`TaiwanStockDelisting`／`TaiwanStockDividend`。
- 已驗證付費/不可用：`TaiwanStockMarketValue`（市值，付費）、`TaiwanStockTradingDailyReport`（分點進出，付費）。
- 未驗證：融資券餘額、當沖比、借券餘額等籌碼資料集的確切 dataset 名稱跟免費層可用性——第一次要用到時要先用 curl 實測，不要用猜的。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`）。

---

## 下一步

見上方「已知的立即可做工作」。下一個馬拉松輪次接手時，先讀 `TW_LOG.md` 最新一條看上一輪實際做到哪裡（這份 state 檔案是快照，`TW_LOG.md` 才有完整過程）。
