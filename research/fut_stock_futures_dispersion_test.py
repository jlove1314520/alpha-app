"""Round 341 left three explicit gaps before the ~509/517 F-suffix
individual-stock-futures pool can be treated as a real cross-sectional
candidate: (a) liquidity, (b) dispersion, (c) rollover rules. Round 344 did
(a) -- 19/37 sampled codes passed a permissive liquidity bar. This round
does (b): the round-338 dispersion_ratio/PCA method (which found TX/MTX/TE
were 97.9% PC1-driven, i.e. not a usable cross-sectional pool), applied now
to the 19 round-344-liquid codes instead of the three index-family products.

This is the single most important open question for the "individual stock
futures as a cross-sectional pool" direction (FUT_LEADS.md round 344 entry):
a large candidate *count* is worthless if the pool's returns are still
dominated by one common factor the way TX/MTX/TE were -- round 338's lesson
explicitly warned not to assume otherwise just because the pool is bigger
this time.

Rollover-mechanism note (round 341 gap (c), partially addressed here as a
byproduct, not separately investigated): continuous_contract.py's H1 rule
("front month = smallest contract_date with a quote today") is generic over
`contract`, already exercised on 4 products (TX/MTX/TE/TF) plus CDF/CCF
(round 341). This round applies it, unmodified, to all 19 codes and reports
each one's `skipped_events` count -- a clean run (0 skipped) across 19 more
codes is evidence the mechanism generalizes, not proof the underlying
expiry/rollover convention is identical to TX's (that would need reading
each stock future's contract spec), so this is flagged as "still assumed,
now with broader empirical support" rather than "verified".

Read-only, reuses continuous_contract.build_continuous_series() ->
finmind_client.load_dev() (dev-capped, holdout-safe). Full-history pulls
for 17 of the 19 codes are new API calls (CDF/CCF already cached from round
341/344); paced at the client's own RATE_LIMIT_MIN_INTERVAL_SEC, no extra
retry loop added on top per MARATHON_PROTOCOL.md section 4.

Pure diagnostic infrastructure (MARATHON_PROTOCOL.md 1c) -- no factor or
strategy is tested here, so no TRIALS_LEDGER row; same precedent as round
332/333/335/338/341/344's probe scripts.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from continuous_contract import build_continuous_series

CODES = [
    "CCF", "CDF", "EHF", "FYF", "GMF", "HBF", "HQF", "ITF", "JWF", "KKF",
    "NWF", "OLF", "PAF", "QDF", "QRF", "RFF", "RUF", "SXF", "ZFF",
]


def build_return_panel(codes: list[str], session: str = "position") -> tuple[pd.DataFrame, dict]:
    frames = {}
    skip_counts = {}
    for c in codes:
        series, skipped = build_continuous_series(contract=c, session=session)
        skip_counts[c] = len(skipped)
        if skipped:
            print(f"  警告：{c} 有 {len(skipped)} 筆轉倉skipped_events（無調整比率）", file=sys.stderr)
        if series.empty:
            print(f"  警告：{c} 查無資料（空序列）", file=sys.stderr)
            continue
        s = series.set_index("date")["adj_close"].sort_index()
        ret = s.pct_change()
        ret.name = c
        frames[c] = ret
    panel = pd.concat(frames.values(), axis=1)
    panel.columns = list(frames.keys())
    return panel, skip_counts


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
    pc1_3_share = float(eigvals[:3].sum() / eigvals.sum())

    return {
        "n_members": int(overlap.shape[1]),
        "n_days": int(len(overlap)),
        "window": (str(overlap.index.min().date()), str(overlap.index.max().date())),
        "avg_cs_std_daily_pct": float(daily_cs_std.mean() * 100),
        "median_cs_std_daily_pct": float(daily_cs_std.median() * 100),
        "avg_cs_range_daily_pct": float(daily_cs_range.mean() * 100),
        "avg_marginal_std_daily_pct": float(avg_marginal_std * 100),
        "dispersion_ratio": dispersion_ratio,
        "pc1_variance_share": pc1_share,
        "pc1_3_variance_share": pc1_3_share,
        "mean_pairwise_corr": float((corr.values.sum() - len(corr)) / (len(corr) * (len(corr) - 1))),
    }


if __name__ == "__main__":
    print(f"=== 對round344 19檔流動性達標F結尾個股期貨做離散度/PCA測試 ===\n")
    panel, skip_counts = build_return_panel(CODES, session="position")

    print("=== 各商品覆蓋天數與日期範圍（回填全歷史，非僅2024） ===")
    coverage_rows = []
    for c in panel.columns:
        s = panel[c].dropna()
        row = {
            "code": c, "n_days": len(s),
            "date_min": str(s.index.min().date()) if len(s) else None,
            "date_max": str(s.index.max().date()) if len(s) else None,
            "n_skipped_rollover_events": skip_counts.get(c, None),
        }
        coverage_rows.append(row)
        print(f"  {c}: {row['n_days']} 天 ({row['date_min']} ~ {row['date_max']}), "
              f"skipped_rollover_events={row['n_skipped_rollover_events']}")

    overlap = panel.dropna(how="any")
    print(f"\n=== {len(panel.columns)}檔同時有資料的重疊窗口 ===")
    if overlap.empty:
        print("  重疊窗口為空！各商品上市時間差異過大，無法直接算離散度。")
        pd.DataFrame(coverage_rows).to_csv("data/fut_stock_futures_dispersion_coverage_round347.csv", index=False)
        print("已存覆蓋率明細：data/fut_stock_futures_dispersion_coverage_round347.csv")
        raise SystemExit(0)

    print(f"  {overlap.index.min().date()} ~ {overlap.index.max().date()}, 共 {len(overlap)} 個交易日")

    r = compute_dispersion(panel)

    print(f"\n=== 離散度比值 dispersion_ratio（{r['n_members']}檔，橫斷面std/邊際std平均） ===")
    print(f"  {r['dispersion_ratio']:.4f}")
    print(f"  （對照round338 TX/MTX/TE三商品：0.1143）")

    print(f"\n=== 相關矩陣PCA ===")
    print(f"  PC1解釋變異比例: {r['pc1_variance_share']*100:.2f}%")
    print(f"  PC1+PC2+PC3解釋變異比例: {r['pc1_3_variance_share']*100:.2f}%")
    print(f"  （對照round338 TX/MTX/TE三商品PC1: 97.91%）")
    print(f"  平均兩兩相關係數: {r['mean_pairwise_corr']:.4f}")

    coverage_df = pd.DataFrame(coverage_rows)
    coverage_df.to_csv("data/fut_stock_futures_dispersion_coverage_round347.csv", index=False)
    print(f"\n已存覆蓋率明細：data/fut_stock_futures_dispersion_coverage_round347.csv")

    summary = pd.DataFrame([r])
    summary.to_csv("data/fut_stock_futures_dispersion_summary_round347.csv", index=False)
    print(f"已存離散度摘要：data/fut_stock_futures_dispersion_summary_round347.csv")

    print("\n（本腳本純診斷統計，不含任何因子/策略檢定，不寫入TRIALS_LEDGER.md）")
