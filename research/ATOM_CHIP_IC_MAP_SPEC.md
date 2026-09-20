# ATOM_CHIP_IC_MAP_SPEC.md — 原子.六 籌碼depth-1素材IC地圖：事前登記規格

2026-09-20建立（研究帽）。對應`PENDING_QUEUE.md`「原子.六」（原子.五判FAIL後
的接續分支，`TRIALS_LEDGER.md`#316）。**本檔案是事前登記（pre-registration）：
在任何IC被算出來之前寫死搜尋空間、宇宙、判定規則。事後不得因為看到結果而改動
本檔案任何一格**——要改必須另開修訂段並標註「看過結果後修訂」，且該次結果
不得用作判定。

規格完全比照原子.二（`ATOM_IC_MAP.md`／`atom_ic_map.py`，日頻、
`factor_ic.build_snapshots`每horizon個交易日一個不重疊snapshot）與原子.五
（`ATOM_FIN_IC_MAP_SPEC.md`，分層宇宙＋覆蓋率規則），差異只在輸入是**籌碼日頻
資料**。

## 0. 硬性禁令（總司令原文，沿用）

1. 只出零件層級的IC分布，**禁止報告「最佳素材」／不得指名任何單一表達式
   為建議因子**。
2. 全數計入`selection_bias_ledger`的N（見第3節(C)）。
3. 必須做分年份與分牛熊段拆解，且牛熊段同號比例**必須與樸素機率基準並列**。
4. 本輪不組depth-2/3、不做任何策略判定、不碰holdout（全程確認
   `is_holdout_consumed()`＝False；所有資料只讀`VAL_END`＝2024-12-31以前）。
5. **放空腿硬規則（`CLAUDE.md`七之三⑩）**：本規格只算橫斷面Spearman IC，不
   組多空價差、不產生任何含放空腿的報酬數字。融券／借券賣出相關表達式的IC
   若日後被拿去組多空組合，一律標「資料缺陷，不得採信」（借券成本與可借量
   未接真實資料）；即使只做多頭排除（不放空）也要註明這點。

## 1. 資料源與歷史起點探測（第10關，2026-09-20實測，非推論）

| 原子來源 | 本機/取得方式 | 歷史起點（實測） | 覆蓋 | 備註 |
|---|---|---|---|---|
| 三大法人買賣超（T86） | `research/data/raw_twse_t86/`逐日全市場parquet（無需任何API） | **2012-05-02**（2010-01～2012-04的檔案存在但0列，為空殼；2011整年無檔） | 每日約746（2012）→1,008（2024）證券，含ETF/權證；只有**上市**，`TPEX3INSTI`快取只有2025-08起、落在VAL_END之後，**不得使用** | 欄位：foreign_net／trust_net／dealer_net／total_net（股）；自營商＝三大法人−外資−投信（既有規則） |
| 個股融資融券 | `research/data/raw/TaiwanStockMarginPurchaseShortSale__<id>__2010-01-01__2024-12-31.parquet`（FinMind快取，無需新API） | **2010-01-04**（2330實測每年239~251列） | 4位數代號411檔（與價格快取交集**392檔**）；另有ETF/空殼檔 | 欄位含MarginPurchaseTodayBalance／MarginPurchaseLimit／ShortSaleTodayBalance |
| 借券賣出餘額（SBL） | FinMind `TaiwanDailyShortSaleBalances`；**本機只有2330一檔**（本輪探測1次請求，已快取） | **2010-01-04**（2330，逐年中位數皆非零，2010~2024） | 尚未回補 | 欄位：SBLShortSalesCurrentDayBalance／SBLShortSalesShortSales。**這是「借券賣出餘額」（放空方），不是「借券餘額」（出借總量）** |
| 成交量／成交值 | `ATOM_LIBRARY.atom_v`／`atom_amt`（既有價量原子） | 2010起 | 同價格宇宙 | 用作正規化分母，不當獨立原子計數 |

**誠實揭露**：(1)交辦原文寫「借券餘額」，實際可得的是**借券賣出餘額**；出借總量
（借券餘額）另有TWSE端點，**本輪尚未做三來源查證**，故不宣稱「沒有」，只宣稱
「本規格未納入」，另立補件（見第9節）。(2)T86起點2012-05-02**晚於**價量地圖的
2010起點，涉及T86的表達式樣本少約2.3年，且**2011歐債危機窗完全沒有值**（第5節處理）。

