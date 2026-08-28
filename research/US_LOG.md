# US_LOG.md — 美股軌 append-only 執行記錄（挖礦馬拉松專用）

跟主線 `REPORT.md` 同樣的精神（append-only，最新在最下面）。美股軌是全新的，這份檔案從第一輪馬拉松開始就是美股軌唯一的執行記錄。

**規則：** 每個馬拉松輪次結束前 append 一條，包含地基搭建進度（美股軌前期主要是這個）跟之後的因子/策略測試結果，不管有沒有進展都要記錄。

---

## 2026-08-28T03:31+08:00 — 馬拉松第159輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：US 02:01（第156輪，最舊）／FUT 02:31（第157輪）／TW 03:18（第158輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。`git log`確認自第156輪（`aad3c9a`）以來新增的commit（`11961bf`/`fbb071b`新增pull-to-refresh+時鐘重整按鈕根治+夜間自主循環啟動、`f27450b`第152輪TW T86回補記錄、`efd7b6f`動能榜因子修正、`39888ae`自動報價更新、`d0999bb`第154輪FUT跳過記錄、`1982542`前瞻選股台帳picks_ledger.json、`168a1e1`merge、`f10b244`第155輪TW T86回補記錄、`a13ad74`第157輪FUT跳過記錄、`b902678`第158輪TW T86回補記錄、`8f68548`B24 PIT回測骨架、`b85f025`夜間循環第4輪UX走查）全部屬於互動session的App開發/夜間自主循環或TW軌回補/其他軌跳過記錄，跟解除暫停規則或`PORTFOLIO_STRATEGY_SPEC.md`都無關。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪開始時確認工作目錄乾淨。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列。

## 2026-08-28T00:31+08:00 — 馬拉松第153輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：US 20:32（第150輪，最舊）／FUT 22:01（第151輪）／TW 00:06 Aug28（第152輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，沒有任何新動作，暫停規則整體仍完全生效中。`git log`確認自`fa369b9`以來新增的commit全部屬於互動session的App開發/BACKLOG登錄/帽子規則整理（`f27450b`/`542111c`/`b2bea6a`/`1b3123a`/`0a6402d`/`6494821`/`6ef1d5f`/`aa4a6c5`/`fbb071b`/`11961bf`），跟解除暫停規則或`PORTFOLIO_STRATEGY_SPEC.md`都無關。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135/138/141/144/147/150判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪開始時確認工作目錄乾淨。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列。

## 2026-08-27T18:31+08:00 — 馬拉松第147輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 18:22（第146輪，最新）／FUT 17:01（第145輪）／US 16:32（第144輪，最舊）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135/138/141/144判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪開始時確認工作目錄乾淨。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列。

## 2026-08-27T16:32+08:00 — 馬拉松第144輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 16:07（第143輪，最新）／FUT 15:31（第142輪）／US 15:01（第141輪，最舊）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，沒有任何新動作，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135/138/141判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪確認工作目錄乾淨（上一輪141記錄的互動session財報檔未commit修改已不存在，應已被收尾）。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列。

## 2026-08-27T15:01+08:00 — 馬拉松第141輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 14:52（第140輪，最新）／FUT 14:02（第139輪）／US 13:31（第138輪，最舊）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認該檔案自建立（`fa369b9`）以來沒有任何新commit動過，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，TAIEX/TWSE相關，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135/138判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則附記+心跳。`git status`本輪確認工作目錄有一份不屬於馬拉松的未commit修改（`.github/scripts/update_fundamentals_daily.py`/`data/fundamentals.json`/`data/stock_detail.json`/`research/build_fundamentals_json.py`四個已修改檔案+`research/build_stock_financials_history.py`一個新檔，明顯是互動session的財報資料改動），本輪刻意不動、不納入commit。`is_holdout_consumed()`確認`False`。

## 2026-08-27T13:31+08:00 — 馬拉松第138輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 13:04（第137輪，最新）／FUT 12:31（第136輪）／US 12:02（第135輪，最舊）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log`確認自第135輪以來新增的commit（`9ce0ad4`第136輪FUT跳過、`369da2d`第137輪TW組合策略基準補算、`e08cdb2`/`5458142`一般互動session選股頁coverage修正）皆與解除暫停規則無關，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，TAIEX/TWSE相關，跟US軌無關），round108/111遺留的1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則附記+心跳。`git status`本輪確認工作目錄乾淨，上一輪記錄的`research/generate_scores_v2.py`未commit修改已不存在。`is_holdout_consumed()`確認`False`。

## 2026-08-27T12:02+08:00 — 馬拉松第135輪：跳過（暫停規則生效中，無組合策略相關工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 11:37/11:38（第134輪，最新）／US 10:32（第132輪，最舊）／FUT 11:01/11:02（第133輪）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log`確認自第134輪（`342ff81`，TW軌T86回補）以來無新使用者互動session介入，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，TAIEX/TWSE相關，跟US軌無關），round108/111遺留的(a)(b)(c)三項1c地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則附記+心跳。工作目錄另有一份不屬於馬拉松的未commit修改（`research/generate_scores_v2.py`，互動session新增`import json`），本輪刻意不動、不納入commit。`is_holdout_consumed()`確認`False`。

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

## 2026-08-26T01:03:39+08:00 — 馬拉松第79輪：新寫 `us_factors.py`（第一版因子庫，僅一個純價格因子）

依使用者2026-08-26裁示「美股軌可以開始建因子管線」（見 `US_MARATHON_STATE.md`），這輪補齊地基最後一塊缺口：`universe.py`／`pit.py`／`validation/us_costs.py` 都已有第一版，只差 `factors.py` 完全不存在，`US_MARATHON_STATE.md`「下一步」明確點名這是候選工作單位之一。**這輪工作單位屬於協定第1c節（地基建設），不是1a（假說便宜關卡）**——第一個因子刻意選純價格、不需要PIT對齊，目的是先確認因子計算管線本身能端到端跑通，不要一次連因子邏輯跟PIT正確性兩個未知數一起賭。

新增 `us_factors.py`：`us_price_series(stock_id, start_date)` 包一層 `load_dev("USStockPrice", ...)`，欄位改名成專案慣用的小寫（`adj_close`/`close`/`high`/`low`/`open`/`volume`），跟`adjust.py`輸出介面一致；`prepare_us_factors(price_df)` 目前只加一個因子欄位：`f_us_low_vol`（60日日報酬標準差取負號），**刻意跟TW版`f_low_vol`用完全相同的定義跟窗口（`LOW_VOL_WINDOW=60`）**，理由寫在docstring——之後如果要比較「低波動異常在兩個市場是否表現一致」，不能讓定義差異混淆結論。

**取鎖後第一次嘗試就撞FinMind 402（額度用盡，顯然是TW軌前幾輪回補剛用光）**：改用已有的快取檔（`data/raw/USStockPrice__AAPL__1990-01-01__2024-12-31.parquet`／`MSFT`同款，第一輪里程碑1探測留下的），把smoke test的`start_date`從原本規劃的`2015-01-01`改成`1990-01-01`（跟快取key完全對齊），零新增API呼叫完成驗證，符合協定第4節「額度用盡優雅結束/不狂重試」的精神，同時沒有浪費這一輪。

Smoke test（`__main__`區塊）：AAPL/MSFT各8817列價格，`f_us_low_vol`都是60列NaN warm-up（`pct_change()`1列NaN+`rolling(min_periods=60)`還差59列湊滿60，數學上剛好60列，不是59列——第一版寫成`LOW_VOL_WINDOW - 1`assert失敗才發現這個off-by-one，已修正assert本身，不是改因子邏輯，跟TW版`factors.py`用的完全同一套`pct_change→rolling(min_periods=W)`寫法，這個warm-up長度是預期行為不是bug），有效值範圍AAPL約[-0.0825, -0.0066]、MSFT約[-0.0518, -0.0057]，數量級合理（年化約略等於日std×√252，AAPL約10%~131%波動帶，MSFT約9%~82%，涵蓋了COVID等真實高波動期間，沒有出現爆炸/全NaN這類明顯bug徵兆）。`python us_factors.py`跑通並印出`OK`。

**沒做的（誠實揭露，下一輪候選）**：只有1個因子，不是完整因子庫；沒有跑`factor_ic.py`風格的便宜關卡IC測試（那是下一輪的1a工作，這輪只確認欄位算得出來）；沒有處理美股宇宙的PIT基本面因子（那些需要`us_pit.py`已知的`era_reliability()`限制、近期IPO股不可信的問題，比純價格因子複雜很多，刻意留到之後）。`is_holdout_consumed()`確認`False`（全程只用`load_dev()`封頂資料+已快取檔案，零新API呼叫）。

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

## 2026-08-25T15:34:05+08:00 — 馬拉松第65輪：`us_pit.py` 接上 `full_history`＋分期PIT reliability標記（第11項）

做了`US_MARATHON_STATE.md`「下一輪建議工作單位」第11項的兩個子任務：(a) `filing_pit()`/`coverage_probe()`新增`full_history: bool = False`參數，直接透傳給`sec_edgar_client.get_filing_dates(full_history=...)`；(b) 新增`era_reliability()`函式跟`_ERA_SEGMENTS`常數表，把第62輪「歷史gap上限比近年寬」的現象變成一個按申報期間分段的標記機制，不再對全歷史套同一個門檻。

**動手前先查證SEC真實規則，不是憑印象猜天數**（WebSearch，見來源：SEC.gov《Acceleration of Periodic Report Filing Dates》2002年規則、Ropes & Gray/Willkie法律事務所摘要）：2002-12-15以前，**全部**申報人（不分規模）10-K/10-Q法定期限是90天/45天；SEC Release 33-8128對「加速申報人」（accelerated filer）分三年逐步收緊：財年結束日在2002-12-15以後維持90/45天、2003-12-15以後10-K降到75天、2004-12-15以後10-K降到60天+10-Q降到40天、2005-12-15以後（最終版）10-Q再降到35天。`_ERA_SEGMENTS`就是照這個真實時間表寫的（5段：pre-2002/2002/2003/2004/2005起），不是自己拍腦袋定的門檻。

