# Alpha App — Backlog / 驗收清單

**驗收標準（2026-08-27 使用者明確裁示，取代先前的預設）**：
「完成」的定義從「程式碼寫好了」改為**「冒煙測試通過 + 該功能可實際操作」**。
未通過冒煙測試（`node scripts/smoke_test.mjs`，Playwright 393×852）的項目，
這份清單一律標 ⚠️，不得標 ✅——即使程式碼看起來已經寫完。每次要把一個項目
從 ⚠️ 改標 ✅，必須附上冒煙測試的實際輸出（不是「已完成」這種文字宣告）。

冒煙測試檢查項目（見 `scripts/smoke_test.mjs`/`scripts/smoke_test.py` 檔頭）：
1. 頁面載入無 uncaught error / unhandledrejection
2. 右上角時鐘 interval 在 3 秒內有執行（monkeypatch 計數）
3. 六個分頁都能切換且不拋錯
4. 主要面板都有內容（不是完全空白）
5. 市場頁三個市場（台股/美股/期貨）切換都不拋錯
6. 互動元素可點擊性（類股卡/選股排行列/自選股列，逐一模擬點擊確認有反應）
7. 整個測試過程（含所有互動操作）結束後仍無累積的 uncaught error

---

## ✅ 已驗收（2026-08-27 20:49 冒煙測試全數通過）

- **B1 時鐘修復**：`setInterval` 先註冊再首次執行，兩句分開；`updateClocks()`
  內所有 DOM 取用（含 `querySelector` 結果）都有 null 檢查，整段包 try/catch。
  對應冒煙測試 check 2、7。
- **B2 冒煙測試框架本身**：`scripts/smoke_test.mjs`（Node.js + Playwright，
  使用者原規格）+ `scripts/smoke_test.py`（備用版本，內容一致）都已完成，
  新增 check 6（互動可點擊性）+ check 7（整個測試過程結束後的累積錯誤，
  修正了原本 check 1 只驗證「頁面剛載入當下」、抓不到後續互動觸發的錯誤
  這個測試框架本身的漏洞）。
- **B3 fundamentals.json**：`status: ok`，`generated_at` 有值，每日排程
  （`market.yml` → `update_fundamentals_daily.py`）正常運作。根因是
  `research/build_fundamentals_json.py` 重跑時整個覆寫 meta、清空
  `generated_at` 的 bug，已修正成 merge 既有 meta。
- **B4 類股卡可點擊**：市場頁「類股表現」每張卡加上點擊 → 開該類股成分股
  清單（代號/名稱/漲跌幅/成交值/AI評分），可再點進個股頁。新增
  `data/company_info.json`（代號→名稱/產業）+ `data/quotes_all_tw.json`
  （全市場輕量收盤/漲跌%/成交值快照）支援。**誠實揭露**：清單依「股票產業
  分類分組」，不是 TWSE 官方指數審核過的完整成分股名冊（畫面本身有這行
  disclaimer）；4 個較舊的合併類別（水泥窯製/塑膠化工/機電/化學生技醫療）
  用聯集近似對應，不保證跟歷史指數定義逐字一致。

  冒煙測試實際輸出（2026-08-27 20:49，`node scripts/smoke_test.mjs`）：
  ```
  PASS - 1. 頁面載入無uncaught error/unhandledrejection
  PASS - 2. 右上角時鐘interval在3秒內有執行：呼叫了3次
  PASS - 3. 六個分頁都能切換且不拋錯
  PASS - 4. 主要面板都有內容（不是完全空白）
  PASS - 5. 市場頁三個市場切換都不拋錯
  PASS - 6. 互動元素可點擊性（類股卡/選股排行列/自選股列）
  PASS - 7. 整個測試過程（含所有互動操作）結束後仍無累積的uncaught error
  === 冒煙測試結果：全部通過 ===
  ```

  **這輪冒煙測試親自抓到的真bug（不是空跑一遍）**：check 6 點擊選股排行列
  後，check 7 才發現 `f.chips`/`f.technical` 的 raw 欄位名在
  `generate_scores_live.py`（JSON-only 上線路徑）跟 `index.html` 讀取的
  `score_v2.py` 舊 schema 不一致，導致 `undefined.toFixed()` 拋出
  unhandledrejection——已修正（`technical` 統一 key 名；`chips` 因為兩條
  管線單位本質不同，改成 `index.html` 兩個 key 都檢查、各自用正確單位顯示）。

---

## ⚠️ 尚未驗收 / 已知限制

- **P1 analyst/catalyst 因子**：全市場沒有免費資料源，暫無解法。
- **earnings_growth 的 PER 反推 EPS 備援**：需要 PER 歷史序列，目前
  `fundamentals.json` 只存最新一筆，尚未建置。
- **technical 因子用未還原權息的收盤價**：除權息當天前後 MA60 會有跳空
  失真，需要抓除權息事件表才能還原。
- **979 檔缺 Q1 基準的財報季度**：因缺同年較早季度資料無法安全還原成單季
  數字，目前跳過不 merge，需要更多歷史資料或額外 FinMind 呼叫才能補上。
- **603 檔 industry 分類歧義**：FinMind `TaiwanStockInfo` 原始資料本身在
  同一天對同一檔股票有超過一種產業分類，`company_info.json` 誠實回傳
  None，需要更權威的產業分類來源或人工判斷才能解決。
- **TPEx 價量端點偶發 SSL 憑證錯誤**：`www.tpex.org.tw` 這幾天間歇性回傳
  `CERTIFICATE_VERIFY_FAILED`（對方伺服器端問題），`_get_retry()` 有正確
  重試+記錄失敗，不是這裡的 bug，但代表 TPEx 股票的 turnover/最新價量
  可能延遲一天更新。
