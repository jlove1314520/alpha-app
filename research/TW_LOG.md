# TW_LOG.md — 台股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面），但只記馬拉松（`MARATHON_PROTOCOL.md`）跑起來之後、台股軌的每一輪動作。馬拉松之前的台股研究記錄在 `REPORT.md`（不重複搬過來）。

**規則：** 每個馬拉松輪次結束前，把這輪做了什麼（測了哪個假說、便宜/深挖關卡結果、卡在哪裡、下一步）append 一條到這裡，不管有沒有找到新東西——「這輪測了3個都FAIL」也是有效記錄，不能跳過不寫。

---

## 2026-08-23T02:00:00+08:00 — 台股軌馬拉松初始化

檔案建立，尚未有實際挖礦輪次執行。第一輪建議工作見 `TW_MARATHON_STATE.md`。

## 2026-08-23 — 馬拉松第一輪：重測 f_value_pb/f_value_pe/f_quality_roe_stability 便宜關卡

**做了什麼**：新寫 `factor_ic_value_quality.py`（沿用 `factor_ic.py` 的 100 名標準樣本、SAMPLE_SEED=20260822，跟已快取的 `data/raw/` parquet），對三個因子跑打散對照便宜關卡，`bonferroni_n=3`（這輪批次大小）。

**結果**：
- `f_value_pb`：val_mean_ic=+0.0592，打散對照 99.9 百分位，過批次門檻(96.7)也過累積校正門檻(n=15時99.3)。
- `f_value_pe`：val_mean_ic=+0.0501，打散對照 96.7 百分位，剛好壓線過批次門檻(96.7)，但**未過**累積校正門檻(99.3)——照 `MARATHON_PROTOCOL.md` 第2節規則老實記錄降級，不進深挖清單。
- `f_quality_roe_stability`：val_mean_ic=+0.0721，打散對照 99.9 百分位，兩種門檻都過。

三個都是 train/val 同號，樣本使用率 80/100（20 檔因缺歷史資料或抓取錯誤被跳過，屬正常篩選）。

**判定**：`f_value_pb`、`f_quality_roe_stability` → `CHEAP_PASS`（待深挖）；`f_value_pe` → 批次過但累積校正後降級，暫緩。已寫進 `TRIALS_LEDGER.md` #13–#15、`TW_LEADS.md`。

**注意事項**：`f_value_pb`/`f_value_pe` 的 PIT 狀態仍未驗證（`factors.py` 檔案開頭已揭露這個已知缺口），深挖 `f_value_pb` 前必須先補這個驗證步驟，不能假設便宜關卡過了就代表資料乾淨。`f_quality_roe_stability` 用的是已驗證過的 PIT 機制，無此疑慮。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

**下一步**：見 `TW_LEADS.md`「目前狀態」章節——優先深挖 `f_quality_roe_stability`，`f_value_pb` 深挖前先做 PIT 驗證。

## 2026-08-23 — 馬拉松第二輪：深挖 f_quality_roe_stability（十分位多空組合）

**做了什麼**：新寫 `deep_dive_f_quality_roe_stability.py`，沿用 `factor_ic.py` 的同一組100名快取樣本（不打新API），對 `f_quality_roe_stability` 建立十分位多空組合（前10%多、後10%空、等權重、20日換倉，跟`long_short_backtest.py`評估`score.py`綜合分時同一套機制，只是換成單一因子排序，重用其`run_long_short`/`capm_beta`/`sortino_ratio`）。跑了 TRAIN(2015-01-01~2020-12-31) 跟 VAL(2021-01-01~2024-12-31) 兩期，每期各測 1x/2x/3x 滑價成本敏感度（`validation/costs.py`的`DEFAULT_SLIPPAGE_BPS`=5bps基準），每個組態都跑20次配對式隨機控制組（同節奏/同十分位大小，隨機選股，不是靜態買進持有）。

**樣本覆蓋**：80/100名可用（跟便宜關卡同批），其中55名有`f_quality_roe_stability`非空值，十分位大小k=8。

