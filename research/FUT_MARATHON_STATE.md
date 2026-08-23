# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-23T11:52:00+08:00**（馬拉松第一輪期貨軌執行後）

**地基狀態：❌ 仍未搭建（本輪未取得任何真實期貨資料）。** 本輪完成了連續合約銜接方法的**設計決策**（不需要 API 資料的部分），見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`：決定用比價法（ratio back-adjustment）當回測用連續序列，同時強制保留原始未調整近月價格當真相來源，架構精神比照 `adjust.py`。**轉倉時點規則（結算日轉倉 vs 成交量交叉轉倉）尚未驗證，需要真實近月/次近月成交量資料才能判斷**——本輪未能取得，見下方。

**⚠️ FinMind API 目前被封鎖（本輪踩到的地雷，下一輪要先看這個）：**
- 本輪嘗試 `curl` 直接打 `https://api.finmindtrade.com/api/v4/data?dataset=TaiwanFuturesDaily&...`，第一次回傳 `402 Requests reach the upper limit`，等 5 秒重試一次後回傳 `403 ip banned, retry_after=1782`（約 30 分鐘，發生時間 2026-08-23T11:4x+08:00 左右，精確時間見 `FUT_LOG.md`）。
- **下一輪如果距離上次 403 發生時間不到約 30 分鐘，第一次呼叫 FinMind 前要有心理準備可能還在封鎖窗口內，不要一失敗就連續重試**（`MARATHON_PROTOCOL.md` 第 4 節本來就禁止狂重試，這裡是本輪實際踩到的具體案例，記下來給下一輪參考）。
- 注意：這個封鎖可能是 FinMind 對這個網路環境（IP）共用的全站額度限制，不是期貨軌專屬——如果 TW/US 軌下一輪也連續打 FinMind API，可能會遇到同一個問題，值得留意。
- 另外，`TaiwanFuturesDaily` 是否是正確的資料集名稱，本輪一次都沒成功呼叫過，**還沒確認過**，不能假設它就是對的名稱，下一輪額度恢復後第一件事是先確認資料集名稱正確性。

**已知資訊（避免重複調查）：**
- TAIFEX 期貨資料是 CSV 格式，**開頭有 BOM，編碼要注意**（`CLAUDE.md` 已記錄的地雷，直接沿用）——這條是官方 TAIFEX 網站直接下載 CSV 時的地雷，如果改走 FinMind API 則不適用（FinMind 回傳的是 JSON，不是 CSV）。
- `CLAUDE.md` 提過既有資料源「期貨（TAIFEX CSV）」跟「三大法人期貨部位（TAIFEX 資料源）」，這是 `alpha-data/fetch.py`（凍結區）已經在用的端點分類，**具體 URL/端點格式要自己重新查證，不能假設 `research/` 這邊能直接沿用凍結區的程式碼**（那是凍結區，只能參考、不能動用或複製）。
- `FUT_LEADS.md` 先前記錄過 FinMind 三大法人期貨部位資料集名稱可能是 `TaiwanFuturesInstitutionalInvestors`——**這個名稱本輪也還沒實測驗證過，只是先前留下的線索，不是已確認的事實**。
- **連續合約銜接方法：已做設計決策**（比價法為主+保留原始價格），完整推理見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。轉倉時點規則還沒定案，列了兩個對照假說（結算日轉倉 H1 vs 成交量交叉轉倉 H2），需要真實資料才能驗證。
- 完全沒有連續合約建構的**程式碼**——設計決策已做完，程式碼還沒寫（`MARATHON_PROTOCOL.md` 明確要求先設計再寫程式碼，這輪只做到前半）。

**下一輪建議工作單位（只做其中一項）：**
1. **優先**：FinMind 額度恢復後，先用一小段日期範圍（例如一週）試打 `TaiwanFuturesDaily`（或查證後的正確資料集名稱）跟 `TaiwanFuturesInstitutionalInvestors`，確認資料集名稱、欄位結構（是否有近月/次近月分開的合約月份欄位）、歷史深度——比照 `DATA.md` 里程碑1、`us_probe_milestone1.py` 的驗證方式，寫一支 `fut_probe_milestone1.py`，實測結果記錄回 `DATA.md`。
2. 如果 1 做完且時間還夠：用抓到的近月+次近月成交量資料，驗證轉倉時點規則 H1（結算日轉倉）vs H2（成交量交叉轉倉）哪個更符合台指期實際流動性轉移型態，把結論寫回 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 的「尚待驗證」章節（驗證完就不再是待驗證，要更新狀態）。
3. 待 1、2 都完成、轉倉規則確定後，才動手寫連續合約建構程式碼（不是這一輪，也可能不是下一輪，看進度）。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約的設計決策跟尚待驗證項目。
