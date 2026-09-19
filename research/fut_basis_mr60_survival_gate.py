"""FUT.basis天條一MDD（`PENDING_QUEUE.md`「順帶」交辦，2026-09-19）。

`fut_basis_mean_reversion_60d`（#19）是全專案至今唯一通過三條事前登記
判準的候選（`FUT_LEADS.md` #19）。這支腳本補天條一（MDD≤50%，硬約束）
的檢驗，依`MARATHON_PROTOCOL.md`「1a-0d.生存門檻」正式記錄判定。

**倉位邏輯完全複製`fut_cheap_gate.py::hyp_basis_mean_reversion()`**
（不改動該檔案本身，這裡只是為了取得完整權益曲線而重算一次同樣的
position/return序列——`_permutation_test()`內部只回傳統計量，不回傳
權益曲線，MDD計算需要完整逐日路徑）：
`position[t] = -sign(basis_pct[t] - trailing_mean_60d(basis_pct)[t-1])`，
`strat_ret[t] = position[t-1] * ret[t]`（無前視，`_permutation_test()`
docstring明文的shift-by-1慣例）。

holdout紀律：只到VAL_END，不碰HOLDOUT。零新增API呼叫（全用
`continuous_contract.py`既有本機快取）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from continuous_contract import build_continuous_series
import fut_basis_series
from validation import holdout

REPO_ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))
MDD_SURVIVAL_THRESHOLD_PCT = -50.0
WINDOW = 60

BEAR_SEGMENTS = {
    "2008金融海嘯": ("2008-05-01", "2008-11-30"),
    "2011歐債危機": ("2011-07-01", "2011-12-31"),
    "2015中國股災": ("2015-06-01", "2015-09-30"),
    "2018Q4貿易戰": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


def load_series() -> pd.DataFrame:
    series, skipped = build_continuous_series()
    if skipped:
        print(f"  [note] {len(skipped)}筆轉倉事件無乾淨調整比例，沿用未調整價格")
    series = series.sort_values("date").reset_index(drop=True)
    series["ret"] = series["adj_close"].pct_change()
    series["date"] = pd.to_datetime(series["date"])
    series = series[series["date"] <= pd.Timestamp(holdout.VAL_END)].reset_index(drop=True)
    holdout.assert_no_holdout_leakage(series, context="fut_basis_mr60_survival_gate")
    basis = fut_basis_series.build_basis_series()[["date", "basis_pct"]]
    basis["date"] = pd.to_datetime(basis["date"])
    merged = series.merge(basis, on="date", how="inner").sort_values("date").reset_index(drop=True)
    return merged


def compute_mdd(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min() * 100)


def segment_mdd(equity_curve: pd.DataFrame, start: str, end: str) -> float | None:
    w = equity_curve[(equity_curve["date"] >= start) & (equity_curve["date"] <= end)]
    if w.empty:
        return None
    pre = equity_curve[equity_curve["date"] <= w["date"].iloc[0]]
    running_peak = pre["equity"].max() if not pre.empty else w["equity"].iloc[0]
    combined = pd.concat([pd.Series([running_peak]), w["equity"]], ignore_index=True)
    running_max = combined.cummax()
    dd = combined / running_max - 1.0
    return float(dd.min() * 100)


def main() -> None:
    merged = load_series()
    print(f"資料範圍：{merged['date'].min().date()} ~ {merged['date'].max().date()}，n={len(merged)}天")

    trailing_mean = merged["basis_pct"].rolling(WINDOW).mean().shift(1)
    deviation = merged["basis_pct"] - trailing_mean
    position = -np.sign(deviation)
    strat_ret = position.shift(1).fillna(0.0) * merged["ret"]
    valid = strat_ret.notna()
    strat_ret = strat_ret[valid].reset_index(drop=True)
    dates = merged.loc[valid, "date"].reset_index(drop=True)

    equity = (1 + strat_ret).cumprod()
    equity_curve = pd.DataFrame({"date": dates, "equity": equity})

    overall_mdd = compute_mdd(equity_curve["equity"])
    seg_mdds = {name: segment_mdd(equity_curve, s, e) for name, (s, e) in BEAR_SEGMENTS.items()}
    worst_seg = min((v for v in seg_mdds.values() if v is not None), default=overall_mdd)
    binding = overall_mdd if overall_mdd <= worst_seg else worst_seg
    verdict = "PASS" if binding >= MDD_SURVIVAL_THRESHOLD_PCT else "VIOLATES_SURVIVAL"

    total_return_pct = float(equity_curve["equity"].iloc[-1] - 1) * 100

    print(f"\n全期總報酬：{total_return_pct:+.1f}%")
    print(f"全期MDD：{overall_mdd:.2f}%")
    for name, v in seg_mdds.items():
        print(f"  {name}: {'無資料' if v is None else f'{v:.2f}%'}")
    print(f"\n天條一（MDD不得超過50%）判定：{verdict}（binding={binding:.2f}%）")

    out = {"generated_at": datetime.now(TZ).isoformat(), "strategy": "fut_basis_mean_reversion_60d",
           "total_return_pct": round(total_return_pct, 1), "overall_mdd_pct": round(overall_mdd, 2),
           "segment_mdds_pct": {k: (round(v, 2) if v is not None else None) for k, v in seg_mdds.items()},
           "mdd_survival_threshold_pct": MDD_SURVIVAL_THRESHOLD_PCT, "verdict": verdict}
    out_path = REPO_ROOT / "research" / "data" / "fut_basis_mr60_survival_gate_result.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n結果已寫入 {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
