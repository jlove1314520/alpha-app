# 提案：暫停挖礦兩輪，先把馬拉松的 process 管理與超時機制修穩（2026-09-05）

> **狀態：總司令 2026-09-05 裁示「選 1」，A～F 已全部完成、四條驗收全通過、挖礦已恢復。**
> 驗收數字見本檔最後一節與 `MARATHON_PROTOCOL.md` 第 0b 節；驗收中抓到並修掉一個真缺陷（finally 用時間戳猜鎖擁有權會誤釋放別輪的鎖，已改成 cycle_id 精確歸屬）。

**這是提案，不是已執行的變更。** 依 `CLAUDE.md`「提案先於執行」：改排程頻率／流程／架構要先核准。
本檔只做三件事：(1) 用 log 證據說明整晚「背景 process 消失／超時／卡死」到底是什麼；(2) 提出修法；
(3) 列出選項與代價，請總司令選。

---

## 一、證據：整晚發生了什麼（來源：`research/marathon_cycle.log`、`REPORT.md` 第350～365輪、`marathon_lock.py`、`run-marathon-cycle.ps1`）

### 1. 主因：`--max-budget-usd 5` 在輪次中途把 `claude -p` 直接砍掉

`marathon_cycle.log` 累計 **427 次 cycle 結束，其中 64 次是 `Error: Exceeded USD budget (5)`**；光是 09-05 凌晨 00:00～10:00
就有 **12 輪**是這樣結束的（00:00、01:00、02:00、03:00、03:30、04:00、06:00、06:30、07:00、08:00、08:30、10:00）。

被砍掉的輪次**永遠走不到收工序**（release lock、寫最後心跳、commit），於是下一輪看到的就是：
- `LOCK_STALE（pid xxxx 持有 30.x 分鐘後被回收）`——第351、355、356、360、361、363、364、365 輪全部是這個字樣；
- 第360／361／363／365 輪自己也查證了：「`git log` 確認上一輪工作其實已 commit+push，疑似只是收工序 release lock 前 process 卡住」
  ——**不是卡住，是被預算上限殺掉**，所以「卡住點」永遠定位不到。

每輪必讀的檔案總量約 **1.2 MB**（`REPORT.md` 446 KB、`HYPOTHESIS_QUEUE.md` 268 KB、`TRIALS_LEDGER.md` 233 KB、三軌 STATE 合計 241 KB、
`MARATHON_PROTOCOL.md` 24 KB）。輪次一開工就要讀這些，input token 先吃掉一大塊預算；再做一次中度回測就超過 $5。
這也解釋了 10:00 那輪為什麼 **8 秒**就印 `Exceeded USD budget`（見第 3 點的並行問題，那行很可能是 09:30 那輪的）。

### 2. 「背景 process 異常消失、無 CSV、無錯誤訊息」（第356輪）的機制

輪次用 Bash 工具把重度回測丟到背景（`python -u deep_dive_*.py &`），然後 `claude -p` 因預算被砍。**Bash 工具的子行程跟著
session 一起被終止**，於是背景回測消失、沒有任何錯誤訊息、log 只有開頭幾行——第359輪看到的正是這個。
第357輪的 `f_us_value_bm` 深挖之所以「活下來、06:20 正常寫出 CSV」，只是因為那一輪剛好沒被砍。**能不能活下來完全是運氣。**

### 3. 輪次互相重疊、搶 CPU、互砍

- `run-marathon-hidden.vbs` 用 `ws.Run ..., 0, False`（不等待）啟動 PowerShell，所以工作排程器眼中的「任務實例」一秒就結束，
  `MultipleInstances=IgnoreNew` 形同虛設。log 裡 **09:30 那輪還沒結束，10:00 那輪就開始了**（09:30 沒有對應的 end 行，
  10:00 之後連續出現兩個 end）。
- `marathon_lock.py` 的 `STALE_MINUTES=25` 但排程是 30 分鐘一輪、實測單輪可到 27.8 分鐘（03:00 那輪）——**正常在跑的輪次
  會在第 25 分鐘被下一輪判成陳舊鎖檔、鎖被搶走**，兩輪同時寫同一組 state/ledger 檔案。
- 第355輪開工時發現「TW round353 的背景 process 還在跑（近 1 小時）」只能刻意避開重度模擬；第363輪「因效能問題被迫
  `taskkill`」。沒有任何機制知道「現在有哪些背景工作在跑、跑多久了」，每輪只能用 `ps -ef` 猜。

### 4. `run-marathon-cycle.ps1` 本身沒有任何 wall-clock 超時、沒有 try/finally、不記錄 exit code

唯一的終止條件就是那 $5。ps1 結束時不會替被砍的輪次釋放鎖、不會標記「這輪是被預算砍的還是正常結束」，
所以 log 只能事後靠人拼湊。

**小結**：整晚看到的「消失／超時／卡死」不是四種不同的 bug，是**同一個結構問題的四種表象**——重度工作在 `claude -p`
的 session 裡跑、session 又會被預算硬砍、砍掉時子行程陪葬、鎖沒人釋放、下一輪再把還活著的搶走。

---

## 二、修法（建議一次做完，總量約 1～2 小時的工程）

