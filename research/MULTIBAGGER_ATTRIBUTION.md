# 飆股歸因分解（衛星倉·描述性研究）——進度記錄

對應 `PENDING_QUEUE.md`「重構.B」／2026-09-18（續3）總司令裁示。

## ⚠️ 本輪（馬拉松，2026-09-18 20:33，收成150+150分層抽樣）發現新混雜因子，數字暫不可採信

**收成job_id=`20260918-193308-c1c6`**（19:33:08投遞、19:51:07結束、exit=0）：
`n_ok=154`／`n_skipped=146`。分層拆解：
- `active`：150檔、skip 19檔（**12.7%**）、skip原因`price_too_short`13／
  `no_data_found`6。
- `delisted`：150檔、skip **127**檔（**84.7%**）、skip原因`fetch_error`
  **121**（95.3%的delisted skip都是這一類）／`price_too_short`3／
  `no_data_found`3。
- two-proportion pooled z-test：z=12.48，p≈0，差異在統計上極顯著。

**但發現一個系統性混雜因子，這個84.7%目前不能當作「delisted真實覆蓋率」
的結論**：`stratified_sample()`用`pd.concat([active組, delisted組])`
組樣本，Python dict插入順序保留，**active全部150檔排在前面、delisted
全部150檔排在後面**，`main()`是逐檔依序處理（`for i, row in
sample.iterrows()`）。核對`data/rate_limit_state.json`：這次執行期間
FinMind額度在**19:49:33**被打到402（`block_reason`含
`"Requests reach the upper limit"`），而這個job是19:33:08開始、
19:51:07結束——**額度耗盡發生在整個18分鐘執行過程的倒數約1.5分鐘**，
剛好落在「後半段幾乎全是delisted」這個區間附近。而`adjusted_price_
series()`的架構是yfinance優先、FinMind只當fallback（見`adjust.py`
docstring）——active股多半yfinance就能滿足、很少觸及FinMind；
delisted股yfinance覆蓋率低（本次log裡有大量`possibly delisted; no
timezone found`警告），幾乎每一檔都要fallback到FinMind，也因此對FinMind
額度的依賴遠高於active股。**這代表「delisted股系統性排在額度耗盡之後
處理」跟「delisted股systematically觸發fetch_error」這兩件事互相
糾纏，目前的84.7%無法排除是「處理順序恰好讓delisted撞上額度耗盡的
尾段」造成的，而不是「delisted股本身查無資料」**。

**與更早一輪（未分層、300檔隨機抽樣，job=`20260918-170334-11f1`）的
數字對照**：那次delisted僅14檔（樣本太小），skip率35.7% vs active
14.0%——差距遠小於這次的84.7% vs 12.7%。如果delisted真實skip率是
35%量級，這次84.7%的落差幅度（多出約50個百分點）大到不像單純樣本
雜訊，更像混雜因子造成的系統性膨脹，這進一步支持上面的懷疑。

**已修正的bug（本輪順手修，屬於「明確壞掉的東西」的bug修復，非新設計，
不需要另外提案）**：`multibagger_attribution.py::main()`新增
`sample = sample.sample(frac=1.0, random_state=SAMPLE_SEED)`，用同一
組固定種子把分層樣本的**處理順序**打散（不改變抽樣組成本身、不改變
`strata_info`／`population_weight`），讓額度耗盡（如果再次發生）平均
分攤到兩組，不再系統性偏向排在後面的那組。

**誠實結論：這次150+150分層抽樣的84.7% vs 12.7%不得引用為「delisted
真實覆蓋率」的結論，「下一輪待做」第3點（用分層抽樣結果評估要不要放大到
全宇宙）目前還不能執行——需要先用打散處理順序後的乾淨版本重新收集一次
乾淨的分層抽樣數字，才能真正回答第3點。**

**下一步（FinMind額度預計2026-09-18 21:49:34+08:00解除後執行）**：
1. 重新投遞150+150分層抽樣（沿用相同`SAMPLE_SEED=42`、
   `SAMPLE_PER_STRATUM=150`，只是這次處理順序已打散），確認過程中
   `rate_limit_state.json`沒有中途被block（若又被block，代表這個
   樣本量本身在單次執行內就會耗盡FinMind免費額度，屬於另一個需要
   解決的問題，例如拆成多個更小批次分開時段跑，而不是照樣採信那次
   結果）。
