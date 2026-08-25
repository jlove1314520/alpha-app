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

---

## 2026-08-24T23:03+08:00（馬拉松第42輪期貨軌，`fut_cheap_gate.py`新增兩個假說）

**選軌理由**：`marathon_lock.py acquire` 回傳 `LOCK_STALE`（上一輪pid 120808持有鎖滿30分鐘後被回收，疑似上一輪異常中止未留下正常結束的log；比對三軌state檔案時間戳，`TW_MARATHON_STATE.md`22:01／`US_MARATHON_STATE.md`22:37／`FUT_MARATHON_STATE.md`21:19，期貨軌最舊，選期貨軌）。

**這一輪工作單位**：依`FUT_MARATHON_STATE.md`「下一輪建議工作單位」優先項目1，接手第39輪剛補齊地基的三大法人期貨部位資料，測`fut_institutional_net_position`類假說。第一批只測外資（三大法人期貨部位中最具流動性、台股散戶文化裡最常被當「聰明錢」追蹤的類別），投信/自營商留給之後的輪次，避免一輪把「三大法人期貨部位有沒有訊號」跟「哪個類別」混在一起測。

**做了什麼**：
1. 在`fut_cheap_gate.py`新增`_load_institutional_net_position()`（inner join `build_continuous_series()`輸出跟`TaiwanFuturesInstitutionalInvestors`外資類別的`long_open_interest_balance_volume - short_open_interest_balance_volume`淨部位，inner join天然把樣本限制在1605天，2018-06-05起，跟已知的資料源起始限制一致）跟兩個假說函式：
   - `fut_inst_foreign_net_position_sign`（水位假說：淨部位方向本身當訊號）
   - `fut_inst_foreign_net_position_change_5d`（動能假說：淨部位5日變化方向當訊號，跟水位假說互相獨立可證偽）
2. 全歷史快取（`TaiwanFuturesInstitutionalInvestors__TX__2000-01-01__2024-12-31.parquet`）跟`TaiwanFuturesDaily`全歷史快取在第39/7輪已經存在，本輪呼叫`load_dev()`用完全相同的鍵值，**零額外API呼叫**，全程只讀本機parquet快取。
3. 執行結果：
   - `fut_inst_foreign_net_position_sign`：n_days=1605，真實策略終值+17.7%累積，隨機控制組中位數+6.4%，percentile=57.5（門檻90.0）→ **FAIL**。
   - `fut_inst_foreign_net_position_change_5d`：n_days=1600（5日diff少5筆），真實策略終值+110.9%累積，隨機控制組中位數-15.1%，percentile=97.0（單測門檻90.0過；本批n=2校正門檻95.0過）→ **CHEAP_PASS（批次）**。
4. **累積多重比較校正（`MARATHON_PROTOCOL.md`第2節，本輪新增2列後`TRIALS_LEDGER.md`總數21→25，bonferroni_n=25，門檻99.6）**：`fut_inst_foreign_net_position_change_5d`的97.0百分位遠不及99.6，判定降級為「CHEAP_PASS（批次），累積校正後降級為不確定，不排入深挖清單」——跟`TRIALS_LEDGER.md`#14（`f_value_pe`）同款「原本通過，累積校正後不再確定」情形，沒有悄悄跳過這個降級。這是本輪唯一新增的候選，暫不進深挖清單；若要重新檢驗需要先把`N_SHUFFLES`從200加密（例如→1000+）才能判斷是否真的能跨過門檻，因為200次排列的解析度只到0.5%，最接近99.6的可達成值只有99.5/100.0。
5. `TRIALS_LEDGER.md`新增#24/#25、`FUT_LEADS.md`新增#7/#8、`FUT_MARATHON_STATE.md`更新。

**沒做的事**：投信/自營商兩個類別的水位/動能假說（下一輪可以直接沿用`_load_institutional_net_position()`換`category`參數，不用重寫）；`N_SHUFFLES`加密重測`fut_inst_foreign_net_position_change_5d`（留待下一輪視優先序決定，需要先評估時間預算）。

**Holdout 檢查**：開始前跟結束前都跑`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。全程只讀本機parquet快取，沒有任何網路請求。

**下一輪**：見`FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目1（投信/自營商類別的水位/動能假說）。

**附帶發現**：`after_market` session 資料起始日（2017-05-16）跟 TAIFEX 夜盤上線日（2017-05-15）幾乎完全吻合，高信心推論 `after_market`＝夜盤、`position`＝日盤（或日盤結算快照）。**這是間接推論（起始日期吻合），不是官方文件確認**，已同步更新 `DATA.md` 第 6 節，把「`trading_session` 只有兩種值」的疑慮從「完全未知」降級為「高信心推論、未經官方文件驗證」。

**沒做的事**：連續合約建構程式碼本身（比價法回溯調整實作）、多次轉倉後的累積漂移幅度實測——這兩項排在轉倉規則確定之後，本輪一個工作單位只處理規則驗證本身，符合本輪目標。`TRIALS_LEDGER.md` 沒有新增列——這是連續合約設計的地基驗證（規則選擇），不是可統計檢定的因子/策略假說測試，理由同前幾輪的地基調查記錄（`institutional_investors` 亂碼排查那次的先例）。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。全程只用 `load_dev()`，本輪唯一一次網路請求（窄窗口那次）也是 402 失敗未取得任何資料，之後全部改讀本機快取，沒有任何管道能碰到 holdout。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目改為寫連續合約建構程式碼（比價法回溯調整，套用本輪確定的 H1 轉倉規則），並實測累積漂移幅度。

---

## 2026-08-25T05:02+08:00（馬拉松第45輪期貨軌，`fut_cheap_gate.py`新增兩個假說）

**選軌理由**：`marathon_lock.py acquire` 乾淨回傳`LOCK_ACQUIRED`（無陳舊鎖檔）。比對三軌state檔案時間戳：`TW_MARATHON_STATE.md`2026-08-25T00:00、`US_MARATHON_STATE.md`2026-08-25T04:31、`FUT_MARATHON_STATE.md`2026-08-24T23:03，期貨軌最舊，選期貨軌。

**這一輪工作單位**：依`FUT_MARATHON_STATE.md`「下一輪建議工作單位」優先項目1，接手三大法人期貨部位家族第二個類別——投信（第42輪只測了外資，投信/自營商留給後續輪次）。只測投信，自營商留給下一輪，維持`MARATHON_PROTOCOL.md`1a每輪2-3個假說上限，也跟第42輪先例（一輪只測一個新類別）保持一致，避免一輪把「這個類別有沒有訊號」跟「另一個類別」混在一起測。

**做了什麼**：
1. 在`fut_cheap_gate.py`新增兩個假說函式，沿用第42輪已寫好的`_load_institutional_net_position()`，只換`category="投信"`參數，不需要重寫地基：
   - `fut_inst_trust_net_position_sign`（水位假說：淨部位方向本身當訊號）
   - `fut_inst_trust_net_position_change_5d`（動能假說：淨部位5日變化方向當訊號）
