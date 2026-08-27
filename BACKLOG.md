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

- **P2-新 財報行事曆**（2026-08-27完成）：新增`.github/scripts/fetch_earnings_calendar.py`，
  用yfinance `Ticker.get_calendar()`抓追蹤美股標的（跟`fetch_quotes_us.py`的
  `US_TICKERS`同一份清單）的下一次財報日期，寫進`data/earnings_calendar.json`，
  掛進`market.yml`每日排程。`index.html`自選股列新增財報徽章（只在21天內
  才顯示，避免每列塞滿用不到的遠期資訊），例："📅 財報：9/6（盤後，估計）"。
  **已知限制**：公布時段（盤前/盤後）用`get_earnings_dates()`歷史公布時間
  推估，這台機器目前遇到`curl_cffi`對`guce.yahoo.com`的DNS解析問題（不是
  程式bug，`socket.gethostbyname()`本身正常，GitHub Actions runner環境
  不一定有同樣問題），`estimated_session`誠實降級為`unknown`（顯示「時段
  未知」），不影響`next_earnings_date`本身的可靠性（6/6檔測試成功）。

  冒煙測試實際輸出（2026-08-27 21:44，`node scripts/smoke_test.mjs`）：
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
  另外用注入測試資料驗證：財報日期落在21天內時正確顯示徽章文字。

- **策略層面決定：拆成兩榜（價值成長榜+題材動能榜）**（2026-08-27完成）：
  使用者診斷AI供應鏈題材股幾乎不上榜，根因是權重設計（財報回顧類48%+
  估值PEG 12%合計60%反向懲罰股價領先財報的題材股）。新增獨立的題材動能榜
  引擎：`research/generate_scores_momentum.py`（因子：relative_strength相對
  強度20/60日、volume_breakout量能突破、chip_concentration籌碼集中、
  group_breadth族群齊漲度、sector_capital_flow產業資金流入；財報只當
  financial_risk_flag地雷排除、不計分；估值完全不扣分）+
  `research/weights_frozen_momentum.json`（初始設計權重，非回測最佳化）+
  `research/score_live_momentum.py`（獨立寫入防護，跟價值成長榜的
  weights_frozen.json物理分離、各自版本控管）。`index.html`新增選股頁
  雙榜切換UI（價值成長榜/題材動能榜），共用同一套流動性門檻+視覺弱化邏輯。
  已掛進`market.yml`每日排程，輸出`scores_momentum.json`。

  **過程中親自抓到並修正兩個真bug**：
  1. relative_strength因子原本0/2374檔算得出來——`market_tw.json`的
     `taiex.sparkline`固定20個點，但計算邏輯要求`>=21`個點才算「20日報酬率」
     （off-by-one），60日版本同理。已修正成用19/59個交易日的近似報酬率。
  2. ETF代碼（例如00400A「主動國泰動能高息」）大量混進兩榜排行榜前段——
     題材動能榜的量能/動能類因子對槓桿型ETF特別友善，測試時發現前10名
     幾乎全是ETF。已修正：用`company_info.json`的industry分類
     （ETF/ETN/存託憑證等）+代碼格式（00開頭）雙重過濾，**同一個bug在
     `generate_scores_live.py`（價值成長榜）也存在，一併修正**（重跑後
     scores.json裡0檔00開頭代碼）。

  冒煙測試實際輸出（2026-08-27 22:44，`node scripts/smoke_test.mjs`）：
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
  另外用直接注入測試驗證：切換榜單UI正確顯示對應disclaimer文字+因子標籤；
  點擊題材動能榜的排行列正確開啟報告頁，顯示題材動能榜專屬的5個因子
  （非價值成長榜的8個因子）。題材動能榜實測結果：南亞科/旺宏/力積電/欣興/
  台郡/景碩等記憶體/PCB/晶圓代工相關個股進入前段排名，跟使用者原本點名的
  AI供應鏈題材有重疊，方向正確（**但這不代表這些股票值得投資，兩榜都尚未
  回測驗證，見下方B16**）。

- **B17：未來性濾網 (a)類因子（現在就能算）**（2026-08-27完成）：第三個
  獨立濾網。新增：
  - `research/generate_scores_future.py`：`institutional_buying_streak`
    （法人連續買超天數）、`institutional_ownership_pct`（買超佔股本比，
    用股本÷10股面額反推約略在外流通張數）、`institutional_buying_
    concentration`（買超集中度，外資佔三大法人買超總量比例）、
    `gross_margin_level_stability`（毛利率水準×穩定度，供應鏈議價力代理）、
    `capacity_utilization_proxy`（產能利用率代理，近4季營收合計/最新一期
    非流動資產）。
  - `.github/scripts/update_stock_financials.py`新增擷取`股本`（反推股數）
    +`非流動資產`（固定資產代理）兩個資產負債表欄位。
  - `research/weights_frozen_future.json`+`research/score_live_future.py`：
    跟另外兩榜同一套獨立版本控管+寫入防護。
  - `customer_concentration`（營收客戶集中度）**這一版未實作**——沒有現成
    免費資料源，誠實留白。`capacity_utilization_proxy`**只算目前水準、
    不是趨勢**——`non_current_assets_latest`目前只有最新一筆快照，沒有
    retained歷史序列；且「非流動資產」不是精確的「固定資產」，是TWSE
    官方資產負債表沒有單獨固定資產欄位下的近似代理，兩者都已寫進
    STATUS.json的todo誠實揭露。
  - `index.html`選股頁擴為三榜切換（價值成長榜/題材動能榜/未來性濾網），
    重構`BOARD_CONFIG`集中管理三榜的因子標籤/順序/cache，取代原本
    value/momentum兩路分開寫的ternary。
  - 掛進`market.yml`每日排程，輸出`scores_future.json`。

  冒煙測試實際輸出（2026-08-27 23:00，`node scripts/smoke_test.mjs`）：
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
  另外用注入測試驗證：切換到「未來性濾網」正確顯示對應disclaimer文字+
  5個專屬因子標籤（非另外兩榜的因子集合），點擊排行列正確開啟報告頁。

