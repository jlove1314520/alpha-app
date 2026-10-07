# Holdout access log

Every call to `unlock_holdout_once()`, successful or blocked, appended here. Append-only by convention -- do not edit past entries.

- **2026-09-26T00:50:10.050068+00:00** — CONSUMED. reason='H.一（2026-09-26總司令裁示【考.一結案確認＋新候選dividend×70/30＋holdout單次解鎖＋daily_price修正核准】）：dividend_yield_v1_common×帳戶70/30一致性檢查，期間2025-01-01~資料最新日，僅限TRIALS_LEDGER#400這一個候選，only-once。' approved_by='總司令（PENDING_QUEUE.md 2026-09-26 H.一裁示）'
- **2026-10-07T21:3x+08:00** — READ（非 unlock_holdout_once；該函式已於 2026-09-26 由 #400 用掉）。依總司令 2026-10-07【先.四十五】一原文「動用 2025-01-01～2026-09-30 保留資料，只此一次」，由互動視窗把 `bb90_oos_2025.py` 加入 `ALLOWED_HOLDOUT_READERS`（commit 04cdf67b7），執行 #423 Bb-90 樣本外單發一次（預登記 SHA256 ce89180b…，#418 原參數，結果檔存在即拒絕重跑）。approved_by='總司令（PENDING_QUEUE.md 2026-10-07 先.四十五 一）'
