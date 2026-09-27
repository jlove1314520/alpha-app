# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的 65 則已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-27T15:3x+08:00（馬拉松第643輪，研究帽）**——取鎖乾淨
（cycle`20260927-153037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=39條阻塞中，
逐一核對開頭標記可能已解除的條件均未到解除時間（金流一.4法人史累積、
資料源一.3待總司令領key、外部一改.2 tick累積等）。**佇列深度自檢**：
`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`轉向.一`結果
尚未登記），本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：TW
round642=09-27 14:3x／US round641=09-25 00:3x／**FUT round640=09-24
23:3x（最舊，逾2.5天未碰）**——依輪替選FUT。**核心查證**：`git status`
確認`research/adjust.py`／`universe.py`／`audit_q2_ipo_pre_listing.py`
等`CLAUDE.md`十三節單一寫入者限定檔案**已由互動視窗commit**（`36bf7fab`
「查.二放行」），無殘留未commit編輯，銜接round642留下的「下一輪先確認
是否已commit」待辦。`PENDING_QUEUE.md`核對：「查.二放行」①-⑦全部已
完成並標`[x]`（TPEx上櫃日期893檔補齊、72檔查無上市日排除嚴格宇宙、
`common_stock_only()`興櫃排除、#398/#399影響評估：持股天數落在上市前
興櫃比例4.85%/1.92%、報酬貢獻+0.34%/-0.22%、`check_adjusted_series_
anomalies()`日期相依門檻已改、`CashIncreaseSubscriptionRate`單位疑義
維持不修改公式、已push停下等Cowork核對）；「新.二結案」／「紙.一」
（基礎設施完成，等2026-10第一個交易日啟動）皆已完成。`data/rate_limit_
state.json`確認FinMind`blocked_until`=2026-09-27T08:22:52 UTC（本輪
07:32查詢時仍BLOCKED，約差51分鐘），非本輪可推進資料抓取的理由。
`run_detached.py status`：`running=0`（162筆歷史，無job待收成）。
`AWAITING_REVIEW.md`「等待中」表格核對**11件**（表頭與列數一致），
本輪未變動——皆為等Cowork/總司令裁示的項目，非FUT軌可推進。**本輪
誠實結論**：`凍結.二`允許的四類工作（稽核重跑／資料抓取／工具修正／
驗.二重跑）先前輪次已全部完成或被外部條件阻擋，`查.二放行`為前一輪
互動視窗新增的工作已完整結案並push，FUT軌本身查無可推進的新工作
單位——依`CLAUDE.md`「零之一」白名單第7條精神（佇列真的空了）記錄後
結束本輪，不硬湊候選、不觸碰`凍結.二`禁止的新alpha試驗、不搶碰十三節
限定檔案。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（402列，本輪純查證未新增判定，不觸發`register_trial()`）。
`validation/holdout.py::is_holdout_consumed()`本輪讀取為`True`（H.一
單次解鎖已於2026-09-27正式消耗，非本輪新增動作，僅讀取核對，未再次
解鎖）。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改`research/backtest/`／`research/validation/`／`research/adjust.py`
／`research/pit.py`／`trial_registry.py`等`CLAUDE.md`十三節限定清單內
任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增
外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**。
**等待審閱：11件**（查.一daily_price日期欄位／考.一2007-2014單發檢定／
登記.二主動式ETF／資料源.主動ETF／源.二主動ETF條款／UX.一介面改版／
查.一排程健康診斷／乾.三看門狗健檢／驗.五+修.六基準汙染診斷／紙.一
70/30基礎設施／查.二放行TPEx補齊，完整清單見`AWAITING_REVIEW.md`）。
**下一輪任一軌接手**：FinMind額度預計08:22台北解除，解除後三軌皆可用
於既有查證工作（若有）；`#50`持續被動等待tick累積至20；`轉向.一`凍結
在等Cowork核對`查.二放行`與其餘10件等待審閱項目，此前不解凍、不補新
alpha試驗；依輪替下一輪建議選US軌（round641=09-25 00:3x，三軌中最舊）。
完整見`REPORT.md`第643輪心跳、`PENDING_QUEUE.md`「查.二放行」條目、
`AWAITING_REVIEW.md`。

---

