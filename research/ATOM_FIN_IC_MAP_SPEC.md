# ATOM_FIN_IC_MAP_SPEC.md — 原子.五 財報depth-1素材IC地圖：事前登記規格

2026-09-20建立（研究帽）。對應`PENDING_QUEUE.md`「原子.五」。**本檔案是
事前登記（pre-registration）：在任何IC被算出來之前寫死搜尋空間、宇宙、
判定規則。事後不得因為看到結果而改動本檔案任何一格**——要改必須另開修訂段
並標註「看過結果後修訂」，且該次結果不得用作判定。

規格完全比照原子.二（`ATOM_IC_MAP.md`／`atom_ic_map.py`），差異只在
輸入是**季頻財報**（`FIN_ATOM_LIBRARY.py`）而非日頻價量。

## 0. 硬性禁令（總司令原文，沿用）

1. 只出零件層級的IC分布，**禁止報告「最佳素材」／不得指名任何單一表達式
   為建議因子**。
2. 全數計入`selection_bias_ledger`的N（見第5節）。
3. 必須做分年份與分牛熊段拆解，且牛熊段同號比例**必須與樸素機率基準並列**
   （原子.二即由此抓到「5.03% < 6.25%」，`TRIALS_LEDGER.md`#286）。
4. 本輪不組depth-2/3、不做任何策略判定、不碰holdout（全程確認
   `is_holdout_consumed()`＝False；資料一律走`FIN_ATOM_LIBRARY.load_quarter_frame`
   → `finmind_client.load_dev`，擷取層即截在VAL_END）。

## 1. 宇宙（覆蓋率前置問題的處置，`[自行裁量]`）

`FIN_ATOM_COVERAGE.md`顯示資產負債表／現金流原子全體覆蓋僅20~31%（本機缺檔）。
本機快取實數（2026-09-20，非空parquet）：損益表1861檔、資產負債表687檔、
現金流量表407檔，**三表齊全＝407檔**。選擇不補抓（補抓受FinMind額度約束，
屬另案`財報原子.補快取`，且花額度），改用**兩層宇宙**：

| 層 | 宇宙 | 可用原子 | 目的 |
|---|---|---|---|
| Tier A | 損益表有快取者（實際建表成功約1851檔） | revenue／eps／gross_profit／op_income／net_income／shares（6個，覆蓋率皆≥60%） | 大宇宙、存活者偏誤較輕 |
| Tier B | **三表齊全的407檔** | 全11個原子；**只測涉及total_assets/equity/inventory/receivable/ocf其中至少一個的表達式** | 補資產負債／現金流原子，不與Tier A重複計數 |

**Tier B的已知偏誤方向（必須隨結果一併揭露）**：三表齊全者是「本機有快取」
的子集，而下市代理（末季<2024）的資產負債表覆蓋率僅13~16%（對照存續14%起、
損益表97%），代表Tier B**系統性少了下市公司**＝存活者偏誤更重，方向是
**高估品質/成長類素材的IC**（活下來的公司財報較好）。因此Tier B任何
「看起來有訊號」的結果一律降一級解讀，不得單獨當作進depth-2/3的依據，
必須Tier A有對應的獨立證據（涉及的損益表原子部分）才算數。

金融業（產業名含「金融」）：`gross_profit`／`op_income`／`inventory`／`receivable`
本質NaN，樣本內僅4檔，不特別處理，NaN自然被跳過。

## 2. 樣本時間起點

- 含`net_income`或`shares`的表達式：樣本起點須≥2013Q1（定義造成，見
  `FIN_ATOM_COVERAGE.md`第5節第2點），不做舊GAAP拼接。
- 其餘表達式：沿用`load_quarter_frame`的2010-01-01起點；實際可用起點由
  各表達式首個非NaN值自然決定，**不得為了對齊而丟棄較早期資料，也不得
  為了湊樣本而填補**。
- 一律以`pit_date`（法定申報期限，Q4＝次年3/31）決定「該日可得」，
  不得用期別日；`pit_source`恆為`assumed_statutory`，前視限制照
  `FIN_ATOM_LIBRARY.py`檔頭聲明（重編只存最新版、舊制期限為保守估計）。

## 3. 事前登記的搜尋空間

窗口`n`只准`{1,4,8}`（庫內強制）。算子只用`FIN_OPERATORS`既有七個，不新增。

### (A) 單一原子 × 算子（一元）

