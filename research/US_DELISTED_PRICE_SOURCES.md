# 美股已下市股價格來源比較表（先.八十六-3）

**狀態**：第 1 批 2026-10-14 DevQueue `20261014-083101`；第 2 批 2026-10-14 DevQueue `20261014-093102` 補齊所有「待查」格（標「第2批」）。
**原則**：只列官方頁面原文；查不到的寫「頁面未載明」，不猜。**不申請試用、不採購**（總司令「App 賺錢前不花錢買資料」）。key 只放本機 `.env`，不進 repo、不進對話。
**價格均為各官方頁 2026-10-14 擷取當下的標價，未親自下單驗證；匯率、稅、續約價以官網結帳頁為準。**

| 來源 | 含已下市股？ | 歷史起點 | 費用 | 條款是否允許自用研究 | 查證來源 |
|---|---|---|---|---|---|
| Tiingo（免費） | 實測：60 檔已下市樣本 58 檔已查，found 95%、但起訖正確只有 46.7%（OTC 續掛、代號被沿用） | 對照組 KO 等多數 9,262 筆日線 | 免費：50 次/時、1,000 次/日、500 檔/月 | 官方定價頁 Licensing「Internal Use Only」（只限自用、不得展示或分享） | 先.八十八-2／-3（`tiingo.com/about/pricing`；`research/data/tiingo_delisted_probe.json`） |
| Alpha Vantage（免費） | SIVB 回破產後 OTC 空殼價（陷阱）；TWTR、ATVI 正確 | 免費層只給近 100 筆 | 免費 | **允許**（第2批）：服務條款第 2.a 條授權「personal, non-commercial use」，並明定超出「investment analysis, research, testing, monitoring, and any other activities that are private and individual in nature」才算商業用途；以公司／團體名義使用、或讓他人間接取得資訊，屬商業用途 | `docs/US_PRICE_SOURCES.md` 第 224～290 行；先.九十-3；`alphavantage.co/terms_of_service/`（PDF，第2批） |
| Stooq | 未實測（三個端點都是 JavaScript 驗證牆，依鐵律不繞） | 宣稱 20 年以上（第三方說明，未親自驗證） | 資料本身免費；key 要人工過 CAPTCHA | **讀不到**（第2批）：①`stooq.com/` 回 JavaScript 工作量證明驗證頁（不繞）②`stooq.pl/regulamin/` 回「Wybrana lokalizacja nie istnieje」（頁面不存在）③網路搜尋只找到第三方下載教學，沒有官方條款原文。→ 要總司令用瀏覽器開官網頁尾自己看，**未親自驗證** | `docs/US_PRICE_SOURCES.md` 第 35～64 行；`TRIALS_LEDGER.md` #410 |
| yfinance（參考） | 已下市股 60 檔抽樣只有 2 檔有價 | 在市股 1962 起 | 免費 | README：非 Yahoo 官方、Yahoo 資料限個人使用 | `research/data/us_delisted_price_probe.json`；`github.com/ranaroussi/yfinance` |
| Norgate Data（收費） | Silver／Gold 方案**不含**；Platinum、Diamond 方案含「delisted securities」與「historical index constituents」 | Silver 10 年、Gold 20 年、Platinum 1990、Diamond 1950 | **Platinum** 6 個月 USD 346.50／12 個月 USD 630；**Diamond** 6 個月 USD 433.13／12 個月 USD 787.50（第2批，官方方案頁） | **允許**（第2批，官方 FAQ）：「Personal use … includes … conducting your own research, analysis, backtesting」；**只賣個人授權**（無商業授權）；可裝 2 台；**到期後匯出的資料必須刪除**，但回測結果、模型參數可保留 | `norgatedata.com/prices.php`、`norgatedata.com/stockmarketpackages.php`、`norgatedata.com/faq.php` |
| EODHD（收費） | 含（第2批，官方文件）：已下市代號用 `delisted=1` 列出，「the US list alone returns tens of thousands of symbols」；「Before 2018: EOD only」「After 2018: EOD, Fundamentals, Dividends and Splits」；哪個方案含已下市資料**頁面未載明** | 定價頁：「US from the earliest available (Ford Motors from June 1972)」；已下市股起點頁面未載明 | 免費 $0（每日 20 次）；Historian $19.99／月、Active trader $29.99、Equity analyst $59.99、ALL-IN-ONE $99.99（年繳較低） | **允許**（第2批，服務條款）：Non-Professional User（個人投資用途）可「store, manipulate, and analyze data for private purposes」；禁止分享帳號、轉售、轉發、**展示**；商業用途需 Professional 授權；條款更新日期頁面未載明 | `eodhd.com/pricing`、`eodhd.com/financial-apis/list-supported-exchanges`、`eodhd.com/financial-apis/delisted-stock-companies-data-2`、`eodhd.com/financial-apis/terms-conditions` |
| Sharadar（Nasdaq Data Link，收費） | 含（第2批）：「No survivorship bias: includes active and delisted tickers」 | 價格 1998 起（基本面 1990 起、S&P 500 成分 1957 起） | **頁面未載明**：要登入並選授權類型才顯示價格（不登入、不申請） | 有個人（Non-Professional）／專業授權之分；條款原文：「If your use … is in relation to professional activities of any sort, you agree to subscribe to the appropriate professional or institutional license」 | `quantrocket.com/pricing/data/sharadar`（經銷商頁，第2批）；`data.nasdaq.com/databases/SFA` 為 JS 頁抓不到內容 |
| CRSP（經 WRDS，收費） | 含（第2批，大學資料庫說明）：有下市資訊與下市報酬 DLRET；但「correct delisting returns are not available for most of the stocks that have been delisted for negative reasons since 1962」（文獻已知缺口） | 1925 起 | **頁面未載明**：官方頁只有「Request Subscription Information」表單 | **個人實務上取得不到**：官方頁原文「designed for and delivered to licensees at academic institutions, government agencies, and investment practitioners」，WRDS 走機構帳號 | `indexes.morningstar.com/research-data-products/crsp-us-stock-databases`（`crsp.org` 已 301 轉址至此）；`datahub.aalto.fi`、`library.novasbe.pt` 大學資料庫說明 |

## 結論（第2批，供總司令決定時參考；不採購、不申請）

1. **免費的路**：Tiingo 已實測（起訖正確 46.7%，要逐檔核對下市日）；Alpha Vantage 條款允許自用研究，但免費層只給近 100 筆，對已下市股回測沒用；Stooq 條款與 key 都卡在瀏覽器驗證，要總司令本人開瀏覽器。
2. **個人買得到、條款允許自用回測、明確含已下市股**的收費來源有三家：Norgate（Platinum USD 630／年起，1990 起）、EODHD（$19.99～$99.99／月，但哪個方案含下市股頁面沒寫）、Sharadar（1998 起，價格要登入才看得到）。
3. **共同限制**：三家都**禁止展示或轉發**——買了也只能用在本機研究，**不能把價格放進公開 repo 或 App 畫面**（本 repo 是公開的）。Norgate 還規定到期要刪資料。
4. CRSP 是學界標準，但只賣機構，個人路線不可行。
5. 依總司令「App 賺錢前不花錢買資料」，以上全部維持「待採購（暫停）」。
