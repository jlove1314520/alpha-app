# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T05:03:32+08:00**（馬拉松第33輪期貨軌執行後，接手上一輪陳舊鎖檔並完成收尾）

**地基狀態：🟢 完整可用，可以開始測短中期回看窗口的因子/策略假說。** `continuous_contract.py`（連續合約建構）、轉倉時點規則（H1）、資料欄位品質（`settlement_price`/`open_interest`/`institutional_investors`）、累積漂移幅度全部已驗證。詳見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪（第33輪）完成：第一批策略假說已全部收尾，共測4個技術訊號家族，全部FAIL。** 上一輪（也是第33輪，但中途因鎖檔陳舊而被判定疑似失敗）已完成 `fut_cheap_gate.py` 撰寫與前2個假說測試但未收尾，本輪偵測到 `LOCK_STALE` 後接手，補完收尾（`FUT_MARATHON_STATE.md`/心跳/commit）並額外多測了2個假說（詳見 `FUT_LOG.md` 兩則本輪相關條目、`FUT_LEADS.md` #1–#4、`TRIALS_LEDGER.md` #18–#21）：

| 假說 | 訊號家族 | percentile（門檻90.0） | 判定 |
|---|---|---|---|
| `fut_trend_multi_tf` | 10/20/60日動能多數決 | 82.5 | FAIL |
| `fut_donchian_breakout_20` | 20日通道突破 | 61.0 | FAIL |
| `fut_ma_crossover_20_60` | 20/60日SMA均線交叉 | 75.5 | FAIL |
| `fut_vol_regime_trend` | 動能訊號+波動regime過濾（結構性變體） | 82.5（跟未過濾版打平） | FAIL |

**四個都沒過便宜關卡，依協定不調參數硬救，直接記錄。** 波動regime過濾對 `fut_trend_multi_tf` 沒有帶來可辨識的改善（percentile跟原版幾乎一樣），已排除對這個訊號家族再做進一步規則變體。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **優先**：四個純技術面趨勢/突破/均線類訊號都FAIL，**建議換方向而非同家族繼續變體**。候選（`MARATHON_PROTOCOL.md` 第3節）：(a) 日內均值回歸——跟趨勢方向相反的假說家族，訊噪比可能不同，值得優先試；(b) 期現價差（basis，近月期貨 vs 現貨指數，需要另外確認台股加權指數現貨資料源）；(c) 三大法人期貨部位或未平倉量變化——籌碼面，不是技術面，理論基礎不同；(d) 星期效應/盤別效應——季節性，機制完全不同。同樣一輪最多測2–3個假說，用便宜關卡先篩。
2. （較低優先，不擋路）用 FinMind 官方欄位文件或另外查證確認 `after_market`＝夜盤的推論是否正確（目前只是起始日期吻合的間接證據）。
3. （較低優先，不擋路）上上輪發現的開放問題：連續合約累積漂移的經濟成因未拆解（可能跟台股高股息殖利率、期現貼水有關）——可以另立為一個獨立假說排進候選清單，但不急。
4. （較低優先）若之後有策略需要用到夜盤資料，才需要把 `after_market` session 也納入連續合約建構——目前候選策略清單用日頻資料即可，不急。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪開始前跟結束前都確認 `is_holdout_consumed()` → `False`）。本輪全程只讀本機 parquet 快取，沒有任何網路請求。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `fut_cheap_gate.py` 了解目前已建立的便宜關卡測試框架（配對式隨機排列控制組，可以直接照樣加新的假說函式進去，不用重寫框架），再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約設計決策全貌（含漂移幅度量測結果，地基章節已標記完成）。**開始測新因子/策略時，先確認回看窗口長度合理（短中期已驗證安全；有需要可以直接呼叫 `fut_drift_probe.py` 的邏輯查特定窗口長度的漂移量級），並比照 `TW_MARATHON_STATE.md`／`US_MARATHON_STATE.md` 的先例，判定結果記進 `TRIALS_LEDGER.md`（累積總帳）跟 `FUT_LEADS.md`（本軌候選）。已測過FAIL的4個訊號（見上表）不要重測相同設定。**
