# MARATHON_LOG.md — 自主研究馬拉松可見心跳（2026-08-29啟動）

## 2026-09-07 hypothesis_queue排程接續（取鎖時發現陳舊鎖檔，pid 92972，
30分鐘，已回收接手）— #50前置依賴查證+#51三子事件資料可行性查證，
仍未結案（純地基查證，非PASS/FAIL）。確認#50前置依賴「資料一逐筆
tick落地」剛於2026-09-07起步、遠未累積20交易日，改依協定指引查#51。
**子事件2（現金增資除權參考價）確認可行**：FinMind`TaiwanStockDividend`
（本機已有2170檔快取，零新增API呼叫）含`AnnouncementDate`，118筆現金
增資事件中`AnnouncementDate<ex_date`118/118成立，lag中位數7天。
**子事件1（融券強制回補/停資停券）三來源皆確認直接預告表不可行**
（TWSE openapi BFI84U即時快照不支援歷史回溯、FinMind同名dataset付費牆、
TPEx同構「預告表」佐證），備用反推重建路徑留待下一輪。**子事件3（可轉
債轉換價重設）僅查2來源（FinMind CB系列付費牆、TPEx為發行資料非重設
事件），未達三來源門檻未下結論**，MOPS查證留待下一輪。新增
`forced_trader_events_probe.py`（可重複執行）。完整見`HYPOTHESIS_
QUEUE.md`#51條目「資料可行性查證」段落。`is_holdout_consumed()`開工/
收工前皆確認`False`。本輪工作到此為止，下一輪從補齊子事件3的MOPS
查證+查證子事件1反推路徑開始。

## 2026-09-07 01:26 hypothesis_queue排程接續 — #49第6關逐年一致性，
已結案：**FAIL**。依上一輪建議改道跳過gate2 placebo，直接對gate1已
CHEAP_PASS的overnight段（TAIEX open切分）做逐年一致性檢驗（新增
`overnight_intraday_gate6_consistency.py`），事前綁定門檻沿用#29/#34
同一把尺（同號年數占比>=5/6=83.3%，TRAIN/VAL兩窗口各自獨立要求通過）。
**結果**：TRAIN（2010-2020共11年）11/11年同號=100.0%通過；VAL
（2021-2024共4年）僅3/4年同號=75.0%（2022年overnight轉負-3.46%，
全球股市系統性下跌年），未達83.3%門檻（N=4等同要求4/4零容錯），未
通過。依事前綁定不移動門柱鐵律判**FAIL**，不再回頭補做gate2，#49
正式結案。完整見`HYPOTHESIS_QUEUE.md`#49「最終判定」段落、
`STRATEGY_GRAVEYARD.md`#49、`TRIALS_LEDGER.md`#184。
`is_holdout_consumed()`開工/收工前皆確認`False`，全程零新增API呼叫
（複用round180已快取的`^TWII`資料）。**佇列#1~49全數結案。依
2026-09-07轉向裁示，舊方向不再新增假設**，已在`HYPOTHESIS_QUEUE.md`
記下一輪指引（先查證#50前置依賴「資料一逐筆tick落地」是否已累積
足夠交易日，未足則查#51是否能先開跑，不跳過排序直接挑#52）——本輪
只做完#49收尾這一個有界工作單位，未擅自開始#50/#51查證，留給下一輪。

## 2026-09-07 hypothesis_queue排程接續 — #49第2關placebo設計，仍未
結案（非PASS/FAIL）。三來源查證確認TRAIN期(2015-2020)無法取得TAIEX
盤中分鐘/tick價格資料（yfinance回溯上限1m~8天/5m~60天/60m~730天皆
不覆蓋；FinMind免費層無盤中1分K；TWSE`MI_5MINS`雖支援任意歷史日期
但欄位是委託/成交統計非指數點位），「隨機時刻切分」placebo判定不
可行。改用`high`/`low`當替代切分點的比較設計（`overnight_intraday_
alt_cutpoint_placebo.py`，新增）：發現high/low切分也通過跟open完全
同一套事前綁定判準且數字更極端，但診斷出這是**選擇偏誤**（high/low
是當天極值，依定義必然產生偏態，不是經濟機制證據）——這個比較選錯
對照組，既不能證明open特殊也不能證明不特殊。連續兩輪嘗試gate2操作化
都因方法論問題卡住，非訊號被推翻。**建議下一輪放棄合成placebo，
改道直接做gate6逐年一致性**（對已CHEAP_PASS的open切分逐年拆解，
不需要null model，是#29/#34已示範的標準做法）。完整見
`HYPOTHESIS_QUEUE.md`#49條目最新更新、`TRIALS_LEDGER.md`#182。
`is_holdout_consumed()`開工/收工前皆確認`False`。本輪同時注意到
`C:\alpha\alpha-app\CLAUDE.md`在本輪工作期間被另一個來源新增「七之三、
研究紀律」章節（移植自Cybex的判斷方法，含存活者偏誤/財報跳空/交易
時段/借券成本/漲跌停五項台股特有偽影家族），不是本輪產生，未觸碰，
下一輪應納入閱讀範圍。

## 2026-09-06 23:57 hypothesis_queue排程接續 — #49第1關cheap gate跑完，
**CHEAP_PASS**（非最終判定）。新增`overnight_intraday_decomposition_gate.py`，
TAIEX(^TWII)逐日拆解overnight/intraday報酬，用log報酬加總做期間累積
報酬的exact可加性分解（恆等式sanity檢查誤差2.22e-16）。事前綁定判準
（至少一段兩期皆顯著p<0.05+同號+log貢獻占比兩期皆偏離50%±20%）：
overnight段乾淨通過（TRAIN mean=+0.0788%/t=+7.737/p=0.0000/占比=
+356.2%，VAL mean=+0.0552%/t=+3.124/p=0.0018/占比=+114.6%）；
intraday段VAL期不顯著(p=0.8954)未通過，但依判準只需一段即
CHEAP_PASS。跟美股文獻（Lou/Polk/Skouras 2019 JFE；AQR隔夜/盤中報酬
不對稱現象）方向一致。**開放問題誠實記錄**：本佇列既有隨機控制組模板
（打亂訊號時序、保留目標時序）不直接適用於這種「同一報酬加性分解」
機制類型，下一輪需先設計適配的第2關placebo檢定，不強套舊模板產生
偽結論。完整見`HYPOTHESIS_QUEUE.md`#49條目、`TRIALS_LEDGER.md`#180。
`is_holdout_consumed()`開工/收工前皆確認`False`。本輪工作到此為止，
下一輪從設計第2關placebo檢定開始，不跳關。

## 2026-09-06 23:28 hypothesis_queue排程接續 — 重新查證`BACKLOG.md`
確認#5/#6/#8/#10四項外部依賴（`value_board_v2`回測未通過、題材動能榜
/未來性濾網紙上交易中）仍未解鎖，跟上一輪查證結果一致，判定佇列
（#1~48全數結案）維持實質已空。**設計新假設軸#49（日內／隔夜報酬
結構分解 Overnight vs Intraday Return Decomposition）**——第十一種
機制分類，完全不依賴外部regime訊號的結構性時段切分，跟`#19`（隔夜
美股方向預測台股報酬，已FAIL）機制不同（那條測跨市場方向外溢，這條
測台股自身隔夜段vs盤中段報酬結構），完整內容見`HYPOTHESIS_QUEUE.md`
新增章節。**同時查證發現一個必要前置工程問題**：`adjust.py::
adjusted_price_series()`只對`close`做除權息還原，`open`/`high`/`low`
維持原始未還原，若不先修正會在計算隔夜報酬時被除權息事件污染——已
記錄為下一輪第1關前的必要前置步驟。本輪依協定第1節「設計完就收工，
下一輪從新加的這條開始跑第1關」規定，未寫任何測試腳本、未跑任何
統計檢定，`is_holdout_consumed()`確認為`False`。`git status`確認
另有其他自動化來源留下的未提交檔案（`.github/workflows/audit.yml`、
`research/.live_watchlist.json`、`research/data_cache/`、`research/
deep_dive_f_us_low_vol_persistent_random_control.py`）已記錄、不
觸碰、不納入本次commit。

## 2026-09-06 22:53 hypothesis_queue排程接續 — 本輪為純落地/接手輪，
無新研究產出。取鎖時發現鎖檔陳舊（LOCK_STALE，pid 84872，30.2分鐘，
疑似上一輪失敗），本輪回收接手。工作目錄裡已有上一輪（pid 84872）
完整跑完但未commit的#48（董監質押比例）FAIL結案內容（`HYPOTHESIS_
QUEUE.md`/`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#178皆已就緒，
內容經覆核前後一致、`is_holdout_consumed()`確認為`False`），本輪
只做落地工作：驗證一致性後直接commit+push，未重跑或修改任何研究
邏輯。佇列狀態沿用上一輪結論：**#1~48全數結案，#5/#6/#8/#10仍卡
外部依賴，下一輪從設計#49開始**（本輪因鎖檔回收+落地確認已是一個
完整工作單位，未在同一輪內硬塞設計#49，避免倉促）。git狀態確認
另有其他自動化來源留下的未提交檔案（`.github/workflows/audit.yml`、
`research/.live_watchlist.json`、`research/data_cache/`、`research/
deep_dive_f_us_low_vol_persistent_random_control.py`）已記錄、不
觸碰、不納入本次commit。

## 2026-09-06 hypothesis_queue排程接續 — #48（董監質押比例）第1關cheap
gate已跑完並結案：FAIL。取鎖時發現上一輪鎖檔陳舊（LOCK_STALE，91808，
30.3分鐘，疑似上一輪失敗），本輪回收接手。確認回補job
`20260906-220343-82ae`已完成（`irb130_pledge_combined.csv`
203,194筆），新增`irb130_pledge_gate.py`：`pledge_level`兩期皆正號
（與事前綁定負相關方向相反）、`pledge_mom`TRAIN幾近零訊號+VAL僅邊緣
顯著(p=0.0665)，判FAIL。**過程中發現並修正一個方法論公式bug**：
`day_trading_ratio_gate.py`/`institutional_concentration_gate.py`/
`avg_pairwise_correlation_gate.py`共用的單邊有號null percentile公式
`100*mean(shuffled>=real_corr)`（門檻`<=10.0`）用模擬資料證實方向
跟腳本自己註解相反（真實負相關越強percentile越接近100而非0），本
腳本改用`factor_ic.py`絕對值null慣例修正；已逐一覆核`#37`/`#42`/
`#43`三者判定不受影響（詳見`STRATEGY_GRAVEYARD.md`#48）。已更新
`HYPOTHESIS_QUEUE.md`（#48條目+排隊順序總結）、`TRIALS_LEDGER.md`
#178、`STRATEGY_GRAVEYARD.md`#48。因預算考量本輪未設計新假設軸#49，
下一輪從設計#49開始。`is_holdout_consumed()`全程False（僅讀既有
holdout-safe快取，未解鎖）。git狀態確認另有其他自動化來源留下的未
提交檔案（`.github/workflows/audit.yml`、`research/.live_watchlist.json`、
`research/data_cache/`、`research/deep_dive_f_us_low_vol_persistent_
random_control.py`）已記錄、不觸碰、不納入本次commit。

## 2026-09-06 21:58 — hypothesis_queue排程接續：#48（董監事及大股東股權
質押比例）完成(a)(b)(c)三點資料可行性查證，全數確認可行。用curl直接
測試找到真實端點`https://siis.twse.com.tw/publish/{sii|otc}/{yyy}
IRB130_{mm}.HTM`（純靜態HTML，經由MOPS互動頁`IRB130`表單action
`ajax_IRB130`的JS轉址目標反查得到，比照`#40`/`#41`鎖定真實端點手法），
歷史回溯確認涵蓋2015-2025（sii+otc兩市場皆測試2015-01/更近月份成功），
PIT時間差確認為正常約3週月頻揭露延遲（非回溯修正風險）。解析正確性
已驗證（Big5解碼、1101台泥質押比例%人工核對一致）。新增可重複執行
探測腳本`irb130_pledge_probe.py`，已更新`HYPOTHESIS_QUEUE.md`#48條目
狀態小節。下一輪直接進第1關cheap gate，不跳關，不需再查資料可行性。
本輪僅做唯讀HTTP GET測試（約8次請求、每次間隔1.5秒），未寫入任何
`data/`正式快取、未動`alpha-data`凍結區、`is_holdout_consumed()`維持
`False`。

## 2026-09-06 21:25 — hypothesis_queue排程接續：修正#47結案後排隊順序
總結未同步問題+設計新假設#48（董監事及大股東股權質押比例）。本輪
發現`HYPOTHESIS_QUEUE.md`「排隊順序總結」章節第46條末尾仍寫著
「#47現在排隊第一，尚未開始第1關」，但#47自身章節（下方新章節）
已寫明2026-09-06結案：FAIL（TWSE/TPEx免費openapi端點皆只回傳「當前
處置中」近期快照，無法支撐train/val分期，FinMind同類資料集為付費
層級，依快殺標準「資料不可及」判定，`TRIALS_LEDGER.md`#176/
`STRATEGY_GRAVEYARD.md`#47已存在），正是`HYPOTHESIS_QUEUE_PROTOCOL.md`
第1節警告過的「條目本身結案但排隊順序總結字樣沒同步」情況——已修正
對齊。修正後確認佇列#1~47全數結案，重新查證#5/#6/#8/#10四項外部
依賴仍卡`value_board_v2`回測未通過/題材動能榜與未來性濾網PIT引擎
地基未建（無新進展），設計出第十類機制假設#48（公司治理/代理成本
風險：董監事及大股東股權質押比例，跟已FAIL的`#30`融資使用率⑤類
差異是觸發者為內部人非散戶、跟`#41`內部人持股轉讓差異是測水位非
交易事件），WebFetch初步確認MOPS
`mopsov.twse.com.tw/mops/web/t05st03`存在候選彙總表端點
IRB130/IRB180，但SPA動態渲染無法直接解析出實際查詢API路徑，
**下一輪需先確認確切端點/參數/歷史回溯深度**才能進第1關cheap gate。
本輪本身無新測試判定，只做地基設計+文件對齊，`is_holdout_consumed()`
本輪開工/收工前皆為`False`。

## 2026-09-06 21:14 — hypothesis_queue排程接續（LOCK_STALE回收，上一輪
crash未提交）：取鎖時鎖檔顯示`LOCK_STALE (held by 87920, 29.9 min old)`。
`git status`檢查發現上一輪（見下方2026-09-06 20:38心跳條目）已經完整
做完#46第1關cheap gate執行、FAIL判定、`STRATEGY_GRAVEYARD.md`/
`HYPOTHESIS_QUEUE.md`文件更新、設計新假設#47（處置股解除後價格反轉），
但在commit前中斷未釋放鎖，`research/HYPOTHESIS_QUEUE.md`/
`research/MARATHON_LOG.md`/`research/STRATEGY_GRAVEYARD.md`/
`research/factors.py`四份檔案與`build_twse_listing_dates.py`/
`factor_ic_ipo_listing_age.py`兩支新腳本全部留在未提交狀態；同時
`TRIALS_LEDGER.md`#175已被同機器另一條US軌馬拉松的commit（3dc3554）
意外一併帶走提交（該軌`git add -A`掃到本軌未提交檔案），故該檔案
本輪`git status`已顯示乾淨。本輪逐一核對四份未提交文件內容前後一致、
`_listing_age_days()`bug修復記錄清楚、`排隊順序總結`章節已同步標記
#46已結案/#47排隊第一，未發現需要修正的不一致，確認`is_holdout_consumed()`
為`False`、`data/twse_listing_dates.json`快取檔存在（1094檔，
sanity核對過）。**本輪判定：無需新增工作，只需完成上一輪漏掉的
commit+push這個收尾動作**（回收已完成的一個完整有界工作單位，
不在本輪額外開始#47第1關，依協定「一輪只做一個有界工作單位」原則，
下一輪從#47「資料可行性查證」段落(a)(b)(c)三點開始）。`git add`僅限定
上述六個確認屬於本軌的檔案，不動同時存在於working tree的
`.github/workflows/audit.yml`/`research/.live_watchlist.json`/
`research/data_cache/`/`research/deep_dive_f_us_low_vol_persistent_random_control.py`
（判斷為其他自動化來源留下的殘留，不觸碰、不納入本次commit）。

## 2026-09-06 20:38 — hypothesis_queue排程接續（LOCK_STALE回收，上一輪疑似
中途失敗未釋放鎖）：取鎖時鎖檔顯示`LOCK_STALE (held by 3188, 30.3 min
old)`，研判上一輪（見下方2026-09-06 20:05心跳條目）做完`factors.py`新增
`f_listing_age_days`因子與`factor_ic_ipo_listing_age.py`腳本後，在commit
前中斷未釋放鎖，`research/MARATHON_LOG.md`/`factors.py`兩份工作檔案留在
未提交狀態。本輪接續完成上一輪明列的「下一輪待辦」：執行
`python factor_ic_ipo_listing_age.py`跑完#46第1關cheap gate。首次執行
發現`_listing_age_days()`實作bug（`date`欄位str型別直接與`pd.Timestamp`
相減拋錯，159/300檔全數ERROR、n=0 dates），已定位修復（改用
`pd.to_datetime()`轉型），修復後重跑拿到乾淨結果：248/300檔有效，TRAIN
mean_ic=+0.0036/VAL mean_ic=-0.0029（符號不一致）、null percentile=
**13.4**（需>=90.0，且低於50，比隨機還差），依快殺標準「觀測層級就
無訊號」判**FAIL**，未進第2關以後，見`HYPOTHESIS_QUEUE.md`#46「最終
判定」段落、`STRATEGY_GRAVEYARD.md`#46、`TRIALS_LEDGER.md`#175。**佇列
#1~46全數結案**，已設計新假設軸#47（處置股解除後價格反轉
Post-Disposition-Stock Price Reversion，交易所監理干預類——第九種
機制分類，跟已測過的八種皆不同），TWSE官方`announcement/punish`端點
已用WebFetch初步確認回傳合法JSON（`Date`/`Code`/`ReasonsOfDisposition`/
`DispositionPeriod`/`DispositionMeasures`五個欄位），現在排隊第一，
尚未開始第1關，下一輪從「資料可行性查證」段落列出的(a)(b)(c)三點開始
（歷史回溯深度/TPEx對應端點/樣本規模）。`is_holdout_consumed()`本輪
開工/收工前皆為`False`。本輪本應無新產出但已完整結案一條假設+設計
一條新假設，屬有界工作單位正常收工，準備commit（含撿回上一輪未提交的
`factors.py`/本檔案上一則心跳）+push+釋放鎖。

## 2026-09-06 20:05 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
本輪工作單位：完成`#46`（新股上市長期弱勢）下一輪待辦第2/3點，未做第1點
（TWSE 383家下市公司原始上市日期查證，依假設已預留的彈性本輪直接跳過，
先做「現存公司子樣本」版本）。(a) 新增`build_twse_listing_dates.py`抓取
TWSE官方`t187ap03_L`端點，成功解析1094檔現存上市公司「上市日期」，sanity
核對1101(台泥)=19620209通過，存`research/data/twse_listing_dates.json`。
(b) 在`factors.py`新增因子`f_listing_age_days`（距官方上市日天數，事前
綁定方向為正、不取負號）+對應loader`_load_twse_listing_dates()`（lru_cache，
零額外FinMind呼叫），已接進`prepare_factors()`並手動import驗證可正常
運作（2330→19940905核對正確）。**刻意不用price_df第一筆日期當上市日
代理**——對2010年前上市的公司那個代理會被`START_DATE`截斷成假的常數值，
混入跟真實上市日無關的confound，這是本輪的方法論決策，見`factors.py`
docstring完整說明。(c) 新增`factor_ic_ipo_listing_age.py`（沿用
`factor_ic.py`既有cross-sectional IC框架，standalone bonferroni_n=1），
**本輪僅完成程式撰寫+import語法驗證，尚未實際執行跑第1關cheap gate**
（本輪USD預算即將用盡，依協定「一輪只做一個有界工作單位」原則收工，
不趕在預算見底前跑可能耗時的300檔抓取+因子計算）。**只覆蓋TWSE現存
上市公司**（範圍界定決策，TPEx下市清單本輪重新確認仍查無官方API，
延續上一輪結論），這是誠實揭露的局限，不是bug。`is_holdout_consumed()`
本輪開工/收工前皆為`False`（本輪未觸碰任何回測/holdout資料，純資料源
建置+因子定義）。本輪未產生新的PASS/FAIL判定，`TRIALS_LEDGER.md`/
`STRATEGY_GRAVEYARD.md`無新增條目。**下一輪待辦**：執行
`python factor_ic_ipo_listing_age.py`跑完第1關cheap gate三項判準
（幅度非零/train-val同號且方向為正/VAL贏過洗牌null），若CHEAP_PASS
再決定是否投入TWSE 383家下市公司原始上市日期查證（緩解存活者偏差）或
直接進第2關以後。本輪收工，準備commit+push+釋放鎖。

## 2026-09-06 19:25 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
本輪工作單位：完成`#46`（新股上市長期弱勢IPO Long-Run
Underperformance）地基查證(a)(b)(c)三點，未進第1關cheap gate（依
協定「先把地基做好，不用強求一次做完全部關卡」）。(a) TPEx對應端點
確認可行：`https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O`
（上櫃股票基本資料），欄位`DateOfListing`格式YYYYMMDD，實測回傳
合法JSON。(b) TWSE找到官方終止上市清單端點
`https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml`，
實測383筆（Code/Company/DelistingDate），可用於緩解TWSE端存活者
偏差，但此清單**沒有上市日期欄位**，下一輪需另外查證383家的原始
上市日期來源。依`搜尋紀律：三來源查證`鐵律查了TPEx swagger文件
關鍵字搜尋、Google搜尋、data.gov.tw資料集搜尋三個獨立管道，皆未
找到TPEx終止上櫃清單的官方API，記錄為現況不可及（非保證永久不
存在）。(c) 樣本規模粗估：TWSE+TPEx現存合計約1700~1800家量級，加
TWSE下市383家，總量約2000筆上下，遠超cheap gate統計檢定力需求。
**範圍界定決策**：下一輪cheap gate先只做TWSE單一交易所（依假設
定義本身預留的彈性），TPEx留待有初步訊號後再擴充。零新增批次
API呼叫（本輪僅少量WebFetch驗證端點存在性與欄位格式，未批次抓取
全市場清單）。`is_holdout_consumed()`本輪開工/收工前皆為`False`
（本輪未接觸任何回測資料，純資料源可行性查證）。本輪未產生新的
PASS/FAIL判定，`TRIALS_LEDGER.md`/`STRATEGY_GRAVEYARD.md`無新增
條目。完整見`HYPOTHESIS_QUEUE.md` #46條目「2026-09-06 hypothesis_
queue排程接續（本輪，地基查證(a)(b)(c)完成）」新增段落。下一輪
待辦已列在該段落最後，從查證下市公司原始上市日期來源開始，不跳關
進cheap gate。本輪收工，準備commit+push+釋放鎖。

## 2026-09-06 18:57 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
發現`HYPOTHESIS_QUEUE.md`「排隊順序總結」章節與#44/#45自身條目內容
不同步（#44自身「狀態」段落停留在「本輪新增，尚未開始第1關」，但
「排隊順序總結」跟`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#164都
早已記錄#44最終判定FAIL——資料不可及，官方唯一免費合規管道無「當時
發布版」燈號欄位，官方查詢系統403、Wayback快照不含逐月分數，依快殺
標準判死），依`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節指示「先把不一致
修正掉」，已在#44自身條目補上最終判定段落，跟其他三處記錄對齊。
確認#43/#44/#45三條全數已結案，佇列實質已空。重新查證`BACKLOG.md`
`value_board_v2`仍`回測未通過`，#5/#6/#8/#10四項外部依賴仍未解鎖。
依協定第1節設計新假設軸**#46（新股上市長期弱勢IPO Long-Run
Underperformance）**——第八種機制分類，源自承銷定價偏樂觀+初期
情緒消退的**被動**價格衰減，跟`#40`買回股份/`#41`內部人轉讓這類
管理層**主動**決策事件經濟機制不同，也跟`#39`（指數編製方調整，
已因資料不可及FAIL）不同（那條測指數層級被動資金流，這條測個股
自身上市後價格路徑）。已用WebFetch初步確認TWSE官方openapi端點
`t187ap03_L`（上市公司基本資料）含`上市日期`欄位（格式YYYYMMDD，
範例：台泥1101→19620209），零金鑰、免費、可複用既有`fetch.py`
節流模式。尚未查證TPEx對應端點、是否含下市公司清單（存活者偏差
緩解）、樣本規模量級，下一輪從這三點開始，未跳關進cheap gate。
`is_holdout_consumed()`本輪開工/收工前皆確認`False`。零新增API呼叫
（本輪只做一次WebFetch驗證欄位存在，未批次抓取）。完整見
`HYPOTHESIS_QUEUE.md` #44最終判定段落＋#46新章節＋排隊順序總結。
本輪未新增TRIALS_LEDGER/STRATEGY_GRAVEYARD條目（#44已有#164、#46
尚未有測試結果可記錄）。本輪收工，準備commit+push+釋放鎖。

## 2026-09-06 18:24 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
完成#45「下一輪待辦(a)」——排除TSM對照重跑（僅UMC+CHT+ASX三檔pooled）。
新增`adr_premium_gate_ex_tsm.py`（複用`adr_premium_gate.py`既有
`build_panel()`/`_split()`/`evaluate()`，不重寫邏輯）。**結果決定性**：
TRAIN排除TSM pooled n=5558 r=**-0.0364**(p=0.0066)，VAL排除TSM pooled
n=2853 r=**+0.1094**(p=0.0000)——**train/val符號直接翻轉**，第2項判準
（同號）決定性未過，即使VAL單獨仍贏過null(percentile=100.0)也不放行
（同`#42`/`#43`「事前綁定判準不因單項顯著就通融」同一把尺）。逐檔拆解：
UMC(TRAIN-0.0923/VAL+0.0221不顯著)、CHT(TRAIN+0.2732/VAL-0.0157方向
反轉不顯著)、ASX(TRAIN+0.0898/VAL+0.1114兩期皆顯著同號，唯一穩定的
一檔)。證實#45「下一輪待辦(c)」預先訂的判死條件成立：排除TSM後訊號
不穩定，**判定訊號集中在單一巨型股（TSM），外部效度未證明**，依快殺
標準「觀測層級就無訊號」（ex-TSM panel層級）對#45整體最終判**FAIL**，
不進第2關以後、不查證(b)UMC/CHT 2006-2010比率變更公告（budget不值得
投入去擴大一個已經決定性判死的樣本）。已更新`HYPOTHESIS_QUEUE.md` #45
條目「最終判定」+排隊順序總結、`TRIALS_LEDGER.md`#169、
`STRATEGY_GRAVEYARD.md`。重新查證`BACKLOG.md`確認`value_board_v2`仍
`回測未通過`、題材動能榜/未來性濾網仍卡PIT引擎，#5/#6/#8/#10仍未解鎖
（無新進展）。`is_holdout_consumed()`開工/收工前皆確認`False`。零新增
API呼叫（複用既有`data/adr_premium_aligned.csv`）。**佇列#1~45全數
結案**，本輪因預算考量優先確保#45完整記錄與收斂，未倉促設計新假設軸
#46，下一輪從設計#46開始，不空轉。本輪收工，準備commit+push+釋放鎖。

## 2026-09-06 17:55 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
接續#45（ADR溢價收斂），完成上一輪地基建置後的第1關cheap gate。新增
`adr_premium_gate.py`：訊號=premium原始水位（比照#45事前寫死的定義，
非本輪重選）、target=本地股forward M=20日報酬、N=4小樣本改用「逐標的
內部時序洗牌」null（每檔股票各自獨立打散自己的premium時序，保留自己
forward return時序，避免跨標的混洗污染）。結果：TRAIN pooled n=9260
r=+0.0640(p=0.0000)null percentile=100.0、VAL pooled n=3804
r=+0.1242(p=0.0000)null percentile=100.0，三項判準（幅度非零/同號/
贏過null>=90.0）皆過，方向符合事前預期。**判定：CHEAP_PASS**。但額外
逐檔拆解揭露重要異質性——VAL期只有TSM/ASX顯著同號，UMC/CHT兩者VAL期
皆不顯著、CHT方向反轉，證實#45原先揭露的TSM主導風險確實存在，訊號未
證明在四檔標的上普遍成立。已更新`HYPOTHESIS_QUEUE.md` #45條目+排隊
順序總結、`TRIALS_LEDGER.md`#168。`is_holdout_consumed()`開工/收工前
皆確認`False`。仍未最終結案（僅第1關），現在排隊第一，下一輪待辦：
排除TSM對照重跑（僅UMC+CHT+ASX），檢驗訊號是否幾乎完全消失，再決定
進第2關或提早收斂判死。本輪收工，準備commit+push+釋放鎖。

## 2026-09-06 17:31 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
延續#45（ADR溢價收斂）地基建置：(1)用SEC EDGAR官方FY2006 20-F逐字確認
CHT比率1ADS=10股（"each of which represents ten of our common shares"）。
(2)新增`adr_premium_assembly.py`完成PIT對齊資料組裝——merge_asof
backward+allow_exact_matches=False避免美股ADR時區領先造成的未來函數，
FX用spot_sell同日對齊。**意外發現重大異常並已修正**：初版用UMC/CHT
現行比率(5:1/10:1)貫穿2006年至今算出的premium，在2006~2010年持續偏高
（UMC年均34~54%、CHT年均15~37%），2010~2011之交驟降到趨近0%並穩定至今，
型態跟全程穩定的TSM(2~8%)明顯不同；WebSearch查到UMC存管契約日期為
"October 21, 2009"，暗示比率極可能在該時點附近變更過，CHT同時間出現
幾乎相同斷點並非巧合。保守處置：UMC/CHT起始日改為2011-01-01（排除有
疑慮的2006-2010），TSM/ASX不變，重跑後四檔premium量級皆合理（TSM
mean+5.69%、UMC+0.08%、CHT+0.05%、ASX+2.30%，皆遠低於50%量級檢查
門檻）。已輸出`data/adr_premium_aligned.csv`(13144列)。**#45下一輪待辦**：
(1)完成PIT對齊已達成，(2)下一步進第1關cheap gate（時序相關性或事件式
統計檢定，須先決定用premium連續值或收斂速度當訊號）；若未來需要UMC/CHT
2006-2010歷史，須先查到官方比率變更公告與確切生效日期，本輪未深入（時間
/預算考量），現在排隊第一，未結案。

