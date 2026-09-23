# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的 65 則已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

---

**最後更新：2026-09-23T06:3x+08:00（馬拉松第610輪，維運帽）**——取鎖乾淨
（cycle`20260923-063037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
全文0條`- [ ]`，23條`- [!]`阻塞中；逐一核對阻塞項開頭標記可能已解除的
條件（金流一.4等待資料累積、資料源一.3等待總司令領key、`#50`tick累積
與gate50裁示等）皆未到解除時間點，維持`- [!]`。**佇列深度自檢**：
`- [ ]`=0（<12下限），round599~609已連續多輪確認三個備援來源掃無新項，
本輪不重複全面掃描。三軌時間戳：TW round608=09-23 04:3x／US
round609=09-23 05:3x（最新）／**FUT round607=09-23 03:3x（最舊）**——
依round608/609建議與輪替選FUT。`run_detached.py status`確認`running=0`
（151筆歷史，無running job需收成）。`git status`僅例行排程檔案
（`audit_report.json`/`factory_stability*`/`connectivity_check.log`等），
無conflict標記、無孤兒未commit產出。**本輪工作單位＝完成round607留下的
明確待辦**（「建議下一次維運帽輪次搜尋所有`.ps1`/排程設定裡`git -c
rebase.autoStash`或`git pull`不帶`--no-rebase`的呼叫點」）：`grep`
`alpha-app`repo內（僅`news_events.yml`一處，雲端runner）與repo外
`C:\alpha\`（`find`才找得到，round607在repo內搜尋`*.ps1`找不到的原因）
共查出**四個**位置使用`git pull --rebase --autostash`收尾：
`run-marathon-cycle.ps1`第65行／`run-dev-queue-cycle.ps1`第121行／
`run-hypothesis-queue-cycle.ps1`第44行／`news_events.yml`第68行。三支
本機wrapper各自獨立排程（15~30分鐘週期）、彼此無git操作層級的協調
機制（`marathon_lock.py`等鎖只防同track內部重疊，不管跨track的
pull/push時機）。**根因判定**：`--autostash`會掃入「當下工作目錄裡
所有已追蹤但未commit的修改」，不只是該wrapper自己準備commit的檔案；
若某輪claude session因`BUDGET`/`TIMEOUT`被砍（`MARATHON_PROTOCOL.md`
0b節已知會發生）留下未commit的修改，下一次任一wrapper（不限同track）
跑到`git pull --rebase --autostash`時會把這些修改一併暫存，若遠端剛好
也有同檔案的不同修改，rebase本身成功但post-rebase的stash-pop可能衝突，
只留下工作目錄字面衝突標記、不會設定`rebase-merge`/`MERGE_HEAD`狀態
——這正好解釋round607觀察到的異常現象。**產出**：把完整查證與三個
候選修復方案（甲：跨wrapper共用git操作鎖；乙：改用`git stash push --
<明確路徑>`縮小掃描範圍；丙：pull後push前偵測衝突標記，偵測到就跳過
push降級成警告）寫入`PENDING_QUEUE.md`「2026-09-23【維運.git衝突根因】」
章節並登記進`AWAITING_REVIEW.md`（**等待中：2件**，此為新增第2件）；
核准前三支wrapper維持現狀不變（依`CLAUDE.md`「提案先於執行」——跨
wrapper協調git操作屬架構選擇，非本輪`[自行裁量]`範圍）。本輪未修改
任何`.ps1`檔案，純查證＋grep＋讀檔＋寫入`alpha-app`repo內的文件。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（347列，本輪未新增判定，純維運根因查證非統計判定，不觸發
`register_trial()`）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，全程零新增外部API呼叫（純`grep`/`find`/讀檔/寫入
`.md`文件）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條未開始**（23條`- [!]`阻塞中）。**等待審閱：2件**（規.二第4節
參數掃描方式提案，延續中；本輪新增維運.git衝突根因修復方案）。
**下一輪任一軌接手**：`#50`仍是三軌唯一未結案方向，被動等待tick累積至
20（12/20）與總司令對gate50三條件的回應；本輪新增的git衝突根因修復
提案待總司令裁示方案甲/乙/丙或指定其他做法，核准前不得修改三支
wrapper；依輪替下一輪建議選TW軌（round608=09-23 04:3x，三軌中最舊）。
完整見`REPORT.md`第610輪心跳（待補）、`PENDING_QUEUE.md`「2026-09-23
【維運.git衝突根因】」章節、`AWAITING_REVIEW.md`。


