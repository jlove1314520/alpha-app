# TW_LOG.md — 台股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面），但只記馬拉松（`MARATHON_PROTOCOL.md`）跑起來之後、台股軌的每一輪動作。馬拉松之前的台股研究記錄在 `REPORT.md`（不重複搬過來）。

**規則：** 每個馬拉松輪次結束前，把這輪做了什麼（測了哪個假說、便宜/深挖關卡結果、卡在哪裡、下一步）append 一條到這裡，不管有沒有找到新東西——「這輪測了3個都FAIL」也是有效記錄，不能跳過不寫。

---

## 2026-08-23T02:00:00+08:00 — 台股軌馬拉松初始化

檔案建立，尚未有實際挖礦輪次執行。第一輪建議工作見 `TW_MARATHON_STATE.md`。

## 2026-08-23 — 馬拉松第一輪：重測 f_value_pb/f_value_pe/f_quality_roe_stability 便宜關卡

**做了什麼**：新寫 `factor_ic_value_quality.py`（沿用 `factor_ic.py` 的 100 名標準樣本、SAMPLE_SEED=20260822，跟已快取的 `data/raw/` parquet），對三個因子跑打散對照便宜關卡，`bonferroni_n=3`（這輪批次大小）。

**結果**：
- `f_value_pb`：val_mean_ic=+0.0592，打散對照 99.9 百分位，過批次門檻(96.7)也過累積校正門檻(n=15時99.3)。
- `f_value_pe`：val_mean_ic=+0.0501，打散對照 96.7 百分位，剛好壓線過批次門檻(96.7)，但**未過**累積校正門檻(99.3)——照 `MARATHON_PROTOCOL.md` 第2節規則老實記錄降級，不進深挖清單。
- `f_quality_roe_stability`：val_mean_ic=+0.0721，打散對照 99.9 百分位，兩種門檻都過。

三個都是 train/val 同號，樣本使用率 80/100（20 檔因缺歷史資料或抓取錯誤被跳過，屬正常篩選）。

**判定**：`f_value_pb`、`f_quality_roe_stability` → `CHEAP_PASS`（待深挖）；`f_value_pe` → 批次過但累積校正後降級，暫緩。已寫進 `TRIALS_LEDGER.md` #13–#15、`TW_LEADS.md`。

**注意事項**：`f_value_pb`/`f_value_pe` 的 PIT 狀態仍未驗證（`factors.py` 檔案開頭已揭露這個已知缺口），深挖 `f_value_pb` 前必須先補這個驗證步驟，不能假設便宜關卡過了就代表資料乾淨。`f_quality_roe_stability` 用的是已驗證過的 PIT 機制，無此疑慮。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

**下一步**：見 `TW_LEADS.md`「目前狀態」章節——優先深挖 `f_quality_roe_stability`，`f_value_pb` 深挖前先做 PIT 驗證。
