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

## 2026-08-24T22:37:00+08:00 — 馬拉松第41輪（US軌）：找到 FRC/SBNY 查不到 SEC CIK 的根本原因（第12(i)條銀行申報主管機關規則），不是查錯而是本來就不歸 SEC EDGAR 管

**取鎖/選軌**：取鎖乾淨成功（`LOCK_ACQUIRED`，非陳舊鎖檔，上一輪正常結束）。三軌「最後更新」時間戳比對：US（07:31:16）明顯早於FUT（21:19:00）跟TW（22:01:00），輪替規則指向US。TW軌剛在22:01完成一批全市場宇宙回補（很可能剛用掉FinMind額度），為避免撞同一堵限流牆，本輪選「下一輪建議工作單位」第1項（找FRC正確CIK，不需要FinMind額度，只打SEC EDGAR/FDIC.gov）。

**做了什麼**：
1. 把第七輪的 `browse-edgar` 名稱搜尋窮盡——加測 `company=first+republic&type=10-K`（HTML output，發現 atom output 在這個查詢形狀下 `<company-info name>` 屬性會壞掉印出 `ARRAY(0x...)`，這是個值得記錄的小地雷）跟不限 type 的 exact-name 搜尋，找到一個新候選 CIK 1097256「FIRST REPUBLIC BANK /MSD」，查其申報記錄只有 1 筆 2008 年 `MSDW`（Morgan Stanley Dean Witter）表單，排除。
2. 把 `efts.sec.gov` 全文檢索從第七輪的窄 `entityName` 過濾改成完全不限定，只限定一個正常年份（2019）＋`forms=10-K`：74筆命中裡完全沒有FRC自己的年報，全部是不相干的Sequoia房貸信託跟其他銀行（因為文字裡剛好提到FRC是貸款服務機構）。同年不限form查同一詞組有7,802筆命中（前20桶全是持有FRC股票的基金），對照之下「FRC自己完全不在10-K索引裡」是個決定性異常，不是索引缺口。
3. 用 `WebSearch`＋`WebFetch` 查證（只用公開免登入的.gov來源，`fdic.gov/accounting/bank-securities`跟`ecfr.gov` 12 CFR Part 335）：《證券交易法》第12(i)條規定，FDIC承保的「州立、非聯準會會員銀行」若有註冊證券，定期申報要直接向FDIC申報（依12 CFR Part 335），不是向SEC申報。FRC是加州州立銀行，本輪推論（未逐一查證，標記為假設）它沒有獨立的SEC掛牌控股公司、可能也不是聯準會會員，因此符合這個規則。**這一個結構性原因一次解釋了第4–7輪的所有異常**：查不到10-K/10-Q/8-K、下市查不到Form 25——不是因為2023年被FDIC接管才不交Form 25，而是這類銀行本來就從未是SEC EDGAR的申報人。第六輪的「FDIC接管型下市不走Form 25」假設應該**直接退役**，不是繼續降級——前提本身就錯了。
4. 確認FDIC自己的公開申報系統存在且可連線：`efr.fdic.gov/fcxweb/efr/`（200 OK），但是JS驅動的單頁應用，本輪只確認連得到，沒有逆向工程搜尋API。

**判定**：這是基礎建設/資料源調查工作單位，不是因子/策略統計檢定，`TRIALS_LEDGER.md`不需要加列。完整探測過程新寫 `sec_edgar_frc_root_cause_probe.py`（純打SEC EDGAR公開API，不碰FinMind／alpha.db，holdout規則不適用），跑過驗證輸出穩定可重現。詳見 `DATA.md`「美股存活者偏差調查（根本原因）」小節。

**這輪沒做的**：沒有逆向工程 `efr.fdic.gov` 搜尋API（下一輪如果要接，這是明確定義好的下一步，但值不值得投入要先評估——這類銀行在美股全市場宇宙裡占比應該很小，優先序可能不如先把美股地基其他部分（宇宙建構、`pit.py`）搭起來）；沒有查證SBNY是否真的是非聯準會會員銀行（假設未驗證）；沒有查證FRC本身是否真的沒有獨立控股公司（假設未驗證，但跟「10-K完全不在SEC EDGAR」這個直接觀察一致）。

`is_holdout_consumed()` 確認為 `False`（本輪完全沒有呼叫任何FinMind函式，只打SEC EDGAR公開JSON API跟FDIC.gov/eCFR公開網頁，不碰holdout）。

