# 主動式ETF 逐家投信查證表（16家發行機構，v2）

> 2026-09-26 對應 `PENDING_QUEUE.md`「資料源.主動ETF」條目。
> **v2 取代同日互動視窗 CC 寫的初版**（初版逐家「持股頁：未找到」，且把
> 待售網域 `www.fsitc.com` 誤當成第一金投信官網，見第 4 節更正）。
> **只查證、不抓取任何持股資料、不建收集器。** 沒有下載任何持股資料，
> 沒有呼叫任何持股／淨值 API，沒有寫入 alpha.db。
> 查證方式：curl（UA `AlphaResearch/1.0 (compliance verification)`，每次請求
> 間隔 ≥3 秒）＋WebFetch＋WebSearch；由 4 個子任務各查 4 家並行，我整合。
> **遇到 WAF（403／302 Security Redirect）一律停手記錄，不換 UA、不繞過。**
> 不使用 etfshenteam／etfinfo.tw／zdsetf／CMoney／MoneyDJ 等第三方彙整站的資料
> （只用來找投信官網網址）。
> 凍結.二仍生效：本文件不產生任何 alpha 試驗。2025-05 以來歷史落在 holdout，
> 一律不得回測，只做前瞻收集與紙上追蹤。

## 0. 完整清單（來源：TWSE ISIN 系統，官方原始層）

`isin.twse.com.tw/isin/C_public.jsp?strMode=2`（上市）／`strMode=4`（上櫃）。

**⚠️ 更正互動視窗初版的數字**：初版寫「上市32＋上櫃7＝39檔」。本輪
重新抓取並用程式計數，**上市 33 檔＋上櫃 7 檔＝40 檔**（代號清單本身沒錯，
是加總寫錯）。每投信檔數（依下表）加總同為 40。

| 投信 | 檔數 | 代號 |
|---|---|---|
| 國泰 | 1 | 00400A |
| 摩根 | 2 | 00401A、00989A |
| 安聯 | 3 | 00402A、00984A、00993A |
| 統一 | 5 | 00403A、00981A、00988A、00411A(櫃)、00987D(櫃) |
| 聯博 | 3 | 00404A、00984D、00980D(櫃) |
| 富邦 | 3 | 00405A、00982D、00983D |
| 中信 | 4 | 00406A、00983A、00995A、00981D(櫃) |
| 第一金 | 3 | 00407A、00408A、00994A |
| 復華 | 4 | 00409A、00991A、00986D(櫃)、00998A(櫃) |
| 永豐 | 1 | 00410A |
| 野村 | 3 | 00980A、00985A、00999A |
| 台新 | 2 | 00986A、00987A |
| 元大 | 1 | 00990A |
| 群益 | 3 | 00982A、00992A、00997A |
| 兆豐 | 1 | 00996A |
| 貝萊德 | 1 | 00985D(櫃) |

（發行投信歸屬取自 ISIN 名稱與各投信官網頁面；00407A／00408A 在 ISIN 名稱
上看起來像同名，是否兩檔皆屬第一金**未逐一核對**。）

## 1. 判定規則（沿用裁示，不放寬）

- **允許**：robots 對持股頁所在路徑明確 Allow，**且**條款讀過原文、沒有禁止程式讀取／重製。
- **不明**：robots 沒有規則／被 WAF 擋／回 SPA 首頁殼、或條款頁讀不到。**不明一律視同禁止**。
- **禁止**：條款原文明文禁止（重製／轉載／爬蟲／機器人／須書面授權）。
- SPA 首頁殼、robots 404、「沒有 `User-agent: *` 段」都**不算明確允許**。

## 2. 逐家查證表（查證日 2026-09-26）

