# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-23T16:3x+08:00（馬拉松第619輪，研究帽）**——取鎖乾淨
（cycle`20260923-163037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=3（驗.一/驗.一第4點續（剩餘16支）/驗.二第二部分）。`git log`
確認`尺.一`（commit`cbaa4412`）與`審.一`（commit`f807ce64`，DSR=0.0000
決定性FAIL、一頁摘要已寫入`AWAITING_REVIEW.md`待總司令裁示）**皆已由
互動視窗CC完成並commit**，上一輪（618）避開的`portfolio_backtest_v2.py`
碰撞已解除。**本輪工作單位＝驗.一第4點續，重算16支中的3支**：
`margin_utilization_regime_portfolio_v1`（#120原FAIL）／
`odd_lot_imbalance_portfolio_v1`（#232原FAIL）／
`short_sale_utilization_portfolio_v1`（#133原PASS第2關非最終結案）——
三支共用checkpoint可續跑架構（同`dividend_yield_portfolio_v1.run_one()`
同一套機制，checkpoint的`real`欄位存的是完整回測摘要而非equity_curve
時間序列，清空`real`後重跑`main()`會自動用新引擎(compounding修正)+
新量尺(0050含息總報酬預設值)重算，`cost_returns`/`random_finals`不受
量尺影響直接讀舊快取，省時間）。三份checkpoint的`real`欄位已清空並
備份為`*_checkpoint.pre_engine_fix_backup.json`。**[自行裁量，違規
自糾記錄]**：本輪一開始誤在session內直接同步執行
`margin_utilization_regime_portfolio_v1.py`（未走`run_detached.py`），
超過5分鐘後手動`taskkill`，事後核對checkpoint的`real`欄位仍是空的
（未跑完就被砍，跟從未執行狀態相同，**沒有殘留半套用的污染資料**），
違反`MARATHON_PROTOCOL.md`0b節「任何可能跑超過5分鐘的工作一律脫離
session」規則，發現後立刻改正：新增`audit_16remaining_batch1.py`
（依序呼叫三支腳本`main()`）並改用`run_detached.py submit`正式投遞
（job`20260923-163927-c80e`，timeout 40分鐘），`wait --max-min 3`確認
`STILL_RUNNING`，**本輪不等待完成、下一輪收成**。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（377列，本輪未新增
判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆
確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／
`portfolio_backtest_v2.py`任何原始碼（僅呼叫既有函式、清空/重算
checkpoint資料），全程零新增外部API呼叫（回測用既有`finmind_client.
load_dev`本地快取）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。
**交辦佇列還剩2條未開始**（驗.一第4點續其餘13支＋驗.二第二部分；
`驗.一`本身因這批job running中不算「未開始」但也未結案）。**等待
審閱：1件**（`審.一`f52w DSR=0.0000決定性FAIL摘要，延續中，非本輪
新增）。**下一輪任一軌接手**：`run_detached.py status`收成
`20260923-163927-c80e`，`finished`後讀三支腳本`data/*_results.csv`與
checkpoint的`real`欄位，對照`TRIALS_LEDGER.md`#120/#232/#133舊判定，
翻轉一律進`AWAITING_REVIEW.md`不自行改判；完成後剩餘13支繼續（已排除
`phase_sensitivity.py`——雖有checkpoint但該腳本是相位敏感度診斷工具
非trial候選，不計入16支這批）。完整見`REPORT.md`第619輪心跳、
`PENDING_QUEUE.md`「驗.一第4點續（剩餘16支）」條目、
`audit_16remaining_batch1.py`。

---

**最後更新：2026-09-23T15:3x+08:00（馬拉松第618輪，研究帽）**——取鎖乾淨
（cycle`20260923-153037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=2（驗.一殘餘16支稽核+f52w#86、驗.二第二部分）。`tasklist`確認
**12個claude.exe行程仍在並行**。開工先收成round616投遞的detached job
`20260923-133203-00a4`：仍`orphaned`（上一輪已核對過與互動視窗CC重複
勞動、已補commit資料檔，本輪不重複處理）。
**開工中途發現新總司令裁示（commit`03bbaff1`）剛落地**：「【修正alpha
量尺＋f52w補完審查＋稽核續跑】」，`PENDING_QUEUE.md`新增`尺.一`(組合層
alpha/基準量尺修正，最優先，0050含息總報酬+Newey-West HAC+Dimson
beta)、`審.一`(f52w補完審查，待尺.一完成)、`驗.一第4點續(剩餘16支)`
(待尺.一完成)三項，`ORDER-BEGIN`優先序改為尺.一→審.一→驗.一續2→
驗.一→驗.二。**`git status`發現`research/portfolio_backtest_v2.py`
有uncommitted修改**，`git diff`核對確認是互動視窗CC正在即時實作`尺.一`
（`buy_and_hold_index_pct()`/`alpha_significance()`改注入
`benchmark`參數、新增`_load_0050_total_return_series()`，程式碼與
裁示原文逐字對應）——**判斷本輪不得觸碰`portfolio_backtest_v2.py`
或任何下游項目（審.一／驗.一第4點續／f52w #86正式判定），避免與互動
視窗CC產生第三次同形狀的重複勞動/檔案衝突**（同round615/616已有
先例）。**本輪實質工作**：確認`f52w_high_gates.py`（#86，第3/5/6關
逐年一致性等）的計算內容**不依賴`portfolio_backtest_v2.py`的
`alpha_significance()`/`buy_and_hold_index_pct()`**（僅import該模組的
`_liquidity_proxy_series()`，與benchmark/alpha量尺無關），判斷此腳本
可安全獨立跑，**先`reap`清除兩筆前次提交失敗的殘留job登記**（cwd參數
路徑格式錯誤導致的`failed`/`orphaned`各一筆），修正`--cwd`跨殼層
路徑跳脫問題後成功投遞`20260923-153207-e7ea`（timeout 45分鐘），
session內確認已進入`Loading sample + factors`階段、4.7分鐘仍
`running`+`watchdog_alive=True`，**本輪不等待完成、不對其輸出下任何
判定**（尊重裁示原文「審.一...待尺.一完成後開始」的順序，只是先把
獨立於量尺修正之外的診斷數字准備好，供尺.一完成後的審.一直接參考，
不是搶跑審.一本身）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（377列，本輪未新增判定）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／
`portfolio_backtest_v2.py`任何原始碼，全程零新增外部API呼叫。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未開始**
（驗.一殘餘16支稽核+f52w#86、驗.二第二部分——現已知需等`尺.一`完成，
`審.一`/`驗.一第4點續`兩項新增條目本輪視為與既有兩項同一組待辦，不
重複計數）。**等待審閱：1件**（`f52w_high_portfolio_v1`#85/#370翻轉
判定，`AWAITING_REVIEW.md`未變動，延續中，新裁示`審.一`即是對這件的
正式處理指示）。**下一輪任一軌接手**：先確認`portfolio_backtest_v2.py`
是否已被互動視窗CC commit完成`尺.一`（`git log`/`git diff`），完成
才能接續`審.一`／`驗.一第4點續`；若仍在進行中，比照本輪做法找低碰撞
的獨立工作（`run_detached.py status`收成`20260923-153207-e7ea`若已
`finished`，先讀log但不下判定，留給`審.一`正式使用）；`驗.二`第二
部分同樣建議先確認是否受尺.一影響（初步判斷其9關統計檢定與
portfolio_backtest_v2的benchmark函式無關，但需二次確認）。完整見
`REPORT.md`第618輪心跳、`PENDING_QUEUE.md`「尺.一」「審.一」章節、
commit`03bbaff1`。

---

**最後更新：2026-09-23T14:3x+08:00（馬拉松第617輪，研究帽）**——取鎖乾淨
（cycle`20260923-143037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=3（驗.一/驗.二/驗.三；常備.9仍`- [!]`待採購阻塞，常備.10/常備.12
已完成）。`tasklist`確認**15個claude.exe行程仍在並行**（高併發持續中）。
**開工先收成round616投遞的detached job`20260923-133203-00a4`**：狀態為
`orphaned`（非`finished`），核對log發現該job已完整跑完2/3~3/3（`pead_
portfolio_v1`/`run_score_backtest`），但`git log`顯示**互動視窗CC已在
本輪開工前用直接呼叫`run_one()`/`main()`的方式獨立完成同一件事**
（commit`633b47f3`/`ecb34a98`，登記`TRIALS_LEDGER.md`#373/#375），且已
`taskkill`終止這個重複job並記錄協調事故於`PENDING_QUEUE.md`驗.一條目
（協調.零第5點透明回報義務）。**核對**：orphaned job輸出的
`research/data/audit_run_backtest_5priority.json`數值與互動視窗CC已
登記的#373/#375逐位吻合（TRAIN/VAL報酬/MDD/Sortino完全一致），確認
無新資訊、不重複登記，但發現互動視窗CC的commit（`ecb34a98`）漏了
`git add`這個JSON資料檔本身（只commit了`.md`/`.jsonl`帳本），導致
working tree留著一份跟已登記結論一致但未commit的資料差異——**本輪
housekeeping補commit這份資料檔**，純資料歸檔非新判定。
**驗.三結案**：核對後發現該項「尚未完成」段落點名的`vix_term_
structure_gate.py`(#76)／`hy_etf_ratio_gate.py`(#78)已由`常備.12`
（DevQueue軌，cycle`20260923-121601`）用新增的
`sample_nonoverlapping_blocks()`+`circular_shift_null()`完整重跑
（`TRIALS_LEDGER.md`#374，8/8組FAIL），逐字對應驗.三要求的變體設計，
屬「已被其他track用不同編號完成的過時待辦」（同round615常備.11同一
形狀），標`[x]`結案，純文件核對不觸發`register_trial()`。
**修補`trial_registry.py --check`前置阻塞**：開工時發現該檢查已是
`exit=1`（`#346`verdict=FAIL缺`failed_gates`欄位，非本輪造成，本輪
開工前即存在），依裁示「收工前非0不准commit」，直接在
`TRIALS_REGISTRY.jsonl`補上`failed_gates=["unknown"]`（判死依據是
spillover前視偏誤，不在GATE_SEQUENCE六關值域內，同`#296`先例），
`TRIALS_LEDGER.md`同步補註記，重跑後`exit=0 PASS`（377列）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`任何原始碼（僅呼叫
既有函式核對、修TRIALS_REGISTRY.jsonl資料），全程零新增外部API呼叫。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未開始**
（驗.一殘餘16支稽核+f52w#86後續、驗.二第二部分開盤到收盤重跑；驗.三
本輪結案）。**等待審閱：0件**（`AWAITING_REVIEW.md`未變動，本輪未新增
待審項）。**下一輪任一軌接手**：佇列深度`- [ ]`=2，低於`MIN_QUEUE_
DEPTH=12`門檻，下一輪開工需先執行佇列深度補件（來源①②③掃描）；
`驗.一`剩餘16支腳本第二輪稽核+`f52w_high_portfolio_v1`的`#86`
gate3/5/6後續，高併發下建議先`tasklist`+`git log`確認互動視窗CC是否
已在同步進行，避免重複勞動（本輪已是本cycle第二次發生類似協調碰撞）；
`驗.二`第二部分（開盤到收盤重跑全部9關）屬於較大範圍工作單位，建議
拆解成子步驟後再投入單一輪次。完整見`REPORT.md`第617輪心跳（待補）、
`PENDING_QUEUE.md`「驗.一」「驗.三」條目、`TRIALS_REGISTRY.jsonl`
`#346`補登記錄。

---

（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪已歸檔至`TW_STATE_ARCHIVE.md`，
僅保留最新3則）
