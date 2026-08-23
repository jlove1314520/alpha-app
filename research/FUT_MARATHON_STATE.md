# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T21:35:00+08:00**（馬拉松第九輪期貨軌執行後）

**地基狀態：🟢 連續合約建構程式碼首版已完成（`continuous_contract.py`），並用單一次轉倉的手算數學驗證過正確性；轉倉時點規則（H1）、資料欄位品質（`settlement_price`/`open_interest`/`institutional_investors`）都已釐清。剩下唯一未驗證的地基項目是比價法多次轉倉後的累積漂移幅度。** 詳見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪完成：`continuous_contract.py`（單一合約序列銜接首版）**（詳細版見 `FUT_LOG.md` 本輪條目）：
- 關鍵簡化發現：「當天有資料的合約中 `contract_date` 最小者」這個定義本身就自動等於 H1 轉倉——到期合約結算日隔天會直接從 `TaiwanFuturesDaily` 消失，不需要額外寫「今天是不是結算日」的判斷邏輯。
- 全樣本（2000-2024）跑出 300 次轉倉事件、0 次因資料缺口跳過——跟上一輪 `fut_probe_rollover_h1_h2.py` 測的「300 個月結算週期」數字完全吻合，兩支獨立邏輯的腳本互相交叉驗證。
- 手算驗證 2024-06 那次轉倉：調整後序列在交界點的報酬率跟「假設新合約序列沒中斷過」的理論值完全吻合（`23548.338839/23801.853318 = 0.989349...` = `23129/23378`），數學上證實邏輯正確。
- 目前範圍：只做 `position` session（推測是日盤/日盤結算快照），`after_market`（推測夜盤）尚未納入，這是刻意的範圍限縮，寫在模組 docstring 裡，不是遺漏。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：實測比價法「連續多次轉倉後累積漂移幅度」（`FUT_CONTINUOUS_CONTRACT_DESIGN.md` 尚待驗證 #2）——用 `continuous_contract.py` 算出來的 `adj_close` 序列，跟同一天的真實現價（`close`，未調整）比較差距，看 2000-2024 全期間累積下來的漂移是否在合理範圍（理論上多頭市場期貨溢價會讓調整後價格逐漸偏離現價，這是比價法已知的副作用，要用真實資料量化幅度，不能只憑理論假設它「還好」）。
2. （較低優先，不擋路）用 FinMind 官方欄位文件或另外查證確認 `after_market`＝夜盤的推論是否正確（目前只是起始日期吻合的間接證據）。
3. （較低優先）若之後有策略需要用到夜盤資料，才需要把 `after_market` session 也納入連續合約建構——目前候選策略清單（多時間框架趨勢、突破、均線系統）用日頻資料即可，不急。
4. 地基（連續合約 + 漂移幅度驗證）都就緒之後，才開始照 `MARATHON_PROTOCOL.md` 第 3 節清單系統化測期貨因子（多時間框架趨勢、突破 Donchian channel、波動 regime 過濾、均線系統、日內均值回歸、期現價差、三大法人期貨部位、未平倉量變化、隔夜 vs 日內報酬、星期效應、盤別效應）。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。本輪全程只讀本機 parquet 快取，沒有任何網路請求。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `continuous_contract.py` 本身的 docstring 了解連續合約序列的介面（`build_continuous_series()` 回傳 `(series, skipped_events)`），再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解設計決策全貌。
