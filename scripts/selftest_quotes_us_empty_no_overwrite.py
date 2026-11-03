#!/usr/bin/env python3
"""先.一四七-2：美股報價（.github/scripts/fetch_quotes_us.py）整份 quotes 為空（Finnhub matched 0）時
不得覆蓋上一版好資料（CLAUDE.md 七節「失敗不覆蓋」）——合成自測。
只測 write_quotes_file()，輸出換暫存檔，零外部請求。"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fqu_selftest2", ROOT / ".github" / "scripts" / "fetch_quotes_us.py")
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
    p = Path(td) / "sub" / "quotes_us.json"
    good = {"fetched_at": "old", "meta": {"matched": 9}, "quotes": {"NVDA": {"price": 1}}}
    # 1. 有報價 → 寫檔（含建立目錄）
    check("有報價 → 寫入並回 True", m.write_quotes_file(good, p) is True and json.loads(p.read_text(encoding="utf-8")) == good)
    before = p.read_text(encoding="utf-8")
    # 2. quotes 為空 → 不覆蓋、回 False、印出 GitHub 告警
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = m.write_quotes_file({"fetched_at": "new", "meta": {"matched": 0}, "quotes": {}}, p)
    check("quotes 為空 → 回 False", r is False)
    check("quotes 為空 → 上一版原封不動", p.read_text(encoding="utf-8") == before)
    check("quotes 為空 → 印出 ::warning:: 告警", "::warning" in buf.getvalue(), buf.getvalue()[:200])
    # 3. quotes 欄位缺或為 None 也視為空
    for bad in ({"quotes": None}, {}):
        check(f"quotes={bad.get('quotes', '缺')!r} → 不覆蓋", m.write_quotes_file(bad, p) is False
              and p.read_text(encoding="utf-8") == before)
    # 4. 上一版不存在時，空結果也不產生檔案（不假裝有資料）
    q = Path(td) / "none.json"
    check("沒有上一版 + 空結果 → 不產生檔案", m.write_quotes_file({"quotes": {}}, q) is False and not q.exists())

print(f"\n{'全過' if not fails else '失敗 ' + str(len(fails)) + ' 項'}（共 {total} 項）")
sys.exit(1 if fails else 0)
