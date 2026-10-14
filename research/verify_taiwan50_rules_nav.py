# -*- coding: utf-8 -*-
"""先.九十五-1：core_tilt 第 0 階段改用 0050 官方每日結算淨值（NAV）當基準，只跑一次。

修正清單（重跑前已 commit，research/PIT_MKTCAP_RULES_FIX.md 先.九十五-1 節）：
  F2 基準＝0050 NAV 含息：一般日 NAV_t/NAV_{t-1}−1；除息日 (NAV_t+D)/NAV_{t-1}−1，
     D＝證交所 TWT49U「除權息前收盤價−除權息參考價」（research/data/twse_exright_2013_2024.csv）。
  F3 NAV 日期＝API UPDATE_T 日期（research/fetch_0050_nav.py 已處理）；與重建組合取共同交易日。
重建組合沿用 verify_taiwan50_rules.build_portfolio()（R1～R6＋F1），門檻不變：
  日頻 TE 年化 ≤1% 合格／1～3% 送審／>3% 結案（事前寫死）。月頻、相關、逐年、折溢價只作參考。
只讀本機檔、0 次網路請求、不讀 holdout。不登記試驗、不計 N。
輸出：research/data/taiwan50_rules_verify_nav.json（原 taiwan50_rules_verify.json 不覆蓋）。
"""
from __future__ import annotations

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
import pit_mktcap_rank as pmr  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402
from verify_taiwan50_rules import START, build_portfolio  # noqa: E402

NAV_CSV = HERE / "data" / "etf0050_nav_daily.csv"
EXR_CSV = HERE / "data" / "twse_exright_2013_2024.csv"
OUT = HERE / "data" / "taiwan50_rules_verify_nav.json"


def nav_total_return(days: list[str]) -> tuple[pd.Series, list[dict]]:
    nav = pd.read_csv(NAV_CSV, dtype={"date": str}).set_index("date")["nav"]
    ex = pd.read_csv(EXR_CSV, dtype={"date": str, "stock_id": str})
    ex = ex[ex["stock_id"] == "0050"]
    div = {r.date: float(r.prev_close - r.ref_price) for r in ex.itertuples()}
    nv = nav.reindex(days)
    r = nv / nv.shift(1) - 1
    used = []
    for d, D in div.items():
        if d in r.index and not np.isnan(nv.get(d, np.nan)):
            i = r.index.get_loc(d)
            if i > 0:
                r.iloc[i] = (nv.iloc[i] + D) / nv.iloc[i - 1] - 1
                used.append({"date": d, "dividend": round(D, 4)})
    return r, used


def main() -> int:
    etf = pmr.total_return_index("0050")
    days = [d for d in etf.index if START <= d <= VAL_END]
    port, sched, tsmc_w, no_px = build_portfolio(days)
    nav_r, divs = nav_total_return(days)
    etf_r = etf.reindex(days).pct_change()
    df = pd.DataFrame({"port": port, "nav": nav_r, "etf": etf_r}).dropna()
    ann = np.sqrt(252)
    te = lambda a, b, x=df: float((x[a] - x[b]).std() * ann)
    te_d = te("port", "nav")
    mdf = (1 + df).groupby(pd.to_datetime(df.index).to_period("M")).prod() - 1
    by_year = {}
    for y, g in df.groupby(pd.to_datetime(df.index).year):
        c = lambda col: float((1 + g[col]).prod() - 1)
        by_year[int(y)] = {"te_vs_nav": round(te("port", "nav", g), 4), "corr": round(float(g["port"].corr(g["nav"])), 4),
                           "port_ret": round(c("port"), 4), "nav_tr_ret": round(c("nav"), 4), "etf_px_tr_ret": round(c("etf"), 4)}
    big = (df["nav"] - df["etf"]).abs()
    verdict = "PASS_合格" if te_d <= 0.01 else ("REVIEW_送審" if te_d <= 0.03 else "FAIL_量尺無法重建0050")
    nav_lv = pd.read_csv(NAV_CSV, dtype={"date": str}).set_index("date")
    prem = (nav_lv["close"] / nav_lv["nav"] - 1).reindex(df.index).dropna()
    res = {"generated_at": datetime.now().isoformat(timespec="seconds"), "task": "先.九十五-1（基準改 0050 官方 NAV 含息，只跑一次）",
           "fix_list": "research/PIT_MKTCAP_RULES_FIX.md 先.九十五-1 F2／F3（重跑前 commit c9eb1d82b）",
           "period": [df.index[0], df.index[-1]], "n_days": len(df),
           "primary": {"metric": "日頻 TE（年化）：重建組合 − 0050 NAV 含息", "te_daily": round(te_d, 4), "verdict": verdict,
                       "thresholds": "≤1% 合格／1～3% 送審／>3% 結案（事前寫死，與先.九十三-1b 相同）"},
           "reference_only": {"te_monthly_vs_nav": round(float((mdf["port"] - mdf["nav"]).std() * np.sqrt(12)), 4),
                              "corr_daily_vs_nav": round(float(df["port"].corr(df["nav"])), 4),
                              "te_daily_vs_0050_price_same_days": round(te("port", "etf"), 4),
                              "te_daily_0050_price_vs_nav": round(te("etf", "nav"), 4),
                              "autocorr_lag1_port_minus_nav": round(float((df["port"] - df["nav"]).autocorr(1)), 3),
                              "premium_close_vs_nav": {"mean": round(float(prem.mean()), 5), "std": round(float(prem.std()), 5),
                                                       "abs_p95": round(float(prem.abs().quantile(0.95)), 5)},
                              "cum": {k: round(float((1 + df[k]).prod() - 1), 4) for k in ("port", "nav", "etf")}},
           "by_year": by_year,
           "nav_dividends_applied": divs,
           "data_check_days_nav_vs_price_gt_3pct": [{"date": d, "nav_r": round(float(df.at[d, "nav"]), 4), "etf_r": round(float(df.at[d, "etf"]), 4)}
                                                     for d in big[big > 0.03].index],
           "n_changes": len(sched), "weight_starts_without_price": no_px,
           "tsmc_weight_at_reviews": {d: round(v, 4) for d, v in tsmc_w},
           "not_implemented": ["N1 自由流通市值加權（無免費官方流通係數歷史）", "N2 最低流通量", "N3 流動性篩選", "N4 全額交割股排除",
                               "經理費未扣（NAV 已扣，約 0.3～0.4%／年，只影響累積差）"],
           "requests_made": 0}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("period", "n_days", "primary", "reference_only")}, ensure_ascii=False, indent=1))
    print("除息套用", len(divs), "次；資料檢查 >3% 日數", len(res["data_check_days_nav_vs_price_gt_3pct"]))
    print(json.dumps(by_year, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