**結果**（詳細數字見 `data/deep_dive_f_quality_roe_stability.csv`）：
- **6個組態（2期×3成本倍率）全部贏過全部20次隨機抽樣**（percentile=100.0）——但只抽20次，解析度只到95%/100%這種粗顆粒度，無法精細確認是否真的站穩n=16累積校正門檻(99.4)。
- **beta兩期都接近零**（TRAIN +0.083、VAL -0.080）：market-neutral構造有成立，不是隱藏的大盤方向性賭注。
- **淨成本後絕對年化報酬 train/val 正負號不一致**：TRAIN期為負（-3.77%~-4.17%，隨成本倍率遞增而更負），VAL期為正（+13.42%~+13.18%，隨成本倍率遞增而略降）。這跟便宜關卡的IC同號結果不同——IC測的是排序相關性方向，十分位價差測的是實際換倉後的絕對報酬，兩者不必然一致。
- **反常現象**：TRAIN期的隨機控制組本身也大虧（20次終值中位數0.31，即-69%），比真實策略虧得更慘（真實策略TRAIN期終值約0.80，即-20%）。這代表在55名有效樣本、10%十分位、20日換倉的構造下，每次換倉幾乎等於完全換手（因為候選池小），週轉成本drag非常大，可能是TRAIN期絕對報酬為負的主因，不必然是因子本身方向錯誤——但這個推論還沒有進一步拆解驗證，誠實列為待查。

**判定**：`EXPERIMENTAL`（不是乾淨PASS）。理由：統計上穩健打贏隨機控制組（兩期都是），且market-neutral構造成立，這兩點是正面訊號；但(a)絕對報酬train/val正負號不一致、(b)隨機抽樣次數只有20次、解析度不足以精細比對校正門檻，這兩個限制都是誠實揭露、不能忽略的缺口，所以不能直接判PASS。經濟解釋（ROE穩定度反映獲利品質、Novy-Marx品質因子文獻）能說明因子本身「為什麼可能有效」，但**不能解釋TRAIN/VAL報酬正負號為何不同**（如果是防禦性品質因子敘事，理應在波動大的TRAIN期更占優，而不是相反），這點誠實標註為未解之處。

**下一步建議**（已寫進`TW_LEADS.md`）：(1) 把`N_RANDOM_DRAWS`從20提高（比照`factor_ic.py`當初200→1000的做法）取得更精細的百分位解析度；(2) 嘗試拉長換倉週期或縮小十分位比例，檢驗TRAIN期負報酬是否主要是週轉成本drag而非因子失效。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

## 2026-08-23 — 馬拉松第三輪：加密 f_quality_roe_stability 隨機控制組解析度

**做了什麼**：照 `TW_MARATHON_STATE.md` 下一步建議(a)，修改 `deep_dive_f_quality_roe_stability.py` 的 `N_RANDOM_DRAWS` 從20提高到100（比照`factor_ic.py`當初200→1000的精神，seed序列用加法`RANDOM_CONTROL_SEED+i`，所以前20次抽樣結果跟第二輪完全相同，只是新增21–100次），重跑同一組6個配置（TRAIN/VAL兩期×1x/2x/3x成本），未打新API（沿用第二輪同批快取樣本）。

**過程小插曲（誠實記錄）**：第一次用 `Bash` 前景執行加上570秒timeout，結果被自動移到背景執行（超過9.5分鐘還沒印出任何stdout，可能是Windows下pipe到`tail`造成緩衝，不是真的卡住）。中途一度擔心跑太久會拖到鎖檔25分鐘的陳舊門檻，用`taskkill`嘗試終止該行程，但當下行程其實已經自然執行完畢（`taskkill`回報「行程已經終止」），最終從輸出檔跟CSV檔的時間戳確認整個腳本確實跑完、輸出正確，沒有半途而廢的資料。全程約9.5分鐘完成，距離鎖檔取得時間約11.3分鐘，在25分鐘陳舊門檻內有餘裕。

**結果**（見`data/deep_dive_f_quality_roe_stability.csv`）：真實策略的終值/年化報酬/Sortino/beta/alpha六組數字跟第二輪完全相同（這些是決定性計算，不含隨機性，seed不變本來就該一樣）——TRAIN期年化報酬仍為負(-3.77%~-4.17%隨成本遞增)、VAL期仍為正(+13.18%~+13.42%)，beta仍近零(+0.083/-0.080)。唯一實質變化是隨機控制組：**100次抽樣，真實策略6組配置全部仍贏過全部100次**（`random_control_percentile`=100.0），對應p<0.01（1/101），比第二輪20次抽樣的p<0.05（1/21）更嚴格地站穩，且已經解決第二輪備註的「解析度不足，只到95%/100%粗顆粒度」限制。

