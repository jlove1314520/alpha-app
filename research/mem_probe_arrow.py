"""稽核.六(b)：驗證每檔常駐增量是否為 pyarrow memory pool 保留未還（release_unused 可否回收）。"""
import mem_guard  # 稽核.六續一（2026-09-20）：全市場/多檔全歷史載入的記憶體安全閥，可用記憶體<3GB即終止本行程（見mem_guard.py/INCIDENTS.md事件001）
mem_guard.install()
import sys, io, contextlib, gc
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import pyarrow as pa
import factor_ic as F
print("pool backend", pa.default_memory_pool().backend_name)
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
with contextlib.redirect_stdout(io.StringIO()):
    F.load_sample_with_factors(ids[:3], mk)
gc.collect(); base = private_mb(); print("warm baseline", round(base), "arrow allocated MB", round(pa.total_allocated_bytes()/1e6,1), "pool bytes", round(pa.default_memory_pool().bytes_allocated()/1e6,1), "max", round(pa.default_memory_pool().max_memory()/1e6))
with contextlib.redirect_stdout(io.StringIO()):
    data = F.load_sample_with_factors(ids[3:23], mk)
gc.collect(); b = private_mb()
print("after 20 names +%dMB; arrow allocated %.1fMB" % (b-base, pa.total_allocated_bytes()/1e6))
pa.default_memory_pool().release_unused(); gc.collect(); c = private_mb()
print("after release_unused +%dMB" % (c-base))
