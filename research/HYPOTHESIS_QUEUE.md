# HYPOTHESIS_QUEUE.md — 有經濟理由的假設佇列（2026-08-29新增）

**這份檔案存在的理由**：使用者裁示「死命挖『有經濟理由的假設』，禁止暴力掃參數」
——盲掃所有參數組合＝製造假陽性＝違反`CLAUDE.md`「最高投資原則」第一條（假贏家會
拿真錢去賠）。這裡一條條排隊，每條都要先寫清楚「為什麼經濟上應該有效」跟「事前
綁定的判定關卡」，才能開始測——不是先跑數字再回頭找理由。

**跟這份佇列相對的另一半是`STRATEGY_GRAVEYARD.md`**：測過死掉的假設寫在那裡，
具體記「哪一點失效」，不是本檔案的一部分。

**⚠ 2026-09-04校準探針結論(乙)（見`CALIBRATION_PROBE.md`）**：第1關cheap gate的樣本自本日起
為300檔（`factor_ic.SAMPLE_SIZE`），100檔時代對|IC|≈0.03的弱訊號漏殺率60%。#11/#13/#21
（TRIALS_LEDGER #77/#79/#91）改標「未定」，待300檔重跑；主軸依`MARATHON_PROTOCOL.md`第0節
改為多因子組合策略迭代，不再單因子亂挖。

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

**佇列狀態（2026-09-02更新）：#1 Weinstein已結案（FAIL）、#2 CTA已結案
（FAIL）、#3 PEAD已結案（FAIL）、#4股票股利率carry已結案（FAIL，alpha顯著性
未過，見下方條目與`STRATEGY_GRAVEYARD.md`）、#9殘差動量Residual Momentum
已結案（FAIL，第1關cheap IC gate train/val正負號不一致，見下方條目與
`STRATEGY_GRAVEYARD.md`）、#10市場regime擇時overlay方法論框架已建置完成+
sanity通過（非PASS/FAIL判定，工具就緒待未來候選套用，見下方條目）、#11
產業內相對強度Sector-Neutral Relative Strength已結案（FAIL，第1關cheap
IC gate贏過洗牌null分布這一項未過，percentile=82.8<90.0門檻，見下方條目
與`STRATEGY_GRAVEYARD.md`）、#12 Betting-Against-Beta/低beta已結案（FAIL，
引用`TRIALS_LEDGER.md`#61既有跨軌結果判定、非新測試，train期IR僅0.009+
跨累積Bonferroni校正未過，見下方條目與`STRATEGY_GRAVEYARD.md`）、#13台股
三大法人連續買超持續性已結案（FAIL，第1關cheap IC gate train/val正負號
相反+null percentile=81.9未過90.0門檻，見下方條目與`STRATEGY_GRAVEYARD.md`）、
#14台股月營收公布事件效應已結案（FAIL，事件研究設計贏過洗牌null分布這一項
未過，percentile=68.0未過90.0門檻，見下方條目與`STRATEGY_GRAVEYARD.md`）、
#15波動度目標化Vol-Targeting已結案（FAIL，第2關輕量版隨機控制組Sharpe/
CAGR percentile僅8.0/3.0，遠低於90.0門檻且低於50，見下方條目與
`STRATEGY_GRAVEYARD.md`）、#7低波動（TW策略層）已結案（FAIL，VAL期
十分位多空隨機控制組percentile=85.0未過90.0門檻+兩期alpha皆不顯著，
見下方條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#82）、#16
同產業配對交易/統計套利已新增登記（尚未開始，2026-09-02T07:09本輪
判定佇列實質已空後設計的新假設軸，見下方條目）。**#5待B24/B25收尾、
#6/#8卡題材動能榜PIT引擎地基、#10（regime overlay基礎設施已就緒）
待未來有選股候選通過1~8關才能套用測試，四者仍為外部依賴阻塞、非
「排隊等待輪到」——下一輪應從#16第1關sanity開始執行，其餘四項外部
依賴若有進展再插回接續。**

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

**狀態（2026-09-01T23:23更新，第三輪排程）**：上一版執行結果TRAIN/
VALIDATION兩期皆0筆交易，查出是**實作bug**（借用的`pbv2._eligible()`
帶`n_components>=2`門檻，跟本策略刻意單因子的設計不合，把候選全篩空）
不是無訊號。已修復（新增本地`_eligible_single_factor()`，只改本策略
不動共用模組），重新在背景執行。

**狀態（2026-09-01T23:58更新，第四輪排程）**：接續上一輪，確認bug修復
邏輯正確並commit。背景重跑（PID 48852）已累計執行超過35分鐘仍在跑
（TRAIN/VAL各100次隨機控制組排列，計算量本身就大，非異常），**仍未
結案**，等下一輪排程觸發時查看`dividend_yield_portfolio_v1_run.log`
完整結果再判定。

**狀態（2026-09-02T00:45更新，第五輪排程）**：上一輪假設「背景行程會
存活到下一輪」**是錯的**——本輪發現PID 48852已不存在、log仍是0位元組，
研判headless呼叫結束時背景行程被一併終止（詳見`MARATHON_LOG.md`
2026-09-02T00:45條目的完整分析）。本輪重新啟動計算，前景等待約23分鐘
（確認行程持續運算中、非卡死），**觀察時間內仍未跑完**，`data/
dividend_yield_portfolio_v1_results.csv`仍是23:01的舊殘留（0筆交易，
已知是先前bug修復前的結果，非本輪產出）。**下一輪必須重新執行**
`python research/dividend_yield_portfolio_v1.py`，不能假設能接續本輪
留下的行程。這是這條假設連續第三輪「重跑中未結案」的根本原因——每輪
都在從頭重算，不是bug也不是無訊號，是單輪時間預算跟計算所需時間（實測
單次完整跑可能需要30分鐘以上）有落差，需要下一輪或使用者評估是否要
調整`HYPOTHESIS_QUEUE_PROTOCOL.md`的長計算任務處理方式（例如換一種
真正跨輪存活的啟動方式，或把這個工作單位改為「這輪就等到跑完為止」）。

**狀態（2026-09-02T01:20更新，第六輪排程，根治性修復）**：先精確量測
瓶頸（`market load: 1.5s`、`sample+factors load(80檔): 102.2s`、單次真實
回測`14.12s`、單次隨機回測`17.03s`），算出TRAIN+VALIDATION合計約需
206次回測（各1真實+2成本情境+100隨機）、總計約35~40分鐘——這正是連續
五輪卡住的量化根因。**根治方案**：把`run_one()`改成checkpoint可續跑
（新增`CHECKPOINT_PATH`落盤`data/dividend_yield_portfolio_v1_checkpoint.json`，
真實回測/成本敏感度/每10筆隨機控制組都會落盤，`main()`帶7分鐘時間預算
安全落在外層工具10分鐘逾時上限內，未跑完回傳`None`不做任何判定）。**改
之前先用n_random=3的縮小規模自測**：故意deadline過期只做完真實+成本、
再deadline足夠接續完成剩餘隨機控制組，跟完全不中斷一次跑完的對照組
逐欄位數值完全相同（`DETERMINISM_CHECK_PASS`），確認續跑邏輯正確不是
只是「看起來能跑」。**本輪內用同一session連續呼叫兩次腳本驗證真的在
累積進度**（TRAIN隨機控制組0→22→44/100，真實回測+成本敏感度已完成
不重算），`data/dividend_yield_portfolio_v1_checkpoint.json`不納入git
（`research/data/`本來就在`.gitignore`），是這台機器上的本機持久狀態，
之後每次排程觸發都會自動接續，**不會再重算已完成的部分**。本輪因USD
budget將近用盡而收工，**尚未結案**——下一輪執行
`python research/dividend_yield_portfolio_v1.py`會自動接續TRAIN剩餘
隨機控制組（44/100起），完成TRAIN後接著跑VALIDATION，預估TRAIN還需要
約3段、VALIDATION（期間較短，單次回測應更快）需要額外幾段，最終才會
產出`data/dividend_yield_portfolio_v1_results.csv`跟第7/8關判定。

**狀態（2026-09-02T01:41更新，第七輪排程）**：接續上一輪（鎖檔陳舊
30.7分鐘後由本輪回收，研判上一輪是寫完上面2026-09-02T01:20那則狀態
後、還沒commit就中斷）。確認上一輪的checkpoint機制程式碼正確、沒有
背景行程殘留（`ps`確認乾淨），直接沿用不重工。本輪內用前景阻塞方式
連續呼叫腳本兩次，每次約9分鐘（7分鐘計算預算+資料載入~102秒+~14秒
真實回測時間），**TRAIN隨機控制組進度44/100→65/100→85/100，持續在
累積、無重算**。仍未結案（TRAIN還差約15筆才完成，接著才輪到
VALIDATION全套）。下一輪執行`python research/dividend_yield_portfolio_v1.py`
會自動接續，預估還需要2~3輪才能跑完TRAIN+VALIDATION並產出第7/8關
判定。

**狀態（2026-09-02T02:31更新，第八輪排程，已結案：FAIL）**：接續上一輪
（`ps`確認無殘留背景行程），本輪內用背景+前景監控方式連續呼叫腳本四次，
TRAIN隨機控制組85→100/100（完成），VALIDATION真實回測+成本敏感度完成後
隨機控制組0→30→60→90→100/100（完成），**TRAIN+VALIDATION全部跑完，
`data/dividend_yield_portfolio_v1_results.csv`已產出**。腳本自身內建的
第7/8關判定邏輯（只看報酬贏買進持有+percentile>=90.0+MDD/beta<1.3）印出
表面PASS，但**這個判準沒有納入alpha顯著性**——套用本專案已建立的評判
標準（`portfolio_multifactor_v2`/`weinstein_stage2_v2`/`pead_portfolio_v1`
同一把尺）後，TRAIN alpha p=0.4868、VAL alpha p=0.1487，兩期都遠不顯著
（>0.05），VAL期報酬+71.93%相對買進持有+54.58%有+17.35pp超額（比PEAD的
+0.07pp明顯更大、VAL p值也比PEAD的0.4809更接近顯著），但仍未跨過0.05
門檻，人工判讀後改判**FAIL**，不採信腳本自己印出的PASS字樣。**不泛化成
「股利率因子沒用」**——因子層IC（#74）依然CHEAP_PASS，死的是「等權/
月頻/Top20」這個具體portfolio構造（跟PEAD同一種構造、同一種死法）。完整
見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#75、`MARATHON_LOG.md`
2026-09-02T02:31條目。佇列#4結案，接續佇列第一順位#9殘差動量。

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

**狀態（2026-09-02更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程接續，已結案：
FAIL）**：新增`deep_dive_f_low_vol.py`（直接移植US軌`deep_dive_f_us_low_
vol.py`方法框架，十分位多空+train/val+隨機控制組N=100+成本敏感度1x/2x/3x+
CAPM beta/alpha）——本輪接手時上一輪已在背景執行此腳本超過30分鐘（陳舊
鎖檔被回收），確認為真實存活行程後未重工，輪詢等待其自然跑完（非本輪
從頭重跑）。結果（100檔快取樣本，80/100可用，79檔有非NaN因子值）：
TRAIN(2015-2020)1x：total_return+13.99%、beta=-0.424、alpha+9.96%
(p=0.6011不顯著)、隨機控制組percentile=99.0（過關）；VAL(2021-2024)1x：
**total_return-30.09%**、beta=-0.718、alpha+4.65%(p=0.7590不顯著)、
**隨機控制組percentile=85.0（未過90.0門檻）**，2x/3x成本情境percentile
=87.0/88.0同樣未過。**VAL期策略本身虧損且輸給85%的隨機對照組**，兩期
alpha從未顯著，依協定判**FAIL**，不進第3關以後。**不泛化成「低波動因子
沒用」**——因子層IC（#9，PASS）不受影響，死的是「十分位多空、放空高
波動腿」這個具體構造，兩期負beta暗示放空高波動腿在VAL期反彈段系統性
虧損吃掉多頭腿獲利。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`
#82、`MARATHON_LOG.md`本輪心跳條目。佇列#7結案——**目前佇列其餘項目
（#5/#6/#8/#10）皆處於外部依賴阻塞狀態，沒有下一個可直接開工的候選**，
見下方「排隊順序總結」。

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

### 9. 殘差動量 Residual Momentum（Blitz/Huij/Martens 2011）

**經濟理由**：這個專案目前已死的三條假設（Weinstein第二階段、CTA趨勢跟隨、
PEAD策略層）共同死因都是「表面報酬漂亮但拆解後是beta曝險、alpha不顯著」
——傳統動量訊號本身就常常隱含大量市場/規模/價值beta。殘差動量先用因子
模型（至少CAPM市場beta，有現成的size/value因子可延伸為三因子）迴歸剝離
系統性曝險，只對「剝離後的殘差報酬」做動量排序，文獻上發現這樣做波動更
低、動量崩盤（momentum crash）現象更輕微——直接對症我們目前「都是beta」
的病，不是換皮重測已死的動量類假設。

**具體假設定義**：對個股過去12個月報酬做因子迴歸（市場，若有現成size/
value因子則延伸三因子），取迴歸殘差的累積報酬排序，做多殘差報酬最高
分位。

**已知相關背景**：跟已死的原始價格動量類假設（`f_rel_strength_regime_
switch`#40、Weinstein第二階段、CTA的`cta_momentum_12m`）不同——那些都是
「原始價格/相對強度動量」，沒有先剝離beta；跟PEAD（SUE盈餘動量）也不同，
那是財報驚訝不是價格動量。這是本項目第一次測試「剝離beta後的動量」。

**狀態（2026-09-02T02:58更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第九輪排程，
已結案：FAIL）**：新增`factors.py::prepare_factors()`「(u)殘差動量」段落
（`f_residual_momentum`：252日滾動CAPM beta，用「12個月股票報酬-beta×
12個月大盤報酬」近似12個月累積殘差報酬，沿用`f_bab`/`f_idio_vol`同一套
cov/var計算，只換窗口從60天到252天）+`factor_ic_residual_momentum.py`
（新增，沿用`factor_ic.py`既有cross-sectional IC框架，standalone
bonferroni_n=1）。結果：TRAIN mean_ic=-0.0092（n=40，方向為負）、VAL
mean_ic=+0.0305（n=47，方向為正）、null percentile=90.6（單看勉強過
90.0門檻）——**但train/val正負號不一致**，`evaluate_factor()`三項判準
之一未過，直接判**FAIL**，未進第2關以後。**不泛化成「剝離beta後的動量
機制本身沒用」**——這次用的是簡化一階近似（未逐日重算複利殘差）+只測
CAPM單因子（未延伸size/value三因子，本專案目前沒有現成TW版size/value
系統性因子可零成本複用），未來若要重測需要換一種殘差計算方式或延伸多
因子模型，不能沿用這次的具體實作當作「這個經濟機制已經測過」的證據。
完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#76。佇列#9結案，接續
佇列第一順位#10市場regime擇時overlay。

---

### 10. 市場regime擇時overlay（200MA/VIX/breadth）

**經濟理由**：`CLAUDE.md`最高投資原則第3條明講「regime閘門（危機一律降
曝險）是所有策略的強制overlay，非選配」——這不是選股邏輯，是「什麼時候
該收手」的獨立機制，直接針對「第一原則：永遠不要賠錢」做正面攻擊，不是
再測一個選股因子。用大盤200日均線位階、VIX水位（或台股對應的波動度
指標）、市場廣度（漲跌家數比）當總開關，危機情境降低整體曝險。

**具體假設定義**：這是overlay不是獨立選股策略——套用在已經過關的候選
組合上，在regime開關判定為空頭/高波動時，整體曝險依規則調降（例如降到
50%或更低），其餘時候維持原策略曝險。**目前沒有已過關的候選可以套用**
（CTA/PEAD/Weinstein都FAIL，Carry判定中）——先建立方法論框架（regime
判定規則+疊加曝險調整的回測工具），等未來有候選通過1~8關後再實際套用
測試第9關（下檔保護）。

**已知相關背景**：跟已死的`#40 f_rel_strength_regime_switch`不同——那個
是把regime開關當成「選股訊號本身的一部分」（開關決定進出場），這裡是
「獨立於選股邏輯之外的曝險總開關」，跟`HYPOTHESIS_QUEUE.md`#5（Regime
輪動）原本的區隔說明一致，這條就是把#5從「待B24收尾後才排」提前正式
排入佇列、給出具體下一步。

**狀態（2026-09-02T03:25更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十輪排程，
方法論框架建置完成+sanity通過，非PASS/FAIL判定）**：新增
`research/regime_overlay.py`——沿用兩個既有市場層級regime定義（200日
均線位階、20日波動度vs擴張窗中位數，皆非這輪新發明，見檔案docstring）
組成`EXPOSURE_MAP`（第一版單調參數，非搜尋/優化），並用TAIEX買進持有
本身當sanity測試對象。結果：①combined_regime分布非系統性單一格（4種
組合皆出現）；②TRAIN+VAL全期間MDD由-31.63%改善到-17.10%，Sharpe
0.55→0.60；③三個已知歷史危機期間（2018Q4貿易戰急跌/2020Q1新冠崩盤/
2022全年空頭）regime標籤正確辨識為多數空頭/高波動，窗內overlay MDD相對
baseline皆明顯改善（約腰斬）——機制方向正確，非常數/no-op/標籤錯位。
**這不是PASS/FAIL判定**：套用對象是大盤買進持有而非任何選股策略，不是
可部署的擇時策略，只是驗證「regime判定規則+疊加曝險回測工具」這個
基礎設施本身做對了事。市場廣度(breadth)規則仍未實作（誠實記錄「待補」，
理由見腳本docstring）。**下一步待未來有選股候選通過1~8關後**，把
`compute_regime_labels()`+`apply_overlay()`接到那個候選的日報酬序列上，
正式測第9關（下檔保護）——目前佇列裡沒有這樣的候選（Weinstein/CTA/
PEAD/Carry/殘差動量皆FAIL），所以#10本輪工作到此為止，接續佇列往下
一項推進。完整見`MARATHON_LOG.md`2026-09-02T03:25條目。

---

### 11. 產業內相對強度 Sector-Neutral Relative Strength

**經濟理由**：全市場排序的相對強度動量（`f_rel_strength`）天然帶有產業
輪動的beta（例如整個半導體產業一起漲跌時，排序前段班可能只是剛好都是
半導體股，不是真正的個股選股能力）。限制在同產業內部排序，天然中性化
市場+產業層級的beta曝險，只留下「個股相對同業的相對強弱」這個更乾淨的
訊號——直接對症「都是beta」的病，跟#9（剝離時間序列beta）是互補的兩種
中性化角度（#9剝離的是跨時間的系統性因子曝險，這條剝離的是橫截面的
產業曝險）。

**具體假設定義**：每個產業分類（沿用既有`industry_category`分類）內，
依過去N個月（跟`f_rel_strength`同一個回顧窗口，方便比較）相對強度排序，
做多產業內前段班、避開產業內落後段班。

**已知相關背景**：跟`f_rel_strength`（全市場排序）刻意做出區隔——同一份
原始資料、不同的排序範圍（產業內 vs 全市場），如果全市場版本已經在某些
測試中出現方向正確但下檔沒守住的情形，這條的假設是「限制在產業內排序
可能降低beta污染、提升訊噪比」。

**狀態（2026-09-02第十一輪排程，已結案：FAIL）**：新增
`factor_ic_sector_neutral_rel_strength.py`（沿用`factor_ic.py`既有
cross-sectional IC+洗牌null框架，不改該共用模組本身）——`f_rel_strength`
在每個橫斷面快照裡減去同產業分類（`universe.py::industry_category`，
排除ETF/基金類，`MIN_GROUP_SIZE=3`）內平均值。結果（100檔快取樣本，
80檔可用，73檔有非ETF產業分類，121個20交易日快照）：診斷顯示組別稀疏度
尚可（中位數每快照10組、組內4檔、39檔可用個股，非結構性no-op）。TRAIN
mean_ic=-0.0323 IR=-0.160(n=62)、VAL mean_ic=-0.0340 IR=-0.176
hit_rate=0.59(n=41)，**train/val同號（皆負）**、|val_ic|=0.034超過最低
門檻，但**null percentile=82.8未達90.0門檻**——三項判準之一未過，依協定
第1關未過直接結案，未進第2關以後。兩期IC方向皆為負，跟假設定義（做多
產業內前段班預期正向延續）相反，暗示若有訊號也是產業內短期反轉而非
延續。**不泛化成「產業中性化這個角度本身沒用」**——這次實作有兩個明確
保留：①產業分類用`universe.py`單一快照未處理`build_company_info.py`
已知的同日多產業分類歧義（約24%代碼受影響）；②100檔快取樣本組合
`MIN_GROUP_SIZE=3`統計力偏弱，未測過更大樣本。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#77。佇列#11結案，接續佇列
第一順位#12 Betting-Against-Beta/低beta。

**【2026-09-04馬拉松第334輪補充——`CALIBRATION_PROBE.md`「未定」路徑300檔
重跑，`TRIALS_LEDGER.md`#101】**：保留②「更大樣本統計力可能改善」被本輪
證偽——300檔樣本（248可用，組內中位數成員數4→6檔、可用產業組數10→20組，
確實變密了）percentile不升反降（82.8→**41.9**），IC量級也萎縮約
1/3~1/5，判定從「未定」正式改回**確定FAIL**，且比原100檔證據更明確
排除檢定力不足的可能。保留①（產業分類歧義未修正）、只測單一基底因子
兩項限制仍未解除。完整見`STRATEGY_GRAVEYARD.md`該條目補充、
`TRIALS_LEDGER.md`#101。

---

### 12. Betting-Against-Beta / 低beta（Frazzini-Pedersen 2014）

**經濟理由**：下檔保護型異常，跟前面幾條「剝離beta找alpha」的角度不同，
這條本身就是「beta曝險程度」當作選股訊號——文獻機制是槓桿限制投資人
被迫追高beta股票以達到報酬目標，導致高beta股票長期風險調整後報酬反而
較低，低beta股票提供下檔保護但沒有被市場正確定價，是`CLAUDE.md`「資本
保全優先」原則在因子層級的具體對應標的。

**具體假設定義**：估計個股相對大盤的beta（例如60日滾動回歸），做多
低beta分位（可選擇是否搭配放空高beta分位，或先測純多版本）。

**已知相關背景**：跟已經PASS的`f_low_vol`（因子層）是相關但不同的概念
——低波動看的是個股自身總波動率，低beta看的是相對大盤的系統性風險
曝險，文獻上這是兩個分開驗證的異常（低波動異常 vs betting-against-beta
異常），不能因為`f_low_vol`已經PASS就假設這條也一定PASS，需要獨立驗證；
也要注意跟US軌`f_us_low_vol`深挖後發現「方向性反向曝險」的FAIL教訓做
對照（見`TRIALS_LEDGER.md`#39/#41），這條要在deep_dive階段特別檢查beta
本身的穩定性，不能只看表面排序報酬。**（2026-09-02修正遺漏）此外
`f_bab`這個因子本身其實已在TW marathon軌道測過**（`TRIALS_LEDGER.md`
#61，2026-08-26，跟這裡`f_bab`的因子定義完全相同——60日滾動beta取
負號、cross-sectional排序），先前這個段落沒有揭露這件事，是本輪
發現並修正的遺漏。

**狀態（2026-09-02更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十二輪排程，
已結案：FAIL——引用既有結果判定，非新測試）**：本輪沒有跑新程式，是
補齊上面「已知相關背景」的遺漏後，依`TRIALS_LEDGER.md`#61既有結果做出
判定。#61原始數字：TRAIN mean_ic=+0.0020 IR=+0.009（n=63，基本上是
雜訊）、VAL mean_ic=+0.0302 IR=+0.141 hit_rate=0.47（n=47）、train/val
同號，對隨機打散null的percentile=91.0單獨看剛好過90.0門檻，**但當時
TW軌累積因子家族數m=27（含此因子），跨累積Bonferroni校正門檻=
100×(1-0.10/27)=99.63，91.0離這個門檻差距很大**，TW軌本身已判定
「CHEAP_PASS(單測)但批次/累積校正未過，降級為不確定，不進深挖清單」。
**這條假設佇列（獨立具名鎖`hypothesis_queue`）跟TW marathon雖互不阻塞，
但共寫同一份跨軌累積的`TRIALS_LEDGER.md`帳本**——多重比較的「已測
次數」是全專案共用，不是分軌各自歸零，若重新用standalone
bonferroni_n=1框架把同一個因子當「全新測試」重跑（數字會完全相同），
等於繞過已誠實套用的累積校正、把已判「證據不足」的因子透過換框架
包裝成「新的CHEAP_PASS」，違反`CONSTITUTION.md`第2節「多重比較」跟
`CLAUDE.md`最高投資原則第5條「誠實判不及格」的要求。加上TRAIN期IR
僅0.009（獨立支持理由：協定明訂可用快殺標準之一「觀測層級就無訊號」，
train半段量不到訊號），判定**FAIL**，不進第2關以後。**不泛化成
「beta曝險程度這個風險管理維度本身沒用」**——只測過「60日滾動beta、
cross-sectional排序、純多頭」這個具體實作，未測過多空版本/downside
beta/不同窗口，未來重測需換其中一個變體。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#78（本輪新增）、
`MARATHON_LOG.md`2026-09-02對應條目。佇列#12結案，接續佇列第一順位
#13台股三大法人連續買超持續性（**這個提示字已過時，#13已結案，見上方
#13條目跟本檔案「排隊順序總結」章節取得最新接續狀態**）。

---

### 13. 台股三大法人連續買超持續性

**經濟理由**：三大法人（外資/投信/自營商）在台股市場普遍被視為資訊
優勢方（informed flow），連續買超天數代表持續性的資訊優勢累積，比單日
買賣超金額更能過濾雜訊（單日大額買超可能只是換股操作或程式交易雜訊，
連續多日同方向才更可能反映真實的資訊優勢）。台股三大法人籌碼資料
（`www.twse.com.tw/rwd/zh/fund/T86`）每日更新、已經是這個專案現成的
資料源（T86回補已完成100%），且相對美股機構持股資料（13F季度揭露、
遠不即時）而言，台股三大法人連續買超因子較不擁擠（less crowded），
是台股專屬的資訊優勢角度。

**具體假設定義**：計算個股三大法人合計買賣超連續同方向的天數，排序
做多「連續買超天數最長」分位。

**已知相關背景**：跟既有籌碼類因子的既有測試（若有）不同之處在於強調
「連續性」而非單日金額或短期加總——這是這條假設要驗證的核心經濟機制，
deep_dive階段要特別確認「連續天數」本身的排序能力是否顯著優於「加總
金額」這種更簡單的既有做法，否則只是換個統計量重複驗證同一個訊號。

**狀態（2026-09-02更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十三輪排程，已結案：
FAIL）**：新增`factors.py::_consecutive_positive_streak_days()`
（`f_inst_streak_days`：逐日輸出「截至當天為止、三大法人合計淨買超連續
未中斷的天數」，非正即歸零，重用既有`_institutional_daily_net()`已算好的
`total_net`欄位）+`factor_ic_inst_streak_days.py`（新增，沿用`factor_ic.py`
既有cross-sectional IC+洗牌null框架，standalone bonferroni_n=1）。結果
（100檔快取樣本，80檔可用，121個20交易日快照）：TRAIN mean_ic=+0.0328
IR=+0.281(n=74)、VAL mean_ic=-0.0236 IR=-0.183 hit_rate=0.53(n=47)，
**train/val正負號相反**、null percentile=81.9（門檻90.0，未過）。三項判準
中兩項未過，依協定第1關未過直接結案，未進第2關以後。跟已FAIL的
`f_foreign_streak`（#3，外資單一法人版，打散對照76.0百分位+train/val
正負號相反）死法幾乎相同（percentile同一量級76.0 vs 81.9），暗示「連續
買超」這個時間序列結構本身（不論算外資或三大法人合計、不論用天數或金額
衡量）在此框架下測不出穩健訊號。**不泛化成「三大法人籌碼流向沒用」**——
既有`f_inst_flow`（20日淨額/成交值比率）仍在正式因子清單中未被推翻，死的
只是「連續期間」這個特定衡量角度，未來重測籌碼類因子建議換完全不同構造
（持股比例變化速率/法人分歧度/大額單筆），不建議再嘗試連續期間的其他
變體。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#79。佇列#13結案，
接續佇列第一順位#14台股月營收公布事件效應。

---

### 14. 台股月營收公布事件效應

**經濟理由**：台股上市櫃公司依法每月10日前必須公布上月營收（美股只有
季報，沒有這種高頻強制揭露義務），這是台股市場結構性的高頻資訊事件，
不是隨便挑的觀察窗口。營收公布當下市場消化不完全，若營收驚喜程度（相對
自身歷史趨勢或市場預期）夠大，理論上會有公布後的持續漂移，概念上類似
PEAD（盈餘公告後漂移）但事件頻率更高、是台股結構特有的資訊優勢來源，
不是重新測一次美股文獻的舶來品。

**具體假設定義**：月營收公布當日（10日前後，抓實際公布日期而非固定
假設10日），計算YoY成長率相對於自身歷史趨勢（或簡單的市場共識代理）
的驚喜程度，排序做多正驚喜分位，觀察公布後N個交易日（例如20日）的
累積漂移報酬。

**已知相關背景**：跟已經PASS的`f_revenue_surprise`（SUE方法論，因子層
IC驗證）有關聯但層級不同——`f_revenue_surprise`是橫截面IC驗證（因子層），
這條是「事件研究設計」（策略層，公布日當天進場、持有固定窗口，不是
每日橫截面排序），概念上更接近`HYPOTHESIS_QUEUE.md`#3 PEAD策略層那種
「用已知有效的因子IC，構造成具體可執行的持股規則」但這裡改用事件窗口
設計而非月頻橫截面再平衡，是不同的策略構造方式，值得獨立測試，不是
PEAD策略層（已FAIL）的重複測試——PEAD策略層FAIL的是「等權/月頻/Top20」
這個具體構造，不代表用事件窗口設計的營收驚喜策略也會失敗。

**狀態（2026-09-02T05:26更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十四輪排程，
已結案：FAIL）**：新增`monthly_revenue_event_study.py`——事件錨定窗口設計
（跟`factor_ic.py`固定日曆網格cross-sectional、`pead_portfolio_v1`月頻
再平衡都刻意不同：逐股用自己的月營收公布`pit_date`
（`pit.py::month_revenue_pit()`既有PIT邏輯）當事件起點，公布後第一個交易日
進場、持有20交易日，池化`factors.py::_revenue_surprise_sue()`(SUE)跟事件後
報酬）。100檔快取樣本，61檔有可用事件，總事件數8322筆（TRAIN 5594筆跨109
個月、VAL 2728筆跨47個月）。結果：TRAIN pooled Spearman IC=+0.0601
(p=0.0000,n=5594)、VAL pooled Spearman IC=+0.0204(p=0.2863,n=2728)，
train/val**同號**（皆正），quintile利差TRAIN+0.0318→VAL+0.0085（樣本外
萎縮73%），VAL |IC| vs 500次洗牌null percentile=68.0（門檻90.0，未過）。
三項判準（幅度非零/同號/贏過null）中「贏過洗牌null」這項未過，依協定第1關
cheap gate標準判**FAIL**，未進第2關以後。**不泛化成「月營收驚喜訊號完全
沒用」**——因子層日頻cross-sectional IC驗證（`TRIALS_LEDGER.md`#8，PASS）
不受影響、依然成立，這裡死的是「事件窗口設計」這個具體策略層構造，跟PEAD
策略層（#3，FAIL，月頻再平衡構造）是兩種不同portfolio構造但殊途同歸，暗示
SUE類訊號偏離原始日頻cross-sectional驗證設計、改包裝成月頻或事件窗口構造
時訊噪比整體偏弱。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#80、
`MARATHON_LOG.md`2026-09-02T05:26條目。佇列#14結案，接續佇列第一順位#15
波動度目標化Vol-Targeting。

---

### 15. 波動度目標化部位配置 Vol-Targeting

**經濟理由**：這個專案目前所有已測試/排隊中的假設清一色都是「選股」
維度（挑哪些標的），這條刻意測試完全正交的另一個維度：「edge是否在
部位大小配置（sizing），而不是選股本身」——用波動度目標化動態調整
整體曝險（波動度高時降低部位、低時提高部位，維持目標波動率水準），
這是純粹的風險管理/配置層策略，不涉及挑選任何個股，理論基礎是「風險
平價」類文獻——在相同的標的池上，光是調整曝險時機（不調整選股），
就可能改善風險調整後報酬（提升Sharpe、降低MDD），這對`CLAUDE.md`
「資本保全優先」原則來說是直接可用的機制，不用等其他選股假設先過關。