**判定**：`f_quality_roe_stability` 維持`EXPERIMENTAL`（不變）。理由：第二輪的兩個限制中，「隨機抽樣解析度不足」這項已用本輪動作解決；但「TRAIN/VAL絕對報酬正負號不一致」這項完全沒被觸及，依然是未解之處，所以不能升級為PASS。已更新`TRIALS_LEDGER.md` #17（新增列，累積總數16→17）、`TW_LEADS.md` #3（更新原列，附加本輪結果）。

**下一步**：見`TW_LEADS.md`「下一輪建議」——優先拆解TRAIN期絕對報酬為負是否為週轉成本drag（拉長換倉週期/縮小十分位比例）；`f_value_pb`深挖前仍需先做PIT驗證。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰）。

## 2026-08-23 — 馬拉松第四輪：`f_value_pb`/`f_value_pe` PIT 前置驗證

**做了什麼**：照 `TW_MARATHON_STATE.md` 下一輪優先(b)，新寫 `verify_pit_value_pb.py`。方法：對 2330（單檔，2015-01-01~VAL_END=2024-12-31）合併 `TaiwanStockPrice`（收盤價）跟 `TaiwanStockPER`（PBR），回推 `implied_bvps = close / PBR`（PBR應該是「price / 每股淨值」，所以反推出的每股淨值理論上是階梯函數，只在FinMind真的更新trailing淨值那天才跳變，其餘時間只會因為PBR四捨五入到小數第二位而有雜訊）。用日對日變動百分比>0.8%當跳變偵測門檻，找出每季的跳變日，跟 `pit.quarterly_pit()` 算出的財報季末日／本專案假設的`pit_date`（季末+45天）比對天數差。

**結果**（完整見 `data/verify_pit_value_pb_2330.csv`）：40/42個季度（2015-01起，扣除價格資料涵蓋範圍外跟VAL_END邊界的2季）偵測到跳變日。跳變日距季末天數：**min=32、median=45、max=62，從未貼近0天**——如果FinMind在季末當天就把淨值更新進PBR（即0天落後），會是嚴重前瞻偏誤，本次沒有觀察到任何一季是這種情況。median剛好等於本專案`pit.py`原本假設的45天，也貼近台灣法規規定的季報45天內公告期限，指向FinMind的PBR更新時點是貼著「實際可能公告時間」在動，不是季末就先知道。跳變日距假設`pit_date`（季末+45天）的天數：min=-13、median=0、max=+17——中位數精準對齊假設值，但個別季度有正負13~17天的落差（有些公司提早公告、有些拖到季末後60天才被FinMind更新）。

**判定**：這不是假說檢定（沒有對隨機打散/控制組做統計比較），是資料源時序特性調查，不計入`TRIALS_LEDGER.md`累積試驗數，記在「已調查但不計入試驗數」表（同分點集中度調查的先例）。**PIT狀態從「完全未驗證」升級為「單檔（2330）抽測，無嚴重前瞻偏誤」**——不是「完全驗證」，只測了一檔股票，用的是間接跳變偵測法而非FinMind官方文件確認的更新時點邏輯，這個限制要在往後任何引用這個結論的地方誠實帶上。`f_value_pe`共用同一個`TaiwanStockPER`資料源，推論同樣結論適用，但沒有對PER單獨重跑同樣的跳變偵測，是推論延伸不是直接驗證。

**下一步**：`f_value_pb`深挖的PIT前置條件已滿足，可以在下一輪開始十分位多空深挖（方法比照`deep_dive_f_quality_roe_stability.py`的精神，不是照抄檔案），深挖結果要註明PIT驗證的單檔限定範圍。`f_quality_roe_stability`拆解TRAIN期負報酬的工作單位仍待進行。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪未觸碰，`VAL_END=2024-12-31`跟`load_dev()`的自動截斷機制正常運作——2024-12-31那季因為預期揭露日2025-02-14超過VAL_END而在資料裡看不到後續價格，導致該季正確地被跳過偵測，不是異常）。

