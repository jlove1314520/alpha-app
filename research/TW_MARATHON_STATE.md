# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-30T11:0x+08:00（馬拉松第685輪，維運帽）**——取鎖乾淨
（cycle`20260930-110037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，與round676~684持平，round684的
`先.三`四項子任務已由互動視窗結案並移入`AWAITING_REVIEW.md`）；
`grep -c "^- \[!\]"`=13（較round683/684持平，`先.二-三b`／`先.三-二`
FinMind封鎖已於round684確認解除並從清單移除）。逐一核對13條`- [!]`
阻塞項：`金流一.4`實測`institutional_history.json`raw`dates`仍21筆
（20260930盤中，今日尚未收盤不會有新一天資料）、`sector_flow.json`
`meta.trading_days_available`仍**17**、`windows_missing_days.20`仍**3**，
20日視窗仍差3個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測仍**14/20**，未解除；`本地AI摘要
(Breeze-7B)`四選一仍待總司令裁示，屬白名單第6條法遵疑慮，未解除；其餘
10條逐一核對開頭標記（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`／`研究.c`皆
等總司令/Cowork裁示或親自操作；`紙.一`需2026-10第一個交易日，今日仍
09-30），皆未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，
逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度
自檢**：`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。
三軌時間戳（比對各檔案內*最新*一則）：TW round682=09-30 08:0x（本輪
選定，三軌中最舊）／US round683=09-30 09:0x／FUT round684=09-30 10:0x。
**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已
全部完成並登記；資料抓取（`資料.一`已標`- [x]`完成300/300，`先.三`存活
者偏誤探測為互動視窗自行裁量的獨立工作，已結案待審，不代做）；工具
修正已由互動視窗commit（本輪`git log`最新5筆commit均為排程自動更新，
無互動視窗新commit）；`git status --short -- research/backtest/
research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案狀態未變，
`CALIBRATION_PROBE.md`給TW軌的操作指令（#77/#79/#91、
portfolio_multifactor_v2 300檔重跑）先前輪次已複核確認早已完成並登記，
本輪再核對`TRIALS_LEDGER.md`無新變化，無清楚剩餘的全新機制候選，且
凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py status`
running=0（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：27件）」，逐行核對
與27筆資料列一致，本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；
凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`逐一核對均未到
解除時間（`金流一.4`倒數仍差3個交易日、tick累積仍14/20、`本地AI摘要`
仍待總司令四選一裁示）；TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零
新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條`- [ ]`未開始**。**等待審閱：27件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round683=
09-30 09:0x，三軌中最舊，FUT剛在round684更新過）；開工前先重新檢查
`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已裁示、`金流一.4`
是否已隨當日排程更新走到20日視窗、`外部一改.2`tick累積14/20還差6日。
凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`
第685輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」
條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T14:0x+08:00（馬拉松第688輪，維運帽）**——取鎖乾淨
（cycle`20260930-140037`）。同round685~687的結論：`- [ ]`=0、`- [!]`=13，
逐一核對均未到解除時間（`金流一.4`仍差3個交易日；tick累積**15/20**，
較上次核對+1，仍差5日；FinMind`blocked_until`已過期但無現存阻塞項以此
為由；系統記憶體實測8.36GB遠高於3GB門檻，但無現存阻塞項以記憶體為由；
`本地AI摘要`仍待總司令四選一；`紙.一`明日(10/1)才到期）。凍結.二仍生效
（`凍結.二解除`grep=4，皆條件敘述非宣告）。凍結.二允許四類工作皆已完成
或無新內容，TW軌無新工作單位。詳見`REPORT.md`第688輪心跳。
**下一輪建議選US軌**（round686=09-30 12:0x，三軌中最舊）。

