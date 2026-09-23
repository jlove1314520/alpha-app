# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

**最後更新：2026-09-23T10:3x+08:00（馬拉松第614輪，研究帽）**——取鎖乾淨
（cycle`20260923-103037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
本輪開工時`- [ ]`=4（**驗.一/驗.二/驗.三/驗.四**，2026-09-23總司令裁示
【三個方法缺陷＋E-c/E-d走正式閘門】新交辦，round613收工後才進佇列）——
交辦有貨，本輪名額全部給交辦，不做自走。裁示規定順序「驗.一與驗.四
並行→驗.二→驗.三」。

**驗.四（已完成）**：新增`research/regime_overlay_exit_rule_gate.py`，
E-c移動停損10%與E-d MA200regime走`REGIME_OVERLAY_PROTOCOL.md`正式閘門
（重用`exit_rule_lab.simulate()`同一套成本模型與冷卻期重入規則，不重寫
底層交易邏輯；隨機擇時對照組用block permutation，保證空手總天數與
切換次數跟真實序列完全相同，只隨機化日期落點，見腳本docstring
[自行裁量]1~5）。結果：E-c真實CAGR對照1000次隨機排列p=0.062、E-d
p=0.394，皆未達裁示寫死的p<=0.01門檻，VAL期MDD皆守住天條一
（E-c-32.11%／E-d-21.30%，優於-50%），但p這關沒過，**兩者綜合FAIL**。
登記`TRIALS_LEDGER.md`#359(E-c)/#360(E-d)，`STRATEGY_GRAVEYARD.md`補
「E-c移動停損10%／E-d MA200 regime出場」條目（第五、六個死於同一種
「方向有道理但統計檢定力不足」形狀的regime/出場機制）。
`selection_bias_ledger.py`重跑，N=361（其間偵測到有其他track同時
登記，非本輪獨占361全部增量）。E-c參數高原(24格，7~15%x10/20/40天)
CAGR範圍[8.23%,12.31%]、MDD範圍[-52.09%,-31.63%]，形狀報告不選最佳值。

**驗.一（進行中，detached job）**：發現前一個未commit的執行個體已
寫好`research/backtest_engine_soundness_test.py`（S1-S3測試組，含
docstring完整說明根因與方法），本輪核對邏輯後直接沿用執行，不重寫。
`run_detached.py submit`第一次因路徑寫成`backtest_engine_soundness_
test.py`（相對research/內部路徑，但`run_detached.py`從repo根目錄
`C:\alpha\alpha-app`執行導致找不到檔案）失敗（exit=2），第二次改用
`research/backtest_engine_soundness_test.py`正確路徑成功投遞，job id
`20260923-103738-7132`，本輪收尾時仍`running`（耗時5.5分鐘，S3做
100個seed的隨機8檔月頻回測較慢），**下一輪用`run_detached.py status`／
`log`收成S1/S2/S3結果**，S1-S3任一不過要先修引擎（`backtest/
engine.py`不複利bug）才能做驗.一後續（複利修正/下市股mark/#358稽核
翻轉重跑），不得跳過。

**驗.二/驗.三本輪未動**（依裁示順序在驗.一之後，且驗.一S1-S3結果
尚未出爐，尚不知引擎要不要先修，貿然動驗.二/驗.三的重跑意義不大，
留給下一輪視驗.一結果決定）。

`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）本輪未重跑確認
（時間有限，下一輪需補跑確認exit=0）；`validation/holdout.py::
is_holdout_consumed()`本輪未動holdout，維持`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫
（純重算既有0050價格快取＋既有樣本因子快取）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩2條未開始**（驗.二、驗.三；驗.一
`running`中不算「未開始」但也未結案）。**等待審閱：0件**（規.二第4節
掃描提案與維運.git衝突根因，皆已在round613前由總司令裁示結案，見
US_MARATHON_STATE.md round613記錄）。**下一輪任一軌接手**：優先收成
`20260923-103738-7132`（`run_detached.py status`確認`finished`後
`run_detached.py log`看S1/S2/S3輸出，或直接讀`research/data/
backtest_engine_soundness_test.json`），S1-S3全PASS才能繼續驗.一第
2~4點（複利修正/殭屍部位/#358稽核翻轉），任一FAIL要先修
`backtest/engine.py`；驗.一結案或至少S1-S3結果出爐後再排驗.二
（spillover前視偏誤重跑）、驗.三（#81虛無分布修正）。完整見
`REPORT.md`第614輪心跳（待補）、`PENDING_QUEUE.md`「2026-09-23總司令
裁示【三個方法缺陷＋E-c/E-d走正式閘門】」章節、`TRIALS_LEDGER.md`
#359/#360、`STRATEGY_GRAVEYARD.md`。

---

**最後更新：2026-09-23T07:3x+08:00（馬拉松第611輪，研究帽）**——取鎖乾淨
（cycle`20260923-073037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0，23條`- [!]`阻塞中；逐一核對阻塞項開頭解除條件（含`AWAITING_
REVIEW.md`兩件、`金流一.4`、`資料源一.3`、`#50`），皆未到解除時間點，
維持`- [!]`。**佇列深度自檢**：`- [ ]`=0（<12下限），round599~610已連續
12輪確認三個備援來源掃無新項，依round604/609既有建議本輪不重複全面
掃描，改做精簡確認。三軌時間戳：US round609=09-23 05:3x／FUT
round610=09-23 06:3x／**TW round608=09-23 04:3x（最舊）**——依輪替選TW。
`run_detached.py status`確認`running=0`（151筆歷史，無running job需
收成）。`git status`（開工時）僅例行排程檔案（`audit_report.json`／
`factory_stability*`／`connectivity_check.log`／`marathon_cycle.log`等），
無conflict標記、無孤兒未commit產出，round607修復的git stash衝突未
復發。`#50`（唯一未結案方向）tick累積**精確重新清點為12/20**（`ls
research/data/ticks/*.parquet`實測12個檔案：20260907/08/09/10/11/14/15/
16/17/18/21/22；另有一個無`.parquet`副檔名的`20260915`目錄疑為殘留
非資料檔，未計入），**更正round609記錄的「13/20」為計數誤差**，實際
未變。`AWAITING_REVIEW.md`兩件（規.二第4節掃描方式提案、維運.git衝突
根因修復方案）皆仍`等待中`，未收到總司令回應。**結論：與round604~610
連續七輪一致，TW/US/FUT三軌本輪仍無新可推進工作單位**，目前唯二解鎖
點（總司令對兩件`AWAITING_REVIEW`的裁示、tick累積至20/gate50回應）皆
非自走可推進範圍，不硬湊新項。未執行任何新統計判定，不觸發
`register_trial()`。`trial_registry.py --check`（`PYTHONIOENCODING=
utf-8`）exit=0 PASS（347列，本輪未新增判定）。`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫（純讀
既有`.md`/`.json`帳本檔案、`git status`、`run_detached.py status`、
`ls research/data/ticks/`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪
一行。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞中）。**等待審閱：
2件**（規.二第4節參數掃描方式提案／維運.git衝突根因修復方案，皆非
本輪新增，延續中）。**下一輪任一軌接手**：兩件`AWAITING_REVIEW`項是
目前TW/US集中版框架與三支wrapper git協調修復的唯一解鎖點，出爐前
建議持續比照本輪做精簡確認，不必每輪重新全面掃描三個備援來源；`#50`
仍被動等待tick累積至20（12/20）與總司令對gate50三條件的回應；依輪替
下一輪建議選US軌（US round609/FUT round610本輪皆已比TW新，但下一輪
若仍無新裁示，三軌可等距輪替即可，不必刻意避開剛碰過的軌）。完整見
`REPORT.md`第611輪心跳、`AWAITING_REVIEW.md`。


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
