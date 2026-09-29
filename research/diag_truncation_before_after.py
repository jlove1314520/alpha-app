# -*- coding: utf-8 -*-
"""評.B-2 二：64檔被上市日截斷股票，改前／改後截斷日對照＋4檔指名股票證據。
只讀既有價格快取（*__2024-12-31.parquet，VAL_END封頂），零API請求。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mem_guard; mem_guard.install()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
import universe as U
from build_otc_to_twse_dates import _cached_price

HERE = Path(__file__).parent
old_doc = json.loads((HERE / "data" / "diag_v8_yf_crosscheck.json").read_text(encoding="utf-8"))
ids = [r["stock_id"] for r in old_doc["truncation"]["all_truncated"]]
T = json.loads(U._TWSE_LISTING_PATH.read_text(encoding="utf-8"))["listing_dates"]
O = json.loads(U._OTC_LISTING_PATH.read_text(encoding="utf-8"))["listing_dates"]
fmt = lambda y: f"{y[:4]}-{y[4:6]}-{y[6:]}"
before = {}
for src in (T, O):                       # 改前：後讀的覆蓋（原邏輯）
    for s, y in src.items(): before[s] = fmt(y)
after = U.listing_date_lookup()
xfer = json.loads(U._OTC_TO_TWSE_PATH.read_text(encoding="utf-8"))["transfers"]

rows = []
for sid in ids:
    df = _cached_price(sid)
    ret = df["close"].where(df["close"] > 0).pct_change().replace([np.inf, -np.inf], np.nan)
    b, a = before.get(sid), after.get(sid)
    pre_b = df[df["date"] < b]; pre_a = df[df["date"] < a]
    pre_ret = ret[pre_b.index].abs()
    rows.append(dict(sid=sid, src="TWSE" if sid in T else "TPEx", 櫃轉市=sid in xfer,
        first=df["date"].iloc[0], cut_before=b, cut_after=a, changed=b != a,
        rows_cut_before=len(pre_b), rows_cut_after=len(pre_a),
        pre_zero_vol=round(float((pre_b["Trading_Volume"] == 0).mean()), 2) if len(pre_b) else None,
        pre_days_over_11pct=int((pre_ret > 0.11).sum())))
t = pd.DataFrame(rows).sort_values(["changed", "sid"], ascending=[False, True])
pd.set_option("display.width", 250)
print(t.to_string(index=False))
chg = t[t.changed]
print(f"\n改後截斷日有變動：{len(chg)}檔；列數 改前{int(t.rows_cut_before.sum())} → 改後{int(t.rows_cut_after.sum())}"
      f"（少砍{int(t.rows_cut_before.sum() - t.rows_cut_after.sum())}列）")
named = t[t.sid.isin(["4741", "6584", "8284", "6438"])]
print("\n指名4檔："); print(named.to_string(index=False))
out = {"n_stocks": len(t), "n_changed": int(len(chg)), "rows_cut_before": int(t.rows_cut_before.sum()),
       "rows_cut_after": int(t.rows_cut_after.sum()), "table": json.loads(t.to_json(orient="records", force_ascii=False))}
(HERE / "data" / "diag_truncation_before_after.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# 自我測試：櫃轉市3檔不再被砍上櫃期間；興櫃→上櫃/上市者維持截斷
r = t.set_index("sid")
assert r.loc["6438", "cut_after"] == "2013-11-25" and r.loc["6438", "rows_cut_after"] == 0
assert r.loc["8114", "rows_cut_after"] == 0 and r.loc["6183", "rows_cut_after"] == 0
for s in ("4741", "6584", "8284"):
    assert r.loc[s, "cut_after"] == r.loc[s, "cut_before"], s
print("[self-test] diag_truncation_before_after 通過")
