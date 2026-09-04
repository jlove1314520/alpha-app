"""Round 344 (FUT) — liquidity screen for the individual-stock-futures (F-suffix)
candidate pool discovered in round 341 (fut_probe_stock_futures_info.py; that
script itself no longer exists on disk -- see FUT_LOG.md round 344 entry for
the anomaly note -- but its cached output, TaiwanFutOptDailyInfo, is still on
disk and reused here with zero new API calls for step 1).

Round 341 left three explicit unverified gaps before the ~509/517 F-suffix
codes can be treated as a real cross-sectional candidate pool:
  (a) liquidity -- unknown what fraction have adequate volume/open interest
  (b) dispersion -- not yet measured with the round 338 dispersion_ratio/PCA method
  (c) rollover rules -- unknown whether H1-style rollover (continuous_contract.py)
      applies the same way as index futures

This script tackles (a) only, on a bounded stratified sample (not all ~517,
to keep this one work unit's API usage bounded per MARATHON_PROTOCOL.md 1c).
(b) and (c) are explicitly left for a future round.

Methodology: front-month, day-session ("position") volume over calendar year
2024 (the last full year inside the holdout boundary), reusing
continuous_contract.load_session()/front_month_series() so filtering logic
(single-month contract_date, session) stays in one place rather than
duplicated here.

Liquidity threshold (pre-registered before looking at results, in the spirit
of MARATHON_PROTOCOL.md section 2's hash-lock discipline -- this is a
foundation/infrastructure check not a factor test so it does not need a
TRIALS_LEDGER entry, but the same "decide the bar before you look" discipline
still applies to keep this honest):
  - >=200 trading days with a front-month quote in 2024 (out of ~245 trading
    days), i.e. the contract was actively trading most of the year, AND
  - mean front-month day-session volume over those days >= 50 contracts/day.
Both conditions chosen to be a low, permissive bar (not the bar a strategy
would actually need) -- this is a first-pass filter to size the *maximum
plausible* liquid subset, not a final trading-liquidity determination.
"""

import sys
import time

import pandas as pd

from continuous_contract import load_session, front_month_series

CANDIDATE_CACHE = "data/raw/TaiwanFutOptDailyInfo__ALL__2024-12-30__2024-12-30.parquet"
SCREEN_YEAR_START = "2024-01-01"
SCREEN_YEAR_END = "2024-12-31"
MIN_ACTIVE_DAYS = 200
MIN_MEAN_VOLUME = 50
SAMPLE_STRIDE = 15  # every 15th code across the sorted F-suffix list -> ~34 samples out of ~517


def load_candidates() -> list[str]:
    df = pd.read_parquet(CANDIDATE_CACHE)
    fut = df[df["type"] == "TaiwanFuturesDaily"].copy()
    f_suffix = sorted(set(fut[fut["code"].str.endswith("F")]["code"].tolist()))
    return f_suffix


def screen_one(code: str) -> dict:
    raw = load_session(contract=code, session="position",
                        start_date=SCREEN_YEAR_START, end_date=SCREEN_YEAR_END)
    if raw.empty:
        return {"code": code, "active_days": 0, "mean_volume": 0.0, "liquid": False, "note": "no rows"}
    front = front_month_series(raw)
    if front.empty:
        return {"code": code, "active_days": 0, "mean_volume": 0.0, "liquid": False, "note": "no front-month rows"}
    active_days = len(front)
    mean_volume = float(front["volume"].mean())
    liquid = active_days >= MIN_ACTIVE_DAYS and mean_volume >= MIN_MEAN_VOLUME
    return {"code": code, "active_days": active_days, "mean_volume": round(mean_volume, 1), "liquid": liquid, "note": ""}


def main():
    candidates = load_candidates()
    print(f"F-suffix候選總數（去重）：{len(candidates)}")

    sample = candidates[::SAMPLE_STRIDE]
    # round 341 already cached CDF/CCF full-history -- fold them into the
    # sample too (zero extra API cost) rather than wasting that prior work.
    for extra in ("CDF", "CCF"):
        if extra not in sample:
            sample.append(extra)
    sample = sorted(set(sample))
    print(f"本輪抽樣數：{len(sample)}（含round341既有快取CDF/CCF）")

    results = []
    for i, code in enumerate(sample):
        try:
            r = screen_one(code)
        except Exception as e:  # noqa: BLE001 -- foundation probe script, log and continue per code
            print(f"  [{i+1}/{len(sample)}] {code}: 例外 {type(e).__name__}: {e}", file=sys.stderr)
            r = {"code": code, "active_days": 0, "mean_volume": 0.0, "liquid": False, "note": f"exception: {e}"}
        results.append(r)
        print(f"  [{i+1}/{len(sample)}] {code}: active_days={r['active_days']} mean_vol={r['mean_volume']} liquid={r['liquid']}")
        time.sleep(0.3)  # gentle pacing; _fetch()'s own throttle/retry handles real rate limits

    out = pd.DataFrame(results)
    out_path = "data/fut_stock_futures_liquidity_screen_round344.csv"
    out.to_csv(out_path, index=False)

    n_liquid = int(out["liquid"].sum())
    n_sample = len(out)
    pct = 100.0 * n_liquid / n_sample if n_sample else 0.0
    print(f"\n樣本內達門檻（active_days>={MIN_ACTIVE_DAYS} 且 mean_volume>={MIN_MEAN_VOLUME}）："
          f"{n_liquid}/{n_sample} ({pct:.1f}%)")
    print(f"外推估計：全體{len(candidates)}檔F結尾候選中約有 {pct/100*len(candidates):.0f} 檔可能達到此低門檻")
    print(f"結果已存：{out_path}")


if __name__ == "__main__":
    main()
