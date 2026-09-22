

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-09-23T05:3x+08:00（馬拉松第609輪，研究帽）**——取鎖乾淨
（cycle`20260923-053037`）。開工先照CLAUDE.md「交辦優先於自走」讀
`PENDING_QUEUE.md`：`- [ ]`=0，23條`- [!]`阻塞中；逐一核對阻塞項開頭
標記可能已解除的條件，皆未到解除時間點，維持`- [!]`（含`金流一.4`
法人歷史累積、`資料源一.3`待總司令領key、`#50`tick累積、`外部一改`
系列、`Cybex.beta`架構裁示待回應等）。**佇列深度自檢**：`- [ ]`=0
（<12下限），round599~608已連續十輪確認三個備援來源掃無新項，本輪
不重複全面掃描。三軌時間戳：TW round608=09-23 04:3x（最新）／FUT
round607=09-23 03:3x／**US round606=09-23 02:3x（最舊）**——依輪替
選US。`run_detached.py status`：`running=0`（151筆歷史，無running job
需收成）。`git status`僅例行排程檔案（`audit_report.json`/
`factory_stability*`/`connectivity_check.log`等），無conflict標記、
無孤兒未commit產出，round607修復的git stash衝突未復發。
**本輪查證**：`AWAITING_REVIEW.md`「規.二第4節參數掃描方式提案」仍
`等待中`（round605完成、尚無總司令回應），`CONCENTRATED_SPEC.md`
第4節候選A/B/C未核准前`concentrated_backtest.py`不得動筆，此關卡
同時擋住TW與US兩軌集中版框架（第4節參數不分市場），非US軌獨有阻塞；
round606已完成的US軌地基工程（`sp500_tr_series.py`）與round608已
完成的TW軌文件更正皆已就緒，**第4節提案審閱結果出爐前，集中版路線
兩軌皆無可再推進的新工作單位**。逐一核對`US_LEADS.md`/
`STRATEGY_GRAVEYARD.md`確認price-only因子家族（低波動/動能/反轉）
結案狀態未變（round557/599已收斂，無新遺漏）；`MARATHON_PROTOCOL.md`
0a節四條新方向中`#49`/`#51`/`#52`已FAIL結案、`#50`屬TW/FUT範疇被動
等待tick累積，US軌本身無對應的結構性優勢候選可開新方向（沿用
round599既有結論，非本輪新判斷）。**本輪誠實結論：US軌本輪無新增
可推進工作單位**——依`CLAUDE.md`七之三節研究紀律「找不到就老實說
找不到」與`MARATHON_PROTOCOL.md`「不得無限期換皮測試」，不硬湊候選。
未執行任何新統計判定，不觸發`register_trial()`。`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（347列，最大編號
#345，本輪未新增判定）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本
檔案、`git status`、`run_detached.py status`、`trial_registry.py
--check`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列
還剩0條未開始**（23條`- [!]`阻塞中）。**等待審閱：1件**（規.二第4節
參數掃描方式提案，非本輪新增，延續中）。**下一輪任一軌接手**：規.二
第4節提案審閱結果是集中版框架兩軌（TW/US）共同的唯一解鎖點，出爐前
建議下一輪比照本輪做精簡確認即可，不必每輪重新全面掃描；`#50`仍
被動等待tick累積至20（13/20，`data/ticks/`）；依輪替下一輪建議選
FUT軌（TW/US本輪皆已碰過）。完整見`REPORT.md`第609輪心跳、
`AWAITING_REVIEW.md`。