| # | 投信 | 每日持股揭露頁（格式） | 歷史日期 | robots.txt 實測 | 條款原文（與自動讀取／重製有關） | 判定 |
|---|---|---|---|---|---|---|
| 1 | 國泰 | `www.cathaysite.com.tw/ETF/detail/EEA?tab=etf3`（Angular SPA；有「持股權重」與「匯出 Excel」）。後端 `cwapi.cathaysite.com.tw/api/ETF/GetETFDetailStockList`（**僅記錄端點存在，未呼叫**） | 不明 | 三次結果不一致：curl 宣告 UA 讀到 404、先前記錄 403（Akamai）；WebFetch 商品頁 403，**停手** | 讀到三份法務文字（個資約定／隱私／ETF 警語）無相關條文；持股頁須按「同意」的免責條款全文**未取得** | **不明→禁止** |
| 2 | 摩根 | `am.jpmorgan.com/tw/zh/asset-management/twetf/…#/portfolio`（HTML 分頁）＋PCF xlsx 靜態檔（檔名為 `…pcf_updates_<代號>.xlsx`，疑似單一持續更新檔，非按日存檔） | 不明 | `am.jpmorgan.com` 200：同時符合 `Allow: /*/*/asset-management/` 與 `Disallow: /*/asset-management/`，較長規則優先→傾向允許但模稜兩可；帶 `?q=` 被禁 | **原文**（`am.jpmorgan.com/tw/zh/asset-management/per/terms-of-use/`）：「未經我們事先明確的書面許可，您不得使用任何網路機器人、網路爬蟲、其他自動設備或手動流程來監視或複製我們的網頁、資料或其中內容」 | **禁止** |
| 3 | 安聯 | `etf.allianzgi.com.tw/etf-info/E0001?tab=1`（SPA；「持股比重」分頁＋「申購買回清單」可選日期）；資料 API 在第三方主機 `allianzetf.webtech888.com/webapi/`，需先取 AntiForgeryToken（**不碰**）。程式碼註明部分持股僅以月報提供 | 申購買回清單有日期選擇器，回溯範圍不明 | `tw.allianzgi.com` 200，只擋 sitecore 等後台路徑；`etf.allianzgi.com.tw/robots.txt` 回 SPA 首頁殼＝實際無 robots | **原文**（`tw.allianzgi.com/zh-tw/compliance/terms-of-use`）：「使用者未經本公司書面同意，不得就此等資料為任何利用。」；頁尾「不得轉載」 | **禁止** |
| 4 | 統一 | `www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW`（00981A；持股嵌在 HTML `data-content`，需先收 cookie 才不會 302 迴圈）。代號對應：00981A=49YTW、00988A=61YTW、00403A=63YTW、00411A=64YTW、00987D=65YTW | 不明（有 SD/ED 欄位，用途未確認） | 帶 cookie 讀到 200 但內容是「頁面不存在」HTML 殼＝實際無 robots | **原文**（`…/news/info/4705?tid=57`）：「任何人未經同意，不得將網站全部或部分內容轉載於任何形式媒體。」；「隱私權政策」「風險聲明」JS 載入**未取得** | **不明→禁止** |
| 5 | 聯博 | `www.abfunds.com.tw/zh-tw/etfs/pcf.TW00000404A5.html`（申購買回清單，表格 JS 動態載入，端點未找到） | 不明 | `www.abfunds.com.tw/robots.txt` 302→`abcomredirect.alliancebernstein.com/robots.txt` 404 | **原文**（`…/zh-tw/terms-of-use.html`）：「本網站的內容皆不可以任何形式拷貝、複製、重新刊載、上載、刊登、傳送或分發。您得下載本網站內容，且須保留所有著作權…聲明。」——前後矛盾（禁複製但允許下載），無爬蟲字眼 | **不明→禁止** |
| 6 | **富邦** | `websys.fsit.com.tw/FubonETF/Trade/Assets.aspx?stkId=00405A&ddate=YYYY/MM/DD&lan=TW`（伺服器端渲染 HTML；欄位：代碼／名稱／股數／金額／權重）；另有 `Pcf.aspx`。00405A、00982D、00983D 三檔（後兩檔未實際請求） | **有**：`ddate` 參數實測可取 2026/06/15（00405A 於 2026/06/09 上市）；更早未測，**至少回溯 3 個多月**。請求 `ddate=2026/09/25` 回傳的資料日期是 2026/09/24（日期取自頁面資料本身） | `websys.fsit.com.tw/robots.txt` 200：`User-agent: *`／`Disallow: /`／`Allow: /Event`／`Allow: /FubonETF`——**`/FubonETF/Trade/` 明確 Allow**。（`www.fubon.com/robots.txt` 導向 not_found；`etrade.fsit.com.tw` 與持股頁無關） | ETF 投資網頁尾只連到隱私權／資安／個資／洗錢防制／消費者保護，**沒有使用條款頁**。唯一重製句在投信首頁（`fubon.com/asset-management/`）風險揭露：「本文內容非經本公司同意請勿為任何重製、轉載、散布、改作等侵害智慧財產權或其他權利之行為」——範圍是「本文內容」（投資評論），無爬蟲字眼。`footer?type=privacy` 彈窗 JS 載入**未取得** | **有條件允許**（見第 3 節） |
| 7 | 中信 | `www.ctbcinvestments.com/Etf/<內部基金ID>/Info`（Vue SPA；「持股」分頁只顯示前十大＋產業配置，非完整持股）；「申購買回清單」路由存在，內容未驗證。API `www.ctbcinvestments.com.tw/API/{method}` 需 token（**不碰**） | 不明 | 兩個網域皆 200：`User-agent: *`／`Allow: /` | **原文**（`/Privacy` 第七節，讀自 JS bundle）：「非經本公司授權使用或同意，本網站資料均不得以任何形式、利用任何方式予以重製、轉載。」 | **禁止**（保守；robots 允許但條款涵蓋網站資料） |
| 8 | 第一金 | `www.fsitc.com.tw/FundDetail.aspx?ID=182`（00994A；ASP.NET WebForms，有「資料日期」欄與「查詢」按鈕；讀到「您查詢的日期無資料」，完整每日持股是否揭露於此**未驗證**） | 有日期查詢欄，範圍不明（未觸發 postback） | `www.fsitc.com.tw/robots.txt` 回 200 但內容是 404 錯誤頁 HTML（夾帶 `_Incapsula_Resource`＝Imperva 防護）＝無有效 robots。**⚠️ `www.fsitc.com` 是 GoDaddy 待售網域，不是第一金官網，其 `Allow: /` 與 `LLM-Policy` 對第一金無效（更正初版第 8 列）** | **原文**（`FooterLink.aspx?ID=1007`「使用本站政策」）：「非經本公司書面授權同意，不得以任何形式轉載、傳輸、傳播、散布、展示、出版、再製或利用【第一金投信理財網】內容的局部、全部的內容，用以賺取利益」——有「用以賺取利益」限定語，是否涵蓋非營利內部研究屬法律解讀 | **不明→禁止** |
| 9 | 復華 | `www.fhtrust.com.tw/ETF/etf_detail/ETF23`（00991A；HTML＋「檔案下載」→`/api/assetsExcel/ETF23/20260924`，形式 `/api/assetsExcel/{ETF代號}/{yyyymmdd}`，**格式推測 Excel、未驗證**）。頁碼：00409A=ETF26、00998A=ETF24、00986D=ETF25 | 日期選擇器 `data-min="1998/01/01"` 只是 UI 下限，實際不明 | 200，全文只有 `User-agent: GPTBot`／`Disallow: /`，**無 `*` 段**（沒寫≠允許）。第一次探測連線失敗為暫時性 | 頁尾「重要聲明」JS 渲染，內文兩次嘗試皆 302 回首頁，**未取得**（fail-closed，未繞過）；全站警語 `/api/warning` 只有基金風險與指數授權聲明，無爬蟲／重製條文 | **不明→禁止** |
| 10 | 永豐 | `sitc.sinopac.com/SinopacEtfs/Etfs/Pcf/00410A`（HTML 表；POST 表單 `fundId`／`hDate`；「資料下載」按鈕僅提供歷史日期，格式未驗證） | 有歷史下載功能，回溯範圍不明 | `sitc.sinopac.com`、`/SinopacEtfs/`、`www.sinopac.com` 三個 robots 皆 404 | **原文**（隱私權保護政策「七、智慧財產權」）：「若未經得永豐投信之合法授權，任何人不得基於任何目的或理由，透過自行重製、傳輸、編輯、改寫運用等各項形式使用本網站資訊。」 | **禁止** |
| 11 | 野村 | `www.nomurafunds.com.tw/ETFWEB/product-description?fundNo=00980A`（Angular SPA）；前端 JS 可見 `POST /API/ETFAPI/api/Fund/GetFundAssets`（`FundID`,`SearchDate`）與 `getExcel()`（**僅讀原始碼，未呼叫**） | `SearchDate` 參數暗示可指定日期，回溯不明 | `www.nomurafunds.com.tw/robots.txt` 回 SPA 首頁 HTML 殼＝無 robots；`money.nomurafunds.com.tw` 有真 robots（全部允許）但持股頁不在該主機 | **原文**（`…/activity/edm/index.html` 頁尾）：「非經書面授權，不得轉貼、節錄或轉載於任何形式媒體。」`/ETFWEB/` 自身頁尾條款**未取得** | **不明→禁止** |
| 12 | 台新 | `www.tsit.com.tw/ETF/Home/ETFSeriesDetail/00987A`（00986A 同路徑；伺服器渲染 HTML 持股權重表）；`/ETF/Home/Pcf` | 頁面 `PUB_DATE` 唯讀，未見日期選擇入口，不明 | 200，只有 Googlebot／AdsBot-Google 兩段，**無 `*` 段**（持股頁路徑不在其 Disallow 內，但沒寫≠允許）；`/active/` 實測 403 | 隱私權頁（`/Home/FooterPrivate`）全文無相關條文；專門使用條款頁**未取得** | **不明→禁止** |
| 13 | 元大 | `www.yuantaetfs.com/product/detail/00990A/ratio`（SSR，持股嵌 HTML，有「匯出 excel」按鈕；最新資料日期 20260924）；PCF：`/tradeInfo/pcf/00990A` | PCF 日期框 `min="2013-02-01"`（疑全站通用設定，不代表 00990A 可回溯），實際不明 | `yuantaetfs.com` 200 `Allow: /`；`yuantafunds.com` 只有 `DisAllow: /mrFund`（拼字非標準，多數解析器視同 Disallow，只擋 /mrFund，不算明確允許） | **原文**（`openweb.yuantafunds.com/privacy/`）：「非經本公司授權使用或同意，此處資料均不得利用電子、機械、影印、錄音或任何形式、方法予以重製、轉載或製作衍生物等。」（「此處資料」範圍有歧義）；`yuantaetfs.com/Q&A/legal` JS 渲染**未取得** | **不明→禁止** |
| 14 | 群益 | `www.capitalfund.com.tw/etf/product/detail/399/hold`（00982A；Angular SPA，前端呼叫 `CFWeb` API；ETF 持股實際端點**未確認**）；`.../399/buyback` | 持股頁 JS 看似只取最新一天，不明 | 200 `User-agent: *`／`Allow: /`（站前有 Imperva，我的請求未被擋） | 《重要事項》頁（`/capital/other/statement`）為個資／隱私／App 權限／警語，**無**自動讀取或重製條文；**找不到**專門使用條款頁（沒找到≠沒有）；頁尾僅 © 聲明 | **不明→禁止** |
| 15 | 兆豐 | `www.megafunds.com.tw/MEGA/etf/trade_pcf.aspx`（ASP.NET POST 表單，`qdt` 日期欄＋「持股權重」表，HTML；00996A=`fund_id=23`）。（募集期行銷頁 `project.emega.com.tw/etf_ipo/00996A/` 不是持股頁） | 有日期選擇器，範圍不明（未送出查詢） | `megafunds.com.tw/robots.txt` 404；`project.emega.com.tw`／`www.emega.com.tw` 皆導向首頁＝無 robots | 隱私權聲明（`/MEGA/footer/privacy.aspx`）關鍵字掃描（著作權／重製／轉載／自動／擷取／爬／機器人）無命中；專門使用條款頁**未取得** | **不明→禁止** |
| 16 | 貝萊德 | `www.blackrock.com/tw/products/349339/`（00985D）——請求回 **403 Akamai，停手**；格式／端點／歷史全部**未驗證** | 不明 | `blackrock.com/robots.txt` 200（全球共用）：`User-agent: *` 未涵蓋 `/tw/`；僅對 `Brightbot 1.0` 全禁 | **原文**（`/tw/terms-of-use-noframe`）：「該資料不得以任何方式重製、散佈、傳送予他人或整理納入任何其他資料庫或資料。」 | **禁止** |

