# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


---
**最後更新：2026-09-29T10:0x+08:00（馬拉松第663輪，維運/研究帽）**——取鎖乾淨
（cycle`20260929-100036`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=4（`分K.零`／`驗.八`／`本地AI摘要(Breeze-7B)`／
`稽核.三B`——`驗.八一`已由互動視窗於今日09:xx commit`f390e081`完成，但
`驗.八`整體仍`- [ ]`因二~五未完成；`grep -c "^- \[!\]"`=12（較round648~662
的15少3，因`驗.八一`已把`群益API`三條合併為1條暫緩，見下方）。**判斷本輪
可插手哪一條**：`驗.八`本身——`git status --short`顯示`docs/
EPS_REVENUE_SIGNAL_ANATOMY_2026-09-29.md`／`research/audit_v8_signal_
anatomy.py`兩個untracked檔案，mtime為09:57/10:00（取鎖前3分內），比照
round661對`驗.七`的判斷（時間吻合＝互動視窗正在做，避免插手覆寫競爭），
本輪不觸碰`驗.八`；`本地AI摘要(Breeze-7B)`／`稽核.三B`皆是[開發]/[資料]
性質、非馬拉松研究帽慣常範疇（且Breeze-7B需要本機裝GPU套件、稽核.三B
涉及改寫下游讀取假設，兩者都更適合互動視窗執行），本輪選擇**`分K.零`**
——它是`CLAUDE.md`「零之一」允許的可還原技術任務、且已由總司令在`驗.八`
明確同意解除阻塞。**做了什麼**：確認`shioaji_quotes.py`(PID 129748)
常駐中、`/health`帶token回應`shioaji_connected:true`且`stale_process:
false`；寫`research/probe_kbars_coverage.py`測涵蓋範圍（上市/上櫃/ETF/
已下市各3檔，沿用既有`/live/kbars`端點不開第二條連線）。**結果**：上市/
上櫃/ETF共9檔全部200（68根bar，09:01開盤到查詢當下），已下市3檔
（6452康友-KY/3662樂陞/4803VHQ-KY）全部404——推論Shioaji contract
lookup對已下市代碼查不到。**過程中的自我糾正**：原本第3個下市樣本填錯
代碼（4930誤當淘帝-KY，實際4930是仍上市的燦星網，淘帝-KY正確代號2929
也未下市），empirical結果（回200而非404）當場暴露這個查證疏漏，已用
查證過的VHQ-KY(4803，2021-12-27正式下市)補測並在結果檔誠實留下更正
記錄，不覆蓋掉原始錯誤。**意外發現**：404的失敗查詢一樣會被
`kbars_usage.calls_today`計入（13次呼叫，budget從null累加到18，多出
5次推測是同時段其他既有活動），代表**contract查不到的失敗查詢一樣燒
額度**。**尚未做（下一步，已寫入`分K.零`條目）**：最多回溯多久——現有
`shioaji_quotes.py`的op="kbars"協定寫死`start=day,end=day`(今天)，
沒有start/end參數，要測需先擴充daemon協定+重啟常駐行程，屬於對正式
交易連線的變更，列為下一個獨立工作單位；速率限制（全市場2年要多久）
依賴(1)才能測；停牌/漲跌停標的本輪沒查到現成清單，未測。`分K.零`維持
`- [ ]`。核對12條`- [!]`阻塞項（較上輪少3條，因`驗.八一`已把群益API
三條合併為1條）：`institutional_history.json`確認`dates`陣列仍20筆、
solid交易日數維持16日，20日視窗仍差4個交易日，未解除；tick累積仍
13/20，未解除；其餘10條均未到解除時間。`CLAUDE.md`十四節【凍結.二】
仍生效（`分K.零`屬infra可行性測試非alpha試驗，不受凍結.二限制）。
`run_detached.py status`：running=0。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（406列，本輪純infra測試未新增
判定）。`AWAITING_REVIEW.md`「等待中」表頭「目前：16件」，本輪未變動
（`驗.七`仍等Cowork核對）。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼；本輪對外部服務
的呼叫僅限本機`alpha_live_server.py`（既有常駐行程，走既有token驗證，
未開第二條Shioaji連線，13次kbars查詢均在240/日預算內）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩3條未開始**
（`驗.八`判定為互動視窗進行中非漏做；`本地AI摘要(Breeze-7B)`／
`稽核.三B`留給互動視窗或下一輪，非馬拉松研究帽慣常範疇）。**等待審閱：
16件**（與`AWAITING_REVIEW.md`表格列數一致）。**下一輪任一軌接手**：
依輪替下一輪建議選FUT軌（round661=09-29 00:3x，三軌中最舊）；開工前
先重新檢查`驗.八`是否仍在進行中；`分K.零`下一步是擴充daemon協定測
回溯天數，屬於對正式交易連線的變更，建議由互動視窗執行較安全（重啟
風險）。完整見`REPORT.md`第663輪心跳、`PENDING_QUEUE.md`「分K.零」
條目、`research/data/probe_kbars_coverage_result.json`。

