# FIRST_HAND_SOURCES.md — 全網第一手公開源極限盤點（源頭二.1）

> 2026-09-15建立，依總司令2026-09-06【源頭二】裁示原話：「所有合法方法都試盡，
> 別人拿得到的第一手公開資料我們全部自己接。」`PENDING_QUEUE.md`「源頭二」節。
>
> **本檔案的範圍界線**：這是**盤點**（源頭二.1）——把repo裡已經查證/已經在用/
> 完全沒碰過的現況如實列出，**不是**逐項重新對外實測連線（那是源頭二.2的工作，
> 本輪未執行任何新的對外請求，全部是本地repo內既有紀錄的整理）。已有查證結論
> 的一律引用既有文件（主要是`docs/DATA_SOURCE_MAP.md`），不重複查一次。

---

## ⚠️ 本輪盤點時發現的重大問題（優先讀這段）

**`mopsov.twse.com.tw`（MOPS 查詢頁後端）robots.txt 與四支既有生產程式衝突，
且已用來回填了真實資料到 App 使用中的功能——這件事需要總司令裁示，本檔案
只誠實記錄，不擅自處理（不刪資料、不停用程式）。**

`docs/DATA_SOURCE_MAP.md`（查證日2026-09-08）已判定：

```
GET https://mopsov.twse.com.tw/robots.txt   → HTTP 200

User-agent: *
Disallow: /

User-agent: bingbot
Allow: /mops/web
```

**除bingbot外，全站`Disallow: /`。我們的程式不是bingbot，因此`mopsov.twse.com.tw`
（含`/mops/web/...`路徑）不得程式取用**——這是`docs/DATA_SOURCE_MAP.md`「🔴
走不通：MOPS公開查詢頁」小節的原文結論。

但repo裡有**四支已經在跑、且已回填真實資料**的程式直接打這台主機：

| 程式 | 建立日 | 端點 | 用途 | 是否早於09-08發現 |
|---|---|---|---|---|
| `research/mops_insider_holdings_client.py` | 2026-09-06 | `POST .../mops/web/ajax_stapap1` | 董監持股，已backfill、已做pilot IC | 是（早2天） |
| `research/mops_buyback_client.py` | 2026-09-06 | `POST .../mops/web/ajax_t35sc09` | 庫藏股公告，已backfill回溯至2015年 | 是（早2天） |
| `research/mops_cb_conversion_price_client.py` | 2026-09-07 | 兩段式AJAX `.../ajax_t108sb08_1_q2`→`.../ajax_t108sb08_1` | 可轉債轉換價 | 是（早1天） |
| `research/mops_material_news_client.py` | 2026-09-08 | `.../mops/web/t05st01`+`ajax_t05st01` | 重大訊息全類別，供`material_news_classify.py`等一系列事件研究使用 | **否，同日或稍晚**（`DATA_SOURCE_MAP.md`該筆記錄08:19寫入，此檔案22:01建立） |

四支程式的原始碼裡都**沒有任何一行提到robots.txt或這個合規疑慮**——不是
「查過覺得沒問題」，是查證這件事本身沒有發生在寫這些程式的當下。

**為什麼這件事重要**：
1. `CLAUDE.md`「取得方式鐵律」明文：「資料只走官方公開端點與已授權來源；
   任何需繞過驗證碼、登入牆、付費牆或速率封鎖的取得方式一律禁止，不論是否
   對外使用」——robots.txt的`Disallow`是網站方明確表達的存取意思表示，
   性質上跟這條鐵律要防的事是同一類。
2. 這不是「以後不要用」就結案的問題——**已經回填的資料現在被下游功能使用**
   （董監持股pilot IC、庫藏股`buyback_car_gate.py`、重大訊息一系列事件研究
   `material_news_car_gate*.py`等），停用程式不會讓已經產出的資料/結論消失。
