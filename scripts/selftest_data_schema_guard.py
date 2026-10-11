"""常備.開發-28 自測：data_schema_guard 的驗證規則＋「失敗不覆蓋」＋守門員自身失敗 fail open（十二節第4點）。

在暫存 git repo 裡跑，不碰真的 data/。用法：python scripts/selftest_data_schema_guard.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_schema_guard as g  # noqa: E402

FAILS: list[str] = []


def ok(cond: bool, name: str) -> None:
    print(("✓ " if cond else "✗ ") + name)
    if not cond:
        FAILS.append(name)


GOOD_FX = {"fetched_at": "2026-10-11T10:00:00+08:00", "errors": [], "usd_twd": {"rate": 32.1}}

# ---- 規則 ----
ok(g.validate_obj("data/fx.json", GOOD_FX) == [], "合法 fx.json 通過")
ok(any("usd_twd" in e for e in g.validate_obj("data/fx.json", {"fetched_at": "2026-10-11", "errors": []})),
   "缺必要欄位被抓")
ok(any("型別" in e for e in g.validate_obj("data/fx.json", {**GOOD_FX, "usd_twd": "x"})), "型別錯被抓")
ok(any("時間戳" in e for e in g.validate_obj("data/fx.json", {**GOOD_FX, "fetched_at": "昨天"})), "時間戳無法解析被抓")
ok(any("時間戳" in e for e in g.validate_obj("data/fx.json", {k: v for k, v in GOOD_FX.items() if k != "fetched_at"})),
   "缺時間戳被抓")
ok(g.validate_obj("data/fx.json", {**GOOD_FX, "fetched_at": "2026-10-11T02:00:00Z"}) == [], "Z 結尾時間戳可解析")
ok(any("頂層" in e for e in g.validate_obj("data/fx.json", [1, 2])), "頂層型別錯被抓")
sc = {"meta": {"generated_at": "2026-10-11T10:00:00+08:00"}, "stocks": []}
ok(any("為空" in e for e in g.validate_obj("scores.json", sc)), "大型資料檔 stocks 為空被抓")
ok(g.validate_obj("data/paper_trades.json", {"generated_at": None, "strategies": []}) == [], "ts_nullable 允許 null")
ok(any("ts" in e or "時間戳" in e for e in g.validate_obj("data/margin_maintenance.json", [])) or
   any("清單為空" in e for e in g.validate_obj("data/margin_maintenance.json", [])), "清單型空清單被抓")
ok(any("ratio_pct" in e for e in g.validate_obj("data/margin_maintenance.json", [{"date": "2026-10-01"}])),
   "清單元素缺欄位被抓")
ok(g.validate_obj("data/未登記.json", {}) == [], "未登記檔不檢查")
ok(g.validate_obj("data/fx.json", {**GOOD_FX, "usd_twd": True}) != [], "bool 不得冒充 dict")
ok(g.validate_obj("data/audit_report.json", {"generated_at": "2026-10-11T00:00:00", "violation_rate": True,
                                              "universe": 1}) != [], "bool 不得冒充 num")

# ---- 實際 git repo 內的守門流程 ----
with tempfile.TemporaryDirectory() as td:
    repo = Path(td)
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)
    run("init", "-q")
    run("config", "user.email", "selftest@example.invalid")
    run("config", "user.name", "selftest")
    (repo / "data").mkdir()
    fx = repo / "data" / "fx.json"
    fx.write_text(json.dumps(GOOD_FX), encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "init")
    g.REPO = repo

    # 1) 寫壞（NaN）→ 還原上一版
    fx.write_text('{"fetched_at":"2026-10-12T10:00:00+08:00","errors":[],"usd_twd":{"rate":NaN}}', encoding="utf-8")
    res = g.guard(None, "data/schema_guard/test.json", "selftest")
    ok(len(res["rejected"]) == 1 and "NaN" in res["rejected"][0]["errors"][0], "NaN 檔被攔下")
    ok(json.loads(fx.read_text(encoding="utf-8")) == GOOD_FX, "被攔下的檔已還原成 HEAD 版本（失敗不覆蓋）")
    rep = json.loads((repo / "data/schema_guard/test.json").read_text(encoding="utf-8"))
    ok(rep["rejected"][0]["file"] == "data/fx.json", "告警報告記錄被攔下的檔")

    # 2) 合法更新 → 放行
    newer = {**GOOD_FX, "fetched_at": "2026-10-12T10:00:00+08:00"}
    fx.write_text(json.dumps(newer), encoding="utf-8")
    res = g.guard(None, None, "selftest")
    ok(res["rejected"] == [] and res["checked"] == ["data/fx.json"], "合法更新放行")
    ok(json.loads(fx.read_text(encoding="utf-8")) == newer, "合法更新內容保留")

    # 3) 未追蹤新檔寫壞 → 移出 repo
    mt = repo / "data" / "market_us.json"
    mt.write_text('{"fetched_at":"2026-10-12T10:00:00+08:00"}', encoding="utf-8")
    res = g.guard(None, None, "selftest")
    ok(not mt.exists() and any(r["file"] == "data/market_us.json" for r in res["rejected"]), "未追蹤壞新檔移出 repo")

    # 4) BOM
    fx.write_text("﻿" + json.dumps(GOOD_FX), encoding="utf-8")
    res = g.guard(["data/fx.json"], None, "selftest")
    ok(len(res["rejected"]) == 1 and "BOM" in res["rejected"][0]["errors"][0], "BOM 被攔下（--files 指定模式）")

    # 5) 報告內容沒變不重寫
    rp = repo / "data/schema_guard/test2.json"
    g.guard(None, "data/schema_guard/test2.json", "selftest")
    m1 = rp.read_text(encoding="utf-8")
    g.guard(None, "data/schema_guard/test2.json", "selftest")
    ok(rp.read_text(encoding="utf-8") == m1, "結果沒變時報告不重寫（不產生空 commit）")

    # 6) 守門員自身失敗 → fail open，exit 0，不動檔案
    fx.write_text(json.dumps(newer), encoding="utf-8")
    orig = g._changed_registered
    g._changed_registered = lambda: (_ for _ in ()).throw(RuntimeError("模擬守門員壞掉"))
    res = g.guard(None, None, "selftest")
    g._changed_registered = orig
    ok(res["guard_error"] and "模擬" in res["guard_error"] and res["rejected"] == [], "守門員自身例外 → fail open")
    ok(json.loads(fx.read_text(encoding="utf-8")) == newer, "fail open 時檔案不被動到")
    orig_guard = g.guard
    g.guard = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("更外層壞掉"))
    ok(g.main(["guard"]) == 0, "main() 外層例外也 exit 0")
    g.guard = orig_guard

print(f"\n{'全部通過' if not FAILS else f'{len(FAILS)} 項失敗'}")
sys.exit(1 if FAILS else 0)
