"""先.一一三-B1 V4：券資比（反向）台股 2007～2014 單發。

事前登記：`docs/PREREG_DRAFT_VAR1018_V4_short_margin_ratio_tw2007_reversed.md`（2026-10-18 總司令【先.一一三】B 放行）。
**只跑一次**：結果檔 `research/data/var1018_v4_result.json` 已存在就拒絕重跑。只讀本機快取、零外部請求、不讀 2025 以後。

規則（照 PREREG；實作細節在登記前寫死於此）：
- 宇宙：本機有融資融券檔（`TaiwanStockMarginPurchaseShortSale__*__2006-01-01__*`）且有日線的 4 碼普通股；每個快照日只收
  「當天有因子值、且有 20 交易日後收盤」的股票，**少於 20 檔的快照整期跳過**。
- 快照：交易日曆（本機日線，當天有價股票數 ≥ 期間最多的一半）上，從 2007-01-01 起每 20 個交易日一期、不重疊，
  最後一期的結束日 ≤ 2014-12-31（沿用 `factor_ic.build_snapshots`，horizon＝20）。
- 因子：−(ShortSaleTodayBalance ÷ MarginPurchaseTodayBalance)，取快照日當天或之前 5 個日曆日內最近一筆；融資餘額 ≤0 剔除。
- 目標：快照日收盤到期末收盤的股利還原報酬（`var1018_twdata`）。
- 主檢定：各期 Spearman IC 的平均 > 0；控制組＝每期內打散因子值 N＝500（種子 20261018），真實平均 IC 贏過的比例（百分位）≥ 90；
  對半切（≤2010-12-31／之後）兩半平均 IC 都 > 0。三項都過 → PASS（只過第 1 關 cheap IC gate）。
- 天條一：每期買因子前 20%（券資比最低的五分之一）等權，期末換股；成本 costs.round_trip_cost_pct()×換手比例，1×／2×／3×；
  全期與 2007-10-30～2008-11-21、2011-05-02～2011-12-19 兩段空頭的最大回撤，任一段 >50% → VIOLATES_SURVIVAL。
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import var1018_twdata as T
from factor_ic import build_snapshots
from validation import costs

D = Path(__file__).parent / "data"
OUT = D / "var1018_v4_result.json"
START, END, HORIZON = "2007-01-01", "2014-12-31", 20
N_NULL, SEED, MIN_N, LOOKBACK_DAYS = 500, 20261018, 20, 5
HALF_CUT = pd.Timestamp("2010-12-31")
SEGMENTS = [("全期", START, END), ("2008 金融海嘯", "2007-10-30", "2008-11-21"), ("2011 歐債", "2011-05-02", "2011-12-19")]


def margin_series(code: str) -> pd.Series:
    parts = []
    for f in glob.glob(str(T.RAW / f"TaiwanStockMarginPurchaseShortSale__{code}__2006-01-01__*.parquet")):
        d = pd.read_parquet(f)
        if not d.empty and {"date", "ShortSaleTodayBalance", "MarginPurchaseTodayBalance"} <= set(d.columns):
            parts.append(d)
    if not parts:
        return pd.Series(dtype=float)
    d = pd.concat(parts).drop_duplicates("date")
    d["date"] = pd.to_datetime(d["date"])
    d = d[(d["date"] <= T.VAL_END) & (d["MarginPurchaseTodayBalance"] > 0)].sort_values("date")
    return pd.Series(-(d["ShortSaleTodayBalance"] / d["MarginPurchaseTodayBalance"]).to_numpy(), index=d["date"])


def mdd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min() * 100) if len(eq) else float("nan")


def main() -> int:
    if OUT.exists():
        print(f"結果檔 {OUT.name} 已存在：只跑一次，拒絕重跑")
        return 1
    codes = sorted({re.match(r"TaiwanStockMarginPurchaseShortSale__([^_]+)__", Path(f).name).group(1)
                    for f in glob.glob(str(T.RAW / "TaiwanStockMarginPurchaseShortSale__*__2006-01-01__*.parquet"))})
    codes = [c for c in codes if re.match(r"^[1-9]\d{3}$", c)]
    fac = {c: margin_series(c) for c in codes}
    fac = {c: s for c, s in fac.items() if len(s)}
    px = {c: T.daily(c) for c in fac}
    px = {c: d for c, d in px.items() if len(d)}
    cal = T.market_calendar(list(px), START, END)
    snaps = build_snapshots([t.strftime("%Y-%m-%d") for t in cal], START, END, HORIZON)
    rows, skipped = [], 0
    for a, b in snaps:
        ta, tb = pd.Timestamp(a), pd.Timestamp(b)
        xs, ys, cs = [], [], []
        for c, s in fac.items():
            if c not in px:
                continue
            w = s[(s.index <= ta) & (s.index >= ta - pd.Timedelta(days=LOOKBACK_DAYS))]
            if w.empty:
                continue
            r = T.cum_return(px[c], ta, tb)
            if r is None:
                continue
            xs.append(float(w.iloc[-1])); ys.append(r); cs.append(c)
        if len(xs) < MIN_N:
            skipped += 1
            continue
        rows.append({"start": a, "end": b, "n": len(xs), "x": xs, "y": ys, "codes": cs})
    ics = np.array([spearmanr(r["x"], r["y"]).statistic for r in rows])
    real = float(np.nanmean(ics))
    rng = np.random.default_rng(SEED)
    null = np.empty(N_NULL)
    for k in range(N_NULL):
        null[k] = np.nanmean([spearmanr(rng.permutation(r["x"]), r["y"]).statistic for r in rows])
    pct = 100.0 * float(np.mean(null <= real))
    ends = pd.to_datetime([r["start"] for r in rows])
    half = [float(np.nanmean(ics[ends <= HALF_CUT])), float(np.nanmean(ics[ends > HALF_CUT]))]
    # 天條一：前 20%（因子最高＝券資比最低）等權
    rt = costs.round_trip_cost_pct()
    eqs, prev = {1: [1.0], 2: [1.0], 3: [1.0]}, set()
    dates = [pd.Timestamp(rows[0]["start"])] if rows else []
    turnovers = []
    for r in rows:
        order = np.argsort(r["x"])[::-1]
        k = max(1, len(order) // 5)
        top = [order[i] for i in range(k)]
        names = {r["codes"][i] for i in top}
        g = float(np.mean([r["y"][i] for i in top]))
        to = 1.0 if not prev else len(names - prev) / len(names)
        turnovers.append(to)
        for m in (1, 2, 3):
            eqs[m].append(eqs[m][-1] * (1 + g - rt * m * to))
        prev = names
        dates.append(pd.Timestamp(r["end"]))
    segs = []
    eq1 = pd.Series(eqs[1], index=dates)
    for lab, a, b in SEGMENTS:
        m = (eq1.index >= a) & (eq1.index <= b)
        segs.append({"segment": lab, "start": a, "end": b, "top20_mdd_pct_1x": round(mdd(eq1[m]), 2)})
    survival = all(s["top20_mdd_pct_1x"] > -50 for s in segs if not np.isnan(s["top20_mdd_pct_1x"]))
    passed = real > 0 and pct >= 90.0 and all(h > 0 for h in half)
    verdict = "VIOLATES_SURVIVAL" if not survival else ("PASS" if passed else "FAIL")
    out = {"prereg": "docs/PREREG_DRAFT_VAR1018_V4_short_margin_ratio_tw2007_reversed.md", "verdict": verdict,
           "mean_ic": real, "null_percentile": pct, "null_median": float(np.median(null)), "null_p90": float(np.percentile(null, 90)),
           "half_mean_ic": {"2007-2010": half[0], "2011-2014": half[1]}, "n_periods": len(rows), "n_periods_skipped_lt20": skipped,
           "n_stocks_per_period": {"min": int(min(r["n"] for r in rows)), "median": float(np.median([r["n"] for r in rows])), "max": int(max(r["n"] for r in rows))},
           "n_codes_with_factor": len(fac), "round_trip_cost_1x": rt, "mean_turnover": float(np.mean(turnovers)),
           "top20_final_equity": {f"{m}x": round(eqs[m][-1], 4) for m in (1, 2, 3)}, "survival_segments": segs,
           "ic_by_period": [{"start": r["start"], "n": r["n"], "ic": float(i)} for r, i in zip(rows, ics)],
           "simplifications": "價格只做股利還原（分割／減資／面額變更未納入）；宇宙為本機快取（今天名單抽樣，有存活者偏誤，方向偏向低估效應）"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"V4：{len(rows)} 期（跳過 {skipped} 期 <{MIN_N} 檔），每期檔數 {out['n_stocks_per_period']}；平均 IC {real:+.4f}、"
          f"null 百分位 {pct:.1f}、兩半 {[round(h, 4) for h in half]}；前 20% 終值 {out['top20_final_equity']}；判定 {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
