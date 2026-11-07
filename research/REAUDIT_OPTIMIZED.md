# REAUDIT_OPTIMIZED.md — 墓園重審：最優化版本總表（先.一五〇-1，Cowork 收件匣 039 已定案）

> **性質：樣本內最優化（描述性），不是判定。** 每一列都是「在 2003-07～2024-12 這段資料上掃參數後挑最好的一組」，所以數字**一定偏樂觀**（挑格子本身就是過擬合來源）；下一步照方針直接上紙上測試，用前向數據說話。2025 以後資料（holdout）本批完全沒讀。非投資建議。

資料期間：2003-07-01～2024-12-31；產生：2026-11-04T19:34:18；程式 `research/reaudit_optimized_batch1.py`（F1～F6）、`research/reaudit_optimized_batch2_tx.py`（F7，台指期連續合約，期間同樣從 2003-07-01 起以對齊無風險利率資料）、`research/reaudit_optimized_batch2_ssu.py`（F8，台股個股，期間 2015-01～2024-12，同 #133 抽樣宇宙 300 檔）、`research/reaudit_optimized_batch2_sector.py`（F9，同 F8 宇宙與期間）、`research/reaudit_optimized_batch2_breadth.py`（F10，期間 2010-12-31～2024-12-31，廣度暖身後才有訊號）、`research/reaudit_optimized_batch2_margin.py`（F11，期間 2013-11-25～2024-12-31，融資餘額 2012-05 起、暖身 52 週）、`research/reaudit_optimized_batch2_weinstein.py`（F12，同 F8 宇宙與期間）、`research/reaudit_optimized_batch2_roe.py`（F13，同 F8 宇宙與期間）、`research/reaudit_optimized_batch2_ml.py`（F14，同 F8 宇宙與期間，模型訓練資料 2011 起）、`research/reaudit_optimized_batch2_us_lowvol.py`（F15，美股，2011-01～2024-12）、`research/reaudit_optimized_batch2_us_value.py`（F16，美股，同 F15）、`research/reaudit_optimized_batch2_coretilt.py`（F17，重建臺灣50 量尺，2013-06～2024-12）、`research/reaudit_optimized_batch2_oddlot.py`（F18，2020-10-26～2024-12，TWTC7U 起點）。**注意：各家族期間不同，綜合分數跨家族比較要看期間**（F1～F7 從 2003-07、F8／F9／F12～F14 從 2015、F10 從 2011、F11 從 2013-11、F15／F16 從 2011、F17 從 2013-06、F18 從 2020-10）。**曲線 png 與明細 JSON 在本機 `research/data/`（該目錄依 .gitignore 不進公開 repo），連結只在本機有效。**

## 0. 總表（依綜合分數＝年化報酬÷|最大回撤| 排名；MDD 超過 50% 的排最後並標天條一）

| 排名 | 家族 | 最好的一組參數 | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 掃描格數（多重比較參考） | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | F11 #249 全市場融資餘額 regime（0050 曝險，2013～2024） | k_weeks=8，pctile=0.7，direction=cold，def_exposure=0.25，freq=M，L=3.0，stop=0.3 | +47.0% | -44.3% | 1.21 | +100.0% | 5 | 1.06 | 2304（其中 873 格 MDD>50%） | [png](data/reaudit_curves/batch2_F11.png) |
| 2 | F18 #383／#232 零股委託簿失衡度組合（台股個股） | rebalance_days=21，direction=高失衡，top_n=30，pos_stop=0.15，L=3.0，stop=0.1 | +24.3% | -25.4% | 1.02 | +50.2% | 602 | 0.96 | 576（其中 205 格 MDD>50%） | [png](data/reaudit_curves/batch2_F18.png) |
| 3 | F12 #11／#393 Weinstein 第二階段（台股個股，引擎版） | ma=150，market_gate=False，top_n=20，pos_stop=None，rebalance_days=21，L=2.0，stop=0.1 | +26.6% | -30.1% | 0.94 | +34.6% | 332 | 0.88 | 384（其中 197 格 MDD>50%） | [png](data/reaudit_curves/batch2_F12.png) |
| 4 | F16 #128／#144 f_us_value_bm 美股價值（只做多） | lowvol_filter_window=0，N=25，rebalance_days=126，L=1.5，stop=0.2 | +26.9% | -30.7% | 1.04 | +75.0% | 137 | 0.88 | 288（其中 122 格 MDD>50%） | [png](data/reaudit_curves/batch2_F16.png) |
| 5 | F15 #64／#151 f_us_low_vol 美股低波動（只做多） | vol_window=20，N=50，rebalance_days=21，L=1.0，stop=0.1 | +13.3% | -15.5% | 1.21 | +67.3% | 2540 | 0.86 | 384（其中 138 格 MDD>50%） | [png](data/reaudit_curves/batch2_F15.png) |
| 6 | F14 #475／#483 ML 價量選股（HGB 逐年重訓，台股個股，引擎版） | horizon_eq_rebalance_days=63，market_gate=False，top_n=30，pos_stop=0.15，L=1.0，stop=0.2 | +10.9% | -13.1% | 1.30 | +35.7% | 516 | 0.83 | 384（其中 77 格 MDD>50%） | [png](data/reaudit_curves/batch2_F14.png) |
| 7 | F10 #248 全市場廣度 regime（0050 曝險，2011～2024） | ma=250，threshold=0.4，def_exposure=0.0，freq=M，L=3.0，stop=0.3 | +31.0% | -48.2% | 0.91 | +63.6% | 11 | 0.64 | 1152（其中 227 格 MDD>50%） | [png](data/reaudit_curves/batch2_F10.png) |
| 8 | F17 #446 core_tilt v2 成分內傾斜（重建臺灣50 總報酬量尺） | tilt_pp=0.02，industry_band=0.03，rebalance_days=63，direction=順向，L=1.0，stop=0.1 | +14.8% | -23.2% | 1.05 | +57.6% | 92 | 0.64 | 512（其中 224 格 MDD>50%） | [png](data/reaudit_curves/batch2_F17.png) |
| 9 | F2 #426 危機閘門 × 槓桿 Bb-90（月均線／絕對動能閘門） | mix=B，w_eq=0.85，safe=IEF，gate=MA6m，L=1.0，stop=0.1 | +10.1% | -17.9% | 1.05 | +64.0% | 25 | 0.57 | 1344（其中 244 格 MDD>50%） | [png](data/reaudit_curves/batch1_F2.png) |
| 10 | F7 #244／#250～#252 台指期均線擇時（TX 連續合約） | ma_days=100，bear_exposure=0.0，L=1.0，stop=None | +10.8% | -21.2% | 0.83 | +25.2% | 115 | 0.51 | 240（其中 115 格 MDD>50%） | [png](data/reaudit_curves/batch2_F7.png) |
| 11 | F6 #430 R1 信用利差閘門（BAA10Y） | spread_ma_months=18，w_eq=0.7，L=1.0，stop=None | +8.1% | -16.3% | 0.86 | +71.4% | 14 | 0.50 | 96（其中 23 格 MDD>50%） | [png](data/reaudit_curves/batch1_F6.png) |
| 12 | F8 #133／#136／#137／#384 融券使用率最低 N 檔（台股個股，多頭鏡像半邊） | top_n=10，rebalance_days=42，pos_stop=0.15，L=1.0，stop=0.1 | +6.0% | -12.8% | 0.70 | +51.9% | 162 | 0.47 | 576（其中 106 格 MDD>50%） | [png](data/reaudit_curves/batch2_F8.png) |
| 13 | F9 #282（#73）產業金流加速度輪動（台股個股，引擎版） | accel_ma=20-60，top_frac=0.2，top_n=30，rebalance_days=21，pos_stop=None，L=1.0，stop=None | +4.0% | -9.5% | 0.66 | +48.7% | 791 | 0.43 | 512（其中 177 格 MDD>50%） | [png](data/reaudit_curves/batch2_F9.png) |
| 14 | F1 #418／#425 Bb-90 核心配置（0050／VTI＋債／現金） | mix=B，w_eq=0.5，safe=IEF，L=1.0，stop=0.1 | +6.8% | -16.9% | 0.99 | +80.0% | 5 | 0.40 | 576（其中 329 格 MDD>50%） | [png](data/reaudit_curves/batch1_F1.png) |
| 15 | F13 #16／#17 f_quality_roe_stability 最高 N 檔（台股個股，只做多頭半邊） | rebalance_days=63，market_gate=True，top_n=20，pos_stop=0.15，L=1.0，stop=0.2 | +4.5% | -11.4% | 0.57 | +27.3% | 348 | 0.40 | 384（其中 87 格 MDD>50%） | [png](data/reaudit_curves/batch2_F13.png) |
| 16 | F3 #414 0050 趨勢槓桿（日均線） | ma_days=50，bear_exposure=0.5，L=3.0，stop=0.1 | +13.7% | -45.6% | 0.54 | +48.1% | 104 | 0.30 | 160（其中 84 格 MDD>50%） | [png](data/reaudit_curves/batch1_F3.png) |
| 17 | F5 #247 已實現波動度 regime（0050） | vol_win=60，hi_vol_exposure=0.25，L=1.0，stop=None | +6.9% | -23.9% | 0.58 | +100.0% | 1 | 0.29 | 144（其中 49 格 MDD>50%） | [png](data/reaudit_curves/batch1_F5.png) |
| 18 | F4 #413 美股趨勢槓桿（VTI 台幣計，日均線） | ma_days=250，bear_exposure=0.5，L=1.0，stop=None | +7.0% | -33.4% | 0.54 | +100.0% | 1 | 0.21 | 160（其中 108 格 MDD>50%） | [png](data/reaudit_curves/batch1_F4.png) |
| 對照 | 0050 買進持有（含息） | — | +11.6% | -55.8% | 0.64 | — | — | 0.21 | — | — |

### 同一家族裡「MDD≤50% 前提下年化最高」的一組（給想看報酬上限的人）

| 家族 | 參數 | 年化 | MDD | Sharpe | 交易次數 |
|---|---|---|---|---|---|
| F11 | k_weeks=8，pctile=0.7，direction=cold，def_exposure=0.25，freq=M，L=3.0，stop=0.3 | +47.0% | -44.3% | 1.21 | 5 |
| F18 | rebalance_days=21，direction=高失衡，top_n=30，pos_stop=0.15，L=3.0，stop=0.1 | +24.3% | -25.4% | 1.02 | 602 |
| F12 | ma=150，market_gate=False，top_n=20，pos_stop=0.15，rebalance_days=21，L=3.0，stop=0.1 | +38.2% | -45.8% | 1.03 | 375 |
| F16 | lowvol_filter_window=0，N=10，rebalance_days=21，L=2.0，stop=0.1 | +33.6% | -41.2% | 0.97 | 159 |
| F15 | vol_window=20，N=50，rebalance_days=21，L=3.0，stop=0.2 | +31.5% | -44.3% | 1.04 | 2540 |
| F14 | horizon_eq_rebalance_days=63，market_gate=False，top_n=30，pos_stop=0.15，L=3.0，stop=0.1 | +22.8% | -34.8% | 1.09 | 516 |
| F10 | ma=250，threshold=0.4，def_exposure=0.0，freq=M，L=3.0，stop=0.3 | +31.0% | -48.2% | 0.91 | 11 |
| F17 | tilt_pp=0.02，industry_band=0.03，rebalance_days=63，direction=順向，L=2.0，stop=0.2 | +22.2% | -47.2% | 0.85 | 92 |
| F2 | mix=B，w_eq=0.85，safe=IEF，gate=MA6m，L=3.0，stop=0.2 | +22.8% | -46.7% | 0.98 | 26 |
| F7 | ma_days=100，bear_exposure=0.5，L=2.0，stop=0.2 | +21.6% | -48.3% | 0.83 | 20 |
| F6 | spread_ma_months=18，w_eq=0.7，L=3.0，stop=None | +20.3% | -46.3% | 0.78 | 14 |
| F8 | top_n=10，rebalance_days=42，pos_stop=None，L=2.0，stop=None | +8.9% | -36.8% | 0.53 | 162 |
| F9 | accel_ma=5-20，top_frac=0.3，top_n=30，rebalance_days=42，pos_stop=0.15，L=1.5，stop=0.1 | +4.8% | -17.8% | 0.54 | 486 |
| F1 | mix=B，w_eq=0.9，safe=IEF，L=2.0，stop=0.1 | +15.6% | -41.6% | 0.87 | 42 |
| F13 | rebalance_days=63，market_gate=True，top_n=10，pos_stop=0.15，L=1.0，stop=None | +5.8% | -17.6% | 0.59 | 162 |
| F3 | ma_days=50，bear_exposure=0.5，L=3.0，stop=0.1 | +13.7% | -45.6% | 0.54 | 104 |
| F5 | vol_win=20，hi_vol_exposure=0.25，L=2.0，stop=0.3 | +13.0% | -46.1% | 0.61 | 4 |
| F4 | ma_days=250，bear_exposure=0.5，L=1.5，stop=0.2 | +8.6% | -47.3% | 0.50 | 10 |

## 1. 前 20 個家族怎麼挑的、目前做到哪

抽取規則〔自行裁量〕：TRIALS_LEDGER.md 表格列與 TRIALS_REGISTRY.jsonl 的 result／notes 文字裡，用「年化…X%」樣式抓數字，每列取最大值；457 列中只有 47 列有可抓的年化數字（其餘多是 IC／百分位檢定，沒記報酬）。同一機制的網格／重跑列併成一個家族。#425／#428 的高數字是 2025 年 OOS（holdout 期），只拿來排序、不拿來回測。

| 序 | 家族（來源試驗） | 當時記錄的最高年化 | 類型 | 本批狀態 |
|---|---|---|---|---|
| 1 | #64／#151 f_us_low_vol 小型股 | 280%／121% | 個股橫斷面（美股） | F15（第 2 批，2011～2024，只做多，價格改 yfinance，同 #151 分層抽樣宇宙）；原數字含放空腿且當時已判經濟上不可信 |
| 2 | #128／#144 f_us_value_bm | 121% | 個股橫斷面（美股） | F16（第 2 批，2011～2024，只做多，B/M 用 SEC XBRL PIT，同 F15 宇宙）；原數字含放空腿且當時已判經濟上不可信 |
| 3 | #418／#420／#425 Bb-90 核心配置 | 38.36%（#425 為 2025 OOS，不用） | ETF 配置 | F1 |
| 4 | #424／#426／#428 危機閘門 × 槓桿 Bb-90 | 22.23%（#428 為 2025 OOS，不用） | ETF 配置＋閘門 | F2 |
| 5 | #133／#136／#137／#384 借券賣出使用率 | 19.89% | 個股組合（台股） | F8（第 2 批，2015～2024，`research/backtest/` 引擎） |
| 6 | #171 宇宙離散度 | 18.42% | 描述性檢驗（非策略） | 不適用，跳過並遞補 |
| 7 | #282 產業金流加速度輪動（#73） | 16.86% | 產業輪動（台股） | F9（第 2 批，2015～2024，`research/backtest/` 引擎，同 F8 抽樣宇宙） |
| 8 | #430 R1 信用利差閘門 | 15.13% | ETF＋閘門 | F6 |
| 9 | #413 美股趨勢槓桿 | 13.47% | ETF 擇時 | F4 |
| 10 | #16／#17 f_quality_roe_stability 多空 | 13.2% | 個股多空（台股） | F13（第 2 批，2015～2024，只做多頭半邊，同 F8 抽樣宇宙） |
| 11 | #414／#243 0050 趨勢槓桿 | 11.15% | ETF 擇時 | F3 |
| 12 | #416 趨勢 1.5×／0.5× 跨市場 | 5.46% | ETF 擇時 | F3／F4 格子內含 L＝1.5、空頭曝險 0.5（相乘後為 0.75×，不完全相同） |
| 13 | #247 已實現波動度 regime | 4.43% | ETF 擇時 | F5 |
| 14 | #248 全市場廣度 regime | 3.27% | ETF 擇時（需個股廣度） | F10（第 2 批，2010-12～2024，0050 曝險） |
| 15 | #483 ML 價量（2008～2012） | 2.88% | 個股模型 | F14（第 2 批，2015～2024，HGB 逐年重訓，同 F8 抽樣宇宙與引擎） |
| 16 | #253～#261／#349 regime 替代 A（MA×k） | 2.37% | ETF 擇時 | F3 格子已涵蓋（日均線＋空頭曝險） |
| 17 | #249 全市場融資餘額 regime | 1.38% | ETF 擇時（需融資資料） | F11（第 2 批，2013-11～2024，0050 曝險） |
| 18 | #11／#393 Weinstein 第二階段 | 1.05% | 個股（台股） | F12（第 2 批，2015～2024，`research/backtest/` 引擎，同 F8 抽樣宇宙） |
| 19 | #283 core_tilt 市值前 50 | 1.0% | 重建 0050 吻合度驗證（非策略） | 不適用，跳過並遞補（同 #171） |
| 20 | #244／#250～#252 台指期 200MA | 0.25% | 期貨擇時 | F7（第 2 批） |
| 21 | #445／#446 core_tilt v2 成分內傾斜（遞補 #171） | −0.92%（超額） | 重建 0050 成分內傾斜 | F17（第 2 批，2013-06～2024，同 #446 量尺，含反向） |
| 22 | #232／#383 零股委託簿失衡度組合（遞補 #283） | −1.79%（alpha） | 個股組合（台股） | F18（第 2 批，2020-10-26～2024，同原版抽樣宇宙與引擎） |