## 2026-09-06 16:55 — hypothesis_queue排程接續（正常取鎖LOCK_ACQUIRED）：
延續上一輪新增的#45（ADR溢價收斂）地基查證，完成(a)+部分(b)：新增
`adr_convergence_probe.py`確認FinMind `USStockPrice`實際收錄
TSM/UMC/CHT/ASX四檔且資料完整無缺口；換股比率查證意外發現一項重大
結構性風險——ASX（日月光投控）2018年因合併矽品(SPIL)成立控股公司
（1股ASE換0.5股新控股公司股份，新ADR比率2:1），用探查腳本實測
FinMind的ASX價格序列在2018-04-17→04-18（-18.9%）與2018-05-01→05-02
（-10.7%）出現兩次跳空，時點吻合合併生效期，確認這個ticker橫跨
2311（日月光半導體工業）與3711（日月光投控）兩個不同法人實體，
後續資料組裝必須明確切分、不能縫合成單一連續序列。TSM/UMC比率有
中等信賴度網路二手佐證（皆約5:1、未查到變動記錄），CHT具體比率
仍未查到官方數字。#45仍未結案、未進第1關cheap gate，下一輪待辦
（SEC EDGAR查CHT F-6、定案ASX斷點處理方案、寫PIT對齊資料組裝
腳本）已寫入`HYPOTHESIS_QUEUE.md`#45條目，現在排隊第一。

## 2026-09-06 16:26 — hypothesis_queue排程接續（取鎖LOCK_STALE(held by
68460, 29.9 min old)-recovering，上一輪疑似中斷但`git status`乾淨、
未留下未commit變更，判斷是取得鎖後尚未動作就中斷）：讀完
`HYPOTHESIS_QUEUE_PROTOCOL.md`+`CONSTITUTION.md`+`CLAUDE.md`+
`git pull`（已是最新）後確認佇列#1~44全數結案（#44已於上一輪判定
FAIL），依協定第1節「佇列已空」流程設計**新假設軸#45：存託憑證
（ADR）溢價/折價收斂**——本佇列第七種經濟機制分類（跨市場「同一
資產法則單一價格」套利收斂，非①方向性選股/②timing overlay/
③portfolio construction/④配對交易均值回歸/⑤強制平倉賣壓/⑥公司
行動事件驅動），跟已FAIL的`#16`配對交易（無結構性收斂錨）、`#19`
跨市場美股隔夜外溢（測大盤傳導非個股價位收斂）皆有明確機制區隔。
資料可行性初步查證確認可複用既有基礎設施（`USStockPrice`美股資料
loader、`#32`已驗證的USD/TWD匯率管線），唯一待查證是各檔ADR換股
比率是否曾變動；已誠實揭露三項限制（樣本數僅4~6檔、台積電權重
極高需拆分對照、既有引擎不支援放空故本輪先聚焦溢價半邊）。完整
內容已寫入`HYPOTHESIS_QUEUE.md`新章節#45（含經濟理由/具體假設定義/
PIT時序對齊要求/下檔保護要求）並同步更新「排隊順序總結」章節。
本輪僅完成假設設計，尚未查證FinMind是否收錄TSM/UMC/CHT/ASX、
尚未確認換股比率、未撰寫任何腳本，下一輪從三點資料查證開始，不
跳關進cheap gate。`is_holdout_consumed()`確認為`False`。commit+push
後正常收工並釋放鎖。

## 2026-09-06 15:58 — hypothesis_queue排程：#44景氣對策信號資料可行性查證即死（FAIL，資料不可及/回溯修正污染無法規避，未進第1關），設計#45留待下一輪 — 佇列#1~44全數結案

## 2026-09-06T15:25（台北時間，hypothesis_queue排程接續，取鎖
LOCK_STALE(held by 76668, 150.0 min old)-recovering，上一輪疑似崩潰
中斷但未留下任何未commit變更，`git status`乾淨，判斷上一輪在取得鎖後、
還沒開始寫檔案前就中斷）：讀完`HYPOTHESIS_QUEUE_PROTOCOL.md`+
`CONSTITUTION.md`+`CLAUDE.md`後`git pull`（已是最新），確認佇列#1~43
全數結案（上一次成功心跳12:28已完成#43並正常收工），依協定第1節
「佇列已空」流程設計新假設軸**#44：景氣對策信號燈號（NDC Business
Cycle Composite Signal）**——本佇列第一次完全不用市場價格衍生資料，
改用國家發展委員會官方總體景氣綜合指標，是第六種資料建構維度（前
`#43`已歸納前五種）。WebSearch+WebFetch確認`data.gov.tw/dataset/6099`
免費ZIP下載、涵蓋多年歷史、無需API金鑰，但明確標註兩個須優先排除的
方法論陷阱：(1)官方每月回溯修正歷史指標數值，直接用「最終版」數字
回測有look-ahead風險；(2)綜合分數9項構成項目之一就是股價指數本身，
訊號與待預測目標變數存在結構性內生關聯，須設計「排除股價指數重新
合成」的對照測試才能宣稱新增資訊。完整經濟理由+具體假設定義+資料
可行性查證+下檔保護要求已寫入`HYPOTHESIS_QUEUE.md`新章節#44，並同步
更新「排隊順序總結」章節。本輪僅完成假設設計，尚未下載實際ZIP檔案、
未開始撰寫`ndc_business_cycle_gate.py`，下一輪從下載確認資料細節開始，
不跳關進cheap gate。`is_holdout_consumed()`確認`False`。commit+push
後正常收工並釋放鎖。

## 2026-09-06T12:28（台北時間，hypothesis_queue排程接續，取鎖
LOCK_STALE(held by 76852, 29.9 min old)-recovering，上一輪（11:27
那筆）疑似又中斷了——這是同一個#43工作單位連續第二次遇到陳舊鎖，
但比對內容發現上一輪其實**已經把最重的工作做完**：`institutional_
concentration_gate.py`已跑完並產出`data/institutional_concentration_
{hhi,top10}_aligned.csv`（gitignored，共3012筆），`TRIALS_LEDGER.md`
#161跟`STRATEGY_GRAVEYARD.md`「#43」章節也都已經寫好完整FAIL記錄，
只差`HYPOTHESIS_QUEUE.md`本身（#43條目「狀態」小節＋「排隊順序總結」
章節）還沒同步更新、以及commit+push+釋放鎖——本輪重新執行一次腳本
（用既有快取，數字跟`TRIALS_LEDGER.md`#161完全一致，確認deterministic）
驗證判定，接著補完`HYPOTHESIS_QUEUE.md`兩處同步（比照協定第1節「先
把不一致修正掉」）。**判定：FAIL**——HHI/Top10兩指標TRAIN/VAL皆為
顯著正相關（HHI兩期p<0.001），跟事前綁定的負相關方向相反，依「事前
綁定方向不換」鐵律判死，跟`#42`同一種死法。`is_holdout_consumed()`
確認`False`。佇列#1~43全數結案，本輪因預算考量不再倉促設計#44，
下一輪從設計新假設軸開始。完整見`HYPOTHESIS_QUEUE.md`#43、
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#161。commit+push後正常
收工並釋放鎖。

## 2026-09-06T11:27（台北時間，hypothesis_queue排程接續，取鎖
LOCK_STALE(held by 68532, 30.0 min old)-recovering，上一輪疑似
失敗中斷，設計#43並修正#42記錄不一致）：讀完
`HYPOTHESIS_QUEUE_PROTOCOL.md`+`CONSTITUTION.md`後`git pull`（已是
最新）+`git status`，發現4個非本輪產生的未commit變更
（`data/rate_limit_state.json`/`HYPOTHESIS_QUEUE.md`/
`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`）——比對內容確認這些
正是上一輪`hypothesis_queue`排程已完成`#42`第1關cheap gate判定
（FAIL，見`TRIALS_LEDGER.md`#157）但**沒能commit+push+釋放鎖就
中斷**留下的成果，非其他自動化來源（另有一個確實不相關的未追蹤
檔案`.github/workflows/audit.yml`，上上輪已確認非本軌產生，本輪
維持不觸碰）。取鎖時果然回傳`LOCK_STALE`（30分鐘陳舊，pid 68532），
確認判斷正確。**先修正一處不一致**：`HYPOTHESIS_QUEUE.md`「排隊
順序總結」章節#42條目文字仍停留在「尚未開始第1關」，跟章節內文
`#42`已寫好的「最終判定：FAIL」不同步——依協定「發現不一致先修正
掉」，已更新該條目為FAIL摘要並同步收斂佇列狀態文字。**接著依協定
第1節「佇列已空」流程**：#1~42全數結案、#5/#6/#8/#10重新查證仍未
解鎖，回顧四類已死regime/籌碼假設資料建構維度（①單一外部序列
水位、②個股自身持續性、③報酬相關結構`#42`、④散戶槓桿），設計
出第五種資料維度的第43條假設：**三大法人買賣超集中度（資金流
橫斷面分布集中度，非價格廣度非報酬相關性非個股自身歷史）當市場
領漲廣度regime訊號**，零新資料源（複用`#13`/`#41`已回補的三大
法人日頻買賣超快取），已寫入新章節（經濟理由+具體假設定義+已知
相關背景+資料可行性+下檔保護要求）並同步「排隊順序總結」新增#43
條目。本輪未寫測試程式碼、未動`TRIALS_LEDGER.md`（無新PASS/FAIL
判定，符合協定「這輪工作單位到此為止」）。`is_holdout_consumed()`
未查（本輪未做任何資料抓取）。下一輪從#43第1關cheap gate開始，
不跳關。commit（含補上一輪遺留成果+本輪新增#43設計）+push+釋放鎖
後收工。

## 2026-09-06T10:27（台北時間，hypothesis_queue排程接續，取鎖乾淨
LOCK_ACQUIRED，佇列#1~41全數結案確認、設計新假設軸#42）：讀完
`HYPOTHESIS_QUEUE_PROTOCOL.md`+`CONSTITUTION.md`+`git pull/status`
（確認`.github/workflows/audit.yml`非本輪產生，不觸碰）後取鎖成功。
依協定第1節「佇列已空」流程確認`HYPOTHESIS_QUEUE.md`「排隊順序總結」
最新狀態（#1~41全數PASS/FAIL結案，剩餘#5/#6/#8/#10仍卡外部依賴——
重新查證`BACKLOG.md`第1311/1164行`題材動能榜／未來性濾網：紙上交易中`
/`value_board_v2：回測未通過`，跟上輪查證結果一致，無新進展）。回顧
已死11條timing/regime類假設（#10/#15/#26/#28/#30/#31/#32/#33/#34/
#35/#37）共同模式——清一色用「單一外部序列水位/成長率」當訊號——
設計出經濟機制真正不同的第42條假設：**個股間平均成對相關係數
（Average Pairwise Correlation）當系統性風險regime訊號**，看的是
整個股票宇宙內部的橫斷面共同運動結構，不是任何單一序列的水位，且
零新資料源需求（複用既有300檔快取宇宙，跟`f_bab`/`f_idio_vol`同源
的rolling covariance計算路徑）。已寫入`HYPOTHESIS_QUEUE.md`新章節
（經濟理由+具體假設定義+已知相關背景+資料可行性+下檔保護要求）+
同步「排隊順序總結」章節新增#42條目，同時順手修正#41條目結尾一句
已過時的「下一輪從設計#42開始」提示字（現在#42已設計完成，改成
「現在排隊第一，尚未開始第1關」）。本輪未寫測試程式碼、未動
`TRIALS_LEDGER.md`/`STRATEGY_GRAVEYARD.md`（無PASS/FAIL判定，符合
協定「這輪工作單位到此為止」）。`is_holdout_consumed()`未查（本輪
未做任何資料抓取），下一輪從#42第1關cheap gate開始，不跳關。
commit+push+釋放鎖後收工。

## 2026-09-06T14:10（台北時間，hypothesis_queue排程接續，取鎖乾淨
LOCK_ACQUIRED，#41第六輪擴大pilot樣本35→45檔並結案FAIL）：
`backfill_insider_holdings.py` PILOT_STOCK_COUNT 35→45，新增200筆
請求全數成功（含快取共900筆，ok=590/65.6% empty=310 error=0）。重跑
pilot IC：panel擴大為N=560/30檔，r=-0.0089（**符號翻轉為負，前三輪
皆正**）、p=0.8331、null percentile=47.5（**貼在50附近，四輪最差**）。
四輪序列(r/percentile)：+0.0710/90.5 → +0.0775/94.0 → +0.0417/79.0 →
-0.0089/47.5，決定性轉為無訊號，依「觀測層級就無訊號」快殺標準判
**FAIL**，不投入需數千筆額外請求才能達到的正式300檔+VAL期cheap
gate規模。已更新`HYPOTHESIS_QUEUE.md`#41最終判定+排隊順序總結、
`STRATEGY_GRAVEYARD.md`新增條目、`TRIALS_LEDGER.md`#155。佇列#1~41
全數結案，剩餘#5/#6/#8/#10仍卡外部依賴，本輪因預算考量未設計新假設
軸#42，下一輪從設計#42開始。`is_holdout_consumed()`開工/收工前皆
確認False，全程只查TRAIN期資料。準備commit+push+釋放鎖。

## 2026-09-06T09:34（台北時間，hypothesis_queue排程接續，取鎖乾淨
LOCK_ACQUIRED，接續#41第五輪，擴大pilot樣本25→35檔，發現趨勢逆轉）：
延續上一輪的prefix-consistent抽樣（`sample_universe_ids(60,seed)`前60
候選篩4位數字代碼取前35檔），跑`backfill_insider_holdings.py`（前景
9分鐘逾時後自動轉背景，等待約4分鐘後完成），新增200筆請求（加上300筆
快取命中的舊組合共700筆）全數成功無error（`ok=470(67.1%) empty=230
error=0`）。重跑`insider_holdings_pilot_ic.py`：panel擴大為**N=446筆/
24檔股票**，真實Spearman IC **r=+0.0417**（方向仍為正，三輪皆同號）、
**p=0.3799**（比上一輪0.1525明顯轉差，甚至比上上輪0.2858更不顯著）、
洗牌null percentile=**79.0**（比上一輪94.0明顯下滑）。**誠實記錄並
修正上一輪判斷**：上一輪只用兩個資料點（N=228→342）就framed成「改善
趨勢」，本輪第三個資料點（N=342→446）顯著性反而惡化，三點序列
（0.2858→0.1525→0.3799、90.5→94.0→79.0）呈非單調震盪，更像小樣本
雜訊而非訊號隨樣本數穩定浮現的收斂——這是上一輪過早下結論，本輪
已在`HYPOTHESIS_QUEUE.md` #41條目與排隊順序總結同步修正這個框架，
不再宣稱「改善趨勢」。仍非正式cheap gate判準（`factor_ic.py`標準
SAMPLE_SIZE=300/N_SHUFFLES=1000），依協定不用這個非正式檢查宣稱
PASS/FAIL，未動`TRIALS_LEDGER.md`。`is_holdout_consumed()`確認仍為
False。下一輪選項：(a)繼續分批擴大樣本觀察震盪是否隨樣本數收斂，
或(b)規劃分多輪擴到`factor_ic.py`標準300檔規模做正式整合（這是跟
其他因子相同的既有標準規模，不構成協定stop condition(a)項——該項
指超出既有300/1000標準之上的規模）。commit+push後收工，釋放鎖。

## 2026-09-06T09:10（台北時間，hypothesis_queue排程接續，取鎖乾淨
LOCK_ACQUIRED，接續#41第四輪，擴大pilot樣本）：延續上一輪判定
（`PILOT_STOCK_COUNT`從15擴大到25，`PILOT_SAMPLE_SIZE`維持60不變，
先實測確認`random.Random(seed).sample()`在不同size下對這個母體是
prefix-consistent的——`sample_universe_ids(60,seed)==sample_universe_ids(150,seed)[:60]`
成立，確保新增的10檔股票接續在原本15檔之後、不是重抽整組新樣本）。
受限於per-company查詢+headless單次Bash呼叫10分鐘上限（一次擴到接近
factor_ic.py標準300檔規模需6000筆請求、以1.8秒節流估算超過3小時，
遠超單輪可行時間），本輪只分批擴大10檔，用`run_in_background`跑
`backfill_insider_holdings.py`（前景10分鐘逾時後自動轉背景，等待
約5分鐘後完成），**新增500筆請求（含300筆快取命中的舊組合+200筆
新組合）全數成功無error**（`ok=360(72.0%) empty=140 error=0`）。
重跑`insider_holdings_pilot_ic.py`：panel擴大為**N=342筆/18檔股票**
（原25檔中部分股票`adjusted_price_series`載入失敗被跳過），真實
Spearman IC **r=+0.0775**（方向仍為正、跟上一輪+0.0710同號一致）、
**p=0.1525**（比上一輪0.2858顯著改善）、洗牌null percentile=
**94.0**（比上一輪90.5略升，N_SHUFFLES=200整panel打散，非正式判準）。
**判定：樣本擴大後方向一致性與顯著性皆呈改善趨勢（p值下降、
percentile上升），支持「這不是雜訊」的假設，但p=0.1525仍未過常規
p<0.05門檻，樣本規模（18檔/342筆）距離factor_ic.py標準300檔仍有
數量級差距，依協定「一輪只做一個有界工作單位」原則不強行一次擴到
300檔，不倉促宣稱CHEAP_PASS或FAIL**。`is_holdout_consumed()`確認
仍為False。已同步`HYPOTHESIS_QUEUE.md` #41條目「狀態更新（第四輪）」
小節+排隊順序總結，未動`TRIALS_LEDGER.md`（尚無正式PASS/FAIL/
CHEAP_PASS判定可記）。下一輪：延續同一套prefix-consistent抽樣邏輯
繼續分批擴大樣本（例如25→50，視單輪10分鐘時間預算而定），持續觀察
p值/percentile趨勢是否收斂到顯著或發散回不顯著。commit+push後收工，
釋放鎖。

## 2026-09-06T08:49（hypothesis_queue排程接續，取鎖乾淨LOCK_ACQUIRED，
接續#41地基建置本輪）：依上一輪查證結果，設計節流後的中小樣本回補腳本
——新增`mops_insider_holdings_client.py`（per-company per-month查詢+
per筆parquet快取，只取「全體董監持股合計」單一彙總數字，避免逐筆
董監事/經理人明細列數量在公司間變動造成解析不穩）+
`backfill_insider_holdings.py`（15檔股票x20季度=300筆請求的pilot樣本
回補，`TYPEK=sii`only、只查TRAIN期105Q1~109Q4即西元2016~2020）。
實測回補**300筆請求全數成功無error**（`ok=240(80.0%) empty=60
error=0`，empty多半是股票尚未上市/該季無申報資料，非連線失敗）。
接著寫`insider_holdings_pilot_ic.py`做**非正式**的訊號存在性pilot
檢查（明確標註非正式第1關cheap gate，只是決定值不值得投入全量整合
工程成本的粗篩）：panel N=228筆觀測/12檔股票，季度董監持股合計變動率
vs下一季報酬，Spearman IC r=+0.0710（事前綁定方向為正，符合），
**p=0.2858不顯著**，整panel洗牌null percentile=90.5（表面壓線過90.0
門檻但p值不顯著+樣本量遠小於正式300檔標準，不能當真的第1關判準）。
**判定：訊號方向正確、有初步跡象但目前樣本量太小無法下定論**——值得
投入下一輪把樣本擴大到接近標準300檔規模+正式整合進`factor_ic.py`
`run_ic_test()`機制（SAMPLE_SIZE/N_SHUFFLES/bonferroni），但本輪不
倉促用這個12檔pilot結果宣稱CHEAP_PASS或FAIL，避免用不夠格的證據
做決定性判定（`CONSTITUTION.md`「事前綁定通過標準」精神——正式判準
就該用正式規模的測試才算數）。`is_holdout_consumed()`确认仍為False。
已同步`HYPOTHESIS_QUEUE.md` #41條目+排隊順序總結，未動`TRIALS_LEDGER.md`
（尚無正式PASS/FAIL/CHEAP_PASS判定可記）。下一輪：擴大樣本至接近
factor_ic.py標準規模（可能需要更長回補時間，分批進行）後跑正式
`factor_ic.py`整合版cheap gate。commit+push後收工，釋放鎖。

## 2026-09-06T07:57（hypothesis_queue排程接續，取鎖乾淨LOCK_ACQUIRED，
本輪有網路搜尋工具，接續上一輪#41「地基查證卡住待有搜尋工具session」）：
用`WebSearch`查到上一輪猜錯的MOPS功能代碼正解——`stapap1`（個股董監
持股明細，POST `ajax_stapap1`，參數year/month/co_id/TYPEK）與
`stapap1_all`（產業別公司清單，POST `ajax_stapap1_all`）。用`requests`
實測確認`ajax_stapap1`**接受任意歷史民國年月**（用2330/1101/2317三檔
+1.5秒間隔測試皆成功），**推翻上一輪「工具限制未解」的中繼判斷**——
這條**不是**資料不可及（跟#38/#39不同死法），但代價是per-company
逐檔查詢、無法像#40買回股份一次拿全市場，全歷史回補（約1700檔×多年
×12個月）請求量體大，需要下一輪先設計節流/取樣頻率（比照#40先小樣本
驗第1關訊號再決定是否投入全量回補）。新增`mops_insider_holdings_
probe.py`記錄確認過程與可重複呼叫的函式，已同步`HYPOTHESIS_QUEUE.md`
#41條目+排隊順序總結。本輪未寫因子/測試程式碼、未動`TRIALS_LEDGER.md`/
`STRATEGY_GRAVEYARD.md`（尚未進第1關，無PASS/FAIL判定）、未產生任何
`data/`快取檔案。`is_holdout_consumed()`開工/收工前皆確認`False`。
`git status`確認`.github/workflows/audit.yml`（非本輪產生，前兩輪心跳
已記錄過）依然未觸碰、未納入本輪commit。下一輪從「設計節流後的個股
逐檔回補腳本」開始，不跳關。

## 2026-09-06T07:28（hypothesis_queue排程接續，取鎖乾淨LOCK_ACQUIRED）：
發現`HYPOTHESIS_QUEUE.md`內文不一致——#40詳細條目章節（第3928行起）
還停在上一輪「地基完成、尚未執行完整回補」的舊狀態，但「排隊順序
總結」章節、`TRIALS_LEDGER.md`#150、`STRATEGY_GRAVEYARD.md`已經記錄
完整的最終判定（FAIL，unconditional版+執行率分組兩版皆未過VAL null
percentile 90.0門檻）——依協定第0節先修正這個不一致，補上#40詳細章節
的「最終判定」段落，三處現在同步一致。接著設計新假設軸#41：**內部人
（董監事/大股東/經理人）持股轉讓**（informed trading信號，跟已FAIL
的機構法人流向#3/#12/#13不同資訊含量假設，跟已FAIL的#40庫藏股公司
集體決策不同分析單位）。資料查證：TWSE openapi三個候選端點
（`t187ap11/12/13`）皆確認只有最新單一快照、無歷史查詢參數，跟#38
同一種死法；嘗試找MOPS互動查詢頁對應版本（仿照#40`t35sc09`模式），
猜測三個候選功能代碼（`t05st07`/`t34sc01`/`t108sb01`）皆連線被拒，
用已知可行的`t35sc09`同組headers重測仍正常200排除環境問題，確認是
這三個代碼本身猜錯，**沒有網路搜尋工具可查證正確代碼**，這是本輪
遇到的工具限制而非資料確定不可及。**不比照#38/#39直接判FAIL**——
只窮盡了一條路徑，MOPS互動頁路徑本輪未能證實可行也未能證實不可行，
如實登記為「地基查證卡住待下一輪/有搜尋工具的session接手」，完整
內容見`HYPOTHESIS_QUEUE.md`#41新章節。本輪為地基查證性質工作，非
新變更/非部署決策，依`CLAUDE.md`「已核准的自主挖礦馬拉松不受提案
先於執行約束」條款執行。`is_holdout_consumed()`開工/收工前皆確認
`False`。`git status`確認`.github/workflows/audit.yml`（非本輪產生，
上一輪心跳已記錄過）依然未觸碰、未納入本輪commit。

## 2026-09-06（hypothesis_queue排程接續，上一輪鎖檔陳舊(30分鐘)被回收，
#40最終結案：FAIL）：接續上一輪完成的MOPS資料回補地基，執行完整回補
（41個快取檔案，1727原始列去重後1824列），寫`buyback_car_gate.py`跑
第1關cheap gate（CAR事件研究：董事會決議日為事件日、N=20交易日
forward horizon、CAR=個股超額報酬vs TAIEX、隨機日期控制組N=200）。
抽樣100檔（母體725檔）、265筆可用事件：TRAIN mean_CAR=+4.00%
(p<0.0001)、VAL mean_CAR=+2.12%(p=0.078)，train/val同號但VAL null
percentile=84.5未過90.0門檻。依假設自己預先寫明的深挖計畫測執行率
分組（`buyback_car_gate_high_execution.py`，區分真實信心表態vs
cheap talk）：高執行率組VAL percentile=78.0(n=23)、低執行率組
85.0(n=27)，皆未過且高執行率組反而更低，排除cheap talk稀釋假說，
判定#40最終FAIL。已同步`HYPOTHESIS_QUEUE.md`#40狀態+排隊順序總結、
`STRATEGY_GRAVEYARD.md`新增段落、`TRIALS_LEDGER.md`#150。**佇列
#1~40全數結案，本輪因預算考量未設計新假設軸#41**（比照#37先例，
優先確保#40完整記錄），下一輪從設計#41開始。`is_holdout_consumed()`
開工/收工前皆確認`False`。git status確認`.github/workflows/audit.yml`
（非本輪產生）未觸碰、未納入commit。

## 2026-09-06 06:30（hypothesis_queue排程接續，#40地基完成）：接續上一輪
新增的#40（庫藏股買回公告效應）——寫`buyback_announcement_probe.py`
確認MOPS t35sc09可回溯至民國104年(2015)，過程發現表頭其實是兩列
colspan結構（資料實際20欄非表面18欄），簡易解析會誤判0列。已修正並
寫成正式模組`mops_buyback_client.py`（`_build_header()`展開colspan）
+可續跑回補腳本`backfill_buyback_announcement.py`（2015-01-01~VAL_END
逐半年窗口x sii/otc），實測`fetch_window`可正確回傳119列含核心欄位。
本輪僅測試性抓1個窗口驗證解析正確、未執行完整回補（預算考量），
已同步`HYPOTHESIS_QUEUE.md`#40條目狀態。下一輪先跑完整回補腳本，
再寫CAR事件研究檢定腳本，第1關cheap gate仍未過關，不跳關。

## 2026-09-06 05:58（hypothesis_queue排程接續第十三輪，上一輪鎖檔陳舊
(30.0分鐘)被回收，疑似上一輪失敗未產出）：確認佇列#1~39全數結案，
剩餘#5/#6/#8/#10重新查證仍卡外部依賴（value_board_v2仍回測未通過、
題材動能榜/未來性濾網仍紙上交易中），依協定第1節設計新假設軸#40
（庫藏股買回公告效應Share Buyback Announcement Effect，管理層信心
信號事件研究，跟前39條①方向性選股②timing overlay③portfolio
construction④配對交易⑤強制平倉風控機制分類皆不同的第六類：公司
行動事件驅動）。本輪已完成資料可行性查證並確認可行：公開資訊觀測站
（MOPS）t35sc09功能（上市公司買回自己公司股份彙總統計表）可用POST
查詢任意日期範圍，回傳含董事會決議日期（事件日）等完整欄位的HTML
表格，實測民國114/115年皆有資料。已更新HYPOTHESIS_QUEUE.md新增#40
完整條目（排隊順序總結+獨立詳細章節）。本輪未寫任何因子/測試程式碼、
未動TRIALS_LEDGER.md/STRATEGY_GRAVEYARD.md（無新PASS/FAIL判定）。
holdout未消耗（=False）。git status確認repo內非本輪產生的殘留檔案
（.github/workflows/audit.yml、畸形檔名暫存檔）未觸碰、未納入commit。
下一輪從第1關cheap gate開始，先寫buyback_announcement_probe.py確認
歷史回溯範圍，再寫正式回補腳本，不跳關。
## 2026-09-06（hypothesis_queue排程接續第十二輪，上一輪鎖檔陳舊
(149.8分鐘)被回收，疑似上一輪失敗未產出）：查證#39（0050/台灣50指數
成分股調整事件效應）資料可行性——掃描TWSE openapi全144端點+FinMind
dataset清單+data.gov.tw搜尋，皆無「歷史成分股名單+調整生效日期」
結構化API，跟#38同一種死法，依快殺標準「資料不可及」判**FAIL**，
未進第1關。同時修正「排隊順序總結」章節格式不一致（#38/#39原先擠在
#36段落文字裡沒有自己的編號bullet，已拆開對齊）。已更新
`HYPOTHESIS_QUEUE.md`#39條目+排隊順序總結、`TRIALS_LEDGER.md`#149、
`STRATEGY_GRAVEYARD.md`對應段落。新增`index_reconstitution_probe.py`
（可重複執行）。holdout未消耗（=False）。佇列#1~39全數結案，剩餘
#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`仍未解鎖），下一輪
需設計新假設軸#40，本輪因預算考量未倉促設計。`git status`確認repo內
仍有非本輪產生的殘留（`data/rate_limit_state.json`、
`.github/workflows/audit.yml`、帶亂碼檔名tmp檔、
`round366_deep_dive...log`），未觸碰、不納入本輪commit。

## 2026-09-06T02:28（hypothesis_queue排程接續第十一輪，上一輪鎖檔陳舊
(30.2分鐘)被回收，疑似上一輪失敗）：重新查證確認佇列#1~37全數結案、
#5/#6/#8/#10仍卡外部依賴（BACKLOG.md無新進展）未解鎖，設計新假設軸
#38（大戶籌碼集中度/股東持股分級表）。查證資料可行性：FinMind
免費層被拒（HTTP 400需付費會員），改查
TDCC集保結算所官方免費開放API()，
實測發現不支援date參數、永遠只回傳最新一週快照，無歷史PIT時間序列
可回測。依快殺標準「資料不可及」判#38 **FAIL**（未進第1關），移出
佇列。設計新假設軸#39（0050/台灣50指數成分股調整事件效應，被動指數
基金強制買賣壓力機制，本佇列第六種機制類別，跟前38條經濟機制皆不同），
已登記完整經濟理由+假設定義，資料可行性尚未查證，下一輪從查證開始。
已更新#38/#39條目+「排隊順序總結」+
#148+#38條目。holdout未消耗
（=False）。新增
（探查腳本，可重複執行）。

