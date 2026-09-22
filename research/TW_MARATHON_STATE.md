# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-22T20:3x+08:00（馬拉松第601輪）**——取鎖乾淨
（cycle`20260922-203037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=0（`財報原子.補快取`／`籌碼原子.補上櫃三大
法人歷史`皆已於第598輪後續跑完成並標`[x]`，`git log`確認`7d0c7975`
「完成籌碼原子.補上櫃三大法人歷史回補（1718/1718工作日），修
remaining欄位bug」），24條`- [!]`阻塞中。`run_detached.py status`
確認running=0（147筆歷史）。**依輪替本應選TW**（TW round598=17:4x最舊，
US round599=18:3x，FUT round600=19:3x），核實TW軌是否真有新工作單位：
逐一複核`原子.一`~`原子.六`（含`五B`）在`PENDING_QUEUE.md`皆已標`[x]`
結案（一PASS審閱通過、二~六與五B皆FAIL），`CALIBRATION_PROBE.md`的
300檔重跑操作指令（#77/#79/#91/US#47/#52/FUT#34複驗）經`REPORT.md`
第552輪等多輪確認「全數複驗完畢」、`factor_ic.py::SAMPLE_SIZE`現況
確認仍為300。重跑`fin_atom_coverage.py`（背景執行，PYTHONIOENCODING
問題已知，輸出亂碼不影響數字判讀）確認五項原子（total_assets 67.5%/
equity 60.7%/inventory 63.7%/receivable 65.1%/ocf 65.0%）皆≥60%，與
round598記錄一致，無新增覆蓋率變化。`#50`（唯一未結案方向）tick
累積`data/ticks/`實測仍12/20（`20260916`~`20260922`，較FUT round600
無變化，屬時間累積型阻塞非本輪可推進）。掃`STRATEGY_GRAVEYARD.md`
「下一步/待辦」關鍵字，命中處皆為歷史結案條目內部的過程記錄（例如
#52-US round454條目的「下一步（留給下一輪判斷）」已被round456的
Item 5.02後續測試涵蓋），非未執行的活躍待辦。**結論：TW/US/FUT三軌
本輪皆無新可推進工作單位，與round594~600連續七輪的一致結論相同**，
本輪為新增的第八次獨立複核，維持不硬湊新項（避免違反誠實紀律）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（332列，本輪未新增判定，純查證/確認性質工作）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本檔案、`git log`、
`run_detached.py status`、重跑本機`fin_atom_coverage.py`純讀parquet
快取）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條
未開始**（24條`- [!]`阻塞中）。等待審閱：0件。**下一輪任一軌接手**：
`#50`仍是三軌唯一未結案方向，被動等待tick累積至20（目前12/20）與
總司令對gate50三條件的回應；若總司令未給新裁示，往後每輪不需要重複
做這種全面複核（已連續8輪相同結論），可直接於開工簡報確認`- [ ]`=0
後即記錄「與前次結論相同」並收工，節省輪次成本；依輪替下一輪建議選
US軌（US round599=18:3x）。完整見`REPORT.md`第601輪心跳、
`MARATHON_STATE.md`（輪次計數器601）。

---

**最後更新：2026-09-22T17:4x+08:00（馬拉松第598輪，驗證帽）**——
取鎖乾淨。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：`- [ ]`=0，
只有`財報原子.補快取`等既有`- [!]`冷卻中（預計17:0x解除，見下方接續
處理）。**本輪工作單位＝收成上一輪（第597輪）投遞的`chip_atom_ic_map.py
--tier A --tag _otc`job**（`20260922-163454-eca1`，`run_detached.py
status`確認`finished`/`exit=0`/耗時25.4min，log顯示宇宙U392檔、表達式
67、horizon20有183個snapshot／horizon60有61個，已存
`chip_atom_ic_map_result_A_otc.json`）。**戴驗證帽**：
1. 幫`chip_atom_ic_map_aggregate.py`加`--tag`參數（讀寫`_otc`後綴檔名，
   不動預設無tag行為，原`chip_atom_ic_map_aggregate.json`/
   `CHIP_ATOM_IC_MAP.md`/parquet全部未變動，已用`git status`核對）。
