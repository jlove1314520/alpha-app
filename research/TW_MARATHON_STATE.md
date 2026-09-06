# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T08:30+08:00（馬拉松第392輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:30（round385，最舊，round385自己結論「trend+oi四種組合/變體全FAIL，優先權回TW/US，除非有全新機制假說」，明確跳過信號）／TW 07:30（round390）／US 08:00（round391，最新）——TW較US舊，且US round391已把heavy-job-slot佔用狀況寫清楚，選TW。開工前`run_detached.py status`確認US背景job`20260906-060311-6a01`已`finished`(exit=0,expect_exists=True)，heavy-job-slot已釋放。**本輪工作單位分兩部分**：(1)**先代US軌收成該結果**（非重算的順手工作，round390已預先寫明此judgment call）：`run_detached.py log --tail 80`讀出SUMMARY——TRAIN(2015-2020)3個成本倍數ann_return+19.75%~+20.99%/beta-0.316~-0.317/alpha+30.30%~+31.65%/random_percentile 100.0（量級與BAB文獻一致，合理）；**VAL(2020-2024)3個成本倍數ann_return+90.64%~+92.46%/beta-0.820~-0.821/alpha+125.00%~+127.17%/random_percentile 100.0**——TRAIN/VAL同號、皆贏隨機控制組，表面像PASS，但VAL期報酬量級（年化90%+）與beta（較TRAIN惡化2.6倍）在經濟上不尋常，跟`f_us_value_bm`舊池子#128死因（乾淨IC過關但回測量級不合理）同一種風險模式，且VAL期涵蓋2022升息熊市可能是regime-specific單一年份驅動（同`margin_debt_level_v1`#141-143教訓）。**判定：EXPERIMENTAL，不判定PASS**，已寫入`TRIALS_LEDGER.md`#151、`US_LEADS.md`#21更新，下一步指定給US軌：VAL期逐年拆解排除2022年集中驅動。(2)**執行TW軌本輪工作單位**：heavy-job-slot空出後，投遞round390排定的`python research/run_detached.py submit --name tw_deep_dive_quality_roe_stability_full_rerun --timeout-min 150 -- python -u research/deep_dive_f_quality_roe_stability.py`（job_id`20260906-083408-d6ab`），session內`run_detached.py wait --max-min 3`確認3分鐘後仍`running`（未立即崩潰），依協定breakaway繼續在背景執行150分鐘上限內。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫。**下一輪TW軌接續**：`run_detached.py status`確認`20260906-083408-d6ab`是否`finished`；若是，讀SUMMARY寫入`TRIALS_LEDGER.md`（**優先檢查TRAIN期percentile與beta方向**，且鑑於本輪US低波動深挖VAL期出現量級異常的教訓，**這次TW的300檔重跑若VAL期也出現類似遠超TRAIN的異常放大量級，同樣不要直接判PASS，先排查是否為2022年單一年份或其他集中事件驅動**）。完整見`TW_LOG.md`第392輪記錄、`US_LEADS.md`#21、`TRIALS_LEDGER.md`#151。

---

**上一則保留（第390輪，供對照）**——本輪更正下一輪`tw_deep_dive_quality_roe_stability_full_rerun`投遞參數（`--timeout-min`40→150，因`factor_ic.SAMPLE_SIZE`已改300檔跟US低波動同量級），純程式碼審閱，零新增運算；過程中誤覆寫round377已存在的`margin_debt_level_window_robustness.py`已用`git checkout`即時還原。完整見`TW_LOG.md`第390輪記錄。

---

**上一則保留（第389輪，供對照）**——鎖定`TW_LEADS.md`第55行「最高優先（第107輪新發現）」但橫跨60餘輪從未真正執行的待辦：完整重跑`deep_dive_f_quality_roe_stability.py`本身（含完整100次隨機控制組×2期×3成本倍數＝606次回測），因round107只重跑了分解腳本真實腿位、未重跑完整隨機控制組。`run_detached.py submit`因US工作佔用exit=3被拒絕，改做不需重算的工作：確認待辦仍有效、更新`TW_LEADS.md`過時的`MI_MARGN`備註。完整見`TW_LEADS.md`第55行備註更正、`TW_LOG.md`第389輪記錄。（第388輪原文已搬至`TW_STATE_ARCHIVE.md`。）
