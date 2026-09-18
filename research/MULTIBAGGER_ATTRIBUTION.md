# 飆股歸因分解（衛星倉·描述性研究）——進度記錄

對應 `PENDING_QUEUE.md`「重構.B」／2026-09-18（續3）總司令裁示。

## 本輪（馬拉松自走，2026-09-18，接續上一輪 hypothesis_queue）做了什麼

1. **修正抽樣 bug**：`multibagger_attribution.py::main()` 改成先過濾
   `stock_id` 為 4 位純數字（排除 ETF 連結型代號 `00400A` 這類帶字母
   尾碼的樣本，`universe()` 本身的 `is_warrant` 過濾只擋 6 位純數字
   權證，不擋這種），再用固定種子（`SAMPLE_SEED=42`）隨機抽樣，取代
   舊版「依字母排序取前 N 檔」（那個取法會系統性抽到 ETF 代號）。
   刻意不動共用的 `universe.py`，只在本檔案內過濾，避免影響其他呼叫者。
2. **重跑 20 檔煙霧測試（`MULTIBAGGER_SMOKE_SIZE=20`）驗證通過**：
   宇宙總數 3196 檔，過濾掉 450 檔非 4 位數字代號後隨機抽 20 檔，
   **17/20 真正跑進 `process_stock()` 核心計算**（3 檔因
   `adjust.adjusted_price_series()` 抓不到足夠長價格序列被
   `price_too_short` 跳過，是正常情況非 bug），產出 198 個 moonshot
   窗口，`yearly_base_rate` 有 2002～2024 年逐年數字（**這仍是 20 檔
   小樣本，數字僅供驗證管線正確性，不得引用為結論**）。這證明抽樣
   bug 已修正、歸因邏輯確實能在真實普通股資料上跑出非空結果。
3. **已投遞 300 檔工作**（依裁示原文建議樣本量）：
   `run_detached.py submit --name multibagger_attribution_300`，
   job_id=`20260918-140419-49bf`，session 內等待 4 分鐘未完成（300 檔
   預估耗時遠超 20 檔的驗證輪，逐檔含多次 PIT 模組呼叫），**已脫離
   session 背景執行，下一輪用
   `python research/run_detached.py status` / `log 20260918-140419-49bf`
   收成**，預期產出 `research/multibagger_raw/run_summary.json`。

## 上一輪（hypothesis_queue 自走，2026-09-18）做了什麼

1. 建立 `research/multibagger_attribution.py`：定義「起飛事件」＝任一 12
   個月月頻滾動窗口還原權息報酬 ≥ +100%，並串接既有 PIT-safe 模組
   （`universe.universe()`／`adjust.adjusted_price_series()`／
   `pit.quarterly_pit()`／`pit.month_revenue_pit()`），逐檔 try/except
   隔離錯誤（單檔失敗不影響其他檔）。
2. 跑了一次 6 檔的管線煙霧測試（`MULTIBAGGER_SMOKE_SIZE=6`）：**程式碼
   本身跑完整個流程沒有拋出未捕捉例外，正確寫出 `run_summary.json`**，
   但抽到的 6 檔（依 stock_id 字母排序取前 6 檔）恰好全是 ETF 連結型
   代號（`00400A`～`00405A`），這類代號沒有真正的股票價格/EPS 資料，
   6 檔全部被 `price_too_short` 跳過——**這證明了錢包沒有炸掉（error
   isolation 有效），但沒有證明歸因邏輯本身算得對**，因為沒有一檔真正
   跑進 `process_stock()` 的核心計算。

## 已知缺口（截至本輪，仍待解決）

- **五題目前仍全部尚未真正回答**：20 檔驗證輪的數字只證明管線正確，
  樣本太小不能拿來回答五題（母體 3196 檔裡只抽 20 檔，逐年基準機率
  等統計量在這個樣本量下噪音極大）。**不得引用 20 檔或 6 檔輪任何
  統計數字作為結論**，要等 300 檔（下一輪收成）甚至全宇宙跑完才行。
- 第 2 題（歸因分解）目前只實作兩項嚴格對數恆等式（EPS 成長貢獻 +
  PE 變化貢獻），第三項「股數變化」因 FinMind 免費層缺可靠流通股數
  欄位，如實標為待補資料源，見程式檔頭 docstring 詳細說明，這不是
  遺漏是誠實揭露的已知限制。
- 全宇宙（依裁示原文，先小樣本再放全量）尚未開跑，本輪只完成
  20 檔驗證＋投遞 300 檔背景工作，300 檔結果尚待下一輪收成。

## 下一輪待做

1. **收成 300 檔背景工作**（job_id=`20260918-140419-49bf`）：
   `python research/run_detached.py status` 確認 `finished`／`failed`／
   `timeout`，`finished` 則讀 `research/multibagger_raw/run_summary.json`
   核對 `n_ok`／`n_skipped`／`skip_reasons_sample`，確認 skip 比例合理
   （不應該像舊版全軍覆沒）。
2. 300 檔驗證通過（多數股票真正跑進核心計算、無異常錯誤集中）後才
   放大到全宇宙（3196 檔，扣掉非普通股代號後約 2746 檔）。
3. 全宇宙跑完才能真正回答五題（逐年基準機率含空頭年／EPS-PE-股數
   三項歸因分解／起漲前 PIT-safe 特徵／對照組起飛率-平庸率-下市率
   表／市值門檻邊際效果），全程 TRAIN+VAL、PIT-safe、不生選股規則。
