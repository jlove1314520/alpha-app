# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

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

---

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

（第592輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
