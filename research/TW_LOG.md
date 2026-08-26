# TW_LOG.md — 台股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面），但只記馬拉松（`MARATHON_PROTOCOL.md`）跑起來之後、台股軌的每一輪動作。馬拉松之前的台股研究記錄在 `REPORT.md`（不重複搬過來）。

**規則：** 每個馬拉松輪次結束前，把這輪做了什麼（測了哪個假說、便宜/深挖關卡結果、卡在哪裡、下一步）append 一條到這裡，不管有沒有找到新東西——「這輪測了3個都FAIL」也是有效記錄，不能跳過不寫。

---

## 2026-08-25T21:05:35+08:00 — 馬拉松第76輪：全市場宇宙回補第二十三批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對（TW 19:35 / US 20:10 / FUT 20:36），TW最久沒更新，且覆蓋率54.5%仍低於80%門檻，優先跑`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1743 done/371 skip，跟第73輪記錄一致（無落差）。額度已恢復，未被立即限流。

**結果**：本批嘗試104檔（50→100→連續15次限流提前停止，設計內行為），新完成76/新跳過13。累積覆蓋率1743→1819/3196（54.5%→56.9%），累積永久跳過371→384。

**驗證**：`is_holdout_consumed()` 確認仍為 `False`。

**下一輪**：覆蓋率仍低於80%門檻，繼續跑`backfill_universe.py --batch-size 300`（除非一開始就被限流，改做候補工作單位，見`TW_MARATHON_STATE.md`）。

## 2026-08-25T12:04:29+08:00 — 馬拉松第58輪：全市場宇宙回補第十七批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。三軌時間戳比對（TW 10:31 / US 11:02 / FUT 11:33），TW最久沒更新，且覆蓋率40.5%仍遠低於80%門檻，優先跑`backfill_universe.py --batch-size 300`（自動接續）。開始前state檔案為1295 done/286 skip，跟第55輪記錄一致（無落差，代表第55輪本身乾淨結束）。

**結果**：本批嘗試103檔，新完成74/新跳過14，撞限流牆提前停止（設計內行為）。累積覆蓋率1295→1369/3196（40.5%→42.8%），累積永久跳過286→300。

**驗證**：`is_holdout_consumed()` 確認仍為 `False`。

**下一輪**：覆蓋率仍遠低於80%門檻，繼續跑`backfill_universe.py --batch-size 300`（除非一開始就被限流，改做候補工作單位，見`TW_MARATHON_STATE.md`）。

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

