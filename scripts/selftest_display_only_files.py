# -*- coding: utf-8 -*-
"""先.一百-4（2026-10-15）：App 顯示用回補檔不得被研究端讀取的守門自測。
掃 research/ 底下所有 .py（含子目錄；不含 research/validation/holdout.py 本身的清單定義），
出現 research/validation/holdout.py::DISPLAY_ONLY_DATA_FILES 任何一個檔名就 FAIL。
scripts/ 底下（build_research.py、backfill_*.py 這些 App 顯示端）不在檢查範圍。
另外自測守門本身：餵一段含檔名的假程式，確認會被抓到。用法：python scripts/selftest_display_only_files.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from validation.holdout import DISPLAY_ONLY_DATA_FILES  # noqa: E402

SELF = (ROOT / "research" / "validation" / "holdout.py").resolve()


def hits(text: str) -> list[str]:
    return [n for n in sorted(DISPLAY_ONLY_DATA_FILES) if n in text]


res = []
res.append(("守門能抓到假程式裡的檔名", hits('open("data/revenue_backfill.json")') == ["revenue_backfill.json"]))
bad = []
for p in sorted((ROOT / "research").rglob("*.py")):
    if p.resolve() == SELF or "__pycache__" in p.parts:
        continue
    try:
        h = hits(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        continue
    if h:
        bad.append(f"{p.relative_to(ROOT)}：{','.join(h)}")
res.append((f"research/ 底下沒有程式引用 App 顯示用回補檔（{len(DISPLAY_ONLY_DATA_FILES)} 個檔名）" + ("" if not bad else "；" + "；".join(bad[:5])), not bad))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
nb = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {nb}")
sys.exit(1 if nb else 0)
