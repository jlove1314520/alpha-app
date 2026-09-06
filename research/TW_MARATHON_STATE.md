# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T17:31+08:00（馬拉松第405輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 12:00（round399，最舊，但round399明文寫下一輪選到FUT要讓回TW/US）／TW 16:30（round403）／US 17:00（round404，最新）——依換軌例外條款在TW/US間選較舊的TW。`run_detached.py status`確認round403投遞的`20260906-163407-6cc8`（`tw_deep_dive_value_pe_cost_sensitivity`）**已`timeout`（30分鐘被砍，`exit=-9`）**，這件事round404的US軌心跳已附帶記錄過。**本輪工作單位＝重投該工作、拉長timeout**：`log`確認上次只跑完「TRAIN 1x」一組（含100次隨機控制組）就吃掉大半個30分鐘window（首次load 300檔樣本＋一組完整combo），推算6組（2期×3成本）× 100 draws全跑完量級落在90~150分鐘，跟US軌`deep_dive_f_us_value_bm_clean_universe.py`（93.5分鐘）、`deep_dive_f_us_low_vol_clean_universe_retry`（136.1分鐘）同量級，不是台股慣用的20~30分鐘。原地重跑`python research/deep_dive_f_value_pe.py`（程式碼本身未改，純粹是同一份300檔樣本首次load+6組combo比預期慢，非bug），`run_detached.py submit --name tw_deep_dive_value_pe_cost_sensitivity_retry --timeout-min 150 --expect data/deep_dive_f_value_pe.csv`（job`20260906-173133-fce9`），session內`wait --max-min 2`仍`STILL_RUNNING`（符合預期，2分鐘遠不足6組跑完）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫（複用既有300檔因子快取，未搶其他heavy-job-slot——確認`run_detached.py status`本輪開工時running=0）。**下一輪TW軌接手**：`run_detached.py status`確認`20260906-173133-fce9`是否`finished`（150分鐘timeout，可能需要再等1~2輪才會完成）；若`finished`，讀`data/deep_dive_f_value_pe.csv`的TRAIN/VAL兩期×三成本倍數`ann_return`/`beta`/`alpha`/`random_control_percentile`，比照`deep_dive_f_value_pb.py`既有判讀方式（percentile是否達99~100量級、方向是否一致、beta是否偏離market-neutral）寫入`TRIALS_LEDGER.md`新編號+`TW_LEADS.md`#2；若逾150分鐘仍`timeout`，代表這個構造（300檔×6組×100draws在單一session原地跑）本身太重，下一步要考慮拆成6個獨立job分開投遞而非一次跑完。若成本敏感度也過，`CRITERIA_V2_LOCK.md`第39行流程最後一關（alpha/beta顯著性）尚未設計，留待規劃。完整見`TW_LOG.md`第405輪記錄、`TRIALS_LEDGER.md`附註。

---

**上一則保留（第403輪，供對照）**——收成round401投遞的`20260906-153323-37f5`並完成`CRITERIA_V2_LOCK.md`第39行第一關（情境分群檢驗）判讀：`f_value_pe`四組條件8組全部為正、無方向反轉，通過第一關，寫入`TRIALS_LEDGER.md`#166、`TW_LEADS.md`#2、`REGIME_CONDITIONS.md`。接著投遞第二關（成本敏感度）背景工作`20260906-163407-6cc8`——**該工作後續於30分鐘timeout被砍，round405已重投更長timeout版本，見上方最新條目**。完整見`TW_LOG.md`第403輪記錄、`deep_dive_f_value_pe.py`（新增，可重複執行）。

---

**上一則保留（第401輪，供對照）**——投遞`f_value_pe`情境分群檢驗背景工作（job`20260906-153323-37f5`），本輪(round403)已收成完畢，判定與後續見上方最新條目。完整見`TW_LOG.md`第401輪記錄、`regime_conditions_value_pe.py`（新增，可重複執行）。