3. `docs/DATA_SOURCE_MAP.md`對同一主機的另一個路徑（`t05st03`等查詢頁）已經
   給出處理原則：「除bingbot外，全站`Disallow: /`，我們不是bingbot，因此
   MOPS查詢頁不得程式取用」，但**沒有人回頭比對這條結論跟已經寫好的四支
   client程式是否衝突**——這正是本輪盤點意外抓到的落差。

**本輪決定**（誠實記錄，不繞過）：
- **不停用、不刪除這四支程式或其產出的資料**——那本身是一個需要總司令裁示
  的決定（要不要保留已收集資料、要不要去信申請書面授權、要不要改找替代
  來源），不是自走流程可以自行判斷的事。
- **本檔案如實記錄現況，「官方是否允許程式存取」欄位對這四項一律標🔴**，
  不因為「已經在用」就美化成🟢。
- 本輪結束時會呼叫`dev_queue_runner.py block`把這件事提到總司令面前，
  暫停自走佇列，不繼續做源頭二.2（避免在同一個未解決的合規問題上繼續
  疊加更多對這台主機的請求或更多下游功能）。

---

## 台灣

### 1. 期交所大額交易人未沖銷部位

| 欄位 | 內容 |
|---|---|
| 機構 | 台灣期貨交易所（TAIFEX） |
| 我們現況 | 🔴 查證過、**免費層不可行**。走的是FinMind `TaiwanFuturesOpenInterestLargeTraders`，`PROGRESS.md:6451`記載「確認真的要收費、免費方案拿不到」。`data/STATUS.json`列為P2待辦：「需人工查閱TAIFEX網站」找官方原生端點。 |
| 官方是否允許程式存取 | 未查證TAIFEX原生端點（只查過FinMind中介層） |
| 對應機構用途 | 集中大額交易人的未沖銷部位監控（防止過度集中） |
| 後續 | 待查TAIFEX官網是否有原生開放資料端點，不假設FinMind收費層等於官方也收費 |

### 2. 三大法人期貨選擇權買賣

| 欄位 | 內容 |
|---|---|
| 機構 | 台灣期貨交易所（TAIFEX），經FinMind中介 |
| 端點 | FinMind `TaiwanFuturesInstitutionalInvestors`（`data_id=TX`） |
| 我們現況 | 🟡 **已整合，但非直連官方**。`research/fut_probe_institutional_positions.py`查證、`fut_cheap_gate.py`已用於期貨籌碼卡。歷史範圍實際從2018-06-05起（非預期的2000-01-01），可用樣本1605天。`data/STATUS.json`列「脫離FinMind」為P2未完成待辦。 |
| 歷史回溯 | 2018-06-05起（FinMind中介層限制，非TAIFEX官方限制） |
| 官方是否允許程式存取 | 未查證TAIFEX官方原生端點；FinMind中介層本身允許 |
| 對應機構用途 | 三大法人（外資/投信/自營商）期貨部位方向性監控 |
| 後續 | 選擇權買賣部分（非期貨）未見對應查證，需另查 |

### 3. 選擇權未平倉與 Put/Call 比

| 欄位 | 內容 |
|---|---|
| 機構 | 台灣期貨交易所，經FinMind中介 |
| 端點 | FinMind `TaiwanOptionDaily` |
| 我們現況 | 🟡 **已整合，非直連官方**。`research/option_pcr_gate.py`／`option_oi_pcr_gate.py`／`option_pcr_overlay_v1.py`皆用此資料集，已完成`#69`（未平倉量PCR）假設測試（FAIL，見`data/signal_status.json`）。`PROGRESS.md:6441`提到曾因FinMind免費層限制一度拿掉。 |
| 官方是否允許程式存取 | 未查證TAIFEX官方原生端點 |
| 對應機構用途 | 選擇權市場情緒（避險需求/投機部位）監控 |

### 4. 證交所外資持股比率（MI_QFIIS）

