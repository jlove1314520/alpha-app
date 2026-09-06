# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T15:33+08:00（馬拉松第401輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 11:30（round398，最舊）／FUT 12:00（round399）／US 12:30（round400，最新）——依輪替選TW。`run_detached.py status`確認全部10個既有job皆`finished`/`failed`/`orphaned`，heavy-job-slot完全空閒（`running=0`）。**本輪工作單位＝`TW_LEADS.md`#2/`CRITERIA_V2_LOCK.md`第39行：`f_value_pe`（FDR重新評分後「待複驗候選（CANDIDATE）」）補做「情境分群檢驗」**——這是該候選進深挖清單前的必要前置關卡，`regime_conditions.py`（2026-08-26主線1）當初只測了7個因子，`f_value_pe`是已知未涵蓋的落差。新增`regime_conditions_value_pe.py`（重用`regime_conditions.py`既有函式，不修改該檔案），改用`factor_ic.SAMPLE_SIZE`現行300檔（`CALIBRATION_PROBE.md`裁示後新常數）跑同一套四組條件（大盤位階/波動度/市值規模/流動性）。`ast.parse`確認語法正確後`run_detached.py submit --name tw_regime_conditions_value_pe --timeout-min 20`（job`20260906-153323-37f5`），session內`wait --max-min 4`仍`STILL_RUNNING`（300檔樣本首次載入預期約13分鐘，未搶跑其他heavy job）。`is_holdout_consumed()`開工前已確認`False`。全程零新增API呼叫（複用既有300檔快取，唯一風險是快取若不完整會觸發新抓取，`load_sample_with_factors()`本身有既有的PIT/holdout檢查機制）。**下一輪TW軌接手**：`run_detached.py status`確認`20260906-153323-37f5`是否`finished`；若是，讀log裡四組條件的mean_ic/n_obs數字，比照`REGIME_CONDITIONS.md`既有7因子的判讀方式（方向是否一致、n_obs≥100門檻）寫入`TRIALS_LEDGER.md`+`TW_LEADS.md`#2+`REGIME_CONDITIONS.md`；若逾20分鐘timeout被砍，記錄`timeout`並檢查是否為300檔首次載入耗時比預期長（可考慮拉長timeout重跑，不需要拆解，此腳本本身運算量不大，瓶頸應是I/O載入）。round398遺留的(1)TRAIN/VAL beta查證、(2)176/248覆蓋率查證兩項仍待查，暫緩（`f_quality_roe_stability`納入`portfolio_multifactor_v2`一事round398已建議擱置，不再是近期優先方向）。完整見`TW_LOG.md`第401輪記錄、`regime_conditions_value_pe.py`（新增，可重複執行）。

---

**上一則保留（第398輪，供對照）**——`f_quality_roe_stability`VAL期逐年分解＋leave-one-year-out：VAL期四年報酬正負交替（2021+15.88%/2022-8.21%/2023+16.15%/2024-11.34%），leave-2021-out與leave-2023-out皆變號，判定CONFIRMED（單一年份驅動、非全期廣泛存在）——round396的PASS判定（`TRIALS_LEDGER.md`#156）因此降級回EXPERIMENTAL。已寫入`TRIALS_LEDGER.md`#158、`TW_LEADS.md`#3更新。完整見`TW_LOG.md`第398輪記錄。

---

**上一則保留（第396輪，供對照）**——收成TW自己的背景job`20260906-083408-d6ab`（`tw_deep_dive_quality_roe_stability_full_rerun`，300檔乾淨樣本完整重跑）：`f_quality_roe_stability`唯一disqualify理由（TRAIN/VAL絕對報酬正負號不一致）解決，TRAIN由負轉正+7.25%~7.59%，VAL維持正但量級萎縮至+0.98%~1.25%（約1/13），判定由EXPERIMENTAL上修為PASS（1b深挖關卡）。已寫入`TRIALS_LEDGER.md`#156、`TW_LEADS.md`#3。**（後續：round398已針對VAL量級萎縮做逐年分解，發現是單一年份驅動的巧合淨額，判定已降級回EXPERIMENTAL，見上方條目。）**完整見`TW_LOG.md`第396輪記錄。
