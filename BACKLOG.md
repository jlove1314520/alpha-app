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

## ✅ 已驗收（各項附實際冒煙測試時間戳與輸出）

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

- **P1-新 選股改為「全市場 + 資料完整度」，不要用門檻排除**（2026-08-27完成）：
  移除伺服器端`coverage<0.5`硬性排除，全部2,586檔都進`scores.json`的
  `stocks[]`（原本只有341檔）；每筆輸出新增`missing_factors`（缺哪幾項因子）
  +`coverage`（已有，前端用於視覺弱化）；`index.html`的`pickRowHtml()`改成
  低完整度卡片降不透明度至0.62+加註「資料稀疏，分數僅供參考（缺XX、YY）」，
  不隱藏；**新增流動性門檻**（原本這條JSON-only路徑完全沒有，用
  `data/price_history.json`的turnover算近20日均成交值，低於門檻標記
  「流動性不足」、`rank`留`null`不進數字排名，沿用研究端score_v2.py既有
  設計）；選股頁新增固定說明「總分與資料完整度是兩件事」。
  `meta.avg_coverage`從341檔子集的0.597變成全市場2,586檔的0.341（分母
  變大是預期中的下降，不是新的資料流失）。

  冒煙測試實際輸出（2026-08-27 21:18，`node scripts/smoke_test.mjs`）：
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
  另外用直接查詢驗證：rank 1（2344，coverage 0.54）opacity=1無標記；
  rank 2-3（coverage 0.28）opacity=0.62、有「資料稀疏」標記；原本因
  coverage<0.5被排除、單因子造成假高分的6225/6810現在`rank=null`+標記
  「流動性不足」+「資料稀疏」（雙重標記，正確不進數字排名）。

---

- **P1-新 補足TPEx上櫃三大法人/融資融券資料缺口**（2026-08-27完成）：
  查證確認缺口確實是上櫃股票（TWSE T86/MI_MARGN都只涵蓋上市）。新增
  `fetch_institutional_tpex()`（`tpex_3insti_daily_trading`）+
  `fetch_margin_by_stock_tpex()`（`tpex_mainboard_margin_balance`），merge
  時修正原本`tse_codes`過濾器會把所有TPEx代碼一併濾掉的問題（TWSE來源仍用
  官方上市清單過濾ETF/權證，TPEx來源的代碼另外放行，不套用不適用的過濾）。
  **涵蓋檔數變化**：三大法人 1,083→1,990 檔、融資融券 1,063→1,983 檔、
  `stock_detail.json`合計 1,983→2,321 檔。**scores.json平均coverage
  0.341→0.376**（chips因子權重14%受益最多）。已知限制：TPEx這兩個端點未做
  ETF/權證過濾（跟fundamentals.json的TPEx補充同一個既有取捨，不是新問題）。

  冒煙測試實際輸出（2026-08-27 21:27，`node scripts/smoke_test.mjs`）：
  ```
  PASS - 1. 頁面載入無uncaught error/unhandledrejection
  PASS - 2. 右上角時鐘interval在3秒內有執行：呼叫了4次
  PASS - 3. 六個分頁都能切換且不拋錯
  PASS - 4. 主要面板都有內容（不是完全空白）
  PASS - 5. 市場頁三個市場切換都不拋錯
  PASS - 6. 互動元素可點擊性（類股卡/選股排行列/自選股列）
  PASS - 7. 整個測試過程（含所有互動操作）結束後仍無累積的uncaught error
  === 冒煙測試結果：全部通過 ===
  ```

- **P2-新 美股盤前盤後（Extended Hours）**（2026-08-27完成）：
  - `fetch_quotes_us.py`新增`fetch_extended_hours_yf()`（yfinance
    `Ticker.get_info()`的`preMarketPrice`/`postMarketPrice`/
    `regularMarketPrice`），寫進`quotes_us.json`每檔的`extended_hours`
    子物件，`regular`/`pre`/`post`三個獨立欄位各自帶`time`時間戳，
    跟既有Finnhub regular quote完全分開存放、互不影響（yfinance失敗不影響
    Finnhub已抓到的regular報價）。
  - `us_market_session()`：pre(04:00-09:30)/regular(09:30-16:00)/
    post(16:00-20:00)/closed，用`zoneinfo.ZoneInfo("America/New_York")`
    算美東當地時間分鐘數判斷，**不寫死UTC常數**，日光節約由zoneinfo自動
    處理。
  - `quotes.yml`排程延長：cron本身不懂時區，改成「排寬（同時涵蓋EDT/EST
    兩種UTC對應區間）+ 腳本自己精確判斷」——主區塊UTC 08:00-23:59（週一
    至五）+ 跨午夜收尾區塊UTC 00:00-01:59（週二至六，對應前一個美股交易
    日晚上20:00 ET收盤）。
  - `index.html`：新增`usMarketSession()`（跟Python版同一套ET分鐘邊界）+
    `mktPillUS()`取代原本二態的`mktPill()`呼叫，右上角美股時鐘擴為
    盤前/盤中/盤後/休市四態；自選股列的美股報價新增獨立一行顯示盤前/
    盤後價（跟正規盤價明確分開、標示「盤前」/「盤後」字樣），只在真的
    顯示了盤前/盤後價時才出現風險揭露文字「延長交易時段流動性低、價差大，
    僅接受限價單，價格常於隔日開盤反轉」（不是固定貼一段沒人看的警語）。
  - IBKR `outsideRth`旗標：只記錄在這裡，這輪不實作（使用者原話「先記進
    BACKLOG，現在不實作」）。

  冒煙測試實際輸出（2026-08-27 21:36，`node scripts/smoke_test.mjs`）：
  ```
  PASS - 1. 頁面載入無uncaught error/unhandledrejection
  PASS - 2. 右上角時鐘interval在3秒內有執行：呼叫了4次
  PASS - 3. 六個分頁都能切換且不拋錯
  PASS - 4. 主要面板都有內容（不是完全空白）
  PASS - 5. 市場頁三個市場切換都不拋錯
  PASS - 6. 互動元素可點擊性（類股卡/選股排行列/自選股列）
  PASS - 7. 整個測試過程（含所有互動操作）結束後仍無累積的uncaught error
  === 冒煙測試結果：全部通過 ===
  ```
  另外用直接注入測試資料驗證：`usMarketSession()`四態分類正確（pre/regular/
  post/closed各自對應正確的邊界時間）；自選股列注入盤前資料後正確顯示
  「盤前 $311.2 -0.72%」獨立一行、跟正規盤價$310.5分開，風險揭露文字
  同時正確顯示。**已知限制**：`fetch_quotes_us.py`完整流程（含Finnhub
  regular quote）需要`FINNHUB_API_KEY`，本機沒有這把key無法完整端對端
  測試，只驗證了新增的yfinance extended_hours部分（獨立函式，用真實網路
  呼叫驗證過）。

## 🔄 進行中

- **P2-新 財報行事曆**（2026-08-27登錄）：評估yfinance earnings dates或
  SEC申報建立data/earnings_calendar.json，標示追蹤標的財報日與公布時段
  （盤前/盤後）。**進度：尚未開始。**

## ❌ 待處理（依使用者指定順序排列）

（目前為空——依使用者指定的P0→全市場改造→上櫃法人補齊→盤前盤後→財報
行事曆順序，前四項皆已完成，財報行事曆是最後一項，已列在上方🔄。）

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
