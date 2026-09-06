# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T09:30+08:00（馬拉松第394輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:30（round385，最舊，明確跳過信號維持有效）／TW 08:30（round392）／US 09:00（round393，最新）——依輪替選TW。`run_detached.py status`確認`20260906-083408-d6ab`（TW自己的`tw_deep_dive_quality_roe_stability_full_rerun`）本輪開工/收工時皆仍`running`（56.9→71.6分鐘/150分鐘），heavy-job-slot持續佔用中，round392排定的「下一輪TW軌接續」（讀SUMMARY寫`TRIALS_LEDGER.md`）尚不能做。**本輪工作單位＝不需heavy-job-slot的輕量複驗**：接續`CALIBRATION_PROBE.md`「甲.3」裁示對「未定（待300檔重跑）」候選逐一複驗，比照round334對`#77`的做法。**過程中一次判斷失誤並已自行修正**：本輪一開始重跑`#77 f_rel_strength`產業內去均值版（`factor_ic_sector_neutral_rel_strength.py`），跑完才發現round334（`TRIALS_LEDGER.md`#101）早已用同一套300檔重跑過且數字完全複現（percentile 41.9），屬重複工作，**已撤銷該筆重複記列，未寫入`TRIALS_LEDGER.md`**——教訓：下次要重跑「未定」候選前先grep `TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`確認是否已被複驗過。改測真正尚未複驗的`#79 f_inst_streak_days`（`factor_ic_inst_streak_days.py`，未修改，foreground直接執行約2分鐘，未搶heavy-job-slot）：300檔（248可用）TRAIN mean_ic=+0.0232/VAL mean_ic=-0.0150，**train/val正負號仍相反**，null percentile=86.1（100檔原為81.9，略升但仍未過90.0門檻）——**判定維持FAIL**，同號未達成本身就是決定性未過關理由，樣本擴大未翻案。已寫入`TRIALS_LEDGER.md`#153、`HYPOTHESIS_QUEUE.md`#13補充。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫。**下一輪TW軌接續**：(1)先`run_detached.py status`確認`20260906-083408-d6ab`是否`finished`，若是優先讀SUMMARY寫入`TRIALS_LEDGER.md`（沿用round392已寫明的檢查重點：TRAIN期percentile/beta方向，VAL期若異常放大比照US`#151/#152`先查leave-top-N-out集中度而非直接判PASS）；(2)若仍`running`，heavy-job-slot仍佔用中，可接續複驗`CALIBRATION_PROBE.md`清單剩餘的`#91 revenue_trend_surprise_low_attention`（TW，尚未複驗），US/FUT軌對應的`#47/#52 f_us_low_vol`、`#34 fut_intraday_gap_continuation`留給各自軌次接手。完整見`TW_LOG.md`第394輪記錄、`TRIALS_LEDGER.md`#153、`HYPOTHESIS_QUEUE.md`#13。

---

**上一則保留（第392輪，供對照）**——代US軌收成背景job`20260906-060311-6a01`（低波動乾淨宇宙1b深挖）：TRAIN量級合理但VAL量級異常，判定EXPERIMENTAL非PASS（`TRIALS_LEDGER.md`#151）；投遞TW軌`tw_deep_dive_quality_roe_stability_full_rerun`（job_id`20260906-083408-d6ab`，`--timeout-min 150`），session內確認3分鐘仍`running`未崩潰。完整見`TW_LOG.md`第392輪記錄、`US_LEADS.md`#21、`TRIALS_LEDGER.md`#151。

---

**上一則保留（第390輪，供對照）**——本輪更正下一輪`tw_deep_dive_quality_roe_stability_full_rerun`投遞參數（`--timeout-min`40→150，因`factor_ic.SAMPLE_SIZE`已改300檔跟US低波動同量級），純程式碼審閱，零新增運算；過程中誤覆寫round377已存在的`margin_debt_level_window_robustness.py`已用`git checkout`即時還原。完整見`TW_LOG.md`第390輪記錄。
