"""fut_basis_mean_reversion_60d 分年份／regime 分段穩健性複驗
（PENDING_QUEUE.md「FUT.basis均值回歸regime複驗」，FUT_LEADS.md #19 備註）。

事前綁定的判準（看結果前寫死，跑完不得改）：
  分段A：逐年（2000~VAL_END）毛報酬；「單一年份佔全期對數報酬比例」最大值。
  分段B：TAIEX現貨相對自身「前一日」200MA 的多頭／空頭 regime（shift(1) 防未來函數）。
  分段C：四個年代 2000-2005／2006-2012／2013-2020／2021-VAL_END。
判定（三條全過才算「原判定確認穩健」）：
  1. 逐年為正的比例 >= 60%
  2. 單一年份佔全期對數報酬 <= 40%
  3. 多頭、空頭兩個 regime 的年化平均報酬都 > 0
否則「某年份/regime 單獨貢獻異常」→ 比照 #34 銅金比，需重新評估。
純描述性複驗：不做新的隨機控制組、不登記新試驗（未改動候選本身）。
只用 <= VAL_END 資料（holdout 不碰）。零新增 API（本機快取）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import fut_cheap_gate as cg
import fut_basis_series
from validation import holdout

WINDOW = 60
MA = 200


def _ann(r: pd.Series) -> float:
    return float(r.mean() * 252) if len(r) else float("nan")


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"
    series = cg._load_series()
    merged = cg._load_basis(series)
    spot = fut_basis_series.build_basis_series()[["date", "spot_close"]]
    merged = merged.merge(spot, on="date", how="inner").sort_values("date").reset_index(drop=True)
    merged = holdout.cap_to_dev(merged)

    trailing_mean = merged["basis_pct"].rolling(WINDOW).mean().shift(1)
    merged["position"] = -np.sign(merged["basis_pct"] - trailing_mean)
    merged["strat_ret"] = merged["position"].shift(1).fillna(0.0) * merged["ret"]
    merged["year"] = merged["date"].dt.year
    ma = merged["spot_close"].rolling(MA).mean().shift(1)
    merged["regime"] = np.where(merged["spot_close"].shift(1) > ma, "bull", "bear")
    merged.loc[ma.isna(), "regime"] = "warmup"
    v = merged.dropna(subset=["position"]).reset_index(drop=True)
    print(f"rows={len(v)} {v['date'].min().date()}..{v['date'].max().date()}")

    # A 逐年
    g = v.groupby("year")["strat_ret"]
    yr = pd.DataFrame({"n": g.size(), "ret": g.apply(lambda s: (1 + s).prod() - 1),
                       "logret": g.apply(lambda s: np.log1p(s).sum())})
    total_log = yr["logret"].sum()
    yr["share_of_total_log"] = yr["logret"] / total_log
    print("\n=== A. 逐年毛報酬 ===")
    print(yr.to_string(formatters={"ret": "{:+.2%}".format, "share_of_total_log": "{:.1%}".format,
                                    "logret": "{:+.3f}".format}))
    pos_share = float((yr["ret"] > 0).mean())
    max_share = float(yr["share_of_total_log"].max())
    print(f"  逐年為正比例={pos_share:.1%} ({int((yr['ret']>0).sum())}/{len(yr)})；"
          f"單一年份最大佔比={max_share:.1%}（{int(yr['share_of_total_log'].idxmax())}）")
    for tag, mask in [("排除2000-2002", v["year"] > 2002), ("2003起", v["year"] >= 2003)]:
        print(f"  {tag}: 年化平均毛報酬={_ann(v.loc[mask, 'strat_ret']):+.2%}，"
              f"終值={float((1+v.loc[mask, 'strat_ret']).prod()):.3f}x")

    # B regime
    print("\n=== B. 多頭/空頭 regime（現貨 vs 前一日200MA）===")
    rg_ann = {}
    for name in ["bull", "bear"]:
        s = v.loc[v["regime"] == name, "strat_ret"]
        rg_ann[name] = _ann(s)
        print(f"  {name}: n={len(s)} 年化平均毛報酬={rg_ann[name]:+.2%} "
              f"日勝率={(s[s != 0] > 0).mean():.1%}")

    # C 年代
    print("\n=== C. 年代 ===")
    eras = [(2000, 2005), (2006, 2012), (2013, 2020), (2021, 2024)]
    era_ok = 0
    for a, b in eras:
        s = v.loc[(v["year"] >= a) & (v["year"] <= b), "strat_ret"]
        eq = float((1 + s).prod())
        era_ok += eq > 1
        print(f"  {a}-{b}: n={len(s)} 終值={eq:.3f}x 年化平均毛報酬={_ann(s):+.2%}")

    c1 = pos_share >= 0.60
    c2 = max_share <= 0.40
    c3 = rg_ann["bull"] > 0 and rg_ann["bear"] > 0
    print(f"\n判準：1逐年為正>=60% {'PASS' if c1 else 'FAIL'}；2單年佔比<=40% {'PASS' if c2 else 'FAIL'}；"
          f"3兩regime皆正 {'PASS' if c3 else 'FAIL'}；年代終值>1：{era_ok}/4")
    print("總判定：", "原判定確認穩健" if (c1 and c2 and c3) else "有分段貢獻異常，需重新評估")
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
