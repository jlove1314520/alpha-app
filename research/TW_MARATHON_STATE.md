# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-23T01:3x+08:00（馬拉松第605輪，研究帽）**——取鎖乾淨
（cycle`20260923-013037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=2（`規.二`／`規.三`，2026-09-23總司令裁示【拆除機構約束，改集中版】
新交辦，round604收工後才進佇列），23條`- [!]`阻塞中不變。**本輪連續完成
兩項交辦**：

1. **規.二**：建立`research/CONCENTRATED_SPEC.md`（只寫規格不實作）——
   目標函數（年化總報酬>0050/S&P500含息總報酬，取代舊TE≤2.5%約束）、
   天條對應、待測參數（持股檔數5格×部位上限3格×股票曝險比例4格=60格，
   不得全掃，列三個候選抽樣方案A/B/C）、選擇驗證紀律、三個必答問題
   （產業上限ceil(N/2)、出場規則、MDD日頻全期+逐空頭段）。**重要更正**：
   規.一.4原認為0050含息總報酬序列需另外提案建構，本輪查證發現
   `survival_constraint_allocation_test.py::load_0050_full_history()`
   （天條一.1既有程式碼）已是這個函式，可直接重用，不需另立建構工程；
   S&P500 Total Return序列缺口仍未解決。同時提交第4節參數掃描方式提案
   （候選C，約14~16格）至`PENDING_QUEUE.md`待總司令裁示，登記進
   `research/AWAITING_REVIEW.md`（**等待中：1件**）。順帶補commit孤兒
   產出`research/e1_rejudge_result.json`（round594已判定的支撐檔案，
   先前未git add）。
2. **規.三**：建立`research/exit_rule_lab.py`並執行——同一進場訊號
   (買入並持有0050)逐日模擬E-a~E-d四種出場規則（1+3+2+1=7變體，裁示
   原文寫8次試驗，如實登記7筆不湊數），輸出未扣成本/扣成本(基準情境
   1.8折)兩條淨值曲線的CAGR/MDD/Calmar/換手率。**重要發現**：E-b固定
   停損(8%/15%/25%)三者數字與E-a買進持有完全相同——進場價(2003-07-01)
   恰好接近0050歷史低點區域，全期最低點距進場價僅約-4.67%，從未觸及
   任一停損線，已誠實揭露「固定停損綁定單一原始進場價，在標的長期
   結構性上漲下一旦建倉初期未被停損就形同虛設」這個設計限制，供規.二
   出場規則設計參考，不建議直接沿用。E-c移動停損比固定停損更能實際
   發揮風控作用；E-d 200日均線regime出場net CAGR轉負(-6.07%，換手
   31.5次/年)，與既有regime overlay家族七次FAIL結論方向一致。全部7筆
   登記verdict=EXPERIMENTAL（純描述性比較，非alpha檢定）。

`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（346列，新增#338~#344）；`selection_bias_ledger.py`重跑更新N=346
（TW=156/US=66/FUT=48/未分軌=76）；`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫（純讀
既有0050價格快取與帳本檔案）。`PROGRESS_HEARTBEAT.jsonl`已append兩行
（規.二、規.三各一行）。兩筆分別commit+push（`b55dc193`規.二、`9c8ecb56`
規.三）。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞中）。**等待審閱：
1件**（規.二第4節參數掃描方式提案，見`research/AWAITING_REVIEW.md`）。
**下一輪任一軌接手**：交辦佇列已清空（`- [ ]`=0），依round604既有建議
與round601~604連續多輪一致的「三個備援來源已掃無新項」結論，`#50`仍是
三軌唯一未結案方向（tick累積待重新清點，round604記錄12/20），被動等待
總司令對gate50三條件與規.二掃描方式提案的回應；若佇列持續空、且`#50`
仍卡在等待，下一輪可比照round604做法做精簡確認即可，不必每輪重新
全面掃描。完整見`REPORT.md`第605輪心跳（待補）、`PENDING_QUEUE.md`
「2026-09-23總司令裁示【拆除機構約束，改集中版】」章節、
`research/CONCENTRATED_SPEC.md`、`research/exit_rule_lab.py`、
`TRIALS_LEDGER.md`#338~#344。

---

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

（第598輪、第601輪、第602輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
