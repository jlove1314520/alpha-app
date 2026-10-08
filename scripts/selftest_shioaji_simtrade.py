# -*- coding: utf-8 -*-
"""先.五十一-1 自我測試：股票 tick handler 收到試撮 tick（tick.simtrade 為真）時，
不得改動 last／change_pct、不得進 1 分K 走勢與量、不得落地，只寫 sim_price／sim_at。
用法：python scripts/selftest_shioaji_simtrade.py（純離線，不登入 Shioaji、不送 UDP、不寫熱檔）。
全部通過 exit 0，否則 exit 1。"""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import shioaji_quotes as sq  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


class _FakeRecorder:
    def __init__(self):
        self.n = 0

    def record(self, key, tick, bid=None, ask=None):
        self.n += 1


def _tick(close, simtrade, hhmm, volume=5):
    h, m = hhmm
    return SimpleNamespace(close=str(close), pct_chg="1.0", price_chg="1.0", volume=volume,
                           total_volume=100, chg_type=2, simtrade=simtrade,
                           datetime=datetime(2026, 10, 8, h, m, 0))


def main() -> int:
    rec = _FakeRecorder()
    sq.RECORDER = rec
    st = sq.TickState()
    st.live_state_path = None  # 不寫熱檔
    st.push_addr = None        # 不送 UDP
    h = sq._make_tick_stk_handler(st, "2330", None)

    h(_tick(101.0, False, (9, 1)))
    q = st.snapshot()["2330"]
    bars = st.kbars_snapshot().get("2330") or []
    check("真成交 tick 寫入 last", q.get("last") == 101.0, str(q.get("last")))
    base_bars = len(bars)
    base_vol = sum(b["v"] for b in bars)
    check("真成交 tick 進 1 分K", base_bars == 1 and base_vol == 5, f"bars={base_bars} vol={base_vol}")
    check("真成交 tick 有落地", rec.n == 1, str(rec.n))

    h(_tick(150.0, True, (13, 26), volume=999))
    q = st.snapshot()["2330"]
    bars = st.kbars_snapshot().get("2330") or []
    check("試撮 tick 不改 last", q.get("last") == 101.0, str(q.get("last")))
    check("試撮 tick 不改 change_pct", q.get("change_pct") == 1.0, str(q.get("change_pct")))
    check("試撮 tick 寫 sim_price", q.get("sim_price") == 150.0, str(q.get("sim_price")))
    check("試撮 tick 寫 sim_at", str(q.get("sim_at", "")).startswith("2026-10-08T13:26"), str(q.get("sim_at")))
    check("試撮 tick 不進 1 分K（根數與量不變）",
          len(bars) == base_bars and sum(b["v"] for b in bars) == base_vol,
          f"bars={len(bars)} vol={sum(b['v'] for b in bars)}")
    check("試撮 tick 不落地", rec.n == 1, str(rec.n))

    # 沒有 simtrade 屬性的舊版 tick 物件照真成交處理（不因缺欄位而誤判成試撮）
    t = _tick(102.0, False, (9, 2))
    del t.simtrade
    h(t)
    check("缺 simtrade 欄位視為真成交", st.snapshot()["2330"].get("last") == 102.0)

    print("失敗：", "、".join(fails) if fails else "無")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
