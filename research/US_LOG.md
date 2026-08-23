# US_LOG.md — 美股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面）。美股軌是全新的，這份檔案從第一輪馬拉松開始就是美股軌唯一的執行記錄。

**規則：** 每個馬拉松輪次結束前 append 一條，包含地基搭建進度（美股軌前期主要是這個）跟之後的因子/策略測試結果，不管有沒有進展都要記錄。

---

## 2026-08-23T02:00:00+08:00 — 美股軌馬拉松初始化

檔案建立，尚未有實際輪次執行。地基完全未搭建，第一輪工作見 `US_MARATHON_STATE.md`。

## 2026-08-23T10:30:00+08:00 — 馬拉松第一輪：里程碑1資料驗證（歷史深度/更新頻率/代號涵蓋）

做了 `US_MARATHON_STATE.md` 建議的第一輪工作單位第 1 項：用 `research/us_probe_milestone1.py`（全部走 `load_dev()`，封頂 VAL_END）實測 `USStockPrice` 的歷史深度、更新頻率，跟 `USStockInfo`（`_fetch()` 直接呼叫，membership 快照，理由同 `universe.py` 對 `TaiwanStockInfo` 的處理）的代號涵蓋範圍。

結果：AAPL/MSFT 都有 1990-01-02 起 8817 筆逐日資料到 VAL_END，2024-06 抽測無漏交易日；`USStockInfo` 是 289 個時間快照疊出來的名單（不是上市日），distinct stock_id 18396 檔（5470 檔 ETF），最新快照（2026-08-22）12429 列。完整細節寫進 `DATA.md`「美股里程碑1」小節。

**沒做的**：美股存活者偏差（下市股名單/歷史價格）完全還沒測——這是這個工作單位刻意排除的部分（一輪只做一件事），留給下一輪。SEC EDGAR PIT 資料源、美股成本模型也都還沒碰。

`is_holdout_consumed()` 確認為 `False`（本輪全程只碰 <=VAL_END 的資料 + 一個不含日期時間序列語意的 membership 快照）。

## 2026-08-23T13:00:00+08:00 — 馬拉松第二輪：SEC EDGAR PIT 資料源文件調查

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 2 項：查證 SEC EDGAR 公開 JSON API 能不能拿到申報日期（filing date）。**這輪完全是文件調查，沒有寫程式碼、沒有實際打過 `data.sec.gov` 的任何 API 請求。**

查到：submissions API（`data.sec.gov/submissions/CIK{cik}.json`）文件顯示每筆申報記錄同時有 `filingDate`（申報日）跟 `reportDate`（財報期間結束日）兩個獨立欄位；XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）據稱每個數值點也帶 `filed` 欄位。如果實測驗證屬實，美股 PIT 可以比台股「+45天保守假設」精確很多。查證來源是第三方 wrapper 文件（`sec-edgar-api.readthedocs.io`），因為 `www.sec.gov` 本身的網頁對本環境的 fetch 工具回傳 403（原因未查明），只能先參考轉述來源，**還沒有一手驗證**。完整細節、還沒查的部分（rate limit 官方原文、資料回溯深度等）寫進 `DATA.md`「美股 PIT 資料源調查」小節。

**沒做的**：完全沒有實際呼叫任何 SEC EDGAR API，欄位結構是否真的如文件所述、能不能順利解析，都還是假設——下一輪建議直接對 AAPL（CIK=0000320193）打一次 submissions API 驗證。美股存活者偏差、成本模型也還沒碰。

`is_holdout_consumed()` 確認為 `False`（本輪完全沒有觸碰任何 FinMind 或 alpha.db 資料，純網路文件查證）。

## 2026-08-23T13:35:00+08:00 — 馬拉松第三輪：SEC EDGAR API 實測驗證

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 1 項：把第二輪的文件調查升級成真實 API 呼叫。寫了 `research/sec_edgar_probe.py`，先手動確認 `data.sec.gov` 沒有 `robots.txt`（404，等於沒有額外爬取限制）、`www.sec.gov/robots.txt` 沒有 disallow 相關路徑，再對三檔股票（AAPL、MSFT、PLTR——刻意加一檔非巨型股避免重蹈第一輪只測兩檔大型股的偏差）打了 `www.sec.gov/files/company_tickers.json` 跟 `data.sec.gov/submissions/CIK{cik}.json`。

