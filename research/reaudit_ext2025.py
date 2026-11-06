# -*- coding: utf-8 -*-
"""先.一五五-2 墓園重審第一批補跑 2025 起資料（Cowork 收件匣 039 已定案）。

做兩件事，兩組並列：
 ① 同一組最優參數（`reaudit_optimized_batch1.json` 的 best_by_calmar，2024 底以前挑的）**不重調**，
    把回測延長到本機資料最新日，另列「2025 起段」年化／MDD／Sharpe——這一段沒拿來調參。
 ② 用全期（含 2025 起）重新掃同一張網格、重新挑最優。
性質：描述性，不寫 TRIALS_LEDGER（紙上優化軌，先.一五五-1）。非投資建議。

資料（零新外部請求）：0050 2025 起改讀本機 FinMind 快取
`research/data/raw/TaiwanStockPrice__0050__2025-01-01__latest.parquet`（原始收盤）＋
`TaiwanStockDividend__0050__2025-01-01__latest.parquet`（現金股利，除息日把股利加回）＋
`TaiwanStockSplitPrice__0050__2003-01-01__latest.parquet`（2025-06-18 分割，用分割前後參考價比值還原）。
2024-12-31 以前的 0050 照舊走 `adjust.adjusted_price_series()`（同第一批）。VTI／IEF／DEXTAUS／DTB3／央行定存
都是既有本機快取，截到各自最新日；全期終點取 0050 與 VTI 共同最新日。

用法：python research/reaudit_ext2025.py [F1 F2 ...]
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = HERE / "data" / "raw"
SEG_START = "2025-01-01"


def _tw_0050_from_cache() -> pd.DataFrame:
    px = pd.read_parquet(RAW / "TaiwanStockPrice__0050__2025-01-01__latest.parquet")
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    px = px[px["close"].astype(float) > 0].sort_values("date").reset_index(drop=True)
    c = px["close"].to_numpy(float)
    add = np.zeros(len(px))          # 除息日加回的現金股利
    mult = np.ones(len(px))          # 分割日把當天價格換回分割前單位
    dv = pd.read_parquet(RAW / "TaiwanStockDividend__0050__2025-01-01__latest.parquet")
    for _, row in dv.iterrows():
        exd = str(row.get("CashExDividendTradingDate") or "")[:10]
        cash = float(row.get("CashEarningsDistribution") or 0) + float(row.get("CashStatutorySurplus") or 0)
        if not exd or cash <= 0:
            continue
        hit = np.flatnonzero(px["date"].to_numpy() == np.datetime64(exd))
        if len(hit):
            add[hit[0]] += cash
    sp = pd.read_parquet(RAW / "TaiwanStockSplitPrice__0050__2003-01-01__latest.parquet")
    sp["date"] = pd.to_datetime(sp["date"]).dt.normalize()
    for _, row in sp[sp["date"] >= SEG_START].iterrows():
        ratio = float(row["before_price"]) / float(row["after_price"])
        hit = np.flatnonzero(px["date"].to_numpy() == np.datetime64(row["date"]))
        if len(hit):
            mult[hit[0]] = ratio
    r = np.zeros(len(px))
    r[1:] = ((c[1:] + add[1:]) * mult[1:]) / c[:-1] - 1.0
    out = pd.DataFrame({"date": px["date"], "r_0050": r})
    bad = np.abs(r) > 0.105
    if bad.any():
        raise RuntimeError(f"0050 2025 起還原後仍有超過漲跌幅的日報酬：{out[bad].to_dict('records')}")
    return out


def extend_0050(df: pd.DataFrame) -> pd.DataFrame:
    """df：LB.load_all() 延長版（0050 只到 2024-12-31，之後 r_0050 被 fillna 成 0）。
    換成本機快取的 2025 起 0050 日報酬，日曆取聯集；r_cash 只在台股交易日計（同 CA.load_all）。"""
    tw = _tw_0050_from_cache()
    # 第一天（2025-01-02）的報酬要接 2024-12-31 收盤：用第一批同一份原始收盤
    first_close_2024 = pd.read_parquet(RAW / "TaiwanStockPrice__0050__2003-01-01__2024-12-31.parquet")
    last = first_close_2024.sort_values("date").iloc[-1]
    assert str(last["date"])[:10] == "2024-12-31"
    px25 = pd.read_parquet(RAW / "TaiwanStockPrice__0050__2025-01-01__latest.parquet").sort_values("date")
    tw.loc[0, "r_0050"] = float(px25.iloc[0]["close"]) / float(last["close"]) - 1.0
    rf = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rfm = pd.Series({str(x["date"])[:7]: float(x["rf_rate_pct"]) for x in rf}).sort_index()
    months = tw["date"].dt.strftime("%Y-%m")
    tw["r_cash"] = months.map(lambda m: float(rfm[rfm.index <= m].iloc[-1])).to_numpy() / 100.0 / 252.0
    old = df[df["date"] <= "2024-12-31"].copy()
    new_us = df[df["date"] > "2024-12-31"][["date", "r_vti", "r_ief"]]
    us_end = pd.read_parquet(HERE / "data" / "raw" / "core_alloc" / "VTI.parquet")["date"].max()
    end = min(pd.Timestamp(us_end), tw["date"].max())
    new = tw.merge(new_us, on="date", how="outer").sort_values("date")
    new[["r_0050", "r_cash", "r_vti", "r_ief"]] = new[["r_0050", "r_cash", "r_vti", "r_ief"]].fillna(0.0)
    new = new[new["date"] <= end]
    cols = ["date", "r_0050", "r_cash", "r_vti", "r_ief"]
    out = pd.concat([old[cols], new[cols]], ignore_index=True).sort_values("date").reset_index(drop=True)
    print(f"[ext2025] 0050 2025 起 {len(tw)} 天（至 {tw['date'].max().date()}），VTI 至 {pd.Timestamp(us_end).date()}，"
          f"全期終點 {end.date()}", flush=True)
    return out


def _seg_metrics(r: np.ndarray, dates: pd.Series, a: str, b: str | None = None) -> dict:
    m = (dates >= a).to_numpy() if b is None else ((dates >= a) & (dates <= b)).to_numpy()
    x = r[m]
    if len(x) < 2:
        return {}
    curve = np.cumprod(1.0 + x)
    d = dates[m]
    yrs = (d.iloc[-1] - d.iloc[0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 and yrs > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(np.concatenate([[1.0], curve]))[1:] - 1).min())
    sd = x.std(ddof=1)
    return {"start": str(d.iloc[0].date()), "end": str(d.iloc[-1].date()), "cagr": float(cagr), "mdd": mdd,
            "sharpe": float(x.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0, "total_return": float(curve[-1] - 1)}


def run_batch1(only: set[str] | None) -> dict:
    os.environ["REAUDIT_END"] = "2099-12-31"
    import reaudit_optimized_batch1 as B
    prev = json.loads((HERE / "data" / "reaudit_optimized_batch1.json").read_text(encoding="utf-8"))
    prev_best = {f["id"]: f["best_by_calmar"] for f in prev["families"] if "best_by_calmar" in f}
    bench_full = B.metrics({"r": B.R["0050"], "trades": [(1.0, 2.0)]})
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_start": str(B.DATES.iloc[0].date()),
           "data_end": str(B.DATES.iloc[-1].date()), "seg_start": SEG_START,
           "benchmark_0050": {"full": bench_full, "seg2025": _seg_metrics(B.R["0050"], B.DATES, SEG_START)},
           "families": []}
    for fid, title, src, gen in B.FAMILIES:
        if only and fid not in only:
            continue
        B.prog(f"{fid} 開始")
        pb = prev_best.get(fid)
        keys = None
        fixed = None
        rows = []
        best = None
        try:
            for params, T, assets, monthly in gen():
                res = B.simulate(T, assets, params["L"], params["stop"], monthly)
                m = B.metrics(res)
                rows.append({**params, **m})
                ok = not m["violates_survival"]
                key = (ok, m["calmar"] if ok else -m["mdd"])
                if best is None or key > best[0]:
                    best = (key, params, m, res["r"])
                if pb is not None:
                    keys = keys or list(params)
                    if all(params[k] == pb.get(k) for k in params):
                        fixed = (params, m, res["r"])
        except Exception as e:  # noqa: BLE001
            print(f"::warning::{fid} 失敗：{e!r}")
            out["families"].append({"id": fid, "title": title, "error": repr(e)})
            continue
        fam = {"id": fid, "title": title, "source_trials": src, "n_grid": len(rows),
               "n_violates": sum(r["violates_survival"] for r in rows)}
        if fixed is not None:
            fam["fixed_params"] = fixed[0]
            fam["fixed_full"] = fixed[1]
            fam["fixed_pre2025"] = _seg_metrics(fixed[2], B.DATES, "1900-01-01", "2024-12-31")
            fam["fixed_seg2025"] = _seg_metrics(fixed[2], B.DATES, SEG_START)
        else:
            fam["fixed_missing"] = f"網格裡找不到原最優組 {pb}"
        fam["reopt_params"] = best[1]
        fam["reopt_full"] = best[2]
        fam["reopt_seg2025"] = _seg_metrics(best[3], B.DATES, SEG_START)
        fam["curve_png"] = _plot(B, fid, title, fixed[2] if fixed else None, best[3])
        out["families"].append(fam)
        B.prog(f"{fid} 完成：原最優 2025 起 {fam.get('fixed_seg2025')}；重新優化 {best[1]}")
    return out


def _plot(B, fid, title, fixed_r, reopt_r):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    if fixed_r is not None:
        ax.plot(B.DATES, np.cumprod(1 + fixed_r), color="#2a6fdb", lw=1.6, label="原最優組（2024 底前挑、不重調）")
    ax.plot(B.DATES, np.cumprod(1 + reopt_r), color="#e8710a", lw=1.1, ls="--", label="全期重新優化")
    ax.plot(B.DATES, np.cumprod(1 + B.R["0050"]), color="#9aa0a6", lw=1.1, label="0050 買進持有（含息）")
    ax.axvline(pd.Timestamp(SEG_START), color="#5f6368", lw=0.8, ls=":")
    ax.set_yscale("log")
    ax.set_title(f"{fid} {title}（延長到 {B.DATES.iloc[-1].date()}，虛線右邊＝沒拿來調參的 2025 起段，非投資建議）", fontsize=9)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    d = HERE / "data" / "reaudit_curves"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"ext2025_{fid}.png"
    fig.savefig(p)
    plt.close(fig)
    return p.relative_to(HERE).as_posix()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    only = set(sys.argv[1:]) or None
    sys.argv = [sys.argv[0]]
    out = run_batch1(only)
    p = HERE / "data" / "reaudit_ext2025_batch1.json"
    if p.exists() and only:
        prev = json.loads(p.read_text(encoding="utf-8"))
        keep = [f for f in prev.get("families", []) if f["id"] not in only]
        out["families"] = sorted(keep + out["families"], key=lambda f: f["id"])
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"寫入 {p}")


if __name__ == "__main__":
    main()
