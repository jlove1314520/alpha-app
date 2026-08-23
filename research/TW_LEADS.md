# TW_LEADS.md — 台股軌因子/策略候選登記簿（挖礦馬拉松專用）

**這份檔案只記馬拉松（`MARATHON_PROTOCOL.md`）開始之後新測的候選。** 馬拉松開始前（2026-08-23 之前）已經測過的因子/策略，完整記錄在既有的 `FACTORS.md`（因子）跟 `LEADS.md`（策略）——**不要在這裡重複貼一次**，那兩份檔案繼續是台股因子/策略的權威歷史記錄，這份檔案只是接續它們的新章節。所有列都要先進 `TRIALS_LEDGER.md` 累積一筆才能出現在這裡（見 `MARATHON_PROTOCOL.md` 第 2 節）。

**規則跟 `FACTORS.md`/`LEADS.md` 相同**：判定只能是 `CHEAP_PASS`（過便宜關卡，待深挖）／`PASS`／`FAIL`／`EXPERIMENTAL`／`ABANDONED`；FAIL 也要記，寫清楚為什麼；深挖階段的 `PASS`/`EXPERIMENTAL` 都要附「為什麼會有效」的經濟解釋，沒有解釋要標註「純統計巧合風險，降級」。

| # | 日期 | 假說名稱 | 假說來源 | 型態 | 便宜關卡 | 深挖結果 | 判定 | 經濟解釋 | 備註 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-23 | `f_value_pb`（負PBR估值） | `MARATHON_PROTOCOL.md`第3節「價值」家族 | 因子 | 100名樣本，打散對照99.9百分位，過批次(n=3)與累積(n=15)校正門檻 | 未深挖 | **CHEAP_PASS**（待深挖） | 便宜的帳面價值可能反映市場對困境/低成長公司過度悲觀定價，日後基本面改善時修正（經典價值因子文獻） | PIT狀態未驗證，深挖前必須先查證FinMind PBR計算用的淨值更新時點（見`factors.py`揭露） |
| 2 | 2026-08-23 | `f_value_pe`（負PER估值） | `MARATHON_PROTOCOL.md`第3節「價值」家族 | 因子 | 100名樣本，打散對照96.7百分位，壓線過批次(n=3)門檻但**未過**累積(n=15)校正門檻99.3 | 未深挖 | CHEAP_PASS（批次）→累積校正後降級，暫不進深挖清單 | 同上（低本益比反映市場對盈餘品質/成長性的悲觀折價） | 需要更大樣本/更長歷史重測才能判斷是否為真訊號還是運氣；PIT狀態同樣未驗證 |
| 3 | 2026-08-23 | `f_quality_roe_stability`（ROE穩定度品質因子） | `MARATHON_PROTOCOL.md`第3節「品質」家族 | 因子 | 100名樣本，打散對照99.9百分位，過批次(n=3)與累積(n=15)校正門檻 | 未深挖 | **CHEAP_PASS**（待深挖） | ROE波動小的公司獲利品質較可信、較不易是會計操縱或景氣循環造成的一次性高峰，符合Novy-Marx品質因子文獻精神 | PIT機制與`f_eps_growth`同款（已驗證過的`quarterly_pit`），非未驗證狀態，深挖優先序可排在`f_value_pb`之前 |

---

## 目前狀態

**馬拉松第一輪（2026-08-23）已完成便宜關卡測試。** 產出：`f_quality_roe_stability`／`f_value_pb` 進入「已通過便宜關卡，待深挖」清單；`f_value_pe` 批次過但累積校正後降級，暫緩深挖。詳見 `TRIALS_LEDGER.md` #13–#15、`TW_LOG.md` 本輪記錄。

**下一輪建議**：
1. 深挖 `f_quality_roe_stability`（PIT已驗證，優先序最高）：樣本外/WFA、配對式隨機控制組、成本敏感度、beta對照、寫經濟解釋（草稿已在上表，深挖時要具體化）。
2. 深挖 `f_value_pb` 前，先解決 PIT 未驗證的缺口——用類似 `f_rev_accel`/`f_eps_growth` 當初的逐日核對方法，查 FinMind `TaiwanStockPER` 的 PBR 更新時點是否真的等到財報公告才變動。
3. 若還有時間額度，照 `MARATHON_PROTOCOL.md` 第 3 節繼續掃還沒碰過的因子家族：短期反轉、BAB/特異波動率、Amihud流動性、季節性、資產成長異常、Piotroski F-score、accruals盈餘品質。
