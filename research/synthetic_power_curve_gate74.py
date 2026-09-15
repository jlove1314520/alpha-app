"""HYPOTHESIS_QUEUE.md #74 閘門統計檢定力量測（synthetic power curve）。

**這不是一個新假設**——這是對GATE_SEQUENCE（1~6關）本身做元分析（meta-analysis）：
在真實歷史報酬序列上疊加一個事先設定Sharpe強度的人工訊號分量，量測六關各自
與合計的「真訊號通過率」（統計檢定力），回答「69個FAIL裡有沒有一部分是閘門
太嚴格誤殺，而不是市場真的有效率」。

**本輪範圍（一輪一個有界工作單位，2026-09-15 hypothesis_queue排程接續#74
待辦(a)(b)(c)）**：
(a) 已查證：GATE_SEQUENCE各關現況是**每個假設各自複製貼上一份bespoke實作**
    （見`validation/`目錄下~90支`*_gate*.py`），**沒有**單一可重複呼叫、
    餵任意報酬序列就能跑完整六關的通用函式。可重用的只有底層基礎元件：
    `validation/control_group.py::run_control_group()`（隨機控制組percentile
    計算，seam是`evaluate_fn`，天生通用）跟`validation/costs.py::
    round_trip_cost_pct()`（成本模型，純函式）。sanity/leave-one-out/逐年
    一致性/參數高原這幾關目前只存在於個別假設腳本裡（例如
    `equal_weight_rebalance_leave_one_out_v1.py`），跟該假設自己的panel/
    simulate()資料結構綁死，不是通用函式。
(b) 本檔案就是為此新寫的**通用注入+六關mini pipeline**，不依賴任何單一
    既有假設腳本的內部資料結構，只依賴真實股價panel（`equal_weight_rebalance_
    sanity.py::load_prices`/`build_panel`複用既有300檔快取，零新增API呼叫）。
(c) 本輪執行單一強度(Sharpe=0.5)單一種子的一次性試跑，驗證整條pipeline
    機制可行——**這是可行性驗證，不是正式檢定力數字**，下一輪才擴大到
    完整強度(0.3/0.5/0.8)×種子網格。

**注入方法（對應總司令原話「在真實歷史報酬序列上疊加一個事先設定Sharpe強度的
人工訊號分量」）**：
    combined_t = base_t + epsilon_t，epsilon_t ~ iid N(mu, sigma^2)
其中`sigma`取`base`日報酬序列的實際標準差（讓注入雜訊量級貼近真實市場日波動，
不是憑空假設一個數字），`mu = target_sharpe * sigma / sqrt(252)`——這樣
`epsilon_t`這個分量本身的**母體**年化Sharpe恰好等於`target_sharpe`（樣本
Sharpe會因為N有限而圍繞這個母體值抖動，這正是我們要量測的「檢定力」：母體
真的有一個Sharpe=S的訊號，六關能不能穩定抓到）。

**GATE 2隨機控制組的null定義（本檔案特有，需要說明理由）**：
既有假設腳本的隨機控制組null是「同樣動作、隨機挑選標的」（見
`control_group.py`模組docstring），因為那些假設測的是「選股」。本檔案測的
不是選股，是「這段報酬序列裡有沒有一個外加的Sharpe=S訊號」，所以對應的null
是「同樣雜訊量級(sigma相同)、但mu=0（沒有注入alpha）」——這是**同一個統計
問題**換了一種操作化：既有假設是「隨機挑標的vs.訊號挑標的」，本檔案是
「隨機（無alpha）雜訊vs.有alpha雜訊」，兩者的共同精神都是「拿掉被測的那個
判斷依據後，機制自然會做的事」（CLAUDE.md控制組定義），未違反既有紀律。

is_holdout_consumed()本輪開工/收工前皆確認False。全程僅讀取本機既有快取
（`equal_weight_rebalance_sanity.load_prices`複用的300檔快照csv），零新增
外部API呼叫。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from equal_weight_rebalance_sanity import REBAL_FREQ, build_panel, load_prices
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from validation import costs, holdout

TRADING_DAYS_PER_YEAR = 252


def annualized_sharpe(daily_ret: pd.Series) -> float:
    mu, sigma = daily_ret.mean(), daily_ret.std(ddof=1)
    if sigma == 0 or np.isnan(sigma):
        return float("nan")
    return float(mu / sigma * np.sqrt(TRADING_DAYS_PER_YEAR))


def yearly_total_returns(ret_series: pd.Series) -> dict[int, float]:
    out = {}
    for y in sorted(ret_series.index.year.unique()):
        sub = ret_series[ret_series.index.year == y]
        if not sub.empty:
            out[int(y)] = float((1 + sub).prod() - 1)
    return out


def compounded(yearly: dict[int, float], exclude_year: int | None = None) -> float:
    total = 1.0
    for y, v in yearly.items():
        if y != exclude_year:
            total *= (1 + v)
    return total - 1


def inject_synthetic_alpha(base: pd.Series, target_sharpe: float, seed: int) -> pd.Series:
    """combined_t = base_t + epsilon_t, epsilon_t~iid N(mu,sigma^2)，
    sigma取base序列實際標準差，mu校準使epsilon_t母體年化Sharpe=target_sharpe。"""
    rng = np.random.default_rng(seed)
    sigma = float(base.std(ddof=1))
    mu = target_sharpe * sigma / np.sqrt(TRADING_DAYS_PER_YEAR)
    epsilon = rng.normal(loc=mu, scale=sigma, size=len(base))
    return base + pd.Series(epsilon, index=base.index)


def gate1_sanity(combined: pd.Series) -> dict:
    n_nan = int(combined.isna().sum())
    finite = bool(np.isfinite(combined.dropna()).all())
    passed = (n_nan == 0) and finite and (len(combined) > 100)
    return {"gate": 1, "name": "sanity", "n_nan": n_nan, "finite": finite,
            "n_obs": len(combined), "passed": passed}


def gate2_random_control(base: pd.Series, combined: pd.Series, target_sharpe: float,
                          n_random: int, seed: int) -> dict:
    """null=同樣sigma、mu=0（無alpha）的隨機抽樣；candidate=combined的年化Sharpe。"""
    rng = np.random.default_rng(seed + 1)
    sigma = float(base.std(ddof=1))
    candidate_metric = annualized_sharpe(combined)
    null_metrics = []
    for _ in range(n_random):
        epsilon_null = rng.normal(loc=0.0, scale=sigma, size=len(base))
        null_combined = base + pd.Series(epsilon_null, index=base.index)
        null_metrics.append(annualized_sharpe(null_combined))
    beats = sum(1 for m in null_metrics if candidate_metric > m)
    percentile = 100.0 * beats / len(null_metrics)
    return {"gate": 2, "name": "random_control", "candidate_sharpe": candidate_metric,
            "null_median": float(np.median(null_metrics)), "n_random": n_random,
            "percentile": percentile, "passed": percentile >= 90.0}


def gate3_seed_plateau(base: pd.Series, target_sharpe: float, n_seeds: int,
                        n_random_per_seed: int, base_seed: int) -> dict:
    """同一強度、多個獨立種子重複整個注入+GATE2流程，量測通過率（非傳統參數高原，
    是本檔案對應『重複多次取得穩定通過率估計』的操作化，見模組docstring）。"""
    results = []
    for i in range(n_seeds):
        seed = base_seed + 100 * (i + 1)
        combined = inject_synthetic_alpha(base, target_sharpe, seed)
        g2 = gate2_random_control(base, combined, target_sharpe, n_random_per_seed, seed)
        results.append(g2["passed"])
    pass_rate = sum(results) / len(results) if results else float("nan")
    return {"gate": 3, "name": "seed_plateau", "n_seeds": n_seeds,
            "pass_rate": pass_rate, "passed": pass_rate >= 0.6}


def gate4_cost_sensitivity(combined: pd.Series) -> dict:
    """假設REBAL_FREQ天換手一次（比照equal_weight_rebalance慣例），逐日報酬扣除
    攤提到每日的來回成本，在1x/2x/3x情境下檢查年化總報酬是否仍為正。"""
    results = {}
    for mult, label in ((1, "1x"), (2, "2x"), (3, "3x")):
        rt_cost = costs.round_trip_cost_pct(slippage_bps=costs.DEFAULT_SLIPPAGE_BPS * mult)
        daily_cost = rt_cost / REBAL_FREQ
        net = combined - daily_cost
        total_return = float((1 + net).prod() - 1)
        results[label] = {"daily_cost": daily_cost, "total_return": total_return,
                           "positive": total_return > 0}
    passed = all(v["positive"] for v in results.values())
    return {"gate": 4, "name": "cost_sensitivity", "scenarios": results, "passed": passed}


def gate5_leave_one_out(combined: pd.Series) -> dict:
    yearly = yearly_total_returns(combined)
    if not yearly:
        return {"gate": 5, "name": "leave_one_out", "passed": False, "note": "無年度資料"}
    full_total = compounded(yearly)
    max_year = max(yearly, key=lambda y: yearly[y])
    loo_total = compounded(yearly, exclude_year=max_year)
    return {"gate": 5, "name": "leave_one_out", "full_total": full_total,
            "max_year": max_year, "max_year_contribution": yearly[max_year],
            "loo_total": loo_total, "passed": loo_total > 0}


def gate6_yearly_consistency(combined: pd.Series) -> dict:
    yearly = yearly_total_returns(combined)
    n_years = len(yearly)
    n_positive = sum(1 for v in yearly.values() if v > 0)
    ratio = n_positive / n_years if n_years else float("nan")
    return {"gate": 6, "name": "yearly_consistency", "n_years": n_years,
            "n_positive": n_positive, "ratio": ratio, "passed": ratio >= (5 / 6)}


def run_pilot(target_sharpe: float, seed: int, n_random: int = 100) -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    prices = load_prices(sample_ids)
    panel = build_panel(prices)
    if panel.shape[1] < 30:
        raise RuntimeError(f"panel只有{panel.shape[1]}檔，過少無法可靠測試")

    base_raw = panel.pct_change().mean(axis=1).dropna()
    base_raw = holdout.train_val_only(base_raw.to_frame("ret"))["ret"] \
        if hasattr(holdout, "train_val_only") else base_raw[base_raw.index <= pd.Timestamp(holdout.VAL_END)]
    print(f"base_raw(等權重日報酬,TRAIN+VAL)：{len(base_raw)}筆，"
          f"{base_raw.index[0].date()}..{base_raw.index[-1].date()}，"
          f"母體Sharpe(去均值化前)={annualized_sharpe(base_raw):.4f}")

    # 去均值化修正（2026-09-15上一輪發現：base_raw自己Sharpe=1.1057，疑似
    # 存活者偏誤⑦造成人為膨脹，遠大於注入的目標強度，導致GATE2判定幾乎完全
    # 由base_raw自己的既有優勢決定，不是被注入的epsilon分量）。只減去均值，
    # 保留真實的波動/自相關/厚尾結構，讓epsilon成為母體Sharpe的唯一來源，
    # 忠實操作化「在真實報酬序列上疊加一個Sharpe=S的訊號」。
    base = base_raw - base_raw.mean()
    print(f"base(去均值化後，用於注入)：母體Sharpe={annualized_sharpe(base):.4f}"
          f"（應接近0，殘留非零純屬樣本抖動，非母體效應）")

    combined = inject_synthetic_alpha(base, target_sharpe, seed)
    print(f"注入後combined年化樣本Sharpe={annualized_sharpe(combined):.4f}"
          f"（目標母體Sharpe={target_sharpe}，樣本值會圍繞目標值抖動，非恆等）")

    g1 = gate1_sanity(combined)
    g2 = gate2_random_control(base, combined, target_sharpe, n_random, seed)
    g3 = gate3_seed_plateau(base, target_sharpe, n_seeds=5, n_random_per_seed=30, base_seed=seed)
    g4 = gate4_cost_sensitivity(combined)
    g5 = gate5_leave_one_out(combined)
    g6 = gate6_yearly_consistency(combined)

    gates = [g1, g2, g3, g4, g5, g6]
    for g in gates:
        print(f"  GATE{g['gate']} {g['name']}: {'PASS' if g['passed'] else 'FAIL'} | {g}")

    all_passed = all(g["passed"] for g in gates)
    print(f"\n=== 單次試跑(Sharpe={target_sharpe}, seed={seed}) 六關綜合：",
          "全PASS" if all_passed else "至少一關FAIL", "===")
    return {
        "target_sharpe": target_sharpe, "seed": seed, "gates": gates, "all_passed": all_passed,
        "base_raw_sharpe": annualized_sharpe(base_raw),
        "base_demeaned_sharpe": annualized_sharpe(base),
        "demean_applied": True,
    }


if __name__ == "__main__":
    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

    result = run_pilot(target_sharpe=0.5, seed=20260915)

    import json
    out_path = Path(__file__).parent / "data" / "synthetic_power_curve_gate74_pilot.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n試跑結果已存 {out_path.relative_to(Path(__file__).parent)}（gitignored，僅供除錯）")

    print(f"\nis_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"
