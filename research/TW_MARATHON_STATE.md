# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
---
**最後更新：2026-10-02T22:3x+08:00（馬拉松第697輪，TW軌，維運帽）**——取鎖
乾淨（cycle`20261002-223037`）。三軌時間戳（開工前）：TW round694=10-01
23:1x（最舊，本輪選定）／FUT round696=10-02 21:3x／US round695=10-02
20:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round694~696持平）；`grep -c "^- \[!\]"`=21（持平，round694的18
加round695/696新增的3條）。

**本輪實質產出：修正並收斂「先.七-一／先.六-四 Shioaji連線失敗」的根因
診斷**（詳見`PENDING_QUEUE.md`「先.七-一」條目下方本輪補記）：
1. 直接讀`shioaji.log`（Rust核心append-only log）確認：10/1、10/2兩個
   完整交易日**零次**成功連上（最後一次成功是09-30T00:31 UTC的
   `contracts_v2::traffic`backend response；之後兩天共約300次登入嘗試
   全部卡在「get site info」這一步，失敗點早於帳密/token驗證，**排除
   憑證／API key到期**這個假設方向）。
2. **更正round696（21:3x）對`external_connectivity.jsonl`的讀數**：
   round696稱「今天259筆全部`internet.ok=True`」，本輪用`results.
   internet.ok`欄位依`ts`前綴嚴格篩選2026-10-02重新逐筆核對兩次（結果
   一致）：**實際272筆中218筆`False`（80%）**，連續壞區間
   **00:02～18:07台北**（18:12起才轉全部`True`，正好銜接round695/696
   查詢時間20:3x/21:3x，round696看到的是已恢復後的尾段，不是全天）。
   往前核對：10/1同樣288筆中240筆`False`（83%，幾乎整天）；09-30則
   73/261筆`False`（28%，晚間才開始，範圍小得多）。壞區間`fail_streak`
   曾達106，`tailscale`同步壞，確認是本機對外連線真的有長時間異常，
   不只是round696說的「這支腳本沒測對網域」。
3. 這個異常窗口（00:02~18:07）完整覆蓋Shioaji盤中失敗時段（09:00~
   13:30台北），也完整覆蓋`維運.AlphaData三日DNS解析失敗`條目原本認定
   的「15:30窄窗口」——已在該條目下方補記交叉參照：15:30很可能只是
   落在這個更大異常窗口裡的一個點，不是獨立現象，但本輪未越權合併兩
   條目的判定、未碰`fetch.py`凍結區。
4. 先.七-一「失敗→依序查」三步執行結果：本機網路＝有異常（**由「已
   排除」改回「待查」**）；憑證/API key到期＝已排除（失敗點在site
   info之前）；永豐維護公告＝round696已三來源查無。**不更動先.七-一/
   先.六-四的BLOCKED狀態與既有解除條件**（仍等10/5樣本或總司令查永豐
   帳戶狀態），本輪只修正「網路已排除」這個子結論的事實依據，並留下
   「為何本機網路連續3天都在類似長窗口異常、晚間自行恢復」這個未解之
   問供總司令或下一輪查Windows事件記錄/排程/VPN設定。

