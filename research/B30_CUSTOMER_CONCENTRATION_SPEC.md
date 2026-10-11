# B30 客戶集中度／供應鏈——事前登記規格

- 登記日：2026-10-11（DevQueue cycle `20261011-163102`，常備.開發-因子類-B30，先.六十七 凍結.二解除後）
- 試驗名：`b30_us_customer_concentration_v1`（track=US）
- 依據：`BACKLOG.md` B30（2026-08-28 登錄）
- **本檔在執行 `research/b30_customer_concentration_gate.py`（任何報酬計算）之前 commit**；
  執行後不得改任何參數或規則，要改＝另開 v2、重新登記（N+1）。
- 回填抽取（`research/b30_sec_concentration_extract.py`）只讀申報裡的集中度數字，不碰價格；
  在本檔 commit 前看過的只有「維度命名長什麼樣」（為了把分類規則寫死），沒有看過任何報酬。

## 0. BACKLOG B30 原文兩點，各自的處理

1. **質性供應鏈關係**（`ic.tpex.org.tw` 產業價值鏈平台）：BACKLOG 原文就寫「併入既有 B19，
   不另開獨立管線」。B19 已上線（#432，`data/signal_ledger.json`）。本輪**不另做**，只補查證
   （第 1 節第 3 列）。平台只有當下快照、沒有歷史版本 → 依第 10 關只能前向觀察，與 B19 同性質。
2. **量化「前五大客戶占營收%」**：
   - **台股：仍無結構化免費來源**（第 1 節第 1、2 列）→ 維持「`customer_concentration`
     因子未實作」，不美化。
   - **美股：找到官方結構化來源**（第 1 節第 4 列）——SEC DERA「Financial Statement and Notes
     Data Sets」含 ASC 280「單一客戶占營收 ≥10%」的**帶維度** XBRL 數字，2009 年起逐季、
     PIT（每筆有申報日）。所以本試驗以**美股**為主市場；台股無法做跨市場複製（資料不存在），
     如實記錄。

## 1. 資料源查證（三來源以上，七之三「搜尋紀律」）

| # | 來源 | 2026-10-11 實測 | 結論 |
|---|---|---|---|
| 1 | 台股年報「主要進銷貨客戶名單」（`doc.twse.com.tw`）、MOPS 查詢頁 | robots `Disallow: /`（B20 規格第 2 節、`docs/DATA_SOURCE_MAP.md` 題材五.1） | 不可用（取得方式鐵律） |
| 2 | TWSE openapi `v1/swagger.json`（143 端點）全文搜「客戶／營業比重／主要」 | 命中 5 個皆非客戶揭露（ESG、損益表、券商人員數、獨董兼任）；B20 已查 TWSE＋TPEx 368 端點同樣沒有 | 不可用 |
| 3 | `ic.tpex.org.tw` 產業價值鏈平台 | 首頁 200；`/robots.txt` 302 轉回首頁 HTML（未宣告 robots）；內容為產業鏈位置（質性），無占比數字、無歷史版本 | 質性部分併入 B19（前向）；量化不可用 |
| 4 | SEC companyfacts API（NVDA） | 只有無維度事實；`ConcentrationRisk*` 0 筆 | 不可用（維度被剝掉） |
| 5 | SEC frames API `ConcentrationRiskPercentage1/pure/CY2023` | 200，但只有 45 家、無維度、多為基金 | 不可用 |
| 6 | **SEC DERA Notes Data Sets**（`sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets`，79 個 zip：2009q1～2025q3 季檔＋2025-10 起月檔） | 2026_09 月檔：`ConcentrationRiskPercentage1` 3,478 列／233 份申報，`dim.tsv` 帶 `ConcentrationRiskByBenchmark`／`ConcentrationRiskByType`／`MajorCustomers`；2011q2 起舊名 `ConcentrationRiskPercentage`（無 1） | **可用**（官方、免費、PIT） |

頻率：一個 zip 一個請求、間隔 ≥0.2 秒（官方 10 req/秒）；每檔約 0.5GB，抽取完即刪，只留小 CSV。

## 2. 訊號定義（固定規則，不是參數）

逐份 10-K（`form == "10-K"`，不含 10-K/A）計算 `s` ＝下列「公司層級單一客戶營收占比」事實的**最大值**：

1. `tag ∈ {ConcentrationRiskPercentage1, ConcentrationRiskPercentage}`；
2. 維度鍵 ⊆ {`ConcentrationRiskByBenchmark`, `ConcentrationRiskByType`, `MajorCustomers`}，
   且**必須有** `MajorCustomers` 與 `ConcentrationRiskByBenchmark`（帶部門、地區、區間、
   法人個體等其他維度者一律排除）；