## 🔄 進行中

（目前為空——夜間自主循環進行中，見下方❌待處理，依序處理。）

## ✅ 2026-08-28 凌晨完成：兩個使用者實測回報的P0問題（時鐘/重整按鈕）

使用者深夜追加指示：兩個「已宣稱修復但手機實測仍壞」的問題最優先根治。

**1. 時鐘仍不動（第五次回報）**——診斷：程式碼本身的clock bug已在B1修好（見
上方✅），headless冒煙測試也一直是PASS，但使用者手機仍卡住——最大嫌疑是
Service Worker快取讓手機一直拿到修復前的舊版index.html。已做：
- (a) 確認`sw.js`的fetch handler其實已經是network-first（2026-08-25就改
  好，`e.respondWith(fetch(...).then(...).catch(()=>caches.match(...)))`，
  先打網路成功就用網路版本，只有網路失敗才退回快取）——這部分沒有新bug。
- (a) `CACHE`常數改用時間戳格式（`alpha-v2026-08-28.0000`），並新增
  `.git/hooks/pre-commit`：**每次commit只要有動到`index.html`或`sw.js`，
  自動把兩者的版本號常數改成當下時間戳再重新git add**，不用手動記得改
  （使用者原話「每次commit自動更新」）。
- (b) 首頁底部新增版本號顯示（`#home-footer-version`，原本只有設定頁的
  「關於」卡片有，使用者要求要在「一進App就看得到」的地方也顯示），跟
  設定頁的App版本共用同一個`APP_VERSION`常數，載入當下就顯示（不用等
  使用者自己點進設定頁才觸發）。
- (c) `scripts/smoke_test.mjs`新增check 9：模擬「手機已裝舊版SW快取」
  情境（塞一份竄改過的假index.html進CacheStorage），驗證reload後畫面
  顯示的仍是真實版本、不是快取裡的假內容。
- (d) 全域錯誤收集（`#error-log`／`recordGlobalError()`）2026-08-27已存在
  且是全域、非分頁專屬、持續顯示（不是會自動消失的短暫橫幅）——查證後
  確認這部分已經滿足「使用者能截圖回報實際錯誤」的需求，不用重做。
- **誠實揭露殘留風險**：iOS Safari對PWA/Service Worker的更新檢查時機
  本身有已知的跨瀏覽器不一致行為（不是這份程式碼能單方面解決的），已經
  做的這幾層是「盡量降低問題再發生機率＋讓問題更容易被肉眼診斷」，不能
  100%保證去除；如果使用者手機下次還是卡住，**第一步先看首頁底部版本號
  是不是最新commit的時間戳**，不是最新代表SW更新真的卡住了（這時按設定頁
  「強制更新」或整個移除PWA捷徑重新加入），是最新版本號卻clock還是不動，
  才代表是新的程式碼bug需要重查。

**2. 所有重新整理按鈕都按不動**——診斷：實際測試（smoke_test.mjs新增
check 8：點擊後900ms內驗證有無觸發新的網路請求）發現4個「重新整理」按鈕
的onclick**其實都有正確觸發fetch**，不是繫結斷掉。真正問題找到了：
`home-updated-tm`／`market-updated-tm`這兩個「最後更新」時間戳欄位存在於
HTML、卻從來沒有任何JS寫入過（死欄位，永遠卡在`--:--`）——按下重新整理
後畫面沒有任何可見變化（沒有spinner、時間戳不會動），使用者從結果反推
「大概是壞了」完全合理。已修正：新增共用helper `refreshTap(el,tsElId,fn)`
——點擊時按鈕文字先變「更新中…」＋暫時不可再點，執行完成後更新對應的
「最後更新」時間戳＋跳toast確認，無論成功失敗都還原按鈕文字，4個重新整理
按鈕（今日/市場/主流題材/選股）全部改用這個helper。
**尚未做（下一輪繼續）**：pull-to-refresh手勢（使用者要求的(b)項）。

冒煙測試實際輸出（2026-08-28 00:09，`node scripts/smoke_test.mjs`，
含新增check 8/9）：
```
PASS - 1. 頁面載入無uncaught error/unhandledrejection
PASS - 2. 右上角時鐘interval在3秒內有執行：呼叫了4次
PASS - 3. 六個分頁都能切換且不拋錯
PASS - 4. 主要面板都有內容（不是完全空白）
PASS - 5. 市場頁三個市場切換都不拋錯
PASS - 6. 互動元素可點擊性（類股卡/選股排行列/自選股列）
PASS - 8. 重新整理按鈕點擊後都會觸發實際網路請求
PASS - 9. 模擬手機已裝舊版SW快取，驗證network-first不會被舊內容覆蓋
PASS - 10. 整個測試過程（含所有互動操作，含8/9新增檢查）結束後仍無累積的uncaught error
=== 冒煙測試結果：全部通過 ===
```

## ✅ UX走查第1輪（2026-08-28 03:25，夜間循環第4輪）

