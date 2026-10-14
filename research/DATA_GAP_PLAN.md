# DATA_GAP_PLAN.md — 「資料不足」逐條分甲／乙／丙（總司令裁示 先.八十六-1）

**產生**：2026-10-14 DevQueue `20261014-083101`
**對象**：`research/GRAVEYARD_AUTOPSY.md` 第 5 節 B 類 20 條 ＋ 先.八十三-3a（B1 開案第一步，與 B 類第 1 條同一件，合併成一列另附子項）
**性質**：只做資料可得性分類與查證，**不登記試驗、不跑回測、不改任何判定、不碰 holdout**。分到甲類的只代表「資料抓得到」，要重測仍須另寫規格、事前登記、計入 N。

## 0. 分類定義（裁示原文）

- **甲**：免費公開、只是還沒抓 → 直接排抓取工作（DevQueue 可執行）。
- **乙**：需要總司令本人註冊 key 或付費 → 列來源、費用、註冊步驟（**未親自驗證**），付費的標「待採購」。
- **丙**：歷史上不存在或統計結構上限 → 註明原因後維持現判。

**一條可能同時有兩種缺口**（例：資料補得到，但補完樣本仍不夠）。這裡以「**決定能不能重開的那個缺口**」為主分類，另一個缺口寫在備註。

**本輪新查證**（2026-10-14，本輪實際打的請求，全部官方公開端點、間隔 ≥3 秒）：
- TWSE `rwd/zh/TAIEX/MI_5MINS_HIST`：1999-01、2004-01、2009-01 都回開盤指數（3 次）。
- TWSE `rwd/zh/announcement/punish?startDate&endDate`（公布處置有價證券資訊，可查區間）：2000 全年 0 筆、2005 全年 28 筆、2010 全年 62 筆、2015Q1 有資料（4 次）；`www.twse.com.tw/robots.txt` 只禁 `/epaper/`、`/FTSE/`。
- TPEx `www/zh-tw/bulletin/disposal?startDate&endDate`（上櫃處置有價證券，可查區間）：2015Q1 13 檔 23 次（1 次）。
- TDCC `opendata.tdcc.com.tw/getOD.ashx?id=1-5`：只回 20261008 一週（1 次）。
- FRED `BAMLH0A0HYM2` 序列頁 notes 原文「Starting in April 2026, this series will only include 3 years of observations」，CSV 第一筆 2023-10-16（2 次）。
- 央行 `www.cbc.gov.tw/tw/lp-971-1-6-20.html`（重要政策新聞列表）列出 105/09/29、105/12/22、106/03/23、106/06/22、106/12/21 理監事聯席會議決議；`cp-302-36355` 為 2010-03-25 決議新聞稿。
- `mopsov.twse.com.tw/robots.txt`：`User-Agent: * Disallow: /`（1 次，與舊紀錄一致）。
- TWSE／TPEx openapi swagger 關鍵字掃描（買回／庫藏／內部人／處置／現金增資）：沒有庫藏股買回端點；內部人轉讓 `t187ap12_L`／`mopsfin_t187ap12_O` 是「每日」申報表（不能帶日期）；處置 `/announcement/punish`、`tpex_disposal_information` 是當期快照。

## 1. 總表

