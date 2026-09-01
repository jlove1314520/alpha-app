# HYPOTHESIS_QUEUE.md — 有經濟理由的假設佇列（2026-08-29新增）

**這份檔案存在的理由**：使用者裁示「死命挖『有經濟理由的假設』，禁止暴力掃參數」
——盲掃所有參數組合＝製造假陽性＝違反`CLAUDE.md`「最高投資原則」第一條（假贏家會
拿真錢去賠）。這裡一條條排隊，每條都要先寫清楚「為什麼經濟上應該有效」跟「事前
綁定的判定關卡」，才能開始測——不是先跑數字再回頭找理由。

**跟這份佇列相對的另一半是`STRATEGY_GRAVEYARD.md`**：測過死掉的假設寫在那裡，
具體記「哪一點失效」，不是本檔案的一部分。

## 統一關卡（GATE_SEQUENCE，每條假設都要照這個順序，不得跳關）

1. **sanity**：資料/邏輯基本檢查（無NaN爆炸、方向不是反的、樣本數夠不夠）。
2. **隨機控制組（≥100 draws）**：配對式/排列式隨機對照，不是裸測。
3. **參數「密集高原」（非稀疏三點）**：附近一整片參數都要能過，不是剛好三個點
   湊巧過——單一參數點通過不算數（`BACKLOG.md`「少走彎路指南」item三已登錄
   這個升級要求）。
4. **成本/稅/滑價敏感**：1x/2x/3x情境（`validation/costs.py`既有費率），任一
   情境轉負就要誠實記錄，不能只挑1x講。
5. **leave-one-out**：逐年拿掉最大貢獻年份，看終值/報酬是否過度集中在少數年份
   （`fut_basis_carry`#35→#37的教訓：717x有82倍放大集中在2000-2002三年，樣本外
   直接FAIL——這個關卡就是為了在深挖早期抓到這種集中度問題，不用每次都走到
   deep_dive才發現）。
6. **逐年一致性≥5/6**：至少6個年度區間裡有5個方向一致（正報酬或贏過對照組），
   不是只看總和。
7. **樣本外（train/val切分）**：`validation.holdout`既有TRAIN_END/VAL_END框架，
   val期單獨過關，不能靠train期撐平均。
8. **前向paper**：樣本外過關後，才進`data/strategy_performance.json`前向模擬
   （見`update_strategy_performance.py`），逐日累積、不可回填。

**加上`CLAUDE.md`最高投資原則的額外要求（2026-08-29新增，凌駕以上關卡）**：
9. **下檔保護證明**：MDD受控、地雷率顯著低於隨機、regime危機情境（大盤/該
   假設的regime開關進入空頭/高波動）有降曝險，不是只看上檔數字。只有上檔漂亮、
   下檔沒守 = 不過，不管前面8關過得多乾淨。

**快殺標準（只能用便宜且決定性的證據，禁止「直覺沒肉」判死）**：
- 結構性不可能（數學上就是no-op，例如訊號永遠等於零/常數）。
- 資料不可及（查證過真的沒有免費/合規來源）。
- 觀測層級就無訊號（單測便宜關卡percentile遠低於門檻，不是邊緣case）。
- 已被控制組拆穿之偽影家族換皮（跟`BACKLOG.md`「少走彎路指南」item二偽影
  六家族其中一個結構相同、只是換個參數/換個排名方式，本質是同一個已死的
  機制）。

---

## 佇列（依這輪使用者裁示的順序，Weinstein/CTA排最前面）

### 1. Weinstein第二階段（趨勢/階段判定，股票）

**經濟理由**：Stan Weinstein的階段分析——股票從第一階段（築底/盤整）進入
第二階段（站上長期均線+均線上揚，法人/大戶開始建倉推升）時，趨勢延續機率
較高，是技術分析文獻裡少數有明確市場微結構解釋（機構建倉需要時間、不是
一次到位）的趨勢訊號，不是憑空的技術指標。

**具體假設定義**：站上30週（約150交易日）均線 + 均線本身上揚 + 相對大盤
強弱為正，三條件同時成立才算「進入第二階段」。

**已知相關背景（誠實揭露，不是全新未測領域）**：`TRIALS_LEDGER.md`#10/#11
（`weinstein_stage2_pilot_v1`手選30檔FAIL、`weinstein_stage2_unbiased`
無偏宇宙版EXPERIMENTAL，2026-08-22）已經測過早期版本；`strategies/
weinstein_stage2.py`的`gate`欄位（TAIEX vs MA200大盤位階開關）也已經被
`f_rel_strength_regime_switch`（#40，FAIL）用過。這次要測的是**新設計**
（見`data/strategies.json`的`weinstein_stage2_baseline`草稿登錄），跟舊版
差異點：新版用個股自身30週均線判斷（舊版部分用大盤位階當開關），需要在
深挖階段明確交代跟舊版本的差異，不能含糊地說「這是全新假設」。