393×852截圖六個分頁+個股評分報告畫面，見`docs/UX_AUDIT.md`完整記錄。
**發現並修正UX-1**：選股頁「主流題材」空狀態訊息把「真的沒有產業符合
條件」跟「連線失敗」兩種語意用「或」糊成一句話，使用者看了不知道該不該
按重新整理——`FM_LAST_FAILED`其實已經能明確分辨，改成兩句各自獨立、
不含糊的訊息（`renderMainstreamChips()`）。其餘五頁+報告畫面沒發現新的
功能性bug；確認`loadStockInfo:fetch Failed to fetch`錯誤是本機網路
本身斷斷續續造成（同一晚`git fetch`也遇過DNS失敗），不是regression。

冒煙測試實際輸出（2026-08-28 03:22，`node scripts/smoke_test.mjs`）：
全部PASS（1/2/3/4/5/6/8/9/11/12）。

## 🌙 夜間自主循環規則（2026-08-28使用者裁示，使用者已就寢，記錄完整規則供每輪自己對照）

使用者原話（逐字記錄，不精簡）：
- 每30分鐘一輪（沿用AlphaMarathon同一套隱藏排程精神，但這是**這個互動session
  自己**用ScheduleWakeup自我排程，不是另開排程任務）。
- 每輪流程：1.讀BACKLOG.md挑最高優先的一項❌（一次只做一項）2.實作→跑冒煙
  測試→通過才commit push→更新BACKLOG 3. App內所有標示「未完成/未開發/建置中」
  的區塊依序納入開發，優先序＝使用者最常用頁面優先（今日→選股→市場→個股頁→
  交易→日誌→設定）4. 遇到「未解方向」（分析師目標價/FCF/期貨FinMind依賴等），
  每晚至少一輪專門研究替代解法（回退鏈原則：至少試三條路），結果寫進BACKLOG
  備註，可解就解、不可解寫明原因。
- 人因工程檢查點：每完成4輪（約2小時）做一次完整UX走查（393×852逐頁截圖，
  真實使用者視角檢查哪裡怪/不好用/壞掉/沒回饋），缺陷登錄BACKLOG（標
  UX-系列編號），嚴重的立即修，走查結果累積寫進`docs/UX_AUDIT.md`。
- 晨間報告（必做，早上07:00前）：產出`MORNING_REPORT.md`並commit，內容：
  1.昨夜完成清單（每項附commit hash+冒煙測試結果證據）2.版本號（使用者起床
  第一件事：對照App版本號確認手機吃到新版）3.時鐘與重整按鈕的修復驗證方式
  （使用者如何30秒內自行確認）4.未解方向調查結論 5.UX走查發現與已修/待修
  清單 6.今日建議優先序。
- 紀律不變：單一進行中、冒煙測試不過不commit、假資料零容忍、不碰holdout、
  不接真實下單、全程繁中。

## ❌ 待處理（依使用者2026-08-27/28指定順序：還原權息✅ → 重整/時鐘✅ →
歷史+量能深度 → 創新高 → 量價配合度 → B24選股驗證(PIT回測+翻倍率+前瞻台帳)
→ B16原有回測項目併入B24 → 其餘BACKLOG項目依App頁面優先序）

- **✅ pull-to-refresh手勢**（2026-08-28完成）：`#main`滾到最頂端時下拉
  超過64px門檻放開，觸發對應分頁（今日/市場/選股）的重整動作，跟
  `refreshTap()`按鈕共用同一套fmClearCache+hydrate*邏輯，指示器文字
  「↓下拉重新整理」/「↑放開重新整理」/「更新中…」。`scripts/smoke_test.mjs`
  新增check 11：合成touch事件模擬下拉手勢，驗證觸發實際網路請求。

  冒煙測試實際輸出（2026-08-28 00:14，`node scripts/smoke_test.mjs`，
  新增至12項）：全部PASS（1/2/3/4/5/6/8/9/11/12）。

- **✅ B24第一步：前瞻選股台帳picks_ledger.json（快照）已完成，回填為骨架**
  （2026-08-28完成，使用者原話「今晚就要開始累積快照，鐵律：只能事前快照
  嚴禁事後補建」——今晚2026-08-28已經開始累積，沒有再拖）：
  - `.github/scripts/build_picks_ledger.py`（新增）：讀三榜scores*.json，
    各取Top20（排除`rank=null`的流動性不足股票），配對`quotes_all_tw.json`
    的收盤價，寫進`data/picks_ledger.json`。**鐵律的具體實作**：
    `already_snapshotted()`保證同一個(board, snapshot_date)只會被快照
    一次，重跑這支腳本不會覆蓋既有快照。已掛進`.github/workflows/market.yml`
    （三榜產生完之後、commit之前）。
  - **本機實測抓到的真bug**：`future`板Top20第1名(6452)配對到的收盤價是
    `quotes_all_tw.json`裡2020-08-17的資料（6年前！同一種FinMind快取
    極度過期的根因，比B23發現的2024-12-31案例更嚴重）。已加守門：
    `price_date`比`snapshot_date`早超過10天就判定`price_stale=true`，
    `close_price`誠實記null，不塞錯誤價格污染之後的報酬率計算。今晚
    首次快照：value板1檔/future板2檔因此記為stale、其餘17-20檔正常。
  - **順便修正一個既有的生產環境真bug**：查core發現`market.yml`的
    commit步驟`git add`清單裡漏了`data/ex_dividend_events.json`——代表
    B23前一輪新增的除權息事件帳台，daily排程雖然有正確產生，卻從來沒被
    自動commit過（只有我本機手動commit過的那幾次才進repo），GitHub
    Actions每天跑完都會把這個檔案的異動丟棄。已一併補上，同時也把
    `data/picks_ledger.json`加進commit清單。
  - `.github/scripts/update_picks_ledger_returns.py`（新增，**骨架，未完整
    實作**，使用者原話「可以先設計、不用今晚就實作完」）：定義T+5/20/60/120
    回填的資料結構與待解問題（交易日曆怎麼算、大盤超額報酬公式），下一輪
    或後續輪次補上`_trading_days_after()`/`_lookup_price_on()`/
    `_lookup_taiex_on()`的實際邏輯再掛進market.yml排程。

  冒煙測試實際輸出（2026-08-28 01:47，`node scripts/smoke_test.mjs`）：
  全部PASS（1/2/3/4/5/6/8/9/11/12）。

