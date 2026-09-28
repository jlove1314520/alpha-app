# 提案：`f_eps_surprise`／`f_revenue_surprise` 重驗未過後的降權或移除方案（2026-09-29，等 Cowork 核可，未執行）

依總司令 2026-09-29 裁示【驗.七】三.4：「若 (ii) 過不了門檻：不得自行改
score.py，改為提出降權或移除方案，等 Cowork 核可。」本文件只是提案，
**`research/score.py` 一個字元都沒改**。

## 1. 事實（`TRIALS_LEDGER.md` #401–#404，`research/FACTORS.md` 最上方）

| 因子 | 原登記 | (i) 舊還原公式＋新財報時點 | (ii) 新還原公式＋新財報時點 | 門檻 | 重驗判定 |
|---|---|---|---|---|---|
| `f_eps_surprise`（#7） | 100.0 | 61.2 | 61.2 | 98.33 | FAIL（#403） |
| `f_revenue_surprise`（#8） | 99.0 | 87.2 | 87.0 | 98.33 | FAIL（#404） |

(i)≈(ii)：還原公式修正不是原因，**財報時點（Q4 PIT）修正**是全部原因；
這與 2026-09-20 `FACTORS.md` 已記錄的重跑結論一致，本次是預先登記的正式
重驗再確認。

## 2. 現況：這兩個因子在 App 即時計分路徑上的位置

`research/score.py`：

- `eps_family` ＝ `f_eps_growth`、`f_eps_surprise` 兩者產業內 z-score 平均
  （`f_eps_growth` 同樣在 2026-09-20 失去 PASS，#287）。
- `revenue_surprise` ＝ `f_revenue_surprise` 產業內 z-score。
- `low_vol` ＝ `f_low_vol`（驗.六／驗.七重測百分位仍 100.0，唯一站得住的成分）。
- `composite` ＝ 三個成分**等權平均**；`MIN_COMPONENTS_FOR_RANKING = 2`
  （少於 2 個成分的股票不進榜）。

也就是說 **3 個成分裡 2 個（佔權重 2/3）建立在已未通過重驗的因子上**，
且 `scores.json`（App 價值成長榜）每日由此產生。

## 3. 三個方案（推薦 B）

### 方案 A：降權（保留成分，改權重）
把 `SCORE_COMPONENTS` 的等權改為顯性權重，例如
`{"low_vol": 1.0, "eps_family": 0.25, "revenue_surprise": 0.25}`。

- 優點：App 榜單不會突然大洗牌；保留未來若 PIT 修正後重新累積樣本再驗
  通過時的接回路徑。
- 缺點：**權重 0.25 沒有任何統計依據**，等於用一個「看起來比較保守」的
  數字掩蓋「這兩個成分現在沒有證據」的事實；違反 `CLAUDE.md` 七之三
  「未登記的候選判定一律無效」精神——降權本身就是一個新的、未驗證的
  參數選擇。**不推薦。**

### 方案 B（推薦）：移除，只留 `low_vol`，並同步調整可排名門檻與 App 揭露
1. `SCORE_COMPONENTS = ["low_vol"]`（`eps_family`／`revenue_surprise` 仍
   計算、仍輸出到 `scores.json` 的明細欄位供閱覽，但**不進 composite**）。
2. `MIN_COMPONENTS_FOR_RANKING` 由 2 改為 1——否則只剩一個成分時全部股票
   都不合格、榜單清空。**必須同時處理** `score.py` 註解裡記載的原始風險
   ：ETF／債券型 ETF 在 low-vol-only 下會被系統性高估——現在
   `universe.common_stock_only()` 已能排除 ETF／特別股／TDR／興櫃
   （宇.二＋查.三），把它接進 `export_scores_json()` 的資格池即可堵住
   這個舊風險（這一步是方案 B 的前置條件，不是選配）。
3. App 端 `scores.json` 的 `_meta` 與選股頁警語改為：「目前只用低波動
   一個成分計分；EPS／營收意外成分因 2026-09-20 財報時點修正後未通過
   重驗（#403/#404）已暫停計分，明細仍顯示。」
4. 冒煙測試（`node scripts/smoke_test.mjs`）第 39／41／46 項會直接驗到
   榜單是否清空、是否含下市股、產業覆蓋率——改完必須全過才算完成。

- 優點：榜單只依賴目前唯一有證據的成分；不引入新的無依據參數；揭露誠實。
- 缺點：榜單語意從「多因子」變成「低波動排行」，App 上的價值主張要
  同步改（UX.一 提案已在等審閱，可一併處理）。

### 方案 C：整榜暫停顯示，直到有 ≥2 個通過重驗的成分
`scores.json` 改輸出空榜＋說明。最誠實但對使用者最不友善；`f_low_vol`
本身證據充分，沒理由連它一起下架。**不推薦。**

## 4. 需要 Cowork／總司令決定的事（一句話）

**是否核准方案 B**（移除兩個未通過成分、只留 `low_vol`、可排名門檻改 1、
資格池接 `common_stock_only()`、App 揭露同步改）。核可後由互動視窗執行，
執行前先在 `PENDING_QUEUE.md` 登記原文。

## 5. 不在本提案範圍內、但相關的既有待辦

- `f_eps_growth`（#2／#287 FAIL）同樣在 `eps_family` 裡，方案 B 一併移出。
- `portfolio_multifactor_v2`／`core_tilt` 系列也依賴這三個因子（`FACTORS.md`
  2026-09-20 段落「下一步」），屬另案，本提案不處理。
