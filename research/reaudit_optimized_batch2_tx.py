# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之一：#244／#250～#252 台指期（TX）200MA 擇時家族的樣本內最優化（描述性，非判定）。

資料：`continuous_contract.build_continuous_series("TX","position")`（比例回溯調整連續合約，日盤），截到 2024-12-31，
     不讀 2025 以後（holdout 不解鎖）。
規則：訊號用當天收盤以前資料、隔日生效；部位＝曝險 e×槓桿 L 口數等值，保證金以外的現金收台灣無風險利率
     （沿用 #421 load_tw_rf_daily）；成本＝每單位曝險變動 5bps 來回（沿用 #244 的期交稅＋手續費假設），
     轉倉價差由比例調整吸收（未另計轉倉滑價，照實揭露）；止損同 batch1（淨值自持倉高點回落 s 退場、21 日冷卻）；
     權益跌到 0 停在 0（期貨可能虧超過保證金，這裡以權益歸零近似斷頭）。
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
from continuous_contract import build_continuous_series  # noqa: E402

END = "2024-12-31"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_tx.json"
COST = 5.0 / 10_000.0
LEVS = (1.0, 1.5, 2.0, 3.0)
STOPS = (None, 0.10, 0.20, 0.30)
COOLDOWN = 21


def main():
    s, skipped = build_continuous_series(contract="TX", session="position")
    s = s.copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[(s["date"] <= END) & (s["date"] >= "2003-07-01")].sort_values("date").reset_index(drop=True)
    assert s["date"].max() <= pd.Timestamp(END)
    px = s["adj_close"].to_numpy(float)
    r = np.zeros(len(px))
    r[1:] = px[1:] / px[:-1] - 1.0
    dates = s["date"]
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB  # noqa: E402
    rf = LB.load_tw_rf_daily(dates)
    n = len(px)
    yrs = (dates.iloc[-1] - dates.iloc[0]).days / 365.25

    def run(e_sig, L, stop):
        out = np.zeros(n)
        eq, peak, cool, prev = 1.0, 1.0, 0, 0.0
        trades, in_pos, entry = [], False, 1.0
        for i in range(n):
            e = e_sig[i] * L
            if cool > 0:
                cool -= 1
                e = 0.0
            cost = abs(e - prev) * COST
            ret = 0.0 if eq <= 0 else e * r[i] + rf[i] - cost
            now_in = e > 0
            if now_in and not in_pos:
                entry = eq
            eq = max(eq * (1 + ret), 0.0)
            if in_pos and not now_in:
                trades.append((entry, eq))
            in_pos = now_in
            out[i] = ret if eq > 0 or ret > -1 else -1.0
            prev = e
            peak = max(peak, eq) if in_pos else eq
            if stop is not None and in_pos and eq < peak * (1 - stop):
                cool, peak = COOLDOWN, eq
        if in_pos:
            trades.append((entry, eq))
        curve = np.cumprod(1 + out)
        cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
        mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
        sd = out.std(ddof=1)
        return out, {"cagr": float(cagr), "mdd": mdd, "sharpe": float(out.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
                     "trades": len(trades), "win_rate": float(np.mean([b > a for a, b in trades])) if trades else float("nan"),
                     "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"), "violates_survival": bool(mdd < -0.5)}

    rows, best = [], None
    for ma, k, L, st in itertools.product((50, 100, 150, 200, 250), (0.0, 0.25, 0.5), LEVS, STOPS):
        m = pd.Series(px).rolling(ma, min_periods=ma).mean().to_numpy()
        raw = np.where(np.isnan(m), 1.0, np.where(px > m, 1.0, k))
        sig = np.r_[raw[0], raw[:-1]]
        ret, met = run(sig, L, st)
        p = {"ma_days": ma, "bear_exposure": k, "L": L, "stop": st}
        rows.append({**p, **met})
        ok = not met["violates_survival"]
        key = (ok, met["calmar"] if ok else -met["mdd"])
        if best is None or key > best[0]:
            best = (key, p, met, ret)
    bh_ret, bh = run(np.ones(n), 1.0, None)
    top = max((x for x in rows if not x["violates_survival"]), key=lambda x: x["cagr"], default=None)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(dates, np.cumprod(1 + best[3]), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(dates, np.cumprod(1 + bh_ret), color="#9aa0a6", lw=1.2, label="台指期 1 口等值持有＋現金利息")
    ax.set_yscale("log")
    ax.set_title(f"F7 #244 台指期均線擇時（樣本內最優化，{dates.iloc[0].date()}～2024-12，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    cd = HERE / "data" / "reaudit_curves"
    cd.mkdir(parents=True, exist_ok=True)
    fig.savefig(cd / "batch2_F7.png")
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": END,
           "data_start": str(dates.iloc[0].date()), "benchmark_tx_hold": bh, "skipped_rollovers": len(skipped),
           "families": [{"id": "F7", "title": "#244／#250～#252 台指期均線擇時（TX 連續合約）", "source_trials": [244, 250, 251, 252],
                         "n_grid": len(rows), "best_by_calmar": {**best[1], **best[2]}, "best_by_cagr_within_mdd50": top,
                         "n_violates": sum(x["violates_survival"] for x in rows),
                         "curve_png": "research/data/reaudit_curves/batch2_F7.png"}]}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("轉倉未調整筆數", len(skipped), "期間", dates.iloc[0].date(), "～", dates.iloc[-1].date())
    print("持有", bh)
    print("最佳", best[1], best[2])


if __name__ == "__main__":
    main()
