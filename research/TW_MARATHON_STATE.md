# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T15:05:00+08:00**（馬拉松第四輪執行後）

**地基狀態：✅ 完整可用，不需要額外搭建。** `universe.py`（全市場宇宙）、`adjust.py`（還原股價）、`pit.py`（point-in-time）、`factors.py`（因子計算框架）、`factor_ic.py`（IC 檢定引擎，含 Bonferroni 校正）、`score.py`（綜合分引擎）、`long_short_backtest.py`（十分位多空回測引擎，含配對式隨機控制組/CAPM beta/成本模型）全部可以直接重用。**這一軌可以直接從測新因子/深挖候選開始，不用等地基。**

**已知的立即可做工作（優先序）：**
1. ~~`f_value_pb`／`f_value_pe`／`f_quality_roe_stability` 重測~~ ✅ 第一輪（2026-08-23上午）已完成，見 `TW_LOG.md`／`TW_LEADS.md`／`TRIALS_LEDGER.md` #13–#15。
2. ~~深挖 `f_quality_roe_stability`~~ ✅ 第二輪（2026-08-23中午）已完成，新寫 `deep_dive_f_quality_roe_stability.py`。判定 `EXPERIMENTAL`（不是乾淨PASS）——十分位多空組合穩健贏過配對式隨機控制組、beta近零(market-neutral成立)，但淨成本後絕對報酬train/val正負號不一致，且隨機抽樣解析度不足。完整見 `TRIALS_LEDGER.md` #16、`TW_LEADS.md` #3、`TW_LOG.md` 該輪記錄、`data/deep_dive_f_quality_roe_stability.csv`。
3. ~~加密隨機控制組解析度~~ ✅ 第三輪（2026-08-23下午）已完成，`N_RANDOM_DRAWS` 20→100，6組配置全部仍贏過全部100次抽樣（percentile=100.0，p<0.01，比第二輪p<0.05更嚴格站穩）。判定維持 `EXPERIMENTAL`（train/val絕對報酬正負號不一致這個限制未被觸及，仍未解決）。完整見 `TRIALS_LEDGER.md` #17、`TW_LEADS.md` #3、`TW_LOG.md` 本輪記錄。**注意：跑100次抽樣耗時約9.5分鐘，若下一輪要再加抽樣次數，先評估時間預算（30分鐘鎖檔窗口），避免超時。**
4. ~~深挖 `f_value_pb` 前先補 PIT 驗證~~ ✅ 第四輪（2026-08-23下午）已完成，新寫 `verify_pit_value_pb.py`。2330單檔（2015–2024，40/42季度）跳變偵測：跳變日距季末天數min=32/median=45/max=62（從未貼近0天，無明顯前瞻偏誤），中位數貼近法規45天公告期限跟`pit.py`既有假設。**PIT狀態從「完全未驗證」升級為「單檔抽測無嚴重前瞻偏誤」**（不是完全驗證，只測1檔+間接跳變偵測法）。完整見`TRIALS_LEDGER.md`「已調查但不計入試驗數」表、`TW_LEADS.md`#1/#2、`TW_LOG.md`本輪記錄、`data/verify_pit_value_pb_2330.csv`。
5. **下一輪優先（任一）**：(a) 深挖 `f_value_pb`（十分位多空組合，方法比照`deep_dive_f_quality_roe_stability.py`的精神——配對式隨機控制組/TRAIN+VAL/成本敏感度1x2x3x/CAPM beta，但PIT前置驗證已完成可以直接開始，結果要註明PIT驗證範圍僅限單檔）；(b) 拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag——嘗試拉長換倉週期（例如60日）或縮小十分位比例，重跑`deep_dive_f_quality_roe_stability.py`比較TRAIN期結果是否轉正。
6. 完成上面之後，照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化掃過還沒碰過的因子家族：短期反轉、BAB/特異波動率、Amihud流動性、季節性、資產成長異常、Piotroski F-score、accruals盈餘品質。

**FinMind 資料集使用現況（避免重複調查已知資訊）：**
- 已驗證可用：`TaiwanStockPrice`／`TaiwanStockPER`／`TaiwanStockMonthRevenue`／`TaiwanStockFinancialStatements`／`TaiwanStockBalanceSheet`／`TaiwanStockInstitutionalInvestorsBuySell`／`TaiwanStockInfo`／`TaiwanStockDelisting`／`TaiwanStockDividend`。
- 已驗證付費/不可用：`TaiwanStockMarketValue`（市值，付費）、`TaiwanStockTradingDailyReport`（分點進出，付費）。
- 未驗證：融資券餘額、當沖比、借券餘額等籌碼資料集的確切 dataset 名稱跟免費層可用性——第一次要用到時要先用 curl 實測，不要用猜的。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`）。

---

## 下一步

見上方「已知的立即可做工作」。下一個馬拉松輪次接手時，先讀 `TW_LOG.md` 最新一條看上一輪實際做到哪裡（這份 state 檔案是快照，`TW_LOG.md` 才有完整過程）。
