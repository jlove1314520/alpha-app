# 自動交易設定與開通（永豐 Shioaji，Bb-90：0050／00646／00697B）

> 2026-10-06 總司令裁示【先.二十九（修訂版）】。規則本體見 `CLAUDE.md` 第八節「自動交易規則」。
> 本文件分兩類：**已查證**（附官方來源，2026-10-06 擷取）與**未查證**（明確標示，以你實際看到的為準）。
> 憑證與密碼只放本機 `.env`，CC／Cowork 不得讀出、印出或 commit。

## 一、官方來源與查證結果

| 項目 | 官方說法（摘要） | 來源 |
|---|---|---|
| 正式下單前須簽署 API 服務條款 | 於簽署中心完成，**證券與期貨需各別簽署** | <https://sinotrade.github.io/zh/tutor/prepare/terms/> |
| 模擬測試 | 須在模擬模式通過「登入測試」與「下單測試」；時間限週一至週五 08:00～20:00（18:00～20:00 僅限台灣 IP）；版本需 ≥1.2；證券、期貨戶**各別測試**；下單測試間隔 1 秒以上 | 同上 |
| API 金鑰權限 | 使用的 API key 須已開通「交易」權限才能做下單測試 | 同上 |
| 憑證啟用 | API 簽署時間須早於 API 測試時間；通過測試後，登入正式環境看帳戶 `signed` 欄位確認 | 同上 |
| 模擬環境用法 | `sj.Shioaji(simulation=True)`，再 `api.login(api_key=..., secret_key=...)` | <https://sinotrade.github.io/zh/tutor/login/> |
| 模擬環境支援的 API | `place_order`、`update_order`、`cancel_order`、`update_status`、`list_trades`、`list_positions`、`list_profit_loss`、行情查詢 | <https://sinotrade.github.io/zh/tutor/simulation/> |
| **模擬環境限制** | 官方明載：**模擬環境下單不支援興櫃與零股**。因此模擬端到端只能用**整股（1 張=1000 股）** | 同上 |
| 下單參數 | `price_type`：`StockPriceType.LMT`（限價）／`MKT`；`order_type`：`ROD`／`IOC`／`FOK`；`order_lot`：`Common`（整股）／`Odd`（盤後零股）／`IntradayOdd`（盤中零股）／`Fixing`（定盤） | <https://sinotrade.github.io/zh/tutor/order/Stock/> |
| 上市／上櫃 | 官方文件涵蓋 TSE 與 OTC，兩者同樣的委託類型與條件。00697B 為上櫃 ETF，**文件層級支援**；實際可否成交以開通後正式環境為準（未實測） | 同上 |
| 持股查詢 | `api.list_positions(account, unit=Unit.Common｜Unit.Share)`；`Unit.Share` 可查零股；欄位含 `code`、`direction`、`quantity`、`price`、`last_price`、`pnl` | <https://sinotrade.github.io/zh/tutor/accounting/position/> |
| 帳戶餘額 | `api.account_balance()` 回傳 `AccountBalance(acc_balance, date, errmsg)`；官方說明僅支援永豐銀行／分戶帳／LINE Bank | <https://sinotrade.github.io/zh/tutor/accounting/account_balance/>（路徑為程式註解所載，**本輪未逐字重新核對**，以官網為準） |
| 台股交易日曆 | 證交所休市日表（官方 JSON，依年度查詢）：名稱為開始交易日／最後交易日的列為交易日，其餘列皆休市；週六日休市 | <https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear=2026> |

### 先.三十 新增設計與限制（`[自行裁量]` 處已標註）
- **INSUFFICIENT_CASH**：可用餘額須 ≥ 本批總金額 × 1.003，否則整批拒單、紅色橫幅、心跳 ERROR；查不到或逾時一律拒單（fail closed）。模擬模式用本機設定 `sim_cash_twd`（缺失即拒單），LIVE 類用 `account_balance()`＋執行緒逾時。**模擬環境是否支援 `account_balance()` 未驗證**（實測呼叫曾逾時無回應），所以模擬不依賴它。
- **T+2 限制（未驗證）**：餘額可能未扣除已成交尚未交割的款項；多日補單時現金可能被高估。`api.settlements()` 本輪未使用，列為待查。
- **日曆**：每年度快取在本機；抓取與快取都失敗 → 視為無法判斷，拒絕執行（fail closed）。**已發現本 repo 的 `TW_HOLIDAYS_2026`（index.html 約 2239 行）與 `scripts/expected_shift_calendar.py` 缺 2026-09-28（教師節）**，未於本輪修改，已列入回報。
- **推播**：repo 內查無任何手機推播機制（唯一前例為 2026-09-15 PROGRESS 的 iOS PWA Web Push 提案，從未核准）。本輪**不註冊任何外部服務**；否決窗期間以 App 橫幅與 `/auto/status` 呈現。提案見第七節。

