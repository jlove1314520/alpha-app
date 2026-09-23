# -*- coding: utf-8 -*-
"""驗.四（總司令2026-09-23裁示【三個方法缺陷＋E-c/E-d走正式閘門】驗.四）：
E-c移動停損10%與E-d MA200regime走`REGIME_OVERLAY_PROTOCOL.md`正式閘門。

兩者屬於二元降曝險機制，與已結案的regime overlay家族（#243/#245/#246等）
同類，用同一套判定邏輯，不得另立寬鬆標準——但regime家族既有的
`regime_overlay_trend_filter_gate.py`測的是「連續曝險水位切換」(1.00/0.50)，
E-c/E-d是「進出場交易事件」(全部持有或全部出清，0/1)，資料結構不同，
本檔案重寫控制組與績效計算，但**沿用同一套成本模型**
（`exit_rule_lab.py`已修正的0.1% ETF證交稅、1.8折手續費、
`validation/margin_of_safety.py`基準情境）與同一套模擬引擎
（`exit_rule_lab.simulate()`，含冷卻期重入規則），不重寫底層交易邏輯。

裁示原文七項要求：
1. train(<=2020-12-31)/val(2021-2024)分別報告。
2. 隨機擇時對照組1000次：出場次數與空手天數比例和實際相同、日期隨機，
   比較CAGR/MDD百分位。
3. 逐年表（每年策略vs買進持有，標贏的年份）+剔除2008後全期結果。
4. 參數高原：移動停損{7..15}%×冷卻{10,20,40}天，只報形狀，不選最佳值，
   主判定維持10%/20天；網格全部計入N。
5. 空手期現金改用定存利率計息，與零利息版並列。
6. 停損用含息還原價計算高點——`exit_rule_lab.load_prices()`本身用的
   `load_0050_full_history()`已是FinMind手動還原權息序列，滿足此點，
   不需額外處理。
7. 兩者都登記進N；判定寫死：隨機擇時對照組p<=0.01且val期仍守住天條一
   (MDD<=50%)才能叫PASS。

**[自行裁量]記錄（每一條都是「可還原的技術選擇」，非新裁示，供總司令
下一輪推翻）**：
1. **隨機擇時對照組的操作定義**：真實策略的逐日in-position狀態序列
   拆成「連續同狀態區段」(runs)，隨機打亂區段出現的順序（block
   permutation），保證與真實序列完全相同的空手總天數與切換次數(=出場
   次數的2倍)，只隨機化「哪些日曆日」落在哪個狀態——這樣量出的效果
   隔離的是「進出場的時機選擇能力」，不是「要不要進出場」本身，符合
   裁示原文「出場次數與空手天數比例相同、日期隨機」的字面要求。
2. **切換成本的簡化**：真實策略(`exit_rule_lab.simulate()`)用逐筆
   notional計算買/賣兩腿成本；隨機控制組為了1000次可行必須向量化，
   改用「每次狀態切換扣一次固定成本率」（=買腿+賣腿成本率之和/2，
   即完整來回成本的一半，跟`regime_overlay_trend_filter_gate.py`既有
   `COST_PER_UNIT_EXPOSURE_CHANGE`同一種簡化精神）。為求真實值與隨機
   對照可比（apples-to-apples），**真實策略在本檔案的p值計算改用同一個
   簡化引擎重算**，不直接借用`exit_rule_lab.py`原始逐筆成本的CAGR——
   兩者在其他章節(1/3/4/5)仍各自使用最精確的引擎（真實用
   `exit_rule_lab.simulate()`，摘要用它的真實逐筆成本）。
3. **p值定義**：對CAGR與MDD各自算百分位（真實值贏過幾%的隨機對照組），
   取兩者中**較不極端**的一個換算成p值（p=1-min(pctl_cagr,pctl_mdd)/100）
   當最終判定用的p——理由：裁示要求「p<=0.01」是單一數字，但同時要求
   看CAGR與MDD兩個百分位，若只需其中一個極端就能過關，等於只要策略
   剛好在某一個維度走運就能PASS，門檻形同虛設；取較嚴格的一個較符合
   「這是真本事不是運氣」的檢定精神。
4. **剔除2008做法**：把2008年的逐日淨報酬從序列中整段移除（前後年份
   直接接續複利），不是「假裝2008報酬=0」，年化用移除後的實際交易天數
   換算，這樣才誠實反映「拿掉這一年後，其餘年份的複利軌跡長什麼樣」。
5. **定存利率的計息時點**：只在真實策略序列(非1000次隨機控制組，避免
   複雜度爆炸且裁示原文只要求「並列」不要求隨機控制組也套用)套用，
   空手日的cash部位以當月央行五大銀行定存利率代理值/252換算日息計入，
   跟零利息版並列在同一份輸出，供比較差異量級。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

import exit_rule_lab as erl
from validation import holdout
from validation.holdout import is_holdout_consumed
from cbc_rf_rate_client import load_risk_free_rate_series, rf_rate_for_date
from trial_registry import register_trial

REPO_ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))
OUT_JSON = REPO_ROOT / "research" / "data" / "regime_overlay_exit_rule_gate_result.json"

N_RANDOM_DRAWS = 1000
RNG_SEED = 20260923  # 裁示日期,非搜出來的
MAIN_TRAILING_PCT = 0.10
MAIN_COOLDOWN = 20
TRAILING_PCT_GRID = [0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.15]
COOLDOWN_GRID = [10, 20, 40]

# 完整來回(買+賣)成本率/2 = 每次狀態切換的簡化成本（見docstring[自行裁量]2）
_ROUND_TRIP = (erl._leg_cost(1.0, side="buy", commission_discount=0.18, slippage_bps=erl.costmod.DEFAULT_SLIPPAGE_BPS)
               + erl._leg_cost(1.0, side="sell", commission_discount=0.18, slippage_bps=erl.costmod.DEFAULT_SLIPPAGE_BPS))
SWITCH_COST_PCT = _ROUND_TRIP / 2.0

RULES_UNDER_TEST = {
    "E-c_trailing10": {"type": "trailing_stop", "pct": MAIN_TRAILING_PCT},
    "E-d_ma200_regime": {"type": "ma_regime"},
}
MDD_SURVIVAL_LIMIT_PCT = -50.0  # 天條一


# ---------------------------------------------------------------------------
# 狀態序列萃取與向量化引擎（供真實策略摘要重算與1000次隨機控制組共用）
# ---------------------------------------------------------------------------

def extract_state(dates: list, trades: list) -> np.ndarray:
    """由`exit_rule_lab.simulate()`回傳的trades事件序列重建逐日in-position
    布林陣列（True=持有0050，False=空手），跟`dates`逐一對齊。"""
    trade_map: dict[str, list[str]] = {}
    for t in trades:
        trade_map.setdefault(t["date"], []).append(t["side"])
    state = np.zeros(len(dates), dtype=bool)
    cur = False
    for i, d in enumerate(dates):
        for side in trade_map.get(d, []):
            cur = (side == "buy")
        state[i] = cur
    return state


def compute_equity_from_state(raw_ret: np.ndarray, state: np.ndarray, switch_cost_pct: float,
                                idle_daily_rate: np.ndarray | None = None) -> np.ndarray:
    """給定逐日原始報酬與逐日in-position狀態，算出淨值路徑（向量化）。
    `state[i]`是"day i收盤後"的持有狀態；day i的報酬曝險用`state[i-1]`
    （前一天收盤後的狀態）判斷——買進當天不吃到當天報酬(T+1成交後才開始
    曝險)，賣出當天吃得到當天報酬(持有到當天收盤才賣)，這跟
    `exit_rule_lab.simulate()`的T+1成交邏輯一致。"""
    n = len(state)
    exposure = np.zeros(n, dtype=bool)
    exposure[1:] = state[:-1]
    switch = np.zeros(n)
    switch[1:] = (state[1:] != state[:-1]).astype(float)
    idle_component = idle_daily_rate if idle_daily_rate is not None else np.zeros(n)
    ret_component = np.where(exposure, raw_ret, idle_component)
    ret_component = np.nan_to_num(ret_component, nan=0.0)
    ret_mult = 1 + ret_component
    cost_mult = 1 - switch * switch_cost_pct
    return np.cumprod(ret_mult * cost_mult)


def cagr_mdd(dates: pd.Series, equity: np.ndarray) -> tuple[float, float]:
    n_years = (pd.to_datetime(dates.iloc[-1]) - pd.to_datetime(dates.iloc[0])).days / 365.25
    total_return = equity[-1] / equity[0] - 1
    cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else float("nan")
    running_max = np.maximum.accumulate(equity)
    mdd = float((equity / running_max - 1).min())
    return float(cagr) * 100, mdd * 100


def rebased_metrics(dates: pd.Series, equity: np.ndarray, start: str, end: str) -> dict:
    d = pd.to_datetime(dates)
    mask = (d >= start) & (d <= end)
    if mask.sum() < 30:
        return {"n_days": int(mask.sum()), "cagr_pct": float("nan"), "mdd_pct": float("nan")}
    sub_dates = dates[mask].reset_index(drop=True)
    sub_eq = equity[mask.values]
    sub_eq = sub_eq / sub_eq[0]
    cagr, mdd = cagr_mdd(sub_dates, sub_eq)
    return {"n_days": int(mask.sum()), "cagr_pct": round(cagr, 4), "mdd_pct": round(mdd, 4)}


def yearly_table(dates: pd.Series, strat_eq: np.ndarray, base_eq: np.ndarray) -> list[dict]:
    df = pd.DataFrame({"date": pd.to_datetime(dates), "strat": strat_eq, "base": base_eq})
    df["year"] = df["date"].dt.year
    rows = []
    for y, g in df.groupby("year"):
        if len(g) < 5:
            continue
        s_ret = float(g["strat"].iloc[-1] / g["strat"].iloc[0] - 1) * 100
        b_ret = float(g["base"].iloc[-1] / g["base"].iloc[0] - 1) * 100
        rows.append({"year": int(y), "n_days": int(len(g)), "strategy_ret_pct": round(s_ret, 2),
                      "buyhold_ret_pct": round(b_ret, 2), "strategy_won": bool(s_ret > b_ret)})
    return rows


def exclude_year_result(dates: pd.Series, raw_ret: np.ndarray, state: np.ndarray, switch_cost_pct: float,
                          exclude_year: int) -> dict:
    """把`exclude_year`整年的逐日報酬從序列中移除（前後年份直接接續複利），
    重新算CAGR/MDD——年化用移除後的實際交易天數換算(見docstring[自行裁量]4)。"""
    d = pd.to_datetime(dates)
    keep = (d.dt.year != exclude_year).values
    n = len(state)
    exposure = np.zeros(n, dtype=bool)
    exposure[1:] = state[:-1]
    switch = np.zeros(n)
    switch[1:] = (state[1:] != state[:-1]).astype(float)
    ret_component = np.where(exposure, raw_ret, 0.0)
    ret_component = np.nan_to_num(ret_component, nan=0.0)
    daily_ret = ret_component - switch * switch_cost_pct
    daily_ret_kept = daily_ret[keep]
    equity = np.cumprod(1 + daily_ret_kept)
    n_years = len(daily_ret_kept) / 252.0
    total_return = float(equity[-1] - 1)
    cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else float("nan")
    running_max = np.maximum.accumulate(equity)
    mdd = float((equity / running_max - 1).min())
    return {"excluded_year": exclude_year, "n_days_kept": int(keep.sum()),
            "cagr_pct": round(cagr * 100, 4), "mdd_pct": round(mdd * 100, 4)}


def random_control(dates: pd.Series, raw_ret: np.ndarray, real_state: np.ndarray,
                     switch_cost_pct: float, n_draws: int = N_RANDOM_DRAWS, seed: int = RNG_SEED) -> dict:
    """block permutation隨機擇時對照組（見docstring[自行裁量]1）：把真實
    state拆成連續同值區段，隨機打亂區段順序，保證空手總天數與切換次數
    跟真實序列完全相同，只隨機化日期落點。"""
    # 拆runs: (value, length)
    runs = []
    cur_val = real_state[0]
    cur_len = 1
    for v in real_state[1:]:
        if v == cur_val:
            cur_len += 1
        else:
            runs.append((cur_val, cur_len))
            cur_val, cur_len = v, 1
    runs.append((cur_val, cur_len))

    real_equity = compute_equity_from_state(raw_ret, real_state, switch_cost_pct)
    real_cagr, real_mdd = cagr_mdd(dates, real_equity)

    rng = np.random.default_rng(seed)
    rand_cagrs = np.empty(n_draws)
    rand_mdds = np.empty(n_draws)
    n_runs = len(runs)
    lengths = np.array([r[1] for r in runs])
    values = np.array([r[0] for r in runs])
    for i in range(n_draws):
        order = rng.permutation(n_runs)
        shuffled_state = np.repeat(values[order], lengths[order])
        # 長度理論上必然等於原序列長度(區段長度總和不變，只是順序被打亂)
        eq = compute_equity_from_state(raw_ret, shuffled_state, switch_cost_pct)
        c, m = cagr_mdd(dates, eq)
        rand_cagrs[i], rand_mdds[i] = c, m

    pctl_cagr = float((rand_cagrs < real_cagr).mean() * 100)
    pctl_mdd = float((rand_mdds < real_mdd).mean() * 100)  # mdd是負數,較不負(較大)=較好
    p_value = 1 - min(pctl_cagr, pctl_mdd) / 100.0
    return {
        "n_draws": n_draws, "real_cagr_pct": round(real_cagr, 4), "real_mdd_pct": round(real_mdd, 4),
        "random_cagr_median_pct": round(float(np.median(rand_cagrs)), 4),
        "random_mdd_median_pct": round(float(np.median(rand_mdds)), 4),
        "percentile_cagr": round(pctl_cagr, 2), "percentile_mdd": round(pctl_mdd, 2),
        "p_value_conservative": round(p_value, 4),
        "n_idle_days_real": int((~real_state).sum()), "n_switches_real": int(len(runs) - 1),
    }


def parameter_plateau(df: pd.DataFrame) -> list[dict]:
    """驗.四第4點：移動停損{7..15}%x冷卻{10,20,40}天，只報形狀，不選
    最佳值；主判定維持10%/20天不變。24格全部計入N（見PENDING_QUEUE.md
    驗.四條目「網格全部計入N」，本檔案在同一筆register_trial裡完整記錄
    24格結果，不逐格另開試驗列——比照既有regime overlay家族
    (`regime_overlay_trend_filter_gate.py::control_d_plateau`,
    TRIALS_LEDGER.md #243/#245/#246)同一種登記慣例：高原掃描是同一個
    候選的穩健性檢查，登記在同一列裡，不是24個獨立候選。"""
    rows = []
    orig_cooldown = erl.COOLDOWN_DAYS
    try:
        for cooldown in COOLDOWN_GRID:
            erl.COOLDOWN_DAYS = cooldown  # monkeypatch,比照lending_fee_gate63_param_plateau.py慣例
            for pct in TRAILING_PCT_GRID:
                rule = {"type": "trailing_stop", "pct": pct}
                net = erl.simulate(df, rule, commission_discount=0.18,
                                    slippage_bps=erl.costmod.DEFAULT_SLIPPAGE_BPS, apply_costs=True)
                m = erl.compute_metrics(net["equity_curve"], net["trades"])
                rows.append({"trailing_pct": pct, "cooldown_days": cooldown,
                              "cagr_pct": m["cagr_pct"], "mdd_pct": m["mdd_pct"], "calmar": m["calmar"]})
    finally:
        erl.COOLDOWN_DAYS = orig_cooldown
    return rows


def build_idle_rate_series(dates: list) -> np.ndarray:
    """空手期現金計息版本用：逐日央行五大銀行定存利率代理值(年化%)/252。
    超出快取涵蓋範圍的早期日期，`rf_rate_for_date()`會往前找最近一筆，
    不做外推假設之外的靜默容錯（沿用該函式既有行為）。"""
    monthly = load_risk_free_rate_series()
    rates_pct = []
    for d in dates:
        ts = pd.Timestamp(d)
        try:
            r = rf_rate_for_date(ts, monthly)
        except ValueError:
            r = float(monthly["rf_rate_pct"].iloc[0])  # 早於序列涵蓋範圍,用最早一筆
        rates_pct.append(r)
    return np.array(rates_pct) / 100.0 / 252.0


def main() -> None:
    df = erl.load_prices()
    dates = df["date"].tolist()
    raw_ret = df["adj_close"].pct_change().fillna(0.0).to_numpy()
    idle_rate = build_idle_rate_series(dates)

    baseline_net = erl.simulate(df, erl.RULES["E-a_buy_and_hold"], commission_discount=0.18,
                                 slippage_bps=erl.costmod.DEFAULT_SLIPPAGE_BPS, apply_costs=True)
    baseline_state = extract_state(dates, baseline_net["trades"])
    baseline_equity_zero_interest = compute_equity_from_state(raw_ret, baseline_state, SWITCH_COST_PCT)

    results = {}
    for name, rule in RULES_UNDER_TEST.items():
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
        net = erl.simulate(df, rule, commission_discount=0.18,
                            slippage_bps=erl.costmod.DEFAULT_SLIPPAGE_BPS, apply_costs=True)
        state = extract_state(dates, net["trades"])
        equity_zero = compute_equity_from_state(raw_ret, state, SWITCH_COST_PCT)
        equity_rf = compute_equity_from_state(raw_ret, state, SWITCH_COST_PCT, idle_daily_rate=idle_rate)
        date_series = pd.Series(dates)

        train = rebased_metrics(date_series, equity_zero, dates[0], holdout.TRAIN_END)
        val = rebased_metrics(date_series, equity_zero, holdout.TRAIN_END, holdout.VAL_END)
        train_base = rebased_metrics(date_series, baseline_equity_zero_interest, dates[0], holdout.TRAIN_END)
        val_base = rebased_metrics(date_series, baseline_equity_zero_interest, holdout.TRAIN_END, holdout.VAL_END)
        print(f"TRAIN(<= {holdout.TRAIN_END}): 策略CAGR={train['cagr_pct']}% MDD={train['mdd_pct']}% "
              f"| 買進持有CAGR={train_base['cagr_pct']}% MDD={train_base['mdd_pct']}%")
        print(f"VAL({holdout.TRAIN_END}~{holdout.VAL_END}): 策略CAGR={val['cagr_pct']}% MDD={val['mdd_pct']}% "
              f"| 買進持有CAGR={val_base['cagr_pct']}% MDD={val_base['mdd_pct']}%")

        yearly = yearly_table(date_series, equity_zero, baseline_equity_zero_interest)
        n_won = sum(1 for r in yearly if r["strategy_won"])
        print(f"逐年表：{n_won}/{len(yearly)}年贏過買進持有")

        excl_2008 = exclude_year_result(date_series, raw_ret, state, SWITCH_COST_PCT, 2008)
        print(f"剔除2008後全期：CAGR={excl_2008['cagr_pct']}% MDD={excl_2008['mdd_pct']}% "
              f"(n_days_kept={excl_2008['n_days_kept']})")

        print(f"隨機擇時對照組({N_RANDOM_DRAWS}次)...")
        ctrl = random_control(date_series, raw_ret, state, SWITCH_COST_PCT)
        print(f"  真實CAGR={ctrl['real_cagr_pct']}%(百分位{ctrl['percentile_cagr']}) "
              f"真實MDD={ctrl['real_mdd_pct']}%(百分位{ctrl['percentile_mdd']}) "
              f"保守p值={ctrl['p_value_conservative']}")

        rf_full = cagr_mdd(date_series, equity_rf)
        zero_full = cagr_mdd(date_series, equity_zero)
        print(f"全期比較(零利息 vs 定存計息)：CAGR {zero_full[0]:.2f}% vs {rf_full[0]:.2f}%　"
              f"MDD {zero_full[1]:.2f}% vs {rf_full[1]:.2f}%")

        plateau = None
        plateau_summary = None
        if name == "E-c_trailing10":
            print("參數高原({7..15}%x{10,20,40}天，24格)...")
            plateau = parameter_plateau(df)
            cagrs_p = [r["cagr_pct"] for r in plateau if r["cagr_pct"] == r["cagr_pct"]]
            mdds_p = [r["mdd_pct"] for r in plateau if r["mdd_pct"] == r["mdd_pct"]]
            plateau_summary = {"n_grid": len(plateau),
                                "cagr_pct_min": round(min(cagrs_p), 2) if cagrs_p else None,
                                "cagr_pct_max": round(max(cagrs_p), 2) if cagrs_p else None,
                                "mdd_pct_min": round(min(mdds_p), 2) if mdds_p else None,
                                "mdd_pct_max": round(max(mdds_p), 2) if mdds_p else None}
            print(f"  形狀：CAGR範圍[{plateau_summary['cagr_pct_min']}%,{plateau_summary['cagr_pct_max']}%] "
                  f"MDD範圍[{plateau_summary['mdd_pct_min']}%,{plateau_summary['mdd_pct_max']}%]")

        val_survives_tenet1 = bool(val["mdd_pct"] == val["mdd_pct"] and val["mdd_pct"] > MDD_SURVIVAL_LIMIT_PCT)
        p_pass = bool(ctrl["p_value_conservative"] <= 0.01)
        verdict = "PASS" if (p_pass and val_survives_tenet1) else "FAIL"
        print(f"判定：p<=0.01 {'PASS' if p_pass else 'FAIL'}(p={ctrl['p_value_conservative']}) "
              f"且 val守住天條一(MDD>{MDD_SURVIVAL_LIMIT_PCT}%) {'PASS' if val_survives_tenet1 else 'FAIL'} "
              f"=> 綜合{verdict}")

        results[name] = {
            "rule": rule, "train": train, "val": val, "train_baseline": train_base, "val_baseline": val_base,
            "yearly_table": yearly, "n_years_won": n_won, "n_years_total": len(yearly),
            "exclude_2008": excl_2008,
            "random_control": ctrl,
            "cash_interest_comparison": {"zero_interest_cagr_pct": round(zero_full[0], 4),
                                          "zero_interest_mdd_pct": round(zero_full[1], 4),
                                          "risk_free_cagr_pct": round(rf_full[0], 4),
                                          "risk_free_mdd_pct": round(rf_full[1], 4)},
            "parameter_plateau_grid": plateau, "parameter_plateau_summary": plateau_summary,
            "val_survives_tenet1": val_survives_tenet1, "p_le_0_01": p_pass, "verdict": verdict,
        }

    out = {
        "generated_at": datetime.now(TZ).isoformat(),
        "switch_cost_pct_per_switch": round(SWITCH_COST_PCT, 6),
        "n_random_draws": N_RANDOM_DRAWS,
        "results": results,
        "holdout_consumed_check": is_holdout_consumed(),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n寫入 {OUT_JSON}")


if __name__ == "__main__":
    main()