## 2026-08-25T13:34:50+08:00 — 馬拉松第61輪：全市場宇宙回補第十八批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T12:04:29）早於US（2026-08-25T12:32:41）跟FUT（2026-08-25T13:03:21），輪替規則指向TW。開始前 `data/backfill_state.json` 為1369 done/286 skip（共1655筆），跟 `TW_MARATHON_STATE.md` 第58輪記錄一致（無資料落差，代表第58輪本身乾淨結束）。覆蓋率42.8%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試103檔（前100/後3兩段輸出，後段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成70/新跳過18。**累積覆蓋率：1369→1439/3196（42.8%→45.0%）**，累積永久跳過：286→318檔。已用`backfill_state.json`實際筆數（1439 done/318 skip=1757筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（45.0%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T15:13:42+08:00 — 馬拉松第64輪：全市場宇宙回補第十九批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T13:34:50）早於US（2026-08-25T14:02:23）跟FUT（2026-08-25T14:32:52），輪替規則指向TW。開始前 `data/backfill_state.json` 為1439 done/318 skip（共1757筆），跟 `TW_MARATHON_STATE.md` 第61輪記錄一致（無資料落差，代表第61輪本身乾淨結束）。覆蓋率45.0%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試110檔（前50/前100/最終110三段輸出，最終段連續限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成77/新跳過13。**累積覆蓋率：1439→1516/3196（45.0%→47.4%）**，累積永久跳過：318→331檔。已用`backfill_state.json`實際筆數（1516 done/331 skip=1847筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（47.4%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T16:35:41+08:00 — 馬拉松第67輪：全市場宇宙回補第二十批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T15:13:42）早於US（2026-08-25T15:34:05）跟FUT（2026-08-25T16:04:29），輪替規則指向TW。開始前 `data/backfill_state.json` 為1516 done/331 skip（共1847筆），跟 `TW_MARATHON_STATE.md` 第64輪記錄一致（無資料落差，代表第64輪本身乾淨結束）。覆蓋率47.4%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試102檔（前50/前100/最終102三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成73/新跳過14。**累積覆蓋率：1516→1589/3196（47.4%→49.7%）**，累積永久跳過：331→345檔。已用`backfill_state.json`實際筆數（1589 done/345 skip=1934筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（49.7%，已過半），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T19:35:10+08:00 — 馬拉松第73輪：全市場宇宙回補第二十二批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T18:05:40）早於US（2026-08-25T18:33:29）跟FUT（2026-08-25T19:05:53），輪替規則指向TW。開始前 `data/backfill_state.json` 為1665 done/363 skip（共2028筆），跟 `TW_MARATHON_STATE.md` 第70輪記錄一致（無資料落差，代表第70輪本身乾淨結束）。覆蓋率52.1%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試130檔（前50/前100/最終130三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成78/新跳過8。**累積覆蓋率：1665→1743/3196（52.1%→54.5%）**，累積永久跳過：363→371檔。已用`backfill_state.json`實際筆數（1743 done/371 skip=2114筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（54.5%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-25T18:05:40+08:00 — 馬拉松第70輪：全市場宇宙回補第二十一批

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，無陳舊鎖檔）。比對三軌「最後更新」時間戳，TW（2026-08-25T16:35:41）早於US（2026-08-25T17:02:50）跟FUT（2026-08-25T17:34:50），輪替規則指向TW。開始前 `data/backfill_state.json` 為1589 done/345 skip（共1934筆），跟 `TW_MARATHON_STATE.md` 第67輪記錄一致（無資料落差，代表第67輪本身乾淨結束）。覆蓋率49.7%仍遠低於80%門檻，跑 `backfill_universe.py --batch-size 300`（自動接續）。呼叫時額度已恢復（沒有立刻被限流）。

**結果**：本批嘗試109檔（前50/前100/最終109三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成76/新跳過18。**累積覆蓋率：1589→1665/3196（49.7%→52.1%）**，累積永久跳過：345→363檔。已用`backfill_state.json`實際筆數（1665 done/363 skip=2028筆）覆核腳本輸出摘要，數字一致。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍遠低於80%門檻（52.1%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（深挖 `f_value_pb`——repo裡仍有疑似留下的未提交 `deep_dive_f_value_pb.py`，接手前先讀過、實際跑一次驗證輸出合理再沿用；或拆解 `f_quality_roe_stability` TRAIN期絕對報酬為負是否為週轉成本drag）並誠實記錄跳過原因。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T00:36:06+08:00 — 馬拉松第78輪：全市場宇宙回補第二十四批

**做了什麼**：取鎖時偵測到`LOCK_STALE`（pid 132048持有鎖30.1分鐘後被回收，代表第77輪（US軌）之後某一輪疑似異常中止、未留下任何log）。比對三軌「最後更新」時間戳，FUT（2026-08-25T20:36:09）最舊，但依`FUT_MARATHON_STATE.md`頂部使用者裁示（期貨軌效率最低22試驗0通過，最多佔整體輪次20%，選輪次時TW/US優先度更高），本輪不選FUT，改依次舊的TW（2026-08-25T21:05:35）。開始前覆蓋率56.9%（1819/3196）遠低於80%門檻，跑`backfill_universe.py --batch-size 300`（自動接續），呼叫時額度已恢復（未被立即限流）。

**結果**：本批嘗試137檔（前50/前100/最終137三段輸出，最終段連續15次限流判斷額度已用盡、提前停止，符合`MAX_CONSECUTIVE_RATE_LIMITS`設計，非bug）。新完成100/新跳過22。**累積覆蓋率：1819→1919/3196（56.9%→60.0%）**，累積永久跳過：384→406檔。

**判定**：基礎建設/資料落地工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。

