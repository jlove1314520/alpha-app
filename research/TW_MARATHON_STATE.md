# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

**最後更新：2026-09-22T15:3x+08:00（馬拉松第596輪）**——
取鎖乾淨（cycle`20260922-153036`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=2（`財報原子.補快取`／`籌碼原子.補上櫃三大
法人歷史`），皆持續回補中，`run_detached.py status`確認running=0。
**先確認上一輪投遞的TPEx batch5**（job`20260922-144247-c12b`）`exit=0`
（20.1min），log自報`cached_total=1711/range_workdays=1718/remaining=7`。
**FinMind距上次請求（14:40:41）僅約51分鐘，未滿一小時安全間隔，本輪不
投FinMind批次**，單工作槽留給TPEx：投batch6（`--batch-size 300`，
job`20260922-153118-42df`）。**[自行裁量][發現並記錄一個debt bug，非
本輪阻塞]** 投遞後腳本自己重算真實`pending`，開工行印出「已快取1711，
待處理304」——跟上一輪log摘要`remaining=7`矛盾。查`backfill_tpex_
3insti_history.py`第103~109行：那個`remaining`欄位算法是
`len(all_dates)-len(have)`，`have`是**整個`DATA_DIR`目錄**的parquet檔
數，不是「在`all_dates`範圍內」的檔案數；`pending`（實際決定下一批要抓
哪些日期）才是正確的集合成員判斷。兩者用不同邏輯，導致log摘要的
`remaining`虛低（可能是START從更早日期改成2018-06-01後，目錄裡混有
範圍外的舊快取檔，虛增`have`分母）。**不影響回補正確性**（下一批仍是
用`pending`算的，對），只是狀態文字誤導、容易讓人誤判「快補完了」。
已投batch6處理304筆裡的300筆，依歷史耗時（300項約16~17min）超過本輪
安全邊際，session內未等待完成，留給下一輪`run_detached.py status`收成；
建議下一輪順手修`remaining`欄位算法（改成`len(pending)`或
`len(all_dates)-len(have & set(all_dates))`），這是純debt不急，但要讓
下一輪知道真實進度是約304筆待處理（這批做完後約剩4筆），不是舊訊息
暗示的「只差7筆」。`trial_registry.py --check`（`PYTHONIOENCODING=
utf-8`）exit=0 PASS（329列，本輪未新增判定，純債務/維運性質工作）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，零新增外部
API呼叫（僅投遞TPEx job，未實際發出FinMind請求）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未開始**
（皆持續回補中，非新交辦）。等待審閱：0件。**下一輪**：先
`run_detached.py status`確認`20260922-153118-42df`是否`finished`，讀
真實`pending`（不要信舊的`remaining`欄位，等下一輪修過再信）決定是否
需batch7；`財報原子.補快取`距14:40:41滿一小時（約15:41台北）後可續投
b15/b16（優先覆蓋率離60%較遠者：equity/inventory/receivable/ocf）；
順手修`backfill_tpex_3insti_history.py`的`remaining`欄位算法（低優先，
純debt）。完整見`PENDING_QUEUE.md`籌碼原子.補上櫃三大法人歷史條目。

---

**最後更新：2026-09-22T14:4x+08:00（馬拉松第595輪）**——
取鎖乾淨（cycle`20260922-143037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=2（`財報原子.補快取`／`籌碼原子.補上櫃三大
法人歷史`），皆持續回補中。**先確認上一輪投遞的TPEx batch4**
（job`20260922-133117-9ffe`）`exit=0`（17.4min），累計快取1111→1411/1718，
remaining=307。**FinMind額度距上次請求（12:42:32）已逾1.8小時，冷卻早
解除**，本輪工作單位＝續投`財報原子.補快取`b13/b14：
`run_detached.py submit --name fin_atom_cache_backfill_b13 --timeout-min 15
--cwd . -- python -u backfill_fin_atom_cache.py --batch-size 50`
（job`20260922-143130-7a32`，session內等待4.6min後`finished`，92次請求
全成功0個402），接續投b14（job`20260922-143622-bfde`，4.4min後
`finished`，87次請求全成功0個402），本小時累計179次請求接近既有
190次/小時安全上限，本輪不再續投。remaining_pairs 1889→1710。
`fin_atom_coverage.py`重跑：**total_assets全體61.0%（前57.6%）首度
轉OK**、equity 55.0%（前52.0%）、inventory 57.5%（前54.3%）、
receivable 58.7%（前55.4%）、ocf 56.3%（前52.5%）——四者仍<60%→(a)
未達，維持`- [ ]`續補。FinMind批次收成後單工作槽空出，續投
`籌碼原子.補上櫃三大法人歷史`batch5：`run_detached.py submit
--name tpex3insti_hist_b5 --timeout-min 25 --cwd . --
python -u backfill_tpex_3insti_history.py --batch-size 300`
（job`20260922-144247-c12b`），依歷史批次耗時約16~17min＞本輪剩餘時間
安全邊際，session內未等待完成，留給下一輪`run_detached.py status`收成。
**佇列深度自檢**：`- [ ]`僅2項，低於`queue_depth_config.py`門檻12——
沿用round594/593判斷（掃描`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`/
`HYPOTHESIS_QUEUE.md`後仍只有「需先設計具體構造才能開跑」的候選，
`#76`屬hypothesis_queue自己獨立自走軌道不重複灌入），**本輪判斷維持
現況2項、不硬湊新項**。`trial_registry.py --check`（`PYTHONIOENCODING=
utf-8`）exit=0 PASS（329列，本輪未新增判定，純債務/維運性質工作）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，FinMind請求
皆計入既有額度追蹤，TPEx確認查詢零新增外部API呼叫追蹤外的用量。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條未開始**
（皆持續回補中，非新交辦）。等待審閱：0件。**下一輪**：先
`run_detached.py status`確認`20260922-144247-c12b`是否`finished`並視
remaining決定是否需batch6；`財報原子.補快取`本小時額度已接近上限，
下一批最早15:4x台北，優先回補equity/inventory/receivable/ocf四項
（覆蓋率離60%最遠者優先）；`STRATEGY_GRAVEYARD.md`「事件驅動」結案後，
若總司令核准可評估`MARATHON_PROTOCOL.md`0a節四條方向是否已全數窮盡。
完整見`PENDING_QUEUE.md`財報原子.補快取／籌碼原子.補上櫃三大法人歷史
條目。


（第594輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
