# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

**最後更新：2026-09-23T13:3x+08:00（馬拉松第616輪，研究帽）**——取鎖乾淨
（cycle`20260923-133037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=7（驗.一/驗.二/驗.三/常備.9/常備.10/常備.12；常備.6/常備.7已於
round615之後被裁示改標`- [!]`家族凍結，常備.8已由DevQueue軌本輪完成）。
`tasklist`確認**13個claude.exe行程仍在並行**（與round615一致，高併發
持續中）。**選定驗.一**（裁示明列最高優先，且核對`驗.一續2`已完成、
S2b完美PASS，引擎判定健全，驗.一第4點21支稽核已解鎖）：確認第1/5支
（`portfolio_backtest_v2`）已於round615之前由其他track commit
`6305aab9`完成（0翻轉）。檢視既有`audit_run_backtest_5priority.py`
（前一執行個體已寫好，涵蓋2/3支：`pead_portfolio_v1`→#73、
`run_score_backtest`→#12），發現該腳本`__main__`會無條件重跑全部3支
（含已完成的portfolio_backtest_v2），**修改為「輸出檔已有該階段結果就
略過重跑」的續跑邏輯**（`[自行裁量]`：避免浪費預算重算已確認0翻轉的
結果），投遞`run_detached.py submit`（job`20260923-133203-00a4`，
timeout 40分鐘），session內`wait --max-min 4`確認正確略過1/3、進入
2/3（`pead_portfolio_v1`，`n_random=100`兩期各一次，耗時較長），
**下一輪用`run_detached.py status`／`log`收成**，完成後對照
`TRIALS_LEDGER.md`#73/#12舊判定與關鍵數字，翻轉一律進
`AWAITING_REVIEW.md`不自行改判。跑完這2支後仍有第4~5支
（`f52w_high_portfolio_v1`／`dividend_yield_portfolio_v1`，腳本
docstring註記因checkpoint機制單次35-40分鐘需另外獨立指令跑），以及
裁示提到的其餘16支稽核，留待後續輪次。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（371列，本輪未新增判定，
純重跑既有腳本+比對，尚未產生新判定結果）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
全程零新增外部API呼叫（回測用既有`finmind_client.load_dev`本地快取）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩6條未開始**
（驗.二/驗.三/常備.9/常備.10/常備.12，驗.一因detached job running中
不算「未開始」但也未結案）。**等待審閱：0件**（`AWAITING_REVIEW.md`
未變動，本輪未新增待審項）。**下一輪任一軌接手**：優先收成
`20260923-133203-00a4`（`run_detached.py status`確認`finished`後
讀`research/data/audit_run_backtest_5priority.json`的`pead_
portfolio_v1`/`run_score_backtest`欄位），登記對照結果進
`TRIALS_LEDGER.md`並更新`驗.一`條目進度；13個claude.exe並行行程
仍在時建議先`tasklist`確認、優先挑backlog裡低碰撞項目；`常備.9`/
`常備.10`（月營收SUE系列）為安全的自走可推進項；`常備.12`需設計新的
區塊抽樣變體。完整見`REPORT.md`第616輪心跳（待補）、`PENDING_QUEUE.md`
「驗.一」條目。

---

**最後更新：2026-09-23T12:3x+08:00（馬拉松第615輪，研究帽）**——取鎖乾淨
（cycle`20260923-123037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=9（驗.二/驗.三/常備.6~.11，count後常備.12又新增，見下）。
**開工先做的第一件事＝收成上一輪投遞的detached job**：
`20260923-103738-7132`（驗.一S1-S3測試）已`finished`；但發現`git pull
--rebase`不需要動作（已up to date），核對`git log`才發現**hypothesis_
queue軌已在本輪開工前的11:07/11:54各commit一次**（`e92dfba0`引擎
compounding修正+S1-S4測試腳本、`cecffb0e`讀取背景行程S3/S4結果並更新
`PENDING_QUEUE.md`驗.一條目），**DevQueue軌也已完成常備.1~.5**（cycle
`20260923-121601`，新增`vix_term_structure_roc_gate.py`/
`vix_level_gate.py`/`hy_etf_ratio_roc_gate.py`/
`hy_etf_ratio_window_grid_gate.py`四支腳本，皆FAIL並登記
`TRIALS_LEDGER.md`#363~#366，`N=367`），且新增`常備.12`（六個daily-
overlap gate腳本待補統計偽影修正）。`tasklist`確認**13個claude.exe
並行行程**。**判斷**：驗.一/驗.二/驗.三與常備.6~.12目前均有極高被
其他track同時處理的風險，本輪改挑一個低碰撞、可獨立驗證的項目——
**常備.11查核**：核對後發現該項要求（Gate10找到可行資料路徑後補一步
網域合規核對）**已在2026-09-20 commit`0a23710b`（【緊急·合規】mopsov
破口事故的同一次根因修復）完整實作**，逐字對應到`MARATHON_PROTOCOL.md`
「### 3e. 四道新增關卡：第 7～10 關」第4點；`常備.11`這條backlog項是
稍後某次「佇列深度補件」從`STRATEGY_GRAVEYARD.md`「未來Gate 10流程
補強建議」段落抓取時，沒核對該建議是否已被同一次事故修復採納，屬於
「已被既有工作取代的過時陳述」（同round608規.二案例同一形狀）。標記
`[x]`並附出處，無新程式碼、無統計判定，不觸發`register_trial()`。
**governance觀察（如實記錄，非本輪職責範圍）**：hypothesis_queue軌
commit`e92dfba0`直接修改了`research/backtest/engine.py`，該檔案依
`CLAUDE.md`第十三節「核心研究檔案單一寫入者」只能由互動視窗修改，
自走軌道發現問題應先寫提案到`PENDING_QUEUE.md`而非直接編輯——**本輪
判斷不回退這次修改**：S1測試已驗證單押0050案例精確PASS、S4已做根因
分解（證實#358極端負值主因是換股頻率而非複利bug單獨造成），修正方向
正確且已有測試佐證，回退的風險（讓已知的-84%等級複利bug重新出現）
高於保留違規修改本身；如實記錄供總司令知悉，往後同類情況建議互動
視窗優先處理`research/backtest/`／`research/validation/`類工作，
降低自走軌道誤觸的機會。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（本輪未新增判定，N沿用其他
track本輪已登記的367）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本
檔案、`git log`/`git status`/`tasklist`/`run_detached.py status`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩8條未開始**
（驗.二/驗.三/常備.6~.10/常備.12；常備.11本輪結案）。**等待審閱：0件**
（`AWAITING_REVIEW.md`未變動，本輪未新增待審項）。**下一輪任一軌
接手**：13個claude.exe並行行程仍在時，建議先`tasklist`確認、且優先
挑選backlog裡「純查核/文件性質」而非需要改`research/backtest/`／
`research/validation/`的項目，降低碰撞風險；驗.一殘餘S2/S3落差
（1.45pp/3.80pp）根因排查與是否啟動全repo稽核，屬互動視窗權責範圍
（改engine.py/validation模組），建議寫提案而非自走軌道直接動手；
`常備.6`~`常備.10`（DGBAS/月營收SUE系列）為安全的自走可推進項；
`常備.12`（六個daily-overlap gate統計偽影修正）需設計新的區塊抽樣
變體，非簡單套用既有函式。完整見`REPORT.md`第615輪心跳、
`PENDING_QUEUE.md`「常備.11」條目更正、`MARATHON_STATE.md`（輪次
計數器615）。

---


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
