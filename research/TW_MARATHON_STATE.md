# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。


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
**最後更新：2026-09-27T23:3x+08:00（馬拉松第651輪，維運帽）**——取鎖乾淨
（cycle`20260927-233037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
`grep -c "^- \[ \]"`=0（無未開始交辦項），`grep -c "^- \[!\]"`=15條（與
round645~650一致）。逐一核對15條`- [!]`阻塞項開頭標記是否解除：
`金流一.4`直接讀`data/institutional_history.json`確認`dates`陣列仍20筆、
最後日期`20260924`，solid交易日數維持**16日**（round647查明的正確值），
今日09-27仍為週日無新交易日，20日視窗仍差4個交易日，未解除；`外部一改.2`
tick累積`ls research/data/ticks/*.parquet`實測仍**13/20**（週日無新交易日
tick，未解除）；其餘13條逐一核對開頭標記，均為等總司令/Cowork裁示或
其他外部條件，皆未到解除時間。**佇列深度自檢**：`- [ ]`=0（<12下限），
`CLAUDE.md`十四節【凍結.二】仍生效（`grep -c "凍結.二解除" PENDING_QUEUE.md`
=3，皆為條件敘述提及該詞彙、非實際宣告解除，依規則字面仍算生效中），
本階段暫停佇列深度補件，不重掃備援來源。三軌時間戳：TW round648=09-27
20:3x／FUT round649=09-27 21:3x／US round650=09-27 22:3x（最新）——依
輪替本應選TW（648最舊），本輪即為TW。**逐一核對`凍結.二`允許的四類
工作現況**：稽核重跑／驗.二重跑先前輪次已全部完成並登記；資料抓取
（`資料.一`/`閘門.一`）已完成300/300；工具修正（修.三/修.六/修.七）已
由互動視窗commit；`git status --short`確認`research/backtest/`／
`research/validation/`／`research/adjust.py`／`research/pit.py`／
`research/trial_registry.py`等十三節限定清單內檔案無殘留未commit編輯
（輸出為空）。`run_detached.py status`：`running=0`（162筆歷史，無job
待收成）。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0
PASS（402列，本輪純查證未新增判定）。`validation/holdout.py::is_
holdout_consumed()`讀取為`True`（H.一單次解鎖已於09-27消耗，非本輪
新增動作，僅讀取核對）。`AWAITING_REVIEW.md`「等待中」表格逐行核對
22~36行共**15列**，與表頭「目前：15件」一致，較round648~650記錄的
15件無變動。**本輪誠實結論**：四類允許工作皆已完成或無新內容，
`- [!]`15條逐一核對均未到解除時間，TW軌本身查無可推進的新工作單位
——依`CLAUDE.md`「零之一」白名單第7條精神（佇列真的空了）記錄後結束
本輪，不硬湊候選、不觸碰`凍結.二`禁止的新alpha試驗、不搶碰十三節
限定檔案。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，
未修改十三節限定清單內任何原始碼（僅讀取核對＋改狀態檔＋archive舊
state條目），全程零新增外部API呼叫（純讀既有`.json`/`.md`帳本檔案、
`git status`/`git log`、`run_detached.py status`、`trial_registry.py
--check`、`ls`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦
佇列還剩0條未開始**。**等待審閱：15件**（與`AWAITING_REVIEW.md`「等待
中」表格列數一致）。**下一輪任一軌接手**：依輪替下一輪建議選FUT軌
（round649=09-27 21:3x，三軌中最舊）；凍結.二在總司令/Cowork明確寫
「凍結.二解除」前不解除，不補新alpha試驗；`金流一.4`還需4個交易日
（20日視窗）；`外部一改.2`tick累積仍13/20。完整見`REPORT.md`第651輪
心跳、`PENDING_QUEUE.md`「凍結.二」條目、`research/AWAITING_REVIEW.md`。

---


（第598輪、第601輪、第602輪、第603輪、第604輪、第605輪、第608輪、
第611輪、第614輪、第615輪、第616輪、第617輪、第619輪、第620輪、
第621輪、第622輪、第623輪、第624輪、第632輪、第635輪、第638輪、
第642輪、第645輪、第648輪已歸檔至`TW_STATE_ARCHIVE.md`，僅保留最新3則）
