# -*- coding: utf-8 -*-
"""驗.八 三（析.二）：營收→EPS 預估（nowcast）可行性——只驗「預估準不準」，
**不跑任何報酬回測**、不登記試驗、不改任何判定（凍結.二仍生效，這是前置研究）。

對每檔股票、每一季，在「該季財報公布之前」（取該季第3個月營收公布日 T_n，
即 month_revenue_pit 的 pit_date）估：
    預估EPS = 該季三個月「已公布」月營收加總 × 過去4季平均淨利率 ÷ 股數
- 淨利率＝歸屬母公司淨利(EquityAttributableToOwnersOfParent，缺則IncomeAfterTaxes)÷Revenue，
  過去4季逐季比率取簡單平均（敏感度另報「加總比」）。
- 股數＝**前一季**（T_n 時點已公布的最新一季）CapitalStock ÷ 面額10元；
  敏感度另報「隱含股數＝前一季歸屬淨利÷前一季EPS」。
- 所有輸入的可得日一律 ≤ T_n（前四季財報 pit_date 均先檢查 ≤ T_n）；
  評估季限制 pit_date ≤ VAL_END（holdout 一律不碰，load_dev 亦已 cap）。
準確度：預估 vs 實際 EPS 的相關、方向命中率（相對去年同季 EPS 的升降）、誤差分佈；
另列「T_n → 季報法定截止日」的平均交易日數（可交易窗口上限，因實際公告日
多早於法定截止日，這是上限不是實測）。

輸出：research/data/diag_v8_nowcast_eps.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

import factor_ic as fic
import pit as pit_mod
from finmind_client import load_dev
from validation import holdout

OUT = Path(__file__).parent / "data" / "diag_v8_nowcast_eps.json"
HIST_START = "2010-01-01"  # 驗.九二.2：由2012改2010以重用既有快取；評估季由EVAL_FROM固定，不受影響
EVAL_FROM = pd.Timestamp("2014-12-31")  # 第一個評估季（需前四季→2013Q4起有資料）
PAR_VALUE = 10.0
SCALE_FLOOR = 0.1


def _quarter_end(d: pd.Timestamp) -> pd.Timestamp:
    return d + pd.offsets.QuarterEnd(0)


def _shift_q(pe: pd.Timestamp, k: int) -> pd.Timestamp:
    return (pe + pd.offsets.QuarterEnd(k)).normalize()


def _calendar() -> np.ndarray:
    px = load_dev("TaiwanStockPrice", "2330", HIST_START)
    return np.array(sorted(pd.to_datetime(px["date"]).unique()), dtype="datetime64[D]")


def _tdays_between(cal: np.ndarray, a: pd.Timestamp, b: pd.Timestamp) -> int:
    """(a, b] 內的交易日數。"""
    lo = np.searchsorted(cal, np.datetime64(a.date()), side="right")
    hi = np.searchsorted(cal, np.datetime64(b.date()), side="right")
    return int(max(hi - lo, 0))


def _stock_rows(sid: str, cal: np.ndarray) -> list[dict]:
    q = pit_mod.quarterly_pit(sid, HIST_START)
    try:
        b = pit_mod.balance_sheet_pit(sid, HIST_START)
    except Exception:  # noqa: BLE001 -- 資產負債表未快取且 FinMind 冷卻中：只跑「隱含股數」版本
        b = pd.DataFrame()
    m = pit_mod.month_revenue_pit(sid, HIST_START)
    if q.empty or m.empty or "EPS" not in q.columns or "Revenue" not in q.columns:
        return []
    ni_col = "EquityAttributableToOwnersOfParent" if "EquityAttributableToOwnersOfParent" in q.columns else "IncomeAfterTaxes"
    if ni_col not in q.columns:
        return []
    has_bs = (not b.empty) and "CapitalStock" in b.columns
    q = q.copy()
    q["pe"] = pd.to_datetime(q["fiscal_period_end"])
    q = q.drop_duplicates("pe").set_index("pe").sort_index()
    q["pit"] = pd.to_datetime(q["pit_date"])
    q["ni"] = pd.to_numeric(q[ni_col], errors="coerce")
    q["rev"] = pd.to_numeric(q["Revenue"], errors="coerce")
    q["eps"] = pd.to_numeric(q["EPS"], errors="coerce")
    if has_bs:
        b = b.copy()
        b["pe"] = pd.to_datetime(b["fiscal_period_end"])
        b = b.drop_duplicates("pe").set_index("pe").sort_index()
        cap = pd.to_numeric(b["CapitalStock"], errors="coerce")
    else:
        cap = pd.Series(dtype=float)
    m = m.copy()
    m["rev_m"] = pd.to_numeric(m["revenue"], errors="coerce")
    m["pit"] = pd.to_datetime(m["pit_date"])
    mkey = {(int(r.revenue_year), int(r.revenue_month)): (r.rev_m, r.pit) for r in m.itertuples()}

    rows: list[dict] = []
    for pe in q.index:
        if pe < EVAL_FROM:
            continue
        pit_q = q.at[pe, "pit"]
        if pit_q > pd.Timestamp(holdout.VAL_END):
            continue
        actual = q.at[pe, "eps"]
        if not np.isfinite(actual):
            continue
        # 三個月營收
        months = [(pe.year, pe.month - 2), (pe.year, pe.month - 1), (pe.year, pe.month)]
        vals, pits = [], []
        for y, mo in months:
            if (y, mo) not in mkey:
                vals = []
                break
            v, p = mkey[(y, mo)]
            vals.append(v)
            pits.append(p)
        if len(vals) != 3 or not all(np.isfinite(vals)):
            continue
        t_n = max(pits)
        if t_n >= pit_q:
            continue
        # 前四季（必須是連續4個曆季，且 T_n 時皆已可得）
        prev = [_shift_q(pe, -k) for k in (1, 2, 3, 4)]
        if any(p not in q.index for p in prev):
            continue
        if any(q.at[p, "pit"] > t_n for p in prev):
            continue
        margins, ni_s, rev_s = [], 0.0, 0.0
        ok = True
        for p in prev:
            r, n = q.at[p, "rev"], q.at[p, "ni"]
            if not (np.isfinite(r) and np.isfinite(n)) or r <= 0:
                ok = False
                break
            margins.append(n / r)
            ni_s += n
            rev_s += r
        if not ok:
            continue
        p1 = prev[0]
        shares = cap.at[p1] / PAR_VALUE if (p1 in cap.index and np.isfinite(cap.at[p1]) and cap.at[p1] > 0) else np.nan
        eps1, ni1 = q.at[p1, "eps"], q.at[p1, "ni"]
        implied_shares = (ni1 / eps1) if (np.isfinite(eps1) and abs(eps1) > 1e-9 and np.isfinite(ni1)) else np.nan
        rev3 = float(sum(vals))
        est = rev3 * float(np.mean(margins)) / shares if np.isfinite(shares) else np.nan
        est_sum = rev3 * (ni_s / rev_s) / shares if np.isfinite(shares) else np.nan
        est_impl = rev3 * float(np.mean(margins)) / implied_shares if np.isfinite(implied_shares) and implied_shares > 0 else np.nan
        p4 = prev[3]
        eps_ly = q.at[p4, "eps"]
        past_eps = [q.at[p, "eps"] for p in prev]
        scale = max(float(np.nanmean(np.abs(past_eps))), SCALE_FLOOR)
        rows.append({
            "sid": sid, "pe": pe.strftime("%Y-%m-%d"), "qtr": (pe.month - 1) // 3 + 1, "year": pe.year,
            "t_n": t_n.strftime("%Y-%m-%d"), "pit_q": pit_q.strftime("%Y-%m-%d"),
            "window_tdays": _tdays_between(cal, t_n, pit_q),
            "est": est, "est_sumratio": est_sum, "est_impl": est_impl,
            "actual": float(actual), "eps_ly": float(eps_ly) if np.isfinite(eps_ly) else np.nan,
            "eps_lq": float(eps1) if np.isfinite(eps1) else np.nan,
            "has_bs": bool(np.isfinite(shares)), "scale": scale, "par_ratio": (shares / implied_shares) if np.isfinite(shares) and np.isfinite(implied_shares) and implied_shares > 0 else np.nan,
        })
    return rows


def _corr(a: np.ndarray, b: np.ndarray) -> dict:
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < 10:
        return {"n": int(len(a))}
    lo_a, hi_a = np.percentile(a, [1, 99])
    lo_b, hi_b = np.percentile(b, [1, 99])
    return {
        "n": int(len(a)),
        "spearman": round(float(spearmanr(a, b)[0]), 4),
        "pearson_winsor1_99": round(float(pearsonr(np.clip(a, lo_a, hi_a), np.clip(b, lo_b, hi_b))[0]), 4),
    }


def _hit(pred_delta: np.ndarray, act_delta: np.ndarray) -> dict:
    ok = np.isfinite(pred_delta) & np.isfinite(act_delta) & (pred_delta != 0) & (act_delta != 0)
    p, a = pred_delta[ok], act_delta[ok]
    if len(p) == 0:
        return {"n": 0}
    return {
        "n": int(len(p)),
        "hit_rate": round(float((np.sign(p) == np.sign(a)).mean()), 4),
        "base_rate_actual_up": round(float((a > 0).mean()), 4),
    }


def _err(e: np.ndarray, scale: np.ndarray) -> dict:
    ok = np.isfinite(e)
    e, s = e[ok], scale[ok]
    qs = np.percentile(e, [5, 25, 50, 75, 95])
    ne = e / s
    nq = np.percentile(ne, [5, 25, 50, 75, 95])
    return {
        "n": int(len(e)),
        "bias_mean": round(float(e.mean()), 4),
        "MAE": round(float(np.abs(e).mean()), 4),
        "MedAE": round(float(np.median(np.abs(e))), 4),
        "err_q05_25_50_75_95": [round(float(x), 4) for x in qs],
        "norm_err_q05_25_50_75_95": [round(float(x), 4) for x in nq],
        "share_abs_norm_err_le_0.25": round(float((np.abs(ne) <= 0.25).mean()), 4),
        "share_abs_norm_err_le_0.5": round(float((np.abs(ne) <= 0.5).mean()), 4),
    }


def _block(df: pd.DataFrame) -> dict:
    est, act, ly = df["est"].to_numpy(), df["actual"].to_numpy(), df["eps_ly"].to_numpy()
    naive = ly  # 季節性 naive：去年同季 EPS
    d_est, d_act = est - ly, act - ly
    d_naive_prev = df["eps_lq"].to_numpy() - ly  # 對照：用上一季相對去年同季的方向猜這一季
    return {
        "n_stock_quarters": int(len(df)),
        "level_corr_est_vs_actual": _corr(est, act),
        "level_corr_seasonal_naive_vs_actual": _corr(naive, act),
        "yoy_change_corr(est-EPS_ly vs actual-EPS_ly)": _corr(d_est, d_act),
        "direction_hit(est vs EPS_ly)": _hit(d_est, d_act),
        "direction_hit_baseline(上一季YoY方向延續)": _hit(d_naive_prev, d_act),
        "sign_profit_hit": {
            "hit_rate": round(float(((est > 0) == (act > 0)).mean()), 4),
            "base_rate_actual_positive": round(float((act > 0).mean()), 4),
        },
        "error_est_minus_actual": _err(est - act, df["scale"].to_numpy()),
        "error_seasonal_naive_minus_actual": _err(naive - act, df["scale"].to_numpy()),
    }


def _paired_hit_increment(d: pd.DataFrame, n_boot: int = 2000, seed: int = 20260929) -> dict:
    """驗.九二.2：同一批股票-季上，est 方向命中率 − naive(上一季YoY方向延續) 命中率，
    以股票為單位的 cluster bootstrap 95%CI。另附「永遠猜多數方向」基準（用同批列自身多數方向，偏樂觀的上限基準）。"""
    x = d[["sid", "est_", "eps_ly", "eps_lq", "actual"]].copy()
    x["p_est"] = x["est_"] - x["eps_ly"]
    x["p_nv"] = x["eps_lq"] - x["eps_ly"]
    x["a"] = x["actual"] - x["eps_ly"]
    x = x[np.isfinite(x[["p_est", "p_nv", "a"]]).all(axis=1) & (x["p_est"] != 0) & (x["p_nv"] != 0) & (x["a"] != 0)]
    if len(x) < 30:
        return {"n": int(len(x))}
    x["h_est"] = (np.sign(x["p_est"]) == np.sign(x["a"])).astype(float)
    x["h_nv"] = (np.sign(x["p_nv"]) == np.sign(x["a"])).astype(float)
    x["up"] = (x["a"] > 0).astype(float)
    g = x.groupby("sid").agg(n=("a", "size"), he=("h_est", "sum"), hn=("h_nv", "sum"), up=("up", "sum"))
    n, he, hn, up = (g[c].to_numpy() for c in ("n", "he", "hn", "up"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), size=(n_boot, len(g)))
    N = n[idx].sum(1)
    d_nv = he[idx].sum(1) / N - hn[idx].sum(1) / N
    up_r = up[idx].sum(1) / N
    d_maj = he[idx].sum(1) / N - np.maximum(up_r, 1 - up_r)
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    hr_e, hr_n, base = he.sum() / n.sum(), hn.sum() / n.sum(), up.sum() / n.sum()
    return {
        "n_stock_quarters": int(n.sum()), "n_stocks_clusters": int(len(g)),
        "hit_est": round(float(hr_e), 4), "hit_naive_prevQ_yoy_dir": round(float(hr_n), 4),
        "increment_vs_naive": round(float(hr_e - hr_n), 4), "increment_vs_naive_ci95_cluster_boot": ci(d_nv),
        "ci_excludes_zero_vs_naive": bool(ci(d_nv)[0] > 0 or ci(d_nv)[1] < 0),
        "base_rate_actual_up": round(float(base), 4),
        "increment_vs_majority_direction": round(float(hr_e - max(base, 1 - base)), 4),
        "increment_vs_majority_ci95_cluster_boot": ci(d_maj),
        "boot": {"n_boot": n_boot, "seed": seed, "unit": "stock(cluster)"},
    }


def _xs_ic(df: pd.DataFrame, x: str, y: str, min_n: int = 15) -> dict:
    ics = []
    for _, g in df.groupby("pe"):
        g = g[[x, y]].dropna()
        if len(g) >= min_n:
            ics.append(float(spearmanr(g[x], g[y])[0]))
    if not ics:
        return {"n_quarters": 0}
    a = np.array(ics)
    return {"n_quarters": int(len(a)), "mean_spearman": round(float(a.mean()), 4),
            "share_positive": round(float((a > 0).mean()), 4), "min": round(float(a.min()), 4)}


def main() -> None:
    ids = fic.sample_universe_ids(300, 20260822)
    print(f"[析.二] 樣本{len(ids)}檔，載入中...")
    cal = _calendar()
    rows: list[dict] = []
    used = 0
    for i, sid in enumerate(ids, 1):
        try:
            r = _stock_rows(sid, cal)
        except Exception as e:  # noqa: BLE001
            print(f"  {sid} 略過：{type(e).__name__}: {e}")
            r = []
        if r:
            used += 1
            rows.extend(r)
        if i % 50 == 0:
            print(f"  {i}/{len(ids)}")
    df = pd.DataFrame(rows)
    print(f"可用股票 {used} 檔，股票-季 {len(df)} 筆（其中有 BalanceSheet 股本者 {int(df['has_bs'].sum())} 筆）")
    df["d_act"] = df["actual"] - df["eps_ly"]

    def report(d: pd.DataFrame, col: str) -> dict:
        d = d.copy()
        d["est_"] = d[col]
        d = d[np.isfinite(d["est_"])].copy()
        d["d_est"] = d["est_"] - d["eps_ly"]
        dd = d.assign(est=d["est_"])
        return {
            "n_stocks": int(d["sid"].nunique()),
            "n_stock_quarters": int(len(d)),
            "pooled": _block(dd),
            "by_quarter_of_year": {f"Q{k}": _block(g) for k, g in dd.groupby("qtr")},
            "q1q3_vs_q4": {
                "Q1-Q3": {"pooled": _block(dd[dd["qtr"] <= 3]), "hit_increment": _paired_hit_increment(dd[dd["qtr"] <= 3])},
                "Q4": {"pooled": _block(dd[dd["qtr"] == 4]), "hit_increment": _paired_hit_increment(dd[dd["qtr"] == 4])},
                "all": {"hit_increment": _paired_hit_increment(dd)},
            },
            "by_year": {str(k): {"n": int(len(g)), "level_spearman": _corr(g["est"].to_numpy(), g["actual"].to_numpy()).get("spearman"),
                                 "direction_hit": _hit(g["d_est"].to_numpy(), g["d_act"].to_numpy()).get("hit_rate")}
                        for k, g in dd.groupby("year")},
            "cross_sectional_by_quarter": {
                "est_vs_actual_level": _xs_ic(dd, "est", "actual"),
                "est_minus_EPSly_vs_actual_minus_EPSly": _xs_ic(dd.assign(d_est=dd["d_est"]), "d_est", "d_act"),
                "seasonal_naive_level_baseline": _xs_ic(dd, "eps_ly", "actual"),
            },
        }

    bs = df[df["has_bs"]]
    out: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict_locked_note": "可行性前置診斷，不是試驗、不含任何報酬回測、不登記TRIALS_REGISTRY、不改任何既有判定（凍結.二仍生效）。",
        "sample": {"n_stocks_requested": len(ids), "n_stocks_used_any": used,
                   "n_stock_quarters_all": int(len(df)), "n_stock_quarters_with_balance_sheet": int(len(bs)),
                   "eval_quarters": f"{df['pe'].min()}..{df['pe'].max()}", "holdout_guard": f"評估季 pit_date <= {holdout.VAL_END}",
                   "note": "FinMind 免費額度於本次執行中觸發 402 冷卻，BalanceSheet 只有已快取的子集可用；"
                           "A 版（面額10股本，裁示公式）只能跑在該子集，B 版（隱含股數）跑在全部可用樣本。"},
        "formula_A": "est_EPS = 該季三個月月營收(PIT)加總 × 前4季歸屬母公司淨利率簡單平均 ÷ (前一季CapitalStock/面額10)；僅 BalanceSheet 已快取子集",
        "formula_B": "同上，但股數＝前一季歸屬淨利÷前一季EPS（隱含股數，不需 BalanceSheet）；全部可用樣本",
        "A_par10_shares_subset": report(bs, "est"),
        "B_implied_shares_full": report(df, "est_impl"),
        "sensitivity_on_A_subset": {
            "margin_ratio_of_sums": {"level_corr": _corr(bs["est_sumratio"].to_numpy(), bs["actual"].to_numpy()),
                                     "direction_hit": _hit((bs["est_sumratio"] - bs["eps_ly"]).to_numpy(), bs["d_act"].to_numpy())},
            "par10_share_ratio_vs_implied": {
                "median": round(float(bs["par_ratio"].median()), 4),
                "share_within_10pct": round(float(((bs["par_ratio"] - 1).abs() <= 0.10).mean()), 4),
                "share_within_25pct": round(float(((bs["par_ratio"] - 1).abs() <= 0.25).mean()), 4)},
        },
        "tradeable_window_tdays": {
            "definition": "(T_n=第3個月營收公布日, 季報法定截止日] 內的交易日數；法定截止日≥實際公告日，故為窗口上限",
            "overall": {"mean": round(float(df["window_tdays"].mean()), 2), "median": float(df["window_tdays"].median()),
                        "p10": float(df["window_tdays"].quantile(0.1)), "p90": float(df["window_tdays"].quantile(0.9))},
            "by_quarter_of_year": {f"Q{k}": {"mean": round(float(g["window_tdays"].mean()), 2), "median": float(g["window_tdays"].median()),
                                             "n": int(len(g))} for k, g in df.groupby("qtr")},
            "by_year_quarter_mean": {f"{y}Q{q}": round(float(g["window_tdays"].mean()), 1) for (y, q), g in df.groupby(["year", "qtr"])},
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT}")


if __name__ == "__main__":
    main()
