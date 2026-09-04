# FUT_LOG.md — 期貨軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面）。期貨軌是全新的，這份檔案從第一輪馬拉松開始就是期貨軌唯一的執行記錄。

**規則：** 每個馬拉松輪次結束前 append 一條，包含地基搭建進度（期貨軌前期主要是這個，尤其連續合約銜接方法的決定過程）跟之後的策略測試結果，不管有沒有進展都要記錄。

---

## 2026-09-02T05:31+08:00 — 第284輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 04:02（第281輪，最舊）、US 04:31（第282輪）、TW 05:01（第283輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有9個未追蹤log殘留（`dividend_yield_portfolio_v1_run.log`／`monthly_revenue_event_study_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`val_continue_run.log`～`val_continue_run4.log`／`weinstein_v2_run.log`，判斷是其他互動session殘留），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約175輪、跨度約152.9小時（約6.37天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

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

## 馬拉松第63輪（2026-08-25T14:32+08:00）

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T13:34:50、US 2026-08-25T14:02:23、FUT 2026-08-25T13:03:21，FUT最久沒被碰，本輪選FUT軌。取鎖`LOCK_ACQUIRED`（乾淨，無陳舊鎖檔）。

**做的事**：依第60輪「下一輪建議工作單位」#1（優先項）——驗證夜盤`after_market`列的`date`欄位代表的確切交易時段順序，這是第60輪留下的「未解決、最重要的風險提示」，動`continuous_contract.py`寫夜盤連續序列之前的必要前置步驟。新增`fut_verify_night_session_timing.py`，方法：session邊界價格gap比對（市場不會瞬移，正確的時序配對應該有較小的邊界價格跳動），對兩個候選假設各自檢驗兩個邊界：
- H_A（直覺假設）：夜盤(T)介於日盤(T)跟日盤(T+1)之間（收盤後才開盤、隔天日盤開盤前收盤）。
- H_B：夜盤(T)介於日盤(T-1)跟日盤(T)之間（夜盤標示的日期是「即將到來的那個交易日」，這是不少期貨市場的慣例標示法，例如CME的trade date慣例）。

全程沿用`fut_probe_night_session.py`已驗證過的`load_position_session()`快取鍵，零額外API呼叫。第一版執行時遇到`RuntimeWarning: divide by zero encountered in log`——查證後發現1,386/42,995列（含156列夜盤）是零成交量的遠月合約日，open/close確實是`0.0`（不是NaN），不是資料損毀；補上明確過濾（`>0`）後乾淨重跑。

**結果**（TX，全歷史，過濾零成交量列後）：
- **夜盤開盤邊界**（n=10,606）：H_A配對`|ln(n_open(T)/d_close(T))|` mean=0.007652／median=0.005526；H_B配對`|ln(n_open(T)/d_close(T-1))|` mean=0.001465／median=0.000898。H_A gap比H_B gap小的列只佔12.5%（即H_B在87.5%的列上gap更小）。
- **夜盤收盤邊界**（n=10,510）：H_A配對`|ln(d_open(T+1)/n_close(T))|` mean=0.008538／median=0.006267；H_B配對`|ln(d_open(T)/n_close(T))|` mean=0.002562／median=0.001621。H_A gap比H_B gap小的列只佔16.1%。
- **參考基準**：同日日盤本身盤中波動`|ln(d_close/d_open)|` mean=0.005277——H_B的兩個邊界gap（0.0015、0.0026）都明顯小於這個「同一根K棒內」的波動幅度，H_A的兩個邊界gap（0.0077、0.0085）則都大於這個基準，方向合理（真正相鄰的session邊界跳動應該比橫跨一整個額外session的配對小，H_B完全符合這個直覺，H_A不符合）。
- **結論明確、不模糊**：兩個邊界、mean跟median、多數列判定四個指標全部一致指向H_B——**夜盤標示日期T實際上代表「T前一晚15:00到T當天清晨05:00」這一段，是即將到來的日盤T的前哨（前置盤），不是日盤T收盤後才開始**。這推翻了第60輪筆記裡「理論上應該是日盤收盤後才開始」的直覺假設，但吻合部分海外期貨市場（如CME）「夜盤標示為次一交易日」的常見慣例。

**經濟解釋（暫不適用）**：本輪是純資料時序驗證，沒有測任何交易假說，不適用`MARATHON_PROTOCOL.md`第1b節要求。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程只讀本機parquet快取，零額外API呼叫。

**已更新**：新增`fut_verify_night_session_timing.py`、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋更新「下一輪建議工作單位」，時序假設已解決，第一項優先序讓給basis家族地基或直接開始寫夜盤連續序列）。**沒有新增`TRIALS_LEDGER.md`列**（地基時序驗證不是假說測試，同`fut_probe_night_session.py`／`fut_probe_institutional_positions.py`先例）。

**下一輪建議**：時序假設已解決（H_B確認），下一輪可以在這個基礎上動`continuous_contract.py`寫夜盤感知的連續序列建構（rollover規則要重新確認：夜盤合約轉倉時點可能跟日盤不同步，這輪沒有檢查），或改測完全獨立的basis家族地基（不受此結果影響，仍是可選項）。

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

## 馬拉松第66輪（2026-08-25T16:04:29+08:00）

**選軌依據**：讀三軌state「最後更新」時間戳——TW 2026-08-25T15:13:42、US 2026-08-25T15:34:05、FUT 2026-08-25T14:32:52，FUT最久沒被碰，本輪選FUT軌。取鎖`LOCK_ACQUIRED`（乾淨，無陳舊鎖檔）。

**做的事**：依第63輪「下一輪建議工作單位」第2項——不碰`continuous_contract.py`本身（夜盤連續序列建構是核心地基改動，風險較高，留給專門一輪處理），改接手完全獨立的期現價差basis家族地基第一步：確認台股加權指數（TAIEX）現貨價格資料源在FinMind免費層是否可用。

**過程（誠實記錄WebSearch/WebFetch的不可靠性）**：先用WebSearch/WebFetch查FinMind官方文件兩次，兩次AI摘要給出**互相矛盾且部分明顯錯誤**的答案（一次說`TaiwanVariousIndicators5Seconds`是最佳選擇，另一次改推薦`TaiwanStockKBar`分K資料，都沒有提到後來證實可用的`TaiwanStockPrice`/`TAIEX`組合）——這印證了`MARATHON_PROTOCOL.md`第3節「查到的方法一定要重新走這個專案自己的完整驗證關卡」的規則不只適用於策略假說，也適用於基礎資料源查證本身。**沒有直接採信任何一次網路摘要，改寫`fut_probe_spot_index.py`對3個候選`(dataset, data_id)`組合各打一次小樣本（2024-01單月）API呼叫實測。**

**結果**：
- `('TaiwanVariousIndicators5Seconds', '')`：**HTTP 400**，該dataset明確拒絕多日區間查詢（"we only send one day data, so end_date parameter need be none"）——不適合日頻歷史回測，排除。
- `('TaiwanStockTotalReturnIndex', 'TAIEX')`：可用，但回傳的是**報酬指數**（2024-01-02收盤價38475.17，遠高於同日真實TAIEX收盤17853.76），是股利再投資後的還原數字，**不是**basis計算該用的現貨標的價格，排除（但確認這個dataset本身存在，未來如果需要報酬指數可以回頭用）。
- `('TaiwanStockPrice', 'TAIEX')`：✅ **可用，且正是需要的原始現貨指數**——回傳open/max/min/close/Trading_Volume等完整OHLC欄位，2024-01-02收盤17853.76跟真實TAIEX當日收盤一致。**這是basis家族的正確現貨資料源。**
- 全歷史範圍（`FULL_HISTORY_START`=2000-01-01～`FULL_HISTORY_END`=2024-12-31）追加驗證：**6,185列，日期範圍2000-01-04～2024-12-31，open/max/min/close全部無NaN、無≤0異常值、無重複日期**。**6,185這個列數跟`FUT_MARATHON_STATE.md`多處記錄的期貨連續合約全樣本天數完全一致**（「累計15個FAIL...這批便宜關卡...對台指期日頻」等處反覆提到的樣本規模），暗示現貨指數跟期貨連續序列的交易日曆高度重合，未來用日期做inner join銜接時應該不會遇到大量缺口問題（但這只是列數巧合對上，還沒有實際逐日join驗證，下一輪或深挖時要做這一步再確認）。

**這輪只做地基第一步（資料源確認），沒有寫basis計算邏輯本身**（近月合約選取規則、basis定義的正負號慣例、跟`continuous_contract.py`銜接的join key設計都還沒動），照`MARATHON_PROTOCOL.md`第5節「地基搭建也要遵守誠實記錄原則...每一輪只搭一部分」的精神，不要為了看起來有進度而囫圇吞棗。

**經濟解釋（暫不適用）**：本輪是純資料源地基探測，沒有測任何交易假說，不適用`MARATHON_PROTOCOL.md`第1b節要求。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程僅3次短窗口探測API呼叫（各22列，2024-01單月）+1次全歷史API呼叫（6185列），未觸碰holdout邊界（`load_dev()`全程截斷在`VAL_END`）。

**已更新**：新增`fut_probe_spot_index.py`、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋更新「下一輪建議工作單位」）。**沒有新增`TRIALS_LEDGER.md`列**（地基資料源探測不是假說測試，同`fut_probe_night_session.py`／`fut_probe_institutional_positions.py`先例）。

**下一輪建議**：basis家族地基第二步——寫近月期貨選取邏輯（`continuous_contract.py`已有的「近月」定義可以直接參考/重用，不需要重新設計）跟TAIEX現貨的逐日join，實際算出basis序列（近月期貨收盤/結算價 − TAIEX現貨收盤），檢查join後的覆蓋率（列數巧合對上6185不代表交易日曆100%重合，需要實際驗證）、basis值的分布是否合理（正常情況台指期通常小幅貼水或升水，不應該出現離譜的異常值）。若這輪不想繼續basis家族，另一個獨立選項仍是：確認夜盤合約轉倉時點是否跟日盤同步（第63輪解決時序方向問題後留下的前置查證項），為之後動`continuous_contract.py`寫夜盤連續序列鋪路。

---

## 2026-08-25T17:34:50+08:00 — 馬拉松第69輪期貨軌執行：basis家族地基第二步完成（近月期貨×TAIEX現貨join，全樣本100%覆蓋）+ 意外發現並修復`validation/holdout.py`的pandas 3.0.5相容性bug

**選軌理由**：取鎖乾淨成功`LOCK_ACQUIRED`，無陳舊鎖檔。比對TW（16:35:41）／US（17:02:50）／FUT（16:04:29，最舊）三軌最後更新時間戳，選期貨軌。

**做了什麼**：

1. **basis家族地基第二步（第66輪「下一輪建議工作單位」第1項）**：新寫`fut_basis_series.py`，`build_basis_series()`函式：
   - 近月期貨：直接重用`continuous_contract.py`的`build_continuous_series()`／`front_month_series()`既有定義（最小`contract_date`且當天有非空收盤價的合約），**用原始（未經比價法調整的）`close`欄位**，不是`adj_close`——因為basis是「當天實際成交價 vs 當天實際現貨價」的同日快照，比價法調整的用途是讓*報酬率*序列跨轉倉平滑銜接，套用在同日價差快照上反而是錯誤用法（早期區段會被乘上調整係數，扭曲了那天真實的期現價差）。
   - 現貨：`load_dev("TaiwanStockPrice", "TAIEX", ...)`，第66輪已確認的正確資料源。
   - 用`date`欄位inner join，計算`basis = fut_close - spot_close`跟`basis_pct = basis / spot_close`（因為TAIEX指數水位全樣本期間漲了約5倍，原始點數差不能跨期間直接比較，要看百分比）。
2. **意外撞到並修復一個真實bug**：第一次執行時，`holdout.assert_no_holdout_leakage()`直接丟`TypeError: '>' not supported between instances of 'Timestamp' and 'str'`——不是我寫的程式碼邏輯錯，是`validation/holdout.py`本身的`cap_to_dev`／`cap_to_train`／`validation_slice`／`assert_no_holdout_leakage`／`unlock_holdout_once`五個函式全部直接拿`df[date_col]`（可能是`datetime64` dtype，例如`continuous_contract.py`的`load_position_session()`一開始就把`date`轉成`pd.to_datetime`）跟`VAL_END`／`TRAIN_END`（純Python字串）比大小，這在**pandas 3.0.5**下不再自動把字串轉型再比較（舊版pandas的`Timestamp > str`行為是自動解析字串），直接丟`TypeError`。這解釋了為什麼`factor_ic.py`等既有呼叫者都沒撞到過這個問題——它們全部是在`prepare_market_data()`等日期轉型**之前**呼叫這個檢查，餵進去的還是原始字串dtype，剛好繞開了這個地雷；`fut_basis_series.py`是第一個把**已經轉成`datetime64`的df**餵給這個檢查的呼叫者。
   - **修法**：五個函式的日期比較全部改成先用`pd.to_datetime(df[date_col])`／`pd.Timestamp(max_date)`統一轉型，再跟`pd.Timestamp(VAL_END)`等比較——雙邊都正規化成`Timestamp`後比較，字串dtype跟`datetime64` dtype都能正確處理，行為對舊呼叫者（字串dtype）完全不變（有寫smoke test驗證，見下）。
   - **性質判斷**：這是fail-loud（直接crash）不是fail-silent（悄悄放行holdout洩漏），所以不是「已經發生過的洩漏事件」，是「這個安全機制本身在特定合法輸入型態下會直接壞掉、擋住合法呼叫者」的可用性bug，修復範圍侷限在型態正規化這五行，沒有動任何日期邊界常數（`TRAIN_END`／`VAL_END`不變）、沒有動`unlock_holdout_once()`的鎖檔機制邏輯本身。
   - **驗證**：跑了一次獨立smoke test（字串dtype df＋datetime64 dtype df，各測`cap_to_dev`／`validation_slice`／`assert_no_holdout_leakage`能正常通過＋確認`assert_no_holdout_leakage`在真正洩漏情境下**還是會正確丟出**`AssertionError`，不是被我改壞成永遠不報錯），全部符合預期，細節見本輪`git log`/commit diff。
3. 執行`fut_basis_series.py`的`__main__`探測（全歷史`2000-01-01`～`2024-12-31`，零額外新API呼叫——`continuous_contract.build_continuous_series()`跟`TaiwanStockPrice`/`TAIEX`都命中既有本機parquet快取）：

   | 指標 | 結果 |
   |---|---|
   | 近月期貨原始列數 | 6185 |
   | basis序列列數（inner join後）| 6185 |
   | **join覆蓋率** | **100.0000%（0筆無對應現貨列）** |
   | basis（點數）均值/中位數 | -16.67 / -10.61 |
   | basis_pct 均值/中位數 | -0.203% / -0.117% |
   | 貼水（fut<spot）天數佔比 | 65.72%（4065/6185）|
   | 升水（fut>spot）天數佔比 | 34.26%（2119/6185）|
   | \|basis_pct\|>5% 極端值 | 2筆，都在2008-10-24／10-27（金融海嘯期間） |
   | null/非正值 | 0 |

   **判定：地基乾淨可用，第66輪「列數巧合對上」的未驗證假設本輪確認成立（100%覆蓋，不是巧合）。** basis分布合理：均值輕微貼水（-0.2%），跟台股相對高殖利率、期現理論價差公式（cost-of-carry扣掉預期股利）的方向一致，是經濟上說得通的現象，不是異常；唯二超過5%的極端值都落在2008年金融海嘯崩盤期間，屬於已知的市場極端波動情境，不是資料品質問題。**這是地基驗證，不是假說測試，沒有新增`TRIALS_LEDGER.md`列**（比照第39/60/63/66輪先例）。

**沒做的事**：沒有拿basis序列去測任何策略假說（那是下一步，這輪只把序列本身算出來並驗證乾淨）；沒有動`continuous_contract.py`本身（`fut_basis_series.py`只是import它既有的公開函式，沒有修改其邏輯）；holdout邊界常數（`TRAIN_END`/`VAL_END`）本身沒有變動，只有比較邏輯的型態處理被修正。

**Holdout 確認**：本輪開始前跟結束前都跑`is_holdout_consumed()`→`False`。全程零額外FinMind API呼叫（兩份輸入都命中既有全歷史parquet快取）。

**下一輪建議**：basis家族第一批假說可以開始測了（例如：basis水位是否預示短期期貨報酬、basis變化動能、basis均值回歸），用`fut_cheap_gate.py`既有的便宜關卡框架加新的假說函式進去即可，不用重寫框架，記得比照TRIALS_LEDGER累積校正規則。或者繼續獨立的夜盤分支（確認夜盤轉倉時點是否跟日盤同步，第63輪解決時序方向後留下的前置查證項）。

---

## 2026-08-25T19:xx（馬拉松第72輪，時間戳見git commit）期貨軌執行：basis家族第一批假說測試，`fut_basis_carry`是期貨軌第一個全通過候選

**選軌理由**：取鎖乾淨成功`LOCK_ACQUIRED`，無陳舊鎖檔。比對TW（2026-08-25T18:05:40）／US（2026-08-25T18:33:29）／FUT（2026-08-25T17:34:50，最舊）三軌最後更新時間戳，選期貨軌。

**做了什麼**：依第69輪「下一輪建議」第1項，`fut_basis_series.py`的`build_basis_series()`已是乾淨可用地基（100%覆蓋），在`fut_cheap_gate.py`新增`_load_basis(series)`合併輔助函式＋兩個假說：

1. **`fut_basis_carry`**（水位）：`position = -sign(basis_pct)`，貼水（fut<spot）做多、升水做空——經典roll yield/期現收斂carry交易（Keynes正常逆價差理論的股指期貨版本，carry驅動因子理論上是預期股利淨融資成本）。
2. **`fut_basis_change_momentum_5d`**（動能）：`position = sign(basis_pct.diff(5))`，跟著basis 5日變化方向交易——跟三大法人期貨部位家族#7/#8同款「水位vs動能」兩型獨立可證偽設計。

**結果**：

| 假說 | percentile（單測門檻90.0） | 本批(n=2)校正門檻95.0 | 累積校正(n=36)門檻99.7222 | 判定 |
|---|---|---|---|---|
| `fut_basis_carry` | 100.0 | 過 | **過** | **CHEAP_PASS，全部層級通過，排入待深挖清單** |
| `fut_basis_change_momentum_5d` | 0.0（方向嚴重不對） | — | — | FAIL |

**`fut_basis_carry`是期貨軌馬拉松至今第一個乾淨通過全部層級（單測/批次/累積）便宜關卡的假說**（累計19個假說：1全通過、2批次過但累積校正後不確定、16 FAIL）。真實策略終值714.8483（+71384.8%累積，2000-2024無成本），隨機控制組中位數1.3624（+36.2%），200次排列全部輸給真實策略。

**誠實記錄一個異常大的數字，本輪沒有照單全收，額外做了sanity check**：終值717倍是極端數字，本輪懷疑這可能只是「訊號多數時間偏多、順路吃到連續合約長期累積漂移（已知caveat，見`FUT_MARATHON_STATE.md`地基段落）」造成的假訊號，所以另外跑了一段獨立檢查（同一套position/ret資料，不經過`_permutation_test`的drop-NaN路徑）：

- 同期間單純買進持有（無訊號，全程做多`adj_close`）終值僅**8.79x**（+679%）——遠低於策略的717x，**排除了「純漂移artifact」這個最簡單的錯誤解讀**（若真的只是靠常數偏多吃到漂移，買進持有本身也該接近717x，但沒有）。
- position全樣本共翻轉**1613次**（6185天中），不是靜態單一方向。
- 逐年平均部位方向會隨年份變化（2000年-0.64、2024年-0.24偏空，中間多數年份+0.2~+0.7偏多），顯示這是真的在跟著basis逐日變化的動態訊號，不是常數偏多的偽裝成訊號的buy-and-hold。

