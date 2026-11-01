# 「未分軌」試驗盤點（先.一三五-1gt）

DevQueue 20261101-120102，研究帽。**唯讀、零外部請求、沒改 `selection_bias_ledger.py`、沒改帳本、沒登記新試驗、沒碰 holdout。**

## 1. 結論（白話）

`selection_bias_ledger.py` 只認第 3～5 欄寫著 `TW`／`US`／`FUT` 的列，其餘退路只看 `fut_` 開頭與「美股」字樣。
目前有 98 列落在「未分軌」（扣掉 4 列事前登記合併後計入 N 94 筆）。逐列看名稱與說明欄後：

| 判讀 | 列數 | 說明 |
|---|---:|---|
| TW | 88 | 第 3 欄 `hypothesis_queue` 的 85 列、標「跨市場」但實際只交易台股的 #429／#430、`calibration` 的 #98 |
| 真跨市場 | 8 | #415／#416、#419／#420、#424／#426、#427／#428（同時持有台股與美股槓桿腿，或同一規則逐市場套用） |
| US | 1 | #324（#75 美股內部人交易 Form 4） |
| FUT | 1 | #127（賣出台指選擇權收波動度溢酬，交易標的是期交所衍生品） |
| 判不出 | 0 | — |

**[自行裁量] 判讀口徑＝「交易／預測標的在哪個市場」**，不是「訊號資料從哪來」：
例如 VIX9D/VIX、HYG/IEF、FRED 利差、銅金比當 TAIEX 降曝險訊號的試驗，訊號是美國資料，但下注對象是台股，判 TW。
TXO 偏斜／PCR 當 TAIEX 報酬預測訊號（#239／#241）判 TW；只有真的交易選擇權的 #127 判 FUT（FUT 軌已有 TXO 鐵蝶 #455 先例）。

可明確判軌的有 98 列（≥1），依交辦分支 → 寫提案送 `research/AWAITING_REVIEW.md`，**腳本不先改**。

## 2. 照判讀改分軌後的前後對照（exec 兩版 `parse()`，輸出寫到 repo 外暫存檔）

全體 N＝459 不變（分軌只是重新分配分母，不改總數）。門檻＝Bonferroni 所需百分位；E[max SR] 沿用 ledger 的示意假設（試驗間 SR 標準差 0.5）。

| 軌 | 改前 N | 改前門檻 | 改前 E[max SR] | 改後 N | 改後門檻 | 改後 E[max SR] |
|---|---:|---:|---:|---:|---:|---:|
| TW | 236 | 99.9788 | 1.410 | **323** | 99.9845 | 1.459 |
| US | 77 | 99.9351 | 1.219 | 78 | 99.9359 | 1.221 |
| FUT | 52 | 99.9038 | 1.146 | 53 | 99.9057 | 1.149 |
| 未分軌 | 94 | 99.9468 | 1.254 | — | — | — |
| 跨市場（甲案，自成一軌） | — | — | — | 5 | **99.0000** | 0.596 |
| 跨市場（乙案，同時計入 TW 與 US） | — | — | — | TW 328／US 83 | 99.9848／99.9398 | 1.462／1.232 |

（跨市場 8 列計入 5 筆：#415／#419／#424 被結果列合併；#427 沒被合併，見第 4 節附帶發現。TW 88 列計入 87 筆：#429 併入 #430。）

**「撐住／倒下」清單前後完全相同**：
- 全體口徑（ledger 現行判定用的口徑）：宣稱做過校正 11 筆，撐住 3、倒下 4（#8、#13、#14、#15），改前改後一樣——全體 N 沒變。
- 分軌口徑（另算）：7 筆有百分位的通過列都在 TW 軌；#2／#7／#9（100 百分位）在 236 與 323 下都撐住，#8／#13／#14／#15 在兩者下都倒下。**沒有任何一筆由撐住變倒下。**
- 跨軌重複因子：改前改後都只有 `low_vol`（TW、US）1 個。
- 本次改判的 98 列裡，PASS／CHEAP_PASS／EXPERIMENTAL 的列都沒有留下「N 百分位」統計量，不進分母自查，不影響任何既有判定。

## 3. 提案（送 AWAITING_REVIEW，照零之二 24 小時預設放行）