**上一則保留（第520輪，供對照）**——原文：最後更新：2026-09-10T15:02+08:00（馬拉松第520輪）**——取鎖乾淨（cycle`20260910-150037`）。依round519建議本輪重新評估FUT例外條款是否仍成立。`run_detached.py status`：`running=0`（60筆歷史紀錄，無新增）；`git log`確認round519之後除round519自身commit`10abc8b5`外，還有互動session兩筆維運commit（停擺三／停擺四／停擺一收尾、深讀三新增第7~10關、深讀四.3連續曝險縮放偏好成文），皆非本馬拉松範圍，未動凍結區。**FUT例外條款複核結果：仍不成立，無新機制候選**——`MARATHON_PROTOCOL.md`第3節列出的期貨假說類別（多時間框架趨勢/突破/波動regime/均線/日內均值回歸/期現價差/三大法人期貨部位/未平倉量/隔夜vs日內/星期效應/盤別效應）round399已確認全數至少測過一個變體；`#64`基差regime訊號（round484，唯一一次真正觸發例外條款的新機制）已於round484結案FAIL；round484之後至今唯一新增的期貨相關試驗是`hypothesis_queue`（非本馬拉松軌）2026-09-10「外部一改.3」補測的五個名家發表趨勢跟隨機制（海龜/Donchian/Keltner/波動度突破/CTA多時間框架），`TRIALS_LEDGER.md`#234~#238全數FAIL，且經相關係數檢查後四條與既有`hyp_trend_multi_tf`/`hyp_donchian_breakout`同屬趨勢突破家族（`|r|>0.7`），只有波動度突破一條是真正獨立發現但percentile僅7.0，非FUT track本身的新工作單位，亦未帶來可承接的候選。**依輪替回落TW軌**：TW 14:02（round518，最舊）／US 15:02（round520本輪決策前查詢，最新）——本輪決策為FUT優先評估但未推進實質工作單位，依規則本輪工作單位改為對TW軌做同等的精簡確認（見下段）。**TW軌精簡確認**：`PENDING_QUEUE.md`第99~113行gate50查證段落仍原封不動，總司令尚未回應三條件具體定義，`#50`維持未解鎖；`data/ticks/`累積進度**4/20**（`20260907`~`20260910`四個`.parquet`皆已finalize，距20日仍差16日，較round519無變化——`20260910`當日盤中tick仍在累積中，尚未到隔日finalize時點）；`STRATEGY_GRAVEYARD.md`掃描`## #6x`/`## #7x`標題，最新結案仍為`#70`（2026-09-10，hypothesis_queue軌，非本馬拉松範圍），本馬拉松TW/US/FUT三軌自身最新結案仍為`#68`（round510），無新結案。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（243列，撞號2組皆為歷史存量不回頭改寫，本輪未產生新試驗判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`檔案與`git log`/`git status`/`run_detached.py status`）。**結論：FUT例外條款複核完畢並確認不成立（本輪唯一實質產出），候選池連續34輪（487~520）維持同一狀態，TW/US/FUT三軌本地端皆無新可推進工作單位**，僅剩`#50`（tick累積4/20，被動等待總司令對gate50三條件的回應）。**下一輪任一軌接手**：`#50`gate50原文仍待總司令回應；FUT例外條款已複核確認不成立，往後除非出現真正跳脫`MARATHON_PROTOCOL.md`第3節清單的全新機制假說，不需要每輪重新複核FUT，依輪替下一輪建議選TW軌。完整見`REPORT.md`第520輪心跳、`MARATHON_STATE.md`（輪次計數器520）。