2. 沿用第39輪已快取的`TaiwanFuturesInstitutionalInvestors`全歷史parquet（`load_dev()`用完全相同的鍵值），**零額外API呼叫**，全程只讀本機快取。
3. 執行結果：
   - `fut_inst_trust_net_position_sign`：n_days=1605，真實策略終值-49.7%累積，隨機控制組中位數-53.7%，percentile=41.5（門檻90.0）→ **FAIL**（方向不對，真實值雖也是負的但沒比隨機打散好）。
   - `fut_inst_trust_net_position_change_5d`：n_days=1600（5日diff少5筆），真實策略終值+150.2%累積，隨機控制組中位數+0.7%，percentile=96.5（單測門檻90.0過；本批n=2校正門檻95.0過）→ **CHEAP_PASS（批次）**。
4. **累積多重比較校正（`MARATHON_PROTOCOL.md`第2節，本輪新增2列後`TRIALS_LEDGER.md`總數25→27，bonferroni_n=27，門檻99.63）**：`fut_inst_trust_net_position_change_5d`的96.5百分位不及99.63，判定降級為「CHEAP_PASS（批次），累積校正後降級為不確定，不排入深挖清單」——跟`TRIALS_LEDGER.md`#25（外資動能假說）同款情形，沒有悄悄跳過這個降級。**值得記錄的觀察（不是結論）：外資（#25）跟投信（本輪#27）連續兩個類別的「淨部位5日動能」假說都出現同一種模式（單測/批次過、累積校正未過），可能暗示這個訊號家族本身邊際特性一致，也可能只是巧合，需要更多證據（例如自營商類別的結果，或N_SHUFFLES加密後的結果）才能判斷，不要在這輪就下結論。**
5. `TRIALS_LEDGER.md`新增#26/#27、`FUT_LEADS.md`新增#9/#10、`FUT_MARATHON_STATE.md`本輪更新。

**沒做的事**：自營商類別的水位/動能假說（下一輪可以直接沿用`_load_institutional_net_position()`換`category="自營商"`，三大法人期貨部位家族就三類別全覆蓋）；`N_SHUFFLES`加密重測兩個動能假說（留待下一輪視優先序決定，需要先評估時間預算）。

**Holdout 檢查**：開始前跟結束前都跑`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。全程只讀本機parquet快取，沒有任何網路請求。

**下一輪**：見`FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目1剩餘部分（自營商類別的水位/動能假說）。

---

## 2026-08-24T21:35:00+08:00 — 馬拉松第九輪期貨軌執行：連續合約建構程式碼首版完成（`continuous_contract.py`）

**選軌理由**：`marathon_lock.py acquire` 成功後比對 `TW_MARATHON_STATE.md`（21:05）／`US_MARATHON_STATE.md`（20:35）／`FUT_MARATHON_STATE.md`（20:05，最舊）三個最後更新時間戳，選最久沒被碰的期貨軌。

**這一輪工作單位**：`FUT_MARATHON_STATE.md`「下一輪建議工作單位」優先項目 1——開始寫連續合約建構程式碼（比價法回溯調整，套用上一輪確定的 H1 轉倉規則）。依協定第 1c/5b 節精神，只做「第一輪把單一合約序列銜接寫出來、用少數幾次轉倉手動驗證正確性」，不追求一次做完全部功能（累積漂移實測留到下一輪）。

**做了什麼**：
1. 用零額外 API 呼叫的既有全歷史快取（`TaiwanFuturesDaily__TX__2000-01-01__2024-12-31.parquet`）先做了一次資料探索：直接查 2024-06-17～06-21 這個真實區間，肉眼確認 `contract_date=202406`（近月合約）在 2024-06-19（June 2024 結算日，第三個星期三）當天仍有正常成交量的報價，隔天（06-20）完全從資料表消失、次近月 `202407` 自然接手成為量能最大的合約。這證實了一個重要簡化：**「當天有資料的合約中 `contract_date` 最小者」這個定義，本身就自動等於 H1（結算日轉倉）——不需要另外寫「今天是不是結算日」的判斷邏輯**，因為到期合約本來就會在結算日隔天直接從資料源消失。
2. 寫了 `continuous_contract.py`（精神上比照 `adjust.py` 對股票的做法：`load_position_session()` 只篩 `trading_session=="position"`、排除含 `/` 的價差合約列；`front_month_series()` 實作上述「當天最小 `contract_date`」規則；`rollover_events()` 在每次前月合約 ID 切換時，用**切換前一天**（新舊合約當天都還有報價的最後一天）的新舊合約收盤價算比價法調整比例；`build_continuous_series()` 把比例用跟 `adjust.py` 完全相同的「由近到遠倒序套用、mask = date < roll_date」邏輯疊乘進 `open/max/min/close` 四欄，產生 `adj_*` 系列，原始欄位完全不覆寫）。
3. **執行結果與交叉驗證**：全樣本（2000-2024）跑出 **300 次轉倉事件、0 次因資料缺口而跳過**——這個 300 剛好精確對應上一輪 `fut_probe_rollover_h1_h2.py` 測試的「300 個月結算週期（2000-2024）」，兩支獨立腳本用不同邏輯（一支專門偵測量能超車、一支偵測合約 ID 消失）算出同一個數字，是一個很強的交叉確認訊號，不是巧合。
4. **手動驗證正確性**（協定要求的「少數幾次轉倉」）：針對 2024-06 這次轉倉手算數學關係——切換前一天（06-19）新合約（202407）收盤 23129、舊合約（202406）收盤 23225，比例 = 23129/23225 = 0.995866。理論上調整後序列在這個交界點的報酬率應該等於「假設新合約序列從沒中斷過」的真實報酬率，即 `adj_close(06-19)/adj_close(06-20)` 應該等於 `raw_close(06-19,舊合約)*比例/raw_close(06-20,新合約)` = `23129/23378` = 0.989349。實際程式輸出 `23548.338839/23801.853318 = 0.989349...`，**完全吻合**，數學上證實調整邏輯正確。另外印出的前 5 次轉倉窗口（2000年1～5月）也做了肉眼檢查，`contract_date` 切換點跟報酬連續性型態一致，沒有看到異常跳空。

**沒做的事**：多次轉倉後的累積漂移幅度實測（`FUT_CONTINUOUS_CONTRACT_DESIGN.md`「尚待驗證 #2」，需要拿調整後價格 vs 真實現價比較，這是下一輪的工作單位）、`after_market`（夜盤）session 的連續合約（目前只做 `position` session，這是刻意的範圍限縮，寫在模組 docstring 裡）、任何期貨因子/策略假說測試——這些都排在連續合約地基完全就緒之後，本輪一個工作單位只處理「單一合約序列銜接程式碼＋手動驗證」，已達成本輪目標。`TRIALS_LEDGER.md` 沒有新增列——這是連續合約建構的地基工作（延續 `institutional_investors` 排查、H1/H2 驗證兩次先例的判斷），不是可統計檢定的因子/策略假說測試。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。本輪完全沒有呼叫任何網路請求——`continuous_contract.py` 預設的 `FULL_HISTORY_START`/`FULL_HISTORY_END` 就是既有快取的鍵值，`load_dev()` 全程命中本機 parquet 快取。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目改為實測比價法累積漂移幅度（`FUT_CONTINUOUS_CONTRACT_DESIGN.md`「尚待驗證 #2」）。

