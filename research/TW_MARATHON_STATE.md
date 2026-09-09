# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-09T18:30+08:00（馬拉松第497輪）**——取鎖乾淨（cycle`20260909-183037`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 17:30（round495，較舊）／US 18:00（round496，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；`PENDING_QUEUE.md`頂端有2026-09-09總司令裁示的「題材」新聞管線任務，但屬互動session/Cowork範疇（涉及`news_body_extract.py`/`build_themes.py`等非馬拉松三軌檔案），非本track工作範圍，本輪未碰。**核實候選池現況不變**：0a節四條方向＋`#61`~`#66`全數結案，`data/ticks/`仍僅2個完整交易日parquet（`20260909`當日檔仍`.tmp`未finalize，較round495無變化，距20日門檻仍差18個交易日）；`#50`提案（`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`）仍待核准。**本輪工作單位＝延續round496做法，補齊`build_signal_status.py`其餘遺漏方向**：round496補上`#61`後，本輪逐一核對`STRATEGY_GRAVEYARD.md`確認`#53`（全市場報酬離散度速度）/`#54`（成交值集中度速度）/`#55`（三大法人買賣超截面離散度速度）/`#57`（全市場當沖比重截面離散度速度）/`#58`（反向波動度加權投資組合建構）/`#59`（最小變異數投資組合建構）/`#60`（衍生性商品結算機械性效應）共7條hypothesis_queue假說皆已正式結案（全數FAIL），但同樣從未寫進`build_signal_status.py`公開清單——`#56`因屬「Cowork更正一條件判定下的撤案不測」（未實際跑檢定），與其餘「測過、FAIL」性質不同，依本檔案定位（`我們也告訴使用者「測過、沒用」`）判斷不納入。已比照`#61`/`#62`格式，逐條核對`STRATEGY_GRAVEYARD.md`對應條目內容後新增段落（含`note`欄位註明「非0a節四條方向之一」＋所屬機制家族），並在檔頭docstring補一句說明實務範圍已擴及`#53`起的後續編號、不限於原始四條方向。重跑`build_signal_status.py`：`directions`清單`ids`從10條（`49/50/51/52/61/62/63/64/65/66`）增至17條（新增`53/54/55/57/58/59/60`），`git diff -b`確認`data/signal_status.json`除新增區塊與`generated_at`時間戳外無其他變動、`build_signal_status.py`除新增區塊與docstring一句話外無其他變動。`trial_registry.py --check`exit=0 PASS（232列，撞號2組皆為歷史存量不回頭改寫，本輪未產生新判定，只是補齊既有FAIL判定的公開曝光，不需要新的`register_trial()`呼叫）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`/`.py`檔案）。**下一輪任一軌接手**：建議再核對一次是否還有其他`STRATEGY_GRAVEYARD.md`已結案但`build_signal_status.py`遺漏的編號（目前`ids`已涵蓋`49~66`扣除撤案的`56`，若`hypothesis_queue`排程後續產生新編號結案，記得同步補上）；`#50`提案仍待核准；候選池本身未變薄也未變厚，仍是純維護性工作。完整見`REPORT.md`第497輪心跳、`build_signal_status.py`（新增7段落）、`data/signal_status.json`（新增7條，共17條）。

---

**上一則保留（第495輪，供對照）**——取鎖乾淨（cycle`20260909-173036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 16:30（round493，較舊）／US 17:00（round494，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`，無heavy-job-slot佔用；`git log`確認round494後無新commit。**核實候選池現況不變**：0a節四條方向＋`#61`~`#66`全數結案，`data/ticks/`仍僅2個完整交易日parquet（`20260907`/`20260908`，`20260909`當日檔仍`.tmp`，較round494無變化，距20日門檻仍差18個交易日）；`hypothesis_queue`仍停在`#67`地基建置完成、尚未跑cheap gate，非本track範圍。**本輪工作單位＝發現並提報一個架構性問題：`#50`的tick累積樣本股票不在目標成交值區間（誠實查證，非新假說，屬「發現需要提案的架構問題」而非「已交辦任務」，依`CLAUDE.md`提案先於執行規則寫提案不直接動手）**：

過去8輪（round487~494）心跳持續記錄「`#50`卡tick累積，2/20，被動等待」，語氣暗示只要再等18個交易日資料就會就緒。本輪實地核對`data/ticks/20260908.parquet`實際涵蓋的股票代號（零新增API呼叫，純讀本機快取），發現訂閱清單來自`shioaji_quotes.py::DEFAULT_TW_WATCHLIST`（台積電2330/聯發科2454/鴻海2317/中興電1513/緯創3231）加上`.live_watchlist.json`（App使用者自選股，目前跟預設值完全相同，代表使用者尚未額外加自選股）與固定訂閱指數/期貨——**這份清單的設計目的是支援App即時報價畫面，從未對齊過`#50`要求的「日均成交值500萬～5,000萬新台幣」區間**。用既有tick快取估算單日成交值（`sum(close×volume)`），15檔全部落在明顯超出目標上限的大型/中型股範圍（最小的1513都約2.1億元，超出目標上限4倍以上；最大的2330約638.7億元）。**問題本質**：成交值區間是由「訂閱了哪些代號」決定，不是由「訂閱了多久」決定——用現在這份清單，累積200個交易日一樣是0檔落在目標區間，不是樣本不夠長，是樣本股票從一開始就選錯了。已寫成`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`提報：建議善用`MAX_DYNAMIC_SUBSCRIPTIONS=100`目前僅用5個的餘裕，加入一批專門為`#50`取樣、落在目標成交值區間的代號，但**未直接執行**——這牽涉常駐服務`shioaji_quotes.py`的訂閱名單變更（`CLAUDE.md`七之三常駐服務發布紀律＋外部API頻率上限風險，且可能與使用者實際自選股互動），依「提案先於執行」規則需先經核准，不是純bug修復也不是已明確交辦的具體做法。**未動任何生產程式碼或訂閱設定**，只新增文件與本輪記錄。

