# 本機排程工作清單（重開機後照這份走）

建立於 2026-09-10，起因是 09-09 深夜到 09-10 中午之間這台機器重開機，
03:26 之後所有產出停止。事後查證發現**排程本身在使用者登入後就自動恢復了**，
真正的問題是另外三個「狀態顯示成功、實際上什麼都沒產出」的靜默故障。

這份文件的用途只有一個：**下次重開機時照著跑一次自檢，不必再從頭查一遍。**

---

## 一、最重要的一句話：所有工作都要「使用者登入」才會跑

十個 Alpha* 工作原本的執行身分全部是 `InteractiveToken`
（工作排程器 UI 上的「只有使用者登入時才執行」）。

意思是：**電腦開機後如果停在鎖定畫面沒有人登入，一個都不會跑。**
加「系統啟動時」的觸發器也沒有用——`InteractiveToken` 在定義上就需要一個
互動式登入工作階段才能取得權杖，觸發時根本沒有可用的權杖。

### 總司令裁示（2026-09-10）：分兩類，不一刀切

先前提的兩條路（全機改執行身分／開啟自動登入）**都被否決**，理由如下：

- 全機改執行身分：`claude` CLI 在沒有互動式工作階段時能不能跑**未驗證**，
  不能拿三個研究工作去賭。
- 自動登入：這台是**真錢帳戶機器**，開機即解鎖與既有的連線安全強化自相矛盾。

改採分類處理：

| 類別 | 工作 | 執行身分 | 理由 |
|---|---|---|---|
| **A（資料命脈）** | `AlphaLiveServer`／`AlphaShioajiQuotes`／`AlphaIbkrQuotes`／`AlphaConnectivity`／`AlphaTwsePublishProbe`／`AlphaData` | **S4U**（不論登入都執行，**不存密碼**） | 人不在時 App 要活著、tick 不能斷。資料一斷就是**永久損失**，補不回來 |
| **B（研究）** | `AlphaMarathon`／`AlphaDevQueue`／`AlphaHypothesisQueue` | 維持 `InteractiveToken` | 都要啟動 `claude` CLI。研究中斷只是暫停、**無資料損失**，登入後可補跑 |

**S4U 是什麼**：Windows 的「服務帳戶登入」，讓工作以該使用者身分在 session 0
執行，**不需要儲存密碼**。這是三個選項裡唯一不引入新祕密、也不放寬機器鎖定的做法。

### 怎麼套用（需要一次系統管理員提權）

註冊 S4U 工作需要「以批次工作登入」權限，非提權階段做不到（實測 `Access is denied`）。
這台機器的 `user` 帳號**已經在 Administrators 群組裡**，所以只差一次 UAC 同意。

在**系統管理員** PowerShell 裡跑：

```powershell
powershell -ExecutionPolicy Bypass -File C:\alpha\convert-tasks-to-s4u.ps1
```

那支腳本會逐一：備份原始設定 → 改成 S4U → **實際跑一次** → 檢查產出檔時間戳
**真的有動**。**沒有產出的一律當場還原成 `InteractiveToken` 並列為失敗**，
不留半殘的管線。全部還原：

```powershell
powershell -ExecutionPolicy Bypass -File C:\alpha\convert-tasks-to-s4u.ps1 -Revert
```

**未知數要誠實講**：Shioaji 與 IBKR 的登入在非互動階段能不能完成，**沒人驗過**。
腳本的逐一實測就是為了當場問出答案，而不是改完宣告完成。
`AlphaData` 刻意不試跑——在非 15:30 的時間跑會把不完整的當日資料寫進 `alpha.db`，
它的驗收是下一次 15:30 排程。

### B 類的待辦（不要沒驗證就改）

另立一條待辦：**單獨驗證 `claude` CLI 在非互動階段能否啟動**。
驗證通過才談要不要把 B 類也改過去。見 `PENDING_QUEUE.md`。

## 二、工作清單

| 工作 | 用途 | 觸發器 | 產出（驗證看這個） |
|---|---|---|---|
| `AlphaLiveServer` | App 即時報價伺服器（聽 127.0.0.1:8001，對外靠 Tailscale Funnel） | 每 1 分鐘 ＋ 登入時 | `research/alpha_live_server_cycle.log` |
| `AlphaShioajiQuotes` | 永豐 Shioaji 盤中逐筆常駐程式的啟動器 | 每 2 分鐘 ＋ 登入時 | `research/shioaji_quotes_cycle.log` |
| `AlphaIbkrQuotes` | 美股報價（IBKR Gateway） | 每 5 分鐘 ＋ 登入時 | `research/ibkr_quotes_cycle.log`、`data/quotes_ibkr.json` |
| `AlphaConnectivity` | 對外連通性監測 ＋ 常駐工作停擺自檢 | 每 5 分鐘 ＋ 登入時（延遲 1 分） | `research/external_connectivity.jsonl`、`data/audit_report.json` 的 `local_task_health` |
| `AlphaTwsePublishProbe` | 實測 TWSE T86／MI_MARGN／STOCK_DAY_ALL 的實際發布時間 | **每日** 13:30 起每 15 分鐘、共 6.5 小時 ＋ 登入時（延遲 2 分） | `research/twse_probe.log`、`research/twse_publish_probe.jsonl` |
| `AlphaDevQueue` | 開發任務佇列自走輪次 | 每 15 分鐘 ＋ 登入時 | `research/dev_queue_cycle.log` |
| `AlphaMarathon` | 研究馬拉松自走輪次 | 每 30 分鐘 ＋ 登入時（延遲 5 分） | `research/marathon_cycle.log`、`research/MARATHON_STATE.md` |
| `AlphaHypothesisQueue` | 假設佇列自走輪次 | 每 30 分鐘 ＋ 登入時（延遲 3 分） | `research/hypothesis_queue_cycle.log` |
| `AlphaData` | `alpha-data` 每日六大類資料入庫 | 每日 15:30 | `C:\alpha\alpha-data\run.log`、`alpha.db` 各表的 `max(date)` |
| `AlphaDepCheck` | 相依套件安全性更新檢查 | 每週日 08:00 | `data/dependency_status.json` |