### 未查證／需留意（不得當成事實）
- ETF 價格檔位（程式內採：價格 <50 為 0.01、≥50 為 0.05）**未逐字對照交易所公告**；若券商退單，以交易所公告為準修正 `tick_size()`。
- 零股限價單最小單位、盤中零股撮合時段、漲跌停以外的價格限制，**未逐條對照官方頁面**。
- 00697B 在正式環境的零股下單實測：**尚未做**（模擬不支援零股）。
- 永豐正式環境是否要求另行申請「零股下單」權限：**未查證**，請於簽署中心／營業員確認。

## 二、需要總司令本人完成的步驟（CC 與 Cowork 不得代做）

1. 於永豐簽署中心簽署**證券 API 服務條款**（證券與期貨各別，本專案只需證券）。
2. 於永豐 API 管理頁，確認你的 API key 已開通**「交易」權限**；金鑰與密鑰只寫進本機 `alpha-app/.env`（`SINOPAC_API_KEY`／`SINOPAC_SECRET_KEY`），不貼給任何人。
3. 在 08:00～20:00（週一至週五）親自跑一次官方要求的**模擬登入測試與模擬下單測試**（`simulation=True`），間隔 1 秒以上。
4. 通過後，登入正式環境確認帳戶 `signed` 為已啟用（若需 CA 憑證檔，憑證與密碼同樣只放本機，不進 repo）。
5. 向永豐確認是否需另開**零股下單**權限，以及 00697B（上櫃）零股可否下單。
6. 準備第一批資金，確認本機設定檔 `research/data/auto_trading/config.local.json` 內的金額上限（見下）。
7. **親手**把 `mode` 由 `SIMULATION` 改成 `LIVE_WITH_VETO`。這個動作只有你能做，CC／Cowork 不得改、不得在 LIVE 類模式下觸發任何真實下單測試。
8. 經你另行裁示後，才可把 `LIVE_WITH_VETO` 改為 `LIVE`（取消 30 分鐘否決窗）。

## 三、系統行為

- 程式：`research/auto_rebalance_bb90.py`；本機狀態目錄：`research/data/auto_trading/`（`.gitignore` 已涵蓋 `research/data/`，不進 repo）。
- 模式（由本機 `config.local.json` 決定，預設 `SIMULATION`；設定檔缺失或讀不懂一律視為 `SIMULATION`）：
  - `SIMULATION`：Shioaji 模擬環境（整股）。
  - `LIVE_WITH_VETO`：正式帳戶；下單前 30 分鐘先把待執行訂單寫出給 App，期間可「全部取消」，逾時才送單。
  - `LIVE`：正式帳戶，無否決窗（須總司令另行裁示）。
- 目標：0050 45%／00646 45%／00697B 10%。**新資金優先補低配、盡量不賣**（僅買入；偏離只靠新資金修正）。
- 硬限制（任一不符即拒單並通知）：白名單標的、僅現股（不含融資券／當沖）、單次金額上限、限價且偏離前收 ≤1%、資料新鮮度、下單前券商持股對帳、緊急停止旗標。
- 紀錄：~~`research/data/live_orders.jsonl`~~（⚠️ 2026-10-06 先.三十-一-1 起改為按模式族分檔，舊檔保留不再寫入）。
  - 模式族：`SIMULATION` 一套、`LIVE_WITH_VETO`／`LIVE` 共用一套（同一個真錢帳戶）。
  - 每族各自的帳本 `auto_trading/<族>/orders.jsonl`（append-only）、對帳快照 `auto_trading/<族>/state.json`、待執行訂單 `auto_trading/<族>/pending_orders.json`。
  - 共用：`config.local.json`、`STOP.flag`、`status.json`（App 讀）。
  - 冪等鍵＝「模式族＋月份＋批次＋標的」（例：`LIVE-202610-T1-0050`），重複執行略過不重複下單；模擬已成交的同月同批，切到 LIVE 類後真錢照常送單，對帳以真錢帳戶自己的快照為準。
- 對帳不符：寫 `last_error`、心跳 `ERROR`、App 紅色橫幅，並停止送單（失敗時 fail open 於**通知**，fail closed 於**送單**）。
- App：設定頁「自動交易」區塊顯示狀態、待執行訂單與「全部取消」按鈕，另有常駐「緊急停止」開關；兩者都只寫本機停止旗標，不具任何下單能力（走 `alpha_live_server.py` 的 `/auto/*`，需 `X-Alpha-Local-Token`）。

