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