| 欄位 | 內容 |
|---|---|
| 機構 | 臺灣證券交易所（TWSE） |
| 端點 | `https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=YYYYMMDD&selectType=ALLBUT0999&response=json`（`.github/scripts/fetch_foreign_holding.py`） |
| 我們現況 | 🟢 **已整合（2026-09-15，源頭二.3第1名）**。寫入`data/foreign_holding.json`，掛在`market.yml`每日排程；個股頁「籌碼」分頁新增「外資持股比率」卡（`fh-ratio`/`fh-can-invest`），已用Playwright實測2330顯示69.23%（2026-09-14資料日，與同日集保/T86資料合理對得上）。 |
| 已知地雷 | `selectType=ALL`回傳0筆，須用`selectType=ALLBUT0999`才有逐股資料（2026-09-15實測踩到，已寫進腳本docstring） |
| 官方是否允許程式存取 | 🟢（`www.twse.com.tw`主站範圍內，同T86/MI_MARGN/TWTASU/BFIAUU家族） |
| 對應機構用途 | 個股外資持股水位監控（外資是否加碼/減碼） |

### 5. 借券賣出餘額

| 欄位 | 內容 |
|---|---|
| 機構 | TWSE／TPEx |
| 候選端點 | TWSE openapi `/SBL/TWT96U`（查證結論：是「餘量」非「成交費率」）、`exchangeReport/TWT93U`（`BACKLOG.md:125`記錄的候選）；TPEx openapi `/tpex_margin_sbl`、`/tpex_short_sell`（`research/tpex_openapi_scan_c51.txt`列出，未逐一測試） |
| 我們現況 | 🟡 **查證中，未整合**。`HYPOTHESIS_QUEUE.md:8455-8462`已查過`/SBL/TWT96U`但發現欄位語意不是我們要的。`PENDING_QUEUE.md`「源頭一.2b」仍是`- [ ]`未完成：「查TWSE/TPEx官方借券端點文件，確認免費可得後接入」。 |
| 官方是否允許程式存取 | TWSE/TPEx openapi本身🟢允許（見下方「共通結論」），但尚未鎖定正確端點 |
| 對應機構用途 | 融券市場活動監控、借券成本推估 |

### 6. 處置股與注意股公告

| 欄位 | 內容 |
|---|---|
| 機構 | TWSE／TPEx |
| 候選端點 | TWSE openapi `/announcement/punish`（僅8筆近期快照，無歷史查詢）、TPEx openapi `/tpex_disposal_information`／`/tpex_esb_disposal_information`（僅18筆近期快照，同樣無歷史區間參數） |
| 我們現況 | 🔴 **已查證，判定資料不可及，FAIL結案**（假設#47，見`research/STRATEGY_GRAVEYARD.md:1917`、`research/TW_STATE_ARCHIVE.md:169`、`research/TW_LOG.md:2044-2057`完整查證過程）。FinMind對應dataset為付費層。 |
| 官方是否允許程式存取 | 端點本身🟢允許存取，但**只回傳近期快照、無歷史區間可回溯**，無法支撐事件研究 |
| 對應機構用途 | 警示異常交易個股（處置/注意股）供投資人注意 |

### 7. 當日沖銷（當沖）

| 欄位 | 內容 |
|---|---|
| 機構 | TWSE |
| 端點 | `https://www.twse.com.tw/rwd/zh/afterTrading/TWTASU`（官方，`research/twse_day_trading_client.py`） |
| 我們現況 | 🟢 **已整合**。`backfill_day_trading_ratio.py`／`backfill_day_trading_detail.py`已回填。`PENDING_QUEUE.md`「源頭一.2c」沿用此端點。另有研究腳本走FinMind `TaiwanStockDayTrading`，但該dataset免費層要收費，實際生產路徑走TWSE官方版本。 |
| 格式 | JSON（TWSE官方RWD端點慣例格式） |
| 官方是否允許程式存取 | 🟢（TWSE主站robots.txt除`/epaper/`、`/FTSE/`外全部允許，見`docs/DATA_SOURCE_MAP.md`） |
| 對應機構用途 | 監控當沖比重異常（防過度投機） |

