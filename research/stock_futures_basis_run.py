"""補.研究-個股期貨基差 單發本體（TRIALS #460，PREREG docs/PREREG_STOCK_FUTURES_BASIS_FINAL.md 第 3～4 節＋附錄 A）。

由 `stock_futures_basis_oneshot.py --run` 呼叫 run_oneshot()；結果檔存在即拒跑（呼叫端檢查）。
自測：python research/stock_futures_basis_run.py --selftest（假資料，不讀真資料、不寫結果檔）。

實作上的 [自行裁量]（看結果前寫）：
- 組報酬：現貨 t+1 收盤買（含滑價）、T 收盤賣（含滑價）；期貨 t+1 收盤賣（含滑價）、T 以現貨收盤結算（附錄 A-1，不收滑價）；
  現貨領 (t+1, T] 除息的現金股利；成本＝現貨手續費兩邊＋證交稅賣邊＋期貨稅兩邊＋期貨手續費兩邊＋滑價；
  分母＝現貨金額＋期貨保證金（13.5%×期貨金額）。成本倍數乘在全部成本（含滑價）上。
- t+1 期貨收盤缺（沒成交）→ 該候選無法以 t+1 收盤成交，排除並列數。
- 淨值（天條一、第 8 關）：M 個等權槽位，每槽每日報酬＝該部位當日盯市損益／該部位本金（期貨用每日結算價盯市，
  最後一天以現貨收盤結算）；空槽報酬 0（保守，不算現金利息）；每日等權複利。月頻超額＝月報酬－1.0%/12。
- 隨機時點控制組：每一組實際交易，在同一契約符合 τ／OI／有成交／未鎖漲停的日子裡隨機抽一天進場（1,000 次，種子 20261022），
  不套 M 上限，統計量＝平均超額報酬（1× 成本）。
非投資建議。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

Q = 2000
R_MAIN = 0.010
K_MAIN, TMIN_MAIN, OI_MIN, M_MAX = 0.010, 10, 100, 20
GRID_K = (0.007, 0.010, 0.013)
GRID_T = (7, 10, 13)
MARGIN_MAIN = 0.135
FUT_TAX = 0.00002
FUT_FEE = 80.0
N_RAND, SEED = 1000, 20261022
HALF_SPLIT = pd.Timestamp("2018-01-01")


def _costs():
    from validation.costs import COMMISSION_RATE, DEFAULT_SLIPPAGE_BPS, tax_rate
    return COMMISSION_RATE, DEFAULT_SLIPPAGE_BPS / 1e4, tax_rate("normal")


def trade_returns(c: pd.DataFrame, cost_mult=1.0, r=R_MAIN, margin=MARGIN_MAIN, settle_bias=0.0,
                  comm=None, slip=None, stax=None) -> pd.DataFrame:
    """c 需要欄位 S1（現貨 t+1 收盤）、F1（期貨 t+1 收盤）、ST（現貨 T 收盤）、div（(t+1,T] 現金股利）、t1、T。"""
    if comm is None:
        comm, slip, stax = _costs()
    S1, F1, ST, dv = c["S1"].values, c["F1"].values, c["ST"].values, c["div"].values
    FT = ST * (1 + settle_bias)
    gross = Q * (ST - S1) + Q * (F1 - FT) + Q * dv
    cost = (comm * Q * (S1 + ST) + stax * Q * ST + FUT_TAX * Q * (F1 + FT) + 2 * FUT_FEE
            + slip * Q * (S1 + ST + F1))
    cap = Q * S1 + margin * Q * F1
    ret = (gross - cost_mult * cost) / cap
    days = (c["T"] - c["t1"]).dt.days.values
    out = c[["code", "ym", "t1", "T"]].copy()
    out["ret"] = ret
    out["excess"] = ret - r * days / 365.0
    out["cap"] = cap
    out["net_ntd"] = gross - cost_mult * cost
    return out


def select(el: pd.DataFrame, k: float, tmin: int, m_max=M_MAX) -> pd.DataFrame:
    """PREREG §3-3：m≥k、n_td≥tmin；每個進場日依 m 由大到小補滿 M 槽；同契約只進一次。"""
    c = el[(el["m"] >= k) & (el["n_td"] >= tmin)].sort_values(["t1", "m"], ascending=[True, False])
    taken, open_T, rows = set(), [], []
    for t1, g in c.groupby("t1", sort=True):
        open_T = [x for x in open_T if x > t1]  # T 當天收盤結算 → 當天即釋放
        free = m_max - len(open_T)
        if free <= 0:
            continue
        for idx, row in zip(g.index, g[["code", "ym", "T"]].itertuples(index=False)):
            if free <= 0:
                break
            key = (row.code, row.ym)
            if key in taken:
                continue
            taken.add(key)
            open_T.append(row.T)
            rows.append(idx)
            free -= 1
    return el.loc[rows]


def nav_series(trades: pd.DataFrame, spot_px: dict, fut_px: dict, tdays, comm, slip, stax, m_max=M_MAX):
    """每日等權 M 槽淨值。spot_px[sid]：日期→收盤；fut_px[(code,ym)]：日期→結算價。"""
    tdays = pd.DatetimeIndex(tdays)
    pos = {d: i for i, d in enumerate(tdays)}
    daily = np.zeros(len(tdays))
    for tr in trades.itertuples(index=False):
        i0, i1 = pos[tr.t1], pos[tr.T]
        cap = Q * tr.S1 + MARGIN_MAIN * Q * tr.F1
        sp, fp = spot_px[tr.sid], fut_px[(tr.code, tr.ym)]
        prev_s, prev_f = tr.S1 * (1 + slip), tr.F1 * (1 - slip)
        pnl0 = -comm * Q * tr.S1 - FUT_TAX * Q * tr.F1 - FUT_FEE
        daily[i0] += (pnl0 + Q * (tr.S1 - prev_s) + Q * (prev_f - tr.F1)) / cap / m_max
        prev_s, prev_f = tr.S1, tr.F1
        divmap = tr.divmap
        for i in range(i0 + 1, i1 + 1):
            d = tdays[i]
            s = sp.get(d, prev_s)
            f = s if i == i1 else fp.get(d, prev_f)
            pnl = Q * (s - prev_s) + Q * (prev_f - f) + Q * divmap.get(d, 0.0)
            if i == i1:
                pnl -= comm * Q * s + stax * Q * s + slip * Q * s + FUT_TAX * Q * s + FUT_FEE
            daily[i] += pnl / cap / m_max
            prev_s, prev_f = s, f
    nav = pd.Series(np.cumprod(1 + daily), index=tdays)
    return nav


def mdd(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def sharpe_monthly(mret: pd.Series):
    x = mret.dropna()
    sd = x.std(ddof=1)
    return (float(x.mean() / sd) if sd > 0 else float("nan")), len(x), float(x.skew()), float(x.kurt() + 3)


def tw0050_monthly(end="2024-12-31", start="2010-01-25") -> pd.Series:
    raw = ROOT / "research" / "data" / "raw"
    p = pd.read_parquet(raw / "TaiwanStockPrice__0050__2003-01-01__2024-12-31.parquet")[["date", "close"]]
    p["date"] = pd.to_datetime(p["date"])
    p = p[(p["close"] > 0) & (p["date"] <= end)].drop_duplicates("date").set_index("date")["close"].sort_index()
    d = pd.read_parquet(raw / "TaiwanStockDividend__0050__2003-01-01__2024-12-31.parquet")
    dv = {}
    for _, rr in d.iterrows():
        ex, cash = rr.get("CashExDividendTradingDate"), float(rr.get("CashEarningsDistribution") or 0)
        if ex and cash > 0:
            dv[pd.Timestamp(ex)] = dv.get(pd.Timestamp(ex), 0.0) + cash
    divs = pd.Series(dv).reindex(p.index).fillna(0.0)
    tr = (p + divs) / p.shift(1) - 1
    tr = tr[tr.index >= start]
    return (1 + tr.fillna(0)).resample("ME").prod() - 1


def _attach(el, fut, spots, divs):
    """補 F1、期貨 t+1 成交量、ST、(t+1,T] 現金股利、分日股利表。"""
    fk = fut[["code", "ym", "date", "close", "vol"]].rename(columns={"date": "t1", "close": "F1", "vol": "vol1"})
    el = el.merge(fk, on=["code", "ym", "t1"], how="left")
    st = pd.concat([s[["close"]].reset_index().assign(sid=k) for k, s in spots.items()], ignore_index=True)
    st = st.rename(columns={"date": "T", "close": "ST"})
    el = el.merge(st, on=["sid", "T"], how="left")
    dsum, dmaps = [], []
    for r in el[["sid", "t1", "T"]].itertuples(index=False):
        cash = divs[r.sid][0]
        mp = {}
        for ex, ann, cv in cash:
            if r.t1 < ex <= r.T:
                mp[ex] = mp.get(ex, 0.0) + cv
        dmaps.append(mp)
        dsum.append(sum(mp.values()))
    el["div"] = dsum
    el["divmap"] = dmaps
    return el


def run_oneshot(fut, cands, spots, divs, tdays, tidx, result_out: Path) -> int:
    from trial_registry import register_trial
    from validation.holdout import assert_no_holdout_leakage
    comm, slip, stax = _costs()
    excl = {}
    base = cands[(cands["oi"] >= OI_MIN) & (cands["vol"] > 0) & cands["F"].notna() & ~cands["locked"]].copy()
    base = base[base["n_td"] >= min(GRID_T)]
    base["Fstar"] = base["S"] * (1 + R_MAIN * base["tau"] / 365.0) - base["D"]
    base["m"] = (base["F"] - base["Fstar"]) / base["S"]
    base = _attach(base, fut, spots, divs)
    miss = base["F1"].isna() | base["ST"].isna()
    excl["t+1 期貨無收盤（沒成交）或結算日現貨缺"] = int(miss.sum())
    base = base[~miss].reset_index(drop=True)
    assert_no_holdout_leakage(base.rename(columns={"T": "date"})[["date"]], date_col="date", context="basis trades")
    tr1 = trade_returns(base, 1.0, comm=comm, slip=slip, stax=stax)
    base["ret1"], base["exc1"], base["net1"] = tr1["ret"].values, tr1["excess"].values, tr1["net_ntd"].values

    main_sel = select(base, K_MAIN, TMIN_MAIN)
    n = len(main_sel)
    res = {"generated_at": datetime.now().isoformat(timespec="seconds"), "trial": 460,
           "excluded_at_run": excl, "eligible_rows_tmin7": int(len(base)), "n_trades": n,
           "assumptions": "保證金 13.5%、期貨稅十萬分之二、手續費 NT$80／口／邊皆為保守假設（歷史官方值本輪未查到）；"
                          "期貨以標的最後交易日收盤結算（附錄 A-1）"}
    gates = {}
    # 天條一
    spot_px = {k: s["close"] for k, s in spots.items()}
    fut_px = {}
    for (c_, y_), g in fut[fut.set_index(["code", "ym"]).index.isin(list(zip(main_sel["code"], main_sel["ym"])))].groupby(["code", "ym"]):
        fut_px[(c_, y_)] = g.set_index("date")["settle"].dropna().to_dict()
    spot_d = {k: v.to_dict() for k, v in spot_px.items() if k in set(main_sel["sid"])}
    nav = nav_series(main_sel, spot_d, fut_px, tdays, comm, slip, stax)
    res["mdd"] = mdd(nav)
    gates["天條一 MDD≤50%"] = res["mdd"] >= -0.50
    res["trade_mdd_note"] = "淨值＝M=20 等權槽、空槽 0 報酬"
    # 交易數
    gates["交易數≥100"] = n >= 100
    # 主檢定＋隨機時點
    mean1 = float(main_sel["exc1"].mean()) if n else float("nan")
    res["mean_excess_1x"] = mean1
    res["mean_ret_1x"] = float(main_sel["ret1"].mean()) if n else float("nan")
    res["hit_rate_1x"] = float((main_sel["exc1"] > 0).mean()) if n else float("nan")
    elig_main = base[base["n_td"] >= TMIN_MAIN]
    pools = {k: g["exc1"].values for k, g in elig_main.groupby(["code", "ym"])}
    rng = np.random.default_rng(SEED)
    keys = list(zip(main_sel["code"], main_sel["ym"]))
    tot = np.zeros(N_RAND)
    for k in keys:
        pl = pools[k]
        tot += pl[rng.integers(0, len(pl), N_RAND)]
    rand_means = tot / n if n else np.array([])
    p95 = float(np.percentile(rand_means, 95)) if n else float("nan")
    res["random_timing"] = {"n": N_RAND, "p50": float(np.median(rand_means)) if n else None, "p95": p95,
                            "max": float(rand_means.max()) if n else None,
                            "pct_rank_of_main": float((rand_means < mean1).mean()) if n else None}
    gates["主檢定 超額>0 且 >隨機 P95"] = bool(n and mean1 > 0 and mean1 > p95)
    # 成本
    for cm in (2.0, 3.0):
        t = trade_returns(main_sel, cm, comm=comm, slip=slip, stax=stax)
        res[f"mean_excess_{int(cm)}x"] = float(t["excess"].mean()) if n else float("nan")
    gates["成本 2×3× 仍>0"] = bool(n and res["mean_excess_2x"] > 0 and res["mean_excess_3x"] > 0)
    # 兩半
    h1 = main_sel[main_sel["t1"] < HALF_SPLIT]
    h2 = main_sel[main_sel["t1"] >= HALF_SPLIT]
    res["halves"] = {"2010_2017": {"n": len(h1), "mean_excess_1x": float(h1["exc1"].mean()) if len(h1) else None},
                     "2018_2024": {"n": len(h2), "mean_excess_1x": float(h2["exc1"].mean()) if len(h2) else None}}
    if len(h1) < 30:
        gates["兩半一致"] = None  # INCONCLUSIVE（§5-6），整體不得 PASS
    else:
        gates["兩半一致"] = bool(len(h2) and h1["exc1"].mean() > 0 and h2["exc1"].mean() > 0)
    # 高原 9 格
    grid = {}
    for k in GRID_K:
        for tm in GRID_T:
            s = select(base, k, tm)
            grid[f"k={k:.3f},T={tm}"] = {"n": len(s), "mean_excess_1x": float(s["exc1"].mean()) if len(s) else None}
    res["plateau_grid"] = grid
    npos = sum(1 for v in grid.values() if v["mean_excess_1x"] is not None and v["mean_excess_1x"] > 0)
    res["plateau_positive_cells"] = npos
    gates["高原 ≥7/9"] = npos >= 7
    # 第 8 關等價替代
    mret = nav.resample("ME").last().pct_change()
    mret.iloc[0] = nav.resample("ME").last().iloc[0] - 1
    mexc = mret - R_MAIN / 12
    sr, nobs, sk, ku = sharpe_monthly(mexc)
    b = tw0050_monthly() - R_MAIN / 12
    srb = sharpe_monthly(b)[0]
    res["sharpe_monthly_excess"] = {"strategy": sr, "0050_total_return": srb,
                                    "strategy_annualized": sr * math.sqrt(12), "0050_annualized": srb * math.sqrt(12),
                                    "n_months": nobs}
    gates["第8關替代 超額Sharpe>0050含息Sharpe"] = bool(sr > srb)
    # 敏感度（不當關卡）
    sens = {}
    for rr in (0.005, 0.015):
        sens[f"r={rr}"] = float(trade_returns(main_sel, 1.0, r=rr, comm=comm, slip=slip, stax=stax)["excess"].mean()) if n else None
    for mg in (0.10, 0.20):
        sens[f"margin={mg}"] = float(trade_returns(main_sel, 1.0, margin=mg, comm=comm, slip=slip, stax=stax)["excess"].mean()) if n else None
    for sb in (-0.003, 0.003):
        sens[f"settle_bias={sb:+}"] = float(trade_returns(main_sel, 1.0, settle_bias=sb, comm=comm, slip=slip, stax=stax)["excess"].mean()) if n else None
    res["sensitivity_mean_excess_1x"] = sens
    # 容量
    cap = main_sel.assign(lots=np.floor(0.1 * main_sel["vol1"].fillna(0)), y=main_sel["t1"].dt.year)
    cap["ntd"] = cap["lots"] * cap["net1"]
    res["capacity_by_year"] = {int(y): {"lots": int(g["lots"].sum()), "net_ntd_1x": float(g["ntd"].sum())}
                               for y, g in cap.groupby("y")}
    res["trades_by_year"] = {int(y): int(c) for y, c in main_sel["t1"].dt.year.value_counts().sort_index().items()}
    res["gates"] = gates
    # 判定
    order = list(gates)
    if not gates["天條一 MDD≤50%"]:
        verdict, fg = "VIOLATES_SURVIVAL", None
    elif not gates["交易數≥100"]:
        verdict, fg = "未結案", None
    else:
        fails = [g for g in order[2:] if gates[g] is False]
        gmap = {"主檢定 超額>0 且 >隨機 P95": "gate5", "成本 2×3× 仍>0": "gate4", "高原 ≥7/9": "gate3",
                "第8關替代 超額Sharpe>0050含息Sharpe": "gate2", "兩半一致": "unknown"}
        if fails:
            verdict, fg = "FAIL", sorted({gmap[g] for g in fails})
        elif gates["兩半一致"] is None:
            verdict, fg = "未結案", None
        else:
            verdict, fg = "PASS", None
    res["verdict"] = verdict
    res["failed_gates"] = fg
    result_out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    summary = (f"交易 {n} 組；1× 平均超額 {mean1:+.4%}（隨機時點 P95 {p95:+.4%}）；2×/3× "
               f"{res['mean_excess_2x']:+.4%}/{res['mean_excess_3x']:+.4%}；MDD {res['mdd']:.2%}；"
               f"兩半 {res['halves']}；高原 {npos}/9 格>0；月超額 Sharpe {sr:.3f} vs 0050含息 {srb:.3f}；"
               f"關卡 {gates}")
    tid, _ = register_trial(
        track="FUT", name="stock_futures_basis_oneshot",
        design="個股期貨基差偏離單發（同 #460 事前登記，PREREG docs/PREREG_STOCK_FUTURES_BASIS_FINAL.md＋附錄 A）",
        result=summary, verdict=verdict,
        notes=("只做期貨偏貴一邊，無放空現貨腿；期貨以標的最後交易日收盤結算（歷史最後結算價查不到，附錄 A-1）；"
               "保證金／期貨稅／手續費為保守假設；與 fut_basis_carry（#35／#37）同家族、結果並列。結果檔 "
               "research/data/stock_futures_basis_oneshot_result.json。非投資建議。"),
        round_note="DevQueue 單發（驗證帽），非馬拉松輪次",
        sharpe=sr, n_obs=nobs, skew=sk, kurtosis=ku, periods_per_year=12,
        failed_gates=fg, code_paths=["research/stock_futures_basis_run.py", "research/stock_futures_basis_oneshot.py"],
    )
    print(f"已登記 #{tid}：{verdict}")
    return 0


def _selftest() -> int:
    comm, slip, stax = 0.001425, 0.0005, 0.003
    t1, T = pd.Timestamp("2015-01-05"), pd.Timestamp("2015-01-21")
    c = pd.DataFrame({"code": ["XXF"], "ym": ["201501"], "t1": [t1], "T": [T], "S1": [100.0], "F1": [102.0],
                      "ST": [100.0], "div": [0.0]})
    r = trade_returns(c, 1.0, comm=comm, slip=slip, stax=stax).iloc[0]
    gross = 2000 * 2.0
    cost = comm * 2000 * 200 + stax * 2000 * 100 + FUT_TAX * 2000 * 202 + 160 + slip * 2000 * 302
    exp = (gross - cost) / (2000 * 100 + 0.135 * 2000 * 102)
    assert abs(r["ret"] - exp) < 1e-12, (r["ret"], exp)
    assert abs(r["excess"] - (exp - 0.01 * 16 / 365)) < 1e-12
    # 現貨跌、期貨收斂：避險部位損益只剩錯價
    c2 = c.assign(ST=[80.0])
    r2 = trade_returns(c2, 0.0, comm=comm, slip=slip, stax=stax).iloc[0]
    assert abs(r2["ret"] * (2000 * 100 + 0.135 * 2000 * 102) - 4000) < 1e-6
    # 股利：現貨領息
    r3 = trade_returns(c.assign(div=[3.0]), 0.0, comm=comm, slip=slip, stax=stax).iloc[0]
    assert abs(r3["ret"] * (2000 * 100 + 0.135 * 2000 * 102) - 10000) < 1e-6
    # select：M 上限、同契約只進一次、到期當天釋放
    days = pd.bdate_range("2015-01-01", periods=10)
    el = pd.DataFrame({"code": ["A", "B", "C", "A"], "ym": ["1", "1", "1", "1"],
                       "t1": [days[0], days[0], days[1], days[2]], "T": [days[1], days[5], days[5], days[5]],
                       "m": [0.02, 0.03, 0.05, 0.04], "n_td": [10, 10, 10, 10]})
    s = select(el, 0.01, 10, m_max=2)
    assert list(s["code"]) == ["B", "A", "C"], list(s["code"])  # day0 取 B、A；day1 A 到期釋放→C；day2 A 已進過
    # 淨值：單筆無成本部位最後一天報酬＝錯價／本金／M
    tr = pd.DataFrame({"code": ["A"], "ym": ["1"], "sid": ["1111"], "t1": [days[0]], "T": [days[2]],
                       "S1": [100.0], "F1": [102.0], "divmap": [{}]})
    nav = nav_series(tr, {"1111": {days[1]: 101.0, days[2]: 100.0}}, {("A", "1"): {days[1]: 103.0}}, days,
                     0.0, 0.0, 0.0, m_max=1)
    exp_total = 1 + (4000 - 2 * FUT_FEE - FUT_TAX * 2000 * 202) / (200000 + 0.135 * 204000)
    assert abs(nav.iloc[-1] - exp_total) < 1e-3, (nav.iloc[-1], exp_total)
    assert abs(mdd(pd.Series([1, 2, 1, 3])) + 0.5) < 1e-12
    print("自測通過：trade_returns／select／nav_series／mdd")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print("請用 stock_futures_basis_oneshot.py --run 呼叫；自測用 --selftest")
    raise SystemExit(2)
