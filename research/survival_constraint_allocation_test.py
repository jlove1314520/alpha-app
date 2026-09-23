"""天條一.1：永久性降曝險 vs 擇時降曝險（`PENDING_QUEUE.md`「2026-09-19
【總司令裁示·三條天條】」第二點）。

背景：擇時降曝險已七次全FAIL結案（regime overlay家族），但天條一
（MDD不得超過50%）仍須達成，而TAIEX 2008年跌幅代表買0050並持有本身
就違反天條一。剩下的可行路徑是不擇時的永久性降曝險——固定股債比、
不看訊號、沒有擇時成本、沒有換手、對MDD的削減是確定的（結構性，
不是統計上可能被雜訊推翻的「訊號」）。

目的**不是找最佳比例**，是量出「滿足天條一的最低代價是多少報酬」，
那個數字直接餵給`CORE_TILT_SPEC.md`第0節當選股alpha的目標值。

**[自行裁量]資料來源選擇，一個重要的資料缺口修正**：`adjust.
adjusted_price_series("0050")`預設先試yfinance，但實測yfinance對
0050.TW的涵蓋範圍只從2009-01-02開始（0050實際2003-06-30才上市），
**這會讓2008金融海嘯——天條一.1最需要驗證的那個崩盤——完全測不到**。
本腳本改為直接呼叫FinMind手動還原權息的路徑（`adjust.adjustment_
events()`+`finmind_client.load_dev()`），繞過yfinance，取得完整
2003-06-30起的還原股價序列，涵蓋2008年在內全部歷史空頭段。這不是
修改`adjust.py`本身（該檔案不動），是在本腳本內重現同一套FinMind
還原邏輯以取得更長歷史，理由與作法在此完整記錄以便稽核。

**債券/定存代理**：`cbc_rf_rate_client.load_risk_free_rate_series()`
（央行五大銀行「定存利率-一個月-固定」月頻算術平均，2001年起），
比照總司令原文「0050+台灣公債或定存代理」裡的定存選項——定存利率
比公債殖利率更保守（更低），用它當「債」的代理會**低估**固定收益
部位的報酬，方向上不會讓永久性降曝險的報酬缺口看起來比實際更小，
是保守假設。

**holdout紀律**：全程只到`VAL_END`（2024-12-31），不碰HOLDOUT，即使
這是「測量」不是「搜尋」（沒有可調的自由參數、四個配置事前寫死），
仍比照全專案零容忍holdout的紀律處理。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from adjust import adjustment_events
from finmind_client import load_dev
from cbc_rf_rate_client import load_risk_free_rate_series, rf_rate_for_date
from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate
from validation import holdout

REPO_ROOT = Path(__file__).resolve().parent.parent
STOCK_ID = "0050"
REBALANCE_DAYS = 21  # 月頻，跟passive_benchmark_tw_v1.py/#4/#3/#17/#36/#30同一個節奏
ALLOCATIONS = [1.00, 0.85, 0.70, 0.60]  # 0050權重；債/定存權重=1-w，事前鎖定，不得事後增格
TZ = timezone(timedelta(hours=8))

# 歷史空頭段清單（沿用REGIME_OVERLAY_PROTOCOL.md第2節既有定義，額外補回
# 2008——該協定受限於TAIEX資料起點2010-01-04測不到2008，但0050走FinMind
# 直接路徑可回溯到2003，天條一.1的目的正是要驗證2008，不能沿用同一個
# 資料限制略過它）。
BEAR_SEGMENTS = {
    "2008金融海嘯": ("2008-05-01", "2008-11-30"),
    "2011歐債危機": ("2011-07-01", "2011-12-31"),
    "2015中國股災": ("2015-06-01", "2015-09-30"),
    "2018Q4貿易戰": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}

MDD_SURVIVAL_THRESHOLD_PCT = -50.0  # 天條一硬約束
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"
OUT_MD = REPO_ROOT / "research" / "SURVIVAL_CONSTRAINT.md"
OUT_JSON = REPO_ROOT / "research" / "data" / "survival_constraint_allocation_test.json"


def load_0050_full_history() -> pd.DataFrame:
    """繞過yfinance，直接用FinMind手動還原權息路徑取得0050完整2003起歷史
    （見本檔docstring說明理由）。回傳欄位跟`adjust.adjusted_price_series()`
    相容：date/adj_close。"""
    raw = load_dev("TaiwanStockPrice", STOCK_ID, "2003-01-01")
    if raw.empty:
        raise RuntimeError(f"{STOCK_ID} FinMind原始價格為空，無法建立還原序列")
    raw = raw.sort_values("date").reset_index(drop=True)
    events = adjustment_events(STOCK_ID, "2003-01-01")
    factor_cum = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        mask = raw["date"] < ev["ex_date"]
        factor_cum.loc[mask] = factor_cum.loc[mask] * ev["factor"]
    out = raw.copy()
    out["adj_close"] = raw["close"].astype(float) * factor_cum
    out["date"] = pd.to_datetime(out["date"])
    out = out[out["date"] <= pd.Timestamp(holdout.VAL_END)].reset_index(drop=True)
    holdout.assert_no_holdout_leakage(out, context="survival_constraint 0050 full history")
    return out[["date", "adj_close"]]


def simulate_fixed_allocation(prices: pd.DataFrame, rf_monthly: pd.DataFrame, stock_w: float,
                               *, rebalance_every_n_days: int = REBALANCE_DAYS,
                               initial_capital: float = 1_000_000.0) -> pd.DataFrame:
    """固定股債比、真實權重漂移＋定期再平衡照實收成本（沿用
    `passive_benchmark_tw_v1.py::simulate()`同一套「誠實引擎」精神，這裡
    generalize成兩個都會生息/漲跌的資產，不是「股票+不生息現金」）。
    債券/定存部位用央行五大銀行定存利率月頻代理，逐日簡單複利
    （`(1+年化率%/100)^(1/252)-1`），不是連續複利也不是完全不生息。
    """
    df = prices.sort_values("date").reset_index(drop=True)
    # 2026-09-23修.二修正：股票部位交易標的是0050（股票型ETF），賣出證交稅率
    # 應為0.1%（instrument_type="etf"），原本用BacktestConfig預設"normal"
    # （一般股票0.3%）——見PENDING_QUEUE.md修.二完整清單。
    cfg = BacktestConfig(start_date=str(df["date"].iloc[0].date()), end_date=str(df["date"].iloc[-1].date()),
                          initial_capital=initial_capital, cost_multiplier=1.0,
                          book_name="survival_constraint_allocation_test", instrument_type="etf")
    buy_rate = buy_leg_rate(cfg)
    sell_rate = sell_leg_rate(cfg)

    stock_value = initial_capital * stock_w
    bond_value = initial_capital * (1 - stock_w)
    rows = []
    prev_price = None
    for i, row in df.iterrows():
        price = float(row["adj_close"])
        date = row["date"]
        if prev_price is not None:
            stock_value *= price / prev_price
        rf_pct = rf_rate_for_date(date, rf_monthly)
        bond_daily_ret = (1.0 + rf_pct / 100.0) ** (1.0 / 252.0) - 1.0
        bond_value *= (1.0 + bond_daily_ret)
        prev_price = price

        is_rebalance_day = (i == 0) or (i % rebalance_every_n_days == 0)
        if is_rebalance_day and stock_w not in (0.0, 1.0):
            total = stock_value + bond_value
            target_stock = total * stock_w
            delta = target_stock - stock_value
            if abs(delta) > total * 0.0005:
                if delta > 0:
                    cost = delta * buy_rate
                    stock_value += delta
                    bond_value -= (delta + cost)
                else:
                    sell_notional = -delta
                    cost = sell_notional * sell_rate
                    stock_value -= sell_notional
                    bond_value += (sell_notional - cost)
        rows.append({"date": date, "equity": stock_value + bond_value})

    equity_curve = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(equity_curve, context=f"survival_constraint w={stock_w}")
    return equity_curve


def compute_mdd(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min() * 100)


def segment_mdd(equity_curve: pd.DataFrame, start: str, end: str) -> float | None:
    w = equity_curve[(equity_curve["date"] >= start) & (equity_curve["date"] <= end)]
    if w.empty:
        return None
    # 用段內起點前最近一筆的權益值當基準峰值，避免段內第一天就被算成峰值
    # 而低估真實回撤（真正的峰值可能發生在空頭段開始前）。
    pre = equity_curve[equity_curve["date"] <= w["date"].iloc[0]]
    running_peak = pre["equity"].max() if not pre.empty else w["equity"].iloc[0]
    combined = pd.concat([pd.Series([running_peak]), w["equity"]], ignore_index=True)
    running_max = combined.cummax()
    dd = combined / running_max - 1.0
    return float(dd.min() * 100)


def main() -> None:
    print("[天條一.1] 載入0050完整歷史（繞過yfinance，取FinMind直接還原路徑）...")
    prices = load_0050_full_history()
    print(f"  範圍：{prices['date'].min().date()} ~ {prices['date'].max().date()}，n={len(prices)}天")
    rf_monthly = load_risk_free_rate_series()
    print(f"[天條一.1] 定存利率代理範圍：{rf_monthly['date'].min().date()} ~ {rf_monthly['date'].max().date()}")

    results = []
    for w in ALLOCATIONS:
        print(f"\n[天條一.1] 模擬配置 0050={w:.0%} / 定存={1-w:.0%} ...")
        eq = simulate_fixed_allocation(prices, rf_monthly, w)
        total_return_pct = float(eq["equity"].iloc[-1] / eq["equity"].iloc[0] - 1) * 100
        years = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days / 365.25
        cagr_pct = (float(eq["equity"].iloc[-1] / eq["equity"].iloc[0]) ** (1 / years) - 1) * 100
        overall_mdd = compute_mdd(eq["equity"])
        seg_mdds = {name: segment_mdd(eq, s, e) for name, (s, e) in BEAR_SEGMENTS.items()}
        worst_seg = min((v for v in seg_mdds.values() if v is not None), default=overall_mdd)
        survives_article1 = worst_seg >= MDD_SURVIVAL_THRESHOLD_PCT and overall_mdd >= MDD_SURVIVAL_THRESHOLD_PCT
        results.append({
            "stock_weight": w, "bond_weight": round(1 - w, 2),
            "total_return_pct": round(total_return_pct, 2), "cagr_pct": round(cagr_pct, 3),
            "overall_mdd_pct": round(overall_mdd, 2), "worst_segment_mdd_pct": round(worst_seg, 2),
            "segment_mdds_pct": {k: (round(v, 2) if v is not None else None) for k, v in seg_mdds.items()},
            "survives_article1_mdd50": survives_article1,
        })
        print(f"  CAGR={cagr_pct:.2f}%  全期MDD={overall_mdd:.2f}%  最差空頭段MDD={worst_seg:.2f}%  "
              f"天條一={'PASS' if survives_article1 else 'VIOLATES_SURVIVAL'}")

    base_cagr = results[0]["cagr_pct"]  # 100/0（純0050）當基準
    for r in results:
        r["cagr_gap_vs_100pct_stock_pct"] = round(base_cagr - r["cagr_pct"], 3)

    out = {"generated_at": datetime.now(TZ).isoformat(), "allocations_tested": ALLOCATIONS,
           "mdd_survival_threshold_pct": MDD_SURVIVAL_THRESHOLD_PCT,
           "data_source_note": "0050繞過yfinance(僅涵蓋2009起)，直接用FinMind還原權息路徑取得2003-06-30起完整歷史，涵蓋2008金融海嘯",
           "bond_proxy": "央行五大銀行定存利率-一個月-固定，月頻算術平均（保守假設，低估真實固定收益報酬）",
           "results": results}
    OUT_JSON.parent.mkdir(exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("[天條一.1] 總結表")
    print("=" * 80)
    for r in results:
        print(f"  0050={r['stock_weight']:.0%}/定存={r['bond_weight']:.0%}: "
              f"CAGR={r['cagr_pct']:.2f}%  全期MDD={r['overall_mdd_pct']:.2f}%  "
              f"最差空頭段MDD={r['worst_segment_mdd_pct']:.2f}%  "
              f"天條一={'PASS' if r['survives_article1_mdd50'] else 'VIOLATES_SURVIVAL'}  "
              f"報酬缺口={r['cagr_gap_vs_100pct_stock_pct']:+.2f}pp/年")

    with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(TZ).isoformat(), "item": "天條一.1",
            "note": "永久性降曝險四格配置測試完成，見research/SURVIVAL_CONSTRAINT.md",
        }, ensure_ascii=False) + "\n")
    print(f"\n[天條一.1] 心跳已寫入 {HEARTBEAT_PATH}")
    print(f"[天條一.1] 完整結果已寫入 {OUT_JSON}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
