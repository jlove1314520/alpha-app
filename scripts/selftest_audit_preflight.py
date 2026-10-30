"""自測：稽核自檢 `scripts/audit_preflight.py`（先.一三五-1da）。

`ROOT`／`OUT` 換暫存目錄、`CHECKS` 換一條會過＋一條會失敗的假 import；暫存目錄放假的 net_guard.py、
假的 sync_continuation_prompts.py／reproducibility_check.py：零外部請求、不動真實 data/audit_report.json。
確認：import 失敗只寫進 self_check（ok=False＋錯誤訊息）且回 0；黑名單網域掃描命中／未接 net_guard 計數正確、
豁免 net_guard.py 本身；既有 audit_report 其他欄位保留；既有報告損壞／頂層陣列不拋例外；
子腳本不存在／逾時語意／沒產出結果檔 → ok=False 不拋例外；net_guard 讀不到 → 掃描回空、不拋例外。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("audit_preflight", ROOT / "scripts" / "audit_preflight.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


NET_GUARD = 'DOMAIN_BLOCKLIST: frozenset = frozenset({\n    "bad.example.com",\n    "evil.example.org",\n})\n'


def setup(root: Path, net_guard=NET_GUARD, sync=True, repro="ok", report=None) -> None:
    B.ROOT = root
    B.OUT = root / "data" / "audit_report.json"
    B.CHECKS = [("假模組會過", "import json"), ("假模組會壞", "import alpha_no_such_module_xyz")]
    for d in ("data", "research", "scripts"):
        (root / d).mkdir(parents=True, exist_ok=True)
    ng = root / "research" / "net_guard.py"
    if net_guard is None:
        if ng.exists():
            ng.unlink()
    else:
        ng.write_text(net_guard, encoding="utf-8")
    sp = root / "research" / "sync_continuation_prompts.py"
    if sync is None:
        if sp.exists():
            sp.unlink()
    else:
        sp.write_text("print('SYNCED')\n" if sync else "import sys; print('DRIFT'); sys.exit(1)\n", encoding="utf-8")
    rp = root / "research" / "reproducibility_check.py"
    res = root / "research" / "reproducibility_check_result.json"
    if res.exists():
        res.unlink()
    if repro is None:
        if rp.exists():
            rp.unlink()
    elif repro == "no_output":
        rp.write_text("pass\n", encoding="utf-8")
    else:
        broken = [] if repro == "ok" else ["research/x.py"]
        rp.write_text("import json, pathlib\n"
                      f"pathlib.Path(__file__).with_name('reproducibility_check_result.json').write_text("
                      f"json.dumps({{'broken': {broken!r}, 'n_checked': 3}}))\n", encoding="utf-8")
    if report is not None:
        B.OUT.write_text(report, encoding="utf-8")
    elif B.OUT.exists():
        B.OUT.unlink()
    (root / "scripts" / "guarded.py").write_text("import net_guard\nURL = 'https://bad.example.com/x'\n", encoding="utf-8")
    (root / "scripts" / "unguarded.py").write_text("A = 'evil.example.org'\nB = 'fine.example.net'\nC = 'bad.example.com'\n", encoding="utf-8")
    (root / "scripts" / "clean.py").write_text("print('hi')\n", encoding="utf-8")


def run_main():
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = B.main()
        return rc, buf.getvalue(), None
    except Exception as e:  # noqa: BLE001
        return None, buf.getvalue(), e


def report():
    return json.loads(B.OUT.read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory() as td:
    r = Path(td)

    print("情境一：正常執行（一條 import 會壞）")
    setup(r, report=json.dumps({"other_field": {"keep": 1}}))
    rc, out, err = run_main()
    check("回 0、無例外", rc == 0 and err is None, (rc, err))
    d = report()
    sc = d.get("self_check", {})
    check("self_check.ok=False（有一條失敗）", sc.get("ok") is False, sc)
    by = {c["label"]: c for c in sc.get("checks", [])}
    check("會過的那條 ok=True、error 空", by.get("假模組會過", {}).get("ok") is True and by["假模組會過"]["error"] == "")
    check("會壞的那條 ok=False、錯誤訊息含 ModuleNotFoundError",
          by.get("假模組會壞", {}).get("ok") is False and "ModuleNotFoundError" in by["假模組會壞"]["error"], by.get("假模組會壞"))
    check("印出 ::error::", "::error::" in out)
    check("既有 audit_report 其他欄位保留", d.get("other_field") == {"keep": 1})
    ds = d.get("domain_blocklist_scan", {})
    check("黑名單取自 net_guard.py", sorted(ds.get("domains", [])) == ["bad.example.com", "evil.example.org"], ds.get("domains"))
    check("命中 3 處（guarded 1、unguarded 2），豁免 net_guard.py 本身",
          ds.get("hit_count") == 3 and ds.get("unguarded_count") == 2
          and all(h["file"] != "research/net_guard.py" for h in ds.get("hits", [])), ds)
    check("unguarded 行號正確", sorted((h["file"], h["line"]) for h in ds.get("unguarded", []))
          == [("scripts/unguarded.py", 1), ("scripts/unguarded.py", 3)], ds.get("unguarded"))
    check("印出合規.三警告", "合規.三發現 2 處" in out)
    check("queue_depth_sync ok", d.get("queue_depth_sync", {}).get("ok") is True)
    check("reproducibility_check ok、n_checked=3",
          d.get("reproducibility_check", {}).get("ok") is True and d["reproducibility_check"]["detail"].get("n_checked") == 3)

    print("情境二：全部 import 都過")
    setup(r)
    B.CHECKS = [("假模組會過", "import json")]
    rc, out, err = run_main()
    check("self_check.ok=True、不印 ::error::", rc == 0 and report()["self_check"]["ok"] is True and "::error::" not in out)

    print("情境三：子腳本不同步／壞掉／不存在／沒產出")
    setup(r, sync=False)
    run_main()
    check("佇列門檻不同步 → ok=False", report()["queue_depth_sync"]["ok"] is False)
    setup(r, sync=None, repro=None)
    rc, out, err = run_main()
    check("兩支子腳本都不存在 → 兩欄 ok=False、回 0",
          rc == 0 and err is None and report()["queue_depth_sync"]["ok"] is False
          and report()["reproducibility_check"]["ok"] is False, (rc, err))
    setup(r, repro="no_output")
    run_main()
    check("reproducibility 沒產出結果檔 → ok=False＋說明",
          report()["reproducibility_check"]["ok"] is False and "沒有產出" in report()["reproducibility_check"]["detail"]["error"])
    setup(r, repro="broken")
    rc, out, err = run_main()
    check("reproducibility 有 broken → ok=False＋警告", report()["reproducibility_check"]["ok"] is False and "reproducibility_check發現" in out)

    print("情境四：既有報告損壞／頂層陣列／net_guard 讀不到")
    for label, raw in [("損壞", "{"), ("頂層陣列", "[1]"), ("空檔", "")]:
        setup(r, report=raw)
        rc, out, err = run_main()
        check(f"既有報告{label} → 不拋例外、重建報告", rc == 0 and err is None and "self_check" in report(), (rc, err))
    setup(r, net_guard=None)
    rc, out, err = run_main()
    ds = report()["domain_blocklist_scan"]
    check("net_guard.py 不存在 → 黑名單空、命中 0、不拋例外", rc == 0 and ds["domains"] == [] and ds["hit_count"] == 0, ds)
    setup(r, net_guard="DOMAIN_BLOCKLIST = set()\n")
    rc, out, err = run_main()
    check("net_guard.py 格式認不得 → 黑名單空、不拋例外", rc == 0 and report()["domain_blocklist_scan"]["domains"] == [])

    print("情境五：報告檔寫不進去（先.一三五-1dc）")
    setup(r)
    B.OUT = r / "data" / "as_dir"
    B.OUT.mkdir(exist_ok=True)
    rc, out, err = run_main()
    check("OUT 是目錄 → 不拋例外、回 0、印 ::warning::", err is None and rc == 0 and "::warning::稽核自檢報告寫不進" in out, (rc, err))
    check("OUT 是目錄 → 自檢結果仍印出", "FAIL 假模組會壞" in out and "OK 假模組會過" in out)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
