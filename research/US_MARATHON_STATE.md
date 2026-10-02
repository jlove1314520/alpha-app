# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `US_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-10-01T21:0x+08:00（馬拉松第692輪，維運帽）**——取鎖乾淨
（cycle`20261001-210036`）。三軌時間戳：US round689=09-30 15:0x（最舊，
本輪選定）／FUT round690=09-30 16:0x／TW round691=2026-10-01 20:0x（本輪
開工前剛完成，結論相同）。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`
=1（`先.五-三`，標明「互動視窗」執行、非馬拉松範圍，非真正可動手項）；
`grep -c "^- \[!\]"`=13（與round689持平）。逐一核對13條`- [!]`阻塞項：
`金流一.4`實測`data/sector_flow.json` `meta.trading_days_available`=18、
`windows_missing_days.20`=2（較round689的3縮1，與TW round691記錄一致），
20日視窗仍差2個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測15/20（較round689持平，仍差5日），
未解除；`本地AI摘要(Breeze-7B)`(a)/(b)/(c)/(d)資料來源裁示分支仍待總
司令選一，屬白名單第6條法遵疑慮，未解除；`紙.一`需2026-10-01（今日）
但`data/paper_7030.json`仍`started:false`（當日收盤尚未經market.yml
寫入，查詢時刻早於台股收盤後批次），未解除；其餘9條逐一核對開頭標記，
均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間。`grep -c
"凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際
宣告解除，凍結.二仍生效（`轉向.一`仍阻塞於等Cowork人工核對閘門.一，
屬白名單第2類，自走軌道不得代為放行）。**佇列深度自檢**：`- [ ]`=1但
保留給互動視窗，實質可動手項=0（<12下限），凍結.二期間暫停補件，不
硬湊alpha試驗候選。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成
300/300）；工具修正已由互動視窗commit（`git log`最新數筆均為排程自動
更新，無互動視窗新commit待複查）；`git status --short -- research/
backtest/ research/validation/ research/adjust.py research/pit.py
research/trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未
commit編輯）。US軌本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only
因子家族結案狀態未變，`CALIBRATION_PROBE.md`唯一指名給US軌的操作指令
（#47/#52重跑）先前輪次已複核確認2026-09-04早已結案、無殘留，本輪再次
核對`TRIALS_LEDGER.md`第572~573行備註仍為最終狀態，無新變化。無對應
結構性優勢候選可開新方向（凍結.二期間本來就不得開新alpha試驗）。驗證：
`run_detached.py status`running=0（162筆歷史，無job待收成）；`trial_
registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（409列，
另有FDR對照表33列，最大編號#407，本輪未新增判定）；`validation/
holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取
核對）。`AWAITING_REVIEW.md`「等待中（目前：28件）」，逐行核對與28筆
資料列一致，與round691一致，本輪未變動。**本輪誠實結論**：交辦佇列
實質0條可動手項（`先.五-三`保留給互動視窗）；凍結.二允許的四類工作
皆已完成或無新內容；13條`- [!]`逐一核對均未到解除時間；US軌本身查無
可推進的新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後
結束本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節
限定檔案、不代做互動視窗保留項目。未動`alpha.db`/`fetch.py`/
`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何原始碼
（僅讀取核對＋改狀態檔），全程零新增外部API呼叫（純讀既有`.json`/
`.md`帳本檔案、`git status`/`git log`、`run_detached.py status`、
`trial_registry.py --check`、`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條真正可動手的`- [ ]`未開始**。
**等待審閱：28件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一
軌接手**：依輪替下一輪建議選FUT軌（round690=09-30 16:0x，三軌中最舊）；
開工前先重新檢查`- [ ]`有無新交辦、`金流一.4`20日視窗是否已補到0（目前
差2個交易日）、`外部一改.2`tick累積15/20還差5日、`本地AI摘要
(Breeze-7B)`四選一是否已裁示、`紙.一`是否已有`started:true`紀錄
（今晚market.yml跑完後應會更新）、`轉向.一`Cowork核對是否已完成。
凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見
`REPORT.md`第692輪心跳、`PENDING_QUEUE.md`「金流一.4」「外部一改.2」
「本地AI摘要(Breeze-7B)」「紙.一」「轉向.一」條目、
`research/AWAITING_REVIEW.md`。

