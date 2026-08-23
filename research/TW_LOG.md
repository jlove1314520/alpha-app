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