## 3. 判定彙總與唯一候選

| 判定 | 家數 | 投信 |
|---|---|---|
| 允許（有條件） | 1 | 富邦（3 檔） |
| 禁止（條款原文明禁） | 5 | 摩根、安聯、中信、永豐、貝萊德 |
| 不明→視同禁止 | 10 | 國泰、統一、聯博、第一金、復華、野村、台新、元大、群益、兆豐 |

**條款原文全部讀到的家數只有 6 家**（摩根、安聯、永豐、貝萊德、中信、富邦）；
其餘 10 家至少有一份條款頁 JS 渲染或找不到入口而未取得，判「不明」是
**工具讀不到**造成，不代表條款一定沒有限制。

### 富邦為何是「有條件允許」而不是「允許」

- **支持允許**：持股頁所在主機 `websys.fsit.com.tw` 的 robots 對 `/FubonETF`
  **明確 Allow**；資料為伺服器渲染 HTML、可用 `ddate` 查歷史（≥3 個月）、
  資料日期取自頁面本身；沒有任何網站專屬使用條款禁止程式讀取。
- **殘餘不確定性**：(1) 投信首頁有一句「請勿為任何重製、轉載、散布、改作」，
  範圍寫「本文內容」，未明說是否涵蓋持股表；(2) 沒有網站專屬使用條款可對照，
  「沒有禁止條文」是缺席證據，不是明文授權；(3) `footer?type=privacy` 彈窗
  內文未讀到；(4) 只覆蓋 3 檔／40 檔，且 00982D／00983D 未實際請求驗證。
