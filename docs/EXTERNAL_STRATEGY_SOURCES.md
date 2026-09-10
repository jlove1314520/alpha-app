# EXTERNAL_STRATEGY_SOURCES.md — 外部（名家）策略來源與公開後衰減風險登記

**這份檔案存在的理由**：2026-09-08 總司令裁示【外部策略三】第 2 點——
「每條外部策略在 signal_status.json 標註來源與『公開後衰減』風險（引用
McLean & Pontiff 2016），App 上顯示時一併揭露」。這份文件是那個標註的
權威來源（citation 從哪裡來、狀態對應到哪個帳本編號），`data/signal_status.json`
的 `external_strategies` 節只放精簡版，詳情回這裡查。

規則見 `CLAUDE.md`「外部策略匯入紀律」：每匯入一條算一次試驗、須
`register_trial()`、單批上限 8 條、跨軌同概念依 |r|>0.7 同家族規則只算一個
獨立發現。**只抄機制與判定規則，不抄原文獻在別的市場調出來的參數**——
本專案的參數全部是在台美股/台指期資料上獨立掃出來或依原文獻公開規則寫死
（見各條「參數來源」欄），不是从其他市場的回測結果搬過來的。

## 公開後衰減風險（McLean & Pontiff, 2016, *Journal of Finance*）

> McLean, R. D., & Pontiff, J. (2016). "Does Academic Research Destroy Stock
> Return Predictability?" *The Journal of Finance*, 71(1), 5-32.

實證發現：學術文獻正式發表已知異常報酬因子後，樣本外（post-publication）
報酬平均衰減約 **1/3～1/2**，部分歸因於套利資金湧入、部分歸因於資料探勘
（發表前的樣本內表現本身已經是挑出來的）。**這篇是每一條「外部名家策略」
共同適用的基準衰減風險**——不分市場、不分因子類型，公開發表本身就是一個
系統性利空。

適用範圍界定：這個衰減風險只適用於**已經在公開文獻／書籍／業界規則發表過**
的機制（本文件列的這些）；**本專案自己原創、尚未發表的假說**（`hypothesis_queue`
馬拉松輪次 #1～#70 那些）不適用這條，那些的風險是「樣本內過擬合」不是
「發表後被套利抹平」，兩種風險成因不同、不能用同一個數字概括。

## 台股軌（TW）

| 策略/因子 | 原始文獻/來源 | 本專案代號 | 狀態 | 帳本 |
|---|---|---|---|---|
| PEAD／SUE（盈餘意外延續） | Foster, Olsen & Shevlin (1984) *The Accounting Review*；Bernard & Thomas (1989) *Journal of Accounting Research* | `f_eps_surprise`／`f_revenue_surprise` | `f_eps_surprise` 通過全體分母校正（見 `SELECTION_BIAS_LEDGER.md`）；`f_revenue_surprise` 降級 FAIL | `TRIALS_LEDGER.md` #7／#8 |
| Piotroski F-score（財務體質 9 項二元品質分數） | Piotroski, J. D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research*, 38, 1-41. | F-score 排雷閘門 | FAIL（HYPOTHESIS_QUEUE.md #23，2026-09-03） | `STRATEGY_GRAVEYARD.md` #23 |
| Sloan 應計項目異常 | Sloan, R. G. (1996). "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?" *The Accounting Review*, 71(3), 289-315. | `f_accruals` | 已測（見 `factor_ic_accruals.py`） | 詳 `TRIALS_LEDGER.md` 搜尋 `f_accruals` |
| Novy-Marx 毛利率溢酬 | Novy-Marx, R. (2013). "The Other Side of Value: The Gross Profitability Premium." *Journal of Financial Economics*, 108(1), 1-28. | `f_gross_profitability` | 降級 FAIL（總帳裁示分母重算後） | `SELECTION_BIAS_LEDGER.md` |
| 殘差動量 Residual Momentum | Blitz, D., Huij, J., & Martens, M. (2011). "Residual Momentum." *Journal of Empirical Finance*, 18(3), 506-521. | `f_residual_momentum` | FAIL（第1關 cheap IC gate 未過） | `STRATEGY_GRAVEYARD.md` #9 |
| 52 週高點接近度 | George, T. J., & Hwang, C.-Y. (2004). "The 52-Week High and Momentum Investing." *The Journal of Finance*, 59(5), 2145-2176. | `f_52w_high_prox` | FAIL（策略層，因子層 IC 本身通過但組合未過） | `STRATEGY_GRAVEYARD.md` #17（2026-09-02） |
| Weinstein 第二階段（Stage Analysis） | Weinstein, S. (1988). *Secrets for Profiting in Bull and Bear Markets*. Dow Jones-Irwin.（業界方法論書籍，非學術論文） | Stage 2 掃描 | FAIL（不可泛化成整個概念無效，見備註） | `STRATEGY_GRAVEYARD.md` |
| BAB（Betting Against Beta） | Frazzini, A., & Pedersen, L. H. (2014). "Betting Against Beta." *Journal of Financial Economics*, 111(1), 1-25. | `factor_ic_bab.py` | 已測，文獻基礎不受既有 FAIL 結論影響（見墳場備註） | `STRATEGY_GRAVEYARD.md` |

## 美股軌（US）