2. 跑`python chip_atom_ic_map_aggregate.py --tag _otc`，輸出
   `chip_atom_ic_map_aggregate_otc.json`/`CHIP_ATOM_IC_MAP_otc.md`。
3. 依`ATOM_CHIP_IC_MAP_SPEC.md`第7節事前綁定判定：條件1（20日p=0.913、
   60日p=0.924，皆遠高於0.01門檻）與條件2（高階篩選兩horizon皆通過0個，
   未超過樸素期望上界）**皆不成立→分支(b)FAIL**。與#317（併入前，
   20日p=0.913／60日p=0.986）幾乎相同，證明併入上櫃三大法人（T86族
   有效覆蓋50.5%→87.8%）**沒有改變結論方向**，排除「#317是檢定力不足」
   的疑慮。
4. `register_trial()`登記為**新試驗#328**（不沿用#317編號，依規格第12節
   要求），`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
   PASS（330列）；`selection_bias_ledger.py`重跑更新（N全體330，
   分軌TW=142）。更新`STRATEGY_GRAVEYARD.md`新增條目（緊接#317之前）、
   `ATOM_CHIP_IC_MAP_SPEC.md`第10節追記結案。**不寫入`TW_LEADS.md`**
   （FAIL不進候選清單）。
5. **佇列深度自檢**：`- [ ]`=0（低於門檻12），依既有規則本輪收工前需
   補件——但`財報原子.補快取`距上次請求（16:11:46）已逾79分鐘，冷卻
   早已解除，[自行裁量]優先轉回`- [ ]`續投b17/b18（單工作槽此刻空閒，
   `run_detached.py status`確認running=0），比另外湊補件更符合「有債務
   優先做債務」精神，佇列深度留給下一輪若仍<12再處理。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`；
未動凍結區；零新增外部API呼叫（`chip_atom_ic_map_aggregate.py`只讀本機
parquet/json）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條未開始**。等待審閱：0件。**下一輪**：若本輪已續投
`財報原子.補快取`b17/b18，下一輪先`run_detached.py status`收成並重跑
`fin_atom_coverage.py`；否則17:0x後續投。US/FUT依累積輪替下一輪建議
選其中之一。完整見`ATOM_CHIP_IC_MAP_SPEC.md`第10節、
`STRATEGY_GRAVEYARD.md`「原子.六（併入上櫃三大法人重測）」條目、
`PENDING_QUEUE.md`「財報原子.補快取」條目。

---

