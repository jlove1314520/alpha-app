"""先.七十一-2（2026-10-11）：multiprocessing／ProcessPoolExecutor 工作行程的「父行程死亡偵測」。

事故：2026-10-05 01:16 馬拉松輪次跑 industry_shortage_backtest（ProcessPoolExecutor，6 個 worker，每個各載入約 1.9GB
面板）時，父行程被逾時砍掉（taskkill 未帶 /T），6 個 worker 卡在等工作的管線上永遠不結束，佔住約 11.4GB 認可記憶體
直到 10-11 才被人工清掉（先.七十一-1）。ProcessPoolExecutor 的 with 區塊只在父行程「正常」離開時收拾 worker；
父行程被硬砍時什麼都不會執行，所以要由 worker 自己發現父行程不見了。

用法：在 worker 的 initializer 第一行呼叫 `mp_guard.start_parent_watchdog()`。
它開一條背景執行緒，每 10 秒檢查一次父行程；父行程不在了就 `os._exit(3)` 自我結束。
檢查方式：優先用 `multiprocessing.parent_process().is_alive()`（spawn 模式下以父行程 sentinel 判斷，Windows 可靠）；
取不到時退回用父 PID 查（Windows 用 OpenProcess／GetExitCodeProcess，其他平台用 os.kill(pid, 0)）。
自身任何錯誤只印警告、不影響 worker 工作（十二節：守門員失敗只降級）。
"""
from __future__ import annotations

import os
import sys
import threading

CHECK_SECONDS = 10
_started = False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True  # 查不到就當還活著（保守，不誤殺）
            return code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def parent_alive(parent=None, ppid: int | None = None) -> bool:
    try:
        if parent is not None:
            return bool(parent.is_alive())
    except Exception:  # noqa: BLE001
        pass
    return _pid_alive(ppid if ppid is not None else os.getppid())


def start_parent_watchdog(check_seconds: float = CHECK_SECONDS, on_orphan=None) -> bool:
    """在 worker 內啟動父行程監看。重複呼叫只會啟動一次。回傳是否有啟動。"""
    global _started
    if _started:
        return True
    try:
        import multiprocessing as mp
        parent = mp.parent_process()
        ppid = parent.pid if parent is not None and parent.pid else os.getppid()

        def _loop():
            import time
            while True:
                time.sleep(check_seconds)
                if not parent_alive(parent, ppid):
                    msg = f"mp_guard: 父行程 {ppid} 已不存在，工作行程 {os.getpid()} 自我結束（避免成為孤兒佔記憶體）"
                    print(msg, file=sys.stderr, flush=True)
                    if on_orphan:
                        on_orphan()
                    else:
                        os._exit(3)
                    return

        threading.Thread(target=_loop, daemon=True, name="mp_guard_parent_watchdog").start()
        _started = True
        return True
    except Exception as e:  # noqa: BLE001
        print(f"mp_guard: 父行程監看啟動失敗（{type(e).__name__}），本 worker 不受保護", file=sys.stderr, flush=True)
        return False
