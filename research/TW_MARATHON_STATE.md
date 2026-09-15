# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-15T14:30+08:00（馬拉松第537輪）**——取鎖乾淨（cycle`20260915-143037`）。開工先照CLAUDE.md「交辦優先於自走」鐵律讀`PENDING_QUEUE.md`：2條阻塞項（S4U排程註冊／claude CLI非互動驗證，等待總司令有管理員權限）維持阻塞；題材七維持部分完成待續（由`hypothesis_queue`軌自身持續推進，累計110/259檔，非本馬拉松三軌範圍）；gate50三條件仍待總司令釐清；另發現同一時段互動session已把「研究.c 盤中微結構假設」標記`⛔自走中止`交還總司令（14:01，需總司令親自操作，非馬拉松範圍）。**交辦佇列對本馬拉松三軌而言無可執行未開始項，回落自走**。依round536建議依輪替選TW。查`run_detached.py status`：`running=0`（60筆歷史紀錄，無新增）；`git log`確認round536自身commit後，只有`hypothesis_queue`軌commit（題材七第六批）與互動session的`研究.a`／`研究.b`／IBKR診斷commit，均非本馬拉松三軌範圍，未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區；`git status`工作目錄有其他排程軌殘留未commit變更（`PENDING_QUEUE.md`等，經比對是互動session剛做的「研究.c」標記與`dev_queue`／`connectivity`軌既有殘留），本輪未觸碰、未越權處理。**核實現狀（本輪唯一實質變化）**：`research/data/ticks/`累積進度由**6/20→7/20**（新增`20260915.parquet`，資料涵蓋至13:45:00與台指期日盤收盤時間吻合，判定已finalize；`20260907`/`08`/`09`/`10`/`11`/`14`/`15`共7個交易日，距20日仍差13日）——`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`記錄的架構性問題（現行tick訂閱清單皆為大型股，不在#50要求的500萬~5,000萬成交值區間）仍待總司令核准，即使累積滿20日這份tick仍不足以支撐#50 cheap gate；`PENDING_QUEUE.md`gate50查證段落（現位於第759~766行）內容與round517查證時相同，總司令尚未回應三條件具體定義，`#50`維持未解鎖；`STRATEGY_GRAVEYARD.md`本馬拉松三軌自身最新結案仍為`#68`（round510），無新結案；另複查確認0a節四條方向中`#49`/`#51`（三個子事件＋US版）/`#52`（TW＋US三個item family）全數已FAIL結案，僅`#50`仍卡阻塞、尚未正式結案，故協定0a節「無可驗證預測優勢」提報門檻尚未觸發。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（244列，本輪未產生新試驗判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`/`.json`/`.parquet`檔案與`git log`/`git status`/`run_detached.py status`）。**結論：候選池狀態與round487~536時實質相同（僅tick累積由6/20進到7/20），TW/US/FUT三軌自身仍無新可推進工作單位，僅剩`#50`被動等待（tick累積+提案核准雙重阻塞）與gate50三條件待總司令回應**。**下一輪任一軌接手**：`#50`gate50原文仍待總司令回應；`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`仍待核准；FUT仍維持skip；依輪替下一輪建議選US軌。完整見`REPORT.md`第537輪心跳、`MARATHON_STATE.md`（輪次計數器537）。

---

**上一則保留（第535輪，供對照）**——取鎖乾淨（cycle`20260915-110037`）。依round534建議依輪替選TW。**核實現狀**：`research/data/ticks/`累積進度**6/20**，距20日仍差14日；`PENDING_QUEUE.md`gate50查證段落仍原封不動，`#50`維持未解鎖。`trial_registry.py --check`exit=0 PASS（244列）。`is_holdout_consumed()`確認`False`。**結論**：候選池狀態與round527~534時實質相同，僅剩`#50`被動等待。完整見`REPORT.md`第535輪心跳。

---

**上一則保留（第533輪，供對照）**——取鎖乾淨（cycle`20260915-090037`）。依round532建議依輪替選TW。**核實現狀**：`data/ticks/`累積進度仍**6/20**，距20日仍差14日；`PENDING_QUEUE.md`gate50查證段落仍原封不動，`#50`維持未解鎖。`trial_registry.py --check`exit=0 PASS（244列）。`is_holdout_consumed()`確認`False`。**結論**：候選池狀態與round527~532時實質相同，僅剩`#50`被動等待。完整見`REPORT.md`第533輪心跳。


（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489/491/493/495/497/499/501/503/505/507/509/512/514/516/518/521/523/525/527/529/531輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
