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

---

## 2026-08-23T13:02:00+08:00 — 馬拉松第二輪期貨軌執行：仍被 FinMind 封鎖，第二次撞牆

**選軌理由**：`marathon_lock.py acquire` 成功後比對 `TW_MARATHON_STATE.md`（12:08）／`US_MARATHON_STATE.md`（12:32）／`FUT_MARATHON_STATE.md`（11:52，最舊）三個最後更新時間戳，選最久沒被碰的期貨軌。

**做了什麼**：
1. 距離上一輪記錄的 403（2026-08-23T11:47:30+08:00，`retry_after=1782`≈30分鐘，理論解封時間約 12:17）已經過了超過 40 分鐘，判斷應該已解封，寫了 `fut_probe_milestone1.py`（比照 `us_probe_milestone1.py` 的結構：一支只印結果、不改其他檔案的探測腳本），對 `TaiwanFuturesDaily`（data_id=`TX`）用一週窄視窗（2024-06-03~06-07）跑 `load_dev()`。
2. 實際執行結果：**仍然是 403**，`{"msg":"ip banned","status":403,"retry_after":828}`（2026-08-23T13:01:40+08:00）。只呼叫了這一次，沒有重試（`MARATHON_PROTOCOL.md` 第 4 節規則）。
3. 這代表封鎖視窗比預期的更持久或會重新計時——不是「等滿 30 分鐘就一定解封」這麼單純。已把這個發現寫進 `FUT_MARATHON_STATE.md`，提醒下一輪心理準備。

**沒做的事**：`TaiwanFuturesInstitutionalInvestors` 探測、轉倉規則驗證（H1/H2）、連續合約程式碼——全部因為第一步 `TaiwanFuturesDaily` 就被拒絕而擋在前面，沒有機會執行到。`TRIALS_LEDGER.md` 沒有新增列，理由同第一輪：這是資料源可用性調查途中撞到額度牆，不是完成一次可統計檢定的假說測試。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目 1——`fut_probe_milestone1.py` 已經寫好可直接執行，等過了本輪記錄的 `retry_after`（約 2026-08-23T13:15:28+08:00 之後）再試。

---

## 2026-08-23T14:31:00+08:00 — 馬拉松第三輪期貨軌執行：封鎖解除，兩個資料集首次成功探測

**選軌理由**：`marathon_lock.py acquire` 成功後比對 `TW_MARATHON_STATE.md`（13:30）／`US_MARATHON_STATE.md`（13:35）／`FUT_MARATHON_STATE.md`（13:02，最舊）三個最後更新時間戳，選最久沒被碰的期貨軌。

