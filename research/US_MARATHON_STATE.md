# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---

**最後更新：2026-10-02T23:3x+08:00（馬拉松第698輪，US軌，維運帽）**——取鎖
乾淨（cycle`20261002-233037`）。三軌時間戳（開工前）：US round695=10-02
20:3x（最舊，本輪選定）／FUT round696=10-02 21:3x／TW round697=10-02
22:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round695~697持平）；`grep -c "^- \[!\]"`=21（持平）。

**housekeeping（[自行裁量]，非交辦，屬馬拉松維運帽日常工作）**：
`US_MARATHON_STATE.md`累積到5個條目（round683/686/689/692/695），超過
規則要求的「只保留最新3則」，已將最舊的683／686／689三則原文搬到
`US_STATE_ARCHIVE.md`（append-only，依既有慣例保持時間順序：先683後
686後689），本檔只留692／695／本輪698。純檔案維護，未變動任何判定
內容。

逐一核對21條`- [!]`阻塞項（與round697一致，本輪重複驗證+2項新查證，
未發現新解除）：`金流一.4` `sector_flow.json` `meta.trading_days_
available`仍**18**、`windows_missing_days.20`仍**2**，未解除——**新查
到一個細節**：`data/institutional_history.json`原始`dates`陣列其實已有
**23筆、最新到20261001**（與round697查詢時的認知一致，此為10/2凌晨
01:08 UTC「美股班次」commit`4cb4e95cb`順帶補上的，非本輪新增），但
`sector_flow.json`的`_solid_dates()`品質篩選仍判定可用天數停在18（即
20261001被篩掉，可能是三大法人覆蓋率不足，非程式錯誤，與`known_gaps`
欄位既有說明一致），**20日視窗的卡關不是「沒抓到10/1資料」，是「抓到
但品質篩選沒放行」，這是比round697認知更精確一層的子結論，不影響
BLOCKED狀態與既有解除條件**。`外部一改.2`／`研究.c`tick累積`ls
research/data/ticks/*.parquet`實測仍**15/20**，未解除。`本地AI摘要
(Breeze-7B)`仍待總司令四選一，未解除。`market.yml`今日(10/2)台股主/
補救班次（09:13/10:41 UTC）：本輪查詢時間15:3x UTC（23:3x台北），`gh
run list --workflow=market.yml`實測仍只有1筆run（`36949207832`，
2026-10-02T01:05:01Z，前一天美股班次延遲落地），**尚未到round696/697
訂的17:49 UTC升級判斷時間點（還差約2小時16分）**，沿用既定分支不升級，
留給下一輪。`紙.一`／`先.七-二`仍待該批次落地才能inception，未解除。
`先.七-一`／`先.六-四`（Shioaji）：`data/quotes_sinopac.json`10/2收盤
快照仍`connected:false`、`checked_at`=13:45:02（收盤檢查點），
`research/.live_state_sinopac.json`mtime仍停09-30 13:45（10/1、10/2
兩個交易日皆未更新），與round697結論一致，未解除。

**本輪新增診斷（針對round697留下的未解之問「本機網路為何連續3天在
類似長窗口異常、晚間自行恢復」，只讀查，不碰凍結區）**：①Windows
`System`事件記錄檔篩選WLAN-AutoConfig／RST Middleware／Kernel-Boot
相關事件，**最近一筆是9/24與9/16，與本輪關注的10/1～10/2異常窗口
（00:02~23:57）完全不重疊**，排除「本機重開機/網卡重啟」這個假設。
②`tailscale status`查詢當下（23:3x台北，已在異常窗口外）顯示連線
正常、`alpha-pc`為online狀態、Funnel仍開啟，`Get-NetAdapter`顯示
Ethernet與Tailscale Tunnel皆`Up`，**當下沒有異常可供比對**（異常窗口
是日間特定時段，本輪查詢時已過了恢復時間）。**誠實結論：本輪嘗試
但沒有查到新線索**，排除了「重開機」這個假設，但真正根因（本機
DNS/網路堆疊在白天特定長窗口異常、晚間自癒）仍待下一輪在異常窗口
內（例如明天上午）即時查`Get-NetTCPConnection`／`ipconfig /displaydns`
或總司令檢查路由器/ISP側紀錄，超出本輪所能做的範圍。

`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），
凍結.二期間暫停補件。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300）；
工具修正本輪未改動任何原始碼（僅讀取診斷＋archive舊state條目）；
`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定清單內檔案無殘留未commit編輯，本輪亦未touch）。US軌本身
`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，
`CALIBRATION_PROBE.md`唯一指名給US軌的操作指令（#47/#52重跑）先前
輪次已複核確認2026-09-04早已結案、無殘留，無清楚剩餘的全新機制候選，
且凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py
status`running=0（162筆歷史，無job待收成）；`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（409列，另有FDR對照表
33列，最大編號#407，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：39件）」，逐行核對（精確計算表格
資料列=39，排除表頭與分隔列）與round696/697一致，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；21條`- [!]`逐一核對均未到解除時間（`金流一.4`得到一層
更精確的子結論——卡關原因是品質篩選而非資料缺失，但不改變BLOCKED
狀態）；針對round697留下的網路異常根因未解之問做了一次新嘗試（排除
重開機假設），未查到決定性新線索；US軌本身查無可推進的新alpha試驗
工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
十三節限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證
（`gh run list`查既有workflow紀錄、`tailscale status`、
`Get-WinEvent`／`Get-NetAdapter`查本機系統狀態），無資料抓取類API
呼叫，未讀取或輸出任何金鑰／憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪
已append一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：39件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選FUT軌（round696=10-02 21:3x，三軌中最舊）；開工前先重新
檢查`- [ ]`有無新交辦、`market.yml`今日09:13/10:41 UTC批次是否已過
17:49 UTC上限仍缺席（若是則依round696既定分支升級為「需總司令手動
Run workflow」）、`金流一.4`／`外部一改.2`tick累積進度、`先.七-一`
是否已到10/5下一交易日可累積新樣本。凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除。完整見`REPORT.md`第698輪心跳、
`PENDING_QUEUE.md`「金流一.4」「先.七-一」「維運.market.yml」相關
條目、`research/AWAITING_REVIEW.md`。

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
