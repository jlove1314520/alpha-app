"""Futures track, marathon round (2026-08-24): infra probe for TW_MARATHON_STATE.md's
/ FUT_MARATHON_STATE.md's "下一輪建議工作單位" candidate (c) -- 三大法人期貨部位
(directional institutional-investor futures positions), as distinct from the
non-directional `open_interest` column already used in `fut_oi_price_confirm_5d`
(FAILed, see FUT_LOG.md 2026-08-24T06:32).

`DATA.md` section 6 already confirmed the dataset name (`TaiwanFuturesInstitutionalInvestors`,
data_id="TX"), the field list, and that the previously-suspected `institutional_investors`
encoding garble was a terminal display artifact, not a real data problem -- but that
was only verified on a narrow 5-day window (2024-06-03..2024-06-07). This is a genuine
infra gap per FUT_MARATHON_STATE.md: "需要先做小型地基工作（確認端點、欄位格式）才能測".

This script does ONLY the infra work for this round -- fetch the full history
(matching continuous_contract.py's FULL_HISTORY_START/END, so it can be joined
against the existing continuous-contract OI series later), and validate:
  1. Which institutional_investors category labels actually appear (expect exactly
     the three known ones: 外資, 投信, 自營商).
  2. Date coverage / gaps vs. the existing TaiwanFuturesDaily cache for the same range.
  3. NaN / zero / negative sanity on the position-balance columns.
  4. Whether the three categories' long_open_interest_balance_volume sum reconciles
     against continuous_contract's aggregate `open_interest` column (a real
     cross-check, not just eyeballing one dataset in isolation).

Deliberately does NOT build a factor/strategy or run fut_cheap_gate.py in this round --
per MARATHON_PROTOCOL.md 1c, infra ("地基") and hypothesis testing are separate work
units, and this dataset has never been pulled for the full 2000-2024 range before, so
its shape needs to be seen before any signal construction is designed around it.
"""
from __future__ import annotations

import pandas as pd

import finmind_client
from continuous_contract import (
    FULL_HISTORY_START,
    FULL_HISTORY_END,
    build_continuous_series,
    load_position_session,
)


