# MARATHON_STATE.md — 斷點狀態檔

**這份檔案永遠只描述「現在」，會被覆寫，不是 append-only。** 換 session／換機器／換 agent 接手 Phase 2（自動下單引擎）研究工作時，**先讀這份**，再視需要去查 `REPORT.md`（細節動作記錄）、`STRATEGY_LOG.md`（里程碑敘事）、`LEADS.md`（策略候選）。

**最後更新：2026-08-22T14:00:00+08:00**

**GitHub 稽核狀態：✅ 通過**（12:00 的 `.py` 檔案存在性問題是 Cowork 端舊快照；13:00 的 holdout 截斷漏洞是真的，已修復，見下方里程碑 2）。**如果又收到類似回報，先照 STRATEGY_LOG.md 的 FILE MANIFEST 重新走一次驗證，不要預設是自己這邊漏推，也不要預設對方一定錯——這次兩種情況都各發生過一次。**

**Holdout 狀態：✅ 依然未被使用。** `is_holdout_consumed()` 目前回傳 `False`，`HOLDOUT_LOCK.json` 不存在。里程碑 4 第一個候選（`weinstein_stage2_pilot_v1`）已經完整跑過 train/val 全套關卡並判定 `FAIL`，全程沒有觸碰 holdout。

---

## 現在做到哪

**里程碑 1（資料誠實度盤點）：✅ 完成。** 三顆地雷（台股還原股價、存活者偏差、財報 point-in-time）都已實測、記錄在 `DATA.md`，並且已經寫成程式碼修復（不只是文件）：
- `adjust.py` — 台股還原股價，用 2330 全部 42 筆歷史除權息事件驗證過
- `universe.py` — TW 回測宇宙限定 2003 年後 + 納入下市股（3,196 檔），殘餘偏差已記錄
- `pit.py` — 財報保守發布延遲假設（季報 +45 天、月營收優先真實 `create_time`）

**里程碑 2（驗證框架）：🟡 進行中，地基元件做完，還沒串成一個能跑的骨架。**
- ✅ `validation/holdout.py` — train/val/holdout 物理隔離，train≤2020、val 2021–2024、holdout 是之後到今天，`unlock_holdout_once()` 一次性鎖，鎖檔跟稽核日誌都進 git（`HOLDOUT_LOCK.json`／`HOLDOUT_LOG.md`，目前都還不存在，因為還沒真的用過）。**2026-08-22 追加 `assert_no_holdout_leakage()`**：資料載入時的硬性斷言，取代原本只能靠 `cap_to_dev()` 選配的弱防護
- ✅ `finmind_client.py` — **2026-08-22 重構**：`load_dev()` 現在是策略/分析程式碼唯一該用的資料入口，內建自動截斷在 `VAL_END`；`_fetch()`／`load_full_history()` 是不對外的底層路徑。修的是 Cowork 抓到的真漏洞：原本 `fetch()` 預設無截斷。
- ✅ `validation/costs.py` — 台股成本模型（手續費0.1425%×2/證交稅0.3%或0.15%/滑價）+ 漲跌停鎖死偵測（用真實資料 3231 在 2025-04-07 的跌停案例驗證過）
- ✅ `validation/control_group.py` — 隨機控制組，策略無關（`evaluate_fn` seam），合成資料驗證過區辨力
- ✅ `validation/criteria.py` — 事前綁定標準（鎖檔+雜湊比對，防止事後移動門柱），驗證過鎖定/竄改偵測都正常
- ✅ **2026-08-22 已串成能跑的骨架**：`backtest/engine.py`（通用回測引擎，日曆逐日走、T日訊號→T+1成交、三層風控、`validation/costs.py` 成本、進場前 `assert_no_holdout_leakage()`）。已用真實策略（下方里程碑 4）實跑驗證過，不是空殼。
- ❌ **還沒做**：美股成本模型（價差/衝擊/借券/wash sale/PDT）——目前 `costs.py` 只有台股
- ❌ **還沒做**：`control_group.py` 的動態週頻重抽版本——目前里程碑 4 用的是簡化版靜態對照（見下方）