**具體假設定義**：對整體投組（或先用大盤本身當測試對象，因為不依賴
任何選股邏輯）用歷史滾動波動率（例如60日已實現波動率）計算部位倍數，
維持目標年化波動率（例如10%），比較跟固定100%曝險buy-and-hold的風險
調整後報酬（Sharpe/MDD/Sortino）差異。

**已知相關背景**：這是全新的、跟選股完全正交的維度，不重疊任何已測過
的因子或策略假設，也不依賴任何選股候選先通過關卡才能開工（可以獨立
於Carry/其他候選的判定結果先行測試）。

**狀態（2026-09-02更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程首次試跑，
已結案：FAIL）**：新增`vol_targeting_v1.py`——TAIEX（不依賴選股候選，套用
對象是大盤買進持有本身）60交易日滾動已實現波動度、目標年化波動率15%、
`exposure=clip(TARGET_VOL/realized_vol,0,1.0)`（刻意不允許槓桿，見腳本
docstring說明理由）、`exposure.shift(1)`避免未來函數。**第1關sanity**：
exposure非常數（min=0.434/max=1.000/mean=0.911/std=0.144，60.6%天數被
上限1.0截斷）、realized_vol與exposure相關係數=-0.946（機制方向正確）、
MDD全期間確實改善（-31.63%→-27.34%）、三個已知危機期間overlay MDD皆
改善——但同一組數字裡Sharpe/Sortino/Calmar在TRAIN/VAL/全期間**全部**比
買進持有差，是先於第2關就浮現的警訊。**第2關（輕量版隨機控制組，打亂
exposure時序N=100draws）**：真實（依realized_vol計時）曝險序列的Sharpe
percentile=8.0、CAGR percentile=3.0，遠低於90.0門檻且低於50——代表92%/
97%的隨機打亂時序反而表現更好，只有MDD percentile=90.0，但MDD單項改善
不能證明timing本身有加值（降低平均曝險本身幾乎必然壓低MDD，不論時機好
壞）。依協定快殺標準「觀測層級就無訊號」判**FAIL**，未進第3關以後。
死因研判：60日滾動已實現波動度是落後指標，市場V型/U型復甦時價格常在
波動度真正回落前就已反彈，導致這個機制系統性錯過反彈段報酬。**不泛化
成「波動度目標化/風險平價概念本身沒用」**——這次刻意不允許槓桿（拿掉
文獻機制「低波動期加碼」那一半）、只測單一60日窗口/單一15%目標/單一
TAIEX標的，未測允許槓桿版本、不同窗口、或套用在真正的選股組合上。完整
見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#81。佇列#15結案，接續佇列
第一順位#7低波動（TW策略層，可直接沿用US的deep_dive方法框架，目前佇列
裡唯一無阻塞依賴的下一個排隊項目——#5依附B24/B25、#6/#8卡題材動能榜PIT
引擎、#10待有選股候選通過1~8關）。

---

## 排隊順序總結（供之後接手的人/馬拉松快速定位）

1. ~~Weinstein第二階段（股票）~~——**2026-08-29馬拉松自主循環已結案：
   FAIL**（隨機控制組+成本敏感度雙雙不過，見`STRATEGY_GRAVEYARD.md`），
   移出排隊佇列。
2. ~~CTA趨勢跟隨（期貨）~~——**2026-09-01已結案：FAIL**（第2關隨機控制組
   percentile=10.0，見`STRATEGY_GRAVEYARD.md`），移出排隊佇列。
3. ~~PEAD策略層構造~~——**2026-09-01已結案：FAIL**（alpha顯著性未過，
   VAL期報酬幾乎等於買進持有，見`STRATEGY_GRAVEYARD.md`），移出排隊佇列。
4. ~~Carry（股票股利率）~~——**2026-09-02第八輪已結案：FAIL**（alpha顯著性
   未過，TRAIN p=0.4868/VAL p=0.1487皆遠不顯著，見`STRATEGY_GRAVEYARD.md`/
   `TRIALS_LEDGER.md`#75），移出排隊佇列。因子層IC（#74）本身仍是
   CHEAP_PASS，未被推翻，死的只是這個具體portfolio構造。
5. Regime輪動——作為強制overlay接上已過關候選，不是獨立假設，依附在
   B24收尾+B25之後。
6. 量價配合——卡在題材動能榜PIT引擎地基。
7. ~~低波動（TW版策略層）~~——**2026-09-02排程接續已結案：FAIL**（十分位
   多空，VAL期隨機控制組percentile=85.0未過90.0門檻、真實策略VAL期虧損
   30%輸給85%隨機對照、兩期alpha皆不顯著，見上方條目與
   `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#82），移出排隊佇列。不
   泛化成低波動因子沒用——因子層IC（#9）不受影響，死的是十分位多空、
   放空高波動腿這個具體構造。
8. 類股輪動——卡在題材動能榜PIT引擎地基，跟#6同一個依賴。
9. ~~殘差動量Residual Momentum~~——**2026-09-02第九輪排程已結案：FAIL**
   （因子層第1關cheap IC gate，train/val正負號不一致，見
   `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#76），移出排隊佇列。
10. 市場regime擇時overlay——**2026-09-02第十輪排程：方法論框架建置完成+
    sanity通過**（`research/regime_overlay.py`，regime標籤在三個已知歷史
    危機期間正確辨識+overlay確實降低曝險與MDD，見上方條目完整數字）。
    **這不是PASS/FAIL判定**，是基礎設施就緒——套用對象是TAIEX買進持有，
    不是選股策略。下一步待未來有選股候選通過1~8關後才能正式測第9關，
    目前佇列裡沒有這樣的候選，本輪工作到此為止，移出「排隊第一」位置。
11. ~~產業內相對強度Sector-Neutral~~——**2026-09-02第十一輪排程已結案：
    FAIL**（第1關cheap IC gate贏過洗牌null分布這一項未過，percentile=
    82.8<90.0門檻，train/val同號但方向與假設預期相反，見
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#77），移出排隊佇列。
12. ~~Betting-Against-Beta/低beta~~——**2026-09-02第十二輪排程已結案：
    FAIL**（引用`TRIALS_LEDGER.md`#61既有跨軌結果判定、非新測試，
    train期IR僅0.009+跨累積Bonferroni校正未過，見上方條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#78），移出排隊佇列。
13. ~~台股三大法人連續買超持續性~~——**2026-09-02第十三輪排程已結案：
    FAIL**（因子層第1關cheap IC gate，`f_inst_streak_days`train/val正負號
    相反+null percentile=81.9<90.0門檻，跟已FAIL的`f_foreign_streak`
    （#3）死法幾乎相同，見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#79），
    移出排隊佇列。
14. ~~台股月營收公布事件效應~~——**2026-09-02第十四輪排程已結案：FAIL**
    （事件研究設計第1關cheap gate，贏過洗牌null分布這一項未過，
    percentile=68.0<90.0門檻，train/val同號但VAL期樣本外萎縮73%+不顯著，
    見上方條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#80），移出
    排隊佇列。因子層IC（`TRIALS_LEDGER.md`#8）本身仍是PASS，未被推翻，
    死的只是「事件窗口」這個具體策略層構造。
15. ~~波動度目標化Vol-Targeting~~——**2026-09-02排程首次試跑已結案：FAIL**
    （第2關輕量版隨機控制組，打亂exposure時序後真實Sharpe/CAGR percentile
    僅8.0/3.0，遠低於90.0門檻且低於50，只有MDD單項改善但不足以證明timing
    本身有加值，見上方條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`
    #81），移出排隊佇列。不泛化成波動度目標化概念本身沒用——這次刻意不
    允許槓桿、只測單一窗口/單一標的。
16. ~~同產業配對交易/統計套利Pair Trading~~——**2026-09-02排程接續已結案：
    FAIL**（第2關隨機控制組N=100，相關係數篩選相對「同樣動作隨機挑12對」
    無顯著加值，percentile=56.0/39.0遠低於90.0門檻，屬「縮小候選池」型
    偽影，另一條獨立方法用完整多空P&L回測也在第3關參數高原判死，殊途同歸，
    見上方條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#83），移出排隊
    佇列。不泛化成配對交易/統計套利機制類別完全沒用——只測了簡單相關係數
    篩選+固定參數這個具體實作。
17. ~~52週高點接近度~~——**2026-09-02接續排程已結案：FAIL**（因子層#84
    CHEAP_PASS後portfolio層月頻Top20構造第7/8關，腳本內建判準表面PASS但
    alpha顯著性未過（VAL p=0.0831，本佇列目前最接近顯著的FAIL案例），
    依既有alpha顯著性+beta拆解標準人工override判FAIL，見上方#17條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#85），移出排隊佇列。不
    泛化成因子沒用——因子層IC（#84）不受影響，死的是具體portfolio構造。
18. ~~短期反轉（1週Reversal）~~——**2026-09-02T23:59第十八輪排程已結案：
    FAIL**（因子層第1關cheap IC gate，`f_short_term_reversal_1w`
    train/val同號但null percentile=41.3<90.0門檻且低於50，見上方#18
    條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#87），移出排隊
    佇列。不泛化成短期反轉完全無效——只測過1週窗口+100檔樣本，未測
    更大樣本版本。**佇列#1~18原始15條項目（含#16/#17新增）全部結案，
    剩餘#5/#6/#8/#10仍卡外部依賴（同上）——本輪判定佇列實質已空，設計
    新假設軸#19（跨市場美股隔夜報酬外溢效應，見下方新章節），現在排隊
    第一，尚未開始第1關。**
19. ~~跨市場美股隔夜報酬外溢效應~~——**2026-09-03第二十輪排程已結案：
    FAIL**（第1關cheap gate CHEAP_PASS但第2關以後具體擇時規則第6關逐年
    一致性未過，TRAIN期11年僅4年正報酬，見上方#19條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#89），移出排隊佇列。不
    泛化成相關性沒用——第1關CHEAP_PASS（#88）不受影響，死的是這個具體
    擇時規則。
20. ~~純毛利率因子Gross Profitability~~——**2026-09-03T13:47排程已結案：
    FAIL**（第1關cheap IC gate，null percentile=48.4遠未過90.0門檻，見
    上方#20條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#90），移出
    排隊佇列。
21. ~~月營收「意外」漂移×低關注度~~——**2026-09-03排程已結案：FAIL**
    （低/高關注度兩組皆未過90.0門檻且方向與假設預期相反，見上方#21
    條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#91），移出排隊
    佇列。
22. ~~品質×營收加速×法人吸籌複合訊號+低波動閘門~~——**2026-09-03第
    二十三輪排程已結案：FAIL**（第1關sanity，四gate合取候選池14.0%
    快照有候選，門檻30.0%未過，四者近似統計獨立無協同，推翻假設核心
    前提，見上方#22條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`
    #92），移出排隊佇列。
23. ~~Piotroski F-score當價值榜排雷閘門~~——**2026-09-03第二十六輪排程
    已結案：FAIL**（核心比較：+F-score gate(F>=6)後兩期alpha的p值皆
    變得更不顯著（TRAIN 0.2672→0.4743、VAL 0.1441→0.1772），地雷率沒有
    一致改善（TRAIN惡化25.3%→29.1%、VAL改善16.9%→5.7%，一升一降），
    VAL期return大幅流失機會成本（+85.52%→+33.31%），依#23事前訂的
    「沒有實質改善代表問題不是陷阱股」判準快殺，見上方#23條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#93/#94），移出排隊佇列。
    **佇列#19~23（馬拉松自主新增的#19+使用者2026-09-03裁示新增5條中的
    前4條#20~23）至此全部結案，現在排隊第一順位是#24（除權息季節行為
    效應），尚未開始第1關，下一輪從sanity（含FinMind除權息日曆資料源
    可行性查證）開始，不跳關。**
24. ~~除權息季節行為效應~~——**2026-09-03排程接續已結案：FAIL**（三個
    cheap gate皆未過90.0門檻，見上方#24條目與`STRATEGY_GRAVEYARD.md`/
    `TRIALS_LEDGER.md`#95），移出排隊佇列。**佇列#20~24（使用者
    2026-09-03裁示新增5條）全數結案。剩餘#5/#6/#8/#10仍卡外部依賴，
    下一輪需先確認依賴是否解鎖，未解鎖則佇列實質已空，需設計新假設軸。**
25. ~~月轉效應（Turn-of-Month Effect，指數層級，非選股）~~——**2026-09-03
    排程接續已結案：FAIL**（第1關cheap gate，N=3/N=4兩種窗口定義皆
    train/val正負號相反，見上方#25條目與`STRATEGY_GRAVEYARD.md`/
    `TRIALS_LEDGER.md`#96），移出排隊佇列。**佇列#1~25全數結案。剩餘
    #5/#6/#8/#10仍卡外部依賴（同上，本輪重新確認仍未解鎖），設計新
    假設軸#26（全市場融資餘額成長率當槓桿/擁擠度regime訊號），現在
    排隊第一。資料可行性查證已於2026-09-03排程接續完成並確認可行
    （找到TWSE官方全市場歷史數字，見下方#26條目「資料可行性查證：
    已確認可行」段落），下一輪從第1關cheap gate開始，不跳關。**
26. ~~全市場融資餘額成長率（Margin Debt Growth）~~——**2026-09-03
    排程接續已結案：FAIL**（662週回補完成後第1關cheap gate，20d/60d
    兩種窗口定義皆train/val正負號相反，60d窗口VAL percentile=88.5
    接近但未過90.0門檻，見上方#26條目與`STRATEGY_GRAVEYARD.md`/
    `TRIALS_LEDGER.md`#97），移出排隊佇列。不泛化成「融資餘額槓桿
    水位這個維度完全無效」——只測了週頻近似成長率+Spearman相關+
    同長度forward回撤幅度這個具體構造。
27. ~~多因子z-score複合評分（GP+value_pb+revenue_surprise等權）~~——
    **2026-09-04排程接續已結案：FAIL**（第1關cheap IC gate
    CHEAP_PASS，但使用者原話要求的300-draw隨機因子組合控制第2關
    percentile=87.2未過90.0門檻，依「事前綁定不事後移動門柱」鐵律
    直接判FAIL，未做正交性檢查/leave-one-factor-out，見上方#27條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#102），移出排隊佇列。
    不泛化成「多因子z-score複合這個構造類別完全沒用」——只測了這三個
    具體因子等權組合。
28. ~~市場廣度背離（Breadth Divergence）當regime擇時訊號~~——
    **2026-09-04排程接續已結案：FAIL**（第1關sanity PASS後轉具體
    曝險規則走第2關隨機控制組，TRAIN/VAL打亂exposure時序percentile
    分別為54.0/51.0，遠低於90.0門檻且貼在50附近，依快殺標準「已被
    控制組拆穿之偽影家族換皮」判定，見上方#28條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#105），移出排隊佇列。
    不泛化成「市場廣度這個概念完全沒用」——只測了固定0.3/1.0二元曝險
    切換這個具體規則。**佇列#1~28全數結案。**
29. ~~等權重再平衡溢酬 Diversification Return / Equal-Weight Rebalancing
    Premium~~——**2026-09-04接續排程已結案：FAIL**（第1~5關全數PASS——
    sanity、隨機控制組bootstrap N=100 CHEAP_PASS、參數密集高原17/17點、
    成本/稅/滑價1x/2x/3x敏感度三情境皆正、leave-one-out拿掉最大貢獻年
    2020後仍為正——但**第6關逐年一致性未過**：TRAIN期6個年度（2015-2020）
    僅4個正報酬（2016/2019為負），4/6=66.7%未達>=5/6=83.3%門檻，依快殺
    標準判定，未進第7/8/9關，見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`
    #114），移出排隊佇列。設計出跟前28條在機制分類上真正不同的第三類
    假設（既非①方向性選股排序、也非②timing/exposure overlay，是
    ③portfolio construction——給定同一組標的、不做任何選股判斷、全程
    滿倉不做曝險縮放，純粹用「定期拉回等權重」這個機械式再平衡動作本身
    測試diversification return，**基準操作化偏離原文市值加權，改為t0
    等權重buy-and-hold**，理由見上方#29條目「狀態」小節）。**不泛化成
    「等權重再平衡機制在台股完全無效」**——第1~5關已扎實證明效果存在、
    非隨機、非集中在單一年份，死的只是這個具體159檔樣本/2015-2020窗口
    下年度方向不夠一致，是本佇列走最深、通過最多關卡才死的案例之一。
    **佇列#1~29全數結案。剩餘#5/#6/#8/#10仍卡外部依賴（本輪未重新
    查證，狀態沿用先前判定），下一輪需先確認依賴是否解鎖，若仍未解鎖
    則佇列實質已空，依協定第1節設計新假設軸。**
30. 個股融資使用率（Margin Financing Utilization Ratio）——強制平倉/
    流動性螺旋風險訊號——**2026-09-04本輪排程新增，尚未開始第1關**。
    重新查證#5/#6/#8/#10四項外部依賴仍全部卡住（`value_board_v2`仍
    `回測未通過`、題材動能榜/未來性濾網仍`紙上交易中`，跟#29查證結果
    一致，無新進展），判定佇列實質已空，設計出跟前29條在機制分類上
    真正不同的第四類假設（既非①方向性選股排序、②timing/exposure
    overlay、③portfolio construction，也非④配對交易均值回歸，是
    ⑤強制平倉/流動性驅動賣壓——Brunnermeier & Pedersen margin spiral
    機制，資料可行性已查證FinMind`TaiwanStockMarginPurchaseShortSale`
    涵蓋2015年至今完整歷史可直接複用，完整內容見下方新章節）。**第1關
    cheap IC gate已CHEAP_PASS**（train/val同號皆負、null percentile=
    100.0，`TRIALS_LEDGER.md`#116），**deep_dive第一步下跌段vs上漲段
    分組IC已完成**（下跌段VAL\|IC\|=0.1817遠大於上漲段0.0280，約6.5倍，
    方向與核心機制主張完全吻合，`TRIALS_LEDGER.md`#117）。**portfolio層
    構造（`margin_utilization_regime_portfolio_v1.py`）已設計完成並開始
    執行**：regime-conditional避開高融資使用率個股（危機regime時挑最低
    使用率TOP20、非危機regime挑流動性最高TOP20，控制組核心判準是打贏
    「危機期隨機選股」而非買進持有大盤，完整設計見上方#30條目最新狀態）。
    checkpoint可續跑機制運作正常（本輪內驗證），**TRAIN期真實訊號+成本
    敏感度已完成、隨機控制組進度20/100，尚未結案**，現在排隊第一，下一輪
    重跑腳本即可自動接續（比照`#4`股利率carry的多輪checkpoint接續先例）。
    ~~個股融資使用率~~——**2026-09-05接續排程已結案：FAIL**（TRAIN+VAL
    兩期100/100隨機控制組跑完，TRAIN percentile=1.0決定性反證（worse than
    99/100隨機對照）、VAL percentile=99.0表面過關但alpha p=0.4991不顯著+
    beta+0.638，依既有alpha顯著性+beta拆解標準判FAIL，見上方#30條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#120），移出排隊佇列。不
    泛化成機制完全無效——因子層cheap gate（#116）跟下跌/上漲段分組IC
    （#117）方向皆一致，死的是「TOP20純多方向、regime二元切換」這個
    具體構造。**佇列#1~30全數結案。剩餘#5/#6/#8/#10仍卡外部依賴（本輪
    重新查證仍未解鎖），設計新假設軸#31（台指選擇權Put/Call成交量比率
    當市場regime/擇時訊號，見下方新章節），現在排隊第一，尚未開始第1關。**
31. ~~台指選擇權Put/Call成交量比率~~——**2026-09-05接續排程第2/3關已
    結案：FAIL**（第1關cheap gate原為CHEAP_PASS，`option_pcr_gate.py`，
    TRAIN r=+0.0611/null percentile=98.2、VAL r=+0.0587/null
    percentile=94.0，見`TRIALS_LEDGER.md`#121；但轉具體overlay規則後
    `option_pcr_overlay_v1.py`第2關隨機控制組表面過關（percentile=100.0）
    卻兩期報酬皆大幅跑輸買進持有（TRAIN-36.91% vs+55.93%、VAL-17.57%
    vs+59.73%），第3關參數密集高原僅7/49點(14%)為正、遠低於60%門檻，
    判定FAIL，見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#122），移出
    排隊佇列。不泛化成「PCR訊號本身沒用」——第1關cheap gate的時序相關性
    依然CHEAP_PASS，死的是「trailing百分位+單一固定門檻+二元曝險切換」
    這個具體overlay構造。**（本輪修正：本檔案先前此處字樣停留在「尚未
    結案，接續第2關」，跟#31條目自身已寫的結案狀態不同步，已在
    2026-09-05 hypothesis_queue排程本輪修正對齊——這正是
    `HYPOTHESIS_QUEUE_PROTOCOL.md`第1節警告過的「條目本身已結案但總結
    區塊字樣沒同步更新」情況。）**佇列#1~31全數結案，剩餘#5/#6/#8/#10
    仍卡外部依賴（未重新查證，跟#29/#30/#31查證結果一致，無理由預期
    已解鎖），設計新假設軸#32（美元兌台幣匯率當資金外流/市場壓力
    regime訊號，見下方新章節）。**#32已於2026-09-05接續排程結案：FAIL**
    （第1關cheap gate train/val正負號相反，TRAIN r=+0.0368percentile=
    82.6未過、VAL r=-0.0723percentile=96.0過但方向不一致，見上方#32
    條目與`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#123），移出排隊
    佇列。**佇列#1~32全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪
    2026-09-05T03:23重新查證仍未解鎖），設計新假設軸#33（美國公債
    殖利率曲線10Y-2Y利差當全球風險regime訊號，見下方新章節），現在
    排隊第一，尚未開始第1關。**
33. ~~美國公債殖利率曲線（10Y-2Y利差）~~——**2026-09-05接續排程第1關
    已結案：FAIL**（`fred_yield_curve_gate.py`，TRAIN r=-0.0636
    percentile=98.6過、VAL r=-0.0242**percentile=52.8遠未過**90.0門檻，
    且兩期方向皆與事前綁定的正相關預期相反，見上方#33條目與
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#124），移出排隊佇列。不
    泛化成「殖利率曲線這個總經領先指標本身沒用」——只測過利差水位單一
    口徑+M=20交易日這組事前綁定窗口，未測變動率/其他窗口/傳導延遲。
    **佇列#1~33全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證
    `BACKLOG.md`仍未解鎖），設計新假設軸#34（銅金比Copper/Gold Ratio
    當全球成長/風險偏好regime訊號，見下方新章節），現在排隊第一，
    尚未開始第1關。**（本輪修正：這一條在「排隊順序總結」原先誤標為
    「32.」，跳過了#32美元兌台幣匯率自己應有的編號，導致從此處起編號
    落後內容區塊標題一號——已於2026-09-05 hypothesis_queue本輪修正對齊，
    這正是`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節警告過的「排隊順序總結」
    跟內容區塊標題編號不同步情況。）
34. ~~銅金比（Copper/Gold Ratio）~~——**2026-09-05接續排程第2關以後已
    結案：FAIL**（第1關cheap gate原為CHEAP_PASS，`copper_gold_ratio_gate.py`，
    TRAIN r=-0.2467/null percentile=100.0、VAL r=-0.1758/null
    percentile=100.0，見`TRIALS_LEDGER.md`#125；但轉具體overlay規則
    （方向依實測負相關反轉）後`copper_gold_ratio_overlay_v1.py`第2/3關
    表面過關（隨機控制組percentile=100.0、參數高原44/49點(90%)），**第5關
    leave-one-out未過**：TRAIN逐年報酬2015~2020複利總報酬+10.14%幾乎
    全部由單一年份2019(+37.43%)貢獻，拿掉2019後剩餘複利總報酬翻負為
    -19.85%，依協定第5關未過快殺判定FAIL，未進第6關以後，見
    `STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#126），移出排隊佇列。不
    泛化成「銅金比訊號本身沒用」——第1關cheap gate（#125）的時序相關性
    依然CHEAP_PASS且是本佇列timing類最強訊號，死的是「trailing百分位+
    單一固定門檻(0.70)+二元曝險切換」這個具體overlay構造，訊號強度不等於
    構造穩健性是這次最值得記住的教訓。**佇列#1~34全數結案，剩餘#5/#6/
    #8/#10仍卡外部依賴（本輪重新查證仍未解鎖），設計新假設軸#35（賣出
    TAIEX選擇權波動度風險溢酬 Volatility Risk Premium，見下方新章節），
    現在排隊第一，尚未開始第1關。**
35. ~~賣出台指選擇權波動度風險溢酬 VRP~~——**2026-09-05接續排程第1關
    已結案：FAIL**（`vrp_gate.py`，Brenner-Subrahmanyam近似公式反推IV，
    TRAIN mean_spread=+1.19pp/t檢定p=0.0004過、VAL mean_spread=+0.76pp
    <1pp門檻**且t檢定p=0.0595僅些微未過**，Wilcoxon兩期皆顯著、兩期
    中位數皆明顯為正，暗示溢價可能確實存在但分布右偏、事前綁定判準
    不因此放寬，見上方#35條目與`STRATEGY_GRAVEYARD.md`/
    `TRIALS_LEDGER.md`#127），移出排隊佇列。不泛化成「台股VRP完全不
    存在」——只測了ATM月合約+Brenner-Subrahmanyam近似+5日抽樣這組具體
    實作。**佇列#1~35全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新
    查證仍未解鎖），設計新假設軸#36（個股融券使用率/借券成本當知情
    放空者訊號，資料可行性已查證`TaiwanStockMarginPurchaseShortSale`
    本就含`ShortSaleTodayBalance`/`ShortSaleLimit`欄位可直接複用），
    現在排隊第一，尚未開始第1關。**
36. 個股融券使用率（Short Sale Utilization Ratio）——**2026-09-05
    hypothesis_queue接續排程第1關cheap IC gate已完成：CHEAP_PASS**
    （`factor_ic_short_sale_utilization.py`，train/val同號皆負、null
    percentile=100.0，見上方#36條目與`TRIALS_LEDGER.md`#129）。**尚未
    結案**——第2關以後已起跑（`short_sale_utilization_portfolio_v1.py`，
    測訊號多頭鏡像半邊，放空腿因引擎不支援尚未驗證，見上方#36條目誠實
    揭露段落），本輪TRAIN真實策略+成本敏感度已算完，隨機控制組checkpoint
    進度持續接續（20→30→40→**50**/100 draws，最新一次是2026-09-05T09:23
    hypothesis_queue排程接續，420秒時間預算內記憶體內達59但落盤頻率
    僅每滿10筆一次，實際持久化50/100，下一輪從50接續）。前一輪
    （T09:04）曾因鎖檔陳舊回收（LOCK_STALE，判斷疑似上一輪執行中斷）
    而留下已寫檔但未commit的殘留，本輪已一併確認內容正確並隨本次進度
    一起補commit，非資料遺失。VALIDATION期仍完全尚未開始，`is_holdout_
    consumed()`執行前後皆確認False，待下一輪接續跑完TRAIN 100 draws
    才能判定，**佇列排隊順序仍是#36（未結案，接續第2關）**，剩餘
    #5/#6/#8/#10仍卡外部依賴（同上）。

**佇列現況小結（2026-09-02T07:09更新，#7結案後，內容已嚴重過時，僅存
歷史脈絡——實際最新狀態一律以本章節最後一條編號條目為準）**：15條原始佇列項目中
#1~4、#7、#9、#11~15共10條已結案（皆FAIL），#10已建置方法論框架（非
PASS/FAIL）。**剩餘#5/#6/#8三條全部卡在外部依賴**（#5待B24/B25、#6/#8
卡題材動能榜PIT引擎），**#10待有選股候選通過1~8關才能套用**——目前
沒有任何一條已過關的候選（全數FAIL）可供#10套用。這代表佇列目前**沒有
可直接開工的下一個項目**，但嚴格來說#5/#6/#8/#10並非「已結案
PASS/FAIL」，所以不完全符合協定第1節「佇列已空（全部PASS或FAIL）」
的字面條件——**留給下一輪判斷**：是否要解讀為實質等同已空（因為剩餘
項目都動不了）進而設計新假設軸，或者先確認B24/B25、題材動能榜PIT引擎
是否有進展可以解鎖#5/#6/#8其中之一。若下一輪判斷為實質已空，依協定
指引的方向是regime/擇時型——但#10（市場regime擇時overlay）已經是這個
方向且已建置完成，卡點是「沒有已過關候選可套用」而非「機制沒做」，
所以真正需要的新假設軸應該避開再度嘗試「純選股」類型（本佇列10條
選股類假設全滅，共同死因見`HYPOTHESIS_QUEUE_PROTOCOL.md`第58行分析：
表面報酬漂亮但alpha不顯著/beta曝險主導），優先考慮**與選股完全正交**
的維度（跟#15波動度目標化同一種精神，但#15本身也FAIL了，需要換一個
機制而非同一個vol-targeting換皮）。

**佇列已空判定（2026-09-02T07:09同輪追加，`HYPOTHESIS_QUEUE_PROTOCOL.md`
本輪執行）**：確認`BACKLOG.md`——B24-500已跑完但**不及格**（沒有已過關
候選）、B25/B26僅登錄規格**尚未執行**、題材動能榜PIT引擎**仍未建置**
（`BACKLOG.md`第1042/1119/1132行仍是`回測未通過`/`null`/`紙上交易中`
狀態，非「已解鎖」）——三個外部依賴均無新進展。判定**佇列實質已空**
（剩餘#5/#6/#8/#10全部動不了），依協定第1節設計新假設軸：**#16同產業
配對交易/統計套利**（見上方條目），機制是market-neutral均值回歸，跟
本佇列10條已FAIL的方向性排序假設、以及#10（regime overlay）、#15
（vol-targeting，兩者皆為「單一標的曝險timing」）都不同構造，避開了
「純選股排序」跟「已測過的timing類型」兩種已知死法。**下一輪從#16
第1關sanity開始**，其餘#5/#6/#8/#10仍登記在案、任一外部依賴解鎖時
應優先評估是否能接續，不因為新增#16就永久放棄它們。

**2026-09-02（使用者裁示追加，同日稍晚更新）**：~~#16（同產業配對交易/
統計套利）~~**已結案：FAIL**（見上方item 16與`STRATEGY_GRAVEYARD.md`/
`TRIALS_LEDGER.md`#83），移出排隊佇列。**#17（52週高點接近度，George
& Hwang錨定不足機制）現在排隊第一，尚未開始，下一輪從第1關sanity開始，
不得跳關**。#18（短期反轉1週，流動性溢酬機制）排隊第二。兩者都是全新
機制、跟已FAIL的方向性排序假設經濟理由不同類別，各自完整內容見上方
對應章節。**使用者原本也點名「產業內相對強度中性化」「betting-against-
beta低beta在地版」「台股月營收公布事件動能」三個方向，查證後這三個
分別就是已結案FAIL的#11/#12/#14，不重複登記——已跟使用者說明清楚，
不是漏做。**

**2026-09-02T22:27更新（第十七輪排程）**：#17第1關cheap IC gate
**CHEAP_PASS**（`f_52w_high_prox`，TRAIN/VAL同號、null percentile=
100.0，完整數字見上方#17條目與`TRIALS_LEDGER.md`#84），本佇列第二個
通過第1關的候選。**本輪未繼續往第2關以後推進**——執行途中發現
`CLAUDE.md`新增最高優先鐵律「提案先於執行（總司令核准制）」，跟這整個
無人值守自動化軌道的運作前提直接衝突，本輪判斷比照「三個停下條件」
精神處理：完整問題寫進`MARATHON_LOG.md`本輪心跳＋本條目，commit+push
後正常收工，不自行決定「協定本身視同已交辦」就逕自繼續。**下一輪（或
使用者回應後的下一輪）需要的裁示**：這條新鐵律是否適用於
`hypothesis_queue`／三軌馬拉松這類原本就設計成自主執行、只在三個明訂
條件下才停的無人值守排程軌道？若適用，這些軌道之後每次觸發是否應該
改成「只做完當前工作單位就停下寫提案，不再自動進到下一關/下一條假設」，
直到使用者核准為止？若不適用（例如新鐵律主要針對互動式session的
臨場決策），則#17可以在下一輪直接接續第2關隨機控制組。

**2026-09-03（使用者裁示追加）**：#20（純毛利率GP）FAIL後使用者要求
「實作正確性健檢」（公式/PIT對齊/涵蓋率/方向四點），健檢結果四點皆
正確、無bug，FAIL維持成立，完整過程見#20條目「實作正確性健檢」小節、
`STRATEGY_GRAVEYARD.md`對應追加段落。同時新增**#27多因子z-score複合
評分**假設（吸取#22硬AND合取過度擬合教訓，改用z-score加總+更嚴格的
抗過擬合控制：隨機對照≥300draws/正交性檢查/TRAIN期凍結權重），排隊
接續#26之後，完整內容見下方#27條目。

**B25/B26任務提醒（2026-09-02新增，跟上面九條假設是平行的另一個工作
項目，不是同一序列）**：`BACKLOG.md`已有完整規格「登記但尚未執行」——
B25（回測regime標記與分情境報告，套用在B24-500的value_board_v2結果上，
只做報告不做權重調整）、B26（B24報告補強：調整後Sharpe×0.5/×0.7+
CVaR(95%)）。這兩項工作對象是既有的B24-500報告，不是這份佇列的因子/
策略候選，跟Carry/#9~15不衝突、可以在Carry收尾後、佇列繼續往下跑#9之前
或之後任何空檔接續，去讀`BACKLOG.md`「B25」「B26」條目取得完整規格
（已經寫得很完整，不用重新設計）。**（後續更新：B25/B26皆已於
2026-09-02完成，見`BACKLOG.md`對應條目跟`research/B24_RESULTS.md`
「B25分情境績效報告」章節，這裡的提醒已解決，不是還沒做。）**

**2026-09-02T22:27條目的裁示問題已解決**：使用者已在CLAUDE.md「提案
先於執行」補上明確界線——這條規則不適用於已核准的自主挖礦馬拉松，
馬拉松照三大停下條件持續跑，死路寫墓園繼續、不必逐關停下問，只有
「全部關卡都過、準備部署」才停下提案。**#17後續已接續完成**：第2/7/8
關（`TRIALS_LEDGER.md`#85）+ 補齊的第3/5/6關（`TRIALS_LEDGER.md`#86）
——第3關參數高原PASS、第5關leave-one-out PASS，但**第6關逐年一致性
FAIL**（TRAIN期6年只有4年報酬為正，2015/2018為負，未達≥5/6門檻）+
第7關OOS alpha不顯著（VAL p=0.0831），依快殺標準綜合判**FAIL**。
**#18（短期反轉1週）也已結案：FAIL**（`TRIALS_LEDGER.md`#87，null
percentile=41.3遠低於90.0門檻）。**#1~18原始+新增佇列項目至此全數
結案**，馬拉松依協定判斷佇列實質已空，自主設計新假設軸**#19（跨市場
美股隔夜報酬外溢效應）**，已登記、尚未開始第1關（完整內容見上方#19
條目）。

**2026-09-03（使用者裁示新增5條假設，#20~#24）**：使用者原始提案編號
為#18~#22，**因為#18（短期反轉）跟#19（跨市場美股隔夜報酬外溢）在
使用者下指令當下已經被馬拉松自主佔用，這裡重新編號成#20~#24避免
衝突**（已跟使用者說明清楚這個編號調整，不是擅自更改內容）：
#20純毛利率因子(Gross Profitability)、#21月營收意外漂移×低關注度
（改造#14）、#22品質×營收加速×法人吸籌複合訊號+低波動閘門、#23
Piotroski F-score當價值榜排雷閘門、#24除權息季節行為效應。**排隊
順序：接續#19之後，依#20→#21→#22→#23→#24順序執行**，每條完整內容
見下方對應章節。使用者統一裁示這5條都要額外證明下檔保護（MDD/地雷率
/regime存活），已寫進各條目「下檔保護要求」小節，見上方GATE_SEQUENCE
第9關規定。三大停下條件（1000draws規模投入/survivorship-free宇宙
投入/不可逆或花錢操作）之外，只有「某條假設通過完整關卡準備部署」
才停下問總司令，其餘自主一條接一條跑完、跑完就換下一條。

**2026-09-03（第十九輪排程更新）**：#19第1關cheap gate**CHEAP_PASS**
（r=0.40~0.46兩期、p<0.0001、洗牌null percentile滿分100.0，本佇列至今
證據最強的候選，完整數字見上方#19條目與`TRIALS_LEDGER.md`#88）。**#19
尚未結案**——第2關以後（成本敏感度、portfolio層擇時規則構造、alpha
顯著性拆解）待下一輪接續，**佇列排隊順序仍是#19（未結案，接續第2關）
→#20→#21→#22→#23→#24**，不因為第1關CHEAP_PASS就跳過#20~24優先度或
提前判定#19最終PASS/FAIL。

**2026-09-03（第二十輪排程更新，#19已結案：FAIL）**：新增
`spillover_overlay_v1.py`——把#19已CHEAP_PASS的相關性轉成具體擇時規則
（`exposure=0.3 if 美股當日收黑 else 1.0`），走完GATE_SEQUENCE第2/3關皆
PASS，但**第6關逐年一致性FAIL**（TRAIN期11個年度僅4個正報酬，遠低於
>=5/6門檻，且TRAIN總報酬-22.10%大幅落後同期買進持有+79.42%），依協定
快殺結案，未進第4/7/8/9關。根因是THRESHOLD=0.0觸發頻率過高（近乎逐日
翻轉），把防禦型regime overlay變成高頻方向性賭注，被切換成本+踏空
多頭格局侵蝕。**不泛化成相關性沒用**——第1關CHEAP_PASS（#88）不受影響，
死的是這個具體擇時規則。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#89。**佇列#19結案，接續佇列第一順位#20（純毛利率
因子Gross Profitability）**。

**2026-09-03（第二十一輪排程更新，#20已結案：FAIL）**：`f_gross_
profitability`（GrossProfit/TotalAssets）第1關cheap IC gate未過——
null percentile=48.4（門檻90.0，遠未過且低於50），IC幅度兩期皆接近
雜訊，依協定判FAIL，未進第2關以後。完整見上方#20條目與
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#90。**佇列#20結案，接續
佇列第一順位#21（月營收「意外」漂移×低關注度，改造已陣亡的#14）**。

---

### 16. 同產業配對交易 / 統計套利（Pair Trading / Statistical Arbitrage）

**經濟理由**：這個專案目前15條已測項目（#1~15，其中10條已結案，全數FAIL）
清一色是**方向性排序**機制（不論是原始動量、剝離beta後的動量、產業內
相對強度、籌碼連續性、營收驚喜、低波動/低beta——全部是「把股票排序、
做多前段班」這個共同結構，差別只在排序依據），共同死因是`HYPOTHESIS_
QUEUE_PROTOCOL.md`第56行分析的「表面報酬漂亮但拆解後主要是beta曝險、
alpha不顯著」。配對交易/統計套利在經濟機制上**真正不同**：同產業內找
兩檔歷史上走勢同步（協整/高度相關）的股票，當兩者價差（spread）偏離
歷史常態時，賭的是**均值回歸**（價差會收斂）而非**方向延續**（單一
標的會繼續漲/跌），且策略天生**market-neutral**（同時做多做空一組，
理論上淨beta≈0）——直接對症「都是beta」這個共同病灶，不是同一個機制
換皮。`HYPOTHESIS_QUEUE_PROTOCOL.md`第113行「建議研究方向」第5點也
明列了這個方向。

**具體假設定義**：同產業分類（沿用`universe.py::industry_category`，
排除ETF/基金類，跟#11同一個分類來源）內，兩兩配對，用歷史窗口（例如
過去120交易日）計算價格比率或對數價差的z-score；當|z-score|超過進場
閾值（例如2.0）時，做多相對低估的一邊、做空相對高估的一邊等金額對沖；
價差回歸到出場閾值（例如0.5）附近或達到最長持有期限就平倉。先用簡單
相關係數/價差穩定度篩配對候選（門檻要夠嚴格，避免把「本來就不相關的
兩檔股票湊巧同向」誤判成配對），不強求一開始就做完整Johansen協整檢定
（若簡單版本有訊號再考慮升級檢定方法）。

**已知相關背景（誠實揭露）**：`HYPOTHESIS_QUEUE_PROTOCOL.md`第113行
明確提到Cybex的`coint_pairs`經驗——**測了17個on-window機制**、
Bonferroni校正後**常全軍覆沒**，這是配對交易類機制在Cybex（加密貨幣）
上已知容易被多重比較拆穿的前車之鑑，這次要嚴格套用本專案既有的隨機
控制組+多重比較校正框架，不能因為「概念上聽起來合理」就放鬆判準。跟
`#11產業內相對強度`（已FAIL）刻意做出區隔——#11是同產業內排序**動量
延續**（做多產業內強勢股、預期持續強），這條是同產業內配對**均值回歸**
（價差擴大後預期收斂），兩者經濟機制方向相反，不是同一個「產業內」
框架換皮測第二次。**執行摩擦誠實揭露（不是回測階段忽略、是要記錄在
案）**：台股放空受限——需要券源（可能無券可借）、平盤下不得放空部分
標的（`CLAUDE.md`「已知地雷」章節已記錄的雷）——這條假設在便宜的因子
層/機制存在性驗證階段可以先用「多空對稱」理論值測試訊號本身存不存在，
但若進到portfolio層（第4關成本敏感度以後），必須把放空可行性/借券成本
這個台股專屬摩擦計入，不能假設放空永遠做得到。