## 2. 宇宙與已知偏誤

- **宇宙U**＝「個股融資融券快取的4位數代號」∩「`TaiwanStockPrice`快取」＝**392檔**
  （事前綁定；不再另抽300檔——快取是這批股票的融資融券唯一來源）。價格一律走
  `adjust.adjusted_price_series()`（含下市股）。
- 三大法人表達式：宇宙U中**有T86列的股票**（上市）；上櫃股該類表達式自然無值，
  被跳過，**不補、不用別的來源代替**。因此三大法人族只反映上市股，同一宇宙U內
  上市/上櫃組成隨表達式不同，**報告時逐族列出實際入樣檔數**。
- **存活者偏誤（偽影⑦）**：融資融券快取的411檔是早期研究陸續抓的，抽取機制
  未記錄（與300檔抽樣宇宙只重疊207檔），**方向未知**；價格側含下市股，但
  籌碼側是否含下市股**未驗證**（實作步驟第一件事：統計U中末筆日期<2024-06的
  檔數，寫進結果檔）。任何「看起來有訊號」的結果都須附此但書。
- T86／融資融券／借券賣出餘額**都是收盤後才公布**（約16:30～21:30），與收盤價
  成交不同時點（偽影⑨）。**PIT紀律（事前綁定，不可調）**：所有籌碼原子一律
  **lag 1個交易日**——snapshot日t的表達式值只用t−1日（含）以前的籌碼資料。
  這不是可掃描的參數，是時間因果的必要條件。

## 3. 事前登記的搜尋空間

窗口`n`只准`{1,5,20,60}`（`ATOM_LIBRARY.ALLOWED_WINDOWS`，n=1只用於有意義處）。
算子只用`ATOM_LIBRARY`既有`op_*`（`op_delay/op_ts_sum/op_ts_rank/op_decay_linear/
op_sign/op_ratio`），**不新增算子**。

### 籌碼原子（本家族，各自lag 1日）

| 代號 | 原子 | 來源 | 型態 |
|---|---|---|---|
| foreign | 外資買賣超 | T86 | 流量（股） |
| trust | 投信買賣超 | T86 | 流量 |
| dealer | 自營商買賣超（總−外−投） | T86 | 流量 |
| total | 三大法人合計 | T86 | 流量 |
| margin_bal | 融資餘額 | 融資融券快取 | 存量 |
| short_bal | 融券餘額 | 融資融券快取 | 存量 |
| margin_util | 融資使用率（今日餘額/融資限額） | 融資融券快取 | 比率（存量） |
| sbl_bal | 借券賣出餘額 | TaiwanDailyShortSaleBalances | 存量 |
| sbl_sales | 借券賣出（當日新增） | 同上 | 流量 |

（成交量`v`、成交值`amt`沿用價量庫，只當分母。）

### 表達式空間（depth-1，事前逐族列滿）

**流量族**（F∈{foreign,trust,dealer,total,sbl_sales}）：
- `nf_n`＝`op_ratio(ts_sum(F,n), ts_sum(v,n))`，n∈{1,5,20,60}（4個；除以成交量是
  為了去掉個股規模，原始股數橫斷面不可比，**故不做未正規化版**）
- `streak_n`＝`ts_sum(sign(F), n)`（買超天數−賣超天數），n∈{5,20,60}（3個；n=1
  退化為sign）
- `decay_n`＝`decay_linear(ratio(F, v), n)`，n∈{5,20,60}（3個）
→ 每個流量原子10個。

**存量族**（S∈{margin_bal, short_bal, sbl_bal}）：
- `growth_n`＝`op_ratio(S, delay(S,n)) − 1`，n∈{1,5,20,60}（4個）
- `rank_n`＝`ts_rank(S, n)`，n∈{5,20,60}（3個）
- `dov`＝`op_ratio(S, ts_mean(v,20))`（餘額相當於幾日成交量；1個。此處單位換算
  是全體共同常數，**橫斷面Spearman對正常數倍數不變**，故單位（張/股）不影響IC，
  實作仍須核對單位並記錄）
