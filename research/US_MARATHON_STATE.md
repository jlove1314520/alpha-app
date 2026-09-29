# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

---
**最後更新：2026-09-29T12:0x+08:00（馬拉松第665輪，維運帽）**——取鎖乾淨
（cycle`20260929-120037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=1（僅`分K.零`；round663/664已判定其下一步——擴充
`shioaji_quotes.py`daemon協定加start/end參數並重啟常駐行程——需互動視窗
執行，理由是變更正式交易連線非可還原的純讀取操作，本輪重新核對此判斷
仍成立，不觸碰），`grep -c "^- \[!\]"`=13條（較round648~664的15/12再變
動：`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`
已於【驗.八】一改列合併或暫緩新條目，故總數與round663/664的12條一致，
非新變化）。逐一核對13條`- [!]`阻塞項是否解除：直接讀
`data/institutional_history.json`確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**，今日09-29（週二）12:0x查詢
（盤中，13:30才收盤，盤中資料要收盤後才會入庫），20日視窗仍差4個
交易日，未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/
data/ticks/*.parquet`實測仍**13/20**（盤中查詢無新增，收盤後排程才會
寫入），未解除；其餘11條逐一核對開頭標記，均為等總司令/Cowork裁示或
其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，今日
仍09月）。**佇列深度自檢**：`- [ ]`=1（<12下限），`CLAUDE.md`十四節
【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，皆為
條件敘述提及該詞彙、非實際宣告解除），本階段暫停佇列深度補件，且即使
補件`分K.零`已是佇列裡唯一`- [ ]`項目本身也非alpha試驗（屬infra/研究
可行性，凍結.二不禁止），但仍不因佇列淺而硬做已判定需互動視窗處理的
項目。三軌時間戳：US round662=09-29 09:0x（最舊）／TW round663=09-29
10:0x／FUT round664=09-29 11:0x——依輪替選US。**逐一核對`凍結.二`
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；
資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗
commit；`git status --short`確認`research/backtest/`／`research/
validation/`／`research/adjust.py`／`research/pit.py`／`research/
trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯（輸出為
空）。US軌本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子家族
結案狀態未變，`#49`/`#51`/`#52`已FAIL結案、`#82`依`驗.七`裁示暫停，
無對應結構性優勢候選可開新方向（`凍結.二`期間本來就不得開新alpha
試驗）。`run_detached.py status`：`running=0`（162筆歷史，無job待
收成）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（406列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格逐行核對
共**18列**，與表頭「目前：18件」一致（較round662的16件+2，來自`驗.八`
本身與`本地AI摘要(Breeze-7B)`兩項完成待審，非本輪新增動作）。**本輪
誠實結論**：`分K.零`唯一未開始交辦項的下一步需要變更正式交易連線，
不適合由無人值守馬拉松執行；凍結.二允許的四類工作皆已完成或無新
內容，13條`- [!]`逐一核對均未到解除時間，US軌本身查無可推進的新
工作單位——依`CLAUDE.md`「零之一」白名單第7條精神（佇列真的空了）
記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰
十三節限定檔案、不變更正式交易連線。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼
（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫
（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、`run_
detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩1條`- [ ]`
未開始**（`分K.零`，判定為需互動視窗處理，非漏做）。**等待審閱：
18件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：
依輪替下一輪建議選TW軌（round663=09-29 10:0x，三軌中最舊）；開工前
先重新檢查`分K.零`是否已由互動視窗處理；凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除；`金流一.4`還需4個交易日（今日09-29收盤後
入庫將是第一個新增交易日）；`外部一改.2`tick累積仍13/20。完整見
`REPORT.md`第665輪心跳、`PENDING_QUEUE.md`「分K.零」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T09:0x+08:00（馬拉松第662輪，維運帽）**——取鎖乾淨
（cycle`20260929-090036`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，含互動視窗剛完成的`驗.七`已標
`- [x]`），`grep -c "^- \[!\]"`=15條（與round648~661一致）。逐一核對15條
`- [!]`阻塞項是否解除：直接讀`data/institutional_history.json`確認
`dates`陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，
今日09-29（週二）09:0x查詢（盤前，13:30才收盤，09-25/09-28兩個已過
交易日尚未入庫，且今日尚未收盤），20日視窗仍差4個交易日，未解除；
`外部一改.2`／`研究.c`共用的tick累積`ls research/data/ticks/*.parquet`
實測仍**13/20**（同理盤前無新增），未解除；其餘13條（`資料源.外銷
訂單彙總`／`重構.C4`／`資料源一.3`／`外部二改`／`Cybex.beta`／`分K.零`／
`稽核.三`／`稽核.五`／`零之三`／`結案.一`／`常備.9`／`紙.一`）逐一核對
開頭標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間
（`紙.一`需等2026-10第一個交易日，今日仍09月）。**佇列深度自檢**：
`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c
"凍結.二解除" PENDING_QUEUE.md`=3，皆為條件敘述提及該詞彙、非實際
宣告解除），本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：
US round659=09-28 19:3x（最舊）／TW round660=09-28 22:0x／FUT
round661=09-29 00:3x——依輪替選US。**額外查證：`驗.七`（總司令
2026-09-29裁示，互動視窗執行）現況**——PENDING_QUEUE.md對應條目已標
`- [x]`且附完整完成回報（#82新alpha軸暫停已生效並已寫進
`HYPOTHESIS_QUEUE_CONTINUATION_PROMPT.txt`第負一步；699筆殘留異常
分類、#7/#8重驗（#403/#404皆FAIL，原判定鎖定不動）、Sortino納入標準
報表皆已完成並push，commit`270f8775`等；現正等Cowork核對，不需要
馬拉松軌道插手）；`AWAITING_REVIEW.md`「等待中」表頭已由互動視窗同步
更新為**16件**（15件舊有＋`驗.七`本身1件），逐行核對表格列數與表頭
一致。**逐一核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑
先前輪次已全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成
300/300；工具修正已由互動視窗commit；`git status --short`確認
`research/backtest/`／`research/validation/`／`research/adjust.py`／
`research/pit.py`／`research/trial_registry.py`等十三節限定清單內檔案
無殘留未commit編輯（輸出為空）。US軌本身`US_LEADS.md`/`STRATEGY_
GRAVEYARD.md`price-only因子家族結案狀態未變，`#49`/`#51`/`#52`已FAIL
結案，`#82`本輪起依`驗.七`裁示暫停、不得再探測，無對應結構性優勢候選
可開新方向（`凍結.二`期間本來就不得開新alpha試驗）。`run_detached.py
status`：`running=0`（162筆歷史，無job待收成）。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純查證
未新增判定；`驗.七`新增的#401~#404已由互動視窗登記完畢，非本輪動作）。
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（H.一單次
解鎖已於09-27消耗，非本輪新增動作，僅讀取核對）。**本輪誠實結論**：
四類允許工作皆已完成或無新內容，`- [!]`15條逐一核對均未到解除時間，
`驗.七`已完成正等Cowork核對（不屬於馬拉松可插手的工作），US軌本身
查無可推進的新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神
（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰`凍結.二`禁止的新
alpha試驗、不搶碰十三節限定檔案。未動`alpha.db`/`fetch.py`/`parsers.py`
/`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋
改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**。**等待審閱：16件**
（與`AWAITING_REVIEW.md`「等待中」表格列數一致，較上一輪＋1，來自
`驗.七`完成待Cowork核對，非本輪新增動作）。**下一輪任一軌接手**：依
輪替下一輪建議選TW軌（round660=09-28 22:0x，三軌中最舊）；凍結.二在
總司令/Cowork明確寫「凍結.二解除」前不解除，不補新alpha試驗；`金流
一.4`還需4個交易日（20日視窗，09-29收盤後入庫將是第一個新增交易日）；
`外部一改.2`tick累積仍13/20。完整見`REPORT.md`第662輪心跳、
`PENDING_QUEUE.md`「凍結.二」／「驗.七」條目、`research/AWAITING_
REVIEW.md`。