- **甲**：`parse()` 加一條退路——第 3 欄是 `hypothesis_queue`／`calibration` 的列判 TW；「跨市場」維持一軌。缺點：跨市場軌 N=5、門檻只要 99.0 百分位，比任何單一市場軌都鬆得多，等於讓跨市場試驗享受最寬的門檻。
- **乙（建議）**：同甲的 TW 退路，另外 `hypothesis_queue` 列裡實為美股／期貨的用明確編號表（#324→US、#127→FUT，比照 `KNOWN_DUPLICATE_IDS` 的寫法）；「跨市場」列**同時計入 TW 與 US 兩軌分母**（TW 328、US 83），全體 N 不重複計。理由：跨市場試驗同時佔用兩個市場的搜尋名額，算進兩邊才是保守方向；甲案的 99.0 門檻方向錯誤（變鬆）。
- **丙**：維持現狀，只在 `SELECTION_BIAS_LEDGER.md` 加註「未分軌 94 筆多數是台股」。缺點：TW 門檻持續低估（99.9788 vs 應有 99.9845～99.9848）。

影響：只動分軌門檻（TW 變嚴），全體門檻與現行撐住／倒下判定不變；歷史判定一律不改，只記錄。
`selection_bias_ledger.py` 不是十三節核心檔，核准後 DevQueue 可直接改，改完重跑 ledger、確認第 2 節數字與本報告一致。

## 4. 附帶發現（只記錄，未改）

1. **#94 編號在帳本出現兩次**（第 3 欄一列 `TW`、一列 `hypothesis_queue`），`parse()` 兩列都計入；#149 也有同樣情形（FUT 軌）。是否為重複登記待另查（`trial_registry.py` append-only，不得回頭改列）。
2. **#427 沒有被 `merged_prereg_pairs()` 合併**：結果列 #428 寫的是「預登記 #427」，合併正則只認「事前登記 #N」。若比照其他事前登記合併，全體 N 會是 458、跨市場軌 4。
3. 第 1 節口徑是自行裁量；若總司令認為「訊號來源市場」也該算（例如美國總經訊號 → 台股），那約 15 列（#124／#125／#126／#168／#169／#327／#329／#330／#347／#363／#365／#366／#374／#429／#430）會變成跨市場，應另案討論。

### 4.1 附帶發現 1 追查結果（先.一三五-1gw，DevQueue 20261101-170101，唯讀、零請求）

全帳本重掃（`selection_bias_ledger.parse()`）：491 列、最大編號 #489、**1～489 無缺號**，重號只有 #94、#149 兩組（各 2 列），沒有第三組。

| 編號 | 帳本行 | 第 3 欄 | 內容 | 原始寫入 commit | 判讀 |
|---|---|---|---|---|---|
| #94 | 596 | TW | `piotroski_fscore_gate_v1`（#23 F-score 排雷閘門，FAIL） | `53324bfc3b` 2026-09-03 05:57「hypothesis_queue #23 … 結案（FAIL）」 | **① 同一次試驗重複登記** |
| #94 | 635 | hypothesis_queue | 「#23 Piotroski F-score當價值榜排雷閘門（核心比較）」，同一支腳本、同一組數字（TRAIN alpha +6.26%→+7.92%、VAL +12.38%→+5.24%、交易數 718→98） | `ef14642642` 2026-09-03 06:30（33 分鐘後，「#24 結案…修正#23狀態順序」順手再寫一列） | 同上，**後寫的這列是重複** |
| #149 | 594 | FUT | `fut_oi_price_confirm_graded_5d`（OI 濾網分級，FAIL percentile=24.5） | `e52399a60a` 2026-09-06 02:37 馬拉松第385輪（FUT 軌） | **② 兩次不同試驗撞號** |
| #149 | 707 | TW | #39 0050 成分股調整事件效應（資料不可及 FAIL） | `8fbb0183ae` 2026-09-06 05:32 hypothesis_queue | 同上 |

（`git blame` 兩組四列都指向 `26c5665c25` 2026-09-10「外部一改.4…修正總帳兩個計數bug」，那是整檔重寫；原始寫入者用 `git log -S` 查出如上。）