---

**最後更新：2026-10-02T20:3x+08:00（馬拉松第695輪，維運帽）**——取鎖乾淨。
三軌時間戳：US round692=10-01 21:0x（最舊，本輪選定）／FUT round693=
10-01 22:0x／TW round694=10-01 23:1x。開工先讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（凍結.二期間不補件，維持）；`grep -c "^- \[!\]"`
=21（本輪新增1條「維運.AlphaData三日DNS解析失敗」，其餘為既有累積）。
**本輪不是單純逐一核對阻塞項解除時間，而是主動查證多個時間敏感的
已知阻塞條件，因為距上次更新已過24小時、多個條件的時間窗口已經
到期或接近到期**：
1. **先.六-四／先.七-一（Shioaji 10/2開盤後確認）**：查`data/
   quotes_sinopac.json`10/2收盤快照、`research/.live_state_sinopac.json`
   mtime（仍停2026-09-30 13:45，10/1與10/2兩個完整交易日皆未更新）、
   `research/external_connectivity.jsonl`（10/2全天internet.ok=True）。
   **結論：10/2仍登入失敗，且本次已排除網路原因**（10/1是網路中斷，
   10/2網路正常但照樣連不上），指向Shioaji端憑證/API key/維護，需
   總司令本人查永豐帳戶狀態（白名單第2條），已詳細記錄於PENDING_
   QUEUE對應兩條目，未讀取或輸出任何金鑰憑證內容。
2. **維運.market.yml今日排程缺席／先.九-四／先.九-五**：`gh run list
   --workflow=market.yml`確認10/2截至20:32台北仍只有1筆run（屬前一天
   21:43 UTC美股班次延遲落地，非今日台股班次）；已執行`python
   scripts/log_dispatch_delay.py --since 2026-10-02`記錄0筆（未到
   8.6小時延遲上限，暫不升級為「確定缺席」）。三個相關條目已同步
   更新一致結論，避免互相矛盾。
3. **新發現（本輪真正的維運產出）：`C:\alpha\alpha-data`（Phase 2
   歷史資料庫管線，不在alpha-app repo內）的`run_daily.py`連續3天
   （10-01、10-02）因DNS解析失敗（`NameResolutionError...getaddrinfo
   failed`，對`openapi.twse.com.tw`/`www.twse.com.tw`/`openapi.
   taifex.com.tw`/`www.sec.gov`四個網域皆失敗）完全沒有新增資料，
   `alpha.db`卡在2026-09-29**。本輪立即重跑連線測試確認DNS/連線
   目前正常（非持續性故障），研判是每天15:30那個特定時間窗口本機
   DNS resolver短暫異常，已完整記錄根因、證據鏈與三個修復選項(a)/
   (b)/(c)到`PENDING_QUEUE.md`新條目「維運.AlphaData三日DNS解析
   失敗」，**未改動`fetch.py`/`parsers.py`/`config.py`/`alpha.db`
   任何位元組**（依根目錄CLAUDE.md規定需總司令確認才能動）。
4. **附帶發現**：`AlphaQuotesTW`/`AlphaNewsEvents`兩個本機watchdog
   聲稱連續錯過9/14個應跑班次，直接核對`data/quotes_tw.json`/
   `data/news.json`實際`fetched_at`皆新鮮正常，判斷是`先.九-三`
   （2026-10-01）cron錯開分鐘數後watchdog的「預期班次」邏輯未同步
   更新，產生假陽性告警（非真停擺），已記錄供日後修復參考，未修改
   watchdog程式碼本身。