| # | 條目 | 缺什麼 | 分類 | 一句話結論 |
|---|---|---|---|---|
| 1 | f_us_momentum_12m ＋ 先.八十三-3a（B1） | 1994 起 PIT 宇宙；大樣本美股價格（含已下市） | **宇宙＝甲（已抓完）；已下市價格＝乙** | 宇宙 1993Q1 起已補完（先.八十三-3a-2／3a-3）；已下市股價格 Tiingo 免費版實測 60/60 完成：拿得到 98.3%、正確只有 48.3% → **暫停：免費管道補不到，等 App 有收入再評估**（先.八十八-5，`research/DATA_SOURCE_COVERAGE_TEST.md`）；付費全歷史待採購 |
| 2 | f_us_value_bm／low_vol 乾淨宇宙 | 未還原原始價；真實借券費率與可借量 | **乙＋丙** | 原始價可走 Tiingo 免費 key（已有）；借券歷史無免費來源，空頭腿依第⑩條維持不採信 |
| 3 | 原子.五B 財報通道 B | 約 30 個獨立族 | **丙** | 先.八十三-3c 實測上限 23–24 族（K=5 只 9–10 族），資料源結構上限 |
| 4 | dividend_yield_portfolio_v1 | VAL 太短 | **甲（已補、已測）** | 2007–14 單發 #397／#399→#400 FAIL，維持死亡 |
| 5 | 52 週高點策略層 #17 | VAL 太短 | **甲（已補、已測）** | 2007–14 單發 #396／#398 FAIL，維持死亡 |
| 6 | 台指 VRP #35（B4） | 2002–2014 TXO 日行情 | **甲（已抓完）** | 年度檔 2002～2014 已下載（先.八十六-2c）；PREREG 草稿在 AWAITING |
| 7 | #38 大戶籌碼 | 股東持股分級歷史週資料 | **乙（待採購）／前向累積** | TDCC 免費只給最新一週；FinMind 歷史要付費會員 |
| 8 | #39 0050 成分股調整 | 歷史成分股名單＋生效日 | **甲（已在 #82 查證可得）** | 無結構化 API，但 #82（2026-09-23～24）已用維基完整變動表＋四家媒體交叉核對判「資料可行」；事件數天生少 |
| 9 | #40 庫藏股買回 | VAL 事件數、全市場歷史 | **丙（合規上不存在）** | 唯一歷史來源 mopsov robots 全站禁止；openapi 無買回端點 |
| 10 | #41 內部人持股轉讓 | 全市場歷史 | **丙（合規上不存在）→ 前向累積** | openapi 只有每日申報表、不能帶日期；歷史在 mopsov |
| 11 | #44 景氣對策信號（當時發布版） | 即時版（vintage）數字 | **丙** | 即時版要逐月翻新聞稿重建；就算重建完，月頻樣本仍受 #81 的結構上限 |
| 12 | #47 處置股 | 處置股歷史清單 | **甲（推翻舊結論）** | 證交所／櫃買官網「公布處置有價證券」可查日期區間，2005 起有資料 |
| 13 | #49 隔夜／盤中分解（B5） | 2010 前每日開盤價 | **甲（已查證可得）** | TWSE MI_5MINS_HIST 1999-01-05 起有開盤指數；待寫 PREREG |
| 14 | #51 子事件 2 現金增資 | 事件數 | **丙** | 全市場歷史約 118 筆已全用，VAL 要 117～148 筆 |
| 15 | #52-US 8-K 2.02（B2） | 股票數與事件數 | **甲（事件已數完）＋乙（下市股價格）** | 前 200 檔 TRAIN＋VAL 14,010 個事件；價格同第 1 列 |
| 16 | #61 央行決策日 | 2015–17 會議日期；會議場數 | **丙（主）；日期部分＝甲** | 2015–17 日期官網其實查得到（推翻舊結論），但每年 4 場，補完也只多 12 場 |
| 17 | #72 重大訂單 | 歷史深度 | **丙（合規上不存在）→ 前向累積** | 有歷史的 t51sb10 在 mopsov（robots 禁止） |
| 18 | #77 高收益債利差 | 2023 年以前序列 | **乙（待採購）** | FRED 自 2026-04 只給 3 年；完整歷史要向 ICE Data Indices 授權 |
| 19 | #81 景氣對策信號（月頻） | 不重疊月觀測 | **丙** | r≈−0.10 約需 783 個月（65 年），資料自 1984 起 |
| 20 | D10-b 美股供給緊縮 | 已下市股代號與價格（#410） | **乙（＋部分丙）** | 代號解析是新宇宙仍未解的瓶頸；價格同第 1 列 |

**分類統計**：甲 7（其中已抓完／已查證 6：#1 宇宙、#4、#5、#6、#13、#39；**真正待排抓取 1：#47**）、乙 4（#1 價格、#2、#7、#18、#20 中的價格面，主分類算 #7、#18、#20、#2）、丙 9（#3、#9、#10、#11、#14、#16、#17、#19，以及 #2 的借券面）。

> 統計說明：#1、#2、#15、#16、#20 有兩種缺口，上面「主分類」照第 0 節規則取決定性缺口；把它們硬塞進單一格會失真，所以逐條段落都寫兩邊。

## 2. 逐條（每條附三來源查證）

查證來源分四類：①官方網站／開放資料入口 ②官方 API 文件 ③GitHub／社群 ④其他供應商。每條至少涵蓋三類。「repo」指本專案先前已留檔的查證紀錄（附檔名），「本輪」指 2026-10-14 本輪重打。

### 2.1 f_us_momentum_12m ＋ 先.八十三-3a（B1）
- **缺口**：(a) 時點宇宙要到 1994 起才有 ≥196 個月度快照；(b) 已下市股價格。
- **分類**：(a) **甲，已完成**；(b) **乙**。
- **(a) 已做**：先.八十三-3a-2 用 EDGAR full-index form.idx 1993Q1～2026Q3 重建名冊 49,615 個 CIK；先.八十三-3a-3 補抓 SIC 全部完成。宇宙覆蓋 1997-01～2024-12（336 個月）。細節見 `research/AUTOPSY_ACTIONS.md`「B1 補件結果」「B1 補件結果續」。
- **(b) 現況**：1997～2001 每月只有 11.5%～13.3% 的公司有代號（拿得到代號才有機會查價格）；先.十九 抽樣已下市股 yfinance 只有 2/60 有價。Tiingo 免費 key（總司令已申請，只在本機 .env）實測完成：先.八十八-3 60/60，found 98.3%、但「起訖正確」只有 48.3%（OTC 續掛 10、代號被沿用 6、片段 10）→ 拿得到≠拿對，要逐檔截斷。
- **三來源查證**：
  1. 官方：SEC EDGAR full-index（`www.sec.gov/Archives/edgar/full-index/YYYY/QTRn/form.idx`），repo `AUTOPSY_ACTIONS.md` B1 段落；SEC webmaster FAQ 10 req/秒。
  2. 官方 API 文件：`data.sec.gov/submissions/CIK*.json`（sic、tickers、formerNames 欄位），repo `research/us_sic_universe_fetch.py`。
  3. 社群：yfinance README（非官方、Yahoo 資料限個人使用，已下市股 0 覆蓋，repo `docs/US_PRICE_SOURCES.md`）。
  4. 供應商：Tiingo 定價頁 `tiingo.com/about/pricing`（免費 50 次/時、1,000 次/日、500 檔/月、Internal Use Only，先.八十八-2 擷取）；付費含下市股的商品（CRSP、Norgate、Sharadar 等）比較表另由 **先.八十六-3** 產出。
