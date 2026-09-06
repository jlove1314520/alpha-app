# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-06T11:30+08:00（馬拉松第398輪）**——取鎖乾淨（非陳舊鎖檔）。三軌時間戳：FUT 02:30（round385，最舊，明確跳過信號維持有效）／TW 10:30（round396）／US 11:00（round397，最新）——依輪替選TW（較US舊）。`run_detached.py status`確認US軌`us_deep_dive_valuebm_clean_universe`（job`20260906-110113-735e`）本輪開工時仍`running`（約30~37分鐘/150分鐘timeout），heavy-job-slot持續佔用中，round396排定的「投遞新重度工作」選項本輪無法做。**本輪工作單位＝round396「下一步(1)」：`f_quality_roe_stability`VAL期逐年分解＋leave-one-year-out**（不需heavy-job-slot的輕量診斷，單次真實回測不含100次隨機控制組重跑，同`US_LEADS.md`#151/#152方法論）。新增`deep_dive_f_quality_roe_stability_val_year_breakdown.py`，事前綁定判準（任一leave-year-out變號或跌破全期30%＝CONFIRMED單一年份驅動）。**結果：VAL期四年報酬正負交替**（2021+15.88%/2022-8.21%/2023+16.15%/2024-11.34%），leave-2021-out(-1.97%)與leave-2023-out(-1.93%)**皆變號**，判定**CONFIRMED（單一年份驅動、非全期廣泛存在）**。**round396的PASS判定（`TRIALS_LEDGER.md`#156）因此降級回EXPERIMENTAL**——VAL期+0.98%~1.25%淨值本質是兩正兩負年份幾乎完全抵銷後的殘餘量，不是「訊號變弱但方向仍正確」，而是「year-to-year方向不穩定、剛好淨額為正」，統計上難與巧合區分。TRAIN期結果（#156，由負轉正+7.25%~7.59%）不受本輪影響。已寫入`TRIALS_LEDGER.md`#158（注意：#157已被同日另一輪`hypothesis_queue`軌用掉，本筆用#158不重複編號）、`TW_LEADS.md`#3更新（判定欄+備註+下一步清單同步修正）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增API呼叫（複用SAMPLE_SIZE已回補的300檔快取），與US背景job同時佔用CPU下執行約8分鐘（首次前景執行嘗試在4分20秒逾時仍卡在sample loading，判斷是CPU競爭導致載入變慢，放寬逾時到8分20秒後正常跑完，未寫出任何損毀或不完整的輸出檔）。**下一輪TW軌接續**：(1)TRAIN期beta+0.223比VAL期+0.027明顯偏離market-neutral的regime查證（尚未做）；(2)176/248（71%）因子值覆蓋率偏低原因查證（尚未做）；(3)`portfolio_multifactor_v2`成分因子候選一事本輪已建議擱置，不再列為近期優先方向；(4)若US軌`20260906-110113-735e`本輪或下輪已完成，heavy-job-slot空出後可考慮TW軌是否有其他候選需要完整重度深挖。完整見`TW_LOG.md`第398輪記錄、`TRIALS_LEDGER.md`#158、`TW_LEADS.md`#3。

---

**上一則保留（第396輪，供對照）**——收成TW自己的背景job`20260906-083408-d6ab`（`tw_deep_dive_quality_roe_stability_full_rerun`，300檔乾淨樣本完整重跑）：`f_quality_roe_stability`唯一disqualify理由（TRAIN/VAL絕對報酬正負號不一致）解決，TRAIN由負轉正+7.25%~7.59%，VAL維持正但量級萎縮至+0.98%~1.25%（約1/13），判定由EXPERIMENTAL上修為PASS（1b深挖關卡）。已寫入`TRIALS_LEDGER.md`#156、`TW_LEADS.md`#3。**（後續：round398已針對VAL量級萎縮做逐年分解，發現是單一年份驅動的巧合淨額，判定已降級回EXPERIMENTAL，見上方最新條目。）**完整見`TW_LOG.md`第396輪記錄。

---

**上一則保留（第394輪，供對照）**——接續`CALIBRATION_PROBE.md`「甲.3」複驗`#79 f_inst_streak_days`：300檔（248可用）TRAIN mean_ic=+0.0232/VAL mean_ic=-0.0150，train/val正負號仍相反，null percentile=86.1（未過90.0門檻）——判定維持FAIL。**過程中一次判斷失誤並已自行修正**：先誤重跑`#77`才發現round334已用同一套300檔重跑過且數字複現，已撤銷重複記列。已寫入`TRIALS_LEDGER.md`#153、`HYPOTHESIS_QUEUE.md`#13補充。完整見`TW_LOG.md`第394輪記錄。
