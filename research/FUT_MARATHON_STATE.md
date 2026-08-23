# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T09:10:00+08:00**（馬拉松第六輪期貨軌執行後）

**地基狀態：🟢 兩個核心資料集品質已釐清可用（`TaiwanFuturesDaily` 的 `settlement_price`/`open_interest`，以及 `TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位都已解決），但連續合約的**轉倉時點規則**（H1 結算日 vs H2 成交量交叉）仍未驗證，還不能開始寫連續合約建構程式碼或用三大法人期貨部位測因子。** 連續合約銜接方法的**設計決策**（第一輪完成）維持不變，見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪解決：`institutional_investors` 亂碼問題**（詳細版見 `DATA.md` 第 6 節）：
- 之前看到的 `�~��`／`��H`／`�����` 是**顯示層假象，不是資料問題**——直接檢查 FinMind 回傳的原始 bytes，欄位值是標準 JSON `\uXXXX` escape（ASCII-safe），`requests.json()` 解析完全正確；問題出在之前的探測腳本用 `print(df.head())` 直接印到 Windows 終端機，終端機 codepage 不是 UTF-8 才顯示成亂碼。
- 把值寫進明確 `encoding="utf-8"` 的檔案再讀出來，確認三種值正確為：`外資`／`投信`／`自營商`，跟三大法人分類完全吻合。
- **`finmind_client.py` 不需要任何修改**——`_fetch()`/`load_dev()` 目前用 `resp.json()` 的寫法本來就是對的，這不是它的 bug。
- **給下一輪、給任何未來遇到疑似「亂碼」欄位的人的提醒**：先用「寫入明確 `encoding='utf-8'` 的檔案再讀」排除顯示假象，不要急著懷疑資料源或改解碼邏輯。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：驗證連續合約轉倉時點規則 H1（結算日轉倉）vs H2（近月/次近月成交量交叉轉倉）——需要用 `TaiwanFuturesDaily` 抓近月+次近月合約在同一段期間的真實成交量互相比較，看哪個時點的量能交叉點跟官方結算日對得上/對不上。這是連續合約建構前最後一個尚待驗證的地基項目。
2. 待轉倉規則確定，才動手寫連續合約建構程式碼（不是這一輪，也可能不是下一輪，看進度）。
3. （較低優先，不擋路）確認 `trading_session` 是否真的只有 `after_market`/`position` 兩種值——可以查 FinMind 官方欄位文件，或另外抽樣更多不同月份的窗口交叉確認，但這不影響 1、2 的推進，可以晚一點再做。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪確認 `is_holdout_consumed()` → `False`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `DATA.md` 第 6 節看資料集欄位細節，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約的設計決策跟尚待驗證項目。