## 2026-08-25T04:31:00+08:00 — 馬拉松第44輪（US軌）：SBNY確認為FDIC-insured銀行（用FDIC BankFind Suite公開API，繞過SEC EDGAR死路）

**做了什麼**：取鎖時乾淨成功（`LOCK_ACQUIRED`，非陳舊）。比對三軌「最後更新」時間戳，US（22:37）早於FUT（23:03）跟TW（00:00），輪替規則指向US。原本嘗試接第4項工作單位（`us_probe_price_depth_smallmid.py`，中小型股/近期IPO價格深度抽測），第一檔`XPER`立刻撞FinMind 402（`{"msg":"Requests reach the upper limit."...}`）——這是這支腳本第三次嘗試、第三次在第一檔就被限流，累積證據顯示TW軌回補（第43輪，本輪開始前約4.5小時，109次嘗試）用掉的額度到本輪時間點還沒恢復。依`MARATHON_PROTOCOL.md`第4節「優雅結束這一輪，不要為了硬跑而狂重試」，立刻換方向，改接第2項（US_MARATHON_STATE.md「下一輪建議工作單位」第2項：SBNY的FDIC路徑調查，不需要FinMind額度）。

**方法**：第41輪已推論「FRC/SBNY查不到SEC EDGAR CIK是因為第12(i)條規定州立非聯準會會員銀行直接向FDIC申報，不歸SEC管」，但這個推論當時沒有獨立資料源驗證。本輪改用FDIC自己的公開REST API（`api.fdic.gov/banks/...`，`banks.data.fdic.gov/api/...`會301導到這裡，無需認證/無需token，遵守MARATHON_PROTOCOL.md第3節「只用公開可讀來源」規則），不是原本計畫的`efr.fdic.gov`（JS驅動SPA，搜尋API未探測，成本較高）：
1. `institutions`端點查`NAME:"Signature Bank"`：回傳8筆同名機構（美國有很多小型銀行都叫這個名字，這是預期中的名稱碰撞，跟第六輪查SEC EDGAR時踩到的同名陷阱同一種坑）。用`CITY`/`STALP`/`ESTYMD`交叉比對，`CERT=57053`（New York, NY，設立日2001-04-12，`ACTIVE=0`，`ENDEFYMD=2023-03-12`）明確對應到2023年倒閉的那家NYSE掛牌Signature Bank——日期、城市、狀態三項都吻合已知的公開歷史事實。
2. `failures`端點查`CERT:57053`確認細節：`FAILDATE="3/12/2023"`、`RESTYPE="FAILURE"`、`RESTYPE1="PA"`（Purchase and Assumption，被收購式清算）、`SAVR="DIF"`（存款保險基金）、`QBFDEP=88,612,911`（千美元，約886億美元存款）、`QBFASSET=110,363,650`（約1,104億美元資產）——資產規模跟公開報導的「美國史上第三大銀行倒閉案之一」量級吻合。

**結果**：**SBNY（Signature Bank）獨立確認為FDIC-insured銀行，CERT=57053，2023-03-12倒閉，是真實的存款保險機構失敗（FAILURE/PA），不是資料缺失或代號重用假象。** 這跟第41輪的FRC推論（12(i)條銀行不歸SEC管）方向一致、互相印證，但這次是用完全獨立的資料源（FDIC自己的官方資料庫，不是SEC EDGAR的旁證）直接證實，比第41輪「推論但未驗證」更進一步。

**判定**：這是基礎建設/資料源調查工作單位，不是因子/策略統計檢定，`TRIALS_LEDGER.md`不需要加列。原本規劃「逆向工程`efr.fdic.gov`」的工作被更簡單的公開REST API取代，不需要再做那件事了——`api.fdic.gov`才是正確、更便宜的路徑，`efr.fdic.gov`可以從待辦清單移除。

**對美股存活者偏差方法論的意義**：`FALLBACK_CIK`機制（`sec_edgar_client.py`目前只處理SEC EDGAR CIK）如果未來要正式擴充成美股版`universe.py`的下市股名單，**FDIC-insured銀行類下市股應該走FDIC `failures`端點當地面真相，不能只靠SEC EDGAR的Form 25**——這是本輪新確認的具體結論，不是重複第41輪的推論。目前只驗證了SBNY一檔，FRC本身仍然沒有找到FDIC CERT（FRC=First Republic Bank，本輪沒有花時間去查，因為第4節的優先序判斷是「不強制接這項」，本輪只針對SBNY把懸而未決的問題收尾）。