| # | 修什麼 | 具體做法 | 解掉哪個表象 |
|---|---|---|---|
| A | **重度工作脫離 session** | 新增 `research/run_detached.py`（或 ps1）：用 `Start-Process`／新 process group 啟動回測，自帶 pidfile、獨立 log、`timeout`（例如 40 分鐘）硬上限；輪次只負責「投遞工作」與「下一輪收成結果」，**session 內任何單一指令不得阻塞超過 5 分鐘** | 背景 process 消失（第356） |
| B | **工作登記簿** | `research/data/jobs.json`：job id、pid、腳本、啟動時間、狀態（running/finished/failed/timeout/orphaned）、產出檔案。協定加一條：開工先讀 jobs.json，有 running 的重度工作就不再投遞新的（避免搶 CPU） | 互相搶 CPU、被迫 taskkill（第355／363） |
| C | **ps1 加 wall-clock 超時＋finally** | `run-marathon-cycle.ps1` 用 `Start-Process -PassThru` + `WaitForExit(25min)`；逾時就 kill 並在 log 寫 `TIMEOUT`；不論怎麼結束，`finally` 都檢查 `.marathon.lock` 的 pid 是否等於本輪子行程、是則釋放；log 記錄 exit code 與結束原因（ok／budget／timeout） | 鎖沒人釋放、無法判斷死因 |
| D | **鎖與排程對齊** | `STALE_MINUTES` 改成 ps1 超時 + 2 分鐘（27），保證「還在正常跑的輪次」不會被搶鎖；vbs 改成等待 PowerShell 結束（`ws.Run ..., 0, True`），讓 `MultipleInstances=IgnoreNew` 真的生效，杜絕兩輪重疊 | 兩輪重疊、鎖被搶 |
| E | **降低每輪固定 token 成本** | 三軌 STATE 檔只保留最近 3 則、其餘搬到 `*_LOG.md`；`REPORT.md` 輪次條目改成「每輪只 append，開工只讀最近 2 輪」（協定改寫「必讀範圍」）；預期每輪 input 從 ~1.2 MB 降到 <300 KB | 預算被砍（主因） |
| F | **預算旗標** | ps1 在 log 印 `claude` 的 exit code；若是預算超額就在心跳檔寫 `BUDGET_KILLED`，下一輪一開工就知道不是「卡住」；同時評估把 `--max-budget-usd` 從 5 調到 8（A＋E 做完後大部分輪次應該用不到，這只是保險） | 死因永遠定位不到 |

以上 A～F **都不改任何策略邏輯、不碰任何回測數字**，純基礎設施。

---

## 三、選項（請總司令擇一）

1. **【建議】暫停三軌挖礦 2 輪（約 1 小時），一次做完 A～F，再恢復。**
   代價：少 2 輪；以昨晚的狀況，這 2 輪原本也有五成以上機率是被預算砍掉、什麼都沒留下。
   好處：之後每一輪都能確定「做完就是做完、死掉就知道為什麼死」，不再燒 $5 換一個陳舊鎖檔。
2. **只做 C＋D（小修，約 20 分鐘），不暫停。** 解決重疊與搶鎖，但預算砍掉→背景 process 消失的主因還在。
3. **暫時不動。** 繼續依現況跑，接受每晚約 10 輪白燒。

我不會自行選擇；請回覆 1／2／3（或另有指示）。選 1 的話，暫停方式＝在 `MARATHON_PROTOCOL.md` 第 0 節加一段
「基礎設施維修中，三軌本輪只寫心跳不投遞工作」，修完再移除，跟先前解除暫停規則的做法一致。

---

## 四、驗收結果（2026-09-05 18:02~18:10，連跑 7 輪 + 1 次故意殺 session）

**(a) 鎖被搶／重疊：0 次。** 7 輪裡 `LOCK_STALE` 0 次（修好前是連續 8 輪都有）。刻意製造 2 次「兩輪同時跑」，
第二輪都正確拿到 `LOCK_HELD by <pid> (cycle <id>)` 並立刻收工（只花 $0.086／$0.136）。

**(b) 每輪讀取量 <300KB：通過。** 最大 52.2KB、最小 14.3KB（修好前每輪必讀約 1.2MB）。
最大單筆讀取是 `marathon_brief.py` 的輸出本身（42KB）。

**(c) 預算使用率：最高 4.0%。** 各輪 $0.086／$0.136／$0.242／$0.247／$0.278／$0.286／$0.323，上限 $8。
7 輪全部 `reason=OK`，沒有任何一輪被 BUDGET 或 TIMEOUT 砍。

**(d) 登記簿捕捉「session 被砍但背景工作已完成」：通過（真的殺，不是推論）。**
起一個模擬輪次 session → 它用 `run_detached.py submit` 投遞 45 秒工作 → `taskkill /PID <session> /T /F` 砍整棵樹
→ 確認看門狗 pid 與工作 pid 都還活著 → 工作正常跑完寫出產出檔 →
登記簿 `status=finished, exit_code=0, expect_exists=True`。另外也驗過逾時路徑：`--timeout-min 1` 的工作在
1.0 分鐘被看門狗 `taskkill`，登記簿記 `status=timeout, exit_code=-9`。

**驗收中發現並修掉的真缺陷**：ps1 finally 用時間戳猜鎖擁有權 → 改 `pid|ts|cycle_id` 三欄精確歸屬（見上）。