逐一核對其餘`- [!]`阻塞項（與round696一致，本輪僅重複驗證，未發現
新解除）：`金流一.4``sector_flow.json``meta.trading_days_available`仍
**18**（因今日10/2台股主班次`market.yml`截至查詢時間14:31 UTC仍缺席，
尚未到round696訂的17:49 UTC升級判斷時間點，不重複升級，沿用既定分支）；
`外部一改.2`／`研究.c`tick累積`ls research/data/ticks/*.parquet`實測仍
**15/20**，未解除；`本地AI摘要(Breeze-7B)`仍待總司令四選一，未解除；
`紙.一`／`先.七-二`仍待market.yml含10/2收盤資料的那一輪落地，未解除。
`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），
凍結.二期間暫停補件。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300）；
工具修正本輪未改動任何原始碼（僅讀取診斷＋補寫`PENDING_QUEUE.md`狀態
記錄，`TW_MARATHON_STATE.md`/`TW_STATE_ARCHIVE.md`屬狀態檔不在十三節
限定清單內）；`git status --short -- research/backtest/ research/
validation/ research/adjust.py research/pit.py research/
trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit編輯，
本輪亦未touch）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案
狀態未變，無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新
alpha試驗。驗證：`run_detached.py status`running=0（162筆歷史，無job
待收成）；`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：39件）」，與round696
一致，本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的
四類工作皆已完成或無新內容；21條`- [!]`逐一核對均未到解除時間；TW軌
本身查無可推進的新alpha試驗工作單位；**本輪實質產出是Shioaji連線失敗
根因診斷的重大修正（網路排除結論被推翻，改為待查，並發現與AlphaData
DNS失敗條目可能同根因），已完整記錄進`PENDING_QUEUE.md`「先.七-一」與
「維運.AlphaData三日DNS解析失敗」兩個條目，未自行執行任何修復動作或
更動BLOCKED狀態**——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束
本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定
檔案。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
十三節限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證
（`requests.get()`即時重測兩個site-info網址、`gh run list`查
market.yml既有紀錄），無資料抓取類API呼叫，未讀取或輸出任何金鑰／
憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：39件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round695=
10-02 20:3x，三軌中最舊，須下一輪開工時重新比對三軌實際時間戳）；
開工前先重新檢查`- [ ]`有無新交辦、`market.yml`今日17:00台北班次是否
已過17:49 UTC上限仍缺席（若是則依round696既定分支升級判斷）、`金流
一.4`／`外部一改.2`tick累積進度、`先.七-一`根因是否有新線索（本機網路
連續3天異常窗口的成因）。凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除。完整見`REPORT.md`第697輪心跳、`PENDING_QUEUE.md`「先.七-一」
「維運.AlphaData三日DNS解析失敗」「金流一.4」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T01:3x+08:00（馬拉松第700輪，TW軌，維運帽）**——取鎖
乾淨（cycle`20261003-013037`）。三軌時間戳（開工前）：TW round697=10-02
22:3x（最舊，本輪選定）／US round698=10-02 23:3x／FUT round699=10-03
00:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項；round699的2條`- [ ]`先.十二-一/二已由互動視窗完成並移出，非本輪
代做）；`grep -c "^- \[!\]"`=19（較round699的21減2，同樣對應先.十二-
一/二結案移除）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03為週六，無新交易日資料，多數
條件結構上不可能在本輪解除）：`金流一.4``data/sector_flow.json`
`meta.trading_days_available`仍**19**、`windows_missing_days.20`仍
**1**（`generated_at`=10-03T00:23，較round697的18已前進1，但仍差1個
交易日，下一個交易日為2026-10-05週一），未解除；`先.九-五`派發延遲
樣本：`research/dispatch_delay_log.jsonl`已有10/2兩筆（392.9／341.0
分鐘），仍差10/5、10/6，進度1/3不變，未解除；`先.七-一`／`先.六-四`
Shioaji：今日週六無開盤，仍等10/5週一09:00台北開盤，未解除；`外部
一改.2`／`研究.c`tick累積`ls research/data/ticks/*.parquet`實測仍
**15/20**（週末無盤中tick可累積），未解除；`先.十一-二`／`先.十二-三`
FinMind財報預熱：`PYTHONIOENCODING=utf-8 python research/
finmind_warmup.py --status`實測`stmt_code_coverage`已由round699的
23.68%推進至**34.09%**（658/1930完整）、`eta_local`仍約
2026-10-04T00:17，未達門檻，未解除；`本地AI摘要(Breeze-7B)`仍卡在
法遵疑慮（法說會PDF來源`doc.twse.com.tw`robots.txt全站disallow，
round699之前已查證，本輪未重查），未解除；`紙.一`仍為每月末寫一筆的
長週期心跳，本月尚未到月末，未解除；其餘`資料源.外銷訂單彙總`／
`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／
`群益API(合併)`／`維運.先.六-二後續一`皆為等總司令/Cowork裁示或親自
操作，均未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗
候選。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前
輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300）；工具修正
本輪未修改任何原始碼（僅讀取診斷＋改狀態檔／archive舊state條目，
`TW_MARATHON_STATE.md`/`TW_STATE_ARCHIVE.md`屬狀態檔不在十三節限定
清單內）；`git status --short -- research/backtest/ research/
validation/ research/adjust.py research/pit.py research/
trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit編輯，
本輪亦未touch）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案
狀態未變，無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新
alpha試驗。驗證：`run_detached.py status`running=0（162筆歷史，無job
待收成）；`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪
動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：44件）」，
逐行核對（排除表頭/分隔列，46列扣2＝44）與表格列數一致，本輪未變動
（round697的39件＋5：互動視窗本輪期間新增的`先.十.四`等條目，非馬拉松
動作）。**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作
皆已完成或無新內容；19條`- [!]`逐一核對均未到解除時間，其中2項有
量化進度推進（金流一.4的`generated_at`已更新但視窗計數不變、先.十一-
二財報預熱23.68%→34.09%）；TW軌本身查無可推進的新alpha試驗工作單位；
**今日為週六無開盤，多數時效性阻塞結構上不可能在本輪解除**——依
`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不
觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗
保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改十三節限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證
（`research/finmind_warmup.py --status`讀取既有快取狀態、`run_
detached.py status`、`trial_registry.py --check`、`holdout.py`、既有
`.json`/`.md`帳本檔案讀取），未讀取或輸出任何金鑰／憑證內容。`PROGRESS_
HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩0條`- [ ]`未開始**。
**等待審閱：44件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪
任一軌接手**：依輪替下一輪建議選US軌（round698=10-02 23:3x，三軌中
最舊）；開工前先重新檢查`- [ ]`有無新交辦、`金流一.4`20日視窗是否已
補到0（下一個交易日2026-10-05）、`先.七-一`/`先.九-五`是否已到10/5
開盤可驗證、`先.十一-二`/`先.十二-三`財報預熱是否已達門檻（eta約
10/4 00:17）。凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。
完整見`REPORT.md`第700輪心跳、`PENDING_QUEUE.md`「金流一.4」「先.九-
五」「先.十一-二」「先.十二-三」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T04:3x+08:00（馬拉松第703輪，TW軌，維運帽）**——取鎖
乾淨（cycle`20261003-043037`）。三軌時間戳（開工前）：TW round700=10-03
01:3x（最舊，本輪選定）／US round701=10-03 02:3x／FUT round702=10-03
03:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round701~702持平）；`grep -c "^- \[!\]"`=19（持平）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除，本輪僅對有量化進度可能性的條目重新
實測，其餘沿用round702既定結論不重複贅述）：`金流一.4``data/
sector_flow.json``generated_at`仍`2026-10-03T00:23:57`（週六無新批次，
與round702一致）、`trading_days_available`仍**19**、`windows_missing_
days.20`仍**1**，未解除；`先.十一-二`／`先.十二-三`FinMind財報預熱：
`finmind_warmup.py --status`實測`stmt_code_coverage`已由round702的
48.6%推進至**53.26%**（`stmt_codes_complete`1028/1930，`calls_last_
hour`360，`eta_local`2026-10-04T00:35），量化進度前進但仍未達可續做
`先.十一-二`§5門檻，未解除；`先.七-一`／`先.六-四`（Shioaji）：下一
交易日2026-10-05週一，本輪（週六）結構上不可能驗證，未解除；`先.九-
五`派發延遲樣本仍1/3（僅10/2一筆，等10/5、10/6），週六無新run，未
解除；`外部一改.2`／`研究.c`tick累積依2026-09-15總司令裁示「累積到
20或gate50裁示下來才需要回報，中途不用」，本輪不重複讀取進度；其餘
13條（`本地AI摘要(Breeze-7B)`／`維運.先.六-二後續一`／`資料源.外銷
訂單彙總`／`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`／`結案.一`／
`常備.9`／`群益API(合併)`等）皆待總司令/Cowork裁示或親自操作，與
round702一致，未解除。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗
候選。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前
輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300，`先.十一-二`
財報預熱為既有排程被動累積，本輪僅讀取核對）；工具修正本輪未修改任何
原始碼（僅讀取診斷＋改狀態檔／archive舊state條目`round694`至
`TW_STATE_ARCHIVE.md`，`TW_MARATHON_STATE.md`/`TW_STATE_ARCHIVE.md`
屬狀態檔不在十三節限定清單內）；`git status --short --
research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯，本輪亦未touch）。TW軌本身`TW_LEADS.md`/
`STRATEGY_GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py
status`running=0（162筆歷史，無job待收成）；`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（409列，另有FDR對照表
33列，最大編號#407，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：44件）」，逐行核對與44筆資料列
一致，與round700/702持平，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱48.6%→53.26%；TW軌本身查無可推進的新
alpha試驗工作單位；**今日仍為週六無開盤，多數時效性阻塞結構上不可能
在本輪解除**——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束
本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定
檔案、不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼。全程新增外部
呼叫僅限讀取性質驗證（`research/finmind_warmup.py --status`讀取既有
快取狀態、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`、既有`.json`/`.md`帳本檔案讀取），未讀取或輸出任何金鑰／
憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round701=
10-03 02:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、
`先.十一-二`/`先.十二-三`財報預熱覆蓋率是否已達可續做門檻（eta約
10/4 00:35）、`金流一.4`20日視窗是否已補到0（週一10/5開盤後才可能）、
`先.七-一`/`先.九-五`是否已到10/5開盤可驗證。凍結.二在總司令/Cowork
明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第703輪心跳、
`PENDING_QUEUE.md`「金流一.4」「先.十一-二」「先.十二-三」相關條目、
`research/AWAITING_REVIEW.md`。