**狀態（2026-09-02T07:09新增，`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程
判定佇列實質已空後設計此新假設軸）**：**尚未開始**，這輪只登記假設、
未寫任何程式碼、未跑任何測試。下一輪從第1關sanity開始（先確認能篩出
合理數量的候選配對、價差z-score計算邏輯正確、非結構性no-op），比照
本佇列既有GATE_SEQUENCE，不跳關、不因為是新機制就放寬第一關的cheap
gate標準。

**狀態（2026-09-02接續排程，已結案：FAIL）**：新增`pair_trading_sanity.py`
（第1關）+`pair_trading_control_v1.py`（第2關）。**第1關sanity PASS**：
100檔快取樣本72檔可用，15個產業組，89條可配對、12條通過相關係數
（>=0.70）篩選，555次進場事件，方向性sanity median converged_frac=
0.855、mean|z|reduction=+0.820（方向正確）。**第2關隨機控制組（N=100
draws，「同樣動作、隨機挑12對」控制組，測相關係數篩選本身有沒有加值）：
真實(corr篩選12對)pooled converged_frac=0.8577/mean_abs_reduction=
+0.8356，vs null分布median=0.8555/+0.8516，percentile=56.0/39.0，皆遠
低於90.0門檻**（39.0甚至低於50）——相關係數篩選相對隨機挑配對沒有加值，
確認是`CONSTITUTION.md`「縮小候選池」偽影家族：rolling z-score本身的
統計定義就會讓任意同產業配對的log價差呈現類似的均值回歸表現，跟兩檔
股票是否真有協整關係無關。依協定快殺標準「已被控制組拆穿之偽影家族
換皮」判**FAIL**，未進第3關以後。**不泛化成「配對交易/統計套利這個
機制類別完全沒用」**——只測了簡單相關係數篩選+固定120日窗口/2.0進場
閾值這個具體實作，未測嚴格協整檢定(Johansen)、未測不同參數組合，也
未進到真正的多空P&L/放空摩擦驗證（連機制存在性都沒過，不需要走到那
一步）。**獨立交叉驗證**：另一條並行的agent用完全不同方法（`pair_trading_
backtest_v1.py`真實多空P&L回測+`pair_trading_gates.py`跑第2/3關）也
獨立判定同一具體實作FAIL——第2關（TRAIN期N=100）percentile=94.0過關，
但**第3關參數密集高原沒過**：登記門檻(entry=2.0,exit=0.5)本身TRAIN期
報酬為負(-1.91%)，ENTRY_Z×EXIT_Z網格12點只有2點(17%)報酬為正，遠低於
60%高原門檻，是孤立僥倖點不是穩健區域。兩種獨立方法（sanity層級收斂
統計 vs 完整多空P&L回測）殊途同歸，都是FAIL，強化這不是單一分析角度
的偶然結論。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#83。佇列
#16結案，接續佇列第一順位#17（52週高點接近度）。

**狀態（2026-09-02T21:28更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十六輪
排程，第1關sanity：PASS，非最終判定）**：新增`pair_trading_sanity.py`
（沿用#11同一個`universe.py::industry_category`分類來源+排除ETF/基金、
`factor_ic.py`同一個`sample_universe_ids(100,seed=20260822)`取樣，價格
用`adjust.py::adjusted_price_series`，已holdout-safe capped在VAL_END）。
100檔樣本中72檔可用（>=500交易日歷史），組成15個產業群組（median組內
4檔，最大7檔），共形成90組候選配對（89組有足夠重疊天數可算相關係數）。
**簡單相關係數篩選**（門檻0.70，篩掉「同產業但走勢不同步」的雜訊配對）：
全部可配對配對的log價格相關係數中位數僅0.273（顯示濾網確實有鑑別力，
不是形同虛設），12/89組通過門檻。**這12組配對的z-score機制檢查**：
120交易日滾動窗口，|z|>=2.0進場門檻，共555次進場事件（12組配對每組都
至少觸發過一次，非結構性0事件）；**方向性sanity（進場後20交易日|z|是否
朝均值收斂，不是反的）**：pair-level收斂比例中位數85.5%、平均|z|縮減
中位數+0.820（正值，確認收斂方向正確）。三項sanity檢查（候選配對數量
合理非0、相關係數濾網有鑑別力、z-score方向正確非反向）皆通過，**判第1
關sanity PASS**，機制非結構性no-op、非觀測層級無訊號。**這不是策略層
最終判定**——只確認地基/方向正確，尚未做隨機控制組（第2關，例如打亂
配對組合或打亂進場時點當null對照）、未計入台股放空摩擦、未做多重比較
校正。完整輸出見`data/pair_trading_sanity_results.csv`（gitignored，
逐配對明細）。下一輪從第2關隨機控制組開始（比照本佇列既有配對式/排列式
隨機對照精神，N>=100 draws，需先設計「配對交易專屬」的null——例如同
產業內隨機配對而非精心篩選的高相關配對，或打亂進場時點但保留配對本身）。

**修正說明（2026-09-02本輪`HYPOTHESIS_QUEUE_PROTOCOL.md`排程發現並修正，
不是新判定）**：上面這則T21:28的紀錄跟前一則「已結案：FAIL」互相矛盾——
本輪查證`TRIALS_LEDGER.md`#83與`STRATEGY_GRAVEYARD.md`，兩份權威帳本都
明確記載#16在第2關（隨機控制組N=100，percentile=56.0/39.0）已判**FAIL**
並正式結案，「排隊順序總結」章節也已同步標記#16為刪除線+FAIL、#17為
排隊第一。T21:28這則是某一輪誤重跑`pair_trading_sanity.py`後補寫的
狀態更新，沒有先確認佇列已經結案，數字（72/100可用、15個產業組、12組
通過相關係數篩選、555次進場、收斂比例85.5%/縮減0.820）跟結案時第1關
sanity的數字完全一致，純屬重複執行、沒有推翻原判定。**結論：#16維持
FAIL已結案，不重啟、不再跑第2關**，T21:28那則紀錄保留在此處僅供追溯
「這輪誤重工」的事實，不代表佇列狀態變動。

---

### 17. 52週高點接近度（George & Hwang 2004，錨定不足）

**經濟理由**：George & Hwang經典異常——股價接近其52週高點時，投資人
對「創新高」這個顯著錨點反應不足（anchoring/underreaction），導致
價格未能立即反映應有的正面資訊，股價越接近52週高點者後續報酬顯著
較高，且文獻上發現這個訊號的解釋力比傳統動量更強、更不容易被動量
因子解釋掉。**跟本佇列已FAIL的10條方向性排序假設有本質差異**：那些
（原始動量、剝離beta動量、產業內RS、營收驚喜事件、籌碼連續性等）全部
是「近期報酬/資訊流」驅動的排序，這條是「價格相對於一個顯著心理錨點
的距離」驅動，訊息來源完全不同（不是報酬本身、不是財報事件、不是籌碼
流向，是價格水位相對歷史極值的位置），值得獨立驗證而不是同一機制換皮。

**具體假設定義**：計算每檔股票「當前收盤價 / 過去252個交易日最高價」
的比率（越接近1代表越接近52週高點），排序做多比率最高分位。

**已知相關背景**：跟`f_rel_strength`（此佇列多條已FAIL假設共用的基礎
因子，衡量近期報酬相對大盤）不同——52週高點比率是「價格水位」不是
「報酬率」，兩者在同一檔股票上可能給出不同排序（例如一檔股票近期
報酬普通但因為前期大漲，現在價格仍貼近52週高點）。這是本佇列第一次
測試「錨定」機制。

**狀態（2026-09-02T22:27更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十七輪
排程，第1關cheap IC gate：CHEAP_PASS）**：新增`factors.py::prepare_factors()`
「(v) 52週高點接近度」段落（`f_52w_high_prox`：當前收盤價/過去252個交易日
滾動最高價，比率越接近1排名越靠前）+`factor_ic_52w_high.py`（新增，沿用
`factor_ic.py`既有cross-sectional IC框架）。結果：TRAIN mean_ic=+0.0760
IR=+0.389(n=74)、VAL mean_ic=+0.0863 IR=+0.465 hit_rate=0.68(n=47)、
train/val同號、null percentile=100.0（門檻90.0，過關）。**這只是因子層
第1關，不是最終PASS**——三項判準（幅度非零/同號/贏過洗牌null）皆過，
且IR跟null percentile表現優於#4股利率因子（同樣CHEAP_PASS，percentile
也是100.0但IR較低），是本佇列第二個通過第1關的候選。**下一步（第2關
以後）本輪未執行**：本輪執行途中發現`C:\alpha\alpha-app\CLAUDE.md`新增
了最高優先鐵律「提案先於執行（總司令核准制，2026-09-02使用者裁示）」，
要求任何新的更動/優化/新建議一律先提案給使用者、核准才執行，例外只有
「純bug修復」跟「已明確交辦的任務」。**這條新規則的字面範圍跟這整個
無人值守佇列自動化的運作前提（設計上就是無人在場、不能停下來等核准，
只有三個明訂條件才停）直接衝突**，本輪判斷屬於協定精神上等同「停下
條件」的情況，不自行判斷「這個佇列協定本身應該算已交辦所以不受新規則
約束」就逕自往下跑第2關以後，完整問題已寫進`MARATHON_LOG.md`本輪心跳，
等使用者裁示這條新鐵律如何套用在`hypothesis_queue`/三軌馬拉松這類無人
值守自動化軌道上，再決定下一輪要不要接續走第2關。

**狀態（2026-09-02接續排程，第2/7/8關已跑完，已結案：FAIL）**：`CLAUDE.md`
已於本輪前補上「適用範圍界線（第二次裁示）」，明確確認`hypothesis_queue`
不受「提案先於執行」約束，本輪接續走第2關以後。新增`f52w_high_portfolio_v1.py`
（逐字比照`dividend_yield_portfolio_v1.py`架構+checkpoint可續跑機制，
單因子`f_52w_high_prox`、Top20、月頻21日換股）。TRAIN+VALIDATION隨機
控制組N=100全跑完（本輪內用checkpoint機制連續呼叫5次腳本累積進度，
最後一次中途因外層timeout被中斷導致log為空但checkpoint已落盤未遺失，
下一次呼叫確認接續無誤）。結果：TRAIN報酬+89.81%（買進持有+58.86%）、
alpha+10.84%(p=0.3155)、隨機控制組percentile=100.0；VAL報酬+69.30%
（買進持有+54.58%）、alpha+10.47%(p=0.0831)、隨機控制組percentile=100.0，
beta兩期偏低(+0.436/+0.353)、成本1x/2x/3x兩期皆正、MDD受控。腳本內建
判準印出表面第7/8關PASS，但套用本專案alpha顯著性+beta拆解既定標準
（PEAD/股利率/Weinstein同一把尺）後，兩期alpha皆未跨過p<0.05門檻（VAL
p=0.0831是本佇列目前所有FAIL案例中最接近顯著的一次），人工override判
**FAIL**。不泛化成「52週高點接近度因子沒用」——因子層IC（#84）不受
影響，死的只是「等權/月頻/Top20」這個具體portfolio構造。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#85、`MARATHON_LOG.md`本輪
心跳條目。佇列#17結案，接續佇列第一順位#18短期反轉（1週）。

---

### 18. 短期反轉（1週Reversal，流動性溢酬）

**經濟理由**：短期反轉異常（Jegadeesh 1990等）——股票在極短窗口
（1週左右）的報酬存在顯著反轉，經濟解釋是流動性提供者（market
maker/流動性交易者）承接短期價格壓力後要求的溢酬：短期內被過度
賣壓的股票，流動性提供者買入承接後很快推回真實價值附近，產生反轉；
這是流動性溢酬機制，不是資訊面機制，跟本佇列已測過的所有假設（動量、
營收驚喜、籌碼、beta類）經濟機制完全不同類別。

**具體假設定義**：計算每檔股票過去5個交易日（1週）的累積報酬，排序
做多**過去1週報酬最差**的分位（反轉：跌越多、預期近期反彈越大）。

**已知相關背景**：跟`#15波動度目標化`一樣是本佇列少數非「方向性報酬
延續」類的假設，但機制不同（#15是曝險timing、這條是個股層級的短期
價格壓力反轉）。**特別注意**：短期反轉訊號在文獻上高度依賴交易成本
假設（因為需要極高換手率），第4關成本敏感度（1x/2x/3x）對這條假設
格外關鍵，便宜關卡過關也絕對不能跳過完整成本敏感度就下結論——這是
這條假設在深挖階段最需要嚴格把關的地方。

**狀態（2026-09-02更新，接續佇列排隊第一）**：#17（52週高點接近度）
已結案FAIL（見上方#17條目與`STRATEGY_GRAVEYARD.md`），#18現在排隊
第一，第1關（cheap IC gate）尚未開始。

**狀態（2026-09-02T23:59更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十八輪
排程，第1關cheap IC gate：已結案，FAIL）**：新增
`factors.py::prepare_factors()`「(w) 短期反轉（1週）」段落
（`f_short_term_reversal_1w`：-(當前收盤價/5交易日前收盤價-1)）+
`factor_ic_short_term_reversal_1w.py`（新增，沿用`factor_ic.py`既有
cross-sectional IC框架，standalone bonferroni_n=1）。結果：TRAIN
mean_ic=+0.0219 IR=+0.129(n=74)、VAL mean_ic=+0.0097 IR=+0.064
hit_rate=0.45(n=47)，train/val同號（皆正），但**null percentile=41.3
（門檻90.0，遠未過且低於50）**，VAL期IC幅度過小接近雜訊。三項判準
（幅度非零/同號/贏過洗牌null）中兩項未過，依協定第1關cheap gate標準
判**FAIL**，未進第2關以後。**跟已FAIL的`f_short_reversal_1m`（#46，
21交易日/~1個月窗口，percentile=23.1）刻意做出區隔**——那筆FAIL紀錄
原文建議「若改用更短窗口（1週）可再測」，本輪就是遵照建議測試5日窗口，
percentile從23.1微幅升至41.3，方向略有改善但幅度不足以逆轉結論。
**不泛化成「短期反轉在台股完全無效」**——只測過100檔快取樣本+單一5日
窗口，未測更大樣本/日頻分層版本，但目前證據不支持升格，也不建議再嘗試
相鄰窗口長度變體（1個月跟1週兩端點皆偏弱，暗示問題可能在樣本規模而非
窗口長度）。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#87、
`MARATHON_LOG.md`本輪心跳條目。佇列#18結案，佇列#1~18原始排隊項目全部
結案，本輪新增#19（見下方章節）接續。

---

### 19. 跨市場美股隔夜報酬外溢效應（Cross-Market Overnight Spillover）

**經濟理由**：這是佇列第19條，也是第一條**指數層級（index-level）、不做
任何個股選擇**的方向性擇時假設——跟已測過的18條方向性排序假設（動量、
營收/財報意外、籌碼、beta類、產業內RS、52週高點等）經濟機制完全不同
類別，也跟#15（vol-targeting，用自身歷史波動度timing）、#16（配對交易，
market-neutral均值回歸）、#10（regime overlay，用大盤自身200日均線/波動度
當開關）三種已測過的「非選股」機制都不同——這條用的是**外部市場（美股）
的隔夜報酬**當台股當日曝險的擇時訊號，是資訊外溢（information spillover）
/領先-落後（lead-lag）機制，不是任何形式的自身歷史統計量。台灣是出口導向、
高度依賴半導體供應鏈的經濟體，跟美股（尤其那斯達克/費城半導體指數）
連動性眾所皆知（台股開盤常被觀察到跟隨美股前一晚收盤漲跌反應）；美股
收盤時間（美東下午4點，約台灣時間隔日清晨4-5點）早於台股開盤（台灣時間
上午9點），這個時間差讓美股隔夜報酬對台股當日開盤具有**結構性的資訊
領先**（台股開盤前，美股已經反映了這段時間發生的全球性消息），不是巧合
相關，是有明確時序因果方向的可驗證假設。

**具體假設定義**：用S&P 500（`^GSPC`）或那斯達克綜合指數（`^IXIC`）
的美股當日收盤對前一美股交易日收盤的報酬（這個報酬發生在台股開盤之前，
天然point-in-time，無需額外延遲假設），當作台股加權指數（TAIEX，`^TWII`）
**次一個台股交易日**開盤到收盤（或報酬全日）的預測訊號/曝險擇時依據
——單純測試「美股隔夜報酬正時，台股次日報酬是否顯著偏正（且反之亦然）」
這個cross-sectional/時序相關性本身（第1關cheap gate：相關係數/簡單迴歸
IC，不必一開始就設計完整的交易規則），若訊號存在，第2關以後再考慮具體
擇時規則（例如美股大跌超過X%時降低台股曝險）。

**已知相關背景**：查證`TRIALS_LEDGER.md`/`STRATEGY_GRAVEYARD.md`/
`HYPOTHESIS_QUEUE.md`全文（`spillover`/`外溢`/`隔夜.*美股`/`跨市場`/
`SPX`等關鍵字），**這個專案至今沒有測過任何跨市場（美股→台股）的時序
外溢假設**——已測過的期貨軌相關假設（`fut_intraday_gap_reversal`／
`fut_night_gap_reversal`／`fut_day_gap_reversal`，皆FAIL）測的是台指期
**自身**日盤/夜盤之間的跳空，不是美股對台股的外部訊號，經濟機制不同
（自身市場微結構跳空 vs 跨市場資訊傳導）。**資料可行性已確認**：
`yf_price_client.py::fetch_yf_index()`是既有的、通用的指數抓取函式
（目前預設抓`^TWII`給`strategies/weinstein_stage2.py::prepare_market_data()`
用），同一個函式可直接傳入`ticker="^GSPC"`取得S&P 500歷史資料，本身已經
holdout-safe（截斷在`VAL_END`），零新增API整合成本、零新的資料源風險，
不是「查證後發現拿不到資料」的情形。

**狀態（2026-09-02T23:59新增，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十八輪
排程判定佇列（#1~18）實質已空後設計此新假設軸）**：**尚未開始**，這輪
只登記假設、未寫任何程式碼、未跑任何測試。下一輪從第1關sanity/cheap
gate開始（先確認`fetch_yf_index(ticker="^GSPC")`真的能拿到合理的歷史
資料、美股與台股交易日曆對齊邏輯正確——例如台股國定假日與美股不同步，
需要正確處理「上一個有交易的美股收盤」對應「下一個有交易的台股開盤」
這組配對，不能假設兩邊行事曆完全一致），比照本佇列既有GATE_SEQUENCE，
不跳關、不因為是新機制就放寬第一關的cheap gate標準。**其餘#5/#6/#8/#10
仍登記在案**，任一外部依賴解鎖時應優先評估是否能接續，不因為新增#19
就永久放棄它們。

**狀態（2026-09-03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第十九輪排程，
第1關cheap gate：CHEAP_PASS，本佇列證據最強的候選）**：新增
`spillover_overnight_gate.py`——用`fetch_yf_index()`分別取`^GSPC`/
`^TWII`日線，對每個台股交易日t，配對「日曆日期嚴格早於t的最近一個美股
交易日」的隔夜報酬（`us_ret[d]=close[d]/close[d-1]-1`）當訊號，目標變數
是台股t日close-to-close報酬，測時序（非cross-sectional）Pearson/Spearman
相關 + 洗牌null(N=500,打散美股訊號序列)。**時序對齊sanity**：3662組配對，
美股訊號日到台股交易日日曆天數差min=1/max=5/median=1.0（確認訊號嚴格
早於目標，無未來函數）。結果：TRAIN(<=2020-12-31,n=2693) Pearson
r=+0.3987(p<0.0001)、Spearman ρ=+0.3778(p<0.0001)、洗牌null percentile=
100.0；VAL(2021-01-01~2024-12-31,n=969) Pearson r=+0.4550(p<0.0001)、
Spearman ρ=+0.4616(p<0.0001)、洗牌null percentile=100.0。三項判準（幅度
非零/train-val同號/贏過洗牌null）全過，**相關係數量級(r=0.40~0.46)是本
佇列至今第1關證據最強的候選**（p值遠低於0.0001，兩期方向一致且percentile
滿分）。**這只是第1關（相關性存在性驗證），不是最終PASS**——下一步是把
這個訊號轉成具體的台股當日曝險擇時規則（例如美股大跌超過某個門檻時降低
台股曝險），比照`regime_overlay.py`（#10）已建置的overlay框架整合，走
完整GATE_SEQUENCE第2關以後（含成本敏感度、leave-one-out、逐年一致性、
alpha顯著性拆解——經濟理由再強，最終判準仍是`portfolio_multifactor_v2`
一路以來的alpha顯著性+beta拆解標準，不能因為第1關相關係數漂亮就放寬
後續關卡）。完整見`TRIALS_LEDGER.md`#88、`MARATHON_LOG.md`本輪心跳條目、
`data/spillover_overnight_aligned.csv`（新增，gitignored）。

---

### 20. 純毛利率因子（Gross Profitability，Novy-Marx品質維度，2026-09-03使用者裁示新增）

**經濟理由**：Novy-Marx (2013)「The Other Side of Value: The Gross
Profitability Premium」——GP = (營收−銷貨成本) / 總資產，橫截面排序
做多高GP股票，跨19個成熟市場+新興市場（年化約5.1%）+亞太皆穩健。經濟
機制是「難套利、資訊不確定性高→行為性低估持續」：高毛利率相對總資產
的公司代表核心業務真正的獲利能力強（不是財務槓桿/業外損益堆出來的
帳面數字），但市場對這個訊號的定價效率不足，超額報酬被認為是行為性
（低估持續），不是承擔額外系統性風險（beta）的補償。

**具體假設定義**：`GP = (營業收入淨額 − 銷貨成本) / 總資產`（分子=毛利，
分母=資產負債表總資產，不是股東權益也不是市值），橫截面排序做多GP
最高分位。資料源：FinMind免費層`TaiwanStockFinancialStatements`（損益
表，取營收/銷貨成本）+`TaiwanStockBalanceSheet`（資產負債表，取總資產）
——第1關sanity第一步要先確認這兩個資料集的欄位命名+財報公布時間點
（PIT安全，用公布日不是財報期別日），不能假設欄位名跟其他既有品質
因子腳本完全一致，需要重新查證。

**已知相關背景（誠實揭露，避免誤判成重複）**：本專案已測過`f_gross_
margin_stability`（`TRIALS_LEDGER.md`#67，Novy-Marx精神的品質異常
「變體」，衡量近8季毛利率的**滾動標準差**（穩定度/波動度），train/val
同號但null percentile=70.7未過90.0門檻，判FAIL）——**這條GP因子跟
#67是不同構造，不是重複**：#67測的是毛利率隨時間的**穩定性**（越穩定
越好），這條測的是毛利率相對總資產的**水位高低**（越高越好），是
Novy-Marx原始論文真正的訊號定義，本專案至今沒有直接測過這個版本。
另外查證過`f_quality_roe_stability`（ROE穩定度，另一個品質變體）跟
`f_accruals`（應計項目，#10，FAIL）也都不是同一個構造。

**下檔保護要求（本輪使用者統一裁示，適用以下全部5條新假設）**：不能
只贏買進持有就算過關，必須額外證明：MDD受控（相對大盤/相對隨機對照
組）、地雷率（重挫機率）顯著低於隨機、regime危機情境（大盤空頭/高
波動期間）有降曝險或至少不放大虧損。

