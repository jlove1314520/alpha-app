# -*- coding: utf-8 -*-
"""先.一五五-3：籌碼類（f_inst_flow／f_foreign_streak／f_inst_streak_days／f_margin_utilization／f_short_margin_ratio）
延長用 2025 起法人買賣超＋融資融券續抓（236 檔抽樣宇宙，依資料集→代號排序，已有快取者跳過）。
同 fetch_per_2025_resume.py：未開抓前用量 >=300 就每分鐘再看；開抓後 >450 就停；
REAUDIT_DEADLINE（epoch 秒）到就停；本次最多 CHIP_MAX_CALLS 次（預設 150）。
請求一律走 finmind_client._fetch（共用節流與快取）。非投資建議。"""
import os, sys, time, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import finmind_client as f

START, END = "2025-01-01", "2026-09-30"
DATASETS = ["TaiwanStockInstitutionalInvestorsBuySell", "TaiwanStockMarginPurchaseShortSale"]
dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1200))
cap = int(os.environ.get("CHIP_MAX_CALLS", "150"))
data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
sids = sorted(data["data"].keys() if isinstance(data, dict) and "data" in data else data.keys())
raw = HERE / "data" / "raw"


def covered(ds, s):
    if (raw / f"{ds}__{s}__{START}__{END}.parquet").exists():
        return True
    # 既有快取結束日 >= 2026-09-24（延長期終點）且起始 <= 2025-01 也算已覆蓋
    for p in raw.glob(f"{ds}__{s}__*.parquet"):
        parts = p.stem.split("__")
        if len(parts) == 4 and parts[2] <= START and parts[3] >= "2026-09-24":
            return True
    return False


todo = [(ds, s) for ds in DATASETS for s in sids if not covered(ds, s)]
print(f"宇宙 {len(sids)} 檔，尚缺 {len(todo)} 個（資料集×代號）", flush=True)
started, n = False, 0
for ds, s in todo:
    if n >= cap:
        print(f"本次上限 {cap} 次到，斷點＝{ds} {s}", flush=True); sys.exit(0)
    while True:
        if time.time() > dl:
            print(f"時間到，斷點＝{ds} {s}，本次送 {n} 次", flush=True); sys.exit(0)
        u = f.calls_last_hour()
        if (not started and u < 300) or (started and u <= 450):
            break
        if started:
            print(f"用量 {u}>450 停，斷點＝{ds} {s}，本次送 {n} 次", flush=True); sys.exit(0)
        print(f"用量 {u}，等 60 秒", flush=True); time.sleep(60)
    started = True
    df = f._fetch(ds, s, START, END)
    n += 1
    print(f"{ds} {s} {len(df)} 列", flush=True)
print(f"全部完成，本次送 {n} 次", flush=True)
