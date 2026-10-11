"""先.七十一-2 驗收：mp_guard.start_parent_watchdog() 真的能讓「父行程被硬砍」後的 worker 自我結束。

重現 2026-10-05 事故的形狀：父行程開 ProcessPoolExecutor（worker 閒置等工作）→ 從外部 taskkill /F 只砍父行程
（不帶 /T）→ 檢查 worker 是否在數秒內自己結束。另跑一組「不裝 watchdog」的對照組，證明這個測試本身抓得到孤兒
（對照組留下的孤兒由本測試自行清掉）。只在 Windows 跑。
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = textwrap.dedent(r"""
    import os, sys, time
    sys.path.insert(0, r"{here}")
    from concurrent.futures import ProcessPoolExecutor
    import mp_guard

    def _init():
        if {guard}:
            mp_guard.start_parent_watchdog(check_seconds=1)

    def _pid(_):
        time.sleep(0.5)
        return os.getpid()

    if __name__ == "__main__":
        ex = ProcessPoolExecutor(max_workers=3, initializer=_init)
        pids = sorted(set(ex.map(_pid, range(12))))
        print("WORKERS", " ".join(map(str, pids)), flush=True)
        time.sleep(600)
""")


def _alive(pid: int) -> bool:
    import mp_guard
    return mp_guard._pid_alive(pid)


def _run(guard: bool) -> tuple[list[int], list[int]]:
    sys.path.insert(0, str(HERE))
    script = HERE / f"_mp_guard_parent_tmp_{int(guard)}.py"
    script.write_text(PARENT.format(here=str(HERE), guard=guard), encoding="utf-8")
    try:
        p = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
        line = ""
        t0 = time.time()
        while time.time() - t0 < 60:
            line = p.stdout.readline()
            if line.startswith("WORKERS"):
                break
        pids = [int(x) for x in line.split()[1:]]
        subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)  # 只砍父行程，模擬事故
        time.sleep(6)
        return pids, [w for w in pids if _alive(w)]
    finally:
        script.unlink(missing_ok=True)


def test_workers_exit_when_parent_killed() -> None:
    pids, left = _run(guard=True)
    assert pids, "沒拿到 worker PID"
    assert not left, f"裝了 watchdog，父行程被砍 6 秒後仍有 worker 存活：{left}"
    print(f"PASS 裝 watchdog：父行程被硬砍後 {len(pids)} 個 worker 全部自我結束")


def test_control_without_guard_leaves_orphans() -> None:
    pids, left = _run(guard=False)
    try:
        assert left, "對照組沒有留下孤兒——測試無法證明 watchdog 有作用"
        print(f"PASS 對照組（不裝 watchdog）：{len(left)}/{len(pids)} 個 worker 成為孤兒（測試確實抓得到事故形狀）")
        import mem_guard
        found = {o["pid"] for o in mem_guard.find_orphan_python_workers()}
        assert set(left) <= found, f"mem_guard.find_orphan_python_workers() 漏抓：{set(left) - found}"
        print(f"PASS mem_guard 孤兒偵測抓到對照組全部 {len(left)} 支孤兒（只列出、未結束）")
    finally:
        for w in left:
            subprocess.run(["taskkill", "/PID", str(w), "/F"], capture_output=True)


if __name__ == "__main__":
    if sys.platform != "win32":
        print("SKIP：只在 Windows 驗")
        sys.exit(0)
    test_workers_exit_when_parent_killed()
    test_control_without_guard_leaves_orphans()