**但這不代表717x是「已確認的真訊號」**：82倍（717/8.79）的擇時放大倍數，在單一日頻sign訊號、零成本、無槓桿上限框架下極端罕見，很可能是被少數幾個歷史大事件年份（2000年網路泡沫、2008金融海嘯、2024年空頭）主導，不是穩定可重複的邊際優勢——這個疑慮沒有被本輪的sanity check排除，只排除了最簡單的那一種錯誤解讀。**深挖階段(1b)的walk-forward/樣本外切分是驗證這個疑慮的必要下一步**，在那之前這個CHEAP_PASS的極端數字必須帶著這個警語使用。

**經濟解釋**（1b要求，這輪雖然只是1a便宜關卡但候選通過全部層級，提前記錄假說本身的economic story，深挖時仍要重新完整驗證）：期貨價格隨到期日接近會收斂到現貨（cost-of-carry理論），貼水時收斂方向對多頭部位是正報酬、升水時對多頭是負報酬——這是「buy backwardation, sell contango」carry交易的股指期貨版本，round 69已記錄basis均值輕微貼水（-0.2%）跟台股相對高股息殖利率的方向一致，是經濟上說得通的持續性現象，不是隨機雜訊。

**沒做的事**：沒有做深挖（1b，walk-forward/樣本外/成本敏感度/beta對照），本輪只是便宜關卡（1a），依協定一輪做完一個有界工作單位就收工，不要在同一輪塞進深挖。basis家族第三個候選方向（均值回歸，偏離歷史均值後的回歸傾向）這輪也沒測，留給下一輪。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零額外FinMind API呼叫（`build_continuous_series()`與`build_basis_series()`都命中既有全歷史parquet快取）。

**已更新**：`fut_cheap_gate.py`（新增`_load_basis()`/`hyp_basis_carry`/`hyp_basis_change_momentum_5d`，`main()`改跑本輪兩個假說）、`TRIALS_LEDGER.md`（#35/#36）、`FUT_LEADS.md`（#17/#18＋目前狀態＋下一輪建議段落）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。

**下一輪建議**：優先深挖`fut_basis_carry`（walk-forward優先確認717x不是被少數年份主導），次要選項是basis家族第三個假說（均值回歸）或盤別效應家族地基（`after_market`轉倉時點驗證）。

---

## 2026-08-25T20:36:09+08:00（馬拉松第75輪）期貨軌執行：`fut_basis_carry`深挖（1b）完成，結論FAIL，第72輪的CHEAP_PASS降級

**選軌理由**：取鎖乾淨成功`LOCK_ACQUIRED`，無陳舊鎖檔。比對TW（2026-08-25T19:35:10）／US（2026-08-25T20:10:00）／FUT（2026-08-25T19:05:53，最舊）三軌最後更新時間戳，選期貨軌。

**做了什麼**：依`FUT_MARATHON_STATE.md`第72輪「下一輪建議工作單位」#1（最高優先），對期貨軌至今第一個乾淨通過全部便宜關卡層級的候選`fut_basis_carry`做完整深挖（`MARATHON_PROTOCOL.md` 1b）。新寫`deep_dive_fut_basis_carry.py`，四項檢查：

1. **Train/Val切分**（`validation/holdout.py`的`TRAIN_END=2020-12-31`／`VAL_END=2024-12-31`），每個子期間各自跑period-local的配對式隨機控制組（不是重用整個樣本的靜態控制組，是`_matched_permutation_terminal()`針對子區間重新排列，符合協定「配對式隨機控制組（不是靜態版）」的要求）：
   - train（2000-2020，5214天）：真實策略終值638.97x（+63796.7%），買進持有終值僅5.10x，隨機控制組中位數1.15x，percentile=100.0——跟整體便宜關卡結果一致，穩健通過。
   - val（2021-2024，971天）：真實策略終值僅1.10x（+10.4%），買進持有終值1.72x（+72.2%，反而遠贏過策略），隨機控制組中位數1.15x（+15.1%附近），**percentile=46.0——連隨機打散控制組的中位數都沒贏過**。
2. **Leave-one-year-out敏感度**：25年逐一排除，計算排除後終值／全樣本終值的比值。**排除2000/2001/2002三年（依單年報酬排序的前三大貢獻年）後，終值從717.5x驟降到107.9x，只剩全樣本的15.0%**——85%的終值集中在這三個早期年份（2000網路泡沫首當其衝）。其餘年份的leave-one-year-out比值分布相對平緩（0.52–1.18），沒有其他單一年份有這種級別的集中度。
3. **成本敏感度1x/2x/3x**：因為repo目前沒有現成的TX期貨成本模型（`validation/costs.py`是股票百分比成本模型，不適用固定稅制的期貨合約），本輪新記錄一個近似假設並在腳本docstring/輸出中明確標註是近似值非已驗證的真實券商費率表：round-trip 1x=5bps（期貨交易稅0.002%單邊為主要成本來源，約占4bps round-trip，手續費/交易所費用相對TX約NT$340萬名目本金是不到1bp的次要項目，故5bps是保守估的稅費主導假設）。結果：1x→320.9x、2x→143.4x、3x→64.1x，方向不變但**這只是次要檢查**，因為終值本身在check 1/2之後已經確認不可信，成本敏感度的意義降為「就算不管樣本外問題，成本本身也會侵蝕掉相當比例的報酬」這個補充資訊，不是決定性判準。
4. **Beta vs TAIEX現貨日報酬**：對策略日報酬（`position.shift(1)*ret`）跟TAIEX現貨（`spot_close.pct_change()`）做OLS，beta=0.3597，corr=0.3217，r²=0.1035。**beta明顯非零**，代表這個訊號帶有實質的指數方向性曝險，不是原本便宜關卡sanity check暗示的「market-neutral timing edge」——這跟`FUT_MARATHON_STATE.md`第72輪記錄的逐年平均部位方向觀察（大多數年偏多）是一致的：訊號本身結構性偏多頭，不是真正對沖過的中性訊號。

**判定**：**深挖FAIL**。第72輪明確標記的最高優先疑慮——「82倍的擇時放大倍數（717x/8.79x）可能被少數大事件年份主導，不是穩定邊際優勢」——經本輪四項檢查逐一驗證後**完全成立**，最直接的證據是val期percentile=46.0，連隨機控制組中位數都沒贏過，這已經不是「統計顯著但缺乏經濟解釋所以打折扣」的情況，是更根本的「樣本外根本不成立」。cost-of-carry（roll yield收斂）這個經濟解釋本身在邏輯上仍然自洽（basis均值輕微貼水、跟台股相對高股息殖利率的方向一致），但**這個經濟解釋救不回這個具體實作的樣本外失敗**——經濟上說得通不代表統計上可靠，兩者是獨立的判準，這次剛好是「經濟解釋合理但統計驗證不通過」的案例，跟`MARATHON_PROTOCOL.md`原本預期的「統計顯著但沒有經濟解釋」剛好相反，值得記錄下來提醒之後不要把兩者混為一談。

**值得記錄的方法論教訓（給下一輪／下一個候選參考）**：本輪深挖是先跑完leave-one-year-out跟成本敏感度、beta，最後才做train/val切分——但train/val切分是**唯一直接證偽**這個候選的檢查（其他三項都只是提供背景資訊，即使它們全部「合理」，val期percentile=46.0本身就足以判定FAIL）。下一次遇到新的CHEAP_PASS候選要深挖時，**應該把train/val切分放在深挖清單的第一步**，如果那一步就不過，可以省下後面幾項檢查的時間直接記錄FAIL收工，不用照本輪這樣把四項都做完才發現問題（本輪這樣做是因為`fut_basis_carry`是期貨軌第一個深挖案例，想建立完整的deep-dive腳本範本供之後重用，所以刻意四項都寫，之後的候選不需要每次都照抄全部四項，可以視第一步結果決定要不要繼續）。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零額外FinMind API呼叫（`_load_series()`／`_load_basis()`／`fut_basis_series.build_basis_series()`全部命中既有全歷史parquet快取，跟第69/72輪一致）。

**已更新**：新增`deep_dive_fut_basis_carry.py`；`TRIALS_LEDGER.md`（新增#37，append-only，同時修正第9行累積總數說明文字從失準的33更新為37並補記中間幾輪忘記同步更新的落差）；`FUT_LEADS.md`（#17整列更新為深挖後的FAIL判定＋更新「目前狀態」／「下一輪建議」段落）；`FUT_MARATHON_STATE.md`（覆寫本輪完成段落＋更新「下一輪建議工作單位」／「下一步」段落）。

**下一輪建議**：basis家族第三個、也是最後一個方向——均值回歸（basis偏離自身歷史均值後的回歸傾向），用`fut_cheap_gate.py`既有的`_load_basis()`框架加新假說函式即可。如果這個新假說也通過便宜關卡，**深挖時把train/val切分放第一步**，不要等全部檢查做完才驗證樣本外穩健性。次要選項：盤別效應家族地基（`after_market`轉倉時點是否跟日盤同步，第63輪解決時序方向後留下的前置查證項）。

---

## 2026-08-26T02:05:00+08:00（馬拉松第80輪）期貨軌執行：basis家族第三個假說`fut_basis_mean_reversion_60d`便宜關卡（1a），CHEAP_PASS，待深挖

**選軌理由**：取鎖時偵測到`LOCK_STALE`（pid 134988持有約40.1分鐘，上一輪疑似異常中止，未留下對應log）。三軌時間戳比對，FUT最舊（2026-08-25T20:36:09），依協定選FUT。

**做了什麼**：依`FUT_MARATHON_STATE.md`第75輪「下一輪建議工作單位」#1，basis家族剩下唯一沒測的機制——均值回歸（basis偏離自身trailing 60日均值後的回歸傾向）。`fut_cheap_gate.py`新增`hyp_basis_mean_reversion(window=60)`，沿用既有`_load_basis()`（零額外API呼叫，命中`build_basis_series()`既有全歷史parquet快取）。position[t] = -sign(basis_pct[t] - basis_pct.rolling(60).mean().shift(1))，即今天basis比自身近60日均值更貼水則做多（賭回歸向上），更升水則放空。

結果：percentile=100.0（單測門檻90.0過），真實策略終值89.2392（+8823.9%累積，n_days=6125因60日warm-up損失部分樣本），隨機控制組中位數0.3433（-65.7%）。FUT軌獨立FDR家族第21筆試驗，最嚴格單測門檻100×(1-0.10/21)=99.52，同樣過。**CHEAP_PASS，排入待深挖清單**。

**誠實揭露（不能省略的警語）**：89.24x的終值放大幅度，跟#17`fut_basis_carry`（717.5x/8.79x≈82倍）同款模式——`fut_basis_carry`第75輪深挖已證實這種極端放大主要由2000-2002三個早期事件年份主導、2021-2024樣本外表現連隨機控制組都打不過。這次的89倍同樣需要用同等懷疑角度看待，**不能因為便宜關卡通過就當作候選宣傳**，深挖(1b)時第一步必須先做train/val切分（吸取第75輪教訓：train/val切分放第一步，若val不過直接記FAIL收工，不必照`fut_basis_carry`先例把四項檢查都做完才發現問題）。

**沒做的事**：沒有做深挖（1b），本輪只是便宜關卡（1a），依協定一輪做完一個有界工作單位就收工。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零額外FinMind API呼叫。

**已更新**：`fut_cheap_gate.py`（新增`hyp_basis_mean_reversion`，`main()`改跑本輪這個假說）、`TRIALS_LEDGER.md`（#38）、`FUT_LEADS.md`（#19＋目前狀態更新）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。**發現這台機器上有一份尚未commit的互動session工作（`research/REPORT.md`/`DATA.md`/`LEADS.md`/`TW_MARATHON_STATE.md`/多個TW軌程式碼檔案的修改＋數個新檔案），描述混合資料源架構上線、宇宙覆蓋率突破80%——這份工作不屬於本輪FUT軌範圍，本輪commit刻意排除這些檔案（`git add`只限定FUT軌相關檔案+心跳相關的`REPORT.md`/`MARATHON_STATE.md`），留給使用者或下一次互動session review後自行commit，避免把未經審閱的大量異動夾帶進自動馬拉松commit。**

**下一輪建議**：`fut_basis_mean_reversion_60d`深挖（1b），第一步先做train/val切分（不要照`fut_basis_carry`先例把四項都做完才發現問題）。basis家族三個機制（水位/動能/均值回歸）至此全部測完便宜關卡層級。

---

## 2026-08-26T06:20:00+08:00（馬拉松第86輪）期貨軌執行：`fut_basis_mean_reversion_60d`深挖（1b）完成，判定EXPERIMENTAL

**選軌理由**：取鎖時偵測到`LOCK_STALE`（pid 132832持有29.9分鐘，上一輪疑似異常中止，未留下log）。三軌最後更新時間戳比對：FUT（第80輪，2026-08-26T02:05）明顯比US（第84輪，05:02）、TW（第85輪，05:49）舊，依協定簡單輪替選FUT。

**做了什麼**：對`FUT_LEADS.md`#19（`fut_basis_mean_reversion_60d`，第80輪CHEAP_PASS）做1b深挖。新寫`deep_dive_fut_basis_mean_reversion_60d.py`，重用`deep_dive_fut_basis_carry.py`（#17深挖用的既有腳本）的`_matched_permutation_terminal()`配對式隨機控制組helper跟成本模型常數，只換掉position建構邏輯（60日trailing均值偏離的sign，而非水位本身的sign）。四項檢查，順序照協定：

1. **Train/Val切分**（`validation.holdout`的`TRAIN_END=2020-12-31`/`VAL_END=2024-12-31`）：TRAIN(2000-2020) period-local配對式隨機控制組percentile=100.0（real_eq=72.67x，+7167%）。**VAL(2021-2024) percentile=83.5**——贏過隨機控制組中位數（>50）但未達單測門檻90.0，real_eq=1.2118x（+21.2%），同期買進持有為+72.2%（策略跑輸買進持有，但仍贏隨機打散控制組）。train/val絕對報酬正負號一致（皆為正）——這點跟`f_quality_roe_stability`/`f_value_pb`那種「train/val正負號不一致」的EXPERIMENTAL模式不同，也跟#17`fut_basis_carry`（val=46.0連中位數都沒贏）明顯不同，是介於兩者之間的第三種模式。
2. **Leave-one-year-out**：前三大貢獻年份為2002(+151.5%)/2007(+80.8%)/2004(+50.7%)，排除這三年後終值從89.24x降到13.03x（只剩14.6%），跟#17拿掉2000-2002後只剩15.0%的集中度幾乎一樣。**這個訊號一樣高度依賴少數早期年份，集中度問題沒有比#17好。**
3. **成本敏感度1x/2x/3x**（round-trip 5/10/15bps，沿用#17深挖記錄的台指期期交稅為主近似假設）：89.24→37.76/15.97/6.75x，方向不變，3x後仍為+575%。
4. **Beta vs TAIEX現貨日報酬**：beta=0.0286，r²=0.0007。**這是本輪最大的正向發現**——遠比#17的beta=0.36更接近0，代表這個訊號確實比水位假說更接近真正的market-neutral timing edge，不是變相的方向性押注。

**判定：EXPERIMENTAL**（不是乾淨PASS，也不是像#17那樣的乾淨深挖FAIL）。理由：VAL期贏過隨機控制組中位數（比#17強），且beta近零（比#17乾淨很多），但VAL期沒有清楚跨過90.0的單測門檻，且LOYO集中度問題跟#17一樣沒解決——證據強度介於「乾淨PASS」跟「#17那種深挖FAIL」之間，誠實記錄成EXPERIMENTAL，不因為部分指標比#17好就直接升格候選使用。

**經濟解釋**（待驗證方向，非結論）：basis長期均值反映結構性cost-of-carry（預期股利殖利率淨融資成本，相對穩定），暫時偏離這個均值更可能反映期貨市場短期供需失衡（避險/投機部位暫時性推擠），失衡消退後應回歸——這個解釋邏輯自洽，但鑑於VAL證據不夠乾淨+LOYO集中度未解，不能單憑經濟解釋合理就升格使用。

