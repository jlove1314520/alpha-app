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

## 已知的歷史陣亡紀錄（回溯整理，非本輪新測——這輪之前`TRIALS_LEDGER.md`
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

---

## `HYPOTHESIS_QUEUE.md`佇列本輪新測的陣亡紀錄

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
  接續#13台股三大法人連續買超持續性（下一個排隊項目，待起跑）。