**最後更新：2026-09-24T23:3x+08:00（馬拉松第640輪，維運帽）**——取鎖乾淨。研究帽：交辦優先於自走，開工讀`PENDING_QUEUE.md`：`- [ ]`=0、`- [!]`逐項核對。收成上一輪(639)投遞的job `20260924-224213-1281`（`f52w_2007_extension_resume`，finished exit=0、expect_exists=True）：資料.一300/300完成，互動視窗CC已接續完成宇.一/宇.二/規.五/閘門.一補充（commit `7119c232`，閘門六項全PASS）。**本輪動作＝把過期的`- [!]`標記對齊事實**：`資料.一`、`閘門.一`改`- [x]`（保留歷史阻塞文字）；轉向.一單發檢定條目補註「等資料.一」阻塞已解除，現行唯一阻塞是總司令裁示的「閘門.一後停下等Cowork核對」（零之一白名單第2類，自走不得放行）；`AWAITING_REVIEW.md`新增一列（原本只列重開機查核1件，漏列閘門.一等Cowork核對，N由1→2）。凍結.二仍生效，無新alpha試驗、N不變；`is_holdout_consumed()`=False。FUT軌本輪無獨立可推進項（凍結.二：不得登記新alpha試驗；期貨軌無稽核/資料類待辦）。

**最後更新：2026-09-24T05:3x+08:00（馬拉松第636輪，研究帽）**——取鎖乾淨
（cycle`20260924-053037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`- [ ]`=0（`grep -n "^- \[ \]"`全文0筆命中，`閘門.一`仍標`- [!]`），逐一核對
`- [!]`阻塞項開頭標記皆未到解除時間。**佇列深度自檢**：`- [ ]`=0（<12
下限），依`CLAUDE.md`十四節【凍結.二】本階段暫停佇列深度補件，不重掃
備援來源。三軌時間戳：TW round635=09-24 04:3x／US round634=09-24
03:3x／**FUT round633=09-24 02:3x（最舊）**——依輪替選FUT。**核心查證**：
`data/rate_limit_state.json`顯示FinMind於2026-09-23T20:37:44 UTC再次
命中402，`blocked_until`=1790203064.30（換算台北2026-09-24T06:37:44），
本輪05:31查詢時**仍BLOCKED，約差66分鐘**——round635記錄的「額度已解除、
另一行程接手續抓」是暫時現象，該行程續抓到`fetched_ids`=222後又再次
撞額度（`failed_ids`由round635的35增至41），目前無lock檔案（確認
`research/.f52w_2007_extension.lock`不存在），非有行程正在跑，是被
FinMind硬性擋住。`run_detached.py status`：`running=0`（160筆歷史，
無job待收成）。`git status`僅例行排程檔案8個（`audit_report.json`/
`factory_stability*`/`connectivity_check.log`等），無conflict標記、
無孤兒未commit產出。**逐一核對`凍結.二`允許的四類工作現況**：稽核
重跑（驗.一第4點續剩餘8支＋剩餘16支）皆已grep確認標`[x]`完成並登記
#387-393；資料抓取被FinMind額度硬性擋住（見上，還需約66分鐘）；工具
修正（修.三額度錯誤bug＋並發鎖）已由互動視窗CC完成並commit
（`a80b27f7`，本輪`git status`確認`research/factors.py`無未commit
修改）；驗.二開盤到收盤重跑（`驗.二續`）已grep確認標`[x]`完成並登記
`TRIALS_LEDGER.md`#394（FAIL，第3關參數高原未過）。`AWAITING_REVIEW.md`
「等待中」表格確認**0件**。**本輪誠實結論**：四類允許工作皆已完成或
被外部額度阻擋，FUT軌本身查無可推進的新工作單位（`#50`容量受限小型股
方向tick累積13/20，依裁示不重複回報進度細節）——依`CLAUDE.md`「零之
一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰
`凍結.二`禁止的新alpha試驗。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（399列，本輪純查證未新增判定，
不觸發`register_trial()`）。`validation/holdout.py::is_holdout_consumed()`
開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改`research/backtest/`／`research/validation/`
／`trial_registry.py`等`CLAUDE.md`十三節限定清單內任何原始碼（僅讀取
核對＋改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`Get-Process`等效檢查）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**
（僅`閘門.一`標`- [!]`，BLOCKED於續抓完成）。**等待審閱：0件**。**下一輪
任一軌接手**：FinMind額度預計06:37台北解除，解除後才可繼續續抓
f52w/dividend 2007-2014延伸資料（目前222/300，還差78檔，但`failed_ids`
已41筆需一併檢視是否為永久性失敗）；`閘門.一`待續抓完成後才可執行五項
資料品質檢查；`#50`持續被動等待tick累積至20（13/20）；依輪替下一輪
建議選US軌（round634=09-24 03:3x，三軌中最舊）。完整見`REPORT.md`
第636輪心跳、`PENDING_QUEUE.md`「閘門.一」條目、
`data/f52w_2007_extension_checkpoint.json`。

---
