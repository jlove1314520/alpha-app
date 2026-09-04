"""Round 335 left three options for the "cross-sectional multi-commodity
pool" direction; this round does option (a): quantify whether the overlap
window's cross-sectional dispersion (TX/MTX/TE) is actually large enough to
give a permutation test any statistical power, rather than assuming it is
or isn't from the pairwise correlations alone.

Round 335's pairwise correlations (0.997 / 0.955 / 0.954) already hinted at
the problem qualitatively ("all three are wrappers around the same market
beta"). This round makes it quantitative:

1. Daily cross-sectional dispersion: for each day in the overlap window,
   std() across the 3 commodities' simple returns that day. If the 3 series
   were independent with similar marginal vol, this cross-sectional std
   should be comparable in magnitude to each commodity's own (time-series)
   daily std. If they're near-perfectly correlated, cross-sectional std
   shrinks toward 0 regardless of how large each commodity's own vol is,
   because on any given day all 3 move almost the same amount.
2. dispersion_ratio = mean(daily cross-sectional std) / mean(per-commodity
   time-series std). This is the single number that answers round 335's
   question directly: how much of each commodity's own volatility survives
   as cross-sectional (exploitable, long-short) dispersion versus being
   common-factor noise that a long-short pool can't monetize.
3. PCA on the correlation matrix (eigenvalues of the 3x3 corr matrix): the
   share of total variance explained by PC1 is a second, independent way to
   see the same thing -- if PC1 explains e.g. 98% of variance, only ~2% of
   the system's total variance is idiosyncratic (potentially useful)
   cross-sectional signal, no matter how many days of history are pooled.

This is still pure diagnostic infrastructure (MARATHON_PROTOCOL.md 1c), not
a factor/strategy test -- no TRIALS_LEDGER row, same precedent as round
332/333's fut_probe_multi_commodity.py / fut_multi_commodity_pool.py.

Read-only, reuses fut_multi_commodity_pool.build_return_panel() which itself
reuses continuous_contract.build_continuous_series() -> finmind_client.
load_dev() (dev-capped, holdout-safe). Zero new API calls expected: same
TX/MTX/TE full-history "position" session data already cached by round 332.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fut_multi_commodity_pool import build_return_panel


def compute_dispersion(panel: pd.DataFrame) -> dict:
    overlap = panel.dropna(how="any")
    if overlap.empty:
        raise ValueError("重疊窗口為空，無法計算離散度")

    daily_cs_std = overlap.std(axis=1, ddof=0)
    daily_cs_range = overlap.max(axis=1) - overlap.min(axis=1)
    marginal_std = overlap.std(axis=0, ddof=0)
    avg_marginal_std = float(marginal_std.mean())
    dispersion_ratio = float(daily_cs_std.mean() / avg_marginal_std) if avg_marginal_std > 0 else float("nan")

    corr = overlap.corr()
    eigvals = np.linalg.eigvalsh(corr.values)[::-1]
    eigvals = np.clip(eigvals, 0, None)
    pc1_share = float(eigvals[0] / eigvals.sum())

    return {
        "n_days": int(len(overlap)),
        "window": (str(overlap.index.min().date()), str(overlap.index.max().date())),
        "avg_cs_std_daily_pct": float(daily_cs_std.mean() * 100),
        "median_cs_std_daily_pct": float(daily_cs_std.median() * 100),
        "avg_cs_range_daily_pct": float(daily_cs_range.mean() * 100),
        "per_commodity_marginal_std_daily_pct": {c: float(marginal_std[c] * 100) for c in overlap.columns},
        "avg_marginal_std_daily_pct": float(avg_marginal_std * 100),
        "dispersion_ratio": dispersion_ratio,
        "corr_eigenvalues": [float(v) for v in eigvals],
        "pc1_variance_share": pc1_share,
    }


if __name__ == "__main__":
    panel = build_return_panel(session="position")
    r = compute_dispersion(panel)

    print(f"=== 重疊窗口 {r['window'][0]} ~ {r['window'][1]}（{r['n_days']}個交易日）===\n")

    print("=== 各商品自身時序日報酬標準差（邊際波動） ===")
    for c, v in r["per_commodity_marginal_std_daily_pct"].items():
        print(f"  {c}: {v:.4f}%/日")
    print(f"  三商品平均: {r['avg_marginal_std_daily_pct']:.4f}%/日")

    print("\n=== 橫斷面（跨商品）每日離散度 ===")
    print(f"  每日std(3商品當日報酬)的平均: {r['avg_cs_std_daily_pct']:.4f}%")
    print(f"  每日std(3商品當日報酬)的中位數: {r['median_cs_std_daily_pct']:.4f}%")
    print(f"  每日range(max-min)的平均: {r['avg_cs_range_daily_pct']:.4f}%")

    print(f"\n=== 離散度比值 dispersion_ratio = 橫斷面std / 邊際std平均 ===")
    print(f"  {r['dispersion_ratio']:.4f}")
    print("  （若三商品互相獨立、邊際波動相近，此比值應接近1；")
    print("   若三商品幾乎完全同向，此比值會趨近0，")
    print("   代表個股自身的波動幾乎全是共同因子，橫斷面幾乎沒有可供多空配對的殘餘離散度）")

    print(f"\n=== 相關矩陣特徵值分解（PCA） ===")
    print(f"  特徵值（由大到小）: {[round(v, 4) for v in r['corr_eigenvalues']]}")
    print(f"  PC1解釋變異比例: {r['pc1_variance_share']*100:.2f}%")
    print("  （PC1解釋比例越接近100%，代表整個系統幾乎只有一個共同因子，")
    print("   剩下能被橫斷面多空策略利用的獨立變異比例 = 1 - PC1解釋比例，越小越沒有戲）")

    print("\n（本腳本純診斷統計，不含任何因子/策略檢定，不寫入TRIALS_LEDGER.md）")
