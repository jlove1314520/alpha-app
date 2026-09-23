# -*- coding: utf-8 -*-
"""
規.三（出場.零，2026-09-23總司令裁示【拆除機構約束，改集中版】規.三）。
**2026-09-23總司令裁示【修正兩個系統性錯誤＋兩件待審閱結案】修.一重做**：
原始版本（`TRIALS_LEDGER.md` #338~#344，已標INVALID_BUG）有一個真實bug——
未持倉時`enter_today = True`無條件成立、`ma_regime`分支只有`pass`，
docstring寫的「站上均線才進場」從未實作，任何出場觸發後隔日即無條件
買回。證據：E-d原本交易數高達1357筆、未扣成本MDD −69.34%（比買進
持有本身的−55.75%還差——一個設計用來降曝險的機制，MDD反而更差，這是
bug的直接證據，不是市場給的結論）。本輪修正：

    E-b/E-c（固定/移動停損）：出場後**冷卻20個交易日**才能重新進場，
        重新進場時以新的進場價與新的峰值重新計算（不沿用前一次持倉的
        entry_price/peak_price）。
    E-d（MA200 regime）：出場後必須**收盤站回MA200之上**才重新進場
        （不加緩衝帶、不新增參數，嚴格`close > ma200`）。
    E-a（買進持有）：沒有出場事件，此修正對它不生效。

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
拉高換手」）。**成本改用0050的ETF證交稅率0.1%**（`validation.costs.
tax_rate("etf")`，2026-09-23修.二修正，原本誤用一般股票稅率0.3%）。

**[自行裁量]記錄**：
1. 裁示原文列舉的變體數 1(E-a)+3(E-b)+2(E-c)+1(E-d)=7，跟原文「登記為
   8次試驗」的字面數字對不上。沒有找到自然的第8個變體（不猜測湊數），
   如實只登記7筆，這個落差在PENDING_QUEUE.md與commit訊息裡如實記錄，
   不假裝湊到8筆。
2. **冷卻期天數(20)與均線緩衝(0)是裁示原文明寫的值，不是本腳本選的**
   ——E-b/E-c的20交易日冷卻、E-d的「不加緩衝帶」都是裁示原文字面
   規定，不算自由參數。
3. **執行延遲**：沿用`backtest/engine.py`既有的
   `EXECUTION_LAG_DAYS=1`精神——出場/進場訊號用T日收盤價判斷，
   在T+1日收盤價成交，不同日決策同日成交（避免未來函數）。
4. **移動停損的峰值追蹤範圍**：從「本次進場」開始重新累計峰值，不是
   整個回測期間的峰值——停損邏輯的峰值理應綁定當次持倉，不然重新
   進場後會被前一次持倉的舊峰值誤傷。
5. **200日均線的資料起點**：`adj_close`序列前200個交易日沒有均線值
   （`rolling(200, min_periods=200)`），E-d在這段期間視為「均線未定義
   時預設持有/預設可進場」（等同E-a行為），待均線定義後才開始套用
   regime判斷，已在輸出裡註記這段天數。
6. **交易頻率警告門檻(>12次/年)是裁示原文明寫的值**，守門邏輯本身
   包在try/except，失敗只印警告不中止腳本（`CLAUDE.md`十二節「守門員
   自己的失敗只能降級成警告」）。
7. **起點敏感度的60個起點**：裁示原文明寫「2003-07到2008-06每月第一個
   交易日」，逐一取該月第一個交易日當新的模擬起點，跑到資料結尾
   （VAL_END），不是另外抽樣或猜測範圍。

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
COOLDOWN_DAYS = 20          # 修.一裁示原文：E-b/E-c出場後冷卻20交易日才重新進場
MAX_ROUND_TRIPS_PER_YEAR = 12  # 修.一裁示原文：交易頻率自我檢查門檻
SENSITIVITY_START_RANGE = ("2003-07", "2008-06")  # 修.一裁示原文：起點敏感度範圍

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
    """單邊交易成本（手續費+稅(僅賣出)+滑價），沿用validation/costs.py費率常數。
    2026-09-23修.二修正：交易標的是0050（股票型ETF），賣出證交稅率應為0.1%
    （`tax_rate("etf")`），原本誤用一般股票稅率0.3%（`SECURITIES_TX_TAX_
    NORMAL`），系統性多扣了0.2個百分點——見PENDING_QUEUE.md修.二完整清單。
    """
    commission = notional * costmod.COMMISSION_RATE * commission_discount
    slip = notional * (slippage_bps / 10_000)
    tax = notional * costmod.tax_rate("etf") if side == "sell" else 0.0
    return commission + slip + tax


def simulate(df: pd.DataFrame, rule: dict, *, commission_discount: float, slippage_bps: float,
             apply_costs: bool, start_idx: int = 0) -> dict:
    """單資產、逐日模擬。回傳equity_curve(list of {date,equity})、trades(list)。
    T日收盤價判斷訊號，T+1日收盤價成交（EXECUTION_LAG_DAYS），不同日決策同日成交。

    `start_idx`：從`df`第幾列開始模擬（供起點敏感度掃描重用同一份價格
    序列，避免每個起點都重新讀檔/算MA200；MA200仍用**全序列**算好的
    值，只是模擬本身從`start_idx`才開始，這樣MA200在新起點當下就已經
    是有效值，不會因為起點往後移而讓均線視窗重新出現「未定義」的情況）。

    2026-09-23修.一修正：出場後不再無條件隔日買回——
        fixed_stop/trailing_stop：出場後冷卻`COOLDOWN_DAYS`個交易日才能
            重新進場，重新進場時entry_price/peak_price以新進場價重算。
        ma_regime：出場後必須收盤站回MA200之上（`close > ma200`，不加
            緩衝帶）才能重新進場。
        hold_forever：沒有出場事件，不受影響。
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
    cooldown_until = -1  # fixed_stop/trailing_stop專用：i < cooldown_until時不得進場
    trades = []
    equity_rows = []
    rule_type = rule["type"]
    pct = rule.get("pct")

    for i in range(start_idx, n):
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
            entry_price = close  # 每次進場（含重新進場）都以當次成交價重算
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
            if rule_type in ("fixed_stop", "trailing_stop"):
                cooldown_until = i + COOLDOWN_DAYS
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
            if rule_type in ("fixed_stop", "trailing_stop"):
                # 冷卻期內不得進場；冷卻期滿（或從未出場過，cooldown_until=-1
                # 恆小於任何i）才可進場。
                enter_today = i >= cooldown_until
            elif rule_type == "ma_regime":
                m = ma200[i]
                # 均線未定義時視同「可進場」（見docstring[自行裁量]5，
                # 涵蓋初始建倉與均線未定義期間的重新進場）；均線已定義時
                # 嚴格要求收盤站回均線之上才能（重新）進場，不加緩衝帶。
                enter_today = pd.isna(m) or close > m
            else:  # hold_forever
                enter_today = True
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


