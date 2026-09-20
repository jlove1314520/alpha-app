# ATOM_FIN_CHANNEL_B_SPEC.md — 原子.五B 財報通道B（結構型算子）重掃：事前登記規格

2026-09-20建立（研究帽，馬拉松第584輪）。對應`PENDING_QUEUE.md`「原子.五B」與
`ATOM_LIBRARY.md`「深度組合的閘門規則：通道A／通道B」。**本檔案是事前登記：
在任何IC被算出來之前寫死搜尋空間、宇宙、判定規則。事後不得改動任何一格**；
要改必須另開「看過結果後修訂」段，且該次結果不得用作判定。

執行機制完全沿用`ATOM_FIN_IC_MAP_SPEC.md`（原子.五）的第1（宇宙兩層）、第2（時間起點）、
第4（每個公布週期一個snapshot、橫斷面Spearman IC、20/60日、n_snap<8標樣本不足、
記憶體紀律）、第5（分年份／五個危機窗、6.25%樸素基準並列、K窗規則）、第6（共線分群）、
第7（判定規則）節，**這裡只登記「不同的地方」＝搜尋空間**。

## 0. 硬性禁令（沿用，總司令原文）

1. 只出零件層級IC分布，**不報告「最佳素材」、不指名任何單一表達式為建議因子**。
2. 搜尋空間全數計入`selection_bias_ledger`的N。
3. 牛熊段同號比例必須與樸素機率基準（5窗全同號＝6.25%）並列。
4. 不做策略判定、不碰holdout（`is_holdout_consumed()`須為False；資料一律走
   `load_dev`，擷取層截在VAL_END）。

## 1. 一個必須誠實揭露的事實（事前寫下，非看結果後）

佇列條目寫「原子.五FAIL只證明水準與成長無效」。**實際核對`fin_atom_ic_map.py`的
`build_registry()`**：原子.五的depth-1空間其實已含`surprise(naive)`、
`surprise(drift)`（套在6個流量原子的**水準**上）、`delta_yoy`（＝`accel`，套在原子上）、
與單季`ratio(x,y)`（＝depth-1的`spread`比值形式）。所以通道B相對原子.五的**新增量**
不是「第一次測意外」，而是：**把四類結構型算子套在「已衍生的序列」上（depth-2/3）**——
比率序列的意外／加速度／自身歷史z分數、成長率序列的意外／自身歷史z分數、
成長率之間的差（跨科目成長差）。下面第2節的表達式與原子.五的145個**零重疊**。
（f_eps_surprise式的「EPS水準意外」原子.五已測過；這裡測的是「利潤率意外」
「成長率意外」這類更深一層。）

## 2. 事前登記的搜尋空間（結構型算子清單事前鎖定，不得擴充）

窗口只准`{1,4,8}`；`zscore_ts`窗口**綁定為8季**（含當季，8個曆法連續季須齊全且非NaN，
std==0→NaN；與庫內`surprise`的ts_std窗同一個8，不掃4）。`surprise`的預期模型
**事前綁定為兩個零參數版本**：`naive`（去年同季）、`drift`（庫內`expected_seasonal_drift`），
不得因結果增刪。`accel(x)＝delta_yoy(x)`（庫內既有）。自由參數個數：**0**
（第11關參數上限閘門：≤5，遠低於，不需逐一辯護）。

**衍生序列**（經濟意義事前指定，共兩組）：

- **R組：11個經濟意義明確的比率（單季值，`fin_ratio`，分母≤0→NaN）**
  毛利率＝gross_profit/revenue；營業利益率＝op_income/revenue；淨利率＝net_income/revenue；
  ROA＝net_income/total_assets；ROE＝net_income/equity；資產週轉＝revenue/total_assets；
  存貨營收比＝inventory/revenue；應收營收比＝receivable/revenue；
  盈餘品質＝ocf/net_income；營業現金流營收比＝ocf/revenue；權益比＝equity/total_assets。
  （Tier A：前3個，只需損益表；其餘8個屬Tier B。）
- **G組：11個原子的年增率序列`yoy(x)`**（x∈revenue, eps, gross_profit, op_income,
  net_income, ocf, shares, total_assets, equity, inventory, receivable；基期≤0→NaN由庫內處理）。
  （Tier A：revenue/eps/gross_profit/op_income/net_income/shares共6個；其餘5個Tier B。）

**表達式**：

| 群 | 定義 | 個數 | Tier A | Tier B |
|---|---|---|---|---|
| B1 R組×`surprise(naive)` | surprise(R, naive) | 11 | 3 | 8 |
| B2 R組×`surprise(drift)` | surprise(R, drift) | 11 | 3 | 8 |
| B3 R組×`zscore_ts(8)` | z(R,8) | 11 | 3 | 8 |
| B4 R組×`accel` | delta_yoy(R) | 11 | 3 | 8 |
| B5 G組×`surprise(naive)` | surprise(yoy(x), naive) | 11 | 6 | 5 |
| B6 G組×`surprise(drift)` | surprise(yoy(x), drift) | 11 | 6 | 5 |
| B7 G組×`zscore_ts(8)` | z(yoy(x),8) | 11 | 6 | 5 |
| B8 `spread`（成長差） | yoy(x)−yoy(y)，**無序配對**（x−y與y−x只差正負號，IC必為鏡像，不重複計數） | 55 | 15 | 40 |
| **合計** | | **132** | **45** | **87** |