2. 拿到乾淨數字後才回到「下一輪待做」第3點，評估要不要放大到全宇宙——
   這是需要總司令核准的決策，本輪不自行執行。

## 上一輪（馬拉松第548輪，2026-09-18 19:33，FinMind解封後接續）做了什麼

**對應「下一輪待做」第1、2點。**

1. **完成1.2（4檔delisted `no_data_found`代號手動逐一驗證）**：FinMind
   額度已於19:18:53解封，用`load_dev("TaiwanStockPrice", sid,
   "2000-01-01")`逐檔查詢`8710`／`3001`／`2398`／`1422`，**四檔全部
   回空（0列），且都沒有拋出`RuntimeError`**（`finmind_client.py`的
   `_rate_limit_wait_or_raise()`在封鎖冷卻中會直接raise，不會回空，
   所以「回空且無例外」可排除是額度問題偽裝成無資料）。**結論：這4檔
   在FinMind確實查無資料，`no_data_found`分類成立，不是fetch_error誤判**。
   查證紀錄至此完整（3種可能結果——有列數/回空/RuntimeError——本輪
   實測4檔全部落在「回空」這一類）。
2. **投遞正式規模150+150分層抽樣工作**：`SAMPLE_PER_STRATUM`環境變數
   未設定（沿用程式碼預設值150），`run_detached.py submit --name
   multibagger_attribution_stratified_150 --timeout-min 40`，
   job_id=`20260918-193308-c1c6`，session內等待逾時仍在背景執行
   （已脫離session），下一輪用`run_detached.py status`/`log
   20260918-193308-c1c6`收成，預期產出覆寫
   `research/multibagger_raw/run_summary.json`。
3. 未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區；
   `validation/holdout.py::is_holdout_consumed()`開工前確認`False`；
   本輪僅4次單檔FinMind查詢（額度剛解封，刻意輕量），未觸發新的
   額度封鎖。

**⚠️ PIT-safe不等於沒有前視，這是兩件事**（2026-09-18 Cowork【重構.B收成
前必修】裁示）：本檔案裡每一個特徵數值都是用`_asof_value()`嚴格限制
`pit_date <= asof日期`查出來的，這個查詢本身永遠是PIT-safe的。但如果
**事件標記方式本身選錯了asof日期**（例如舊版把漲勢中段的月份誤標成
「起漲前」），PIT-safe的查詢一樣會忠實地回傳「那個錯誤時間點當下可得
的資料」，產生的特徵仍然是系統性前視污染的——這正是本輪修復的第1、2項
bug的根因，見下方「本輪」小節。**任何引用本檔案數字的人，看到
「PIT-safe」四個字不代表可以跳過檢查事件標記邏輯本身對不對。**

## ⛔ 撤回先前結論（2026-09-18，Cowork【重構.B續·先別放棄】裁示查證後）

**先前「台股下市股價格覆蓋不足，判定存活者偏誤阻塞，不放大到全宇宙」
這個結論，證據不足，已撤回。**

**為什麼撤回**：那個結論的唯一證據是job log裡208行yfinance的
`possibly delisted; no timezone found`警告，**FinMind那一半完全沒有
查證**——`process_stock()`舊版用`except Exception`把「真的沒有這檔
資料」「有資料但太短」「FinMind額度/冷卻/HTTP錯誤（節流，不是覆蓋
不足）」三種完全不同的狀況收斂成同一個`skip_reason`字串，沒辦法從
結果反推是哪一種。

**查證結果**（本輪修好`process_stock()`例外分類後，用同一組
`SAMPLE_SEED=42`重跑300檔隨機抽樣，`job_id=20260918-170334-11f1`）：
- `n_ok=255`／`n_skipped=45`（**85%成功**，遠優於舊job的126/300=42%）。
- 45筆skip依四類分解：`no_data_found`（真的查無此檔）22筆
  **48.9%**、`fetch_error`（FinMind額度/冷卻/HTTP錯誤）13筆
  **28.9%**、`price_too_short`（有資料但<260天）10筆**22.2%**。
