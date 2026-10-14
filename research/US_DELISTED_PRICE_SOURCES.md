# 美股已下市股價格來源比較表（先.八十六-3，**未完成：第 1 批**）

**狀態**：2026-10-14 DevQueue `20261014-083101` 第 1 批，只查了下表標「本輪」的幾家；其餘欄位標「待查」。下一輪從「待查」那幾格續做。
**原則**：只列官方頁面原文；查不到的寫「頁面未載明」，不猜。**不申請試用、不採購**（總司令「App 賺錢前不花錢買資料」）。key 只放本機 `.env`，不進 repo、不進對話。

| 來源 | 含已下市股？ | 歷史起點 | 費用 | 條款是否允許自用研究 | 查證來源 |
|---|---|---|---|---|---|
| Tiingo（免費） | 實測：60 檔已下市樣本 58 檔已查，found 95%、但起訖正確只有 46.7%（OTC 續掛、代號被沿用） | 對照組 KO 等多數 9,262 筆日線 | 免費：50 次/時、1,000 次/日、500 檔/月 | 官方定價頁 Licensing「Internal Use Only」（只限自用、不得展示或分享） | 先.八十八-2／-3（`tiingo.com/about/pricing`；`research/data/tiingo_delisted_probe.json`） |
| Alpha Vantage（免費） | SIVB 回破產後 OTC 空殼價（陷阱）；TWTR、ATVI 正確 | 免費層只給近 100 筆 | 免費 | 待查 | `docs/US_PRICE_SOURCES.md` 第 224～290 行；先.九十-3 |
| Stooq | 未實測（三個端點都是 JavaScript 驗證牆，依鐵律不繞） | 待查 | 免費 key 要人工過 CAPTCHA | 待查 | `docs/US_PRICE_SOURCES.md` 第 35～64 行；`TRIALS_LEDGER.md` #410 |
| yfinance（參考） | 已下市股 60 檔抽樣只有 2 檔有價 | 在市股 1962 起 | 免費 | README：非 Yahoo 官方、Yahoo 資料限個人使用 | `research/data/us_delisted_price_probe.json`；`github.com/ranaroussi/yfinance` |
| Norgate Data（收費） | Silver／Gold 方案**不含**；Platinum、Diamond 方案含「Delisted securities」（本輪） | Silver 10 年、Gold 20 年、Platinum 1990、Diamond 1950（本輪） | 頁面是動態試算器，擷取不到價格（**待查，未親自驗證**） | 待查 | `norgatedata.com/prices.php`（本輪）；首頁自述「survivorship bias-free」 |
| EODHD（收費） | API 文件有 `delisted=1` 參數可列出已下市代號（本輪，原文以華沙交易所為例）；美股已下市**價格**涵蓋範圍頁面未載明 | 定價頁：「US from the earliest available (Ford Motors from June 1972)」 | 免費 $0（每日 20 次）；Historian $19.99／月、Active trader $29.99、Equity analyst $59.99、ALL-IN-ONE $99.99（年繳較低）（本輪） | 定價頁未區分個人／商業（待查服務條款） | `eodhd.com/pricing`、`eodhd.com/financial-apis/list-supported-exchanges`（本輪） |
| Sharadar（Nasdaq Data Link，收費） | 待查（本輪抓到的頁面只有標題） | 待查 | 待查 | 待查 | `data.nasdaq.com/databases/SFA`（JS 頁，抓不到內容） |
| CRSP（經 WRDS，收費） | 待查 | 待查 | 待查（通常為機構授權） | 待查 | — |

**下一輪續做**：Alpha Vantage／Stooq 條款、Norgate 價格（試算器）、EODHD 服務條款與已下市價格涵蓋、Sharadar、CRSP；全部只讀官方頁面。完成後在 `research/DATA_GAP_PLAN.md` 第 4 節乙類表連過來。