def check_trade_frequency(name: str, turnover_annualized: float) -> str | None:
    """修.一裁示原文：交易次數若>每年12次來回，輸出警告一行。守門邏輯
    本身包try/except，失敗只降級為警告不中止腳本（CLAUDE.md十二節）。
    回傳警告字串（無警告時回傳None）。
    """
    try:
        if turnover_annualized is not None and turnover_annualized == turnover_annualized \
                and turnover_annualized > MAX_ROUND_TRIPS_PER_YEAR:
            return (f"⚠ {name}: 年化換手{turnover_annualized:.2f}次/年 > "
                    f"門檻{MAX_ROUND_TRIPS_PER_YEAR}次/年")
    except Exception as e:  # noqa: BLE001 -- 守門員自己的失敗只能降級成警告
        return f"⚠ {name}: 交易頻率檢查本身失敗（不影響其他結果）：{e}"
    return None


def _monthly_first_trading_day_starts(df: pd.DataFrame, start_ym: str, end_ym: str) -> list[int]:
    """回傳`start_ym`~`end_ym`（含）範圍內，每個月第一個交易日在`df`裡的
    整數列位置（供`simulate(start_idx=...)`使用）。"""
    dates = pd.to_datetime(df["date"])
    months = pd.period_range(start=start_ym, end=end_ym, freq="M")
    idxs = []
    for m in months:
        month_start, month_end = m.start_time, m.end_time
        mask = (dates >= month_start) & (dates <= month_end)
        candidates = df.index[mask]
        if len(candidates) == 0:
            continue  # 該月無交易日資料，誠實跳過不硬湊
        idxs.append(int(candidates[0]))
    return idxs