- **依 CLAUDE.md 白名單第 6 條（法遵疑慮）與「裁示：不明一律視同禁止」，
  收集器（裁示第 3 點）本輪不建。** 提請總司令二選一：
  ①接受殘餘不確定性，授權對富邦 3 檔建收集器（每日 1 次、每檔間隔 ≥3 秒、
  誠實 UA、原始回應存檔、交易日取自頁面資料日期）；
  ②先發書面詢問富邦投信再建。**[自行裁量]** 本輪選擇「不建、等裁示」，
  可被總司令推翻，推翻成本只是多等一輪。

## 4. 相對初版與 DevQueue 先前查證的更正

1. **第一金**：初版與 `ACTIVE_ETF_HOLDINGS_PROPOSAL.md` 引用的 `www.fsitc.com`
   是 GoDaddy 待售網域，第一金官網是 `www.fsitc.com.tw`（robots 為 404 頁＋
   Imperva 痕跡）。初版「robots 允許但 ToS 禁止」的敘述要改成「robots 無效
   ＋ToS 須書面授權（限定語『用以賺取利益』）」，判定仍是不明→禁止。
2. **檔數**：39 → 40（見第 0 節）。
3. **持股頁**：初版 16 家全標「未找到」；本輪找到 15 家的持股／PCF 頁網址
   （貝萊德被 403 擋下未能確認），列於第 2 節。
