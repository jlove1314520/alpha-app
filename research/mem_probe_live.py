"""稽核.六(b)：tracemalloc 找出 load_sample_with_factors 呼叫後「仍存活」的配置，依 repo 內最內層呼叫行歸因。"""
import sys, io, contextlib, gc, tracemalloc, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import factor_ic as F
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
with contextlib.redirect_stdout(io.StringIO()):
    F.load_sample_with_factors(ids[:3], mk)
gc.collect()
tracemalloc.start(25)
s0 = tracemalloc.take_snapshot()
with contextlib.redirect_stdout(io.StringIO()):
    data = F.load_sample_with_factors(ids[3:23], mk)
gc.collect()
s1 = tracemalloc.take_snapshot()
agg = collections.Counter()
for st in s1.compare_to(s0, "traceback"):
    if st.size_diff <= 0: continue
    key = "(no repo frame)"
    for fr in st.traceback:            # 由外到內；取最內層屬於 research/ 的那一行
        if "\alpha-app\research\\" in fr.filename and "mem_probe" not in fr.filename:
            key = f"{fr.filename.split('research')[-1]}:{fr.lineno}"
    agg[key] += st.size_diff
tot = sum(agg.values())
print("traced live total MB", round(tot/1e6, 1))
for k, v in agg.most_common(8): print(round(v/1e6, 1), "MB", k)
