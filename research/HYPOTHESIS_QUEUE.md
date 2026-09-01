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

**佇列狀態（2026-09-02更新）：#1 Weinstein已結案（FAIL）、#2 CTA已結案
（FAIL）、#3 PEAD已結案（FAIL）、#4股票股利率carry已結案（FAIL，alpha顯著性
未過，見下方條目與`STRATEGY_GRAVEYARD.md`）、#9殘差動量Residual Momentum
已結案（FAIL，第1關cheap IC gate train/val正負號不一致，見下方條目與
`STRATEGY_GRAVEYARD.md`）、#10市場regime擇時overlay方法論框架已建置完成+
sanity通過（非PASS/FAIL判定，工具就緒待未來候選套用，見下方條目）、#11
產業內相對強度Sector-Neutral Relative Strength已結案（FAIL，第1關cheap
IC gate贏過洗牌null分布這一項未過，percentile=82.8<90.0門檻，見下方條目
與`STRATEGY_GRAVEYARD.md`），目前排隊第一：#12 Betting-Against-Beta/低beta
（第1關sanity尚未開始）。**

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
本身的穩定性，不能只看表面排序報酬。

**狀態**：待起跑，第1關（sanity）尚未開始。

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

**狀態**：待起跑，第1關（sanity）尚未開始。

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

**狀態**：待起跑，第1關（sanity）尚未開始。

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

**狀態**：待起跑，第1關（sanity）尚未開始，可以獨立於選股類假設先跑，
不用等其他候選排隊。

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
7. 低波動（TW版策略層）——可直接沿用US的deep_dive方法框架。
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
12. **Betting-Against-Beta/低beta——現在排隊第一。** 2026-09-02新增，
    待起跑，第1關尚未開始。
13. 台股三大法人連續買超持續性——2026-09-02新增，待起跑，第1關尚未開始。
14. 台股月營收公布事件效應——2026-09-02新增，待起跑，第1關尚未開始。
15. 波動度目標化Vol-Targeting——2026-09-02新增，可獨立於選股類假設先跑，
    不用等其他候選排隊。

**B25/B26任務提醒（2026-09-02新增，跟上面九條假設是平行的另一個工作
項目，不是同一序列）**：`BACKLOG.md`已有完整規格「登記但尚未執行」——
B25（回測regime標記與分情境報告，套用在B24-500的value_board_v2結果上，
只做報告不做權重調整）、B26（B24報告補強：調整後Sharpe×0.5/×0.7+
CVaR(95%)）。這兩項工作對象是既有的B24-500報告，不是這份佇列的因子/
策略候選，跟Carry/#9~15不衝突、可以在Carry收尾後、佇列繼續往下跑#9之前
或之後任何空檔接續，去讀`BACKLOG.md`「B25」「B26」條目取得完整規格
（已經寫得很完整，不用重新設計）。
