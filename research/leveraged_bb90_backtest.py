# -*- coding: utf-8 -*-
"""先.三十三-三：槓桿版 Bb-90 單發檢定。

定義全部事前綁定於 docs/PREREG_leveraged_bb90_FINAL.md（登記 #419，試驗數以 6 計入 N，
家族合計 30），該檔已於執行前 commit＋push。**單發只跑一次；績效數字一律到 JSON 寫完後才印。**

順序：①追蹤誤差驗證（00631L／00647L）→ 任一 |CAGR 差| > 2pp 即判無效、不跑網格
      ②六組網格＋Bb-90 重算 → 通過條件 → DSR／cluster bootstrap → 只報告項。
通過也只能提紙上追蹤草案，不得接入自動下單。
"""
from __future__ import annotations

import hashlib
import json
import math
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
import core_allocation_backtest as CA  # noqa: E402  #418 同一資料載入與成本
import trend_leverage_backtest as TL  # noqa: E402  mdd/sortino/cagr/worst_12m

PREREG = "docs/PREREG_leveraged_bb90_FINAL.md"
PREREG_TRIAL = 419
OUT = HERE / "data" / "leveraged_bb90_result.json"
END = "2024-12-31"
SEED = 20261006
B_BOOT = 2000
TE_MAX_PP = 2.0
FEE = 0.01
SPREAD = 0.01
GRID = {"C1": (0.45, 0.00, 0.55), "C2": (0.30, 0.30, 0.40), "C3": (0.55, 0.00, 0.45),
        "C4": (0.40, 0.30, 0.30), "C5": (0.65, 0.00, 0.35), "C6": (0.50, 0.30, 0.20)}
STRESS = {"2008": ("2008-01-01", "2008-12-31"), "2020": ("2020-02-01", "2020-04-30"),
          "2022": ("2022-01-01", "2022-12-31")}
DAILY_JUMP_MAX = 0.21

# 先.三十四-一：#421 重新登記（docs/PREREG_leveraged_bb90_421.md）。以 --formula 421 切換；
# 預設仍為 #419/#420 舊公式（保留供稽核，不刪）。
F421 = "--formula" in sys.argv and sys.argv[sys.argv.index("--formula") + 1] == "421"
if F421:
    PREREG = "docs/PREREG_leveraged_bb90_421.md"
    PREREG_TRIAL = 421
    OUT = HERE / "data" / "leveraged_bb90_421_result.json"
    SPREAD = 0.0          # 期貨定價原理：不含借款利差
N_FAMILY = 36 if F421 else 30


def load_tw_rf_daily(dates: pd.Series) -> np.ndarray:
    """#421：data/rf_monthly.json 央行一個月定存（年化%，月資料）→ 所屬月份日化 /252；缺月向前填補；2025 起不讀。"""
    d = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    m = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in d if r["date"][:10] <= END})
    m = m.sort_index()
    m = m.reindex(pd.period_range(m.index.min(), pd.Period(END[:7], "M"), freq="M")).ffill()
    per = pd.to_datetime(dates).dt.to_period("M")
    v = per.map(m).astype(float).to_numpy()
    if np.isnan(v).any():
        raise RuntimeError("rf_monthly 無法涵蓋全部交易日（期初缺值）")
    return v / 100.0 / 252.0


