"""research/mem_guard.py — 全市場/全歷史批次腳本的記憶體安全閥
（2026-09-20總司令裁示【記憶體事故記錄不精確，查證後重寫；安全閥可能
根本沒實作】三，事件001的補正實作）。

**誠實背景（這段本身就是記錄的一部分，不是裝飾）**：`research/
INCIDENTS.md`事件001與commit`75b54f06`原本聲稱「另掛一個系統可用
記憶體<3GB就自動kill行程的安全閥」，總司令查證後指出`research/`與
`scripts/`底下完全找不到任何`psutil`/記憶體量測程式碼——**這個查證
是對的，那次的「安全閥」只是一次性的bash背景迴圈（呼叫`powershell
-Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"`
輪詢），從來沒有寫進repo成為可重用的程式碼**，只在那一次互動session
裡存在過，事後任何人（包含下一次跑同一支腳本的自走行程）都不會受它
保護。這是「聲稱做了但沒做」，已在`INCIDENTS.md`更正記錄。這支模組
是補上真正的、可被任何腳本`import`重用的實作。

**設計**：背景執行緒每隔固定秒數（不可執行期間調整）讀一次系統可用
實體記憶體，低於固定門檻（不可執行期間調整）就呼叫`os._exit(1)`
立即終止本行程——選`os._exit`而非`sys.exit`／拋例外，是因為記憶體
真的耗盡時，行程可能連走完`except`/`finally`清理都做不到，與其
冒險讓「優雅關閉」卡死整台機器，不如硬終止換取機器活下來；呼叫端
也無法用`try/except`吃掉這個終止意圖（`os._exit`不會觸發Python的
例外處理機制）。

**跨平台安全**：這個專案目前只在Windows機器上跑批次腳本，用
`ctypes`直接呼叫Windows API `GlobalMemoryStatusEx`（不需要`psutil`
這個外部依賴，減少一個環境安裝步驟）。若未來在非Windows環境
`import`到這支模組（例如`.github/scripts/`的GitHub Actions Linux
runner），`install()`會偵測平台不支援，印一行警告後直接不啟動監控
（fail open，不讓「監控工具本身裝不上」拖垮被監控的腳本——跟
`CLAUDE.md`「監控工具自己的失敗只能降級成警告」同一條紀律）。

用法：
    import mem_guard
    mem_guard.install()   # 批次腳本最前面呼叫一次，之後全程監控直到行程結束
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time

# 門檻與檢查頻率：事前寫死，不得執行期間調整（總司令裁示明文要求）。
# 3GB沿用事件001當時互動視窗CC手動設定的門檻（判斷依據：Windows本身
# 加上一般背景服務通常需要2~3GB才能維持系統穩定運作，留3GB緩衝區）。
MIN_FREE_BYTES = 3 * 1024 ** 3
CHECK_INTERVAL_SECONDS = 10
# 2026-10-11 先.七十-4：開跑前門檻（大型回測啟動前的「可用記憶體」下限）。量的是 Windows 的 Available
# （GlobalMemoryStatusEx.ullAvailPhys＝工作管理員「可用」，含可回收的待命快取），不是 Free（純空閒頁）。
# 執行中終止門檻 MIN_FREE_BYTES 仍為 3GB 不變（事件001 裁示寫死，不得執行期間調整）。
START_MIN_AVAILABLE_BYTES = int(4.5 * 1024 ** 3)

_installed = False
_thread: threading.Thread | None = None
_stop_event = threading.Event()


class _MEMORYSTATUSEX_Windows:
    """延遲定義：只在Windows平台且真的呼叫`get_available_bytes()`時
    才建立ctypes結構，避免非Windows平台import本檔案時就出錯。"""

    def __init__(self):
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        self._ctypes = ctypes
        self._struct_cls = MEMORYSTATUSEX

    def available_bytes(self) -> int:
        stat = self._struct_cls()
        stat.dwLength = self._ctypes.sizeof(self._struct_cls)
        ok = self._ctypes.windll.kernel32.GlobalMemoryStatusEx(  # type: ignore[attr-defined]
            self._ctypes.byref(stat)
        )
        if not ok:
            raise OSError("GlobalMemoryStatusEx 呼叫失敗")
        return stat.ullAvailPhys


def _read_proc_meminfo_available_bytes() -> int:
    """Linux後備路徑（本專案目前用不到，但避免未來在Actions runner上
    import這支模組時直接爆炸）：讀`/proc/meminfo`的`MemAvailable`。"""
    with open("/proc/meminfo", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                return kb * 1024
    raise OSError("/proc/meminfo 找不到 MemAvailable 欄位")


def is_supported_platform() -> bool:
    return platform.system() == "Windows" or os.path.exists("/proc/meminfo")


def get_available_bytes() -> int:
    """回傳目前系統可用實體記憶體（bytes）。平台不支援時拋
    `NotImplementedError`——呼叫端（`install()`）會接住並fail open，
    這支函式本身不吞例外，讓單元測試/除錯時看得到真正的失敗原因。"""
    if platform.system() == "Windows":
        return _MEMORYSTATUSEX_Windows().available_bytes()
    if os.path.exists("/proc/meminfo"):
        return _read_proc_meminfo_available_bytes()
    raise NotImplementedError(f"mem_guard不支援目前平台：{platform.system()}")


def _watch_loop() -> None:
    while not _stop_event.is_set():
        try:
            free = get_available_bytes()
        except Exception as e:  # noqa: BLE001 -- 量測本身失敗只能降級成警告，不能讓監控迴圈自己掛掉去拖累被監控的腳本
            print(f"mem_guard: 記憶體量測失敗（{type(e).__name__}: {e}），"
                  f"本輪跳過，{CHECK_INTERVAL_SECONDS}秒後重試", file=sys.stderr, flush=True)
            _stop_event.wait(CHECK_INTERVAL_SECONDS)
            continue
        if free < MIN_FREE_BYTES:
            print(f"mem_guard: 系統可用記憶體 {free / 1024**3:.2f}GB 低於門檻 "
                  f"{MIN_FREE_BYTES / 1024**3:.0f}GB，立即終止本行程（PID {os.getpid()}）"
                  f"以保護機器其餘用途。", file=sys.stderr, flush=True)
            os._exit(1)
        _stop_event.wait(CHECK_INTERVAL_SECONDS)


def install() -> bool:
    """啟動背景監控執行緒。回傳是否真的啟動了（平台不支援時回False，
    印一行警告，不拋例外——呼叫端不需要包try/except）。重複呼叫安全
    （不會啟動第二條執行緒）。"""
    global _installed, _thread
    if _installed:
        return True
    if not is_supported_platform():
        print(f"mem_guard: 目前平台（{platform.system()}）不支援記憶體監控，"
              f"本次執行不受保護。", file=sys.stderr, flush=True)
        return False
    _stop_event.clear()
    _thread = threading.Thread(target=_watch_loop, daemon=True, name="mem_guard")
    _thread.start()
    _installed = True
    return True


def preflight(min_bytes: int = START_MIN_AVAILABLE_BYTES) -> tuple[bool, float, str]:
    """先.七十-4：大型回測開跑前檢查可用記憶體（Available）。回傳 (是否足夠, 目前 GB, 說明)。
    量測失敗或平台不支援 → 回 (True, nan, 說明)：開跑前檢查本身失敗只降級，執行中仍有 install() 的安全閥兜底。"""
    try:
        avail = get_available_bytes()
    except Exception as e:  # noqa: BLE001
        return True, float("nan"), f"可用記憶體量測失敗（{type(e).__name__}），略過開跑前檢查，執行中仍受 3GB 安全閥保護"
    gb = avail / 1024 ** 3
    need = min_bytes / 1024 ** 3
    if avail < min_bytes:
        return False, gb, f"可用記憶體 {gb:.2f}GB 低於開跑門檻 {need:.1f}GB，不開跑"
    return True, gb, f"可用記憶體 {gb:.2f}GB ≥ 開跑門檻 {need:.1f}GB"


def find_orphan_python_workers() -> list[dict]:
    """先.七十一-2：列出「父行程已不存在」的 python multiprocessing 工作行程（只列出，不結束）。

    判定：程序名 python*.exe、命令列含 multiprocessing 的 spawn_main(parent_pid=N)／--multiprocessing-fork，
    且 N 這個父行程已不存在（mp_guard._pid_alive）。2026-10-05 事故的 6 支孤兒正是這個形狀。
    只支援 Windows（PowerShell Get-CimInstance）；其他平台回空清單。量測失敗拋例外，由呼叫端降級。"""
    if platform.system() != "Windows":
        return []
    import json as _json
    import re as _re
    import subprocess as _sp
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'spawn_main|multiprocessing-fork' } | "
          "Select-Object ProcessId,ParentProcessId,CommandLine,PrivatePageCount,@{n='Start';e={$_.CreationDate.ToString('yyyy-MM-ddTHH:mm:ss')}} | ConvertTo-Json -Compress")
    out = _sp.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout.strip()
    rows = _json.loads(out) if out else []
    if isinstance(rows, dict):
        rows = [rows]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mp_guard
    found = []
    for r in rows:
        m = _re.search(r"parent_pid=(\d+)", r.get("CommandLine") or "")
        ppid = int(m.group(1)) if m else int(r.get("ParentProcessId") or 0)
        if not mp_guard._pid_alive(ppid):
            found.append({"pid": r["ProcessId"], "parent_pid": ppid, "started": r.get("Start"),
                          "private_mb": round((r.get("PrivatePageCount") or 0) / 1024 ** 2)})
    return found


def uninstall() -> None:
    """停止背景監控（主要給測試用）。"""
    global _installed
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=CHECK_INTERVAL_SECONDS + 5)
    _installed = False


if __name__ == "__main__":
    print(f"平台：{platform.system()}，支援：{is_supported_platform()}")
    if is_supported_platform():
        avail = get_available_bytes()
        print(f"目前系統可用記憶體（Available）：{avail / 1024**3:.2f}GB"
              f"（執行中終止門檻 {MIN_FREE_BYTES / 1024**3:.0f}GB，"
              f"{'低於門檻，會被終止' if avail < MIN_FREE_BYTES else '正常'}；"
              f"大型回測開跑門檻 {START_MIN_AVAILABLE_BYTES / 1024**3:.1f}GB）")
