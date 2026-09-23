# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-23T18:3x+08:00（馬拉松第621輪，研究帽）**——取鎖乾淨
（cycle`20260923-183037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=3（驗.一/驗.一第4點續（剩餘16支）/驗.二第二部分）。`git log`確認
互動視窗CC無新commit，工作目錄修改檔皆是例行排程檔案，非CC-only限定
路徑，無碰撞風險。`run_detached.py status`：`running=0`，收成上一輪
job`20260923-163927-c80e`（已由round620收成登記，本輪不重複）。
**本輪工作單位＝承接round620列出的候選清單，查證並修復一個範圍缺陷後
投遞剩餘2支重算**：發現`piotroski_fscore_gate_v1.py`／`run_value_board_
v2_pit_backtest.py`各自「自成一體複製一份」`alpha_significance()`／
`buy_and_hold_index_pct()`（舊版docstring自稱跟`portfolio_backtest_v2.
py`逐行一致），尺.一（commit`cbaa4412`）只改了`portfolio_backtest_v2.
py`本體，這兩支獨立複製沒有被自動更新，直接重跑只會拿到「新引擎+舊
量尺」的半套修正。**[自行裁量，判定為bug修復非新架構決策]**：修復
`run_value_board_v2_pit_backtest.py`改成直接呼叫`portfolio_backtest_v2`
的函式（import驗證通過，`piotroski_fscore_gate_v1.py`透過既有import
間接沿用，`determinism_self_test.py`為位置參數呼叫不受影響）。同時
發現`weinstein_alpha_gate.py`依賴的`long_only_vs_market.py::
decompose_alpha_beta()`也有同樣缺陷，但blast radius涵蓋4支腳本
（`portfolio_backtest.py`/`run_alpha_decomposition.py`/
`weinstein_alpha_gate.py`/`weinstein_v2_alpha_gate.py`），**本輪不動，
留給下一輪評估**。新增`audit_16remaining_batch2.py`（依序呼叫
`run_value_board_v2_pit_backtest.main()`→`piotroski_fscore_gate_v1.
main()`，順序不可顛倒，後者要讀前者產生的baseline CSV），投遞
`run_detached.py submit`（job`20260923-183404-d854`，timeout 420分鐘/
7小時——`run_value_board_v2_pit_backtest.py`跑500檔+TRAIN/VAL兩期各
100次隨機對照draws，腳本docstring記錄實測約102秒/draw，200次draws
估算上限約5.7小時，設計上跨多輪馬拉松收成）。session內確認job已進入
TRAIN期執行（讀取快取486/500檔可用，日誌顯示正常進度），本輪不等待
完成。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（386列，本輪未新增判定，純程式碼修復非統計判定）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／
`portfolio_backtest_v2.py`任何原始碼（只修改`run_value_board_v2_pit_
backtest.py`，不在CLAUDE.md「十三、核心研究檔案單一寫入者」限定清單
內），全程零新增外部API呼叫（回測讀既有本地pickle快取）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未開始**
（`驗.一第4點續`本身因job running中不算「未開始」但也未結案；驗.二）。
**等待審閱：1件**（`審.一`f52w DSR=0.0000決定性FAIL摘要，延續中，非
本輪新增）。**下一輪任一軌接手**：`run_detached.py status`收成
`20260923-183404-d854`——預估要跑數小時，若仍`running`不必每輪都查，
可先做`驗.二`或其他工作隔幾輪再回頭確認；若`finished`，讀
`data/value_board_v2_pit_backtest_liquidity500_full.csv`與
`data/piotroski_fscore_gate_v1_results.csv`，對照`TRIALS_LEDGER.md`
#93/#290/#94/#291比較新舊數字方向是否一致，翻轉一律進
`AWAITING_REVIEW.md`不自行改判；`weinstein_alpha_gate.py`同類缺陷
待決定是否修復（需先核查`run_alpha_decomposition.py`用途）。完整見
`REPORT.md`第621輪心跳、`PENDING_QUEUE.md`「驗.一第4點續」條目、
`audit_16remaining_batch2.py`。

---

**最後更新：2026-09-23T17:3x+08:00（馬拉松第620輪，研究帽）**——取鎖乾淨
（cycle`20260923-173037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=3（驗.一/驗.一第4點續（剩餘16支）/驗.二第二部分）。`git log`確認
互動視窗CC無新commit，`portfolio_backtest_v2.py`/`PENDING_QUEUE.md`無
uncommitted修改，無碰撞風險。**本輪工作單位＝收成round619投遞的job並
登記＋enumeration剩餘候選**：`run_detached.py status`確認
`20260923-163927-c80e`已`finished`（exit=0），讀job log與三支腳本輸出，
對照`TRIALS_LEDGER.md`#120/#232/#133舊判定：**3支皆0翻轉，維持FAIL**
（`margin_utilization_regime_portfolio_v1`：VAL隨機控制組percentile從
舊99.0→新0.0更決定性；`odd_lot_imbalance_portfolio_v1`：TRAIN/VAL
percentile從33.0/13.0→11.0/1.0更決定性；`short_sale_utilization_
portfolio_v1`：第2關本身從雙雙100.0→87.0/69.0未過門檻，VAL alpha p從
0.0354顯著→0.4489不顯著，補強#137既有最終FAIL判定證據力）。登記
`TRIALS_LEDGER.md`#382/#383/#384（`register_trial()`，failed_gates=
['gate2']），`trial_registry.py --check`exit=0 PASS（386列）。**16支
現況：8支完成（首5支+本輪3支，皆0翻轉），13支未開始**。
**[自行裁量，enumeration發現]**：重新grep`run_backtest(`（修正先前
`grep -v "test_"`filter誤濾掉`portfolio_backtest_v2.py`等合法候選的
bug），找到33個匹配（原估21支）；核對`data/*checkpoint*.json`發現**沒
有更多跟本輪3支同結構（`real`欄位）的續跑腳本**（僅存2個其他checkpoint
`capital_reduction_verify`/`composite_zscore_v1`是完全不同資料結構，
非同一套架構）。原始「16支」估計本身無明確逐一列名權威清單（源自「28
支裁示估計→grep找到21支」模糊過程），本輪初步過濾出候選清單（待下一輪
逐一確認是否曾用舊引擎判過）寫入`PENDING_QUEUE.md`「驗.一第4點續」條目，
同時列出明確排除項（審.一診斷工具、已凍結的`concentrated_backtest.py`、
框架自檢腳本、已用#137結案不受影響的short_sale後續關卡腳本等）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（386列）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆
確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／
`portfolio_backtest_v2.py`任何原始碼（僅呼叫既有函式收成/enumeration/
寫帳本），全程零新增外部API呼叫。`PROGRESS_HEARTBEAT.jsonl`已append
本輪一行。**交辦佇列還剩2條未開始**（驗.一第4點續其餘13支候選待確認範圍
＋驗.二第二部分）。**等待審閱：1件**（`審.一`f52w DSR=0.0000決定性FAIL
摘要，延續中，非本輪新增）。**下一輪任一軌接手**：從`PENDING_QUEUE.md`
「驗.一第4點續」本輪新列出的候選清單逐一確認範圍（是否曾用舊引擎/舊
量尺產出過`TRIALS_LEDGER.md`判定），確認後排入`run_detached.py submit`
繼續，翻轉一律進`AWAITING_REVIEW.md`不自行改判。完整見`REPORT.md`第
620輪心跳、`PENDING_QUEUE.md`「驗.一第4點續（剩餘16支）」條目、
`TRIALS_LEDGER.md`#382-384。

---

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

（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪已歸檔至`TW_STATE_ARCHIVE.md`，
僅保留最新3則）