### 8. 鉅額交易

| 欄位 | 內容 |
|---|---|
| 機構 | TWSE |
| 端點 | `https://www.twse.com.tw/rwd/zh/block/BFIAUU?date=YYYYMMDD&response=json`（官方，`research/twse_block_trade_client.py`） |
| 我們現況 | 🟢 **已整合**。`backfill_block_trade.py`回填，`block_trade_gate62.py`已完成假設`#62`測試（FAIL，見`data/signal_status.json`）。 |
| 官方是否允許程式存取 | 🟢（同上，TWSE主站範圍內） |
| 對應機構用途 | 大額配對交易揭露，監控機構級部位調整 |

### 9. MOPS 內部人持股轉讓事前申報

| 欄位 | 內容 |
|---|---|
| 機構 | 公開資訊觀測站（MOPS） |
| 候選端點 | TWSE openapi `/opendata/t187ap12_L`（已轉讓）／`t187ap13_L`（未轉讓）——**只回傳最新單一批次快照，無歷史區間參數**（`HYPOTHESIS_QUEUE.md:4373-4393`）。嘗試猜測MOPS互動查詢頁功能代碼（`t05st07`／`t34sc01`／`t108sb01`）**全部連線被拒**，未找到正確代碼 |
| 我們現況 | 🟡 **查證過、尚未確認可行** |
| 官方是否允許程式存取 | openapi快照端點🟢允許但功能不足；互動查詢頁**未確認代碼、亦適用下方⚠️robots.txt疑慮** |
| 對應機構用途 | 內部人（董監/大股東）計畫轉讓股票的事前揭露，防內線交易 |

### 10. 董監持股 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | `POST https://mopsov.twse.com.tw/mops/web/ajax_stapap1`（`research/mops_insider_holdings_client.py`） |
| 我們現況 | 🔴/🟡 **已整合（含pilot IC驗證），但落在`mopsov.twse.com.tw`robots.txt「除bingbot外全站Disallow」的衝突裡**，見本檔案最上方【重大發現】 |
| 格式 | JSON（AJAX回應） |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許**（見上方重大發現） |
| 對應機構用途 | 董監事持股比例揭露，防公司派掏空/內線 |

### 11. 庫藏股 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | `POST https://mopsov.twse.com.tw/mops/web/ajax_t35sc09`（`research/mops_buyback_client.py`），回溯至2015年 |
| 我們現況 | 🔴/🟡 **已整合**（`buyback_car_gate.py`已用於庫藏股事件研究），同樣落在robots.txt衝突裡 |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許** |
| 對應機構用途 | 公司買回自家股份公告，市場信心訊號 |

### 12. 可轉債轉換 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | 兩段式AJAX：`GET .../t108sb08_1_q2`→`POST .../ajax_t108sb08_1_q2`→`POST .../ajax_t108sb08_1`（`research/mops_cb_conversion_price_client.py`） |
| 我們現況 | 🔴/🟡 **已整合但僅驗證單一(市場,年月)組合，未做多年份回填**，同樣落在robots.txt衝突裡 |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許** |
| 對應機構用途 | 可轉債轉換價格調整揭露 |

### 13. 私募

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 我們現況 | **⚪ 未獨立查證**，只作為關鍵字併入「重大訊息」新聞分類（`research/material_news_classify.py:55,97`把「私募」列為增減資類別關鍵字），沒有獨立資料源 |
| 對應機構用途 | 私募增資對象與價格揭露，防利益輸送 |

### 14. 法說會音檔與簡報 PDF

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS／`doc.twse.com.tw` |
| 我們現況 | 🔴 **簡報PDF已查證不可用**——`docs/DATA_SOURCE_MAP.md`「🔴(b)法說會簡報PDF」：PDF主機`doc.twse.com.tw`robots.txt全站`Disallow: /`；`events.json`法說會事件只有公告標題不含產品內容。**音檔部分repo內未找到任何查證紀錄** |
| 官方是否允許程式存取 | 🔴 PDF主機禁止；音檔未查 |
| 對應機構用途 | 法人說明會內容公開揭露 |

