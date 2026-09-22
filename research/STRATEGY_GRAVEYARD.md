# STRATEGY_GRAVEYARD.md — 策略墓園（2026-08-29新增）

**這份檔案存在的理由**：使用者裁示「每個負結果寫進`STRATEGY_GRAVEYARD.md`，
具體記『哪一點失效』，不泛化成『整類沒用』；墓園接進策略監控台，讓使用者看得到
挖過什麼、為何死」。

**寫入規則（鐵律）**：
1. **只記`research/HYPOTHESIS_QUEUE.md`佇列走完`GATE_SEQUENCE`後死掉的假設**
   ——不是隨便一個念頭沒驗證就放這裡，要走過至少sanity+隨機控制組才算數
   （比照`TRIALS_LEDGER.md`「已調查但不計入試驗數」的區分：純粹「調查後
   發現資料不可及」不算一次試驗，不放這裡，放`HYPOTHESIS_QUEUE.md`各條目
   自己的「已知相關背景」裡交代）。
2. **具體記「哪一關、哪一點失效」**，不能只寫「沒有肉」/「測試失敗」這種
   空泛結論——要能讓看的人明白是sanity不過、隨機對照組沒贏、成本吃掉優勢、
   樣本外反轉、還是下檔保護關卡沒過。
3. **不泛化成整類沒用**——例如`fut_basis_carry`死於「717x放大集中在
   2000-2002三年、樣本外沒有」，不能寫成「carry類機制在台指期沒有用」，
   下一個carry變體（例如均值回歸版本）仍然值得獨立測試，實際上
   `fut_basis_mean_reversion_60d`後來測出EXPERIMENTAL（比水位版證據更強），
   如果當初泛化成「carry沒用」就會錯過這個。
4. **禁止事後美化/淡化**——死亡原因照實寫，附上原始試驗編號/腳本路徑，
   讓人可以回頭查證原始數字，不是這裡重新摘要一遍就算數。

**跟`TRIALS_LEDGER.md`的關係**：`TRIALS_LEDGER.md`是**因子/策略層級**的
完整累積帳本（含PASS/FAIL/CHEAP_PASS/EXPERIMENTAL全部判定，供Bonferroni/FDR
多重比較校正使用，不能只挑FAIL的放這裡）——**這份檔案是`TRIALS_LEDGER.md`
FAIL/深挖後降級案例的策展摘要，給使用者/App策略監控台看的精簡版**，兩者
不是互斥關係：一個候選在`TRIALS_LEDGER.md`永遠有完整記錄，死掉之後才會
額外在這裡出現一筆精簡摘要。**這份檔案不是權威來源，`TRIALS_LEDGER.md`
才是**——如果兩邊數字對不上，以`TRIALS_LEDGER.md`為準。

## 條目格式（供之後串進策略監控台時用同一套schema解析，先手寫累積，
等真的有夠多條目再考慮寫解析腳本，避免為了0條目的檔案先建一支空腳本）

```
### <假設名稱>（<家族>，<陣亡日期>）

- **哪一關死的**：<GATE_SEQUENCE的第幾關，或「下檔保護」關>
- **具體數字**：<實際數字，不是「表現不好」這種形容詞>
- **這個死法能不能泛化**：<能/不能，為什麼——是機制本身的問題，還是
  這個特定實作方式的問題>
- **原始記錄**：<TRIALS_LEDGER.md編號/腳本路徑>
```

---

## 已知死亡模式索引（2026-09-15新增，設計新候選前先比對這裡）

**目的**：跟上面單條紀錄不同，這裡收的是**重複出現、跨多條假設共同的死法**
——設計新假設前先看這裡有沒有已知模式，值不值得先做便宜的事前估算再決定
要不要投入完整六關，不要每次都從零撞一次同樣的牆。

### 毛報酬有效、扣成本歸零（低頻切換型訊號的共同風險）

**首見案例**：`#243` TAIEX 200MA趨勢濾網regime overlay（2026-09-15
FAIL）——毛(未扣成本)MDD縮小28.8%（看起來快過35%門檻），扣除
`validation/costs.py`全額切換成本後只剩1.8%，門檻FAIL。**關鍵數字**：
年化切換8.4次、年化成本≈2.888%，幾乎吃掉基底CAGR（6.10%）本身。

**規則（往後任何低頻切換/擇時訊號適用）**：設計階段就要先估算「訊號
本身的切換頻率 × 單次切換成本」這個乘積，拿`2.888%/年（8.4次切換）`
當一個具體基準線參考——如果一個新訊號的年化切換次數落在同一個量級
（個位數到十位數/年）卻沒有明顯比200MA濾網更集中的economic edge，
成本吃掉大半毛利潤的風險就該在設計SPEC階段先寫出來、決定要不要真的
投入六關去測，不要等測完了才發現成本吃光。**這不是叫大家不要測低頻
切換訊號**，是要求把成本敏感度的估算提前到「值不值得測」這一步，而
不是只留在既有第4關「成本/稅/滑價敏感」事後才發現。

### 控制組(b)延遲一週方向翻轉＝前視偏誤跡象（regime類訊號標準關卡）

**首見案例**：同`#243`——訊號延遲1週後MDD反而從-20.46%惡化為
-37.84%（比基底買進持有更差），方向直接翻轉，不排除保護機制本身帶有
前視/擬合成分。

**規則（2026-09-15確認，即日起適用所有regime/擇時類訊號，不限這一條）**：
凡是「用某個判斷條件決定要不要降曝險」的regime overlay類訊號，
**控制組(b)（訊號整體延遲N期，通常1週）方向是否翻轉**都要當標準關卡
跑一次——這道檢查很便宜（沿用同一套回測管線，只是把訊號序列整體
shift），但對抓「保護機制本身其實是靠著未來資訊才顯得有效」非常有效，
不應該只在單一候選臨時想到才做，往後所有regime類候選的SPEC都要內建
這一項。
就已經累積的FAIL/深挖降級案例，補記在這裡方便App之後串接時有內容可顯示，
不是重新測試一遍）

### fut_basis_carry（basis carry水位版，期貨，2026-08-25深挖降級）

- **哪一關死的**：樣本外（GATE_SEQUENCE第7關）——便宜關卡/密集參數/成本
  敏感度全部通過，敗在train/val切分。
- **具體數字**：TRAIN期period-local配對式隨機控制組percentile=100.0；
  VAL期percentile僅46.0（連隨機控制組中位數都沒贏）。leave-one-year-out：
  拿掉2000/2001/2002三年，終值717.5x→107.9x（只剩15.0%），代表原本
  看起來驚人的717x有82倍放大主要由三個早期事件年份主導。
- **這個死法能不能泛化**：**不能**泛化成「basis carry在台指期沒用」——
  同一個basis資料源、換成均值回歸機制（`fut_basis_mean_reversion_60d`）
  測出EXPERIMENTAL（比這個水位版證據更強、beta更接近零），代表死的是
  「水位本身方向性押注」這個具體構造，不是「basis這個資料維度」本身。
- **原始記錄**：`TRIALS_LEDGER.md`#35/#37，`deep_dive_fut_basis_carry.py`。

### f_rel_strength_regime_switch（大盤位階開關+相對強度十分位多空，股票，2026-08-26 FAIL）

- **哪一關死的**：成本/稅/滑價敏感（GATE_SEQUENCE第4關）——分群IC層級
  方向正確，扣真實成本後TRAIN期全負。
- **具體數字**：TRAIN期三種成本情境(1x/2x/3x)：ann_return −6.82%~−9.22%
  全負、alpha −4.66%~−7.11%全負、Sortino −0.144~−0.233全負；VAL期
  1x成本微幅轉正(+0.50%)，2x/3x轉負，對成本高度敏感；beta由TRAIN+0.073
  升至VAL+0.191，market-neutral構造在VAL期較不成立。
- **這個死法能不能泛化**：**不完全能**——這個具體實作是「regime開關決定
  進出場」（空頭平倉觀望），死於「因子排序能力(IC)存在，但十分位/20日
  換倉的真實週轉成本吃掉優勢」，是這個特定持股構造（十分位、20日換倉）
  的問題，不代表「regime輪動」這個大方向沒用——`HYPOTHESIS_QUEUE.md`
  #5仍然把regime輪動排進佇列，改用「regime作為強制overlay套用在已過關
  候選上」而非「regime決定進出場的獨立策略」這個不同的機制設計。
- **原始記錄**：`TRIALS_LEDGER.md`#40，`regime_switch_f_rel_strength.py`。

### f_us_low_vol（美股低波動，深挖，2026-08-26 FAIL）

- **哪一關死的**：樣本外（GATE_SEQUENCE第7關）+ 下檔保護關（beta不受控）。
- **具體數字**：TRAIN期(2015-2020)十分位多空(k=3/腳,20日換倉)×1x/2x/3x
  ann_return −13.16%~−13.87%全負，對隨機控制組percentile僅41.0~48.0
  （連中位數都沒贏）；VAL期(2020-2024)表面轉強(+17.53%~+18.67%)，但
  beta驟降至−0.891（遠非市場中性）——代表VAL期的「轉強」是方向性反向
  曝險造成的，不是橫斷面排序優勢。
- **這個死法能不能泛化**：**部分能**——這個結果直接影響`HYPOTHESIS_QUEUE.md`
  #7（TW版低波動策略層）的設計：TW版必須在深挖階段特別檢查beta是否
  隨時間漂移，不能只看VAL期報酬數字轉強就誤判為訊號變強。
- **原始記錄**：`TRIALS_LEDGER.md`#39/#41，`deep_dive_f_us_low_vol.py`。

**2026-09-19更新（第557輪，家族正式結案）**：中型股tier（`TIER="mid"`）
的1b深挖同樣FAIL——cheap gate層N=30小樣本版（`TRIALS_LEDGER.md`#52
CHEAP_PASS）與N=90重跑版（#206 CHEAP_PASS，`CALIBRATION_PROBE.md`裁示
的最終複驗）都在簡單多空IC檢定過關，但兩次深挖（N=30版`TRIALS_LEDGER.md`
#68、N=90版本輪新增#245）TRAIN期percentile皆僅8~25（連隨機控制組中位數
都沒贏過），跟不分層版死法完全同款：cheap gate能過、策略構造層（十分位
多空、隨機控制組）一測就現形。至此`f_us_low_vol`在不分層、小型股tier
（#13）、中型股tier（N=30版#68／N=90版#245）三個樣本組合的1b深挖皆已
跑完皆FAIL，大型股tier cheap gate本身未過未進深挖——**因子家族全部
tier/樣本規模組合已窮盡，正式結案，不再開新變體**。原始記錄：
`TRIALS_LEDGER.md`#206/#245，`US_LEADS.md`#28/#33，
`deep_dive_f_us_low_vol_mid_tier_n90.py`。

### f_us_momentum_12m（美股12-1動能，US軌，2026-09-22第599輪盤點結案，FAIL）

- **哪一關死的**：cheap gate（GATE_SEQUENCE前置的1a便宜關卡，same_sign
  同號檢查／null percentile門檻），四個樣本規模組合全數未進入1b深挖。
- **背景**：round557已指出US軌候選池需回頭盤點「CHEAP_PASS但下一步從
  未執行」的遺漏（同一輪揪出`f_us_low_vol`中型股N=90深挖遺漏、補做後
  結案），本輪（第599輪）比照掃`US_LEADS.md`全表，發現這個因子家族雖
  然中型股tier N=30版（`TRIALS_LEDGER.md`#53，`US_LEADS.md`#8）曾判
  **CHEAP_PASS**、但從未被1b深挖，形式上跟`f_us_low_vol`中型股tier
  遺漏同款。查證後確認**不需要再投入新的深挖工作**，因為同一個
  cheap-gate換更大樣本（N=90）重跑後直接FAIL，已足以結案（見下）。
- **具體數字（四個樣本規模組合）**：
  - 不分層（27/40可用，`TRIALS_LEDGER.md`#44）：train mean_ic=−0.0129、
    val mean_ic=+0.0613，same_sign未過（train負val正）→**FAIL**。
  - 大型股tier：N=29版（#48）train正/val負、same_sign未過→**FAIL**；
    N=90版（`CALIBRATION_PROBE.md`裁示複驗，#204，78/90可用）train/val
    同號皆負但percentile僅73.5（門檻96.7）→**FAIL**。
  - 中型股tier：N=30版（#53，26/30可用）train mean_ic=+0.0119、
    val mean_ic=+0.0968，same_sign過、percentile=99.9→**CHEAP_PASS**
    （待深挖，`US_LEADS.md`#8信心等級標「低」，因三次不同樣本版本
    train/val方向組合互不相同，疑似小樣本雜訊）；**N=90重跑版**
    （#207，81/90可用，`us_factor_ic_by_size.py`同一次執行的附帶
    產出，非CALIBRATION_PROBE.md原始明列項目但依登記紀律入帳）
    train/val同號皆正但percentile僅**60.0**（門檻96.7，遠未過）
    →**FAIL**，`US_LEADS.md`#28已載明此結果並定性為「便宜關卡本身
    FAIL」。
  - 小型股tier：N=30版（#58，`US_LEADS.md`#11）train負/val正、
    same_sign未過→**FAIL**（僅測過N=30，未再重跑N=90——原始判定
    已是FAIL非CHEAP_PASS，依`CALIBRATION_PROBE.md`複驗規則不需要
    像中型股tier那樣為了解決「未定」而重跑更大樣本）。
- **死因分類**：中型股tier N=30的CHEAP_PASS被同一套方法論換更大樣本
  重跑後直接推翻——**用小樣本cheap-gate結果本身不可靠**（同一因子
  在27~30檔規模下四次測試出現三種不同的train/val正負號組合），而非
  「深挖階段構造層發現隱藏風險」。跟`f_us_low_vol`（cheap gate通過、
  但1b策略構造深挖才現形）死法不同層級：momentum連cheap gate本身
  換大樣本就不穩，是**檢定力不足＋樣本雜訊主導**，不是構造層的隱藏
  瑕疵。因此**不需要再投入1b深挖工作量**——用更大、雜訊更低的樣本
  重測cheap gate本身已經是比1b深挖更早、更省成本的否證。
- **這個死法能不能泛化**：不泛化到「12-1動能在美股無效」——
  Jegadeesh-Titman動能異常是文獻中最穩健的美股異常之一，這裡否決的
  只是「27~90檔隨機抽樣、未做regime控制、按市值tier分層」這個具體
  構造組合在本專案免費資料源上測不出穩定訊號，跟`f_us_low_vol`/
  `f_us_value_bm`（乾淨宇宙版）同款屬於「工具/樣本限制」而非「機制
  被推翻」。
- **原始記錄**：`TRIALS_LEDGER.md`#44/#48/#53/#58/#204/#207，
  `US_LEADS.md`#2/#5/#8/#11/#27/#28，`us_factor_ic.py`／
  `us_factor_ic_by_size.py`（皆可重複執行）。**因子家族全部
  tier/樣本規模組合已窮盡，正式結案，不再開新變體**。

### f_us_value_bm／f_us_low_vol 乾淨宇宙版本（US軌，round382-425，
9輪短腿診斷鏈整併結案，2026-09-07 FAIL）

- **哪一關死的**：資料完整性（非GATE_SEQUENCE任何一關的統計判準本身
  失敗——cheap gate、1b深挖、多個下檔保護與穩健性檢定全部「數字上」
  通過甚至過關到不合理的量級，死因是這些數字本身無法被驗證為現實中
  可執行的報酬）。
- **背景**：round382/383換用市值分層隨機抽樣（`us_stratified_universe_
  sample.py`）修正舊池子熱門股偏誤後，`f_us_value_bm`（book-to-market）
  與`f_us_low_vol`（60日波動負號）兩因子cheap gate皆清楚過關
  （percentile 100.0），1b深挖（`TRIALS_LEDGER.md`#163）VAL期
  （2020-2024）年化報酬皆超過三位數（value_bm +141%~142%、low_vol
  +90%~230%視拆解方式），遠超文獻認定的HML／BAB溢酬量級，判定
  EXPERIMENTAL、不直接PASS，觸發長達9輪的異常成因診斷。
- **具體數字（依時序，六個候選解釋依序被排除）**：
  1. 單一年份驅動（`TRIALS_LEDGER.md`#152/#167）：VAL期逐年拆解顯示
     四年全部為正、leave-2022-out不降反升——**REFUTED**。
  2. 持股集中度（`TRIALS_LEDGER.md`#154）：排除own-VAL-return前7%極端
     贏家後報酬不降反升——**REFUTED**（與`f_us_value_bm`舊池子#18形成
     鮮明對比，那裡排除極端值後報酬從+121%驟降至<30%）。
  3. 宇宙離散度（`TRIALS_LEDGER.md`#171）：乾淨宇宙與舊宇宙VAL/TRAIN
     報酬離散度比值同量級（1.34x vs 1.59x），SPY自身波動率反而下降
     ——**REFUTED**。
  4. Long/Short腿拆解（`TRIALS_LEDGER.md`#172）：多頭腿VAL報酬完全在
     合理範圍（甚至低於TRAIN），異常幾乎100%來自空頭腿。
  5. 空頭腿持股與成本模型（`TRIALS_LEDGER.md`#174/#177/#183）：空頭腿
     高度集中在少數「反覆反向分割死亡螺旋」微型股（WATT/CRWD/LEE/
     AMTX/WULF/CIIT/DVLT/MNTS/PALI等），價格下限篩選因`adj_close`
     被未來反向分割回溯放大而失效；把借券費率從固定2%/yr大幅提高到
     文獻上限100%/yr（price-tiered），空頭年化報酬僅降0.6%~8.4%
     ——**REFUTED**（成本被低估不解釋量級）。
  6. 換手率混淆（`TRIALS_LEDGER.md`#181）：把隨機控制組換手率鎖定到
     與真實策略同量級（persistent-random null）後仍是淨損
     ——**REFUTED**。
  7. FINRA threshold list歷史紀錄（`TRIALS_LEDGER.md`#185）：常駐空頭
     ticker月頻抽樣49點0命中——**REFUTED**（但月頻抓不到短暫FTD事件，
     非強證據）。
  8. 免key免登入替代資料源（`TRIALS_LEDGER.md`#188）：yfinance實測與
     FinMind的`adj_close`逐位元相同，證實Yahoo Finance本身也是
     back-adjusted（非FinMind獨有限制）；stooq.com觸發反機器人驗證，
     依`CLAUDE.md`取得方式鐵律不得繞過。Alpha Vantage`TIME_SERIES_
     DAILY`文件宣稱raw報價，但需要API key，需使用者同意才能註冊，
     馬拉松無人值守輪次不得代為決定。
- **死因**：排除以上六類解釋後，唯一站得住腳、且已無免費合法管道可
  進一步驗證的解釋是`adj_close`回溯膨脹歷史名目價格——空頭腿系統性
  選中的死亡螺旋型微型股，其歷史價格因為「未來」尚未發生的反向分割
  被回溯放大（例：`MNTS`在VAL起點2020-12-31的adj_close高達
  $224,500，`DVLT`達$53,100），導致比率報酬計算本身雖然算式正確，
  卻無法代表真實世界能夠執行的交易結果。這不是策略構造錯誤，也不是
  隨機控制組/成本模型/樣本方法的問題，是**資料源本身結構性缺乏raw
  報價欄位**，屬於`CLAUDE.md`「取得方式鐵律」框架下「查了三個來源都
  沒有→誠實記錄替代路徑」的情境，不是可以靠更聰明的統計方法解決的
  邊際問題。US軌額外落地了一個Top-N長多組合構造（`#22`，完全避開
  短腿）試圖繞過這個限制，但在組合層級本身測出FAIL（隨機控制組
  percentile 43.0/60.0，alpha p值皆>0.7），代表繞開短腿後也沒有可
  兌現的顯著alpha。
- **這個死法能不能泛化**：**不泛化到「value/低波動因子在美股無效」**
  ——文獻基礎（Fama-French HML、BAB/leverage-constraint）不受影響，
  多頭腿本身在TRAIN/VAL兩期報酬量級都合理、無異常。死的是「用FinMind
  免費美股資料源建構含空頭腿的長短倉策略，且空頭腿容易選中低價微型
  股」這個具體資料/構造組合。**若未來取得含raw報價的合法資料源**
  （例如使用者核准註冊Alpha Vantage、或購買含未調整報價的商業資料），
  這兩個因子值得重新測試——不是因為經濟機制被推翻，是因為量測工具
  的限制被移除。
- **原始記錄**：`TRIALS_LEDGER.md`#144/#163/#165/#167/#170/#171/#172/
  #174/#177/#181/#183/#185/#188，`US_LEADS.md`#20/#21/#22（完整9輪
  更新記錄），`us_factor_ic_value_clean_universe.py`／
  `us_factor_ic_lowvol_clean_universe.py`／
  `deep_dive_us_value_bm_lowvol_leg_decomposition.py`／
  `us_short_leg_holdings_check.py`／`us_short_leg_price_floor_check.py`／
  `us_short_leg_tiered_borrow_check.py`／
  `deep_dive_f_us_low_vol_persistent_random_control.py`／
  `finra_threshold_probe.py`／`us_alt_source_raw_price_probe.py`
  （皆可重複執行）。

---

## `HYPOTHESIS_QUEUE.md`佇列本輪新測的陣亡紀錄

### 原子.六 籌碼depth-1原子IC地圖 Tier A（併入上櫃三大法人重測，描述性地圖，2026-09-22 FAIL，TRIALS_REGISTRY #328）

- **哪一關死的**：`ATOM_CHIP_IC_MAP_SPEC.md`第7節條件1（同上）與條件2（同上），與#317同一套判定口徑重測。
- **背景**：`籌碼原子.補上櫃三大法人歷史`回補完成並併入`chip_atom_library.load_t86_by_stock()`後，T86族有效覆蓋由50.5%（198/392，僅上市）→87.8%（344/392），規格第12節明文這是新一輪試驗、不得沿用#317判定，故重跑`chip_atom_ic_map.py --tier A --tag _otc`並獨立登記。
- **具體數字**：20日 K>=4有67個、全窗同號4個 vs 樸素期望6.69（p=0.913，與#317完全一致）；60日 K>=4有43個、全窗同號2個 vs 期望4.06（p=0.924，#317為1個/p=0.986，略升但仍遠未達p<0.01）；高階篩選兩horizon皆通過0個（期望上界0.33/0.21）。VAL IC為正占比20日34.3%/60日58.2%。
- **死因分類**：流程對但這條假設無edge；非流程錯。**額外穩健性證據**：併入上櫃資料、覆蓋率大幅提升後結論實質不變，說明#317的FAIL不是「上市股樣本不足」造成的檢定力問題，補樣本沒有改變方向。
- **不泛化聲明**：與#317相同——不代表「籌碼資訊沒用」，只否決depth-1單一原子時間序列、日頻lag1、Tier A（現涵蓋87.8%）、IC地圖層級的檢驗；depth-2/3、籌碼×價量交互、Tier B借券賣出餘額族（SBL未回補，記「未檢驗」非FAIL）皆未測。
- 完整：`CHIP_ATOM_IC_MAP_otc.md`、`chip_atom_ic_map_aggregate_otc.json`、`chip_atom_ic_map_result_A_otc.json`。

### 原子.六 籌碼depth-1原子IC地圖 Tier A（描述性地圖，2026-09-20 FAIL，TRIALS_REGISTRY #317）

- **哪一關死的**：`ATOM_CHIP_IC_MAP_SPEC.md`第7節條件1（K>=4者「全窗同號」比例對各表達式自己的樸素基準做單尾檢定，門檻p<0.01）與條件2（高階篩選通過數須超過樸素期望）。
- **具體數字**：20日 K>=4有67個、全窗同號4個 vs 樸素期望6.69（**低於期望**），Poisson-binomial p=0.913；高階篩選通過0（期望上界0.33）；60日 K>=4有43個、全窗同號1個 vs 期望4.06，p=0.986；通過0（期望上界0.21）。TRAIN/VAL同號40/67、28/67，IC中位數約-0.005~+0.004，遠低於0.02。
- **死因分類**：流程對但這條假設無edge（depth-1日頻lag1籌碼原子未見跨牛熊段穩定訊號）；非流程錯。
- **不泛化聲明**：不代表「籌碼資訊沒用」，只否決depth-1單一原子時間序列、日頻lag1、Tier A（三大法人族僅上市約198檔、融資融券族392檔）、IC地圖層級的檢驗；depth-2/3、籌碼×價量交互、上櫃三大法人、Tier B借券賣出餘額族（SBL未回補，記「未檢驗」非FAIL）皆未測。T86族缺2011歐債窗（K只有4）；存活者偏誤方向未知，U中價格末筆<2024-06有23檔、融資融券22檔（見`chip_atom_universe_delist_stat.json`）。
- 完整：`CHIP_ATOM_IC_MAP.md`、`chip_atom_ic_map_aggregate.json`、`chip_atom_ic_map_result_A.json`。

### 原子.五 財報depth-1素材IC地圖（描述性地圖，2026-09-20 FAIL，TRIALS_REGISTRY #316）

- **哪一關死的**：SPEC第7節條件1（Tier A族層級五窗全同號比例 vs 樸素6.25%，Bonferroni×2後p<0.01）。
- **具體數字**：Tier A族層級 20日 2/10族(調整後p=0.252)、60日 3/8族(未調整p=0.0108、調整後0.0215)；表達式層級60日6/26(p=0.0046)但只有14~17個獨立族，p高估顯著性。Tier B僅輔助(p=0.39~0.50)。
- **死因分類**：流程對但這條假設無edge（未見跨牛熊段穩定訊號）；非流程錯。
- **不泛化聲明**：不代表「財報資訊沒用」，只否決depth-1單一時間序列/單季比值、季頻約48 snapshot、IC地圖層級的檢驗；depth-2/3、更長窗口、擴大三表齊全宇宙皆未測。存活者偏誤偏高估、共同市場行情使樸素基準低估同號機率，兩者都不利於過關，結論方向不受影響。
- 完整：`FIN_ATOM_IC_MAP.md`、`fin_atom_ic_map_family.json`。

### 原子.五B 財報通道B(結構型算子)IC地圖（描述性地圖，2026-09-21 FAIL，TRIALS_LEDGER #320）

- **哪一關死的**：SPEC第4節條件①（Tier A K=5族層級五窗全同號比例 vs 6.25%）與條件②（篩選通過需≥2獨立族）。
- **具體數字**：K=5僅4個獨立族；20日0/4(p=1.0)、60日1/4(p=0.228，×2=0.455)；篩選通過1族(樸素期望上界0.022)。Tier B(K=4，僅輔助)兩horizon皆1/13(p=0.82)。
- **死因分類**：**流程對但檢定力不足**（不是「確認無edge」）：45個表達式中37個因depth-2/3需12~16季歷史而缺2011窗，母體僅4族。
- **不泛化聲明**：**不得外推成「財報depth-2/3以內皆無效」**（SPEC第4節分支(b)那句在此檢定力下不成立）；只能寫「此檢定力下未見訊號、無法排除」。價量×財報混合、其他預期模型、分析師預期皆未測。
- **待總司令裁示**：是否待財報原子.補快取擴大Tier A宇宙後另立新SPEC以未看過的檢定重測（不得併入K=4等替代規則＝改門檻）。
- 完整：`FIN_ATOM_CHANNEL_B.md`、`fin_atom_ic_map_b_family.json`。

### weinstein_stage2_v2（站上150日均線+均線上揚+相對強度>0，股票，2026-08-29馬拉松自主循環FAIL）

- **哪一關死的**：隨機控制組（GATE_SEQUENCE第2關）+ 成本/稅/滑價敏感度
  （第4關）——兩期都沒清楚跨過單測門檻，且alpha在成本壓力下轉負。
- **具體數字**：
  - VALIDATION(2021-2024)：總報酬+56.72%（贏買進持有+54.58%），但拆解
    後beta=+0.51、beta貢獻+32.93%（占總報酬過半），純alpha累積僅
    +23.80%（年化+5.70%）；配對式隨機控制組(n=200)中位數+21.31%，
    **percentile=55.0，遠低於90.0單測門檻**——alpha沒有清楚贏過隨機。
    成本敏感度：1x alpha+23.80%→2x+4.79%→**3x轉負-16.37%**。
  - TRAIN(2015-2020)：總報酬+15.45%，beta=+0.36、beta貢獻+19.11%
    （比總報酬還高，代表純alpha本身已經是負的），純alpha累積**-3.66%
    （年化-0.64%，本來就是負的）**；隨機控制組中位數-27.17%，
    percentile=84.0，同樣未達90.0門檻（策略比隨機控制組的「更負」
    好一點，但雙方都是虧錢，不是有意義的勝出）。成本敏感度：1x
    alpha-3.66%→2x-7.26%→**3x總報酬轉負-19.65%、alpha-31.97%**。
- **這個死法能不能泛化**：**能，但範圍有限**——這個具體實作（相對強度
  用60日窗口、150日均線判斷站上/上揚、TAIEX 200日均線當大盤閘門）死於
  「表面總報酬好看主要是beta曝險，扣掉曝險後的純alpha薄弱且經不起
  真實交易成本」，這正是`CLAUDE.md`「復盤原則：流程重於盈虧」點名的
  典型案例——**不能泛化成「Weinstein第二階段這個概念完全沒用」**，
  可能的後續變體（例如改用更短/更長的相對強度窗口、改用不同的大盤
  閘門定義、或搭配其他篩選條件縮小候選池）都還沒測過，但這個具體版本
  乾淨FAIL，不進候選清單。
- **原始記錄**：`research/weinstein_v2_alpha_gate.py`、
  `research/strategies/{weinstein_stage2_v2,run_weinstein_unbiased_v2}.py`，
  輸出`data/weinstein_v2_alpha_gate_summary.csv`（gitignored，本機保留）。
  `HYPOTHESIS_QUEUE.md`#1狀態同步更新為FAIL。

### fut_cta_momentum_12m（單一12個月/252交易日回顧報酬正負號，月頻重平衡，期貨，2026-09-01FAIL）

- **哪一關死的**：隨機控制組（GATE_SEQUENCE第2關），percentile=10.0，
  遠低於90.0單測門檻，而且**低於50**——真實策略比多數（190/200）隨機
  洗牌自己的部位陣列還差，不是「差一點沒過」，是清楚的反向結果。
- **具體數字**：2000-01-04至2024-12-31全樣本6185天，有效訊號天數5915
  （開頭270天無12個月回顧史），long 73.9%/short 26.1%/flat 0%，月頻
  換倉29次。真實策略終值0.7162（**累積虧損-28.4%**，無成本），同期買
  進持有+778.9%，配對式隨機控制組(N=200)中位數+180.9%。
- **死因（研判，非確定，已誠實標記為推論）**：人工檢查訊號構造本身
  無bug——2000年底~2001年做空區間對應網路泡沫破裂後續下跌（訊號方向
  正確），2023-2024全程做多對應多頭格局（訊號方向也正確），不是索引
  錯位或反向寫反。研判是典型「動量崩盤」（momentum crash，Daniel &
  Moskowitz 2016文獻現象）：12個月落後訊號在V型急拉反彈時來不及轉向，
  反而在轉折點附近持有錯誤方向，這在單一慢速趨勢窗口、無多時間框架
  平滑、無波動regime過濾的「教科書式」時序動量最容易發生。
- **這個死法能不能泛化**：**不能泛化成「CTA/趨勢跟隨在台指期沒用」**。
  已FAIL的`fut_trend_multi_tf`（`TRIALS_LEDGER.md`#18，10/20/60日三窗口
  多數決）percentile=82.5，方向正確但不夠穩健；這次單一12個月窗口反而
  更差（10.0<82.5）。這暗示「多窗口平滑投票」可能比「單一慢窗口」更能
  緩解動量崩盤問題，值得記錄供未來變體參考——但**不能直接套用**
  `fut_vol_regime_trend`（#21，對`fut_trend_multi_tf`加波動regime過濾
  無顯著改善）的結論到這個單一窗口版本，因為那是不同的基礎訊號，需要
  獨立測試才能下結論。依協定第2關未過直接結案，未進行第3關以後的
  參數高原/成本敏感度/leave-one-out/樣本外驗證（協定規定不硬做）。
- **原始記錄**：`research/cta_momentum_12m.py`（新增，可重複執行）、
  `TRIALS_LEDGER.md`#72。`HYPOTHESIS_QUEUE.md`#2狀態同步更新為FAIL，
  佇列接續#3 PEAD策略層構造。

### pead_portfolio_v1（SUE二因子等權組合，月頻Top20，股票，2026-09-01FAIL）

- **哪一關死的**：alpha顯著性（本專案已建立、非`HYPOTHESIS_QUEUE.md`
  GATE_SEQUENCE明文編號、但`portfolio_multifactor_v2`/`weinstein_stage2_v2`
  兩個先例都用過的既有評判標準）——隨機控制組percentile技術上過關
  （TRAIN 100.0/VAL 98.0），但這不能取代alpha顯著性檢定。
- **具體數字**：TRAIN(2015-2020)報酬+60.28%/alpha+7.36%(p=0.5349)/
  beta+0.564；VALIDATION(2021-2024)報酬+54.65%/alpha+6.03%(p=0.4809)/
  beta+0.570，**VAL期總報酬跟買進持有大盤(+54.58%)只差+0.07個百分點**，
  兩期alpha都遠不顯著(p遠高於0.05)。
- **死因**：beta約+0.56~0.57代表報酬主要來自市場曝險，不是選股貢獻的
  超額報酬；隨機控制組贏的是「排序這兩個因子挑的股票比隨機挑股票好」，
  這跟`f_eps_surprise`/`f_revenue_surprise`因子層IC本來就PASS的結論一致
  且不矛盾，但沒有轉化成portfolio層級統計上站得住腳的alpha——跟
  `weinstein_stage2_v2`（表面總報酬贏買進持有，拆解後主要是beta貢獻）
  同一種死法，也跟`portfolio_multifactor_v2`（隨機控制組99~100分但alpha
  p值全部>0.05）同一個卡關點。
- **這個死法能不能泛化**：**不能泛化成「PEAD/SUE因子沒用」**——因子層
  IC本身依然是`TRIALS_LEDGER.md`#7/#8的PASS結論，沒有被推翻。這裡死的
  是「等權、月頻、Top20」這個具體portfolio構造方式，未來變體（IC加權、
  更窄資格池、跟其他因子情境式組合）仍值得獨立測試，不能因為這次死了
  就認定PEAD概念在這個宇宙沒有可執行的形式。
- **原始記錄**：`research/pead_portfolio_v1.py`（新增，可重複執行，沿用
  `portfolio_backtest_v2.py`通用機制不修改該檔案）、`TRIALS_LEDGER.md`#73，
  `data/pead_portfolio_v1_results.csv`（gitignored）。`HYPOTHESIS_QUEUE.md`
  #3狀態同步更新為FAIL，佇列接續#4股票股利率carry。

### dividend_yield_portfolio_v1（HYPOTHESIS_QUEUE.md#4「股票股利率carry」，
單因子`f_dividend_yield_ttm`月頻Top20，股票，2026-09-02FAIL）

- **哪一關死的**：alpha顯著性（本專案已建立、`portfolio_multifactor_v2`/
  `weinstein_stage2_v2`/`pead_portfolio_v1`三個先例都用過的既有評判
  標準）——腳本內建的第7/8關判定邏輯（`gate7_pass`/`gate8_pass`，見
  `dividend_yield_portfolio_v1.py`第298/311行）**沒有把alpha顯著性納入
  判準**，只看「VAL報酬為正+隨機控制組percentile>=90.0」與「VAL MDD/
  成本情境/beta<1.3」，技術上印出兩關皆PASS，但套用本專案既有的alpha
  p值標準後兩期都不顯著，依協定第2節「判定標準要跟既有已結案案例同一把
  尺」改判FAIL，不採信腳本自己印出的表面PASS字樣。
- **具體數字**：TRAIN(2015-2020)報酬+68.07%/MDD-28.33%/Sortino0.431/
  alpha+11.29%(p=0.4868不顯著)/beta+0.585，買進持有+58.86%，隨機控制組
  (N=100)percentile=99.0。VALIDATION(2021-2024)報酬+71.93%/MDD-12.40%/
  Sortino1.009/alpha+9.89%(p=0.1487不顯著)/beta+0.448，買進持有+54.58%，
  隨機控制組(N=100)percentile=100.0。成本1x/2x/3x：TRAIN
  +68.07%/+65.07%/+63.29%、VAL+71.93%/+66.88%/+62.52%（三個成本情境
  VAL皆正，這點腳本第8關判準沒錯）。
- **死因**：兩期alpha p值（0.4868、0.1487）都遠高於0.05標準顯著性門檻，
  beta（+0.585、+0.448）代表報酬有相當比例來自市場曝險，不是純粹選股
  貢獻的超額報酬——隨機控制組贏的是「排序股利率高的股票比隨機挑股票
  好」（跟`f_dividend_yield_ttm`因子層IC本來就CHEAP_PASS的結論一致且
  不矛盾，`TRIALS_LEDGER.md`#74），但沒有轉化成portfolio層級統計上站
  得住腳的alpha。跟`pead_portfolio_v1`（#73，兩期alpha p=0.53/0.48）
  同一種死法，但**這次VAL期相對買進持有的超額報酬明顯更大**（+17.35個
  百分點 vs PEAD的+0.07個百分點）、VAL alpha p值也更接近顯著（0.1487
  vs PEAD的0.4809）——證據比PEAD稍強但仍未跨過0.05門檻，誠實記錄為
  FAIL不因為「比上一個死掉的案例好一點」就放寬標準。
- **這個死法能不能泛化**：**不能泛化成「股利率因子沒用」**——因子層
  IC（`TRIALS_LEDGER.md`#74，train/val同號、null percentile=100.0）依然
  是CHEAP_PASS的結論，沒有被推翻。這裡死的是「等權、月頻、Top20」這個
  具體portfolio構造方式（跟PEAD死掉的構造完全相同，是本專案第二次同一種
  構造方式在不同因子上死於同一個alpha顯著性問題），值得記錄的教訓是
  「等權Top20月頻」這個portfolio構造本身可能系統性地讓beta稀釋掉alpha
  訊號，未來變體（IC加權、更窄Top-N資格池、跟其他因子情境式組合、或者
  搭配regime overlay降低beta曝險期間的部位）仍值得獨立測試。
- **流程教訓（順帶記一筆，跟`CLAUDE.md`「復盤原則」呼應）**：腳本自己
  印出的gate7/gate8判定文字不能直接採信為最終結案依據——寫portfolio層
  驗證腳本時，第7/8關的PASS/FAIL判準應該直接把`alpha_significant`納入
  程式碼邏輯（而非只印出數字讓人工事後核對），避免未來排程實例誤信
  腳本自己的PASS字樣就草率結案。這條教訓留給下次寫類似portfolio驗證
  腳本時參考，不回頭修改`pead_portfolio_v1.py`/`dividend_yield_
  portfolio_v1.py`本身（已完成的驗證腳本，人工判讀已經抓出正確結論，
  不算bug需要熱修）。
- **原始記錄**：`research/dividend_yield_portfolio_v1.py`（沿用
  `portfolio_backtest_v2.py`通用機制不修改該檔案，checkpoint機制詳見
  `MARATHON_LOG.md`2026-09-02T01:20條目）、`TRIALS_LEDGER.md`#75，
  `data/dividend_yield_portfolio_v1_checkpoint.json`（gitignored，
  完整TRAIN/VALIDATION兩期100/100隨機控制組數字）。`HYPOTHESIS_QUEUE.md`
  #4狀態同步更新為FAIL，佇列接續#9殘差動量Residual Momentum。

### f_residual_momentum（HYPOTHESIS_QUEUE.md#9「殘差動量Residual Momentum」，
Blitz/Huij/Martens 2011，因子層第1關cheap IC gate，2026-09-02FAIL）

- **哪一關死的**：GATE_SEQUENCE第1關cheap IC gate本身——`factor_ic.py`
  `evaluate_factor()`要求同時滿足三項判準（VAL期IC非零、train/val同號、
  贏過洗牌null分布），這條在「train/val同號」這一項就沒過，依協定第1關
  未過直接結案，未進第2關以後（更不用說portfolio層構造）。
- **具體數字**：`factor_ic_residual_momentum.py`（100檔快取樣本，80檔
  可用，121個20交易日快照，2015-01-01~2024-12-31）：TRAIN mean_ic=
  -0.0092 IR=-0.057（n=40期）、VAL mean_ic=+0.0305 IR=+0.248 hit_rate=
  0.62（n=47期），null percentile=90.6（門檻90.0，單看percentile勉強
  過）。
- **死因**：TRAIN期IC幾乎為零且方向為負，VAL期轉正但幅度很小——如果只看
  VAL單期percentile會誤以為過關，但train/val方向相反代表這個關係在不同
  期間不穩定，是雜訊主導，不是穩健的橫斷面預測能力。跟`dividend_yield_
  portfolio_v1`（#75）「表面贏但alpha不顯著」的死法不同——這條連因子層
  最便宜的第1關單測都沒過，比portfolio層才死的案例更早、更便宜地被拆穿。
- **這個死法能不能泛化**：**不能泛化成「剝離beta找殘差動量這個機制本身
  沒用」**。有兩個明確保留的理由，未來重測前要先看過：
  1. 這次用的是簡化的一階近似（12個月股票報酬減去「252日滾動beta×12個月
     大盤報酬」，不是逐日重算複利殘差再累加，見`factors.py::prepare_
     factors()`「(u)」段落docstring）——跟`f_rel_strength`用「股票報酬-
     大盤報酬」隱含beta=1同一種近似程度，但沒有驗證過這個近似對「beta
     隨時間變動」是否夠敏感。
  2. 只測了CAPM單因子（純市場beta），文獻原始設計（Blitz/Huij/Martens
     2011）建議延伸到三因子（加size/value），本專案目前沒有現成的TW版
     size/value系統性因子可以零成本複用，這條路徑沒有測到。
  未來若要重測，需要換一種殘差計算方式（例如真的逐日跑滾動迴歸取殘差
  再累加）或延伸多因子模型，不能沿用這次同一個具體實作（252日CAPM一階
  近似）當作「這個經濟機制已經測過」的證據。
- **跟已死案例的區隔**：跟`f_rel_strength_regime_switch`（#40）、
  Weinstein第二階段v2、`cta_momentum_12m`（#72）三個已死的原始價格動量
  類假設死法不同——那三個都是「表面贏了但拆解後是beta曝險」，這條是
  「觀測層級本身train/val就不一致，連表面訊號方向都不穩定」，屬於協定
  「快殺標準」的「觀測層級就無訊號」類別，不是同一個偽影家族換皮。
- **原始記錄**：`research/factors.py`（新增`f_residual_momentum`欄位，
  `prepare_factors()`函式內，未加入`FACTOR_COLUMNS`/`ALL_FACTOR_COLUMNS`
  清單，跟`f_dividend_yield_ttm`等其他standalone因子同一種做法）、
  `research/factor_ic_residual_momentum.py`（新增，可重複執行）、
  `TRIALS_LEDGER.md`#76。`HYPOTHESIS_QUEUE.md`#9狀態同步更新為FAIL，
  佇列接續#10市場regime擇時overlay（下一個排隊項目，方法論框架待建立）。

### 產業內相對強度 Sector-Neutral Relative Strength（HYPOTHESIS_QUEUE.md#11，
`f_rel_strength`去產業內均值，因子層第1關cheap IC gate，2026-09-02FAIL）

- **哪一關死的**：GATE_SEQUENCE第1關cheap IC gate本身（跟#9殘差動量、#4
  股利率因子同一種第1關「因子層cross-sectional IC＋洗牌null分布＋train/val
  同號」三項判準）——這條在「贏過洗牌null分布」這一項沒過（percentile=
  82.8，門檻90.0），依協定第1關未過直接結案，未進第2關以後（更不用說
  portfolio層構造）。
- **具體數字**：`factor_ic_sector_neutral_rel_strength.py`（新增，可重複
  執行，沿用同一個100檔快取樣本，80檔可用，其中73檔有非ETF產業分類，121個
  20交易日快照，2015-01-01~2024-12-31）：診斷（`MIN_GROUP_SIZE=3`）每快照
  中位數可用產業組數10組、組內中位數成員數4檔、中位數可用個股數39檔（103/
  121個快照有足夠橫斷面樣本），組別稀疏度尚可、不是結構性no-op。TRAIN
  mean_ic=-0.0323 IR=-0.160（n=62期）、VAL mean_ic=-0.0340 IR=-0.176
  hit_rate=0.59（n=41期），train/val**同號**（皆為負），|val_mean_ic|=
  0.034超過0.02最低門檻，但null percentile=82.8**未達**90.0門檻。
- **死因**：三項判準裡「同號」跟「幅度非零」都過了，唯獨「贏過洗牌隨機
  對照組」這一項沒過——82.8雖然不算「遠低於」90.0（跟#9的90.6勉強壓線
  但同號未過剛好相反：這條同號過了、percentile沒過），但這是`factor_ic.py`
  `evaluate_factor()`原封不動搬過來的判準邏輯（跟#4/#9用同一套threshold常數
  BASE_ALPHA/N_SHUFFLES/SHUFFLE_SEED，事前綁定、非事後移動門柱），
  `passes=False`是這套已經套用在#4/#9兩次的固定判準機械算出的結果，不是
  本輪臨場放寬或收緊的主觀判斷。此外，兩期IC本身方向為**負**（IR僅
  -0.16~-0.18，比CHEAP_PASS的股利率因子IR+0.43~+0.56明顯弱得多），意味著
  即使未來換更大樣本/不同demean方式讓percentile剛好壓線過關，這個訊號的
  經濟方向也跟假設定義（「做多產業內前段班」預期正向延續）相反——是產業內
  短期反轉而非延續，跟原始假設的機制敘事不符，不是同一個東西換個方向講。
- **這個死法能不能泛化**：**不能泛化成「產業中性化這個中性化角度本身
  沒用」**，有明確保留的理由：
  1. 產業分類來源用`universe.py::universe()`的`industry_category`（單一
     `keep="last"`快照），沒有處理`build_company_info.py`已經發現的「同一
     股票同一天FinMind回傳兩種產業分類」歧義問題（約24%代碼有此現象）——
     這會讓部分股票被分進錯誤的產業組，稀釋demean的訊噪比，是這次具體
     實作的資料品質限制，不是機制本身無效的證明。
  2. `MIN_GROUP_SIZE=3`跟100檔快取樣本（3.1%抽樣率）組合出中位數組內
     4檔的稀疏度，「產業內排序」在只有3~5檔的小組裡統計力天生偏弱——換
     更大樣本（例如300~500檔）讓每個產業組都有10檔以上，統計力可能明顯
     改善，這條未測過。
  3. 只測了`f_rel_strength`（60日相對大盤動能）一種基底因子的產業中性化
     版本，沒測試其他窗口（例如12個月動能）或其他基底因子（例如營收/
     籌碼類）的產業中性化版本。
  未來若要重測，需要先修正產業分類歧義處理（比照`company_info.json`的
  同日多分類→留None規則）+ 擴大樣本規模，不能沿用這次的具體實作（100檔
  快取樣本+`universe.py`粗略產業對照）當作「產業中性化這個角度已經測過」
  的證據。
- **跟已死案例的區隔**：跟#9殘差動量都屬於「beta/曝險剝離」家族但剝離的
  維度不同（#9剝離跨時間系統性因子曝險，這條剝離橫截面產業曝險），死法
  也不同——#9是train/val**方向不一致**（雜訊主導），這條是**方向一致但
  幅度不足以贏過隨機對照**，且方向本身跟假設預期相反，屬於協定「快殺
  標準」的「觀測層級就無訊號」類別的另一種呈現方式，不是同一個偽影家族
  換皮。
- **原始記錄**：`research/factor_ic_sector_neutral_rel_strength.py`（新增，
  可重複執行，不改`factor_ic.py`本身，比照`dividend_yield_portfolio_v1`
  「只改自己、不動共用模組」的教訓）、`TRIALS_LEDGER.md`#77。
  `HYPOTHESIS_QUEUE.md`#11狀態同步更新為FAIL，佇列接續#12
  Betting-Against-Beta/低beta（下一個排隊項目，待起跑）。

**【2026-09-04馬拉松第334輪補充——`CALIBRATION_PROBE.md`結論(乙)＋
`MARATHON_PROTOCOL.md`操作指令「接著依序重跑#77/#79/#91」，300檔重跑，
`TRIALS_LEDGER.md`#101】**：`factor_ic.SAMPLE_SIZE`已由校準探針改100→300，
腳本零修改重跑。300檔樣本248檔可用（原100檔80檔可用），216/248有非ETF
產業分類，組內中位數成員數從4檔升到6檔、可用產業組數從10組升到20組（本輪
保留②「更大樣本讓每組10檔以上，統計力可能明顯改善」的推測方向正確——組
確實變密了）。**但結果與推測相反**：TRAIN mean_ic=-0.0113、VAL mean_ic=
-0.0065（原100檔樣本分別是-0.0323/-0.0340，量級縮小約1/3~1/5），null
percentile從82.8**驟降**到41.9（不是小幅波動，是大幅遠離門檻）。**這與
#79`f_inst_streak_days`同批300檔重跑（percentile 81.9→86.1小幅提升）呈現
方向相反的結果**，代表這條假說原本100檔樣本測出的82.8很可能是**小樣本
雜訊放大出的假邊緣訊號**，不是被稀疏樣本錯殺的真訊號——跟前面保留②的
猜測（訊號被稀釋、地基不夠大）恰好相反，是「地基不夠大讓雜訊看起來像
訊號」。**判定從「未定（待300檔重跑）」正式改回確定FAIL，且證據比100檔
樣本更明確、比`f_inst_streak_days`更乾淨排除「檢定力不足」這個保留理由**。
其餘既有保留（產業分類歧義未修正、只測`f_rel_strength`單一基底因子）不變。
完整見`TRIALS_LEDGER.md`#101、`TW_LOG.md`第334輪記錄。

### Betting-Against-Beta / 低beta（HYPOTHESIS_QUEUE.md#12，`f_bab`因子層第1關
cheap IC gate，2026-09-02FAIL——重用既有結果，非新測試）

- **重要說明（這則條目的特殊之處）**：這輪沒有跑任何新程式或新計算。查核
  `HYPOTHESIS_QUEUE.md`#12「已知相關背景」段落時發現一個**遺漏**——`f_bab`
  這個因子（60日滾動beta取負號的cross-sectional排序）其實**已經在另一條
  軌道（TW marathon，非這條假設佇列）測過**，結果記在`TRIALS_LEDGER.md`
  #61（2026-08-26），但佇列#12條目完全沒提到這件事，寫著「第1關（sanity）
  尚未開始」是不準確的。這輪的工作是把這個遺漏的背景資訊補齊，並依這個
  已有的（且是跨軌共用同一份`TRIALS_LEDGER.md`累積帳本的）證據做出判定，
  不是重新起跑。
- **哪一關死的**：因子層第1關cheap IC gate——具體是`TRIALS_LEDGER.md`
  「累積比較校正」這個跨軌共用的多重比較框架（見該檔案開頭說明：
  `bonferroni_n`＝這份檔案目前的總列數，涵蓋台股因子/美股因子/期貨策略/
  任何軌道，不是只算單一軌道自己測了幾個）。
- **具體數字（原封不動引用`TRIALS_LEDGER.md`#61，2026-08-26，TW marathon
  第101輪，`factor_ic_bab.py`：沿用`f_idio_vol`已算好的60日滾動beta，零新
  資料/零新計算，80/100可用樣本，121個不重疊20交易日快照）**：TRAIN
  mean_ic=+0.0020 IR=+0.009（n=63期，基本上是雜訊，跟零沒有可辨識差異）；
  VAL mean_ic=+0.0302 IR=+0.141 hit_rate=0.47（n=47期）；train/val同號
  （皆為正）；對隨機打散null的percentile=91.0，單獨看剛好過90.0門檻，
  **但當時TW軌本身累積的因子家族數已到27（含這筆），跨累積Bonferroni
  校正門檻＝100×(1-0.10/27)=99.63，91.0離這個門檻還差非常多**，已由
  TW軌自己判定「CHEAP_PASS（單測），但批次/累積校正未過，降級為不確定，
  不進深挖清單」。
- **死因（這輪的判定邏輯，套用到佇列#12）**：`TRIALS_LEDGER.md`存在的
  唯一理由就是「多重比較校正必須涵蓋這個專案有史以來測過的所有因子/策略，
  不是只看某一次批次測了幾個」（見該檔案開頭第一句）——這條假設佇列
  （`HYPOTHESIS_QUEUE_PROTOCOL.md`軌道）跟TW marathon軌道雖然用不同的
  具名鎖、互不阻塞執行，但**兩者共寫同一份`TRIALS_LEDGER.md`累積帳本**，
  代表多重比較的「已測試次數」本來就是全專案共用、不是分軌各自歸零。
  若這輪重新用`factor_ic_bab.py`的standalone bonferroni_n=1框架把同一個
  因子當「全新測試」跑一次（數字會完全相同，因為樣本/種子/計算方式都
  一樣），等於是繞過TW軌已經誠實套用過的累積校正、把一個已經被判定
  「證據不足」的因子透過換一個框架重新包裝成「新的CHEAP_PASS」——這正是
  `CONSTITUTION.md`第2節明講的陷阱（「多重比較/拿OOS當驗證集：反覆拿
  同一塊樣本外去篩候選，本身就是過擬合。搜越多，通過門檻要越高」）跟
  `CLAUDE.md`最高投資原則第5條（「誠實判不及格、不部署未證明的edge」）
  要求要避免的行為。加上TRAIN期IR僅0.009（本輪判定的獨立支持理由，不
  依賴累積校正這個技術性論證也成立：這是協定明訂可用的快殺標準之一
  「觀測層級就無訊號」，train半段的IC強度基本上量不到訊號），兩個理由
  疊加，這輪判定**FAIL**，不重新起跑第1關，不進第2關以後。
- **這個死法能不能泛化**：**不能泛化成「beta曝險程度這個風險管理維度
  本身沒用」**，有明確保留：①這次測的是「60日滾動beta，cross-sectional
  排序，純多頭」這個具體實作，未測過更長/更短窗口、未測過搭配放空高
  beta分位的多空版本、未測過downside beta（只算下跌期的beta，文獻上
  有時比全期beta更能捕捉下檔保護訊號）這個變體；②`CLAUDE.md`最高投資
  原則第3條「regime閘門是強制overlay」這個方向（`HYPOTHESIS_QUEUE.md`#10
  已建置方法論框架、待未來有選股候選通過1~8關後套用）跟這條「beta當
  選股訊號」是不同機制，第10條的存續不受這條判定影響。未來若要重測
  BAB類假設，需要用上述保留的變體之一，且要留意累積Bonferroni校正
  只會越來越嚴（`TRIALS_LEDGER.md`列數持續增加），單一standalone
  bonferroni_n=1測試的說服力會越來越低，設計時要有心理準備。
- **原始記錄**：`TRIALS_LEDGER.md`#61（原始測試，2026-08-26，TW marathon
  軌道）、`TRIALS_LEDGER.md`#78（本輪新增，記錄佇列#12引用#61並做出判定
  的過程，非新測試）。`HYPOTHESIS_QUEUE.md`#12狀態同步更新為FAIL，佇列
  接續#13台股三大法人連續買超持續性（**這個提示字已過時，#13本輪已結案，
  見下方新條目，接續佇列請看下一則的結尾**）。

### 台股三大法人連續買超持續性（HYPOTHESIS_QUEUE.md#13，`f_inst_streak_days`
因子層第1關cheap IC gate，2026-09-02FAIL）

- **哪一關死的**：因子層第1關cheap IC gate（`factor_ic.py`既有
  cross-sectional IC + 洗牌null分布框架，`evaluate_factor()`三項判準：幅度
  非零、train/val同號、贏過洗牌null）。
- **具體數字**（`factor_ic_inst_streak_days.py`，新增，100檔快取樣本，
  80檔可用，121個20交易日快照，2015-01-01..2024-12-31）：TRAIN
  mean_ic=+0.0328 IR=+0.281（n=74期）；VAL mean_ic=-0.0236 IR=-0.183
  hit_rate=0.53（n=47期）；**train/val正負號相反**；對隨機打散null的
  percentile=81.9（門檻90.0，未過）。三項判準中兩項未過（同號、贏過null），
  直接判死，未進第2關以後。
- **死因**：`f_inst_streak_days`（三大法人合計淨買超連續同方向天數，新增
  `factors.py::_consecutive_positive_streak_days()`，逐日輸出「截至當天
  為止連續買超未中斷的天數」，非正即歸零）跟已經FAIL的`f_foreign_streak`
  （#3，2026-08-22，`TRIALS_LEDGER.md`打散對照76.0百分位+train/val正負號
  相反）刻意做過兩點區隔——①用三大法人合計（`total_net`）而非外資單一
  法人（`foreign_net`）；②衡量連續天數本身這個計數統計量，而非用成交量
  正規化的連續期間累積買超金額（連續量的大小）——但這輪結果顯示**兩者
  最終死法幾乎一模一樣**：train/val正負號都相反、null percentile都遠低於
  90.0門檻且同一量級（76.0 vs 81.9）。這暗示問題可能不在統計量的選擇
  （天數 vs 金額）或法人範圍（外資 vs 三大法人合計），而是「連續同方向
  未中斷」這個時間序列結構本身，在這套cross-sectional IC框架下就是測不出
  跨期穩健的方向性訊號。
- **這個死法能不能泛化**：**不能泛化成「三大法人籌碼流向這個資訊來源本身
  沒用」**——本專案既有`f_inst_flow`（20日三大法人淨額/20日平均成交值比率，
  `FACTOR_COLUMNS`正式批次因子清單既有成員）目前仍未被推翻，代表籌碼類
  資料本身仍可能帶有訊號，只是「連續天數/連續金額」這種**強調連續性、
  忽略單日規模**的衡量角度已經連續兩次（外資版+三大法人合計版）測試
  失敗。未來若要重測籌碼類假設，建議換一個完全不同的構造角度（例如
  三大法人持股比例的變化速率、單一法人之間的分歧/一致程度、大額單筆
  買超而非連續多日），不建議再嘗試「連續期間」這個角度的其他變體
  （例如換不同天數門檻），因為兩次獨立測試已經指向同一個死因。
- **原始記錄**：`TRIALS_LEDGER.md`#79（原始測試）、`HYPOTHESIS_QUEUE.md`#13。
  `HYPOTHESIS_QUEUE.md`#13狀態同步更新為FAIL，佇列接續#14台股月營收公布
  事件效應（下一個排隊項目，待起跑）。
- **2026-09-04補充（`TRIALS_LEDGER.md`#100，300檔樣本重跑）**：依
  `CALIBRATION_PROBE.md`結論(乙)「檢定力不足、100檔樣本可能錯殺邊緣FAIL」，
  用`factor_ic.SAMPLE_SIZE`300檔重跑（腳本零修改，248/300可用）：TRAIN
  mean_ic=+0.0232（n=74），VAL mean_ic=**-0.0150**（n=47），train/val正負號
  **仍相反**；null percentile從81.9小幅升到**86.1**（仍未過90.0門檻）。
  **結論：查核後確認原判正確，不是被錯殺的邊緣案例**——樣本擴大確實讓
  percentile往門檻方向移動了一點（符合檢定力假設），但train/val方向不一致
  這項判準不受樣本大小影響，300檔沒有解決這個根本問題。正式從「未定
  （待重跑）」改回**確定FAIL**，不再是待查項目。

### 台股月營收公布事件效應（HYPOTHESIS_QUEUE.md#14，事件研究設計第1關
cheap gate，2026-09-02FAIL）

- **哪一關死的**：事件研究第1關cheap gate（`monthly_revenue_event_study.py`
  新增自建框架，三項判準比照`factor_ic.py::evaluate_factor()`同一把尺：
  幅度非零、train/val同號、贏過洗牌null分布percentile>=90.0）。
- **具體數字**：100檔快取樣本，61檔有可用事件，總事件數8322筆（TRAIN
  5594筆跨109個不同月份、VAL 2728筆跨47個不同月份，樣本涵蓋度足夠、非
  單一年份集中）。TRAIN pooled Spearman IC=+0.0601（p=0.0000，n=5594）；
  VAL pooled Spearman IC=+0.0204（p=0.2863，n=2728）；**train/val同號**
  （皆正，這項有過）；quintile利差TRAIN+0.0318→VAL+0.0085（樣本外萎縮
  73%）；VAL |IC| vs 500次洗牌null percentile=**68.0**（門檻90.0，未過）。
  三項判準中「贏過洗牌null」這一項未過，依協定第1關cheap gate標準直接
  判死，未進第2關以後（成本敏感度/leave-one-out等）。
- **設計上跟既有失敗案例的區隔（誠實揭露，避免被誤讀成重複測試）**：
  `pead_portfolio_v1`（#3，FAIL）跟`factor_ic.py`固定日曆網格
  cross-sectional設計都是「全樣本共用同一批快照日期」，這條刻意改用
  **事件錨定窗口**——逐股用自己的月營收公布`pit_date`
  （`pit.py::month_revenue_pit()`既有PIT邏輯，真實`create_time`優先、
  否則假設次月10日）當事件起點，公布後第一個交易日進場、持有20交易日，
  事件之間彼此不同步。這是`HYPOTHESIS_QUEUE.md`#14明確要求測試的「新
  東西」，不是換皮重測PEAD策略層，這次的FAIL是這個具體設計首次被真正
  測試後得出的結果，不是理論推演。
- **死因**：VAL期p值0.2863遠不顯著、quintile利差樣本外萎縮73%
  （+0.0318→+0.0085），是典型「訓練期看似有訊號、樣本外大幅衰退」的
  過擬合/雜訊主導形狀——train期n=5594事件數夠大，任何微弱的雜訊相關性
  都容易被推到p=0.0000的表面顯著，但VAL期用完全不同時間段的獨立事件
  重新檢驗後，訊號幅度跟顯著性都明顯衰退，贏過隨機洗牌對照的百分位也
  只有68.0（比#11的82.8、#13的81.9差距更大，不是邊緣case）。
- **這個死法能不能泛化**：**不能泛化成「月營收驚喜訊號完全沒用」**——
  `f_revenue_surprise`因子層日頻cross-sectional IC驗證（`TRIALS_
  LEDGER.md`#8，PASS，Bonferroni校正n=6皆過）**完全不受這次結果影響**，
  依然是本專案正式因子清單成員；這次死的是「事件窗口這個策略層構造」
  ——跟PEAD策略層（#3，FAIL，月頻再平衡構造）是兩種完全不同的具體
  portfolio/事件構造，但殊途同歸都死於樣本外alpha/顯著性不足，暗示
  SUE類訊號在偏離「日頻橫斷面連續排序」這個原始驗證設計、改包裝成
  月頻再平衡或事件窗口這類「進出場時機集中在特定日期」的構造時，訊
  噪比整體偏弱——這是繼PEAD之後第二次觀察到同一個模式，未來若還要
  嘗試SUE/營收驚喜的策略層follow-up，建議優先考慮貼近原始因子驗證
  設計本身的構造（例如維持日頻/高頻的連續持股調整，而非月頻或事件式
  進出場），而不是再嘗試另一種事件/再平衡包裝方式。
- **過程小記（工程細節，非結果影響）**：第一版實作對原始月營收表直接
  套用holdout洩漏斷言，誤觸發`AssertionError`——`pit_date`（揭露日）
  本來就會晚於`load_dev()`用來裁切VAL_END的營收所屬期間`date`欄位，
  個別rows的`pit_date`超過VAL_END是正常現象、不是真的洩漏，因為進場
  邏輯本身已經保證只用「已經被`adjusted_price_series()`裁到VAL_END的
  交易日」當進場日。已修正為只對最終組好的事件表（用`entry_date`）做
  斷言，過程中沒有真正碰觸或洩漏holdout資料，記錄下來是給未來寫類似
  事件研究腳本的人參考：PIT揭露日晚於資料所屬期間是正常設計，不要對
  中間原始表過早套用嚴格斷言。
- **原始記錄**：`TRIALS_LEDGER.md`#80（本輪新增）、`HYPOTHESIS_QUEUE.md`#14、
  `MARATHON_LOG.md`2026-09-02T05:26條目。`HYPOTHESIS_QUEUE.md`#14狀態
  同步更新為FAIL，佇列接續#15波動度目標化Vol-Targeting（下一個排隊
  項目，可獨立於選股類假設先跑，待起跑）。

---

### 波動度目標化部位配置 Vol-Targeting（HYPOTHESIS_QUEUE.md#15，第2關
隨機控制組，2026-09-02FAIL）

- **哪一關死的**：第2關隨機控制組（`vol_targeting_v1.py`新增，第1關
  sanity先過、緊接著加做一個輕量版隨機控制組，非完整N=100正式流程但
  同一個判定精神）。
- **機制設計**：TAIEX（不依賴任何選股候選，套用對象是大盤買進持有本身，
  跟`regime_overlay.py`#10同一個「先用大盤驗證機制本身」的做法）60交易日
  滾動已實現波動度、目標年化波動率15%（`TARGET_VOL`，事前選定，該值
  低於全期間中位數已實現波動13.60%以外的水準，屬合理設定，非事後調整）、
  `exposure=clip(TARGET_VOL/realized_vol, 0, 1.0)`——**刻意不允許槓桿**
  （上限鎖1.0，理由：股票帳戶用保證金放大曝險本身是額外風險/成本來源，
  超出這輪驗證範圍），`exposure.shift(1)`避免未來函數。
- **第1關sanity結果（多數項目過關，但已埋下伏筆）**：exposure非常數
  （min=0.434/max=1.000/mean=0.911/std=0.144，60.6%天數被上限1.0截斷）；
  realized_vol與exposure相關係數=-0.946（機制方向正確，波動越高曝險越低）；
  MDD確實改善（TRAIN -28.72%→-25.54%、VAL -31.63%→-27.34%、全期間
  -31.63%→-27.34%）；已知三個危機期間（2018Q4/2020Q1/2022全年）overlay
  MDD都比baseline淺、平均滯後曝險0.68~0.79明顯低於1.0。**但同一組數字裡
  Sharpe/Sortino/Calmar全部比買進持有差**（TRAIN Sharpe 0.45→0.40、VAL
  0.74→0.69、全期間0.54→0.48；Sortino/Calmar同樣方向）——只有MDD單項
  改善，風險調整後報酬全面轉差，這是第2關前就該注意的警訊，不是事後
  才發現。
- **第2關隨機控制組（決定性證據）**：打亂`exposure_lagged`的時間順序
  （保留邊際分布：一樣的min/max/mean、一樣~60%天數在上限，只打亂哪一天
  配到哪個曝險值），N=100draws，套用到同一組`raw_return`上比較。結果：
  **真實（依realized_vol計時）曝險序列的Sharpe percentile=8.0、CAGR
  percentile=3.0**——代表92%/97%的隨機打亂時序反而表現更好，真實機制
  不只沒贏過隨機對照，是**輸給**隨機對照的多數情況，遠低於90.0門檻且
  低於50（不是邊緣case）。只有MDD percentile=90.0（真實MDD比90%的隨機
  打亂情況淺），但這一項單獨無法支撐機制有效——降低平均曝險本身幾乎
  必然壓低MDD（不論用什麼時機降），MDD改善不能證明「用realized_vol挑
  時機」這個機制本身有加值，Sharpe/CAGR雙雙輸給隨機對照才是真正的
  試金石。
- **死因研判（機制層面的解釋，非臆測）**：60日滾動已實現波動度是**落後**
  指標——市場崩跌後波動度通常會維持高檔一段時間才緩慢回落，而價格often
  在波動度真正回落前就已經開始反彈（V型或U型復甦時尤其明顯），這代表
  「用trailing realized vol降曝險」系統性地容易在**反彈初期**還維持低
  曝險、錯過復甦段的漲幅，這正是隨機控制組percentile遠低於50所量化出來
  的效果——不是隨機噪音，是這個具體時機選擇機制的結構性缺陷。
- **這個死法能不能泛化**：**不能泛化成「波動度目標化/風險平價這整個
  概念沒用」**——這次測試有兩個明確、刻意的簡化，都可能是死因的一部分：
  ①**刻意不允許槓桿**（上限鎖1.0）——文獻上（Moreira & Muir 2017等）
  波動度目標化改善風險調整後報酬的機制通常包含「低波動期加碼超過100%」
  這一半，本次版本拿掉了這一半，只剩「高波動期降曝險」單邊，可能正是
  Sharpe反而變差的部分原因（降曝險的期間報酬被砍掉，卻沒有加碼期間的
  報酬來補償）；②只測了單一60日窗口、單一15%目標值、單一標的（TAIEX
  廣義指數），未測不同波動度估計窗口（例如更短的10~20日、或EWMA加權）、
  未測套用在真正的多因子投組（而非大盤本身）。未來若要重測，建議：
  (a) 先測「允許槓桿版本」是否能修復Sharpe/CAGR輸給隨機對照的問題，
  (b) 換更短的波動度估計窗口降低落後效應，(c) 套用在已過關的選股候選
  組合上而非大盤本身——但目前佇列裡沒有已過關的候選（Weinstein/CTA/
  PEAD/Carry/殘差動量/產業內相對強度/BAB/三大法人連續買超/月營收事件
  效應皆FAIL），這個限制跟`regime_overlay.py`#10面臨的處境相同。
- **原始記錄**：`TRIALS_LEDGER.md`#81（本輪新增）、`HYPOTHESIS_QUEUE.md`#15、
  `vol_targeting_v1.py`（新增，可重複執行）、`MARATHON_LOG.md`本輪心跳
  條目。`HYPOTHESIS_QUEUE.md`#15狀態同步更新為FAIL，佇列接續#7低波動
  （TW策略層，可直接沿用US的deep_dive方法框架，唯一目前無阻塞依賴的
  下一個排隊項目）。

### 低波動（TW策略層，十分位多空）Low Volatility Decile Long-Short（HYPOTHESIS_QUEUE.md#7，2026-09-02FAIL）

- **哪一關死的**：GATE_SEQUENCE第2關隨機控制組（VAL期）+ alpha顯著性
  （`deep_dive_f_low_vol.py`新增，沿用`deep_dive_f_quality_roe_stability.py`
  的十分位多空+train/val+成本敏感度+CAPM beta模板，跟US軌
  `deep_dive_f_us_low_vol.py`同一套方法直接移植成TW版）。
- **機制設計**：`f_low_vol`（因子層`TRIALS_LEDGER.md`#9已PASS，60日滾動
  日報酬標準差取負號）十分位多空——做多`f_low_vol`最高10%（=實現波動度
  最低）、放空最低10%（=實現波動度最高），20交易日換股，100檔快取樣本
  （80/100可用、79檔有非NaN因子值）。
- **結果數字（`data/deep_dive_f_low_vol.csv`，2026-09-02T07:09完成）**：
  - TRAIN(2015-2020) 1x成本：total_return+13.99%、ann_return+2.27%、
    beta=-0.424、alpha(年化)+9.96%（p=0.6011，不顯著）、隨機控制組(N=100)
    percentile=99.0（過90.0門檻）。
  - VAL(2021-2024) 1x成本：**total_return-30.09%、ann_return-8.87%**、
    beta=-0.718、alpha(年化)+4.65%（p=0.7590，不顯著）、**隨機控制組(N=100)
    percentile=85.0（未過90.0門檻）**。2x/3x成本情境percentile=87.0/88.0，
    同樣未過。
  - beta drift check：|TRAIN beta − VAL beta| = 0.294，腳本自帶門檻0.3內
    （非「大幅漂移」等級），但兩期beta本身都是**負值**（-0.42~-0.72）
    ——這不是市場中性的十分位多空該有的樣貌，反映做多的低波動腿跟放空
    的高波動腿系統性有不同的市場曝險（機制上類似Betting-Against-Beta的
    負beta副作用，見#12`f_bab`條目，但這裡是十分位多空的副產物不是
    刻意設計）。
- **判定理由（跟本專案已建立的同一把尺）**：VAL期真實策略**虧損30%**，
  同期隨機打亂持股組合中位數equity=0.438（也是虧損但幅度較小），真實
  策略輸給85%的隨機對照組——這不是「表面漲、拆解後是beta」的偽陽性
  家族，是**VAL期連隨機控制組percentile都沒過**（GATE_SEQUENCE第2/7關
  同時未過），比其他大部分死掉假設的死法更明確、不需要更多深挖就能判死。
  兩期alpha p值也都遠高於0.05（0.60~0.76），從未顯著過。
- **死因研判**：TRAIN期（2015-2020，多為多頭與盤整格局）表現尚可
  （+13.99%、percentile 99），但VAL期（2021-2024，涵蓋2022全年空頭+
  2023-2024反彈）大幅轉負且輸給多數隨機對照——低波動股在這段期間的
  絕對表現本身不差，但這個十分位多空的**空頭腿**（放空高波動股）在
  2023-2024急漲反彈階段很可能持續虧損（高波動股反彈通常更猛），把
  多頭腿的正報酬吃掉還倒虧，是動量崩潰類機制在低波動因子多空構造上的
  類似體現，不是隨機雜訊。
- **這個死法能不能泛化**：**不泛化成「低波動因子完全沒用」**——因子層
  cross-sectional IC（`TRIALS_LEDGER.md`#9，PASS）不受影響、依然成立，
  這裡死的是「十分位多空、放空高波動腿」這個具體策略構造。跟US軌
  `f_us_low_vol`（#39/#41，FAIL，VAL期表面轉強但beta驟降至-0.891）的
  死法**不完全相同**——US版是「表面漲、其實是反向曝險」，TW版是「VAL期
  直接虧損、連隨機對照都贏不了」，但兩者共同點是**空頭腿（或多空構造
  整體）系統性引入非預期的市場方向性曝險**，暗示未來若要重測低波動因子
  的策略層，值得優先測「純多頭版本」（只做多低波動、不放空高波動），
  避開放空腿造成的方向性曝險問題，而非直接排除低波動因子本身。
- **原始記錄**：`TRIALS_LEDGER.md`#82（本輪新增）、`HYPOTHESIS_QUEUE.md`#7、
  `deep_dive_f_low_vol.py`（新增，可重複執行，上一輪陳舊鎖檔回收後本輪
  接續等待其背景執行完成，非本輪從頭重跑）、`data/deep_dive_f_low_vol.csv`
  （新增）、`MARATHON_LOG.md`本輪心跳條目。`HYPOTHESIS_QUEUE.md`#7狀態
  同步更新為FAIL——**佇列目前所有其餘項目皆處於外部依賴阻塞狀態**（#5待
  B24/B25、#6/#8卡題材動能榜PIT引擎、#10待有選股候選通過1~8關），沒有
  下一個可直接開工的候選，下一輪需評估是否進入協定「佇列已空」分支
  設計新假設軸，或等某個阻塞解除。

### 同產業配對交易/統計套利 Pair Trading（HYPOTHESIS_QUEUE.md#16，2026-09-02FAIL）
- **死因**：第2關隨機控制組（N=100，「同樣動作、隨機挑12對同產業配對」）
  證明相關係數篩選（89條可配對縮小到12條）沒有加值——真實(篩選後)pooled
  converged_frac=0.8577/mean_abs_reduction=+0.8356，vs 隨機挑12對之null
  分布median=0.8555/+0.8516，percentile僅56.0/39.0（門檻90.0，後者甚至
  低於50）。第1關sanity本身漂亮（85.5%事件收斂）掩蓋了這件事：rolling
  z-score的統計定義本身就會讓任意同產業股價log價差在極端值後有相當機率
  回落到滾動均值附近，跟兩檔股票是否真有協整/均值回歸關係無關。
- **屬於哪個偽影家族**：`CONSTITUTION.md`「縮小候選池」型偽影——機制本質
  是用相關係數把候選配對從89縮小到12，被控制組直接拆穿。
- **不泛化成什麼**：不泛化成「配對交易/統計套利機制類別完全沒用」——只
  測了簡單相關係數篩選+固定120日窗口/2.0進場閾值，未測嚴格協整檢定
  （Johansen）、未測不同參數組合，也未進到真正多空P&L/放空摩擦驗證（未
  進到那一步）。
- **原始記錄**：`TRIALS_LEDGER.md`#83、`HYPOTHESIS_QUEUE.md`#16、
  `pair_trading_sanity.py`/`pair_trading_control_v1.py`（新增，可重複
  執行）。佇列#16結案，接續佇列第一順位#17（52週高點接近度）。

### 52週高點接近度 52-Week High Proximity 策略層（HYPOTHESIS_QUEUE.md#17，2026-09-02FAIL）
- **死因**：因子層cheap IC gate（`TRIALS_LEDGER.md`#84）CHEAP_PASS後，
  組成月頻Top20單因子portfolio構造測第7/8關——`f52w_high_portfolio_v1.py`
  跑出的表面數字很漂亮（TRAIN/VAL隨機控制組percentile皆100.0、beta偏低
  +0.35~+0.44、MDD受控、成本敏感度皆正、腳本內建判準自己印出PASS），
  但**alpha顯著性未過**：TRAIN alpha+10.84%(p=0.3155)、VAL alpha+10.47%
  (p=0.0831)，兩期都未跨過本專案套用的p<0.05顯著門檻，依既有標準（PEAD/
  股利率/Weinstein同一把尺）人工override為FAIL，不採信腳本自身PASS字樣。
- **這次死法的特殊之處（誠實記錄，不是無關緊要的細節）**：VAL期p=0.0831
  是本佇列（#1~#17）目前所有FAIL案例中alpha p值最接近顯著的一次（比PEAD
  的0.4809、股利率的0.1487都更接近0.05），且beta明顯低於PEAD/股利率
  （+0.35~+0.44 vs PEAD的+0.56~+0.57）——暗示這個因子的訊噪比可能真的
  優於前面測過的其餘候選，只是這次「等權/月頻/Top20」的具體構造仍未能
  把訊號放大到統計顯著。**事前綁定門檻不因為這次比較接近就放寬**，門檻
  就是p<0.05，0.083不算過。
- **不泛化成什麼**：不泛化成「52週高點接近度因子沒用」——因子層IC
  （`TRIALS_LEDGER.md`#84，CHEAP_PASS）不受影響，死的只是「等權/月頻/
  Top20」這個具體portfolio構造，跟PEAD/股利率同一種死法。未來若要重測，
  值得優先嘗試放大樣本數（目前僅100檔快取樣本、80檔可用）或調整Top-N/
  排名權重，而非直接放棄這個因子方向——這是本佇列目前最接近過關的候選。
- **補充（2026-09-02T23:55，另一輪接續，`TRIALS_LEDGER.md`#86）**：上面
  只做了第2/4/7/9關，複製了PEAD/股利率/低波動三個先例共同跳過第3/5/6關
  的缺口——本輪新增`f52w_high_gates.py`補齊：**第3關參數密集高原PASS**
  （TOP_N∈{10,15,20,25,30}、REBALANCE_DAYS∈{10,21,42,63}共8個網格點，
  8/8皆正報酬）、**第5關leave-one-out PASS**（拿掉貢獻最大的2017年
  (+28.00%)後剩餘複利報酬仍為正+48.29%）、**第6關逐年一致性FAIL**（TRAIN
  期6個年度中僅4個正報酬，2015/2018為負，未達>=5/6門檻）。第6關FAIL跟
  第7關alpha不顯著是兩個獨立死因、互相強化，不是單一角度的偶然結論。
  依`HYPOTHESIS_QUEUE.md`「統一關卡」不得跳關的要求，這裡補上了PEAD
  (#73)/股利率(#75)/低波動(#82)三個先前案例都欠缺的第3/5/6關資料。
- **原始記錄**：`TRIALS_LEDGER.md`#85/#86、`HYPOTHESIS_QUEUE.md`#17、
  `f52w_high_portfolio_v1.py`（新增，可重複執行，checkpoint機制已驗證
  可跨次接續不重算）、`f52w_high_gates.py`（新增，可重複執行）、
  `data/f52w_high_portfolio_v1_results.csv`、`data/f52w_high_gate3_grid.csv`、
  `data/f52w_high_gate6_yearly.csv`（新增）。
  佇列#17結案，接續佇列第一順位#18（短期反轉1週）。

### 短期反轉（1週）Short-Term Reversal (Jegadeesh 1990) 因子層（HYPOTHESIS_QUEUE.md#18，2026-09-02FAIL）
- **死因**：第1關cheap IC gate未過。`f_short_term_reversal_1w`
  （-(當前收盤價/5交易日前收盤價-1)）在100檔快取樣本(80檔可用)上：
  TRAIN mean_ic=+0.0219 IR=+0.129(n=74)、VAL mean_ic=+0.0097 IR=+0.064
  hit_rate=0.45(n=47)，train/val雖同號（皆正），但VAL期IC幅度太小接近
  雜訊，且對隨機打散null percentile=41.3，遠低於90.0門檻、甚至低於50
  （代表過半數隨機打散的排列表現都優於這個真實因子）。三項判準（幅度非零/
  同號/贏過洗牌null）中兩項未過，依協定第1關cheap gate標準判**FAIL**，
  未進第2關以後。
- **跟已FAIL的`f_short_reversal_1m`的關係（誠實記錄，非重複測試）**：
  `TRIALS_LEDGER.md`#46測過21交易日（~1個月）窗口版本，同樣FAIL
  （percentile=23.1），該筆紀錄原文建議「若之後樣本擴大或改用更短窗口
  （1週）可再測」——本輪就是遵照這個建議，真正把窗口縮短到5個交易日，
  結果percentile從23.1微幅上升到41.3，方向上略有改善但幅度不足以逆轉
  結論，依然遠未過關。
- **不泛化成什麼**：不泛化成「短期反轉在台股完全無效」——只測過100檔
  快取樣本+單一5日窗口，未測更細（日頻分層/更大樣本/不同市值分層）版本，
  但目前證據不支持升格，也不建議再嘗試相鄰窗口長度的變體（1個月跟1週
  兩個端點都已經一致偏弱，暗示問題可能在樣本規模而非窗口長度本身）。
- **原始記錄**：`TRIALS_LEDGER.md`#87、`HYPOTHESIS_QUEUE.md`#18、
  `factors.py::prepare_factors()`「(w)」段落、
  `factor_ic_short_term_reversal_1w.py`（新增，可重複執行）。佇列#18
  結案，佇列#1~18原始排隊全部結案，本輪新增#19（跨市場美股隔夜報酬
  外溢效應）接續。

### 跨市場美股隔夜報酬外溢效應 擇時overlay層（HYPOTHESIS_QUEUE.md#19，2026-09-03FAIL）
- **死因**：第1關cheap gate（`TRIALS_LEDGER.md`#88）已CHEAP_PASS（美股
  ^GSPC隔夜報酬對台股^TWII次日報酬時序相關r=0.40~0.46，train/val皆
  p<0.0001，本佇列證據最強候選），這次把訊號轉成具體擇時規則
  （`spillover_overlay_v1.py`：`exposure=0.3 if us_ret<0.0 else 1.0`）
  走GATE_SEQUENCE第2關以後。**第2關隨機控制組PASS**（打亂exposure時序
  N=100，TRAIN/VAL真實值percentile皆100.0）、**第3關參數密集高原PASS**
  （49點網格78%報酬為正），但**第6關逐年一致性FAIL**：TRAIN期
  2010~2020共11個年度僅4個年度報酬為正，遠低於>=5/6門檻，且TRAIN總報酬
  本身-22.10%大幅落後同期買進持有+79.42%，依協定第6關未過快殺結案，
  未進第4/7/8/9關。
- **根本原因**：THRESHOLD=0.0（美股當日只要收黑就降曝險）觸發頻率接近
  每天一半交易日，把一個原本設計成「危機才降曝險」的防禦型regime
  overlay，實務上變成近乎逐日翻轉的高頻方向性擇時賭注——扣除頻繁切換的
  手續費/證交稅/滑價後，即使方向判斷本身正確也被成本侵蝕，加上台股
  2010-2020是強勢多頭格局，任何頻繁踏空的機制都容易系統性跑輸買進持有。
- **第5關「退化通過」的誠實記錄（不是真PASS，是判準邊界情形）**：
  `gate5_leave_one_out()`沿用`f52w_high_gates.py`同一套判準（「原本為正
  的話，拿掉最大貢獻年份後不能翻負」），但TRAIN總報酬本身已為負，判準
  條件在數學上自動滿足，不代表機制真的通過leave-one-out的實質檢驗——
  這不影響最終FAIL結論（已在更早的第6關被快殺），但記錄下來提醒未來
  類似判準寫法在輸入可能為負報酬時要另外處理，不能照抄。
- **不泛化成什麼**：不泛化成「跨市場美股隔夜外溢相關性沒用」——因子/
  相關性層級的第1關CHEAP_PASS（`TRIALS_LEDGER.md`#88）不受這次結果
  推翻，死的只是「THRESHOLD=0.0+EXPOSURE_DOWN=0.3」這個切換過於頻繁的
  具體擇時規則。未來若要重測，建議方向是拉大THRESHOLD（例如只在美股
  當日跌幅超過-1%~-2%才觸發，把切換頻率降到真正regime-gate等級——一年
  觸發數次而非隔天翻轉），但這是未來獨立測試的變體，不能拿本次FAIL的
  具體參數反推「拉大threshold應該會PASS」當結論。
- **原始記錄**：`TRIALS_LEDGER.md`#89、`HYPOTHESIS_QUEUE.md`#19、
  `spillover_overlay_v1.py`（新增，可重複執行）、
  `data/spillover_overlay_gate3_grid.csv`/`data/spillover_overlay_gate6_yearly.csv`
  （新增）。佇列#19結案，接續佇列第一順位#20（純毛利率因子Gross
  Profitability）。

### 純毛利率因子 Gross Profitability（品質，2026-09-03）

- **哪一關死的**：GATE_SEQUENCE第1關cheap IC gate（因子層級，未進第2關
  以後）。
- **具體數字**：`f_gross_profitability`（GrossProfit/TotalAssets，比率
  越高排名越靠前）TRAIN mean_ic=+0.0030 IR=+0.024(n=74)、VAL
  mean_ic=+0.0114 IR=+0.089 hit_rate=0.62(n=47)，train/val同號（皆正）
  但幅度都接近雜訊，對500次洗牌null分布的percentile=48.4（門檻90.0，
  遠未過，甚至低於50——代表半數以上的隨機打散排序表現優於真實排序）。
- **這個死法能不能泛化**：不泛化成「毛利率相關的品質異常在台股完全
  無效」——只測過100檔快取樣本+單一GrossProfit/TotalAssets定義（Novy-
  Marx原始論文的「水位」版本），未測更大樣本、未測是否受成長股（高
  毛利率但資產也快速膨脹）稀釋。跟已FAIL的`f_gross_margin_stability`
  （`TRIALS_LEDGER.md`#67，測毛利率隨時間「穩定性」，percentile=70.7）
  是不同構造、死法不同但同屬毛利率相關訊號在此樣本規模下測不出穩健
  訊號，兩者用的是同一批財報資料，暗示問題可能出在樣本規模/財報資料
  雜訊，不是「水位」vs「穩定度」的構造選擇本身。
- **原始記錄**：`TRIALS_LEDGER.md`#90、`HYPOTHESIS_QUEUE.md`#20、
  `factor_ic_gross_profitability.py`（新增，可重複執行）。佇列#20結案，
  接續佇列第一順位#21（月營收「意外」漂移×低關注度）。
- **2026-09-03實作正確性健檢（使用者裁示追加，理由：GP是跨19國最穩健
  品質因子之一，死在mean_ic≈noise跟強證據矛盾，疑似bug非真的無訊號）**：
  逐一查證公式/科目對應（FinMind`GrossProfit`欄位數值上精確等於
  `Revenue−CostOfGoodsSold`，8季全部diff=0.0）、PIT對齊（跟其他已通過
  cheap gate因子共用同一套`+45天`延遲+`merge_asof`機制，非#20獨有未經
  驗證路徑）、涵蓋率（77/100可用、逐快照中位數N=56，跟CHEAP_PASS的
  `f_52w_high_prox`中位數N=60同量級，不是涵蓋率崩塌稀釋成noise）、
  方向（TRAIN/VAL兩期`mean_ic`皆為正，跟「高GP做多」假設一致沒有接反）
  ——**四點皆查證正確，沒有發現任何實作/資料bug，正式接受FAIL、不
  重跑，維持墓園判定**。完整健檢過程見`HYPOTHESIS_QUEUE.md`#20「實作
  正確性健檢」章節。

### revenue_trend_surprise_low_attention（月營收「意外」漂移x低關注度分組，改造#14，股票，2026-09-03FAIL）

- **哪一關死的**：第1關cheap gate分組比較——低關注度組與高關注度組
  皆未通過（`evaluate_factor()`同一套三項判準：幅度非零/train-val同號/
  贏過洗牌null），依`HYPOTHESIS_QUEUE.md`#21原話「兩組都不顯著視同改造
  沒有解決#14根本問題」直接判死。
- **具體數字**：100檔快取樣本，62檔有可用事件，總事件數8958筆，用近
  20日均成交值（volume*close）中位數（4,177,417）切分低/高關注度各
  4479筆。**低關注度組**：TRAIN IC=+0.0071(p=0.6863,n=3277)、VAL
  IC=+0.0117(p=0.6850,n=1202)，同號但幅度接近雜訊，500次洗牌null
  percentile=**31.2**（門檻90.0，遠未過）。**高關注度組**：TRAIN
  IC=+0.0097(p=0.6007,n=2928)、VAL IC=-0.0416(p=0.1017,n=1551)，
  **train/val正負號相反**，null percentile=89.8（門檻90.0，差0.2個
  百分點未過）。
- **意外之處（誠實記錄，不淡化）**：方向跟假設預期完全相反——經濟理由
  預期低關注度組訊號應該更強（散戶主導、資訊擴散慢、市場對低關注股
  反應不足），但實際上低關注度組（percentile=31.2）比高關注度組
  （89.8）明顯更弱，高關注度組反而只差0.2個百分點就過關。研判可能
  原因（皆為推論）：①趨勢外推對成交量大的股票營收序列可能本身更平滑
  雜訊更小；②20日均成交值是價量代理，不是法人持股比例/分析師覆蓋率
  這種更直接的關注度衡量，可能沒有精確捕捉文獻定義的「關注度」概念；
  ③分組後樣本數減半，可能讓原本就薄弱的訊號進一步稀釋。
- **這個死法能不能泛化**：**不泛化成「月營收驚喜×關注度分組這個機制
  方向完全沒用」**——只測了「線性外推trend殘差+成交值中位數分組」這
  一種具體組合，未測法人持股比例當關注度代理（`HYPOTHESIS_QUEUE.md`#21
  原本列的另一個候選）、未測moving average trend（只測了linear
  regression外推）、未測非對稱分組（僅取最低/最高十分位而非中位數
  對半分）。跟已FAIL的`#14`（`TRIALS_LEDGER.md`#80，純YoY全樣本，
  percentile=68.0）比較：這次改造後最好的子組（高關注度89.8）反而
  比#14全樣本（68.0）更接近門檻，暗示trend殘差這個新意外定義本身
  可能比原始YoY更貼近訊號，但分組切法本身沒有帶來預期的差異化效果，
  兩件事要分開看，不能因為分組沒差異化就否定trend殘差定義本身。
- **原始記錄**：`TRIALS_LEDGER.md`#91、`HYPOTHESIS_QUEUE.md`#21、
  `revenue_trend_surprise_low_attention.py`（新增，可重複執行）。
  佇列#21結案，接續佇列第一順位#22（品質×營收加速×法人吸籌複合訊號
  +低波動閘門）。

### 品質×營收加速×法人吸籌×低波動複合訊號 合取式overlay（HYPOTHESIS_QUEUE.md#22，2026-09-03FAIL）

**經濟理由**：假設edge存在於四個各自單測皆FAIL/邊緣的濾網（品質ROE/FCF、
月營收YoY加速度、三大法人連買、低波動）的**合取（AND）**而非任一單一維度
——各濾網分別砍掉不同失敗模式，單獨測時其餘失敗模式的雜訊蓋過該濾網
本身的訊號，合起來才會顯現。

**實作與結果**：`composite_quality_revaccel_inst_lowvol_sanity.py`（新增）+
`pit.py::cash_flow_pit()`（新增，本次補上，FinMind`TaiwanStockCashFlowsStatement`
無明確資本支出科目，用營運現金流CFO正當「FCF正」的簡化代理，非真FCF）。
100檔快取樣本、80檔可用、121個20交易日快照(2015-2024)。四個gate個別通過
率合理非退化（quality56.8%/rev_accel49.6%/inst_streak13.0%/low_vol49.2%）
——**但四者合取候選池14.0%快照有>=1檔候選（事前訂門檻30.0%，未過）、平均
候選池佔比僅1.7%**，且觀察值≈四個通過率連乘積(0.568×0.496×0.130×0.492≈
1.8%)，代表四個濾網彼此近似**統計獨立、無正向協同**——這直接推翻了假設
本身的核心前提（合取應該顯現單獨測不出的協同訊號）。額外發現：五個因子
同時非NaN的樣本量2015-2021全數為0、2022才轉正常，早期樣本資料交集近乎
全空，進一步削弱可測性。

**判定：FAIL（第1關sanity未過，依協定門檻事前綁定判定，不得因看到14.0%
比30.0%差不遠就事後放寬門柱）**，未進第2關以後。

**不泛化成什麼**：不泛化成任一單一濾網沒用（各自命中率個別皆非退化，
`f_quality_roe_stability`/`f_low_vol`因子層IC仍分別PASS/未受影響）——死的
是「四濾網AND合取」這個具體構造。未測OR邏輯、加權分數式組合、或放寬
個別門檻（例如inst_streak改用>0而非>=3天）的變體，未來若要重測需換其中
一種構造，不能沿用這次「四者皆嚴格AND」的失敗當證據。

完整數字見`TRIALS_LEDGER.md`#92、`HYPOTHESIS_QUEUE.md`#22。

### Piotroski F-score當價值榜排雷閘門（HYPOTHESIS_QUEUE.md#23，2026-09-03FAIL）

**經濟理由**：`value_board_v2`（B24-500）正式回測目前判定「不及格」，
alpha兩期皆不顯著（TRAIN p=0.2672、VAL p=0.1441）——假設診斷是價值榜
排序邏輯選到不少「便宜是因為基本面正在惡化」的價值陷阱股，稀釋了真正
被低估、體質健康股票的alpha。用Piotroski (2000) F-score（9項二元品質
指標）當候選池的排雷閘門（gate，不是排序因子），只留F-score夠高的
便宜股，被判定體質惡化的便宜股直接踢出候選池。

**實作與結果**：第1關sanity（`piotroski_fscore_sanity.py`，`TRIALS_LEDGER.md`
#93）先確認FinMind免費層9項指標欄位可算（7項直接對應、2項用文件化proxy：
CFO正近似FCF正、面額股本近似流通股數），F-score分布非退化（mean=3.29/
median=3.26，0-9分），但**F>=7候選池均值僅1.2%、F>=8均值0.0%**（在未經
value_board_v2篩選的一般樣本上）——判SANITY_PASS但誠實記錄候選池天生
偏薄的警訊。第2步（`piotroski_fscore_gate_v1.py`，`TRIALS_LEDGER.md`#94）
沿用B24-500既有快取，自適應門檻選擇（F>=8/7/6在24個抽樣再平衡日的平均
候選數皆不到TOP_N=20，退而求其次選F>=6，即最寬鬆的門檻）。**核心比較**
（使用者在#23事前明訂的判準）：
- 原始baseline：TRAIN alpha=+6.26%(p=0.2672)/mine_rate=25.3%/return=+75.87%；
  VAL alpha=+12.38%(p=0.1441)/mine_rate=16.9%/return=+85.52%。
- +F-score gate(F>=6)：TRAIN alpha=+7.92%(p=0.4743)/mine_rate=29.1%/
  return=+71.79%(591筆交易)；VAL alpha=+5.24%(p=0.1772)/mine_rate=5.7%/
  return=+33.31%(98筆交易)。

**判定：FAIL（依#23事前綁定的驗證改造判準直接快殺，未投入100次隨機
控制組成本）**——兩期alpha的p值皆變得**更不顯著**（惡化不是改善），
地雷率沒有一致改善方向（TRAIN惡化、VAL改善，一升一降，無法佐證統一的
「篩掉陷阱股」敘事），且VAL期出現明顯機會成本流失（return驟降+85.52%
→+33.31%、交易數718→98，候選池被F-score+流動性雙重篩選砍得太窄）。
使用者原話：「若加了gate後數字沒有實質改善，代表價值榜的問題不是陷阱
股，是別的原因」——本次結果正是這個「沒有實質改善」的情況，判死不需要
勉強護航F-score gate的效果。

**不泛化成什麼**：不泛化成「F-score排雷機制完全無效」——本輪只測了套在
B24-500已流動性篩選過的500檔候選池上、自適應選中最寬鬆F>=6門檻的具體
應用；sanity階段已誠實記錄未篩選樣本上F>=7/8候選池本就極稀薄，暗示
F-score要發揮排雷效果或許需要套用在更寬廣的候選池（例如全市場）才有
足夠空間同時滿足門檻與樣本數，這是未來若要重測的方向，不是本次結論
的一部分。也不代表原始`value_board_v2`的alpha不顯著問題已有解——這條
假設想解決的問題（價值陷阱稀釋alpha）本身仍未被證實或推翻，只確認了
「F-score gate」這個具體解法在這個候選池上沒有兌現。

完整數字見`TRIALS_LEDGER.md`#93/#94、`HYPOTHESIS_QUEUE.md`#23。

**⚠️2026-09-20重大可重現性疑慮（原子.四建置的副產品發現，非原本任務
範圍，意外查證出來）**：`piotroski_fscore_sanity.py`（產出上方#93
SANITY_PASS數字的腳本）自2026-09-03首次commit起，頂層就有
`from pit import balance_sheet_pit, cash_flow_pit, quarterly_pit`，
但`pit.py`裡**從未定義過`cash_flow_pit`**（用`git log --all -S
"def cash_flow_pit" -- research/pit.py`查整個git歷史，零命中）——
實測`import piotroski_fscore_sanity`直接拋`ImportError`。
`piotroski_fscore_gate_v1.py`（產出上方#94 FAIL數字的腳本）又
`from piotroski_fscore_sanity import _fscore_components`，代表它
**也一樣無法被import**。換句話說，**#93/#94這兩筆已登記的結果，
依現有程式碼完全無法重現**——現有`pit.py`從來沒有這個函式，這兩支
腳本理論上從2026-09-03起就不能執行。已補上`cash_flow_pit()`定義
（2026-09-20，見`pit.py`該函式docstring，沿用既有`balance_sheet_pit`/
`quarterly_pit`同一套「期末+45日」PIT假設），修好dangling import，
但**沒有回頭重跑#23驗證**——這不在本次任務範圍內，且#23早已結案兩週
以上、佇列已往前走到#24，貿然重跑可能得到不同數字但意義有限。**誠實
記錄可能性，不下結論**：(a) 也許2026-09-03當時的執行環境裡`pit.py`
真的有這個函式、後來某次commit意外遺漏了它（但整個git歷史檢查不到
任何蛛絲馬跡）；(b) 也許#93/#94的數字本身未經真實執行產生。兩者都
無法在事後補證，已登記為`PENDING_QUEUE.md`「稽核.七」。

**⚠️2026-09-20裁示【Q4前視與#23無法重現】二後續：已重跑，結果可
重現**——總司令裁示「一個跑不出來的登記結果比一個FAIL更糟，會讓
多重比較帳的N含有一筆無法驗證的東西」，要求重跑不得省略。修好
dangling import後重新執行`piotroski_fscore_sanity.py`（同時也套用
了同一輪修好的Q4法定期限PIT，因為`cash_flow_pit()`共用
`_pivot_with_statutory_pit()`）：

- **樣本**：300檔（跟原始100檔不同——`factor_ic.SAMPLE_SIZE`常數
  在這之間已演進為300，這是抽樣規模的既有變化，不是本次重跑刻意
  調整），123/300檔可用（原始47/100）。
- **F-score分布**：mean=3.27（原3.29）、median=3.40（原3.26）——
  **高度一致**。
- **候選池比例**：F≥7均值1.2%（原1.2%，完全相同）、F≥8均值0.1%
  （原0.0%，同樣趨近於零）。
- **判定：SANITY_PASS**（跟原始判定相同）。

**結論：#93的SANITY_PASS判定可重現**，核心發現（F-score候選池天生
偏薄）在更大樣本下依然成立，不是原始47檔小樣本的雜訊。`TRIALS_LEDGER.md`
已補註「2026-09-20重現驗證通過」（#290）。

**`piotroski_fscore_gate_v1.py`（#94最終FAIL判定）重跑結果
（`TRIALS_LEDGER.md`#291）：方向性結論重現，但非逐位元重現。**
baseline（原始`value_board_v2`）數字逐位元相同（不依賴財報PIT，
不受Q4修正影響）：TRAIN alpha=+6.26%(p=0.2672)、VAL alpha=+12.38%
(p=0.1441)，跟原登記完全一致。gated（F≥6）數字有變動：TRAIN
alpha=+7.92%→+8.85%（p=0.4743→0.3870）、VAL alpha=+5.24%→+5.96%
（p=0.1772→0.1371）——差異來源：(a) Q4 PIT修正改變F-score依賴的
財報可得日 (b) 本次重跑期間FinMind一度402冷卻，fscore僅184/486檔
算出，覆蓋率跟原始執行不同。**但判定FAIL的核心理由結構在新數字下
依然成立**：TRAIN期p值仍然惡化、mine_rate仍是「TRAIN惡化、VAL
改善」這種一升一降的不一致模式（跟原始25.3%→29.1%／16.9%→5.7%
同一種不一致，新數字18.8%→29.1%／14.9%→5.4%），缺乏兩期一致改善
方向這個核心判準沒有變，**FAIL判定維持**。

**#23最終狀態總結**：sanity（#93/#290）高度一致重現、gate_v1
（#94/#291）方向重現但數字因PIT修正+本次限流覆蓋率而有別，兩者
皆支持原FAIL結論可信，**不作廢原登記**，但誠實記錄數字差異的
來源，不假裝是逐位元重現。

---

### 除權息季節行為效應（HYPOTHESIS_QUEUE.md#24，2026-09-03FAIL）

**經濟理由**：台股7-9月除權息旺季，散戶「填息」信念+稅制驅動的棄息/
參與行為，是台股在地行為/稅制效應。

**實作與結果**：`ex_dividend_seasonal_sanity.py`（新增，用原始未還原
收盤價、複用`adjust.py::adjustment_events()`既有除權息解析）。100檔
快取樣本62檔可用，443筆純現金股利事件。**Sanity PASS**：7-9月事件佔比
69.8%（符合已知結構事實）、除息跌幅vs理論殖利率rho=+0.6858(p<0.0001)。
**三個cheap gate皆FAIL**：殖利率→除息前5日報酬null percentile=32.6；
殖利率→除息後20日報酬train/val正負號相反+percentile=83.0；旺季vs
非旺季填息率洗牌檢定20/60/120日percentile=87.0/86.2/60.6，皆未過90.0
門檻（旺季填息率確實較高+7.1~7.2pp，但未達顯著）。

**判定：FAIL**——依「事前綁定門檻不事後移動門柱」鐵律，87.0/86.2雖
接近90.0門檻仍判FAIL，不因接近而放寬。**不泛化成「除權息季節效應
完全不存在」**——只測了現金股利+殖利率當自變數+5/20日窗口+100檔樣本
這個具體組合，未測稅率級距分組（第1關方向性訊號未過，稅後淨alpha
前置條件未執行）、未測不同forward窗口。完整數字見`TRIALS_LEDGER.md`
#95、`HYPOTHESIS_QUEUE.md`#24。

### 月轉效應 Turn-of-Month Effect（HYPOTHESIS_QUEUE.md#25，2026-09-03FAIL）

**經濟理由**：Turn-of-month效應（Ariel 1987、Lakonishok & Smidt 1988）
——股市報酬系統性集中在月底最後一個交易日到月初前N個交易日這個窄
窗口，機構現金流時點（月薪提撥退休金/基金申購集中月初、月底windows
dressing）是經濟機制。指數層級（TAIEX），不涉及任何個股選擇。

**實作與結果**：`turn_of_month_gate.py`（新增），月轉窗口用實際交易日
序列判定（當月最後一個交易日+次月前N個交易日，N分別測3跟4，不用自然
日期近似），對照組是打散「哪些交易日算窗口」這個布林標籤本身（保留
原始報酬序列不變，N=200次洗牌置換）。TAIEX日報酬2010-2024（TRAIN
2694筆、VAL 969筆）。Sanity PASS：N=3窗口天數/年=47.8（預期約48天/年
附近，判定邏輯無bug）。**N=3**：TRAIN窗口內日均報酬+0.00084 vs 窗口外
+0.00012（diff=+0.00072），贏過洗牌null percentile=94.0（過關）；
**VAL窗口內+0.00008 vs 窗口外+0.00064（diff=-0.00056，方向完全反轉）**，
percentile=28.0（遠未過90.0門檻）。**N=4**：TRAIN diff=+0.00035
(percentile=79.0，未過)、VAL diff=-0.00029(percentile=37.5，未過)，
同樣train/val正負號相反。

**判定：FAIL（第1關cheap gate，兩種窗口定義皆train/val方向相反）**，
未進第2關以後。TRAIN期（2010-2020）效應方向正確且贏過洗牌null，VAL期
（2021-2024）完全反轉為負，暗示這個效應（若曾存在）樣本外未能延續，
或TRAIN期本身是特定年份雜訊巧合。**不泛化成「日曆效應類別完全沒用」**
——只測了TAIEX指數層級+N=3/N=4兩種窗口定義+2010-2024樣本，未測成分股
層級、未測其他N值、未排除已知市場崩盤月份對TRAIN期結果的槓桿影響。

完整數字見`TRIALS_LEDGER.md`#96、`HYPOTHESIS_QUEUE.md`#25。

### 全市場融資餘額成長率 Margin Debt Growth（HYPOTHESIS_QUEUE.md#26，2026-09-03FAIL）

**經濟理由**：全市場總融資餘額（散戶信用交易槓桿）快速成長代表市場
槓桿/擁擠度升高，文獻與實務界（美股margin debt研究）視其為市場脆弱
度領先指標——槓桿快速累積時對利空反應會被放大（強制斷頭連鎖賣壓）。
這是regime訊號，預期方向是「融資餘額成長越快，後續下檔風險（回撤
幅度）越大」，不預測報酬方向本身。資料源：TWSE官方全市場歷史數字
（`www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN`，非樣本估計），
662個週檔回補完成（2012-05-02~2024-12-31，100%涵蓋）。

**實作與結果**：`margin_debt_growth_gate.py`（新增）——週頻融資餘額
`.pct_change(4)`/`.pct_change(12)`近似20日/60日成長率，配對TAIEX日線
（`yf_price_client.py::fetch_yf_index`）算後續同長度窗口最大回撤幅度
（絕對值），測Spearman相關（融資成長率 vs 後續回撤幅度），對照組是
打散配對本身（保留兩邊各自時序不變，N=200次洗牌）。sanity：成長率
量級合理（4週成長率全樣本mean=+0.58%/std=6.46%/min=-32.9%/max=+21.6%，
非常數非爆炸值）。**20d(4w)窗口**：TRAIN(n=408) corr=-0.0490
(percentile=14.0)；VAL(n=190) corr=+0.0633(percentile=86.0)——
**train/val正負號相反**，兩期幅度皆<0.05門檻。**60d(12w)窗口**：
TRAIN(n=400) corr=-0.0954(percentile=3.5)；VAL(n=181) corr=+0.0870
(percentile=88.5)——**train/val正負號仍相反**，VAL percentile
88.5雖接近但未過90.0門檻。

**判定：FAIL（第1關cheap gate，兩種窗口定義皆train/val方向相反）**，
未進第2關以後。依「事前綁定門檻不事後移動門柱」鐵律，60d窗口VAL
percentile=88.5雖接近90.0門檻仍判FAIL，不因接近而放寬（比照#24的
87.0/86.2同一標準）。兩期方向不一致本身已足以否決，percentile是否
過線只是次要參考。**不泛化成「融資餘額槓桿水位這個維度完全無效」**
——只測了「週頻近似成長率+Spearman相關+同長度forward回撤幅度」這個
具體構造，未測不同回顧窗口（例如更長的季度尺度）、未測用融資餘額
水位（而非成長率）當訊號、未測非線性關係（例如只有極端高分位成長率
才有效應、中段成長率無訊號的可能性）。#5/#6/#8/#10仍未解鎖，佇列
#1~26全數結案（#26含建置地基+cheap gate測試），下一輪需重新確認外部
依賴或設計新假設軸#28（#27多因子z-score複合評分已排隊接續但尚未
開始，非本次結案影響範圍）。

完整數字見`TRIALS_LEDGER.md`#97、`HYPOTHESIS_QUEUE.md`#26。

### 多因子複合評分 z-score blend baseline（HYPOTHESIS_QUEUE.md#27，2026-09-04FAIL）

**經濟理由**：吸取#22硬AND合取過度擬合的教訓，改用z-score加總複合
GP+value_pb+revenue_surprise三個「經濟理由獨立、統計上低相關」的因子
（兩兩|corr|<0.4），做多複合分數最高分位，理論上分散各因子特異雜訊、
累加訊號。

**實作與結果**：`composite_zscore_v1.py`（cheap gate已CHEAP_PASS，
VAL mean_ic=+0.0826，null percentile=100.0）之後，依使用者原話額外
要求補測`composite_zscore_v1_random_control.py`——從`factors.py`實際
產出的全部25個f_*因子池抽3個+Uniform(-1,1)隨機權重，N=300 draws（跨
多輪session用checkpoint累積完成），比較baseline是否顯著贏過「任意
複合、隨便加權」。結果：baseline贏過隨機組合的percentile=**87.2**
（門檻90.0，未過），約12.8%隨機3因子加權組合的VAL IC強度與baseline
相當或更強。

**判定：FAIL**——依「事前綁定門檻不事後移動門柱」鐵律，87.2雖接近
90.0門檻仍判FAIL，不因接近而放寬（比照#24/#26同一標準），未做正交性
檢查/leave-one-factor-out，未進portfolio層構造。**誠實保留**：87.2
落在`CALIBRATION_PROBE.md`探針發現的「100檔樣本檢定力不足邊緣區」
型態附近，但該探針的修正手段（`SAMPLE_SIZE`100→300）針對的是單因子
橫斷面IC洗牌null機制，跟這裡「隨機因子組合分布」null機制不同，不能
自動套用，未來若要重測需獨立驗證更大樣本是否改變此結論。**不泛化成
「多因子z-score複合這個構造類別完全沒用」**——只測了GP+value_pb+
revenue_surprise這三個具體因子的等權組合，未測依驗證強度加權的版本。
完整數字見`TRIALS_LEDGER.md`#102、`HYPOTHESIS_QUEUE.md`#27。

### 市場廣度背離 Breadth Divergence 當regime擇時overlay（HYPOTHESIS_QUEUE.md#28，2026-09-04FAIL）

**經濟理由**：跟已FAIL的`#2`（CTA價格趨勢）/`#10`（TAIEX趨勢+波動度
regime，方法論框架非PASS/FAIL）/`#15`（波動度目標化）/`#26`（融資餘額
成長率）四者機制刻意做出區隔——這條測的是「指數上漲時，有多少比例個股
真的一起參與上漲」（廣度背離），不是價格趨勢、不是波動度水位、不是
槓桿水位。第1關sanity（`breadth_divergence_sanity.py`，`TRIALS_LEDGER.md`
#103）已確認`breadth_pct`非退化、危機run-up期領先惡化、觸發後前瞻報酬
較低，方向正確。

**實作與結果**：`breadth_divergence_overlay_v1.py`——把divergence_flag
轉成`exposure=0.3 if divergence_flag else 1.0`（shift(1)避免未來函數），
走GATE_SEQUENCE第2關（打亂exposure時序，N=100 draws，比照`vol_targeting_
v1.py`/`spillover_overlay_v1.py`同一套permutation null）。TRAIN：真實
overlay總報酬+62.86%（反而輸給買進持有+79.49%）、對打亂分布percentile=
54.0；VAL：真實overlay總報酬+42.96%（買進持有+56.36%）、percentile=51.0。
兩期皆遠低於90.0門檻，且貼在50附近（不是明顯偏低，是完全沒有加值）。

**判定：FAIL**——依快殺標準「已被控制組拆穿之偽影家族換皮」（改變曝險
力道）直接結案，未進第3關以後。第1關sanity驗證的方向性事實本身沒有錯，
但轉成具體規則後，**隨機時點降曝險達到的績效跟用breadth背離挑時機幾乎
沒有差別**——edge不在「用breadth背離挑降曝險時機」這個時序關係上，只是
「平均曝險比100%低」的效果。跟`vol_targeting_v1.py`（#15，percentile
8.0/3.0，同款死法但更極端）、`spillover_overlay_v1.py`（#19，第6關
逐年一致性FAIL）是這個佇列第三個「timing/overlay類」機制陣亡案例——
本佇列目前所有regime/擇時型變體全數FAIL（`#10`是唯一存活的，但那是
「方法論框架待套用」非PASS，且套用對象也還沒出現）。**不泛化成「市場
廣度這個概念完全沒用」**——只測了「TAIEX 20日動量+60日breadth變化」
這個具體二元背離定義+固定0.3/1.0曝險二元切換，未測連續函數版本（曝險
反比於breadth惡化程度，類似vol-targeting但用breadth當輸入）、未測不同
回顧窗口組合。完整數字見`TRIALS_LEDGER.md`#105、`HYPOTHESIS_QUEUE.md`#28。

### 等權重再平衡溢酬 Diversification Return / Equal-Weight Rebalancing Premium（HYPOTHESIS_QUEUE.md#29，2026-09-04FAIL）

**經濟理由**：設計出跟前28條在機制分類上真正不同的第三類假設——既非
①方向性選股排序（前28條中10條）、也非②timing/exposure overlay（前28條
中另一批），是③portfolio construction：給定同一組標的、不做任何選股
判斷、全程滿倉不做曝險縮放，純粹用「定期拉回等權重」這個機械式再平衡
動作本身測試Booth & Fama（1992）文獻定義的diversification return/
volatility harvesting效應。**基準操作化偏離原文的市值加權，改為t0等
權重buy-and-hold**（本專案無市值/流通股數資料源，避免新增資料工程，
理由見`HYPOTHESIS_QUEUE.md`#29條目）。

**死因**：走完第1~5關全數PASS——sanity（TRAIN/VAL溢酬+24.81pp/+31.72pp、
Sharpe/MDD同步改善）、隨機控制組（bootstrap抽80/159檔子集N=100 draws，
100/100 draws TRAIN且VAL同時為正，CHEAP_PASS）、參數密集高原
（`REBAL_FREQ`5~80交易日網格17/17點TRAIN/VAL皆正）、成本/稅/滑價
1x/2x/3x敏感度（三情境皆維持正溢酬，3x保守情境仍有+16.06%/+24.60%）、
leave-one-out（拿掉貢獻最大年份2020後剩餘複利溢酬+8.72%仍為正）——但
**第6關逐年一致性未過**：TRAIN期(2015-2020)6個年度中僅4個年度溢酬為正
（2015/2017/2018/2020，2016/2019為負），4/6=66.7%，未達事前訂定的
>=5/6=83.3%門檻，依快殺標準判定，未進第7/8/9關。

**這次死法的特殊之處（誠實記錄）**：是本佇列29條假設中通過關卡數最多、
死得最深的案例之一——跟`f_52w_high_prox`（#17）同一種死法（第3/5關
乾淨通過，第6關逐年一致性未過），兩者都證明了「效果存在、非隨機、
非集中在單一年份」但「年度方向本身不夠一致」是兩種獨立的問題，前面幾關
通不代表後面一定通。依`CLAUDE.md`復盤原則——這不是流程錯（GATE_SEQUENCE
本身沒問題，關卡設計正確抓到了這個弱點），是流程對但這條假設在這個具體
樣本/窗口下無edge夠強到通過。

**不泛化成什麼**：不泛化成「等權重再平衡/diversification return這個
機制在台股完全無效」——第1~5關已扎實證明效果存在，死的只是「這個具體
159檔快取樣本+2015-2020這個TRAIN窗口」的逐年一致性不夠。未來若要重測，
值得先檢查VAL期(2021-2024)逐年一致性是否更穩（VAL期整體報酬更平順、
Sharpe更高於TRAIN），或擴大樣本池到全市場而非300檔快取子集，但這是
未來獨立測試的變體，不是本次結果的一部分，不能拿本次FAIL反推「擴大
樣本應該會PASS」當結論。

**原始記錄**：`TRIALS_LEDGER.md`#107/#108/#110/#111/#112/#114、
`HYPOTHESIS_QUEUE.md`#29、`equal_weight_rebalance_sanity.py`／
`equal_weight_rebalance_control_v1.py`／`equal_weight_rebalance_plateau_v1.py`／
`equal_weight_rebalance_costs_v1.py`／`equal_weight_rebalance_leave_one_out_v1.py`
（皆新增，可重複執行）。佇列#1~29全數結案，剩餘#5/#6/#8/#10仍卡外部
依賴，下一輪需確認依賴是否解鎖，若仍未解鎖則佇列實質已空，需設計新
假設軸#30。

### 個股融資使用率 Margin Financing Utilization Ratio（HYPOTHESIS_QUEUE.md#30，2026-09-05 FAIL）

**經濟理由**：強制平倉/流動性螺旋（Brunnermeier & Pedersen margin
spiral機制）——個股融資使用率越高，一旦下跌越容易觸發追繳/斷頭賣壓，
是本佇列第五類機制（既非選股排序、timing overlay、portfolio
construction、也非配對交易）。

**死因**：`margin_utilization_regime_portfolio_v1.py`——regime-conditional
避開高融資使用率個股（危機regime挑最低使用率TOP20，非危機regime挑流動性
最高TOP20），控制組核心判準是打贏「危機期隨機選股」。結果：**TRAIN**
return-16.97%、alpha-4.18%(p=0.7512不顯著)、beta+0.737、隨機控制組
percentile=**1.0**（遠低於90.0門檻，且是本策略worse than 99/100隨機
對照組，直接牴觸假設核心主張）。**VAL**return+65.20%、alpha+8.94%
(p=0.4991不顯著)、beta+0.638、percentile=**99.0**（表面過90.0門檻）。
依本專案既有標準（alpha顯著性+beta拆解為最終判準，percentile表面過關
不夠），VAL期alpha遠不顯著+顯著beta曝險，加上TRAIN期決定性反證（worse
than幾乎全部隨機對照），判**FAIL**，未進第3關以後。

**這次死法的特殊之處**：TRAIN/VAL percentile劇烈不一致（1.0 vs
99.0）——不是「單期偶然」可以解釋的邊緣案例，暗示這個具體TOP20/regime
二元切換構造對樣本/期間高度敏感，不是穩健機制。

**不泛化成什麼**：不泛化成「強制平倉/流動性螺旋這個機制完全無效」——
因子層cheap gate（`TRIALS_LEDGER.md`#116）跟下跌段vs上漲段分組IC
（#117）都給出跟機制主張方向一致的證據（下跌段IC遠強於上漲段，約6.5
倍），死的是「TOP20純多方向、regime二元切換」這個具體portfolio構造。
未來若要重測，建議改用連續曝險縮放（而非二元regime切換）或改成放空/
避開性質的曝險降低（而非純多方向替代持股），並且要先查清楚為何TRAIN/
VAL方向會如此懸殊不一致，不能直接沿用這次的具體實作當作「機制已測過」
的證據。

**原始記錄**：`TRIALS_LEDGER.md`#116/#117/#120、`HYPOTHESIS_QUEUE.md`
#30、`margin_utilization_regime_portfolio_v1.py`（新增，可重複執行）、
`data/margin_utilization_regime_portfolio_v1_results.csv`。佇列#1~30
全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`
`value_board_v2`仍`回測未通過`、題材動能榜/未來性濾網仍`紙上交易中`，
無新進展），下一輪需設計新假設軸#31。

### 台指選擇權Put/Call成交量比率當市場regime/擇時訊號（HYPOTHESIS_QUEUE.md#31，2026-09-05 FAIL）

**經濟理由**：選擇權市場的部位分布反映法人對未來波動/方向的看法（Pan &
Poteshman 2006），Put/Call ratio長期是市場情緒/避險需求的經典指標——本
佇列第一次引入衍生性商品市場的部位資訊當market regime判定輸入，不是
既有股票市場資料換一個計算方式。

**死因**：`option_pcr_overlay_v1.py`——曝險規則為PCR在trailing 250交易日
窗口內的百分位排名低於30%時降曝險至0.3、否則維持1.0全曝險。結果：TRAIN
(2015-2020)防禦曝險天數占比27.7%、overlay總報酬**-36.91%**（同期買進
持有+55.93%）；VAL(2020-2024)防禦天數占比30.8%、overlay總報酬
**-17.57%**（同期買進持有+59.73%）——**兩期overlay都大幅跑輸買進持有**。
第2關隨機控制組（打亂exposure時序，N=100）TRAIN/VAL percentile皆
=100.0，真實策略打贏幾乎全部隨機打亂版本，但這只證明「這個防禦時機
安排比隨機亂降曝險損失更小」，不代表贏過買進持有本身——**這是本佇列
第一次出現「隨機控制組表面滿分過關、但策略本身仍是絕對虧損且大幅跑輸
基準」的組合**。第3關參數密集高原（threshold_pctl∈[0.10,0.40]×
exposure_down∈[0.0,0.6]共49個網格點，TRAIN期1x成本）僅7/49點(14%)報酬
為正，遠低於60%門檻，非一整片，登錄門檻點(0.30,0.3)本身報酬即為
-36.91%。依協定第3關未過直接結案，未進第5關以後。

**這次死法的特殊之處**：TRAIN(2015-2020)+VAL(2020-2024)台股都是持續
大多頭（買進持有各+55.93%/+59.73%），此防禦型overlay在近三成交易日
降曝險至0.3，機會成本在長多頭環境下遠大於任何危機情境下換來的下檔
保護——是防禦型/timing類overlay在持續多頭市場的典型失敗模式，跟本
佇列已FAIL的#10（`f_rel_strength_regime_switch`）同屬「表面訊號存在、
但轉成實際曝險規則後機會成本蓋過保護效益」的家族，但這條在第3關參數
高原就被快殺，比多數同類假設走得更快、更乾淨地確認失敗。

**不泛化成什麼**：不泛化成「PCR訊號本身沒用」——第1關cheap gate的時序
相關性（`TRIALS_LEDGER.md`#121）依然CHEAP_PASS（TRAIN r=+0.0611
p=0.0193、VAL r=+0.0587 p=0.0676，null percentile 98.2/94.0），死的是
「trailing百分位排名+單一固定門檻(30%)+二元曝險切換(1.0/0.3)」這個
具體overlay構造。未來若要重測，建議方向：①改用連續曝險縮放（訊號強度
按比例調整曝險，而非二元切換）取代單一門檻硬切換；②改用更極端的門檻
（例如只在PCR處於歷史極端低位如第5百分位才觸發，而非30百分位這種相對
常見的水準）以降低防禦觸發頻率、減少多頭市場的機會成本侵蝕；③考慮
PCR是否更適合當作選股層級的橫斷面訊號而非指數層級擇時訊號。這些都是
未來獨立測試的變體，不能沿用這次的具體實作當作「PCR overlay已經測過」
的證據。

**原始記錄**：`TRIALS_LEDGER.md`#121/#122、`HYPOTHESIS_QUEUE.md`#31、
`option_pcr_gate.py`／`option_pcr_overlay_v1.py`（皆新增，可重複執行）、
`data/option_pcr_aligned.csv`／`data/option_pcr_overlay_v1_run.log`
（皆gitignored）。佇列#1~31全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，
下一輪需依`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節設計新假設軸#32。

### fx_twd_gate（美元兌台幣匯率當資金外流/市場壓力regime訊號，股匯連動家族，2026-09-05 hypothesis_queue排程陣亡）

- **哪一關死的**：第1關cheap gate（GATE_SEQUENCE最便宜關卡）——train/val
  正負號不一致這一項判準未過，直接快殺，未進第2關以後。
- **具體數字**：訊號=台幣即期匯率`spot_sell`N(20)交易日變動率（事前綁定，
  貶值方向為正）；目標=TAIEX後M(20)交易日報酬。對齊後n=2388
  （2015-02-02~2024-12-02）。TRAIN(<=2020-12-31,n=1439)：Pearson
  r=**+0.0368**(p=0.1634)、洗牌null(N=500)percentile=**82.6**（未過90.0
  門檻）。VAL(2020-12-31~2024-12-31,n=949)：Pearson r=**-0.0723**
  (p=0.0258)、洗牌null percentile=**96.0**（過90.0門檻）。三項判準：
  幅度非零（\|r\|>0.01兩期）過；**train/val正負號相反（TRAIN正、VAL負）
  未過**；VAL贏過洗牌null過。三項判準之一未過即依協定結案。
- **方向解讀（附註，非判準本身）**：VAL期方向符合事前綁定的經濟預期
  （台幣貶值對應TAIEX後續報酬轉弱，負相關）且贏過洗牌null，是這條假設
  唯一支持經濟機制的證據；但TRAIN期方向相反（正相關）且未過null門檻，
  兩期矛盾的結果不足以支撐「股匯連動」這個機制在此具體實作下穩健存在。
- **這個死法能不能泛化**：**不能**泛化成「股匯連動這個經濟機制本身
  沒用」——這是本佇列第一次引入貨幣市場資料當regime輸入，只測過
  `spot_sell`單一即期匯率欄位+N=M=20交易日這一組事前綁定的具體窗口
  組合，未測其他匯率欄位（`cash_sell`零售匯率或buy/sell中價）、未測
  其他窗口長度（例如更短的5日捕捉急速資金外流、或更長的60日捕捉緩慢
  趨勢性貶值）。死法本身（train/val正負號不一致）跟本佇列已FAIL的
  #9殘差動量（`TRIALS_LEDGER.md`#76）、#11產業內相對強度（#77）、
  #13三大法人連續買超（#79）同一種模式——第1關cheap gate這類「單一窗口
  組合的方向不穩定」死法在本佇列已出現多次，暗示的教訓是事前綁定單一
  窗口組合、不做參數搜尋的第1關本身容易在方向不穩定的訊號上判死，這是
  設計上刻意的保守（避免動量尺），不是這條假設獨有的問題。
- **原始記錄**：`TRIALS_LEDGER.md`#123、`HYPOTHESIS_QUEUE.md`#32、
  `fx_twd_gate.py`（新增，可重複執行）、`data/fx_twd_aligned.csv`
  （gitignored）。佇列#32結案，佇列#5/#6/#8/#10仍卡外部依賴，下一輪
  需依`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節設計新假設軸#33。

### fred_yield_curve_gate（美國公債殖利率曲線10Y-2Y利差當全球風險regime訊號，公債市場家族，2026-09-05 hypothesis_queue排程陣亡）

- **哪一關死的**：第1關cheap gate（GATE_SEQUENCE最便宜關卡）——VAL期
  贏過洗牌null這一項判準未過，直接快殺，未進第2關以後。
- **具體數字**：訊號=FRED `T10Y2Y`利差水位本身（level，非變動率，
  事前綁定，理由是曲線形狀代表市場預期是一個狀態非速度）；目標=TAIEX
  後M(20)交易日報酬。對齊後n=2320（2015-01-05~2024-12-02）。
  TRAIN(<=2020-12-31,n=1406)：Pearson r=**-0.0636**(p=0.0171)、Spearman
  rho=-0.1050(p=0.0001)、洗牌null(N=500)percentile=**98.6**（過90.0
  門檻）。VAL(2020-12-31~2024-12-31,n=914)：Pearson r=**-0.0242**
  (p=0.4656)、Spearman rho=-0.0268(p=0.4187)、洗牌null
  percentile=**52.8**（未過90.0門檻，貼近50，等同雜訊）。三項判準：
  幅度非零（\|r\|>0.01兩期）過；train/val同號（皆負）過；**VAL贏過
  洗牌null未過**。三項判準之一未過即依協定結案。
- **方向解讀（附註，非判準本身）**：事前綁定的方向預期是利差水位本身
  應與未來報酬**正相關**（利差走低/轉負=風險上升=未來報酬應轉弱）——
  但TRAIN/VAL兩期實測方向皆為**負相關**，跟事前預期方向相反，且VAL期
  幅度小到貼近雜訊（percentile=52.8）。這代表這條假設不只「贏過null」
  這一關沒過，連方向本身都跟總經文獻預期相反，是本佇列少數「方向也錯+
  幅度也不顯著」雙重不支持的案例（多數已FAIL案例至少VAL期方向對但
  TRAIN方向錯，或反之，如#32；這條是VAL、TRAIN皆錯方向）。
- **這個死法能不能泛化**：**不能**泛化成「殖利率曲線這個總經領先指標
  本身沒用」——這是本佇列第一次引入公債市場資料當regime輸入，只測過
  `T10Y2Y`利差水位單一口徑+M=20交易日這一組事前綁定的具體窗口組合，
  未測利差N日變動率（速度而非水位）、未測不同預測窗口（例如更長的
  60~120日捕捉衰退傳導的較長時滯）、未測利差是否需要落後幾個交易日
  才傳導到台股（本次假設t日利差即刻對應t+M報酬，未考慮傳導延遲）。
  也未排除「10年期減2年期」這個特定利差定義是否適合台股（美國衰退
  領先指標的原始文獻脈絡是預測美國自身經濟/股市，不是台股，傳導路徑
  多了一層「美國衰退預期→全球risk-off→台股」的假設，這一層本身未被
  單獨驗證）。
- **原始記錄**：`TRIALS_LEDGER.md`#124、`HYPOTHESIS_QUEUE.md`#33、
  `fred_yield_curve_gate.py`（新增，可重複執行）、
  `data/fred_yield_curve_aligned.csv`（gitignored）。佇列#33結案，佇列
  #5/#6/#8/#10仍卡外部依賴，下一輪需依`HYPOTHESIS_QUEUE_PROTOCOL.md`
  第1節設計新假設軸#34。

### 銅金比 Copper/Gold Ratio 當全球成長/風險偏好regime訊號（HYPOTHESIS_QUEUE.md#34，2026-09-05 FAIL）

**經濟理由**：銅（工業金屬，需求跟全球製造業/營建景氣連動）對黃金（避險
資產）的比值，是總經圈廣泛引用的「風險偏好vs風險趨避」量化指標——本佇列
第一次引入「實體經濟供需」（商品期貨價格）當market regime判定輸入，跟
先前的#19/#31/#32/#33（皆來自金融市場參與者的部位或預期）資訊來源類別
不同。

**死因**：第1關cheap gate（`copper_gold_ratio_gate.py`，`TRIALS_LEDGER.md`
#125）本身CHEAP_PASS（TRAIN Pearson r=-0.2467 p<0.0001 null
percentile=100.0、VAL r=-0.1758 p<0.0001 null percentile=100.0，本佇列
timing類假設中訊號最強的一個），**但方向與事前綁定的正相關敘事相反**——
實測為負相關（銅金比走高，TAIEX後續報酬反而轉弱）。轉具體overlay規則後
（`copper_gold_ratio_overlay_v1.py`，方向已依實測負相關反轉：比值百分位
偏高才降曝險）：TRAIN(2015-2020,n=1507)防禦曝險天數占比23.2%、overlay
總報酬僅**+10.14%**（同期買進持有+52.41%，overlay本身已大幅跑輸基準）。
第2關隨機控制組（打亂exposure時序，N=100）TRAIN/VAL percentile皆
=100.0，第3關參數密集高原（threshold_high_pctl∈[0.60,0.90]×
exposure_down∈[0.0,0.6]共49個網格點，TRAIN期1x成本）44/49點(90%)報酬
為正，表面雙雙過關。**但第5關leave-one-out揭穿：TRAIN逐年報酬
2015~2020為-2.11%/+7.10%/+9.70%/-8.20%/+37.43%/-24.09%，複利總報酬
+10.14%幾乎全部由單一年份2019（+37.43%）貢獻，拿掉2019後剩餘複利總
報酬直接翻負為-19.85%**。依協定第5關未過（原本為正、拿掉最大貢獻年份
後翻負）直接快殺結案，未進第6關以後，VAL期數字（+124.09%）不納入最終
判定。

**這次死法的特殊之處**：跟`fut_basis_carry`（#35→#37，717x放大集中在
2000-2002三年）以及`equal_weight_rebalancing_premium`（#29，逐年一致性
4/6未過）同屬「表面關卡（隨機控制組/參數高原）都過、但拆解逐年貢獻後
發現集中度問題」的家族，是這個佇列第一次有overlay類假設死在第5關
（前面幾條timing假設多半死在第1/2/3關），比第1關cheap gate訊號更強
（|r|=0.18~0.25，本佇列timing類最強）不代表轉成overlay後就更穩健——
訊號強度跟策略構造穩健性是兩件事，這是本次最值得記住的教訓。

**不泛化成什麼**：不泛化成「銅金比這個訊號本身沒用」——第1關cheap gate
的時序相關性（`TRIALS_LEDGER.md`#125）依然CHEAP_PASS，死的是「trailing
百分位排名(WINDOW=250)+單一固定門檻(0.70)+二元曝險切換(1.0/0.3)」這個
具體overlay構造。未來若要重測，建議方向：①先做逐年拆解確認訊號本身
是否也集中在少數年份（本次尚未對「訊號」本身做這個檢查，只對「overlay
報酬」做，訊號集中度跟報酬集中度可能是同一個問題的兩面）；②改用連續
曝險縮放取代二元切換；③深挖「銅金比與台股負相關」這個反轉方向背後的
真實機制（可能是美元強弱/Fed政策預期同時驅動銅金比與台股的共同因子）
再決定是否值得重新設計規則。這些都是未來獨立測試的變體，不能沿用這次
的具體實作當作「銅金比overlay已經測過」的證據。

**原始記錄**：`TRIALS_LEDGER.md`#126、`HYPOTHESIS_QUEUE.md`#34、
`copper_gold_ratio_gate.py`／`copper_gold_ratio_overlay_v1.py`（皆新增，
可重複執行）、`data/copper_gold_ratio_aligned.csv`／
`data/copper_gold_ratio_overlay_gate3_grid.csv`／
`data/copper_gold_ratio_overlay_v1_run.log`（皆gitignored）。佇列#1~34
全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，下一輪需依
`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節設計新假設軸#35。

**補充（2026-09-06 馬拉松第384輪，TW軌，第二個獨立死因）**：回頭查核
第1關cheap gate（`TRIALS_LEDGER.md`#125，CHEAP_PASS，TRAIN/VAL null
percentile皆100.0）本身的判準可信度——`margin_debt_level_v1`
（`TRIALS_LEDGER.md`#143）發現完全打散`_shuffle_percentile()`框架對
「慢變訊號×重疊窗口目標」（本條目訊號是逐日幾乎不變的比值水位、目標是
TAIEX後20日重疊窗口報酬）會系統性低估虛無假設變異數。新增
`copper_gold_ratio_circular_shift_control.py`（保留訊號自相關結構的
circular-shift控制組，N=500，對照同N完全打散版）：**VAL期percentile
從100.0（完全打散）降到62.0（circular-shift，跌破90.0門檻），TRAIN期
從100.0降到95.6（仍過關）**。**確認：連第1關cheap gate本身的顯著性
都主要是自相關造成的假顯著，不是真實訊號**——這條候選現在有兩個獨立
死因：①本篇記錄的第5關集中度問題（單一年份2019貢獻全部overlay報酬）；
②第1關cheap gate本身在嚴謹控制組下就站不住腳。兩者互相印證，判定
FAIL維持不變（本來就已經FAIL，這只是加深确定性，不影響任何最終判斷）。
完整見`TRIALS_LEDGER.md`#147、`HYPOTHESIS_QUEUE.md`#34狀態更新、
`copper_gold_ratio_circular_shift_control.py`（新增，可重複執行）。

---

### 賣出台指選擇權波動度風險溢酬 VRP（HYPOTHESIS_QUEUE.md#35，2026-09-05 FAIL）

**經濟理由**：選擇權隱含波動度長期系統性高於後續實現波動度（variance
risk premium，Bakshi & Kapadia 2003），機制是市場對尾部風險的保險需求
使買方願付溢價、賣方能長期收取。跟前34條在機制類別上真正不同——不是
選股排序、不是timing/exposure overlay、不是portfolio construction、
不是配對交易均值回歸、不是強制平倉流動性訊號，是「結構性風險溢酬收取」
這第六種機制。

**資料可行性查證**：`TaiwanOptionDaily`（FinMind）不含隱含波動度欄位，
需從價格反推。採用Brenner-Subrahmanyam(1988)近似公式（ATM跨式價格≈
0.8×S×σ×√T），不需要利率/股利率假設、不需要數值解法，是VRP第1關最便宜
檢定的標準做法。

**第1關cheap gate：FAIL（邊緣案例，非乾淨無訊號）**。只用日盤月合約
（排除週合約避免涵蓋期間不對稱）、到期天數10~45天區間內最接近30天的
合約、離TAIEX收盤最近且call/put兩邊都有成交的價平履約價、每5個交易日
抽樣一次（降低同合約重疊窗口的序列相關）。TRAIN（n=292）：mean_spread
=+1.19pp、median=+2.01pp、pct(IV>RV)=74.0%、t檢定p=0.0004、Wilcoxon
p=0.0000（皆顯著）。VAL（n=190）：mean_spread=+0.76pp、median=+1.75pp、
pct(IV>RV)=63.7%、**t檢定p=0.0595（僅些微未過0.05）**、Wilcoxon
p=0.0002（顯著）。事前綁定三項判準：①幅度非零（\|mean\|>=1pp兩期）——
VAL的0.76pp未達標；②train/val同號且為正——過；③t檢定+Wilcoxon皆兩期
p<0.05——VAL的t檢定未過。任一項未過依協定直接判FAIL，不做主觀裁量。

**這次死法的特殊之處**：兩期中位數價差皆明顯為正（1.75~2.01pp）、
IV>RV天數占比皆過半、Wilcoxon（對離群值/偏態穩健的無母數檢定）兩期都
顯著，暗示VRP溢價本身可能確實存在，但均值法的t檢定在VAL期沒能兩期都
顯著。研判是**價差分布右偏（多數時間小額正值）但左尾有少數大幅負值**
（少數重大波動衝擊事件中RV暴衝遠超發行時的IV，例如市場急跌），這正是
VRP文獻本身描述的「多數時間穩定收租金、少數危機時刻大賠」尾部風險
特徵——不是資料或方法論bug，而是這個經濟機制的固有性質，卻同時是它在
事前綁定的均值t檢定下沒能兩期都顯著的直接原因。依`CLAUDE.md`「事前
綁定通過標準，絕不事後移動門柱」鐵律，本輪嚴格依已寫入`vrp_gate.py`
docstring的判準結案為FAIL，不因為Wilcoxon顯著、中位數漂亮就放寬標準
通融放行。

**不泛化成什麼**：不泛化成「台股VRP完全不存在」——這次只測了ATM月合約
（10~45天到期區間）+Brenner-Subrahmanyam近似公式+5日抽樣頻率這組具體
實作，未測不同到期天數窗口、未測更精確的Black-Scholes數值反推IV（可能
減少近似公式本身帶來的雜訊）、未做危機期間單獨拆解（例如排除2020Q1/
2022極端月份後價差分布是否更穩定）、未測中位數/robust統計量為主判準
的替代框架（本次判準以均值t檢定為主，若未來重測改以Wilcoxon/中位數為
主判準，需要事前重新綁定並說明理由，不能拿這次已跑出的數字回頭套用
新判準）。

**原始記錄**：`TRIALS_LEDGER.md`#127、`HYPOTHESIS_QUEUE.md`#35、
`vrp_gate.py`（新增，可重複執行）、`data/vrp_gate_observations.csv`／
`data/vrp_gate_sampled.csv`（皆gitignored）。佇列#1~35全數結案，剩餘
#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`仍未解鎖），下一輪
從新假設軸#36（個股融券使用率/借券成本當知情放空者訊號）第1關開始。

### portfolio_multifactor_v2_loo_no_low_vol（拿掉`low_vol`剩`eps_family`+
`revenue_surprise`兩因子子版本，train-only IC加權，股票，TW軌，
2026-09-05FAIL）

- **哪一關死的**：獨立樣本外驗證（`TRIALS_LEDGER.md`#118明列的第三個
  深挖前提，round346/353全程只用同一批`safe_pool_ids()[:300]`留下的
  缺口，round356/359/362補齊）——不是sanity/隨機控制組/成本敏感度這些
  常見早期關卡死的，是死在「換一批完全獨立的樣本重新估計權重之後」。
- **具體數字**：round353在原樣本monthly cadence／VALIDATION：
  alpha+12.26%（p=0.0489，名目<0.05）、percentile=100.0（N=100配對式
  隨機控制組）；round362在完全獨立的300檔新樣本（`safe_pool_ids()
  [300:600]`，重新計算train-only IC權重、不沿用舊樣本權重數字）monthly
  cadence／VALIDATION：alpha**+4.55%（p=0.5647，不顯著）**、
  beta+0.610、percentile=97.0（N=300）。
- **死因**：round356撰寫腳本時事前寫死判讀原則（避免看到結果才回頭
  解釋）——「若新樣本monthly alpha轉負、或p值遠高於0.05、或percentile
  明顯不到90，選擇偏誤假說得到支持，這個子版本應該維持FAIL/降級」。
  本輪p=0.565明確觸發「p值遠高於0.05」這一支（percentile=97.0其實仍
  過90，但單一分支觸發已足以判定，不需要三個條件同時成立）。核心
  死因是round346/353在同一批300檔上比較3個leave-one-out子版本（拿掉
  eps_family/拿掉revenue_surprise/拿掉low_vol）、挑「看起來最好」的
  那個（拿掉low_vol，monthly p=0.0489全場最低）——這個挑選動作本身
  就隱含多重比較，#118當時的備註已誠實承認這一點（「隱含多重比較，
  未經FDR/多重比較校正前不能視為通過」），本輪的獨立樣本測試提供了
  直接實證證據，不只是理論上的疑慮：換一批完全沒被這個挑選過程碰過
  的樣本、重新估計權重後，原本的近似顯著結果並未重現。
- **這個死法能不能泛化**：**能部分泛化——對這條馬拉松所有
  leave-one-factor-out式「試多個子版本挑最佳者」的方法論是一個直接
  警訊**，不是只死在這一個候選本身。未來任何類似「從N個變體裡挑出
  表現最好的那個」的探索流程，即使名目p值通過門檻，都應該預期存在
  類似的選擇偏誤風險，必須規劃真正獨立的樣本外驗證才能升格，不能
  只靠同一批樣本的成本敏感度/隨機控制組補強就視為完整。但**不泛化
  成「`eps_family`/`revenue_surprise`兩個因子本身無edge」**——這兩個
  因子各自的單因子IC測試（`TRIALS_LEDGER.md`#7/#8）早已PASS，沒有被
  推翻，死的是「拿掉low_vol的這個特定2因子組合子版本」這個具體構造。
- **依`CLAUDE.md`復盤原則分類**：流程對，這個假設本身無edge（不是流程
  錯）——round346/353的成本敏感度/隨機控制組/train-only權重估計流程
  本身正確，round362用同一套正確流程在獨立樣本上重新驗證，誠實地
  發現這個假設站不住腳，這正是流程應該做的事，不是流程失敗。
- **原始記錄**：`TRIALS_LEDGER.md`#131、`TW_LEADS.md`#13、
  `deep_dive_loo_no_low_vol_independent_sample.py`（round356新增，可
  重複執行）、`data/deep_dive_loo_no_low_vol_independent_sample.csv`
  （gitignored）。quarterly cadence獨立樣本本輪未執行（round353原樣本
  quarterly本就最弱、p=0.1162，monthly都已崩潰不太可能翻盤，未強制
  補測，若需要可設`DEEP_DIVE_CADENCES=quarterly`重跑同腳本補齊）。

### 個股融券使用率 Short Sale Utilization Ratio（HYPOTHESIS_QUEUE.md#36，2026-09-05 FAIL）

**經濟理由**：放空需要向券商借券，借券供給有限、需求越高代表市場上有
越多知情/悲觀投資人願付出借券成本建立空頭部位（Asquith, Pathak &
Ritter 2005；Cohen, Diether & Malloy 2007），高融券使用率是「知情
悲觀者集中出現」的訊號，事前綁定方向為負。跟前35條在機制類別上真正
不同——最接近的是#30融資使用率，但#30是散戶槓桿多頭斷頭賣壓（流動性
驅動、被迫平倉），這條是放空者主動選擇（資訊驅動、主動押注），機制
原理完全不同。

**哪一關死的**：不是早期便宜關卡死的，是GATE_SEQUENCE九關機械判準
全數走過一輪（第1/2/3/5/6/9關皆PASS）後，死在「TRAIN/VAL alpha
顯著性最終判斷」這一步——依既有「alpha顯著性+beta拆解才是最終判準」
同一把尺（#17/#29/#30等案例一致採用），TRAIN期（2015-2020，六年，
樣本較長的那一期）alpha年化+7.44%但**p=0.3717完全不顯著**、
beta=+0.310代表這期報酬有實質市場曝險成分；只有VAL期（2021-2024）
alpha年化+11.88%、p=0.0354顯著。單一期alpha不顯著，就代表那期報酬
主要是曝險而非訊號本身alpha，顯著性判準必須兩期都成立，不是任一期
成立就算數。

**跟既有先例的比較**：這個「TRAIN無訊號、VAL單獨顯著」型態，本佇列
已有處理先例——`#106`（`revenue_trend_surprise_low_attention`高關注度
組，`TRIALS_LEDGER.md`#106）出現TRAIN p=0.8105完全不顯著、VAL p=0.0002
單獨強顯著的組合，當時判斷是「這種模式增加了VAL期特定巧合（而非跨期
穩定真實edge）的疑慮」，沒有因為VAL顯著就放行列入候選，而是要求用
獨立樣本切分或不同期間切法複驗才能排除巧合。#36情況幾乎對稱（只是
TRAIN長但不顯著、VAL短卻顯著），顯著性出現在哪一期本身沒有理論上的
優先順序，同一把審慎的尺一致套用，不因為#36多走了幾關（第3/5/6/9關
機械PASS）就對這個核心問題放寬標準，這正是`CLAUDE.md`「事前綁定通過
標準，絕不事後移動門柱」要防的事。

**額外的誠實限縮，即使忽略上述alpha顯著性問題也不足以判PASS**：
`backtest/engine.py`不支援放空，整套測試（第2/3/5/6/9關）從頭到尾
只驗證了訊號的「多頭鏡像半邊」（融券使用率最低分位做多），原始假設
核心主張「放空高融券使用率股票有資訊優勢訊號」**從未被真正測試過**——
即使多頭鏡像半邊的alpha被證明顯著，也只能算對原假說的間接支持，不能
宣稱驗證了原始機制。第9關regime overlay疊加後另有代價需誠實揭露：
2022年對TAIEX是空頭年，但對這個選股訊號本身是獲利年（+25.53%），
大盤層級通用regime先驗仍把該年曝險砍到平均0.48、吃掉六成以上原有
報酬（overlay僅+9.49%），機械判準PASS不代表這組regime先驗是免費保險。

**這個死法能不能泛化**：**不泛化成「融券使用率/知情放空者訊號完全
無效」**——第1關cheap IC gate（`TRIALS_LEDGER.md`#129，train/val同號
皆負、null percentile=100.0）本身的橫斷面時序相關性存在性不受本次
判定影響，未來若要重測這個方向，正確的下一步應該是先擴充
`backtest/engine.py`支援放空、真正測試原始假說的放空腿，而不是繼續
在「多頭鏡像半邊」這個代理構造上打轉。死的是「用多頭鏡像半邊代理放空
假說、TOP20月頻換股」這個具體構造，不是這個經濟機制本身。

**依`CLAUDE.md`復盤原則分類**：流程對，這個假設本身無edge（不是流程
錯）——GATE_SEQUENCE九關的機械判準流程本身正確地跑完並誠實記錄了每
一關的結果，最終在alpha顯著性這道防線上誠實判死，沒有因為多走了幾關
或表面數字漂亮就放寬既有一致標準，這正是流程應該做的事。

**原始記錄**：`TRIALS_LEDGER.md`#129/#133/#134/#135/#136/#137、
`HYPOTHESIS_QUEUE.md`#36、`factor_ic_short_sale_utilization.py`／
`short_sale_utilization_portfolio_v1.py`／`short_sale_utilization_
gates.py`／`short_sale_utilization_gate5_loo.py`／`short_sale_
utilization_gate9_regime_overlay.py`（皆新增，可重複執行）。佇列
#1~36全數結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證仍未解鎖），
下一輪從新假設軸#37（全市場現股當沖比重當市場過熱regime訊號）第1關
開始。

---

## #37 全市場現股當沖比重（Day-Trading Ratio）當市場過熱regime訊號
（2026-09-06，第1關cheap gate即死，`hypothesis_queue`獨立排程軌）

**經濟理由**：現股當沖（同日買賣沖銷，不需交割款）集中反映短線投機客/
散戶交易熱度，Barber, Lee, Liu, Odean（2009，用台灣資料）證實台灣當沖
客整體是系統性虧損的noise trader，事前綁定假設：全市場當沖比重相對其
自身trailing歷史異常升高時，未來報酬應偏差（負相關）。跟本佇列前36條
機制不同——第一次使用「零售投機熱度／市場微結構」這個資料類別。

**具體構造（本輪測試的版本）**：訊號=當沖比重（TWTASU「當沖賣出成交
數量+資券互抵成交數量」/FMTQIK全市場成交股數）相對trailing 60個交易日
自身的百分位排名；目標=訊號日之後20個交易日TAIEX累積報酬；Spearman
相關+時序洗牌null（N=200，打散訊號時序保留報酬時序）。

**哪一關、哪一點失效**：第1關cheap gate。TRAIN期（2015-04-09~
2020-12-31，n=1401）有微弱訊號：corr=-0.0550（p=0.0396），洗牌null
percentile=98.5（單邊，過關）。**但VAL期（2021-01-01~2024-12-02，
n=950）訊號幾乎完全消失**：corr=-0.0042（p=0.8981，完全不顯著），
洗牌null percentile=60.0（門檻<=10.0，遠未過，貼近中位數等於「跟隨機
打散沒有分別」）。兩期方向都符合事前綁定的負號，但VAL期幅度
（\|corr\|=0.0042 < 0.02門檻）與統計顯著性雙雙消失，是典型「訓練期
過擬合雜訊、驗證期無訊號」形狀，不需要進第2關隨機控制組即可決定性
判死（依快殺標準「觀測層級就無訊號」）。

**這個死法能不能泛化**：**不泛化成「當沖比重／零售投機熱度這個資料
類別完全無效」**——只測了「trailing 60日百分位排名+20日forward
horizon+固定TWTASU/FMTQIK口徑」這一組事前綁定的具體構造，未測其他
trailing窗口（例如20/120日）、其他forward horizon（例如5/60日）、
或改用個股層級當沖集中度而非全市場加總比重。TRAIN期本身出現的微弱
訊號（percentile=98.5）也未必是純雜訊——不排除是2015-2020這段期間
的特定結構性巧合，本輪未深究，若未來要重測這個資料類別，應先換一組
不同的窗口參數而非直接判定整個資料源無用。

**依`CLAUDE.md`復盤原則分類**：流程對，這個具體構造本身無edge（不是
流程錯）——第1關cheap gate機制設計正確（事前綁定方向、train/val
切分、時序洗牌null），誠實地在VAL期訊號消失時判死，沒有因為TRAIN期
表面過關就放寬標準或跳過VAL期直接宣稱CHEAP_PASS。

**原始記錄**：`TRIALS_LEDGER.md`#146、`HYPOTHESIS_QUEUE.md` #37、
`day_trading_ratio_gate.py`（新增，可重複執行）、
`data/day_trading_ratio_aligned.csv`（新增）、
`twse_day_trading_client.py`/`twse_market_volume_client.py`/
`backfill_day_trading_ratio.py`（前幾輪新增的資料回補地基，本輪首次
用於正式gate測試）。佇列#1~37全數結案，剩餘#5/#6/#8/#10仍卡外部依賴
（本輪重新查證`BACKLOG.md`——B24仍`回測未通過`、題材動能榜/未來性
濾網仍`紙上交易中`，無新進展，未解鎖）。**下一輪需先確認依賴是否
解鎖，若仍未解鎖則佇列實質已空，需依`HYPOTHESIS_QUEUE_PROTOCOL.md`
第1節設計新假設軸（本輪因時間/預算考量，優先確保#37完整記錄，未在
同輪倉促設計下一條，留給下一輪處理，避免跟同機器`AlphaMarathon`
FUT軌重複測試已在`fut_cheap_gate.py`系列碰過的「三大法人期貨部位」
類機制）。**

## #38 大戶籌碼集中度（股東持股分級表）（2026-09-06，資料可行性
查證即死，`hypothesis_queue`獨立排程軌，上一輪鎖檔陳舊回收接續）

**經濟理由**：股東持股分級表（誰持有多少股）是週頻的慢變數，跟三大
法人買賣超（日頻資金流）、融資餘額（散戶槓桿水位）、融券使用率
（知情放空者）三者資料來源與更新機制完全不同——這是本佇列第一次
嘗試用「持股結構本身」當訊號：大戶（例如>=400張級距）持股占比上升
+散戶（<=1張級距）占比下降＝籌碼往少數人手上集中，可能代表知情
大戶正在吸籌；反向則可能是出貨給散戶，是台股籌碼分析裡常見但本
佇列從未測過的「籌碼安定度」概念。

**哪一關、哪一點失效**：連第1關cheap gate都還沒開始——死在資料
可行性查證這一步（比第1關更早，屬於協定第2節「快殺標準：資料不可
及（查證過真的沒有免費/合規來源）」）。查證過兩條路線都不可行：
(1) FinMind `TaiwanStockHoldingSharesPer`（股東持股分級表）需要付費
會員層級，免費層直接被拒（`holding_shares_per_probe.py`實測回傳
HTTP 400「Your level is free. Please update your user level.」）；
(2) 集保結算所（TDCC）官方確實有免費開放資料
（`https://openapi.tdcc.com.tw/v1/opendata/1-5`），但實測發現這個
open API**不支援日期參數查詢歷史週別**——不論帶不帶`date`參數，
永遠只回傳最新一週快照（實測當下回傳`資料日期=20260904`，`data=`
過去日期參數被忽略），等於沒有任何免費管道能取得多年期的PIT歷史
時間序列供回測使用。

**這個死法能不能泛化**：**不泛化成「大戶籌碼集中度訊號本身沒用」**
——經濟機制從未被真正測試，死的純粹是「目前免費/合規資料源查不到
可回測的歷史時間序列」這個工程限制。未來若要重測，唯二可行路徑是
(a) 付費升級FinMind會員層級（違反本專案至今「免費資料源」的一貫
原則，需要總司令另外裁示是否要花這筆錢），或(b) 自建TDCC官網互動
查詢頁面（`https://www.tdcc.com.tw/portal/zh/smWeb/qryStock`）的
逐週爬蟲、每週手動/排程回補一次並長期累積歷史庫（工程成本高、且
從「現在」才開始累積，無法回溯過去年份，不在本次評估範圍內）。

**依`CLAUDE.md`復盤原則分類**：流程對，非流程錯——事前有做資料
可行性查證（`CLAUDE.md`第七條「任何『拿不到』的結論，須先證明試過
三條路：主來源→備援→由已有欄位推導」），確實試過FinMind主來源
+TDCC備援兩條路都查證後才判死，沒有跳過查證就假設可行或假設不可行。

**原始記錄**：`holding_shares_per_probe.py`（新增，可重複執行，探查
FinMind路線失敗）、直接curl測試`https://openapi.tdcc.com.tw/v1/
opendata/1-5`（帶與不帶`date`參數皆回傳同一份最新週快照，未存檔，
純探查性質未新增快取檔案）、`TRIALS_LEDGER.md`#148、
`HYPOTHESIS_QUEUE.md` #38。佇列#1~38全數結案，剩餘#5/#6/#8/#10仍卡
外部依賴（本輪重新查證`BACKLOG.md`仍未解鎖），設計新假設軸#39
（0050/台灣50指數成分股調整事件效應，見`HYPOTHESIS_QUEUE.md` #39
完整內容），排隊第一，**資料可行性尚未查證，下一輪需先查證再決定
是否能開始第1關**。

---

## #39 0050/台灣50指數成分股調整事件效應（Index Reconstitution Effect）— FAIL（資料不可及，未進第1關）

**死因**：查證三條免費/合規路線——FinMind（無指數成分股相關dataset）、
TWSE openapi（掃描全144個端點，僅命中`/indicesReport/TAI50I`指數點數
時間序列與`/ETFReport/ETFRank`ETF排名，皆非成分股名單）、data.gov.tw
（網路搜尋無命中）——皆未找到「歷史成分股名單+調整生效日期」結構化
API。台灣指數公司（TIP）官方雖每季公布調整結果，但只以新聞稿/公告
網頁呈現，無可程式化回溯查詢的歷史API。依`HYPOTHESIS_QUEUE_PROTOCOL.md`
快殺標準「資料不可及」判死，經濟機制本身從未被測試。

**依`CLAUDE.md`復盤原則分類**：流程對，非流程錯——查證優先於投入，
避免重蹈#38「先寫完整假設定義才發現資料不可及」的覆轍，本次先探查
（`index_reconstitution_probe.py`）再決定，符合資料可行性查證應在
設計投入之前完成的教訓。

**不泛化聲明**：不代表「被動指數基金強制買賣壓力」這個機制類別本身
無效——若未來能取得可回溯的成分股調整歷史（例如手動爬公告PDF逐年
整理、或找到付費資料源），此假設值得重新評估，死的只是「目前免費
資料源沒有結構化歷史序列」這個工程限制。

**原始記錄**：`index_reconstitution_probe.py`（新增，可重複執行）、
`TRIALS_LEDGER.md`#149、`HYPOTHESIS_QUEUE.md` #39。佇列#1~39全數
結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`仍未
解鎖），下一輪需設計新假設軸#40。

### 庫藏股買回公告效應（Share Buyback Announcement Effect，管理層信心
信號事件研究，`HYPOTHESIS_QUEUE.md` #40，2026-09-06 hypothesis_queue
排程結案）

- **哪一關死的**：第1關cheap gate（CAR事件研究+隨機日期控制組），
  unconditional版跟執行率分組深挖版皆未過。
- **具體數字**：`buyback_car_gate.py`——抽樣100檔買回公告股票（母體
  725檔，`SAMPLE_SEED=20260906`），99檔取得可用還原股價，總可用事件
  265筆。TRAIN mean_CAR=+4.00%（t-test p<0.0001, n=215）、VAL
  mean_CAR=+2.12%（t-test p=0.0780, n=50），train/val同號，方向與
  事前綁定的正向假設一致，但**VAL期mean_CAR vs 200次隨機日期控制組
  （同一批公司、隨機挑非公告日當偽事件日）percentile=84.5，未過
  90.0門檻**（勉強未過，非決定性反證）。因為未達門檻屬「勉強」而非
  「遠低於」，且假設本身「台股特有考量」小節已預先寫明「宣告但執行率
  低」是cheap talk疑慮，依既有寫明的計畫做`buyback_car_gate_high_
  execution.py`執行率分組深挖（事前綁定門檻>=80%為高執行率組）：**高
  執行率組VAL percentile=78.0（n=23，樣本不足30）、低執行率組VAL
  percentile=85.0（n=27，樣本亦不足30）——高執行率組percentile反而
  低於低執行率組，跟「高執行率=真實信心表態應有更強CAR」的假設方向
  相反**，證明cheap talk稀釋假說無法解釋unconditional版本的未過關，
  執行率分組沒有拯救訊號。
- **這個死法能不能泛化**：**不泛化成「公司主動決策型事件驅動
  （corporate action event-driven）這個機制大類完全無效」**——這是
  本佇列第一次測試這個機制分類（跟已FAIL的#14月營收公布/#24除權息
  季節經濟機制不同，那兩者是被動揭露/機械調整，這條是管理層主動決策
  +signaling），只測了「20交易日forward horizon+CAR相對大盤超額報酬
  +100檔抽樣」這一組具體構造；也不代表「庫藏股宣告完全沒有市場反應」
  ——TRAIN期訊號存在且高度顯著（p<0.0001），VAL期方向一致且t檢定
  勉強顯著（p=0.078<0.10），只是幅度不足以在隨機日期控制組面前站穩
  90百分位這個事前綁定的高標準，且執行率分組排除了「訊號被cheap talk
  稀釋」這個最自然的補救解釋。死的是「unconditional pooled CAR
  event study，N=20交易日，100檔抽樣」這個具體判定，未來若要重新
  評估，值得考慮的方向：擴大樣本至全部725檔（提高VAL期事件數，目前
  VAL僅50筆是判定信心不足的主因之一）、測試不同forward horizon（如
  5/10日觀察即時反應強度是否更高）、或改用宣告金額佔市值比重當
  連續因子做cross-sectional排序而非事件研究pooled平均。
- **原始記錄**：`buyback_car_gate.py`、`buyback_car_gate_high_
  execution.py`、`mops_buyback_client.py`/`backfill_buyback_
  announcement.py`（資料回補地基，皆新增可重複執行）、
  `TRIALS_LEDGER.md`#150、`HYPOTHESIS_QUEUE.md` #40。佇列#1~40全數
  結案，剩餘#5/#6/#8/#10仍卡外部依賴，本輪因預算考量未設計新假設軸
  #41，下一輪從設計#41開始。

### portfolio_multifactor_v2（多因子組合策略家族，A_4pass/B_plus_value_pe，
equal/ic_weighted/regime_weighted×monthly/quarterly，含全部leave-one-out
子版本，股票，TW軌，2026-09-06整併結案）

- **哪一關死的**：alpha顯著性（`PORTFOLIO_STRATEGY_SPEC.md`規則第3關）。
  隨機控制組（第2關）從未是問題——A_4pass percentile=99.0、
  B_plus_value_pe percentile=100.0（N=100），MDD/Sortino/Sharpe全面優於
  買進持有大盤（VAL期MDD−8.4%~−8.7% vs 大盤−31.6%）；純粹卡在alpha
  p值始終高於0.05這一關，且樣本越大越明確不顯著（不是「差一點」）。
- **具體數字（依時序）**：(1) 原80檔驗證樣本最佳兩組合（A/IC加權/季頻、
  B/IC加權/季頻）alpha分別+10.40%/+10.26%，p皆=0.053，屬邊緣未過；
  (2) `CALIBRATION_PROBE.md`判定管線檢定力不足後，`SAMPLE_SIZE`
  100→300重跑（round327，298檔獨立樣本），同一格`ic_weighted`/
  `quarterly`p值驟降到0.5314、alpha only+3.05%，其餘5組合p值範圍
  0.2159~0.6451，全數遠高於0.05；(3) train-only嚴格樣本外權重
  （round340，排除權重本身看過VAL期表現的洩漏疑慮）：quarterly
  p=0.4314、monthly p=0.1996，方向略改善但仍不顯著；(4) leave-one-
  factor-out三個2因子子版本（round346）：拿掉`low_vol`monthly
  p=0.0489是唯一名目<0.05者，但這是「先看3個子版本挑最佳者」之後
  才看到的數字，隱含多重比較；(5) 該子版本換完全獨立300檔樣本重新
  估計權重複驗（round356/359/362，見上方`portfolio_multifactor_v2_
  loo_no_low_vol`條目）：p從0.0489回到0.5647，選擇偏誤假說得到直接
  實證支持，原本看似邊緣顯著的訊號未能重現。
- **這個死法能不能泛化**：**能，針對這個具體規格家族**——`f_value_pe`/
  `f_value_pb`/`f_rel_strength`/`revenue_surprise`/`eps_family`/
  `low_vol`六個成分因子的等權/IC加權/大盤位階情境加權三種混合方式、
  月/季兩種頻率、含或不含`f_value_pe`兩種因子版本、以及三種leave-
  one-out子版本，總計已測試遠超12種具體構造，全數卡在同一關（alpha
  顯著性），且樣本越大訊號越弱（不是雜訊縮小後訊號浮現，是訊號本身
  隨樣本增大而消失）——這是判斷「真的沒有可累加alpha」而非「檢定力
  不足」的標準模式。**不泛化成「多因子組合這個方法論本身無效」**：
  死的是這一組特定成分因子（已被個別驗證過的cheap-pass因子）用這幾種
  特定混合權重法組合起來後沒有可累加的alpha，不代表換一組完全不同的
  成分因子（例如`f_us_low_vol`/`f_us_value_bm`乾淨宇宙版本，round383/
  386/387正在測試中）用同一套組合框架也會失敗；也不代表regime overlay
  （危機降曝險，`CLAUDE.md`最高投資原則要求的強制overlay）本身沒有
  價值——只是在alpha都不顯著的前提下，continuing to layer regime
  overlay/下檔保護證明在這個家族上屬於錦上添花而非解決根本問題，
  故本輪判斷優先權應轉向尋找新的成分因子候選，而非在同一組已知
  無顯著alpha的因子上疊加更多結構。
- **原始記錄**：`TRIALS_LEDGER.md`#109/#118/#131、`LEADS.md`
  `portfolio_multifactor_v2`條目（round137/201/202/327/340/346/353/356/
  359/362完整數字）、`portfolio_backtest_v2.py`/`portfolio_backtest_v2_
  bigsample.py`/`train_only_ic_weight_bigsample.py`/`leave_one_factor_
  out_bigsample.py`/`deep_dive_loo_no_low_vol_independent_sample.py`
  （皆可重複執行）。子版本`portfolio_multifactor_v2_loo_no_low_vol`
  詳細死因見上方獨立條目。
- **2026-09-20補記（財報PIT.三，流程對但因子失效）**：Q4前視修正後（`TRIALS_REGISTRY`#292~#303，295檔bigsample，`PIT3_RERUN_RESULT.md`），修正臂VAL最小alpha p=0.083、12組無一p<0.06，「p=0.053接近顯著」證據作廢；死因分類＝**流程對、但因子（f_eps_growth/f_eps_surprise/f_revenue_surprise，見#287~#289）修正PIT後失效**，非流程錯誤。前視貢獻未被直接量化（原p=0.053出自80檔樣本，見`財報PIT.四`）。
- **2026-09-20補記（財報PIT.四，80檔樣本，分支(a)）**：以原p=0.053的80檔樣本（`TRIALS_REGISTRY`#304~#315，`PIT4_RERUN_RESULT.md`）重跑雙臂：legacy臂A_4pass/ic_weighted/季頻VAL alpha=+8.75% p=0.168（原+10.40%/p=0.053）→**舊數字不可重現、前視貢獻無法量化，不再追**。兩臂12格VAL平均差僅+0.32pp、方向不一致，無證據顯示Q4前視是主因；月頻兩格修正臂p=0.049/0.052但legacy臂同格0.081/0.089，屬12格未校正取最小、非預先指定格，**不得稱alpha殘存，仍FAIL**。死因分類維持＝流程對、因子失效。

### 內部人（董監事/大股東/經理人）持股轉讓 Insider Holdings Transfer
（`HYPOTHESIS_QUEUE.md` #41，informed trading信號，股票，TW軌，
2026-09-06接續第六輪結案）

- **哪一關死的**：地基pilot階段（非正式`factor_ic.py` cheap gate）的
  觀測層級無訊號。四輪nested樣本（同一seed逐步擴大，非重抽）序列：
  12檔/N=228/r=+0.0710/percentile=90.5 → 18檔/N=342/r=+0.0775/
  percentile=94.0 → 24檔/N=446/r=+0.0417/percentile=79.0 → 30檔/
  N=560/**r=-0.0089（符號翻轉為負）**/**percentile=47.5（貼在50
  附近，等同隨機猜測）**。
- **判定理由**：本輪決定性轉為無訊號——若真有穩健橫斷面訊號，
  percentile應隨樣本數增加趨於穩定，而非退化到接近50；符號在第六輪
  首次翻轉，打破前三輪「方向一致性」這個唯一穩定觀察，代表先前的
  一致性本身也只是小樣本雜訊尚未被打散。依協定「快殺標準：觀測層級
  就無訊號」判FAIL，未投入需數千筆額外請求（全市場300檔規模+涵蓋
  VAL期共約36季度，累計約3小時以上網路時間）才能達到的正式cheap
  gate規模——在觀測證據已如此決定性的情況下，這筆額外工程成本的
  預期價值很低。
- **這個死法能不能泛化**：**不能泛化成「內部人持股資訊完全不含
  alpha」這個經濟命題**，也**不是**#38/#39那種「資料不可及」死法
  ——MOPS互動頁`stapap1`確認接受任意歷史年月，資料源本身可行。只
  測試了：(a)「全體董監持股合計」單一彙總數字（未涵蓋經理人/持股
  逾10%大股東個別持股變化）、(b)季度頻率持股變動率（未測逐筆轉讓
  事前申報事件研究路線）、(c)僅TRAIN期(2016-2020)單一子期間（未
  做VAL期或跨期一致性測試）、(d)最多30檔有效股票（遠小於標準300
  檔規模）。未來若要重新評估，值得考慮方向：改用逐筆轉讓事件研究
  （比照#40買回股份CAR框架）、擴充經理人/大股東持股明細、或找更
  省請求量的全市場查詢路徑。
- **原始記錄**：`mops_insider_holdings_probe.py`/`mops_insider_
  holdings_client.py`/`backfill_insider_holdings.py`/`insider_
  holdings_pilot_ic.py`（皆新增，可重複執行）、`TRIALS_LEDGER.md`
  #155、`HYPOTHESIS_QUEUE.md` #41。佇列#1~41全數結案，剩餘#5/#6/
  #8/#10仍卡外部依賴，本輪因預算考量未設計新假設軸#42，下一輪從
  設計#42開始。

## 個股間平均成對相關係數 Average Pairwise Correlation
（`HYPOTHESIS_QUEUE.md` #42，regime訊號，股票，hypothesis_queue軌，
2026-09-06結案）

- **哪一關死的**：第1關cheap gate，事前綁定方向判準未過。
- **判定理由**：對300檔快取宇宙trailing 60日窗口用z-score恆等式算平均
  成對相關係數（避免O(N^2)逐對計算），訊號=該值相對自身歷史百分位，
  預測未來20日TAIEX報酬。TRAIN Spearman=+0.0447（p=0.2247不顯著）、
  VAL Spearman=+0.1528（**p=0.0000高度顯著**），但事前綁定方向為負
  （相關係數升高→未來報酬轉差），實測兩期皆為**正**號——訊號本身
  確實存在且VAL期非常顯著，但方向與Longin & Solnik(1995)假設相反。
  依「事前綁定方向，不因結果換方向」鐵律判FAIL，不因為統計顯著就
  放寬方向判準通融放行。
- **這個死法能不能泛化**：**不能泛化成「橫斷面共同運動結構這個資料
  維度沒有訊號」**——訊號存在性本身被兩期資料證實，尤其VAL期p值極端
  顯著，死的只是「危機時降曝險」這個具體方向假設。可能的解釋是相關
  係數升高常伴隨恐慌拋售後的V型結構性反彈（齊漲），而非持續下跌，
  跟`#15`波動度目標化「追高殺低型timing系統性落後於急速反彈」屬同一
  類機制陷阱。**不泛化成計算方法有誤**——z-score恆等式算出的相關係數
  量級（mean=0.1413, std=0.0817）跟文獻上台股個股相關係數量級吻合。
  未來若要重測，應設計一條全新事前綁定的「相關係數升高後加碼」反向
  假設，不能直接沿用這次結果換方向重判。
- **原始記錄**：`avg_pairwise_correlation_gate.py`（新增，可重複執行）、
  `TRIALS_LEDGER.md`#157、`HYPOTHESIS_QUEUE.md` #42。佇列#1~42全數
  結案，剩餘#5/#6/#8/#10仍卡外部依賴，本輪因預算考量未設計新假設軸
  #43，下一輪從設計#43開始。

## #43 三大法人買賣超集中度（Institutional Buying Concentration）— FAIL（2026-09-06）
- **假設**：三大法人買賣超金額在個股間分布集中度（narrow leadership）升高
  →未來20日TAIEX報酬轉差（事前綁定方向為負）。
- **死因**：兩個候選指標（HHI/Top10比例）train/val皆顯著正相關（hhi兩期
  p<0.001，top10 VAL p=0.0094），方向與假設相反——集中度升高反而預示
  未來報酬更好。依「事前綁定方向，不因結果換方向」鐵律判FAIL，跟`#42`
  同一種死法（訊號存在但方向相反）。
- **不泛化成**：資金流集中度這個資料維度沒有訊號——訊號存在性被兩指標
  兩期資料證實，死的只是「集中度升高應降曝險」這個具體方向假設。
- **原始記錄**：`institutional_concentration_gate.py`（新增，可重複執行）、
  `TRIALS_LEDGER.md`#161、`HYPOTHESIS_QUEUE.md` #43。佇列#1~43全數
  結案，剩餘#5/#6/#8/#10仍卡外部依賴，下一輪從設計#44開始。

## #44 景氣對策信號 NDC Business Cycle Composite Signal — FAIL（2026-09-06，資料不可及）
- **假設**：NDC景氣對策信號燈號/分數轉紅燈或連續轉差→未來3~6月TAIEX報酬轉差（逆向）。
- **死因**：官方唯一免費合規管道（data.gov.tw ZIP）只提供回溯修正後最終版數字，無「當時發布版」欄位；官方查詢系統/新聞稿對一般請求403（依鐵律不偽造UA繞過）；Wayback Machine快照未涵蓋逐月分數內容，重建vintage需大型逐月爬取工程。假設本身事前寫明「做不到當時發布版則判資料不可及」，依此快殺。
- **不泛化成**：景氣對策信號本身無訊號——訊號經濟機制從未被測試，死的是「免費合規管道重建無look-ahead污染PIT版本」這個工程限制。
- **原始記錄**：`TRIALS_LEDGER.md`#164、`HYPOTHESIS_QUEUE.md` #44、`research/data_cache/ndc/`（原始ZIP）。佇列#1~44全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，下一輪從設計#45開始。

## #45 存託憑證（ADR）溢價/折價收斂 — FAIL（2026-09-06，訊號集中在單一巨型股，外部效度未證明）
- **假設**：台灣公司在美掛牌ADR（TSM/UMC/CHT/ASX）與台股本地價之間的
  premium顯著為正（ADR隱含價值高於本地價）→本地股價將上漲收斂價差
  （事前綁定方向：正相關，做多訊號）。經濟機制是存託契約可轉換性帶來的
  結構性套利錨點，跟已FAIL的`#16`配對交易（純經驗相關無結構錨點）、
  `#19`跨市場隔夜外溢（大盤層級資訊擴散，非個股自身收斂）皆不同類別。
- **死因**：第1關pooled四檔（TSM+UMC+CHT+ASX）表面CHEAP_PASS（TRAIN
  r=+0.0640/VAL r=+0.1242，皆p=0.0000、null percentile=100.0），但
  逐檔拆解揭露異質性：VAL期只有TSM(+0.1380)與ASX(+0.1114)顯著同號，
  UMC(+0.0221,p=0.4967)/CHT(-0.0157,p=0.6296)皆不顯著且CHT方向反轉。
  依事前訂好的「排除TSM對照重跑」判死規則，改用僅UMC+CHT+ASX三檔
  重跑後，**train/val符號直接翻轉**（TRAIN r=**-0.0364**(p=0.0066)、
  VAL r=**+0.1094**(p=0.0000)），第2項判準（同號）決定性未過，即使
  VAL單獨仍以percentile=100.0贏過null也不放行——依`#42`/`#43`已建立
  的「事前綁定判準不因單項統計顯著就通融」同一把尺，符號不一致本身
  就是判死理由。排除TSM後只剩ASX一檔兩期皆顯著同號，經濟意義上等同
  「單一標的擇時」而非本假設核心主張的「跨標的普遍存在的收斂機制」。
- **不泛化成**：ADR溢價/折價收斂這個跨市場套利機制完全無效——ASX兩期
  獨立看訊號仍顯著同號，且第1關cheap gate方法論本身乾淨（逐標的內部
  時序洗牌null正確處理了N=4小樣本問題，不是設計瑕疵）；死的是「四檔
  台灣ADR上普遍存在可交易的收斂訊號」這個具體主張，pooled層級的表面
  CHEAP_PASS主要由TSM（樣本列數最多、n=4673）撐起。未查證UMC/CHT
  2006-2010比率變更公告以擴大樣本（已是決定性判死結果，投入額外資料
  工程去擴大一個已判死的樣本不符合成本效益，是「本輪未做」而非「資料
  不可及」）；既有回測引擎不支援放空，本假設從頭到尾只設計測試了
  premium為正的多頭鏡像半邊，折價半邊完全未測試。
- **原始記錄**：`adr_convergence_probe.py`、`adr_premium_assembly.py`、
  `adr_premium_gate.py`、`adr_premium_gate_ex_tsm.py`（皆新增，可重複
  執行）、`data/adr_premium_aligned.csv`、`data/adr_premium_panel_with_target.csv`、
  `TRIALS_LEDGER.md`#168/#169、`HYPOTHESIS_QUEUE.md` #45。佇列#1~45
  全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，下一輪從設計#46開始。

## #46 新股上市長期弱勢 IPO Long-Run Underperformance — FAIL（2026-09-06，第1關cheap gate觀測層級無訊號）
- **假設**：新上市股票距上市日的交易日天數（`f_listing_age_days`）與未來
  報酬正相關——上市越久的股票，預期未來報酬優於新上市股票（事前綁定
  方向為正，源自Ritter 1991"The Long-Run Performance of Initial Public
  Offerings"承銷定價偏樂觀+初期投資人情緒消退的被動衰減機制）。跟本
  佇列已測過的七種機制（方向性選股排序/timing overlay/portfolio
  construction/配對交易均值回歸/強制平倉流動性驅動賣壓/公司行動事件
  驅動/跨市場套利收斂）皆不同——這是第八種：純粹的「事件時鐘」，不涉及
  任何人的主動決策。
- **死因**：`factor_ic_ipo_listing_age.py`第1關cheap IC gate，300檔抽樣
  中248檔有效（僅覆蓋TWSE現存上市公司，見下方局限說明）。TRAIN
  mean_ic=+0.0036（幾乎為零）、VAL mean_ic=-0.0029（符號翻轉為負）、
  null percentile=**13.4**（需>=90.0，且遠低於50——比隨機打散時序的
  對照組表現還差），依快殺標準「觀測層級就無訊號」判定，三項判準
  （VAL量級/train-val同號/贏過洗牌null）全數未過，是決定性反證非
  邊緣未過。
- **過程記錄（誠實揭露，非死因本身）**：本輪執行時先發現一個實作bug——
  `factors.py::_listing_age_days()`把`price_df`的`date`欄位（dtype為
  str）直接與`pd.Timestamp`相減，300檔中159檔全數factor ERROR、
  train/val皆n=0 dates，若照這個假結果記錄會誤判。已定位並修復
  （加`pd.to_datetime(dates)`轉型），修復後重跑才拿到上述248/300檔的
  真實結果，本次FAIL判定基於修復後的乾淨執行，不受此bug影響。
- **不泛化成**：「新股長期弱勢」這個文獻異常在美股不存在——本測試只
  覆蓋(a) TWSE現存上市公司（排除已下市383家，未緩解存活者偏差，
  且存活者偏差方向若存在會讓弱勢訊號被低估而非高估，跟本次觀測到的
  「無訊號」結果同向不衝突）、(b) 只用「上市天數」單一連續變數，未做
  依`HYPOTHESIS_QUEUE.md`#46已揭露的「控制市值後」分組對照（因訊號
  本身在觀測層級已無方向性，未達需要做混淆排除的門檻）、(c) 未納入
  TPEx上櫃公司（第1關前已查證TPEx終止上櫃清單不可及，本輪只做
  TWSE子樣本）、(d) 台股市場結構（IPO承銷制度、蜜月期漲跌停限制、
  三大法人參與度）跟美股原始文獻樣本（美國IPO市場）本質不同，本次
  結果不能反推「Ritter 1991發現的美股IPO長期弱勢異常不存在」，只能
  說「這個機制在台股TWSE現存公司子樣本、用距上市天數這個簡單連續
  代理變數上，觀測層級量測不到訊號」。
- **原始記錄**：`build_twse_listing_dates.py`（新增，可重複執行）、
  `factor_ic_ipo_listing_age.py`（新增，可重複執行）、
  `research/data/twse_listing_dates.json`（新增，1094檔TWSE現存上市
  公司官方上市日期快取）、`factors.py::f_listing_age_days`/
  `_listing_age_days()`（新增因子，已修復date dtype bug）、
  `TRIALS_LEDGER.md`#175、`HYPOTHESIS_QUEUE.md` #46。佇列#1~46全數
  結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證仍未解鎖），下一輪
  從設計#47開始。

## #47 處置股解除後價格反轉 Post-Disposition-Stock Price Reversion — FAIL（2026-09-06，資料不可及，未進第1關）
- **假設**：近期曾被交易所列入處置措施（分盤交易）的股票，處置解除後
  forward報酬顯著較差（事前綁定方向）——第九種機制：交易所監理干預
  （官方對「投機炒作過熱」的認定訊號），跟已FAIL的#30個股融資使用率
  （槓桿驅動強制平倉）核心區別在於這是監理機關主動認定，不涉及持有人
  槓桿部位。完整經濟理由見`HYPOTHESIS_QUEUE.md`#47。
- **死因**：資料歷史回溯深度不足，不支援`train(2015-2020)/val(2021-2024)`
  分期，依#47事前綁定的快殺標準「資料不可及」判定，未進入第1關cheap
  gate。四來源查證（依`CLAUDE.md`「搜尋紀律：三來源查證」，缺(3)但
  (1)(2)(4)三類一致）：
  1. TWSE官方openapi `v1/announcement/punish`——單次GET確認`stat=200`，
     僅8筆，涵蓋日期`1150831`~`1150904`（民國115年即2026-08-31~
     2026-09-04），n_unique_dates=4。
  2. TWSE舊版rwd端點`www.twse.com.tw/rwd/zh/announcement/punish`——
     `date`查詢參數對回傳內容無作用，回傳同一組「當前處置中」快照，
     確認是即時公告牆而非可查詢的歷史封存。
  3. TPEx官方openapi `v1/tpex_disposal_information`——單次GET確認
     `stat=200`，僅18筆，涵蓋`1150826`~`1150903`，n_unique_dates=6，
     同一種只回傳近期快照的模式。
  4. FinMind `TaiwanStockDispositionSecuritiesPeriod`資料集——確認
     存在（`https://finmind.github.io/tutor/TaiwanMarket/Chip/
     #taiwanstockdispositionsecuritiesperiod-backersponsor`），但API
     回應400「Your level is free. Please update your user level」，
     即這是付費層級資料，依`CLAUDE.md`「取得方式鐵律」標記**待採購**
     （確切價格需登入查看，本輪未深入查價，因不涉及採購決策）、未
     嘗試任何繞過手段。
  兩個官方免費端點（TWSE/TPEx）各自的swagger.json逐一確認`punish`/
  `disposal`相關路徑都只有這一條，沒有帶歷史區間查詢參數的替代端點。
  FinMind把同一類資料包裝成付費資料集這件事本身是第四來源的佐證：
  獨立商業供應商認定這份歷史資料值得收費打包，反推「官方免費端點沒有
  歷史深度」不是本輪查證疏漏，而是市場端已給出確認。
- **不泛化成**：「處置股解除後價格路徑」這個機制假說完全不可測——只
  確認了「TWSE/TPEx免費openapi端點+FinMind免費層」這個具體資料源組合
  缺乏歷史深度。`HYPOTHESIS_QUEUE.md`#47原查證清單提到的替代管道
  （TWSE網站html歷史新聞稿封存）本輪未查證，若未來重新評估可以從那
  個方向繼續，但依快殺標準，這條在馬拉松自動迴圈裡到此結案。
- **原始記錄**：`TRIALS_LEDGER.md`#176、`HYPOTHESIS_QUEUE.md` #47
  「最終判定」段落。全程零因子計算、零回測、僅4次唯讀GET請求（3個
  官方免費端點各1次+FinMind 1次直接被400拒絕），零FinMind額度消耗
  進入正式抓取流程。

## #48 董監事及大股東股權質押比例 Controlling Shareholder / Insider Share
Pledge Ratio — FAIL（2026-09-06，第1關cheap gate未過）

- **假設**：董監事/經理人/十%以上大股東質押股數佔持有股數比例（`board_
  pledge_pct`）越高（或近期上升），未來forward報酬顯著較差／下檔風險
  較高（公司治理／代理成本風險機制，Anderson & Puleo 2020；中國市場
  股權質押文獻）。
- **方法**：`irb130_pledge_gate.py`——300檔快取宇宙（seed=20260822，
  同`#42`/`#43`）中198檔在`irb130_pledge_combined.csv`（MOPS `IRB130`
  月頻全市場sii+otc彙總表，`backfill_irb130_pledge.py`回補
  2015-01~2024-12共240次請求全數成功）有紀錄，逐月PIT對齊（月底+1個
  月緩衝當可得日，避免look-ahead）+`adjusted_price_series`算forward
  20交易日報酬，兩個訊號口徑（`pledge_level`水位/`pledge_mom`MoM差分）
  各自跑pooled panel Spearman相關+N=200時序洗牌null對照。
- **結果**：
  - `pledge_level`（依TRAIN期樣本數選定為主要指標，n=11384 vs
    `pledge_mom` n=11206）：TRAIN corr=+0.0044(p=0.6354)、VAL
    corr=+0.0153(p=0.1694)，**兩期皆為正號，與事前綁定的負相關方向
    相反**。
  - `pledge_mom`（對照指標）：TRAIN corr=-0.0012(p=0.8952，幾近純
    雜訊)、VAL corr=-0.0205(p=0.0665，僅邊緣未達p<0.05)，同號但TRAIN
    幅度遠低於0.02門檻。
- **判定**：**FAIL**——`pledge_level`依「事前綁定方向、不因結果換
  方向」鐵律（同`#42`/`#43`）判死；`pledge_mom`屬「TRAIN無訊號、VAL
  單獨邊緣顯著」不放行的既定模式（同`#36`/`#106`先例）。主要指標已
  FAIL，未進第2關以後。
- **本輪額外發現並修正的方法論bug（重要，記錄供未來新腳本參考）**：
  原本比照`day_trading_ratio_gate.py`(#37)/`institutional_concentration_
  gate.py`(#43)/`avg_pairwise_correlation_gate.py`(#42)沿用的單邊有號
  null percentile公式`pctl=100*mean(shuffled>=real_corr)`（用於「事前
  綁定負相關」的顯著性判準，門檻`<=10.0`），用模擬資料（見
  `MARATHON_LOG.md`本輪心跳）驗證證實這個公式的方向解讀跟腳本自己的
  註解相反：真實負相關越強，算出的percentile越接近100而非接近0——
  正確的解讀應該是**高percentile=顯著**，跟那三支腳本沿用的`<=10.0`
  門檻剛好相反。改採`factor_ic.py`（本佇列驗證最多次、最穩健的版本）
  「null取絕對值比較、方向另外用same_sign獨立檢查」慣例後才重跑拿到
  上述結果。**已逐一覆核`#37`/`#42`/`#43`三個已結案判定，證實這個
  公式方向問題不影響它們的最終FAIL結論**：`#42`/`#43`本就因train/val
  同號但方向與事前綁定相反、在same_sign檢查那一關就已定案FAIL，從未
  依賴這個有問題的null percentile數值；`#37`VAL期真實相關係數本身
  幾乎為零（corr=-0.0042,p=0.8981），在任一種percentile公式下都會落
  在~50附近、遠不顯著，結論不受影響。三者皆**不需重新開案**，但提醒
  往後任何新設計的regime/overlay類gate腳本一律採`factor_ic.py`的
  絕對值null慣例，不要再複製這個方向錯誤的公式。
- **不泛化成**：「股權質押這個資料維度完全無效」——只測了「全體董監
  持股合計質押比例」單一彙總數字（`IRB130`彙總表未拆分揭露經理人/
  十%以上大股東個別細項）+月頻+forward 20交易日單一構造，未測其他
  forward horizon、未做「控制市值後」的分組對照（`#48`事前列的已知
  混淆風險之一，因第1關本身已FAIL不需要走到那一步）、未測放空高質押
  比例股票這個鏡像半邊（既有引擎不支援放空，同`#36`/`#45`/`#46`教訓）。
- **原始記錄**：`TRIALS_LEDGER.md`#178、`HYPOTHESIS_QUEUE.md` #48
  「最終判定」段落、`irb130_pledge_gate.py`（新增，可重複執行）、
  `data/irb130_pledge_signal_panel.csv`（新增）。全程零新增FinMind
  額度消耗（複用既有`adjusted_price_series`快取+上一輪已回補的
  `irb130_pledge_combined.csv`），原地執行約2分鐘。

## #49 日內／隔夜報酬結構分解 Overnight vs Intraday Return Decomposition — FAIL（2026-09-07，第6關逐年一致性未過）

- **經濟機制**：第十一種機制分類（交易時段報酬結構分解，跟②timing/
  exposure overlay的差異是完全不依賴任何外部regime訊號，是每個交易日
  都相同的結構性時段切分）。假說主張台股TAIEX指數層級，報酬在「收盤到
  隔天開盤（overnight）」與「開盤到當天收盤（intraday）」兩段之間分布
  不對稱，對應美股文獻（Lou, Polk & Skouras 2019 JFE「A Tug of War」；
  AQR/Cliff Asness多次引用的S&P500隔夜/盤中報酬不對稱現象）。
- **第1關cheap gate（`overnight_intraday_decomposition_gate.py`）**：
  CHEAP_PASS——TAIEX(^TWII)逐日拆解overnight_ret=open_t/close_{t-1}-1、
  intraday_ret=close_t/open_t-1，用log報酬做exact可加性分解。
  overnight段TRAIN(<=2020-12-31,n=2694) mean=+0.0788%/日(p=0.0000)、
  log貢獻占比=+356.2%；VAL(2021~2024,n=969) mean=+0.0552%/日
  (p=0.0018)、log貢獻占比=+114.6%，兩期同號、皆顯著、皆遠偏離50%，
  跟美股文獻方向一致。intraday段VAL期不顯著(p=0.8954)未過，依判準
  只需其中一段通過即CHEAP_PASS，overnight段乾淨通過。見
  `TRIALS_LEDGER.md`#180。
- **第2關placebo（連續兩輪嘗試皆卡在方法論死胡同，非訊號被推翻）**：
  (a) 「隨機時刻切分」需要盤中分鐘/tick級價格路徑，三來源查證
  （yfinance分鐘K回溯不足、FinMind免費層無盤中1分K、TWSE官方
  `MI_5MINS`只有委託/成交統計無指數點位）皆確認TRAIN期(2015-2020)
  資料不可及，這個操作化方式直接判「資料不可及」死路。
  (b) 改用當天`high`/`low`當替代切分點做同形式telescoping分解對照，
  結果高/低切分數字比open切分更極端（TRAIN occ=+2274.0%/-2061.7%
  vs open的+356.2%），表面上通過同一套判準，但診斷出這是**選擇偏誤
  造成的數學必然性**（high/low依定義是當天極值，用極值當切分點必然
  產生偏態），不是任何經濟機制的證據，這個對照組本身選錯了、既不能
  證明open特殊也不能證明不特殊。見`TRIALS_LEDGER.md`#182。
- **第6關逐年一致性（本輪，改道跳過gate2直接測，因為只需要既有日線
  OHLC不需要建構任何placebo/null model）**：新增
  `overnight_intraday_gate6_consistency.py`，對gate1已CHEAP_PASS的
  overnight段逐年拆解，事前綁定門檻沿用`#29`/`#34`同一把尺（同號年數
  占比>=5/6=83.3%，TRAIN與VAL兩個窗口各自獨立要求通過）。
  **結果**：TRAIN（2010-2020共11年）11/11年同號=100.0%，一致性極高，
  通過。VAL（2021-2024共4年）僅3/4年同號=75.0%——**2022年overnight段
  轉負（年度複利-3.46%）**，未達83.3%門檻（N=4時等同要求4/4零容錯），
  未通過。見`TRIALS_LEDGER.md`#184。
- **判定**：**FAIL**——依「事前綁定通過標準，不事後移動門柱」鐵律，
  即使VAL僅4年、單一壞年（2022全球股市系統性下跌年）就跌破零容錯門檻
  屬於small-N artifact，仍不放寬標準通融放行；比照協定建議「gate6沒過
  就直接依快殺標準結案，不必再糾結gate2怎麼設計」，不再回頭補做gate2
  placebo設計，#49至此正式結案。
- **不泛化成**：「台股/TAIEX隔夜報酬異常不存在」——第1關cheap gate的
  統計顯著性與跟美股文獻一致的方向性不受本輪推翻，訊號存在性本身在
  TRAIN/VAL兩期皆有統計證據；死的是「任意4年VAL窗口都要逐年零容錯
  一致」這個具體嚴格判準。只測了TAIEX指數層級+open切分+這一組事前
  綁定的逐年一致性門檻，未測：個股層級橫斷面差異（例如外資持股比重
  高低分組是否有不同的隔夜/盤中結構）、0050層級（已完成的
  `adj_open`/`adj_high`/`adj_low`還原擴充工程留給未來用）、滾動多年
  平均代替嚴格逐年二元判準這種較寬鬆的一致性操作化、任何具體「只在
  隔夜持倉」portfolio構造的每日換手成本敏感度（本佇列已誠實揭露這點
  很可能是另一個獨立死因，但因gate6先死而未測到那一關）。
- **原始記錄**：`TRIALS_LEDGER.md`#180/#182/#184、`HYPOTHESIS_QUEUE.md`
  #49條目完整版本演進、`overnight_intraday_decomposition_gate.py`、
  `overnight_intraday_alt_cutpoint_placebo.py`、
  `overnight_intraday_gate6_consistency.py`（三支腳本皆新增，可重複
  執行）、`data/overnight_intraday_taiex_decomposed.csv`、
  `data/overnight_intraday_alt_cutpoint.csv`、
  `data/overnight_gate6_train_years.csv`、
  `data/overnight_gate6_val_years.csv`（皆新增）。全程零新增API呼叫
  （複用round180已快取的`^TWII`yfinance資料）。

## #51子事件1 融券強制回補 事件條件式短天期IC — FAIL（2026-09-07，第1關cheap gate未過，子事件1資料可行性/反推公式不受影響、`#51`整體未結案）

- **經濟機制**：round419-421已用2330/1808兩檔真實個股核對通過反推公式
  （`停止過戶日=CashExDividendTradingDate後第2交易日`、`強制回補視窗=
  [停止過戶日-6交易日,停止過戶日-3交易日]`）。本輪測的是這條公式支撐
  的具體經濟預測：視窗開始前既有的融券部位（`ShortSaleTodayBalance/
  ShortSaleLimit`）越大，強制回補視窗內的超額報酬應該越高（被迫買盤
  跟回補股數成正比）。
- **測試**：`forced_short_covering_gate1.py`，`factor_ic.py`同一個300檔
  樣本，現金股利除息事件1984筆，窗口+融券資料皆可用1707筆，Spearman
  IC+VAL期洗牌null N=200。
- **結果**：TRAIN IC=+0.0192(p=0.54)、**VAL IC=-0.0373(p=0.34)**，
  train/val正負號不一致，null percentile=19.0（門檻>=90.0），四個
  事前綁定判準全數未過。見`TRIALS_LEDGER.md`#186。
- **判定**：**FAIL（僅這個具體規格）**——「短天期融券部位大小線性
  預測強制回補視窗內超額報酬」這個假說沒有證據支持。
- **不影響**：子事件1的資料可行性/反推公式驗證（round419-421，用
  2330/1808真實個股核對通過）——那是「視窗算不算得出來」的PIT可得性
  問題，跟本輪「視窗內有沒有可觀測的異常報酬」是獨立的問題，公式本身
  未被推翻，未來若有#51其他子事件或不同規格仍可沿用。
- **誠實揭露限制**：82.2%事件的`short_ratio`為零（多數股票根本沒有
  顯著融券部位），樣本高度右偏，用連續比例做Spearman IC可能被大量
  零值稀釋掉訊號，只測了「連續比例大小」這一種規格，未測「有無融券
  部位」的二元對照這個可能更合適的規格變體——依研究紀律一輪一個
  有界工作單位，本輪誠實記負，是否值得追加二元規格留給下一輪判斷，
  不在本輪內自行加測。
- **原始記錄**：`TRIALS_LEDGER.md`#186、`HYPOTHESIS_QUEUE.md` #51條目、
  `forced_short_covering_gate1.py`（新增，可重複執行）。全程零新增
  付費/需登入API呼叫（52檔新抓皆為FinMind免費層正常呼叫）。

## #51子事件1 融券強制回補 二元規格對照 — FAIL（2026-09-07馬拉松第426輪，第1關cheap gate未過，與連續比例規格結論一致，子事件1至此兩種規格皆FAIL）

- **背景**：上面`#186`那筆FAIL誠實揭露82.2%事件`short_ratio`為零，
  懷疑連續比例規格可能被大量零值稀釋訊號，留待下一輪追加二元對照
  （有無融券部位）驗證。本輪就是那個待辦。
- **測試**：`forced_short_covering_gate1_binary.py`，沿用`#186`同一批
  1707筆事件（現金股利除息、300檔樣本、反推公式不變），改測
  `short_ratio>0`（有融券部位）vs`==0`（無部位）兩組VAL期mean_CAR差，
  事前綁定方向為正，null分布=組別標籤洗牌N=200次。
- **結果**：TRAIN diff=+0.00160、**VAL diff=-0.00174**，train/val正負號
  不一致，null percentile=37.5（門檻>=90.0）。四個事前綁定判準全數未過。
  見`TRIALS_LEDGER.md`#189。
- **判定**：**FAIL**，且與連續規格（`#186`）結論一致——排除「零值
  稀釋訊號」這個解讀，換成二元對照後結果仍是負向。子事件1（強制回補
  事件窗口）用融券部位（連續或二元表示法皆同）預測窗口內超額報酬，
  兩種合理規格都無法支持事前假說。反推公式本身仍有效（不受影響），
  只是「融券部位大小/有無 → 窗口內超額報酬」這個具體經濟預測沒有
  證據支持。
- **子事件1現況**：兩種規格皆FAIL，暫不再追加第三種規格（例如分層
  按產業或流動性），留給下一輪判斷是否正式結案子事件1、轉向子事件3
  （轉換公司債轉換價格重設，已由hypothesis_queue排程另行驗證資料
  可行）。
- **原始記錄**：`TRIALS_LEDGER.md`#189、`HYPOTHESIS_QUEUE.md` #51條目、
  `forced_short_covering_gate1_binary.py`（新增，可重複執行）。全程
  零新增API呼叫（全部命中`#186`已留下的本機快取）。

## #51子事件2 現金增資折價 事件條件式CAR — FAIL（2026-09-07，第1關cheap gate僅顯著性未過，接近但未過門檻，`#51`整體未結案）

- **經濟機制**：跟子事件1（強制回補，被迫買盤）方向相反的#51子案例——
  現金增資股東用比市價折價的認股價格拿到新股，折價幅度越大，代表這批
  股東潛在的「認股套利者賣壓」誘因越強，事前綁定除權交易日後20交易日
  CAR應該越負。折價幅度與除權日皆是公告日當下就公開已知的資訊，符合
  `#51`「強制交易者、日期事前已知」的核心主張。
- **測試**：`cash_increase_dilution_gate1.py`，全市場層級94檔曾發生
  現金增資的股票（非固定300檔抽樣，理由：全歷史僅約118筆事件，固定
  抽樣會砍到樣本不足），discount=(公告日前**原始未還原**收盤價-認股價)
  /公告日前原始收盤價，Spearman IC+VAL期200次洗牌permutation null
  （鏡射負向），事前綁定MIN_EVENTS_PER_PERIOD=15（低於子事件1的30，
  因事件密度本質不同，此門檻在跑之前就寫進腳本docstring，不是看到
  結果後才調整）。
- **結果**：TRAIN IC=-0.0383(p=0.7731,n=59)、VAL IC=-0.2289(p=0.1554,
  n=40)，同號（皆負，符合預測方向），null percentile=94.0（>=90.0
  門檻，過關），**唯獨VAL Spearman p=0.1554未達0.10顯著水準**，四項
  事前綁定判準中三項通過、一項未過。見`TRIALS_LEDGER.md`#187。
- **判定**：**FAIL（依事前綁定判準逐條檢查，不因「其他三項都過」就
  通融放行未過的那一項）**——依「事前綁定通過標準，不事後移動門柱」
  鐵律，p值判準沒有豁免空間。
- **誠實揭露**：這是本佇列少見「接近但未過」的FAIL案例（跟`#35` VRP
  的VAL p=0.0595同一種性質）——VAL期方向正確且null percentile通過，
  暗示訊號可能存在但**樣本量小（n=40）導致統計檢定力不足**，不是
  訊號被推翻。VAL四分位mean_CAR未呈現單調關係
  （q0=-0.0058/q1=+0.0463/q2=-0.0582/q3=+0.0202），跟連續IC的負向
  結果不完全吻合，暗示可能存在非線性或極端值影響，未進一步深挖。
- **bug修正過程記錄（誠實揭露，不是隱藏後才發現）**：初版腳本誤用
  `adjust.py::adjusted_price_series()`的還原股價計算discount，導致
  折價幅度出現不合理極端值（min=-3.49），因為還原股價會被距今之間
  所有後續公司行動的累積調整因子縮放，拿它跟`CashIncreaseSubscriptionpRrice`
  這種原始名目認股價比較是蘋果比橘子。已在本輪內發現並修正為改用
  `TaiwanStockPrice`原始收盤價計算discount（CAR計算仍用還原股價，
  這部分沒有問題），修正後折價幅度回到合理範圍（mean=0.2265，
  median=0.2329，符合台股現金增資實務上常見的2~3成折價）。上述FAIL
  判定是修正後的乾淨結果。
- **不泛化成**：「現金增資折價機制完全無效」——只測了「原始收盤價
  vs 認股價折價幅度」這一種discount定義+20交易日單一窗口長度+
  全市場稀有事件小樣本(n=99)，未測不同窗口長度、未測「新股實際掛牌
  可流通日」這個更貼近套利行為實際觸發時點的替代事件定義（本輪用
  除權交易日當t=0是簡化版本，新股通常要再等數週才能真正掛牌交易，
  真正的賣壓時點理論上更晚，這是本輪已知但未測試的局限）。
- **原始記錄**：`TRIALS_LEDGER.md`#187、`HYPOTHESIS_QUEUE.md` #51條目、
  `cash_increase_dilution_gate1.py`（新增，可重複執行）。全程零新增
  API呼叫（複用既有本機`TaiwanStockDividend`/`TaiwanStockPrice`快取，
  價格資料94檔全數命中快取）。

## #51子事件3：可轉換公司債轉換價格重設（Convertible Bond Conversion Price Reset）——2026-09-07結案：FAIL

- **假設**：`reset_magnitude=(old_price-new_price)/old_price`（僅向下重設）越大，`effective_date`後20交易日CAR應越負（潛在轉換套利賣壓）。
- **死因**：TRAIN IC=+0.0117(p=0.5978,n=2031)、VAL IC=+0.0430(p=0.1649,n=1047)，同號但方向與事前綁定的負相關預期相反；VAL洗牌控制組(N=200)null percentile=8.0遠低於90.0門檻且遠低於50。四項判準僅同號成立，其餘全數未過。
- **不泛化聲明**：不代表可轉債轉換價格重設機制完全無效——只測了單一固定20交易日窗口+effective_date當t0這個具體構造，僅取向下重設半邊（780筆向上重設未測）。
- **#51（強制交易者事件）三個子事件（強制回補/現金增資折價/可轉債轉換價重設）至此全數FAIL，#51正式結案**，移出排隊佇列。
- **原始記錄**：`TRIALS_LEDGER.md`#190、`HYPOTHESIS_QUEUE.md` #51條目(i)段落、`cb_conversion_price_reset_gate1.py`／`mops_cb_conversion_price_client.py`（新增，可重複執行）。回填30次MOPS查詢（2市場x15民國年），711檔股票，3078筆最終可用事件。


## #51-US（美股版）：S&P指數Addition事件公告日→生效日CAR搶跑漲幅——2026-09-09結案：FAIL

- **假設**：被動指數基金必須在生效日前追蹤買進新納入S&P成分股，公告日明顯早於生效日，事前綁定預期公告日→生效日CAR為正（搶跑買盤推升股價），文獻（Harris & Gurel 1986等index-effect）已大量研究但近二十年因套利搶跑明顯減弱甚至反轉。
- **事前排除Deletion**：只測Addition，Deletion事件常見成因是被收購/破產下市，會踩到`CLAUDE.md`「下市股資料取得不等於正確」的yfinance低覆蓋污染雷，事前決定排除、非事後挑選。
- **價格源修正**：本次改用`yf_price_client.fetch_yf_index()`（yfinance原生美股），不用`us_factors.us_price_series()`（FinMind `USStockPrice`）——後者違反`CLAUDE.md`2026-09-08「禁止用台灣資料商作為美股宇宙或價格的主來源」裁示。
- **死因**：390筆Addition事件中222筆可用。TRAIN（2012-2020,n=25）mean_CAR=+11.59%嚴格大於控制組（own_ticker_window/cross_ticker_window兩變體，各N=200）最大值5.36%，CHEAP_PASS，但樣本量僅25筆過小不足採信。VAL（2021-2024,n=197）mean_CAR=+1.56%，控制組百分位97.8已非常接近門檻，但未達「嚴格大於控制組最大值2.38%」的2026-09-07升級標準，判定FAIL。
- **不泛化聲明**：方向與index-effect文獻完全一致，是「近年套利搶跑減弱」已知風險下的誠實邊緣FAIL，不代表S&P指數效應在美股完全不存在，只是在嚴格控制組標準下、這個具體CAR窗口定義、這個樣本期間，不足以通過。
- **附帶發現**：查證確認`us_8k_pead_gate52.py`/`us_8k_item502_gate52.py`/`us_8k_item101_gate52.py`（#29/#30/#31）與`us_factor_ic_by_size.py`系列既有US軌試驗，價格源皆走FinMind `USStockPrice`，與2026-09-08裁示牴觸（這些試驗結案早於裁示發布）。是否需要用yfinance重跑覆核，留給後續驗證帽輪次或總司令判斷，本輪未擅自重工。
- **#51整體（台股三子事件＋美股Addition子測試）至此全數FAIL，正式結案**，移出排隊佇列；美股Deletion子測試因下市股價格污染雷未測，非跳關。
- **原始記錄**：`TRIALS_LEDGER.md`#222、`HYPOTHESIS_QUEUE.md` #51-US條目、`US_LEADS.md` #32、`sp500_addition_runup_gate51us.py`／`sp500_index_changes_client.py`／`backfill_sp500_index_changes.py`（新增，可重複執行）。


## 【家族層級】橫斷面離散度速度（台股）——2026-09-08 建立，**2026-09-08 正式結案**

> 2026-09-08 總司令裁示建立。這是**家族層級**條目，不是單一假設的死亡記錄；
> 個別假設的完整死因見各自條目與 `TRIALS_LEDGER.md`。

**家族定義**：把 Cybex 的「水位 → 速度」規律移植到台股——
取某個全市場橫斷面統計量的**水位百分位**，再取其**變化速度**，
用 `f(z)=1-z` 之類的映射轉成市場總曝險縮放。

**最終戰績：0 勝 5 敗（#56 撤案不計入勝負）——2026-09-08 家族正式結案**

| 假設 | 資料維度 | 死在哪一關 |
|---|---|---|
| **#26** 全市場融資餘額成長率 | 信用交易餘額 | cheap gate（`TRIALS_LEDGER.md`#97） |
| **#53** 全市場報酬離散度速度 | 個股報酬的截面標準差 | **第 2 關**隨機化時序控制組（#194）。第 1 關 sanity 三項皆 PASS |
| **#54** 成交值集中度速度 | 成交值的集中度 | **第 1 關** sanity（馬拉松第 430 輪 TW 軌） |
| **#55** 三大法人買賣超截面離散度速度 | 法人資金流（規模標準化後） | **第 1 關** sanity（hypothesis_queue排程，2026-09-08，#198） |
| **#57** 全市場當沖比重截面離散度速度 | 投機參與度（當沖比重） | **第 2 關**隨機化時序控制組（#201）。第 1 關 sanity 三項皆 PASS |

**結案結論：五個資料維度全數死亡，但明確不泛化為「橫斷面統計量這種構造
本身在台股無效」。**

已死的五個共同點不是「橫斷面統計量沒用」，而是**具體構造的問題更集中**：
`#53`與`#57`（本佇列唯二走到第2關的候選）死法完全相同——第1關sanity三項
皆PASS（訊號存在性成立），但`f(z)=1-z`這個固定線性映射的連續曝險 overlay，
在隨機化時序控制組（circular_shift/block_shuffle_5/block_shuffle_20）面前
贏不了。`#54`/`#55`則死在更早的sanity階段（方向與事前綁定相反）。**這是
一個比「資料維度沒訊號」更值得記住的教訓：percentile-based線性映射這個
timing overlay 建構手法本身，可能系統性地打不贏「保留曝險序列邊際分布、
只打散時序對齊」這種嚴格控制組**——因為隨機打亂後的曝險序列統計性質
（平均值/變異數）跟真實序列完全相同，訊號帶來的時序對齊優勢常小於抽樣
雜訊。未來若要重測這類 timing overlay，應優先考慮改變映射函數本身（例如
非線性S型映射、加入遲滯/緩衝帶避免高頻切換）或改用離散regime狀態機而非
連續縮放，而不是繼續換橫斷面統計量的資料來源。

**不構成「橫斷面統計量這種構造本身沒用」的證據**——這正是墓園寫入規則
第 3 條（不泛化成整類沒用）要防的錯誤：`#53`/`#57`的**訊號存在性**（第1關
sanity）從未被推翻，死的只是「線性映射連續曝險縮放」這個具體下游構造。

**統計陷阱提醒（結案時重申，不因結案而放棄）**：這五次失敗**不是五份
獨立證據**。本輪已實測部分相關係數：#55與#53相關係數corr_level=+0.463/
corr_vel=+0.134、#55與#54相關係數corr_level=+0.029/corr_vel=+0.148、#57
與#53/#54/#55相關係數|corr|全數<0.7（最高0.226），皆<0.7門檻確認四者互為
獨立截面統計量，但#26（融資餘額）未與其餘四者實測相關係數。依「同家族
因子只能算一個獨立發現」的同一個道理，即使確認獨立，**五次失敗仍應理解
為「同一個 timing overlay 構造手法在五種不同資料維度上都不夠強」**，而非
五個完全不相關的獨立否證，對「這類 overlay 手法整體」的推翻力道應該
比表面數字更弱。

## #53 全市場報酬離散度速度（Cross-Sectional Return Dispersion Velocity）——2026-09-08結案：FAIL（GATE_SEQUENCE第2關）

- **假設**：截面報酬離散度（`disp_t=std_i(r_{i,t})`）與其20日速度版（`vel_t`）異常偏高時降曝險，`exposure_t=clip(1-pctile_{t-1},0,1)`連續縮放，TAIEX標的。
- **死因**：GATE_SEQUENCE第2關隨機控制組（`control_group_standard.py::evaluate_vs_control()`，控制組3變體circular_shift/block_shuffle_5/block_shuffle_20各N=100）。level規格：TRAIN年化Sharpe+0.444未過控制組最大值+0.873、VAL+0.751未過+1.048。vel規格：TRAIN+0.356未過+0.913、VAL+0.801未過+1.349。四項判定全數未過（贏過平均/落在62~73百分位皆不算通過，2026-09-07標準升級——只有嚴格贏過控制組最大值或配對式20/20全勝才算過）。依快殺標準「已被控制組拆穿之偽影家族換皮」判FAIL，未進第3關。
- **不泛化聲明**：不代表「全市場截面報酬離散度這個資料維度完全沒有訊號」——第1關sanity（`TRIALS_LEDGER.md`#192）三項皆PASS（危機期間vel_pctile方向正確2/3、level_pctile條件式前瞻報酬方向正確），訊號存在性本身未被推翻。死的是`f(z)=1-z`這一個固定線性映射建構，本輪依#53共同規格「f事前固定不掃斜率」的約定未測試其他映射斜率或視窗長度，未來若重測應優先考慮更陡峭的映射（放大訊號在極端百分位時的曝險縮放幅度）或不同速度視窗長度。相位敏感度不適用（逐日連續曝險，非週期性重平衡）。
- **對#54/#55的參考意義（誠實記錄，非結論）**：本佇列「市場總開關假設軸」目前唯一走完第2關的候選以FAIL收場，說明「1-percentile線性映射+隨機化時序控制組」這套框架本身門檻不低，但#54（成交值集中度）/#55（法人流離散度）是不同的截面統計量與不同的資料來源，不因#53的結果預先判死，仍須各自獨立走完第2關。
- **原始記錄**：`TRIALS_LEDGER.md`#194、`HYPOTHESIS_QUEUE.md` #53條目、`cross_sectional_dispersion_gate53_control.py`（新增，可重複執行）。零新增API呼叫（複用#53第1關sanity既有快取與計算結果）。

## #54 成交值集中度速度（Turnover Concentration Velocity）——2026-09-08結案：FAIL（第1關sanity，馬拉松第430輪TW軌）

- **假設**：每日逐檔成交值占比的HHI（`conc_t=Σw_{i,t}²`，二階，金額流向而非價格變動）與其20日速度版異常偏升時降曝險（集中度急升＝參與面收窄＝廣度惡化）。
- **死因**：第1關sanity兩項獨立檢定皆與事前綁定方向相反，不是訊號太弱：(1) 已知危機窗口僅1/3通過（2018Q4/2020Q1的vel_pctile皆低於無條件基準，只有2022全年空頭通過，門檻>=2/3）；(2) tertile條件式前瞻20日TAIEX報酬，level與vel兩版皆是高集中度組的前瞻報酬**高於**低集中度組（事前綁定方向為高集中度應對應更低前瞻報酬）。依`MARATHON_PROTOCOL.md`1a節「沒過便宜關卡不調參數硬救，立刻FAIL換下一個」，本輪未進入GATE_SEQUENCE第2關隨機控制組即判FAIL，跟#53（sanity混合結果仍過關才進第2關被控制組拆穿）是不同的死法——#54是sanity階段方向直接反轉。
- **可能的經濟解釋（誠實記錄，非事後合理化）**：台股集中度上升可能伴隨的是**權值股領漲的多頭慣性延續**（例如台積電權重行情推升大盤同時拉高HHI），而非原假設「參與面收窄→risk-off」；機制方向與原假設相反，這是一個誠實的負結果，不代表HHI集中度這個統計量本身沒有其他用途（例如可能反過來是動能/慣性訊號的候選，但那是另一個假設，本輪不順勢展開，避免調參數硬救的變體）。
- **與#53關係（事前約定的相關係數檢查）**：level_pctile/vel_pctile與#53同版本相關係數分別為+0.0535/+0.0570，遠低於0.7合併門檻，**確認金額流向（#54）與價格變動（#53）是真正不同源的截面二階變數，計數上各自獨立**——即使兩者最終都FAIL，這條查證仍排除了「其實是同一個訊號測了兩次」的疑慮。
- **原始記錄**：`TRIALS_LEDGER.md`#195、`HYPOTHESIS_QUEUE.md` #54條目、`turnover_concentration_gate54.py`（新增，可重複執行）、`data/turnover_concentration_gate54.csv`（新增）。零新增API呼叫（複用#53已快取個股parquet與既有FMTQIK月檔）。

## #55 三大法人買賣超截面離散度速度（Institutional Flow Dispersion Velocity）——2026-09-08結案：FAIL（第1關sanity，hypothesis_queue排程）

- **假設**：每日逐檔三大法人合計淨買超金額除以當日成交值做規模標準化後（`f_{i,t}=total_net_{i,t}/money_{i,t}`），取截面標準差`flow_disp_t`與其20日速度版，異常偏升時降曝險（法人流離散度急升＝錢集中到少數股＝結構脆弱）。
- **死因**：第1關sanity三項中，sanity1（非退化性）與sanity2（危機窗口2/3命中）皆PASS，但**sanity3（tertile條件式前瞻20日TAIEX報酬方向）level_pctile與vel_pctile兩版皆與事前綁定方向相反**——低離散度tertile前瞻報酬（level+0.69%／vel+0.77%）反而低於高離散度tertile（level+0.74%／vel+0.96%），跟事前綁定「離散度升高→未來報酬應偏低」相反。依`MARATHON_PROTOCOL.md`1a節「沒過便宜關卡不調參數硬救」原則（跟#54同一把判死邏輯），未進GATE_SEQUENCE第2關隨機控制組即判**FAIL**。
- **與#53/#54相關係數（本輪一併查證，非佇列條目強制要求，屬`CLAUDE.md`通則自主延伸）**：corr_level(#55 vs #53)=+0.463、corr_vel=+0.134；corr_level(#55 vs #54)=+0.029、corr_vel=+0.148。皆<0.7門檻，**確認法人資金流離散度與報酬離散度／成交值集中度為三個彼此獨立的截面統計量**，非同一訊號換皮三次。
- **可能的經濟解釋（誠實記錄，非事後合理化）**：跟#54類似，台股法人買賣超集中到少數股可能伴隨的是**權值股/主流股的資金匯聚行情延續**，而非原假設「集中→結構脆弱→risk-off」；另外`#43`（三大法人買賣超**金額**集中度HHI/Top10）已測過方向相反的類似結論（2026-09-06結案FAIL，見上方#43條目），本次#55用的是**規模標準化後的截面標準差**（不同統計量），但兩者都指向同一個方向：法人資金集中在台股歷史樣本上系統性地不是risk-off訊號。
- **不泛化聲明**：不代表「三大法人資金流這個資料維度完全沒有訊號」——只測了`total_net/Trading_money`單一規模標準化口徑+20日速度窗口+4碼普通股子集，未測其他標準化分母（例如市值而非當日成交值）或窗口長度；`#30`個股融資使用率、`#36`個股融券使用率、`#43`買賣超集中度皆已獨立測過法人/信用資金相關訊號且各自死於不同關卡，法人/信用資金流這整條資料礦脈已被挖得相當深，未來若重測應優先考慮全新的標準化方式而非重複截面二階統計量的變體。
- **原始記錄**：`TRIALS_LEDGER.md`#198、`HYPOTHESIS_QUEUE.md` #55條目、`institutional_flow_dispersion_gate55.py`（新增，可重複執行）、`data/institutional_flow_dispersion_gate55.csv`（新增）。零新增API呼叫（複用既有T86快取（含前一輪回填的136個交易日）與#53/#54的money parquet快取）。

## #57 全市場當沖比重截面離散度速度（Day-Trading Ratio Dispersion Velocity）——2026-09-08結案：FAIL（GATE_SEQUENCE第2關）

- **假設**：逐檔當沖成交值（賣出當沖+資券互抵）占該股當日成交值比重，取截面標準差`dt_disp_t`與其20日速度版，異常偏升時降曝險（投機資金押注收窄至少數題材股＝過熱＝結構脆弱），`exposure_t=clip(1-pctile_{t-1},0,1)`連續縮放，TAIEX標的。
- **地基**：2,609個交易日逐檔當沖detail全數回填完成（100%，`backfill_day_trading_detail.py`，跨約15輪hypothesis_queue排程接續完成），第1關sanity三項皆PASS（`day_trading_ratio_dispersion_gate57.py`，馬拉松第441輪TW軌），與#53/#54/#55相關係數皆<0.7（最高0.226）確認非同家族、是獨立發現。
- **死因**：GATE_SEQUENCE第2關隨機控制組（`day_trading_ratio_dispersion_gate57_control.py`，完全比照`#53`同一套框架：控制組3變體circular_shift/block_shuffle_5/block_shuffle_20各N=100）。level規格：TRAIN年化Sharpe+0.9439未嚴格贏過控制組最大值+1.2340（percentile=99.0，但未達「嚴格贏過最大值」門檻）、VAL+0.5957未過+1.6160（percentile=44.3）。vel規格：TRAIN+0.6988未過+1.0901（percentile=83.7）、VAL+0.6314未過+1.5239（percentile=51.0）。四項判定全數未過（跟#53同一把尺：贏過平均/落在高百分位不算通過，只有嚴格贏過控制組最大值或配對式20/20全勝才算過）。依快殺標準「已被控制組拆穿之偽影家族換皮」判FAIL，未進第3關，死法跟#53完全相同。
- **不泛化聲明**：不代表「當沖比重截面離散度這個資料維度完全沒有訊號」——第1關sanity三項皆PASS（危機窗口2/3命中、tertile條件式前瞻報酬方向level/vel兩版皆正確），訊號存在性本身未被推翻。死的是`f(z)=1-z`這一個固定線性映射建構，跟#53同一個教訓：這個具體overlay構造本身的門檻，本佇列目前測過的四個不同資料維度（報酬離散度/成交值集中度/法人流離散度/當沖比重）**沒有一個能贏過隨機化時序控制組**。
- **家族結論**：**至此`#53～#57`「市場總開關假設軸」家族全數結案：0勝5敗**（#56撤案不計入勝負）。完整家族層級總結見上方「【家族層級】橫斷面離散度速度（台股）」條目，本輪已同步更新為正式結案狀態。
- **原始記錄**：`TRIALS_LEDGER.md`#201、`HYPOTHESIS_QUEUE.md` #57條目、`day_trading_ratio_dispersion_gate57.py`／`day_trading_ratio_dispersion_gate57_control.py`（新增，可重複執行）、`data/day_trading_ratio_dispersion_gate57.csv`／`data/day_trading_ratio_dispersion_gate57_control_results.csv`（新增）。零新增API呼叫（複用#57第1關sanity既有快取與計算結果）。

## Cybex.引擎：三個on-window執行時機改動套用於#53——2026-09-15結案：FAIL（GATE_SEQUENCE第2關，開發佇列自走輪）

- **假設**：#53「全市場報酬離散度速度」死於控制組，但死法可能是「翻轉太頻繁被雜訊主導」而非訊號構造本身無效；用進場延遲確認（entry_delay=3交易日）、出場延遲確認（exit_delay=3交易日）、總開關重新開啟冷卻期（reopen_cooldown=5交易日）三個執行時機機制降噪，測試是否能讓#53重新贏過控制組。三個參數皆為事前固定的保守小值，不掃描（`research/timing_overlay_engine.py::apply_confirmed_switch()`）。
- **死因**：GATE_SEQUENCE第2關隨機控制組（完全比照#53既有框架，控制組每次抽樣同步套用同一個延遲確認轉換）。level規格：TRAIN年化Sharpe+0.5580未過控制組最大值+1.5006（percentile=87.3）、VAL+0.7360未過+1.3997（percentile=57.3）。vel規格：TRAIN+0.3780未過+1.4185（percentile=60.0）、VAL+0.7220未過+1.6601（percentile=74.3）。四項判定全數未過。
- **結論（比#53本身更進一步的診斷）**：執行時機層面的降噪沒有改變結果，說明#53的失敗根因是`f(z)=1-z`percentile線性映射構造本身對雜訊敏感，不是「翻轉太頻繁」這個可以用延遲確認修補的執行層問題——這是兩個不同層次的缺陷，此結果排除了「換個執行方式就能救回#53」的可能性。
- **對Cybex.beta的參考意義**：`Cybex.beta`（score_longonly_v1擇時版本）若沿用同一套`f(z)=1-z`percentile映射構造做曝險縮放，會面臨同一個已證實的缺陷，應優先評估換一個對雜訊不敏感的映射方式。
- **原始記錄**：`TRIALS_LEDGER.md`#242、`HYPOTHESIS_QUEUE.md`「Cybex.引擎」條目、`research/timing_overlay_engine.py`（新增，含5項自測）、`research/cybex_engine_on53.py`（新增，可重複執行）、`research/data/cybex_engine_on53_results.csv`（新增）。零新增API呼叫（複用#53既有快取與計算結果）。

## #58 反向波動度加權投資組合建構（Inverse-Volatility-Weighted Portfolio Construction）——2026-09-08結案：FAIL（GATE_SEQUENCE第2關，馬拉松第443輪TW軌）

- **假設**：`w_{i,t}=(1/σ_{i,t})/Σ_j(1/σ_{j,t})`（`σ`為trailing 60日日報酬標準差），月頻（21交易日）再平衡，跟`#29`共用同一批159檔PIT宇宙（2015-2020）與同一個t0等權重buy-and-hold基準操作化。第1關sanity已PASS（三個期間波動度比值invvol/buyhold皆<1.0：TRAIN 0.7903/VAL 0.7175/FULL 0.7555，加權確實降低組合波動度，前提成立）。
- **控制組設計判斷（本輪自主判斷，非佇列預先指定）**：`#29`的bootstrap子集控制組（換一批股票測效果在不在）不適用於`#58`——`#58`要測的不是「有沒有波動度分散」而是「權重高低是不是真的對應個股波動度高低」，換股票測不出這個。本輪改設計專屬控制組：固定`REBAL_FREQ=21`/`VOL_WINDOW=60`，每次再平衡把算出的權重值集合原封不動、但**打散股票-權重對應**（保留邊際分布，只重排分配對象），2變體`per_rebal_permutation`（每次事件獨立重排，N=100）／`fixed_permutation`（全程固定一組重排，N=100），統計量取TRAIN/VAL年化Sharpe（invvol_ret本身，不扣buyhold，避免混入`#29`已測過的機械式再平衡效果）。
- **死因**：TRAIN期PASS（真實訊號年化Sharpe+1.1747嚴格贏過200次控制組抽樣最大值+1.0512），但**VAL期FAIL**（真實訊號+1.5163沒有贏過控制組最大值+1.5389，控制組百分位99.0，但2026-09-07標準升級後「贏過平均/落在高百分位」不算通過，只有嚴格贏過最大值或配對式20/20全勝才算）。GATE_SEQUENCE規則要求TRAIN+VAL皆PASS才算過關，VAL未過即整體FAIL。
- **不泛化聲明**：這是非常邊緣的FAIL（VAL百分位99.0，只差控制組最大值一點點），不代表反向波動度加權完全沒有風險調整後報酬的改善能力——sanity階段觀察到的invvol版本全期間total_return/sharpe/mdd皆優於buyhold版本方向正確，且TRAIN期已嚴格通過控制組檢定；死的是「這個具體實作（trailing 60日窗口/21日頻率/159檔樣本）在VAL期的邊際優勢小到跟隨機權重分配幾乎無法區分」，不是「風險平價這個經濟機制本身無效」。若未來有新的具體機制假說（例如不同的波動度估計窗口、或改用完整共變異數風險平價而非僅個股自身波動度），仍可視為獨立測試，不算換皮。
- **原始記錄**：`TRIALS_LEDGER.md`#202、`HYPOTHESIS_QUEUE.md` #58條目、`inverse_vol_weighted_portfolio_gate58.py`／`inverse_vol_weighted_portfolio_gate58_control.py`（新增，可重複執行）、`data/inverse_vol_weighted_portfolio_gate58_daily_returns.csv`／`data/inverse_vol_weighted_portfolio_gate58_control_results.csv`（新增）。零新增API呼叫（複用#29/#58已快取個股parquet）。

## #59 最小變異數投資組合建構（Minimum-Variance Portfolio Construction，共變異數矩陣版）——2026-09-08結案：FAIL（GATE_SEQUENCE第4關，hypothesis_queue排程接續）

- **假設**：Ledoit-Wolf收縮估計trailing 60日共變異數矩陣、全域最小變異數封閉解、負權重裁剪為0後正規化，月頻（21交易日）再平衡，跟`#29`/`#58`共用同一批159檔PIT宇宙。第1關sanity PASS（三期波動度比值皆<1.0且優於#58）、第2關隨機控制組TRAIN/VAL皆嚴格通過、第3關參數高原13/13網格點滿分——是本佇列③portfolio construction類走最深、前3關表現最乾淨的一次。
- **死因**：第4關成本/稅/滑價敏感度。TRAIN期在最寬鬆的1x成本情境下淨溢酬已轉負（buyhold+66.14% vs minvar淨+66.02%，淨溢酬-0.12%），2x/3x進一步惡化至-15.86%/-30.13%；VAL期1x/2x為正但3x轉負(-3.99%)。根因是換手率：每次拉回都要重新求解159x159共變異數矩陣得出全新目標權重，平均單次turnover=0.2107，約為`#29`固定拉回1/n版本(0.0332)的6.3倍。依GATE_SEQUENCE「TRAIN+VAL皆須PASS」同一把尺（比照#58判例），TRAIN未過即整體FAIL，未進第5關leave-one-out。
- **不泛化聲明**：不代表「共變異數結構帶來的分散化效益不存在」——GATE2/GATE3已證明毛報酬層面確實優於#58（個股波動度加權，忽略相關性），死的是「月頻+全域無槓桿長倉限制+封閉解直接求解」這個具體構造的換手率成本，換手成本吃光了毛報酬優勢。未來若重測應優先考慮：(a)拉長COV_WINDOW或再平衡頻率降低換手、(b)在最佳化目標函數加入turnover懲罰項、(c)加入權重變動上限約束，而非直接否定整個「最小變異數/風險平價」機制家族。
- **原始記錄**：`TRIALS_LEDGER.md`#212、`HYPOTHESIS_QUEUE.md` #59條目、`min_variance_portfolio_gate59.py`／`min_variance_portfolio_gate59_control.py`／`min_variance_portfolio_gate59_plateau.py`／`min_variance_portfolio_gate59_costs.py`（新增，可重複執行）、`data/min_variance_portfolio_gate59_costs_grid.csv`（新增）。零新增API呼叫（複用#29/#58已快取個股parquet）。

## #60 台指選擇權/期貨結算到期日機械性效應（Derivatives Settlement/Expiration Mechanical Effect）——2026-09-08結案：FAIL（GATE_SEQUENCE第1關，馬拉松第453輪TW軌）

- **假設**：TAIFEX台指期貨(TX)月合約每月第三個星期三（遇假日順延，本次用`continuous_contract.py`滾動偵測反推的300個真實歷史結算日，非自行套規則推算）前後，市場造市者/大型避險部位平倉或轉倉，產生機械性交易壓力，事前假設(a)結算日前有方向性壓力、(b)結算日後部位鬆綁出現反轉。事前綁定PRE_WINDOW=3、POST_WINDOW=1（範圍內最保守單點），TAIEX大盤層級事件研究（非個股橫斷面），控制組為count-matched隨機非結算日窗口的雙尾null分布。
- **死因**：第1關cheap gate兩個子測試皆FAIL。(a)結算前3日報酬：TRAIN mean=-0.0098%，VAL mean=+0.2684%，**train/val正負號不一致**，VAL |mean| vs 500次隨機窗口雙尾null percentile僅56.0（門檻90.0）。(b)結算當日報酬：TRAIN mean=+0.1825%顯著（p=0.0284）但VAL mean=+0.1117%不顯著（p=0.4953），雖同號但percentile僅47.6（門檻90.0），TRAIN期的顯著性沒有在VAL期重現，判斷為noise。180個可用事件（300個歷史結算日中120個落在TAIEX價格快取起始日2010-01-01之前不可用，屬預期內的資料涵蓋邊界非異常）。
- **不泛化聲明**：只測了PRE_WINDOW=3/POST_WINDOW=1這一組事前綁定的單點，依協定「不得看到FAIL後換N/M繼續測、避免變成事後選格子的多重比較」紀律，未掃描`HYPOTHESIS_QUEUE.md`#60條目原定的N/M網格即結案；不代表已窮盡所有窗口長度組合，但依既有紀律不應在同一組事前綁定之外另尋能過關的參數點。⑨大類（衍生性商品結算機械性效應）本次是本佇列第一次測試這個維度，唯一一條假設即FAIL，該大類至此0勝1敗結案。
- **原始記錄**：`TRIALS_LEDGER.md`#213/#214、`HYPOTHESIS_QUEUE.md` #60條目、`fut_settlement_date_probe60.py`（hypothesis_queue排程新增，資料可行性查證）、`fut_settlement_event_gate60.py`（本輪新增，可重複執行）、`data/fut_settlement_dates_derived_tx.csv`。零新增API呼叫（複用既有TAIEX/TaiwanFuturesDaily快取）。

## #52-US SEC EDGAR 8-K Item 2.02 事件反應速度（PEAD）—— 2026-09-08結案（小樣本先導）：FAIL（cheap gate，馬拉松第454輪US軌）

- **假設**：8-K Item 2.02（財報公布）對應Post-Earnings-Announcement Drift文獻
  （Bernard & Thomas 1989起，underreaction機制）——公告當日反應（r0）與其後
  一週漂移報酬（r_drift）應同號（continuation，事前綁定方向，非reversal）。
  round452已完成PIT/交易日對齊規則設計＋`get_8k_events()`地基程式碼，本輪
  （round454）依round452交辦，首次執行cheap gate（small pilot規模）。
- **測試**：`us_8k_pead_gate52.py`（新增，可重複執行），large tier N=25
  （seed 20260908_52），22/25檔可用（3檔無`us_price_series()`歷史），
  1004筆Item 2.02事件。控制組：同股票配對式重抽（排除真事件日±10交易日
  緩衝避免污染），2組隨機種子各100 draws，走`evaluate_vs_control()`新標準
  （嚴格贏控制組最大值或配對20/20全勝）。TRAIN/VAL依`validation.holdout`切分。
- **結果**：TRAIN（n=730）same-sign比例=0.5068 vs 控制組max=0.5484（百分位
  62.5，未過）；VAL（n=274）same-sign比例=0.5255 vs 控制組max=0.5686
  （百分位83.5，未過）。兩期方向一致（皆正），非train/val正負號矛盾，是
  量級不足——真實訊號比控制組雜訊高一些但沒有高到嚴格贏過控制組最高點。
- **判定**：**FAIL（僅N=25小樣本先導這一次執行）**——round452規格本身
  （PIT錨點、交易日對齊、r0/r_drift視窗定義）未被推翻，死的是「這組樣本
  規模下能不能偵測到訊號」這個具體結果。
- **誠實揭露限制**：(1) N=25屬小樣本，`CALIBRATION_PROBE.md`已證實類似
  規模的cheap gate對「文獻等級」弱訊號（|IC|≈0.03等級）檢定力只有四~五成，
  本次結果不排除同樣的檢定力不足問題，但依協定FAIL先誠實記錄，不在同一輪
  內片面放大樣本重跑（會變成看到FAIL才加碼的多重比較）。(2) `get_cik()`
  僅回傳ticker的**現況**映射，本輪抽樣意外發現一個具體例證：現況`XOM`
  對應的CIK`2115436`（title「ExxonMobil Holdings Corp」）非傳統認知的
  CIK 34088，可能是企業重組後的新法人實體，8-K歷史因而很短——這是
  `sec_edgar_client.py`docstring早已記載的「ticker多對一時序」風險首次
  在US軌實測中具體浮現（本輪樣本未抽中`XOM`，未影響本次結果，但未來擴大
  樣本時必須逐檔核對，不能只信任ticker字面匹配）。(3) 只測了Item 2.02
  單一item family，未測5.02/1.01等其他家族。
- **下一步（留給下一輪判斷）**：(a) 判定此小樣本結果是否足以結案
  #52-US整體，或 (b) 評估放大到full tier樣本重測（需先確認CIK歷史一致性
  查核方式），或 (c) 换測其他item family。三選項皆未替下一輪預先決定，
  依規則FAIL了先記錄換下一條，不在本輪內自行加測。
  **（後續：round456已依選項(c)測試Item 5.02，見下方新條目，同樣FAIL。）**
- **原始記錄**：`TRIALS_LEDGER.md`#215/#216、`HYPOTHESIS_QUEUE.md` #52-US
  條目、`us_8k_pead_gate52.py`（新增，可重複執行）。零新增付費/需登入API
  呼叫（純SEC EDGAR公開JSON端點）。

## #52-US SEC EDGAR 8-K Item 5.02 事件反應速度（管理層異動）—— 2026-09-08結案（小樣本先導）：FAIL（cheap gate，馬拉松第456輪US軌）

- **假設**：8-K Item 5.02（董監事/高階主管異動）屬非排程的意外揭露，文獻
  （如Fee & Hadlock 2004、Cziraki & Jenter 2020論forced turnover）指出這
  類揭露常伴隨市場尚未充分消化的負面資訊，可能產生比Item 2.02（排程性
  財報公布）更強的underreaction drift——與2.02不同經濟機制，非換皮測試。
  方向事前綁定為continuation（r0與r_drift同號）。
- **測試**：`us_8k_item502_gate52.py`（新增，可重複執行），復用
  `us_8k_pead_gate52.py`同一套PIT錨點/交易日對齊/控制緩衝機制（僅
  `process_ticker()`/`main()`加`item_code`參數，round454原版行為不變，
  已重跑round454原規格確認TRAIN 62.5/VAL 83.5數字一致，無回歸）。同一批
  22檔tickers（seed 20260908_52，複用round454已cached的
  `get_8k_events(full_history=True)`，**零新增API呼叫**，執行僅數秒）。
- **結果**：TRAIN（n=356）same-sign比例=0.5000（178/356）vs 控制組
  max=0.5856（百分位55.0，未過）；VAL（n=128）same-sign比例=0.4375
  （56/128）vs 控制組max=0.6068（百分位**8.0**，未過，且方向與
  continuation假說相反）。兩期皆遠低於門檻90.0，VAL期甚至反向。
- **判定**：**FAIL**——TRAIN幾乎等於隨機（0.5000），VAL不僅未過還反向，
  無一致方向性訊號，非train/val量級不足的邊緣case，是乾淨的無edge結果。
- **誠實揭露限制**：`items`欄位無法分辨異動動機（例行退休 vs 被迫離職），
  本規格未做語意過濾即全部納入，若真實機制只存在於被迫離職子集，混入
  例行退休會稀釋訊號使結果偏向null——這是本結果「無法排除」而非「已排除」
  的一個限制，程式docstring已預先揭露，不在本輪內另做語意過濾重測（避免
  看到FAIL後才加碼的多重比較）。
- **#52-US整體盤點**：至此測過Item 2.02（PEAD，round454，#215/#216）與
  Item 5.02（管理層異動，本輪，#217/#218）兩個item family，皆FAIL。
  round454選項(a)/(b)/(c)三選一已完整走過(c)，(b)（CIK歷史一致性查核＋
  full tier重測）因(c)已顯示同一批tickers在不同item family下皆呈現接近
  隨機或反向的結果，優先權下修；下一輪可判斷(a)結案整體#52-US（兩個
  family都FAIL，缺乏繼續深挖同一機制的證據），或視野擴大到1.01（重大
  協議）作第三個family再確認一次才下整體結論。
- **原始記錄**：`TRIALS_LEDGER.md`#217/#218、`HYPOTHESIS_QUEUE.md` #52-US
  條目、`us_8k_item502_gate52.py`（新增，可重複執行）。零新增API呼叫。

## #61 央行理監事會議決策事件（Central Bank Policy Decision Event）——2026-09-08結案：FAIL（GATE_SEQUENCE第1關，馬拉松第457輪TW軌）

- **假設**：央行理監事聯席會議決議公布日（每季一次，3/6/9/12月）是貨幣政策機關的離散主動決策，觸發源既非公司本身也非交易所規則，公布當下可能因政策意外（policy surprise）或不確定性消除產生機械性價格反應。子測試1（本輪測試）：決策公布日本身這一天大盤報酬是否顯著異於一般交易日，不分升息/降息/持平。事前綁定POST_WINDOW=1（前一交易日收盤→決策日收盤），TAIEX大盤層級事件研究，控制組為count-matched隨機非決策日交易日的雙尾null分布。事件資料來自`cbc_policy_decision_data.py`（`hypothesis_queue`排程人工核對官方頁面轉錄，非程式化API），fallback樣本僅涵蓋2018-2024（2015-2017三年官方會議日期經WebSearch索引、官方逐年頁面模式、Wayback Machine三個獨立管道查證皆窮盡失敗，判定目前免費合規手段下不可得）。
- **死因**：第1關cheap gate。TRAIN(2018-2020,12場)mean=-0.6541%(p=0.2128)、VAL(2021-2024,16場)mean=+0.5263%(p=0.0991)，**train/val正負號不一致**（TRAIN負VAL正）——即使VAL |mean| vs 500次隨機交易日null雙尾percentile=93.6單獨過90.0門檻，依同一把尺（`fut_settlement_event_gate60.py`#60判例）train/val方向不一致即整體FAIL。依`HYPOTHESIS_QUEUE.md` #61條目事前綁定「子測試1不過關，子測試2（決策方向分組）直接快殺不強行深挖」，未再測子測試2（該子測試樣本量本就極小，僅11筆2015-2024重貼現率變動事件，TRAIN 5筆/VAL 6筆）。
- **不泛化聲明**：只測了POST_WINDOW=1這一個事前綁定單點，且樣本fallback限於2018-2024（缺2015-2017三年12場會議），不代表已窮盡所有窗口長度或補齊完整樣本後結論不變；但依既有紀律不應在同一組事前綁定之外另尋能過關的參數點，也不應為了湊到更大樣本而放寬「三管道皆窮盡」的查證紀律去硬爬未授權來源。⑩央行政策決策事件大類本次是本佇列第一次測試這個維度，唯一一條假設即FAIL（含子測試1本身失敗、子測試2依規則快殺未測），該大類至此0勝1敗結案。跟`#60`（結算前3日報酬）同一種「train/val正負號不一致」失敗模式，是本佇列第二次出現這個具體失敗形態，可能暗示大盤層級單日事件反應本身在台股樣本規模下訊號噪音比偏低，非個股層級橫斷面排序那種訊號結構。
- **原始記錄**：`TRIALS_LEDGER.md`#219、`HYPOTHESIS_QUEUE.md` #61條目、`cbc_policy_decision_data.py`（`hypothesis_queue`排程新增，資料可行性查證，含三來源查證紀錄）、`cbc_decision_event_gate61.py`（本輪新增，可重複執行）。零新增API呼叫（複用既有TAIEX快取）。

## #52-US SEC EDGAR 8-K Item 1.01 事件反應速度（重大確定性協議）—— 2026-09-08結案（第三個item family，整體結案）：FAIL（cheap gate，馬拉松第458輪US軌）

- **假設**：8-K Item 1.01（新供應合約/信貸協議/授權夥伴關係/併購協議等）
  是非排程、傾向正面或中性的揭露，與2.02（排程性財報公布）、5.02（非排程
  負面傾向主管異動）皆不同象限——理論上是獨立的市場消化速度假說，非既有
  兩個family的換皮。方向事前綁定為continuation（r0與r_drift同號）。
- **測試**：`us_8k_item101_gate52.py`（新增，可重複執行），復用
  `us_8k_pead_gate52.py`同一套PIT錨點/交易日對齊/控制緩衝機制（僅
  `item_code`參數不同）。同一批22檔tickers（seed 20260908_52，複用
  round454已cached的`get_8k_events(full_history=True)`，**零新增API
  呼叫**，執行僅數秒）。
- **結果**：TRAIN（n=289）same-sign比例=0.4879（141/289）vs 控制組
  max=0.5747（seed_a）/0.5581（seed_b）（百分位36.0，未過）；VAL（n=61）
  same-sign比例=0.4754（29/61）vs 控制組max=0.6667/0.6792（百分位43.0，
  未過）。兩期訊號比例皆低於控制組平均（約0.497）。
- **判定**：**FAIL**——比Item 2.02（#215/#216，兩期皆正向但量級不足）跟
  Item 5.02（#217/#218，同號幾近隨機/反轉）都更明確地落在null區間，是
  三個item family裡最乾淨的無edge結果。
- **誠實揭露限制**：未依協議金額/對手方/交易類型做語意過濾，混入例行性
  小型協議（如常規信貸展期）可能稀釋訊號，屬「無法排除」而非「已排除」
  的限制，程式docstring已預先揭露，不在本輪內另做語意過濾重測（避免看到
  FAIL後才加碼的多重比較）。
- **#52-US整體結案**：至此測過Item 2.02（PEAD，round454，#215/#216）、
  Item 5.02（管理層異動，round456，#217/#218）、Item 1.01（重大協議，
  本輪，#220）三個item family，**全部FAIL**。三個family涵蓋排程性/
  非排程負面/非排程正中性三種不同性質的揭露，皆未通過同一套PIT/控制組
  機制的cheap gate，已足以支持「#52-US（SEC EDGAR 8-K事件反應速度）
  整體無edge」的結論，不再測第四個item family（`MARATHON_PROTOCOL.md`
  0a節「不得無限期繼續換皮測試」紀律）。已同步更新
  `data/signal_status.json`（0a節要求四條結構性優勢方向成績含FAIL全部
  對使用者公開）。
- **原始記錄**：`TRIALS_LEDGER.md`#220、`HYPOTHESIS_QUEUE.md` #52-US
  條目、`us_8k_item101_gate52.py`（新增，可重複執行）。零新增API呼叫。

## #52-TW MOPS 重大訊息事件反應速度 —— 2026-09-09結案（gate1 CHEAP_PASS + gate2 FAIL，整條假說結案）：FAIL（馬拉松第470輪US軌協助收成TW軌job）

- **假設**：MOPS重大訊息公告（併購/增減資/財務/人事/處分資產/停復牌/訴訟/
  法說會共8類）觸發的異常股價反應，是否可預測且可交易。拆成兩關：gate1測
  「有沒有異常反應」，gate2測「異常反應是否延續到可交易」（PEAD式方向性
  漂移檢定）。
- **gate1結果（`TRIALS_LEDGER.md`#221）**：8類中4類CHEAP_PASS（併購/增減資/
  財務/人事，`control_percentile`皆100.0，訊號嚴格大於全部400次控制組抽樣
  最大值），4類FAIL（停復牌/訴訟/法說會/處分資產，N=200正式量後現形，
  N=50小樣本曾虛胖PASS）。
- **gate2結果（`TRIALS_LEDGER.md`#223，正式N=200全量job
  `20260909-030107-0bce`）**：對gate1的4類PASS測「看到reaction_day+1初始
  反應方向(car0，帶正負號)後才進場，接下來H=5交易日是否有可預測的同向
  延續」，signal_stat=VAL期mean(sign(car0)*post_ret)，控制組2變體（
  `sign_shuffle`／`random_window`）各N=200，通過門檻=嚴格大於全部400次
  抽樣最大值（2026-09-07控制組標準升級）。**4類全數FAIL**：
  併購signal=0.0052<control_max=0.0112(percentile=94.5)、
  增減資signal=0.0000<control_max=0.0036(percentile=35.0)、
  財務signal=0.0020<control_max=0.0022(percentile=98.5)、
  人事signal=0.0018<control_max=0.0030(percentile=97.75)。與round467的
  N=25 smoke test方向完全一致，非小樣本雜訊。
- **判定**：**FAIL**——正式結論「異常反應存在但不可交易（已price-in、
  無延續）」。gate1扎實證明這4類公告確實觸發顯著大於隨機的異常反應幅度，
  但gate2證實反應後H=5交易日內沒有可預測的同向延續，賺不到這個訊號。
- **誠實揭露限制**：不泛化成「重大訊息公告完全無效」——只測了H=5單一
  窗口的方向性延續假設，未測其他horizon（H=1/3/10）或反轉假設
  （over-reaction後是否存在反轉，經濟理由與延續假設相反，屬另一條獨立
  假設，未來若重探此方向應優先測反轉，而非重測同一個延續假設換參數）。
- **#52整體盤點**：台股版（本條目）與美股版（`#52-US`，上方三個item
  family段落）皆FAIL，事件反應速度大類（0a節#52）兩市場合計0勝2敗結案。
  已同步更新`build_signal_status.py`的`DIRECTIONS`常數並重跑產生
  `data/signal_status.json`（0a節要求四條結構性優勢方向成績含FAIL全部
  對使用者公開）。
- **收成備註**：本輪的正式N=200 job由前一輪（第469輪TW軌）投遞，
  結果讀取與`TRIALS_LEDGER.md`#223登記由獨立自動化排程`hypothesis_queue`
  搶先完成（早於本輪馬拉松cycle）；本輪（第470輪，依輪替本應選US軌）
  發現`data/signal_status.json`與本檔案皆未實際同步更新（HYPOTHESIS_QUEUE.md
  文字紀錄聲稱「已寫入STRATEGY_GRAVEYARD.md新增段落」但檔案裡實際不存在，
  研判是`hypothesis_queue`排程預算用完中斷），故本輪補寫本段落與
  `data/signal_status.json`，非重跑試驗。
- **原始記錄**：`TRIALS_LEDGER.md`#221/#223、`HYPOTHESIS_QUEUE.md` #52
  條目(x)段落、`material_news_car_gate.py`／`material_news_car_gate2_
  continuation.py`（皆可重複執行）。零新增API呼叫。

## #62 鉅額逐筆交易（Block Trade）跟隨訊號（配對交易子集）—— 2026-09-09結案：FAIL（gate1，馬拉松第475輪TW軌）

- **假設**：`www.twse.com.tw/rwd/zh/block/BFIAUU`鉅額逐筆交易（門檻500交易單位
  或1,500萬元）只取「配對交易」型態（排除拍賣/標購兩種不同競價機制），以
  vwap相對當日收盤價偏離代理買賣方發起方（vwap<close視為sell-initiated），
  事前假設賣壓延續（第⑫類「知情大額交易跟隨/資訊不對稱」機制，round471三
  來源查證判可行，經濟文獻依據Kraus & Stoll 1972、Holthausen et al. 1987）。
  事前綁定：N=5/10/20交易日三個窗口各自獨立判定，signal=VAL期(2021-01-01~
  2024-12-31)mean(post_ret)，控制組matched_stock/unmatched_universe兩變體
  N=200（2026-09-07升級標準：訊號需嚴格大於全部400次抽樣最大值）。
- **死因**：第1關cheap gate。回補（`backfill_block_trade.py`背景job，
  round472~474持續推進，round475開工時已累積1600個交易日快取涵蓋VAL期至
  2021-02-17）追上後VAL期n_val=237（三個N值皆同）事件量已足夠判定。三個N
  值方向一致朝反方向（sell-initiated後市場調整報酬皆為正而非事前假設的
  負）：N5百分位0.8、N10百分位7.8、N20百分位0.8，皆遠低於嚴格大於控制組
  最大值的門檻，非邊緣case。
- **不泛化聲明**：只測了「配對交易」這一種競價機制、vwap<close這一種方向
  代理、N=5/10/20三個事前綁定窗口，不代表「拍賣」「標購」型態或其他方向
  代理（例如逐筆bid/ask比對）結論相同；但依既有紀律不應為了湊出能過關的
  結果而事後放寬篩選或另尋代理定義。**研判**：台股鉅額配對交易的「賣方」
  較可能是機構調節部位（ETF成分股權重調整、大股東質押後轉讓）而非資訊
  不對稱下的知情交易；亦可能反映一次性大量成交的流動性溢價（買方付溢價
  換取立即成交），隔日賣壓被市場快速消化甚至反彈。buy-initiated方向依
  事前綁定未判定（僅測sell方向）。第⑫類機制大類至此本佇列第一次測試，
  0勝1敗結案。
- **原始記錄**：`TRIALS_LEDGER.md`#224、`HYPOTHESIS_QUEUE.md` #62條目、
  `block_trade_gate62.py`／`twse_block_trade_client.py`／
  `backfill_block_trade.py`（皆可重複執行）。全程零新增FinMind/SEC EDGAR
  呼叫；`www.twse.com.tw`背景回補job本輪前累積約1600次請求（2秒/次節流，
  官方公開JSON端點）。

### f_lending_fee_spike（借券費率異常飆升作為知情放空訊號，股票/台股，2026-09-09結案）

- **哪一關死的**：成本/稅/滑價敏感度（GATE_SEQUENCE第4關）——第1關cheap gate
  （三N值percentile皆100.0）跟第2關參數高原（Z_THRESH∈{1.5,2.0,2.5,3.0}共
  12組全PASS）都乾淨通過，敗在扣除交易成本後訊號絕對報酬幅度不夠大。
- **具體數字**：`round_trip_cost_pct()`1x round-trip成本率0.685%。VAL期淨
  效益（避開損失-成本，正值代表划算）：N5於1x已轉負（−0.35%）；N10於1x已
  轉負（−0.04%）；N20於1x勉強為正（+0.21%）但2x轉負（−0.48%）、3x更負
  （−1.16%）。三個N值沒有一個能在2x成本下存活。
- **這個死法能不能泛化**：**不能**泛化成「借券市場定價這個機制家族無效」——
  統計顯著性本身乾淨（訊號嚴格大於全部400次控制組抽樣最大值），死因是
  「事前綁定的應用方式」（z-score急升事件觸發單次長倉降曝險/剔除持股，
  非實際放空）在此規格下絕對報酬幅度不足以覆蓋成本，不是方向錯或雜訊。
  若改用實際放空版本（省下借券成本外的下檔保護價值可能不同，但要另計
  借券費本身的成本）、或改用更大絕對報酬幅度的閾值/持有期組合，仍值得
  當獨立新試驗另開登記測試，不可直接沿用本次判FAIL的規格結論。
- **原始記錄**：`TRIALS_LEDGER.md`#225（gate1 CHEAP_PASS）/#226（gate2參數
  高原CHEAP_PASS）/#227（gate4成本敏感度FAIL）、`HYPOTHESIS_QUEUE.md` #63
  條目(m)段落、`lending_fee_gate63.py`／`lending_fee_gate63_param_plateau.py`／
  `lending_fee_gate63_costs.py`（皆可重複執行）。全程零新增FinMind/SEC EDGAR
  呼叫，全部走TWSE官方`www.twse.com.tw/rwd/zh/lending/t13sa710`端點。

**⚠️ 追加（2026-09-19，成本.二稽核重跑，總司令裁示【成本模型更正】）**：
原1x成本用`round_trip_cost_pct()`預設`commission_discount=1.0`(0.6850%)，
比總司令實際1.8折(0.4513%)更貴。同一套事件/信號改用1.8折重跑（可精確
重現，非隨機抽樣）：N5仍負(VAL-0.12%，舊-0.35%)；**N10由負轉正**
(VAL+0.20%，舊-0.04%，但TRAIN仍微負-0.05%，方向不一致判為雜訊)；
**N20維持正且TRAIN/VAL同向**(VAL+0.44%/TRAIN+0.32%，舊VAL+0.21%)。
三個N值在2x/3x下仍全數轉負——`CONSTITUTION.md`要求撐過2x/3x的margin-
of-safety慣例本次不重新定義，故N20在既有判準下**FAIL判定不變**，
但N20是本次稽核中除regime.候選2外最接近翻案的一格，[自行裁量]不擅自
重啟gate5，留待總司令裁示是否要用「寫實1x即足夠，不強制撐過2x/3x」
這個新判準單獨重審N20。詳見`TRIALS_LEDGER.md`#277。

**⚠️ 再追加（2026-09-19，總司令裁示【#63邊緣案例＋安全邊際倍數重新
錨定】，取代上一則追加的2x/3x判準，理由改寫）**：

總司令裁示：N20**維持FAIL**，但理由不是「規則如此（未過2x/3x）」，而是
「**今天剛好證明了我們對成本的估計會錯**（連錯兩次：先漏折數、再誇大
影響）。一個只在成本估計精確時才為正的策略，正是最脆弱的那一種」，加上
N=20樣本量本身極小。機械倍數2x/3x本身也被判定要廢除——1.8折下2x
(0.9026%)已經比「完全無折扣+滑價」(0.535~0.685%)還貴，3x(1.3540%)是
不存在的情境，安全邊際的用意是「防我們對成本估錯」不是「防一個不可能
發生的世界」。改用`validation.margin_of_safety`的三個錨定情境（基準
1.8折／保守無折扣／最壞無折扣+雙倍滑價，皆用`daytrade=False`與#63
實際交易型態一致），判準改為「必須在最壞情境下淨效益仍為正」。

**誠實揭露：裁示原文自己舉的範例數字內部不一致**——原文「保守情境：
無折扣+0.1%滑價=0.5350%」與「最壞情境：無折扣+0.2%滑價=0.6350%」
實際上是用**當沖稅率0.15%**算出來的（對照`daytrade=True`的t1窗口），
但「基準情境：1.8折+0.1%滑價=0.4513%」卻是用**一般交易稅率0.3%**算的
（對照`daytrade=False`的t5/t20窗口）——三個情境混用了兩種稅率假設。
#63本身是「賣掉剔除持股+換回大盤曝險」的一般交易，不是現股當沖，依裁示
原文自己的規則「三個情境的成本數字全部從breakeven_alpha_table.py取，
不得硬寫」，改用`daytrade=False`一致算出：基準0.4513%（與原文相同）／
保守0.6850%／最壞0.7850%（皆比原文範例更高，即更保守）。

**用內部一致的版本重跑（`TRIALS_LEDGER.md`#278，`lending_fee_gate63_
costs.py`已改為永久使用新三情境，不再是monkeypatch）**：N5三情境VAL/
TRAIN全負；N10基準情境TRAIN已轉負（VAL+0.20%/TRAIN−0.05%方向不一致）、
最壞情境雙期皆負；**N20基準情境VAL+0.44%/TRAIN+0.32%同向為正，但换算
到最壞情境後VAL+0.11%仍正、TRAIN轉為−0.02%（方向轉負）**——即使是
本次校正後、比裁示原文範例更嚴格的最壞情境，N20在TRAIN期依然撐不住。
這比原文預期的「同一組混稅率最壞情境下N20仍可能兩期皆正」更弱，
**恰好是總司令裁示理由的活生生範例**：N20的「像是正的」結果，換一種
（其實更嚴謹的）成本假設就消失了，證明它對成本假設本身的敏感度，
而不是訊號強度真的贏過成本。**FAIL判定維持，不重啟gate5**。

### f_lending_fee_spike v2（借券費率異常飆升·長持有期/較高閾值降曝險版，股票/台股，2026-09-19結案）

- **哪一關死的**：成本敏感度（gate4，六關系列第4關）——6格（Z∈{2,3,4}×N∈{40,60}）0通過；
  Z=4.0兩格連gate1（贏過全部400次控制組最大值）也沒過（percentile 99.0／99.75）。
- **流程對還是流程錯**：**流程對、這條假設在此規格下無足夠幅度**（不是流程錯）。事前綁定規格
  寫在`lending_fee_gate_v2_longhold.py`檔頭；跑數字前已誠實揭露看過gate63的Z/N舊數字。
- **具體數字**（事件冷卻期=N，VAL平均超額報酬；淨效益VAL 1x/2x/3x）：
  Z2.0_N40 −1.32%(t=−4.40)，+0.64/−0.05/−0.73%；Z3.0_N40 −1.38%，+0.70/+0.01/−0.67%；
  Z4.0_N40 −0.84%(gate1 FAIL)，+0.15/−0.53/−1.22%；Z2.0_N60 −1.17%，+0.48/−0.20/−0.89%；
  Z3.0_N60 −1.47%，+0.79/+0.10/−0.58%；Z4.0_N60 −1.25%(gate1 FAIL)，+0.56/−0.12/−0.81%。
  3x成本（2.055%）全部轉負，2x只有Z3.0兩格微正。
- **關鍵發現**：毛避開損失**沒有隨持有期線性增長**（N20 0.89%→N40約1.3%→N60約1.2~1.5%，
  飽和）；Z升高也不放大幅度。原條目建議的「拉長持有期/提高閾值放大幅度」兩條路都不成立，
  這個訊號的幅度天花板約1.5%，付不起2x~3x成本。
- **這個死法能不能泛化**：只結案「多頭剔除持股、單次round-trip、事件日進場」這個應用形式；
  **不泛化**成借券市場定價機制無效（統計顯著性在多數格乾淨成立）。放空版本仍受CLAUDE.md⑩
  硬規則擋住（借券成本/可借量未接入真實資料，數字不得採信）。**不再另開第三種持有期/閾值變體**。
- **原始記錄**：`TRIALS_LEDGER.md`#264~#269、`data/lending_fee_gate_v2_longhold_result.json`、
  `lending_fee_gate_v2_longhold.py`。全程零新增外部API呼叫。

**⚠️ 追加（2026-09-19，總司令裁示【#63邊緣案例＋安全邊際倍數重新錨定】二，
安全邊際重新錨定後6格全部重跑）**：原判定用的「1x」其實是無折扣0.685%
（跟#63同一種污染），且2x/3x機械倍數本身已廢除（見`CLAUDE.md`/
`CONSTITUTION.md`與`validation/margin_of_safety.py`）。改用三個錨定情境
（基準1.8折0.4513%／保守無折扣0.6850%／最壞無折扣+雙倍滑價0.7850%）、
判準改為「VAL最壞情境淨效益>0 且 TRAIN基準情境淨效益>0」，6格全部重跑
（`lending_fee_gate_v2_longhold.py`已永久改用新判準，`TRIALS_LEDGER.md`
#279）：

  Z2.0_N40最壞情境VAL+0.537%(TRAIN基準+0.008%)→**PASS**；Z3.0_N40最壞
  VAL+0.596%(TRAIN基準+0.011%)→**PASS**；Z4.0_N40 gate1仍FAIL
  (percentile99.0)→FAIL；Z2.0_N60最壞VAL+0.384%(TRAIN基準+0.014%)→
  **PASS**；Z3.0_N60最壞VAL+0.685%(TRAIN基準+0.016%)→**PASS**；
  Z4.0_N60 gate1仍FAIL(percentile99.75)→FAIL。

**總結：4/6格通過（舊機械3x規則下是0/6），兩個主格(Z2.0,N40)與
(Z2.0,N60)皆PASS**，但依家族事前綁定規則「至少5格通過」，4/6仍未達標，
**維持「不晉級深挖」的結案判定**——[自行裁量]不擅自放寬「至少5格」的
門檻去湊過關，也不擅自另開新格點（如Z=3.5）去湊到第5格，那正是本次
裁示要求根治的「調整規則去救候選」同一種病。**誠實記錄**：這比舊判定
實質上更接近通過，唯二未過的Z4.0兩格敗在gate1（控制組百分位，跟成本
模型完全無關的統計顯著性關卡），不是敗在成本，家族結案的原因已經從
「成本吃不消」轉變為「兩個高Z鄰近格的統計顯著性不夠」。是否值得就
這兩個邊緣格另開複驗（例如更長樣本期），留待總司令裁示。

### fut_basis_regime_gate64（台指期貨基差regime預測TAIEX現貨報酬，期貨，2026-09-09第484輪FAIL）

- **哪一關死的**：第1關cheap gate（新版`control_group_standard.py`標準，
  2026-09-07升級後）——依舊版90百分位門檻本會被誤判CHEAP_PASS，新標準下
  誠實判FAIL。
- **具體數字**：訊號`=sign(basis_pct-60日trailing均值)`逐日換倉，目標=TAIEX
  現貨次日報酬，全歷史(2000-2024,n=6125)real_terminal_equity=4.1425
  （+314.3%累積）。控制組`full_shuffle`（完全打散順序）與`block_shuffle_20d`
  （20日區塊打散）各N=200，合併400次抽樣percentile=97.0（贏過平均/中位數），
  但**未過新標準的「嚴格贏過最大值」門檻**——`block_shuffle_20d`變體最大值
  12.2143明顯高於真實訊號的4.1425。
- **這個死法能不能泛化**：**不能**泛化成「basis對TAIEX現貨完全沒有預測力」
  ——只代表本次事前綁定的具體規格（WINDOW=60/direct sign/逐日單日換倉）
  在新的嚴格控制組標準下不夠格；跟同一個basis資料源但預測期貨自身報酬的
  `fut_basis_carry`(#35→#37 FAIL)/`fut_basis_change_momentum_5d`(#36 FAIL)/
  `fut_basis_mean_reversion_60d`(#38/#43 EXPERIMENTAL)是不同的預測目標，
  不是同一機制換皮。這也是控制組標準升級後第一個「舊標準會誤判過關、新
  標準誠實判死」的具體實例，印證了升級的必要性。
- **原始記錄**：`TRIALS_LEDGER.md`#228、`HYPOTHESIS_QUEUE.md` #64條目、
  `fut_basis_regime_gate64.py`（可重複執行）、
  `data/fut_basis_regime_gate64_result.json`。全程零新增API呼叫，複用
  `fut_basis_series.py`既有快取。

### f_leader_follower_lag（產業龍頭股跨期領先-落後動能，股票/台股，2026-09-09
hypothesis_queue排程接續FAIL）

- **哪一關死的**：第1關cheap IC gate——train/val同號（皆為正，符合事前綁定
  方向）但兩處都沒過：VAL期IC絕對值遠小於事前訂的0.02門檻，且贏過洗牌
  null分布的百分位87.5未達90.0Bonferroni門檻。
- **具體數字**：`factor_ic_leader_follower_lag.py`，300檔樣本、18+產業分組
  （median每快照14組、每組中位數7名成員）、龍頭trailing 20日均成交金額
  最大者、龍頭t期5日報酬廣播給族群成員、預測族群成員t+1期5日報酬。
  TRAIN mean_ic=+0.0072/IR=+0.065(n=288日)、VAL mean_ic=+0.0094/IR=+0.091/
  hit_rate=0.51(n=193日)、null_percentile=87.5(需>=90.0)、same_sign=True。
- **這個死法能不能泛化**：不能泛化成「同產業龍頭-族群資訊擴散延遲這個
  經濟機制在台股完全不存在」——只測了「成交金額最大」當關注度代理、
  trailing 5日/次5日這組固定lag窗口、300檔樣本內分組（非全市場真龍頭）。
  同號但強度貼近雜訊（IC僅+0.007~+0.009量級，比本佇列多數已過cheap gate
  的因子小一個數量級以上），比較貼近Hou(2007)原文機制在台股（散戶占比
  更高、但樣本內龍頭認定較粗糙）下訊號真的很弱，而非方向判斷錯誤。若
  未來重測，應優先改善龍頭認定精確度（例如換全市場成交金額排名而非樣本
  內排名）或改用分析師覆蓋度更直接的代理，而非直接放棄整個機制類別。
- **原始記錄**：`TRIALS_LEDGER.md`#229、`HYPOTHESIS_QUEUE.md` #65條目、
  `factor_ic_leader_follower_lag.py`（可重複執行，零新增API呼叫，完全
  複用`factor_ic.py::load_sample_with_factors()`既有快取）。

### us_tax_loss_selling_gate66（美股年末稅損收割賣壓／一月效應，股票/美股，
2026-09-09 hypothesis_queue排程接續FAIL）

- **哪一關死的**：第1關cheap gate——事前綁定「12月賣壓期＋次年1月反轉期，
  TRAIN/VAL各自需過洗牌null百分位>=90.0且方向一致」共4項判準，僅1/4項
  過關，判FAIL。
- **具體數字**：`us_tax_loss_selling_gate66.py`，199/200檔clean universe
  可用、總事件數3371（TRAIN年份1990~2020/2802筆、VAL年份2021~2023/
  569筆）。排序變數改用YTD(1~10月)報酬（避免12月報酬同時當排序與測試
  窗口造成套套邏輯，此澄清在跑數字前已寫進腳本docstring）。
  (a) 12月賣壓期：TRAIN percentile=40.6（方向對但未過門檻）、
  **VAL percentile=10.2（方向相反，losers組12月反而贏對照組+0.32%）**；
  (b) 次年1月反轉期：TRAIN percentile=100.0 CHEAP_PASS、
  VAL percentile=87.4（方向對但些微未過90.0門檻）。
- **這個死法能不能泛化**：不能泛化成「一月效應／稅損收割假說完全不存在」
  ——反轉窗口（次年1月）訊號方向兩期一致且TRAIN顯著，死的主要是「12月
  賣壓」這一半機制在近百年美股樣本上未能證實，尤其VAL期方向相反。文獻
  本就記載現代市場（尤其2000年後）效應已明顯減弱，此結果與先驗預期
  方向一致（見經濟機制段落）。未測小型股子樣本分組（文獻記載效應集中
  在小型股，若未來重測應優先做這個deep_dive，本輪因第1關已判FAIL、
  不符合「第1關過關才做deep_dive」的協定順序，故未執行）。**沿用既有
  存活者偏誤但書**：yfinance對已下市股0%覆蓋，本假設選「今年跌最多」
  的股票正是最可能下市/除牌的族群，若真正的年度最大輸家已下市而從
  宇宙/價格源消失，會系統性低估losers組真實跌幅與後續效應強度。
- **原始記錄**：`TRIALS_LEDGER.md`#230、`HYPOTHESIS_QUEUE.md` #66條目、
  `us_tax_loss_selling_gate66.py`（可重複執行，零新增API呼叫，複用
  `us_universe_pit.py`survivorship-free宇宙與既有美股價格快取）。


### odd_lot_imbalance_portfolio_v1_gate67（盤中零股交易比重Odd-Lot Imbalance
portfolio層構造，股票/台股，2026-09-10 hypothesis_queue排程接續FAIL）

- **哪一關死的**：GATE_SEQUENCE第2關隨機控制組（N=100，TRAIN+VAL皆完整
  跑完100 draws，非稀疏抽樣）。
- **具體數字**：`odd_lot_imbalance_portfolio_v1.py`，因子IC為負改升冪排序，
  月頻挑委託簿失衡度最低TOP20做多，TRAIN=[2020-10-26,2022-12-31]/
  VAL=(2023-01-01,2024-12-31]（VAL_END物理邊界未變動，僅內部切分起點依
  TWTC7U資料自2020-10-26才可得這個限制調整）。
  TRAIN：真實報酬+4.93%（MDD-13.23%）vs 買進持有+9.52%，隨機控制組
  percentile=**33.0**（門檻90.0），alpha年化+0.71%不顯著p=0.898、
  beta=+0.351；
  VAL：真實報酬+10.80%（MDD-7.88%）vs 買進持有+61.94%，隨機控制組
  percentile=**13.0**（門檻90.0），alpha年化-2.31%不顯著p=0.605、
  beta=+0.300。
  兩期percentile皆遠低於90.0門檻且低於50，兩期alpha皆不顯著、beta皆為
  正曝險，屬決定性未過而非邊緣未過。
- **這個死法能不能泛化**：不能泛化成「零股委託簿失衡度這個訊號完全
  無效」——第1關cheap gate的時序相關性（`TRIALS_LEDGER.md`#231）依然
  CHEAP_PASS，方向（失衡度高預測後續報酬下修）未被推翻，死的是「升冪
  排序、月頻、純多方向、TOP20固定持股數」這個具體portfolio構造。
  第1關cheap gate當時已附「邊緣過關」但書（train僅3個快照、val
  percentile=90.7距門檻僅0.7個百分點、val_mean_ic=0.0249僅微幅高於0.02
  下限），本次第2關決定性未過呼應了那個但書的疑慮——**訊號強度不等於
  構造穩健性**是這次最值得記住的教訓，跟#34銅金比案例（第1關訊號很強
  但第5關leave-one-out死於單一年份貢獻）是同一類警示的不同版本。若
  未來重測，應優先評估是否有結構性理由改善事件密度（例如放寬持有天數
  或改用連續曝險力道而非二元TOP20切換），而非直接放棄整個機制類別；
  但鑑於資料源本身2020-10-26才存在（TRAIN窗口僅約2年、VAL僅2年），
  樣本量天生受限這個限制無法用工程手段解決。
- **原始記錄**：`TRIALS_LEDGER.md`#231（gate1 CHEAP_PASS）、
  `TRIALS_LEDGER.md`#232（gate2 FAIL，本則）、`HYPOTHESIS_QUEUE.md`
  #67條目、`odd_lot_imbalance_portfolio_v1.py`（可重複執行，checkpoint
  機制完整保留TRAIN 100/100+VAL 100/100兩期隨機控制組全部draws，
  零新增外部API呼叫，複用既有零股逐日快取）。

## #68 券資比（Short-to-Margin Ratio）—— 2026-09-10結案：FAIL（第1關cheap IC gate，馬拉松第510輪，hypothesis_queue軌）

- **假設**：`TaiwanStockMarginPurchaseShortSale`的ShortSaleTodayBalance/
  MarginPurchaseTodayBalance（融券今日餘額/融資今日餘額），捕捉同一檔股票
  放空籌碼相對做多槓桿籌碼的比值（多空分歧程度／軋空風險）。跟已FAIL的
  #30（個股融資使用率，水位）、#36（個股融券使用率，水位）不同維度——這是
  比值關係，屬第六類「資金結構失衡驅動」。事前綁定方向為正：券資比越高，
  代表放空籌碼相對做多槓桿籌碼越多，若股價開始上漲，看空者被迫回補（軋空）
  會放大且延續漲勢，預期未來報酬越好，因子值保留原始比例不取負號。
- **死因**：第1關cheap IC gate。300檔樣本（248/300可用），standalone
  bonferroni_n=1。train mean_ic=-0.0056（n=74期）、val mean_ic=-0.0548
  （n=47期，hit_rate=0.64），null percentile=100.0（門檻90.0），train/val
  同號，`evaluate_factor()`機械判準PASSES=True——**但train/val的IC皆為負，
  與事前綁定的正向假設方向相反**，依腳本docstring事前寫明的規則（同號但
  方向為負，即視為方向假設證偽，不因符合「同號」判準就宣稱通過）override
  為FAIL，不採信機械判準。
- **不泛化聲明**：只否證「原始比例、正向」這個具體構造；反向使用（券資比
  越高預期報酬越差，例如解讀為做多籌碼相對稀缺、軋空風險已被市場定價、
  後續反而回落）或其他變換（例如取對數、與歷史分位比較）未經測試，非本輪
  判定範圍。
- **原始記錄**：`TRIALS_LEDGER.md`#233、`HYPOTHESIS_QUEUE.md` #68條目、
  `factors.py::_short_margin_ratio()`／`factor_ic_short_margin_ratio.py`
  （皆可重複執行）。零新增API呼叫（複用既有300檔快取+既有融資融券資料）。


## 外部一改.3 名家趨勢跟隨機制（台指期，2026-09-10 第1關 cheap gate 全部 FAIL）

- **死因分類**：流程對，這五條假設在台指期上沒有可證實的 edge（不是流程錯）。
- **機制與結果**（TX 日盤連續合約 2000-2024，6,184 個可用日，未計成本；
  控制組 full_shuffle／block_shuffle_20d 各 N=200，門檻＝合併最大值）：
  - 海龜 System 1（20/10、2N 停損、0.5N 加碼上限 4 單位、1% 風險反比部位）
    終值 1.4494、Sharpe 0.179、MDD −36.8%、百分位 57.5 → FAIL（`TRIALS_LEDGER.md`#234）
  - Donchian 完整版（55/20，其餘同上）終值 1.6232、Sharpe 0.215、MDD −28.7%、
    百分位 54.0 → FAIL（#235）
  - Keltner 通道突破（EMA20±2×ATR10，穿回中線出場）終值 2.1929、Sharpe 0.266、
    MDD −49.2%、百分位 78.8 → FAIL（#236）
  - 波動度突破（收盤突破前收 ±0.5×ATR20）終值 0.1675（**25 年累積 −83.3%**）、
    Sharpe −0.203、MDD −86.5%、百分位 7.0 → FAIL（#237），**這條是乾淨的無效**
  - CTA 多時間框架（20/60/120 動量平均 × 15% 年化波動度目標）終值 2.7023、
    Sharpe 0.405、MDD −25.8%、百分位 73.0 → FAIL（#238）
- **不泛化成什麼**：不等於「趨勢跟隨在台指期無效」。這裡測的是**原文獻規則的單一
  參數點、單一標的、日 K 粒度、不計成本的第 1 關**。原始海龜是多商品組合分散＋
  盤中觸價執行的系統，把它壓成單一商品、日收盤決策之後，最重要的兩個組成
  （跨商品分散、盤中停損）都不在了。要推翻「趨勢跟隨」這個大類，需要的是
  多商品版本的測試，不是這一輪的結果。
- **同家族提醒**：四條趨勢突破機制彼此 r=+0.64～+0.84、且與既有
  `hyp_trend_multi_tf`／`hyp_donchian_breakout` r≈+0.70～+0.75，
  **獨立發現數是 2 不是 5**（另一個是與所有機制 r≤0.234 的波動度突破）。
- **原始記錄**：`TRIALS_LEDGER.md`#234～#238、`FUT_LEADS.md` 2026-09-10 段落、
  `fut_classic_trend_gate_ext13.py`／`data/fut_classic_trend_gate_ext13_result.json`
  （皆可重複執行）。零新增 API 呼叫。

### option_oi_pcr_gate69（台指選擇權買賣權比未平倉量口徑Open Interest PCR
逆向情緒訊號，股票/台指衍生品，2026-09-10 hypothesis_queue排程接續FAIL）

- **哪一關死的**：GATE_SEQUENCE第1關cheap gate（未進第2關以後）。
- **具體數字**：`option_oi_pcr_gate.py`，FinMind`TaiwanOptionDaily`(TXO)
  既有快取，`trading_session`==`position`（日盤）未平倉量Put/Call比率
  predict次一交易日台股報酬。TRAIN(<=2020-12-31) n=1467，Pearson
  r=+0.0508（p=0.0519）、null percentile=93.6；VAL(2020-12-31~2024-12-31)
  n=970，Pearson r=+0.0395（p=0.2188）、null percentile=**79.0**（門檻
  90.0）。四項判準：幅度非零✓、train/val同號✓、事前綁定方向為正兩期皆
  正✓，但VAL贏過洗牌null未過（79.0<90.0）——第4項未過即判FAIL。
- **這個死法能不能泛化**：不能泛化成「Put/Call比訊號完全無效」——TRAIN
  期本身percentile=93.6接近門檻、p=0.0519邊緣顯著，只是VAL期訊號明顯
  減弱，屬「訓練期邊緣訊號、驗證期未能穩定重現」，符合#69事前寫明的
  先驗風險（現代機構化市場的簡單逆向訊號可能已被套利抹平）。與已FAIL的
  `#31`（`option_pcr_gate.py`，成交量口徑，同樣FAIL但死於第2關以後具體
  overlay構造）為同源資料但不同聚合口徑（未平倉量=存量，成交量=流量），
  經濟意涵不同，本輪未計算兩者相關係數（#31已移出佇列非現役候選，同
  家族查核非必要）。
- **原始記錄**：`TRIALS_LEDGER.md`#239、`HYPOTHESIS_QUEUE.md` #69條目、
  `option_oi_pcr_gate.py`（可重複執行，零新增API呼叫，全用`#31`留下的
  既有parquet快取）。

## #70 選擇權波動度偏斜（Volatility Skew）— FAIL（2026-09-10）

**假設**：put_iv-call_iv（OTM put減OTM call隱含波動度）與後續台股N=5/N=20
交易日報酬呈負向IC（skew越陡代表下檔避險需求越濃，後續報酬越差，比照
Xing et al. 2010原文獻方向）。

**死因**：TRAIN/VAL正負號相反，且TRAIN期方向與事前綁定完全相反並高度
顯著（N=5 TRAIN r=+0.1914 p=0.0000 percentile=100.0；N=20 TRAIN r=+0.3425
p=0.0000 percentile=100.0），VAL期方向雖轉負（N=5 r=-0.0458 percentile=
83.6未過門檻；N=20 r=-0.1823 percentile=100.0），但依「不給方向彈性」
鐵律，train/val不同號即直接判FAIL，不因VAL單期好看而放行。

**不泛化聲明**：不泛化成「選擇權市場資訊對台股完全無效」——本佇列同源
TXO選擇權訊號中`#31`（成交量PCR）曾CHEAP_PASS，`#35`（VRP）、`#69`
（未平倉量PCR）FAIL但未出現方向反轉，`#70`是唯一出現train/val系統性
方向反轉的，死的是「put_iv−call_iv水位＋固定5%名目OTM距離」這個具體
構造，未測其他OTM距離口徑或25-delta動態篩選。

**詳細數字**：見`TRIALS_LEDGER.md`#241、`HYPOTHESIS_QUEUE.md` #70條目。

### TAIEX 200MA趨勢濾網 regime overlay（#10協定第一個訊號，binary曝險
1.00/0.50，2026-09-15 FAIL）

- **哪一關死的**：`REGIME_OVERLAY_PROTOCOL.md`鎖定門檻第1條（MDD縮小
  ≥35%）——扣除切換成本後未過。不是危機視窗關卡死的（4個TRAIN可測
  視窗全部改善），是成本敏感度直接判死。
- **具體數字**：TRAIN期(2010-01-04~2020-12-31,n=2710天)基底(TAIEX買進
  持有)MDD=-28.72%；overlay毛(未扣成本)MDD=-20.46%（縮小28.8%，看起來
  接近門檻），但套用`validation/costs.py`全額切換成本後淨MDD=-28.22%
  （只縮小1.8%，門檻≥35% FAIL）。年化切換8.4次、年化成本≈2.888%，
  幾乎吃掉基底CAGR（6.10%）本身。控制組(d)參數高原25格（MA窗口
  140/170/200/230/260 × 空頭曝險0.35/0.425/0.5/0.575/0.65）**0/25**
  達到35%門檻，排除單點運氣。控制組(b)訊號延遲1週後MDD反而惡化為
  -37.84%（比基底更差），方向翻轉，不排除殘留的少量保護本身帶有前視/
  擬合成分。控制組(a)隨機開關排列法(n=300)百分位=100（>90門檻通過），
  但這只證明「照趨勢訊號切換比同頻率隨機切換好」，不能救回已經沒通過
  的成本門檻。
- **這個死法能不能泛化**：**不能**泛化成「regime擇時整個方向沒用」——
  死的是這個具體構造：①binary(二元)曝險切換，而不是連續縮放（`CLAUDE.md`
  已明講binary版本更容易讓少數進出場事件的雜訊偽裝成乾淨績效，這裡的
  控制組(b)翻轉正好印證這個顧慮）；②固定200日均線單一濾網，沒有任何
  緩衝帶/遲滯機制去抑制在均線附近反覆穿越造成的高頻切換（8.4次/年對
  一個「長期趨勢」訊號而言明顯過高，象徵均線本身在盤整期會被雜訊反覆
  觸發）。下一個變體（例如加緩衝帶降低切換頻率、改連續曝險縮放、或换
  已實現波動度regime而非純價格趨勢）都還沒被這次結果否證，值得繼續在
  `REGIME_OVERLAY_PROTOCOL.md`第10節「下一步」排隊測試。
- **原始記錄**：`TRIALS_LEDGER.md`#243、`REGIME_OVERLAY_PROTOCOL.md`、
  `regime_overlay_trend_filter_gate.py`（可重複執行，零FinMind API呼叫，
  全用`finmind_client.load_dev()`本機train+val快取）。

### TX連續合約 200MA趨勢濾網 regime overlay（FUT軌配合#10協定第一個訊號，
binary曝險1.00/0.50，2026-09-15 FAIL，但明顯比股票版更接近門檻）

- **哪一關死的**：`REGIME_OVERLAY_PROTOCOL.md`鎖定門檻第1條（MDD縮小
  ≥35%）——在鎖定的基準參數點（MA=200,bear_exposure=0.50）沒有跨過。
  不是成本吃掉優勢死的（跟股票版不同，期貨成本模型年化僅0.167%），也
  不是危機視窗死的（5個TRAIN可測視窗全部改善），是這個基準參數點本身
  的效果量不夠大。
- **具體數字**：TRAIN期(2000-01-04~2020-12-31,n=5214天)基底(TX買進持有)
  MDD=-55.53%；overlay淨(扣期貨成本)MDD=-39.91%（縮小28.1%，門檻≥35%
  FAIL，毛28.5%幾乎相同——證明成本不是這次FAIL的主因）。上檔捕捉率
  78.3%過關。危機視窗5/5改善（2008金融海嘯/2011歐債/2015中國股災/
  2018Q4貿易戰/2020Q1新冠）。控制組(a)隨機開關百分位=100過關。控制組
  (b)延遲1週後MDD=-42.30%仍縮小23.8%，**方向一致無翻轉**（跟股票版的
  疑似前視偏誤不同，這個訊號的保護效果更可信）。控制組(d)參數高原25格
  僅4/25過35%門檻，且集中在`bear_exposure≤0.425`的角落（`(140,0.35)`
  `(140,0.425)` `(170,0.35)` `(200,0.35)`），不構成「一整片都好」——
  這更可能是「曝險水位越低MDD機械性越小」的效果，不是參數穩健證據。
- **這個死法能不能泛化**：**不能**泛化成「FUT軌regime擇時沒用」——
  跟股票版的死法性質不同：股票版死於「保護效果被高頻切換成本吃掉+
  控制組(b)翻轉暗示前視偏誤」，這裡死於「基準參數點(0.50)的效果量本身
  不夠大，但機制方向乾淨、無前視偏誤疑慮、成本不是問題」。**這代表
  FUT軌值得用更低的`bear_exposure`（例如0.35）當新的鎖定參數點重新走
  一輪完整協定**——但這是新的參數點、新的一輪測試，不是本次結果的
  事後參數優化，依「門檻TRAIN先訂死」原則需要總司令核准才能開新一輪，
  不能因為看到控制組(d)這個角落就直接宣稱0.35已經過關。
- **原始記錄**：`TRIALS_LEDGER.md`#244、`REGIME_OVERLAY_PROTOCOL.md`第9節、
  `regime_overlay_trend_filter_gate_fut.py`（可重複執行，零新增API呼叫，
  全用`continuous_contract.py`既有本機快取）。

**⚠️ 續（2026-09-19，總司令裁示【裁示】三「選B」，`REGIME_OVERLAY_
PROTOCOL.md`第15/17節）**：上面「值得用更低`bear_exposure`重新走一輪」
這個建議，**已完整測試，結論是FAIL，不要再引用上面那句話當作未完成的
待辦**。總司令裁示不准直接跑單點0.35重測（提案自己揭露0.35是看過
`#244`結果後選定），改成事前網格`{0.25, 0.35, 0.45}`（MA=200固定），
三格全報：0.25(MDD縮小37.1%/上檔捕捉67.4%)、0.35(37.5%/71.7%)、
0.45(31.2%/76.1%)——四個點（含原始0.50的28.1%/78.3%）連成一條乾淨的
單調效率前緣，**沒有一個曝險水位能同時滿足MDD縮小≥35%與上檔捕捉
≥75%**，危機視窗/控制組(a)/控制組(b)全部乾淨（訊號本身可信、無前視
偏誤），確認死因是機制形式的結構天花板，不是參數選錯或訊號品質問題。
**FUT軌regime overlay（200MA濾網家族）至此正式結案**，跟股票軌候選
2/3/1/4/5併入同一個「機制類別結案：門檻觸發式二元降曝險overlay」條目
（見本檔案下方對應章節）。三格已登記`TRIALS_LEDGER.md`#250/#251/#252。

### TAIEX 回撤斷路器 regime overlay（regime.候選5，自身淨值回撤≥15%降曝險至0.50、回到−7.5%解除，2026-09-19 FAIL）

- **哪一關死的**：`REGIME_OVERLAY_PROTOCOL.md`第3節鎖定門檻第1條（MDD縮小≥35%，
  實測13.5%）與第2條（上檔捕捉率≥75%，實測62.7%）雙雙未過，加上第11節
  鎖定的absorbing state判準（準吸收態）也FAIL。規格在看結果前已於第11節
  鎖定並commit，未調參。
- **具體數字**（TRAIN 2010-01-04~2020-12-31，n=2710）：基底MDD −28.72%→
  斷路器淨 −24.83%；CAGR 5.59%→0.50%；Sortino 0.55→0.11。5次觸發全部
  有解除，但持續134/719/660/249/164交易日，全期71.1%時間在半倉，最長
  719日（門檻504日）；5次觸發期間基底合計漲了約+20%~+26%/次，斷路器
  全數擋掉一半。危機視窗3/4改善（2018Q4未改善，4個TRAIN可測非6個）。
  控制組(b)延遲5日保護完全消失（0.0%）。參數高原X×R共25格0/25達35%，
  且25格全部判準吸收態。切換僅10次（年0.93次），成本3.4%不是主因。
- **死因分類**：**流程對、這條假設結構性無edge**（不是資料或實作錯誤）。
  自身淨值回撤當輸入＋峰值不重置，降曝險後淨值恢復速度減半，解除要求基底
  再漲約17.6%，機制變成「跌了之後長時間不參與反彈」。
- **absorbing state教訓（七之三第9關的落地實例）**：解除條件在數學上可達
  （5次都解除了），所以「永遠不解除」的教科書式吸收態沒有發生；但實務上
  是準吸收。**只看聚合統計（MDD縮小13.5%、控制組(a)百分位100）看不出
  來**，逐筆事件表＋TRIPPED占比才揭露。控制組(a)在此機制下資訊量低
  （隨機排列平均−68pp，因71%半倉時間打散後成本暴增），不可拿來當通過依據。
- **這個死法能不能泛化**：能泛化到「以策略自身績效為輸入且峰值不重置的
  斷路器」這一類；不能泛化到「以外部市場狀態為輸入的降曝險」（那是候選
  1/3/4的範圍）。
- **原始記錄**：`TRIALS_LEDGER.md`#246、`REGIME_OVERLAY_PROTOCOL.md`第11節、
  `regime_overlay_drawdown_breaker_gate.py`（零新增API呼叫，全用TAIEX本機快取）。

### TAIEX 已實現波動度regime overlay（regime.候選3，vol20>expanding中位數→半倉，2026-09-19 FAIL）

- **哪一關死的**：成本前置關卡（協定1a-0）＋`REGIME_OVERLAY_PROTOCOL.md`第3節
  第1條MDD縮小≥35%。毛報酬MDD縮小36.9%（剛過門檻），扣切換成本後淨值
  0.0%；上檔捕捉率72.9%（<75%）亦未過。規格於協定第12節看結果前鎖定。
- **具體數字**（TRAIN 2010-01-04~2020-12-31，warm-up後n=2630）：基底MDD
  −28.72%，overlay淨−28.73%；CAGR 6.42%→0.41%。切換135次（年12.9次，
  比#243趨勢濾網的8.4次更高）、累計成本46.2%、年化4.43%。危機視窗4/4改善
  （毛效果殘影，不救判定）。控制組(b)延遲5日−9.3%；參數高原25格0/25
  （最高淨18.9%）。
- **死因分類**：**流程對、這條假設在真實成本下無edge**（與#243同一死法）。
  吸取候選2教訓，第一版就把成本接進主路徑，結果一次就看到毛淨落差。
- **這個死法能不能泛化**：能泛化到「無緩衝帶、以單一分位數門檻切二元曝險的
  台股現貨overlay」；不能泛化到連續縮放或有遲滯帶的版本（不同機制，需另立
  SPEC並先過1a-0成本前置關卡，不在本輪）。
- **原始記錄**：`TRIALS_LEDGER.md`最新一筆(regime.候選3)、協定第12節、
  `regime_overlay_realized_vol_gate.py`（零新增API呼叫）。

### TAIEX 市場廣度水位regime overlay（regime.候選1，%個股站上200MA<0.50→半倉，2026-09-19 FAIL）

- **哪一關死的**：成本前置關卡（協定1a-0）＋`REGIME_OVERLAY_PROTOCOL.md`第3節
  第1、2條（MDD縮小淨−12.6%＜35%；上檔捕捉64.6%＜75%）。規格於協定第13節
  看結果前鎖定。**與`#28`死因不同**：`#28`是廣度背離旗標貼在50百分位無加值；
  這條的廣度序列有資訊（危機視窗4/4改善、毛MDD縮小26.4%），但被切換成本
  （95次/11年，年化3.27%）與過長防禦時間（56.5%時間半倉）吃光。
- **具體數字**（TRAIN，warm-up後n=2510，廣度宇宙1822檔4位數代號）：基底MDD
  −28.72%→overlay淨−32.34%；CAGR 6.10%→0.29%。控制組(b)延遲5日7.8%。
  參數高原6/25過35%，但全在門檻0.575/0.65，MA200/230/260於0.65皆為46.4%
  ——是幾乎恆半倉的機械性縮小，不是穩健證據。
- **死因分類**：**流程對、這條假設在真實成本下無edge**。
- **但書**：廣度宇宙是「今天仍在市」快取，存活者偏誤（偽影⑦）未修正；用未
  還原收盤價算200MA（除息缺口輕微低估廣度）。兩者皆不影響FAIL判定方向的
  結論（毛效果已不足以撐過成本），但任何日後引用此廣度序列的結果都要附。
- **原始記錄**：`TRIALS_LEDGER.md`最新一筆(regime.候選1)、協定第13節、
  `regime_overlay_breadth_gate.py`（零新增API呼叫，用`data/raw`本機快取）。

### 機制類別結案：門檻觸發式二元降曝險 overlay（台股，2026-09-19 總司令裁示【regime overlay 家族結案】）

**這是家族層級的結案條目，不是單一候選的記錄**——下面五個具體構造
（regime.候選2即`#243`200MA趨勢濾網／候選3已實現波動度／候選1市場廣度
水位／候選4融資餘額成長率／候選5自身淨值回撤斷路器）**全數FAIL**，
各自的詳細數字已記錄在上面（候選2/`#243`）與下面（候選3/1/4，見上一節
候選5）各自的條目裡，這裡只做跨候選的機制層級整併。

**四個有效測試（候選5/3/1/4）的死因高度一致**，指向同一堵牆，不是四個
獨立的訊號品質問題：
- 候選5（回撤斷路器）：上檔捕捉率**62.7%**（門檻≥75%未過），且落入
  準吸收態（`TRIPPED`占比71.1%全期時間，單次觸發最長**719日**才解除）。
- 候選3（已實現波動度）：毛MDD縮小36.9%（剛好過門檻），但年化切換
  **12.9次**，切換成本把淨效果整個吃光，淨MDD縮小僅**0.0%**。
- 候選1（市場廣度水位）：上檔捕捉率**64.6%**（門檻≥75%未過），淨MDD
  縮小僅**−12.6%**（比基底還差，遠低於≥35%門檻）。
- 候選4（融資餘額成長率）：訊號**在最大回撤期間根本沒降曝險**（overlay
  最大回撤與基底完全相同，同為−28.72%），上檔捕捉率85.1%雖然過關，
  但那只是因為訊號幾乎不動作。

**共同死因（機制形式層級，不是訊號品質層級）**：在台股現貨的真實切換
成本（單邊來回約0.585%量級）與大盤長期上行的市場環境下，**門檻觸發式
二元降曝險**這個機制形式本身要付出「錯過約三成五上檔」的結構性代價
——不管輸入訊號換成價格趨勢、已實現波動度、市場廣度、融資餘額或自身
回撤，只要輸出是「跨過門檻就整批砍曝險到固定水位、回落門檻才整批
恢復」這種二元形式，就會在真正的危機期之外的長時間裡持續壓抑上檔（候選
5的準吸收態、候選1/3的高切換頻率都是這個結構天花板的不同表現形式），
且降曝險期間的「保護」在扣除真實成本後往往被切換頻率或防禦時間長度
吃光。**這是機制形式的結構天花板，不是訊號品質問題**——候選1（市場
廣度）跟候選4的死因對照就是證據：候選1的廣度序列本身有真實資訊（危機
視窗4/4改善、毛MDD縮小26.4%），候選4的融資餘額序列則毛效果直接是0，
但兩者都死在同一種機制形式下，代表換再多「更好的訊號」也救不了這個
形式本身的結構問題。

**明確不泛化聲明**：**這不泛化為「regime概念在台股無效」**。下面兩條
是完全不同的機制形式，尚未測試，不受本次結案影響：
1. **連續型曝險調節**（曝險是訊號強度的連續函數，不是二元開關）——
   本次五個候選全部是binary形式，`CLAUDE.md`七之三節「②曝險力道連續
   縮放」本來就預期binary版本更容易讓少數進出場事件的雜訊偽裝成乾淨
   績效或製造這類結構性代價，連續形式尚未被這次結果否證。
2. **regime用在選股權重而非總曝險**——總曝險維持100%，只在不同regime
   下切換因子權重，不降曝險就沒有「上檔損失」這個結構性代價的存在
   基礎，是完全不同的價值主張。

**結案後的紀律**：**不准再新增第六個門檻式二元降曝險訊號**——不管換
什麼輸入序列，都是在同一堵牆上撞第六次，在機制形式本身換掉之前，這個
方向已經窮盡。後續regime相關工作只接受上面兩條替代形式（`PENDING_
QUEUE.md`「regime.替代A」／「regime.替代B」），或總司令另行核准的
第三種機制形式，不接受「換個總體序列再測一次二元開關」這種變體。

**⚠️ 追加（2026-09-19，總司令裁示【裁示】三「選B」）**：FUT軌的
`#244`（同一200MA濾網機制，bear_exposure=0.50，原本「差一點」未結案）
已用事前網格`{0.25,0.35,0.45}`補測完畢，同樣FAIL——四個曝險水位
（含原始0.50）連成一條乾淨的單調效率前緣，沒有一點同時滿足MDD縮小
≥35%與上檔捕捉≥75%。**FUT軌併入本家族結案**，共六個具體構造全部
FAIL（股票軌候選2/3/1/4/5＋FUT軌`#244`+三格網格），同一堵牆。詳見
FUT`#244`條目「⚠️續」小節與`REGIME_OVERLAY_PROTOCOL.md`第17節。

**原始記錄**：候選2/`#243`與FUT版、候選5/3/1見上方鄰近條目，候選4見
本條目正下方條目，`REGIME_OVERLAY_PROTOCOL.md`全篇、`TRIALS_LEDGER.md`
#243/#244/#246/#250/#251/#252及候選1/3/4最新三筆。

**⚠️ 追加（2026-09-19，成本.二稽核重跑，總司令裁示【成本模型更正】）**：
股票軌五個候選（2/3/1/4/5）沿用的共用成本常數
`regime_overlay_trend_filter_gate.py::COST_PER_UNIT_EXPOSURE_CHANGE`原本
硬寫`COMMISSION_RATE*2`(等於1.0折/無折扣)+證交稅0.3%+滑價2*5bps=0.685%/次
切換，**沒有任何折數參數**——比總司令實際1.8折手續費更貴，是本次成本
模型稽核發現的另一個受污染點（FUT軌`#244`/三格網格用的是期貨慣例成本
`ROUND_TRIP_COST_BPS_1X=5bps`，是完全獨立的常數，不受此問題影響，
不需重跑）。已改為`validation.costs.round_trip_cost_pct(commission_discount=
0.18)`=0.4513%/次切換，五個候選逐一重跑（協定/資料/門檻/危機視窗/控制組
設計完全不變），結果：

| 候選 | 淨MDD縮小(舊→新) | 上檔捕捉(舊→新) | 門檻(≥35%/≥75%) | 判定 |
|---|---|---|---|---|
| 2/`#243` 200MA濾網 | 1.8%→**14.6%** | 未變/79.5%(PASS) | 縮小仍FAIL | FAIL不變 |
| 3 已實現波動度 | 0.0%→**19.4%** | 72.9%→73.9%(FAIL) | 兩項皆FAIL | FAIL不變 |
| 1 市場廣度 | −12.6%→**7.8%**(由負轉正) | 64.6%→65.3%(FAIL) | 兩項皆FAIL | FAIL不變 |
| 4 融資餘額成長率 | −0.0%→−0.0%(無變化) | 85.1%→85.4%(PASS) | 縮小仍FAIL | FAIL不變 |
| 5 回撤斷路器 | 13.5%→19.7% | 未過門檻(65.0%,FAIL) | 兩項皆FAIL | FAIL不變 |

**五個候選的FAIL判定全部維持不變**，但這次稽核**加強而非削弱**了「結構性
天花板」的結論：候選2/3/1三個原本被歸類為「主要死因是成本」的候選，
即使成本下修34%（0.685%→0.4513%/次），淨效果雖有感提升（候選3甚至
從完全被吃光的0.0%回升到19.4%），**仍然遠低於35%門檻**，且候選3/1的
上檔捕捉率門檻是與成本無關的獨立指標、同樣未過——證明這不是「成本
偽裝了一個本來能過的訊號」，而是訊號本身確實不夠強。候選4/5的死因
（訊號在關鍵期沒有動作／準吸收態）本來就與成本無關，此次重跑數字
幾乎無變化，交叉驗證了根因分類正確。**家族結案的判定與範圍不變**，
本追加只更新支持證據的可信度。詳見`TRIALS_LEDGER.md`#271-275。

### TAIEX 融資餘額成長率下檔regime overlay（regime.候選4，12週成長率>expanding第80百分位→半倉，2026-09-19 FAIL）

- **哪一關死的**：`REGIME_OVERLAY_PROTOCOL.md`第3節第1條——毛、淨MDD縮小皆為
  0.0%（overlay最大回撤與基底同為−28.72%：訊號在最大回撤期間根本沒降曝險）。
  上檔捕捉率85.1%雖過，但那只是因為幾乎沒動作。規格於協定第14節看結果前鎖定，
  方向事前綁定（過熱→降曝險），不因結果換方向。
- **具體數字**（判定期2013-08-12~2020-12-31，n=1815；融資週資料412週）：危機
  視窗只有3個可判（2011在資料起點前），改善1/3（2015、2020Q1未改善）；切換
  29次（年4.0次）成本9.9%；控制組(b)0.0%；參數高原25格0/25（最高6.5%）。
- **死因分類**：**流程對、這條假設無edge**——與`#26`同一種死因（單一總體
  序列＋週頻，樣本自由度天生不足），且毛效果即為零，不是成本吃掉。
  融資餘額成長在2015中國股災與2020Q1崩盤前都未出現過熱旗標。
- **這個死法能不能泛化**：能泛化到「全市場總融資餘額成長率」這個輸入序列
  （降曝險用途也死了，加上`#26`、`#56`撤案，這條資料礦脈的總體版已窮盡）；
  不能泛化到逐檔融資（已由`#30`測過）或去化方向（本輪不測，事前綁定）。
- **原始記錄**：`TRIALS_LEDGER.md`最新一筆(regime.候選4)、協定第14節、
  `regime_overlay_margin_growth_gate.py`（零新增API呼叫，用本機週頻快取）。

**⚠️ 追加（2026-09-19，`regime.替代A` TRAIN判定，`regime_alt_a_train_verdict.py`，`TRIALS_LEDGER.md` #253~#261九格全FAIL）**：連續型曝險調節（E=clip(1−0.5×risk_z,0.5,1.0)，訊號＝同一200MA距離）主規格淨MDD縮小**25.5%**（門檻≥35%未過）、上檔捕捉**86.4%**（過關）；9格高原**0/9**通過（淨MDD縮小21.1%~26.3%，上檔82.1%~89.2%）。相同訊號並排：二元版（對齊連續版樣本2011-10-27起）淨MDD縮小9.6%、上檔79.1%，連續版確實「保留更多上檔＋成本較低（1.48% vs 2.79%/年）」，但保護力度先天不足，符合規格第16節事前預期（低機率通過）。誠實但書：(1)連續版warm-up較長使樣本起點晚至2011-10-27，2011危機窗僅部分覆蓋（n=47天）；(2)控制組(a)排列法百分位100.0對連續版**無鑑別力**（打亂連續曝險使換手暴增、成本把隨機組拖垮到平均−55.8pp），不作為通過依據；(3)延遲5日後淨MDD縮小掉到4.0%，保護高度依賴訊號時效；(4)價格指數口徑未含股利。**死因分類：流程對、這條假設無edge**（規格事前鎖定、成本內建、無偽影家族包裝）。**這不泛化為「regime概念在台股無效」**：本結案僅涵蓋「曝險水位調節函數」機制類別（二元＋連續兩種形式，不再嘗試第三種函數形式，除非總司令另行核准）；`regime.替代B`（regime用在選股權重而非總曝險）是完全不同的價值主張，尚未測試，不受影響。

### 減資事件CAR（#71，現金減資組＋彌補虧損減資組，恢復買賣日後20交易日，2026-09-19 FAIL）

- **哪一關死的**：第1關cheap gate（`buyback_car_gate.py`同款CAR框架，
  `capital_reduction_car_gate.py`，判準事前寫死於腳本docstring，Bonferroni N=2：
  VAL p<0.05、方向感知控制組百分位>=95、TRAIN/VAL各n>=30且同號且符合綁定方向）。
  805/805檔全數驗證、364筆減資事件（彌補虧損252／現金112）。
- **具體數字**：現金減資 TRAIN n=84 mean_CAR−0.12%(p=0.93)、VAL n=25 mean_CAR−5.93%
  (p=0.0016，**方向與事前綁定「正向」相反**)、控制組百分位0.0；彌補虧損 TRAIN n=183
  −1.31%(p=0.42)、VAL n=68 +2.98%(p=0.23)、TRAIN/VAL不同號、控制組百分位7.5
  （綁定「負向」）。
- **死因分類**：**流程對、這條假設無edge**（兩組方向皆與事前綁定相反或不顯著）。
  現金組VAL顯著為負**不得反轉方向改寫成新假設**——那是看完結果才選方向；要測必須另立
  新假設、事前登記、多算一次試驗。
- **已知限制**：拿不到公告日，t0=恢復買賣日，只測「事後漂移」，**沒有測公告當下反應**，
  所以不能推論「減資公告沒有資訊」。現金組VAL僅n=25（<30）本身就不足以下強結論。
- **原始記錄**：`TRIALS_LEDGER.md` #262/#263、`research/data/capital_reduction_car_gate_result.json`、
  `PENDING_QUEUE.md`【重構.減資】。

### core_tilt市值加權為底構造（TE可行性重測，2026-09-19總司令裁示【0050成分股：
查證不足，重做，且需求規格放寬】二，取代同日稍早`成本.二`稽核fork的
第一輪判定）

- **哪一關死的**：追蹤誤差（TE）遠超反推所需門檻，前置於任何alpha驗證
  之前的結構性關卡。
- **背景（避免跟同一天稍早的判定混淆）**：同日稍早的`core_tilt_backtest.py`
  第一版（`成本.二`稽核fork建置，`TRIALS_LEDGER.md`#280）用「因子分數
  排序取前N名、才在此子集內市值加權」的選股邏輯，測出TE 11.87%~13.20%，
  診斷根因是「選股邏輯本身不是貼齊基準」。**本次是同一問題的第二輪
  修正**：改成「先按重建市值排序取全市場前50大（近似0050成分股名單）、
  保留全部成員、只做被band限制住的小幅權重傾斜」，理論上更貼近
  `CORE_TILT_SPEC.md`原意，結果**TE不減反增到51.5%~51.7%**（9組
  band×非名單股權重上限網格全數落在這個窄幅區間），比第一輪還差4倍。
- **具體數字**：反推所需TE=2.0631%（目標alpha2.89%,n_years=3.85）。
  9組實測：band∈{1,2,3}pp × non_list_cap∈{0%,5%,10%} 全部
  TE=51.51%~51.66%，beta=1.31~1.41（同樣系統性偏高，非市場中性）。
  最佳一組（band1pp/non_list5pct）TE=51.5112%，仍是門檻的25倍，落入
  總司令原文「TE>5%」分支。
- **根因診斷（比第一輪更具體，這是本輪新發現、比原本假設的「拿不到
  真名單」更精確的一層）**：追查發現87.65%的重建市值集中在單一檔
  （2330台積電）——`factor_ic.sample_universe_ids(300)`（隨機抽300檔
  做因子IC測試用的既有基礎設施，本來就不是為了重建市值加權指數設計的）
  抽出的300檔隨機樣本裡，只有89檔算得出市值代理（PBR×Equity需要兩個
  資料集都有快取），而這89檔裡台積電一檔市值(16.4兆)就佔了其餘88檔
  總和(2.3兆)的7倍以上——**這不是重建方法本身的計算錯誤，是隨機300檔
  抽樣的樣本量級/涵蓋面撐不起市值加權重建**：真實大盤裡台積電雖然
  也是最大權重（0050實際約30~35%），但其他真正的大型股（鴻海/聯發科/
  台達電/金控股等）在這個隨機300檔抽樣裡沒有同時被抽到、或抽到了但
  沒有市值代理資料，導致重建出來的「前50大」變成「台積電＋89檔裡
  剩下的中小型股」，跟真實0050的產業/規模分布完全不像，這正好解釋
  了beta持續偏高（重壓半導體單一巨頭+分散的中小型股尾巴，不是分散的
  藍籌股組合）。
- **兩層根因並存，需分開記錄**：(1)`CORE_TILT_SPEC.md`「2.1.3」節已
  記錄的「0050真實成分股名單拿不到，財務報告書存在但被
  `mopsov.twse.com.tw`的robots.txt擋住，Wayback Machine只驗證到5檔
  成員資格(非市值排序)」——這是**外部資料可得性**的限制；(2)本輪新
  發現的「即使認了用重建市值近似，既有的隨機300檔抽樣基礎設施也撐
  不起市值加權重建」——這是**內部資料涵蓋面**的限制，理論上可以靠
  改用全市場（而非隨機300檔子樣本）的資料載入修正，但那是一次量級
  不同的工程投入（需要載入全市場約1000+檔的價格/PER/資產負債表資料，
  而不是抽樣300檔），本輪未嘗試，留給總司令裁示是否值得投入。
- **這個死法能不能泛化**：**不能**泛化成「market-cap加權為底這個機制
  本身無效」——本次死因明確是資料涵蓋面不足（隨機300檔抽樣不適合
  重建市值加權指數），不是`因子無效`，也不是機制設計錯誤（selection
  邏輯這次已經改對了）。若總司令核准投入全市場資料載入，這條路線
  值得用真正完整的市場宇宙重新測一次，屆時beta應該會顯著往1靠近，
  TE的量級才有意義。
- **原始記錄**：`TRIALS_LEDGER.md`（本輪登記，`register_trial()`）、
  `research/core_tilt_backtest.py`（已改用新選股邏輯，覆蓋掉第一版）、
  `research/core_tilt_backtest_result.json`、
  `research/CORE_TILT_TE_FEASIBILITY.md`「⚠️2026-09-19後續修正」節、
  `CORE_TILT_SPEC.md`「2.1.3」節。
  `PENDING_QUEUE.md`【重構.減資】。

### 產業金流加速度輪動（#73，月頻、accel=(MA5−MA20)/S 前20%產業，2026-09-19 FAIL）

- **哪一關死的**：GATE_SEQUENCE 第2關配對式隨機控制組（`sector_rotation_accel_gate73_gate2.py`，
  500 draws、判準事前寫死：TRAIN與VAL百分位皆>=95、差值同號為正、VAL>=30月）。
  `TRIALS_LEDGER.md` #282（`failed_gates=["gate2"]`）。
- **數字**：TRAIN(101月)訊號月均+1.398% vs控制中位+1.160%，百分位96.0（過）；
  VAL(47月)+1.378% vs +1.324%，差僅+0.054%，百分位61.4（控制組p95=1.70%、max=2.05%，未過）；
  逐年贏控制中位9/13；年化16.86%(TRAIN)/16.51%(VAL) vs 控制中位13.66%/15.72%。
- **死因分類**：**流程對、這條假設無穩定edge**（TRAIN的優勢在VAL幾乎消失，不是流程錯）。
  與Gate 1觀察一致：月間選中產業Jaccard≈隨機、換手近整體換倉，訊號沒有月頻持續性，
  再加上成本前置估算年拖累4.5~6.8%，淨值層面更不划算。
- **限制（不影響判定方向，須誠實附註）**：yf還原價缺519/2014檔（25.8%，訊號與控制組同一規則，配對比較不受影響
  但存活者偏誤未消）；產業分類為2026靜態快照非PIT；T86僅上市股。
- **不接受**：只看TRAIN過關；事後把VAL門檻降到60百分位；換前10%/週頻救援（=同一機制換參數點，
  且會計入多重比較）。
- **能不能泛化**：只能說「法人淨買超加速度做月頻產業輪動」在本資料上沒過關；不代表產業層級資金流訊號無效
  （例如更低頻或事件式用法未測）。
- **原始記錄**：`TRIALS_LEDGER.md`#282、`research/sector_rotation_accel_gate73_gate2.py`/`.json`、
  `HYPOTHESIS_QUEUE.md`#73第8輪、`PENDING_QUEUE.md`【金流一.5】。

### core_tilt（市值加權為底＋主動權重帶＋產業中性，2026-09-19結案，
`TRIALS_LEDGER.md`#283）

- **哪一關死的**：決定性判準（2026-09-19總司令裁示【0050查證採信；但驗證標準改成
  「報酬吻合」不是「名單吻合」】新設立的關卡）——重建組合（純市值前50大，band=0/
  non_list_cap=0，未加任何因子傾斜的最基本版本）日報酬 vs 0050**真實**日報酬的
  相關係數與年化追蹤誤差。判準：TE≤1%合格、1~3%回報裁示、>3%判死。
- **數字**：n=970天重疊。相關係數**0.0102**（幾乎零相關）；年化TE **20.47%**
  （逐年：2021年18.28%／2022年22.43%／2023年13.83%／2024年25.29%，四年一致
  地遠高於3%門檻，不是單一異常年份撐出來的數字）。**對照組（誤導性指標，
  誠實記錄）**：舊的策略層判準（重建組合vs**TAIEX**的CAPM回歸殘差TE）在同一批
  9組holdings×band網格全數顯示TE=0.762%、beta=0.0009，表面上「達標」，但beta
  趨近0代表這個CAPM回歸本來就沒什麼系統性關係可解釋，TE低只是因為投組跟大盤
  幾乎不同步、不是因為追蹤得準——這正是總司令裁示要求改用「對真實0050的報酬
  吻合度」取代「對TAIEX的策略層TE」當決定性判準的理由：舊判準在這個案例上
  會給出偽陽性（PASS），新判準才抓到真正的問題。
- **根因（總司令原文要求明確區分，不得與「因子無效」混淆）**：**無法取得或
  重建足夠貼近的基準籃子**。樣本宇宙306檔中僅146檔有可用市值代理
  （`PBR×Equity`），重建的「市值前50大」實際上是「146檔隨機抽樣子集裡的
  前50大」，不是全市場前50大——2330台積電這類真正的權值股很可能根本不在
  這306檔隨機抽樣宇宙裡（`factor_ic.py::sample_universe_ids()`是無偏隨機
  抽樣，不是刻意涵蓋大型股的抽樣，全市場約1700+檔裡抽306檔，個別特定巨型
  股被抽中的機率不高）。**選股邏輯本身（先市值前50大出發、保留全部只調
  權重，取代舊版「先選股再假裝市值加權」）是站得住的設計更正，因子傾斜
  機制也未被證明有問題**——死因是「用隨機抽樣宇宙近似市值排名，抽樣涵蓋率
  不足以捕捉真正的權值股結構」這個資料方法論限制，不是選股/傾斜邏輯設計
  錯誤，這條區分很重要：往後若要復活這條路線，正確的下一步是解決全市場
  （非抽樣子集）市值排名的資料源問題，不是調整選股/傾斜參數。
- **能不能泛化**：**不泛化**成「市值加權為底＋主動權重帶」這整個機制概念
  無效——這個機制從未在「真正涵蓋全市場权值股的市值排名」下被測過，測的
  只是「用一個隨機抽樣子集近似市值排名」這個具體實作，兩者是不同的問題。
- **除錯過程附帶發現（記錄供未來類似驗證參考，不是本次死因）**：過程中
  修好兩個實作bug：(1) `simulate_equity_curve()`對缺值股票原本用無限期
  forward-fill凍結價格（後改為`limit=5`天有界版）；(2) `returns_based_
  validation()`的日期join原本一邊是Timestamp一邊是字串，型別不一致導致
  `pd.concat(...,join="inner")`找不到任何重疊列，先前兩次重跑都誤報
  「0天重疊」（不是真的沒有重疊資料，是join本身失效）。兩個bug都已修好
  並在`CORE_TILT_TE_FEASIBILITY.md`留下修復記錄，這次的FAIL判定是在兩個
  bug都修好之後、乾淨執行下得到的，不是bug污染的結果。
- **原始記錄**：`TRIALS_LEDGER.md`#283、`research/core_tilt_backtest.py`
  （可重複執行）、`research/core_tilt_backtest_result.json`、
  `research/CORE_TILT_TE_FEASIBILITY.md`、`research/CORE_TILT_SPEC.md`。

## #72 重大訂單／得標公告效應（Order Win Announcement Effect）— FAIL（合規資料源歷史深度不足，未進第1關；2026-09-20總司令裁示【緊急·合規】結案）

**死因**：本假設事前查證（Gate 10，2026-09-15）已確認合規官方端點
（TWSE openapi `t187ap04_L`、TPEx openapi `mopsfin_t187ap04_O`）皆是
**snapshot-only、無日期區間查詢參數**——2026-09-20用官方swagger規格檔
（`https://openapi.twse.com.tw/v1/swagger.json`、`https://www.tpex.
org.tw/openapi/swagger.json`）重新確認，兩個端點的GET定義**完全沒有
宣告任何查詢參數**，這不是本專案功力不夠找不到參數，是官方本來就沒
提供。唯一支援關鍵字＋歷史年度區間查詢的介面`t51sb10`（重大訊息主旨
全文檢索）**只存在於`mopsov.twse.com.tw`**——這個網域robots.txt全站
`Disallow: /`（僅bingbot例外，2026-09-08已查證，見`docs/DATA_SOURCE_
MAP.md`），本專案不得程式取用。本條目Gate 10查證階段找到`t51sb10`
「功能上可行、歷史回溯到2015年」時，沒有同步核對它落在哪個網域上，
2026-09-19~20因此發生違規事件（`research/material_disclosure_order_
win_count.py`對mopsov發出100次請求，`research/material_disclosure_
order_win_probe.py`更早的探查階段也有真實請求）——兩支腳本已加
`PermissionError`停用，違規細節見`PENDING_QUEUE.md`「違規事件記錄」。

**根因精確分類（比照`CLAUDE.md`根因分類鐵律，不能只寫「資料不可及」
就結束）**：不是「完全沒有合規來源」（合規來源確實存在且本專案自己
的`fetch_news_events.py`已在用），也不是「因子無效」（經濟機制從未
被測試）——是**「合規來源存在但只能前向累積（2026-09-08起，本輪結案
時約12天深度），無法回溯到2015-2024所需的歷史深度；唯一有歷史深度的
來源不合規且已被永久排除」**這種更精確的中間態，跟`#38`/`#39`同一種
「資料工程限制非機制錯」死法，但比那兩個多了一層「差一點就能合規地
拿到」的教訓。

**依`CLAUDE.md`復盤原則分類**：流程有漏洞——Gate 10「資料源歷史起點
探測」只驗證了「這個功能是否存在、歷史深度夠不夠」，沒有同步驗證
「這個功能所在的網域是否合規」，這兩件事被當成獨立問題各自查證
（網域合規性在`docs/DATA_SOURCE_MAP.md`裡，功能可行性在Gate 10裡），
沒有人在找到「可行路徑」的當下去交叉核對它是否踩在已知紅線上。
**未來Gate 10流程補強建議**：找到任何「可行的資料路徑」後，下一步
必須先核對該路徑的網域是否在`docs/DATA_SOURCE_MAP.md`的🔴清單或
`research/net_guard.py`的黑名單裡，這個核對動作要內化成Gate 10本身
的最後一步，不是查完就直接動手。

**不泛化聲明**：不代表「重大訂單/得標公告後價格延遲反應」這個機制
本身無效——若未來取得書面授權（例如向證交所/櫃買中心申請`t51sb10`的
書面存取許可，比照`ic.tpex.org.tw`「唯一正途是書面授權」的既有先例）
或找到其他合規的歷史結構化來源，此假設值得重新評估，死的只是「目前
合規管道沒有足夠歷史深度」這個工程限制。

**原始記錄**：`TRIALS_LEDGER.md`#284、`research/material_disclosure_
order_win_probe.py`（已停用，保留供稽核）、`research/material_
disclosure_order_win_count.py`（已停用，保留供稽核）、
`research/material_disclosure_order_win_count.json`（已標`_COMPLIANCE_
WARNING`保留作違規證據）、`HYPOTHESIS_QUEUE.md` #72、`research/net_
guard.py`（本次事件催生的網域層防呆）。

## 原子.二 depth-1原子表達式IC地圖 — FAIL（日K原子層找不到穩定素材，2026-09-20總司令裁示【緊急·合規】延伸輪結案）

**死因**：事前登記1592個depth-1表達式（24個原子×19個算子的單層組合）
×2個horizon=3184個測試，300檔樣本cross-sectional Spearman IC描述性
掃描。分年份/分牛熊段穩定度拆解（用`REGIME_OVERLAY_PROTOCOL.md`既有
5個危機視窗）顯示：完整可比較樣本（1950個測試）裡全部5個危機視窗
同號的比例僅**5.03%**，**低於**「5個獨立二元符號剛好全部一致」的
樸素機率基準線6.25%（=2×0.5⁵）——牛熊段穩定度不比純噪音更好。疊加
train/val同號＋crisis同號＋逐年同號率≥0.7＋|VAL IC|>0.02四個條件的
候選只有15/1950（0.77%），遠低於單獨crisis篩選的機率期望值
（約122/1950），且這15個彼此高度共線（`ts_std`/`ts_max`作用在
`true_range`/`gap`等原子上，是同一個波動度概念的不同算子外殼），
不構成獨立發現。

**依`CLAUDE.md`復盤原則分類**：流程對，非流程錯——事前登記搜尋空間、
描述性掃描不做選材、規格要求的分年/牛熊段穩定度拆解如實做完才下判定
（過程中一度只做了TRAIN/VAL兩段聚合就想停下，被要求補齊才是正確
流程）。**額外收穫**：過程中發現並修好一個真實的記憶體事故
（300檔全量跑第一版把每檔股票全歷史×1592表達式常駐記憶體，實測單一
行程衝到18.9GB，把使用者機器可用記憶體從31GB壓到1.26GB，互動視窗CC
手動kill止血並重新設計為只保留snapshot所需日期聯集），以及一個重大
方法論發現（990個涉及基準原子的表達式裡430個是「純基準原子轉換」，
在橫斷面上對每檔股票取值完全相同，cross-sectional IC結構性退化，
非bug，已用個股實測驗證）。

**不泛化聲明**：只否決「這24個原子×19個算子的depth-1單層表達式，用
cross-sectional Spearman IC，20/60日horizon」這個具體搜尋空間——不
代表更深的原子組合（`mul`/`ratio`/交互作用，原子.三原本要測的假設）
沒有機會，只是失去了「用depth-1存活素材當起點」這條路，若未來要測
需要重新設計比較基礎的搜尋策略；也不代表分K頻率或時序型（非橫斷面）
IC沒有機會，本輪只測日K的cross-sectional排序型IC。**原子.三本輪不
開工**——沒有depth-1存活素材可組，這個具體切入點走到底了，不是暫緩。

**原始記錄**：`TRIALS_LEDGER.md`#285（掃描本身）、#286（最終判定）、
`research/atom_ic_map.py`（可重複執行，含記憶體修復與年份/牛熊段拆解）、
`research/ATOM_IC_MAP.md`（完整分析）、`research/ATOM_LIBRARY.py`
（24個原子/19個算子庫本身審閱通過，不受本次FAIL影響——死的是這一次
的搜尋策略，不是原子/算子庫本身的品質）。

## 原子.六 出借總量(TWSE TWT72U) depth-1 IC地圖（2026-09-22 07:24，TRIALS #321）
- **判定FAIL（流程對、這條假設無edge）**：14表達式×2horizon=28測試，高階篩選通過0/28；危機窗全同號僅1/28（level__slb_bal h60，且TRAIN/VAL反號），樸素期望值約1.9無超額。
- **哪一點失效**：跨牛熊段穩定性與TRAIN/VAL同號同時成立者為零。level__slb_ratio(h20)有輕微一致正IC（TRAIN+0.027/VAL+0.025、逐年同號0.87）但危機窗不全同號，且與成交量分母/規模共線未拆解，只算未證實描述性線索。
- **不泛化成「借券出借總量沒用」**：僅指depth-1、日頻lag1、325檔上市股IC地圖層級；出借總量是供給側量，不含借券成本/可借量，放空腿未評估（硬規則：不得採信任何放空腿數字）；僅上市無上櫃。


## #75 內部人買入淨額/買方家數 cross-sectional選股訊號（2026-09-20結案）

**死因**：第1關cheap IC gate，(i)僅有價格版train_IC=+0.0253/val_IC=-0.018正負號相反；
(ii)悲觀填補版train_IC=-0.0683/val_IC=-0.0825同號但為負（事前綁定方向為正）。
兩版本null percentile分別0.5/0.0，遠未過90門檻。 #324。
**不泛化成**：內部人交易資訊完全無用——只測了net_usd/n_buyers兩個聚合訊號、
月頻、cross-sectional排序這個具體構造；未測個股層級事件研究、未測交易後短窗口
（<20日）、未測CEO/CFO角色加權。地基工程（DERA下載/價格補齊/悲觀填補）保留。

## 事件驅動SUE訊號（E1財報公布/E2月營收公布）GATE_SEQUENCE驗證（2026-09-22結案，TRIALS #325/#326）

**死因（流程對、這條假設無edge）**：`event_driven_prototype.py`（#323原型，
分組依事件當下SUE前10%）過完整4關驗證（`event_driven_gate_sequence.py`：
隨機控制組排列檢定N=200／train-val OOS切分／成本敏感度3情境／leave-one-out
時間分桶+產業）——**兩個事件類型都在第2關（隨機控制組）落馬**：
- E1財報SUE（n=6706）：訊號統計量0.0064，未超過控制組最大值0.0093（訊號
  百分位94.5，2026-09-07標準升級後「贏過平均」或「高百分位」都不算通過）；
  唯一未過關卡是gate2，train-val OOS／成本敏感度／leave-one-out三關皆PASS。
- E2月營收SUE（n=20339）：訊號統計量0.0039，未超過控制組最大值0.0055
  （百分位97.0）；且train_median_diff=+0.0065→val_median_diff=-0.0008
  正負號翻轉，train-val OOS也未過，比E1更明確是雜訊。

**哪一點失效**：#323原型只做`tail_test()`方向性檢查（無隨機控制組），
兩事件類型t+20方向一致（median_diff>0、右尾較胖）看起來像PEAD文獻同方向，
但完整驗證後發現那個方向性落在隨機重排控制組的常態擾動範圍內——這正是
七之三節「效果量級越誇張，越應該懷疑」的反向案例：效果量級不誇張、看似
合理，仍然通不過控制組，說明**光有「方向與文獻一致」不能替代隨機控制組
檢定**。

**不泛化成**：SUE類訊號在台股完全無用——本次只測了「事件當下SUE前10%
二元分組×同季度/產業/市值五分位配對對照組×t+20單一horizon」這個具體構造；
未測SUE連續分數加權（非二元閾值）、未測券商財測共識調整版、未測搭配動能
交叉訊號。地基工程（`event_driven_prototype.py`／`event_driven_gate_
sequence.py`）保留，可重複執行供未來變體使用。

## #76 美股VIX期限結構（VIX9D/VIX比值）當TAIEX regime降曝險訊號（2026-09-22結案）

**死因**：第1關cheap gate，`vix_term_structure_gate.py`——訊號=VIX9D/VIX
比值水位、目標=TAIEX後20交易日報酬、TRAIN(<=2020-12-31)/VAL(2020-12-31~
2024-12-31)兩期Pearson+Spearman相關性+N=500洗牌null。**train/val正負號
相反**：TRAIN r=-0.0146(p=0.4777，接近零、不顯著)，VAL r=+0.0849
(p=0.0101，null percentile=98.4，表面顯著)。依三項判準之一「train/val
同號」為必要條件，正負號相反直接判FAIL，不因VAL單期看似贏過洗牌null而
放行——這正是#32美元兌台幣匯率、#75內部人淨額(價格版)同一種死法（train/
val正負號相反）。附帶發現：VAL期的方向(+)恰與事前綁定方向(比值越高即
倒掛越深→後續報酬應越低，即負相關)相反，兩個獨立理由都指向FAIL。#327。

**不泛化成**：VIX期限結構訊號在台股完全無用——只測了VIX9D/VIX比值水位+
M=20交易日單一窗口這個具體操作化；未測比值變動率（速度而非水位）、未測
其他窗口（5/10/60日）、未測VIX絕對水位本身（不取比值）、未測搭配台股
自身波動度（`regime_overlay.py`既有20日波動度窗）的交互作用。地基查證
（`vix_term_structure_probe.py`，確認yfinance `^VIX9D`/`^VIX`起點皆早於
TRAIN_END）保留，可重複執行供未來變體使用。


## #77 美國高收益債利差（BAMLH0A0HYM2）當TAIEX regime降曝險訊號（2026-09-22結案，資料不可及）

**死因**：資料源歷史深度不足，非機制被推翻。FRED官方`BAMLH0A0HYM2`序列2026-04起僅分發近3年觀測值（`hy_credit_spread_probe.py`實測：2023-09-22~2026-09-18共785筆，TRAIN期(<=2020-12-31)0筆覆蓋），三方查證一致：(1)FRED官方序列頁notes明載3年限制且更早歷史僅ICE Data Indices付費可得；(2)用限制生效前的realtime vintage(2026-01-01)重查仍只回2023-09-22起，證實資料庫已回溯截斷；(3)WebSearch交叉比對第三方彙整頁一致。依快殺標準「資料不可及」判FAIL，未進cheap gate，見`TRIALS_LEDGER.md`#329。

**不泛化成「高收益債利差機制對台股regime沒用」**——機制本身從未被測試，死的是目前免費官方通路的歷史深度。備援路徑（改用yfinance可得的HYG/IEF ETF價格比值代理同一機制）已設計為#78，待下一輪查證資料可行性。
