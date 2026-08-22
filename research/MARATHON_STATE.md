# MARATHON_STATE.md — 斷點狀態檔

**這份檔案永遠只描述「現在」，會被覆寫，不是 append-only。** 換 session／換機器／換 agent 接手 Phase 2（自動下單引擎）研究工作時，**先讀這份**，再視需要去查 `REPORT.md`（細節動作記錄）、`STRATEGY_LOG.md`（里程碑敘事）、`LEADS.md`（策略候選）、`FACTORS.md`（因子登記簿）。

**最後更新：2026-08-22T16:00:00+08:00**

**⏸ 目前停在：AI 選股引擎 Phase A 步驟 1／2 做完，依使用者指示在此暫停等審。** 步驟 3（`score.py` 計分）跟步驟 4（App 選股頁）**不會自己開始**，要等 Cowork／使用者審完步驟 2 的因子結果（`FACTORS.md`）才繼續。

**GitHub 稽核狀態：✅ 通過**（12:00 的 `.py` 檔案存在性問題是 Cowork 端舊快照；13:00 的 holdout 截斷漏洞是真的，已修復）。**如果又收到類似回報，先照 STRATEGY_LOG.md 的 FILE MANIFEST 重新走一次驗證，不要預設是自己這邊漏推，也不要預設對方一定錯。**

**Holdout 狀態：✅ 依然未被使用。** `is_holdout_consumed()` 複查為 `False`，`HOLDOUT_LOCK.json` 不存在。目前有一個候選（`weinstein_stage2_unbiased`）train/val 全部關卡都過，是否要花掉這個專案唯一一次 holdout 測試機會在它身上，**需要使用者明確授權，這裡不會自己決定**。

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
- ✅ `validation/control_group.py` — `run_control_group()`（靜態版，仍保留）+ **2026-08-22 新增 `run_matched_control_group()`**（配對式：同進出場日期只換股，機制上真正對應策略行為，Cowork 要求的修正）
- ✅ `validation/criteria.py` — 事前綁定標準（鎖檔+雜湊比對，防止事後移動門柱），驗證過鎖定/竄改偵測都正常
- ✅ `backtest/engine.py`（通用回測引擎，日曆逐日走、T日訊號→T+1成交、三層風控、`validation/costs.py` 成本、進場前 `assert_no_holdout_leakage()`）。已用真實策略實跑兩輪驗證過。**2026-08-22 追加 `sortino_ratio` 屬性**；`buy_leg_rate()`/`sell_leg_rate()` 拿掉底線變公開，給 `control_group.py` 重用（單一成本費率來源）
- ❌ **還沒做**：美股成本模型（價差/衝擊/借券/wash sale/PDT）——目前 `costs.py` 只有台股

**里程碑 3（紙上前測基礎設施）：🟡 剛起步，只有骨架先搭好，沒有真實資料流過。**
- ✅ `audit_ledgers.py` — 唯讀稽核腳本，3 條恆等式，對兩輪真實回測交易紀錄（共 4 批：train/val × pilot/unbiased）都實測 PASS
- ✅ `trades.csv` schema 已定義，`research/data/backtests/` 底下有兩輪真實回測的交易/權益曲線 CSV（`.gitignore` 排除，本機保留）——注意是**回測**輸出，不是紙上前測帳本
- ✅ `LEADS.md` — 2 列（`weinstein_stage2_pilot_v1` FAIL、`weinstein_stage2_unbiased` EXPERIMENTAL）
- ❌ **還沒做**：影子帳本本身（開一本空手起跑的 paper book，只認前向自己開的單）
- ❌ **還沒做**：`dashboard.html`（使用者說「必要時」才做）
- ❌ **還沒做**：每日/每三日自動健檢排程

**里程碑 4（Weinstein 第二階段 baseline）：✅ 兩輪跑完，第二輪（無偏宇宙+配對式控制組）train/val 全過，仍未進 holdout。**
- `strategies/weinstein_stage2.py`：股票層 150 日均線上揚突破 + 60 日動量排名；大盤層加權指數 200 日均線閘門（兩輪都用同一套訊號邏輯，沒有為了過關而改訊號）。
- **第一輪**（`strategies/run_weinstein_pilot.py`，30 檔手選試點宇宙）：買進持有/成本敏感度都過，**隨機控制組沒打贏**（第 24.5 百分位）。判定 `FAIL`。事後發現方法論有兩個缺陷（Cowork 指出）：靜態對照組不對應策略機制、手選宇宙有選擇偏差。
- **第二輪**（`strategies/run_weinstein_unbiased.py`，`universe.py` 全市場隨機抽樣 100 檔 + 配對式控制組）：四項關卡（買進持有 val+train/成本1x2x3x敏感度/交易數≥100/配對式隨機控制組）**全部通過**（控制組第 99.5 百分位）。判定 **`EXPERIMENTAL`**（規則要求 `PASS` 必須含 holdout 驗證，這輪沒碰）。過程中抓到並修好 3 個真 bug（`adjust.py` 兩處空值檢查順序錯、`engine.py` 除以零），詳見 `REPORT.md`。
- 完整結果、解讀、已知簡化見 `STRATEGY_LOG.md`／`REPORT.md` 2026-08-22T14:00 跟 T15:00 兩條。

