# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T15:38:00+08:00**（馬拉松第四輪期貨軌執行後）

**地基狀態：🟡 部分搭建（`TaiwanFuturesDaily` 欄位品質已釐清可用，但 `TaiwanFuturesInstitutionalInvestors` 分類欄位亂碼問題仍未解，還不能開始寫連續合約程式碼或測因子）。** 連續合約銜接方法的**設計決策**（第一輪完成）維持不變，見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`；轉倉時點規則（H1 結算日轉倉 vs H2 成交量交叉轉倉）**仍未驗證**——本輪解決了 `settlement_price`/`open_interest` 全零疑慮，但還沒有拿近月/次近月成交量做交叉驗證，下一輪如果 `institutional_investors` 問題也解決了才能開始。

**✅ 本輪解決：`settlement_price`／`open_interest` 全零疑慮**（詳細版見 `DATA.md` 第 6 節）：
- 把窗口從一週擴大到一整月（2024-06-01～06-30），過濾掉價差列後依 `trading_session` 分組，發現 `after_market`（113 列）恆為 0、`position`（114 列）幾乎全部非零。
- **結論：不是資料品質問題，是這兩欄只在 `trading_session == "position"` 才有值**，之前窄視窗沒有分組看才誤判為「全部是 0」。
- **下一輪／未來使用這兩欄時，一定要先篩 `position` session，不能整批直接用。**

**⚠️ 仍未解決（次要，本輪未觸碰，優先序調整見下）**：`trading_session` 拉到一整月窗口仍只看到 `after_market`／`position` 兩種值，沒有出現「日盤」標籤——證據比之前更一致地指向「這個資料集本來就只有這兩種 session」，但還沒到可以下定論的程度，先繼續標未確認，不影響 `settlement_price`/`open_interest` 的可用性結論（因為那個結論已經用 `position` session 篩選過，跟日盤/夜盤拆分與否無關）。

**⚠️ 仍未解決（優先項目，下一輪先做這個）**：`TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位仍是亂碼，不能拿來區分自營商/投信/外資。本輪未觸碰（一輪一個工作單位，本輪工作單位是上面的全零疑慮，已完成）。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：查清楚 `institutional_investors` 亂碼問題的根因：檢查 `finmind_client.py` 抓資料時用的 encoding/decoding 邏輯（**只能參考，這是 research/ 底下的檔案不是凍結區，如果確定是這裡的問題可以直接修**），如果是 API 回傳本身就是這樣（不是這邊解碼出錯），改用「同一天固定出現幾種不重複值、順序穩定」的方式間接對應到自營商/投信/外資，並在 `DATA.md` 誠實記錄這是間接推斷不是官方文件確認。
2. 如果 1 解決，才能開始驗證轉倉時點規則 H1 vs H2（需要近月+次近月的真實成交量資料互相比較，`TaiwanFuturesDaily` 這部分已經確認可用）。
3. 待轉倉規則確定，才動手寫連續合約建構程式碼（不是這一輪，也可能不是下一輪，看進度）。
4. （較低優先，不擋路）確認 `trading_session` 是否真的只有 `after_market`/`position` 兩種值——可以查 FinMind 官方欄位文件，或另外抽樣更多不同月份的窗口交叉確認，但這不影響 1、2、3 的推進，可以晚一點再做。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `DATA.md` 第 6 節看資料集欄位細節，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約的設計決策跟尚待驗證項目。
