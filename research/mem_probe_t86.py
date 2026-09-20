"""稽核.六(b)：量測 twse_t86_client._load_all_t86_grouped 的峰值與穩態記憶體（只讀T86快取）。"""
import sys, gc
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import pandas as pd, twse_t86_client as t
print("baseline", round(private_mb()))
g = t._load_all_t86_grouped()
gc.collect()
print("after load (steady)", round(private_mb()), "MB; stocks", len(g))
rows = sum(len(v) for v in g.values())
mem = sum(v.memory_usage(deep=True).sum() for v in g.values())/1e6
print("rows", rows, "grouped deep MB", round(mem))
v = next(iter(g.values())); print(v.dtypes.to_dict())