### 排程（先.三十-二，Windows 工作排程器，腳本在 `C:\alpha\`，不在本 repo）
| 工作 | 時間（週一至週五） | 指令 |
|---|---|---|
| AlphaAutoRun0905 | 09:05 | `--run` |
| AlphaAutoRun0940 | 09:40 | `--run`（否決窗到期送單） |
| AlphaAutoSettle1340 | 13:40 | `--settle` |
| AlphaAutoWatchRun | 09:55 | `--watchdog run`（09:30 後無心跳 → 紅色橫幅） |
| AlphaAutoWatchSettle | 14:00 | `--watchdog settle`（13:35 後無心跳 → 紅色橫幅） |

- 排程涵蓋所有平日，由程式自己判斷是否交易日與是否觸發（當月最後交易日；或 LIVE 類且第 1 批未執行；或有未完成批次）。未觸發記 `NOT_TRIGGERED` 心跳。
- 每次執行寫 `auto_trading/schedule_heartbeat.jsonl`；看門狗自身失敗一律 fail open（不告警、不中斷）。
- 狀態檔 `status.json` 新增 `next_tranche`、`deviation`、`drift_alert`；偏離目標 >5 個百分點只顯示，不自動賣出。
- 設定新增：`sim_cash_twd`（模擬資金，須夠買整張）、`monthly_contribution_twd`（第 4 批後常態月投入）。

## 四、分批進場（4 批各 25%）

1. 第 1 批：須同時滿足 ①PIT 快照回放流程檢查 PASS ②模擬環境端到端通過 ③總司令完成上列第 1～7 步並切換模式。
2. 第 2～4 批：之後每個月底自動執行（`tranche` 由本機設定檔遞增，上限 4）。
3. 本輪（先.二十九）**不執行任何真實下單**；第 1 批是否開跑，由總司令開通後決定。

## 五、本機設定檔範例（`config.local.json`，數字為示意，請自行填）

```json
{
  "mode": "SIMULATION",
  "tranche": 1,
  "tranche_total": 4,
  "total_capital_twd": 0,
  "per_order_cap_twd": 0,
  "max_price_dev_pct": 1.0,
  "max_data_age_days": 4
}
```

`total_capital_twd` 為 4 批合計規劃資金，每批用其 25%；`per_order_cap_twd` 為單筆委託金額上限。為 0 或缺失時程式一律拒單。

## 六、驗證紀錄（2026-10-06）

- 自測：`scripts/selftest_auto_rebalance.py` 29 項全 PASS（每條硬限制各一則拒單、價格缺失、資料過期、持股對不上、停止旗標、重跑不重複下單）。
- PIT 回放流程檢查：`scripts/pit_replay_auto_rebalance.py` → `research/PIT_REPLAY_AUTO_REBALANCE.md`，五個月底全 PASS（只檢流程，無淨值／報酬）。
- Shioaji 模擬環境端到端（完整月底流程，整股）：15:12（收盤後）送出 0050 3 張、00646 5 張、00697B 2 張限價買單，三筆皆被模擬環境接受，帳本寫入 SUBMITTED 與 OPEN（券商狀態 PreSubmitted，因收盤後未成交），status 無錯誤。**誠實揭露：未取得成交回報**（收盤後排隊）；之後手動撤銷三筆並於帳本記 CANCELLED，模擬持股回到空。盤中成交路徑與零股、00697B 正式環境零股下單**尚未實測**。
- 自動交易 App 區塊：本機 `/auto/status`（GET）與 `/auto/stop`（POST）只讀寫狀態與 STOP.flag，不具下單能力。

### 先.三十 自測與 10/7 盤中模擬（待填）
- 自測：`scripts/selftest_auto_rebalance.py` 76 項全 PASS（拆單、晚成交結算、EXPIRED／R2 重排、PARTIAL、INSUFFICIENT_CASH 各情境、期數 T1→T2→M、偏離告警、日曆、觸發條件、看門狗）。**誠實揭露：測試是實作之後才寫的**，對象為假券商，`ShioajiBroker` 的狀態回補路徑未對真券商驗證。
- 2026-10-07 09:00–13:30 盤中模擬端到端紀錄：（待 10/7 執行後填入；須取得實際成交，否則如實寫「未取得成交」）。

## 七、否決窗手機推播提案（未核准，未註冊任何外部服務）
- 現況：repo 無推播機制。
- 方案 A：iOS PWA Web Push（自架 VAPID；需 iOS 16.4+ 且 PWA 加到主畫面；零第三方帳號，但需本機長駐推送程式與公網可達的訂閱端點）。
- 方案 B：Firebase Cloud Messaging（需 Google 帳號與專案，金鑰進本機）。
- 方案 C：OneSignal 等託管服務（最省事，但訂單摘要會經第三方）。
- 建議：先 A；任何一案都屬註冊外部服務，需總司令裁示。過渡期以 App 橫幅與 `/auto/status` 為準。
