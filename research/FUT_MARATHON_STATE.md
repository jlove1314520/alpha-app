# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T14:31:00+08:00**（馬拉松第三輪期貨軌執行後）

**地基狀態：🟡 部分搭建（資料源確認可用，但欄位品質尚有兩個未解問題，還不能開始寫連續合約程式碼或測因子）。** 連續兩輪的 FinMind IP 封鎖本輪解除，`fut_probe_milestone1.py` 第一次呼叫就成功，兩個資料集都拿到真實資料。連續合約銜接方法的**設計決策**（第一輪完成）維持不變，見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`；轉倉時點規則（H1 結算日轉倉 vs H2 成交量交叉轉倉）**仍未驗證**——本輪雖然拿到資料，但因為 `contract_date` 混雜單一月份與價差合約、且抽樣視窗沒看到近月/次近月同時有非零成交量可比較，還不足以驗證，需要先解決下面的欄位品質問題再做。

**✅ FinMind API 封鎖已解除**：本輪（2026-08-23T14:31 左右）第一次呼叫 `TaiwanFuturesDaily`（data_id=TX, 2024-06-03~06-07）就成功，沒有再吃到 403。距離上一輪記錄的封鎖時間已經超過一小時。

**本輪確認的事實（詳細版見 `DATA.md` 第 6 節）：**
- `TaiwanFuturesDaily`、`TaiwanFuturesInstitutionalInvestors` 兩個資料集名稱**都確認正確可用**，`data_id="TX"` 正確。
- `TaiwanFuturesDaily` 歷史深度：**2000-01-04 ～ 2024-12-31，共 64,936 列**（含所有合約月份/價差列）。
- `TaiwanFuturesDaily` 的 `contract_date` **混雜單一月份合約（如 `202406`）跟價差合約（如 `202406/202407`）**，用之前要先過濾。
- ⚠️ **兩個未解問題，下一輪要先處理，不能跳過直接寫因子/連續合約程式碼**：
  1. `TaiwanFuturesDaily` 抽樣視窗裡 `settlement_price` 跟 `open_interest` 全部是 0，原因未知（session 因素？資料品質？視窗剛好？）。
  2. `TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位顯示為亂碼，不能拿來區分自營商/投信/外資。
- `trading_session` 在抽樣視窗只出現 `after_market`／`position` 兩種值，沒看到預期的日盤標籤，需要下一輪查更多天或查欄位文件才能確定資料集本身的 session 結構。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：查清楚 `settlement_price`/`open_interest` 是否真的恆為 0，或只是這次抽樣視窗/session 的巧合。方法：擴大日期視窗（例如抓一整個月）跟不同 `trading_session`（如果有找到日盤標籤的話），看是否出現非零值。如果確認某個 session（例如可能存在的「日盤」）才有非零未平倉量，記錄下來；如果全部視窗都是 0，記錄「這個欄位在 FinMind 這個資料集裡不可靠，需要另尋資料源」。
2. 查清楚 `institutional_investors` 亂碼問題的根因：檢查 `finmind_client.py` 抓資料時用的 encoding/decoding 邏輯（**只能參考，這是 research/ 底下的檔案不是凍結區，如果確定是這裡的問題可以直接修**），如果是 API 回傳本身就是這樣（不是這邊解碼出錯），改用「同一天固定出現幾種不重複值、順序穩定」的方式間接對應到自營商/投信/外資，並在 `DATA.md` 誠實記錄這是間接推斷不是官方文件確認。
3. 如果 1、2 都解決，才能開始驗證轉倉時點規則 H1 vs H2（需要近月+次近月的真實成交量資料互相比較）。
4. 待轉倉規則確定，才動手寫連續合約建構程式碼（不是這一輪，也可能不是下一輪，看進度）。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `DATA.md` 第 6 節看資料集欄位細節，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約的設計決策跟尚待驗證項目。
