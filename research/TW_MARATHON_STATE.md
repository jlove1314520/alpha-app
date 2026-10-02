# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

---
**最後更新：2026-10-01T20:0x+08:00（馬拉松第691輪，維運帽）**——取鎖乾淨
（cycle`20261001-200037`）。**注意：上一輪（round688）結束於09-30 14:0x，
距本輪隔了約30小時——查`research/data/quota_throttle_state.json`：
`marathon.daily.skip_signal=39/skip_interval=1/run=1`、
`consecutive_no_progress=2`，是額度節流機制正常運作（09-30 16:0x~10-01
19:xx這段`git log`滿版`Marathon cycle log 自動更新（節流跳過）`），不是
卡死，[自行裁量]不需額外處理，照常開工。三軌時間戳：TW round688=09-30
14:0x（本輪選定，三軌中最舊）／US round689=09-30 15:0x／FUT round690=
09-30 16:0x。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項，與round679~690持平）；
`grep -c "^- \[!\]"`=13（持平）。逐一核對13條`- [!]`阻塞項：`金流一.4`
實測`data/sector_flow.json``meta.trading_days_available`**18**（較
round685~690的17＋1）、`windows_missing_days.20`**2**（較13↓1），20日
視窗還差2個交易日，未解除；`外部一改.2`／`研究.c`共用tick累積
`ls research/data/ticks/*.parquet`實測仍**15/20**（與round688持平），
未解除；`本地AI摘要(Breeze-7B)`四選一仍待總司令裁示，屬白名單第6條法
遵疑慮，未解除；`紙.一`：今日已是2026-10-01（首個交易日），但
`data/paper_7030.json`仍`started:false`——`sector_flow.json`
`generated_at`=2026-10-01T08:42（晨間排程，處理的是前一交易日09-30收盤
資料，`date=20260930`），market.yml當日收盤後那一輪（處理10-01收盤價）
本輪查詢時間20:0x尚未見其commit寫入`data/price_history.json`含10-01
資料，紙.一的inception要等那一輪跑過，非馬拉松可代做，未解除；其餘9條
逐一核對開頭標記（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`稽核.三`／`稽核.五`／`結案.一`／`常備.9`／`群益API(合併)`皆等總司令/
Cowork裁示或親自操作；`研究.c`同金流一.4/外部一改.2共用的資料累積阻塞），
均未到解除時間。`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆
為條件敘述提及、非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：
`- [ ]`=0（<12下限），凍結.二期間暫停補件，不硬湊alpha試驗候選。**逐一
核對凍結.二允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成
並登記；資料抓取（`資料.一`已完成300/300）；工具修正已由互動視窗commit
（`git log`本輪查詢區間內唯一互動視窗commit為`deb160a8d`「先.四-二/三：
供給緊縮衛星策略單發執行完成，判定FAIL（#406），結案寫入墓園」，屬互動
視窗自行裁量工作非馬拉松代做範圍）；`git status --short --
research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單內
檔案無殘留未commit編輯）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`
結案狀態未變，`CALIBRATION_PROBE.md`給TW軌的操作指令（#77/#79/#91、
portfolio_multifactor_v2 300檔重跑）先前輪次已複核確認早已完成並登記，
無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新alpha試驗。驗證：
`run_detached.py status` running=0（162筆歷史，無job待收成）；
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（408列，另有FDR對照表33列，最大編號#406，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：28件）」（較round685~
690的27件＋1：新增`先.四`供給緊縮衛星策略結案條目，屬互動視窗本輪工作、
非馬拉松動作），逐行核對28筆資料列一致，本輪未變動。**本輪誠實結論**：
交辦佇列0條`- [ ]`；凍結.二允許的四類工作皆已完成或無新內容；13條
`- [!]`逐一核對均未到解除時間（`金流一.4`20日視窗差距由3縮為2，但仍未
解除；tick累積仍15/20；本地AI摘要仍待總司令四選一裁示；紙.一雖已到
2026-10-01但當日收盤資料尚未經market.yml寫入）；TW軌本身查無可推進的
新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束本輪，不
硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定檔案、不代做
互動視窗保留項目。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋
archive舊state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本
檔案、`git status`/`git log`、`run_detached.py status`、
`trial_registry.py --check`、`holdout.py`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條`- [ ]`未開始**。**等待審閱：28件**
（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：依輪替
下一輪建議選US軌（round689=09-30 15:0x，三軌中最舊）；開工前先重新檢查
`- [ ]`有無新交辦、`金流一.4`20日視窗是否已補到0（目前差2個交易日）、
`外部一改.2`tick累積15/20還差5日、`本地AI摘要(Breeze-7B)`四選一是否已
裁示、`紙.一`是否已有`data/paper_7030.json`的`started:true`紀錄。凍結.
二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見`REPORT.md`
第691輪心跳、`PENDING_QUEUE.md`「金流一.4」「本地AI摘要(Breeze-7B)」
「紙.一」條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-01T23:1x+08:00（馬拉松第694輪，維運帽）**——取鎖乾淨
（cycle`20261001-230037`）。三軌時間戳（開工前）：TW round691=10-01 20:0x
（最舊，本輪選定）／US round692=10-01 21:0x／FUT round693=10-01 22:0x。
開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=1（round693之後、本輪
開工前新出現的唯一一條：`先.八-一 產業層級缺貨可行性盤點`）。

**並行碰撞記錄（誠實揭露，非隱藏錯誤）**：本輪依交辦優先原則接手
`先.八-一`，獨立完成全部查證（下載`data.gov.tw`全平台資料集目錄73,496列
逐列比對、對命中候選`requests.get()`實測驗證三個官方資料源的可及性），
寫出`docs/FEASIBILITY_industry_shortage.md`與`docs/PREREG_DRAFT_
industry_shortage.md`草案，**正要更新`PENDING_QUEUE.md`狀態時發現檔案
已被外部修改**（`Edit`工具報錯"File has been modified since read"）——
重新讀取後確認：**另一個並行session（互動視窗，commit`897a56697`「先.
八-一：產業層級缺貨可行性盤點與事前登記草案」＋`34564f8fc`「先.八收尾：
一、三完成登記」）已經在本輪執行期間獨立完成並提交了同一條目**，其結論
與本輪查到的高度重疊但更周全（額外發現"存貨率"≠"存貨價值/銷售價值"
自算比約10個百分點落差、約9個貨品別類別可及 vs 本輪查到11個——差異
可能來自命名規則枚舉方式不同，未深究）。**處理方式**：`git checkout --`
還原本輪覆寫的兩個docs檔案為已提交版本，不覆蓋對方更完整的成果；不重複
修改`PENDING_QUEUE.md`（已是`[x]`）；不寄望自己的草稿，誠實記錄這次
碰撞而非默默蓋過。**根因**：`PENDING_QUEUE.md`裡程碑本身沒有「認領中」
標記機制，兩個並行執行個體（馬拉松與互動視窗）都看到同一條`- [ ]`就都
去做了——這跟`CLAUDE.md`十三節「核心研究檔案單一寫入者」要解決的是同一
類問題（並行寫入衝突），但十三節限定清單只涵蓋`research/backtest/`等
回測引擎核心檔案，不涵蓋一般`docs/`與`PENDING_QUEUE.md`本身的交辦項
認領，本次碰撞的檔案不在十三節清單內，不算違反該節規則，但值得記錄
作為未來可能擴充「認領」機制的參考案例，不在本輪提案（屬架構變更，
需總司令核准）。

重新查詢`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（先.八-一已由並行
session標`[x]`）；`grep -c "^- \[!\]"`=18（較round693的14＋4：新增
`維運.先.六-二後續一`／`維運.market.yml今日(10/1)排程兩次觸發皆缺席`／
`先.七-一`／`先.七-二`，皆為round693 FUT軌維運帽發現後互動視窗/後續輪次
新增的條目，非本輪漏做）。逐一核對18條`- [!]`：`金流一.4`
`sector_flow.json``meta.trading_days_available`仍**18**、
`windows_missing_days.20`仍**2**，未解除；`外部一改.2`／`研究.c`tick
累積`ls research/data/ticks/*.parquet`實測仍**15/20**，未解除；`本地AI
摘要(Breeze-7B)`仍待總司令四選一，未解除；`維運.market.yml今日(10/1)
排程兩次觸發皆缺席`：本輪查詢時間23:1x，`gh run list --workflow=market.yml`
實測最新run仍是`createdAt=2026-10-01T00:39:54Z`（昨晚美股班次），10/1
17:00／18:30兩個台北班次查詢時已過排定時間6~8小時仍完全缺席，**問題
持續未解除**；`先.六-四`／`先.七-一`／`先.七-二`：本輪查詢23:1x仍是
10/1，未到10/2台北09:00開盤，均未解除；`維運.先.六-二後續一`：
`.gitattributes`renormalize提案仍待總司令裁示，本輪不擅自執行；其餘
10條均為等總司令/Cowork裁示或其他外部條件，皆未到解除時間。`grep -c
"凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、非實際
宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），凍結.
二期間暫停補件。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／驗.二
重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300，
`先.八-一`資料源可行性盤點屬此類，已由並行session完成）；工具修正本輪
僅改狀態檔+archive，未修改任何原始碼；`git status --short --
research/backtest/ research/validation/ research/adjust.py
research/pit.py research/trial_registry.py`輸出為空（十三節限定清單內
檔案無殘留未commit編輯，本輪亦未touch）。TW軌本身`TW_LEADS.md`/
`STRATEGY_GRAVEYARD.md`結案狀態未變，`CALIBRATION_PROBE.md`給TW軌的
操作指令（#77/#79/#91、portfolio_multifactor_v2 300檔重跑）先前輪次
已複核確認早已完成並登記，無清楚剩餘的全新機制候選，且凍結.二期間本來
就不得登記新alpha試驗。驗證：`run_detached.py status`running=0（162筆
歷史，無job待收成）；`trial_registry.py --check`（`PYTHONIOENCODING=
utf-8`）exit=0 PASS（409列，另有FDR對照表33列，最大編號#407，本輪未
新增判定）；`validation/holdout.py::is_holdout_consumed()`讀取為`True`
（非本輪動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：34件）」
（較round691的28件+6：並行session`先.八`系列三項結案登記），本輪僅讀取
核對不變動。**本輪誠實結論**：交辦佇列原有1條`- [ ]`已被並行互動視窗
session獨立完成並提交，本輪查到時已結案，已正確還原自己重複的草稿、
未覆蓋對方成果；凍結.二允許的四類工作皆已完成或無新內容；18條`- [!]`
逐一核對均未到解除時間；TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神記錄後結束本輪，不硬湊候選、不觸碰凍結.二
禁止的新alpha試驗、不搶碰十三節限定檔案、不代做互動視窗保留項目。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定
清單內任何原始碼，全程零新增外部研究類API呼叫（本輪查證`先.八-一`時
呼叫過`data.gov.tw`／`service.moea.gov.tw`／`opendata.customs.gov.tw`／
`web02.mof.gov.tw`等官方公開端點，但成果已被並行session的版本取代，
本輪最終提交內容不含這些查證結果，僅保留本段文字記錄過程；其餘驗證
動作為既有`.json`/`.md`帳本檔案讀取、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`holdout.py`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行（track"marathon"）。**交辦
佇列還剩0條`- [ ]`未開始**。**等待審閱：34件**（與`AWAITING_REVIEW.md`
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌
（round692=10-01 21:0x，三軌中最舊）；開工前先重新檢查`- [ ]`有無新
交辦（**開工前務必先確認是否有其他並行session正在處理同一條，避免
重複勞動**）、`market.yml`今日排程是否已補跑、10/2開盤後`先.六-四`／
`先.七-一`／`先.七-二`是否可解除、`金流一.4`／`外部一改.2`tick累積
進度。凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除。完整見
`REPORT.md`第694輪心跳、`PENDING_QUEUE.md`相關條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-10-02T22:3x+08:00（馬拉松第697輪，TW軌，維運帽）**——取鎖
乾淨（cycle`20261002-223037`）。三軌時間戳（開工前）：TW round694=10-01
23:1x（最舊，本輪選定）／FUT round696=10-02 21:3x／US round695=10-02
20:3x。開工先讀`PENDING_QUEUE.md`：`grep -c "^- \[ \]"`=0（無未開始交辦
項，與round694~696持平）；`grep -c "^- \[!\]"`=21（持平，round694的18
加round695/696新增的3條）。

**本輪實質產出：修正並收斂「先.七-一／先.六-四 Shioaji連線失敗」的根因
診斷**（詳見`PENDING_QUEUE.md`「先.七-一」條目下方本輪補記）：
1. 直接讀`shioaji.log`（Rust核心append-only log）確認：10/1、10/2兩個
   完整交易日**零次**成功連上（最後一次成功是09-30T00:31 UTC的
   `contracts_v2::traffic`backend response；之後兩天共約300次登入嘗試
   全部卡在「get site info」這一步，失敗點早於帳密/token驗證，**排除
   憑證／API key到期**這個假設方向）。
2. **更正round696（21:3x）對`external_connectivity.jsonl`的讀數**：
   round696稱「今天259筆全部`internet.ok=True`」，本輪用`results.
   internet.ok`欄位依`ts`前綴嚴格篩選2026-10-02重新逐筆核對兩次（結果
   一致）：**實際272筆中218筆`False`（80%）**，連續壞區間
   **00:02～18:07台北**（18:12起才轉全部`True`，正好銜接round695/696
   查詢時間20:3x/21:3x，round696看到的是已恢復後的尾段，不是全天）。
   往前核對：10/1同樣288筆中240筆`False`（83%，幾乎整天）；09-30則
   73/261筆`False`（28%，晚間才開始，範圍小得多）。壞區間`fail_streak`
   曾達106，`tailscale`同步壞，確認是本機對外連線真的有長時間異常，
   不只是round696說的「這支腳本沒測對網域」。
3. 這個異常窗口（00:02~18:07）完整覆蓋Shioaji盤中失敗時段（09:00~
   13:30台北），也完整覆蓋`維運.AlphaData三日DNS解析失敗`條目原本認定
   的「15:30窄窗口」——已在該條目下方補記交叉參照：15:30很可能只是
   落在這個更大異常窗口裡的一個點，不是獨立現象，但本輪未越權合併兩
   條目的判定、未碰`fetch.py`凍結區。
4. 先.七-一「失敗→依序查」三步執行結果：本機網路＝有異常（**由「已
   排除」改回「待查」**）；憑證/API key到期＝已排除（失敗點在site
   info之前）；永豐維護公告＝round696已三來源查無。**不更動先.七-一/
   先.六-四的BLOCKED狀態與既有解除條件**（仍等10/5樣本或總司令查永豐
   帳戶狀態），本輪只修正「網路已排除」這個子結論的事實依據，並留下
   「為何本機網路連續3天都在類似長窗口異常、晚間自行恢復」這個未解之
   問供總司令或下一輪查Windows事件記錄/排程/VPN設定。

逐一核對其餘`- [!]`阻塞項（與round696一致，本輪僅重複驗證，未發現
新解除）：`金流一.4``sector_flow.json``meta.trading_days_available`仍
**18**（因今日10/2台股主班次`market.yml`截至查詢時間14:31 UTC仍缺席，
尚未到round696訂的17:49 UTC升級判斷時間點，不重複升級，沿用既定分支）；
`外部一改.2`／`研究.c`tick累積`ls research/data/ticks/*.parquet`實測仍
**15/20**，未解除；`本地AI摘要(Breeze-7B)`仍待總司令四選一，未解除；
`紙.一`／`先.七-二`仍待market.yml含10/2收盤資料的那一輪落地，未解除。
`grep -c "凍結.二解除" PENDING_QUEUE.md`=4，逐行核對皆為條件敘述提及、
非實際宣告解除，凍結.二仍生效。**佇列深度自檢**：`- [ ]`=0（<12下限），
凍結.二期間暫停補件。**逐一核對凍結.二允許的四類工作現況**：稽核重跑／
驗.二重跑先前輪次已全部完成並登記；資料抓取（`資料.一`已完成300/300）；
工具修正本輪未改動任何原始碼（僅讀取診斷＋補寫`PENDING_QUEUE.md`狀態
記錄，`TW_MARATHON_STATE.md`/`TW_STATE_ARCHIVE.md`屬狀態檔不在十三節
限定清單內）；`git status --short -- research/backtest/ research/
validation/ research/adjust.py research/pit.py research/
trial_registry.py`輸出為空（十三節限定清單內檔案無殘留未commit編輯，
本輪亦未touch）。TW軌本身`TW_LEADS.md`/`STRATEGY_GRAVEYARD.md`結案
狀態未變，無清楚剩餘的全新機制候選，且凍結.二期間本來就不得登記新
alpha試驗。驗證：`run_detached.py status`running=0（162筆歷史，無job
待收成）；`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（409列，另有FDR對照表33列，最大編號#407，本輪未新增判定）；
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（非本輪動作，
僅讀取核對）。`AWAITING_REVIEW.md`「等待中（目前：39件）」，與round696
一致，本輪未變動。**本輪誠實結論**：交辦佇列0條`- [ ]`；凍結.二允許的
四類工作皆已完成或無新內容；21條`- [!]`逐一核對均未到解除時間；TW軌
本身查無可推進的新alpha試驗工作單位；**本輪實質產出是Shioaji連線失敗
根因診斷的重大修正（網路排除結論被推翻，改為待查，並發現與AlphaData
DNS失敗條目可能同根因），已完整記錄進`PENDING_QUEUE.md`「先.七-一」與
「維運.AlphaData三日DNS解析失敗」兩個條目，未自行執行任何修復動作或
更動BLOCKED狀態**——依`CLAUDE.md`「零之一」白名單第7條精神記錄後結束
本輪，不硬湊候選、不觸碰凍結.二禁止的新alpha試驗、不搶碰十三節限定
檔案。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改
十三節限定清單內任何原始碼。全程新增外部呼叫僅限讀取性質驗證
（`requests.get()`即時重測兩個site-info網址、`gh run list`查
market.yml既有紀錄），無資料抓取類API呼叫，未讀取或輸出任何金鑰／
憑證內容。`PROGRESS_HEARTBEAT.jsonl`本輪已append一行。**交辦佇列還剩
0條`- [ ]`未開始**。**等待審閱：39件**（與`AWAITING_REVIEW.md`表格
列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選US軌（round695=
10-02 20:3x，三軌中最舊，須下一輪開工時重新比對三軌實際時間戳）；
開工前先重新檢查`- [ ]`有無新交辦、`market.yml`今日17:00台北班次是否
已過17:49 UTC上限仍缺席（若是則依round696既定分支升級判斷）、`金流
一.4`／`外部一改.2`tick累積進度、`先.七-一`根因是否有新線索（本機網路
連續3天異常窗口的成因）。凍結.二在總司令/Cowork明確寫「凍結.二解除」
前不解除。完整見`REPORT.md`第697輪心跳、`PENDING_QUEUE.md`「先.七-一」
「維運.AlphaData三日DNS解析失敗」「金流一.4」條目、
`research/AWAITING_REVIEW.md`。
