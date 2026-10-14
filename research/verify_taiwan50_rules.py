# -*- coding: utf-8 -*-
"""先.九十三-1b：照臺灣50官方編制規則（research/PIT_MKTCAP_RULES_FIX.md，重跑前已 commit）重建 0050，驗證量尺。

主判定事先寫死：**日頻 TE**（重建組合日報酬 − 0050 含息日報酬，年化 √252）。
  ≤1% 合格／1～3% 送審／>3% core_tilt 以「量尺無法重建 0050」結案。月頻 TE 只作參考。
做法：pit_mktcap_rank.taiwan50_schedule() 排出成分股異動（季審＋40/61 緩衝＋期中遞補＋快速納入）；
每次異動以 weight_day 收盤的總市值定權重（N1：流通係數無免費官方資料，照實用總市值），之後買進持有（含息）。
只讀本機快取、0 次網路請求、不讀 holdout。不登記試驗、不計 N。
輸出：research/data/taiwan50_rules_verify.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pit_mktcap_rank as pmr  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

OUT = HERE / "data" / "taiwan50_rules_verify.json"
START = "2013-06-01"
TSMC = "2330"


def main() -> int:
    etf = pmr.total_return_index("0050")
    days = [d for d in etf.index if START <= d <= VAL_END]
    sched = pmr.taiwan50_schedule(days)
    print(f"異動 {len(sched)} 次（季審 {sum('季審' in s['reason'] for s in sched)}、期中遞補 {sum('遞補' in s['reason'] for s in sched)}、"
          f"快速納入 {sum('快速' in s['reason'] for s in sched)}）", flush=True)
    wdays = sorted({s["weight_day"] for s in sched})
    cap = pmr.mktcap_panel(wdays).set_index(["date", "stock_id"])["mktcap"]
    tri = {}
    port = pd.Series(np.nan, index=pd.Index(days))
    no_px, tsmc_w = 0, []
    for k, s in enumerate(sched):
        seg_end = sched[k + 1]["effective"] if k + 1 < len(sched) else None
        seg = [d for d in days if d >= s["effective"] and (seg_end is None or d < seg_end)]
        if not seg:
            continue
        w = {m: float(cap.get((s["weight_day"], m), np.nan)) for m in s["members"]}
        w = {m: v for m, v in w.items() if v == v and v > 0}
        tot = sum(w.values())
        w = {m: v / tot for m, v in w.items()}
        if "季審" in s["reason"] or k == 0:
            tsmc_w.append((s["effective"], w.get(TSMC, 0.0)))
        base_day = s["weight_day"]
        val = pd.Series(0.0, index=[base_day] + seg)
        for m, wm in w.items():
            if m not in tri:
                tri[m] = pmr.total_return_index_patched(m)   # 先.九十四-1 F1：補官方 TWT49U 缺列的除權息
            p = tri[m].reindex([base_day] + seg).ffill(limit=5)
            if pd.isna(p.iloc[0]):
                no_px += 1
                continue
            val = val + wm * (p.ffill() / p.iloc[0])
        r = (val / val.shift(1)).iloc[1:] - 1
        port.loc[seg] = r.to_numpy()
    etf_ret = etf.reindex(days).pct_change()
    df = pd.DataFrame({"port": port, "etf": etf_ret}).dropna()
    diff = df["port"] - df["etf"]
    te = float(diff.std() * np.sqrt(252))
    corr = float(df["port"].corr(df["etf"]))
    mdf = (1 + df).groupby(pd.to_datetime(df.index).to_period("M")).prod() - 1
    te_m = float((mdf["port"] - mdf["etf"]).std() * np.sqrt(12))
    by_year = {}
    for y, g in df.groupby(pd.to_datetime(df.index).year):
        dd = g["port"] - g["etf"]
        by_year[int(y)] = {"te": round(float(dd.std() * np.sqrt(252)), 4), "corr": round(float(g["port"].corr(g["etf"])), 4),
                           "port_ret": round(float((1 + g["port"]).prod() - 1), 4), "etf_ret": round(float((1 + g["etf"]).prod() - 1), 4)}
    verdict = "PASS_合格" if te <= 0.01 else ("REVIEW_送審" if te <= 0.03 else "FAIL_量尺無法重建0050")
    res = {"generated_at": datetime.now().isoformat(timespec="seconds"), "task": "先.九十四-1c（先.九十三-1b＋F1 重跑）",
           "rules_doc": "research/PIT_MKTCAP_RULES_FIX.md", "period": [df.index[0], df.index[-1]], "n_days": len(df),
           "primary": {"metric": "日頻 TE（年化）", "te_daily": round(te, 4), "verdict": verdict,
                       "thresholds": "≤1% 合格／1～3% 送審／>3% 結案（事前寫死）"},
           "reference_only": {"te_monthly": round(te_m, 4), "corr_daily": round(corr, 4),
                              "previous_monthly_reconstitution_te_daily": 0.0446,
                              "previous_rules_run_te_daily_93_1b": 0.0446},
           "by_year": by_year,
           "n_changes": len(sched), "changes": [{k2: v for k2, v in s.items() if k2 != "members"} for s in sched],
           "tsmc_weight_at_reviews": {d: round(v, 4) for d, v in tsmc_w},
           "weight_starts_without_price": no_px,
           "not_implemented": ["N1 自由流通市值加權（無免費官方流通係數歷史）", "N2 最低流通量", "N3 流動性篩選", "N4 全額交割股排除"],
           "fix_list": "research/PIT_MKTCAP_RULES_FIX.md 先.九十四-1 F1",
           "requests_made": 0}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("period", "primary", "reference_only", "n_changes", "weight_starts_without_price")}, ensure_ascii=False, indent=1))
    print(json.dumps(by_year, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
