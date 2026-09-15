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

**2026-09-15 總司令裁示（推翻上面「不停用」那版，這版是最終決定）**：

> 總司令原話：「立刻停掉那四支程式（董監持股／庫藏股／可轉債轉換／重大訊息）
> 對 mopsov.twse.com.tw 的存取。理由：我們已為同一條紅線放棄 ic.tpex、分點
> 資料、驗證碼繞道，自己記錄的紅線不能自己踩。」

**已執行**：四支程式（`mops_insider_holdings_client.py`／`mops_buyback_client.py`／
`mops_cb_conversion_price_client.py`／`mops_material_news_client.py`）各自的
實際發request函式（`_fetch_html()`／`fetch_conversion_price_events()`／
`fetch_material_news_day()`，皆在cache-miss才會走到的位置）都已加上硬性
`PermissionError`防呆，物理上不可能再打`mopsov.twse.com.tw`，直到有合規
替代方案或總司令另行核准。**已快取的parquet檔案不受影響、不刪除**——
guard插在cache-check之後，讀已快取資料完全不受影響。

**合規替代查證結果**（本輪用TWSE openapi官方swagger規格檔`https://
openapi.twse.com.tw/v1/swagger.json`實測查證，不是猜測）：

| 程式 | 對應項目 | 現有快取量 | 下游用途 | 合規替代 | App現況 |
|---|---|---|---|---|---|
| `mops_insider_holdings_client.py` | #10 董監持股 | 901個parquet | `insider_holdings_pilot_ic.py`（第1關可行性IC查證） | **🔴 查無**——TWSE openapi只有ESG揭露裡的「前10大股東持股情形」（`t187ap46_L_18`），是股東不是董監事，且只有前10名不是全體彙總，非同一資料 | 未接入任何App面板，純研究用，**不受影響** |
| `mops_buyback_client.py` | #11 庫藏股 | 41個parquet（回溯至2015年） | `buyback_car_gate.py`（事件研究CAR gate） | **🔴 查無**——TWSE openapi資產負債表端點（`t187ap07_X_*`）只把「庫藏股」當資產負債表上的**加總金額科目**，不是逐筆買回公告事件 | 未接入任何App面板，純研究用，**不受影響** |
| `mops_cb_conversion_price_client.py` | #12 可轉債轉換 | 30個parquet（僅單一市場×年月組合，尚未真正開始多年份回填） | `cb_conversion_price_reset_gate1.py` | **🔴 查無**——swagger規格檔搜尋「轉換公司債」無任何對應端點 | 未接入任何App面板，純研究用，**不受影響**（且這條本來就還沒真正開跑，停用代價最小） |
| `mops_material_news_client.py` | #15 重大訊息 | 2,607個parquet | `material_news_classify.py`／`material_news_car_gate*.py`（題材驗證與新聞事件研究的資料基礎） | **🟢 已有，而且已經在production用**——`openapi.twse.com.tw/v1/opendata/t187ap04_L`（TWSE）＋`www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O`（TPEx），`.github/scripts/fetch_news_events.py`每30分鐘排程已在用，供App「近期事件與題材」卡使用。**限制**：這兩個官方端點是**當日快照，無歷史區間查詢參數**，只能從排程上線那天（2026-09-08）開始往前累積，補不回更早的歷史 | App面板走的本來就是這條合規端點，**不受影響**；受影響的只有研究端想拿更深歷史回測，這部分現在資料深度被鎖在2026-09-08之後 |

**結論**：四支程式全部**沒有App面板依賴**，都是純研究/因子可行性查證用途，
停用不影響任何使用者看得到的功能。#15（重大訊息）App端本來就走合規的
`t187ap04_L`／`mopsfin_t187ap04_O`，唯一實質損失是研究端拿不到2026-09-08
之前的歷史深度做事件研究；#10/#11/#12 目前查無任何官方替代，這三項的
候選研究（董監持股IC查證、庫藏股CAR gate、可轉債轉換價重置gate）**在
找到合規替代或總司令核准書面申請之前，維持用已快取的既有資料做結案，
不再擴充樣本**。

**已同步更新**：`docs/DATA_SOURCE_MAP.md`「🔴 走不通：MOPS 公開查詢頁」節
加註本次裁示與執行結果；`PENDING_QUEUE.md`源頭二.2該行更新為已依裁示執行。

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

