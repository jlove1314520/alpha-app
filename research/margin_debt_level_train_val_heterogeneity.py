"""`margin_debt_level_v1`（`TRIALS_LEDGER.md`#140/#141）保留疑慮①查證：
TRAIN期corr普遍弱於VAL期（三個trailing窗口104/156/208週皆同款形狀），
是否為VAL期2021-2024特定回撤事件（例如2022年系統性下跌）驅動、還是
真實穩定訊號。

**本輪工作單位（round379接續round377「下一步(a)」）**：只測trailing=156週
（#140/#141的原始參照案例，非新窗口）、horizon=60d(12w)（唯一CHEAP_PASS
窗口，20d已FAIL不重複測）。

**查證方法（事前綁定，非事後掃描）**：
1. 逐年切分TRAIN（2015-2020）與VAL（2021-2024）子期間，各自報告Spearman
   corr、n、level_pct/fwd_mdd_abs的年度均值——單純描述性統計，不對子期間
   本身另做置換檢定顯著性判斷（子期間n太小，個別年份的p值不具參考意義，
   本查證只看corr量級與正負號的年度分布形狀）。
2. **VAL期leave-one-year-out**：依序拿掉2021/2022/2023/2024其中一年，
   用剩餘三年重算Spearman corr，若拿掉某一年後corr大幅下降甚至變號，
   代表VAL期的顯著性是被那一年（極可能是2022年系統性下跌）少數事件驅動，
   不是四年一致的穩定訊號。
3. 列出VAL期fwd_mdd_abs最大的10個觀測點（回撤最深的10個窗口起點），
   連同其level_pct值與所屬年份，供人工核對是否集中在特定事件期間。

零新增API呼叫（完全重用`margin_debt_level_gate.py`/`margin_debt_growth_gate.py`
既有函式與`backfill_margin_debt_market.py`662週檔快取＋既有TAIEX日線快取）。

2026-09-05 馬拉松第379輪（TW軌）新增，接續round377/`TRIALS_LEDGER.md`#141
明確保留的疑慮①，非新假說、非重測已完成的window穩健性。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from margin_debt_growth_gate import (
    N_SHUFFLE,
    SHUFFLE_SEED,
    _forward_window_mdd,
    _load_margin_series,
    _load_taiex_daily,
    _shuffle_percentile,
    _split,
)
from margin_debt_level_gate import TRAILING_WEEKS, _build_pairs, _level_percentile

HORIZON_DAYS = 60  # 12週，唯一CHEAP_PASS窗口


def main():
    print("=== margin_debt_level_v1 TRAIN/VAL異質性查證（疑慮①，trailing=156週, horizon=60d） ===")
    margin = _load_margin_series()
    margin["level_pct"] = _level_percentile(margin["balance"], TRAILING_WEEKS)
    taiex = _load_taiex_daily()
    pairs = _build_pairs(margin, taiex, HORIZON_DAYS, "level_pct")
    pairs["year"] = pairs["date"].dt.year
    train, val = _split(pairs)
    print(f"TRAIN n={len(train)}  VAL n={len(val)}")

    overall_train = spearmanr(train["level_pct"], train["fwd_mdd_abs"])
    overall_val = spearmanr(val["level_pct"], val["fwd_mdd_abs"])
    print(f"\n複現check：TRAIN corr={overall_train.correlation:+.4f}(p={overall_train.pvalue:.4f})  "
          f"VAL corr={overall_val.correlation:+.4f}(p={overall_val.pvalue:.4f})")

    print("\n--- 1. 逐年子期間描述性統計（TRAIN） ---")
    for yr, g in train.groupby("year"):
        if len(g) < 5:
            corr_str = "n太小不計算corr"
        else:
            c, p = spearmanr(g["level_pct"], g["fwd_mdd_abs"])
            corr_str = f"corr={c:+.4f}(p={p:.4f})"
        print(f"  {yr}: n={len(g):3d}  level_pct均值={g['level_pct'].mean():5.1f}  "
              f"fwd_mdd_abs均值={g['fwd_mdd_abs'].mean():.4f}  {corr_str}")

    print("\n--- 1. 逐年子期間描述性統計（VAL） ---")
    val_year_stats = []
    for yr, g in val.groupby("year"):
        if len(g) < 5:
            corr_str = "n太小不計算corr"
            c = np.nan
        else:
            c, p = spearmanr(g["level_pct"], g["fwd_mdd_abs"])
            corr_str = f"corr={c:+.4f}(p={p:.4f})"
        print(f"  {yr}: n={len(g):3d}  level_pct均值={g['level_pct'].mean():5.1f}  "
              f"fwd_mdd_abs均值={g['fwd_mdd_abs'].mean():.4f}  {corr_str}")
        val_year_stats.append({"year": yr, "n": len(g), "corr": c,
                                "level_pct_mean": g["level_pct"].mean(),
                                "fwd_mdd_abs_mean": g["fwd_mdd_abs"].mean()})

    print("\n--- 2. VAL期leave-one-year-out ---")
    loyo_rows = []
    years = sorted(val["year"].unique())
    for drop_yr in years:
        remaining = val[val["year"] != drop_yr]
        c, p = spearmanr(remaining["level_pct"], remaining["fwd_mdd_abs"])
        shuf = _shuffle_percentile(remaining["level_pct"].to_numpy(),
                                    remaining["fwd_mdd_abs"].to_numpy(), N_SHUFFLE, SHUFFLE_SEED)
        print(f"  拿掉{drop_yr}年 (剩餘n={len(remaining)}): corr={c:+.4f}(p={p:.4f})  "
              f"洗牌null percentile={shuf['percentile']:.1f}")
        loyo_rows.append({"dropped_year": drop_yr, "n_remaining": len(remaining),
                           "corr": c, "p": p, "null_percentile": shuf["percentile"]})

    print("\n--- 3. VAL期fwd_mdd_abs最深的10個觀測點 ---")
    top10 = val.sort_values("fwd_mdd_abs", ascending=False).head(10)
    for _, row in top10.iterrows():
        print(f"  {row['date'].date()}  year={row['year']}  level_pct={row['level_pct']:5.1f}  "
              f"fwd_mdd_abs={row['fwd_mdd_abs']:.4f}")

    print("\n=== 判讀 ===")
    corr_all = overall_val.correlation
    max_drop = max(loyo_rows, key=lambda r: abs(corr_all - r["corr"]))
    min_corr_loyo = min(loyo_rows, key=lambda r: r["corr"])
    print(f"  全樣本VAL corr={corr_all:+.4f}；leave-one-year-out中變動最大的是拿掉{max_drop['dropped_year']}年"
          f"（corr變為{max_drop['corr']:+.4f}，差異{corr_all - max_drop['corr']:+.4f}）")
    print(f"  leave-one-year-out中最低corr出現在拿掉{min_corr_loyo['dropped_year']}年"
          f"（corr={min_corr_loyo['corr']:+.4f}）——若仍>0.3以上且顯著，代表非單一年份主導；"
          f"若接近0或變號，代表VAL顯著性由該年（含{min_corr_loyo['dropped_year']}年）少數觀測驅動")
    top10_years = top10["year"].value_counts()
    print(f"  VAL期fwd_mdd_abs最深10個觀測點的年份分布: {dict(top10_years)}")

    pd.DataFrame(val_year_stats).to_csv("data/margin_debt_level_val_year_stats.csv", index=False)
    pd.DataFrame(loyo_rows).to_csv("data/margin_debt_level_val_leave_one_year_out.csv", index=False)
    top10.to_csv("data/margin_debt_level_val_top10_drawdowns.csv", index=False)
    return {"val_year_stats": val_year_stats, "loyo": loyo_rows}


if __name__ == "__main__":
    main()