- **乙類結果（2026-10-14 先.八十八-5）**：Tiingo 60/60 拿得到 98.3%、整體正確 48.3%（2010–2012 下市 0/10 正確；B 類 OTC 續掛截斷後全算也只 65%）→ 偏低。**B1 美股動能：暫停：免費管道補不到，等 App 有收入再評估。** 不寫用法提案、不登記試驗、不自行採購。細節見 `research/DATA_SOURCE_COVERAGE_TEST.md`。
  - ⚠️ 下面這行已過時，保留供稽核：免費 Tiingo 結果出來後（先.八十八-5）決定；若 ≥80% 正確 → 提案；偏低 → 標「暫停：等 App 有收入再評估收費資料」。**不自行採購。**

### 2.2 f_us_value_bm／low_vol 乾淨宇宙
- **缺口**：未還原原始價格（算市值／帳面市值比）；真實借券費率與可借量（空頭腿）。
- **分類**：原始價＝**乙**（免費 key，已在手）；借券＝**丙**（免費歷史不存在）＋**乙**（收費資料商）。
- **三來源查證**：
  1. 官方：SEC XBRL `EntityPublicFloat` 不成序列、只得價格下界（CLAUDE.md 七之三已查證不可行）。
  2. 供應商：Tiingo 日線提供 `close` 與 `adjClose` 兩欄（免費方案即有，先.八十八-4 對照組實測拿得到日線）；Alpha Vantage 免費層只給近 100 天未還原價（`docs/US_PRICE_SOURCES.md` 第 224～290 行）；yfinance 還原價與 FinMind 逐位元相同、沒有未還原價（`TRIALS_LEDGER.md` #188）；Stooq 需人工過 CAPTCHA 領 key（`docs/US_PRICE_SOURCES.md` 第 35～64 行）。
  3. 官方／交易所：美股借券費率與可借量沒有交易所公開歷史——repo 只有 FINRA 空頭部位（每兩週）與 Nasdaq Reg SHO 名單（`docs/FIRST_HAND_SOURCES.md` 第 434～442 行），都不是費率；repo `research/validation/us_costs.py` 的 `BORROW_FEE_TIERS_USD` 仍是寫死假設值（CLAUDE.md 第⑩條）。
  4. 收費：借券資料商（如 S&P Markit Securities Finance）為機構授權商品，價格不公開 → **待採購（未查到公開價格，未親自驗證）**。
- **維持現判**：空頭腿依第⑩條不得採信；只做多頭的版本（#22）已 FAIL。

### 2.3 原子.五B 財報通道 B（#320）
- **分類**：**丙**（資料源結構上限）。
- **理由**：先.八十三-3c 只讀本機快取實測：損益表全部表達式最多 23–24 族、K=5 只 9–10 族；資產負債表／現金流最早 2012，進不了 2011 窗；`net_income`／`shares` 是 IFRS 2013 起。要湊 30 族只能開新搜尋空間＝新假設。
- **三來源查證**：
  1. 官方：TWSE openapi `t187ap06/07_*` 財報只有最新一期（repo `C:\alpha\CLAUDE.md` 財報擴充段）。
  2. 官方網站：MOPS 歷史財報在 `mopsov.twse.com.tw`，robots.txt `Disallow: /`（本輪重打確認）。
  3. 供應商：FinMind `TaiwanStockFinancialStatements` 本機 3,477 檔、最早 2008 前（二手，已在用），repo `AUTOPSY_ACTIONS.md` B3 段落。
- **維持死亡**。

### 2.4 dividend_yield_portfolio_v1
- **分類**：**甲，已補、已測**。用 2007–2014 新資料做過事前登記單發（#397／#399→#400），FAIL。
- **查證**：這條的缺口已用新資料補完並測過，repo 只有開考前資料品質閘門紀錄（`research/SINGLE_SHOT_2007_2014_SPEC.md` 第 26～50、133 行：FinMind 2007–2014 延伸樣本 300/300 檔、0050 自 2003-06-30；`research/AWAITING_REVIEW.md` 第 79 行全數通過），**只有 2 個來源紀錄**。已無資料缺口、結論是 FAIL，補第三來源不改變任何事，故不再查。
- **維持死亡**。

### 2.5 52 週高點策略層（#17）
- **分類**：**甲，已補、已測**。2007–2014 單發 #396／#398 FAIL。
- **查證**：同 2.4（同一份 SPEC、同一批延伸資料，結案紀錄 `STRATEGY_GRAVEYARD.md` 第 4052～4076 行），**只有 2 個來源紀錄**，理由同上不再補查。
- **維持死亡**。

