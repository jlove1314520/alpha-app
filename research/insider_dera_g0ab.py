"""#75續11：2018+子樣本 G0-a/G0-b 覆蓋統計（依續10 SPEC事前綁定）。零外部請求、不讀報酬。
G0-a：2018~2024逐年「買入月落在價格區間內」覆蓋>=50%；G0-b：每月有價格買方家數>=100，剔除月數>10%即不過。"""
import json, sys
from pathlib import Path
import pandas as pd
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
H = Path(__file__).parent
st = json.loads((H/"insider_dera_price_fetch_status.json").read_text(encoding="utf-8"))["tickers"]
df = pd.read_csv(H/"data/dera_insider/issuer_month_net.csv", dtype={"issuer_cik": str})
df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
b = df[(df["buy_usd"] > 0) & (df["month"] >= "2018-01") & (df["month"] <= "2024-12")].copy()
b["fm"] = pd.to_datetime(b["month"]+"-01")
ok = {t: v for t, v in st.items() if v["status"] == "ok"}
first = pd.to_datetime(b["ticker"].map(lambda t: ok.get(t, {}).get("first")))
last = pd.to_datetime(b["ticker"].map(lambda t: ok.get(t, {}).get("last")))
b["in_range"] = b["ticker"].isin(ok) & (b["fm"] >= first.dt.to_period("M").dt.to_timestamp()) & (b["fm"] <= last)
yr = {y: round(float(g["in_range"].mean()), 4) for y, g in b.groupby(b["month"].str[:4])}
pm = b[b["in_range"]].groupby("month").size().reindex(sorted(b["month"].unique()), fill_value=0)
low = [m for m, n in pm.items() if n < 100]
res = {"months": len(pm), "G0a_by_year": yr, "G0a_pass": all(v >= 0.5 for v in yr.values()),
       "G0b_buyers_per_month": {"median": float(pm.median()), "min": int(pm.min()), "max": int(pm.max())},
       "G0b_months_below_100": low, "G0b_below_pct": round(len(low)/len(pm), 4),
       "G0b_pass": len(low)/len(pm) <= 0.10}
res["G0ab_pass"] = res["G0a_pass"] and res["G0b_pass"]
(H/"insider_dera_g0ab_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