def prog(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


# ───────── 資料 ─────────
def load_dtb3_annual(dates: pd.Series) -> np.ndarray:
    d = pd.read_parquet(HERE / "data" / "us_rf_dtb3.parquet")
    d = d[d["date"] <= END]                      # 2025 起不讀（快取含更新資料）
    s = pd.Series(d["dtb3_pct"].astype(float).to_numpy() / 100.0,
                  index=pd.to_datetime(d["date"]).dt.normalize()).sort_index()
    return s.reindex(pd.to_datetime(dates)).ffill().bfill().to_numpy(float)


def vti_lev_twd(fx: pd.Series) -> pd.DataFrame:
    """L_US：美元層 2×r_usd − b − f，再換台幣；r_usd 同 #418（未調整收盤＋配息×(1−30%)）。"""
    d = pd.read_parquet(CA.CACHE / "VTI.parquet")
    d = d[d["date"] <= END].reset_index(drop=True)
    c = d["close"].to_numpy(float)
    dv = d["dividends"].to_numpy(float)
    r_usd = np.zeros(len(c))
    r_usd[1:] = (c[1:] + dv[1:] * (1.0 - CA.WHT)) / c[:-1] - 1.0
    b = (load_dtb3_annual(d["date"]) + SPREAD) / 252.0
    lev = 2.0 * r_usd - b - FEE / 252.0
    lev[0] = 0.0
    f = fx.reindex(d["date"]).ffill().to_numpy(float)
    fr = np.zeros(len(f))
    with np.errstate(invalid="ignore"):
        fr[1:] = f[1:] / f[:-1] - 1.0
    fr = np.nan_to_num(fr)
    return pd.DataFrame({"date": d["date"], "r_lus": (1.0 + lev) * (1.0 + fr) - 1.0})


def load_all() -> tuple[pd.DataFrame, pd.Series]:
    base = CA.load_all()["df"]                    # #418 同一函式（已截至 2024-12-31）
    from fred_yield_curve_gate import fetch_fred_series
    fxd = fetch_fred_series("DEXTAUS", "2002-01-01")
    fx = pd.Series(fxd["value"].astype(float).to_numpy(),
                   index=pd.to_datetime(fxd["date"]).dt.normalize()).sort_index()
    fx = fx[fx.index <= END]
    b = (load_tw_rf_daily(base["date"]) if F421 else (load_dtb3_annual(base["date"]) + SPREAD) / 252.0)
    base["r_ltw"] = 2.0 * base["r_0050"].to_numpy(float) - b - FEE / 252.0
    base.loc[base.index[0], "r_ltw"] = 0.0
    lus = vti_lev_twd(fx)
    df = base.merge(lus, on="date", how="left")
    df["r_lus"] = df["r_lus"].fillna(0.0)        # 同 #418 VTI 的 left-merge＋補 0
    return df, fx


# ───────── 模擬（#418 simulate 的同一算法，擴充槓桿腿） ─────────
USD = {"VTI", "IEF", "LUS"}
TWSE = {"0050", "LTW"}


def simulate(df: pd.DataFrame, tgt: dict) -> np.ndarray:
    col = {"0050": "r_0050", "VTI": "r_vti", "IEF": "r_ief", "CASH": "r_cash", "LTW": "r_ltw", "LUS": "r_lus"}
    keys = [k for k, v in tgt.items() if v > 0]
    comp = np.column_stack([df[col[k]].to_numpy(float) for k in keys])
    t = np.array([tgt[k] for k in keys], float)
    reb = (df["date"].dt.to_period("M") != df["date"].dt.to_period("M").shift(-1)).to_numpy()
    w = t.copy()
    out = np.zeros(len(df))
    for i in range(len(df)):
        w = w * (1.0 + comp[i])
        tot = w.sum()
        out[i] = tot - 1.0
        w = w / tot
        if reb[i]:
            d = t - w
            cost = 0.0
            for j, k in enumerate(keys):
                if k in USD:
                    cost += abs(d[j]) * CA.FX_COST
                elif k in TWSE and d[j] < 0:
                    cost += abs(d[j]) * CA.TW_SELL_TAX
            out[i] -= cost
            w = t.copy()
    return out


def grid_target(lev2: float, one: float, ief: float) -> dict:
    return {"LTW": lev2 / 2, "LUS": lev2 / 2, "0050": one / 2, "VTI": one / 2, "IEF": ief}


def target_418(key: str) -> dict:
    eq, sf, w = key[0], key[1], int(key.split("-")[1]) / 100.0
    t = {"0050": w} if eq == "A" else {"0050": w / 2, "VTI": w / 2}
    ws = 1.0 - w
    if sf == "a":
        t["CASH"] = ws
    elif sf == "b":
        t["IEF"] = ws
    else:
        t["CASH"] = ws / 2
        t["IEF"] = ws / 2
    return t


# ───────── 指標 ─────────
def stats(r: np.ndarray, dates: pd.Series) -> dict:
    half = len(r) // 2
    return {"cagr": TL.cagr(r, dates), "mdd": TL.mdd(r), "sortino": TL.sortino(r),
            "worst_12m": TL.worst_12m(r), "longest_underwater_days": TL.longest_underwater(r),
            "cagr_first_half": TL.cagr(r[:half], dates[:half].reset_index(drop=True)),
            "cagr_second_half": TL.cagr(r[half:], dates[half:].reset_index(drop=True)),
            "mdd_first_half": TL.mdd(r[:half]), "mdd_second_half": TL.mdd(r[half:]),
            "sharpe_daily": float(r.mean() / r.std(ddof=1)),
            "total_ret": float(np.prod(1 + r) - 1)}


def moments(r: np.ndarray) -> tuple[float, float]:
    x = r - r.mean()
    sd = x.std(ddof=0)
    return float((x ** 3).mean() / sd ** 3), float((x ** 4).mean() / sd ** 4)


def dsr(r: np.ndarray, n: int, v: float) -> dict:
    from candidate_report import CandidateStats, deflated_sharpe
    sk, ku = moments(r)
    st = CandidateStats(float(r.mean() / r.std(ddof=1)), len(r), sk, ku, 252)
    return deflated_sharpe(st, n, v, var_periods_per_year=252)


def cluster_boot(rc: np.ndarray, rb: np.ndarray, dates: pd.Series) -> dict:
    yrs = dates.dt.year.to_numpy()
    ex = np.log1p(rc) - np.log1p(rb)
    uy = sorted(set(yrs))
    sums = np.array([ex[yrs == y].sum() for y in uy])
    ndays = np.array([(yrs == y).sum() for y in uy], float)
    rng = np.random.default_rng(SEED)
    out = np.empty(B_BOOT)
    for b in range(B_BOOT):
        idx = rng.integers(0, len(uy), len(uy))
        out[b] = sums[idx].sum() / (ndays[idx].sum() / 252.0)
    return {"clusters": len(uy), "B": B_BOOT, "seed": SEED,
            "share_excess_gt_0": float(np.mean(out > 0)), "share_excess_gt_1pp": float(np.mean(out > 0.01)),
            "p5_p50_p95_annual_log_excess": [float(x) for x in np.percentile(out, [5, 50, 95])],
            "pass": bool(np.mean(out > 0) >= 0.90)}


def seg(r, dates, a, b):
    m = ((dates >= a) & (dates <= b)).to_numpy()
    x = r[m]
    return {"n_days": int(len(x)), "ret": float(np.prod(1 + x) - 1), "mdd": TL.mdd(x) if len(x) > 2 else None}


# ───────── 追蹤誤差驗證 ─────────
def real_etf(sym: str) -> tuple[pd.DataFrame | None, dict]:
    import adjust
    info = {}
    for path in ("adjusted_price_series", "_finmind_adjusted_frame"):
        try:
            p = getattr(adjust, path)(sym, "2014-01-01")
        except Exception as e:  # noqa: BLE001
            info[path] = f"取得失敗：{type(e).__name__}: {str(e)[:120]}"
            continue
        p = p[["date", "adj_close"] + [c for c in ("close", "volume") if c in p.columns]].dropna(subset=["adj_close"])
        p["date"] = pd.to_datetime(p["date"]).dt.normalize()
        p = p[p["date"] <= END].sort_values("date").reset_index(drop=True)
        a = p["adj_close"].to_numpy(float)
        rr = np.zeros(len(a))
        rr[1:] = a[1:] / a[:-1] - 1.0
        bad = int((np.abs(rr) > DAILY_JUMP_MAX).sum())
        info[path] = {"n": len(p), "start": str(p["date"].iloc[0].date()) if len(p) else None,
                      "n_jumps_gt_21pct": bad, "source": str(p.get("source", pd.Series(["?"])).iloc[0]) if "source" in p else None}
        if len(p) > 100 and bad == 0:
            p["r"] = rr
            info["used"] = path
            return p, info
    return None, info


def tracking(sym: str, syn_col: str, df: pd.DataFrame) -> dict:
    p, info = real_etf(sym)
    if p is None:
        return {"symbol": sym, "ok": False, "reason": "追蹤驗證無法完成（資料瑕疵或取不到）", "data": info}
    first = p["date"].iloc[0]
    start = (first + pd.offsets.MonthBegin(1)).normalize()   # 上市後第一個完整月份
    p = p[p["date"] >= start]
    mg = p[["date", "r"]].merge(df[["date", syn_col]], on="date", how="inner").reset_index(drop=True)
    mg.loc[0, ["r", syn_col]] = 0.0                            # 起點不計入
    a, s = mg["r"].to_numpy(), mg[syn_col].to_numpy()
    ca, cs = TL.cagr(a, mg["date"]), TL.cagr(s, mg["date"])
    m = mg.set_index("date")[["r", syn_col]].apply(lambda x: (1 + x).resample("ME").prod() - 1)
    te_m = float((m["r"] - m[syn_col]).std(ddof=1) * math.sqrt(12))
    lag1 = float(np.corrcoef(a[1:], s[:-1])[0, 1])
    gap = abs(ca - cs) * 100
    return {"symbol": sym, "ok": True, "synthetic": syn_col, "data": info,
            "window": [str(mg["date"].iloc[0].date()), str(mg["date"].iloc[-1].date())], "n_days": len(mg),
            "cagr_actual": ca, "cagr_synthetic": cs, "abs_cagr_gap_pp": gap,
            "mdd_actual": TL.mdd(a), "mdd_synthetic": TL.mdd(s),
            "report_only": {"monthly_te_annualized_pp": te_m * 100,
                            "daily_corr_same_day": float(np.corrcoef(a, s)[0, 1]),
                            "daily_corr_actual_vs_synthetic_lag1": lag1},
            "pass": bool(gap <= TE_MAX_PP)}


def volume_report(df_unused=None) -> dict:
    try:
        import adjust
        p = adjust._finmind_adjusted_frame("00647L", "2023-01-01")
        p["date"] = pd.to_datetime(p["date"])
        p = p[(p["date"] >= "2023-01-01") & (p["date"] <= END)]
        val = p["Trading_money"].astype(float).to_numpy()   # FinMind 成交金額（元）；原寫 volume×close 欄名不存在，報告項 bug 修正
        med = float(np.median(val))
        trade = 10_000_000 * 0.05
        return {"window": "2023-01-01~2024-12-31", "n_days": int(len(val)), "source": "FinMind（adjust._finmind_adjusted_frame）",
                "median_daily_value_twd": med, "p10_daily_value_twd": float(np.percentile(val, 10)),
                "assumed_rebalance_trade_twd": trade, "trade_pct_of_median": trade / med * 100 if med else None,
                "note": "只報告不判定；假設組合1,000萬×5%調整"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"未取得：{type(e).__name__}: {str(e)[:160]}"}


def conv(o):
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def main() -> int:
    sha = hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG, "prereg_sha256": sha, "prereg_trial_id": PREREG_TRIAL,
           "n_trials_counted": 6, "n_trials_family": N_FAMILY,
           "holdout_note": "資料截至 2024-12-31，2025 起未讀取（DTB3／DEXTAUS／VTI 快取在載入處截斷）",
           "synthetic": ("#421：2×含息日報酬 −當地短利/252 −1%/252（台股：央行一個月定存 rf_monthly；美股：DTB3）；L_US 於美元層計算後換台幣"
                         if F421 else "2×日報酬 −(DTB3+1%)/252 −1%/252；L_US 於美元層計算後換台幣")}
    prog("載入資料")
    df, _fx = load_all()
    dates = df["date"]
    res["period"] = {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": len(df)}
    prog(f"資料 {len(df)} 日")

    prog("追蹤誤差驗證")
    tr = {"00631L": tracking("00631L", "r_ltw", df), "00647L": tracking("00647L", "r_lus", df)}
    res["tracking_validation"] = tr
    valid = all(v.get("ok") and v.get("pass") for v in tr.values())
    res["tracking_valid"] = valid
    if not valid:
        res["verdict"] = "INVALID：追蹤誤差驗證未通過（或無法完成），依事前登記不跑網格"
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
        prog(f"已寫入 {OUT}（未跑網格）")
        return 0

    prog("網格")
    rets = {"Bb-90": simulate(df, target_418("Bb-90"))}
    for k, (a, b, c) in GRID.items():
        rets[k] = simulate(df, grid_target(a, b, c))
    S = {k: stats(r, dates) for k, r in rets.items()}
    ref418 = json.loads(CA.OUT.read_text(encoding="utf-8"))["grid"]["Bb-90"]
    res["bb90_recomputed"] = S["Bb-90"]
    res["bb90_vs_418_file"] = {"cagr_418": ref418["cagr"], "cagr_now": S["Bb-90"]["cagr"],
                               "diff_pp": (S["Bb-90"]["cagr"] - ref418["cagr"]) * 100,
                               "mdd_418": ref418["mdd"], "mdd_now": S["Bb-90"]["mdd"]}
    # V：30 組日頻 Sharpe 的樣本變異數（24 組 #418 定義重算＋6 組）
    sh = []
    for eq in ("A", "B"):
        for sf in ("a", "b", "c"):
            for w in CA.EQUITY_W:
                k = f"{eq}{sf}-{int(w * 100)}"
                r = rets[k] if k in rets else simulate(df, target_418(k))
                sh.append(float(r.mean() / r.std(ddof=1)))
    sh += [S[k]["sharpe_daily"] for k in GRID]
    V = float(np.var(sh, ddof=1))
    res["dsr_V"] = {"value_daily": V, "n_sharpes": len(sh), "N_used": N_FAMILY,
                    "source": "本家族可取得 30 組（#418 24 組重算＋本次 6 組）日頻 Sharpe 樣本變異數" + ("；#420 未產生網格 Sharpe，只計入 N" if F421 else ""),
                    "bias_note": "同家族配置組合高度相關，V 偏小→SR0 偏低→DSR 偏寬鬆；另報全帳本 V 敏感度"}
    v_global = None
    try:
        import dsr_reeval as DR
        rows = DR.collect_sharpe_rows()
        ann = [r["sharpe_ann"] for r in rows]
        v_global = float(np.var(ann, ddof=1) / 252.0) if len(ann) >= 2 else None
        res["dsr_V_global_report_only"] = {"value_daily": v_global, "n_sharpes": len(ann),
                                           "source": "dsr_reeval.collect_sharpe_rows()（V 為僅有 Sharpe 記錄者的離散度，非全體）"}
    except Exception as e:  # noqa: BLE001
        res["dsr_V_global_report_only"] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}

    b = S["Bb-90"]
    res["grid"] = {}
    for k in GRID:
        s = S[k]
        d = dsr(rets[k], N_FAMILY, V)
        ex = rets[k] - rets["Bb-90"]
        rep = {}
        if v_global:
            try:
                rep["dsr_global_V"] = dsr(rets[k], N_FAMILY, v_global)["dsr"]
            except Exception as e:  # noqa: BLE001
                rep["dsr_global_V"] = f"{type(e).__name__}"
        try:
            rep["dsr_excess_vs_bb90_family_V"] = dsr(ex, N_FAMILY, V)["dsr"]
        except Exception as e:  # noqa: BLE001
            rep["dsr_excess_vs_bb90_family_V"] = f"{type(e).__name__}"
        cb = cluster_boot(rets[k], rets["Bb-90"], dates)
        cond = {"mdd_gt_-45": s["mdd"] > -0.45, "worst12m_gt_-40": s["worst_12m"] > -0.40,
                "cagr_ge_bb90_plus_1pp": s["cagr"] >= b["cagr"] + 0.01,
                "first_half_gt_bb90": s["cagr_first_half"] > b["cagr_first_half"],
                "second_half_gt_bb90": s["cagr_second_half"] > b["cagr_second_half"],
                "dsr_ge_0.95": d["dsr"] >= 0.95, "cluster_boot_ge_0.90": cb["pass"]}
        res["grid"][k] = {"weights": dict(zip(("2x", "1x", "IEF"), GRID[k])), **s,
                          "cagr_minus_bb90_pp": (s["cagr"] - b["cagr"]) * 100,
                          "dsr": d, "dsr_report_only": rep, "cluster_bootstrap": cb,
                          "conditions": cond, "pass": bool(all(cond.values())),
                          "stress_report_only": {nm: {"cand": seg(rets[k], dates, a, z), "bb90": seg(rets["Bb-90"], dates, a, z)}
                                                 for nm, (a, z) in STRESS.items()}}
    passed = [k for k in GRID if res["grid"][k]["pass"]]
    winner = max(passed, key=lambda k: S[k]["cagr"]) if passed else None
    res["passed"] = passed
    res["winner"] = winner
    res["verdict"] = (f"PASS：{winner} 勝出（只能提紙上追蹤草案，不得接入自動下單）" if winner
                      else "FAIL：六組皆未全部通過，維持 Bb-90")
    res["volume_00647L_report_only"] = volume_report()
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    prog(f"已寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