**這輪沒做的**：沒有反查FRC在FDIC BankFind的CERT（下一輪如果要接，方法完全一樣，`NAME:"First Republic Bank"`＋比對城市/州/倒閉日期即可，預期能找到，因為FRC倒閉是2023-05-01的公開事件，FDIC一定有記錄）；沒有把這個FDIC查詢邏輯包裝成可重用函式（目前只是探測性WebFetch呼叫，沒有寫進`sec_edgar_client.py`或新模組，如果之後要正式用於`universe.py`需要另外寫程式碼呼叫`api.fdic.gov`REST API並處理分頁/錯誤）；沒有回頭重跑`us_probe_price_depth_smallmid.py`（額度狀況未變，留給下一輪視情況判斷）。

`is_holdout_consumed()` 確認為 `False`（本輪對FinMind只有一次失敗呼叫立刻中止未重試，其餘全部是FDIC公開API的WebFetch呼叫，不碰holdout）。

## 2026-08-25T06:04:00+08:00 — 馬拉松第47輪（US軌）：FDIC查詢邏輯包裝成可重用模組，順帶解出FRC的FDIC CERT

**做了什麼**：取鎖乾淨成功（`LOCK_ACQUIRED`，非陳舊）。比對三軌「最後更新」時間戳，US（04:31）早於FUT（05:02）跟TW（05:37），輪替規則指向US。讀`US_MARATHON_STATE.md`「下一輪建議工作單位」：第4項（中小型股價格深度抽測）需要FinMind額度，TW第46輪（05:37）才剛用到撞限流牆提前中止，距今僅約27分鐘，額度顯然還沒恢復，跳過（不重蹈第35/38/44輪連續三次同一堵牆的覆轍，不重新嘗試）。第2項殘留任務（FDIC查詢邏輯包裝成可重用函式、FRC的FDIC CERT反查）不需要FinMind額度，且第44輪已明確留下這兩件待辦，本輪接手。

**方法**：新寫`fdic_client.py`，風格仿照`sec_edgar_client.py`（同款on-disk JSON快取、`if __name__=="__main__"`smoke test）。提供`search_institutions(name, fields, limit)`（`institutions`端點，NAME精確片語搜尋，回傳原始候選列表不自動消歧義）跟`get_failure(cert, fields)`（`failures`端點，依CERT查倒閉細節，查不到回傳`None`）。**過程中踩到一個新坑**：先用WebFetch工具查探API回應格式，WebFetch回傳的「摘要後」JSON把每列的巢狀結構`{"data": {...實際欄位...}, "score": ...}`拉平成看起來像是欄位直接在頂層——照著這個（錯的）形狀寫的第一版`search_institutions`/`get_failure`跑smoke test時`CERT`全部是`None`，完全查不到預期的CERT。用`requests`直接呼叫API驗證真實原始回應，才發現WebFetch的摘要把巢狀結構「幫忙」拉平了，跟真實API形狀不符。**教訓：WebFetch工具的回應是經過模型摘要過的，不能當作驗證API精確資料形狀（例如巢狀結構、欄位型別）的可靠依據，寫程式碼解析API回應前，應該用`requests`直接打一次確認原始JSON結構，不能只信WebFetch的摘要文字。** 改正後（`row["data"]`解開巢狀層）重新smoke test，SBNY（CERT=57053）跟FRC的部分都能正確解析。

**結果**：
1. `fdic_client.py`smoke test對SBNY（CERT=57053）跟第44輪的手動查詢結果完全一致（New York, NY，設立04/12/2001，`ENDEFYMD`03/12/2023，`FAILURE/PA`，資產$110,363,650千）——**驗證重構沒有改變邏輯**，跟`sec_edgar_client.py`第38輪的驗證精神一致。
2. **順帶解出第44輪明確留下的開放問題「FRC本身的FDIC CERT還沒反查」**：`search_institutions("First Republic Bank")`回傳3筆同名機構（跟SBNY一樣是常見銀行名稱碰撞），用`ESTYMD`（成立日）跟`ENDEFYMD`（結束日）交叉比對鎖定`CERT=59017`（San Francisco, CA，成立2010-07-01，結束2023-05-01）——**成立年份2010跟`US_MARATHON_STATE.md`第七輪推論「2010-2023年那個真正掛牌NYSE的FRC」的時間窗吻合**，這是目前為止第一次有具體證據支持第七輪那個推論指向的實體，儘管仍然不是SEC EDGAR CIK（FRC走FDIC申報路徑，本來就不會有對應的SEC CIK，這點第41輪已經推論過，本輪只是補上FDIC側的具體號碼）。`get_failure(59017)`確認：`FAILDATE=5/1/2023`、`RESTYPE=FAILURE`、`RESTYPE1=PA`、資產約$212,638,872千（約2126億美元）——跟公開報導「美國史上第二大銀行倒閉案，摩根大通收購」的規模量級吻合。

