# 本機排程工作清單（重開機後照這份走）

建立於 2026-09-10，起因是 09-09 深夜到 09-10 中午之間這台機器重開機，
03:26 之後所有產出停止。事後查證發現**排程本身在使用者登入後就自動恢復了**，
真正的問題是另外三個「狀態顯示成功、實際上什麼都沒產出」的靜默故障。

這份文件的用途只有一個：**下次重開機時照著跑一次自檢，不必再從頭查一遍。**

---

## 一、最重要的一句話：所有工作都要「使用者登入」才會跑

十個 Alpha* 工作的執行身分全部是 `InteractiveToken`
（工作排程器 UI 上的「只有使用者登入時才執行」）。

意思是：**電腦開機後如果停在鎖定畫面沒有人登入，一個都不會跑。**
這不是設定錯誤可以修掉的東西——`InteractiveToken` 在定義上就需要一個
互動式登入工作階段才能取得權杖，加「系統啟動時」的觸發器也沒有用，
因為觸發時根本沒有可用的權杖。

所以重開機後的第一件事永遠是：**登入 Windows 桌面。** 登入之後：

- 有登入觸發器的工作會在 1–5 分鐘內自己補跑（見下表）
- 其餘工作會在下一個時間點跑，且因為都已開啟「錯過排程就儘快啟動」
  （`StartWhenAvailable`），錯過的那一輪會自動補

若想連「沒人登入也要跑」都做到，只有兩條路，兩條都有代價，**尚未採用**：

1. 把執行身分改成「不論使用者是否登入都執行」（要存密碼或用 S4U）。
   風險：`AlphaMarathon` / `AlphaDevQueue` / `AlphaHypothesisQueue`
   要啟動 `claude` CLI，沒有互動式工作階段時能不能正常跑**未驗證**。
2. 開啟 Windows 自動登入。風險：等於這台機器開機即解鎖。

要改哪一條請總司令裁示，不要自行決定。

---

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
只有檔案時間戳騙不了人。

```powershell
python C:\alpha\alpha-app\scripts\check_external_connectivity.py
```

這支會同時做兩件事：對外連通性，以及**比對每個常駐工作產出檔的修改時間**，
超過預期間隔 3 倍就告警，並寫進 `data/audit_report.json` 的 `local_task_health`。

只想看結果不想重跑：

```powershell
python -c "import json;d=json.load(open(r'C:\alpha\alpha-app\data\audit_report.json',encoding='utf-8'))['local_task_health'];print(d['checked_at'],'alert=',d['alert']);[print(' ',t['task'],t['status'],t.get('age_min','')) for t in d['tasks']]"
```

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

**尚未解決、需要總司令裁示**：第一節那個「沒人登入就一個都不會跑」的結構性限制。
