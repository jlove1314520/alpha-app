"""#75續8：yfinance補價後的買方月覆蓋率（買入月須落在該ticker價格first~last區間內）。零外部請求、不讀報酬。"""
import json, sys
from pathlib import Path
import pandas as pd
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
H = Path(__file__).parent
st = json.loads((H/"insider_dera_price_fetch_status.json").read_text(encoding="utf-8"))["tickers"]
df = pd.read_csv(H/"data/dera_insider/issuer_month_net.csv", dtype={"issuer_cik": str})
df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
b = df[df["buy_usd"] > 0].copy()
b["fm"] = pd.to_datetime(b["month"]+"-01")
ok = {t: v for t, v in st.items() if v["status"] == "ok"}
b["processed"] = b["ticker"].isin(st)
b["has_px"] = b["ticker"].isin(ok)
first = b["ticker"].map(lambda t: ok.get(t, {}).get("first"))
last = b["ticker"].map(lambda t: ok.get(t, {}).get("last"))
first = pd.to_datetime(first); last = pd.to_datetime(last)
b["in_range"] = b["has_px"] & (b["fm"] >= first.dt.to_period("M").dt.to_timestamp()) & (b["fm"] <= last)
pm = b[b["in_range"]].groupby("month").size()
res = {"tickers_processed": len(st), "tickers_ok": len(ok),
       "buy_issuer_months": len(b), "processed_pct": round(float(b["processed"].mean()),4),
       "has_px_pct": round(float(b["has_px"].mean()),4), "in_range_pct": round(float(b["in_range"].mean()),4),
       "in_range_buyers_per_month": {"median": float(pm.median()), "min": int(pm.min()), "max": int(pm.max())},
       "by_year_in_range_pct": {y: round(float(g["in_range"].mean()),3) for y, g in b.groupby(b["month"].str[:4])}}
(H/"insider_dera_price_coverage2_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