### 2.6 台指 VRP #35（B4）
- **分類**：**甲，已抓完**。
- **已做**：期交所 TXO 年度檔 2002～2014 已下載到 `research/data/raw/taifex_opt_yearly/`（不進 repo，先.八十六-2c／先.八十三-3d-1）；加權指數 1999 起可得（2.13）。PREREG 草稿已列 AWAITING_REVIEW（先.八十五-4），**不得自行登記**。
- **三來源查證**（repo `AUTOPSY_ACTIONS.md` B4 段落）：
  1. 官方網站：`www.taifex.com.tw/cht/3/dlOptDailyMarketView` 年度行情下載 2001～2025；付費價目表（臺指VIX 歷史 NT$3,000／半年，#35 不需要）。
  2. 官方 API：`openapi.taifex.com.tw/swagger.json` 的 `/DailyMarketReportOpt` 不能帶日期 → 歷史只能走年度檔。
  3. GitHub：約 10 個專案使用 `optDataDown`（例 ZivHong/twse_taifex_crawler、chunkai1312/node-twstock）。
  4. 供應商：FinMind `TaiwanOptionDaily` 文件寫 2001-12 起。
- **PREREG 前仍待辦**（不是資料缺口）：只用月合約、2002–2005 價平買賣兩邊成交驗證、天條一 MDD。

### 2.7 #38 大戶籌碼集中度
- **分類**：**乙（待採購）**；免費路線只能前向累積（從現在起每週存一份，要好幾年）。
- **三來源查證**：
  1. 官方開放資料：TDCC `opendata.tdcc.com.tw/getOD.ashx?id=1-5`（本輪實測只回 20261008 一週；`docs/FIRST_HAND_SOURCES.md` 第 289～299 行同結論）；`openapi.tdcc.com.tw/v1/opendata/1-5` 帶 `date` 參數被忽略（repo `STRATEGY_GRAVEYARD.md` #38，2026-09-06）。
  2. 官方網站：TDCC 集保戶股權分散表查詢頁 `www.tdcc.com.tw/portal/zh/smWeb/qryStock`（互動查詢頁，非 API；**repo 只列為路徑、沒有實測**，可回溯多久未驗證）。
  3. 供應商：FinMind `TaiwanStockHoldingSharesPer` 免費層回 HTTP 400「Your level is free」（repo `holding_shares_per_probe.py`）。
- **乙類資料**：FinMind 付費會員（方案與價格以 FinMind 官網為準，**未親自驗證**）→ **待採購**，依總司令「App 賺錢前不花錢買資料」暫不採購。
- **前向累積選項**（不是本項交辦、僅列出）：每週一次抓 TDCC 開放資料 1 次請求存檔，屬合規、零成本；要開始累積需另立交辦。
  - ⚠️ 上一行「要開始累積需另立交辦」已過時（2026-10-14 先.九十四-5c 更正）：`scripts/fetch_tdcc_holders.py`（源頭一.2a，2026-09-10 加入）已由本機排程 `AlphaTdccHolders` 每週累積，`research/data/tdcc/` 現有 20260904／0911／0924／1008 四週（0918、1001 兩週缺，原因未查），並產出 `data/holders.json`。

### 2.8 #39 0050 成分股調整
- **分類**：**甲（已查證可得）**。`GRAVEYARD_AUTOPSY.md` 第 5 節寫「不能」，與 `HYPOTHESIS_QUEUE.md` #82（第 12520～12700 行，2026-09-23～24）判「資料可行」互相矛盾——以 #82 較新且查得較深為準。
- **三來源查證**：
  1. 官方 API：TWSE openapi 144 個端點只有 `/indicesReport/TAI50I` 指數點數與 `/ETFReport/ETFRank`，沒有成分股名單；FinMind 無指數成分股 dataset（repo `STRATEGY_GRAVEYARD.md` #39、`index_reconstitution_probe.py`，2026-09-06）。
  2. 官方網站：TWSE「臺灣50指數歷史資料」`twse.com.tw/zh/indices/ftse/tai50i.html` 與 `taiwanindex.com.tw` 為 JS 動態頁讀不到（#82）；編制規則來自 FTSE Ground Rules v5.2、TWSE `IndexSen19.pdf`、元大 0050 公開說明書（先.九十三-1a，`research/PIT_MKTCAP_RULES_FIX.md`）。
  3. 社群／其他：中文維基「臺灣50指數」有 2003-01～2026-09 完整變動表；#82 用工商時報、鉅亨、聯合、自由時報核對 2016-06、2018-06、2020-09 三筆，組成全吻合。GitHub `yfiua/index-constituents`、`Jaycome/tw50-quant-data` 沒有變動資料。
- **另一個缺口（丙性質）**：每季審核通常只換 0～3 檔，2003～2024 約數十個事件，樣本小；要重測先估檢定力。
- **建議**：資料面已不是瓶頸，不排新抓取；`GRAVEYARD_AUTOPSY.md` 該列改指向 #82。重測需另寫規格事前登記並計入 N（#82 現況見 `HYPOTHESIS_QUEUE.md`）。`www.twse.com.tw/robots.txt` `Disallow: /FTSE/`，所以**不抓**證交所 FTSE 路徑。

