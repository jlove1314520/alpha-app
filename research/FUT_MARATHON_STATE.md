# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---

**最後更新：2026-09-30T10:0x+08:00（馬拉松第684輪，維運帽）**——取鎖乾淨
（cycle`20260930-100037`）。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`
=0（round683記錄的4條`先.三`子任務已由互動視窗完成並移入
`AWAITING_REVIEW.md`「等待中」表，本輪核對非馬拉松動作）；`grep -c "^- \[!\]"`
=13（較round683的15減2：`先.二-三b`／`先.三-二`FinMind 402封鎖已於09:25
解除，實測`data/rate_limit_state.json`的`last_request_at`已晚於
`blocked_until`，兩條已由互動視窗從`- [!]`清單移除，非新增交辦）。逐一
核對13條`- [!]`阻塞項：`金流一.4`實測`data/institutional_history.json`
原始21筆，經`_solid_dates()`過濾後仍**17個交易日**（20260901~20260929，
09-30當日資料尚未反映在此檔），20日視窗仍差3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積實測仍**14/20**，未解除；`本地AI摘要
(Breeze-7B)`四選一仍待總司令裁示，未解除；其餘均等待總司令核准或親自
操作、或未到解除時間（`紙.一`需10/1，本輪查詢仍09-30）。`grep -c "凍結.
二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告解除，
凍結.二仍生效。三軌時間戳：FUT round681=09-30 07:0x（最舊，本輪選定）／
TW round682=09-30 08:0x／US round683=09-30 09:0x。**逐一核對凍結.二允許
的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取
（資料.一已完成300/300，`先.三`為互動視窗自行裁量的獨立工作，已結案待
審，不代做）；工具修正已由互動視窗commit；`git status --short`確認
`research/backtest/`／`research/validation/`／`research/adjust.py`／
`research/pit.py`／`research/trial_registry.py`等十三節限定清單內檔案
無殘留未commit編輯（輸出為空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check` exit=0
PASS（406列，本輪未新增判定）。`AWAITING_REVIEW.md`「等待中（目前：
27件）」，逐行核對（`sed -n '22,49p'`實測27筆資料列）與表頭一致，較
round683的26件+1（`先.三`結案新增一列）。**本輪誠實結論**：交辦佇列0條
`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對
均未到解除時間；FUT軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之
一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新
alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔），全程零新增外部API呼叫（純讀
既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`）。`PROGRESS_HEARTBEAT.jsonl`已
append本輪一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：27件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選TW軌（round682=09-30 08:0x，三軌中最舊）；開工前先重新
檢查`- [ ]`有無新交辦、`金流一.4`還需3個交易日、`外部一改.2`tick累積
14/20還差6日、`本地AI摘要(Breeze-7B)`四選一是否已裁示；凍結.二在總
司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第684輪
心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T13:0x+08:00（馬拉松第687輪，維運帽）**——取鎖乾淨
（cycle`20260930-130037`）。三軌時間戳：FUT round684=09-30 10:0x（最舊，
本輪選定）／TW round685=09-30 11:0x／US round686=09-30 12:0x，依輪替
選FUT。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始
交辦項）；`grep -c "^- \[!\]"`=13（與round684~686一致）。逐一核對13條
`- [!]`阻塞項：`金流一.4`實測`data/institutional_history.json`原始
`dates`陣列已21筆、最後日期`20260929`，經`_solid_dates()`過濾仍
**17個交易日**（20260901~20260929），20日視窗仍差3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積`ls research/data/ticks/*.parquet`
實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`四選一仍待總司令裁示，
屬白名單第6條法遵疑慮，未解除；`紙.一`需2026-10第一個交易日，本輪查詢
時仍09-30，未到；其餘9條逐一核對，均為等總司令/Cowork裁示或其他外部
條件，皆未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行
核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**逐一核對凍結.二
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；
資料抓取（`資料.一`已完成300/300）；工具修正已由互動視窗commit；
`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定清單內檔案無殘留未commit編輯）。FUT軌本身`FUT_LEADS.md`/
`STRATEGY_GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：27件）」，`grep -c
"^| "`=38列（含表頭），與round684~686一致，本輪未變動。**本輪誠實
結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；
13條`- [!]`逐一核對均未到解除時間；FUT軌本身查無可推進的新工作單位——
依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不
觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留
項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），
全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦
佇列還剩0條`- [ ]`未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選TW軌
（round685=09-30 11:0x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新
交辦、`金流一.4`還需3個交易日、`外部一改.2`tick累積14/20還差6日、
`本地AI摘要(Breeze-7B)`四選一是否已裁示、`紙.一`是否已到2026-10第一
個交易日。凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整
見`REPORT.md`第687輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要
(Breeze-7B)」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T16:0x+08:00（馬拉松第690輪，維運帽）**——取鎖乾淨
（cycle`20260930-160037`）。三軌時間戳：FUT round687=09-30 13:0x（最舊，
本輪選定）／TW round688=09-30 14:0x／US round689=09-30 15:0x，依輪替
選FUT。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始
交辦項，與round685~689持平）；`grep -c "^- \[!\]"`=13（與round685~689
持平）。逐一核對13條`- [!]`阻塞項：`data/sector_flow.json`的
`meta.trading_days_available`仍**17**、`windows_missing_days.20`仍
**3**，20日視窗仍差3個交易日，未解除；`外部一改.2`／`研究.c`共用tick
累積`ls research/data/ticks/*.parquet`實測**15/20**（較round688持平），
仍差5日，未解除；`本地AI摘要(Breeze-7B)`四選一仍待總司令裁示，屬白
名單第6條法遵疑慮，未解除；`稽核.三B`已於先前輪次三類全數完成並標
`[x]`，非現存`- [!]`項目；其餘9條均等總司令/Cowork裁示或其他外部
條件（`紙.一`需2026-10-01，本輪查詢仍09-30尚未到），皆未到解除時間。
`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**逐一核對凍結.二允許的四類工作現況**：
稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已
完成300/300）；工具修正已由互動視窗commit；`git status --short --
research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
exit=0 PASS（406列，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：27件）」，`grep -c "^| "`=38列
（含表頭），與round685~689一致，本輪未變動。**本輪誠實結論**：交辦
佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`
逐一核對均未到解除時間；FUT軌本身查無可推進的新工作單位——依
`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不
觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗
保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔），全程零新增
外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`holdout.py`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選TW軌（round688=09-30 14:0x，
三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、`金流一.4`還需3個
交易日、`外部一改.2`tick累積15/20還差5日、`本地AI摘要(Breeze-7B)`
四選一是否已裁示、`紙.一`是否已到2026-10-01（明日）。凍結.二在總
司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第690輪
心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。