- **B24：選股驗證——回答「到底選不選得到賺錢/翻倍的股票」**（2026-08-28
  使用者深夜追加，取代/併入原B16，優先序在B23量價因子鏈之後）：
  1. **PIT回測**（正式開工，凍結權重）：每月底只用「當時已知」資料算三榜
     （財報用公告日、營收用公布日，查到未來資料即該輪作廢）。**資料深度
     誠實聲明**：目前營收26個月/財報8季/價格260日，只夠回測約12-18個月，
     回測期要明確標示、不足以下長期結論。每月對三榜各取Top20，算後續
     1/3/6/12個月報酬。對照組（缺一不可）：(a)動態隨機對照1000次
     (b)加權指數同期 (c)對大盤回歸的alpha+顯著性。評判：Top20平均超額
     報酬對隨機分布的百分位、Sortino、MDD。
  2. **翻倍率指標**（使用者核心關切）：翻倍率=Top20中12個月內最高漲幅
     曾達+100%的檔數比例；大賺率=曾達+50%的比例；對照基準=隨機20檔的
     翻倍率分布（重點是「選中比例」是否顯著高於亂槍打鳥）；同時報告反面
     ——12個月跌超過-30%的比例（地雷率）。三榜分開算，好壞都要報告
     （例如預期動能榜翻倍率高但地雷率也高、價值榜相反，這個取捨要用
     數字呈現，不能只報好的一面）。
  3. **✅ 前瞻選股台帳快照已完成**（見上方「B24第一步」條目，今晚已開始
     累積），**回填腳本仍是骨架、App「選股成績單」UI區塊尚未實作**——
     這兩塊等回填邏輯做完、累積夠幾筆真實回填資料後再做UI，不然UI會是
     空的沒有意義。
  4. 結果寫入`research/REPORT.md`專章+`MORNING_REPORT.md`摘要：三榜各自
     超額報酬百分位、翻倍率vs隨機基準、地雷率、alpha顯著性。**如果結果是
     「沒有顯著優於隨機」，照實寫，那是下一輪改進因子的起點，不美化，
     禁止只挑好看的窗口報告**。
  - 未經使用者同意不得解鎖holdout（沿用B16既有前提）。
  尚未開始。



- **✅ 動能榜還原權息修正（P0，使用者回報，2026-08-27完成）**：
  `data/price_history.json`新增`adj_close`欄位（還原權息收盤價），
  `generate_scores_momentum.py`的`relative_strength`因子改用這欄，修正
  除息跳空被誤判成下跌、除息季系統性扭曲排名的bug。雙軌來源：一次性
  回補讀research端FinMind`TaiwanStockDividend`本機快取
  （`research/build_price_history.py`，繞開`load_dev()`/holdout機制，
  因為這是正式上線即時資料不是回測）；每日排程改讀TWSE官方
  `rwd/zh/exRight/TWT48U`除權息預告表累積事件、回溯調整
  （`.github/scripts/update_price_history.py`，新增`data/ex_dividend_events.json`
  帳本），刻意不在每日排程呼叫FinMind，維持JSON-only架構原則。
  **過程中親自抓到的真bug**：少數股票（1583/2227/2420/2753/4582/6216/
  6955/8442共8檔）的research端FinMind快取已經停在2024-12-31很久以前，
  導致「除權息日前一筆可用資料」抓到1年8個月前的舊收盤價當定錨，算出
  的調整係數完全不對——已加上守門（`MAX_PREV_CLOSE_GAP_DAYS=10`天），
  超過門檻就跳過不套用、記錄`skip_reason`，不會靜默套用錯誤係數。
  **已知殘留限制**：TWT48U只回傳未來約5週的事件預告，不支援歷史查詢，
  涵蓋率隨每天累積逐步提高，剛上線這幾週少數個股可能還沒回溯到。
  `index.html`動能榜disclaimer已更新註明還原權息狀態。

  冒煙測試實際輸出（2026-08-27 23:47，`node scripts/smoke_test.mjs`）：
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