**狀態（2026-08-29馬拉松自主循環第1輪更新）**：
- **v2具體實作**：`strategies/weinstein_stage2_v2.py`（新增，不改v1）——
  三個gate（站上150日均線+均線上揚+`f_rel_strength`(=60日個股報酬-60日
  大盤報酬，`factors.py`既有因子)>0），排名依`f_rel_strength`本身。
- **第1關 sanity：PASS**（`weinstein_v2_sanity.py`，用500檔流動性樣本
  快取快篩，40個季度檢查點，通過三個gate的股票池mean=95.2/median=107.0
  （486檔候選中，合理範圍，非系統性0檔或全部通過）；通過gate的股票事後
  20交易日報酬平均+2.24% vs 全樣本平均+1.41%，方向正確(+0.83pp)）。
- **B24乾淨重跑完成後，執行第2/4關時抓到真bug並修好**：第一版
  `stage2_signal_v2()`假設呼叫端已經算好相對強度欄位（沿用
  `factor_ic.py`快取現成的`f_rel_strength`），但`run_weinstein_
  unbiased_v2.py`走的是不同資料路徑（`adjusted_price_series()`，不經過
  `factors.py::prepare_factors()`），根本沒算過這個欄位——導致整個
  TRAIN/VALIDATION期間**0筆交易**（每天都被誤判「資料缺失」跳過）。
  這證明第1關sanity雖然PASS，但**測的不是後續關卡實際會用的資料載入
  路徑**（sanity用了factor_ic.py快取，剛好有這個欄位）——已修正：新增
  `prepare_price_data_v2()`獨立算相對強度（不依賴外部欄位是否存在），
  sanity腳本也同步改用同一條路徑重新驗證（結果不變，仍PASS，證明
  bug只在campaign腳本的資料路徑，不影響sanity本身的判定）。**教訓已
  寫進`weinstein_stage2_v2.py`docstring：之後sanity要用跟後續關卡完全
  同一條資料載入路徑測試**。
- **第2/4關結果：FAIL，移入`STRATEGY_GRAVEYARD.md`，不進第3/5/6/9關**。
  VALIDATION表面總報酬+56.72%贏買進持有，但拆解後beta貢獻+32.93%占
  過半，純alpha僅+23.80%（隨機控制組percentile=55.0，遠低於90.0門檻）；
  TRAIN純alpha本身就是負的(-3.66%)。兩期alpha在3x成本情境下都轉負
  （VALIDATION -16.37%、TRAIN -31.97%，TRAIN總報酬也轉負-19.65%）。
  **典型「表面漂亮、下檔/流程沒守」案例**，完整數字見
  `STRATEGY_GRAVEYARD.md`weinstein_stage2_v2條目。**這個結論只針對這個
  具體實作（60日相對強度窗口+150日均線+TAIEX 200日均線閘門），不代表
  Weinstein第二階段這個概念完全沒用**，後續變體（不同窗口/不同閘門/
  搭配其他篩選）未來若要測需要獨立走完整套關卡，不能沿用這次的失敗
  當作證據。

**佇列狀態（2026-09-01更新）：#1 Weinstein已結案（FAIL）、#2 CTA已結案（FAIL）、
#3 PEAD已結案（FAIL），目前進行中：#4股票股利率carry（因子層第1關cheap_pass，
待portfolio層構造）。**

### 2. CTA趨勢跟隨（時序動量，期貨）

**經濟理由**：時序動量（time-series momentum，Moskowitz/Ooi/Pedersen 2012）
——資產自身過去12個月報酬的正負號預測未來報酬方向，經典解釋是投資人對
新資訊漸進消化（underreaction）+ 動能交易者的自我實現（herding），是
CTA（管理期貨）產業幾十年的核心策略類型，不是這個專案自己發明的假說。

**具體假設定義**：台指期連續合約，用12個月回顧報酬正負號決定long/flat/
short，不是`fut_trend_multi_tf`（#18，FAIL）那種10/20/60日多時間框架
多數決——是更接近學術文獻標準定義的單一時序動量。

