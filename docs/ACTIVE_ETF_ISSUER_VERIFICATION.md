# 主動式ETF 逐家投信查證表（16家發行機構）

> 2026-09-26 互動視窗CC 產出，對應 `PENDING_QUEUE.md`「資料源.主動ETF」條目。
> **只查證、不抓取任何持股資料、不建收集器。** 沿用並補完 DevQueue 稍早
> （`docs/ACTIVE_ETF_HOLDINGS_PROPOSAL.md`）對其中7家的查證，本文件涵蓋
> 完整16家（依 TWSE 官方 ISIN 系統 `isin.twse.com.tw/isin/C_public.jsp`
> `strMode=2`(上市)/`strMode=4`(上櫃) 撈出的全部39檔主動式ETF反推去重
> 後的發行機構清單）。

## 0. 完整ETF清單（來源：TWSE ISIN系統，2026-09-26查證，官方原始層）

**TWSE上市（32檔）**：00400A主動國泰動能高息、00401A主動摩根台灣鑫收、
00402A主動安聯美國科技、00403A主動統一升級50、00404A主動聯博動能50、
00405A主動富邦台灣龍耀、00406A主動中信台灣收益、00407A主動第一金優
股息、00408A主動第一金優股息、00409A主動復華全球50、00410A主動永豐
科技趨勢、00980A主動野村臺灣優選、00981A主動統一台股增長、00982A
主動群益台灣強棒、00982D主動富邦動態入息、00983A主動中信ARK創新、
00983D主動富邦複合收益、00984A主動安聯台灣高息、00984D主動聯博全球
非投、00985A主動野村台灣50、00986A主動台新龍頭成長、00987A主動台新
優勢成長、00988A主動統一全球創新、00989A主動摩根美國科技、00990A
主動元大AI新經濟、00991A主動復華未來50、00992A主動群益科技創新、
00993A主動安聯台灣、00994A主動第一金台股優、00995A主動中信台灣卓越、
00996A主動兆豐台灣豐收、00997A主動群益美國增長、00999A主動野村臺灣
高息

**TPEx上櫃（7檔）**：00411A主動統一前沿科技、00980D主動聯博投等入息、
00981D主動中信非投等債、00985D主動貝萊德優投等、00986D主動復華金融
債息、00987D主動統一美債量化、00998A主動復華金融股息

**去重後16家發行投信**：國泰、摩根(JPMorgan)、安聯(Allianz)、統一、
聯博(AllianceBernstein)、富邦、中信(CTBC)、第一金、復華、永豐
(SinoPac)、野村(Nomura)、台新、元大(Yuanta)、群益(Capital)、兆豐
(Mega)、貝萊德(BlackRock)。

## 1. 逐家投信查證表

**查證方式**：直接 `curl`/WebFetch 讀取 `robots.txt` 與官網頁面本身
（不經第三方摘要），UA一律用 `AlphaResearch/1.0 (robots-check; contact:
jlove201314@yahoo.com.tw)`，被WAF/403/302擋下時不換UA、不繞過。