4. **國泰 robots**：初版記 403；本輪宣告 UA 讀到 404，兩次結果不同（WAF 對不同
   UA 行為不同），仍不能當允許。
5. **統一 robots**：初版記「302 自我迴圈」；帶 cookie 後為 200 的「頁面不存在」
   HTML 殼＝無 robots。
6. **摩根**：初版「條款未讀原文」；本輪讀到原文，**明文禁止網路機器人與爬蟲**。
7. **中信**：初版條款只拿到標題；本輪從 JS bundle 讀到「不得重製、轉載」原文。
8. **永豐、貝萊德、聯博、統一、野村、元大**：本輪補讀到條款原文（見第 2 節）。

## 5. 替代方案（對「不明／禁止」的家數）

依「取得方式鐵律」：不繞過、不用第三方彙整站、付費牆標「待採購」。
1. **書面詢問投信**（客服信箱／電話，多家條款自己寫「書面授權同意」即可）：
   需總司令本人身分（白名單第 2 條）。建議優先問**規模最大**的幾檔所屬投信
   （例如復華 00991A 資產規模 788.98 億元，見 DevQueue 初版引用之官方資料頁；
   該數字取自搜尋結果，未獨立驗證），一封信問完「程式每日讀取＋保存」。
2. **人工每日下載一次**（總司令自己開網頁按下載）：我方只處理檔案。
   代價：人力＋2025-05 以前補不回（且那段本來就不得回測）。
3. **官方彙整層再查一輪**（**尚未做合規查證**）：證交所「ETF e添富」個別頁
   （`twse.com.tw/zh/ETFortune/etfInfo/<代號>`）、櫃買中心主動式 ETF 頁、
   `data.gov.tw` 是否上架持股資料集。TWSE 網頁層條款第 6 條禁止自動化下載
   （DevQueue 初版已讀），故 e添富頁**不可直接抓**，只能先查其是否走
   政府資料開放授權端點。
4. 採購：若有投信或資料商正式授權販售，標「待採購」等預算裁示。

## 6. 收集器規格草案（僅在總司令核准第 3 節①後才使用；本輪**未實作**）

- 每日一次，收盤淨值公布後（富邦頁面資料日期落後一天，實測 `ddate=9/25`
  回 9/24，故以頁面資料日期為準，**不用執行日**——避免重蹈 daily_price 錯誤）。
