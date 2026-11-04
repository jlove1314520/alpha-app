# 本機排程停擺監控盤點（先.一三五-1kh-f）

2026-11-04 DevQueue 20261104-113101。零外部請求、唯讀：`Get-ScheduledTask -TaskName Alpha*` 共 39 支，
其中 12 支已在 `data/seed/pipeline_registry.json`（停擺自檢清單），**27 支不在**。
`scripts/check_external_connectivity.py::check_local_tasks()` 只看 registry，所以這 27 支停擺時沒有任何告警。

資料取得方式：`(Get-ScheduledTask X).Triggers／.Actions`，再讀 `C:\alpha\run-*-hidden.vbs`、`C:\alpha\run-*.ps1`、
`scripts\run_*.ps1` 裡的腳本與 log 路徑（只用 grep 抓路徑，沒有執行任何排程）。

分類：**該登記**＝有可判的產出；**代管**＝已由 registry 別條看同一份產出；**不必登記**＝已停用／一次性。
「建議看」欄是 1kh-g／1kh-h 的起點，登記前要逐支打開產出檔確認欄位（本表沒有逐檔驗證欄位）。

| 排程 | 狀態 | 觸發 | 主程式 | 產出（log／資料檔） | 分類 | 建議看 | 交給 |
|---|---|---|---|---|---|---|---|
| AlphaTdccHolders | 就緒 | 每日 09:00 | `scripts/fetch_tdcc_holders.py` | `research/tdcc_holders_cycle.log`（PowerShell `*>>`＝UTF-16，且**有進 git**）、`data/holders.json` | 該登記 | holders.json 資料層欄位（週更，interval 10080）；log 不能用（UTF-16＋git 會改 mtime） | 1kh-g |
| AlphaWarrantSnapshot | 就緒 | 週一～五 17:30 | `scripts/run_warrant_snapshot.ps1` | `research/data/warrant_snapshot_cycle.log`、`data/warrant_backup_status.json` | 該登記 | warrant_backup_status.json 時間欄位；`tw_trading_days_only` | 1kh-g |
| AlphaMoeaPitSnapshot | 就緒 | 每日 10:30 | `scripts/snapshot_moea_pit.py` | `research/data/moea_pit_cycle.log`、`research/data/moea_pit_status.json` | 該登記 | moea_pit_status.json | 1kh-g |
| AlphaRfMonthly | 就緒 | 每日 09:20 | `scripts/export_rf_monthly.py` | `research/data/rf_monthly_cycle.log`、`data/rf_monthly.json` | 該登記 | rf_monthly.json（月資料，判準用 log 或「每日有跑」欄位，別用資料月份） | 1kh-g |
| AlphaFinMindWarmup | 執行中 | 每 15 分鐘 | `research/finmind_warmup.py` | `research/data/finmind_warmup_cycle.log`、`finmind_warmup_status.json` | 該登記 | status json | 1kh-g |
| AlphaPaperSupplyV2 | 就緒 | 每小時 | `research/paper_supply_v2.py` | `research/data/paper_supply_v2_cycle.log`、`research/data/paper_supply_v2_log.jsonl` | 該登記 | cycle log 最後時間戳 | 1kh-g |
| AlphaPaper9 | 就緒 | 週一～五 18:30 | `scripts/run_paper_9.py` | `research/data/paper_9_cycle.log`、`data/paper_9.json` | 該登記 | paper_9.json generated_at；`tw_trading_days_only` | 1kh-g |
| AlphaB25Control | 就緒 | 每日 00:30 | `research/b25_random_control_regime.py --max-minutes 300` | `research/data/b25_random_control/run.log` | 該登記（若已跑完應改標停用） | run.log；先確認這支是否已完成任務 | 1kh-g |
| AlphaMarketCatchup | 就緒 | 週一～五 17:30 | `scripts/market_local_catchup.py` | `research/market_local_catchup.jsonl`、`research/data/market_local_catchup_stdout.log` | 該登記 | catchup jsonl 最後一筆（只證明有觸發，不證明有補） | 1kh-g |
| AlphaMarketCatchupLate | 就緒 | 週一～五 19:30 | 同上 | 同上 | 該登記（可與上一支共用一條） | 同上 | 1kh-g |
| AlphaMarginCkCheck | 就緒 | 週一～五 19:30 | `scripts/margin_ck_check.py` | 包裝腳本沒寫 log 路徑——**待查** | 該登記（產出待查） | 看 margin_ck_check.py 寫什麼檔 | 1kh-g |
| AlphaTwDataCheck | 就緒 | 週一～五 20:30 | `scripts/check_tw_data_landed.py --layer local` | `research/tw_data_landed_check.log`（cmd `>>`，非 UTF-16） | 該登記 | log 最後時間戳 | 1kh-g |
| AlphaQuotesFallback | 就緒 | 週一～五 09:05 起每 10 分鐘 | `scripts/quotes_local_fallback.py` | `research/quotes_local_fallback.jsonl`、`data/quotes_tw.json` | 代管（AlphaQuotesTW 看 quotes_tw.json）＋1kh-e 提案 | 1kh-e 定案後一起處理 | 1kh-e |
| AlphaNewsFallback | 就緒 | 每 30 分鐘 | `scripts/news_local_fallback.py` | `research/news_local_fallback.log`、`data/news.json` | 代管（AlphaNewsEvents）＋1kh-e 提案 | 同上 | 1kh-e |
| AlphaAutoRun0905／AlphaAutoRun0940 | 就緒 | 週一～五 09:05／09:40 | `research/auto_rebalance_bb90.py`（真錢 Bb-90） | `research/data/auto_trading/scheduler.log`、`scripts/scheduler/publish_heartbeat.py` 心跳 | 該登記（只看有沒有跑） | scheduler.log／心跳檔；**不碰、不觸發下單程式** | 1kh-h |
| AlphaAutoSettle1340 | 就緒 | 週一～五 13:40 | 同上 settle | 同上 | 該登記（只看有沒有跑） | 同上 | 1kh-h |
| AlphaAutoWatchRun／AlphaAutoWatchSettle | 就緒 | 週一～五 09:55／14:00 | 同上 watchdog | 同上 | 該登記（只看有沒有跑） | 同上 | 1kh-h |
| AlphaIbkrGateway | 就緒 | 登入時＋每 15 分鐘 | `C:\alpha\run-ibkr-gateway-cycle.ps1` | `research/ibkr_gateway_cycle.log` | 部分代管（AlphaIbkrQuotes 已在亮燈：quotes_ibkr.json 停 17 天，總司令待辦第 3 項） | gateway cycle log | 1kh-h |
| AlphaNightlySix | 就緒 | 每日 02:00 起每 20 分鐘 | `research/nightly_six_runner.py` | `research/nightly6_task.log` | 該登記 | log | 1kh-h |
| AlphaOrphanScan | 就緒 | 每日 03:00 | `scripts/orphan_process_scan.py` | `research/orphan_scan.log` | 該登記 | log | 1kh-h |
| AlphaPhoneRegression | 就緒 | 每日 22:30 | `scripts/phone_regression.py` | 包裝腳本沒寫 log 路徑——**待查** | 該登記（產出待查） | 看 phone_regression.py 寫什麼檔 | 1kh-h |
| AlphaTelegram0815／AlphaTelegram2015 | 就緒 | 每日 08:15／20:15 | `research/telegram_reader.py` | `<outDir>\_runner.log`（路徑由腳本變數決定，待查） | 該登記（產出待查） | _runner.log | 1kh-h |
| AlphaWeeklyReport | 就緒 | 每週一 20:00 | `scripts/build_weekly_report.py` | `research/data/weekly_report_cycle.log`、`data/weekly_report.json` | 該登記 | weekly_report.json（interval 10080） | 1kh-h |
| AlphaCoworkInbox | **已停用** | 登入時 | `C:\alpha\cowork_inbox_watcher.ps1` | — | 不必登記（停用中；若恢復再登記） | — | — |

## 已知限制（照實寫）

- 「產出」欄是從包裝腳本 grep 出來的路徑，**沒有逐檔打開確認時間欄位**；登記時（1kh-g／1kh-h）才逐檔驗證。
- PowerShell `*>>` 寫的 log 是 UTF-16，`pipeline_freshness` 的 `log_last_timestamp` 解不出時間戳、會退回 mtime；
  有進 git 的 log（例：`research/tdcc_holders_cycle.log`）mtime 會被 checkout／pull 改寫，不能當判準（1kh-c 同一個坑）。
- 真錢相關（AlphaAuto*）只能看「有沒有跑」的痕跡，盤點與登記都不執行、不觸發下單程式。