**已知相關背景**：`TRIALS_LEDGER.md`#18（`fut_trend_multi_tf`，多時間
框架動量多數決，FAIL）跟#20（`fut_ma_crossover_20_60`，均線交叉，FAIL）
都是趨勢家族的變體，但都不是標準時序動量定義（前者是多數決投票，後者是
均線交叉，兩者都跟「單一回顧期報酬正負號」這個經典CTA定義不同）——這是
這次要測的東西跟過去失敗案例之間刻意做出的區隔，不是換皮重測。

**狀態（2026-09-01結案）：FAIL，移入`STRATEGY_GRAVEYARD.md`**。
`cta_momentum_12m.py`（新增，可重複執行）：252交易日/12個月回顧報酬
正負號，月頻重平衡。第1關sanity PASS（long73.9%/short26.1%，29次月頻
換倉），**第2關隨機控制組（N=200）percentile=10.0，遠低於90.0門檻且
低於50**——真實策略終值-28.4%累積，同期買進持有+778.9%，配對式隨機
控制組中位數+180.9%。研判是動量崩盤（momentum crash）機制：單一慢速
12個月窗口在V型反彈時來不及轉向。不泛化成「CTA在台指期沒用」——已
FAIL的多窗口投票版本（`fut_trend_multi_tf`#18，percentile=82.5）比這次
單一窗口版本（10.0）明顯不那麼差，暗示多窗口平滑可能有幫助，但這是
未來變體才需要驗證的推論，不是本次結論。依協定第2關未過直接結案，未做
第3關以後的關卡。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#72。

### 3. PEAD（盈餘公告後漂移，股票）——已有部分驗證，待補強至策略層

**經濟理由**：Post-Earnings-Announcement Drift（Bernard/Thomas 1989經典
異常）——市場對意外的盈餘/營收消化不完全，公告後報酬會沿著意外方向持續
漂移數週到數月，是行為財務學裡最穩健的異常之一。

**誠實現況（這不是全新假設，是既有PASS因子的策略層follow-up）**：
`TRIALS_LEDGER.md`#7（`f_eps_surprise`，SUE方法論，**PASS**）跟#8
（`f_revenue_surprise`，SUE方法論，**PASS**）就是PEAD家族的因子層驗證，
已經通過因子級的統計檢定（Bonferroni校正n=6皆過）。**這條佇列項目要做的
是把這兩個已驗證因子組成一個明確的持股規則（月度再平衡/Top20/成本模型），
走完整套GATE_SEQUENCE（尤其是第7/8/9關：樣本外+前向paper+下檔保護），
不是重新驗證因子本身IC是否存在**——那部分已經有紮實證據了，缺的是portfolio
層級的完整驗證，跟B24對score_v2的處理是同一層級的工作。

**狀態（2026-09-01結案）：FAIL，移入`STRATEGY_GRAVEYARD.md`**。
`pead_portfolio_v1.py`（新增，可重複執行）：等權組合，月頻Top20。
第7關樣本外表面過關（TRAIN/VAL隨機控制組percentile 100.0/98.0），但
**alpha顯著性未過**（本專案已建立的評判標準，`portfolio_multifactor_v2`/
`weinstein_stage2_v2`都用過）——TRAIN alpha+7.36%(p=0.5349)、VAL
alpha+6.03%(p=0.4809)皆不顯著，VAL期總報酬(+54.65%)幾乎等於買進持有
大盤(+54.58%，只差+0.07pp)，beta+0.56~0.57顯示報酬主要來自市場曝險。
**不泛化成「PEAD/SUE因子沒用」**——因子層IC（`TRIALS_LEDGER.md`#7/#8）
依然PASS，死的是「等權/月頻/Top20」這個具體portfolio構造，未來IC加權
或情境式組合變體仍值得獨立測試。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#73。

### 4. Carry（股票股利率因子，期貨basis carry已有明確結論）

**經濟理由（股票端，新的角度）**：股利率（dividend yield）因子——高股利
股票可能反映市場對其成長性/風險的保守定價，也可能反映公司財務穩健、有
持續配息能力，經典價值/收益因子文獻的一支，跟`f_value_pb`/`f_value_pe`
（帳面/盈餘估值）是不同的估值角度（現金流分配 vs 資產負債表/損益表）。

**具體假設定義**：TW股票近12個月現金股利/股價（殖利率），高殖利率者
排名靠前——**這是這條佇列目前唯一的新東西**（其餘期貨carry已經測過，
見下）。

