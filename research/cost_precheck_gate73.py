"""#73 第0關成本前置估算（HYPOTHESIS_QUEUE GATE_SEQUENCE 第0關）。
只用「實際選到的產業→成分股權重」算換手，不看任何報酬、無績效判定、不登記TRIALS。
換手＝相鄰兩個再平衡日目標權重的單邊變動量（等權重產業、產業內等權重，靜態2026成分股）。
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sector_rotation_accel_gate73_sanity as S  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "cost_precheck_gate73.json"


def main() -> int:
    wide = pd.read_parquet(S.ALL)
    assert wide.index.max() <= S.VAL_END
    acc = S.accel_frame(wide)
    comp = json.loads(S.COMPANY_INFO.read_text(encoding="utf-8"))["companies"]
    members: dict[str, list[str]] = {}
    for sid, rec in comp.items():
        ind = (rec or {}).get("industry")
        if ind:
            members.setdefault(ind, []).append(sid)
    prev: dict[str, float] = {}
    turn, dates = [], []
    for reb, sig in S.month_first_signal_dates(wide.index):
        if sig not in acc.index:
            continue
        top = S.pick_top(acc.loc[sig])
        top = {s for s in top if members.get(s)}
        if not top:
            continue
        w: dict[str, float] = {}
        for s in top:
            for st in members[s]:
                w[st] = w.get(st, 0.0) + 1.0 / (len(top) * len(members[s]))
        keys = set(w) | set(prev)
        one_way = 0.5 * sum(abs(w.get(k, 0.0) - prev.get(k, 0.0)) for k in keys)
        if prev:  # 首月建倉不計入穩態換手
            turn.append(one_way)
            dates.append(reb)
        prev = w
    t = np.array(turn)
    years = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    n_per_year = len(t) / years
    tbl = json.loads((HERE / "breakeven_alpha_table.json").read_text(encoding="utf-8"))
    t20 = next(h for h in tbl["holding_periods"] if h["window"] == "t20")
    res = {"note": "第0關成本前置；無績效判定、未登記TRIALS", "rebalances": int(len(t)),
           "years": round(years, 2), "rebalances_per_year": round(n_per_year, 2),
           "one_way_turnover_mean": round(float(t.mean()), 4),
           "one_way_turnover_median": round(float(np.median(t)), 4),
           "one_way_turnover_p10_p90": [round(float(np.percentile(t, 10)), 4), round(float(np.percentile(t, 90)), 4)],
           "table_t20_trades_per_year": t20["trades_per_year"], "scenarios": []}
    for sc in t20["scenarios"]:
        rt = sc["roundtrip_cost_pct_with_slippage"] / 100.0  # 買+賣一趟完整成本
        # 每次再平衡：賣出比例=買進比例=T，付一趟成本×T；一年 n 次，幾何複利
        annual_drag = 1 - (1 - t.mean() * rt) ** n_per_year
        res["scenarios"].append({"commission_discount": sc["commission_discount"],
                                 "roundtrip_cost_pct": sc["roundtrip_cost_pct_with_slippage"],
                                 "annual_cost_drag_pct_actual_turnover": round(annual_drag * 100, 3),
                                 "table_t20_breakeven_geometric_pct(全換倉假設)": sc["breakeven_annual_alpha_pct_geometric"]})
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
