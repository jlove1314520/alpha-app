# -*- coding: utf-8 -*-
"""先.四十五-一：Bb-90 樣本外單發（2025-01-01～2026-09-30 保留資料，只此一次）。

定義全部事前綁定於 docs/PREREG_bb90_oos_2025.md（登記 #423，SHA256 見該檔 commit 訊息），
已於執行前 commit＋push。**單發只跑一次；結果檔已存在即拒絕重跑；數字一律在 JSON 寫完後才印。**

保留資料守門（validation/holdout.py）：
- `unlock_holdout_once()` 已於 2026-09-26 由 #400 使用，本腳本**不呼叫**它（再呼叫只會被拒）；
- 讀取保留期資料前先以 `assert_no_holdout_leakage()` 自檢本腳本是否已列入 `ALLOWED_HOLDOUT_READERS`
  （須由互動視窗依總司令【先.四十五】一裁示加入）；未列入就**在載入任何保留期資料之前**停止，不產出任何數字；
- 每一條序列進入計算前再各過一次 `assert_no_holdout_leakage()`。

配置／成本／再平衡：直接呼叫 `core_allocation_backtest.simulate()`（#418 本體，不複製、不修改）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from validation.holdout import assert_no_holdout_leakage  # noqa: E402

PREREG = "docs/PREREG_bb90_oos_2025.md"
TRIAL_ID = 423
START, END = "2025-01-01", "2026-09-30"
PRE_START = "2024-12-01"   # 只用來取 2025-01-01 第一天日報酬的前值與還原事件
OUT = HERE / "data" / "bb90_oos_2025_result.json"
PORTS = {"Bb-90": ("B", "b", 0.90), "0050_hold": ("A", "a", 1.00), "paper1_70_30": ("A", "a", 0.70)}


def guard_preflight() -> bool:
    """不讀任何保留期資料，只用一列假日期確認守門是否放行本腳本。"""
    probe = pd.DataFrame({"date": [pd.Timestamp("2025-01-02")]})
    try:
        assert_no_holdout_leakage(probe, context="bb90_oos_2025 守門自檢（假資料，一列）")
        return True
    except AssertionError as e:
        print("[停止] 保留資料守門未放行本腳本，未讀取任何保留期資料、未產出任何數字。", flush=True)
        print("        需由互動視窗依總司令【先.四十五】一裁示，把 'bb90_oos_2025.py' 加入 "
              "research/validation/holdout.py 的 ALLOWED_HOLDOUT_READERS 後再執行一次。", flush=True)
        print(f"        守門訊息：{str(e)[:300]}", flush=True)
        return False


def _uncapped_0050() -> pd.DataFrame:
    import adjust
    from finmind_client import load_full_history
    raw = load_full_history("TaiwanStockPrice", "0050", PRE_START, allow_holdout=True)
    raw = raw.sort_values("date").reset_index(drop=True)
    div = load_full_history("TaiwanStockDividend", "0050", PRE_START, allow_holdout=True)
    split_df = load_full_history("TaiwanStockSplitPrice", "0050", PRE_START, allow_holdout=True)
    cr_df = load_full_history("TaiwanStockCapitalReductionReferencePrice", "0050", PRE_START, allow_holdout=True)
    pv_df = adjust._par_value_change_market_wide(PRE_START, "0050", uncapped=True)
    empty = pd.DataFrame()
    events = adjust._combine_adjustment_events(
        div if div is not None and not div.empty else empty,
        split_df if split_df is not None and not split_df.empty else empty,
        cr_df if cr_df is not None and not cr_df.empty else empty,
        pv_df if pv_df is not None and not pv_df.empty else empty,
        dict(zip(raw["date"], raw["close"])), raw["date"].tolist())
    f = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        m = raw["date"] < ev["ex_date"]
        f.loc[m] = f.loc[m] * ev["factor"]
    out = pd.DataFrame({"date": pd.to_datetime(raw["date"]).dt.normalize(),
                        "adj_close": raw["close"].astype(float) * f})
    out.attrs["n_events"] = int(len(events))
    out.attrs["events"] = [{"ex_date": str(e["ex_date"])[:10], "factor": float(e["factor"])}
                           for _, e in events.iterrows()]
    return out


def load_oos() -> tuple[pd.DataFrame, dict]:
    import core_allocation_backtest as CA
    from fred_yield_curve_gate import fetch_fred_series
    fxd = fetch_fred_series("DEXTAUS", "2024-01-01")
    fx = pd.Series(fxd["value"].astype(float).to_numpy(),
                   index=pd.to_datetime(fxd["date"]).dt.normalize()).sort_index()
    px = _uncapped_0050()
    a = px["adj_close"].to_numpy(float)
    r = np.zeros(len(a))
    r[1:] = a[1:] / a[:-1] - 1.0
    tw = pd.DataFrame({"date": px["date"], "r_0050": r})
    rf = json.loads((ROOT / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rfm = {str(x["date"])[:7]: float(x["rf_rate_pct"]) for x in rf}
    months = tw["date"].dt.strftime("%Y-%m")
    missing_rf = sorted({m for m in months if m not in rfm})
    tw["r_cash"] = [rfm.get(m, 0.0) / 100.0 / 252.0 for m in months]
    vti = CA.yf_total_return_twd("VTI", fx).rename(columns={"r_twd": "r_vti"})
    ief = CA.yf_total_return_twd("IEF", fx).rename(columns={"r_twd": "r_ief"})
    df = tw.merge(vti, on="date", how="left").merge(ief, on="date", how="left")
    miss = {"vti_missing_days": int(df["r_vti"].isna().sum()), "ief_missing_days": int(df["r_ief"].isna().sum())}
    df[["r_vti", "r_ief"]] = df[["r_vti", "r_ief"]].fillna(0.0)
    df = df[(df["date"] >= START) & (df["date"] <= END)].reset_index(drop=True)
    for nm, frame in (("0050", px), ("VTI", vti), ("IEF", ief), ("merged", df)):
        assert_no_holdout_leakage(frame, context=f"bb90_oos_2025 {nm}")
    meta = {"n_adjust_events_0050": px.attrs.get("n_events"), "adjust_events_0050": px.attrs.get("events"),
            "rf_months_missing_used_0": missing_rf, **miss,
            "vti_ief_source": "core_allocation_backtest.yf_total_return_twd（cache 或 yfinance，扣 30% 預扣稅、DEXTAUS 換台幣）"}
    return df, meta


def metrics(r: np.ndarray, dates: pd.Series) -> dict:
    eq = np.cumprod(1 + r)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    days = (dates.iloc[-1] - dates.iloc[0]).days + 1
    cum = float(eq[-1] - 1.0)
    mret = pd.Series(r, index=pd.DatetimeIndex(dates)).groupby(pd.DatetimeIndex(dates).to_period("M")).apply(
        lambda x: float(np.prod(1 + x) - 1))
    worst = mret.idxmin()
    return {"cum_return": cum, "cagr": float((1 + cum) ** (365.25 / days) - 1.0), "mdd": float(dd.min()),
            "worst_month": {"month": str(worst), "return": float(mret.min())},
            "monthly": {str(k): float(v) for k, v in mret.items()}}


def main() -> int:
    if OUT.exists():
        print(f"[拒絕] {OUT.name} 已存在：本試驗只跑一次，不得重跑。", flush=True)
        return 2
    if not guard_preflight():
        return 3
    import core_allocation_backtest as CA
    print("=== 載入保留期資料（只此一次）===", flush=True)
    df, meta = load_oos()
    dates = df["date"]
    rets = {k: CA.simulate(df, *v) for k, v in PORTS.items()}
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG,
           "prereg_sha256": hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
           "trial_id": TRIAL_ID, "n_trials_counted": 1,
           "period": {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": int(len(df))},
           "portfolios": {"Bb-90": "45% 0050 + 45% VTI + 10% IEF", "0050_hold": "100% 0050",
                          "paper1_70_30": "70% 0050 + 30% 台幣定存"},
           "costs": {"us_dividend_withholding": CA.WHT, "fx_one_way": CA.FX_COST, "tw_sell_tax": CA.TW_SELL_TAX,
                     "rebalance": "每月最後交易日（core_allocation_backtest.simulate）"},
           "data_meta": meta,
           "power_note": "21 個月統計檢定力很低，好壞都不構成證明；描述性樣本外檢驗，非部署判定。",
           "results": {k: metrics(v, dates) for k, v in rets.items()}}
    b, z, p = res["results"]["Bb-90"], res["results"]["0050_hold"], res["results"]["paper1_70_30"]
    res["bb90_minus_0050"] = {"cum_return_pp": (b["cum_return"] - z["cum_return"]) * 100,
                              "cagr_pp": (b["cagr"] - z["cagr"]) * 100,
                              "monthly_pp": {m: (b["monthly"][m] - z["monthly"][m]) * 100 for m in b["monthly"]}}
    res["bb90_minus_paper1"] = {"cum_return_pp": (b["cum_return"] - p["cum_return"]) * 100,
                                "cagr_pp": (b["cagr"] - p["cagr"]) * 100}
    res["survival_rule_1"] = {"bb90_mdd": b["mdd"], "violates_minus_50pct": b["mdd"] < -0.50}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結果已寫入 {OUT}", flush=True)
    for k, v in res["results"].items():
        print(f"{k}: 累積 {v['cum_return']*100:+.2f}%  年化 {v['cagr']*100:+.2f}%  MDD {v['mdd']*100:.2f}%  "
              f"最差月 {v['worst_month']['month']} {v['worst_month']['return']*100:+.2f}%", flush=True)
    print(f"Bb-90 − 0050：累積 {res['bb90_minus_0050']['cum_return_pp']:+.2f}pp、年化 {res['bb90_minus_0050']['cagr_pp']:+.2f}pp", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