## 2026-08-24 — 馬拉松第五輪：全市場宇宙回補（`backfill_universe.py --batch-size 300`）

**做了什麼**：照 `MARATHON_PROTOCOL.md` 第5b節，取鎖時發現上一把鎖是陳舊鎖（held by pid 110416, 30.0分鐘前, `marathon_lock.py acquire` 自動判定陳舊並接手）。TW軌是三軌中最久未更新的一軌（15:05 vs US 15:35 vs FUT 15:38），輪替規則指向TW；且回補覆蓋率（跑之前）僅199/3196＝6.2%，遠低於80%門檻，依協定本輪工作單位是跑回補而非測新因子。呼叫時額度顯然已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（背景執行，約93檔嘗試後撞到連續15次限流自動停止，符合設計，非異常）。

**結果**：本批嘗試93檔，新完成63檔，新跳過15檔（永久跳過，非限流失敗），因限流提前中止（`hit_rate_limit_wall=True`，符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，不是bug）。**累積覆蓋率：199→262/3196（6.2%→8.2%）**，累積永久跳過：42→57檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`（腳本本身會自動接續未完成的部分，不需要手動指定起點）。若下一次呼叫一開始就立刻被限流（距上次批次結束時間太短），該輪應改做其他不需要新資料的工作單位（深挖已有候選、系統化掃過因子家族清單），並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24 — 馬拉松第六輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖後比對三軌`最後更新`時間戳，TW（2026-08-24T00:10:00+08:00）明顯早於US（09:40）跟FUT（09:10），輪替規則指向TW；且回補覆蓋率（跑之前）為262/3196＝8.2%，遠低於80%門檻，依協定本輪工作單位是繼續跑回補。呼叫時額度顯然已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（腳本自動讀取`data/backfill_state.json`接續未完成的部分，不需要手動指定起點）。

**結果**：本批嘗試108檔，新完成74檔，新跳過18檔（永久跳過，非限流失敗），因限流提前中止（連續15次限流，符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，不是bug）。**累積覆蓋率：262→336/3196（8.2%→10.5%）**，累積永久跳過：57→75檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24 — 馬拉松第八輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖成功（無陳舊鎖），比對三軌「最後更新」時間戳，TW（2026-08-24T10:10:00+08:00）明顯早於US（20:35）跟FUT（20:05），輪替規則指向TW；且回補覆蓋率（跑之前）為336/3196＝10.5%，遠低於80%門檻，依協定本輪工作單位是繼續跑回補。呼叫時額度已恢復（沒有立刻被限流），跑了`python backfill_universe.py --batch-size 300`（腳本自動讀取`data/backfill_state.json`接續未完成的部分，不需要手動指定起點）。

**結果**：本批嘗試98檔（含批次內部先跑到50檔的中繼進度：新完成43／新跳過7），最終本批合計新完成72檔、新跳過11檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：336→408/3196（10.5%→12.8%）**，累積永久跳過：75→86檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T02:35:10+08:00 — 馬拉松第29輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 114240持有鎖90分鐘後被回收，明顯遠超過25分鐘陳舊門檻，代表第28輪之後的某一輪疑似完全沒跑完就異常中止，這輪之間沒有留下任何`TW_LOG.md`/`REPORT.md`記錄）。比對三軌「最後更新」時間戳，TW（2026-08-24T00:34:00+08:00）明顯早於US（22:05，08-24第十輪）跟FUT（21:35，08-24第九輪），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為569 done/122 skip，跟`TW_MARATHON_STATE.md`記錄的569/3196（17.8%）一致（這次沒有落差，代表第28輪確實乾淨結束、是介於第28輪跟本輪之間的某一輪異常中止），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試78檔（其中15檔為state已存在的重複資料，判斷邏輯已窮盡提前結束本批次；實際新處理63檔），新完成57檔，新跳過6檔（永久跳過，非限流失敗）。**累積覆蓋率：569→626/3196（17.8%→19.6%）**，累積永久跳過：122→128檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T00:34:00+08:00 — 馬拉松第28輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 103272持有鎖滿60分鐘後被回收，明顯遠超過25分鐘陳舊門檻，代表第26輪之後的某一輪疑似完全沒跑完就異常中止或崩潰，這輪之間沒有留下任何`TW_LOG.md`/`REPORT.md`記錄）。比對三軌「最後更新」時間戳，TW（2026-08-23T23:03:00+08:00）明顯早於FUT（21:35，但日期是08-24，所以FUT實際更晚）跟US（22:05，08-24），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為509 done/109 skip（=509/3196=15.9%，比TW_MARATHON_STATE.md記錄的480/3196=15.0%略高，推測是被跳過的那些輪次中有部分進度先落地但沒來得及更新state檔案），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試101檔，新完成60檔，新跳過13檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：509→569/3196（15.9%→17.8%）**，累積永久跳過：109→122檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡已有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-23T23:03:00+08:00 — 馬拉松第26輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 100308持有鎖30分鐘後被回收，對應第25輪「無輸出/行程疑似被中止」）。比對三軌「最後更新」時間戳，TW（21:05）早於FUT（21:35）跟US（22:05），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`已有449 done/95 skip（=449/3196=14.05%，比state檔案記錄的408/3196略高，推測是上一輪被中止前有部分進度先落地），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試51檔，新完成31檔，新跳過5檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：449→480/3196（14.1%→15.0%）**，累積永久跳過：95→100檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`或拆解`f_quality_roe_stability`TRAIN期負報酬成因）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T03:36:08+08:00 — 馬拉松第31輪（TW軌）：全市場宇宙回補接續（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表第30輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T02:35:10+08:00）早於FUT（03:01:00）跟US（22:05:00，明顯晚很多），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為626 done/128 skip（=626/3196=19.6%，跟`TW_MARATHON_STATE.md`記錄的626/3196一致，無落差，代表第29輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試104檔，新完成70檔，新跳過19檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：626→696/3196（19.6%→21.8%）**，累積永久跳過：128→147檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T05:35:57+08:00 — 馬拉松第34輪（TW軌）：全市場宇宙回補第九批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表第33輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T03:36:08+08:00）早於US（04:05:00）跟FUT（05:03:32），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為696 done（跟`TW_MARATHON_STATE.md`記錄的696/3196一致，無落差，代表第31輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試120檔，新完成75檔，新跳過21檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：696→771/3196（21.8%→24.1%）**，累積永久跳過：147→168檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有第25輪疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T07:06:36+08:00 — 馬拉松第37輪（TW軌）：全市場宇宙回補第十批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時第一次嘗試就成功（乾淨`LOCK_ACQUIRED`，非`LOCK_STALE`，代表上一輪正常結束）。比對三軌「最後更新」時間戳，TW（`TW_MARATHON_STATE.md`，2026-08-24T05:35:57+08:00）早於US（06:02:00）跟FUT（06:32:00），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為771 done/168 skip（跟`TW_MARATHON_STATE.md`記錄的771/3196一致，無落差，代表第34輪本身乾淨結束），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔，新完成75檔，新跳過12檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：771→846/3196（24.1%→26.5%）**，累積永久跳過：168→180檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-24T22:01:00+08:00 — 馬拉松第40輪（TW軌）：全市場宇宙回補第十一批（`backfill_universe.py --batch-size 300`）

**做了什麼**：取鎖時偵測到`LOCK_STALE`（pid 116400持有鎖45.2分鐘，上一輪疑似異常中止，未留下正常結束的log）。比對三軌「最後更新」時間戳，TW（07:06:36）早於US（07:31:16）跟FUT（21:19:00），輪替規則指向TW；本輪開始前實測`data/backfill_state.json`為846 done/180 skip（跟`TW_MARATHON_STATE.md`記錄的846/3196一致，無落差，代表第37輪本身乾淨結束，卡住的是介於第37輪跟本輪之間某個未留記錄的輪次），仍遠低於80%門檻，依協定跑`python backfill_universe.py --batch-size 300`。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試100檔，新完成72檔，新跳過13檔（永久跳過，非限流失敗），因連續15次限流提前中止（符合`MAX_CONSECUTIVE_RATE_LIMITS=15`設計，非bug）。**累積覆蓋率：846→918/3196（26.5%→28.7%）**，累積永久跳過：180→193檔。

**判定**：這是基礎建設/資料落地工作單位，不是假說檢定，不計入`TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑`backfill_universe.py --batch-size 300`。若下一次呼叫一開始就立刻被限流，該輪應改做其他不需要新資料的工作單位（深挖`f_value_pb`——repo裡仍有疑似留下的未提交`deep_dive_f_value_pb.py`，下一輪接手時要先讀過、實際跑一次驗證輸出合理再沿用，不要假設它是對的；或拆解`f_quality_roe_stability`TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`adjusted_price_series()`/`load_dev()`，未觸碰holdout解鎖函式）。

