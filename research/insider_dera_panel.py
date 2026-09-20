"""#75續13：建構真實面板（買入月×發行人的後20交易日報酬）＋套用G0-c悲觀填補，只印覆蓋與填補筆數，不算IC、不印任何報酬統計。
事前綁定：進場＝買入月最後一個交易日收盤；fwd20＝其後第20個交易日調整收盤/進場−1。
價格檔已於抓取時截斷在2025-01-01前（VAL_END），此處再截一次。fwd20需20日空間，故面板月份止於2024-11
（2024-12的fwd20會超出VAL_END，不可用；[自行裁量]，非依結果調整）。買入月＝該發行人該月buy_usd>0，樣本2018-01~2024-11。"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from insider_dera_g0c_fill import pessimistic_fill
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
H = Path(__file__).parent
VAL_END = pd.Timestamp("2024-12-31")
st = json.loads((H/"insider_dera_price_fetch_status.json").read_text(encoding="utf-8"))["tickers"]
df = pd.read_csv(H/"data/dera_insider/issuer_month_net.csv", dtype={"issuer_cik": str})
df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
last_filing = df.groupby("issuer_cik")["month"].max().to_dict()
b = df[(df["buy_usd"] > 0) & (df["month"] >= "2018-01") & (df["month"] <= "2024-11")][["month", "issuer_cik", "ticker"]].copy()
ok = {t for t, v in st.items() if v["status"] == "ok"}
cache = {}
def fwd(t, m):
    if t not in ok: return np.nan
    if t not in cache:
        p = pd.read_csv(H/"data/dera_insider/prices"/f"px_{t}.csv", parse_dates=["Date"])
        cache[t] = p[p["Date"] <= VAL_END].set_index("Date")["adj_close"]
    s = cache[t]
    me = pd.Period(m).end_time.normalize()
    hist = s[s.index <= me]
    if hist.empty or hist.index[-1] < me - pd.Timedelta(days=7): return np.nan   # 進場日須貼近月底（防ticker空窗）
    i = s.index.get_loc(hist.index[-1])
    return float(s.iloc[i+20]/s.iloc[i]-1) if i+20 < len(s) else np.nan
b["fwd20"] = [fwd(t, m) for t, m in zip(b["ticker"], b["month"])]
opt, pes, gap = pessimistic_fill(b, last_filing)
gap["priced_by_year"] = {y: int(g["fwd20"].notna().sum()) for y, g in b.groupby(b["month"].str[:4])}
gap["filled_share_of_pessimistic"] = round(gap["n_filled"]/max(len(pes),1), 4)
gap["min_months_priced_buyers"] = int(opt.groupby("month").size().min())
out = H/"data/dera_insider"
opt.to_csv(out/"panel_opt.csv", index=False); pes.to_csv(out/"panel_pes.csv", index=False)
(H/"insider_dera_panel_result.json").write_text(json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(gap, ensure_ascii=False))