**basis家族結案**：水位(#17)、動能(#18)、均值回歸(#19本輪)三個機制全部測完1a（+可行的1b），結果0 PASS、1 EXPERIMENTAL、2 FAIL。`MARATHON_PROTOCOL.md`第3節期貨候選清單原始的「期現價差」項目至此完整覆蓋，不需要再對這個機制找新變體。

**沒做的事**：沒有做分年份/regime的穩健性子樣本檢查（`FUT_LEADS.md`本輪備註列為可選的下一步，非硬性待辦）。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零新增FinMind API呼叫（`build_continuous_series()`/`build_basis_series()`都命中既有全歷史parquet快取）。

**已更新**：`deep_dive_fut_basis_mean_reversion_60d.py`（新增）、`TRIALS_LEDGER.md`（#43）、`FUT_LEADS.md`（#19＋目前狀態＋下一輪建議更新）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。**本輪commit範圍延續第80–85輪判斷**：只commit FUT軌相關檔案+心跳檔案(`REPORT.md`/`MARATHON_STATE.md`)+共用`TRIALS_LEDGER.md`（`TRIALS_LEDGER.md`附帶包含了第85輪TW軌尚未commit的`f_value_pb`深挖條目#42，因為append-only檔案裡兩筆新增緊鄰、沒有做patch層級拆分，誠實揭露這個範圍細節）。TW軌自己的狀態/log檔案跟互動session的混合資料源架構程式碼本輪依然刻意不動。

**下一輪建議**：basis家族已全部結案，可選方向見`FUT_LEADS.md`本輪更新——(a) 盤別效應家族（日盤/夜盤轉倉時點是否同步，尚未查）；(b) 期現價差以外的全新機制家族；(c) 若要進一步驗證均值回歸候選，可做分年代子樣本穩健性檢查，但非硬性待辦，記得FUT軌20%資源上限，不要連續佔用太多輪。

---

## 2026-08-26T08:33:39+08:00（馬拉松第90輪）期貨軌執行：盤別效應家族地基第二步——夜盤轉倉時點與日盤同步性驗證，結果乾淨無誤

**選軌理由**：取鎖時偵測到`LOCK_STALE`（pid 145052持有26.6分鐘，上一輪疑似異常中止）。核對後確認這個孤兒沒有留下任何未commit的FUT軌工作（`git status`／檔案mtime比對，唯一新增的是這輪自己寫的探測腳本；既有的三個modified檔案`TW_LEADS.md`/`TW_LOG.md`/`.github/workflows/quotes.yml`都是延續多輪的互動session工作，不屬於這次孤兒）——這次是「乾淨崩潰、沒有留下待核實的殘留工作」的情況，跟先前幾次「孤兒工作內容一致、補心跳收工」不同，本輪可以直接開始新的工作單位。三軌時間戳比對：FUT（第86輪，2026-08-26T06:20）明顯比US（第89輪，07:33）舊，依協定選FUT。

**做了什麼**：依`FUT_MARATHON_STATE.md`第86輪「下一輪建議」(a)項，basis家族結案後的下一個方向——盤別效應家族地基第二步。第63輪已解決夜盤`date`欄位時序方向（夜盤標示日期T代表T前一晚至T清晨，是日盤T的前哨），但轉倉時點（前月合約消失、次月合約成為主連的那個切換日）是否跟日盤同步，第63輪明確標記為未查、動工前必須先確認的風險項。

新寫`fut_probe_night_session_rollover.py`：重用`continuous_contract.py`既有的`load_position_session()`/`front_month_series()`（日盤半邊零改動、零新API呼叫），對夜盤（`after_market`）套用同一套「每日最小`contract_date`且當日收盤價非空」規則獨立算出夜盤自己的主連序列跟轉倉事件日期，再直接比對日盤／夜盤的轉倉日期集合（限定在夜盤有資料的範圍內，即2017-05-16起，避開2017年以前日盤獨有的轉倉事件造成的假性不匹配）。

**結果：完全同步，零例外。** 比較窗內日盤轉倉事件92筆、夜盤轉倉事件92筆，**逐一比對日期集合，92/92筆日期完全相同（exact match），沒有任何一筆需要靠「最近日期」去猜測偏移量**——即日盤跟夜盤在同一個`date`標籤下同時完成從舊主連合約切換到新主連合約，沒有領先或落後一個交易日的情況。前5筆逐筆核對（2017-05-18/06-22/07-20/08-17/09-21）日盤夜盤完全一致，符合機制上的預期：第63輪確立的時序關係下，標示日期T的夜盤代表「T前一晚到T清晨」，落在舊合約結算日（日盤最後出現日）之後、次一個交易日日盤開盤之前，理論上就應該跟日盤在同一個`date`一起切換到新合約——這輪是把這個理論預期用全歷史比較日期集合的方式做了實測驗證，不是只靠邏輯推論。

**這代表什麼**：第60/63輪標記的「盤別效應家族動工前必須先查證轉倉時點是否同步」這個前置風險項**已解決，結果是好消息**——不需要為夜盤另外設計一套獨立的轉倉規則，日盤既有的H1規則（`continuous_contract.py`的「smallest contract_date that has data today」）可以直接沿用同一組轉倉事件日期套用到夜盤序列上，兩個session的主連合約邊界完全對齊。

**沒做的事**：沒有寫夜盤感知的連續序列建構本身（`continuous_contract.py`目前仍只处理`position` session），也沒有測任何盤別效應假說——本輪只做地基驗證（1c），依協定一輪一個有界工作單位收工。下一輪如果要繼續這個方向，可以直接寫`build_night_continuous_series()`或擴充現有函式支援session參數，不需要再重新驗證轉倉同步性。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零新增FinMind API呼叫（`load_position_session()`／`load_dev("TaiwanFuturesDaily", "TX", ...)`兩者都命中既有全歷史parquet快取，同`fut_probe_night_session.py`先例）。

**已更新**：新增`fut_probe_night_session_rollover.py`；`FUT_LEADS.md`（地基狀態備註更新，見下方）；`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。**沒有新增`TRIALS_LEDGER.md`列**（地基驗證不是假說測試，同第39/60/63輪先例）。本輪commit範圍延續第80–89輪判斷：只commit FUT軌相關檔案+心跳檔案(`REPORT.md`/`MARATHON_STATE.md`)，TW軌互動session未commit變更（`TW_LEADS.md`/`TW_LOG.md`/`.github/workflows/quotes.yml`）依然刻意排除不動。

**下一輪建議**：(a) 寫夜盤感知的連續序列建構（轉倉同步性已確認，可以直接沿用日盤轉倉事件日期，風險降低）；(b) 或換一個全新機制家族測試假說（`MARATHON_PROTOCOL.md`第3節清單）；(c) 記得FUT軌資源配置上限20%，不要連續佔用太多輪，若TW/US軌有更高優先待辦應優先讓給那兩軌。

---

## 2026-08-26T10:34:09+08:00 — 馬拉松第93輪期貨軌執行：夜盤感知連續序列建構（1c地基改動）

**選軌理由**：`marathon_lock.py acquire` 成功（乾淨`LOCK_ACQUIRED`，非陳舊鎖檔）。比對三軌最後更新時間戳：FUT（第90輪，08:33）／US（第91輪，09:04）／TW（第92輪，約09:35–10:06）——FUT最久沒被碰，選期貨軌。同時確認FUT軌資源配置20%上限：近10輪（83–92）FUT只佔2輪（86、90）=20%，選這輪不算連續佔用超額。

**做了什麼**（照`FUT_MARATHON_STATE.md`第90輪「下一輪建議」第1項）：
1. 讀`continuous_contract.py`確認`load_position_session()`/`front_month_series()`/`rollover_events()`三個函式本身不寫死session（只有`load_position_session()`寫死`trading_session == "position"`），代表夜盤支援可以用最小改動達成：把session過濾邏輯抽成通用的`load_session(contract, session, start_date, end_date)`，`load_position_session()`改成薄包裝（保留原簽章給既有7個呼叫端，零破壞性變更）；`build_continuous_series()`新增`session: str = "position"`參數（預設值不變，既有呼叫端`build_continuous_series()`／`build_continuous_series(contract, start_date, end_date)`兩種呼叫方式都不受影響）。
2. 更新模組docstring說明夜盤支援的依據：round 63（夜盤`date`標籤代表「前一晚到當天清晨」，領先日盤）+ round 90（轉倉事件日期跟日盤完全同步，92/92 exact match）——這兩輪的查證結果是這次改動敢直接重用`front_month_series()`/`rollover_events()`而不用另外設計夜盤專屬轉倉邏輯的依據，不是憑空假設。**特別注意**：夜盤序列的比價調整因子是用夜盤自己的收盤價算出來的（不是複製日盤的比率），因為同一天同一合約日盤/夜盤收盤價本來就不同，混用會算錯。
3. **雙重驗證，不只信任「能跑起來」**：新寫`fut_validate_night_continuous_series.py`，獨立重跑一次round 90的方法（直接呼叫`fut_probe_night_session_rollover.py`的`_night_front_month_series()`/`_switch_dates()`，完全不經過這輪新寫的`load_session()`/`build_continuous_series()`），比對兩條獨立路徑算出的轉倉日期集合是否完全一致。**結果：92/92轉倉事件、日期集合`exact match: True`，零差異**。另外檢查：1867列涵蓋2017-05-16～2024-12-31，`open`/`max`/`min`/`close`/`adj_*`八個欄位NaN皆為0、無非正值價格、`open_interest`全為0（跟round 60發現一致，不是bug）、0筆skipped events。
4. **回歸測試**：重跑`python continuous_contract.py`（既有`__main__`區塊），確認日盤（預設session）路徑結果跟改動前完全一致——6185個交易日、300次轉倉事件、0筆skipped，數字跟`FUT_MARATHON_STATE.md`／`FUT_CONTINUOUS_CONTRACT_DESIGN.md`一路記錄的基準完全吻合，沒有意外改變既有行為。另外`python -c "import fut_basis_series, fut_cheap_gate, fut_drift_probe"`確認三個既有呼叫端模組匯入無誤。

**沒有測任何策略假說，沒有新增`TRIALS_LEDGER.md`列**（這是地基建設，1c類，同第39/60/63/90輪先例——`build_night_continuous_series`還沒被拿去測任何盤別效應假說，只是把「能建構」這件事做出來並驗證乾淨）。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。**全程零新增FinMind API呼叫**——`fut_validate_night_continuous_series.py`跟回歸測試都命中既有全歷史parquet快取（跟round 90/60同一批快取鍵），沒有打過任何新的網路請求。

**已更新**：`continuous_contract.py`（新增`load_session()`、`load_position_session()`改包裝、`build_continuous_series()`新增`session`參數、docstring更新）；新增`fut_validate_night_continuous_series.py`；`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。**沒有動`FUT_LEADS.md`**（沒有候選判定產生，這輪是純地基）。本輪commit範圍延續第80–92輪判斷：只commit FUT軌相關檔案+心跳檔案(`REPORT.md`/`MARATHON_STATE.md`)，TW軌互動session未commit變更（`.github/workflows/quotes.yml`）依然刻意排除不動。

**下一輪建議**：(a) **現在可以真正開始測盤別效應假說了**——地基（`build_continuous_series(session="after_market")`）已就緒且雙重驗證過，例如「夜盤報酬vs日盤報酬」「隔夜跳空（日盤收盤→夜盤開盤，或夜盤收盤→日盤開盤，注意round 63確認的時序方向：夜盤T領先日盤T）」等第一批假說可以直接用便宜關卡框架（`fut_cheap_gate.py`）加新的資料載入函式測試，不用再處理地基問題；(b) 或換一個全新機制家族（`MARATHON_PROTOCOL.md`第3節清單裡還沒測過的）；(c) 記得FUT軌資源配置上限20%，不要連續佔用太多輪。

---

## 2026-08-26T13:05:49+08:00 — 馬拉松第98輪期貨軌執行：盤別效應家族第一批假說（夜盤自身報酬 vs 日盤報酬），2個都FAIL

**選軌理由**：`marathon_lock.py acquire`成功（乾淨`LOCK_ACQUIRED`，非陳舊鎖檔）。比對三軌最後更新時間戳：FUT（第93輪，2026-08-26T10:34:09）／TW（第96輪，12:08:18）／US（第97輪，12:15）——FUT明顯最舊。資源配置檢查：近10輪（89–97）FUT只佔2輪（90、93）=20%，選這輪後（89–98窗口）變成3/10=30%，仍在協定「不要連續佔用太多輪」的精神下可接受（不是連續兩輪，中間隔了94–97共4輪TW/US），下一輪起應優先讓給TW/US。

**做了什麼**：依`FUT_MARATHON_STATE.md`第93輪「下一輪建議」(a)項——夜盤感知連續序列建構（`build_continuous_series(session="after_market")`）已在第93輪雙重驗證過，這輪第一次真正拿它來測假說，而不是只驗證地基。`fut_cheap_gate.py`新增`_load_session_pair(series)`：把日盤系列（`_load_series()`既有輸出）跟夜盤自己的`build_continuous_series(session="after_market")`輸出，用`date`欄位inner join（round 63確認夜盤date T代表「T前一晚到清晨」，領先日盤同date T，round 90/91確認轉倉事件完全同步，這個inner join不會有主連合約錯位問題）。算出`night_ret`（夜盤自身open→close）跟`day_ret`（日盤自身open→close，重新算而非沿用`series["ret"]`那個跨日close-to-close定義），兩個假說：

1. **`fut_night_session_momentum`**：`position = sign(night_ret)`，順著夜盤方向交易同一date T的日盤日內報酬。
2. **`fut_night_session_reversal`**：`position = -sign(night_ret)`，反向操作（跟#14/#15隔夜跳空反轉/順勢同款「同一輪測兩個方向」設計，不是調參數硬救）。

兩者都用`_permutation_test_same_day()`（既有函式，同date配對不跨日shift，跟隔夜跳空假說相同的配對邏輯）。

**結果**：

| 假說 | percentile（單測門檻90.0） | 判定 |
|---|---|---|
| `fut_night_session_momentum` | 19.0（方向不對，81%隨機排列贏過真實策略） | **FAIL** |
| `fut_night_session_reversal` | 81.0（方向正確但強度不夠） | **FAIL** |

真實策略終值：動能版0.7284（-27.2%累積），反轉版1.2365（+23.7%累積）；隨機控制組中位數：動能版0.9630（-3.7%），反轉版0.9357（-6.4%）。n_days=1861（夜盤資料起始於2017-05-16，比日盤全歷史2000-2024短，同`_load_basis()`/`_load_institutional_net_position()`的inner join精神）。

**誠實記錄**：反轉版（81.0）方向正確、也贏過隨機控制組中位數，但離90.0單測門檻還有距離，不是「差一點點過批次校正」那種模糊地帶（跟#33`fut_intraday_gap_continuation`的92.0剛好過單測但沒過批次校正不同——這裡連單測都沒過），依協定誠實記錄FAIL，不排入待深挖清單，也不因為方向正確就調整訊號定義硬救。

**沒做的事**：沒有測日盤收盤→夜盤開盤／夜盤收盤→日盤開盤這兩個「跳空」構造（跟#14/#15已測的日盤自身跳空是不同的資料，這兩個gap還沒測），也沒有測夜盤多日累積報酬（本輪只測夜盤單日open→close），留給下一輪。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零新增FinMind API呼叫（`build_continuous_series(session="after_market")`／`_load_series()`都命中既有全歷史parquet快取，同第93輪先例）。

**已更新**：`fut_cheap_gate.py`（新增`_load_session_pair()`/`hyp_night_session_momentum`/`hyp_night_session_reversal`，`main()`改跑本輪兩個假說，模組docstring新增「Tenth round」段落）、`TRIALS_LEDGER.md`（#55/#56）、`FUT_LEADS.md`（#20/#21＋目前狀態＋下一輪建議更新）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。

**下一輪建議**：(a) 盤別效應家族第二批——日盤收盤(T-1)→夜盤開盤(T)、夜盤收盤(T)→日盤開盤(T)兩個跳空構造（跟#14/#15的日盤自身跳空不同資料），或夜盤多日累積報酬；(b) 換一個全新機制家族；(c) FUT軌資源配置20%上限，近10輪含本輪已佔30%，下幾輪優先讓給TW/US。

## 2026-08-26T17:05:24+08:00 — 馬拉松第104輪期貨軌執行：盤別效應家族第二批假說（日盤收盤(T-1)→夜盤開盤(T)跳空，反轉/順勢），2個都FAIL

**選軌理由**：`marathon_lock.py acquire`成功（乾淨`LOCK_ACQUIRED`，非陳舊鎖檔）。比對三軌最後更新時間戳：FUT（第98輪，2026-08-26T13:05:49）／TW（第102輪，16:06:04）／US（第103輪，16:38:29）——FUT明顯最舊。資源配置檢查：近10輪（95–104，含本輪）FUT只佔2輪（98、本輪104）=20%，剛好在協定20%上限之內，未超額。

**做了什麼**：依`FUT_MARATHON_STATE.md`第98輪「下一輪建議」(a)項——盤別效應家族第二批：日盤收盤(T-1)→夜盤開盤(T)這個跳空構造（跟round 98測的「夜盤自身完整open→close報酬」是不同資料，也跟#14/#15測的「日盤自身跳空」是不同資料）。`fut_cheap_gate.py`新增`hyp_night_gap_reversal`/`hyp_night_gap_continuation`：重用既有`_load_session_pair()`（round 98新增，零改動）已經算好的`night_open`/`adj_close`欄位，新增`gap = merged["night_open"] / merged["adj_close"].shift(1) - 1.0`（日盤T-1收盤→夜盤T開盤的跳空），預測目標是夜盤T自己的open→close報酬（`night_ret`，同`_load_session_pair()`既有欄位，不是`day_ret`——這個跳空領先進入夜盤，理應預測的是夜盤自己接下來的走勢，不是日盤）。結構上直接對應#14/#15（`series["adj_close"].shift(1)`算日盤自身跳空、預測日盤自身`intraday_ret`），只是把「開盤後接續的那個session」從日盤換成夜盤。兩個方向（反轉/順勢）同一輪測試，跟#14/#15、round 98#20/#21同款「同一輪測相反方向」設計，不是調參數硬救。

**結果**：

| 假說 | percentile（單測門檻90.0） | 判定 |
|---|---|---|
| `fut_night_gap_reversal` | 17.5（方向不對） | **FAIL** |
| `fut_night_gap_continuation` | 82.5（方向正確但強度不夠） | **FAIL** |

真實策略終值：反轉版1.9904（+99.0%累積），順勢版0.4630（-53.7%累積）；隨機控制組中位數：反轉版2.0993（+109.9%），順勢版0.4390（-56.1%）。n_days=1860（首列因`.shift(1)`產生NaN被`_permutation_test_same_day`的`notna()`過濾排除，1861-1）。

**誠實記錄**：順勢版（82.5）方向正確、贏過隨機控制組中位數，但離90.0單測門檻還有7.5個百分點差距——不是round 98`fut_night_session_reversal`（81.0）或#15`fut_intraday_gap_continuation`（92.0剛好過單測但沒過批次校正）那種模糊地帶，這裡連單測都沒過，依協定誠實記錄FAIL，不排入待深挖清單，也不因為方向正確就調整訊號定義硬救。

**沒做的事**：round 98標記的第二種跳空構造（夜盤收盤(T)→日盤開盤(T)，預測目標應為`day_ret`）本輪沒有測，留給下一輪；也沒有測夜盤多日累積報酬。依協定一輪最多測2-3個假說，測完收工。

**Holdout檢查**：本輪開始前跟結束前都跑`is_holdout_consumed()` → `False`。全程零新增FinMind API呼叫（`_load_session_pair()`／`build_continuous_series(session="after_market")`都命中既有全歷史parquet快取，同第98輪先例）。

**已更新**：`fut_cheap_gate.py`（新增`hyp_night_gap_reversal`/`hyp_night_gap_continuation`，`main()`改跑本輪兩個假說，模組docstring新增「Eleventh round」段落）、`TRIALS_LEDGER.md`（#65/#66）、`FUT_LEADS.md`（#22/#23＋目前狀態＋下一輪建議更新）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。

**下一輪建議**：(a) 盤別效應家族第三批——夜盤收盤(T)→日盤開盤(T)第二種跳空構造，預測目標改為`day_ret`（資料已現成，`_load_session_pair()`已有`night_close`/`adj_open`兩欄，不需要新地基），或夜盤多日累積報酬；(b) 換一個全新機制家族；(c) FUT軌資源配置20%上限，近10輪含本輪剛好20%，下一輪若還選FUT要重新盤點窗口是否超額。

---
## 2026-08-26T19:34:28+08:00 — 馬拉松第109輪：盤別效應家族第三批（進入日盤前的跳空）——夜盤收盤(T)→日盤開盤(T)，round98/104留下的最後一種跳空構造

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔，上一輪無殘留孤兒工作）。

**選軌**：讀三軌state檔案「最後更新」時間戳——TW 19:45（round107）、US 19:05（round108）、FUT 17:05:24（round104，最舊）。檢查FUT近10輪（99-108）資源配置：99TW/100US/101TW/102TW/103US/104FUT/105TW/106US/107TW/108US，FUT僅佔1/10=10%，遠低於20%上限，可以選FUT。

**做的事**：延續round104`FUT_LEADS.md`#23「夜盤收盤(T)→日盤開盤(T)這個第二種跳空構造尚未測試，留給下一輪」的明確待辦。`fut_cheap_gate.py`新增`hyp_day_gap_reversal`/`hyp_day_gap_continuation`，重用`_load_session_pair()`既有`night_close`/`adj_open`欄位（round98/104建立的地基，零新資料/零新API）。跟#22/#23（測日盤T-1收盤→夜盤T開盤的跳空，預測夜盤T自身`night_ret`）互為鏡像，本批測夜盤T收盤→日盤T開盤的跳空（round63時序：夜盤T在日盤T之前，仍屬同一date T標籤，非跨日位移，同樣用`_permutation_test_same_day`），能否預測日盤T自身`day_ret`（open→close）。

**結果**：
- `fut_day_gap_reversal`（反轉版）：percentile=0.5（門檻90.0），方向嚴重不對，199/200隨機排列贏過真實策略（真實-35.9% vs 隨機中位數-17.2%）。**FAIL**，不需要經濟解釋。
- `fut_day_gap_continuation`（順勢版）：percentile=99.5（單測門檻90.0過；本批n=2 BH門檻k=1時95.0過），真實策略終值+40.5% vs 隨機控制組中位數+8.7%。**但累積FUT家族FDR校正未過**——FUT家族累積試驗數由27→29（本批+2），保守單測門檻100×(1-0.10/29)=99.66，99.5未達，差距僅0.15個百分點，落在`N_SHUFFLES=200`排列解析度（0.5個百分點步階）以內，可能是測量雜訊偏低估而非真正未達標。判定**CHEAP_PASS（單測+本批），累積FDR校正邊界未過，不排入待深挖清單**——這是FUT軌盤別效應家族至今第一次出現「邊界模糊、疑似解析度雜訊」而非清楚判定的案例，同round51→54`fut_intraday_gap_continuation`高解析度重測先例（那次N=2000重測後92.0→89.60反而確認FAIL，證明「重測不一定會讓邊界案例翻盤成PASS」，這次結果需要真的跑過N=2000才能定論，不能預設方向）。

**盤別效應家族現況**：round98第一批（夜盤自身完整報酬）2 FAIL、round104第二批（進入夜盤前的跳空）2 FAIL、本輪第三批（進入日盤前的跳空）1 FAIL+1邊界候選——家族累計6個假說：5 FAIL、1邊界候選，三種跳空/報酬構造全部測完，家族本身可視為已窮盡已知構造。

**holdout檢查**：`python -c "from validation.holdout import is_holdout_consumed; print(is_holdout_consumed())"` → `False`。

**已更新**：`fut_cheap_gate.py`（新增`hyp_day_gap_reversal`/`hyp_day_gap_continuation`，`main()`改跑本輪兩個假說，模組docstring更新指出round98/104的兩個gap構造均已測完）、`TRIALS_LEDGER.md`（#70/#71）、`FUT_LEADS.md`（#24/#25）、`FUT_MARATHON_STATE.md`（覆寫本輪完成段落）。

**下一輪建議**：(a) 對`fut_day_gap_continuation`用`N_SHUFFLES=2000`高解析度重測確認邊界結果（同round54先例，monkey-patch局部覆蓋，不改`fut_cheap_gate.py`本身預設值），這是唯一一個FUT軌目前處於「不確定」而非清楚FAIL的1a層級案例，值得優先釐清；(b) 若(a)確認FAIL，盤別效應家族三批構造全部窮盡，應換一個全新機制家族（`MARATHON_PROTOCOL.md`第3節期貨清單裡「日內均值回歸」以外的變體、或星期效應以外的季節性）；(c) FUT軌資源配置20%上限，近10輪（100-109）含本輪：100US/101TW/102TW/103US/104FUT/105TW/106US/107TW/108US/109FUT，FUT佔2/10=20%，剛好觸頂，下一輪若還選FUT要先重新盤點是否超額。

---

## 第112輪（2026-08-26T21:32+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 20:37、US 21:03（第111輪剛更新）、FUT 19:34（最舊）。正常輪替本應選FUT。

**為何跳過**：FUT軌目前唯一明確的「下一步」待辦是對round109`fut_day_gap_continuation`（邊界模糊候選，累積FDR校正差0.15個百分點未過）用`N_SHUFFLES=2000`高解析度重測。這雖然不是「全新假說」，但本質是1b層級的深挖驗證，目的是推進一個因子候選的最終判定——跟第111輪處理US round108「驗證PE因子分子」待辦時的判斷邏輯一致：使用者的暫停規則寫的是「不分軌道」禁止任何單因子相關工作（1a便宜關卡或1b深挖皆然），不因為候選不是全新假說就破例。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格，跟FUT軌完全無關，本輪也沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認狀態（`is_holdout_consumed()`為`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第118輪（2026-08-27T03:31+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 02:43（第116輪）、US 03:01（第117輪）、FUT 02:01（第115輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「待使用者確認」，`git log`確認自第117輪以來無新使用者互動session介入，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選用`N_SHUFFLES=2000`高解析度重測；或另立全新因子家族）本質仍是單因子相關工作（不管是既有候選深挖還是全新假說掃描），屬於暫停規則「不分軌道」禁止的範圍——跟round109/112/115判斷邏輯完全一致。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格，跟FUT軌無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第115輪（2026-08-27T02:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 01:20（第113輪）、US 01:31（第114輪）、FUT 21:32 Aug26（第112輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「待使用者確認」，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選用`N_SHUFFLES=2000`高解析度重測）本質是1b層級深挖驗證，目的是推進一個因子候選的最終判定，屬於暫停規則「不分軌道」禁止的單因子相關工作——跟round111（US）、round112（FUT）、round114（US）判斷邏輯完全一致，不因為候選不是全新假說就破例。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格，跟FUT軌無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第121輪（2026-08-27T05:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 04:21（第119輪）、US 04:32（第120輪，最新）、FUT 03:31（第118輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第1行仍「待使用者確認」；`git log`確認自`cb5976d`（第120輪，US跳過）以來沒有新的使用者互動session commit（下一筆就是本輪），暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選高解析度重測，或另立新因子家族）本質仍是單因子相關工作，跟round109/112/115/118判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：工作目錄偵測到`.github/workflows/market.yml`有未commit的修改，非本輪造成、疑似先前自動報價流程遺留。依協定本輪commit範圍限定FUT軌相關檔案+心跳檔案，刻意不動這個檔案。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第124輪（2026-08-27T06:32+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 05:20（第122輪）、US 06:01（第123輪，最新）、FUT 05:01（第121輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log`確認自`05d290f`（第123輪，US跳過）以來沒有新的使用者互動session commit（下一筆就是本輪），暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選高解析度重測，或另立新因子家族）本質仍是單因子相關工作，跟round109/112/115/118/121判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：工作目錄仍偵測到`.github/workflows/market.yml`有未commit的修改（自第121輪起已連續多輪觀察到同一項），非本輪造成、疑似先前自動報價流程遺留。依協定本輪commit範圍限定FUT軌相關檔案+心跳檔案，刻意不動這個檔案。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第127輪（2026-08-27T08:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 07:14（第125輪）、US 07:32（第126輪，最新）、FUT 06:32（第124輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第1行仍「狀態：待使用者確認」；`git log`發現自`15098b5`（第126輪，US跳過）以來有一筆新commit`7b4fe7d`（新增`data/STATUS.json`給Cowork讀的單一事實來源），但該commit只動了`PROGRESS.md`/`data/STATUS.json`/`generate_status_json.py`三個檔案，未觸及`PORTFOLIO_STRATEGY_SPEC.md`，內容也跟解除暫停規則無關，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選高解析度重測，或另立新因子家族）本質仍是單因子相關工作，跟round109/112/115/118/121/124判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`確認工作目錄乾淨，沒有偵測到先前幾輪反覆提到的`.github/workflows/market.yml`未commit修改——該問題看來已在某次自動化流程或互動session中被自然解決，不需要額外處理。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第130輪（2026-08-27T09:31+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 08:43（第128輪）、US 09:01（第129輪，最新）、FUT 08:01（第127輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第1行仍「狀態：待使用者確認」；`git log`確認自`449e7ad`（第129輪，US跳過）以來只有自動報價流程的commit（`7354151`），沒有新的使用者互動session介入，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round109留下：對`fut_day_gap_continuation`邊界候選高解析度重測，或另立新因子家族）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round109的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`確認工作目錄乾淨，沒有偵測到`.github/workflows/*.yml`未commit修改。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第133輪（2026-08-27T11:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 10:22（第131輪）、US 10:33（第132輪，最新）、FUT 09:31（第130輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log`確認自`25883f5`（第132輪，US跳過）以來有三筆新commit（`28e1120`/`56ac814`/`e9c09af`，皆為互動session的自選股sparkline/融資維持率標示/金融股資料bug修正），跟解除暫停規則無關，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`確認工作目錄乾淨，沒有偵測到未commit的殘留修改。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第136輪（2026-08-27T12:31+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 11:37/11:38（第134輪）、US 10:32/12:02（第135輪，最新）、FUT 11:01/11:02（第133輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log`確認自`345fbcb`（第133輪，FUT跳過）以來有四筆新commit（`e9c09af`/`56ac814`/`28e1120`皆為互動session的自選股sparkline/融資維持率標示/金融股資料bug修正，`25883f5`/`ce55cc3`/`4a8750d`/`342ff81`皆為第131/132/134/135輪TW/US軌自動輪次），沒有任何一筆觸及`PORTFOLIO_STRATEGY_SPEC.md`本身，跟解除暫停規則無關，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`偵測到`research/generate_scores_v2.py`有一筆未commit的修改（新增`import json`一行），非本輪造成、疑似互動session遺留的未完成小改動。依協定本輪只commit FUT軌相關檔案+心跳檔案，刻意不動這個不相關的檔案。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第139輪（2026-08-27T14:02+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——TW 13:04（第137輪）、US 13:31（第138輪，最新）、FUT 12:31（第136輪，最舊）。正常輪替本應選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；改用`git log -- PORTFOLIO_STRATEGY_SPEC.md`直接確認該檔案自唯一一次建立commit（`fa369b9`）以來完全沒有新commit觸及過（比逐一檢查中間commit內容更直接），暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133/136判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`確認工作目錄乾淨——上一輪（第136輪）記錄的`research/generate_scores_v2.py`未commit修改（`import json`一行）本輪已不存在，應已由互動session一併處理收尾。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第142輪（2026-08-27T15:31+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——FUT 14:02（第139輪，最舊）、TW 14:52（第140輪）、US 15:01（第141輪，最新）。依輪替選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log -- PORTFOLIO_STRATEGY_SPEC.md`確認該檔案自唯一一次建立commit（`fa369b9`）以來完全沒有新commit觸及過，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133/136/139判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`（在本輪開始時）確認工作目錄乾淨，沒有遺留的未commit修改。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第145輪（2026-08-27T17:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——FUT 15:31（第142輪，最舊）、TW 16:07（第143輪）、US 16:32（第144輪，最新）。依輪替選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log -- PORTFOLIO_STRATEGY_SPEC.md`確認該檔案自唯一一次建立commit（`fa369b9`）以來完全沒有新commit觸及過，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133/136/139/142判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`（在本輪開始時）確認工作目錄乾淨，沒有遺留的未commit修改。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第148輪（2026-08-27T19:01+08:00）——跳過，暫停規則生效中

**取鎖**：乾淨（`LOCK_ACQUIRED`，非陳舊鎖檔）。

**選軌判斷**：三軌state檔案「最後更新」時間戳——FUT 17:01（第145輪，最舊）、TW 18:23（第146輪）、US 18:32（第147輪，最新）。依輪替選FUT。

**為何跳過**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」；`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認該檔案自唯一一次建立commit（`fa369b9`）以來完全沒有新commit觸及過，暫停規則整體仍完全生效中。FUT軌唯一明確的「下一步」待辦（round104留下：盤別效應第三批跳空構造、或另立新因子家族；round86的`fut_basis_mean_reversion_60d` regime穩健性檢查為次要待辦）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133/136/139/142/145判斷邏輯完全一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬多因子規格（圍繞TAIEX/TWSE），跟FUT軌完全無關，本輪沒有組合策略相關工作可做。依`MARATHON_PROTOCOL.md`第0節第3點，本輪直接跳過整輪，不動`fut_cheap_gate.py`或任何因子/回測程式碼。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（複查結果：`False`）、補寫這則log跟`FUT_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round104的「下一步」1–4項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

**額外觀察**：`git status`（在本輪開始時）確認工作目錄乾淨，沒有遺留的未commit修改。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-27T22:01:00+08:00 — 馬拉松第151輪：跳過（暫停規則仍生效，無組合策略工作可做）＋收尾第150輪積壓commit

**取鎖時偵測到`LOCK_STALE`**（pid 96956, 89.9分鐘沒更新，自動回收）。檢查`git status`發現確有四份未commit的修改（`REPORT.md`/`MARATHON_STATE.md`/`US_MARATHON_STATE.md`/`US_LOG.md`），逐一比對內容確認是第150輪（US軌，跳過判定）完整寫完的記錄，只是卡在commit這一步沒做完（研判是session額度/連線中斷，不是內容寫壞），**不重做，直接沿用並在本輪一併commit+push**。

三軌時間戳：FUT 19:01（第148輪，最舊）、TW 19:31（第149輪）、US 20:32（第150輪，最新）——依輪替選FUT。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。FUT軌依舊沒有組合策略相關工作可做（規格書全部圍繞TAIEX/TWSE台股樣本，跟FUT軌無關），FUT軌唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族，round104留下）本質仍是單因子相關工作，跟round109/112/115/118/121/124/127/130/133/136/139/142/145/148判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳，並收尾第150輪積壓的commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T01:01+08:00 — 馬拉松第154輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（第153輪正常結束）。三軌時間戳：FUT 22:01（第151輪，最舊）、TW 00:06（第152輪）、US 00:31（第153輪，最新）——依輪替選FUT。

**判斷過程**：複查`PORTFOLIO_STRATEGY_SPEC.md`（第3行）仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本）。FUT軌round104留下的唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族）本質仍是單因子相關工作，同round109/112/115/118/121/124/127/130/133/136/139/142/145/148/151連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳。

**額外發現**：`git status`顯示有不屬於本輪的未commit修改（`index.html`／`research/generate_scores_momentum.py`／`research/weights_frozen_momentum.json`已修改；`_tmp_backfill_gaps2.log`／`research/backfill_price_history_gaps.py`為新檔案），研判是另一個互動session正在進行的工作，依規則不觸碰、不commit、不刪除，本輪commit範圍只限心跳/記錄檔。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T05:31+08:00 — 馬拉松第163輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（第162輪US軌正常結束，判定跳過未做實質工作）。三軌時間戳：FUT 04:01（第160輪，最舊）、TW 04:31（第161輪）、US 05:01（第162輪，最新）——依輪替選FUT。

**判斷過程**：複查`PORTFOLIO_STRATEGY_SPEC.md`（第3行）仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本）。複查`git log`確認自第160輪以來新增的commit（`9a0fd2b`／`99b7733`／`718a5f9`／`1b9fcc2`／`0e62a50`／`96c2557`／`6dc99f8`／`ff5bcbb`）皆屬互動session的B23/B24研究工作或馬拉松自身跳過紀錄，未觸及`PORTFOLIO_STRATEGY_SPEC.md`。FUT軌round104留下的唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳。

**額外發現**：本輪開始時`git status`乾淨（跟第162輪結束時一致），無不屬於本輪的殘留變更。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T04:01+08:00 — 馬拉松第160輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（第159輪US軌正常結束，判定跳過未做實質工作）。三軌時間戳：FUT 02:31（第157輪，最舊）、TW 03:18（第158輪）、US 03:31（第159輪，最新）——依輪替選FUT。

**判斷過程**：複查`PORTFOLIO_STRATEGY_SPEC.md`（第3行）仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本）。FUT軌round104留下的唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳。

**額外發現**：`git status`顯示有不屬於本輪的未commit新檔案（`research/_tmp_pit3.log`），研判是另一個互動session正在進行PIT回測相關工作，依規則不觸碰、不commit、不刪除，本輪commit範圍只限心跳/記錄檔。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T02:31+08:00 — 馬拉松第157輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（第156輪正常結束）。三軌時間戳：FUT 01:01（第154輪，最舊）、TW 01:31（第155輪）、US 02:01（第156輪，最新）——依輪替選FUT。

**判斷過程**：複查`PORTFOLIO_STRATEGY_SPEC.md`（第3行）仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本）。FUT軌round104留下的唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳。

**額外發現**：`git status`顯示有不屬於本輪的未commit修改（`_tmp_backfill3.log`／`_tmp_pit_backtest.log`／`research/run_value_board_v2_pit_backtest.py`皆為新檔案），研判是另一個互動session正在進行PIT回測相關工作，依規則不觸碰、不commit、不刪除，本輪commit範圍只限心跳/記錄檔。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T07:01+08:00 — 馬拉松第166輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（第165輪US軌正常結束）。三軌時間戳：FUT 05:31（第163輪，最舊）、TW 06:13（第164輪）、US 06:32（第165輪，最新）——依輪替選FUT。

**判斷過程**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第164輪的里程碑記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）也都已達標，目前三軌皆無已知允許的工作單位可做。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`FUT_MARATHON_STATE.md`附記、心跳。

**額外發現**：`git status`本輪開始時乾淨（開工前先把第165輪遺留的1個未push commit補push上去，見`REPORT.md`第166輪心跳附記）。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 2026-08-28T08:32:00+08:00 — 馬拉松第169輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨。三軌時間戳：FUT 07:01（第166輪，最舊）/TW 07:33（第167輪）/US 08:01（第168輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改，推測是`6d98d64`速率限制修正之後持續運作的模組寫入狀態）、`research/pit_run_500.log`（未追蹤，推測跟同一session的B24 PIT回測500檔擴大測試有關）。兩者皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---
## 2026-08-28T11:31+08:00 — 馬拉松第175輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 10:01（第172輪，最舊）/TW 10:31（第173輪）/US 11:01（第174輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`再度發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改）、`research/pit_run_500.log`（未追蹤），跟第169–174輪記錄的殘留一致，皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---
## 2026-08-28T10:01+08:00 — 馬拉松第172輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 08:32（第169輪，最舊）/TW 09:02（第170輪）/US 09:31（第171輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`再度發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改）、`research/pit_run_500.log`（未追蹤），跟第169–171輪記錄的殘留一致，皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第178輪 · 2026-08-28T13:01+08:00 · 跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 11:31（第175輪，最舊）、TW 12:02（第176輪）、US 12:32（第177輪，最新）——依輪替選FUT。

複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本）。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。

同時複查`TW_MARATHON_STATE.md`第176輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。

本輪未做任何實質工作。

**額外發現**：開工時`git status`再度發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改）、`research/pit_run_500.log`（未追蹤），跟第169–177輪記錄的殘留一致，皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

---
## 2026-08-28T14:31+08:00 — 馬拉松第181輪：跳過（暫停規則生效中）

**選軌理由**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 13:01（第178輪，最舊）/TW 13:31（第179輪）/US 14:01（第180輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第179輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`再度發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改）、`research/pit_run_500.log`（未追蹤），跟第169–180輪記錄的殘留一致，皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 第184輪（2026-08-28T16:01+08:00）

**開工**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 14:31（第181輪，最舊）、TW 15:01（第182輪）、US 15:31（第183輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第182輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`再度發現屬於另一互動session的殘留變更——`data/rate_limit_state.json`（已修改）、`research/pit_run_500.log`（未追蹤），跟第169–183輪記錄的殘留一致，皆非本輪馬拉松產生，依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 第187輪（2026-08-28T17:31+08:00）

**開工**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 16:01（第184輪，最舊）、TW 16:32（第185輪）、US 17:01（第186輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第185輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認乾淨，僅慣常的`research/pit_run_500.log`未追蹤殘留（另一互動session產生，跟第169–186輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約77輪、跨度約45小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-08-28T19:01+08:00 — 馬拉松第190輪：跳過，暫停規則生效中

**選軌理由**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 17:31（第187輪，最舊）、TW 18:02（第188輪）、US 18:31（第189輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第188輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認乾淨，僅慣常的`research/pit_run_500.log`未追蹤殘留（另一互動session產生，跟第169–187輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約80輪、跨度約46.5小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-28T20:31+08:00 — 馬拉松第193輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 19:01（第190輪，最舊）、TW 19:31（第191輪）、US 20:02（第192輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第191輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認乾淨，僅慣常的`research/pit_run_500.log`未追蹤殘留（另一互動session產生，跟第169–190輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約83輪、跨度約48小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-28T22:01+08:00 — 馬拉松第196輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 20:31（第193輪，最舊）、TW 21:01（第194輪）、US 21:31（第195輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第194輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認乾淨，僅慣常的`research/pit_run_500.log`未追蹤殘留（另一互動session產生，跟第169–193輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約86輪、跨度約49.5小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-28T23:31+08:00 — 馬拉松第199輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 22:01（第196輪，最舊）、TW 22:54（第197輪）、US 23:02（第198輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第197輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，本輪（第197輪）額外嘗試補`portfolio_multifactor_v2`隨機控制組N15→100但卡在`load_sample_with_factors()`效能異常未完成，也不是FUT軌能接手的工作。目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認乾淨，僅慣常的`research/pit_run_500.log`未追蹤殘留（另一互動session產生，跟第169–196輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約89輪、跨度約51小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T02:01+08:00 — 馬拉松第203輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 23:31（第199輪，最舊）、US 01:02（第200輪）、TW 01:44（第202輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`（於repo根目錄`C:\alpha\alpha-app`執行，注意`research/`子目錄下直接跑會因pathspec相對路徑問題查不到結果）確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第202輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，第202輪補齊了`portfolio_multifactor_v2`兩組合的N=100隨機控制組數字（A_4pass percentile 99.0、B_plus_value_pe percentile 100.0，alpha皆未達p<0.05顯著），判定仍是FAIL，沒有留下已知的下一個補對照組工作單位，也不是FUT軌能接手的工作。目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`發現工作目錄有另一互動session的殘留變更（`data/rate_limit_state.json`已修改、`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`未追蹤，跟第169–199輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約93輪、跨度約53小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T03:32+08:00 — 馬拉松第206輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:01（第203輪，最舊）、US 02:32（第204輪）、TW 03:03（第205輪，最新）——依輪替選FUT。

**判定**：複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`（於repo根目錄`C:\alpha\alpha-app`執行）確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中，跟FUT軌本身無關（規格書全部圍繞TAIEX/TWSE台股樣本，不涉及期貨）。同時複查`LEADS.md`最新`portfolio_multifactor_v2`條目——仍是「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項留給使用者決定，未見新回應。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第205輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，第205輪額外發現並記錄`TW_LOG.md`第202輪結尾一則措辭跟round109起長期一致判斷矛盾的內部矛盾（研判是撰寫疏失，已交由使用者裁決，不擅自解決），沒有留下FUT軌能接手的工作。目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`發現工作目錄仍有另一互動session的殘留變更（`data/rate_limit_state.json`已修改、`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`未追蹤，跟第169–203輪記錄一致），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約96輪、跨度約55小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T05:01+08:00 — 馬拉松第209輪：跳過，暫停規則生效中

**取鎖**：乾淨（非陳舊鎖檔）。三軌時間戳：FUT 03:32（第206輪，最舊）、US 04:02（第207輪）、TW 04:31（第208輪，最新）——依輪替選FUT。

**判定**：獨立複查三個解除條件皆未成立：(1) `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -3 -- research/PORTFOLIO_STRATEGY_SPEC.md`（於repo根目錄`C:\alpha\alpha-app`執行）確認自建立（`fa369b9`）以來仍只有這一個commit；(2) `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）——判定仍FAIL（卡在alpha顯著性p>0.05），「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項仍留給使用者決定，未見新回應；(3) 暫停規則本身（`MARATHON_PROTOCOL.md`最上方）未被修改移除。FUT軌round104留下的盤別效應第三批待辦本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。同時複查`TW_MARATHON_STATE.md`第208輪記錄——TW軌兩項地基背景工作（宇宙回補81.3%、T86回補100%）仍維持已達標，round205已釐清的round202文件矛盾判斷維持有效，沒有留下FUT軌能接手的工作。目前三軌皆無已知允許的工作單位可做。**本輪整輪跳過，未做任何實質工作。**

**額外發現**：開工時`git status`確認工作目錄僅`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`（未追蹤），跟第169–206輪記錄一致（另一互動session殘留），依規則不觸碰、不加入本輪commit。

`is_holdout_consumed()`確認為`False`（本輪未打任何API）。無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約99輪、跨度約56.5小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 第 212 輪 · 2026-08-29T06:31+08:00
取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 05:04（第209輪，最舊）、US 05:33（第210輪）、TW 06:02（第211輪，最新）——依輪替選FUT。獨立複查三個解除條件：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」；`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個 commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍 FAIL，(a) 換更大樣本重跑 / (b) train-only 嚴格樣本外，兩選項仍待使用者裁示，未見新回應。
3. 暫停規則本身（`MARATHON_PROTOCOL.md` 最上方章節）未被修改或移除。

三個解除條件皆未成立。FUT軌round104留下的唯一明確待辦（盤別效應第三批跳空構造/另立新因子家族）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md` 全部圍繞 TAIEX/TWSE 台股樣本，FUT軌本身沒有組合策略相關工作可接。

`is_holdout_consumed()` 確認 `False`。`git status` 檢查發現兩個不屬於本輪的殘留檔案（`research/pit_run_500.log`、`research/pit_run_liquidity500_full.log`），研判是另一互動session的PIT回測相關工作留下的，依規則不觸碰、不commit、不刪除。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

---

## 2026-08-29T08:01:00+08:00 — 馬拉松第215輪：跳過，暫停規則生效中

**選軌理由**：`marathon_lock.py acquire` 回傳 `LOCK_ACQUIRED`（取鎖乾淨，非陳舊鎖檔）。三軌時間戳比對：FUT 06:31（第212輪，最舊）、US 07:01（第213輪）、TW 07:31（第214輪，最新）——依輪替選FUT。

**獨立複查三個解除條件，皆未成立**：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」；`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍 **FAIL**（alpha p>0.05未達顯著性門檻），「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b) 兩個選項仍待使用者裁示，未見新回應。
3. 暫停規則本身未被修改移除。