**狀態（2026-09-03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第二十一輪排程，
已結案：FAIL）**：新增`factors.py::_gross_profitability()`（GrossProfit
[`quarterly_pit`損益表]/TotalAssets[`balance_sheet_pit`資產負債表]，
兩者用同一組+45天延遲假設合併，跟`_roe_stability`同一個merge模式）+
`prepare_factors()`「(x) 純毛利率因子」段落+`factor_ic_gross_profitability.py`
（新增，沿用`factor_ic.py`既有cross-sectional IC框架，standalone
bonferroni_n=1）。結果（100檔快取樣本，80檔可用，121個20交易日快照）：
TRAIN mean_ic=+0.0030 IR=+0.024(n=74)、VAL mean_ic=+0.0114 IR=+0.089
hit_rate=0.62(n=47)，train/val同號（皆正），但**null percentile=48.4
（門檻90.0，遠未過且低於50）**——IC幅度兩期皆接近雜訊，代表打散對照組
半數以上表現優於真實排序。三項判準（幅度非零/同號/贏過洗牌null）中
兩項未過，依協定第1關cheap gate標準判**FAIL**，未進第2關以後。**不
泛化成「毛利率相關的品質異常在台股完全無效」**——這次只測了100檔快取
樣本+單一GrossProfit/TotalAssets定義（Novy-Marx原始論文的「水位」
版本），未測更大樣本、未測是否受成長股稀釋。跟已FAIL的
`f_gross_margin_stability`（#67，測毛利率「穩定性」，percentile=70.7）
死法不同但同屬毛利率相關訊號在此樣本規模下測不出穩健訊號。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#90。佇列#20結案，接續佇列
第一順位#21（月營收「意外」漂移×低關注度）。

**實作正確性健檢（2026-09-03使用者裁示追加，「GP是跨19國最穩健品質
因子之一，死在mean_ic≈noise跟強證據矛盾，疑似實作/資料問題」）——
四點逐一查證，結論：實作無bug，FAIL成立，正式接受留墓園**：
1. **公式/科目對應**：直接查FinMind`TaiwanStockFinancialStatements`
   原始資料（2330近8季），數值上驗證`GrossProfit`欄位**精確等於**
   `Revenue − CostOfGoodsSold`（8季全部diff=0.0，非近似值）——FinMind
   本身就提供算好的GrossProfit，不是自己組欄位算錯。`TotalAssets`
   （`TaiwanStockBalanceSheet`）數值量級核對2330近幾季約5.5~6.7兆
   台幣，跟公開財報認知的台積電總資產規模一致，不是誤取到`_per`
   （佔比）版本或其他科目。**公式/科目對應正確**。
2. **PIT對齊**：`quarterly_pit()`（損益表GrossProfit）跟
   `balance_sheet_pit()`（資產負債表TotalAssets）用**同一組**
   `fiscal_period_end`+45天延遲假設（`pit.py`共用邏輯，非#20獨有），
   `_asof_join()`用`pd.merge_asof(...,direction="backward")`對
   `pit_date`做因果合併（本專案數十個已測因子共用的同一套機制，多個
   通過cheap gate的因子如#84/#74都靠這套機制證明可用，不是#20專屬、
   未經驗證的新路徑）。**沒有用到未來資料，也沒有系統性多lag一季的
   證據**（+45天是既有全域假設，非本次新增）。**PIT對齊正確**。
3. **涵蓋率**：實測100檔快取樣本裡，77檔在合併GrossProfit+TotalAssets
   後有至少一筆有效值（跟其他因子的「80/100可用」基準同量級，不是
   崩塌）；更關鍵的**逐次橫斷面樣本數**（真正決定IC雜訊程度的數字）：
   184個快照裡144個N≥10被納入計算，N的中位數=56（p25=47/p75=59），
   跟同一批樣本上已CHEAP_PASS的`f_52w_high_prox`中位數N=60幾乎同量級
   ——**不是「大量NaN被剔除稀釋成noise」，樣本規模本身沒問題，兩個
   因子在同一套資料/樣本下，一個測得出訊號、一個測不出，差異不是
   來自涵蓋率**。
4. **方向**：TRAIN跟VAL兩期`mean_ic`皆為**正值**（+0.0030/+0.0114），
   代表「GP越高、後續報酬確實傾向越高」，方向跟「高GP做多」的假設
   完全一致，**沒有接反**（接反的話應該會看到穩定為負的IC，不會是
   兩期都恰好為正但很小）。
5. **結論**：四點皆查證正確，沒有發現任何實作或資料bug。IC幅度
   （IR僅0.024/0.089，null percentile=48.4甚至低於50）就是真實測到的
   結果，不是被某個技術缺陷污染出來的假noise。**正式接受FAIL、不
   重跑，維持墓園判定**——GP在文獻上的穩健性是基於已開發市場+新興
   市場的大樣本長期驗證，這裡受限於100檔小樣本+台股單一市場，測不出
   訊號並不跟文獻矛盾，只代表這個樣本規模下的統計檢定力不足以偵測到
   （若真的存在）較弱的訊號，這點已在原始FAIL記錄裡誠實揭露
   （「不泛化成完全無效」），這次健檢沒有推翻這個既有的誠實揭露，
   只是額外確認「不是因為程式碼寫錯才測不出來」。

---

### 21. 月營收「意外」漂移 × 低關注度（改造已陣亡的#14，2026-09-03使用者裁示新增）

**經濟理由**：`#14`（台股月營收公布事件效應，純YoY意外）已結案FAIL
（`TRIALS_LEDGER.md`#80：VAL期贏過洗牌null分布未過，percentile=68.0，
樣本外萎縮73%）。這條不是同一個機制換皮重測，而是**改造訊號定義+限縮
子集**：①意外基準從「去年同月YoY」改成「相對自身trailing 12個月趨勢
的殘差」（更貼近文獻上PEAD類研究常用的「季節調整後意外」，排除單純
基期效應）；②只在**低關注度**（成交量/法人持股/分析師覆蓋率低的中小
型股）且**公布後價量已確認反應**（排除公布當下無人注意、之後才慢慢
擴散的雜訊）的子集做多。經濟機制：台股散戶主導、資訊擴散速度慢，
市場對低關注股的營收意外反應不足（underreaction），漂移空間來自這個
資訊摩擦；大型權值股法人覆蓋密集、套利效率高，訊號會被迅速吃掉（這正
是原始`#14`用全樣本測、訊號被大型股稀釋而死的可能原因之一）。

**具體假設定義**：意外`= (實際營收 − trailing 12個月趨勢外推值) /
trailing 12個月趨勢外推值`（trend用簡單線性迴歸或移動平均皆可，第1關
sanity階段先選最簡單的線性外推，不用一開始就上複雜模型）。樣本切成
「高關注度」與「低關注度」兩組（關注度代理變數：近20日均成交值分位、
或法人持股比例分位，擇一在sanity階段先定，不要兩個都測造成事後多重
比較），**分開跑cheap IC gate，若假設成立應該只有低關注度組顯著、
高關注度組不顯著或顯著較弱**——這個「分組差異」本身就是最直接的驗證
證據，不是額外加分項。

**已知相關背景**：跟`#14`共用同一個PIT事件基礎設施
（`pit.py::month_revenue_pit()`），但訊號定義（trend殘差 vs 原始YoY）
跟樣本範圍（限低關注度子集 vs 全樣本）都不同，不算同一個假設重跑。
若第1關cheap gate兩組都不顯著或都顯著（沒有分組差異），視同「改造
沒有解決#14的根本問題」，依快殺標準判FAIL，不需要勉強找理由續命。

**下檔保護要求**：同上（見#20條目），適用本輪全部5條新假設。

**狀態（2026-09-03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第二十二輪排程，
已結案：FAIL）**：新增`revenue_trend_surprise_low_attention.py`——意外
定義改用trailing 12個月線性迴歸外推值的殘差（`_revenue_trend_surprise()`，
沿用`pit.py::month_revenue_pit()`同一套PIT邏輯）+近20個交易日均成交值
（volume*close，`adjusted_price_series()`衍生，注意yfinance路徑欄位名
`volume`、FinMind回退路徑欄位名`Trading_Volume`，兩種都要接受否則會漏篩
一半樣本，已修正）中位數切成低/高關注度兩組分開跑cheap gate。結果（100檔
快取樣本，62檔有可用事件，總事件數8958筆，median_dollar_volume_20d=
4,177,417）：**低關注度組**（n=4479）TRAIN IC=+0.0071(p=0.6863)、VAL
IC=+0.0117(p=0.6850)，同號但幅度接近雜訊，null percentile=**31.2**
（門檻90.0，遠未過）→FAIL；**高關注度組**（n=4479）TRAIN IC=+0.0097
(p=0.6007)、VAL IC=-0.0416(p=0.1017)，**train/val正負號相反**，null
percentile=89.8（門檻90.0，差0.2個百分點未過）→FAIL。**兩組皆FAIL、
沒有分組差異**，依`HYPOTHESIS_QUEUE.md`#21原話「兩組都不顯著視同改造
沒有解決#14根本問題」判**FAIL**，未進第2關以後。**意外之處（誠實記錄）**：
方向與假設預期相反——低關注度組證據明顯比高關注度組更弱，跟「市場對
低關注股反應不足」的經濟機制敘事矛盾，可能原因見`STRATEGY_GRAVEYARD.md`
對應條目完整分析。**不泛化成「月營收驚喜×關注度分組這個機制方向完全
沒用」**——只測了「線性外推trend殘差+成交值中位數分組」這一種具體組合，
未測法人持股比例當關注度代理（原本列的另一個候選）、未測moving
average trend、未測非對稱分組。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#91。佇列#21結案，接續佇列第一順位#22（品質×營收
加速×法人吸籌複合訊號+低波動閘門）。

---

### 22. 品質×營收加速×法人吸籌複合訊號 + 低波動閘門（對症「單因子必死」，2026-09-03使用者裁示新增）

**經濟理由**：本佇列（含TW軌整體）目前墓園裡的因子全部是**單獨測試**
死掉的（品質、營收動能、籌碼連續性、低波動各自單測皆FAIL或表現邊緣）。
假設：edge存在於**合取**（conjunction）而非任一單一維度——每個濾網
各自砍掉一種失敗模式（品質濾網砍財報造假/體質差公司、營收加速濾網砍
成長趨緩公司、法人吸籌濾網砍籌碼真空股、低波動濾網砍高波動地雷股），
單獨測任一濾網時，其餘失敗模式的雜訊蓋過該濾網本身的訊號，合起來才會
顯現。使用者原話提到「實戰平台公開重驗後存活5檔、Sharpe 1.31–1.67，
全是複合」——**這是外部參考證據不是本專案自己的驗證結果，不能直接
當成本專案的PASS依據，只能當成假設值得測的動機，仍要走完整
GATE_SEQUENCE獨立驗證**。

**具體假設定義**：四個濾網的合取（AND，不是加權平均分數）：①品質
（ROE/FCF正且達某分位門檻，具體門檻第1關sanity階段訂）②月營收加速
（YoY年增率本身還在上升，即YoY的二階導數為正，不是單純YoY為正）
③三大法人連買（近N日三大法人合計淨買超，方向為正，N值第1關sanity
訂）④低波動（近60日年化波動度低於分位門檻）。四個條件同時成立才
入選候選池，候選池內等權重或依某個既有排序次序選前N檔。

**驗證改造（使用者原話明講的關鍵驗證設計，務必照做，不能省略）**：
**用leave-one-out檢查每個濾網的邊際貢獻**——分別測試「拿掉品質濾網」
「拿掉營收加速濾網」「拿掉法人吸籌濾網」「拿掉低波動濾網」四個三濾網
版本，跟四濾網完整版比較。**若拿掉任一濾網績效顯著崩潰（不是持平或
微幅下降），才能證明是合取機制而非偶然湊出來的偽影**；若拿掉某個
濾網績效不變甚至更好，代表那個濾網是雜訊/多餘的，要誠實拆穿不能護航。
這個leave-one-out跟GATE_SEQUENCE第5關（拿掉最大貢獻年份）是兩件不同
的事，這條假設兩者都要做。

**已知相關背景**：四個組成濾網對應的既有測試——品質類（`f_quality_
roe_stability`等ROE/FCF相關因子）、營收動能（`#14`已FAIL，但這裡用的
是「加速度」不是原始YoY，構造不同）、法人吸籌（`f_inst_streak_days`，
`#13`已FAIL）、低波動（`f_low_vol`因子層`#9`PASS但十分位多空策略層
`#7`已FAIL）——**單獨每一個都FAIL或表現邊緣，這正是這條假設要測試的
前提本身**，不是矛盾。

**下檔保護要求**：同上（見#20條目），適用本輪全部5條新假設。

**狀態（2026-09-03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第二十三輪排程，
已結案：FAIL）**：`composite_quality_revaccel_inst_lowvol_sanity.py`（新增）
第1關sanity——四gate個別通過率合理（56.8%/49.6%/13.0%/49.2%），但四者
合取候選池僅14.0%快照有候選（門檻30.0%，未過），觀察值≈四通過率連乘積
（近似統計獨立、無協同），推翻假設核心前提，判**FAIL**，未進第2關。完整
見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#92。佇列#22結案，接續佇列
第一順位#23（Piotroski F-score價值榜排雷閘門）。

---

### 23. Piotroski F-score當價值榜排雷閘門（救回被價值陷阱拖死的價值榜，2026-09-03使用者裁示新增）

**經濟理由**：Piotroski (2000) F-score（9項二元基本面品質指標加總，
0-9分，涵蓋獲利能力/財務槓桿與流動性/營運效率三大類）國際證據穩健，
核心用途正是**篩掉「便宜但體質正在惡化」的價值陷阱（value trap）**。
`B24-500`正式回測（`research/B24_RESULTS.md`）目前判定「不及格」，
alpha兩期皆不顯著（TRAIN p=0.2672、VALIDATION p=0.1441）——這條假設
的診斷猜想是：價值榜排序邏輯本身可能選到不少「便宜是因為基本面正在
惡化」的陷阱股，稀釋了真正被低估、體質健康股票的alpha。**F-score不是
獨立當一個新的排序因子使用**，是當價值榜的**閘門（gate）**：只留
F-score≥7（門檻依文獻慣例，第1關sanity可先測≥7/≥8兩種）的便宜股，
被F-score判定體質惡化的便宜股直接踢出候選池，不參與排序。

**具體假設定義**：沿用`value_board_v2`既有排序邏輯與候選池，新增
F-score計算（9項指標：ROA為正、營運現金流為正、ROA年增、營運現金流>
淨利、長期負債年減、流動比率年增、當年度未發行新股稀釋、毛利率年增、
資產週轉率年增——逐項查證FinMind免費層對應欄位是否齊全，缺哪幾項
第1關sanity要誠實記錄，不能為了湊9項硬套不精確的替代欄位），對候選池
套用`F-score≥門檻`過濾後再進原本排序流程。

**驗證改造（使用者原話明講的關鍵比較，務必照做）**：**比較「原始
value_board_v2」vs「value_board_v2+F-score gate」兩個版本的alpha
與地雷率**——若加上F-score gate後alpha從不顯著轉為顯著、且地雷率
（重挫機率）下降，證明原始價值榜確實死於價值陷阱、F-score gate有
效解決這個問題；若加了gate後數字沒有實質改善，代表價值榜的問題不是
陷阱股，是別的原因（例如訊號本身就弱、或beta曝險問題），要誠實記錄
不能勉強護航F-score gate的效果。

**已知相關背景**：`B24-500`（`value_board_v2`）是App正式選股引擎的
組合策略驗證，記錄方式跟本佇列因子/策略層假設略有不同（見
`research/B24_RESULTS.md`），這條假設的驗證仍完整比照本佇列
GATE_SEQUENCE走（不是另外自訂一套判準），只是比較基準（baseline）
是既有的`B24-500`原始版本，不是買進持有。

**下檔保護要求**：同上（見#20條目），適用本輪全部5條新假設。

**狀態（2026-09-03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第二十四輪排程，
地基完成+第1關sanity：SANITY_PASS，非最終PASS/FAIL判定）**：新增
`piotroski_fscore_sanity.py`——先查證FinMind免費層9項F-score指標欄位
（`TaiwanStockFinancialStatements`/`TaiwanStockBalanceSheet`/
`TaiwanStockCashFlowsStatement`）：7項有直接對應欄位，2項需文件化proxy
（②CFO正沿用既有`pit.py::cash_flow_pit()`簡化——CFO近似FCF；⑦未發行
新股稀釋用`CapitalStock`面額股本近似股數，無直接流通股數欄位），**9項
皆可算，不因「資料不可及」快殺**。100檔快取樣本47檔可用（比#22少，因
F-score需要更多欄位同時齊全，涵蓋率天然更嚴）、121個20交易日快照
(2015-2024)，9/9項欄位齊全覆蓋率100.0%（可用樣本內）。F-score分布：
mean=3.29/median=3.26（0-9分，非常數/非退化）、F>=7候選池均值僅1.2%、
F>=8均值0.0%（在**未經value_board_v2價值篩選的一般樣本**上兩個標準
門檻幾乎無候選——這是符合Piotroski原始論文預期的結果，原始應用是套在
已篩過的低淨值市值比價值股宇宙，不是全市場，不代表F-score本身失效，
但暗示下一步套到value_board_v2時若候選池仍過薄，可能需要降低門檻）。
完整數字見`TRIALS_LEDGER.md`#93。**下一步（尚未做）**：用
`run_value_board_v2_pit_backtest.py`既有value_board_v2排序+候選池，
比較「原始版本」vs「+F-score gate（F>=7，若候選池過薄則測F>=6）」兩
版本的alpha與地雷率，這是本條「驗證改造」小節明講的核心比較，走完整
GATE_SEQUENCE剩餘關卡，不是重新驗證F-score本身IC。

**狀態（2026-09-03T04:55更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`第二十五輪
排程，本輪未跑完）**：新增`piotroski_fscore_gate_v1.py`——重用B24-500
既有快取（不重抓價量）+對500檔算F-score+自適應選門檻（F>=8/7/6取平均
候選數>=TOP_N裡最嚴格者），跑TRAIN/VALIDATION真實回測（本輪刻意跳過
100次隨機控制組，先看方向性alpha/mine_rate證據）跟既有基準比較。本輪
受時間/預算限制**未觀察到腳本完成**，`tasklist`確認背景行程仍在執行中
（記憶體量級跟500MB快取吻合，非卡死），完整心跳見`MARATHON_LOG.md`
2026-09-03T04:55條目。**尚未結案**——下一輪直接重跑
`python research/piotroski_fscore_gate_v1.py`即可（底層parquet快取
已涵蓋部分股票，非從零重跑）。

**狀態（2026-09-03T05:52更新，第二十六輪排程，本輪未跑完，重要執行面
教訓）**：本輪誤判上一輪背景行程已死（`tasklist`指令輸出亂碼疑似
「查無資料」），連續三次重新啟動同一支腳本，造成4個行程併發競爭同一
輸出檔（已用`kill -9`砍掉本輪誤開的3個，只留最早、存活最久的PID
9991繼續跑）。**教訓：這個環境背景行程其實會跨tool call存活，查證
要用`ps -ef`不要用`tasklist`**，完整分析見`MARATHON_LOG.md`
2026-09-03T05:52條目。**尚未結案**，`data/piotroski_fscore_gate_v1_
results.csv`仍不存在。下一輪先確認PID 9991（或其後繼行程）是否還在跑
再決定要不要重啟，不要盲目重新啟動。

**狀態（2026-09-03T05:56更新，第二十六輪排程接續，已結案：FAIL——
本段落與上段時序易誤讀，2026-09-03排程本輪整理時已修正順序：本段
發生在上段之後，是最終結論）**：上一段留下的PID 9991（加上排查過程中
一度誤啟動、後已用`kill -9`清掉的3個重複行程）皆已自然執行完畢，
`data/piotroski_fscore_gate_v1_results.csv`已產出且內容完整可用（多個
重複行程各自寫入同一輸出檔，最後完成者的結果覆蓋前面的，未觀察到檔案
損毀）。**核心比較結果**：自適應選定F>=6（最寬鬆門檻）。原始baseline：
TRAIN alpha=+6.26%(p=0.2672)/mine_rate=25.3%/return=+75.87%；VAL
alpha=+12.38%(p=0.1441)/mine_rate=16.9%/return=+85.52%。+F-score
gate(F>=6)：TRAIN alpha=+7.92%(p=0.4743)/mine_rate=29.1%/return=
+71.79%；VAL alpha=+5.24%(p=0.1772)/mine_rate=5.7%/return=+33.31%
(交易數718→98)。依本條「驗證改造」小節事前訂的判準：兩期alpha的p值
皆變得**更不顯著**（惡化非改善），地雷率沒有一致改善（TRAIN惡化
25.3%→29.1%、VAL改善16.9%→5.7%，一升一降），且VAL期return大幅流失
機會成本，**判定FAIL**，依快殺標準（使用者事前訂的便宜且決定性判準）
直接結案，未投入100次隨機控制組成本。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#94、`MARATHON_LOG.md`2026-09-03T05:56條目。**佇列
#23結案，接續佇列第一順位#24（除權息季節行為效應）**。

---

### 24. 除權息季節行為效應（台股專屬微結構，2026-09-03使用者裁示新增）

**經濟理由**：台股7-9月除權息旺季存在強烈的**散戶「填息」信念**
（相信除權息後股價會漲回除權息前水準）+**稅制驅動的棄息/參與行為**
（股利所得併入綜合所得稅計算、外加二代健保補充保費，高稅率族群傾向
棄息賣出、低稅率或外資傾向參與），這是台股在地行為/稅制效應，**不在
本佇列已測過的動量/營收/籌碼/beta類「美股因子家族本土化」譜系裡**，
是結構完全不同的假設來源（微結構+稅制，不是資訊面/風險溢酬）。

**具體假設定義**：以除權息交易日為事件錨點，測試除權息前/後一段窗口
（例如除權息前T-5到除權息日、除權息後填息期間）的報酬型態是否存在
系統性可預測性——第1關sanity階段先確認FinMind免費層有沒有現成的
「除權息日曆」資料集（`TaiwanStockDividend`或類似端點），若有才能做
PIT安全的事件研究，若查證後真的沒有免費來源，依快殺標準「資料不可及」
誠實判死，不硬幹。

**驗證改造（使用者原話明講，本條特別關鍵、必須做，不能省略）**：
**成本/稅務（含二代健保補充保費）必須全額建模**——除權息類效應是
本佇列所有假設裡最容易被交易成本+稅務吃光淨利的一類（頻繁參與除權息
交易牽涉證交稅、且股利所得計入稅務會顯著侵蝕淨報酬，不像一般價差
交易只有證交稅+手續費）。GATE_SEQUENCE第4關成本敏感度在這條假設上
要做到「含稅後淨alpha」而不是單純的價格報酬，1x情境的稅務假設要
明確寫清楚用哪個稅率級距（不能只用最低稅率美化結果，也不能只用最高
稅率醜化結果，需要合理範圍的敏感度分析）。**必須先證明扣完稅費淨
alpha仍為正、且能避開棄息殺盤的下檔保護成立，才能繼續往後面關卡走**
——這是本條假設額外於標準GATE_SEQUENCE第9關（下檔保護）之上、更早
就要確認的前置條件，因為棄息殺盤本身就是這個訊號最大的下檔風險來源。

**已知相關背景**：查證`HYPOTHESIS_QUEUE.md`/`STRATEGY_GRAVEYARD.md`
全文（`除權息`/`填息`/`棄息`/`股利`等關鍵字），本專案至今沒有測過
任何除權息季節性/事件相關假設，是全新的假設來源類別。

**下檔保護要求**：同上（見#20條目）+本條額外的稅後淨alpha前置條件，
適用本輪全部5條新假設。

**狀態（2026-09-03排程接續，已結案：FAIL）**：`ex_dividend_seasonal_sanity.py`
（新增，用原始未還原收盤價+複用`adjust.py::adjustment_events()`）。100檔
快取樣本62檔可用，443筆純現金股利事件。Sanity PASS（7-9月佔比69.8%、
除息跌幅vs理論殖利率rho=+0.6858）。三個cheap gate皆FAIL：殖利率→除息前
報酬percentile=32.6；殖利率→除息後報酬train/val正負號相反+percentile=
83.0；旺季vs非旺季填息率洗牌檢定20/60/120日percentile=87.0/86.2/60.6，
皆未過90.0門檻（依「不事後移動門柱」判死，不因87.0接近而放寬）。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#95。**佇列#20~24（使用者
2026-09-03裁示新增5條）至此全數結案。剩餘#5/#6/#8/#10仍卡外部依賴，
下一輪需重新確認這些依賴是否解鎖，若仍未解鎖則判定佇列實質已空，
需設計新假設軸。**

**2026-09-03（`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程，重新確認外部依賴
未解鎖，判定佇列實質已空，新增#25）**：逐一重新查證三個外部依賴——
①`BACKLOG.md`題材動能榜相關段落（`momentum_board`狀態仍是「紙上交易中」，
`grep`「回測未通過」/`null`/「紙上交易中」等關鍵字確認**PIT回測引擎仍未
建置**，#6/#8依附此地基仍動不了）；②B24/B25/B26——B25/B26已於2026-09-02
完成（見`research/B24_RESULTS.md`「B25分情境績效報告」章節），但#5/#10
真正的阻塞點不是「B25/B26未完成」，是**佇列裡至今沒有任何一條假設通過
完整GATE_SEQUENCE**（#1~24全數FAIL或卡外部依賴），沒有已過關的候選可
套用regime overlay，這個阻塞條件本身沒有改變。**確認三個依賴皆未解鎖**，
依協定第1節判定佇列實質已空，設計新假設軸：**#25月轉效應（Turn-of-Month
Effect，指數層級、非選股）**，見下方新章節。避開的兩種已知死法：①本
佇列10+條純選股排序類假設全滅（`HYPOTHESIS_QUEUE_PROTOCOL.md`第56行
分析的「表面漂亮、alpha不顯著/beta主導」共同死因）——#25不做任何個股
選擇；②已測過的三種「非選股」timing機制（#10regime overlay用大盤自身
200日均線/波動度、#15 vol-targeting用自身已實現波動度、#19+spillover
overlay用美股隔夜報酬）皆FAIL或卡待用——#25用的是**日曆結構本身**（月初
/月底特定交易日），經濟機制是機構現金流時點（月薪提撥退休金/基金申購
集中在月初、月底作帳buying），跟前三者的「用某個連續數值訊號決定曝險」
完全不同類別，是本佇列第一次測試「日曆效應」在指數層級的應用（唯一
已測過的日曆類是FUT軌`fut_weekday_effect`星期效應，FAIL，經濟機制
（週末效應）跟月轉效應（機構現金流時點）不同，不算重複）。

---

### 25. 月轉效應（Turn-of-Month Effect，指數層級，非選股）

**經濟理由**：Turn-of-month效應（Ariel 1987、Lakonishok & Smidt 1988等
經典文獻）——股市報酬系統性集中在「月底最後一個交易日到月初前3~4個
交易日」這個窄窗口，其餘天數報酬平淡甚至為負。經濟機制是**機構現金流
時點**：月薪提撥的退休金/定期定額基金申購集中在月初入帳、需要買進；
月底常有基金windows dressing（作帳買進強勢股美化月報表）跟月底結算
的系統性資金再平衡。這跟本佇列已測過的三種「非選股」timing機制（#10
regime overlay用大盤200日均線/波動度當開關、#15 vol-targeting用自身
已實現波動度動態配置曝險、#19+spillover overlay用美股隔夜報酬當訊號）
經濟機制完全不同——那三個都是「用某個連續數值統計量」決定曝險，這條
用的是**日曆本身的結構性位置**（交易日在月份中的相對位置），不依賴
任何連續型市場數據，是全新的機制類別。也跟已測過的日曆類假設
（FUT軌`fut_weekday_effect`，星期一/二~五固定規則，FAIL，經濟機制是
「週末效應」不是「月轉效應」）不同，本佇列/專案至今沒有測過月轉效應。

**具體假設定義**：定義「月轉窗口」= 每月最後一個交易日 + 次月前N個
交易日（第1關sanity先測N=3、N=4兩種常見文獻定義，不要一開始就上更多
變體造成事後多重比較），TAIEX（`^TWII`，不做任何個股選擇，套用對象是
大盤指數本身，資料源沿用`yf_price_client.py::fetch_yf_index()`既有
函式，零新增資料源風險）在月轉窗口內的日報酬 vs 窗口外其餘天數的日
報酬，先做第1關cheap gate（兩組平均報酬差異，對照組是隨機打散「哪些
交易日算月轉窗口」這個日曆標籤本身、保留原始報酬序列不變的洗牌null，
N>=100次），若訊號存在，第2關以後再考慮具體的曝險規則（例如只在月轉
窗口內持有大盤曝險，其餘時間空手或降低曝險）。

**已知相關背景**：查證`STRATEGY_GRAVEYARD.md`/`HYPOTHESIS_QUEUE.md`/
`TRIALS_LEDGER.md`全文（`月轉`/`turn.of.month`/`月底效應`/`window
dressing`等關鍵字），本專案至今沒有測過任何月轉效應假設——唯一相關
的日曆類測試是FUT軌`fut_weekday_effect`（星期效應，FAIL，`TRIALS_
LEDGER.md`#23），經濟機制（週末效應：資訊在週末累積、週一消化）跟
月轉效應（機構現金流時點）不同類別，不算重複測試。**資料可行性已
確認**：跟#19同樣使用`fetch_yf_index()`既有函式，零新增API整合成本；
台股交易日曆（考慮國定假日/颱風假等非交易日）需要正確判定「每月最後
一個交易日」跟「次月第N個交易日」，不能假設是自然日的月底/月初——
第1關sanity要用實際交易日曆（`^TWII`資料本身的交易日序列）計算，不
能用自然日期近似。

**下檔保護要求**：比照#20~24同一標準（見#20條目）——不能只贏買進持有
就算過關，須額外證明MDD受控、地雷率顯著低於隨機、regime危機情境（大盤
空頭/高波動期間）月轉效應是否依然存在或至少不放大虧損。

**狀態（2026-09-03，`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程新增）**：
**尚未開始**，這輪只登記假設、未寫任何程式碼、未跑任何測試。下一輪從
第1關cheap gate開始（先確認`fetch_yf_index()`能拿到`^TWII`完整歷史、
交易日曆月轉窗口判定邏輯正確——用實際交易日序列而非自然日期近似），
比照本佇列既有GATE_SEQUENCE，不跳關、不因為是新機制就放寬第一關的
cheap gate標準。**其餘#5/#6/#8/#10仍登記在案**，任一外部依賴解鎖時
應優先評估是否能接續，不因為新增#25就永久放棄它們。

**狀態（2026-09-03排程接續，已結案：FAIL）**：新增`turn_of_month_gate.py`
——月轉窗口定義用實際交易日序列判定（當月最後一個交易日+次月前N個
交易日，N分別測3跟4，不用自然日期近似），對照組是打散「哪些交易日算
窗口」這個布林標籤本身（保留原始報酬序列不變，N=200次洗牌）。**Sanity
PASS**：N=3窗口天數/年=47.8（預期約48天/年附近，判定邏輯無bug）。結果：
**N=3**——TRAIN(2010-2020)窗口內日均報酬+0.00084 vs 窗口外+0.00012，
diff=+0.00072，贏過洗牌null percentile=94.0（過關）；但**VAL(2021-2024)
窗口內+0.00008 vs 窗口外+0.00064，diff=-0.00056，方向完全反轉**，
percentile=28.0（遠未過90.0門檻）。**N=4**——TRAIN diff=+0.00035
(percentile=79.0，未過)、VAL diff=-0.00029(percentile=37.5，未過)，
同樣train/val正負號相反。兩種窗口定義的train/val同號判準皆未過，依
協定第1關cheap gate標準判**FAIL**，未進第2關以後。**不泛化成「日曆
效應類別完全沒用」**——只測了TAIEX指數層級+N=3/N=4兩種窗口定義+
2010-2024樣本，未測其他指數/成分股層級、未測不同N值、未排除已知市場
崩盤月份對TRAIN期結果的槓桿影響。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#96。佇列#25結案，**佇列#1~25原始+新增項目全數
結案**，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新確認：題材動能榜PIT
引擎仍未建置、佇列裡至今無任何一條通過完整GATE_SEQUENCE的候選可供
regime overlay套用，兩個阻塞條件均未改變），依協定第1節設計新假設軸
#26（見下方新章節），排隊第一，尚未開始第1關（含資料可行性查證），
下一輪不跳關。

---

### 26. 全市場融資餘額成長率（Aggregate Margin Debt Growth）當槓桿/
擁擠度regime訊號

**經濟理由**：融資餘額（散戶用信用交易槓桿買進的融資總額）快速成長
代表市場槓桿/投機性擁擠度升高，文獻與實務界（尤其美股NYSE margin
debt研究，例如margin debt growth rate被視為市場脆弱度/系統性風險的
領先指標之一）發現槓桿快速累積的市場對利空消息的反應會被放大（強制
斷頭/追繳保證金造成的連鎖賣壓），是**全新機制類別**——跟本佇列已測
過的三種非選股timing機制（#10 regime overlay用大盤200日均線/波動度、
#15 vol-targeting用自身已實現波動度、#19+spillover用美股隔夜報酬）
完全不同：那三者都是「價格/報酬本身衍生的連續數值統計量」，這條用的
是**市場結構性槓桿/擁擠度**（誰在用錢買、用了多少信用），不是價格
序列的任何變換，也跟已FAIL的#25（日曆結構）不同類別。台股融資融券
資料（`TaiwanStockMarginPurchaseShortSale`，FinMind既有資料集，
`load_dev()`個股層級已在`research/long_only_vs_market.py`使用過，
非全新資料源整合）逐日更新，可加總取得全市場層級的總融資餘額時間序列。

**具體假設定義**：對樣本內個股逐日融資餘額加總，計算全市場總融資餘額
的成長率（例如20日或60日變化率），排序/分箱後比較「成長率高分位期間」
vs「成長率低分位期間」的後續大盤（TAIEX）報酬與下檔風險（MDD/波動度）
——預期方向：融資餘額成長過快的時期，後續下檔風險升高（regime開關
應該在這種時期降曝險），不是預期融資餘額本身能預測報酬方向。

**資料可行性（尚未驗證，下一輪第1關要做的第一件事）**：`load_dev()`
目前是**逐檔**呼叫（見`long_only_vs_market.py`用法），要組成「全市場
總融資餘額」需要逐股加總——樣本涵蓋度是否足以代表大盤總融資餘額水位
（100檔快取樣本 vs 全市場，可能需要更大樣本才具代表性，這點在
sanity階段要誠實檢查、不能假設100檔加總就等於大盤）是本假設第一個
要驗證、可能推翻整個方向的關卡，不能省略直接跳去測訊號。

**已知相關背景**：跟`HYPOTHESIS_QUEUE_PROTOCOL.md`目前已測過的所有
「規則本身死於「選股排序」或「單一連續數值timing」的項目不同，這是
本佇列第一次測試「市場結構性槓桿/擁擠度」這個維度；跟已死的
`f_inst_streak_days`（#13，三大法人籌碼連續性，個股層級選股）也不同
——這條是市場加總層級的regime訊號，不對個股排序。

**狀態（2026-09-03，`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程新增）**：
**尚未開始**，這輪只登記假設、未寫任何程式碼、未跑任何測試。下一輪
第1關要先做**資料可行性/樣本代表性查證**（100檔快取樣本加總後的融資
餘額走勢跟外部已知的台股融資餘額歷史高低點是否大致吻合，例如2021年
台股大多頭融資餘額創高、2022年空頭融資餘額大幅下降這類已知結構性
事實），若樣本代表性不足需誠實記錄並考慮擴大樣本或改用官方公布的
全市場加總數字（若FinMind或TWSE openapi有現成全市場層級的融資餘額
統計，優先用官方數字而非自行從個股樣本加總估計），驗證通過後才進
cheap gate（成長率vs後續報酬/風險的洗牌置換檢定）。**其餘#5/#6/#8/#10
仍登記在案**，任一外部依賴解鎖時應優先評估是否能接續，不因為新增
#26就永久放棄它們。

