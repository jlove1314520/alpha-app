"""先.一一三-B1 V5：1 月反轉（今年 1～10 月輸家隔年 1 月）台股單發。

事前登記：`docs/PREREG_DRAFT_VAR1018_V5_january_reversal_tw.md`（2026-10-18 總司令【先.一一三】B 放行）。
**只跑一次**：結果檔 `research/data/var1018_v5_result.json` 已存在就拒絕重跑。只讀本機快取、零外部請求、不讀 2025 以後。

規則（照 PREREG；實作細節在登記前寫死於此）：
- 主判定：排序年 Y＝2010～2023、反轉月＝Y+1 年 1 月（14 個 1 月），母體＝本機有日線的 4 碼普通股（全市場快取）。
- 排序日＝Y 年 10 月最後一個交易日；排序變數＝Y 年第一個交易日收盤到排序日收盤的股利還原報酬（1～10 月）；
  只收排序日前 20 個交易日平均成交值 ≥ 3,000 萬元、且兩個日子都有價格的股票；最差 20% 為輸家組。
- 買進日＝Y 年 12 月最後一個交易日收盤；買進日鎖漲停（costs.limit_status）的買不到、剔除不補。
  賣出日＝Y+1 年 1 月最後一個交易日收盤；鎖跌停就順延到下一個沒鎖跌停的交易日（最多 10 天，仍鎖用第 10 天並計數）。
- 輸家淨報酬＝還原報酬 − costs.round_trip_cost_pct()（1×；另報 2×／3×）；對照＝同一母體（流動性門檻後、可買進者）
  同期等權**毛**報酬（對照不扣成本＝保守）。超額＝輸家淨 − 對照毛。
- 主檢定：14 年超額平均 > 0；控制組＝每年在母體內隨機抽同數量當「輸家」N＝500（種子 20261018），真實平均超額贏過的比例 ≥ 90；
  對半切（2011～2017／2018～2024 的 1 月）兩半平均都 > 0。都過 → PASS。
- 天條一：只在 1 月持有輸家組、其他月份持現金的淨值，最大回撤 >50% → VIOLATES_SURVIVAL；另列 14 個 1 月逐年報酬與最差單月。
- 另報（不入判定）：2008-01、2009-01 兩個 1 月，母體限本機 2007～2009 有日線的固定樣本。
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

import var1018_twdata as T
from validation import costs

D = Path(__file__).parent / "data"
OUT = D / "var1018_v5_result.json"
MAIN_YEARS = list(range(2010, 2024))      # 排序年 → 反轉月 Y+1 年 1 月（2011-01～2024-01）
SUPP_YEARS = [2007, 2008]                 # 另報：2008-01、2009-01
LOSER_FRAC, LIQ_MIN, LIQ_DAYS, MAX_DEFER = 0.2, 30_000_000, 20, 10
N_NULL, SEED = 500, 20261018


def last_td(cal: list[pd.Timestamp], y: int, m: int) -> pd.Timestamp | None:
    xs = [t for t in cal if t.year == y and t.month == m]
    return xs[-1] if xs else None


def first_td(cal: list[pd.Timestamp], y: int) -> pd.Timestamp | None:
    xs = [t for t in cal if t.year == y]
    return xs[0] if xs else None


def row_at(d: pd.DataFrame, t: pd.Timestamp):
    s = d[d["date"] == t]
    return None if s.empty else s.iloc[0]


def prev_close(d: pd.DataFrame, t: pd.Timestamp):
    s = d[d["date"] < t]
    return None if s.empty else float(s["close"].iloc[-1])


def locked(d: pd.DataFrame, t: pd.Timestamp, kind: str) -> bool:
    r, pc = row_at(d, t), prev_close(d, t)
    if r is None or pc is None:
        return False
    st = costs.limit_status(float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), pc)
    return bool(st.limit_up if kind == "up" else st.limit_down)


def one_year(y: int, codes: list[str], cal: list[pd.Timestamp]) -> dict | None:
    t0, trank, tbuy, tsell0 = first_td(cal, y), last_td(cal, y, 10), last_td(cal, y, 12), last_td(cal, y + 1, 1)
    if None in (t0, trank, tbuy, tsell0):
        return None
    elig, ytd = [], {}
    for c in codes:
        d = T.daily(c)
        if d.empty:
            continue
        r = T.cum_return(d, t0, trank)
        if r is None:
            continue
        w = d[d["date"] <= trank].tail(LIQ_DAYS)
        if len(w) < LIQ_DAYS or float(w["money"].mean()) < LIQ_MIN:
            continue
        elig.append(c); ytd[c] = r
    if len(elig) < 20:
        return None
    k = max(1, int(round(len(elig) * LOSER_FRAC)))
    losers = sorted(elig, key=lambda c: ytd[c])[:k]
    later = [t for t in cal if t >= tsell0]
    rets, n_locked_buy, n_deferred, n_still_locked = {}, 0, 0, 0
    for c in elig:
        d = T.daily(c)
        if row_at(d, tbuy) is None:
            continue
        if locked(d, tbuy, "up"):
            n_locked_buy += c in losers
            continue
        ts, j = tsell0, 0
        while locked(d, ts, "down") and j < MAX_DEFER and j + 1 < len(later):
            j += 1; ts = later[j]
        if j:
            n_deferred += c in losers
            n_still_locked += (c in losers) and locked(d, ts, "down")
        r = T.cum_return(d, tbuy, ts)
        if r is not None:
            rets[c] = r
    lo = [rets[c] for c in losers if c in rets]
    uni = list(rets.values())
    if not lo or len(uni) < 20:
        return None
    rt = costs.round_trip_cost_pct()
    gross = float(np.mean(lo))
    return {"rank_year": y, "jan": f"{y + 1}-01", "n_eligible": len(elig), "n_losers": len(losers), "n_losers_traded": len(lo),
            "n_losers_locked_up_skipped": n_locked_buy, "n_losers_sell_deferred": n_deferred, "n_losers_still_locked_after_10d": n_still_locked,
            "losers_gross": gross, "losers_net_1x": gross - rt, "losers_net_2x": gross - 2 * rt, "losers_net_3x": gross - 3 * rt,
            "universe_gross": float(np.mean(uni)), "excess_net_1x": gross - rt - float(np.mean(uni)),
            "_rets": rets, "_n_losers_traded": len(lo)}


def mdd(eq: np.ndarray) -> float:
    s = pd.Series(eq)
    return float((s / s.cummax() - 1).min() * 100)


def main() -> int:
    if OUT.exists():
        print(f"結果檔 {OUT.name} 已存在：只跑一次，拒絕重跑")
        return 1
    codes = T.codes_with_price()
    cal = T.market_calendar(codes, "2010-01-01", "2024-12-31")
    years = [r for r in (one_year(y, codes, cal) for y in MAIN_YEARS) if r]
    rt = costs.round_trip_cost_pct()
    exc = np.array([r["excess_net_1x"] for r in years])
    real = float(exc.mean())
    rng = np.random.default_rng(SEED)
    null = np.empty(N_NULL)
    for k in range(N_NULL):
        vals = []
        for r in years:
            pool = list(r["_rets"].values())
            pick = rng.choice(len(pool), size=r["_n_losers_traded"], replace=False)
            vals.append(float(np.mean([pool[i] for i in pick])) - rt - r["universe_gross"])
        null[k] = float(np.mean(vals))
    pct = 100.0 * float(np.mean(null <= real))
    jans = [int(r["jan"][:4]) for r in years]
    half = [float(np.mean([e for e, j in zip(exc, jans) if j <= 2017])), float(np.mean([e for e, j in zip(exc, jans) if j >= 2018]))]
    eq = np.cumprod([1.0] + [1 + r["losers_net_1x"] for r in years])
    m = mdd(eq)
    survival = m > -50
    passed = real > 0 and pct >= 90.0 and all(h > 0 for h in half)
    verdict = "VIOLATES_SURVIVAL" if not survival else ("PASS" if passed else "FAIL")
    # 另報：2008-01、2009-01（固定小樣本）
    cal2 = T.market_calendar(codes, "2007-01-01", "2009-12-31")
    small = [c for c in codes if not T.daily(c).empty and T.daily(c)["date"].min() <= pd.Timestamp("2007-01-31")]
    supp = [r for r in (one_year(y, small, cal2) for y in SUPP_YEARS) if r]
    clean = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}
    out = {"prereg": "docs/PREREG_DRAFT_VAR1018_V5_january_reversal_tw.md", "verdict": verdict,
           "mean_excess_net_1x": real, "null_percentile": pct, "null_median": float(np.median(null)), "null_p90": float(np.percentile(null, 90)),
           "half_mean_excess": {"2011-2017": half[0], "2018-2024": half[1]}, "n_januaries": len(years),
           "round_trip_cost_1x": rt, "mean_losers_net": {f"{k}x": float(np.mean([r[f'losers_net_{k}x'] for r in years])) for k in (1, 2, 3)},
           "january_only_strategy_mdd_pct_1x": round(m, 2), "worst_january_net_1x": float(min(r["losers_net_1x"] for r in years)),
           "years": [clean(r) for r in years], "supplementary_2008_2009_not_in_verdict": [clean(r) for r in supp],
           "n_universe_codes": len(codes),
           "simplifications": "價格只做股利還原（分割／減資／面額變更未納入）；母體為本機快取（今天名單，存活者偏誤方向偏好本假設）；漲跌停用 costs.limit_status 近似判定"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"V5：{len(years)} 個 1 月；平均超額（淨 1×）{real:+.4f}、null 百分位 {pct:.1f}、兩半 {[round(h, 4) for h in half]}；"
          f"1 月策略 MDD {m:.1f}%、最差 1 月 {out['worst_january_net_1x']:+.3f}；判定 {verdict}")
    for r in years:
        print(f"  {r['jan']}：母體 {r['n_eligible']}、輸家 {r['n_losers_traded']}／{r['n_losers']}，輸家淨 {r['losers_net_1x']:+.4f}、母體 {r['universe_gross']:+.4f}、超額 {r['excess_net_1x']:+.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
