# -*- coding: utf-8 -*-
"""右尾判定標準工具（`PENDING_QUEUE.md`方法.二，2026-09-22互動視窗CC建置）。

背景：既有cheap gate/GATE_SEQUENCE系列量的是「平均訊號」（mean IC、mean
report），對本專案七之三節「指標順序：淨利+MDD→Sortino→Sharpe放最後」與
「報酬高度集中在少數交易是動量策略的常態」這兩條既有紀律而言，只看均值
會錯過「少數怪獸單交易撐起整體績效」這種右尾主導的訊號形狀（也會錯過
「少數怪獸虧損拖垮整體」這種左尾風險）。`tail_test()`是給事件型/右尾型
假說（方法.三事件驅動原型的前置工具）用的獨立統計介面，不取代既有
`factor_ic.py::evaluate_factor()`的橫斷面IC框架，是另一把尺。

**本檔案只提供通用統計函式，不含任何資料抓取邏輯**——呼叫端（例如
`pead_calibration_gate.py`）負責準備signal_returns／control_returns
（比對組已經是「同時間窗/同產業/同市值分位、未觸發訊號個股」PIT對齊
配好的資料），`tail_test()`本身對輸入的配對過程零假設、零信任，只做
純統計計算，符合CONSTITUTION.md「工程紀律」一節「稽核恆等式兩端必須是
呼叫端已知的數字，不准重播引擎」同一種切分精神。
"""
from __future__ import annotations

import sys

import numpy as np

from validation.costs import round_trip_cost_pct

# Windows主控台cp950編不出中文print()裡的內容時不得讓行程崩潰
# （`CLAUDE.md`十二節「守門員自己的失敗只能降級成警告」同一套修法）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

N_BOOTSTRAP = 10000  # 裁示原文「各bootstrap 10000次」
RIGHT_TAIL_THRESHOLD = 0.20   # >+20% 視為右尾（怪獸單）
LEFT_TAIL_THRESHOLD = -0.20   # <-20% 視為左尾（地雷單）
P_TAIL = 90  # "P90差異"裁示原文指定的分位數

# 總司令2026-09-19查證過的實際手續費折數（見`core_tilt_backtest.py::
# COMMISSION_DISCOUNT`同一個數字、同一個查證來源，`成本.一`更正後的1.8折），
# 不重新發明一個新的折數假設。
COMMISSION_DISCOUNT = 0.18

# 「依持有期選當沖/一般稅率」——horizon以交易日計；<=1個交易日視為現股當沖
# （`validation/costs.py::SECURITIES_TX_TAX_DAYTRADE`半稅），其餘一律用一般
# 稅率（`SECURITIES_TX_TAX_NORMAL`）。這是保守二分法：現股當沖的法定定義是
# 「同日沖銷」，horizon<=1天是唯一可能符合這個定義的情況，horizon>=2天
# 不可能是當沖，一律用一般稅率，不做更細的分類猜測。
DAYTRADE_MAX_HORIZON_DAYS = 1


def _bootstrap_median_and_p90(sample: np.ndarray, n_boot: int, rng: np.random.RandomState) -> tuple[np.ndarray, np.ndarray]:
    """對`sample`做`n_boot`次重抽樣（取後放回，size與原樣本相同），同一次
    抽樣同時算中位數與P90——用同一組抽樣序列避免兩個統計量各自獨立抽樣
    製造不必要的額外隨機差異（同一份bootstrap資料，兩個統計量共用）。
    """
    n = len(sample)
    idx = rng.randint(0, n, size=(n_boot, n))
    draws = sample[idx]
    return np.median(draws, axis=1), np.percentile(draws, P_TAIL, axis=1)


