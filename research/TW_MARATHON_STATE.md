# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-22T09:1x+08:00（馬拉松第591輪，互動視窗CC接手）**——
開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：`- [ ]`=3，挑最舊未開始項
`方法.三`（[研究]，事件驅動原型，前置條件方法.二已通過）。新建
`research/event_driven_prototype.py`：E1財報公布(SUE)/E2月營收公布(SUE)，
進場=公布日後第一個交易日，前瞻報酬t+1/t+5/t+20從進場價起算，**分組依
事件當下SUE前10%（非事後報酬，跟方法.二PEAD校準的car3事後分組刻意不同）**，
對照組=同季度/同產業/同市值五分位、非前10%個股，PIT對齊，全走
`tail_test()`。300檔快取樣本，兩事件類型合計11秒+21秒建表（<5分鐘門檻，
未用`run_detached.py`）。**結果**：E1事件6706筆(訊號n=671/對照n=1134)，
t+20 median_diff=+0.0063、right_tail訊號組0.095>對照組0.066；E2事件20339
筆(訊號n=2034/對照n=5924)，t+20 median_diff=+0.0039、right_tail訊號組
0.075>對照組0.051——**兩事件類型t+20方向皆一致**，power_class兩者皆
**VALID**(`DEGENERATE_N_FLOOR`=60門檻，min(n)遠高於門檻)。`register_
trial()`登記`TRIALS_LEDGER.md`#323（verdict=EXPERIMENTAL——本檔案只做
`tail_test()`方向性檢查，無隨機控制組排列檢定/train-val切分/成本敏感度，
比cheap_gate_precheck更前一步，不宣稱PASS/FAIL，定位是原型）。
`trial_registry.py --check`exit=0 PASS（325列）。補件盤點：`- [ ]`剩3項
（新增`方法.三續.GATE_SEQUENCE驗證`[自走補入，來源本輪#323下一步]／
出場.零／宇宙.零後兩者性質是「暫不做只登記」），三備援來源重掃與前四輪
結論一致無新項可補，未硬湊。holdout未動、未碰凍結區、零新增外部API呼叫
（全部讀本機既有快取）。**下一輪**：若總司令核准往下投入，`方法.三續.
GATE_SEQUENCE驗證`——E1/E2的SUE訊號需走完整GATE_SEQUENCE（隨機控制組/
train-val切分/成本敏感度/leave-one-out/逐年一致性）才能宣稱PASS/FAIL。
完整見`PENDING_QUEUE.md`方法.三條目、`TRIALS_LEDGER.md`#323、
`research/event_driven_prototype.py`（新增，可重複執行）。

**最後更新：2026-09-22T08:5x+08:00（馬拉松第590輪，互動視窗CC接手）**——
開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：`- [ ]`=4，挑最舊未開始項
`方法.二`（[研究]，前置條件方法.三需要它先通過）。新建`research/tail_test.py`
（中位數差異/P90差異各bootstrap 10000次、右尾佔比>+20%/左尾佔比<-20%、
期望值扣1.8折成本依horizon選當沖/一般稅率），純數學自我測試PASS。
**PEAD自我校準**（`research/pead_calibration_gate.py`新增）：300檔快取樣本，
財報`pit_date`後3日累積報酬(car3)前10%為訊號組(n=707)，對照組=同季度/同
產業/同市值五分位、非前10%個股(n=1289)，PIT對齊。**t+20 median_diff=
+0.0107(90%CI[+0.0013,+0.0198])、right_tail訊號組0.102>對照組0.054，
校準PASS**——工具驗證通過，方法.三前置條件已滿足。`register_trial()`登記
`TRIALS_LEDGER.md`#322（verdict=EXPERIMENTAL，工具校準非新候選）。
`trial_registry.py --check`exit=0 PASS（324列）。補件盤點：`- [ ]`剩3項
（方法.三／出場.零／宇宙.零，後兩者性質是「暫不做只登記」），三備援來源
與前三輪結論一致無新項可補，未硬湊。holdout未動、未碰凍結區、零新增
外部API呼叫。**下一輪**：`方法.三`事件驅動原型（前置條件已過）——E1財報
公布日/E2月營收公布日先做，全走`tail_test()`，計入`TRIALS_REGISTRY`且
標power_class。完整見`PENDING_QUEUE.md`方法.二條目、`TRIALS_LEDGER.md`#322。

**最後更新：2026-09-20T22:42:21+08:00（馬拉松第584輪）**——取鎖乾淨。戴研究帽做`原子.五B`計算層：`ATOM_FIN_CHANNEL_B_SPEC.md`事前登記（132表達式/264測試）→`fin_atom_ic_map_b.py`→Tier A(204檔)/B(567檔)全量跑完；K=5僅4族、檢定力低，機械結果FAIL但不可外推（SPEC第6節）；尚未登記、判定留驗證帽輪次（`PENDING_QUEUE.md`原子.五B進度）。下一步：驗證帽寫`FIN_ATOM_CHANNEL_B.md`＋register_trial；`籌碼原子.補出借總量快取`第2批續投（slb_backfill_b1結束後）。