**里程碑 5（挖策略）：未開始**——`weinstein_stage2_unbiased` 是否進 holdout 還沒決定，決定之前不會開新策略。

---

## AI 選股引擎 Phase A（新工作流，跟里程碑 1–5 平行，不是同一條線）

依使用者設計書分 5 步：因子庫→因子IC檢定→計分→App選股頁→每日排程。**目前狀態：步驟 1、2 完成，因子結果已產出，在此暫停等 Cowork／使用者審，步驟 3、4、5 都還沒開始，不會自己往下做。**

- ✅ `factors.py`：6 個因子全部實作，全部透過 `load_dev()`／`pit.py` 取資料，基本面因子用 `merge_asof(direction='backward')` 鍵在 `pit_date` 做 point-in-time 對齊，用真實資料逐日驗證過對齊時間點完全正確（不早於揭露日）。(d) 因子的「市值」用流動性正規化代替（`TaiwanStockMarketValue` 付費，已驗證確認），有明確揭露。
- ✅ `factor_ic.py`：跟 `weinstein_stage2_unbiased` 同一套無偏抽樣（100 檔種子`20260822`，80 檔可用）、121 個不重疊 20 日橫截面、train/val 分開、200 次隨機打散對照組。
- ✅ `FACTORS.md`：6 個因子的完整結果登記，**只有 `f_eps_growth` 通過**（val IC +0.073，打散對照 100 百分位），其餘 5 個因子（月營收YoY加速度/外資連續買超/三大法人淨買/相對強度/站上季線量能）都沒過，原因逐一記錄（其中 2 個是 train/val 正負號相反，1 個差一點點沒到門檻）。

## 下一步（優先序，僅供接手者參考，實際順序看使用者當下指示）

1. **當下最優先**：等 Cowork／使用者審 `FACTORS.md` 的因子結果，決定要不要進 AI 選股引擎步驟 3（`score.py`）。**不要自己跳過這個審核往下做。**
2. `weinstein_stage2_unbiased` 要不要做一次性 holdout 測試（跟上面是平行的兩條線，互不阻塞）——需要明確授權，這裡不會自己決定。

背景待辦（優先度較低，不阻塞上面兩項）：
1. 美股成本模型補到 `costs.py`。
2. 擴大抽樣規模，或真的逐檔掃全市場。
3. 紙上前測影子帳本（里程碑 3 剩下的部分）。

## 目前沒有在等待使用者回覆的事（下面兩項例外，**是**在等）

- AI 選股引擎步驟 3/4/5 要不要繼續——**是**在等 Cowork／使用者審完步驟 2 的因子結果，明確要求「先停下」。
- `weinstein_stage2_unbiased` 是否進 holdout——**是**在等使用者，因為 holdout 一次性、不可逆。

其餘背景待辦不阻塞，可以先做。

---

## 檔案地圖

| 檔案 | 用途 | git 狀態 |
|---|---|---|
| `CONSTITUTION.md` | Phase 2 最高原則，違反即無效 | 進 git |
| `DATA.md` | 資料誠實度盤點結果（里程碑 1） | 進 git |
| `STRATEGY_LOG.md` | 里程碑等級敘事日誌 + FILE MANIFEST | 進 git |
| `REPORT.md` | 顆粒度細的 append-only 執行記錄 | 進 git |
| `LEADS.md` | 策略候選登記簿（2 列：`weinstein_stage2_pilot_v1` FAIL、`weinstein_stage2_unbiased` EXPERIMENTAL） | 進 git |
| `FACTORS.md` | 因子登記簿（6 列，1 個 PASS：`f_eps_growth`） | 進 git |
| `MARATHON_STATE.md` | 本檔案，斷點狀態快照 | 進 git |
| `HOLDOUT_LOCK.json` / `HOLDOUT_LOG.md` | holdout 一次性鎖 + 稽核軌跡 | 進 git（尚未產生） |
| `criteria/*.json` | 鎖定的事前通過標準 | 進 git（尚未產生） |
| `finmind_client.py` / `adjust.py` / `universe.py` / `pit.py` | 資料層 | 進 git |
| `validation/*.py` | 驗證框架 | 進 git |
| `backtest/*.py` | 回測引擎骨架（里程碑 4 新增） | 進 git |
| `strategies/*.py` | 策略訊號 + 跑法（里程碑 4 新增） | 進 git |
| `factors.py` / `factor_ic.py` | AI 選股引擎 Phase A 步驟 1/2（因子庫 + IC 檢定） | 進 git |
| `audit_ledgers.py` | 唯讀稽核腳本 | 進 git |
| `data/` | parquet 快取、`data/backtests/`、`data/factor_ic_results.csv`、`data/ledger/trades.csv`、回測結果 | **不進 git**（`.gitignore`） |
