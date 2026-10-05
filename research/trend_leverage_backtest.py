# -*- coding: utf-8 -*-
"""先.二十二-三／四：趨勢槓桿兩案單發執行（T-A 美股 SPY／T-B 台股 0050）。

定義全部事前綁定於 docs/PREREG_trend_leverage_{US,TW}_FINAL.md（登記 #411／#412），
該兩檔已於執行前 commit＋push。**單發只跑一次；績效數字一律到 JSON 寫完後才印。**

用法：python research/trend_leverage_backtest.py --market us|tw
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

SEED = 20261006
N_CTRL = 200
MA = 200
LEV = 2.0
END = "2024-12-31"            # holdout 自 2025-01-01 起，一律不讀

CFG = {
    "us": {"start": "1994-01-01", "fee": 0.0095, "cost": 0.0005, "bench": "SPY",
           "prereg": "docs/PREREG_trend_leverage_US_FINAL.md",
           "out": "data/trend_leverage_us_result.json", "trial": 411},
    "tw": {"start": "2003-07-01", "fee": 0.0100, "cost": 0.0010, "bench": "0050",
           "prereg": "docs/PREREG_trend_leverage_TW_FINAL.md",
           "out": "data/trend_leverage_tw_result.json", "trial": 412},
}


def sha256_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ───────── 資料 ─────────
def load_us() -> pd.DataFrame:
    spy = pd.read_parquet(HERE / "data" / "us_benchmark_spy.parquet")
    rf = pd.read_parquet(HERE / "data" / "us_rf_dtb3.parquet")
    df = spy.merge(rf[["date", "dtb3_daily"]], on="date", how="left")
    df["rf_daily"] = df["dtb3_daily"].ffill().fillna(0.0)
    return df[["date", "adj_close", "rf_daily"]]


#: T-B 的 0050 還原價來源說明（**本次重跑的原因，必須保留**）
#: 事前登記寫「0050 還原價（research/adjust.py）」。該模組的 `adjusted_price_series()`
#: 預設走 yfinance，但 2026-10-06 實測對 0050 有兩個瑕疵：
#:   (a) 只回溯到 2009-01-02，不足以涵蓋登記的 2003-07 起算期間；
#:   (b) 2014-01-02 出現 −75.06% 的假跌幅（37.186 → 9.273，恰為 4 倍），
#:       `adjust.check_adjusted_series_anomalies()` 另命中 10 筆逾 7.5% 門檻的異常。
#: 用這份序列跑 2 倍槓桿會把淨值打成負數（首次執行即產生 NaN，**該次未讀取、
#: 未印出任何績效數字即作廢並刪除結果檔**，依既有慣例「績效印出前的失敗可修正後
#: 重跑並記錄」處理）。
#: 改走同一模組既有的 FinMind 還原路徑 `_finmind_adjusted_frame()`：5,304 筆、
#: 2003-06-30～2024-12-31、日報酬區間 −9.13%～+7.95%（合於台股 ±10% 漲跌幅），
#: 仍在事前登記所指的 research/adjust.py 之內，非更換資料源。
#: yfinance 路徑的瑕疵本身**不在本試驗範圍內修正**，另記於結果檔供後續處理。
TW_PRICE_SOURCE = "research/adjust.py::_finmind_adjusted_frame('0050')（yfinance 路徑有瑕疵，見程式註解）"


def load_tw() -> pd.DataFrame:
    import adjust
    px = adjust._finmind_adjusted_frame("0050", "2003-01-01")
    px = px[["date", "adj_close"]].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    px = px.dropna(subset=["adj_close"]).sort_values("date")
    rf = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rfm = {str(x["date"])[:7]: float(x["rf_rate_pct"]) for x in rf}
    px["rf_daily"] = [rfm.get(str(d)[:7], 0.0) / 100.0 / 252.0 for d in px["date"].dt.strftime("%Y-%m")]
    return px.reset_index(drop=True)


# ───────── 核心 ─────────
def run_strategy(df: pd.DataFrame, fee: float, cost: float, ma: int = MA,
                 lev: float = LEV, cost_mult: float = 1.0, signal: np.ndarray | None = None):
    """回傳 (策略日報酬, 基準日報酬, 部位陣列, 換倉次數)。

    訊號當日收盤算出，**次一交易日起**生效（position = signal.shift(1)），
    這是避免用當日收盤訊號賺當日報酬的未來函數。
    """
    px = df["adj_close"].to_numpy(float)
    rf = df["rf_daily"].to_numpy(float)
    bench = np.zeros(len(px))
    bench[1:] = px[1:] / px[:-1] - 1.0
    if signal is None:
        sma = pd.Series(px).rolling(ma).mean().to_numpy()
        sig = (px > sma).astype(float)
        sig[np.isnan(sma)] = 0.0
    else:
        sig = signal.astype(float)
    pos = np.zeros(len(px))
    pos[1:] = sig[:-1]                      # 次一交易日起生效
    lev_ret = lev * bench - (lev - 1.0) * rf - fee / 252.0
    ret = np.where(pos > 0, lev_ret, rf)
    switch = np.zeros(len(px), dtype=bool)
    switch[1:] = pos[1:] != pos[:-1]
    ret = ret - switch * cost * cost_mult
    return ret, bench, pos, int(switch.sum())


def mdd(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def longest_underwater(r: np.ndarray) -> int:
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    uw = eq < peak
    best = cur = 0
    for x in uw:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return int(best)


def sortino(r: np.ndarray, ppy: int = 252) -> float:
    d = r[r < 0]
    sd = d.std(ddof=1) if len(d) > 1 else np.nan
    if not sd or np.isnan(sd) or sd == 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(ppy))


def cagr(r: np.ndarray, dates) -> float:
    yrs = max((dates.iloc[-1] - dates.iloc[0]).days / 365.25, 1e-9)
    return float(np.prod(1.0 + r) ** (1 / yrs) - 1)


def worst_12m(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + r)
    n = 252
    if len(eq) <= n:
        return float(eq[-1] - 1)
    w = eq[n:] / eq[:-n] - 1.0
    return float(w.min())


def summarize(r: np.ndarray, b: np.ndarray, dates) -> dict:
    return {"total_ret": float(np.prod(1 + r) - 1), "cagr": cagr(r, dates), "mdd": mdd(r),
            "sortino": sortino(r), "longest_underwater_days": longest_underwater(r),
            "worst_12m": worst_12m(r),
            "bench_total_ret": float(np.prod(1 + b) - 1), "bench_cagr": cagr(b, dates),
            "bench_mdd": mdd(b), "bench_sortino": sortino(b),
            "sortino_diff": sortino(r) - sortino(b),
            "excess_total_ret": float(np.prod(1 + r) - np.prod(1 + b))}


def random_control(df, fee, cost, n_switch, frac_lev, k=N_CTRL):
    """同換倉次數、同持有 2 倍天數比例，隨機時點 200 條。"""
    rng = np.random.default_rng(SEED)
    n = len(df)
    out = []
    for _ in range(k):
        cuts = np.sort(rng.choice(np.arange(MA, n - 1), size=min(n_switch, n - MA - 2), replace=False))
        sig = np.zeros(n)
        state = 0.0
        prev = MA
        for c in cuts:
            sig[prev:c] = state
            state = 1.0 - state
            prev = c
        sig[prev:] = state
        # 調到目標持有比例：多退少補（隨機翻轉未達標的區段）
        cur = sig[MA:].mean()
        if cur < frac_lev:
            idx = np.flatnonzero(sig[MA:] == 0) + MA
            need = int((frac_lev - cur) * (n - MA))
            if len(idx) and need > 0:
                sig[rng.choice(idx, size=min(need, len(idx)), replace=False)] = 1.0
        elif cur > frac_lev:
            idx = np.flatnonzero(sig[MA:] == 1) + MA
            need = int((cur - frac_lev) * (n - MA))
            if len(idx) and need > 0:
                sig[rng.choice(idx, size=min(need, len(idx)), replace=False)] = 0.0
        r, _, _, _ = run_strategy(df, fee, cost, signal=sig)
        out.append(sortino(r))
    return np.array([x for x in out if not np.isnan(x)])


def main() -> int:
    mk = sys.argv[sys.argv.index("--market") + 1] if "--market" in sys.argv else None
    if mk not in CFG:
        print("用法：--market us|tw")
        return 2
    c = CFG[mk]
    print(f"=== T-{'A' if mk == 'us' else 'B'} {c['bench']} 趨勢槓桿單發 ===", flush=True)
    df = (load_us() if mk == "us" else load_tw())
    df = df[(df["date"] >= c["start"]) & (df["date"] <= END)].reset_index(drop=True)
    assert df["date"].max() <= pd.Timestamp(END), "holdout 邊界違反"
    print(f"資料 {len(df)} 日：{df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}", flush=True)

    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "market": mk, "prereg": c["prereg"], "prereg_sha256": sha256_lf(ROOT / c["prereg"]),
           "prereg_trial_id": c["trial"], "seed": SEED, "holdout_note": "資料截至 2024-12-31，2025 起未讀取",
           "rules": {"ma": MA, "leverage": LEV, "annual_fee": c["fee"], "switch_cost_one_way": c["cost"]},
           "inputs": []}
    for p in (["data/us_benchmark_spy.parquet", "data/us_rf_dtb3.parquet"] if mk == "us" else []):
        f = HERE / p
        if f.exists():
            res["inputs"].append({"path": f"research/{p}", "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                  "size_bytes": f.stat().st_size})
    if mk == "tw":
        f = ROOT / "data" / "rf_monthly.json"
        res["inputs"].append({"path": "data/rf_monthly.json", "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                              "size_bytes": f.stat().st_size})
        res["inputs"].append({"path": TW_PRICE_SOURCE, "note": "函式輸出，非靜態檔"})
        res["tw_price_source_deviation"] = {
            "prereg_wording": "0050 還原價（research/adjust.py）",
            "actually_used": "research/adjust.py::_finmind_adjusted_frame('0050')",
            "reason": ("同模組預設的 adjusted_price_series() 走 yfinance，對 0050 有兩個瑕疵："
                       "(a) 只回溯到 2009-01-02，不足以涵蓋登記的 2003-07 起算期間；"
                       "(b) 2014-01-02 有 −75.06% 假跌幅（37.186→9.273，恰為 4 倍），"
                       "check_adjusted_series_anomalies() 另命中 10 筆逾 7.5% 門檻的異常。"
                       "以該序列跑 2 倍槓桿會把淨值打成負數。"),
            "first_run_voided": ("首次執行即產生 NaN，該次**未讀取、未印出任何績效數字**即作廢並刪除結果檔，"
                                 "依既有慣例『績效印出前的失敗可修正後重跑並記錄』處理；本檔為修正後的唯一一次有效執行。"),
            "why_still_within_prereg": "FinMind 路徑是同一個 research/adjust.py 模組既有的還原路徑，非更換資料源",
            "followup": "yfinance 路徑對 0050 的瑕疵不在本試驗範圍內修正，另行處理",
        }

    r, b, pos, nsw = run_strategy(df, c["fee"], c["cost"])
    S = summarize(r, b, df["date"])
    frac = float(pos[MA:].mean())
    res["main"] = S
    res["main"]["n_switches"] = nsw
    res["main"]["frac_days_levered"] = frac

    # 關1 天條一
    yrs = df["date"].dt.year.to_numpy()
    bear = {}
    for y in sorted(set(yrs)):
        m = yrs == y
        if mdd(b[m]) < -0.15:               # 以基準年度回撤 <-15% 認定為空頭年
            bear[int(y)] = {"strategy_mdd": mdd(r[m]), "bench_mdd": mdd(b[m])}
    res["gate1_survival"] = {"mdd_all": S["mdd"], "bear_years": bear,
                             "pass": bool(S["mdd"] > -0.5 and all(v["strategy_mdd"] > -0.5 for v in bear.values()))}
    # 關2 Sortino
    res["gate2_sortino"] = {"strategy": S["sortino"], "bench": S["bench_sortino"],
                            "diff": S["sortino_diff"], "pass": bool(S["sortino"] >= S["bench_sortino"])}
    # 關3 隨機擇時對照
    cs = random_control(df, c["fee"], c["cost"], nsw, frac)
    res["gate3_random_timing"] = {"k": int(len(cs)), "control_max": float(cs.max()),
                                  "control_mean": float(cs.mean()),
                                  "control_p95": float(np.percentile(cs, 95)),
                                  "strategy": S["sortino"],
                                  "n_exceeding": int((cs >= S["sortino"]).sum()),
                                  "percentile": float(100.0 * (cs < S["sortino"]).mean()),
                                  "pass": bool(S["sortino"] > cs.max())}
    # 關4 Bonferroni/DSR
    try:
        import candidate_report as CR
        import selection_bias_ledger as sbl
        from comparable_trial_variance import v_sensitivity_table
        n0, note = CR.default_n_trials()
        n_tr = n0 + 1
        sk = float(pd.Series(r).skew())
        ku = float(pd.Series(r).kurtosis())
        st = CR.CandidateStats(sharpe=float(r.mean() / r.std(ddof=1)), n_obs=len(r),
                               skew=sk, kurtosis=ku, periods_per_year=252, freq_label="日")
        scen = []
        V, nV = CR.trials_sharpe_variance(252)
        if V:
            d = CR.deflated_sharpe(st, n_tr, V)
            scen.append({"name": "帳本V(僅有Sharpe記錄者，必然低估)", "V": V, "V_samples": nV,
                         "dsr": d["dsr"], "pass": bool(d["dsr"] >= CR.DSR_MIN)})
        for row in v_sensitivity_table(n_tr):
            d = CR.deflated_sharpe(st, n_tr, row["v_daily"])
            scen.append({"name": f"年化SD={row['ann_sd']}", "V": row["v_daily"],
                         "dsr": d["dsr"], "pass": bool(d["dsr"] >= CR.DSR_MIN)})
        res["gate4_multiple_testing"] = {
            "n_trials": n_tr, "n_note": note,
            "bonferroni_required_percentile": float(sbl.required_percentile(n_tr)),
            "strategy_percentile": res["gate3_random_timing"]["percentile"],
            "bonferroni_pass": bool(res["gate3_random_timing"]["percentile"] >= sbl.required_percentile(n_tr)),
            "dsr_daily": scen, "all_v_pass": bool(scen and all(x["pass"] for x in scen)),
            "v_caveat": "V 為僅有 Sharpe 記錄者之離散度，非全體，必然低估，門檻偏鬆"}
    except Exception as e:  # noqa: BLE001
        res["gate4_multiple_testing"] = {"error": f"{type(e).__name__}: {e}",
                                         "bonferroni_pass": False, "all_v_pass": False}
    # 關5 成本
    costs = {}
    for m_ in (1.0, 2.0, 3.0):
        rr, bb, _, _ = run_strategy(df, c["fee"], c["cost"], cost_mult=m_)
        s2 = summarize(rr, bb, df["date"])
        costs[f"{m_:g}x"] = {k: s2[k] for k in ("total_ret", "cagr", "mdd", "sortino", "sortino_diff")}
        costs[f"{m_:g}x"]["survive"] = bool(s2["sortino"] >= s2["bench_sortino"] and s2["mdd"] > -0.5)
    res["gate5_costs"] = costs
    res["gate5_pass"] = all(v["survive"] for v in costs.values())
    # 關6 均線敏感度（只報告）
    ms = {}
    for m_ in (150, 250):
        rr, bb, _, nn = run_strategy(df, c["fee"], c["cost"], ma=m_)
        s2 = summarize(rr, bb, df["date"])
        ms[f"ma{m_}"] = {k: s2[k] for k in ("total_ret", "cagr", "mdd", "sortino", "sortino_diff")}
        ms[f"ma{m_}"]["n_switches"] = nn
    res["gate6_ma_sensitivity_report_only"] = ms
    # 關7 兩段
    half = len(df) // 2
    e1 = float(np.prod(1 + r[:half]) - np.prod(1 + b[:half]))
    e2 = float(np.prod(1 + r[half:]) - np.prod(1 + b[half:]))
    res["gate7_two_segments"] = {"first_half_excess": e1, "second_half_excess": e2,
                                 "split_date": str(df["date"].iloc[half].date()),
                                 "pass": bool((e1 > 0) == (e2 > 0))}
    # 逐年
    yr = {}
    for y in sorted(set(yrs)):
        m = yrs == y
        yr[int(y)] = {"strategy": float(np.prod(1 + r[m]) - 1), "bench": float(np.prod(1 + b[m]) - 1)}
        yr[int(y)]["excess"] = yr[int(y)]["strategy"] - yr[int(y)]["bench"]
    res["yearly"] = yr
    res["years_beating"] = int(sum(1 for v in yr.values() if v["excess"] > 0))
    res["years_total"] = len(yr)
    # 分批配置（只報告）
    alloc = {}
    for w in (0.10, 0.25, 0.50, 1.00):
        mix = w * r + (1 - w) * b
        alloc[f"{int(w * 100)}%"] = {"cagr": cagr(mix, df["date"]), "mdd": mdd(mix),
                                     "worst_12m": worst_12m(mix),
                                     "longest_underwater_days": longest_underwater(mix)}
    res["allocation_report_only"] = alloc

    # 判定
    order = [("gate1_survival", "天條一"), ("gate2_sortino", "Sortino≥基準"),
             ("gate3_random_timing", "隨機擇時對照"), ("gate4_multiple_testing", "Bonferroni/DSR"),
             ("gate5", "成本1x/2x/3x"), ("gate7_two_segments", "兩段同號")]
    verdict, failed = "PASS", None
    for k, nm in order:
        if k == "gate5":
            ok = res["gate5_pass"]
        elif k == "gate4_multiple_testing":
            ok = bool(res[k].get("bonferroni_pass"))
            if ok and not res[k].get("all_v_pass"):
                res["gate4_provisional"] = True
        else:
            ok = bool(res[k].get("pass"))
        if not ok:
            verdict = "VIOLATES_SURVIVAL" if k == "gate1_survival" else "FAIL"
            failed = (k, nm)
            break
    if verdict == "PASS" and res.get("gate4_provisional"):
        verdict = "PASS_PROVISIONAL(DSR 非所有V情境皆過)"
    res["verdict"] = verdict
    res["first_failed_gate"] = failed[0] if failed else None
    res["first_failed_gate_name"] = failed[1] if failed else None

    def conv(o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)

    (HERE / c["out"]).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=conv), encoding="utf-8")
    print(f"已寫入 research/{c['out']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
