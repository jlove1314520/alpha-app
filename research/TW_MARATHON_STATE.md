# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

---
**最後更新：2026-10-03T07:3x+08:00（馬拉松第706輪，TW軌，維運帽）**——
取鎖乾淨（cycle`20261003-073037`）。三軌時間戳（開工前）：TW round703=
10-03 04:3x（最舊，本輪選定）／US round704=10-03 05:3x／FUT round705=
10-03 06:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未
開始交辦項，與round704~705持平）；`grep -c "^- \[!\]"`=19（持平）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除）：`金流一.4``sector_flow.json`
`trading_days_available`仍**19**、`windows_missing_days.20`仍**1**、
`generated_at`仍`2026-10-03T00:23:57`（週六無新批次），未解除；`先.十一
-二`／`先.十二-三`FinMind財報預熱：`finmind_warmup.py --status`實測
`stmt_code_coverage`由round705的67.41%推進至**72.8%**
（`stmt_codes_complete`1405/1930），`px_code_coverage`仍**0.1%**
（`px_codes_complete`2/1930，連三輪停滯，與round704/705發現一致），
`calls_last_hour=153`、`eta_local=2026-10-04T00:51`，仍未達可續做
`先.十一-二`§5門檻，未解除；`先.七-一`／`先.六-四`（Shioaji）：下一
交易日2026-10-05週一，本輪（週六）結構上不可能驗證，未解除；`先.九-
五`派發延遲樣本仍1/3（僅10/2一筆，等10/5、10/6），週六無新run，未
解除；`外部一改.2`／`研究.c`tick累積依2026-09-15總司令裁示「累積到
20或gate50裁示下來才需要回報，中途不用」，本輪不重複讀取進度；其餘
13條（`本地AI摘要(Breeze-7B)`／`維運.先.六-二後續一`／`資料源.外銷
訂單彙總`／`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`／`結案.一`／
`常備.9`／`群益API(合併)`等）皆待總司令/Cowork裁示或親自操作，與
round705一致，未解除。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗
候選。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前
輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300，`先.十一-二`
財報預熱為既有排程被動累積，本輪僅讀取核對）；工具修正本輪未修改任何
原始碼（僅讀取診斷＋補寫`PENDING_QUEUE.md`「結案.一」條目補充證據＋
archive round697舊state條目至`TW_STATE_ARCHIVE.md`，兩者皆為狀態/文件
檔，不在十三節限定清單內）；`git status --short -- research/backtest/
research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未
commit編輯，本輪亦未touch）。TW軌本身`TW_LEADS.md`/`STRATEGY_
GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且凍結.二期間
本來就不得登記新alpha試驗。

**本輪額外發現（純讀查、支持既有`結案.一`修法必要性，不影響任何判定
結論，詳見`PENDING_QUEUE.md`「結案.一」條目本輪補記）**：追查
round697引用的`external_connectivity.jsonl`10/2數字（272筆中218筆
False）時，發現這批原始資料**在git歷史裡完全不存在**——`git log
--all`逐一核對round701/703前後commit（含`41d062542 On main:
autostash`這個merge commit的兩個parent）對10/2這一天的筆數皆為**0**，
10/1與10/3皆有正常筆數，只有10/2整天缺。型態吻合「結案.一」要解決的
git stash/rebase衝突導致未commit的append遺失，是一個具體已發生案例。
**不影響`先.十二-二`已有的根因結論**（該結論已由總司令/互動視窗另外
查明是iPhone熱點斷線所致，證據鏈完整，不依賴這份已遺失的原始日誌）。
未修改`external_connectivity.jsonl`或任何原始碼。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`未重查（非本輪動作範圍，
round701已核對為True，條件不變）。`AWAITING_REVIEW.md`「等待中（目前：
55件）」，逐行核對（排除表頭/分隔列）與55筆資料列一致，較round704/705
的44件增加11件（互動視窗本輪期間新增的項目，非馬拉松動作）。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱67.41%→72.8%（`px_code_coverage`連三輪
停滯於0.1%）；TW軌本身查無可推進的新alpha試驗工作單位；本輪額外找到
一筆支持`結案.一`修法必要性的具體證據（10/2連線日誌於git歷史遺失），
已記錄供總司令參考、不影響既有BLOCKED狀態——依`CLAUDE.md`「零之一」
白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新
alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證（`research/
finmind_warmup.py --status`讀取既有快取狀態、`run_detached.py
status`、`trial_registry.py --check`、既有`.json`/`.md`帳本檔案讀取、
`git log`/`git show`查既有commit歷史），未讀取或輸出任何金鑰／憑證
內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩0條
`- [ ]`未開始**。**等待審閱：55件**（與`AWAITING_REVIEW.md`表格列數
一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round704=10-03
05:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、先.十一-二/
先.十二-三財報預熱`stmt_code_coverage`是否已達可續做門檻（eta約10/4
00:51）、`px_code_coverage`是否開始推進、`金流一.4`20日視窗是否已補到
0（週一10/5開盤後才可能）、`先.七-一`/`先.九-五`是否已到10/5開盤可
驗證。凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見
`REPORT.md`第706輪心跳、`PENDING_QUEUE.md`「結案.一」「先.十一-二」
「先.十二-三」相關條目、`research/AWAITING_REVIEW.md`。
