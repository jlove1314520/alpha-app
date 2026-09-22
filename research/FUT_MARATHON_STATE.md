# FUT_MARATHON_STATE.md — 期貨軌斷點狀態（覆寫式）

**✅ 2026-09-01T20:31 第266輪已確認第260輪push積壓早已解決**：`3fab283`已成功推送，`git log`本輪（第278輪）再次確認`origin/main`與本機`HEAD`一致，push機制正常運作中（本輪期間可見到自動報價workflow持續在推送commit）。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`3fab283`）...下一輪...先跑`git push`~~」。

**✅ 2026-08-29T05:02 第209輪push積壓已自行解決**：前3次因DNS解析失敗（`Could not resolve host: github.com`）未能push，第4次（多等20秒後）成功推送（`8ce907c..58f4bfe`），不需要任何額外動作。以下這段警告保留供歷史對照，已非待辦事項：「~~本輪commit（`b2bcd84`）...下一輪...先跑`git push`~~」。

**【2026-08-25晚起、2026-08-26再次確認】資源配置：期貨軌維持最多佔整體馬拉松輪次20%**（29次策略試驗中1個EXPERIMENTAL、1個邊界候選待複驗、0個乾淨PASS，仍是三軌中效率最低的一軌）。這不是說完全不做，是說選輪次時TW/US軌優先度更高，FUT軌不要連續佔用太多輪。**第109輪提醒：近10輪（100–109）FUT佔2輪=20%，剛好觸頂（未超額但已滿），下一輪若還選FUT要先重新盤點窗口。** 完整背景見`MARATHON_STATE.md`「2026-08-26 使用者裁示」區塊。
**✅ 2026-08-25T22:31（第77輪，US軌）已確認上面那個push積壓問題自行解決**：`git log`確認`fa6c7e5`是目前`HEAD`的祖先且`origin/main`本地快取ref跟`HEAD`一致，代表後續（可能是第76輪TW或更早）某次push已經成功把它推上去了，不需要任何額外動作。以下這行警告保留供歷史對照，但已經不是待辦事項。

**⚠️ 2026-08-25T20:36 push失敗待處理（已解決，見上方）**：本輪commit（fa6c7e5）因DNS解析失敗（`Could not resolve host: github.com`）重試3次仍無法push，commit已在本機完成不會遺失，**下一輪不管選到哪一軌，開始前先跑`git push`把這個積壓的commit推上去**（如果那時網路正常，一個指令就好，不需要重做任何工作）。

**這份檔案只描述期貨軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `FUT_LOG.md`；候選判定看 `FUT_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的 64 則已原文搬到 `FUT_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-23T03:3x+08:00（馬拉松第607輪，維運帽）**——取鎖乾淨
（cycle`20260923-033037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：
全文0條`- [ ]`，23條`- [!]`阻塞中。**佇列深度自檢**：`- [ ]`=0（<12下限），
round599~606已連續多輪確認三個備援來源無新項，本輪不重複全面掃描。三軌
時間戳：TW round605=09-23 01:3x／US round606=09-23 02:3x／**FUT
round600=09-22 19:3x（最舊）**——依round606建議與輪替選FUT。`run_detached.py
status`確認`running=0`（151筆歷史，無running job需收成）。**本輪意外發現：
`git status`顯示`data/audit_report.json`處於未解決的merge衝突狀態**
（`both modified`，index含3個stage，working tree內含`<<<<<<< Updated
upstream`/`=======`/`>>>>>>> Stashed changes`字面衝突標記）——不是
rebase中（無`.git/MERGE_HEAD`/`rebase-merge`/`rebase-apply`），比對
`git stash list`找到內容完全相符的`stash@{0}`（標記`autostash`，含
`data/audit_report.json`/`factory_stability.json`/
`factory_stability_history.jsonl`/`connectivity_check.log`/
`external_connectivity.jsonl`五檔，與衝突的「Stashed changes」側逐檔
一致），研判是某次`git pull --rebase --autostash`完成rebase後，
autostash自動`pop`回衝突未被處理就留下——根因（哪支腳本觸發）本輪未
查出（repo內`*.ps1`未見明文`autostash`字串，可能是互動session或
另一支排程直接下`git -c rebase.autoStash=true pull`，留給下一輪維運帽
或總司令視需要再深查，不阻塞本次修復）。**修復**：比對衝突兩側
`generated_at`（HEAD側02:59:35新於stash側前一日23:00:02），確認HEAD版
較新且為權威來源，`git checkout --ours`解衝突並驗證解析後仍是合法
JSON，`git add`清空index衝突stage；`stash@{0}`內容已被HEAD版本涵蓋
（且是被conflict擋下、從未真正套用成功的半套用狀態），確認冗餘後
`git stash drop`；同批連帶已被其他排程正常staged但因這個衝突卡住未能
commit的其餘4個例行自動更新檔案（`factory_stability.json`等）一併
納入本次commit。commit`de8a7fb2`並push成功（`54d1b919..de8a7fb2`）。
**這是本輪唯一工作單位**：`#50`（唯一未結案方向）tick累積本輪未變更查
（round600已確認12/20，FUT例外條款已四次複核不成立，不必每輪重查）。
`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS
（本輪純維運修復，未新增統計判定，不觸發`register_trial()`）。
`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。
未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，零新增外部
API呼叫（純`git`操作與既有帳本/log讀取）。`PROGRESS_HEARTBEAT.jsonl`
已append本輪一行。**交辦佇列還剩0條未開始**（23條`- [!]`阻塞中）。
等待審閱：1件（規.二第4節參數掃描方式提案，非本輪新增，延續中）。
**下一輪任一軌接手**：`#50`仍是三軌唯一未結案方向，被動等待tick累積至
20（12/20）與總司令對gate50三條件的回應；本輪修復的git衝突根因
（哪支排程觸發autostash pop衝突）若未來再發作，建議下一次維運帽輪次
搜尋所有`.ps1`/排程設定裡`git -c rebase.autoStash`或`git pull`不帶
`--no-rebase`的呼叫點，本輪礙於預算未展開這個較深的排查；依輪替下一輪
建議選TW軌（round605=09-23 01:3x，三軌中最舊）。完整見`REPORT.md`
第607輪心跳（待補）、commit`de8a7fb2`。

