# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-25T17:34:50+08:00**（馬拉松第69輪：basis家族地基第二步完成——`fut_basis_series.py`把近月期貨×TAIEX現貨inner join算出basis序列，全樣本6185/6185列100%覆蓋，分布合理（均值貼水-0.2%，唯二極端值都在2008金融海嘯期間）；意外撞到並修復`validation/holdout.py`的pandas 3.0.5相容性bug（Timestamp跟字串比較不再自動轉型），已smoke test驗證修復不影響既有呼叫者行為）

**地基狀態：🟢 完整可用（純技術面），🟡 三大法人期貨部位地基本輪補齊但發現重大樣本限制。** `continuous_contract.py`（連續合約建構）、轉倉時點規則（H1）、資料欄位品質（`settlement_price`/`open_interest`/`institutional_investors`）、累積漂移幅度全部已驗證，可直接測純技術面短中期因子。**新發現（第39輪）：`TaiwanFuturesInstitutionalInvestors`（三大法人期貨部位）全歷史範圍實際只從`2018-06-05`起有資料，不是預期的`2000-01-01`——可用樣本只有1605天（全歷史6191天的26%）。** 資料品質本身乾淨（無NaN/負值、類別完整、跟`continuous_contract`聚合OI交叉核對後無異常，細節見`FUT_LOG.md`本輪記錄跟`DATA.md`第6節），但這個樣本規模天花板是設計該因子便宜關卡時必須考慮的限制，不能跟前6個FAIL假說（全樣本6185天）用同一套統計檢定力預期比較。詳見 `FUT_CONTINUOUS_CONTRACT_DESIGN.md`。

**✅ 本輪（第36輪）完成：換家族第一批，籌碼面（OI確認）+季節性（週一效應）各測1個，全部FAIL。** 累計已測6個策略假說，全部FAIL（詳見 `FUT_LOG.md` 本輪記錄、`FUT_LEADS.md` #1–#6、`TRIALS_LEDGER.md` #18–#23）：

| 假說 | 訊號家族 | percentile（門檻90.0） | 判定 |
|---|---|---|---|
| `fut_trend_multi_tf` | 10/20/60日動能多數決 | 82.5 | FAIL |
| `fut_donchian_breakout_20` | 20日通道突破 | 61.0 | FAIL |
| `fut_ma_crossover_20_60` | 20/60日SMA均線交叉 | 75.5 | FAIL |
| `fut_vol_regime_trend` | 動能訊號+波動regime過濾（結構性變體） | 82.5（跟未過濾版打平） | FAIL |
| `fut_oi_price_confirm_5d` | 1日價格方向經5日OI變化過濾（籌碼面，第一次換家族） | 62.0（方向正確） | FAIL |
| `fut_weekday_effect` | 週一放空/週二至五做多，固定規則（季節性，第一次換家族） | 13.5（方向不對） | FAIL |

**六個都沒過便宜關卡，依協定不調參數硬救，直接記錄。** 前4個是純技術面同源家族（regime過濾對`fut_trend_multi_tf`沒有可辨識改善），第36輪首次換到機制完全不同的兩個家族（籌碼面、季節性）測試，結果仍是FAIL——`fut_oi_price_confirm_5d`方向正確但強度不夠；`fut_weekday_effect`不只沒過，隨機打散還大幅贏過真實策略（隨機中位數+308.1% vs 真實+19.7%），暗示台指期樣本內沒有美股文獻描述的負向週一效應。

**✅ 本輪（第39輪）完成：三大法人期貨部位地基探測，`fut_probe_institutional_positions.py`。** 資料集本身乾淨可用，但發現全歷史範圍實際只從2018-06-05起有資料（1605/6191天，26%覆蓋率）——這是資料源天生的樣本限制，不是可以修的品質問題。完整見上方地基狀態段落、`FUT_LOG.md`本輪記錄、`DATA.md`第6節更新。**沒有新增`TRIALS_LEDGER.md`列**（地基驗證不是假說測試，跟先前漂移探測/PIT驗證同精神）。