| 原子群 | 原子 | 算子 | 每原子數 | 小計 |
|---|---|---|---|---|
| 流量（不含shares） | revenue、eps、gross_profit、op_income、net_income、ocf | `yoy`、`qoq`、`ttm`、`slope(4)`、`slope(8)`、`delta_yoy`、`surprise(naive)`、`surprise(drift)` | 8 | 48 |
| shares | shares | `yoy`、`qoq`、`slope(4)`、`slope(8)`、`delta_yoy`（不做`ttm`與`surprise`：股數加總／意外無經濟意義） | 5 | 5 |
| 時點（存量） | total_assets、equity、inventory、receivable | `yoy`、`qoq`、`slope(4)`、`slope(8)`、`delta_yoy`（`ttm`庫內即拒；`surprise`對存量無定義故不做） | 5 | 20 |
| **(A)合計** | | | | **73** |

其中Tier A（不涉及受限原子）＝revenue/eps/gross_profit/op_income/net_income的
5×8＝40＋shares 5＝**45**；Tier B（涉及ocf或四個存量原子）＝ocf 8＋存量20＝**28**。

### (B) 兩原子單季比值 `ratio(x, y)`

- 參與原子：**revenue、gross_profit、op_income、net_income、ocf、total_assets、
  equity、inventory、receivable**（9個）；**排除eps與shares**（每股值與總額
  單位不相容，硬比無經濟意義）。
- 一律用**單季值**（流量科目當季值、存量科目當季末時點值），不套ttm（`[自行裁量]`：
  避免把搜尋空間再乘上一倍，且ttm×時點的混用口徑另需經濟理由）。
- **有序配對全列**（x/y與y/x視為兩個不同表達式；分母≤0→NaN由庫內處理）：
  9×8＝**72**；其中僅涉及{revenue, gross_profit, op_income, net_income}的
  4×3＝**12**屬Tier A，其餘**60**屬Tier B。

明確排除：`mul`類乘積、depth-2以上任何組合、任何跨價量原子的混合表達式
（財報×價量留給原子.三之後）、ratio的ttm版本。

### (C) 合計

| 層 | 表達式數 | ×2 horizon(20/60日) | 測試數 |
|---|---|---|---|
| Tier A | 45＋12＝57 | | 114 |
| Tier B | 28＋60＝88 | | 176 |
| **合計** | **145** | | **290** |

**N＝290**（`selection_bias_ledger`帳上以290個測試計入；同族高度共線者只算
一個獨立發現，見第6節）。

## 4. 執行方式（事前綁定，不得依結果調整）

- 樣本：Tier A取`sample_universe_ids`同一套抽樣邏輯的上限300檔（記憶體紀律，
  見`INCIDENTS.md`事件001：不得常駐全歷史，只保留snapshot所需日期）；
  Tier B取407檔全部（量級與300相近，仍須逐檔算完即壓縮）。
  執行前先用10~30檔小樣本驗證邏輯與記憶體，再跑全量，並掛「系統可用記憶體
  <3GB就自動砍行程」安全閥（沿用原子.二做法）。
- **Snapshot日期（財報特有，事前綁定）**：財報一年只更新4次，若沿用原子.二的
  密集snapshot，同一份財報會在數十個snapshot重複貢獻→IC高度自相關、
  有效樣本數被灌水。因此**每個公布週期只取一個snapshot**：各法定期限
  （5/15、8/14、11/14、次年3/31）之後的**第一個交易日**，共約4個/年。
  期間為各表達式首個可算日起至VAL_END（依`validation/holdout.py`切分TRAIN/VAL）。
  代價：有效樣本數小（約12年×4＝~48個，TRAIN約24個），**這是財報頻率的
  結構性上限，不是設計缺陷，結果解讀須據此放寬信賴區間**。
- 每個snapshot：橫斷面Spearman IC（原子.二同一套`corrwith`向量化做法），
  前瞻報酬20日／60日（自snapshot日起算的交易日）。
- 每個表達式輸出：`train_mean_ic`、`val_mean_ic`、`n_snap_train`、`n_snap_val`、
  `same_sign`（TRAIN/VAL平均IC同號）。**`n_snap`低於8者標「樣本不足」，
  不進任何同號比例的分母**（`[自行裁量]`：8＝2年×4次，過低者同號純屬運氣）。

## 5. 分年份與牛熊段拆解（事前綁定）