---

**最後更新：2026-09-22T19:3x+08:00（馬拉松第600輪）**——取鎖乾淨（cycle`20260922-193037`）。開工先照「交辦優先於自走」讀`PENDING_QUEUE.md`：全文0條`- [ ]`（`2026-09-22總司令裁示【方法論重建】`三條、出場.零、宇宙.零皆已`[x]`完成），24條`- [!]`阻塞中，其中`#50`依賴的`籌碼原子.補借券快取`／`財報原子.補快取`等皆已解除或標BLOCKED且冷卻條件未到，無可立即動手項。**佇列深度自檢**：`- [ ]`=0（<12下限），重掃三個備援來源：`HYPOTHESIS_QUEUE.md`「排隊中」grep僅命中3處歷史敘述（2處2026-09-04、1處#79屬hypothesis_queue自己排隊，非本馬拉松軌範圍）；`TW_LEADS.md`/`US_LEADS.md`/`FUT_LEADS.md`/`STRATEGY_GRAVEYARD.md`「下一步/待辦」逐一核對round592~599四輪一致結論未變，本輪另外查證`原子.五B`（`ATOM_FIN_CHANNEL_B_SPEC.md`第6節）標註的「待Tier A回補擴大後另立新SPEC重測」是否已因今日完成的`財報原子.補快取`（round598，覆蓋率≥60%）而解鎖——**查證結果：不成立**，`tier_universe('A')`（`fin_atom_ic_map.py`第150~156行）只交集`TaiwanStockFinancialStatements`（損益表）快取，Channel B的Tier A六原子（revenue/eps/gross_profit/op_income/net_income/shares）全部是損益表科目，而今日回補的是資產負債表/現金流量表（total_assets/equity/inventory/receivable/ocf），兩者不相交——損益表覆蓋率本就已97%+高原（見`FIN_ATOM_COVERAGE.md`第1節），今日回補對Channel B Tier A的K=5深度瓶頸（37/45表達式缺2011窗，本質是net_income/shares定義自2013Q1起才存在的時間深度問題，不是股票數覆蓋問題）沒有任何幫助，**維持FAIL結論不變，不重跑**。**未硬湊新項**，符合白名單第7條精神。**依輪替選FUT**（TW round598=17:4x／US round599=18:3x／FUT round562=09-19 14:10，FUT遠遠最舊）：核對`MARATHON_PROTOCOL.md`第3節機制清單（多時間框架趨勢/突破/波動regime/均線/日內均值回歸/期現價差/三大法人期貨部位/未平倉量/隔夜vs日內/星期效應/盤別效應）自round399確認全數至少測過一個變體後，round484~562三次複核均確認「無新機制候選」，本輪`git log`核對round562之後FUT相關檔案（`fut_cheap_gate.py`/`fut_basis_series.py`/`continuous_contract.py`）零新增commit，`HYPOTHESIS_QUEUE.md`#77/#78/#79（信用利差/HYG-IEF比值/TAIEX對電子指數相對強度）皆屬hypothesis_queue自己的獨立軌道，非本馬拉松FUT軌新機制。**本輪唯一實質產出：FUT例外條款第四次複核，結論不變（無新機制候選）**；`#50`（唯一未結案方向）tick累積依`data/ticks/`實測12/20（`20260907`~`20260922`共12個`.parquet`，較round520的4/20推進8日），**未達20且gate50三條件總司令尚未回應，依2026-09-15裁示不重複回報進度細節，此處僅供稽核軌跡**，維持`- [!]`被動等待，非本輪可推進項。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（332列，本輪未新增判定，純查證/確認性質工作）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。未動`alpha.db`/`fetch.py`/`parsers.py`/`config.py`凍結區，全程零新增外部API呼叫（純讀既有`.md`/`.json`帳本檔案與`git log`/`run_detached.py status`）。`PROGRESS_HEARTBEAT.jsonl`已append本輪一行。**交辦佇列還剩0條未開始**（24條`- [!]`阻塞中）。等待審閱：0件。**下一輪任一軌接手**：`#50`仍是TW/US/FUT三軌唯一未結案方向，被動等待tick累積至20（目前12/20）與總司令對gate50三條件的回應；FUT例外條款已四次複核確認不成立，往後除非出現真正跳脫`MARATHON_PROTOCOL.md`第3節清單的全新機制假說，不需要每輪重新複核；依輪替下一輪建議選TW軌（round598=17:4x最舊）。完整見`REPORT.md`第600輪心跳、`MARATHON_STATE.md`（輪次計數器600）、`ATOM_FIN_CHANNEL_B_SPEC.md`第6節、`PENDING_QUEUE.md`「原子.五B」條目。

