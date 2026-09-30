# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-30T12:0x+08:00（馬拉松第686輪，維運帽）**——取鎖乾淨
（cycle`20260930-120037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（round683記錄的`先.三`四項子任務已由互動視窗全部
完成並標`[x]`，見`PENDING_QUEUE.md`17164~17187行，本輪核對非馬拉松動作）；
`grep -c "^- \[!\]"`=13，較round683/684/685持平，逐一核對13條均未到解除
時間：`金流一.4`讀`build_sector_flow.py::_solid_dates()`自動維護的倒數行
仍**17個交易日（20260901~20260929）**，20日視窗還需3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積`ls research/data/ticks/*.parquet`
實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源
裁示分支仍待總司令選一個，屬白名單第6條法遵疑慮，未解除；`data/rate_
limit_state.json`的FinMind`blocked_until`=09:25:48、`last_request_at`
=09:37:35，本輪查詢12:01，**封鎖早已解除**（round684已先確認並移除
`先.二-三b`／`先.三-二`兩條，非本輪新發現，僅重複驗證一致）；其餘10條
逐一核對開頭標記，均為等總司令/Cowork裁示或其他外部條件（`紙.一`需
2026-10第一個交易日，本輪查詢仍09-30，尚未到）。**佇列深度自檢**：
`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c
"凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際
宣告解除），本階段暫停佇列深度補件，不重掃備援來源湊數，符合白名單
第7條。三軌時間戳：US round683=09-30 09:0x（本輪選定，三軌中最舊）／
FUT round684=09-30 10:0x／TW round685=09-30 11:0x。**逐一核對凍結.二
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；
資料抓取（`資料.一`已完成300/300，`先.三`系列為互動視窗自行裁量的獨立
工作，已結案待審，不代做）；工具修正已由互動視窗commit（`git log`最新
數筆均為排程自動更新，無互動視窗新commit待複查）；`git status --short
-- research/backtest/ research/validation/ research/adjust.py research/
pit.py research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留
未commit編輯）。US軌本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only
因子家族結案狀態未變，`CALIBRATION_PROBE.md`唯一指名給US軌的操作指令
（#47/#52重跑）先前輪次已複核確認2026-09-04早已結案、無殘留，本輪再次
核對`TRIALS_LEDGER.md`第572~573行備註仍為最終狀態，無新變化。無對應
結構性優勢候選可開新方向（凍結.二期間本來就不得開新alpha試驗）。驗證：
`run_detached.py status`running=0（162筆歷史，無job待收成）；`trial_
registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，
本輪未新增判定）；`validation/holdout.py::is_holdout_consumed()`讀取為
`True`（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：
27件）」，逐行核對（`grep -c "^| " research/AWAITING_REVIEW.md`=38列含
表頭）與round684/685一致，本輪未變動。**本輪誠實結論**：交辦佇列0條
`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對
均未到解除時間（FinMind 402封鎖已解除但這只是重複驗證round684既有結論，
不構成新工作單位）；US軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零
新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`holdout.py`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round684=09-30 10:0x，
三軌中最舊，TW round685剛更新過）；開工前先重新檢查`- [ ]`有無新交辦、
`本地AI摘要(Breeze-7B)`四選一是否已裁示、`金流一.4`是否已隨當日排程
更新走到20日視窗、`外部一改.2`tick累積14/20還差6日、`紙.一`是否已到
2026-10第一個交易日。凍結.二在總司令/Cowork明確寫「凍結.二解除」前不
解除。完整見`REPORT.md`第686輪心跳、`PENDING_QUEUE.md`「金流一.4」
「本地AI摘要(Breeze-7B)」條目、`research/AWAITING_REVIEW.md`。
---
**最後更新：2026-09-30T09:0x+08:00（馬拉松第683輪，維運帽）**——取鎖乾淨
（cycle`20260930-090037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=4（`先.三-一`／`先.三-三`／`先.三-四`／`先.三-五`，
2026-09-30總司令裁示【先.三：存活者偏誤探測＋資料補齊＋草案持股數修訂】），
四條**皆明文標「互動視窗」**；核對`git status --short`確認互動視窗正在
進行中（`research/probe_delisted_fs.py`未commit新檔案，對應`先.三-一`；
`research/diag_planb_live_check.py`已`git mv`到`research/archive/`，
對應`先.三-五`；`docs/PREREG_DRAFT_supply_tightness.md`／
`research/precheck_supply_tightness.py`／`precheck_supply_tightness_results.json`
均已修改，對應`先.三-三`草案修訂鏈）。依CLAUDE.md「三之一」交辦優先
原則，四條均非本輪可動手範圍，等同交辦佇列對馬拉松而言為0，本輪不搶碰、
不代做、不commit這些WIP檔案。`grep -c "^- \[!\]"`=15（較round680的13＋2：
新增`先.二-三b`／`先.三-二`，兩者為同一件FinMind 402封鎖，屬互動視窗
自行裁量的BLOCKED背景任務，非新增交辦）。逐一核對15條`- [!]`阻塞項：
`金流一.4`（讀`build_sector_flow.py::_solid_dates()`自動維護的倒數行）
仍**17個交易日（20260901~20260929）**，20日視窗仍差3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積`ls research/data/ticks/*.parquet`
實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`四選一仍待總司令裁示，
屬白名單第6條法遵疑慮，未解除；`先.二-三b`／`先.三-二`（FinMind 402封鎖）
實測`data/rate_limit_state.json`的`blocked_until`對應台北09:25:48，本輪
查詢09:01~09:02，**尚未到**（還差約24分鐘）；其餘10條逐一核對開頭標記，
均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`需等
2026-10第一個交易日，今日仍09-30）。`grep -c "凍結.二解除" PENDING_QUEUE.md`
=4，逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列
深度自檢**：`- [ ]`=4但全數保留給互動視窗，凍結.二期間本來就暫停馬拉松
補alpha試驗湊數，不動作。三軌時間戳：US round680=09-30 06:0x（本輪選定，
三軌中最舊）／FUT round681=09-30 07:0x／TW round682=09-30 08:0x。**逐一
核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成
並登記；資料抓取（`資料.一`已標`- [x]`完成300/300，`先.三`系列為互動
視窗自行裁量的獨立工作，不代做）；工具修正已由互動視窗commit；`git
status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定清單內檔案無殘留未commit編輯）。US軌本身`US_LEADS.md`/
`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，`CALIBRATION_
PROBE.md`唯一指名給US軌的操作指令（#47/#52重跑）先前輪次已複核確認
2026-09-04早已結案、無殘留，本輪再次核對`TRIALS_LEDGER.md`第572~573行
備註仍為最終狀態，無新變化。無對應結構性優勢候選可開新方向（凍結.二
期間本來就不得開新alpha試驗）。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：26件）」，逐行核對
與26筆資料列一致，本輪未變動。**本輪誠實結論**：交辦佇列4條`- [ ]`全部
保留給互動視窗（本輪不代做其進行中的`先.三`四項子任務，也不動其WIP
未commit檔案）；凍結.二允許的四類工作皆已完成或無新內容；15條`- [!]`
逐一核對均未到解除時間；US軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零
新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩4條`- [ ]`未開始，但均保留給互動視窗，非馬拉松漏做**。**等待審閱：
26件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：
依輪替下一輪建議選FUT軌（round681=09-30 07:0x，三軌中最舊）；開工前先
重新檢查`先.三`四項子任務是否已由互動視窗改標`- [x]`、`金流一.4`還需3個
交易日、`外部一改.2`tick累積14/20還差6日、`先.二-三b`／`先.三-二`
FinMind封鎖是否已於09:25解除；凍結.二在總司令/Cowork明確寫「凍結.二
解除」前不解除。完整見`REPORT.md`第683輪心跳、`PENDING_QUEUE.md`
「先.三」「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。


---
**最後更新：2026-09-30T15:0x+08:00（馬拉松第689輪，維運帽）**——取鎖乾淨
（cycle`20260930-150037`）。三軌時間戳：US round686=09-30 12:0x（最舊，
本輪選定）／FUT round687=09-30 13:0x／TW round688=09-30 14:0x。開工先讀
`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦項，與
round680~688持平）；`grep -c "^- \[!\]"`=13（與round683~688持平）。逐一
核對13條`- [!]`阻塞項：`金流一.4`實測`data/sector_flow.json`
`meta.trading_days_available`仍**17**、`windows_missing_days.20`仍**3**，
20日視窗仍差3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測**15/20**（較round688持平，仍差
5日），未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源裁示分支
仍待總司令選一，屬白名單第6條法遵疑慮，未解除；`data/rate_limit_
state.json`的FinMind`blocked_until`早已過期，但無現存阻塞項以此為由；
其餘9條逐一核對開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到
解除時間（`紙.一`需2026-10-01，本輪查詢時仍09-30，尚未到）。`grep -c
"凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際
宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），凍結.二
期間暫停補件，不硬湊alpha試驗候選。**逐一核對凍結.二允許的四類工作
現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`
已完成300/300）；工具修正已由互動視窗commit（`git log`最新數筆均為排程
自動更新，無互動視窗新commit待複查）；`git status --short -- research/
backtest/ research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯）。US軌本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子家族
結案狀態未變，`CALIBRATION_PROBE.md`唯一指名給US軌的操作指令（#47/#52
重跑）先前輪次已複核確認2026-09-04早已結案、無殘留，本輪再次核對
`TRIALS_LEDGER.md`第572~573行備註仍為最終狀態，無新變化。無對應結構性
優勢候選可開新方向（凍結.二期間本來就不得開新alpha試驗）。驗證：
`run_detached.py status`running=0（162筆歷史，無job待收成）；`trial_
registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，
本輪未新增判定）；`validation/holdout.py::is_holdout_consumed()`讀取為
`True`（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：
27件）」，逐行核對與27筆資料列一致，本輪未變動。**本輪誠實結論**：
交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`
逐一核對均未到解除時間；US軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零
新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`holdout.py`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round687=09-30 13:0x，
三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、`本地AI摘要
(Breeze-7B)`四選一是否已裁示、`金流一.4`還需3個交易日、`外部一改.2`
tick累積15/20還差5日、`紙.一`是否已到2026-10-01。凍結.二在總司令/
Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第689輪心跳、
`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。
