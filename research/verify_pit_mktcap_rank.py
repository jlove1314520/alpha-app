# -*- coding: utf-8 -*-
"""先.八十三-2a-1 驗證腳本：用 pit_mktcap_rank 的時點正確市值排名，重建「前 50 大市值加權」
組合，對 2024 年以前的 0050 檢查：

  0. 淨值曲線有在動（#283 的 bug 是整條平線：日報酬標準差≈0、相關≈0、beta≈0）
  1. 台積電權重（每次再平衡日）——交辦期待 30～50%
  2. 與 0050 含息日報酬相關 ≥ 0.98
  3. 年化追蹤誤差 TE ≤ 1%

只讀本機快取（0 次網路請求），只用 ≤ VAL_END（2024-12-31）的資料；不登記試驗、不計 N
（這是宇宙工具的量尺檢查，不是策略）。輸出 research/data/pit_mktcap_rank_verify.json。

已知限制（照實揭露，不為了過關而調）：
- 0050 依「流通」市值加權、且有單檔權重上限規則；這裡用總股數 → TE 有結構性下限。
- 0050 每季調整成分、這裡每月底再平衡（月底排名、隔一個交易日起持有）。
- 季間增減資要到下一個法定公告日才反映。
- 部分成分股沒有任何除權息事件快取 → 除息日會被當成下跌（列在 holdings_without_event_cache）。

用法：python research/verify_pit_mktcap_rank.py [--start 2013-06-01]
"""
from __future__ import annotations

import argparse
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

OUT = HERE / "data" / "pit_mktcap_rank_verify.json"
TOP_N = 50
TSMC = "2330"


