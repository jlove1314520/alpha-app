# STATUS.json known_limitations 封存（先.一三五-1kh-l2）

- 2026-11-05 DevQueue 20261105-120102（維運帽）依提案 `docs/PROPOSAL_STATUS_JSON_SLIM.md` 甲（收件匣 039 已定案丙＝甲＋乙，乙已於 20261105-043102 做完）搬出。
- 判準 [自行裁量]：該條在 `generate_status_json.py` 的最後改寫日（`git log -S` 取該條末 40 字查最新一次 commit）早於 2026-10-06（＝30 天前）。
- 以下為**原文**，一字未改；內容是寫入當時的狀態，可能已過時（例：FinMind 依賴後來陸續拔除），以 `data/STATUS.json` 與各資料檔為準。
- `data/STATUS.json` 的 `known_limitations` 只留近 30 天條目，另有 `known_limitations_archive` 指向本檔。

## 1. （原第 0 條；最後改寫 2026-08-27 0a6402d3ac6）

【策略層面，最重要】2026-08-27新增題材動能榜（scores_momentum.json）+未來性濾網（scores_future.json），跟價值成長榜（scores.json）三榜並列——三榜都尚未經過組合策略回測驗證，App固定顯示「本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤」，見TODO的B16項目。權重是專家判斷的初始設計值（weights_frozen_momentum.json/weights_frozen_future.json），不是回測最佳化結果。

## 2. （原第 1 條；最後改寫 2026-08-27 aa4a6c51609）

2026-08-27修正P0 bug（使用者回報）：題材動能榜relative_strength因子改用還原權息收盤價（price_history.json新增adj_close欄位）——來源雙軌：一次性回補讀research端FinMind TaiwanStockDividend本機快取（research/build_price_history.py），之後每日排程改讀TWSE官方rwd/zh/exRight/TWT48U除權息預告表累積事件、回溯調整（.github/scripts/update_price_history.py，見data/ex_dividend_events.json）——刻意不在每日排程呼叫FinMind，維持JSON-only架構原則。已知殘留限制：(1)TWT48U只回傳未來約5週的事件預告，不支援歷史查詢，故涵蓋率隨每天累積逐步提高，剛上線這幾週少數個股可能還沒回溯到；(2)實測發現少數股票(如2420/2227/6216/8442等8檔)的research端FinMind快取已經停在很久以前(2024-12-31)，導致「除權息日前一筆可用資料」距離超過10天，判定無法安全定錨調整係數，這類事件會被跳過(adj_close退回等於close，不會比修正前更差)並記錄skip_reason，不會靜默套用錯誤係數。

## 3. （原第 2 條；最後改寫 2026-08-27 e08cdb21028）

margin_maintenance.json：分母（全市場融資金額）2026-09-15起改用TWSE官方www.twse.com.tw/rwd信用交易統計端點（同T86網站家族），拔掉最後一個FinMind依賴；單日查無資料時往回找最多5天取最新可用值，若5天內都失敗才明確寫入data_incomplete=true，App顯示「資料不完整」，不會沿用舊值假裝正常。

## 4. （原第 4 條；最後改寫 2026-08-27 e08cdb21028）

quotes_tw.json：自選股sparkline約24檔上櫃(TPEx)股票查不到（TWSE STOCK_DAY端點是TWSE專屬）。

## 5. （原第 7 條；最後改寫 2026-08-27 e08cdb21028）

2026-08-27發現：這台機器目前曾被FinMind IP封鎖過（非單純額度用盡），research/finmind_client.py原本完全沒有請求節流——已加上每次真正網路請求間至少0.35秒的節流，但這只能降低未來再次觸發封鎖的機率，無法解除已經發生的封鎖，也不是精確調校過的數字。

## 6. （原第 8 條；最後改寫 2026-08-27 44a5b3b8478）

scores.json（選股頁分數）2026-08-27新增GitHub Actions每日排程（research/generate_scores_live.py，market.yml），只讀repo內JSON、不依賴parquet/FinMind，不會再因為研究者本機沒開機而停擺——但這條JSON-only路徑覆蓋率上限約0.74（technical/analyst/catalyst三項恆缺），跟研究端手動執行（research/generate_scores_v2.py，因子較完整）互不覆蓋衝突，用meta.engine_version分辨這次是哪條管線產生的。

## 7. （原第 9 條；最後改寫 2026-08-27 7b4fe7d327c）

本檔案（STATUS.json）由generate_status_json.py產生，APP_DATA_SOURCES那份面板對照表是人工核對、不是自動掃描——異動面板資料源時要記得同步更新腳本裡的常數，否則這份清單會跟實際程式碼不同步。

## 8. （原第 10 條；最後改寫 2026-08-27 f8fc74ae754）

earnings_calendar.json：yfinance get_calendar()（下一次財報日期）穩定可用，但get_earnings_dates()（用來推估盤前/盤後公布時段）在這台機器持續遇到curl_cffi對guce.yahoo.com的DNS解析失敗（socket.gethostbyname()本身正常，是curl_cffi內部的環境特定問題，不是程式bug）——estimated_session因此誠實降級為'unknown'，不影響next_earnings_date本身的可靠性；GitHub Actions runner環境不一定有同樣的DNS問題，之後排程實跑可能就會恢復正常。