- 每檔間隔 ≥3 秒；UA `AlphaResearch/1.0 (compliance verification)`。
- 原始回應原樣存檔（`data/raw/active_etf/<投信>/<代號>_<資料日期>.html`）。
- 比對持股變化前先做除權息／分割還原（只呼叫 `research/adjust.py`，不修改）。
- 心跳位置：`data/active_etf_holdings_status.json`（尚不存在，屬未來工程）。
- 試跑 5 個交易日並附抽樣核對後才納入排程（裁示第 5 點）。

## 7. 本輪已知缺口（誠實揭露）

- 各家歷史可回溯深度：除富邦外全部「不明」，我沒有對其他家試打歷史日期
  （避免對官方端點造成負擔，也避免下載持股資料）。
- 條款多為 JS 渲染或藏在彈窗，工具（curl／WebFetch 小模型摘要）讀不到，
  「未取得」不等於「沒有」；WebFetch 轉譯內容非逐字元核對 HTML。
- 國泰、貝萊德商品頁被 WAF 擋下，格式／端點／歷史全未驗證。
- 摩根、貝萊德 robots 為全球共用版本，台灣路徑判讀含推論。
- 00407A／00408A 是否皆屬第一金、00982D／00983D 富邦頁面實測，未逐一核對。
- 富邦歷史只測了 2026/06/15 一個舊日期。
- 子任務回報的網域／代號對應（統一 fundCode、復華頁碼、群益內部 ID 399、
  兆豐 fund_id=23）來自各頁面連結或程式碼，未獨立第二次核對。

## 8. 源.二補充查證（2026-09-26，marathon 自走軌，情報帽；只讀條款，未抓任何持股資料）

本節補 v2 缺口，範圍照總司令裁示【源.二】：群益、中信、第一金三家條款，加 data.gov.tw
與官方 OpenAPI 目錄。**所有請求皆單次、間隔 ≥3 秒、UA 為
`AlphaResearch/1.0 (compliance verification; read-only …)`；沒有請求任何持股／PCF 頁。**

### 8.1 三家逐字條款與 robots（原文以「」標示，非摘要）

| 投信 | robots.txt（今日 curl 原始回應） | 條款原文 | 判定 |
|---|---|---|---|
| 群益 | `www.capitalfund.com.tw/robots.txt` 200 `text/plain`，全文：`User-agent: *`／`Allow: /`／`Sitemap: …/sitemap.xml` | 讀了 sitemap（2,815 個網址）中 3 個可能的條款頁：`/capital/other/statement`（v2 已讀）、`/capital/statement`、`/capital/other/protect`（反洗錢）。**三頁皆未見**重製／轉載／自動讀取條文，僅頁尾「©2020 by Capital Investment Trust Corporation. All Rights reserved」。**限制**：後兩頁是 WebFetch 小模型判讀、非逐字元核對 HTML；「沒找到」≠「沒有」。 | **未禁止＋robots 明確允許＝條件式可行**，但見 8.3：持股資料端點未確認、且屬法遵疑慮，**本輪不建收集器** |
| 中信 | `www.ctbcinvestments.com/robots.txt` 200，全文：`User-agent: *`／`Allow: /`（23 bytes） | v2 已讀自 JS bundle（`/Privacy` 第七節）：「非經本公司授權使用或同意，本網站資料均不得以任何形式、利用任何方式予以重製、轉載。」——**今日未重讀**，沿用 v2 原文 | **禁止**（robots 允許不凌駕條款） |
| 第一金 | `www.fsitc.com.tw/robots.txt` 與 **`/llms.txt`**：兩者皆 HTTP 200 但 body 是同一張站內 404 錯誤頁 HTML（表單 action 為 `./llms.txt?404;https://www.fsitc.com.tw:443/llms.txt`，`content-type: text/html`）＝**兩者都不存在**（伺服器把 404 包成 200）。⚠️ 初版引用的 `LLM-Policy`／`Allow: /` 來自 GoDaddy 待售網域 `www.fsitc.com`，對第一金無效（v2 已更正，這裡再確認 llms.txt 同理） | v2 已讀（`FooterLink.aspx?ID=1007`）：「非經本公司書面授權同意，不得以任何形式轉載、傳輸、傳播、散布、展示、出版、再製或利用【第一金投信理財網】內容的局部、全部的內容，用以賺取利益」——今日未重讀 | **不明→禁止**（無 robots、無 llms.txt；條款有「用以賺取利益」限定語，是否涵蓋內部研究屬法律解讀） |

