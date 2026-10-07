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

### 先.三十八：掛單＋撤單串接（2026-10-06）
- **緊急停止會撤單**：停止旗標生效時，下一次 `--run`／`--settle` 先撤掉「本系統帳本內」尚未終結的委託（只照帳本的委託編號撤，不碰帳戶裡其他委託），帳本記 `CANCELLED`；撤單失敗→ERROR＋紅色橫幅＋推播，請立即到券商 App 人工確認。
- **模擬環境驗證**：`python research/auto_rebalance_bb90.py --sim-cancel-test`（0050 限價買 1 張，限價＝前收×0.95；掛單→查詢→撤單→確認 Cancelled）。結果只寫 `research/data/auto_trading_drill/cancel_test.jsonl`，不動正式帳本。2026-10-06 22:40 實測：PreSubmitted→Cancelled、成交 0，PASS（模擬環境當晚仍可下單）。
- **真錢掛單＋撤單測試（只能由總司令本人執行，CC／Cowork 不得執行）**：
  1. 先確認自檢顯示「正式環境權限：已生效」（`--preflight`）。沒生效時本指令會直接拒絕。
  2. 在電腦開 PowerShell，貼上（此為完整指令，勿修改）：
     `cd C:\alpha\alpha-app; C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe -X utf8 research\auto_rebalance_bb90.py --live-cancel-test`
  3. 畫面會顯示即將送出的內容（0050 盤中零股買 1 股、限價＝前收×0.95，預期不會成交），要求完整輸入確認字串「我確認以真錢帳戶掛0050零股1股並立即撤單」；不符就取消、不送單。
  4. 送出後約 1 秒撤單，再查詢確認 Cancelled；結果寫入 LIVE 帳本（SUBMITTED→CANCELLED）、App 狀態並推播。
  5. 盤中零股只在盤中時段撮合，建議台股交易時間執行。
  - 防呆：不受設定檔模式影響；非互動終端機（排程、自動化）或排程環境變數 `ALPHA_SCHEDULED_TASK` 存在時一律拒絕。**以上步驟依程式寫法整理，真錢環境尚未實際執行過，以你看到的畫面為準。**
- Shioaji 預設委託回呼會把含帳號的委託內容印到畫面／排程 log，已在 ShioajiBroker 關閉（狀態一律主動查詢）。

### 先.三十三：上線前自檢與真錢帳戶卡（2026-10-06）
- `python research/auto_rebalance_bb90.py --preflight`：逐項 PASS／FAIL＋缺什麼，結果寫本機 `status.json` 的 `preflight`，App 自動交易卡「上線前自檢」顯示。只查詢、**絕不送單**：正式環境只 `login`、不 `activate_ca`（沒有 CA 就不可能送出委託），結束即 `logout`；說明文字不含金額、持股數、帳號或金鑰值。
- 2026-10-06 19:39 首跑：PASS 5／FAIL 7。正式環境登入被拒（永豐回應 `Token doesn't have production permission`：目前金鑰只有模擬權限，需完成簽署與模擬測試報告後由永豐開通）；推播 0 支；`data/ex_dividend_events.json` 不含三檔白名單的除息事件。
- 先.三十四-二（同日 20:xx）：除息項改判「新鮮（72 小時，同 generate_status_json.py）＋來源涵蓋 ETF」，白名單三檔無事件判 PASS 附註「近期無除息公告」；引擎的除息拒單規則不變。重跑結果 PASS 6／FAIL 6。
- App「真錢帳戶」卡：`/auto/status` 的 `live_account`（LIVE 族帳本＋對帳基準，只在本機）。損益只算自動交易買進的股數；對照組＝每筆成交改成同金額、同日收盤買 0050；未計手續費與稅。無 LIVE 成交時顯示空狀態。

### 先.三十二：模擬否決窗演練設定（2026-10-06 新增，僅 SIMULATION 有效）

| 設定鍵 | 預設 | 作用 | LIVE 類影響 |
|---|---|---|---|
| `sim_veto` | `false`（未設定即 false；必須恰為 JSON `true` 才生效，字串 `"true"` 不算） | 模擬批次也走 30 分鐘否決窗＋否決窗開始推播；推播送不到同樣整批不執行（fail closed） | 無：`LIVE_WITH_VETO` 一律走否決窗、`LIVE` 一律不走，與本鍵無關（`sim_veto_on()`，自測有對應案例） |
| `sim_drill_date` | 無 | 指定日期（`YYYY-MM-DD`）讓排程的 `--run` 在非月底也觸發一次（觸發原因 `sim_drill`） | 無：`should_run()` 只在 mode=SIMULATION 時看這個鍵 |

