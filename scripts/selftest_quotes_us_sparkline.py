#!/usr/bin/env python3
"""先.一三五-1ea：美股報價（.github/scripts/fetch_quotes_us.py）sparkline 單檔沒抓到時沿用上一份——合成自測。
只測 reuse_prev_sparklines()，上一份檔案換暫存，零外部請求。"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fqu_selftest", ROOT / ".github" / "scripts" / "fetch_quotes_us.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
fails, total = [], 0


def check(name, ok, detail=""):
    global total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail and not ok else ""))
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as td:
    prev = Path(td) / "quotes_us.json"
    prev.write_text(json.dumps({"quotes": {"NVDA": {"sparkline": [1.0, 2.0, 3.0]}, "AAPL": {"sparkline": [9.0]},
                                           "MSFT": {"sparkline": [5.0, 6.0]}}}), encoding="utf-8")
    q = {"NVDA": {"price": 1}, "AAPL": {"price": 2}, "MSFT": {"price": 3, "sparkline": [7.0, 8.0]}, "TSLA": {"price": 4}}
    r = m.reuse_prev_sparklines(q, prev)
    check("缺的檔沿用上一份並回報代號", r == ["NVDA"] and q["NVDA"]["sparkline"] == [1.0, 2.0, 3.0], str(r))
    check("本輪有抓到的不被舊值蓋掉", q["MSFT"]["sparkline"] == [7.0, 8.0])
    check("上一份不足 2 點／沒有該檔 → 不沿用", "sparkline" not in q["AAPL"] and "sparkline" not in q["TSLA"])
    check("全都有 → 回空清單", m.reuse_prev_sparklines({"X": {"sparkline": [1, 2]}}, prev) == [])
    for bad in ("{壞", "[]", ""):
        prev.write_text(bad, encoding="utf-8")
        q2 = {"NVDA": {"price": 1}}
        ok = m.reuse_prev_sparklines(q2, prev) == [] and "sparkline" not in q2["NVDA"]
        check(f"上一份壞檔（{bad!r}）不拋例外、不沿用", ok)
    q3 = {"NVDA": {"price": 1}}
    check("上一份不存在不拋例外", m.reuse_prev_sparklines(q3, Path(td) / "nope.json") == [])

print(f"\n{'全過' if not fails else '失敗 ' + str(len(fails)) + ' 項'}（共 {total} 項）")
sys.exit(1 if fails else 0)
