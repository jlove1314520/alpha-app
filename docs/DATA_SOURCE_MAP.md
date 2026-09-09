# DATA_SOURCE_MAP.md — 資料源可行性地圖

> 2026-09-08 建立（總司令裁示：查證結論要有固定登記處，**避免日後有人再提一次同一條路**）。
> 這份檔案記「哪些路走得通、哪些走不通、為什麼」。
> **看到某條路標 🔴，不要再重新評估一次，先看這裡的日期與理由。**

## 🔴 走不通：櫃買中心「產業價值鏈資訊平台」（ic.tpex.org.tw）

**查證日：2026-09-08。詳見 `docs/TPEX_INDUSTRY_CHAIN_GATE.md`。**

| 查證項 | 結果 |
|---|---|
| `ic.tpex.org.tw/robots.txt` | **302 Security Redirect、0 位元組，不存在** |
| `www.tpex.org.tw/robots.txt` | **HTTP 200 但內容是 404 頁**（「200 不等於成功」的老陷阱） |
| 使用條款 | **明文禁止爬蟲**（見下） |
| TPEx 官方 OpenAPI（225 端點） | **無價值鏈端點** |
| data.gov.tw | **無此資料集**，只有產業別（已有） |

條款原文：
> 「禁止透過包括但不限於自動化裝置、指令碼、自動程式、**蜘蛛程式、爬蟲程式**
> 或擷取程式等方式下載本網站之軟體或資料。」

**間隔拉到 3 秒也不改變它被禁止——速率不是重點，「用程式下載」本身就是被禁的行為。**

**唯一正途**：去信櫃買申請書面授權（條款寫「未經書面同意」不得重製，
反過來說書面同意是存在的途徑）。需總司令具名申請，Claude 不能代辦。

## 🔴 走不通：MOPS 公開查詢頁（mopsov.twse.com.tw）

**查證日：2026-09-08。** 這是總司令【裁示二】指定的替代路徑之一，**同樣不可走**。

```
GET https://mopsov.twse.com.tw/robots.txt   → HTTP 200

User-Agent: *
Disallow: /

User-Agent: bingbot
Allow: /mops/web
```

**除 bingbot 外，全站 `Disallow: /`。我們不是 bingbot，因此 MOPS 查詢頁不得程式取用。**

（`mops.twse.com.tw/robots.txt` 回 404、`mopsfin.twse.com.tw/robots.txt` 回 404 的
HTML 頁；但 `mopsov` 這台明確拒絕，而 `t05st03` 等查詢頁正是在 `mopsov` 上。）

## 🟢 走得通：TWSE 主站（www.twse.com.tw）

```
GET https://www.twse.com.tw/robots.txt   → HTTP 200

User-agent: Googlebot / Googlebot-News / OAI-SearchBot / GPTBot
Allow: /

User-agent: *
Disallow: /epaper/
Disallow: /FTSE/
Allow: /
```

**除 `/epaper/` 與 `/FTSE/` 外全部允許**，且明列允許 GPTBot 等 AI 檢索器。
我們既有的 `www.twse.com.tw/rwd/zh/fund/T86`（三大法人）**在允許範圍內，合規**。

註：TWSE 主站是 SPA，著作權/使用條款頁面在無 JS 時只回 747B 空殼，
無法以純 HTTP 取得條款全文——**已知限制，誠實記錄**。
robots.txt 是目前能取得的最明確意思表示。

## 🟢 走得通：TWSE／TPEx OpenAPI

`https://openapi.twse.com.tw/v1/`（143 端點）、
`https://www.tpex.org.tw/openapi/`（225 端點）。官方發布，設計上就是給程式讀的。

**但要知道它們沒有什麼**（2026-09-08 全表掃描確認）：
- ❌ 產業價值鏈上/中/下游分段
- ❌ **主要商品或服務項目及其營業比重**（368 個端點全掃，沒有）
  - `t187ap03_L`（上市公司基本資料，1,094 筆）只有**產業別**，無營業比重
  - `t187ap01` 是「各營業別**人員數**」（券商員額），**名稱容易誤中關鍵字，不是營收結構**