**結果：全部驗證通過。** `filingDate`/`reportDate` 欄位確實存在（三檔都200 OK），ticker→CIK對照表也可用（10403筆）。新發現：10-K/10-Q 的 filingDate−reportDate 天數差因公司而異，AAPL平均33.1天、MSFT平均27.5天，但PLTR平均41.5天（範圍34–57天）——比兩檔大型股寬不少，代表未來設計「找不到精確filingDate時的保守預設值」不能只用大型股估。另外發現 `filings.files[]` 分頁機制可以拿到更早期申報記錄（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有抓分頁內容。完整數字寫進 `DATA.md`「美股 PIT 資料源調查」小節（已從「文件調查」升級為「已驗證」，原第二輪記錄摺疊保留在該小節底部作對照）。

**沒做的**：XBRL company facts API（據稱有更細的 `filed` 欄位）完全沒測；`filings.files[]` 分頁檔案內容沒抓；美股存活者偏差、成本模型都還沒碰；`sec_edgar_probe.py` 目前只是探測腳本，還沒包裝成可重用的 fetch 函式。這不是一次統計檢定（沒有因子/策略假說被測試），所以 `TRIALS_LEDGER.md` 不需要加列，跟 `MARATHON_PROTOCOL.md` 第1c節「地基工作」的精神一致。

## 2026-08-24T22:05:00+08:00 — 馬拉松第十輪：XBRL company facts API 實測，發現比較期重複揭露陷阱

做了 `US_MARATHON_STATE.md` 建議工作單位第 3 項（獨立於 FRC/SBNY CIK 未解問題）：實測 `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`，用第三輪已驗證的三個 CIK（AAPL/MSFT/PLTR）。新寫 `research/sec_edgar_xbrl_facts_probe.py`。

**結果：端點可用，但發現一個重要陷阱。** 每個資料點確實有 `end`/`filed` 欄位，結構跟文件轉述一致。但天真算 `filed - end` 的 PIT gap 出現不合理離群值（AAPL max=772天）——追查發現這是「每個資料點」層級（不是「每次申報」層級）的設計：同一財報期間會在後續申報裡以比較期形式重複出現。實測驗證：AAPL 74個不同 `end` 日期裡 71個（96%）被超過一次申報引用。**結論：要用這個 API 做 PIT 必須先按 `end` 分組取最小 `filed`，不能直接用原始欄位值**，跟 submissions API（每次申報一筆、沒有這個問題）不一樣。另外發現 XBRL concept 名稱不穩定（`Revenues` 只回溯到2016，`EarningsPerShareDiluted` 回溯到2007，PLTR 甚至沒有 `Revenues` concept），推測是不同年代/公司用不同 concept 名稱申報同一語意。完整細節寫進 `DATA.md`「美股 PIT 資料源調查（續）」小節。

**沒做的**：修正後（取最小filed分組）的 gap 統計沒有重新算；concept 名稱隨時間變化的完整對照表沒有系統化列出；`filings.files[]` 分頁檔案內容仍未抓；FRC/SBNY CIK 問題、美股存活者偏差、成本模型都還沒碰，這輪刻意獨立於這些未解問題之外。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列。

`is_holdout_consumed()` 確認為 `False`（本輪只打 SEC EDGAR 公開 API，沒有碰 FinMind 或 alpha.db）。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。

## 2026-08-23T15:35:00+08:00 — 馬拉松第四輪：美股存活者偏差實測（負面結果）

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 1 項：實測台股 `universe.py` 的核心方法（`TaiwanStockPrice` 有沒有某天資料 = 那天能不能交易的地面真相）跟 `USStockInfo` 快照增減法，能不能直接搬到美股。寫了 `research/us_survivorship_probe.py`，挑 5 檔涵蓋不同下市原因（收購下市、銀行倒閉被接管、破產）跟不同年份的已知下市/出事美股：TWTR、SIVB、SBNY、FRC、BBBY。