| # | 投信 | 官網 | robots.txt 實測內容 | ToS/使用條款 | 每日持股揭露頁 | 歷史查詢 | 判定 |
|---|---|---|---|---|---|---|---|
| 1 | 國泰 | cathaysite.com.tw | `www.cathaysite.com.tw/robots.txt` → **HTTP 403**（被擋，未換UA未繞過） | 未查（robots已擋，依規則不明視同禁止，不必再查ToS） | 未找到 | 未查 | **不明→禁止** |
| 2 | 摩根(JPMorgan) | am.jpmorgan.com（TW頁在`/tw/zh/asset-management/per/`） | `am.jpmorgan.com/robots.txt` → HTTP 200。`User-agent: *`：`Allow: /*/*/asset-management/`（優先於）`Disallow: /*/asset-management/`——TW頁路徑`/tw/zh/asset-management/`符合兩段萬用字元後綴「asset-management/」，依robots.txt比對慣例（更長/更具體規則優先）**應解讀為明確Allow** | 未親自讀到專屬條款頁（僅搜尋摘要），**不採信未讀原文的推論** | 未找到主動式ETF每日持股專頁（找到的是產品介紹頁） | 未查 | **不明→禁止**（robots雖傾向允許，但ToS未讀原文、且無持股頁可用，依規則不明視同禁止） |
| 3 | 安聯(Allianz) | tw.allianzgi.com | HTTP 200。`User-agent: *`僅disallow系統/CMS路徑（`/sitecore/`等），**未disallow一般內容路徑** | 讀到版權頁`tw.allianzgi.com/zh-tw/copyright`原文：「非經本公司書面授權同意，**不得以任何形式轉載、傳輸、傳播、散布、展示、出版、再製或利用**」 | 未找到 | 未查 | **禁止**（ToS明文須書面授權，robots層級的允許不能凌駕ToS的著作權限制） |
| 4 | 統一 | ezmoney.com.tw | `robots.txt` → **HTTP 302自我迴圈**（導向自己），取不到內容 | 搜尋摘要顯示「網站內容智慧財產權屬統一投信，未經同意不得以任何媒體形式重製或轉載」（未親自讀到條款頁原文） | 未找到 | 未查 | **不明→禁止** |
| 5 | 聯博(AllianceBernstein) | web.alliancebernstein.com（TW）→302導向`www.alliancebernstein.com`（全球站） | 全球站`robots.txt`→HTTP 200，`User-agent: *`僅disallow系統路徑（`/abcom/`等），未disallow一般內容 | 未查（TW專屬站的robots.txt因跳轉到全球站而拿不到TW站本身的規則，視為不明） | 未找到 | 未查 | **不明→禁止**（TW站本身的robots狀態未確認，且ToS未讀） |
| 6 | 富邦 | fubon.com/asset-management | `www.fubon.com/robots.txt` → HTTP 302導向`.../not_found.html`，等同**沒有這個路徑的robots.txt** | 未查 | 未找到 | 未查 | **不明→禁止** |
| 7 | 中信(CTBC) | ctbcinvestments.com(.tw) | `www.ctbcinvestments.com/robots.txt` → HTTP 200，`User-agent: *` `Allow: /`（跟DevQueue先前結果一致） | 未親自讀到條款頁原文（WebFetch兩次都只拿到標題，內容疑似JS渲染） | 未找到 | 未查 | **不明→禁止**（robots允許，但ToS未讀原文，依規則不明視同禁止） |
| 8 | 第一金 | fsitc.com(.tw) | `www.fsitc.com/robots.txt` → HTTP 200，`Allow: /`，另有`LLM-Policy: /llms.txt`（**未讀該檔**） | **已讀到原文**（`FooterLink.aspx?ID=1007`「使用本站政策」）：「非經本公司書面授權同意，**不得以任何形式轉載、傳輸、傳播、散布、展示、出版、再製或利用**」 | 未找到（首頁頁尾連結只到淨值表/ESG/治理專區，沒有主動式ETF持股連結） | 未查 | **禁止**（robots允許但ToS明文須書面授權，跟安聯同款結論） |
| 9 | 復華 | fhtrust.com.tw | `www.fhtrust.com.tw/robots.txt` → HTTP 200，但**只有`User-agent: GPTBot`的`Disallow: /`**，沒有`User-agent: *`區塊——對通用爬蟲的規則是「未聲明」，依規則不明 | 未查 | 未找到 | 未查 | **不明→禁止** |
| 10 | 永豐(SinoPac) | sitc.sinopac.com | `sitc.sinopac.com/robots.txt` → **HTTP 404**（不存在） | 未查 | 未找到（找到`fundmobile.sinopac.com`行動版入口，未進一步查） | 未查 | **不明→禁止** |
| 11 | 野村(Nomura) | nomurafunds.com.tw | `www.nomurafunds.com.tw/robots.txt` → HTTP 200但**回傳的是SPA應用程式殼層本身**（Angular框架，該路徑實際上不存在獨立robots.txt，伺服器fallback到index） | 未查（同DevQueue先前結果） | 未找到（重度JS渲染，內容無法用HTTP GET取得） | 未查 | **不明→禁止** |
| 12 | 台新 | tsit.com.tw | `www.tsit.com.tw/robots.txt` → HTTP 200，但**只有`Googlebot`與`AdsBot-Google`兩段規則，沒有`User-agent: *`**——對其他UA的規則是「未聲明」 | 未查 | 未查（robots的`Allow: /active/`暗示`/active/`路徑可能是主動式ETF專區，但這是給Google的規則不是給我們的） | 未查 | **不明→禁止** |
| 13 | 元大(Yuanta) | yuantaetfs.com／yuantafunds.com | 兩個網域皆HTTP 200：`yuantaetfs.com`→`Allow: /`；`yuantafunds.com`→`Allow: /`（有一行`DisAllow: /mrFund`，拼字非標準`Disallow`，實務上多數解析器仍會辨識，但也可能被忽略——不影響本判定） | 未親自讀到條款頁原文（僅搜尋摘要指向頁尾應有連結，未確認網址與內容） | 未找到 | 未查 | **不明→禁止**（robots允許但ToS未讀原文） |
| 14 | 群益(Capital) | capitalfund.com.tw | `www.capitalfund.com.tw/robots.txt` → HTTP 200，`Allow: /`（跟DevQueue先前結果一致） | 讀到「重要事項」頁（`/capital/other/statement`）——**這個頁面本身沒有自動化存取/著作權相關條文**（內容是個資保護、隱私權、App權限、TLS/SSL、吹哨管道、基金風險警語），**沒找到**真正的網站使用條款/著作權聲明頁面，可能在其他路徑 | 未找到 | 未查 | **不明→禁止**（找到的頁面不含相關條文，不代表網站沒有這類條文放在別處，未窮盡查找前不得判定為允許） |
| 15 | 兆豐(Mega) | megafunds.com.tw | `www.megafunds.com.tw/robots.txt` → **HTTP 404**（不存在） | 未查 | 未找到 | 未查 | **不明→禁止** |
| 16 | 貝萊德(BlackRock) | blackrock.com/tw | `www.blackrock.com/robots.txt` → HTTP 200（全球共用robots），`User-agent: *`僅disallow特定功能路徑（登入、搜尋、特定國別頁等），**未disallow一般內容** | 未查（全球性大型金融機構，ToS極可能有嚴格的重製限制條款，但未親自讀到TW頁面專屬條款） | 未找到（貝萊德在台灣的ETF可能透過犇華投信舊制或另有專屬入口，本輪未深入） | 未查 | **不明→禁止** |