### 15. 重大訊息全類別 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | `FORM_URL=https://mopsov.twse.com.tw/mops/web/t05st01`、`AJAX_URL=.../ajax_t05st01`（`research/mops_material_news_client.py`，需先GET表單頁拿`jcsession`cookie） |
| 我們現況 | 🔴/🟡 **已整合，且是四支衝突程式中最重要的一支**——供`material_news_classify.py`、`material_news_car_gate*.py`一系列事件研究使用，是題材驗證與新聞事件管線的資料基礎之一 |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許**，且此檔建立時間（09-08 22:01）**晚於或同日**`DATA_SOURCE_MAP.md`記錄該衝突的時間（09-08 08:19），影響範圍比其他三支更需要優先釐清 |
| 對應機構用途 | 上市櫃公司重大訊息即時揭露 |

### 16. 月營收

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS，經FinMind中介 |
| 端點 | FinMind `TaiwanStockMonthRevenue` |
| 我們現況 | 🟡 **已整合，非直連MOPS官方公告**。`research/monthly_revenue_event_study.py`使用；`research/DATA.md:390-404`有PIT（公布時點）查證段落 |
| 官方是否允許程式存取 | FinMind中介層允許；MOPS官方月營收公告頁未查證 |
| 對應機構用途 | 上市櫃公司月度營收公告 |

### 17. 集保股權分散（TDCC）

| 欄位 | 內容 |
|---|---|
| 機構 | 台灣集中保管結算所（TDCC） |
| 端點 | `https://opendata.tdcc.com.tw/getOD.ashx?id=1-5`（官方、免費、免金鑰） |
| 我們現況 | 🟢 **已整合**。`scripts/fetch_tdcc_holders.py`寫入`data/holders.json`，已設Windows排程`AlphaTdccHolders`（`docs/LOCAL_SCHEDULED_TASKS.md`）。首次實測4,051檔、68,867列。 |
| 已知限制 | 無歷史查詢端點，只能往前累積（`PENDING_QUEUE.md:2260-2279`） |
| 官方是否允許程式存取 | 🟢（TDCC開放資料平台，設計上供程式讀取） |
| 對應機構用途 | 股權分散統計，反映籌碼集中度 |
| 待辦 | TDCC其他開放資料集（id=1-5以外）未查證 |

### 18. 台灣指數公司成分股調整公告

| 欄位 | 內容 |
|---|---|
| 機構 | 台灣指數公司（TIP） |
| 我們現況 | 🔴 **已查證，判定資料不可及，FAIL**。`research/index_reconstitution_probe.py`：FinMind無對應dataset；TWSE openapi 144端點裡`/indicesReport/TAI50I`只是指數點數序列、`/ETFReport/ETFRank`只是排名，皆非成分股名單。台灣指數公司僅以新聞稿/公告網頁呈現，無結構化歷史API |
| 官方是否允許程式存取 | 無結構化端點可測 |
| 對應機構用途 | 指數成分股調整（如台灣50季度調整）事前/事後公告 |

### 19. 財政部海關進出口統計

| 欄位 | 內容 |
|---|---|
| 機構 | 財政部關務署 |
| 我們現況 | **⚪ 未查證**（repo內僅出現在任務清單原文，無任何查證紀錄） |
| 對應機構用途 | 台灣對外貿易月度統計，總經領先指標 |
| 後續 | 源頭二.2實測，候選：`web02.mof.gov.tw`或財政部資料開放平台 |

### 20. 經濟部工業生產統計與外銷訂單