**結果：兩個候選方法都不可靠，這是重要的負面發現。**
- 價格資料法：`TWTR`／`SIVB`／`FRC` 三檔 `USStockPrice` 完全 EMPTY（一筆都沒有，資料直接消失不是保留到下市日）；`SBNY`（96筆，全落在2024-08~12月）／`BBBY`（5687筆，2002~2024連續無缺口）兩檔的資料時間軸都跟「已知下市日」對不上——`SBNY`完全找不到倒閉前的歷史，`BBBY`則是完全沒有下市痕跡（逐日檢查2023-04~09確認無交易缺口、無價格斷層），懷疑是代號重用（ticker reuse，美股特有、台股沒有的陷阱）或原本記憶中的下市日不準確，這輪沒有進一步查證是哪一種。
- `USStockInfo` 快照法：`TWTR` 289個快照裡只出現1次（2019-01-10）卻實際活躍交易到2022年，證明快照本身對活躍股票的覆蓋率就有嚴重缺口，不是只有下市股才會漏，這個方法從根本上不可靠。

**重要限制（誠實記錄）**：這輪用來 sanity check 的「已知下市日」是憑一般常識記憶寫進腳本的參考值，**沒有用權威資料源逐一核實**，所以無法百分之百確定 `SBNY`／`BBBY` 的異常是代號重用還是我的記憶本身不準——下一輪如果要繼續深挖，應該先用第三輪已驗證可用的 SEC EDGAR API（`company_tickers.json`+`submissions`，甚至查 Form 25/25-NSE 下市申報）去核實真實下市時間，而不是繼續依賴記憶。

完整數字寫進 `DATA.md`「美股存活者偏差調查」小節、`US_MARATHON_STATE.md`。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列，跟第二、三輪地基工作的先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪 `USStockPrice` 全走 `load_dev()` 封頂 VAL_END=2024-12-31，`USStockInfo` 走 `_fetch()` 直接呼叫，跟 `universe.py`/`us_probe_milestone1.py` 對 membership 快照的既有先例一致，測試的5檔股票下市時間都遠早於 VAL_END，沒有觸碰 holdout 邊界後的資料）。

## 2026-08-23T18:30:00+08:00 — 馬拉松第五輪：SEC EDGAR Form 25 核實下市案例

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 1 項：接續第四輪負面結果，用第三輪已驗證可用的 SEC EDGAR API 去核實第四輪憑記憶寫的「已知下市日」是否準確，而不是繼續依賴人的記憶。寫了 `research/sec_edgar_delisting_probe.py`，對同一組 5 檔股票（TWTR/SIVB/SBNY/FRC/BBBY）先試現行 `company_tickers.json` ticker→CIK 對照，查不到就退回腳本內手寫的備援 CIK，掃 `submissions` API 的 `filings.recent` 找 Form 25／25-NSE／15-12B／15-12G 這類下市/註銷申報。

**結果：3 個確認、1 個重要新發現、2 個本輪失敗（誠實記錄）。**
- `TWTR`：確認為真下市，`25-NSE`（2022-10-28）跟第四輪記憶的末交易日（2022-10-27）只差1天——**第四輪的假設是對的，`USStockPrice` EMPTY 是真實資料缺口**。
- `SIVB`：確認為真下市，`25-NSE`（2023-05-02），但發現同一家公司 2017-2018 還有一組更早的下市/註銷申報（可能是不同證券類別，未分辨），加上 2025-01-24 還有後續申報——**下市不是單一乾淨日期，之後設計「下市日」欄位要考慮這種複雜性**。
- `BBBY`：**這輪最重要的發現**——現行 `company_tickers.json` 把 ticker `BBBY` 指向 CIK 1130713，公司名是「NEIGHBORHOOD INTELLIGENCE, INC.」，完全不是 Bed Bath & Beyond。獨立確認代號重用是真的，而且證據比第四輪的「價格時序對不上」的間接推論更直接。**方法論教訓：連 SEC 自己現行的 ticker 對照表都會被重用代號誤導，任何用「ticker→身分」單一現行對照表的設計對已下市/改名股票都不安全。**
- `SBNY`：**這輪失敗**——腳本裡手寫的備援 CIK（1288776）猜錯，查到的是「GOOGLE INC.」的申報記錄，結果作廢。這推翻了腳本 docstring 原本的假設（「CIK 是永久識別碼，手寫備援不像手寫日期那樣有猜錯風險」）——**手寫任何未經查證的識別碼都有風險，不是 CIK 就比較安全**，這個錯誤假設需要在下一輪修正腳本時一併處理。
- `FRC`：查不到 Form 25（`filings.recent` 視窗43筆，涵蓋2004-01-05到2024-02-09，理論上該涵蓋已知收購日2023-05-01卻完全沒有）。未解決，可能是視窗覆蓋不到、FDIC接管走不同申報機制、或需要查 `filings.files[]` 分頁檔案，這輪沒有查證是哪一種。