## 2. 回測規則（照實算）

- 訊號只用當天收盤以前看得到的資料，隔一個交易日生效；月頻閘門在月底收盤決定。
- 槓桿＝每日再平衡合成（L×r −(L−1)×無風險利率 − 1%/年），同 #421；權益跌到 0 就停在 0。
- 成本：台股腿買賣各 0.1% 滑價＋0.0855% 手續費、賣出加 0.1% ETF 證交稅；美股腿 0.3% 匯兌；配息扣 30% 預扣稅（沿用 #418）。
- 止損：淨值從持倉高點回落超過 s 全數退現金，21 個交易日後才依訊號重新進場。
- 勝率／交易次數定義：一次「從空手到有風險部位、再回到空手」算一筆；一直持有的配置型策略只算 1 筆（勝率意義有限）。
- F1～F7 是 ETF／指數／期貨層級，沒有個股下市與漲跌停問題；個股層級家族（第二批）用 `research/backtest/` 引擎處理下市與漲跌停。
- F8（個股）：`research/backtest/` 引擎＝下一交易日成交、漲跌停鎖住不成交、缺價／下市照引擎處理、手續費＋0.3% 證交稅＋滑價；槓桿＝融資，借款部分 6.5%/年〔自行裁量〕、融資上限約 2.5×，**3× 台股個股實務上做不到、只當參考**；追繳以權益歸零近似（偏樂觀）。只做多頭鏡像半邊（買融券使用率最低），沒有放空腿。宇宙是當下抽樣的 300 檔，存活者偏誤未完全排除（偏樂觀）。交易次數＝個股賣出筆數、勝率＝賣出已實現損益>0 比例。對照組是同期加權價格指數（不含息）。
- F9（產業金流加速度）：同 F8 引擎、宇宙、成本與融資假設；訊號＝三大法人產業淨買賣加速度（換股日當天收盤以前，隔日開盤成交），取前 top_frac 產業、產業內以產業加速度當分數挑前 N 檔等權。產業分類是 `data/company_info.json` 靜態快照（非 PIT，偏樂觀）；抽樣宇宙下每個產業只剩抽到的個股（和 #282 用全部成分股不同）。另外 N 檔名額常常湊不滿（選中的產業在抽樣裡個股不夠），沒用到的名額放現金，年化與回撤都因此偏低。
- F10（全市場廣度）：回測、成本、槓桿、止損與 F3 同一套 simulate()；廣度＝本機 `data/raw` 4 位數代號個股站上 MA 的比例（今天仍在的名冊、未還原價，存活者偏誤未修正，偽影⑦）；另掃「月底才更新訊號」變體（#248 原版死在一年切換 9.5 次的成本）。**F10 第 1 名的但書**：它是 3× 槓桿、MDD −48.2%，只比天條一 50% 上限少 1.8 個百分點；回測期間 2010-12 起、**不含 2008 年**（廣度快取從 2010 起），遇到 2008 那種跌法很可能直接越線；只有 11 筆交易、1,152 格裡挑出來的，過擬合風險最高，不能當成它真的最好。
- F11（全市場融資餘額）：同 F3／F10 的 simulate()；訊號＝TWSE MI_MARGN 週頻融資餘額 k 週成長率對自己的 expanding 百分位（PIT），週五收盤後已知、隔日生效；另掃原版沒測過的反向「去槓桿（成長率偏低）才降曝險」。**F11 第 1 名的但書**：它是 3× 槓桿＋反向「去槓桿」方向、MDD −44.3%；期間 2013-11 起是長多頭（0050 同期年化 +15.5%），**不含 2008**；防禦曝險 0.25 不歸零所以只算 5 筆、勝率 100% 沒有意義；2,304 格挑出來，過擬合風險高。只開 1×、無止損時最好的一組（12 週、去槓桿、月頻）年化 +15.7%、MDD −21.3%，和 0050 同期 +15.5%／−34.0% 比，主要好處在回撤。
- F12（Weinstein 第二階段）：同 F8 引擎、宇宙、成本與融資假設；還原收盤 > MA_n 且 MA_n 比 10 日前高、以 60 日報酬排序，可選大盤 200 日均線閘門；引擎第一層出場線同步改成 MA_n。最好的一組沒開大盤閘門、2× 融資、組合止損 10%；2× 以上融資在台股個股屬實務上限邊緣，追繳以權益歸零近似（偏樂觀）；宇宙為抽樣 300 檔、存活者偏誤未完全排除。
- F13（ROE 穩定度）：同 F8 引擎、宇宙、成本與融資假設；#16／#17 原版是十分位多空，這裡只做多頭半邊（放空腿借券成本未接真實資料，依放空腿硬規則不做），所以和原版 13.2% 的多空價差不能直接比。原版數字含放空腿，屬資料缺陷、不得採信。槓桿在這個家族沒有幫助（報酬低於融資利率 6.5%，加槓桿反而變差）。
- F14（ML 價量）：同 F8 引擎、宇宙、成本與融資假設；HistGradientBoostingRegressor 預設參數、#483 同一組 10 個價量因子，標籤＝每月第一個交易日起 H 日報酬的橫斷面百分位；測試年 Y 的模型只用標籤到期日早於 Y-01-01 的樣本訓練（2011 起擴張視窗），只用當時看得到的資料。#483 原版是 2008～2012 全市場、天條一 −52.75% 死在 2008；這裡期間 2015 起**不含 2008**、宇宙是抽樣 236 檔，和原版不能直接比。
- F15／F16（美股個股）：價格改走美股原生來源 yfinance（原版走 FinMind `USStockPrice`，台灣資料商，違反七節），一次批次下載 248 檔＋SPY（2010-01～2024-12，auto_adjust 還原股息與分割），存本機 `research/data/reaudit_us_prices.pkl`，246 檔有價；宇宙＝#151 的 `data/us_stratified_universe_sample.csv`（**今天還在的名冊**分層抽樣，存活者偏誤很重：同宇宙等權持有 2011～2024 年化 +21.8%、MDD −38.8%，遠高於 SPY 的 +13.7%／−33.7%，所以 F15／F16 要跟這個等權數字比，不是跟 SPY 比）。只做多（原版十分位多空含放空腿，依放空腿硬規則原版數字屬資料缺陷、不得採信）。訊號第 t 日收盤算、t+1 日收盤成交；換手成本單邊 0.10%〔自行裁量〕；槓桿借款＝DTB3＋1.5%/年〔自行裁量〕，3× 超過 Reg T 2× 上限只當參考。勝率＝換股期組合報酬>0 的比例、交易次數＝被換出的個股筆數（個股逐筆損益未追蹤）。F15 最好的一組（20 日波動、50 檔、月換、1×、止損 10%）年化 +13.3%／MDD −15.5%，**低於同宇宙等權 +21.8%**，好處只在回撤。F16 的 B/M 用 `us_factors_value.book_value_per_share_pit()`（SEC XBRL，本機快取 246/246 命中、零新請求），期末 158 檔有值，2011 年前後 XBRL 覆蓋較少。
- F17（core_tilt v2）：完全沿用 #446 的量尺與 A_4pass 分數、tilt() 映射、成本（`round_trip_cost_pct()` 按單邊換手）、總報酬（含息）；只把傾斜幅度（2／5／10／20pp）、產業偏離上限（3pp／不設）、再平衡間隔（21／63 日）與方向（順向／反向）拿來掃。交易次數＝權重重設次數、勝率＝各重設期間報酬>0 比例。對照組是不傾斜的重建臺灣50（同量尺、1×）。量尺本身缺自由流通係數、台積電權重偏低約 7pp。**F17 的重點：傾斜本身沒有加分**——最好的一組（原版 2pp、63 日、1×、止損 10%）年化 +14.8%／MDD −23.2%，但不傾斜臂套同樣 10% 止損是 +15.6%／−24.4%（綜合分數 0.64，幾乎一樣、年化更高）；不加止損時傾斜 +14.0% 也輸不傾斜 +14.4%。改善全來自組合止損，不是因子傾斜。
- F18（零股失衡）：同原版 `odd_lot_imbalance_portfolio_v1.py` 的分數與流動性下限、原版抽樣宇宙與 `research/backtest/` 引擎；兩個方向都掃；期間只有約 4 年（TWTC7U 2020-10-26 起），不含 2008／2015／2018 空頭。**F18 第 1 名的但書**：最好的一組是**反過來挑高失衡**（原版挑低失衡）、3× 融資、止損 10%（+24.3%／−25.4%），3× 超過台股融資上限只當參考；1× 最好的一組（高失衡、10 檔、63 日、止損 10%）只有 +9.6%／−11.6%，低於同期加權價格指數 +14.9%。
- 美股（VTI）結論附但書：**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小，但書照附；F15／F16 是個股，影響大。）

<!-- EXT2025-BEGIN -->

## 3. 2025 起補跑（先.一五五-2，Cowork 收件匣 039 已定案；保留資料已開放，先.一五五-1）

> 期間延長到 **2026-10-05**（0050 本機快取到 2026-11-06、VTI／IEF 快取到 2026-10-05，取共同終點）；「2025 起段」＝2025-01-01～2026-10-05，約 1.8 年。產生：2026-11-06T21:37:54；程式 `research/reaudit_ext2025.py`（呼叫第一批同一支 `reaudit_optimized_batch1.py` 的網格與 simulate()，只用 `REAUDIT_END` 把終點延長）。**零新外部請求**：0050 2025 起讀本機 FinMind 快取原始收盤＋現金股利（除息日加回）＋2025-06-18 分割（188.65→47.16 參考價比值），其餘利率／匯率／美股 ETF 都是既有快取。性質仍是描述性，不是判定；非投資建議。

**怎麼讀**：①欄是 2024 底以前挑出來的最優組**原封不動**往後跑——2025 起段那一欄完全沒拿來調參，是這張表裡最接近「樣本外」的數字；②欄是把 2025 起也放進去重新挑一次，一定比①好看（又多挑了一次），只當參考。

對照 0050 買進持有（含息）：全期年化 +15.1%、MDD -55.8%；2025 起段年化 +67.3%、MDD -27.5%、Sharpe 2.00。

| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化的參數 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 #418／#425 Bb-90 核心配置（0050／VTI＋債／現金） | mix=B，w_eq=0.5，safe=IEF，L=1.0，stop=0.1 | +6.8%／-16.9% | +15.0% | -12.2% | 1.69 | +7.4%／-16.9% | mix=B，w_eq=0.5，safe=IEF，L=2.0，stop=0.1 | +12.7%／-28.9%／1.06 | +35.2%／-18.2% | 未越線 | [png](data/reaudit_curves/ext2025_F1.png) |
| F2 #426 危機閘門 × 槓桿 Bb-90（月均線／絕對動能閘門） | mix=B，w_eq=0.85，safe=IEF，gate=MA6m，L=1.0，stop=0.1 | +10.1%／-17.9% | +22.4% | -20.1% | 1.66 | +11.0%／-23.4% | mix=B，w_eq=0.85，safe=IEF，gate=MA10m，L=3.0，stop=0.2 | +26.1%／-42.0%／1.07 | +100.5%／-30.1% | 未越線 | [png](data/reaudit_curves/ext2025_F2.png) |
| F3 #414 0050 趨勢槓桿（日均線） | ma_days=50，bear_exposure=0.5，L=3.0，stop=0.1 | +13.7%／-45.6% | +109.4% | -35.9% | 1.85 | +19.1%／-45.6% | ma_days=50，bear_exposure=0.5，L=3.0，stop=0.1 | +19.1%／-45.6%／0.67 | +109.4%／-35.9% | 未越線 | [png](data/reaudit_curves/ext2025_F3.png) |
| F4 #413 美股趨勢槓桿（VTI 台幣計，日均線） | ma_days=250，bear_exposure=0.5，L=1.0，stop=None | +7.0%／-33.4% | +13.6% | -16.4% | 0.97 | +7.5%／-33.4% | ma_days=250，bear_exposure=0.5，L=1.0，stop=None | +7.5%／-33.4%／0.58 | +13.6%／-16.4% | 未越線 | [png](data/reaudit_curves/ext2025_F4.png) |
| F5 #247 已實現波動度 regime（0050） | vol_win=60，hi_vol_exposure=0.25，L=1.0，stop=None | +6.9%／-23.9% | +22.4% | -7.4% | 2.31 | +8.0%／-23.9% | vol_win=20，hi_vol_exposure=0.25，L=1.5，stop=0.2 | +12.2%／-34.1%／0.72 | +47.6%／-12.2% | 未越線 | [png](data/reaudit_curves/ext2025_F5.png) |
| F6 #430 R1 信用利差閘門（BAA10Y） | spread_ma_months=18，w_eq=0.7，L=1.0，stop=None | +8.1%／-16.3% | +4.8% | -10.8% | 0.46 | +7.9%／-16.3% | spread_ma_months=6，w_eq=0.7，L=1.0，stop=0.1 | +7.9%／-14.7%／0.86 | +19.8%／-10.9% | 未越線 | [png](data/reaudit_curves/ext2025_F6.png) |

**天條一（MDD>50%）**：F1～F6、F12～F14 沒有任何一組（①或②）越過 50%（F12 全期 -48.1% 逼近，見 3b）；**F10 原最優組（3 倍）全期 MDD -51.7% 越過天條一**（2025 起段本身 -32.8%，是 2024 高點延續到 2025-04 的回撤疊加），見 3c 與 `DRAWDOWN_FIX.md` 第 6 節。

### 3b. 個股引擎家族（`research/reaudit_ext2025_engine.py`，零新外部請求）

