# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T03:01:00+08:00**（馬拉松第30輪期貨軌執行後）

**地基狀態：🟢 完整可用，可以開始測短中期回看窗口的因子/策略假說。** `continuous_contract.py`（連續合約建構）、轉倉時點規則（H1）、資料欄位品質（`settlement_price`/`open_interest`/`institutional_investors`）、累積漂移幅度全部已驗證。詳見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪完成：累積漂移幅度實測（`fut_drift_probe.py`）**（詳細版見 `FUT_LOG.md` 本輪條目、`FUT_CONTINUOUS_CONTRACT_DESIGN.md`「累積漂移幅度」章節）：
- **重要修正，不是好消息**：漂移幅度遠比原設計文件假設的「影響很小」要大——樣本起點（2000-01-04，全部300次轉倉累積調整後）`adj_close` 只剩真實同日 `close` 的約30%（`pct_diff = -70.4%`）。`corr(days_back, |pct_diff|)` = 0.9825，幾乎完美單調，是系統性偏態、不是隨機雜訊。全樣本83.5%的交易日 `|pct_diff| > 10%`。
- **但同時證實：報酬率本身未受汙染。** 逐日核對 `adj_close` vs `close`（原始未調整）的百分比變動，全樣本6185天中差異只出現在296天（精確對應300次轉倉事件的絕大多數），**非轉倉日差異天數 = 0**。原設計文件「轉倉點的報酬率是連續、無跳空的」這個核心主張站得住腳。
- **對候選策略清單的意涵**：短中期回看窗口（多時間框架趨勢、突破、均線系統、日內均值回歸——第3節候選全部屬於這類）可以安全使用 `adj_close`。但任何未來用到很長回看窗口（跨十幾次以上轉倉）或絕對點位判斷的測試，要另外注意這個已量化的漂移風險，不能假設「反正是報酬率導向就沒事」。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：地基已完備，開始照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化測期貨因子（多時間框架趨勢、突破 Donchian channel、波動 regime 過濾、均線系統、日內均值回歸、期現價差、三大法人期貨部位、未平倉量變化、隔夜 vs 日內報酬、星期效應、盤別效應）。**一輪最多測2–3個假說，用便宜關卡先篩（IC 測試/樣本內對隨機控制組），不要一次做完整驗證**（`MARATHON_PROTOCOL.md` 1a）。建議從「多時間框架趨勢」或「突破 Donchian channel」開始，這兩個是最基本、最容易先建立測試框架（例如仿照 `factor_ic.py` 精神寫一支期貨策略版的便宜關卡腳本）的候選。
2. （較低優先，不擋路）用 FinMind 官方欄位文件或另外查證確認 `after_market`＝夜盤的推論是否正確（目前只是起始日期吻合的間接證據）。
3. （較低優先，不擋路）本輪發現的開放問題：這個系統性漂移的經濟成因未拆解（新合約系統性相對舊合約偏低/偏高的價差本身是什麼原因造成的，可能跟台股高股息殖利率、期現貼水有關）——可以另立為一個獨立假說排進候選清單，但不急。
4. （較低優先）若之後有策略需要用到夜盤資料，才需要把 `after_market` session 也納入連續合約建構——目前候選策略清單用日頻資料即可，不急。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。本輪全程只讀本機 parquet 快取，沒有任何網路請求。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `continuous_contract.py`／`fut_drift_probe.py` 本身的 docstring 了解連續合約序列的介面跟漂移驗證方法，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解設計決策全貌（現在包含漂移幅度的完整量測結果，地基章節已標記完成）。**開始測因子/策略時，先確認回看窗口長度合理（不要憑空假設；有需要可以直接呼叫 `fut_drift_probe.py` 的邏輯查特定窗口長度的漂移量級），並比照 `TW_MARATHON_STATE.md`／`US_MARATHON_STATE.md` 的先例，判定結果記進 `TRIALS_LEDGER.md`（累積總帳）跟 `FUT_LEADS.md`（本軌候選）。**