| 欄位 | 內容 |
|---|---|
| 機構 | 經濟部統計處 |
| 我們現況 | **⚪ 未查證**。`research/data_cache/ndc/`底下有國發會「景氣對策信號」等快取，**那是國發會(NDC)非經濟部，用途也不同，不可算作已查證** |
| 對應機構用途 | 工業生產指數、外銷訂單金額，總經領先指標 |
| 後續 | 源頭二.2實測經濟部統計處官網開放資料 |

### 21. 央行外匯與利率

| 欄位 | 內容 |
|---|---|
| 機構 | 中央銀行 |
| 利率端點 | `https://www.cbc.gov.tw/public/data/OpenData/A13Rate.csv`（官方、免費、CSV，`research/cbc_rf_rate_client.py`），另有`cbc_policy_decision_data.py`／`cbc_decision_event_gate61.py`（假設`#61`已FAIL，見`data/signal_status.json`） |
| 我們現況（利率） | 🟢 **已整合** |
| 我們現況（外匯） | 🟡 **未走央行官方牌告匯率**——App端`fx.json`改用yfinance`TWD=X`（`.github/scripts/fetch_fx.py`，因FinMind額度問題改的），研究端`fx_twd_gate.py`用FinMind`TaiwanExchangeRate`，兩者皆非央行官方 |
| 官方是否允許程式存取 | 利率🟢；外匯官方牌告未查證 |
| 對應機構用途 | 貨幣政策（重貼現率）、官方匯率牌告 |

---

## 美國

### 22. SEC EDGAR 全表（8-K/10-K/10-Q/13F/Form 4/S-1）

| 欄位 | 內容 |
|---|---|
| 機構 | U.S. Securities and Exchange Commission |
| 端點 | `https://www.sec.gov/files/company_tickers.json`（ticker↔CIK對照）、`https://data.sec.gov/submissions/CIK{cik}.json`（申報清單）、XBRL companyfacts（`research/DATA.md:193-343`大量查證） |
| 我們現況 | 🟢 **已整合，但僅部分表別**。已用於下市查證、PIT財報（companyfacts）、filer category、**8-K事件研究**（`us_8k_item101_gate52.py`／`us_8k_item502_gate52.py`／`us_8k_pead_gate52.py`，假設`#52-us`已FAIL）。**13F／Form 4／S-1未見專門查證或使用** |
| 官方是否允許程式存取 | 🟢（SEC EDGAR公開API，設計上供程式讀取，需帶識別性User-Agent） |
| 對應機構用途 | 上市公司法定揭露文件全表 |
| 待辦 | 13F（機構持倉季報）、Form 4（內部人交易）、S-1（IPO招股書）未查證，皆有研究價值 |

### 23. EDGAR full-text search

| 欄位 | 內容 |
|---|---|
| 機構 | SEC |
| 端點 | `efts.sec.gov`（全文檢索API） |
| 我們現況 | **⚪ 未整合，僅有構想提及**。`research/US_STATE_ARCHIVE.md:217`只寫「未來若要...可以考慮掃efts.sec.gov全文檢索」，是待辦構想。「搜台灣客戶名稱反推供應鏈」這個具體用途完全未查證 |
| 對應機構用途 | 跨申報全文檢索，可用於反推供應鏈關係（例如搜「TSMC」出現在哪些美股10-K的客戶揭露段落） |

### 24. FRED 巨觀

| 欄位 | 內容 |
|---|---|
| 機構 | Federal Reserve Bank of St. Louis |
| 我們現況 | 🟡 **已整合但僅單一序列**——`research/fred_yield_curve_gate.py`用`T10Y2Y`（10Y-2Y利差）做台股regime訊號 |
| 官方是否允許程式存取 | 🟢（FRED API免費、需申請key，`fred_key.txt.txt`已存在） |
| 對應機構用途 | 美國總經數據巨量資料庫（數千個序列） |
| 待辦 | 「FRED巨觀」原始裁示指的是全面盤點可用序列，目前只用了1個，遠未窮盡 |

### 25. BLS（美國勞工統計局）