## 🔴 走不通：Stooq（已下市美股價格）

**查證日：2026-09-08。詳見 `docs/US_PRICE_SOURCES.md`。**
2026-03 起改 API key 制，key 需**人工過 CAPTCHA** 取得。資料本身免費無訂閱費。
**程式解 CAPTCHA＝禁止；人親自到官網領 key＝合規**，待總司令決定是否領。

## 🔴 更正：Stooq 的領 key 步驟我寫錯過（2026-09-08）

先前寫的逐步指南與實際頁面不符（總司令實測回報「根本就沒有你說的那些」）。
那不是親眼看到的畫面，是從第三方說明推得的，卻寫成了步驟一二三的形式——
**那個形式本身就在暗示已驗證，是誤導**。詳見 `docs/US_PRICE_SOURCES.md` 末段。
**Stooq 維持 🔴，除非總司令另有指示，不再嘗試。**

## 🟡 部分可用：Alpha Vantage（已實測，2026-09-08 key 已領）

**交叉驗證 ✅**：AAPL 與 yfinance 共同 100 日，收盤**差異率 0.0000%**。
**下市名冊 ✅**：`LISTING_STATUS` 免費可用，含 `delistingDate`。
**下市股價格 🟡**：TWTR（末日 2022-10-28、53.70）與 ATVI（2023-10-13、94.42）**正確**；
FRC 未收錄；**SIVB 是陷阱**——回傳的是破產後 OTC 空殼（0.006 美元、區間 2026 年），
不含 2023-03 崩潰期，**直接用會注入假的 −99.99% 報酬**。
**致命限制 ❌**：`outputsize=full` 與 `TIME_SERIES_DAILY_ADJUSTED` 皆為**付費**，
免費層只給**近 100 個交易日**且**未除權息調整**。
**100 天不足以回測**，故**未補起存活者偏誤缺口**，付費層標「待採購」。
客戶端與額度紀律：`research/av_price_client.py`（每日 22 次硬上限，用完誠實拒絕）。

## ~~🟡 未評估完：Alpha Vantage（已下市美股價格）~~

`LISTING_STATUS` 免費可用（demo key 實測回 426 筆真 CSV 含 `delistingDate`）；
價格序列需免費 key（填 email、**無 CAPTCHA**）。**待總司令決定是否領 key。**

## 🔴 不採用：鉅亨網 RSS

**查證日：2026-09-08（建置一.1）。** 兩個公開 RSS 路徑皆 404，
唯一可通的是 `api.cnyes.com` 的**站台後端 API**，違反取得方式鐵律「不撈 App／站台後端」。
日後若恢復公開 RSS 再加回。

## 🔴 本階段不接：LongPort OpenAPI（長橋）

**查證日：2026-09-07（Cowork）。總司令 2026-09-08 裁示本階段不開戶、不接入。**
- 行情涵蓋港股／美股／A 股，**不涵蓋台股**——對我方最缺的台股軌零幫助。
- 「免費」需分層：接口不另收開通費，但行情訂閱費在 App「行情商城」另計。
- 須完成開戶＋開發者認證才取得 token。速率：行情每秒 10 次、並發 5。
- 財報／估值／分析師評級屬**券商加工資料、無申報日可做 PIT 對齊**，
  **回測一律以 SEC EDGAR XBRL companyfacts 為準，不得改用券商衍生資料。**
- 僅在「App 要對外提供美股即時報價且本機 IBKR 無法修復」時才重新評估。

## 🟡 部分可用：美股軌對應 `MARATHON_PROTOCOL.md` 0a 節四條結構性優勢方向的資料源（2026-09-08 馬拉松第450輪查證）