**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次
已全部完成並登記；資料抓取（`資料.一`已完成300/300）；工具修正——
本輪僅執行既有工具（`log_dispatch_delay.py`讀取，無程式碼修改）；
`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出
為空（十三節限定清單內檔案無殘留未commit編輯，本輪亦未touch）。US軌
本身查無新工作單位，凍結.二期間不得開新alpha試驗。驗證：`run_
detached.py status`running=0；`PYTHONIOENCODING=utf-8 python research/
trial_registry.py --check`exit=0 PASS（409列不變，本輪未新增判定，
純維運工作不產生試驗）；`holdout.py::is_holdout_consumed()`=True
（僅讀取核對）。`AWAITING_REVIEW.md`「等待中：51件」（較round692的
28件增加，為互動視窗本輪活躍產出的結案項，非馬拉松動作，本輪僅讀取
核對）。**本輪誠實結論**：交辦佇列0條`- [ ]`；本輪產出4筆維運發現
（2筆Shioaji/market.yml既有阻塞項的時效性更新、1筆全新的alpha-data
DNS故障根因鑑識、1筆watchdog假陽性觀察），已完整記錄進`PENDING_
QUEUE.md`供總司令/互動視窗裁示，**未自行修改任何受保護檔案**（`alpha.
db`/`fetch.py`/`parsers.py`/`config.py`凍結區、十三節限定清單皆未
touch）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：51件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round693=
10-01 22:0x，三軌中最舊）；開工前務必先確認：Shioaji 10/3（下一個
交易日，10/3-10/4為週末，故實際是10/6）是否仍登入失敗（累積更多
樣本）、`market.yml`今日09:13/10:41 UTC批次最終是否在17:49 UTC前
出現（本輪查詢時仍未到判斷時間點）、`alpha-data`明天15:30的
`run_daily.py`是否恢復正常（若恢復代表是偶發自癒，若再失敗則3天
變4天，升高修復優先度）。凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除。完整見`REPORT.md`第695輪心跳（待補）、`PENDING_QUEUE.md`
「先.六-四」「先.七-一」「維運.market.yml今日(10/1)排程兩次觸發皆
缺席」「先.九-四」「先.九-五」「維運.AlphaData三日DNS解析失敗」
條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-02T23:3x+08:00（馬拉松第698輪，US軌，維運帽）**——取鎖
乾淨（cycle`20261002-233037`）。三軌時間戳（開工前）：US round695=10-02
20:3x（最舊，本輪選定）／FUT round696=10-02 21:3x／TW round697=10-02
22:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round695~697持平）；`grep -c "^- \[!\]"`=21（持平）。

**housekeeping（[自行裁量]，非交辦，屬馬拉松維運帽日常工作）**：
`US_MARATHON_STATE.md`累積到5個條目（round683/686/689/692/695），超過
規則要求的「只保留最新3則」，已將最舊的683／686／689三則原文搬到
`US_STATE_ARCHIVE.md`（append-only，依既有慣例保持時間順序：先683後
686後689），本檔只留692／695／本輪698。純檔案維護，未變動任何判定
內容。

逐一核對21條`- [!]`阻塞項（與round697一致，本輪重複驗證+2項新查證，
未發現新解除）：`金流一.4` `sector_flow.json` `meta.trading_days_
available`仍**18**、`windows_missing_days.20`仍**2**，未解除——**新查
到一個細節**：`data/institutional_history.json`原始`dates`陣列其實已有
**23筆、最新到20261001**（與round697查詢時的認知一致，此為10/2凌晨
01:08 UTC「美股班次」commit`4cb4e95cb`順帶補上的，非本輪新增），但
`sector_flow.json`的`_solid_dates()`品質篩選仍判定可用天數停在18（即
20261001被篩掉，可能是三大法人覆蓋率不足，非程式錯誤，與`known_gaps`
欄位既有說明一致），**20日視窗的卡關不是「沒抓到10/1資料」，是「抓到
但品質篩選沒放行」，這是比round697認知更精確一層的子結論，不影響
BLOCKED狀態與既有解除條件**。`外部一改.2`／`研究.c`tick累積`ls
research/data/ticks/*.parquet`實測仍**15/20**，未解除。`本地AI摘要
(Breeze-7B)`仍待總司令四選一，未解除。`market.yml`今日(10/2)台股主/
補救班次（09:13/10:41 UTC）：本輪查詢時間15:3x UTC（23:3x台北），`gh
run list --workflow=market.yml`實測仍只有1筆run（`36949207832`，
2026-10-02T01:05:01Z，前一天美股班次延遲落地），**尚未到round696/697
訂的17:49 UTC升級判斷時間點（還差約2小時16分）**，沿用既定分支不升級，
留給下一輪。`紙.一`／`先.七-二`仍待該批次落地才能inception，未解除。
`先.七-一`／`先.六-四`（Shioaji）：`data/quotes_sinopac.json`10/2收盤
快照仍`connected:false`、`checked_at`=13:45:02（收盤檢查點），
`research/.live_state_sinopac.json`mtime仍停09-30 13:45（10/1、10/2
兩個交易日皆未更新），與round697結論一致，未解除。

**本輪新增診斷（針對round697留下的未解之問「本機網路為何連續3天在
類似長窗口異常、晚間自行恢復」，只讀查，不碰凍結區）**：①Windows
`System`事件記錄檔篩選WLAN-AutoConfig／RST Middleware／Kernel-Boot
相關事件，**最近一筆是9/24與9/16，與本輪關注的10/1～10/2異常窗口
（00:02~23:57）完全不重疊**，排除「本機重開機/網卡重啟」這個假設。
②`tailscale status`查詢當下（23:3x台北，已在異常窗口外）顯示連線
正常、`alpha-pc`為online狀態、Funnel仍開啟，`Get-NetAdapter`顯示
Ethernet與Tailscale Tunnel皆`Up`，**當下沒有異常可供比對**（異常窗口
是日間特定時段，本輪查詢時已過了恢復時間）。**誠實結論：本輪嘗試
但沒有查到新線索**，排除了「重開機」這個假設，但真正根因（本機
DNS/網路堆疊在白天特定長窗口異常、晚間自癒）仍待下一輪在異常窗口
內（例如明天上午）即時查`Get-NetTCPConnection`／`ipconfig /displaydns`
或總司令檢查路由器/ISP側紀錄，超出本輪所能做的範圍。

`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），
凍結.二期間暫停補件。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300）；
工具修正本輪未改動任何原始碼（僅讀取診斷＋archive舊state條目）；
`git status --short -- research/backtest/ research/validation/
research/adjust.py research/pit.py research/trial_registry.py`輸出為空
（十三節限定清單內檔案無殘留未commit編輯，本輪亦未touch）。US軌本身
`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子家族結案狀態未變，
`CALIBRATION_PROBE.md`唯一指名給US軌的操作指令（#47/#52重跑）先前
輪次已複核確認2026-09-04早已結案、無殘留，無清楚剩餘的全新機制候選，
且凍結.二期間本來就不得登記新alpha試驗。驗證：`run_detached.py
status`running=0（162筆歷史，無job待收成）；`trial_registry.py
--check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（409列，另有FDR對照表
33列，最大編號#407，本輪未新增判定）；`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（非本輪動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中（目前：39件）」，逐行核對（精確計算表格
資料列=39，排除表頭與分隔列）與round696/697一致，本輪未變動。

**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成
或無新內容；21條`- [!]`逐一核對均未到解除時間（`金流一.4`得到一層
更精確的子結論——卡關原因是品質篩選而非資料缺失，但不改變BLOCKED
狀態）；針對round697留下的網路異常根因未解之問做了一次新嘗試（排除
重開機假設），未查到決定性新線索；US軌本身查無可推進的新alpha試驗
工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，
不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
十三節限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證
（`gh run list`查既有workflow紀錄、`tailscale status`、
`Get-WinEvent`／`Get-NetAdapter`查本機系統狀態），無資料抓取類API
呼叫，未讀取或輸出任何金鑰／憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪
已append一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：39件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選FUT軌（round696=10-02 21:3x，三軌中最舊）；開工前先重新
檢查`- [ ]`有無新交辦、`market.yml`今日09:13/10:41 UTC批次是否已過
17:49 UTC上限仍缺席（若是則依round696既定分支升級為「需總司令手動
Run workflow」）、`金流一.4`／`外部一改.2`tick累積進度、`先.七-一`
是否已到10/5下一交易日可累積新樣本。凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除。完整見`REPORT.md`第698輪心跳、
`PENDING_QUEUE.md`「金流一.4」「先.七-一」「維運.market.yml」相關
條目、`research/AWAITING_REVIEW.md`。
