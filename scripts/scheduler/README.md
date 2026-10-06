# 自動交易排程：備份與還原（先.三十一-五）

本資料夾是 `C:\alpha\` 底下三支排程腳本與五個 Windows 工作排程器任務的備份副本，供換機或重灌後還原。**不含任何憑證**（憑證只在本機 `.env`）。XML 內的使用者 SID 已換成 `__USER_SID__`。

| 檔案 | 還原到哪裡 |
|---|---|
| `run-auto-trading-cycle.ps1`、`run-auto-trading-hidden.vbs`、`register-auto-trading-tasks.ps1` | `C:\alpha\` |
| `AlphaAutoRun0905.xml`、`AlphaAutoRun0940.xml`、`AlphaAutoSettle1340.xml`、`AlphaAutoWatchRun.xml`、`AlphaAutoWatchSettle.xml` | 供對照或匯入工作排程器 |

## 還原步驟（在互動式 PowerShell 執行，不要用自動化工作階段，否則會 Access denied）
1. 把 repo clone 到 `C:\alpha\alpha-app`，並讓 `C:\alpha\` 存在。
2. 把上表三支腳本複製到 `C:\alpha\`（腳本內路徑寫死 `C:\alpha\`）。
3. 還原本機 `.env`（API 金鑰與 CA 設定）與 `research\data\auto_trading\config.local.json`；這兩個檔案不在 repo，要從總司令自己的備份取回。
4. 執行 `powershell -ExecutionPolicy Bypass -File C:\alpha\register-auto-trading-tasks.ps1`，會用目前登入的使用者建立 5 個任務（週一至週五：09:05、09:40 執行；09:55 看門狗；13:40 結算；14:00 看門狗）。已存在的任務會略過。
5. 若要改用 XML：先把檔案內 `__USER_SID__` 換成 `whoami /user` 顯示的 SID，再 `Register-ScheduledTask -Xml (Get-Content .\AlphaAutoRun0905.xml -Raw) -TaskName AlphaAutoRun0905`。
6. 驗證：`Get-ScheduledTask -TaskName AlphaAuto*` 應有 5 筆；`python research\auto_rebalance_bb90.py --watchdog run` 能正常印出結果。

來源版本以 2026-10-06 的本機設定匯出；若 `C:\alpha\` 的腳本之後有修改，需同步更新這裡的副本。