**撞號原因**：兩組都發生在 `research/trial_registry.py` 建立（`249a5fdad9`，2026-09-07）**之前**——當時各軌道手寫編號、各自讀帳本取最大值，FUT 軌與 hypothesis_queue 同一晚各自取到 149。09-07 之後編號一律由 `next_trial_id()`（帳本最大值＋1）推導，#150～#489 沒有再撞號，**不是 `trial_registry.py` 的編號 bug**。
附記（只記錄，不提案）：`register_trial()` 讀帳本→推導編號→寫入之間沒有跨行程鎖，兩個行程同一秒登記理論上仍可能撞號；目前背景只剩 DevQueue 一條、09-07 後 340 筆零撞號，風險低，暫不另開條目。

**對 N 的影響**：
- #149（②）：兩列是兩次獨立試驗，**N 計 2 筆本來就對**，結案、不改。
- #94（①）：同一個統計檢定被數兩次，全體 N 多 1、有效 N 也多 1。修法提案見 `PENDING_QUEUE.md` 先.一三五-1gw-a（送 AWAITING）。
  **注意**：不能直接把 94 加進 `KNOWN_DUPLICATE_IDS`——那個集合用編號比對，會把 #94 兩列**都**排除出有效 N（少算 1 變成多扣 1）。

## 5. 逐列判讀（98 列）