**狀態（2026-09-03排程接續，資料可行性查證：第一階段完成，尚未取得
可用歷史序列，未進cheap gate）**：查證結果分三部分——
①**確認TWSE openapi `/exchangeReport/MI_MARGN`存在且可用**：實測回傳
1297檔全市場個股融資融券當日餘額（含融資買進/賣出/前日餘額/今日餘額/
限額等欄位），這正是「全市場層級官方數字」，比100檔個股加總估計更
理想（本假設條目原本列的優先方案）。②**但這條路目前拿不到多年歷史
序列**：`alpha-data/config.py`裡`twse_margin`資料源本來就已經在每日
管線裡（`kind: json, parser: raw_only`，非本輪新增，屬於既有凍結區
設定，本輪只讀未動），但查`alpha.db`（唯讀連線）發現`raw_records`表
裡`source='twse_margin'`**只有1天資料（2026-08-21）**——因為
openapi只回傳「當下最新一天」的快照，每日管線是從某天才開始持續
累積，還沒有累積出可回測的歷史深度，不能拿來做多年regime研究。
③**嘗試TWSE舊式`www.twse.com.tw/rwd/zh/margin/MI_MARGN?date=YYYYMMDD`
歷史查詢端點**（比照`twse_t86`同一個rwd家族的用法）：`curl`直接打回傳
空內容（0 bytes），尚未確認是「這個端點真的不存在/路徑錯誤」還是
「像`CLAUDE.md`記錄的TWSE已知地雷一樣需要用`requests`+正確headers
才會通，curl測不出來」——本輪budget用盡前來不及用Python requests
（比照`fetch.py`既有`HTTP_HEADERS`）重測這一步，是誠實的「查到一半」
狀態，不是「查證過確定沒有」。**下一輪要做的事（不跳關，先把這步
查完再進cheap gate）**：用Python `requests`（不要用curl，比照
`CLAUDE.md`已知地雷）加`HTTP_HEADERS`重測`www.twse.com.tw/rwd/zh/
margin/MI_MARGN?date=...`能不能回傳歷史特定日期資料；若這條路也不通，
退回原方案——用`factor_ic.py::sample_universe_ids(100,seed=20260822)`
同一批100檔快取樣本，逐檔`load_dev("TaiwanStockMarginPurchaseShortSale",...)`
（FinMind既有資料集，`long_only_vs_market.py`已用過同一個dataset，非
新資料源整合）逐股加總估計全市場融資餘額走勢，並用2021多頭創高/2022
空頭驟降這類已知結構性事實驗證樣本代表性（原假設條目已寫好這個驗證
方法，只是優先序調整為「先確認官方全市場數字真的拿不到歷史，才退回
估計方案」，避免捨棄更理想的資料源）。本輪查證用的暫存檔
（`twse_swagger_tmp.json`/`mi_margn_tmp.json`/`mi_margn_hist_tmp.json`）
已刪除、不納入commit，`is_holdout_consumed()`本輪未觸碰任何holdout
邊界。

**狀態（2026-09-03排程再接續，資料可行性查證：已確認可行，找到官方
全市場歷史數字，下一輪直接進cheap gate）**：上一段列的「下一輪要做
的事」在本輪完成——**問題出在路徑名稱寫錯**：正確的TWSE舊式歷史查詢
路徑是`/rwd/zh/marginTrading/MI_MARGN`（`marginTrading`，不是
`margin`），用`requests`+`HTTP_HEADERS`實測`https://www.twse.com.tw/
rwd/zh/marginTrading/MI_MARGN?date=YYYYMMDD&response=json&selectType=ALL`
回傳`stat=OK`的合法JSON（`content-type: application/json;charset=UTF-8`），
`.content.decode('utf-8')`可正確解析（注意：`requests`的`.json()`
內建編碼偵測在這個API上會誤判、需手動`json.loads(r.content.decode
('utf-8'))`，這是新發現、不是`fetch.py`既有已知地雷清單裡的項目，
下一輪寫正式抓取程式碼時要記得處理）。**回傳內容分兩個table**：
`tables[0]`是**全市場加總統計**（title「OOO年OO月OO日 信用交易統計」，
6欄：類別/買進/賣出/現金(券)償還/前日餘額/今日餘額，第3列是「融資
金額(千元)」——這正是本假設要的**官方全市場總融資餘額**，不需要
逐股加總估計，比原計畫的100檔樣本加總方案更理想、更準確）；
`tables[1]`是1200+檔個股逐檔明細（本假設用不到，但留存供未來其他
假設參考）。**歷史深度實測**：抽測2013-01-02／2015-01-05／
2018-01-02／2020-01-02／2022-01-04／2024-01-02／2026-08-21共7個
橫跨13年的日期，全部`stat=OK`且有完整資料，「今日餘額」數字量級
（單位千元）依序約1803億／2053億／1732億／1456億／2836億／2484億／
5469億，**大致符合已知結構性事實**（2020年低點呼應2020年3月COVID
崩盤後去槓桿、2022年高點呼應2021年全年多頭累積的融資水位、2026年
最新值遠高於過去反映近年大盤上漲後總市值與融資水位同步墊高）——
**樣本代表性查證用官方數字後已無意義**（官方數字本身就是全市場
100%涵蓋，不是樣本估計，不需要再驗證涵蓋度）。**結論：資料可行性
確認通過，下一輪直接進第1關cheap gate**——寫抓取腳本（逐日呼叫此
API取得`tables[0]`第3列「今日餘額」，比照`fetch.py`既有節流/重試
模式但**不寫進凍結區`fetch.py`本體**，另立`research/`目錄下的研究
專用抓取腳本；資料範圍鎖定TRAIN/VAL可用區間，不觸碰holdout），
計算20日/60日成長率，對TAIEX後續報酬與MDD做洗牌置換檢定。本輪
查證未寫入`alpha.db`（唯讀）、未修改任何凍結區檔案、`is_holdout_
consumed()`確認仍為`False`。

**狀態（2026-09-03排程接續，地基建置：抓取client+resumable週頻backfill
已完成並驗證可用，回補進度2.3%，尚未進cheap gate）**：新增
`margin_debt_market_client.py`（`fetch_margin_market_day()`單日抓取+
逐日parquet快取，跟`twse_t86_client.py`同一套atomic read/write pattern，
解決本輪探測到的新編碼陷阱——`requests`的`.json()`在這個API上會誤判
編碼，需手動`json.loads(resp.content.decode('utf-8'))`）+
`backfill_margin_debt_market.py`（`run_batch()`，resumable、bounded
batch，同`backfill_t86.py`同一種設計）。**刻意採用週頻抽樣、不是逐日**
（跟本條目原文字面「逐日呼叫」不同，這是本輪工程判斷非事後偷改範圍，
理由：全市場總融資餘額是緩慢變化的存量指標、20日/60日成長率用週頻
資料仍可合理近似中期趨勢，同時把約3300+次逐日呼叫壓縮到約680次週頻
呼叫，大幅降低反爬蟲封鎖風險與所需輪數，完整理由見腳本docstring）。
**驗證批次**：`run_batch(batch_size=15)`成功抓取15/15週（0錯誤、0封鎖、
0非交易日誤判），確認schema解析正確（`tables[0]`第3列「融資金額(仟元)」
「今日餘額」欄，單位仟元）、快取機制正常運作。**累積進度：15/662週
（2.3%）**，全範圍`2012-05-02~2024-12-31`（TRAIN+VAL，不觸碰holdout）。
**下一步（尚未做）**：下一輪繼續呼叫`python research/
backfill_margin_debt_market.py --batch-size 150`累積回補進度（比照
`backfill_t86.py`慣例，每輪跑一個batch即可，不用一次跑完），累積到
一定覆蓋率後（不需要100%，但要涵蓋2013-01-02/2015/2018/2020/2022/
2024這幾個先前查證過的已知結構性事實年份附近）才進cheap gate（計算
20日/60日成長率對TAIEX後續報酬與MDD做洗牌置換檢定，比照#25
`turn_of_month_gate.py`同一套框架）。本輪查證/驗證用requests未寫入
`alpha.db`（唯讀）、未修改任何凍結區檔案，`is_holdout_consumed()`
確認仍為`False`。

**狀態（2026-09-03排程接續，回補進度延續）**：接續上一輪，執行
`python research/backfill_margin_debt_market.py --batch-size 150`
（前景阻塞監控，因單批次超過工具10分鐘逾時上限被系統移至背景繼續
執行，本輪用逐次輪詢`research/data/raw_margin_debt_market/`快取檔案
數量確認持續累積、非卡死）。**累積進度：15→149/662週（22.5%）**，
本輪新增134週快取，過程中未見錯誤（輸出log因python stdout緩衝暫時
看不到內容，以實際落盤的parquet檔案數為準）。**尚未達到cheap gate
所需覆蓋率**（仍需涵蓋2013/2015/2018/2020/2022/2024這幾個關鍵年份
附近的完整覆蓋，目前僅覆蓋到約2015年初，2018年以後年份尚未回補到），
**下一輪繼續呼叫**`python research/backfill_margin_debt_market.py
--batch-size 150`接續回補（resumable，不會重算已完成的部分）。本輪
未寫入`alpha.db`、未修改任何凍結區檔案，`is_holdout_consumed()`確認
仍為`False`。

**狀態（2026-09-03T11:06更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程接續
回補）**：接續上一輪，前景阻塞執行一批`python research/
backfill_margin_debt_market.py --batch-size 150`（自動被系統移至背景，
輪詢快取檔案數量確認持續累積直到批次完成，非卡死）。**成功150/150週
（含11週非交易日/無資料，正常現象），0錯誤0封鎖，累積進度：
149→315/662週（22.5%→47.6%）**，資料涵蓋範圍延伸至2012-05~2018-05。
**仍未達到cheap gate所需覆蓋率**（2020/2022/2024三個關鍵年份附近仍
未回補到，2018年後年份也尚未涵蓋），**下一輪繼續呼叫**`python
research/backfill_margin_debt_market.py --batch-size 150`接續回補
（resumable，不會重算已完成的部分，比照近三輪的慣例）。本輪未寫入
`alpha.db`、未修改任何凍結區檔案，`is_holdout_consumed()`確認仍為
`False`。

**狀態（2026-09-03T11:35更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程接續
回補）**：接續上一輪，執行`python research/backfill_margin_debt_market.py
--batch-size 150`（自動被系統移至背景，輪詢快取檔案數量確認持續累積
直到批次完成，非卡死）。**成功150/150週（含17週非交易日/無資料，正常
現象），0錯誤0封鎖，累積進度：315→465/662週（47.6%→70.2%）**，資料
涵蓋範圍延伸至2012-05~2021-03。**仍未達到cheap gate所需覆蓋率**（2022
跟2024兩個關鍵年份附近仍未回補到），**下一輪繼續呼叫**`python
research/backfill_margin_debt_market.py --batch-size 150`接續回補
（resumable，剩餘約197週，預估再1~2輪批次即可回補到2024年底、涵蓋
所有已知結構性事實年份）。本輪未寫入`alpha.db`、未修改任何凍結區檔案，
`is_holdout_consumed()`確認仍為`False`。

**狀態（2026-09-03T12:03更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程接續
回補）**：接續上一輪，執行`python research/backfill_margin_debt_market.py
--batch-size 150`（前景阻塞逾時後自動移至背景，用until-loop輪詢
`research/data/raw_margin_debt_market/`檔案數量直到連續4次（60秒）
數量不變才視為批次完成，非卡死判斷法比前幾輪更嚴謹）。**新增109個
週檔（略少於請求的150，研判是批次內非交易日/假日週數較多，非錯誤，
下一輪若要精確核對可查腳本本身的skip計數），累積進度：465→574/662週
（70.2%→86.7%）**，資料涵蓋範圍延伸至2012-05~2023-04-28。**仍未達到
cheap gate所需覆蓋率**（2023年後段跟2024全年仍未回補到，2024關鍵年份
附近尚未涵蓋），**下一輪繼續呼叫**`python research/
backfill_margin_debt_market.py --batch-size 150`接續回補（resumable，
剩餘約88週，預估再1輪批次即可回補到2024年底、涵蓋所有已知結構性事實
年份）。本輪未寫入`alpha.db`、未修改任何凍結區檔案，`is_holdout_
consumed()`確認仍為`False`。`git status`確認殘留變更（`data/
rate_limit_state.json`、`research/pit.py`及多個`.log`未追蹤檔案）
跟前幾輪判斷一致，非本輪產生，不觸碰、不納入commit。

**狀態（2026-09-03T12:29更新，`HYPOTHESIS_QUEUE_PROTOCOL.md`排程接續
回補，本批次一次補完剩餘全部）**：接續上一輪，執行`python research/
backfill_margin_debt_market.py --batch-size 150`（背景執行，輪詢
`research/data/raw_margin_debt_market/`檔案數量直到連續3次（60秒）
數量不變才視為批次完成）。**成功補完剩餘全部88週（其中4週非交易日/
無資料，正常現象），0錯誤0封鎖**。**累積進度：574→662/662週
（86.7%→100.0%）——全範圍`2012-05-02~2024-12-31`（TRAIN+VAL）週頻
回補正式完成，資料地基就緒**。**下一輪要做的事（不跳關，直接進第1關
cheap gate，不用再回補）**：讀取`research/data/raw_margin_debt_market/`
全部662個週檔，計算全市場總融資餘額20日/60日成長率，對TAIEX後續報酬
與MDD做洗牌置換檢定（比照`turn_of_month_gate.py`同一套cheap gate
框架：真實訊號 vs N≥100次隨機打亂時序的對照組，percentile需≥90.0
門檻，train/val同號才算過），事前先鎖定判準（不能事後移動門柱）。
本輪未寫入`alpha.db`、未修改任何凍結區檔案，`is_holdout_consumed()`
確認仍為`False`。`git status`確認殘留變更（`data/rate_limit_state.json`、
`research/pit.py`及多個`.log`未追蹤檔案）跟前幾輪判斷一致，非本輪
產生，不觸碰、不納入commit。

**狀態（2026-09-03排程接續，第1關cheap gate：已結案，FAIL）**：新增
`margin_debt_growth_gate.py`——週頻融資餘額`.pct_change(4)`/
`.pct_change(12)`近似20日/60日成長率，配對TAIEX日線算後續同長度窗口
最大回撤幅度（絕對值），Spearman相關+洗牌置換檢定（N=200，打散配對
本身，保留兩邊各自時序不變）。**20d(4w)**：TRAIN(n=408)corr=-0.0490
(percentile=14.0)、VAL(n=190)corr=+0.0633(percentile=86.0)，train/val
正負號相反。**60d(12w)**：TRAIN(n=400)corr=-0.0954(percentile=3.5)、
VAL(n=181)corr=+0.0870(percentile=88.5)，正負號仍相反，VAL percentile
接近但未過90.0門檻。兩種窗口定義皆train/val方向不一致，依協定第1關
cheap gate標準判**FAIL**，未進第2關以後（比照#24/#25「不因接近門檻
而放寬」同一把尺，88.5雖接近90.0仍判死）。**不泛化成「融資餘額槓桿
水位這個維度完全無效」**——只測了週頻近似成長率+Spearman相關+同長度
forward回撤幅度這個具體構造，未測用水位（而非成長率）當訊號、未測
非線性/極端分位效應。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#97。**佇列#26結案，接續佇列第一順位#27（多因子
z-score複合評分）**。

---

### 27. 多因子「複合評分」策略（z-score blend，2026-09-03使用者裁示新增）

**經濟理由（吸取#22的教訓）**：`#22`（品質×營收加速×法人吸籌+低波動
四濾網硬AND合取）已結案FAIL，死因是sanity階段候選池只剩14%（四個
條件同時成立的股票太少，本質是把宇宙砍到剩一小撮特定組合，過度擬合
單一交集，不是穩健的複合訊號）。這條改用**z-score加總複合**取代硬
AND交集：3-5個「經濟理由彼此獨立、統計上低相關」的因子各自算橫截面
z-score後加總（等權或依既有驗證強度加權），做多複合分數最高分位——
複合價值的經濟理由是**分散因子各自的特異雜訊**（每個因子的訊噪比都
不夠高，但彼此獨立的雜訊部分加總後互相抵消，訊號部分累加），不是
硬性篩掉不符合任一條件的股票，樣本規模不會像硬AND那樣被過度壓縮。
這是本佇列第一次測試「z-score線性複合」這個構造，跟已FAIL的硬AND
版本（#22）機制上有本質差異，不是同一個死法換皮。

**具體假設定義（使用者原話方法論，逐字記錄）**：
1. 選3-5個「經濟理由獨立、彼此低相關」的因子：品質（GP或ROE）、
   價值（B/P或E/P）、動能（中期）、台股專屬（月營收意外或法人連續
   買超）——各自算標準化z-score。
2. 等權（或依既有驗證強度加權）加總成複合分數，做多top decile、
   月度再平衡、全額成本。
3. **因子相關性要先查證**：算相關矩陣，高度相關的因子只留一個——
   複合價值來自分散因子特異風險，不是疊加同一個訊號兩次。

**抗過度擬合控制（使用者原話明講，比單因子更嚴格，因為組合放大
p-hacking風險，務必全部做到不能省略）**：
- **隨機對照draws≥300**（比本佇列一般假設的100更嚴），且對照組是
  「隨機選同數量因子、亂配權重」，用來證明贏的是**這個特定的複合
  組合**，不是「任意複合、隨便加權都會贏」這種弱證據。
- **因子權重只准用TRAIN期資料決定並凍結**，進入OOS(VAL)驗證前不得
  回頭調整權重——這是防止用VAL期資料偷偷微調權重、把樣本外驗證做成
  變相的樣本內擬合。
- **正交性檢查**：複合策略的超額報酬對每一個組成單因子分別做迴歸，
  確認複合的alpha不是「只是重新表達了其中某一個因子」（如果複合alpha
  被其中一個單因子完全解釋掉，代表這不是真正的複合，是偽複合、換皮
  的單因子）。
- **leave-one-factor-out**：逐一拿掉複合裡的每一個因子，看邊際貢獻——
  跟#22「四濾網leave-one-out」同精神但這裡是z-score加總不是AND，操作
  方式是「重新算拿掉某個因子後的複合分數」不是「拿掉某個條件篩選」。
- 逐年一致性≥5/6、成本1x/2x/3x敏感度——跟本佇列標準GATE_SEQUENCE
  第4/6關一致，複合策略不能豁免。

**已知相關背景**：組成因子候選裡，GP（#20）跟月營收意外×低關注度
（#21）都已經在**單因子層級**FAIL（IC接近雜訊）——**這是刻意的**，
使用者原話明講「先跑baseline複合（GP+價值+月營收意外，等權），過
cheap gate才打完整gauntlet」，複合假設的前提正是「單因子各自弱訊號
可能透過分散雜訊而在複合後顯現」，不是要求組成因子必須各自先通過
單獨測試才能拿來組合——但這也代表baseline複合若在cheap gate就死，
證據力會比較弱（因為組成因子本身證據已經很薄弱），需要如實記錄這個
先驗弱點，不要因為複合gate1過了就過度樂觀宣稱「弱訊號組合出強訊號」，
還是要走完整驗證鏈才算數。價值因子（B/P或E/P）本專案已有`value_
board_v2`既有實作可以參考因子定義，不用重新設計。

**下檔保護要求**：同本輪其餘假設（見#20條目「下檔保護要求」小節），
不能只贏買進持有，MDD/地雷率/regime存活都要證明。

**狀態（2026-09-03排程接續，第1關CHEAP_PASS，未結案）**：新增
`composite_zscore_v1.py`——相關矩陣確認baseline三因子（`f_gross_
profitability`/`f_value_pb`/`f_revenue_surprise`）兩兩相關係數絕對值
皆<0.4（GP vs value_pb=-0.378、GP vs revenue_surprise=+0.162、
value_pb vs revenue_surprise=-0.200），非高度相關，符合「低相關」
前提；選`f_value_pb`而非`f_value_pe`當估值因子理由：`TRIALS_LEDGER.md`
#13 CHEAP_PASS狀態比#14（累積校正後降級為不確定）更穩固。逐日橫斷面
z-score加總後跑cheap IC gate（沿用`factor_ic.py`既有框架，standalone
bonferroni_n=1）：TRAIN mean_ic=+0.0735 IR=+0.458(n=74)、VAL
mean_ic=+0.0826 IR=+0.529 hit_rate=0.66(n=47)，train/val同號，
null percentile=**100.0**（門檻90.0，過關）——**CHEAP_PASS**，本佇列
證據最強的複合候選之一。**但這只是第1關，且刻意未包含使用者原話額外
要求的「隨機對照draws>=300、對照組是隨機選同數量因子亂配權重」這個
更嚴格控制**（見腳本檔頭範圍聲明）——目前的cheap gate只證明「這個
複合分數本身有可辨識的橫斷面預測力」，不等於證明「贏過任意隨機3因子
組合」，尤其GP（#20）跟月營收意外相關的revenue_surprise單因子IC
本身接近雜訊，複合後轉強需要下一輪用300-draw隨機組合控制驗證不是
巧合疊加，不能只因cheap gate過關就樂觀認定「弱訊號組合出強訊號」
成立。**下一輪**：300-draw隨機因子組合控制→正交性檢查→leave-one-
factor-out→若都過再進portfolio層構造（走完整GATE_SEQUENCE第2~9關）。
完整見`TRIALS_LEDGER.md`#97、`composite_zscore_v1.py`（新增，可重複
執行）、`composite_zscore_v1_run.log`（新增）。

**狀態更新（2026-09-03T23:47排程接續，仍未結案）**：上一輪（陳舊鎖檔顯示
崩潰，未commit）已寫好`composite_zscore_v1_random_control.py`（300-draw
隨機因子組合控制，方法見腳本檔頭）但有實作bug——`weighted_zscore_composite`
每次呼叫後沒清掉暫存欄位`_f_composite_random_draw`，baseline補算階段留下
的殘留欄位讓後續draw迴圈merge時左右兩側同名欄位被pandas加`_x`/`_y`後綴，
導致`KeyError`當場崩潰（第1個draw就死，300 draws一次都沒跑成）。本輪已
修好（merge前先drop殘留欄位，見腳本diff）並在背景重新啟動執行，跑到本輪
收工時**仍未跑完**（300 draws每次都要對~80檔股票重新merge+121個快照算
Spearman IC，比預期慢很多，本輪內等待20分鐘以上仍在跑，過程中還撞到
本機另一個排程觸發的hypothesis_queue instance搶走鎖檔又提前結束的插曲，
但雙方都沒寫壞任何已提交的檔案，只是巧合印證了`marathon_lock.py`docstring
自己講的「not thread-safe against true concurrency」）。**下一輪待辦**：
`python composite_zscore_v1_random_control.py`背景進程若還在跑（本輪
收工時pid 28324仍存活，用`nohup`背景啟動，理論上會在本次claude session
結束後於作業系統上繼續跑），先檢查`data/composite_zscore_v1_random_
control.csv`是否已產生（300列，欄位`draw/factors/weights/train_ic/
val_ic`）；若已產生，直接讀取算出的`baseline_val_ic`跟隨機分布比較算
percentile（跟腳本`main()`同一套公式：`100*mean(abs(baseline)>abs(random
draws))`，門檻90.0）寫進本條目跟`TRIALS_LEDGER.md`正式判CHEAP_PASS或
FAIL；若進程已死但CSV沒產生完整300列，直接重跑（bug已修好，理論上這次
可以順利跑完，只是慢，需要抓時間預算，必要時背景啟動後這輪先收工，
下一輪只做「檢查結果」不用重跑）。

**狀態更新（2026-09-04T00:15排程接續，仍未結案，已改善根基設施）**：
接手時上一輪背景行程仍在運算（CPU持續增加、非卡死）但完全沒有
checkpoint機制，300 draws跑完才一次寫入。已比照`dividend_yield_
portfolio_v1.py`checkpoint模式改寫`composite_zscore_v1_random_
control.py`（`CHECKPOINT_PATH`+`deadline`時間預算+每10筆draw落盤，
`(CONTROL_SEED,i)`衍生種子讓任一draw可獨立重放），終止舊行程重新
啟動。**新發現的更嚴重瓶頸**：`load_sample_with_factors()`（100檔×
全部~25個因子）光載入就要20分鐘以上，比每次重啟省下多少draw運算都
更貴——真正的成本大頭是「重啟本身」不是「300 draws本身」。已用大
時間預算(3000秒)重新在背景啟動，本輪收工時仍未產出結果。**下一輪
待辦**：先查`data/composite_zscore_v1_random_control_checkpoint.json`
／`data/composite_zscore_v1_random_control.csv`是否已有進度或完整
結果，完整見`MARATHON_LOG.md`2026-09-04T00:15條目。

**狀態更新（2026-09-04 03:23排程接續，仍未結案）**：背景行程（PID 34408）
這次真的存活過了上一輪session邊界，checkpoint從上一輪的10/300推進到
30/300，本輪確認存活+持續進步後判斷「重啟成本(~20分鐘reload)遠高於等待
成本」，刻意不碰這個行程，只等它自然跑完，完整分析見`MARATHON_LOG.md`
2026-09-04 03:23條目。下一輪先查`data/composite_zscore_v1_random_
control_checkpoint.json`是否已到300 draws，到了就直接判percentile
CHEAP_PASS/FAIL，沒到且行程還活著就繼續等，行程死了才重跑。

**狀態更新（2026-09-04T04:53排程接續，仍未結案）**：接手時發現陳舊鎖檔
（held by pid 20592, 30.1分鐘），研判上一輪異常結束未commit。checkpoint
已從上一輪心跳的100/300推進到**122/300**（行程存活期間確實有累積進度，
`Get-Process python`確認舊行程已死）。本輪維持「不重啟、等待」策略，用
`CZC_TIME_BUDGET_SECONDS=1500`重新背景啟動（PID 1869，nohup+disown），
等待約3分鐘後確認仍存活且處於已知的~20分鐘資料載入階段（未進入draw
迴圈輸出，非卡死），本輪不繼續同步等待、收工讓行程於OS層背景繼續，
完整分析見`MARATHON_LOG.md`2026-09-04T04:53條目。**下一輪待辦**：先查
`data/composite_zscore_v1_random_control_checkpoint.json`是否已到300
draws，到了就直接判percentile CHEAP_PASS/FAIL並更新
`TRIALS_LEDGER.md`，沒到且行程還活著就沿用同一策略繼續等待，行程死了
才重跑（已確認checkpoint機制正確，重跑只需接續而非從頭）。

**狀態更新（2026-09-04T05:27排程接續，仍未結案）**：接手時PID 1869
確認仍存活，checkpoint從122推進到150/300、監控5分鐘內再推進到155/300，
**確認背景行程真的能跨輪session邊界存活**（04:52:31啟動、存活到至少
05:27，遠超過單輪session長度，坐實「不重啟、等待」策略的前提假設）。
本輪監控中PID 1869自然消失（研判是上一輪25分鐘時間預算到期後正常
結束，非崩潰），改用`CZC_TIME_BUDGET_SECONDS=3600`（1小時，比前幾輪
更大）重新nohup+disown背景啟動（PID 883），確認3分鐘內無crash後收工。
**下一輪待辦不變**：查checkpoint是否已到300 draws再判定；本輪額外
教訓是時間預算不能設太小（25分鐘會在reload+多輪draw運算後不夠、提前
正常退出），這次拉大到1小時應能減少「進度還在推進但被時間預算切斷」
的無謂重啟次數。完整見`MARATHON_LOG.md`2026-09-04T05:27條目。

**狀態更新（2026-09-04T05:54排程接續，仍未結案，新發現存活偵測方法
盲點）**：接手時誤用Windows原生`tasklist`查python.exe回報「無符合準則
的工作」，誤判上一輪05:27啟動的PID 883（3600秒預算，理論到期時間跟
本輪檢查時刻幾乎重疊）已死，因此重複啟動了一個新行程（PID 1126）。
啟動後改用`ps aux`（MSYS/Git-Bash指令）交叉確認才發現**PID 883其實
仍存活**——`tasklist`偵測不到Git-Bash背景啟動的python行程，是這次
誤判的根因。發現雙行程同時對同一份checkpoint運算後立即`kill -9
1126`，確認`data/composite_zscore_v1_random_control_checkpoint.json`
draw_records數量在kill前後皆為**170**（1126啟動後僅約2-3分鐘、仍卡在
~20分鐘資料載入階段，尚未寫入任何checkpoint），未被雙寫破壞，保留
PID 883繼續獨自運算。**下一輪起，判斷背景行程存活一律用`ps -p <pid>`
/`ps aux`，不要只信`tasklist`**——這是本輪唯一的方法論修正，記進本
段落供下一輪與其他馬拉松軌道參考（同一台機器上其他背景長跑腳本也
可能中同一個坑）。完整見`MARATHON_LOG.md`2026-09-04T05:54條目。

**狀態更新（2026-09-04T06:27排程接續，仍未結案）**：`ps -p 883`確認
PID 883持續存活，checkpoint從170推進到220/300（本輪內輪詢5分鐘觀察到
210→220，非卡死，單draw約60~75秒）。行程已自然跨過自身3600秒時間
預算理論到期時刻（05:27:37啟動，理論到期06:27:37）仍未結束，研判
deadline判斷點只在draw之間檢查、不會中途切斷正在算的那一筆。維持
「不重啟、等待」策略（重啟成本~20分鐘reload遠高於等待成本，已連續
多輪驗證），不碰這個行程，讓它繼續在OS背景運算。以本輪觀測速率估計
剩餘80 draws還需80~100分鐘，遠超單輪工作預算。**下一輪待辦**：
`ps -p 883`確認存活，活著就不碰繼續等；已自然結束（不論到期或崩潰）
則檢查checkpoint是否已到300，未到用`CZC_TIME_BUDGET_SECONDS`（建議
3600以上）重新nohup+disown背景啟動接續（checkpoint機制已驗證正確
續跑，不重算已完成draw）；到300就直接算percentile
（`100*mean(abs(baseline_val_ic)>abs(random_draw_val_ic))`，門檻90.0）
判CHEAP_PASS/FAIL並更新`TRIALS_LEDGER.md`。完整見`MARATHON_LOG.md`
2026-09-04T06:27條目。

