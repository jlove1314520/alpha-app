# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-29T16:0x+08:00（馬拉松第667輪，維運帽）**——取鎖乾淨
（cycle`20260929-160037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=1（僅`驗.九`，標記「進行中，DevQueue cycle
20260929-154602接手」）。**核對`驗.九`是否真的在進行中**：
`powershell Get-CimInstance Win32_Process`實測發現PID135492
`audit_v9_fetch_missing.py --phase nowcast`於15:49:07啟動、取鎖前仍在
執行（非透過`run_detached.py`機制，屬互動視窗/DevQueue前景工作），且
`git status --short`顯示`research/audit_v9_fetch_missing.py`／
`research/audit_v9_revenue_trace.py`為untracked新檔、多個`data/*.json`
為近期修改——與PENDING_QUEUE.md該條目內文描述（一/二子項進行中、三/四
已完成、五未達成）吻合，判定確實正被其他活躍session執行中。比照
round661對`驗.七`、round663對`驗.八`的既有判斷（時間吻合＝互動視窗
正在做，避免插手覆寫競爭），本輪**不觸碰`驗.九`**、不啟動任何新的
`audit_v9`相關行程。核對13條`- [!]`阻塞項：`institutional_history.json`
確認`dates`陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，
今日09-29（週二）16:0x查詢（收盤後約2.5小時，法人資料排程尚未入庫本日
新交易日），20日視窗仍差4個交易日，未解除；`外部一改.2`／`研究.c`
共用的tick累積`ls research/data/ticks/*.parquet`實測**14/20**（較
round648~664的13/20 +1，同理仍未達20），未解除；其餘11條逐一核對開頭
標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`
需等2026-10第一個交易日，今日仍09月）。**佇列深度自檢**：`- [ ]`=1
（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c "凍結.二解除"
PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際宣告解除），本階段
暫停佇列深度補件，且即使補件`驗.九`本身也非alpha試驗（屬驗證/資料/
研究診斷，凍結.二不禁止），但仍不因佇列淺而硬做已被他人佔用的項目。
三軌時間戳：FUT round664=09-29 11:0x（最舊）／US round665=09-29
12:0x／TW round666=09-29 15:0x——依輪替選FUT。**逐一核對`凍結.二`允許
的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料
抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗
commit；`git status --short`確認`research/backtest/`／`research/
validation/`／`research/adjust.py`／`research/pit.py`／`research/
trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯（輸出為
空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`回顧：個股期貨
橫斷面線、trend/oi組合嘗試、全天close-to-close反轉/順勢皆已窮盡並
結案，無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新alpha
試驗。`run_detached.py status`：`running=0`（162筆歷史，無job待收成，
`驗.九`正在跑的行程如上述非透過此機制啟動）。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純查證
未新增判定）。`validation/holdout.py::is_holdout_consumed()`讀取為
`True`（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格
表頭「目前：19件」，較round666無變動（表格逐行核對32行含表頭/分隔線，
與19筆資料列一致）。**本輪誠實結論**：交辦佇列唯一的`- [ ]`項目
`驗.九`正被DevQueue即時執行中，為避免覆寫/競爭，本輪選擇不插手；
凍結.二允許的四類工作皆已完成或無新內容，13條`- [!]`逐一核對均未到
解除時間（tick累積14/20有進展但未達標），FUT軌本身查無可推進的新
工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不
硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、未
啟動任何與`驗.九`重疊的新行程。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改
狀態檔＋archive舊state條目＋一次PowerShell`Get-CimInstance`查詢行程
命令列，無外部API呼叫）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。
**交辦佇列還剩1條`- [ ]`未開始**（`驗.九`，判定為他人進行中，非漏做）。
**等待審閱：19件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪
任一軌接手**：依輪替下一輪建議選US軌（round665=09-29 12:0x，三軌中
最舊）；開工前務必重新檢查`驗.九`是否仍在進行中（`Get-CimInstance`查
`audit_v9`相關PID、`git log`看有沒有新commit）；凍結.二在總司令/
Cowork明確寫「凍結.二解除」前不解除；`金流一.4`還需4個交易日；`外部
一改.2`tick累積14/20，還差6日。完整見`REPORT.md`第667輪心跳、
`PENDING_QUEUE.md`「驗.九」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T19:0x+08:00（馬拉松第670輪，維運帽）**——取鎖乾淨
（cycle`20260929-190037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項）；`grep -c "^- \[!\]"`=14條（與
round669一致）。逐一核對14條`- [!]`阻塞項是否解除：`驗.九`兩個retry
條件本輪重新查證——FinMind額度`blocked_until`=2026-09-29T18:24:16+08:00
**已過**（本輪查詢19:0x，已超過block時限約37分鐘），但`Get-CimInstance
Win32_Process`實測發現**`audit_v9_fetch_missing.py --phase crosscheck`
（PID131264）已於18:26:16啟動並持續執行中**（`data/rate_limit_state.json`
的`last_request_at`=19:00:57，與查詢當下僅差約23秒，代表該行程正在
主動使用FinMind額度）——判定為DevQueue在額度解除後已自行接手重試，
比照round661/663/667對`驗.七`/`驗.八`/`驗.九`的既有判斷（時間吻合＝
他人session正在做，避免插手覆寫競爭），本輪**不觸碰`驗.九`**、不啟動
任何新的`audit_v9`相關行程；記憶體本輪實測**2.59GB**（<3GB門檻，較
round668的2.60GB持平未回升），另一retry條件仍未解除。核對其餘13條：
`institutional_history.json`確認`dates`陣列仍20筆、最後日期`20260924`，
solid交易日數維持**16日**，今日09-29（週二）19:0x查詢（收盤後約5.5
小時，法人資料排程尚未入庫本日新交易日），20日視窗仍差4個交易日，
未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/data/ticks/
*.parquet`實測仍**14/20**，未解除；其餘11條逐一核對開頭標記，均為
等總司令/Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`需等
2026-10第一個交易日，今日仍09月）。**佇列深度自檢**：`- [ ]`=0
（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c "凍結.二解除"
PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際宣告解除），本階段
暫停佇列深度補件，不重掃備援來源。三軌時間戳：FUT round667=09-29
16:0x（最舊）／US round668=09-29 17:0x／TW round669=09-29 18:0x——
依輪替選FUT。**逐一核對`凍結.二`允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`/`閘門.一`）
已完成300/300；工具修正已由互動視窗commit；`git status --short`確認
`research/backtest/`／`research/validation/`／`research/adjust.py`／
`research/pit.py`／`research/trial_registry.py`等十三節限定清單內檔案
無殘留未commit編輯（輸出為空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天
close-to-close反轉/順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。`run_detached.py status`：
`running=0`（162筆歷史，無job待收成，`驗.九`正在跑的行程如上述非透過
此機制啟動）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（406列，本輪純查證未新增判定）。`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中」表頭「目前：19件」，本輪未變動。**本輪
誠實結論**：交辦佇列無`- [ ]`項目，`驗.九`唯一FinMind額度解除的retry
條件已滿足但正被DevQueue即時執行中（記憶體retry條件仍未解除），為
避免覆寫/競爭本輪選擇不插手；凍結.二允許的四類工作皆已完成或無新
內容，其餘13條`- [!]`逐一核對均未到解除時間，FUT軌本身查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、
未啟動任何與`驗.九`重疊的新行程。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼
（僅讀取核對＋改狀態檔＋archive舊state條目＋一次PowerShell
`Get-CimInstance`查詢行程命令列），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`Get-CimInstance`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**。**等待審閱：19件**（與`AWAITING_REVIEW.md`表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選US軌（round668=09-29 17:0x，
三軌中最舊）；開工前先重新檢查`驗.九`是否仍在DevQueue執行中、記憶體
retry條件是否已回升≥3GB；凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除；`金流一.4`還需4個交易日；`外部一改.2`tick累積仍14/20，還差
6日。完整見`REPORT.md`第670輪心跳、`PENDING_QUEUE.md`「驗.九」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T22:0x+08:00（馬拉松第673輪，維運帽）**——取鎖乾淨
（cycle`20260929-220037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項）；`grep -c "^- \[!\]"`=14條（與
round670~672一致）。逐一核對14條`- [!]`阻塞項是否解除：`驗.九`兩個
retry條件本輪重新查證——`Get-CimInstance Win32_Process`未發現任何
`audit_v9`相關行程在跑（round672記錄的PID131264 crosscheck已跑完退出，
非本輪動作）；讀`research/data/diag_v9_fetch_missing.json`：
`generated_at=2026-09-29T20:48:17`、`requests_used=426`／`remaining=0`
／`stopped=null`，與round672記錄一致，crosscheck已完成、無新變化；
`git log --oneline -2 -- research/audit_v9_fetch_missing.py`確認
round672提到的WIP修改（`V9_SPACING`環境變數）已由commit`575901a71`
（round672自己）併入正式commit，`git status --short`確認該檔案目前
無殘留未commit編輯。記憶體retry條件本輪`Get-CimInstance
Win32_OperatingSystem`實測**2.63GB**（<3GB門檻，較round672的2.76GB
略降，仍未解除）——驗.九一（`audit_v9_revenue_trace.py`定量分解）
維持阻塞，`[自行裁量]`不重試（已試超過兩次，retry條件明文為記憶體
回升非重新嘗試）。核對其餘13條：`data/institutional_history.json`
（需以`encoding='utf-8'`讀取，預設`cp950`會`UnicodeDecodeError`）
確認`dates`陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，
今日09-29（週二）22:0x查詢（收盤後約8.5小時，法人資料排程仍未入庫
本日新交易日），20日視窗仍差4個交易日，未解除；`外部一改.2`／
`研究.c`共用的tick累積`ls research/data/ticks/*.parquet`實測仍
**14/20**，未解除；其餘11條逐一核對開頭標記，均為等總司令/Cowork
裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對其中3行為條件敘述提及、1行為round670自身心跳文字裡引用
「=3」這個數字本身被字串比對命中，非實際宣告解除），本階段暫停佇列
深度補件，不重掃備援來源。三軌時間戳：FUT round670=09-29 19:0x（最舊）
／US round671=09-29 20:0x／TW round672=09-29 21:0x——依輪替選FUT。
**逐一核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次
已全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具
修正已由互動視窗commit；`git status --short`確認`research/backtest/`
／`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯（輸出為空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`
回顧：個股期貨橫斷面線、trend/oi組合嘗試、全天close-to-close反轉/
順勢皆已窮盡並結案，無清楚剩餘的全新機制候選，且凍結.二期間本來就
不得登記新alpha試驗。`run_detached.py status`：`running=0`（162筆
歷史，無job待收成）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純查證未新增
判定）。`validation/holdout.py::is_holdout_consumed()`讀取為`True`
（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表頭「目前：
19件」，逐行核對21行（含表頭/分隔線）與19筆資料列一致，本輪未變動。
**本輪誠實結論**：交辦佇列無`- [ ]`項目，`驗.九`FinMind額度子任務已
完成（crosscheck 426/426零撞牆），記憶體子任務仍未解除（2.63GB<3GB），
凍結.二允許的四類工作皆已完成或無新內容，其餘13條`- [!]`逐一核對均
未到解除時間，FUT軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不變更正式交易連線。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），
全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`Get-CimInstance`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。
**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：19件**（與
`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選US軌（round671=09-29 20:0x，三軌中最舊）；開工前先重新
檢查`驗.九`記憶體retry條件是否已回升≥3GB；凍結.二在總司令/Cowork
明確寫「凍結.二解除」前不解除；`金流一.4`還需4個交易日；`外部一改.2`
tick累積仍14/20，還差6日。完整見`REPORT.md`第673輪心跳、
`PENDING_QUEUE.md`「驗.九」條目、`research/AWAITING_REVIEW.md`。
