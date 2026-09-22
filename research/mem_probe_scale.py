"""稽核.六(b)：修 T86 快取後，在同一 process 內以 25 檔一批連續載入至 150 檔，觀察 private memory 實測斜率（不外推）。"""
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()
import sys, io, contextlib, gc, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
def working_mb():
    c = PMC(); c.cb = ctypes.sizeof(c); _ps.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 1e6
import factor_ic as F
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
print("universe ids", len(ids))
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
base = private_mb(); print("baseline", round(base)); keep = {}; out = []
for s in range(0, min(N, len(ids)), 25):
    t = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        keep.update(F.load_sample_with_factors(ids[s:s+25], mk))
    gc.collect(); p = private_mb()
    out.append({"names_requested": min(s+25, len(ids)), "usable": len(keep), "private_mb": round(p), "working_set_mb": round(working_mb()), "sec": round(time.time()-t)})
    print(out[-1], flush=True)
json.dump({"baseline": base, "steps": out}, open("mem_probe_scale.json", "w"))