**下一步**：覆蓋率仍低於80%門檻（60.0%），下一輪若輪到TW軌且額度已恢復，應繼續跑 `backfill_universe.py --batch-size 300`。若一開始就被限流，改做候補工作單位（見`TW_MARATHON_STATE.md`第14項——主線1情境條件式檢驗，`f_foreign_streak`/`f_rel_strength`/`f_quality_roe_stability`方向反轉三假說+4個已PASS因子的分群IC，產出`REGIME_CONDITIONS.md`；這是`METHODOLOGY_FIX_TASK.md`修正2，目前跟宇宙回補並列最高優先序）。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫 `backfill_universe.py` 內部的 `load_dev()`/`adjusted_price_series()` 路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T04:17:00+08:00 — 馬拉松第83輪：`f_rel_strength_regime_switch` 策略層深挖（FAIL）

**取鎖**：乾淨成功（`LOCK_ACQUIRED`），無需回填「上一輪疑似異常中止」的註記。三軌狀態檔時間戳比對：TW（2026-08-26，互動session寫的無精確時分）最舊，選TW軌。

**做了什麼**：讀`TW_MARATHON_STATE.md`第14項與主線`MARATHON_STATE.md`「2026-08-26使用者裁示」段落，發現主線1（情境條件式檢驗）跟主線2（組合策略）已在同日稍早的互動session全部完成，「下一輪建議接續」第一項點名`f_rel_strength`情境切換策略「要不要真的建regime-switching backtest驗證」。檢查發現repo裡已有互動session寫好但**從未執行過**的`regime_switch_f_rel_strength.py`（未commit，讀完全文確認安全：走`load_dev()`+`holdout.assert_no_holdout_leakage()`、零新FinMind呼叫、matched random control同樣走regime開關），判定這是本輪最適合的有界工作單位——執行它、驗證輸出、誠實記錄判定，不需要自己重寫回測邏輯。背景執行（timeout規劃1500秒，實際112秒完成，遠比預期快）。

**結果**：TRAIN(2015-2020)×1x/2x/3x成本全部負報酬(ann −6.82%~−9.22%)/負alpha(−4.66%~−7.11%)/負Sortino(−0.144~−0.233)，對配對式隨機控制組僅84.0~89.0百分位；VAL(2021-2024)只有1x成本微幅轉正(ann+0.50%/alpha+1.77%)，2x/3x轉負，對配對式隨機控制組93.0~94.0百分位——兩期六組全部未達其他TW候選（`f_quality_roe_stability`等）慣見的99~100百分位門檻。**判定FAIL**。

**判定**：策略層完整驗證失敗，不進候選清單。`REGIME_CONDITIONS.md`分群IC找到的動量崩潰/套利限制經濟解釋在因子排序能力(IC)層級是對的，但沒有轉化成扣成本後能打贏隨機選股的可交易邊際優勢——這是TRAIN期乾淨虧損、VAL期對成本極敏感的組合，不是「差一點點沒過」的邊緣案例。完整數字、經濟解釋、與`f_quality_roe_stability`同款模式的對照，見`TW_LEADS.md`#4、`TRIALS_LEDGER.md`#40。

**待辦**：主線`LEADS.md`裡`f_rel_strength_regime_switch`那一列目前仍是PENDING（該檔案因互動session其他未commit變更處於dirty狀態，本輪延續US#82/FUT#80對TW互動session變更的迴避慣例，刻意不動、不commit）——下一個處理主線`LEADS.md`commit的session（互動或馬拉松皆可）需要把該列同步更新成FAIL。本輪commit範圍嚴格限定：只有`regime_switch_f_rel_strength.py`（互動session寫的分析腳本本身，這輪驗證過安全且已產出結果，判定可以入庫）+ `TW_LEADS.md`/`TRIALS_LEDGER.md`/`TW_LOG.md`/`REPORT.md`/`MARATHON_STATE.md`（本輪自己的記錄與心跳），**不動** `DATA.md`/`LEADS.md`/`TW_MARATHON_STATE.md`/`adjust.py`/`backfill_universe.py`/`factors.py`/`generate_scores_v2.py`/`score_v2.py`/`scores.json`/`REGIME_CONDITIONS.md`/`backfill_t86.py`/`portfolio_backtest.py`/`realtime_asof.py`/`regime_conditions.py`/`twse_t86_client.py`/`yf_price_client.py`（互動session的其餘產出，涉及App正式評分/資料源架構等有風險項目，留給使用者自己審過再決定commit）。

