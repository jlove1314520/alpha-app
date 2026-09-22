# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-22T13:3x+08:00（馬拉松第594輪）**——
取鎖乾淨（cycle`20260922-133037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=2（`財報原子.補快取`／`籌碼原子.補上櫃三大
法人歷史`），皆持續回補中，`run_detached.py status`確認running=0（上一輪
兩批FinMind job與TPEx batch3皆已收成完畢）。**佇列深度自檢**：`- [ ]`
僅2項，低於`queue_depth_config.py`門檻12，依規則需自走補件到20項——
`[自行裁量]`檢查`data/rate_limit_state.json`確認FinMind上次請求
12:42:32，距本輪開工僅約48分鐘不到一小時安全間隔（既有慣例約需滿一小時
才續投避免撞402），故本輪不投FinMind批次；掃描`TW_LEADS.md`/
`STRATEGY_GRAVEYARD.md`「下一步」相關段落與`HYPOTHESIS_QUEUE.md`最新
`#76`（VIX期限結構regime訊號，資料源起點探測已完成，下一步為cheap
gate1）——`#76`屬`hypothesis_queue`自己的獨立自走軌道範圍（有自己的
continuation prompt自動接續），不重複寫入`PENDING_QUEUE.md`造成雙軌
競爭；`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`近期「下一步」條目（#19事件
驅動SUE延伸變體/連續分數加權、#52-US 8-K放大樣本）皆屬「需先設計具體
構造才能開跑」而非「可立即動手」的候選，與2026-09-19深讀二.3六項徹底
搜尋後仍只找到9項（現已完成7項只剩2項）的結論一致，**本輪判斷維持
現況2項、不硬湊新項**，理由記於此供下一輪覆核。**本輪工作單位＝續投
`籌碼原子.補上櫃三大法人歷史`batch4**（單工作槽規則，FinMind未滿冷卻
故單工作槽留給TPEx）：`run_detached.py submit --name tpex3insti_hist_b4
--timeout-min 25 --cwd . -- python -u backfill_tpex_3insti_history.py
--batch-size 300`（job`20260922-133117-9ffe`），依歷史批次耗時約
16~17min＞本輪25分鐘硬超時安全邊際，session內未等待完成，留給下一輪
`run_detached.py status`收成。`trial_registry.py --check`（`PYTHONIOENCODING=
utf-8`）exit=0 PASS（328列，本輪未新增判定，純債務/維運性質工作）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，零新增外部API
呼叫（本輪僅投遞TPEx job，未實際執行FinMind請求）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩2條未開始**（皆持續回補中，非新交辦）。
等待審閱：0件。**下一輪**：先`run_detached.py status`確認
`20260922-133117-9ffe`是否`finished`，讀remaining決定是否需batch5；
`財報原子.補快取`距12:42:32已逾一小時後可續投b13/b14（優先覆蓋率離60%
較遠者，目前ocf/equity差距最大）；`STRATEGY_GRAVEYARD.md`「事件驅動」
結案後，若總司令核准可評估`MARATHON_PROTOCOL.md`0a節四條方向是否已
全數窮盡。完整見`PENDING_QUEUE.md`籌碼原子.補上櫃三大法人歷史條目。

---

