# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的 65 則已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-24T05:3x+08:00（馬拉松第636輪，研究帽）**——取鎖乾淨
（cycle`20260924-053037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（`grep -n "^- \[ \]"`全文0筆命中，`閘門.一`仍標`- [!]`），逐一核對
`- [!]`阻塞項開頭標記皆未到解除時間。**佇列深度自檢**：`- [ ]`=0（<12
下限），依`CLAUDE.md`十四節【凍結.二】本階段暫停佇列深度補件，不重掃
備援來源。三軌時間戳：TW round635=09-24 04:3x／US round634=09-24
03:3x／**FUT round633=09-24 02:3x（最舊）**——依輪替選FUT。**核心查證**：
`data/rate_limit_state.json`顯示FinMind於2026-09-23T20:37:44 UTC再次
命中402，`blocked_until`=1790203064.30（換算台北2026-09-24T06:37:44），
本輪05:31查詢時**仍BLOCKED，約差66分鐘**——round635記錄的「額度已解除、
另一行程接手續抓」是暫時現象，該行程續抓到`fetched_ids`=222後又再次
撞額度（`failed_ids`由round635的35增至41），目前無lock檔案（確認
`research/.f52w_2007_extension.lock`不存在），非有行程正在跑，是被
FinMind硬性擋住。`run_detached.py status`：`running=0`（160筆歷史，
無job待收成）。`git status`僅例行排程檔案8個（`audit_report.json`/
`factory_stability*`/`connectivity_check.log`等），無conflict標記、
無孤兒未commit產出。**逐一核對`凍結.二`允許的四類工作現況**：稽核
重跑（驗.一第4點續剩餘8支＋剩餘16支）皆已grep確認標`[x]`完成並登記
#387-393；資料抓取被FinMind額度硬性擋住（見上，還需約66分鐘）；工具
修正（修.三額度錯誤bug＋並發鎖）已由互動視窗CC完成並commit
（`a80b27f7`，本輪`git status`確認`research/factors.py`無未commit
修改）；驗.二開盤到收盤重跑（`驗.二續`）已grep確認標`[x]`完成並登記
`TRIALS_LEDGER.md`#394（FAIL，第3關參數高原未過）。`AWAITING_REVIEW.md`
「等待中」表格確認**0件**。**本輪誠實結論**：四類允許工作皆已完成或
被外部額度阻擋，FUT軌本身查無可推進的新工作單位（`#50`容量受限小型股
方向tick累積13/20，依裁示不重複回報進度細節）——依`CLAUDE.md`「零之
一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰
`凍結.二`禁止的新alpha試驗。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增判定，
不觸發`register_trial()`）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改`research/backtest/`／`research/validation/`
／`trial_registry.py`等`CLAUDE.md`十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`Get-Process`等效檢查）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**
（僅`閘門.一`標`- [!]`，BLOCKED於續抓完成）。**等待審閱：0件**。**下一輪
任一軌接手**：FinMind額度預計06:37台北解除，解除後才可繼續續抓
f52w/dividend 2007-2014延伸資料（目前222/300，還差78檔，但`failed_ids`
已41筆需一併檢視是否為永久性失敗）；`閘門.一`待續抓完成後才可執行五項
資料品質檢查；`#50`持續被動等待tick累積至20（13/20）；依輪替下一輪
建議選US軌（round634=09-24 03:3x，三軌中最舊）。完整見`REPORT.md`
第636輪心跳、`PENDING_QUEUE.md`「閘門.一」條目、
`data/f52w_2007_extension_checkpoint.json`。

---