### 2.9 #40 庫藏股買回
- **分類**：**丙（合規上不存在）**。
- **三來源查證**：
  1. 官方網站：MOPS 庫藏股查詢在 `mopsov.twse.com.tw`，robots.txt `User-Agent: * Disallow: /`（本輪重打）；`mops_buyback_client.py` 已依 2026-09-15 裁示停用（client 第 86–93 行）。
  2. 官方 API：TWSE／TPEx openapi swagger 掃描（本輪）：沒有庫藏股買回端點（「庫藏」只出現在資產負債表科目）。
  3. repo：`research/mops_buyback_client.py` 第 1～25 行記錄 MOPS `t35sc09` 實測可回溯 2015 年，但主機是 mopsov（`docs/DATA_SOURCE_MAP.md` 第 79～96 行，2026-09-08）。
  - 未查：櫃買 openapi（本輪 swagger 掃描已涵蓋，同樣沒有）、FinMind 是否有庫藏股 dataset（未查，誠實標註）。
- **維持死亡**；除非取得 MOPS 書面授權。

### 2.10 #41 內部人持股轉讓
- **分類**：**丙（合規上不存在歷史）→ 可前向累積**。
- **三來源查證**：
  1. 官方 API：TWSE `t187ap12_L`／`t187ap13_L`、TPEx `mopsfin_t187ap12_O`／`13_O`「每日內部人持股轉讓事前申報表」（本輪 swagger 掃描），每日快照、不能帶日期。
  2. 官方網站：歷史查詢在 mopsov（robots 禁止）；`mops_insider_holdings_client.py` 打的也是 mopsov。
  3. 官方 API：`t187ap11_L` 董監事持股餘額明細＝當月快照，同樣無歷史。
  4. repo：`HYPOTHESIS_QUEUE.md` 第 4422～4460 行（2026-09-06）：猜 MOPS `t05st07`／`t34sc01`／`t108sb01` 都被拒；MOPS `stapap1` 可查任意歷史年月，但在 mopsov（`docs/FIRST_HAND_SOURCES.md` 第 211～230 行）。
- **前向累積選項**：每日 2 個 openapi 端點各 1 次，合規；要開始累積需另立交辦。

### 2.11 #44 景氣對策信號（當時發布版）
- **分類**：**丙**。
- **理由**：data.gov.tw 只有修正後最終版；「當時發布版」理論上可逐月翻國發會新聞稿重建（每月一篇），但這條訊號的統計上限在 #81 已算過：月頻、r≈−0.10 要約 783 個不重疊月，重建 vintage 不會增加月數。
- **三來源查證**：
  1. 官方開放資料：data.gov.tw 景氣指標資料集只有修正後序列（repo `STRATEGY_GRAVEYARD.md` #44）。
  2. 官方網站：國發會查詢系統 `index.ndc.gov.tw` 與新聞稿頁回 403（`HYPOTHESIS_QUEUE.md` 第 4856～4898 行，2026-09-06），依鐵律不偽造 User-Agent 繞過；Wayback 快照沒有逐月分數。
  3. 其他：媒體（科技新報、工商時報）逐月轉載燈號＝可作為 vintage 交叉核對來源，但屬二手。
- **維持死亡**。

### 2.12 #47 處置股 ← **推翻舊結論**
- **分類**：**甲**（舊判「官方只有快照、歷史要付費」不成立）。
- **本輪實測**：
  - **與舊紀錄不同**：`STRATEGY_GRAVEYARD.md` #47（2026-09-06）寫「主站 `rwd/zh/announcement/punish` 日期參數無效」。本輪帶 `startDate`＋`endDate` 兩個參數，回應 title 會跟著區間變（「89/01/01 至 89/12/31」「94/01/01 至 94/12/31」），筆數也不同 → 日期參數有效。舊紀錄可能只帶了單一 `date` 參數（未能重現，原因未確認）。
  - TWSE `www.twse.com.tw/rwd/zh/announcement/punish?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json`：2000 全年 0 筆（可能是官方資料起點之前，或該年真的沒有，**未分辨**）、2005 全年 28 筆、2010 全年 62 筆；欄位含公布日期、代號、累計次數、處置條件、處置起迄、處置措施。
  - TPEx `www.tpex.org.tw/www/zh-tw/bulletin/disposal?startDate=YYYY/MM/DD&endDate=...&response=json`：2015Q1 13 檔 23 次，欄位含處置起訖、原因、措施、收盤價。
  - `www.twse.com.tw/robots.txt` 只禁 `/epaper/`、`/FTSE/`，`/rwd/` 允許。
- **三來源查證**：
  1. 官方網站：上兩個可查區間端點（本輪）。
  2. 官方 API：openapi `/announcement/punish`、`tpex_disposal_information`＝當期快照（本輪 swagger）——這就是舊紀錄只看到快照的原因。
  3. 供應商：FinMind `TaiwanStockDispositionSecuritiesPeriod` 回 400、付費層（repo `STRATEGY_GRAVEYARD.md` #47、`docs/FIRST_HAND_SOURCES.md` 第 180～188 行）。
  4. 社群：同一個 `rwd/zh/announcement/punish` 路徑與本專案 `C:\alpha\CLAUDE.md` 已登記的 TWT49U／exDailyQ 區間查詢是同一套網站結構。
