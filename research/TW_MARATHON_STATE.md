# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-09T16:30+08:00（馬拉松第493輪）**——取鎖乾淨（cycle`20260909-163036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 15:30（round491，較舊）／US 16:00（round492，最新）——FUT跳過後依輪替選TW。開工查`run_detached.py status`：`running=0`；另用`Get-CimInstance Win32_Process`確認無`hypothesis_queue`/`odd_lot`相關背景行程在跑，無並行風險。**核實候選池現況不變**：0a節四條方向＋`#61`~`#66`全數結案，`data/ticks/`仍僅2個完整交易日parquet（`20260909`當日檔仍`.tmp`未finalize，較round492無變化）；`git log`確認`hypothesis_queue`排程已於本輪之前（commit`831874a9`）完成`#67`（盤中零股委託簿失衡度）三來源可行性查證＋地基建置（`twse_odd_lot_client.py`/`backfill_odd_lot.py`，pilot 30天驗證通過），尚未跑第1關cheap gate，非本馬拉松三軌工作範圍（依round487教訓，避免與該排程自己的下一輪重疊執行，本輪未碰`backfill_odd_lot.py`）。**本輪工作單位＝核實`CALIBRATION_PROBE.md`給馬拉松的操作指令是否已完整結案（誠實查證，非新假說）**：

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

**上一則保留（第489輪，供對照）**——取鎖乾淨（cycle`20260909-130036`）。三軌時間戳：FUT 10:30（round484，最舊，但無新機制、依例外條款不選）／TW 12:00（round487）／US 12:30（round488，最新）——FUT跳過後依輪替選TW（TW較US舊）。開工查`run_detached.py status`：`running=0`，無heavy-job-slot佔用。**核實候選池現況不變**：0a節四條方向＋`#61`~`#65`全數結案，僅`#50`仍卡tick累積——實測`data/ticks/`本輪仍僅2個完整交易日parquet（`20260907`/`20260908`），較round487無變化，距20日門檻仍差18個交易日。**本輪工作單位＝`data/signal_status.json`完整性維護（純資料/文件補齊，比照round485先例）**：round488心跳確認`hypothesis_queue`排程已於12:22正式將`#65`（產業龍頭股跨期領先-落後動能）判定FAIL並登記`TRIALS_LEDGER.md`/`TRIALS_REGISTRY.jsonl`#229、寫入`STRATEGY_GRAVEYARD.md`（`f_leader_follower_lag`條目），但`build_signal_status.py`的`DIRECTIONS`常數尚未補上這一條，會讓App將來對使用者揭露的「測過、沒用」清單漏掉`#65`。已逐字核對`STRATEGY_GRAVEYARD.md`的`f_leader_follower_lag`條目內容後，比照`#62`/`#63`/`#64`格式新增對應段落（含`note`欄位註明「非0a節四條方向之一」），重跑`build_signal_status.py`驗證：`directions`清單`ids=['49','50','51','52','62','63','64','65']`共8條，`git diff -b`確認除新增段落外無其他內容被更動。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（231列，撞號2組皆為歷史存量不回頭改寫）。`is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純核對既有結案文件）。**下一輪任一軌接手**：`#50`tick累積仍是唯一活動候選，純被動等待（查`data/ticks/`是否已到3/20）；`hypothesis_queue`排程下一輪會自行設計`#66`（美股年末稅損收割/一月效應，見`HYPOTHESIS_QUEUE.md`尾端，尚未跑第1關），非本馬拉松三軌工作範圍，屆時可核對其設計是否符合「真正跳脫既有清單」標準即可；若TW/US/FUT三軌本輪皆無新工作單位可做，且找不到真正跳脫既有清單的新機制，下一次盤點時應誠實評估是否已接近0a節「無可驗證預測優勢」正式結論的提報時機（但`#50`未結案前嚴格說還不到門檻）。完整見`data/signal_status.json`（本輪新增`65`一條）、`build_signal_status.py`（本輪新增對應`DIRECTIONS`段落）、`REPORT.md`第489輪心跳。

（第430/432/437/439/441/443/445/447/449/451/453/455/457/459/461/463/465/467/469/470/471/472/474/475/477/478/480/482/485/487輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