---

## 2026-08-24T03:01:00+08:00 — 馬拉松第30輪期貨軌執行：累積漂移幅度實測（`fut_drift_probe.py`）

**選軌理由**：`marathon_lock.py acquire` 成功後比對三軌 state 檔案的實際檔案修改時間（timestamp 欄位本身有幾筆疑似寫錯未來時間，改用 `ls --time-style=full-iso` 的真實 mtime 判斷）——FUT（08-23 21:34:45）最舊，US（08-23 22:03:42）次之，TW（08-24 02:35:48）最新，選最久沒被碰的期貨軌。

**這一輪工作單位**：`FUT_MARATHON_STATE.md`／`FUT_CONTINUOUS_CONTRACT_DESIGN.md`「尚待驗證 #2」——實測比價法連續多次轉倉後的累積漂移幅度，這是連續合約地基最後一項尚未驗證的工作。

**做了什麼**：
1. 寫了 `fut_drift_probe.py`，呼叫上一輪已完成的 `continuous_contract.build_continuous_series()`（預設鍵值直接命中既有全歷史快取，零網路請求）。
2. 量測 `pct_diff = adj_close/close - 1`（`close` 是前月合約當天真實成交價，未調整）的全樣本分佈、逐年首日快照、`corr(days_back, |pct_diff|)`、超過 1%/5%/10%/20%/50% 門檻的天數占比。
3. 額外加了一個沒有明確要求但邏輯上必須驗證的檢查（避免只驗證「漂移多大」卻沒驗證「漂移有沒有連帶汙染報酬率」，這是設計文件核心主張，值得順手交叉確認）：逐日比對 `adj_close` 跟 `close` 各自的百分比變動，看差異天數是否精確等於轉倉事件數、且非轉倉日差異天數是否為 0。