def month_end_trading_days(idx: pd.Index, start: str) -> list[str]:
    s = pd.Series(idx, index=pd.to_datetime(idx))
    s = s[(s.index >= start) & (s.index <= VAL_END)]
    return s.groupby([s.index.year, s.index.month]).last().tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2013-06-01",
                    help="資產負債表 OrdinaryShare 快取最早 2012Q4（法定公告日 2013-04-30），故預設 2013-06 起")
    a = ap.parse_args()

    etf = pmr.total_return_index("0050")
    if etf.empty:
        print("0050 價格快取不存在，無法驗證", flush=True)
        return 1
    days = [d for d in etf.index if a.start <= d <= VAL_END]
    rebal = month_end_trading_days(pd.Index(days), a.start)
    print(f"再平衡日 {len(rebal)} 個（{rebal[0]}～{rebal[-1]}），計算市值面板…", flush=True)
    panel = pmr.mktcap_panel(rebal)
    top = panel[panel["rank"] <= TOP_N].copy()
    top["w"] = top["mktcap"] / top.groupby("date")["mktcap"].transform("sum")

    # 持有期日報酬：每月底定權重，下一個交易日起到下一個月底，權重隨價格漂移（買進持有）
    tri_cache: dict[str, pd.Series] = {}
    no_event = set()
    port = pd.Series(np.nan, index=pd.Index(days))
    missing_px_days = 0
    for i, d0 in enumerate(rebal):
        d1 = rebal[i + 1] if i + 1 < len(rebal) else days[-1]
        hold_days = [d for d in days if d0 < d <= d1]
        if not hold_days:
            continue
        hold = top[top["date"] == d0]
        val = pd.Series(0.0, index=[d0] + hold_days)
        for r in hold.itertuples():
            if r.stock_id not in tri_cache:
                tri_cache[r.stock_id] = pmr.total_return_index(r.stock_id)
                if tri_cache[r.stock_id].attrs.get("no_event_cache"):
                    no_event.add(r.stock_id)
            tri = tri_cache[r.stock_id]
            p = tri.reindex([d0] + hold_days).ffill(limit=5)
            if pd.isna(p.iloc[0]):
                missing_px_days += 1
                p = p.fillna(1.0) * 0 + 1.0                     # 起點沒價格：該檔當現金（照實計數）
            p = p.ffill()                                         # 下市後最後價凍結
            val = val + r.w * (p / p.iloc[0])
        port.loc[hold_days] = (val / val.shift(1)).iloc[1:].to_numpy() - 1

    etf_ret = etf.reindex(days).pct_change()
    df = pd.DataFrame({"port": port, "etf": etf_ret}).dropna()
    diff = df["port"] - df["etf"]
    te = float(diff.std() * np.sqrt(252))
    corr = float(df["port"].corr(df["etf"]))
    beta = float(np.cov(df["port"], df["etf"])[0, 1] / df["etf"].var())
    nonzero = float((df["port"].abs() > 1e-12).mean())
    port_vol = float(df["port"].std() * np.sqrt(252))
    etf_vol = float(df["etf"].std() * np.sqrt(252))

    # 診斷（不是判準）：月報酬頻率的 TE／相關——0050 市價對淨值的日間溢折價會灌進日頻 TE，月頻可看出量級
    mdf = (1 + df).groupby(pd.to_datetime(df.index).to_period("M")).prod() - 1
    te_m = float((mdf["port"] - mdf["etf"]).std() * np.sqrt(12))
    corr_m = float(mdf["port"].corr(mdf["etf"]))

    by_year = {}
    for y, g in df.groupby(pd.to_datetime(df.index).year):
        dd = g["port"] - g["etf"]
        by_year[int(y)] = {"te": round(float(dd.std() * np.sqrt(252)), 4),
                           "corr": round(float(g["port"].corr(g["etf"])), 4),
                           "port_ret": round(float((1 + g["port"]).prod() - 1), 4),
                           "etf_ret": round(float((1 + g["etf"]).prod() - 1), 4)}

    tw = top[top["stock_id"] == TSMC].set_index("date")["w"]
    tsmc = {"min": round(float(tw.min()), 4), "max": round(float(tw.max()), 4),
            "by_year_end": {str(k)[:4]: round(float(v), 4) for k, v in tw.groupby(tw.index.str[:4]).last().items()},
            "months_in_top50": int(len(tw)), "months_total": len(rebal)}
    cnt = top.groupby("date").size()

    checks = {
        "c0_curve_moves": bool(port_vol > 0.05 and nonzero > 0.95 and beta > 0.5),
        "c1_tsmc_weight_30_50": bool(tsmc["min"] >= 0.30 and tsmc["max"] <= 0.50),
        "c2_corr_ge_0_98": bool(corr >= 0.98),
        "c3_te_le_1pct": bool(te <= 0.01),
    }
    res = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task": "先.八十三-2a-1",
        "period": [df.index[0], df.index[-1]], "n_days": len(df), "n_rebalance": len(rebal),
        "rebalance": "每月最後交易日依市值排名、前 50 大市值加權、隔日起買進持有",
        "benchmark": "0050 含息（本機快取事件因子還原）",
        "curve": {"port_vol": round(port_vol, 4), "etf_vol": round(etf_vol, 4),
                  "nonzero_day_ratio": round(nonzero, 4), "beta": round(beta, 4),
                  "port_cum": round(float((1 + df['port']).prod() - 1), 4),
                  "etf_cum": round(float((1 + df['etf']).prod() - 1), 4)},
        "corr": round(corr, 4), "te_annual": round(te, 4), "by_year": by_year,
        "diagnostic_monthly": {"te_annual": round(te_m, 4), "corr": round(corr_m, 4),
                               "note": "僅診斷，判準仍用日頻"},
        "tsmc_weight": tsmc,
        "top50_count_min": int(cnt.min()), "top50_count_max": int(cnt.max()),
        "holdings_without_event_cache": sorted(no_event),
        "holding_starts_without_price": missing_px_days,
        "checks": checks,
        "note": "未過的項目照實記錄，不放寬門檻；0050 依流通市值加權＋權重上限，總市值重建 TE 有結構性下限",
        "requests_made": 0,
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("period", "curve", "corr", "te_annual", "diagnostic_monthly", "checks",
                                           "holdings_without_event_cache")}, ensure_ascii=False, indent=1))
    print(json.dumps(by_year, ensure_ascii=False))
    print(f"寫入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