完整數字寫進 `DATA.md`「美股存活者偏差調查（續）」小節、`US_MARATHON_STATE.md`。

**沒做的**：`SBNY` 需要重新查證正確 CIK（不能再猜）；`FRC` 需要抓 `filings.files[]` 分頁檔案；`sec_edgar_delisting_probe.py` docstring 裡「CIK 比日期安全」的錯誤假設沒有在這輪修正腳本本身（一輪一個工作單位，這輪工作單位是「跑探測+誠實記錄結果」，修腳本留給下一輪）；XBRL company facts API、中小型股價格深度抽測、美股成本模型都還沒碰。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列，跟第二～四輪地基工作的先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。

## 2026-08-24T09:40:00+08:00 — 馬拉松第六輪：重查 `SBNY` 正確 CIK（失敗，但排除兩個錯誤候選+修正腳本）

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 1 項：接續第五輪失敗的待辦，重新查證 Signature Bank（SBNY）正確的 CIK，不能再手寫猜測值。

**過程**：先試 `www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=signature+bank`（有無 `type=25` 過濾都試過），查到 CIK 1288784「Signature Bank Corp」（Greeley, CO 的小型銀行控股公司）——查了 `submissions` API 確認公司名稱後發現這**不是**紐約那家倒閉的 Signature Bank，只是名字類似的無關公司。接著改用 `efts.sec.gov` 全文檢索，試了 `q="Signature Bank"`／`q="SBNY"` 搭配多種表單（10-K、8-K、25-NSE、15-12B、15-12G）跟時間範圍，entity 聚合結果裡從未出現任何名稱含「Signature」的申報實體。最後針對「Form 25-NSE，2023-03-01～2023-06-30」（已知的接管時間窗口）逐頁抓完全部 200 筆命中的申報實體名單，**沒有一家含「Signature」**——同一次查詢正確找到 `SVB FINANCIAL GROUP`（SIVB），證明查詢方法本身有效。

**結果：`SBNY` 正確 CIK 仍未查到，這輪排除了兩個錯誤候選（1288776=Google，第五輪已知；1288784=無關的 CO 小型銀行，這輪新排除），沒有找到替代候選。** 附帶發現一個方法論教訓：`browse-edgar` 公司名稱搜尋在沒有精確符合的公司名時會自動跳到字母排序最近的單一公司，不是回傳候選清單，之前誤以為它會像搜尋引擎一樣列多筆候選是錯的假設。另外發現一個值得記錄的新線索：`SBNY`（這輪）跟 `FRC`（第五輪）兩個獨立的「FDIC 接管型下市」案例都查不到 Form 25，而 `TWTR`／`SIVB`（一般下市/併購）都乾淨查到，這輪把這個模式記錄為未查證的假設，留給下一輪。

**這輪也做了**（跟查證同一個工作單位範疇內，屬於同一個待辦第1項）：修正了 `sec_edgar_delisting_probe.py` 的 docstring（移除「CIK 比日期安全」的錯誤假設，改成明確說明第五輪 `SBNY` 案例已經證偽這個假設）跟 `FALLBACK_CIK` 字典（`SBNY` 改成 `None` 並加註解「已知錯誤待查，不要用猜的」，其他四檔標註「已驗證正確」）。完整細節寫進 `DATA.md`「美股存活者偏差調查（再續）」小節、`US_MARATHON_STATE.md`。

**沒做的**：正確的 `SBNY` CIK 仍然未知；`FRC` 的 `filings.files[]` 分頁檔案沒有抓過；「FDIC 接管型下市不走 Form 25」的假設沒有用 SEC EDGAR 以外的資料源（FDIC BankFind Suite、Nasdaq 官方公告）查證，只是這輪觀察到的模式；XBRL company facts API、中小型股價格深度抽測、美股成本模型都還沒碰。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列，跟第二～五輪地基工作的先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。

## 2026-08-24T20:35:00+08:00 — 馬拉松第七輪：查 `FRC` 的 `filings.files[]` 分頁（意外發現 CIK 本身可能查錯實體）

做了 `US_MARATHON_STATE.md` 建議的下一輪工作單位第 2 項：查證第五輪「`FRC` 查不到 Form 25」是不是因為 `filings.recent` 視窗覆蓋不到、需要抓 `filings.files[]` 分頁檔案。新寫 `sec_edgar_frc_cik_probe.py`。