**結果**（完整數字見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`「累積漂移幅度」章節）：
- 樣本起點（2000-01-04，全部300次轉倉累積）：`adj_close`＝2621.72 vs `close`＝8843.0，`pct_diff = -70.4%`。
- 逐年首日快照顯示漂移隨時間單調收斂到0（2000年-70%→2010年-52%→2020年-18%→2023年轉正+0.8%→2024年+2.6%），`corr(days_back, |pct_diff|)` = 0.9825（幾乎完美單調，系統性偏態，不是隨機雜訊互相抵銷）。
- 全樣本 96.2%/89.3%/83.5%/78.5%/42.7% 的交易日 `|pct_diff|` 分別超過 1%/5%/10%/20%/50% 門檻——這是絕大多數歷史日期的常態狀態，不是尾端離群值。
- 報酬率交叉確認：`adj_close` vs `close` 逐日百分比變動的差異天數 = 296（全樣本6185天中），精確對應300次轉倉事件的絕大多數（4天差異未逐一排查根因，量級小到不影響結論），**非轉倉日差異天數 = 0**，證實設計文件「轉倉點報酬率連續、無跳空」的主張站得住腳。

**判讀（誠實記錄，不誇大也不淡化）**：這是本輪最重要的修正——原設計文件說「比價法調整後價格不是真實成交價的缺點在這裡影響很小」，實測後發現「影響很小」這句話**低估了量級**（早期歷史價位漂移到只剩3成），但沒有錯到「不能用」——因為候選策略清單全部是短中期報酬率導向，而報酬率本身被證實完全未受污染。地基狀態從「連續合約有，漂移未知」升級為「連續合約有，漂移已量化且不阻塞短中期回看窗口的因子測試，但長回看窗口/絕對點位判斷要另外小心」。

**沒做的事**：漂移背後的經濟成因拆解（新合約系統性相對舊合約偏低的價差本身是什麼原因，可能跟台股高股息殖利率/期現貼水有關，這是另一個獨立假說，值得排進候選清單但不是本輪範圍）、任何期貨因子/策略假說測試（地基現在完備了，但本輪一個工作單位只處理漂移驗證，不塞第二件事）。`TRIALS_LEDGER.md` 沒有新增列——這是連續合約地基驗證的最後一項，延續前幾輪地基調查的判斷（不是可統計檢定的因子/策略假說測試）。

**Holdout 檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（未被使用）。本輪完全沒有呼叫任何網路請求——`fut_drift_probe.py` 透過 `build_continuous_series()` 的預設鍵值全程命中本機 parquet 快取。

**下一輪**：見 `FUT_MARATHON_STATE.md`「下一輪建議工作單位」，優先項目改為開始系統化測期貨因子（`MARATHON_PROTOCOL.md` 第3節清單），建議從「多時間框架趨勢」或「突破 Donchian channel」開始，一輪最多測2–3個假說，用便宜關卡先篩。

## 2026-08-24T04:34:00+08:00 — 馬拉松第33輪期貨軌執行：第一批策略假說便宜關卡（兩個都FAIL）

**這是地基完成後第一輪實際策略測試。** 上一輪（第30輪）確認地基🟢完整可用並量測了累積漂移幅度，本輪接手開始測`MARATHON_PROTOCOL.md`第3節候選清單。

**新寫`fut_cheap_gate.py`**：期貨版的便宜關卡腳本，仿照`factor_ic.py`的打散對照精神，但改成適合單一時間序列策略的版本——把真實策略的每日部位陣列做200次隨機排列（permutation，不是重新生成隨機部位，這樣可以保留真實策略的活躍度/多空比例分布，只打亂訊號的時序精準度），跟原始報酬序列重新配對，比較真實策略終值落在200次隨機排列終值分布的第幾百分位。單測門檻90.0百分位（跟`factor_ic.py`的90th percentile起點一致），這是便宜關卡不是最終判定，尚未套用累積多重比較校正。

**測了兩個假說**（`FUT_MARATHON_STATE.md`建議的起手候選）：
1. `fut_trend_multi_tf`：10/20/60日動能方向多數決（3個窗口各自sign，加總再取sign當部位），日頻換倉。真實策略終值+174.6%累積（2000-2024全樣本6184天，無成本），隨機排列中位數+2.4%，percentile=**82.5**，未過90.0門檻。**FAIL**。
2. `fut_donchian_breakout_20`：20日Donchian channel突破，有狀態持有（突破上緣做多、突破下緣做空，區間內持有前一部位不動）。真實策略終值+24.1%累積，隨機排列中位數-1.4%，percentile=**61.0**，未過門檻，比#1更弱。**FAIL**。

**判定依協定不調參數硬救**——兩個都是最基本、最常見的技術訊號起手式，都沒過，誠實記錄FAIL，換方向。已更新`TRIALS_LEDGER.md`#18/#19、`FUT_LEADS.md`#1/#2。

**下一輪建議**：`fut_trend_multi_tf`雖然FAIL但方向正確（真實策略明顯贏隨機中位數，只是強度不夠精準跨過90百分位門檻），暗示台指期可能真的有動能訊號但訊噪比不夠——下一輪可以嘗試波動regime過濾（`MARATHON_PROTOCOL.md`第3節期貨候選之一，邏輯是「只在某些波動狀態下交易，濾掉雜訊期」）或均線系統（不同於純動能sign的訊號構造），而不是重測同一類單一動能/突破訊號。**兩個訊號都用了adj_close（10-60日回看窗口），落在上一輪漂移量測確認「短中期回看窗口安全」的範圍內，PIT/漂移方面沒有新的未驗證假設。**

Holdout確認：`is_holdout_consumed()` → `False`（本輪結束前再次確認）。本輪只讀本機parquet快取（`continuous_contract.py`的`load_dev`走既有快取key），無新網路請求。

---

## 2026-08-24T05:03:32+08:00 — 馬拉松第33輪期貨軌執行（續接）：偵測到上一輪陳舊鎖檔並接手，第二批策略假說便宜關卡（兩個都FAIL）

**開場即偵測到`LOCK_STALE`**（pid 104836，鎖檔已存在30.0分鐘，超過25分鐘陳舊門檻，自動回收）。檢查後確認：**上一輪（即上方04:34那筆條目的執行個體）並非完全沒做事——它已經完成`fut_cheap_gate.py`的撰寫跟前兩個假說(`fut_trend_multi_tf`/`fut_donchian_breakout_20`)的便宜關卡測試，並且已經把結果寫進`FUT_LOG.md`（上方那筆條目）、`TRIALS_LEDGER.md`(#18/#19)、`FUT_LEADS.md`(#1/#2)——但它在完成`FUT_MARATHON_STATE.md`更新、心跳寫入`REPORT.md`、`MARATHON_STATE.md`輪號遞增、`git commit`+`push`、釋放鎖檔之前就中止了**（`git status`確認這三份檔案的修改跟新建的`fut_cheap_gate.py`都還是uncommitted狀態，證實協定第6節步驟5–7全部沒跑完）。這是繼第13/14/25/27輪之後，`LOCK_STALE`偵測機制又一次成功攔截住的部分完成、未收尾的執行個體——跟第27輪那種「完全沒留下任何內容」不同，這次是**寫到一半、卡在收尾步驟**，屬於更輕微但一樣需要記錄的失敗模式。

**接手方式**：不重跑`fut_trend_multi_tf`/`fut_donchian_breakout_20`（已經有乾淨結果，重跑只是浪費），直接在上一輪已建立的`fut_cheap_gate.py`基礎上繼續本輪自己的工作單位——照`FUT_MARATHON_STATE.md`「下一輪建議」新增兩個結構上不同的假說：

3. `fut_ma_crossover_20_60`：20日/60日SMA均線交叉（`sign(SMA20-SMA60)`當部位），跟動能多數決/通道突破都不同的訊號構造（均線平滑帶來的落後 vs 原始價格的即時反應，是不同的bias/variance取捨）。真實策略終值+127.7%累積（2000-2024，無成本），隨機排列中位數+14.1%，percentile=**75.5**，未過90.0門檻。**FAIL**。
4. `fut_vol_regime_trend`：對已FAIL的`fut_trend_multi_tf`訊號加上20日已實現波動度regime過濾（只在波動度低於自身展開中位數的「平靜期」進場，其餘部位歸零）——這是`MARATHON_PROTOCOL.md`明確建議的結構性變體（改變「何時允許進場」，不是調整訊號本身參數），測試「波動regime過濾」這個獨立候選家族。真實策略終值+195.3%累積，隨機排列中位數+31.6%，percentile=**82.5**，未過門檻，**跟未過濾版本(#18的82.5)幾乎打平**——顯示這個regime過濾對`fut_trend_multi_tf`沒有帶來統計上可辨識的改善。**FAIL**。

**判定依協定不調參數硬救**——四個技術訊號家族（動能多數決、通道突破、均線交叉）加一個regime過濾變體全部FAIL，已更新`TRIALS_LEDGER.md`#20/#21、`FUT_LEADS.md`#3/#4。**下一輪建議換方向**：不要再對`fut_trend_multi_tf`類趨勢訊號做regime過濾類變體（已證實無效），改試日內均值回歸（跟趨勢方向相反的假說家族）、期現價差、三大法人期貨部位/未平倉量變化（籌碼面，跟純技術面訊噪比可能不同）、或星期效應/盤別效應（季節性，機制完全不同）。

Holdout確認：`is_holdout_consumed()` → `False`（本輪開始前跟結束前都確認過）。本輪只讀本機parquet快取（`continuous_contract.py`的`load_dev`走既有快取key），無新網路請求。

---

## 2026-08-24T06:32:00+08:00 — 馬拉松第36輪期貨軌執行：換家族第一批（籌碼面OI確認、季節性週一效應，兩個都FAIL）

**選軌理由**：取鎖乾淨成功（`LOCK_ACQUIRED`，非陳舊回收）。比對三軌state檔案「最後更新」時間戳：FUT 05:03:32最舊，TW 05:35:57次之，US 06:02:00最新，選最久沒被碰的期貨軌。

**這一輪工作單位**：接上一輪（第33輪續接）明確建議的「換方向而非同家族繼續變體」，四個純技術面訊號（動能多數決/通道突破/均線交叉/regime過濾）都FAIL後，本輪選兩個機制完全不同的家族各測一個假說：

1. **`fut_oi_price_confirm_5d`**（籌碼面，第一次）：1日價格方向（最粗糙、無平滑的方向輸入，刻意如此，讓OI過濾器本身承擔全部辨識工作）經5日未平倉量變化過濾——只在OI上升（新資金淨流入這個方向的解讀，區別於單純的空單回補/多單平倉）時才進場，否則空手。`open_interest`欄位已經存在於`continuous_contract.build_continuous_series()`輸出裡（上一輪地基已驗證資料品質，本輪確認無NaN、無零值/負值，6185列全部有效），**不需要新資料源**。真實策略終值+11.9%累積（2000-2024全樣本，無成本），隨機排列中位數−13.1%，percentile=**62.0**，未過90.0門檻。**FAIL**（但方向正確，真實策略贏隨機中位數）。
2. **`fut_weekday_effect`**（季節性，第一次）：週一放空、週二至週五做多的固定規則，來源是American equity「週末效應」文獻（French 1980，週一報酬歷史上顯著低於其他工作日，通常歸因於週末累積的負面消息在週一開盤時被定價）——**這是文獻來源的固定規則，沒有用本樣本的星期別平均報酬去配適挑選**（符合`MARATHON_PROTOCOL.md`第3節「查到的方法當假說來源，一定要重新走驗證關卡，不可照抄」的精神，但這裡連「照抄」都沒有，是完全外部斷言的規則，樣本內沒有任何配適動作）。真實策略終值+19.7%累積（無成本），隨機排列中位數**+308.1%**，percentile=**13.5**，不只沒過門檻，方向還是反的——隨機打散這個部位陣列（多數為+1，僅週一為−1）大幅贏過真實策略，暗示台指期樣本內週一報酬並沒有系統性偏低（跟美股文獻的方向不一致）。**FAIL**。

**做法**：兩個假說都新增到既有`fut_cheap_gate.py`（沒有另開新檔案，延續同一套便宜關卡框架跟200次排列/90百分位門檻，維持跟前4個假說可比），docstring同步更新記錄本輪的假說設計理由跟兩者「刻意跟已測家族不同機制」的用意。

**判定依協定不調參數硬救**——六個獨立機制家族（動能多數決、通道突破、均線交叉、regime過濾、OI確認、週一效應）全部FAIL，已更新`TRIALS_LEDGER.md`#22/#23、`FUT_LEADS.md`#5/#6。**下一輪建議**：見`FUT_LEADS.md`「下一輪建議」段落——剩餘候選(a)日內均值回歸（需先確認資料是否支援日內拆解）、(b)期現價差（需要新增現貨指數資料源）、(c)三大法人期貨部位（不同於本輪測的無方向性OI，是有方向性的法人多空未平倉，需要另外接TAIFEX資料，是新的小型地基工作）、(d)盤別效應（需要先把`after_market` session納入連續合約建構，也是地基工作）。**六連敗後值得留意但不是本輪判斷**：這批便宜關卡本身（200次排列、90百分位）對這個市場/頻率組合是否系統性偏嚴格，需要更多資料點才能下結論，不要在還沒有更多證據前就調整門檻本身。

**Holdout檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（本輪開始前跟結束前都確認過）。本輪只讀本機parquet快取（`continuous_contract.py`的`load_dev`走既有快取key），無新網路請求。

---

## 2026-08-24T21:19:00+08:00 — 馬拉松第39輪期貨軌執行：三大法人期貨部位地基探測（`fut_probe_institutional_positions.py`）

**選軌理由**：取鎖乾淨成功（`LOCK_ACQUIRED`，非陳舊回收）。比對三軌state檔案「最後更新」時間戳：FUT 06:32:00最舊，TW 07:06:36次之，US 07:31:16最新，選最久沒被碰的期貨軌。

**這一輪工作單位**：接上一輪（第36輪）「下一輪建議工作單位」候選(c)——三大法人期貨部位（有方向性的法人多空未平倉部位，不同於已測過的無方向性`open_interest`），該候選明確標註「需要先做小型地基工作（確認端點、欄位格式）才能測」。`DATA.md`第6節先前只在窄視窗（2024-06-03～06-07）驗證過`TaiwanFuturesInstitutionalInvestors`的欄位結構跟編碼問題，本輪把地基補齊到跟`continuous_contract.py`同樣的全歷史範圍（2000-01-01～2024-12-31）。

**做了什麼**：新寫`fut_probe_institutional_positions.py`，透過`finmind_client.load_dev()`抓`TaiwanFuturesInstitutionalInvestors`TX全歷史範圍（單次網路請求，未撞限流），驗證：類別標籤（寫入UTF-8檔案避免終端機顯示假象，沿用第六輪的教訓）、日期覆蓋率（跟已快取的`TaiwanFuturesDaily`比對）、每日列數、數值欄位NaN/負值/零值健檢、跟`continuous_contract`聚合OI的交叉核對。

**結果（誠實記錄，包含一個重要的負面發現）**：
1. **實際抓到4815列，日期範圍`2018-06-05`～`2024-12-31`（1605個不同交易日）——不是預期的2000-01-01起算。** 跟`TaiwanFuturesDaily`同範圍的6191個交易日相比，**4586天（74%）完全沒有這個資料集的資料**，早期歷史（2000–2018年中）整段缺失。**這是本輪最重要的發現：這個資料集的實際可用樣本只有全歷史的約26%，遠比先前地基（連續合約、漂移量測）建立時假設的「地基已完整可用」樂觀**——如果之後要拿這個資料集當因子輸入，樣本規模天花板就是1605天，不是既有策略測試用的6185天。
2. 類別標籤確認3種（外資/投信/自營商），每個涵蓋日期都恰好3列（無缺類別），無日期落在institutional-investors但不在TaiwanFuturesDaily的異常情況。
3. 數值欄位（成交量/金額/未平倉餘額量/金額共8欄）全部NaN=0、負值=0；`long_deal_volume`/`long_deal_amount`各55/4815零值、`short_deal_volume`/`short_deal_amount`各69/4815零值（低量但非零發生率，合理範圍內，未進一步排查是否集中在特定早期日期）；未平倉餘額四欄0個零值。
4. **交叉核對一開始出現看似異常的結果（3類多單OI總和/continuous_contract聚合OI比值，313/1605天>1.0，最高5.316），但追查後確認是本輪自己交叉核對設計的方法論落差，不是資料源真的有問題**：`continuous_contract`的`open_interest`欄位只取**近月合約單一欄位**（`front_month_series()`的定義），而三大法人資料集回報的是**所有月份合約加總**的部位。改用`load_position_session()`重算「所有月份合約OI加總」後重新比對，比值全部落在0.499–0.904之間、**0天超過1.0**——證實三大法人資料集本身沒有真正的異常，先前的>1.0現象完全是聚合層級不一致造成的假警報。**這是一個值得記錄的方法論教訓：拿任何期貨衍生資料跟`continuous_contract`聚合欄位做交叉核對前，先確認對方的OI/成交量統計口徑是近月合約還是全合約月份，不能預設一致。**

**判讀**：地基工作完成，但結論比預期保守——資料集本身乾淨可用（無NaN/負值、類別完整、交叉核對後無異常），**但2000–2018年中完全空白的樣本缺口是這個候選因子/策略天生的限制，不是可以修的資料品質問題**。下一輪如果要接手測`f`ut_institutional_net_position`類假說，樣本只能用2018-06-05以後的區間（1605天），設計便宜關卡時要注意這比先前6個FAIL假說用的全樣本小很多，統計檢定力會偏低，判定時要把這個限制寫進假說紀錄，不能跟全樣本假說用同一套心理預期比較。