### 5. 借券賣出餘額 —— 已接入「可借券賣出股數」子集（2026-09-15，源頭二.3第5名）

| 欄位 | 內容 |
|---|---|
| 機構 | TWSE／TPEx |
| 端點 | TWSE openapi `/SBL/TWT96U`——2026-09-15查證：這是TWSE swagger完整目錄裡**唯一**含「借券」關鍵字的端點（`exchangeReport/TWT93U`實測回200+HTML，是已知「無效路徑回HTML」地雷，非合法端點）。官方欄位定義是「上市上櫃股票**當日可借券賣出股數**」，語意是**借券供給水位（可借額度）**，不是「已借券賣出的未平倉部位」也不是「借券費率」——原始標籤「借券賣出餘額」跟這個端點的真實語意有落差，已誠實標註不誇大。 |
| **已知地雷（本次接入實測發現）** | 回傳的1237列同時有`TWSECode`/`TWSEAvailableVolume`（上市）與`GRETAICode`/`GRETAIAvailableVolume`（上櫃）四欄，但**同一列的上市代號跟上櫃代號不是同一家公司**（例如某列`TWSECode=00400A`、`GRETAICode=00411A`）——這是把兩個長度不同的獨立陣列用index位置硬湊成同一列JSON，不是關聯式資料，取用時必須拆成兩個獨立清單處理，不可逐列對應。 |
| 官方是否允許程式存取 | 🟢（TWSE openapi，設計上供程式讀取，免金鑰） |
| 對應機構用途 | 借券供給水位監控（融券市場活動的其中一個面向） |
| 我們現況 | 🟢 **已接入子集，誠實標示範圍**。`.github/scripts/fetch_short_lending_available.py`，輸出`data/short_lending_available.json`，個股頁「籌碼」分頁新增「可借券賣出股數」卡（僅台股顯示）。2026-09-15實測：上市1237檔、上櫃858檔，2330可借6,619,228股。**誠實限制**：CLAUDE.md「借券成本與可借量硬規則」提到的兩項缺口（成本／可借量）本項只補上「可借額度」這一部分，**借券費率仍完全未接入**（各券商議定，無公開統一費率），不得因為這項接入就視為該硬規則的資料缺陷已解除。 |

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
| 我們現況 | 🔴 **2026-09-15 總司令裁示已停用存取**（`mops_insider_holdings_client.py::_fetch_html()`已加`PermissionError`硬性防呆），既有901個parquet快取保留可讀，不再新增。查無TWSE openapi合規替代（僅ESG揭露「前10大股東」，非同一資料），見本檔案最上方【重大發現】 |
| 格式 | JSON（AJAX回應） |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許**（見上方重大發現） |
| 對應機構用途 | 董監事持股比例揭露，防公司派掏空/內線 |

### 11. 庫藏股 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | `POST https://mopsov.twse.com.tw/mops/web/ajax_t35sc09`（`research/mops_buyback_client.py`），回溯至2015年 |
| 我們現況 | 🔴 **2026-09-15 總司令裁示已停用存取**（`mops_buyback_client.py::_fetch_html()`已加`PermissionError`硬性防呆），既有41個parquet快取保留可讀，不再新增。查無TWSE openapi合規替代（資產負債表只把庫藏股當彙總金額科目，非逐筆公告），見本檔案最上方【重大發現】 |
| 官方是否允許程式存取 | **🔴 依robots.txt判定不允許** |
| 對應機構用途 | 公司買回自家股份公告，市場信心訊號 |

### 12. 可轉債轉換 ⚠️見上方重大發現

| 欄位 | 內容 |
|---|---|
| 機構 | MOPS |
| 端點 | 兩段式AJAX：`GET .../t108sb08_1_q2`→`POST .../ajax_t108sb08_1_q2`→`POST .../ajax_t108sb08_1`（`research/mops_cb_conversion_price_client.py`） |
| 我們現況 | 🔴 **2026-09-15 總司令裁示已停用存取**（`mops_cb_conversion_price_client.py::fetch_conversion_price_events()`已加`PermissionError`硬性防呆），既有30個parquet快取（僅單一市場×年月組合，本來就還沒真正開始多年份回填）保留可讀，不再新增。查無TWSE openapi合規替代，見本檔案最上方【重大發現】 |
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
| 我們現況 | 🔴 **2026-09-15 總司令裁示已停用存取**（`mops_material_news_client.py::fetch_material_news_day()`已加`PermissionError`硬性防呆），既有2,607個parquet快取保留可讀，不再新增。**App面板不受影響**——`.github/scripts/fetch_news_events.py`早就走合規的`openapi.twse.com.tw/v1/opendata/t187ap04_L`＋`mopsfin_t187ap04_O`，只是那條合規端點是當日快照無歷史區間，補不回2026-09-08之前的深度，見本檔案最上方【重大發現】 |
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