→ 每個存量原子8個。

**融資使用率**（margin_util，單一原子）：level（1）、`delta_n`＝`S−delay(S,n)`
n∈{5,20,60}（3）、`rank_n` n∈{5,20,60}（3）→ 7個。

**跨族比值**：
- `short_margin`＝`op_ratio(short_bal, margin_bal)`（券資比）：level（1）＋
  `delta_n` n∈{5,20,60}（3）→ 4個（Tier A）
- `sbl_short`＝`op_ratio(sbl_bal, short_bal)`（借券賣出佔融券比）：同構4個（Tier B）

明確排除：任何depth-2以上、`mul`類乘積、籌碼×價量混合（留給原子.三之後）、
未正規化的原始股數、窗口n=2,3,10,120等連續掃描。

### 分層與計數

| 層 | 內容 | 需要新API | 表達式數 | ×2 horizon(20/60日) |
|---|---|---|---|---|
| Tier A | 4個T86流量原子×10＝40；margin_bal、short_bal各8＝16；margin_util 7；券資比4 | 否（本機快取） | **67** | **134** |
| Tier B | sbl_sales 10；sbl_bal 8；sbl_short 4 | **是**（需回補`TaiwanDailyShortSaleBalances`） | **22** | **44** |
| **合計** | | | **89** | **178** |

**N＝178**（`selection_bias_ledger`以178個測試計入；Tier B若因未回補而未執行，
帳上仍**不得**用「沒跑」抵銷它——見第8節：未執行記「未檢驗」，N只在實際執行時
才計入，並在帳上註明分兩次登記）。同族高度共線者只算一個獨立發現（第6節）。

## 4. 執行方式（事前綁定，不得依結果調整）

- 樣本：宇宙U全部（≤392檔，量級與原子.五Tier B相近）。記憶體紀律照
  `INCIDENTS.md`事件001：逐檔算完只保留snapshot所需日期、掛「系統可用記憶體
  <3GB自動砍行程」安全閥（`mem_guard.install()`）、先15檔smoke→30檔記憶體驗證
  →全量；BLAS執行緒數依`MEM_BLAS_THREADS.md`提案**不改啟動器**，腳本內自行在
  import numpy前設`OPENBLAS_NUM_THREADS=4`即可（不動排程）。
- Snapshot：`factor_ic.build_snapshots(calendar, start, end, horizon)`，horizon∈
  {20,60}，不重疊；依`validation/holdout.py`切TRAIN（≤2020-12-31）與VAL
  （2021-01-01～2024-12-31）；**T86族起點2012-05-02**，融資融券族2010-01-04；
  各表達式的起點由其首個非NaN值自然決定，**不得為對齊而丟資料，也不得填補**。
  預估snapshot數：20日TRAIN約107／VAL約50；60日TRAIN約36／VAL約17。
- 每個snapshot橫斷面Spearman IC（原子.二同一套`corrwith`向量化做法），前瞻報酬
  自snapshot日收盤起算h個交易日（用`adj_close`）。
- 每個表達式輸出：`train_mean_ic`、`val_mean_ic`、`n_snap_train`、`n_snap_val`、
  `same_sign`；**`n_snap`<8者標「樣本不足」，不進任何同號比例分母**（沿用原子.五
  門檻）。
- **入樣規則**：每個snapshot橫斷面有效檔數<30者該snapshot跳過並計數（籌碼族
  上櫃缺席時尤其要看）。

## 5. 分年份與牛熊段拆解（事前綁定）

- 逐年平均IC與逐年同號率（該年snapshot IC符號）；**報告每年n**。
- 牛熊段：沿用`atom_ic_map.py::CRISIS_WINDOWS`同一份5個危機視窗。**T86族
  （起點2012-05-02）沒有2011歐債窗，K只有4**；融資融券／借券族K最多5。
  每個表達式的K＝「窗內至少有1個有值snapshot」的窗數；**不同K不得混進同一
  分母**。
- **樸素機率基準與結果並列（硬性）**：「K個窗全同號」的樸素基準＝2×0.5^K：
  **K=5→6.25%、K=4→12.5%**；60日horizon的窗內snapshot極少（2018Q4窗約1個），
  單窗符號就是單次拋硬幣，基準仍是0.5。K<3的表達式不做「全窗同號」判定，
  只報描述。
