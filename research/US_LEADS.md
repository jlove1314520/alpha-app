# US_LEADS.md — 美股軌因子/策略候選登記簿（挖礦馬拉松專用）

**美股是全新的軌道，目前完全沒有地基（宇宙建構、point-in-time 對齊、成本模型都還沒寫）。** 在地基搭好之前，這裡不會有任何因子/策略候選——先寫因子代碼再測是本末倒置。地基搭建進度見 `US_MARATHON_STATE.md`。

**規則跟 `FACTORS.md`/`LEADS.md` 相同**：判定只能是 `CHEAP_PASS`／`PASS`／`FAIL`／`EXPERIMENTAL`／`ABANDONED`；FAIL 也要記，寫清楚為什麼；深挖階段的 `PASS`/`EXPERIMENTAL` 都要附「為什麼會有效」的經濟解釋。**美股跟台股是不同市場，同一個因子在美股不一定用同樣的參數/門檻，不能直接照搬台股 `factor_ic.py` 的常數（例如樣本規模、橫截面窗口）沒有重新檢視就套用。**

| # | 日期 | 假說名稱 | 假說來源 | 型態 | 便宜關卡 | 深挖結果 | 判定 | 經濟解釋 | 備註 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-26 | `f_us_low_vol`（60日日報酬std取負號，跟TW版`f_low_vol`定義/窗口完全對齊） | 跟TW軌`f_low_vol`（已PASS，見`LEADS.md`#9）同家族，特意挑純價格、零PIT依賴的第一個因子 | 因子 | `us_factor_ic.py`，40檔隨機樣本（27檔可用），train IC+0.031/val IC+0.134，null percentile=100.0（門檻90.0） | 尚未深挖 | **CHEAP_PASS**（US軌第一個通過便宜關卡的候選，排入待深挖清單） | 尚未寫（深挖階段才需要）——初步猜測跟TW版同源：低特異波動股可能反映投資人對彩票型高波動股的偏好（lottery preference / BAB文獻），但這是假設不是結論 | US軌FDR家族m=1，第一個試驗天生易過門檻，深挖時第一步務必做train/val切分（`FUT_MARATHON_STATE.md`記錄的`fut_basis_carry`教訓：便宜關卡CHEAP_PASS≠可信候選）。詳見`TRIALS_LEDGER.md`#39、`US_LOG.md`本輪記錄 |

---

## 目前狀態

**（2026-08-26第82輪更新）地基已搭好（`us_universe.py`/`us_pit.py`/`validation/us_costs.py`/`us_factors.py`/`us_factor_ic.py`），上面表格已有第一筆候選（#1 `f_us_low_vol`，CHEAP_PASS待深挖）。以下段落是地基搭建期間的歷史記錄，保留供對照：** 已知的既有基礎（`DATA.md` 記錄過）：`USStockPrice` 免費且**已經是還原股價**（跟台股 `TaiwanStockPrice` 不對稱，美股這邊反而比較好處理），這是好消息，可以直接當價格資料源用，不需要像台股那樣自己組還原邏輯。2026-08-23 馬拉松第一輪已驗證 `USStockPrice` 歷史深度（AAPL/MSFT 回溯到 1990、逐日更新無漏交易日）跟 `USStockInfo` 涵蓋範圍（18396 檔 distinct stock_id，含 5470 檔 ETF），細節見 `DATA.md`「美股里程碑1」、`US_MARATHON_STATE.md`。

**下一輪工作單位建議**（`MARATHON_PROTOCOL.md` 第 5 節）：美股存活者偏差資料源（下市股名單）、美股 point-in-time 財報資料源（`CLAUDE.md` 提過 SEC EDGAR 是既有資料源之一，去看能不能借用同樣的資料源邏輯，**不能動 `alpha-data/fetch.py` 本身**，那是凍結區，只能參考公開的 SEC EDGAR API 文件重新寫）。

**2026-08-23 馬拉松第四輪更新**：存活者偏差調查有進展但是負面結果——台股 `universe.py` 的方法（價格列存在=地面真相）跟 `USStockInfo` 快照增減法，用 5 檔已知下市美股實測後**都證實不可靠**，細節見 `US_MARATHON_STATE.md`／`DATA.md`「美股存活者偏差調查」小節。下一步建議改用 SEC EDGAR 查證真實下市時間，而不是繼續猜。