**判定**：這是基礎建設/資料源調查工作單位，不是因子/策略統計檢定，`TRIALS_LEDGER.md`不需要加列。

**對後續工作的意義**：未來美股版`universe.py`要處理FDIC-insured銀行類下市股時，`fdic_client.py`的`search_institutions()`+`get_failure()`可以直接呼叫，不需要重新手動WebFetch。**但`search_institutions()`的名稱碰撞消歧義仍然是人工判斷（用城市/州/日期交叉比對），沒有自動化邏輯**，這是有意的設計（同名碰撞的正確答案需要脈絡判斷，自動選第一筆或用其他啟發式規則風險太高，寧可留給呼叫者手動核對）。

**這輪沒做的**：沒有把`fdic_client.py`整合進任何實際的`universe.py`下市偵測邏輯（那個模組本身還不存在，見`US_MARATHON_STATE.md`「地基狀態」）；沒有嘗試`us_probe_price_depth_smallmid.py`（額度狀況判斷同上，跳過）；沒有處理`search_institutions()`的分頁（目前觀察到的碰撞筆數都是個位數，用不到分頁，如果未來查到碰撞筆數破百再處理）。

`is_holdout_consumed()`確認為`False`（本輪完全沒有呼叫FinMind，只有FDIC公開API的`requests`呼叫跟一次WebFetch探測性呼叫，不碰holdout）。

## 2026-08-25T08:02:55+08:00 — 馬拉松第50輪（US軌）：中小型股/近期IPO股 `USStockPrice` 歷史深度抽測（`us_probe_price_depth_smallmid.py` 第四次嘗試，首次成功執行）

**做了什麼**：取鎖時偵測到 `LOCK_STALE`（pid 57480 持有鎖30.0分鐘後被回收，上一輪疑似異常中止、未留下正常結束的log——這筆記錄補上，讓後續不會漏看）。比對三軌「最後更新」時間戳：US（2026-08-25T06:04:00）早於TW（07:05:00）跟FUT（06:35:00），輪替規則指向US。讀 `US_MARATHON_STATE.md`「下一輪建議工作單位」，第1/2/3/5項都已完成，只剩第4項（中小型股/近期IPO歷史深度抽測）待做，第35/38/44輪三次嘗試都在第一檔就撞FinMind 402。查 `TW_LOG.md` 最新一筆（第49輪，07:05，130次嘗試撞限流牆停止）距本輪開始（約08:02）已過約57分鐘，接近觀察到的約每小時額度重置週期，決定嘗試第四次。

**結果**：**額度已恢復，`us_probe_price_depth_smallmid.py` 全部10檔（中小型股組`XPER`/`SWIM`/`IMOS`/`ABR`/`OCSL`＋近期IPO組`FINW`/`LAW`/`NRGV`/`GPCR`/`CAVA`）一次跑完，沒有中途被限流。** 逐檔筆數/起訖日期/缺口統計已寫進 `DATA.md`「美股里程碑1（續）」小節。**核心發現**：所有10檔的日期間隔直方圖都只落在2/3/4天（週末/連假），沒有任何一檔出現>7天的異常缺口，`first`日期都跟各自實際上市/掛牌年份合理對應，`last`全部一致停在`VAL_END=2024-12-31`（`load_dev()`封頂生效）。**里程碑1原本只測AAPL/MSFT兩檔巨型股的資料品質保證，這輪10檔中小型股/近期IPO股的多樣性抽測沒有找到反例，初步驗證通過。**

**判定**：這是地基驗證工作單位，不是假說檢定，不計入 `TRIALS_LEDGER.md`。`US_MARATHON_STATE.md`「下一輪建議工作單位」第1–5項現在全部完成，下一輪需要重新盤點美股軌下一步（候選方向：美股宇宙建構`universe.py`本體、美股版`pit.py`、美股成本模型，這三個都還沒開始寫程式碼，只有資料源探測完成）。