- **B23進度（2026-08-28凌晨，本輪完成大半，🔄未完全結束見下方殘留項）**：

  **1. 歷史/量能深度延伸——過程中親自抓到一個嚴重真bug**：
  查證發現題材動能榜候選宇宙（2375檔）裡593檔`price_history.json`列數
  不足60列。修法演進（誠實記錄試過的路）：
  a) 先試TWSE官方`exchangeReport/STOCK_DAY`單股歷史日線——**本輪實測被
     反爬蟲整批擋下**（53檔測試全部428，不是間歇性），放棄。
  b) 改用FinMind**即時線上API**（不經過research端本機parquet快取，也
     不經過`load_dev()`/holdout——見`research/backfill_price_history_gaps.py`
     docstring說明取捨）——**成功補進177檔**，之後撞到FinMind免費額度
     （402 Payment Required，跟T86那種「反爬蟲封鎖」不同，是quota用盡），
     **416檔待下次額度重置後重跑**。

  **真bug（本機測試才發現，不是空跑）**：只看「列數是否≥60」不夠——列數
  足夠不代表這些列是「連續的最近60個交易日」。實測發現2337（旺宏）有90列
  卻是89列2024年舊資料+daily排程新增的1列2026年資料，中間20個月完全空白；
  用這種視窗算「創新高」因子算出荒謬的+375%（拿2024年20元跟2026年125元
  相減）。**全市場實測：2,270檔裡有1,649檔（超過七成！）的90列視窗裡都
  藏著這種日曆天缺口**——這代表原本已經上線的`relative_strength`因子
  （用`closes[-60]`）可能一直在對大多數股票算出不可靠的60日報酬率，
  只是沒人發現。已修正：新增`_has_calendar_gap()`守門（日曆天跨度>列數
  3倍就判定混進不連續舊資料），套用到`relative_strength`/`volume_breakout`/
  `new_high_breakout`/`volume_price_coordination`全部四個依賴價量視窗的
  因子——資料不夠可靠寧可回傳None（該因子這檔股票就不計分，反映在
  `missing_factors`），不硬算一個可能是假訊號的數字。修正後
  `new_high_breakout`覆蓋率525/2370、`volume_price_coordination`
  534/2370（誠實的低覆蓋率，不是虛高但錯誤的覆蓋率）。
  **殘留待辦（🔄下一輪繼續）**：用修正後的缺口判定重新統計，實際需要
  回補的股票是**1,850檔**（比原本593檔的估計大很多，因為原本的判定
  漏抓了「列數夠但有缺口」這類case）。FinMind額度何時重置未知，下一輪
  先測小批量是否已恢復，恢復就繼續分批回補；沒恢復就記錄等待，不要
  硬打浪費時間。

  **2. 創新高因子（new_high_breakout）已完成**：近60日內價格創階段高，
  用adj_close（還原權息收盤價）避免除息跳空誤判，含上述日曆缺口守門。

  **3. 量價配合度因子（volume_price_coordination）已完成**：使用者原話
  a-f全部規則實作（吸收比/量能梯度/回檔量縮/價漲量縮背離/高檔爆量不漲/
  派發訊號），含警語標籤(⚠️高檔爆量滯漲/量價背離/下跌放量)反映在
  `flags`。創新高＋量價配合度聯動：創新高但量價配合度為負，創新高分數
  打3折（使用者原話「不讓假突破拿高分」）。門檻全部經驗值，UI已標
  「參數未驗證」，`weights_frozen_momentum.json`重新分配權重
  （relative_strength 0.16/volume_breakout 0.10/new_high_breakout 0.10/
  volume_price_coordination 0.12，四者合計0.48≤55%上限；
  chip_concentration 0.20/group_breadth 0.14/sector_capital_flow 0.18）。

  冒煙測試實際輸出（2026-08-28 01:08，`node scripts/smoke_test.mjs`，
  第一次跑check 1 FAIL是網路瞬斷讀取FinMind失敗，重跑確認是暫時性、
  非程式碼regression，第二次全部通過）：全部PASS（1/2/3/4/5/6/8/9/11/12）。

- **B23殘留待辦（因子本身已完成，見上方「B23進度」條目）**：
  1. 用修正後的`_has_calendar_gap()`缺口判定重新統計出的1,850檔待回補
     股票，`research/backfill_price_history_gaps.py`已可重跑。02:38那輪
     撞到FinMind「ip banned」已中止；**03:12這輪封鎖已解除，測試性跑了
     保守的80檔小批量**——但跟同時在跑的B24 PIT回測（也需要FinMind額度
     載入research樣本）搶同一份共用額度，80檔裡只有約24檔真的成功補進
     （其餘56檔406/402額度用盡，例如1101這檔已確認補到完整90天連續
     資料）。**教訓：FinMind額度是共用的，不要同時跑多個會打FinMind的
     工作**，下次要嘛錯開時間、要嘛先確認沒有其他工作在佔用額度。剩餘
     約1,826檔待之後分批繼續，且不要跟其他FinMind工作同時跑。

     **04:20這輪：獨立跑（不跟其他FinMind工作搶），過程中又抓到一個真
     bug**——`main()`原本判斷「有沒有補到」只看「列數是否增加」，但很多
     目標股票本來就已經在90列的cap上（只是內容有巨大日曆缺口），補齊
     缺口後列數不會變多（還是90列，只是從「充滿缺口」變成「真正連續」），
     這種最主要的價值案例反而被誤判成「無增益」而不計入`backfilled`
     計數——已修正成同時看「列數增加」或「缺口狀態改善」才算真的有補到
     （實際寫入`prices[code]`的資料本身一直是對的，只有計數/回報的統計
     數字被低估，不影響資料正確性）。已用修正後的計數邏輯獨立重跑
     （不跟B24搶額度），跑在背景，下一輪確認結果。
  2. B16回測時要對量價配合度/創新高的門檻參數（1.3倍/2.5倍/0.7/0.6/
     80百分位等）做±30%敏感度掃描，只有單點有效就判定為過擬合。