**✅ 本輪（第42輪）完成：三大法人期貨部位第一批假說測試，外資水位/動能各測1個。** `fut_cheap_gate.py`新增`_load_institutional_net_position()`（inner join限制樣本1605天，2018-06-05起）＋兩個假說：`fut_inst_foreign_net_position_sign`（水位，percentile=57.5，**FAIL**）、`fut_inst_foreign_net_position_change_5d`（5日動能，percentile=97.0，單測/批次過但累積校正n=25門檻99.6未過，**CHEAP_PASS（批次），累積校正後降級為不確定，不排入深挖清單**）。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#7/#8、`TRIALS_LEDGER.md`#24/#25。全程零額外API呼叫（沿用第39/7輪的全歷史parquet快取）。

**✅ 本輪（第45輪）完成：三大法人期貨部位第二批假說測試，投信水位/動能各測1個。** 沿用第42輪已寫好的`_load_institutional_net_position()`，換`category="投信"`，不需要重寫地基。`fut_inst_trust_net_position_sign`（水位，percentile=41.5，方向不對，**FAIL**）、`fut_inst_trust_net_position_change_5d`（5日動能，percentile=96.5，單測/批次過但累積校正n=27門檻99.63未過，**CHEAP_PASS（批次），累積校正後降級為不確定，不排入深挖清單**）。**值得留意的觀察（非結論）：外資（#25）跟投信（本輪#27）連續兩個類別的動能假說都是同一種「批次過、累積校正未過」模式**，需要更多證據（自營商結果或N_SHUFFLES加密）才能判斷是巧合還是這個訊號家族的共通特性。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#9/#10、`TRIALS_LEDGER.md`#26/#27。全程零額外API呼叫（沿用第39/7輪的全歷史parquet快取）。

**✅ 本輪（第48輪）完成：三大法人期貨部位第三批假說測試，自營商水位/動能各測1個，完成整個家族。** 沿用第42/45輪已寫好的`_load_institutional_net_position()`，換`category="自營商"`，不需要重寫地基。`fut_inst_dealer_net_position_sign`（水位，percentile=42.5，**FAIL**）、`fut_inst_dealer_net_position_change_5d`（5日動能，percentile=25.0，方向也不對，**FAIL**）。**跟外資/投信不同：自營商動能版連批次都沒過，不是又一個「批次過但累積校正未過」——這打破了外資/投信連續兩輪觀察到的模式，暗示那個模式（動能版批次過）不是這整個訊號家族的共通特性，至少自營商類別不適用。** 三大法人期貨部位家族（水位×動能×3類別=6個假說）至此全部測完：0 PASS、4 FAIL（外資水位/投信水位/自營商水位/自營商動能）、2 CHEAP_PASS但累積校正後不確定（外資動能/投信動能）——**這個訊號家族目前沒有任何一個假說進入深挖清單**。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#11/#12、`TRIALS_LEDGER.md`#28/#29。全程零額外API呼叫（沿用第39/7輪的全歷史parquet快取）。

**✅ 本輪（第51輪）完成：高解析度重測`fut_inst_foreign_net_position_change_5d`／`fut_inst_trust_net_position_change_5d`，三大法人期貨部位家族完全結案。** 新增`fut_recheck_inst_momentum_highres.py`（monkey-patch `fut_cheap_gate.N_SHUFFLES`從200→2000，不改`fut_cheap_gate.py`檔案本身的預設值），零額外API呼叫（全程沿用本機parquet快取）。結果：外資動能percentile 97.0→97.40（10倍解析度下幾乎沒變），投信動能96.5→97.80（同樣幾乎沒變）——兩者都清楚低於n=31累積校正門檻99.68，**確認不是解析度不足造成的模糊，是確定沒有跨過門檻**。三大法人期貨部位家族（水位×動能×3類別=6個假說，跨第39/42/45/48/51輪）至此完全結案：0 PASS、4 FAIL、2「單測過但累積校正確認未過」，沒有任何候選進入深挖清單，**之後不需要再回頭處理這個家族，除非有全新的機制假說（非水位/動能的既有兩種構造）**。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#13、`TRIALS_LEDGER.md`#30/#31。