FUT軌round104留下的「下一步」1–4項（盤別效應第三批跳空構造等）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，符合協定第0節第3項「US/FUT軌如果沒有組合策略相關工作可做，這段期間直接跳過這一輪」的明文指示。

`is_holdout_consumed()` 確認 `False`（本輪未打任何API）。`git status` 檢查發現除慣常的兩個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`，判斷是另一互動session的PIT回測工作殘留）外，還出現本輪未預期的變更：`../BACKLOG.md`／`../data/STATUS.json` 被修改，且新增兩個未追蹤檔案 `HYPOTHESIS_QUEUE.md`／`STRATEGY_GRAVEYARD.md`——這些不屬於研究帽（`research/`）管轄範圍（依 `alpha-app/CLAUDE.md` 第九節帽子規則，`BACKLOG.md`/`data/STATUS.json` 屬維運/開發帽），研判是另一個並行互動session正在進行的工作，本輪不觸碰、不納入commit，僅記錄於此供後續核對。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

## 2026-08-29T09:32+08:00 — 馬拉松第218輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 08:01（第215輪，最舊）、US 08:32（第216輪）、TW 09:02（第217輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL，(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的「下一步」1–4項（盤別效應第三批跳空構造等）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，符合協定第0節第3項明文指示。

`is_holdout_consumed()`確認`False`（本輪未打任何API）。`git status`確認僅慣常的兩個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`，另一互動session殘留）無其他變更，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約108輪、跨度約61小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T11:01+08:00 — 馬拉松第221輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 09:32（第218輪，最舊）、US 10:01（第219輪）、TW 10:31（第220輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL，(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的「下一步」1–4項（盤別效應第三批跳空構造等）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，符合協定第0節第3項明文指示。

`is_holdout_consumed()`確認`False`（本輪未打任何API）。`git status`確認僅慣常的兩個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`，另一互動session殘留）無其他變更，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約111輪、跨度約62小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T12:32+08:00 — 馬拉松第224輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 11:01（第221輪，最舊）、US 11:31（第222輪）、TW 12:04（第223輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL，(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的「下一步」1–4項（盤別效應第三批跳空構造等）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，符合協定第0節第3項明文指示。

`is_holdout_consumed()`確認`False`（本輪未打任何API）。`git status`確認除慣常的三個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`，另一互動session殘留）跟`data/rate_limit_state.json`（已追蹤但屬GitHub Actions自動更新的App資料檔，非本輪研究工作範圍，依`alpha-app/CLAUDE.md`帽子規則不動）之外無其他變更，皆未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約114輪、跨度約63.9小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-08-29T14:01+08:00 — 馬拉松第227輪：跳過，暫停規則生效中

**選軌理由**：取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 12:32（第224輪，最舊）、US 13:01（第225輪）、TW 13:31（第226輪，最新）——依輪替選FUT。

獨立複查三個解除條件：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL，(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的「下一步」1–4項（盤別效應第三批跳空構造等）本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，符合協定第0節第3項明文指示。

`is_holdout_consumed()`確認`False`（本輪未打任何API）。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（已追蹤但屬GitHub Actions自動更新的App資料檔，非本輪研究工作範圍，依`alpha-app/CLAUDE.md`帽子規則不動）之外無其他變更，皆未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** FUT軌round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約117輪、跨度約65.0小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-08-29T15:31+08:00 — 馬拉松第230輪：跳過（暫停規則生效中，依輪替選FUT）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 14:01（第227輪，最舊）、US 14:31（第228輪）、TW 15:01（第229輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（GitHub Actions自動更新的App資料檔，非本輪研究範圍）之外無其他變更，未觸碰、未納入本輪commit。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約120輪、跨度約66.5小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T17:01+08:00 — 馬拉松第233輪：跳過（暫停規則生效中，依輪替選FUT）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 15:31（第230輪，最舊）、US 16:02（第231輪）、TW 16:32（第232輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（GitHub Actions自動更新的App資料檔，非本輪研究範圍）之外無其他變更，未觸碰、未納入本輪commit。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約123輪、跨度約68.5小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T18:31+08:00 — 馬拉松第236輪：跳過（暫停規則生效中，依輪替選FUT）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 17:01（第233輪，最舊）、US 17:32（第234輪）、TW 18:01（第235輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（GitHub Actions自動更新的App資料檔，非本輪研究範圍）之外無其他變更，未觸碰、未納入本輪commit。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約126輪、跨度約69.9小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-08-29T20:01+08:00 — 馬拉松第239輪：跳過（暫停規則生效中，依輪替選FUT）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 18:31（第236輪，最舊）、US 19:01（第237輪）、TW 19:32（第238輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍待使用者裁示，未見新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（GitHub Actions自動更新的App資料檔，非本輪研究範圍）之外無其他變更，未觸碰、未納入本輪commit。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約129輪、跨度約71.4小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-08-29T21:31+08:00 — 馬拉松第242輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 20:01（第239輪，最舊）、US 20:31（第240輪）、TW 21:01（第241輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項仍待使用者裁示，未見新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，同round109起連續判斷邏輯一致，保守跳過。`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認除慣常的四個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_full.log`／`research/pit_run_liquidity500_clean.log`／`research/weinstein_v2_run.log`，另一互動session殘留）跟`data/rate_limit_state.json`（GitHub Actions自動更新的App資料檔，非本輪研究範圍）之外無其他變更，未觸碰、未納入本輪commit。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約132輪、跨度約72.9小時，需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-01T09:03:00+08:00 — 馬拉松第245輪：跳過，暫停規則生效中

**取鎖狀況**：本輪開頭 `marathon_lock.py acquire` 回傳 `LOCK_STALE (held by 32928, 29.9 min old) -- recovering` 後 `LOCK_ACQUIRED`——**上一輪（第244輪之後、本輪之前應該還有一輪，但鎖檔陳舊代表那一輪疑似卡死或崩潰，沒有留下任何記錄**（`REPORT.md`最新一筆仍是第244輪，`MARATHON_STATE.md`計數器仍是244，中間沒有第245輪之前的其他痕跡，代表卡死的那一輪確實什麼都沒寫成功就異常終止）。

**選軌理由**：比對三軌最後更新時間戳——TW `2026-09-01T08:32`（第244輪，最新）／US `2026-09-01T08:01`（第243輪）／FUT `2026-08-29T21:31`（第242輪，最舊）——依輪替規則選FUT。

**獨立複查三個解除條件，皆未成立**：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」；`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自 `fa369b9` 建立以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p=0.0535/0.053，未達5%顯著性門檻）；「換更大樣本重跑」(a)、「train-only嚴格樣本外」(b)兩個選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文完整重讀一遍（本輪開頭執行的三步驟之一），未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」1–4項本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌本身沒有組合策略相關工作可接，同round109起連續判斷邏輯一致，保守跳過。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。`git status` 確認除4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit（未見round244提到的`TRIALS_LEDGER.md`未commit修改，該筆應已在其他session被處理，本輪不做任何推測，只如實記錄現況）。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約135輪、跨度約132.4小時（約5.5天）；且本輪偵測到上一輪（第244輪之後那一輪）疑似崩潰、陳舊鎖檔被回收，未留下任何記錄，需留意排程器/機器穩定性。需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 第 248 輪 · 2026-09-01T10:31+08:00

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 09:03（第245輪，最舊）、US 09:31（第246輪）、TW 10:01（第247輪，最新）——依輪替選FUT。

獨立複查暫停規則三個解除條件：
1. `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md`確認自`fa369b9`以來仍只一個commit，未變。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

三者皆未成立，暫停規則整體仍完全生效中。FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`weinstein_v2_run.log`，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約138輪、跨度約133.9小時（約5.6天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-01T12:01:00+08:00 — 馬拉松第251輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 10:32（第248輪，最舊）、US 11:01（第249輪）、TW 11:33（第250輪，最新）——依輪替選FUT。

獨立複查三個解除條件：(1) `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2) `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3) `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。三者皆未成立，暫停規則整體仍完全生效中。FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`weinstein_v2_run.log`，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約141輪、跨度約135.9小時（約5.7天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-01T13:31:00+08:00 — 馬拉松第254輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 12:01（第251輪，最舊）、US 12:31（第252輪）、TW 13:01（第253輪，最新）——依輪替選FUT。

獨立複查三個解除條件：(1) `PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2) `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3) `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。三者皆未成立，暫停規則整體仍完全生效中。FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約144輪、跨度約137.4小時（約5.7天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-01T15:01:00+08:00 — 馬拉松第257輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 13:31（第254輪，最舊）、US 14:01（第255輪）、TW 14:35（第256輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，A_4pass p=0.0535/B_plus_value_pe p=0.0535），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約147輪、跨度約138.9小時（約5.8天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-01T16:32:13+08:00 — 馬拉松第260輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 15:01（第257輪，最舊）、US 15:31（第258輪）、TW 16:01（第259輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，A_4pass p=0.0535/B_plus_value_pe p=0.0535），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約150輪、跨度約140.0小時（約5.8天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-01T19:02:10+08:00 — 馬拉松第263輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 16:32（第260輪，最舊）、US 18:01（第261輪）、TW 18:31（第262輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，A_4pass p=0.0535/B_plus_value_pe p=0.0535），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

開工前先確認第260輪留下的push積壓問題（DNS解析失敗）——`git log`確認本機`HEAD`與`origin/main`皆為`4c74e23`，一致，已由第261輪（US軌）自行解決，不需要任何額外動作。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約153輪、跨度約142.0小時（約5.9天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-01T20:31:00+08:00 — 馬拉松第266輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 19:02（第263輪，最舊）、US 19:31（第264輪）、TW 20:01（第265輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，A_4pass p=0.0535/B_plus_value_pe p=0.0535），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

第260輪遺留的push積壓問題本輪再次確認：`git status`顯示「Your branch is up to date with 'origin/main'」，`git log --oneline -5`與`git log --oneline origin/main -5`完全一致（HEAD=`e6bc3c2`），確認早已解決，無需任何額外動作。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約156輪、跨度約143.5小時（約6.0天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-01T22:01:00+08:00 — 馬拉松第269輪：跳過，暫停規則生效中

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 20:31（第266輪，最舊）、US 21:01（第267輪）、TW 21:31（第268輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，A_4pass p=0.0535/B_plus_value_pe p=0.0535），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

開工前確認`git status`：HEAD與`origin/main`一致（`2404ff6`），無push積壓；另偵測到2個commit（`afc5e46`／`2404ff6`）是另一互動session的IBKR paper下單開發工作，非本輪產生，未觸碰。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()`確認`False`（本輪零API呼叫）。`git status`確認僅4個未追蹤log殘留（`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致，另一互動session殘留）之外無其他變更，未觸碰、未納入本輪commit。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約159輪、跨度約145.5小時（約6.1天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-01T23:31+08:00 — 第272輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 22:01（第269輪，最舊）、US 22:31（第270輪）、TW 23:01（第271輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

開工前確認 `git status`：HEAD與`origin/main`一致（`1e84acd`），無push積壓；另偵測到 `MARATHON_LOG.md`／`dividend_yield_portfolio_v1.py` 為修改狀態，研判是另一互動session殘留，非本輪產生，未觸碰。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。`git status` 確認除上述另一session殘留外，僅5個未追蹤log殘留（`research/dividend_yield_portfolio_v1_run.log`／`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致），未觸碰、未納入本輪commit。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約162輪、跨度約147.0小時（約6.1天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-02T01:01+08:00 — 第275輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 23:31（第272輪，最舊）、US 00:01（第273輪）、TW 00:31（第274輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，保守跳過。