- 演練 B（取消）用 `python research/auto_rebalance_bb90.py --run --drill-label DRILLB`：以獨立批次名（`SIMULATION-<年月>-DRILLB-R1`）建立待執行訂單，**不動** state 的批次／`last_done`／期數；取消走 App「全部取消」同一條本機 API（`POST /auto/stop {"stop":true}` 寫 `STOP.flag`）。否決窗到期後再跑同一指令，走正式的停止旗標路徑（逐筆 `REJECT STOP_FLAG`、pending 標 `cancelled`）。萬一到期仍未取消，程式判演練失敗（`DRILL_NOT_CANCELLED`）且**絕不送單**。
- `--drill-label` 只接受 `DRILL` 開頭大寫英數、必須 `sim_veto: true` 且設定檔 mode 為 SIMULATION，否則拒絕。演練心跳記 `task=drill`，不寫進公開心跳 `data/auto_heartbeat.json`、也不滿足看門狗，避免與排程實證混淆。
- 演練結束後：清除停止旗標（App 再按一次或 `POST /auto/stop {"stop":false}`），並把 `sim_drill_date` 移除或留著（過了那天就不再觸發）。

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
- 自測：`scripts/selftest_auto_rebalance.py` 91 項全 PASS（先.三十一-三／四／六 後；原 76 項）（拆單、晚成交結算、EXPIRED／R2 重排、PARTIAL、INSUFFICIENT_CASH 各情境、期數 T1→T2→M、偏離告警、日曆、觸發條件、看門狗）。**誠實揭露：測試是實作之後才寫的**，對象為假券商，`ShioajiBroker` 的狀態回補路徑未對真券商驗證。
- 2026-10-07 09:00–13:30 盤中模擬端到端紀錄：（待 10/7 執行後填入；須取得實際成交，否則如實寫「未取得成交」）。
- 先.三十二 前置（2026-10-06 晚）：自測 131 項全 PASS（新增 sim_veto／演練日／演練 B 共 19 項）；休市表比對在無網路且無快取時改印 SKIP＋警告（交易流程本身仍是抓不到日曆一律不動作，未放寬）。排程器內 WindowsApps `python.exe` 實測可用：臨時一次性排程（同樣 Interactive 登入類型）以該路徑 import shioaji 1.7.4 成功，故**不改路徑**；臨時排程已刪除，未手動觸發任何交易排程。

### 先.三十一-三／四：限價基準與交割款（2026-10-06）
- **限價基準**：改用 Shioaji 合約 `reference`（平盤參考價）與 `update_date`，來源 <https://sinotrade.github.io/zh/tutor/contract/>。**文件只說 reference 是參考價，沒有寫是否含除息調整**，所以不單信它：每次送單前與 `price_history.json` 昨收交叉核對，差距 >1% 時，只有 `data/ex_dividend_events.json` 登記當日除息、且價差不超過「現金股利／昨收＋1%」才放行，其餘整批拒單並報錯。`update_date` 不是今天、昨收過期、缺值同樣整批拒單。
- 實測（2026-10-06 模擬環境）：三檔 reference 等於前一日收盤、update_date 為當日，與昨收核對通過。**已知缺口**：`ex_dividend_events.json` 目前沒有 0050／00646／00697B 的事件（ETF 未收錄），所以除息豁免實際上不會觸發；遇到 ETF 除息日會整批拒單（安全方向，需人工處理），要補事件才會放行。
- **交割款**：可用餘額扣掉 `api.settlements()` 回傳各列 `amount` 的絕對值總和後，才與整批所需金額比較；查詢逾時或失敗一律拒單。來源 <https://sinotrade.github.io/zh/tutor/accounting/settlements/>。**文件只列欄位（date／amount／T），未說明 amount 正負號與 T 涵蓋範圍**，因此採保守的絕對值加總（寧可多扣）。模擬環境 settlements 回空清單，**含未交割款的真實資料行為尚未實測**。
- 模擬環境 `account_balance()` 可用（回傳成功）；模擬模式的現金仍取設定檔 `sim_cash_twd`，不依賴它。
- **正式環境唯讀檢查：未能完成**。以目前 .env 的金鑰登入正式環境，券商回覆 400「Token doesn't have production permission」，即金鑰尚無正式環境權限（依永豐流程需完成 API 測試簽署後開通，細節以券商說明為準）。因此 `account_balance`／`settlements` 在正式帳戶的欄位與行為**未驗證**；開通後須重做一次唯讀檢查（只確認欄位存在，不寫金額）。

