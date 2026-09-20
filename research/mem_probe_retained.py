"""稽核.六(b)：拆解 load_sample_with_factors 每檔的常駐記憶體是「回傳資料本身」還是「快取/碎片」。"""
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()
import sys, io, contextlib, gc
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import factor_ic as F, finmind_client as FC
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
with contextlib.redirect_stdout(io.StringIO()):
    F.load_sample_with_factors(ids[:3], mk)   # 暖機：吃掉一次性固定成本
gc.collect(); base = private_mb(); print("warm baseline", round(base))
with contextlib.redirect_stdout(io.StringIO()):
    data = F.load_sample_with_factors(ids[3:23], mk)
a = private_mb(); gc.collect(); b = private_mb()
deep = sum(d.memory_usage(deep=True).sum() for d in data.values())/1e6
print("20 names: private +%dMB (after gc +%dMB); returned data deep=%.0fMB, cols/frame=%d, usable=%d" % (a-base, b-base, deep, len(next(iter(data.values())).columns), len(data)))
import functools, gc as g
big = []
for o in g.get_objects():
    if hasattr(o, "cache_info") and hasattr(o, "cache_clear"):
        big.append((getattr(o,"__qualname__",str(o)), o.cache_info()))
print("lru_caches:", big)
for m in (FC,):
    for k,v in vars(m).items():
        if isinstance(v,(dict,list)) and len(v)>0 and k.startswith("_"): print("module cache", k, len(v))
