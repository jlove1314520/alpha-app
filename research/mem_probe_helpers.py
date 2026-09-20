"""稽核.六(b)前置：逐個 factors.py 的 per-stock helper 量測第一次呼叫的 private memory 增量，
定位 prepare_factors 3.4GB 固定成本的來源（只讀快取，不碰 holdout）。"""
import sys, io, contextlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import factor_ic as F, factors as FA, time
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED)
sid = ids[0]
print("stock", sid, "baseline", round(private_mb()))
names = ["_institutional_daily_net","_revenue_yoy_acceleration","_eps_yoy_growth","_eps_surprise_sue",
         "_revenue_surprise_sue","_roe_stability","_asset_growth","_accruals","_gross_margin_stability",
         "_gross_profitability","_dividend_yield_ttm_cash","_margin_utilization","_short_sale_utilization",
         "_short_margin_ratio"]
prev = private_mb()
for n in names:
    t = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        try: getattr(FA, n)(sid, F.START_DATE)
        except Exception as e: pass
    a = private_mb()
    print(f"{n:32s} +{a-prev:7.0f}MB  {time.time()-t:5.1f}s")
    prev = a