## 2026-09-06T02:04（hypothesis_queue排程接續第十輪，本輪取鎖乾淨
`LOCK_ACQUIRED`）：#37（全市場現股當沖比重）TWTASU逐日回補完成剩餘
121天，**累積2609/2609（100.0%），地基100%回補完成**。新增
`day_trading_ratio_gate.py`跑第1關cheap gate（訊號=當沖比重trailing
60日自身百分位排名，目標=未來20日TAIEX報酬，事前綁定方向為負）：
TRAIN corr=-0.0550(p=0.0396)percentile=98.5過關，**VAL
corr=-0.0042(p=0.8981)percentile=60.0遠未過**<=10.0門檻，訊號幾乎
完全消失，典型「TRAIN過擬合、VAL無訊號」形狀，依快殺標準判定
**FAIL**，不進第2關。已更新`HYPOTHESIS_QUEUE.md`#37條目+「排隊順序
總結」章節+`TRIALS_LEDGER.md`#146+`STRATEGY_GRAVEYARD.md`對應段落。
holdout未消耗（`is_holdout_consumed()`=False）。**佇列#1~37全數
結案，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新查證`BACKLOG.md`——B24
仍`回測未通過`、題材動能榜仍`紙上交易中`，未解鎖）**——本輪因時間/
預算考量，優先確保#37完整記錄，未在同輪倉促設計新假設軸#38，留給
下一輪處理，並提醒下一輪避開跟同機器`AlphaMarathon`FUT軌
`fut_cheap_gate.py`系列已測過的「三大法人期貨部位」類機制重複。
`git pull`確認乾淨，`git status`確認repo內仍有非本輪產生的殘留
（`data/rate_limit_state.json`、`.github/workflows/audit.yml`、一個
帶亂碼檔名的tmp檔、`round366_deep_dive...log`），未觸碰、不納入本輪
commit。

## 2026-09-06T01:43（hypothesis_queue排程接續第九輪，本輪取鎖乾淨
`LOCK_ACQUIRED`）：#37（全市場現股當沖比重）TWTASU逐日回補再接續一批：
`python backfill_day_trading_ratio.py --skip-market-volume --batch-size
250`，本輪嘗試250天、新完成250天（其中17天無交易/無資料），累積已
快取2488/2609（95.4% of全範圍工作日，2015-01-01~2024-12-31），FMTQIK
（分母）已100%回補不用重跑。checkpoint機制運作正常（逐日atomic寫入，
本輪從上一輪留下的2238天接續，未遺失進度，`data/raw_twse_day_trading`
實際檔案數2488與腳本回報一致），未觸及cheap gate（資料仍不完整），
holdout未消耗（`is_holdout_consumed()`=False）。已更新
`HYPOTHESIS_QUEUE.md`#37條目最新進度（含「排隊順序總結」章節同步
更新）。下一輪重跑同一指令即可自動從上次進度接續，估計還需1輪左右
批次即可回補完整TRAIN+VAL期（剩餘121天）。`git pull`確認乾淨，
`git status`確認repo內仍有非本輪產生的殘留（`data/rate_limit_
state.json`已修改、`index.html`已修改、三個`_tmp_*.mjs`未追蹤檔案、
一個路徑寫壞的暫存txt、一個round366深挖log未追蹤檔案），判斷屬於
三軌馬拉松或其他自動化留下，本輪不觸碰、不納入commit。此輪為單純
基礎設施回補批次、非新變更/非部署決策，依`CLAUDE.md`「已核准的自主
挖礦馬拉松不受提案先於執行約束」條款執行。

## 2026-09-06（hypothesis_queue排程接續第八輪，本輪取鎖`LOCK_STALE`
回收，發現上一輪疑似崩潰）：#37（全市場現股當沖比重）TWTASU逐日回補
再接續一批：`python backfill_day_trading_ratio.py --skip-market-volume
--batch-size 250`，本輪嘗試250天、新完成250天（其中19天無交易/無
資料），累積已快取2238/2609（85.8% of全範圍工作日，2015-01-01~
2024-12-31），FMTQIK（分母）已100%回補不用重跑。checkpoint機制運作
正常（逐日atomic寫入，本輪從上一輪留下的1988天接續，未遺失進度），
未觸及cheap gate（資料仍不完整），holdout未消耗
（`is_holdout_consumed()`=False）。已更新`HYPOTHESIS_QUEUE.md`#37
條目最新進度（含「排隊順序總結」章節同步更新），並修正上一筆心跳
（第七輪）因崩潰被截斷的段落，補上崩潰後實際進度領先記錄進度的
說明，不影響資料正確性。下一輪重跑同一指令即可自動從上次進度接續，
估計還需約2輪左右批次即可回補完整TRAIN+VAL期。`git pull`確認乾淨，
`git status`確認repo內仍有兩份非本輪產生的殘留（`data/rate_limit_
state.json`已修改、以及一個路徑寫壞的暫存txt與一個round366深挖log
未追蹤檔案），判斷屬於三軌馬拉松留下，本輪不觸碰、不納入commit。此輪
為單純基礎設施回補批次、非新變更/非部署決策，依`CLAUDE.md`「已核准
的自主挖礦馬拉松不受提案先於執行約束」條款執行。

## 2026-09-05T22:12（hypothesis_queue排程接續第七輪，本輪取鎖乾淨
`LOCK_ACQUIRED`）：#37（全市場現股當沖比重）TWTASU逐日回補再接續一批：
`python backfill_day_trading_ratio.py --skip-market-volume --batch-size
250`，本輪嘗試250天、新完成250天（其中17天無交易/無資料），累積已
快取1554/2609（59.6% of全範圍工作日，2015-01-01~2024-12-31），
FMTQIK（分母）已100%回補不用重跑。checkpoint機制運作正常（逐日
atomic寫入，本輪從上一輪留下的1304天接續，未遺失進度），未觸及cheap
gate（資料仍不完整），holdout未消耗（`is_holdout_consumed()`=False）。
已更新`HYPOTHESIS_QUEUE.md`#37條目最新進度（含「排隊順序總結」章節
同步更新）。下一輪重跑同一指令即可自動從上次進度接續，估計還需約4輪
左右批次才能回補完整TRAIN+VAL期。此輪為單純基礎設施回補批次、非新
變更/非部署決策，依`CLAUDE.md`「已核准的自主挖礦馬拉松不受提案先於
執行約束」條款執行。`git pull`確認乾淨（有兩個非本輪產生的殘留未追蹤
檔案`research/C:alphaalpha-appresearch_tmp_twse_check.txt`與
`research/round366_deep_dive_f_us_value_bm_leave_extreme_out.log`，
不觸碰、不納入本輪commit）。**本輪心跳原文在此處被截斷（本輪`git
push`成功，commit `5963b5b`，但process在寫完本句前異常終止，未執行到
釋放鎖檔步驟，導致鎖檔陳舊超過25分鐘）——2026-09-06第八輪已於上方
補記完整說明，此處保留原始截斷痕跡不重寫歷史，僅在此註明真相：第八輪
重新盤點本地快取檔案發現實際進度是1988/2609，領先本筆記錄的
1554/2609，判斷第七輪崩潰前backfill腳本本身已多跑過幾批未留下
心跳/commit記錄，資料進度未遺失（checkpoint逐日atomic寫入可獨立
驗證），只是敘事沒同步。**

## 2026-09-05T21:44（hypothesis_queue排程接續第六輪，本輪取鎖乾淨
`LOCK_ACQUIRED`）：#37（全市場現股當沖比重）TWTASU逐日回補再接續一批：
`python backfill_day_trading_ratio.py --skip-market-volume --batch-size
250`，本輪嘗試250天、新完成250天（其中18天無交易/無資料），累積已
快取1304/2609（50.0% of全範圍工作日，剛好過半，2015-01-01~
2024-12-31），FMTQIK（分母）已100%回補不用重跑。checkpoint機制運作
正常（逐日atomic寫入，本輪從上一輪留下的1054天接續，未遺失進度），
未觸及cheap gate（資料仍不完整），holdout未消耗
（`is_holdout_consumed()`=False）。已更新`HYPOTHESIS_QUEUE.md`#37
條目最新進度（含「排隊順序總結」章節同步更新）。下一輪重跑同一指令
即可自動從上次進度接續，估計還需約5輪左右批次才能回補完整TRAIN+VAL
期。此輪為單純基礎設施回補批次、非新變更/非部署決策，依`CLAUDE.md`
「已核准的自主挖礦馬拉松不受提案先於執行約束」條款執行。本輪`git
status`確認repo內有兩份非本輪產生的殘留未追蹤檔案（一個路徑寫壞的
暫存txt、一個round366深挖log），判斷屬於三軌馬拉松留下，本輪不觸碰、
不納入commit。

## 2026-09-05T21:12（hypothesis_queue排程接續第五輪，本輪取鎖乾淨
`LOCK_ACQUIRED`，非陳舊鎖回收）：#37（全市場現股當沖比重）TWTASU
逐日回補再接續一批：`python backfill_day_trading_ratio.py
--skip-market-volume --batch-size 250`，本輪嘗試250天、新完成250天
（其中16天無交易/無資料），累積已快取1054/2609（40.4% of全範圍
工作日，2015-01-01~2024-12-31），FMTQIK（分母）已100%回補不用重跑。
checkpoint機制運作正常（逐日atomic寫入，本輪從上一輪留下的804天
接續，未遺失進度），未觸及cheap gate（資料仍不完整），holdout未消耗
（`is_holdout_consumed()`=False）。已更新`HYPOTHESIS_QUEUE.md`#37
條目最新進度，下一輪重跑同一指令即可自動從上次進度接續，估計還需約
6輪左右批次才能回補完整TRAIN+VAL期。此輪為單純基礎設施回補批次、非
新變更/非部署決策，依`CLAUDE.md`「已核准的自主挖礦馬拉松不受提案
先於執行約束」條款執行。

## 2026-09-05T20:35（hypothesis_queue排程接續，**取鎖時發現陳舊鎖**，
held by pid 70000、30.2分鐘未更新，已自動回收——記錄疑似上一輪失敗或
卡住，本輪未進一步追查原因）：#37（全市場現股當沖比重）TWTASU逐日
回補再接續一批：`python backfill_day_trading_ratio.py
--skip-market-volume --batch-size 250`，本輪嘗試250天、新完成250天
（其中11天無交易/無資料），累積已快取804/2609（30.8% of全範圍工作日，
2015-01-01~2024-12-31），FMTQIK（分母）已100%回補不用重跑。checkpoint
機制運作正常（逐日atomic寫入，本輪從上一輪留下的541天接續，未遺失
進度），未觸及cheap gate（資料仍不完整），holdout未消耗
（`is_holdout_consumed()`=False）。已更新`HYPOTHESIS_QUEUE.md`#37
條目最新進度，下一輪重跑同一指令即可自動從上次進度接續，估計還需約
7輪左右批次才能回補完整TRAIN+VAL期。此輪為單純基礎設施回補批次、非
新變更/非部署決策，依`CLAUDE.md`「已核准的自主挖礦馬拉松不受提案
先於執行約束」條款，不需先提案。**本輪順帶發現**repo根目錄有非本輪
產生的殘留未commit變更（`.github/workflows/market.yml`、
`data/rate_limit_state.json`、兩個未追蹤的暫存/log檔），依協定第0節
不觸碰、不納入本輪commit，僅記錄於此。

## 2026-09-05T19:42（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#37
（全市場現股當沖比重）TWTASU逐日回補再接續一批：`python
backfill_day_trading_ratio.py --skip-market-volume --batch-size 250`，
本輪嘗試250天、新完成250天（其中16天無交易/無資料），累積已快取
541/2609（20.7% of全範圍工作日，2015-01-01~2024-12-31），FMTQIK
（分母）已100%回補不用重跑。checkpoint機制運作正常（逐日atomic寫入，
本輪從上一輪留下的291天接續，未遺失進度），未觸及cheap gate（資料仍
不完整），holdout未消耗（`is_holdout_consumed()`=False）。已更新
`HYPOTHESIS_QUEUE.md`#37條目最新進度，下一輪重跑同一指令即可自動從
上次進度接續，估計還需約8輪左右批次才能回補完整TRAIN+VAL期。此輪為
單純基礎設施回補批次、非新變更/非部署決策，依`CLAUDE.md`「已核准的
自主挖礦馬拉松不受提案先於執行約束」條款，不需先提案。

## 2026-09-05T19:05（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#37
（全市場現股當沖比重）TWTASU逐日回補接續一批：`python
backfill_day_trading_ratio.py --skip-market-volume --batch-size 250`，
本輪嘗試250天、新完成250天（其中16天無交易/無資料），累積已快取
291/2609（11.2% of全範圍工作日，2015-01-01~2024-12-31），FMTQIK
（分母）已100%回補不用重跑。checkpoint機制運作正常（逐日atomic寫入，
本輪從上一輪留下的41天接續，未遺失進度），未觸及cheap gate（資料仍
不完整），holdout未消耗（`is_holdout_consumed()`=False）。已更新
`HYPOTHESIS_QUEUE.md`#37條目最新進度，下一輪重跑同一指令即可自動從
2015年較後段接續，估計還需約9輪左右批次才能回補完整TRAIN+VAL期。
**額外發現（非本輪產生，記錄供其他軌道注意）**：本輪rebase前發現
`git stash list`累積6個從先前輪次留下、從未還原的舊stash（涉及
TW_MARATHON_STATE.md/TW_LOG.md等TW軌檔案），研判是其他軌道（可能是
`AlphaMarathon`三軌）rebase時暫存後忘記pop回去；本輪只暫存+還原了
自己這次為了rebase新增的2筆（不影響上述6筆），未觸碰/未清理舊有的，
留給TW軌自己的排程處理。

## 2026-09-05T18:30（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#37
（全市場現股當沖比重）發現FinMind`TaiwanStockDayTrading`免費層資料只從
2024-01-02起有、涵蓋不到TRAIN期（2015-2020），標準cheap gate無法用原
設計執行。改建TWSE官方資料源：新增`twse_day_trading_client.py`
（TWTASU）+`twse_market_volume_client.py`（FMTQIK，當分母）+
`backfill_day_trading_ratio.py`（比照`backfill_t86.py`可續跑批次設計）。
本輪執行：FMTQIK全市場成交量120個月（2015-01~2024-12）**100%回補完成**；
TWTASU逐日回補（瓶頸在TWSE反爬蟲需2.0秒/次間隔）本輪僅完成16天即因
**本輪執行環境USD預算即將用盡被迫提前收工**，checkpoint機制正常（逐日
atomic寫入不遺失進度），下一輪重跑`backfill_day_trading_ratio.py
--skip-market-volume`即可自動接續，估計還需約10輪批次才能回補完整
TRAIN+VAL期。已更新`HYPOTHESIS_QUEUE.md`#37條目+排隊順序總結。

## 2026-09-05T18:00（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#36
（個股融券使用率）**最終alpha顯著性判定完成：FAIL，正式結案**。解決
上一輪（T17:32）留下的TRAIN期alpha不顯著(p=0.3717)/VAL期alpha顯著
(p=0.0354)判斷——依既有「alpha顯著性須兩期皆成立」同一把尺，比照
`#106`「TRAIN無訊號、VAL單獨顯著」不放行的先例，判FAIL；另誠實揭露
整套測試因引擎不支援放空，從頭到尾只驗證了訊號多頭鏡像半邊，原始
「放空高融券使用率股票」假說核心從未被真正測試過。已更新
`HYPOTHESIS_QUEUE.md`#36條目+排隊順序總結、`STRATEGY_GRAVEYARD.md`
新條目、`TRIALS_LEDGER.md`#137。重新查證`BACKLOG.md`確認#5/#6/#8/#10
四項外部依賴仍全部卡住，依協定設計新假設軸**#37（全市場現股當沖比重
當市場過熱regime訊號）**——首次針對「零售投機熱度/市場微結構」這個
資料類別建立假設，跟前36條機制類別皆不同，已查證FinMind
`TaiwanStockDayTrading`免費層可用，本輪僅完成設計+可行性查證，尚未
開始第1關。`is_holdout_consumed()`開工/收工前皆確認False，零新增
下單/資料抓取（僅查證單一免費API端點回應）。**佇列排隊順序現在是
#37，下一輪從第1關cheap gate開始，不跳關。**

## 2026-09-05T17:32（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#36
（個股融券使用率）第9關（下檔保護）本輪完成，**判定：機械判準PASS，但
代價需誠實揭露**。新增`short_sale_utilization_gate9_regime_overlay.py`
——把`regime_overlay.py`（#10方法論框架）**首次正式接上一個已通過1~6關
的真實選股候選**，沿用#10既有大盤trend×vol regime判定+既有`EXPOSURE_
MAP`先驗（不重新優化），疊加到#36真實訊號equity curve上。TRAIN：MDD
-18.12%→-17.37%、地雷率(單日<-3%)1.23%→0.75%（皆改善，但CAGR+8.39%→
+6.90%、Sharpe0.50→0.45同時下降）。VALIDATION：MDD-9.18%→-7.34%、
地雷率0.31%→0.10%（皆改善，代價更明顯：CAGR+15.27%→+9.42%、Sharpe
1.28→1.09）。**最重要的誠實發現**：2022全年對台股大盤是空頭年、但對
這個選股訊號本身是獲利年，baseline報酬+25.53%，套上未經校準的通用
regime overlay後只剩+9.49%（平均曝險被砍到0.48）——代表這組先驗會
誤殺選股訊號本身的特異性報酬來源，不是穩賺不賠的免費保險。完整數字見
`TRIALS_LEDGER.md`#136、`HYPOTHESIS_QUEUE.md`#36。**GATE_SEQUENCE九關
已全數走過一輪，#36現在唯一剩下的未決問題是`#135`留下的TRAIN期alpha
不顯著(p=0.3717) vs VAL期alpha顯著(p=0.0354)最終判斷**，本輪依協定
刻意不倉促下結論，留給下一輪或視需要提案給總司令一併討論。
`is_holdout_consumed()`開工/收工前皆以獨立`python -c`呼叫確認為False，
零新增API呼叫（純本地快取讀取）。

## 2026-09-05T17:07（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#36
（個股融券使用率）第5/6關（leave-one-out+逐年一致性）本輪完成，**判定：
皆PASS**。新增`short_sale_utilization_gate5_loo.py`（逐字比照
`copper_gold_ratio_overlay_v1.py`#34第5/6關同一套判準，用TRAIN期單一
真實訊號equity curve逐年拆解，1x成本，只測TRAIN不動VAL；第6關直接複用
第5關已算好的逐年報酬dict，免費延伸判斷、非新工作單位）。TRAIN逐年
報酬2015~2020：-1.92%/+5.69%/+21.87%/+2.13%/+14.24%/+8.22%（複利連乘
+59.53%，與`short_sale_utilization_portfolio_v1.py`TRAIN真實策略報酬
交叉確認一致）。第5關拿掉貢獻最大的2017年(+21.87%)後剩餘複利總報酬
+30.90%仍為正，PASS。第6關6個年度中5個為正(5/6=83.3%)，達門檻PASS。
完整數字見`TRIALS_LEDGER.md`#135。**誠實保留（本輪新發現，不妄下最終
結論）**：這條候選出現「TRAIN期alpha不顯著(p=0.3717)、VAL期alpha
顯著(p=0.0354)」的組合，跟本佇列過往FAIL案例常見型態（多為VAL不顯著）
相反，需要更審慎判斷才能定最終alpha顯著性判準，本輪刻意不在此做最終
PASS/FAIL裁決，也未觸及「通過完整GATE_SEQUENCE準備部署」的停下提案
門檻（第9關下檔保護尚未開始）。`is_holdout_consumed()`開工/收工前皆以
獨立`python -c`呼叫確認False，零新增API呼叫（純本地快取讀取）。**佇列
排隊順序仍是#36（未結案，第5/6關PASS，下一輪從第9關下檔保護開始，或
先處理TRAIN/VAL alpha顯著性不一致的判斷）**，剩餘#5/#6/#8/#10仍卡外部
依賴，這輪工作單位到此為止。

## 2026-09-05T16:31（hypothesis_queue排程接續，取鎖乾淨非陳舊）：#36
（個股融券使用率）第3關（參數密集高原）本輪完成，**判定：PASS**。新增
`short_sale_utilization_gates.py`（逐字比照`f52w_high_gates.py`#17第3關
同一套TOP_N/REBALANCE_DAYS雙維度網格精神，不改
`short_sale_utilization_portfolio_v1.py`本體，只測TRAIN期不動VAL）。
TOP_N in [10,15,20,25,30]（固定REBALANCE_DAYS=21）報酬依序
+74.19%/+77.74%/+59.53%(錨點)/+54.37%/+41.01%；REBALANCE_DAYS in
[10,21,42,63]（固定TOP_N=20）報酬依序+47.29%/+59.53%(錨點)/+54.05%/
+53.65%。網格共8獨立點**全部為正（8/8=100%，遠高於60%門檻）**，登錄
門檻點不是單點孤峰。誠實提醒：仍是訊號多頭鏡像半邊（融券使用率最低
分位），第3關高原穩健不代表第2關發現的TRAIN期alpha不顯著（p=0.3717）
問題已解決，留到第6關逐年一致性/第7關OOS一併檢視，**尚未結案**。
`is_holdout_consumed()`開工/收工前皆以獨立`python -c`呼叫確認False。
零新增API呼叫（純本地快取讀取）。**下一輪從第5關leave-one-out開始，
不跳關**。已更新`HYPOTHESIS_QUEUE.md`#36條目對應段落（正文+「排隊順序
總結」章節）、`TRIALS_LEDGER.md`新增#134，commit+push收工。

## 2026-09-05T16:14（hypothesis_queue排程接續，取鎖時發現LOCK_STALE
[held by 66552, 29.9 min old]被自動回收recovering，記錄：上一輪疑似
執行中斷未正常收工——`git pull`確認`Already up to date`、`git status`
無殘留未commit變更，判斷上一輪已正常收尾，這次陳舊只是排程間隔巧合，
非資料遺失）：#36（個股融券使用率）連續執行兩次
`short_sale_utilization_portfolio_v1.py`，**TRAIN隨機控制組跑完
100/100、VALIDATION隨機控制組從70跑完到100/100，第2關（隨機控制組）
本輪判定：PASS**。TRAIN：真實策略+59.53%vs買進持有+58.86%、
alpha年化+7.44%、beta=+0.310、p=0.3717（不顯著）、隨機控制組
percentile=100.0。VALIDATION：真實策略+72.46%vs買進持有+54.58%、
alpha年化+11.88%、beta=+0.278、p=0.0354（顯著）、隨機控制組
percentile=100.0。腳本內建判準（VAL percentile>=90.0）判PASS，但依
alpha顯著性+beta拆解同一把尺，TRAIN期不顯著這件事留到第6/7關一併
檢視，**尚未結案**。`is_holdout_consumed()`前後皆確認False。**判定：
第2關PASS，下一輪從第3關參數密集高原（TOP_N掃描）開始，不跳關**。
已更新`HYPOTHESIS_QUEUE.md`#36條目對應段落與「排隊順序總結」章節、
`TRIALS_LEDGER.md`新增#133，commit+push收工。

## 2026-09-05T10:21（hypothesis_queue排程接續，LOCK_ACQUIRED乾淨取鎖）：
`git pull`確認`Already up to date`、`git status`乾淨無殘留。#36（個股
融券使用率）連續執行兩次`short_sale_utilization_portfolio_v1.py`，
TRAIN隨機控制組checkpoint持久化進度50→80→90/100 draws（兩次執行皆
順利跑完正常結束，未觸發timeout截斷）。VALIDATION期仍未開始，
`is_holdout_consumed()`前後皆確認False。**判定：未結案，接續中，下一輪
從90/100接續，只差10筆即完成TRAIN**。已更新`HYPOTHESIS_QUEUE.md`#36
條目對應段落，commit+push收工。

**格式修正說明（2026-09-05 hypothesis_queue排程本輪發現並修正）**：上一輪
插入心跳時把新條目插在標題文字中間（切斷「自主研」「究馬拉松」），把
標題還原成完整一行，新條目改放正確位置（標題之後、第一筆既有條目之上）。

## 2026-09-05T09:23（hypothesis_queue排程接續，取鎖時發現`LOCK_STALE`
[held by 59452, 30.5 min old]被自動回收recovering，非乾淨LOCK_ACQUIRED
——記錄：上一輪（T09:04）疑似執行中斷未正常收工。`git pull`確認
`Already up to date`，但`git status`發現上一輪已`git add`但未commit的
殘留（`HYPOTHESIS_QUEUE.md`/`MARATHON_LOG.md`，內容是TRAIN checkpoint
30→40/100 draws的合法紀錄）——查證確認是本track自己上一輪的合法產出、
非其他排程來源，決定併入本輪一起補commit，不是「不觸碰納入」的外來
殘留情況。另確認先前輪筆記提到的未追蹤檔`deep_dive_f_us_value_bm_
leave_extreme_out.py`現已被其他來源正式`git add`納入版本控制，不再是
未追蹤殘留，本輪不處理。）—接續佇列第36條（個股融券使用率）第2關TRAIN
隨機控制組：重新執行`short_sale_utilization_portfolio_v1.py`一次，420秒
時間預算內記憶體內進度40→59/100draws，因checkpoint僅每滿10筆落盤，實際
持久化進度為**50/100draws**（下一輪從50接續、重算50~59這9筆，非資料
遺失，是既有落盤頻率設計）。VALIDATION期仍未開始，**尚未做PASS/FAIL
判定**——已同步`HYPOTHESIS_QUEUE.md` #36條目「狀態」小節+排隊順序總結
（原文字停留在過時的20/100，本輪一併修正）。`is_holdout_consumed()`
執行前後皆以獨立`python -c`呼叫再次確認False。本輪未觸及三個停下條件，
正常收工，下次排程觸發從checkpoint 50/100繼續。

## 2026-09-05T09:04（hypothesis_queue排程接續，取鎖成功LOCK_ACQUIRED，無殘留鎖檔，`git pull`/`git status`確認乾淨，發現非本輪殘留未追蹤檔`deep_dive_f_us_value_bm_leave_extreme_out.py`不觸碰不納入commit）—接續佇列第36條（個股融券使用率）第2關TRAIN隨機控制組：重新執行`short_sale_utilization_portfolio_v1.py`一次，420秒時間預算內記憶體內進度30→49/100draws，因checkpoint僅每滿10筆落盤，實際持久化進度為40/100draws（下一輪從40接續、重算40~49這9筆，非資料遺失，是既有落盤頻率設計）。VALIDATION期仍未開始，**尚未做PASS/FAIL判定**——已同步`HYPOTHESIS_QUEUE.md` #36條目「狀態」小節。`is_holdout_consumed()`執行前後皆確認False。本輪未觸及三個停下條件，正常收工，下次排程觸發從checkpoint 40/100繼續。**（誠實補充：本輪commit+push未及完成即中斷，具名鎖留下陳舊鎖檔，由下一輪T09:23回收接手，內容已查證正確並補commit，非資料遺失）**

## 2026-09-05T08:35（hypothesis_queue排程接續，取鎖成功LOCK_ACQUIRED，無殘留鎖檔，`git pull`/`git status`確認乾淨，發現非本輪殘留未追蹤檔`deep_dive_f_us_value_bm_leave_extreme_out.py`不觸碰不納入commit）—接續佇列第36條（個股融券使用率）第2關TRAIN隨機控制組：連續執行`short_sale_utilization_portfolio_v1.py`兩次，持久化進度20→30/100 draws，VALIDATION期仍未開始，**尚未做PASS/FAIL判定**——已同步`HYPOTHESIS_QUEUE.md` #36條目狀態小節。`is_holdout_consumed()`執行前後皆確認False。本輪未觸及三個停下條件，正常收工，下次排程觸發從checkpoint 30/100繼續。

## 2026-09-05T08:04（hypothesis_queue排程接續，取鎖成功LOCK_ACQUIRED，
無殘留鎖檔，`git pull`/`git status`確認乾淨）— 接續佇列第36條（個股
融券使用率）第2關TRAIN隨機控制組：重新執行
`short_sale_utilization_portfolio_v1.py`，420秒時間預算內記憶體內
進度10→29/100 draws，因checkpoint僅每滿10筆落盤，實際持久化進度為
20/100 draws（下一輪從20接續、重算20~29這9筆，非資料遺失，是既有
落盤頻率設計）。VALIDATION期仍未開始，**尚未做PASS/FAIL判定**——已
同步`HYPOTHESIS_QUEUE.md` #36條目「狀態」小節+「排隊順序總結」，
未新增`TRIALS_LEDGER.md`列（沒有新判定可記）。`is_holdout_consumed()`
執行前後皆確認False。本輪未觸及三個停下條件，正常收工，下次排程
觸發從checkpoint 20/100繼續。

## 2026-09-05T07:43（hypothesis_queue排程接續，取鎖成功LOCK_ACQUIRED，
無殘留鎖檔）— 接續佇列第36條（個股融券使用率）第2關以後：新增
`short_sale_utilization_portfolio_v1.py`（做多融券使用率最低分位，
誠實揭露這只測訊號多頭鏡像半邊，放空腿因`backtest/engine.py`不支援
放空/負權重尚未驗證，見腳本docstring與`HYPOTHESIS_QUEUE.md`#36條目
完整說明）。本輪執行結果：TRAIN真實策略報酬+59.53%（買進持有
+58.86%，alpha年化+7.44%、p=0.3717不顯著）、成本1x/2x/3x=+59.53%/
+45.68%/+31.88%，隨機控制組在420秒時間預算內跑到16/100 draws即
checkpoint，VALIDATION期尚未開始，**尚未做PASS/FAIL判定**——已同步
`HYPOTHESIS_QUEUE.md` #36條目「狀態」小節+「排隊順序總結」，未新增
`TRIALS_LEDGER.md`列（沒有新判定可記）。開工前確認FUT軌道殘留變更
（`research/FUT_LEADS.md`/`FUT_MARATHON_STATE.md`/`fut_cheap_gate.py`/
`round359_deep_dive_loo_no_low_vol_independent_sample_monthly.log`/
`TRIALS_LEDGER.md`本地未提交差異）非本輪產生，`git pull`因
`data/rate_limit_state.json`衝突用`git stash`保留後解衝突（取較新的
timestamp），未觸碰、未納入本輪commit。`is_holdout_consumed()`本輪
執行前後皆確認False。下一輪重跑同一支腳本會自動從checkpoint接續。

