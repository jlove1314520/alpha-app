# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-30T05:0x+08:00（馬拉松第679輪，維運帽）**——取鎖乾淨
（cycle`20260930-050037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，round675~678記錄的`修.八`／
`價值成長榜恢復`／`先.一`三條互動視窗保留項目本輪核對仍不在`- [ ]`清單），
`grep -c "^- \[!\]"`=13（與round676~678持平）。逐一核對13條`- [!]`阻塞項：
`金流一.4`實測`data/institutional_history.json`原始`dates`陣列已從20→
**21筆**（新增20260930一天），但`_solid_dates()`過濾覆蓋率的倒數仍以
`data/sector_flow.json`最後一次自動更新（`git log`確認為2026-09-29T16:38
UTC＝台北00:38，早於本輪查詢時間）為準，尚未反映新增這一天，PENDING_QUEUE.md
6838行仍**17個交易日**、20日視窗仍差3個交易日，未解除；`外部一改.2`／
`研究.c`共用tick累積`ls research/data/ticks/*.parquet`實測仍**14/20**，
未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源裁示分支仍待總司令
選一，未解除；其餘10條逐一核對開頭標記，均為等總司令/Cowork裁示或其他
外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，今日仍09-30）。
`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限）但
凍結.二期間暫停補件，不硬湊alpha試驗候選。三軌時間戳（依「最久沒被碰」
規則，實際比對各檔案內*最新*一則的時間戳，非機械取檔案內最後一段文字）：
TW round676=09-30 02:0x（本輪選定，三軌中最舊）／US round677=09-30
03:0x／FUT round678=09-30 04:0x。**逐一核對凍結.二允許的四類工作現況**：
稽核重跑／驗.二重跑（`驗.二續`／`驗.二第二部分`皆`- [x]`）先前輪次已全部
完成並登記；資料抓取（`資料.一`已標`- [x]`完成300/300、`閘門.一`同前）；
工具修正已由互動視窗commit；`git status --short -- research/backtest/
research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit
編輯）。TW軌本身無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新
alpha試驗。驗證：`run_detached.py status` running=0（162筆歷史，無job待
收成）；`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（406列，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：25件）」，逐行核對25筆資料列一致，
本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類
工作皆已完成或無新內容；13條`- [!]`逐一核對均未到解除時間（`金流一.4`
原始日期陣列雖已多1天但尚未走完當日排程更新流程、實質倒數仍差3個交易日、
tick累積仍14/20、`本地AI摘要`仍待總司令四選一裁示）；TW軌本身查無可推進
的新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做
互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結
區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊
state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`、`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。
**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：25件**（與
`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替下一輪
建議選US軌（round677=09-30 03:0x，三軌中最舊，FUT剛在round678更新過）；
開工前先重新檢查`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已
裁示、`金流一.4`是否已隨當日排程更新走到20日視窗（原始陣列已21筆，留意
下次`sector_flow.json`自動更新後倒數可能提前解除）、`外部一改.2`tick
累積14/20還差6日；凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。
完整見`REPORT.md`第679輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI
摘要(Breeze-7B)」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-30T02:0x+08:00（馬拉松第676輪，維運帽）**——取鎖乾淨
（cycle`20260930-020037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項——round675記錄的3條`修.八`／
`價值成長榜恢復`／`先.一`皆明文標「互動視窗執行」，本輪核對已全數不在
`- [ ]`清單，交由互動視窗自行收工，非馬拉松代勞），`grep -c "^- \[!\]"`=13
（較round674的14條−1：`驗.九`已於前一輪確認由互動視窗22:50完成並改列
`- [x]`＋移入`AWAITING_REVIEW.md`，本輪核對PENDING_QUEUE.md 16772行
確認`- [x]`狀態維持）。逐一核對13條`- [!]`阻塞項：`金流一.4`（讀
`build_sector_flow.py::_solid_dates()`自動維護的倒數行，非raw陣列長度）
仍**17個交易日**（20260901~20260929），20日視窗仍差3個交易日，未解除；
`外部一改.2`／`研究.c`共用tick累積`ls research/data/ticks/*.parquet`
實測仍**14/20**，未解除；`本地AI摘要(Breeze-7B)`——DevQueue上一輪
（cycle`20260930-011601`）已完成Ollama安裝後的合成輸入推論smoke test
驗證，但(a)/(b)/(c)/(d)資料來源裁示分支仍待總司令選一個，屬白名單第6條
法遵疑慮，本輪核對仍`- [!]`未解除，不代為決定；其餘10條逐一核對開頭
標記，均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間（`紙.一`
需等2026-10第一個交易日，今日仍09-30）。`grep -c "凍結.二解除"
PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際宣告解除，凍結.二
仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限）但凍結.二期間暫停補件，
不硬湊alpha試驗候選。三軌時間戳：TW round672=09-29 21:0x（本輪選定，
三軌中最舊）／FUT round675=09-30 01:0x／US round674=09-29 23:0x。
驗證：`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定檔案無殘留未commit編輯）；`run_detached.py status`
`running=0`（162筆歷史，無job待收成）；`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪未新增判定）。
`AWAITING_REVIEW.md`「等待中（目前：25件）」，逐行核對與25筆資料列
一致（較round675的22件+3，來自互動視窗完成`修.八`／`價值成長榜恢復`／
`先.一`部分項目後移入等待審閱，非本輪動作）。**本輪誠實結論**：交辦
佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條`- [!]`
逐一核對均未到解除時間（`金流一.4`仍差3個交易日、tick累積仍14/20、
`本地AI摘要`仍待總司令四選一裁示）；TW軌本身查無可推進的新工作單位
——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、
不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗
保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊
state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還
剩0條`- [ ]`未開始**。**等待審閱：25件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌
（round674=09-29 23:0x，三軌中最舊，FUT剛在round675更新過）；開工前
先重新檢查`- [ ]`有無新交辦、`本地AI摘要(Breeze-7B)`四選一是否已裁示、
`金流一.4`還需3個交易日、`外部一改.2`tick累積14/20還差6日；凍結.二在
總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`第676輪
心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-29T21:0x+08:00（馬拉松第672輪，維運帽）**——取鎖乾淨
（cycle`20260929-210037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=14條（與
round669~671一致）。逐一核對14條`- [!]`阻塞項：**`驗.九`狀態有實質變化**
——讀`research/data/diag_v9_fetch_missing.json`（gitignore）：
`generated_at=2026-09-29T20:48:17`，`requests_used=426`／`remaining=0`／
`stopped=null`，crosscheck 511筆FinMind快取補抓**已全數完成、零撞牆**
（上一輪round671記錄仍253/511卡在額度冷卻）；核對`data/rate_limit_
state.json`確認`finmind.blocked_until`已於18:24過期、`last_request_at`
20:47:57為額度解除後的正常請求。**但瓶頸轉移，非全部解除**：二.1「跑完
並回報受影響股票數與天數」實際要跑的是`research/audit_v8_yf_
crosscheck.py`（`import factor_ic`→觸發`mem_guard`），本輪`Get-
CimInstance Win32_OperatingSystem`實測系統可用記憶體**2.76GB**（<3GB
門檻），執行會被10秒內`os._exit(1)`強制終止；一（定量分解，`audit_v9_
revenue_trace.py`同樣觸發`mem_guard`）同一原因仍阻塞。`[自行裁量]`：
不嘗試執行（阻塞成因與先前輪次判定「試了兩次還是失敗」相同——記憶體
<3GB——重試無新資訊）；發現`research/audit_v9_fetch_missing.py`有
未commit的WIP修改（非十三節限定檔案，本輪只讀不commit，留給後續
接手者自行處理，避免覆蓋風險）。retry條件維持不變：記憶體回升≥3GB。
`institutional_history.json`確認`dates`陣列仍20筆、最後日期`20260924`，
solid交易日數維持16日；tick累積仍14/20；其餘12條均未到解除時間。
`凍結.二`仍生效，佇列深度`- [ ]`=0不補alpha試驗湊數。完整見
`PENDING_QUEUE.md`「驗.九」條目本輪新增段落。

