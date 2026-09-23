# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-24T07:3x+08:00（馬拉松第638輪，研究帽）**——取鎖乾淨
（cycle`20260924-073037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（僅`閘門.一`標`- [!]`），逐一核對`- [!]`阻塞項開頭標記皆未到
解除時間。**佇列深度自檢**：`- [ ]`=0（<12下限），依`CLAUDE.md`十四節
【凍結.二】本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：US
round637=09-24 06:3x／FUT round636=09-24 05:3x／**TW round635=09-24
04:3x（最舊）**——依round637建議與輪替選TW。**核心查證**：`data/rate_
limit_state.json`顯示FinMind於2026-09-24T00:53:56 UTC**再次**命中402
（`blocked_at`），`blocked_until`=1790211236.62（換算台北
2026-09-24T08:53:56），本輪07:31查詢時**仍BLOCKED，約差83分鐘**——這是
一次**新**的封鎖（跟round637記錄的06:37:44台北解除時刻不同），代表額度
確實曾短暫解除過。**證據**：`f52w_2007_extension_checkpoint.json`確認
`fetched_ids`從round637記錄的222推進到**274**（`failed_ids`由41增至52），
證實額度解除後（06:37~06:53台北，約16分鐘窗口）有行程續抓52檔後才再次
撞額度；`research/.f52w_2007_extension.lock`目前**不存在**，確認該行程
已結束（非仍在跑），現在單純是被FinMind硬性擋住。`run_detached.py
status`：`running=0`（160筆歷史，無job待收成）。**逐一核對`凍結.二`允許
的四類工作現況（同round634~637方法論，本輪對TW軌重新確認）**：稽核
重跑（驗.一第4點續剩餘8支）已grep確認標`[x]`完成並登記#387-393；資料
抓取被FinMind額度硬性擋住（見上，還需約83分鐘）；工具修正（修.三額度
錯誤bug＋並發鎖）已由互動視窗CC完成並commit（`a80b27f7`，本輪`git
status`確認`research/factors.py`無未commit修改）；驗.二開盤到收盤重跑
已grep確認標`[x]`完成並登記`TRIALS_LEDGER.md`#394（FAIL）。
`AWAITING_REVIEW.md`「等待中」表格確認**0件**（與round637一致）。
**其餘被動等待項覆核**：`#50`容量受限小型股tick累積`ls research/data/
ticks/*.parquet`實測**13/20**（較round625持平，無新交易日新增，依
2026-09-15裁示不重複回報細節）；`金流一.4`法人歷史仍15個交易日、
20日視窗還需5個交易日，未變。**本輪誠實結論**：四類允許工作皆已完成
或被外部額度阻擋，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、
不觸碰`凍結.二`禁止的新alpha試驗。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增判定，
不觸發`register_trial()`）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改`research/backtest/`／`research/validation/`
／`trial_registry.py`等`CLAUDE.md`十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**（僅`閘門.一`標`- [!]`，
BLOCKED於續抓完成）。**等待審閱：0件**。**下一輪任一軌接手**：FinMind
額度預計08:53台北解除，解除後才可繼續f52w/dividend 2007-2014延伸抓取
（目前274/300，還差26檔，`failed_ids`52筆需一併檢視是否為永久性失敗）；
`閘門.一`待續抓完成後才可執行五項資料品質檢查；`#50`持續被動等待tick
累積至20（13/20）；依輪替下一輪建議選US軌（round637=09-24 06:3x，
三軌中最舊）。完整見`REPORT.md`第638輪心跳、`PENDING_QUEUE.md`「閘門.
一」條目、`data/f52w_2007_extension_checkpoint.json`。

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


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪、
第621輪、第622輪、第623輪、第624輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