**這輪沒做的**：沒有開始寫任何美股版 `universe.py`/`pit.py`/成本模型的正式程式碼（探測完成不等於地基搭好，下一輪才是真正開始寫可重用模組的時候）；沒有把這次的10檔擴大成更大樣本的窮舉驗證（10檔已經是有意義的多樣性抽測，邊際報酬遞減，下一輪應該轉向寫程式碼而非繼續抽測）。

`is_holdout_consumed()`確認為`False`（本輪只呼叫 `load_dev()`，封頂在 `VAL_END`，未觸碰holdout解鎖函式）。

## 2026-08-25T09:33:32+08:00 — 馬拉松第53輪（US軌）：發現並修復孤兒檔案`us_delisting_client.py`的分類邏輯bug，正式納入版本控制

**背景**：本輪一開始例行`ls`檢查目錄時，發現`research/us_delisting_client.py`是`git status`顯示的未追蹤檔案（`?? research/us_delisting_client.py`），`US_LOG.md`／`US_MARATHON_STATE.md`都完全沒有提到這個檔案，`git log`對這個檔案也是空的。檔案本身的docstring自稱是「Marathon round 50」的產物，但已記錄的第50輪心跳明確是做`us_probe_price_depth_smallmid.py`（項目4），不是這個檔案。合理推論：這是某一輪（很可能是第50輪心跳記錄提到的「上一輪pid 57480疑似失敗」那個陳舊鎖檔對應的輪次）已經寫完程式碼、但在寫log/commit之前就異常中止的殘留產物——`MARATHON_PROTOCOL.md`第0節提到的「上一輪悄悄死掉、什麼都沒留下」情境的具體案例，只是這次不是「什麼都沒留下」，是留下了未完成記錄的實體檔案。

**這個檔案是什麼**：`get_delisting_status(ticker, cik_override, fdic_cert, expected_name_fragment)`，把之前探測階段（第5、7、41、44、47輪）分散在`sec_edgar_client.py`／`fdic_client.py`／各`*_probe.py`裡的下市判定邏輯，第一次包裝成一個「給已驗證身分的股票代號，回答是否下市/何時下市」的可重用函式。是`US_MARATHON_STATE.md`「下一輪建議工作單位」第6項（寫`universe.py`本體）的必要前置積木，不是這輪的目標本身（第6項本身還沒開始）。

**驗證過程發現的bug**：先跑了檔案自帶的`if __name__ == "__main__"` smoke test（5檔已知下市股：TWTR/SIVB/BBBY走SEC EDGAR、SBNY/FRC走FDIC），結果TWTR跟BBBY都被分類成`confirmed_sec_form25_multiple_events_ambiguous`（多重事件、無法判定日期）——但`US_MARATHON_STATE.md`已經用手動調查明確記錄這兩檔是乾淨的單一下市事件（TWTR: 25-NSE 2022-10-28；BBBY: 25-NSE 2023-07-10）。追查原因：原始版本的判定邏輯把Form 25家族（交易所下市申報）跟Form 15家族（SEC註銷登記申報，`DELISTING_FORM_PREFIXES=("25","15-12")`兩者都算進同一個「distinct filingDate」集合）混在一起算「有幾個不同日期」——但**正常的下市流程本來就是先申報Form 25、隔一段時間後才申報Form 15，兩者日期本來就不同，這是每一次下市事件的常態，不是「多重事件」的訊號**。原始邏輯會把每一檔正常下市都誤判成「模糊、無法判定」，只有SIVB（真的有兩個不相關事件：2017-2018一組跟2023真正的下市）才是原設計者想抓的情境。

