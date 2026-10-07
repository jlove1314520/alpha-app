# -*- coding: utf-8 -*-
"""先.四十七-一：S3-C6 危機閘門樣本外單發（2025-01-01～2026-09-30 保留資料，只此一次）。

定義全部事前綁定於 docs/PREREG_s3c6_oos_2025.md（登記 #427，SHA256 4ab1cb46…，commit 8e3238b6a），
母登記 #424 docs/PREREG_crisis_gate_leveraged_bb90.md（SHA256 76c3eea0…）。**只跑一次；結果檔已存在即拒絕重跑；
數字一律在 JSON 寫完後才印。** 本檔已由互動視窗列入 validation/holdout.py 的 ALLOWED_HOLDOUT_READERS（a3a93553f）。

沿用（不複製參數）：crisis_gate_leveraged_bb90 的 Sim／sig_credit／CONFIGS／COST、leveraged_bb90_backtest（#421 公式）
的 simulate／target_418／FEE。真實版槓桿腿：00631L、00647L 還原價（比照 bb90_oos_2025.py 對 0050 的做法）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import crisis_gate_leveraged_bb90 as CG  # noqa: E402  （import 時設定 #421 公式）
from validation.holdout import assert_no_holdout_leakage  # noqa: E402

LB, CA = CG.LB, CG.CA
PREREG = "docs/PREREG_s3c6_oos_2025.md"
PREREG_SHA = "4ab1cb46f604fef93b4897e98b9c378705ebae1596be79429ee6c235751a124e"
PARENT_SHA = "76c3eea0f3ccf504a21d3d4b2be9d47eb18938ea218105f96d89914bd0494222"
TRIAL_ID = 427
START, END = "2025-01-01", "2026-09-30"
HIST_START = "2023-10-01"   # 只用來取 2024-12 月底訊號所需的前 11 個月底，以及第一天日報酬前值
OUT = HERE / "data" / "s3c6_oos_2025_result.json"
JUMP = 0.21


def guard_preflight() -> bool:
    probe = pd.DataFrame({"date": [pd.Timestamp("2025-01-02")]})
    try:
        assert_no_holdout_leakage(probe, context="s3c6_oos_2025 守門自檢（假資料，一列）")
        return True
    except AssertionError as e:
        print(f"[停止] 保留資料守門未放行本腳本，未讀取任何保留期資料。守門訊息：{str(e)[:300]}", flush=True)
        return False


def uncapped_adj(sym: str) -> pd.DataFrame:
    """bb90_oos_2025._uncapped_0050 的同一做法，參數化標的。"""
    import adjust
    from finmind_client import load_full_history
    raw = load_full_history("TaiwanStockPrice", sym, HIST_START, allow_holdout=True)
    raw = raw.sort_values("date").reset_index(drop=True)
    div = load_full_history("TaiwanStockDividend", sym, HIST_START, allow_holdout=True)
    split_df = load_full_history("TaiwanStockSplitPrice", sym, HIST_START, allow_holdout=True)
    cr_df = load_full_history("TaiwanStockCapitalReductionReferencePrice", sym, HIST_START, allow_holdout=True)
    pv_df = adjust._par_value_change_market_wide(HIST_START, sym, uncapped=True)
    empty = pd.DataFrame()
    events = adjust._combine_adjustment_events(
        div if div is not None and not div.empty else empty,
        split_df if split_df is not None and not split_df.empty else empty,
        cr_df if cr_df is not None and not cr_df.empty else empty,
        pv_df if pv_df is not None and not pv_df.empty else empty,
        dict(zip(raw["date"], raw["close"])), raw["date"].tolist())
    f = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        m = raw["date"] < ev["ex_date"]
        f.loc[m] = f.loc[m] * ev["factor"]
    out = pd.DataFrame({"date": pd.to_datetime(raw["date"]).dt.normalize(),
                        "adj_close": raw["close"].astype(float) * f})
    a = out["adj_close"].to_numpy(float)
    r = np.zeros(len(a))
    r[1:] = a[1:] / a[:-1] - 1.0
    out["r"] = r
    out.attrs["events"] = [{"ex_date": str(e["ex_date"])[:10], "factor": float(e["factor"])} for _, e in events.iterrows()]
    assert_no_holdout_leakage(out, context=f"s3c6_oos_2025 {sym}")
    return out


def tw_rf_daily(dates: pd.Series) -> np.ndarray:
    d = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    m = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in d}).sort_index()
    m = m.reindex(pd.period_range(m.index.min(), pd.Period(END[:7], "M"), freq="M")).ffill()
    v = pd.to_datetime(dates).dt.to_period("M").map(m).astype(float).to_numpy()
    if np.isnan(v).any():
        raise RuntimeError("rf_monthly 無法涵蓋全部交易日")
    return v / 100.0 / 252.0


def dtb3_annual(dates) -> np.ndarray:
    d = pd.read_parquet(HERE / "data" / "us_rf_dtb3.parquet")
    s = pd.Series(d["dtb3_pct"].astype(float).to_numpy() / 100.0,
                  index=pd.to_datetime(d["date"]).dt.normalize()).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(pd.to_datetime(dates))).ffill().reindex(pd.to_datetime(dates)).to_numpy(float)


def baa_on(dates: pd.Series) -> np.ndarray:
    from fred_yield_curve_gate import fetch_fred_series
    b = fetch_fred_series("BAA10Y", "2022-01-01")
    b = b[pd.to_datetime(b["date"]) <= END]
    s = pd.Series(b["value"].astype(float).to_numpy(), index=pd.to_datetime(b["date"]).dt.normalize()).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(pd.to_datetime(dates))).ffill().reindex(pd.to_datetime(dates)).to_numpy(float)


def load() -> tuple[pd.DataFrame, dict]:
    from fred_yield_curve_gate import fetch_fred_series
    fxd = fetch_fred_series("DEXTAUS", "2023-01-01")
    fx = pd.Series(fxd["value"].astype(float).to_numpy(), index=pd.to_datetime(fxd["date"]).dt.normalize()).sort_index()
    fx = fx[fx.index <= END]
    p0050, p631, p647 = uncapped_adj("0050"), uncapped_adj("00631L"), uncapped_adj("00647L")
    df = pd.DataFrame({"date": p0050["date"], "r_0050": p0050["r"]})
    meta = {"adjust_events": {"0050": p0050.attrs["events"], "00631L": p631.attrs["events"], "00647L": p647.attrs["events"]}}
    for col, p, sym in (("r_ltw_real", p631, "00631L"), ("r_lus_real", p647, "00647L")):
        df = df.merge(p[["date", "r"]].rename(columns={"r": col}), on="date", how="left")
        meta[f"{sym}_missing_days"] = int(df[col].isna().sum())
        df[col] = df[col].fillna(0.0)
    vti = CA.yf_total_return_twd("VTI", fx).rename(columns={"r_twd": "r_vti"})
    ief = CA.yf_total_return_twd("IEF", fx).rename(columns={"r_twd": "r_ief"})
    df = df.merge(vti, on="date", how="left").merge(ief, on="date", how="left")
    meta["vti_missing_days"], meta["ief_missing_days"] = int(df["r_vti"].isna().sum()), int(df["r_ief"].isna().sum())
    df[["r_vti", "r_ief"]] = df[["r_vti", "r_ief"]].fillna(0.0)
    # 合成版（#421／#424 公式）
    df["r_cash"] = tw_rf_daily(df["date"])
    df["r_ltw_syn"] = 2.0 * df["r_0050"] - df["r_cash"] - LB.FEE / 252.0
    v = pd.read_parquet(CA.CACHE / "VTI.parquet")
    v = v[(v["date"] >= HIST_START) & (v["date"] <= END)].reset_index(drop=True)
    c, dv = v["close"].to_numpy(float), v["dividends"].to_numpy(float)
    r_usd = np.zeros(len(c))
    r_usd[1:] = (c[1:] + dv[1:] * (1.0 - CA.WHT)) / c[:-1] - 1.0
    lev = 2.0 * r_usd - dtb3_annual(v["date"]) / 252.0 - LB.FEE / 252.0
    f = fx.reindex(fx.index.union(pd.to_datetime(v["date"]))).ffill().reindex(pd.to_datetime(v["date"])).to_numpy(float)
    fr = np.zeros(len(f))
    with np.errstate(invalid="ignore"):
        fr[1:] = f[1:] / f[:-1] - 1.0
    fr = np.nan_to_num(fr)
    lus = pd.DataFrame({"date": pd.to_datetime(v["date"]).dt.normalize(), "r_lus_syn": (1.0 + lev) * (1.0 + fr) - 1.0})
    df = df.merge(lus, on="date", how="left")
    df["r_lus_syn"] = df["r_lus_syn"].fillna(0.0)
    df["baa"] = baa_on(df["date"])
    for nm, frame in (("VTI", vti), ("IEF", ief), ("merged", df)):
        assert_no_holdout_leakage(frame, context=f"s3c6_oos_2025 {nm}")
    meta["rf_source"] = "data/rf_monthly.json 缺月向前填補（同 #421 load_tw_rf_daily）"
    return df, meta


def metrics(r: np.ndarray, dates: pd.Series) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    days = (dates.iloc[-1] - dates.iloc[0]).days + 1
    cum = float(eq[-1] - 1.0)
    idx = pd.DatetimeIndex(dates)
    mret = pd.Series(r, index=idx).groupby(idx.to_period("M")).apply(lambda x: float(np.prod(1 + x) - 1))
    w = mret.idxmin()
    return {"cum_return": cum, "cagr": float((1 + cum) ** (365.25 / days) - 1.0), "mdd": float(dd.min()),
            "worst_month": {"month": str(w), "return": float(mret.min())},
            "monthly": {str(k): float(x) for k, x in mret.items()}}


def seg_targets(base: dict, on_seg: np.ndarray) -> np.ndarray:
    """第 s 段由 on_seg[s] 決定（on_seg[0]＝2024-12 月底訊號）；關→兩條 2 倍腿移到 CASH（S3 兩腿共用）。"""
    b = CG.tvec(base)
    T = np.tile(b, (len(on_seg), 1))
    for s, on in enumerate(on_seg):
        if not on:
            T[s, CG.KEYS.index("CASH")] += T[s, 0] + T[s, 1]
            T[s, 0] = T[s, 1] = 0.0
    return T


def run_lagged(sim, T: np.ndarray) -> np.ndarray:
    """crisis_gate_timing_sensitivity.run_lagged 的同一做法（狀態變更延後一個交易日），目標表由外部給。"""
    me_set = {int(i): k for k, i in enumerate(sim.me)}
    switch_day = {int(i) + 1: k for k, i in enumerate(sim.me) if int(i) + 1 < sim.n}
    cur = T[0].copy()
    w = cur.copy()
    out = np.zeros(sim.n)

    def cost(d):
        return float((np.abs(d) * CG.COST[0]).sum() * CA.FX_COST + (np.abs(np.minimum(d, 0)) * CG.COST[1]).sum() * CA.TW_SELL_TAX)

    for i in range(sim.n):
        w = w * (1.0 + sim.R[i])
        tot = w.sum()
        out[i] = tot - 1.0
        w = w / tot
        if i in switch_day:
            k = switch_day[i]
            new = T[k + 1] if k + 1 < sim.nseg else T[k]
            if not np.allclose(new, cur):
                out[i] -= cost(new - w)
                w = new.copy()
                cur = new.copy()
        if i in me_set:
            out[i] -= cost(cur - w)
            w = cur.copy()
    return out


def main() -> int:
    if OUT.exists():
        print(f"[拒絕] {OUT.name} 已存在：本試驗只跑一次，不得重跑。", flush=True)
        return 2
    sha = hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    psha = hashlib.sha256((ROOT / CG.PREREG).read_bytes()).hexdigest()
    if sha != PREREG_SHA or psha != PARENT_SHA:
        print("事前登記檔 SHA256 不符，拒絕執行", flush=True)
        return 2
    if not guard_preflight():
        return 3
    print("=== 載入保留期資料（只此一次）===", flush=True)
    full, meta = load()
    full_dates = full["date"]
    reb_full = (full_dates.dt.to_period("M") != full_dates.dt.to_period("M").shift(-1)).to_numpy()
    me_full = np.flatnonzero(reb_full)
    me_dates = full_dates.iloc[me_full].reset_index(drop=True)
    on_me = CG.sig_credit(full["baa"].to_numpy(float)[me_full])
    spread_me = full["baa"].to_numpy(float)[me_full]
    gate_list = []
    for k in range(len(me_full)):
        if me_dates[k] < pd.Timestamp("2024-12-01"):
            continue
        gate_list.append({"month_end": str(me_dates[k].date()), "baa10y": float(spread_me[k]),
                          "mean_12m": float(spread_me[max(0, k - 11):k + 1].mean()) if k >= CG.WARM["S3"] else None,
                          "next_month_gate": "開（持有2倍腿）" if on_me[k] else "關（2倍腿改現金）"})
    df = full[(full["date"] >= START) & (full["date"] <= END)].reset_index(drop=True)
    dates = df["date"]
    oos_me_dates = set(dates[(dates.dt.to_period("M") != dates.dt.to_period("M").shift(-1)).to_numpy()])
    me_lookup = {d: on for d, on in zip(me_dates, on_me)}
    dec = pd.Timestamp(me_dates[me_dates <= pd.Timestamp("2024-12-31")].iloc[-1])
    seg_on = [me_lookup[dec]] + [me_lookup[d] for d in sorted(oos_me_dates)][:-1]
    jumps = {k: [str(dates[i].date()) for i in np.flatnonzero(np.abs(df[c].to_numpy(float)) > JUMP)]
             for k, c in (("00631L", "r_ltw_real"), ("00647L", "r_lus_real"))}
    C6 = CG.CONFIGS["C6"]
    rets = {}
    for ver, (cl, cu) in (("S3-C6_real", ("r_ltw_real", "r_lus_real")), ("S3-C6_synthetic", ("r_ltw_syn", "r_lus_syn"))):
        d2 = df.assign(r_ltw=df[cl], r_lus=df[cu])
        sim = CG.Sim(d2)
        T = seg_targets(C6, np.array(seg_on, bool))
        if len(T) != sim.nseg:
            raise RuntimeError(f"段數不符：{len(T)} vs {sim.nseg}")
        rets[ver] = sim.run(T)
        if ver == "S3-C6_real":
            rets["S3-C6_real_lag1_report_only"] = run_lagged(sim, T)
    rets["Bb-90"] = LB.simulate(df, LB.target_418("Bb-90"))
    rets["0050_hold"] = LB.simulate(df, {"0050": 1.0})
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG, "prereg_sha256": sha, "parent_prereg": CG.PREREG, "parent_sha256": psha,
           "trial_id": TRIAL_ID, "n_trials_counted": 1,
           "period": {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": int(len(df))},
           "config_C6": C6, "gate": "S3：BAA10Y 月底值 > 最近12個月月底平均 → 下個月兩條2倍腿改台幣現金",
           "data_meta": {**meta, "real_etf_daily_jumps_gt_21pct": jumps},
           "power_note": "21 個月統計檢定力很低，好壞都不構成證明；描述性樣本外檢驗，非部署判定。",
           "segment_gate_on": [bool(x) for x in seg_on],
           "gate_months": gate_list,
           "results": {k: metrics(v, dates) for k, v in rets.items()}}
    R = res["results"]
    res["real_minus_synthetic"] = {
        "cum_return_pp": (R["S3-C6_real"]["cum_return"] - R["S3-C6_synthetic"]["cum_return"]) * 100,
        "cagr_pp": (R["S3-C6_real"]["cagr"] - R["S3-C6_synthetic"]["cagr"]) * 100,
        "mdd_pp": (R["S3-C6_real"]["mdd"] - R["S3-C6_synthetic"]["mdd"]) * 100,
        "monthly_pp": {m: (R["S3-C6_real"]["monthly"][m] - R["S3-C6_synthetic"]["monthly"][m]) * 100
                       for m in R["S3-C6_real"]["monthly"]}}
    res["s3c6_real_minus"] = {k: {"cum_return_pp": (R["S3-C6_real"]["cum_return"] - R[k]["cum_return"]) * 100,
                                  "cagr_pp": (R["S3-C6_real"]["cagr"] - R[k]["cagr"]) * 100} for k in ("Bb-90", "0050_hold")}
    res["survival_rule_1"] = {"s3c6_real_mdd": R["S3-C6_real"]["mdd"], "violates_minus_45pct_buffer": R["S3-C6_real"]["mdd"] < -0.45}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結果已寫入 {OUT}", flush=True)
    for k, x in R.items():
        print(f"{k}: 累積 {x['cum_return']*100:+.2f}%  年化 {x['cagr']*100:+.2f}%  MDD {x['mdd']*100:.2f}%  "
              f"最差月 {x['worst_month']['month']} {x['worst_month']['return']*100:+.2f}%", flush=True)
    print("閘門：", " ".join(f"{g['month_end'][:7]}:{'開' if g['next_month_gate'].startswith('開') else '關'}" for g in gate_list), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
