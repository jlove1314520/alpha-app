# `costs.limit_status()` 寫死 ±10%：2015-06-01 前用到它的地方清查（先.一三五-1au）

2026-10-29 DevQueue 空轉補件，零外部請求、只讀程式碼與試驗帳本；**不改核心檔、不重跑任何單發、不算報酬**。
用途：給互動視窗修 先.一三三-2c-限（`research/validation/costs.py` 屬十三節核心檔）時直接拿來當「受影響試驗清單」，不用重新調查。

## 問題一句話

`limit_status()` 用前收 ×1.10／×0.90 判一字鎖死；台股 2015-06-01 起才是 ±10%，之前上市上櫃都是 ±7%。
所以 2015-06 前的資料上，**實際漲停（+7%）一字鎖死的日子不會被判成鎖死**＝回測以為買得到／賣得掉（偏誤方向：成交過度樂觀）。

## 呼叫者逐支（2026-10-29 grep `limit_status`，research／scripts／.github）

| 呼叫者 | 資料期間 | 有沒有 2015-06 前 | 試驗 | 目前揭露狀態 |
|---|---|---|---|---|
| `research/backtest/engine.py` 第 234 行（`run_backtest()` 成交順延） | 看呼叫端 | **大範圍受影響**（見下方「engine 呼叫端」，1au-a） | 多支 | 無 |
| `research/stock_grid_oneshot.py` | 2007-07-02～2009-12-31 | **全期都是** | #468～#474 | 已揭露：`stock_grid_register_result.py` 第 42 行＋`stock_grid_limit7_diag.py` ±7% 診斷（23 筆賣、3 筆買落在一字鎖死日；先.一三三-2c 判偏誤方向不翻轉 FAIL） |
| `research/ml_pricevol_oneshot.py` | 2006-01-02～2012-12-31 | **全期都是** | #475 | 已揭露：程式說明第 9 點＋`ml_pricevol_register_result.py` 第 42 行；**沒有 ±7% 診斷數字** |
| `research/var1018_v5_january_reversal.py` | 主判定買進日＝2010～2023 年 12 月最後交易日；另報 2007～2009 | **部分**：主判定 14 個買進日有 5 個（2010-12～2014-12）在 2015-06 前；另報兩個 1 月全在 | #452（FAIL） | **沒有揭露**（程式只寫「漲跌停用 costs.limit_status 近似判定」） |
| `research/etf_rebalance_event_study.py` | 生效日 2022～2024 | 沒有 | #457／#458 | 不受影響 |
| `research/paper_forward_events.py`（模擬 P／Q／R 共用） | 前向 2027-01-04 起 | 沒有 | 前向模擬 | 不受 ±7% 影響；檔位取整近似另見 先.一三五-1ar／1ar-a |
| `research/paper_14_grid_range_tracker.py` | 前向 | 沒有 | 模擬 N | 已改官方檔位版，不再呼叫 |
| `scripts/compare_locked_up_approx_vs_official.py` | 近期 | 沒有 | — | 量測工具 |

## 偏誤方向（照實寫，未算數字）

- 買進腿：+7%～+10% 之間一字鎖死的日子被當成「買得到」→ 策略多拿到一些現實中買不到的強勢股。
- 賣出腿：−7%～−10% 一字鎖死被當成「賣得掉」→ 低估崩跌時的出場損失。
- 兩者都讓單發**看起來比實際好**；已判 FAIL 的（#452、#468）修正後只會更差，結論不翻轉。#475 的判定方向要看它的結果，本輪不讀結果、不推論。

## 下一步（寫進 PENDING_QUEUE）

1. 互動視窗修核心檔時（先.一三三-2c-限），照本表把 #452 補一句揭露（程式＋帳本備註），#475 視需要補 ±7% 診斷（比照 `stock_grid_limit7_diag.py`，只揭露不改判）。
2. ~~`engine.py` 呼叫端逐支清查~~ 2026-10-29 先.一三五-1au-a 已做，見下節。

## engine 呼叫端（先.一三五-1au-a，2026-10-29，只讀程式碼的日期常數，零外部請求）

46 支 .py 含 `run_backtest(`。逐支 grep 2015 年前的日期字面值，有 11 支；再看 import 關係：

- **`factor_ic.START_DATE = "2010-01-01"` 家族（影響最大）**：`portfolio_backtest.py`、`portfolio_backtest_v2.py`、`pead_portfolio_v1.py`、
  `dividend_yield_portfolio_v1.py`、`f52w_high_portfolio_v1.py`、`core_tilt_backtest.py` 都 `from factor_ic import START_DATE`，
  加權指數與樣本股從 2010-01-01 載入；train 段＝起點～2020-12-31（`validation/holdout.py` TRAIN_END），
  所以**約 2010-01～2015-05（約 5.4 年）的 train 段成交都用 ±10% 判鎖死**。val（2021～2024）不受影響。
- 其他起點 2010-01-01：`b25_random_control_regime.py`、`b25_regime_report.py`、`strategies/run_weinstein_pilot.py`、
  `run_weinstein_unbiased.py`、`run_weinstein_unbiased_v2.py`（pilot 註明 2010 是均線暖機，暖機段不交易的話影響較小，未逐行確認）。
- **全期在 2015-06 前**：`single_shot_2007_2014_test.py`（#396／#397）、`f52w_2007_extension.py`（轉向.一 2007～2014 單發）。
- 起點更早但只拿來載資料：`holdout_2025_dividend_account_test.py`（2000／2003 是名冊與 0050 價格起點，#399／#400）、
  `audit_universe_composition_val.py`（2000 名冊）、`backtest_engine_soundness_test.py`（2003 指數，#358 引擎自測）、
  `concentrated_backtest.py`（2011 下半年是危機區間標籤）——有沒有在 2015-06 前透過 engine 成交，本輪**未逐行確認**。
- **真錢策略 Bb-90（#418）不受影響**：`rerun_418_chain_unioncal.py`／`r1_0050_credit_gate.py`／`auto_rebalance_bb90.py`
  都沒有呼叫 `limit_status` 或 `run_backtest`（grep 0 筆）。

判讀：這些幾乎都是已 FAIL／已結案的試驗，偏誤方向（成交過度樂觀）不會讓 FAIL 翻成 PASS；
但 val 判定只看 2021～2024，**train 段的偏誤主要影響「train 上看起來有效才送 val」這一步的篩選**，不影響 val 結論本身。
本表只列清單，不重跑、不改判；修核心檔（先.一三三-2c-限）時預設行為不變（建議加 `trade_date` 參數、呼叫端自選），
既有試驗只補揭露。