**✅ 本輪（第54輪）完成：換到日內均值回歸家族，地基確認完成（不需要新資料源），測了2個相反方向假說。** `build_continuous_series()`已有`adj_open`，隔夜跳空(`overnight_gap`)跟日內報酬(`intraday_ret`)可直接拆解，6185天樣本乾淨（僅1筆首日NaN，無零值/負值異常）。`fut_cheap_gate.py`新增`_permutation_test_same_day()`（同日內配對，跟既有跨日shift版本並存）。`fut_intraday_gap_reversal`（放空gap up、做多gap down，percentile=8.0，**FAIL**，且方向嚴重不對，92%隨機排列贏過真實策略）；`fut_intraday_gap_continuation`（相反方向，做多gap up、放空gap down，percentile=92.0，單測門檻90.0過但**本批次n=2校正門檻95.0未過**，累積校正n=33門檻99.70更沒過，**弱CHEAP_PASS，不排入深挖清單**）。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#14/#15、`TRIALS_LEDGER.md`#32/#33。全程零額外API呼叫（`build_continuous_series()`命中既有全歷史快取）。

**✅ 本輪（第57輪）完成：`fut_intraday_gap_continuation`高解析度重測，日內均值回歸家族第一批完全結案。** 新增`fut_recheck_intraday_gap_continuation_highres.py`（monkey-patch `fut_cheap_gate.N_SHUFFLES`從200→2000，同第51輪先例），零額外API呼叫（`_load_series()`命中`build_continuous_series()`既有全歷史快取）。結果：percentile 92.0→89.60——**跟第51輪三大法人動能假說重測後幾乎不變不同，這次明顯下降且首次跌破單測門檻90.0本身**，代表原本粗解析度讀數落在測量雜訊範圍內偏高估，不是被掩蓋的真訊號。日內均值回歸家族第一批（反轉`fut_intraday_gap_reversal`＋順勢`fut_intraday_gap_continuation`）現在完全結案：0 PASS，兩個方向都不通過。完整見`FUT_LOG.md`本輪記錄、`FUT_LEADS.md`#16、`TRIALS_LEDGER.md`#34。

**✅ 本輪（第60輪）完成：盤別效應家族地基第一步，探測`after_market`夜盤原始資料形狀。** 新增`fut_probe_night_session.py`，沿用`continuous_contract.load_position_session()`同一個快取鍵，零額外API呼叫。關鍵發現：(1) 夜盤15,607列，2017-05-16～2024-12-31，首日跟TAIFEX官方夜盤上線日（2017-05-15）只差一天，用全歷史範圍重新確認`after_market`＝夜盤的推論，信心等級從「一個月樣本間接推論」升級為「全歷史範圍一致無例外」；(2) 夜盤`settlement_price`／`open_interest`全歷史100%恆為0（不是NaN），跟`DATA.md`原本只用227列一個月樣本的結論完全一致，同樣升級到全歷史確認；(3) 夜盤OHLCV完整、約1.4%成交量為0（遠月合約合理現象）；(4) 夜盤也有價差列（30.6%），未來要沿用既有過濾規則；(5) **最重要的未解決風險**：夜盤`date`欄位代表的確切交易時段順序（相對日盤是「之後」還是「之前」）這輪只做了單一樣本合約的間接觀察，**沒有驗證清楚**，如果之後要建構夜盤連續序列或測盤別效應假說，這個時序假設沒搞對會讓報酬正負號整個顛倒卻看起來像正常結果。完整見`FUT_LOG.md`第60輪記錄。**沒有新增`TRIALS_LEDGER.md`列**（地基探測不是假說測試）。

