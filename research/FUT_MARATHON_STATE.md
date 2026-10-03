# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-10-03T03:3x+08:00（馬拉松第702輪，FUT軌，維運帽）**——
取鎖乾淨（cycle`20261003-033037`）。三軌時間戳（開工前）：FUT round699=
10-03 00:3x（最舊，本輪選定）／TW round700=10-03 01:3x／US round701=
10-03 02:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（先.十二
一/二已由互動視窗標`[x]`結案，無新交辦）；`grep -c "^- \[!\]"`=19（與
round701持平）。

逐一核對19條`- [!]`阻塞項（**本輪為週六凌晨，台股/美股/期貨皆無交易，
多數時效性條件結構上不可能本輪解除**）：
1. **`金流一.4`**：`data/sector_flow.json` `generated_at`仍
   `2026-10-03T00:23:57`（週六無新交易日），`trading_days_available`
   仍**19**、`windows_missing_days.20`仍**1**，未解除。
2. **`先.十一-二`／`先.十二-三`（FinMind財報預熱）**：`finmind_warmup.py
   --status`實測`stmt_code_coverage`由round701的34.09%升至**48.6%**
   （`stmt_codes_complete`938/1930），`px_code_coverage`仍0.1%，
   `calls_last_hour`439（<450上限，節流正常運作），`eta_local`
   **2026-10-04T00:25**——量化進度前進，**未解除**。
3. **`先.七-一`／`先.六-四`（Shioaji）**：下一交易日2026-10-05週一，
   本輪（週六）結構上不可能驗證，未解除，不重複讀取既有診斷。
4. **`先.九-五`（派發延遲）**：尚缺10/5、10/6兩個交易日樣本，週六無
   新run，未解除。
5. **`外部一改.2`／`研究.c`（tick累積）**：依2026-09-15總司令裁示
   「累積到20或gate50裁示下來才需要回報，中途不用」，本輪不重複
   讀取進度。
