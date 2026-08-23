# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T20:05:00+08:00**（馬拉松第七輪期貨軌執行後）

**地基狀態：🟢 三個核心地基問題已全部釐清（`TaiwanFuturesDaily` 的 `settlement_price`/`open_interest`、`TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位、以及連續合約轉倉時點規則都已解決）。連續合約銜接方法的**設計決策**（第一輪）跟**轉倉時點規則**（本輪）都已確定，下一步可以開始寫連續合約建構程式碼本身。** 詳見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪解決：轉倉時點規則，採用 H1（結算日轉倉）**（詳細版見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`「轉倉時點規則：✅ 已驗證」章節、`FUT_LOG.md` 本輪條目）：
- 用 `TaiwanFuturesDaily` 全歷史快取（2000-2024，零額外 API 呼叫，重用既有 parquet 快取檔案），對全部 300 個月結算週期做「結算日前10個交易日內，近月/次近月成交量是否曾超車」的檢驗。
- `position` session：45/300（15.0%）週期曾發生超車，但**全部集中在結算日前 1～2 個日曆天**，沒有更早的提前遷移現象。
- `after_market` session：92 個可測週期，**0 次**超車。
- **判讀：H1 成立，不需要另外實作 H2 成交量交叉偵測邏輯**——結算日附近的自然轉倉本身就會產生「最後一兩天量能超車」的現象，這不是獨立於結算日之外的訊號。
- **附帶發現**（間接推論，非官方確認）：`after_market` 資料起始日（2017-05-16）跟 TAIFEX 夜盤上線日（2017-05-15）幾乎完全吻合，高信心推論 `after_market`＝夜盤、`position`＝日盤。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：開始寫連續合約建構程式碼——比價法（ratio back-adjustment，見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 的設計決策）套用本輪確定的 H1 轉倉規則（結算日或結算日前一交易日轉倉），保留原始未調整價格為稽核軌跡（精神同 `adjust.py` 對股票的做法，但不能照抄邏輯）。這是一個可能跨多輪的工作項目，第一輪先把單一合約序列銜接寫出來、用少數幾次轉倉手動驗證正確性即可，不用一次做完全部功能。
2. 連續合約寫出來初步能動之後，實測比價法「連續多次轉倉後累積漂移幅度」（`FUT_CONTINUOUS_CONTRACT_DESIGN.md` 尚待驗證 #2）——用回溯調整後的價格 vs 真實現價比較，看漂移是否在合理範圍。
3. （較低優先，不擋路）用 FinMind 官方欄位文件或另外查證確認 `after_market`＝夜盤的推論是否正確（目前只是起始日期吻合的間接證據）。
4. 地基跟連續合約都就緒之後，才開始照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化測期貨因子（多時間框架趨勢、突破 Donchian channel、波動 regime 過濾、均線系統、日內均值回歸、期現價差、三大法人期貨部位、未平倉量變化、隔夜 vs 日內報酬、星期效應、盤別效應）。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約的設計決策跟轉倉規則（本輪已確定，都在這份文件裡），再讀 `DATA.md` 第 6 節看資料集欄位細節。