| 欄位 | 內容 |
|---|---|
| 機構 | Bureau of Labor Statistics |
| 我們現況 | **⚪ 完全未查證**（repo內僅出現在任務清單原文） |
| 對應機構用途 | 就業/失業率/CPI等總經數據 |

### 26. 美國海關（Census）進口統計

| 欄位 | 內容 |
|---|---|
| 機構 | U.S. Census Bureau |
| 我們現況 | **⚪ 完全未查證** |
| 對應機構用途 | 美國進出口貿易統計 |

### 27. FINRA 融券與暗池

| 欄位 | 內容 |
|---|---|
| 機構 | FINRA（融券部位）；Nasdaq（實際查證的是Reg SHO Threshold List，非FINRA本體） |
| 我們現況 | 🟡 **部分查證，未整合，兩支不同粒度查證並存**：(a) `docs/DATA_SOURCE_MAP.md:147-164`查過FINRA官方股票空頭部位目錄，結論「每兩週公布一次，粒度太粗，不足以支撐強制回補事件研究」；(b) `research/finra_threshold_probe.py`實際用的是**Nasdaq**（非FINRA）的Reg SHO Threshold List（`ftp://ftp.nasdaqtrader.com/SymbolDirectory/regsho/nasdaqth{YYYYMMDD}.txt`，免費匿名FTP，回溯至少2021年），已用於`#20`/`#21`短腿ticker查證（REFUTED結論，見`data/signal_status.json`外部策略段落相關脈絡） |
| 官方是否允許程式存取 | (a)🟢FINRA官方目錄允許；(b)🟢Nasdaq匿名FTP允許 |
| 對應機構用途 | 融券部位監控、防止過度放空 |
| 待辦 | **暗池（dark pool/ATS）成交量資料完全未查證** |

### 28. CFTC COT 部位報告

| 欄位 | 內容 |
|---|---|
| 機構 | Commodity Futures Trading Commission |
| 我們現況 | **⚪ 完全未查證** |
| 對應機構用途 | 期貨市場各類交易者（商業/非商業）部位周報，市場情緒指標 |

---

## 共通結論：官方是否允許程式存取（依主機分組，避免逐項重複判斷）

| 主機/平台 | robots.txt結論 | 查證日 | 涵蓋本檔案哪些項目 |
|---|---|---|
| `www.twse.com.tw`（TWSE主站） | 🟢 除`/epaper/`、`/FTSE/`外全部允許，且明列允許GPTBot等AI檢索器 | 2026-09-08，`docs/DATA_SOURCE_MAP.md` | #4/#5(部分)/#6/#7/#8 |
| `openapi.twse.com.tw`／`www.tpex.org.tw/openapi` | 🟢 官方開放API，設計上就是給程式讀的 | 2026-09-08 | #5/#6/#9(部分)/#18 |
| `mopsov.twse.com.tw`（MOPS查詢頁AJAX後端） | 🔴 除bingbot外全站`Disallow: /` | 2026-09-08 | #9/#10/#11/#12/#15（見本檔案最上方【重大發現】） |
| `doc.twse.com.tw`（年報/法說會PDF主機） | 🔴 全站`Disallow: /` | 2026-09-08 | #14 |
| `opendata.tdcc.com.tw` | 🟢 官方開放資料平台 | 既有 | #17 |
| `www.cbc.gov.tw` | 🟢 官方開放資料CSV | 既有 | #21 |
| `www.sec.gov`／`data.sec.gov`（SEC EDGAR） | 🟢 官方公開API | 既有 | #22/#23 |
| `ftp.nasdaqtrader.com` | 🟢 官方匿名FTP | 既有 | #27 |

---

## 總結：現況分佈