開工前`git status`偵測到 `dividend_yield_portfolio_v1.py` 為修改狀態，研判是另一互動session殘留，非本輪產生，未觸碰。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。`git status` 確認除上述另一session殘留外，僅5個未追蹤log殘留（`research/dividend_yield_portfolio_v1_run.log`／`research/pit_run_500.log`／`research/pit_run_liquidity500_clean.log`／`research/pit_run_liquidity500_full.log`／`research/weinstein_v2_run.log`，跟前幾輪記錄一致），未觸碰、未納入本輪commit。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約165輪、跨度約149.0小時（約6.2天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-02T02:31+08:00 — 第278輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 01:01（第275輪，最舊）、US 01:31（第276輪）、TW 02:01（第277輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有未追蹤log殘留（`dividend_yield_portfolio_v1_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`val_continue_run.log`／`val_continue_run2.log`／`val_continue_run3.log`／`val_continue_run4.log`／`weinstein_v2_run.log`，判斷是其他互動session殘留），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約168輪、跨度約150.5小時（約6.27天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-02T04:02+08:00 — 第281輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:31（第278輪，最舊）、US 03:01（第279輪）、TW 03:31（第280輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有未追蹤log殘留（`dividend_yield_portfolio_v1_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`val_continue_run.log`／`val_continue_run2.log`／`val_continue_run3.log`／`val_continue_run4.log`／`weinstein_v2_run.log`，判斷是其他互動session殘留），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約172輪、跨度約151.9小時（約6.33天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-02T07:01+08:00 — 第287輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 05:31（第284輪，最舊）、US 06:02（第285輪）、TW 06:31（第286輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有12個未追蹤log/腳本殘留（`deep_dive_f_low_vol.py`／`deep_dive_f_low_vol_run.log`／`dividend_yield_portfolio_v1_run.log`／`monthly_revenue_event_study_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`val_continue_run.log`／`val_continue_run2.log`／`val_continue_run3.log`／`val_continue_run4.log`／`weinstein_v2_run.log`，同上一輪TW軌記錄的性質，另一互動session殘留），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約178輪、跨度約154.4小時（約6.43天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-02T21:32+08:00 — 第290輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 07:01（第287輪，最舊）、US 07:31（第288輪）、TW 21:28（第289輪，最新）——依輪替選FUT。本輪與上一次FUT輪（07:01）相隔約14.5小時，明顯超出正常30分鐘排程間隔，如實記錄此觀察（鎖檔本身乾淨，非陳舊鎖檔回收）。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`../index.html`／`TRIALS_LEDGER.md`／`pair_trading_sanity.py`已修改，另有數個未追蹤log/腳本檔案），皆為另一互動session留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約181輪、跨度約168.9小時（約7.04天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-02T23:01+08:00 — 第293輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 21:32（第290輪，最舊）、US 22:01（第291輪）、TW 22:31（第292輪，最新）——依輪替選FUT。與上一次FUT輪相隔約1.5小時，接近正常排程間隔（略有累積延遲，非異常）。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`../data/rate_limit_state.json`已修改，另有13個未追蹤log/腳本檔案），皆為另一互動session留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約184輪、跨度約170.4小時（約7.10天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-03T00:31+08:00 — 第296輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 23:01（第293輪，最舊）、US 23:32（第294輪）、TW 00:02（第295輪，最新）——依輪替選FUT。與上一次FUT輪相隔約1.5小時，接近正常排程間隔。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`已修改，另有14個未追蹤log/腳本檔案），皆為另一互動session留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約187輪、跨度約171.9小時（約7.16天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

