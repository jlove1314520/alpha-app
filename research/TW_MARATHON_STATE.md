# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-23T00:3x+08:00（馬拉松第604輪）**——取鎖乾淨
（cycle`20260923-003037`）。依round601自己的建議（已連續8輪同一結論後
不必再做全面複核），本輪僅做精簡確認：`PENDING_QUEUE.md`『- [ ]』=0，
23條`- [!]`阻塞中；`run_detached.py status`確認running=0（150筆歷史，
無新增，round603投遞/收成的Tier B job`20260922-223837-b449`仍是最新一筆
`finished`）；`git status`乾淨（僅例行排程檔`data/audit_report.json`／
`research/*.log`/`*.jsonl`等自動更新檔案，無孤兒未commit產出）；`#50`
唯一未結案方向tick累積`research/data/ticks/`實測仍**12/20**（`20260916`
~`20260922`，09-23當日盤中tick尚未finalize，較round600/601無變化）。
**結論：與round594~601連續八輪一致，TW/US/FUT三軌本輪仍無新可推進
工作單位**，本輪為第九次確認，繼續維持不硬湊新項。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（333列，本輪未新增
判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，全程
零新增外部API呼叫（純讀既有帳本/log檔案、`git status`、`run_detached.py
status`、`ls research/data/ticks/`）。`PROGRESS_HEARTBEAT.jsonl`已append
本輪一行。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞中）。等待審閱：
0件。**下一輪任一軌接手**：`#50`仍是三軌唯一未結案方向，被動等待tick
累積至20（目前12/20，預計還需8個交易日finalize）與總司令對gate50三
條件的回應；**建議下一輪比照本輪做法：先確認`- [ ]`=0與tick累積數字，
若無變化直接記錄「與前次結論相同」收工，不必逐條重新掃描三個備援
來源**（該三個來源已連續9輪掃無新項，重複掃描本身不再產生新資訊）。
完整見`REPORT.md`第604輪心跳、`MARATHON_STATE.md`（輪次計數器604）。

---

**最後更新：2026-09-22T23:5x+08:00（馬拉松第603輪，維運帽）**——取鎖乾淨
（cycle`20260922-233037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0，23條`- [!]`阻塞中。`run_detached.py status`確認round602投遞的
`chip_atom_ic_map.py --tier B`全量job`20260922-223837-b449`已`finished`
（exit=0，11.1min）。**發現：這項收成工作已在本輪開工前被hypothesis_queue
自走軌次獨立完成**——`git log`確認22:55有一次hypothesis_queue cycle
commit（`48d29ad8`），但比對`run-hypothesis-queue-cycle.ps1`的
`Commit-CycleLog`函式（僅`git add`三個固定log檔）與`git show --stat
48d29ad8`（只含`hypothesis_queue_cycle.log`/`quota_usage_daily.log`
兩檔），確認該cycle的`claude -p`session本身完成了實質工作（讀
`chip_atom_ic_map_result_B.json`、依規格第7節判定、寫入
`CHIP_ATOM_IC_MAP.md`「Tier B 補充」章節、`register_trial()`登記
`TRIALS_LEDGER.md`/`TRIALS_REGISTRY.jsonl`#331、更新`PENDING_QUEUE.md`
該條目為`[x]`、重跑`SELECTION_BIAS_LEDGER.md`）**但該session自己未在
收工前commit這些實質變更**，全部以未追蹤/已修改狀態留在工作目錄裡，
橫跨兩次30分鐘馬拉松cycle窗口而未遺失，純屬僥倖（若中途有任何`git
checkout`/`git clean`類操作會整批消失）。**本輪工作單位＝驗證＋補
commit，不重做**：逐項核對判定正確性（20日Poisson-binomial
p=0.0452、60日p=0.1111，皆未達規格第7節p<0.01門檻；高階篩選通過0個，
未超過樸素期望上界；依分支(b)判FAIL，與Tier A(#317/#328)方向一致，
屬穩健性佐證非獨立判定，符合規格第7節第3款「Tier B僅可作輔助」的
明文限制）。執行`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（333列，最大編號#331，無強制期內未登記判定）；重跑
`selection_bias_ledger.py`確認N=333與已寫入`SELECTION_BIAS_LEDGER.md`
的數字一致（分軌TW=143/US=66/FUT=48/未分軌=76）；`validation/
holdout.py::is_holdout_consumed()`確認`False`。確認`chip_atom_ic_map_
result_B.json`／`chip_atom_ic_map_aggregate_B.json`兩個產出檔案（比照
既有`_A`/`_A_otc`慣例應進版控但先前未`git add`）一併納入本輪commit。
**根因記錄（不在本輪修復，留給維運帽或總司令裁示是否需要修）**：
`run-hypothesis-queue-cycle.ps1`的`Commit-CycleLog`是2026-09-18刻意
限制pathspec的設計（修過去`git commit`不帶pathspec誤吃無關檔案的
bug），設計上**假設`claude -p`session自己會在收工前完成commit**——
本次是session本身漏做收工序最後一步（commit+push），不是wrapper的
pathspec設計缺陷，跟`CLAUDE.md`十/十一/十二節「排程腳本改寫檔案未進
allowlist」不是同一種故障形狀（allowlist涵蓋範圍是對的，是session
沒把自己該做的commit做完）。至此`原子.六`規格第8節執行清單（89個
籌碼depth-1表達式×2horizon=178測試）全數完成並判定：T86族/融資融券族
（Tier A）與借券賣出族（Tier B）在depth-1、日頻、lag1構造下四組
（2 Tier×2 horizon）判定條件全數不成立，無跨牛熊段穩定訊號，死因為
「流程對但這條假設無edge」。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，零新增外部API呼叫（純讀既有快取與帳本檔案、
`git log`/`git show`/`run_detached.py status`）。`PROGRESS_HEARTBEAT.
jsonl`已append本輪一行。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞
中）。等待審閱：0件。**下一輪任一軌接手**：`#50`仍是TW/US/FUT三軌
唯一未結案方向，被動等待tick累積至20（`data/ticks/`目前進度需重新
清點）與總司令對gate50三條件的回應；`原子.六`規格全數結案後，TW軌
若無總司令新裁示，建議下一輪盤點是否有其他既有SPEC的「下一步」欄位
類似本輪這種「已算完但漏commit」的孤兒產出，可比照本輪`git status`
+`git log`交叉核對的方式抓漏；依輪替下一輪建議選US軌（US round599
最舊，晚於TW round603/FUT round600）。完整見`REPORT.md`第603輪心跳、
`MARATHON_STATE.md`（輪次計數器603）、`ATOM_CHIP_IC_MAP_SPEC.md`第7節、
`CHIP_ATOM_IC_MAP.md`「Tier B 補充」章節、`TRIALS_LEDGER.md`#331。

---

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

（第598輪、第601輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
