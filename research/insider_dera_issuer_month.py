# -*- coding: utf-8 -*-
"""#75續6(b)：DERA P/S 交易 → 發行人×月 淨買入序列（地基工程，無績效判定）。
事前綁定規則（在看任何報酬之前寫死，不得依結果調整）：
 1. PIT：月份鍵一律用「申報日 filing_date」，不用交易日（交易日當下市場看不到）。
 2. 去重：同一經濟交易（owner_cik,trans_date,code,shares,price,acq_disp）若出現在
    不同 accession（原申報 vs 4/A 修正），只保留最早 filing_date 的那個 accession；
    同一 accession 內完全相同的列視為真實分批成交，全部保留。
 3. 剔除：price 缺失或<=0、名目>1e9（資料錯誤嫌疑，數量會記錄）。
 4. 每 issuer×月 輸出：buy_usd(P)、sell_usd(S)、net_usd、n_buyers(P 不重複 owner)、
    n_sellers、n_trades。之後(c)用 net_usd/n_buyers 作訊號，不在此步決定。
本腳本只讀既有 CSV、不碰價格/報酬、不碰 holdout、零外部請求。"""
import sys, json, glob
import pandas as pd
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = "data/dera_insider/"
frames = [pd.read_csv(f, dtype={"issuer_cik": str, "owner_cik": str, "accession": str}) for f in sorted(glob.glob(D + "20*q*.csv"))]
df = pd.concat(frames, ignore_index=True)
n0 = len(df)
df["fdate"] = pd.to_datetime(df["filing_date"], format="%d-%b-%Y", errors="coerce")
df["tdate"] = pd.to_datetime(df["trans_date"], format="%d-%b-%Y", errors="coerce")
bad_date = int(df["fdate"].isna().sum())
df = df[df["fdate"].notna()]
# 去重：跨 accession
key = ["owner_cik", "tdate", "code", "shares", "price", "acq_disp"]
first_acc = df.sort_values(["fdate", "accession"]).groupby(key, dropna=False)["accession"].transform("first").reindex(df.index)
dup_cross = int((df["accession"] != first_acc).sum())
df = df[df["accession"] == first_acc]
# 剔除
bad_price = int((df["price"].isna() | (df["price"] <= 0)).sum())
df = df[df["price"].notna() & (df["price"] > 0)]
df["usd"] = df["shares"].abs() * df["price"]
huge = int((df["usd"] > 1e9).sum())
df = df[df["usd"] <= 1e9]
df["month"] = df["fdate"].dt.to_period("M").astype(str)
df["is_buy"] = df["code"] == "P"
b = df[df["is_buy"]].groupby(["issuer_cik", "month"]).agg(buy_usd=("usd", "sum"), n_buyers=("owner_cik", "nunique"))
s = df[~df["is_buy"]].groupby(["issuer_cik", "month"]).agg(sell_usd=("usd", "sum"), n_sellers=("owner_cik", "nunique"))
t = df.groupby(["issuer_cik", "month"]).agg(n_trades=("usd", "size"), ticker=("ticker", "last"))
out = t.join(b, how="left").join(s, how="left")
for c in ["buy_usd", "sell_usd", "n_buyers", "n_sellers"]:
    out[c] = out[c].fillna(0)
out["net_usd"] = out["buy_usd"] - out["sell_usd"]
out = out.reset_index()
out.to_csv(D + "issuer_month_net.csv", index=False)
mo = out.groupby("month").agg(n_iss=("issuer_cik", "nunique"), n_buy_iss=("n_buyers", lambda x: int((x > 0).sum())))
res = {
    "rows_in": n0, "bad_filing_date": bad_date, "dropped_cross_accession_dup": dup_cross,
    "dropped_bad_price": bad_price, "dropped_notional_gt_1e9": huge, "rows_after": int(len(df)),
    "issuer_months": int(len(out)), "issuers": int(out["issuer_cik"].nunique()),
    "month_min": out["month"].min(), "month_max": out["month"].max(),
    "issuer_months_with_buy": int((out["n_buyers"] > 0).sum()),
    "median_active_issuers_per_month": float(mo["n_iss"].median()),
    "median_buying_issuers_per_month": float(mo["n_buy_iss"].median()),
    "min_buying_issuers_per_month": int(mo["n_buy_iss"].min()),
    "by_year_buying_issuers_mean": {y: round(float(g["n_buy_iss"].mean()), 1) for y, g in mo.reset_index().assign(y=lambda d: d["month"].str[:4]).groupby("y")},
}
json.dump(res, open("insider_dera_issuer_month_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
