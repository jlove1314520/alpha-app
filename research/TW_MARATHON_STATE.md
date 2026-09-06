# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T10:30+08:00（馬拉松第396輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:30（round385，最舊，明確跳過信號維持有效）／TW 09:30（round394）／US 10:00（round395，最新）——依輪替選TW。**本輪工作單位＝收成TW自己的背景job`20260906-083408-d6ab`**（`tw_deep_dive_quality_roe_stability_full_rerun`，300檔乾淨樣本完整重跑，`run_detached.py wait --max-min 4`確認`finished, exit=0`，總耗時約123分鐘）。**結果：`f_quality_roe_stability`（`TW_LEADS.md`#3）唯一disqualify理由（TRAIN/VAL絕對報酬正負號不一致）已解決**——300檔重跑後TRAIN ann_return由100檔樣本的-3.8%~-4.2%轉正為**+7.25%~+7.59%**，VAL維持正但量級從+13.2%~13.4%萎縮至**+0.98%~+1.25%**（約1/13），兩期同號，beta+0.223(TRAIN)/+0.027(VAL)，6/6組合仍全贏100次隨機控制組（percentile=100.0）。**判定由EXPERIMENTAL上修為PASS（1b深挖關卡）**，但誠實揭露VAL量級大幅萎縮（暗示100檔樣本原本的VAL強勢混有小樣本雜訊）、TRAIN/VAL beta差異、176/248因子值覆蓋率偏低（71%）三項尚待查證的保留，**未到「完整GATE_SEQUENCE可部署」程度，不觸發停下提案**。已寫入`TRIALS_LEDGER.md`#156、`TW_LEADS.md`#3更新。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫（複用已回補的300檔快取）。**下一輪TW軌接續**：(1)heavy-job-slot本輪已空出，可投遞新的重度工作（例如`f_quality_roe_stability`VAL期逐年分解，比照`US_LEADS.md`#151/#152方法論，或`CALIBRATION_PROBE.md`清單剩餘的`#91 revenue_trend_surprise_low_attention`複驗——**先grep `TRIALS_LEDGER.md`確認#91是否已被複驗過，本檔案round394已提醒但實際上round前期`TRIALS_LEDGER.md`#106已完成#91的300檔重跑，處理前務必先核實避免第三次重複**）；(2)或轉向`portfolio_multifactor_v2`是否納入`f_quality_roe_stability`當新成分因子候選的評估。完整見`TW_LOG.md`第396輪記錄、`TRIALS_LEDGER.md`#156。

---

**上一則保留（第394輪，供對照）**——接續`CALIBRATION_PROBE.md`「甲.3」複驗`#79 f_inst_streak_days`：300檔（248可用）TRAIN mean_ic=+0.0232/VAL mean_ic=-0.0150，train/val正負號仍相反，null percentile=86.1（未過90.0門檻）——判定維持FAIL。**過程中一次判斷失誤並已自行修正**：先誤重跑`#77`才發現round334已用同一套300檔重跑過且數字複現，已撤銷重複記列。已寫入`TRIALS_LEDGER.md`#153、`HYPOTHESIS_QUEUE.md`#13補充。完整見`TW_LOG.md`第394輪記錄。

---

**上一則保留（第392輪，供對照）**——代US軌收成背景job`20260906-060311-6a01`（低波動乾淨宇宙1b深挖）：TRAIN量級合理但VAL量級異常，判定EXPERIMENTAL非PASS（`TRIALS_LEDGER.md`#151）；投遞TW軌`tw_deep_dive_quality_roe_stability_full_rerun`（job_id`20260906-083408-d6ab`，`--timeout-min 150`），session內確認3分鐘仍`running`未崩潰。完整見`TW_LOG.md`第392輪記錄、`US_LEADS.md`#21、`TRIALS_LEDGER.md`#151。
