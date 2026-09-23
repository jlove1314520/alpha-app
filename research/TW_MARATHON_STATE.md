# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-23T20:3x+08:00（馬拉松第623輪，研究帽）**——取鎖乾淨
（cycle`20260923-203037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=7（尺.二/審.二/資料.一/驗.一/驗.一第4點續(16支)/驗.一第4點續
(8支)/驗.二，比round622多的4項是總司令新裁示【DSR單位錯誤修正＋f52w
改用資訊比率重審＋2008延伸】，權威`<!-- ORDER-BEGIN -->`清單排序尺.二
最優先）。`run_detached.py status`：`audit_16remaining_batch2`
（job`20260923-183404-d854`）仍`running`（累計119.3分鐘，符合預估數
小時工作，不必每輪查）——**因此本輪不得`submit`新的重度job（規則3：
一次只跑一個重度工作）**。**開工時發現重大觀察：一個帶`Claude-Session`
標籤的活躍session（非本馬拉松、非interactive視窗本身的commit署名模式）
剛在20:2x~20:28完成`尺.二`（commit`5eb1894c`）與`資料.一`（commit
`3bdf8a05`，f52w樣本延伸至2007腳本背景抓取中），且`research/data/
comparable_trial_variance.json`的mtime是20:33——**晚於本輪20:30:37
取鎖時間**，代表該session在本輪取鎖後仍持續在同一工作目錄執行程式，
`research/audit_f52w_ir_review.py`（審.二腳本）也已存在但未commit
（`git status`顯示`??`）。**[自行裁量，避免重複勞動與檔案競態]**：
判斷該session正在依序處理尺.二→審.二→資料.一（權威排序前三項），
本輪**不觸碰**`audit_f52w_ir_review.py`／`comparable_trial_variance.py`
／`f52w_2007_extension.py`任何一支，也不執行任何會寫入同一批輸出檔的
腳本，避免跟活躍session搶寫同一份`data/*.json`造成競態或重複計算浪費
運算資源。**本輪工作單位＝逐點核對`尺.二`六點是否真的全部完成**（不
是照做，是驗證另一session的宣稱）：1.`#379`已記`INVALID_BUG`（
`trial_registry.py::KNOWN_INVALID_BUG_IDS`）確認。2.`register_trial()`
已有`periods_per_year`必填+`|sharpe|>1`拒絕登記防呆確認。3.
`deflated_sharpe()`已有`var_periods_per_year`不一致raise確認（讀
`candidate_report.py`原始碼逐行核對）。4.`comparable_trial_variance.py`
已存在且已實際執行過（`data/comparable_trial_variance.json`：
`n_comparable=4<10`已附V敏感度表，數字合理）。5.重跑
`python candidate_report.py --self-test`**本輪實測仍PASS**
（`✓ self-test 全過`）。6.`dsr_reeval.py`已有`periods_per_year`檢查
+「無法計算」防呆確認，「撐住3、倒下5」誤植已在commit訊息如實記錄
更正。**六點全部確認完成**，`PENDING_QUEUE.md`「尺.二」改標`[x]`並
附核對摘要與V敏感度表數字（見該條目）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（386列，本輪純核對未新增
判定，不觸發`register_trial()`）。`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改`research/backtest/`
／`research/validation/`／`trial_registry.py`等CLAUDE.md十三節限定
清單內任何原始碼（僅讀取核對＋改`PENDING_QUEUE.md`一個條目），全程
零新增外部API呼叫（純讀既有`.json`/程式碼、跑既有自我測試）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩6條未開始**
（審.二/資料.一因活躍session正在處理暫不計入「未開始」但也未結案；
驗.一/驗.一第4點續16支/8支/驗.二皆排在尺.二之後，依權威清單本輪不動）。
**等待審閱：1件**（`審.一`f52w DSR=0.0000決定性FAIL摘要，延續中，非
本輪新增）。**下一輪任一軌接手**：先`git status`確認活躍session是否
已完成`審.二`/`資料.一`並commit（若已commit，`audit_f52w_ir_review.py`
會從`??`變成已追蹤，`comparable_trial_variance.json`等資料檔內容可
直接引用不必重算）；若仍在跑，比照本輪做法避免搶寫；`audit_16remaining_
batch2`job預估數小時，收成後接續投遞`weinstein_alpha_gate.py`(#60)
重算（round622標記待辦，本輪因「一次只跑一個重度工作」規則仍未投遞）；
`驗.二`第二部分（開盤到收盤重跑spillover_overlay_v1）需先設計新腳本，
規模較大（9關全跑），評估後排入下一次有空的重度工作槽位。完整見
`REPORT.md`第623輪心跳、`PENDING_QUEUE.md`「尺.二」條目、commit待補。

---
**最後更新：2026-09-23T19:4x+08:00（馬拉松第622輪，研究帽）**——取鎖乾淨
（cycle`20260923-183037`，上一輪已於開工前結束reason=OK）。開工先照
「交辦優先於自走」讀`PENDING_QUEUE.md`：`- [ ]`=3（驗.一/驗.一第4點續
（剩餘16支）/驗.二）。`run_detached.py status`：`audit_16remaining_
batch2`（job`20260923-183404-d854`）仍`running`（開工57.3分鐘、收工
62.5分鐘，符合預估數小時長工作，不必每輪都查）。`驗.二`明文排在21支
稽核之後，本輪不動。**本輪工作單位＝承接round621標記「留給下一輪」的
`long_only_vs_market.py::decompose_alpha_beta()`同類缺陷評估**：查證
上一輪估計的4支呼叫端（`long_only_vs_market.py`本體／`run_alpha_
decomposition.py`／`weinstein_alpha_gate.py`／`weinstein_v2_alpha_
gate.py`），`grep TRIALS_LEDGER.md`逐一比對確認**真正需要重算的只有
`weinstein_alpha_gate.py`(#60)一支**（`run_alpha_decomposition.py`0
matches純診斷工具、`weinstein_v2_alpha_gate.py`0 matches從未登記、
`portfolio_backtest.py`(v1)不呼叫此函式），blast radius比原估計小
很多。**[自行裁量，判定為bug修復非新架構決策，比照round621
`run_value_board_v2_pit_backtest.py`同一precedent]**：修復
`long_only_vs_market.py`——`capm_beta_vs_market()`／
`decompose_alpha_beta()`改呼叫`portfolio_backtest_v2.
alpha_significance()`（0050含息總報酬benchmark+Newey-West HAC標準誤
+Dimson beta），取代原本各自複製的簡單OLS(np.polyfit)+TAIEX價格指數
公式；`run_period()`的`mkt_total_ret`同步改用`buy_and_hold_index_
pct(benchmark=0050_total_return)`，修正舊版beta/alpha跟
excess_vs_market用兩把不同尺的內部不一致。**已知簡化未變且如實記錄**：
純化alpha報酬序列時仍只用單一beta係數乘「當期」大盤報酬扣除，未把
Dimson三個落後項分別扣除，本輪只修正beta估計方法與benchmark，未重新
設計純化方法論本身。**自我測試**：合成0050完全追蹤equity_curve餵入
`decompose_alpha_beta()`，得到beta=1.0000、alpha_ann_pct≈0.0000%
（誤差量級1e-12，浮點精度內）、beta_contribution_pct≈
total_return_pct（934.29%對934.29%），驗證修正後函式行為正確。
`weinstein_alpha_gate.py`／`run_alpha_decomposition.py` import驗證
皆正常（僅import未執行）。`git status`確認本輪只修改
`research/long_only_vs_market.py`一個檔案，未觸碰凍結區或CLAUDE.md
十三節限定的核心研究檔案（此檔不在`research/backtest/`／
`research/validation/`等限定清單內，馬拉松軌可修改）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（386列，本輪未新增判定，純程式碼修復）。`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。**同時補記round621
遺漏的心跳**（發現原執行個體完成commit`6dafadcc`但未寫入`REPORT.md`
／未更新`MARATHON_STATE.md`計數器，已於本輪一併補齊，避免下一個無
記憶執行個體看不到那輪實際發生過什麼）。**佇列深度檢查**：`- [ ]`=3
低於`MIN_QUEUE_DEPTH=12`，**[自行裁量]本輪不重掃三個備援來源**——
round617今日稍早已完整重掃並誠實結論「補不出新候選」（`常備backlog`
區塊記錄在案），本輪之後情況未變（無新FAIL/PASS結案釋出新議題），
重複同一份exhaustive grep不產生新資訊，屬於預算的無效消耗，留給
下一輪：若`驗.一第4點續`/`驗.二`都結案後佇列見底才需要重新掃描。
**交辦佇列還剩2條未開始**（`驗.一第4點續`因job running中不算「未
開始」但也未結案；`驗.二`明文排在21支之後）。**等待審閱：1件**
（`審.一`f52w DSR=0.0000決定性FAIL摘要，延續中，非本輪新增）。
**下一輪任一軌接手**：`run_detached.py status`收成`20260923-183404-
d854`——預估要跑數小時，若仍`running`不必每輪都查，可先投遞
`weinstein_alpha_gate.py`(#60)重算job（N=200配對隨機控制組×TRAIN/VAL
兩期，重度工作，本輪因batch2佔用「一次只跑一個重度工作」名額未投遞）；
若batch2`finished`，優先收成該job並對照`TRIALS_LEDGER.md`#93/#290/
#94/#291。完整見`REPORT.md`第622輪心跳、`PENDING_QUEUE.md`「驗.一第
4點續」條目、commit`ea4ea60a`。

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

（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪已歸檔至
`TW_STATE_ARCHIVE.md`，僅保留最新3則）