## 七、否決窗手機推播提案（未核准，未註冊任何外部服務）
- 現況：repo 無推播機制。
- 方案 A：iOS PWA Web Push（自架 VAPID；需 iOS 16.4+ 且 PWA 加到主畫面；零第三方帳號，但需本機長駐推送程式與公網可達的訂閱端點）。
- 方案 B：Firebase Cloud Messaging（需 Google 帳號與專案，金鑰進本機）。
- 方案 C：OneSignal 等託管服務（最省事，但訂單摘要會經第三方）。
- 建議：先 A；任何一案都屬註冊外部服務，需總司令裁示。過渡期以 App 橫幅與 `/auto/status` 為準。

## 八、手機推播開通步驟（先.三十一-一，方案 A：標準 Web Push＋VAPID，不註冊任何第三方帳號）

> 狀態：程式與自測已完成（selftest_web_push 17 項、selftest_auto_rebalance 含推播接線 12 項）。
> **尚未在總司令的 iPhone 實機驗證**——以下步驟是依 Apple 官方「iOS 16.4 起，加到主畫面的網頁 App 才能收 Web Push」的說法整理，
> 「沒有親眼看到的畫面」，實際按鈕位置請以你手機上看到的為準。

**事前條件**：iPhone 為 iOS 16.4 以上；本機 `.env` 已有 VAPID 金鑰（已產生，`python research/web_push.py --status` 顯示 `vapid_ready: true`）；本機服務（alpha_live_server）在跑。

1. 用 Safari 開 https://jlove1314520.github.io/alpha-app/ 。
2. 點 Safari 下方分享按鈕 → 「加入主畫面」→ 確認。**一定要從主畫面圖示開啟**，在 Safari 分頁裡開不會有推播權限。
3. 從主畫面開啟 Alpha → 設定 → 自動交易卡 → 按「開啟本裝置推播」→ 系統問是否允許通知時選「允許」。
4. 按「測試推播」。手機應收到「Alpha 測試推播」。收不到：確認 iPhone 沒開專注模式、設定 → 通知 → Alpha 為開啟。
5. 否決窗推播收不到時，系統**不會執行該批**（fail closed）：App 出現紅色橫幅、下次排程重試。

**推播事件**：否決窗開始（標的／股數／限價／總額／排定送出時間／取消方式）、整批拒單或 ERROR、排程漏跑、批次完成。
**失敗處理**：只有「否決窗開始」推播送不出去才會擋單；其餘推播失敗只降級成警告。
**隱私**：VAPID 私鑰只在本機 `.env`；推播內容不經任何第三方帳號，但會經 Apple 推播服務（內容端對端加密，Apple 看不到明文）；`push_log.jsonl` 只記類別與成功／失敗數。

## 九、真錢第 1 批上線清單（先.四十四，2026-10-07 19:2x）

> 本節依程式碼與 2026-10-07 實測整理。**切換模式由總司令本人修改本機設定檔**；CC／Cowork 不得把模式改成 LIVE 類，也不建議任何金額。

### 1. 上線前驗證結果

| 項目 | 結果 | 證據 |
|---|---|---|
| `--preflight`（19:2x，含 CA） | **PASS 17／FAIL 0**，`go_live_ready=true` | 本機 `status.json` 的 `preflight` |
| 正式環境權限 | 18:56 起生效（08:30、14:00 兩次排程自檢仍被拒「Token doesn't have production permission」） | `scheduler.log`、`status.json.live_permission` |
| CA 憑證 | 啟用成功，到期日 2028-09-01（剩 695 天）；只驗證，未送任何委託 | 自檢 `ca` 項 |
| 排程實證（先.三十二-一） | 10/7 09:05 WAITING_VETO、09:40 OK、13:40 settle OK，皆由工作排程器觸發 | `data/auto_heartbeat.json`、`schedule_heartbeat.jsonl` |
| 演練 A（模擬，不取消） | 09:05 建單＋推播送達 → 09:40 送 3 筆：0050 3,000 股與 00697B 2,000 股當場成交，00646 5,000 股盤中未成交、13:40 結算查得成交 → 對帳通過、批次完成推播送達 | 模擬帳本 `SIMULATION/orders.jsonl` |
| 演練 B（模擬，只取消本批） | 18:44 建單＋推播 → 經 `/auto/cancel_pending` 取消 → 19:14 到期逐筆 CANCELLED、送出 0 張、停止旗標未開 | 同上 |
| 演練設定清理 | `sim_drill_date` 已移除；`sim_veto` 保留（只影響 SIMULATION）；10/8 SIMULATION `should_run`＝不觸發 | 本機設定檔 |
| 身分證外洩修補 | 發現 Shioaji 預設事件訊息含身分證字號、09:05 曾寫入本機 `scheduler.log`；已關閉事件輸出、啟動器寫 log 前再遮蔽，既有 3 個本機檔已遮蔽（皆不在 repo） | 先.四十四 commit |