- 高階篩選（沿用原子.二／五四條件）：TRAIN/VAL同號＋危機窗全同號＋逐年同號率
  ≥0.7＋|VAL IC|>0.02；報告通過數／總數，並與「樸素機率下期望值」並列
  （期望值以各表達式實際K逐一算後加總，不用單一K）。

## 6. 獨立性與共線

- 同一原子的`nf`／`streak`／`decay`、外資與三大法人合計（total含foreign）、
  margin_bal的`growth`與margin_util的`delta`等高度相關者，依既有規則（|r|>0.7
  同族）只算一個獨立發現。執行後以snapshot層IC向量的相關矩陣分群，**報告
  「有效獨立表達式數」**，同號比例解讀以獨立數為準。
- **既有因子重疊聲明**：`f_margin_utilization`、`f_short_margin_ratio`、
  `institutional_*`系列閘門已在HYPOTHESIS_QUEUE測過；本地圖的margin_util／券資比
  表達式與之**同族**，帳上依`SELECTION_BIAS_LEDGER.md`第4節「跨軌重複因子」
  不重複算獨立發現。

## 7. 判定規則（事前綁定，本輪結果唯一解讀方式）

- **分支(a)進depth-2/3**：同時滿足
  1. 有效樣本（K≥4、n_snap達標）的「全窗同號」比例以單尾二項檢定對各表達式
     樸素基準（按K混合，不混K）p<0.01，且比例高於基準；
  2. 高階篩選通過數超過樸素期望值，且通過者分群後**≥2個獨立族**；
  3. 條件1、2在**Tier A**成立（不依賴尚未回補的SBL資料）；Tier B僅可作輔助。
  進depth-2/3須另行登記新條目，不在本輪。
- **分支(b)誠實判FAIL**：任一條不滿足→判FAIL，登記`TRIALS_LEDGER.md`（描述性
  地圖類，比照#285/#286/#316）與`STRATEGY_GRAVEYARD.md`，聲明「不泛化成
  籌碼資訊沒用」——只是depth-1、日頻、lag1、392檔IC地圖層級未見跨牛熊段
  穩定訊號；並如實寫明T86僅上市、無2011窗的限制。
- **Tier B未回補時**：Tier A獨立判定；Tier B記「**未檢驗**」，不記FAIL、不計
  入「籌碼原子已窮盡」。回補達U的60%（沿用原子.五覆蓋率門檻）才執行Tier B，
  另立試驗登記，不改動本檔案。
- **不設「勉強過」中間態**；任何結果都不得以「最佳素材」名義寫進`LEADS.md`。

## 8. 執行清單（給下一輪接續，這一輪只完成本檔案）

1. 寫`research/chip_atom_library.py`（載入T86全市場→逐檔lag1面板、融資融券快取、
   單位核對、下市檔數統計；**先斷言表達式清單＝本檔案第3節，89個**）。
2. 寫`research/chip_atom_ic_map.py`（仿`fin_atom_ic_map.py`：逐檔算完即壓縮、輸出
   result JSON＋逐snapshot IC快取）；15檔smoke→30檔記憶體→Tier A全量，
   `run_detached.py submit`。
3. 聚合（分年／牛熊／共線分群／樸素基準）→ 寫`CHIP_ATOM_IC_MAP.md`。
4. `trial_registry.register_trial()`登記（**先登記再宣稱判定**）、
   `python research/trial_registry.py --check`、重跑`selection_bias_ledger.py`。
5. 心跳寫`PROGRESS_HEARTBEAT.jsonl`；全程不碰holdout。

## 9. 相依補件（本規格衍生，已另立`PENDING_QUEUE.md`項目）

- `籌碼原子.補借券快取`：回補`TaiwanDailyShortSaleBalances`（U約391檔、每檔1次
  請求），批次≤200、遇402即停標BLOCKED，沿用`backfill_fin_atom_cache.py`樣式。
- `籌碼原子.出借總量查證`：對「借券餘額（出借總量）」做三來源查證（官方端點／
  API文件／社群或其他供應商），**不得只寫「查無」**。