**沒做的事**：沒有本輪同時建構訊號/跑`fut_cheap_gate.py`（依協定1c「地基」跟「假說測試」是分開的工作單位，且本輪發現的樣本缺口是重要到值得先讓下一輪知道再決定要不要接手測試，不要在還沒讓紀錄可見前就急著往下做）。`TRIALS_LEDGER.md`沒有新增列（跟第30輪漂移探測、第4/9輪PIT驗證同精神，這是地基驗證不是可統計檢定的假說測試）。已同步更新`DATA.md`第6節。

**Holdout檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`（本輪開始前跟結束前都確認過）。本輪對`TaiwanFuturesInstitutionalInvestors`發出1次網路請求（先前只快取過窄視窗，這次是全歷史範圍的新請求，未撞限流；`TaiwanFuturesDaily`部分全程命中既有快取，零額外請求）。

**下一輪建議**：見`FUT_MARATHON_STATE.md`「下一輪建議工作單位」——(a) 用這1605天的樣本測`fut_institutional_net_position`類假說（例如外資多空淨部位變化方向、連續N日淨部位增減）——**要在假說紀錄裡明確標註樣本受限於2018-06-05起，不是全歷史**；(b) 或維持`FUT_MARATHON_STATE.md`先前列出的其他候選（日內均值回歸資料形狀確認、期現價差新資料源、盤別效應session infra）。

---

## 2026-08-25T06:35:00+08:00 — 馬拉松第48輪：三大法人期貨部位第三批（自營商），完成整個家族

**取鎖**：`LOCK_ACQUIRED`，乾淨成功，無陳舊鎖檔（上一輪第47輪US軌正常結束）。

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T05:37、US 2026-08-25T06:04、FUT 2026-08-25T05:02，FUT最久沒被碰，本輪選FUT軌。

**做的事**：沿用第42/45輪已寫好的`_load_institutional_net_position()`（inner join限制樣本1605天，2018-06-05起），換`category="自營商"`，不需要重寫地基。在`fut_cheap_gate.py`新增`hyp_inst_dealer_net_position_sign`／`hyp_inst_dealer_net_position_change_5d`兩個假說函式（同`hyp_inst_foreign_*`/`hyp_inst_trust_*`的構造，只換category），並在檔案開頭docstring補上第六輪的方法論說明（自營商book主要是選擇權/權證造市避險流，不是方向性押注，經濟解釋框架跟外資「知情交易」、投信「從眾」都不同——第三種結構性不同的機制假說）。

**結果**：
- `fut_inst_dealer_net_position_sign`：percentile=42.5（門檻90.0），**FAIL**。真實策略終值-2.2% vs 隨機控制組中位數+5.3%。
- `fut_inst_dealer_net_position_change_5d`：percentile=25.0（門檻90.0，方向也不對），**FAIL**。真實策略終值-34.7% vs 隨機控制組中位數-7.3%。**跟外資（#8, percentile=97.0）、投信（#10, percentile=96.5）不同——自營商動能版連批次都沒過，是這個家族第一個動能版直接FAIL的案例，不是又一個「批次過但累積校正未過」。**

三大法人期貨部位家族（水位×動能×3類別=6個假說）至此全部測完，兩輪前（第42輪）就已規劃好的順序全部走完：0 PASS、4 FAIL（外資水位#7/`TRIALS_LEDGER.md`#24、投信水位#9/#26、自營商水位#11/#28、自營商動能#12/#29）、2 CHEAP_PASS但累積校正後降級為不確定（外資動能#8/#25、投信動能#10/#27）。**這個訊號家族目前沒有任何一個假說進入深挖清單。**

**過程**：全程零額外API呼叫（沿用第39/7輪的全歷史parquet快取，`_load_institutional_net_position()`內部呼叫`finmind_client.load_dev()`但走既有快取，不撞流量限制）。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程只讀本機快取，沒有任何觸及holdout的操作。

**已更新**：`fut_cheap_gate.py`（新增兩個假說函式+docstring第六輪說明，`main()`改為執行自營商兩個假說）、`TRIALS_LEDGER.md`（#28/#29，累積27→29）、`FUT_LEADS.md`（#11/#12，「目前狀態」跟「下一輪建議」段落同步更新）、`FUT_MARATHON_STATE.md`（下方另行覆寫）。

**下一輪建議**：三大法人期貨部位家族已全覆蓋，優先序改回`MARATHON_PROTOCOL.md`第3節清單其他候選家族——(a) 若優先序判斷值得，把`N_SHUFFLES`從200加密（例如→1000+）一次重新檢驗`fut_inst_foreign_net_position_change_5d`（#8）跟`fut_inst_trust_net_position_change_5d`（#10）是否能跨過累積校正門檻（先評估30分鐘時間預算，1605天樣本+更高N_SHUFFLES執行時間未知）；(b) 日內均值回歸（需先確認日頻資料形狀是否支援拆解，可能改用隔夜vs當日拆解代替）；(c) 期現價差basis（需新增台股加權指數現貨資料源，小型地基工作）；(d) 盤別效應（需把`after_market` session納入連續合約建構，小型地基工作）。

---

## 2026-08-25T08:32:52+08:00 — 馬拉松第51輪：高解析度重測外資/投信淨部位動能，三大法人期貨部位家族完全結案

**取鎖**：`LOCK_ACQUIRED`，乾淨成功，無陳舊鎖檔。

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T07:05、US 2026-08-25T08:02:55、FUT 2026-08-25T06:35，FUT最久沒被碰，本輪選FUT軌。

**做的事**：依`FUT_MARATHON_STATE.md`第48輪「下一輪建議」#1，把`fut_inst_foreign_net_position_change_5d`（`TRIALS_LEDGER.md`#25）跟`fut_inst_trust_net_position_change_5d`（#27）這兩個「單測/批次過但累積校正未過」的假說，用更高解析度重新檢驗是否只是原本N_SHUFFLES=200（0.5%步階）測不準。新增獨立腳本`fut_recheck_inst_momentum_highres.py`——monkey-patch匯入後的`fut_cheap_gate`模組的`N_SHUFFLES`屬性（200→2000），不改`fut_cheap_gate.py`檔案本身的預設值（保留給其他/未來假說用），呼叫既有`hyp_inst_foreign_net_position_change_5d`／`hyp_inst_trust_net_position_change_5d`函式不變。

**結果**：
- `fut_inst_foreign_net_position_change_5d`：percentile 97.0（N=200）→ **97.40**（N=2000），10倍解析度下幾乎沒變（測量雜訊範圍內）。
- `fut_inst_trust_net_position_change_5d`：percentile 96.5（N=200）→ **97.80**（N=2000），同樣幾乎沒變。
- 累積校正門檻（n=31，含本批2列）＝99.68，兩者都清楚低於門檻。**結論：不是原本解析度不足造成的模糊地帶，是用足夠精確度後仍然確定沒有跨過累積校正門檻。**

三大法人期貨部位家族（水位×動能×3類別=6個假說，跨第39/42/45/48/51輪）至此完全結案：0 PASS、4 FAIL（外資水位/投信水位/自營商水位/自營商動能）、2「單測過但累積校正確認未過」（外資動能/投信動能，第51輪高解析度確認）。沒有任何候選進入深挖清單，之後不需要再回頭處理這個家族（除非有全新的機制假說，不是既有水位/動能兩種構造的變體）。

**過程**：全程零額外API呼叫（`_load_institutional_net_position()`內部`finmind_client.load_dev()`命中第39/42/45/48輪已快取的全歷史parquet）。執行時間極短（numpy向量化排列測試，1600天樣本×2000次排列，數秒內完成），先前state檔案擔心的「可能接近30分鐘鎖檔窗口」的顧慮在實測後證實是過度保守。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`（腳本內建二次assert，執行輸出也印出確認）。全程只讀本機parquet快取，沒有任何觸及holdout的操作。