**下一步**：見`TW_LEADS.md`「下一輪建議」段落——(1)深挖`f_value_pb`；(2)拆解`f_quality_roe_stability`TRAIN期絕對報酬為負的成因；(3)若時間允許，掃`MARATHON_PROTOCOL.md`第3節還沒碰過的因子家族。宇宙回補（主線3）已在互動session達80%門檻(81.3%)，不再是TW軌本輪強制優先項，但下一輪若碰到額度受限、其他工作單位卡住時仍可回頭補「price done但finrev缺」的405檔。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`load_dev()`/`assert_no_holdout_leakage()`路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T05:49:00+08:00 — 馬拉松第85輪：`f_value_pb` 深挖（1b），判定EXPERIMENTAL

**取鎖**：乾淨成功（`LOCK_ACQUIRED`），無需回填「上一輪疑似異常中止」的註記。三軌狀態檔時間戳比對：TW（`TW_MARATHON_STATE.md` mtime 2026-08-26 01:55，早於US的05:02跟FUT的02:05）最舊，選TW軌。

**做了什麼**：讀`TW_MARATHON_STATE.md`第14項候補清單第(a)項與`TW_LEADS.md`#1備註，確認`f_value_pb`便宜關卡已`CHEAP_PASS`、PIT前置驗證已完成（單檔2330跳變偵測，第四輪），下一步是深挖（1b）。repo裡有一份互動session留下、**從未執行過**的`deep_dive_f_value_pb.py`（2026-08-23 17:03），先完整讀過原始碼：方法完全比照`deep_dive_f_quality_roe_stability.py`的精神（十分位多空/配對式隨機控制組100次抽樣/TRAIN+VAL兩期/成本1x2x3x/CAPM beta），資料路徑走`load_dev()`+`holdout.assert_no_holdout_leakage()`，重用既有80/100快取樣本、零新FinMind呼叫，確認安全無holdout風險後執行。背景執行約耗時分鐘級（6組配置×100次隨機抽樣，跟ROE深挖第三輪同等工作量）。

**結果**：61/80名有`f_value_pb`值。**TRAIN(2015-2020)**×1x/2x/3x成本：ann_return −6.93%~−7.42%（全負）、alpha −3.11%~−3.62%（全負）、Sortino −0.168~−0.188（全負）、beta −0.109（近零，market-neutral構造成立）、對配對式隨機控制組percentile=88.0/96.0/97.0（1x未達其他候選慣見的99~100門檻，2x/3x較強）。**VAL(2021-2024)**×1x/2x/3x：ann_return +4.82%~+5.56%（全正）、alpha +8.58%~+9.35%（全正）、Sortino +0.326~+0.358（全正）、beta −0.080~−0.081（近零）、percentile=99.0/100.0/100.0（三組全數穩健通過）。

**判定：EXPERIMENTAL**（不是PASS，不是FAIL）——十分位多空組合在VAL期乾淨、穩健地贏過配對式隨機控制組（beta近零，market-neutral成立），但**TRAIN期絕對報酬/alpha/Sortino全部為負、VAL期全部為正，正負號不一致**，跟`f_quality_roe_stability`（#16/#17）完全同款的「IC/相對排序層級可能成立，絕對報酬層級train/val反轉」模式，是這個模式的第三個實例（第二個是`f_rel_strength_regime_switch`，見#40，但那個是策略層FAIL，不是EXPERIMENTAL——差別在於`f_rel_strength_regime_switch`兩期對隨機控制組都沒有穩健勝出，`f_value_pb`至少VAL期是乾淨的99~100百分位）。**誠實揭露這次證據比ROE深挖更弱**：ROE的6組全部是percentile=100.0，這次TRAIN 1x只有88.0（低於便宜關卡慣用的90門檻），代表TRAIN期的「贏過隨機」本身在最低成本情境下就不夠穩健，是隨著成本墊高才轉強（2x=96.0/3x=97.0），這個方向（成本越高越贏隨機）本身也需要留意，可能代表策略在TRAIN期虧損没有隨機控制組虧得多（因為隨機控制組換手率相近但選股方向錯，兩者一起虧、策略虧得較少），不是策略本身賺錢。