- **🔄 B24 PIT回測（價值成長榜，2026-08-28凌晨開工中）**：新增
  `research/run_value_board_v2_pit_backtest.py`——重用既有驗證框架
  （`run_score_backtest.py`同一套`backtest/engine.py::run_backtest()`機制、
  `portfolio_backtest_v2.py`同一套alpha/beta回歸公式、
  `benchmark_taiex_stats.py`同一套TAIEX買進持有MDD/Sortino公式），訊號
  函式換成`score_v2.py::compute_scores_v2()`（=App目前正式上線的價值
  成長榜八大因子FACTOR_DEFS）。月度再平衡(21交易日)、持股20檔、全成本、
  對照組含隨機draws(機制驗證先用30次，非最終1000次)+買進持有大盤、
  alpha/beta回歸。**重要澄清**：走research端`factor_ic.py`既有100檔樣本
  （2010年起，FinMind歷史parquet快取），有10年以上可用歷史，不受使用者
  原本假設的「App JSON路徑12-18個月」限制——這是好消息，統計檢定力更高。
  全程只用`load_dev()`（cap在VAL_END=2024-12-31），`run_backtest()`本身
  結構性擋掉holdout洩漏，**未經使用者同意不解鎖holdout**（這代表這次
  回測回答「這套因子在2015-2024歷史資料上能否穩定打敗大盤」，不是
  「App最近幾個月的實際表現」，後者需要holdout解鎖）。

  **本輪嘗試執行時撞到真狀況**：跑到一半發現FinMind回傳
  `{"msg":"ip banned","status":403,"retry_after":1315}`——這台機器這幾輪
  （B23的177+416檔回補+這輪重跑1,850檔）對FinMind的請求量觸發了臨時IP
  封鎖（比402額度用盡更嚴重，是官方主動封鎖，附倒數1315秒≈22分鐘）。
  已立即停止所有FinMind呼叫（含B23殘留回補的重跑，也一併中止）。**這支
  回測腳本本身尚未被完整跑過一次驗證**（懷疑是`score_v2.py::
  compute_scores_v2()`裡的`_revenue_yoy_latest()`每個as_of日期、每檔股票
  都呼叫一次`month_revenue_pit()`，在banned期間每次呼叫都要熬過3次重試
  backoff才失敗，導致嚴重拖慢——這是既有score_v2.py的設計特性，不是這輪
  新引入的bug，但拿來做「上千次rebalance×30次random draws」規模的回測時
  第一次暴露出這個效能問題）。
  **03:12這輪追蹤結果**：封鎖已解除。逐步測試發現「卡住」其實不是bug，
  是`factor_ic.py::load_sample_with_factors()`對每檔股票的
  `prepare_factors()`本身就要約12-13秒（真實運算：15年技術指標+法人
  流量滾動窗口，不是網路請求卡住）——100檔樣本單純載入資料就要約22分鐘，
  是一次性成本（後面62次回測跑合(2期×(1真實+30隨機))都是對已載入記憶體
  資料做運算，不會重複付這個22分鐘）。已重新啟動完整跑（含VALIDATION期
  +30次random draws），跑到這輪結束時仍在載入階段，尚未跑完，下一輪繼續
  等待/檢查結果。**上一輪誤判為「FinMind封鎖導致卡住」而提前kill掉的
  那次，很可能其實只是這個22分鐘的正常載入時間，不是真的卡住**——這輪
  學到教訓：往後對這類腳本要有耐心等超過20分鐘再判斷是否真的異常。

  **03:45這輪：第一次機制驗證跑完整跑完，結果出爐（使用者原話「如果結果
  是沒有顯著優於隨機，照實寫，那是下一輪改進因子的起點，不要美化」，
  以下逐字照實記錄，不加修飾）**：

  | 期間 | 策略報酬 | 買進持有 | 策略MDD | 大盤MDD | 策略Sortino | 大盤Sortino | alpha(年化) | alpha顯著 | 隨機對照百分位(30次) |
  |---|---|---|---|---|---|---|---|---|---|
  | TRAIN 2015-2020 | **-1.03%** | +58.86% | -46.61% | -28.72% | 0.278 | 0.756 | +4.96% | 否(p=0.82) | **0.0（墊底）** |
  | VALIDATION 2021-2024 | **-1.06%** | +54.58% | -48.44% | -31.63% | 0.159 | 0.942 | -3.67% | 否(p=0.81) | **0.0（墊底）** |

  **結果很差，誠實記錄**：策略兩期都小賠(-1%上下)，同期買進持有大盤都
  賺超過50%；策略的MDD比大盤還深、Sortino比大盤還差；alpha不顯著（甚至
  VALIDATION期是負的）；**30次隨機對照組draws裡，真實策略的最終權益連
  最差的隨機組都贏不了（百分位0.0，敬陪末座）**——這個結果如果成立，
  代表App目前正式上線的價值成長榜八大因子組合，不但沒有選股能力，反而
  系統性地選到比隨機亂選還差的股票。

  **在完全採信這個結果之前，這輪多做了一個誠實的自我懷疑動作**：兩期
  報酬率驚人地接近（-1.03% vs -1.06%），橫跨完全不同的市場環境（TRAIN
  跨6年多頭+2020疫情崩盤反彈、VALIDATION跨4年不同景氣循環），這麼接近
  的數字有點可疑，值得先排除「腳本本身有bug」的可能性，不要急著把這個
  當成最終定論。已經：(a) 幫`run_value_board_v2_pit_backtest.py`加上
  本地pickle快取（`research/data/backtests/value_board_v2_sample_cache.pkl`），
  把100檔樣本+因子的載入時間從每次22分鐘降到之後重跑只要幾秒，方便
  之後反覆做sanity check不用每次乾等；(b) 已另外啟動一輪用快取跑的
  背景任務，準備做sanity check（例如檢查`make_score_v2_signal_fn()`在
  幾個抽樣日期是不是真的選出合理數量、看起來正常的Top20名單，不是
  因為某個bug讓資格池長期是空的、變相全程空手不投資才導致這種接近0%
  但略負的報酬率）。

  **04:10這輪：sanity check做完，找到一個重大方法論問題——上一輪「-1% vs
  +55%」的結果很可能主要不是「因子選股能力差」，而是「回測設定本身有
  結構性的現金拖累」，必須大幅修正解讀，不能直接採信上一輪的結論**：

  抽樣檢查`make_score_v2_signal_fn()`在多個再平衡日實際選出的合格股票數
  （用剛建好的pickle快取，秒級重跑），發現：**合格股票池（通過流動性
  門檻）平均只有約11.5檔（抽樣20個季度時間點，範圍0~18檔），從來沒有
  一次達到20檔的目標持股數**。根因：`factor_ic.py`的100檔樣本
  （`SAMPLE_SIZE=100`）原本是設計給「因子IC統計檢定」用的驗證樣本，不是
  為了支撐「20檔實際持股組合」設計的完整可投資宇宙——扣掉流動性門檻後，
  能打進排名的股票經常只有10檔左右。而`backtest/engine.py`的
  `slot_allocation = initial_capital / max_positions`是**固定除以20**，
  不會因為當天只選得出10檔就自動把資金集中投入那10檔——代表**平均約
  40-45%的資金整個回測期間都閒置在現金、完全沒有投入市場**，這對「策略
  報酬 vs 100%投入的買進持有大盤」這種比較是結構性不公平的比較，不是
  在測試「選股能力」，主要在測「現金拖累有多大」。

  **同時發現並修正一個真bug（sanity check時當場crash抓到的）**：
  `compute_scores_v2()`在某些as_of日期（樣本裡完全沒有股票有資料）會
  回傳零欄位的空DataFrame（跟`adjust.py`/`build_price_history.py`之前
  修過的同一種陷阱），`make_score_v2_signal_fn()`沒擋住的話
  `cs.sort_values("total_score",...)`會直接`KeyError`讓整支腳本中止
  ——已修正成這種情況誠實回傳空dict（=當天沒有新持倉建議）。

  **對隨機對照組「百分位0.0」這個數字的額外保留**：因為`make_random_
  signal_fn()`在合格池<20檔時就是「直接全拿」（跟真實策略在同一天選的
  很可能是同一批股票，因為都只有那10幾檔可選），這代表很多再平衡日的
  「真實 vs 隨機」比較根本沒有真的隨機到——這進一步削弱了上一輪「墊底」
  這個結論的可信度，不是可以直接拿來用的統計證據。

  **結論：上一輪的具體數字（-1.03%/-1.06%、alpha不顯著、百分位0.0）
  先保留、不能當成「App正式上線的價值成長榜選股能力差」的證據**——這
  是一次不夠格的測試設計，不是策略本身的診斷。**正確的下一步（留給
  之後的研究輪次，不是今晚能做完的量）**：需要一個明顯更大的可投資
  股票池（例如至少300-500檔，涵蓋流動性門檻後仍能穩定填滿20個持股
  名額），重新跑這整套PIT回測，數字才有意義。這需要對更多股票重新跑
  `prepare_factors()`（每檔約13秒，300-500檔預估要65-110分鐘的一次性
  載入成本，比100檔貴很多，且可能需要更多FinMind即時資料觸發額度/
  反爬蟲風險），建議留到使用者醒來後決定要不要投入這個量級的運算再做，
  不要在使用者不知情的狀況下夜間就把時間/API配額燒在這上面。這輪的
  30-random-draws背景任務讓它自然跑完（不特地中止，數字還是留作記錄，
  但務必附上以上這整段警語，不能被誤讀成定論）。