## 2026-09-03T04:31+08:00 — 第302輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 03:02（第299輪，最舊）、US 03:31（第300輪）、TW 04:02（第301輪，最新）——依輪替選FUT。與上一次FUT輪相隔約1小時29分，略超出正常30分鐘排程間隔，幅度不大，如實記錄此觀察（鎖檔本身乾淨）。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`research/pit.py`已修改，`research/STRATEGY_GRAVEYARD.md`已修改——內容為`HYPOTHESIS_QUEUE.md#22`複合訊號FAIL判定，屬另一個獨立自主馬拉松軌道`AlphaHypothesisQueue`留下，另有17個未追蹤log/腳本檔案），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約193輪、跨度約175.9小時（約7.33天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-03T03:02+08:00 — 第299輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 00:32（第296輪，最舊）、US 01:02（第297輪）、TW 02:32（第298輪，最新）——依輪替選FUT。與上一次FUT輪（第296輪）相隔約2.5小時，超出正常30分鐘排程間隔，如實記錄此觀察（鎖檔本身乾淨，非陳舊回收，非上一輪崩潰跡象）。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`../data/rate_limit_state.json`已修改，另有15個未追蹤log/腳本檔案，皆為另一互動session/`AlphaHypothesisQueue`軌道留下），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約190輪、跨度約174.4小時（約7.27天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-03T06:01+08:00 — 第305輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 04:31（第302輪，最舊）、US 05:01（第303輪）、TW 05:31（第304輪，最新）——依輪替選FUT。與上一次FUT輪（第302輪）相隔約1小時30分，略超出正常30分鐘排程間隔，幅度不大，如實記錄此觀察（鎖檔本身乾淨）。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`research/pit.py`已修改，另有多個未追蹤log/腳本檔案，皆研判為另一互動session／`AlphaHypothesisQueue`軌道留下），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。

round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增 `TRIALS_LEDGER.md` 列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約196輪、跨度約177.4小時（約7.39天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-03T07:31+08:00 — 第308輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 06:01（第305輪，最舊）、US 06:31（第306輪）、TW 07:01（第307輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：
1. `PORTFOLIO_STRATEGY_SPEC.md` 第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md` 確認自建立（`fa369b9`）以來仍只有這一個commit。
2. `LEADS.md` 最新 `portfolio_multifactor_v2` 條目（round202補充）判定仍FAIL（alpha p>0.05未顯著），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應。
3. `MARATHON_PROTOCOL.md` 第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作；`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`research/pit.py`已修改，另有17個未追蹤log/腳本檔案：`b25_regime_report_run.log`／`composite_quality_revaccel_inst_lowvol_sanity.py`／`composite_sanity_run.log`／`dividend_yield_portfolio_v1_run.log`／`f52w_high_gates_run.log`／`f52w_high_gates_run_utf8.txt`／`f52w_high_portfolio_v1_run.log`／`monthly_revenue_event_study_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`spillover_overlay_v1_run.log`／`val_continue_run.log`～`val_continue_run4.log`／`weinstein_v2_run.log`），研判是另一互動session/`AlphaHypothesisQueue`軌道留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約199輪、跨度約178.9小時（約7.45天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**


## 2026-09-03T09:02+08:00 — 第311輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 07:31（第308輪，最舊）、US 08:02（第309輪）、TW 08:31（第310輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`HYPOTHESIS_QUEUE.md`／`MARATHON_LOG.md`／`research/pit.py`已修改，另有17個未追蹤log/腳本檔案：`b25_regime_report_run.log`／`composite_quality_revaccel_inst_lowvol_sanity.py`／`composite_sanity_run.log`／`dividend_yield_portfolio_v1_run.log`／`f52w_high_gates_run.log`／`f52w_high_gates_run_utf8.txt`／`f52w_high_portfolio_v1_run.log`／`monthly_revenue_event_study_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`spillover_overlay_v1_run.log`／`val_continue_run.log`～`val_continue_run4.log`／`weinstein_v2_run.log`），研判是另一互動session/`AlphaHypothesisQueue`軌道留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約202輪、跨度約180.4小時（約7.52天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**


## 2026-09-03T10:31+08:00 — 第314輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 09:02（第311輪，最舊）、US 09:31（第312輪）、TW 10:01（第313輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`research/pit.py`已修改，另有17個未追蹤log/腳本檔案：`b25_regime_report_run.log`／`composite_quality_revaccel_inst_lowvol_sanity.py`／`composite_sanity_run.log`／`dividend_yield_portfolio_v1_run.log`／`f52w_high_gates_run.log`／`f52w_high_gates_run_utf8.txt`／`f52w_high_portfolio_v1_run.log`／`monthly_revenue_event_study_run.log`／`pit_run_500.log`／`pit_run_liquidity500_clean.log`／`pit_run_liquidity500_full.log`／`spillover_overlay_v1_run.log`／`val_continue_run.log`～`val_continue_run4.log`／`weinstein_v2_run.log`），研判是另一互動session/`AlphaHypothesisQueue`軌道留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約205輪、跨度約181.9小時（約7.58天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**


## 2026-09-03T12:01+08:00 — 第317輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 10:31（第314輪，最舊）、US 11:01（第315輪）、TW 11:31（第316輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`data/rate_limit_state.json`／`research/pit.py`已修改，另有多個未追蹤log/腳本檔案，研判是另一互動session/`AlphaHypothesisQueue`軌道留下），未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約208輪、跨度約183.4小時（約7.64天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**


## 2026-09-03T22:02+08:00 — 第320輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 12:01（第317輪，最舊）、US 12:31（第318輪）、TW 13:01（第319輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認僅既有非本輪產生的殘留變更（`research/HYPOTHESIS_QUEUE.md`／`research/TRIALS_LEDGER.md`已修改，另有多個未追蹤log/腳本檔案），研判是另一互動session/`AlphaHypothesisQueue`軌道留下，未觸碰、未納入本輪commit。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 本輪成功以既有指令路徑重新驗證，確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約211輪、跨度約193.4小時（約8.06天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-04T00:01+08:00 — 第323輪（FUT軌，跳過，暫停規則生效中）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 22:02（第320輪，最舊）、US 23:03（第321輪）、TW 23:31（第322輪，最新）——依輪替選FUT。

獨立複查三個解除條件皆未成立：(1)`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log --oneline -- research/PORTFOLIO_STRATEGY_SPEC.md`本輪重新確認自建立（`fa369b9`）以來仍只有這一個commit；(2)`LEADS.md`最新`portfolio_multifactor_v2`條目（round202補充）判定仍FAIL（alpha p>0.05未顯著，最佳兩組合p=0.053/0.0535「接近顯著」），(a)換更大樣本重跑／(b)train-only嚴格樣本外兩選項仍未見使用者新回應；(3)`MARATHON_PROTOCOL.md`第0節暫停規則本文本輪完整重讀一遍，未被修改移除。

FUT軌round104留下的盤別效應第三批「下一步」本質仍是單因子相關工作，`PORTFOLIO_STRATEGY_SPEC.md`全部圍繞TAIEX/TWSE台股樣本，FUT軌沒有組合策略相關工作可接，且「宇宙全量回補」（第5b節）是TW軌專屬的地基工作、FUT軌沒有對應項目，保守跳過。

開工前`git status`確認：除了既有非本輪產生的殘留未追蹤log檔案（`research/`底下約17個，研判是另一互動session留下）之外，**本輪新觀察到`.github/workflows/market.yml`／`.github/workflows/quotes.yml`兩個檔案已修改**（先前幾輪未見這兩個檔案有變動）——這屬於維運帽子擁有的檔案（`CLAUDE.md`第九節帽子規則），跟FUT軌無關，未觸碰、未查看內容、未納入本輪commit，僅記錄觀察供使用者留意。

**本輪整輪跳過，未做任何實質工作。** `is_holdout_consumed()` 本輪成功以既有指令路徑重新驗證，確認 `False`（本輪零API呼叫）。round104的「下一步」1–4項維持原狀不變，等使用者解除暫停規則後從那裡接續。沒有新增`TRIALS_LEDGER.md`列。

**提醒使用者：自第110輪暫停規則生效以來，三軌合計已連續跳過約214輪、跨度約195.4小時（約8.14天），需使用者親自確認`PORTFOLIO_STRATEGY_SPEC.md`或裁示選項(a)/(b)/解除暫停規則三者之一才能恢復進度。**

---

## 2026-09-04T04:31+08:00 — 第328輪（FUT軌，方法論查證，非新假說）

**取鎖時偵測到`LOCK_STALE`**（pid 15340持有30.1分鐘，上一輪疑似異常中止、未正常釋放鎖，已自動回收）。三軌時間戳：FUT 00:01（第323輪，最舊）、US 02:32（第324輪）、TW 04:15（第327輪，最新，已於暫停規則解除後恢復實質工作）——依輪替選FUT。

**主軸背景**：暫停規則已於2026-09-03解除（`8aad0d4`），總司令裁示甲.3的校準探針（`CALIBRATION_PROBE.md`）已完成，結論(乙)「檢定力不足」，指令是`factor_ic.SAMPLE_SIZE`100→300（已由TW軌round325/327執行），並要求「US/FUT軌的#47/#52/#34同理各自重跑」。本輪工作單位：**查證這個「同理重跑」指令對FUT軌#34（`fut_intraday_gap_continuation`）是否真的可行**——這是校準探針指令的可行性複查，不是新假說、不是深挖既有候選，屬於`MARATHON_PROTOCOL.md`第2節「先用當下該軌道的累積FDR門檻重新檢查候選是否還站得住腳」精神的延伸應用（方向相反：這裡是查證「重新分類」本身是否成立，不是重新分類一個新結果）。

**查證過程**：
1. 確認`factor_ic.SAMPLE_SIZE`已經是300（TW軌已改）。
2. 校準探針的修正機制本質是「增加橫斷面N（可抽樣的獨立標的數）降低null分布變異數」——這個機制天生依賴「同一時間點有多個獨立標的可抽樣」，股票宇宙有3196檔可抽，TX期貨只有一條連續合約序列（`build_continuous_series()`回傳單一時間序列），沒有橫斷面維度。
3. 查兩個FUT軌可能的替代「擴大樣本」手段：
   - **延長歷史期數**（時間序列版的「更多樣本」）：查`continuous_contract.py`發現`FULL_HISTORY_END = "2024-12-31"`——比對`validation/holdout.py`的`VAL_END = "2024-12-31"`，**兩者完全相等**，代表FUT軌現有資料窗口已經頂到holdout邊界，不是尚未回補的落差。再延伸就是動用holdout資料，`MARATHON_PROTOCOL.md`第4節「絕對不碰holdout」明文禁止，**此路不通，且發現得早（在寫任何抓資料程式碼之前），沒有誤觸`load_full_history()`或`unlock_holdout_once()`風險**。
   - **提高`N_SHUFFLES`**（排列檢定次數）：這控制的是p值估計本身的蒙地卡羅精度（估計值的雜訊），跟校準探針講的「檢定力」（真實訊號被null分布淹沒的機率）是不同概念——後者取決於null分布本身的變異數（跟橫斷面N相關），不是排列次數。且這個手段round57已經做過（`fut_recheck_intraday_gap_continuation_highres.py`，N_SHUFFLES 200→2000），結果92.0→**89.60（下降，跌破單測門檻，不是逼近門檻）**，方向跟「樣本太小、真訊號被低估」的假設相反——如果真的是檢定力不足導致低估，加大解析度應該讓讀數更接近真實值（可能更高也可能更低，但這裡明確變差且更確定FAIL），這個既有結果本身就是「這個手段對FUT #34不成立」的直接反證。
4. `is_holdout_consumed()`本輪成功以既有指令路徑重新驗證，確認`False`（本輪零API呼叫，純讀檔查證）。

**判定**：`TRIALS_LEDGER.md`「2026-09-04校準探針後的重新分類」區塊裡#34（FUT）的「未定（待300檔重跑）」標記**對FUT軌不成立**，改標「查證後維持FAIL，理由：無holdout安全的擴大樣本手段可用」，寫進`TRIALS_LEDGER.md`#99、`FUT_LEADS.md`「第328輪新增」。TW/US的#77/#79/#91/#47/#52不受影響，本輪未觸碰。

**誠實記錄本輪性質**：這不是一個PASS/FAIL/CHEAP_PASS判定（沒有測試新訊號），是一個「查證上一輪指令對本軌是否適用」的方法論工作單位，結果是負面的（不適用）——依協定「誠實記錄，包含大量FAIL」精神，這種「查證後發現此路不通」也要老實寫下來，不能因為「沒有測出新東西」就跳過不記錄。同時記下一個未來可能的方向（非本輪待辦）：測試TX以外的其他TAIFEX商品（MTX/TE/TF）當作多標的池，是唯一可能真正類比股票橫斷面擴大的路，但需要全新的跨商品pooling方法論設計。

**下一輪建議**：FUT #34已徹底結案（不必再回頭）。可回到`FUT_LEADS.md`既有的「下一輪建議」清單：(a) 盤別效應家族第三批（夜盤收盤(T)→日盤開盤(T)跳空）、(b) 全新機制家族、(c) `fut_basis_mean_reversion_60d`的regime/年代分段穩健性檢查。FUT軌資源配置上限20%提醒同前。

`git status`開工前確認：除了既有非本輪產生的殘留變更（`.github/workflows/market.yml`／`.github/workflows/quotes.yml`／`data/rate_limit_state.json`／`research/MARATHON_LOG.md`已修改，另有約17個未追蹤log/腳本殘留檔案，皆研判為另一互動session／`AlphaHypothesisQueue`軌道留下）之外無其他變更，未觸碰、未納入本輪commit。

---

## 2026-09-04T06:33+08:00 — 第332輪（FUT軌，地基查證：多商品資料可用性）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳（本輪開工時）：FUT 04:31（第328輪，最舊）、US 05:07（第329輪）、TW 06:09/06:10（第331輪，最新）——依輪替選FUT。

**主軸背景**：2026-09-03總司令裁示（`MARATHON_PROTOCOL.md`最上方區塊）明確要求「US／FUT軌：主軸同樣是組合策略層級（US可先建立跟TW同構的組合回測地基），沒有組合層級工作可做時才跳過，理由要寫清楚」。FUT #34上一輪（328）已查證確定「無法比照TW/US做300檔重跑」，並在`FUT_LEADS.md`結尾記下「唯一可能真正類比股票『多標的橫斷面』的方向，是同時測試TX以外的其他TAIFEX商品（MTX小台、TE電子期、TF金融期）當作『多個獨立標的』的池子——但這是全新的方法論設計，不是本輪待辦」。本輪選擇把這個「未來方向」往前推一步：**先查證資料源可用性，這是`MARATHON_PROTOCOL.md`第1c節「地基還沒搭好，先查資料源可用性，不要急著測因子」的精神**（跟US軌一開始查`USStockPrice`可用性同款做法）。

**做了什麼**：新增`fut_probe_multi_commodity.py`（唯讀探針，透過`finmind_client.load_dev()`走既有holdout截斷機制，零新的資料抓取邏輯，只是換`data_id`）。用跟`continuous_contract.py`完全相同的`(FULL_HISTORY_START, FULL_HISTORY_END)`窗口（2000-01-01～2024-12-31）各查一次`TaiwanFuturesDaily`資料集，`data_id`分別為`MTX`（小型台指）、`TE`（電子期）、`TF`（金融期）。3次API呼叫（每個商品一次，全部命中新cache key，非重複請求）。

**結果（三個商品皆有資料，深度都足夠）**：

| 商品 | 可用 | 單月合約列數 | 資料起始 | 資料結束 | 盤別 | 相異合約月數 |
|---|---|---|---|---|---|---|
| MTX（小型台指） | 是 | 46,494 | 2001-04-09 | 2024-12-31 | position + after_market | 744 |
| TE（電子期） | 是 | 40,835 | 2000-01-04 | 2024-12-31 | position + after_market | 306 |
| TF（金融期） | 是 | 31,894 | 2000-01-04 | 2024-12-31 | **僅position** | 306 |

**新發現（誠實記錄，非本輪待辦但影響未來設計）**：TF（金融期）只有日盤（`position`）資料，沒有`after_market`（夜盤）——跟TX/MTX/TE三者都同時有兩種盤別不同。如果未來真的做跨商品pooling，若要用到夜盤資料，TF會是唯一缺角的商品，屆時要嘛排除TF的夜盤分析、要嘛整組商品池只用日盤以求一致，這個決定留給實際動手設計pooling方法論時再做，本輪只負責誠實記下這個資料形狀差異，不擅自下設計決定。

**這不是TRIALS_LEDGER判定**：沒有測試任何因子/策略，是純資料可用性查證（同`FUT_MARATHON_STATE.md`過去「地基搭建」性質的記錄），不加`TRIALS_LEDGER.md`列，也不是CHEAP_PASS/FAIL/EXPERIMENTAL。

**下一輪建議（若要接續這個方向）**：資料源可用性已確認，下一步是設計「跨商品橫斷面池」本身——例如「同一天T，池子裡有幾個商品（TX/MTX/TE/TF，扣掉盤別限制後可能是3或4個）」「同一套排列檢定要怎麼跨商品共用null分布」——這是全新方法論設計，不是重跑既有腳本，可能需要跨兩三輪才能想清楚，不是硬性待辦（`FUT_LEADS.md`既有「下一輪建議」清單：盤別效應家族第三批、全新單一機制家族、`fut_basis_mean_reversion_60d`regime複驗，三者仍是更快能出結果的替代選項，下一輪選哪個依實際情況判斷即可）。

`is_holdout_consumed()`本輪成功確認`False`（本輪3次API呼叫皆透過`load_dev()`走既有dev截斷機制，零繞過holdout風險）。

`git status`開工前確認：除既有非本輪產生的殘留變更（`.github/workflows/market.yml`／`.github/workflows/quotes.yml`已修改，另有多個未追蹤log/腳本殘留檔案，研判是另一互動session／`AlphaHypothesisQueue`軌道留下）之外無其他變更，未觸碰、未查看、未納入本輪commit。本輪新增檔案：`fut_probe_multi_commodity.py`（程式碼）；`data/raw/`底下新增3個parquet快取檔案（gitignored，不進commit）；`data/rate_limit_state.json`本輪也會更新（既有殘留變更之上疊加本輪3次請求的時間戳，gitignored，不進commit）。

## 2026-09-04T08:03+08:00 — 第335輪（FUT軌，地基修bug＋多商品資料池首版）

**接續第332輪確認MTX/TE/TF資料可用性後的下一步**：把「跨商品橫斷面池」往前推一步，
從「資料存在」推進到「連續合約序列可跨商品共用同一套建構邏輯，且真的建出池子」。

**發現並修正一個真bug**：`continuous_contract.py::build_continuous_series()`雖然
`contract`參數早就存在（理論上支援任意商品），但實際上只有TX被真正跑過。本輪直接
呼叫`build_continuous_series(contract='MTX')`立刻crash——`load_session()`的
`contract_date.astype(int)`對MTX的值`'201308W1'`（週選/週合約，2013-07-31起，
佔MTX非跨月價差列約10.3%）拋`ValueError`。TE無此問題（0筆非數字）、TX原本就沒有
週合約所以從未觸發。**修正**：`load_session()`新增一行過濾（`contract_date`必須
精確匹配6位數字`^\d{6}$`），並在docstring記下這次發現，未動既有跨月價差列過濾邏輯
（保留兩行各自獨立說明理由，不合併成一條不透明的正規表達式）。

