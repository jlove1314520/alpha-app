# 本機 autostash 盤點（2026-10-14 先.九十三-2，交 Cowork 審閱）

- 範圍：`git stash list` 共 **71 份**（2026-09-04 07:30 ～ 2026-10-14 05:16），都是 `git pull --rebase --autostash` 自動產生。
- 判定方法：每份暫存裡改過的每一個檔（含未追蹤部分，若有），比對「暫存版本」與目前 HEAD 版本的檔案雜湊；**全部相同**才算「內容已完整存在於 HEAD」。
- 結果：**0 份完整存在於 HEAD → 依裁示一份都沒有刪除**。刪除前後清單相同（71 份）。
- 53 份只有機器自動寫的檔不同（data/、research/*.log、*.jsonl、research/data/、隱藏狀態檔），內容是當時的排程輸出，現在已被更新的版本取代；**是否可丟由 Cowork 判斷**。
- 18 份含非機器檔差異（程式碼、研究紀錄、圖片），列在下表「非機器檔」欄，**建議逐份人工看過再決定**。
- 本檔只列檔名與差異統計，不貼任何檔案內容。

| # | 暫存 | 日期 | 原分支訊息 | 改動檔數 | 與 HEAD 不同 | 非機器檔（與 HEAD 不同，含差異統計） |
|---|---|---|---|---|---|---|
| 1 | stash@{0}（86cc8524a） | 2026-10-14 05:16:17 | autostash | 15 | 15 | —（只有機器檔） |
| 2 | stash@{1}（c751a83fd） | 2026-10-14 02:12:14 | autostash | 15 | 15 | —（只有機器檔） |
| 3 | stash@{2}（55d513bd8） | 2026-10-14 01:09:27 | autostash | 19 | 17 | —（只有機器檔） |
| 4 | stash@{3}（e682463d9） | 2026-10-14 00:31:13 | autostash | 15 | 15 | `research/us_universe_rebuild.py`（1 file changed, 2 insertions(+), 9 deletions(-)） |
| 5 | stash@{4}（929f5776f） | 2026-10-13 19:22:15 | autostash | 12 | 12 | —（只有機器檔） |
| 6 | stash@{5}（f994dd5a0） | 2026-10-13 07:40:07 | autostash | 10 | 10 | —（只有機器檔） |
| 7 | stash@{6}（a515cec31） | 2026-10-13 04:42:46 | autostash | 15 | 15 | —（只有機器檔） |
| 8 | stash@{7}（0509ab3c3） | 2026-10-13 03:16:07 | autostash | 15 | 15 | —（只有機器檔） |
| 9 | stash@{8}（b09f5d248） | 2026-10-12 11:42:16 | autostash | 437 | 437 | —（只有機器檔） |
| 10 | stash@{9}（743a29428） | 2026-10-12 05:12:16 | autostash | 841 | 841 | —（只有機器檔） |
| 11 | stash@{10}（fbbe8ff5d） | 2026-10-11 20:40:36 | WIP on main: 9a926297c 常備.開發-31 標記完成＋心跳（ | 20 | 19 | `app.js`（1 file changed, 98 insertions(+), 549 deletions(-)） |
| 12 | stash@{11}（f74e09545） | 2026-10-10 04:16:05 | autostash | 12 | 12 | —（只有機器檔） |
| 13 | stash@{12}（8e6b758fe） | 2026-10-09 21:25:09 | autostash | 18 | 12 | —（只有機器檔） |
| 14 | stash@{13}（d44126687） | 2026-10-09 04:46:05 | autostash | 15 | 14 | —（只有機器檔） |
| 15 | stash@{14}（bc1642cf0） | 2026-10-08 04:46:06 | autostash | 14 | 14 | —（只有機器檔） |
| 16 | stash@{15}（51c1814de） | 2026-10-07 04:31:05 | autostash | 19 | 17 | `scripts/long_job_progress_heartbeat.py`（1 file changed, 2 insertions(+), 5 deletions(-)） |
| 17 | stash@{16}（8bd20ef6f） | 2026-10-07 00:05:32 | autostash | 29 | 25 | `index.html`（1 file changed, 7263 insertions(+), 537 deletions(-)）；`research/alpha_live_server.py`（1 file changed, 3 insertions(+), 236 deletions(-)）；`research/auto_rebalance_bb90.py`（1 file changed, 38 insertions(+), 535 deletions(-)）；`scripts/long_job_progress_heartbeat.py`（1 file changed, 2 insertions(+), 5 deletions(-)）；`scripts/selftest_auto_rebalance.py`（1 file changed, 2 insertions(+), 226 deletions(-)） |
| 18 | stash@{17}（44a8c2e2b） | 2026-10-06 06:21:04 | autostash | 18 | 17 | `scripts/long_job_progress_heartbeat.py`（1 file changed, 2 insertions(+), 5 deletions(-)） |
| 19 | stash@{18}（73d42a4a8） | 2026-10-05 17:21:38 | autostash | 17 | 16 | —（只有機器檔） |
| 20 | stash@{19}（cd7f5713b） | 2026-10-03 21:46:04 | autostash | 9 | 9 | —（只有機器檔） |
| 21 | stash@{20}（0f1a3f6dc） | 2026-10-03 20:46:04 | autostash | 11 | 11 | —（只有機器檔） |
| 22 | stash@{21}（60a631cc0） | 2026-10-03 15:51:04 | autostash | 11 | 11 | —（只有機器檔） |
| 23 | stash@{22}（c804f088f） | 2026-10-03 14:21:04 | autostash | 11 | 11 | —（只有機器檔） |
| 24 | stash@{23}（8cd116256） | 2026-10-03 13:01:04 | autostash | 9 | 9 | —（只有機器檔） |
| 25 | stash@{24}（e285f5cf9） | 2026-10-03 11:46:04 | autostash | 9 | 9 | —（只有機器檔） |
| 26 | stash@{25}（d3bd05087） | 2026-10-03 10:51:05 | autostash | 11 | 11 | `research/MARATHON_LOG.md`（1 file changed, 11 insertions(+), 88 deletions(-)） |
| 27 | stash@{26}（ad88b36d9） | 2026-10-03 09:01:05 | autostash | 7 | 7 | —（只有機器檔） |
| 28 | stash@{27}（a5f17cab8） | 2026-10-03 07:46:04 | autostash | 9 | 9 | —（只有機器檔） |
| 29 | stash@{28}（41d062542） | 2026-10-03 05:21:04 | autostash | 9 | 9 | —（只有機器檔） |
| 30 | stash@{29}（d95aed7e6） | 2026-10-03 04:00:40 | autostash | 8 | 8 | —（只有機器檔） |
| 31 | stash@{30}（bc8dab235） | 2026-10-03 00:21:04 | autostash | 10 | 9 | —（只有機器檔） |
| 32 | stash@{31}（cc99db727） | 2026-10-02 18:16:06 | autostash | 12 | 12 | —（只有機器檔） |
| 33 | stash@{32}（b5986c420） | 2026-10-01 19:46:06 | autostash | 17 | 17 | —（只有機器檔） |
| 34 | stash@{33}（5dc64b15c） | 2026-09-30 23:51:13 | autostash | 14 | 14 | —（只有機器檔） |
| 35 | stash@{34}（3adcdfa86） | 2026-09-30 12:22:11 | autostash | 9 | 9 | —（只有機器檔） |
| 36 | stash@{35}（fa7bda17e） | 2026-09-30 08:46:08 | autostash | 10 | 10 | —（只有機器檔） |
| 37 | stash@{36}（c78c3d63e） | 2026-09-29 23:44:13 | On main: machine-files-before-pull-0929 | 10 | 10 | `scores.json`（1 file changed, 59557 insertions(+), 197873 deletions(-)） |
| 38 | stash@{37}（5aebab48f） | 2026-09-29 22:16:04 | autostash | 15 | 15 | —（只有機器檔） |
| 39 | stash@{38}（09b9f4b87） | 2026-09-29 12:30:38 | autostash | 14 | 14 | `research/alpha_live_server.py`（1 file changed, 45 insertions(+), 402 deletions(-)）；`research/shioaji_quotes.py`（1 file changed, 73 insertions(+), 343 deletions(-)） |
| 40 | stash@{39}（a8da56a9e） | 2026-09-29 12:16:04 | autostash | 12 | 12 | —（只有機器檔） |
| 41 | stash@{40}（bd7e53219） | 2026-09-29 05:21:04 | autostash | 11 | 11 | —（只有機器檔） |
| 42 | stash@{41}（de8fb9b34） | 2026-09-29 04:46:03 | autostash | 11 | 11 | —（只有機器檔） |
| 43 | stash@{42}（af4d83d56） | 2026-09-29 04:01:03 | autostash | 11 | 11 | —（只有機器檔） |
| 44 | stash@{43}（fc44863b6） | 2026-09-29 03:31:03 | autostash | 12 | 12 | —（只有機器檔） |
| 45 | stash@{44}（21f4ec6ff） | 2026-09-29 00:16:04 | autostash | 11 | 11 | —（只有機器檔） |
| 46 | stash@{45}（2b42e9e64） | 2026-09-28 23:21:04 | autostash | 11 | 11 | —（只有機器檔） |
| 47 | stash@{46}（787a6f330） | 2026-09-28 20:21:04 | autostash | 13 | 13 | —（只有機器檔） |
| 48 | stash@{47}（2b909be85） | 2026-09-28 19:46:03 | autostash | 13 | 13 | —（只有機器檔） |
| 49 | stash@{48}（bb29690a6） | 2026-09-26 15:51:55 | WIP on main: 2f32093a 假設佇列第32輪：交辦0條未開始、阻 | 16 | 16 | —（只有機器檔） |
| 50 | stash@{49}（f3e9b94c6） | 2026-09-25 03:21:43 | autostash | 14 | 14 | —（只有機器檔） |
| 51 | stash@{50}（7ddf6b70b） | 2026-09-23 12:39:59 | On main: marathon-round615-tmp-stash | 14 | 14 | —（只有機器檔） |
| 52 | stash@{51}（a3a1ea166） | 2026-09-22 21:43:59 | autostash | 8 | 8 | —（只有機器檔） |
| 53 | stash@{52}（c2c65c1d8） | 2026-09-22 04:16:07 | autostash | 23 | 18 | —（只有機器檔） |
| 54 | stash@{53}（b5247dd0d） | 2026-09-20 17:24:09 | WIP on main: f79312d3 原子.五：寫事前登記SPEC（145 | 24 | 20 | `research/mem_probe_scale.py`（1 file changed, 2 deletions(-)）；`research/backfill_fin_atom_cache.py（未追蹤）`（未追蹤檔） |
| 55 | stash@{54}（dcf3c2c2c） | 2026-09-19 15:15:56 | On main: marathon563暫存 | 18 | 17 | `research/backfill_stock_financials_gap_2025.log.json`（1 file changed, 31 insertions(+), 157 deletions(-)） |
| 56 | stash@{55}（67abbb900） | 2026-09-15 17:26:10 | On main: residual-other-automation-round | 20 | 20 | `kbars_open_check.png（未追蹤）`（未追蹤檔）；`research/backfill_stock_financials_gap_2025.log.json（未追蹤）`（未追蹤檔）；`research/backfill_stock_financials_gap_2025.py（未追蹤）`（未追蹤檔）；`sector_flow_1_market_card.png（未追蹤）`（未追蹤檔）；`sector_flow_2_sector_expand.png（未追蹤）`（未追蹤檔）；`sector_flow_3_stock_2330_chips.png（未追蹤）`（未追蹤檔） |
| 57 | stash@{56}（bd66f6d36） | 2026-09-09 22:36:18 | On main: hypothesis_queue排程：暫存非本track殘留變 | 2 | 2 | —（只有機器檔） |
| 58 | stash@{57}（706fda786） | 2026-09-09 20:32:23 | WIP on main: 005c97a5 hypothesis_queue:  | 2 | 2 | —（只有機器檔） |
| 59 | stash@{58}（964f6cf20） | 2026-09-09 19:03:48 | On main: non-hypothesis_queue residual ( | 3 | 3 | —（只有機器檔） |
| 60 | stash@{59}（e9252d8ed） | 2026-09-08 12:27:21 | On main: hypothesis_queue round: preserv | 3 | 3 | —（只有機器檔） |
| 61 | stash@{60}（ca9436301） | 2026-09-08 12:01:13 | WIP on main: 6dce8fd hypothesis_queue：#5 | 2 | 2 | —（只有機器檔） |
| 62 | stash@{61}（191cd4865） | 2026-09-08 11:23:14 | On main: 非本輪殘留變更暫存 | 3 | 3 | —（只有機器檔） |
| 63 | stash@{62}（66826aeec） | 2026-09-08 09:56:01 | On main: hypothesis_queue暫存非本輪殘留變更 | 2 | 2 | —（只有機器檔） |
| 64 | stash@{63}（cf77b1765） | 2026-09-06 02:04:33 | WIP on main: ab9d67c hypothesis_queue: # | 1 | 1 | —（只有機器檔） |
| 65 | stash@{64}（b1027ac57） | 2026-09-04 20:44:11 | On main: hypothesis_queue輪次暫存-非本輪產生的其他軌殘 | 15 | 15 | `research/MARATHON_STATE.md`（1 file changed, 2 insertions(+), 159 deletions(-)）；`research/REPORT.md`（1 file changed, 1739 deletions(-)）；`research/TW_LOG.md`（1 file changed, 1026 deletions(-)）；`research/US_LEADS.md`（1 file changed, 1 insertion(+), 45 deletions(-)）；`research/US_LOG.md`（1 file changed, 565 deletions(-)）；`research/US_MARATHON_STATE.md`（1 file changed, 208 insertions(+), 229 deletions(-)）；`research/train_only_ic_weight_bigsample_full_gate.py（未追蹤）`（未追蹤檔） |
| 66 | stash@{65}（dd0286fd6） | 2026-09-04 20:00:07 | On main: 其他軌道殘留變更(非本輪) | 18 | 18 | `research/MARATHON_STATE.md`（1 file changed, 2 insertions(+), 159 deletions(-)）；`research/REPORT.md`（1 file changed, 1739 deletions(-)）；`research/TRIALS_LEDGER.md`（1 file changed, 1 insertion(+), 430 deletions(-)）；`research/US_LEADS.md`（1 file changed, 1 insertion(+), 45 deletions(-)）；`research/US_LOG.md`（1 file changed, 565 deletions(-)）；`research/US_MARATHON_STATE.md`（1 file changed, 208 insertions(+), 229 deletions(-)）；`research/fut_probe_stock_futures_info.py（未追蹤）`（未追蹤檔）；`research/leave_one_factor_out_v2.py（未追蹤）`（未追蹤檔）；`research/us_factor_ic_cached_universe.py（未追蹤）`（未追蹤檔） |
| 67 | stash@{66}（69c988c35） | 2026-09-04 19:27:59 | On main: hypothesis_queue軌道暫存：其他軌道殘留未提交變 | 5 | 5 | `.github/scripts/fetch_quotes_tw.py`（1 file changed, 191 insertions(+), 53 deletions(-)）；`research/LEADS.md`（1 file changed, 4 insertions(+), 35 deletions(-)）；`research/TW_LOG.md`（1 file changed, 4 insertions(+), 1033 deletions(-)）；`research/US_LEADS.md`（1 file changed, 2 insertions(+), 46 deletions(-)） |
| 68 | stash@{67}（3c7f0dfbc） | 2026-09-04 13:57:31 | On main: hypothesis_queue輪殘留(非本輪產生,rebas | 14 | 13 | `.github/scripts/fetch_quotes_tw.py`（1 file changed, 191 insertions(+), 53 deletions(-)）；`index.html`（1 file changed, 3897 insertions(+), 811 deletions(-)）；`research/US_LEADS.md`（1 file changed, 2 insertions(+), 46 deletions(-)）；`research/US_LOG.md`（1 file changed, 572 deletions(-)）；`research/us_factor_ic_cached_universe.py（未追蹤）`（未追蹤檔） |
| 69 | stash@{68}（a95fe86a3） | 2026-09-04 09:25:40 | On main: 非本輪殘留:.gitignore(alpha_live_ser | 1 | 1 | `.gitignore`（1 file changed, 7 insertions(+), 67 deletions(-)） |
| 70 | stash@{69}（ddea4d804） | 2026-09-04 09:25:26 | On main: 非本輪殘留:US/TW軌未commit變更 | 6 | 6 | `research/TRIALS_LEDGER.md`（1 file changed, 7 insertions(+), 448 deletions(-)）；`research/US_LEADS.md`（1 file changed, 2 insertions(+), 46 deletions(-)）；`research/US_LOG.md`（1 file changed, 1 insertion(+), 601 deletions(-)）；`research/US_MARATHON_STATE.md`（1 file changed, 202 insertions(+), 229 deletions(-)）；`research/us_factor_ic_by_size.py`（1 file changed, 9 insertions(+), 8 deletions(-)） |
| 71 | stash@{70}（870a1fb40） | 2026-09-04 07:30:28 | WIP on main: 98b41c9 hypothesis_queue排程： | 3 | 3 | `.github/workflows/market.yml`（1 file changed, 21 insertions(+), 279 deletions(-)）；`.github/workflows/quotes.yml`（1 file changed, 20 insertions(+), 25 deletions(-)） |

## 2026-10-14 先.九十四-2 重新比對與清除（總司令裁示）

- **裁示**：53 份只含機器寫檔的清除；18 份含程式或文件的，改用「暫存相對它自己的基底 commit 的差異」比對 HEAD，已包含的清除，未包含的列差異摘要交 Cowork、不得刪。
- **比對方法**（只看非機器檔；機器檔依同一裁示第一句視為可丟）：
  1. 取 `git diff 暫存^1 暫存 -- 檔案`（這份暫存自己的改動），在一份等於 HEAD 的暫用索引上做 `git apply -R --check`：反向套得上＝HEAD 已含這段改動。
  2. 套不上（之後又改過、上下文變了）時逐行比：這段改動新增的每一行都在 HEAD、刪掉的每一行都已不在 HEAD，才算已包含；有任何一行對不上就算未包含（保守，寧可留）。
  3. 未追蹤檔（暫存^3）：與 HEAD 同路徑檔案雜湊完全相同才算已包含。
- **結果**：清除前 71 份 → 清除 57 份（機器檔 53＋已包含 4）→ 清除後 14 份。清除後清單已核對＝下表「保留」14 份，一份不多一份不少。
- 被清除的暫存 commit 在 git 垃圾回收前（預設約 2 週）仍可用 `git stash store <完整 SHA>` 救回；完整 SHA 列在下表。

### 清除前清單（71 份）與處理結果

| # | 暫存（完整 SHA） | 日期 | 類別 | 處理 | 比對結果（非機器檔） |
|---|---|---|---|---|---|
| 1 | 86cc8524a2dcf5a38b68e13b6100ffabb2c5116d | 2026-10-14 05:16:17 | 只有機器檔 | 清除 | — |
| 2 | c751a83fdbd6483883c28139ea6a52c772ff5834 | 2026-10-14 02:12:14 | 只有機器檔 | 清除 | — |
| 3 | 55d513bd847cffdf78c787807ef14399609c7167 | 2026-10-14 01:09:27 | 只有機器檔 | 清除 | — |
| 4 | e682463d9fb156e7921d8b26022a2c14f7e4a754 | 2026-10-14 00:31:13 | 含程式／文件 | 清除（已包含） | `research/us_universe_rebuild.py`：已包含 |
| 5 | 929f5776f5b19aa9943e8796682215f7d9231446 | 2026-10-13 19:22:15 | 只有機器檔 | 清除 | — |
| 6 | f994dd5a065612c6a205ef016d98713d2f28eb10 | 2026-10-13 07:40:07 | 只有機器檔 | 清除 | — |
| 7 | a515cec31cbdb3629722c8fa610a9fb3cdca42ca | 2026-10-13 04:42:46 | 只有機器檔 | 清除 | — |
| 8 | 0509ab3c3a6ef46aed058dfc0f5b8abdd058a2bd | 2026-10-13 03:16:07 | 只有機器檔 | 清除 | — |
| 9 | b09f5d248281ec43de461924fac049cf17c073ab | 2026-10-12 11:42:16 | 只有機器檔 | 清除 | — |
| 10 | 743a294284734bafa8f297c25aa36648498f2226 | 2026-10-12 05:12:16 | 只有機器檔 | 清除 | — |
| 11 | fbbe8ff5d0bdd0016239570db7a4e8cb748f7800 | 2026-10-11 20:40:36 | 含程式／文件 | 清除（已包含） | `app.js`：已包含 |
| 12 | f74e09545024f053162c1dfa723f24e1dd991417 | 2026-10-10 04:16:05 | 只有機器檔 | 清除 | — |
| 13 | 8e6b758fefc93a90a5d7a2ffdd8943bdac178a14 | 2026-10-09 21:25:09 | 只有機器檔 | 清除 | — |
| 14 | d4412668705c2b95fa6c10359dd9b564c22ea862 | 2026-10-09 04:46:05 | 只有機器檔 | 清除 | — |
| 15 | bc1642cf06d5db0192e2e269ebdd0993d7a2467a | 2026-10-08 04:46:06 | 只有機器檔 | 清除 | — |
| 16 | 51c1814de034caf4ef53051fcd6910ad464c4aa7 | 2026-10-07 04:31:05 | 含程式／文件 | 清除（已包含） | `scripts/long_job_progress_heartbeat.py`：已包含（逐行：新增 9 行都在 HEAD、刪除 4 行都已不在） |
| 17 | 8bd20ef6fd8c11288138c99a3a9f364977194886 | 2026-10-07 00:05:32 | 含程式／文件 | **保留，交 Cowork** | `index.html`：未包含（HEAD 該處已改寫）；逐行：新增 0/37 行在 HEAD、刪除 4/4 行已不在；暫存相對基底：1 file changed, 37 insertions(+), 4 deletions(-)；`research/alpha_live_server.py`：已包含（逐行：新增 11 行都在 HEAD、刪除 0 行都已不在）；`research/auto_rebalance_bb90.py`：已包含（逐行：新增 47 行都在 HEAD、刪除 6 行都已不在）；`scripts/long_job_progress_heartbeat.py`：已包含（逐行：新增 9 行都在 HEAD、刪除 4 行都已不在）；`scripts/selftest_auto_rebalance.py`：已包含（逐行：新增 51 行都在 HEAD、刪除 7 行都已不在） |
| 18 | 44a8c2e2b8d94e3a6d01feee3d6d6d862ef02baf | 2026-10-06 06:21:04 | 含程式／文件 | 清除（已包含） | `scripts/long_job_progress_heartbeat.py`：已包含（逐行：新增 9 行都在 HEAD、刪除 4 行都已不在） |
| 19 | 73d42a4a8794fa6f62f6590a24c2588cd08b044d | 2026-10-05 17:21:38 | 只有機器檔 | 清除 | — |
| 20 | cd7f5713b23c35c5b4034e528c0a3444aef7bccc | 2026-10-03 21:46:04 | 只有機器檔 | 清除 | — |
| 21 | 0f1a3f6dcf7451735073e2f62c23311cc0fd3ac8 | 2026-10-03 20:46:04 | 只有機器檔 | 清除 | — |
| 22 | 60a631cc03a0ab08ef443d5b876325232dd3f798 | 2026-10-03 15:51:04 | 只有機器檔 | 清除 | — |
| 23 | c804f088ff5ca57498189c3ef86866e7cec48625 | 2026-10-03 14:21:04 | 只有機器檔 | 清除 | — |
| 24 | 8cd1162569b35e22a7e88261ab3239e72f5bbde5 | 2026-10-03 13:01:04 | 只有機器檔 | 清除 | — |
| 25 | e285f5cf95e3eec576b86dd3e4cdafe5b1ea732e | 2026-10-03 11:46:04 | 只有機器檔 | 清除 | — |
| 26 | d3bd05087e1efbaf4a1e217b093265aaf4dfb525 | 2026-10-03 10:51:05 | 含程式／文件 | **保留，交 Cowork** | `research/MARATHON_LOG.md`：未包含（HEAD 該處已改寫）；逐行：新增 1/12 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 13 insertions(+) |
| 27 | ad88b36d9d69c5f27a8aee96ffa667dbb741c776 | 2026-10-03 09:01:05 | 只有機器檔 | 清除 | — |
| 28 | a5f17cab8996d2172fe307e16b686acacb5d3de9 | 2026-10-03 07:46:04 | 只有機器檔 | 清除 | — |
| 29 | 41d0625423064b1792296c3da9068d526b6ee777 | 2026-10-03 05:21:04 | 只有機器檔 | 清除 | — |
| 30 | d95aed7e6edf04ff4ccc4f41076bd67b0c043507 | 2026-10-03 04:00:40 | 只有機器檔 | 清除 | — |
| 31 | bc8dab23559a8ac7753db9db59882fd9cee3471d | 2026-10-03 00:21:04 | 只有機器檔 | 清除 | — |
| 32 | cc99db7270e2efb31224cec4924256417b216a72 | 2026-10-02 18:16:06 | 只有機器檔 | 清除 | — |
| 33 | b5986c420d086f02044ddce0221403fa665ffb05 | 2026-10-01 19:46:06 | 只有機器檔 | 清除 | — |
| 34 | 5dc64b15c4bac6a6987d16b9eec351c054626a48 | 2026-09-30 23:51:13 | 只有機器檔 | 清除 | — |
| 35 | 3adcdfa860785818dba24841fcff018c3ff18b96 | 2026-09-30 12:22:11 | 只有機器檔 | 清除 | — |
| 36 | fa7bda17e5fba57621d2ece94ea9308295d02da6 | 2026-09-30 08:46:08 | 只有機器檔 | 清除 | — |
| 37 | c78c3d63e6e56dc36d441d652e7796bc825e79de | 2026-09-29 23:44:13 | 含程式／文件 | **保留，交 Cowork** | `scores.json`：未包含（HEAD 該處已改寫）；逐行：新增 21101/34227 行在 HEAD、刪除 33521/171359 行已不在；暫存相對基底：1 file changed, 34227 insertions(+), 171359 deletions(-) |
| 38 | 5aebab48f340fac057f1f8ee599fdad163836bd8 | 2026-09-29 22:16:04 | 只有機器檔 | 清除 | — |
| 39 | 09b9f4b874fc7ac386776b9a305c88fb8e082656 | 2026-09-29 12:30:38 | 含程式／文件 | **保留，交 Cowork** | `research/alpha_live_server.py`：未包含（HEAD 該處已改寫）；逐行：新增 26/52 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 58 insertions(+)；`research/shioaji_quotes.py`：未包含（HEAD 該處已改寫）；逐行：新增 26/51 行在 HEAD、刪除 1/6 行已不在；暫存相對基底：1 file changed, 54 insertions(+), 6 deletions(-) |
| 40 | a8da56a9ef8d60f0da210394613ebae90c48ade4 | 2026-09-29 12:16:04 | 只有機器檔 | 清除 | — |
| 41 | bd7e532198693a6eb9c0ea2996fee491ff3a00cc | 2026-09-29 05:21:04 | 只有機器檔 | 清除 | — |
| 42 | de8fb9b3448ad7e05367ed235a1a74c2c51f0436 | 2026-09-29 04:46:03 | 只有機器檔 | 清除 | — |
| 43 | af4d83d56e692b830989aece55730c66aac7c363 | 2026-09-29 04:01:03 | 只有機器檔 | 清除 | — |
| 44 | fc44863b66786f96814448ee1f8afa82f6ecd635 | 2026-09-29 03:31:03 | 只有機器檔 | 清除 | — |
| 45 | 21f4ec6ffe81ec461635dacb63c6ba2b500c7502 | 2026-09-29 00:16:04 | 只有機器檔 | 清除 | — |
| 46 | 2b42e9e6470ee08df4d566633a6db2a8ab17961e | 2026-09-28 23:21:04 | 只有機器檔 | 清除 | — |
| 47 | 787a6f330766d22e50cce52ccada9a34d557a5f8 | 2026-09-28 20:21:04 | 只有機器檔 | 清除 | — |
| 48 | 2b909be85e22981d33cae9d689342fcd7f147dba | 2026-09-28 19:46:03 | 只有機器檔 | 清除 | — |
| 49 | bb29690a6d385b5bc85d8329176ce13054e1776a | 2026-09-26 15:51:55 | 只有機器檔 | 清除 | — |
| 50 | f3e9b94c6df407d74997e4561c27524756621379 | 2026-09-25 03:21:43 | 只有機器檔 | 清除 | — |
| 51 | 7ddf6b70b851fb06038573e0512e5fe79314f87a | 2026-09-23 12:39:59 | 只有機器檔 | 清除 | — |
| 52 | a3a1ea166e8caff4721ee384ef751365b9820de3 | 2026-09-22 21:43:59 | 只有機器檔 | 清除 | — |
| 53 | c2c65c1d8e7a242b5fad786513e6f3b0c9167949 | 2026-09-22 04:16:07 | 只有機器檔 | 清除 | — |
| 54 | b5247dd0d88aad1462dcae0d5a7c75a98796077b | 2026-09-20 17:24:09 | 含程式／文件 | **保留，交 Cowork** | `research/mem_probe_scale.py`：已包含；`research/backfill_fin_atom_cache.py（未追蹤）`：未包含（未追蹤檔，HEAD 版本不同） |
| 55 | dcf3c2c2ce25fe76a70ab1493bd3d9e20447e2fe | 2026-09-19 15:15:56 | 含程式／文件 | **保留，交 Cowork** | `research/backfill_stock_financials_gap_2025.log.json`：未包含（HEAD 該處已改寫）；逐行：新增 414/445 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 445 insertions(+), 1 deletion(-) |
| 56 | 67abbb90009ee06740a1ad60e650bd9598c680fc | 2026-09-15 17:26:10 | 含程式／文件 | **保留，交 Cowork** | `kbars_open_check.png（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔）；`research/backfill_stock_financials_gap_2025.log.json（未追蹤）`：未包含（未追蹤檔，HEAD 版本不同）；`research/backfill_stock_financials_gap_2025.py（未追蹤）`：未包含（未追蹤檔，HEAD 版本不同）；`sector_flow_1_market_card.png（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔）；`sector_flow_2_sector_expand.png（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔）；`sector_flow_3_stock_2330_chips.png（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔） |
| 57 | bd66f6d36ff602ac5dcc6994b72df93b583936aa | 2026-09-09 22:36:18 | 只有機器檔 | 清除 | — |
| 58 | 706fda7864322ede8f5dea840768786401c52420 | 2026-09-09 20:32:23 | 只有機器檔 | 清除 | — |
| 59 | 964f6cf2056a5ba7c5d3e0587e33a35d8e4cbd1f | 2026-09-09 19:03:48 | 只有機器檔 | 清除 | — |
| 60 | e9252d8eda364170c9c10bbb6e6e9392c017c729 | 2026-09-08 12:27:21 | 只有機器檔 | 清除 | — |
| 61 | ca94363014cec87601a23310a4045a22e3aa301a | 2026-09-08 12:01:13 | 只有機器檔 | 清除 | — |
| 62 | 191cd4865d7cdba8c8cf8d29314f1e6e261839e3 | 2026-09-08 11:23:14 | 只有機器檔 | 清除 | — |
| 63 | 66826aeecc9089b67d5e0e20321f118ecff9f3ee | 2026-09-08 09:56:01 | 只有機器檔 | 清除 | — |
| 64 | cf77b1765e63513fbe05a7ebe1e073e59e3184db | 2026-09-06 02:04:33 | 只有機器檔 | 清除 | — |
| 65 | b1027ac57478310f4a1b7e17731070884c39fac8 | 2026-09-04 20:44:11 | 含程式／文件 | **保留，交 Cowork** | `research/MARATHON_STATE.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 1 insertion(+), 1 deletion(-)；`research/REPORT.md`：已包含（逐行：新增 2 行都在 HEAD、刪除 0 行都已不在）；`research/TW_LOG.md`：已包含（逐行：新增 4 行都在 HEAD、刪除 0 行都已不在）；`research/US_LEADS.md`：已包含（逐行：新增 1 行都在 HEAD、刪除 0 行都已不在）；`research/US_LOG.md`：已包含（逐行：新增 2 行都在 HEAD、刪除 0 行都已不在）；`research/US_MARATHON_STATE.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/2 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 3 insertions(+), 1 deletion(-)；`research/train_only_ic_weight_bigsample_full_gate.py（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔） |
| 66 | dd0286fd6fe51c3a248461beb5eec449cd57b1d7 | 2026-09-04 20:00:07 | 含程式／文件 | **保留，交 Cowork** | `research/MARATHON_STATE.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 1 insertion(+), 1 deletion(-)；`research/REPORT.md`：已包含（逐行：新增 2 行都在 HEAD、刪除 0 行都已不在）；`research/TRIALS_LEDGER.md`：已包含（逐行：新增 1 行都在 HEAD、刪除 0 行都已不在）；`research/US_LEADS.md`：已包含（逐行：新增 1 行都在 HEAD、刪除 0 行都已不在）；`research/US_LOG.md`：已包含（逐行：新增 2 行都在 HEAD、刪除 0 行都已不在）；`research/US_MARATHON_STATE.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/2 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 3 insertions(+), 1 deletion(-)；`research/fut_probe_stock_futures_info.py（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔）；`research/leave_one_factor_out_v2.py（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔）；`research/us_factor_ic_cached_universe.py（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔） |
| 67 | 69c988c35e38f8941affaf457b74199ae12978ac | 2026-09-04 19:27:59 | 含程式／文件 | **保留，交 Cowork** | `.github/scripts/fetch_quotes_tw.py`：未包含（HEAD 該處已改寫）；逐行：新增 2/16 行在 HEAD、刪除 4/4 行已不在；暫存相對基底：1 file changed, 16 insertions(+), 4 deletions(-)；`research/LEADS.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 1 insertion(+), 1 deletion(-)；`research/TW_LOG.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/4 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 5 insertions(+)；`research/US_LEADS.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 1 insertion(+) |
| 68 | 3c7f0dfbcdd03fe7535d1afdbbb88b80512a5d92 | 2026-09-04 13:57:31 | 含程式／文件 | **保留，交 Cowork** | `.github/scripts/fetch_quotes_tw.py`：未包含（HEAD 該處已改寫）；逐行：新增 2/16 行在 HEAD、刪除 4/4 行已不在；暫存相對基底：1 file changed, 16 insertions(+), 4 deletions(-)；`index.html`：未包含（HEAD 該處已改寫）；逐行：新增 30/106 行在 HEAD、刪除 31/41 行已不在；暫存相對基底：1 file changed, 107 insertions(+), 41 deletions(-)；`research/US_LEADS.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 1 insertion(+)；`research/US_LOG.md`：已包含（逐行：新增 15 行都在 HEAD、刪除 0 行都已不在）；`research/us_factor_ic_cached_universe.py（未追蹤）`：未包含（未追蹤檔，HEAD 沒有此檔） |
| 69 | a95fe86a3f244287b377665b2eaf3ff20d6ef074 | 2026-09-04 09:25:40 | 含程式／文件 | **保留，交 Cowork** | `.gitignore`：未包含（HEAD 該處已改寫）；逐行：新增 4/5 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 5 insertions(+) |
| 70 | ddea4d804f4bb9903c926736a7b04a25e895d60b | 2026-09-04 09:25:26 | 含程式／文件 | **保留，交 Cowork** | `research/TRIALS_LEDGER.md`：未包含（HEAD 該處已改寫）；逐行：新增 1/7 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 7 insertions(+), 1 deletion(-)；`research/US_LEADS.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 1 insertion(+)；`research/US_LOG.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 0/0 行已不在；暫存相對基底：1 file changed, 2 insertions(+)；`research/US_MARATHON_STATE.md`：未包含（HEAD 該處已改寫）；逐行：新增 0/1 行在 HEAD、刪除 1/1 行已不在；暫存相對基底：1 file changed, 1 insertion(+), 1 deletion(-)；`research/us_factor_ic_by_size.py`：未包含（HEAD 該處已改寫）；逐行：新增 1/10 行在 HEAD、刪除 2/7 行已不在；暫存相對基底：1 file changed, 10 insertions(+), 7 deletions(-) |
| 71 | 870a1fb40ddb907a407947d9134f7522a70acc7f | 2026-09-04 07:30:28 | 含程式／文件 | **保留，交 Cowork** | `.github/workflows/market.yml`：未包含（HEAD 該處已改寫）；逐行：新增 4/18 行在 HEAD、刪除 0/3 行已不在；暫存相對基底：1 file changed, 18 insertions(+), 3 deletions(-)；`.github/workflows/quotes.yml`：未包含（HEAD 該處已改寫）；逐行：新增 2/16 行在 HEAD、刪除 0/3 行已不在；暫存相對基底：1 file changed, 16 insertions(+), 3 deletions(-) |

### 清除後清單（14 份，全部保留交 Cowork）

| 目前編號 | 完整 SHA | 日期 |
|---|---|---|
| stash@{0} | 8bd20ef6fd8c11288138c99a3a9f364977194886 | 2026-10-07 00:05:32 |
| stash@{1} | d3bd05087e1efbaf4a1e217b093265aaf4dfb525 | 2026-10-03 10:51:05 |
| stash@{2} | c78c3d63e6e56dc36d441d652e7796bc825e79de | 2026-09-29 23:44:13 |
| stash@{3} | 09b9f4b874fc7ac386776b9a305c88fb8e082656 | 2026-09-29 12:30:38 |
| stash@{4} | b5247dd0d88aad1462dcae0d5a7c75a98796077b | 2026-09-20 17:24:09 |
| stash@{5} | dcf3c2c2ce25fe76a70ab1493bd3d9e20447e2fe | 2026-09-19 15:15:56 |
| stash@{6} | 67abbb90009ee06740a1ad60e650bd9598c680fc | 2026-09-15 17:26:10 |
| stash@{7} | b1027ac57478310f4a1b7e17731070884c39fac8 | 2026-09-04 20:44:11 |
| stash@{8} | dd0286fd6fe51c3a248461beb5eec449cd57b1d7 | 2026-09-04 20:00:07 |
| stash@{9} | 69c988c35e38f8941affaf457b74199ae12978ac | 2026-09-04 19:27:59 |
| stash@{10} | 3c7f0dfbcdd03fe7535d1afdbbb88b80512a5d92 | 2026-09-04 13:57:31 |
| stash@{11} | a95fe86a3f244287b377665b2eaf3ff20d6ef074 | 2026-09-04 09:25:40 |
| stash@{12} | ddea4d804f4bb9903c926736a7b04a25e895d60b | 2026-09-04 09:25:26 |
| stash@{13} | 870a1fb40ddb907a407947d9134f7522a70acc7f | 2026-09-04 07:30:28 |

**交 Cowork**：這 14 份的改動在 HEAD 找不到（多半是當時排程與互動視窗同時改同一檔，後來被改寫），建議逐份看差異決定要不要撿回；未經裁示不再清除。本檔仍只列檔名與差異統計，不貼內容。

## 先.九十五-7（2026-10-14）：剩下 14 份匯出 patch 後清除

- 做法：逐份 `git stash show -p --binary --include-untracked <SHA>` 匯出到 `research/archive/stash_patches/stash_NN_<SHA12>.patch`（本機、已加 .gitignore，不進 repo）；每份檢查 diff 檔數＝暫存改動＋未追蹤檔數，並在暫時索引上 `git apply --cached --check` 確認可套回自己的基底 commit（14/14 通過）；再逐份核對 SHA 後 `git stash drop`（由大編號往小，避免編號位移）。
- 對照表（含基底 commit）：本機 `research/archive/stash_patches/INDEX.md`。

清除前（14 份）：

```
stash@{0} 8bd20ef6fd8c11288138c99a3a9f364977194886
stash@{1} d3bd05087e1efbaf4a1e217b093265aaf4dfb525
stash@{2} c78c3d63e6e56dc36d441d652e7796bc825e79de
stash@{3} 09b9f4b874fc7ac386776b9a305c88fb8e082656
stash@{4} b5247dd0d88aad1462dcae0d5a7c75a98796077b
stash@{5} dcf3c2c2ce25fe76a70ab1493bd3d9e20447e2fe
stash@{6} 67abbb90009ee06740a1ad60e650bd9598c680fc
stash@{7} b1027ac57478310f4a1b7e17731070884c39fac8
stash@{8} dd0286fd6fe51c3a248461beb5eec449cd57b1d7
stash@{9} 69c988c35e38f8941affaf457b74199ae12978ac
stash@{10} 3c7f0dfbcdd03fe7535d1afdbbb88b80512a5d92
stash@{11} a95fe86a3f244287b377665b2eaf3ff20d6ef074
stash@{12} ddea4d804f4bb9903c926736a7b04a25e895d60b
stash@{13} 870a1fb40ddb907a407947d9134f7522a70acc7f
```

清除後：0 份（`git stash list` 為空）。