### 19. 財政部海關進出口統計 —— 已接入（2026-09-15，源頭二.3第9名）

| 欄位 | 內容 |
|---|---|
| 機構 | 財政部關務署 |
| 端點 | `https://opendata.customs.gov.tw/data/6053/csv.csv`（`data.gov.tw`資料集#6053「海關進出口貿易統計」，官方CSV，免金鑰，`.github/scripts/fetch_customs_trade.py`） |
| 我們現況 | 🟢 **已整合（2026-09-15）**——三來源查證：①`data.gov.tw`資料集#6053頁面（WebSearch找到）②WebFetch該頁確認CSV下載網址、提供機關、更新頻率（每1月）③實測`curl`/`requests`皆200、合法CSV，回溯至民國103年1月（西元2014-01）150個月 |
| 官方是否允許程式存取 | 🟢（官方開放資料平台，政府資料開放授權條款第1版） |
| 對應機構用途 | 台灣對外貿易月度統計（出口總值/進口總值/出入超），總經領先指標 |
| 已知SSL陷阱 | 跟`www.cbc.gov.tw`同一類問題——`opendata.customs.gov.tw`憑證鏈中繼CA缺Subject Key Identifier，`requests`預設驗證會拋`CERTIFICATE_VERIFY_FAILED`，修法沿用同一個只關閉`ssl.VERIFY_X509_STRICT`旗標的做法 |
| 已知限制 | 官方每月更新，資料通常落後1個月，非即時；YoY為本管線自行計算，非官方原始欄位 |

### 20. 經濟部工業生產統計與外銷訂單 —— 工業生產指數已接入，外銷訂單未接入（2026-09-15，源頭二.3第10名）

| 欄位 | 內容 |
|---|---|
| 機構 | 經濟部（工業生產）／經濟部統計處（外銷訂單） |
| 端點（工業生產） | `https://service.moea.gov.tw/EE520/opendata/d.csv`（`data.gov.tw`資料集#6607「工業生產」，官方CSV約8.4MB，免金鑰，`.github/scripts/fetch_industrial_production.py`） |
| 我們現況（工業生產） | 🟢 **已接入（2026-09-15）**——三來源查證：①`data.gov.tw`#6607頁面（WebSearch找到）②WebFetch確認CSV網址/提供機關/更新頻率③實測`curl`/`requests`皆200、合法CSV，行業代碼`Z`（全體工業加總，判斷依據見腳本docstring）逐月序列回溯至1996-01共367筆。基期「110年=100」原樣記錄，MoM/YoY為本管線自算 |
| 我們現況（外銷訂單） | ⚪ **未接入（刻意縮小範圍）**——查證發現data.gov.tw上的外銷訂單資料是按產品別拆成多個獨立資料集（電機產品/塑橡膠製品等），未找到單一「總金額」聚合資料集，需要另一輪查證+跨資料集加總邏輯，工作量超出單輪範圍 |
| 官方是否允許程式存取 | 工業生產🟢（官方開放資料平台）；外銷訂單未查證 |
| 對應機構用途 | 工業生產指數、外銷訂單金額，總經領先指標 |
| 已知限制 | 官方每月更新，資料通常落後1~2個月；行業代碼`Z`＝全體工業加總為觀察CSV結構後的推論（其餘235組代碼皆為具體行業名稱），若官方改變代碼配置會在`errors`欄位誠實記錄，非改用其他代碼硬湊 |

### 21. 央行外匯與利率 —— 外匯已接入（2026-09-15，源頭二.3第7名）

