# FUT_LOG.md — 期貨軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面）。期貨軌是全新的，這份檔案從第一輪馬拉松開始就是期貨軌唯一的執行記錄。

**規則：** 每個馬拉松輪次結束前 append 一條，包含地基搭建進度（期貨軌前期主要是這個，尤其連續合約銜接方法的決定過程）跟之後的策略測試結果，不管有沒有進展都要記錄。

---

## 2026-08-23T02:00:00+08:00 — 期貨軌馬拉松初始化

檔案建立，尚未有實際輪次執行。地基完全未搭建，第一輪工作見 `FUT_MARATHON_STATE.md`。

---

## 2026-08-23T11:52:00+08:00 — 馬拉松第一輪期貨軌執行：連續合約設計決策 + FinMind 額度撞牆

**選軌理由**：`marathon_lock.py acquire` 成功後比對 `TW_MARATHON_STATE.md`（09:50）／`US_MARATHON_STATE.md`（10:30）／`FUT_MARATHON_STATE.md`（02:00，最舊）三個最後更新時間戳，選最久沒被碰的期貨軌。

**做了什麼**：
1. 依 `MARATHON_PROTOCOL.md` 第 5 節「第一輪建議工作單位」第 3 項，嘗試打 FinMind API 探測 `TaiwanFuturesDaily`（台指期日線）資料集可用性。`curl` 第一次回傳 `402 Requests reach the upper limit`（約 11:47 左右）。等 5 秒後重試一次，回傳惡化為 `403 ip banned, retry_after=1782`（約 30 分鐘封鎖，約 11:47:30 左右發生）。**沒有再重試第三次**，符合 `MARATHON_PROTOCOL.md` 第 4 節「不要為了硬跑而狂重試」的規則。
2. 因為 API 被封鎖，資料探測（第 5 節第 1、2 項工作）這輪做不了，改做不需要網路的第 3 項：設計連續合約銜接方法。寫成新檔案 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`：比較比價法/價差調整法/不調整直接拼接三種方法，決定用**比價法為主+永遠保留原始未調整近月價格當真相**（架構精神比照 `adjust.py`），理由是本軌候選策略清單全部是報酬率導向、TX 指數不會跨零所以比價法數值安全。轉倉時點規則列了兩個對照假說（H1 結算日轉倉、H2 成交量交叉轉倉）但**沒有驗證**，因為驗證需要真實近月/次近月成交量資料，這輪拿不到。
3. 更新 `FUT_MARATHON_STATE.md`：記錄 API 封鎖狀態（含 `retry_after`）、連續合約設計決策已完成、資料集名稱`TaiwanFuturesDaily`還沒實際驗證過是否正確、下一輪建議先做資料探測（`fut_probe_milestone1.py`，比照 US 軌 `us_probe_milestone1.py` 的精神）。

**沒做的事**：沒有測任何策略假說（地基連資料都還沒有，不到能測策略的階段）；沒有寫連續合約建構程式碼（設計決策做完，程式碼刻意留給資料驗證完之後）；`TRIALS_LEDGER.md` 沒有新增列——本輪不是「測了一個假說但沒過」，是「連測都還沒到那一步」，比照 `TRIALS_LEDGER.md` 開頭說明的「調查後發現連測都不能測」不計入原則，這裡是「調查途中撞到額度牆」，同樣不算一次可統計檢定的試驗，不計入。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目 1（FinMind 額度恢復後的資料探測）。
