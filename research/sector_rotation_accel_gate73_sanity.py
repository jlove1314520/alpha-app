# -*- coding: utf-8 -*-
"""#73 產業金流加速度——GATE_SEQUENCE 第1關 sanity（驗證帽；只查資料/邏輯，不算任何報酬）。

**不做回測、不比較績效、不登記 TRIALS**（沒有統計檢定；sanity 是前置檢查）。
檢查項（規格見 HYPOTHESIS_QUEUE #73 與第3輪事前綁定「尺度標準化差值」）：
  S1 金額單位：T86 淨買賣股數是「股」不是「張」——用同日 Trading_Volume 核對
     （單一股票法人淨買賣股數絕對值不應超過當日成交量；且比值中位數不應落在 1/1000 量級）。
     並核對 Trading_money ≈ Trading_Volume × 加權均價，確認 close 與成交金額同一量級（close 未還原）。
  S2 無未來函數：accel(t) 只用 t 以前資料——把寬表截斷到 t 重算，t 那天的值必須與全序列算出的相同。
  S3 月頻前20%：每月第一個交易日的訊號取「前一交易日」值（T86 盤後才公布，當日開盤前只看得到 t-1）；
     檢查每月有效產業數、選出產業數（=ceil? 這裡事前綁定 round(0.2×n)，至少1）、成分股數、
     月間產業重疊率（換手代理）、產業覆蓋（每個產業被選中的月份數，看是否只集中在少數產業）。
  S4 方向：accel>0 必須對應 MA5 相對 MA20 的資金流入偏多（單純算術方向核對，不看未來報酬）。
  S5 全宇宙 vs 核心宇宙訊號一致性：兩套寬表各自算 accel，逐月前20%集合的 Jaccard 重疊。

訊號（第3輪事前綁定，本檔不得改）：accel = (MA5 − MA20) / S，S＝過去120日 |日金額| 均值（min_periods=60，只用當下以前）。
輸出：research/sector_rotation_accel_gate73_sanity.json（進 git）。
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation.holdout import VAL_END  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ALL = DATA / "sector_flow_daily_gate73.parquet"
CORE = DATA / "sector_flow_daily_gate73_core.parquet"
OUT = HERE / "sector_rotation_accel_gate73_sanity.json"
T86_DIR = DATA / "raw_twse_t86"
PRICE_DIR = DATA / "raw"
COMPANY_INFO = HERE.parent / "data" / "company_info.json"

SCALE_WINDOW, SCALE_MIN = 120, 60
TOP_FRAC = 0.20
_PRICE_RE = re.compile(r"^TaiwanStockPrice__(\w+)__(\d{4}-\d\d-\d\d)__")


def accel_frame(wide: pd.DataFrame) -> pd.DataFrame:
    ma5 = wide.rolling(5, min_periods=5).mean()
    ma20 = wide.rolling(20, min_periods=20).mean()
    scale = wide.abs().rolling(SCALE_WINDOW, min_periods=SCALE_MIN).mean()
    scale = scale.where(scale > 0)
    return (ma5 - ma20) / scale


def month_first_signal_dates(idx: pd.Index) -> list[tuple[str, str]]:
    """回傳 [(再平衡日, 訊號日=前一交易日)]，每月第一個交易日。"""
    s = pd.Series(list(idx))
    out = []
    ym = s.str[:7]
    for i in range(1, len(s)):
        if ym.iloc[i] != ym.iloc[i - 1]:
            out.append((s.iloc[i], s.iloc[i - 1]))
    return out


def pick_top(row: pd.Series) -> set[str]:
    v = row.dropna()
    n = len(v)
    if n < 5:
        return set()
    k = max(1, round(TOP_FRAC * n))
    return set(v.sort_values(ascending=False, kind="mergesort").index[:k])


def s1_units() -> dict:
    """單位核對：抽樣 40 檔 × 全部 T86 日期。"""
    t86 = pd.concat(
        [pd.read_parquet(p) for p in sorted(glob.glob(str(T86_DIR / "T86_*.parquet")))],
        ignore_index=True)
    t86 = t86[t86["stock_id"].str.match(r"^[1-9][0-9]{3}$") & (t86["date"] <= VAL_END)]
    t86["net"] = t86["foreign_net"] + t86["trust_net"] + t86["dealer_net"]
    ids = sorted(t86["stock_id"].unique())
    rng = np.random.default_rng(73)
    pick = list(rng.choice(ids, size=min(40, len(ids)), replace=False))
    best: dict[str, tuple[str, str]] = {}
    for p in glob.glob(str(PRICE_DIR / "TaiwanStockPrice__*.parquet")):
        m = _PRICE_RE.match(os.path.basename(p))
        if m and m.group(1) in pick and (m.group(1) not in best or m.group(2) < best[m.group(1)][0]):
            best[m.group(1)] = (m.group(2), p)
    ratios, over, n, money_ratio = [], 0, 0, []
    for sid, (_, p) in best.items():
        px = pd.read_parquet(p, columns=["date", "stock_id", "Trading_Volume", "Trading_money", "close"])
        m = t86[t86["stock_id"] == sid].merge(px, on=["date", "stock_id"])
        m = m[m["Trading_Volume"] > 0]
        r = m["net"].abs() / m["Trading_Volume"]
        ratios.extend(r.tolist())
        over += int((r > 1.0).sum())
        n += len(r)
        vwap = m["Trading_money"] / m["Trading_Volume"]
        mr = (m["close"] / vwap).replace([np.inf, -np.inf], np.nan).dropna()
        money_ratio.extend(mr.tolist())
    ra = np.array(ratios)
    mo = np.array(money_ratio)
    return {
        "sampled_stocks": len(best), "matched_rows": n,
        "abs_net_over_volume_median": round(float(np.median(ra)), 5),
        "abs_net_over_volume_p99": round(float(np.quantile(ra, 0.99)), 4),
        "rows_abs_net_gt_volume": over,
        "rows_abs_net_gt_volume_frac": round(over / n, 6) if n else None,
        "close_over_vwap_median": round(float(np.median(mo)), 4),
        "close_over_vwap_p01_p99": [round(float(np.quantile(mo, 0.01)), 3), round(float(np.quantile(mo, 0.99)), 3)],
        "note": "單位若是『張』(1張=1000股)，abs_net/volume 中位數會低約1000倍且 close/vwap 不受影響；"
                "若 |net|>volume 比例極低且中位數在 1e-3~1e-1 量級，判定單位為『股』，與 Trading_Volume（股）一致。",
    }


def main() -> int:
    wide_all = pd.read_parquet(ALL)
    wide_core = pd.read_parquet(CORE)
    res: dict = {"note": "Gate 1 sanity；無回測、無績效比較、未登記TRIALS", "val_end_cap": VAL_END,
                 "dates": [wide_all.index.min(), wide_all.index.max()],
                 "sectors": int(wide_all.shape[1])}
    assert wide_all.index.max() <= VAL_END, "寬表超過 VAL_END（碰到 holdout 區間）"

    # S1
    res["S1_units"] = s1_units()

    # S2 無未來函數
    acc = accel_frame(wide_all)
    rng = np.random.default_rng(2)
    valid_idx = np.where(acc.notna().sum(axis=1).values > 5)[0]
    sample = rng.choice(valid_idx, size=min(25, len(valid_idx)), replace=False)
    maxdiff = 0.0
    for i in sample:
        trunc = accel_frame(wide_all.iloc[: i + 1]).iloc[-1]
        full = acc.iloc[i]
        d = (trunc - full).abs().max(skipna=True)
        maxdiff = max(maxdiff, 0.0 if pd.isna(d) else float(d))
        both_nan = (trunc.isna() == full.isna()).all()
        if not both_nan:
            maxdiff = max(maxdiff, 1.0)
    res["S2_no_lookahead"] = {"sampled_dates": int(len(sample)), "max_abs_diff_trunc_vs_full": maxdiff,
                              "pass": maxdiff < 1e-9}

    # S3 月頻前20%
    comp = json.loads(COMPANY_INFO.read_text(encoding="utf-8"))["companies"]
    per_sector_n = {}
    for sid, rec in comp.items():
        ind = (rec or {}).get("industry")
        if ind:
            per_sector_n[ind] = per_sector_n.get(ind, 0) + 1
    months = month_first_signal_dates(wide_all.index)
    rows, prev, sel_count = [], set(), {}
    for reb, sig in months:
        if sig not in acc.index:
            continue
        top = pick_top(acc.loc[sig])
        nvalid = int(acc.loc[sig].notna().sum())
        if not top:
            continue
        for s in top:
            sel_count[s] = sel_count.get(s, 0) + 1
        overlap = len(top & prev) / len(top | prev) if prev else None
        rows.append({"reb": reb, "n_valid": nvalid, "n_sel": len(top),
                     "stocks": int(sum(per_sector_n.get(s, 0) for s in top)),
                     "jaccard_prev": overlap})
        prev = top
    df = pd.DataFrame(rows)
    jac = df["jaccard_prev"].dropna()
    res["S3_monthly_top20"] = {
        "rebalance_months": int(len(df)),
        "first_reb": df["reb"].iloc[0], "last_reb": df["reb"].iloc[-1],
        "n_valid_sectors_min_med_max": [int(df.n_valid.min()), float(df.n_valid.median()), int(df.n_valid.max())],
        "n_selected_sectors_min_med_max": [int(df.n_sel.min()), float(df.n_sel.median()), int(df.n_sel.max())],
        "selected_stocks_static_min_med_max": [int(df.stocks.min()), float(df.stocks.median()), int(df.stocks.max())],
        "month_to_month_jaccard_mean_median": [round(float(jac.mean()), 3), round(float(jac.median()), 3)],
        "fully_replaced_months_frac": round(float((jac == 0).mean()), 3),
        "distinct_sectors_ever_selected": len(sel_count),
        "top5_sector_selection_share": round(sum(sorted(sel_count.values(), reverse=True)[:5]) / sum(sel_count.values()), 3),
        "selection_count_by_sector_top8": dict(sorted(sel_count.items(), key=lambda kv: -kv[1])[:8]),
        "sectors_never_selected": sorted(set(wide_all.columns) - set(sel_count)),
    }

    # S4 方向：accel 與 MA5>MA20 同號
    ma5 = wide_all.rolling(5, min_periods=5).mean()
    ma20 = wide_all.rolling(20, min_periods=20).mean()
    both = acc.notna() & ma5.notna() & ma20.notna()
    agree = ((acc > 0) == (ma5 > ma20)) & both
    res["S4_direction"] = {"valid_cells": int(both.values.sum()),
                           "sign_agree_frac": round(float(agree.values.sum() / both.values.sum()), 6)}

    # S5 全宇宙 vs 核心
    acc_c = accel_frame(wide_core)
    cols = sorted(set(acc.columns) & set(acc_c.columns))
    js = []
    for reb, sig in months:
        if sig in acc.index and sig in acc_c.index:
            a, b = pick_top(acc.loc[sig, cols]), pick_top(acc_c.loc[sig, cols])
            if a and b:
                js.append(len(a & b) / len(a | b))
    res["S5_all_vs_core"] = {"months": len(js), "jaccard_mean": round(float(np.mean(js)), 3),
                             "jaccard_median": round(float(np.median(js)), 3),
                             "frac_months_jaccard_ge_0.5": round(float(np.mean(np.array(js) >= 0.5)), 3)}

    # NaN 爆炸檢查
    res["nan_check"] = {"accel_valid_frac": round(float(acc.notna().values.mean()), 4),
                        "inf_cells": int(np.isinf(acc.values.astype(float)).sum())}

    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        raise