- 按總司令（透過Cowork）定的判準：「只有當(b)佔壓倒性多數...才可以
  維持結論，否則必須撤回」——**48.9%不構成「壓倒性多數」**，這個
  判準的第一個條件就沒有滿足，結論**依規則必須撤回**，不需要等到
  第2步5檔手動驗證的結果才能下這個判斷。
- 相同一批資料裡`active` vs `delisted`的skip率仍有統計上顯著差異
  （delisted 35.7% vs active 14.0%，two-proportion z-test
  p=0.026）——**這代表下市股skip率確實比較高不是假的**，但幅度遠
  小於舊結論暗示的「雙雙覆蓋不足」，而且未排除這14檔delisted樣本數
  太小（僅14檔）本身的抽樣雜訊，見下方「二」分層抽樣就是為了解決
  這個樣本數不足的問題。

**額外發現（附帶但重要）**：這次300檔重跑本身，在跑完的最後一刻把
FinMind的免費額度打到402上限，觸發**2小時**冷卻封鎖（`data/
rate_limit_state.json`記錄`blocked_until`＝2026-09-18T19:18:53+08:00）
——這件事本身就是「(c) fetch_error/節流」是真實、非邊緣案例限制的
直接證據：**一次300檔規模的研究工作本身就足以吃光FinMind免費額度**，
過去把大量skip歸因於「資料源覆蓋不足」而非「額度打完」，某種程度上
是倒果為因。

**尚未完成（如實記錄，不影響上面撤回的判斷，因為判準的第一條已經
不成立）**：
- 1.2（5檔delisted `no_data_found`代號用`load_dev()`單檔逐一驗證）
  **因FinMind目前封鎖中（預計2026-09-18 19:18:53+08:00解除）尚未
  執行**，候選代號已從這次重跑結果取得：`8710`／`3001`／`2398`／
  `1422`（**只有4檔，不是5檔**——這組300檔隨機樣本裡`delisted`×
  `no_data_found`剛好只有4筆，誠實記錄樣本限制，不湊一個假的第5檔）。
  留給下一輪FinMind額度恢復後執行，屬於補充查證，不是撤回結論的
  前提條件。
- 二（分層抽樣）已完成程式碼實作（見下方「本輪」小節），但**尚未
  用正式的150+150規模跑一次**——FinMind目前封鎖中，此刻跑只會讓
  大量delisted樣本落在`fetch_error`而非真實訊號，會產生跟這次
  「額外發現」一樣的污染，留到解封後才有意義。

## 本輪（互動視窗CC，2026-09-18，Cowork【重構.B收成前必修】三項修復）做了什麼

**在下面三項修好之前，300檔背景工作（job_id=`20260918-140419-49bf`）的
`n_moonshot_windows_total=1351`／逐年基準機率等數字，一律不得引用為
結論**——那批數字是用修復前的程式碼跑出來的，帶有本輪修的三個系統性
偏誤，跟20/6檔煙霧測試數字一樣，只能證明管線能跑，不能拿來回答五題。

1. **事件去重疊（最重要）**：`_find_moonshot_windows()`原本回傳每一個
   滿足12個月窗報酬>=100%的「月份」，一次上漲的整段連續達標期間每個月
   都各算一筆——20檔煙霧測試量到17檔跑進核心計算、產生198個窗口
   （11.6筆/檔）。改成「episode」：上升緣偵測（上個月不達標、這個月
   達標才記一筆）+ 記完冷卻12個月才能再記下一筆 + 保留
   `episode_length_months`/`peak_return`兩個欄位不丟資訊。**驗收（同一
   組20檔重跑，`SAMPLE_SEED=42`可重現）**：episode數從198降到**39**
   （17檔平均2.3筆/episode，不是預期的「20上下」但同一個量級的骤降，
   198→39是近5倍的縮減，方向與量級都印證了灌水假說）。掉最多的三檔：
   `2436`（31→5，episode_length_months=[1,1,3,4,10]）、`6538`
   （25→2，[19,6]）、`2504`（22→5，[4,2,2,3,5]）——注意`6538`兩次
   episode本身持續很久（19個月、6個月），代表它是「少數幾次真正的大
   漲，但每次都撐很久」，不是「頻繁短暫達標」，這正是去重疊要保留
   `episode_length_months`的原因：光看episode數掉很多，不代表這檔股票
   不常起飛，可能只是每次起飛持續得比別人久。
