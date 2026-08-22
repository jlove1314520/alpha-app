# REPORT.md — append-only 主日誌

「Session 是消耗品，檔案才是本體」：這份檔案是這個專案唯一不會因為換 session、換機器、換 agent 而消失的執行記錄。

**規則：**
- **只往下 append，不覆寫、不刪除舊條目。** 發現舊條目寫錯了，加一條新的訂正，不要回頭改。
- 每條目格式：`## <ISO 8601 時間戳> — <一行摘要>`，內容至少包含「做了什麼」跟「驗證結果」兩項——沒驗證過的事不能寫得像驗證過。
- 這份檔案記的是**顆粒度細的單一動作**（一個函式寫完測完、一個 bug 修好、一次資料驗證）。里程碑等級的敘事跟決策脈絡記在 [`STRATEGY_LOG.md`](./STRATEGY_LOG.md)；現在整體卡在哪、下一步是什麼，看 [`MARATHON_STATE.md`](./MARATHON_STATE.md)——換 session 接手時**先看 MARATHON_STATE.md**，這份是給「我怎麼走到這裡」找細節用的。
- 策略候選的最終判定記在 [`LEADS.md`](./LEADS.md)，不要跟一般開發記錄混在一起。

---

## 2026-08-22T11:00:00+08:00 — 建立檔案紀律本身（REPORT / LEADS / MARATHON_STATE / audit_ledgers.py）

**做了什麼：** 依使用者指示，把「session 是消耗品，檔案才是本體」的紀律正式建成四樣東西：
- 本檔案（`REPORT.md`）
- `LEADS.md`：策略候選登記簿，目前是空的（還沒有策略候選——里程碑 2 驗證框架都還沒接成能跑的骨架，鐵律規定框架完成前不挖策略）
- `MARATHON_STATE.md`：斷點狀態檔，內容是這個時間點專案的完整快照
- `audit_ledgers.py`：唯讀稽核腳本，目前有 2 條恆等式（每個平倉都有對應進場記錄、沒有 NaN 價格/股數），對著空的 `trades.csv`（還沒有任何交易，schema 先定義好）跑，全部 PASS（因為沒資料可違反，不是因為邏輯有問題——已用合成的壞資料手動驗證過這兩條檢查真的抓得到問題）。

**驗證結果：**
- `audit_ledgers.py` 對空 ledger 跑：兩條檢查都 PASS，0 筆交易。
- 用合成資料驗證檢查邏輯本身有效：故意造一筆「平倉但 entry_trade_id 指到不存在的 trade_id」的假資料，`check_every_position_has_entry` 正確抓到；故意造一筆 `price=NaN` 的假資料，`check_no_nan_prices` 正確抓到。（驗證腳本跑完即丟棄，沒有寫進 `trades.csv`，維持 ledger 乾淨。）

**下一步：** 見 `MARATHON_STATE.md`。
