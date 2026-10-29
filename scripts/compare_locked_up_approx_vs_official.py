# -*- coding: utf-8 -*-
"""先.一三五-1ar：前向追蹤漲停判斷「近似版」vs「官方檔位版」差異量測（零外部請求，只讀本機檔）。

比對兩組（全部普通股 × data/price_history 近 90 個交易日）：
A. 模擬 Q／R（paper_17／18）用的 `paper_forward_events.locked_up()`
   ＝核心檔 `costs.limit_status()`（前收 ±10%、不取整、除權息日不用參考價）
   vs `official_limit.OfficialLimits` ＋ `lock_status()`（模擬 J／N 修訂 R1 用的官方檔位版）。
B. 模擬 I（paper_9）`limit_up_at_entry`：還原收盤漲幅 ≥ +9.5%
   vs 原始收盤 ≥ 官方漲停價（同 J 的修訂 R1 定義）。
只數「判定不一致」的列數與舉例，不算任何報酬、不改任何追蹤程式。輸出 research/data/locked_up_approx_vs_official.json。
非投資建議。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import paper_forward_common as C  # noqa: E402
import paper_forward_events as E  # noqa: E402
from official_limit import OfficialLimits, lock_status  # noqa: E402

OUT = ROOT / "research" / "data" / "locked_up_approx_vs_official.json"


def main() -> int:
    px = C.load_px()
    ol = OfficialLimits()
    a = {"rows": 0, "both": 0, "approx_only": 0, "official_only": 0, "no_official": 0, "examples": []}
    b = {"rows": 0, "both": 0, "approx_only": 0, "official_only": 0, "no_official": 0, "examples": []}
    src_count: dict[str, int] = {}
    for code, rs in px.rows.items():
        if not C.is_common(code):
            continue
        for i in range(1, len(rs)):
            r, p = rs[i], rs[i - 1]
            try:
                o, h, l, c = (float(r[k]) for k in ("open", "high", "low", "close"))
                pc = float(p["close"])
            except (TypeError, ValueError, KeyError):
                continue
            if pc <= 0:
                continue
            day = r["date"]
            lim = ol.limits(code, day, p["date"], pc)
            # A：locked_up
            a["rows"] += 1
            ap = E.locked_up(px, code, day)
            if lim is None:
                a["no_official"] += 1
                of = False
            else:
                src_count[lim["src"]] = src_count.get(lim["src"], 0) + 1
                of = lock_status(lim, o, h, l, c)[0]
            if ap and of:
                a["both"] += 1
            elif ap != of:
                k = "approx_only" if ap else "official_only"
                a[k] += 1
                if len(a["examples"]) < 15:
                    a["examples"].append({"code": code, "date": day, "kind": k, "prev_close": pc, "ohlc": [o, h, l, c],
                                          "official_up": lim and lim["up"], "src": lim and lim["src"],
                                          "base_src": lim and lim["base_src"]})
            # B：paper_9 limit_up_at_entry（還原收盤 ≥ +9.5%）vs 原始收盤 ≥ 官方漲停價
            b["rows"] += 1
            av, ap_ = px.close_on(code, day), px.close_on(code, p["date"])
            approx_b = bool(av and ap_ and av / ap_ - 1 >= 0.095)
            off_b = bool(lim and c >= lim["up"] - 1e-9)
            if lim is None:
                b["no_official"] += 1
            if approx_b and off_b:
                b["both"] += 1
            elif approx_b != off_b:
                k = "approx_only" if approx_b else "official_only"
                b[k] += 1
                if len(b["examples"]) < 15:
                    b["examples"].append({"code": code, "date": day, "kind": k, "prev_close": pc, "close": c,
                                          "official_up": lim and lim["up"], "src": lim and lim["src"],
                                          "base_src": lim and lim["base_src"]})
    out = {"generated_by": "scripts/compare_locked_up_approx_vs_official.py（先.一三五-1ar）",
           "calendar": [px.calendar[0], px.calendar[-1]] if px.calendar else None,
           "official_src_count": src_count,
           "A_paper17_18_locked_up": a, "B_paper9_limit_up_at_entry": b,
           "note": "只數判定不一致列數，未算報酬、未改追蹤程式。非投資建議。"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("A_paper17_18_locked_up", "B_paper9_limit_up_at_entry"):
        d = out[k]
        print(k, {x: d[x] for x in ("rows", "both", "approx_only", "official_only", "no_official")})
    print("official_src_count", src_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