| 欄位 | 內容 |
|---|---|
| 機構 | 中央銀行 |
| 利率端點 | `https://www.cbc.gov.tw/public/data/OpenData/A13Rate.csv`（官方、免費、CSV，`research/cbc_rf_rate_client.py`），另有`cbc_policy_decision_data.py`／`cbc_decision_event_gate61.py`（假設`#61`已FAIL，見`data/signal_status.json`） |
| 外匯端點 | `https://www.cbc.gov.tw/public/data/OpenData/外匯局/FTDOpenData015.csv`（`A13Rate.csv`的姊妹端點，同一台主機、同一種免金鑰CSV格式；`data.gov.tw`資料集#7232「新臺幣兌換美元銀行間收盤匯率」，官方每日更新，回溯至2008-01-02，`.github/scripts/fetch_fx.py`） |
| 我們現況（利率） | 🟢 **已整合** |
| 我們現況（外匯） | 🟢 **已整合（2026-09-15）**——`fetch_fx.py`主來源改打央行`FTDOpenData015.csv`（銀行間每日收盤即期匯率），yfinance`TWD=X`降為備援（央行端點失敗才用，維持回退鏈不單點依賴）；`fx_twd_gate.py`（研究端）仍用FinMind`TaiwanExchangeRate`，未同步改動（研究腳本非本輪範圍，一致性列為已知缺口） |
| 官方是否允許程式存取 | 利率🟢；外匯🟢（同host、CSV直接下載、無robots.txt限制、`requests`實測200） |
| 對應機構用途 | 貨幣政策（重貼現率）、官方匯率牌告 |
| 已知SSL陷阱 | 央行憑證鏈中繼CA缺`Subject Key Identifier`擴充欄位，`requests`預設驗證會拋`CERTIFICATE_VERIFY_FAILED`；修法為只關閉`ssl.VERIFY_X509_STRICT`旗標（沿用`cbc_rf_rate_client.py`已驗證的做法，非`verify=False`） |

---

## 美國

### 22. SEC EDGAR 全表（8-K/10-K/10-Q/13F/Form 4/S-1）

| 欄位 | 內容 |
|---|---|
| 機構 | U.S. Securities and Exchange Commission |
| 端點 | `https://www.sec.gov/files/company_tickers.json`（ticker↔CIK對照）、`https://data.sec.gov/submissions/CIK{cik}.json`（申報清單）、XBRL companyfacts（`research/DATA.md:193-343`大量查證） |
| 我們現況 | 🟢 **已整合，但僅部分表別**。已用於下市查證、PIT財報（companyfacts）、filer category、**8-K事件研究**（`us_8k_item101_gate52.py`／`us_8k_item502_gate52.py`／`us_8k_pead_gate52.py`，假設`#52-us`已FAIL）。**Form 4（內部人交易）已接入**（2026-09-15，源頭二.3第2名，見下方22b）；**13F（機構持倉）已接入極小子集**（2026-09-15，源頭二.3第6名，見下方22c）；**S-1未見專門查證或使用** |
| 官方是否允許程式存取 | 🟢（SEC EDGAR公開API，設計上供程式讀取，需帶識別性User-Agent） |
| 對應機構用途 | 上市公司法定揭露文件全表 |
| 待辦 | S-1（IPO招股書）未查證，有研究價值；13F全市場整合（CUSIP對映）仍待評估是否值得投入 |

### 22b. SEC EDGAR Form 4（內部人交易）—— 已接入（2026-09-15，源頭二.3第2名）

| 欄位 | 內容 |
|---|---|
| 機構 | U.S. Securities and Exchange Commission |
| 端點 | `browse-edgar?action=getcompany&CIK={cik}&type=4&output=atom`（列出申報）→ `Archives/edgar/data/{cik}/{accession}/index.json`（找xml檔名）→ 申報xml（逐筆交易結構化資料） |
| 欄位 | 申報人姓名/職稱、交易日期、交易代碼（P買進/S賣出/A獎酬/M履約等）、股數、每股價格、交易後持股 |
| 更新頻率 | 每日（跟`market.yml`美股班次同批） |
| 歷史可回溯到哪年 | 依申報人而異，本輪只取每檔最近8筆申報（不做歷史回補） |
| 官方是否允許程式存取 | 🟢 |
| 對應機構用途 | 內部人買賣常被視為對公司前景信心的訊號，是機構投資人常態監控指標 |
| 我們現況 | 🟢 **已接入**。`.github/scripts/fetch_us_insider_trading.py`，輸出`data/us_insider_trading.json`，個股頁「籌碼」分頁新增「內部人交易」卡（僅美股顯示）。2026-09-15實測：9檔（沿用`us_sic.json`的CIK對映）、AAPL/NVDA/MSFT/TSM/GOOGL/AMZN/UMC/ASX/CHT，共取得約100+筆真實交易（例：AAPL SVP Jennifer Newstead 2026-09-08賣出1438股@317.23）。**誠實限制**：UMC/ASX/CHT為台股ADR，外國私人發行人多數豁免Section 16申報，查到0~少數筆是正常狀態非抓取失敗；極舊申報（accession開頭`9999999997`）目錄裡沒有.xml檔，已知並記錄跳過原因。 |