2. **起漲前特徵基準修正**：`_pre_window_features()`原本直接用
   `window_start`當asof日期。去重疊後`window_start`本身已經是正確的
   episode起點，但為了不踩「window_start當月價格本身是12個月報酬分母」
   這條邊界，特徵基準改成**episode起點的前一個月月底**，新增
   `feature_asof_date`欄位記錄實際取值日。同時修正一個連帶發現的
   bug：歸因分解（第2題）用的`eps_start`/`close_start`必須維持在
   `window_start`當天（不能跟著features的新asof日期一起往前移一個月，
   否則EPS成長貢獻的計算會摻進一個月的時間差雜訊），這兩者現在各自
   獨立取值，不再共用同一個變數。
3. **存活者偏誤skip率分解**：新增`_survivorship_skip_breakdown()`，
   輸出active/delisted兩組的總檔數/成功/skip率/skip_reason分布，並用
   two-proportion pooled z-test檢定兩組skip率是否有顯著差異，顯著時
   在stdout印粗體警告。**20檔煙霧測試的初步數字**（樣本太小，z檢定
   因delisted組n=2<5門檻直接回傳無法檢定，這不是bug是誠實揭露）：
   active 18檔skip 2檔（11.1%）、delisted 2檔skip 1檔（50.0%）——
   看起來delisted skip率高很多，但n=2完全無法下任何統計結論，這正是
   為什麼**這張表要在300檔重跑時才有意義**，20檔的數字只證明程式碼能
   跑，不能拿來說「存活者偏誤有多嚴重」。

**下一步（未在本輪完成，如實記錄）**：三項修復本身已在20檔樣本上驗證
（episode數下降符合預期方向、feature_asof_date正確產生、
status_breakdown正確分組），但**尚未拿300檔重跑**——上一輪的300檔
job_id=`20260918-140419-49bf`是用舊程式碼跑的，其
`n_ok=126`/`n_skipped=174`已知卡在「已下市股票歷史價格來源不足」這個
更早發現的阻塞點（見下方「上一輪」小節），三項修復不會改變這個成功率，
但會改變episode數與feature數值本身，需要重跑一次300檔才能拿到反映
三項修復後的正確數字，且五題結論仍然卡在原有的「已下市股價格來源」
阻塞點上，不因本輪三項修復而解除。

## 上一輪（AlphaHypothesisQueue自走，2026-09-18，收成300檔背景工作）做了什麼

**對應「下一輪待做」第1、2點**。

1. **收成 300 檔背景工作**（job_id=`20260918-140419-49bf`）：
   `run_detached.py status --json` 確認 `status=finished`、`exit_code=0`、
   `expect_exists=true`。讀 `research/multibagger_raw/run_summary.json`：
   `n_ok=126`／`n_skipped=174`（**42% 成功、58% 跳過**），
   `n_moonshot_windows_total=1351`，`n_moonshot_stocks_total=97`。
2. **skip 原因查證（不只看 `skip_reasons_sample` 前10筆，追查完整 log）**：
   `research/data/jobs/20260918-140419-49bf.log` 裡有 **208 行**
   `possibly delisted; no timezone found`（yfinance 對已下市代號的典型
   錯誤訊息），另有數十行 `Data doesn't exist for startDate=...`。
   逐一核對 `adjust.py::adjusted_price_series()` 原始碼：yfinance 空值時
   確實有 fallback 到 FinMind（`load_dev("TaiwanStockPrice", ...)`），
   但 `price_too_short` 表示**連 FinMind fallback 也不足 260 個交易日**——
   代表這 174 檔多數是「兩個價格來源都缺乏足夠歷史」，不是 fallback
   邏輯沒接上的程式錯誤。