def start_sensitivity(df: pd.DataFrame, rule: dict, *, commission_discount: float,
                       slippage_bps: float) -> dict:
    """起點敏感度（修.一裁示原文第3點）：2003-07~2008-06每月第一個交易日
    各起跑一次（60個起點，事前寫死非本腳本挑選），扣成本後的CAGR/MDD
    中位數、P10、P90。**不計入N**（同一條規則的穩健性檢查，不是新試驗）。
    """
    start_idxs = _monthly_first_trading_day_starts(df, *SENSITIVITY_START_RANGE)
    cagrs, mdds = [], []
    for idx in start_idxs:
        if idx >= len(df) - 1:
            continue
        net = simulate(df, rule, commission_discount=commission_discount,
                        slippage_bps=slippage_bps, apply_costs=True, start_idx=idx)
        m = compute_metrics(net["equity_curve"], net["trades"])
        if m["cagr_pct"] == m["cagr_pct"]:  # 排除NaN
            cagrs.append(m["cagr_pct"])
            mdds.append(m["mdd_pct"])
    if not cagrs:
        return {"n_starts_requested": len(start_idxs), "n_starts_usable": 0}
    return {
        "n_starts_requested": len(start_idxs), "n_starts_usable": len(cagrs),
        "cagr_pct_median": round(float(np.median(cagrs)), 4),
        "cagr_pct_p10": round(float(np.percentile(cagrs, 10)), 4),
        "cagr_pct_p90": round(float(np.percentile(cagrs, 90)), 4),
        "mdd_pct_median": round(float(np.median(mdds)), 4),
        "mdd_pct_p10": round(float(np.percentile(mdds, 10)), 4),
        "mdd_pct_p90": round(float(np.percentile(mdds, 90)), 4),
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
    warnings = []
    for name, rule in RULES.items():
        gross = simulate(df, rule, commission_discount=1.0, slippage_bps=0.0, apply_costs=False)
        net = simulate(df, rule, commission_discount=baseline_commission_discount,
                       slippage_bps=baseline_slippage_bps, apply_costs=True)
        net_metrics = compute_metrics(net["equity_curve"], net["trades"])
        freq_warning = check_trade_frequency(name, net_metrics["turnover_annualized_round_trips_per_year"])
        if freq_warning:
            warnings.append(freq_warning)
        sensitivity = start_sensitivity(df, rule, commission_discount=baseline_commission_discount,
                                         slippage_bps=baseline_slippage_bps)
        results[name] = {
            "rule_definition": rule,
            "gross": compute_metrics(gross["equity_curve"], gross["trades"]),
            "net_baseline_1p8discount": net_metrics,
            "start_sensitivity": sensitivity,
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
        "cooldown_days": COOLDOWN_DAYS, "max_round_trips_per_year": MAX_ROUND_TRIPS_PER_YEAR,
        "sensitivity_start_range": list(SENSITIVITY_START_RANGE),
        "trade_frequency_warnings": warnings,
        "rules": results,
        "n_declared_by_decree": 8, "n_actual_variants": len(RULES),
        "count_mismatch_note": "裁示原文寫8次試驗，實際列舉的變體數(E-a1+E-b3+E-c2+E-d1)=7，"
                                "如實登記7筆，不湊數（見本檔docstring[自行裁量]1）",
        "invalid_prior_registration_note": "#338~#344（本輪修正前的舊版）已標INVALID_BUG，"
                                            "見TRIALS_LEDGER.md對應位置，本次重新登記新編號",
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
    if warnings:
        print("\n交易頻率警告：")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n交易頻率檢查：0筆超過門檻")

    # 登記7筆試驗（見docstring[自行裁量]1，裁示原文寫8筆但列舉變體只有7個）
    for name, r in results.items():
        g, nn, sens = r["gross"], r["net_baseline_1p8discount"], r["start_sensitivity"]
        design = (f"規.三出場.零修.一重做：同一進場訊號(買入並持有0050)，出場規則={name}"
                  f"（{json.dumps(r['rule_definition'], ensure_ascii=False)}）。"
                  f"日頻逐日模擬，T日收盤價判斷訊號、T+1日收盤價成交，"
                  f"MA200前{n_ma_undefined}日均線未定義視同持有/可進場。"
                  f"重入規則：fixed_stop/trailing_stop出場後冷卻{COOLDOWN_DAYS}交易日才重新"
                  f"進場(新entry_price/peak_price)；ma_regime出場後須收盤站回MA200之上"
                  f"才重新進場(不加緩衝帶)。取代已標INVALID_BUG的#338~#344"
                  f"（原版本重入邏輯有bug，出場後隔日無條件買回）。")
        sens_str = ("；起點敏感度(60起點2003-07~2008-06，不計入N)：" +
                    (f"CAGR中位數{sens.get('cagr_pct_median')}%(P10={sens.get('cagr_pct_p10')}%,"
                     f"P90={sens.get('cagr_pct_p90')}%)、MDD中位數{sens.get('mdd_pct_median')}%"
                     f"(P10={sens.get('mdd_pct_p10')}%,P90={sens.get('mdd_pct_p90')}%)，"
                     f"可用起點{sens.get('n_starts_usable')}/{sens.get('n_starts_requested')}"
                     if sens.get("n_starts_usable") else "無可用起點"))
        result_str = (f"n={g['n_days']}天({g['n_years']}年)。"
                      f"未扣成本：CAGR={g['cagr_pct']}% MDD={g['mdd_pct']}% Calmar={g['calmar']}。"
                      f"扣成本(基準情境1.8折)：CAGR={nn['cagr_pct']}% MDD={nn['mdd_pct']}% "
                      f"Calmar={nn['calmar']} 換手率={nn['turnover_annualized_round_trips_per_year']}"
                      f"次/年 交易數={nn['n_trades']}" + sens_str + "。")
        freq_note = check_trade_frequency(name, nn["turnover_annualized_round_trips_per_year"])
        notes = ("純描述性比較，非alpha檢定——沒有vs隨機/vs買進持有的統計顯著性判準，"
                "目的是量出四種出場規則本身對MDD/Calmar/換手率的權衡，供規.二集中版第6節(b)"
                "出場規則設計與天條一防線參考。取代INVALID_BUG的舊版(#338~#344，重入邏輯"
                "bug讓所有出場規則實質上退化成買進持有的雜訊版本，本次修正重入規則後"
                "重新執行)。" + (f" {freq_note}" if freq_note else " 交易頻率未超過門檻。"))
        register_trial(
            track="TW", name=f"exit_rule_lab_{name}", design=design, result=result_str,
            verdict="EXPERIMENTAL", notes=notes,
            round_note="規.三出場.零修.一重做，互動視窗CC，交辦優先於自走",
        )
    print("已登記7筆修正版試驗至TRIALS_LEDGER.md")

    with HEARTBEAT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(TZ).isoformat(), "track": "interactive", "round": "修.一",
            "item": "修.一：exit_rule_lab.py重入邏輯bug修正並重新登記7筆試驗（E-a~E-d出場規則比較）",
            "artifacts_changed": ["research/exit_rule_lab.py", "research/data/exit_rule_lab_result.json",
                                  "research/TRIALS_LEDGER.md", "research/selection_bias_ledger.py"],
            "note": "取代INVALID_BUG的#338~#344，純描述性比較，非alpha檢定",
        }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