## 2026-08-25 — 馬拉松第43輪：全市場宇宙回補第十二批

**做了什麼**：取鎖時偵測到 `LOCK_STALE`（上一輪 pid 100692 持有鎖滿300.1分鐘後被回收，第42輪期貨軌之後某一輪疑似完全沒跑完就異常中止，未留下任何log）。開始前 `data/backfill_state.json` 為918 done/193 skip，跟 `TW_MARATHON_STATE.md` 第40輪記錄一致（無資料落差，代表第40輪本身乾淨結束）。跑 `backfill_universe.py --batch-size 300`（自動接續）。

**結果**：本批嘗試109檔，新完成74/新跳過20，連續15次限流後判斷額度已用盡、提前停止（設計內行為）。累積覆蓋率 918→992/3196（28.7%→31.0%），累積永久跳過 193→213。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T05:37:00+08:00 — 馬拉松第46輪：全市場宇宙回補第十三批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T05:37:00）早於US（2026-08-25T06:04:00）跟FUT（2026-08-25T06:35:00），輪替規則指向TW。開始前 `data/backfill_state.json` 為1070 done/222 skip，跟 `TW_MARATHON_STATE.md` 第46輪記錄一致（無資料落差，代表第46輪本身乾淨結束）。覆蓋率仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試130檔（前100/後30兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計）。新完成78/新跳過21。**累積覆蓋率：1070→1148/3196（33.5%→35.9%）**，累積永久跳過：222→243檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25 — 馬拉松第52輪：全市場宇宙回補第十五批

