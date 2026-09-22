# -*- coding: utf-8 -*-
"""PEAD 自我校準（`PENDING_QUEUE.md` 方法.二前置條件，2026-09-22互動視窗CC）。

目的：`tail_test.py`是全新工具，還沒有在真實市場資料上驗證過它抓不抓得到
「已知存在」的右尾訊號。裁示原文：「測不出已知訊號代表工具壞了，不是市場
沒訊號」——本腳本用學界有大量文獻支持的 PEAD（Post-Earnings-Announcement
Drift）當校準基準：財報公布後3日累積報酬（本專案簡化為原始累積報酬，非
market-model異常報酬，理由見下）最高的前10%個股，理論上會在後續(t+1/t+5/
t+20)延續同方向漂移。如果`tail_test()`在這個已知案例上量不出任何右尾/
中位數差異，先懷疑工具，不懷疑市場。

**CAR定義的簡化說明（誠實揭露，非隱藏）**：學界標準PEAD用market-model
或market-adjusted累積異常報酬(CAR)，本腳本用原始累積報酬（未扣大盤同期
報酬）。`PENDING_QUEUE.md`原文對這一段的描述本身就是「財報公布後3日累積
報酬」（無「異常」二字），採用原始報酬與裁示原文一致；若要換成真正的
market-adjusted CAR，需要額外扣減對應期間大盤報酬，留待這個校準有需要
時再做（原始CAR夠格當自我校準基準——PEAD文獻對兩種定義的方向結論一致，
只有量級略有差異）。

對照組建構（裁示：「同時間窗/同產業/同市值分位、未觸發訊號個股，PIT對齊」）：
- 同時間窗：事件進場日所在的日曆季（year-quarter）
- 同產業：`score.py::load_industry_map()`（靜態快照，非PIT，是既有專案
  容忍的做法——見該函式docstring「membership/classification metadata，
  非price/volume時間序列，沒有前視風險」）
- 同市值分位：用`core_tilt_backtest.py::build_market_cap_lookup()`／
  `market_cap_at_date()`（PBR×權益重建市值，僅用本機已快取的PER/資產
  負債表parquet，不額外發API請求）在全體事件的市值分布上切五分位
- 未觸發訊號個股：CAR3不在前10%的事件（同一個事件池）
- PIT對齊：訊號組與對照組兩者的進場日都用`entry_idx = 公布日pit_date之後
  第一個交易日`（跟`monthly_revenue_event_study.py::_stock_events()`
  同一個既有慣例），不使用公布當天收盤價

沿用既有元件（不重新發明）：`adjusted_price_series`（還原股價+VAL_END
自動截斷）、`factors.py::_quarterly_eps`（已含PIT邏輯的`pit_date`欄位）、
`factor_ic.py::sample_universe_ids`（既有300檔快取樣本）、`validation.holdout`
（洩漏斷言）、`trial_registry.register_trial()`（登記強制化唯一入口）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from core_tilt_backtest import build_market_cap_lookup, market_cap_at_date
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from factors import _quarterly_eps
from score import load_industry_map
from tail_test import tail_test
from validation import holdout

HORIZONS = (1, 5, 20)
CAR_WINDOW = 3  # 裁示原文「3日CAR」
TOP_DECILE = 0.10
MC_QUANTILE_BUCKETS = 5
MIN_EVENTS_PER_STOCK_PRICE_HISTORY = 260  # 跟monthly_revenue_event_study.py同一個門檻


def _stock_events(stock_id: str) -> pd.DataFrame:
    """單一股票的財報公布事件表：pit_date, entry_date, car3, fwd1, fwd5, fwd20。"""
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟monthly_revenue_event_study.py同一個容錯尺度
        return pd.DataFrame()
    if px.empty or len(px) < MIN_EVENTS_PER_STOCK_PRICE_HISTORY:
        return pd.DataFrame()
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in pead_calibration_gate")

    try:
        eps = _quarterly_eps(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        return pd.DataFrame()
    if eps.empty:
        return pd.DataFrame()

    px = px.sort_values("date").reset_index(drop=True)
    dates = px["date"].tolist()
    adj_close = px["adj_close"].tolist()
    max_h = max(HORIZONS)

    rows = []
    for _, r in eps.iterrows():
        pit = r["pit_date"]
        if pd.isna(pit):
            continue
        entry_idx = None
        for i, d in enumerate(dates):
            if d > pit:
                entry_idx = i
                break
        if entry_idx is None:
            continue
        window_end_idx = entry_idx + CAR_WINDOW
        if window_end_idx + max_h >= len(dates):
            continue
        p0, p_win_end = adj_close[entry_idx], adj_close[window_end_idx]
        if pd.isna(p0) or pd.isna(p_win_end) or p0 <= 0:
            continue
        car3 = p_win_end / p0 - 1
        row = {
            "stock_id": stock_id, "pit_date": pit, "entry_date": dates[entry_idx],
            "car3": float(car3),
        }
        ok = True
        for h in HORIZONS:
            p_h = adj_close[window_end_idx + h]
            if pd.isna(p_h) or p_win_end <= 0:
                ok = False
                break
            row[f"fwd{h}"] = float(p_h / p_win_end - 1)
        if not ok:
            continue
        rows.append(row)
    return pd.DataFrame(rows)


def _mc_quantile_bucket(events: pd.DataFrame, mc_lookup: dict) -> pd.DataFrame:
    events = events.copy()
    mc = []
    for _, r in events.iterrows():
        v = market_cap_at_date(r["stock_id"], pd.Timestamp(r["entry_date"]), mc_lookup)
        mc.append(v)
    events["market_cap"] = mc
    n_before = len(events)
    events = events[events["market_cap"].notna() & (events["market_cap"] > 0)].copy()
    n_dropped_mc = n_before - len(events)
    try:
        events["mc_quantile"] = pd.qcut(events["market_cap"], MC_QUANTILE_BUCKETS, labels=False, duplicates="drop")
    except ValueError:
        events["mc_quantile"] = 0
    return events, n_dropped_mc


def build_event_table(sample_ids: list[str], verbose: bool = True) -> pd.DataFrame:
    industry_map = load_industry_map()
    all_events = []
    n_ok = 0
    t0 = time.time()
    for i, sid in enumerate(sample_ids):
        ev = _stock_events(sid)
        if not ev.empty:
            ev["industry"] = industry_map.get(sid)
            all_events.append(ev)
            n_ok += 1
        if verbose and (i + 1) % 20 == 0:
            print(f"  progress {i+1}/{len(sample_ids)}, {n_ok} usable so far, {time.time()-t0:.0f}s elapsed")
    if not all_events:
        return pd.DataFrame()
    events = pd.concat(all_events, ignore_index=True)
    holdout.assert_no_holdout_leakage(events, date_col="entry_date", context="pead_calibration_gate events (final)")

    mc_lookup = build_market_cap_lookup(sorted(events["stock_id"].unique().tolist()))
    events, n_dropped_mc = _mc_quantile_bucket(events, mc_lookup)
    n_dropped_industry = int(events["industry"].isna().sum())
    events = events[events["industry"].notna()].copy()
    events["time_bucket"] = pd.to_datetime(events["entry_date"]).dt.to_period("Q").astype(str)
    events["bucket_key"] = (
        events["time_bucket"].astype(str) + "|" + events["industry"].astype(str) + "|" + events["mc_quantile"].astype(str)
    )
    if verbose:
        print(f"事件建表完成：{len(events)}筆（市值查無丟棄{n_dropped_mc}筆、產業查無丟棄{n_dropped_industry}筆）")
    return events


def run_calibration(events: pd.DataFrame) -> dict:
    n_top = max(1, int(np.ceil(len(events) * TOP_DECILE)))
    signal_df = events.sort_values("car3", ascending=False).iloc[:n_top]
    non_signal_df = events.sort_values("car3", ascending=False).iloc[n_top:]
    active_buckets = set(signal_df["bucket_key"])
    control_df = non_signal_df[non_signal_df["bucket_key"].isin(active_buckets)]

    print(f"\n訊號組(car3前10%) n={len(signal_df)}，car3範圍=[{signal_df['car3'].min():+.4f}, {signal_df['car3'].max():+.4f}]")
    print(f"對照組(同時間窗/同產業/同市值分位、未觸發訊號) n={len(control_df)}，"
          f"命中bucket數={len(active_buckets)}/{events['bucket_key'].nunique()}")

    results = {}
    for h in HORIZONS:
        out = tail_test(
            signal_df["entry_date"].tolist(),
            signal_df[f"fwd{h}"].tolist(),
            control_df[f"fwd{h}"].tolist(),
            horizon=h,
        )
        results[h] = out
        if out["insufficient_n"]:
            print(f"t+{h}: 樣本不足 (n_signal={out['n_signal']}, n_control={out['n_control']})，跳過")
            continue
        print(f"t+{h}: median_diff={out['median_diff']:+.4f} (90%CI=[{out['median_diff_ci90'][0]:+.4f}, {out['median_diff_ci90'][1]:+.4f}])  "
              f"p90_diff={out['p90_diff']:+.4f}  right_tail(sig/ctl)={out['right_tail_share_signal']:.3f}/{out['right_tail_share_control']:.3f}  "
              f"left_tail(sig/ctl)={out['left_tail_share_signal']:.3f}/{out['left_tail_share_control']:.3f}  "
              f"EV_net_diff={out['expected_value_diff_net']:+.4f}")
    return {"n_signal": len(signal_df), "n_control": len(control_df), "n_events_total": len(events),
            "n_buckets_hit": len(active_buckets), "n_buckets_total": int(events["bucket_key"].nunique()),
            "by_horizon": results}


def calibration_verdict(summary: dict) -> tuple[bool, str]:
    """校準通過的判準：至少要有一個horizon顯示「訊號組續航優於對照組」的
    方向一致證據（median_diff>0 或 right_tail_share_signal>control），且
    以t+20（PEAD文獻最常見的驗證窗口）為主要依據，t+1/t+5作輔助佐證。
    這不是策略PASS/FAIL的判定（沒有走GATE_SEQUENCE），只是回答「工具量
    得到已知訊號嗎」。
    """
    h20 = summary["by_horizon"].get(20)
    if h20 is None or h20["insufficient_n"]:
        return False, "t+20樣本不足，無法判斷校準是否成功"
    drift_positive = h20["median_diff"] > 0
    fatter_right_tail = h20["right_tail_share_signal"] > h20["right_tail_share_control"]
    if drift_positive and fatter_right_tail:
        return True, f"t+20 median_diff={h20['median_diff']:+.4f}>0 且 right_tail_share訊號組({h20['right_tail_share_signal']:.3f})>對照組({h20['right_tail_share_control']:.3f})，工具在已知訊號上量得出方向正確的右尾差異"
    return False, (f"t+20 median_diff={h20['median_diff']:+.4f}（{'正' if drift_positive else '非正'}）、"
                    f"right_tail_share訊號組={h20['right_tail_share_signal']:.3f} vs 對照組={h20['right_tail_share_control']:.3f}"
                    f"（{'訊號組較胖' if fatter_right_tail else '未較胖'}）——未同時滿足兩個校準條件")


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== PEAD自我校準 (方法.二前置條件, tail_test.py) ===")
    print(f"Sample: {len(sample_ids)}檔 (SAMPLE_SEED={SAMPLE_SEED})，CAR window={CAR_WINDOW}交易日，horizons={HORIZONS}")

    events = build_event_table(sample_ids)
    if events.empty:
        print("校準 FAIL：零事件，資料層級問題（不是市場沒訊號）")
        return {"passes": False, "reason": "no_events"}

    summary = run_calibration(events)
    passed, reason = calibration_verdict(summary)
    print(f"\n=== 校準結論 ===\n{'PASS' if passed else 'FAIL'}：{reason}")
    summary["calibration_passed"] = passed
    summary["calibration_reason"] = reason
    return summary


if __name__ == "__main__":
    import json
    out = main()
    out_path = Path(__file__).parent / "pead_calibration_gate_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