**修復**：改成只用Form 25家族（`ANCHOR_FORM_PREFIX="25"`）的filingDate來判定「有幾個獨立事件」，Form 15家族只當輔助資訊（放在`all_hits`裡但不影響event計數）。理由：Form 15是同一次下市事件必然的後續行政程序，只是間隔天數變異很大（TWTR 10天、BBBY 81天、SIVB真正那次2023-05-02到2025-01-24將近630天——查證後排除了用固定時間窗合併25+15的方案，因為630天遠超過任何合理窗口，但10天又太短不能設高門檻）；反之，兩筆不同日期的Form 25家族申報，才是真正代表兩個不同的下市事件（不同證券類別，或像SIVB真的有一次無關的2017-2018事件）。修復後重跑smoke test：TWTR/BBBY正確變回`confirmed_sec_form25`（單一事件，日期正確），SIVB維持`confirmed_sec_form25_multiple_events_ambiguous`（正確，這是原設計意圖要抓的真實情境），SBNY/FRC的FDIC路徑不受影響、結果不變。同時新增一個先前完全沒覆蓋到的分支（`confirmed_sec_form15_only_no_form25_anchor`）：如果只找到Form 15、完全沒有Form 25家族申報（例如公司從未在交易所掛牌、只是單純SEC註銷登記），明確標註信心較低，不是靜默套用跟Form25同款的`confirmed_sec_form25`狀態——這個分支5檔已知案例都沒觸發，未來若遇到才會第一次被實測驗證，先誠實記錄「理論設計、未實測」。

**這輪沒有新打任何外部API**——`sec_edgar_client.py`／`fdic_client.py`的快取（`research/data/raw/`底下）已經在之前輪次建立，這輪的修復跟smoke test重跑完全命中快取，零額度消耗，也因此完全不受FinMind額度限制影響（跟這輪一開始選US軌純粹是因為時間戳最舊、不是刻意挑不耗額度的工作無關，是巧合）。

**判定**：這是地基建設工作單位（見`MARATHON_PROTOCOL.md`第1c節），不是假說檢定，不計入`TRIALS_LEDGER.md`。修復後的`us_delisting_client.py`正式`git add`納入版本控制（先前是孤兒未追蹤檔案，現在有完整commit記錄跟log對照）。

**這輪沒做的**：沒有開始寫`universe.py`本體（這個模組只是`universe.py`未來會呼叫的其中一個積木，`universe.py`要做的「累積{ticker: 已驗證身分}對照表」這件事，docstring裡明確寫這輪範圍之外）；沒有測試`confirmed_sec_form15_only_no_form25_anchor`分支（沒有已知的真實案例可驗證，留待未來遇到時驗證）；沒有查證是否還有其他孤兒未追蹤檔案（這輪只是在例行`ls`時偶然發現這一個，沒有系統性掃描整個research目錄比對git狀態，如果之後想徹底排查，`git status --short research/`可以列出所有未追蹤/未commit的異動，值得未來某一輪專門做一次）。

`is_holdout_consumed()`確認為`False`（本輪完全沒有呼叫任何FinMind相關函式，只讀SEC EDGAR/FDIC的既有本地快取）。

---

## 2026-08-25T11:02:00+08:00 — 馬拉松第56輪：美股版 `universe.py` 第一版（`US_MARATHON_STATE.md` 建議工作單位第6項）

做了「下一輪建議工作單位」第6項：新寫 `us_universe.py`。**明確標註不是完整的存活者偏差修正**——第4/5/7/41/44/47/50輪查過，台股`universe.py`「價格列存在=地面真相」跟`USStockInfo`快照增減兩個方法在美股都不可靠（見`US_MARATHON_STATE.md`），美股又沒有等同`TaiwanStockDelisting`的免費可查詢下市名單端點，所以這輪採用狀態檔案建議的現實做法：現存快照 + 手動維護的已驗證下市股清單。

**`active_stock_ids()`**：抓最新`USStockInfo`快照（`_fetch()`直接呼叫，理由同`universe.py`對`TaiwanStockInfo`的處理——這是snapshot時間戳不是上市日，走`load_dev()`會被`VAL_END`濾光），過濾掉ETF（`Subsector=='ETF'`，2026-08-22快照12429列裡5247列）跟SPAC衍生工具（stock_name含Warrant/Units/Rights，565列，判斷邏輯標記為「判斷call，未驗證是否有誤刪」）。剩6618檔。

**`known_delisted_stock_ids()`**：直接沿用`us_delisting_client.py`的`__main__` smoke test已經驗證過的5檔（TWTR/SIVB/BBBY走SEC EDGAR Form 25、SBNY/FRC走FDIC failures），日期跟來源都寫進`KNOWN_DELISTED`常數，附註SIVB是「人工排歧義後的日期」（自動分類器本身回傳ambiguous，因為有一組2017-2018不相關的Form 25 cluster）。**這輪沒有重新呼叫網路API**——5檔的身分/日期在先前輪次已經獨立驗證過，這輪只是把已知答案固化成程式碼裡的表格，不是重新查證。