**過程與結果**：
1. **先解決原本要查的問題**：CIK 1132979（第五輪的 FRC 備援 CIK）的 `filings.files[]` 是空陣列——代表 `filings.recent`（43筆，2004-01-05～2024-02-09）本身就是完整記錄，不是被截斷的近期視窗。**視窗覆蓋不到這個可能性可以排除。**
2. **但過程中發現更根本的問題**：這個 CIK 的 43 筆申報**全部是 `SC 13G`／`SC 13G/A`（受益所有權揭露）＋1 筆 `40-6B/A`，完全沒有任何 10-K／10-Q／8-K**——一家 NYSE 掛牌十幾年、資產規模破 2000 億美元的銀行控股公司不可能是這種申報型態。**第五輪只核對「公司名稱是 FIRST REPUBLIC BANK」就判定「已驗證」，沒有核對申報型態是否合理，這是一個方法論漏洞**——這個 CIK 很可能是 FRC 旗下信託/財富管理部門以機構投資人身分申報的 CIK，不是 FRC 本身對 SEC 申報年報用的公司 CIK。
3. **嘗試找正確 CIK，三管齊下都失敗**：`browse-edgar` 公司名稱搜尋跳到 CIK 770975「FIRST REPUBLIC BANCORP INC」，但那是**另一家舊公司**（申報止於2008，還有一筆真的 Form 25 是2005年下市/私有化——第三個踩到「同名不同實體」陷阱的案例，前兩個是 BBBY／SBNY）；`efts.sec.gov` 全文檢索限定 Form 25-NSE＋2023-04-01～2023-08-31（FRC接管日窗口）搜「republic」只找到1筆不相干結果；`entityName=First Republic Bank`＋Form 10-K 只找到2筆不相干的抵押貸款證券化信託。**2010-2023年那個真正在NYSE掛牌的FRC的正確CIK，這輪沒有找到，仍是開放問題。**
4. **對第六輪「FDIC接管型下市不走Form 25」假設的影響：這個假設變弱了**。第六輪把 `SBNY`＋`FRC` 當成兩個獨立支持證據，但這輪發現 `FRC` 案例從一開始查的就是錯誤實體，「FRC真的查不到Form 25」這個結論從來沒有被真正驗證過。這個假設應該從「兩個獨立案例支持」降級為「一個未解案例（SBNY）＋一個查錯實體的無效案例（FRC）」。

完整數字寫進 `DATA.md`「美股存活者偏差調查（再再續）」小節、`US_MARATHON_STATE.md`。也同步更新了 `sec_edgar_delisting_probe.py` 的 `FALLBACK_CIK["FRC"]`（從 1132979 改成 `None`）跟對應註解，標記為「已知很可能是錯誤實體，不要用猜的」，跟現有 `SBNY` 的標註方式一致。

**沒做的**：正確的 FRC CIK（2010-2023年那個真正掛牌的實體）仍未找到，下一輪如果要繼續可以試 FDIC BankFind Suite 或 Nasdaq 官方停牌公告（跳出SEC EDGAR，需先確認公開可讀）；`SBNY` 仍未查到任何候選；XBRL company facts API、中小型股價格深度抽測、美股成本模型都還沒碰。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列，跟第二～六輪地基工作的先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。

---

## 第十一輪（2026-08-24T04:05:00+08:00）：XBRL company facts 修正後 gap 統計重算，發現兩類殘留離群值成因

**工作單位**：接續第十輪明確留下的下一步——「同一 `end` 分組取最小 `filed`」的去重邏輯只被驗證過陷阱存在，沒有實際算過修正後的數字。這輪把它算出來。

**做了什麼**：新寫 `research/sec_edgar_xbrl_facts_dedup_probe.py`（第十輪的 `sec_edgar_xbrl_facts_probe.py` 保留不動，維持探測腳本本身的歷史記錄）。對 AAPL/MSFT/PLTR 三檔（沿用第三輪已驗證的 CIK）、`EarningsPerShareDiluted`／`Revenues` 兩個 concept，同一 `end` 只保留最小 `filed`（10-K/10-Q），重算 gap 統計，並跟第十輪的未去重原始數字並列輸出。