3. **誠實結論：驗證未通過「下一輪待做」第2點的門檻，不放大到全宇宙**。
   SPEC 原文寫「300 檔驗證通過（**多數**股票真正跑進核心計算、無異常
   錯誤集中）後才放大」——42% 明確不構成「多數」（未過半）。且這不是
   隨機噪音式的錯誤集中，而是**系統性集中在已下市代號**（yfinance＋
   FinMind 對已下市股票的歷史價格覆蓋率雙雙不足），這正是
   `CLAUDE.md`七之三節「台股偽影家族⑦存活者偏誤」與「美股結論一律附
   存活者偏誤但書」在價格資料源上的同一種病灶換了個市場出現一次——
   **能跑進核心計算的 126 檔系統性偏向「還有完整長價格歷史可查」的
   股票，這本身就是存活者偏誤的來源，不是隨機缺值**。若直接放大到
   全宇宙、忽略這個偏誤，五題裡「逐年基準機率含空頭年」與「對照組
   起飛率-平庸率-**下市率**表」這兩題會被系統性低估下市股權重，
   結論不可信。
4. **阻塞點記錄（供下一輪或總司令裁示）**：在放大到全宇宙之前，需要
   先回答「已下市 TW 股票的歷史價格要從哪裡補」，這跟
   `docs/US_PRICE_SOURCES.md` 美股下市股價格缺口是同一類問題的台股版本，
   但**尚未有對應的 `docs/TW_DELISTED_PRICE_SOURCES.md` 查證紀錄**——
   這是本輪發現的新缺口，不是既有已知限制的重複記錄。可能路徑（皆未
   查證，僅列候選）：①TWSE/OTC 官方歷史資料是否保留下市股全期價格
   ②FinMind 付費層是否覆蓋下市股③接受樣本涵蓋已下市但保留在 OTC 續掛
   的期間、對真正除牌股票明確排除並在五題結論裡揭露涵蓋率。**不在本
   輪展開查證**（本輪任務範圍是收成驗證，不是開新查證分支），留給
   `重構.B` 下一輪或另行裁示。

## 上一輪（馬拉松自走，2026-09-18，接續上一輪 hypothesis_queue）做了什麼

1. **修正抽樣 bug**：`multibagger_attribution.py::main()` 改成先過濾
   `stock_id` 為 4 位純數字（排除 ETF 連結型代號 `00400A` 這類帶字母
   尾碼的樣本，`universe()` 本身的 `is_warrant` 過濾只擋 6 位純數字
   權證，不擋這種），再用固定種子（`SAMPLE_SEED=42`）隨機抽樣，取代
   舊版「依字母排序取前 N 檔」（那個取法會系統性抽到 ETF 代號）。
   刻意不動共用的 `universe.py`，只在本檔案內過濾，避免影響其他呼叫者。
2. **重跑 20 檔煙霧測試（`MULTIBAGGER_SMOKE_SIZE=20`）驗證通過**：
   宇宙總數 3196 檔，過濾掉 450 檔非 4 位數字代號後隨機抽 20 檔，
   **17/20 真正跑進 `process_stock()` 核心計算**（3 檔因
   `adjust.adjusted_price_series()` 抓不到足夠長價格序列被
   `price_too_short` 跳過，是正常情況非 bug），產出 198 個 moonshot
   窗口，`yearly_base_rate` 有 2002～2024 年逐年數字（**這仍是 20 檔
   小樣本，數字僅供驗證管線正確性，不得引用為結論**）。這證明抽樣
   bug 已修正、歸因邏輯確實能在真實普通股資料上跑出非空結果。
3. **已投遞 300 檔工作**（依裁示原文建議樣本量）：
   `run_detached.py submit --name multibagger_attribution_300`，
   job_id=`20260918-140419-49bf`，session 內等待 4 分鐘未完成（300 檔
   預估耗時遠超 20 檔的驗證輪，逐檔含多次 PIT 模組呼叫），**已脫離
   session 背景執行，下一輪用
   `python research/run_detached.py status` / `log 20260918-140419-49bf`
   收成**，預期產出 `research/multibagger_raw/run_summary.json`。

## 上一輪（hypothesis_queue 自走，2026-09-18）做了什麼

1. 建立 `research/multibagger_attribution.py`：定義「起飛事件」＝任一 12
   個月月頻滾動窗口還原權息報酬 ≥ +100%，並串接既有 PIT-safe 模組
   （`universe.universe()`／`adjust.adjusted_price_series()`／
   `pit.quarterly_pit()`／`pit.month_revenue_pit()`），逐檔 try/except
   隔離錯誤（單檔失敗不影響其他檔）。
