# -*- coding: utf-8 -*-
"""先.一五〇-2 元件合理性檢查（描述性，零請求）：恐慌日是否落在已知股災、各門檻事件數、PQ 名單每季檔數。
輸出 research/data/panic_pq/sanity.json；不做任何報酬計算。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "panic_pq"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KNOWN = ["2008-10-24", "2011-08-09", "2015-08-24", "2018-10-11", "2020-03-19", "2021-05-12", "2022-10-25", "2024-08-05"]
TIERS = {
    "strict": dict(gm=2, om=2, rev=0.25, eps=0.30, ttm=10),
    "mid": dict(gm=1, om=1, rev=0.15, eps=0.20, ttm=5),
    "loose": dict(gm=0, om=0, rev=0.0, eps=0.0, ttm=0),
}


def events(pan: pd.DataFrame, theta: float, gap: int = 20) -> list[str]:
    hit = pan.index[pan["frac_limit_down"] >= theta].tolist()
    out, last = [], -10**9
    for i in hit:
        if i - last > gap:
            out.append(pan.at[i, "date"])
        last = i
    return out


def main() -> int:
    pan = pd.read_csv(OUT / "panic_daily.csv").reset_index(drop=True)
    pq = pd.read_csv(OUT / "pq_snapshots.csv", dtype={"stock_id": str})
    res = {"panic_days": int(len(pan)), "date_range": [pan["date"].min(), pan["date"].max()]}
    res["top20_frac_limit_down"] = pan.nlargest(20, "frac_limit_down")[["date", "n_limit_down", "n_traded", "frac_limit_down", "taiex_ret"]].round(4).to_dict("records")
    res["known_crash_days"] = pan[pan["date"].isin(KNOWN)][["date", "n_limit_down", "frac_limit_down", "taiex_ret"]].round(4).to_dict("records")
    res["events_by_theta"] = {str(t): events(pan, t) for t in (0.01, 0.02, 0.03, 0.05)}
    res["n_events_by_theta"] = {k: len(v) for k, v in res["events_by_theta"].items()}
    cnt = {}
    for name, t in TIERS.items():
        m = ((pq["gm_yoy_pp"] > t["gm"]) if t["gm"] == 0 else (pq["gm_yoy_pp"] >= t["gm"]))
        m &= (pq["om_yoy_pp"] > t["om"]) if t["om"] == 0 else (pq["om_yoy_pp"] >= t["om"])
        m &= (pq["rev3m_yoy"] > t["rev"]) if t["rev"] == 0 else (pq["rev3m_yoy"] >= t["rev"])
        m &= (pq["eps_yoy"] > t["eps"]) if t["eps"] == 0 else (pq["eps_yoy"] >= t["eps"])
        m &= (pq["eps_ttm"] > t["ttm"]) if t["ttm"] == 0 else (pq["eps_ttm"] >= t["ttm"])
        s = pq[m].groupby("quarter")["stock_id"].count()
        cnt[name] = {"quarters": int(len(s)), "median": float(s.median()) if len(s) else 0,
                     "min": int(s.min()) if len(s) else 0, "max": int(s.max()) if len(s) else 0,
                     "2024-06-30": int(s.get("2024-06-30", 0))}
        if name == "strict":
            res["strict_2024Q2_top10_by_om_yoy"] = pq[m & (pq["quarter"] == "2024-06-30")].nlargest(10, "om_yoy_pp")["stock_id"].tolist()
    res["pq_counts"] = cnt
    (OUT / "sanity.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "events_by_theta"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