- **抓取計畫（DevQueue 可執行）**：TWSE 2000～2024 每年 1 次、TPEx 每年 1 次（若單次筆數有上限則改每季），約 50～100 次請求、同源間隔 ≥3 秒、402/403/428/429 即停；先抓「注意股」對應的 `rwd/zh/announcement/notice` 是否也可查區間一起確認。輸出 `research/data/disposal_history_{twse,tpex}.json`。**只補資料、不登記試驗**；要重測 #47 需另寫規格事前登記，並注意 #47 已被判死過一次（新資料單發）。→ 排入佇列 **先.八十六-1a**。
- **抓取結果（先.八十六-1a，2026-10-14 DevQueue 20261014-083101）**：`research/fetch_disposal_history.py` 逐年 2000～2024 各 1 次、間隔 3.5 秒、0 錯誤（共 50 次＋核對 16 次）。輸出 `research/data/disposal_history_{twse,tpex}.json`（`research/data/` 在 .gitignore，只在本機；重抓指令 `python research/fetch_disposal_history.py 2000 2024`）。
  - 上市：**2001 起**有資料（2000 全年 0 筆），25 年 3,149 列；以（公布日期、代號、處置起迄）去重後 3,076 個事件。
  - 上櫃：**2003 起**有資料（2000～2002 全年 0 筆），6,417 列；去重後 6,344 個事件。
  - **查詢語意**：區間是比對「處置期間」是否重疊，不是公布日期——跨年的處置會在兩年各出現一次（兩邊各 73 筆跨年重複、約 80 筆公布日期落在前一年）。使用時一律先去重。
  - **沒有單次筆數上限**：2020 年改逐季查 4 次，唯一事件與全年查詢完全一致（上市 383＝383、上櫃 491＝491，兩邊差集皆 0）。
  - 只補資料、未登記試驗；#47 要重測需另寫規格事前登記並計入 N。
- **注意股歷史（先.九十四-5c，2026-10-14 DevQueue 20261014-170102）**：
  - **三來源查證**：
    1. 官方網站（實測）：上市 `www.twse.com.tw/rwd/zh/announcement/notice?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json`、上櫃 `www.tpex.org.tw/www/zh-tw/bulletin/attention?startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&response=json`，**都可查區間**：title／`date` 欄位跟著查詢區間變（例：上市「109年01月01日 至 109年12月31日」4,262 筆、只查 1 月 126 筆；上櫃 2020-01 回 79 筆、`date`＝20200101~20200131）。
    2. 官方 API：openapi `/announcement/notice`、TPEx `tpex_trading_warning_information` 類端點＝當期快照（與處置股同一情況，見上方 2.12 第 2 點），不能拿來補歷史。
    3. 同站結構：與上方處置股 `punish`／`disposal` 是同一套 rwd／www bulletin 結構，參數格式相同；`www.twse.com.tw/robots.txt` 只禁 `/epaper/`、`/FTSE/`，`www.tpex.org.tw` 沒有 robots.txt。
  - **抓取結果**：`research/fetch_notice_history.py` 逐年 2000～2024 各 1 次、間隔 3.5 秒；上櫃 2018 遇 1 次 `ChunkedEncodingError`（網路中斷，非 402/403/428/429），斷點續抓一次補齊。輸出 `research/data/notice_history_{twse,tpex}.json`（本機，`research/data/` 在 .gitignore；重抓 `python research/fetch_notice_history.py 2000 2024`，已抓年份不重抓）。
    - 上市：**2001 起**（2000 全年 0 筆），47,151 列。
    - 上櫃：**2002 起**（2000、2001 全年 0 筆），42,154 列。
  - **沒有單次筆數上限**：2021 年改逐季查 4 次，唯一列（去掉編號與累計次數）與全年一次查完全一致（上市 5,041＝5,041、上櫃 3,828＝3,828，差集皆 0）。
  - **地雷**：「累計次數」欄是**按查詢區間重算**的（同一列全年查與分季查數字不同），不能當成官方「最近 N 日累計」；要用時自己從日期重算。
  - 只補資料、未登記試驗、不計 N；#47 要重測需另寫規格事前登記。

### 2.13 #49 隔夜／盤中分解（B5）
- **分類**：**甲（已查證可得，資料量小、未整批抓）**。
- **三來源查證**：
  1. 官方網站：TWSE `MI_5MINS_HIST` 1999-01-05 起有開盤指數（repo `AUTOPSY_ACTIONS.md` B5；本輪重打 1999-01／2004-01／2009-01 都有）；查 1995-01 回「查詢日期小於88年1月5日」。
  2. 官方 API：openapi `/indicesReport/MI_5MINS_HIST` 只回最近 15 個交易日（`HYPOTHESIS_QUEUE.md` 第 11972～11980 行）。
  3. 官方年度檔：期交所 `futDataDown` 期貨年度檔（`docs/PREREG_overnight_intraday_1999_2009_FINAL.md` 第 53～60 行）；原試驗用 yfinance `^TWII` 只有 2010 起。
  - `docs/DATA_SOURCE_MAP.md` 第 311 行仍寫「未查證」，已過時。