**已更新**：新增`fut_recheck_inst_momentum_highres.py`、`TRIALS_LEDGER.md`（#30/#31，累積29→31）、`FUT_LEADS.md`（#13新增列＋「目前狀態」段落改寫為完全結案）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋「下一輪建議」改為剩餘3個候選家族＋「下一步」段落同步）。

**下一輪建議**：三大法人期貨部位家族已完全結案，優先序改回`MARATHON_PROTOCOL.md`第3節剩餘期貨候選家族——(a) 日內均值回歸（需先確認日頻資料是否支援拆解「日內」報酬，可能改用隔夜vs當日拆解代替）；(b) 期現價差basis（需新增台股加權指數現貨資料源，小型地基工作）；(c) 盤別效應（需把`after_market` session納入連續合約建構，小型地基工作）。三者都需要先做地基，接手時先評估30分鐘時間預算，做不完就只做地基那一半，比照第39/48輪先例。

---

## 馬拉松第54輪（2026-08-25T10:05+08:00）

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T09:03:00、US 2026-08-25T09:33:32、FUT 2026-08-25T08:32:52，FUT最久沒被碰，本輪選FUT軌。取鎖`LOCK_ACQUIRED`（乾淨，無陳舊鎖檔）。

**做的事**：依`FUT_MARATHON_STATE.md`「下一輪建議工作單位」#1(a)，接手日內均值回歸家族，第一步先確認地基。