---
**最後更新：2026-09-23T02:3x+08:00（馬拉松第606輪，研究帽）**——取鎖乾淨
（cycle`20260923-02xxxx`）。開工先照CLAUDE.md「交辦優先於自走」讀
`PENDING_QUEUE.md`：全文0條`- [ ]`，23條`- [!]`阻塞中，逐一核對開頭
標記可能已解除的阻塞項（金流一.4等待資料累積、資料源一.3等待總司令
領key、#50等待tick累積與gate50裁示等）皆未到解除時間點，維持
`- [!]`。**佇列深度自檢**：`- [ ]`=0（<12下限），round599~605連續
多輪已確認三個備援來源掃無新項，本輪不重複全面掃描（避免重工），
改直接處理下方查到的既有缺口。三軌時間戳：TW round605=09-23 01:3x
（最新）／FUT round600=09-22 19:3x／**US round599=09-22 18:3x（最舊）**
——依輪替選US。`run_detached.py status`：`running=0`（151筆歷史，
無running中的job需收成）。**round599既有結論**：US軌price-only因子
家族（低波動/動能/反轉）已全數FAIL收斂，US軌若要延續新方向需總司令
裁示（`MARATHON_PROTOCOL.md`0a節四條方向#49/#50/#51/#52主要屬TW/FUT
範疇）。**本輪工作單位**（`[自行裁量]`：US軌本身無可自行開跑的新
方向，但`CONCENTRATED_SPEC.md`第3節記錄一個明確、不需要新方向裁示
的既有資料缺口——S&P500 Total Return序列，屬於「地基工程」而非
「策略/因子新試驗」，選它作為本輪US軌可推進項）：新增
`sp500_tr_series.py::load_sp500tr_full_history()`，查證候選#1
（Yahoo Finance`^SP500TR`）：沿用既有`yf_price_client.py::
fetch_yf_index()`基礎設施（零新增抓取邏輯），取得1990-01-02起完整
歷史（裁至`VAL_END`後8816列，`close`欄位零缺值）；驗證方式：
2003-06-30~2024-12-31同期比較，`^SP500TR`年化報酬10.87% vs 價格
報酬指數`^GSPC`同期8.74%，缺口2.1個百分點/年，與S&P500歷史平均
股利殖利率量級（約1.8~2.2%/年）吻合，確認`^SP500TR`確實是計入股利
再投資的total return序列，非價格指數誤標；回傳欄位（date/adj_close）
與`survival_constraint_allocation_test.py::load_0050_full_history()`
相容，供`concentrated_backtest.py`核准動筆後直接複用；
`holdout.assert_no_holdout_leakage()`已內建檢查，通過。更新
`CONCENTRATED_SPEC.md`第3/11節反映此缺口已解決，並明確註記
「解決缺口≠核准推進美股集中版」——第4節參數掃描方式仍待總司令裁示
（`AWAITING_REVIEW.md`），美股集中版是否要推進本身也是需要總司令
裁示的新方向判斷，本輪只是清除一個「就算核准了也做不了」的技術性
障礙。純資料查證與工具函式新增，非統計判定，不觸發`register_trial()`。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（346列，本輪未新增判定）。`validation/holdout.py::
is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫
（yfinance請求走既有`yf_price_client.py`快取機制，非本專案「頻率上限
清單」列管對象，且僅一次性抓取單一指數序列）。`PROGRESS_HEARTBEAT.
jsonl`已append本輪一行。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞
中）。**等待審閱：1件**（規.二第4節參數掃描方式提案，見
`research/AWAITING_REVIEW.md`，非本輪新增，round605延續）。**下一輪
任一軌接手**：US軌新方向仍待總司令裁示，`sp500_tr_series.py`已就緒
可供未來美股集中版或其他需要S&P500 TR基準的工作直接複用；依輪替
下一輪建議選FUT軌（TW round605/US round606皆本輪或上輪已碰過）。
完整見`REPORT.md`第606輪心跳、`MARATHON_STATE.md`（輪次計數器606）、
`CONCENTRATED_SPEC.md`第3/11節、`sp500_tr_series.py`。

---
**最後更新：2026-09-22T18:3x+08:00（馬拉松第599輪）**——取鎖乾淨（cycle`20260922-183037`）。開工先照CLAUDE.md「交辦優先於自走」鐵律讀`PENDING_QUEUE.md`：全文0條`- [ ]`（僅`2026-09-22總司令裁示【方法論重建】`三條已全數`[x]`完成，含出場.零/宇宙.零登記），24條`- [!]`阻塞中。**佇列深度自檢**：`- [ ]`=0（<12下限），依三個備援來源盤點——`HYPOTHESIS_QUEUE.md`「排隊中」grep僅命中2處歷史敘述（非新項）；`TW_LEADS.md`/`US_LEADS.md`/`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`「下一步/待辦」逐一核對後，**發現本輪要做的事本身正好是round557交辦的那個未完成盤點**（見下），故不另外硬湊補件，優先完成這項既有交辦。三軌時間戳：TW round598=17:4x（最新）／FUT round562=09-19（09-19後無新機制候選）／**US round559=09-19 11:17（最舊）**——依輪替選US。`run_detached.py status`：`running=0`（147筆歷史）；round559提到的job`20260919-110815-d4cf`已不在近期登記簿窗口內（3天前的舊job，未查得finished/failed紀錄，研判早已被後續稽核/DevQueue自走接手完成——查`data/stock_detail.json`現況`financials_updated_count`=844，`generated_at`=2026-09-22T08:13（market.yml每日自動更新），`find_gap_codes()`實測剩8檔，與`PENDING_QUEUE.md`常備backlog區塊「稽核.三(a)…剩8檔量級」的既有結論一致——**這條「下一步」已由市場日排程自動吸收，非本輪US軌待辦**，不重複投遞）。**本輪真正工作單位＝round557交辦的候選池盤點**（「US軌候選池需重新盤點是否還有其他類似round446那種CHEAP_PASS但下一步從未執行的遺漏，可先掃`US_LEADS.md`各條目下一步欄位」）：逐列核對`US_LEADS.md`全表33列，找出`f_us_momentum_12m`中型股tier N=30版（#8，`TRIALS_LEDGER.md`#53，CHEAP_PASS）符合這個形狀——但查證後發現**不需要新的深挖工作**：同一批`us_factor_ic_by_size.py`已在round446的N=90重跑中把這格一併測過（`US_LEADS.md`#28、`TRIALS_LEDGER.md`#207，percentile僅60.0，FAIL），這個換大樣本重跑本身已經是比1b深挖更早、更省成本的否證，跟`f_us_low_vol`中型股tier（cheap gate換N=90後仍CHEAP_PASS、要靠1b深挖才現形）是不同死法。逐一核對`f_us_momentum_12m`四個樣本規模組合（不分層#44/大型#48+#204/中型#53+#207/小型#58）確認全數FAIL，`f_us_value_bm`（#16，book-to-market非乾淨宇宙版）已由round350~425「9輪短腿診斷鏈」的乾淨宇宙版FAIL結論涵蓋（`STRATEGY_GRAVEYARD.md`既有段落），非新遺漏。**產出**：`STRATEGY_GRAVEYARD.md`新增「f_us_momentum_12m（美股12-1動能）」家族結案段落（引用既有#44/#48/#53/#58/#204/#207，未執行新的統計檢定，純文件盤點與判定綜整，不需要`register_trial()`）；`US_LEADS.md`#8列追加結案註記，指向`STRATEGY_GRAVEYARD.md`。**至此US軌price-only因子家族（低波動/動能/反轉）三者、四個樣本規模組合、共計約20筆試驗全數FAIL收斂，0 PASS/EXPERIMENTAL**——這個結論本身不觸發`MARATHON_PROTOCOL.md`0a節「四條新方向全部結案後才誠實提報」門檻（0a節的四條方向`#49`/`#50`/`#51`/`#52`是不同的新方向清單，price-only因子屬於更早、已被0a節裁示放棄的舊方向，本輪只是把舊方向殘留的CHEAP_PASS遺漏補齊結案文件，不是新的0a結論）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（331列，最大編號#329，本輪未新增試驗判定——純引用既有已登記編號的文件綜整）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本檔案）。**交辦佇列還剩幾條未開始**：0條`- [ ]`；24條`- [!]`阻塞中，其餘待總司令。**下一輪任一軌接手**：round557交辦的候選池盤點至此完成（`f_us_low_vol`round557已結案、`f_us_momentum_12m`本輪結案、`f_us_value_bm`確認非遺漏），US軌price-only因子路線已窮盡；若無總司令新裁示，下一輪US軌建議轉往`MARATHON_PROTOCOL.md`0a節四條新方向裡US軌尚可推進的部分（目前#49/#50/#51/#52主要是TW/FUT範疇，US軌若要延續需先確認是否有對應的美股版本結構性優勢，這是需要總司令裁示的新方向判斷，不是本輪自行裁量範圍）；依輪替下一輪建議選FUT軌（TW/US本輪皆已碰過）。完整見`REPORT.md`第599輪心跳、`MARATHON_STATE.md`（輪次計數器599）、`STRATEGY_GRAVEYARD.md`「f_us_momentum_12m」段落、`US_LEADS.md`#8。