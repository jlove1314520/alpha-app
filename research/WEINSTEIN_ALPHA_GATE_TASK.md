# WEINSTEIN_ALPHA_GATE_TASK.md — `weinstein_stage2_unbiased` 解鎖 holdout 前的 alpha/beta 關卡

**2026-08-25 使用者直接指示（完整原話見 `MARATHON_STATE.md`「2026-08-25 使用者解除卡關指令」第1點）：**

> 先不要解鎖 holdout。在動 holdout 前，先在 train/val 做 alpha vs beta 分解——把策略報酬對大盤指數回歸，報告 alpha(截距)、beta、以及扣成本後有沒有贏買進持有。若 alpha 沒有明確為正且通過 Bonferroni，直接判否決(它就是 beta，這條故事我們早知道)，不要浪費一次性 holdout。只有確認是真 alpha 才回報給我，由我決定是否解鎖。

**這份文件是給接手這個工作單位的馬拉松輪次看的任務規格。跟平常「測一個新因子」性質不同——這是對一個已經 EXPERIMENTAL 的舊候選（`weinstein_stage2_unbiased`，見 `LEADS.md`）補做一個關卡，不是廣度優先掃因子家族，不用照 `MARATHON_PROTOCOL.md` 第3節找假說。**

---

## 做完這個任務的判定結果只有兩種，沒有模糊地帶

- **否決（most likely）**：alpha 不夠正、或沒通過 Bonferroni 顯著性關卡 → 在 `LEADS.md`／`STRATEGY_LOG.md` 記錄判定為「否決：純 beta，非真 alpha，不建議解鎖 holdout」，**不回報使用者要求解鎖**（誠實記錄結果即可，這本身不是需要使用者決策的事，是否決）。
- **通過**：alpha 明確為正且通過 Bonferroni → 在 `LEADS.md`／`MARATHON_STATE.md` 記錄「已通過 alpha/beta 關卡，等待使用者決定是否解鎖 holdout」，**這裡停手，不自己呼叫 `unlock_holdout_once()`**——`unlock_holdout_once()` 永遠只能由使用者明確指示才能呼叫，這條沒有例外，不管這輪的分析結果多漂亮。

---

## 怎麼做（建議步驟，不是強制唯一做法，做的人可以視實際情況調整，但判定標準不能鬆）

### 1. 拿到 train/val 的策略報酬序列

`strategies/run_weinstein_unbiased.py::main()` 已經有 train/val 兩期的完整回測（`train_result`／`val_result`，各自有 `.equity_curve`，欄位是 `date`/`equity`），跟同一份 `market_df`（TAIEX，`prepare_market_data()` 準備好的）。這些不用重新寫，直接 import 呼叫 `main()`（或把裡面 train/val 那兩段抽出來重用，避免重跑一次不必要的隨機控制組），拿到 `train_result.equity_curve`／`val_result.equity_curve`／`market_df`。

### 2. Alpha/beta 拆解（沿用既有工具，不要重寫）

`research/long_only_vs_market.py::decompose_alpha_beta(result, market_df)` 已經是現成的工具（第2輪 Cowork 覆核時為 `score_longonly_v1` 寫的，函式簽名是通用的：只要傳入一個有 `date`/`equity` 欄位的 DataFrame 就能用，不是 `score_longonly_v1` 專屬）。對 train 跟 val 各自呼叫一次，拿到：
- `beta`（CAPM迴歸的斜率）
- `alpha_ann_pct`（純alpha年化報酬）
- `alpha_total_return_pct`（純alpha累積報酬）
- `alpha_sortino`
- `alpha_mdd_pct`
- `beta_contribution_pct`（大盤貢獻部分，用來對照「總報酬 = beta貢獻 + alpha貢獻」）

### 3. 扣成本後有沒有贏買進持有