**最後更新：2026-09-22T12:5x+08:00（馬拉松第593輪）**——
取鎖乾淨（cycle`20260922-123037`）。開工先照「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=2（`財報原子.補快取`／`籌碼原子.補上櫃三大
法人歷史`），兩項皆FinMind/TPEx回補進行中，優先收成上一輪投遞的背景job
再續補。**收成`方法.三續.GATE_SEQUENCE驗證`**：`run_detached.py status`
確認`20260922-104311-7d2c`（round592投遞）狀態`finished`（8.8min，
`expect_exists=True`），讀`event_driven_gate_sequence_result.json`——
**E1財報SUE(n=6706)與E2月營收SUE(n=20339)皆FAIL**：兩者共同卡在gate2
隨機控制組（訊號統計量分別0.0064/0.0039，皆未超過控制組最大值0.0093/
0.0055，2026-09-07標準升級要求超過控制組最大值非僅高百分位）；E2另外
train_val_oos也未過（train+0.0065→val-0.0008正負號翻轉）。E1的
train_val_oos/成本敏感度/leave_one_out三關皆PASS，唯一敗因是gate2。
`register_trial()`登記`TRIALS_LEDGER.md`#325(E1)/#326(E2)，寫入
`STRATEGY_GRAVEYARD.md`「事件驅動SUE訊號」段落與`TW_LEADS.md`#19，
`PENDING_QUEUE.md`該條目已標`[x]`完成。事件驅動大類（E1/E2）至此結案
FAIL，地基程式碼保留供未來變體（連續分數加權/券商共識調整版）重用。
**續投`財報原子.補快取`**：距上次FinMind請求（07:47:39）已逾4.75小時，
冷卻早解除，投b11/b12（絕對路徑`--cwd`，job`20260922-123258-a622`／
`20260922-123752-49c7`，共188次請求全成功0個402），remaining_pairs
2077→1889。`fin_atom_coverage.py`重跑：total_assets全體57.6%（前
53.9%）、equity 52.0%、inventory 54.3%、receivable 55.4%、ocf 52.5%，
五者仍<60%→維持`- [ ]`續補。**確認`籌碼原子.補上櫃三大法人歷史`
batch3**：`20260922-115518-f116`（round592投遞）`exit=0`（16.9min），
累計快取811→1111/1718，remaining=607；本輪單工作槽讓給FinMind回補，
未投batch4。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（328列，最大編號#326，本輪新增2筆判定）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，全程FinMind
請求皆計入既有額度追蹤，TPEx確認查詢零新增外部API呼叫。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩2條
未開始**（`財報原子.補快取`／`籌碼原子.補上櫃三大法人歷史`，皆持續回補
中，非新交辦）。等待審閱：0件。**下一輪**：先跑
`python research/run_detached.py status`確認本輪未等待完成的
`fin_atom_coverage.py`背景檢查（已在本輪內完成，無殘留）；續投
`財報原子.補快取`b13/b14或`籌碼原子.補上櫃三大法人歷史`batch4（單工作
槽輪流，二擇一，優先覆蓋率離60%較遠者，目前ocf/equity差距最大）；
`STRATEGY_GRAVEYARD.md`「事件驅動」結案後，若總司令核准可評估
`MARATHON_PROTOCOL.md`0a節四條方向是否已全數窮盡（#49/#50/#51/#52
現況需重新盤點）。完整見`PENDING_QUEUE.md`方法.三續條目、
`TRIALS_LEDGER.md`#325/#326、`STRATEGY_GRAVEYARD.md`「事件驅動SUE訊號」
段落、`TW_LEADS.md`#19。

**最後更新：2026-09-22T10:5x+08:00（馬拉松第592輪，互動視窗CC接手）**——
開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：`- [ ]`=2，兩項皆「登記
缺口暫不做只登記」（`出場.零`／`宇宙.零`），文字本身即登記，已標`[x]`
完成，無需額外動作；改做`- [!]`裡真正可動手的`方法.三續.GATE_SEQUENCE
驗證`。新建`research/event_driven_gate_sequence.py`：對`event_driven_
prototype.py`的E1/E2事件表補上四關（隨機控制組排列檢定比照
`control_group_standard.py::evaluate_vs_control()`／train-val OOS切分／
成本敏感度[自行裁量改用`margin_of_safety.py::passes_worst_case()`，理由
`CLAUDE.md`七之三節已廢止機械倍數規則]／leave-one-out）。**實測發現
效能地雷**：`tail_test()`預設`n_bootstrap=10000`單次呼叫（sig~700/
ctl~6000規模）耗時5.28秒，直接同步執行整條GATE_SEQUENCE（200次排列
檢定+leave-one-out×2事件類型）遠超5分鐘門檻，第一次同步嘗試280秒逾時
中止、只印出E1標頭無結果。**[自行裁量]修法**：新增`AUX_N_BOOTSTRAP=500`
套用在排列檢定/leave-one-out內部呼叫（不影響其餘關卡），實測同一呼叫
降到0.12秒（43倍）——理由：bootstrap均值點估計不隨n_bootstrap系統性
偏移，只是CI精度降低，這裡只需要點估計判方向。改完依`MARATHON_
PROTOCOL.md`0b節規則改走`run_detached.py submit`
（job_id=`20260922-104311-7d2c`，`--timeout-min 30`），session內等4分鐘
仍未結束（`watchdog_alive=True`非卡死，計算量仍偏大），轉交下一輪收成。
`trial_registry.py --check`未變動（本輪尚未新增登記列，等下一輪讀到
gate結果才登記）。未動凍結區、holdout未動、零新增外部API呼叫。
**下一輪**：先跑`python research/run_detached.py status`確認
`20260922-104311-7d2c`是否`finished`，讀`event_driven_gate_sequence_
result.json`依verdict登記`TRIALS_REGISTRY`（CHEAP_PASS或FAIL＋
failed_gates寫`STRATEGY_GRAVEYARD.md`）；若`timeout`代表`AUX_
N_BOOTSTRAP=500`仍不夠快，需再評估降`N_DRAWS_PER_VARIANT`或向量化重寫。
完整見`PENDING_QUEUE.md`方法.三續.GATE_SEQUENCE驗證條目、
`research/event_driven_gate_sequence.py`（新增）。

（第591輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）


