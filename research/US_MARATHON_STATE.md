# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-10-03T02:3x+08:00（馬拉松第701輪，US軌，維運帽）**——
取鎖乾淨（cycle`20261003-023037`）。三軌時間戳（開工前）：US round698=
10-02 23:3x（最舊，本輪選定）／FUT round699=10-03 00:3x／TW round700=
10-03 01:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未
開始交辦項，先.十二-一/二已由互動視窗於round700之前標`[x]`結案）；
`grep -c "^- \[!\]"`=19（較round698的21減少2條，為先.十二-一/二結案
＋維運.market.yml今日(10/1)已解除所致，非本輪新增變動）。

逐一核對19條`- [!]`阻塞項：`金流一.4` `sector_flow.json`
`meta.trading_days_available`仍**19**、`windows_missing_days.20`仍
**1**（與round700一致），未解除；`外部一改.2`／`研究.c`tick累積
`ls research/data/ticks/*.parquet`實測仍**15/20**，未解除；`本地AI
摘要(Breeze-7B)`仍待總司令四選一，未解除；`先.十二-三`／`先.十一-二`
重跑`finmind_warmup.py --status`：`stmt_code_coverage`已由round700
記錄的34.09%升至**39.59%**（`calls_last_hour=111`，`eta_local=
2026-10-04T00:32+08:00`），仍未達完成門檻，未解除；`先.六-四`／
`先.七-一`（Shioaji）：`data/quotes_sinopac.json`仍`connected:false`，
下一交易日2026-10-05（週一），本輪查詢時間（週六02:3x）尚未到，未
解除；`先.九-五`派發延遲樣本仍1/3（僅10/2一筆，等10/5、10/6），未
解除；其餘13條（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`／維運
`.gitattributes`renormalize提案／`紙.一`／其餘維運觀察項）皆等
總司令/Cowork裁示或固定條件，均未到解除時間，與round700一致，不
重複贅述。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為
條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：
`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。
**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次
已全部完成並登記；資料抓取（`資料.一`已完成300/300）；工具修正——
本輪僅執行既有工具（`finmind_warmup.py --status`／`trial_registry.py
--check`／`run_detached.py status`）與更新狀態記錄，未修改任何原始
碼；`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出
為空（十三節限定清單內檔案無殘留未commit編輯，本輪亦未touch）。US軌
本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案狀態未變，凍結.二期間
本來就不得登記新alpha試驗。

驗證：`run_detached.py status` running=0（162筆歷史，無job待收成）；
`trial_registry.py --check` exit=0 PASS（409列，另有FDR對照表33列，
最大編號#407，本輪未新增判定）；`is_holdout_consumed()`未重查（非
本輪動作範圍，round700已核對為True，條件不變）。`AWAITING_REVIEW.md`
「等待中（目前：44件）」，逐行核對與44筆資料列一致，本輪未變動（本
輪未產生新完成項，先.十二-一/二等為互動視窗先前commit）。

**本輪誠實結論**：交辦佇列`- [ ]`=0；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間（唯一有量化進度的是
先.十一-二/先.十二-三財報預熱34.09%→39.59%，仍未達完成門檻）；US軌
本身查無可推進的新alpha試驗工作單位——依`CLAUDE.md`「零之一」白名單
第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha
試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證與既有工具的
`--status`/`--check`查詢，無新增資料抓取類API呼叫。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條
`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`表格列
數一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round699=
10-03 00:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、
先.十一-二/先.十二-三財報預熱是否已達完成門檻、`金流一.4`20日視窗
是否已補到0、`外部一改.2`tick累積15/20進度、`先.六-四`/`先.七-一`
是否已到10/5開盤可驗證。凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除。完整見`REPORT.md`第701輪心跳、`PENDING_QUEUE.md`「金流
一.4」「外部一改.2」「先.十二-三」相關條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T05:3x+08:00（馬拉松第704輪，US軌，維運帽）**——取鎖
乾淨（cycle`20261003-053037`）。三軌時間戳（開工前）：US round701=10-03
02:3x（最舊，本輪選定）／FUT round702=10-03 03:3x／TW round703=10-03
04:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round702~703持平）；`grep -c "^- \[!\]"`=19（持平）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除，本輪對有量化進度可能性的條目重新
實測，其餘沿用round703既定結論不重複贅述）：`先.十一-二`／`先.十二-三`
FinMind財報預熱：`finmind_warmup.py --status`實測`stmt_code_coverage`
已由round703的53.26%推進至**61.09%**（`stmt_codes_complete`1179/1930，
`calls_last_hour=450`，`eta_local=2026-10-04T00:30`），另查`px_code_
coverage`仍**0.1%**（`px_codes_complete`2/1930）——**本輪新發現**：財報
欄位（`stmt_code`）覆蓋率持續推進，但價格欄位（`px_code`）幾乎沒動，
推測是warmup排程優先序把額度都分給`stmt_code`佇列，`px_code`佇列實質
沒在消化；這不影響先.十一-二/先.十二-三既定「等覆蓋率達可信水準」的
解除條件判斷（§5相關係數分析主要依賴`stmt_code`，待互動視窗或下一輪
確認`px_code`是否也是解除前提之一，本輪僅如實記錄觀察，未更動
`finmind_warmup.py`原始碼，該檔不在十三節限定清單內但本輪仍選擇只讀
不改以避免越權判斷解除條件定義）；`金流一.4``sector_flow.json`
`trading_days_available`仍**19**、`windows_missing_days.20`仍**1**，
`generated_at`仍`2026-10-03T00:23:57`（週六無新批次），未解除；`外部
一改.2`／`研究.c`tick累積`ls research/data/ticks/*.parquet`實測仍
**15/20**（週末無盤中tick可累積，依2026-09-15總司令裁示本輪不重複
贅述進度細節），未解除；`先.七-一`／`先.六-四`Shioaji：
`data/quotes_sinopac.json`仍`connected:false`、`fetched_at`停在
2026-10-02T08:31（週六無交易，下一交易日2026-10-05週一，結構上不可能
在本輪驗證），未解除；`先.九-五`派發延遲樣本仍1/3（僅10/2一筆，等
10/5、10/6），未解除；其餘13條（`本地AI摘要(Breeze-7B)`／`維運.先.
六-二後續一`／`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／`稽核.
三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`等）皆待總司令/
Cowork裁示或親自操作，與round703一致，未解除。`grep -c "凍結.二解除"
PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告解除，
凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），凍結.二期間
暫停補件，不硬湊alpha試驗候選。**逐一核對凍結.二允許的四類工作現況**：
稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已
完成300/300，`先.十一-二`財報預熱為既有排程被動累積，本輪僅讀取
核對）；工具修正本輪未修改任何原始碼（僅讀取診斷＋archive
round695舊state條目至`US_STATE_ARCHIVE.md`，`US_MARATHON_STATE.md`/
`US_STATE_ARCHIVE.md`屬狀態檔不在十三節限定清單內）；`git status
--short -- research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯，本輪亦未touch）。US軌本身`US_LEADS.md`/
`STRATEGY_GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。

**housekeeping（[自行裁量]，非交辦，屬馬拉松維運帽日常工作）**：
`US_MARATHON_STATE.md`累積到4個條目（695/698/701/本輪704），超過規則
要求的「只保留最新3則」，已將最舊的695原文搬到`US_STATE_ARCHIVE.md`
（append-only，接續既有時間順序：689後692後695），本檔只留698／701／
本輪704。純檔案維護，未變動任何判定內容。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`holdout.py::is_holdout_consumed()`未重查（非本輪動作範圍，round701
已核對為True，條件不變）。`AWAITING_REVIEW.md`「等待中（目前：44件）」，
與round701/703持平，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱53.26%→61.09%（同時發現`px_code_
coverage`停滯在0.1%，已如實記錄供後續判斷）；US軌本身查無可推進的新
alpha試驗工作單位；**今日仍為週六無開盤，多數時效性阻塞結構上不可能
在本輪解除**——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不
代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼。全程新增外部
呼叫僅限讀取性質驗證（`research/finmind_warmup.py --status`讀取既有
快取狀態、`run_detached.py status`、`trial_registry.py --check`、既有
`.json`/`.md`帳本檔案讀取），未讀取或輸出任何金鑰／憑證內容。
`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩0條
`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`表格列數
一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round702=
10-03 03:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、先.十一
-二/先.十二-三財報預熱`px_code_coverage`是否開始推進、`stmt_code_
coverage`是否已達完成門檻、`金流一.4`20日視窗是否已補到0（週一10/5
開盤後才可能）、`先.七-一`/`先.九-五`是否已到10/5開盤可驗證。凍結.二
在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第704
輪心跳、`PENDING_QUEUE.md`「金流一.4」「先.十一-二」「先.十二-三」
相關條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T08:3x+08:00（馬拉松第707輪，US軌，維運帽）**——
取鎖乾淨（cycle`20261003-083037`）。三軌時間戳（開工前）：US round704=
10-03 05:3x（最舊，本輪選定）／FUT round705=10-03 06:3x／TW round706=
10-03 07:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未
開始交辦項，與round705~706持平）；`grep -c "^- \[!\]"`=19（持平）。

**本輪實質產出：解答round704留下的未解之問**——round704觀察到
`stmt_code_coverage`持續推進但`px_code_coverage`停滯於0.1%，推測可能
是warmup排程優先序把額度都分給`stmt_code`佇列，標記為待確認的疑點。
本輪讀`research/finmind_warmup.py`原始碼（第256行註解「P2 補缺：財報
先、價格後」）確認**這是刻意設計的循序優先序，不是bug**：`gen_tasks()`
的P2階段用兩個獨立`for`迴圈依序處理`miss_stmt`後才處理`miss_px`
（第256~264行），在`stmt`缺口（目前1181個檔案，5790-4609）尚未清空前，
`px`佇列（缺口5606個檔案）結構上不會被yield任何任務；`write_status()`
的`eta_hours_at_92pct_cap`本就是`miss_stmt`+`miss_px`合計算出的單一
完工時間（本輪`eta_local=2026-10-04T00:55`），代表`px`會在`stmt`清空後
接續處理，不是被永久餓死。**結論：無需修改`finmind_warmup.py`，
round704的疑點已排除，非程式缺陷**；未修改該檔案任何原始碼（僅讀取
確認設計意圖）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除，其餘沿用round706既定結論不重複
贅述）：`先.十一-二`／`先.十二-三`FinMind財報預熱：`finmind_warmup.py
--status`實測`stmt_code_coverage`由round706的72.8%推進至**79.59%**
（`stmt_codes_complete`1536/1930，`calls_last_hour=386`），`px_code_
coverage`仍**0.1%**（`px_codes_complete`2/1930，原因已如上定性為「按
設計尚未輪到」，非異常），`eta_local=2026-10-04T00:55`，仍未達可續做
`先.十一-二`§5門檻，未解除；`金流一.4``sector_flow.json`
`trading_days_available`仍**19**、`windows_missing_days.20`仍**1**，
`generated_at`仍`2026-10-03T00:23:57`（週六無新批次），未解除；`先.七
-一`／`先.六-四`（Shioaji）：下一交易日2026-10-05週一，本輪（週六）
結構上不可能驗證，未解除；`先.九-五`派發延遲樣本仍1/3（僅10/2一筆，
等10/5、10/6），週六無新run，未解除；`外部一改.2`／`研究.c`tick累積
依2026-09-15總司令裁示「累積到20或gate50裁示下來才需要回報，中途不
用」，本輪不重複讀取進度；其餘13條（`本地AI摘要(Breeze-7B)`／`維運.
先.六-二後續一`／`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`等）皆待
總司令/Cowork裁示或親自操作，與round706一致，未解除。`grep -c "凍結.
二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告
解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），凍結.二
期間暫停補件，不硬湊alpha試驗候選。**逐一核對凍結.二允許的四類工作
現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取
（`資料.一`已完成300/300，`先.十一-二`財報預熱為既有排程被動累積，
本輪僅讀取核對）；工具修正——本輪僅讀取`finmind_warmup.py`原始碼
確認設計意圖，未修改任何原始碼；`git status --short -- research/
backtest/ research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未
commit編輯，本輪亦未touch）。US軌本身`US_LEADS.md`/`STRATEGY_
GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且凍結.二期間
本來就不得登記新alpha試驗。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`is_holdout_consumed()`未重查（非本輪動作範圍，round701已核對為
True，條件不變）。`AWAITING_REVIEW.md`以python精確解析表格（排除
表頭與分隔列）得資料列**44**，與檔案標題「等待中（目前：44件）」
一致，無需更正（round706曾記錄55件，期間互動視窗已完成審閱若干項，
回落至44，屬正常消化，非漏更新）。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱72.8%→79.59%；**本輪主要產出是解答
round704遺留的px_code_coverage停滯疑問，確認為「財報先、價格後」的
刻意設計而非程式缺陷，避免了誤判為bug而進行不必要的修改**；US軌
本身查無可推進的新alpha試驗工作單位；今日仍為週六無開盤，多數時效性
阻塞結構上不可能在本輪解除——依`CLAUDE.md`「零之一」白名單第7條精神
記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰
十三節限定檔案、不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼。
全程新增外部呼叫僅限讀取性質驗證（`research/finmind_warmup.py
--status`讀取既有快取狀態、`run_detached.py status`、`trial_registry.py
--check`、既有`.json`/`.md`帳本檔案讀取），未讀取或輸出任何金鑰／
憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌
（round705=10-03 06:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新
交辦、先.十一-二/先.十二-三財報預熱`stmt_code_coverage`是否已達可
續做門檻（eta約10/4 00:55）、`金流一.4`20日視窗是否已補到0（週一10/5
開盤後才可能）、`先.七-一`/`先.九-五`是否已到10/5開盤可驗證。凍結.二
在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第707
輪心跳、`PENDING_QUEUE.md`「金流一.4」「先.十一-二」「先.十二-三」
相關條目、`research/AWAITING_REVIEW.md`。