6. 其餘13條（`本地AI摘要(Breeze-7B)`／`維運.先.六-二後續一`／
   `資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／`稽核.三`／
   `稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`等）皆待總司令/
   Cowork裁示或親自操作，與round701一致，未解除。

`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述
提及、非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0，
<12下限，但凍結.二期間暫停補件，不硬湊alpha試驗候選。**逐一核對
凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部
完成並登記；資料抓取（`資料.一`已完成300/300，`先.十一-二`財報預熱
為既有排程被動累積，本輪僅讀取核對）；工具修正——本輪未修改任何
原始碼；`git status --short -- research/backtest/ research/
validation/ research/adjust.py research/pit.py research/
trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯，本輪亦未touch）。FUT軌本身`FUT_LEADS.md`/`STRATEGY_
GRAVEYARD.md`結案狀態未變，凍結.二期間本來就不得登記新alpha試驗。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪
動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：44件）」，
逐行核對（排除表頭/分隔列，實際46行-2=44）與標題數字一致，本輪未
變動。

**本輪誠實結論**：交辦佇列`- [ ]`=0；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對，**週六無交易日，結構上多數條件本輪
不可能解除**；僅財報預熱覆蓋率量化前進（34.09%→48.6%，仍未達可續做
`先.十一-二`§5的門檻）；FUT軌本身查無可推進的新alpha試驗工作單位——
依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、
不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證（既有`.json`/
`.md`帳本檔案讀取、`git status`/`git log`、`run_detached.py status`、
`trial_registry.py --check`、`holdout.py`、`finmind_warmup.py
--status`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選TW軌
（round700=10-03 01:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無
新交辦、`金流一.4`20日視窗是否已補到0（週一10/5開盤後才可能）、
`先.十一-二`財報預熱覆蓋率是否已達可續做門檻（eta約10/4 00:25）、
`先.七-一`是否已到10/5開盤可驗證。凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除。完整見`REPORT.md`第702輪心跳、
`PENDING_QUEUE.md`「金流一.4」「先.十一-二」「先.十二」相關條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T06:3x+08:00（馬拉松第705輪，FUT軌，維運帽）**——取鎖
乾淨（cycle`20261003-063037`）。三軌時間戳（開工前）：FUT round702=10-03
03:3x（最舊，本輪選定）／TW round703=10-03 04:3x／US round704=10-03
05:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round703~704持平）；`grep -c "^- \[!\]"`=19（持平）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除，本輪對有量化進度可能性的條目重新
實測，其餘沿用round704既定結論不重複贅述）：`先.十一-二`／`先.十二-三`
FinMind財報預熱：`finmind_warmup.py --status`實測`stmt_code_coverage`
已由round704的61.09%推進至**67.41%**（`stmt_codes_complete`1301/1930，
`calls_last_hour=367`，`eta_local=2026-10-04T00:36`）；`px_code_
coverage`仍**0.1%**（`px_codes_complete`2/1930，與round704一致，持續
停滯，round704已如實記錄此觀察，本輪重複驗證確認非單輪異常而是持續
現象），未達門檻，未解除；`金流一.4``sector_flow.json`
`trading_days_available`仍**19**、`windows_missing_days.20`仍**1**，
`generated_at`仍`2026-10-03T00:23:57`（週六無新批次），未解除；`外部
一改.2`／`研究.c`tick累積`ls research/data/ticks/*.parquet`實測仍
**15/20**（週末無盤中tick可累積，依2026-09-15總司令裁示本輪不重複
贅述進度細節），未解除；`先.七-一`／`先.六-四`Shioaji：
`data/quotes_sinopac.json`仍`connected:false`、`market_status:closed`、
`fetched_at`停在2026-10-02T08:31（週六無交易，下一交易日2026-10-05
週一，結構上不可能在本輪驗證），未解除；`先.九-五`派發延遲樣本仍1/3
（僅10/2一筆，等10/5、10/6），週六無新run，未解除；其餘13條（`本地
AI摘要(Breeze-7B)`／`維運.先.六-二後續一`／`資料源.外銷訂單彙總`／
`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／
`群益API(合併)`等）皆待總司令/Cowork裁示或親自操作，與round704一致，
未解除。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件
敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：
`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。
**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次
已全部完成並登記；資料抓取（`資料.一`已完成300/300，`先.十一-二`
財報預熱為既有排程被動累積，本輪僅讀取核對）；工具修正本輪未修改任何
原始碼（僅讀取診斷＋執行本節下方housekeeping，`FUT_MARATHON_STATE.md`/
`FUT_STATE_ARCHIVE.md`屬狀態檔不在十三節限定清單內）；`git status
--short -- research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯，本輪亦未touch）。FUT軌本身`FUT_LEADS.md`/
`STRATEGY_GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。

**housekeeping（[自行裁量]，非交辦，屬馬拉松維運帽日常工作）**：
`FUT_MARATHON_STATE.md`累積到4個條目（693/696/699/702），超過規則
要求的「只保留最新3則」，已將最舊的693原文搬到`FUT_STATE_ARCHIVE.md`
（append-only，接續既有時間順序）。本檔只留696／699／702／本輪705。
純檔案維護，未變動任何判定內容。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`holdout.py::is_holdout_consumed()`未重查（非本輪動作範圍，先前輪次
已核對為`True`，條件不變）。`AWAITING_REVIEW.md`「等待中（目前：44件）」，
逐行核對（46列扣表頭/分隔列2＝44）與表格列數一致，與round703/704
持平，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱61.09%→67.41%（`px_code_coverage`持續
停滯於0.1%，已連兩輪觀察到同一現象，記錄供後續判斷是否需要調整
warmup排程優先序，本輪未修改`finmind_warmup.py`原始碼）；FUT軌本身
查無可推進的新alpha試驗工作單位；**今日仍為週六無開盤，多數時效性
阻塞結構上不可能在本輪解除**——依`CLAUDE.md`「零之一」白名單第7條
精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不
搶碰十三節限定檔案、不代做互動視窗保留項目。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定清單內
任何原始碼。全程新增外部呼叫僅限讀取性質驗證（`research/
finmind_warmup.py --status`讀取既有快取狀態、`run_detached.py
status`、`trial_registry.py --check`、既有`.json`/`.md`帳本檔案
讀取），未讀取或輸出任何金鑰／憑證內容。`PROGRESS_HEARTBEAT.jsonl`
本輪已append一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：
44件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：
依輪替下一輪建議選TW軌（round703=10-03 04:3x，三軌中最舊）；開工前
先重新檢查`- [ ]`有無新交辦、先.十一-二/先.十二-三財報預熱`px_code_
coverage`是否開始推進、`stmt_code_coverage`是否已達完成門檻、`金流
一.4`20日視窗是否已補到0（週一10/5開盤後才可能）、`先.七-一`/`先.
九-五`是否已到10/5開盤可驗證。凍結.二在總司令/Cowork明確寫「凍結.二
解除」前不解除。完整見`REPORT.md`第705輪心跳、`PENDING_QUEUE.md`
「金流一.4」「先.十一-二」「先.十二-三」相關條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-03T09:3x+08:00（馬拉松第708輪，FUT軌，維運帽）**——
取鎖乾淨（cycle`20261003-093037`）。三軌時間戳（開工前）：FUT round705=
10-03 06:3x（最舊，本輪選定）／TW round706=10-03 07:3x／US round707=
10-03 08:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未
開始交辦項，與round706~707持平）；`grep -c "^- \[!\]"`=19（持平）。

逐一核對19條`- [!]`阻塞項（今日2026-10-03仍為週六，無新交易日資料，
多數條件結構上不可能在本輪解除，其餘沿用round707既定結論不重複
贅述）：`先.十一-二`／`先.十二-三`FinMind財報預熱：`finmind_warmup.py
--status`實測`stmt_code_coverage`由round707的79.59%推進至**89.43%**
（`stmt_codes_complete`1726/1930，`stmt_files_nonempty`4830/5790），
`px_code_coverage`仍**0.1%**（`px_codes_complete`2/1930，round707
已確認為「P2補缺：財報先、價格後」刻意循序設計，非bug，本輪不重複
查證），`calls_last_hour=316`、`eta_local=2026-10-04T00:33`，仍未達
可續做`先.十一-二`§5門檻（§5門檻依`先.十-二`原定目標為stmt/px兩項
覆蓋率皆≥98%，目前stmt 89.43%、px 0.1%，兩者皆未達標）；`金流一.4`
`sector_flow.json` `generated_at`仍`2026-10-03T08:48:44`（週六無新
交易日批次，較round705的`00:23:57`時間戳有更新但`trading_days_
available`仍**19**、`windows_missing_days.20`仍**1**，未解除）；
`先.七-一`／`先.六-四`（Shioaji）：`data/quotes_sinopac.json`仍
`connected:false`、`fetched_at`停在`2026-10-02T08:31`，下一交易日
2026-10-05週一，本輪（週六）結構上不可能驗證，未解除；`先.九-五`
派發延遲樣本仍1/3（`research/dispatch_delay_log.jsonl`仍2筆，即
10/2當天392.9／341.0分鐘，等10/5、10/6），週六無新run，未解除；
`外部一改.2`／`研究.c`tick累積依2026-09-15總司令裁示「累積到20或
gate50裁示下來才需要回報，中途不用」，本輪不重複讀取進度；其餘13條
（`本地AI摘要(Breeze-7B)`／`維運.先.六-二後續一`／`資料源.外銷訂單
彙總`／`重構.C4`／`資料源一.3`／`稽核.三`／`稽核.五`／`結案.一`／
`常備.9`／`群益API(合併)`等）皆待總司令/Cowork裁示或親自操作，與
round707一致，未解除。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗
候選。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前
輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300，`先.十一-二`
財報預熱為既有排程被動累積，本輪僅讀取核對）；工具修正本輪未修改任何
原始碼（僅讀取診斷＋archive round696/699舊state條目至`FUT_STATE_
ARCHIVE.md`，使本檔回到「只保留最新3則」規則，`FUT_MARATHON_STATE.md`/
`FUT_STATE_ARCHIVE.md`屬狀態檔不在十三節限定清單內）；`git status
--short -- research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單
內檔案無殘留未commit編輯，本輪亦未touch）。FUT軌本身`FUT_LEADS.md`/
`STRATEGY_GRAVEYARD.md`結案狀態未變，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。

驗證：`run_detached.py status`running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪
動作，僅讀取核對）。`AWAITING_REVIEW.md`以python精確解析表格（排除
表頭與分隔列，含表格中段一處非標準空白列）得資料列**44**，與檔案
標題「等待中（目前：44件）」一致，與round706/707持平，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；19條`- [!]`逐一核對均未到解除時間，唯一有量化進度的是
先.十一-二/先.十二-三財報預熱79.59%→89.43%（`px_code_coverage`仍
0.1%，確認為刻意設計非bug）；FUT軌本身查無可推進的新alpha試驗工作
單位；**本輪housekeeping**：`FUT_MARATHON_STATE.md`累積到4個條目
（696/699/702/705），超過規則要求的「只保留最新3則」，已將最舊的
696與699原文搬到`FUT_STATE_ARCHIVE.md`（append-only，接續既有時間
順序：693後696後699），本檔只留702／705／本輪708，純檔案維護未變動
任何判定內容——今日仍為週六無開盤，多數時效性阻塞結構上不可能在
本輪解除——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、
不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼。全程新增外部
呼叫僅限讀取性質驗證（`research/finmind_warmup.py --status`讀取
既有快取狀態、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`、既有`.json`/`.md`帳本檔案讀取），未讀取或輸出任何金鑰／
憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：44件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選TW軌（round706=
10-03 07:3x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新交辦、先.十一
-二/先.十二-三財報預熱`stmt_code_coverage`是否已達98%門檻、`金流
一.4`20日視窗是否已補到0（週一10/5開盤後才可能）、`先.七-一`/`先.九-
五`是否已到10/5開盤可驗證。凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除。完整見`REPORT.md`第708輪心跳、`PENDING_QUEUE.md`「金流
一.4」「先.十一-二」「先.十二-三」相關條目、
`research/AWAITING_REVIEW.md`。
