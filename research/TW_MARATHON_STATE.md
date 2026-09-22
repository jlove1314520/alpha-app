# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-22T22:42+08:00（馬拉松第602輪）**——取鎖乾淨
（cycle`20260922-223037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=0，24條`- [!]`阻塞中。逐項檢查阻塞條件是否
已解除：`run_detached.py status`確認`籌碼原子.補借券快取`b3
（job`20260922-214041-d80a`，round601之後由某輪投遞）已`finished`
（exit=0，8.6min），讀`backfill_sbl_cache_status.json`：`coverage_of_U`
從0.4719升至**0.6939**（≥0.6門檻、≥236檔），依`ATOM_CHIP_IC_MAP_SPEC.md`
第7/9節觸發Tier B（原文：「回補達U的60%（沿用原子.五覆蓋率門檻）才
執行Tier B，另立試驗登記」）。**本輪工作單位＝解除`chip_atom_ic_map.py
--tier B`硬擋並提交全量job**：原`main()`對`--tier B`恆印警告並
`return 2`；改為動態讀覆蓋率狀態檔，≥0.6才放行。同時修正一個潛在bug：
逐檔組frame時原本`cal.build_chip_frame(px, t86, cal.load_margin_frame(sid),
None)`的sbl參數恆傳`None`（即使解除硬擋也算不出IC），改成tier B時呼叫
`cal.load_sbl_frame(sid)`；`assert len(names) == 67`改依tier動態判斷
（A=67／B=22）。**驗證**：先跑`--tier B --n 15 --tag _smoke`（0列——15檔
小於`MIN_VALID=30`橫斷面門檻結構上不可能有IC，非bug），再跑
`--tier B --n 60 --tag _smoke60`（44列有IC，horizon20跳過1個snapshot、
horizon60跳過0個，峰值1890MB），確認正確後刪除煙霧測試輸出檔。
**提交全量job**`20260922-223837-b449`（`--tier B`，392檔×22表達式，
timeout 40分鐘），`wait --max-min 3`仍`STILL_RUNNING`（3分鐘時已印出
T86逐股載入2011檔、進度50/392，量級與Tier A（25.4min完成）同型），
轉交下一輪收成。`PENDING_QUEUE.md`「籌碼原子.補借券快取」條目與
`chip_atom_ic_map.py`模組docstring已同步更新。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（332列，本輪未新增判定，Tier B
結果尚未產出）。`validation/holdout.py::is_holdout_consumed()`開工/收工
前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，零新增外部API呼叫（煙霧測試與全量job皆只讀本機既有快取）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**
（24條`- [!]`阻塞中）。等待審閱：0件。**下一輪**：`run_detached.py
status`確認`20260922-223837-b449`是否`finished`；`finished`則讀
`chip_atom_ic_map_result_B.json`，依規格第7節「Tier B僅可作輔助」寫入
`CHIP_ATOM_IC_MAP.md`補充章節、`register_trial()`另立登記（依規格第9節，
不沿用#317），跑`trial_registry.py --check`與`selection_bias_ledger.py`；
`timeout`/`failed`則查log並比照Tier A的`run_detached`參數調整重跑。
完整見`REPORT.md`第602輪心跳、`MARATHON_STATE.md`（輪次計數器602）、
`ATOM_CHIP_IC_MAP_SPEC.md`第7/9節、`PENDING_QUEUE.md`「籌碼原子.補借券
快取」條目。

---

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
（第597輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
