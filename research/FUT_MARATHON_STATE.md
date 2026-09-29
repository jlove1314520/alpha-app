# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-29T00:3x+08:00（馬拉松第661輪，維運帽）**——取鎖乾淨
（cycle`20260929-003037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=**1**（round648~660以來首次出現未開始交辦項，非0）：
`驗.七`（殘留異常分類＋#7/#8重驗預登記＋Sortino納入標準報表＋#82暫停，
五個子項）。**判斷是否可做**：`git log --oneline -3`確認最近3個commit
（`db3e820e`/`270f8775`/`8e1c0edf`）皆已在處理此條目的項一/二/三.1/四，
作者含`Claude Fable 5.1`（互動視窗協作模型署名）；`git status --short`
確認核心研究檔案清單（`research/backtest/`／`research/validation/`／
`research/adjust.py`／`research/pit.py`／`research/trial_registry.py`）
無殘留未commit編輯，但`powershell Get-CimInstance Win32_Process`實測
發現**兩支非`run_detached.py`啟動的python行程正在跑**：
`audit_v7_factor_revalidation.py --group ii`（PID116796，00:29:22啟動，
對應項三②(ii)新還原公式＋新財報時點）與`audit_v6_anomaly_rescan.py`
（PID114532，00:30:00啟動，對應db3e820e提到的「已修正並重跑中」）——
兩者啟動時間都在本輪取鎖（00:30:37）前不到90秒，且`run_detached.py
status`顯示`running=0`（這兩支不是透過脫離session機制跑的，代表是
互動視窗當下正在執行的前景/背景工作，不是孤兒行程）。**本輪判斷**：
`驗.七`雖是交辦、理論上該做，但它同時正被另一個活躍session實際執行中
（有時間吻合的commit與running process佐證，非臆測），此時搶著碰同一批
輸出檔（`research/data/diag_v7_factor_revalidation.json`已在`git status`
顯示為`M`）會有覆寫/競爭風險，且項三本身是統計判定性質（#7/#8重驗
n=6 Bonferroni門檻判定），屬於`CLAUDE.md`「絕對不准為了省額度而降階的
工作」點名的統計判定類別，不適合由每輪25分鐘、無記憶的馬拉松執行個體
在不清楚對方進度下插手。**依「不確定但可還原→自行裁量」處理**：本輪
不觸碰`驗.七`、不啟動任何新的`audit_v7`/`audit_v6`相關行程，避免與
進行中的互動視窗工作衝突；`[自行裁量]`標記，下一輪開工前重新檢查
這兩支行程是否已結束、commit是否已納入，若已結束且條目仍是`- [ ]`
才由下一輪接手完成收尾（例如`register_trial()`登記、`AWAITING_REVIEW.md`
更新）。核對15條`- [!]`阻塞項：`institutional_history.json`確認`dates`
陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，今日
09-29（週二）00:3x查詢，尚未進入新交易日收盤入庫窗口，20日視窗仍差
4個交易日，未解除；tick累積`ls research/data/ticks/*.parquet`實測仍
**13/20**，未解除；其餘13條逐一核對開頭標記，均為等總司令/Cowork裁示
或其他外部條件，皆未到解除時間。**佇列深度自檢**：`- [ ]`=1（<12下限），
`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c "凍結.二解除"
PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際宣告解除），本階段
暫停佇列深度補件，且即使補件`驗.七`本身也非alpha試驗（屬驗證/維運，
凍結.二不禁止），但仍不因佇列淺而硬做已被他人佔用的項目。三軌時間戳：
FUT round658=09-28 17:0x（最舊）／US round659=09-28 19:3x／TW
round660=09-28 22:0x——依輪替選FUT。`run_detached.py status`：
`running=0`（162筆歷史，無job待收成，兩支正在跑的行程如上述非透過此
機制啟動）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（404列，本輪純查證未新增判定）。`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中」表格表頭「目前：15件」，較round648~660
無變動。**本輪誠實結論**：交辦佇列有1條`驗.七`，但實測證據顯示它正被
互動視窗即時執行中，為避免覆寫/競爭與重複統計判定，本輪選擇不插手，
記錄觀察並結束本輪，不硬做、不觸碰`凍結.二`禁止的新alpha試驗、不搶碰
十三節限定檔案、未啟動任何與`驗.七`重疊的新行程。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何
原始碼（僅讀取核對＋改狀態檔＋archive舊state條目＋一次PowerShell
`Get-CimInstance`查詢行程命令列，無外部API呼叫）。`PROGRESS_HEARTBEAT.
jsonl`已append本輪一行。**交辦佇列還剩1條未開始**（`驗.七`，判定為
他人進行中，非漏做）。**等待審閱：15件**（與`AWAITING_REVIEW.md`
「等待中」表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌
（round659=09-28 19:3x，三軌中最舊）；開工前務必重新檢查`驗.七`
是否仍在進行中（`Get-CimInstance`查`audit_v7`/`audit_v6`相關PID、
`git log`看有沒有新commit），若已完成收尾且仍是`- [ ]`才動手，避免
與互動視窗重複勞動；凍結.二在總司令/Cowork明確寫「凍結.二解除」前
不解除；`金流一.4`還需4個交易日；`外部一改.2`tick累積仍13/20。完整見
`REPORT.md`第661輪心跳、`PENDING_QUEUE.md`「驗.七」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-28T17:0x+08:00（馬拉松第658輪，維運帽）**——取鎖乾淨
（cycle`20260928-170037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round648~657一致）。逐一核對15條`- [!]`阻塞項是否解除：直接讀
`data/institutional_history.json`確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**，今日09-28（週一）17:0x查詢
（收盤後約3.5小時，法人資料排程尚未入庫本日新交易日），20日視窗仍差
4個交易日，未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/
data/ticks/*.parquet`實測仍**13/20**（同理排程尚未寫入新tick），未
解除；其餘13條（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`外部二改`／`Cybex.beta`／`分K.零`／`稽核.三`／`稽核.五`／`零之三`／
`結案.一`／`常備.9`／`紙.一`）逐一核對開頭標記，均為等總司令/Cowork
裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，
皆為條件敘述提及該詞彙、非實際宣告解除），本階段暫停佇列深度補件，
不重掃備援來源。三軌時間戳：FUT round655=09-28 09:3x（最舊）／TW
round657=09-28 14:3x／US round656=09-28 12:0x——依輪替選FUT。**逐一
核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已
全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具
修正已由互動視窗commit；`git status --short`確認`research/backtest/`
／`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯（輸出為空）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`
回顧：個股期貨橫斷面調查線與trend/oi組合嘗試皆已窮盡並結案，無清楚
剩餘的「全新機制」候選，且`凍結.二`期間本來就不得登記新alpha試驗。
`run_detached.py status`：`running=0`（162筆歷史，無job待收成）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（402列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格逐行核對
共**15列**，與表頭「目前：15件」一致，較round648~657無變動。**本輪
誠實結論**：四類允許工作皆已完成或無新內容，`- [!]`15條逐一核對均
未到解除時間，FUT軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之
一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不
觸碰`凍結.二`禁止的新alpha試驗、不搶碰十三節限定檔案。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），
全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`ls`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩
0條未開始**。**等待審閱：15件**（與`AWAITING_REVIEW.md`「等待中」
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌
（round656=09-28 12:0x，三軌中最舊）；凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除，不補新alpha試驗；`金流一.4`還需4個交易日
（20日視窗，收盤後排程入庫後可望更新）；`外部一改.2`tick累積仍
13/20。完整見`REPORT.md`第658輪心跳、`PENDING_QUEUE.md`「凍結.二」
條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T11:0x+08:00（馬拉松第664輪，維運帽）**——取鎖乾淨
（cycle`20260929-110036`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=1（僅`分K.零`；`驗.八`／`稽核.三B`已於round663之後由
互動視窗/DevQueue完成並標`- [x]`）。**核對`分K.零`**：round663已完成
「涵蓋範圍」量測（上市/上櫃/ETF共9檔全200、已下市3檔全404），下一步
「最多回溯多久」需擴充`shioaji_quotes.py`daemon協定（加start/end參數）
並重啟常駐行程——round663已明確記錄「對正式交易連線的變更，建議由
互動視窗執行」。本輪重新核對此判斷仍成立（`shioaji_quotes.py`是實盤
報價常駐行程，重啟有中斷風險，非可回復的純讀取操作），依「零之一」
白名單精神不自行變更正式交易連線，本輪不觸碰，`分K.零`維持`- [ ]`。
逐一核對12條`- [!]`阻塞項：`institutional_history.json`確認`dates`
陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，20日視窗
仍差4個交易日，未解除；tick累積`ls research/data/ticks/*.parquet`實測
仍**13/20**，未解除；其餘10條均為等總司令/Cowork裁示或其他外部條件，
皆未到解除時間。**佇列深度自檢**：`- [ ]`=1（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，
皆為條件敘述提及、非實際宣告解除），本階段暫停佇列深度補件。三軌
時間戳：FUT round661=09-29 00:3x（最舊）／TW round663=09-29 10:0x／US
round662=09-29 09:0x——依輪替選FUT。**逐一核對`凍結.二`允許的四類
工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取
（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗commit；
`git status --short`確認`research/backtest/`／`research/validation/`／
`research/adjust.py`／`research/pit.py`／`research/trial_registry.py`
等十三節限定清單內檔案無殘留未commit編輯（輸出為空）。FUT軌本身
`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`回顧：個股期貨橫斷面線、
trend/oi組合嘗試、全天close-to-close反轉/順勢皆已窮盡並結案，無清楚
剩餘的全新機制候選，且凍結.二期間本來就不得登記新alpha試驗。
`run_detached.py status`：`running=0`（162筆歷史，無job待收成）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（406列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格逐行核對
共**18列**，與表頭「目前：18件」一致（較round663的16件+2，來自
`驗.八`本身與`本地AI摘要(Breeze-7B)`兩項完成待審，非本輪新增動作）。
**本輪誠實結論**：`分K.零`唯一未開始交辦項的下一步需要變更正式交易
連線，不適合由無人值守馬拉松執行；凍結.二允許的四類工作皆已完成或
無新內容，12條`- [!]`逐一核對均未到解除時間，FUT軌本身查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、
不變更正式交易連線。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋
改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩1條`- [ ]`未開始**（`分K.零`，判定
為需互動視窗處理，非漏做）。**等待審閱：18件**（與`AWAITING_REVIEW.md`
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌
（round662=09-29 09:0x，三軌中最舊）；開工前先重新檢查`分K.零`是否
已由互動視窗處理；凍結.二在總司令/Cowork明確寫「凍結.二解除」前不
解除；`金流一.4`還需4個交易日；`外部一改.2`tick累積仍13/20。完整見
`REPORT.md`第664輪心跳、`PENDING_QUEUE.md`「分K.零」條目、
`research/AWAITING_REVIEW.md`。