**查證日：2026-09-08。三來源查證，對應 `US_MARATHON_STATE.md` round448「下一輪US軌接手」交辦事項。**
背景：0a 節四條方向（#49隔夜vs日內、#50容量受限小型股、#51強制交易者事件、#52事件反應速度）
原本以台股資料源設計，本輪查證美股是否有對應資料源可跟進。

### #52 事件反應速度（對應 MOPS 重大訊息）→ 🟢 有對應且免費，比台股更好

**SEC EDGAR 有官方免費即時申報 feed，時間戳精度到秒級**，比 MOPS T+0/T+1 更細：
- 官方文件：`https://www.sec.gov/edgar/sec-api-documentation`、
  `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
  （`data.sec.gov` RESTful JSON API；daily/quarterly index 含 html/xml/json 四種格式）
- 社群實測：Medium 文章與 GitHub（`SECurityTr8Ker` 專案監控 8-K RSS）皆證實
  metadata 在 RSS 更新前約 20 秒即可公開取得，內容約提早 2 秒
- 反推證據：多家商業資料商（sec-api.io、Tradefeeds、edgar.tools）把「即時 SEC 申報流」
  當商品賣，佐證這是有價值且被廣泛使用的官方免費資料

**結論**：8-K（重大事件揭露）是美股「事件反應速度」假說最直接的對應資料源，
且完全免費、官方、不需繞過任何限制。**這是四條方向裡US軌最有機會的一條**，
下一步可設計 8-K 申報時間戳 vs 次日/當日股價反應的事件研究，非本輪範圍
（本輪僅完成資料源查證，設計與回測留給下一個工作單位）。

### #51 強制交易者事件（對應台股融券強制回補/現增/CB轉換價重設）→ 🟡 部分對應，機制不同

三來源查證：
- FINRA 官方（`https://www.finra.org/finra-data/browse-catalog/equity-short-interest`）：
  空頭部位資料**每兩週**公布一次（結算日後第2營業日18:00 ET），**遠比台股融資券
  的日頻粒度粗**，不足以支撐「事前已知日期、被迫交易」這種事件研究設計
- 官方規則文件（SEC Release 34-98738／34-94313）：2024年新規要求機構法人申報空頭
  部位，但申報對象是機構本身的部位，不是「強制回補事件」的日期清單
- 最接近的美股類比是**指數成分股調整（S&P 500 季度／Russell 半年度重新平衡）**：
  生效日期**官方提前公告**（S&P 每季第3個週五生效、Russell 6月/12月），且會強迫
  被動基金在生效日**不管價格都要交易**——這個機制性質上更接近台股的「強制交易者」
  而非融券回補本身。三方確認來源：FTSE Russell 官方新聞稿（`lseg.com`）、
  S&P 官方規則說明、學界既有大量「index effect」文獻（本輪僅確認資料源存在，
  未查證文獻結論是否已被套利掉——那是另一個工作單位）

**結論**：融券強制回補的美股對應資料源**沒有找到**（FINRA 頻率太粗），但指數
重新平衡是一個機制不同、但同屬「事前已知、被迫交易」家族的可查證方向，
效果是否已被市場套利掉需另外查證，**不在本輪下結論**。

### #50 容量受限小型股（對應逐筆tick估真實滑價）→ 🔴 免費源查無，需採購

三來源查證：
- EODHD 官方定價頁（`eodhd.com/pricing`）：tick-by-trade 資料屬付費方案，
  免費層僅 20 次/日 EOD 呼叫且僅示範 5 檔（`AAPL`/`TSLA`/`VTI`/`AMZN`/`BTC-USD`）
- Databento 官方（`databento.com/stocks`）：全美15家交易所 order book 深度＋
  NBBO，明確標示「無即時授權費」但仍是計量付費（非全免費）
- Finazon 官方定價：個人非商業用途 $4/月起，商業用途 $2,000/月＋交易所費
  $2,500~10,000