- **B16（P0）：價值成長榜+題材動能榜+未來性濾網都必須各自回測驗證**
  （2026-08-27提升為P0；2026-08-27【驗證帽】本輪查證進度：**已確認前置
  障礙，記錄進`research/TRIALS_LEDGER.md`「待測」區塊，尚未執行任何統計
  檢定**）：
  - 明確交易規則：換股頻率、持股檔數、進出場、停損、單檔上限、全成本。
  - 三個必要對照：(a) 動態隨機對照組（每次再平衡從當期可交易宇宙隨機抽
    同檔數，跑1000次取分布）；(b) 買進持有加權指數；(c) 對大盤回歸的
    alpha(截距)、beta、alpha統計顯著性。
  - 評判順序：淨利與MDD達標 → Sortino → alpha顯著 → 夏普最後 → 勝率不看。
  - 未經使用者同意不得解鎖holdout（本輪確認`is_holdout_consumed()=False`，
    未消耗，`TRAIN_END=2020-12-31`／`VAL_END=2024-12-31`）。
  - 在回測完成前，三榜頁面都已固定顯示「本榜為資料排序，尚未經過組合
    策略回測驗證，不代表能贏大盤」（已完成，見上方✅）。
  - **本輪查證發現的真正前置工作**：`generate_scores_momentum.py`/
    `generate_scores_future.py`是JSON-only上線路徑，讀的是即時累積快照
    （只有幾天到90天歷史），不是`TRIALS_LEDGER.md`既有框架用的2010-2024
    歷史parquet資料——回測前必須先在research/建一套「用歷史FinMind快取
    重算這10個新因子」的管線（比照`factors.py::prepare_factors()`模式），
    才能套進既有的`_permutation_test()`/Bonferroni累積校正框架。這塊
    工作量不小於這兩支JSON-only腳本本身，是**研究帽**的SPEC/因子產出，
    不是驗證帽這輪能直接做的事——不會為了求快另開一條簡化捷徑，那樣
    違反CLAUDE.md九「做與判分離」鐵律。
  - 下一步：切換到**研究帽**，實作歷史因子重算管線；完成後才能回到
    **驗證帽**跑真正的統計檢定。

