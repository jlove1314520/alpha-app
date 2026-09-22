# -*- coding: utf-8 -*-
"""
規.三（出場.零，2026-09-23總司令裁示【拆除機構約束，改集中版】規.三）。

背景：366次試驗全部在測「買什麼」，零次測「什麼時候賣」。集中之後，
出場規則是天條一唯一的實質防線。本腳本在**同一個進場訊號**（買入並
持有0050，最笨的那個，目的是隔離出場規則本身的效果，不跟選股糾纏在
一起）上比較四種出場規則：

    E-a 固定持有期到期出場（對照組，等於現在的做法＝永久買進持有，
        不主動出場，直到回測結束才平倉）
    E-b 固定停損 {-8%, -15%, -25%}（從進場價起算）
    E-c 移動停損（從進場後最高點回落 {10%, 20%}）
    E-d 大盤regime出場（0050跌破200日均線即全數轉現金，站上均線才
        重新買回）

判定量：年化報酬(CAGR)、MDD、Calmar、換手率，**未扣成本／扣成本
（基準情境=1.8折+預設滑價，見validation/margin_of_safety.py）兩條
並列**（裁示原文「必須同時輸出未扣成本與扣成本兩條，因為停損會大幅
拉高換手」）。

**[自行裁量]記錄**：
1. 裁示原文列舉的變體數 1(E-a)+3(E-b)+2(E-c)+1(E-d)=7，跟原文「登記為
   8次試驗」的字面數字對不上。沒有找到自然的第8個變體（不猜測湊數），
   如實只登記7筆，這個落差在PENDING_QUEUE.md與commit訊息裡如實記錄，
   不假裝湊到8筆。
2. **重入(reentry)節奏**：E-b/E-c觸發停損出場後，「下一次進場時機」
   裁示原文未明講。本腳本採**連續每日檢查、出場後次一交易日立即
   重新買回**（不是等固定週期換股日）——理由：這裡測的是「停損規則
   本身」的效果，若重入延遲到任意固定週期，會把「重入節奏」這個額外
   自由度混進「出場規則」的比較裡，讓四組規則不是在同一個重入假設下
   比較。E-d比照同一節奏：跌破均線次一交易日出場、站回均線次一交易日
   重新買回。E-a沒有出場事件，此假設對它不生效。
3. **執行延遲**：沿用`backtest/engine.py`既有的
   `EXECUTION_LAG_DAYS=1`精神——出場/進場訊號用T日收盤價判斷，
   在T+1日收盤價成交，不同日決策同日成交（避免未來函數）。
4. **移動停損的峰值追蹤範圍**：從「本次進場」開始重新累計峰值，不是
   整個回測期間的峰值——停損邏輯的峰值理應綁定當次持倉，不然重新
   進場後會被前一次持倉的舊峰值誤傷。
5. **200日均線的資料起點**：`adj_close`序列前200個交易日沒有均線值
   （`rolling(200, min_periods=200)`），E-d在這段期間視為「均線未定義
   時預設持有」（等同E-a行為），待均線定義後才開始套用regime判斷，
   已在輸出裡註記這段天數。

資料來源：`survival_constraint_allocation_test.py::load_0050_full_
history()`（天條一.1既有函式，FinMind手動還原權息，覆蓋2003-06-30
起，已含holdout安全截斷至VAL_END），直接重用不重寫（見
`CONCENTRATED_SPEC.md`第3節同一個發現）。
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

from survival_constraint_allocation_test import load_0050_full_history
from validation import costs as costmod
from validation.margin_of_safety import margin_of_safety_scenarios, BASELINE_KEY
from validation.holdout import assert_no_holdout_leakage, is_holdout_consumed
from trial_registry import register_trial

REPO_ROOT = Path(__file__).resolve().parent.parent
MA_WINDOW = 200
EXECUTION_LAG_DAYS = 1
INITIAL_CAPITAL = 1_000_000.0
TZ = timezone(timedelta(hours=8))

OUT_JSON = REPO_ROOT / "research" / "data" / "exit_rule_lab_result.json"
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"

# E-a沒有主動出場事件；其餘六個變體的定義：
RULES = {
    "E-a_buy_and_hold": {"type": "hold_forever"},
    "E-b_stop8": {"type": "fixed_stop", "pct": 0.08},
    "E-b_stop15": {"type": "fixed_stop", "pct": 0.15},
    "E-b_stop25": {"type": "fixed_stop", "pct": 0.25},
    "E-c_trailing10": {"type": "trailing_stop", "pct": 0.10},
    "E-c_trailing20": {"type": "trailing_stop", "pct": 0.20},
    "E-d_ma200_regime": {"type": "ma_regime"},
}


def load_prices() -> pd.DataFrame:
    df = load_0050_full_history()  # date, adj_close -- 已holdout-safe
    df = df.sort_values("date").reset_index(drop=True)
    df["ma200"] = df["adj_close"].rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
    assert_no_holdout_leakage(df, context="exit_rule_lab 0050 price+ma200")
    return df


def _leg_cost(notional: float, *, side: str, commission_discount: float, slippage_bps: float) -> float:
    """單邊交易成本（手續費+稅(僅賣出)+滑價），沿用validation/costs.py費率常數。"""
    commission = notional * costmod.COMMISSION_RATE * commission_discount
    slip = notional * (slippage_bps / 10_000)
    tax = notional * costmod.SECURITIES_TX_TAX_NORMAL if side == "sell" else 0.0
    return commission + slip + tax


def simulate(df: pd.DataFrame, rule: dict, *, commission_discount: float, slippage_bps: float,
             apply_costs: bool) -> dict:
    """單資產、逐日模擬。回傳equity_curve(list of {date,equity})、trades(list)。
    T日收盤價判斷訊號，T+1日收盤價成交（EXECUTION_LAG_DAYS），不同日決策同日成交。
    """
    dates = df["date"].tolist()
    closes = df["adj_close"].tolist()
    ma200 = df["ma200"].tolist()
    n = len(dates)

    cash = INITIAL_CAPITAL
    shares = 0.0
    in_position = False
    entry_price = None
    peak_price = None
    pending_action = None  # "buy" / "sell"，於下一交易日執行
    pending_action_reason = None
    trades = []
    equity_rows = []
    rule_type = rule["type"]
    pct = rule.get("pct")

    for i in range(n):
        date = dates[i]
        close = closes[i]

        # 1) 執行前一日排定的動作（T+1成交）
        if pending_action == "buy" and not in_position:
            fee = _leg_cost(cash, side="buy", commission_discount=commission_discount,
                             slippage_bps=slippage_bps) if apply_costs else 0.0
            notional = cash - fee if fee > 0 else cash
            shares = notional / close if close > 0 else 0.0
            cash = 0.0
            in_position = True
            entry_price = close
            peak_price = close
            trades.append({"date": date, "side": "buy", "price": close, "reason": "entry"})
        elif pending_action == "sell" and in_position:
            notional = shares * close
            fee = _leg_cost(notional, side="sell", commission_discount=commission_discount,
                             slippage_bps=slippage_bps) if apply_costs else 0.0
            cash = notional - fee
            shares = 0.0
            in_position = False
            trades.append({"date": date, "side": "sell", "price": close, "reason": pending_action_reason})
            entry_price = None
            peak_price = None
        pending_action = None

        # 2) 依當日收盤價判斷訊號（供下一交易日執行）
        if in_position:
            peak_price = max(peak_price, close)
            exit_today = False
            if rule_type == "fixed_stop" and close <= entry_price * (1 - pct):
                exit_today = True
            elif rule_type == "trailing_stop" and close <= peak_price * (1 - pct):
                exit_today = True
            elif rule_type == "ma_regime":
                m = ma200[i]
                if not pd.isna(m) and close < m:
                    exit_today = True
            if exit_today and i + EXECUTION_LAG_DAYS < n:
                pending_action = "sell"
                pending_action_reason = rule_type
        else:
            enter_today = True  # 進場訊號恆為「買入並持有0050」
            if rule_type == "ma_regime":
                m = ma200[i]
                # 均線未定義的前200個交易日，regime判準不成立，視同持有
                # （見腳本docstring [自行裁量]5），此處不需額外處理——
                # in_position初值False，但下面的buy排程本身不受影響，
                # 均線未定義時 close < m 恆為False（NaN比較），故不會被
                # ma_regime觸發過提早出場；起始買入沿用下方共用邏輯。
                pass
            if enter_today and i + EXECUTION_LAG_DAYS < n:
                pending_action = "buy"

        equity = cash + shares * close
        equity_rows.append({"date": date, "equity": equity})

    equity_df = pd.DataFrame(equity_rows)
    return {"equity_curve": equity_df, "trades": trades}


def compute_metrics(equity_df: pd.DataFrame, trades: list) -> dict:
    eq = equity_df["equity"]
    dates = pd.to_datetime(equity_df["date"])
    n_days = len(eq)
    n_years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    total_return = eq.iloc[-1] / INITIAL_CAPITAL - 1
    cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else float("nan")
    running_max = eq.cummax()
    dd = (eq - running_max) / running_max
    mdd = float(dd.min())
    calmar = cagr / abs(mdd) if mdd < 0 else float("nan")
    n_round_trips = sum(1 for t in trades if t["side"] == "sell")
    # 換手率：年化「買入次數」佔全期年數比例（單資產，用交易次數而非精確notional，
    # 因為shares隨每次進場的現金基礎變動，交易次數本身就是最直觀的換手代理）。
    turnover_annualized = n_round_trips / n_years if n_years > 0 else float("nan")
    return {
        "n_days": n_days, "n_years": round(n_years, 3),
        "total_return_pct": round(total_return * 100, 4),
        "cagr_pct": round(cagr * 100, 4),
        "mdd_pct": round(mdd * 100, 4),
        "calmar": round(calmar, 4) if calmar == calmar else None,
        "n_trades": len(trades), "n_round_trips": n_round_trips,
        "turnover_annualized_round_trips_per_year": round(turnover_annualized, 4),
    }


def main() -> None:
    df = load_prices()
    n_ma_undefined = int(df["ma200"].isna().sum())
    scenarios = margin_of_safety_scenarios(daytrade=False)
    baseline_cost_pct = scenarios[BASELINE_KEY]
    # baseline情境是round-trip cost_pct，這裡拆回買/賣兩腿供逐筆試算——round_trip_cost_pct
    # 本身就是buy_leg+sell_leg，這裡改用margin_of_safety.py同一組(commission_discount,
    # slippage_bps)組合重算，而不是直接切半round-trip數字（因為買/賣兩腿費率不對稱，
    # 賣腿多一個證交稅，對半切會算錯）。
    baseline_commission_discount = 0.18
    baseline_slippage_bps = costmod.DEFAULT_SLIPPAGE_BPS

    results = {}
    for name, rule in RULES.items():
        gross = simulate(df, rule, commission_discount=1.0, slippage_bps=0.0, apply_costs=False)
        net = simulate(df, rule, commission_discount=baseline_commission_discount,
                       slippage_bps=baseline_slippage_bps, apply_costs=True)
        results[name] = {
            "rule_definition": rule,
            "gross": compute_metrics(gross["equity_curve"], gross["trades"]),
            "net_baseline_1p8discount": compute_metrics(net["equity_curve"], net["trades"]),
        }

    out = {
        "generated_at": datetime.now(TZ).isoformat(),
        "n_price_days": len(df), "n_ma200_undefined_days": n_ma_undefined,
        "date_range": [df["date"].iloc[0].strftime("%Y-%m-%d") if hasattr(df["date"].iloc[0], "strftime")
                        else str(df["date"].iloc[0]),
                        df["date"].iloc[-1].strftime("%Y-%m-%d") if hasattr(df["date"].iloc[-1], "strftime")
                        else str(df["date"].iloc[-1])],
        "baseline_cost_scenario": {
            "commission_discount": baseline_commission_discount,
            "slippage_bps": baseline_slippage_bps,
            "round_trip_cost_pct_reference": baseline_cost_pct,
        },
        "rules": results,
        "n_declared_by_decree": 8, "n_actual_variants": len(RULES),
        "count_mismatch_note": "裁示原文寫8次試驗，實際列舉的變體數(E-a1+E-b3+E-c2+E-d1)=7，"
                                "如實登記7筆，不湊數（見本檔docstring[自行裁量]1）",
        "holdout_consumed_check": is_holdout_consumed(),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_JSON}")
    for name, r in results.items():
        g, nn = r["gross"], r["net_baseline_1p8discount"]
        print(f"{name}: gross CAGR={g['cagr_pct']}% MDD={g['mdd_pct']}% Calmar={g['calmar']} "
              f"| net CAGR={nn['cagr_pct']}% MDD={nn['mdd_pct']}% Calmar={nn['calmar']} "
              f"turnover={nn['turnover_annualized_round_trips_per_year']}/yr n_trades={nn['n_trades']}")

    # 登記7筆試驗（見docstring[自行裁量]1，裁示原文寫8筆但列舉變體只有7個）
    for name, r in results.items():
        g, nn = r["gross"], r["net_baseline_1p8discount"]
        design = (f"規.三出場.零：同一進場訊號(買入並持有0050)，出場規則={name}"
                  f"（{json.dumps(r['rule_definition'], ensure_ascii=False)}）。"
                  f"日頻逐日模擬，T日收盤價判斷訊號、T+1日收盤價成交，"
                  f"MA200前{n_ma_undefined}日均線未定義視同持有。")
        result_str = (f"n={g['n_days']}天({g['n_years']}年)。"
                      f"未扣成本：CAGR={g['cagr_pct']}% MDD={g['mdd_pct']}% Calmar={g['calmar']}。"
                      f"扣成本(基準情境1.8折)：CAGR={nn['cagr_pct']}% MDD={nn['mdd_pct']}% "
                      f"Calmar={nn['calmar']} 換手率={nn['turnover_annualized_round_trips_per_year']}"
                      f"次/年 交易數={nn['n_trades']}。")
        notes = ("純描述性比較，非alpha檢定——沒有vs隨機/vs買進持有的統計顯著性判準，"
                "目的是量出四種出場規則本身對MDD/Calmar/換手率的權衡，供規.二集中版第6節(b)"
                "出場規則設計與天條一防線參考。")
        register_trial(
            track="TW", name=f"exit_rule_lab_{name}", design=design, result=result_str,
            verdict="EXPERIMENTAL", notes=notes,
            round_note="規.三出場.零，互動視窗CC，交辦優先於自走",
        )
    print("已登記7筆試驗至TRIALS_LEDGER.md")

    with HEARTBEAT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(TZ).isoformat(), "track": "marathon", "round": "605",
            "item": "規.三：exit_rule_lab.py完成並執行，登記7筆試驗（E-a~E-d出場規則比較）",
            "artifacts_changed": ["research/exit_rule_lab.py", "research/data/exit_rule_lab_result.json",
                                  "research/TRIALS_LEDGER.md"],
            "note": "純描述性比較，非alpha檢定",
        }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
