# -*- coding: utf-8 -*-
"""先.二十五-二／三：核心配置 24 組格點單發（分散化，不擇時）。

定義全部事前綁定於 docs/PREREG_core_allocation_FINAL.md（登記 #417，試驗數以 24 計入 N），
該檔已於執行前 commit＋push。**單發只跑一次；績效數字一律到 JSON 寫完後才印。**

紙.一 70/30 不得改動；本試驗只決定是否另開紙.一b。
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
import trend_leverage_backtest as TL  # noqa: E402  （沿用已登記的 mdd/sortino/cagr 等函式）

START, END = "2003-07-01", "2024-12-31"
PREREG = "docs/PREREG_core_allocation_FINAL.md"
OUT = HERE / "data" / "core_allocation_result.json"
CACHE = HERE / "data" / "raw" / "core_alloc"
CACHE.mkdir(parents=True, exist_ok=True)

WHT = 0.30          # 美國 ETF 配息預扣稅
FX_COST = 0.003     # 匯兌成本單邊
TW_SELL_TAX = 0.001  # 台股 ETF 賣出證交稅
EQUITY_W = [0.60, 0.70, 0.80, 0.90]
BEAR = {"2008": ("2008-01-01", "2008-12-31"), "2015": ("2015-04-01", "2015-12-31"),
        "2020": ("2020-02-01", "2020-04-30"), "2022": ("2022-01-01", "2022-12-31")}


def yf_total_return_twd(sym: str, fx: pd.Series) -> pd.DataFrame:
    """美國 ETF 的台幣計價總報酬日序列，配息扣 30% 預扣稅。

    `Adj Close` 內含**稅前**再投資配息，直接用會高估。做法：
    用未調整的 Close 算價格報酬，再逐筆把現金配息（扣 30% 後）加回，
    最後乘上匯率變動換成台幣。
    """
    p = CACHE / f"{sym}.parquet"
    if p.exists():
        d = pd.read_parquet(p)
    else:
        import yfinance as yf
        t = yf.Ticker(sym).history(start="2002-01-01", auto_adjust=False, actions=True).reset_index()
        t.columns = [str(c).lower().replace(" ", "_") for c in t.columns]
        dc = "date" if "date" in t.columns else t.columns[0]
        d = pd.DataFrame({"date": pd.to_datetime(t[dc]).dt.tz_localize(None).dt.normalize(),
                          "close": t["close"].astype(float),
                          "dividends": t.get("dividends", pd.Series(0.0, index=t.index)).astype(float)})
        d = d.dropna(subset=["close"]).sort_values("date")
        d.to_parquet(p, index=False)
    c = d["close"].to_numpy(float)
    dv = d["dividends"].to_numpy(float)
    r_usd = np.zeros(len(c))
    r_usd[1:] = (c[1:] + dv[1:] * (1.0 - WHT)) / c[:-1] - 1.0
    out = pd.DataFrame({"date": d["date"], "r_usd": r_usd})
    f = fx.reindex(out["date"]).ffill()
    fr = np.zeros(len(out))
    fv = f.to_numpy(float)
    with np.errstate(invalid="ignore"):
        fr[1:] = fv[1:] / fv[:-1] - 1.0
    fr = np.nan_to_num(fr)
    # 台幣計價總報酬 = (1+美元報酬)(1+匯率變動) - 1；DEXTAUS 為 TWD/USD，升值代表美元走強
    out["r_twd"] = (1.0 + out["r_usd"].to_numpy()) * (1.0 + fr) - 1.0
    return out[["date", "r_twd"]]


def load_all() -> dict:
    from fred_yield_curve_gate import fetch_fred_series
    import adjust
    fxd = fetch_fred_series("DEXTAUS", "2002-01-01")
    fx = pd.Series(fxd["value"].astype(float).to_numpy(),
                   index=pd.to_datetime(fxd["date"]).dt.normalize()).sort_index()
    px = adjust.adjusted_price_series("0050", "2003-01-01")[["date", "adj_close"]].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    px = px.dropna().sort_values("date")
    a = px["adj_close"].to_numpy(float)
    r0050 = np.zeros(len(a))
    r0050[1:] = a[1:] / a[:-1] - 1.0
    tw = pd.DataFrame({"date": px["date"], "r_0050": r0050})
    rf = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rfm = {str(x["date"])[:7]: float(x["rf_rate_pct"]) for x in rf}
    tw["r_cash"] = [rfm.get(str(d)[:7], 0.0) / 100.0 / 252.0 for d in tw["date"].dt.strftime("%Y-%m")]
    vti = yf_total_return_twd("VTI", fx).rename(columns={"r_twd": "r_vti"})
    ief = yf_total_return_twd("IEF", fx).rename(columns={"r_twd": "r_ief"})
    df = tw.merge(vti, on="date", how="left").merge(ief, on="date", how="left")
    df[["r_vti", "r_ief"]] = df[["r_vti", "r_ief"]].fillna(0.0)
    df = df[(df["date"] >= START) & (df["date"] <= END)].reset_index(drop=True)
    return {"df": df}


def simulate(df: pd.DataFrame, eq_leg: str, safe_leg: str, w_eq: float) -> np.ndarray:
    """月底再平衡、固定比例。回傳扣成本後的日報酬。

    成本在再平衡日依「需要調整的金額比例」計收：跨幣別部位走匯兌 0.3%，
    台股 ETF 賣出部分走證交稅 0.1%。不擇時、無訊號。
    """
    n = len(df)
    comp = {}
    comp["0050"] = df["r_0050"].to_numpy(float)
    comp["VTI"] = df["r_vti"].to_numpy(float)
    comp["IEF"] = df["r_ief"].to_numpy(float)
    comp["CASH"] = df["r_cash"].to_numpy(float)
    tgt = {}
    if eq_leg == "A":
        tgt["0050"] = w_eq
    else:
        tgt["0050"] = w_eq * 0.5
        tgt["VTI"] = w_eq * 0.5
    ws = 1.0 - w_eq
    if safe_leg == "a":
        tgt["CASH"] = ws
    elif safe_leg == "b":
        tgt["IEF"] = ws
    else:
        tgt["CASH"] = ws * 0.5
        tgt["IEF"] = ws * 0.5
    keys = list(tgt)
    usd = {"VTI", "IEF"}
    twse = {"0050"}
    reb = df["date"].dt.to_period("M") != df["date"].dt.to_period("M").shift(-1)   # 月最後交易日
    w = np.array([tgt[k] for k in keys], float)
    out = np.zeros(n)
    for i in range(n):
        r = np.array([comp[k][i] for k in keys], float)
        w = w * (1.0 + r)
        tot = w.sum()
        out[i] = tot - 1.0
        w = w / tot
        if reb.iloc[i]:
            t = np.array([tgt[k] for k in keys], float)
            d = t - w
            cost = 0.0
            for j, k in enumerate(keys):
                if k in usd:
                    cost += abs(d[j]) * FX_COST
                elif k in twse and d[j] < 0:
                    cost += abs(d[j]) * TW_SELL_TAX
            out[i] -= cost
            w = t.copy()
    return out


def seg(r, dates, a, b):
    m = (dates >= a) & (dates <= b)
    x = r[m.to_numpy()]
    return {"n_days": int(len(x)), "ret": float(np.prod(1 + x) - 1),
            "mdd": TL.mdd(x) if len(x) > 2 else None} if len(x) else None


def main() -> int:
    print("=== 載入資料 ===", flush=True)
    d = load_all()
    df = d["df"]
    dates = df["date"]
    half = len(df) // 2
    print(f"資料 {len(df)} 日：{dates.iloc[0].date()} ~ {dates.iloc[-1].date()}", flush=True)

    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG,
           "prereg_sha256": hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
           "prereg_trial_id": 417, "n_trials_counted": 24,
           "period": {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": len(df)},
           "holdout_note": "資料截至 2024-12-31，2025 起未讀取",
           "costs": {"us_dividend_withholding": WHT, "fx_one_way": FX_COST, "tw_sell_tax": TW_SELL_TAX,
                     "rebalance": "每月最後交易日"},
           "grid": {}}
    rets = {}
    for eq in ("A", "B"):
        for sf in ("a", "b", "c"):
            for w in EQUITY_W:
                key = f"{eq}{sf}-{int(w * 100)}"
                r = simulate(df, eq, sf, w)
                rets[key] = r
                h1, h2 = r[:half], r[half:]
                res["grid"][key] = {
                    "equity_leg": "100% 0050" if eq == "A" else "50% 0050 + 50% VTI",
                    "safe_leg": {"a": "台幣定存", "b": "IEF", "c": "50%定存+50%IEF"}[sf],
                    "equity_weight": w,
                    "cagr": TL.cagr(r, dates), "mdd": TL.mdd(r), "sortino": TL.sortino(r),
                    "worst_12m": TL.worst_12m(r), "longest_underwater_days": TL.longest_underwater(r),
                    "mdd_first_half": TL.mdd(h1), "mdd_second_half": TL.mdd(h2),
                    "cagr_first_half": TL.cagr(h1, dates[:half]), "cagr_second_half": TL.cagr(h2, dates[half:]),
                    "total_ret": float(np.prod(1 + r) - 1)}
    base_key = "Aa-70"
    base = res["grid"][base_key]
    res["baseline_current_70_30"] = base_key

    # 選擇規則（寫死）
    elig = [k for k, v in res["grid"].items()
            if v["mdd"] >= -0.45 and v["mdd_first_half"] >= -0.45 and v["mdd_second_half"] >= -0.45]
    res["step1_mdd_filter"] = {"rule": "全期 MDD >= -45% 且前後兩半期各自 MDD >= -45%",
                               "n_eligible": len(elig), "eligible": sorted(elig)}
    winner = None
    if elig:
        best = max(elig, key=lambda k: (round(res["grid"][k]["cagr"], 10), res["grid"][k]["sortino"]))
        ok_sortino = res["grid"][best]["sortino"] >= base["sortino"]
        res["step2_best_cagr"] = {"candidate": best, "cagr": res["grid"][best]["cagr"],
                                  "sortino": res["grid"][best]["sortino"],
                                  "baseline_sortino": base["sortino"],
                                  "sortino_ge_baseline": bool(ok_sortino)}
        winner = best if ok_sortino else None
    res["winner"] = winner
    res["verdict"] = "有組合勝出" if winner else "無組合勝出，維持現行 70/30"

    # 穩健度報告（只報告）
    if winner:
        r = rets[winner]
        rob = {"two_halves": {"first": {"cagr": res["grid"][winner]["cagr_first_half"],
                                       "mdd": res["grid"][winner]["mdd_first_half"]},
                              "second": {"cagr": res["grid"][winner]["cagr_second_half"],
                                         "mdd": res["grid"][winner]["mdd_second_half"]}},
               "worst_12m": res["grid"][winner]["worst_12m"],
               "longest_underwater_days": res["grid"][winner]["longest_underwater_days"],
               "bear_segments": {}}
        rb = rets[base_key]
        for nm, (a, b) in BEAR.items():
            rob["bear_segments"][nm] = {"winner": seg(r, dates, a, b), "baseline_70_30": seg(rb, dates, a, b)}
        yrs = dates.dt.year.to_numpy()
        yr = {}
        for y in sorted(set(yrs)):
            m = yrs == y
            yr[int(y)] = {"winner": float(np.prod(1 + r[m]) - 1), "baseline_70_30": float(np.prod(1 + rb[m]) - 1)}
            yr[int(y)]["diff"] = yr[int(y)]["winner"] - yr[int(y)]["baseline_70_30"]
        rob["yearly_vs_baseline"] = yr
        rob["years_beating_baseline"] = int(sum(1 for v in yr.values() if v["diff"] > 0))
        rob["years_total"] = len(yr)
        res["robustness_report_only"] = rob

    # 交叉核對：00646 / 00679B 台灣上市 ETF 實際淨值
    cross = {}
    try:
        import adjust
        for sym, proxy in (("00646", "VTI 換算序列"), ("00679B", "IEF 換算序列")):
            try:
                p = adjust.adjusted_price_series(sym, "2015-01-01")[["date", "adj_close"]].dropna()
                p["date"] = pd.to_datetime(p["date"]).dt.normalize()
                if len(p) < 50:
                    cross[sym] = {"note": "資料不足", "n": len(p)}
                    continue
                a = p["adj_close"].to_numpy(float)
                rr = np.zeros(len(a))
                rr[1:] = a[1:] / a[:-1] - 1.0
                col = "r_vti" if sym == "00646" else "r_ief"
                mg = pd.DataFrame({"date": p["date"], "actual": rr}).merge(
                    df[["date", col]], on="date", how="inner")
                if len(mg) < 50:
                    cross[sym] = {"note": "重疊日不足", "n": len(mg)}
                    continue
                cross[sym] = {
                    "proxy": proxy, "n_days": int(len(mg)),
                    "start": str(mg["date"].iloc[0].date()), "end": str(mg["date"].iloc[-1].date()),
                    "actual_cagr": TL.cagr(mg["actual"].to_numpy(), mg["date"]),
                    "converted_cagr": TL.cagr(mg[col].to_numpy(), mg["date"]),
                    "actual_mdd": TL.mdd(mg["actual"].to_numpy()), "converted_mdd": TL.mdd(mg[col].to_numpy()),
                    "daily_corr": float(np.corrcoef(mg["actual"], mg[col])[0, 1]),
                    "mean_abs_daily_diff_pp": float(np.mean(np.abs(mg["actual"] - mg[col])) * 100)}
            except Exception as e:  # noqa: BLE001
                cross[sym] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    except Exception as e:  # noqa: BLE001
        cross["error"] = f"{type(e).__name__}: {e}"
    cross["note"] = "只報告差異，不列入判定；差異來源為追蹤誤差、折溢價、配息稅務處理與匯率換算時點"
    res["crosscheck_tw_etf_report_only"] = cross

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