**修正後驗證**：TX/MTX/TE三者皆能乾淨建出連續合約序列，`skipped_events`全部為0
（無缺轉倉比率的資料缺口）：TX 6185天（300次轉倉）、MTX 5853天（285次轉倉，
2001-04-09起）、TE 6185天（300次轉倉）。

**新增`fut_multi_commodity_pool.py`**：把TX/MTX/TE三條連續序列的`adj_close`日報酬
併成一個寬表（outer join，各自完整日期範圍都保留，不預先裁到重疊窗口），並輸出
描述統計。

**結果（純資料池建構＋描述統計，非因子/策略檢定，不佔TRIALS_LEDGER列）**：

| 商品 | 天數 | 日期範圍 | 年化均報酬 | 年化波動 |
|---|---|---|---|---|
| TX | 6184 | 2000-01-05~2024-12-31 | +11.50% | 22.96% |
| MTX | 5852 | 2001-04-10~2024-12-31 | +13.63% | 21.99% |
| TE | 6184 | 2000-01-05~2024-12-31 | +13.57% | 26.60% |

三商品同時有資料的重疊窗口：2001-04-10～2024-12-31，共5852個交易日。

重疊窗口內日報酬相關係數矩陣：
```
        TX    MTX     TE
TX   1.000  0.997  0.955
MTX  0.997  1.000  0.954
TE   0.955  0.954  1.000
```

**誠實記錄一個重要、可能潑冷水的發現，不因為是自己這輪做的就美化**：TX與MTX
日報酬相關係數**0.997**，幾乎是同一個東西（MTX本來就是台指期的1/4規模版本，
標的指數完全相同，這個結果完全在經濟邏輯預期內，不是bug）；TE（電子期）跟
TX/MTX也高達0.954/0.955（台股大盤本身電子權值股占比極高，尤其台積電，這個
高相關同樣經濟上合理）。**這代表「TX+MTX+TE」這三個商品本身其實不構成有意義
的橫斷面分散——三者幾乎是同一個大盤beta的三種包裝，不像股票宇宙有數百檔
相對獨立的標的。** 這是往「跨商品橫斷面池」方向推進之前必須誠實面對的限制：
單純把這三個商品湊成池子，離散度（cross-sectional dispersion）可能小到
沒有統計上有意義的排列檢定空間，不是「資料不夠」的問題，是「這三個商品
在經濟意義上高度共線」的問題。**下一步的方法論設計如果要繼續走橫斷面這條路，
可能需要先評估：(a) 這個相關係數結構是否讓橫斷面排列檢定失去意義（如果需要，
先算一下重疊窗口內每日跨商品報酬的橫斷面標準差有多小）；(b) 或改看TAIFEX
的個股期貨（股票期貨，若FinMind有涵蓋）——那才是真正多檔、相對獨立標的的
候選池，比指數系列期貨更接近股票橫斷面的精神。** 這個判斷本身也留給下一輪
或使用者裁示，本輪只負責誠實把數字攤開，不代替下一輪下最終設計決定。

`is_holdout_consumed()`確認`False`（`build_continuous_series()`/`load_dev()`
全程命中既有本機快取——TX/MTX/TE的`(2000-01-01,2024-12-31)` position session
資料，MTX/TE已由round332的`fut_probe_multi_commodity.py`拉過，TX更早就有，
本輪零新增API呼叫）。

`git status`開工前確認：除既有非本輪產生的殘留變更（`.github/workflows/market.yml`
／`.github/workflows/quotes.yml`已修改，另有多個未追蹤log/腳本殘留檔案，研判是
另一互動session／`AlphaHypothesisQueue`軌道留下）之外無其他變更，未觸碰、未查看、
未納入本輪commit。本輪異動檔案：`continuous_contract.py`（bug修正，2處：docstring
+過濾邏輯一行）、`fut_multi_commodity_pool.py`（新增）。

**下一輪建議**：(a) 若接續橫斷面池方向，先算重疊窗口內三商品每日報酬的橫斷面
標準差，量化「離散度是否足夠支撐排列檢定」；(b) 查證FinMind是否有台股期（個股
期貨）資料集，若有，那才是接近股票橫斷面精神的候選池；(c) 或回頭選`FUT_LEADS.md`
既有「下一輪建議」清單（盤別效應家族第三批/全新單一機制家族/`fut_basis_mean_
reversion_60d` regime複驗）——三者仍是更快出結果的替代選項，非硬性待辦，下一輪
依實際情況判斷。

---

## 2026-09-04T09:33+08:00 — 第338輪（FUT軌）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 08:03（第335輪，最舊）、US 08:33（第336輪）、
TW 09:03（第337輪，最新）——依輪替選FUT。

延續round335留下的三選一「下一步」，做選項(a)：量化重疊窗口內TX/MTX/TE橫斷面
離散度，正式回答「跨商品橫斷面池」方向是否有足夠離散度支撐排列檢定。

新增`fut_multi_commodity_dispersion.py`（純讀，重用`fut_multi_commodity_pool.
build_return_panel()`，零新增API呼叫，全程命中round332/333已建立的本機快取）。
計算兩個獨立指標：

1. **dispersion_ratio**（每日橫斷面std / 各商品自身時序std平均）= **0.1143**。
   三商品各自邊際日波動約1.37%~1.57%（平均1.4411%），但同一天三者之間的橫斷面
   std平均只有0.1648%——代表個股自身波動裡有近九成是三者共同、方向一致的部分，
   只剩約一成左右是三者之間互不相同（可能被多空配對利用）的殘餘離散度。
2. **PCA**：相關矩陣特徵值分解，PC1（第一主成分）解釋變異比例=**97.91%**
   （特徵值[2.9373, 0.0601, 0.0026]，總和3）。跟dispersion_ratio互相獨立驗證出
   同一個結論：整個TX/MTX/TE系統幾乎只由單一共同因子（大盤beta）驅動，剩給
   橫斷面策略可用的獨立變異只剩約2%。

**判定（誠實記錄，是潑冷水但不能美化）**：round335的定性觀察（相關係數0.95~0.997）
本輪被兩個獨立量化指標證實——「跨商品橫斷面池」方向以TX/MTX/TE三者為標的池，
離散度確實太小，不足以支撐有意義的排列檢定式多空策略。這不代表整個「組合策略
主軸」在FUT軌走不通，而是這三個指數系列期貨本身彼此太像，不是合適的橫斷面
候選池——round335選項(b)「查證台股個股期貨（股票期貨）是否有免費資料源」變成
現在唯一還沒排除、真正接近股票橫斷面精神的候選方向。

這是純診斷統計，不含因子/策略檢定，不寫`TRIALS_LEDGER.md`列，跟round332/333
同precedent。`is_holdout_consumed()`本輪開工/收工前皆確認`False`。

