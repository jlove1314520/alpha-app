# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-10T02:02+08:00（馬拉松第512輪）**——取鎖乾淨（cycle`20260910-020037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 00:30（round509，較舊）／US 01:33（round511，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round511後新增`hypothesis_queue`自走commit（`f5b8b839` `#69`三來源資料可行性查證完成）與一筆互動session commit（`fbf3491c` 建置一.2目標價卡改估值區間，屬App開發track非本馬拉松範圍）；`git status`僅`DEV_QUEUE_PROMPT.txt`／`dev_queue_cycle.log`／`external_connectivity.jsonl`三個自動化檔案在動，屬`hypothesis_queue`自身產物，本輪未觸碰。**額外驗證round511 dev_queue修法效果**：`tail dev_queue_cycle.log`確認`240b1b6d`commit後01:46:02那輪起不再出現「本輪跳過」，改為正常`LOCK_ACQUIRED`＋`PROMPT_READY`，**修法確認有效**，`#69`即為解除阻塞後第一個產出。**依round500~511建議延續採精簡確認**：`data/ticks/`仍2/20（`20260907.parquet`/`20260908.parquet`已finalize，`20260909.parquet.tmp`與`20260909/`原始目錄皆停在09-09 13:45未finalize，較round511無變化，判定屬另一支排程既定行為）；`../PENDING_QUEUE.md`全文搜尋`gate50`無任何結果，`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`本身仍無總司令回應；`STRATEGY_GRAVEYARD.md`掃描`## #6x`/`## #7x`標題，確認最新結案仍為`#68`（2026-09-10，round510結案），與round511盤點一致。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（235列，撞號2組皆為歷史存量不回頭改寫，無新判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.log`/`.md`/`.json`檔案與`git log`/`git status`）。**結論：候選池連續24輪（487~512）維持同一狀態，TW軌本地端無新可推進工作單位**，僅剩`#50`（tick累積2/20，被動等待總司令對gate50提案的回應）。本輪額外產出為驗證round511 dev_queue修法生效。**下一輪任一軌接手**：`#50`gate50提案仍待總司令回應，核准前`#50`本身仍視為未結案；候選池已連續24輪無TW/US/FUT三軌自身可推進的新統計工作單位，建議下一輪繼續採精簡確認節省預算。完整見`REPORT.md`第512輪心跳。

---

**上一則保留（第509輪，供對照）**——取鎖乾淨（cycle`20260910-003037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 23:31（round507，較舊）／US 00:02（round508，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round508後僅自動排程commit（IBKR報價）與`hypothesis_queue`自走commit（`38bfe0ca` `#67`結案FAIL＋新增`#68`：接手陳舊鎖檔回收未commit工作）；`git status`僅`dev_queue_cycle.log`／`external_connectivity.jsonl`兩個自動化log在動，屬另一track自身產物，本輪未觸碰。**結論：候選池連續23輪（487~509）維持同一狀態，TW軌本地端無新可推進工作單位**，僅剩`#50`（tick累積2/20，被動等待總司令對gate50提案的回應）與`hypothesis_queue`自走排程（現在`#67`已結案FAIL、`#68`起）的被動維護。完整見`REPORT.md`第509輪心跳。

---

**上一則保留（第507輪，供對照）**——取鎖乾淨（cycle`20260909-233037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 22:30（round505，較舊）／US 23:00（round506，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`git log`確認round506後僅自動排程commit（IBKR報價）與`hypothesis_queue`自走commit（`28421937` `#67`gate2 TRAIN完整100/100+VAL隨機控制組推進40/100）；`git status`僅`dev_queue_cycle.log`／`external_connectivity.jsonl`兩個自動化log在動，屬另一track自身產物，本輪未觸碰。**結論：候選池連續21輪（487~507）維持同一狀態，TW軌本地端無新可推進工作單位**，僅剩`#50`（tick累積2/20，被動等待總司令對gate50提案的回應）與`hypothesis_queue`自走排程（現在`#67`gate2/`#68`起）的被動維護。完整見`REPORT.md`第507輪心跳。

---

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489/491/493/495/497/499/501/503/505輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
