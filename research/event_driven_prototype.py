# -*- coding: utf-8 -*-
"""事件驅動原型（`PENDING_QUEUE.md` 方法.三，2026-09-22互動視窗CC，前置條件
方法.二PEAD自我校準已PASS——`tail_test.py`在已知訊號上量得出方向正確的
右尾/中位數差異）。

跟方法.二（`pead_calibration_gate.py`）的關鍵差異：方法.二分組依據是「事後」
的3日累積報酬(car3)——那是用來校準工具本身的已知效應，事件發生當下並不
知道car3會是多少。方法.三要求「分組依事件當下意外程度(非事後報酬)」，
所以這裡分組用的是財報/月營收公布**當下就已知**的意外程度統計量（SUE，
Standardized Unexpected Earnings/Revenue，`factors.py::_eps_surprise_sue`／
`_revenue_surprise_sue`，季節差分後用自身歷史波動度標準化），不是事件後
的股價反應。這才是一個真正可以在T日當天執行的訊號設計原型。

E1＝財報公布日（`_eps_surprise_sue`的`pit_date`，內部即`statutory_
quarterly_pit_date()`）、E2＝月營收公布日（`_revenue_surprise_sue`的
`pit_date`，內部即`pit.py::month_revenue_pit()`的法定公布日）。E3(除權息)/
E4(法說會)裁示原文本身就說「先做E1/E2」，E3/E4留待下一步，不在本檔案
範圍內。

進場＝公布日後第一個交易日（跟`pead_calibration_gate.py`同一個既有慣例），
前瞻報酬t+1/t+5/t+20一律從**進場價**起算（不是像方法.二那樣先累積3日
car再往後算——這裡沒有car3這個事後窗口，訊號本身就是SUE，進場當天就是
t=0）。訊號組＝SUE前10%（同`bucket_key`＝同季度×同產業×同市值五分位，
跟方法.二同一組對照建構規則），對照組＝同bucket、非前10%個股。

**定位（誠實揭露，不是GATE_SEQUENCE判定）**：本檔案只做`tail_test()`右尾/
中位數方向性檢查，**沒有**隨機控制組排列檢定、沒有train/val樣本外切分、
沒有成本敏感度掃描——這些都是GATE_SEQUENCE的關卡，本檔案的定位跟
`monthly_revenue_event_study.py`（cheap gate等級, standalone bonferroni_n=1）
更輕，屬於「原型」（prototype）：只回答「這個當下可執行的訊號設計，值不值得
再往下投入做完整GATE_SEQUENCE」。因此一律登記`verdict=EXPERIMENTAL`，不
宣稱PASS也不宣稱FAIL（PENDING_QUEUE.md裁示原文本身只要求「計入
TRIALS_REGISTRY且標power_class」，沒有要求跑完整關卡）。

沿用既有元件（不重新發明）：`adjusted_price_series`、`factors.py`既有SUE
因子、`pead_calibration_gate.py::_mc_quantile_bucket`（bucket建構邏輯完全
相同，直接重用不複製）、`tail_test()`、`trials_power_audit.DEGENERATE_N_
FLOOR`（power_class判準跟方法.一同一個門檻，不另訂新數字）、
`trial_registry.register_trial()`。
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
from core_tilt_backtest import build_market_cap_lookup
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from factors import _eps_surprise_sue, _revenue_surprise_sue
from pead_calibration_gate import _mc_quantile_bucket
from score import load_industry_map
from tail_test import tail_test
from trials_power_audit import DEGENERATE_N_FLOOR
from validation import holdout

HORIZONS = (1, 5, 20)
TOP_DECILE = 0.10
MIN_PRICE_HISTORY = 260  # 跟pead_calibration_gate.py同一個門檻
# 2026-09-23【方法.三續.E1重判 續.B】波動度配對控制組第4維：事件日前
# 60交易日已實現波動度（PIT，視窗嚴格結束於entry_idx-1，不含事件當天，
# 見`_stock_events()`裡`entry_idx - VOL_WINDOW : entry_idx`的切片）。
VOL_WINDOW = 60

# E3(除權息)/E4(法說會) 依裁示原文「先做E1/E2」不在本檔案範圍。
EVENT_TYPES = {
    "E1_財報公布(SUE)": {"surprise_fn": _eps_surprise_sue, "surprise_col": "eps_sue"},
    "E2_月營收公布(SUE)": {"surprise_fn": _revenue_surprise_sue, "surprise_col": "revenue_sue"},
}


def _stock_events(stock_id: str, surprise_fn, surprise_col: str) -> pd.DataFrame:
    """單一股票的事件表：pit_date, entry_date, surprise, fwd1, fwd5, fwd20。
    跟`pead_calibration_gate.py::_stock_events`的差異：這裡沒有car3中繼窗口，
    前瞻報酬直接從進場價（entry_idx，也就是t=0）算起。
    """
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception:  # noqa: BLE001 -- 跟pead_calibration_gate.py同一個容錯尺度
        return pd.DataFrame()
    if px.empty or len(px) < MIN_PRICE_HISTORY:
        return pd.DataFrame()
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in event_driven_prototype")

    try:
        sue = surprise_fn(stock_id, START_DATE)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if sue.empty:
        return pd.DataFrame()

    px = px.sort_values("date").reset_index(drop=True)
    dates = px["date"].tolist()
    adj_close = px["adj_close"].tolist()
    max_h = max(HORIZONS)

    rows = []
    for _, r in sue.iterrows():
        pit = r["pit_date"]
        surprise = r[surprise_col]
        if pd.isna(pit) or pd.isna(surprise):
            continue
        entry_idx = None
        for i, d in enumerate(dates):
            if d > pit:
                entry_idx = i
                break
        if entry_idx is None or entry_idx + max_h >= len(dates):
            continue
        p0 = adj_close[entry_idx]
        if pd.isna(p0) or p0 <= 0:
            continue
        # 續.B：事件日前VOL_WINDOW個交易日已實現波動度，視窗嚴格在entry_idx
        # 之前（[entry_idx-VOL_WINDOW, entry_idx)，不含entry_idx本身這個
        # PIT邊界——事件當天的價格反應不得洩漏進波動度估計）。
        if entry_idx >= VOL_WINDOW:
            window = np.asarray(adj_close[entry_idx - VOL_WINDOW: entry_idx], dtype=float)
            # 實測發現少數視窗含0價（資料品質問題，非本函式要修的範圍），
            # 觸發RuntimeWarning（0/0或x/0）；實測結果顯示最終`pre_event_vol`
            # 沒有inf值漏出（原本`~np.isnan`的濾法剛好沒漏，因為本次資料
            # 剛好都是0/0產生nan而非x/0產生inf），但`~np.isnan`理論上無法
            # 攔住x/0產生的inf，改用`np.isfinite`同時濾nan與inf是更穩健的
            # 防護，`np.errstate`只是關掉警告訊息本身。
            with np.errstate(divide="ignore", invalid="ignore"):
                rets = window[1:] / window[:-1] - 1.0
            rets = rets[np.isfinite(rets)]
            pre_event_vol = float(np.std(rets, ddof=1)) if len(rets) >= 2 else None
        else:
            pre_event_vol = None
        row = {
            "stock_id": stock_id, "pit_date": pit, "entry_date": dates[entry_idx],
            "surprise": float(surprise), "pre_event_vol": pre_event_vol,
        }
        ok = True
        for h in HORIZONS:
            p_h = adj_close[entry_idx + h]
            if pd.isna(p_h):
                ok = False
                break
            row[f"fwd{h}"] = float(p_h / p0 - 1)
        if not ok:
            continue
        rows.append(row)
    return pd.DataFrame(rows)


def build_event_table(sample_ids: list[str], surprise_fn, surprise_col: str, verbose: bool = True) -> pd.DataFrame:
    industry_map = load_industry_map()
    all_events = []
    n_ok = 0
    t0 = time.time()
    for i, sid in enumerate(sample_ids):
        ev = _stock_events(sid, surprise_fn, surprise_col)
        if not ev.empty:
            ev["industry"] = industry_map.get(sid)
            all_events.append(ev)
            n_ok += 1
        if verbose and (i + 1) % 50 == 0:
            print(f"  progress {i+1}/{len(sample_ids)}, {n_ok} usable so far, {time.time()-t0:.0f}s elapsed")
    if not all_events:
        return pd.DataFrame()
    events = pd.concat(all_events, ignore_index=True)
    holdout.assert_no_holdout_leakage(events, date_col="entry_date", context="event_driven_prototype events (final)")

    mc_lookup = build_market_cap_lookup(sorted(events["stock_id"].unique().tolist()))
    events, n_dropped_mc = _mc_quantile_bucket(events, mc_lookup)
    n_dropped_industry = int(events["industry"].isna().sum())
    events = events[events["industry"].notna()].copy()
    events["time_bucket"] = pd.to_datetime(events["entry_date"]).dt.to_period("Q").astype(str)
    events["bucket_key"] = (
        events["time_bucket"].astype(str) + "|" + events["industry"].astype(str) + "|" + events["mc_quantile"].astype(str)
    )
    # 續.B：第4配對維度（波動度五分位）。只對`pre_event_vol`非NaN的列算
    # `vol_quantile`／`bucket_key_vol`，NaN（entry_idx<VOL_WINDOW，事件前
    # 歷史不足60個交易日）的列這兩欄留NaN，不強行分配一個假分位——4維
    # 分析時再篩掉，3維（既有）分析完全不受影響（`bucket_key`欄不變）。
    n_dropped_vol = int(events["pre_event_vol"].isna().sum())
    has_vol = events["pre_event_vol"].notna()
    events["vol_quantile"] = np.nan
    if has_vol.sum() >= 5:
        try:
            events.loc[has_vol, "vol_quantile"] = pd.qcut(
                events.loc[has_vol, "pre_event_vol"], 5, labels=False, duplicates="drop"
            )
        except ValueError:
            events.loc[has_vol, "vol_quantile"] = 0
    events["bucket_key_vol"] = None
    events.loc[has_vol, "bucket_key_vol"] = (
        events.loc[has_vol, "bucket_key"].astype(str) + "|" + events.loc[has_vol, "vol_quantile"].astype(str)
    )
    if verbose:
        print(f"事件建表完成：{len(events)}筆（市值查無丟棄{n_dropped_mc}筆、產業查無丟棄{n_dropped_industry}筆、"
              f"波動度分位查無{n_dropped_vol}筆不影響3維分析）")
    return events


def run_event_study(events: pd.DataFrame) -> dict:
    """分組依SUE（事件當下意外程度，非事後報酬）——前10%為訊號組。"""
    n_top = max(1, int(np.ceil(len(events) * TOP_DECILE)))
    signal_df = events.sort_values("surprise", ascending=False).iloc[:n_top]
    non_signal_df = events.sort_values("surprise", ascending=False).iloc[n_top:]
    active_buckets = set(signal_df["bucket_key"])
    control_df = non_signal_df[non_signal_df["bucket_key"].isin(active_buckets)]

    print(f"\n訊號組(SUE前10%) n={len(signal_df)}，surprise範圍=[{signal_df['surprise'].min():+.4f}, {signal_df['surprise'].max():+.4f}]")
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

    n_signal, n_control = len(signal_df), len(control_df)
    power_class = "VALID" if min(n_signal, n_control) >= DEGENERATE_N_FLOOR else "DEGENERATE"
    return {
        "n_signal": n_signal, "n_control": n_control, "n_events_total": len(events),
        "n_buckets_hit": len(active_buckets), "n_buckets_total": int(events["bucket_key"].nunique()),
        "power_class": power_class,
        "power_class_reason": f"min(n_signal={n_signal}, n_control={n_control}) "
                               f"{'>=' if power_class == 'VALID' else '<'} {DEGENERATE_N_FLOOR}",
        "by_horizon": results,
    }


def direction_summary(summary: dict) -> str:
    """跟`pead_calibration_gate.py::calibration_verdict`同一種方向性描述，
    但這裡**不下PASS/FAIL判定**（本檔案定位是原型，見模組說明），只誠實
    描述t+20方向是否一致，留給下一步（真正走GATE_SEQUENCE）判斷。
    """
    h20 = summary["by_horizon"].get(20)
    if h20 is None or h20["insufficient_n"]:
        return "t+20樣本不足，方向性無法判斷"
    drift_positive = h20["median_diff"] > 0
    fatter_right_tail = h20["right_tail_share_signal"] > h20["right_tail_share_control"]
    if drift_positive and fatter_right_tail:
        return (f"t+20 median_diff={h20['median_diff']:+.4f}>0 且 "
                f"right_tail_share訊號組({h20['right_tail_share_signal']:.3f})>對照組"
                f"({h20['right_tail_share_control']:.3f})——方向與PEAD文獻假說一致")
    return (f"t+20 median_diff={h20['median_diff']:+.4f}（{'正' if drift_positive else '非正'}）、"
            f"right_tail_share訊號組={h20['right_tail_share_signal']:.3f} vs 對照組={h20['right_tail_share_control']:.3f}"
            f"（{'訊號組較胖' if fatter_right_tail else '未較胖'}）——方向不一致或不明確")


def main() -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print("=== 事件驅動原型 (方法.三, E1財報公布/E2月營收公布, 分組依事件當下SUE) ===")
    print(f"Sample: {len(sample_ids)}檔 (SAMPLE_SEED={SAMPLE_SEED})，horizons={HORIZONS}")

    all_results = {}
    for event_name, spec in EVENT_TYPES.items():
        print(f"\n--- {event_name} ---")
        events = build_event_table(sample_ids, spec["surprise_fn"], spec["surprise_col"])
        if events.empty:
            print(f"{event_name}: 零事件，資料層級問題（不是市場沒訊號）")
            all_results[event_name] = {"n_events_total": 0, "power_class": "DEGENERATE",
                                        "power_class_reason": "零事件"}
            continue
        summary = run_event_study(events)
        summary["direction_summary"] = direction_summary(summary)
        print(f"\n{event_name} 方向性摘要：{summary['direction_summary']}")
        print(f"{event_name} power_class={summary['power_class']}（{summary['power_class_reason']}）")
        all_results[event_name] = summary

    return all_results


if __name__ == "__main__":
    import json
    out = main()
    out_path = Path(__file__).parent / "event_driven_prototype_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
