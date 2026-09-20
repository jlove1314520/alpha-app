"""稽核.六續五：量測 OPENBLAS/OMP/MKL 執行緒數（預設/4/1）對「代表性負載」的 commit(PeakPagefileUsage)、
WorkingSet 峰值與 wall-clock 的影響。只量不改任何既有腳本/排程；只讀本機快取、不碰holdout、零API。
用法：python mem_blas_threads_bench.py            # 父行程：3種設定×3次，各開子行程，寫MEM_BLAS_THREADS.md
      python mem_blas_threads_bench.py --child   # 子行程：跑負載並印一行JSON
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if "--child" in sys.argv:
    import ctypes, json, time, io, contextlib
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t)]
    k32 = ctypes.WinDLL("kernel32"); ps = ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    t0 = time.time()
    import factor_ic as F
    ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)[:25]
    mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
    with contextlib.redirect_stdout(io.StringIO()):
        data = F.load_sample_with_factors(ids, mk)
    c = PMC(); c.cb = ctypes.sizeof(c); ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    print("RESULT " + json.dumps({"usable": len(data), "sec": round(time.time() - t0, 1),
          "peak_commit_mb": round(c.PeakPagefileUsage / 1e6), "peak_ws_mb": round(c.PeakWorkingSetSize / 1e6)}))
    sys.exit(0)

import os, subprocess, json, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent
CFG = [("預設(不設，24核)", None), ("4", "4"), ("1", "1")]
rows = []
for label, n in CFG:
    env = dict(os.environ)
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        env.pop(k, None)
        if n: env[k] = n
    res = []
    for i in range(3):
        p = subprocess.run([sys.executable, str(Path(__file__)), "--child"], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
        if not line:
            print(label, "第", i + 1, "次失敗", p.stderr[-300:]); continue
        res.append(json.loads(line[0][7:])); print(label, i + 1, res[-1], flush=True)
    if res:
        rows.append((label, len(res), [r["usable"] for r in res][0], statistics.median(r["sec"] for r in res),
                     statistics.median(r["peak_commit_mb"] for r in res), statistics.median(r["peak_ws_mb"] for r in res)))
base = rows[0][3] if rows else None
md = ["# 稽核.六續五：BLAS執行緒數對commit與速度的取捨（量測）", "",
      "腳本`mem_blas_threads_bench.py`；負載＝`factor_ic.load_sample_with_factors`25檔＋`prepare_market_data(TAIEX)`（含import factor_ic），",
      "每設定3次取中位數；子行程量`PeakPagefileUsage`（commit峰值）與`PeakWorkingSetSize`。只讀快取、不碰holdout、零API。", "",
      "| OPENBLAS/OMP/MKL_NUM_THREADS | 次數 | 可用檔數 | wall-clock中位數(秒) | 相對預設 | commit峰值中位數(MB) | WorkingSet峰值中位數(MB) |", "|---|---|---|---|---|---|---|"]
for label, n, u, sec, cm, ws in rows:
    md.append(f"| {label} | {n} | {u} | {sec} | {sec / base:+.0%}".replace("+", "") if False else f"| {label} | {n} | {u} | {sec} | {(sec / base - 1):+.0%} | {cm:.0f} | {ws:.0f} |")
(HERE / "MEM_BLAS_THREADS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md))