×2 horizon(20/60日)＝**264個測試**（Tier A 90、Tier B 174）。**N＝264**，
與原子.五的290互不重疊、累加計入。Tier B的存活者偏誤警語與原子.五第1節相同
（三表齊全者缺下市公司，高估品質類IC；Tier B只作輔助、不可單獨進深挖）。

**明確排除**：任何未列在上表的算子×序列組合、depth-4以上、`zscore_ts`其他窗口、
價量混合、`spread`的水準差（`x−y`未成長率化，單位不相容）、對Tier B事後增加`ratio`。

## 3. 成本前置關卡（協定1a-0）的處置

本輪是**描述性IC地圖**，不是有換手頻率的可交易機制，1a-0成本前置關卡不適用
（沒有「保守毛alpha估計」可比）；**若任何族在第4節判定下存活進入深挖，深挖SPEC
必須先做1a-0**（財報事件驅動，預期換手約每年4次、持有期量級t60，查
`breakeven_alpha_table.json` geometric版門檻）。這裡先記下，避免深挖時漏掉。

## 4. 判定規則（事前綁定；與`ATOM_FIN_IC_MAP_SPEC.md`第7節同款，總司令裁示指定）

- **分支(a)進深挖（比照原子.三六道控制，第六條「經濟機制寫不出來就砍」尤其嚴格）**：
  同時滿足①Tier A、K=5、**族層級**「五窗全同號」比例對6.25%基準單尾二項p<0.01
  （Bonferroni×2＝兩個horizon）**且**比例高於基準；②高階篩選（TRAIN/VAL同號＋
  危機窗同號＋逐年同號率≥0.7＋|VAL IC|>0.02）通過者超過樸素期望值，且分群後
  **≥2個獨立族**；③Tier B僅輔助。
- **分支(b)誠實判FAIL**：任一條不滿足→FAIL，登記`TRIALS_LEDGER.md`（描述性地圖類）
  與`STRATEGY_GRAVEYARD.md`。此時結論範圍可外推為
  **「財報depth-2/3以內、這11個原子＋這套結構型算子皆無效」**（佇列裁示原文）；
  但仍**不得**外推成「財報資訊沒用」——未測價量×財報混合、未測其他預期模型、
  未含分析師預期、資料為季頻約48個snapshot的低解析度。接原子.六（已在跑）。
- **不設「勉強過」中間態。** 60日族層級p落在0.01附近時，沿用原子.五報告的
  「共同因子警語」（危機窗共享同一段行情，樸素基準低估同號機率）並列，
  但判定仍以事前p<0.01為準，不因警語放寬或收緊。

## 5. 執行清單

1. `research/fin_atom_ic_map_b.py`：薄包裝，重用`fin_atom_ic_map.py`的宇宙／snapshot／IC
   機制，只替換`REGISTRY`（斷言＝本檔132／45／87），輸出加`_chB`後綴，不覆蓋原子.五檔案。
2. 15檔smoke → Tier A全量 → Tier B全量（`run_detached.py`投遞，掛`mem_guard`）。
3. 聚合／族層級檢定（重用原子.五聚合腳本邏輯，讀`_chB`檔）→ 寫`FIN_ATOM_CHANNEL_B.md`。
4. `register_trial()`登記264個測試（描述性地圖類）→ `trial_registry.py --check`
   → 重跑`selection_bias_ledger.py`。
5. 心跳寫`PROGRESS_HEARTBEAT.jsonl`。

## 6. 【看過結果後附註（2026-09-20 22:4x，研究帽）——本節內容不得用作判定，也不改動上面任何一格】

計算層跑完後、判定前，必須事先揭露的三件事（都是**機械事實**，不是解讀後的新規則）：

1. **K=5的檢定力先天很低。** 通道B表達式多為depth-2/3，需要12~16季歷史（yoy要+4季、
   surprise的8季std要+8季、naive預期再+4季），加上`net_income`/`shares`/`eps`資料起點≥2013Q1，
   導致Tier A 45個表達式中只有**8個**有2011年窗內的snapshot（K=5），其餘K=3（8個）或K=4（29個）。
   按第4節判定規則（族層級、僅K=5）只剩**4個獨立族**可檢定（20日、60日皆4個）。
   4個族的二項檢定，即使真訊號存在也很難達到事前p<0.01（需要3~4個族全同號）——
   這是**檢定力問題，不是「檢定過了但沒訊號」**，與原子.二「檢定力關卡」同一種形狀。
   **含義**：判定若為FAIL，SPEC第4節分支(b)那句「結論可外推為財報depth-2/3以內皆無效」
   **不成立**，只能寫成「此檢定力下未見訊號、K=5母體僅4族，無法排除」。
2. **Tier B宇宙與原子.五登記的407檔不同**：`tier_universe('B')`＝本機快取列數>0且三表齊全，
   跑時為**568檔**（567檔可用），因`財報原子.補快取`/`補借券`回補期間新增了非空資產負債表／
   現金流量表快取。`[自行裁量]`：不回頭固定為407（無該批股票清單存檔、無從精確重建）；
   Tier B本就只作輔助（第2節、第4節），此差異不影響判定，但**Tier B結果不得與原子.五
   Tier B逐格比對**。存活者偏誤警語不變（下市代理仍覆蓋較低）。
3. **任何替代規則（例如把K=4表達式併入、改用K-adjusted基準）＝修改判定門檻**，屬
   `CLAUDE.md`零之一白名單第5條（需總司令裁示），且**用這批已看過的結果去選規則
   就不是事前登記**——若要走這條路，須另開新SPEC、換一批未看過的檢定（例如延後到
   Tier A宇宙隨回補擴大後重跑），這批結果不得當驗證性證據。
