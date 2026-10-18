"""先.一一五-1 V7：美國失業率年增（反向）→ S&P 500 未來 20 日報酬，1990～2024 單發。

事前登記：`docs/PREREG_DRAFT_VAR1018_V7_us_unemployment_spx.md`（先.一一三-B3 改 ALFRED、先.一一四-4／先.一一五-1 放行）。
**只跑一次**：結果檔 `research/data/var1018_v7_result.json` 已存在就拒絕重跑。只讀本機（ALFRED 首次公布值已抓存 1 次）、不讀 2025 以後。

規則（照 PREREG；實作細節登記前寫死於此）：
- 資料：`research/data/raw/ALFRED_UNRATE_initial_release.json`（output_type=4，每個月份只有首次公布值與首次公布日 realtime_start）；
  S&P：`research/data/raw_yf/INDEX_GSPC__1990-01-01__2024-12-31.parquet`。
- 訊號：月份 m 的年增＝首次公布值(m) − 首次公布值(m−12)（百分點）；在「月份 m 的首次公布日」**下一個交易日**起才可用；每天用最近一個可用的值。
- 目標：t 日收盤到 t+20 個交易日收盤的 S&P 報酬（未來報酬，最後 20 天沒有完整目標的不計）。樣本 1991-01-02～2024-12-30。
- 主檢定：Pearson 與 Spearman 都 > 0；虛無分布沿用原試驗 #80 的 `regime_gate_common.circular_shift_null`（N＝500、種子 20261018，
  保留訊號自身序列相關，百分位以 |r| 計）≥ 90；對半切（≤2007-12-31／之後）兩半 Pearson 與 Spearman 都 > 0。都過 → PASS。
- 天條一：曝險＝訊號在過去 2,520 個交易日（約 10 年，不足時用至今全部）的百分位（0～100% 連續，不做門檻二元），
  報告此投組與 S&P 買進持有在全期、2000-03-24～2002-10-09、2007-10-09～2009-03-09 的最大回撤；曝險投組任一段 >50% → VIOLATES_SURVIVAL。
  成本：曝險變動量 × us_costs.round_trip_cost_pct()／2（單邊），另報 2×／3×。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd
from scipy import stats

from regime_gate_common import circular_shift_null
from validation import us_costs, holdout

D = Path(__file__).parent / "data"
OUT = D / "var1018_v7_result.json"
H, N_NULL, SEED, WIN = 20, 500, 20261018, 2520
START, CUT = pd.Timestamp("1991-01-02"), pd.Timestamp("2007-12-31")
SEGS = [("全期", "1991-01-02", "2024-12-30"), ("2000～2002 空頭", "2000-03-24", "2002-10-09"), ("2008 空頭", "2007-10-09", "2009-03-09")]


def mdd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min() * 100) if len(eq) else float("nan")


def main() -> int:
    if OUT.exists():
        print(f"結果檔 {OUT.name} 已存在：只跑一次，拒絕重跑")
        return 1
    obs = json.loads((D / "raw" / "ALFRED_UNRATE_initial_release.json").read_text(encoding="utf-8"))["observations"]
    u = pd.DataFrame(obs)
    u = u[u["value"] != "."].copy()
    u["month"] = pd.to_datetime(u["date"])
    u["released"] = pd.to_datetime(u["realtime_start"])
    u["value"] = u["value"].astype(float)
    u = u.sort_values("month").drop_duplicates("month").set_index("month")
    u["yoy"] = u["value"] - u["value"].shift(12)
    u = u.dropna(subset=["yoy"])
    px = pd.read_parquet(D / "raw_yf" / "INDEX_GSPC__1990-01-01__2024-12-31.parquet")[["date", "close"]]
    px["date"] = pd.to_datetime(px["date"])
    px = px[px["date"] <= pd.Timestamp(holdout.VAL_END)].sort_values("date").reset_index(drop=True)
    dates = px["date"]
    # 每個月份的訊號：首次公布日「下一個交易日」起可用
    avail = []
    for m, r in u.iterrows():
        nxt = dates[dates > r["released"]]
        if len(nxt):
            avail.append((nxt.iloc[0], float(r["yoy"]), m))
    a = pd.DataFrame(avail, columns=["from", "yoy", "month"]).sort_values("from").drop_duplicates("from", keep="last")
    sig = pd.merge_asof(px[["date"]], a.rename(columns={"from": "date"}), on="date", direction="backward")
    px["signal"], px["sig_month"] = sig["yoy"], sig["month"]
    px["fwd"] = px["close"].shift(-H) / px["close"] - 1
    df = px[(px["date"] >= START)].dropna(subset=["signal", "fwd"]).reset_index(drop=True)
    s, t = df["signal"].to_numpy(), df["fwd"].to_numpy()
    pear, spear = stats.pearsonr(s, t)[0], stats.spearmanr(s, t)[0]
    null = circular_shift_null(s, t, N_NULL, SEED)
    halves = {}
    for lab, m in (("1991-2007", df["date"] <= CUT), ("2008-2024", df["date"] > CUT)):
        halves[lab] = {"pearson": float(stats.pearsonr(s[m], t[m])[0]), "spearman": float(stats.spearmanr(s[m], t[m])[0]), "n": int(m.sum())}
    # 天條一：連續曝險
    full = px[px["date"] >= START].dropna(subset=["signal"]).reset_index(drop=True)
    sv = full["signal"]
    expo = sv.rolling(WIN, min_periods=250).apply(lambda w: (w[:-1] < w[-1]).mean() + 0.5 * (w[:-1] == w[-1]).mean(), raw=True).fillna(0.5)
    ret = full["close"].pct_change().fillna(0.0)
    rt = us_costs.round_trip_cost_pct(price=float(full["close"].median()), shares=100.0)
    dexp = expo.diff().abs().fillna(expo.iloc[0])
    eqs = {}
    for k in (1, 2, 3):
        r = expo.shift(1).fillna(0.5) * ret - dexp * rt / 2 * k
        eqs[k] = pd.Series(np.cumprod(1 + r.to_numpy()), index=full["date"])
    bh = pd.Series(np.cumprod(1 + ret.to_numpy()), index=full["date"])
    segs = []
    for lab, x, y in SEGS:
        m = (bh.index >= x) & (bh.index <= y)
        segs.append({"segment": lab, "exposure_portfolio_mdd_pct_1x": round(mdd(eqs[1][m]), 2), "buy_hold_mdd_pct": round(mdd(bh[m]), 2)})
    yrs = (full["date"].iloc[-1] - full["date"].iloc[0]).days / 365.25
    cagr = {f"{k}x": round(float(eqs[k].iloc[-1] ** (1 / yrs) - 1) * 100, 3) for k in (1, 2, 3)}
    survival = all(sg["exposure_portfolio_mdd_pct_1x"] > -50 for sg in segs)
    passed = pear > 0 and spear > 0 and null["percentile"] >= 90.0 and all(h["pearson"] > 0 and h["spearman"] > 0 for h in halves.values())
    verdict = "VIOLATES_SURVIVAL" if not survival else ("PASS" if passed else "FAIL")
    out = {"prereg": "docs/PREREG_DRAFT_VAR1018_V7_us_unemployment_spx.md", "verdict": verdict, "n": int(len(df)),
           "start": str(df["date"].iloc[0].date()), "end": str(df["date"].iloc[-1].date()),
           "pearson": float(pear), "spearman": float(spear), "circular_shift_null": null, "halves": halves,
           "exposure_portfolio_cagr_pct": cagr, "buy_hold_cagr_pct": round(float(bh.iloc[-1] ** (1 / yrs) - 1) * 100, 3),
           "survival_segments": segs, "round_trip_cost_1x": rt,
           "data": "ALFRED UNRATE 首次公布值（output_type=4）；首次公布日下一個交易日起可用"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"V7：n={len(df)}（{out['start']}～{out['end']}），Pearson {pear:+.4f}、Spearman {spear:+.4f}、circular-shift 百分位 {null['percentile']:.1f}；"
          f"兩半 {halves}；曝險投組 CAGR {cagr}（買進持有 {out['buy_hold_cagr_pct']}%）；天條一 {segs}；判定 {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
