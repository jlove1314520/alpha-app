# RUNBOOK：真錢閘門（深讀五，2026-09-15建立）

> **目前狀態：規則與程式碼已備妥，旗標檔不存在，永遠不會啟用，未啟用。**
> 這份文件是**操作手冊**，不是啟用授權。CC 不會、也不得建立任何旗標檔或
> 執行任何送單動作。
>
> **移植聲明**：本文件結構移植自
> `C:\Users\user\cybex_knowledge_export\RUNBOOK_first_real_money.md`
> （Cybex 加密貨幣真錢上線手冊），依總司令 2026-09-07 授權的移植原則——
> **拿判斷方法，不拿參數**。Cybex 的 $1,500／$300／6筆等數字是在加密貨幣
> 市場上訂出來的，本文件完全不沿用那些數字；沿用的只有「四道獨立屏障＋
> 兩級kill＋30天只看執行品質」這個判斷結構本身。凡是本文件裡出現的具體
> 金額／標的白名單，一律標示「待總司令裁示」，不是我自己填的數字。

---

## 0. 為什麼要做這件事（以及為什麼現在還不能做）

裁示五原文（`PENDING_QUEUE.md`【Cybex 深讀補充裁示】）：「我們正走向群益
真錢」。但截至本文件建立時，`C:\alpha\CLAUDE.md`記錄的現況是：

- **群益／國泰台股目前沒有合適的下單API**（該文件「重要決策與原因」一節
  明載）。
- Shioaji（永豐）目前只有`research/shioaji_order_server.py`的**模擬環境**
  （`SIMULATION_MODE = True`寫死），從未送過真實測試單。
- 沒有任何一筆真實市場的成交價 vs 訊號價紀錄——跟 Cybex 當初建這道閘門的
  理由完全一樣：回測的滑價假設（`research/validation/costs.py`
  `DEFAULT_SLIPPAGE_BPS = 5.0`bp）從來沒有被真實市場檢驗過。

**因此本文件現在做的是「規則先立好」，不是「即將真錢上線」的訊號。**
等哪一家券商真的釋出可用的下單API（無論是永豐、群益、或其他），送單流程
接進來的第一步就是呼叫這裡定義的閘門，而不是繞過它直接下單。

---

## 1. 已經備妥的元件（2026-09-15，可查驗）

| 元件 | 位置 | 狀態 |
|---|---|---|
| 四道獨立屏障 + 兩級kill switch | `research/mainnet_gate.py` | ✅ 已實作，25項自我測試PASS |
| 執行品質證據紀錄（滑價/成交/對帳/停擺/kill演練） | `research/execution_logs.py` | ✅ 已實作，含雜湊鏈防竄改，自我測試含竄改偵測案例，全PASS |
| 30天執行品質五題計分卡 | `research/execution_quality_scorecard.py` | ✅ 已實作，自我測試PASS；**跑在真實資料上目前五題皆為`INSUFFICIENT_DATA`（誠實反映尚無真錢紀錄，非bug）** |
| 本手冊 | `research/RUNBOOK_first_real_money.md` | ✅ |

### 現行四道屏障（全部要通過才可能送真錢單，見`mainnet_gate.py`docstring完整說明）

1. **旗標檔`secrets/MAINNET_ENABLE`** —— 內容需逐字等於
   `i_understand_this_uses_real_money=yes`。**只有總司令能建立這個檔案**，
   任何自動化流程（含 CC 自己）都不得建立或修改。
2. **主網憑證設定檔`secrets/shioaji_mainnet_config.txt`** —— 檔名必須包含
   `mainnet`字樣（物理上跟`research/shioaji_order_server.py`讀的`.env`
   分開），且內容長度需通過防呆門檻（抓空檔／貼上失敗）。
3. **`mainnet_gate.DRY_RUN`寫死`True`** —— 改成`False`是一次**獨立的、
   只有總司令能下令的變更**，不接受任何參數或環境變數覆蓋。即使屏障
   1/2/4全部通過，`can_submit_real_order()`在`DRY_RUN=True`時永遠回傳
   `False`。
4. **白名單＋金額上限設定檔`secrets/mainnet_limits.json`** —— 需包含
   `account_whitelist`／`symbol_whitelist`（皆不可為空清單）／
   `total_capital_cap_twd`／`per_order_cap_twd`／`daily_order_count_cap`
   五個欄位。**這支程式碼刻意不寫死任何金額或標的**——那是總司令的風險
   決策，不是工程判斷；設定檔不存在或格式不對，一律 fail-closed（視為
   未通過）。