**做了什麼**：
1. 確認系統時間（14:31）已遠超過上一輪記錄的預估解封時間（13:15:28），直接執行上一輪已寫好的 `fut_probe_milestone1.py`（不重寫探測邏輯，比照協定第 1c 節精神）。
2. **第一次呼叫就成功**，沒有再吃到 403。`TaiwanFuturesDaily`（data_id=TX）跟 `TaiwanFuturesInstitutionalInvestors`（data_id=TX）兩個資料集名稱**都確認正確可用**。歷史深度檢查確認 `TaiwanFuturesDaily` 涵蓋 2000-01-04～2024-12-31，共 64,936 列。
3. 檢視回傳資料時發現兩個需要下一輪處理的品質問題：(a) `TaiwanFuturesDaily` 的 `contract_date` 混雜單一月份合約跟價差合約在同一表；抽樣視窗裡 `settlement_price`／`open_interest` 全部是 0，原因未查；(b) `TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位是亂碼，還不能拿來區分自營商/投信/外資。這兩點**沒有硬猜或跳過**，誠實記錄為待解問題，寫進 `DATA.md` 第 6 節（新增章節）跟 `FUT_MARATHON_STATE.md`。
4. 沒有進一步深挖這兩個問題的根因（例如去改 `finmind_client.py` 的解碼邏輯），因為協定要求「一輪一個有界工作單位」，本輪的工作單位是「確認資料集可用性」，已經達成；根因調查留給下一輪（`FUT_MARATHON_STATE.md` 已列為優先項目 1、2）。

**沒做的事**：轉倉時點規則 H1/H2 驗證（需要先解決欄位品質問題才能可靠比較近月/次近月成交量）、連續合約建構程式碼、任何因子/策略假說測試——這些都還在「地基未完全搭好」階段，`TRIALS_LEDGER.md` 沒有新增列（同前兩輪理由：這是資料源可用性/品質調查，不是完成一次可統計檢定的假說測試）。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目 1（查清楚 `settlement_price`/`open_interest` 是否恆為 0）。

---

## 2026-08-23T15:38:00+08:00 — 馬拉松第四輪期貨軌執行：`settlement_price`/`open_interest` 全零疑慮解除

**選軌理由**：`marathon_lock.py acquire` 成功後比對 `TW_MARATHON_STATE.md`（15:05）／`US_MARATHON_STATE.md`（15:35）／`FUT_MARATHON_STATE.md`（14:31，最舊）三個最後更新時間戳，選最久沒被碰的期貨軌。

**做了什麼**：
1. 依上一輪優先項目 1，寫了新探測腳本 `fut_probe_settlement_oi.py`（不改動 `fut_probe_milestone1.py`），把窗口從一週擴大到一整月（`TaiwanFuturesDaily`，data_id=TX，2024-06-01～06-30），過濾掉 `contract_date` 含 `/` 的價差列（只留單一月份合約，227 列），依 `trading_session` 分組統計 `settlement_price`/`open_interest` 的零值/非零值列數。
2. **結果**：`after_market`（113 列）兩欄恆為 0；`position`（114 列）幾乎全部非零（113/114 `settlement_price` 非零、114/114 `open_interest` 非零）。**結論：不是資料品質問題，是這兩欄語意上只在 `position` session（推測是盤後結算/未平倉揭露快照）才有值，`after_market` 本身就不含這兩欄的資料**——上一輪窄視窗誤判「全部是 0」是因為沒有按 `trading_session` 分組看。
3. 把結論寫進 `DATA.md` 第 6 節（含「下一輪使用這兩欄前務必先篩 `position` session」的提醒）跟 `FUT_MARATHON_STATE.md`。同時誠實記錄一個附帶觀察：即使窗口拉到一整月，`trading_session` 仍然只出現 `after_market`/`position` 兩種值，沒有看到「日盤」標籤——這個附帶問題**沒有下定論**（證據比之前更一致但還不到能確認的程度），標為低優先、不擋路的待查項目，跟已解決的全零疑慮分開處理，不能混為一談。

**沒做的事**：`institutional_investors` 亂碼問題（下一輪優先項目 1，本輪一個工作單位只處理一項，已達成本輪目標）、轉倉時點規則 H1/H2 驗證、連續合約建構程式碼。`TRIALS_LEDGER.md` 沒有新增列——這是資料欄位品質調查，不是完成一次可統計檢定的假說測試，理由同前三輪。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目 1（`institutional_investors` 亂碼根因調查）。

---

## 2026-08-24T09:10:00+08:00 — 馬拉松第六輪期貨軌執行：`institutional_investors` 亂碼根因調查（已解決，不是編碼問題）

**工作單位**：上一輪列的優先項目 1——查清楚 `TaiwanFuturesInstitutionalInvestors` 的 `institutional_investors` 分類欄位亂碼問題根因。

**做了什麼**：
1. 寫了 `fut_probe_institutional_encoding.py`，直接用 `requests.get` 呼叫 FinMind API（同一個已探測過的窗口 2024-06-03～06-07，在 VAL_END=2024-12-31 之前，繞過 `finmind_client.py` 的 parquet 快取，因為快取裡已經是「解碼後」的值，要查根因得看最原始的 response bytes/headers）。
2. 檢查 `resp.headers['Content-Type']`（`'application/json'`，無 charset）、`resp.encoding`（requests 猜為 `'utf-8'`）、`resp.apparent_encoding`（chardet 猜為 `'ascii'`，這個線索很關鍵：如果原始 bytes 裡真的有 replacement character 那 chardet 應該猜不出 ascii）。
3. 直接印出原始 bytes 在 `institutional_investors` 欄位附近的內容，發現是 `"institutional_investors":"自營商"`——**這是標準 JSON `\uXXXX` escape，本身就是 ASCII-safe 純文字，跟任何多位元編碼（UTF-8/Big5/GB2312）猜測完全無關**，`自營商` 解出來就是「自營商」三個字。
4. 用 `resp.json()`（`requests` 內建，也是 `finmind_client._fetch()` 目前用的方法）解析，再把結果寫進**明確指定 `encoding='utf-8'` 的檔案**（不是印到終端機）再讀回來檢查——三個值正確顯示為 `外資`／`投信`／`自營商`，跟三大法人分類完全吻合，不再是間接推斷。
5. 也用 `finmind_client.load_dev()`（走 parquet 快取的正式路徑）重複同一個檢查，確認快取寫入/讀出的過程也沒有引入任何損壞。

**結論**：`institutional_investors` 從頭到尾都沒有壞——FinMind 回傳的資料是對的，`requests.json()` 解析是對的，`finmind_client.py` 現有寫法也是對的，**完全不需要改任何程式碼**。之前看到的 `�~��`／`��H`／`�����` 亂碼，根因是 `fut_probe_milestone1.py` 用 `print(df.head())` 把記憶體裡完全正確的 Unicode 字串直接印到 Windows 終端機，而終端機的 codepage 不是 UTF-8，才在**顯示層**把正確字元換成 `�`——資料本身從來沒有被污染過。這是一個顯示層陷阱，不是資料層問題，已經把這個排查方法（寫入明確 UTF-8 檔案再讀）記進 `DATA.md` 第 6 節，供以後遇到類似「疑似亂碼」欄位時優先排除顯示假象。

**地基狀態更新**：`TaiwanFuturesDaily`（`settlement_price`/`open_interest`）跟 `TaiwanFuturesInstitutionalInvestors`（`institutional_investors` 分類）兩個資料集的欄位品質疑慮都已解除，期貨軌地基推進到「只剩轉倉時點規則未驗證」的階段。

**沒做的事**：轉倉時點規則 H1（結算日）vs H2（成交量交叉）驗證、連續合約建構程式碼——這兩項本來就排在 `institutional_investors` 解決之後，本輪一個工作單位只處理一項，已達成本輪目標。`TRIALS_LEDGER.md` 沒有新增列——這是資料欄位品質調查（顯示層 bug 排查），不是完成一次可統計檢定的假說測試，理由同前幾輪的地基調查記錄。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目 1（轉倉時點規則 H1 vs H2 驗證，需要近月/次近月真實成交量互相比較）。

---

## 2026-08-24T20:05+08:00（馬拉松第七輪期貨軌，`fut_probe_rollover_h1_h2.py`）

**這一輪工作單位**：驗證 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 列的轉倉時點規則假說 H1（結算日轉倉）vs H2（成交量交叉轉倉）——這是連續合約建構前最後一個尚待驗證的地基項目。

**這一輪實際發生的事**：
1. 先用窄窗口（`2024-05-15`～`2024-07-15`）打 `load_dev("TaiwanFuturesDaily", "TX", ...)`，第一次呼叫就回 `HTTP 402`（額度用盡）。**沒有重試**（遵守協定第4節，`_fetch()` 本身已經有重試邏輯，不再上層包重試迴圈）。
2. 發現 `research/data/raw/` 早就有前幾輪留下的完整歷史快取 `TaiwanFuturesDaily__TX__2000-01-01__2024-12-31.parquet`（64,936 列）。改用跟這個快取檔案**完全相同的鍵值**（`start_date=2000-01-01, end_date=2024-12-31`）呼叫 `load_dev()`，直接命中快取、**零額外 API 呼叫**，再自行在記憶體裡切窗口分析。這個技巧本身值得記下來：額度用盡時先查有沒有既有快取可以重用，不只省額度，往往還能做比原計畫更完整的分析。
3. 利用這個零成本的全歷史快取，把驗證範圍從原本規劃的單一窗口（2 個月、1-2 個結算週期）擴大成**全部 300 個月結算週期（2000-2024）**：對每個結算日（第三個星期三），檢查結算日前 10 個交易日內是否曾出現「次近月成交量 > 近月成交量」（比較前兩個日曆月合約，不是量能最大的兩個合約，避免誤把遠月投機量算進來）。
4. 依 `trading_session` 分組分析：
   - `after_market`（資料從 2017-05-16 才開始，92 個可測結算週期）：**0 次**超車。
   - `position`（2000-2024 全期間，300 個可測結算週期）：45 次（15.0%）超車，但**49 個實際超車日全部集中在結算日前 1～2 個日曆天**（45 次結算日前1天、4 次結算日前2天，**沒有任何一次發生在更早的時間點**）。

**結論：採用 H1**——「結算日前 1～2 天量能超車」的型態正好符合 H1（結算日附近自然轉倉）本身就會產生的現象，不是 commodity CTA 文獻描述的那種提前數天/數週的獨立 H2 現象。已寫進 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`「轉倉時點規則」章節，該文件原本列的「尚待驗證 #1」標記為已解決。