**`era_reliability()`明確記錄一個刻意不解決的已知限制**：這個函式不知道某公司在某個財年**是不是**加速申報人（需要逐年公眾流通市值歷史，這個模組沒有這份資料），所以2005-12-15以後**一律**套用加速申報人的最嚴門檻（60/35天），對真正非加速申報人（仍適用90/45天）會誤判。這輪smoke test（`python us_pit.py`，`full_history=True`，AAPL/MSFT/PLTR，全部命中第62輪留下的快取，沒有打新的SEC請求）**用實測資料證實了這個限制是真的、不是理論擔心**：

- **AAPL**（128筆，1994–2026）：5/128（4%）`exceeds_era_deadline`，全部集中在2005–2007年（10-K FY2005 68天、10-Q FY2006Q3 181天、10-K FY2006 90天、兩筆FY2007 10-Q 39–40天）。**這個時間點對得上一個真實的公開歷史事件**：Apple 2006年爆發股票選擇權回溯授予（options backdating）調查，導致當年多份定期報告延後申報——**這輪沒有重新查證這件事本身（只是憑既有背景知識辨認出時間點吻合），標記為「合理解釋、未在本輪獨立確認」，不是「已證實原因」**，但如果屬實，這代表`era_reliability`抓到的是真實的延遲申報事件，不是資料雜訊，強化了這個標記機制的可信度。
- **MSFT**（131筆，1994–2026）：只有2/131（1.5%）超標，1997年兩筆（91天/48天），數字剛好卡在90/45天門檻邊緣，最可能只是「剛好壓線申報」，不是異常事件。
- **PLTR**（24筆，2020–2026）：**14/24（58%）超標，遠高於AAPL/MSFT**——median gap=39天，卡在35天（加速申報人10-Q最終門檻）跟45天（非加速申報人）之間。**這正是上面記錄的「已知限制」的具體現場**：PLTR 2020年IPO後前幾年很可能有一段時間還不符合「加速申報人」定義（SEC對加速申報人的認定需要「已完成至少一次年報申報週期＋前一會計季末公眾流通市值達門檻」，剛IPO公司通常前一到兩年還不算加速申報人），這輪函式對PLTR全部套用最嚴的35天門檻，很可能大量誤判。**結論：`era_reliability`目前只在AAPL/MSFT這種長年掛牌的大型加速申報人身上可信，PLTR這類「近期IPO/申報人身分可能還在變動」的股票，`exceeds_era_deadline`旗標目前應視為「需要人工複核」，不能當作「確認有問題」直接使用或過濾樣本。**

**沒做的**：沒有去逐年查證PLTR/其他個股實際的加速申報人身分變動時間點（那需要另外查SEC的filer category申報，這輪範圍外）；沒有把`era_reliability`接進任何下游回測邏輯（這個模組目前還是純資料層，`universe.py`/`factors.py`都還沒有美股對應版本）；美股成本模型（第8項）沒動；擴充`KNOWN_DELISTED`（第9項）沒動。

這輪沒有打任何FinMind API；`data.sec.gov`零新請求（全部命中第62輪的快取，`python us_pit.py`跑完只讀本機快取檔）；`is_holdout_consumed()`確認為`False`。

## 2026-08-25T17:02:50+08:00 — 馬拉松第68輪：美股成本模型第一版（`US_MARATHON_STATE.md` 第8項）

做了「下一輪建議工作單位」第8項：新寫 `validation/us_costs.py`，仿 `validation/costs.py`（TW model）的結構跟誠實揭露精神，補上美股版的 `round_trip_cost_pct()`/`short_round_trip_cost_pct()`。

跟TW model的關鍵差異（不是換個數字，是不同的成本結構）：
- **無證交稅**：TW的0.3%/0.15% STT在美股沒有對應項目。
- **無漲跌停鎖死機制**：TW的`limit_status()`在美股沒有對應功能，US是LULD/市場級熔斷機制（不同運作方式），這輪刻意不做對應函式。
- **零售手續費預設為$0**（Schwab標準/IBKR Lite，WebSearch 2026-08-25驗證，來源brokerchooser.com/stockbrokers.com對兩家官網定價頁的轉述，非一手PDF核對），但保留`IBKR_PRO_COMMISSION_PER_SHARE`當敏感度測試備用常數（IBKR Pro是分層計價，這個常數只是粗略代表值，不是精確重現分層規則）。
- **兩個強制性監管費**（僅賣出邊）：SEC Section 31 fee（$20.60/百萬美元成交額，2026-04-04生效，來源FINRA Information Notice 20260317／Federal Register 2026-04233）、FINRA TAF（$0.000195/股，2026-01-01生效，min $0.01/max $9.79每筆，來源finra.org/rules-guidance/guidance/trading-activity-fee）。**兩者都是WebSearch查證，非直接呼叫官方API/PDF逐字核對**。

**誠實揭露的關鍵限制（寫在模組docstring裡，這裡摘要）**：這兩個監管費率是主管機關定期（SEC約每年）依市場量體調整的浮動費率，不是像TW STT那樣的穩定法定稅率——這份模組目前只驗證了「當下（2026-08-25）這一刻」的費率快照，**沒有查證歷史費率的變動範圍**，如果拿今天的費率套用到跨年（例如2015–2026）的回測，等於隱含假設「監管費率歷年不變」，這個假設本身沒被驗證過，跟TW軌/US軌都已經踩過的「數字用最新快照套全歷史」同一類地雷（呼應`us_pit.py`的`era_reliability()`分期教訓），這裡故意用文字揭露而不是假裝精確。滑價（`DEFAULT_SLIPPAGE_BPS=5.0`）跟借券費（`BORROW_FEE_ANNUAL_PCT=2.0`）維持跟TW model同款「未校準佔位值」狀態，同樣的誠實揭露。

**smoke test**（`python validation/us_costs.py`）：100股@$50範例，手算SEC fee($0.1030)+TAF($0.0195)+滑價跟函式輸出完全吻合（誤差<1e-12），30天空頭成本嚴格大於即時買賣來回成本（借券費驗證有生效）。輸出：`round_trip_cost_pct=0.102450%`、`short_round_trip_cost_pct(30天)=0.266834%`。

**沒做的**：沒有查證兩個監管費率的多年歷史變動範圍（只驗證了當下這一刻）；沒有查證IBKR Pro分層計價的精確min/max clamp規則（只用一個代表性數字）；沒有把這個模組接進任何回測腳本（那還需要美股版`factors.py`/`long_short_backtest.py`，目前都不存在）；`limit_status()`等價功能（LULD/熔斷）刻意不做，留白不是遺漏。`US_MARATHON_STATE.md`「下一輪建議工作單位」剩第9、12項未做。

`is_holdout_consumed()` 確認為 `False`（本輪全程沒碰任何FinMind/SEC資料抓取，只有WebSearch文件查證跟寫純邏輯程式碼）。

## 2026-08-25T18:33:29+08:00 — 馬拉松第70輪：filer category 欄位探測（第12項）

接「下一輪建議工作單位」第12項：`era_reliability()`（第65輪）對近期IPO股（PLTR）不可信，因為不知道個股逐年的加速申報人身分。新寫 `sec_edgar_filer_category_probe.py`，對已驗證的三個CIK（AAPL/MSFT/PLTR）測了兩個候選欄位：

1. `submissions/CIK{cik}.json` 頂層 `category` 欄位：**存在，但三檔今天全部顯示`"Large accelerated filer"`**——這是單一「今天」快照，沒有日期/申報context，對PLTR早年分級完全沒有資訊量。跟`USStockInfo`快照陷阱是同一類問題的第三次出現。
2. XBRL company facts `facts.dei.EntityPublicFloat`：**確實有逐年資料**（AAPL 19筆2009–2025、MSFT 17筆2009–2025、PLTR 6筆2020–2025，含`end`/`filed`/`fy`/`val`）。這是SEC規則據以判定分級的原始輸入（公眾流通市值門檻制），不是分級標籤本身——理論上可以搭配歷史門檻時間表反推逐年分級，但**這輪只確認資料存在，門檻歷史表沒查證，反推邏輯沒寫**。

**判定：問題從「完全開放」推進到「有具體候選路徑，但還要兩個子步驟才能真正解決」**（WebSearch查證門檻歷史時間表 + 寫反推邏輯 + 拿PLTR已知誤判樣本重測）。這不是因子/策略統計檢定，不計入`TRIALS_LEDGER.md`。完整見 `DATA.md`「美股 PIT 資料源調查（三續）」小節。

**沒做的**：沒查歷史門檻時間表；沒寫反推邏輯；沒重測PLTR。這三步留給下一輪視優先序決定要不要接，也可以直接跳過改做第9項（系統化擴充`KNOWN_DELISTED`名單）。

`is_holdout_consumed()` 確認為 `False`（本輪只呼叫`sec_edgar_client.py`既有函式+一次直接`requests`打XBRL company facts端點，皆走公開SEC API，不碰FinMind/alpha.db）。

## 2026-08-25T20:10:00+08:00 — 馬拉松第74輪：第12項子步驟(a)——SEC accelerated/large accelerated filer 門檻歷史時間表 WebSearch 查證

接第70輪留下的三個子步驟，這輪只做(a)：純文件調查（WebSearch，3次查詢），沒有寫程式碼、沒有打任何 API。查到門檻時間表五個節點，都附官方文件連結：2002–2005分期（entry $75M不變，只有申報期限分四階段緊縮）、2005-12-21/12-27生效的Release 33-8644（新增LAF分類，entry $700M，AF重定義為$75M–<$700M，AF→NAF exit門檻$50M）、2018-06-28 SRC定義修正（細節未深挖）、2020-03-12/約04-27生效的Release 34-88365（exit門檻全面調高$50M→$60M、$500M→$560M，**新增營收測試**，且新增「SRC若營收<$100M且流通市值<$700M可直接列NAF」路徑）、2026-05-19聲明的Release 33-11419（**提案中，尚未生效**，擬把LAF entry調到$2B）。

