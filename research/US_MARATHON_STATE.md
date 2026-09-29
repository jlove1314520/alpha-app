# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

---
**最後更新：2026-09-29T17:0x+08:00（馬拉松第668輪，維運帽）**——取鎖乾淨
（cycle`20260929-170037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=1（僅`驗.九`，round667判定為DevQueue進行中）。**核對
`驗.九`現況**：`Get-CimInstance`實測round667記錄的PID135492
（`audit_v9_fetch_missing.py --phase nowcast`）與PENDING_QUEUE.md
cycle161602記錄的PID118932（`--phase all`）皆已不存在；讀
`research/data/diag_v9_fetch_missing.json`（`generated_at:
2026-09-29T16:24:16`）確認**crosscheck背景工作已於16:24因FinMind回傳
HTTP 402（額度上限）而停止**，非crash——腳本符合設計「撞牆即停不吞錯」
（`requests_used=253`，per_phase：nowcast168／crosscheck85）。交叉核對
`data/rate_limit_state.json`：`sources.finmind.blocked_until=
1790677456.67`＝**2026-09-29T18:24:16+08:00**，與腳本訊息「已標記
finmind額度2小時」一致。`[自行裁量]`：**不重試、不繞過**（`CLAUDE.md`
研究紀律「取得方式鐵律」與「外部API頻率上限清單」FinMind一節「額度
用完就誠實拒絕，不排隊、不重試」），本輪僅在`PENDING_QUEUE.md`「驗.九」
條目下補記這個真實狀態轉折（上一次commit記錄的是「PID118932仍在執行」，
本輪查證後那已是16:24前的舊狀態），未啟動任何新的FinMind請求，全程
零外部API呼叫。二的狀態改標**BLOCKED（FinMind額度冷卻，解除時間
2026-09-29T18:24+08:00之後）**，屆時DevQueue可重跑
`audit_v9_fetch_missing.py --phase crosscheck`（腳本本身會自動只補
還缺的部分）。一（定量分解）：記憶體本輪17:02查詢仍**2.60GB**（<3GB
門檻，較cycle161602記錄的2.5~2.8GB持平未回升），未解除。核對13條
`- [!]`阻塞項：`institutional_history.json`確認`dates`陣列仍20筆、
最後日期`20260924`，solid交易日數維持**16日**，20日視窗仍差4個交易日，
未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/data/ticks/
*.parquet`實測**14/20**（與round667一致），未解除；其餘11條逐一核對
開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間
（`紙.一`需等2026-10第一個交易日，今日仍09月）。**佇列深度自檢**：
`- [ ]`=1（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c
"凍結.二解除" PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際
宣告解除），本階段暫停佇列深度補件，且即使補件`驗.九`本身也非alpha
試驗（屬驗證/資料/研究診斷，凍結.二不禁止），但仍不因佇列淺而硬做
已被他人佔用且正確地respects rate limit的項目。三軌時間戳：US
round665=09-29 12:0x（最舊）／TW round666=09-29 15:0x／FUT
round667=09-29 16:0x——依輪替選US。**逐一核對`凍結.二`允許的四類
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
「等待中」表頭「目前：19件」，較round667無變動。**本輪誠實結論（含收工前發現的並發寫入）**：`驗.九`唯一未開始交辦項
的crosscheck子項已因FinMind額度耗盡而暫停，本輪誠實記錄這個狀態轉折
並遵守2小時冷卻不重試；凍結.二允許的四類工作皆已完成或無新內容，13條
`- [!]`逐一核對均未到解除時間，US軌本身查無可推進的新工作單位。
**commit前發現**：本輪對`PENDING_QUEUE.md`的編輯尚未commit時，DevQueue
cycle 20260929-170102獨立做出完全一致的結論（同樣查`diag_v9_fetch_
missing.json`／`rate_limit_state.json`／記憶體），並先行commit（`8e12fa782`
「驗.九DevQueue cycle 170102」）——由於工作目錄共用，其commit連帶掃進
了本輪尚未commit的`PENDING_QUEUE.md`編輯（兩者內容一致、非衝突，本輪
文字被完整保留在該commit diff裡），且把`驗.九`本身標記從`- [ ]`改為
`- [!]`（阻塞，retry條件＝記憶體回升≥3GB或FinMind額度2026-09-29T18:24
+08:00解除）。本輪對`PENDING_QUEUE.md`不再重複commit（已在`8e12fa782`
裡）。依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊
候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不重試
已知額度耗盡的外部請求。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼，全程零新增外部
API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_
detached.py status`、`trial_registry.py --check`、`Get-CimInstance`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`
未開始**（`驗.九`已由DevQueue改標`- [!]`阻塞，`- [!]`共14條）。**等待
審閱：19件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌
接手**：依輪替下一輪建議選TW軌（round666=09-29 15:0x，三軌中最舊）；
開工前先重新檢查`驗.九`retry條件（記憶體≥3GB或FinMind額度過
2026-09-29T18:24+08:00解除）是否已滿足、滿足就改回`- [ ]`接續；凍結.二
在總司令/Cowork明確寫「凍結.二解除」前不解除；`金流一.4`還需4個交易日；
`外部一改.2`tick累積14/20，還差6日。完整見`REPORT.md`第668輪心跳、
`PENDING_QUEUE.md`「驗.九」條目（commit `8e12fa782`）、
`research/AWAITING_REVIEW.md`。

