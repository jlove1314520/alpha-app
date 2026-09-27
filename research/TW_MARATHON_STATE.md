# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-27T14:3x+08:00（馬拉松第642輪，研究帽）**——取鎖乾淨
（cycle`20260927-143037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=2（驗.二第二部分／查.二放行）。**本輪主要發現：驗.二第二部分是
過期重複補件**——今天稍早hypothesis_queue軌道13:51做佇列深度補件時，
把這項當成「未做過的稽核類工作」補入，但`spillover_overlay_v1_o2c.py`
早在2026-09-24（3天前）就已完整重跑第2-9關並終局判定：commit`8ca6dad5`
登記為`TRIALS_LEDGER.md`#394，第3關參數密集高原未過（FAIL），
`STRATEGY_GRAVEYARD.md`已明文「#19在台股的兩種實現皆已窮盡並判死，
不建議再嘗試同一機制的其他變體」。已把`PENDING_QUEUE.md`該項改標`[x]`
並附完整出處，避免下一輪自走再次誤補同一項（詳見該檔案本項條目）。
**查.二放行本輪不動**：`git status`顯示`research/adjust.py`/`universe.py`/
`audit_q2_ipo_pre_listing.py`等CLAUDE.md十三節單一寫入者限定檔案有大量
未commit變更，`ls`實測mtime距本輪開工僅3~17分鐘（14:15~14:29），核對
`dev_queue_cycle.log`／`hypothesis_queue_cycle.log`確認本機兩條自走排程
同一時段皆為YIELD/未執行，判定是互動視窗CC session剛做的中途未完成
編輯（內容確認是`check_adjusted_series_anomalies()`日期相依門檻、
`universe.listing_date_lookup()`/`truncate_to_listing_date()`新增、
`CashIncreaseSubscriptionRate`單位查證等，皆對應查.二放行裁示的①③⑤⑥
項）。**[自行裁量，比照round613/623/625避讓先例]**：本輪不觸碰這些
限定檔案，避免搶寫或提交半成品程式碼；查.二放行本身也涉及裁示明文
「adjust.py屬十三節單一寫入者範圍由互動視窗執行」，自走軌道結構上就
不該碰。**佇列深度自檢**：修正後`- [ ]`=0（查.二放行仍`- [ ]`但正被
互動視窗處理中，非自走可推進項），凍結.二仍生效，不補新alpha試驗。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（未新增判定，本輪純佇列維運）。`is_holdout_consumed()`開工/收工前皆
`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／`research/adjust.py`
／`research/pit.py`／`research/trial_registry.py`任何原始碼，全程零
新增外部API呼叫（純`git`/`ls`/既有帳本讀取）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條可由自走推進**（查.二放行等互動
視窗完成）。**等待審閱：10件**（`AWAITING_REVIEW.md`表頭與實際列數
核對一致，本輪未變動；順道發現其中「新.二」一列今日已由【新.二結案＋
紙.一＋查.二放行】裁示回覆，但該列尚未搬移到「已結案審閱紀錄」表，
非本輪工作範圍，留給下一輪或該項原負責軌道搬移）。**下一輪任一軌接手**：先`git status`確認`research/adjust.py`等
檔案是否已由互動視窗commit——若已commit，查.二放行後續步驟（TPEx資料
校驗、common_stock_only()興櫃排除的下游影響評估等）才輪到自走接手；
若仍是未commit的編輯中狀態，繼續避讓；依輪替下一輪建議選FUT或US軌
（TW本輪已碰過）。完整見`REPORT.md`第642輪心跳、`PENDING_QUEUE.md`
「驗.二第二部分」條目更正。