2. 跑了一次 6 檔的管線煙霧測試（`MULTIBAGGER_SMOKE_SIZE=6`）：**程式碼
   本身跑完整個流程沒有拋出未捕捉例外，正確寫出 `run_summary.json`**，
   但抽到的 6 檔（依 stock_id 字母排序取前 6 檔）恰好全是 ETF 連結型
   代號（`00400A`～`00405A`），這類代號沒有真正的股票價格/EPS 資料，
   6 檔全部被 `price_too_short` 跳過——**這證明了錢包沒有炸掉（error
   isolation 有效），但沒有證明歸因邏輯本身算得對**，因為沒有一檔真正
   跑進 `process_stock()` 的核心計算。

## 已知缺口（截至本輪，仍待解決）

- **五題目前仍全部尚未真正回答**：20 檔驗證輪的數字只證明管線正確，
  樣本太小不能拿來回答五題（母體 3196 檔裡只抽 20 檔，逐年基準機率
  等統計量在這個樣本量下噪音極大）。**不得引用 20 檔或 6 檔輪任何
  統計數字作為結論**，要等 300 檔（下一輪收成）甚至全宇宙跑完才行。
- 第 2 題（歸因分解）目前只實作兩項嚴格對數恆等式（EPS 成長貢獻 +
  PE 變化貢獻），第三項「股數變化」因 FinMind 免費層缺可靠流通股數
  欄位，如實標為待補資料源，見程式檔頭 docstring 詳細說明，這不是
  遺漏是誠實揭露的已知限制。
- 全宇宙（依裁示原文，先小樣本再放全量）尚未開跑，本輪只完成
  20 檔驗證＋投遞 300 檔背景工作，300 檔結果尚待下一輪收成。

## 下一輪待做

**⚠️ 2026-09-18（續·先別放棄）查證後：第1點「查證已下市TW股票歷史價格
來源／建docs/TW_DELISTED_PRICE_SOURCES.md」這個阻塞已隨上方「撤回先前
結論」一併解除——舊結論的證據本身不成立，不代表「已經補齊」，而是
「原本判定阻塞的理由不夠格」，見最上方⛔小節。下面改記查證後真正該做
的事。**

1. ~~**FinMind額度恢復後（預計2026-09-18 19:18:53+08:00）補做1.2**~~
   **已完成（第548輪，見上方「本輪」小節）**：4檔全部回空、無例外，
   `no_data_found`分類確認成立。
2. ~~**FinMind額度恢復後，跑一次正式規模的分層抽樣**~~
   **已收成但發現混雜因子，判定為「無效需重跑」（馬拉松，2026-09-18
   20:33）**：job_id=`20260918-193308-c1c6`跑出delisted skip 84.7%
   vs active 12.7%，但額度耗盡時間點（19:49:33）與樣本處理順序
   （active全在前、delisted全在後）重疊，無法排除是處理順序造成的
   系統性混雜，不是delisted真實覆蓋率。已修正`main()`把處理順序打散
   （固定種子，不改變抽樣組成），**FinMind額度預計2026-09-18
   21:49:34+08:00解除後需重新投遞一次乾淨版本**才能拿到可信數字，
   詳見上方⚠️小節。
3. **用（打散處理順序後）乾淨的分層抽樣結果評估要不要放大到全宇宙**：
   SPEC原文「多數股票真正跑進核心計算」門檻——未分層隨機抽樣重跑曾達
   85%成功率（255/300），遠超過半數，但**分層抽樣目前唯一一次的結果
   因混雜因子作廢，不能拿來當決策依據**，必須先用第2點乾淨重跑後的
   delisted成功率為準——**這是需要總司令核准的放大決策，不是工程
   判斷可以自己執行的事**，依CLAUDE.md「提案先於執行」規則辦理。
4. 全宇宙（或先分層驗證通過後的下一步）跑完才能真正回答五題（逐年
   基準機率含空頭年／EPS-PE-股數三項歸因分解／起漲前PIT-safe特徵／
   對照組起飛率-平庸率-下市率表／市值門檻邊際效果），全程TRAIN+VAL、
   PIT-safe、不生選股規則。**分層抽樣算出的統計量記得用
   `population_weight`加權還原回母體比例**（見`stratified_sample()`
   docstring），不能直接拿分層樣本的比例當母體比例。