3. `ConcentrationRiskByType` 不存在或 ＝ `CustomerConcentrationRisk`；
4. 基準以 `Sales` 或 `Revenue` 開頭（例：`SalesRevenueNet`、`SalesRevenueGoodsNet`、`Sales`、
   `RevenueFromContractWithCustomer…`），且不含 `Receivable`／`Purchase`／`Cost`；
   沒有基準維度的 `MajorCustomers` 列（可能是應收帳款）一律排除；
5. `MajorCustomers` 成員名若含 `Customers`（複數）／`Top`／`Next`／`Total`／`Aggregate`／
   `Combined`／`Other`（不分大小寫）→ 視為客戶群合計、排除；
6. `qtrs == 4` 且 `ddate == sub.period`（本會計年度全年數字）；`0 < value ≤ 1`。

沒有任何事實符合的 10-K 不進樣本（ASC 280 只要求揭露 ≥10% 的客戶，沒揭露≠集中度 0，
不能拿來當低分組）。

## 3. 假說與檢定（GATE_SEQUENCE 逐關，第一個 FAIL 即判定）

- **H1（方向事前寫死）**：Patatoukas (2012, *The Accounting Review*)——客戶集中度高的
  公司未來報酬較高。**高集中組**＝`s` ≥ 前一個日曆年全部樣本 `s` 的第 67 百分位
  （用前一年分布＝PIT，不用當年後來才申報的資料；第一個有樣本的年份只當暖身、不進檢定）。
- **進場**：申報日（`sub.filed`）之後第一個交易日收盤；持有 **H=60** 交易日；
  指標＝相對 SPY 超額報酬平均。同一檔前一事件持有窗內再出現的事件略過。
- **價格**：`research/data/dera_insider/prices/px_*.csv` 既有 yfinance 快取（零新增價格請求），
  CIK→代號用 `sec_edgar_client.get_cik_map()`；全部對得上的事件都用，不抽樣。
- **切分**：`validation.holdout` TRAIN ≤2020-12-31、VAL 2021～2024；不碰 holdout
  （`assert_no_holdout_leakage`）。
- **控制組（兩個變體，`evaluate_vs_control`，通過＝訊號 > 控制組最大值）**：
  ① 同年度隨機：每次從同一申報年的全部樣本（所有揭露者）抽與高集中組同年同數量的事件；
  ② 同年度＋同 SIC 兩碼隨機：同上，但限同 SIC 兩碼，該格不夠抽時退回同年度。各 200 次。
- **各關**：1 sanity（TRAIN、VAL 高集中組各 ≥100 筆、無 NaN）→ 2 隨機控制組（TRAIN）→
  3 參數高原（H ∈ {40, 50, 60, 75, 90} 都要 > 控制組 95 百分位）→ 4 成本 1×/2×/3×
  （`validation.us_costs.round_trip_cost_pct`，部位 1 萬美元）TRAIN、VAL 淨值都 >0 →
  5 leave-one-out（拿掉貢獻最大年份仍 >0 且 > 控制組 95 百分位）→ 6 逐年一致性（≥5/6 年為正）→
  7 樣本外 VAL 控制組。
- **全部通過才做**：天條一（換成組合層級 MDD）、前向 paper；部署前停下提案（部署決策）。
- **跨市場複製**：台股無量化來源（第 1 節）→ 記「無法執行（資料不存在）」，不是 PASS。

## 4. 自由參數（第 11 關）

| 參數 | 值 | 性質 |
|---|---|---|
| H 持有天數 | 60 交易日 | 自由參數①（第 3 關掃描） |
| 高集中切點 | 前一年第 67 百分位（三分位最高組） | 自由參數② |
| 訊號定義、進場時點、控制組抽法、去重 | 見上 | 固定規則 |

自由參數 2 個 ≤ 5，第 11 關通過。

## 5. 已知偏誤（照實揭露）

- **存活者偏誤未完全修正：已下市股 7.1%（775／10,863 檔）無價格來源。** 本試驗價格宇宙另偏向
  存活者（yfinance 現存代號＋DERA 內部人買入發行人快取）。
- 揭露者本身偏小型股，相對 SPY 的超額報酬會混入規模效果；控制組都從揭露者抽，可抵掉一部分，
  抵不掉的部分照實寫在結果裡。
- 帶維度標記的完整度隨年份提升（2009～2010 幾乎沒有，2012 起才多），早期樣本少。
