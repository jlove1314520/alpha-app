# 排程第二批改「不論登入與否都執行」：清單與切換步驟（先.一〇二-2b／先.一一九-4）

> 2026-10-20 互動視窗整理。**密碼只由總司令本人在 Windows 跳出的認證視窗輸入；CC 不讀、不記錄、不索取。**
> 第一批（先.一〇二-2a，10/15 22:40 改完）：AlphaMarketCatchup、AlphaMarketCatchupLate、AlphaData、AlphaQuotesFallback、AlphaWarrantSnapshot、AlphaDevQueue。

## 一、第一批三個交易日觀察結果

核對工具：`python scripts/check_password_batch1.py 2026-10-16 2026-10-19 2026-10-20`（只讀；看排程器上次結果、心跳／日誌、當天資料落地）。

| 排程 | 10/16 | 10/19 | 10/20 |
|---|---|---|---|
| AlphaMarketCatchup（17:30） | OK：當天 market_tw 落地 | OK：當天 market_tw 落地 | （收盤後補） |
| AlphaMarketCatchupLate（19:30） | OK（融資維持率缺，見下） | OK（同左） | （收盤後補） |
| AlphaData（15:30） | OK（FinMind 融資金額 402 一處，次日恢復） | OK | （收盤後補） |
| AlphaQuotesFallback（盤中每 10 分鐘） | OK：29 筆 | OK：29 筆 | （收盤後補） |
| AlphaWarrantSnapshot（17:30） | **快照缺**：櫃買 16MB 檔下載到一半被對方切斷連線（ConnectionReset），程式 exit=1 | OK | （收盤後補） |
| AlphaDevQueue（每 30 分鐘） | OK（1 輪用量上限） | 排程照常每 30 分鐘啟動；04:14 起 39 輪是 **claude 每週用量上限**（429 usage_limit_reached，10/20 04:00 重置後恢復） | （收盤後補） |

判讀：6 支排程在「存密碼身分」下**每次都有被叫起來、都跑到自己的程式**；看到的三個問題（櫃買連線中斷、FinMind 402、claude 每週用量上限）都是**資料源或額度**，跟登入身分無關，回到互動身分也一樣會發生。
- 10/16 權證快照：官方端點只給當天，**補不回來**，照實記缺一天。
- `margin_maintenance` 每天 19:30 仍標缺：這是既有的資料殘缺（雲端融資維持率），不是本批造成。

## 二、第二批清單（目前 Interactive 30 支，建議分三組）

**A 組：純資料／研究（20 支，建議第二批一次改）**
AlphaB25Control、AlphaDataAudit、AlphaDepCheck、AlphaDisposalFlags、AlphaFinMindWarmup、AlphaHypothesisQueue、AlphaMarathon、
AlphaMarginCkCheck、AlphaMoeaPitSnapshot、AlphaNewsFallback、AlphaNightlySix、AlphaOrphanScan、AlphaPaperSupplyV2、AlphaPhoneRegression、
AlphaRfMonthly、AlphaTdccHolders、AlphaTwDataCheck、AlphaWeeklyReport、AlphaTelegram0815、AlphaTelegram2015

**B 組：常駐服務／盤中報價（3 支，可跟 A 組同批，但改完要照 CLAUDE.md 七之二節四步驗證）**
AlphaLiveServer、AlphaShioajiQuotes、AlphaIbkrQuotes

**C 組：真錢自動投資（5 支，建議單獨第三批，A＋B 觀察 3 個交易日後再改）**
AlphaAutoRun0905、AlphaAutoRun0940、AlphaAutoSettle1340、AlphaAutoWatchRun、AlphaAutoWatchSettle
——自動投資目前是「已暫停：等紙上策略打贏 0050」；改完只用 `--preflight`（唯讀、不送單）驗證，**不做任何真實下單測試**。

**不改、維持「只在登入時執行」（1 支）**：AlphaIbkrGateway——它是開 IBKR Gateway 的**視窗程式**，每週日還要人工登入一次；
改成不登入也執行會在看不到的背景桌面開一個沒人能登入的視窗，反而更糟。

（AlphaConnectivity、AlphaTwsePublishProbe 已是 S4U，不需要密碼、也不 push，不動。）

