# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-30T03:0x+08:00（馬拉松第677輪，維運帽）**——取鎖乾淨
（cycle`20260930-030037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項）；`grep -c "^- \[!\]"`=13條，較
round674~676持平。逐一核對13條`- [!]`阻塞項是否解除：`金流一.4`（讀
`PENDING_QUEUE.md`由`build_sector_flow.py::_solid_dates()`自動維護的
倒數行，非raw陣列長度）仍**17個交易日（20260901~20260929）**，20日視窗
還需3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積`ls
research/data/ticks/*.parquet`實測仍**14/20**，未解除；`本地AI摘要
(Breeze-7B)`——(a)/(b)/(c)/(d)資料來源裁示分支仍待總司令四選一，屬白
名單第6條法遵疑慮，未解除；其餘10條逐一核對開頭標記，均為等總司令/
Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個
交易日，本輪查詢仍09-30，尚未到）。**佇列深度自檢**：`- [ ]`=0（<12
下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c "凍結.二解除"
PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告解除），本
階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：US round674=09-29
23:0x（最舊，本輪選定）／FUT round675=09-30 01:0x／TW round676=09-30
02:0x。**逐一核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑
（含`驗.二`、`驗.二續`、`驗.二第二部分`）先前輪次已全部完成並標
`[x]`；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由
互動視窗commit；`git status --short -- research/backtest/ research/
validation/ research/adjust.py research/pit.py research/trial_
registry.py`輸出為空（十三節限定清單內檔案無殘留未commit編輯）。
**特別複核`CALIBRATION_PROBE.md`指定「US軌#47/#52同理各自重跑」這項
操作指令的現況**（本輪主動追查，非例行重複）：`grep`
`TRIALS_LEDGER.md`確認**兩者皆已於2026-09-04完成並登記**——#47
（大型股tier）用`us_factor_ic_cached_universe.py`201檔全樣本重跑，
percentile翻盤為**100.0**（CHEAP_PASS），但死因是#41的1b深挖（策略
構造層beta非市場中性），不是cheap-gate檢定力問題，`f_us_low_vol`家族
整體判定維持**FAIL不變**（見`TRIALS_LEDGER.md`第572行備註，避免未來
誤讀成完全平反）；#52（中型股tier）本身cheap gate早已CHEAP_PASS，死因
是1b深挖TRAIN期輸給隨機控制組（`TRIALS_LEDGER.md`#68），不是樣本太小
問題，校準探針的「換大樣本重跑cheap gate」修正手段對它不對症，已從
「待重跑」清單移出（第573行）——**這項任務並非本輪新完成，是確認早
已結案，US軌無殘留的校準探針待辦事項**。US軌本身`US_LEADS.md`/
`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，`#49`/`#51`/
`#52`已FAIL結案、`#82`依`驗.七`裁示暫停，無對應結構性優勢候選可開新
方向（`凍結.二`期間本來就不得開新alpha試驗）。`run_detached.py
status`：`running=0`（162筆歷史，無job待收成）。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純查證
未新增判定）。`validation/holdout.py::is_holdout_consumed()`讀取為
`True`（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表頭
「目前：25件」，逐行核對與25筆資料列一致，本輪未變動。**本輪誠實
結論**：交辦佇列無`- [ ]`項目；凍結.二允許的四類工作皆已完成或無新
內容；13條`- [!]`逐一核對均未到解除時間；主動複核`CALIBRATION_
PROBE.md`唯一指名給US軌的操作指令（#47/#52重跑）確認早已結案、無殘留
——US軌本身查無可推進的新工作單位，依`CLAUDE.md`「零之一」白名單第7條
精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶
碰十三節限定檔案、不變更正式交易連線。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼
（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫
（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_
detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：25件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round675=09-30 01:0x，
三軌中最舊）；開工前先重新檢查`金流一.4`（還需3個交易日）與tick累積
（14/20）；凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整
見`REPORT.md`第677輪心跳、`PENDING_QUEUE.md`「金流一.4」條目、
`research/AWAITING_REVIEW.md`。
---
**最後更新：2026-09-29T23:0x+08:00（馬拉松第674輪，維運帽）**——取鎖乾淨
（cycle`20260929-230037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項）；`grep -c "^- \[!\]"`=13條（較
round671~673的14條**−1**：`驗.九`已由互動視窗於22:50完成，見
`PENDING_QUEUE.md`「驗.九完成報告」，不再列入阻塞清單；同輪互動視窗
另完成`評.B`計分榜方案B，兩項皆已寫入`AWAITING_REVIEW.md`「等待中」
表格，表頭由19→**21件**）。逐一核對剩餘13條`- [!]`阻塞項是否解除：
`data/institutional_history.json`確認`dates`陣列raw長度20（date_range
20260826~20260924，較先前輪次查到的20260901起點更早，屬morning既有
批次09:15產生，非本輪新資料）——`[自行裁量]`**未直接採信raw長度**，
改讀`scripts/build_sector_flow.py`的`_solid_dates()`過濾邏輯與其自動
改寫的`PENDING_QUEUE.md`「金流一.4」倒數行：仍為**16個solid交易日
（20260901~20260924）**，因20260826~20260831這幾天股票覆蓋率過薄被
過濾，20日視窗仍差4個交易日，**未解除**（raw陣列長度不能直接當solid
天數用，這是本輪查證後的教訓，供下一輪參考避免誤判）；`外部一改.2`／
`研究.c`共用的tick累積`ls research/data/ticks/*.parquet`實測仍
**14/20**，未解除；其餘11條逐一核對開頭標記，均為等總司令/Cowork裁示
或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效，本階段暫停佇列深度補件，不重掃備援來源。
三軌時間戳：US round671=09-29 20:0x（最舊）／TW round672=09-29 21:0x／
FUT round673=09-29 22:0x——依輪替選US。**逐一核對`凍結.二`允許的四類
工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取
（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗commit；
`git status --short`確認`research/backtest/`／`research/validation/`／
`research/adjust.py`／`research/pit.py`／`research/trial_registry.py`
等十三節限定清單內檔案無殘留未commit編輯（輸出為空）。US軌本身
`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，
`#49`/`#51`/`#52`已FAIL結案、`#82`依`驗.七`裁示暫停，無對應結構性
優勢候選可開新方向（`凍結.二`期間本來就不得開新alpha試驗）。
`run_detached.py status`：`running=0`（162筆歷史，無job待收成）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（406列，本輪純查證未新增判定）。`validation/holdout.py::is_holdout_
consumed()`讀取為`True`（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`
「等待中」表頭「目前：21件」，逐行核對與21筆資料列一致（較round671的
19件+2，來自`驗.九`與`評.B`兩項互動視窗完成待審，非本輪新增動作）。
**本輪誠實結論**：`驗.九`已由互動視窗完成解除阻塞（改列等待審閱，非
本輪動作）；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`
逐一核對均未到解除時間（含本輪釐清raw天數20≠solid天數16的判讀陷阱）；
US軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之一」白名單第7條
精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、
不搶碰十三節限定檔案、不變更正式交易連線。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼
（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫
（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_
detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：21件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選TW軌（round672=09-29 21:0x，
三軌中最舊）；開工前先重新檢查`金流一.4`（solid天數是否已回升至20，
用`build_sector_flow.py`自動倒數行判讀，不要直接讀`dates`陣列raw長度）
與tick累積（14/20）；凍結.二在總司令/Cowork明確寫「凍結.二解除」前
不解除。完整見`REPORT.md`第674輪心跳、`PENDING_QUEUE.md`「驗.九完成
報告」、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T20:0x+08:00（馬拉松第671輪，維運帽）**——取鎖乾淨
（cycle`20260929-200037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=14條（與
round669/670一致）。逐一核對14條`- [!]`阻塞項是否解除：`驗.九`兩個
retry條件本輪重新查證——FinMind額度`blocked_until`=2026-09-29T18:24:16
+08:00早已過（本輪查詢20:0x）；`Get-CimInstance Win32_Process`實測
`audit_v9_fetch_missing.py --phase crosscheck`（PID131264，18:26:16
啟動）**仍持續執行中**（已跑約1小時35分），`data/rate_limit_state.json`
的`last_request_at`=1790683297.5（本輪查詢時間點附近），確認DevQueue
正在主動使用FinMind額度——比照round667~670對`驗.七`/`驗.八`/`驗.九`
的既有判斷（時間吻合＝他人session正在做，避免插手覆寫競爭），本輪
**不觸碰`驗.九`**、不啟動任何新的`audit_v9`相關行程；記憶體本輪實測
**2.82GB**（<3GB門檻，較round670的2.59GB略回升但仍未解除）。核對其餘
13條：`data/institutional_history.json`確認`dates`陣列仍20筆、最後
日期`20260924`，solid交易日數維持**16日**，今日09-29（週二）20:0x
查詢（收盤後約6.5小時，法人資料排程尚未入庫本日新交易日），20日視窗
仍差4個交易日，未解除；`外部一改.2`／`研究.c`共用的tick累積`ls
research/data/ticks/*.parquet`實測仍**14/20**，未解除；其餘11條逐一
核對開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間
（`紙.一`需等2026-10第一個交易日，今日仍09月）。**佇列深度自檢**：
`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c
"凍結.二解除" PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際
宣告解除），本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：US
round668=09-29 17:0x（最舊）／TW round669=09-29 18:0x／FUT round670=
09-29 19:0x——依輪替選US。**逐一核對`凍結.二`允許的四類工作現況**：
稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`/
`閘門.一`）已完成300/300；工具修正已由互動視窗commit；`git status
--short`確認`research/backtest/`／`research/validation/`／`research/
adjust.py`／`research/pit.py`／`research/trial_registry.py`等十三節
限定清單內檔案無殘留未commit編輯（輸出為空）。US軌本身`US_LEADS.md`/
`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，`#49`/`#51`/
`#52`已FAIL結案、`#82`依`驗.七`裁示暫停，無對應結構性優勢候選可開新
方向（`凍結.二`期間本來就不得開新alpha試驗）。`run_detached.py
status`：`running=0`（162筆歷史，無job待收成，`驗.九`正在跑的行程
如上述非透過此機制啟動）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純查證未新增
判定）。`validation/holdout.py::is_holdout_consumed()`讀取為`True`
（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表頭「目前：
19件」，逐行核對30行（含表頭/分隔線）與19筆資料列一致，較round670無
變動。**本輪誠實結論**：交辦佇列無`- [ ]`項目，`驗.九`FinMind retry
條件已解除但正被DevQueue即時執行中，記憶體retry條件仍未解除，為避免
覆寫/競爭本輪選擇不插手；凍結.二允許的四類工作皆已完成或無新內容，
其餘13條`- [!]`逐一核對均未到解除時間，US軌本身查無可推進的新工作
單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊
候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、未啟動
任何與`驗.九`重疊的新行程。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改
狀態檔＋archive舊state條目＋一次PowerShell`Get-CimInstance`查詢行程
命令列），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`、`Get-CimInstance`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪
一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：19件**（與
`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替下一
輪建議選TW軌（round669=09-29 18:0x，三軌中最舊）；開工前先重新檢查
`驗.九`是否仍在DevQueue執行中、記憶體retry條件是否已回升≥3GB；凍結.二
在總司令/Cowork明確寫「凍結.二解除」前不解除；`金流一.4`還需4個交易
日；`外部一改.2`tick累積仍14/20，還差6日。完整見`REPORT.md`第671輪
心跳、`PENDING_QUEUE.md`「驗.九」條目、`research/AWAITING_REVIEW.md`。

