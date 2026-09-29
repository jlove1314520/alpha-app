# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-30T07:0x+08:00（馬拉松第681輪，維運帽）**——取鎖乾淨
（cycle`20260930-070037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=3（`先.二-一`缺日補齊／`先.二-二`先.一草案修訂／
`先.二-三`不看報酬前置檢查），三條**皆明文標「互動視窗執行」**（承接
2026-09-30總司令裁示【先.二】，見PENDING_QUEUE.md 17164~17166行），非
馬拉松可做範圍；核對`git status`確認互動視窗已有對應WIP（`research/
backfill_cashflow_gap.py`／`research/precheck_supply_tightness.py`／
`research/precheck_supply_tightness_results.json`／`scripts/
check_0050_continuity.py`皆為未commit的新檔案，`docs/PREREG_DRAFT_
supply_tightness.md`已修改），確認互動視窗正在進行中，本輪不搶碰、不
代做、不commit這些WIP檔案。**依CLAUDE.md「三之一」交辦優先原則，三條
均非本輪可動手範圍，等同交辦佇列對馬拉松而言為0**。核對13條`- [!]`
阻塞項是否解除：`金流一.4`（讀`build_sector_flow.py::_solid_dates()`
自動維護的倒數行）仍**17個交易日（20260901~20260929）**，20日視窗仍差
3個交易日，未解除（`institutional_history.json`原始`dates`陣列已21筆
含20260930，但`sector_flow.json`最後一次自動更新為2026-09-29T16:38
UTC，早於本輪查詢時間，尚未反映；且今日09-30盤未收，本來就不會有新
一天資料）；`外部一改.2`／`研究.c`共用tick累積`ls research/data/
ticks/*.parquet`實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`四選一
仍待總司令裁示，屬白名單第6條法遵疑慮，未解除；`紙.一`需2026-10第一個
交易日，本輪查詢時仍09-30，未到；其餘9條逐一核對開頭標記，均為等總
司令/Cowork裁示或其他外部條件，皆未到解除時間。`grep -c "凍結.二解除"
PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二
（一般alpha試驗）仍生效——但注意`先.二`這個特定方向已由總司令2026-09-29
明確解凍，該方向工作正由互動視窗進行，與本輪FUT軌無關。**佇列深度
自檢**：`- [ ]`=3但全數保留給互動視窗，凍結.二期間本來就暫停馬拉松
補alpha試驗湊數，不動作。三軌時間戳：FUT round678=09-30 04:0x（最舊，
本輪選定）／TW round679=09-30 05:0x／US round680=09-30 06:0x。**逐一
核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑（`驗.二續`／
`驗.二第二部分`皆`- [x]`）先前輪次已全部完成並登記；資料抓取（`資料.一`
已標`- [x]`完成300/300）；工具修正已由互動視窗commit；`git status
--short -- research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，`CALIBRATION_PROBE.md`唯一
指名給FUT軌的操作指令（#34重跑）round678已主動複核確認早於2026-09-04
已查證不適用、無殘留，本輪再核對`TRIALS_LEDGER.md`無新變化。無清楚
剩餘的全新機制候選，且凍結.二期間本來就不得登記新alpha試驗。驗證：
`run_detached.py status` running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（406列，本輪未新增判定）；`validation/holdout.py::is_holdout_
consumed()`讀取為`True`（非本輪動作，僅讀取核對）。`AWAITING_
REVIEW.md`「等待中（目前：25件）」，逐行核對與25筆資料列一致，本輪
未變動。**本輪誠實結論**：交辦佇列3條`- [ ]`全部保留給互動視窗（本輪
不代做其進行中的`先.二`三項子任務，也不動其WIP未commit檔案）；凍結.二
允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對均未到解除時間；
FUT軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之一」白名單第7條
精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶
碰十三節限定檔案、不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅
讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀
既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`holdout.py`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩3條`- [ ]`
未開始，但均保留給互動視窗，非馬拉松漏做**。**等待審閱：25件**（與
`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替下一
輪建議選TW軌（round679=09-30 05:0x，三軌中最舊）；開工前先重新檢查
`先.二`三項子任務是否已由互動視窗改標`- [x]`或有新`- [ ]`交辦出現、
`金流一.4`還需3個交易日、`外部一改.2`tick累積14/20還差6日；凍結.二
（一般alpha試驗，`先.二`本身已解凍）在總司令/Cowork明確寫「凍結.二
解除」前不解除。完整見`REPORT.md`第681輪心跳、`PENDING_QUEUE.md`
「先.二」「金流一.4」「本地AI摘要(Breeze-7B)」條目、`research/
AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T01:0x+08:00（馬拉松第675輪，維運帽）**——取鎖乾淨
（cycle`20260930-010037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=3（`修.八`／`價值成長榜恢復`／`先.一`），三條**皆
明文標「互動視窗執行」**（例如`- [ ]` **修.八**（互動視窗執行；動
`.github/scripts/update_price_history.py`…十三節僅互動視窗…）），非馬拉松
可做範圍。核對`git log`確認其中兩條（`修.八`＝commit`e75abd3d`、`價值成長榜
恢復`＝commit`dd4bf713`）已由互動視窗完成，但checkbox尚未改`- [x]`且未進
`AWAITING_REVIEW.md`——這是互動視窗自己的收工序，馬拉松不代勞（避免搶碰
別人正在做的收尾動作）；`先.一`（`docs/PREREG_DRAFT_supply_tightness.md`）
實測`ls`確認尚未產出，仍待互動視窗執行。**依CLAUDE.md「三之一」交辦優先
原則，三條均非本輪可動手範圍，等同交辦佇列對馬拉松而言為0**。核對13條
`- [!]`阻塞項是否解除：`金流一.4`——重讀PENDING_QUEUE.md倒數行（由
`build_sector_flow.py::_solid_dates()`自動維護，非直接讀`dates`陣列raw
長度，依round674教訓）：仍為**17個交易日（20260901~20260929）**，20日
視窗還需3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積`ls
research/data/ticks/*.parquet`實測仍**14/20**，未解除；其餘11條逐一核對
開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`
需等2026-10第一個交易日，今日09-30，明日即10/1，但本輪查詢時仍09-30，
未到）。**佇列深度自檢**：`- [ ]`=3但全數保留給互動視窗，`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行
核對皆為條件敘述提及、非實際宣告解除），本階段暫停佇列深度補件，不重掃
備援來源。三軌時間戳：FUT round667=09-29 16:0x（最舊，本輪選定）／TW
round672=09-29 21:0x／US round674=09-29 23:0x——依輪替選FUT。**逐一核對
`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並
登記；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動
視窗commit；`git status --short`確認`research/backtest/`／`research/
validation/`／`research/adjust.py`／`research/pit.py`／`research/
trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯（輸出為空）。
FUT軌本身`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`回顧：個股期貨橫斷面線、
trend/oi組合嘗試、全天close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘
的全新機制候選，且凍結.二期間本來就不得登記新alpha試驗。`run_detached.py
status`：`running=0`（162筆歷史，無job待收成）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）。
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表頭「目前：22件」，逐行核對
與22筆資料列一致（較round667的19件+3，來自互動視窗`驗.九`／`評.B`／
`評.B-2`已完成待審，非本輪動作）。**本輪誠實結論**：交辦佇列的3條`- [ ]`
全部保留給互動視窗（本輪不代勞其收工序，也不搶碰其進行中的`先.一`）；
凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對均未到解除
時間（`金流一.4`仍差3個交易日、tick累積仍14/20）；FUT軌本身查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不
硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做
互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結
區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊
state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩
3條`- [ ]`未開始，但均保留給互動視窗，非馬拉松漏做**。**等待審閱：22件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替下
一輪建議選TW軌（round672=09-29 21:0x，三軌中最舊）；開工前先重新檢查
`修.八`/`價值成長榜恢復`/`先.一`是否已由互動視窗改標`- [x]`或有新`- [ ]`
交辦出現；`金流一.4`還需3個交易日；`外部一改.2`tick累積14/20，還差6日；
凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`
第675輪心跳、`PENDING_QUEUE.md`「修.八」「價值成長榜恢復」「先.一」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T04:0x+08:00（馬拉松第678輪，維運帽）**——取鎖乾淨
（cycle`20260930-040037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，round675記錄的3條`修.八`／
`價值成長榜恢復`／`先.一`已由round676確認全數不在`- [ ]`清單，交由互動
視窗自行收工）；`grep -c "^- \[!\]"`=13（與round676~677一致）。逐一核對
13條`- [!]`阻塞項：`金流一.4`（讀`build_sector_flow.py::_solid_dates()`
自動維護的倒數行）仍**17個交易日（20260901~20260929）**，20日視窗仍差
3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積`ls research/data/
ticks/*.parquet`實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`四選一
仍待總司令裁示，屬白名單第6條法遵疑慮，未解除；其餘10條均未到解除時間
（`紙.一`需10/1，本輪查詢仍09-30）。`grep -c "凍結.二解除" PENDING_QUEUE.md`
=4，逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。三軌時間戳：
FUT round675=09-30 01:0x（最舊，本輪選定）／TW round676=09-30 02:0x／
US round677=09-30 03:0x。**主動追查（非例行重複）**：複查`TRIALS_LEDGER.md`
#99（2026-09-04）確認`CALIBRATION_PROBE.md`結論(乙)「#34同理各自重跑」對
FUT軌的可行性早已查證為**不成立**（TX期貨無股票橫斷面維度可擴大樣本，
延長歷史會動用holdout，提高N_SHUFFLES反而使percentile從92.0降到89.60，
方向與「樣本太小」假設相反）——FUT軌#34已改標維持FAIL，非「待重跑」，
本輪核對無殘留待辦。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已
完成300/300；工具修正已由互動視窗commit；`git status --short`確認
`research/backtest/`／`research/validation/`／`research/adjust.py`／
`research/pit.py`／`research/trial_registry.py`等十三節限定清單內檔案
無殘留未commit編輯（輸出為空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）；
`AWAITING_REVIEW.md`「等待中（目前：25件）」，逐行核對（awk統計實際
資料列=25）與表頭一致，較round677持平，本輪未變動。**本輪誠實結論**：
交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條
`- [!]`逐一核對均未到解除時間；主動複查`CALIBRATION_PROBE.md`對FUT軌
的唯一操作指令（#34重跑）確認早於2026-09-04已查證不適用、無殘留——
FUT軌本身查無可推進的新工作單位。依`CLAUDE.md`「零之一」白名單第7條
精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶
碰十三節限定檔案、不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅
讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀
既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`）。`PROGRESS_HEARTBEAT.jsonl`已
append本輪一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：25件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選TW軌（round676=09-30 02:0x，三軌中最舊）；開工前先重新
檢查`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已裁示、
`金流一.4`還需3個交易日、`外部一改.2`tick累積14/20還差6日；凍結.二在
總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第678輪
心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。