---
**最後更新：2026-09-28T22:0x+08:00（馬拉松第660輪，維運帽）**——取鎖乾淨
（cycle`20260928-220037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round648~659一致）。逐一核對15條`- [!]`阻塞項是否解除：直接讀
`data/institutional_history.json`確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**，今日09-28（週一）22:0x查詢
（收盤後約8.5小時，法人資料排程尚未入庫本日新交易日），20日視窗仍差
4個交易日，未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/
data/ticks/*.parquet`實測仍**13/20**（同理排程尚未寫入新tick），未
解除；其餘13條（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`外部二改`／`Cybex.beta`／`分K.零`／`稽核.三`／`稽核.五`／`零之三`／
`結案.一`／`常備.9`／`紙.一`）逐一核對開頭標記，均為等總司令/Cowork
裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，
皆為條件敘述提及該詞彙、非實際宣告解除），本階段暫停佇列深度補件，
不重掃備援來源。三軌時間戳：TW round657=09-28 14:3x（最舊）／FUT
round658=09-28 17:0x／US round659=09-28 19:3x——依輪替選TW。**逐一
核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已
全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具
修正已由互動視窗commit；`git status --short`確認`research/backtest/`
／`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯（輸出為空）。`run_detached.py status`：`running=0`（162筆歷史，
無job待收成）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（402列，本輪純查證未新增判定）。`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非
本輪新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格表頭
明寫「目前：15件」，逐行核對一致，較round648~659無變動。**本輪誠實
結論**：四類允許工作皆已完成或無新內容，`- [!]`15條逐一核對均未到
解除時間，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`「零之一」
白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊候選、不觸碰
`凍結.二`禁止的新alpha試驗、不搶碰十三節限定檔案。未動`alpha.db`/
`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節限定清單內
任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），全程零新增
外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/`git log`、
`run_detached.py status`、`trial_registry.py --check`、`ls`）。
`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未
開始**。**等待審閱：15件**（與`AWAITING_REVIEW.md`「等待中」表格列數
一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌（round658=
09-28 17:0x，三軌中最舊）；凍結.二在總司令/Cowork明確寫「凍結.二
解除」前不解除，不補新alpha試驗；`金流一.4`還需4個交易日（20日視窗，
收盤後排程入庫後可望更新）；`外部一改.2`tick累積仍13/20。完整見
`REPORT.md`第660輪心跳、`PENDING_QUEUE.md`「凍結.二」條目、
`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-28T14:3x+08:00（馬拉松第657輪，維運帽）**——取鎖乾淨
（cycle`20260928-143037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round648~656一致）。逐一核對15條`- [!]`阻塞項是否解除：直接讀
`data/institutional_history.json`確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**，今日09-28（週一）14:3x查詢
（收盤後約1小時，法人資料排程尚未入庫本日新交易日），20日視窗仍差
4個交易日，未解除；`外部一改.2`／`研究.c`共用的tick累積`ls research/
data/ticks/*.parquet`實測仍**13/20**（同理排程尚未寫入新tick），
未解除；其餘13條（`資料源.外銷訂單彙總`／`重構.C4`／`資料源一.3`／
`外部二改`／`Cybex.beta`／`分K.零`／`稽核.三`／`稽核.五`／`零之三`／
`結案.一`／`常備.9`／`紙.一`）逐一核對開頭標記，均為等總司令/Cowork
裁示或其他外部條件，皆未到解除時間（`紙.一`需等2026-10第一個交易日，
今日仍09月）。**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`
十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，
皆為條件敘述提及該詞彙、非實際宣告解除），本階段暫停佇列深度補件，
不重掃備援來源。三軌時間戳：TW round654=09-28 07:0x（最舊）／FUT
round655=09-28 09:3x／US round656=09-28 12:0x——依輪替選TW。**逐一
核對`凍結.二`允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已
全部完成並登記；資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具
修正已由互動視窗commit；`git status --short`確認`research/backtest/`
／`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit
編輯（輸出為空）。`run_detached.py status`：`running=0`（162筆歷史，
無job待收成）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）
exit=0 PASS（402列，本輪純查證未新增判定）。`validation/holdout.py::
is_holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非
本輪新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格逐行
核對共**15列**，與表頭「目前：15件」一致，較round648~656無變動。
**本輪誠實結論**：四類允許工作皆已完成或無新內容，`- [!]`15條逐一
核對均未到解除時間，TW軌本身查無可推進的新工作單位——依`CLAUDE.md`
「零之一」白名單第7條精神（佇列真的空了）記錄後結束本輪，不硬湊
候選、不觸碰`凍結.二`禁止的新alpha試驗、不搶碰十三節限定檔案。未動
`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，未修改十三節
限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊state條目），
全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、`git status`/
`git log`、`run_detached.py status`、`trial_registry.py --check`、
`ls`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩
0條未開始**。**等待審閱：15件**（與`AWAITING_REVIEW.md`「等待中」
表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌
（round655=09-28 09:3x，三軌中最舊）；凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除，不補新alpha試驗；`金流一.4`還需4個交易日
（20日視窗，收盤後排程入庫後可望更新）；`外部一改.2`tick累積仍
13/20。完整見`REPORT.md`第657輪心跳、`PENDING_QUEUE.md`「凍結.二」
條目、`research/AWAITING_REVIEW.md`。

---
**最後更新：2026-09-28T07:0x+08:00（馬拉松第654輪，維運帽）**——取鎖乾淨
（cycle`20260928-070037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round645~653一致）。逐一核對15條`- [!]`阻塞項是否解除：直接讀
`data/institutional_history.json`確認`dates`陣列仍20筆、最後日期
`20260924`，solid交易日數維持**16日**，今日09-28（週一）盤前查詢
（07:0x），尚無新交易日入庫，20日視窗仍差4個交易日，未解除；
`外部一改.2`／`研究.c`共用的tick累積`ls research/data/ticks/*.parquet`
實測仍**13/20**（同理盤前無新增tick），未解除；其餘13條（`資料源.
外銷訂單彙總`／`重構.C4`／`資料源一.3`／`外部二改`／`Cybex.beta`／
`分K.零`／`稽核.三`／`稽核.五`／`零之三`／`結案.一`／`常備.9`／
`紙.一`）逐一核對開頭標記，均為等總司令/Cowork裁示或其他外部條件，
皆未到解除時間（`紙.一`需等2026-10第一個交易日，今日仍09月）。
**佇列深度自檢**：`- [ ]`=0（<12下限），`CLAUDE.md`十四節【凍結.二】
仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`=3，皆為條件敘述提及
該詞彙、非實際宣告解除），本階段暫停佇列深度補件，不重掃備援來源。
三軌時間戳：TW round651=09-27 23:3x（最舊）／FUT round652=09-28
02:0x／US round653=09-28 04:3x——依輪替選TW。**逐一核對`凍結.二`
允許的四類工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；
資料抓取（`資料.一`/`閘門.一`）已完成300/300；工具修正已由互動視窗
commit；`git status --short`確認`research/backtest/`／`research/
validation/`／`research/adjust.py`／`research/pit.py`／`research/
trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯（輸出
為空）。**額外查證**：重新核對`CALIBRATION_PROBE.md`給出的具體操作
指令（300檔重跑`portfolio_multifactor_v2`＋依序重跑#77/#79/#91）——
獨立確認`factor_ic.py::SAMPLE_SIZE`現值已是**300**（非待改），且
`TRIALS_LEDGER.md`#100/#101/#106已分別完成#79/#77/#91三項300檔重跑
並全部改判定回**確定FAIL**（#106高關注度子組雖CHEAP_PASS但因TRAIN期
不顯著、需獨立樣本複驗，未列入待深挖清單），這條指令早於round645~653
即已執行完畢，非本輪遺漏的可做工作。`run_detached.py status`：
`running=0`（162筆歷史，無job待收成）。`trial_registry.py --check`
（`PYTHONIOENCODING=utf-8`）exit=0 PASS（402列，本輪純查證未新增
判定）。`validation/holdout.py::is_holdout_consumed()`讀取為`True`
（H.一單次解鎖已於09-27消耗，非本輪新增動作，僅讀取核對）。
`AWAITING_REVIEW.md`「等待中」表格逐行核對共**15列**，與表頭「目前：
15件」一致，較round651~653無變動。**本輪誠實結論**：四類允許工作
皆已完成或無新內容，`- [!]`15條逐一核對均未到解除時間，
`CALIBRATION_PROBE.md`操作指令也已查證早於本輪完成，TW軌本身查無
可推進的新工作單位——依`CLAUDE.md`「零之一」白名單第7條精神（佇列
真的空了）記錄後結束本輪，不硬湊候選、不觸碰`凍結.二`禁止的新alpha
試驗、不搶碰十三節限定檔案。未動`alpha.db`/`fetch.py`/`parsers.py`/
`config.py`凍結區，未修改十三節限定清單內任何原始碼（僅讀取核對＋
改狀態檔＋archive舊state條目），全程零新增外部API呼叫（純讀既有
`.json`/`.md`帳本檔案、`git status`/`git log`、`run_detached.py
status`、`trial_registry.py --check`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**。**等待審閱：15件**
（與`AWAITING_REVIEW.md`「等待中」表格列數一致）。**下一輪任一軌
接手**：依輪替下一輪建議選FUT軌（round652=09-28 02:0x，三軌中最舊）；
凍結.二在總司令/Cowork明確寫「凍結.二解除」前不解除，不補新alpha
試驗；`金流一.4`還需4個交易日（20日視窗，09-28開盤後入庫將是第一個
新增交易日）；`外部一改.2`/`研究.c`tick累積仍13/20。完整見
`REPORT.md`第654輪心跳、`PENDING_QUEUE.md`「凍結.二」條目、
`research/AWAITING_REVIEW.md`。

---


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪、
第621輪、第622輪、第623輪、第624輪、第632輪、第635輪、第638輪、
第642輪、第645輪、第648輪、第651輪、第654輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