**關鍵發現**：反推邏輯的主要複雜度不在「門檻數字隨時間變」（entry門檻2005年後其實很穩定），而在2020年新增的營收測試——2020年之後要正確反推分級，光有`EntityPublicFloat`不夠，還要同時查同年度營收。PLTR（2020-09 IPO）申報生涯完全落在2020新規之後，這代表它14/24誤判可能有相當比例是「反推邏輯沒接營收測試」造成的，不只是「缺乏歷史分級資料」——這改變了子步驟(c)重測時的預期：如果(b)只做流通市值反推不接營收測試，PLTR樣本可能還是測不準。

**留白（誠實記錄，沒有查證完畢）**：2018年SRC修正只確認日期，內容細節沒深挖；2005年LAF exit門檻（$500M）是從2020年文件的「調整前/調整後」對比句反推出來的，不是直接讀到33-8644原文寫的數字，如果(b)真的要用到這個數字，建議先去readSEC 33-8644 final rule PDF原文確認。完整時間表、來源連結、對(b)(c)的具體影響見`DATA.md`「美股 PIT 資料源調查（四續）」小節。

**判定**：子步驟(a)完成，(b)(c)留給下一輪，也可以視優先序改做第9項（系統化擴充`KNOWN_DELISTED`）。這不是因子/策略統計檢定，不計入`TRIALS_LEDGER.md`，跟第70輪先例一致。

`is_holdout_consumed()` 確認為 `False`（本輪完全沒有呼叫任何資料抓取函式，純WebSearch文件調查）。

## 2026-08-25T22:31:58+08:00 — 馬拉松第77輪：第12項子步驟(b)(c)——filer category反推邏輯執行與PLTR重測，**結論：此路不通**（接續異常中止留下的腳本）

**交接背景**：取鎖時偵測到`LOCK_STALE`（pid 131600持有鎖60.1分鐘），回收後發現repo裡有一個未提交的檔案`research/sec_edgar_filer_category_infer.py`——內容是完整的第12項子步驟(b)實作（依第74輪查證的門檻表寫Era A/B/C分類邏輯＋2020年營收測試，含完整docstring跟四項LIMITATIONS），但從未被執行過、沒有任何log記錄。推斷這是某次啟動後異常中止（可能是`STATUS_CONTROL_C_EXIT`或類似崩潰，沒有留下痕跡）的執行個體留下的成果。本輪判斷：腳本本身完整可用，直接接手跑子步驟(c)，不重寫。

**做的事**：`python sec_edgar_filer_category_infer.py`（smoke test，AAPL/MSFT/PLTR三檔）。

**結果**：
- AAPL（19財年）/MSFT（17財年）全部分類`LAF`，符合預期。
- AAPL FY2009的`EntityPublicFloat`資料點重複出現三次（數值相同）——推翻了腳本docstring裡「不需要去重」的假設（該假設先前未經實測，這輪是第一次驗證，結果不成立）。不影響分類結論，但未來若要用逐筆計數會需要先去重。
- **PLTR六個財年（2020–2025）全部分類`LAF`，沒有一年落入AF/NAF**——float從IPO當年就是$13.3B，遠超$700M門檻，2020年營收測試的`float_val < _LAF_FLOAT`條件從未成立，測試等於沒被觸發。

**關鍵判定：這推翻了第74輪的預期**。第74輪推測PLTR 14/24誤判可能源自「反推邏輯沒接營收測試」，暗示PLTR早期float應落在受營收測試影響的邊界。但本輪反推分類器（已含營收測試）判定PLTR全部財年是LAF，跟`era_reliability()`原本套用的全市場LAF假設完全一致，沒有任何分歧。**「filer category誤判」這個假說被證偽——兩種方法算出的類別相同，代表第65輪發現的PLTR 14/24 gap超標不可能是用錯申報期限造成的，真正原因未知（COVID寬限令/真實延遲/gap計算定義問題等候選，本輪未查證）。**

**判定**：第12項到此視為有明確負向結論，不是懸而未決。依`MARATHON_STATE.md`第74輪已預告的退路，建議`era_reliability()`維持現狀（只信任已驗證過的長年掛牌大型股，其他標記`unverified`），不建議再投入輪次救這條路。這不是因子/策略統計檢定，不計入`TRIALS_LEDGER.md`，跟第70/74輪先例一致。完整見`DATA.md`「美股 PIT 資料源調查（五續）」小節。

`is_holdout_consumed()` 確認為 `False`（本輪只呼叫`sec_edgar_client.py`既有函式+一次直接`requests`打XBRL company facts端點，皆走公開SEC API，不碰FinMind/alpha.db）。

## 2026-08-26T02:35:47+08:00 — 馬拉松第81輪：第一次真正跑`f_us_low_vol`的1a便宜關卡IC測試——**FinMind IP被暫時封鎖，測試無法執行，這是資料可用性發現不是因子判定**

**取鎖與選軌背景**：取鎖乾淨（非陳舊鎖檔）。選軌時發現TW軌`git status`顯示一批使用者互動session的未commit變更（混合資料源架構，`TW_MARATHON_STATE.md`本身也在其中），第80輪(FUT)已明確記錄「本輪commit刻意排除，只commit FUT軌相關檔案」。本輪延續同樣判斷，跳過TW，改做次舊的US軌（US round79 01:03 < FUT round80 02:05）。

**做的事**：新寫`us_factor_ic.py`——重用`factor_ic.py`既有的`evaluate_factor()`/`build_snapshots()`（泛型、不需要改，只要輸入符合`{sid: DataFrame}`+`date`/`adj_close`/factor欄位的形狀即可），自己寫US專屬的樣本抽樣（`us_universe.universe()`隨機抽40檔，seed=20260826）跟trading calendar（用AAPL自身日期序列當calendar proxy，因為這軌還沒有類似TAIEX的市場指數序列）。40檔全部走`load_dev`（`load_dev()`已經是唯一合規進入點，符合協定第4節「絕對不碰holdout」規則）。

**結果**：**40次呼叫全部回傳HTTP 403 `{"msg":"ip banned","status":403,"retry_after":~709-731}`**——不是單純額度用盡（402），是這個IP被暫時封鎖（約12分鐘）。原因研判：TW軌互動session的混合資料源大量backfill＋round79前一次402，短時間內對這個IP的FinMind請求量顯然觸發了更嚴重的封鎖層級，而不只是配額歸零。0/40可用樣本，遠低於`evaluate_factor()`要求的最小10檔橫截面，**無法跑IC測試，腳本正確地中止並回報「這是infra/資料可用性發現，不是因子結果」，沒有寫CHEAP_PASS/FAIL判定**。

**⚠️腳本本身有個bug，這輪順手修了**：一開始的`QUOTA_ERROR_MARKERS`只有`("402","429")`，沒接住這次實際的403/"ip banned"格式，導致早停邏輯沒生效，40個樣本全部打完才發現（浪費了39次多餘的呼叫，都打在同一個已知被封的IP上）。已改成`("402","429","ip banned","ip_banned")`，讓下次遇到同款格式能在第一次呼叫就停手。**這個修正只做了邏輯層面的檢查（讀程式碼確認字串比對正確），沒有再打一次API驗證**——目前IP還在封鎖期內，沒必要再消耗一次呼叫只為了驗證早停邏輯本身，晚一點等封鎖解除、下一輪真的要抓資料時自然會驗證到。

**判定**：這不是因子/策略統計檢定，不計入`TRIALS_LEDGER.md`，跟第70/74/77輪先例一致（純infra/資料可用性發現）。`f_us_low_vol`便宜關卡IC測試依然是US軌待完成的下一步，等IP封鎖解除、有足夠新鮮的sample可用時再試一次（下次應該會在第一檔就停手，而不是打完40檔才發現）。

`is_holdout_consumed()` 確認為 `False`（本輪所有價格呼叫都走`us_factors.us_price_series()`→`load_dev()`，全部被拒絕在`_fetch()`層，沒有任何一筆資料真正落地；沒有呼叫`load_full_history()`/`unlock_holdout_once()`）。

## 2026-08-26T03:35:00+08:00 — 馬拉松第82輪：`f_us_low_vol`第一次真正完成1a便宜關卡IC測試——**US軌第一個CHEAP_PASS**

**取鎖與選軌背景**：取鎖時偵測到`LOCK_STALE`（上一輪pid 136244持有鎖30.0分鐘後被回收，疑似異常中止，未留下任何log）。三軌時間戳比對：TW軌實際上最舊（第76輪2026-08-25T21:05，之後只有使用者互動session直接改動未commit的檔案，不是馬拉松輪次），但延續第80/81輪的判斷——`git status`確認TW軌一批混合資料源架構的互動session變更仍然未commit（`TW_MARATHON_STATE.md`本身也在其中），繼續刻意不碰。FUT軌（第80輪02:05）依`MARATHON_PROTOCOL.md`「FUT佔比上限20%、選輪次時TW/US優先」的裁示被跳過。改選US軌（第81輪02:35，三者中可用選項裡最舊）。

**做的事**：重跑`python us_factor_ic.py`——第81輪已寫好管線＋修好早停偵測（403/"ip banned"字串偵測），本輪只是重新執行等待IP封鎖解除後的結果。

**結果：IP封鎖已解除，測試順利跑完**。40檔隨機樣本（seed=20260826）：27檔可用、13檔被過濾（8檔EMPTY下市/無資料、2檔<260列太短、1檔含`/`特殊字元觸發FinMind HTTP 400 "data_id is illegal"新踩雷、2檔省略——實際上是27 usable，13 dropped，加總40）。125個不重疊20交易日快照，2015-01-01～2024-12-31。

`f_us_low_vol`（60日日報酬std取負號）：train mean_ic=+0.0310 IR=+0.114（n=76期）、val mean_ic=+0.1340 IR=+0.557 hit_rate=0.71（n=49期），train/val同號（both positive，方向一致）。null percentile=100.0，遠超單測門檻90.0。**PASSES cheap gate: True——US軌自2026-08-23馬拉松第一輪開始以來，第一次有因子真正跑完統計檢定並通過便宜關卡**。

**新發現（小雷，非阻斷性）**：樣本裡出現`AKO/B`這種代號含`/`的股票，FinMind API把它當非法`data_id`直接拒絕（HTTP 400），不是額度/IP問題。`us_factor_ic.py`目前的處理方式是照既有的price ERROR分支自然跳過並繼續下一檔，行為正確，但這是第一次遇到這種格式問題的股票代號，記錄在案供之後`us_universe.py`若要做代號清理/正規化時參考。

