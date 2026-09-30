# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-30T08:0x+08:00（馬拉松第682輪，維運帽）**——取鎖乾淨
（cycle`20260930-080037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，與round676~681持平），
`grep -c "^- \[!\]"`=14（較round679的13＋1：新增`先.二-三b`資產負債表
缺口補抓，本身即為BLOCKED狀態，非新增交辦）。逐一核對14條`- [!]`阻塞項：
`金流一.4`實測`institutional_history.json`raw`dates`仍21筆、
`_solid_dates()`覆蓋率過濾後仍**17個交易日**（20260901~20260929，
`sector_flow.json`最後一次自動更新為2026-09-29T16:38 UTC＝台北00:38，
早於本輪查詢時間，尚未反映新一輪排程），20日視窗仍差3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積`ls research/data/ticks/*.parquet`
實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源
裁示分支仍待總司令選一，未解除；新增的`先.二-三b`解除條件為FinMind
402封鎖至約09:25，本輪查詢時間08:0x，**尚未到**（`data/rate_limit_
state.json`實測`blocked_until`對應台北09:25:48，距今約84分鐘）；其餘
9條逐一核對開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到
解除時間（`紙.一`需等2026-10第一個交易日，今日仍09-30）。`grep -c
"凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際
宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），凍結.二
期間暫停補件，不硬湊alpha試驗候選。三軌時間戳：TW round679=09-30
05:0x（本輪選定，三軌中最舊）／US round680=09-30 06:0x／FUT round681=
09-30 07:0x。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑
（`驗.二續`／`驗.二第二部分`皆`- [x]`）先前輪次已全部完成並登記；資料
抓取（`資料.一`已標`- [x]`完成300/300、`先.二-三b`為互動視窗自行裁量
的獨立背景任務，非馬拉松職權範圍不代做）；工具修正已由互動視窗commit；
`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定清單內檔案無殘留未commit編輯）。TW軌本身無清楚剩餘的全新
機制候選，且凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py
status` running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（169筆FAIL判定核對，本輪未新增
判定）；`validation/holdout.py::is_holdout_consumed()`讀取為`True`
（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：26件）」
（較round679的25件＋1：新增`先.二`合併版條目，屬互動視窗本輪工作、非
馬拉松動作），逐行核對26筆資料列一致，本輪未變動。**本輪誠實結論**：
交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容（僅有的
新進展`先.二-三b`為互動視窗自行裁量的既有背景任務，非馬拉松新開工作）；
14條`- [!]`逐一核對均未到解除時間（`金流一.4`倒數仍差3個交易日、tick
累積仍14/20、`本地AI摘要`仍待總司令四選一裁示、`先.二-三b`FinMind封鎖
還差約84分鐘）；TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程
零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條`- [ ]`未開始**。**等待審閱：26件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round680=
09-30 06:0x，三軌中最舊，FUT剛在round681更新過）；開工前先重新檢查
`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已裁示、`金流一.4`
是否已隨當日排程更新走到20日視窗、`外部一改.2`tick累積14/20還差6日、
`先.二-三b`FinMind封鎖是否已於09:25解除；凍結.二在總司令/Cowork明確
寫「凍結.二解除」前不解除。完整見`REPORT.md`第682輪心跳、
`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」「先.二-三b」
條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T05:0x+08:00（馬拉松第679輪，維運帽）**——取鎖乾淨
（cycle`20260930-050037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，round675~678記錄的`修.八`／
`價值成長榜恢復`／`先.一`三條互動視窗保留項目本輪核對仍不在`- [ ]`清單），
`grep -c "^- \[!\]"`=13（與round676~678持平）。逐一核對13條`- [!]`阻塞項：
`金流一.4`實測`data/institutional_history.json`原始`dates`陣列已從20→
**21筆**（新增20260930一天），但`_solid_dates()`過濾覆蓋率的倒數仍以
`data/sector_flow.json`最後一次自動更新（`git log`確認為2026-09-29T16:38
UTC＝台北00:38，早於本輪查詢時間）為準，尚未反映新增這一天，PENDING_QUEUE.md
6838行仍**17個交易日**、20日視窗仍差3個交易日，未解除；`外部一改.2`／
`研究.c`共用tick累積`ls research/data/ticks/*.parquet`實測仍**14/20**，
未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源裁示分支仍待總司令
選一，未解除；其餘10條逐一核對開頭標記，均為等總司令/Cowork裁示或其他
外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，今日仍09-30）。
`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限）但
凍結.二期間暫停補件，不硬湊alpha試驗候選。三軌時間戳（依「最久沒被碰」
規則，實際比對各檔案內*最新*一則的時間戳，非機械取檔案內最後一段文字）：
TW round676=09-30 02:0x（本輪選定，三軌中最舊）／US round677=09-30
03:0x／FUT round678=09-30 04:0x。**逐一核對凍結.二允許的四類工作現況**：
稽核重跑／驗.二重跑（`驗.二續`／`驗.二第二部分`皆`- [x]`）先前輪次已全部
完成並登記；資料抓取（`資料.一`已標`- [x]`完成300/300、`閘門.一`同前）；
工具修正已由互動視窗commit；`git status --short -- research/backtest/
research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯）。TW軌本身無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新
alpha試驗。驗證：`run_detached.py status` running=0（162筆歷史，無job待
收成）；`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（406列，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：25件）」，逐行核對25筆資料列一致，
本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類
工作皆已完成或無新內容；13條`- [!]`逐一核對均未到解除時間（`金流一.4`
原始日期陣列雖已多1天但尚未走完當日排程更新流程、實質倒數仍差3個交易日、
tick累積仍14/20、`本地AI摘要`仍待總司令四選一裁示）；TW軌本身查無可推進
的新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做
互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結
區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊
state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`、`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。
**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：25件**（與
`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替下一輪
建議選US軌（round677=09-30 03:0x，三軌中最舊，FUT剛在round678更新過）；
開工前先重新檢查`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已
裁示、`金流一.4`是否已隨當日排程更新走到20日視窗（原始陣列已21筆，留意
下次`sector_flow.json`自動更新後倒數可能提前解除）、`外部一改.2`tick
累積14/20還差6日；凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。
完整見`REPORT.md`第679輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI
摘要(Breeze-7B)」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T11:0x+08:00（馬拉松第685輪，維運帽）**——取鎖乾淨
（cycle`20260930-110037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，與round676~684持平，round684的
`先.三`四項子任務已由互動視窗結案並移入`AWAITING_REVIEW.md`）；
`grep -c "^- \[!\]"`=13（較round683/684持平，`先.二-三b`／`先.三-二`
FinMind封鎖已於round684確認解除並從清單移除）。逐一核對13條`- [!]`
阻塞項：`金流一.4`實測`institutional_history.json`raw`dates`仍21筆
（20260930盤中，今日尚未收盤不會有新一天資料）、`sector_flow.json`
`meta.trading_days_available`仍**17**、`windows_missing_days.20`仍**3**，
20日視窗仍差3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測仍**14/20**，未解除；`本地AI摘要
(Breeze-7B)`四選一仍待總司令裁示，屬白名單第6條法遵疑慮，未解除；其餘
10條逐一核對開頭標記（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`／`研究.c`皆
等總司令/Cowork裁示或親自操作；`紙.一`需2026-10第一個交易日，今日仍
09-30），皆未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。
三軌時間戳（比對各檔案內*最新*一則）：TW round682=09-30 08:0x（本輪
選定，三軌中最舊）／US round683=09-30 09:0x／FUT round684=09-30 10:0x。
**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已
全部完成並登記；資料抓取（`資料.一`已標`- [x]`完成300/300，`先.三`存活
者偏誤探測為互動視窗自行裁量的獨立工作，已結案待審，不代做）；工具
修正已由互動視窗commit（本輪`git log`最新5筆commit均為排程自動更新，
無互動視窗新commit）；`git status --short -- research/backtest/
research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案狀態未變，
`CALIBRATION_PROBE.md`給TW軌的操作指令（#77/#79/#91、
portfolio_multifactor_v2 300檔重跑）先前輪次已複核確認早已完成並登記，
本輪再核對`TRIALS_LEDGER.md`無新變化，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：27件）」，逐行核對
與27筆資料列一致，本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；
凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對均未到
解除時間（`金流一.4`倒數仍差3個交易日、tick累積仍14/20、`本地AI摘要`
仍待總司令四選一裁示）；TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零
新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條`- [ ]`未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round683=
09-30 09:0x，三軌中最舊，FUT剛在round684更新過）；開工前先重新檢查
`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已裁示、`金流一.4`
是否已隨當日排程更新走到20日視窗、`外部一改.2`tick累積14/20還差6日。
凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`
第685輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」
條目、`research/AWAITING_REVIEW.md`。