**里程碑 3（紙上前測基礎設施）：🟡 剛起步，只有骨架先搭好，沒有真實資料流過。**
- ✅ `audit_ledgers.py` — 唯讀稽核腳本，**3** 條恆等式（每個平倉有對應進場記錄、無 NaN 價格/股數、無未經 holdout 解鎖的未來日期交易）。**2026-08-22 追加**：對里程碑 4 真實跑出來的 train（324 筆）／validation（160 筆）交易紀錄實測，全部 PASS
- ✅ `trades.csv` schema 已定義，`research/data/backtests/` 底下已有真實回測的交易/權益曲線 CSV（`.gitignore` 排除，本機保留）——注意這是**回測**輸出，不是紙上前測帳本；紙上前測用的 `data/ledger/trades.csv` 還沒開始
- ✅ `LEADS.md` — 第一列已填（`weinstein_stage2_pilot_v1`，判定 `FAIL`）
- ❌ **還沒做**：影子帳本本身（開一本空手起跑的 paper book，只認前向自己開的單）——跟回測引擎是兩回事，回測是「歷史資料重播」，紙上前測是「接上即時資料、真的往前走」
- ❌ **還沒做**：`dashboard.html`（使用者說「必要時」才做）
- ❌ **還沒做**：每日/每三日自動健檢排程

**里程碑 4（Weinstein 第二階段 baseline）：✅ 第一輪跑完，結果 FAIL，未進 holdout。**
- `strategies/weinstein_stage2.py`：股票層 150 日均線上揚突破 + 60 日動量排名；大盤層加權指數 200 日均線閘門。
- `strategies/run_weinstein_pilot.py`：30 檔手選試點宇宙（**非全市場**，見下方已知簡化），train(2015–2020)/val(2021–2024) 都通過買進持有比較跟成本 1x/2x/3x 敏感度，**但隨機控制組沒打贏**（val 期策略落在第 24.5 百分位，輸給隨機靜態買進持有的中位數）。判定 `FAIL`，記在 `LEADS.md`。
- 完整結果、解讀、已知簡化見 `STRATEGY_LOG.md`／`REPORT.md` 2026-08-22T14:00 條目。

**里程碑 5（挖策略）：未開始**——第一個候選沒過，還沒有東西可以往下一步推。

---

## 下一步（優先序，僅供接手者參考，實際順序看使用者當下指示）

等使用者決定 `weinstein_stage2_pilot_v1` FAIL 之後的方向。`STRATEGY_LOG.md` 該條目列了三個選項（換宇宙建構方式 / 升級隨機控制組成動態版本 / 全新參數當新候選），沒有預設答案。任何後續嘗試都要走一輪新的 `LEADS.md` 記錄，不能直接改 `weinstein_stage2_pilot_v1` 這條的判定。

其他背景待辦（優先度較低，不阻塞上面）：
1. 美股成本模型補到 `costs.py`。
2. `control_group.py` 升級成動態週頻重抽版本（目前的靜態版本是已知簡化）。
3. 紙上前測影子帳本（里程碑 3 剩下的部分）。

## 目前沒有在等待使用者回覆的事

無阻塞事項——上面「等使用者決定方向」不算阻塞，因為背景待辦（美股成本模型/動態控制組/影子帳本）都可以先做。

---

## 檔案地圖

| 檔案 | 用途 | git 狀態 |
|---|---|---|
| `CONSTITUTION.md` | Phase 2 最高原則，違反即無效 | 進 git |
| `DATA.md` | 資料誠實度盤點結果（里程碑 1） | 進 git |
| `STRATEGY_LOG.md` | 里程碑等級敘事日誌 + FILE MANIFEST | 進 git |
| `REPORT.md` | 顆粒度細的 append-only 執行記錄 | 進 git |
| `LEADS.md` | 策略候選登記簿（1 列：`weinstein_stage2_pilot_v1`，FAIL） | 進 git |
| `MARATHON_STATE.md` | 本檔案，斷點狀態快照 | 進 git |
| `HOLDOUT_LOCK.json` / `HOLDOUT_LOG.md` | holdout 一次性鎖 + 稽核軌跡 | 進 git（尚未產生） |
| `criteria/*.json` | 鎖定的事前通過標準 | 進 git（尚未產生） |
| `finmind_client.py` / `adjust.py` / `universe.py` / `pit.py` | 資料層 | 進 git |
| `validation/*.py` | 驗證框架 | 進 git |
| `backtest/*.py` | 回測引擎骨架（里程碑 4 新增） | 進 git |
| `strategies/*.py` | 策略訊號 + 跑法（里程碑 4 新增） | 進 git |
| `audit_ledgers.py` | 唯讀稽核腳本 | 進 git |
| `data/` | parquet 快取、`data/backtests/`、`data/ledger/trades.csv`、回測結果 | **不進 git**（`.gitignore`） |