### 22c. SEC EDGAR Form 13F-HR（機構持倉季報）—— 已接入極小子集（2026-09-15，源頭二.3第6名）

| 欄位 | 內容 |
|---|---|
| 機構 | U.S. Securities and Exchange Commission |
| 端點 | `browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&output=atom`（列出申報）→ `Archives/edgar/data/{cik}/{accession}/index.json`（找資訊表xml，**地雷**：目錄裡有`primary_doc.xml`封面頁跟另一個數字檔名的資訊表本體，要用內容含`informationTable`判斷，不能猜檔名）→ 資訊表xml（逐筆`nameOfIssuer`/`cusip`/`value`/`shares`） |
| 官方是否允許程式存取 | 🟢 |
| 對應機構用途 | 機構投資人常態關注「聰明錢在買什麼」，13F是唯一能看到大型機構持股變化的公開揭露 |
| 我們現況 | 🟢 **已接入，但刻意大幅縮小範圍，不是全市場13F整合**。13F沒有ticker欄位只有`nameOfIssuer`/`cusip`，全市場整合需要CUSIP↔ticker對映表（商業資料，非免費公開），規模遠超一輪工作單位，故**本輪只追蹤波克夏海瑟威一家申報人**（CIK 1067983，最知名、最被公開關注的13F申報人），比對其持股`nameOfIssuer`是否精確命中`ISSUER_NAME_MAP`裡手動核對過的5檔ticker（AAPL/GOOGL/MSFT/NVDA/AMZN）。`.github/scripts/fetch_us_13f_holdings.py`，輸出`data/us_13f_holdings.json`，個股頁「籌碼」分頁新增「機構持倉（13F·僅波克夏海瑟威）」卡（僅美股顯示）。2026-09-15實測：最新13F（申報日2026-08-14，共89筆持股）命中2檔——AAPL 227,917,808股（申報市值約US$65,950M）、GOOGL（合併Class A+C）105,979,600股（申報市值約US$37,764M），其餘7檔追蹤清單這一期確實沒有部位，非抓取失敗。**已踩過並修正的兩個地雷**：(1) 同一發行人常拆成多筆infoTable列（不同子公司/被授權管理人各自持有的區塊，SEC combination filing標準格式，非重複列），必須全部加總才是真實總持股，只取一列會嚴重低估或算出不合理數字；(2) `value`欄位2026-09-15實測是「整數美元」，不是13F紙本申報年代慣例的「千美元」（用value/shares反推隱含股價驗證：AAPL約$289/股、GOOGL約$356/股，皆為合理量級，若照千美元慣例誤乘1000會得到天文數字）。 |

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

### 25. BLS（美國勞工統計局） —— 已接入（2026-09-15，源頭二.3第8名）

| 欄位 | 內容 |
|---|---|
| 機構 | Bureau of Labor Statistics |
| 端點 | `https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}`（Public Data API v2，GET，未註冊金鑰即可用；`.github/scripts/fetch_bls_macro.py`） |
| 追蹤序列 | 失業率`LNS14000000`／CPI-U全項`CUUR0000SA0`（本管線自算YoY）／非農就業人數`CES0000000001`（本管線自算MoM） |
| 我們現況 | 🟢 **已整合（2026-09-15）**——三來源查證：①BLS官方API文件②WebSearch第三方整合文件交叉確認免金鑰限額③實測三個series id皆`REQUEST_SUCCEEDED`、200、回溯約32個月 |
| 官方是否允許程式存取 | 🟢（官方公開API，設計上供程式讀取） |
| 對應機構用途 | 就業/失業率/CPI等總經數據，專業投資人常態監控指標 |
| 已知限制 | 未註冊金鑰（第三方文件引用「25次/日」，官方未明講上限，本管線每日僅3次遠低於此值）；月頻統計常有一個月落後，非即時數據 |

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