**結果**：
- 中位數大幅改善：AAPL EPS median=32天、MSFT=28天、PLTR=40天——**貼近第三輪 submissions API 測到的水準**（AAPL平均33.1天/MSFT平均27.5天），代表去重邏輯本身抓對了方向，大多數資料點的離群值確實是「比較期重複揭露」造成的假象。
- 但 `max` 幾乎沒變（AAPL 759天、MSFT 1034天，Revenues更明顯，去重後平均反而更高因為樣本數太少被離群值拖走）——去重是必要但不充分的修正。
- 追查殘留離群值：抽樣核對 MSFT 最大離群值（`end=2007-09-30`, `filed=2010-07-30`）的原始資料列，發現 `fy=2010`／`form=10-K`——是2010年10-K的「五年精選財務數據」表格重新揭露2007年數字，不是原始申報。統計全部離群值的`end`日期分布：AAPL/MSFT離群值全部落在2007–2009年（推測是這兩家公司XBRL強制標記生效前的期間，原始申報未被XBRL標記，company facts API裡完全沒有這筆原始紀錄）；PLTR離群值全部落在2020年9月IPO之前（上市前無公開申報義務，這是真實結構性事實，不是資料陷阱）。
- 詳細數字跟解讀已寫進 `DATA.md`「美股 PIT 資料源調查（再續）」小節，`US_MARATHON_STATE.md` 已同步更新。

**沒做的**：只測了3檔股票、2個concept；沒有查證每家公司確切的XBRL強制標記生效日期（只用「~2009年中」概略時間點做形狀比對，這是SEC對大型加速申報者的分階段生效時間，沒有逐公司查證）；沒有實際測試「排除pre-XBRL期間+排除pre-IPO期間後gap是否全部落在合理範圍」（這是驗證上述假說的直接方法，留給下一輪）；沒有驗證更多公司樣本確認這兩種模式是否普遍成立。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列，跟第二～十輪地基工作的先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪只打了 SEC EDGAR 公開 API，完全沒有觸碰任何 FinMind 或 alpha.db 資料）。取鎖時第0節第2步偵測結果：`LOCK_ACQUIRED`（乾淨取得，非陳舊鎖檔，上一輪正常結束）。

---

## 第35輪（2026-08-24T06:02:00+08:00）：中小型股/近期IPO股 USStockPrice 深度抽測 — 一開始就撞 FinMind 402 額度牆，優雅收工

**工作單位**：接續「下一輪建議工作單位」第4項——`us_probe_milestone1.py`（2026-08-23）只測了 AAPL/MSFT 兩檔巨型股，`US_MARATHON_STATE.md` 明確警告「不能假設全市場都一樣深」。

**做了什麼**：
1. 讀取已快取的 `USStockInfo` 最新快照（2026-08-22，12429列），用 `MarketCap`／`IPOYear` 欄位篩選出兩組候選（只挑純字母代號，排除 W/WS/U/R 這類權證/單位後綴，避免混進不同金融工具類別）：
   - 中小型股組（MarketCap 3億～20億美元）：`XPER`、`SWIM`、`IMOS`、`ABR`、`OCSL`（seed=3 隨機抽樣）。
   - 近期IPO組（2021–2023年上市，MarketCap>1億美元）：`FINW`、`LAW`、`NRGV`、`GPCR`、`CAVA`（同抽樣方法）。
2. 新寫 `us_probe_price_depth_smallmid.py`（跟 `us_probe_milestone1.py` 同款結構，透過 `load_dev()` 抓 `USStockPrice`，只印結果不改其他檔案）。
3. **執行時，第一檔（`XPER`）就打到 HTTP 402**（`{"msg":"Requests reach the upper limit."...}`）——本機快取（`data/raw/`）裡完全沒有這 10 檔的價格資料（跟第 34 輪台股回補撞到的限流是同一個全域額度池，前幾輪台股回補批次已經先把這小時的額度用光），連第一次呼叫都直接被拒絕，不是跑到一半才斷。

**判定**：依 `MARATHON_PROTOCOL.md` 第4節「任何一次 FinMind 呼叫回傳 402...優雅結束這一輪...不要為了硬跑而狂重試」——立刻停手，不重試。腳本本身已經寫好、邏輯正確（候選篩選方法有記錄在 docstring 裡可重現），只是這輪沒有額度可以執行。**下一輪（或額度明顯恢復後的任何一輪）如果要接美股軌，直接跑 `python us_probe_price_depth_smallmid.py` 即可，不需要重新設計。**

