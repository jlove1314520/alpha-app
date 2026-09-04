"""Step 2 of the multi-commodity cross-sectional groundwork flagged in
CALIBRATION_PROBE.md (2026-09-03 decree) / FUT_LEADS.md round 328: round 332
confirmed MTX/TE/TF all have usable TaiwanFuturesDaily depth; this round
(333) builds the first actual pooled daily-return panel across TX/MTX/TE
(TF excluded per round 332's finding that it has no night-session data,
which would make it an inconsistent member of any future night-session
pooling design -- kept out of the day-session pool too for now so all three
members are on equal footing; TF can be added back later if a day-only pool
design is chosen).

This is pure infrastructure (MARATHON_PROTOCOL.md 1c): builds the panel and
reports descriptive stats (overlap window, pairwise correlation, coverage).
It does NOT test any factor or strategy on the panel, so no TRIALS_LEDGER
row -- same precedent as fut_probe_multi_commodity.py last round.

Getting here required a real generalization bug fix in continuous_contract.py
this round (load_session() previously silently assumed every contract's
non-spread rows have a plain 6-digit YYYYMM contract_date; MTX has carried
weekly contracts, e.g. "201308W1", since 2013-07-31 -- about 10.3% of MTX's
non-spread rows -- which crashed the int() cast before this round's fix).
Session is day ("position") only for now -- TX/MTX/TE all have night session
too (round 332), but pooling night alongside day is a separate design
decision (bar-timing alignment, whether to treat night+day as one trading
day or two rows) left for whoever picks this direction back up.

Read-only, reuses continuous_contract.build_continuous_series() which itself
reuses finmind_client.load_dev() (dev-capped). Zero new API calls expected:
TX/MTX/TE full-history "position" session data was already pulled into the
local cache by round 332 (fut_probe_multi_commodity.py, same window) and
earlier TX rounds.
"""
from __future__ import annotations

import pandas as pd

from continuous_contract import build_continuous_series

COMMODITIES = ["TX", "MTX", "TE"]


def build_return_panel(session: str = "position") -> pd.DataFrame:
    """Wide panel indexed by date, one adj_close-based simple daily return
    column per commodity (outer join -- deliberately keeps every commodity's
    full date range rather than pre-truncating to the overlap, so the
    overlap window itself can be measured and reported rather than assumed).
    """
    frames = {}
    for c in COMMODITIES:
        series, skipped = build_continuous_series(contract=c, session=session)
        if skipped:
            print(f"警告：{c} 有 {len(skipped)} 筆轉倉skipped_events（無調整比率），詳見continuous_contract.py")
        s = series.set_index("date")["adj_close"].sort_index()
        ret = s.pct_change()
        ret.name = c
        frames[c] = ret
    panel = pd.concat(frames.values(), axis=1)
    panel.columns = list(frames.keys())
    return panel


def summarize(panel: pd.DataFrame) -> dict:
    overlap = panel.dropna(how="any")
    coverage = {c: int(panel[c].notna().sum()) for c in panel.columns}
    corr = overlap.corr()
    ann_stats = {
        c: {
            "n_days": int(panel[c].notna().sum()),
            "date_min": str(panel[c].dropna().index.min().date()),
            "date_max": str(panel[c].dropna().index.max().date()),
            "mean_ann_pct": float(panel[c].mean() * 252 * 100),
            "std_ann_pct": float(panel[c].std() * (252 ** 0.5) * 100),
        }
        for c in panel.columns
    }
    return {
        "coverage_days": coverage,
        "overlap_window": (str(overlap.index.min().date()), str(overlap.index.max().date())) if not overlap.empty else None,
        "overlap_n_days": len(overlap),
        "pairwise_corr": corr.round(3).to_dict(),
        "per_commodity_stats": ann_stats,
    }


if __name__ == "__main__":
    panel = build_return_panel(session="position")
    summary = summarize(panel)

    print("=== 每商品覆蓋天數與日期範圍 ===")
    for c, stats in summary["per_commodity_stats"].items():
        print(f"  {c}: {stats['n_days']} 天 ({stats['date_min']} ~ {stats['date_max']}), "
              f"年化均報酬 {stats['mean_ann_pct']:.2f}%, 年化波動 {stats['std_ann_pct']:.2f}%")

    print(f"\n=== 三商品同時有資料的重疊窗口 ===")
    print(f"  {summary['overlap_window']}, 共 {summary['overlap_n_days']} 個交易日")

    print("\n=== 重疊窗口內日報酬相關係數矩陣 ===")
    print(pd.DataFrame(summary["pairwise_corr"]))

    print("\n（本腳本純建構資料池＋描述統計，不含任何因子/策略檢定，不寫入TRIALS_LEDGER.md）")