### 28. CFTC COT 部位報告 —— 已接入（2026-09-15，源頭二.3第3名）

| 欄位 | 內容 |
|---|---|
| 機構 | Commodity Futures Trading Commission |
| 端點 | `https://publicreporting.cftc.gov/resource/6dca-aqww.json`（CFTC自己的Socrata Public Reporting Environment，Legacy Futures Only報告，官方公開資料入口非第三方鏡像） |
| 欄位 | 各合約每週非商業(投機客)/商業(避險者)多空部位、未平倉量；本專案取`noncomm_positions_long_all`/`short_all`算淨部位 |
| 更新頻率 | 官方每週五公布，資料日固定為前一週二（`report_date_as_yyyy_mm_dd`） |
| 歷史可回溯到哪年 | 本輪只取每合約最近12週（`HISTORY_WEEKS`），未做歷史回補 |
| 官方是否允許程式存取 | 🟢（Socrata SODA API，設計上供程式讀取，免金鑰） |
| 對應機構用途 | 期貨市場各類交易者（商業/非商業）部位周報，市場情緒指標 |
| 我們現況 | 🟢 **已接入，僅美股情緒指標**（CFTC只涵蓋美國期貨市場，不含TAIFEX台指期）。`.github/scripts/fetch_cftc_cot.py`，追蹤三檔：S&P 500 Consolidated（代碼`13874+`）、NASDAQ-100 Consolidated（代碼`20974+`）、VIX FUTURES（代碼`1170E1`），輸出`data/cftc_cot.json`，市場頁美股分頁新增「CFTC投機客淨部位」卡。2026-09-15實測資料日2026-09-08：S&P500淨部位-93,933（較上週-4,562）、NASDAQ-100淨部位+20,704（較上週-6,373）、VIX期貨淨部位-94,829（較上週-10,644）。**已踩過的地雷**：`$where`參數裡的`%`萬用字元不可自己手動加`%25`，會被`requests`二次編碼成`%2525`導致完全比對不到任何列，讓`requests`自己編碼即可。 |

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
| `publicreporting.cftc.gov` | 🟢 官方Socrata公開資料入口，設計上供程式讀取 | 2026-09-15 | #28 |
| `api.bls.gov` | 🟢 官方Public Data API v2，設計上供程式讀取，未註冊金鑰即可用 | 2026-09-15 | #25 |
| `opendata.customs.gov.tw` | 🟢 官方開放資料平台CSV | 2026-09-15 | #19 |
| `service.moea.gov.tw` | 🟢 官方開放資料CSV | 2026-09-15 | #20 |

---

## 總結：現況分佈

