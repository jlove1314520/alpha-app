"""先.一一三-B1 V2：月轉效應跨市場單發（S&P 500 1990～2024＋TAIEX 1990～2009）。

事前登記：`docs/PREREG_DRAFT_VAR1018_V2_turn_of_month_spx_taiex1990.md`（2026-10-18 總司令【先.一一三】B 放行）。
**只跑一次**：結果檔 `research/data/var1018_v2_result.json` 已存在就拒絕重跑。不讀 2025 年以後（holdout）。

規則（照 PREREG，參數寫死）：
- 窗口＝實際交易日序列的「當月最後一個交易日＋次月前 3 個交易日」（沿用原試驗 `turn_of_month_gate.label_turn_of_month`，N＝3）。
- 每個市場：窗口內日均報酬 − 窗口外日均報酬（diff）；控制組＝打散窗口布林標籤 N＝200（沿用 `_shuffle_percentile`，單邊）。
- PASS（兩個市場都要）：diff > 0、洗牌百分位 ≥ 90、對半切兩半 diff 都 > 0；另天條一：窗口策略任一段回撤 >50% → VIOLATES_SURVIVAL。
- 成本只用在「只在窗口內持有」策略的報告：台股 costs.round_trip_cost_pct(instrument_type="etf")、美股 us_costs.round_trip_cost_pct，每個窗口一次來回，1×／2×／3×。
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd

from turn_of_month_gate import label_turn_of_month, _shuffle_percentile, _real_diff
from validation import costs, us_costs, holdout

D = Path(__file__).parent / "data"
OUT = D / "var1018_v2_result.json"
N_AFTER = 3
N_SHUFFLE = 200
SEED = 20261018
SEGMENTS = {
    "SPX": [("全期", "1990-01-01", "2024-12-31"), ("2000～2002 空頭", "2000-03-24", "2002-10-09"), ("2008 空頭", "2007-10-09", "2009-03-09")],
    "TAIEX": [("全期", "1990-01-01", "2009-12-31"), ("1990 崩盤", "1990-02-12", "1990-10-12"), ("2000～2001 空頭", "2000-02-18", "2001-10-03"), ("2008 空頭", "2007-10-30", "2008-11-21")],
}
HALVES = {"SPX": ("2007-12-31",), "TAIEX": ("1999-12-31",)}


def load_spx() -> pd.DataFrame:
    d = pd.read_parquet(D / "raw_yf" / "INDEX_GSPC__1990-01-01__2024-12-31.parquet")[["date", "close"]]
    d["date"] = pd.to_datetime(d["date"])
    return d


def load_taiex() -> pd.DataFrame:
    a = pd.DataFrame(json.loads((D / "raw" / "fmtqik_taiex_1990_2003.json").read_text(encoding="utf-8")))
    a["date"] = pd.to_datetime(a["date"])
    rows = []
    for f in sorted(glob.glob(str(D / "taiex_open_hist" / "*.json"))):
        j = json.loads(Path(f).read_text(encoding="utf-8"))
        for r in j.get("data") or []:
            y, m, dd = [int(x) for x in re.findall(r"\d+", r[0])]
            rows.append({"date": pd.Timestamp(y + 1911, m, dd), "close": float(str(r[4]).replace(",", ""))})
    b = pd.DataFrame(rows)
    ov = a.merge(b, on="date", suffixes=("_a", "_b"))
    max_gap = float((ov["close_a"] - ov["close_b"]).abs().max()) if len(ov) else None
    d = pd.concat([a[a["date"] < b["date"].min()], b]).drop_duplicates("date").sort_values("date")
    d = d[d["date"] <= "2009-12-31"].reset_index(drop=True)
    return d, {"overlap_days": int(len(ov)), "overlap_max_abs_close_gap": max_gap}


def mdd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min() * 100)


def evaluate(name: str, px: pd.DataFrame, rt_cost_1x: float) -> dict:
    px = px.sort_values("date").reset_index(drop=True)
    assert px["date"].max() <= pd.Timestamp(holdout.VAL_END), "讀到 holdout"
    px["ret"] = px["close"].pct_change()
    df = px.dropna(subset=["ret"]).reset_index(drop=True)
    win = label_turn_of_month(df["date"], N_AFTER)
    ret = df["ret"].to_numpy()
    shuf = _shuffle_percentile(ret, win, N_SHUFFLE, SEED)
    cut = pd.Timestamp(HALVES[name][0])
    halves = []
    for m in (df["date"] <= cut, df["date"] > cut):
        halves.append(_real_diff(ret[m.to_numpy()], win[m.to_numpy()]))
    # 只在窗口內持有：窗口第一天收益前一日收盤進場、窗口最後一天收盤出場，每個窗口一次來回
    starts = np.where(win & ~np.r_[False, win[:-1]])[0]
    strat = {}
    for k in (1, 2, 3):
        r = np.where(win, ret, 0.0).copy()
        r[starts] -= rt_cost_1x * k
        eq = pd.Series(np.cumprod(1 + r), index=df["date"])
        yrs = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
        strat[f"{k}x"] = {"cagr_pct": round(float(eq.iloc[-1] ** (1 / yrs) - 1) * 100, 3), "final": round(float(eq.iloc[-1]), 4)}
    eq1 = pd.Series(np.cumprod(1 + np.where(win, ret, 0.0) - np.isin(np.arange(len(ret)), starts) * rt_cost_1x), index=df["date"])
    bh = pd.Series(np.cumprod(1 + ret), index=df["date"])
    yrs = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    segs = []
    for lab, a, b in SEGMENTS[name]:
        m = (eq1.index >= a) & (eq1.index <= b)
        segs.append({"segment": lab, "start": a, "end": b, "window_strategy_mdd_pct": round(mdd(eq1[m]), 2), "buy_hold_mdd_pct": round(mdd(bh[m]), 2)})
    return {"market": name, "n_days": int(len(df)), "n_window_days": int(win.sum()), "n_windows": int(len(starts)),
            "start": str(df["date"].iloc[0].date()), "end": str(df["date"].iloc[-1].date()),
            "mean_in": float(ret[win].mean()), "mean_out": float(ret[~win].mean()), "diff": shuf["real_diff"],
            "null_median": shuf["null_median"], "null_p90": shuf["null_p90"], "null_percentile": shuf["percentile"],
            "half_split_at": str(cut.date()), "half_diffs": halves, "round_trip_cost_1x": rt_cost_1x,
            "window_strategy": strat, "buy_hold_cagr_pct": round(float(bh.iloc[-1] ** (1 / yrs) - 1) * 100, 3), "survival_segments": segs}


def main() -> int:
    if OUT.exists():
        print(f"結果檔 {OUT.name} 已存在：只跑一次，拒絕重跑")
        return 1
    spx = load_spx()
    tw, ov = load_taiex()
    spx_cost = us_costs.round_trip_cost_pct(price=float(spx["close"].median()), shares=100.0)
    tw_cost = costs.round_trip_cost_pct(instrument_type="etf")
    res = {"SPX": evaluate("SPX", spx, spx_cost), "TAIEX": evaluate("TAIEX", tw, tw_cost)}
    res["TAIEX"]["source_overlap_check"] = ov
    checks = {}
    for k, r in res.items():
        checks[k] = {"diff_pos": r["diff"] > 0, "null_ge_90": r["null_percentile"] >= 90.0, "halves_pos": all(h > 0 for h in r["half_diffs"]),
                     "survival_ok": all(s["window_strategy_mdd_pct"] > -50 for s in r["survival_segments"])}
    survival = all(c["survival_ok"] for c in checks.values())
    passed = all(c["diff_pos"] and c["null_ge_90"] and c["halves_pos"] for c in checks.values())
    verdict = "VIOLATES_SURVIVAL" if not survival else ("PASS" if passed else "FAIL")
    out = {"prereg": "docs/PREREG_DRAFT_VAR1018_V2_turn_of_month_spx_taiex1990.md", "verdict": verdict, "checks": checks, "results": res,
           "params": {"n_after": N_AFTER, "n_shuffle": N_SHUFFLE, "seed": SEED}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    for k, r in res.items():
        print(f"{k} {r['start']}～{r['end']}：diff={r['diff']:+.5f}（窗口內 {r['mean_in']:+.5f}／外 {r['mean_out']:+.5f}），"
              f"洗牌百分位 {r['null_percentile']:.1f}，兩半 {[round(h, 5) for h in r['half_diffs']]}，窗口策略 1× CAGR {r['window_strategy']['1x']['cagr_pct']}%")
    print("判定：", verdict, json.dumps(checks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
