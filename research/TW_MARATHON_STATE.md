# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-23T04:3x+08:00（馬拉松第608輪，研究帽）**——取鎖乾淨
（cycle`20260923-043037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0，23條`- [!]`阻塞中；逐一核對阻塞項開頭解除條件，皆未到解除
時間點，維持`- [!]`。**佇列深度自檢**：`- [ ]`=0（<12下限），round599~
607已連續多輪確認三個備援來源掃無新項，本輪不重複全面掃描。`run_
detached.py status`確認`running=0`（151筆歷史，無running job需收成）。
`git status`僅例行排程檔案（`audit_report.json`/`factory_stability*`/
`dev_queue_cycle.log`等），無孤兒未commit產出，round607已修復的git
stash衝突未再復發。`#50`（唯一未結案方向）tick累積實測仍**12/20**
（`data/ticks/`，09-23當日盤中尚未finalize，較round604/607無變化）。
**本輪工作單位＝文件維護**：核對`CONCENTRATED_SPEC.md`第3節現況時
發現`PENDING_QUEUE.md`規.二條目內一句話已過時——原記「S&P500 Total
Return序列缺口依然未解決」，但round606（US軌）已新增
`research/sp500_tr_series.py::load_sp500tr_full_history()`並同步更新
`CONCENTRATED_SPEC.md`第3/11節解決此缺口，唯`PENDING_QUEUE.md`規.二
條目本體的這句話未跟著更正，若不修會誤導下一輪讀者以為此缺口仍待
解決。依`CLAUDE.md`三之二節「純bug修復可直接做」精神（更正一句已被
既有工作取代的過時陳述，不是新裁示也不涉及判斷取捨）修正，補充完整
脈絡並註明「解決缺口≠核准推進」與round606出處。**至此TW/US兩軌基準
序列地基工程（0050含息總報酬／S&P500 Total Return）皆已就緒**，但
規.二第4節參數掃描方式仍待總司令裁示（`AWAITING_REVIEW.md`：等待中
1件，非本輪新增），`concentrated_backtest.py`不得動筆。純文件更正，
非統計判定，不觸發`register_trial()`。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（346列，本輪未新增判定）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本檔案、`git status`、
`run_detached.py status`、`ls research/data/ticks/`）。`PROGRESS_
HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**（23條
`- [!]`阻塞中）。**等待審閱：1件**（規.二第4節參數掃描方式提案，非
本輪新增，延續中）。**下一輪任一軌接手**：`#50`仍是三軌唯一未結案
方向，被動等待tick累積至20（12/20）與總司令對gate50三條件的回應；
規.二第4節掃描方式提案仍待總司令裁示，是目前唯一阻擋集中版框架
實際動筆的關卡；三個備援來源已連續多輪掃無新項，若佇列持續空建議
下一輪比照本輪做法做精簡確認即可，不必每輪重新全面掃描；依輪替
下一輪建議選US或FUT軌（TW本輪剛碰過）。完整見`REPORT.md`第608輪
心跳、`PENDING_QUEUE.md`「2026-09-23【規.二後續】」章節（規.二條目
更正）。

---

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

（第598輪、第601輪、第602輪、第603輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
