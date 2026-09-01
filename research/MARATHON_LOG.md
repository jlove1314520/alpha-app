# MARATHON_LOG.md — 自主研究馬拉松可見心跳（2026-08-29啟動）

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
