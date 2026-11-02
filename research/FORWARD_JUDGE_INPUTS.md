# 14 支前向模擬：判定所需數字在判定日能否重建（先.一三五-1hy）

2026-11-02 23:3x DevQueue 20261102-233102 清查。**零外部請求、不算報酬、不改任何追蹤程式**，只讀程式碼、PREREG 判定條文與 repo 現況。

## 分類標準

- **①可重建**：帳本每個交易日有一列 `nav`（append-only，進 repo），期間 MDD／年化／逐年都能從帳本本身算出。
- **②受 90 日視窗影響**：判定要的數字帳本沒存，要靠 `data/price_history`（每檔只留約 90 個交易日）或 `data/strategy_curves.json`（每次用 90 日價格重算）推，判定日（2028～2030）那天早已滾出。
- **③0050 含息**：判定要比「同期 0050 含息」，要有一條從起跑日連續到判定日的 0050 含息序列。

## 結果總表

| 模擬 | 程式 | 判定日 | 帳本 nav（MDD／年化／逐年） | 0050 含息 | 隨機時點／控制組對照 | 其他 |
|---|---|---|---|---|---|---|
| F | `paper_5_vrp_tracker.py` | 滿 12 個結算月 | ①（每天 entry／mark／flat／settle 一列帶 nav）；**但**期交所選擇權日報只有「當天」，漏跑或 `NO_MARK` 那天無法補 → 缺點不補 | ③ | 不需要 | — |
| F-翼 | `paper_6_vrp_wing_tracker.py` | 滿 12 個結算月 | ①（同 F，同樣漏跑不補） | ③ | 不需要 | — |
| G | `paper_7_revsurprise_tracker.py` | 約 2028-11 | **②**：帳本只有 inception／rebalance（`values_post`），期間 MDD 靠 `build_strategy_curves.py` 推（即 1hx） | ③（另要「兩年中至少一年贏 0050」） | 不需要 | — |
| H | `paper_8_ml_tracker.py` | 滿 24 次再平衡 | **②**：同 G，帳本只記再平衡日；「期間回撤 ≤50%」要每日淨值 | ③ | 不需要 | 大盤序列 `paper_8_taiex_closes.json` 自己累積，不受影響 |
| I | `paper_9_breakout_tracker.py` | 2028-11-01 後 | ①（每天一列 nav，`write_summary` 自己算 MDD） | ③ | **②**（隨機時點 1,000 次要整個宇宙的價格路徑） | — |
| J | `paper_10_disposition_tracker.py` | 2028-12-01 後 | ①（共用 `paper_forward_common`，每個交易日一列 nav；漏跑 90 日內會依序補） | ③ | **②**（隨機時點）；影子帳本 `paper_10_control_log.jsonl` 自己記 nav → ① | — |
| K | `paper_11_tdcc_bigholder_tracker.py` | 2028-12-01 後 | ①（共用） | ③ | **②** | — |
| L | `paper_12_warrant_wave_tracker.py` | 2028-12-01 後 | ①（共用；本機 `run_warrant_snapshot.ps1` add -f 進 repo） | ③ | **②** | — |
| M | `paper_13_ml_low_beta_tracker.py` | 2029-01-02 後 | ①（共用） | ③ | **②**；「揭露與模擬 H 同期淨值差」要 H 的每日淨值 → 跟著 H 是 **②** | — |
| N | `paper_14_grid_range_tracker.py` | 2029-01-02 後 | ①（每天一列 nav＋`grid_state`） | ③ | **②**（隨機時點 1,000 次、濾網控制組 200 次都要價格路徑）；影子網格 `paper_14_shadow_log.jsonl` → ① | — |
| O | `paper_15_ml_industry_tracker.py` | 2029-01-02 後 | ①（共用 weighted） | ③ | **②**（隨機時點、隨機產業）；`research/data/paper_15_stock_daily/` 是本機 FinMind 面板、不進 repo | — |
| P | `paper_16_order_win_tracker.py` | 2030-01-02 後 | ①（共用 event） | ③ | **②** | 標題精準度稽核（60 則）要當時的公告標題——**本輪未查**是否有持續歸檔 |
| Q | `paper_17_margin_liquidation_tracker.py` | 2029-01-02 後 | ①（共用 event） | ③ | **②** | — |
| R | `paper_18_sbl_covering_tracker.py` | 2029-01-02 後 | ①（共用 event） | ③ | **②** | — |

帳本進 repo 的確認：`research/data/` 整個被 `.gitignore`；`market.yml` 對 paper_5～8、10、11、13～18 帳本都用 `git add -f`，paper_9 已在 repo，paper_12 由本機 `scripts/run_warrant_snapshot.ps1` add -f。

## 結論

1. **②帳本本身沒有每日 nav：G（paper_7）、H（paper_8）兩支**——併進 1hx 修法範圍（1hx 原本只寫 G）。M 的「與 H 同期淨值差」揭露跟著 H。
2. **②隨機時點／控制組對照：I、J、K、L、M、N、O、P、Q、R 共 10 支**——判定時要「同一段期間整個宇宙的每日價格」去模擬 1,000 次隨機進場，帳本只有自己持股的價格，`data/price_history` 只留 90 日。
   - 可能的重建路：`data/price_history/` 從 2026-10-13 改分檔後每次排程都 commit（10 月起 52 版），git 歷史裡每一版都有全市場 90 日 OHLC＋`adj_close`，理論上可串回完整日線；**未實作、未驗證**，且還原價基準日會隨除權息改變，串接時只能用「同一版內相鄰兩天的比值」。
   - 這不是 1hx（策略曲線）的範圍 → 開新條目 **先.一三五-1ic**。
3. **③0050 含息長序列：14 支全部需要，目前 repo 沒有一條會持續更新到判定日的序列**——開新條目 **先.一三五-1ib**。查過的地方：
   - `research/data/etf0050_nav_daily.csv`：元大官方淨值，2013-01-02～**2024-12-31**，`research/fetch_0050_nav.py` 手動跑、未排程。
   - `data/price_history` 的 0050：90 筆滾動（目前 2026-06-22 起），有 `adj_close`（還原權息）但基準日會變。
   - `research/data/paper_7030_log.jsonl`（紙.一）：每月一筆 `price_0050`＝**原始收盤**、不含息。
   - `data/strategy_history.json`：0050 逐月只到 2026-09-30，不再更新；`data/strategy_curves.json` 灰線也是 90 日價格算的。
   - `data/ex_dividend_events.json`：目前最早 ex_date 2026-08-26、沒有 0050 這一檔的事件，是否長期保留舊事件**本輪未查證**。
4. **F／F-翼漏跑不補**：期交所選擇權日報只有當天，那一天沒跑到就永久缺點；MDD 會漏掉那天的盤中最低。屬於既知設計（PREREG 寫「前進式只能用當天資料」），本輪只記錄、不另開條目。

## 副帶發現（不在本條範圍，照實記錄）

- 紙.一（`paper_7030_tracker.py`，不在 14 支內）股票腿用 `price_0050`＝原始收盤逐月相乘，除息月的現金股利沒有進淨值（程式內搜「股利／dividend」無命中；`price_0050` 取 `price_row["close"]`、不是 `adj_close`）——開新條目 **先.一三五-1id** 查證影響（只記錄、本條不改）。
