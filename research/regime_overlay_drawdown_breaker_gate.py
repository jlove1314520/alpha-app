"""regime overlay協定候選5——回撤斷路器＋absorbing state檢查，TRAIN期單次判定。

規格已在`REGIME_OVERLAY_PROTOCOL.md`第11節看結果前鎖定（X=15%,R=0.5,
tripped曝險0.50），本檔案只回報數字，不回頭調規格。重用trend_filter_gate
的metrics/capture/crisis/控制組(a)函式，不重新發明。
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from factor_ic import START_DATE
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from regime_overlay_trend_filter_gate import (
    COST_PER_UNIT_EXPOSURE_CHANGE as COST, metrics, capture_ratios,
    crisis_window_results, control_a_random_switch,
)

X_TRIGGER = 0.15
R_RELEASE = 0.5
TRIPPED_EXPOSURE = 0.50
MAX_SPELL_DAYS = 504
MAX_TRIPPED_FRAC = 0.50


def simulate(raw: np.ndarray, x: float = X_TRIGGER, r: float = R_RELEASE,
             tripped_exp: float = TRIPPED_EXPOSURE, lag: int = 0):
    """路徑依賴狀態機。狀態於收盤後決定，最早影響下一交易日(+lag)。
    回傳 (套用曝險, 淨報酬, 事件列表)。"""
    n = len(raw)
    state_hist = np.ones(n)
    applied = np.ones(n)
    ret = np.zeros(n)
    eq, peak, state = 1.0, 1.0, 1.0
    events, open_event = [], None
    prev_applied = 1.0
    for t in range(n):
        idx = t - 1 - lag
        a = state_hist[idx] if idx >= 0 else 1.0
        applied[t] = a
        ret[t] = raw[t] * a - abs(a - prev_applied) * COST
        prev_applied = a
        eq *= 1 + ret[t]
        peak = max(peak, eq)
        dd = eq / peak - 1
        if state == 1.0 and dd <= -x:
            state = tripped_exp
            open_event = {"trip_i": t, "trip_dd": dd * 100}
        elif state != 1.0 and dd >= -x * r:
            state = 1.0
            open_event.update({"release_i": t, "release_dd": dd * 100})
            events.append(open_event)
            open_event = None
        state_hist[t] = state
    if open_event is not None:
        events.append(open_event)  # 樣本結束仍未解除
    return applied, ret, events


def absorbing_check(events: list, applied: np.ndarray) -> dict:
    n = len(applied)
    spells = [e.get("release_i", n - 1) - e["trip_i"] for e in events]
    frac = float((applied < 1.0).mean())
    never_released = any("release_i" not in e for e in events)
    max_spell = max(spells) if spells else 0
    quasi = never_released or max_spell > MAX_SPELL_DAYS or frac > MAX_TRIPPED_FRAC
    return {"n_trips": len(events), "never_released": never_released, "max_spell_days": max_spell,
            "tripped_frac": frac, "quasi_absorbing": quasi}


def build_d(train_df: pd.DataFrame, x=X_TRIGGER, r=R_RELEASE, lag=0):
    d = train_df.sort_values("date").reset_index(drop=True).copy()
    d["raw_return"] = d["close"].pct_change()
    d = d[d["raw_return"].notna()].reset_index(drop=True)
    applied, ret, events = simulate(d["raw_return"].to_numpy(), x, r, lag=lag)
    d["exposure_lagged"] = applied
    d["overlay_return"] = ret
    d["switch_cost"] = np.abs(np.diff(applied, prepend=1.0)) * COST
    d["overlay_return_gross"] = d["raw_return"] * applied
    d["baseline_equity"] = (1 + d["raw_return"]).cumprod()
    d["overlay_equity"] = (1 + d["overlay_return"]).cumprod()
    return d, events


def mdd_reduction(d):
    b = metrics(d["baseline_equity"], d["raw_return"])
    o = metrics(d["overlay_equity"], d["overlay_return"])
    return b, o, (1 - o["mdd_pct"] / b["mdd_pct"]) * 100


def main():
    print("=" * 70)
    print("regime overlay候選5 回撤斷路器 TRAIN期單次判定 (規格見協定第11節)")
    print("=" * 70)
    raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(raw, context="regime_overlay_drawdown_breaker_gate")
    train_df = holdout.cap_to_train(prepare_market_data(raw))
    print(f"TRAIN期: {train_df['date'].min()} ~ {train_df['date'].max()}, n={len(train_df)}")

    d, events = build_d(train_df)
    b, o, red = mdd_reduction(d)
    up, down = capture_ratios(d["raw_return"], d["overlay_return"])
    print(f"\n基底: CAGR={b['cagr_pct']:+.2f}% MDD={b['mdd_pct']:.2f}% Sortino={b['sortino']:.2f} Calmar={b['calmar']:.2f}")
    print(f"斷路器(淨): CAGR={o['cagr_pct']:+.2f}% MDD={o['mdd_pct']:.2f}% Sortino={o['sortino']:.2f} Calmar={o['calmar']:.2f}")
    print(f"MDD縮小(淨)={red:.1f}% (門檻>=35%: {'PASS' if red >= 35 else 'FAIL'})")
    print(f"上檔捕捉率={up:.1f}% (門檻>=75%: {'PASS' if up >= 75 else 'FAIL'})  下檔捕捉率={down:.1f}%")

    print("\n--- absorbing state逐筆事件 ---")
    dates = d["date"].astype(str).to_numpy()
    for k, e in enumerate(events, 1):
        rel = e.get("release_i")
        end_i = rel if rel is not None else len(d) - 1
        seg = d["raw_return"].iloc[e["trip_i"] + 1:end_i + 1]
        base_ret = float((1 + seg).prod() - 1) * 100
        rel_txt = f"{dates[rel]}(dd={e['release_dd']:.1f}%)" if rel is not None else "未解除"
        print(f"  #{k} 觸發{dates[e['trip_i']]}(dd={e['trip_dd']:.1f}%) 解除{rel_txt} "
              f"持續{end_i - e['trip_i']}交易日 期間基底報酬={base_ret:+.1f}%")
    ab = absorbing_check(events, d["exposure_lagged"].to_numpy())
    print(f"  觸發{ab['n_trips']}次 未解除={ab['never_released']} 最長{ab['max_spell_days']}日 "
          f"TRIPPED占比={ab['tripped_frac']*100:.1f}% -> 準吸收態={'是(FAIL)' if ab['quasi_absorbing'] else '否'}")

    n_sw = int((np.abs(np.diff(d["exposure_lagged"], prepend=1.0)) > 1e-9).sum())
    yrs = len(d) / 252
    print(f"\n(c) 切換{n_sw}次 (每年{n_sw / yrs:.2f}次) 累計成本={d['switch_cost'].sum() * 100:.3f}%")

    print("\n--- 危機視窗(4個TRAIN可測) ---")
    n_imp = 0
    for r_ in crisis_window_results(d):
        if r_["improved"] is None:
            continue
        n_imp += int(r_["improved"])
        print(f"  {r_['window']}: 基底{r_['baseline_mdd_pct']:.1f}% overlay{r_['overlay_mdd_pct']:.1f}% "
              f"{'改善' if r_['improved'] else '未改善'}")
    print(f"  改善數 {n_imp}/4")

    ca = control_a_random_switch(d)
    print(f"\n(a) 隨機排列n=300: 真實改善={ca['real_mdd_improve_pct']:.2f}pp 隨機平均={ca['random_mean_improve_pct']:.2f}pp "
          f"百分位={ca['percentile']:.1f} ({'PASS' if ca['pass_gt_90'] else 'FAIL'})")

    d5, _ = build_d(train_df, lag=5)
    _, _, red5 = mdd_reduction(d5)
    print(f"(b) 延遲5日後MDD縮小={red5:.1f}% (延遲前{red:.1f}%)")

    print("\n(d) 參數高原 X x R (MDD縮小%, * = >=35%, Q=準吸收態)")
    n_pass, cells = 0, 0
    print("      R:   " + "  ".join(f"{r_:.3f}" for r_ in (0.35, 0.425, 0.5, 0.575, 0.65)))
    for x in (0.105, 0.1275, 0.15, 0.1725, 0.195):
        row = []
        for r_ in (0.35, 0.425, 0.5, 0.575, 0.65):
            dd_, ev = build_d(train_df, x=x, r=r_)
            _, _, rd = mdd_reduction(dd_)
            q = absorbing_check(ev, dd_["exposure_lagged"].to_numpy())["quasi_absorbing"]
            n_pass += int(rd >= 35)
            cells += 1
            row.append(f"{rd:5.1f}{'*' if rd >= 35 else ' '}{'Q' if q else ' '}")
        print(f"  X={x * 100:5.2f}%  " + " ".join(row))
    print(f"  25格中MDD縮小>=35%: {n_pass}/{cells}")

    print("\n結論:")
    print(f"  1.MDD縮小>=35%: {red:.1f}% -> {'PASS' if red >= 35 else 'FAIL'}")
    print(f"  2.上檔捕捉>=75%: {up:.1f}% -> {'PASS' if up >= 75 else 'FAIL'}")
    print(f"  3.危機視窗 {n_imp}/4 (換算待總司令裁示)")
    print(f"  4.控制組(a)百分位 {ca['percentile']:.1f}")
    print(f"  5.absorbing: {'準吸收態FAIL' if ab['quasi_absorbing'] else '通過'}")
    print(f"  6.參數高原 {n_pass}/25")
    print(f"  sharpe_for_registry={o['sharpe']:.4f} n={len(d)}")


if __name__ == "__main__":
    main()