> **外加**：憑證只有在旗標檔存在且內容正確時才會被讀取內容
> （`load_mainnet_credentials()`），不是「讀了但忽略」——見`mainnet_gate.py`
> 模組docstring的順序保證說明。

---

## 2. Go / No-Go 檢查清單（**只有總司令能執行，且目前多數項目「不適用」**）

**每一項都必須是 ✅ 才可以進行下一步。任何一項打叉，就停下來，不要繞過。**
（比照Cybex，但截至本文件建立時，第2.1節多數項目「不適用」——因為根本
還沒有可用的下單API，這是誠實現況，不是待補的空白。）

### 2.1 前置條件（工程面）

- [ ] **不適用（阻塞）**：目前沒有任何券商釋出可用的台股下單API
      （群益／國泰皆無，Shioaji僅模擬環境）。這一項本身就是整份清單的
      最上位阻塞條件，其餘項目要等它解除才有意義。
- [ ] `python research/mainnet_gate.py --self-test` → 全部PASS
- [ ] `python research/execution_logs.py --self-test` → 全部PASS
- [ ] `python research/execution_quality_scorecard.py --self-test` → 全部PASS
- [ ] `node scripts/smoke_test.mjs` → 全部PASS

### 2.2 前置條件（帳戶面，**總司令親自確認，不可由程式代勞**）

- [ ] 已確認要用哪一家券商的哪一支API（永豐 Shioaji 正式環境／或其他）
- [ ] 該券商帳戶已開啟兩步驟驗證（若支援）
- [ ] API金鑰權限已依「最小必要」原則設定，且已理解其風險
- [ ] 已裁示：`secrets/mainnet_limits.json`裡的
      `total_capital_cap_twd`／`per_order_cap_twd`／
      `daily_order_count_cap`／白名單標的要填多少
- [ ] 已理解：這筆錢**可能全部虧掉**，而且那不算系統失敗

### 2.3 心理面（認真回答，不要跳過）

- [ ] 我清楚這次上線的目的是**買到真實執行資訊，不是賺錢**
- [ ] 我可以接受連續數週都是小額虧損而不去改參數
- [ ] 我不會因為前幾天賺錢就加碼超過`secrets/mainnet_limits.json`設定的上限

### 2.4 啟用步驟（全部由總司令手動執行，CC不執行）

1. 把主網憑證寫進`secrets/shioaji_mainnet_config.txt`（或未來實際使用
   的券商對應檔名，但檔名必須包含`mainnet`字樣）。
2. 建立`secrets/mainnet_limits.json`，填入裁示過的金額與白名單。
3. 建立旗標檔`secrets/MAINNET_ENABLE`，內容**逐字**一行：
   ```
   i_understand_this_uses_real_money=yes
   ```
4. 執行`python research/mainnet_gate.py status`確認`enabled: true`。
5. **此時仍然不會送單**——最後一步是把`mainnet_gate.py`裡的
   `DRY_RUN`改成`False`，**那是一個獨立的變更，請明確下令，不要讓
   自動化流程自己順手改**。

---

## 3. 每日對帳 SOP（真錢啟用後）

**每個交易日收盤後執行，不可跳過：**

1. 比對三方一致：券商實際持倍 vs 系統記錄的部位快照 vs 引擎目標權重。
   三者任一不符 → 立即呼叫`mainnet_gate.set_kill_state("halt_new", 原因)`，
   當天不再送任何新單，並用`execution_logs.log_reconciliation(status=
   "MISMATCH", ...)`記錄。
2. 三方一致 → `execution_logs.log_reconciliation(status="MATCH", ...)`。
3. 檢視當日新增的滑價紀錄（`execution_logs.log_slippage`寫入的）：
   - 中位`vs_signal_bp`是否顯著高於回測假設（`DEFAULT_SLIPPAGE_BPS`的2倍）？
   - 有沒有單筆異常大的滑價？
4. 核對手續費是否與預期一致（手續費另計，不併入滑價，見`execution_logs.py`）。
5. 跑`python research/execution_quality_scorecard.py`，把結果記進
   `research/REPORT.md`（即使「沒事」也要記一行）。

---

## 4. Kill 條件（達到任一條就停，不要討價還價）

**兩級kill的分工（`mainnet_gate.py`已實作為程式邏輯，非僅文件敘述）**：

