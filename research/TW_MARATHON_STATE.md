# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


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

---
**最後更新：2026-09-29T18:0x+08:00（馬拉松第669輪，維運帽）**——取鎖乾淨
（cycle`20260929-180037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，`分K.零`已由round666完成並移入
`AWAITING_REVIEW.md`），`grep -c "^- \[!\]"`=14條（較round661~666的
12/13條略增，round667新增`驗.九`後轉`- [!]`）。逐一核對14條`- [!]`
阻塞項是否解除：直接讀`data/institutional_history.json`確認`dates`
陣列仍20筆、最後日期`20260924`，solid交易日數維持**16日**，今日
09-29（週二）18:0x查詢（收盤後約4.5小時，法人資料排程尚未入庫本日
新交易日），20日視窗仍差4個交易日，未解除；`外部一改.2`／`研究.c`
共用的tick累積`ls research/data/ticks/*.parquet`實測**14/20**（與
round667/668一致），未解除；`驗.九`retry條件（記憶體≥3GB或FinMind
額度過2026-09-29T18:24+08:00解除）本輪實測：`Get-CimInstance
Win32_OperatingSystem`可用實體記憶體**2.70GB**（<3GB，未解除）；
`data/rate_limit_state.json`確認`blocked_until=1790677456.67`＝
2026-09-29T18:24:16+08:00，本輪查詢時間18:0x**尚未到解除時刻**（差
約24分鐘），未解除；其餘11條逐一核對開頭標記，均為等總司令/Cowork
裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，
皆為條件敘述提及該詞彙、非實際宣告解除；`轉向.一`本身已完成第1點
查證、待Cowork核對閘門一/二後總司令放行單發檢定，現列在
`AWAITING_REVIEW.md`），本階段暫停佇列深度補件，不重掃備援來源。
三軌時間戳：TW round666=09-29 15:0x（最舊）／FUT round667=09-29
16:0x／US round668=09-29 17:0x——依輪替選TW。**逐一核對`凍結.二`
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；
資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗
commit；`git status --short`確認`research/backtest/`／`research/
validation/`／`research/adjust.py`／`research/pit.py`／`research/
trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯（輸出為
空）。**額外核對是否有互動視窗/DevQueue正在進行的工作**：
`Get-CimInstance Win32_Process`未偵測到`audit_v9`/`audit_v8`/
`audit_v7`/`audit_v6`相關python行程；僅`http.server 8792`（冒煙測試
用途，非研究行程）與一支無法讀取命令列的python.exe（PID 115432，
推測為`shioaji_quotes.py`常駐行程，權限限制無法讀取完整命令列，非
異常）。`run_detached.py status`：`running=0`（162筆歷史，無job待
收成）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（406列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表頭「目前：
19件」，本輪未變動。**本輪誠實結論**：交辦佇列無`- [ ]`項目，凍結.二
允許的四類工作皆已完成或無新內容，14條`- [!]`逐一核對均未到解除時間
（`驗.九`兩個retry條件皆差臨門一步：記憶體2.70GB<3GB、FinMind額度
約24分鐘後才解除），TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊
候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不變更
正式交易連線。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋
archive舊state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`
帳本檔案、`git status`/`git log`、`run_detached.py status`、
`trial_registry.py --check`、`Get-CimInstance`）。`PROGRESS_HEARTBEAT.
jsonl`已append本輪一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待
審閱：19件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌
接手**：依輪替下一輪建議選FUT軌（round667=09-29 16:0x，三軌中最舊）；
開工前先重新檢查`驗.九`retry條件（記憶體≥3GB或FinMind額度過
2026-09-29T18:24+08:00解除，兩者本輪查詢時已非常接近，下一輪查詢
時大機率已解除，需重新讀取確認並視情況改回`- [ ]`接續）；凍結.二在
總司令/Cowork明確寫「凍結.二解除」前不解除；`金流一.4`還需4個交易日；
`外部一改.2`tick累積14/20，還差6日。完整見`REPORT.md`第669輪心跳、
`PENDING_QUEUE.md`「驗.九」條目、`research/AWAITING_REVIEW.md`。