**地基確認**（用python直接檢查，非獨立probe腳本——一行`describe()`就能確認，不需要多步驟investigation）：`continuous_contract.build_continuous_series()`回傳的`series`已經有`adj_open`/`adj_max`/`adj_min`/`adj_close`四欄，隔夜跳空(`overnight_gap = adj_open/adj_close.shift(1)-1`)跟日內報酬(`intraday_ret = adj_close/adj_open-1`)可以直接拆解，**不需要新資料源**（跟`FUT_MARATHON_STATE.md`原本估計「可能需要隔夜vs當日拆解代替」不同，實測發現地基已經現成，不用額外工作）。6185天樣本：`overnight_gap`只有1筆NaN（首日無前一日收盤可比較，預期內）、`intraday_ret`零NaN、無零值/負值價格異常、兩者標準差分別約0.89%/1.16%，量級合理。

**測了2個假說**（同一輪，互為相反方向，`fut_cheap_gate.py`新增`_permutation_test_same_day()`——既有`_permutation_test()`是跨日shift配對，日內訊號是同日決策同日交易，需要不shift的版本，否則會錯誤地多墊一天落後）：
1. `fut_intraday_gap_reversal`（放空gap up、做多gap down）：percentile=8.0，**FAIL**，而且方向嚴重不對——92%的隨機排列贏過真實策略（真實終值-79.5% vs 隨機中位數-45.2%）。
2. `fut_intraday_gap_continuation`（做多gap up、放空gap down）：#1失敗後方向明顯指向「跳空會延續」而非反轉，測相反方向（換一個獨立可證偽的經濟假說，不是對#1調參數）。percentile=92.0，單測門檻90.0過，但**本批次(n=2)Bonferroni校正門檻95.0未過**（累積校正n=33門檻99.70更沒過）。真實終值+117.0% vs 隨機中位數約-19.4%，方向清楚但統計證據比先前#25/#27那種「批次過、只有累積校正沒過」的模式更弱一截——連本批次校正都沒過，誠實記錄為弱訊號，不排入深挖清單。

**經濟解釋**（給#2留待未來驗證用，目前只是方向，不是結論）：隔夜跳空可能反映總經新聞/美股ADR或期指隔夜走勢等真實新資訊，台指期本身開盤前無法交易，日內session持續消化這個資訊而非反轉——市場微結構文獻裡「開盤反應不足」對「開盤過度反應」的標準替代假說。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程只讀本機parquet快取（`build_continuous_series()`命中既有全歷史快取），零額外API呼叫。

**已更新**：`fut_cheap_gate.py`（新增docstring第七輪段落、`_permutation_test_same_day()`、`hyp_intraday_gap_reversal()`、`hyp_intraday_gap_continuation()`、`main()`換成本輪兩個假說）、`TRIALS_LEDGER.md`（#32/#33，累積31→33）、`FUT_LEADS.md`（#14/#15新增列＋「目前狀態」段落新增第54輪小節）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋「下一輪建議」更新）。

**下一輪建議**：見`FUT_LEADS.md`「目前狀態」第54輪小節——(a)若要繼續深究`fut_intraday_gap_continuation`，先加大`N_SHUFFLES`解析度重測（percentile 92.0離批次門檻95.0不遠，值得先排除是不是解析度不足造成的模糊，同第51輪對三大法人動能假說的處理方式）；(b)或換到剩餘候選家族（期現價差basis、盤別效應），兩者都需要小型地基工作，接手時先評估時間預算。

---

## 馬拉松第57輪（2026-08-25T11:33+08:00）

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T10:31:00、US 2026-08-25T11:02:00、FUT 2026-08-25T10:05:00，FUT最久沒被碰，本輪選FUT軌。取鎖`LOCK_ACQUIRED`（乾淨，無陳舊鎖檔）。

**做的事**：依第54輪「下一輪建議工作單位」#1（優先項），對`fut_intraday_gap_continuation`（#33，percentile=92.0，單測過但本批次校正95.0未過）做高解析度重測，排除是不是200次排列的粗解析度造成的模糊地帶。新增`fut_recheck_intraday_gap_continuation_highres.py`（monkey-patch `fut_cheap_gate.N_SHUFFLES`從200→2000，跟第51輪對三大法人動能假說的處理方式同一套做法：不改`fut_cheap_gate.py`本身的模組層級預設值，只在這支獨立腳本的執行過程裡局部覆蓋，呼叫既有`hyp_intraday_gap_continuation()`函式不做任何改動）。