### 2. 總司令要親手修改的設定（本機 `research/data/auto_trading/config.local.json`）

| 欄位 | 改成 | 說明 |
|---|---|---|
| `mode` | `"LIVE_WITH_VETO"` | 真錢＋30 分鐘否決窗。**不要改成 `"LIVE"`**（無否決窗，需另行裁示） |
| `total_capital_twd` | 由總司令自填 | 4 批合計規劃資金，每批用 1/4；CC 不建議金額 |
| `per_order_cap_twd` | 由總司令自填 | 單筆委託上限；須 ≥ 單批最大一筆（改完重跑 `--preflight`，「設定合理」項會檢查） |
| `tranche` | 維持 `1` | 第 1 批 |

改完後建議再跑一次：`C:\Users\user\AppData\Local\Microsoft\WindowsApps\python.exe -X utf8 research\auto_rebalance_bb90.py --preflight`（在 `C:\alpha\alpha-app` 執行），確認仍全部 PASS。

### 3. 切換後 10/8（交易日）的預期時程（依程式寫法，真錢尚未實際跑過）

1. **09:05** 排程觸發（觸發原因 `first_tranche`）：查券商持股與現金（含扣未交割款）、取平盤參考價並與昨收交叉核對、依 45／45／10 規劃買單（真錢可含盤中零股），建立待執行訂單並推播「無需操作，09:35 將自動送出；如要取消可按全部取消」。
2. **09:35** 否決窗結束；**09:40** 排程送出限價買單（限價不超過參考價 +0.5%），送出後短暫查詢成交。
3. **13:40** 盤後結算：依券商回報記 FILLED／PARTIAL／EXPIRED，與券商持股對帳，全部成交則推播「批次完成」；未成交餘量下一個交易日以新編號（R2）補單。
4. **09:55／14:00** 看門狗：當日沒有對應心跳就紅色橫幅＋推播。

### 4. 任一步失敗時系統的自動行為（無需總司令操作）

| 情況 | 系統行為 |
|---|---|
| 否決窗推播送不出去 | 該批不執行（fail closed）、紅色橫幅、下次排程重試 |
| 現金不足／餘額或未交割款查不到 | 整批拒單、紅色橫幅、推播 |
| 參考價缺失、非今日、與昨收差 >1% 且非除息日 | 整批拒單、紅色橫幅、推播 |
| 任一硬限制不符（白名單、僅買進、現股、單筆上限、價格偏離、資料過期） | 該筆拒單並記錄原因 |
| 持股對帳不符 | ERROR、紅色橫幅、推播，不送新單 |
| 前一交易日有未結算委託 | 先自動結算，仍未結算就不送新單 |
| 排程未執行（關機／離線） | 看門狗紅色橫幅＋推播；App 讀公開心跳顯示「排程未執行」 |
| 你按「全部取消」 | 只取消這一批、記 CANCELLED、不送單；之後批次照常 |
| 你打開「緊急停止」 | 之後所有批次拒單；已送出未成交的本系統委託在下次執行時自動撤單 |

### 5. 誠實揭露：真錢路徑尚未實測的部分

- **盤中零股**：模擬環境只下整股；真錢規劃會把不足一張的部分拆成盤中零股，這條路徑沒有實際下過單。
- **帳戶既有持股**：真錢第一次執行會以券商現有持股為對帳基準，規劃時把既有的 0050／00646／00697B 也算進 45／45／10 配比（只買不賣）。
- **真錢掛單＋撤單測試**（`--live-cancel-test`）尚未執行，需由總司令本人在電腦上跑（見先.三十八節）。

## 十、Shioaji 版本查證（先.四十六-補 四，2026-10-08，只回報、未升級）

目前安裝 1.7.4。來源：官方 release 頁（https://sinotrade.github.io/release/ 、/zh/release/）、PyPI 版本頁與 JSON（含撤回狀態）、GitHub Sinotrade/Shioaji releases 與 2026-08-20 後的 issue；三者內容吻合。

