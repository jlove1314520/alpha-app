import sys, io, contextlib, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import factor_ic as F
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
mk = F.prepare_market_data(F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE))
out = []; prev = private_mb(); print("baseline", round(prev))
keep = {}
for i, sid in enumerate(ids[:8]):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            px = F.adjusted_price_series(sid, F.START_DATE)
        except Exception as e:
            px = None
    a = private_mb(); step1 = a - prev; prev = a
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            d = F.prepare_factors(sid, px, mk, F.START_DATE) if px is not None and len(px) >= 260 else None
        except Exception as e:
            d = None
    b = private_mb(); step2 = b - prev; prev = b
    keep[sid] = (px, d)
    out.append((i, sid, round(step1), round(step2)))
    print(i, sid, "price+%dMB" % step1, "factors+%dMB" % step2)