**結果**：percentile 92.0（N=200）→ 89.60（N=2000）。**跟第51輪三大法人動能假說重測後幾乎不變（97.0→97.40、96.5→97.80）明顯不同——這次結果不是逼近門檻，反而下降，而且首次跌破單測門檻90.0本身**。真實策略終值+117.0%（訊號本身沒變，只是隨機排列控制組的抽樣數變多，測量更精確）。結論：原本#33的92.0讀數落在N=200測量雜訊範圍內偏高估，不是解析度不足掩蓋了一個更強的真訊號；`fut_intraday_gap_continuation`現在應視為**確定FAIL**，不再是待觀察的弱訊號。日內均值回歸家族第一批（反轉#14/#32、順勢#15/#33，現在都已高解析度確認）兩個方向雙雙結案：0 PASS。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`（開始前另外跑了一次獨立確認，見上方指令輸出；腳本內建二次assert，執行輸出也印出確認）。全程只讀本機parquet快取（`_load_series()`命中`build_continuous_series()`既有全歷史快取），零額外API呼叫，沒有任何觸及holdout的操作。

**已更新**：新增`fut_recheck_intraday_gap_continuation_highres.py`、`TRIALS_LEDGER.md`（#34，累積33→34）、`FUT_LEADS.md`（#16新增列＋「目前狀態」段落新增第57輪小節，累計FAIL數更新為15）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋「下一輪建議」改為剩餘2個候選家族＋「下一步」段落同步）。

**下一輪建議**：日內均值回歸家族第一批已完全結案（0 PASS），沒有候選需要深挖。換到`MARATHON_PROTOCOL.md`第3節剩餘期貨候選家族——(a) 期現價差basis（需要新增台股加權指數現貨資料源，小型地基工作）；(b) 盤別效應（需要把`after_market` session納入連續合約建構，小型地基工作）。兩者都不能直接套用既有`build_continuous_series()`輸出，接手時先評估30分鐘時間預算，做不完就只做地基那一半，比照第39/48輪先例。

---

## 馬拉松第60輪（2026-08-25T13:03+08:00）

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T12:04:29、US 2026-08-25T12:32:41、FUT 2026-08-25T11:33:00，FUT最久沒被碰，本輪選FUT軌。取鎖`LOCK_ACQUIRED`（乾淨，無陳舊鎖檔）。

**做的事**：依第57輪「下一輪建議」#(b)，接手盤別效應（日盤vs夜盤）家族的地基第一步——先探測`after_market`（推測夜盤）原始資料的形狀，不直接動`continuous_contract.py`本身（避免在還沒搞懂資料形狀前就寫錯銜接邏輯）。新增`fut_probe_night_session.py`，刻意沿用`continuous_contract.load_position_session()`一樣的`(dataset, contract, start_date, end_date)`快取鍵，全程命中既有全歷史parquet快取，零額外API呼叫。

**結果**（TX，全歷史2000-01-01～2024-12-31）：
- `after_market`共15,607列，日期範圍2017-05-16～2024-12-31；`position`（日盤）共49,329列，範圍2000-01-04～2024-12-31。
- **首筆夜盤日期2017-05-16，跟TAIFEX官方夜盤上線日2017-05-15只差一天**——跟`DATA.md`第6節先前只用一週窗口做的推論一致（`after_market`＝夜盤），本輪用全歷史範圍重新確認同一個結論，信心等級提升（原本只是「間接推論」，現在是「全歷史範圍一致，無例外」）。
- **`settlement_price`／`open_interest`：夜盤15,607列，100%數值恆為0**（不是NaN，是明確的0.0，用`==0`直接驗證，不是只看notna）——這跟`DATA.md`先前用2024-06一個月227列樣本得出的結論完全一致，本輪用全歷史35倍樣本量重新確認，**同一個結論的信心等級從「一個月樣本」升級為「全歷史範圍0例外」**。相對地，日盤（position）的這兩欄約35%（17,360/49,329、17,252/49,329）是0，其餘非零——這點沒有先例記錄過，先誠實記下來，但不在本輪範圍內深究原因（可能是遠月合約揭露規則或某些日子officially無成交量，留給以後需要用到這兩欄時再查）。
- **OHLCV完整度**：夜盤單月份合約列（10,833列，已排除價差列）的open/max/min/close/volume全部非NaN，但約1.4%（156/10,833）成交量為0（遠月合約夜盤掛牌但當天無實際成交，合理現象，非資料品質問題）。
- **價差列（`contract_date`含`/`）夜盤也有，4,774/15,607（≈30.6%）**——未來寫夜盤連續合約時，需要沿用`continuous_contract.py`既有的同一個過濾規則，不是新問題。
- **夜盤每日單一月份合約數**：平均5.8檔、最多6檔（近+遠月同時掛牌），比日盤更多——這點只是觀察到，還沒跟日盤逐日比對確認差異幅度，留待以後需要精確銜接邏輯時再查。
- **樣本合約`202212`交叉核對**：日盤該合約首見2021-12-16、末見2022-12-21（結算日）；夜盤首見2021-12-17（比日盤晚一天）、末見同樣2022-12-21。夜盤末端跟日盤在結算日當天對齊，沒有明顯的日期偏移問題；但夜盤起始比日盤晚一天這點只看了一個樣本合約，**還沒有足夠證據判斷是普遍現象還是這個合約的個案**。

**未解決、留給下一輪**（誠實記錄地基還沒完全搭好，不要假裝已經懂了時序關係）：**這輪還沒確認`date`欄位對夜盤列代表的確切交易時段順序**——台灣期貨夜盤實際交易時間是當日15:00到隔日05:00，理論上應該是「日盤收盤後才開始」，但這輪只做了資料形狀探測，沒有拿獨立來源（例如TAIFEX官方交易時間公告，或至少交叉比對夜盤close跟隔日日盤open的相關性）驗證這個時序假設是否成立。**如果之後要建構日盤/夜盤混合的連續序列或測試盤別效應假說，這個時序假設必須先驗證，搞錯方向會讓任何隔夜/盤別報酬的正負號整個顛倒但看起來像是正常的統計結果——這是本輪發現的最重要的風險提示，不是次要細節。**

**經濟解釋（暫不適用）**：本輪是純資料形狀地基探測，沒有測任何交易假說，不適用`MARATHON_PROTOCOL.md`第1b節「為什麼會有效」的要求（那是深挖階段才需要的）。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程只讀本機parquet快取，零額外API呼叫，沒有任何觸及holdout的操作。

**已更新**：新增`fut_probe_night_session.py`、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋「下一輪建議」更新為「先驗證時序假設，再決定要不要動`continuous_contract.py`」）。**沒有新增`TRIALS_LEDGER.md`列**（地基資料形狀探測不是假說測試，同`fut_probe_institutional_positions.py`／`fut_probe_settlement_oi.py`先例）。

**下一輪建議**：兩個選項擇一：(a) 驗證夜盤`date`欄位的時序假設（用夜盤收盤跟隔日日盤開盤的相關性當間接證據，或查TAIFEX官方文件），這是動`continuous_contract.py`寫夜盤連續序列之前的必要前置步驟，不能跳過；(b) 若這輪時間/額度不夠驗證時序，改測期現價差basis家族地基（需要新增台股加權指數現貨資料源，是完全獨立的另一條路，不受夜盤時序問題阻擋）。兩者都是小型地基工作，接手時先評估30分鐘時間預算。

---