**做了什麼**：取鎖時偵測到`LOCK_STALE`（上一輪pid 128940持有鎖滿30.0分鐘後被回收，第49輪之後某一輪疑似完全沒跑完就異常中止，未留下任何log）。比對三軌「最後更新」時間戳，TW（2026-08-25T07:05:00）早於US（2026-08-25T08:02:55）跟FUT（2026-08-25T08:32:52），輪替規則指向TW。開始前 `data/backfill_state.json` 為1148 done/243 skip，跟 `TW_MARATHON_STATE.md` 第49輪記錄一致（無資料落差，代表第49輪本身乾淨結束；陳舊鎖檔對應的中止輪次沒有動到任何已落地資料）。覆蓋率仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔（前100/後9兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成73/新跳過21。**累積覆蓋率：1148→1221/3196（35.9%→38.2%）**，累積永久跳過：243→264檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻，下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

**上一輪異常提醒**：取鎖時偵測到`LOCK_STALE`（pid 128940，30.0分鐘），已在心跳記錄跟`TW_MARATHON_STATE.md`同步註明，供使用者留意「上一輪疑似失敗」這個訊號。

## 2026-08-25T10:31:00+08:00 — 馬拉松第55輪：全市場宇宙回補第十六批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T09:03:00）早於US（2026-08-25T09:33:32）跟FUT（2026-08-25T10:05:00），輪替規則指向TW。開始前 `data/backfill_state.json` 為1221 done/264 skip（共1485筆），跟 `TW_MARATHON_STATE.md` 第52輪記錄一致（無資料落差，代表第52輪本身乾淨結束）。覆蓋率38.2%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試117檔（前100/後17兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成74/新跳過22。**累積覆蓋率：1221→1295/3196（38.2%→40.5%）**，累積永久跳過：264→286檔。已用`backfill_state.json`實際筆數（1295 done/286 skip=1581筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（40.5%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。