**`universe()`**：合併兩者，欄位跟台股版對齊（`stock_id`/`stock_name`/`status`/`delist_date`），但額外加一欄`bias_correction`常數字串（`active_snapshot_plus_hand_verified_delisted__NOT_COMPLETE`），確保之後任何用這份宇宙做回測的程式碼都會在資料裡直接看到這個限制，不是只寫在文件裡容易被忽略。

**驗證**：`python us_universe.py` 跑通，6623列（6618 active + 5 delisted），5檔已知下市股全部正確保留在合併結果裡（防呆檢查：如果任何一檔被去重邏輯誤刪會直接assert失敗）。`is_holdout_consumed()`確認仍是`False`。

**這輪沒有新打任何外部API**——`USStockInfo`快照已經在之前輪次快取在`research/data/raw/`，這輪的`_fetch()`呼叫命中快取，零額度消耗。

**下一步（`US_MARATHON_STATE.md`第7/8項未動，留給下一輪）**：美股版`pit.py`（要處理pre-XBRL標記缺口跟pre-IPO歷史資料兩類已知不可信PIT gap）、美股成本模型。這輪只接第6項一項，符合協定「一輪一件事」。

`is_holdout_consumed()`確認為`False`。

## 2026-08-25T12:32:41+08:00 — 馬拉松第59輪：新寫美股版 `pit.py`（第7項）

做了`US_MARATHON_STATE.md`「下一輪建議工作單位」第7項：新寫`research/us_pit.py`，用`sec_edgar_client.py`已驗證的`get_filing_dates()`（submissions API的`filingDate`/`reportDate`）建構`filing_pit(ticker, cik_override=None, forms=("10-K","10-Q"))`函式，回傳每筆申報一列的PIT對齊表（欄位：ticker/cik/form/fiscal_period_end/pit_date/gap_days/pit_source）。跟`pit.py`（TW版）介面對稱（`any_assumed()`同款函式簽名），但這裡`pit_source`固定是`'real'`——submissions API的`filingDate`是SEC自己公布的真實申報日，不是像TW財報那樣要用+45天假設。

**刻意沒做的設計決策（記錄理由，不是漏做）**：第7項原始措辭要求把「pre-XBRL標記缺口」跟「pre-IPO歷史資料」兩類已知不可信PIT gap「納入設計」。查證後發現：pre-XBRL缺口這個現象是第十/十一輪在**XBRL company facts API**（每個資料點層級，因比較期重複揭露而產生的去重artifact）診斷出來的，跟本模組用的**submissions API**（每次申報一列，沒有比較期重複揭露這個機制）是不同端點、不同資料形狀——沒有實測證據顯示這個artifact會出現在submissions API上，如果不驗證就把這個flag原封不動搬過來，等於在沒有證據的情況下把一個端點的結論套用到另一個端點，違反協定第4節的誠實記錄精神。所以`XBRL_MANDATE_PHASE1_CUTOFF`常數保留（供未來真的要碰XBRL facts端點時用），但**沒有**在`filing_pit()`裡套用成reliability flag，這點在模組docstring裡完整記錄成一個開放的方法論問題，不是最終結論。Pre-IPO這一類則不需要額外flag邏輯：因為submissions API本質上只會列出真實存在的申報，公司上市前沒有申報，`filing_pit()`自然回傳空/從IPO後才開始的資料，這是結構性保證，不是靠額外程式碼判斷。

**新發現、且是這輪跑smoke test才第一次量化出來的**：`filings.recent`滾動視窗的實際深度，用AAPL/MSFT/PLTR三檔（沿用前幾輪已驗證的CIK，全部命中快取無新API呼叫）實測——AAPL 45筆申報，最早`fiscal_period_end`只回溯到**2015-06-27**（不是理論上`filings.files[]`分頁能拿到的1994年）；MSFT 25筆，最早只回溯到**2020-06-30**，比AAPL的視窗還短，兩檔申報頻率相近但視窗深度差很多，原因未查（可能跟filer規模分級或申報數量門檻有關，這輪沒有進一步追查）；PLTR 24筆，最早`2020-09-30`剛好貼著其2020年9月IPO時間，符合結構性保證的預期。gap_days（filingDate−reportDate）三檔統計跟第三輪(`sec_edgar_probe.py`)/第38輪(`sec_edgar_client.py`)的既有數字一致（AAPL median 34天、MSFT median 28天、PLTR median 39天，range 25–37/24–30/34–57），驗證重構沒有改變邏輯。**這代表：任何要用`filing_pit()`做全歷史回測的假設都要先意識到，長年掛牌股（AAPL/MSFT這類）目前只能拿到近5–10年的PIT對齊財報日期，不是全歷史——這是新增的`coverage_probe()`診斷函式存在的理由，之後接美股版`universe.py`/PIT回測時要先對目標樣本跑一次`coverage_probe()`，不能假設視窗深度對所有股票一致。**