### 8.2 data.gov.tw 與官方 OpenAPI 目錄（三來源查證，結論分級）

依「搜尋紀律：三來源查證」，逐一列出實際看到什麼：

1. **官方 OpenAPI 目錄（機器可讀、最可靠的一項）**：今日下載
   `openapi.twse.com.tw/v1/swagger.json`（「臺灣證券交易所 OpenAPI 1.0」，**143 個端點**）
   與 `www.tpex.org.tw/openapi/swagger.json`（「證券櫃檯買賣中心 OpenAPI 1.0.0」，**225 個端點**），
   以「ETF／持股／成分／投資組合／PCF／申購買回／受益憑證／指數股票」逐端點比對 path 與說明：
   證交所僅有 `/ETFReport/ETFRank`（定期定額交易戶數排行月報，非持股）、
   `/fund/MI_QFIIS_*`（外資持股，非 ETF）；櫃買僅有 `/tpex_opfund_recommended_dealer`
   （**開放式基金**受益憑證造市商，非主動式 ETF 持股）與各指數成分股端點。
   **兩個官方 OpenAPI 皆無主動式 ETF 持股／PCF 端點。**
2. **data.gov.tw 站內搜尋**：搜尋頁是 Nuxt 前端渲染，WebFetch 只拿到空殼（「無資料」）；
   嘗試其前端目錄 API（`POST /api/front/dataset/list`）時，我猜的關鍵字參數
   （keyword／query／q／qs／search／keywords／name）**全部沒有生效**（每次回傳全站
   52,437 筆未過濾），共 4 組關鍵字＋6 個參數名的探測後**停止**——那是未公開文件的
   內部端點，不應繼續猜。改用 WebSearch 限縮 `site: data.gov.tw`：搜尋引擎回傳的相關
   資料集只有「定期定額交易戶數統計排行（區分股票及ETF）」（dataset/55021 是個股期貨
   交易量）、集保戶股權分散表（dataset/11452）等，**沒有任何主動式 ETF 每日持股資料集**。
   **結論分級**：搜尋引擎層「未見」；站內檢索層「**無法有效查詢，尚未證明沒有**」——
   這一項**不得下「不存在」的結論**，需總司令在瀏覽器手動搜尋一次，或等有文件的 API 參數。
3. **社群／GitHub（其他人怎麼取得）**：WebSearch 見 `nctuwanglin/active-etf`（自述持股
   取自「各投信官網公告的 PCF」）、`kevin12596/00981a`（統一 ezmoney，Playwright 爬蟲）、
   `solymx/tw-etf-pages`（統一＋復華）、`jasperchen111/ETF`（MoneyDJ 前十大）。
   **這證明技術上可行、且有人在做，但不構成授權**——依「取得方式鐵律」，別人在爬
   不改變各家條款的文字，我方不以此為依據。

**data.gov.tw 部分的最終判斷**：官方 OpenAPI 兩個目錄查無；data.gov.tw 站內檢索未完成
（工具限制）。**不宣稱「政府資料開放平臺沒有」**，登記為待總司令手動搜尋一次的項目。

### 8.3 對裁示第 4 點的判斷（能不能建收集器）

裁示第 4 點：「條款明文允許或未禁止、且 robots 允許者，才可依原裁示建立收集器。」

- **群益**是三家中唯一同時滿足「robots 明確 Allow」＋「已讀條款頁未見禁止」的。
  **但本輪仍不建收集器**，原因（`[自行裁量]`，總司令可推翻）：
  ① 條款頁只有小模型判讀，未逐字元核對；② 持股資料端點**尚未確認**（Angular SPA，
  實際 `CFWeb` API 路徑未讀）——建收集器前得先讀其 JS bundle 找端點，那一步本身
  就是「摸內部 API」，該由總司令先點頭；③ 依白名單第 6 條（法遵疑慮：ToS、爬蟲），
  「未見禁止」是缺席證據，與富邦同級的殘餘不確定性，處理方式與富邦一致（見 v2 第 3 節）。
- 中信、第一金：不符合第 4 點，不建。

### 8.4 詢問信範本

見 `docs/ACTIVE_ETF_INQUIRY_LETTER_TEMPLATE.md`。**CC 不代寄**；寄件人與聯絡方式由總司令
自行填入（文件內以中文說明欄位、不放任何看起來像真值的佔位符）。