**判定**：`f_us_low_vol` **CHEAP_PASS**，排入US軌待深挖清單（`US_LEADS.md`#1）。**已加`TRIALS_LEDGER.md`#39**（US軌FDR家族第一筆，m=1，見該檔案US軌FDR區塊）。依協定，US軌FDR家族目前只有這一筆，天生容易通過門檻，深挖時（1b）第一步務必做train/val切分（吸取FUT軌`fut_basis_carry`的教訓：便宜關卡CHEAP_PASS≠可信候選，見`FUT_MARATHON_STATE.md`第75輪記錄），不能因為FDR顯著或val IC看起來很強（+0.134）就跳過完整驗證關卡。

`is_holdout_consumed()` 確認為 `False`（全程走`us_universe.universe()`/`load_dev()`既有合規路徑，沒有呼叫`load_full_history()`/`unlock_holdout_once()`）。

## 2026-08-26T05:02:18+08:00 — 馬拉松第84輪：接手孤兒工作——`f_us_low_vol`深挖（1b）結果補記+收工，**FAIL，#39的CHEAP_PASS降級**

**取鎖與選軌背景**：取鎖時偵測到`LOCK_STALE`（pid 141036持有鎖29.9分鐘，超過25分鐘陳舊門檻被回收）。回收後檢查`git status`，發現一批**尚未commit但看起來已經完成的US軌工作**：新檔`deep_dive_f_us_low_vol.py`（300行）、`US_LEADS.md`（#1那列已從「尚未深挖」更新成完整的深挖結果）、`TRIALS_LEDGER.md`（已加#41列）。但`US_LOG.md`、`US_MARATHON_STATE.md`都還是第82輪的舊內容，`REPORT.md`心跳也停在第83輪（TW）——**判定：這是上一輪（pid 141036）真正做完1b深挖分析、寫完兩份紀錄檔案後，在寫`US_LOG.md`/`US_MARATHON_STATE.md`/心跳/commit的路上被中止**（研判是Windows工作排程器30分鐘週期到時被強制結束，分析本身花了較長時間，收工程序沒跑完），不是完全沒做事的空鎖。

**這輪做的事：核實孤兒工作，不重做分析**：
1. 讀`deep_dive_f_us_low_vol.py`全文，確認：(a) 資料存取只透過`load_dev`（`from finmind_client import load_dev`），沒有`load_full_history`/`unlock_holdout_once`字樣，符合協定第4節；(b) 邏輯結構跟`US_LEADS.md`/`TRIALS_LEDGER.md`裡記錄的數字對得上（TRAIN/VAL兩期、1x/2x/3x成本、配對式隨機控制組percentile、SPY beta）；(c) docstring明確提到吸取`fut_basis_carry`（#37 FAIL）教訓，先做train/val切分再判定，方法論上站得住腳。
2. 跑`is_holdout_consumed()`確認仍是`False`（見下方）。
3. 補齊`US_MARATHON_STATE.md`最新一版記錄（FAIL結果+下一步建議：待深挖清單已清空，回到1c擴充第二個因子）。
4. 寫這筆`US_LOG.md`記錄（本筆）。

**結果摘要（數字取自孤兒工作留下的`US_LEADS.md`#1／`TRIALS_LEDGER.md`#41，未重新執行驗證）**：`f_us_low_vol`深挖用同27檔快取樣本+SPY market benchmark，十分位多空(k=3/腳,20日換倉)。TRAIN(2015-2020)×1x/2x/3x：ann_return −13.16%~−13.87%（全負），對配對式隨機控制組percentile僅41.0~48.0（**連中位數都沒贏過**），beta −0.149。VAL(2020-2024)×1x/2x/3x：ann_return +17.53%~+18.67%，percentile 91.0~97.0，但beta **−0.891**（遠非市場中性，接近反向於SPY的方向性押注）。**判定：TRAIN期未過隨機控制組門檻本身已足以結案；VAL期表面轉強伴隨beta驟降，暗示是方向性反向曝險而非橫斷面排序優勢——跟FUT`fut_basis_carry`(#35→#37)、TW`f_rel_strength_regime_switch`(#40)同款「便宜關卡過、深挖不成立」模式第三例。FAIL，不進入候選清單，#39的CHEAP_PASS判定降級。**

**方法論觀察（給之後的無人值守輪次參考）**：這是馬拉松第一次出現「上一輪陳舊鎖檔裡其實藏著完整、正確、只是沒寫完收工程序的工作」，跟先前幾次陳舊鎖檔（pid 136244、136244之前那次）不同——先前幾次都是真的什麼都沒留下。**教訓：陳舊鎖檔不代表上一輪一定一事無成，接手前先看`git status`有沒有看起來完整的孤兒變更，值得的話核實後收下、比重做更有效率，但核實步驟（讀程式碼確認holdout合規、核對數字前後一致）不能省略——不能因為「看起來已經做完」就照單全收不查證。**

## 2026-08-26T07:33:00+08:00 — 馬拉松第89輪：接手孤兒工作（第二次）——US軌`f_us_momentum_12m`（#2）1a便宜關卡結果補記+收工，**FAIL，未進深挖**

**取鎖與選軌背景**：取鎖時偵測到`LOCK_STALE`（pid 138560持有鎖30.0分鐘後被回收，超過25分鐘陳舊門檻）。`git status`檢查發現一批看起來已完成的US軌工作：`us_factors.py`（新增`f_us_momentum_12m`因子定義+smoke test）、`us_factor_ic.py`（改成只測尚無判定的新因子，跳過已有終局判定的`f_us_low_vol`）、`US_LEADS.md`（#2新增列，完整結果）、`TRIALS_LEDGER.md`（已加#44列）、`US_MARATHON_STATE.md`（已更新到「馬拉松第88輪」的敘述）。但`US_LOG.md`（本檔案）跟`REPORT.md`心跳都還停在第87輪——判定模式跟第84輪（pid 141036那次）完全一致：**上一輪（pid 138560）真正做完1a便宜關卡測試、寫完程式碼跟三份紀錄檔案後，在寫`US_LOG.md`/心跳/`MARATHON_STATE.md`計數器/commit的路上被Windows工作排程器30分鐘週期強制中止**，不是空鎖。

**這輪做的事：核實孤兒工作，不重做分析**（同第84輪先例的核實步驟）：
1. 讀`us_factors.py`跟`us_factor_ic.py`的完整diff，確認：(a) `f_us_momentum_12m`是純價格因子（`adj_close`的t-252到t-21累積報酬），零PIT依賴，跟`f_us_low_vol`同精神；(b) `us_factor_ic.py`資料存取仍只透過`load_dev`（`from finmind_client import load_dev`），全文搜尋確認沒有`load_full_history`/`unlock_holdout_once`/下單相關字樣；(c) 新增的`ALREADY_VERDICTED`跳過邏輯合理（`f_us_low_vol`已有終局FAIL判定，重測會浪費API額度且錯誤地把單因子批次跟雙因子批次的bonferroni_n混淆）。
2. 跑`is_holdout_consumed()`確認仍是`False`（見下方）。
3. 核對`US_LEADS.md`#2跟`TRIALS_LEDGER.md`#44的數字是否一致——**一致**：TRAIN(2015-2020) mean_ic=−0.0129 IR=−0.042（n=76期）、VAL(2021-2024) mean_ic=+0.0613 IR=+0.205 hit_rate=0.57（n=49期）、null percentile=94.6，同一批27/40可用樣本（同種子），跟`US_MARATHON_STATE.md`敘述完全對得上。
4. 補齊這筆`US_LOG.md`記錄（本筆）——`US_MARATHON_STATE.md`本身孤兒工作已經寫好，不需要再改。

**結果摘要（數字取自孤兒工作留下的`US_LEADS.md`#2／`TRIALS_LEDGER.md`#44，未重新執行驗證）**：`f_us_momentum_12m`（12-1動能，Jegadeesh-Titman經典定義，t-252到t-21交易日累積報酬，跳過近1個月避開短期反轉混淆）用同一批40檔隨機樣本（27檔可用）跑`evaluate_factor()`：TRAIN(2015-2020) mean_ic=−0.0129 IR=−0.042（n=76期，為負）；VAL(2021-2024) mean_ic=+0.0613 IR=+0.205 hit_rate=0.57（n=49期，為正）；對隨機打散null percentile=94.6（單測門檻90.0，此關本身有過）。**但`evaluate_factor()`的same_sign檢查（train/val方向一致性）未過**——train為負、val為正，依協定同號要求優先於percentile門檻，直接判**FAIL，不進深挖**。

**判定**：`f_us_momentum_12m` **FAIL**（便宜關卡本身沒過，即使null percentile單獨看有過線）。US軌因子驗證累積2筆，皆FAIL（#1`f_us_low_vol`深挖FAIL、#2`f_us_momentum_12m`便宜關卡FAIL），至今尚無任何PASS/EXPERIMENTAL候選。US軌FDR家族m=2（兩者皆FAIL，累積校正暫不影響）。經濟解釋（孤兒工作已寫好，本輪核實無誤）：12-1動能是文獻中最穩健的美股異常之一，這裡train/val反轉較可能是27檔樣本太小＋未做regime控制所致，不是動能本身無效的證據，值得標記「情境依賴候選」保留追蹤但不升格。

**取鎖模式再次確認**：這是馬拉松第二次出現「上一輪陳舊鎖檔裡藏著完整正確、只差收工程序的工作」（第一次是第84輪核實pid 141036那次），跟第77輪（FUT，補心跳）、第87輪（FUT，補心跳）的「只缺心跳一步」模式略有不同——這次連`US_LOG.md`本身的細節記錄都缺，缺漏範圍比純心跳缺漏更大，但核實方法完全沿用第84輪建立的先例（讀程式碼查holdout合規→核對數字→補記錄），沒有另外發明新流程。

`is_holdout_consumed()` 確認為 `False`（全程走`us_universe.universe()`/`load_dev()`既有合規路徑，沒有呼叫`load_full_history()`/`unlock_holdout_once()`）。

`is_holdout_consumed()` 確認為 `False`（`deep_dive_f_us_low_vol.py`全程走`load_dev()`，本輪沒有呼叫任何FinMind API，零新增網路請求）。