| 觸發條件 | 動作 |
|---|---|
| 對帳三方不符 | `halt_new` — 停止送新單，既有部位出場照常執行；查清楚之前不再送新單 |
| `slippage_log`當日中位`vs_signal_bp`超過回測假設2倍 | `halt_new` — 代表流動性假設崩了 |
| 連線異常／API錯誤連續3次 | `halt_new` |
| 實際持倉出現白名單以外的標的 | `halt` — 連調整都停，人工介入 |
| 單日虧損達到總司令裁示的門檻（待裁示，寫進`secrets/mainnet_limits.json`
  或另一份風控設定，本文件不預設數字） | `halt_new`；是否人工全部平倉由
  總司令決定，不由自動化執行 |
| 累計虧損達到總司令裁示的門檻（待裁示） | **結束這次實驗，回頭檢討，不要
  補錢** |

**`halt_new`與`halt`的差別**（`mainnet_gate.is_new_order_allowed()` /
`is_existing_position_action_allowed()`已實作此語意並經自我測試驗證）：
`halt_new`只擋新單，既有部位的**出場照常執行**（不能因為停機就讓虧損部位
裸奔）；`halt`連調整都停，等於凍結，只有人工能動。

**自動化目前只會做`halt_new`的邏輯判斷（函式已備妥），不會做`flatten`
（全部平倉）——`flatten`一律由總司令本人決定，自動平倉在極端行情裡本身
就是風險。** 這條沿用Cybex原始RUNBOOK的判斷，本文件完全繼承。

---

## 5. 第一個 30 天的驗收標準：**只看執行品質，不看損益**

30天內不得用「賺了多少」判斷這次上線成功與否——樣本太小，統計上什麼都
證明不了（`research/SELECTION_BIAS_LEDGER.md`已說明回測階段的統計證據已經
用盡，真錢階段要累積的是**執行面**的證據）。

30天要回答的是這五個問題，`research/execution_quality_scorecard.py`會自動
從`research/execution_logs.py`的資料算出來：

| # | 問題 | 通過標準 | 對應函式 |
|---|---|---|---|
| 1 | 紙上部位和真錢部位對得起來嗎 | **30/30天對帳無不符**（零股尾差不算） | `score_q1_reconciliation()` |
| 2 | 真實滑價 vs 回測假設差多少 | 中位`vs_signal_bp` ≤ 回測假設（`DEFAULT_SLIPPAGE_BPS`）的**2倍** | `score_q2_slippage()` |
| 3 | 送單成功率 | ≥ **95%** 完全成交 | `score_q3_fill_rate()` |
| 4 | 基礎設施可靠度 | **零非預期停擺**；任何一次停擺都要有事後記錄 | `score_q4_reliability()` |
| 5 | kill條件真的能執行嗎 | 至少**演練一次**`halt_new`，證明它不是紙上規則 | `score_q5_kill_drill()` |

**五題全過 → 才討論是否加碼資金或延長。任何一題不過 → 停下來修，不加碼。**
損益數字照常記錄、照常顯示，但**在這30天內它不是判準**。

**現況**：五題目前全部是`INSUFFICIENT_DATA`（尚無真錢資料），這是預期中的
空狀態，不是失敗。

---

## 6. 滑價記錄格式（`research/execution_logs.py::log_slippage()`）

| 欄位 | 意義 |
|---|---|
| `signal_px` | 訊號價（決策當下引擎看到的價格） |
| `intended_px` | 送單當下的參考價 |
| `filled_px` | 實際成交均價 |
| `slippage_bp` | 相對`intended_px`的滑價，**正＝吃虧**（買賣方向已處理） |
| `vs_signal_bp` | 相對`signal_px`的滑價，**含決策到送單之間的價格漂移**——比較回測假設時看這一欄 |
| `fee_twd` | 手續費，**另計，不併入滑價** |
| `session` | 台股新增欄位：`開盤集合競價`／`盤中逐筆撮合`／`收盤集合競價` |
| `is_call_auction` | 台股新增欄位：是否為集合競價撮合（由`session`推導） |
| `dry_run` | `True`＝模擬（預設），`False`＝真錢 |

---

## 7. 版本紀錄

| 日期 | 事件 |
|---|---|
| 2026-09-15 | 建立。`mainnet_gate.py`（四道屏障+兩級kill）、`execution_logs.py`
  （五本證據帳本，含雜湊鏈）、`execution_quality_scorecard.py`（30天五題）
  三支程式碼與本手冊完成，全部自我測試PASS。**未啟用，旗標檔不存在。
  目前無可用券商下單API，這是規則先行的預備基礎設施。** |