**結論**：美股逐筆 tick 資料**沒有查到全免費且覆蓋小型股的來源**，比照
`CLAUDE.md`「取得方式鐵律」標記**待採購**，不找替代爬法。若要繼續 #50 美股版，
需先向總司令提案採購方案（EODHD／Databento／Finazon 三選一，價格已如上列），
本階段不採購。

### #49 隔夜 vs 日內拆解 → 未查證（已有既有設計可直接沿用，非本輪範圍）

---

## 🟢 既有可用：本 session 的 IBKR MCP 工具

`get_price_snapshot`／`get_price_history`／`search_contracts`，
可作為美股報價與歷史的**交叉驗證來源，不需額外開戶**。
**限制**：對已下市美股 **0/4 覆蓋**（TWTR／SIVB／FRC／ATVI），
AAPL 對照組正常，故為下市股特有限制而非工具問題。

---

## 歷史新聞回補：**行不通**，但每日捕獲量可以提高約 20 倍（2026-09-09 查證）

**問題**：題材驗證的瓶頸已確認是新聞量——180 篇內文只萃出 12 句可用證據、
7 檔成員，撐不起 123 個題材。所以查「能不能回補歷史新聞」。

### 查證結果

**兩家都在 robots.txt 主動宣告 sitemap**（那是明確邀請爬蟲索引，性質上最沒疑慮）：

| 來源 | Sitemap | 涵蓋範圍 |
|---|---|---|
| 中央社 | `sitemap_fromRemote_cfp.xml`、`GoogleNewsSitemap_fromRemote_cfp.xml` | **998 則，2026-09-04 ~ 09-09（6 天）** |
| Yahoo 股市 | `news-sitemap-index.xml`（3 天）、`sitemap-index.xml`（7 天） | 子檔**檔名帶日期** |

**Yahoo 的子 sitemap 檔名帶日期，一度看起來可以回補歷史**，實測：

```
news-sitemap-2026-09-08.xml → HTTP 200，1,431 則
news-sitemap-2026-09-01.xml → HTTP 404
news-sitemap-2026-08-15.xml → HTTP 404
news-sitemap-2026-07-01.xml → HTTP 404
news-sitemap-2026-01-15.xml → HTTP 404
news-sitemap-2025-09-08.xml → HTTP 404
```

**只有最近幾天存在，舊日期一律 404。** sitemap 是滾動窗口，不是封存。

### 🔴 結論：歷史回補無合規途徑

兩家的 sitemap 都只保留約 6~7 天。**沒有封存頁、沒有歷史 RSS。**
要拿更久以前的新聞只剩「搜尋引擎快取」或「第三方鏡像」，
兩者都違反取得方式鐵律（不撈鏡像、不繞），**不做**。

### 🟢 但每日捕獲量可以大幅提高

現況是靠 RSS，每次只拿得到最新 20~50 則，累積 30 天才 300 則。
改用 sitemap 可以每天拿到：

| 來源 | RSS（現況） | Sitemap | 倍數 |
|---|---|---|---|
| Yahoo 股市 | 50 則/次 | **1,431 則/日** | ~28× |
| 中央社（全部） | 20 則/次 | **998 則/6 日 ≈ 166 則/日** | ~8× |
| 中央社（財經 afe） | — | **145 則/6 日 ≈ 24 則/日** | — |

**推估**：改走 sitemap 後每日約 1,500 則，30 天累積約 45,000 則，
相對現在的 300 則是 **150 倍**。以目前「180 篇 → 12 句」的產出率外推，
45,000 篇約可產出 **3,000 句題材證據**——那才是能撐起 123 個題材的量級。

**代價誠實揭露**：每日 1,500 篇 × 2 秒間隔 = 約 50 分鐘的抓取時間，
且只有中央社與 Yahoo 在內文白名單內（總司令 2026-09-09 選項 2）。
實際要不要全抓、抓哪些分類，需總司令決定。

### 新聞產出率實測（2026-09-09，取樣 345 篇）