## 2026-08-26T09:04:37+08:00 — 馬拉松第91輪：1a便宜關卡——US軌第三個因子`f_us_reversal_1m`（短期反轉）

**取鎖**：`LOCK_ACQUIRED`（乾淨，非陳舊鎖檔接手）。

**選軌**：讀三軌`_MARATHON_STATE.md`最後更新的git commit時間戳，US軌最久沒被碰（07:34:04 vs TW 08:05:29 vs FUT 08:36:07），本輪選US軌。

**做的事**：延續第88輪`US_MARATHON_STATE.md`「下一步建議」（「擴充第三個因子（短期反轉1週/1個月...）」），`us_factors.py`新增`f_us_reversal_1m`——近1個月（`REV_LOOKBACK=21`交易日，刻意跟`f_us_momentum_12m`的`MOM_SKIP`常數完全相同）累積報酬取負號，純價格、零PIT依賴，同前兩個因子精神。smoke test（`python us_factors.py`，用既有快取AAPL/MSFT，零新API呼叫）通過：warm-up剛好21列NaN符合預期，兩檔皆有合理範圍的有效值。

`us_factor_ic.py`的`ALREADY_VERDICTED`同步加入`f_us_momentum_12m`（第88輪已FAIL但先前只排除了`f_us_low_vol`）——避免這輪因為`US_FACTOR_COLUMNS`已有三個因子而被誤判成多因子批次，本輪維持`bonferroni_n=1`的單因子測試語義。

跑`python us_factor_ic.py`：同一批40檔隨機樣本（seed=20260826，跟#1/#2同種子），27/40可用（13檔因下市/資料太短/`AKO/B`格式問題被過濾，跟#1/#2完全一致，因為是同一份快取樣本）。

**結果**：TRAIN(2015-2020) mean_ic=+0.0938 IR=+0.327（n=76期，正）；VAL(2021-2024) mean_ic=−0.0198 IR=−0.075 hit_rate=0.59（n=49期，負）；null percentile=49.5（單測門檻90.0，不只沒過線，還低於50，比隨機打散還不如）。**FAIL**——train/val方向不一致（same_sign未過），且percentile遠低於門檻，比第88輪動能因子的FAIL更明確（動能至少VAL期percentile 94.6有過線）。

**判定**：`f_us_reversal_1m` **FAIL**（便宜關卡本身沒過）。US軌因子驗證累積3筆，全部FAIL（#1`f_us_low_vol`深挖FAIL、#2`f_us_momentum_12m`便宜關卡FAIL、#3本次便宜關卡FAIL）。至今尚無任何PASS/EXPERIMENTAL候選。US軌FDR家族m=3。經濟解釋：短期反轉是文獻中跟12-1動能同樣穩健但方向相反的異常，這裡測的正是動能因子刻意排除的21日窗口本身——train/val反轉較可能是27檔小樣本、未分層抽樣、無regime控制所致（跟#1/#2同款限制），不代表反轉因子在美股完全無效，但目前證據不支持升格。

**下一步建議**：純price-only因子家族（低波動/動能/反轉）三個都已測完，全部FAIL。若延續同路線可考慮規模/流動性分層抽樣重測；或改做US軌宇宙覆蓋率擴充（`KNOWN_DELISTED`目前僅5檔手動查證下市股）/情境分群類工作。

`is_holdout_consumed()` 確認為 `False`（全程走`us_universe.universe()`/`load_dev()`既有合規路徑，沒有呼叫`load_full_history()`/`unlock_holdout_once()`）。

完整見`US_LEADS.md`#3（新增）、`TRIALS_LEDGER.md`#45（新增）、`us_factors.py`/`us_factor_ic.py`（新增f_us_reversal_1m）。

## 2026-08-26T11:34:59+08:00 — 馬拉松第95輪：規模分層重測三個既有FAIL因子（大型股tier）

**取鎖**：`LOCK_ACQUIRED`（乾淨，非陳舊鎖檔接手）。

**選軌**：讀三軌`_MARATHON_STATE.md`最後修改時間，US軌最久沒被碰（09:04:37 vs FUT 10:35:19 vs TW 11:04:17），本輪選US軌。取鎖前先確認`US_MARATHON_STATE.md`記錄的第91輪push失敗（commit`3cf1a1c`，DNS解析失敗）是否仍積壓——`git fetch`+`git status`確認`Your branch is up to date with 'origin/main'`，代表後續輪次已經自然把這筆commit推上去了，本輪不需要額外處理。

**做的事**：延續`US_MARATHON_STATE.md`第91輪「下一步」建議首選——「規模/流動性分層抽樣重測」，因為三個純價格因子（`f_us_low_vol`/`f_us_momentum_12m`/`f_us_reversal_1m`）都在同一批27檔未分層小樣本上FAIL，備註都指出這可能是樣本問題而非因子問題。新寫`us_factor_ic_by_size.py`：用`us_universe.py`既有的`market_cap`欄位（零額外API呼叫取得分層依據）對6,618檔active宇宙做market cap三分位切割（5,566檔有可用numeric market_cap，各tertile 1,855檔），本輪只測large tier（mid/small留給未來輪次，避免一輪內三倍API用量）。從large tier抽樣30檔（seed=202608261），29檔可用，跑同一套`evaluate_factor()`框架（`bonferroni_n=3`，三因子同批次）。

**結果**（全部FAIL，誠實負面結果）：
- `f_us_low_vol`：train mean_ic=+0.0001（幾乎零）、val mean_ic=+0.0377，percentile=83.4（門檻96.7，未過）。比不分層版更弱，不支持「小型股雜訊拖累」假設。
- `f_us_momentum_12m`：train mean_ic=+0.0191、val mean_ic=−0.0262，percentile=66.8。**same_sign未過，且反轉方向跟不分層版（train負/val正）剛好相反**——這是本輪最有資訊量的發現：兩次不同樣本的train/val反轉方向不一致，代表反轉本身是抽樣雜訊，不是穩定的規模效應。
- `f_us_reversal_1m`：train mean_ic=+0.0357、val mean_ic=+0.0192，percentile=53.4。same_sign通過（跟不分層版train正/val負不同），但val期IC仍接近雜訊水準，沒有變得可用。

**判定**：三個因子的大型股分層版本全部**FAIL**（`TRIALS_LEDGER.md`#47/#48/#49，`US_LEADS.md`#4/#5/#6）。US軌因子驗證累積6筆試驗（3不分層+3分層），全部FAIL，至今尚無任何PASS/EXPERIMENTAL候選。US軌FDR家族m維持3（獨立分母，見`MARATHON_PROTOCOL.md`第2節——分層重測算US軌自己家族內的新試驗，不影響FDR分母邏輯本身，只是同一輪多筆）。

`is_holdout_consumed()` 確認為 `False`（全程走`us_universe.universe()`/`load_dev()`既有合規路徑，零`load_full_history()`/`unlock_holdout_once()`呼叫）。

**下一步建議**：mid/small tier尚未測（`us_factor_ic_by_size.py`的`TIER`常數切換即可沿用，下一輪可接著做）；或視資源配置優先序改做第9項（系統化擴充`KNOWN_DELISTED`名單，目前僅5檔）。

完整見`US_LEADS.md`#4/#5/#6（新增）、`TRIALS_LEDGER.md`#47/#48/#49（新增）、`us_factor_ic_by_size.py`（新增，可重複執行，`TIER`常數可切mid/small）。

## 2026-08-26T12:xx+08:00 — 馬拉松第97輪：中型股tier分層重測，US軌至今第一批CHEAP_PASS

延續第95輪「下一步」建議首選：`us_factor_ic_by_size.py`把`TIER`常數從`"large"`改成`"mid"`（seed也換成`202608262`，跟大型股tier的`202608261`區分），零額外程式碼改動，重測同三個既有FAIL因子。

中型股tertile（1,855檔）隨機抽樣30檔，26檔可用（3檔EMPTY下市/1檔<260列不足）：
- `f_us_low_vol`：train mean_ic=+0.0300 IR=+0.104、val mean_ic=+0.1123 IR=+0.377 hit_rate=0.67，null percentile=100.0（門檻96.7）——**CHEAP_PASS**，同號，數字比大型股tier（第95輪：train≈0/val+0.038/percentile 83.4）明顯強，也比不分層版（第39輪：train+0.031/val+0.134/percentile 100.0）接近。
- `f_us_momentum_12m`：train mean_ic=+0.0119、val mean_ic=+0.0968，null percentile=99.9——**CHEAP_PASS**，但信心等級低：這個因子三次測試（不分層train負/val正、大型股train正/val負、中型股本輪train正/val正）train/val方向組合三次互不相同，比較像小樣本雜訊而非穩定規模效應。
- `f_us_reversal_1m`：train mean_ic=+0.0913、val mean_ic=−0.0345，null percentile=78.4——**FAIL**（same_sign未過），三個tier全部FAIL，是US軌至今唯一三個tier都沒有CHEAP_PASS過的因子。

`is_holdout_consumed()` 確認為 `False`（全程走`us_universe.universe()`/`load_dev()`既有合規路徑，零`load_full_history()`/`unlock_holdout_once()`呼叫）。零額外API呼叫以外的新增支出：本輪對26檔中型股樣本股票發出新的`load_us_sample_with_factors()`請求（未命中大型股/不分層批次的既有快取，因為是不同的股票代號集合），未觸發402/403限流。

**下一步建議**：(a) small tier分層重測（優先，`TIER="small"`即可沿用）；(b) `f_us_low_vol`中型股CHEAP_PASS（#7）深挖前務必先做train/val切分＋beta對照——吸取第41輪教訓（不分層版便宜關卡CHEAP_PASS，深挖後因VAL期beta驟降至−0.891判定FAIL），不能只看便宜關卡數字漂亮就直接假設市場中性；(c) `f_us_momentum_12m`中型股CHEAP_PASS（#8）信心等級低，深挖前建議先換一個種子/更大樣本複驗是否穩定重現，而非直接排入標準深挖清單。