**下一步**：(a')優先——查證FinMind `TaiwanFuturesDaily`是否涵蓋個股期貨代碼
（例如台積電期`CDF`系列），若有且深度足夠，那才是FUT軌真正的「組合策略地基」
候選（多標的、彼此相對獨立，跟股票宇宙同精神）；若確認沒有，「跨商品橫斷面池」
這個大方向可視為在TAIFEX既有商品範圍內結案，回頭選`FUT_LEADS.md`既有清單
（盤別效應家族第三批/全新單一機制家族/`fut_basis_mean_reversion_60d`regime複驗）。

## 2026-09-04T18:36+08:00 — 第341輪（FUT軌，地基查證：個股期貨資料源，正面結果）

取鎖時偵測到`LOCK_STALE`（pid 42268持有29.9分鐘後被回收，上一輪疑似異常中止未
釋放鎖）。三軌時間戳：FUT 09:33（第338輪，最舊）、US 17:32（第339輪）、
TW 18:10（第340輪，最新）——依輪替選FUT。

延續round338「下一步(a')」：查證FinMind是否有台股個股期貨（股票期貨）資料，
是否涵蓋足夠標的數/深度，能否成為TX/MTX/TE三者太collinear（round338量化結論）
之後、真正接近股票橫斷面精神的候選池。

**做法**：先用WebSearch/WebFetch查FinMind公開教學頁
（`https://finmind.github.io/tutor/TaiwanMarket/Derivative/`，公開可讀頁面，
非付費/需登入來源，符合`MARATHON_PROTOCOL.md`第3節「允許查公開網路資料當假說
來源」規則），找到候選資料集名稱`TaiwanFutOptDailyInfo`（商品代碼/種類/名稱
對照表）；這只是「靈感來源」，實際存在與否/內容正確與否全部重新走FinMind API
實測，不照抄網頁內容。新增`fut_probe_stock_futures_info.py`（唯讀，
`TaiwanFutOptDailyInfo`是membership/reference清單非時間序列，走`_fetch()`
直接呼叫，跟`universe.py`的`TaiwanStockInfo`/`TaiwanStockDelisting`同precedent，
非違規繞過`load_dev()`）。

**結果（正面，誠實記錄，不誇大）**：

1. `TaiwanFutOptDailyInfo`資料集**確實存在**，單日快照（2024-12-30）回傳
   1406列，欄位`code`/`type`/`name`，其中`type=='TaiwanFuturesDaily'`（期貨，
   非選擇權）有**1139列**——遠多於目前已知的4種商品（TX/MTX/TE/TF）。
2. `name`欄位可見大量個股期貨，例如`CDF`＝台積電期貨、`CCF`＝聯電期貨、
   `CJF`＝華南金期貨（同時`CJ`這個無後綴的base代碼名稱是`華南金(股票期貨)`，
   明確標註）。粗略以2-letter前綴分組觀察，個股期貨（金融股/傳產/電子股皆有）
   佔多數，不是少數幾檔。
3. **深度實測**（走`load_dev('TaiwanFuturesDaily', <code>, ...)`，跟
   round332對MTX/TE/TF的檢查方式相同）：`CDF`（台積電期貨）單月合約
   19479列，2010-01-25～2024-12-31（holdout邊界），184個不同合約月份；
   `CCF`（聯電期貨）18409列，同樣2010-01-25～2024-12-31，184個合約月份。
   兩者深度跟現有TX/MTX/TE的「已驗證可用」水準相當（14年以上、逐月合約
   齊全），不是資料稀疏的邊緣商品。
4. **代碼規則發現（避免下一輪誤踩）**：無後綴的base代碼（例如`CJ`、`CQ`、
   `CL`）直接查`TaiwanFuturesDaily`回傳**空**——這些是`TaiwanFutOptDailyInfo`
   目錄裡的「標註列」，真正可查詢的合約序列是帶`F`後綴的代碼（`CJF`／`CQF`／
   `CLF`⋯，同TX/MTX一貫命名法），跟`1`/`2`後綴的舊版/已停用序列（例如`CJ1`
   只到2024-09-18、`CQ1`只到2015-09-30，明顯是被`F`後綴序列取代的舊合約）
   要分開，不能混用。
5. **規模粗估**：`type=='TaiwanFuturesDaily'`且代碼以`F`結尾的列有**517筆**，
   排除已知的4個指數/商品期貨代碼（TXF/MXF/EXF/FXF）後約509筆——這是「候選
   個股期貨主力合約序列」的粗略上限估計，尚未逐一驗證每一檔的實際成交量/
   流動性是否足夠納入橫斷面池，只確認「代碼存在且至少CDF/CCF兩檔深度良好」。

**判定（誠實記錄，不過度樂觀）**：round338「下一步(a')」查證結果是**正面**——
FinMind確實涵蓋大量台股個股期貨，深度跟現有已驗證商品相當，這是FUT軌第一次
出現「數量級遠大於個位數、標的彼此獨立（不同公司）」的候選池，性質上比
TX/MTX/TE更接近股票橫斷面精神，值得作為下一階段跨商品橫斷面池的主要方向。
**但這只是資料存在性查證，不是策略判定**：尚未驗證(a)這~500檔的實際流動性
（成交量/未平倉量門檻，很可能有相當比例是掛牌但成交清淡的邊緣合約，需要
篩選）、(b)彼此之間的橫斷面離散度是否真的比TX/MTX/TE好（同round338
`fut_multi_commodity_dispersion.py`方法論，尚未套用在這個新池子上——直覺上
應該會更好，因為是不同公司而非同一大盤的不同包裝，但直覺不能取代實測）、
(c)個股期貨是否有股票期貨特有的技術問題（例如是否也有轉倉/連續合約建構
需求，跟`continuous_contract.py`目前只支援TX/MTX/TE/TF是否相容）。這是純
資料地基查證，不含因子/策略檢定，不寫`TRIALS_LEDGER.md`列，跟round332/335/338
同precedent，但**因為是重要的正面新地基發現，本輪額外補一筆到`FUT_LEADS.md`**
（跟round332/335的處理方式一致：資料可用性發現本身不進`TRIALS_LEDGER`，但
值得讓下一輪/使用者一眼看到）。

**下一步**：(a)先用`fut_probe_stock_futures_info.py`已列出的~500檔`F`後綴
候選，逐一（或抽樣）檢查成交量/未平倉量門檻，篩出「真正有流動性」的子集
（可能剩下幾十到一兩百檔，仍遠多於現有4種商品）；(b)確認個股期貨的轉倉
時點規則是否跟指數期貨相同（H1，見`FUT_CONTINUOUS_CONTRACT_DESIGN.md`），
若不同要另外設計；(c)篩選完成後，比照`fut_multi_commodity_dispersion.py`
方法論算這個新池子的dispersion_ratio/PCA，正式回答「這個池子是否真的比
TX/MTX/TE有更多可用的橫斷面獨立變異」，那之後才是真正可以開始設計因子/
排列檢定的地基完成點。

`is_holdout_consumed()`本輪開工/收工前皆確認`False`。全程走`finmind_client`
既有快取層（`TaiwanFutOptDailyInfo`探測查詢是本輪唯一新增的少量API呼叫，
CDF/CCF深度查詢因跟round332同`(FULL_HISTORY_START, FULL_HISTORY_END)`參數
組合，若之前未被查過則為新查詢，本輪執行時間內完成無限流）。**額外觀察**：
`MARATHON_STATE.md`第7行「馬拉松全局輪次計數器」單行內嵌的完整輪次歷史敘事
已成長到約9萬字元，持續每輪append會越來越肥大——這是既有慣例（非本輪造成），
只如實記錄觀察供使用者知悉，本輪未擅自精簡/搬移該檔案結構。

---

## 第344輪 · 2026-09-04T21:06+08:00 · FUT

**背景**：取鎖時偵測到`LOCK_STALE`（pid 52496持有30.0分鐘後被回收，第343輪(TW)疑似異常中止未釋放鎖——但複查確認第343輪commit`deb2a67`已完整推送，屬正常收尾後鎖檔未即時釋放，非資料遺失）。三軌時間戳：TW 20:47（第343輪，最新）／US 19:35（第342輪）／FUT 18:36（第341輪，最舊）——依輪替選FUT。

**額外異常觀察**：round341遺留的`fut_probe_stock_futures_info.py`本輪開工時已從磁碟消失（`git log --all`確認從未commit過），跟第343輪TW記錄的「本輪自建腳本三次執行後檔案本身從磁碟消失」是同一種異常模式的第二次出現（皆發生在近幾輪之內）。本輪未深究根因（超出FUT軌工作範圍），僅如實記錄：**兩次異常都發生在腳本執行完成、產出已寫入其他檔案（parquet快取/log）之後，遺失的只有`.py`原始碼本身**，懷疑跟本機環境有關但無法在目前預算內確認，供使用者/下一輪參考。

**本輪工作單位**：接續round341「下一步(a)」——對~511檔F結尾個股期貨候選池做流動性篩選。原查證腳本雖已消失，但其產出`data/raw/TaiwanFutOptDailyInfo__ALL__2024-12-30__2024-12-30.parquet`快取完好，零API呼叫即可重建候選清單。新增`fut_stock_futures_liquidity_screen.py`：

- 去重後F結尾候選共**511檔**（round341粗估~509，數字接近，差異來自去重方式）。
- **抽樣方法**：每15檔取1檔做等距分層抽樣（stride sampling，非隨機亂數，確保涵蓋代碼字母序全範圍），共取得**37檔樣本**（含round341已快取的CDF/CCF併入，這兩檔零新增API成本）。
- **流動性門檻**（執行前先寫死，不看結果回頭調）：2024整年（holdout邊界內最後一個完整年度）front-month day-session成交量，`active_days>=200`（約245個交易日中至少200天有front-month報價）且`mean_volume>=50`口/日——刻意訂得寬鬆（不是策略實際需要的門檻，只是抓「可能可用」的上限）。
- **結果：19/37 (51.4%) 達到此低門檻**。全數不達標的樣本中，多數是`active_days=0`（該代碼2024年完全無交易，可能是尚未掛牌/已下市/從未活絡的個股期貨），少數是有交易但量極低（如SIF僅mean_vol=1.7、BRF僅8.1）。
- **外推估計**：511檔候選中約**262檔**可能達到此低門檻——比現有TX/MTX/TE/TF（4種商品、round338證實高度共線）大一個數量級，是FUT軌第一次出現「數量級接近股票宇宙橫斷面精神」的候選池規模。

**誠實限制（不能過度樂觀）**：
1. 抽樣門檻刻意寬鬆，不代表這些代碼「足以支撐策略」，只代表「值得排進下一步(c)離散度實測」。
2. 只做了1年（2024）的流動性快照，未查證更早年度是否同樣活絡（個股期貨可能有掛牌時間差異，「2024年活絡」不保證「2015年也活絡」，對PIT宇宙建構是重要缺口）。
3. **round341下一步(b)（轉倉規則是否跟指數期貨相同）跟(c)（實測dispersion_ratio/PCA）仍完全未做**，這輪只完成(a)。
4. 37檔屬於分層抽樣不是普查，51.4%這個比例本身有抽樣誤差，262檔只是點估計。

零因子/策略判定，跟round332/335/338/341同precedent不寫`TRIALS_LEDGER.md`列，但因為是重要的正面地基發現，補記`FUT_LEADS.md`。結果存於`data/fut_stock_futures_liquidity_screen_round344.csv`（37列）。API呼叫：35次新查詢（37樣本扣除CDF/CCF既有快取）+ 0次（TaiwanFutOptDailyInfo命中快取），全程遵守`RATE_LIMIT_MIN_INTERVAL_SEC=3.0`節流，未遭遇限流。`is_holdout_consumed()`開工/收工前皆確認`False`。

**下一步**：round341下一步(b)轉倉規則查證、(c)對這262檔（或抽樣子集）實測dispersion_ratio/PCA，回答「這個池子的橫斷面獨立變異是否真的比TX/MTX/TE多」——那之後才是這個方向的地基完成點，可以開始設計因子。

---

## 第348輪（2026-09-05T00:35+08:00）：round341/344下一步(b)(c)——19檔流動性達標個股期貨的離散度/PCA實測，結果顯著正面

取鎖時偵測到`LOCK_STALE`（pid 49300持有30.2分鐘後被回收），本輪標記「上一輪疑似失敗」，未進一步深究其未commit產物（依協定僅需記錄，第0節第2點）。三軌時間戳：FUT 21:06（第344輪，最舊）／TW 22:32（第346輪）／US 00:10（第347輪，最新）——依輪替選FUT。

延續round341/344留下的關鍵未答問題：round344只完成流動性初篩（(a)，19/37樣本達標），(b)轉倉規則是否跟指數期貨相同、(c)dispersion_ratio/PCA實測——round338證實TX/MTX/TE三者PC1解釋變異達97.91%（幾乎是單一共同因子），這是「跨商品橫斷面池」方向能否成立的關鍵瓶頸，本輪直接處理。

新增`fut_stock_futures_dispersion_test.py`，對round344篩出的19檔流動性達標F結尾個股期貨（CCF/CDF/EHF/FYF/GMF/HBF/HQF/ITF/JWF/KKF/NWF/OLF/PAF/QDF/QRF/RFF/RUF/SXF/ZFF）套用round338同款方法論：

**離散度/PCA結果（19檔重疊窗口）**：
- 19檔上市時間差異很大（CCF/CDF最早2010-01-26，SXF最晚2023-12-19才有資料），19檔同時有資料的重疊窗口只有**250個交易日（2023-12-19~2024-12-31）**——約1年。
- **dispersion_ratio = 1.6371**（對照round338 TX/MTX/TE三商品：0.1143，高出約14倍）。
- **PC1解釋變異比例 = 27.33%**（對照TX/MTX/TE：97.91%），PC1+PC2+PC3合計40.62%。
- 平均兩兩相關係數僅0.1803（TX/MTX/TE三者兩兩相關係數是0.997/0.955/0.954量級）。

**判定：跟TX/MTX/TE指數期貨家族形成鮮明對比，個股期貨池確實具備跨商品橫斷面池所需的獨立變異結構，不像指數家族幾乎全被單一共同因子（大盤beta）主導。** 這是FUT軌第一次找到「離散度看起來足夠支撐排列檢定式橫斷面策略」的候選池，方向性上是正面訊號。

**誠實限制（不能過度樂觀，逐項記錄）**：
1. **重疊窗口只有250個交易日**——因為多數個股期貨掛牌時間晚（2011年後陸續掛牌，部分2021~2023年才掛牌），19檔全部同時有資料的共同窗口被最晚掛牌的成員（SXF 2023-12-19）拖到只剩約1年，樣本量對任何日後要做的排列檢定/樣本外驗證都明顯偏薄，需要進一步設計「不要求全體19檔同時存在」的滾動式宇宙建構（類似股票`universe.py`的存活者偏差處理精神），才能延長可用窗口，這是下一步的核心工作。
2. **多數代碼有非零`skipped_rollover_events`**（EHF 24、FYF 18、GMF 9、HBF 11、HQF 16、ITF 27、JWF 37、KKF 22、NWF 3、QDF 1、SXF 4；只有CCF/CDF/OLF/PAF/QRF/RFF/RUF/ZFF是0）——代表這些代碼有相當比例的轉倉事件缺乏乾淨的價格銜接調整（前後合約在切換錨點日缺報價），`adj_close`對這些代碼並非完全乾淨，可能存在未調整的價格跳空，這點跟TX/MTX/TE/TF/CDF/CCF（round332/341皆為0 skipped）明顯不同，是round341留下的「轉倉規則是否跟指數期貨相同」疑慮的具體證據——**機制本身（H1「前月合約消失即代表已轉倉」）可以泛化執行不crash，但清潔度不如指數期貨**，這是使用任何這19檔資料前必須修的資料品質缺口，不是可以忽略的小事。
3. n=19僅是round344分層抽樣37檔中的達標子集，並非round344外推估計的262檔全量，實際離散度數字若換一批更大的樣本可能會變（雖然方向不太可能反轉——27.33% vs 97.91%差距懸殊，不太可能是抽樣巧合）。
4. 本輪只做離散度診斷，完全沒有測任何因子/策略，離散度夠只代表「這個池子理論上有東西可挖」，不代表已經有能用的訊號。

零因子/策略判定，跟round332/335/338/341/344同precedent不寫`TRIALS_LEDGER.md`列，補記`FUT_LEADS.md`。結果存`data/fut_stock_futures_dispersion_coverage_round347.csv`（19檔覆蓋率明細）、`data/fut_stock_futures_dispersion_summary_round347.csv`（離散度摘要）、`fut_stock_futures_dispersion_round347_run.log`（原始輸出）。17次新API呼叫（19檔扣除CDF/CCF既有快取），全程遵守`RATE_LIMIT_MIN_INTERVAL_SEC=3.0`節流，未遭遇限流。`is_holdout_consumed()`開工/收工前皆確認`False`。

**下一步**：(a) 設計不要求全體成員同時存在的滾動式宇宙/窗口建構，把可用樣本期間從250天延長（不同世代的個股期貨輪流加入池子，類似股票universe的動態成分股精神）；(b) 修/繞過skipped_rollover_events較多代碼的資料品質缺口（先只用0 skipped的8檔子集做第一版驗證，或研究能否從其他資料源補上缺報價）；(c) 若(a)(b)完成，才是這個方向可以開始設計橫斷面因子（動能/反轉/成交量等）的地基完成點。

---

## 第352輪（2026-09-05，FUT）

**接續round348下一步(a)+(b)**：19檔F結尾個股期貨離散度/PCA結果（dispersion_ratio=1.6371、PC1=27.33%）建立在只有250個交易日的重疊窗口（被最晚掛牌的SXF拖累）、且11/19檔有非零skipped_rollover_events（轉倉價格銜接不乾淨）之上，本輪同時處理這兩個限制。

新增`fut_stock_futures_dispersion_clean_subset.py`（唯讀，import重用`fut_stock_futures_dispersion_test.py`的`build_return_panel()`/`compute_dispersion()`，不修改原腳本本身），在round348已快取的19檔面板上切出兩個子集，零新增API呼叫：

1. **(b) 資料品質乾淨子集**：8檔0-skipped_rollover_events（CCF/CDF/OLF/PAF/QRF/RFF/RUF/ZFF）。重疊窗口2023-08-02~2024-12-31（346天，比19檔版略長）。**dispersion_ratio=0.8574、PC1=37.72%、PC1+PC2+PC3=61.95%、平均兩兩相關係數=0.2652**。
2. **(a) 長窗口子集**：4檔0-skipped且2018年前掛牌（CCF/CDF/OLF/PAF）。重疊窗口延長到2018-05-03~2024-12-31（1623天，是19檔版250天的6.5倍）。**dispersion_ratio=0.9052、PC1=42.25%、PC1+PC2+PC3=86.41%、平均兩兩相關係數=0.2080**。

**誠實解讀（不能只挑對自己有利的數字）**：兩個乾淨子集的dispersion_ratio（0.86、0.91）都明顯低於round348原始19檔結果（1.6371）、PC1解釋變異（37.72%、42.25%）都明顯高於原始19檔結果（27.33%）——代表round348偏樂觀的離散度數字，有一部分可能來自那11檔非零skipped_rollover_events代碼的轉倉銜接雜訊（機械性不連續造成的虛假變異），不是全部都是真實的橫斷面獨立性。**但即使拿掉這個雜訊，乾淨子集的dispersion_ratio（0.86~0.91）仍然遠優於round338 TX/MTX/TE指數期貨家族的0.1143（高7~8倍）、PC1（37.72%~42.25%）仍然遠低於TX/MTX/TE的97.91%**——核心結論「個股期貨池比指數期貨池更具跨商品橫斷面獨立性」依然成立，只是幅度應該從round348的「14倍/一個數量級」下修到「7~8倍」這個更保守、更站得住腳的數字。

**另一個誠實限制**：4檔長窗口子集PC1+PC2+PC3=86.41%——即使只是4檔的池子，3個主成分就解釋了86%變異，比8檔短窗口子集的61.95%集中得多，樣本數太小本身也會系統性推高PC1集中度（4檔的相關矩陣自由度有限），這個數字的可信度低於8檔版本，只能當作「窗口延長後的參考點」，不是更強的證據。

**副作用觀察，非本輪判定範圍**：`compute_dispersion()`的`avg_cs_range_daily_pct`欄位在round347原始輸出跟本輪兩個子集都是`inf`（用`git show`確認round347的CSV本來就有這個值，不是本輪引入的新問題），可能是某天某檔報酬因轉倉調整或除權息缺口產生極端值導致`max-min`爆炸；這個欄位目前沒有被用在任何判定邏輯裡（dispersion_ratio用的是`daily_cs_std`不是`daily_cs_range`），先誠實記錄，不在本輪修，留給之後真的要用到這個欄位時再處理。

零因子/策略判定，跟round332/335/338/341/344/348同precedent不寫`TRIALS_LEDGER.md`列，補記`FUT_LEADS.md`。結果存`data/fut_stock_futures_dispersion_clean_subset_round349.csv`、`fut_stock_futures_dispersion_clean_subset_run.log`（原始輸出，主控台編碼是Big5導致中文亂碼但數字可讀，未來若要重跑建議加`chcp 65001`或改用`PYTHONIOENCODING=utf-8`）。零新增API呼叫（全部命中round347/348既有快取）。`is_holdout_consumed()`開工/收工前皆確認`False`。

**下一步**：round348下一步(a)(b)已完成初步處理（本輪），round348下一步(c)「開始設計橫斷面因子的地基完成點」下一輪可以考慮開始，但先決條件是要決定用哪個子集（8檔短窗口 vs 4檔長窗口，各有取捨：更多標的vs更長歷史），或者研究round348原本提過的「滾動式宇宙」——不要求全體同時存在、依上市時間動態納入池子的成分股精神，這樣可能同時保留樣本數跟窗口長度，是比二選一子集更好的長期方向，值得下一輪評估可行性。
## 第355輪（2026-09-05T04:04+08:00，FUT）：round348下一步(c)前置——「滾動式宇宙」可行性評估

**取鎖時偵測到`LOCK_STALE`（pid 55412持有29.9分鐘後被回收）——上一輪（應為round354後、round355之前某輪，但`MARATHON_STATE.md`計數器顯示上一輪就是US round354，代表這是round354結束後、下一輪自然排程之間鎖檔異常，而非round354本身失敗；`MARATHON_STATE.md`round354心跳條目本身完整、有正常收工敘述，判斷是round354成功結束、正常釋放鎖之後、下一次30分鐘排程啟動時鎖檔status殘留或某次極短暫的異常執行——本輪未深究根因，如實記錄「取鎖偵測到陳舊鎖檔」這個事實，供後續比對。**

三軌時間戳：TW 03:26（第353輪，最新）／US 03:42（第354輪，更新）／FUT 02:35（第352輪，最舊）——依輪替選FUT。

**開工前風險評估（新增，因應US round354/TW round353都記錄的CPU資源競爭發現）**：`ps -ef`確認TW round353留下的背景process（`deep_dive_loo_no_low_vol.py`，pid 1427）本輪開工時**仍在運行**（自03:03起、已運行近1小時），是US round354記錄的「多輪馬拉松背景process疊加造成CPU資源競爭」現象的延續證據。**因此本輪工作單位刻意避開任何N=100隨機控制組等級的重度Monte Carlo模擬**，選擇round352下一步(c)的前半段（「決定用哪個子集，或研究滾動式宇宙可行性」）中純讀取快取、無重度計算的那一半：滾動式宇宙可行性評估。

**做了什麼**：新增`fut_stock_futures_rolling_universe_probe.py`（import重用`continuous_contract.build_continuous_series()`，19碼全部命中round347/348/349已建立的`2000-01-01~2024-12-31`完整快取，**零新增API呼叫**，執行耗時<10秒，完全不涉及round353/354同款的重度模擬瓶頸）。對round344篩出的19檔F結尾個股期貨，讀出每檔實際的on-disk資料起訖日，建立逐年在架數表。

**結果（誠實記錄，含限制）**：
- 19檔上市時間分散在2010-01-25（CCF/CDF最早）到2023-12-18（SXF最晚），逐年在架數從2010年僅2檔穩定成長到2023-2024年的19檔（全數在架）。
- **關鍵發現**：2011-2024（14年窗口）逐年最低在架數=10檔；2015-2024（10年窗口）=11檔；2018-2024（7年窗口）=13檔。相較round349兩個固定子集（8檔/346天 或 4檔/1623天）的二選一取捨，**滾動式宇宙確實能同時取得更長窗口跟比8檔子集更寬的橫斷面**（例如2011-2024可以有14年、最少10檔，遠優於8檔子集的346天）。
- **誠實限制（不能過度樂觀，三點）**：
  1. 這個headcount只代表「該年有資料」（掛牌存續），**不代表「該年流動性足夠」**——round344流動性篩選（`active_days>=200`且`mean_volume>=50`口/日）只驗證過2024一年，更早年度（尤其2011-2015剛掛牌初期）的流動性完全未知，逐年在架數是上限估計，不是可交易數估計。
  2. 19檔中11檔有非零`n_skipped_rollover_events`（round347/348已記錄，本輪原樣列出對照），滾動式宇宙若納入這些非乾淨代碼，繼承既有的轉倉銜接雜訊問題，不會因為換成滾動設計而自動解決。
  3. N=10~13的橫斷面規模，跟`CALIBRATION_PROBE.md`已證實台股100檔cheap gate（每期橫截面N=54~74）在檢定力上都嫌不足（300檔重跑正在進行中）相比，**明顯更薄**——未來若真的在這個滾動宇宙上測橫斷面因子，必須預期比股票版cheap gate更低的檢定力／更寬的信賴區間，不能直接套用相同N_SHUFFLES/門檻假設檢定力足夠。

**判定**：非因子/策略判定，跟round332/335/338/341/344/348/349同precedent不寫`TRIALS_LEDGER.md`列，補記`FUT_LEADS.md`。

**產出檔案**：`fut_stock_futures_rolling_universe_probe.py`（新增）、`data/fut_stock_futures_rolling_universe_probe_round355.csv`（19碼逐檔起訖日）、`data/fut_stock_futures_rolling_universe_yearcounts_round355.csv`（逐年在架數，gitignored）、`fut_stock_futures_rolling_universe_probe_run.log`（原始主控台輸出）。

`is_holdout_consumed()`開工/收工前皆確認`False`。零新增API呼叫。

**下一步**：round348下一步(c)前置條件至此完成（子集取捨 vs 滾動宇宙可行性兩個問題都已有數據支持）——**建議下一輪FUT工作單位＝真正動手設計橫斷面因子/建構滾動宇宙面板本身**（例如挑2015-2024十年窗口、最低N=11的版本，先做流動性驗證延伸到全部年度而非只查2024，再决定要不要繼續走這個方向），或者若CPU資源競爭問題仍未解決，優先處理輕量級（非重度模擬）的候選工作單位。**同時提醒下一輪**：開工先跑`ps -ef`確認背景process是否已結束，避免在資源競爭仍存在時啟動另一個重度模擬（沿用US round354已建立的precedent）。

## 2026-09-05T05:33+08:00 — 第358輪（FUT軌）

**取鎖乾淨**（非陳舊鎖檔）。三軌時間戳：FUT 04:04（第355輪，最舊）／TW 04:32（第356輪）／US 05:13（第357輪，最新）——依輪替選FUT。

**開工前置確認**：先讀`CALIBRATION_PROBE.md`「結論」一節（`MARATHON_PROTOCOL.md`第0節第3點硬性要求）——結論(乙)檢定力不足，給馬拉松的操作指令對FUT軌是`#34`同理重跑，但查`TRIALS_LEDGER.md`#99（2026-09-04，FUT）已經查證過這件事對FUT不成立（TX只有單一連續合約序列，沒有股票那種可擴大的橫斷面維度；`FULL_HISTORY_END`已等於holdout邊界不能再延伸；`N_SHUFFLES`加密是蒙地卡羅精度不是檢定力）——**這個待辦已結案，本輪不重複**。`ps -ef`確認背景process狀態：僅US round357留下的`deep_dive_f_us_value_bm.py -u`（pid 1905）仍在跑，非FUT軌process，不影響本輪。

**本輪工作單位＝round355「下一步」建議的第一項：延伸流動性驗證到全部年度**（round355誠實限制(1)：「在架數只代表掛牌存續，不代表流動性足夠，round344流動性篩選只驗證過2024一年」）。新增`fut_stock_futures_liquidity_by_year.py`（重用`continuous_contract.build_continuous_series()`，跟round347/348/349/352/355命中同一組19檔全歷史快取key，**零新增API呼叫**）：對round344既有19檔候選（`CCF/CDF/EHF/FYF/GMF/HBF/HQF/ITF/JWF/KKF/NWF/OLF/PAF/QDF/QRF/RFF/RUF/SXF/ZFF`）逐年（2010-2024）套用round344**原封不動**的門檻（>=200個交易日有front-month報價 且 平均日量>=50口，**沿用round344既有數字、事前綁定，未看結果前重訂門檻，避免破壞hash-lock紀律**）。

**結果（誠實地推翻round355的樂觀讀數）**：round355「逐年在架數」表（僅計算「有沒有掛牌」）與本輪「逐年**流動**在架數」表（掛牌**且**達流動性門檻）數字差距巨大：

| 候選窗口 | round355「在架」最低headcount | 本輪「流動」最低headcount |
|---|---|---|
| 2011-2024（14年） | 10 | **2** |
| 2015-2024（10年） | 11 | **3** |
| 2018-2024（7年） | 13 | **6** |
| 2021-2024（4年） | — | 10 |
| 2022-2024（3年） | — | 12 |
| 2024-2024（1年） | 19 | 19 |

**只有`CCF`／`CDF`兩檔在15年（2010-2024）全部檢查年度都達流動性門檻（100%）**；其餘17檔多數是「近幾年才變流動」或「時有時無」（例如`ITF`14年裡只有5年流動、`JWF`14年裡只有2年流動、`EHF`/`KKF`皆35.7%）。**推翻round355的樂觀結論**：round355的「2011-2024最低10檔/2015-2024最低11檔」只是「有沒有掛牌」的計數，一旦要求流動性，這兩個窗口的真實可用橫斷面規模崩塌到2~3檔——跟round349已經放棄的固定子集（8檔/346天）相比並沒有明顯優勢，滾動式宇宙的「魚與熊掌兼得」承諾在流動性檢驗下不成立。真正達到N=10以上流動橫斷面的窗口只剩2021-2024（4年，N=10）或更短，用長窗口換寬橫斷面的原始構想失敗。

**下一步建議**：round348(c)「設計橫斷面因子」這個前置決策現在有了誠實數字可以選——(a) 走`CCF`/`CDF`兩檔15年長窗口（但N=2橫斷面太窄，做不了真正的cross-sectional排序因子，頂多是這兩檔之間的相對強弱，統計檢定力極低）；(b) 走2021-2024或2022-2024短窗口（N=10~12，橫斷面夠寬但樣本只有3~4年，跟`CALIBRATION_PROBE.md`已證實100檔台股cheap gate都檢定力不足相比，這個規模的因子測試幾乎注定測不出訊號，除非效應量極強）；(c) 放棄個股期貨橫斷面因子這個方向，改回TX/MTX/TE多商品池或TX單一商品的時序類假說（第3節既有清單：多時間框架趨勢/突破/波動regime/期現價差等，這些不需要橫斷面維度）。**本輪不替下一輪做決定**，誠實列出三個選項留給下一輪或使用者判斷，因為這個決定會影響後續好幾輪的方向,不應該在資料probe腳本裡順手決定。

非因子/策略判定（讀不出edge，只是資料可行性查證），跟round332/335/338/341/344/348/349/355同precedent，**不佔`TRIALS_LEDGER.md`列**，補記`FUT_LEADS.md`。結果存`data/fut_stock_futures_liquidity_by_year_round358.csv`，原始輸出`fut_stock_futures_liquidity_by_year_round358.log`。`is_holdout_consumed()`開工/收工前皆確認`False`。零新增API呼叫。