總司令選項 3「先抓一天全量試水溫」的結果。**分來源量是重點**——
兩者產出率差 3.3 倍，這決定常態該抓哪些。

| 來源 | 抓取 | 有內文 | 命中個股 | 有題材句 | 句數 | **每百篇句數** |
|---|---|---|---|---|---|---|
| 中央社財經 | 145 | 145 | 62 | 12 | 17 | **11.7** |
| Yahoo 股市 | 200 | 200 | 153 | 6 | 7 | **3.5** |
| 合計 | 345 | 345 | 215 | 18 | 24 | 7.0 |

**中央社每篇的產出率是 Yahoo 的 3.3 倍**（財經專稿 vs 全分類混雜）。

**但每日推估的結論相反**：

| | 篇/日 | 句/日 | 抓取時間 | 每句成本 |
|---|---|---|---|---|
| 中央社財經 | 24 | **2.8** | 0.8 分鐘 | 0.3 分鐘/句 |
| Yahoo 股市 | 1,431 | **50.1** | 47.7 分鐘 | 1.0 分鐘/句 |

**30 天累積：只抓中央社 85 句、兩家都抓 1,587 句。**

中央社效率高但**量太小**（一天只有 24 篇財經稿）；
Yahoo 效率低但**基數大 60 倍**，貢獻 95% 的證據量。
要撐起 123 個題材，**Yahoo 不可省**——代價是每天約 48 分鐘的抓取。

命中的題材集中在半導體：晶圓代工 10、記憶體 8、IC設計 2，
玻璃基板／PCB／CPO／半導體設備各 1。
**這反映新聞本身的題材分布，不是規則偏誤**——台股新聞就是集中在這些。
冷門題材（探針卡、CCL、鑽針等）要驗出成員，得靠更長的累積時間。

---

## 題材五.1 查證：公司自述產品的三條來源（2026-09-09）

總司令裁示「基礎歸屬改用公司自述產品，新聞只做增量」，並要求**查完先回報再動手**。
以下三件事各列 ≥3 個獨立佐證。**結論：(a)(b) 都被擋死，(c) 可行但工程量大。**

### 🔴 (a) 年報／公開說明書「主要商品之銷售比重」——不可用

| # | 查證點 | 結果 |
|---|---|---|
| 1 | `doc.twse.com.tw`（年報 PDF 的實際主機）robots.txt | **`User-agent: *` → `Disallow: /`**，整站禁止 |
| 2 | `mopsov.twse.com.tw`（MOPS 查詢頁）robots.txt | **`Disallow: /`，僅 bingbot 例外**（2026-09-08 已查證） |
| 3 | TWSE 143 ＋ TPEx 225＝**368 個 openapi 端點全表掃描** | **無「營業比重」、無「主要商品」** |
| 4 | 同上，另找 IFRS 8 營運部門（segment）揭露 | **無**。唯二命中「業務別」的是 `t187ap01`＝**券商業務別人員數**，與營收結構無關 |

**PDF 主機與查詢頁都是 `Disallow: /`，沒有結構化 API。三條路全紅。**

### 🔴 (b) 法說會簡報 PDF ——不可用

簡報 PDF **與年報同在 `doc.twse.com.tw`**，適用同一條 `Disallow: /`。
`events.json` 裡的法說會事件只有**公告標題**（來自 openapi，合規），
但標題只寫「受邀參加 XX 證券舉辦之法人說明會」，**不含任何產品內容**——
2026-09-08 已實測過，那正是 A 級驗不出來的原因之一。

### 🟢 (c) 公司官網產品頁 ——可行，但要逐站查 robots

| # | 查證點 | 結果 |
|---|---|---|
| 1 | 官網網址來源 | `t187ap03_L`（官方公司基本資料，我們已在用）**1,094/1,094 家上市公司都有網址欄位** |
| 2 | 抽樣 robots.txt | 台積電 🟢（33 條 Disallow，非整站）、聯發科 🟢（5 條）、奇鋐 🟢（147 條） |
| 3 | 例外 | 欣興 `unimicron.com` **SSL 錯誤**，無法查證 |