---

**最後更新：2026-09-19T14:10+08:00（馬拉松第562輪）**——取鎖乾淨（cycle`20260919-140050`）。交辦優先：處理`FUT.basis均值回歸regime複驗`，完成（見FUT_LOG／FUT_LEADS補記）：三條事前判準全過、#19維持EXPERIMENTAL，附註近年邊際衰減至近零。無下一步阻塞；FUT軌仍無新機制候選。

---

**上一則保留（第520輪，供對照）**——原文：最後更新：2026-09-10T15:02+08:00（馬拉松第520輪）**——取鎖乾淨（cycle`20260910-150037`）。依round519建議本輪重新評估FUT例外條款是否仍成立。`run_detached.py status`：`running=0`（60筆歷史紀錄，無新增）；`git log`確認round519之後除round519自身commit`10abc8b5`外，還有互動session兩筆維運commit（停擺三／停擺四／停擺一收尾、深讀三新增第7~10關、深讀四.3連續曝險縮放偏好成文），皆非本馬拉松範圍，未動凍結區。**FUT例外條款複核結果：仍不成立，無新機制候選**——`MARATHON_PROTOCOL.md`第3節列出的期貨假說類別（多時間框架趨勢/突破/波動regime/均線/日內均值回歸/期現價差/三大法人期貨部位/未平倉量/隔夜vs日內/星期效應/盤別效應）round399已確認全數至少測過一個變體；`#64`基差regime訊號（round484，唯一一次真正觸發例外條款的新機制）已於round484結案FAIL；round484之後至今唯一新增的期貨相關試驗是`hypothesis_queue`（非本馬拉松軌）2026-09-10「外部一改.3」補測的五個名家發表趨勢跟隨機制（海龜/Donchian/Keltner/波動度突破/CTA多時間框架），`TRIALS_LEDGER.md`#234~#238全數FAIL，且經相關係數檢查後四條與既有`hyp_trend_multi_tf`/`hyp_donchian_breakout`同屬趨勢突破家族（`|r|>0.7`），只有波動度突破一條是真正獨立發現但percentile僅7.0，非FUT track本身的新工作單位，亦未帶來可承接的候選。**依輪替回落TW軌**：TW 14:02（round518，最舊）／US 15:02（round520本輪決策前查詢，最新）——本輪決策為FUT優先評估但未推進實質工作單位，依規則本輪工作單位改為對TW軌做同等的精簡確認（見下段）。**TW軌精簡確認**：`PENDING_QUEUE.md`第99~113行gate50查證段落仍原封不動，總司令尚未回應三條件具體定義，`#50`維持未解鎖；`data/ticks/`累積進度**4/20**（`20260907`~`20260910`四個`.parquet`皆已finalize，距20日仍差16日，較round519無變化——`20260910`當日盤中tick仍在累積中，尚未到隔日finalize時點）；`STRATEGY_GRAVEYARD.md`掃描`## #6x`/`## #7x`標題，最新結案仍為`#70`（2026-09-10，hypothesis_queue軌，非本馬拉松範圍），本馬拉松TW/US/FUT三軌自身最新結案仍為`#68`（round510），無新結案。`trial_registry.py --check`（`PYTHONIOENCODING=utf-8`）exit=0 PASS（243列，撞號2組皆為歷史存量不回頭改寫，本輪未產生新試驗判定）。`validation/holdout.py::is_holdout_consumed()`開工/收工前皆確認`False`。全程零新增外部API呼叫（純讀既有`.md`檔案與`git log`/`git status`/`run_detached.py status`）。**結論：FUT例外條款複核完畢並確認不成立（本輪唯一實質產出），候選池連續34輪（487~520）維持同一狀態，TW/US/FUT三軌本地端皆無新可推進工作單位**，僅剩`#50`（tick累積4/20，被動等待總司令對gate50三條件的回應）。**下一輪任一軌接手**：`#50`gate50原文仍待總司令回應；FUT例外條款已複核確認不成立，往後除非出現真正跳脫`MARATHON_PROTOCOL.md`第3節清單的全新機制假說，不需要每輪重新複核FUT，依輪替下一輪建議選TW軌。完整見`REPORT.md`第520輪心跳、`MARATHON_STATE.md`（輪次計數器520）。