完整見`US_LEADS.md`#7/#8/#9（新增）、`TRIALS_LEDGER.md`#52/#53/#54（新增）、`us_factor_ic_by_size.py`（本輪改動`TIER`/`SAMPLE_SEED`，可重複執行）。

---

## 2026-08-26T14:05:16+08:00 — 馬拉松第99輪：small tier分層重測（優先A，四個樣本版本全測完）

延續第97輪「下一步」建議首選：`us_factor_ic_by_size.py` 把 `TIER` 常數從 `"mid"` 切成 `"small"`（seed=20260826_3，跟large的20260826_1、mid的20260826_2區分），零額外程式碼改動，重測同三個既有因子。

**結果**：小型股tertile 1856檔（跟mid/large各1855檔規模相近），30檔隨機抽樣26檔可用（4檔EMPTY/樣本過短被排除）。

- `f_us_low_vol`：train mean_ic=+0.0182 IR=+0.058（n=74）、val mean_ic=+0.2181 IR=+1.057 hit_rate=0.88（n=49），null percentile=100.0（門檻96.7，過），same_sign通過。**CHEAP_PASS**——這是US軌至今第三個CHEAP_PASS，跟不分層#1、中型股#7同一個因子。四個樣本版本（不分層/大型/中型/小型）val IC分別為+0.134/+0.038/+0.112/+0.218，呈現「規模越小訊號越強、大型股訊號幾乎消失」的梯度，方向上跟BAB/leverage-constraint文獻（散戶/槓桿受限投資人被迫追高波動小型股以達到報酬目標）一致。**但train期IR只有+0.058，遠低於val期+1.057**——跟#1深挖FAIL的根本原因（train期沒過隨機控制組門檻，val期表面轉強伴隨beta驟降至-0.891）同款警訊形狀，深挖前不能只看這裡的win-rate/hit_rate數字就假設會過。
- `f_us_momentum_12m`：train mean_ic=-0.0105、val mean_ic=+0.1460，null percentile=100.0但same_sign未過（train負/val正）。**FAIL**。四次測試（不分層/大型/中型/小型）train/val方向組合：負正、正負、正正（CHEAP_PASS）、負正——四次出現三種不同排列，比第97輪記錄的「三次互不相同」證據更強，坐實這是27-30檔小樣本雜訊，不是穩定規模效應，不建議繼續花輪次追這條規模分層路線。
- `f_us_reversal_1m`：train mean_ic=+0.0695、val mean_ic=+0.0060，null percentile=14.4（門檻96.7，遠未過）。**FAIL**——四個樣本版本（不分層49.5/大型53.4/中型78.4/小型14.4）percentile全部未過門檻，本列是四者最差的一次，短期反轉在美股這個因子定義下的證據最一致地偏弱，家族可視為結案。

**US軌因子驗證累積12筆（3不分層+3大型股+3中型股+3小型股）：3筆CHEAP_PASS（`f_us_low_vol`不分層版/中型股/小型股，`f_us_momentum_12m`中型股信心較低）、9筆FAIL。US軌FDR家族m=3（分層重測不新增家族數，同一批次）。四個樣本版本規模分層重測工作單位至此全部完成。**

holdout狀態確認：`is_holdout_consumed()` = False。

下一輪建議：(a) 深挖`f_us_low_vol`中型股/小型股CHEAP_PASS，先做train/val切分＋beta對照（吸取#1教訓）；(b) 或改做宇宙覆蓋率擴充（`KNOWN_DELISTED`僅5檔）/情境分群類工作。詳見`US_MARATHON_STATE.md`/`US_LEADS.md`#10-12/`TRIALS_LEDGER.md`#57-59。

## 2026-08-26T16:38:29+08:00 — 馬拉松第103輪：`f_us_low_vol`小型股tier深挖（1b完整驗證），FAIL

延續第99輪「下一步」建議：深挖`f_us_low_vol`小型股CHEAP_PASS（#10，val IC=+0.2181，四個樣本版本裡最強）。新增`deep_dive_f_us_low_vol_small_tier.py`（重用`deep_dive_f_us_low_vol.py`回測機制+`us_factor_ic_by_size.py`的TIER="small"抽樣，seed=20260826_3，同一批30檔小型股樣本，26檔可用）。

跑了完整1b關卡：TRAIN(2015-01-01..2020-12-31,1x slippage) ann_return=-61.57%，beta=+0.260，random_control_percentile=68.0；VAL(2020-12-31..2024-12-31,1x) ann_return=+280.63%，beta=-0.587，random_control_percentile=100.0。成本2x/3x下方向與數量級皆無實質變化（TRAIN仍負、VAL仍極端正）。

**判定：FAIL。** train/val正負號翻轉，beta正負號也翻轉（+0.260→-0.587），跟round 84不分層版深挖FAIL同款警訊形狀、且更嚴重（VAL期年化報酬跟TRAIN期量級差距達到+280% vs -61.57%的極端程度）。樣本裡有多檔2020年後才有資料的微型生技/殼股（BEEP/HKD/TVGN/AMZE/MOBX等），decile size僅k=3/leg（26檔樣本），懷疑單檔波動放大主導了整段VAL期回測，不是穩定可信的規模效應。誠實記錄：cheap gate的橫斷面IC方向本身沒有錯（#10的val IC=+0.2181確實是真實計算結果），但cheap gate只測IC方向、不測真實部位P&L路徑的train/val一致性，這正是為什麼協定要求CHEAP_PASS必須經過1b深挖才能升格，不能只看cheap gate就採信。

**US軌至今累計13筆試驗、0筆深挖後仍成立的PASS/EXPERIMENTAL。** 中型股tier（#7 CHEAP_PASS，percentile=100.0）尚未深挖，但基於#1（不分層版）+本輪（小型股版）兩次一致的失敗模式，下一輪深挖中型股前不應預設會有不同結果——可以做，但要誠實預期，若同樣FAIL，`f_us_low_vol`整個因子跨所有tier可視為結案。

holdout狀態確認：跑前跑後`is_holdout_consumed()`皆為`False`。零新增API呼叫（`load_us_sample_with_factors`同round 99快取，`_load_market_df()`的SPY一次性fetch也命中既有快取，本輪log顯示"market benchmark: SPY, 8038 rows"無新fetch訊息）。

完整見`TRIALS_LEDGER.md`#64、`US_LEADS.md`#13、`deep_dive_f_us_low_vol_small_tier.py`（新增，可重複執行）。


---

## 馬拉松第106輪（2026-08-26T18:10:00+08:00）

取鎖時偵測到`LOCK_STALE`（pid 146308持有30.0分鐘，上一輪疑似異常中止，未查到殘留未commit工作，是乾淨崩潰）。

延續第103輪「下一步」建議首選：深挖`f_us_low_vol`中型股tier（`US_LEADS.md`#7 CHEAP_PASS，round 97 cheap gate：train IC+0.0300/val IC+0.1123，null percentile=100.0）。新增`deep_dive_f_us_low_vol_mid_tier.py`，同`deep_dive_f_us_low_vol_small_tier.py`模式（重用`deep_dive_f_us_low_vol.py`的`run_long_short_us`/cost model/SPY benchmark/random control helper），差異是monkeypatch `us_factor_ic_by_size.TIER="mid"`（該模組目前TIER=`"small"`，不直接改檔案避免影響其他script），重用round 97的seed=20260826_2、SAMPLE_SIZE=30。

26/30檔可用（COSO/EMAT/RMIX無資料、BRUN樣本太短）。市場基準SPY命中既有快取（8038筆）。

**結果：FAIL。** TRAIN(2015-2020,1x) ann_return=-28.53%，對100次配對式隨機控制組percentile僅12.0（**連隨機控制組中位數都沒贏過**），beta=-0.676；2x/3x成本下方向不變（percentile 15.0/16.0）。VAL(2020-2024,1x) ann_return=+22.24%，percentile=92.0，但beta=-1.052（比TRAIN期更負，非翻轉、是同向加深）；2x/3x下percentile略升至94.0/95.0。

跟#13（小型股tier，beta+0.260→-0.587正負號翻轉）警訊型態不同——這裡beta在TRAIN/VAL兩期都是負值且持續加深，代表這26檔中型股樣本組合本身結構性地帶有反市場方向性曝險，不是規模效應本身帶來的訊號。VAL期表面轉強的年化報酬跟alpha，較可能來自2020-2024美股大盤大漲期間「反向押注」剛好獲利，不是穩定的橫斷面排序優勢。TRAIN期沒過隨機控制組門檻（percentile 12-16）本身就足以結案，不需要等VAL期數字才能判定。

**`f_us_low_vol`四個樣本版本至此全部跑完**：不分層#1（1b深挖FAIL）、大型股#4（1a便宜關卡本身沒過，未進1b）、中型股本輪#14（1b深挖FAIL）、小型股#13（1b深挖FAIL）——**因子家族結案**。US軌純price-only三因子家族（低波動/動能/反轉）連同規模分層重測（#1-#14共14筆）全部結案，累計仍是0筆深挖後成立的PASS/EXPERIMENTAL。

holdout狀態確認：跑前跑後`is_holdout_consumed()`皆為`False`。零新增API呼叫（`load_us_sample_with_factors`命中既有快取，SPY市場基準也命中既有快取，本輪log顯示"market benchmark: SPY, 8038 rows"無新fetch訊息）。

**下一步建議**：純price-only因子路線至此已完整走過一輪（不分層+3個規模tier×3個因子=12+2便宜關卡即停=14筆），繼續在同一路線加碼（例如更多tier切法、更多price-only因子變體）預期邊際資訊量遞減。優先序改為：(a) 需要基本面/PIT資料的新因子家族（價值PB/PE、品質），屬於1c地基工作——先確認SEC EDGAR資料源可用性/申報日期欄位（`CLAUDE.md`提過既有邏輯可參考，不能動`alpha-data/fetch.py`凍結區本身），這是US軌目前唯一還沒搭的地基缺口；(b) 或宇宙覆蓋率/存活者偏差調查（`KNOWN_DELISTED`僅5檔，`US_LEADS.md`「目前狀態」段落已記錄過這條調查此前是負面結果，需要換SEC EDGAR方法而非繼續猜）。

完整見`TRIALS_LEDGER.md`#68、`US_LEADS.md`#14、`deep_dive_f_us_low_vol_mid_tier.py`（新增，可重複執行）。