---
**最後更新：2026-09-24T07:3x+08:00（馬拉松第638輪，研究帽）**——取鎖乾淨
（cycle`20260924-073037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（僅`閘門.一`標`- [!]`），逐一核對`- [!]`阻塞項開頭標記皆未到
解除時間。**佇列深度自檢**：`- [ ]`=0（<12下限），依`CLAUDE.md`十四節
【凍結.二】本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：US
round637=09-24 06:3x／FUT round636=09-24 05:3x／**TW round635=09-24
04:3x（最舊）**——依round637建議與輪替選TW。**核心查證**：`data/rate_
limit_state.json`顯示FinMind於2026-09-24T00:53:56 UTC**再次**命中402
（`blocked_at`），`blocked_until`=1790211236.62（換算台北
2026-09-24T08:53:56），本輪07:31查詢時**仍BLOCKED，約差83分鐘**——這是
一次**新**的封鎖（跟round637記錄的06:37:44台北解除時刻不同），代表額度
確實曾短暫解除過。**證據**：`f52w_2007_extension_checkpoint.json`確認
`fetched_ids`從round637記錄的222推進到**274**（`failed_ids`由41增至52），
證實額度解除後（06:37~06:53台北，約16分鐘窗口）有行程續抓52檔後才再次
撞額度；`research/.f52w_2007_extension.lock`目前**不存在**，確認該行程
已結束（非仍在跑），現在單純是被FinMind硬性擋住。`run_detached.py
status`：`running=0`（160筆歷史，無job待收成）。**逐一核對`凍結.二`允許
的四類工作現況（同round634~637方法論，本輪對TW軌重新確認）**：稽核
重跑（驗.一第4點續剩餘8支）已grep確認標`[x]`完成並登記#387-393；資料
抓取被FinMind額度硬性擋住（見上，還需約83分鐘）；工具修正（修.三額度
錯誤bug＋並發鎖）已由互動視窗CC完成並commit（`a80b27f7`，本輪`git
status`確認`research/factors.py`無未commit修改）；驗.二開盤到收盤重跑
已grep確認標`[x]`完成並登記`TRIALS_LEDGER.md`#394（FAIL）。
`AWAITING_REVIEW.md`「等待中」表格確認**0件**（與round637一致）。
**其餘被動等待項覆核**：`#50`容量受限小型股tick累積`ls research/data/
ticks/*.parquet`實測**13/20**（較round625持平，無新交易日新增，依
2026-09-15裁示不重複回報細節）；`金流一.4`法人歷史仍15個交易日、
20日視窗還需5個交易日，未變。**本輪誠實結論**：四類允許工作皆已完成
或被外部額度阻擋，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、
不觸碰`凍結.二`禁止的新alpha試驗。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增判定，
不觸發`register_trial()`）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改`research/backtest/`／`research/validation/`
／`trial_registry.py`等`CLAUDE.md`十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**（僅`閘門.一`標`- [!]`，
BLOCKED於續抓完成）。**等待審閱：0件**。**下一輪任一軌接手**：FinMind
額度預計08:53台北解除，解除後才可繼續f52w/dividend 2007-2014延伸抓取
（目前274/300，還差26檔，`failed_ids`52筆需一併檢視是否為永久性失敗）；
`閘門.一`待續抓完成後才可執行五項資料品質檢查；`#50`持續被動等待tick
累積至20（13/20）；依輪替下一輪建議選US軌（round637=09-24 06:3x，
三軌中最舊）。完整見`REPORT.md`第638輪心跳、`PENDING_QUEUE.md`「閘門.
一」條目、`data/f52w_2007_extension_checkpoint.json`。

---
**最後更新：2026-09-24T04:3x+08:00（馬拉松第635輪，研究帽）**——取鎖乾淨
（cycle`20260924-043037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（僅`閘門.一`標`- [!]`），逐一核對開頭標記皆未到解除時間，僅
`資料.一`與`閘門.一`的解除條件（FinMind額度封鎖`blocked_until`）已到期
（見下）。**佇列深度自檢**：`- [ ]`=0（<12下限），依`CLAUDE.md`十四節
【凍結.二】本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：TW
round632=09-24 01:3x（最舊）／FUT round633=09-24 02:3x／US
round634=09-24 03:3x——依輪替選TW。**核心查證**：`data/rate_limit_
state.json`顯示FinMind`blocked_until`=1790194899.09（換算台北
2026-09-24T04:21:39），本輪04:31取鎖時**額度已解除約10分鐘**——但
`research/.f52w_2007_extension.lock`（未追蹤檔）內容為`163704|
1790194942.50|unknown`，`Get-Process -Id 163704`確認**該PID是活躍的
python行程**（啟動時間04:22:21，剛好緊接額度解除時刻），判定另一
排程（依`閘門.一`條目文字為hypothesis_queue軌）已搶先接手續抓，
`research/data/f52w_2007_extension_checkpoint.json`確認`fetched_ids`
已從round633記錄的169**推進到199**（`failed_ids`=35），證實該行程
正在正常運作中。**[自行裁量，比照round613/623/625避讓先例]**：本輪
不重複執行`f52w_2007_extension.py`（會撞檔案鎖且浪費FinMind額度），
避免跟活躍行程搶佔同一份checkpoint。**逐一核對`凍結.二`允許的四類
工作現況**：稽核重跑（驗.一第4點續剩餘8支）已於round624完成並登記
#387-393；資料抓取正被上述活躍行程處理中（非本輪可重複執行）；工具
修正（修.三額度錯誤bug＋並發鎖）已由互動視窗CC完成並commit
（`a80b27f7`，`git log`/`git status`確認`research/factors.py`無未
commit修改）；驗.二開盤到收盤重跑已於round625~633期間完成並登記
`TRIALS_LEDGER.md`#394（FAIL）。`AWAITING_REVIEW.md`「等待中」表格
確認**0件**（與round634一致）。**本輪誠實結論**：四類允許工作皆已
完成或正被其他活躍行程處理，`凍結.二`禁止開新alpha試驗、佇列深度
補件規則暫停，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之
一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不
搶寫其他行程正在使用的檔案。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增
判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前
皆確認`False`。`run_detached.py status`：`running=0`（160筆歷史，
無job待收成）。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，未修改`research/backtest/`／`research/validation/`／
`trial_registry.py`等CLAUDE.md十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀
既有`.json`/`.md`帳本檔案、`git status`/`git log`、`Get-Process`、
`run_detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未
開始**（僅`閘門.一`標`- [!]`，BLOCKED於續抓完成，非可獨立推進項）。
**等待審閱：0件**。**下一輪任一軌接手**：續抓199/300檔（活躍行程
持續中，預計還需1-2輪、約2-4小時補齊剩餘~101檔，屆時`閘門.一`才可
執行五項資料品質檢查）；`#50`持續被動等待tick累積至20；依輪替下一輪
建議選FUT軌（round633=09-24 02:3x，三軌中最舊）。完整見`REPORT.md`
第635輪心跳、`data/f52w_2007_extension_checkpoint.json`。



（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪、
第621輪、第622輪、第623輪、第624輪、第632輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
