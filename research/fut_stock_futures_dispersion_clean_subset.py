"""Round 349 (FUT) follows up on round 348's next-step (a)+(b): the 19-code
dispersion/PCA result (dispersion_ratio=1.6371, PC1=27.33%) came from an
overlap window of only 250 trading days (2023-12-19~2024-12-31), dragged
down by the latest-listed member (SXF), and 11/19 codes had non-zero
`skipped_rollover_events` (JWF worst at 37) -- a rollover data-quality gap
flagged as unresolved.

This round does NOT re-fetch anything (all 19 codes already cached from
round 347/348's `build_continuous_series()` calls via `finmind_client.
load_dev()`) -- it re-runs the same dispersion/PCA method (imported, not
duplicated, from `fut_stock_futures_dispersion_test.py`) on two narrower,
cleaner subsets of the same 19-code panel:

  (b) clean_subset: the 8 codes with n_skipped_rollover_events == 0 in
      round 348's coverage table (CCF/CDF/OLF/PAF/QRF/RFF/RUF/ZFF) --
      addresses the rollover data-quality gap directly, at the cost of
      still being capped by RUF's 2023-08-02 start.
  (a) long_history_subset: the 4 codes that are BOTH 0-skipped AND have
      a listing date on or before 2018-05-03 (CCF/CDF/OLF/PAF) -- drops
      the three newest 0-skipped codes (QRF/RFF/RUF, all 2021+) to buy
      window length instead, since round 348 flagged the short window as
      a limitation.

Zero new API calls (both subsets are strict subsets of round 348's already-
cached 19-code universe). Pure diagnostic infrastructure (MARATHON_PROTOCOL.
md 1c) -- no factor/strategy tested, no TRIALS_LEDGER row, same precedent as
round 332/333/335/338/341/344/348's probe scripts.
"""
from __future__ import annotations

import pandas as pd

from fut_stock_futures_dispersion_test import CODES, build_return_panel, compute_dispersion

CLEAN_SUBSET = ["CCF", "CDF", "OLF", "PAF", "QRF", "RFF", "RUF", "ZFF"]
LONG_HISTORY_SUBSET = ["CCF", "CDF", "OLF", "PAF"]


def report(name: str, codes: list[str], panel: pd.DataFrame) -> dict | None:
    sub = panel[codes]
    overlap = sub.dropna(how="any")
    print(f"\n=== {name}（{len(codes)}檔：{','.join(codes)}） ===")
    if overlap.empty:
        print("  重疊窗口為空，無法計算。")
        return None
    r = compute_dispersion(sub)
    print(f"  重疊窗口：{r['window'][0]} ~ {r['window'][1]}，共 {r['n_days']} 個交易日")
    print(f"  dispersion_ratio: {r['dispersion_ratio']:.4f}（round347/348 19檔版：1.6371；round338 TX/MTX/TE：0.1143）")
    print(f"  PC1解釋變異: {r['pc1_variance_share']*100:.2f}%（round347/348 19檔版：27.33%；round338 TX/MTX/TE：97.91%）")
    print(f"  PC1+PC2+PC3: {r['pc1_3_variance_share']*100:.2f}%")
    print(f"  平均兩兩相關係數: {r['mean_pairwise_corr']:.4f}")
    return {"subset": name, "n_codes": len(codes), **{k: v for k, v in r.items() if k != "window"},
            "window_start": r["window"][0], "window_end": r["window"][1]}


if __name__ == "__main__":
    print("=== round348 19檔F結尾個股期貨面板重跑：兩個乾淨子集（不重抓資料，全部命中快取） ===")
    panel, skip_counts = build_return_panel(CODES, session="position")

    print("\n（沿用round348已快取的skipped_rollover_events；本輪不重新計算，只重用CODES常數確保面板一致）")
    for c in CLEAN_SUBSET:
        assert skip_counts.get(c) == 0, f"{c} 的 skipped_rollover_events 非0，子集假設不成立：{skip_counts.get(c)}"

    rows = []
    r_clean = report("(b) 資料品質乾淨子集：8檔0-skipped_rollover_events", CLEAN_SUBSET, panel)
    if r_clean:
        rows.append(r_clean)
    r_long = report("(a) 長窗口子集：4檔0-skipped且2018年前掛牌", LONG_HISTORY_SUBSET, panel)
    if r_long:
        rows.append(r_long)

    if rows:
        pd.DataFrame(rows).to_csv("data/fut_stock_futures_dispersion_clean_subset_round349.csv", index=False)
        print("\n已存結果：data/fut_stock_futures_dispersion_clean_subset_round349.csv")

    print("\n（本腳本純診斷統計，重用round347/348已快取資料，零新增API呼叫，不含任何因子/策略檢定，不寫入TRIALS_LEDGER.md）")