| # | 日期 | 第 3 欄 | 名稱（截 60 字） | 判定 | 判讀 | 依據 |
|---|---|---|---|---|---|---|
| 430 | 2026-10-10 | 跨市場 | r1_0050_credit_gate_result | PASS | **TW** | 0050 核心＋台股2倍腿；閘門訊號是美國信用利差，交易標的全在台股 |
| 429 | 2026-10-10 | 跨市場 | r1_0050_credit_gate_prereg | 未結案 | **TW** | 同 #430 的事前登記 |
| 428 | 2026-10-07 | 跨市場 | s3c6_oos_2025_result | EXPERIMENTAL | **跨市場** | 同時持有台股槓桿腿（00631L／合成2倍0050）與美股槓桿腿（00647L／合成2倍VTI換台幣）（S3-C6 樣本外） |
| 427 | 2026-10-07 | 跨市場 | s3c6_oos_2025_prereg | 未結案 | **跨市場** | 同時持有台股槓桿腿（00631L／合成2倍0050）與美股槓桿腿（00647L／合成2倍VTI換台幣）（S3-C6 樣本外事前登記） |
| 426 | 2026-10-07 | 跨市場 | crisis_gate_leveraged_bb90_result | PASS | **跨市場** | 同時持有台股槓桿腿（00631L／合成2倍0050）與美股槓桿腿（00647L／合成2倍VTI換台幣）（危機閘門×槓桿 Bb-90） |
| 424 | 2026-10-07 | 跨市場 | crisis_gate_leveraged_bb90_prereg | 未結案 | **跨市場** | 同時持有台股槓桿腿（00631L／合成2倍0050）與美股槓桿腿（00647L／合成2倍VTI換台幣） |
| 420 | 2026-10-06 | 跨市場 | leveraged_bb90_6grid_result | ABANDONED | **跨市場** | L_TW（00631L）與 L_US（00647L／VTI）六格 |
| 419 | 2026-10-06 | 跨市場 | leveraged_bb90_6grid_prereg | 未結案 | **跨市場** | 同 #420 的事前登記 |
| 416 | 2026-10-06 | 跨市場 | trend_scale_1_5x_0_5x_xmkt_result | FAIL | **跨市場** | PREREG_trend_scale_xmkt：同一規則套多個市場指數 ETF、逐市場比較（SPY 與 0050 列參考） |
| 415 | 2026-10-06 | 跨市場 | trend_scale_1_5x_0_5x_xmkt_prereg | 未結案 | **跨市場** | 同 #416 的事前登記 |
| 374 | 2026-09-23 | hypothesis_queue | regime_gate_nonoverlap_block_reverify_batch | FAIL | **TW** | #76／#78／常備.2～.5 以 TAIEX 為預測目標的 regime gate 重驗（訊號來源美國，交易標的台股） |
| 369 | 2026-09-23 | hypothesis_queue | monthly_revenue_sue_continuous_bucket_v1_volcheck | FAIL | **TW** | 月營收 SUE（台股月營收制度、產業×市值分桶） |
| 368 | 2026-09-23 | hypothesis_queue | monthly_revenue_sue_continuous_bucket_v1 | CHEAP_PASS | **TW** | 台股 300 檔快取宇宙 |
| 366 | 2026-09-23 | hypothesis_queue | PENDING_QUEUE.md 常備.5 HYG/IEF比值水位版其他窗口(M=5/10/60日) 當TAIEX re | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 365 | 2026-09-23 | hypothesis_queue | PENDING_QUEUE.md 常備.4 HYG/IEF比值N日變動率版代理信用利差 當TAIEX regime降曝險 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 363 | 2026-09-23 | hypothesis_queue | PENDING_QUEUE.md 常備.2 VIX9D/VIX期限結構比值N日變動率版 當TAIEX regime降曝險 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 362 | 2026-09-23 | hypothesis_queue | 台灣失業率YoY當TAIEX regime降曝險訊號（HYPOTHESIS_QUEUE.md #80，第1關cheap  | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 361 | 2026-09-23 | hypothesis_queue | 景氣對策信號綜合分數當TAIEX regime降曝險訊號（HYPOTHESIS_QUEUE.md #81，第1關chea | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 357 | 2026-09-23 | hypothesis_queue | 景氣對策信號綜合分數當TAIEX regime降曝險訊號（HYPOTHESIS_QUEUE.md #81，第1關chea | CHEAP_PASS | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 349 | 2026-09-23 | hypothesis_queue | regime_alt_a_etf_tax_recheck | FAIL | **TW** | regime.替代A：TAIEX 均線距離曝險調節（ETF 稅率重跑） |
| 348 | 2026-09-23 | hypothesis_queue | option_pcr_overlay_v1_etf_tax_recheck | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 347 | 2026-09-23 | hypothesis_queue | copper_gold_ratio_overlay_v1_etf_tax_recheck | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 345 | 2026-09-23 | hypothesis_queue | dgbas_unemployment_yoy_gate1 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 330 | 2026-09-22 | hypothesis_queue | HYPOTHESIS_QUEUE.md #78 HYG/IEF比值代理信用利差當TAIEX regime降曝險訊號 第1 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 329 | 2026-09-22 | hypothesis_queue | HYPOTHESIS_QUEUE.md #77 美國高收益債利差(BAMLH0A0HYM2)資料可行性查證 | FAIL | **TW** | #77 美國 HY 利差當 TAIEX regime 訊號的資料查證（交易標的台股） |
| 327 | 2026-09-22 | hypothesis_queue | #76 VIX9D/VIX期限結構比值 當TAIEX regime降曝險訊號 第1關cheap gate | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 324 | 2026-09-22 | hypothesis_queue | #75 2018+子樣本 第1關cheap IC gate (net_usd/n_buyers vs fwd20) | FAIL | **US** | #75 美股內部人交易（SEC EDGAR Form 4，net_usd／n_buyers），HYPOTHESIS_QUEUE.md 第 11311 行 |
| 321 | 2026-09-22 | hypothesis_queue | 原子.六 出借總量(TWSE TWT72U)depth-1 IC地圖（14表達式×2horizon=28測試） | FAIL | **TW** | 台股官方資料（TWSE） |
| 263 | 2026-09-19 | hypothesis_queue | 減資事件CAR·彌補虧損減資組(#71) | FAIL | **TW** | 台股上市櫃事件 |
| 262 | 2026-09-19 | hypothesis_queue | 減資事件CAR·現金減資組(#71) | FAIL | **TW** | 台股上市櫃事件 |
| 261 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=260 k=0.65 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 260 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=260 k=0.5 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 259 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=260 k=0.35 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 258 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=200 k=0.65 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 257 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=200 k=0.5（主規格） | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 256 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=200 k=0.35 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 255 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=140 k=0.65 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 254 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=140 k=0.5 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 253 | 2026-09-19 | hypothesis_queue | regime.替代A 網格 MA=140 k=0.35 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 243 | 2026-09-15 | hypothesis_queue | regime擇時overlay#10協定第一個訊號：TAIEX 200MA趨勢濾網(binary曝險1.00/0.50) | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 242 | 2026-09-15 | hypothesis_queue | Cybex.引擎：進場/出場延遲確認+總開關重開冷卻期 套用於#53全市場報酬離散度速度 | FAIL | **TW** | #53 台股全市場報酬離散度＋Cybex 延遲引擎 |
| 241 | 2026-09-10 | hypothesis_queue | option_skew_cheap_gate #70 | FAIL | **TW** | #70 TXO 波動度偏斜當 TAIEX 報酬預測訊號（不是交易選擇權） |
| 239 | 2026-09-10 | hypothesis_queue | option_oi_pcr_gate69 | FAIL | **TW** | 說明寫台股 |
| 233 | 2026-09-10 | hypothesis_queue | short_margin_ratio_gate68 第1關cheap IC gate（`HYPOTHESIS_QUEUE | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 232 | 2026-09-10 | hypothesis_queue | #67盤中零股交易比重(Odd-Lot Imbalance) portfolio層構造 gate2 | FAIL | **TW** | #67 盤中零股委託簿失衡（TWSE TWTC7U） |
| 231 | 2026-09-09 | hypothesis_queue | f_odd_lot_imbalance (#67 盤中零股委託簿失衡度，第1關cheap gate) | CHEAP_PASS | **TW** | 台股 300 檔快取宇宙 |
| 229 | 2026-09-09 | hypothesis_queue | #65 產業龍頭股跨期領先-落後動能 factor_ic_leader_follower_lag gate1 | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 227 | 2026-09-09 | hypothesis_queue | #63 gate4成本敏感度 | FAIL | **TW** | #63 借券費率飆升（TWSE t13sa710）成本敏感度 |
| 226 | 2026-09-09 | hypothesis_queue | #63 借券費率異常飆升 gate2 參數高原檢定(Z_THRESH) | CHEAP_PASS | **TW** | #63 借券費率飆升參數高原 |
| 225 | 2026-09-09 | hypothesis_queue | `f_lending_fee_spike`（`HYPOTHESIS_QUEUE.md`#63，第1關cheap gate | CHEAP_PASS | **TW** | 台股官方資料（TWSE） |
| 221 | 2026-09-09 | hypothesis_queue | HYPOTHESIS_QUEUE.md #52事件反應速度 正式N=200全量CAR事件研究gate1（8大類×2控制組 | CHEAP_PASS | **TW** | 台股 FinMind 資料 |
| 212 | 2026-09-08 | hypothesis_queue | #59 最小變異數投資組合建構 GATE4 成本敏感度 | FAIL | **TW** | #59 最小變異數組合，159 檔台股存活者無偏宇宙 |
| 211 | 2026-09-08 | hypothesis_queue | #59 最小變異數投資組合建構 GATE_SEQUENCE第3關 參數密集高原 | 未結案 | **TW** | #59 同上，參數高原 |
| 210 | 2026-09-08 | hypothesis_queue | #59 最小變異數投資組合建構 GATE2隨機控制組 | 未結案 | **TW** | 台股 159 檔宇宙 |
| 201 | 2026-09-08 | hypothesis_queue | day_trading_ratio_dispersion_gate57_control | FAIL | **TW** | #57 台股全市場當沖比重離散度 |
| 198 | 2026-09-08 | hypothesis_queue | #55 三大法人買賣超截面離散度速度 Institutional Flow Dispersion Velocity | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 194 | 2026-09-08 | hypothesis_queue | #53 全市場報酬離散度速度 GATE_SEQUENCE第2關隨機控制組 | FAIL | **TW** | #53 台股全市場報酬離散度 |
| 192 | 2026-09-07 | hypothesis_queue | #53全市場報酬離散度速度(Cross-Sectional Return Dispersion Velocity) 第1 | 未結案 | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 190 | 2026-09-07 | hypothesis_queue | cb_conversion_price_reset_gate1 | FAIL | **TW** | 台股 MOPS 公告 |
| 187 | 2026-09-07 | hypothesis_queue | HYPOTHESIS_QUEUE.md #51子事件2（現金增資折價）事件條件式CAR第1關cheap gate | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 97 | 2026-09-03 | hypothesis_queue | `#26 全市場融資餘額成長率 Margin Debt Growth`（TWSE官方全市場歷史數字，槓桿/擁擠度regi | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 92 | 2026-09-03 | hypothesis_queue | `#22 品質×營收加速×法人吸籌×低波動複合訊號`（合取AND） | FAIL | **TW** | #22 品質×營收加速×法人吸籌（台股月營收／三大法人） |
| 93 | 2026-09-03 | hypothesis_queue | `#23 Piotroski F-score當價值榜排雷閘門` | PASS | **TW** | #23 Piotroski F-score 當台股價值榜（value_board_v2）排雷閘門 |
| 94 | 2026-09-03 | TW | `piotroski_fscore_gate_v1`（HYPOTHESIS_QUEUE.md#23「Piotroski  | FAIL | **TW** | 同 #23；注意 #94 編號在帳本出現兩次（另一列第 3 欄已是 TW） |
| 95 | 2026-09-03 | hypothesis_queue | `#24 除權息季節行為效應`（台股7-9月旺季填息/棄息行為，稅制驅動） | FAIL | **TW** | 說明寫台股 |
| 98 | 2026-09-04 | calibration | `calibration_probe_momentum_12_1`（管線校準探針：橫截面12-1動能當已知訊號bench | FAIL | **TW** | 校準探針：台股橫截面 12-1 動能（備註另提 US／FUT 只是同批改標的其他編號） |
| 103 | 2026-09-04 | hypothesis_queue | `#28 市場廣度背離Breadth Divergence`（TAIEX 20日動量為正但300檔樣本breadth_p | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 102 | 2026-09-04 | hypothesis_queue | `#27 多因子複合評分z-score blend baseline`（GP+value_pb+revenue_surp | FAIL | **TW** | #27 台股 f_* 因子池 composite |
| 105 | 2026-09-04 | hypothesis_queue | `#28 市場廣度背離Breadth Divergence`（第1關sanity PASS後，把divergence_f | FAIL | **TW** | #28 市場廣度背離（TAIEX＋300 檔樣本） |
| 107 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_sanity`（`HYPOTHESIS_QUEUE.md`#29「等權重 | PASS | **TW** | 台股 300 檔快取宇宙 |
| 108 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_control_v1`（`HYPOTHESIS_QUEUE.md`#29 | CHEAP_PASS | **TW** | 台股 159 檔宇宙 |
| 110 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_plateau_v1`（`HYPOTHESIS_QUEUE.md`#29 | PASS | **TW** | 台股 159 檔宇宙 |
| 111 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_costs_v1`（`HYPOTHESIS_QUEUE.md`#29「等 | 未結案 | **TW** | #29 等權再平衡，159 檔台股 |
| 112 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_leave_one_out_v1`（`HYPOTHESIS_QUEUE. | PASS | **TW** | 台股 159 檔宇宙 |
| 114 | 2026-09-04 | hypothesis_queue | `equal_weight_rebalance_gate6_yearly`（`HYPOTHESIS_QUEUE.md`# | FAIL | **TW** | 說明寫台股 |
| 122 | 2026-09-05 | hypothesis_queue | `option_pcr_overlay_v1`（HYPOTHESIS_QUEUE.md#31接續#121，PCR訊號轉具 | FAIL | **TW** | 說明寫台股 |
| 123 | 2026-09-05 | hypothesis_queue | `fx_twd_gate`（HYPOTHESIS_QUEUE.md#32美元兌台幣匯率當資金外流/市場壓力regime訊 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 124 | 2026-09-05 | hypothesis_queue | `fred_yield_curve_gate`（HYPOTHESIS_QUEUE.md#33美國公債殖利率曲線10Y-2 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 125 | 2026-09-05 | hypothesis_queue | 銅金比 Copper/Gold Ratio 當全球成長/風險偏好regime訊號（`HYPOTHESIS_QUEUE.m | CHEAP_PASS | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 126 | 2026-09-05 | hypothesis_queue | 銅金比 Copper/Gold Ratio overlay具體規則（`HYPOTHESIS_QUEUE.md`#34接續 | FAIL | **TW** | 說明寫台股 |
| 127 | 2026-09-05 | hypothesis_queue | 賣出台指選擇權波動度風險溢酬 VRP（`HYPOTHESIS_QUEUE.md`#35，第1關cheap gate：IV | FAIL | **FUT** | 賣出台指選擇權（TXO）收波動度風險溢酬，交易標的是期交所衍生品；FUT 軌已有 TXO 鐵蝶 #455 |
| 129 | 2026-09-05 | hypothesis_queue | `f_short_sale_utilization`個股融券使用率（`HYPOTHESIS_QUEUE.md` #36， | CHEAP_PASS | **TW** | 台股 FinMind 資料 |
| 133 | 2026-09-05 | hypothesis_queue | `short_sale_utilization_portfolio_v1`第2關隨機控制組（`HYPOTHESIS_QU | PASS | **TW** | #36 台股個股融券使用率 |
| 134 | 2026-09-05 | hypothesis_queue | `short_sale_utilization_gates`第3關參數密集高原（`HYPOTHESIS_QUEUE.md | PASS | **TW** | #36 同上 |
| 135 | 2026-09-05 | hypothesis_queue | `short_sale_utilization_gate5_loo`第5/6關leave-one-out+逐年一致性（` | PASS | **TW** | #36 同上 |
| 136 | 2026-09-05 | hypothesis_queue | `short_sale_utilization_gate9_regime_overlay`第9關下檔保護（`HYPOTH | PASS | **TW** | #36 同上 |
| 137 | 2026-09-05 | hypothesis_queue | `short_sale_utilization`整體最終alpha顯著性判定（`HYPOTHESIS_QUEUE.md` | FAIL | **TW** | #36 同上 |
| 148 | 2026-09-06 | hypothesis_queue | 大戶籌碼集中度/股東持股分級表（`HYPOTHESIS_QUEUE.md` #38，資料可行性查證） | FAIL | **TW** | 台股 FinMind 資料 |
| 150 | 2026-09-06 | hypothesis_queue | 庫藏股買回公告效應（`HYPOTHESIS_QUEUE.md` #40，管理層信心信號事件研究，上一輪完成MOPS資料回 | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 157 | 2026-09-06 | hypothesis_queue | 個股間平均成對相關係數 Average Pairwise Correlation（`HYPOTHESIS_QUEUE.m | FAIL | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
| 161 | 2026-09-06 | hypothesis_queue | 三大法人買賣超集中度 Institutional Buying Concentration（`HYPOTHESIS_QU | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 164 | 2026-09-06 | hypothesis_queue | 景氣對策信號NDC Business Cycle Composite Signal（`HYPOTHESIS_QUEUE. | FAIL | **TW** | #44 國發會景氣對策信號資料查證 |
| 168 | 2026-09-06 | hypothesis_queue | 存託憑證（ADR）溢價/折價收斂第1關cheap gate（`HYPOTHESIS_QUEUE.md` #45，接續`a | CHEAP_PASS | **TW** | #45 ADR 溢價→本地台股後續報酬 |
| 169 | 2026-09-06 | hypothesis_queue | 存託憑證（ADR）溢價/折價收斂——排除TSM對照重跑最終判定（`HYPOTHESIS_QUEUE.md` #45，接續 | FAIL | **TW** | #45 同上，排除 TSM |
| 175 | 2026-09-06 | hypothesis_queue | 新股上市長期弱勢 IPO Long-Run Underperformance（`HYPOTHESIS_QUEUE.md` | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 176 | 2026-09-06 | hypothesis_queue | 處置股解除後價格反轉 Post-Disposition-Stock Price Reversion（`HYPOTHESI | FAIL | **TW** | 台股官方資料（TWSE） |
| 178 | 2026-09-06 | hypothesis_queue | 董監事及大股東股權質押比例 Controlling Shareholder / Insider Share Pledge | FAIL | **TW** | 台股 300 檔快取宇宙 |
| 182 | 2026-09-07 | hypothesis_queue | 日內／隔夜報酬結構分解（`HYPOTHESIS_QUEUE.md` #49，接續round180第1關CHEAP_PAS | 未結案 | **TW** | 預測／交易標的為 TAIEX（0050 代理） |