- 逐年平均IC與同號率＝該年內snapshot的IC符號；**每年僅有約4個snapshot，
  同號率解析度粗（0/0.25/0.5/0.75/1），報告時須註明每年n**。
- 牛熊段：沿用`atom_ic_map.py::CRISIS_WINDOWS`同一份5個危機視窗（2011歐債／
  2015中國股災／2018Q4貿易戰／2020Q1新冠／2022全年），其餘為「常態/牛市」。
  **snapshot落點（依上述日期預估）**：2011窗2個（8/15、11/14後）、2015窗1個
  （8/14後）、2018Q4窗1個（11/14後）、2020Q1窗約1個（3/31後首個交易日落在
  4/1，在窗內）、2022窗4個。**每窗僅1~4個snapshot，窗內符號＝該窗snapshot
  IC平均的正負**；此解析度遠粗於原子.二，須在結果旁明寫。
- **樸素機率基準與結果並列（硬性）**：「5個危機窗全部同號」的樸素基準
  ＝2×0.5⁵＝**6.25%**（與原子.二同一把尺）；另須並列「以本輪實際各窗
  snapshot數重算的基準」——單窗只有1個snapshot時該窗符號為單次拋硬幣，
  基準仍是0.5，但若有窗因資料缺（表達式起點晚於窗）而無值，該表達式
  改比對「有值窗數K」的2×0.5^K並標K，**不得把不同K混進同一個分母**。
- 高階篩選（沿用原子.二四條件）：TRAIN/VAL同號＋危機窗同號＋逐年同號率≥0.7＋
  |VAL IC|>0.02，報告通過數/總數，並與「樸素機率下期望值」並列。

## 6. 獨立性與共線

- 同一原子的`yoy`／`slope`／`delta_yoy`、`eps`與`net_income`、`gross_profit`與
  `op_income`等高度相關者依既有規則（|r|>0.7視為同族）只算一個獨立發現。
  執行後以snapshot層IC向量的相關係數矩陣分群，**報告「有效獨立表達式數」**，
  同號比例的解讀以獨立數為準，不以290個名目數為準。
- 表達式（`ratio`）本身若在Tier B與Tier A的損益表部分重疊，不重複計數
  （已由第3節分層確保無重疊）。

## 7. 判定規則（事前綁定，這是本輪結果唯一的解讀方式）

- **分支(a)進depth-2/3（進原子.三之後）**：同時滿足
  1. 有效樣本（K=5、n_snap達標）的「五窗全同號」比例，以單尾二項檢定對6.25%
     基準，p<0.01，**且**比例高於基準（不是低於）；
  2. 高階篩選通過數超過樸素期望值，且通過者分群後**≥2個獨立族**（不是單一
     族共線出來的）；
  3. 條件1、2在Tier A（大宇宙）成立；Tier B僅可作輔助，不可單獨進depth-2/3
     （存活者偏誤方向已於第1節揭露）。
- **分支(b)誠實判FAIL**：任一條不滿足→判FAIL，記`TRIALS_LEDGER.md`（描述性
  地圖類，登記方式比照#285/#286）與`STRATEGY_GRAVEYARD.md`，聲明「不泛化成
  財報資訊沒用」——只是depth-1單一時間序列/單季比值、季頻~48snapshot、
  IC地圖層級的檢驗未見跨牛熊段穩定訊號。然後接原子.六（籌碼原子家族）。
- **不設「勉強過」中間態**；任何結果都不得以「最佳素材」名義寫進`LEADS.md`。

## 8. 執行清單（給下一輪接續，這一輪只完成本檔案）

1. 寫`research/fin_atom_ic_map.py`（讀`FIN_ATOM_LIBRARY`、逐檔算完即壓縮、
   輸出`fin_atom_ic_map_result.json`與逐snapshot IC快取parquet）。
2. 15檔smoke → 30檔記憶體驗證 → Tier A全量 → Tier B全量。
3. 分年/牛熊段聚合＋共線分群＋樸素基準並列 → 寫`FIN_ATOM_IC_MAP.md`。
4. 透過`trial_registry.register_trial()`登記（290個測試、描述性地圖類），
   跑`python research/trial_registry.py --check`，重跑
   `selection_bias_ledger.py`。
5. 心跳寫`PROGRESS_HEARTBEAT.jsonl`；任何一步都不得碰holdout。