外部一改.1（把上述 TW 已測名家因子搬到美股宇宙重測）**暫停中**——
等資料源一.4（存活者偏誤修正的價格源）解決後才能重啟，暫停理由與進度見
`PENDING_QUEUE.md` 外部一改.1。美股軌目前只有既有的 4 個一般性因子
（非本文件定義的「具名策略」，是較generic的異常報酬因子，仍一併列出來源）：

| 因子 | 原始文獻 | 本專案代號 | 狀態 |
|---|---|---|---|
| 低波動異常 | Ang, Hodrick, Xing & Zhang (2006). "The Cross-Section of Volatility and Expected Returns." *The Journal of Finance*, 61(1), 259-299. | `f_us_low_vol` | 通過（見 `SELECTION_BIAS_LEDGER.md` 跨軌重複因子，與 `f_low_vol` 同家族） |
| 12 個月動量 | Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *The Journal of Finance*, 48(1), 65-91. | `f_us_momentum_12m` | 已測 |
| 短期反轉 | Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns." *The Journal of Finance*, 45(3), 881-898. | `f_us_reversal_1m` | FAIL（分母重算後仍不成立） |
| 帳面市值比（價值） | Fama, E. F., & French, K. R. (1992). "The Cross-Section of Expected Stock Returns." *The Journal of Finance*, 47(2), 427-465. | `f_us_value_bm` | 已測 |

## 期貨軌（FUT）——外部一改.3，2026-09-10 完成

五個機制皆為**公開發表的規則型交易系統**，非學術論文，參數照原始規則
寫死（見 `CLAUDE.md`「拿機制不拿參數」原則的唯一豁免：規則本身就是
公開參數的一部分）：

| 機制 | 原始來源 | 本專案代號 | 狀態 | 同家族分組 |
|---|---|---|---|---|
| 海龜法則 System 1（20/10 突破） | Dennis, R.（口述訓練規則，公開整理見 Faith, C. M. (2007). *Way of the Turtle*. McGraw-Hill.） | `fut_turtle_system1_20_10` | FAIL（百分位 57.5） | 家族 A（見下） |
| Donchian 通道完整版（55/20） | Donchian, R. D.（1960 年代提出，經典趨勢跟隨通道，海龜 System 2 沿用同一構造） | `fut_donchian_full_55_20` | FAIL（百分位 54.0） | 家族 A |
| Keltner 通道突破（EMA20±2ATR10） | Keltner, C. W. (1960). *How to Make Money in Commodities*.（Linda Bradford Raschke 後續推廣的 ATR 版本，本專案採 ATR 版） | `fut_keltner_breakout_20_2atr` | FAIL（百分位 78.8，五者中最高但未過門檻） | 家族 A |
| 波動度突破（0.5×ATR20） | 業界通用波動度突破規則，無單一起源論文 | `fut_vol_breakout_0p5atr` | FAIL（百分位 7.0，終值僅 0.1675） | 獨立（與其他四者 r≤0.234） |
| CTA 多時間框架趨勢＋波動度目標 | 業界系統化 CTA 常見構造（多週期動量投票＋波動度目標部位縮放），無單一起源論文 | `fut_cta_multi_tf_voltarget` | FAIL（百分位 73.0） | 家族 A |

**家族 A 揭露**（依 CLAUDE.md 同家族規則）：海龜／Donchian／Keltner／CTA
多時間框架彼此相關係數 r=+0.64～+0.84（且與既有 `hyp_trend_multi_tf`／
`hyp_donchian_breakout` r≈+0.70～+0.75），**5 筆試驗只算 2 個獨立發現**
（家族 A 一個、波動度突破一個），已在登記時（`TRIALS_LEDGER.md` #234～#238）
完成揭露，本文件不重複計數。

## 待做（外部二改，尚未開始）

首批抄新策略 8 條分配：美股 3（O'Neil CANSLIM、Minervini SEPA、Darvas box）、
期貨 3（見【外部策略一改】原話列的候補：CTA 多時間框架已用掉一個名額，
剩餘從波動度突破族群或其他公開系統化趨勢規則挑）、台股 2（投信季底作帳、
融券軋空）。**完成後回頭補進本文件對應區塊，不得只更新 signal_status 不更新
這裡**——這裡是來源真相，signal_status 是精簡展示版。

## 誠實揭露（本文件的已知限制）

- 部分文獻年份／期刊資訊取自研究者對經典文獻的既有知識，**未逐一查證
  DOI 或原始 PDF**——這些都是財務金融領域公認的經典引用（Fama-French、
  Jegadeesh-Titman、Piotroski、Sloan、Novy-Marx、Frazzini-Pedersen 等），
  但嚴謹度不等同於官方查證三來源紀律（那條規則是給「某資料源有沒有這個
  資料」這類事實性查證用的，不是給學術引用用的）。若對特定引用有疑慮，
  以原始論文為準，本文件只是索引。
- App 端（`index.html`）**目前尚未讀取 `data/signal_status.json`**
  （2026-09-10 查證：`grep signal_status index.html` 零命中），所以
  「App 上顯示時一併揭露」這句裁示目前只做到「資料層已標註」，
  **UI 顯示尚未串接**。串接需要動 `index.html`（開發帽的檔案），依帽子
  規則不在本項（債務帽／研究資料）範圍內，需另開一個開發帽項目才能做。
  這裡誠實記錄缺口，不假裝已經顯示在畫面上。
