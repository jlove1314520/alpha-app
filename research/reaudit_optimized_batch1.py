# -*- coding: utf-8 -*-
"""先.一五〇-1 墓園重審第一批（Cowork 收件匣 039 已定案）：歷史報酬最高的條目做「最優化版本」。

性質：**描述性的樣本內最優化**，不是判定（不寫 TRIALS_LEDGER；心跳寫 PROGRESS_HEARTBEAT.jsonl）。
資料：沿用 #418／#421 的 `leveraged_bb90_backtest.load_all()`（0050／VTI／IEF／現金，台幣計，已截至 2024-12-31），
     **不讀 2025-01-01 以後任何資料**（holdout 照舊不解鎖）。
回測規則（照實算）：
- 訊號只用當天收盤以前看得到的資料，隔一個交易日才生效（shift 1）。
- 槓桿＝每日再平衡合成：L×r − (L−1)×無風險利率 − 1%/年費用（L>1 才收），同 #421 公式；
  美股腿借款用美國 3 個月國庫券（#419 load_dtb3_annual），台股腿用台灣無風險利率（#421 load_tw_rf_daily）。
  權益跌破 0 視為歸零（之後報酬全為 0），保證金不足不會被「救回來」。
- 成本：每次調整部位，台股腿買賣各收 0.1% 滑價＋0.0855% 手續費（0.1425%×6 折），賣出另收 0.1% ETF 證交稅；
  美股腿收 0.3% 匯兌（#418 FX_COST）。
- 止損：策略淨值從持倉後高點回落超過 s 就全數退到現金，21 個交易日後才依訊號重新進場。
- 漲跌停／下市：本批全是 ETF／指數層級（0050、VTI），無個股下市問題；0050 單日跌停未實際發生於本期，未另建模。
綜合分數＝年化報酬 ÷ |最大回撤|（Calmar）；MDD 超過 50% 的組合標 VIOLATES_SURVIVAL（天條一）並排最後。
多重比較只當參考欄（掃描格數）。
"""
from __future__ import annotations

import itertools
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
ARGV = sys.argv[1:]
sys.argv = [sys.argv[0], "--formula", "421"]
import leveraged_bb90_backtest as LB  # noqa: E402
import core_allocation_backtest as CA  # noqa: E402

END = "2024-12-31"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch1.json"
CURVE_DIR = HERE / "data" / "reaudit_curves"
FEE_LEV = 0.01
SLIP = 0.001
BROKER = 0.001425 * 0.6
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


# ───────── 資料 ─────────
df, _fx = LB.load_all()
df = df[df["date"] <= END].reset_index(drop=True)
assert df["date"].max() <= pd.Timestamp(END)
DATES = df["date"]
N = len(df)
RF_TW = LB.load_tw_rf_daily(DATES)
RF_US = LB.load_dtb3_annual(DATES) / 252.0
R = {k: df[c].to_numpy(float) for k, c in
     [("0050", "r_0050"), ("VTI", "r_vti"), ("IEF", "r_ief"), ("CASH", "r_cash")]}
MONTH_END = (DATES.dt.to_period("M") != DATES.dt.to_period("M").shift(-1)).to_numpy()
PX = {k: np.cumprod(1.0 + R[k]) for k in ("0050", "VTI")}


def lev_ret(asset: str, L: float) -> np.ndarray:
    rf = RF_US if asset == "VTI" else RF_TW
    r = L * R[asset] - (L - 1.0) * rf
    if L > 1:
        r = r - FEE_LEV / 252.0
    return r


def side_cost(asset: str, dw: float) -> float:
    if asset in ("VTI", "IEF"):
        return abs(dw) * CA.FX_COST
    if asset == "CASH":
        return 0.0
    c = abs(dw) * (SLIP + BROKER)
    if dw < 0:
        c += abs(dw) * CA.TW_SELL_TAX
    return c


