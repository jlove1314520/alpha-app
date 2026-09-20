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

import factor_ic as F
ids_all = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
market_raw = F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE)
market_df = F.prepare_market_data(market_raw)
base = private_mb()
print("baseline_mb", round(base, 1))
res = []
for n in (10, 20, 30):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        data = F.load_sample_with_factors(ids_all[:n], market_df)
    after = private_mb()
    rows = sum(len(d) for d in data.values())
    res.append({"requested": n, "usable": len(data), "rows": rows, "private_mb": round(after, 1),
                "delta_mb": round(after - base, 1)})
    print(res[-1])
    del data
# 線性外推（以 n=30 的 delta 為準，並以 20→30 的邊際成本作對照）
d30 = res[-1]["delta_mb"]; per = d30 / max(res[-1]["usable"], 1)
print("per_name_mb", round(per, 2), "extrapolated_300_mb", round(per * 300, 0))
json.dump({"baseline": base, "runs": res, "per_name_mb": per, "extrap_300_mb": per * 300},
          open("mem_probe_factor_ic.json", "w"))
