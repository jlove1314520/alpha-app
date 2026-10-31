"""先.一三五-1gg 自測：reproducibility_check.check_one() 把 mem_guard 開跑門檻不足（exit 3）判 MEM_DEFERRED，
真的 ImportError 仍判 IMPORT_ERROR、exit 3 但沒有 mem_guard 字樣仍判 OTHER_ERROR。用暫存目錄的假腳本，不碰真資料。"""
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import reproducibility_check as rc  # noqa: E402

CASES = {
    "fake_mem_deferred": ('import sys\nprint("mem_guard.preflight：可用記憶體 2.31GB 低於開跑門檻 4.5GB，不開跑", flush=True)\n'
                          'sys.exit(3)\n', "MEM_DEFERRED"),
    "fake_import_error": ("import this_module_does_not_exist_xyz\n", "IMPORT_ERROR"),
    "fake_exit3_no_mark": ('import sys\nprint("別的原因", flush=True)\nsys.exit(3)\n', "OTHER_ERROR"),
    "fake_ok": ("x = 1\n", "OK"),
}

with tempfile.TemporaryDirectory() as d:
    tmp = Path(d)
    for name, (src, _) in CASES.items():
        (tmp / f"{name}.py").write_text(src, encoding="utf-8")
    rc.ROOT = tmp
    fails = 0
    for name, (_, want) in CASES.items():
        got = rc.check_one(name)
        ok = got["status"] == want
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {name}: 期望 {want}，實得 {got['status']} {got.get('available_gb', '')}")
    gb = rc.check_one("fake_mem_deferred").get("available_gb")
    if gb != 2.31:
        fails += 1
        print(f"FAIL available_gb 應為 2.31，實得 {gb}")
    else:
        print("PASS available_gb=2.31")

print("全部通過" if fails == 0 else f"{fails} 項失敗")
sys.exit(1 if fails else 0)