**附帶發現**：`after_market` session 資料起始日（2017-05-16）跟 TAIFEX 夜盤上線日（2017-05-15）幾乎完全吻合，高信心推論 `after_market`＝夜盤、`position`＝日盤（或日盤結算快照）。**這是間接推論（起始日期吻合），不是官方文件確認**，已同步更新 `DATA.md` 第 6 節，把「`trading_session` 只有兩種值」的疑慮從「完全未知」降級為「高信心推論、未經官方文件驗證」。

**沒做的事**：連續合約建構程式碼本身（比價法回溯調整實作）、多次轉倉後的累積漂移幅度實測——這兩項排在轉倉規則確定之後，本輪一個工作單位只處理規則驗證本身，符合本輪目標。`TRIALS_LEDGER.md` 沒有新增列——這是連續合約設計的地基驗證（規則選擇），不是可統計檢定的因子/策略假說測試，理由同前幾輪的地基調查記錄（`institutional_investors` 亂碼排查那次的先例）。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。全程只用 `load_dev()`，本輪唯一一次網路請求（窄窗口那次）也是 402 失敗未取得任何資料，之後全部改讀本機快取，沒有任何管道能碰到 holdout。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目改為寫連續合約建構程式碼（比價法回溯調整，套用本輪確定的 H1 轉倉規則），並實測累積漂移幅度。
