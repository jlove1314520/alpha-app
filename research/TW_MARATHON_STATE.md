# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-19T16:10+08:00（馬拉松第564輪）**——取鎖乾淨（cycle`marathon-20260919-160057`）。交辦優先：處理`借券費率.放大閾值重測`，完成（詳見`REPORT.md`第564輪、`STRATEGY_GRAVEYARD.md`「f_lending_fee_spike v2」）：6格（Z∈{2,3,4}×N∈{40,60}）0通過、3x成本全轉負、毛幅度N40→N60飽和，#264~#269 FAIL，整條長持有期降曝險版結案。交辦佇列剩4條未開始（零股失衡度連續曝險版、fx_twd_gate改央行源，另兩項歸hypothesis_queue軌）。無阻塞。（第554輪原文：見下方。）

---

**最後更新：2026-09-19T02:33+08:00（馬拉松第554輪）**——取鎖乾淨（cycle`20260919-023037`）。開工先照CLAUDE.md「交辦優先於自走」鐵律讀`PENDING_QUEUE.md`：全文0條`- [ ]`，22條`- [!]`全數blocked（逐項核對：多數待總司令本人操作/裁示，其餘為資料累積型阻塞——tick 10/20、法人歷史11個交易日、FinMind額度）。`data/rate_limit_state.json`確認FinMind於2026-09-18T19:36:14 UTC因402再次封鎖，`blocked_until`＝台北03:36:14，本輪開工02:33尚未解封，稽核.三(a)待此解封，依協定不sleep等待，留給下一輪自動接續。**交辦佇列無可執行未開始項，回落自走**，依round552建議依輪替選TW（TW round543=09-16 09:00最舊，US round552=09-19 00:34較新，round553為交辦未觸碰三軌）。查`run_detached.py status`：running=0（72筆歷史，較round552新增2筆`20260919-013209-f86a`failed/`20260919-013225-2a20`finished，皆屬交辦round553的稽核.三(a)回補job，非本三軌）；`git log`確認round553之後新增commit全數為IBKR報價排程／DevQueue／Hypothesis-queue自走維運commit（含`重構.三`美股SEC Form4內部人交易新假設軸#75設計），均非本馬拉松三軌範圍，未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區。**核實現狀**：`research/data/ticks/`累積**10/20**（與round552相同，`20260918.parquet`後未再新增，尚無新交易日finalize）；`STRATEGY_GRAVEYARD.md`本馬拉松三軌自身最新結案仍為`#68`（round510），無新結案（`#75`為hypothesis_queue軌新設計，非本三軌）；0a節四條方向中`#49`/`#51`/`#52`全數已FAIL結案，僅`#50`仍卡阻塞（tick累積+`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`提案核准+gate50三條件三重依賴），尚未正式結案，協定0a節「無可驗證預測優勢」提報門檻尚未觸發。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（246列，與round552相同，本輪未產生新試驗判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`/`.json`檔案與`git log`/`git status`/`run_detached.py status`）。**結論：候選池狀態與round487~552時實質相同（連續約66輪無新工作單位），TW/US/FUT三軌自身仍無新可推進工作單位，僅剩`#50`被動等待**。**下一輪任一軌接手**：優先檢查FinMind是否已解封（台北03:36後）並接續稽核.三(a)（非本三軌範圍，供接手輪次參考）；`#50`gate50原文仍待總司令回應；FUT仍維持skip；依輪替下一輪建議選US軌。完整見`REPORT.md`第554輪心跳、`MARATHON_STATE.md`（輪次計數器554）。

---

**上一則保留（第543輪，供對照）**——取鎖乾淨（cycle`20260916-090037`）。依round542建議依輪替選TW。**核實現狀**：0a節四條方向中`#49`/`#51`/`#52`全數已FAIL結案，僅`#50`仍卡阻塞。`trial_registry.py --check`exit=0 PASS（246列）。`is_holdout_consumed()`確認`False`。**結論**：候選池狀態與round487~542時實質相同，僅剩`#50`被動等待。完整見`REPORT.md`第543輪心跳。

---

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489/491/493/495/497/499/501/503/505/507/509/512/514/516/518/521/523/525/527/529/531/533/535/537/539輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