| 版本 | 發布 | 重點 | 下單 | 帳務 | CA | 登入 |
|---|---|---|---|---|---|---|
| 1.7.5 | 2026-09-10 | VIX 報價、HTTP 監控 API、權證報價修正 | 無 | 無 | 無 | 未列變更 |
| 1.7.6 | 2026-09-22（**已被官方撤回**） | 委託／成交回報自動更新 Trade 快取、回報加 event_id、模擬環境多連線回報 | **有**（快取行為改變） | 無 | 無 | **有缺陷**：未簽 API 條款帳戶快取登入失敗；快取登入誤標成交回報訂閱 |
| 1.7.7 | 2026-09-29（最新） | 修正 1.7.6 兩個登入問題 | 有（沿用 1.7.6 新行為） | 無 | 無 | 修正 |

- 1.7.4 是否受 1.7.6 問題影響：官方未直接說明；兩個問題與 1.7.6 新增的回報快取直接相關、官方只撤回 1.7.6，研判 1.7.4 不受影響（推論）。
- 跨版本未解問題：GitHub #237 回報 Windows 上 `api.login()` 可能卡死在原生程式（1.7.0、1.7.5 皆有回報，官方未回覆）；本專案自檢登入已包逾時。
- 建議（待總司令裁示）：非交易時段另案由 1.7.4 直接升 1.7.7（**不得裝 1.7.6**），升級前在模擬環境驗證：首次與快取登入、signed、activate_ca／到期日、整股與零股 place→update_status→cancel、order callback 與 event_id、帳務三查詢欄位、登入逾時；退回指令 `pip install shioaji==1.7.4`。`auto_rebalance_bb90.py` 主動 update_status、不依賴回呼，理論上不受新快取行為影響，仍須實測。

## 十一、永豐 TG 群組實戰回饋修補（先.五十，2026-10-08）

- **⚠️ 更正：模擬環境不支援零股下單**（群組 #83956 #84243 #84559：模擬不支援零股、零股庫存放大 1000 倍）。**所有模擬演練的零股成交結果一律無效**；本專案模擬模式原本就只下整股（`odd_ok = mode != "SIMULATION"`），10/7 演練 A／B 帳本中沒有任何零股委託。程式另加保險：模擬族帳本若出現零股紀錄，一律標 `validation=SIM_ODD_UNSUPPORTED`、不計入驗證通過。**盤中零股的第一次真實驗證就是 10/8 真錢第 1 批**，13:40 結算（或已全數成交時的 13:40 排程）會產生「零股首次真實驗證」報告：逐筆零股委託量、成交量、均價，並以送單前持股（`pre_batch_positions`，unit=Share）對照結算後持股差，逐檔比對，寫本機 `LIVE/odd_lot_verification_YYYYMMDD.json` 並推播。
- **連線**：`ShioajiBroker.close()` 登出；run／settle／撤單測試／零股驗證都以 finally 關閉；`--preflight` 新增「連線預算」（本機登入中的 Shioaji 程式＋本次 ≥5 條即 FAIL；同一身分證最多 5 條，群組 #81524 #84357）。
- **計價**：下單一律以合約 `reference`（平盤參考價）±0.5% 對齊檔位，全 repo 下單路徑不得使用 `limit_up`／`limit_down`（自測涵蓋 00697B 漲跌停 9999.95／0.01 情境）。
- **可用額度交叉參考**：08:30–15:00 唯讀查 `trading_limits().trading_available`，與「餘額−未交割應付」差 >5% 只記警告（status `cash_crosscheck`），不改變擋單規則。

### 先.四十九 升級檢查清單補充（先.五十-7）
8. **OrderEventDict 唯讀**：1.7 起委託回報是唯讀的 OrderEventDict，程式不得以 `isinstance(msg, dict)` 判斷、不得寫入 msg、不得用 `msg.dict`（群組 #84781 #80952）。本專案已關閉回呼、改主動查詢，升級後仍需 grep 確認。
9. **login 參數**：1.7 已移除 `contracts_cb`／`contracts_timeout`／`fetch_contract`，所有 `login()` 呼叫不得帶這三個參數（群組 #81680）。
10. **長駐行情程式**：加 `faulthandler`（原生崩潰時留下堆疊），崩潰後由排程自動重啟（1.7.6／1.7.7 有長時間執行崩潰回報，群組 #84933 #84934）。