- **B18：未來性濾網 (b)類因子（需事件資料，等新聞管線）**（2026-08-27
  登錄）：打進大廠供應鏈/接獲大額訂單（MOPS重大訊息/SEC 8-K）、訂單能見度
  （法說會逐字稿關鍵詞）。**依賴B19（訊號台帳骨架）跟`docs/Alpha_新聞與
  供應鏈連動_設計小抄.md`既有規格（`news_fetch.py`/`supply_chain.json`/
  `news.json`，2026-08-23已設計但尚未實作）先完成，才能有事件資料可用。**
  尚未開始。

- **B20：未來性濾網 (c)類因子（質性研判，AI閱讀後給結論）**（2026-08-27
  登錄）：是否為關鍵瓶頸環節、是否具不可替代性、獨角獸潛力。**規則
  （使用者原話，逐字照抄）**：必須標「AI研判，非量化驗證」，附推理依據
  與出處，且**不計入量化總分**，另闢區塊呈現。尚未開始，依賴B18的事件
  資料/供應鏈圖作為AI研判的輸入素材。

- **B19：訊號管線骨架（依market-signal-vetting方法）**（2026-08-27登錄，
  P0後次順位，`未來性濾網(a)`完成後開始）：
  1. 來源分層：L1官方申報／L2公司自述／L3專業媒體／L4社群。L4單獨出現
     不得影響任何評分，只能標「待驗證線索」。
  2. 交叉驗證：升格為訊號需滿足其一——有L1/L2對應公告、兩個以上獨立
     來源、或自有資料佐證（法人買超/量能/財報對得上）。
  3. 已反映偵測：計算`run_before`與消息前的量能異常，>15%先漲或消息前
     爆量→標警語並降權（跟`docs/Alpha_新聞與供應鏈連動_設計小抄.md`第三節
     的割韭菜偵測邏輯完全一致，2026-08-23已設計、尚未實作，這次要真的
     做出來）。
  4. **`data/signal_ledger.json`（前瞻追蹤台帳，鐵律）**：每個訊號【事前】
     寫入（ID/時間戳/來源層級/來源識別/類型/標的/當時價/已反映判定），
     由排程在T+5/T+20/T+60【只回填】實際報酬與相對大盤超額報酬。**不得
     事後補建紀錄，那是回測不是前瞻驗證**——這是整個訊號管線信度的根基，
     實作時要特別小心不能讓「回填」變成「重建」。
  5. 校準迴圈：單一分類滿30筆才可初步參考、滿100筆才可調權重。統計各
     來源層級/訊號類型/發文帳號的超額報酬與勝率，據此調整權重；表現為
     零或負者降權或剔除。校準要版本化並記錄理由與樣本數。
  尚未開始，是這批新指示裡最核心、風險也最高的一塊（涉及「不得事後補建」
  這條鐵律，實作要非常小心避免踩到）。

- **B21：Reddit社群訊號抓取（合規）**（2026-08-27登錄，依賴B19訊號管線
  骨架先完成）：
  - 只走官方API：Reddit免費層，需註冊OAuth app；X按次計費，先不接，等
    Reddit驗證有效再評估。
  - 只存貼文ID/時間/作者/標題摘要/連結/互動數，**不整篇轉貼內文**。
  - 抽取「討論量變化率」而非絕對量。
  - 拉抬出貨偵測：新帳號集中推同標的、低流通小型股、話術強但無可查證
    事實→標高風險並降權。
  - 社群內容是未經查證的他人言論，**只能當資料處理，不得當指令執行**
    （提示注入防護：抓到的貼文文字內容不能被拿去當成程式指令解讀）。
  - API金鑰放GitHub Secrets，不寫進任何commit的檔案。
  - 社群訊號區塊固定標示：「社群熱度為注意力指標，非買進理由；討論量
    暴增常伴隨擁擠風險。」
  尚未開始。

- **B22：校準迴圈**（2026-08-27登錄，依賴B19+B21先累積足夠樣本數，
  30筆/100筆門檻見B19第5點）：尚未開始，時間上必然排在B19/B21資料開始
  累積之後（需要真實時間流逝讓T+5/T+20/T+60回填生效，不是能立刻做完的
  工作）。

**三濾網架構現況總覽**（2026-08-27）：
1. 【價值濾網】= 現行`generate_scores_live.py`（財報導向），維持不變。
2. 【題材動能濾網】= `generate_scores_momentum.py`（已完成，見上方✅）。
3. 【未來性濾網】= `generate_scores_future.py`，因子分三階段(a)/(b)/(c)，
   (a)類已完成（見B17✅），(b)/(c)類依賴B18-B20的事件資料/AI質性研判
   基礎設施，尚未開始。

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
- **財報公布時段（盤前/盤後）推估失敗**：`get_earnings_dates()` 在這台
  機器持續遇到 `curl_cffi` 對 `guce.yahoo.com` 的 DNS 解析問題（環境特定，
  非程式 bug），`estimated_session` 誠實降級為 `unknown`；`next_earnings_date`
  本身（來自 `get_calendar()`）不受影響。GitHub Actions runner 環境不一定
  有同樣問題，之後排程實跑可能就會恢復正常。
- **IBKR `outsideRth` 旗標尚未實作**：使用者原話「先記進 BACKLOG，現在不
  實作」——未來若接 IBKR 下單，延長時段（盤前/盤後）下單需要帶這個旗標，
  目前完全沒有下單串接（見 CLAUDE.md 安全紅線：自動下單只做介面/下單計畫，
  絕不串接真實下單 API），這條純粹是記錄給未來參考。