**可行，但每一站都要各自查 robots 與條款**——2,138 家就是 2,138 次判斷，
且各家產品頁結構完全不同，萃取規則無法共用。
這不是「接一個 API」的工作量，是一個獨立的子專案。

### 對題材五驗收指標的影響

總司令設定「先進封裝、玻璃基板、PCB、CCL、散熱、探針卡、AI伺服器 七個各至少 3 檔」。
**用 (a)(b) 達成是不可能的——來源被條款擋死。**
若要達成只剩兩條路：
1. **(c) 公司官網**：可行但需另立子專案，且要逐站合規判斷。
2. **維持新聞路徑但拉長累積時間**：目前 379 篇→6 檔，
   sitemap 每日約 1,600 則，接上排程後 30 天約 45,000 篇，
   以目前產出率外推可到數百檔——但**題材分布仍會偏向新聞常報的半導體**，
   冷門題材（探針卡、CCL）不保證達標。

**這一段是「卡在哪一步」的誠實回報，不是「已完成」。**

---

## 🔴 題材五.3：IBKR 的 `get_company_themes` 不得用於題材庫（2026-09-09 查證）

總司令：「IBKR MCP 的 `get_company_themes` / `get_company_connections`
看起來正好是我們要的，但那是授權資料，進公開 App 等於散布。先查條款，
**在我明確核准前不得寫進任何程式。**」

**已查，未寫任何程式。結論：不可用於對外顯示的題材庫。**

### 三個獨立佐證

**佐證一：非專業訂閱者協議（Non-Professional Subscriber Agreement）**
> Non-Professional Subscribers shall receive Market Data solely for their
> **personal, non-business use** and **shall not furnish Market Data to any
> other person or entity**.

我方帳戶為個人非專業訂閱者。「不得提供給任何其他人或實體」直接涵蓋
「放進公開 App 給人看」。

**佐證二：市場資料協議的通用條款**
> users will **not sell, market, retransmit, publish or redistribute** it in any way,
> unless they have entered into appropriate written agreements with the relevant
> market data providers.

**佐證三：IBKR API 條款（最直接的一條）**
> 「the use of the TWS API as a means of **disseminating information, including
> market data or any other licensed or copyrighted information, to third parties
> or non-registered IB customers is strictly prohibited** without prior written
> approval of Interactive Brokers.」

以及：
> customers agree **not to reproduce, distribute, sell or commercially exploit
> the Information** in any manner without written consent of IB.

### 為什麼「只在內部用、不直接顯示」也不行

有人會想：那我們用 IBKR 的題材資料在內部決定要發布哪些成員，不就沒有散布原始資料？

**不行。** 如果 IBKR 說「台積電屬於 CoWoS 題材」，我們據此在 App 上發布
「台積電屬於 CoWoS」，那**發布出去的正是他們的編纂成果本身**，
只是把出處拿掉了——**這比直接引用更糟，不是更好**。

這與總司令 2026-09-09 對籌碼K線的裁示是同一個判準：
**不抄付費訂閱商品的編纂資料庫。** IBKR 的 themes 也是編纂資料庫，
差別只在我們剛好有帳戶。

### 那 IBKR MCP 還能用在哪

CLAUDE.md 既有規則：**原始交易所資料不得對外轉售，衍生訊號可。**
所以下列用途不受影響（且已在用）：
- `get_price_snapshot` / `get_price_history`：**內部交叉驗證**我們自己抓的價格
- `search_contracts`：確認代號存在性

差別在於：**價格交叉驗證的產出是「我們的資料對不對」這個判斷**（衍生訊號），
不是把 IBKR 的價格本身發布出去。題材歸屬則是**把他們的編纂結果原樣搬走**。
