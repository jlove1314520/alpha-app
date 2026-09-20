import sys, io, contextlib, tracemalloc
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import factor_ic as F
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
sid = ids[0]
px = F.adjusted_price_series(sid, F.START_DATE)
tracemalloc.start(6)
s0 = tracemalloc.take_snapshot()
with contextlib.redirect_stdout(io.StringIO()):
    d = F.prepare_factors(sid, px, mk, F.START_DATE)
s1 = tracemalloc.take_snapshot()
for st in s1.compare_to(s0, "traceback")[:3]:
    print(round(st.size_diff/1e6), "MB")
    for l in st.traceback.format()[-6:]: print("  ", l)