## 2026-08-26T19:05+08:00 — 馬拉松第108輪：`us_fundamentals.py`——XBRL company-facts首個可重用wrapper（PB因子地基第一步）

**動機**：延續第106輪「下一步」建議首選(a)——純price-only三因子家族（低波動/動能/短期反轉）四個樣本版本全部結案（12+4=16筆試驗，見`US_LEADS.md`#1-#14），下一個因子家族轉向需要基本面/PIT資料的價值/品質類。round 10（`sec_edgar_xbrl_facts_probe.py`）/round 11（`sec_edgar_xbrl_facts_dedup_probe.py`）已經探測過XBRL company-facts端點本身（含per-datapoint去重邏輯：group by `end`、取最小`filed`），但從未包裝成可重用模組——跟submissions端點走過的路徑一樣（round 3探測→之後某輪才包成`sec_edgar_client.py`），這輪補上XBRL側對應的那一步。

**取鎖**：乾淨（非陳舊鎖檔）。**選軌**：三軌時間戳FUT最舊（17:05）但近10輪窗口（round 98-107）FUT已佔20%（round 98/104兩次）達上限，比照第107輪「近10輪已達20%資源配置上限改選TW」的先例，這輪也跳過FUT，改選次舊的US（18:10，早於TW的19:45）。

**做的事**：新增`research/us_fundamentals.py`：
- `get_companyfacts(cik)`：重用`sec_edgar_client._cached_get()`同一套快取邏輯，抓`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`原始payload（新的快取命名空間，跟submissions分開）。
- `list_available_concepts(cik, taxonomy)`：診斷用，列出某filer在某分類法下實際回報哪些concept tag。
- `get_concept_series(cik, concept, taxonomy, forms)`：單一concept的PIT對齊+去重時間序列，去重邏輯照搬round 11驗證過的「group by `end`、取最小`filed`、僅10-K/10-Q」，回傳欄位`end`/`pit_date`/`val`/`form`/`unit`/`gap_days`。

**這輪只搭wrapper本身，沒有計算任何因子**——符合「一輪一個工作單位」跟`sec_edgar_client.py`當年的先例（wrapper先行，因子消費邏輯留給下一輪）。

**Smoke test過程中修了一個真bug**：`get_concept_series()`初版把去重字典的key寫錯（`filed`寫成`pit_date`，比較時用了不存在的key），第一次執行`KeyError: 'filed'`當場報錯，修正為統一用`pit_date`後重跑成功——這個bug在smoke test階段就抓到，沒有汙染任何記錄檔案。

**執行結果**（AAPL/MSFT/PLTR，同三檔round 3/10/11已驗證CIK）：

- `StockholdersEquity`（us-gaap，book value分子）：AAPL 72期（2006-09-30~2026-06-27）、MSFT 73期（2008-06-30~2026-06-30）、PLTR 31期（2017-12-31~2026-06-30），三檔皆有資料。
- `CommonStockSharesOutstanding`（us-gaap，股數）：AAPL 70期、MSFT 70期、PLTR 25期，三檔皆有資料。
- `EntityCommonStockSharesOutstanding`（dei，備援股數標籤）：AAPL 69期、MSFT 67期、**PLTR 0期（完全查不到）**。

**關鍵可行性發現**：`StockholdersEquity`+`CommonStockSharesOutstanding`（皆us-gaap）合起來就能算book value per share，**PB因子的兩個核心輸入可行性確認**。但原本以為可以當備援/對照來源的`dei`股數標籤，PLTR完全查不到——**代表股數來源應該以us-gaap標籤為主，dei標籤只能當「gaap標籤剛好缺失時的最後備援」，不能對調優先序**，這是這輪最有資訊量的發現。

**誠實記錄一個尚未解決的異常**：`StockholdersEquity`的`gap_days`（pit_date−end）中位數合理（AAPL 32天/MSFT 27天/PLTR 42天，跟`us_pit.py`的filing gap同量級），但**max值異常大**（AAPL 1123天、MSFT 760天、PLTR 1153天）。推測是`us_pit.py`已經記錄過的pre-XBRL-mandate（`XBRL_MANDATE_PHASE1_CUTOFF="2009-06-15"`）同款artifact在company-facts端點的具體展現——早期期間的數字可能是好幾年後另一份申報書把它當比較期數字第一次以XBRL格式帶出來，這輪**沒有查證這個推測是否成立**，只誠實標記`gap_days`在早期年份不能直接當PIT品質信賴指標使用，下一輪如果要用這個模組建構真正的因子輸入，應該先按`end`年份分段統計（同`era_reliability()`精神）排查。

**Holdout狀態確認**：跑前跑後`is_holdout_consumed()`皆為`False`——本輪只打SEC EDGAR公開API，不碰FinMind/alpha.db，holdout規則不適用，同`sec_edgar_*.py`系列腳本一貫慣例。

**下一步**：(a) 用同樣模式驗證PE因子需要的分子（`NetIncomeLoss`或`EarningsPerShareDiluted`，round 10已驗證AAPL/MSFT/PLTR皆有資料）；(b) 針對`gap_days`異常值按年份分段統計，確認是否真的是pre-2009 artifact；(c) 確認可行後才進入1a——寫`f_us_value_pb`的cheap gate測試。這不是因子/策略統計檢定，`TRIALS_LEDGER.md`不需要加列，跟第二～七輪同類地基工作先例一致。完整程式碼見`research/us_fundamentals.py`（docstring含完整方法論跟三項已知限制）、`DATA.md`「美股 PIT 資料源調查（六續）」小節。

---

## 第 111 輪 · 2026-08-26T21:02+08:00

取鎖乾淨（非陳舊鎖檔）。三軌輪替本應選US（時間戳最舊，19:05），但`MARATHON_PROTOCOL.md`最上方2026-08-26晚使用者裁示的單因子試驗暫停規則第3點適用：US軌沒有`PORTFOLIO_STRATEGY_SPEC.md`相關的組合策略工作可做（那份規格書內容是TW專屬的台股多因子規格：`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`/`f_value_pe`，跟US軌無關）。

round 108留下的「下一步」(a)驗證PE因子分子（`NetIncomeLoss`/`EarningsPerShareDiluted`）本身雖然是1c地基工作、不直接構成「測試單因子假說」，但這輪判斷繼續往那個方向推進終究是為了later測`f_us_value_pe`鋪路，在暫停規則明確禁止「不分軌道」開始任何新因子相關工作的精神下，本輪選擇保守跳過，不繼續。

**本輪沒有做任何實質工作**，只確認狀態（`is_holdout_consumed()`為`False`）、補寫這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round 108的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則後從那裡接續，不需要重新規劃。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第 114 輪 · 2026-08-27T01:31+08:00

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 01:20（第113輪剛更新）、US 21:02（第111輪，最舊）、FUT 21:32（第112輪）——正常輪替本應選US。

複查`MARATHON_PROTOCOL.md`最上方暫停規則現況：`PORTFOLIO_STRATEGY_SPEC.md`第3行仍標記「狀態：待使用者確認」，未見變動；`LEADS.md`的`portfolio_multifactor_v2`列（規格已完整套用，12組合皆FAIL但兩組合p=0.053接近顯著）也仍是最新狀態，`TW_LOG.md`第113輪明確記錄下一輪TW軌工作應先確認使用者是否已回應「下一步」三選項，未回應前不應自行升級——這代表暫停規則整體仍完全生效中，沒有任何解除跡象。`PORTFOLIO_STRATEGY_SPEC.md`全文grep確認不含「美股」/「US軌」字樣，純屬TW專屬規格，US軌依舊沒有組合策略相關工作可接。

round 108/111遺留的「下一步」(a)驗證PE因子分子（`NetIncomeLoss`/`EarningsPerShareDiluted`）、(b) gap_days異常值分段排查、(c) `f_us_value_pb`便宜關卡，三項本質上都是為了推進單一因子（`f_us_value_pb`/`f_us_value_pe`）鋪路的地基工作，跟round 111判斷邏輯一致：保守跳過，不代為決定暫停規則的邊界該怎麼解讀。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（本輪未打任何API，沿用round開始前的檢查結果）、補寫這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round 108的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則或明確回應`portfolio_multifactor_v2`「下一步」選項後再接續。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第 117 輪（2026-08-27T03:01+08:00，US軌，跳過）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 02:43（第116輪，最新）/US 01:31（第114輪，最舊）/FUT 02:01（第115輪）——依輪替選US。

複查`MARATHON_PROTOCOL.md`最上方暫停規則：`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「待使用者確認」，`git log`確認自`bf7895a`（第116輪TW T86回補）以來沒有任何互動session介入、沒有使用者新回應，暫停規則整體仍完全生效中。

US軌檢查有沒有組合策略相關工作可做：`PORTFOLIO_STRATEGY_SPEC.md`規格書內容全部圍繞TAIEX/TWSE/台股樣本（見規格書第8節「樣本沿用`factor_ic.py`既有的100檔驗證樣本」，該樣本是台股宇宙），跟US軌完全無關，沒有可做的組合策略工作。

round 108/111遺留的「下一步」(a)驗證PE因子分子、(b) gap_days異常值分段排查、(c) `f_us_value_pb`便宜關卡，三項本質上仍是為單一因子（`f_us_value_pb`/`f_us_value_pe`）鋪路的地基工作，跟round 111/114判斷邏輯一致：保守跳過，不代為決定暫停規則的邊界該怎麼解讀。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（本輪未打任何API）、補寫這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round 108的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則或明確回應`portfolio_multifactor_v2`「下一步」選項後再接續。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第 120 輪（2026-08-27T04:32+08:00，US軌，跳過）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 04:21（第119輪，最新）/US 03:01（第117輪，最舊）/FUT 03:31（第118輪）——依輪替選US。

複查`MARATHON_PROTOCOL.md`最上方暫停規則：`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「待使用者確認」，`git log`確認自`69c2285`（第119輪TW T86回補）以來沒有任何互動session介入、沒有使用者新回應，暫停規則整體仍完全生效中。