---
**最後更新：2026-10-01T20:0x+08:00（馬拉松第691輪，維運帽）**——取鎖乾淨
（cycle`20261001-200037`）。**注意：上一輪（round688）結束於09-30 14:0x，
距本輪隔了約30小時——查`research/data/quota_throttle_state.json`：
`marathon.daily.skip_signal=39/skip_interval=1/run=1`、
`consecutive_no_progress=2`，是額度節流機制正常運作（09-30 16:0x~10-01
19:xx這段`git log`滿版`Marathon cycle log 自動更新（節流跳過）`），不是
卡死，[自行裁量]不需額外處理，照常開工。三軌時間戳：TW round688=09-30
14:0x（本輪選定，三軌中最舊）／US round689=09-30 15:0x／FUT round690=
09-30 16:0x。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，與round679~690持平）；
`grep -c "^- \[!\]"`=13（持平）。逐一核對13條`- [!]`阻塞項：`金流一.4`
實測`data/sector_flow.json``meta.trading_days_available`**18**（較
round685~690的17＋1）、`windows_missing_days.20`**2**（較13↓1），20日
視窗還差2個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測仍**15/20**（與round688持平），
未解除；`本地AI摘要(Breeze-7B)`四選一仍待總司令裁示，屬白名單第6條法
遵疑慮，未解除；`紙.一`：今日已是2026-10-01（首個交易日），但
`data/paper_7030.json`仍`started:false`——`sector_flow.json`
`generated_at`=2026-10-01T08:42（晨間排程，處理的是前一交易日09-30收盤
資料，`date=20260930`），market.yml當日收盤後那一輪（處理10-01收盤價）
本輪查詢時間20:0x尚未見其commit寫入`data/price_history.json`含10-01
資料，紙.一的inception要等那一輪跑過，非馬拉松可代做，未解除；其餘9條
逐一核對開頭標記（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`皆等總司令/
Cowork裁示或親自操作；`研究.c`同金流一.4/外部一改.2共用的資料累積阻塞），
均未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆
為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：
`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。**逐一
核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成
並登記；資料抓取（`資料.一`已完成300/300）；工具修正已由互動視窗commit
（`git log`本輪查詢區間內唯一互動視窗commit為`deb160a8d`「先.四-二/三：
供給緊縮衛星策略單發執行完成，判定FAIL（#406），結案寫入墓園」，屬互動
視窗自行裁量工作非馬拉松代做範圍）；`git status --short --
research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單內
檔案無殘留未commit編輯）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`
結案狀態未變，`CALIBRATION_PROBE.md`給TW軌的操作指令（#77/#79/#91、
portfolio_multifactor_v2 300檔重跑）先前輪次已複核確認早已完成並登記，
無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新alpha試驗。驗證：
`run_detached.py status` running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（408列，另有FDR對照表33列，最大編號#406，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：28件）」（較round685~
690的27件＋1：新增`先.四`供給緊縮衛星策略結案條目，屬互動視窗本輪工作、
非馬拉松動作），逐行核對28筆資料列一致，本輪未變動。**本輪誠實結論**：
交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條
`- [!]`逐一核對均未到解除時間（`金流一.4`20日視窗差距由3縮為2，但仍未
解除；tick累積仍15/20；本地AI摘要仍待總司令四選一裁示；紙.一雖已到
2026-10-01但當日收盤資料尚未經market.yml寫入）；TW軌本身查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不
硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做
互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋
archive舊state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本
檔案、`git status`/`git log`、`run_detached.py status`、
`trial_registry.py --check`、`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：28件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選US軌（round689=09-30 15:0x，三軌中最舊）；開工前先重新檢查
`- [ ]`有無新交辦、`金流一.4`20日視窗是否已補到0（目前差2個交易日）、
`外部一改.2`tick累積15/20還差5日、`本地AI摘要(Breeze-7B)`四選一是否已
裁示、`紙.一`是否已有`data/paper_7030.json`的`started:true`紀錄。凍結.
二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`
第691輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」
「紙.一」條目、`research/AWAITING_REVIEW.md`。