**✅ 本輪（第63輪）完成：夜盤`date`欄位時序假設驗證，第60輪留下的最重要未解決風險已解決。** 新增`fut_verify_night_session_timing.py`，用session邊界價格gap比對法（正確的時序配對邊界跳動應該較小），全歷史10,600+列樣本、兩個獨立邊界（夜盤開盤/夜盤收盤）測試，結果一致且明確：**夜盤標示日期T實際代表「T前一晚15:00至T清晨05:00」這段，是即將到來的日盤T的前哨，不是日盤T收盤後才開始**——這推翻了第60輪筆記裡「理論上應該日盤收盤後才開始」的直覺假設，但吻合CME等海外期貨市場「夜盤標示為次一交易日」的常見慣例。H_B（夜盤介於日盤T-1與日盤T之間）在mean/median/多數列判定三個指標上全部一致勝出（H_A gap只在12.5%–16.1%的列上較小），且H_B兩個邊界gap（0.0015、0.0026）都明顯小於同日日盤盤中波動基準（0.0053），H_A兩個邊界gap（0.0077、0.0085）都大於這個基準，方向合理不模糊。完整見`FUT_LOG.md`第63輪記錄。**沒有新增`TRIALS_LEDGER.md`列**（時序驗證不是假說測試，同第39/60輪先例）。

**新增（第66輪）：basis家族地基第一步完成——現貨指數資料源確認。** `fut_probe_spot_index.py`實測3個候選FinMind`(dataset, data_id)`組合（不採信WebSearch/WebFetch給出的兩次互相矛盾的文件摘要，直接打API驗證）：`TaiwanVariousIndicators5Seconds`不支援多日區間查詢（HTTP 400，排除）；`TaiwanStockTotalReturnIndex`/`TAIEX`回傳的是股利再投資後的報酬指數（數值遠高於真實TAIEX，不是basis該用的現貨標的，排除但確認存在）；**`TaiwanStockPrice`/`TAIEX`是正確答案**——完整OHLC欄位，2024-01-02收盤17853.76跟真實TAIEX一致，全歷史（2000-01-04～2024-12-31）6,185列乾淨無NaN/無≤0異常/無重複日期，**列數剛好跟期貨連續序列全樣本天數一致**（列數巧合對上，還沒逐日join驗證覆蓋率）。完整見`FUT_LOG.md`第66輪記錄。

**下一輪建議工作單位（只做其中一項，優先順序由上到下）：**
1. **basis家族第一批假說便宜關卡測試**：`fut_basis_series.py`的`build_basis_series()`已經可以直接呼叫（回傳`date`/`fut_close`/`spot_close`/`basis`/`basis_pct`欄位，全樣本6185列100%覆蓋，已驗證乾淨），比照`fut_cheap_gate.py`既有框架加新假說函式即可，不用重寫框架。候選方向（挑1–2個測，不要一次全上）：basis水位（`basis_pct`本身）是否預示短期期貨報酬、basis變化動能（例如5日basis_pct變化）、basis均值回歸（偏離歷史均值後的回歸傾向）。記得累積校正門檻要讀`TRIALS_LEDGER.md`當下總列數。
2. 或者：夜盤時序方向已在第63輪解決，可以開始動`continuous_contract.py`寫夜盤感知的連續序列建構——但要注意：夜盤合約轉倉時點是否跟日盤同步這輪沒有檢查，動工前先確認（可能需要獨立的轉倉規則，不能假設照抄日盤的H1規則就對）。這是核心地基改動，風險較高，建議獨立一輪專門處理，不要跟其他工作單位混在同一輪。
3. （較低優先，不擋路）夜盤每日單一月份合約數（平均5.8檔）比日盤多這點，還沒逐日跟日盤比對確認差異幅度，留待以後需要精確銜接邏輯時再查。
4. （較低優先，不擋路）連續合約累積漂移的經濟成因未拆解（可能跟台股高股息殖利率、期現貼水有關）——可以另立為一個獨立假說排進候選清單，但不急。
5. **（較低優先，不擋路）** 目前累計15個FAIL、0 PASS，值得留意但不是本輪判斷：這批便宜關卡本身（原200次排列、90百分位門檻）對台指期日頻這個市場/頻率組合是否系統性偏嚴格，還是台指期本身在日頻、無成本、單一訊號框架下確實難找到邊際——**不要在還沒有更多證據前就調整門檻本身或懷疑`fut_cheap_gate.py`框架本身有問題**。