`trial_registry.py --check`本輪未重跑（無新試驗需登記，這是發現與提案，不是判定）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀`data/ticks/`既有parquet與`.live_watchlist.json`/`shioaji_quotes.py`原始碼）。**下一輪任一軌接手**：`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`待總司令核准，核准前心跳裡再提到「`#50`卡tick累積」都要附註引用本提案，不要無意識重複過去8輪暗示「等時間到就好」的框架；若提案未獲回應，`#50`本身仍视为未結案（嚴格說還不到0a節「無可驗證預測優勢」提報門檻，但候選池已非常薄）。完整見`PROPOSAL_2026-09-09_gate50_tick_universe_mismatch.md`、`REPORT.md`第495輪心跳。

---

**上一則保留（第493輪，供對照）**——取鎖乾淨（cycle`20260909-163036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 15:30（round491，較舊）／US 16:00（round492，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；另用`Get-CimInstance Win32_Process`確認無`hypothesis_queue`/`odd_lot`相關背景行程在跑，無並行風險。**核實候選池現況不變**：0a節四條方向＋`#61`~`#66`全數結案，`data/ticks/`仍僅2個完整交易日parquet（`20260909`當日檔仍`.tmp`未finalize，較round492無變化）；`git log`確認`hypothesis_queue`排程已於本輪之前（commit`831874a9`）完成`#67`（盤中零股委託簿失衡度）三來源可行性查證＋地基建置（`twse_odd_lot_client.py`/`backfill_odd_lot.py`，pilot 30天驗證通過），尚未跑第1關cheap gate，非本馬拉松三軌工作範圍（依round487教訓，避免與該排程自己的下一輪重疊執行，本輪未碰`backfill_odd_lot.py`）。**本輪工作單位＝核實`CALIBRATION_PROBE.md`給馬拉松的操作指令是否已完整結案（誠實查證，非新假說）**：

`CALIBRATION_PROBE.md`結論(乙)曾指示「下一輪TW軌第一個工作單位＝用300檔樣本重跑`portfolio_multifactor_v2`……接著依序重跑#77/#79/#91的cheap gate。US/FUT軌的#47/#52/#34同理各自重跑」。逐一核對`TRIALS_LEDGER.md`確認：

1. `factor_ic.py::SAMPLE_SIZE`目前確實已是`300`（非探針前的100），修管線動作本身已落地。
2. TW軌三項——`#79`（`f_inst_streak_days`，`TRIALS_LEDGER.md`#100，percentile 86.1仍未過90.0，維持FAIL）、`#77`（`f_rel_strength`產業中性版，#101，percentile從82.8驟降至41.9，維持FAIL）、`#91`（`revenue_trend_surprise_low_attention`，#106，低關注度組維持FAIL/高關注度組意外翻轉CHEAP_PASS但因TRAIN期IC幾乎為零、判定不列入候選）——**皆已於round340前後完整重跑並記錄**。
3. US軌`#47`（`f_us_low_vol`大型股tier，#104，cheap-gate翻盤CHEAP_PASS但策略構造層維持FAIL不變）、`#52`（性質不同，死因是1b深挖非cheap-gate檢定力問題，已移出「待重跑」清單）**亦皆已結案**。
4. FUT軌`#34`已由round328（#99）查證確認「同理各自重跑」對FUT軌不成立（無holdout安全的擴大樣本手段），維持FAIL，非「待重跑」項目。

**結論：`CALIBRATION_PROBE.md`給馬拉松的操作指令鏈已100%執行完畢，不是「候選池以外的待辦」，是已結案項目**——此前TW/US_MARATHON_STATE只各自零散提到個別項目結案（#100/#101/#104/#106各自的心跳），未曾有一輪明確寫下「探針指令鏈全數結案」這個橫向總結，本輪補齊這個確認，避免未來輪次誤以為這條指令鏈還有殘留待辦。**未產生任何新判定**（未跑新的數字，純核對既有`TRIALS_LEDGER.md`記錄），依`CLAUDE.md`「純bug修復/查證」性質，不需先提案。

`trial_registry.py --check`本輪未重跑（無新試驗需登記）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`/`.py`檔案）。**下一輪任一軌接手**：`#50`tick累積仍是唯一活動候選（查`data/ticks/`是否已到3/20）；若`hypothesis_queue`已推進`#67`cheap gate，核對其設計與結果是否符合「真正跳脫既有清單」標準即可；候選池已連續多輪（487~493）皆無TW/US/FUT三軌自身可推進的新工作單位，暫不需要提報0a節「無可驗證預測優勢」結論（`#50`本身未結案前嚴格說還不到）。完整見`TRIALS_LEDGER.md`#100/#101/#104/#106、`REPORT.md`第493輪心跳。

---

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489/491輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
