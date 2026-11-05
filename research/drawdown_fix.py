"""先.一五二-1 回撤診斷與降回撤優化（描述性研究，不是判定；Cowork 收件匣，總司令 11/05「讓回測不要回那麼深」）。

做法（零請求、只讀既有快取，資料期間 ≤2024-12-31，holdout 未讀）：
1. 從 REAUDIT 各家族存好的 1× 日權益快取重建「最優格」曲線，先用同一套 overlay()／stats() 重算，
   跟 REAUDIT_OPTIMIZED.md 的年化／MDD 對得上才往下做（對不上就跳過該家族並記錄）。
2. 回撤成因表：最深 5 段回撤（起點／谷底／回到前高／深度／天數），每段附同期加權指數漲跌與指數自身回撤，
   以及「放大倍數」＝策略深度 ÷ 1× 底層同期深度。
3. 帳戶層降回撤條件（每種都掃參數，曝險只用前一日以前的資訊）：
   A 大盤均線閘門、B 只在崩盤段生效（跌破均線＋指數距 252 日高點跌超過 X 同時成立）、
   C 波動目標、D 回撤斷路器（看 1× 底層影子曲線，不看帳戶，避免 absorbing state）。
4. 每個條件版本都把槓桿 L' 從 0.5 掃到 3.0（步 0.05），找「年化 ≥ 原版」的最小 L'，報 MDD／Calmar／Sharpe；
   取 MDD 最小者為該家族的降回撤版。
個股停損／產業上限／台指期避險／多策略組合要重跑引擎或要全部家族曲線，留給下一輪（見 DRAWDOWN_FIX.md 第 4 節）。

用法：python research/drawdown_fix.py [F18 F12 ...]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DATA = HERE / "data"
OUT_DIR = DATA / "drawdown_fix"
END = "2024-12-31"
MARGIN_RATE = 0.065 / 252.0  # 同 reaudit_optimized_batch2_sector.py
COOLDOWN = 21
L_GRID = np.round(np.arange(0.5, 3.0001, 0.05), 2)

_ONLY = set(sys.argv[1:])
sys.argv = [sys.argv[0], "--formula", "421"]
import leveraged_bb90_backtest as LB  # noqa: E402


def overlay(r, rf, expo, stop, margin=None, reentry=None):
    """帳戶模擬：r＝1× 底層日報酬（r[0]=0），expo＝當日曝險倍數（已含 L 與條件，只用前一日資訊），
    stop＝帳戶自高點回撤停損（清倉 21 日，同 REAUDIT）。未投入部分領 rf，超過 1 倍付融資利率。"""
    n = len(r)
    out = np.empty(n)
    v, peak, cool, in_pos = 1.0, 1.0, 0, True
    nstop = 0
    shadow = 1.0
    for i in range(n):
        if i > 0:
            if in_pos:
                e = expo[i]
                mr = MARGIN_RATE if margin is None else margin[i]
                v *= 1.0 + e * r[i] - max(e - 1.0, 0.0) * mr + max(1.0 - e, 0.0) * rf[i]
            else:
                v *= 1.0 + rf[i]
            v = max(v, 0.0)
        if stop is not None:
            if in_pos:
                peak = max(peak, v)
                if v < peak * (1 - stop):
                    in_pos, cool, nstop, shadow = False, COOLDOWN, nstop + 1, 1.0
            elif reentry is None:
                cool -= 1
                if cool <= 0:
                    in_pos, peak = True, v
            else:
                # E 類：停損後不固定停 21 日，改看 1× 影子曲線（停損隔日起累積）回升到 1+g 才進場；
                # 今日收盤判斷、明日起持有，無前視。
                shadow *= 1.0 + r[i]
                if shadow >= 1.0 + reentry:
                    in_pos, peak = True, v
        out[i] = v
    return out, nstop


def stats(curve, dates):
    yrs = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    dr = np.diff(curve) / np.where(curve[:-1] > 0, curve[:-1], np.nan)
    dr = dr[~np.isnan(dr)]
    sh = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    return float(cagr), mdd, sh


# ---------- 家族載入：回傳 dates、1× 底層日報酬 r（r[0]=0）、原版 L／stop、REAUDIT 記錄的年化／MDD ----------
def _cells(name, key, ret_style=False):
    c = json.loads((DATA / f"reaudit_optimized_batch2_{name}_cells.json").read_text(encoding="utf-8"))[key]
    dates = pd.to_datetime(pd.Series(c["dates"]))
    if ret_style:
        eq = np.concatenate([[1.0], np.cumprod(1 + np.array(c["ret"], float))])
        dates = pd.concat([pd.Series([dates.iloc[0] - pd.Timedelta(days=1)]), dates], ignore_index=True)
    else:
        eq = np.array(c["equity"], float)
        eq = eq / eq[0]
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    return dates, r


def _best(name):
    j = json.loads((DATA / f"reaudit_optimized_batch2_{name}.json").read_text(encoding="utf-8"))
    return j["families"][0]["best_by_calmar"]


FAMILIES = {
    # fid: (標題, cells 檔名, cells key, ret_style)
    "F18": ("零股委託簿失衡度組合（台股個股，2020-10～2024）", "oddlot", "21_-1_30_0.15", False),
    "F12": ("Weinstein 第二階段（台股個股，2015～2024）", "weinstein", "150_0_20_1.0", False),
    "F14": ("ML 價量選股 HGB（台股個股，2015～2024）", "ml", "63_0_30_0.15", False),
    "F17": ("core_tilt v2 成分內傾斜（2013-06～2024）", "coretilt", "0.02_0.03_63_1", True),
}


def load_family(fid):
    title, name, key, rs = FAMILIES[fid]
    dates, r = _cells(name, key, rs)
    assert dates.max() <= pd.Timestamp(END)
    b = _best(name)
    return {"fid": fid, "title": title, "dates": dates.reset_index(drop=True), "r": r,
            "L": float(b["L"]), "stop": b["stop"], "cagr0": float(b["cagr"]), "mdd0": float(b["mdd"])}


_TAIEX = None


def taiex():
    global _TAIEX
    if _TAIEX is None:
        from factor_ic import START_DATE
        from finmind_client import load_dev
        m = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
        m = m[m["date"] <= END].sort_values("date")
        _TAIEX = pd.Series(m["close"].to_numpy(float), index=pd.to_datetime(m["date"]))
    return _TAIEX


# ---------- 回撤段 ----------
def episodes(curve, dates, k=5):
    dd = curve / np.maximum.accumulate(curve) - 1
    eps, i, n = [], 0, len(curve)
    while i < n:
        if dd[i] < 0:
            s = i - 1
            j = i
            while j < n and dd[j] < 0:
                j += 1
            seg = dd[s + 1:j]
            t = s + 1 + int(np.argmin(seg))
            eps.append({"peak_i": s, "trough_i": t, "rec_i": j if j < n else None, "depth": float(dd[t])})
            i = j
        else:
            i += 1
    eps = sorted(eps, key=lambda e: e["depth"])[:k]
    return sorted(eps, key=lambda e: e["peak_i"])


def attribute(e, dates, curve_1x, mkt_series=None):
    d0, d1 = dates[e["peak_i"]], dates[e["trough_i"]]
    tx = taiex() if mkt_series is None else mkt_series
    w = tx[(tx.index >= d0) & (tx.index <= d1)]
    mkt = float(w.iloc[-1] / w.iloc[0] - 1) if len(w) > 1 else float("nan")
    mkt_dd = float((w / w.cummax() - 1).min()) if len(w) > 1 else float("nan")
    base = float(curve_1x[e["trough_i"]] / curve_1x[e["peak_i"]] - 1)
    crash = None
    for name, a, b in (("2008 金融海嘯", "2007-10-01", "2009-03-31"), ("2011 歐債", "2011-04-01", "2011-12-31"),
                       ("2015 陸股崩", "2015-04-01", "2016-02-29"), ("2018 十月", "2018-09-01", "2019-01-31"),
                       ("2020 疫情", "2020-01-15", "2020-04-30"), ("2022 升息", "2022-01-01", "2022-12-31")):
        if d0 <= pd.Timestamp(b) and d1 >= pd.Timestamp(a):
            crash = name
    if crash is None:
        cause = "策略自身（大盤同期未明顯下跌）" if not (mkt < -0.08) else "大盤下跌（非六大崩盤段）"
    else:
        cause = f"跟著大盤崩（{crash}）" if mkt < -0.08 else f"與 {crash} 重疊但大盤同期跌幅小→策略自身"
    lev = e["depth"] / base if base < -1e-9 else float("nan")
    return {"peak": str(d0.date()), "trough": str(d1.date()),
            "recovered": str(dates[e["rec_i"]].date()) if e["rec_i"] is not None else "未回到前高（至 2024-12-31）",
            "depth": e["depth"], "days_to_trough": int((d1 - d0).days),
            "days_total": int(((dates[e["rec_i"]] if e["rec_i"] is not None else dates.iloc[-1]) - d0).days),
            "taiex_ret": mkt, "taiex_dd": mkt_dd, "base_1x_ret": base, "amplify": lev, "cause": cause}


# ---------- 降回撤條件：回傳 0～1 的曝險係數（只用前一日以前的資訊） ----------
def cond_series(kind, p, dates, r, mkt_series=None):
    n = len(r)
    if kind == "none":
        return np.ones(n), {}
    tx = (taiex() if mkt_series is None else mkt_series).reindex(pd.DatetimeIndex(dates)).ffill().to_numpy()
    if kind in ("ma", "crash"):
        s = pd.Series(tx)
        ma = s.rolling(p["n"], min_periods=p["n"]).mean().to_numpy()
        below = tx < ma
        if kind == "crash":
            hi = s.rolling(252, min_periods=60).max().to_numpy()
            below = below & (tx / hi - 1 < -p["x"])
        f = np.where(below, p["y"], 1.0)
    elif kind == "vol":
        rv = pd.Series(r).rolling(p["k"], min_periods=p["k"]).std().to_numpy() * np.sqrt(252)
        f = np.where(np.isfinite(rv) & (rv > 0), np.minimum(1.0, p["t"] / np.maximum(rv, 1e-9)), 1.0)
    elif kind == "dd":
        sh = np.cumprod(1 + r)
        ddv = sh / np.maximum.accumulate(sh) - 1
        f = np.ones(n)
        on = False
        trig = 0
        for i in range(n):
            if not on and ddv[i] <= -p["x"]:
                on, trig = True, trig + 1
            elif on and ddv[i] > -p["z"]:
                on = False
            f[i] = p["y"] if on else 1.0
        f = np.concatenate([[1.0], f[:-1]])
        return f, {"triggers": trig}
    else:
        raise ValueError(kind)
    f = np.concatenate([[1.0], f[:-1]])  # 前一日資訊決定今日曝險
    f = np.where(np.isfinite(f), f, 1.0)
    return f, {}


def variants():
    yield "none", {}
    for n in (60, 120, 200, 250):
        for y in (0.0, 0.25, 0.5):
            yield "ma", {"n": n, "y": y}
    for n in (120, 200, 250):
        for x in (0.10, 0.15, 0.20):
            for y in (0.0, 0.25, 0.5):
                yield "crash", {"n": n, "x": x, "y": y}
    for k in (20, 60):
        for t in (0.10, 0.15, 0.20, 0.30):
            yield "vol", {"k": k, "t": t}
    for x in (0.10, 0.15, 0.20, 0.25):
        for y in (0.0, 0.3, 0.5):
            for z in (0.05, 0.10):
                if z < x:
                    yield "dd", {"x": x, "y": y, "z": z}


KIND_ZH = {"none": "不加條件（只調槓桿）", "ma": "A 大盤均線閘門", "crash": "B 只在崩盤段生效",
           "vol": "C 波動目標", "dd": "D 回撤斷路器（看 1× 影子曲線）", "reentry": "E 停損後看影子曲線回升才進場"}


def desc(kind, p):
    if kind == "ma":
        return f"大盤<{p['n']}日均線→曝險×{p['y']}"
    if kind == "crash":
        return f"大盤<{p['n']}日均線且距252日高點跌>{p['x']:.0%}→曝險×{p['y']}"
    if kind == "vol":
        return f"近{p['k']}日實現波動目標 {p['t']:.0%}（上限 1×）"
    if kind == "dd":
        return f"1×影子回撤≥{p['x']:.0%}→曝險×{p['y']}，回到 −{p['z']:.0%} 以內恢復"
    return "—"


def run_family(fid):
    F = load_family(fid)
    dates, r = F["dates"], F["r"]
    rf = LB.load_tw_rf_daily(dates)
    stop0 = None if F["stop"] is None or F["stop"] != F["stop"] else float(F["stop"])
    c0, _ = overlay(r, rf, np.full(len(r), F["L"]), stop0)
    cagr0, mdd0, sh0 = stats(c0, dates)
    ok = abs(cagr0 - F["cagr0"]) < 0.002 and abs(mdd0 - F["mdd0"]) < 0.002
    print(f"{fid} 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%}（REAUDIT {F['cagr0']:+.2%}／{F['mdd0']:.2%}）→ {'對上' if ok else '對不上'}")
    res = {"fid": fid, "title": F["title"], "period": [str(dates.iloc[0].date()), str(dates.iloc[-1].date())],
           "orig": {"L": F["L"], "stop": stop0, "cagr": cagr0, "mdd": mdd0, "sharpe": sh0,
                    "calmar": cagr0 / abs(mdd0)}, "reproduced": ok}
    if not ok:
        res["error"] = "重建數字對不上 REAUDIT，跳過"
        return res, None
    c1x = np.cumprod(1 + r)
    res["episodes"] = [attribute(e, dates, c1x) for e in episodes(c0, dates)]
    rows = []
    for kind, p in variants():
        f, info = cond_series(kind, p, dates, r)
        for stop in ({None, stop0}):
            best = None
            for L in L_GRID:
                cv, ns = overlay(r, rf, L * f, stop)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None,
                            "n_stop": ns}
                    break
            # 同時記錄不調槓桿（原 L）時的風險調整後數字
            cv1, _ = overlay(r, rf, F["L"] * f, stop)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": kind, "params": p, "desc": desc(kind, p), "stop": stop, **info,
                         "avg_expo_factor": float(f.mean()),
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})

    # E 類：停損後改看影子曲線回升才進場（不加大盤條件）
    for st in (0.10, 0.20, 0.30):
        for g in (0.0, 0.03, 0.05):
            best = None
            for L in L_GRID:
                cv, ns = overlay(r, rf, L * np.ones(len(r)), st, None, g)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None, "n_stop": ns}
                    break
            cv1, ns1 = overlay(r, rf, F["L"] * np.ones(len(r)), st, None, g)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": "reentry", "params": {"stop": st, "g": g},
                         "desc": f"帳戶停損 {st:.0%}，影子曲線回升 {g:.0%} 才進場", "stop": st, "triggers": ns1,
                         "avg_expo_factor": 1.0,
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    res["n_variants"] = len(rows)
    res["n_feasible"] = len(feas)
    bykind = {}
    for x in feas:
        k = x["kind"]
        if k not in bykind or x["same_cagr"]["mdd"] > bykind[k]["same_cagr"]["mdd"]:
            bykind[k] = x
    res["best_by_kind"] = bykind
    res["best"] = max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None
    res["rows"] = rows
    curves = {"dates": dates, "orig": c0, "best": None}
    if res["best"]:
        b = res["best"]
        f, _ = cond_series(b["kind"], b["params"], dates, r)
        curves["best"], _ = overlay(r, rf, b["same_cagr"]["L"] * f, b["stop"])
    return res, curves


# ---------- 原生模擬器路徑（F2／F11／F10：batch1 simulate()，槓桿只加在 0050／VTI 腿、含換手成本） ----------
# 這些家族的大盤代理用 0050 含息淨值（F2 從 2003-07 起，早於 TAIEX 快取起點）。
NATIVE = {
    "F7": "台指期均線擇時（TX 連續合約，2003-07～2024）",
    "F2": "危機閘門 × 槓桿 Bb-90（2003-07～2024）",
    "F11": "全市場融資餘額 regime（0050 曝險，2013-11～2024）",
    "F10": "全市場廣度 regime（0050 曝險，2011～2024）",
}


def load_native(fid):
    """回傳 B 模組、目標權重 T、資產、monthly、原版 L／stop、REAUDIT 記錄值。注意：F11／F10 會切 B 的全域變數，
    所以每次執行只能跑一支原生家族（main() 已保證）。"""
    if fid == "F2":
        import reaudit_optimized_batch1 as B
        j = json.loads((DATA / "reaudit_optimized_batch1.json").read_text(encoding="utf-8"))
        b = [f for f in j["families"] if f["id"] == "F2"][0]["best_by_calmar"]
        gk, gp = b["gate"][:-1].rstrip("0123456789"), int("".join(ch for ch in b["gate"] if ch.isdigit()))
        T, a = B.alloc_target(b["mix"], b["w_eq"], b["safe"], B.gate(gk, gp))
        return B, T, a, True, b
    if fid == "F11":
        import reaudit_optimized_batch2_margin as M
        B = M.B
        b = _best("margin")
        bal = M.load_bal()
        flags = {(k, p, d): M.flag(bal, k, p, d) for k in M.KS for p in M.PS for d in M.DIRS}
        first = max(f.first_valid_index() for f in flags.values())
        i0 = int(np.searchsorted(B.DATES.to_numpy(), np.datetime64(first), side="left")) + 1
        M.slice_globals(i0)
        e = M.exposure(M.to_daily(flags[(int(b["k_weeks"]), float(b["pctile"]), b["direction"])]), b["def_exposure"], b["freq"])
        return B, np.column_stack([e, 1.0 - e]), ["0050", "CASH"], False, b
    if fid == "F10":
        import reaudit_optimized_batch2_breadth as BR
        B = BR.B
        b = _best("breadth")
        panel = BR.load_panel()
        br = {n: BR.breadth(panel, n) for n in BR.MAS}
        first = max(x.first_valid_index() for x in br.values())
        i0 = int(np.searchsorted(B.DATES.to_numpy(), np.datetime64(first), side="left")) + 1
        BR.slice_globals(i0)
        bv = br[int(b["ma"])].reindex(B.DATES, method="ffill").to_numpy(float)
        e = np.where(np.isnan(bv), 1.0, np.where(bv < b["threshold"], b["def_exposure"], 1.0))
        e = B.monthly_hold(e) if b["freq"] == "M" else B.shift1(e)
        return B, np.column_stack([e, 1.0 - e]), ["0050", "CASH"], False, b
    raise ValueError(fid)


def run_native(fid):
    B, T, assets, monthly, b = load_native(fid)
    dates = B.DATES.reset_index(drop=True)
    risky = np.array([x in ("0050", "VTI") for x in assets])
    ci = assets.index("CASH")
    stop0 = None if b["stop"] is None or b["stop"] != b["stop"] else float(b["stop"])

    def sim(f, L, stop):
        T2 = T.copy()
        if f is not None:
            moved = T2[:, risky].sum(axis=1) * (1 - f)
            T2[:, risky] *= f[:, None]
            T2[:, ci] += moved
        r = B.simulate(T2, assets, float(L), stop, monthly)["r"]
        return np.cumprod(1 + r), r

    c0, r0 = sim(None, b["L"], stop0)
    cagr0, mdd0, sh0 = stats(c0, dates)
    ok = abs(cagr0 - b["cagr"]) < 0.002 and abs(mdd0 - b["mdd"]) < 0.002
    print(f"{fid} 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%}（REAUDIT {b['cagr']:+.2%}／{b['mdd']:.2%}）→ {'對上' if ok else '對不上'}")
    res = {"fid": fid, "title": NATIVE[fid], "period": [str(dates.iloc[0].date()), str(dates.iloc[-1].date())],
           "orig": {"L": float(b["L"]), "stop": stop0, "cagr": cagr0, "mdd": mdd0, "sharpe": sh0, "calmar": cagr0 / abs(mdd0)},
           "reproduced": ok, "market_proxy": "0050 含息淨值"}
    if not ok:
        res["error"] = "重建數字對不上 REAUDIT，跳過"
        return res, None
    mkt = pd.Series(np.cumprod(1 + B.R["0050"]), index=pd.DatetimeIndex(dates))
    c1x, r1x = sim(None, 1.0, None)
    res["episodes"] = [attribute(e, dates, c1x, mkt) for e in episodes(c0, dates)]
    rows = []
    Lg = np.round(np.arange(1.0, 3.0001, 0.1), 2)  # 原生模擬器較慢，步距 0.1
    for kind, p in variants():
        f, info = cond_series(kind, p, dates, r1x, mkt)
        for stop in ({None, stop0}):
            best = None
            for L in Lg:
                cv, _ = sim(f, L, stop)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None}
                    break
            cv1, _ = sim(f, b["L"], stop)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": kind, "params": p, "desc": desc(kind, p), "stop": stop, **info,
                         "avg_expo_factor": float(f.mean()),
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    res["n_variants"], res["n_feasible"] = len(rows), len(feas)
    bykind = {}
    for x in feas:
        if x["kind"] not in bykind or x["same_cagr"]["mdd"] > bykind[x["kind"]]["same_cagr"]["mdd"]:
            bykind[x["kind"]] = x
    res["best_by_kind"] = bykind
    res["best"] = max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None
    res["rows"] = rows
    curves = {"dates": dates, "orig": c0, "best": None}
    if res["best"]:
        bb = res["best"]
        f, _ = cond_series(bb["kind"], bb["params"], dates, r1x, mkt)
        curves["best"], _ = sim(f, bb["same_cagr"]["L"], bb["stop"])
    return res, curves


# ---------- F7 台指期連續合約（照抄 reaudit_optimized_batch2_tx.py 的 run()：保證金全額擔保，現金領 rf，換手成本 5bp） ----------
def run_tx():
    import reaudit_optimized_batch2_tx as TX
    s, _ = TX.build_continuous_series(contract="TX", session="position")
    s = s.copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[(s["date"] <= END) & (s["date"] >= "2003-07-01")].sort_values("date").reset_index(drop=True)
    px = s["adj_close"].to_numpy(float)
    r = np.zeros(len(px))
    r[1:] = px[1:] / px[:-1] - 1.0
    dates = s["date"].reset_index(drop=True)
    rf = LB.load_tw_rf_daily(dates)
    n = len(px)
    b = json.loads((DATA / "reaudit_optimized_batch2_tx.json").read_text(encoding="utf-8"))["families"][0]["best_by_calmar"]
    stop0 = None if b["stop"] is None or b["stop"] != b["stop"] else float(b["stop"])
    m = pd.Series(px).rolling(int(b["ma_days"]), min_periods=int(b["ma_days"])).mean().to_numpy()
    raw = np.where(np.isnan(m), 1.0, np.where(px > m, 1.0, b["bear_exposure"]))
    sig = np.r_[raw[0], raw[:-1]]

    def sim(f, L, stop):
        e_sig = sig if f is None else sig * f
        out = np.zeros(n)
        eq, peak, cool, prev, in_pos = 1.0, 1.0, 0, 0.0, False
        for i in range(n):
            e = e_sig[i] * L
            if cool > 0:
                cool -= 1
                e = 0.0
            cost = abs(e - prev) * TX.COST
            ret = 0.0 if eq <= 0 else e * r[i] + rf[i] - cost
            now_in = e > 0
            eq = max(eq * (1 + ret), 0.0)
            in_pos = now_in
            out[i] = ret if eq > 0 or ret > -1 else -1.0
            prev = e
            peak = max(peak, eq) if in_pos else eq
            if stop is not None and in_pos and eq < peak * (1 - stop):
                cool, peak = TX.COOLDOWN, eq
        return np.cumprod(1 + out), out

    c0, _ = sim(None, b["L"], stop0)
    cagr0, mdd0, sh0 = stats(c0, dates)
    ok = abs(cagr0 - b["cagr"]) < 0.002 and abs(mdd0 - b["mdd"]) < 0.002
    print(f"F7 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%}（REAUDIT {b['cagr']:+.2%}／{b['mdd']:.2%}）→ {'對上' if ok else '對不上'}")
    res = {"fid": "F7", "title": "台指期均線擇時（TX 連續合約，2003-07～2024）",
           "period": [str(dates.iloc[0].date()), str(dates.iloc[-1].date())],
           "orig": {"L": float(b["L"]), "stop": stop0, "cagr": cagr0, "mdd": mdd0, "sharpe": sh0, "calmar": cagr0 / abs(mdd0)},
           "reproduced": ok, "market_proxy": "台指期連續合約（還原）"}
    if not ok:
        res["error"] = "重建數字對不上 REAUDIT，跳過"
        return res, None
    mkt = pd.Series(np.cumprod(1 + r), index=pd.DatetimeIndex(dates))
    c1x = mkt.to_numpy()
    res["episodes"] = [attribute(e, dates, c1x, mkt) for e in episodes(c0, dates)]
    rows = []
    for kind, p in variants():
        f, info = cond_series(kind, p, dates, r, mkt)
        for stop in ({None, stop0}):
            best = None
            for L in L_GRID:
                cv, _ = sim(f, L, stop)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None}
                    break
            cv1, _ = sim(f, b["L"], stop)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": kind, "params": p, "desc": desc(kind, p), "stop": stop, **info,
                         "avg_expo_factor": float(f.mean()),
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    res["n_variants"], res["n_feasible"] = len(rows), len(feas)
    bykind = {}
    for x in feas:
        if x["kind"] not in bykind or x["same_cagr"]["mdd"] > bykind[x["kind"]]["same_cagr"]["mdd"]:
            bykind[x["kind"]] = x
    res["best_by_kind"] = bykind
    res["best"] = max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None
    res["rows"] = rows
    curves = {"dates": dates, "orig": c0, "best": None}
    if res["best"]:
        bb = res["best"]
        f, _ = cond_series(bb["kind"], bb["params"], dates, r, mkt)
        curves["best"], _ = sim(f, bb["same_cagr"]["L"], bb["stop"])
    return res, curves


# ---------- F15／F16 美股（原腳本 REAUDIT_DUMP_BASE 模式存的 1× 底層日報酬；融資＝DTB3＋1.5%，同原腳本） ----------
US = {"F15": ("f_us_low_vol 美股低波動（只做多，2011～2024）", "base_F15.json"),
      "F16": ("f_us_value_bm 美股價值（只做多，2011～2024）", "base_F16.json")}


def run_us(fid):
    title, fn = US[fid]
    d = json.loads((OUT_DIR / fn).read_text(encoding="utf-8"))
    dts = pd.to_datetime(pd.Series(d["dates"]))
    dates = pd.concat([pd.Series([dts.iloc[0] - pd.Timedelta(days=1)]), dts], ignore_index=True)
    pad = lambda a: np.concatenate([[0.0], np.array(a, float)])
    r, rf, mg, spy = pad(d["base"]), pad(d["rf"]), pad(d["borrow"]), pad(d["spy"])
    b = d["best"]
    stop0 = None if b["stop"] is None or b["stop"] != b["stop"] else float(b["stop"])
    sim = lambda f, L, stop: overlay(r, rf, L * (np.ones(len(r)) if f is None else f), stop, mg)
    c0, _ = sim(None, b["L"], stop0)
    cagr0, mdd0, sh0 = stats(c0, dates)
    ok = abs(cagr0 - b["cagr"]) < 0.002 and abs(mdd0 - b["mdd"]) < 0.002
    print(f"{fid} 重建：年化 {cagr0:+.2%}／MDD {mdd0:.2%}（REAUDIT {b['cagr']:+.2%}／{b['mdd']:.2%}）→ {'對上' if ok else '對不上'}")
    res = {"fid": fid, "title": title, "period": [str(dts.iloc[0].date()), str(dts.iloc[-1].date())],
           "orig": {"L": float(b["L"]), "stop": stop0, "cagr": cagr0, "mdd": mdd0, "sharpe": sh0, "calmar": cagr0 / abs(mdd0)},
           "reproduced": ok, "market_proxy": "SPY"}
    if not ok:
        res["error"] = "重建數字對不上 REAUDIT，跳過"
        return res, None
    mkt = pd.Series(np.cumprod(1 + spy), index=pd.DatetimeIndex(dates))
    res["episodes"] = [attribute(e, dates, np.cumprod(1 + r), mkt) for e in episodes(c0, dates)]
    rows = []
    for kind, p in variants():
        f, info = cond_series(kind, p, dates, r, mkt)
        for stop in ({None, stop0}):
            best = None
            for L in L_GRID:
                cv, _ = sim(f, L, stop)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None}
                    break
            cv1, _ = sim(f, b["L"], stop)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": kind, "params": p, "desc": desc(kind, p), "stop": stop, **info,
                         "avg_expo_factor": float(f.mean()),
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})

    # E 類：停損後改看影子曲線回升才進場（不加大盤條件）
    for st in (0.10, 0.20, 0.30):
        for g in (0.0, 0.03, 0.05):
            best = None
            for L in L_GRID:
                cv, ns = overlay(r, rf, L * np.ones(len(r)), st, mg, g)
                cg, md, sh = stats(cv, dates)
                if cg >= cagr0 - 1e-9:
                    best = {"L": float(L), "cagr": cg, "mdd": md, "sharpe": sh, "calmar": cg / abs(md) if md < 0 else None, "n_stop": ns}
                    break
            cv1, ns1 = overlay(r, rf, b["L"] * np.ones(len(r)), st, mg, g)
            cg1, md1, sh1 = stats(cv1, dates)
            rows.append({"kind": "reentry", "params": {"stop": st, "g": g},
                         "desc": f"帳戶停損 {st:.0%}，影子曲線回升 {g:.0%} 才進場", "stop": st, "triggers": ns1,
                         "avg_expo_factor": 1.0,
                         "atL0": {"cagr": cg1, "mdd": md1, "sharpe": sh1, "calmar": cg1 / abs(md1) if md1 < 0 else None},
                         "same_cagr": best})
    feas = [x for x in rows if x["same_cagr"]]
    res["n_variants"], res["n_feasible"] = len(rows), len(feas)
    bykind = {}
    for x in feas:
        if x["kind"] not in bykind or x["same_cagr"]["mdd"] > bykind[x["kind"]]["same_cagr"]["mdd"]:
            bykind[x["kind"]] = x
    res["best_by_kind"] = bykind
    res["best"] = max(feas, key=lambda x: x["same_cagr"]["mdd"]) if feas else None
    res["rows"] = rows
    curves = {"dates": dates, "orig": c0, "best": None}
    if res["best"]:
        bb = res["best"]
        f, _ = cond_series(bb["kind"], bb["params"], dates, r, mkt)
        curves["best"], _ = sim(f, bb["same_cagr"]["L"], bb["stop"])
    return res, curves


def plot(res, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    d = curves["dates"]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), dpi=110, sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
    o = res["orig"]
    ax.plot(d, curves["orig"], color="#9aa0a6", lw=1.3, label=f"原版 L={o['L']} 年化{o['cagr']:+.1%} MDD{o['mdd']:.1%}")
    if curves["best"] is not None:
        b = res["best"]
        ax.plot(d, curves["best"], color="#2a6fdb", lw=1.5,
                label=f"降回撤版 {b['desc']}，L'={b['same_cagr']['L']} 年化{b['same_cagr']['cagr']:+.1%} MDD{b['same_cagr']['mdd']:.1%}")
        ax2.plot(d, curves["best"] / np.maximum.accumulate(curves["best"]) - 1, color="#2a6fdb", lw=1)
    ax2.plot(d, curves["orig"] / np.maximum.accumulate(curves["orig"]) - 1, color="#9aa0a6", lw=1)
    for i, e in enumerate(res["episodes"], 1):
        x0, x1 = pd.Timestamp(e["peak"]), pd.Timestamp(e["trough"])
        ax.axvspan(x0, x1, color="#e8710a", alpha=0.15)
        ax.text(x0, ax.get_ylim()[1] if False else curves["orig"][d.searchsorted(x0)], f"#{i}", fontsize=8, color="#e8710a")
    ax.set_yscale("log")
    ax.set_title(f"{res['fid']} {res['title']}：原版 vs 同年化降回撤版（樣本內描述性，非投資建議）", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    ax2.set_ylabel("回撤")
    for a in (ax, ax2):
        a.grid(alpha=0.25)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"{res['fid']}.png"
    fig.savefig(p)
    plt.close(fig)
    return p.relative_to(HERE).as_posix()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    allp = OUT_DIR / "results.json"
    allres = json.loads(allp.read_text(encoding="utf-8")) if allp.exists() else {}
    todo = [f for f in FAMILIES if (not _ONLY or f in _ONLY) and not (_ONLY & (set(NATIVE) | {"F15", "F16"}))]
    nat = [f for f in NATIVE if f in _ONLY][:1]  # 原生家族會切 B 全域變數，一次只跑一支
    usl = [f for f in US if f in _ONLY]
    for fid in todo + nat + usl:
        try:
            res, curves = run_us(fid) if fid in US else run_tx() if fid == "F7" else (run_native(fid) if fid in NATIVE else run_family(fid))
            if curves is not None:
                res["png"] = plot(res, curves)
                pd.DataFrame({"date": pd.to_datetime(curves["dates"]).dt.strftime("%Y-%m-%d"), "orig": curves["orig"],
                              "best": curves["best"] if curves["best"] is not None else np.nan}).to_csv(
                    OUT_DIR / f"curve_{fid}.csv", index=False)
            allres[fid] = res
            b = res.get("best")
            if b:
                print(f"  最好：{b['desc']} stop={b['stop']} L'={b['same_cagr']['L']} → 年化 {b['same_cagr']['cagr']:+.2%}／MDD {b['same_cagr']['mdd']:.2%}")
            else:
                print("  沒有任何條件版本在 L'≤3 下達到原版年化")
        except Exception as e:  # noqa: BLE001 —— 單一家族失敗不影響其他家族
            print(f"::warning::{fid} 失敗：{e!r}")
            allres[fid] = {"fid": fid, "error": repr(e)}
        cur = json.loads(allp.read_text(encoding="utf-8")) if allp.exists() else {}  # 重讀再合併：允許多支平行跑
        cur[fid] = allres[fid]
        allres = cur
        allres["_generated_at"] = datetime.now().isoformat(timespec="seconds")
        allp.write_text(json.dumps(allres, ensure_ascii=False, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