**經濟解釋（憲法要求）**：便宜的帳面淨值（負PBR因子）反映市場對困境/低成長公司的過度悲觀定價，日後基本面改善或估值回歸均值時獲得修正——這是文獻中經典的價值溢酬（value premium，Fama-French HML）。**TRAIN/VAL絕對報酬正負號不一致，本身可能有市場整體風格輪動的解釋**：2015-2020是全球（含台股電子/半導體成長股）成長股顯著跑贏價值股的市場環境，即使選到「最便宜」的一批股票，整體風格逆風下多空組合仍可能虧損（但比隨機選股虧得少或贏得更明確，尤其成本墊高後）；2021-2024則普遍記載有價值股回補輪動（升息環境不利長存續期成長股估值、疫後重啟交易偏好景氣循環/價值股），跟VAL期轉為乾淨正報酬的時間點吻合。**這是觀察到的市場regime模式，不是這輪驗證過的因果機制**，誠實標記為待驗證的解釋，不是確認的因果證據。

**判定不升格為PASS的理由**：train/val絕對報酬正負號不一致這條規則（沿用ROE深挖#16/#17的先例）沒有被這輪的經濟解釋豁免——即使有合理的市場regime故事，也還沒有像`REGIME_CONDITIONS.md`對`f_rel_strength`那樣做過完整的事前可觀測條件分群驗證（大盤位階/波動度/市值/流動性四組），不能只憑「這個故事聽起來合理」就直接升格。**下一步（如果要繼續）**：仿照`regime_conditions.py`對`f_value_pb`也做一次分群IC，看TRAIN/VAL絕對報酬的反轉能不能被「大盤位階（成長/價值風格輪動的代理）」這組條件系統性解釋；如果能，比照`f_rel_strength`升格「情境切換策略候選」流程；如果不能，就跟`f_quality_roe_stability`一樣維持EXPERIMENTAL、不繼續往下挖。

**待辦**：`TW_LEADS.md`#1（`f_value_pb`列）需要更新這輪深挖結果與判定，這輪一併完成（見該檔案本輪更新）。`TRIALS_LEDGER.md`新增#42。**本輪commit範圍嚴格限定**：只有`deep_dive_f_value_pb.py`（互動session寫的分析腳本本身，這輪驗證過安全且已產出結果，判定可以入庫）+ `TW_LEADS.md`/`TRIALS_LEDGER.md`/`TW_LOG.md`/`REPORT.md`/`MARATHON_STATE.md`（本輪自己的記錄與心跳），**不動** `DATA.md`/`LEADS.md`/`TW_MARATHON_STATE.md`/`adjust.py`/`backfill_universe.py`/`factors.py`/`generate_scores_v2.py`/`score_v2.py`/`scores.json`/`REGIME_CONDITIONS.md`/`backfill_t86.py`/`portfolio_backtest.py`/`realtime_asof.py`/`regime_conditions.py`/`twse_t86_client.py`/`yf_price_client.py`（互動session的其餘產出，延續前幾輪US#82/#84、FUT#80、TW#83對這批dirty檔案的迴避慣例，留給使用者自己審過再決定commit）。`.github/workflows/`（untracked）同樣不動，跟本輪工作無關。

**下一步**：(1) 若要繼續深挖`f_value_pb`，考慮補一次分群IC（見上方判定段落）；(2) 拆解`f_quality_roe_stability`TRAIN期絕對報酬為負的成因（候補清單既有項目，這輪未做）；(3) 若時間允許，掃`MARATHON_PROTOCOL.md`第3節還沒碰過的因子家族（短期反轉/BAB/Amihud流動性/季節性/資產成長異常/Piotroski F-score/accruals）。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只呼叫`load_dev()`/`assert_no_holdout_leakage()`路徑，未觸碰holdout解鎖函式）。

## 2026-08-26T09:35頃 — 馬拉松第92輪：接手陳舊鎖檔孤兒工作——補齊`f_short_reversal_1m`便宜關卡的文件記錄

**取鎖**：`LOCK_STALE`（pid 146212持有30.0分鐘後被回收，上一輪疑似異常中止）。三軌狀態檔時間戳：US（第91輪，09:04:37）跟FUT（第90輪，08:33:39）都已有明確馬拉松輪次時間戳，TW（`TW_MARATHON_STATE.md`只標「2026-08-26互動session」無精確時分，且輪替邏輯上TW已經多輪沒被排到）判斷仍是最久沒被馬拉松輪次本身碰過的一軌，選TW軌。