期間 2015-01～2026-09-24（本機個股 2025 起快取的共同終點）；宇宙同第二批 #133 抽樣 236 檔。2025 起價格讀 `TaiwanStockPrice__{代號}__2025-01-01__latest.parquet`，還原權息用「漲跌」欄（當日報酬＝收盤÷(收盤−漲跌)−1，TWSE 漲跌對除權息參考價計；0050 2025-06-18 分割日 47.57−0.41＝47.16＝官方參考價，已核對），從 2024 最後一筆還原價連乘；還原後沒有任何單日超過 ±10.5%。〔自行裁量〕2024 底仍掛牌但本機沒有 2025 起價格的 45 檔（多為 ETF／債券 ETF，例：0056、00878、00772B），從 2024-11-15 起不再給分數，讓它們在 12 月換股就賣出；2025 起實際交易到這些檔：F12 0 檔、F13 0 檔、F14 0 檔。同段加權指數（價格、不含息）2025-01～2026-09-24 年化 +53.9%、MDD -26.7%。F13 的 2025 起 ROE 穩定度用 `research/reaudit_ext2025_roe_factor.py` 以本機財報快取照原公式重算（PIT＝法定期限，Q4＝次年 3/31），2024 底以前沿用原欄位〔自行裁量：重算值有 4 檔在 2024 下半年與原值小幅不同，為保持與原表可比不覆蓋〕。

| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD（原表） | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F12 #11／#393 Weinstein 第二階段（台股個股，引擎版） | ma=150，market_gate=False，top_n=20，pos_stop=None，rebalance_days=21，L=2.0，stop=0.1 | +26.7%／-30.1%（+26.6%／-30.1%） | +13.2% | -35.8% | 0.53 | +23.8%／-48.1% | key=150_0_20_0.15（ma_gate_topN_個股停損），L=3.0，stop=0.1 | +32.8%／-45.8%／0.91 | +2.8%／-42.6% | **全期 MDD 逼近 50%（未越線）** | [png](data/reaudit_curves/ext2025_F12.png) |
| F13 #16／#17 f_quality_roe_stability 最高 N 檔（台股個股，只做多頭半邊） | rebalance_days=63，market_gate=True，top_n=20，pos_stop=0.15，L=1.0，stop=0.2 | +4.5%／-11.4%（+4.5%／-11.4%） | +12.0% | -19.5% | 0.91 | +5.6%／-19.5% | key=21_1_20_1.0（換股日_gate_topN_個股停損），L=1.0，stop=0.1 | +7.1%／-14.8%／0.71 | +26.6%／-12.8% | 未越線 | [png](data/reaudit_curves/ext2025_F13.png) |
| F14 #475／#483 ML 價量選股（HGB 逐年重訓，台股個股，引擎版） | horizon_eq_rebalance_days=63，market_gate=False，top_n=30，pos_stop=0.15，L=1.0，stop=0.2 | +10.9%／-13.1%（+10.9%／-13.1%） | +22.2% | -17.0% | 1.33 | +12.5%／-17.0% | key=63_0_30_0.15（標籤期_gate_topN_個股停損），L=1.0，stop=0.1 | +12.2%／-14.3%／1.27 | +22.3%／-14.3% | 未越線 | [png](data/reaudit_curves/ext2025_F14.png) |

**F12 怎麼讀**：原最優組（2 倍融資＋10% 組合止損）在沒調參的 2025 起段年化 +13.2%、MDD -35.8%，明顯落後同段大盤；全期 MDD 從 -30.1% 擴大到 -48.1%（回撤從 2024 年高點延續到 2025 年），離天條一 50% 只剩約 2 個百分點。全期重新優化挑到 3 倍＋個股停損 15%，但它在 2025 起段只有 +2.8%、MDD -42.6%——重新優化換來的是更差的 2025 段，代表 F12 的最優格對參數很敏感。融資倍數越高、2025 起段回撤越深（2 倍 -35.8%、重新優化的 3 倍 -42.6%）；要上紙上的話建議先用 1 倍版觀察〔自行裁量建議，未驗證〕。

**F13 怎麼讀**：原最優組（63 日換股、大盤閘門、20 檔、個股停損 15%、1 倍、組合止損 20%）在沒調參的 2025 起段年化 +12.0%、MDD -19.5%、Sharpe 0.91，比 2024 底前（+4.5%／-11.4%）好，但遠落後同段大盤；2025 起段的回撤（-19.5%）比 2024 底前整段最深（-11.4%）還深，全期 MDD 因此變成 -19.5%。全期重新優化挑到 21 日換股＋10% 組合止損，2025 起段 +26.6%／-12.8%——又是重新挑過才好看，只當參考。只做多頭半邊，原版多空數字含放空腿、屬資料缺陷。

**F14 怎麼讀**：原最優組（標籤期＝換股 63 日、不設大盤閘門、30 檔、個股停損 15%、1 倍、組合止損 20%）在沒調參的 2025 起段年化 +22.2%、MDD -17.0%、Sharpe 1.33，Sharpe 跟 2024 底前（1.30）差不多，是這批個股家族裡 2025 起段最穩的一支；2025、2026 兩個測試年的模型都只用標籤到期日早於當年 1/1 的樣本重訓（2015～2024 沿用原分數檔），10 個價量特徵重算後在 2024 底前與原快取 236 檔全部一致。全期重新優化只把組合止損從 20% 改成 10%，2025 起段幾乎一樣（+22.3%／-14.3%）——代表這個家族對參數不敏感，跟 F12 相反。仍落後同段大盤（+53.9%），好處在回撤。

### 3c. 0050 曝險 regime 家族：F10 全市場廣度（`research/reaudit_ext2025_breadth.py`，零新外部請求）

期間 2010-12-31～2026-10-02（廣度面板本機 2025 起快取的終點，0050 同上節接法）；廣度面板＝原版 `TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet` 的 4 位數代號 1888 檔，2025 起接同代號的 `__2025-01-01__latest.parquet`（1378 檔有 2025 起價格；同原版用未還原收盤、今天仍在的名冊，存活者偏誤未修正）。網格同原版 1152 格（其中 251 格 MDD>50%）。同期 0050 含息：全期 +17.0%／-34.0%；2025 起段 +65.1%／-27.5%。

| 家族 | ①原最優組（不重調） | ① 2024 底前 年化／MDD（原表） | ① 2025 起段 年化 | ① 2025 起段 MDD | ① 2025 起段 Sharpe | ① 全期 年化／MDD | ②全期重新優化 | ② 全期 年化／MDD／Sharpe | ② 2025 起段 年化／MDD | 天條一 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F10 #248 全市場廣度 regime（0050 曝險） | ma=250，threshold=0.4，def_exposure=0.0，freq=M，L=3.0，stop=0.3 | +31.0%／-48.2%（+31.0%／-48.2%） | -2.0% | -32.8% | 0.19 | +26.8%／-51.7% | ma=200，threshold=0.4，def_exposure=0.25，freq=M，L=2.0，stop=None | +25.9%／-39.3%／0.96 | +60.5%／-29.6% | **越線（VIOLATES_SURVIVAL）** | [png](data/reaudit_curves/ext2025_F10.png) |

**F10 怎麼讀**：原最優組（MA250 廣度<40% 就全數出場、月頻、3 倍、組合止損 30%）在沒調參的 2025 起段年化 -2.0%、MDD -32.8%，同段 0050 +65.1%——廣度在 2025-04 關稅急跌時跌破 40%、月頻訊號讓它在低點附近出場又沒趕上反彈；全期 MDD 從 -48.2% 擴大到 **-51.7%，越過天條一（VIOLATES_SURVIVAL）**。同一個訊號降到 2 倍、不加止損：全期 +20.1%／-39.3%、2025 起段 +5.3%／-29.6%（壓回 50% 內，見 `DRAWDOWN_FIX.md` 第 6 節）。全期重新優化（MA200、門檻 40%、防禦曝險 25%、2 倍、不止損）全期 +25.9%／-39.3%、2025 起段 +60.5%／-29.6%，但那是又挑一次的結果。交易次數很少（原版 11 筆），結論取決於少數幾次出場時點，過擬合風險高。

**還沒補跑的列（照實寫）**：

- F7：2025 起資料缺：`research/data/raw/TaiwanFuturesDaily__TX__2000-01-01__2024-12-31.parquet` 只到 2024-12-31，本機沒有 TX 2025 起日資料（`taifex_fut_yearly/` 也只到 2024.zip）。補法要新增請求（TAIFEX futDataDown 2025、2026 各 1 次，`taifex_www` 節流），依條目規定先寫提案，本輪不送。
- F8：2025 起資料缺：訊號 f_short_sale_utilization 來自逐檔 `TaiwanStockMarginPurchaseShortSale`，本機 1,058 檔快取全部截在 `__2024-12-31.parquet`、沒有任何 2025 起檔；補要新增 FinMind 請求（236 檔×1 次，這台電腦 FinMind 402），依條目規定先寫提案，本輪不送。
- F9：2025 起資料缺：訊號讀 `research/data/sector_flow_daily_gate73.parquet`（只到 2024-12-31），其來源逐檔三大法人 `TaiwanStockInstitutionalInvestorsBuySell` 本機沒有 2025 起快取；同 F8 要新請求，先寫提案。
- F11：2025 起資料缺：訊號讀 `margin_debt_market_client.load_all_cached()`（`MARGIN_*.parquet` 週快取，607 筆、2012-05-04～2024-12-31，沒有任何 2025 起檔）；本機 `data/margin_maintenance.json` 的全市場融資金額只從 2026-08-25 起、`data/margin_by_stock_history.json` 只從 2026-09-29 起，接不上 2025-01～2026-08。補要新增 TWSE MI_MARGN 請求（約 90 週×1 次，`twse_rwd` 節流），依條目規定先寫提案，本輪不送。
- F18：2025 起資料缺：訊號讀 `research/data/raw_twse_odd_lot/TWTC7U_YYYYMMDD.parquet`（1,092 檔，2020-10-26～2024-12-31，沒有任何 2025 起檔）；補要新增 TWTC7U 請求（2025-01～今約 440 個交易日×1 次），依條目規定先寫提案，本輪不送。
- F15、F16：2025 起資料缺：美股價格 `research/data/reaudit_us_prices.pkl` 只到 2024-12；延長要重新批次下載 yfinance（新請求，先寫提案）。
- PQ（先.一五〇-2 恐慌 PQ，`research/reaudit_ext2025_pq.py`，零請求，DevQueue 20261107-013102）：元件延長重建到 2026-10-02（`research/data/panic_pq_ext2025/`，PQ 名單最後可得日 2026-08-31；上櫃指數 2025 起無快取、不影響觸發）。①原最優組（θ=20%、k=1、N=20、H=120、strict＋peak、止損 15%、1×）不重調：2024 底前 +2.2%／−8.3%（原表 +2.1%／−8.3%）、**2025 起段 +34.7%／−6.6%／Sharpe 2.20**（只有 1 個事件：2025-04-07 關稅急跌，買 17 檔）、全期 +4.7%／−8.3%／0.85、52 筆；同段 0050 +63.1%／−27.8%。②全期重新優化（DevQueue 20261107-030102，`--skip-build`，零請求，152 秒；2,592 引擎格×4 槓桿＝10,368 格，5,671 格 MDD>50%；同原規則 MDD≤50%、≥10 筆、Calmar 最高）：**挑出的最優組與原最優組完全相同**（θ=20%、k=1、N=20、H=120、strict＋peak、止損 15%、1×），全期 +4.7%／−8.3%／Sharpe 0.85／Calmar 0.57、52 筆、9 個事件——加進 2025 起資料沒有改變排名。同一組加槓桿（全期年化／MDD）：1.5× +6.8%／−12.4%、2× +8.8%／−16.4%、3× +12.8%／−24.0%；MDD≤50% 前提下年化最高＝θ20%／N=10／H120／strict＋peak／不設止損／3×：+20.8%／−49.2%（貼著天條一邊緣，不建議）。對照 0050 全期 +14.4%／−54.2%（0050 本身越過天條一）。結果檔 `research/data/reaudit_ext2025_pq.json`、格點 `research/data/panic_pq_ext2025/grid_results.csv`（本機）。曲線 `research/data/reaudit_curves/ext2025_PQ.png`（本機）。F17 見 3d。

**但書**：2025 起段只有約 1.8 年、是 0050 強勢上漲的一段（同段 0050 年化見上），任何只做多台股的組合在這段都會好看，不能拿這一段單獨證明策略有效；①欄的價值在於「沒調參也沒崩」，不是「贏多少」。美股（VTI）腿附存活者偏誤但書：**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小。）曲線 png 在本機 `research/data/reaudit_curves/ext2025_*.png`（該目錄不進公開 repo）。

### 3d. F17 core_tilt v2 成分內傾斜（`research/reaudit_ext2025_coretilt.py`，DevQueue 20261107-013102）

期間 2013-06-03～2026-10-02（本機 2025 起個股價格快取多數終點）。做法：執行期把各模組 VAL_END 改成 2026-10-02、FinMind 改只讀本機聯集快取、原量尺（重建臺灣50，2025 起季審照原規則續排：2025-12、2026-03／06／09 共 4 次異動）與 A_4pass 分數照跑，**不改任何原始碼**〔自行裁量：量尺牽涉市值排名／股本／除權息／因子多個模組，重寫會跟原版分岔〕。個股還原價改走 FinMind 本機快取（yfinance 路徑關掉），所以 2024 底前與原表小幅不同：原最優組 +14.5%／−23.6%（原表 +14.8%／−23.2%）、不傾斜臂 +14.4%（原表 +14.4%）。成分聯集 98 檔，全部有因子。
**⚠️ 請求照實揭露**：第一次執行漏擋 yfinance（走 curl_cffi、不經 Python socket），約 10 分鐘內送出約 100 次 yfinance 請求（寫出 93 個 `research/data/raw_yf/*__2026-10-02.parquet`，未見 429）；已中止並改擋，第二次執行（本節數字）零請求、也沒讀那 93 個檔。已登記在 `C:\alpha\CLAUDE.md` yfinance 一節。

| 列 | 參數 | 2024 底前 年化／MDD／Sharpe | 2025 起段 年化／MDD／Sharpe | 全期 年化／MDD／Sharpe | 重設次數 |
|---|---|---|---|---|---|
| ①原最優組（不重調） | 2pp、產業偏離 3pp、63 日、順向、1×、組合止損 10% | +14.5%／−23.6%／1.02 | +46.1%／−15.6%／1.81 | +18.2%／−23.6%／1.15 | 108 |
| 對照：不傾斜重建臺灣50 1× | — | +14.4%／−30.6%／0.90 | +68.7%／−28.3%／1.96 | +20.4%／−30.6%／1.09 | 210 |
| 對照：不傾斜 1×＋止損 10% | — | +15.6%／−24.4%／1.07 | +61.9%／−15.0%／2.25 | +20.8%／−24.4%／1.27 | 210 |
| ②全期重新優化（Calmar，MDD≤50%，只在 32 個傾斜格裡挑） | 5pp、不設產業上限、63 日、順向、1×、止損 10% | — | +75.1%／−14.9% | +20.2%／−22.2%／1.27 | — |

**F17 怎麼讀**：原最優組在沒調參的 2025 起段 +46.1%、MDD −15.6%，回撤比不傾斜臂淺，但年化輸不傾斜臂（+68.7%）約 23 個百分點、也輸「不傾斜＋同樣止損」（+61.9%）——**跟 2024 底前的結論一樣：改善來自組合止損，不是因子傾斜**，2025 起段傾斜反而拖累（A_4pass 分數低的大型權值股 2025 起漲最多）。沒有任何一組越過天條一。曲線 `research/data/reaudit_curves/ext2025_F17.png`（本機）。

<!-- EXT2025-END -->

<!-- BATCH3-LIST-BEGIN -->
## 4. 第二批清單（先.一五五-3 ①②，`research/reaudit_batch3_inventory.py` 自動產生，零請求、只讀帳本）

TRIALS_LEDGER＋TRIALS_REGISTRY 共 **489** 筆試驗（編號 1～489），自動分成 **263** 族：第一批已涵蓋 52 族；第二批待做 **162** 族；判「非策略，跳過」49 族。