- **🟢 已整合且合規**：#4外資持股比率(2026-09-15新增)、#7當沖、#8鉅額交易、#17集保、#21利率、#22 SEC EDGAR、#27(b) Nasdaq threshold list ——7項
- **🟡 已整合但有保留**（非直連官方/僅涵蓋部分/合規存疑）：#2/#3三大法人期貨選擇權(經FinMind)、#5借券(查證中)、#9內部人轉讓(未確認可行)、#10/#11/#12/#15（robots.txt衝突，見重大發現）、#16月營收(經FinMind)、#21外匯(非央行)、#24 FRED(僅單序列)、#27(a)FINRA(粒度太粗) ——約11項
- **🔴 已查證不可行**：#1大額交易人(免費層無)、#6處置注意股(無歷史)、#14簡報PDF、#18指數成分股調整 ——4項
- **⚪ 完全未查證**：#13私募、#14法說會音檔、#19財政部海關、#20經濟部工業生產、#23 EDGAR全文檢索、#25 BLS、#26 Census、#27暗池、#28 CFTC COT ——約9項

---

## 源頭二.3：接入優先順序（機構用途強度 × 接入成本）

> 2026-09-15建立。排序原則：**機構用途強度**（該資料是不是專業投資人常態監控的
> 核心指標，1~5分）×**接入成本**（host是否已驗證合規、端點是否已知、格式複雜度，
> 1~5分，分數越低越便宜）。**明確排除**兩類：(a) 落在`mopsov.twse.com.tw`
> robots.txt衝突裡、待總司令裁示的候選（#9內部人轉讓、#13私募、#10/#11/#12/#15）
> ——這些若排進來理論用途強度會排很前面，但接入決策本身卡在合規裁示，不是
> 「排序後決定接不接」的問題，本輪不列入候選池；(b) 已查證不可行的🔴項目
> （#1/#6/#14/#18）。

| 排名 | 項目 | 用途強度 | 接入成本 | 現況 |
|---|---|---|---|---|
| 1 | #4 外資持股比率(MI_QFIIS) | 5 | 1（🟢host、已知端點家族） | **已完成本輪（2026-09-15）** |
| 2 | #22b SEC Form 4（內部人交易） | 5 | 3（🟢host、需解析XML/申報結構） | 待接入 |
| 3 | #28 CFTC COT部位報告 | 4 | 2（🟢公開CSV/Excel，格式穩定） | 待接入 |
| 4 | #24 FRED擴充（VIX/失業率/CPI等） | 3 | 1（🟢已有client+key，加序列而已） | 待接入 |
| 5 | #5 借券賣出餘額 | 4 | 3（🟢host，但正確端點仍待鎖定） | 待接入 |
| 6 | #22a SEC 13F（機構持倉季報） | 4 | 4（🟢host，但季度大檔需聚合邏輯） | 待接入 |
| 7 | #21 外匯官方牌告（取代yfinance） | 2 | 1（🟢同host的A13Rate.csv姊妹端點） | 待接入 |
| 8 | #25 BLS總經（就業/CPI） | 3 | 2（標準政府API，需申請/免申請key待查） | 待接入 |
| 9 | #19 財政部海關進出口統計 | 3 | 3（⚪host未驗證，需先測robots.txt+端點） | 待接入 |
| 10 | #20 經濟部工業生產與外銷訂單 | 3 | 3（⚪host未驗證，同上） | 待接入 |

**本輪只完成第1名**（見上方#4條目與`.github/scripts/fetch_foreign_holding.py`）。
第2~10名留給後續開發佇列輪次，每接入一個各自獨立commit，接入後回頭更新這份
排名表的「現況」欄與本檔案對應條目，不在同一輪一次做完（單輪時間有限，且
CLAUDE.md「四之二」要求每項都要有實測證據才能標完成，逐項慢慢做比一次宣稱
10項都好更誠實）。

**下一步（源頭二.2，待總司令裁示上述robots.txt衝突後再繼續）**：
對⚪未查證項目（含本排名表#9/#10）逐一打最小請求測試可用性；對🟡項目補齊
查證缺口（尤其#9內部人轉讓正確功能代碼、#5借券正確端點）。