- **注意**：早年加權指數「開盤指數」的計算方式（是否以前一日收盤價代入未成交股）會影響隔夜報酬，PREREG 要寫明檢查法。標的限台指期一般時段（現貨換手成本不可行，見 B5 段落）。
- **待辦**：PREREG 已有 `docs/PREREG_overnight_intraday_1999_2009_FINAL.md`（互動視窗負責，本輪不動）。

### 2.14 #51 子事件 2 現金增資
- **分類**：**丙**（全市場事件已全部用上）。
- **三來源查證**：
  1. 供應商：FinMind `TaiwanStockDividend` 本機快取 2,170 檔（2010–2024），118 筆事件、公告日皆早於除權日（`STRATEGY_GRAVEYARD.md` #51、`HYPOTHESIS_QUEUE.md` 第 5903～5909 行）。
  2. 官方 API：TWSE `exchangeReport/TWT48U_ALL` 除權除息預告表（含現金增資除權）只有預告；歷史除權結果 `TWT49U` 可查區間（`C:\alpha\CLAUDE.md` 除權除息段），能核對事件數但不會變多。
  3. 官方網站：MOPS 現金增資公告在 mopsov（robots 禁止）。
- **維持死亡**：VAL 需 117～148 筆，接近全歷史。

### 2.15 #52-US 8-K 2.02（B2）
- **分類**：事件＝**甲（已數完）**；價格＝**乙**（同 2.1）。
- **已做**：先.八十三-3b-1 `research/us_8k_202_event_count.py`，前 200 檔 TRAIN 10,935＋VAL 3,075＝14,010 個事件；DIS、BLK 控股重組換號要併舊 CIK。
- **三來源查證**（repo `AUTOPSY_ACTIONS.md` B2）：①SEC full-index form.idx（8-K 總數）②`data.sec.gov/submissions` 的 `items` 欄位③SEC 全文搜尋 `efts.sec.gov/LATEST/search-index`（上限參考）④yfinance（在市股價格）。
- **待辦**：PREREG 草稿已在 AWAITING（先.八十五-4），名單是今天在市大型股＝附美股存活者偏誤但書。

### 2.16 #61 央行決策日 ← **部分推翻舊結論**
- **分類**：**丙（主）**；2015–17 會議日期＝**甲**（其實查得到）。
- **本輪查證**：央行官網 `www.cbc.gov.tw/tw/lp-971-1-6-20.html`（重要政策新聞列表第 6 頁）列出 105/09/29、105/12/22、106/03/23、106/06/22、106/12/21 理監事聯席會議決議；`cp-302-36355-EC84A-1.html` 為 2010-03-25 決議新聞稿 → 列表分頁往前翻可補 2015–17 全部 12 場（甚至 2010 起）。舊紀錄「三個管道都失敗」應是查的頁面不對。
- **三來源查證**：
  1. 官方網站：上述央行新聞列表與決議新聞稿（本輪）。
  2. 其他：媒體每季報導決議日（例 inside.com.tw 2022Q1 會議紀錄報導），可交叉核對日期。
  3. repo：`cbc_policy_decision_data.py` 第 11～30、92～125 行（2026-09-08）：重貼現率頁 `lp-640-1-1-20.html`、決議彙整 `lp-357-1.html`＋逐年預定日期公告，2018–2024 核對過；2015–17 當時 WebSearch／官方逐年頁／Wayback 三路都沒找到（本輪改從 `lp-971` 重要政策新聞列表找到）。
- **為什麼仍是丙**：每年 4 場；由 VAL 反推每期約需 41～54 場（約 10～13 年）。就算補到 2010～2024 共約 60 場、切兩期各 30 場，仍不到門檻。
- **維持死亡**；日期補件不排（補了也過不了檢定力）。

### 2.17 #72 重大訂單
- **分類**：**丙（合規上不存在歷史）→ 前向累積中**。
- **三來源查證**：
  1. 官方網站：唯一有歷史的 MOPS 全文檢索 t51sb10 在 mopsov（robots 全站禁止，本輪重打）。
  2. 官方 API：TWSE／TPEx openapi 重大訊息端點只有當日（repo `STRATEGY_GRAVEYARD.md` #72、`data/events.json` 自 2026-09-08 起累積）。
  3. GitHub：`SuYenTing/Quantitative_investment_material_in_R` 有打 t51sb10 的 R 爬蟲（只看檔名），同樣在 mopsov。
  - 另：Wayback Machine 只驗證到 5 檔（`STRATEGY_GRAVEYARD.md` 第 3446 行），屬「下載別人已存的鏡像」，依取得方式鐵律不採用。
- **維持死亡**；前向累積照常。

### 2.18 #77 高收益債利差
- **分類**：**乙（待採購）**。
- **三來源查證**：
  1. 官方：FRED 序列頁 notes「Starting in April 2026, this series will only include 3 years of observations. For more data, go to the source」，CSV 第一筆 2023-10-16（本輪）。
  2. 官方 vintage：用 FRED 2026-01-01 的歷史版本重查，結果一樣截斷（`hy_credit_spread_probe.py`、`HYPOTHESIS_QUEUE.md` 第 11802～11826 行）。
  - 其他：第三方頁面（govspending.org、equibles.com）一致寫完整歷史要向 ICE 付費（同上）。
  3. 供應商：ICE Data Indices 授權（FRED 頁註明版權、需事前核准），價格不公開 → **待採購（未親自驗證）**。
