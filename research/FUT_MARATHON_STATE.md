# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-27T21:3x+08:00（馬拉松第649輪，維運帽）**——取鎖乾淨
（cycle`20260927-213037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條阻塞中
（與round646/647/648一致）。逐一核對15條`- [!]`阻塞項開頭標記是否解除：
`金流一.4`重跑`build_sector_flow.py`（零額外請求，只讀既有
`institutional_history.json`）確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**（與round647/648一致，round646的
「17」誤記已由round647查明並更正），20日視窗仍差4個交易日，未解除；
`外部一改.2`tick累積`ls research/data/ticks/*.parquet`實測仍**13/20**
（今日09-27週日無新交易日tick，未解除）；其餘13條逐一核對，均為等
總司令/Cowork裁示或其他外部條件，皆未到解除時間。**佇列深度自檢**：
`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（未見「凍結.
二解除」字樣），本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：
TW round648=09-27 20:3x／US round647=09-27 19:3x／**FUT round646=09-27
18:3x（最舊）**——依輪替選FUT。**核心查證**：`data/rate_limit_state.json`
確認FinMind`blocked_until`=2026-09-27T08:22:52 UTC，本輪13:31 UTC（台北
21:31）查詢時額度已解除逾5小時，但`資料.一`／`閘門.一`皆已於round640
完成300/300，無待續抓工作，額度狀態不觸發新工作單位。`run_detached.py
status`：`running=0`（162筆歷史，無job待收成）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（402列，本輪純查證未新增判定）。
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（H.一單次
解鎖已於09-27消耗，非本輪新增動作，僅讀取核對）。**逐一核對`凍結.二`
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記
（`驗.一第4點續（剩餘8支）`／`（剩餘16支）`皆已grep確認標`[x]`）；
資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正（修.三/修.六/
修.七）已由互動視窗commit；`git status`確認`research/backtest/`／
`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯。FUT軌本身`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`回顧：個股期貨
橫斷面調查線（round341-358）與trend/oi組合嘗試（round361-399）皆已
窮盡並結案，`MARATHON_PROTOCOL.md`第3節列出的期貨假說類別已全數至少
測過一個變體，無清楚剩餘的「全新機制」候選，且`凍結.二`期間本來就不
得登記新alpha試驗。`AWAITING_REVIEW.md`「等待中」表格核對**15件**
（表頭與列數一致，與TW round648記錄的15件相符，本輪未變動）。**本輪
誠實結論**：四類允許工作皆已完成或無新內容，`- [!]`15條逐一核對均未
到解除時間，FUT軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之一」
白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰
`凍結.二`禁止的新alpha試驗、不搶碰十三節限定檔案。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何
原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API
呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`ls`，唯一寫入
動作是重跑`build_sector_flow.py`——該腳本零額外外部請求，只讀repo內
既有檔案，輸出與既有`sector_flow.json`/`PENDING_QUEUE.md`倒數文字內容
一致無實質變化，僅`generated_at`時間戳更新）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**。**等待審閱：15件**（與
`AWAITING_REVIEW.md`「等待中」表格列數一致）。**下一輪任一軌接手**：
依輪替下一輪建議選US軌（round647=09-27 19:3x，三軌中最舊）；凍結.二
在總司令/Cowork明確寫「凍結.二解除」前不解除，不補新alpha試驗；
`金流一.4`還需4個交易日（20日視窗）；`外部一改.2`tick累積仍13/20。
完整見`REPORT.md`第649輪心跳、`PENDING_QUEUE.md`「凍結.二」條目、
`research/AWAITING_REVIEW.md`。

---

**最後更新：2026-09-27T20:3x+08:00（馬拉松第648輪，維運帽）**——取鎖乾淨
（cycle`20260927-203037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round645一致，`修.七`完成後的佇列規模未再變動）。逐一核對15條`- [!]`
阻塞項是否解除：`金流一.4`（法人歷史，需20交易日）——上一輪（round647,
US軌）已重跑`build_sector_flow.py`查明並更正round645「17日」的暫態誤記，
確認為**16個交易日**（20260826~28/31四個低覆蓋率交易日被`_solid_dates()`
門檻濾掉），今日09-27為週日無新交易日，本輪查證維持**16日，20日視窗
仍差4個交易日，未解除**；`外部一改.2`tick累積`ls research/data/ticks/
*.parquet`實測仍**13/20**（週日無新交易日tick，未解除）；其餘13條
（`資料源一.3`／`結案.一`／`Cybex.beta`／`外部二改`／`稽核.三`／
`稽核.五`／`零之三`／`常備.9`／`重構.C4`／`研究.c`／`資料源.外銷訂單
彙總`／`分K.零`／`紙.一`）逐一核對開頭標記，均為等總司令操作/裁示、
外部條件（法遵/資料源查證回覆）、或時間閘（`紙.一`等2026-10第一個
交易日），皆未到解除時間。**佇列深度自檢**：`- [ ]`=0（<12下限），
`CLAUDE.md`十四節【凍結.二】仍生效（總司令回覆的B類11條`- [!]`實體行
本輪仍原封不動，未見「凍結.二解除」字樣），本階段暫停佇列深度補件。
三軌時間戳：TW round645=09-27 17:3x／FUT round646=09-27 18:3x／US
round647=09-27 19:3x（最新）——依輪替本應選TW（645最舊），本輪即為
TW。**與round645相比的新增背景**（不影響TW軌本身結論，僅供對照）：
hypothesis_queue軌道在本輪之間完成「驗.六：資料修正後的影響重估
（診斷）」（commit`332507f1`），純診斷性質、未動任何#398/#399/#400
判定，已列入`AWAITING_REVIEW.md`（14→15件）。`data/rate_limit_state.json`
確認FinMind`blocked_until`=2026-09-27T08:22:52 UTC，本輪查詢時（台北
20:33，約UTC12:33）額度已解除逾4小時，但`資料.一`／`閘門.一`皆已於
round640完成300/300，無待續抓工作，額度狀態不觸發新工作單位。
`run_detached.py status`：`running=0`（162筆歷史，無job待收成）。
`git status`確認僅常駐排程自動改寫的機器寫檔（`data/audit_report.json`
等，均在既有白名單範圍內）有未commit變更，`research/backtest/`／
`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內原始碼**零未commit
編輯**。**逐一核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑
先前輪次已全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成
300/300；工具修正（修.三/修.六/修.七）已由互動視窗commit。
`AWAITING_REVIEW.md`「等待中」表格核對**15件**（表頭與列數一致，較
round645的14件多1件，為hypothesis_queue軌新完成的`驗.六`）。**本輪
誠實結論**：四類允許工作皆已完成或無新內容，15條`- [!]`逐一核對均未
到解除時間，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之一」
白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰
`凍結.二`禁止的新alpha試驗。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（本輪純查證未新增判定）。
`validation/holdout.py::is_holdout_consumed()`讀取為`True`（H.一單次
解鎖已於09-27消耗，非本輪新增動作，僅讀取核對）。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定清單內任何
原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增外部API
呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`ls`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**。
**等待審閱：15件**（與`AWAITING_REVIEW.md`「等待中」表格列數一致）。
**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round646=09-27
18:3x，三軌中最舊）；凍結.二在總司令/Cowork明確寫「凍結.二解除」前
不解除，不補新alpha試驗；`金流一.4`還需4個交易日（20日視窗，round647
已更正為16日基準）；`外部一改.2`tick累積仍13/20。完整見`REPORT.md`
第648輪心跳、`PENDING_QUEUE.md`「凍結.二」條目、
`research/AWAITING_REVIEW.md`。

---

**最後更新：2026-09-27T19:3x+08:00（馬拉松第647輪，維運帽）**——取鎖乾淨
（cycle`20260927-193037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條阻塞中
（與round645/646一致），逐一核對開頭標記可能已解除的條件。**核心發現：
解決round646留下的金流一.4「16 vs 17交易日」落差查證**——直接讀
`data/institutional_history.json`原始檔顯示`dates`陣列有20筆
（20260826~20260924），但重跑`python scripts/build_sector_flow.py`
（零額外外部請求，純讀既有檔案）顯示前4個交易日（20260826/27/28、
20260831）覆蓋率過低（分別只有4/38/66/113檔，對比尖峰1004檔），被
`_solid_dates()`門檻濾掉，實際「solid」交易日數為**16**（20260901~
20260924），與round646一致；round645記錄的「17」查無對應依據，判定
為round645當輪的筆誤或暫態誤讀，**16才是正確且可重現的數字**，20日
視窗仍差4個交易日、60日視窗仍差44個交易日，未解除。`外部一改.2`tick
累積`ls research/data/ticks/*.parquet`實測仍**13/20**（今日週日無新
交易日tick，未解除）；其餘13條`- [!]`逐一核對，均為等總司令/Cowork
裁示或其他外部條件（`資料源.外銷訂單彙總`需使用者親自在瀏覽器貼
data.gov.tw網址、`資料源一.3`等免費key、`Cybex.beta`/`稽核.三`/
`結案.一`等待裁示），皆未到解除時間。**佇列深度自檢**：`- [ ]`=0
（<12下限），`CLAUDE.md`十四節【凍結.二】仍生效（`轉向.一`FAIL結果
已登記但條目本身尚未寫「凍結.二解除」一句話，依規則字面仍算生效中），
本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：TW round645=
09-27 17:3x／FUT round646=09-27 18:3x／**US round644=09-27 16:3x
（最舊）**——依round646建議與輪替選US。**逐一核對`凍結.二`允許的
四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料
抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正（修.三、修.六、
修.七）已由互動視窗commit；`git status`確認`research/backtest/`／
`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯。US軌本身`US_LEADS.md`/`STRATEGY_GRAVEYARD.md`price-only因子
家族結案狀態未變，`#49`/`#51`/`#52`已FAIL結案，無對應結構性優勢
候選可開新方向（`凍結.二`期間本來就不得開新alpha試驗）。`run_
detached.py status`：`running=0`（162筆歷史，無job待收成）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（402列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格核對
**14件**（表頭與列數一致，逐行核對21~34行共14列，與TW round645/
FUT round646記錄的14件相符，本輪未變動）。**本輪誠實結論**：金流
一.4數字落差已查明並確認16為正確值（非bug、非需修正的程式問題，
純粹是round645的暫態誤記），四類允許工作皆已完成或無新內容，
`- [!]`15條逐一核對均未到解除時間，US軌本身查無可推進的新工作
單位——依`CLAUDE.md`「零之一」白名單第7條精神（佇列真的空了）記錄
後結束本輪，不硬湊候選、不觸碰`凍結.二`禁止的新alpha試驗、不搶碰
十三節限定檔案。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`
凍結區，全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`、`ls`，唯一寫入動作是重跑`build_sector_flow.py`——該腳本
零額外外部請求，只讀repo內既有檔案，輸出與既有`sector_flow.json`/
`PENDING_QUEUE.md`倒數文字內容一致無實質變化，僅`generated_at`
時間戳更新）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦
佇列還剩0條未開始**。**等待審閱：14件**（與`AWAITING_REVIEW.md`
「等待中」表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議
選TW軌（round645=09-27 17:3x，三軌中最舊）；凍結.二在總司令/Cowork
明確寫「凍結.二解除」前不解除，不補新alpha試驗；金流一.4已確認16
為正確值，20日視窗還需4個交易日；外部一改.2 tick累積仍13/20。
完整見`REPORT.md`第647輪心跳、`PENDING_QUEUE.md`「凍結.二」條目、
`research/AWAITING_REVIEW.md`。