def tail_test(
    signal_dates,
    forward_returns,
    control_returns,
    horizon: int,
    *,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = 20260922,
    min_n: int = 10,
) -> dict:
    """比較訊號組(`forward_returns`)與對照組(`control_returns`)的報酬分布，
    側重右尾/左尾而非只看均值。

    參數：
        signal_dates: 訊號組每筆事件的日期（不參與統計計算，只用來回報
            事件時間窗，供呼叫端核對PIT對齊有沒有做對——刻意保留在簽名
            裡而非省略，是為了讓呼叫端不能跳過「這批事件到底發生在什麼
            時候」這個誠實揭露）。
        forward_returns: 訊號組事件後的前瞻報酬（呼叫端已完成PIT對齊，
            本函式不重新驗證）。
        control_returns: 對照組（同時間窗/同產業/同市值分位、未觸發
            訊號個股）事件後的前瞻報酬，PIT對齊由呼叫端負責。
        horizon: 持有期（交易日），只用來決定成本模型的稅率假設，不影響
            上面兩組報酬本身的計算。

    回傳dict（NaN已在輸入端被過濾掉，不參與統計）：
        median_diff / median_diff_ci90（bootstrap 5~95百分位）
        p90_diff / p90_diff_ci90
        right_tail_share_signal / right_tail_share_control（>+20%比例）
        left_tail_share_signal / left_tail_share_control（<-20%比例）
        expected_value_signal_net / expected_value_control_net / expected_value_diff_net
            （均值扣除round-trip成本，1.8折commission_discount，依horizon
            選當沖/一般稅率）
        n_signal / n_control / n_bootstrap / horizon / insufficient_n

    `insufficient_n=True`時（任一組有效樣本數<`min_n`）其餘欄位一律為
    None，不得猜測性地算出一個看似合理但樣本不足以支撐的數字。
    """
    sig = np.asarray([float(v) for v in forward_returns if v is not None and not np.isnan(v)], dtype=float)
    ctl = np.asarray([float(v) for v in control_returns if v is not None and not np.isnan(v)], dtype=float)
    n_signal, n_control = len(sig), len(ctl)
    n_dates = len(list(signal_dates)) if signal_dates is not None else n_signal

    base = {
        "n_signal": n_signal, "n_control": n_control, "n_signal_dates": n_dates,
        "horizon": horizon, "n_bootstrap": n_bootstrap,
    }
    if n_signal < min_n or n_control < min_n:
        base.update({
            "insufficient_n": True, "min_n": min_n,
            "median_diff": None, "median_diff_ci90": None,
            "p90_diff": None, "p90_diff_ci90": None,
            "right_tail_share_signal": None, "right_tail_share_control": None,
            "left_tail_share_signal": None, "left_tail_share_control": None,
            "expected_value_signal_net": None, "expected_value_control_net": None,
            "expected_value_diff_net": None,
        })
        return base

    rng_sig = np.random.RandomState(seed)
    rng_ctl = np.random.RandomState(seed + 1)
    med_boot_sig, p90_boot_sig = _bootstrap_median_and_p90(sig, n_bootstrap, rng_sig)
    med_boot_ctl, p90_boot_ctl = _bootstrap_median_and_p90(ctl, n_bootstrap, rng_ctl)
    median_diff_boot = med_boot_sig - med_boot_ctl
    p90_diff_boot = p90_boot_sig - p90_boot_ctl

    daytrade = horizon <= DAYTRADE_MAX_HORIZON_DAYS
    cost = round_trip_cost_pct(daytrade=daytrade, commission_discount=COMMISSION_DISCOUNT)
    ev_sig_net = float(np.mean(sig) - cost)
    ev_ctl_net = float(np.mean(ctl) - cost)

    base.update({
        "insufficient_n": False, "min_n": min_n,
        "median_signal": float(np.median(sig)), "median_control": float(np.median(ctl)),
        "median_diff": float(np.mean(median_diff_boot)),
        "median_diff_ci90": [float(np.percentile(median_diff_boot, 5)), float(np.percentile(median_diff_boot, 95))],
        "p90_signal": float(np.percentile(sig, P_TAIL)), "p90_control": float(np.percentile(ctl, P_TAIL)),
        "p90_diff": float(np.mean(p90_diff_boot)),
        "p90_diff_ci90": [float(np.percentile(p90_diff_boot, 5)), float(np.percentile(p90_diff_boot, 95))],
        "right_tail_share_signal": float(np.mean(sig > RIGHT_TAIL_THRESHOLD)),
        "right_tail_share_control": float(np.mean(ctl > RIGHT_TAIL_THRESHOLD)),
        "left_tail_share_signal": float(np.mean(sig < LEFT_TAIL_THRESHOLD)),
        "left_tail_share_control": float(np.mean(ctl < LEFT_TAIL_THRESHOLD)),
        "cost_pct_roundtrip": cost, "daytrade_assumed": daytrade, "commission_discount": COMMISSION_DISCOUNT,
        "expected_value_signal_net": ev_sig_net, "expected_value_control_net": ev_ctl_net,
        "expected_value_diff_net": float(ev_sig_net - ev_ctl_net),
    })
    return base


def _self_test() -> None:
    """純數學自我測試（不碰任何市場資料）：訊號組刻意灌右尾，驗證函式
    抓得到方向正確的median_diff/p90_diff/right_tail_share差異。
    """
    rng = np.random.RandomState(0)
    ctl = rng.normal(0.0, 0.05, size=500)
    sig = np.concatenate([rng.normal(0.0, 0.05, size=450), np.full(50, 0.35)])  # 10%右尾怪獸單
    out = tail_test(list(range(len(sig))), sig, ctl, horizon=20, n_bootstrap=2000)
    assert not out["insufficient_n"]
    assert out["p90_diff"] > 0, out
    assert out["right_tail_share_signal"] > out["right_tail_share_control"], out
    assert out["median_diff_ci90"][0] <= out["median_diff"] <= out["median_diff_ci90"][1]
    print("tail_test 自我測試 PASS：", {k: out[k] for k in ("p90_diff", "right_tail_share_signal", "right_tail_share_control")})


if __name__ == "__main__":
    _self_test()
