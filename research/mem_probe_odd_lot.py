"""稽核.六續三：量測 twse_odd_lot_client._load_all_odd_lot_grouped 與 ATOM_LIBRARY._BENCHMARK_CACHE 的
private memory增量（只讀本機快取，零API）。手法同mem_probe_t86.py。"""
"""稽核.六 (a)：以小樣本量測 factor_ic.load_sample_with_factors 的 private memory 成長。
只讀取快取/經 VAL_END 截斷路徑，不碰 holdout。用 ctypes 讀 Windows PrivateUsage。"""
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()
import ctypes, sys, json, io, contextlib
from ctypes import wintypes
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t)]

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ps = ctypes.WinDLL("psapi", use_last_error=True)
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
_ps.GetProcessMemoryInfo.restype = wintypes.BOOL



def private_mb():
    c = PMC(); c.cb = ctypes.sizeof(c)
    ok = _ps.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    assert ok, "GetProcessMemoryInfo 失敗"
    return c.PrivateUsage / 1e6


import gc
import pandas as pd
import twse_odd_lot_client as t
gc.collect(); b0 = private_mb(); print("baseline(import pandas+client)", round(b0), "MB", flush=True)
g = t._load_all_odd_lot_grouped()
gc.collect(); b1 = private_mb()
rows = sum(len(v) for v in g.values())
deep = sum(v.memory_usage(deep=True).sum() for v in g.values()) / 1e6
print(f"odd_lot after load: {round(b1)} MB (增量 {round(b1 - b0)} MB); stocks {len(g)} rows {rows} grouped deep {round(deep)} MB", flush=True)
try:
    import ATOM_LIBRARY as A
    gc.collect(); c0 = private_mb()
    for name, fn in (("0050", A._load_benchmark_0050), ("TAIEX", A._load_benchmark_taiex)):
        df = fn()
        print(f"ATOM_LIBRARY benchmark {name}: {len(df)}列 deep {round(df.memory_usage(deep=True).sum() / 1e6, 3)} MB", flush=True)
    gc.collect(); c1 = private_mb()
    print(f"import ATOM_LIBRARY＋載入兩條benchmark 增量 {round(c1 - c0)} MB（含import套件成本，上限）", flush=True)
except Exception as e:
    print("ATOM_LIBRARY量測失敗:", type(e).__name__, str(e)[:200], flush=True)
