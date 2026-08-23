# FUT_LEADS.md — 期貨軌策略候選登記簿（挖礦馬拉松專用）

**期貨是全新的軌道，目前完全沒有地基。** 台指期歷史價量資料、連續合約建構（近月轉倉）都還沒寫。地基搭建進度見 `FUT_MARATHON_STATE.md`。

**規則跟 `LEADS.md` 相同**：判定只能是 `CHEAP_PASS`／`PASS`／`FAIL`／`EXPERIMENTAL`／`ABANDONED`；FAIL 也要記；深挖階段都要附「為什麼會有效」的經濟解釋。**期貨沒有基本面，所有策略都是技術面/籌碼面，不需要 `pit.py` 的財報 point-in-time 邏輯，但未平倉量/三大法人期貨部位這類籌碼資料的時間戳可信度要先驗證（假設每日公布即可信，但沒查證過就不能當定論）。**

| # | 日期 | 假說名稱 | 假說來源 | 型態 | 便宜關卡 | 深挖結果 | 判定 | 經濟解釋 | 備註 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-24 | `fut_trend_multi_tf`（10/20/60日動能多數決） | `MARATHON_PROTOCOL.md`第3節期貨候選清單 | 策略 | 配對式隨機排列控制組200次，percentile=82.5（門檻90.0） | 未進深挖 | **FAIL** | （便宜關卡未過，不需要經濟解釋） | 見`TRIALS_LEDGER.md`#18、`fut_cheap_gate.py`、`FUT_LOG.md`本輪。方向正確（真實策略贏隨機中位數）但強度不夠，依協定不調參數硬救 |
| 2 | 2026-08-24 | `fut_donchian_breakout_20`（20日Donchian channel突破） | `MARATHON_PROTOCOL.md`第3節期貨候選清單 | 策略 | 配對式隨機排列控制組200次，percentile=61.0（門檻90.0） | 未進深挖 | **FAIL** | （便宜關卡未過，不需要經濟解釋） | 見`TRIALS_LEDGER.md`#19，同批次同腳本。兩個最常見的入門技術訊號都沒過，暗示台指期日頻、無成本考量下的單一訊號動能/突破可能訊噪比不足，下一輪可以考慮波動regime過濾或均線系統，而非重測同類訊號 |
| 3 | 2026-08-24 | `fut_ma_crossover_20_60`（20/60日SMA均線交叉） | `MARATHON_PROTOCOL.md`第3節期貨候選清單（均線系統） | 策略 | 配對式隨機排列控制組200次，percentile=75.5（門檻90.0） | 未進深挖 | **FAIL** | （便宜關卡未過，不需要經濟解釋） | 見`TRIALS_LEDGER.md`#20、`fut_cheap_gate.py`本輪新增。方向正確（真實策略贏隨機中位數）但強度不夠，第三個技術訊號家族沒過 |
| 4 | 2026-08-24 | `fut_vol_regime_trend`（`fut_trend_multi_tf`加20日已實現波動度regime過濾，只在低波動regime進場） | `MARATHON_PROTOCOL.md`第3節期貨候選清單（波動regime過濾），對#1做的結構性變體 | 策略 | 配對式隨機排列控制組200次，percentile=82.5（門檻90.0） | 未進深挖 | **FAIL** | （便宜關卡未過，不需要經濟解釋） | 見`TRIALS_LEDGER.md`#21，同批次同腳本。percentile跟未過濾版本(#1的82.5)幾乎打平，波動regime過濾對這個訊號家族沒有帶來可辨識的改善，不再對`fut_trend_multi_tf`本身做進一步結構變體 |

---

## 目前狀態

**地基已完成（見`FUT_MARATHON_STATE.md`），已測4個策略假說，全部FAIL。**

已排除：`fut_trend_multi_tf`、`fut_donchian_breakout_20`、`fut_ma_crossover_20_60`、`fut_vol_regime_trend`（見上表#1–#4，不要重測相同設定或對`fut_trend_multi_tf`再做regime過濾類變體——已證實對這個訊號家族沒用）。

**下一輪建議**：三個主流技術訊號家族（動能多數決、通道突破、均線交叉）跟一個regime過濾變體都沒過，暗示單一訊號、日頻、無成本框架下訊噪比普遍不足。可以考慮換方向而非同家族繼續變體：(a) 日內均值回歸（跟趨勢類方向相反的假說家族，值得優先試）、(b) 期現價差（basis）、(c) 三大法人期貨部位或未平倉量變化（籌碼面，不是技術面，訊噪比可能不同）、(d) 星期效應/盤別效應（季節性，機制跟趨勢/突破完全不同）。見`MARATHON_PROTOCOL.md`第3節期貨候選清單。