## 2. 總結

**16家全數判定「不明/禁止」，0家判定「允許」。** 依裁示規則「不明一律
視同禁止」，沒有任何一家投信目前可以合規地程式抓取每日持股資料。

**已經確認的硬性禁止（不是「不明」，是明確讀到條文的）**：安聯、第一金
兩家的ToS原文都明確寫「非經書面授權同意，不得以任何形式轉載、傳輸、
傳播、散布、展示、出版、再製或利用」——這兩家連「robots.txt允許」都
沒有幫上忙，因為ToS的著作權限制層級高於robots.txt的協定層級允許。
**這個發現有一定的外推價值**：兩個獨立查到原文的樣本都是同一種「須
書面授權」的標準格式，加上先前DevQueue查到統一投信搜尋摘要也是同一種
措辭，三個獨立來源指向同一個結論方向——這類條文在台灣投信業界很可能
是業界標準用語（金融業網站常見的制式著作權聲明），不是個案。**但這是
推論外推，不是逐一驗證過16家，如實揭露不誇大**。

**技術面的額外障礙**：即使ToS問題解決，至少3家（野村、台新、復華）的
robots.txt本身就沒有對通用UA給出任何規則（不是禁止，是完全沒提到），
另外「找到每日持股揭露頁的實際網址」這件事，**16家中沒有一家被找到**
——本次查證受限於多數投信官網是JavaScript渲染（Angular/React類SPA），
簡單的HTTP GET/WebFetch看不到实际持股表格內容，需要瀏覽器渲染或找出
背後呼叫的API端點，這已經超出「查證」範疇進入「逆向工程」，本輪未做。

**因此結論**：**目前沒有任何一條合規、可行的自動化收集路徑**。步驟3
（建立每日收集器）**不執行**——沒有任何來源通過步驟2的驗證。

## 3. 建議下一步（提案，待總司令裁示，本輪不做）

1. **書面詢問投信**：對這16家（或先挑幾家ETF規模最大的）發客服信詢問
   是否同意程式化每日讀取其揭露頁，這是唯一目前查到「寫進條款」的
   合法路徑（多家條文都寫「非經書面授權同意」，暗示書面同意後可行）。
2. **人工每日下載**：總司令親自每日開網頁記錄，我方只處理已下載的
   檔案，不涉及自動化存取的合規爭議。
3. **查data.gov.tw**：本輪仍未查（同DevQueue先前的待辦），下一步可以
   查是否有政府資料開放平臺上架主動式ETF持股資料集。
4. **鎖定少數幾家先深入處理**：與其對16家平均分散心力，可考慮先選
   ETF規模最大、且robots.txt条件相對友善的1-2家（例如貝萊德、聯博的
   全球robots都相對寬鬆），針對這一兩家單獨發函詢問，而不是同時處理
   16家。

## 4. 誠實揭露本輪查證的侷限

- 多數投信官網是JS渲染SPA，WebFetch的靜態HTML轉換看不到實際內容，
  這會系統性讓「找不到條款頁/持股頁」的比例偏高——不代表這些頁面
  真的不存在，只是本次工具讀不到。
- 摩根、貝萊德、聯博是全球性機構，查到的robots.txt多半是全球共用版本
  （非TW專屬子網域的獨立版本），TW專屬頁面本身的robots狀態部分未能
  單獨確認。
- 第一金的`llms.txt`、群益的其他子路徑條款頁、多家投信的行動版/APP
  服務條款皆未讀，可能藏有本次未看到的相關條文（不排除更寬鬆或更嚴格
  的規定）。
- 本文件的「ToS原文」欄位凡標「已讀到原文」的，是透過WebFetch工具讀取
  頁面轉譯後的內容，不是逐字元核對HTML原始碼，但已避開純搜尋引擎摘要
  這一層。