US軌檢查有沒有組合策略相關工作可做：`PORTFOLIO_STRATEGY_SPEC.md`規格書內容全部圍繞TAIEX/TWSE/台股樣本，跟US軌完全無關，沒有可做的組合策略工作，跟round 111/114/117判斷邏輯一致。

round 108/111遺留的「下一步」(a)驗證PE因子分子、(b) gap_days異常值分段排查、(c) `f_us_value_pb`便宜關卡，三項本質上仍是為單一因子（`f_us_value_pb`/`f_us_value_pe`）鋪路的地基工作，保守跳過，不代為決定暫停規則的邊界該怎麼解讀。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（本輪未打任何API）、補寫這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round 108的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則或明確回應`portfolio_multifactor_v2`「下一步」選項後再接續。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

---

## 第 123 輪（2026-08-27T06:01+08:00，US軌，跳過）

取鎖時偵測到`LOCK_STALE`（pid 158272持有29.9分鐘，上一輪即第123輪的前次嘗試疑似異常中止）。查證工作目錄乾淨，未發現殘留未commit的孤兒工作。

三軌時間戳：TW 05:20（第122輪，最新）/US 04:32（第120輪，最舊）/FUT 05:01（第121輪）——依輪替選US。

複查`MARATHON_PROTOCOL.md`最上方暫停規則：`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「待使用者確認」，`git log`確認自`a89f311`（第122輪TW T86回補）以來只有第120/121輪跳過提交，沒有任何使用者互動session介入，暫停規則整體仍完全生效中。

US軌檢查有沒有組合策略相關工作可做：`PORTFOLIO_STRATEGY_SPEC.md`規格書內容全部圍繞TAIEX/TWSE/台股樣本，跟US軌完全無關，沒有可做的組合策略工作，跟round 111/114/117/120判斷邏輯一致。round 108/111遺留的「下一步」(a)(b)(c)三項本質上仍是為單一因子（`f_us_value_pb`/`f_us_value_pe`）鋪路的地基工作，保守跳過，不代為決定暫停規則的邊界該怎麼解讀。

**本輪沒有做任何實質工作**，只確認`is_holdout_consumed()`為`False`（本輪未打任何API）、補寫這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。round 108的「下一步」(a)(b)(c)三項維持原狀，等使用者解除暫停規則或明確回應`portfolio_multifactor_v2`「下一步」選項後再接續。

沒有新增`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 2026-08-27T07:31:00+08:00 — 馬拉松第126輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 07:13（第125輪，最新）/US 06:01（第123輪，最舊）/FUT 06:32（第124輪）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log`確認自`a89f311`（第122輪，最後一次TW推進；期間123/124/125輪皆為馬拉松自身commit）以來無新使用者互動session介入，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的(a)(b)(c)三項地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則附記+心跳。`is_holdout_consumed()`確認為`False`，無新`TRIALS_LEDGER.md`列。

## 2026-08-27T09:01:00+08:00 — 馬拉松第129輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 08:43（第128輪，最新）/US 07:31（第126輪，最舊）/FUT 08:01（第127輪）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log`確認自`a89f311`（第122輪，最後一次TW實質推進的因子/組合工作以外，之後123-128輪皆為馬拉松自身commit或自動報價流程，`7b4fe7d`新增`data/STATUS.json`跟暫停規則無關）以來無新使用者互動session介入，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的(a)(b)(c)三項地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 2026-08-27T10:32:00+08:00 — 馬拉松第132輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 10:22（第131輪，最新）/US 09:01（第129輪，最舊）/FUT 09:31（第130輪）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log`確認自第129輪以來只有TW軌T86回補（`ce55cc3`）跟一次一般互動session的FinMind依賴收尾（`f25c6cc`/`5c30ae8`，匯率/sparkline/融資維持率/財報籌碼，跟組合策略暫停規則無關）介入，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的(a)(b)(c)三項地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。附記：工作目錄另有一份不屬於馬拉松的未commit修改（`.github/scripts/fetch_quotes_tw.py`，看起來是互動session新增sparkline功能尚未commit），本輪刻意不動它、不納入本輪commit範圍，比照過往「TW軌互動session未commit變更不動」的先例。

## 2026-08-27T20:32:00+08:00 — 馬拉松第150輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：TW 19:31（第149輪，最新）/FUT 19:01（第148輪）/US 18:31（第147輪，最舊）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的(a)(b)(c)三項地基工作本質上仍是為單一因子鋪路，同round111/114/117/120/123/126/129/132/135/138/141/144/147判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪開始時確認工作目錄乾淨。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 2026-08-28T02:01:00+08:00 — 馬拉松第156輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：US 00:31（第153輪，最舊）/FUT 01:01（第154輪）/TW 01:31（第155輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。`git log`確認自第153輪以來新增的commit（`f10b244`TW軌第155輪T86回補、`168a1e1`merge、`1982542`前瞻選股台帳picks_ledger.json B24第一步、`d0999bb`第154輪FUT跳過、`efd7b6f`動能榜因子修正、`39888ae`自動報價更新）皆屬互動session的App開發/資料回補/自動化流程或馬拉松自身跳過紀錄，未觸及暫停規則或`PORTFOLIO_STRATEGY_SPEC.md`。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作（美股宇宙建構/PIT財報資料源/成本模型）本質上仍是為單一因子鋪路，同round111起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳（`REPORT.md`/`MARATHON_STATE.md`）。`git status`本輪開始時確認工作目錄乾淨。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 2026-08-28T05:01:00+08:00 — 馬拉松第162輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：US 03:31（第159輪，最舊）/FUT 04:01（第160輪）/TW 04:31（第161輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。`git log`確認自第159輪以來新增的commit（`c773fb7`第160輪FUT跳過、`eb94649`B24 PIT回測第一次結果、`9a0fd2b`B24方法論修正、`99b7733`PIT背景任務更正、`718a5f9`B23回補計數bug修正、`1b9fcc2`PROGRESS.md記錄、`0e62a50`第161輪TW T86回補）皆屬互動session的研究/開發工作或馬拉松自身跳過紀錄，未觸及`PORTFOLIO_STRATEGY_SPEC.md`。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的(a)(b)(c)三項地基工作本質上仍是為單一因子鋪路，同round111起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**，只補這則log跟`US_MARATHON_STATE.md`附記、心跳。`git status`本輪開始時發現既有未commit變更（`../BACKLOG.md`／`../PROGRESS.md`／`../data/STATUS.json`／`../data/price_history.json`／`../scores_momentum.json`、未追蹤`backfill_final.log`），研判非本輪產生，依規則不觸碰、不納入本輪commit。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。

## 2026-08-28T06:32+08:00 — 馬拉松第165輪：跳過（暫停規則仍生效，無組合策略工作可做）；並補commit第164輪遺留檔案

取鎖時回傳`LOCK_STALE (held by 157136, 30.0 min old) -- recovering`（非乾淨`LOCK_ACQUIRED`）——**上一輪（第164輪，TW軌T86回補）疑似失敗，陳舊鎖檔被回收。** 追查發現：`git status`一開始有3個已修改但未commit的檔案（`research/REPORT.md`／`research/TW_LOG.md`／`research/TW_MARATHON_STATE.md`），內容經檢視是第164輪TW軌T86回補（達成100%覆蓋率）的合法完整記錄（diff乾淨、前後文一致，非半寫壞檔），只是卡在完成寫檔之後、`git commit`之前就被中斷，`MARATHON_STATE.md`全局計數器也因此沒被更新到164（仍停在163）。查`git log`發現最新commit`24724e1`（「輕量值守筆記：AlphaMarathon 06:00輪超出$5預算上限結束(安全機制正常運作)」，06:24另一個互動session寫的）證實根因是**06:00輪撞到$5美元預算上限、安全機制正常中止**，不是bug或crash——第164輪本身工作是誠實完整的，只是被預算上限攔腰斬斷在收工序最後兩步（commit+push、釋放鎖）之前。本輪已將這3個檔案原樣commit（歸還屬於第164輪的紀錄，不算本輪產出），並在`MARATHON_STATE.md`把計數器從163補正到165（跳過中間遺漏的164，用一行註明原因）。三軌時間戳：US 05:01（第162輪，最舊）/FUT 05:31（第163輪）/TW 06:13（第164輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中。US軌依舊沒有組合策略相關工作可做（規格書為台股專屬），round108/111遺留的1c地基工作本質仍是單因子相關工作，同round111起連續判斷邏輯一致，保守跳過。**本輪對US軌判斷是整輪跳過、不做任何新的實質工作**，唯一的實質動作是補commit第164輪遺留檔案+修正計數器落差。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列。

## 2026-08-28T08:01:00+08:00 — 馬拉松第168輪：跳過（暫停規則仍生效，無組合策略工作可做）

取鎖乾淨（非陳舊鎖檔）。三軌時間戳：US 06:32（第165輪，最舊）/FUT 07:01（第166輪）/TW 07:33（第167輪，最新）——依輪替選US。複查`PORTFOLIO_STRATEGY_SPEC.md`第3行仍「狀態：待使用者確認」，`git log -- research/PORTFOLIO_STRATEGY_SPEC.md`確認自建立（`fa369b9`）以來仍只有這一個commit，暫停規則整體仍完全生效中；`git log`確認第165輪以來新增的commit（`e3d9733`第166輪FUT跳過、`c2ae291`第167輪TW跳過）皆屬馬拉松自身跳過紀錄，未觸及暫停規則。US軌依舊沒有組合策略相關工作可做（`PORTFOLIO_STRATEGY_SPEC.md`是台股專屬規格，全部圍繞TAIEX/TWSE樣本，跟US軌無關），round108/111遺留的1c地基工作（美股宇宙建構/PIT財報資料源/成本模型）本質上仍是為單一因子鋪路，同round111起連續判斷邏輯一致，保守跳過。**本輪判斷是整輪跳過、不做任何實質工作**。開工時`git status`一度顯示多個不屬於馬拉松的已修改檔案（`.github/scripts/*.py`等，疑似另一互動session正在同時運作），複查後這些變更已消失（該session顯然已自行處理），本輪commit前確認`git status`乾淨、只含本輪自己的檔案。`is_holdout_consumed()`確認為`False`（本輪未打任何API），無新`TRIALS_LEDGER.md`列（沒有任何判定產生）。
