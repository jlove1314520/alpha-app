# FACTOR_POOL_INVENTORY.md — 因子池盤點（PENDING_QUEUE「零件.零」，2026-09-19）

**性質**：描述性盤點，不是統計判定，不寫 TRIALS_REGISTRY。**盤點方法＝靜態核對**：
`FACTORS.md`／`TRIALS_LEDGER.md`／`LEADS.md` 的判定 ×`factors.py` 註冊表與各 `factor_ic_*.py`
腳本存在性。**沒有執行期實際載入測試**（會打 FinMind 額度、且屬另一個工作單位），
所以下表「可載入」指「程式碼已註冊、有腳本」，不等於「今天跑得出數字」。

**先更正一個前提**：任務原文寫「core_tilt 的載入路徑」，但 `core_tilt_backtest.py`
**尚未存在**（重構.C4 BLOCKED）。現實中的載入路徑是 `factors.py`（`ALL_FACTOR_COLUMNS`
共 12 個）→ `score.py`／`composite_zscore_v1*.py`。`CORE_TILT_SPEC.md` 第 1 節指定的
成分是 `f_eps_growth`＋`f_eps_surprise`(合併)＋`f_revenue_surprise`＋`f_low_vol`。

## 分類結果

| 類別 | 因子 | 現況 |
|---|---|---|
| **A. 現行有效、程式已註冊（可載入）** | `f_eps_growth`、`f_eps_surprise`（同家族 r=+0.831，只算 1 個獨立發現＝`eps_family`）、`f_low_vol` | 2026-09-07 全體分母(N=223)降級後仍未被降級者。**獨立成分實為 2 個**（eps_family、low_vol） |
| **B. 被降級但仍被 spec 沿用（不一致，需總司令/下輪處理）** | `f_revenue_surprise` | `FACTORS.md` 2026-09-07 表：Bonferroni 全體分母下 99.0 < 99.9776 → **FAIL（校正後）**，明文「不得作為組合成分」；但 `CORE_TILT_SPEC.md` 第1節與 `score.py`（INDEPENDENT_RAW_COLS）仍用它。**未動任何一邊**，只標出矛盾 |
| **C. 待驗／候選（不是 PASS）** | `f_idio_vol`（#51 CHEAP_PASS，percentile 100，未見降級紀錄；與 `f_low_vol` 相關性檢查腳本 `check_idio_vol_low_vol_overlap.py` 存在，結果本輪**未讀**）、`f_value_pe`（CANDIDATE 待複驗）、`f_value_pb`／`f_quality_roe_stability`（CHEAP_PASS，2026-09-07 降級 FAIL） | 註冊於 `factors.py`（idio_vol 4 處引用、pe/pb/roe 各 9~12 處）。PIT 狀態：pb/pe 未驗證（`verify_pit_value_pb.py` 存在，結論本輪未讀） |
| **D. 已死（FAIL）** | `f_rev_accel`、`f_foreign_streak`、`f_inst_flow`、`f_rel_strength`、`f_ma_breakout`、`f_bab`（單測 91.0 過、累積校正未過）| 權重為 0，紀錄保留 |
| **E. 無法實作** | 分點集中度 | 付費牆（`TaiwanStockTradingDailyReport`），依 CLAUDE.md 取得方式鐵律標「待採購」 |
| **F. 有獨立腳本、判定未在本輪逐一核對** | `f_odd_lot_imbalance`、`f_52w_high`、`f_amihud_illiq`、`f_gross_profitability`、`f_asset_growth`、`f_accruals`、`f_residual_momentum`、`f_dividend_yield`、`f_short_*`、`f_margin_utilization` 等 | 多數有對應 portfolio 腳本或 graveyard 條目（例：`odd_lot_imbalance_portfolio_v1` 已 FAIL）。逐一判定核對是另一個工作單位，本輪不宣稱 |

美股因子（`f_us_*`）：`f_us_low_vol` #41 深挖 FAIL、`f_us_reversal_1m` FAIL、其餘 FAIL/未達門檻——
與台股 core_tilt 池無關，不計入。

## 回報數字（依任務要求格式）

- **可載入且現行有效：3 個訊號 → 2 個獨立成分**（eps_family、low_vol）。
- 若把 B（revenue_surprise）算進去＝3 個獨立成分，這正是 `零件.二 step 0` 已查到的
  「池僅 3 成分 < 下限 5」（MARATHON_LOG 2026-09-19T13:23）——本盤點與之吻合。
- 待驗候選（C）：4 個；已死（D）：6 個；無法實作（E）：1 個；未逐一核對（F）：約 10 個。
- **修復成本排序（低→高）**：①處理 B 的矛盾（純文書決策，成本≈0，但需總司令裁示用哪個口徑）
  →②讀 `check_idio_vol_low_vol_overlap.py` 結果，確認 idio_vol 是否為 low_vol 同家族
  （已有腳本，成本低）→③F 類逐一核對判定（純查帳，中）→④pb/pe/roe 需先驗 PIT 才可能復活
  （中高，且已被降級 FAIL，復活需新檢定）→⑤E 需採購預算（總司令核准）。

## 分支判定（依交辦原文）

「可修到≥6 個」**不成立**：即使樂觀地把 C 全數修復成有效（實際被降級者不可能不經新檢定復活），
以同家族只算 1 個計，獨立成分頂多約 5 個且多數尚未通過現行門檻。**依交辦分支：誠實回報
「因子庫不足以支撐組合搜尋」，正確動作是造新因子，而非搜舊組合。** 與零件.二/三已作廢的結論一致。

## [自行裁量]

1. 以靜態核對代替執行期載入測試（省 FinMind 額度與預算；執行期驗證可另立項）。
2. 第 B 類矛盾只標示、不擅自改 spec/score.py（涉及既有判定口徑，屬需總司令裁示範疇）。