**期貨端carry：已有明確結論，不重測**——`TRIALS_LEDGER.md`#35→#37
（`fut_basis_carry`，CHEAP_PASS後深挖FAIL，717x的82倍放大集中在
2000-2002三年、樣本外percentile僅46.0）跟#38/#43（`fut_basis_mean_
reversion_60d`，均值回歸版本，EXPERIMENTAL但證據不夠乾淨）已經把basis
carry家族的三個機制（水位/動能/均值回歸）都測完，**這裡不重複排隊測
期貨carry**，只排隊測股票股利率這個新角度。

**狀態（2026-09-01更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程首次試跑）**：
**第1關cheap IC gate：CHEAP_PASS**。新增`factors.py::_dividend_yield_ttm_cash()`
（trailing 12個月現金股利加總，用`TaiwanStockDividend`的`CashExDividendTradingDate`
本身當pit_date，天然PIT-safe不需要延遲假設）+`prepare_factors()`裡的
`f_dividend_yield_ttm`（除以當日收盤價）+`factor_ic_dividend_yield.py`
（新增，沿用`factor_ic.py`既有cross-sectional IC框架）。結果：TRAIN
mean_ic=+0.0606 IR=+0.426、VAL mean_ic=+0.0807 IR=+0.562 hit_rate=0.77、
train/val同號、null percentile=100.0（門檻90.0）。**這只是因子層第1關，
不是最終PASS**——下一步是portfolio層構造（月頻/Top-N/成本模型，走完整
GATE_SEQUENCE第3~9關，跟`pead_portfolio_v1`同一個下一步性質）。

**狀態（2026-09-01T20:10更新，同日第二輪排程）**：portfolio層腳本已寫好
——`dividend_yield_portfolio_v1.py`（新增，逐字比照`pead_portfolio_v1.py`
架構，單因子`f_dividend_yield_ttm`、Top20、月頻21日換股），對應TRAIN/
VALIDATION兩期樣本外+成本敏感度(1x/2x/3x)+隨機控制組(N=100)的第7/8關
測試已啟動執行，但**單次執行超過13分鐘仍未跑完**（計算量問題非bug，
`ps`確認行程持續運算中），本輪依「有界工作單位」原則先收工，未拿到
最終數字，**尚未結案**。下一輪（或人工session）直接重跑
`python dividend_yield_portfolio_v1.py`即可拿到完整結果，判定時比照
`pead_portfolio_v1`/`weinstein_stage2_v2`同一把尺：隨機控制組percentile
過關不夠，alpha顯著性(p值)+beta拆解才是最終判準。完整見
`MARATHON_LOG.md`2026-09-01T20:10條目、`TRIALS_LEDGER.md`#74。

### 5. Regime輪動（依市場情境切換曝險/因子權重）

**經濟理由**：市場在不同狀態（多頭/空頭/高波動/低波動）下，同一個因子的
表現可能系統性不同（動能在多頭延續、在空頭崩潰是文獻裡有名的「動量崩潰」
現象，Daniel & Moskowitz 2016），依情境動態調整曝險理論上比固定曝險更
穩健——**這也正是`CLAUDE.md`最高投資原則第3條「regime閘門是強制overlay」
的具體實作方向**，不只是一個獨立假設，是之後所有策略都要具備的機制。

**已知相關背景（誠實揭露，這個方向已經測過、且結果不理想）**：
`TRIALS_LEDGER.md`#40（`f_rel_strength_regime_switch`，大盤位階開關+
相對強度十分位多空，**FAIL**）——分群IC層級的經濟解釋方向正確，但策略層
扣除十分位/20日換倉真實成本後，TRAIN期三種成本情境全負、VAL期對成本
高度敏感（1x微幅轉正、2x/3x轉負），沒有兌現。**這不代表regime輪動這個
方向本身死了**——#40測的是「用regime開關決定進出場」（平倉觀望版），
不是「用regime開關調整因子權重」（`PORTFOLIO_STRATEGY_SPEC.md`v2的
`regime_weighted`加權方式，目前狀態「待使用者確認」，跟#40是不同機制）。
下一步排隊要測的是**regime作為強制overlay套用在已經過關的候選上**（例如
B24-500的score_v2組合，見`BACKLOG.md`B24收尾的下一步），不是重新測一次
`f_rel_strength_regime_switch`這個已經FAIL的具體實作。

**狀態**：待B24收尾+B25（regime分情境報告）完成後，作為所有已過關候選的
強制overlay接上，不是獨立測試的假設。

### 6. 量價配合（Volume-Price Coordination，股票）

**經濟理由**：價量配合度——上漲伴隨放量、下跌伴隨縮量的股票，代表買盤
是真實需求推動而非籌碼派發，是技術分析裡「量價背離」概念的正向版本，
市場微結構上有一定支持（真正的機構建倉需要成交量承接）。

**誠實現況**：`volume_price_coordination`已經是`generate_scores_momentum.py`
的正式上線因子（題材動能榜十大因子之一），**但只有JSON-only上線路徑，
沒有PIT回測引擎**（跟momentum_board整體限制一樣，見`data/strategies.json`
的`momentum_board.limitations`）——這條佇列項目排隊等的是題材動能榜PIT
引擎建好之後，才能真正走完整套GATE_SEQUENCE，不是這條因子本身完全沒有
基礎，是缺回測基礎設施。

**狀態**：卡在題材動能榜PIT引擎（見`BACKLOG.md`momentum_board段落），
引擎建好前無法起跑第2關以後的步驟。

### 7. 低波動（Low Volatility，股票，已有明確結論，這裡只排隊測「策略層規則」）

**經濟理由**：低波動異常——高波動股票長期報酬反而較低，可能反映槓桿
限制投資人被迫追高波動股以達到報酬目標（leverage constraint theory，
Frazzini & Pedersen 2014），或投機性樂透偏好（Ang et al. 2006）。

**誠實現況（這不是全新假設）**：`TRIALS_LEDGER.md`#9（`f_low_vol`，
**PASS**，因子層級）已經通過驗證；US軌對應版本#39/#41（`f_us_low_vol`，
CHEAP_PASS後深挖**FAIL**——VAL期表面轉強但beta驟降至-0.891，代表是
方向性反向曝險而非橫斷面排序優勢）已經給出明確的策略層負面教訓。**這條
佇列項目要測的是TW版本能不能複製US版本的失敗模式，或者真的有橫斷面
排序優勢**——用US的deep_dive方法（十分位多空+beta對照）在TW股票上重測，
不是重新驗證TW的f_low_vol因子IC（那已經PASS了）。

**狀態**：待起跑，可直接沿用US軌`deep_dive_f_us_low_vol.py`的方法框架
改寫成TW版本。

### 8. 類股輪動（Sector Rotation，股票）

**經濟理由**：產業/類股資金流向——景氣循環不同階段，資金會系統性地從
某些類股流向另一些類股（例如升息循環資金偏好金融股、降息循環偏好成長股），
是總經/產業循環角度的輪動邏輯，跟個股層級的因子選股是不同的分析維度。

**誠實現況**：`sector_capital_flow`已經是`generate_scores_momentum.py`
的正式上線因子之一（`compute_sector_flow_trend()`），**同樣卡在題材動能
榜沒有PIT回測引擎**這個地基缺口——跟量價配合（#6）同一個限制，不重複
描述。

**狀態**：卡在題材動能榜PIT引擎，跟#6同一個依賴。

---

## 排隊順序總結（供之後接手的人/馬拉松快速定位）

1. ~~Weinstein第二階段（股票）~~——**2026-08-29馬拉松自主循環已結案：
   FAIL**（隨機控制組+成本敏感度雙雙不過，見`STRATEGY_GRAVEYARD.md`），
   移出排隊佇列。
2. ~~CTA趨勢跟隨（期貨）~~——**2026-09-01已結案：FAIL**（第2關隨機控制組
   percentile=10.0，見`STRATEGY_GRAVEYARD.md`），移出排隊佇列。
3. ~~PEAD策略層構造~~——**2026-09-01已結案：FAIL**（alpha顯著性未過，
   VAL期報酬幾乎等於買進持有，見`STRATEGY_GRAVEYARD.md`），移出排隊佇列。
4. **Carry（股票股利率，期貨端已有結論不重測）——現在排隊第一，進行中。**
   2026-09-01：第1關cheap IC gate CHEAP_PASS（`f_dividend_yield_ttm`，
   percentile=100.0，見`TRIALS_LEDGER.md`#74）。同日第二輪：portfolio層
   腳本`dividend_yield_portfolio_v1.py`已寫好，第7/8關驗證已啟動執行但
   單輪未跑完（計算耗時，非bug），下一輪直接重跑該腳本即可拿完整結果，
   尚未結案。
5. Regime輪動——作為強制overlay接上已過關候選，不是獨立假設，依附在
   B24收尾+B25之後。
6. 量價配合——卡在題材動能榜PIT引擎地基。
7. 低波動（TW版策略層）——可直接沿用US的deep_dive方法框架。
8. 類股輪動——卡在題材動能榜PIT引擎地基，跟#6同一個依賴。
