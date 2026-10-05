# -*- coding: utf-8 -*-
"""先.二十三-二／三：1.5 倍／0.5 倍趨勢規則跨市場複製驗證（單發）。

定義全部事前綁定於 docs/PREREG_trend_scale_xmkt_FINAL.md（登記 #415），該檔已於執行前
commit＋push。**單發只跑一次；績效數字一律到 JSON 寫完後才印。**

判定只看 8 個未看過的市場；SPY／0050 是產生假設的同一批資料，只列參考不計入判定。
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
import trend_leverage_backtest as TL  # noqa: E402  （沿用已登記的指標計算函式）

SEED = 20261006
N_CTRL = 200
MA = 200
FEE = 0.0095
COST = 0.0005
END = "2024-12-31"
PREREG = "docs/PREREG_trend_scale_xmkt_FINAL.md"
OUT = HERE / "data" / "trend_scale_xmkt_result.json"
CACHE = HERE / "data" / "raw" / "xmkt_px"
CACHE.mkdir(parents=True, exist_ok=True)

JUDGED = ["EFA", "EEM", "EWJ", "EWG", "EWU", "EWT", "EWZ", "EWY"]
REFERENCE = ["SPY"]          # 0050 另走 adjust.py，見 load_0050()
SCALES = [(1.5, 0.5), (1.25, 0.75), (1.75, 0.25)]      # 第一組判定，其餘只報告


def load_etf(sym: str) -> pd.DataFrame:
    p = CACHE / f"{sym}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    import yfinance as yf
    t = yf.Ticker(sym).history(start="1990-01-01", auto_adjust=False, actions=True).reset_index()
    t.columns = [str(c).lower().replace(" ", "_") for c in t.columns]
    dc = "date" if "date" in t.columns else t.columns[0]
    df = pd.DataFrame({"date": pd.to_datetime(t[dc]).dt.tz_localize(None).dt.normalize(),
                       "adj_close": t["adj_close"].astype(float)}).dropna().sort_values("date")
    df.to_parquet(p, index=False)
    return df


def load_0050() -> pd.DataFrame:
    import adjust
    px = adjust.adjusted_price_series("0050", "2003-01-01")[["date", "adj_close"]].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    return px.dropna().sort_values("date").reset_index(drop=True)


def rf_series() -> pd.DataFrame:
    return pd.read_parquet(HERE / "data" / "us_rf_dtb3.parquet")[["date", "dtb3_daily"]]


def prep(sym: str, rf: pd.DataFrame) -> pd.DataFrame:
    df = (load_0050() if sym == "0050" else load_etf(sym))
    df = df.merge(rf, on="date", how="left")
    df["rf_daily"] = df["dtb3_daily"].ffill().bfill().fillna(0.0)
    df = df[df["date"] <= END].reset_index(drop=True)
    return df[["date", "adj_close", "rf_daily"]]


def run_scaled(df: pd.DataFrame, hi: float, lo: float, cost_mult: float = 1.0,
               signal: np.ndarray | None = None):
    """曝險 hi（看多）／lo（看空）。回傳 (策略日報酬, 基準日報酬, 部位, 換倉次數)。

    槓桿年費**只在曝險 > 1 時計收**（0.5 倍是減碼，不涉及槓桿工具）。
    訊號當日收盤算出、**次一交易日起**生效，避免未來函數。
    """
    px = df["adj_close"].to_numpy(float)
    rf = df["rf_daily"].to_numpy(float)
    bench = np.zeros(len(px))
    bench[1:] = px[1:] / px[:-1] - 1.0
    if signal is None:
        sma = pd.Series(px).rolling(MA).mean().to_numpy()
        sig = (px > sma).astype(float)
        sig[np.isnan(sma)] = 0.0
    else:
        sig = signal.astype(float)
    expo = np.where(np.r_[0.0, sig[:-1]] > 0, hi, lo)
    fee = np.where(expo > 1.0, FEE / 252.0, 0.0)
    ret = expo * bench - (expo - 1.0) * rf - fee
    sw = np.zeros(len(px), dtype=bool)
    sw[1:] = expo[1:] != expo[:-1]
    ret = ret - sw * COST * cost_mult
    ret[:MA] = rf[:MA]                      # 均線未成形前不進場，領現金
    return ret, bench, expo, int(sw.sum())


def row(df, r, b, nsw):
    d = df["date"]
    return {"start": str(d.iloc[0].date()), "end": str(d.iloc[-1].date()), "n_days": int(len(d)),
            "cagr": TL.cagr(r, d), "mdd": TL.mdd(r), "sortino": TL.sortino(r),
            "worst_12m": TL.worst_12m(r), "longest_underwater_days": TL.longest_underwater(r),
            "bench_cagr": TL.cagr(b, d), "bench_mdd": TL.mdd(b), "bench_sortino": TL.sortino(b),
            "bench_worst_12m": TL.worst_12m(b),
            "bench_longest_underwater_days": TL.longest_underwater(b),
            "sortino_ge_bench": bool(TL.sortino(r) >= TL.sortino(b)),
            "mdd_shallower_than_bench": bool(TL.mdd(r) > TL.mdd(b)),
            "n_switches": nsw}


def main() -> int:
    rf = rf_series()
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG,
           "prereg_sha256": hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
           "prereg_trial_id": 415, "seed": SEED,
           "holdout_note": "資料截至 2024-12-31，2025 起未讀取",
           "rules": {"ma": MA, "exposure_long": 1.5, "exposure_short": 0.5,
                     "annual_fee_when_levered": FEE, "switch_cost_one_way": COST},
           "provenance": ("本規則源自 #413/#414 只報告的配置數據，屬事後假設；"
                          "SPY/0050 為產生假設的同一批資料，只列參考不計入判定")}
    print("=== 載入市場 ===", flush=True)
    data = {}
    for s in JUDGED + REFERENCE + ["0050"]:
        try:
            data[s] = prep(s, rf)
            print(f"  {s}: {len(data[s])} 日 {data[s]['date'].iloc[0].date()} ~ {data[s]['date'].iloc[-1].date()}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  {s}: 載入失敗 {type(e).__name__}: {e}", flush=True)

    # (a)(b) 逐市場 × 三組曝險
    tables = {}
    for hi, lo in SCALES:
        key = f"{hi:g}x/{lo:g}x"
        tbl = {}
        for s in JUDGED + REFERENCE + ["0050"]:
            if s not in data:
                continue
            r, b, _, nsw = run_scaled(data[s], hi, lo)
            tbl[s] = row(data[s], r, b, nsw)
        tables[key] = tbl
    res["per_market"] = tables
    main_key = "1.5x/0.5x"
    mt = tables[main_key]
    passed = [s for s in JUDGED if s in mt and mt[s]["sortino_ge_bench"] and mt[s]["mdd_shallower_than_bench"]]
    res["gate_b_main"] = {"rule": "8 個市場中至少 6 個同時『Sortino ≥ 買進持有』且『MDD 比買進持有淺』",
                          "n_judged": len(JUDGED), "n_passed": len(passed), "passed": passed,
                          "failed": [s for s in JUDGED if s not in passed],
                          "pass": bool(len(passed) >= 6)}

    # (c) 8 市場等權組合（每日再平衡）
    idx = None
    for s in JUDGED:
        d = data[s]["date"]
        idx = d if idx is None else idx[idx.isin(d)]
    comb = pd.DataFrame({"date": sorted(idx)})
    rs, bs = [], []
    for s in JUDGED:
        d = data[s].set_index("date")
        sub = data[s][data[s]["date"].isin(comb["date"])].reset_index(drop=True)
        r, b, _, _ = run_scaled(sub, 1.5, 0.5)
        rs.append(pd.Series(r, index=sub["date"]).reindex(comb["date"]).to_numpy())
        bs.append(pd.Series(b, index=sub["date"]).reindex(comb["date"]).to_numpy())
    R = np.nanmean(np.vstack(rs), axis=0)
    B = np.nanmean(np.vstack(bs), axis=0)
    R = np.nan_to_num(R)
    B = np.nan_to_num(B)
    nsw_tot = int(sum(tables[main_key][s]["n_switches"] for s in JUDGED))
    cdf = comb.copy()
    res["combined_equal_weight"] = {
        "start": str(cdf["date"].iloc[0].date()), "end": str(cdf["date"].iloc[-1].date()),
        "n_days": int(len(cdf)), "note": "8 市場等權、每日再平衡；僅取 8 市場皆有報價的交易日",
        "cagr": TL.cagr(R, cdf["date"]), "mdd": TL.mdd(R), "sortino": TL.sortino(R),
        "worst_12m": TL.worst_12m(R), "longest_underwater_days": TL.longest_underwater(R),
        "bench_cagr": TL.cagr(B, cdf["date"]), "bench_mdd": TL.mdd(B), "bench_sortino": TL.sortino(B)}
    res["gate_c_survival"] = {"mdd": TL.mdd(R), "pass": bool(TL.mdd(R) > -0.5)}

    # 隨機擇時對照（組合層，同換倉次數、200 條）
    rng = np.random.default_rng(SEED)
    ctrl = []
    per_mkt_sw = {s: tables[main_key][s]["n_switches"] for s in JUDGED}
    for _ in range(N_CTRL):
        rr = []
        for s in JUDGED:
            sub = data[s][data[s]["date"].isin(comb["date"])].reset_index(drop=True)
            n = len(sub)
            k = min(per_mkt_sw[s], max(1, n - MA - 2))
            cuts = np.sort(rng.choice(np.arange(MA, n - 1), size=k, replace=False))
            sig = np.zeros(n)
            st, prev = 0.0, MA
            for c in cuts:
                sig[prev:c] = st
                st = 1.0 - st
                prev = c
            sig[prev:] = st
            r, _, _, _ = run_scaled(sub, 1.5, 0.5, signal=sig)
            rr.append(pd.Series(r, index=sub["date"]).reindex(comb["date"]).to_numpy())
        ctrl.append(TL.sortino(np.nan_to_num(np.nanmean(np.vstack(rr), axis=0))))
    cs = np.array([x for x in ctrl if not np.isnan(x)])
    res["gate_c_random_timing"] = {"k": int(len(cs)), "strategy": TL.sortino(R),
                                   "control_max": float(cs.max()), "control_mean": float(cs.mean()),
                                   "control_p95": float(np.percentile(cs, 95)),
                                   "percentile": float(100.0 * (cs < TL.sortino(R)).mean()),
                                   "pass": bool(TL.sortino(R) > cs.max())}
    # 成本 1x/2x/3x（組合層）
    costs = {}
    for m_ in (1.0, 2.0, 3.0):
        rr = []
        for s in JUDGED:
            sub = data[s][data[s]["date"].isin(comb["date"])].reset_index(drop=True)
            r, _, _, _ = run_scaled(sub, 1.5, 0.5, cost_mult=m_)
            rr.append(pd.Series(r, index=sub["date"]).reindex(comb["date"]).to_numpy())
        Rm = np.nan_to_num(np.nanmean(np.vstack(rr), axis=0))
        costs[f"{m_:g}x"] = {"cagr": TL.cagr(Rm, cdf["date"]), "mdd": TL.mdd(Rm),
                             "sortino": TL.sortino(Rm),
                             "survive": bool(TL.sortino(Rm) >= TL.sortino(B) and TL.mdd(Rm) > -0.5)}
    res["gate_c_costs"] = costs
    res["gate_c_costs_pass"] = all(v["survive"] for v in costs.values())

    order = [("gate_b_main", "主判定 8 市場至少 6 個"),
             ("gate_c_survival", "組合版天條一"),
             ("gate_c_random_timing", "組合版隨機擇時對照"),
             ("gate_c_costs", "組合版成本 1x/2x/3x")]
    verdict, failed = "PASS", None
    for k, nm in order:
        ok = res["gate_c_costs_pass"] if k == "gate_c_costs" else bool(res[k].get("pass"))
        if not ok:
            verdict = "VIOLATES_SURVIVAL" if k == "gate_c_survival" else "FAIL"
            failed = (k, nm)
            break
    res["verdict"] = verdict
    res["first_failed_gate"] = failed[0] if failed else None
    res["first_failed_gate_name"] = failed[1] if failed else None

    def conv(o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    print(f"已寫入 {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
