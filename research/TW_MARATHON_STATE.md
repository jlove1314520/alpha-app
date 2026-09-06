# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T16:30+08:00（馬拉松第403輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 12:00（round399，最舊，但round399明文寫下一輪選到FUT要讓回TW/US）／TW 15:33（round401）／US 16:06（round402，最新）——依換軌例外條款在TW/US間選較舊的TW。`run_detached.py status`確認round401投遞的`20260906-153323-37f5`（`tw_regime_conditions_value_pe`）已`finished, exit=0`（8.0分鐘），heavy-job-slot空閒。**本輪工作單位(1)＝完成`CRITERIA_V2_LOCK.md`第39行第一關（情境分群檢驗）判讀**：`f_value_pe`四組條件（大盤位階/波動度/市值規模/流動性）**8組全部為正、無方向反轉，n_obs全部遠超100門檻**（大盤位階：多頭+0.0516/空頭+0.0984；波動度：高+0.0570/低+0.0696；市值：大+0.0827/中+0.0362/小+0.0593；流動性：高+0.0561/低+0.0623），判定通過第一關（比照`REGIME_CONDITIONS.md`既有7因子的判讀方式）。空頭強於多頭跟`f_revenue_surprise`「危機期更強」同一種模式，經濟解釋成立（價值折價保護在熊市更明顯兌現）。已寫入`TRIALS_LEDGER.md`#166、`TW_LEADS.md`#2、`REGIME_CONDITIONS.md`新增小節。**本輪工作單位(2)＝投遞第二關（成本敏感度）背景工作**：新增`deep_dive_f_value_pe.py`（比照`deep_dive_f_value_pb.py`模板，十分位多空/TRAIN-VAL/1x-2x-3x成本/100次隨機控制組/CAPM beta，改用現行300檔樣本），`run_detached.py submit --name tw_deep_dive_value_pe_cost_sensitivity --timeout-min 30 --expect data/deep_dive_f_value_pe.csv`（job`20260906-163407-6cc8`），session內`wait --max-min 4`仍`STILL_RUNNING`（300檔首次載入預期約13分鐘，未逾常）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫（複用round401已建立的300檔因子快取）。**下一輪TW軌接手**：`run_detached.py status`確認`20260906-163407-6cc8`是否`finished`；若是，讀`data/deep_dive_f_value_pe.csv`的TRAIN/VAL兩期×三成本倍數`ann_return`/`beta`/`alpha`/`random_control_percentile`，比照`deep_dive_f_value_pb.py`既有判讀方式（percentile是否達99~100量級、方向是否一致、beta是否偏離market-neutral）寫入`TRIALS_LEDGER.md`新編號+`TW_LEADS.md`#2；若逾30分鐘timeout被砍，記錄`timeout`並檢查首次load耗時。若成本敏感度也過，`CRITERIA_V2_LOCK.md`第39行流程最後一關（alpha/beta顯著性）尚未設計，留待規劃。完整見`TW_LOG.md`第403輪記錄、`deep_dive_f_value_pe.py`（新增，可重複執行）。

---

**上一則保留（第401輪，供對照）**——投遞`f_value_pe`情境分群檢驗背景工作（job`20260906-153323-37f5`），本輪(round403)已收成完畢，判定與後續見上方最新條目。完整見`TW_LOG.md`第401輪記錄、`regime_conditions_value_pe.py`（新增，可重複執行）。

---

**上一則保留（第398輪，供對照）**——`f_quality_roe_stability`VAL期逐年分解＋leave-one-year-out：VAL期四年報酬正負交替（2021+15.88%/2022-8.21%/2023+16.15%/2024-11.34%），leave-2021-out與leave-2023-out皆變號，判定CONFIRMED（單一年份驅動、非全期廣泛存在）——round396的PASS判定（`TRIALS_LEDGER.md`#156）因此降級回EXPERIMENTAL。已寫入`TRIALS_LEDGER.md`#158、`TW_LEADS.md`#3更新。完整見`TW_LOG.md`第398輪記錄。
