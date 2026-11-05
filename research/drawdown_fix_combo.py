"""先.一五二-1 ②「多策略組合」：用 drawdown_fix.py 存的各家族原版日曲線，挑相關性低的 3～5 支等權（每日再平衡）
看能不能「報酬不縮水、回撤變淺」。零請求、描述性，不是判定。

〔自行裁量〕
- 共同期間＝所有成員都有資料的日期交集（F18 只從 2020-10 起，期間太短，預設排除；F15／F16 為美元計價，未換匯，照實揭露）。
- 每日再平衡、不計再平衡成本（各成員自身成本已含在曲線裡；組合層成本另計會更低估，照實揭露）。
- 「報酬不縮水」的基準＝成員原版年化的中位數；在年化 ≥ 基準的組合裡取 MDD 最淺者。
用法：python research/drawdown_fix_combo.py
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
D = HERE / "data" / "drawdown_fix"
EXCLUDE = {"F18"}
TARGETS = (0.15, 0.20, 0.25)
MARGIN_RATE = 0.065 / 252.0  # 組合槓桿用台股融資利率近似（美股成員未換匯，照實揭露）


def stats(curve, dates):
    yrs = (dates[-1] - dates[0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    dr = np.diff(curve) / curve[:-1]
    sh = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    return float(cagr), mdd, sh


def main():
    rets = {}
    for p in sorted(D.glob("curve_F*.csv")):
        fid = p.stem.split("_")[1]
        if fid in EXCLUDE:
            continue
        c = pd.read_csv(p, parse_dates=["date"]).set_index("date")["orig"]
        rets[fid] = c.pct_change()
    R = pd.DataFrame(rets).dropna()
    dates = R.index
    print(f"成員 {list(R.columns)}；共同期間 {dates[0].date()}～{dates[-1].date()}（{len(R)} 日）")
    corr = R.corr()
    single = {f: stats(np.cumprod(1 + R[f].to_numpy()), dates) for f in R.columns}
    rows = []
    for k in (3, 4, 5):
        for combo in itertools.combinations(R.columns, k):
            sub = corr.loc[list(combo), list(combo)].to_numpy()
            avg_corr = float(sub[np.triu_indices(k, 1)].mean())
            for wmode in ("等權", "反波動"):
                if wmode == "等權":
                    w = np.full(k, 1 / k)
                else:
                    v = R[list(combo)].rolling(60, min_periods=60).std().shift(1)
                    iv = 1 / v
                    wdf = iv.div(iv.sum(axis=1), axis=0).fillna(1 / k)
                r = (R[list(combo)].to_numpy() @ w) if wmode == "等權" else (R[list(combo)] * wdf).sum(axis=1).to_numpy()
                cg, md, sh = stats(np.concatenate([[1.0], np.cumprod(1 + r)]), dates.insert(0, dates[0]))
                base = float(np.median([single[f][0] for f in combo]))
                lev = {}
                for tgt in TARGETS:
                    for L in np.round(np.arange(1.0, 3.0001, 0.05), 2):
                        rl = L * r - (L - 1.0) * MARGIN_RATE
                        c2, m2, s2 = stats(np.concatenate([[1.0], np.cumprod(1 + rl)]), dates.insert(0, dates[0]))
                        if c2 >= tgt:
                            lev[f"L_{tgt}"], lev[f"mdd_{tgt}"] = float(L), m2
                            break
                rows.append({"members": "+".join(combo), "k": k, "weight": wmode, "avg_corr": avg_corr, "cagr": cg, "mdd": md,
                             "sharpe": sh, "calmar": cg / abs(md), "median_member_cagr": base,
                             "worst_member_mdd": float(min(single[f][1] for f in combo)), "ok_return": cg >= base - 1e-9, **lev})
    df = pd.DataFrame(rows)
    ok = df[df["ok_return"]].sort_values("mdd", ascending=False)
    out = {"period": [str(dates[0].date()), str(dates[-1].date())], "members": list(R.columns),
           "single": {f: {"cagr": v[0], "mdd": v[1], "sharpe": v[2]} for f, v in single.items()},
           "corr": corr.round(3).to_dict(), "n_combos": int(len(df)), "n_ok_return": int(len(ok)),
           "best_same_return": ok.head(10).to_dict("records"),
           "best_calmar": df.sort_values("calmar", ascending=False).head(10).to_dict("records"),
           "lowest_corr": df.sort_values("avg_corr").head(5).to_dict("records"),
           "levered_to_target": {str(t): df.dropna(subset=[f"mdd_{t}"]).sort_values(f"mdd_{t}", ascending=False).head(5).to_dict("records")
                                 for t in TARGETS}}
    (D / "combo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"組合 {len(df)} 個，年化 ≥ 成員中位數者 {len(ok)} 個")
    for r in ok.head(5).to_dict("records"):
        print(f"  {r['members']} {r['weight']} 年化 {r['cagr']:+.1%} MDD {r['mdd']:.1%} Calmar {r['calmar']:.2f}（成員中位年化 {r['median_member_cagr']:+.1%}）")
    for t in TARGETS:
        for r in out["levered_to_target"][str(t)][:2]:
            print(f"  槓桿調到 {t:.0%}：{r['members']} {r['weight']} L'={r[f'L_{t}']} MDD {r[f'mdd_{t}']:.1%}")


if __name__ == "__main__":  # noqa: E305
    main()