分族與分類規則〔自行裁量，自動、可重跑、可推翻〕：同一個因子名 `f_xxx`／同一支腳本／同一個 HYPOTHESIS_QUEUE 假說編號＝同一族；都抓不到的單列成族。分類：因子→前 N 檔等權月換股；regime／閘門／擇時→0050 曝險；事件→事件後固定持有；描述性／校準／稽核重跑／量尺驗證→非策略跳過。**自動分類有誤判**（例如事件與因子的界線、同機制不同名），每一批開做前人工複核該批 10 族，併族或改分類就改腳本裡的對照表再重跑，不手改本節。

**第 1 批（10 族，下一輪起做）**〔自行裁量：曾 PASS／CHEAP_PASS、可轉成交易規則、本機台股價格＋財報快取接得上 2025 起〕：`f_eps_surprise`、`f_revenue_surprise`、`f_eps_growth`、`f_value_pe`、`f_value_pb`、`f_low_vol`、`f_rel_strength`、`f_52w_high_prox`、`f_dividend_yield_ttm`、`f_gross_profitability`。做法照條目③：全部可得歷史（含 2025 起）掃參數、持有期、止盈止損、槓桿 1×／1.5×／2×／3×，記最好一組併入總表重排。

| 狀態 | 族 | 試驗數 | 編號（前 8） | 轉成什麼規則 | 當時判定 | 代表名稱 |
|---|---|---|---|---|---|---|
| 待做 | fut | 24 | 18,19,20,21,22,23,24,26 | regime→0050 曝險 | FAIL×19、CHEAP_PASS×4、PASS×1 | fut_trend_multi_tf（10/20/60日動能訊號多數決，多時間框架趨勢） |
| 待做 | f_lending_fee_spike | 8 | 225,264,265,266,267,268,269,279 | 事件→事件後固定持有 | CHEAP_PASS×1、PASS×5、FAIL×2 | f_lending_fee_spike（HYPOTHESIS_QUEUE.md#63，第1關chea |
| 待做 | 名稱:stock_grid_tw2007q | 7 | 468,469,470,471,472,473,474 | 待人工判斷 | PASS×1、其他×6 | stock_grid_tw2007q4_2009_prereg |
| 待做 | event_driven_gate_sequence | 6 | 326,332,333,334,335,337 | 事件→事件後固定持有 | PASS×2、CHEAP_PASS×2、FAIL×2 | event_driven_sue_revenue_gate_sequence |
| 待做 | f_us_momentum_12m | 6 | 44,48,53,58,204,207 | 因子→前 N 檔等權月換股 | FAIL×4、CHEAP_PASS×2 | f_us_momentum_12m（12-1動能，US軌第二個因子，新假說） |
| 待做 | stock_grid_oneshot | 6 | 477,478,479,480,481,482 | 待人工判斷 | FAIL×6 | stock_grid_tw2007q4_2009_oneshot_param_penalty_2 |
| **第 1 批** | f_52w_high_prox | 4 | 84,85,86,114 | 事件→事件後固定持有 | CHEAP_PASS×3、PASS×1 | f_52w_high_prox（HYPOTHESIS_QUEUE.md#17「52週高點接近度」Ge |
| **第 1 批** | f_value_pe | 4 | 14,25,166,173 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2、PASS×2 | f_value_pe（負PER，估值因子） |
| 待做 | HQ#390 | 3 | 395,437,438 | regime→0050 曝險 | FAIL×3 | value_board_v2_ir_dsr_cheap_review |
| 待做 | HQ#76 | 3 | 327,357,374 | regime→0050 曝險 | FAIL×1、CHEAP_PASS×2 | #76 VIX9D/VIX期限結構比值 當TAIEX regime降曝險訊號 第1關cheap ga |
| **第 1 批** | f_eps_growth | 3 | 2,109,287 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1、FAIL×1、PASS×1 | f_eps_growth（EPS成長） |
| **第 1 批** | f_eps_surprise | 3 | 7,73,288 | 因子→前 N 檔等權月換股 | PASS×3 | f_eps_surprise（EPS意外，SUE方法論） |
| **第 1 批** | f_low_vol | 3 | 9,82,107 | 因子→前 N 檔等權月換股 | PASS×3 | f_low_vol（低波動） |
| **第 1 批** | f_rel_strength | 3 | 5,77,101 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2、FAIL×1 | f_rel_strength（相對強度） |
| **第 1 批** | f_revenue_surprise | 3 | 8,289,456 | 因子→前 N 檔等權月換股 | PASS×2、FAIL×1 | f_revenue_surprise（營收意外，SUE方法論） |
| 待做 | fx_twd | 3 | 123,363,365 | regime→0050 曝險 | FAIL×3 | fx_twd_gate（HYPOTHESIS_QUEUE.md#32美元兌台幣匯率當資金外流/市場壓 |
| 待做 | option_pcr_overlay | 3 | 122,126,348 | regime→0050 曝險 | CHEAP_PASS×1、PASS×2 | option_pcr_overlay_v1（HYPOTHESIS_QUEUE.md#31接續#121 |
| 待做 | portfolio | 3 | 318,319,367 | regime→0050 曝險 | FAIL×3 | portfolio_multifactor_v2 p=0.053不可重現的根因調查（財報PIT.四後 |
| 待做 | us_8k_pead_gate52 | 3 | 215,216,220 | 事件→事件後固定持有 | FAIL×3 | #52-US SEC EDGAR 8-K Item 2.02 事件反應速度（PEAD）cheap g |
| 待做 | HQ#29 | 2 | 202,462 | regime→0050 曝險 | PASS×2 | #58 反向波動度加權投資組合建構 GATE_SEQUENCE第2關 隨機控制組 |
| 待做 | HQ#405 | 2 | 406,408 | regime→0050 曝險 | PASS×2 | supply_tightness_satellite_v1_result |
| 待做 | HQ#65 | 2 | 66,229 | 因子→前 N 檔等權月換股 | PASS×1、FAIL×1 | fut_night_gap_continuation（日盤收盤(T-1)→夜盤開盤(T)跳空，順勢交 |
| 待做 | capital_reduction_car | 2 | 262,263 | 事件→事件後固定持有 | FAIL×2 | 減資事件CAR·現金減資組(#71) |
| 待做 | copper_gold_ratio | 2 | 125,364 | regime→0050 曝險 | CHEAP_PASS×1、FAIL×1 | 銅金比 Copper/Gold Ratio 當全球成長/風險偏好regime訊號（HYPOTHESI |
| 待做 | dividend_yield | 2 | 371,376 | regime→0050 曝險 | FAIL×2 | dividend_yield_portfolio_v1_engine_fix_recheck |
| 待做 | etf_rebalance_event_study | 2 | 457,458 | 事件→事件後固定持有 | 其他×1、FAIL×1 | etf_rebalance_high_dividend_event_2022_2024_prereg |
| 待做 | exit_rule_lab | 2 | 359,360 | regime→0050 曝險 | PASS×2 | exit_rule_regime_gate_E-c_trailing10 |
| 待做 | f_bab | 2 | 61,78 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2 | f_bab（betting-against-beta, Frazzini&Pedersen 2014 |
| **第 1 批** | f_dividend_yield_ttm | 2 | 74,75 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2 | f_dividend_yield_ttm（HYPOTHESIS_QUEUE.md#4「股票股利率ca |
| 待做 | f_inst_flow | 2 | 4,12 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1、FAIL×1 | f_inst_flow（三大法人淨買/流動性） |
| 待做 | f_margin_utilization | 2 | 116,117 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2 | f_margin_utilization個股融資使用率（HYPOTHESIS_QUEUE.md #3 |
| 待做 | f_us_gross_profitability | 2 | 191,193 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2 | f_us_gross_profitability（Novy-Marx GrossProfit/Ass |
| **第 1 批** | f_value_pb | 2 | 13,42 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1、PASS×1 | f_value_pb（負PBR，估值因子） |
| 待做 | factor_ic | 2 | 155,157 | 因子→前 N 檔等權月換股 | FAIL×2 | 內部人（董監事/大股東/經理人）持股轉讓（HYPOTHESIS_QUEUE.md #41，infor |
| 待做 | forced_short_covering_gate1 | 2 | 186,189 | 事件→事件後固定持有 | FAIL×2 | HYPOTHESIS_QUEUE.md #51子事件1（融券強制回補）事件條件式短天期IC 第1關c |
| 待做 | fut_recheck_inst_momentum_highres | 2 | 30,31 | 因子→前 N 檔等權月換股 | 其他×1、PASS×1 | fut_inst_foreign_net_position_change_5d（外資期貨淨部位5日變 |
| 待做 | fut_settlement_event_gate60 | 2 | 213,214 | 待人工判斷 | FAIL×2 | fut_settlement_event_gate60_pre |
| 待做 | min_variance_portfolio_gate59_costs | 2 | 212,276 | 事件→事件後固定持有 | PASS×1、FAIL×1 | #59 最小變異數投資組合建構 GATE4 成本敏感度 |
| 待做 | spillover_overlay_v1_o2c | 2 | 386,394 | 因子→前 N 檔等權月換股 | CHEAP_PASS×2 | spillover_overnight_gate_o2c |
| 待做 | spillover_overnight | 2 | 88,121 | regime→0050 曝險 | CHEAP_PASS×2 | spillover_overnight_gate.py（HYPOTHESIS_QUEUE.md#19 |
| 待做 | us_8k_item502_gate52 | 2 | 217,218 | 事件→事件後固定持有 | FAIL×2 | #52-US SEC EDGAR 8-K Item 5.02 事件反應速度（管理層異動）cheap  |
| 待做 | var1018_v2_turn_of_month | 2 | 447,450 | 因子→前 N 檔等權月換股 | 其他×1、PASS×1 | var1018_v2_turn_of_month_spx_taiex1990_prereg |
| 待做 | var1018_v4_short_margin_reversed | 2 | 448,451 | 因子→前 N 檔等權月換股 | 其他×2 | var1018_v4_short_margin_reversed_tw2007_prereg |
| 待做 | var1018_v5_january_reversal | 2 | 449,452 | 因子→前 N 檔等權月換股 | 其他×1、FAIL×1 | var1018_v5_january_reversal_tw_prereg |
| 待做 | var1018_v7_us_unemployment | 2 | 453,454 | regime→0050 曝險 | 其他×1、VIOLATES_SURVIVAL×1 | var1018_v7_us_unemployment_spx_prereg |
| 待做 | vrp | 2 | 127,443 | 事件→事件後固定持有 | FAIL×1、PASS×1 | 賣出台指選擇權波動度風險溢酬 VRP（HYPOTHESIS_QUEUE.md#35，第1關cheap |
| 待做 | HQ#116 | 1 | 120 | regime→0050 曝險 | FAIL×1 | margin_utilization_regime_portfolio_v1（HYPOTHESIS_ |
| 待做 | HQ#186 | 1 | 187 | 事件→事件後固定持有 | FAIL×1 | HYPOTHESIS_QUEUE.md #51子事件2（現金增資折價）事件條件式CAR第1關chea |
| 待做 | HQ#20 | 1 | 188 | regime→0050 曝險 | 其他×1 | round418下一步：查證FinMind以外免費來源能否取得#20/#21常駐短腿ticker真實 |
| 待做 | HQ#225 | 1 | 227 | regime→0050 曝險 | PASS×1 | #63 gate4成本敏感度 |
| 待做 | HQ#27 | 1 | 160 | 因子→前 N 檔等權月換股 | FAIL×1 | fut_daily_continuation_1d（同#159反方向，順勢交易前一日報酬方向，同一輪 |
| 待做 | HQ#31 | 1 | 241 | regime→0050 曝險 | FAIL×1 | option_skew_cheap_gate #70 |
| 待做 | HQ#32 | 1 | 33 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | fut_intraday_gap_continuation（隔夜跳空後日內順勢：gap up做多、g |
| 待做 | HQ#324 | 1 | 372 | 事件→事件後固定持有 | PASS×1 | insider_event_level_shortwindow |
| 待做 | HQ#368 | 1 | 369 | regime→0050 曝險 | CHEAP_PASS×1 | monthly_revenue_sue_continuous_bucket_v1_volcheck |
| 待做 | HQ#379 | 1 | 385 | regime→0050 曝險 | FAIL×1 | f52w_high_portfolio_v1_information_ratio_review_fi |
| 待做 | HQ#396 | 1 | 398 | regime→0050 曝險 | PASS×1 | f52w_high_portfolio_v1_2007_2014_single_shot |
| 待做 | HQ#397 | 1 | 399 | 事件→事件後固定持有 | PASS×1 | dividend_yield_portfolio_v1_2007_2014_single_shot |
| 待做 | HQ#406 | 1 | 407 | regime→0050 曝險 | 其他×1 | supply_tightness_v2_forward_prereg |
| 待做 | HQ#408 | 1 | 409 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | industry_shortage_v1_result |
| 待做 | HQ#424 | 1 | 427 | regime→0050 曝險 | 其他×1 | s3c6_oos_2025_prereg |
| 待做 | HQ#431 | 1 | 433 | 事件→事件後固定持有 | FAIL×1 | b20_qualitative_ai_forward_v1 |
| 待做 | HQ#435 | 1 | 436 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | r1s3_gate_killtest_1990_2003_result |
| 待做 | HQ#436 | 1 | 439 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | volmanaged_leverage_1990_2003_prereg |
| 待做 | HQ#439 | 1 | 440 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | volmanaged_leverage_1990_2003_result |
| 待做 | HQ#44 | 1 | 164 | 待人工判斷 | FAIL×1 | 景氣對策信號NDC Business Cycle Composite Signal（HYPOTHES |
| 待做 | HQ#47 | 1 | 176 | 事件→事件後固定持有 | FAIL×1 | 處置股解除後價格反轉 Post-Disposition-Stock Price Reversion（ |
| 待做 | HQ#49 | 1 | 441 | regime→0050 曝險 | 其他×1 | overnight_intraday_1999_2009_prereg |
| 待做 | HQ#51 | 1 | 190 | 事件→事件後固定持有 | FAIL×1 | cb_conversion_price_reset_gate1 |
| 待做 | HQ#52 | 1 | 223 | 事件→事件後固定持有 | CHEAP_PASS×1 | material_news_car_gate2_continuation |
| 待做 | HQ#55 | 1 | 56 | regime→0050 曝險 | FAIL×1 | fut_night_session_reversal（夜盤自身open→close報酬方向取反，反向 |
| 待做 | HQ#58 | 1 | 210 | 待人工判斷 | PASS×1 | #59 最小變異數投資組合建構 GATE2隨機控制組 |
| 待做 | HQ#61 | 1 | 219 | 事件→事件後固定持有 | FAIL×1 | cbc_decision_event_gate61_subtest1 |
| 待做 | HQ#63 | 1 | 278 | 因子→前 N 檔等權月換股 | FAIL×1 | #63借券費率異常飆升 第4關安全邊際重新錨定(取代1x/2x/3x) |
| 待做 | HQ#66 | 1 | 230 | 待人工判斷 | CHEAP_PASS×1 | us_tax_loss_selling_gate66 |
| 待做 | HQ#69 | 1 | 239 | regime→0050 曝險 | FAIL×1 | option_oi_pcr_gate69 |
| 待做 | HQ#70 | 1 | 71 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | fut_day_gap_continuation（夜盤收盤(T)→日盤開盤(T)跳空，順勢交易同一d |
| 待做 | HQ#75 | 1 | 324 | 因子→前 N 檔等權月換股 | FAIL×1 | #75 2018+子樣本 第1關cheap IC gate (net_usd/n_buyers vs |
| 待做 | HQ#78 | 1 | 366 | regime→0050 曝險 | FAIL×1 | PENDING_QUEUE.md 常備.5 HYG/IEF比值水位版其他窗口(M=5/10/60日) |
| 待做 | HQ#80 | 1 | 345 | 待人工判斷 | FAIL×1 | dgbas_unemployment_yoy_gate1 |
| 待做 | adr_premium_assembly | 1 | 168 | 事件→事件後固定持有 | CHEAP_PASS×1 | 存託憑證（ADR）溢價/折價收斂第1關cheap gate（HYPOTHESIS_QUEUE.md  |
| 待做 | adr_premium_gate_ex_tsm | 1 | 169 | 事件→事件後固定持有 | CHEAP_PASS×1 | 存託憑證（ADR）溢價/折價收斂——排除TSM對照重跑最終判定（HYPOTHESIS_QUEUE.m |
| 待做 | atom_ic_map | 1 | 286 | regime→0050 曝險 | FAIL×1 | 原子.二 分年份/分牛熊段穩定度拆解——最終判定 |
| 待做 | avg_pairwise_correlation | 1 | 161 | regime→0050 曝險 | FAIL×1 | 三大法人買賣超集中度 Institutional Buying Concentration（HYPO |
| 待做 | build_signal_ledger | 1 | 432 | 事件→事件後固定持有 | FAIL×1 | b19_signal_ledger_forward_v1 |
| 待做 | buyback_car | 1 | 150 | 事件→事件後固定持有 | FAIL×1 | 庫藏股買回公告效應（HYPOTHESIS_QUEUE.md #40，管理層信心信號事件研究，上一輪完 |
| 待做 | cbi_signal | 1 | 361 | regime→0050 曝險 | CHEAP_PASS×1 | 景氣對策信號綜合分數當TAIEX regime降曝險訊號（HYPOTHESIS_QUEUE.md # |
| 待做 | cybex_engine_on53 | 1 | 242 | regime→0050 曝險 | FAIL×1 | Cybex.引擎：進場/出場延遲確認+總開關重開冷卻期 套用於#53全市場報酬離散度速度 |
| 待做 | deep_dive_fut_basis_mean_reversion_60d | 1 | 43 | regime→0050 曝險 | PASS×1 | fut_basis_mean_reversion_60d（#38的深挖/1b，非新假說） |
| 待做 | deep_dive_loo_no_low_vol_independent_sample | 1 | 131 | 事件→事件後固定持有 | FAIL×1 | portfolio_multifactor_v2 loo_no_low_vol（eps_family |
| 待做 | dgbas_unemployment | 1 | 362 | regime→0050 曝險 | FAIL×1 | 台灣失業率YoY當TAIEX regime降曝險訊號（HYPOTHESIS_QUEUE.md #80 |
| 待做 | equal_weight_rebalance_costs | 1 | 111 | 事件→事件後固定持有 | PASS×1 | equal_weight_rebalance_costs_v1（HYPOTHESIS_QUEUE.m |
| 待做 | equal_weight_rebalance_leave_one_out | 1 | 112 | regime→0050 曝險 | PASS×1 | equal_weight_rebalance_leave_one_out_v1（HYPOTHESIS |
| 待做 | event_driven_prototype | 1 | 325 | 事件→事件後固定持有 | PASS×1 | event_driven_sue_earnings_gate_sequence |
| 待做 | f_accruals | 1 | 63 | 因子→前 N 檔等權月換股 | FAIL×1 | f_accruals（盈餘品質應計項目，Sloan 1996資產負債表法，「品質」家族accrual |
| 待做 | f_amihud_illiq | 1 | 50 | 因子→前 N 檔等權月換股 | FAIL×1 | f_amihud_illiq（Amihud 2002流動性因子，20日\ |
| 待做 | f_asset_growth | 1 | 62 | 因子→前 N 檔等權月換股 | FAIL×1 | f_asset_growth（資產成長異常，Cooper/Gulen/Schill 2008，Tot |
| 待做 | f_eps_surprise_revalidation_v7 | 1 | 403 | 因子→前 N 檔等權月換股 | FAIL×1 | f_eps_surprise_revalidation_v7 |
| 待做 | f_eps_surprise_revalidation_v7_prereg | 1 | 401 | 因子→前 N 檔等權月換股 | PASS×1 | f_eps_surprise_revalidation_v7_prereg |
| 待做 | f_foreign_streak | 1 | 3 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_foreign_streak（外資連續買超強度） |
| 待做 | f_gross_margin_stability | 1 | 67 | 因子→前 N 檔等權月換股 | FAIL×1 | f_gross_margin_stability（毛利率穩定度，Novy-Marx精神品質異常變體： |
| **第 1 批** | f_gross_profitability | 1 | 90 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_gross_profitability（HYPOTHESIS_QUEUE.md#20「純毛利率因 |
| 待做 | f_idio_vol | 1 | 51 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_idio_vol（特異波動率，Ang et al. 2006異常，60日市場模型變異數分解取負號 |
| 待做 | f_listing_age_days | 1 | 175 | 因子→前 N 檔等權月換股 | FAIL×1 | 新股上市長期弱勢 IPO Long-Run Underperformance（HYPOTHESIS_ |
| 待做 | f_ma_breakout | 1 | 6 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_ma_breakout（站上季線+量能） |
| 待做 | f_rel_strength_regime_switch | 1 | 40 | 因子→前 N 檔等權月換股 | FAIL×1 | f_rel_strength_regime_switch（大盤位階開關+相對強度十分位多空，regi |
| 待做 | f_residual_momentum | 1 | 76 | 因子→前 N 檔等權月換股 | FAIL×1 | f_residual_momentum（HYPOTHESIS_QUEUE.md#9「殘差動量Resi |
| 待做 | f_revenue_surprise_revalidation_v7 | 1 | 404 | 因子→前 N 檔等權月換股 | FAIL×1 | f_revenue_surprise_revalidation_v7 |
| 待做 | f_revenue_surprise_revalidation_v7_prereg | 1 | 402 | 因子→前 N 檔等權月換股 | PASS×1 | f_revenue_surprise_revalidation_v7_prereg |
| 待做 | f_short_margin_ratio | 1 | 233 | 因子→前 N 檔等權月換股 | PASS×1 | short_margin_ratio_gate68 第1關cheap IC gate（HYPOTHE |
| 待做 | f_short_reversal_1m | 1 | 46 | 因子→前 N 檔等權月換股 | FAIL×1 | f_short_reversal_1m（短期反轉，21交易日自身累積報酬取負號，新假說） |
| 待做 | f_short_term_reversal_1w | 1 | 87 | 因子→前 N 檔等權月換股 | FAIL×1 | f_short_term_reversal_1w（HYPOTHESIS_QUEUE.md#18「短期 |
| 待做 | fetch_news_events | 1 | 284 | 事件→事件後固定持有 | FAIL×1 | #72 重大訂單/得標公告效應 |
| 待做 | finmind_client | 1 | 400 | 事件→事件後固定持有 | PASS×1 | dividend_yield_v1_common_x_account_70_30_prereg |
| 待做 | fred_yield_curve | 1 | 124 | regime→0050 曝險 | FAIL×1 | fred_yield_curve_gate（HYPOTHESIS_QUEUE.md#33美國公債殖利 |
| 待做 | fut_recheck_intraday_gap_continuation_highres | 1 | 34 | 因子→前 N 檔等權月換股 | FAIL×1 | fut_intraday_gap_continuation（隔夜跳空後日內順勢，高解析度重測，非新假 |
| 待做 | holding_shares_per | 1 | 148 | regime→0050 曝險 | FAIL×1 | 大戶籌碼集中度/股東持股分級表（HYPOTHESIS_QUEUE.md #38，資料可行性查證） |
| 待做 | hy_etf_ratio | 1 | 330 | regime→0050 曝險 | PASS×1 | HYPOTHESIS_QUEUE.md #78 HYG/IEF比值代理信用利差當TAIEX regi |
| 待做 | irb130_pledge | 1 | 178 | regime→0050 曝險 | PASS×1 | 董監事及大股東股權質押比例 Controlling Shareholder / Insider Sh |
| 待做 | leave_one_factor_out_bigsample | 1 | 118 | 事件→事件後固定持有 | PASS×1 | portfolio_multifactor_v2 leave-one-factor-out重跑（tr |
| 待做 | lending_fee_gate63_param_plateau | 1 | 226 | 待人工判斷 | CHEAP_PASS×1 | #63 借券費率異常飆升 gate2 參數高原檢定(Z_THRESH) |
| 待做 | material_news_car | 1 | 221 | 事件→事件後固定持有 | CHEAP_PASS×1 | HYPOTHESIS_QUEUE.md #52事件反應速度 正式N=200全量CAR事件研究gate |
| 待做 | min_variance_portfolio_gate59 | 1 | 211 | 待人工判斷 | PASS×1 | #59 最小變異數投資組合建構 GATE_SEQUENCE第3關 參數密集高原 |
| 待做 | monthly_revenue_event_study | 1 | 368 | 事件→事件後固定持有 | CHEAP_PASS×1 | monthly_revenue_sue_continuous_bucket_v1 |
| 待做 | option_pcr | 1 | 146 | regime→0050 曝險 | FAIL×1 | 全市場現股當沖比重（HYPOTHESIS_QUEUE.md #37，市場過熱regime訊號，hyp |
| 待做 | overnight_1999_2009 | 1 | 442 | 待人工判斷 | FAIL×1 | overnight_intraday_1999_2009_result |
| 待做 | overnight_intraday_alt_cutpoint_placebo | 1 | 182 | 待人工判斷 | CHEAP_PASS×1 | 日內／隔夜報酬結構分解（HYPOTHESIS_QUEUE.md #49，接續round180第1關C |
| 待做 | overnight_intraday_gate6_consistency | 1 | 184 | 待人工判斷 | CHEAP_PASS×1 | 日內／隔夜報酬結構分解（HYPOTHESIS_QUEUE.md #49，第6關逐年一致性檢驗，依上一 |
| 待做 | paper_10_disposition | 1 | 464 | 事件→事件後固定持有 | 其他×1 | paper_j_disposition_release_rebound_forward_prereg |
| 待做 | paper_11_tdcc_bigholder | 1 | 465 | regime→0050 曝險 | 其他×1 | paper_k_tdcc_bigholder_4w_forward_prereg |
| 待做 | paper_12_warrant_wave | 1 | 466 | regime→0050 曝險 | 其他×1 | paper_l_warrant_issuance_wave_forward_prereg |
| 待做 | paper_13_ml_low_beta | 1 | 484 | regime→0050 曝險 | 其他×1 | paper_m_ml_low_beta_forward_prereg |
| 待做 | paper_14_grid_range | 1 | 485 | regime→0050 曝險 | FAIL×1 | paper_n_stock_grid_range_forward_prereg |
| 待做 | paper_15_ml_industry | 1 | 486 | regime→0050 曝險 | 其他×1 | paper_o_ml_industry_rotation_forward_prereg |
| 待做 | paper_16_order_win | 1 | 487 | 事件→事件後固定持有 | 其他×1 | paper_p_order_win_drift_forward_prereg |
| 待做 | paper_17_margin_liquidation | 1 | 488 | 事件→事件後固定持有 | 其他×1 | paper_q_margin_liquidation_rebound_forward_prereg |
| 待做 | paper_18_sbl_covering | 1 | 489 | 事件→事件後固定持有 | 其他×1 | paper_r_sbl_covering_drift_forward_prereg |
| 待做 | paper_6_vrp_wing | 1 | 455 | regime→0050 曝險 | 其他×1 | paper_f_wing_iron_butterfly_forward_prereg |
| 待做 | paper_8_ml | 1 | 459 | regime→0050 曝險 | 其他×1 | paper_h_ml_stock_forward_prereg |
| 待做 | paper_9_breakout | 1 | 463 | regime→0050 曝險 | 其他×1 | paper_i_breakout252h_volume_forward_prereg |
| 待做 | pead | 1 | 373 | 事件→事件後固定持有 | FAIL×1 | pead_portfolio_v1_engine_fix_recheck |
| 待做 | run_score | 1 | 375 | regime→0050 曝險 | PASS×1 | score_topn_v1_engine_fix_recheck |
| 待做 | sp500_addition_runup_gate51us | 1 | 222 | 事件→事件後固定持有 | CHEAP_PASS×1 | sp500_addition_runup_gate51us |
| 待做 | stock_futures_basis | 1 | 461 | regime→0050 曝險 | FAIL×1 | stock_futures_basis_oneshot |
| 待做 | stock_futures_basis_oneshot | 1 | 460 | 事件→事件後固定持有 | 其他×1 | stock_futures_basis_oneshot_prereg |
| 待做 | stock_grid_limit7_diag | 1 | 476 | regime→0050 曝險 | FAIL×1 | stock_grid_tw2007q4_2009_oneshot |
| 待做 | txo_vrp_2002_2014 | 1 | 444 | 待人工判斷 | PASS×1 | txo_vrp_2002_2014_result |
| 待做 | us_portfolio_multifactor | 1 | 209 | 因子→前 N 檔等權月換股 | FAIL×1 | us_portfolio_gross_profitability_v1（正式N=100版，單因子To |
| 待做 | var1018_v1_oneshot | 1 | 467 | 事件→事件後固定持有 | VIOLATES_SURVIVAL×1 | var1018_v1_equal_weight_rebalance_tw2007h2_oneshot |
| 待做 | 名稱: | 1 | 113 | 因子→前 N 檔等權月換股 | FAIL×1 | portfolio_multifactor_v2 leave-one-factor-out（回答ro |
| 待做 | 名稱:concentrated_backt | 1 | 358 | regime→0050 曝險 | FAIL×1 | concentrated_backtest_framework_check |
| 待做 | 名稱:core_allocation_24 | 1 | 417 | regime→0050 曝險 | FAIL×1 | core_allocation_24grid_prereg |
| 待做 | 名稱:event_driven_sue_e | 1 | 336 | 事件→事件後固定持有 | PASS×1 | event_driven_sue_earnings_e1_rejudge_c_right_tail |
| 待做 | 名稱:fut_cta_multi_tf_v | 1 | 238 | regime→0050 曝險 | FAIL×1 | fut_cta_multi_tf_voltarget |
| 待做 | 名稱:fut_donchian_full_ | 1 | 235 | regime→0050 曝險 | FAIL×1 | fut_donchian_full_55_20 |
| 待做 | 名稱:fut_keltner_breako | 1 | 236 | regime→0050 曝險 | FAIL×1 | fut_keltner_breakout_20_2atr |
| 待做 | 名稱:fut_turtle_system1 | 1 | 234 | regime→0050 曝險 | FAIL×1 | fut_turtle_system1_20_10 |
| 待做 | 名稱:fut_vol_breakout_0 | 1 | 237 | regime→0050 曝險 | FAIL×1 | fut_vol_breakout_0p5atr |
| 待做 | 名稱:passive_benchmark_ | 1 | 240 | regime→0050 曝險 | 其他×1 | passive_benchmark_tw_v1（0050固定小倉位被動基準，深讀二.1） |
| 待做 | 名稱:regime擇時overlay候選5 | 1 | 246 | 事件→事件後固定持有 | FAIL×1 | regime擇時overlay候選5：TAIEX回撤斷路器(自身淨值回撤>=15%降曝險至0.50, |
| 待做 | 名稱:supply_tightness_s | 1 | 405 | regime→0050 曝險 | PASS×1 | supply_tightness_satellite_v1_prereg |
| 待做 | 名稱:us_supply_tightnes | 1 | 410 | 因子→前 N 檔等權月換股 | FAIL×1 | us_supply_tightness_data_unavailable |
| 跳過 | pit3_rerun_v2_corrected | 12 | 292,293,294,295,296,297,298,299 | 非策略，跳過 | FAIL×12 | portfolio_multifactor_v2 A_4pass PIT修正重跑：equal/mon |
| 跳過 | pit4_rerun_80name | 12 | 304,305,306,307,308,309,310,311 | 非策略，跳過 | FAIL×12 | portfolio_multifactor_v2 80檔PIT修正重跑：A_4pass/equal/ |
| 跳過 | HQ#338 | 7 | 350,351,352,353,354,355,356 | 非策略，跳過 | 其他×7 | exit_rule_lab_E-a_buy_and_hold |
| 跳過 | f_us_reversal_1m | 6 | 45,49,54,59,205,208 | 非策略，跳過 | PASS×1、CHEAP_PASS×3、FAIL×2 | f_us_reversal_1m（短期反轉，近1個月累積報酬取負號，US軌第三個因子，新假說） |
| 跳過 | control_group_standard | 4 | 192,194,224,228 | 非策略，跳過 | PASS×1、FAIL×2、CHEAP_PASS×1 | #53全市場報酬離散度速度(Cross-Sectional Return Dispersion Ve |
| 跳過 | f52w_high | 4 | 370,377,396,397 | 非策略，跳過 | PASS×3、其他×1 | f52w_high_portfolio_v1_engine_fix_recheck |
| 跳過 | f_inst_streak_days | 4 | 79,100,140,153 | 非策略，跳過 | FAIL×3、CHEAP_PASS×1 | f_inst_streak_days（HYPOTHESIS_QUEUE.md#13「台股三大法人連續 |
| 跳過 | piotroski_fscore | 3 | 94,291,391 | 非策略，跳過 | FAIL×3 | piotroski_fscore_gate_v1（HYPOTHESIS_QUEUE.md#23「Pi |
| 跳過 | 名稱:exit_rule_lab_E-b_ | 3 | 339,340,341 | 非策略，跳過 | 其他×3 | exit_rule_lab_E-b_stop8 |
| 跳過 | HQ#285 | 2 | 316,317 | 非策略，跳過 | FAIL×2 | 原子.五 財報depth-1素材IC地圖——族層級最終判定 |
| 跳過 | chip_atom_ic_map | 2 | 328,331 | 非策略，跳過 | FAIL×2 | 原子.六 籌碼depth-1原子IC地圖 Tier A（併入上櫃三大法人重測）——規格第7節判定 |
| 跳過 | piotroski_fscore_sanity | 2 | 93,290 | 非策略，跳過 | PASS×2 | #23 Piotroski F-score當價值榜排雷閘門 |
| 跳過 | vol_targeting | 2 | 81,105 | 非策略，跳過 | FAIL×1、PASS×1 | vol_targeting_v1（HYPOTHESIS_QUEUE.md#15「波動度目標化部位配置 |
| 跳過 | 名稱:exit_rule_lab_E-c_ | 2 | 342,343 | 非策略，跳過 | 其他×2 | exit_rule_lab_E-c_trailing10 |
| 跳過 | HQ#316 | 1 | 320 | 非策略，跳過 | FAIL×1 | 原子.五B 財報通道B(結構型算子)IC地圖——族層級最終判定 |
| 跳過 | HQ#367 | 1 | 380 | 非策略，跳過 | FAIL×1 | portfolio_v2_pead_new_scale_recheck |
| 跳過 | HQ#375 | 1 | 381 | 非策略，跳過 | 其他×1 | run_score_backtest_new_scale_recheck |
| 跳過 | HQ#77 | 1 | 106 | 非策略，跳過 | CHEAP_PASS×1 | revenue_trend_surprise_low_attention（HYPOTHESIS_QU |
| 跳過 | HQ#98 | 1 | 99 | 非策略，跳過 | FAIL×1 | 查證CALIBRATION_PROBE.md結論(乙)「#34同理各自重跑」對FUT軌是否可行（非新 |
| 跳過 | audit_f52w_dsr | 1 | 379 | 非策略，跳過 | PASS×1 | f52w_high_portfolio_v1_dsr_bonferroni_final |
| 跳過 | b18_8k_commercial | 1 | 431 | 非策略，跳過 | PASS×1 | b18_8k_commercial_item101_drift_v1 |
| 跳過 | b30_customer_concentration | 1 | 434 | 非策略，跳過 | PASS×1 | b30_us_customer_concentration_v1 |
| 跳過 | breadth_divergence_sanity | 1 | 103 | 非策略，跳過 | PASS×1 | #28 市場廣度背離Breadth Divergence（TAIEX 20日動量為正但300檔樣本b |
| 跳過 | calibration_probe_momentum_12_1 | 1 | 98 | 非策略，跳過 | PASS×1 | calibration_probe_momentum_12_1（管線校準探針：橫截面12-1動能當已 |
| 跳過 | chip_atom_slb_ic_map | 1 | 321 | 非策略，跳過 | FAIL×1 | 原子.六 出借總量(TWSE TWT72U)depth-1 IC地圖（14表達式×2horizon= |
| 跳過 | composite_quality_revaccel_inst_lowvol_sanity | 1 | 92 | 非策略，跳過 | FAIL×1 | #22 品質×營收加速×法人吸籌×低波動複合訊號（合取AND） |
| 跳過 | composite_zscore_v1_random_control | 1 | 102 | 非策略，跳過 | CHEAP_PASS×1 | #27 多因子複合評分z-score blend baseline（GP+value_pb+reve |
| 跳過 | copper_gold_ratio_overlay | 1 | 347 | 非策略，跳過 | PASS×1 | copper_gold_ratio_overlay_v1_etf_tax_recheck |
| 跳過 | cta_momentum_12m | 1 | 72 | 非策略，跳過 | PASS×1 | fut_cta_momentum_12m（HYPOTHESIS_QUEUE.md#2「CTA趨勢跟隨 |
| 跳過 | day_trading_ratio_dispersion_gate57 | 1 | 201 | 非策略，跳過 | PASS×1 | day_trading_ratio_dispersion_gate57_control |
| 跳過 | equal_weight_rebalance_control | 1 | 108 | 非策略，跳過 | CHEAP_PASS×1 | equal_weight_rebalance_control_v1（HYPOTHESIS_QUEUE |
| 跳過 | equal_weight_rebalance_plateau | 1 | 110 | 非策略，跳過 | PASS×1 | equal_weight_rebalance_plateau_v1（HYPOTHESIS_QUEUE |
| 跳過 | ex_dividend_seasonal_sanity | 1 | 95 | 非策略，跳過 | PASS×1 | #24 除權息季節行為效應（台股7-9月旺季填息/棄息行為，稅制驅動） |
| 跳過 | f52w_high_gates | 1 | 378 | 非策略，跳過 | PASS×1 | f52w_high_gates_356_engine_fix_recheck |
| 跳過 | factors | 1 | 323 | 非策略，跳過 | PASS×1 | 事件驅動原型(方法.三)：E1財報公布(SUE)/E2月營收公布(SUE)分組依事件當下意外程度 |
| 跳過 | institutional_flow_dispersion_gate55 | 1 | 198 | 非策略，跳過 | PASS×1 | #55 三大法人買賣超截面離散度速度 Institutional Flow Dispersion V |
| 跳過 | lending_fee_gate63_costs | 1 | 277 | 非策略，跳過 | FAIL×1 | #63借券費率異常飆升 第4關成本敏感度 成本.二重跑(1.8折) |
| 跳過 | margin_debt_growth | 1 | 97 | 非策略，跳過 | FAIL×1 | #26 全市場融資餘額成長率 Margin Debt Growth（TWSE官方全市場歷史數字，槓桿 |
| 跳過 | overnight_intraday_decomposition | 1 | 180 | 非策略，跳過 | CHEAP_PASS×1 | 日內／隔夜報酬結構分解 Overnight vs Intraday Return Decomposi |
| 跳過 | revenue_trend_surprise_low_attention | 1 | 91 | 非策略，跳過 | FAIL×1 | revenue_trend_surprise_low_attention（HYPOTHESIS_QU |
| 跳過 | run_value_board_v2_pit | 1 | 390 | 非策略，跳過 | PASS×1 | value_board_v2_pit_backtest_liquidity500_engine_fi |
| 跳過 | spillover_overlay | 1 | 346 | 非策略，跳過 | PASS×1 | spillover_overlay_v1_etf_tax_recheck |
| 跳過 | tail | 1 | 322 | 非策略，跳過 | 其他×1 | tail_test.py 自我校準（PEAD財報公布後3日累積報酬前10%個股 vs 同時間窗/同產 |
| 跳過 | turn_of_month | 1 | 96 | 非策略，跳過 | FAIL×1 | #25 月轉效應Turn-of-Month Effect（TAIEX指數層級，非選股） |
| 跳過 | turnover_concentration_gate54 | 1 | 195 | 非策略，跳過 | PASS×1 | #54 成交值集中度速度（Turnover Concentration Velocity）第1關sa |
| 跳過 | universe | 1 | 83 | 非策略，跳過 | FAIL×1 | pair_trading_v1（HYPOTHESIS_QUEUE.md#16「同產業配對交易/統計套 |
| 跳過 | 名稱:exit_rule_lab_E-a_ | 1 | 338 | 非策略，跳過 | 其他×1 | exit_rule_lab_E-a_buy_and_hold |
| 跳過 | 名稱:exit_rule_lab_E-d_ | 1 | 344 | 非策略，跳過 | 其他×1 | exit_rule_lab_E-d_ma200_regime |
| 跳過 | 名稱:原子.二 depth-1原子表達式I | 1 | 285 | 非策略，跳過 | 其他×1 | 原子.二 depth-1原子表達式IC地圖（描述性掃描） |
| 第一批已做 | f_us_low_vol | 20 | 39,41,47,52,57,64,68,104 | 因子→前 N 檔等權月換股 | CHEAP_PASS×12、PASS×3、其他×3、FAIL×2 | f_us_low_vol（60日日報酬std取負號，跟TW版f_low_vol定義/窗口對齊） |
| 第一批已做 | f_us_value_bm | 16 | 119,128,139,144,163,165,167,170 | 因子→前 N 檔等權月換股 | CHEAP_PASS×3、FAIL×5、PASS×4、其他×4 | f_us_value_bm（book-to-market，US軌第一個基本面/PIT因子，非pric |
| 第一批已做 | f_quality_roe_stability | 6 | 15,16,17,69,156,158 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1、PASS×4、其他×1 | f_quality_roe_stability（ROE季度變異度穩定性） |
| 第一批已做 | 名稱:regime.替代A 網格 MA=2 | 6 | 256,257,258,259,260,261 | regime→0050 曝險 | FAIL×5、PASS×1 | regime.替代A 網格 MA=200 k=0.35 |
| 第一批已做 | HQ#421 | 3 | 424,429,435 | regime→0050 曝險 | 其他×2、PASS×1 | crisis_gate_leveraged_bb90_prereg |
| 第一批已做 | regime_overlay_trend_filter_gate_fut | 3 | 250,251,252 | regime→0050 曝險 | PASS×3 | regime擇時overlay事前網格：TX連續合約200MA趨勢濾網 bear_exposure= |
| 第一批已做 | 名稱:regime.替代A 網格 MA=1 | 3 | 253,254,255 | regime→0050 曝險 | FAIL×3 | regime.替代A 網格 MA=140 k=0.35 |
| 第一批已做 | HQ#11 | 2 | 10,80 | 因子→前 N 檔等權月換股 | FAIL×1、PASS×1 | weinstein_stage2_pilot_v1（手選30檔試點） |
| 第一批已做 | HQ#418 | 2 | 419,423 | regime→0050 曝險 | 其他×2 | leveraged_bb90_6grid_prereg |
| 第一批已做 | core_tilt | 2 | 280,281 | regime→0050 曝險 | FAIL×2 | core_tilt SPEC TE可行性驗證(反推所需TE vs 實測市值加權+主動權重帶構造TE) |
| 第一批已做 | deep_dive_fut_basis_carry | 2 | 37,244 | 事件→事件後固定持有 | CHEAP_PASS×1、PASS×1 | fut_basis_carry（#35的深挖/1b，非新假說——對已通過便宜關卡的候選做完整驗證） |
| 第一批已做 | f_rev_accel | 2 | 1,11 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1、FAIL×1 | f_rev_accel（月營收YoY加速度） |
| 第一批已做 | leveraged_bb90 | 2 | 420,422 | regime→0050 曝險 | PASS×1、FAIL×1 | leveraged_bb90_6grid_result |
| 第一批已做 | margin_debt_level_circular_shift_control | 2 | 143,147 | regime→0050 曝險 | PASS×1、CHEAP_PASS×1 | margin_debt_level_v1第2關深挖：circular-shift自相關保留版隨機控制 |
| 第一批已做 | regime_overlay | 2 | 89,136 | regime→0050 曝險 | CHEAP_PASS×1、PASS×1 | spillover_overlay_v1（HYPOTHESIS_QUEUE.md#19「跨市場美股隔 |
| 第一批已做 | weinstein_alpha | 2 | 60,392 | 因子→前 N 檔等權月換股 | FAIL×2 | weinstein_stage2_unbiased alpha/beta顯著性關卡（#11的深挖/W |
| 第一批已做 | HQ#10 | 1 | 243 | regime→0050 曝險 | PASS×1 | regime擇時overlay#10協定第一個訊號：TAIEX 200MA趨勢濾網(binary曝險 |
| 第一批已做 | HQ#360 | 1 | 412 | regime→0050 曝險 | PASS×1 | trend_leverage_tw_0050_prereg |
| 第一批已做 | HQ#411 | 1 | 413 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | trend_leverage_us_spy_result |
| 第一批已做 | HQ#412 | 1 | 414 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | trend_leverage_tw_0050_result |
| 第一批已做 | HQ#413 | 1 | 415 | regime→0050 曝險 | PASS×1 | trend_scale_1_5x_0_5x_xmkt_prereg |
| 第一批已做 | HQ#415 | 1 | 416 | regime→0050 曝險 | FAIL×1 | trend_scale_1_5x_0_5x_xmkt_result |
| 第一批已做 | HQ#417 | 1 | 418 | regime→0050 曝險 | PASS×1 | core_allocation_24grid_result |
| 第一批已做 | HQ#419 | 1 | 421 | regime→0050 曝險 | 其他×1 | leveraged_bb90_6grid_421_prereg |
| 第一批已做 | crisis_gate_leveraged_bb90 | 1 | 426 | regime→0050 曝險 | PASS×1 | crisis_gate_leveraged_bb90_result |
| 第一批已做 | f_odd_lot_imbalance | 1 | 231 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_odd_lot_imbalance (#67 盤中零股委託簿失衡度，第1關cheap gate) |
| 第一批已做 | f_short_sale_utilization | 1 | 129 | 因子→前 N 檔等權月換股 | CHEAP_PASS×1 | f_short_sale_utilization個股融券使用率（HYPOTHESIS_QUEUE.m |
| 第一批已做 | hy_credit_spread | 1 | 329 | regime→0050 曝險 | FAIL×1 | HYPOTHESIS_QUEUE.md #77 美國高收益債利差(BAMLH0A0HYM2)資料可行 |
| 第一批已做 | margin_debt_level_window_robustness | 1 | 141 | 事件→事件後固定持有 | CHEAP_PASS×1 | margin_debt_level_v1 trailing窗口參數穩健性檢查（#140 60d(12 |
| 第一批已做 | ml_pricevol_oneshot | 1 | 483 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | ml_pricevol_tw2008_2012_oneshot |
| 第一批已做 | r1_0050_credit | 1 | 430 | regime→0050 曝險 | VIOLATES_SURVIVAL×1 | r1_0050_credit_gate_result |
| 第一批已做 | regime_overlay_breadth | 1 | 248 | regime→0050 曝險 | FAIL×1 | regime擇時overlay候選1：全市場廣度水位regime(4位數代號個股%站上200MA<0 |
| 第一批已做 | regime_overlay_margin_growth | 1 | 249 | regime→0050 曝險 | PASS×1 | regime擇時overlay候選4：全市場融資餘額12週成長率下檔regime(>expandin |
| 第一批已做 | regime_overlay_realized_vol | 1 | 247 | regime→0050 曝險 | FAIL×1 | regime擇時overlay候選3：TAIEX已實現波動度regime單獨測試(vol20>exp |
| 第一批已做 | sector_rotation_accel_gate73_gate2 | 1 | 282 | regime→0050 曝險 | FAIL×1 | HYPOTHESIS_QUEUE.md #73 產業金流加速度輪動（月頻、accel前20%產業）第 |
| 第一批已做 | short_sale_utilization_gate5_loo | 1 | 135 | regime→0050 曝險 | PASS×1 | short_sale_utilization_gate5_loo第5/6關leave-one-out |
| 第一批已做 | short_sale_utilization_gates | 1 | 134 | regime→0050 曝險 | PASS×1 | short_sale_utilization_gates第3關參數密集高原（HYPOTHESIS_Q |
| 第一批已做 | 名稱:ml_pricevol_tw2008 | 1 | 475 | regime→0050 曝險 | PASS×1 | ml_pricevol_tw2008_2012_prereg |
| 第一批已做 | 名稱:trend_leverage_us_ | 1 | 411 | regime→0050 曝險 | PASS×1 | trend_leverage_us_spy_prereg |
| 第一批已做 | regime_overlay_trend_filter | 6 | 271,272,273,274,275,349 | 非策略，跳過 | PASS×5、FAIL×1 | regime.候選2/#243 200MA趨勢濾網(TAIEX現貨) 成本.二重跑 |
| 第一批已做 | margin_utilization_regime | 3 | 133,382,387 | 非策略，跳過 | PASS×1、FAIL×2 | short_sale_utilization_portfolio_v1第2關隨機控制組（HYPOTH |
| 第一批已做 | odd_lot_imbalance | 3 | 232,383,388 | 非策略，跳過 | CHEAP_PASS×1、FAIL×2 | #67盤中零股交易比重(Odd-Lot Imbalance) portfolio層構造 gate2 |
| 第一批已做 | short_sale_utilization | 2 | 384,389 | 非策略，跳過 | PASS×2 | short_sale_utilization_portfolio_v1_new_engine_sca |
| 第一批已做 | HQ#133 | 1 | 137 | 非策略，跳過 | PASS×1 | short_sale_utilization整體最終alpha顯著性判定（HYPOTHESIS_QU |
| 第一批已做 | HQ#423 | 1 | 425 | 非策略，跳過 | 其他×1 | bb90_oos_2025_result |
| 第一批已做 | HQ#427 | 1 | 428 | 非策略，跳過 | 其他×1 | s3c6_oos_2025_result |
| 第一批已做 | HQ#445 | 1 | 446 | 非策略，跳過 | FAIL×1 | core_tilt_v2_stage1_result |
| 第一批已做 | core_tilt_v2_stage1 | 1 | 445 | 非策略，跳過 | PASS×1 | core_tilt_v2_stage1_prereg |
| 第一批已做 | margin_debt_level_train_val_heterogeneity | 1 | 142 | 非策略，跳過 | CHEAP_PASS×1 | margin_debt_level_v1疑慮①TRAIN/VAL異質性查證（#140/#141保留疑 |
| 第一批已做 | us_universe_dispersion_check | 1 | 171 | 非策略，跳過 | PASS×1 | 「宇宙離散度」假說直接檢驗——比較乾淨分層抽樣宇宙（#20/#21用）與舊熱門股偏誤宇宙（#17/# |
| 第一批已做 | weinstein_v2_alpha | 1 | 393 | 非策略，跳過 | FAIL×1 | weinstein_v2_alpha_gate_engine_fix_recheck |
| 第一批已做 | 名稱:core_tilt_backtest | 1 | 283 | 非策略，跳過 | FAIL×1 | core_tilt_backtest 決定性驗證：重建組合(純市值前50大) vs 0050真實日報 |
<!-- BATCH3-LIST-END -->

<!-- BATCH3-B1-BEGIN -->

## 5. 第二批第 1 批 10 族結果（先.一五五-3 ③，`research/reaudit_batch3_factors.py`，零新外部請求）

> 產生：2026-11-07T04:35:07；期間 2015-01-01～2024-12-31（**2025 起延長尚未做**，見下方待辦）。做法同 F13：#133 抽樣 236 檔、`research/backtest/` 引擎（下一交易日成交、漲跌停不成交、全成本）、只做多頭；順向與反向都掃。引擎 48 格 × 組合層 16 格＝每族 768 格挑最好（多重比較懲罰只當參考，不判死）。樣本內最優化，一定偏樂觀；宇宙是今天名冊抽樣，存活者偏誤未完全排除；3× 超過台股融資上限只當參考。非投資建議。

對照：同期加權價格指數（不含息）年化 +9.5%、MDD -31.6%、Sharpe 0.67。

| 因子族 | 格數完成 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不加止損：順向最好 年化／MDD | 1× 不加止損：反向最好 年化／MDD | 越線格數 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f_eps_surprise | 48/48 | 順向（分數高），換股 21 日，大盤閘門 開，N=30，個股停損 不設，L=1，組合止損 30% | +7.4% | -17.4% | 0.65 | 31% | 953 | 0.42 | 約第 14 名 | +7.4%／-17.4% | +5.3%／-14.4% | 325 | [png](data/reaudit_curves/batch3_f_eps_surprise.png) |
| f_revenue_surprise | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=20，個股停損 15%，L=1，組合止損 10% | +16.8% | -20.3% | 1.11 | 30% | 760 | 0.83 | 約第 7 名 | +16.0%／-19.3% | +3.5%／-20.8% | 253 | [png](data/reaudit_curves/batch3_f_revenue_surprise.png) |
| f_eps_growth | 48/48 | 順向（分數高），換股 63 日，大盤閘門 關，N=20，個股停損 15%，L=3，組合止損 10% | +29.0% | -41.6% | 0.97 | 31% | 457 | 0.70 | 約第 7 名 | +9.0%／-20.3% | +9.4%／-17.0% | 244 | [png](data/reaudit_curves/batch3_f_eps_growth.png) |
| f_value_pe | 48/48 | 反向（分數低），換股 21 日，大盤閘門 關，N=10，個股停損 不設，L=2，組合止損 10% | +18.3% | -32.9% | 0.78 | 30% | 513 | 0.56 | 約第 10 名 | +7.5%／-15.2% | +10.3%／-22.8% | 256 | [png](data/reaudit_curves/batch3_f_value_pe.png) |
| f_value_pb | 48/48 | 順向（分數高），換股 21 日，大盤閘門 開，N=20，個股停損 不設，L=1，組合止損 10% | +9.3% | -17.1% | 0.90 | 27% | 895 | 0.54 | 約第 10 名 | +7.2%／-18.4% | +5.5%／-18.9% | 319 | [png](data/reaudit_curves/batch3_f_value_pb.png) |
| f_low_vol | 48/48 | 順向（分數高），換股 63 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 30% | +5.7% | -7.2% | 1.28 | 25% | 639 | 0.80 | 約第 7 名 | +5.7%／-7.2% | +7.8%／-30.0% | 251 | [png](data/reaudit_curves/batch3_f_low_vol.png) |
| f_rel_strength | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=10，個股停損 15%，L=1.5，組合止損 10% | +31.8% | -32.7% | 1.08 | 30% | 196 | 0.97 | 約第 2 名 | +15.8%／-26.0% | -0.0%／-30.8% | 466 | [png](data/reaudit_curves/batch3_f_rel_strength.png) |
| f_52w_high_prox | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=20，個股停損 15%，L=1，組合止損 10% | +18.5% | -15.9% | 1.34 | 38% | 327 | 1.17 | 約第 1 名 | +16.4%／-18.9% | -0.4%／-28.2% | 352 | [png](data/reaudit_curves/batch3_f_52w_high_prox.png) |
| f_dividend_yield_ttm | 48/48 | 順向（分數高），換股 63 日，大盤閘門 開，N=30，個股停損 不設，L=1，組合止損 10% | +7.9% | -9.4% | 1.11 | 28% | 584 | 0.85 | 約第 6 名 | +7.9%／-9.4% | +12.9%／-25.1% | 187 | [png](data/reaudit_curves/batch3_f_dividend_yield_ttm.png) |
| f_gross_profitability | 48/48 | 反向（分數低），換股 21 日，大盤閘門 關，N=30，個股停損 不設，L=1，組合止損 10% | +7.3% | -20.8% | 0.71 | 28% | 1954 | 0.35 | 約第 16 名 | +3.4%／-20.3% | +7.8%／-23.5% | 371 | [png](data/reaudit_curves/batch3_f_gross_profitability.png) |

「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；期間只到 2024 底，跟第 0 節各族期間不同，只當粗排。格數未滿 48 的族是本輪時間到、下一輪接續，數字會再變。

<!-- BATCH3-B1-END -->

<!-- BATCH3-B1X-BEGIN -->

### 5a. 第 1／2 批價量因子延長到 2025 起（`research/reaudit_batch3_ext2025.py`，零新外部請求）

> 產生：2026-11-07T14:02:46。價格 2025 起接本機 FinMind 快取（同 F12／F13 延長作法；2024 底仍掛牌但沒有 2025 起價格的 45 檔從 2024-11-15 起不給分數），因子照 factors.py 原公式在延長價格上重算，2024 底前與原欄核對差 0。「舊最優」＝第 5 節只看 2024 底前挑出的那一組，延長後原封不動看 2025 起表現（這一段等於沒參與挑格）；「新最優」＝用全期（含 2025 起）重新挑，一定更樂觀。非投資建議。

| 因子族 | 格數 | 舊最優（2024 底前挑）參數 | 舊最優 2015～2024 年化／MDD | 舊最優 2025 起 年化／MDD／Sharpe | 舊最優全期 年化／MDD | 新最優（全期挑）參數 | 新最優全期 年化／MDD／Sharpe | 終點 |
|---|---|---|---|---|---|---|---|---|
| f_low_vol | 48/48 | 63_0_30_0.15_1 L=1 止損=0.3 | +5.7%／-7.2% | +3.7%／-7.2%／0.72 | +5.4%／-8.6% | 63_0_30_1.0_1 L=1 止損=0.2 | +5.4%／-8.6%／1.19 | 2026-09-24 |
| f_rel_strength | 48/48 | 21_0_10_0.15_1 L=1.5 止損=0.1 | +31.9%／-32.7% | -29.4%／-47.1%／-0.99 | +20.3%／-50.5% | 21_0_10_1.0_1 L=1 止損=0.1 | +23.7%／-31.2%／1.01 | 2026-09-24 |
| f_52w_high_prox | 48/48 | 21_0_20_0.15_1 L=1 止損=0.1 | +18.4%／-16.2% | +14.7%／-23.0%／0.77 | +17.8%／-26.0% | 63_0_30_1.0_1 L=1 止損=0.1 | +14.7%／-17.2%／1.15 | 2026-09-24 |
| f_idio_vol | 48/48 | 63_0_30_0.15_1 L=1 止損=0.3 | +6.5%／-7.5% | +1.5%／-3.9%／0.49 | +5.7%／-9.2% | 63_0_30_0.15_1 L=1 止損=0.2 | +5.7%／-9.2%／1.27 | 2026-09-24 |
| f_bab | 48/48 | 63_0_30_0.15_1 L=1 止損=0.1 | +6.9%／-12.2% | -2.0%／-8.0%／-0.47 | +5.6%／-16.0% | 21_0_20_0.15_-1 L=1 止損=None | +15.6%／-32.1%／0.79 | 2026-09-24 |
| f_residual_momentum | 48/48 | 63_0_20_0.15_1 L=1 止損=0.1 | +14.9%／-16.6% | +8.5%／-18.8%／0.57 | +14.0%／-20.0% | 21_0_10_1.0_1 L=1.5 止損=0.2 | +33.1%／-42.8%／1.00 | 2026-09-24 |
| f_short_reversal_1m | 48/48 | 21_0_30_1.0_-1 L=3 止損=0.1 | +30.0%／-41.7% | +21.7%／-44.0%／0.67 | +28.8%／-44.0% | 21_1_10_0.15_-1 L=1 止損=0.2 | +20.2%／-27.9%／0.97 | 2026-09-24 |
| f_short_term_reversal_1w | 48/48 | 21_0_30_1.0_-1 L=3 止損=0.1 | +35.7%／-41.3% | +40.0%／-40.9%／0.97 | +36.3%／-41.3% | 21_0_30_1.0_-1 L=1 止損=0.2 | +22.2%／-24.3%／1.12 | 2026-09-24 |
| f_ma_breakout | 48/48 | 21_0_10_0.15_1 L=1.5 止損=0.1 | +21.3%／-32.2% | +32.4%／-26.6%／1.00 | +22.9%／-33.0% | 21_0_10_0.15_1 L=1.5 止損=0.1 | +22.9%／-33.0%／0.86 | 2026-09-24 |
| f_amihud_illiq | 48/48 | 21_1_10_1.0_-1 L=3 止損=0.1 | +18.9%／-43.2% | -18.1%／-54.9%／-0.12 | +12.5%／-59.8% | 21_1_10_1.0_-1 L=1 止損=0.1 | +15.5%／-24.6%／0.99 | 2026-09-24 |
| f_listing_age_days | 48/48 | 63_1_30_1.0_1 L=1 止損=0.1 | +6.8%／-13.0% | +3.0%／-11.3%／0.40 | +6.2%／-13.0% | 21_0_10_0.15_-1 L=1 止損=None | +9.5%／-19.0%／0.64 | 2026-09-24 |
| f_gross_profitability | 48/48 | 21_0_30_1.0_-1 L=1 止損=0.1 | +7.3%／-20.8% | -9.2%／-16.1%／-1.00 | +4.7%／-30.5% | 63_1_30_1.0_-1 L=1 止損=None | +5.0%／-18.7%／0.61 | 2026-09-24 |
| f_gross_margin_stability | 48/48 | 21_0_30_0.15_1 L=1 止損=0.2 | +10.0%／-16.8% | +7.7%／-17.3%／0.64 | +9.6%／-21.1% | 63_0_20_0.15_1 L=1 止損=None | +8.4%／-15.3%／0.89 | 2026-09-24 |
| f_asset_growth | 48/48 | 21_0_10_0.15_1 L=1 止損=0.2 | +8.8%／-22.2% | -7.3%／-20.3%／-0.36 | +6.2%／-31.4% | 21_0_10_0.15_1 L=1 止損=0.1 | +5.8%／-27.1%／0.47 | 2026-09-24 |
| f_accruals | 48/48 | 63_0_30_0.15_-1 L=1 止損=0.1 | +8.7%／-14.0% | -2.9%／-10.4%／-0.31 | +6.9%／-21.2% | 21_0_20_0.15_1 L=1 止損=0.3 | +8.0%／-17.4%／0.65 | 2026-09-24 |
| f_eps_growth | 48/48 | 63_0_20_0.15_1 L=3 止損=0.1 | +29.0%／-41.6% | +11.2%／-28.2%／0.49 | +26.2%／-55.1% | 21_0_20_0.15_1 L=1.5 止損=0.1 | +17.1%／-31.5%／0.86 | 2026-09-24 |
| f_eps_surprise | 48/48 | 21_1_30_1.0_1 L=1 止損=0.3 | +7.3%／-17.4% | +17.3%／-25.2%／0.89 | +8.7%／-25.2% | 21_0_20_1.0_1 L=1 止損=0.1 | +10.0%／-23.2%／0.72 | 2026-09-24 |
| f_revenue_surprise | 48/48 | 21_0_20_0.15_1 L=1 止損=0.1 | +16.8%／-20.3% | +44.9%／-16.9%／1.66 | +20.6%／-27.6% | 63_0_20_0.15_1 L=1 止損=0.2 | +18.1%／-20.2%／1.16 | 2026-09-24 |

參數欄格式＝換股日數_大盤閘門_N_個股停損(1.0＝不設)_方向。2025 起只有約 1.7 年，數字波動大，只當參考。

<!-- BATCH3-B1X-END -->

<!-- BATCH3-B2-BEGIN -->

## 6. 第二批第 2 批 10 族結果（先.一五五-3 ③，`research/reaudit_batch3_factors.py`，零新外部請求）

> 產生：2026-11-07T06:36:33；期間 2015-01-01～2024-12-31（**2025 起延長尚未做**，見下方待辦）。做法同 F13：#133 抽樣 236 檔、`research/backtest/` 引擎（下一交易日成交、漲跌停不成交、全成本）、只做多頭；順向與反向都掃。引擎 48 格 × 組合層 16 格＝每族 768 格挑最好（多重比較懲罰只當參考，不判死）。樣本內最優化，一定偏樂觀；宇宙是今天名冊抽樣，存活者偏誤未完全排除；3× 超過台股融資上限只當參考。非投資建議。

對照：同期加權價格指數（不含息）年化 +9.5%、MDD -31.6%、Sharpe 0.67。

| 因子族 | 格數完成 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不加止損：順向最好 年化／MDD | 1× 不加止損：反向最好 年化／MDD | 越線格數 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f_bab | 48/48 | 順向（分數高），換股 63 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 10% | +6.9% | -12.2% | 0.88 | 27% | 695 | 0.57 | 約第 9 名 | +7.9%／-18.8% | +11.8%／-28.3% | 290 | [png](data/reaudit_curves/batch3_f_bab.png) |
| f_inst_flow | 48/48 | 反向（分數低），換股 21 日，大盤閘門 開，N=10，個股停損 15%，L=2，組合止損 10% | +19.9% | -25.7% | 1.12 | 29% | 319 | 0.77 | 約第 7 名 | +7.7%／-14.1% | +10.6%／-20.5% | 191 | [png](data/reaudit_curves/batch3_f_inst_flow.png) |
| f_margin_utilization | 48/48 | 反向（分數低），換股 63 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 20% | +5.7% | -10.7% | 0.90 | 30% | 691 | 0.54 | 約第 10 名 | +12.4%／-25.2% | +5.7%／-10.7% | 341 | [png](data/reaudit_curves/batch3_f_margin_utilization.png) |
| f_foreign_streak | 48/48 | 順向（分數高），換股 21 日，大盤閘門 開，N=30，個股停損 15%，L=1，組合止損 20% | +8.7% | -19.5% | 0.84 | 31% | 768 | 0.45 | 約第 13 名 | +8.7%／-19.5% | +8.4%／-23.4% | 307 | [png](data/reaudit_curves/batch3_f_foreign_streak.png) |
| f_idio_vol | 48/48 | 順向（分數高），換股 63 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 30% | +6.5% | -7.5% | 1.37 | 25% | 663 | 0.86 | 約第 5 名 | +6.5%／-7.5% | +9.1%／-31.2% | 225 | [png](data/reaudit_curves/batch3_f_idio_vol.png) |
| f_ma_breakout | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=10，個股停損 15%，L=1.5，組合止損 10% | +21.0% | -32.2% | 0.82 | 33% | 174 | 0.65 | 約第 7 名 | +13.0%／-23.7% | -2.5%／-33.9% | 457 | [png](data/reaudit_curves/batch3_f_ma_breakout.png) |
| f_short_margin_ratio | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=20，個股停損 15%，L=3，組合止損 10% | +23.2% | -45.9% | 0.78 | 31% | 899 | 0.51 | 約第 11 名 | +10.2%／-32.3% | +3.2%／-11.7% | 329 | [png](data/reaudit_curves/batch3_f_short_margin_ratio.png) |
| f_residual_momentum | 48/48 | 順向（分數高），換股 63 日，大盤閘門 關，N=20，個股停損 15%，L=1，組合止損 10% | +14.9% | -16.6% | 1.00 | 31% | 349 | 0.90 | 約第 3 名 | +13.2%／-23.6% | +0.0%／-23.2% | 365 | [png](data/reaudit_curves/batch3_f_residual_momentum.png) |
| f_short_reversal_1m | 48/48 | 反向（分數低），換股 21 日，大盤閘門 關，N=30，個股停損 不設，L=3，組合止損 10% | +29.9% | -41.7% | 0.94 | 33% | 662 | 0.72 | 約第 7 名 | +2.5%／-34.1% | +15.2%／-25.8% | 387 | [png](data/reaudit_curves/batch3_f_short_reversal_1m.png) |
| f_short_term_reversal_1w | 48/48 | 反向（分數低），換股 21 日，大盤閘門 關，N=30，個股停損 不設，L=3，組合止損 10% | +35.2% | -41.3% | 1.02 | 36% | 802 | 0.85 | 約第 6 名 | +8.9%／-26.2% | +19.0%／-23.0% | 379 | [png](data/reaudit_curves/batch3_f_short_term_reversal_1w.png) |

「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；期間只到 2024 底，跟第 0 節各族期間不同，只當粗排。格數未滿 48 的族是本輪時間到、下一輪接續，數字會再變。

<!-- BATCH3-B2-END -->

<!-- BATCH3-B3-BEGIN -->

## 7. 第二批第 3 批 6 族結果（先.一五五-3 ③，`research/reaudit_batch3_factors.py`，零新外部請求）

> 產生：2026-11-07T07:53:15；期間 2015-01-01～2024-12-31（**2025 起延長尚未做**，見下方待辦）。做法同 F13：#133 抽樣 236 檔、`research/backtest/` 引擎（下一交易日成交、漲跌停不成交、全成本）、只做多頭；順向與反向都掃。引擎 48 格 × 組合層 16 格＝每族 768 格挑最好（多重比較懲罰只當參考，不判死）。樣本內最優化，一定偏樂觀；宇宙是今天名冊抽樣，存活者偏誤未完全排除；3× 超過台股融資上限只當參考。非投資建議。

對照：同期加權價格指數（不含息）年化 +9.5%、MDD -31.6%、Sharpe 0.67。

| 因子族 | 格數完成 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不加止損：順向最好 年化／MDD | 1× 不加止損：反向最好 年化／MDD | 越線格數 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f_accruals | 48/48 | 反向（分數低），換股 63 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 10% | +8.7% | -14.0% | 0.90 | 27% | 808 | 0.62 | 約第 9 名 | +9.4%／-17.7% | +6.3%／-12.7% | 246 | [png](data/reaudit_curves/batch3_f_accruals.png) |
| f_amihud_illiq | 48/48 | 反向（分數低），換股 21 日，大盤閘門 開，N=10，個股停損 不設，L=3，組合止損 10% | +18.9% | -43.2% | 0.72 | 29% | 275 | 0.44 | 約第 13 名 | +4.0%／-19.8% | +5.6%／-21.6% | 267 | [png](data/reaudit_curves/batch3_f_amihud_illiq.png) |
| f_asset_growth | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=10，個股停損 15%，L=1，組合止損 20% | +8.8% | -22.0% | 0.65 | 32% | 668 | 0.40 | 約第 14 名 | +8.1%／-25.4% | +1.4%／-19.9% | 437 | [png](data/reaudit_curves/batch3_f_asset_growth.png) |
| f_gross_margin_stability | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=30，個股停損 15%，L=1，組合止損 20% | +10.0% | -16.8% | 0.93 | 29% | 1600 | 0.59 | 約第 9 名 | +10.0%／-16.8% | +4.3%／-15.9% | 205 | [png](data/reaudit_curves/batch3_f_gross_margin_stability.png) |
| f_listing_age_days | 48/48 | 順向（分數高），換股 63 日，大盤閘門 開，N=30，個股停損 不設，L=1，組合止損 10% | +6.8% | -13.0% | 0.88 | 27% | 562 | 0.52 | 約第 10 名 | +7.3%／-14.1% | +9.0%／-19.0% | 238 | [png](data/reaudit_curves/batch3_f_listing_age_days.png) |
| f_inst_streak_days | 48/48 | 順向（分數高），換股 21 日，大盤閘門 關，N=10，個股停損 不設，L=1，組合止損 10% | +10.1% | -16.3% | 0.86 | 34% | 218 | 0.62 | 約第 9 名 | +10.2%／-21.0% | +5.1%／-14.3% | 262 | [png](data/reaudit_curves/batch3_f_inst_streak_days.png) |

「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；期間只到 2024 底，跟第 0 節各族期間不同，只當粗排。格數未滿 48 的族是本輪時間到、下一輪接續，數字會再變。

<!-- BATCH3-B3-END -->

<!-- BATCH3-B4-BEGIN -->

## 8. 第二批第 4 批 regime→0050 類 10 族結果（先.一五五-3 ③，`research/reaudit_batch4_regime.py`，零新外部請求）

> 產生：2026-11-07T15:07:45；期間＝各族訊號實際有值起～2024-12-31（對齊檔只到 2024 底，**2025 起延長尚未做**）。做法：訊號觀察日後第 2 個交易日起生效（隔日收盤調倉）、expanding 百分位門檻（不偷看未來）；轉換（水位／變化）×方向×門檻 70/80/90×避險曝險 0/0.5 × 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%。0050 含息、成本照實（滑價＋手續費＋賣出證交稅）、槓桿借款＝台灣無風險利率＋年 1%。樣本內最優化一定偏樂觀；多重比較只當參考。3× 超過台股融資上限只當參考。非投資建議。

| 族 | 期間起 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不設止損最好 年化／MDD | 同期 0050 年化／MDD | 同槓桿不擇時 年化／MDD | 越線格數 | 曲線 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fut（#18 等 0050 多時間框架動能投票（fut 家族改做現股 0050）） | 2004-06-17 | lookbacks=20/60/250，votes_needed=2，riskoff_exposure=0.5，L=1.0，stop=0.1 | +9.1% | -31.3% | 0.67 | 48% | 166 | 0.29 | 約第 17 名 | +8.6%／-38.6% | +11.5%／-55.8% | +11.5%／-55.8% | 175 | [png](data/reaudit_curves/batch3_b4_fut.png) |
| HQ#76（#76 VIX 期限結構（VIX9D/VIX）） | 2012-02-02 | transform=chg21，riskoff_when=高，pct_threshold=0.9，riskoff_exposure=0.5，L=2.0，stop=0.2 | +24.1% | -49.1% | 0.89 | 52% | 147 | 0.49 | 約第 12 名 | +11.5%／-32.0% | +14.2%／-34.0% | +24.5%／-58.5% | 349 | [png](data/reaudit_curves/batch3_b4_HQ76.png) |
| fx_twd（#32 美元兌台幣變化） | 2016-02-23 | transform=level，riskoff_when=高，pct_threshold=0.9，riskoff_exposure=0.0，L=2.0，stop=0.1 | +30.5% | -32.7% | 1.12 | 53% | 36 | 0.93 | 約第 3 名 | +18.8%／-28.0% | +17.8%／-34.0% | +32.1%／-58.5% | 224 | [png](data/reaudit_curves/batch3_b4_fx_twd.png) |
| option_pcr_overlay（#31 台指選擇權 PCR 擇時） | 2016-01-15 | transform=chg21，riskoff_when=低，pct_threshold=0.9，riskoff_exposure=0.5，L=2.0，stop=0.1 | +17.9% | -34.4% | 0.74 | 45% | 166 | 0.52 | 約第 10 名 | +13.4%／-32.3% | +18.5%／-34.0% | +33.6%／-58.5% | 397 | [png](data/reaudit_curves/batch3_b4_option_pcr_overlay.png) |
| copper_gold_ratio（#34 銅金比） | 2016-01-26 | transform=level，riskoff_when=高，pct_threshold=0.8，riskoff_exposure=0.0，L=2.0，stop=0.2 | +39.3% | -35.7% | 1.29 | 45% | 31 | 1.10 | 約第 1 名 | +18.9%／-28.2% | +18.4%／-34.0% | +33.3%／-58.5% | 250 | [png](data/reaudit_curves/batch3_b4_copper_gold_ratio.png) |
| fred_yield_curve（#33 美債 10Y-2Y 利差） | 2016-01-28 | transform=chg63，riskoff_when=低，pct_threshold=0.9，riskoff_exposure=0.5，L=3.0，stop=0.3 | +52.7% | -49.4% | 1.15 | 62% | 39 | 1.07 | 約第 1 名 | +19.0%／-28.2% | +18.5%／-34.0% | +47.3%／-74.7% | 214 | [png](data/reaudit_curves/batch3_b4_fred_yield_curve.png) |
| hy_etf_ratio（#78 HYG/IEF 信用比值） | 2008-05-02 | transform=chg21，riskoff_when=高，pct_threshold=0.9，riskoff_exposure=0.5，L=2.0，stop=0.1 | +14.6% | -37.9% | 0.62 | 51% | 116 | 0.38 | 約第 16 名 | +10.9%／-34.0% | +10.5%／-52.4% | +15.5%／-79.8% | 384 | [png](data/reaudit_curves/batch3_b4_hy_etf_ratio.png) |
| spillover_overnight（#19 美股隔夜報酬外溢） | 2011-01-17 | transform=level，riskoff_when=低，pct_threshold=0.9，riskoff_exposure=0.5，L=1.5，stop=0.2 | +10.2% | -33.7% | 0.54 | 47% | 221 | 0.30 | 約第 16 名 | +8.4%／-35.8% | +12.1%／-34.0% | +15.8%／-47.6% | 466 | [png](data/reaudit_curves/batch3_b4_spillover_overnight.png) |
| cbi_signal（#81 景氣對策信號分數） | 2003-07-02 | transform=chg3，riskoff_when=低，pct_threshold=0.8，riskoff_exposure=0.0，L=1.0，stop=不設 | +13.5% | -28.2% | 0.87 | 94% | 18 | 0.48 | 約第 12 名 | +13.5%／-28.2% | +11.5%／-55.8% | +11.5%／-55.8% | 406 | [png](data/reaudit_curves/batch3_b4_cbi_signal.png) |
| dgbas_unemployment（#80 台灣失業率 YoY） | 2003-07-02 | transform=level，riskoff_when=高，pct_threshold=0.9，riskoff_exposure=0.5，L=2.0，stop=0.1 | +15.9% | -40.1% | 0.66 | 47% | 75 | 0.40 | 約第 16 名 | — | +11.5%／-55.8% | +17.1%／-83.7% | 494 | [png](data/reaudit_curves/batch3_b4_dgbas_unemployment.png) |

「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；各族期間不同（2003～2016 起不等），只當粗排。交易次數＝減碼／出場次數；勝率＝每段持有期間結束時淨值高於進場時的比例。
**讀法提醒**：2016～2024 是大多頭，「同槓桿不擇時」本身年化就很高、但 MDD 多半越過 50%；這批最好的組合主要價值是把回撤壓回 50% 內，年化贏過同槓桿不擇時的只有少數族（看最後兩欄）。fut 族（多時間框架動能）改在 0050 現股上做，期間含 2008。第一版訊號只 shift 1 天，美股隔夜外溢族因此偷吃到台股開盤跳空（年化 +91.9%），已改成觀察日後第 2 個交易日生效並重跑。

<!-- BATCH3-B4-END -->