---

## 三、重開機後的自檢指令

登入桌面後，開一個 PowerShell 視窗，**照順序**跑這三段。

### 第 1 段：排程器有沒有在動

```powershell
Get-ScheduledTask -TaskName "Alpha*" | Get-ScheduledTaskInfo |
  Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime |
  Sort-Object TaskName | Format-Table -AutoSize
```

判讀：

- `LastTaskResult` = `0` 成功；`267009`（0x41301）代表**正在跑**，正常
- `2147942402`（0x80070002）＝找不到檔案，通常是執行檔路徑沒寫全
- `267011`（0x41303）＝從未執行過
- `NextRunTime` **空白是嚴重警訊**：代表這個工作沒有任何還會觸發的觸發器。
  2026-09-10 的 `AlphaTwsePublishProbe` 就是這樣——它的觸發器是
  2026-09-08 的**一次性** `TimeTrigger`，跑完那天就永久失效，
  狀態卻一直顯示「就緒」，兩天沒收到任何樣本也沒有人發現。

### 第 2 段：有沒有真的產出（**這一段才是重點**）

「狀態＝就緒」和「上次結果＝0」都可以在什麼事都沒做的情況下成立。
只有產出騙不了人。

```powershell
python C:\alpha\alpha-app\scripts\pipeline_inventory.py
```

印出十條管線各自「最後一次真正產出是什麼時候」，超過預期新鮮度的會列在最後，
離開碼 1 代表有停擺。

**這張表看的是資料層的時間戳，不是檔案修改時間。**
差別就是 `alpha.db` 那一條：它每天都被連線寫入，**mtime 天天更新**，
但 `daily_price` 的 `max(date)` 停在 2026-08-21——整整 20 天沒人發現。
只看 mtime 的檢查會給它一個漂亮的綠勾。

同一份判定每 5 分鐘會自動跑一次（`AlphaConnectivity`），
結果寫進 `data/audit_report.json` 的 `local_task_health`，
也會進 `data/STATUS.json` 的 `local_pipeline_health`。

**三個地方讀的是同一份設定**：`data/seed/pipeline_registry.json`。
要新增或調整監控對象，改那一份，不要改程式——
否則遲早出現「清點表上有、自檢沒監控」的漏洞。

### 第 3 段：兩個排程管不到的斷點

```powershell
# (a) 即時伺服器本機健康 + 對外通道
curl.exe -s http://127.0.0.1:8001/health
& "C:\Program Files\Tailscale\tailscale.exe" funnel status

# (b) IBKR Gateway 的 API 埠
Test-NetConnection -ComputerName 127.0.0.1 -Port 4001 -InformationLevel Quiet
```

**IBKR Gateway 每週日 01:00 ET 安全權杖失效，一定要人工登入一次**，
排程救不了（見 `CLAUDE.md` 的 IBKR 章節）。四個埠（4001/4002/7496/7497）
全關而 Gateway 行程活著＝卡在登入畫面。

---

## 四、2026-09-10 這次修了什麼

| 問題 | 根因 | 修法 |
|---|---|---|
| `AlphaTwsePublishProbe` 兩天沒收樣本 | 觸發器是 09-08 的一次性 `TimeTrigger`，跑完即永久失效 | 改成 `CalendarTrigger` 每日 13:30 起、每 15 分鐘、共 6.5 小時，另加登入觸發器 |
| 探針日誌全是亂碼、樣本讀不出來 | Python 用 cp950 輸出、PowerShell 以 utf8 寫入 | `run-twse-probe.ps1` 同時設 `PYTHONIOENCODING` 與 `[Console]::OutputEncoding` |
| `AlphaDepCheck` 每週 0x80070002 | 執行檔寫成裸的 `python`，排程器不會走 PATH 找 | 改走 `powershell.exe` 包裝，與其他工作一致 |
| `alpha.db` 自 2026-08-21 起沒有新資料 | `run_daily.py` 輸出重導到 `run.log` 時，第一行 print 的 `・`(U+30FB) 觸發 cp950 `UnicodeEncodeError`，整支在第一檔股票就崩潰 | 工作動作加上 `set PYTHONIOENCODING=utf-8` |
| `AlphaDevQueue` 每輪都跳過 | 「工作目錄乾淨才動手」的守衛用檔名黑名單，機器自動寫的檔案愈來愈多（實測同時有 7 個永遠是髒的），黑名單只擋掉 2 個 | `run-dev-queue-cycle.ps1` 改成白名單：先認定哪些路徑是機器寫的，其餘才算人為改動 |
| 重開機後 `AlphaHypothesisQueue` 停了 9 小時 | 沒有登入觸發器，且沒開「錯過就補跑」 | 加登入觸發器（延遲 3 分）＋ `StartWhenAvailable=true` |
| 停擺完全看不見 | 沒有任何「產出有沒有在動」的檢查 | `check_external_connectivity.py` 加 `local_task_health` 自檢（見第 2 段） |

**待辦**：

1. **A 類六個工作改 S4U** ——腳本已備妥（`C:\alpha\convert-tasks-to-s4u.ps1`），
   需要總司令用系統管理員 PowerShell 跑一次（見第一節）。**尚未執行**。
2. **驗證 `claude` CLI 在非互動階段能否啟動** ——這是 B 類要不要跟進的前提，
   沒驗證前不動 B 類。
