# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-24T04:3x+08:00（馬拉松第635輪，研究帽）**——取鎖乾淨
（cycle`20260924-043037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（僅`閘門.一`標`- [!]`），逐一核對開頭標記皆未到解除時間，僅
`資料.一`與`閘門.一`的解除條件（FinMind額度封鎖`blocked_until`）已到期
（見下）。**佇列深度自檢**：`- [ ]`=0（<12下限），依`CLAUDE.md`十四節
【凍結.二】本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：TW
round632=09-24 01:3x（最舊）／FUT round633=09-24 02:3x／US
round634=09-24 03:3x——依輪替選TW。**核心查證**：`data/rate_limit_
state.json`顯示FinMind`blocked_until`=1790194899.09（換算台北
2026-09-24T04:21:39），本輪04:31取鎖時**額度已解除約10分鐘**——但
`research/.f52w_2007_extension.lock`（未追蹤檔）內容為`163704|
1790194942.50|unknown`，`Get-Process -Id 163704`確認**該PID是活躍的
python行程**（啟動時間04:22:21，剛好緊接額度解除時刻），判定另一
排程（依`閘門.一`條目文字為hypothesis_queue軌）已搶先接手續抓，
`research/data/f52w_2007_extension_checkpoint.json`確認`fetched_ids`
已從round633記錄的169**推進到199**（`failed_ids`=35），證實該行程
正在正常運作中。**[自行裁量，比照round613/623/625避讓先例]**：本輪
不重複執行`f52w_2007_extension.py`（會撞檔案鎖且浪費FinMind額度），
避免跟活躍行程搶佔同一份checkpoint。**逐一核對`凍結.二`允許的四類
工作現況**：稽核重跑（驗.一第4點續剩餘8支）已於round624完成並登記
#387-393；資料抓取正被上述活躍行程處理中（非本輪可重複執行）；工具
修正（修.三額度錯誤bug＋並發鎖）已由互動視窗CC完成並commit
（`a80b27f7`，`git log`/`git status`確認`research/factors.py`無未
commit修改）；驗.二開盤到收盤重跑已於round625~633期間完成並登記
`TRIALS_LEDGER.md`#394（FAIL）。`AWAITING_REVIEW.md`「等待中」表格
確認**0件**（與round634一致）。**本輪誠實結論**：四類允許工作皆已
完成或正被其他活躍行程處理，`凍結.二`禁止開新alpha試驗、佇列深度
補件規則暫停，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之
一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不
搶寫其他行程正在使用的檔案。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增
判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前
皆確認`False`。`run_detached.py status`：`running=0`（160筆歷史，
無job待收成）。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改`research/backtest/`／`research/validation/`／
`trial_registry.py`等CLAUDE.md十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀
既有`.json`/`.md`帳本檔案、`git status`/`git log`、`Get-Process`、
`run_detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未
開始**（僅`閘門.一`標`- [!]`，BLOCKED於續抓完成，非可獨立推進項）。
**等待審閱：0件**。**下一輪任一軌接手**：續抓199/300檔（活躍行程
持續中，預計還需1-2輪、約2-4小時補齊剩餘~101檔，屆時`閘門.一`才可
執行五項資料品質檢查）；`#50`持續被動等待tick累積至20；依輪替下一輪
建議選FUT軌（round633=09-24 02:3x，三軌中最舊）。完整見`REPORT.md`
第635輪心跳、`data/f52w_2007_extension_checkpoint.json`。

