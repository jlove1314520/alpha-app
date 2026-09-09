# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-10T03:00+08:00（馬拉松第514輪）**——取鎖乾淨（cycle`20260910-030037`）。三軌時間戳：FUT 10:30（round484，最舊，依例外條款不選）／TW 02:02（round512，較舊）／US 02:30（round513，最新）——依round513建議依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round513後僅自動排程commit（IBKR報價）與`hypothesis_queue`自走commit（`c03197d0` 佇列#1~69全數結案，設計新假設#70：選擇權波動度偏斜/尾部避險需求訊號）；`git status`僅`DEV_QUEUE_PROMPT.txt`／`dev_queue_cycle.log`／`external_connectivity.jsonl`三個自動化檔案在動，屬`hypothesis_queue`自身產物，本輪未觸碰。

**本輪額外查證：逐一核實`CALIBRATION_PROBE.md`裁示的300檔重跑複驗清單是否真的全數結案（先前幾輪的state只重複「連續N輪無新工作」的結論，沒有明寫這份清單本身的完整性）**：grep `TRIALS_LEDGER.md`確認TW`#77`（round334，percentile 41.9確定FAIL）、`#79`（round153/#100，percentile 86.1確定FAIL）、`#91`（round106，整體維持FAIL，高關注度組衍生觀察未列入候選）皆已複驗結案；US`#47`（round104，cheap-gate層翻盤CHEAP_PASS但策略層維持FAIL因#41深挖死因不同）、`#52`（性質不同，死因非cheap-gate檢定力問題，已移出待重跑清單）皆已處理；FUT`#34`（round328，查證後判定「無holdout安全的擴大樣本手段」不適用300檔重跑手法，維持FAIL）。**結論：`CALIBRATION_PROBE.md`整份操作指令清單無遺漏項目，候選池連續26輪（487~514）維持同一狀態並非漏做，是真的做完了。**

`data/ticks/`仍2/20（`20260907.parquet`/`20260908.parquet`已finalize，`20260909.parquet.tmp`與`20260909/`原始目錄仍停在09-09 13:45未finalize，較round512無變化）；`PENDING_QUEUE.md`全文搜尋`gate50`無任何結果，`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`本身仍無總司令回應；`STRATEGY_GRAVEYARD.md`掃描`## #6x`/`## #7x`標題，確認最新結案仍為`#68`（2026-09-10，round510結案），與round512/513盤點一致，無新結案。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（241列，撞號2組皆為歷史存量不回頭改寫，本輪未產生新試驗判定——本輪是既有結案結果的完整性複核，非新統計判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`檔案）。**下一輪任一軌接手**：`#50`gate50提案仍待總司令回應，核准前`#50`本身仍視為未結案；`CALIBRATION_PROBE.md`裁示清單已確認全數結案（本輪產出），候選池連續26輪無TW/US/FUT三軌自身可推進的新統計工作單位；依輪替下一輪建議選US軌（TW 03:00 round514最新/US 02:30 round513較舊）。完整見`REPORT.md`第514輪心跳。

---

**上一則保留（第512輪，供對照）**——取鎖乾淨（cycle`20260910-020037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 00:30（round509，較舊）／US 01:33（round511，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round511後新增`hypothesis_queue`自走commit（`f5b8b839` `#69`三來源資料可行性查證完成）與一筆互動session commit（`fbf3491c` 建置一.2目標價卡改估值區間，屬App開發track非本馬拉松範圍）；`git status`僅`DEV_QUEUE_PROMPT.txt`／`dev_queue_cycle.log`／`external_connectivity.jsonl`三個自動化檔案在動，屬`hypothesis_queue`自身產物，本輪未觸碰。**額外驗證round511 dev_queue修法效果**：`tail dev_queue_cycle.log`確認`240b1b6d`commit後01:46:02那輪起不再出現「本輪跳過」，改為正常`LOCK_ACQUIRED`＋`PROMPT_READY`，**修法確認有效**，`#69`即為解除阻塞後第一個產出。**結論：候選池連續24輪（487~512）維持同一狀態，TW軌本地端無新可推進工作單位**，僅剩`#50`（tick累積2/20，被動等待總司令對gate50提案的回應）。完整見`REPORT.md`第512輪心跳。

---

**上一則保留（第509輪，供對照）**——取鎖乾淨（cycle`20260910-003037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 23:31（round507，較舊）／US 00:02（round508，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round508後僅自動排程commit（IBKR報價）與`hypothesis_queue`自走commit（`38bfe0ca` `#67`結案FAIL＋新增`#68`：接手陳舊鎖檔回收未commit工作）；`git status`僅`dev_queue_cycle.log`／`external_connectivity.jsonl`兩個自動化log在動，屬另一track自身產物，本輪未觸碰。**結論：候選池連續23輪（487~509）維持同一狀態，TW軌本地端無新可推進工作單位**，僅剩`#50`（tick累積2/20，被動等待總司令對gate50提案的回應）與`hypothesis_queue`自走排程（現在`#67`已結案FAIL、`#68`起）的被動維護。完整見`REPORT.md`第509輪心跳。

---

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489/491/493/495/497/499/501/503/505/507輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