**最後更新：2026-09-22T16:3x+08:00（馬拉松第597輪）**——
取鎖乾淨（cycle`20260922-163037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=0（`籌碼原子.補上櫃三大法人歷史`已於
15:5x hypothesis_queue軌完成，`財報原子.補快取`因本小時FinMind額度
已用完轉標`- [!]`冷卻中，預計17:0x解除）。**[自行裁量：偏離嚴格輪替]**
依輪替本應選US（US round557/2026-09-19最舊，FUT round562/2026-09-19次之，
TW round596/本日15:3x最新），但開工核對US_MARATHON_STATE.md／FUT_
MARATHON_STATE.md：US #49/#51/#52已FAIL結案、#50因tick累積不足
（12/20）+ gate50三條件總司令尚未回應維持阻塞（`- [ ]`0項，依2026-09-15
裁示中途不重複回報tick進度）；FUT例外條款複核確認不成立（round562），
兩軌皆連續多輪確認無新可推進工作單位，**這輪並非「久未碰所以優先」，
是「久未碰是因為沒有新東西」**。同時發現TW軌剛完成的
`籌碼原子.補上櫃三大法人歷史.收尾重評`（DevQueue cycle 20260922-160102）
產出一個具體、尚未執行的新研究工作單位：三大法人族（T86）宇宙覆蓋率
因併入上櫃資料由50.5%→87.8%，`ATOM_CHIP_IC_MAP_SPEC.md`第12節明文
「若要重新檢定三大法人族，屬於新一輪試驗，須另行register_trial()登記，
不能沿用#317的判定」且「是否重跑由研究帽輪次另行排入佇列」——這正是
研究帽輪次該做的事，判斷優先做這個而非重複第N次記錄US/FUT空轉。
**本輪工作單位（戴研究帽）**：重跑`chip_atom_ic_map.py --tier A`
（沿用`ATOM_CHIP_IC_MAP_SPEC.md`原規格，宇宙/表達式/判定規則不變，
差異只在`chip_atom_library.load_t86_by_stock()`已併入上櫃三大法人快取），
用`--tag _otc`輸出至`chip_atom_ic_map_result_A_otc.json`避免蓋掉
`#317`原始結果（保留稽核軌跡）。**[自行裁量，發現並記錄debt]**首次
`run_detached.py submit`未帶`--cwd`預設解到`REPO_ROOT`（alpha-app根目錄）
找不到腳本，exit=2；第二次補`--cwd research`因bash當時cwd已在research/
內解出雙重前綴`research/research`，`NotADirectoryError`（與
`籌碼原子.補上櫃三大法人歷史`條目記錄過的同一種`--cwd`相對路徑陷阱同型，
確認須用絕對路徑`--cwd "C:/alpha/alpha-app/research"`）；過程中一個
失敗的submit產生孤兒watchdog條目（`20260922-163434-d862`），已用
`run_detached.py reap`清除。**第三次submit成功**（job
`20260922-163454-eca1`，timeout 30分鐘），session內`wait --max-min 4`
仍`STILL_RUNNING`（3分鐘時已印出「宇宙U：392檔；表達式=67（Tier A）」
與兩個horizon的snapshot數，計算量與原始#317跑法同量級），轉交下一輪
收成。**解除條件（下一輪第一件事）**：`run_detached.py status`確認
`20260922-163454-eca1`狀態變成`finished`/`failed`/`timeout`；`finished`
則讀`chip_atom_ic_map_result_A_otc.json`，跑聚合腳本
（`chip_atom_ic_map_aggregate.py`，需確認是否要帶`--tag _otc`或新增
對應參數）產生分年/牛熊段/樸此基準/共線分群數字，依`ATOM_CHIP_IC_MAP_
SPEC.md`第7節判定規則（事前綁定，不得因看到結果而調整）判(a)/(b)，
用`register_trial()`登記為**新試驗**（不沿用#317編號），更新
`CHIP_ATOM_IC_MAP.md`與`TW_LEADS.md`；`timeout`則檢視是否需要提高
timeout或改用`fin_atom_ic_map.py`同款的記憶體/效能修法。`trial_
registry.py --check`（`PYTHONIOENCODING=utf-8`）本輪開工前執行exit=0
PASS（329列，本輪未新增判定，因結果尚未產出）。`validation/holdout.py::
is_holdout_consumed()`開工前確認`False`（Tier A全程只讀`VAL_END`以前
快取，不觸碰holdout）。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，零新增外部API呼叫（`chip_atom_ic_map.py`只讀本機
既有快取，docstring明文「不發任何API請求」）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**（`財報原子.補快取`
`- [!]`冷卻中，17:0x後解除）。等待審閱：0件。**下一輪**：優先收成
`20260922-163454-eca1`（見上）；若已完成且判定產出，`財報原子.補快取`
17:0x後可續投b17；US/FUT依累積輪替下一輪建議選其中之一（本輪TW的
偏離屬一次性，不改變既有輪替原則）。完整見`ATOM_CHIP_IC_MAP_SPEC.md`
第12節、`PENDING_QUEUE.md`「籌碼原子.補上櫃三大法人歷史.收尾重評」
條目。

---

（第596輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）

