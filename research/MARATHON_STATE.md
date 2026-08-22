# MARATHON_STATE.md — 斷點狀態檔

**這份檔案永遠只描述「現在」，會被覆寫，不是 append-only。** 換 session／換機器／換 agent 接手 Phase 2（自動下單引擎）研究工作時，**先讀這份**，再視需要去查 `REPORT.md`（細節動作記錄）、`STRATEGY_LOG.md`（里程碑敘事）、`LEADS.md`（策略候選）。

**最後更新：2026-08-22T13:00:00+08:00**

**GitHub 稽核狀態：✅ 2026-08-22T12:00:00+08:00 通過**（`.py` 檔案存在性問題，查證後是 Cowork 端舊快照，非真漏推）。**✅ 2026-08-22T13:00:00+08:00 修復一個真的漏洞**：`finmind_client.fetch()` 原本預設無截斷，任何忘記手動 cap 的研究程式碼都會靜默拿到 holdout 資料。已改成 `load_dev()`（強制截斷，唯一正式入口）＋`_fetch()`（internal）＋`load_full_history()`（唯一合法無截斷路徑，只能餵 `unlock_holdout_once()`）三分，並在資料載入點（`assert_no_holdout_leakage()`）跟帳本層（`audit_ledgers.py` 第 3 條恆等式）各加一道獨立稽核防線。`adjust.py`／`pit.py` 已改用 `load_dev()`；`universe.py` 刻意保留 `_fetch()`（理由見該檔案 docstring）。詳細過程見 `REPORT.md` 2026-08-22T13:00 條目。**如果又收到類似回報，先照 FILE MANIFEST 重新走一次驗證，不要預設是自己這邊漏推，也不要預設對方一定錯——這次兩種情況都各發生過一次。**

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
- ❌ **還沒做**：把上面模組串成一個真正能跑一次「假想策略」的骨架，確認整條管線接起來沒問題——**串接時資料進口一律要走 `load_dev()`，不要圖方便直接叫 `_fetch()`**
- ❌ **還沒做**：美股成本模型（價差/衝擊/借券/wash sale/PDT）——目前 `costs.py` 只有台股

**里程碑 3（紙上前測基礎設施）：🟡 剛起步，只有骨架先搭好，沒有真實資料流過。**
- ✅ `audit_ledgers.py` — 唯讀稽核腳本，目前 **3** 條恆等式（每個平倉有對應進場記錄、無 NaN 價格/股數、**2026-08-22 追加**：無未經 holdout 解鎖就出現的未來日期交易），對空 ledger 跑全 PASS，合成壞資料驗證過真的抓得到問題
- ✅ `trades.csv` schema 已定義（`audit_ledgers.py` 的 `TRADES_SCHEMA`），實體檔案還不存在（`research/data/ledger/trades.csv`，`.gitignore` 排除，因為還沒有任何交易）
- ✅ `LEADS.md` — 策略候選登記簿框架已建好，目前是空的（合乎規定：框架沒蓋好前不挖策略）
- ❌ **還沒做**：影子帳本本身（開一本空手起跑的 paper book，只認前向自己開的單）
- ❌ **還沒做**：`dashboard.html`（使用者說「必要時」才做——現在沒有真實資料可視覺化，先不做假的）
- ❌ **還沒做**：每日/每三日自動健檢排程（目前只能手動跑 `python audit_ledgers.py`）

**里程碑 4（Weinstein 第二階段 baseline）：未開始。** 鐵律：里程碑 2 骨架真正跑起來、里程碑 3 影子帳本能用之前，不會開始。

**里程碑 5（挖策略）：未開始。**

---

## 下一步（優先序，僅供接手者參考，實際順序看使用者當下指示）

1. 把 `validation/` 四個模組串成一個能跑一次的骨架（不用是真策略，隨便一個「隨機挑 5 檔月初買月底賣」都行，重點是驗證管線本身沒有接錯）。
2. 補美股成本模型到 `costs.py`。
3. 影子帳本雛形：定義帳本的欄位/狀態機（現金、持倉、已實現、未實現），空手起跑，接上 `audit_ledgers.py` 的 `check_equity_identity()`。
4. 開始里程碑 4：Weinstein 第二階段全市場掃描 + 大盤總體閘門。

## 目前沒有在等待使用者回覆的事（上一個「需要使用者決定」已在 2026-08-22 解決：研究程式碼放 `alpha-app/research/`）

無阻塞事項。

---

## 檔案地圖

| 檔案 | 用途 | git 狀態 |
|---|---|---|
| `CONSTITUTION.md` | Phase 2 最高原則，違反即無效 | 進 git |
| `DATA.md` | 資料誠實度盤點結果（里程碑 1） | 進 git |
| `STRATEGY_LOG.md` | 里程碑等級敘事日誌 | 進 git |
| `REPORT.md` | 顆粒度細的 append-only 執行記錄 | 進 git |
| `LEADS.md` | 策略候選登記簿 | 進 git |
| `MARATHON_STATE.md` | 本檔案，斷點狀態快照 | 進 git |
| `HOLDOUT_LOCK.json` / `HOLDOUT_LOG.md` | holdout 一次性鎖 + 稽核軌跡 | 進 git（尚未產生） |
| `criteria/*.json` | 鎖定的事前通過標準 | 進 git（尚未產生） |
| `finmind_client.py` / `adjust.py` / `universe.py` / `pit.py` | 資料層 | 進 git |
| `validation/*.py` | 驗證框架 | 進 git |
| `audit_ledgers.py` | 唯讀稽核腳本 | 進 git |
| `data/` | parquet 快取、`data/ledger/trades.csv`、回測結果 | **不進 git**（`.gitignore`） |