---
**最後更新：2026-09-24T01:3x+08:00（馬拉松第632輪，研究帽）**——取鎖乾淨
（cycle`20260924-013037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=5（轉向.一續/定案.一/修.三/驗.四/閘門.一，總司令新裁示【候選名單
定案＋抓取程式修正＋開考前資料品質閘門】）。**完成定案.一**：
`register_trial()`寫入`TRIALS_LEDGER.md`兩筆事前登記列——**#396**
`f52w_high_portfolio_v1_2007_2014_prereg`、**#397**
`dividend_yield_portfolio_v1_2007_2014_prereg`（verdict=未結案，尚未執行
回測），載明期間2007-01-01~2014-12-31、事前綁定只跑一次不得回頭改參數、
主判準為2007-2014全段、2007-2009與2010-2014另分段報告但不作主判準、
Bonferroni以候選數2計算單尾α=0.025、測試前置條件（修.三→驗.四→續抓168檔
→閘門.一全部通過才准執行）。同步核對**轉向.一續**已被本次裁示解除
BLOCKED（value_board_v2不列入、最終候選鎖定二個），改標`[x]`並附出處。
**發現`research/factors.py`處於未commit的中途編輯狀態**（`git status`
顯示`M`，`ls -la`mtime距本輪開工僅約14秒，內容顯示`prepare_factors()`
內15處`except RuntimeError`已新增`if _is_quota_error(e): raise`與
`_record_factor_warning(warnings_out, ...)`呼叫，但`_is_quota_error`／
`_record_factor_warning`兩函式定義與`warnings_out`參數/變數本身尚未
出現在檔案任何位置——判定另一活躍互動視窗CC session正在同步實作`修.三`
額度錯誤防呆，屬合理的中途未完成狀態，非既有bug）。**[自行裁量，比照
round613/623/625避讓先例]**：本輪不觸碰`research/factors.py`與
`research/f52w_2007_extension.py`，避免搶寫或提交半成品程式碼（若此刻
強行補完，兩個session對「防呆訊息文字/checkpoint欄位命名」等細節的
選擇可能不一致，事後要merge反而更麻煩）；`修.三`/`驗.四`/`閘門.一`
三項維持`- [ ]`，留給下一輪核對該session是否已commit。**重新查證
資料.一**：`data/rate_limit_state.json`顯示FinMind於16:05:32UTC再次
命中402（跟round625記錄的01:00那次blocked_until不同，是新一次觸發），
`blocked_until`延到2026-09-24T02:05:32台北，本輪01:3x查詢時仍BLOCKED，
約差32分鐘解除，維持`- [!]`。`run_detached.py status`：`running=0`
（160筆歷史，無job待收成）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪#396/#397兩筆
新增）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆
確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／`trial_registry.py`
等CLAUDE.md十三節限定清單內任何原始碼（僅呼叫`register_trial()`登記＋
改`PENDING_QUEUE.md`/`MARATHON_STATE.md`/`TW_MARATHON_STATE.md`三個
狀態檔），全程零新增外部API呼叫。`PROGRESS_HEARTBEAT.jsonl`已append
本輪一行。**交辦佇列還剩3條未開始**（修.三/驗.四/閘門.一，後兩者BLOCKED
於修.三完成與續抓進度）。**等待審閱：0件**。**下一輪任一軌接手**：
先`git status`確認`research/factors.py`是否已由該活躍session完成並
commit——若已commit，核對`_is_quota_error()`/`_record_factor_warning()`
定義與`修.三`裁示原文兩點是否皆已落實（額度錯誤上拋+checkpoint改每檔
存一次+並發檔案鎖），完成後接續`驗.四`（已抓132檔資料品質稽核）；若
仍未commit且mtime持續變動，繼續避讓改做其他交辦或FUT/US輪替；`資料.一`
預計02:05:32台北解除。完整見`REPORT.md`第632輪心跳、`PENDING_QUEUE.md`
「定案.一」/「轉向.一續」條目、`TRIALS_LEDGER.md`#396/#397。

---
**最後更新：2026-09-23T21:3x+08:00（馬拉松第624輪，研究帽）**——取鎖乾淨
（cycle`20260923-213037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=4（驗.一/驗.一第4點續(剩餘16支)/驗.一第4點續(剩餘8支)/驗.二；
`尺.二`round623已核對完成標`[x]`，`審.二`已完成標`[x]`，`資料.一`
BLOCKED預計22:44解除，未到解除時間）。`run_detached.py status`：
**`audit_16remaining_batch2`（job`20260923-183404-d854`）已`finished`
（exit=0，耗時176.1分鐘）**——「一次只跑一個重度工作」名額釋出。
**本輪工作單位＝收成batch2並登記，發現並更正一個重複登記錯誤，投遞
最後1支重算**：讀log對照`TRIALS_LEDGER.md`#93/#94/#290/#291，
`run_value_board_v2_pit_backtest`（#93baseline，App端`data/
strategies.json`標記value_board_v2『回測未通過』）**VAL alpha顯著性
翻轉**（p=0.1441→0.0470），依裁示「翻轉一律進AWAITING_REVIEW不自行
改判」登記`TRIALS_LEDGER.md`#390（未結案）並寫入`AWAITING_REVIEW.md`；
`piotroski_fscore_gate_v1`（#94/#291）gate本身**0翻轉維持FAIL**（本次
FinMind中途402封鎖，fscore僅311/486檔覆蓋，如實記錄限制），登記#391。
**[自行裁量，事後發現並更正的錯誤]**：登記batch1三支
（margin_utilization/odd_lot_imbalance/short_sale_utilization）前未先
grep核對，重複登記了round620已完成的同一批分析（原#382/#383/#384）
為新編號#387/#388/#389——append-only不回頭改判定欄，已在`TRIALS_
LEDGER.md`#387前方補DUPLICATE更正說明＋`selection_bias_ledger.py`
`KNOWN_DUPLICATE_IDS`加入387/388/389排除出有效N（比照既有#335-337/
#379同一套處理）。`short_sale_utilization`（#389/#384）內容本身是
PASS(第2關,非最終結案)→FAIL(第2/7關)方向翻轉，**[自行裁量]**依
CLAUDE.md最高投資原則「誠實判不及格」精神，往更嚴格方向的翻轉直接
登記FAIL不進AWAITING_REVIEW暫停（保護機制防的是自行升級為PASS的
風險，不是自行降級為FAIL的風險）。`weinstein_alpha_gate.py`(#60)為
11支範圍最後1支，batch2收成後名額釋出，本輪投遞job
`20260923-213506-0f76`（timeout 240分鐘，`--expect research/data/
weinstein_alpha_gate_summary.csv`）。**驗.一第4點續11支範圍現況：
10/11已完成，僅剩weinstein_alpha_gate等待job收成**。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（393列，本輪#387-391五筆新增登記）。`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改`research/backtest/`
／`research/validation/`／`trial_registry.py`等CLAUDE.md十三節限定
清單內任何原始碼（僅呼叫`register_trial()`登記＋讀log＋投遞job＋
改`selection_bias_ledger.py`的常數集合，該檔不在限定清單內）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未
開始**（`驗.一第4點續(剩餘8支)`因尺.二已完成理論上可續跑，但本輪
未觸碰；`驗.二`第二部分）。**等待審閱：2件**（`審.一`f52w DSR摘要，
延續中；本輪新增`value_board_v2`VAL alpha翻轉#390）。**下一輪任一
軌接手**：`run_detached.py status`收成`20260923-213506-0f76`（預估
數小時，不必每輪都查）；收成後對照`TRIALS_LEDGER.md`#60舊判定
（FAIL，VAL純alpha百分位28.5），翻轉一律進`AWAITING_REVIEW.md`不
自行改判；完成後「驗.一第4點續11支範圍」可全數結案，接續處理
`驗.一第4點續（剩餘8支）`與`驗.二`第二部分；**下一輪開工先grep
`TRIALS_LEDGER.md`核對候選是否已有登記再呼叫`register_trial()`，
避免重蹈本輪重複登記的覆轍**。完整見`REPORT.md`第624輪心跳、
`TRIALS_LEDGER.md`#387-391、`AWAITING_REVIEW.md`。


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪、
第621輪、第622輪、第623輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
