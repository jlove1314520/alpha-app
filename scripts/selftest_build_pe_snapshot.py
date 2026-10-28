# -*- coding: utf-8 -*-
"""build_pe_snapshot 自測（先.一三八-8）：①上市／上櫃資料日不同時兩邊都產出 ②同日檔合併不丟列 ③內容相同不重寫。

只讀 data/fundamentals.json 與 price_history；寫入改到暫存資料夾，不碰 data/pe_snapshot/。零網路請求。
用法：python scripts/selftest_build_pe_snapshot.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import build_pe_snapshot as B  # noqa: E402

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f"（{detail}）" if detail else ""))
    fails += 0 if ok else 1


with tempfile.TemporaryDirectory() as td:
    B.OUT_DIR = Path(td)
    # ② 合併：先寫上市列，再寫上櫃列，同日檔要兩邊都在
    B.write_day("2099-01-02", {"2330": [1000.0, 20.0, 50.0]})
    B.write_day("2099-01-02", {"6488": [500.0, None, None]})
    rows = json.loads((B.OUT_DIR / "2099-01-02.json").read_text(encoding="utf-8"))["rows"]
    check("同日兩市場合併", set(rows) == {"2330", "6488"}, str(sorted(rows)))
    # ③ 相同內容不重寫
    p = B.OUT_DIR / "2099-01-02.json"
    before = p.read_text(encoding="utf-8")
    B.write_day("2099-01-02", {"2330": [1000.0, 20.0, 50.0]})
    check("內容相同不重寫", p.read_text(encoding="utf-8") == before)

# ① 真實資料：每個 ≥MIN_ROWS 的資料日都要產出
fund = json.loads((B.DATA / "fundamentals.json").read_text(encoding="utf-8")).get("fundamentals") or {}
cnt: dict[str, int] = {}
for v in fund.values():
    d = ((v or {}).get("ratios") or {}).get("date")
    if d:
        cnt[d] = cnt.get(d, 0) + 1
big = sorted(d for d, n in cnt.items() if n >= B.MIN_ROWS_PER_DAY)
days = B.build()
check("每個主要資料日都有產出", sorted(days) == big,
      f"資料日 {big}，產出 {sorted(days)}，檔數 {[len(days[d]) for d in sorted(days)]}")
check("小於門檻的零星舊日期不產出", all(cnt[d] >= B.MIN_ROWS_PER_DAY for d in days))

print("自測結果：" + ("全過" if not fails else f"{fails} 項失敗"))
sys.exit(1 if fails else 0)