**沒做的**：中小型股/近期IPO價格深度完全沒有實測到任何數字（0/10檔）；「下一輪建議工作單位」清單裡第1、2、3、5項也都沒碰。這不是因子/策略統計檢定，`TRIALS_LEDGER.md` 不需要加列。

`is_holdout_consumed()` 確認為 `False`（唯一一次外部呼叫是被 FinMind 402 拒絕，沒有任何資料真的進來，更沒有碰 holdout）。取鎖時第0節第2步偵測結果：`LOCK_ACQUIRED`（乾淨取得，非陳舊鎖檔，上一輪正常結束）。

## 2026-08-24T07:31:16+08:00 — 馬拉松第38輪（US軌）：完成第5項待辦（`sec_edgar_probe.py` 邏輯包裝成可重用模組 `sec_edgar_client.py`）

**取鎖/選軌**：取鎖乾淨成功（`LOCK_ACQUIRED`，非陳舊鎖檔，上一輪正常結束）。三軌「最後更新」時間戳比對：US（06:02:00）早於FUT（06:32:00）跟TW（07:06:36），輪替規則指向US。

**先試了什麼、為什麼換方向**：本來想直接接「下一輪建議工作單位」第4項（中小型股/近期IPO價格深度抽測，`us_probe_price_depth_smallmid.py` 已就緒），但實際執行第一檔（`XPER`）就立刻撞 FinMind `HTTP 402`（「Requests reach the upper limit」）——推測是TW軌第37輪（07:06，同一小時內）的全市場宇宙回補剛用掉大量額度，25分鐘不足以恢復。依`MARATHON_PROTOCOL.md`第4節「不要為了硬跑而狂重試」，立刻停手（未修改`us_probe_price_depth_smallmid.py`本身，腳本原樣保留待下次額度恢復再跑），改做清單裡不需要FinMind額度的第5項。

**做了什麼**：新增 `research/sec_edgar_client.py`——把 `sec_edgar_probe.py`（第三輪，2026-08-23）驗證過的 ticker→CIK 查詢跟 `filings.recent` 的 filingDate/reportDate（PIT訊號）抽取邏輯，包裝成四個可被其他程式呼叫的函式：`get_cik_map()`、`get_cik(ticker, cik_map=None)`、`get_submissions(cik)`、`get_filing_dates(cik, forms=("10-K","10-Q"))`（回傳含`gap_days`的list of dict）。快取機制仿照`finmind_client.py`的精神（笨拙但可信的exact-key快取），存在`research/data/raw/SEC_*.json`（gitignored），24小時內同一份不重打SEC，避免違反SEC公平使用政策。**刻意不包**XBRL company facts（`sec_edgar_xbrl_facts_*_probe.py`）跟下市/Form 25核實邏輯（`sec_edgar_delisting_probe.py`／`sec_edgar_frc_cik_probe.py`）——這兩類仍是探測階段、有未解問題，不該提前固化進可重用模組，維持「一輪只做一件事」的範圍。

**驗證**：跑了模組自帶的 smoke test（`if __name__ == "__main__"`區塊，對AAPL/MSFT/PLTR做跟第三輪探測腳本一樣的查詢），結果**跟第三輪`US_MARATHON_STATE.md`記錄的數字完全一致**（AAPL n=45, min=25, max=37, avg=33.1；MSFT n=25, min=24, max=30, avg=27.5；PLTR n=24, min=34, max=57, avg=41.5），證明包裝後的函式行為跟原本探測腳本一致，沒有在重構過程中悄悄改變邏輯。

**判定**：這是基礎建設工作單位（第1c類），不是因子/策略統計檢定，`TRIALS_LEDGER.md`不需要加列。

**下一步**：`US_MARATHON_STATE.md`「下一輪建議工作單位」清單第5項已完成，其餘1/2/3/4項還在。**額度恢復後優先選第4項**（腳本已就緒）；額度緊張時選第1/2項（不需要FinMind額度，找FRC正確CIK或SBNY下市日）。之後如果要幫US軌搭`pit.py`類似邏輯，可以直接`from sec_edgar_client import get_filing_dates`，不用重新寫SEC API呼叫。

`is_holdout_consumed()` 確認為 `False`（本輪完全沒有呼叫任何FinMind函式，唯一一次外部呼叫是SEC EDGAR被402前的`us_probe_price_depth_smallmid.py`嘗試，跟後面的`sec_edgar_client.py`smoke test，都不碰holdout）。
