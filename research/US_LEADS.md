# US_LEADS.md — 美股軌因子/策略候選登記簿（挖礦馬拉松專用）

**美股是全新的軌道，目前完全沒有地基（宇宙建構、point-in-time 對齊、成本模型都還沒寫）。** 在地基搭好之前，這裡不會有任何因子/策略候選——先寫因子代碼再測是本末倒置。地基搭建進度見 `US_MARATHON_STATE.md`。

**規則跟 `FACTORS.md`/`LEADS.md` 相同**：判定只能是 `CHEAP_PASS`／`PASS`／`FAIL`／`EXPERIMENTAL`／`ABANDONED`；FAIL 也要記，寫清楚為什麼；深挖階段的 `PASS`/`EXPERIMENTAL` 都要附「為什麼會有效」的經濟解釋。**美股跟台股是不同市場，同一個因子在美股不一定用同樣的參數/門檻，不能直接照搬台股 `factor_ic.py` 的常數（例如樣本規模、橫截面窗口）沒有重新檢視就套用。**

| # | 日期 | 假說名稱 | 假說來源 | 型態 | 便宜關卡 | 深挖結果 | 判定 | 經濟解釋 | 備註 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-26 | `f_us_low_vol`（60日日報酬std取負號，跟TW版`f_low_vol`定義/窗口完全對齊） | 跟TW軌`f_low_vol`（已PASS，見`LEADS.md`#9）同家族，特意挑純價格、零PIT依賴的第一個因子 | 因子 | `us_factor_ic.py`，40檔隨機樣本（27檔可用），train IC+0.031/val IC+0.134，null percentile=100.0（門檻90.0） | `deep_dive_f_us_low_vol.py`（新寫，同27檔快取樣本+SPY當market benchmark，零新股票API呼叫，只加SPY一檔）：十分位多空（k=3/腳，20日換倉，樣本小已知限制）。TRAIN(2015-2020)×1x/2x/3x：ann_return −13.16%~−13.87%（**全負**），對配對式隨機控制組percentile僅41.0~48.0（**連中位數都沒贏過**），beta −0.149。VAL(2020-2024)×1x/2x/3x：ann_return +17.53%~+18.67%，percentile 91.0~97.0，但**beta −0.891**（遠非市場中性，接近反向於SPY的方向性押注）。TRAIN/VAL報酬正負號不一致（負→正） | **FAIL**（深挖未通過，#39的CHEAP_PASS判定降級為FAIL，不進入候選清單——見備註） | 未達判定門檻，依協定不強行套用經濟解釋敘事 | **TRAIN期沒有通過隨機控制組門檻本身已經是結案理由**（percentile 41-48遠低於其他已PASS/EXPERIMENTAL候選慣見的99~100），VAL期看似轉強的percentile跟beta驟降至−0.891同時出現，暗示VAL期表面的「超額報酬」主要來自方向性反向曝險（低波動股在2021-2024美股大盤大漲期間相對抗跌/跌深反彈的組合效應），不是穩定的橫斷面排序優勢——跟FUT軌`fut_basis_carry`（#35→#37）同款「便宜關卡通過、深挖樣本外/風險特性不成立」模式的第三個實例（第二個是TW`f_rel_strength_regime_switch`#40）。**成本模型簡化揭露**：`us_costs.py`需要`price`/`shares`才能算百分比成本，本次用$50/100股（$5,000/腳）代表性假設，非逐日實際股價，屬揭露的簡化，非隱藏假設。完整見`TRIALS_LEDGER.md`#41、`US_LOG.md`本輪記錄、`data/deep_dive_f_us_low_vol.csv`（gitignored） |

---

## 目前狀態

**（2026-08-26第82輪更新）地基已搭好（`us_universe.py`/`us_pit.py`/`validation/us_costs.py`/`us_factors.py`/`us_factor_ic.py`），上面表格已有第一筆候選（#1 `f_us_low_vol`，CHEAP_PASS待深挖）。以下段落是地基搭建期間的歷史記錄，保留供對照：** 已知的既有基礎（`DATA.md` 記錄過）：`USStockPrice` 免費且**已經是還原股價**（跟台股 `TaiwanStockPrice` 不對稱，美股這邊反而比較好處理），這是好消息，可以直接當價格資料源用，不需要像台股那樣自己組還原邏輯。2026-08-23 馬拉松第一輪已驗證 `USStockPrice` 歷史深度（AAPL/MSFT 回溯到 1990、逐日更新無漏交易日）跟 `USStockInfo` 涵蓋範圍（18396 檔 distinct stock_id，含 5470 檔 ETF），細節見 `DATA.md`「美股里程碑1」、`US_MARATHON_STATE.md`。

**下一輪工作單位建議**（`MARATHON_PROTOCOL.md` 第 5 節）：美股存活者偏差資料源（下市股名單）、美股 point-in-time 財報資料源（`CLAUDE.md` 提過 SEC EDGAR 是既有資料源之一，去看能不能借用同樣的資料源邏輯，**不能動 `alpha-data/fetch.py` 本身**，那是凍結區，只能參考公開的 SEC EDGAR API 文件重新寫）。

**2026-08-23 馬拉松第四輪更新**：存活者偏差調查有進展但是負面結果——台股 `universe.py` 的方法（價格列存在=地面真相）跟 `USStockInfo` 快照增減法，用 5 檔已知下市美股實測後**都證實不可靠**，細節見 `US_MARATHON_STATE.md`／`DATA.md`「美股存活者偏差調查」小節。下一步建議改用 SEC EDGAR 查證真實下市時間，而不是繼續猜。
