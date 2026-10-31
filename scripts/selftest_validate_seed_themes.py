# -*- coding: utf-8 -*-
"""先.一三五-1fd 自測：種子題材表校驗（validate_seed_themes.main）。

輸入／輸出全換暫存目錄；零外部請求、不碰真 data/seed。
用法：python scripts/selftest_validate_seed_themes.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import validate_seed_themes as V  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def setup(root: Path, active, themes):
    (root / "data" / "seed").mkdir(parents=True, exist_ok=True)
    V.ROOT = root
    V.SEED = root / "data" / "seed" / "seed_themes.json"
    V.OUT = root / "data" / "seed" / "seed_themes_validated.json"
    V.REPORT = root / "data" / "seed" / "seed_validation_report.md"
    V.SEED.write_text(json.dumps({"version": 1, "themes": themes}, ensure_ascii=False), encoding="utf-8")
    if active is not None:
        (root / "data" / "listed_universe.json").write_text(json.dumps({"active": active}), encoding="utf-8")


THEMES = [
    {"id": "ai", "name": "AI", "chain": "半導體", "members": ["2330", "2330", "6market", "2454"]},
    {"id": "pcb", "name": "PCB", "chain": "電子", "members": ["2330", "3037"]},
    {"id": "junk", "name": "垃圾", "chain": "x", "members": ["6胡", "4points"]},
]

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    setup(root, ["2330", "2454", "3037"], THEMES)
    rc = V.main()
    out = json.loads(V.OUT.read_text(encoding="utf-8"))
    by = {t["id"]: t for t in out["themes"]}
    check("正常跑完 exit 0", rc == 0)
    check("同一題材內重複代號去重", by["ai"]["members"] == ["2330", "2454"])
    check("多重歸屬不去重（2330 同時在 ai／pcb）", "2330" in by["pcb"]["members"])
    check("壞代號逐一列在 members_dropped", by["ai"]["members_dropped"] == ["6market"])
    check("全壞的題材列進 themes_emptied", out["validation"]["themes_emptied"] == ["junk"])
    check("剔除數＝3（6market／6胡／4points）", out["validation"]["codes_dropped"] == 3)
    check("全部標 evidence_level=D", all(t["evidence_level"] == "D" for t in out["themes"]))
    check("報告檔有寫且列出壞代號", "`6胡`" in V.REPORT.read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    setup(root, [], THEMES)
    V.OUT.write_text('{"keep": 1}', encoding="utf-8")
    rc = V.main()
    check("名冊 active 是空的 → 非 0 且不覆寫既有輸出", rc != 0 and V.OUT.read_text(encoding="utf-8") == '{"keep": 1}')

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    setup(root, None, THEMES)
    V.OUT.write_text('{"keep": 1}', encoding="utf-8")
    try:
        rc = V.main()
    except Exception as e:  # noqa: BLE001
        rc = f"例外 {e!r}"
    check("名冊檔不存在 → 非 0、不拋例外、不覆寫", rc not in (0,) and not str(rc).startswith("例外")
          and V.OUT.read_text(encoding="utf-8") == '{"keep": 1}')

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    setup(root, ["2330"], [])
    V.OUT.write_text('{"keep": 1}', encoding="utf-8")
    rc = V.main()
    check("種子題材是空的 → 非 0 且不覆寫", rc != 0 and V.OUT.read_text(encoding="utf-8") == '{"keep": 1}')

print(f"\n{sum(results)}/{len(results)} PASS")
sys.exit(0 if all(results) else 1)
