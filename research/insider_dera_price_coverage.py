"""#75續7：DERA發行人×月序列 vs 既有FinMind USStockPrice快取的價格覆蓋率量測。
只讀 data/dera_insider/issuer_month_net.csv 與 data/raw/USStockPrice__*.parquet 檔名，
零外部請求、不讀任何報酬/價格內容（僅比對ticker是否有快取），不算IC、不做判定、不碰holdout。
輸出 insider_dera_price_coverage_result.json。
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw"
CSV = HERE / "data" / "dera_insider" / "issuer_month_net.csv"


def main():
    tickers = {f.split("__")[1].upper() for f in os.listdir(RAW) if f.startswith("USStockPrice__")}
    df = pd.read_csv(CSV, dtype={"issuer_cik": str})
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["cached"] = df["ticker"].isin(tickers)
    iss = df.drop_duplicates("issuer_cik")
    b = df[df["buy_usd"] > 0].copy()
    b["yr"] = b["month"].str[:4]
    per_month = b[b["cached"]].groupby("month").size()
    by_year = b.groupby("yr")["cached"].agg(["size", "sum"])
    res = {
        "cached_us_price_tickers": len(tickers),
        "issuers_total": int(len(iss)),
        "issuers_ticker_cached": int(iss["cached"].sum()),
        "buy_issuer_months": int(len(b)),
        "buy_issuer_months_cached": int(b["cached"].sum()),
        "buy_cached_pct": round(float(b["cached"].mean()), 4),
        "cached_buyers_per_month": {
            "median": float(per_month.median()),
            "min": int(per_month.min()),
            "max": int(per_month.max()),
        },
        "by_year": {y: {"buy_months": int(r["size"]), "cached": int(r["sum"])} for y, r in by_year.iterrows()},
    }
    (HERE / "insider_dera_price_coverage_result.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "by_year"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
