# -*- coding: utf-8 -*-
"""自測：前向追蹤共用框架把 close=0（零成交日）當「當天無價」（先.一三五-1iy）。

背景：price_history 以 close=0.0、adj_close=0.0 記零成交日（2026 年內 491 列，部分還有 volume>0，
例：1259 2026-06-15 close=0.0 volume=278）。1iy 用真實資料把模擬 O 提前跑，`_day_weighted` 除以零崩潰；
同一個形狀也會讓 `_mark` 以 0 計值、模擬 I 以 0 元出場／誤觸移動停損。
全部用合成資料（形狀照真實列），零外部請求、不碰真實帳本。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_forward_common as C  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def row(d, c, vol=1000.0):
    return {"date": d, "close": c, "adj_close": c, "volume": vol, "turnover": (c or 0) * vol * 1000}


days = [f"2026-11-{i:02d}" for i in range(2, 30)]
prices = {"1111": [row(d, 50.0) for d in days],
          # 2222：11-10 零成交（真實列形狀：close=0.0、adj_close=0.0、volume>0）
          "2222": [row(d, 0.0, 278.0) if d == "2026-11-10" else row(d, 20.0) for d in days]}
px = C.Px(prices)

check(px.close_on("2222", "2026-11-10") is None, "close=0 那天 close_on 回 None")
check(px.raw_close_on("2222", "2026-11-10") is None, "close=0 那天 raw_close_on 回 None")
check(px.close_le("2222", "2026-11-10") == 20.0, "close_le 跳過 0、回前一個有價日")
check(px.close_on("2222", "2026-11-11") == 20.0, "下一個有價日照常")

pos = {"2222": {"units": 100.0, "entry_date": "2026-11-02", "entry_px": 20.0}}
vals = C._mark(px, pos, "2026-11-10", {"1111", "2222"}, "zero")
check(abs(vals["2222"] - 2000.0) < 1e-9, "持股遇零成交日以前一有價日計值（不是 0）")

uni = C.universe(px, "2026-11-10", {"1111", "2222"}, None)
check("2222" not in uni and "1111" in uni, "零成交日不進當天宇宙")

# 模擬 O 的 weighted 模式：訊號給到零成交那檔也不能除以零
with tempfile.TemporaryDirectory() as td:
    sp = C.Spec(key="t", label="t", note="t", prereg="t", trial_no=0, start_not_before="2026-11-10",
                judge_after="2099-01-01", mode="weighted", top_n=2, delist_value="last",
                signal=lambda ctx, d, u: [{"code": "1111", "weight": 0.5}, {"code": "2222", "weight": 0.5}],
                log_path=Path(td) / "l.jsonl", out_path=Path(td) / "o.json", judge_text="t", known_limit="t")
    state = {"positions": {}, "cash": 1_000_000.0, "started": False, "last_rebalance_month": None}
    try:
        rec = C._day_weighted(sp, px, "2026-11-10", state, {}, {"1111", "2222"})
        ok = "2222" not in rec["positions"] and "1111" in rec["positions"]
    except ZeroDivisionError as e:
        ok, rec = False, e
    check(ok, f"weighted 模式：零成交那檔不建倉、不除以零（{type(rec).__name__}）")

# 模擬 I：持股遇零成交日不以 0 元成交／不誤觸移動停損
import paper_9_breakout_tracker as I  # noqa: E402

st = {"positions": {"2222": {"units": 100.0, "entry_date": "2026-11-02", "entry_px": 20.0, "peak_adj": 20.0,
                             "adj_mult": 1.0, "held_days": 3, "signal_date": "2026-11-01"}},
      "cash": 0.0, "started": True,
      "pending_exits": [{"code": "2222", "reason": "hold_days", "decided": "2026-11-09"}], "pending_entries": []}
try:
    rec = I._day(px, {}, "2026-11-10", st, {"1111", "2222"}, 0.001, 0.004)
    held = "2222" in rec["positions"] and not rec["closed_trades"]
    nav_ok = abs(rec["nav"] - 2000.0) < 1e-6
except Exception as e:  # noqa: BLE001
    held, nav_ok, rec = False, False, e
check(held, "模擬 I：零成交日不執行出場（不會以 0 元賣出），延到有價日")
check(nav_ok, "模擬 I：零成交日淨值以前一有價日計（2,000），不是 0")

print(f"\n{'全部通過' if not fails else f'{len(fails)} 項 FAIL'}")
sys.exit(1 if fails else 0)