def probe() -> None:
    print(f"Fetching TaiwanFuturesInstitutionalInvestors TX {FULL_HISTORY_START}..{FULL_HISTORY_END} "
          "(load_dev, VAL_END-capped, single network call if not already cached)...")
    df = finmind_client.load_dev(
        dataset="TaiwanFuturesInstitutionalInvestors",
        data_id="TX",
        start_date=FULL_HISTORY_START,
        end_date=FULL_HISTORY_END,
    )
    print(f"\nRows fetched: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    if df.empty:
        print("EMPTY RESULT -- stopping here, nothing more to validate.")
        return

    # Write category labels to a UTF-8 file rather than trusting console codepage,
    # per the exact lesson learned in fut_probe_institutional_encoding.py / DATA.md.
    categories = sorted(df["institutional_investors"].dropna().unique().tolist())
    with open("data/fut_institutional_categories_utf8.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(categories))
    print(f"\nDistinct institutional_investors category count: {len(categories)} "
          "(labels written to data/fut_institutional_categories_utf8.txt, "
          "not printed to console -- see encoding-artifact lesson in DATA.md)")

    # Date coverage: unique trading dates in this dataset vs. TaiwanFuturesDaily
    # cache for the same range (position dataset should be a subset/match of
    # trading days, since it's derived from daily settlement reporting).
    dates_inst = set(df["date"].unique())
    print(f"\nDistinct dates in institutional-investors dataset: {len(dates_inst)}")
    print(f"Date range: {min(dates_inst)} .. {max(dates_inst)}")

    daily_df = finmind_client.load_dev(
        dataset="TaiwanFuturesDaily",
        data_id="TX",
        start_date=FULL_HISTORY_START,
        end_date=FULL_HISTORY_END,
    )
    dates_daily = set(daily_df["date"].unique()) if not daily_df.empty else set()
    print(f"Distinct dates in TaiwanFuturesDaily (already-cached): {len(dates_daily)}")
    missing_from_inst = dates_daily - dates_inst
    extra_in_inst = dates_inst - dates_daily
    print(f"Trading dates present in TaiwanFuturesDaily but MISSING from institutional-investors: "
          f"{len(missing_from_inst)}")
    print(f"Dates present in institutional-investors but NOT in TaiwanFuturesDaily: "
          f"{len(extra_in_inst)}")
    if missing_from_inst:
        sample_missing = sorted(missing_from_inst)[:5]
        print(f"  sample missing dates: {sample_missing}")

    # Row count per date -- expect exactly 3 rows/date (one per category) if the
    # dataset is clean and complete.
    rows_per_date = df.groupby("date").size()
    print(f"\nRows per date -- min={rows_per_date.min()}, max={rows_per_date.max()}, "
          f"mode={rows_per_date.mode().iloc[0]}")
    dates_not_3 = rows_per_date[rows_per_date != 3]
    print(f"Dates with row count != 3: {len(dates_not_3)}")
    if len(dates_not_3) > 0:
        print(f"  sample: {dates_not_3.head(5).to_dict()}")

    # NaN / zero / negative sanity on the position-balance columns.
    numeric_cols = [
        "long_deal_volume", "long_deal_amount", "short_deal_volume", "short_deal_amount",
        "long_open_interest_balance_volume", "long_open_interest_balance_amount",
        "short_open_interest_balance_volume", "short_open_interest_balance_amount",
    ]
    present_numeric_cols = [c for c in numeric_cols if c in df.columns]
    print(f"\nNumeric columns present: {present_numeric_cols}")
    for col in present_numeric_cols:
        n_nan = df[col].isna().sum()
        n_neg = (df[col] < 0).sum()
        n_zero = (df[col] == 0).sum()
        print(f"  {col}: NaN={n_nan}, negative={n_neg}, zero={n_zero} (of {len(df)})")

    # Cross-check: sum of the 3 categories' long_open_interest_balance_volume vs.
    # continuous_contract's aggregate `open_interest` for the same dates. This is
    # NOT expected to match exactly (aggregate OI counts ALL market participants,
    # institutional-investors dataset only covers the 3 reported categories, retail
    # is excluded) -- the point is to see the *ratio*, which tells us how much of
    # total OI these 3 categories represent (a sanity signal, not an equality check).
    print("\nCross-check vs. continuous_contract aggregate open_interest (ratio check, "
          "NOT expected to be 1.0 -- institutional categories exclude retail):")
    cc_df, _skipped = build_continuous_series()
    cc_oi = cc_df[["date", "open_interest"]].dropna().copy()
    cc_oi["date"] = cc_oi["date"].astype(str)
    inst_long_sum = df.groupby("date")["long_open_interest_balance_volume"].sum().reset_index()
    inst_long_sum.columns = ["date", "inst_long_oi_sum"]
    inst_long_sum["date"] = inst_long_sum["date"].astype(str)
    merged = cc_oi.merge(inst_long_sum, on="date", how="inner")
    if len(merged) > 0:
        merged["ratio"] = merged["inst_long_oi_sum"] / merged["open_interest"]
        print(f"  merged rows: {len(merged)}")
        print(f"  ratio (3-category long OI sum / aggregate OI) -- "
              f"min={merged['ratio'].min():.3f}, median={merged['ratio'].median():.3f}, "
              f"max={merged['ratio'].max():.3f}")
        n_ratio_gt1 = (merged["ratio"] > 1.0).sum()
        print(f"  dates where ratio > 1.0 (front-month-only OI vs institutional OI -- "
              f"see corrected all-contract-months check below before treating this as a red flag): "
              f"{n_ratio_gt1}")
    else:
        print("  NO OVERLAPPING DATES between the two datasets -- cannot cross-check.")

    # Corrected apples-to-apples cross-check: continuous_contract's `open_interest`
    # column is FRONT-MONTH-ONLY (see front_month_series() in continuous_contract.py),
    # while TAIFEX institutional-investor OI balances are almost certainly reported
    # across ALL contract months combined, not just the front month. The ratio>1.0
    # cases above are very likely just this aggregation-level mismatch, not a real
    # data problem -- verify by re-doing the sum across all contract months.
    print("\nCorrected cross-check: institutional 3-category long OI sum vs. "
          "ALL-contract-months aggregate open_interest (not just front-month):")
    pos_df = load_position_session("TX", FULL_HISTORY_START, FULL_HISTORY_END)
    all_months_oi = pos_df.groupby("date")["open_interest"].sum().reset_index()
    all_months_oi.columns = ["date", "open_interest_all_months"]
    all_months_oi["date"] = all_months_oi["date"].astype(str)
    merged2 = all_months_oi.merge(inst_long_sum, on="date", how="inner")
    if len(merged2) > 0:
        merged2["ratio2"] = merged2["inst_long_oi_sum"] / merged2["open_interest_all_months"]
        print(f"  merged rows: {len(merged2)}")
        print(f"  ratio (3-category long OI sum / ALL-contract-months OI) -- "
              f"min={merged2['ratio2'].min():.3f}, median={merged2['ratio2'].median():.3f}, "
              f"max={merged2['ratio2'].max():.3f}")
        n_ratio2_gt1 = (merged2["ratio2"] > 1.0).sum()
        print(f"  dates where ratio > 1.0 (this WOULD be a real anomaly if it persists here): "
              f"{n_ratio2_gt1}")
    else:
        print("  NO OVERLAPPING DATES -- cannot cross-check.")

    print("\nDone. This is infra validation only -- no factor/strategy built this round.")


if __name__ == "__main__":
    probe()
