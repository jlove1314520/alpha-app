# -*- coding: utf-8 -*-
"""先.一五五-3：f_value_pe／pb 延長用 2025 起 PER 續抓（236 檔抽樣宇宙，依代號排序，已有快取者跳過）。
每次送請求前查 finmind_client.calls_last_hour()：未開抓前 >=300 就每分鐘再看一次；開抓後 >450 就停。
REAUDIT_DEADLINE（epoch 秒）到就停。請求一律走 finmind_client._fetch（共用節流與快取）。非投資建議。"""
import os, sys, time, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import finmind_client as f

dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1200))
data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
sids = sorted(data["data"].keys() if isinstance(data, dict) and "data" in data else data.keys())
raw = HERE / "data" / "raw"
todo = [s for s in sids if not (raw / f"TaiwanStockPER__{s}__2025-01-01__2026-09-30.parquet").exists()]
print(f"宇宙 {len(sids)} 檔，尚缺 {len(todo)} 檔", flush=True)
started = False
n = 0
for s in todo:
    while True:
        if time.time() > dl:
            print(f"時間到，斷點＝{s}，本次送 {n} 次", flush=True); sys.exit(0)
        u = f.calls_last_hour()
        if (not started and u < 300) or (started and u <= 450):
            break
        if started:
            print(f"用量 {u}>450 停，斷點＝{s}，本次送 {n} 次", flush=True); sys.exit(0)
        print(f"用量 {u}，等 60 秒", flush=True); time.sleep(60)
    started = True
    df = f._fetch("TaiwanStockPER", s, "2025-01-01", "2026-09-30")
    n += 1
    print(f"{s} {len(df)} 列", flush=True)
print(f"全部完成，本次送 {n} 次", flush=True)