**最後更新：2026-09-24T02:3x+08:00（馬拉松第633輪，研究帽）**——取鎖乾淨
（cycle`20260924-023037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=1（僅`閘門.一`，開考前資料品質閘門），但明文**BLOCKED於「續抓剩餘
168檔」完成**——`定案.一`／`修.三`／`驗.四(資料一品質)`皆已由互動視窗CC
本輪之前完成並標`[x]`（commit`a80b27f7`修正額度錯誤被吞掉的bug＋加並發鎖），
`閘門.一`本身不是可獨立動手的工作單位。逐一核對23條`- [!]`阻塞項的解除
條件，均未到解除時間（`金流一.4`等資料累積、`資料源一.3`待總司令領key、
`外部一改.2`tick累積、`結案.一`需總司令實機驗證等），維持`- [!]`。**佇列
深度自檢**：`- [ ]`=1（<12下限），但`CLAUDE.md`十四節【凍結.二】本階段
明文暫停佇列深度補件（轉向.一結果出來前不得補新alpha試驗湊數），不重掃
備援來源。三軌時間戳：TW round632=09-24 01:3x／US round630=09-23 23:3x／
**FUT round625=09-23 22:3x（最舊）**——依輪替選FUT。**核心查證**：讀
`research/f52w_2007_extension_checkpoint.json`確認`fetched_ids`已達
**169/300**（較round625記錄的132檔續有進展，代表其他session在round625~
本輪之間持續推進續抓），`failed_ids`/`factor_warnings`欄位存在但為空。
`data/rate_limit_state.json`顯示FinMind於2026-09-23T18:21:39 UTC再次命中
402，`blocked_until`=2026-09-24T04:21:39 台北（本輪02:3x查詢時仍BLOCKED，
約差108分鐘），確認**未持有**`f52w_2007_extension.lock`鎖檔（無行程正在
跑），續抓工作單位當下處於「不是被搶佔，是被FinMind額度硬性擋住」的
狀態，任何session此刻嘗試續抓都會立即再次撞額度，不是可推進的工作。
`run_detached.py status`：`running=0`（160筆歷史，無job待收成）。**本輪
誠實結論**：`凍結.二`允許的四類工作（稽核重跑／資料抓取／工具修正／驗.二
開盤到收盤重跑）逐一核對現況——稽核重跑（驗.一第4點續剩餘8支）已於
round624完成並登記#387-393；資料抓取被FinMind額度硬性擋住無法執行；
工具修正（修.三額度錯誤bug＋並發鎖）已由互動視窗CC完成（commit
`a80b27f7`）；驗.二開盤到收盤重跑已於`驗.二續`完成並登記`TRIALS_LEDGER.md`
#394（FAIL，第3關參數高原未過）。**四類允許工作皆已完成或被外部額度阻擋，
FUT軌本身無獨立可推進項**（`#50`容量受限小型股方向仍被動等待tick累積，
`外部一改.2`維持`- [!]`不重複回報進度）——依`CLAUDE.md`七之三節研究紀律
「找不到就老實說找不到」與「零之一」白名單第7條（佇列真的空了）記錄後
結束本輪，不硬湊候選、不觸碰`凍結.二`禁止的新alpha試驗。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（399列，本輪純查證未新增判定，不觸發`register_trial()`）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
`research/backtest/`／`research/validation/`／`trial_registry.py`等
`CLAUDE.md`十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive
舊state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩
1條未開始**（`閘門.一`，BLOCKED於續抓168檔完成，非可獨立推進項）。
**等待審閱：0件**（先前`value_board_v2`翻轉#390已於2026-09-24總司令
裁示【候選名單定案】結案，維持FAIL，非本輪新增）。**下一輪任一軌接手**：
續抓168檔預計04:21台北解除FinMind額度封鎖，解除後才可繼續（目前169/300，
還差131檔）；`閘門.一`待續抓完成後才可執行五項資料品質檢查；`#50`持續
被動等待tick累積至20（13/20）；依輪替下一輪建議選US軌（round630=09-23
23:3x，三軌中最舊）。完整見`REPORT.md`第633輪心跳、`PENDING_QUEUE.md`
「閘門.一」條目、`data/f52w_2007_extension_checkpoint.json`。

---