`run_weinstein_unbiased.py` 本身已經算了 `cost_1x`/`cost_2x`/`cost_3x`（validation期）跟 `bh_val`（同期TAIEX買進持有報酬）——直接沿用這幾個數字回報「1x/2x/3x成本下策略報酬 vs 買進持有」，不用另外重算。Train 期如果原本沒算成本敏感度，比照 val 期的做法補一份（`BacktestConfig(cost_multiplier=mult)` 重跑 train 期即可，跟 val 期用同一套機制）。

### 4. Alpha 顯著性檢定（**這是這個任務唯一需要新寫的部分**，其他都是重用既有工具）

單純看 alpha 的正負號不夠嚴謹——需要一個統計顯著性檢定，方法上要跟這個專案既有的「配對式隨機控制組」精神一致（不是換一套新方法論）：

1. `validation/control_group.py::run_matched_control_group()` 已經有「同進出場日期、只隨機打散選哪一檔股票」的機制（`extract_trade_schedule()` + 內部 `one_draw()`），但目前 `one_draw()` 只回傳最終淨值（一個純量），不是完整的每日淨值序列——**要能對每一次隨機抽樣的結果也做 alpha/beta 拆解，需要 `one_draw()`（或一個新的變體函式，不一定要改動原本的函式，可以寫一個平行的版本）能夠回傳完整的 `date`/`equity` 序列，不是只回傳最終值**。
2. 對 val 期（跟 train 期，如果時間允許）：用同一套隨機抽樣機制跑 N=200 次（沿用專案慣例的抽樣數），每一次隨機抽樣的完整淨值序列都送進 `decompose_alpha_beta()`，拿到這次隨機抽樣的 `alpha_total_return_pct`。
3. 把「真實策略的 alpha_total_return_pct」拿去跟這 200 次隨機抽樣的 alpha_total_return_pct 分布比較，算出 percentile（做法完全比照 `ControlGroupResult` 現有的 percentile 算法，只是比較的指標從「最終淨值」換成「alpha_total_return_pct」）。
4. **Bonferroni（累積校正）**：`bonferroni_n` = `TRIALS_LEDGER.md` 目前的總列數（跟平常因子/策略檢定用同一套規則，見 `MARATHON_PROTOCOL.md` 第2節），這個任務本身如果最後判定要不要進 `TRIALS_LEDGER.md` 加一列——**加**，因為這確實是一次新的統計檢定（alpha 顯著性），不是單純調查，要算進累積校正的分母，也要接受用當下的累積門檻檢驗。

### 5. 判定與記錄

- alpha percentile 沒過累積 Bonferroni 門檻 → **否決**，記錄進 `LEADS.md`（更新 `weinstein_stage2_unbiased` 那一列，判定改為「否決：純 beta，非真 alpha，見 `WEINSTEIN_ALPHA_GATE_TASK.md` 結果」）、`TRIALS_LEDGER.md` 加一列（FAIL）、`STRATEGY_LOG.md` 補一條完整記錄。**不要**去動 `MARATHON_STATE.md` 的 Holdout 狀態段落宣稱「等使用者」——否決了就是否決，不是懸而未決。
- alpha percentile 過門檻 → 記錄「已通過關卡，等待使用者決定是否解鎖」，`TRIALS_LEDGER.md` 加一列（PASS），`MARATHON_STATE.md` 的 Holdout 狀態段落更新成「候選已通過alpha/beta關卡，等待使用者回覆是否解鎖」（明確、具體，不要含糊）。**這裡結束，不要自己呼叫 `unlock_holdout_once()`。**

---

## 安全提醒（跟平常一樣，這裡不因為是特殊任務就放寬）

- 全程不得呼叫 `load_full_history()` 或 `unlock_holdout_once()`。
- 每一步收工前確認 `is_holdout_consumed()` 仍是 `False`。
- 這個任務可能需要不只一輪才能做完（先寫`one_draw()`能回傳完整淨值序列的擴充版本可能就要花掉大半輪時間預算），**分階段做，每輪結束前照常留心跳、commit 已完成的部分，不用一輪內硬做完**。