## 三、切換前要先做的事（CC 做，不需要密碼）

1. **啟動檔改用 `C:\Program Files\Python313\python.exe`**：實際寫死 Store 版 python（`...\WindowsApps\python.exe`）的啟動檔是 **11 支**（不是 9 支；`run_warrant_snapshot.ps1` 第一批時已改、只剩註解）：
   - `C:\alpha\`：run-alpha-live-server-cycle.ps1、run-auto-trading-cycle.ps1、run-ibkr-quotes-cycle.ps1、run-shioaji-quotes-cycle.ps1、run-telegram-reader.ps1（不在 repo，改前各留 `.bak_20261020`）
   - `alpha-app/scripts/`：run_disposal_flags.ps1、run_finmind_warmup.ps1、run_paper_supply_v2.ps1、run_rf_monthly.ps1、run_snapshot_moea_pit.ps1、run_weekly_report.ps1（另 run_supply_watchlist.ps1 目前沒有排程在用，一併改）
   - 工作本身寫「python」（沒寫完整路徑）的 3 支（AlphaData、AlphaDataAudit、AlphaTdccHolders）：這台 `where python` 第一個是 `C:\Program Files\Python313\python.exe`（系統 PATH 在使用者 PATH 前面），
     第一批 AlphaData 已在存密碼身分下實跑正常，不用改。
   - 理由：第一批 10/15 實測，Store 版 python 在「不登入」身分下**輸出全空、但結束碼仍是 0**（看起來成功、其實沒跑）。
2. **兩個 python 的套件比對（10/20 實測）**：shioaji 1.7.4、ib_async 2.1.0、fastapi、uvicorn、requests、pandas、numpy、pyarrow 版本完全相同；
   **唯一缺的是 `telethon`**（Telegram 讀取器用，Store 版 1.45.0）→ 先 `"C:\Program Files\Python313\python.exe" -m pip install --user telethon==1.45.0`。
   掃描方式：從 11 支啟動檔實際執行的 Python 程式出發，遞迴找 repo 內 import，逐一在 Program Files 版檢查（37 個檔），只有 telethon 找不到。
3. **改完先在現在的登入身分各跑一次**：資料類直接跑；Live Server／Shioaji／IBKR 報價改完照七之二節重啟並驗證 `/health`（`stale_process=false`）與 OPTIONS 預檢；
   自動投資只跑 `--preflight`。任何一支不正常就先還原那一支的啟動檔，不進入密碼步驟。
4. `convert-tasks-to-password.ps1` 加入第 2 批（A＋B，23 支）與第 3 批（C，5 支）清單。

以上 1～4 安排在 **10/20 收盤、第一批 10/20 核對完之後**才動（盤中不動常駐服務與自動投資）。

## 四、總司令本人要做的事（約 3 分鐘）

1. CC 會用系統管理員權限開一個 PowerShell 視窗執行 `C:\alpha\convert-tasks-to-password.ps1 -Batch 2`（Windows 會先跳「是否允許變更」→ 按「是」）。
2. 視窗裡會列出要改的 23 支工作名稱，接著跳出 **Windows 認證視窗**：請在**那個視窗**輸入這台電腦的 Windows 登入密碼（若是 Microsoft 帳戶，輸入 Microsoft 帳戶密碼，不是 PIN）。
   **不要把密碼打在對話框、終端機或任何其他地方。**
3. 視窗跑完會自己關閉（20 秒），結果寫在 `C:\alpha\task_password_backup\batch2_result.txt`（只有工作名稱與成功／失敗，沒有密碼）。

（以上視窗畫面是依第一批 10/15 的實際流程描述；第二批清單變長，畫面多幾行，以你看到的為準。）

## 五、改完 CC 驗證與還原

- 逐支看 LogonType=Password、下一次執行的 LastTaskResult、心跳／日誌；`AlphaPushProbe` 暫時工作會自動驗證不登入身分推得上 GitHub。
- 第二批觀察 3 個交易日（照第一批做法）；正常才提第三批（C 組）。
- 任何一支有問題：`convert-tasks-to-password.ps1 -Batch 2 -Revert`，用改前匯出的 XML 原樣還原（`C:\alpha\task_password_backup\<工作名>.orig.xml`，不含密碼）。