**Holdout 狀態：✅ 未被使用**（跟主線 `MARATHON_STATE.md` 共用同一套 `validation/holdout.py`，同一個 `HOLDOUT_LOCK.json`，本輪開始前跟結束前都確認 `is_holdout_consumed()` → `False`）。本輪零額外API呼叫（兩份輸入都命中既有全歷史parquet快取），`assert_no_holdout_leakage()`本輪意外撞到pandas 3.0.5相容性bug並已修復（見上方，型態正規化修法，未動`TRAIN_END`/`VAL_END`邊界常數本身，smoke test驗證修復不影響既有字串dtype呼叫者行為，且真正洩漏情境下仍正確`raise`）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。下一個馬拉松輪次接手時，先讀 `FUT_LOG.md` 最新一條看上一輪實際做到哪裡，再讀 `fut_cheap_gate.py` 了解目前已建立的便宜關卡測試框架（配對式隨機排列控制組，可以直接照樣加新的假說函式進去，不用重寫框架），再讀 `FUT_CONTINUOUS_CONTRACT_DESIGN.md` 了解連續合約設計決策全貌（含漂移幅度量測結果，地基章節已標記完成）。**開始測新因子/策略時，先確認回看窗口長度合理（短中期已驗證安全；有需要可以直接呼叫 `fut_drift_probe.py` 的邏輯查特定窗口長度的漂移量級），並比照 `TW_MARATHON_STATE.md`／`US_MARATHON_STATE.md` 的先例，判定結果記進 `TRIALS_LEDGER.md`（累積總帳）跟 `FUT_LEADS.md`（本軌候選）。已測過FAIL的15個訊號（純技術面/籌碼面/季節性6個 + 三大法人部位水位×3類別+自營商動能4個 + 日內跳空反轉/順勢2個，含各自的高解析度重測）不要重測相同設定。**三大法人期貨部位家族已完全結案（第39輪補齊地基，第42/45/48輪分別測完外資/投信/自營商三類別，第51輪用高解析度重測確認最後2個「不確定」假說也未過：六個假說最終結果4 FAIL+2確認未過+0 PASS）。日內均值回歸家族第一批也已完全結案（第54輪測反轉/順勢兩個方向，第57輪用高解析度重測確認順勢版原本的92.0讀數是測量雜訊偏高估，實際89.60未過單測門檻：兩個方向2 FAIL+0 PASS）。**這兩個家族都不再是接手優先項，也不需要再回頭補做任何變體，除非有全新的機制假說。**盤別效應家族地基：第60輪完成`after_market`夜盤資料形狀探測，第63輪解決夜盤時序方向的關鍵風險（確認夜盤(T)落在日盤(T-1)與日盤(T)之間），**目前可以安全動`continuous_contract.py`寫夜盤連續序列，但夜盤轉倉時點是否跟日盤同步這輪還沒檢查**，動工前先確認。**basis家族地基：第66輪完成第一步（現貨指數資料源確認），第69輪完成第二步（`fut_basis_series.py`的`build_basis_series()`，近月期貨×TAIEX現貨inner join，全樣本6185/6185列100%覆蓋，分布合理已驗證）——地基完整可用，可以直接開始測basis假說，不需要再搭建。** 這兩個地基分支（夜盤連續序列、basis假說測試）互相獨立，接手時任選一個即可，不會互相阻擋。**另外第69輪意外修復了`validation/holdout.py`一個pandas 3.0.5相容性bug（`Timestamp`跟字串比較不再自動轉型，會讓`assert_no_holdout_leakage()`等函式對已經轉型`datetime64` dtype的輸入直接crash）——這是全三軌共用的安全檢查模組，修復後已用smoke test驗證不影響既有字串dtype呼叫者行為，之後任何軌只要看到這個函式莫名`TypeError`都不用再重新排查，已經修好了。**
