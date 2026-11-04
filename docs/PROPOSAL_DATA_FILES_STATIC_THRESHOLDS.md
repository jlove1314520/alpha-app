# 提案：STATUS.json data_files 每週／一次性／無日期檔改個別門檻或 static（先.一三五-1kh-v）

2026-11-04 DevQueue 20261104-180102 撰寫。**本輪只寫提案、不動程式。** 送 `research/AWAITING_REVIEW.md` 等 Cowork 審。

## 一、問題（白話）

`data/STATUS.json` 的 `data_files` 每天有 10 列固定亮黃燈（stale）或「沒日期」（no_date），
但那 10 列**照設計本來就不會每天更新**（每週一次、一次性回補、研究產出、舊檔）。
天天亮燈的壞處：真的停擺的那幾列（例如 `listed_universe`、IBKR 三檔）混在裡面，一眼分不出來——
狼來了。盤點證據見 `docs/DATA_FILES_STALE_AUDIT_20261104.md`（先.一三五-1kh-t，B 類 4 列＋D 類 6 列）。

## 二、現行判定機制（`generate_status_json.py`，零請求讀程式得知）

判定順序（第 733～740 行）：`INTENTIONALLY_EMPTY` → ok；`GENERIC_SKIP_STALE` → static；
找不到日期 → no_date；其餘用 `STALE_HOURS.get(路徑, 24)` 小時判 ok／stale。
`GENERIC_SKIP_STALE` 已有先例：設定檔、研究快照、草稿（先.一〇九-4）；`STALE_HOURS` 已有週頻檔給 192 小時的先例（`us_financials.json`、`weekly_report.json`）。

## 三、逐列處理（甲案）

| 檔案 | 現況 | 更新頻率 | 甲案做法 | 理由 |
|---|---|---|---|---|
| `data/holders.json` | stale（10-31 09:00） | TDCC 每週一次，本機排程每日查、同週已存就略過 | `STALE_HOURS` 給 **192**（8 天） | 每週檔仍要能抓停擺：超過 8 天沒新一週＝真停擺 |
| `data/tw50_constituents.json` | stale（10-29 21:28） | `market.yml` 每班呼叫、未滿 6 天略過 | `STALE_HOURS` 給 **192** | 同上；6 天略過＋班次間隔，最長約 7 天 |
| `data/financials_backfill.json` | stale（10-18） | 手動分批一次性回補（已補 1979 檔） | 列進 `GENERIC_SKIP_STALE` | 沒有排程，時間只代表最後一次手動跑 |
| `data/revenue_backfill.json` | stale（10-17） | 同上 | 列進 `GENERIC_SKIP_STALE` | 同上 |
| `data/capital_reduction_gap_candidates.json` | no_date | 一次性研究產出（09-10） | 列進 `GENERIC_SKIP_STALE` | 不會再更新 |
| `data/capital_reduction_verified.json` | no_date | 一次性研究產出（09-19） | 列進 `GENERIC_SKIP_STALE` | 同上 |
| `data/news_yield_sample.json` | no_date | 手動量測（09-09） | 列進 `GENERIC_SKIP_STALE` | 同上 |
| `data/price_history_index_legacy.json` | no_date | 舊檔搬移（10-16），無產生者 | 列進 `GENERIC_SKIP_STALE` | 同上 |
| `data/paper_order_log.json` | no_date | 9/1 測試下單紀錄，之後無寫入 | 列進 `GENERIC_SKIP_STALE` | 紀錄檔，只在下單測試時才寫 |
| `data/stock_names.json` | no_date | `market.yml` 每班重產 | **不列 static**；另開條目讓產生端 `build_stock_names.py` 在 `meta` 加 `generated_at`，之後用預設 24 小時判 | 它每天都該更新，列 static 會把真停擺藏起來 |

預期效果：甲案做完後，stale／no_date 只剩真停擺（目前 `listed_universe` 今晚應恢復、IBKR 三檔等總司令登入）＋`stock_names` 一列（另條修完消失）。

## 四、選項

- **甲（建議）**：照第三節逐列處理——每週檔給 192 小時、一次性檔列 static、stock_names 改產生端。
  - 影響：只動 `generate_status_json.py` 的兩個設定集合（約 9 行），下一班 `market.yml` 重產 STATUS 生效。
  - 風險：一次性檔以後若改成排程產生，要記得從 static 移出（在註解寫明）；回退＝刪掉這幾行。
- **乙**：10 列全部列 static（含 holders、tw50、stock_names）。
  - 影響最小、燈全滅；**缺點**：三個本來會定期更新的檔真停擺時永遠不會亮燈，等於拆掉偵測——違反十一節「監控工具自己也要被監控」的精神。不建議。
- **丙**：維持現狀。
  - 缺點：每天 10 列假警報繼續蓋住真停擺。

## 五、甲案核准後的實作條目（DevQueue 可執行，不在本輪做）

1. `generate_status_json.py`：`STALE_HOURS` 加 `data/holders.json`、`data/tw50_constituents.json` 各 192；`GENERIC_SKIP_STALE` 加 7 個檔名（各附一行註解寫來源＝先.一三五-1kh-v）。
   驗收：本機跑一次產生函式（不寫回 STATUS.json），比對 data_files 各列 status，只有這 9 列變、其他列不變。冒煙全過才 commit。
2. `build_stock_names.py`：`meta` 加 `generated_at`（台北時間 ISO）。驗收：下一班 `market.yml` 後 STATUS 該列從 no_date 變 ok。
   ——這支是雲端排程腳本，只加欄位、不改既有欄位，App 讀取不受影響（實作前再查一次 App 有沒有讀 `meta` 整包）。

## 六、照零之二

24 小時內（2026-11-05 18:2x 前）沒有 Cowork 裁示 → DevQueue 照**甲**執行，條目與 PROGRESS 標 [預設放行]。