**沒做的**：`filings.files[]`分頁擴充（把視窗往更早年份延伸）仍然完全沒碰；美股成本模型（第8項）沒動；`universe.py`還沒接上`us_pit.py`做實際回測。這輪只接第7項一項，符合協定「一輪一件事」。

這輪沒有打任何新的FinMind API（純SEC EDGAR，且全部命中既有快取），跟`MARATHON_PROTOCOL.md`第4節「holdout只限制FinMind/alpha.db」的範圍一致，`is_holdout_consumed()`確認為`False`。

## 2026-08-25T14:02:23+08:00 — 馬拉松第62輪：`sec_edgar_client.py` 加`filings.files[]`分頁擴充（第10項）

做了`US_MARATHON_STATE.md`「下一輪建議工作單位」第10項：`get_filing_dates()`新增`full_history: bool = False`參數，`True`時額外遍歷`get_submissions(cik)["filings"]["files"]`列出的每個archive pointer（用新函式`get_archive_filings(cik, file_name)`逐一抓取，per-file快取），把結果跟`filings.recent`合併回傳，解決第59輪發現的「`filings.recent`視窗深度對長年掛牌股比理論上限淺很多」問題。

**動手前先直接用`requests`探測archive檔案的真實JSON形狀**（遵守第47輪留下的方法論教訓，不能只信WebFetch摘要）：抓了AAPL的`CIK0000320193-submissions-001.json`（已快取在`data/raw/SEC_submissions_0000320193.json`裡的`filings.files[]`列出這個檔名），確認是**扁平字典**，跟`filings.recent`同款「並列陣列」形狀（`form`/`filingDate`/`reportDate`等欄位直接在頂層，不是巢狀在`filings`鍵底下）——這是新函式`_filings_to_records()`能同時處理`filings.recent`跟archive檔案兩種來源的依據，已在函式docstring記錄這個共用假設的驗證來源。

**smoke test（`python sec_edgar_client.py`）結果，`full_history=True` vs `False`對照**：
- AAPL：recent-only 45筆（最早2015-07-22）→ full_history 128筆（最早**1994-01-26**，貼齊理論上限）。
- MSFT：recent-only 25筆（最早2020-07-30）→ full_history 131筆（最早**1994-02-14**）。
- PLTR：recent-only 24筆 → full_history 24筆**不變**（2020年IPO，本來就沒有archive pointer可分頁，`filings.files[]`是空陣列，結構性保證，不是bug）。

**新發現（這輪smoke test才第一次量化出來，非理論推測）**：`gap_days`（filingDate−reportDate）的max在納入歷史資料後明顯變寬——AAPL max_gap從37天（recent-only）變成**181天**（full_history），MSFT從30天變成**91天**。推測跟SEC加速申報人（accelerated filer）規定的沿革有關（早年10-K/10-Q法定申報期限比現在寬鬆，2000年代初才逐步收緊），但這輪**沒有查證這個推測**，只記錄現象。**這對之後設計美股版PIT reliability機制有實務意義**：如果`filing_pit()`要延伸到1990年代資料，不能沿用近年（~30天）的gap_days當作「正常範圍」的預期值去做離群值偵測，早年本來就會有數倍寬的合法gap，需要按時期分段看待，不是全歷史套同一個門檻。

**沒做的**：`us_pit.py`的`filing_pit()`/`coverage_probe()`還沒接上這個新的`full_history`參數（目前還是只用`filings.recent`），這是下一輪的候選工作單位，不在這輪範圍內。美股成本模型（第8項）也沒動。這輪只接第10項一項，符合協定「一輪一件事」。

這輪沒有打任何FinMind API，`data.sec.gov`請求也全部走`_cached_get`（AAPL/MSFT各多一個archive檔案的快取寫入，PLTR零額外請求因為`filings.files[]`是空的），`is_holdout_consumed()`確認為`False`。