- **🟢 已整合且合規**：#4外資持股比率(2026-09-15新增)、#7當沖、#8鉅額交易、#17集保、#19財政部海關(2026-09-15新增)、#20經濟部工業生產(2026-09-15新增，僅生產指數)、#21利率＋外匯(外匯2026-09-15新增)、#22 SEC EDGAR、#25 BLS總經(2026-09-15新增)、#27(b) Nasdaq threshold list、#28 CFTC COT(2026-09-15新增，先前漏更新本段落) ——11項
- **🟡 已整合但有保留**（非直連官方/僅涵蓋部分/合規存疑）：#2/#3三大法人期貨選擇權(經FinMind)、#5借券(查證中)、#9內部人轉讓(未確認可行)、#10/#11/#12/#15（robots.txt衝突，見重大發現）、#16月營收(經FinMind)、#20外銷訂單子項(未接入，見#20條目)、#24 FRED(僅單序列)、#27(a)FINRA(粒度太粗) ——約11項
- **🔴 已查證不可行**：#1大額交易人(免費層無)、#6處置注意股(無歷史)、#14簡報PDF、#18指數成分股調整 ——4項
- **⚪ 完全未查證**：#13私募、#14法說會音檔、#23 EDGAR全文檢索、#26 Census、#27暗池 ——約5項

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
| 2 | #22b SEC Form 4（內部人交易） | 5 | 3（🟢host、需解析XML/申報結構） | **已完成（2026-09-15）** |
| 3 | #28 CFTC COT部位報告 | 4 | 2（🟢公開CSV/Excel，格式穩定） | **已完成（2026-09-15）** |
| 4 | #24 FRED擴充（VIX/失業率/CPI等） | 3 | 1（🟢已有client+key，加序列而已） | 待接入 |
| 5 | #5 借券賣出餘額 | 4 | 3（🟢host，但正確端點仍待鎖定） | **已接入子集（2026-09-15，僅可借額度，非借券費率）** |
| 6 | #22a SEC 13F（機構持倉季報） | 4 | 4（🟢host，但季度大檔需聚合邏輯） | **已接入極小子集（2026-09-15，僅波克夏一家申報人，見22c）** |
| 7 | #21 外匯官方牌告（取代yfinance） | 2 | 1（🟢同host的A13Rate.csv姊妹端點） | **已完成（2026-09-15）** |
| 8 | #25 BLS總經（就業/CPI） | 3 | 2（標準政府API，免金鑰） | **已完成（2026-09-15）** |
| 9 | #19 財政部海關進出口統計 | 3 | 3（🟢host已驗證，官方CSV免金鑰） | **已完成（2026-09-15）** |
| 10 | #20 經濟部工業生產與外銷訂單 | 3 | 3（🟢工業生產host已驗證免金鑰；外銷訂單⚪待另一輪） | **工業生產已完成（2026-09-15），外銷訂單未接入** |

**2026-09-15開發佇列自走完成第1、2、3、5、6、7、8、9、10名**（見上方#4條目與
`.github/scripts/fetch_foreign_holding.py`；#22b條目與
`.github/scripts/fetch_us_insider_trading.py`；#28條目與
`.github/scripts/fetch_cftc_cot.py`；#5條目與
`.github/scripts/fetch_short_lending_available.py`；#22c條目與
`.github/scripts/fetch_us_13f_holdings.py`；#21條目與
`.github/scripts/fetch_fx.py`；#25條目與`.github/scripts/fetch_bls_macro.py`；
#19條目與`.github/scripts/fetch_customs_trade.py`；#20條目（僅工業生產指數，
外銷訂單未接入，見已知缺口）與`.github/scripts/fetch_industrial_production.py`）。
**排名表前10名至此全數處理完畢**（第4名FRED跳過待總司令裁示；第10名外銷訂單
子項未接入待後續查證），排名表本身的階段性任務告一段落。

**第4名（FRED擴充）本輪跳過，原因記錄如下，不是遺漏**：`research/
fred_yield_curve_gate.py`目前的金鑰讀取方式是`C:\alpha\alpha-data\
fred_key.txt.txt`（本機檔案，docstring稱「凍結區檔案」），只在**本機手動
執行研究腳本**時使用，從未進過任何GitHub Actions workflow。若要讓FRED
擴充序列比照其他源頭二.3項目走`market.yml`每日排程自動更新，必須把這把
金鑰加進GitHub Actions Secrets（`secrets.FRED_API_KEY`）——這是把一把
目前只存在本機、刻意標記「凍結」的憑證，移到雲端CI的信任邊界，屬於
`PENDING_QUEUE.md`「開發佇列」停下條件第1類「需要總司令親自操作／
需要核准的裁示」，不是自走流程能自行判斷該不該做的事。本輪先跳過，
改做接入成本較低、無憑證疑慮的第5名（借券），第4名留待總司令裁示
「是否同意把FRED金鑰上傳GitHub Secrets給CI排程使用」後再繼續，或改為
本機排程執行（比照`quotes_ibkr.json`/`quotes_sinopac.json`模式）——兩種
做法各有取捨，一併留給總司令裁示。

外銷訂單子項留給後續開發佇列輪次（需要另一輪查證跨產品資料集加總邏輯），
每接入一個各自獨立commit，接入後回頭更新這份
排名表的「現況」欄與本檔案對應條目，不在同一輪一次做完（單輪時間有限，且
CLAUDE.md「四之二」要求每項都要有實測證據才能標完成，逐項慢慢做比一次宣稱
10項都好更誠實）。

**下一步（源頭二.2，待總司令裁示上述robots.txt衝突後再繼續）**：
對⚪未查證項目（含本排名表#9/#10）逐一打最小請求測試可用性；對🟡項目補齊
查證缺口（尤其#9內部人轉讓正確功能代碼、#5借券正確端點）。