# ───────── 通用模擬：每日目標權重（已 shift） × 資產報酬 ─────────
def simulate(target: np.ndarray, assets: list[str], L: float, stop: float | None,
             monthly: bool) -> dict:
    """target：N×k 目標權重（第 i 列＝第 i 天開盤後持有的權重，已用前一天以前資訊決定）。
    monthly=True 時只在權重改變或月底再平衡（權重漂移）；False 時每天回到目標。"""
    rets = np.column_stack([lev_ret(a, L) if a in ("0050", "VTI") else R[a] for a in assets])
    k = len(assets)
    w = np.zeros(k)
    out = np.zeros(N)
    eq = 1.0
    peak = 1.0
    cool = 0
    trades = []          # (進場淨值, 出場淨值)
    in_pos = False
    entry_eq = 1.0
    risky = np.array([a in ("0050", "VTI") for a in assets])
    for i in range(N):
        t = target[i].copy()
        if cool > 0:
            cool -= 1
            moved = t[risky].sum()
            t = np.where(risky, 0.0, t)
            t[assets.index("CASH")] += moved
        rebalance = (not monthly) or i == 0 or MONTH_END[i - 1] or np.abs(t - target[i - 1]).sum() > 1e-12 or cool > 0
        cost = 0.0
        if rebalance:
            d = t - w
            cost = sum(side_cost(assets[j], d[j]) for j in range(k))
            w = t.copy()
        now_in = bool((w[risky] > 0).any())
        if now_in and not in_pos:
            entry_eq = eq
        if in_pos and not now_in:
            trades.append((entry_eq, eq))
        in_pos = now_in
        g = w * (1.0 + rets[i])
        tot = g.sum() if w.sum() > 0 else 1.0
        r = (tot - 1.0) - cost
        if eq <= 0:
            r = 0.0
        out[i] = r
        eq = max(eq * (1.0 + r), 0.0)
        w = g / tot if tot > 0 else w * 0
        if in_pos:
            peak = max(peak, eq)
        else:
            peak = eq
        if stop is not None and in_pos and eq < peak * (1.0 - stop):
            cool = COOLDOWN
            peak = eq
    if in_pos:
        trades.append((entry_eq, eq))
    return {"r": out, "trades": trades}