**狀態更新（2026-09-04T06:52排程接續，仍未結案）**：接手時上一輪PID 883
已自然結束（checkpoint停在232/300，比06:27記錄的220多12筆，未遺失），
用`CZC_TIME_BUDGET_SECONDS=3600`重新nohup+disown背景啟動（新PID 2037），
確認3分鐘內存活無crash後維持「不重啟、等待」策略收工。**剩餘68 draws**，
估計還需68~85分鐘。下一輪待辦同上一則：`ps -p 2037`確認存活就繼續等，
已死則檢查checkpoint是否已到300再判定是否重啟或直接算percentile。完整見
`MARATHON_LOG.md`2026-09-04T06:52條目。

**狀態更新（2026-09-04T07:29排程接續，仍未結案）**：`ps -p 2037`確認持續
存活（06:52啟動、已運算37分鐘），checkpoint從06:52記錄的232筆推進到
260/300（06:52→07:21約29分鐘完成28筆，速率約62秒/draw），但07:21~07:28
輪詢7分鐘皆停留260不動——查腳本確認每10筆draw才落盤一次（非逐筆寫入），
260→270正處於批次運算中屬正常現象，非卡死。維持「不重啟、等待」策略，
以剩餘40筆×62秒/draw估算還需約41分鐘。下一輪待辦不變：`ps -p 2037`
存活就繼續等，已死則查checkpoint是否已到300決定重啟或直接判定
percentile。完整見`MARATHON_LOG.md`2026-09-04T07:29條目。

**狀態更新（2026-09-04T08:xx排程接續，已結案：FAIL）**：300 draws已完成
（checkpoint到300，行程自然結束），計算得percentile=**87.2**（baseline
VAL IC=+0.0826 vs 300個隨機3因子加權組合VAL IC分布，門檻90.0，未過）。
依「事前綁定門檻不事後移動門柱」鐵律直接判**FAIL**，不做正交性檢查/
leave-one-factor-out，未進portfolio層構造。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#102。**佇列#27結案。#5/#6/#8/#10仍卡外部依賴未解鎖
（本輪查證：B24-500仍不及格、題材動能榜PIT引擎仍是紙上交易中/無回測）
——佇列實質已空，下一輪需依協定第1節設計新假設軸（regime/擇時型，避開
純選股），本輪因時間/預算限制未及展開，留給下一輪。**

### 28. 市場廣度背離（Breadth Divergence）當regime擇時訊號（2026-09-04排程新增）

**背景（為何是這條，不是同一死掉機制換皮）**：`HYPOTHESIS_QUEUE_PROTOCOL.md`
指出本佇列已死的選股類假設共同死因是「表面總報酬漂亮、拆解後主要是beta
曝險、alpha不顯著」，缺一個「什麼時候該降曝險」的機制。但已測過的
regime/擇時類機制要避免重複：
- `#10`（市場regime擇時overlay）已用**TAIEX 200日均線趨勢＋20日已實現
  波動度**兩維度建置完成方法論框架（`regime_overlay.py`），卡點是「沒有
  已過關的選股候選可套用」，不是機制本身沒做。
- `#15`（波動度目標化）用**已實現波動度**縮放曝險，已FAIL（隨機控制組
  percentile 8.0/3.0）。
- `#2`（CTA趨勢跟隨，期貨）用**12個月報酬正負號**做時序動量，已FAIL
  （percentile=10.0，死因是動量崩盤——單一慢速窗口在V型反彈時來不及
  轉向）。若直接把同一個「價格趨勢正負號」機制搬到TAIEX現貨當資產配置
  開關（多頭持有指數/空頭轉現金），本質跟CTA是同一種「價格趨勢跟隨、
  單一資產、單一窗口」機制換皮，會重蹈同樣的動量崩盤死法，**刻意不
  這樣做**。
- `#26`（全市場融資餘額成長率）用**融資餘額成長率**當個股層級因子測試
  （Spearman相關predict forward報酬/回撤），已FAIL。

這條要測的**廣度（breadth）**是與上述四者本質不同的經濟機制：不是
「指數本身的價格趨勢」（#10的trend維度、#2），不是「波動度水位」（#10的
vol維度、#15），不是「槓桿/融資水位」（#26）——而是**指數上漲時，有
多少比例的個股真的一起參與上漲**。經濟理由：狹幅上漲（指數創高但參與
上漲的個股比例萎縮，即「廣度背離」）是市場結構脆弱、由少數權值股撐盤
的訊號，歷史上常領先於指數本身的頭部（技術分析文獻中的
advance-decline divergence、%above-200MA breadth-thinning，是獨立於
價格趨勢動能之外的市場內部參與度量測）。`#10`建置時明確記錄
「市場廣度——這輪未實作……臨時湊一個需要重新掃全樣本每日漲跌，屬於
這輪工作單位以外的地基建置量」——這條就是把那塊「待補」的地基補上，
並獨立測試它本身有沒有regime擇時的加值，不是等#10的候選出現才附掛。

**具體假設定義**：
1. **廣度指標**：用既有`factor_ic.py`的300檔快取樣本（`SAMPLE_SIZE=300`，
   已有價格快取，不需要新的API呼叫），對每一檔股票計算「當日收盤價 vs
   自身200日均線」的布林值，每個交易日算全樣本「高於自身200日均線的
   比例」（breadth_pct），得到一條與TAIEX指數本身走勢分開計算的時間
   序列。
2. **背離訊號**：TAIEX指數本身20日動量為正（仍在漲）、但breadth_pct
   對其自身歷史（如過去60日）呈現下降趨勢（廣度惡化）時，判定為
   「背離警戒」regime，此時降低（或全部撤出）對TAIEX買進持有的曝險；
   兩者同向（廣度確認）時維持正常曝險。**注意這是廣度相對自身歷史的
   邊際變化，不是breadth_pct的絕對高低**——避免跟#10的「TAIEX vs
   200MA」（絕對趨勢水位）變成同一種訊號的複製。
3. **驗證對象**：跟#10同一個精神，先用TAIEX買進持有本身當測試對象
   （不需要已過關的選股候選），驗證的是「這個擇時overlay本身能否
   改善風險調整後報酬/降低MDD」，不是選股。
4. **對照組設計**：隨機打亂breadth_pct的時間序列（保留其邊際分布，
   打散跟指數報酬的時序對齊關係）當隨機控制組，證明贏的是「廣度惡化
   確實領先指數走弱」這個時序關係本身，不是任意曝險縮放都會贏。

**已知相關背景**：`regime_overlay.py`（#10）docstring第三段
「市場廣度（breadth）：這輪未實作」明確留下這個待補項；`factor_ic.py`
`SAMPLE_SIZE=300`快取樣本已被`#77/#79/#100/#101`等多條因子驗證重複
使用過，資料可行性已被反覆確認可行，這條不需要新的資料工程只需要
重新聚合既有快取。

**資料可行性初步查證**：300檔快取樣本已有日頻收盤價快取（供200日均線
因子如`#17`使用過），聚合成全樣本每日breadth_pct只需要既有快取的
標準pandas聚合，不涉及新的外部API呼叫，符合資料源禮儀（不重新對TWSE/
FinMind發動新一輪爬取）。

**狀態（2026-09-04排隊中，尚未開始第1關）**：這輪工作單位到此為止
（依協定「一輪只做一個有界工作單位」——本輪已完成#27收尾+此新假設
設計，不在同一輪展開第1關sanity），下一輪從sanity（先確認breadth_pct
時間序列在已知的市場頭部/回檔期間是否真的表現出「領先指數走弱」的
背離型態，不是反著跑或無訊號）開始，不跳關。

**狀態（2026-09-04接續排程，第1關sanity：PASS，非最終判定）**：新增
`breadth_divergence_sanity.py`——用既有300檔快取樣本（254檔可用）算
`breadth_pct`（收盤價>自身200日均線比例，逐日聚合），跟TAIEX 20日動量
組成背離訊號（指數動量為正但breadth對60日前下降=「背離警戒」）。三項
sanity皆PASS：①breadth_pct非退化（n=3485天，min=0.000/max=0.878/
mean=0.528/std=0.172）、divergence_flag觸發率25.0%（非0/非常數）；
②3個已知危機run-up窗口2/3（2018Q4貿易戰急跌、2020Q1新冠崩盤）顯示
breadth下降比例73.3%明顯高於無條件基準率50.7%，2022全年空頭run-up
窗口未見領先（50.0%≈50.7%，緩慢型空頭的run-up本來就不一定有急跌前的
清楚領先訊號，記錄不隱瞞）；③divergence_flag觸發後(lag1)20日TAIEX
前瞻報酬+0.17%明顯低於無條件平均+0.66%，方向正確非反過來。**這只是
第1關sanity，不是最終PASS**——下一輪進第2關隨機控制組（打亂breadth_pct
時間序列跟TAIEX報酬的時序對齊，證明贏的是「廣度惡化領先指數走弱」這個
時序關係本身，不是任意曝險縮放都會贏），比照本佇列既有GATE_SEQUENCE，
不跳關。完整見`MARATHON_LOG.md`本輪心跳、`TRIALS_LEDGER.md`#103、
`breadth_divergence_sanity_run.log`。

**狀態（2026-09-04接續排程，第2關隨機控制組已跑完，已結案：FAIL）**：
新增`breadth_divergence_overlay_v1.py`——把divergence_flag轉成具體曝險
規則`exposure=0.3 if divergence_flag else 1.0`（shift(1)避免未來函數），
第2關（打亂exposure時序，N=100 draws，比照`vol_targeting_v1.py`/
`spillover_overlay_v1.py`同一套permutation null）結果：TRAIN真實overlay
總報酬+62.86%（反而輸給買進持有+79.49%）、對打亂分布percentile=54.0；
VAL真實overlay總報酬+42.96%（買進持有+56.36%）、percentile=51.0。兩期
皆遠低於90.0門檻且貼在50附近（完全沒加值，不是邊緣未過）。依快殺標準
「已被控制組拆穿之偽影家族換皮」（改變曝險力道）判**FAIL**，未進第3關
以後。**不泛化成「市場廣度這個概念完全沒用」**——只測了這個具體二元
背離定義+固定0.3/1.0曝險切換，未測連續函數版本。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#105、`MARATHON_LOG.md`本輪
心跳。佇列#28結案——**#1~28全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，
下一輪需重新確認依賴是否解鎖，未解鎖則需設計新假設軸#29，且應避開
「純選股排序」（10條已FAIL）跟「timing/overlay類」（#2/#10(方法論)/
#15/#19/#26/#28全數FAIL或未套用成功）這兩種已知死法/卡點，優先考慮
機制上真正不同的第三類角度。**

---

### 29. 等權重再平衡溢酬 Diversification Return / Equal-Weight Rebalancing Premium（2026-09-04排程新增）

**依賴重新查證（本輪，2026-09-04T接續排程）**：`BACKLOG.md`第698/1142行
`value_board_v2`（B24-500）仍標「回測未通過」，第1289/1291行題材動能榜／
未來性濾網仍標「紙上交易中」，均與上次查證（#27/#28兩輪）一致、無新
進展。確認**#5/#6/#8/#10四項依賴依然全部卡住**，佇列實質已空，依協定
第1節設計新假設軸。

**經濟理由（跟前28條在機制分類上真正不同的第三類）**：前28條假設可歸為
兩大類——①**方向性選股排序**（原始/剝離beta動量、產業內RS、營收驚喜、
籌碼連續性、低波動/低beta、52週高點、多因子z-score等10條，全部是「排序
挑股票」）、②**timing/exposure overlay**（CTA、vol-targeting、美股隔夜
外溢、融資餘額、市場廣度、regime overlay方法論，全部是「決定要不要
持有/持有多少」）——兩類在這個專案裡都全軍覆沒或卡在候選不足。這條測的
是**第三個正交維度：portfolio construction（給定同一組標的，用什麼權重
組合它們）**，不涉及「挑哪些股票」（不做任何選股判斷、可以直接用既有
全樣本或現成的300檔快取宇宙）、也不涉及「什麼時候該持有多少」（全程
維持滿倉、不做任何曝險縮放）。文獻上「等權重指數長期跑贏市值加權指數」
是有名的實證事實（例如S&P500 Equal Weight長期跑贏S&P500 Cap Weight），
理論解釋是Booth & Fama（1992）「diversification return」/「volatility
harvesting」——定期把權重拉回等權重，數學上等同於系統性「賣出漲多的、
買進跌多的」，只要成分股之間報酬不完全相關（有波動度、有相關係數<1），
這個機械式再平衡動作本身就會產生一個跟任何個股選股能力、任何市場擇時
能力都無關的正報酬來源，是純粹的**組合建構/再平衡算術**效應，不是
「這些股票比較會漲」也不是「這個時候比較該進場」。

**具體假設定義**：用既有`factor_ic.py`300檔快取樣本（`SAMPLE_SIZE=300`，
不做任何額外篩選、不依任何因子排序，直接用整個樣本池），月頻（或季頻）
重新平衡回等權重，比較「等權重＋定期再平衡」vs「同一組標的市值加權
（buy-and-hold，不再平衡）」的風險調整後報酬（Sharpe/CAGR/MDD），以及
跟`f_low_vol`/`f_bab`已FAIL教訓一致的**beta拆解**（若等權重組合的beta
顯著偏離1.0，代表贏的是隱含的規模/風格傾斜而非真正的再平衡溢酬本身）。

**已知相關背景（誠實揭露，避免跟已測項目混淆）**：這條**不是重新測試
`f_low_vol`/`f_bab`**（那兩者是「用波動度/beta排序挑股票」，本質仍是
①方向性選股排序）；也**不是`#15`波動度目標化的重測**（`#15`是「調整
單一標的（TAIEX）自身的曝險大小隨時間變化」，屬於②timing overlay，這條
是「同一時間點上，如何在N檔股票之間分配固定的總曝險」，時間維度上不
做任何調整、全程固定滿倉）。跟`#27`多因子z-score複合評分也不同——`#27`
的權重差異來自因子分數（仍是選股排序的變體），這條的等權重是**不依賴
任何因子分數**的機械式规则（宇宙裡的每一檔都給一樣的權重）。

**下檔保護要求（依`CLAUDE.md`最高投資原則第9關）**：deep_dive階段須
額外檢查等權重組合在3個已知歷史危機期間（2018Q4貿易戰急跌/2020Q1新冠
崩盤/2022全年空頭）的MDD、beta穩定度是否優於或至少不劣於市值加權基準
——等權重理論上對小型股曝險更高，危機時流動性風險/波動可能反而放大，
不能假設這個機制天生下檔安全，要實測驗證。

**資料可行性**：不需要任何新的API呼叫或新資料工程，直接複用
`factor_ic.py`既有300檔快取樣本的日頻價格（已被`#11`/`#17`/`#28`等多條
反覆驗證可行），符合資料源禮儀。

**狀態（2026-09-04排隊中，尚未開始第1關）**：這輪工作單位到此為止（依
協定「一輪只做一個有界工作單位」——本輪已完成依賴重新查證+此新假設
設計，不在同一輪展開第1關sanity），下一輪從第1關sanity開始（先確認
等權重再平衡後的組合報酬序列非退化、再平衡確實有觸發、跟市值加權基準
的差異方向符合預期），比照本佇列既有GATE_SEQUENCE，不跳關。

**狀態（2026-09-04接續排程，第1關sanity：PASS，非最終判定）**：新增
`equal_weight_rebalance_sanity.py`。**基準操作化誠實偏離揭露**：上面
「經濟理由」段落原文基準是市值加權買進持有，但本專案查證過`factors.py`
/`universe.py`/`adjust.py`都沒有市值/流通股數資料源，且本節「資料
可行性」段落原文承諾「不需要任何新的API呼叫或新資料工程」——兩者互相
矛盾，本輪選擇遵守後者不新增資料工程，基準改為**「同一組標的、t0等
權重起跑、之後永不主動調整的純buy-and-hold」**，不是市值加權（理由見
腳本docstring：這樣才乾淨隔離「再平衡動作本身」的效果，不混入等權vs
市值加權的額外規模傾斜，避免重蹈`f_low_vol`/`f_bab`已死教訓的覆轍）。
沿用`factor_ic.py`既有300檔快取樣本（SEED=20260822，跟#11/#17/#28
共用同一個宇宙），234/300通過最低歷史長度門檻，視窗頭尾涵蓋度篩選後
剩159檔組panel（2015-01-02..2024-12-31，2498交易日——**這個篩選隱含
存活者偏差，是sanity階段刻意簡化，非最終判定會用的處理方式，已在
腳本docstring誠實揭露**）。結果：再平衡事件118次（21交易日一次，
跟理論值完全一致）、拉回前權重離散度均值0.00068（>0，確認再平衡不是
no-op）、NaN/Inf檢查皆0（非退化）。TRAIN(2015-2020)：buyhold總報酬
+66.14%(Sharpe+0.691,MDD-29.08%) vs rebalanced+90.95%(Sharpe+0.912,
MDD-28.47%)，溢酬+24.81pp；VAL(2021-2024)：buyhold+83.58%(Sharpe
+1.037,MDD-18.70%) vs rebalanced+115.29%(Sharpe+1.379,MDD-17.01%)，
溢酬+31.72pp——**兩期方向一致（rebalanced恆優於buyhold）、Sharpe/MDD
同步改善**，第1關sanity三項要求（非退化/方向不是反的/樣本數夠）皆過，
判**SANITY PASS，非最終判定**。**下一步（第2關隨機控制組）需要專屬
設計**：這條假設不是「股票排序」類，不能直接套用`factor_ic.py`既有的
「洗牌因子值vs報酬配對」null——初步構想是隨機化再平衡日曆相位（rebal
起始日offset隨機0~20天，N>=100draws）觀察溢酬量級是否穩定、或對300檔
宇宙bootstrap抽樣不同159檔子集觀察分布，具體設計留給下一輪執行前先
想清楚，不倉促套用不合適的null。完整見`TRIALS_LEDGER.md`#107、
`equal_weight_rebalance_sanity.py`（新增，可重複執行）、`MARATHON_LOG.md`
本輪心跳。**佇列#29尚未結案，接續第2關**。

**狀態（2026-09-04接續排程，第2關隨機控制組：CHEAP_PASS，非最終判定）**：
新增`equal_weight_rebalance_control_v1.py`。**這條假設專屬控制組設計**（不能
套用因子IC的洗牌null，理由見腳本docstring）：對sanity版本159檔panel做無放回
bootstrap，每次抽80檔子集，重跑同一套`REBAL_FREQ=21`再平衡規則，共N=100
draws（`MASTER_SEED=20260904`，可重現）。**事前綁定三項判準**：①hit_rate
(TRAIN且VAL同時為正)>=80%；②全池結果落在bootstrap分布10th~90th百分位；
③bootstrap中位數溢酬明顯>0。結果：TRAIN溢酬分布median=+23.47%（range
+11.25%~+36.31%）、VAL溢酬分布median=+30.34%（range+10.56%~+60.88%），
**100/100 draws（100%）TRAIN與VAL同時為正**、全池基準結果落在分布
TRAIN=57.0%ile/VAL=56.0%ile（接近中位數，非離群）、兩期中位數皆明顯>0。
三項判準全過，判**CHEAP_PASS**——效果在100次隨機股票子集組合下幾乎全部
穩健重現，不是靠特定159檔的運氣，支持這是Booth & Fama(1992)理論預期的
真正結構性機制。**這是本佇列迄今第2關通過方式最乾淨的案例**（不是邊緣
過關，是幾乎全部隨機配置都同向）。**佇列#29仍未結案**——下一步待接續第
3關（參數密集高原，例如`REBAL_FREQ`附近一整片窗口都要能過，不只21天單
一參數點）、第4關（成本/稅/滑價1x/2x/3x敏感度，等權重再平衡每月換手全部
159檔，換手成本可能不小，需要誠實計入）、第9關（下檔保護，等權重理論上
小型股曝險較高，3個已知歷史危機期間MDD/beta穩定度尚未驗證，是這條假設
最大未知風險）。完整見`TRIALS_LEDGER.md`#108、
`equal_weight_rebalance_control_v1.py`（新增，可重複執行）、
`MARATHON_LOG.md`本輪心跳。

**狀態（2026-09-04接續排程，第3關參數密集高原：PASS，非最終判定，補記
上一輪陳舊鎖檔留下的已計算成果）**：上一輪（`HYPOTHESIS_QUEUE_PROTOCOL.md`
排程）已新增`equal_weight_rebalance_plateau_v1.py`並跑完，但鎖檔陳舊
（211分鐘未更新）被本輪回收，本輪確認腳本與結果有效後補記文字（未重新
執行，`equal_weight_rebalance_plateau_v1_run.log`即上一輪產出，非本輪
重跑）。**事前綁定三項判準**（固定sanity版本159檔panel，對`REBAL_FREQ`
跑5~80交易日密集網格step=5共17個點，含原21天參數點）：①一整片門檻——
TRAIN與VAL溢酬同時為正的比例>=70%；②非孤立尖峰——最長連續通過區段
>=5個網格點；③原21天參數點本身須落在通過範圍內。結果：**17/17個網格點
（100%）TRAIN與VAL溢酬同時為正**（範圍TRAIN+23.44%~+36.65%、VAL
+28.48%~+37.11%，全部落在正值區間、無孤立尖峰無斷裂），最長連續通過
區段=17點（涵蓋整個5~80日網格），21天原始參數點（TRAIN+24.81%/VAL
+31.72%）本身落在高原正中央附近，非邊緣僥倖值。三項判準全過，判**PASS**。
**這是本佇列29條假設中第3關通過方式最乾淨的案例**——不只是「多數點過」，
是整個5~80交易日（約週頻到季頻）網格無一例外，強力支持這是Booth & Fama
(1992)理論主張的、對再平衡頻率不敏感的結構性機制，不是21天這個特定選擇
的偶然巧合。完整見`TRIALS_LEDGER.md`#110、
`equal_weight_rebalance_plateau_v1.py`（新增，可重複執行）、
`equal_weight_rebalance_plateau_v1_run.log`、`data/
equal_weight_rebalance_plateau_v1_grid.csv`（gitignored，17點明細）、
`MARATHON_LOG.md`本輪心跳。**佇列#29仍未結案**——下一步第4關成本/稅/
滑價敏感度。

**狀態（2026-09-04同輪接續，第4關成本/稅/滑價1x/2x/3x敏感度：三情境皆
維持正溢酬，非最終判定）**：新增`equal_weight_rebalance_costs_v1.py`——
沿用`long_only_vs_market.py`既有turnover成本慣例（`cost = turnover ×
validation.costs.round_trip_cost_pct() × cost_multiplier`，不重造成本
模型），turnover定義為每次再平衡前個股權重相對1/n絕對偏離量總和除以2
（標準單邊換手率），對`rebal_ret`路徑逐日扣費（buyhold路徑除t0外不交易，
不額外收費，沿用sanity/第2/3關同一比較基準慣例）。結果：118次再平衡
事件、累計turnover=3.920（每次事件平均換手率0.0332，對159檔等權重組合
而言換手幅度不大，因為權重漂移通常是漸進的）、單次1x round-trip成本率
0.6850%（含手續費雙腳＋證交稅0.3%＋滑價雙腳）。**淨溢酬（TRAIN/VAL）**：
1x：+21.85%/+29.32%；2x：+18.93%/+26.95%；3x：+16.06%/+24.60%——
**三個情境下TRAIN與VAL淨溢酬皆維持顯著為正**（3x保守情境下仍有超過
16pp/24pp的淨超額報酬），turnover成本遠不足以吃光diversification
return（相對於前3關算出的毛溢酬約+24.81%/+31.72%，3x成本情境僅侵蝕
約9pp/7pp）。依協定第4關「任一情境轉負就要誠實記錄」的反向檢查——沒有
任何情境轉負，無需揭露負面情境。**這不是最終PASS**——仍待第5關
leave-one-out（逐年拿掉最大貢獻年份，檢查終值是否過度集中在少數年份，
`fut_basis_carry`#35→#37的教訓）、第6關逐年一致性、第7關樣本外（這條
假設的train/val切分其實跟前面幾關共用同一套，需要另外設計獨立於train/
val之外的樣本外檢驗方式，或明確論證sanity/第2/3/4關的train/val劃分已
足夠嚴謹）、第8關前向paper、第9關下檔保護（等權重理論上小型股曝險較高，
3個已知歷史危機期間MDD/beta穩定度仍是本假設最大未知風險，尚未驗證）。
完整見`TRIALS_LEDGER.md`#111、`equal_weight_rebalance_costs_v1.py`
（新增，可重複執行）、`equal_weight_rebalance_costs_v1_run.log`、
`data/equal_weight_rebalance_costs_v1_grid.csv`（gitignored）、
`MARATHON_LOG.md`本輪心跳。**佇列#29仍未結案，接續第5關leave-one-out**。

