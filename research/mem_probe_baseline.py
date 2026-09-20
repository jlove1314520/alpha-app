"""稽核.六續四：拆解 factor_ic 載入前基線（約1.7GB）——逐步量測各步驟的 private memory 增量。"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
steps = [("python+ctypes 起點", private_mb())]
def mark(name): steps.append((name, private_mb()))
import numpy, pandas; mark("import numpy+pandas")
import scipy.stats; mark("import scipy.stats")
import pyarrow; mark("import pyarrow")
import finmind_client; mark("import finmind_client")
import factor_ic as F; mark("import factor_ic（含其全部傳遞import）")
u = F.build_universe(); mark("build_universe()")
ids = F.sample_universe_ids(F.SAMPLE_SIZE, F.SAMPLE_SEED); mark("sample_universe_ids(300)")
raw = F.load_dev("TaiwanStockPrice", "TAIEX", F.START_DATE); mark("load_dev(TAIEX)")
mk = F.prepare_market_data(raw); mark("prepare_market_data(TAIEX)")
prev = 0
for n, v in steps:
    print(f"{n:42s} {v:7.0f}MB  (+{v-prev:6.0f})"); prev = v
