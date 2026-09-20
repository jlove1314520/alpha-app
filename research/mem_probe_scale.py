"""稽核.六(b)：修 T86 快取後，在同一 process 內以 25 檔一批連續載入至 150 檔，觀察 private memory 實測斜率（不外推）。"""
import sys, io, contextlib, gc, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
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
    out.append({"names_requested": min(s+25, len(ids)), "usable": len(keep), "private_mb": round(p), "sec": round(time.time()-t)})
    print(out[-1], flush=True)
json.dump({"baseline": base, "steps": out}, open("mem_probe_scale.json", "w"))
