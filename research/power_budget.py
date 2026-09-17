# -*- coding: utf-8 -*-
"""檢定力預算計算機（2026-09-18 總司令裁示【研究方向重構】階段一.1，最高優先）。

**要回答的問題（總司令原話）**：「我們用一把只認 9.8% 的尺，在找一個 2.5% 的
東西」——`portfolio_multifactor_v2` 在 4 年 VAL 期的 alpha 標準誤約 5%/年
（Cowork 反推兩個獨立樣本互相吻合：80 檔 10.40/1.94≈5.36、300 檔
3.05/0.626≈4.87），代表 p<0.05 的顯著性門檻需要 alpha ≥ 9.8%/年；但季頻
(t60) 贏過 0050 的損益兩平線只要 2.1~2.9% 毛 alpha（見
`research/breakeven_alpha_table.json`）。用檢定力不足的量尺去測小 alpha，
結果結構上只能是解讀不出來的 FAIL，不是「訊號不存在」的證據。

**三個函式，對應總司令原話 (a)(b)(c)**：
- `min_detectable_alpha()`：輸入年化追蹤誤差(TE)與樣本年數，回傳可偵測
  的最小 alpha。**兩個門檻都算、都印出來，不是只選一個**（同
  `breakeven_alpha_table.py` 的「simple/geometric 都算」精神）：
  - `sig_threshold_alpha_pct`：純粹讓估計值跨過 p<0.05 顯著性所需的
    alpha（z_(0.975)×SE），這是總司令原話「p<0.05 需要 alpha≥9.8%」
    用的定義，**只代表「測到了會顯著」，不代表「多數時候測得到」**。
  - `mde_80pct_power_alpha_pct`：本專案既有慣例（見
    `calibration_probe_momentum_12_1.py` round98「80%檢定力最小可偵測
    IC」同一套定義）——(z_(0.975)+z_(0.80))×SE，是「真實效應要多大，
    才有 80% 機率被這個樣本量測到顯著」，比純顯著性門檻更保守也更
    誠實，**新的前置關卡規則用這一個當判準**。
- `required_years()`：反過來解，給定目標 alpha 與 TE，要幾年樣本才夠。
- `realized_tracking_error()`：對一條已回測出來的 equity curve，量測它
  相對大盤的**實際年化追蹤誤差**（CAPM 迴歸殘差標準差×sqrt(252)，
  跟`alpha_significance()`用的是同一個迴歸，只是額外把殘差std算出來
  ——`portfolio_backtest_v2.py::alpha_significance()`本身沒有回傳這個
  數字，這裡不改那支檔案，另外算一次同樣的迴歸，維持只讀不改的原則）。

**新前置關卡規則**（已寫進 `MARATHON_PROTOCOL.md` 1a-0b，跟既有 1a-0
成本敏感度前置關卡並列，同一節精神：「先算檢定力再花算力，不要反過來」）：
任何策略層試驗開跑前，先用該構造既有的（或同類構造的）年化追蹤誤差、
樣本年數算出 `mde_80pct_power_alpha_pct`；若這個數字 > 該換倉頻率
`breakeven_alpha_table.json` 損益兩平線(geometric版)的 3 倍，這個試驗
**結構上只能產生無法解讀的 FAIL**，不准開跑。**這是新增的前置檢查，
不是放寬任何既有事後判定門檻**——原本通過的 PASS/CHEAP_PASS 不受影響，
既有 FAIL 判定本身也不因此撤銷（那是第 3 步 UNDERPOWERED 重新分類的
工作，不在這支腳本改）。

跑法：`python research/power_budget.py`（(b) 對既有 portfolio 構造實測，
複用 `portfolio_backtest_v2.py::run_one()` 現成的快速掃描模式——
`do_cost_sensitivity=False, do_random_control=False`，純本機計算，
零新增 API 呼叫，複用既有 300 檔快取）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from scipy import stats
from scipy.stats import norm

from validation import holdout

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).parent / "power_budget_table.json"
TZ = timezone(timedelta(hours=8))
TRADING_DAYS_PER_YEAR = 252

Z_SIG = norm.ppf(1 - 0.05 / 2)     # ≈1.96，p<0.05雙尾顯著性門檻
Z_POWER_80 = norm.ppf(0.80)        # ≈0.8416，80%檢定力


def min_detectable_alpha(annual_tracking_error_pct: float, n_years: float) -> dict:
    """(a) 輸入年化追蹤誤差(TE,百分比)與樣本年數，回傳可偵測的最小alpha。"""
    if n_years <= 0 or annual_tracking_error_pct <= 0:
        return {"se_pct": float("nan"), "sig_threshold_alpha_pct": float("nan"),
                "mde_80pct_power_alpha_pct": float("nan")}
    se = annual_tracking_error_pct / (n_years ** 0.5)
    return {
        "se_pct": round(se, 4),
        "sig_threshold_alpha_pct": round(Z_SIG * se, 4),
        "mde_80pct_power_alpha_pct": round((Z_SIG + Z_POWER_80) * se, 4),
    }


def required_years(target_alpha_pct: float, annual_tracking_error_pct: float,
                    use_80pct_power: bool = True) -> float:
    """(a) 反過來解：給定目標alpha與TE，要幾年樣本才夠偵測到。"""
    if target_alpha_pct <= 0 or annual_tracking_error_pct <= 0:
        return float("nan")
    z = (Z_SIG + Z_POWER_80) if use_80pct_power else Z_SIG
    # target = z * TE / sqrt(n)  =>  n = (z*TE/target)^2
    return round((z * annual_tracking_error_pct / target_alpha_pct) ** 2, 2)


def realized_tracking_error(equity_curve, market_df) -> dict:
    """(b) 對一條equity curve量測相對大盤的實際年化追蹤誤差。

    跟`portfolio_backtest_v2.py::alpha_significance()`用同一個CAPM迴歸
    （net_return = alpha + beta*mkt_return），只是這裡額外把殘差std算
    出來換算成年化TE——那支不改，這裡另外算一次同樣的迴歸。
    """
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    import pandas as pd
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"n_days": len(merged), "annual_te_pct": float("nan"), "beta": float("nan")}
    reg = stats.linregress(merged["mkt_return"], merged["net_return"])
    residuals = merged["net_return"] - (reg.intercept + reg.slope * merged["mkt_return"])
    annual_te_pct = float(residuals.std(ddof=2) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100)
    n_years = len(merged) / TRADING_DAYS_PER_YEAR
    return {"n_days": len(merged), "n_years": round(n_years, 2),
            "annual_te_pct": round(annual_te_pct, 4), "beta": round(float(reg.slope), 4)}


def _load_breakeven_table() -> dict:
    p = ROOT / "research" / "breakeven_alpha_table.json"
    if not p.exists():
        raise SystemExit(f"{p} 不存在——先跑 python research/validation/breakeven_alpha_table.py")
    return json.loads(p.read_text(encoding="utf-8"))


def measure_existing_constructs() -> list[dict]:
    """(b) 對既有portfolio構造（A_4pass/B_plus_value_pe，兩種加權x兩種頻率的
    VAL期）實測年化追蹤誤差，算出各自的最小可偵測alpha，跟損益兩平線(3x)比較。
    複用portfolio_backtest_v2.py既有的快速掃描模式，零新增API呼叫。
    """
    import portfolio_backtest_v2 as pb2
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data

    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in power_budget")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + factors (cached)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    industry_map = load_industry_map()
    trend_regime = pb2._trend_regime_series(market_df)
    liquidity = {sid: pb2._liquidity_proxy_series(d) for sid, d in data.items()}

    breakeven = _load_breakeven_table()
    breakeven_by_window = {hp["window"]: hp for hp in breakeven["holding_periods"]}
    cadence_to_window = {"monthly": "t20", "quarterly": "t60"}

    rows = []
    for factor_version in pb2.FACTOR_VERSIONS:
        for weight_mode in ("equal", "ic_weighted", "regime_weighted"):
            for cadence_name in pb2.REBALANCE_CADENCES:
                r = pb2.run_one(factor_version, weight_mode, cadence_name, "VALIDATION",
                                 data, market_df, industry_map, trend_regime, liquidity,
                                 "2021-01-01", holdout.VAL_END,
                                 do_cost_sensitivity=False, do_random_control=False)
                cfg = pb2.BacktestConfig(start_date="2021-01-01", end_date=holdout.VAL_END,
                                          max_positions=pb2.TOP_N,
                                          rebalance_every_n_days=pb2.REBALANCE_CADENCES[cadence_name],
                                          book_name=f"power_budget_{factor_version}_{weight_mode}_{cadence_name}")
                signal_fn = pb2.make_signal_fn(industry_map, pb2.FACTOR_VERSIONS[factor_version],
                                                weight_mode, trend_regime, liquidity)
                bt = pb2.run_backtest(signal_fn, data, market_df, cfg)
                te = realized_tracking_error(bt.equity_curve, market_df)
                mda = min_detectable_alpha(te["annual_te_pct"], te.get("n_years", float("nan")))

                window = cadence_to_window.get(cadence_name)
                geo_breakeven = None
                if window and window in breakeven_by_window:
                    # 無折扣(1.0x)情境當保守基準（跟breakeven_alpha_table.py的判定精神一致：
                    # 不假設已查證到的折扣費率，用最保守的1.0x當預設）
                    for sc in breakeven_by_window[window]["scenarios"]:
                        if sc["discount_label"].startswith("無折扣"):
                            geo_breakeven = sc["breakeven_annual_alpha_pct_geometric"]
                            break

                gate_verdict = None
                if geo_breakeven is not None and mda["mde_80pct_power_alpha_pct"] == mda["mde_80pct_power_alpha_pct"]:
                    threshold_3x = geo_breakeven * 3
                    gate_verdict = ("UNDERPOWERED_BLOCK" if mda["mde_80pct_power_alpha_pct"] > threshold_3x
                                     else "OK_TO_RUN")

                row = {
                    "factor_version": factor_version, "weight_mode": weight_mode,
                    "cadence": cadence_name, "realized_alpha_ann_pct": r["alpha_ann_pct"],
                    "realized_alpha_pvalue": r["alpha_pvalue"],
                    **te, **mda,
                    "breakeven_window": window,
                    "breakeven_geometric_1x_pct": geo_breakeven,
                    "breakeven_3x_pct": round(geo_breakeven * 3, 4) if geo_breakeven is not None else None,
                    "gate_1a_0b_verdict": gate_verdict,
                }
                rows.append(row)
                print(f"  {factor_version}/{weight_mode}/{cadence_name}: "
                      f"realized_alpha={r['alpha_ann_pct']:+.2f}%(p={r['alpha_pvalue']:.3f})  "
                      f"TE={te['annual_te_pct']:.2f}%  n_years={te.get('n_years')}  "
                      f"MDE(80%power)={mda['mde_80pct_power_alpha_pct']:.2f}%  "
                      f"3x損益兩平={row['breakeven_3x_pct']}%  → {gate_verdict}")

    print(f"\nis_holdout_consumed()收工前檢查：{holdout.is_holdout_consumed()}")
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"
    return rows


def main() -> None:
    rows = measure_existing_constructs()
    out = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "question": "既有portfolio構造在我們有的資料長度下，最小可偵測alpha是多少，"
                        "跟該換倉頻率的3倍損益兩平線比較，是否結構上只能產生無法解讀的FAIL",
            "definitions": {
                "sig_threshold_alpha_pct": "z(0.975)*SE，跨過p<0.05所需的alpha（只代表測到了會顯著）",
                "mde_80pct_power_alpha_pct": "(z(0.975)+z(0.80))*SE，80%機率能測到顯著的最小真實效應"
                                             "（本專案既有80%檢定力慣例，前置關卡判準用這一個）",
            },
            "gate_rule": "MARATHON_PROTOCOL.md 1a-0b：mde_80pct_power_alpha_pct > "
                        "3x breakeven_annual_alpha_pct_geometric(1.0x折扣) → 不准開跑",
        },
        "constructs": rows,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n寫入 {OUT_PATH.relative_to(Path(__file__).parent)}")


if __name__ == "__main__":
    main()
