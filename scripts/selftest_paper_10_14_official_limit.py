# -*- coding: utf-8 -*-
"""先.一四一-1 自測：模擬 J／N 漲跌停判斷改官方檔位版（PREREG 修訂 R1）。

全部用合成數字（跨檔位邊界、上櫃有／無公告檔、除權息日、減資恢復日），不讀真實價格、不算任何報酬、
不寫兩支帳本（research/data/paper_10_log.jsonl／paper_14_log.jsonl）。零外部請求。
用法：python scripts/selftest_paper_10_14_official_limit.py
"""
from __future__ import annotations

import copy
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援時照舊輸出
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import paper_forward_common as C  # noqa: E402
import paper_10_disposition_tracker as J  # noqa: E402
import paper_14_grid_range_tracker as N  # noqa: E402
from official_limit import OfficialLimits, lock_status  # noqa: E402

FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def bdays(n, start=date(2026, 12, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def main() -> int:
    log10 = ROOT / "research" / "data" / "paper_10_log.jsonl"
    log14 = ROOT / "research" / "data" / "paper_14_log.jsonl"
    existed = (log10.exists(), log14.exists())

    # ---- 1. OfficialLimits：上市跨檔位、上櫃有／無公告、除權息、減資 ----
    tpex = [{"data_date": "2026-12-01", "rows": {"6001": [55.5, 45.5]}}]
    exdiv = {"events": {"2002": [{"ex_date": "2026-12-02", "factor_applied": 0.9}]},
             "reductions": {"2003": [{"resume_date": "2026-12-02", "ref_price": 20.0}]}}
    L = OfficialLimits(tpex_docs=tpex, exdiv=exdiv)
    a = L.limits("2001", "2026-12-02", "2026-12-01", 45.5)  # 45.5×1.1＝50.05 → 50 元以上檔位 0.1 → 50.0
    check("上市跨檔位 45.5→漲停 50.0", a and abs(a["up"] - 50.0) < 1e-9 and a["src"] == "calc", str(a))
    check("上市 跌停 45.5×0.9＝40.95（10～50 元檔位 0.05）", a and abs(a["down"] - 40.95) < 1e-9, str(a and a["down"]))
    check("舊近似 1.095 會把 49.9 誤標漲停、官方版不會", 49.9 >= 45.5 * 1.095 and not 49.9 >= a["up"])
    b = L.limits("6001", "2026-12-02", "2026-12-01", 50.5)
    check("上櫃有前一日公告 → tpex_official 55.5／45.5", b and b["src"] == "tpex_official" and b["up"] == 55.5 and b["down"] == 45.5, str(b))
    b2 = L.limits("6001", "2026-12-03", "2026-12-02", 50.5)  # 12-02 那份缺
    check("上櫃缺當天公告 → calc_tpex_missing 計算", b2 and b2["src"] == "calc_tpex_missing" and abs(b2["up"] - 55.5) < 1e-9, str(b2))
    e = L.limits("2002", "2026-12-02", "2026-12-01", 100.0)  # 參考價 90 → 99.0
    check("除權息日基準用參考價 90 → 漲停 99.0", e and abs(e["up"] - 99.0) < 1e-9 and e["base_src"] == "exdiv_ref", str(e))
    r = L.limits("2003", "2026-12-02", "2026-12-01", 8.0)  # 減資參考價 20 → 22.0
    check("減資恢復日基準用 ref_price 20 → 22.0", r and abs(r["up"] - 22.0) < 1e-9 and r["base_src"] == "reduction_ref", str(r))
    check("無前收 → None（不算漲跌停）", L.limits("2001", "2026-12-02", "2026-12-01", None) is None)
    check("lock_status 一字漲停", lock_status(a, 50.0, 50.0, 50.0, 50.0) == (True, False))
    check("lock_status 一字跌停", lock_status(a, 40.95, 40.95, 40.95, 40.95) == (False, True))
    check("lock_status 盤中打開不算鎖", lock_status(a, 50.0, 50.0, 49.5, 50.0) == (False, False))
    check("lock_status lim=None → 都不算", lock_status(None, 1, 1, 1, 1) == (False, False))

    # ---- 2. 模擬 J：make_signal 的 limit_up_at_entry ----
    cal = bdays(30)
    def series(code, closes):
        return [{"date": d, "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1e6, "turnover": 5e7}
                for d, c in zip(cal, closes)]
    base = [60.0] * 22 + [55.0, 50.0, 47.0, 45.5]  # cal[22]～cal[25] 處置期間下跌，r＝cal[25] 原始收 45.5
    prices = {"2001": series("2001", base + [50.0, 50, 50, 50]),   # r+1 收 50.0＝官方漲停
              "2004": series("2004", base + [49.9, 50, 50, 50]),   # r+1 收 49.9＝舊近似會誤標
              "6001": series("6001", base[:-1] + [50.5] + [55.5, 55, 55, 55])}  # 上櫃，公告漲停 55.5
    px = C.Px(prices)
    r_day, day = cal[25], cal[26]
    segs = [{"code": c, "start": cal[22], "end": r_day} for c in prices]
    lim = OfficialLimits(tpex_docs=[{"data_date": r_day, "rows": {"6001": [55.5, 45.5]}}], exdiv={})
    uni = {c: True for c in prices}
    out = {c["code"]: c for c in J.make_signal(segs, control=False)({"px": px, "limits": lim}, day, uni)}
    check("J：三檔都入選", set(out) == set(prices), str(sorted(out)))
    check("J：2001 收 50.0 ≥ 官方漲停 50.0 → True", out.get("2001", {}).get("limit_up_at_entry") is True, str(out.get("2001")))
    check("J：2004 收 49.9 < 50.0 → False（舊近似會 True）", out.get("2004", {}).get("limit_up_at_entry") is False, str(out.get("2004")))
    check("J：6001 用上櫃公告 → True、limit_src＝tpex_official",
          out.get("6001", {}).get("limit_up_at_entry") is True and out["6001"]["limit_src"] == "tpex_official", str(out.get("6001")))
    check("J：列上有 limit_base", out.get("2001", {}).get("limit_base") == "raw_prev_close")
    check("J：模組不再有 LIMIT_UP_RATIO", not hasattr(J, "LIMIT_UP_RATIO"))

    # ---- 3. 模擬 N：process_day 開盤掛單遇一字漲停／跌停 ----
    d0, d1 = cal[0], cal[1]
    def grid_px(o1):
        return C.Px({"2001": [{"date": d0, "open": 45.5, "high": 45.5, "low": 45.5, "close": 45.5, "adj_close": 22.75, "turnover": 1e8},
                              {"date": d1, "open": o1, "high": o1, "low": o1, "close": o1, "adj_close": o1 / 2, "turnover": 1e8}]})
    def state():
        st = N.empty_state()
        st["month"] = d1[:7]
        st["pend_buy"] = {"2001": [0]}
        st["last_c"] = {"2001": 22.75}
        return st
    L0 = OfficialLimits(tpex_docs=[], exdiv={})
    rec = N.process_day(grid_px(50.0), d1, state(), {"2001"}, True, L0)
    check("N：原始一字 50.0＝官方漲停 → 買單取消", rec.get("buy_blocked_limit") == 1 and not rec["positions"], str({k: rec.get(k) for k in ("buy_blocked_limit", "limit_src")}))
    check("N：帳本列記 limit_src", rec.get("limit_src") == {"calc": 1}, str(rec.get("limit_src")))
    rec2 = N.process_day(grid_px(49.9), d1, state(), {"2001"}, True, L0)
    check("N：49.9 未達官方漲停 → 照常買進", "2001" in rec2["positions"] and not rec2.get("buy_blocked_limit"), str(rec2.get("positions")))
    st = state()
    st["pend_buy"], st["cells"], st["pend_sell"] = {}, {"2001": {0: {"units": 1.0, "entry_date": d0, "entry_px": 22.75}}}, {"2001": [0]}
    rec3 = N.process_day(grid_px(40.95), d1, copy.deepcopy(st), {"2001"}, True, L0)
    check("N：原始一字 40.95＝官方跌停 → 賣單順延", rec3["positions"].get("2001") and rec3["grid_state"]["pend_sell"].get("2001") == [0], str(rec3["grid_state"]["pend_sell"]))
    rec4 = N.process_day(grid_px(41.0), d1, copy.deepcopy(st), {"2001"}, True, L0)
    check("N：41.0 未鎖跌停 → 賣出", not rec4["positions"] and rec4["closed_trades"], str(rec4["closed_trades"]))
    check("N：模組不再 import costs.limit_status", not hasattr(N, "limit_status"))

    # ---- 4. 不得產生帳本 ----
    check("兩支帳本仍未產生（或維持原狀）", (log10.exists(), log14.exists()) == existed and existed == (False, False), str(existed))

    print(f"\n合計 {'全部通過' if not FAIL else f'{len(FAIL)} 項失敗：' + '、'.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