**發現**：`git status`顯示上一輪（pid 146212）已完成`f_short_reversal_1m`（短期反轉，21交易日自身累積報酬取負號，`MARATHON_PROTOCOL.md`第3節「動量變體/短期反轉」家族第一個測試）的1a便宜關卡測試——新寫`factor_ic_short_reversal.py`、`factors.py`加上該因子定義（`SHORT_REVERSAL_WINDOW=21`）、`TRIALS_LEDGER.md`已新增#46列——但**崩潰在完成前，`TW_LOG.md`完全沒有這筆記錄、`TW_LEADS.md`也還沒新增對應列（#46備註寫著見`TW_LEADS.md#5`，但檔案裡根本沒有#5列）**，是一份「數據已產出、判定已下、只差文件收尾」的孤兒工作，不是半成品程式碼。

**驗證**：重跑`python factor_ic_short_reversal.py`（docstring承諾零新API呼叫，沿用既有100名快取樣本）確認數字跟`TRIALS_LEDGER.md`#46完全一致：TRAIN(2015-2020) mean_ic=+0.0496 IR=+0.286（n=74期）；VAL(2021-2024) mean_ic=−0.0054 IR=−0.032 hit_rate=0.53（n=47期）；null percentile=23.1（單測門檻90.0，遠未過）；same_sign=False（train為正、val接近零轉負）。判定**FAIL**，程式輸出跟既有文件字面一致，不是重新詮釋，只是把上一輪確實做完的判定補上遺漏的文件記錄。

**做的事**：這輪本身沒有測新假說（`f_short_reversal_1m`本身的1a判定是上一輪的產出，這輪只驗證+補文件），本輪新增內容：(1) 這篇`TW_LOG.md`記錄；(2) `TW_LEADS.md`新增#5列（`f_short_reversal_1m`），把`TRIALS_LEDGER.md`#46的完整數字/經濟解釋轉貼過去，符合`TW_LEADS.md`一貫的候選登記簿格式。**`TRIALS_LEDGER.md`#46本身不重複新增**（上一輪已經加好，重跑只是驗證數字沒有錯，不產生新試驗）。

**經濟解釋**（延續上一輪已下的判定，未變）：短期反轉是文獻中跟中期動能方向相反但同樣有名的異常，這裡用自身絕對報酬（非相對大盤，跟`f_rel_strength`刻意區隔），val期IC幾乎為零而非清楚反轉，可能是80檔樣本規模不足以捕捉這種通常需要更細（週頻/日頻分層）資料才穩定顯現的效應。不建議直接視為「台股無短期反轉」定論，但目前證據不支持升格。

**本輪commit範圍**：`factor_ic_short_reversal.py`（新增，上一輪產出，已驗證安全可重複執行）+ `factors.py`（`f_short_reversal_1m`定義，上一輪產出）+ `TW_LOG.md`/`TW_LEADS.md`（本輪補齊文件）+ `TRIALS_LEDGER.md`（working copy裡#46這筆是上一輪產出但還沒commit過，這次一併帶上，不是重複新增）+ `REPORT.md`/`MARATHON_STATE.md`（本輪心跳）。**不動**`.github/workflows/quotes.yml`（working copy裡另一筆跟本輪工作無關的uncommitted變更，看起來是使用者要求的CI健壯性修正，跟TW因子研究無關，延續本協定一貫「只commit跟本輪工作直接相關檔案」的紀律，留給使用者自己審過決定）。

**下一步**：短期反轉家族（唯一測過的變體`f_short_reversal_1m`）已FAIL結案；`TW_MARATHON_STATE.md`第14項候補清單其餘項目（`f_value_pb`分群IC/`f_quality_roe_stability`TRAIN期成因拆解/`MARATHON_PROTOCOL.md`第3節繼續掃BAB/特異波動率/Amihud流動性/季節性/資產成長異常/Piotroski F-score/accruals）仍是下一輪可選項。

**Holdout 檢查**：`is_holdout_consumed()` = `False`（本輪只重跑`factor_ic_short_reversal.py`的`load_dev()`路徑，未觸碰holdout解鎖函式）。