## 源頭二.5：驗收總結（2026-09-15開發佇列自走，cycle_id 20260915-110102）

依總司令原始裁示第5點「驗收：FIRST_HAND_SOURCES.md 表格截圖、前 10 名清單
與理由、每接入一個回報一個」逐條對應。**依CLAUDE.md「四之二」驗收證據原則，
本節用機器可查的表格與資料檔紀錄取代截圖**——上方「源頭二.3：接入優先
順序」表格即為總司令要的表格，本節不重複貼一次，改整理成「每接入一個
回報一個」的驗收清單。

**前10名清單與理由**：見上方表格「排名／項目／用途強度／接入成本」欄，
排序邏輯已在表格前的說明段落寫明（機構用途強度×接入成本，明確排除
robots.txt合規爭議中的候選與已查證不可行的🔴項目）。

**逐項驗收（8項完整/子集接入，1項總司令裁示中，1項子項未接入）**：

| 排名 | 項目 | 資料檔 | 前端顯示位置（`STATUS.json` `app_data_sources[].panel`） | 資料日期驗證方式 |
|---|---|---|---|---|
| 1 | 外資持股比率 | `data/foreign_holding.json` | 個股頁·籌碼·外資持股比率 | Playwright實測2330顯示69.23%/30.76% |
| 2 | SEC Form 4內部人交易 | `data/us_insider_trading.json` | 個股頁·籌碼·內部人交易（僅美股） | Playwright實測AAPL顯示近13筆申報含日期 |
| 3 | CFTC COT部位報告 | `data/cftc_cot.json` | 市場頁·美股·CFTC投機客淨部位 | `report_date_as_yyyy_mm_dd`欄位，Playwright實測顯示三檔淨部位 |
| 5 | 可借券賣出股數 | `data/short_lending_available.json` | 個股頁·籌碼·可借券賣出股數（僅台股） | Playwright實測2330顯示6,619,228股 |
| 6 | SEC 13F（僅波克夏） | `data/us_13f_holdings.json` | 個股頁·籌碼·機構持倉（僅美股，僅波克夏海瑟威） | Playwright實測AAPL/GOOGL顯示申報日與持股 |
| 7 | 央行外匯牌告匯率 | `data/fx.json` | 今日頁·匯率 | 本機實測`rate=31.688 date=2026-09-14` |
| 8 | BLS總經指標 | `data/bls_macro.json` | 市場頁·美股·美國總經指標 | Playwright實測顯示資料月「2026-08」 |
| 9 | 財政部海關貿易統計 | `data/customs_trade.json` | 市場頁·台股·全國進出口貿易統計 | Playwright實測顯示資料月「2026-06」 |
| 10 | 經濟部工業生產指數 | `data/industrial_production.json` | 市場頁·台股·工業生產指數 | Playwright實測顯示資料月「2026-07」 |
| 4 | FRED擴充 | 未接入 | — | 待總司令裁示是否同意金鑰上傳GitHub Secrets（見上方說明） |
| 10（子項） | 外銷訂單金額 | 未接入 | — | 待後續輪次查證跨產品資料集加總邏輯（見上方說明） |

每一列的「回報一個」對應紀錄見`PENDING_QUEUE.md`「源頭二.3」逐項條目與
各自獨立的git commit（`92d23a41`/`071ac586`/`b7dd6113`/`e7e31a81`/
`8fd1293b`/`34c33c96`/`c8e9e779`等，第1/2名為更早的cycle所做）。

**本節誠實揭露**：表格「資料日期驗證方式」欄裡的Playwright/本機實測結果
引用自各自完成當下的紀錄，本節（源頭二.5）本身**未重新逐一實測**（純彙整
既有證據，非重新驗證一輪）；若要重新逐一驗證，需要另開一輪工作單位。

**源頭二（全網第一手公開源極限盤點）至此五個子項狀態**：二.1完成、二.2因
robots.txt合規問題中止待裁示、二.3前10名已處理（2項待總司令裁示/後續研究）、
二.4完成、二.5（本項）完成。`node scripts/smoke_test.mjs` 45/46 PASS
（僅#39既有已知紅燈，本項純文件彙整未動任何`data/`或`index.html`）。