**最後更新：2026-09-23T22:3x+08:00（馬拉松第625輪，維運帽）**——取鎖乾淨
（cycle`20260923-223037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0——TW軌round623/624與互動視窗CC已把先前開放項目全部結案：
`驗.一`／`驗.一第4點續(剩餘16支)`／`驗.一第4點續(剩餘8支)`／`尺.二`／
`審.二`皆已`[x]`；`驗.二`第一部分已`[x]`，第二部分（開盤到收盤重跑）
仍待辦但正被另一活躍session處理中（見下）。`資料.一`仍`BLOCKED`
（FinMind 402額度，`data/rate_limit_state.json`記`blocked_until`=
2026-09-23T14:44:48 UTC＝台北22:44:48，本輪22:30檢查時尚差約13分鐘，
未到解除時間，維持`- [!]`）。**佇列深度自檢**：`- [ ]`=0低於
`MIN_QUEUE_DEPTH=12`下限，但`CLAUDE.md`十四節「凍結.二」明文本階段
佇列深度補件規則暫停，**不得**用新alpha試驗補件，本輪不重掃備援來源。
`run_detached.py status`：`running=0`。**查核並結案一項過時待辦**：
TW round624投遞的job`20260923-213506-0f76`
（`weinstein_alpha_gate_engine_fix_recheck`）已`failed`（exit=1，
`validation/control_group.py::one_draw()`拋`ValueError: cannot
convert float NaN to integer`）——追查為已知舊漏洞
（`entry_price<=0`防呆漏掉NaN，因NaN<=0在Python恆為False）；比對
`git log`確認互動視窗CC已於commit`a73d5c20`（21:47:41，晚於本job
21:35:06啟動、21:37:00失敗）修正此漏洞，並用修正後引擎重新跑出結果，
登記`TRIALS_LEDGER.md`**#392**（`weinstein_alpha_gate.py`，VAL純alpha
配對式隨機控制組percentile=3.0，FAIL）與**#393**
（`weinstein_v2_alpha_gate.py`，percentile=4.0，FAIL）。round624留下
的「下一輪待做：收成job」**已由CC的工作取代，不需要重新投遞**，本輪
未再次呼叫`register_trial()`。**[自行裁量，避免搶寫競態]**：
`git status`發現`research/spillover_overnight_gate.py`有staged未commit
變更（107 insertions，比對`git log`最近一筆commit內容不含這批修改），
同時`tasklist`確認**12個`claude.exe`行程仍在並行**——判斷是另一個
活躍session正在做`驗.二`第二部分（開盤到收盤重跑9關），本輪**不觸碰
此檔案及其可能的輸出檔**，避免搶寫競態或重複運算浪費（比照round613/
623先例）。`#50`tick累積：`research/data/ticks/*.parquet`實測
**13/20**（新增`20260923.parquet`，較round600的12/20推進1日），
gate50三條件總司令仍未回應，維持`- [!]`被動等待，非本輪可推進項。
**本輪誠實結論**：先前所有開放項目已結案或正被其他活躍session處理，
`凍結.二`禁止新增alpha試驗、佇列深度補件規則暫停，本輪查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神（佇列真的空了）
記錄後結束本輪，不硬湊候選。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（395列，本輪未新增判定，純
查證/核對）。`validation/holdout.py::is_holdout_consumed()`開工/收工
前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改`research/backtest/`／`research/validation/`／
`trial_registry.py`等CLAUDE.md十三節限定清單內任何原始碼（僅讀取核對
＋archive舊state條目），全程零新增外部API呼叫（純讀既有`.md`/`.json`
帳本檔案、`git log`/`git status`、`tasklist`、`run_detached.py
status`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦
佇列還剩0條未開始**。**等待審閱：1件**（`value_board_v2`VAL alpha
翻轉#390，非本輪新增，延續中，見`AWAITING_REVIEW.md`）。**下一輪任一
軌接手**：確認`驗.二`第二部分是否已由活躍session完成commit（若已
commit，`research/spillover_overnight_gate.py`會從staged未commit變成
已進歷史，可直接引用結果不必重算）；`資料.一`預計22:44:48解除，屆時
可繼續f52w/dividend 2007-2014延伸抓取（轉向.一前置）；`#50`持續被動
等待tick累積至20（13/20）與gate50裁示；依輪替下一輪建議選**US軌**
（round613=09:3x，三軌中最舊）。完整見`REPORT.md`第625輪心跳、
`TRIALS_LEDGER.md`#392/#393、`FUT_STATE_ARCHIVE.md`（round600歸檔）。