## 2026-09-05T06:59（hypothesis_queue排程接續，取鎖成功LOCK_ACQUIRED，
無殘留鎖檔）— 接續上一輪已登記的佇列第36條（個股融券使用率Short Sale
Utilization Ratio）進行第1關cheap IC gate：新增`factors.py::_short_
sale_utilization()`+`factor_ic_short_sale_utilization.py`（比照#30
`_margin_utilization()`框架），300檔快取宇宙248/300可用、121個20交易日
快照。結果**CHEAP_PASS**：TRAIN mean_ic=-0.0163(n=74)、VAL mean_ic=
-0.0595 IR=-0.363(n=47)，train/val同號（皆負，與事前綁定方向一致），
null percentile=100.0（門檻90.0，過關）。已同步`HYPOTHESIS_QUEUE.md`
#36條目「狀態」小節+「排隊順序總結」新增第36項、`TRIALS_LEDGER.md`
新增#129列。本輪為佇列地基/第1關工作單位（依協定「一輪只做一個有界
工作單位」），下一輪從第2關隨機控制組（≥100 draws）開始，不跳關。
開工前確認殘留變更（`data/rate_limit_state.json`、round359
deep_dive log）非本輪產生，未觸碰、未納入commit。`is_holdout_
consumed()`本輪開工/收工前皆確認False。

## 2026-09-05T06:24（hypothesis_queue排程接續，鎖檔陳舊30.1分鐘後由本輪
回收，上一輪已完整寫完#35 VRP第1關FAIL判定與`STRATEGY_GRAVEYARD.md`/
`TRIALS_LEDGER.md`#127，但未同步「排隊順序總結」章節即中斷未commit）—
本輪先修正「排隊順序總結」缺漏的#35條目（依協定第1節「發現不一致先
修正掉」），確認`is_holdout_consumed()`仍為False，接著正式寫入佇列
第36條完整條目（個股融券使用率Short Sale Utilization Ratio當知情
放空者訊號，資料源沿用#30`TaiwanStockMarginPurchaseShortSale`，改取
`ShortSaleTodayBalance`/`ShortSaleLimit`欄位，跟#30融資使用率機制/
投資人族群相反但同源，見條目內文區隔說明）。本輪為佇列地基設計工作
單位，未寫因子/測試程式碼，下一輪從#36第1關cheap IC gate開始。另確認
`data/rate_limit_state.json`與兩個US track deep-dive log檔案（`deep_
dive_f_us_value_bm_run4_unbuffered.log`／`round359_deep_dive_loo_no_
low_vol_independent_sample_monthly.log`）為AlphaMarathon其他軌道殘留
變更，非本輪產生，依協定不觸碰、不納入本輪commit。

## 2026-09-05T05:29（hypothesis_queue排程接續，鎖檔陳舊30.1分鐘後由本輪
回收，上一輪疑似寫完#34第1關CHEAP_PASS狀態後未commit即中斷）— #34銅金比
第2關以後已結案：FAIL。新增`copper_gold_ratio_overlay_v1.py`（方向依#34
第1關實測負相關反轉），TRAIN總報酬僅+10.14%（跑輸買進持有+52.41%），
第2/3關表面過關但**第5關leave-one-out揭穿**：複利總報酬幾乎全由2019
單一年份貢獻，拿掉後翻負為-19.85%，依協定判FAIL。訊號強度（本佇列
timing類最強）不等於構造穩健性。已更新`STRATEGY_GRAVEYARD.md`/
`TRIALS_LEDGER.md`#126/`HYPOTHESIS_QUEUE.md`（含排隊順序總結同步）。
佇列#1~34全數結案，設計新假設軸#35（賣出台指選擇權波動度風險溢酬VRP，
機制類別首次為結構性風險溢酬收取，非選股/timing/portfolio construction/
配對/強制平倉），尚未開始第1關。

## 2026-09-05T04:56（hypothesis_queue排程接續）— #34銅金比第1關CHEAP GATE：
**CHEAP_PASS但方向反轉，尚未結案**。#33結案後查證#5/#6/#8/#10四項依賴
仍全部卡住，設計新假設軸#34（銅金比Copper/Gold Ratio當全球成長/風險
偏好regime訊號）。本輪先查yfinance `HG=F`/`GC=F`資料可行性（2015-01-02
~2026-06-29完整涵蓋、close無NaN、無>14天缺口，確認可行），新增
`copper_gold_ratio_gate.py`（沿用`fx_twd_gate.py`/`fred_yield_curve_
gate.py`同一套指數層級時序相關性框架）並執行第1關。結果：n=2330，
TRAIN(<=2020-12-31)Pearson r=-0.2467(null percentile=100.0過關)、
VAL(2020-12-31~2024-12-31)Pearson r=-0.1758(null percentile=100.0
過關)，三項cheap gate判準全過，判CHEAP_PASS。**誠實記錄**：事前綁定
方向預期正相關（銅金比走高→TAIEX轉強），實測兩期皆負相關且|r|量級
（0.18~0.25）遠高於#32/#33，不猜測替代機制、不下定論，交由下一輪
deep_dive前先轉具體overlay規則走第2關（規則方向須依實測負相關訂定，
不能沿用已推翻的原始正相關敘事）。已同步更新`HYPOTHESIS_QUEUE.md`#34
條目跟「排隊順序總結」（同時修正一個既有編號off-by-one：#33美國公債
殖利率曲線在總結區塊原誤標「32.」，已改回「33.」並補上「34.」）、
`TRIALS_LEDGER.md`新增#125列。

## 2026-09-05T04:26（hypothesis_queue排程接續）— #33第1關CHEAP GATE：
**已結案FAIL**。接手時發現上一輪鎖檔陳舊（PID 49668持有30.2分鐘，疑似
中途中斷/失敗，本輪`marathon_lock.py`自動回收），但上一輪留下的
`fred_yield_curve_gate.py`程式碼完整可執行（未寫到一半），本輪直接
執行、未重寫。結果：n=2320對齊配對，TRAIN(<=2020-12-31)Pearson
r=-0.0636(null percentile=98.6過關)、VAL(2020-12-31~2024-12-31)
Pearson r=-0.0242(**null percentile=52.8遠未過90.0門檻**)，三項判準
之一（VAL贏過洗牌null）未過，直接FAIL，未進第2關以後。附註：事前
綁定方向預期為正相關，兩期實測皆為負相關，方向也與文獻預期相反。
完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#124、
`HYPOTHESIS_QUEUE.md`#33。佇列#33結案，#5/#6/#8/#10仍卡外部依賴
（本輪重新查證`BACKLOG.md`仍未解鎖），設計新假設軸**#34：銅金比
Copper/Gold Ratio當全球成長/風險偏好regime訊號**（第一次引入實體
經濟商品市場資訊，非任何金融市場部位/流向/預期，見
`HYPOTHESIS_QUEUE.md`新章節），下一輪從資料可行性查證
（yfinance`HG=F`/`GC=F`是否有完整2015年起日頻資料）開始。

## 2026-09-05T03:23（hypothesis_queue排程接續）— 修正
`HYPOTHESIS_QUEUE.md`「排隊順序總結」章節#32字樣不同步（#32條目本身
已寫結案FAIL，但總結區塊仍停留在「現在排隊第一，尚未開始第1關」舊
字樣，本輪發現並修正對齊）；重新查證`BACKLOG.md`確認#5/#6/#8/#10
四項外部依賴仍全部卡住（`value_board_v2`仍`回測未通過`，題材動能榜/
未來性濾網仍`紙上交易中`，無新進展），依協定第1節設計新假設軸**#33：
美國公債殖利率曲線（10Y-2Y利差）當全球風險regime訊號**（公債市場
資訊來源，跟前32條選股/timing/選擇權/外匯訊號皆不同類別，經濟機制
是全球貨幣政策預期領先衰退風險）。FRED`T10Y2Y`資料可行性已查證
（curl確認2015年起逐日資料齊全，涵蓋TRAIN+VAL全期，金鑰沿用既有
`alpha-data/fred_key.txt.txt`凍結區檔案，只讀不動）。本輪未寫任何
因子/測試程式碼，下一輪從第1關CHEAP GATE開始，不跳關。

## 2026-09-05T02:56（hypothesis_queue排程接續）— #32第1關CHEAP
GATE：**已結案FAIL**。新增`fx_twd_gate.py`（沿用#19/#31同一套指數層級
時序相關性框架，逐年分批呼叫`TaiwanExchangeRate`避免502），訊號=台幣
即期匯率`spot_sell`N(20)交易日變動率、目標=TAIEX後M(20)交易日報酬
（N=M=20事前綁定）。結果：TRAIN Pearson r=+0.0368(null percentile=82.6
未過90.0)、VAL Pearson r=-0.0723(null percentile=96.0過90.0，方向符合
事前預期的股匯負相關)，**但train/val正負號相反**，第1關三項判準之一
未過，直接FAIL，未進第2關以後。跟已FAIL的#9/#11/#13同一種「方向不穩定」
死法家族。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#123、
`HYPOTHESIS_QUEUE.md`#32。佇列#32結案，#5/#6/#8/#10仍卡外部依賴，下一輪
需設計新假設軸#33。

## 2026-09-05T02:45（hypothesis_queue排程接續）— 修正`HYPOTHESIS_QUEUE.md`
「排隊順序總結」章節#31字樣不同步（上一輪寫完#31結案FAIL細節後、總結
區塊仍停留在「尚未結案，接續第2關」舊字樣，本輪發現並修正對齊，正是
`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節警告的「條目本身結案但總結字樣沒同步」
情況）；確認佇列#1~31全數結案、#5/#6/#8/#10四項外部依賴仍卡住（無新
進展），依協定第1節設計新假設軸**#32：美元兌台幣匯率當資金外流/市場
壓力regime訊號**（外匯市場資訊來源，跟前31條選股/市場內部timing/選擇權
訊號皆不同類別，經濟機制是外資撤出台股同步伴隨台幣貶值換匯壓力）。
FinMind`TaiwanExchangeRate`資料可行性已查證（curl確認2015年起逐日資料
齊全，涵蓋TRAIN+VAL全期）。本輪未寫任何因子/測試程式碼，下一輪從第1關
CHEAP GATE開始，不跳關。

## 2026-09-05T01:58（hypothesis_queue排程接續）— #31第2/3關：**已結案FAIL**。
新增`option_pcr_overlay_v1.py`（沿用#19`spillover_overlay_v1.py`
overlay/成本/隨機控制組框架，重用`option_pcr_gate.py`快取，未重打API）：
trailing 250日PCR百分位排名<30%時降曝險至0.3。結果TRAIN overlay報酬
-36.91%（買進持有+55.93%）、VAL overlay-17.57%（買進持有+59.73%），
兩期皆大幅跑輸大盤；第2關隨機控制組percentile雖皆=100.0，但第3關
參數密集高原僅7/49點(14%)為正、遠低於60%門檻，判**FAIL**。防禦型
overlay在持續多頭市場的機會成本蓋過保護效益。不泛化成PCR訊號沒用
（第1關cheap gate仍CHEAP_PASS），死的是這個具體二元切換構造。**佇列
#1~31全數結案**，剩餘#5/#6/#8/#10仍卡外部依賴，下一輪需設計新假設軸
#32。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#122、
`HYPOTHESIS_QUEUE.md`#31。`is_holdout_consumed()`確認`False`。

## 2026-09-05T01:28（hypothesis_queue排程，取得陳舊鎖檔接續，上一輪疑似
卡住約30分鐘）— 先push上一輪
未推送成功的commit（佇列#30已結案FAIL文件+新增假設#31登記），接著執行
#31第1關cheap gate：新增`option_pcr_gate.py`（台指選擇權TXO Put/Call
日盤成交量比率，比照#19`spillover_overnight_gate.py`同一套指數層級時序
相關性框架），一次抓10年選擇權資料遇FinMind 502改成逐年分批抓取解決，
結果**CHEAP_PASS**（TRAIN r=+0.0611/null percentile=98.2，VAL
r=+0.0587/null percentile=94.0，三項判準皆過），詳見`HYPOTHESIS_QUEUE.md`
#31與`TRIALS_LEDGER.md`#121。尚未結案，下一輪接續第2關。
## 2026-09-05（hypothesis_queue排程）— 完成並commit佇列#30（個股融資使用率regime-conditional portfolio構造）已結案FAIL的文件（該結論由前一輪未commit的session產出，本輪獨立重跑腳本驗證數字一致後補commit）；同步修正排隊順序總結章節的過時提示字；查證#5/#6/#8/#10依賴仍卡住後設計新假設#31（台指選擇權Put/Call成交量比率當市場regime訊號，僅登記尚未開始第1關）。

**這份檔案存在的理由**：使用者裁示「解決使用者『看不到它在跑』——每完成
一個關卡或每約30分鐘寫一行（時間戳＋現在在跑哪條假設的哪一關＋結果），
並commit push」。最新的寫最上面。

**授權範圍**：從checkpoint `c19c11f`接續，照`research/HYPOTHESIS_QUEUE.md`
排隊執行，先還B24可重現性乾淨重跑這筆前置債，然後Weinstein第二階段→
CTA趨勢跟隨→PEAD組合層→股票股利率carry→（regime overlay/量價/低波/
類股輪動依相依性到位再跑）。只有「要不要拉到1000draws」「survivorship-free
宇宙要不要投入」「任何不可逆操作/花錢」這三種情況才停下來問，其餘自主
往下跑。

---

## 2026-09-05T00:30+08:00 — [hypothesis_queue] 接續#30個股融資使用率regime-conditional避開篩選：`git pull`+`git status`確認乾淨（發現非本輪殘留變更`research/us_fundamentals.py`（已修改）與`research/margin_utilization_regime_portfolio_v1_run.log`/`research/us_factor_ic_value.py`/`research/us_factor_ic_value_run.log`（未追蹤），判斷為其他自動化來源留下，本輪不觸碰、不納入commit），取具名鎖`hypothesis_queue`（`LOCK_ACQUIRED`，非陳舊）。確認無殘留背景行程，checkpoint顯示TRAIN隨機控制組上輪停在70/100。本輪內連續呼叫腳本三次（明確`run_in_background:true`，各480秒預算），確認TRAIN隨機控制組**70→100/100（完成）**——**真實訊號表現：TRAIN 1x報酬-16.97%、alpha-4.18%(p=0.7512不顯著)、beta+0.737，隨機控制組(N=100)真實對照組本身mean=+0.40%、percentile=1.0（遠低於90.0門檻，且真實策略還輸給99%的『危機期隨機選股』對照組）**——這是本佇列目前為止percentile最極端偏低的結果之一，強烈暗示regime-conditional避開高融資使用率個股在TRAIN期沒有兌現保護效果、反而更差。接著VALIDATION真實訊號+成本敏感度(1x/2x/3x)已完成，隨機控制組進度0→**44/100**。**仍未結案**（TRAIN這一項判準已可預見大機率FAIL，但依協定完整走完VALIDATION才能做最終alpha顯著性+beta拆解判定），`is_holdout_consumed()`收工前確認`False`。下一輪`python research/margin_utilization_regime_portfolio_v1.py`會自動接續VALIDATION剩餘56筆隨機控制組。

## 2026-09-04T23:37+08:00 — [hypothesis_queue] 接續#30個股融資使用率regime-conditional避開篩選：`git pull`+`git status`確認乾淨主線外，發現非本輪殘留未提交變更（`.gitignore`／`research/alpha_live_server.py`／`research/us_fundamentals.py`／`scripts/smoke_test.mjs`／`research/gen_local_ca.py`／`research/us_factor_ic_value.py`等，判斷為其他自動化來源留下），本輪不觸碰、不納入commit。取具名鎖`hypothesis_queue`（`LOCK_ACQUIRED`，非陳舊）。確認`margin_utilization_regime_portfolio_v1.py`無殘留背景行程，checkpoint顯示上輪TRAIN隨機控制組已到50/100（比上一則心跳記錄的40更新）。用明確`run_in_background:true`啟動腳本（480秒預算），等待完成後確認TRAIN隨機控制組進度**50→70/100**（checkpoint接續、真實訊號+成本敏感度1x/2x/3x維持不變），本輪480秒預算內達最大進度後正常收工，未跑完VALIDATION。仍未結案，`is_holdout_consumed()`收工前確認`False`。下一輪執行`python research/margin_utilization_regime_portfolio_v1.py`會自動接續TRAIN剩餘30筆。

## 2026-09-04T23:xx（系統時間，本輪排程接手）— [hypothesis_queue] 接續#30個股融資使用率regime-conditional避開篩選：本輪接手時發現鎖檔陳舊（60分鐘）已由本輪回收，疑似上一輪呼叫結束時背景行程被一併終止；TRAIN隨機控制組進度30→40/100（checkpoint接續），中途誤判「移到背景」的行程已結束、意外啟動第二個並行實例，即時發現並安全終止（未寫入任何內容，checkpoint未受影響），已在HYPOTHESIS_QUEUE.md #30記錄操作教訓（之後長腳本一律明確run_in_background）。仍未結案，下一輪接續。

## 2026-09-04 21:01+08:00 — hypothesis_queue排程：#30個股融資使用率deep_dive第一步——下跌段vs上漲段分組IC，訊號集中在下跌段（探索性佐證，非最終判定）

接手前依`HYPOTHESIS_QUEUE_PROTOCOL.md`第0節完成三步驟：讀`CLAUDE.md`/
`CONSTITUTION.md`、`git pull`+`git status`（發現非本輪產生的殘留變更
`data/rate_limit_state.json`（已修改但未commit）與`research/
.alpha_live_server.pid`/`alpha_live_server_*.log`/`run343_full_gate3.log`
（未追蹤新檔），判斷為其他排程/即時報價來源留下，本輪不觸碰、不納入
commit；local分支跟origin分歧2 vs 1個commit，用`git stash`保護殘留變更
後`git rebase origin/main`成功理順，再`git stash pop`還原殘留變更）、
取具名鎖`hypothesis_queue`（`LOCK_ACQUIRED`，非陳舊鎖檔）。

`HYPOTHESIS_QUEUE.md`確認#1~29全數已結案，#30（個股融資使用率）第1關
cheap IC gate已於上一輪CHEAP_PASS（`TRIALS_LEDGER.md`#116），本輪接續
deep_dive。新增`factor_ic_margin_utilization_regime_split.py`（沿用
`factor_ic.py`既有`evaluate_factor()`/`build_snapshots()`，複用#116已
快取資料，零新網路請求）——把121個20交易日快照依TAIEX同窗口報酬正負
分成down（44個）/up（77個）兩組分別跑IC。結果：**下跌段**TRAIN
mean_ic=-0.1394、VAL mean_ic=-0.1817（train/val同號、null percentile=
100.0）；**上漲段**TRAIN mean_ic=+0.0304、VAL mean_ic=+0.0280（train/val
同號但方向翻正、null percentile=95.9）。VAL期下跌段\|IC\|=0.1817約為
上漲段0.0280的6.5倍，方向與#30條目事前寫明的核心機制主張（Brunnermeier
& Pedersen margin spiral，只在下跌段特別有效）完全吻合——unconditional
IC（#116）其實被上漲段弱正訊號稀釋過，真實訊號集中在下跌段。**這不是
PASS/FAIL/CHEAP_PASS最終判定**（樣本數比unconditional版本小，統計檢定力
較弱），是探索性佐證，支持下一步應設計regime-conditional的個股避開篩選
而非恆定十分位多空。完整見`HYPOTHESIS_QUEUE.md`#30條目、
`TRIALS_LEDGER.md`#117。`is_holdout_consumed()`本輪開工/收工前皆確認
`False`。**本輪工作單位到此為止（依協定「一輪一個有界工作單位」）**，
下一輪從設計regime-conditional具體portfolio層構造開始，接續走隨機控制組
（≥100 draws）等後續關卡。

---

## 2026-09-04 22:04 — hypothesis_queue排程：#30個股融資使用率第1關cheap IC gate CHEAP_PASS，非最終判定

新增`factors.py::_margin_utilization()`（FinMind
`TaiwanStockMarginPurchaseShortSale`）+`f_margin_utilization`因子+
`factor_ic_margin_utilization.py`。300檔快取宇宙248檔可用，TRAIN
mean_ic=-0.0293、VAL mean_ic=-0.0523、null percentile=100.0（門檻
90.0），train/val同號且方向與事前綁定（融資使用率越高未來報酬越差）
完全一致。**CHEAP_PASS，第1關而已，未進第2關**——依協定「一輪一個
有界工作單位」本輪到此收工。完整見`HYPOTHESIS_QUEUE.md`#30條目、
`TRIALS_LEDGER.md`#116。`is_holdout_consumed()`本輪開工/收工前皆
確認`False`。下一輪從第2關隨機控制組（≥100 draws）開始，不跳關。

---

## 2026-09-04 19:58 — hypothesis_queue排程：#1~29全數結案確認+設計新假設軸#30 — 佇列#5/#6/#8/#10依賴重新查證仍卡住，新增#30個股融資使用率（強制平倉/流動性螺旋風險），第1關cheap gate尚未開始

`HYPOTHESIS_QUEUE_PROTOCOL.md`第0節三步驟（讀CLAUDE.md/CONSTITUTION.md、
git pull+status、取具名鎖`hypothesis_queue`）皆完成，`git status`發現
`research/MARATHON_STATE.md`/`REPORT.md`/`TRIALS_LEDGER.md`/`US_LEADS.md`/
`US_LOG.md`/`US_MARATHON_STATE.md`有非本輪產生的殘留變更（判斷為TW/US
馬拉松軌道所留），依協定不觸碰、不納入本輪commit。讀完整份
`HYPOTHESIS_QUEUE.md`確認佇列#1~29全數已結案（皆FAIL），重新查證
`BACKLOG.md`（`value_board_v2`仍`回測未通過`、題材動能榜/未來性濾網仍
`紙上交易中`）確認#5/#6/#8/#10四項外部依賴依然全部卡住、無新進展，判定
佇列實質已空。設計新假設軸**#30個股融資使用率（Margin Financing
Utilization Ratio）——強制平倉/流動性螺旋風險訊號**（Brunnermeier &
Pedersen margin spiral機制，跟前29條在①方向性選股排序②timing/exposure
overlay③portfolio construction④配對交易均值回歸這四大已測類別皆不同的
第五類）——用FinMind`TaiwanStockMarginPurchaseShortSale`的
`MarginPurchaseTodayBalance/MarginPurchaseLimit`當融資使用率，事前綁定
方向為負（使用率越高、未來報酬越差，尤其下跌段）。curl直接測試FinMind
確認2015年至今歷史齊全可直接複用`factor_ic.py`既有框架，不需新資料工程；
旁註發現`alpha-data`凍結區`twse_margin`（`MI_MARGN`）只有約2週歷史不適用
（純唯讀查證`alpha.db`，未改動任何凍結區檔案）。完整經濟理由/具體定義/
已知背景區隔/資料可行性/下檔保護要求已寫入`HYPOTHESIS_QUEUE.md`新增
`### 30.`章節與「排隊順序總結」章節。**本輪工作單位到此為止（依協定
「一輪只做一個有界工作單位」），未寫任何因子/測試程式碼，未新增
`TRIALS_LEDGER.md`列（尚無PASS/FAIL/CHEAP_PASS判定可記）。下一輪從#30
第1關cheap IC gate開始，不跳關。**`is_holdout_consumed()`確認`False`。

---

## 2026-09-04T19:27 — hypothesis_queue軌道：#29等權重再平衡溢酬第6關逐年一致性 — FAIL(最終判定，佇列#29結案)

