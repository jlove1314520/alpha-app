# STATUS.json data_files：stale／no_date 16 列逐列盤點（先.一三五-1kh-t）

2026-11-04 DevQueue 20261104-170102。資料來源：本機 `data/STATUS.json`（updated_at 2026-11-04T12:50+08:00）；
門檻：`generate_status_json.py` `STALE_HOURS`（沒列的預設 24 小時）。**本輪不改任何門檻、不改 static 清單**，只分類＋開修復條目。

分類：
- **A 真停擺**：照設計應該更新卻沒更新。
- **B 頻率本來就低**：照設計就是一週／一次性才更新，24 小時門檻本來就會亮 stale（應改 static 或調門檻＝要裁示）。
- **C 檔內其實有日期**：通用解析沒認到既有欄位，可以讀既有欄位（純 bug 修復）。
- **D 真的沒有日期欄位**：一次性研究產出／舊檔，沒有能讀的時間。

## stale 8 列

| 檔案 | generated_at | 產生者／頻率 | 判定 | 證據 |
|---|---|---|---|---|
| `data/listed_universe.json` | 11-03 07:10 | `audit.yml`（每日 cron `20 15 * * 1-5` UTC） | **A 真停擺（已有修法）** | `gh run list --workflow=audit.yml`：11/03 UTC 21:05 班（run 41718634417）只有「Commit 稽核結果」失敗；同一根因已由 先.一三五-1ka 加 push 重試修好（commit 在本班之後）。今晚 23:20 班成功就恢復。 |
| `data/quotes_ibkr.json` | 10-18 11:01 | 本機 `research/ibkr_quotes.py`（IB Gateway） | **A 真停擺（要總司令本人）** | detail＝ConnectionRefusedError；`C:\alpha\總司令待辦.md` 第 3 項「IBKR Gateway 重新登入」已列（並記 11/04 程式檔不見）。CC 不代填帳密。 |
| `data/balance_ibkr.json` | 10-18 11:01 | 同上 | **A（同上根因）** | 同一支、同一時間戳 |
| `data/positions_ibkr.json` | 10-18 11:01 | 同上 | **A（同上根因）** | 同上 |
| `data/holders.json` | 10-31 09:00 | 本機排程 `AlphaTdccHolders` 每日 09:00，TDCC 每週才更新、同一週已存就略過（`_already_built`） | **B 每週一次** | CLAUDE.md「TDCC 集保」段：官方每週更新、只給最新一週。10/31 後下一個新週資料約 11/07。 |
| `data/tw50_constituents.json` | 10-29 21:28 | `market.yml` 每班呼叫，但未滿 6 天就略過（每週約 1 次） | **B 每週一次** | `market.yml` 第 320～325 行註解。今晚 17:13／21 點班次滿 6 天應會更新。 |
| `data/financials_backfill.json` | 10-18 04:04 | 手動／分批 `scripts/backfill_financials_display.py`（每輪上限 300 檔，已補 1979 檔） | **B 一次性回補** | 腳本 docstring（研究室.四）；不在任何 workflow 排程 |
| `data/revenue_backfill.json` | 10-17 06:38 | 手動／分批 `scripts/backfill_revenue_display.py`（已補 1979 檔） | **B 一次性回補** | 腳本 docstring（研究室.三）；不在任何 workflow 排程 |

## no_date 8 列

| 檔案 | 判定 | 證據 |
|---|---|---|
| `data/events_search.json` | **C 有日期** | 頂層 `top.fetched_at`＝2026-11-04T16:06（`news_events.yml`／本機新聞補班 `split_events_by_code.py` 產生）；`describe_generic()` 只找頂層／meta／_meta／metadata，沒找 `top` |
| `data/insider_transfer_tw_history.json` | **C 有日期** | `meta.last_run.fetched_at`＝2026-11-04T01:44Z（`market.yml` 每班）；通用解析只看 meta 第一層 |
| `data/stock_names.json` | D（但每日有產） | `market.yml` 每班 `build_stock_names.py` 重產，`meta` 只有 source／note／count，沒有時間欄位；要有日期得改產生端加 `generated_at` |
| `data/paper_order_log.json` | D（舊檔） | 6 筆，最後一筆 `at`＝2026-09-01；列表沒有頂層時間。內容就是「最後一次測試下單」紀錄，可讀 `[-1].at` 但那是事件時間、不是產生時間 |
| `data/capital_reduction_gap_candidates.json` | D 一次性研究產出 | 只有文字 `generated_at_note`；最後 commit 2026-09-10 |
| `data/capital_reduction_verified.json` | D 一次性研究產出 | `generated_at_note`＝「hypothesis_queue #71 … 2026-09-10 接續」；最後 commit 2026-09-19 |
| `data/news_yield_sample.json` | D 一次性量測 | 只有 `sample`；`scripts/measure_news_yield.py` 手動跑，最後 commit 2026-09-09 |
| `data/price_history_index_legacy.json` | D 舊檔搬移 | `moved_at`＝2026-10-16（搬移日，非資料日）；無產生者 |

## 結論與後續條目

- 真停擺（A）4 列：`listed_universe` 已有修法、等今晚驗收；IBKR 三檔等總司令本人登入（已在總司令待辦）。**不另開重複條目**，只補一條驗收條目（listed_universe 今晚 audit 班）。
- C 類 2 列：純 bug 修復，開條目讓 `describe_generic()` 多認 `top` 範圍與 `meta.last_run.fetched_at`（不改門檻）。
- B 類 4 列＋D 類 6 列：要改成 static 或調門檻＝改既有判定設定，依零之一不自己動，寫成提案由 Cowork 裁示（另開條目寫提案）。
