# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-09T17:30+08:00（馬拉松第495輪）**——取鎖乾淨（cycle`20260909-173036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 16:30（round493，較舊）／US 17:00（round494，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`，無heavy-job-slot佔用；`git log`確認round494後無新commit。**核實候選池現況不變**：0a節四條方向＋`#61`~`#66`全數結案，`data/ticks/`仍僅2個完整交易日parquet（`20260907`/`20260908`，`20260909`當日檔仍`.tmp`，較round494無變化，距20日門檻仍差18個交易日）；`hypothesis_queue`仍停在`#67`地基建置完成、尚未跑cheap gate，非本track範圍。**本輪工作單位＝發現並提報一個架構性問題：`#50`的tick累積樣本股票不在目標成交值區間（誠實查證，非新假說，屬「發現需要提案的架構問題」而非「已交辦任務」，依`CLAUDE.md`提案先於執行規則寫提案不直接動手）**：

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

**上一則保留（第491輪，供對照）**——取鎖乾淨（cycle`20260909-153036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 13:00（round489，較舊）／US 15:00（round490，最新）——FUT跳過後依輪替選TW。**本輪工作單位＝跨軌基礎設施修復：`candidate_report.py --audit`稽核程式假陽性＋兩筆過期判定欄更正**（例行跑`--audit`檢查全體LEADS檔案完整性時發現的真實缺陷，非新假說測試）：

1. **`--audit`本身有假陽性**：舊版`audit()`函式從右往左掃描每一列**全部欄位**找判定關鍵字（`CHEAP_PASS`/`PASS`/`FAIL`等），只要任何欄位（包含「經濟解釋」「備註」這種自由文字欄）出現判定字樣就誤判。實測抓到`FUT_LEADS.md`第46行（`#64`台指期貨基差regime）：該列判定欄本身明明白白寫`**FAIL**（未過...雖percentile=97.0在舊標準下會誤判CHEAP_PASS）`，但因為判定欄自己的說明文字裡提到了「CHEAP_PASS」四個字，且`VALID_VERDICTS`常數裡`CHEAP_PASS`排在`FAIL`前面優先比對，掃描邏輯就誤判這列是CHEAP_PASS並要求並列DSR。
2. **修復**：改用表頭動態鎖定「判定」欄位實際位置（`TW/US/FUT_LEADS.md`與舊`LEADS.md`欄位數不一致，不能寫死欄位序號），且同一欄位內若仍夾雜多個判定關鍵字（前述FAIL列的例子），改採**字串中最早出現的位置**而非固定的關鍵字檢查順序，這樣真正的判定詞（通常在欄位開頭）會贏過稍後才出現、只是在解釋別的判定標準的提及。修復後`--self-test`全過、候選列數從38列（含假陽性）降到18列。
3. **修復稽核程式的過程中，順手發現兩筆真正過期未同步的判定欄**（不是DSR缺失，是判定欄文字沒有跟著同一列「備註」欄的最終結論更新，屬於資料一致性bug）：
   - `US_LEADS.md`第34行（`#23 f_us_gross_profitability`）：判定欄仍寫`CHEAP_PASS`，但備註欄早已記錄round429`deep_dive_f_us_gross_profitability_contamination_check.py`確認`CONFIRMED`（5檔已知死亡螺旋型反向分割微型股佔空頭腿79次腿位分配中的76次，排除後VAL報酬從+33.77%驟降至+1.53%），`TRIALS_LEDGER.md`#193已正式判`FAIL`（跟`#20`/`#21`同一個`adj_close`資料完整性陷阱），判定欄卻沒跟著改。已更正為`FAIL`並引用#193。
   - `US_LEADS.md`第73行（`#28 f_us_low_vol`中型股tier，N=90重跑）：判定欄領頭寫`CHEAP_PASS（非新候選，見備註）`，但備註欄已明言該因子家族早於`TRIALS_LEDGER.md`#14/#68深挖階段確定`FAIL`（TRAIN期percentile僅12-16、beta持續為負且更負），本輪只是cheap-gate層級的重複確認、不觸發重新深挖。已把判定欄改為以`FAIL`領頭，同時保留cheap-gate層級CHEAP_PASS的說明文字。
4. **未動任何原始判定的統計結果本身**（IC/百分位/報酬數字皆未更動，只更正欄位文字跟稽核程式邏輯）——依`CLAUDE.md`「純bug修復」例外，不需要先提案即可直接做。三處修正後`--audit`乾淨PASS（0違規，18列全數已並列DSR或屬2026-09-07前存量不強制）。

`trial_registry.py --check`exit=0 PASS（232列，撞號2組皆為歷史存量不回頭改寫，本輪未產生新判定，只是更正既有判定欄文字讓它跟已登記的帳本結論一致，不需要新的`register_trial()`呼叫）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀寫既有`.md`/`.py`檔案）。**下一輪任一軌接手**：`#50`tick累積仍是唯一活動候選（查`data/ticks/`是否已到3/20）；`hypothesis_queue`排程下一輪會從設計`#67`開始，非本馬拉松三軌工作範圍；候選池已連續多輪（487~491）皆無TW/US/FUT三軌自身可推進的新工作單位，若下一輪盤點仍是同樣狀態且找不到真正跳脫既有清單的新機制，應開始認真評估是否接近0a節「無可驗證預測優勢」提報門檻（`#50`本身未結案前嚴格說還不到）。完整見`candidate_report.py`（修正`audit()`函式）、`US_LEADS.md`（更正#23/#28判定欄）、`REPORT.md`第491輪心跳。

---

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487/489輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