**狀態（2026-09-04接續排程，第5關leave-one-out：PASS，非最終判定）**：新增
`equal_weight_rebalance_leave_one_out_v1.py`——只測TRAIN期（開發期探索，不動
VAL），用毛報酬（沿用sanity/第3關同一口徑，不是第4關已扣成本版本，理由是這關
檢查的是「效果是否結構性集中在少數年份」，跟成本無關的獨立問題）。把TRAIN
期(2015-2020,6年)依日曆年切開，buyhold與rebalanced兩條路徑各自年度內獨立
複利，年度溢酬=兩者年度total_return相減（不是同一序列內部相減）。**事前
綁定判準**：拿掉溢酬貢獻最大的年份後，剩餘複利溢酬仍需>0。結果：逐年溢酬
2015+0.28%、2016-0.05%、2017+3.98%、2018+3.48%、2019-1.10%、2020+9.78%；
完整TRAIN複利溢酬+24.81%（跟第1/3關輸出完全一致，交叉確認腳本正確）；貢獻
最大年份=2020（+9.78%，占完整溢酬39.4%）；拿掉2020後剩餘複利溢酬
buyhold+36.03%/rebalanced+44.75%/**溢酬+8.72%，仍為正**，通過判準，判
**PASS**。跟`fut_basis_carry`（#35→#37，82倍放大集中在2000-2002三年、
拿掉後轉負）不同——本次效果不是靠單一年份撐起，2020年只占總溢酬約四成。
**附加診斷（非本關事前綁定判準，僅供第6關參考）**：目前只有4/6年年度溢酬
為正（2016/2019為負），若第6關套用「逐年一致性>=5/6」這個統一關卡門檻，
以TRAIN期單獨來看**目前是未達標的（4/6=66.7%<83.3%）**——這不是本關的
判定範圍（本關只看leave-one-out集中度，不看方向一致比例），但誠實記錄下來
避免下一輪誤以為第5關PASS代表第6關穩過。完整見`TRIALS_LEDGER.md`#112、
`equal_weight_rebalance_leave_one_out_v1.py`（新增，可重複執行）、
`equal_weight_rebalance_leave_one_out_v1_run.log`、`MARATHON_LOG.md`本輪
心跳。**佇列#29仍未結案，接續第6關逐年一致性——依上述附加診斷，TRAIN期本身
4/6年為正，下一輪需要正式（而非本輪順帶）套用統一關卡的逐年一致性判準（含
VAL期是否也要納入計算、跟既有案例如何比照），不能想當然爾判定，要留給下一輪
仔細處理，避免本輪順帶下結論。**

**狀態（2026-09-04同輪接續，第6關逐年一致性：FAIL，快殺結案）**：套用
`equal_weight_rebalance_leave_one_out_v1.py`第5關已算出的逐年溢酬數據
（TRAIN期2015-2020逐年獨立回測，跟`f52w_high_gates.py`/`spillover_
overlay_v1.py`同一種「TRAIN期逐年方向計數」判準口徑，未另外重寫程式碼，
直接複用第5關輸出）：2015+0.28%、2016-0.05%、2017+3.98%、2018+3.48%、
2019-1.10%、2020+9.78%。正報酬年度2015/2017/2018/2020共4年，負報酬
年度2016/2019共2年——**4/6=66.7%，未達事前訂定的>=5/6=83.3%門檻**，
判**FAIL**。依協定「快殺標準」（第6關逐年一致性未過，同`f_52w_high_prox`
#17、`spillover_overlay_v1`#19兩個先例判法一致），第6關未過不進第7/8/9
關，**佇列#29最終判定：FAIL**。

**誠實記錄，不是流程錯（依`CLAUDE.md`復盤原則）**：這條假設走完第1~5關
全數PASS（sanity、隨機控制組bootstrap N=100 CHEAP_PASS、參數密集高原
17/17點、成本敏感度三情境皆正、leave-one-out拿掉最大貢獻年仍為正），
是本佇列29條假設中通過關卡數最多、死得最深的案例之一——不是流程有錯，
是這個具體159檔樣本/2015-2020窗口下，diversification return雖然存在
且不集中在單一年份，但年度方向本身不夠一致（2016/2019兩年為負），依
跟`f_52w_high_prox`（#17）、`spillover_overlay_v1`（#19）同一把尺的
第6關門檻，誠實判不及格。

**不泛化成什麼**：不泛化成「等權重再平衡/diversification return這個
機制在台股完全無效」——第1~5關已扎實證明效果存在、非隨機、非集中在
單一年份，死的只是「這個具體159檔快取樣本+2015-2020這個TRAIN窗口」的
逐年一致性不夠。未來若要重測，值得先嘗試VAL期(2021-2024)逐年一致性是否
更穩（VAL期報酬本身更平順，Sharpe更高於TRAIN），或擴大樣本池到全市場
而非300檔快取子集，但這是未來獨立測試的變體，不是本次結果的一部分。

完整見`TRIALS_LEDGER.md`#114、`STRATEGY_GRAVEYARD.md`、
`equal_weight_rebalance_leave_one_out_v1.py`與其輸出（第6關直接複用第5關
已算出的逐年明細，未新增腳本）、`MARATHON_LOG.md`本輪心跳。**佇列#29
已結案：FAIL，移出排隊佇列，佇列#1~29全數結案。剩餘#5/#6/#8/#10仍卡
外部依賴（狀態沿用本條目最上方2026-09-04查證結果，本輪未重新查證），
下一輪需先確認依賴是否解鎖，若仍未解鎖則佇列實質已空，依協定第1節
設計新假設軸。**

---

### 30. 個股融資使用率（Margin Financing Utilization Ratio）—— 強制平倉/流動性螺旋風險訊號

**依賴重新查證（本輪，2026-09-04接續排程）**：`BACKLOG.md`第698/1142行
`value_board_v2`（B24-500）仍標「回測未通過」，題材動能榜/未來性濾網
（第1289/1291行附近）仍標「紙上交易中」，均與#29查證結果一致、無新
進展。確認**#5/#6/#8/#10四項依賴依然全部卡住**，佇列實質已空，依協定
第1節設計新假設軸。

**經濟理由（跟前29條在機制分類上真正不同的第五類）**：本佇列前29條
可歸為四大類——①**方向性選股排序**（原始/剝離beta動量、產業內RS、
營收驚喜、籌碼連續性、低波動/低beta、52週高點、多因子z-score等10條，
全部是「排序挑股票、預期會漲」）、②**timing/exposure overlay**（CTA、
vol-targeting、美股隔夜外溢、融資餘額成長率、市場廣度、regime overlay
方法論，全部是「決定整體要不要持有/持有多少」）、③**portfolio
construction**（等權重再平衡，#29，「同一組標的怎麼分配權重」，不涉及
選股或timing）、④**配對交易均值回歸**（#16，market-neutral價差收斂）
——四類在這個專案裡全數FAIL或卡在候選不足。這條測的是**第五個正交
維度：強制平倉/流動性螺旋（forced liquidation / margin spiral，
Brunnermeier & Pedersen 2009的funding liquidity機制）**——個股融資
餘額佔融資限額的比例（融資使用率）越高，代表越多散戶用槓桿持有該
股票，一旦股價開始下跌，維持率不足會觸發券商追繳/斷頭賣壓，這種賣壓
是**流動性驅動而非資訊驅動**（不是市場認為公司變差了才賣，是被迫
平倉），會在下跌時產生自我強化的額外賣壓（下跌→維持率降→斷頭賣出→
股價更跌→更多人斷頭），這是台股市場實務上非常有名的現象（「斷頭」
是台股散戶文化特有語彙），也有對應的國際文獻基礎。**這條假設不是在
找「會漲的股票」，是在找「危機時特別危險、該優先避開或降曝險的
股票」**，直接對應`CLAUDE.md`最高投資原則「資本保全優先」跟「regime
危機情境要降曝險」的精神，但作用在**個股層級**而非市場整體層級（跟
#10市場regime擇時overlay是互補角度：#10是市場整體開關，這條是個股
層級的危險名單篩選）。

**具體假設定義**：用FinMind`TaiwanStockMarginPurchaseShortSale`既有
欄位計算「融資使用率」=`MarginPurchaseTodayBalance / MarginPurchase
Limit`（融資今日餘額/融資限額，當日盤後公布即為PIT日期本身，不需要
延遲假設，比照`f_inst_flow`同樣的PIT處理慣例）。第一步（第1關cheap
IC gate）：跨橫斷面排序，測「融資使用率」對未來N日報酬的Spearman
IC，**事前綁定方向為負**（融資使用率越高，未來報酬越差）——這跟
本佇列其他因子「正向排序做多前段班」的邏輯相反，是這條假設的核心
特徵。deep_dive階段（第2關以後）要額外測「下跌段vs上漲段」分組IC是
否有顯著差異——機制核心主張只在下跌段特別有效（上漲段融資使用率高
可能只是散戶追高的結果，不必然預測未來報酬），這個「條件式有效」的
檢驗留給後續關卡，第1關cheap gate先建立unconditional IC的基礎訊號
存在性。

**已知相關背景（誠實揭露，避免跟已測項目混淆）**：跟`#26`全市場融資
餘額成長率（Aggregate Margin Debt Growth，已FAIL）不同——#26是**市場
整體時間序列**的槓桿水位當**擇時/regime**訊號（決定整個市場曝險要不
要降），這條是**個股橫斷面**的融資使用率當**篩選/排序**訊號（決定
哪些個股該避開），粒度跟用途都不同，不是同一個機制換皮（跟`#12`BAB
相對市場regime overlay的區隔道理相同）。跟`#13`台股三大法人連續買超
（已FAIL）也不同——那是**法人**（機構/資訊優勢方）的**連續性**買賣
行為，這條是**散戶**（透過融資槓桿）的**槓桿水位**，投資人族群跟
訊號性質都不同。這是本佇列第一次測試「強制平倉/流動性驅動賣壓」這個
機制類別，不是既有任何一條的變體。

**資料可行性查證（本輪已確認可行）**：curl直接測試FinMind
`TaiwanStockMarginPurchaseShortSale`（`stock_id=2330,
start_date=2015-01-01`）確認涵蓋2015年至今完整歷史（本專案TRAIN
2015-2020/VAL 2021-2024兩期窗口皆有資料），欄位包含
`MarginPurchaseTodayBalance`（融資今日餘額）跟`MarginPurchaseLimit`
（融資限額），可直接算出使用率比例，沿用`factor_ic.py`既有300檔快取
宇宙+cross-sectional IC框架即可，**不需要新的資料工程或等待回補**
（跟`#26`當時需要662週回補不同，這條的資料源本身就已經是逐日歷史
齊全，不是即時快照類端點）。**旁註（凍結區唯讀查證，未改動任何檔案）**：
`alpha-data`凍結區`config.py`裡的`twse_margin`資料源用的是TWSE
`MI_MARGN`端點，查證`alpha.db::raw_records`發現這個端點**只回傳當日
快照、目前只累積約2週歷史（2026-08-21起）**，不適合拿來測試——這條
假設改用`factor_ic.py`既有的FinMind API直接查詢路徑（跟其他因子測試
同一條資料路徑），不改動`alpha-data`凍結區任何檔案，這是本輪查證過程
中額外發現、記錄下來避免下一輪誤用`twse_margin`原始表格當作歷史資料源。

**下檔保護要求（依`CLAUDE.md`最高投資原則第9關，這條假設特別相關，
因為它本身就是下檔保護機制的候選）**：deep_dive階段除了一般
GATE_SEQUENCE，要額外測試在3個已知歷史危機期間（2018Q4貿易戰急跌/
2020Q1新冠崩盤/2022全年空頭）高融資使用率股票是否確實跌得比低使用率
股票更深——這是這條假設「有沒有用」的最關鍵證據，比一般時期的
unconditional IC更重要，不能只看平均IC就下結論。

**狀態（2026-09-04本輪排程，新假設軸設計完成，尚未開始第1關）**：這輪
工作單位到此為止（依協定「一輪只做一個有界工作單位」），未寫任何
因子/測試程式碼。下一輪從第1關cheap IC gate開始（比照`factor_ic.py`
既有框架新增`factor_ic_margin_utilization.py`，300檔快取宇宙，
train/val正負號一致+null percentile>=90.0門檻三項判準），不跳關。

**狀態（2026-09-04接續排程，第1關：CHEAP_PASS）**：新增
`factors.py::_margin_utilization()`（FinMind
`TaiwanStockMarginPurchaseShortSale`，`MarginPurchaseTodayBalance/
MarginPurchaseLimit`，當日盤後公布即pit_date，天然PIT-safe）+
`prepare_factors()`裡的`f_margin_utilization`（因子值保留原始比例、
不取負號，事前綁定方向為負）+`factor_ic_margin_utilization.py`
（新增，沿用`factor_ic.py`既有cross-sectional IC+洗牌null框架，
standalone bonferroni_n=1）。結果（300檔快取宇宙，248檔可用，121個
20交易日快照）：TRAIN mean_ic=-0.0293 IR=-0.166(n=74)、VAL
mean_ic=-0.0523 IR=-0.290 hit_rate=0.55(n=47)，**train/val同號（皆負，
與事前綁定方向完全一致）**、null percentile=100.0（門檻90.0，過關）。
**第1關CHEAP_PASS，非最終判定**——本佇列第五類機制（強制平倉/流動性
螺旋）第一次嘗試就過第1關，且方向跟假設核心主張完全吻合。**執行過程
記錄**：第一次嘗試（新資料源冷快取，300檔首次抓`TaiwanStockMargin
PurchaseShortSale`）逾600秒未完成，第二次重跑因FinMind快取已建立在
480秒內完成，非bug，是資料源冷啟動成本，下一輪重跑同樣300檔宇宙時
會更快。**下一輪（第2關）待辦**：隨機控制組（≥100 draws）、參數密集
高原、成本/稅/滑價敏感度、leave-one-out、逐年一致性、樣本外，
**deep_dive階段依上方「下檔保護要求」小節，額外測試3個已知歷史危機
期間（2018Q4/2020Q1/2022全年）高融資使用率股票是否確實跌得比低使用率
股票更深，這是這條假設核心主張的關鍵驗證，不能只看unconditional IC**。
完整見`TRIALS_LEDGER.md`#116、`MARATHON_LOG.md`本輪心跳條目。

**狀態（2026-09-04接續排程，deep_dive第一步：下跌段vs上漲段分組IC）**：
新增`factor_ic_margin_utilization_regime_split.py`（沿用`factor_ic.py`
既有`evaluate_factor()`/`build_snapshots()`，把#30既有121個20交易日快照
依TAIEX同窗口報酬正負分成down/up兩組，各自跑一次同一套IC+洗牌null框架，
全程零新網路請求、複用#116已快取資料）。結果：44個下跌段快照、77個上漲段
快照。**下跌段**：TRAIN mean_ic=-0.1394、VAL mean_ic=-0.1817 hit_rate=0.89、
train/val同號、null percentile=100.0。**上漲段**：TRAIN mean_ic=+0.0304、
VAL mean_ic=+0.0280 hit_rate=0.66、train/val同號但**方向翻正**、null
percentile=95.9。VAL期下跌段\|IC\|=0.1817遠大於上漲段\|IC\|=0.0280（約
6.5倍），跟上方「下檔保護要求」小節事前寫明的核心機制主張（機制只在
下跌段特別有效）完全吻合——unconditional IC（#116的-0.0293/-0.0523）
其實是被上漲段的弱正訊號稀釋過的結果，真實訊號集中在下跌段且強度遠
超unconditional版本顯示的程度。**這不是PASS/FAIL/CHEAP_PASS判定**（事前
已聲明這步驟是探索性佐證，44/77兩組樣本數比unconditional版本小很多，
統計檢定力較弱，不能單獨當最終判準），但方向一致、幅度懸殊，強力支持
下一步把這個因子操作化成**regime-conditional的個股避開篩選**（只在
市場轉弱時啟動，比照`regime_overlay.py`既有市場層級regime標籤機制，
但這次是個股篩選層級），而非單純恆定十分位多空。**下一輪待辦**：設計
具體regime-conditional portfolio層構造並走隨機控制組（≥100 draws）
等後續關卡，3個已知歷史危機期間（2018Q4/2020Q1/2022全年）個股層級
下檔保護驗證仍待完成。本輪工作單位到此為止（依協定「一輪一個有界
工作單位」）。完整見`TRIALS_LEDGER.md`#117、
`data/factor_ic_margin_utilization_regime_split_results.csv`、
`MARATHON_LOG.md`本輪心跳。`is_holdout_consumed()`本輪開工/收工前皆
確認`False`。

**狀態（2026-09-04接續排程，portfolio層構造已設計完成，第2/7關進行中，
尚未結案）**：新增`margin_utilization_regime_portfolio_v1.py`——**具體
設計（事前綁定，測試前寫死）**：沿用`regime_overlay.py`既有市場層級
regime判定（TAIEX 200日均線位階+20日波動度vs擴張窗中位數），危機regime
（`CRISIS_REGIME=("bear_below_ma","high_vol")`，跟`regime_overlay.
EXPOSURE_MAP`曝險最低那格對應）時，從流動性篩選後的候選池挑「融資使用率
最低」的TOP20檔（=避開最危險名單）；非危機regime時挑「流動性最高」的
TOP20檔（這條規則刻意跟融資使用率無關、且真實/隨機兩版本逐字相同，隔離
差異只可能來自危機期選股）。**隨機控制組核心判準是打贏『危機期隨機選股』
對照組，不是打贏買進持有大盤**——直接測試「危機時刻意挑低融資使用率
個股」相對「危機時隨機留在場內」有沒有加值，這是本佇列第一次用這種
「非危機期規則鎖定不變、只隔離危機期選股差異」的控制組設計（跟`#4`/
`#3`/`#17`的「同樣動作隨機挑N檔」控制組精神一致，但這裡額外鎖定了
regime切換的另一半，因為假設核心主張本來就是「只在危機時有效」）。
逐字比照`dividend_yield_portfolio_v1.py`checkpoint可續跑模式（`data/
margin_utilization_regime_portfolio_v1_checkpoint.json`，gitignored）。
**執行進度**：TAIEX TRAIN+VAL共3681個交易日，其中786天(21.4%)落在危機
regime（非系統性0天或全部，佔比合理）；300檔快取宇宙248檔可用。本輪內
連續呼叫腳本兩次（7分鐘+5分鐘算力預算），確認checkpoint機制正確接續
（第二次呼叫從第一次留下的進度接續，未重算已完成部分）。**TRAIN期真實
訊號回測+成本敏感度(1x/2x/3x)已完成**（1x報酬-16.97%、MDD-46.58%、
alpha-4.18%(p=0.7511不顯著)、beta+0.737，遠遜於同期買進持有+58.86%——
但這只是TRAIN期單一策略表現，尚未跟隨機控制組比較，不能單獨判讀），
**TRAIN期隨機控制組進度20/100（尚未跑完，不能判定）**，VALIDATION期
尚未開始。**尚未結案**——下一輪重新執行
`python research/margin_utilization_regime_portfolio_v1.py`會自動接續
TRAIN剩餘隨機控制組，完成TRAIN後接著跑VALIDATION，比照`#4`歷經多輪
checkpoint接續的先例，預估還需要數輪才能跑完並產出第2/7關判定。**留意
（不視為bug，記錄避免下一輪誤判）**：TRAIN真實訊號單獨表現不佳
（alpha不顯著、大幅落後買進持有）不代表這條假設會FAIL——因為判準是
相對「危機期隨機選股控制組」而非相對買進持有大盤，且非危機期的中性
流動性選股規則本身就不含任何alpha來源，全期間報酬本來就不預期贏過
放大曝險的買進持有大盤，只有等100筆隨機控制組跑完才能看percentile。

**狀態（2026-09-04接續排程，TRAIN隨機控制組進度30→40/100，操作教訓
記錄）**：本輪接手時上一輪留下的`hypothesis_queue`鎖檔已陳舊（60分鐘，
`marathon_lock.py`自動回收），推測上一輪呼叫結束時背景行程一併被終止，
跟`#4`T00:45條目記錄過的已知風險同一種模式。本輪用未加`run_in_background`
的方式呼叫腳本、觸發工具自身480秒逾時後「移到背景」，但**這個「移到
背景」的行程其實仍在存活執行**（非我原本誤判的「已結束」）——中途誤判
為已結束又額外啟動了第二個並行實例，一度造成兩個行程同時寫同一份
checkpoint的風險，本輪內立即發現（`ps -ef`交叉比對PID/啟動時間）並用
`kill -9`safely終止剛啟動、尚未寫入任何內容的第二個實例（確認其輸出
log為空、checkpoint數值未受影響），第一個行程繼續獨力運算。**教訓**：
之後對這類長時間腳本一律**明確使用`run_in_background: true`**啟動，
不要依賴工具逾時自動轉背景的隱性行為，且啟動前後都要用`ps -ef`確認
沒有同名腳本已在跑，避免重工/checkpoint競爭寫入風險。TRAIN隨機控制組
進度本輪確認為30→40/100（checkpoint每10筆落盤一次，`real`/`cost_returns`
兩期不變），第一個行程本輪結束前仍在繼續運算（可能已推進超過40，但
本輪未及等到下一次10的倍數落盤點就已收工），**仍未結案**。下一輪
`python research/margin_utilization_regime_portfolio_v1.py`會自動接續。

**狀態（2026-09-04T23:37接續排程，TRAIN隨機控制組進度70/100）**：本輪
接手時確認上一輪的行程已正常結束、無殘留背景行程，checkpoint顯示TRAIN
隨機控制組已到50/100（比上一則紀錄的40更新，代表上一輪收工後行程仍
存活了一段時間才自然結束）。用明確`run_in_background:true`啟動腳本
（480秒預算，`MURP_TIME_BUDGET_SECONDS=480`），等待行程自然結束後確認
checkpoint進度50→**70/100**（`real`/`cost_returns`維持不變，非重算）。
本輪480秒預算內達最大進度即收工，未觸及VALIDATION期。**仍未結案**，
`is_holdout_consumed()`收工前確認`False`。下一輪
`python research/margin_utilization_regime_portfolio_v1.py`會自動接續
TRAIN剩餘30筆隨機控制組，完成TRAIN後接著跑VALIDATION。

**狀態（2026-09-05接續排程，已結案：FAIL）**：接手時鎖檔已陳舊（29.8分鐘，
被回收），且發現有一個未受追蹤的既有背景行程仍在執行（推測是上一輪的
殘留，非本輪誤啟動），checkpoint已推進到TRAIN 100/100+VAL 10/100。本輪
繼續接續執行（過程中一度誤判行程結束又啟動第二個實例，發現後立即
`kill -9`安全終止未寫入任何內容的重複實例，checkpoint未受影響），最終
TRAIN+VAL兩期100/100隨機控制組全數跑完。**結果**：TRAIN return-16.97%、
alpha-4.18%(p=0.7512不顯著)、beta+0.737、random_control_percentile=
**1.0**（worse than 99/100隨機對照）；VAL return+65.20%、alpha+8.94%
(p=0.4991不顯著)、beta+0.638、random_control_percentile=**99.0**（表面
過90.0門檻）。依既有標準（alpha顯著性+beta拆解為最終判準）：VAL
percentile雖過關但alpha遠不顯著+顯著beta曝險，TRAIN期更是決定性反證
（worse than幾乎全部隨機對照，直接牴觸假設核心主張），判**FAIL**，未進
第3關以後。**不泛化成機制完全無效**——因子層cheap gate（#116）跟
下跌/上漲段分組IC（#117）方向皆與假設一致，死的是「TOP20純多方向、
regime二元切換」這個具體構造。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#120。**佇列#1~30全數結案**，重新查證#5/#6/#8/#10
外部依賴仍全部卡住（`BACKLOG.md`：`value_board_v2`仍`回測未通過`、
題材動能榜/未來性濾網仍`紙上交易中`，無新進展），佇列實質已空，下一輪
需依協定第1節設計新假設軸#31。

**狀態（2026-09-05T00:30接續排程，TRAIN隨機控制組已完成100/100，
VALIDATION進行中44/100，尚未結案）**：確認無殘留背景行程後，本輪內
連續呼叫腳本三次（明確`run_in_background:true`啟動，各480秒預算，
逐次等待自然結束再啟下一次，未同時並行）。**TRAIN隨機控制組
70→100/100（完成）**。**TRAIN真實訊號表現**：1x情境total_return=
-16.97%、MDD=-46.58%、Sortino=0.077、Sharpe=0.070、400筆交易、
alpha(年化)=-4.18%(p=0.7512不顯著)、beta=+0.737、成本敏感度1x/2x/3x=
-16.97%/-22.99%/-33.74%（三情境皆負）、同期買進持有大盤+58.86%。
**TRAIN隨機控制組（N=100，同樣『非危機期規則鎖定不變、只隨機化危機期
選股』對照組）終值mean=+0.40%，真實策略percentile=1.0**——遠低於
90.0門檻，且真實策略還輸給99%的隨機對照組，是本佇列至今percentile
最極端偏低的結果之一，暗示「危機時刻意挑低融資使用率個股」在TRAIN期
不但沒有兌現下檔保護、反而系統性劣於隨機選股（可能是低融資使用率
篩選同時篩掉了流動性/品質較好的標的，或TRAIN期危機regime判定跟實際
危機時點有落差）。接著啟動VALIDATION：真實訊號+成本敏感度(1x/2x/3x)
已計算完成，隨機控制組進度0→**44/100**。**仍未結案**——依協定判準
（隨機控制組percentile過關不夠，alpha顯著性+beta拆解才是最終判準）
需要VALIDATION完整跑完才能做綜合判定，但TRAIN這一項percentile=1.0已
是極強的負面訊號，大機率最終結果是FAIL。`is_holdout_consumed()`收工前
確認`False`。下一輪`python research/margin_utilization_regime_portfolio_v1.py`
會自動接續VALIDATION剩餘56筆隨機控制組，完成後即可產出最終第2/7關
判定。完整見`MARATHON_LOG.md`2026-09-05T00:30條目。

**補記（2026-09-05T01:04馬拉松第349輪，TW軌回收稽核，說明上面兩則
狀態條目的先後順序矛盾，非資料造假）**：上面「已結案：FAIL」條目與
本則（VAL 44/100，尚未結案）條目在檔案裡的文字順序看起來矛盾——
本則commit(`f58e421`)描述VAL僅44/100，卻排在已經聲稱VAL 100/100完成
的「已結案：FAIL」條目**之後**。核對`git log`發現原因：`f58e421`／
`68455c2`／`9fd0c0f`三個commit是由另一套**獨立、與這條`MARATHON_
PROTOCOL.md`馬拉松互不知情、對同一個checkpoint json無共享鎖**的
`hypothesis_queue`自動化系統寫入的，跟這條馬拉松的TW軌（含產出
「已結案：FAIL」文字的那個session）**同時**在呼叫同一支`margin_
utilization_regime_portfolio_v1.py`續跑同一份checkpoint，兩者交錯
執行導致文字記錄的先後順序跟實際完成時間點不一致，是race condition
的痕跡。**已核實不影響判定正確性**：最終checkpoint（`data/
margin_utilization_regime_portfolio_v1_checkpoint.json`，TRAIN/VAL
各100筆`random_finals`）與`data/margin_utilization_regime_portfolio_
v1_results.csv`數字完全吻合（TRAIN percentile=1.0／VAL percentile=
99.0），跟`TRIALS_LEDGER.md`#120、`STRATEGY_GRAVEYARD.md`記載一致，
FAIL判定成立。**佇列#30正式結案**，`HYPOTHESIS_QUEUE.md`本身不需要
再改動既有文字（append-only精神，不回頭改寫上面兩則）。**留給之後
處理的防呆缺口**（非本輪擅自修改，只記錄發現）：resumable checkpoint
腳本若同時被這條馬拉松跟`hypothesis_queue`系統呼叫會有寫入競爭風險，
之後若要修，應該讓兩套系統共用`marathon_lock.py`同一把鎖，或至少
讓checkpoint腳本自己偵測「非預期的進度跳躍」並中止示警，而不是靜默
覆寫。完整核實過程見`TW_LOG.md`第349輪記錄、`TW_MARATHON_STATE.md`
第349輪條目。

---

### 31. 台指選擇權Put/Call成交量比率當市場regime/擇時訊號

**依賴重新查證（本輪，2026-09-05 hypothesis_queue排程）**：`BACKLOG.md`
`value_board_v2`（B24-500）仍`回測未通過`、題材動能槜/未來性濾網仍
`紙上交易中`，與#29/#30查證結果一致、無新進展。**#5/#6/#8/#10四項依賴
依然全部卡住**，佇列實質已空，依協定第1節設計新假設軸。

**經濟理由（跟前30條在資訊來源上真正不同的第六類）**：本佇列前30條
用過的資訊來源全部是股票市場本身的資料（價格/報酬、成交量、財報、
三大法人籌碼、融資融券）。**選擇權市場的部位分布（Put/Call成交量或
未平倉量比率）是完全不同的資訊管道**——選擇權交易者（尤其法人）
的部位反映對未來波動/方向的看法，且選擇權市場常被認為有更知情的
參與者（Pan & Poteshman 2006發現選擇權成交量對股票未來報酬有預測力），
Put/Call ratio長期是市場情緒/避險需求的經典逆向指標（極端看跌部位
堆積常對應短期底部）。跟本佇列已測過的timing/overlay類假設（#10市場
regime overlay、#15波動度目標化、#19美股隔夜外溢、#26融資餘額成長率、
#28市場廣度背離，皮 FAIL或僅方法論框架）不同之處在於：那些全部只用
「標的自身」的價格/成交量/籌碼資料算出的訊號，這條第一次引入**衍生
性商品市場的部位資訊**當market regime判定的輸入，不是既有訊號換一個
計算方式。

**具體假設定義**：用FinMind`TaiwanOptionDaily`（`option_id=TXO`）逐日依
`call_put`欄位加總全履約價成交量，算出`put_volume/call_volume`比率，
排序或設定閘值（例如相對自身歷史窗口的百分位）判定市場
regime，套用在TAIEX（或未來若有選股候選）的曝險上——具體
閘值/窗口留待第1關前事前綁定，不在這裡先寫死避免未看資料
就湊參數。

**資料可行性查證（本輪已確認可行）**：curl測試FinMind
`TaiwanOptionDaily`（`option_id=TXO`,`start_date=2024-01-01`）確認
回傳逐日逐履約價逐call/put的成交量與未平倉量資料，欄位齊全（`date`/
`call_put`/`volume`/`open_interest`）。**下一輪待查**：TAIFEX選擇權
掛牌起始年份是否涵蓋TRAIN(2015-2020)+VAL(2021-2024)兩期全部窗口
（台指選擇權TXO自2001年即已掛牌，理論上涵蓋，但需在第1關實際
抳取時逐一確認2015年起資料完整，不能只驗證2024年單一切片就
假設全歷史齊全）。

**狀態（2026-09-05 hypothesis_queue排程，新假設軸設計完成，尚未開始
第1關）**：這輪工作單位到此為止（依協定「一輪只做一個有界
工作單位」），未寫任何因子/測試程式碼。下一輪從第1關CHEAP GATE開始
（先驗證2015年起逐日資料完整性，再算Put/Call比率對後續N日TAIEX報酬的
相關性/預測力，比照本佇列既有GATE_SEQUENCE，不跳關）。

**狀態（2026-09-05接續排程，第1關cheap gate：CHEAP_PASS）**：新增
`option_pcr_gate.py`（沿用`spillover_overnight_gate.py`#19同一套指數
層級時序相關性框架，Pearson+Spearman+N=500洗牌null，非cross-sectional
選股IC）。資料可行性確認：FinMind`TaiwanOptionDaily`(TXO)2015年起
逐日資料完整，但**發現一次跨10年抓取會讓FinMind回502 Bad Gateway**
（payload過大伺服器端逾時），改成逐年呼叫`load_dev`（仍是唯一sanctioned
entry point，只是分批呼叫，沿用其既有節流/重試邏輯）解決。**方法論
決定**：只採用`trading_session`==`position`（日盤）成交量計算PCR——
FinMind該欄位還有`after_market`（夜盤），但夜盤資料2017年年中才出現，
2015/2016僅有日盤，含入夜盤會讓訊號口徑在全期間內不一致，故排除，
全期間口徑一致。**時序對齊**：用第t日收盤後才完整可得的PCR（
put_volume/call_volume）預測第t+1日（次一交易日）台股close-to-close
報酬，不用來預測第t日自己的報酬（選擇權日盤13:45收盤晚於台股現貨
13:30收盤，保守起見不假設當日可用）。**結果**（對齊後n=2437）：
TRAIN(<=2020-12-31,n=1467) Pearson r=+0.0611(p=0.0193)、null
percentile=98.2；VAL(2020-12-31~2024-12-31,n=970) Pearson r=+0.0587
(p=0.0676)、null percentile=94.0。三項cheap gate判準（幅度非零/
train-val同號/VAL贏過洗牌null>=90.0）皆過，判定**CHEAP_PASS**——本
佇列第一次成功通過第1關的「新資訊來源類」假設（前29條timing/overlay
類假設中，只有#19美股隔夜外溢跟這條走到CHEAP_PASS，其餘多數第1關就
FAIL）。方向為正（PCR越高、次日台股報酬越正），事前未綁定方向對錯
（文獻本身對PC ratio是逆向/順向指標有分歧，不像#30融資使用率有明確
理論負號預期）。**只是第1關，不是最終判定**——比照#10/#19/#28的教訓，
接下來要走成本敏感度(第2/4關)、具體擇時規則portfolio層構造、逐年一致性、
alpha顯著性+beta拆解，任一關未過都要誠實判FAIL，不能因為第1關相關性
漂亮就預期一定會過。下一輪從第2關（隨機控制組，正式版N>=100）或直接
設計具體擇時規則（比照#19`spillover_overlay_v1.py`把CHEAP_PASS相關性
轉成具體exposure規則）開始，兩者皆可，由下一輪根據既有精神判斷。完整
數字見`TRIALS_LEDGER.md`#121、`data/option_pcr_aligned.csv`
（gitignored）。

**狀態（2026-09-05接續排程，第2/3關：已結案FAIL）**：新增
`option_pcr_overlay_v1.py`（沿用`spillover_overlay_v1.py`(#19)同一套
overlay/成本/隨機控制組框架，重用`option_pcr_gate.py`已產出的
`data/option_pcr_aligned.csv`快取，未重打FinMind API）——曝險規則：
`pcr_pctl`（PCR在trailing 250交易日窗口內的百分位排名，只用過去含當天
資料）低於30百分位時降曝險至0.3，否則維持1.0全曝險（跟已FAIL的#10/#19
同一個「單邊防禦型」量級，非優化結果）。結果：**TRAIN期防禦曝險天數
占比27.7%、VAL期30.8%**。TRAIN overlay總報酬**-36.91%** vs baseline
（買進持有）+55.93%；VAL overlay**-17.57%** vs baseline+59.73%——**overlay
在兩期都大幅跑輸買進持有**。第2關隨機控制組（打亂exposure時序，N=100）
TRAIN/VAL percentile皆=100.0（真實策略打贏幾乎全部隨機打亂版本），但這
只代表「這個防禦時機安排比隨機亂降曝險損失更小」，不代表贏過買進持有
本身——這是這條假設第一次出現「隨機控制組表面過關、但策略本身仍是
虧損且大幅跑輸基準」的組合，提醒之後deep_dive不能只看隨機控制組
percentile，要同時檢查絕對報酬相對基準的差距。**第3關參數密集高原
（threshold_pctl∈[0.10,0.40]×exposure_down∈[0.0,0.6]，49個網格點，
TRAIN期1x成本）：僅7/49點(14%)報酬為正，遠低於60%門檻，非一整片，
判定FAIL**，登錄門檻點(0.30,0.3)本身報酬為-36.91%。依協定第3關未過
直接結案，未進第5關以後。**死因判讀**：TRAIN(2015-2020)+VAL
(2020-2024)台股都是持續大多頭（買進持有各+55.93%/+59.73%），此overlay
在近三成交易日降曝險至0.3，機會成本在長多頭環境下遠大於任何危機情境
下的下檔保護，是防禦型overlay在持續多頭市場的典型失敗模式（跟#10
`f_rel_strength_regime_switch`、#19美股隔夜外溢deep_dive前若失敗會是
同一種死法家族，但#19實際走到gate5/6才知道結果，這條在gate3就被參數
高原直接攔下，比#19更早、更乾淨地被快殺）。**不泛化成「PCR訊號本身
沒用」**——第1關cheap gate的時序相關性（`TRIALS_LEDGER.md`#121）依然
CHEAP_PASS，死的是「trailing百分位排名+單一固定門檻+二元曝險切換」這個
具體overlay構造，未來若要重測建議改用連續曝險縮放（訊號強度按比例調整
曝險，而非二元切換）或改成更短的訊號視窗/更極端的門檻（例如只在PCR
處於歷史極端低位時才觸發，而非30百分位這種相對常見的水準），需要
獨立走完整GATE_SEQUENCE，不能沿用這次的具體實作當作「PCR overlay已經
測過」的證據。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#122、
`option_pcr_overlay_v1.py`（新增，可重複執行）、
`data/option_pcr_overlay_v1_run.log`、`MARATHON_LOG.md`本輪心跳。
**佇列#31結案——佇列#1~31全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（未
重新查證，跟#30/#29查證結果一致，無理由預期已解鎖），下一輪需依協定
第1節設計新假設軸#32。**

---

### 32. 美元兌台幣匯率當資金外流/市場壓力regime訊號

**依賴重新查證（本輪，2026-09-05 hypothesis_queue排程）**：`BACKLOG.md`
`value_board_v2`（B24-500）仍`回測未通過`、題材動能榜/未來性濾網仍
`紙上交易中`，與#29/#30/#31查證結果一致、無新進展。**#5/#6/#8/#10四項
依賴依然全部卡住**，佇列實質已空，依協定第1節設計新假設軸。

**經濟理由（跟前31條在資訊來源上真正不同的第七類）**：本佇列前31條
用過的資訊來源涵蓋股票市場本身資料（價格/報酬/成交量/財報/三大法人/
融資融券）跟選擇權市場部位（#31）。**這條第一次引入外匯市場的資訊**
——台幣兌美元匯率是台灣作為小型開放經濟體、外資持股占比高（台股外資
持股常年3~4成）市場的一個結構性壓力計：外資大舉撤出台股時，賣股所得
台幣需兌換回美元，會同時壓低台股（賣壓）跟壓貶台幣（換匯需求），兩者
是同一個資金外流動作的兩個可觀察面，文獻上新興市場貨幣貶值跟股市壓力
同步發生是有紀錄的現象（EM「雙殺」，股匯雙貶，尤其在risk-off情境）。
跟已測過的timing/overlay類假設不同之處：#10（大盤200日均線/波動度）、
#15（波動度目標化）、#19（美股隔夜報酬）、#26（融資餘額）、#28（市場
廣度）、#31（選擇權Put/Call比率）全部是「台股市場本身內部」的資料（
含跨市場的#19，用的仍是美股「股票市場」報酬而非匯率），這條是第一次
用「貨幣市場」的價格當regime判定輸入，經濟機制（資金流向）跟前面幾條
（動量崩潰/槓桿限制/避險情緒）也不同，不是同一個死掉機制換皮。

**具體假設定義**：用FinMind`TaiwanExchangeRate`（`data_id=USD`）逐日
即期匯率（`spot_buy`/`spot_sell`取中價或`spot_sell`單邊，事前綁定用
哪一個，第1關前決定），算台幣兌美元N日變動率（貶值方向為正），與後續
M個交易日TAIEX報酬做時序相關性（比照#19`spillover_overnight_gate.py`/
#31`option_pcr_gate.py`同一套框架：Pearson+Spearman+洗牌null）。事前
預期方向：台幣貶值幅度加大（匯率上升）應對應台股後續報酬轉弱（負相關），
若第1關方向跟預期相反要誠實記錄、不能事後改預期方向配合結果。

**資料可行性查證（本輪已確認可行）**：curl測試FinMind
`TaiwanExchangeRate`（`data_id=USD`）分別查2015-01-01起與2024-01-01起
兩個切片，皆回傳逐日`cash_buy`/`cash_sell`/`spot_buy`/`spot_sell`四個
匯率欄位，2015年初資料齊全（非2024年後才開始），涵蓋TRAIN(2015-2020)+
VAL(2020-2024)兩期全部窗口，非單一年份切片假設全歷史齊全（比照
`HYPOTHESIS_QUEUE_PROTOCOL.md`第2節「資料源禮儀」要求，需在第1關實際
抓取時逐年批次呼叫，避免像#31一次抓10年遇到FinMind 502逾時的教訓）。

**狀態（2026-09-05 hypothesis_queue排程，新假設軸設計完成，尚未開始
第1關）**：這輪工作單位到此為止（依協定「一輪只做一個有界工作單位」），
未寫任何因子/測試程式碼。下一輪從第1關CHEAP GATE開始（沿用
`option_pcr_gate.py`/`spillover_overnight_gate.py`同一套指數層級時序
相關性框架寫`fx_twd_gate.py`，逐年批次呼叫`TaiwanExchangeRate`避免
502，事前綁定匯率窗口N與預測窗口M、事前綁定方向預期為負相關，比照本
佇列既有GATE_SEQUENCE，不跳關）。

**狀態（2026-09-05第二輪排程，已結案：FAIL）**：新增`fx_twd_gate.py`
（沿用`option_pcr_gate.py`/`spillover_overnight_gate.py`同一套指數層級
時序相關性框架，逐年分批呼叫`TaiwanExchangeRate`避免502）——訊號=台幣
即期匯率`spot_sell`N(20)交易日變動率（事前綁定，貶值方向為正）、目標=
TAIEX後M(20)交易日報酬（事前綁定N=M=20，理由見腳本docstring：與既有
regime類窗口`regime_overlay.py`/`#28`同一量級）。結果（對齊後n=2388，
2015-02-02~2024-12-02）：TRAIN(<=2020-12-31,n=1439) Pearson
r=+0.0368(p=0.1634)、null percentile=82.6（未過90.0）；VAL
(2020-12-31~2024-12-31,n=949) Pearson r=-0.0723(p=0.0258)、null
percentile=96.0（過90.0，且方向符合事前綁定「台幣貶值→TAIEX轉弱」的
預期）。**但train/val正負號相反（TRAIN正/VAL負）**，第1關三項判準之一
未過，依協定直接結案，未進第2關以後。**不泛化成「股匯連動這個經濟機制
本身沒用」**——只測過`spot_sell`單一欄位+N=M=20交易日這組事前綁定的具體
窗口組合，未測其他匯率欄位或窗口長度，未來重測需換其中一個變體。跟已
FAIL的#9/#11/#13同一種「train/val方向不穩定」死法家族。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#123。佇列#32結案，佇列
#5/#6/#8/#10仍卡外部依賴（未重新查證，與#29~#32查證結果一致，無理由
預期已解鎖），下一輪需依協定第1節設計新假設軸#33。

---

### 33. 美國公債殖利率曲線（10Y-2Y利差）當全球風險regime訊號

**依賴重新查證（本輪，2026-09-05T03:23 hypothesis_queue排程）**：
`BACKLOG.md`第1159/1290行`value_board_v2`仍`回測未通過`、題材動能榜/
未來性濾網仍`紙上交易中`，與#29~#32查證結果一致、無新進展。**#5/#6/
#8/#10四項依賴依然全部卡住**，佇列實質已空，依協定第1節設計新假設軸。

**經濟理由（跟前32條在資訊來源上真正不同的第八類）**：本佇列已用過
股票市場本身（價格/報酬/量/財報/三大法人/融資融券/#29再平衡）、選擇權
市場部位（#31）、外匯市場（#32，台幣兌美元）三種資訊來源。**這條第一次
引入公債市場的資訊**——美國公債殖利率曲線（10年期減2年期利差）倒掛
是總經文獻裡最穩健的衰退領先指標之一（Estrella & Mishkin 1996，NY Fed
衰退機率模型的核心輸入），機制是市場對未來短期利率路徑的集體預期：曲線
倒掛代表市場預期央行未來會降息因應經濟走弱，反映的是**全球貨幣政策
預期**而非任何單一市場的部位或資金流向，經濟機制跟前面三種來源都不同
（不是資金流向如#32、不是部位傾向如#31、不是價格動能如#10/#28）。台灣
是高度依賴出口、外資持股占比高的小型開放經濟體，美國衰退風險升高時
（若曲線倒掛確實領先衰退），全球risk-off情緒同步壓抑台股本益比與資金
流入，機制路徑跟#19（美股隔夜報酬外溢）類似（都是美國市場資訊外溢到
台股）但**輸入訊號的市場類別完全不同**（債券殖利率利差 vs 美股股票
報酬本身），不是同一個資料源換皮。此外`C:\alpha\CLAUDE.md`已明確規劃
FRED總經資料整合（`fred_key.txt.txt`），這條假設是第一次真正動用這個
既有但尚未被任何假設使用過的資料源。

**具體假設定義**：用FRED`T10Y2Y`（10年期減2年期公債殖利率利差，日頻，
單位百分點，已直接是利差不需自行相減）當regime輸入，與後續M個交易日
TAIEX報酬做時序相關性（比照#19/#31/#32同一套框架：Pearson+Spearman+
洗牌null，事前綁定預測窗口M）。事前預期方向：**利差走低/轉負（曲線
趨平或倒掛）應對應TAIEX後續報酬轉弱（正相關，因為利差本身跟未來報酬
方向一致——利差降低=風險上升=報酬應該下降，所以利差水位本身應與未來
報酬正相關）**——這個方向定義要在第1關前寫進腳本docstring事前綁定，
不能事後配合結果調整。

**已知相關背景（誠實揭露，避免跟已FAIL的timing類別誤判為同一套）**：
跟已FAIL的#10（大盤200日均線/波動度）、#15（波動度目標化）、#19
（美股隔夜報酬）、#26（融資餘額）、#28（市場廣度）、#31（選擇權PCR）、
#32（台幣匯率）皆不同資訊來源；本佇列regime/timing類假設至今全數FAIL
（含#10方法論框架建置但未套用於任何候選），這條同樣可能複製同一種
死法（第1關cheap gate過但轉具體overlay後在成本/參數高原/逐年一致性
關卡死亡），需要誠實面對這個可能性，不因為經濟理由聽起來紮實就放鬆
判準。

**資料可行性查證（本輪已確認可行）**：curl測試FRED API`T10Y2Y`序列，
分別查2015-01-01起與2024-01-01起兩個切片，皆正常回傳日頻數值（含
負值，例如2024-01-02為-0.38，正確反映當時利差倒掛），2015年初資料
齊全，涵蓋TRAIN(2015-2020)+VAL(2020-2024)兩期全部窗口。金鑰已存在
`alpha-data/fred_key.txt.txt`（凍結區檔案，只讀不動），下一步實作時
需在研究腳本裡讀取金鑰、不得複製金鑰內容進任何會被commit的檔案或log。

**狀態（2026-09-05T03:23 hypothesis_queue排程，新假設軸設計完成，
尚未開始第1關）**：這輪工作單位到此為止（依協定「一輪只做一個有界
工作單位」），未寫任何因子/測試程式碼。下一輪從第1關CHEAP GATE開始
（沿用`fx_twd_gate.py`/`option_pcr_gate.py`同一套指數層級時序相關性
框架寫`fred_yield_curve_gate.py`，事前綁定預測窗口M與方向預期為正
相關，比照本佇列既有GATE_SEQUENCE，不跳關）。

**狀態（2026-09-05接續排程，第1關已結案：FAIL）**：`fred_yield_curve_
gate.py`（上一輪已寫好但陳舊鎖檔中斷未執行，本輪接續直接執行，未
重寫）執行完成，n=2320對齊配對（2015-01-05~2024-12-02）。結果：
TRAIN(<=2020-12-31,n=1406) Pearson r=**-0.0636**(p=0.0171)、null
percentile=98.6（過90.0門檻）；VAL(2020-12-31~2024-12-31,n=914)
Pearson r=**-0.0242**(p=0.4656)、**null percentile=52.8**（遠未過
90.0門檻，貼近50等同雜訊）。三項判準：幅度非零過、train/val同號
（皆負）過、**VAL贏過洗牌null未過**——三項判準之一未過，依協定直接
結案，未進第2關以後。**附註（非判準本身，但值得記錄）**：事前綁定
方向預期是利差水位與未來報酬正相關，實測兩期皆為負相關，方向本身也
與總經文獻預期相反，是本佇列少數「方向也錯+幅度也不顯著」雙重不
支持的案例。**不泛化成「殖利率曲線這個總經領先指標本身沒用」**——
只測過`T10Y2Y`水位單一口徑+M=20交易日這組事前綁定的具體窗口組合，
未測利差變動率（速度而非水位）、不同預測窗口、或「美國衰退預期→
全球risk-off→台股」這條傳導路徑本身可能需要的延遲。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#124。佇列#33結案，佇列
#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`仍未解鎖），依協定
第1節設計新假設軸#34（銅金比 Copper/Gold Ratio當全球成長/風險偏好
regime訊號，見下方新章節），現在排隊第一，尚未開始第1關。

---

### 34. 銅金比（Copper/Gold Ratio）當全球成長/風險偏好regime訊號

**依賴重新查證（本輪，2026-09-05 hypothesis_queue排程）**：
`BACKLOG.md`第1159/1290行`value_board_v2`仍`回測未通過`、題材動能榜/
未來性濾網仍`紙上交易中`，與#29~#33查證結果一致、無新進展。**#5/#6/
#8/#10四項依賴依然全部卡住**，佇列實質已空，依協定第1節設計新假設軸。

**經濟理由（跟前33條在資訊來源上真正不同的第九類——真實經濟需求，
非任何金融市場的部位/流向/預期）**：本佇列至今用過股票市場本身（價格/
量/財報/籌碼/融資融券/#29再平衡）、選擇權市場部位（#31）、外匯市場
（#32）、公債市場利率預期（#33）四種資訊來源，**全部是金融市場參與者
的部位或預期**，沒有一條直接測過「實體經濟供需」本身。銅（工業金屬，
需求跟全球製造業/營建/電子業景氣連動，故有「Dr. Copper博士銅」之稱，
市場長期視其為全球實體經濟活動的領先指標）對黃金（傳統避險資產，
需求跟風險趨避/停滯性通膨預期連動）的比值，是總經圈廣泛引用的「風險
偏好vs風險趨避」量化指標，機制跟殖利率曲線（#33，反映的是央行利率
路徑*預期*）本質不同——銅金比反映的是**當下實體工業需求的價格訊號**，
不是預期，也不是任何金融部位或資金流向。台灣是高度依賴電子/半導體
出口的小型開放經濟體，全球製造業景氣（銅需求的主要驅動力）走強時，
台灣出口訂單與台股企業獲利預期理論上應同步受益，機制路徑跟#19/#33
（美國市場資訊外溢到台股）類似（都是海外資訊外溢），但**輸入訊號的
市場類別完全不同**（工業金屬/貴金屬商品期貨比值，非股票報酬或利率）。

**具體假設定義**：用yfinance銅期貨（`HG=F`）與黃金期貨（`GC=F`）
收盤價比值（銅金比=銅價/金價）當regime輸入，與後續M個交易日TAIEX
報酬做時序相關性（比照#19/#31/#32/#33同一套框架：Pearson+Spearman+
洗牌null，事前綁定預測窗口M）。事前預期方向：**銅金比走高（銅相對
金上漲，代表市場風險偏好升溫/實體需求走強）應對應TAIEX後續報酬轉強
（正相關）**——這個方向要在第1關前寫進腳本docstring事前綁定，不能
事後配合結果調整。訊號口徑用**比值水位本身**（level），不是N日變動率
——理由跟#33相同：這是一個狀態性的風險偏好水位訊號，不是速度訊號，
訊號口徑要對應機制定義本身，不能機械套用同一種變動率公式。

**已知相關背景（誠實揭露，避免跟已FAIL的timing類別誤判為同一套）**：
跟已FAIL的#10（大盤200日均線/波動度）、#15（波動度目標化）、#19
（美股隔夜報酬）、#26（融資餘額）、#28（市場廣度）、#31（選擇權
PCR）、#32（台幣匯率）、#33（殖利率曲線）皆不同資訊來源；本佇列
regime/timing類假設至今全數FAIL（含#10方法論框架建置但未套用於任何
候選），這條同樣可能複製同一種死法（第1關cheap gate過但轉具體overlay
後在成本/參數高原/逐年一致性關卡死亡，或直接在第1關就沒過，比照#33），
需要誠實面對這個可能性，不因為經濟理由聽起來紮實就放鬆判準。

**資料可行性（本輪初步評估，尚未實際curl測試，下一輪第1關開工時
需先確認）**：`yf_price_client.py::fetch_yf_index()`已是本專案既有
基礎設施（`fx_twd_gate.py`未用它，但#10/#19等timing類假設的台股報酬
序列一貫用它取`^TWII`），理論上可直接傳入`ticker="HG=F"`/`ticker=
"GC=F"`取得商品期貨日頻收盤價，不需要新增資料源模組或新的API金鑰
——這點待下一輪第1關實際呼叫驗證（yfinance對商品期貨代碼的資料完整度
未經此專案驗證過，需要像#33查證FRED一樣先curl/試呼叫確認2015年起
資料無缺口）。

**狀態（2026-09-05 hypothesis_queue排程接續，第1關已完成：CHEAP_PASS）**：
資料可行性查證完成——`yf_price_client.py::fetch_yf_index()`直接傳入
`HG=F`/`GC=F`即可取得完整資料，實測`2015-01-02~2026-06-29`共2888/2887
筆、close無NaN、無>14天缺口，不需要新增資料源模組或新API金鑰（原本的
疑慮已排除）。新增`copper_gold_ratio_gate.py`（沿用`fred_yield_curve_
gate.py`/`fx_twd_gate.py`同一套指數層級時序相關性框架，訊號用比值水位
本身，M=20交易日預測窗口）。**結果**：對齊後總配對數n=2330（
2015-01-05~2024-12-02），TRAIN(<=2020-12-31,n=1413) Pearson r=-0.2467
(p<0.0001)、null percentile=100.0；VAL(2020-12-31~2024-12-31,n=917)
Pearson r=-0.1758(p<0.0001)、null percentile=100.0——三項cheap gate
判準（幅度非零/train-val同號/VAL贏過洗牌null≥90.0）全數通過，判
**CHEAP_PASS**。**必須誠實記錄的異常**：事前綁定方向預期是銅金比走高
（風險偏好升溫/實體需求走強）對應TAIEX後續報酬轉強（正相關），實測
兩期皆為**負相關**，且|r|量級（0.18~0.25）遠高於本佇列同類cheap gate
（#32台幣匯率|r|0.02~0.07、#33殖利率曲線|r|0.02~0.06），代表這是一個
比之前幾條timing類假設都更強的統計訊號，但方向與「Dr. Copper博士銅→
全球製造業景氣→台灣出口/台股獲利」這條原始經濟敘事完全相反。**不下
定論、不強行圓一個新敘事**——依`fx_twd_gate.py`/`fred_yield_curve_
gate.py`docstring既定原則，cheap gate判準本身不因方向不符預期而自動
判FAIL，但這個反轉必須帶著警示進下一關：真正的機制可能不是「全球
實體需求外溢」，而是銅金比與台股報酬同時被另一個共同驅動因子影響
（例如美元強弱、Fed政策預期同時牽動商品比價與新興市場股市），這需要
deep_dive才能釐清，此輪不猜測、不下定論。**尚未結案**——下一步（下
一輪）是轉具體overlay規則，比照#31/#32/#33同一套流程（固定門檻+二元
曝險切換）走第2關隨機控制組N=100，**規則方向必須依這輪實測的負相關
訂定（銅金比走高時降曝險、走低時維持曝險），不能沿用已被推翻的正相關
原始敘事方向**，否則等於明知錯誤方向還硬跑一個注定失敗的具體規則，
浪費一輪工作單位。完整見`TRIALS_LEDGER.md`（本輪新增條目）、
`MARATHON_LOG.md`本輪心跳。

**狀態（2026-09-05接續排程，第2關以後已結案：FAIL）**：新增
`copper_gold_ratio_overlay_v1.py`（方向依實測負相關反轉：比值trailing
250日窗口百分位排名>0.70時降曝險至0.3，否則維持1.0）。TRAIN
(2015-2020,n=1507)防禦曝險天數占比23.2%、overlay總報酬僅+10.14%
（同期買進持有+52.41%，已跑輸基準）；第2關隨機控制組N=100，TRAIN/VAL
percentile皆=100.0；第3關參數密集高原49點中44點(90%)報酬為正——表面
雙雙過關。**但第5關leave-one-out揭穿**：TRAIN逐年報酬2015~2020為
-2.11%/+7.10%/+9.70%/-8.20%/+37.43%/-24.09%，複利總報酬+10.14%幾乎
全部由單一年份2019（+37.43%）貢獻，拿掉2019後剩餘複利總報酬翻負為
-19.85%。依協定第5關未過（原本為正、拿掉最大貢獻年份後翻負）直接快殺
判定**FAIL**，未進第6關以後，VAL期數字（overlay+124.09% vs baseline
+205.07%）不納入最終判定。**不泛化成「銅金比訊號本身沒用」**——第1關
cheap gate（本佇列timing類最強訊號）不受影響，死的是這個具體overlay
構造，訊號強度不等於構造穩健性。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#126、`MARATHON_LOG.md`本輪心跳。佇列#34結案，佇列
#5/#6/#8/#10仍卡外部依賴，設計新假設軸#35（見下方新章節）。

---

### 35. 賣出台指選擇權波動度風險溢酬（Volatility Risk Premium, VRP）

**經濟理由（跟前34條在機制類別上真正不同的第五類——不是①方向性選股
排序、②timing/exposure overlay、③portfolio construction、④配對交易
均值回歸、⑤強制平倉流動性訊號，是⑥結構性風險溢酬收取）**：選擇權
隱含波動度長期系統性高於後續實現波動度（variance risk premium，
Bakshi & Kapadia 2003等文獻），機制解釋是市場對尾部風險的保險需求
使買方願付溢價，賣方（保險提供者）長期能收取這個溢價——這不是「預測
方向」，是「結構性提供保險換取穩定收益」，經濟機制與前34條選股/擇時
假設完全不同類別。CBOE的PUT（賣現金擔保賣權指數）、BXM（買進並持續
賣出買權）等指數在美股長期文獻中都證實這個溢價存在。

**具體假設定義**：用台指選擇權（TXO）建立固定規則的賣方部位（例如
每月賣出價外賣權或作跨式空頭的簡化版本），比較其報酬與單純持有TAIEX
的風險調整後表現，核心檢定是「隱含波動度是否系統性高於後續已實現
波動度」（IV-RV spread，這是第1關最便宜的檢定，不需要真的建立選擇權
部位模擬就能先驗證）。

**已知相關背景**：跟#31（選擇權PCR，用的是成交量比率當方向性/regime
訊號）資料源相同（`TaiwanOptionDaily`）但機制完全不同——#31是用選擇權
市場的「部位分布」預測台股方向，這條是直接在選擇權市場本身「賣出保險
收取溢價」，不透過台股方向預測。

**狀態（2026-09-05接續排程，第1關已結案：FAIL，邊緣案例）**：資料
可行性已查證——`TaiwanOptionDaily`不含IV欄位，改用Brenner-Subrahmanyam
(1988)近似公式從ATM跨式價格反推（不需利率/股利假設）。新增`vrp_gate.py`
（月合約日盤、10~45天到期區間內最接近30天的合約、ATM履約價、每5交易日
抽樣降低序列相關）。結果：TRAIN（n=292）mean_spread=+1.19pp、median=
+2.01pp、pct(IV>RV)=74.0%、t檢定p=0.0004、Wilcoxon p=0.0000皆顯著；
VAL（n=190）mean_spread=+0.76pp、median=+1.75pp、pct(IV>RV)=63.7%、
**t檢定p=0.0595僅些微未過0.05**、Wilcoxon p=0.0002顯著。事前綁定三項
判準（幅度非零≥1pp兩期/train-val同號為正/t檢定+Wilcoxon皆p<0.05兩期）
中，VAL的幅度（0.76pp<1pp）跟VAL的t檢定（0.0595）皆些微未過，依協定
判**FAIL**，不做主觀裁量override。兩期中位數皆明顯為正、Wilcoxon兩期
皆顯著，暗示溢價可能確實存在但分布右偏（少數危機期RV暴衝壓低均值），
是VRP文獻本身描述的固有尾部風險特徵，非bug。**不泛化成「台股VRP完全
不存在」**——只測了ATM月合約+Brenner-Subrahmanyam近似+5日抽樣這組具體
實作，未測更精確的IV反推法/不同到期窗口/危機期拆解。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#127。佇列#35結案，接續佇列
第一順位#36（個股融券使用率/借券成本當知情放空者訊號）。

---

### 36. 個股融券使用率（Short Sale Utilization Ratio）當知情放空者訊號

**依賴重新查證（本輪，2026-09-05接續排程）**：`BACKLOG.md`第698/1142行
`value_board_v2`（B24-500）仍標「回測未通過」，題材動能榜/未來性濾網
仍標「紙上交易中」，均與上一輪查證結果一致、無新進展。確認**#5/#6/#8/
#10四項依賴依然全部卡住**，佇列實質已空，依協定第1節設計新假設軸。

**經濟理由（跟前35條在機制類別上真正不同——最接近的是#30融資使用率，
但方向與投資人族群相反）**：放空需要向券商借券，借券供給有限、需求越
高（越多人想放空同一檔股票）代表市場上有越多知情/悲觀投資人願意付出
借券成本去建立空頭部位——文獻上（Asquith, Pathak & Ritter 2005；
Cohen, Diether & Malloy 2007）已證實融券餘額/借券使用率高的股票，未來
報酬顯著較差，機制是放空者通常需要額外的資訊優勢或研究成本才會承擔
放空的不對稱風險（下檔有限、上檔理論無限），高使用率是「知情悲觀者
集中出現」的訊號。**跟#30的關鍵區別**：#30測的是**融資**（散戶槓桿做
多、預期跌時被迫斷頭賣出——是流動性驅動的被動賣壓，方向預期為負是因
為「被迫平倉」邏輯）；這條測的是**融券**（放空者主動選擇放空、預期
本身就是看跌——是資訊驅動的主動訊號，方向預期同樣為負但機制原理完全
不同：一個是「散戶槓桿多頭最終引爆的賣壓」，一個是「放空者事前已經
掌握的資訊」）。兩者資料源同屬FinMind`TaiwanStockMarginPurchaseShort
Sale`但取用完全不同的欄位組。

**具體假設定義**：融券使用率 = `ShortSaleTodayBalance /
ShortSaleLimit`（融券今日餘額/融券限額，當日盤後公布即為PIT日期本身，
不需要延遲假設，比照#30`MarginPurchaseTodayBalance/MarginPurchase
Limit`同樣的PIT處理慣例）。第一步（第1關cheap IC gate）：跨橫斷面
排序，測「融券使用率」對未來N日報酬的Spearman IC，**事前綁定方向為
負**（融券使用率越高，未來報酬越差）。deep_dive階段（第2關以後）要
額外測「排除券資比失衡/融券強制回補風險股」（融券使用率接近100%時
可能面臨強制回補、走勢反而可能因軋空而上漲，這是台股實務上另一個
知名現象——需要跟「知情放空」的正常訊號區分開，避免同一個高使用率
區間混雜兩種相反機制），但第1關cheap gate先建立unconditional IC的
基礎訊號存在性，不在第1關就處理這個細節。

**已知相關背景（誠實揭露，避免跟已測項目混淆）**：跟`#30`個股融資
使用率（已CHEAP_PASS，尚未走完後續關卡）資料源相同但欄位/投資人族群/
機制完全不同（見上方經濟理由段落區隔說明），不是#30的變體換皮。跟
`#13`台股三大法人連續買超（已FAIL）也不同——那是**法人**（機構）的
**連續性買賣行為**，這條是**融券市場全體參與者**（含法人與大戶散戶）
的**借券使用率水位**，訊號性質不同。這是本佇列第一次針對「放空」這個
方向本身建立訊號（先前皆為做多排序或整體曝險調整），跟`#16`配對交易
（market-neutral價差收斂）雖然都涉及放空，但那是相對價值配對，這條是
單邊放空訊號，機制不同。

**資料可行性查證（本輪已確認可行）**：FinMind`TaiwanStockMargin
PurchaseShortSale`（跟#30同一端點）欄位除`MarginPurchaseTodayBalance`/
`MarginPurchaseLimit`外，本就含`ShortSaleTodayBalance`（融券今日餘額）
跟`ShortSaleLimit`（融券限額），可直接複用#30已驗證涵蓋2015年至今的
歷史資料，**不需要新的資料工程或等待回補**，沿用`factor_ic.py`既有
300檔快取宇宙+cross-sectional IC框架即可。

**下檔保護要求（依`CLAUDE.md`最高投資原則第9關）**：這條假設本身不是
下檔保護機制（不像#30是規避高風險股），是尋找alpha的放空訊號，若走到
portfolio construction階段（第4關成本敏感度以後），必須把放空可行性/
借券成本（融券手續費、可能的強制回補風險）計入交易成本敏感度測試，
不能只用做多端同等的成本假設，這是台股放空實務上的已知額外摩擦成本。

**狀態（2026-09-05 hypothesis_queue接續排程，第1關已完成：CHEAP_PASS）**：
新增`factors.py::_short_sale_utilization()`+`factor_ic_short_sale_
utilization.py`（比照`_margin_utilization()`/`factor_ic_margin_
utilization.py`#30框架），300檔快取宇宙248/300可用、121個20交易日
快照(2015-01-01~2024-12-31)。TRAIN mean_ic=-0.0163 IR=-0.094(n=74)、
VAL mean_ic=-0.0595 IR=-0.363 hit_rate=0.64(n=47)，**train/val同號
（皆負，與事前綁定方向一致）**，null percentile=100.0（門檻90.0，
過關）。三項判準（幅度非零/train-val同號/贏過洗牌null）全過，
**第1關CHEAP_PASS**，完整數字見`TRIALS_LEDGER.md`#129。**下一步
（第2關以後）**：隨機控制組（≥100 draws）、參數密集高原、成本/稅/
滑價敏感度（須依上方「下檔保護要求」把放空借券成本/強制回補風險
計入）、leave-one-out、逐年一致性、樣本外；**deep_dive須額外排除
「券資比失衡/融券強制回補風險股」**（融券使用率接近100%可能因軋空
反向上漲，與知情放空正常訊號機制相反），避免同一高使用率區間混雜
兩種相反機制。這輪工作單位到此為止（依協定「一輪只做一個有界工作
單位」），尚未進行portfolio層構造設計，下一輪從第2關隨機控制組開始，
不跳關。

**狀態（2026-09-05接續排程，第2關以後起跑，尚未結案：checkpoint進度中）**：
新增`short_sale_utilization_portfolio_v1.py`——**誠實揭露的範圍限縮**：
`backtest/engine.py`確認完全不支援放空/負權重（本輪查證，`grep -n short
backtest/engine.py`零匹配），這支腳本測的是訊號的**多頭鏡像半邊**（融券
使用率最低分位做多，對應「知情放空者最不感興趣的標的」應有相對較好的
未來報酬），**不是**完整驗證「賣空高使用率」策略本身——完整放空腿需要
引擎擴充後才能回答，尚未驗證，不能把這支腳本的PASS/FAIL直接當作對完整
放空策略的判定，見模組docstring完整說明。沿用`margin_utilization_
regime_portfolio_v1.py`同一套checkpoint可續跑架構（月頻TOP_N=20、
控制組=同池隨機選股、三成本層級）。**本輪執行結果**：TRAIN真實策略
報酬+59.53%（買進持有+58.86%，alpha年化+7.44%但p=0.3717不顯著）、
成本1x/2x/3x=+59.53%/+45.68%/+31.88%，隨機控制組跑到420秒時間預算
上限時進度16/100 draws（已checkpoint至`data/short_sale_utilization_
portfolio_v1_checkpoint.json`），**尚未跑完TRAIN 100 draws、VALIDATION
期完全尚未開始**，不做任何PASS/FAIL判定。`is_holdout_consumed()`
執行前後皆確認False。下一輪重新執行`python short_sale_utilization_
portfolio_v1.py`會自動從中斷處接續（不重算已完成的real/成本敏感度/
已完成的16個隨機draws），預估還需要多輪time budget才能跑完TRAIN+
VALIDATION各100 draws，這是`dividend_yield_portfolio_v1.py`/`margin_
utilization_regime_portfolio_v1.py`同一種「單輪時間預算跟完整計算量
有落差」情況，不是異常。

**狀態（2026-09-05 hypothesis_queue接續排程，同一輪工作單位）**：重新
執行`python short_sale_utilization_portfolio_v1.py`，420秒時間預算內
TRAIN隨機控制組記憶體內跑到29/100 draws，但checkpoint只在每滿10筆時
落盤，deadline在29時觸發，實際持久化進度為**20/100 draws**（下一輪會
從20接續、重算20~29這9筆，不是資料遺失，是既有checkpoint存檔頻率
設計，同`margin_utilization_regime_portfolio_v1.py`先例）。VALIDATION
期仍完全尚未開始，不做任何PASS/FAIL判定，`is_holdout_consumed()`執行
前後皆確認False。**佇列排隊順序仍是#36（未結案，接續第2關TRAIN隨機
控制組）**，這輪工作單位到此為止。

**狀態（2026-09-05T08:35 hypothesis_queue排程接續，同一輪工作單位，連續執行兩次script）**：重新執行`python short_sale_utilization_portfolio_v1.py`兩次，TRAIN隨機控制組持久化進度20→30/100 draws（第二次執行記憶體內達39/100但deadline在下一次落盤前觸發，實際持久化仍是30，跟先前輪同一種落盤頻率限制，非資料遺失）。VALIDATION期仍完全尚未開始，不做任何PASS/FAIL判定，`is_holdout_consumed()`確認為False。**佇列排隊順序仍是#36（未結案，接續第2關TRAIN隨機控制組，下一輪從30/100接續）**，這輪工作單位到此為止。

**狀態（2026-09-05T09:04 hypothesis_queue排程接續）**：重新執行`python
short_sale_utilization_portfolio_v1.py`一次，TRAIN隨機控制組記憶體內
進度30→49/100 draws，但deadline在下一次落盤前觸發，實際持久化進度為
**40/100 draws**（下一輪從40接續、重算40~49這9筆，跟先前輪同一種
落盤頻率限制，非資料遺失）。VALIDATION期仍完全尚未開始，不做任何
PASS/FAIL判定，`is_holdout_consumed()`執行前後皆確認False。**佇列
排隊順序仍是#36（未結案，接續第2關TRAIN隨機控制組，下一輪從40/100
接續）**，這輪工作單位到此為止。**（誠實補充：這輪的git commit+push
未完成就中斷，具名鎖`hypothesis_queue.lock`留下陳舊鎖檔，被下一輪
2026-09-05T09:23回收接手，內容經下一輪查證正確、隨下一輪進度一起
補commit，非資料遺失，見下一則狀態）**

**狀態（2026-09-05T09:23 hypothesis_queue排程接續，取鎖時發現LOCK_STALE
[held by 59452, 30.5 min old]自動回收，git status有上一輪(T09:04)已
staged但未commit的殘留——查證內容確認是本track自己上一輪合法產出（第2
關TRAIN checkpoint 40/100的正確紀錄），非其他排程來源，決定併入本輪
一起補commit）**：重新執行`python short_sale_utilization_portfolio_v1.py`
一次，TRAIN隨機控制組記憶體內進度40→59/100 draws，deadline在下一次
落盤前觸發，實際持久化進度為**50/100 draws**（下一輪從50接續、重算
50~59這9筆，跟先前輪同一種落盤頻率限制，非資料遺失）。VALIDATION期
仍完全尚未開始，不做任何PASS/FAIL判定，`is_holdout_consumed()`執行前後
皆以獨立`python -c`呼叫再次確認為False。**佇列排隊順序仍是#36（未結案，
接續第2關TRAIN隨機控制組，下一輪從50/100接續）**，這輪工作單位到此
為止。

**狀態（2026-09-05馬拉松第365輪，TW軌，取鎖乾淨非陳舊）**：**發現本條目
存在兩套獨立更新來源**——馬拉松30分鐘排程（`marathon.lock`）跟另一套
獨立系統（另一具名鎖`hypothesis_queue.lock`，本輪未查證其排程週期），
兩者都在推進同一份checkpoint、同一份本檔案，開工時checkpoint已是
50/100（對應上一則T09:23狀態），非馬拉松自己上一輪留下。連續執行
`python short_sale_utilization_portfolio_v1.py`兩次，TRAIN隨機控制組
持久化進度50→60→**70/100 draws**（兩次執行皆在420秒內完成本次落盤，
無中途deadline截斷）。VALIDATION期仍完全尚未開始，不做任何PASS/FAIL
判定，`is_holdout_consumed()`開工/收工前皆以獨立`python -c`呼叫確認為
False。零新增API呼叫（純本地快取讀取）。**佇列排隊順序仍是#36（未結案，
接續第2關TRAIN隨機控制組，下一輪從70/100接續）**，這輪工作單位到此
為止。