- **替代**：#78（HYG／IEF ETF 比值代理）已測過 FAIL。依「App 賺錢前不花錢」暫不採購。

### 2.19 #81 景氣對策信號（月頻）
- **分類**：**丙（統計結構上限）**。
- **理由**：資料自 1984 起約 500 個月；r≈−0.10 需約 783 個不重疊月（約 65 年）。
- **三來源查證**：①data.gov.tw v2 API dataset 6099（官方開放資料）②國發會下載點 `ws.ndc.gov.tw/Download.ashx` zip 回 200、1984-01～2026-07（官方網站）③`data.nat.gov.tw` 回 502（已併入 data.gov.tw）；repo `HYPOTHESIS_QUEUE.md` 第 12290～12396 行（2026-09-23）。**誠實標註**：三條都是同一官方主機群，沒有第二家獨立供應商；但本條是統計結構上限，不是資料取得問題，多查供應商也不會增加月數。
- **維持死亡**。

### 2.20 D10-b 美股供給緊縮（#410）
- **分類**：**乙（主：已下市股價格）＋丙（部分：下市股代號）**。
- **理由**：#410 的瓶頸是已下市股代號解析只有 10/60（16.7%）；先.八十七-1 用 XBRL `dei:TradingSymbol` 解析率 44.1%。代號解得出來的部分可用 Tiingo（乙）；解不出來的部分沒有免費代號歷史（SEC 只有 formerNames，沒有代號歷史）。
- **三來源查證**：
  1. 官方：SEC submissions `tickers` 對已下市者一律為空；Form 25 括號代號 2/60、最後一份 10-K／10-Q 封面頁 8/60（`TRIALS_LEDGER.md` #410、`docs/FEASIBILITY_us_supply_tightness.md`）。
  2. 官方 API：XBRL `dei:TradingSymbol` 解析率 44.1%（`research/data/us_delisted_sample60.json`，先.八十七-1）。
  3. 供應商：Stooq 三端點為 JavaScript 驗證牆（#410，依鐵律不繞）；Tiingo 免費版 58/60 實測中（先.八十八-3）。
- **維持駁回**；等 先.八十八-5 結論與 先.八十六-3 比較表。

## 3. 甲類抓取工作清單（本輪排入佇列）

| 子項 | 內容 | 請求預算 | 狀態 |
|---|---|---|---|
| 先.八十六-1a | #47 處置股歷史：TWSE `rwd/zh/announcement/punish` 2000～2024、TPEx `bulletin/disposal` 可查起點～2024，存 `research/data/disposal_history_{twse,tpex}.json`；先確認起始年與單次筆數上限；只補資料、不登記試驗 | 實際 66 次、同源 3.5 秒 | **已完成**（上市 2001 起 3,076 事件、上櫃 2003 起 6,344 事件） |
| （已完成） | B1 宇宙 1993 起、B4 TXO 2002–2014、French UMD | — | 先.八十三-3a-2／3a-3、先.八十六-2a／2b／2c |
| （PREREG 後再抓） | #49 加權指數 1999 起開盤價 | 約 310 次月請求 | 等 B5 PREREG |
| （先法遵） | #39 臺灣50 歷史審核結果整理 | 人工 | 先確認使用條款，不排抓取 |

## 4. 乙類總覽（總司令決定；本專案不自行申請、不採購）

| 條目 | 來源 | 費用 | 狀態 |
|---|---|---|---|
| #1／#15／#20 已下市美股價格 | Tiingo 免費（key 已在本機 .env） | 免費 | 先.八十八-3 實測 58/60 |
| 同上 | 含下市股付費資料商（Norgate／EODHD／Sharadar；CRSP 只賣機構） | Norgate Platinum USD 630／年起；EODHD $19.99～$99.99／月；Sharadar 需登入看價；詳見 `research/US_DELISTED_PRICE_SOURCES.md` | 待採購（暫停：等 App 有收入）；三家條款都禁止展示轉發，只能本機研究 |
| #2 借券費率 | 機構借券資料商 | 未公開 | 待採購（未親自驗證） |
| #7 #38 股權分散歷史 | FinMind 付費會員 | 以 FinMind 官網為準（未親自驗證） | 待採購 |
| #18 #77 HY 利差完整歷史 | ICE Data Indices 授權 | 未公開 | 待採購（未親自驗證） |

## 5. 對 GRAVEYARD_AUTOPSY 的更正提示

本輪查證推翻兩條舊判斷的**資料面**理由（不改任何試驗判定）：
1. **#47**：處置股歷史不是「只有快照」，官網可查區間（2.12）。原試驗判死理由若只有資料不可及，重測需另寫規格事前登記。
3. **#39**：第 5 節寫「不能」，但 #82 已判資料可行（2.8）。
2. **#61**：2015–17 會議日期查得到（2.16），但樣本上限仍成立，維持死亡。

`GRAVEYARD_AUTOPSY.md` 第 5 節表格對應兩列已加註指向本檔。