def metrics(res: dict) -> dict:
    r = res["r"]
    curve = np.cumprod(1.0 + r)
    yrs = (DATES.iloc[-1] - DATES.iloc[0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    sd = r.std(ddof=1)
    sharpe = float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    tr = res["trades"]
    n_tr = len(tr)
    win = float(np.mean([b > a for a, b in tr])) if n_tr else float("nan")
    return {"cagr": float(cagr), "mdd": mdd, "sharpe": sharpe, "trades": n_tr, "win_rate": win,
            "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
            "violates_survival": bool(mdd < -0.50)}


# ───────── 訊號 ─────────
def shift1(x):
    y = np.empty_like(x)
    y[0] = x[0]
    y[1:] = x[:-1]
    return y


def monthly_hold(sig_daily: np.ndarray) -> np.ndarray:
    """只在月底更新訊號，其餘日子沿用上個月底的值；再 shift 1（月底收盤決定、隔日生效）。"""
    out = np.empty_like(sig_daily)
    cur = sig_daily[0]
    for i in range(N):
        if MONTH_END[i]:
            cur = sig_daily[i]
        out[i] = cur
    return shift1(out)


def ma_signal(px, n):
    s = pd.Series(px).rolling(n, min_periods=n).mean().to_numpy()
    return np.where(np.isnan(s), 1.0, (px > s).astype(float))


def month_ma_signal(px, months):
    me_px = pd.Series(px[MONTH_END], index=np.flatnonzero(MONTH_END))
    ma = me_px.rolling(months, min_periods=months).mean()
    sig = np.ones(N)
    cur = 1.0
    me_set = dict(zip(me_px.index, (me_px > ma).where(ma.notna(), True).astype(float)))
    for i in range(N):
        if i in me_set:
            cur = me_set[i]
        sig[i] = cur
    return shift1(sig)


def month_mom_signal(px, months):
    me_idx = np.flatnonzero(MONTH_END)
    me_px = px[me_idx]
    sig = np.ones(N)
    cur = 1.0
    pos = {idx: j for j, idx in enumerate(me_idx)}
    for i in range(N):
        if i in pos:
            j = pos[i]
            cur = 1.0 if j < months else float(me_px[j] / me_px[j - months] - 1 > 0)
        sig[i] = cur
    return shift1(sig)


def vol_signal(r, win, k):
    v = pd.Series(r).rolling(win, min_periods=win).std()
    med = v.expanding(min_periods=252).median()
    hi = (v > med).to_numpy()
    e = np.where(med.isna().to_numpy(), 1.0, np.where(hi, k, 1.0))
    return shift1(e)


# ───────── 策略家族 ─────────
def alloc_target(eq_mix, w_eq, safe, gate=None):
    assets = ["0050", "VTI", "IEF", "CASH"]
    T = np.zeros((N, 4))
    g = np.ones(N) if gate is None else gate
    if eq_mix == "A":
        T[:, 0] = w_eq * g
    else:
        T[:, 0] = w_eq / 2 * g
        T[:, 1] = w_eq / 2 * g
    rest = 1.0 - T[:, 0] - T[:, 1]
    if safe == "CASH":
        T[:, 3] = rest
    elif safe == "IEF":
        T[:, 2] = rest
    else:
        T[:, 2] = rest / 2
        T[:, 3] = rest / 2
    return T, assets


def fam_bb90():
    for mix, w, safe, L, s in itertools.product(("A", "B"), (0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
                                                ("CASH", "IEF", "HALF"), LEVS, STOPS):
        T, a = alloc_target(mix, w, safe)
        yield {"mix": mix, "w_eq": w, "safe": safe, "L": L, "stop": s}, T, a, True


GATES = {}


def gate(kind, p, asset="0050"):
    key = (kind, p, asset)
    if key not in GATES:
        px = PX[asset]
        GATES[key] = month_ma_signal(px, p) if kind == "MA" else month_mom_signal(px, p)
    return GATES[key]


def fam_crisis_gate():
    for mix, w, safe, (gk, gp), L, s in itertools.product(
            ("A", "B"), (0.7, 0.85, 1.0), ("CASH", "IEF"),
            [("MA", m) for m in (6, 8, 10, 12)] + [("MOM", m) for m in (6, 9, 12)], LEVS, STOPS):
        T, a = alloc_target(mix, w, safe, gate(gk, gp))
        yield {"mix": mix, "w_eq": w, "safe": safe, "gate": f"{gk}{gp}m", "L": L, "stop": s}, T, a, True


def fam_trend(asset):
    px = PX[asset]
    for n, k, L, s in itertools.product((50, 100, 150, 200, 250), (0.0, 0.5), LEVS, STOPS):
        e = shift1(np.where(ma_signal(px, n) > 0, 1.0, k))
        T = np.column_stack([e, 1.0 - e])
        yield {"ma_days": n, "bear_exposure": k, "L": L, "stop": s}, T, [asset, "CASH"], False


def fam_vol():
    for win, k, L, s in itertools.product((10, 20, 60), (0.0, 0.25, 0.5), LEVS, STOPS):
        e = vol_signal(R["0050"], win, k)
        T = np.column_stack([e, 1.0 - e])
        yield {"vol_win": win, "hi_vol_exposure": k, "L": L, "stop": s}, T, ["0050", "CASH"], False


def fam_credit():
    from fred_yield_curve_gate import fetch_fred_series
    d = fetch_fred_series("BAA10Y", "2002-01-01")
    s = pd.Series(d["value"].astype(float).to_numpy(), index=pd.to_datetime(d["date"]).dt.normalize()).sort_index()
    s = s[s.index <= END]
    sp = s.reindex(DATES, method="ffill").to_numpy(float)
    for months, w, L, st in itertools.product((6, 12, 18), (0.7, 1.0), LEVS, STOPS):
        me = pd.Series(sp[MONTH_END])
        ma = me.rolling(months, min_periods=months).mean().to_numpy()
        ok = np.where(np.isnan(ma), 1.0, (me.to_numpy() <= ma).astype(float))
        sig = np.ones(N)
        cur = 1.0
        pos = dict(zip(np.flatnonzero(MONTH_END), ok))
        for i in range(N):
            if i in pos:
                cur = pos[i]
            sig[i] = cur
        T, a = alloc_target("A", w, "CASH", shift1(sig))
        yield {"spread_ma_months": months, "w_eq": w, "L": L, "stop": st}, T, a, True


FAMILIES = [
    ("F1", "#418／#425 Bb-90 核心配置（0050／VTI＋債／現金）", [418, 425, 420], fam_bb90),
    ("F2", "#426 危機閘門 × 槓桿 Bb-90（月均線／絕對動能閘門）", [426, 424, 428], fam_crisis_gate),
    ("F3", "#414 0050 趨勢槓桿（日均線）", [414, 243], lambda: fam_trend("0050")),
    ("F4", "#413 美股趨勢槓桿（VTI 台幣計，日均線）", [413, 416], lambda: fam_trend("VTI")),
    ("F5", "#247 已實現波動度 regime（0050）", [247], fam_vol),
    ("F6", "#430 R1 信用利差閘門（BAA10Y）", [430], fam_credit),
]


def plot(fid, title, best_r, bench_r):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(DATES, np.cumprod(1 + best_r), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(DATES, np.cumprod(1 + bench_r), color="#9aa0a6", lw=1.2, label="0050 買進持有（含息）")
    ax.set_yscale("log")
    ax.set_title(f"{fid} {title}（樣本內最優化，2003-07～2024-12，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    CURVE_DIR.mkdir(parents=True, exist_ok=True)
    p = CURVE_DIR / f"batch1_{fid}.png"
    fig.savefig(p)
    plt.close(fig)
    return p.relative_to(HERE.parent).as_posix()


def main():
    only = set(ARGV) if ARGV else None
    bench = {"r": R["0050"], "trades": [(1.0, float(np.prod(1 + R["0050"])))]}
    bm = metrics(bench)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": END,
           "data_start": str(DATES.iloc[0].date()), "benchmark_0050": bm, "families": []}
    if OUT_JSON.exists():
        prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        out["families"] = [f for f in prev.get("families", []) if only and f["id"] not in only]
    for fid, title, src, gen in FAMILIES:
        if only and fid not in only:
            continue
        prog(f"{fid} 開始")
        rows = []
        best = None
        try:
            for params, T, assets, monthly in gen():
                res = simulate(T, assets, params["L"], params["stop"], monthly)
                m = metrics(res)
                rows.append({**params, **m})
                ok = not m["violates_survival"]
                key = (ok, m["calmar"] if ok else -m["mdd"])
                if best is None or key > best[0]:
                    best = (key, params, m, res["r"])
        except Exception as e:  # noqa: BLE001 —— 單一家族失敗不影響其他家族
            print(f"::warning::{fid} 失敗：{e!r}")
            out["families"].append({"id": fid, "title": title, "source_trials": src, "error": repr(e)})
            continue
        top_cagr = max((r for r in rows if not r["violates_survival"]), key=lambda r: r["cagr"], default=None)
        png = plot(fid, title, best[3], R["0050"])
        out["families"].append({"id": fid, "title": title, "source_trials": src, "n_grid": len(rows),
                                "best_by_calmar": {**best[1], **best[2]}, "best_by_cagr_within_mdd50": top_cagr,
                                "n_violates": sum(r["violates_survival"] for r in rows), "curve_png": png})
        prog(f"{fid} 完成 {len(rows)} 格；最佳 {best[1]} → {best[2]}")
    out["families"].sort(key=lambda f: f["id"])
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    prog(f"寫入 {OUT_JSON}")


if __name__ == "__main__":
    main()