接手時鎖檔陳舊（30.7分鐘未更新，PID 50296被回收），確認上一輪已正確
staged第5關成果（含新腳本`equal_weight_rebalance_leave_one_out_v1.py`與
`TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`/`MARATHON_LOG.md`更新）但崩潰
未及commit，本輪先補commit這批遺留成果，再接續執行第6關。第6關直接複用
第5關已算出的TRAIN期逐年溢酬（未新增腳本）：2015+0.28%/2016-0.05%/
2017+3.98%/2018+3.48%/2019-1.10%/2020+9.78%，正報酬年度4/6（2016/2019
為負），4/6=66.7%未達>=5/6=83.3%門檻，判**FAIL**，依快殺標準不進第7/8/9
關。**佇列#29最終判定：FAIL**——第1~5關全數PASS但第6關逐年一致性未過，
跟`f_52w_high_prox`(#17)同一種死法。誠實記錄：這不是流程錯，是這個具體
159檔樣本/2015-2020窗口下年度方向不夠一致，效果本身在前5關已扎實驗證
存在且非隨機非集中在單一年份。詳見`HYPOTHESIS_QUEUE.md`#29條目、
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#114。**佇列#1~29全數結案**，
剩餘#5/#6/#8/#10仍卡外部依賴（本輪未重新查證），下一輪需先確認依賴狀態，
若仍未解鎖則佇列實質已空，需依協定第1節設計新假設軸#30。

---

## 2026-09-04T18:55 — hypothesis_queue軌道：#29等權重再平衡溢酬第5關leave-one-out — PASS(非最終判定)

接手時鎖檔陳舊（30分鐘未更新，PID 16916被回收），確認上一輪的第3/4關成果
已正確commit、無殘留背景行程後接續。新增`equal_weight_rebalance_leave_
one_out_v1.py`（第5關，只測TRAIN期毛報酬，逐年拿掉最大貢獻年份檢查複利
溢酬集中度）：TRAIN(2015-2020)逐年溢酬2015+0.28%/2016-0.05%/2017+3.98%/
2018+3.48%/2019-1.10%/2020+9.78%，完整複利溢酬+24.81%（跟第1/3關數字
一致，交叉確認正確）。拿掉貢獻最大年份2020（占總溢酬39.4%）後，剩餘複利
溢酬buyhold+36.03%/rebalanced+44.75%/**溢酬+8.72%仍為正**，判**PASS**
（`TRIALS_LEDGER.md`#112）。**誠實揭露附加風險**：本輪順帶算出TRAIN期
單獨只有4/6年（66.7%）年度溢酬為正，若第6關套用統一關卡「逐年一致性
>=5/6（83.3%）」門檻，**目前這個數字未達標**——已在`HYPOTHESIS_QUEUE.md`
明確標註「這不是本關判定範圍，留給下一輪正式處理」，不由本輪順帶下
FAIL/PASS結論，避免誤判。**佇列#29仍未結案**——第1~5關全過，下一輪從
第6關逐年一致性開始（需要決定TRAIN單獨看或TRAIN+VAL合併看、跟既有案例
如何比照），第9關下檔保護（等權重小型股曝險）仍是最大未知風險待驗證。

---

## 2026-09-04T接續 — hypothesis_queue軌道：#29等權重再平衡溢酬第3/4關 — 第3關PASS(補記上一輪陳舊鎖檔遺留成果)、第4關(成本敏感度)三情境皆正溢酬

接續上一輪（鎖檔陳舊28.9分鐘，本輪回收）。發現上一輪已跑完
`equal_weight_rebalance_plateau_v1.py`（第3關參數密集高原）但未及寫入
`HYPOTHESIS_QUEUE.md`/`TRIALS_LEDGER.md`即中斷——確認結果有效（17/17
網格點TRAIN/VAL溢酬同時為正，100%通過，無孤立尖峰），本輪補記文字
（`TRIALS_LEDGER.md`#110）。接著本輪新增執行`equal_weight_rebalance_
costs_v1.py`（第4關成本/稅/滑價1x/2x/3x敏感度，沿用`long_only_vs_
market.py`既有turnover成本慣例）：118次再平衡事件、累計turnover=3.920、
1x round-trip成本率0.6850%，淨溢酬1x/2x/3x皆維持顯著為正（TRAIN
+21.85%/+18.93%/+16.06%、VAL+29.32%/+26.95%/+24.60%），無情境轉負
（`TRIALS_LEDGER.md`#111）。**佇列#29仍未結案**——第1~4關全過，接續
第5關leave-one-out，第9關下檔保護（等權重小型股曝險）仍是最大未知風險
待驗證。

## 2026-09-04T09:54:54Z — hypothesis_queue接續#29：發現前一輪陳舊鎖檔(211分鐘)留下的未提交第3關參數高原成果(equal_weight_rebalance_plateau_v1.py，17點網格100%通過)，本輪確認結果有效並commit入庫，因USD budget將近用盡緊急收工，尚未推進第4關成本敏感度，HYPOTHESIS_QUEUE.md #29條目待下一輪補上第3關文字紀錄 — 佇列#29仍未結案

## 2026-09-04T13:56 — hypothesis_queue軌道：#29等權重再平衡溢酬第2關隨機控制組 — CHEAP_PASS

接續上一輪sanity（PASS，`TRIALS_LEDGER.md`#107）。設計並執行這條假設專屬
的第2關隨機控制組（因子IC的洗牌null不適用於這種無排序動作的機制）：對
sanity版本159檔panel做無放回bootstrap抽80檔子集，重跑同一套21交易日再
平衡規則，N=100 draws（`equal_weight_rebalance_control_v1.py`，新增）。
事前綁定三項判準（hit_rate>=80%／全池結果落在10~90百分位／中位數溢酬
明顯>0）全過：**100/100 draws TRAIN且VAL同時為正**、全池結果落在分布
56~57百分位（非離群）、中位數TRAIN+23.47%/VAL+30.34%。判**CHEAP_PASS**，
效果在隨機股票子集組合下幾乎全部穩健重現，符合Booth & Fama(1992)理論
先驗。**佇列#29仍未結案**，下一輪接續第3關（參數密集高原）。已同步更新
`HYPOTHESIS_QUEUE.md`#29條目與「排隊順序總結」、`TRIALS_LEDGER.md`#108。
`is_holdout_consumed()`=False。git狀態確認：`.github/scripts/
fetch_quotes_tw.py`/`data/quotes_tw.json`/`data/rate_limit_state.json`/
`research/US_LEADS.md`/`research/US_LOG.md`跟數個`research/*.log`/
`.pid`檔為其他自動化軌道（美股軌/報價抓取）殘留，本輪不觸碰、不納入
commit。

---

## 2026-09-04T13:27 — hypothesis_queue排程接續（#29第1關sanity：PASS，非最終判定） — 新增`equal_weight_rebalance_sanity.py`。基準操作化偏離#29原文（市值加權買進持有）——本專案無市值/流通股數資料源，且#29「資料可行性」段落原文承諾不新增資料工程，兩者矛盾，選擇遵守後者，改用「t0等權重、永不主動調整的buy-and-hold」當基準（理由見腳本docstring，避免混入等權vs市值加權的規模傾斜，呼應`f_low_vol`/`f_bab`死因）。沿用`factor_ic.py`既有300檔快取樣本(SEED=20260822)，234/300通過歷史長度門檻，視窗頭尾涵蓋度篩選後159檔組panel(2015-2024,2498交易日，存活者偏差已誠實揭露)。結果：再平衡事件118次(理論值一致)、拉回前權重離散度均值0.00068(>0,非no-op)、NaN/Inf皆0。TRAIN：buyhold+66.14%(Sharpe+0.691) vs rebalanced+90.95%(Sharpe+0.912)，溢酬+24.81pp；VAL：buyhold+83.58%(Sharpe+1.037) vs rebalanced+115.29%(Sharpe+1.379)，溢酬+31.72pp——兩期方向一致、Sharpe/MDD同步改善，判SANITY PASS。尚未結案，下一輪需先設計這條假設專屬的第2關隨機控制組（不能沿用因子IC的洗牌null，初步構想是隨機化再平衡日曆相位或宇宙bootstrap抽樣）。完整見`HYPOTHESIS_QUEUE.md`#29條目、`TRIALS_LEDGER.md`#107。`git status`確認`research/US_LEADS.md`/`research/US_LOG.md`跟數個`research/*.log`/`.pid`是別的自動化來源（疑似US軌或即時報價常駐程式）留下的殘留變更，本輪未觸碰、不納入commit。

## 2026-09-04T12:54 — hypothesis_queue排程接續（重新查證依賴+設計新假設軸#29） — 重新查證`BACKLOG.md`確認B24-500仍「回測未通過」、題材動能榜/未來性濾網仍「紙上交易中」，#5/#6/#8/#10依賴無新進展，佇列#1~28維持全數結案。設計新假設軸#29（等權重再平衡溢酬Diversification Return/Equal-Weight Rebalancing Premium）——刻意跟前28條區隔為機制上真正不同的第三類（非①方向性選股排序、非②timing/exposure overlay，是③portfolio construction：不選股、不做曝險縮放，純粹測「定期拉回等權重」這個機械式再平衡動作本身有沒有加值），完整經濟理由/假設定義/下檔保護要求已寫入`HYPOTHESIS_QUEUE.md`#29條目與「排隊順序總結」。本輪只登記假設、未寫程式碼、未跑任何測試，下一輪從第1關sanity開始，不跳關。

## 2026-09-04（hypothesis_queue排程，本輪鎖檔為陳舊鎖回收，上一輪疑似
中斷未完成收工）——#28市場廣度背離接續第2關隨機控制組，已結案：FAIL

新增`breadth_divergence_overlay_v1.py`，把第1關sanity（`breadth_divergence_
sanity.py`）已驗證的divergence_flag轉成具體曝險規則（`exposure=0.3 if
divergence_flag else 1.0`，shift(1)避免未來函數），跑第2關隨機控制組
（打亂exposure時序，N=100 draws）：TRAIN真實overlay總報酬+62.86%（反而
輸給買進持有+79.49%），對打亂分布percentile=54.0；VAL真實overlay總報酬
+42.96%（買進持有+56.36%），percentile=51.0。兩期皆遠低於90.0門檻且貼在
50附近——用breadth背離挑降曝險時機，跟隨機時點降曝險幾乎沒有差別，依
快殺標準「已被控制組拆穿之偽影家族換皮」判**FAIL**，未進第3關以後。
已同步更新`HYPOTHESIS_QUEUE.md`#28條目+「排隊順序總結」、
`STRATEGY_GRAVEYARD.md`新增條目、`TRIALS_LEDGER.md`#105。**佇列#1~28
全數結案**，剩餘#5/#6/#8/#10仍卡外部依賴（本輪重新確認B24-500仍不及格、
題材動能榜PIT引擎仍紙上交易中，均無新進展）。**本輪未設計新假設軸#29**
——因USD budget將近用盡，依「一輪只做一個有界工作單位」原則收工，下一輪
需先重新確認#5/#6/#8/#10依賴是否解鎖，未解鎖則設計新假設軸#29（應避開
「純選股排序」跟「timing/overlay類」兩種已知死法）。

## 2026-09-04T09:xx — hypothesis_queue排程接續（#28市場廣度背離第1關sanity：PASS，非最終判定） — 新增`breadth_divergence_sanity.py`，用既有300檔快取樣本（254檔可用）算breadth_pct（收盤價>自身200日均線比例）跟TAIEX 20日動量組成背離訊號，三項sanity（非退化分布/危機run-up期2/3領先方向正確/觸發後前瞻報酬方向正確）皆PASS，非結構性no-op、非反過來，寫入HYPOTHESIS_QUEUE.md#28＋TRIALS_LEDGER.md#103，本輪工作單位到此為止（依協定一輪一個有界工作單位），下一輪從第2關隨機控制組開始

---

## 2026-09-04T08:25 — hypothesis_queue排程接續（收尾#27＋設計新假設#28） — 接手時發現上一輪（PID 34684）已把#27判FAIL寫進STRATEGY_GRAVEYARD/TRIALS_LEDGER#102但因鎖檔陳舊（卡住30.3分鐘）未commit，本輪先確認並沿用該判定不重跑；修正HYPOTHESIS_QUEUE.md「排隊順序總結」章節#27的過時提示字（原寫「第2關進行中」，已同步為FAIL），重新查證B24-500/題材動能榜PIT引擎仍無新進展、#5/#6/#8/#10依然卡外部依賴，佇列實質已空，依協定第1節設計新假設軸#28（市場廣度背離Breadth Divergence當regime擇時訊號，經濟機制與已FAIL的#2/#10/#15/#26四者皆不同——不是價格趨勢、不是波動度、不是融資水位，是「指數上漲時參與個股比例」，資料可行性已用既有300檔快取樣本查證可行不需新API呼叫），寫入HYPOTHESIS_QUEUE.md完整條目，本輪工作單位到此為止，未展開第1關sanity

## 2026-09-04T08:xx — hypothesis_queue排程接續（#27結案：FAIL） — 接手時checkpoint已到300/300 draws（行程自然完成），計算percentile=87.2（門檻90.0，未過），依鐵律不放寬直接判FAIL，寫入STRATEGY_GRAVEYARD/TRIALS_LEDGER#102/HYPOTHESIS_QUEUE，佇列#5/#6/#8/#10仍卡外部依賴未解鎖，新假設軸設計留給下一輪

## 2026-09-04T07:29 — hypothesis_queue排程接續（#27複合z-score第2關） — 接手時PID 2037仍存活（06:52啟動，已運算37分鐘），checkpoint從06:52記錄的260/300持續輪詢7分鐘（07:21~07:28，每分鐘一次）皆維持260不動，查腳本確認`_save_checkpoint`每10筆draw才落盤一次（`composite_zscore_v1_random_control.py`第226-227行），推算260→270正在批次運算中屬正常現象非卡死，維持「不重啟、等待」策略不碰行程收工

`ps -p 2037`確認行程存在（WINPID 34720，STIME 06:52:03），`tasklist`
交叉確認CPU占用時Git Bash參數帶引號被MSYS路徑轉換搞亂（`/FI`被誤譯成
路徑），改用純`ps -p`結果已足夠判斷「行程存在」這個唯一需要的訊號，
沒有進一步追查CPU占用細節（不影響本輪判斷，記錄下來避免下一輪重複
踩同一個Git Bash引號陷阱，若真的需要CPU占用可改用
`powershell.exe -Command "Get-Process -Id 34720"`）。**進度**：以06:52
（232筆）→07:21（260筆）約29分鐘28筆估算速率約62秒/draw，剩餘40筆
理論還需約41分鐘（純運算時間，不含批次寫入延遲的變異）。**下一輪
待辦**：先`ps -p 2037`確認存活狀態；存活就不碰繼續等（並查checkpoint
是否已推進到270/280/...更接近300）；已死則檢查checkpoint是否已到300，
未到用`CZC_TIME_BUDGET_SECONDS`（建議3600以上）重新nohup+disown背景
啟動接續；到300就直接算percentile（`100*mean(abs(baseline_val_ic)>
abs(random_draw_val_ic))`，門檻90.0）判CHEAP_PASS/FAIL並更新
`TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`#27。holdout本輪確認仍為
`is_holdout_consumed()=False`。本輪`git status`確認repo同時有其他
自動化來源留下的殘留變更（`.github/workflows/market.yml`/`quotes.yml`/
`data/rate_limit_state.json`/多個`research/*_run.log`），依協定不觸碰、
不納入本輪commit。

---

## 2026-09-04T06:52 — hypothesis_queue排程接續（#27複合z-score第2關） — 接手時PID 883已自然結束（checkpoint停在232/300、mtime 06:35，本輪檢查時刻06:51已無存活行程），確認progress未遺失後用`CZC_TIME_BUDGET_SECONDS=3600`重新nohup+disown背景啟動（新PID 2037），確認3分鐘內存活無crash後收工留給下一輪

`ps -p 883`（本輪查證方法沿用上一輪教訓，未用`tasklist`）確認已不存在，
`ps aux | grep python`同樣確認乾淨無殘留，判定行程已自然結束（研判是
05:27:37啟動+3600秒理論到期06:27:37後、在完成232/300那次draw之後的
下一次deadline檢查點正常退出，不是崩潰——跟06:27條目記錄的「deadline
判斷點只在draw之間檢查」機制一致）。查`data/composite_zscore_v1_random_
control_checkpoint.json`確認`draw_records`共**232筆**（比上一輪06:27
記錄的220多12筆，確認PID 883存活期間持續有效累積，資料未遺失也未被
覆寫損毀）。**剩餘68 draws**。用`CZC_TIME_BUDGET_SECONDS=3600`重新
nohup+disown背景啟動（新PID 2037），啟動後確認log正常印出「Loading
sample + computing factors」且`ps -p 2037`3分鐘內持續存活、無crash訊息，
依既有多輪驗證的「重啟成本(~20分鐘reload)遠高於等待成本」結論本輪維持
不碰這個新行程，讓它繼續在OS層背景運算。**進度估算**：以先前觀測速率
（約60~75秒/draw）估計剩餘68 draws還需要約68~85分鐘（不含本次已耗掉的
~20分鐘reload），遠超單輪工作預算。**下一輪待辦不變**：先用`ps -p
2037`（若已不存在則用`ps aux | grep python`交叉確認，不要只信
`tasklist`）確認存活狀態；存活就不碰、繼續等；已死（不論到期正常結束
或異常崩潰）則檢查checkpoint是否已到300 draws，未到則用
`CZC_TIME_BUDGET_SECONDS`（建議維持3600或更大）重新nohup+disown背景
啟動接續（checkpoint機制已驗證正確續跑，不重算已完成draw）；到300則
直接算percentile（`100*mean(abs(baseline_val_ic)>abs(random_draw_val_ic))`，
門檻90.0）判CHEAP_PASS/FAIL並更新`TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`
#27。holdout本輪確認仍為`is_holdout_consumed()=False`。本輪`git status`
確認repo同時有其他自動化來源留下的殘留變更（`.github/workflows/market.yml`
／`.github/workflows/quotes.yml`／`data/rate_limit_state.json`已修改、
另有多支非本輪產生的`research/*_run.log`與`*.py`未追蹤檔案）——依協定
規則不觸碰、不納入本輪commit，只記錄在此供後續追蹤。

## 2026-09-04T06:27 — hypothesis_queue排程接續（#27複合z-score第2關） — 確認PID 883持續存活並自然跨過自身3600秒時間預算理論到期時刻仍未結束，checkpoint從210進步到220/300，監控5分鐘無異常，維持「不重啟、等待」策略收工留給下一輪

用`ps -p 883`（非`tasklist`，記取上一輪教訓）確認PID 883仍存活（啟動於
05:27:37，本輪檢查時刻06:22~06:27橫跨其3600秒理論到期時刻06:27:37前後，
但行程並未在到期瞬間結束——研判時間預算判斷點只在完整完成一次draw之後
才檢查，若當下正在算draw本身不會被中途切斷）。本輪內輪詢5分鐘（每分鐘
一次），checkpoint`draw_records`從210停滯4分鐘後於06:27推進到220，確認
仍在持續累積、非卡死，只是單draw耗時偏長（約54~75秒/draw，比純運算量
預期慢，可能跟本機同時有其他排程軌道競爭CPU有關，未深究）。**依既有
多輪驗證的「重啟成本(~20分鐘reload)遠高於等待成本」結論，本輪維持不
碰這個行程**，讓它繼續在OS層背景運算（PID 883，`CZC_TIME_BUDGET_
SECONDS=3600`，nohup+disown，不受本次claude session結束影響）。**進度
估算**：剩餘80 draws，以本輪觀測速率（約60~75秒/draw）估計還需要
80~100分鐘才能跑滿300 draws，遠超單輪工作預算，**下一輪待辦不變**：
用`ps -p 883`（若已不存在，改用`ps aux | grep python`確認真的沒有殘留）
確認存活狀態；存活就不碰、繼續等；已死（不論是本輪之後到期正常結束，
或異常崩潰）則檢查checkpoint是否已到300 draws，未到則用`CZC_TIME_
BUDGET_SECONDS`（建議維持3600或更大）重新nohup+disown背景啟動接續
（checkpoint機制已驗證可正確續跑，不會重算已完成的draw）；到300則直接
算percentile（`100*mean(abs(baseline_val_ic)>abs(random_draw_val_ic))`，
門檻90.0）判CHEAP_PASS/FAIL並更新`TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`
#27。holdout本輪確認仍為`is_holdout_consumed()=False`。

## 2026-09-04T05:54 — hypothesis_queue排程接續（#27複合z-score第2關） — 誤判PID 883已死重複啟動PID 1126、發現後立即kill 1126避免checkpoint雙寫，確認883持續存活於170/300無資料損毀，收工留給下一輪

鎖檔非陳舊（LOCK_ACQUIRED）。接手時用`tasklist`（Windows原生指令）查
python.exe回報「無符合準則的工作」，誤判上一輪04:52啟動的PID 883已
自然到期死亡（其3600秒時間預算理論到期時間~05:52.5跟檢查時刻幾乎重疊），
因此重新用`CZC_TIME_BUDGET_SECONDS=3600 nohup ... &`啟動了新行程
（PID 1126）。**啟動後用`ps aux`（MSYS/Git-Bash指令，非`tasklist`）交叉
確認才發現PID 883其實仍存活**（`tasklist`偵測不到Git-Bash背景啟動的
python行程，是這次誤判的根因——之後幾輪若要判斷行程存活，優先用
`ps aux`/`ps -p <pid>`，不要只信`tasklist`）。發現兩個行程同時對同一份
checkpoint檔案背景運算後，立即`kill -9 1126`終止我誤啟動的那個（1126
啟動後僅約2-3分鐘、仍卡在~20分鐘資料載入階段、尚未寫入任何checkpoint，
確認`data/composite_zscore_v1_random_control_checkpoint.json`
draw_records數量在kill前後皆為**170**，未被雙寫破壞），保留原本合法
的PID 883繼續獨自運算，並清除誤啟動行程留下的空log檔
`composite_zscore_v1_random_control_run.log`（未commit進repo）。
**下一輪待辦**：確認存活用`ps -p 883`而非`tasklist`；查
`data/composite_zscore_v1_random_control_checkpoint.json`是否已到
300 draws（PID 883時間預算3600秒，啟動於05:27，理論到期~06:27，
中途若自然結束且draws未滿則需再次背景啟動接續，記得用`ps`交叉確認
而非只信`tasklist`)；到300就直接判percentile CHEAP_PASS/FAIL並更新
`TRIALS_LEDGER.md`/`HYPOTHESIS_QUEUE.md`#27。

## 2026-09-04T05:27 — hypothesis_queue排程接續（#27複合z-score第2關） — 接手時PID 1869背景行程仍存活且checkpoint從122進步到150/300，監控中途行程自然結束於155/300（25分鐘時間預算到期，非當掉），已用CZC_TIME_BUDGET_SECONDS=3600重新背景啟動（PID 883），確認無crash後收工留給下一輪

鎖檔非陳舊（LOCK_ACQUIRED），接手時上一輪（04:53）啟動的背景行程
（PID 1869）確認仍存活，checkpoint從心跳記錄的122/300推進到**150/300**
（前5分鐘觀察窗又推進到155/300），確認「不重啟、等待」策略持續有效、
行程真的能跨輪session邊界存活（04:52:31啟動，存活到至少05:27，遠超過
單輪session長度）。本輪監控5分鐘後PID 1869自然消失，checkpoint停在
155/300，研判是上一輪設定的25分鐘時間預算（`CZC_TIME_BUDGET_SECONDS=1500`）
到期後腳本自行正常結束（非崩潰，`Get-Process`確認乾淨消失、無錯誤log）。
用更大的時間預算（`CZC_TIME_BUDGET_SECONDS=3600`，1小時）重新nohup+disown
背景啟動（PID 883，05:27:37），確認3分鐘內無crash（進程持續存活、
checkpoint仍是155/300，符合預期的~20分鐘reload階段）後收工，讓行程在
OS層背景繼續累積剩餘145 draws。holdout確認仍`False`。**下一輪待辦**：
先查`data/composite_zscore_v1_random_control_checkpoint.json`是否已到
300 draws，到了就直接判percentile CHEAP_PASS/FAIL並更新
`TRIALS_LEDGER.md`+`HYPOTHESIS_QUEUE.md`#27條目；沒到且行程還活著就
沿用同一策略（不重啟、監控幾分鐘確認無crash即收工）；行程死了才重跑
（時間預算可以再拉大，避免因25分鐘上限而中途正常退出、浪費下一輪
的~20分鐘reload成本）。

取得具名鎖時發現陳舊鎖（held by pid 20592, 30.1分鐘），研判上一輪已
異常結束（未commit）。查`data/composite_zscore_v1_random_control_
checkpoint.json`：draws已從上一輪心跳的100/300推進到**122/300**
（`Get-Process python`確認上一輪行程已死，checkpoint機制再次驗證有效，
存活期間確實有累積進度，不是白跑）。本輪判斷維持既有策略（reload成本
~20分鐘遠高於每輪重啟的固定成本，不重啟只等待），用
`CZC_TIME_BUDGET_SECONDS=1500`（25分鐘）重新背景啟動
`composite_zscore_v1_random_control.py`（nohup+disown，PID 1869），
等待約3分鐘後確認行程仍存活（`ps aux`可見）且log顯示仍在
`load_sample_with_factors()`載入階段（尚未進入draw迴圈輸出），符合
已知~20分鐘reload行為、非卡死。**本輪不繼續同步等待**（避免單輪
無限期阻塞），收工讓行程在OS層背景繼續累積，下一輪先查checkpoint
是否已到300再決定判CHEAP_PASS/FAIL或繼續等待。

## 2026-09-04T03:53 — hypothesis_queue排程接續（#27複合z-score第2關） — 背景行程重啟，checkpoint 100/300

接手時確認上一輪背景行程（PID 34408）已死（`Get-Process python`查無），
checkpoint `data/composite_zscore_v1_random_control_checkpoint.json`
已從上一輪心跳的30/300推進到**100/300**（該行程存活到某個時間點後
才被session邊界終止，不是bug，是「不重啟只觀察」策略的預期結果）。
本輪判斷：既然checkpoint機制已驗證有效（不重算已完成的draws），直接
用較大時間預算（`CZC_TIME_BUDGET_SECONDS=1500`，25分鐘）重新背景啟動
`composite_zscore_v1_random_control.py`，涵蓋約20分鐘的資料重新載入
成本後應還能再累積若干draws。本輪內等待這次背景執行完成或達到時間
預算上限，再依checkpoint最終進度決定：滿300則正式判定percentile
CHEAP_PASS/FAIL並更新`HYPOTHESIS_QUEUE.md`/`TRIALS_LEDGER.md`；未滿則
記錄進度，收工留給下一輪接續（維持「重啟成本(~20分鐘reload)遠高於
等待成本」的判斷，不因為單輪要等25分鐘就提前放棄）。

## 2026-09-04 03:23 — `hypothesis_queue`排程接續#27（多因子z-score複合評分）第2關 — 確認背景行程這次真的活過session邊界，checkpoint進度10→30/300，本輪不重啟只觀察

上一輪具名鎖是陳舊鎖（held by pid 31248, 29.9分鐘）被本輪回收，研判上一輪
（03:14那則）寫完心跳後在commit+push之前就中斷，但**其背景啟動的
`composite_zscore_v1_random_control.py`（PID 34408，03:05:47啟動）這次真的
存活過了上一輪session邊界**，接手時checkpoint已從上一輪紀錄的10/300推進到
30/300，且行程仍在正常運算（log持續增長、無錯誤、CPU非0）——這修正了先前
`HYPOTHESIS_QUEUE.md`/`MARATHON_LOG.md`多次記錄的假設「headless session結束
背景行程必被終止」，至少這次沒發生，可能跟Windows工作排程器實際觸發間隔跟
行程存活時間的巧合有關，不代表以後每次都保證存活，下一輪仍要先檢查行程是否
還活著再決定要不要重啟。**本輪判斷**：既然行程活著且有進度，**重啟的成本
（~20分鐘reload）遠高於等待的成本**，本輪刻意不碰這個行程（不kill、不重啟），
只確認存活+進度後就收工，把運算時間留給背景行程繼續累積，避免像先前幾輪
因為改機制、修bug而重複支付載入成本。**尚未結案**——下一輪先查checkpoint
draw_records是否已到300（若是，直接讀`data/composite_zscore_v1_random_
control.csv`跟`main()`同一套percentile公式判CHEAP_PASS/FAIL；若行程已死
但checkpoint<300，重跑指令即可從中斷處接續，不會重算已完成的draws）。
`is_holdout_consumed()`本輪確認仍為`False`，未碰任何凍結區檔案，`git
status`檢查到其他自動化軌道（marathon三軌）留下的殘留變更（`.github/
workflows/market.yml`/`quotes.yml`/`data/rate_limit_state.json`/
`research/MARATHON_STATE.md`/`research/REPORT.md`/`research/TW_LOG.md`跟
一批`research/*_run.log`），依協定不觸碰、不納入本輪commit。

## 2026-09-04 03:14 — `hypothesis_queue`排程接續#27（多因子z-score複合評分）第2關 — 修好兩個真bug，checkpoint進度10/300，仍未結案

接手時上一輪的`composite_zscore_v1_random_control.py`背景行程跟checkpoint都
已消失（同`#4`dividend_yield_portfolio_v1踩過的模式：headless session結束
背景行程被一併終止），重新啟動後發現**這支腳本在這台機器上其實從來沒有
成功跑完過任何一個draw**，抓到兩個真bug（都是純bug修復，直接修不提案）：
①`random.Random((CONTROL_SEED, i))`用tuple當seed，這台機器的Python 3.13
(WindowsApps)不支援tuple seed，第一個draw就`TypeError`崩潰；②baseline
複合分數用`weighted_zscore_composite({sid: d}, ...)`逐檔（單一股票dict）
呼叫，內部橫斷面z-score`groupby("date")`每組只剩1檔股票，std必為NaN，
複合分數全部變NaN，導致`TRAIN/VAL mean_ic=+nan(n=0)`。兩個bug都已修好
（seed改字串、baseline改對整個`data`字典一次呼叫），修完後baseline數字
正確重現（TRAIN+0.0735/VAL+0.0826，跟`composite_zscore_v1.py`原始
CHEAP_PASS數字完全一致），checkpoint機制正常運作，本輪內累積到10/300
draws、行程持續正常運算無錯誤。**本輪因USD budget將近用盡收工，尚未
結案**——下一輪執行`python research/composite_zscore_v1_random_control.py`
會自動從checkpoint（10/300）接續（若checkpoint這次真的活過session邊界；
若又消失則從0重跑，但至少bug已修好，不會再一次draw都跑不出來）。
`is_holdout_consumed()`本輪確認仍為`False`，未修改任何凍結區檔案。

## 2026-09-04T00:15 — hypothesis_queue排程：#27隨機控制組(300draws)補checkpoint機制 — 未結案，已改善根基設施

接手時發現上一輪背景啟動的`composite_zscore_v1_random_control.py`（無checkpoint
版本）已持續運算超過45分鐘、CPU時間持續增加確認非卡死，但該腳本**300 draws
跑完才一次寫入CSV**，跟「headless呼叫結束背景行程會被終止」這個已知風險（見
`HYPOTHESIS_QUEUE.md`#4 dividend_yield_portfolio_v1的教訓）疊加，等同每次
都可能從零重跑。已仿照`dividend_yield_portfolio_v1.py`已驗證有效的checkpoint
模式（`CHECKPOINT_PATH`+`deadline`時間預算+每10筆draw落盤，且改用
`(CONTROL_SEED, i)`衍生種子讓任一draw可獨立重放，不依賴rng呼叫順序）改寫
腳本，終止舊行程（未產出任何部分結果，無進度可繼承）。**新發現**：這份
腳本每次啟動要先跑`load_sample_with_factors()`（100檔股票、全部~25個
`prepare_factors()`因子），實測光是這個載入步驟就要20分鐘以上（比先前
`dividend_yield_portfolio_v1`的~100秒載入慢一個數量級——那個腳本只算
單一因子，這個要算全部因子池），是比「300 draws本身要跑多久」更嚴重的
瓶頸：每次重啟都要重付這筆固定成本。已用大時間預算（3000秒）重新在背景
啟動（PID 33776，`composite_zscore_v1_random_control_run.log`），仍未
拿到結果，下一輪先檢查`data/composite_zscore_v1_random_control_
checkpoint.json`是否已有進度／`data/composite_zscore_v1_random_control.csv`
是否已產出完整結果，若行程已死但只有部分checkpoint，直接重跑指令即可
接續（不會重算已完成的draws），只是仍要重付一次載入成本。本輪因USD
budget將近用盡收工。

---

## 2026-09-03T23:50 — hypothesis_queue軌：接續#27多因子z-score複合評分第2關
（300-draw隨機因子組合控制）— 上一輪陳舊鎖檔（未commit）留下的
`composite_zscore_v1_random_control.py`有merge欄位殘留bug（第1個draw就
KeyError崩潰），本輪修好並背景重啟執行，收工時仍在跑（未跑完300draws，
比預期慢很多）。過程中偵測到本機另一個hypothesis_queue排程instance因
本輪耗時過久（>25分鐘）搶走陳舊鎖檔又提前結束（未commit任何東西，無
損害），純屬`marathon_lock.py`docstring自己承認的並行限制，供未來輪次
知悉。下一輪先檢查`data/composite_zscore_v1_random_control.csv`是否已
產生完整300列，據此判CHEAP_PASS/FAIL，見`HYPOTHESIS_QUEUE.md`#27最新
狀態段落。`is_holdout_consumed()`仍是False。

---

## 2026-09-03T14:22 — hypothesis_queue軌：#26全市場融資餘額成長率第1關
cheap gate（662週回補完成後首測） — 20d(4w)/60d(12w)兩種窗口定義的
融資成長率對後續TAIEX回撤幅度Spearman相關皆train/val正負號相反，60d
窗口VAL percentile=88.5接近但未過90.0門檻，依協定判**FAIL**，未進第2
關以後。佇列#1~26全數結案，接續佇列第一順位#27（多因子z-score複合
評分）。完整見`HYPOTHESIS_QUEUE.md`#26、`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#97。

---

## 2026-09-03T12:29 — hypothesis_queue軌：接續#26全市場融資餘額成長率
resumable週頻backfill（batch-size 150），本批次一次補完剩餘全部 —
成功補完剩餘88週（4週非交易日），累積進度574→662/662週
（86.7%→**100.0%，全範圍2012-05-02~2024-12-31回補完成**），資料地基
就緒。下一輪直接進第1關cheap gate（20日/60日成長率對TAIEX後續報酬/
MDD洗牌置換檢定），不用再回補。

## 2026-09-03T12:03 — hypothesis_queue軌：接續#26全市場融資餘額成長率
resumable週頻backfill（batch-size 150） — 新增109週檔，累積進度
465→574/662週（70.2%→86.7%），資料涵蓋延伸至2023-04-28，仍未涵蓋
2024關鍵年份，尚未進cheap gate，下一輪繼續回補（剩餘約88週，預估
再1輪即可補完全範圍）。

## 2026-09-03T11:35 — hypothesis_queue軌：接續#26全市場融資餘額成長率
resumable週頻backfill（batch-size 150） — 成功150/150週（17週非交易日），
累積進度315→465/662週（47.6%→70.2%），資料涵蓋延伸至2021-03，仍未達
2022/2024關鍵年份覆蓋，尚未進cheap gate，下一輪繼續回補。

## 2026-09-03T11:06 — hypothesis_queue排程接續#26全市場融資餘額成長率地基
回補 — 執行`backfill_margin_debt_market.py --batch-size 150`一批，成功
150/150週（其中11週非交易日/無資料，正常）、0封鎖0錯誤，累積進度
315/662週（47.6%，接續上一輪的149/662），資料涵蓋範圍延伸至
2012-05~2018-05。尚未涵蓋2020/2022/2024關鍵年份，尚未進cheap gate，
未結案。本輪`git status`確認`data/rate_limit_state.json`、
`research/pit.py`及多個`.log`/`composite_quality_revaccel_inst_lowvol_
sanity.py`未追蹤檔案非本輪產生，依協定不觸碰、不納入commit。
`is_holdout_consumed()`本輪未觸碰holdout。

---

## 2026-09-03T10:32 — hypothesis_queue軌接續#26全市場融資餘額成長率地基建置 — 回補進度15→149/662週（22.5%），尚未進cheap gate，下一輪繼續呼叫backfill_margin_debt_market.py

## 2026-09-03T10:41 — `hypothesis_queue`軌道排程：#26新增抓取client+resumable週頻backfill並驗證可用，回補進度2.3%（15/662週），尚未進cheap gate

接手鎖檔`LOCK_ACQUIRED`（乾淨取得，非陳舊回收）。`git pull`一開始因
`data/quotes_sinopac.json`衝突報錯，重新檢查後確認已自然解決（其他
自動化來源的fast-forward，未觸碰）。`git status`確認殘留變更同前兩輪
判斷一致：`data/rate_limit_state.json`、`research/pit.py`（新增
`cash_flow_pit()`）、多個`*_run.log`未追蹤檔案——沿用前兩輪已建立的
判斷，這批屬於另一條與#22相關的並行研究殘留、非本軌道本輪產出，**不
觸碰、不納入commit**。本輪工作：#26第1關cheap gate地基——新增
`margin_debt_market_client.py`（單日抓取+parquet快取，解決本輪新發現
的`.json()`編碼陷阱）+`backfill_margin_debt_market.py`（resumable週頻
backfill，同`backfill_t86.py`同一種設計，刻意用週頻不用逐日，理由見
`HYPOTHESIS_QUEUE.md`#26條目與腳本docstring）。驗證批次
`run_batch(batch_size=15)`成功15/15、0錯誤、0封鎖，確認schema解析
正確。累積進度15/662週（2.3%）。**尚未進cheap gate**——下一輪繼續呼叫
`backfill_margin_debt_market.py --batch-size 150`累積回補進度即可，
不用重寫。`is_holdout_consumed()`確認仍為`False`。

---

## 2026-09-03T09:24 — `hypothesis_queue`軌道排程：接手陳舊鎖檔，補完上一輪已完成但未commit的#26資料可行性查證，本輪不新開工作單位

接手鎖檔為`LOCK_STALE`（上一輪PID 56972，30.0分鐘前）。查`git status`
發現`research/HYPOTHESIS_QUEUE.md`、`research/MARATHON_LOG.md`有未
commit的修改，讀內容確認是上一輪（PID 56972，其log條目本身也記載
接手自更早一輪PID 61548的陳舊鎖）已經完整做完#26資料可行性查證（找到
正確的TWSE歷史查詢端點`/rwd/zh/marginTrading/MI_MARGN`並實測7個橫跨
2013~2026的日期確認可行），只是在最後`git commit+push`這步之前就
當掉、沒收工——這是本軌道自己的殘留進度，不是其他自動化來源。同時
存在的`data/rate_limit_state.json`、`research/pit.py`（新增
`cash_flow_pit()`）、以及一批`research/*_run.log`未追蹤檔案，上一輪
已判斷為非本軌道產出，本輪沿用同一判斷，**不觸碰、不納入commit**。
本輪動作：確認`is_holdout_consumed()`仍為`False`，只把上一輪已寫好
內容的`HYPOTHESIS_QUEUE.md`+`MARATHON_LOG.md`兩個檔案commit+push，
不額外開始#26第1關cheap gate（避免一輪塞兩個工作單位）。下一輪排程
觸發時應直接從#26第1關cheap gate（寫抓取腳本+洗牌置換檢定）開始。

---

## 2026-09-03T07:57 — `hypothesis_queue`軌道排程：#26全市場融資餘額資料可行性查證完成並確認可行（找到官方全市場歷史數字），尚未進cheap gate

接手鎖檔為`LOCK_STALE`（上一輪PID 61548，29.9分鐘前，疑似上一輪
中途失敗未收工）。`git status`發現非本輪殘留變更：`data/rate_limit_
state.json`、`research/pit.py`（新增`cash_flow_pit()`，屬於另一條
與#22相關的並行研究、非本輪`hypothesis_queue`工作）、多個其他自動化
來源留下的`*_run.log`——**不觸碰、不納入本輪commit**。`research/
HYPOTHESIS_QUEUE.md`本身也有未commit的修改，但內容是上一輪
（PID 61548）對#26資料可行性查證做到一半的紀錄，判斷是本軌道自己
的殘留進度（非其他自動化來源），**接續完成**：確認正確歷史查詢路徑
是`https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=
YYYYMMDD&response=json&selectType=ALL`（上一輪寫錯成`/rwd/zh/margin/
MI_MARGN`，少了`Trading`，回404），用`requests`+`HTTP_HEADERS`實測
回傳`tables[0]`為官方全市場信用交易統計（第3列「融資金額(千元)」即
全市場總融資餘額，比原計畫100檔樣本加總更理想），抽測2013~2026共7
個日期確認回傳合法且數字量級大致符合已知結構（2020低點/2022高點）。
**結論：資料可行性確認通過**，完整過程與下一步計畫已寫入
`HYPOTHESIS_QUEUE.md`#26條目與「排隊順序總結」項目25/26。下一輪
直接進第1關cheap gate（寫抓取腳本+洗牌置換檢定），不需要再查資料
來源。`is_holdout_consumed()`確認仍為`False`，本輪未寫`alpha.db`
（唯讀）、未修改任何凍結區檔案（`fetch.py`/`parsers.py`/`config.py`
/`alpha.db`皆未觸碰）。**本輪工作到此為止**，commit+push後收工。

---

## 2026-09-03 — 使用者裁示：#20（純毛利率GP）實作正確性健檢，四點皆查證正確，FAIL維持墓園（不重跑，不影響佇列進度）：公式（FinMind GrossProfit數值上精確等於Revenue−CostOfGoodsSold，8季diff=0.0）/PIT對齊（跟其他已CHEAP_PASS因子共用同一套機制）/涵蓋率（逐快照中位數N=56，跟f_52w_high_prox的N=60同量級，非崩塌稀釋）/方向（TRAIN/VAL兩期mean_ic皆正，跟「高GP做多」假設一致）全部確認無bug，完整過程見HYPOTHESIS_QUEUE.md#20「實作正確性健檢」章節。同時登記使用者新增的z-score複合評分假設（吸取#22硬AND組合過度擬合教訓），排入佇列#26之後接續。

## 2026-09-03T07:27 — `hypothesis_queue`軌道排程：#25月轉效應第1關cheap gate已結案FAIL，新增#26全市場融資餘額成長率regime訊號（尚未開始第1關）

接手`LOCK_ACQUIRED`（無陳舊鎖檔）。`git pull`+`git status`確認乾淨，
發現非本輪殘留變更（`data/rate_limit_state.json`/`research/pit.py`
修改+多個其他自動化來源的`*_run.log`）——不觸碰、不納入本輪commit。
新增`turn_of_month_gate.py`：TAIEX月轉窗口效應（N=3/N=4兩種定義），
用實際交易日序列判定窗口位置、N=200次洗牌置換檢定。結果：N=3
TRAIN percentile=94.0過關但VAL percentile=28.0且**train/val正負號
反轉**；N=4同樣train/val正負號反轉且TRAIN未過門檻。依協定第1關
cheap gate標準判**FAIL**，已寫入`STRATEGY_GRAVEYARD.md`+
`TRIALS_LEDGER.md`#96+`HYPOTHESIS_QUEUE.md`#25條目跟排隊順序總結。
重新查證#5/#6/#8/#10三個外部依賴：題材動能榜PIT引擎仍未建置、佇列裡
至今無任何候選通過完整GATE_SEQUENCE可供regime overlay套用——兩個
阻塞條件均未改變，判定佇列實質已空，設計新假設軸**#26全市場融資
餘額成長率當槓桿/擁擠度regime訊號**（機制類別：市場結構性槓桿/
擁擠度，跟已測過的價格/報酬衍生timing訊號、日曆結構效應都不同），
已登記進`HYPOTHESIS_QUEUE.md`，尚未開始第1關（下一輪第一步是資料
可行性/樣本代表性查證，不是直接跳去測訊號）。`is_holdout_consumed()`
確認仍為`False`，本輪未觸碰VAL_END以後任何資料。

---

## 2026-09-03T06:54 — `hypothesis_queue`軌道排程：重新確認外部依賴未解鎖，佇列實質已空，新增#25月轉效應（尚未開始第1關）

接手鎖檔為`LOCK_STALE`（上一輪PID 50392，30.0分鐘前）。`git status`確認
非本輪殘留變更（`data/rate_limit_state.json`/`research/pit.py`修改+
多個其他自動化來源的run.log）不觸碰、不納入本輪commit。讀`HYPOTHESIS_
QUEUE.md`確認#1~24已全數結案（FAIL或外部依賴阻塞），依協定重新逐一
查證#5/#6/#8/#10三個外部依賴：①`BACKLOG.md`確認題材動能榜PIT回測
引擎仍未建置（`momentum_board`狀態仍是「紙上交易中」，#6/#8依附此
地基仍動不了）；②B25/B26已於2026-09-02完成，但#5/#10真正阻塞點是
「佇列裡至今沒有任何一條假設通過完整GATE_SEQUENCE可供regime overlay
套用」，這個條件未變。**確認三個依賴皆未解鎖，判定佇列實質已空**，
依協定設計新假設軸：**#25月轉效應（Turn-of-Month Effect，指數層級、
非選股）**——機構現金流時點（月薪提撥/基金申購集中月初、月底window
dressing）驅動的日曆結構效應，經濟機制跟已測過的三種「非選股」timing
機制（#10大盤均線/波動度開關、#15自身已實現波動度、#19美股隔夜報酬
外溢）皆不同，也跟已FAIL的FUT軌`fut_weekday_effect`（週末效應）不同
類別，本專案至今未測過。完整假設定義+下檔保護要求已寫入`HYPOTHESIS_
QUEUE.md`新增#25章節與「排隊順序總結」項目25，本輪只登記假設、未寫
任何程式碼、未跑任何測試（依協定「佇列已空」情境的工作單位定義）。
`is_holdout_consumed()`確認為`False`。**本輪工作到此為止**，下一輪從
#25第1關cheap gate開始（`fetch_yf_index("^TWII")`+實際交易日曆判定
月轉窗口，不用自然日期近似），不跳關。commit+push後收工。

---

## 2026-09-03T06:35 — `hypothesis_queue`軌道排程：#23狀態順序修正+#24（除權息季節行為效應）已結案FAIL

接手鎖檔為`LOCK_STALE`（上一輪PID 66908，29.9分鐘前）。`git status`發現
多個其他自動化來源殘留（`composite_*`/`f52w_high_*`/`dividend_yield_*`
等run.log、`data/rate_limit_state.json`、`research/pit.py`修改），依協定
不觸碰、不納入本輪commit。**先修正一個文件不一致**：`HYPOTHESIS_QUEUE.md`
#23段落內兩則狀態（T05:52「未跑完」vs「已結案:FAIL」）文字順序跟實際
時序相反（`MARATHON_LOG.md`確認T05:56的FAIL判定才是最終結論），已調整
順序避免誤導。**#24（除權息季節行為效應）第1關**：新增
`ex_dividend_seasonal_sanity.py`（用原始未還原收盤價，複用
`adjust.py::adjustment_events()`）。100檔快取樣本62檔可用，443筆純
現金股利事件（TRAIN267/VAL176）。Sanity PASS（7-9月旺季事件佔比69.8%
符合已知結構事實、除息跌幅vs理論殖利率rho=+0.6858強確認資料完整性）。
三個cheap gate（殖利率→除息前報酬/殖利率→除息後報酬/旺季vs非旺季
填息率洗牌檢定）皆FAIL，percentile分別32.6/83.0(正負號相反)/
87.0-86.2-60.6，皆未過90.0門檻（87.0/86.2雖接近仍依鐵律判死）。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#94(補#23核心比較)/#95。
**佇列#20~24（使用者裁示新增5條）全數結案，剩餘#5/#6/#8/#10仍卡外部
依賴，下一輪需先確認是否解鎖，未解鎖則判定佇列實質已空、需設計新
假設軸**。本輪因USD budget將近用盡，commit+push後收工。

---

## 2026-09-03T05:56 — `hypothesis_queue`軌道第二十六輪排程：#23（Piotroski F-score價值榜排雷閘門）已結案FAIL

接手時取得鎖檔為`LOCK_STALE`（上一輪PID 55044，29.8分鐘前，疑似寫完
#23上一則狀態後未及commit就中斷）。`git status`發現多個其他自動化來源
留下的未commit殘留（`composite_*`/`f52w_high_*`/`dividend_yield_*`等
run.log與腳本），依協定不觸碰、不納入本輪commit。發現前一輪留下**4個
重複的`piotroski_fscore_gate_v1.py`背景行程**同時在跑（headless呼叫
結束時背景行程未被清理，累積成殭屍行程），本輪確認時4者皆已自然執行
完畢，`data/piotroski_fscore_gate_v1_results.csv`已產出且內容完整可用。
**核心比較**（原始`value_board_v2` vs +F-score gate）：自適應選定
F>=6（最寬鬆門檻）。原始：TRAIN alpha=+6.26%(p=0.2672)/mine_rate=25.3%；
VAL alpha=+12.38%(p=0.1441)/mine_rate=16.9%。+gate：TRAIN alpha=+7.92%
(p=0.4743)/mine_rate=29.1%；VAL alpha=+5.24%(p=0.1772)/mine_rate=5.7%
（VAL return由+85.52%驟降至+33.31%，交易數718→98）。依#23事前訂的
「兩期alpha從不顯著轉顯著+地雷率下降才算證明」判準，本次兩期alpha
p值皆變差、地雷率一升一降無統一改善，**判FAIL**。完整見
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#94、`HYPOTHESIS_QUEUE.md`
#23。**佇列#23結案，接續佇列第一順位#24（除權息季節行為效應），尚未
開始第1關**。本輪即將commit+push收工，下一輪從#24第1關sanity開始。

---

## 2026-09-03T05:52 — `hypothesis_queue`軌道：#23接續，發現並修正「重複launch造成4個併發行程」的執行方式問題，仍未跑完

接續上一輪（04:55T那則）留下的`piotroski_fscore_gate_v1.py`背景行程。本輪
一開始誤判上一輪的背景行程已死（`tasklist //FI`指令回傳亂碼、疑似「查無
符合」），依此誤判連續嘗試了三次新的啟動方式（`nohup ... &`、前景阻塞
590秒逾時後被工具自動轉背景、`-u`無緩衝再試一次），結果造成**同一支
腳本同時有4個行程在跑**（PID 9991來自上一輪04:54:30、加上本輪誤啟動的
10324/10393/10722），都對同一個500MB pickle快取+同一個輸出CSV路徑
競爭讀寫。用`ps -ef`（不是`tasklist`——這個環境的python是MSYS/Git
Bash底下跑的Windows process，`tasklist`的篩選語法在這個shell裡對中文
字型輸出有問題，看起來像「查無資料」但其實不準確，`ps -ef`才是可信的
查證方式）才發現這個問題，已用`kill -9`把本輪誤開的3個多餘行程砍掉，
只留最早的PID 9991繼續跑（存活58分鐘以上、`data/raw/`裡有對應這支
行程早期需要新抓的股票財務資料parquet，2026-09-03 05:08-05:09寫入，
證明它真的在做事，不是卡死行程）。**這輪的教訓（已達成，供下一輪
使用）**：這個環境的背景行程**確實會跨tool call存活**（不像先前
dividend_yield/f52w_high兩則紀錄推論的「headless呼叫結束就被砍掉」
——那個推論可能只適用於`nohup command &`這種shell語法本身沒有真的
detach成功的情況，不代表這個環境的背景行程機制整體不可靠）。**下一輪
第一件事要做**：先用`ps -ef | grep piotroski_fscore_gate_v1.py`確認
有沒有既有行程還活著，**絕對不要在沒查證前就重新啟動新的一份**，避免
再次製造多重併發競爭同一輸出檔案的問題。若PID 9991這次仍在跑（尚未
逾時陣亡），直接輪詢等它跑完即可，不要重啟。本輪因USD budget即將用盡
收工，**尚未結案**，`data/piotroski_fscore_gate_v1_results.csv`仍不
存在。

---

## 2026-09-03T04:55 — `hypothesis_queue`軌道：#23 Piotroski F-score價值榜排雷閘門，接續「原始vs+gate比較」步驟，本輪未跑完

延續#23（地基+第1關sanity已PASS，見`TRIALS_LEDGER.md`#93）「下一步」——
新增`piotroski_fscore_gate_v1.py`：重用既有B24-500快取
（`value_board_v2_sample_cache_liquidity500.pkl`，不重抓價量）+對500檔
各自呼叫`piotroski_fscore_sanity.py::_fscore_components()`算F-score+asof
join回每檔股票的日曆，疊加在`compute_scores_v2()`候選池上做F-score門檻
（自適應選F>=8/7/6，取平均候選數>=TOP_N(20)裡最嚴格的門檻），跑TRAIN+
VALIDATION兩期「真實回測」（本輪刻意跳過100次隨機控制組，先看方向性
alpha/mine_rate證據，見腳本docstring完整理由），跟既有基準
（`data/value_board_v2_pit_backtest_liquidity500_full.csv`，原始版TRAIN
alpha p=0.2672／VAL alpha p=0.1441皆不顯著）比較。**本輪執行後未觀察到
完成**：先用shell層級`nohup ... &`背景執行，套用先前dividend_yield/
f52w_high已知的教訓（headless呼叫結束時shell層背景行程被一併終止，
process成功exit 0但log完全空白，等同沒跑），改用Bash工具原生
`run_in_background`機制重跑一次；`tasklist`確認python3.13.exe行程仍在
執行中（記憶體占用~741MB，跟500MB pickle快取載入量級吻合，非卡死），
但受本輪剩餘時間/USD預算限制，未等到腳本印出任何一行輸出或完成，
`piotroski_fscore_gate_v1_run.log`仍是空檔案。**尚未結案**——下一輪
直接重跑`python research/piotroski_fscore_gate_v1.py`，若這次背景行程
真的沒有存活下來，資料層仍受益：500檔中先前已快取過財報的股票（本機
`data/raw/*.parquet`）不需要重抓，只有真正缺快取的股票需要付節流時間，
所以重跑不是從零開始，跟checkpoint機制精神類似（雖然這支腳本本身沒有
落盤checkpoint，是靠底層parquet快取自然達成部分續跑效果）。

---

## 2026-09-03T04:27（系統時間，hypothesis_queue排程，第二十四輪）— #23 Piotroski F-score當價值榜排雷閘門，地基完成+第1關sanity — SANITY_PASS（非最終判準）

本輪先補上一輪遺留的待辦：把上一輪（#22）的FAIL結果同步進「排隊順序
總結」章節的正式編號清單（19~22四項，上一輪只更新了條目本身、未同步
清單，已補齊）。接著開始#23：先查證FinMind免費層是否有齊全的Piotroski
F-score九項指標所需欄位（`TaiwanStockFinancialStatements`/
`TaiwanStockBalanceSheet`/`TaiwanStockCashFlowsStatement`，直接對2330
列舉`type`值確認）——7項有直接對應欄位，2項需要文件化proxy（CFO近似
FCF、CapitalStock面額股本近似股數），9項皆可算，資料源這關不卡。新增
`piotroski_fscore_sanity.py`：100檔快取樣本47檔可用（比#22少，因
F-score需要更多欄位同時齊全，天然涵蓋率更嚴），121個快照，F-score分布
mean=3.29/median=3.26（非退化常數），但F>=7候選池均值僅1.2%、F>=8僅
0.0%（一般樣本未經value_board_v2價值篩選，符合Piotroski原始論文預期
——他的應用場景本來就是低淨值市值比價值股宇宙，不是全市場）。判定
SANITY_PASS（地基就緒），**未進第2關以後**——下一步是套用value_board_v2
既有排序候選池比較「原始版」vs「+F-score gate」兩版本alpha/地雷率，
待下一輪接續。完整見`HYPOTHESIS_QUEUE.md`#23、`TRIALS_LEDGER.md`#93。

`git status`確認`data/rate_limit_state.json`有未commit修改+多個
`research/*_run.log`未追蹤檔案，判斷是其他自動化來源的殘留，本輪未觸碰、
未納入commit。`is_holdout_consumed()`確認仍為`False`。

---

## 2026-09-03（hypothesis_queue排程，第二十三輪）— #22品質x營收加速x法人吸籌x低波動合取訊號第1關sanity — FAIL（合取候選池14.0%快照有候選，門檻30.0%未過，四gate近似獨立無協同，推翻假設前提；上一輪鎖檔陳舊30.1分鐘被回收，疑似上一輪跑到一半中斷；本輪因USD預算將近用盡未同步更新「排隊順序總結」章節數字列表，僅更新#22條目本身，下一輪需補上）

## 2026-09-03（系統時間，見commit時間戳）— hypothesis_queue軌道：#21月營收「意外」漂移×低關注度第1關cheap gate — FAIL（兩組皆未過，快殺結案）

新增`revenue_trend_surprise_low_attention.py`（改造已FAIL的#14：意外定義
從YoY改成trailing 12個月線性趨勢外推殘差+樣本依近20日均成交值中位數切成
低/高關注度兩組分開跑cheap gate）。開發過程中修好一個bug：
`adjusted_price_series()`的volume欄位名依資料來源分岔（yfinance路徑
`volume`、FinMind回退路徑`Trading_Volume`），原本只認`volume`會漏篩約
一半走FinMind路徑的樣本股票，已修正兩種欄位名都接受。結果：低關注度組
null percentile=31.2、高關注度組89.8（皆未過90.0門檻），且**方向與假設
預期相反**（低關注度組理應更強、實際更弱）——兩組皆FAIL，沒有分組差異，
依`HYPOTHESIS_QUEUE.md`#21原話判死。完整見`STRATEGY_GRAVEYARD.md`、
`TRIALS_LEDGER.md`#91、`HYPOTHESIS_QUEUE.md`#21。**佇列#21結案，接續
佇列第一順位#22（品質×營收加速×法人吸籌複合訊號+低波動閘門），下一輪
從第1關sanity開始（含四個濾網門檻值訂定），不跳關。**

`git status`確認`data/rate_limit_state.json`有未commit修改+多個
`research/*_run.log`未追蹤檔案，判斷是其他自動化來源的殘留，本輪未觸碰、
未納入commit。`is_holdout_consumed()`確認仍為`False`。

---

## 2026-09-03T13:47（系統時間，見commit時間戳）— hypothesis_queue軌道：#20純毛利率因子Gross Profitability第1關cheap IC gate — FAIL（第1關未過，快殺結案）

本輪接手時發現`hypothesis_queue`具名鎖為陳舊鎖（held by PID 57132，
60.2分鐘沒更新），依協定判定為上一輪疑似失敗/中斷，回收後繼續（`ps`
未再交叉確認該PID，僅依鎖檔本身60分鐘逾時判斷，跟協定第0節的陳舊
判定機制一致）。`git status`發現`data/rate_limit_state.json`有未commit
的修改+多個`research/*_run.log`未追蹤檔案，判斷是其他自動化來源（三軌
馬拉松或先前輪次）的殘留，本輪未觸碰、未納入commit。

新增`factors.py::_gross_profitability()`（GrossProfit[`quarterly_pit`]/
TotalAssets[`balance_sheet_pit`]，同`_roe_stability`merge模式）+
`prepare_factors()`「(x)」段落+`factor_ic_gross_profitability.py`。結果：
TRAIN mean_ic=+0.0030 IR=+0.024(n=74)、VAL mean_ic=+0.0114 IR=+0.089
hit_rate=0.62(n=47)，train/val同號但幅度皆接近雜訊，null percentile=
48.4（門檻90.0，遠未過且低於50）。依協定第1關cheap gate標準判**FAIL**，
未進第2關以後。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#90、
`HYPOTHESIS_QUEUE.md`#20。**佇列#20結案，接續佇列第一順位#21（月營收
「意外」漂移×低關注度，改造已陣亡的#14），下一輪從第1關sanity開始。**

---

## 2026-09-03T09:xx（系統時間，見commit時間戳）— hypothesis_queue軌道：#19跨市場美股隔夜報酬外溢效應第2關以後 — FAIL（第6關逐年一致性未過，快殺結案）

新增`spillover_overlay_v1.py`，把#19第1關已CHEAP_PASS（`TRIALS_LEDGER.md`
#88）的相關性轉成具體擇時規則（`exposure=0.3 if 美股當日收黑 else 1.0`，
THRESHOLD=0.0/EXPOSURE_DOWN=0.3事前綁定非搜尋）。第2關隨機控制組PASS
（打亂exposure時序N=100，TRAIN/VAL真實值percentile皆100.0）、第3關參數
密集高原PASS（49點網格78%正報酬），**第6關逐年一致性FAIL**（TRAIN期
2010~2020共11年僅4年正報酬，遠低於>=5/6門檻，且TRAIN總報酬-22.10%大幅
落後同期買進持有+79.42%），依協定快殺結案，未進第4/7/8/9關。根因：
THRESHOLD=0.0觸發頻率近乎逐日，把防禦型overlay變成高頻方向賭注，被
切換成本+多頭格局踏空侵蝕。不泛化成相關性沒用——第1關CHEAP_PASS不受
影響。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#89、
`HYPOTHESIS_QUEUE.md`#19。**佇列#19結案，接續佇列第一順位#20（純毛利率
因子Gross Profitability），下一輪從第1關sanity開始。**

---

## 2026-09-03T00:54 — hypothesis_queue軌道：#19跨市場美股隔夜報酬外溢效應第1關cheap gate — CHEAP_PASS（本佇列證據最強候選，尚未結案）

新增`spillover_overnight_gate.py`：對每個台股交易日t，配對「日曆日期
嚴格早於t的最近一個美股(^GSPC)交易日」隔夜報酬當訊號，跟台股(^TWII)t日
close-to-close報酬測時序相關（非cross-sectional）。時序對齊sanity先過
（3662組配對，訊號日到台股日曆天數差min=1/max=5/median=1.0，無未來
函數）。TRAIN(<=2020-12-31,n=2693) Pearson r=+0.3987(p<0.0001)、洗牌
null(N=500)percentile=100.0；VAL(2021-2024,n=969) Pearson r=+0.4550
(p<0.0001)、percentile=100.0，Spearman兩期同號同量級。三項cheap gate
判準全過，**判CHEAP_PASS**——相關係數量級(0.40~0.46)是本佇列至今第1關
證據最強的候選（前兩個CHEAP_PASS股利率/52週高點的p值也顯著但這次
r量級/percentile更乾淨）。**這只是第1關，不是最終PASS**——依「有界
工作單位」原則本輪到此收工，下一輪從第2關以後開始：把訊號轉成具體
台股當日曝險擇時規則、比照`regime_overlay.py`(#10)整合、走完整成本
敏感度/leave-one-out/逐年一致性/alpha顯著性拆解。完整見
`HYPOTHESIS_QUEUE.md`#19、`TRIALS_LEDGER.md`#88。

---

## 2026-09-03T00:39 — 使用者裁示登記5條新假設#20~#24進佇列（登記，未執行）：純毛利率因子(GP)/月營收意外×低關注度(改造#14)/品質×營收加速×法人吸籌複合訊號+低波動閘門/Piotroski F-score排雷閘門/除權息季節行為效應——原始編號#18~#22跟馬拉松已自主佔用的#18/#19衝突，重新編號#20~#24，接續#19之後依序執行。下一輪（或使用者本人）可從#20第1關sanity開始，其餘照協定自主往下跑，只有全部關卡過關要部署才停下問。

## 2026-09-03T00:22 — hypothesis_queue軌道：接手崩潰排程，補完#18短期反轉（1週）FAIL判定commit

本輪`marathon_lock.py acquire`回傳乾淨`LOCK_ACQUIRED`（非陳舊），但
`git status`發現上一輪（T23:59那則心跳，見下方）已經把#18判死+新增#19
假設的全部文件內容（`HYPOTHESIS_QUEUE.md`/`MARATHON_LOG.md`/
`STRATEGY_GRAVEYARD.md`/`factors.py`/`factor_ic_short_term_reversal_1w.py`）
寫好並staged，卻沒有commit就結束（推測上一輪執行到commit那一步之前
中斷，鎖檔則正常釋放）。逐項核對：`TRIALS_LEDGER.md`#87已存在於最新
commit（35e680f，代表這筆是更早前另一個併行實例寫入並commit的，跟本次
staged的其餘檔案指向同一組結果、數字一致，不是缺漏）；`STRATEGY_
GRAVEYARD.md`的#18條目與`HYPOTHESIS_QUEUE.md`的#18結案文字、新增#19
章節內容互相引用一致；`factors.py`新增段落乾淨（僅新增`SHORT_TERM_
REVERSAL_1W_WINDOW`常數+一段`f_short_term_reversal_1w`計算，未動到
既有因子）；`is_holdout_consumed()`確認仍為`False`。判定這批staged
變更是完整且一致的已完成工作單位，非其他自動化來源的殘留（另有
`data/rate_limit_state.json`與一批`research/*_run.log`未追蹤檔案，
研判是三軌馬拉松或其他背景行程留下的殘留，本輪未觸碰、未納入commit），
本輪直接補commit+push，不重跑#18測試、不額外開工#19第1關（依協定
「一輪只做一個有界工作單位」，補完crash commit本身就是這輪的工作單位，
#19第1關留給下一次排程觸發接續）。

## 2026-09-02T23:59 — hypothesis_queue軌道：#18短期反轉（1週）第1關cheap IC gate — 已結案FAIL（`f_short_term_reversal_1w`train/val同號但null percentile=41.3遠低於90.0門檻且低於50，跟已FAIL的1個月窗口版本#46刻意做出區隔，見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#87），佇列#1~18原始15條項目全部結案。判定佇列實質已空後設計新假設軸#19（跨市場美股隔夜報酬外溢效應，指數層級擇時、非選股，資料可行性已用既有`yf_price_client.py::fetch_yf_index()`確認），僅登記假設尚未開始第1關，剩餘#5/#6/#8/#10仍卡外部依賴。本輪同時發現residual git狀態有其他自動化留下的殘留（`f52w_high_gates.py`等log/腳本檔），未觸碰、未納入本次commit。

## 2026-09-02T23:58 — hypothesis_queue軌道：補齊#17第3/5/6關（本輪與另一
併行實例同時作業，發現對方已完成第2/7/8關並結案FAIL，本輪不重工只補缺）

本輪接手時發現本機同時有另一個`hypothesis_queue`相關實例正在/剛完成同一
條假設的作業（`marathon_lock.py`本輪`acquire`回傳乾淨`LOCK_ACQUIRED`非
陳舊，但工作目錄同時出現另一方寫入的`f52w_high_portfolio_v1.py`存活背景
行程PID 5099、以及T23:48的心跳條目與#17已結案FAIL的完整`HYPOTHESIS_
QUEUE.md`/`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#85條目——研判是兩個
`AlphaHypothesisQueue`排程觸發時間點重疊，或另一方鎖檔生命週期與本輪不
同步，本輪未深入追查根因，僅誠實記錄這個現象供之後排查用）。查證後對方
的第7關數字（TRAIN alpha p=0.3155、VAL alpha p=0.0831）跟本輪自己獨立
算出的完全一致，未重工。**本輪唯一新增的是對方沒做的第3/5/6關**：執行
本機已存在但未跑過的`f52w_high_gates.py`——第3關參數密集高原PASS（8/8
網格點皆正報酬）、第5關leave-one-out PASS（拿掉2017年後複利仍正+48.29%）、
第6關逐年一致性FAIL（6年中僅4年正報酬，未達5/6門檻）。已補進
`TRIALS_LEDGER.md`#86、`STRATEGY_GRAVEYARD.md`#17條目補充段落，不影響
已結案的FAIL判定（第6關FAIL跟第7關alpha不顯著是兩個獨立死因，互相強化）。
**未觸碰對方已寫好的`HYPOTHESIS_QUEUE.md`#17狀態段落跟#18起步作業
（`factor_ic_short_term_reversal_1w.py`，對方似乎已在推進，本輪不重複
開工#18，交給對方或下一輪接續）。**

## 2026-09-02T23:48 — hypothesis_queue軌道：接續#17（52週高點接近度）走完第2/7/8關 — 結案FAIL

`CLAUDE.md`「提案先於執行」規則已由使用者於本輪前補上第二版更精確裁示
（「適用範圍界線」段落），明確確認`hypothesis_queue`不受此規則約束，
上一輪（22:27）因誤讀第一版裁示而暫停在#17第1關之後，本輪確認裁示已
到位，接續往下跑。

新增`f52w_high_portfolio_v1.py`（逐字比照`dividend_yield_portfolio_v1.py`
架構+checkpoint可續跑機制），本輪內連續呼叫腳本5次累積進度（TRAIN隨機
控制組0→21→44→64→83→100/100，VALIDATION 0→60→100/100；第五次呼叫因
外層timeout中途中斷、log為空，但checkpoint機制確認資料完整落盤未遺失，
下一次呼叫接續無誤）。結果：TRAIN alpha+10.84%(p=0.3155)、VAL
alpha+10.47%(p=0.0831)，隨機控制組percentile兩期皆100.0，腳本內建判準
印出表面PASS，但依既有alpha顯著性+beta拆解評判標準（PEAD/股利率/
Weinstein同一把尺）人工override判**FAIL**——兩期alpha皆未跨過p<0.05
門檻（VAL p=0.083是本佇列目前所有FAIL案例中最接近顯著的一次）。已寫入
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#85、`HYPOTHESIS_QUEUE.md`
#17條目與「排隊順序總結」章節。**佇列#17結案，接續佇列第一順位#18
短期反轉（1週），下一輪從第1關cheap IC gate開始。**

## 2026-09-02T22:27 — hypothesis_queue軌道：修正#16文件內部矛盾（誤重跑
記錄vs已結案FAIL）+ #17（52週高點接近度）第1關cheap IC gate測試 — 第1關
CHEAP_PASS（TRAIN IR+0.389/VAL IR+0.465、null percentile=100.0），但發現
`CLAUDE.md`新增「提案先於執行」鐵律與本自動化軌道運作前提衝突，本輪到
此為止不繼續往第2關推進，待使用者裁示。

**本輪做了什麼**：
1. 讀`HYPOTHESIS_QUEUE_PROTOCOL.md`+`CONSTITUTION.md`，`git pull`+
   `git status`確認乾淨（發現一批其他自動化留下的log殘留檔+
   `data/rate_limit_state.json`變動，不是本輪產生，未觸碰、未納入commit），
   取得`hypothesis_queue`具名鎖（`LOCK_ACQUIRED`，非陳舊）。
2. 讀`HYPOTHESIS_QUEUE.md`挑下一條，發現#16（配對交易）有兩則互相矛盾的
   狀態紀錄：一則寫「已結案FAIL」（引用`TRIALS_LEDGER.md`#83），另一則
   （T21:28時間戳）寫「第1關sanity PASS，非最終判定，下一輪從第2關開始」。
   查證`TRIALS_LEDGER.md`#83與`STRATEGY_GRAVEYARD.md`確認FAIL才是真正
   結案狀態，T21:28那則是某輪誤重跑`pair_trading_sanity.py`後補寫、數字
   完全重複、未推翻原判定——已在`HYPOTHESIS_QUEUE.md`該處加註修正說明，
   不重啟#16、不再跑第2關。
3. 依「排隊順序總結」正確接續#17（52週高點接近度，George & Hwang 2004
   錨定不足）。新增`factors.py::prepare_factors()`「(v)」段落
   （`f_52w_high_prox`：收盤價/252日滾動最高價）+`factor_ic_52w_high.py`。
   執行結果：TRAIN mean_ic=+0.0760 IR=+0.389(n=74)、VAL mean_ic=+0.0863
   IR=+0.465 hit_rate=0.68(n=47)、train/val同號、null percentile=100.0
   （門檻90.0）——三項判準皆過，**第1關CHEAP_PASS**，是本佇列第二個通過
   第1關的候選（第一個是#4股利率因子`f_dividend_yield_ttm`，portfolio
   層構造後來FAIL）。
4. **執行到這裡時，發現`C:\alpha\alpha-app\CLAUDE.md`已被更新**，新增
   最高優先鐵律「提案先於執行（總司令核准制，2026-09-02使用者裁示）」：
   「任何『更動、優化、調整參數/頻率/架構、或新建議』，一律先想清楚，
   寫成簡短提案...經核准才執行，嚴禁自作主張直接改」，例外只有「純bug
   修復」跟「使用者已明確交辦的任務」。

**為什麼在這裡停下（判斷理由）**：這條新鐵律的字面範圍（任何新建議/
更動都要先提案核准）跟`hypothesis_queue`這整個無人值守排程軌道的設計
前提直接衝突——這類軌道存在的理由就是「終結無人接手就停」，運作方式
是Windows工作排程器定期喚醒headless instance、無人在場、依協定自主
往下跑，只在三個明訂條件（1000draws規模/survivorship-free宇宙/不可逆
或花錢操作）才停下來問。如果新鐵律適用於這條軌道，那麼「繼續往第2關
推進」本身就是需要先提案的「新建議/更動」，而headless instance在
無人的情況下不可能真的等到「核准」——我判斷不應該自己解讀「這個協定
本身視同已交辦所以不受新規則約束」就逕自往下做，比照協定既有「三個
停下條件」的處理精神：把問題完整寫下來、commit+push、正常收工，不
空等、不假裝繼續按舊模式跑下去。

**已完成、確定沒有疑慮的部分（本輪已commit的產出）**：#17第1關cheap IC
gate的CHEAP_PASS結果、#16文件矛盾的修正——這些是「執行既有協定既定
步驟、記錄已完成測量結果」，不是「提出新建議」，不受影響。

**留給下一輪/使用者的問題**：這條新鐵律是否適用於`hypothesis_queue`／
三軌馬拉松這類原本設計成自主執行的無人值守排程軌道？若適用，這些軌道
之後每次觸發應該怎麼運作（例如改成「做完當前工作單位就停下寫提案，不
再自動接續下一關/下一條假設，直到使用者核准」）？若不適用（例如新鐵律
主要針對互動式session的臨場決策，不含這類已經過使用者事先明確授權、
訂有明確停下條件的自動化協定），下一輪可以直接從#17第2關隨機控制組
接續。**`is_holdout_consumed()`確認為`False`。**

---

## 2026-09-02T21:27 — `hypothesis_queue`排程接續：佇列#16同產業配對交易/統計套利第1關sanity(PASS)+第2關隨機控制組(N=100) — 已結案FAIL（相關係數篩選相對隨機挑12對配對無顯著加值，percentile=56.0/39.0遠低於90.0門檻，被控制組拆穿的縮小候選池型偽影），接續佇列第一順位#17。附註：本輪取鎖時上一輪鎖檔已陳舊，已回收接手；`pair_trading_sanity.py`是上一輪留下的未commit殘留，本輪確認邏輯正確、重跑確認determinism後沿用未重工。（這行時間戳跟上一則T21:28的排列順序看似倒反，是因為本輪自己的行程在收工commit前意外中斷、隔了一段時間才由接手的人補commit——內容本身在21:27~21:28這個時間窗內完成，不是憑空捏造時間，見下方TRIALS_LEDGER.md #83與STRATEGY_GRAVEYARD.md對應條目核對）

## 2026-09-02T21:28 — `hypothesis_queue`排程接續#16同產業配對交易/統計套利 — 第1關sanity PASS（100檔樣本72檔可用、15產業群組、90候選配對、相關係數篩選0.70門檻篩出12組、555次進場事件全部組合皆有觸發、方向性sanity收斂比例中位數85.5%），非最終判定，下一輪從第2關隨機控制組開始，見`HYPOTHESIS_QUEUE.md`#16與`pair_trading_sanity.py`

## 2026-09-02T07:23 — hypothesis_queue軌：確認佇列#5/#6/#8/#10外部依賴無新進展（B24-500已跑完但不及格、B25/B26未執行、題材動能榜PIT引擎仍未建），判定佇列實質已空，設計新假設軸#16同產業配對交易/統計套利（market-neutral均值回歸，與已測10條方向性排序假設及#10/#15兩種timing機制皆不同構造） — 結果：僅登記假設定義進`HYPOTHESIS_QUEUE.md`，尚未寫程式碼/未跑測試，下一輪從第1關sanity開始。

## 2026-09-02T07:12 — `hypothesis_queue`排程接續#7低波動(TW策略層)十分位多空深挖 — 已結案FAIL（VAL期隨機控制組percentile=85.0未過90.0門檻+兩期alpha不顯著），佇列#7~#15全數結案，剩餘#5/#6/#8/#10皆外部依賴阻塞，下一輪需判斷是否設計新假設軸

（附註：本輪取`hypothesis_queue`具名鎖時鎖檔已陳舊約30分鐘被回收——研判
上一輪是寫完`HYPOTHESIS_QUEUE.md`#7初始狀態、啟動`deep_dive_f_low_vol.py`
背景執行後、還沒commit就中斷。本輪確認該背景行程（PID 16888）**真的還
活著**（跟先前`dividend_yield_portfolio_v1.py`案例不同，那次背景行程在
輪次交接時被一併終止），輪詢等待約12分鐘後其自然執行完成，未重工也未
中途干預，讀取完整輸出後做出判定，詳見`HYPOTHESIS_QUEUE.md`#7、
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#82三處同步更新。）

## 2026-09-02T05:57 — `HYPOTHESIS_QUEUE_PROTOCOL.md`排程首次試跑：佇列#15
波動度目標化Vol-Targeting第1關sanity+第2關輕量版隨機控制組 — 結果：**FAIL**

新增`vol_targeting_v1.py`（新增，可重複執行）——測試對象是TAIEX買進持有
本身（不依賴任何選股候選，跟`regime_overlay.py`#10同一個做法），60交易日
滾動已實現波動度、目標年化波動率15%、`exposure=clip(target/realized,0,
1.0)`（刻意不允許槓桿）、`exposure.shift(1)`避免未來函數。**第1關sanity**：
機制方向正確（realized_vol與exposure相關係數=-0.946）、exposure非常數
（60.6%天數被上限1.0截斷）、MDD全期間確實改善（-31.63%→-27.34%），**但
Sharpe/Sortino/Calmar在TRAIN/VAL/全期間全部比買進持有差**——先於第2關就
浮現警訊，本輪判斷這個訊號夠重要不能只當infra完成帶過，加做一個計算成本
低的第2關（輕量版隨機控制組，打亂exposure時序N=100draws）。**第2關結果**：
真實（依realized_vol計時）曝險序列的Sharpe percentile=8.0、CAGR
percentile=3.0，遠低於90.0門檻且低於50——92%/97%的隨機打亂時序反而表現
更好，只有MDD percentile=90.0，但單項改善不足以證明timing本身有加值（降
平均曝險本身幾乎必然壓低MDD）。依協定快殺標準「觀測層級就無訊號」判
**FAIL**，未進第3關以後。死因研判：60日滾動已實現波動度是落後指標，市場
V型/U型復甦時價格常在波動度真正回落前就已反彈，機制系統性錯過反彈段
報酬。**不泛化成「波動度目標化/風險平價概念本身沒用」**——這次刻意不
允許槓桿（拿掉文獻機制「低波動期加碼」那一半）、只測單一60日窗口/單一
15%目標/單一TAIEX標的，未測允許槓桿版本、不同窗口、或套用在真正的選股
組合上。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#81、
`HYPOTHESIS_QUEUE.md`#15（狀態已同步更新為FAIL，「排隊順序總結」章節同步
更新）。佇列#15結案，接續佇列第一順位#7低波動（TW策略層，可直接沿用US的
deep_dive方法框架，目前佇列裡唯一無阻塞依賴的下一個排隊項目——#5依附
B24/B25、#6/#8卡題材動能榜PIT引擎、#10待有選股候選通過1~8關）。

---

## 2026-09-02T05:26 — `HYPOTHESIS_QUEUE_PROTOCOL.md`第十四輪排程：佇列#14
台股月營收公布事件效應第1關sanity（事件研究設計）— 結果：**FAIL**

新增`monthly_revenue_event_study.py`（新增，事件錨定窗口設計，跟既有
`factor_ic.py`固定日曆網格快照/`pead_portfolio_v1.py`月頻再平衡都不同——
逐股用自己的月營收公布`pit_date`（`pit.py::month_revenue_pit()`既有PIT
邏輯）當事件起點，公布後第一個交易日進場、持有20交易日，池化所有股票的
事件層級SUE值(`factors.py::_revenue_surprise_sue()`)跟事件後報酬）。100檔
快取樣本，61檔有可用事件，總事件數8322筆（TRAIN 5594筆跨109個月、VAL
2728筆跨47個月，樣本涵蓋度足夠）。結果：TRAIN pooled Spearman
IC=+0.0601(p=0.0000,n=5594)、VAL pooled Spearman IC=+0.0204(p=0.2863,
n=2728)，train/val**同號**（皆正），quintile利差方向正確但VAL期明顯萎縮
（TRAIN spread+0.0318→VAL spread+0.0085，收斂73%），VAL |IC| vs 500次
洗牌null percentile=68.0（門檻90.0，未過）。三項判準（幅度非零/同號/贏過
null）中「贏過洗牌null」這項未過，依協定第1關cheap gate標準判**FAIL**，
未進第2關以後（成本敏感度等）。過程中修正一個實作細節：一開始對原始月
營收表直接做holdout斷言誤觸發AssertionError（`pit_date`揭露日本來就會
晚於`load_dev`用來裁切VAL_END的營收期間`date`欄位，個別rows的`pit_date`
超過VAL_END是正常現象非洩漏），改把斷言移到最終事件表（用天生受
`adjusted_price_series()`保護的`entry_date`）後解決，過程中沒有真正碰觸
holdout資料本身。**不泛化成「月營收驚喜這個訊號完全沒用」**——因子層日頻
cross-sectional IC驗證（`TRIALS_LEDGER.md`#8，PASS）依然成立不受影響，
這裡死的是「事件窗口設計本身」（VAL期樣本外顯著性/贏過隨機對照都不夠）
——跟PEAD策略層（#3，FAIL，月頻再平衡構造）是兩種不同構造但殊途同歸的
結果，暗示SUE類訊號的訊噪比在portfolio/event層級整體偏弱，不論用哪種
構造包裝。完整見`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#80、
`HYPOTHESIS_QUEUE.md`#14。佇列#14結案，接續佇列第一順位#15波動度目標化
Vol-Targeting。

---

## 2026-09-02T04:55 — `HYPOTHESIS_QUEUE_PROTOCOL.md`第十三輪排程：佇列#13
台股三大法人連續買超持續性第1關cheap IC gate — 結果：**FAIL**

新增`factors.py::_consecutive_positive_streak_days()`（`f_inst_streak_days`：
三大法人合計淨買超連續同方向天數，重用既有`_institutional_daily_net()`
已算好的`total_net`欄位）+`factor_ic_inst_streak_days.py`（新增，沿用
`factor_ic.py`既有cross-sectional IC+洗牌null框架）。結果（100檔快取樣本，
80檔可用，121個20交易日快照）：TRAIN mean_ic=+0.0328 IR=+0.281(n=74)、VAL
mean_ic=-0.0236 IR=-0.183 hit_rate=0.53(n=47)，train/val正負號相反、null
percentile=81.9（門檻90.0，未過）。跟已FAIL的`f_foreign_streak`（#3，
外資單一法人版）死法幾乎相同，暗示「連續買超」這個時間序列結構本身測不出
穩健訊號，不是統計量選擇的問題。完整見`HYPOTHESIS_QUEUE.md`#13、
`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`#79。佇列#13結案，接續佇列第一
順位#14台股月營收公布事件效應（第1關sanity尚未開始）。本輪未觸發任何
「三個停下條件」，`is_holdout_consumed()`確認仍為`False`。

## 2026-09-02T04:16 — `HYPOTHESIS_QUEUE_PROTOCOL.md`第十二輪排程，佇列#12 Betting-Against-Beta/低beta — **已結案：FAIL**（查核「已知相關背景」時發現此因子`f_bab`其實已在TW marathon軌道測過`TRIALS_LEDGER.md`#61，本輪引用該既有結果判定、未跑新程式；train期IR僅0.009近乎雜訊，且跨軌共用累積Bonferroni校正門檻99.63遠高於單測percentile91.0，兩者疊加判FAIL；完整見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#78/`HYPOTHESIS_QUEUE.md`#12；佇列接續#13台股三大法人連續買超持續性，第1關尚未開始）

## 2026-09-02T03:59 — `HYPOTHESIS_QUEUE_PROTOCOL.md`第十一輪排程，佇列#11產業內相對強度Sector-Neutral Relative Strength第1關cheap IC gate — **已結案：FAIL**（贏過洗牌null分布這一項未過，percentile=82.8<90.0門檻，train/val同號但方向與假設預期相反；新增`factor_ic_sector_neutral_rel_strength.py`，不改`factor_ic.py`/`factors.py`本身；完整見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#77/`HYPOTHESIS_QUEUE.md`#11；佇列接續#12 Betting-Against-Beta/低beta，第1關尚未開始）

## 2026-09-02T03:25+08:00 — #10市場regime擇時overlay：方法論框架建置完成+sanity通過（HYPOTHESIS_QUEUE_PROTOCOL.md軌道第十輪，跟三軌馬拉松無關）

**背景**：`hypothesis_queue`具名鎖正常取得（`LOCK_ACQUIRED`，非陳舊回收），
`git pull`已是最新，`git status`乾淨（只有一個不是本輪產生的殘留未推送
commit——Shioaji報價自動更新，以及幾個非本輪殘留的`*_run.log`檔案，未
觸碰、未納入本輪commit）。`HYPOTHESIS_QUEUE.md`條目狀態欄跟「排隊順序
總結」兩處核對一致（#1~4、#9皆已結案FAIL，下一順位為#10），無不同步
需要修正。

**本輪工作**：#10「沒有已過關的候選可以套用」，依協定「完全沒開始過→
先把地基做好」，本輪新增`research/regime_overlay.py`（regime判定規則+
疊加曝險回測工具，完整設計理由跟參數選擇見檔案docstring）——沿用兩個
既有、已在其他腳本驗證過的市場層級regime定義（`prepare_market_data().gate`
的200日均線位階、`regime_conditions.py`同款的20日波動度vs擴張窗中位數），
組成exposure_map（第一版單調參數，非搜尋/優化結果），並用TAIEX買進持有
本身當sanity測試對象（唯一不需要選股候選就能驗證機制正確性的方式）。

**sanity結果（PYTHONIOENCODING=utf-8乾淨重跑，log見
`regime_overlay_sanity_run.log`）**：①combined_regime分布非系統性單一格
（4種組合都出現，46.0%/25.3%/21.8%/6.8%）；②全期間(2010-05-05~2024-12-31,
TRAIN+VAL)MDD由baseline-31.63%改善到overlay-17.10%，Sharpe同時從0.55升到
0.60（CAGR則從+7.97%降到+6.38%，符合降曝險犧牲部分上檔換取下檔保護的
預期方向）；③三個已知歷史危機期間regime標籤正確辨識為多數空頭/高波動
（2018Q4貿易戰急跌：空頭天數占比95.4%/高波動89.2%，窗內MDD-14.23%→
-8.08%；2020Q1新冠崩盤：空頭60.7%/高波動100.0%，窗內MDD-26.53%→
-13.41%；2022全年空頭：空頭80.5%/高波動93.1%，窗內MDD-31.63%→-17.10%）
——機制方向正確，不是常數/no-op/標籤錯位。

**這輪的性質不是PASS/FAIL判定**——套用對象是TAIEX買進持有本身而非任何
選股策略，這不是可部署的擇時策略，只證明「工具能力就緒+sanity通過」。
市場廣度(breadth)規則仍未實作（誠實記錄「待補」，理由見檔案docstring）。
第2關（隨機控制組）在「擇時overlay」語境下需要另外設計對照組定義，留給
未來有實際候選要套用第9關（下檔保護）時再處理。`HYPOTHESIS_QUEUE.md`
#10條目狀態已更新，接續佇列第一順位改為#11產業內相對強度Sector-Neutral
（下一輪起跑第1關sanity）。`is_holdout_consumed()`確認仍為`False`。

---

## 2026-09-02T02:58+08:00 — 殘差動量#9：因子層第1關cheap IC gate起跑並結案FAIL（HYPOTHESIS_QUEUE_PROTOCOL.md軌道，跟三軌馬拉松無關）

**背景**：`hypothesis_queue`具名鎖正常取得（非陳舊回收），`git pull`已是
最新，`git status`乾淨（只有幾個非本輪殘留的`*_run.log`檔案，未觸碰、未
納入commit）。依`HYPOTHESIS_QUEUE.md`「排隊順序總結」跟各條目狀態欄兩處
對得上，確認佇列第一順位是#9殘差動量Residual Momentum（第1關sanity尚未
開始）。

**動作**：新增`factors.py::prepare_factors()`「(u)殘差動量」段落——
`f_residual_momentum`用252日滾動CAPM beta（沿用`f_bab`/`f_idio_vol`同一套
cov/var計算，只換窗口60→252天），以「12個月股票報酬-beta×12個月大盤
報酬」近似12個月累積殘差報酬。新增`factor_ic_residual_momentum.py`（沿用
`factor_ic.py`既有cross-sectional IC框架，standalone bonferroni_n=1），
100檔快取樣本、80檔可用、121個20交易日快照，前景一次執行完成（未跨輪）。

**結果**：TRAIN mean_ic=-0.0092（n=40，方向為負）、VAL mean_ic=+0.0305
（n=47，方向為正）、null percentile=90.6（單看勉強過90.0門檻）——但
train/val正負號不一致，`evaluate_factor()`三項判準之一未過，直接判
**FAIL**，未進第2關以後。已更新`HYPOTHESIS_QUEUE.md`#9條目狀態+排隊順序
總結、`STRATEGY_GRAVEYARD.md`新增條目（明確聲明不泛化理由：一階近似+
只測CAPM單因子未延伸size/value）、`TRIALS_LEDGER.md`#76。佇列#9結案，
接續佇列第一順位#10市場regime擇時overlay（方法論框架待建立）。

**`is_holdout_consumed()`確認**：本輪只跑因子層IC測試（`snapshot_start`到
`VAL_END`），未觸及holdout範圍，仍為`False`。

---

## 2026-09-02T02:31+08:00 — Carry #4：TRAIN+VALIDATION全部跑完，人工核對alpha顯著性後結案FAIL

**背景**：`hypothesis_queue`鎖檔正常取得（非陳舊回收）。`git status`乾淨
（只有幾個非本輪殘留log檔，未觸碰），`git pull`已是最新。

**動作**：接續上一輪TRAIN 85/100的進度，本輪內用背景啟動+前景`ps`監控
方式連續呼叫`python dividend_yield_portfolio_v1.py`四次：第一次TRAIN
85→100/100完成；第二~四次VALIDATION真實回測+成本敏感度完成後，隨機
控制組0→30→60→90→100/100完成。全部跑完後`data/dividend_yield_
portfolio_v1_results.csv`產出，腳本內建第7/8關判定印出表面PASS。

**判定**：核對腳本原始碼確認`gate7_pass`/`gate8_pass`（第298/311行）
只看報酬vs買進持有+隨機控制組percentile+MDD/beta<1.3，**沒有納入alpha
顯著性**。套用本專案已建立的評判標準（同`pead_portfolio_v1`/
`weinstein_stage2_v2`），TRAIN alpha p=0.4868、VAL alpha p=0.1487，兩期
皆不顯著（>0.05），改判**FAIL**，不採信腳本表面PASS。已更新
`STRATEGY_GRAVEYARD.md`新增條目、`TRIALS_LEDGER.md`#75、
`HYPOTHESIS_QUEUE.md`#4狀態與排隊順序總結。**不泛化成股利率因子沒用**
——因子層IC（#74）仍是CHEAP_PASS，死的是等權/月頻/Top20這個portfolio
構造，跟PEAD同一種死法。

**下一步**：佇列#4已結案，接續佇列第一順位#9殘差動量Residual Momentum
（待起跑，第1關sanity尚未開始）。`is_holdout_consumed()`確認仍為
`False`。本輪即將commit+push+release lock收工，不開始下一個工作單位。

---

## 2026-09-02T01:41+08:00 — Carry #4：接續checkpoint機制持續有效，TRAIN隨機控制組推進到85/100

**背景**：`hypothesis_queue`鎖檔陳舊（held by 48584, 30.7分鐘，回收）——
研判上一輪寫完01:20那則狀態/心跳更新後，還沒來得及commit+push就中斷
（工作目錄留有未commit的checkpoint程式碼+這兩份文件的狀態更新，內容
核對正確，直接沿用不重工）。`ps`確認沒有殘留背景行程（乾淨，可安全
重新啟動）。

**動作**：本輪內用前景阻塞方式（非背景nohup，吸取00:45那輪的教訓）
連續呼叫`python dividend_yield_portfolio_v1.py`兩次，各約9分鐘（7分鐘
計算預算+資料載入~102秒），checkpoint接續機制運作正常：TRAIN隨機
控制組進度44/100→65/100→85/100，真實回測與成本敏感度未重算。順手
修正上一則(01:20)心跳裡兩處編輯中斷造成的語句破碎（`run_one()`那句
跟結尾那句）。

**收工**：TRAIN還差約15筆才完成，接著才輪到VALIDATION全套（真實+
成本敏感度+100隨機），估計還需要2~3輪。`is_holdout_consumed()`確認
仍為False。未產出PASS/FAIL判定。同步更新`HYPOTHESIS_QUEUE.md`#4狀態
與排隊順序總結章節的進度數字。

---

## 2026-09-02T01:20+08:00 — Carry #4：根治「每輪從零重跑」問題，加上checkpoint續跑機制並驗證進度真的在累積

**動作**：量測出瓶頸（資料載入~102秒、單次真實回測~14秒、單次隨機回測
~17秒，TRAIN+VAL合計約206次回測、約35~40分鐘），把`run_one()`改成
checkpoint可續跑（落盤`data/dividend_yield_portfolio_v1_checkpoint.json`，
本機`.gitignore`狀態，不進版控），先用n_random=3縮小規模自測（中斷後
接續 vs 一次跑完，逐欄位數值完全相同，DETERMINISM_CHECK_PASS），再在
本輪內連續呼叫兩次腳本驗證TRAIN隨機控制組進度0→22→44/100真的累積、
真實回測與成本敏感度不重算。**本輪因USD budget將近用盡收工**，未產出
PASS/FAIL判定，holdout確認仍為False。下一輪執行
`python research/dividend_yield_portfolio_v1.py`會自動接續TRAIN剩餘
部分再進VALIDATION。完整見#4 2026-09-02T01:20條目。

---

## 2026-09-02T00:45+08:00 — Carry #4：修正「背景行程能存活到下一輪」的錯誤假設，重跑中未結案

**背景**：`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程觸發（`hypothesis_queue`軌）。
取鎖乾淨（`LOCK_ACQUIRED`，非陳舊回收）。查看上一輪（23:58）留下的
`dividend_yield_portfolio_v1_run.log`：**0位元組，且`ps`確認PID 48852已不
存在**——上一輪心跳寫的「這個行程...不依附於本次claude session，本輪結束
後預期會繼續在背景跑完」這個假設**是錯的**，需要在這裡明確更正：無人值守
headless呼叫（`claude -p`）結束時，即使用`nohup ... &`啟動的背景行程，
仍然會被一併終止（研判整個MSYS/bash子系統連同其下所有行程被收回，不是
真正脫離Windows行程樹的daemon）。**教訓**：以後任何一輪如果沒能在同一輪
內等到背景計算跑完，就不能假設它會「自己在背景繼續跑完」讓下一輪撿現成
結果——下一輪勢必要重新啟動它，等於每次陳舊superseded的部分工作都要
重算，這是這條假設進度一直卡在「重跑中」超過三輪的根本原因（不是bug、
不是無訊號，是每輪都在從頭重跑同一個計算，前面輪次投入的等待時間沒有
累積）。

**本輪動作**：重新啟動`python dividend_yield_portfolio_v1.py`（新PID），
本輪內用前景阻塞方式等待（`timeout=600000ms`分兩段，累計約23分鐘），
`ps`確認行程持續在跑（非崩潰、非卡死，CPU持續消耗），但**在本輪的觀察
時間內仍未跑完**（`data/dividend_yield_portfolio_v1_results.csv`仍是舊的
23:01那份0筆交易殘留結果，尚未被覆寫）。依「有界工作單位」原則，本輪
到此收工，行程大機率會隨這次headless呼叫結束一併被終止（見上方教訓），
**下一輪必須重新執行`python research/dividend_yield_portfolio_v1.py`**，
不能假設能撿到本輪的殘留行程。未新增判定（PASS/FAIL/CHEAP_PASS/
EXPERIMENTAL），`is_holdout_consumed()`確認仍為`False`。

**下一步建議（給下一輪或人工session參考）**：這支腳本本身邏輯沒有問題
（TRAIN+VALIDATION各1次主回測+2次成本敏感度+100次隨機控制組排列，計算
量本來就大，實測單次完整執行可能需要30分鐘以上），問題純粹是「無人值守
單輪時間預算 vs 計算所需時間」的落差。若下一輪也在有限時間內等不到結果，
可考慮的方向（不是本輪擅自決定，留給下一輪判斷）：(a) 改用真正脫離
Windows行程樹的啟動方式（例如`start /b`搭配獨立排程檢查，而非依賴這個
bash子系統的nohup）讓計算能跨輪持續；(b) 若時間允許，考慮把這個工作
單位提升為「這一輪就是等它跑完」而非「有界後就收工」，因為目前的模式
（每輪都重新啟動、每輪都等不到）等同於重跑計算而非累積進度。這個決定
本身可能屬於協定第3節「三個停下條件」之外的新情況，值得下一輪或使用者
一併確認`HYPOTHESIS_QUEUE_PROTOCOL.md`是否要補一條「長計算任務」的
處理方式。

---

## 2026-09-01T23:58+08:00 — Carry #4：接續上一輪的鎖，確認bug修復＋背景重跑仍在進行

**背景**：`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程觸發（`hypothesis_queue`軌，
獨立於三軌馬拉松）。取鎖時發現上一輪（23:23那則的PID 47756）鎖檔陳舊
（29.8分鐘沒更新，已回收）——研判上一輪是寫完23:23那則心跳、重新在背景
啟動`python dividend_yield_portfolio_v1.py`（PID 48852）之後就中斷了，
沒來得及commit+push，工作目錄留下未提交的bug修復（`_eligible_single_
factor()`）跟那則心跳文字。

**確認**：核對23:23那則的bug分析（`_eligible()`的`n_components>=2`門檻
在單因子策略下把候選全篩空，導致0筆交易）跟修復程式碼（`dividend_yield_
portfolio_v1.py`新增`_eligible_single_factor()`，只改本地函式不動共用
模組，避免影響`pead_portfolio_v1.py`），邏輯正確、不重工，直接沿用。

**背景行程狀態**：PID 48852自23:23:07持續執行中，本輪等待約6分鐘
（`dividend_yield_portfolio_v1_run.log`仍是0位元組）仍未結束——累計已跑
超過35分鐘，比上一輪估計的10~20分鐘更久（TRAIN/VAL兩期各100次隨機
控制組排列，計算量本來就大，非bug徵兆，跟先前0筆交易那種秒殺結束的
異常不同）。這個行程是先前那輪留下的獨立OS行程（父行程已消失、鎖檔已
被回收，行程本身仍存活），不依附於本次claude session，本輪結束後預期
會繼續在背景跑完。

**本輪動作**：commit上一輪遺留的bug修復（程式碼本身正確，直接沿用）+
這則心跳，讓下一輪排程觸發時能看到`dividend_yield_portfolio_v1_run.log`
的完整結果並下判定。未新增判定（PASS/FAIL/CHEAP_PASS/EXPERIMENTAL），
`HYPOTHESIS_QUEUE.md`#4狀態同步更新為「bug已修復、背景重跑中，等下一輪
拿結果」。`*_run.log`等執行期log檔（含這支腳本的log）維持不進版控（跟
`.gitignore`裡`*_cycle.log`同精神，屬可重生執行輸出非原始碼），本輪也
沒有其他判定要寫進`TRIALS_LEDGER.md`/`STRATEGY_GRAVEYARD.md`。

---

## 2026-09-01T23:23+08:00 — Carry #4：抓到並修好0筆交易bug，重跑中（仍在跑第7/8關）

**背景**：`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程觸發。取鎖時發現上一輪
（20:10那則的PID）鎖檔陳舊（39.3分鐘沒更新，已回收），研判上一輪疑似
中途失敗/被中斷，不是正常收工。

**發現**：上一輪留下的`dividend_yield_portfolio_v1_run.log`（23:01時間戳，
代表上一輪其實有跑完，只是沒來得及寫心跳/commit就中斷了）顯示**TRAIN/
VALIDATION兩期皆0筆交易、報酬0.00%、alpha=0%**——這不是「沒有訊號」，
是明顯異常（因子層IC本身是正的CHEAP_PASS結果），查下去是實作bug：
`dividend_yield_portfolio_v1.py`借用`portfolio_backtest_v2.py::_eligible()`
做流動性資格篩選，但該函式套用`score.MIN_COMPONENTS_FOR_RANKING=2`
（多因子組合設計的門檻），這支策略刻意單因子（`COMPONENTS=
["dividend_yield"]`，`n_components`永遠是1），每一列都被篩掉→0檔候選
→0筆交易。`pead_portfolio_v1.py`（本腳本逐字比照的範本）用2個成分
（eps_surprise+revenue_surprise）所以沒踩到這個門檻，這次刻意單因子
才暴露出來。

**修好**：新增`_eligible_single_factor()`（只在`dividend_yield_
portfolio_v1.py`本地定義，不改`portfolio_backtest_v2.py`共用模組，
避免影響`pead_portfolio_v1.py`等其他依賴它的腳本）——流動性下限篩選
邏輯逐行沿用，只把`n_components>=2`門檻改成`n_components>=1`（單因子
本來就只可能是1）。已重新在背景執行`python dividend_yield_portfolio_v1.py`
（教訓：這類bug比計算耗時更值得優先排查，下次看到「0筆交易」不能直接
當作「這次計算量大還沒跑完」的正常現象放過）。

**本輪收工時的真實狀況（等了約48分鐘仍未跑完，比原本估計的10~20分鐘
久很多——修bug前的buggy版本因為候選池永遠是空的，backtest engine每個
換股日幾乎零運算、跑得很快；修好後真的有100檔候選要算流動性+z-score+
真實成交，運算量遠高於buggy版本，這點修bug前沒預料到）**：python行程
（PID 750，23:23:07啟動）持續在跑，log檔仍是空的（stdout要等腳本
`print`到最後才會flush到檔案，這是正常現象不是卡死——`ps`確認CPU仍在
用，不是殭屍行程）。**沒有殺掉這個背景行程**——依上一輪(20:10那則)的
先例，背景python行程在Claude呼叫結束後仍會繼續跑完（20:10那輪同樣在
呼叫結束前跑到一半，後來在23:01自己完成並寫出log，只是那次跑出的是
修bug前的錯誤結果），這次修好bug後的行程應該一樣會在背景繼續算到完成。

**給下一輪排程的明確指示**：開始這條假設前，**先確認`dividend_
yield_portfolio_v1_run.log`是否已經有非空內容**——如果已有完整輸出
（第7/8關判定字樣），直接讀那份結果做判定、寫TRIALS_LEDGER，不用重跑；
如果log仍是空的，**先用`ps`確認`research/dividend_yield_portfolio_v1.py`
對應的python行程是否還在跑（`ps aux | grep dividend_yield`或直接查
PID 750是否還在）**，若還在跑，不要重複啟動第二個行程（會造成兩個
行程同時寫同一個log檔），繼續等待或這輪先收工讓下下輪再檢查；只有
確認行程已經不在跑、log也還是空的（代表行程異常中斷），才重新啟動
`python dividend_yield_portfolio_v1.py`。

**額外插曲**：本輪執行中途發現`.hypothesis_queue.lock`鎖檔案無預警
消失過一次（不是陳舊被回收，是檔案整個不見，原因不明——排除三軌
marathon可能性，因為它用的是不同檔名`.marathon.lock`），已重新
`acquire`確保收工前仍持有鎖、能正常release，但這個異常值得往後留意，
如果下一輪也遇到類似情況，記錄下來看是否有共同模式。**收工前補充**：
已查出鎖檔消失的原因——commit`2b73f69`（同一段時間內出現的另一筆
commit，訊息提到PID48852，跟本輪背景行程的Windows PID相同）已經把
完全相同的bug診斷/修復/文件更新commit過一次，代表這條track在這段
時間內被不只一個執行個體處理過（原因不明，值得之後排查，但不影響
正確性——兩邊獨立得出同一個修復）。本次收工不重複commit程式碼本身
（已跟HEAD一致），只補這則心跳與上面的交接指示。

---

## 2026-09-01T20:10+08:00 — Carry #4：portfolio層腳本寫好，第7/8關驗證跑到一半收工

**背景**：接續11:35那則的斷點（第1關cheap IC gate CHEAP_PASS後，下一步是
portfolio層構造）。這輪`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程觸發，取得
`hypothesis_queue`具名鎖後開始執行。

**做了什麼**：新增`dividend_yield_portfolio_v1.py`——逐字比照
`pead_portfolio_v1.py`同一套機制（`factor_ic.py`抽樣宇宙+快取因子、
`backtest/engine.py`月頻換股21日+三成本層級、`score.py`同產業z-score、
`validation/holdout.py`TRAIN/VAL防呆），單因子`f_dividend_yield_ttm`（同
產業z-score後即為composite），Top20、月頻，跑TRAIN(2015~)/VALIDATION
(2021~)兩期樣本外+成本敏感度(1x/2x/3x)+隨機控制組(N=100)。

**卡住的地方（不是bug，是計算量）**：實際執行`python
dividend_yield_portfolio_v1.py`，光是TRAIN/VALIDATION各100次隨機控制組
backtest加上成本敏感度重跑，單次呼叫（背景執行）已跑超過13分鐘仍未產出
`data/dividend_yield_portfolio_v1_results.csv`（用`ps`查行程本身CPU時間
確認持續運算中，不是掛死——記憶體從278MB穩定成長到472MB後打住，符合
「載入完資料後進入純運算迴圈」的預期行為，非異常）。依協定「一輪只做一個
有界工作單位，不要在單次無人值守呼叫裡硬做到天荒地老」原則，本輪不繼續
死等，先收工。

**下一步（給下一次排程觸發或人工session接手）**：腳本本身已完整寫好、
`可重複執行`（沒有中間快取污染風險，重跑會從頭產生完整結果），直接
`cd research && python dividend_yield_portfolio_v1.py`即可拿到TRAIN/VAL
兩期完整數字（報酬/MDD/Sortino/alpha顯著性/beta/成本敏感度/隨機控制組
percentile），然後依`HYPOTHESIS_QUEUE_PROTOCOL.md`第2節「判定標準要跟
既有已結案案例同一把尺」——**隨機控制組percentile表面過關不夠，alpha
顯著性(p值)+beta拆解才是最終判準**（跟`weinstein_stage2_v2`/
`pead_portfolio_v1`同一標準）——完成後同步更新`HYPOTHESIS_QUEUE.md`#4
狀態、`TRIALS_LEDGER.md`新增一列、PASS則進`STRATEGY_GRAVEYARD.md`或
`generate_strategies_json.py`。若未來多次重跑都遇到同樣的長時間問題，
可考慮把`n_random`降到50並在腳本docstring註明理由，但這個決定留給屆時
真的卡住的那一輪判斷，這輪不擅自改動既有100 draws的標準門檻。

**沒有觸發三個停下條件中的任何一種**——這是計算耗時問題，不是要不要拉
draws到1000/survivorship-free宇宙/花錢的決策，不需要問使用者。

---

## 2026-09-01T11:35+08:00 — 假設佇列排程建置完成 + Carry第1關CHEAP_PASS

**背景**：使用者裁示「把策略假設佇列掛上自動排程，終結『無人接手就停』」——
這份檔案下面08:40那則收工斷點之後，佇列本身仍然沒有自動化，這輪把這個
缺口補上，並用這次建置本身當測試，順便接續佇列#4股票股利率carry。

**一、排程建置（比照既有`AlphaMarathon`三軌排程的真實架構，不是天真的
單一確定性Python腳本——因為「佇列全空時要主動想新假設軸」這種需要經濟
理由判斷的工作，只有LLM agent做得到，純腳本做不到）**：
1. `marathon_lock.py`推廣成支援具名鎖（`--name hypothesis_queue`，向下
   相容，預設仍是三軌用的`.marathon.lock`），已測試acquire/release正常，
   且跟目前正在跑的三軌鎖互不干擾（測試當下三軌鎖確實被另一個活著的
   排程cycle持有，具名鎖仍能獨立取得，證明隔離有效）。
2. 新增`HYPOTHESIS_QUEUE_CONTINUATION_PROMPT.txt`（比照
   `MARATHON_CONTINUATION_PROMPT.txt`極簡bootstrap風格）+
   `HYPOTHESIS_QUEUE_PROTOCOL.md`（新的完整規則文件：取鎖→挑下一條未
   結案假設→執行一個有界工作單位→心跳/同步佇列狀態/TRIALS_LEDGER/
   GRAVEYARD→commit+push→釋放鎖；佇列全空時主動設計regime/擇時型新軸的
   規則也寫在裡面，見該檔案第1節）。
3. 新增`C:\alpha\run-hypothesis-queue-cycle.ps1`+
   `run-hypothesis-queue-hidden.vbs`（逐字比照三軌既有的
   `run-marathon-cycle.ps1`/`run-marathon-hidden.vbs`，同樣的
   `--max-budget-usd 5`預算煞車跟工具限制）。
4. **Windows排程器本身尚未建立/啟用**——新增一個每30~60分鐘會呼叫
   Claude API、常態花錢的排程，屬於使用者自訂的「花錢」停下條件，這步
   驟保留給主session跟使用者確認預算沒問題後再掛上去，這裡只完成
   建置+手動驗證。

**二、手動驗證測試（同時也是佇列#4的真實進度，不是空跑）**：挑到
佇列#4股票股利率carry（`f_dividend_yield_ttm`，trailing 12個月現金股利/
股價），新增`factors.py::_dividend_yield_ttm_cash()`（用
`CashExDividendTradingDate`本身當pit_date，除息生效日天然PIT-safe，不
需要`quarterly_pit`式的延遲假設）+ `prepare_factors()`裡的因子欄位 +
`factor_ic_dividend_yield.py`。**第1關cheap IC gate結果：CHEAP_PASS**
——TRAIN mean_ic=+0.0606 IR=+0.426(n=74)、VAL mean_ic=+0.0807
IR=+0.562 hit_rate=0.77(n=47)，train/val同號，null percentile=100.0
（門檻90.0）。**這只是因子層第1關，不是最終PASS**，下一步是portfolio層
構造（GATE_SEQUENCE第3~9關），留給下一次接手者（不論是排程觸發後的
無人值守instance，或人工session）。完整見`TRIALS_LEDGER.md`#74、
`HYPOTHESIS_QUEUE.md`#4。

**三、順便修正兩處協定遵循瑕疵**（使用者驗證性提問時發現）：這份檔案
先前CTA/PEAD相關的5則條目沒有照「最新的寫最上面」規則插到檔案最頂端，
而是往下接（造成檔案字面最上面其實是最舊的一則）——本次已重新排序成
真正時間新到舊由上到下；`HYPOTHESIS_QUEUE.md`第100行附近「佇列狀態：
#1已結案，接續#2 CTA」的舊提示字也已同步更新反映CTA/PEAD都已結案的
現況。

**沒有觸發三個停下條件中的任何一種**（本輪唯一涉及「花錢」的部分——
啟用常態排程本身——刻意保留給主session確認，不是本輪自己判斷可以跳過）。

---

## 2026-09-01T08:40+08:00 — 本次執行收工：斷點留給下一個接手者

CTA（FAIL）+ PEAD（FAIL）兩條假設本輪都已完整結案並commit+push，佇列
狀態、`STRATEGY_GRAVEYARD.md`、`TRIALS_LEDGER.md`都已同步更新。順便修好
了三軌輪次制馬拉松（`MARATHON_STATE.md`）的排程器7天視窗到期問題（見本檔
案08-25T07:50條目），三軌馬拉松已恢復自動運作，跟這條佇列是不同軌道。

**下一步斷點：佇列#4股票股利率carry**（`HYPOTHESIS_QUEUE.md`原文：TW股票
近12個月現金股利/股價，高殖利率排名靠前）——**這是全新因子，跟CTA/PEAD
不同，CTA/PEAD都是重用既有基礎設施或既有PASS因子，這條要從零開始**：
1. 資料源已知可用：`TaiwanStockDividend`（`adjust.py`已在用，欄位
   `CashExDividendTradingDate`/`CashEarningsDistribution`），需要新寫
   trailing 12個月現金股利加總（依ex-date分桶，PIT-safe——只加總ex-date
   已發生的部分，不看未來）除以現價，新增到`factors.py`（可能命名
   `f_dividend_yield_ttm`，不要跟`_roe_stability`等既有function混在一起，
   獨立新增）。
2. 第1關sanity+第2關隨機控制組：因為這是股票橫斷面因子（不是像CTA那種
   單一時間序列），應該沿用`factor_ic.py`既有的cross-sectional IC+
   洗牌null分布測試框架（跟`f_low_vol`/`f_eps_surprise`等既有PASS因子
   同一套機制），不是`fut_cheap_gate.py`那種單一序列排列測試——**這點
   下一個接手者要留意，不要套錯框架**。可能需要寫一支類似
   `factor_ic_gross_margin_stability.py`（`TRIALS_LEDGER.md`#67先例）的
   新腳本`factor_ic_dividend_yield.py`。
3. 因子層IC過關後才進portfolio層構造（走完整GATE_SEQUENCE第3~9關），
   不能因子IC都還沒測就跳去測策略層——跟CTA（直接測策略層，因為CTA本來
   就是策略假設不是因子假設）、PEAD（因子已PASS只補策略層）都不一樣。
4. 停下三條件其中任一種出現時要停：1000draws授權、survivorship-free
   宇宙授權、任何不可逆/花錢操作——本輪跑完CTA+PEAD都沒有觸發任何一種，
   純粹是「這是全新因子工程，值得從乾淨的斷點交接，不要在長session尾端
   倉促動手」的判斷，不是碰到停下條件。

**收工前確認**：`git status`乾淨（除了已知不屬於本輪、也不屬於這條佇列
的其他並行session殘留檔——`research/pit_run_*.log`/`weinstein_v2_run.log`/
`data/rate_limit_state.json`，這些本輪未觸碰、未commit）。本輪全部commit
都已push成功。

---

## 2026-09-01T08:35+08:00 — PEAD策略層構造結案：FAIL（alpha顯著性未過）

跑完N=100完整版：TRAIN(2015-2020)報酬+60.28%/alpha+7.36%(p=0.5349不顯著)/
beta+0.564，隨機控制組percentile=100.0；VALIDATION(2021-2024)報酬+54.65%/
alpha+6.03%(p=0.4809不顯著)/beta+0.570，隨機控制組percentile=98.0。

**表面上第7關（樣本外+隨機控制組）過關，但套用本專案已建立的alpha顯著性
標準（`portfolio_multifactor_v2`/`weinstein_stage2_v2`都用過同一把尺）
判定FAIL**——隨機控制組percentile高只證明「排序這兩個因子挑的股票比隨機
挑股票好」（跟因子層IC本來就PASS的結論一致），不能取代CAPM alpha顯著性
檢定：兩期alpha都遠不顯著(p=0.48~0.53)，且**VAL期總報酬(+54.65%)幾乎
等於買進持有大盤(+54.58%)，只差+0.07個百分點**，beta+0.56~0.57顯示報酬
主要是市場曝險，不是選股貢獻的超額報酬。**不泛化成PEAD/SUE因子沒用**——
死的是「等權/月頻/Top20」這個具體portfolio構造，IC加權或情境式組合等
變體仍值得未來獨立測試。完整見`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#73。

**立即接續：佇列#4股票股利率carry（全新因子，第1關sanity尚未開始）。**

---

## 2026-09-01T08:25+08:00 — PEAD策略層構造：第7關樣本外背景執行中

`pead_portfolio_v1.py`（新增）：等權組合`f_eps_surprise`+`f_revenue_surprise`
（刻意只用這兩個PEAD/SUE家族因子，跟`portfolio_multifactor_v2`的4因子
版本區隔），月頻換股Top20，沿用`portfolio_backtest_v2.py`通用機制（資格池/
成本模型/alpha回歸，不修改該檔案本身）。TRAIN/VALIDATION兩期各跑N=100
配對式隨機控制組+成本1x/2x/3x敏感度，背景執行中（單一組合N=15隨機控制組
先例耗時2分鐘以上，N=100預估較久），已設置背景任務盯著，完成後立即記錄
第7/8關結果並commit+push。

---

## 2026-09-01T08:10+08:00 — CTA趨勢跟隨結案：FAIL（第2關隨機控制組percentile=10.0）

`cta_momentum_12m.py`（新增）：252交易日/12個月回顧報酬正負號，月頻
重平衡，跟已FAIL的`fut_trend_multi_tf`（10/20/60日多數決）刻意區隔。

第1關sanity PASS（5915/6185天有效，long73.9%/short26.1%，29次月頻換倉，
非結構性no-op）。**第2關隨機控制組（N=200配對式）：percentile=10.0**，
遠低於90.0單測門檻，且低於50——真實策略終值0.7162（累積虧損-28.4%，
無成本），同期買進持有+778.9%，隨機控制組中位數+180.9%，真實策略比
190/200次隨機洗牌自己的部位陣列還差。

人工檢查訊號構造無bug（2000年底/2001年做空對應網路泡沫後續下跌、
2023-2024全程做多對應多頭格局，方向經濟上合理）。研判是典型「動量崩盤」
（momentum crash，Daniel & Moskowitz 2016）：12個月落後訊號在V型反彈
時來不及轉向。**不泛化成「CTA在台指期沒用」**——已FAIL的多窗口投票版
（`fut_trend_multi_tf`#18，percentile=82.5）比這次單一窗口版本(10.0)
明顯不那麼差，暗示多窗口平滑可能有幫助，留給未來變體驗證。

依協定第2關未過直接結案，未做第3關以後的關卡。完整數字見
`STRATEGY_GRAVEYARD.md`/`TRIALS_LEDGER.md`#72/`HYPOTHESIS_QUEUE.md`#2。

**立即接續：佇列#3 PEAD策略層構造（用已PASS的`f_eps_surprise`/
`f_revenue_surprise`兩因子組portfolio層規則）。**

---

## 2026-09-01T07:50+08:00 — 心跳補記：約68小時空窗說明，CTA趨勢跟隨正式起跑

**使用者發現這份檔案從04:45起沒有新條目，要求先查清原因再接續。查清後是兩條
獨立軌道的問題，分開講：**

1. **TW/US/FUT三軌輪次制馬拉松（`MARATHON_STATE.md`，跟這份檔案不同軌）**：
   靠Windows工作排程器`AlphaMarathon`每30分鐘自動觸發。查出這個排程器的
   觸發器設了`Duration=P7DT1H35M`+`StopAtDurationEnd=True`，這個7天視窗
   已經在**2026-08-30 11:35**到期，之後`NextRunTime`變空、永遠不會再自動
   觸發——**跟三軌本身「暫停單因子試驗規則」無關，是排程器設定本身到期，
   不是判斷邏輯卡住**。機器在那之後到2026-08-31 23:17又是關機/睡眠狀態，
   錯過28次觸發視窗。**已修好**：把`Duration`清空、`StopAtDurationEnd`
   設`False`，改成無限期重複，確認`NextRunTime`已排到2026-09-01 08:00，
   三軌馬拉松會恢復自動運作。
2. **這份檔案對應的`HYPOTHESIS_QUEUE.md`佇列（Weinstein→CTA→PEAD→carry）**：
   從一開始就靠互動session手動跑，**從來沒有掛過任何自動化排程**。上一個
   session在2026-08-29T04:45完成Weinstein v2結案（FAIL）後，寫下「立即
   接續CTA趨勢跟隨」就結束了，沒有任何後續session接手——是**無人接手**，
   不是背景任務當機或卡住。

**現在接續：CTA趨勢跟隨（`HYPOTHESIS_QUEUE.md`#2）第1關sanity開始執行。**

---

## 2026-08-29T04:45+08:00 — Weinstein v2結案：FAIL（隨機控制組+成本敏感度雙雙不過）

第2/4關跑完。**判定：FAIL，移入`STRATEGY_GRAVEYARD.md`，不進第3/5/6/9
關**。關鍵數字：
- VALIDATION：表面總報酬+56.72%贏買進持有(+54.58%)，但拆解後beta貢獻
  +32.93%占過半，純alpha僅+23.80%（配對式隨機控制組n=200中位數
  +21.31%，**percentile=55.0，遠低於90.0單測門檻**）。成本敏感度：1x
  alpha+23.80%→2x+4.79%→**3x轉負-16.37%**。
- TRAIN：純alpha本身就是負的（-3.66%，beta貢獻+19.11%比總報酬
  +15.45%還高）。隨機控制組percentile=84.0，同樣未達門檻。成本敏感度
  3x：alpha-31.97%、**總報酬也轉負-19.65%**。

**這是`CLAUDE.md`「復盤原則：流程重於盈虧」點名的典型案例**——表面
總報酬好看（贏買進持有），拆解後發現主要是beta曝險而非真alpha，且
alpha經不起真實成本壓力測試。完整數字寫進`STRATEGY_GRAVEYARD.md`，
`HYPOTHESIS_QUEUE.md`#1標記結案，`data/strategies.json`的
`weinstein_stage2_baseline`狀態自動從`草稿`升級為`回測未通過`（新增
`generate_strategies_json.py::_graveyard_heading()`動態檢查
`STRATEGY_GRAVEYARD.md`是否有對應條目，不是手動改）。**明確不泛化**：
這只是這個具體實作（60日相對強度窗口+150日均線+TAIEX 200日均線閘門）
的死法，不代表Weinstein第二階段概念本身沒用。

**立即接續**：佇列#2 CTA趨勢跟隨（期貨，時序動量），開始第1關sanity。

---

## 2026-08-29T04:05+08:00 — Weinstein v2抓到真bug並修好：0筆交易→有效交易

執行第2/4關（`weinstein_v2_alpha_gate.py`）第一次跑，發現TRAIN/
VALIDATION**兩期都是0筆交易**——追查發現`stage2_signal_v2()`假設
`price_data`已經有相對強度欄位（沿用sanity階段用的`factor_ic.py`快取
現成的`f_rel_strength`），但這支campaign腳本走的是不同資料路徑
（`adjusted_price_series()`直接載入，不經過`factors.py::prepare_
factors()`），那個欄位根本沒被算過，每天每檔都被誤判「資料缺失」跳過。
**這是sanity階段測試涵蓋率不足的真實案例**：sanity PASS了，但測的
不是後續關卡實際會用的資料載入路徑。

修法：新增`prepare_price_data_v2()`獨立計算相對強度（60日個股報酬−
60日大盤報酬，跟`factors.py::f_rel_strength`同一個定義，不依賴外部
欄位是否存在），三支消費端腳本（sanity/run_weinstein_unbiased_v2/
weinstein_v2_alpha_gate）全部改用同一個函式。sanity重跑數字不變
（仍PASS），確認bug只在campaign腳本的資料路徑，不影響sanity本身的
判定方向。

修好後重跑：**VALIDATION期353筆交易，+56.72%報酬，贏過買進持有
（+54.58%）；TRAIN期515筆交易**，第2/4關（n=200隨機控制組+成本敏感度+
alpha/beta拆解）背景執行中，已設置Monitor，會持續更新這裡。

---

## 2026-08-29T03:40+08:00 — B24乾淨重跑完成：判定結論穩健但發現新的非決定性來源

B24可重現性乾淨重跑跑完了。**判定結論一致**（兩次獨立跑法都是不及格：
兩期都贏買進持有+贏全部100次隨機對照組，但兩期alpha都不顯著）——但
**精確數字不是逐位元相同**（TRAIN報酬75.87%→71.79%，MDD -19.95%→
-27.85%）。深入比對兩份log發現根因：**不是快取寫入損毀**（那個bug已經
用atomic write修好，`determinism_self_test.py`本輪兩次獨立確認PASS），
是**FinMind額度即時狀態導致每次跑因子完整度不同**（原始跑1908次因子
跳過、乾淨重跑1461次，次數本身就不一樣）——這是一個新發現、目前還沒解
的非決定性來源，跟已修好的問題是不同機制。完整分析寫進
`B24_RESULTS.md`「可重現性乾淨重跑」章節，`data/strategies.json`的
`value_board_v2.limitations`也同步更新。**這不在使用者的三個停下清單
裡（不是1000draws/survivorship-free/不可逆操作），誠實記錄+登錄下一步
建議後繼續往下跑，不停下等待**。

**B24前置關卡狀態：判定結論確認穩健，可以繼續信任佇列後續的「通過」
判定**——質化結論（及格/不及格）在兩次獨立跑法之間一致，這是「儀器
不穩=不能信」這條最高投資原則要求的最低標準，已經達到；精確數字的
不可重現性是另一個獨立問題，已誠實登錄，不阻擋佇列繼續往下走。

**立即接續**：CPU資源現在空出來了，馬上執行Weinstein v2第2/4關
（隨機控制組n=200+成本敏感度，`weinstein_v2_alpha_gate.py`）。

---

## 2026-08-29T02:55+08:00 — B24乾淨重跑背景執行中；Weinstein v2第1關(sanity)PASS

**B24可重現性乾淨重跑**：`determinism_self_test.py`重跑一次確認Test A/B
仍PASS（bit-identical）。用`CACHE_SUFFIX=_clean`環境變數（新增到
`run_value_board_v2_pit_backtest.py`，不影響預設行為）強制建一份100%在
atomic write修法（`c97ac0f`）之後建置的全新快取，背景執行中
（`pit_run_liquidity500_clean.log`），已設置Monitor持續盯。

**Weinstein第二階段v2**（`HYPOTHESIS_QUEUE.md`#1，佇列第一條）：
- 新增`strategies/weinstein_stage2_v2.py`（不改v1，避免動到
  `TRIALS_LEDGER.md`#10/#11引用的既有結果）：三個gate（站上150日均線+
  均線上揚+`f_rel_strength`>0），排名依相對強度。
- **第1關sanity：PASS**——40個季度檢查點，通過gate股票池
  mean=95.2/median=107.0（486檔候選，合理），事後20日報酬通過gate組
  +2.24% vs 全樣本+1.41%，方向正確。
- 第2關（隨機控制組n=200）+第4關（成本敏感度1x/2x/3x）程式碼已就緒
  （`strategies/run_weinstein_unbiased_v2.py`+`weinstein_v2_alpha_gate.py`，
  複製v1既有基礎設施只換訊號函式），**刻意先不執行**——避免跟B24乾淨
  重跑同時搶CPU（B24-500那輪實測到102秒/draw的CPU競爭拖慢，這次要避免
  重演）。等B24乾淨重跑完成、收到背景任務完成通知後，立刻接著跑這支。

**下一步**：等B24乾淨重跑完成通知 → 記錄B24最終確認結果（含跟原本
100-draws結果的一致性比對）→ 立即執行`weinstein_v2_alpha_gate.py`
（第2/4關）→ 依結果決定PASS進監控台或FAIL進GRAVEYARD、或需要第3/5/6/9
關補強 → 接著CTA趨勢跟隨。

---

## 2026-08-29T02:10+08:00 — 馬拉松啟動，開始B24可重現性乾淨重跑

從checkpoint `c19c11f`接續。目前佇列狀態：`HYPOTHESIS_QUEUE.md`8條全部
未起跑，`STRATEGY_GRAVEYARD.md`只有3筆回溯整理。

**第一步（前置關卡）**：B24可重現性乾淨重跑。既有的
`value_board_v2_sample_cache_liquidity500.pkl`（2026-08-29 00:38建立）
建置時間橫跨atomic write修法commit（`c97ac0f`）前後，不能100%確定沒有
受並行讀寫影響——即使那輪跑完沒有崩潰/讀取錯誤。這次改用全新快取檔名
`value_board_v2_sample_cache_liquidity500_clean.pkl`（不覆蓋/不刪除舊檔，
純粹確保這次建置100%發生在atomic write修法之後），重跑：
1. `determinism_self_test.py`（Test A+Test B）——先確認機制本身仍然
   健康。
2. 全新快取建置 + B24-500完整流程（TRAIN+VALIDATION兩期、各100次
   隨機對照draws）。

背景執行中，預估耗時跟上一輪相近（factor prep~20分鐘+約6~7小時的
draws），會持續更新這裡。
