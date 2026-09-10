"""台股被動基準候選（`PENDING_QUEUE.md` 深讀二.1，Cybex 深讀補充裁示【裁示二】第1點）。

**為什麼要造這個**：`CLAUDE.md` 新增的第 8 關（被動基準對照）要求每個主動候選都要贏過
一個「固定小倉位持有大盤代理標的」的被動基準，才算真的有 alpha——單純跟零成本買進
持有比，或跟隨機選股控制組比，都不能回答「這個複雜的主動策略，真的贏得過一個什麼都
不用做、只是放著一小筆錢在 0050 上」這個更基本的問題。Cybex 那邊（加密貨幣專案）第
49 輪的完整通過候選正是這個形狀：固定小倉位被動持有最大市值標的，第 52/54 輪還證明
分散化跟主動輪動都更差。這裡是台股版的第一次落地。

**「誠實引擎」是什麼意思，跟隨便寫一個報酬公式有什麼不同**：
1. **真實權重漂移**：只在每次再平衡當天才交易，兩次再平衡之間完全不動，讓 0050 的
   持股權重隨價格自然漂移（漲了權重變高、跌了權重變低）——不是每天偷偷把權重拉回
   target_w（那是免費連續再平衡的幻覺，現實中每天調倉的手續費會吃光報酬）。
2. **再平衡照實收成本**：每次再平衡只對「實際交易的差額」（把權重拉回 target_w 需要
   買/賣多少）收費，用 `backtest/engine.py` 的 `buy_leg_rate()`/`sell_leg_rate()`
   （跟全專案其他策略同一套成本模型，不是另外發明一套）。
3. **現金部位不生息（刻意的保守簡化，非疏漏）**：(1-w) 留在現金的部分報酬率設 0%，
   不是台股實際可得的短期票券/定存利率。這個簡化**方向上對被動基準不利**（低估它的
   真實報酬），所以不會讓「主動策略打贏被動基準」這件事變得比實際情況更容易——
   是保守假設，不是討好基準的假設。

**標的選擇**：用 0050（元大台灣50 ETF）而不是 TAIEX 期貨多單——0050 的
`adjust.adjusted_price_series()` 已經把配息還原回股價序列（total-return-like），
台指期則需要另外處理逐月轉倉的基差成本（`research/continuous_contract.py`），
兩者都是裁示允許的選項，這裡先做 0050 版本，期貨版本留待後續需要時再補。

**holdout 紀律**：資料一律走 `adjust.adjusted_price_series()`（底層用
`finmind_client.load_dev()`，硬性截在 `VAL_END`），TRAIN/VAL 切分用
`validation.holdout.cap_to_train()`/`validation_slice()`，每次模擬結束後對
equity curve 額外呼叫一次 `assert_no_holdout_leakage()`。

執行方式：
    python passive_benchmark_tw_v1.py --self-test   # 不碰網路，驗證引擎邏輯本身
    python passive_benchmark_tw_v1.py --run          # 抓 0050 真實資料，掃 w 網格
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, BacktestResult, buy_leg_rate, sell_leg_rate
from validation import holdout

STOCK_ID = "0050"
REBALANCE_DAYS = 21  # 月頻，跟本專案其餘 portfolio 層構造（#4/#3/#17/#36/#30）同一個節奏，
# 方便日後拿來當這些候選的第 8 關對照組時基準一致，不是隨便選的數字。
W_GRID = [round(0.08 + 0.02 * i, 2) for i in range(12)]  # 0.08, 0.10, ..., 0.30，12 個點
OUT_PATH = RESEARCH_DIR / "data" / "passive_benchmark_tw_v1_result.json"


def simulate(prices: pd.DataFrame, target_w: float, *, rebalance_every_n_days: int = REBALANCE_DAYS,
             initial_capital: float = 1_000_000.0, cost_multiplier: float = 1.0) -> BacktestResult:
    """真實權重漂移＋定期再平衡照實收成本的被動曝險模擬。

    `prices` 必須已排序、含 `date`/`adj_close` 欄位，且已經過 holdout 裁切。
    """
    df = prices.sort_values("date").reset_index(drop=True)
    if df.empty:
        raise ValueError("simulate(): empty price series")
    cfg = BacktestConfig(start_date=str(df["date"].iloc[0]), end_date=str(df["date"].iloc[-1]),
                          initial_capital=initial_capital, cost_multiplier=cost_multiplier,
                          book_name="passive_benchmark_tw_v1")
    buy_rate = buy_leg_rate(cfg)
    sell_rate = sell_leg_rate(cfg)

    cash = initial_capital
    shares = 0.0
    trades: list[dict] = []
    equity_rows: list[dict] = []

    for i, row in df.iterrows():
        price = float(row["adj_close"])
        date = str(row["date"])
        is_rebalance_day = (i == 0) or (i % rebalance_every_n_days == 0)
        if is_rebalance_day:
            current_value = cash + shares * price
            current_holding_value = shares * price
            target_holding_value = current_value * target_w
            delta = target_holding_value - current_holding_value
            # 差額太小（<0.05%淨值）不交易——真實世界不會為了幾塊錢的權重誤差去下單，
            # 這個容忍帶避免每次再平衡日都無意義地產生一筆極小交易吃手續費。
            if abs(delta) > current_value * 0.0005:
                if delta > 0:
                    cost = delta * buy_rate
                    shares += delta / price
                    cash -= (delta + cost)
                    trades.append({"date": date, "side": "buy", "notional": delta, "cost": cost})
                else:
                    sell_notional = -delta
                    cost = sell_notional * sell_rate
                    shares -= sell_notional / price
                    cash += (sell_notional - cost)
                    trades.append({"date": date, "side": "sell", "notional": sell_notional, "cost": cost})
        equity_rows.append({"date": date, "equity": cash + shares * price})

    equity_curve = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(columns=["date", "side", "notional", "cost"])
    holdout.assert_no_holdout_leakage(equity_curve, context=f"passive_benchmark_tw_v1 w={target_w}")
    return BacktestResult(equity_curve=equity_curve, trades=trades_df, config=cfg)


# ---------------------------------------------------------------- self-test

def _synthetic_prices(n_days: int = 300, seed: int = 20260910) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-05", periods=n_days).strftime("%Y-%m-%d").tolist()
    rets = rng.normal(0.0004, 0.01, n_days)
    prices = 100.0 * np.cumprod(1 + rets)
    return pd.DataFrame({"date": dates, "adj_close": prices})


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    flat = pd.DataFrame({"date": pd.bdate_range("2015-01-05", periods=100).strftime("%Y-%m-%d"),
                          "adj_close": [100.0] * 100})
    res = simulate(flat, target_w=0.20, cost_multiplier=1.0)
    # 1. 價格完全不動：只有第一天的建倉交易，之後任何一次「再平衡」權重都沒漂移，
    #    不應該產生新交易（差額為0，低於容忍帶）。
    check("平盤價格只有初始建倉一筆交易", len(res.trades) == 1, f"{len(res.trades)} 筆")
    # 2. 平盤下唯一的成本是初始建倉的買進成本，權益應該等於 initial_capital - 建倉成本。
    buy_rate = buy_leg_rate(res.config)
    expected_cost = 1_000_000.0 * 0.20 * buy_rate
    expected_final = 1_000_000.0 - expected_cost
    check("平盤下最終權益＝初始資金－建倉成本（無其他損耗）",
          abs(res.final_equity - expected_final) < 1e-6,
          f"{res.final_equity:.4f} vs {expected_final:.4f}")

    # 3. w=0：完全不持有 0050，權益應該永遠等於初始資金（沒有任何交易，因為 target=0
    #    跟 current=0 一開始就相等，delta=0）。
    res0 = simulate(_synthetic_prices(120), target_w=0.0)
    check("w=0 時完全不交易、權益不變", len(res0.trades) == 0 and abs(res0.final_equity - 1_000_000.0) < 1e-6,
          f"{len(res0.trades)} 筆交易，final={res0.final_equity:.2f}")

    # 4. 漲勢下權重應該自然漂移升高（真實漂移而非每天拉回），下一次再平衡才會賣出部分部位。
    up = pd.DataFrame({"date": pd.bdate_range("2015-01-05", periods=50).strftime("%Y-%m-%d"),
                        "adj_close": [100.0 * (1.01 ** i) for i in range(50)]})
    res_up = simulate(up, target_w=0.20, rebalance_every_n_days=21)
    sells = [t for t in res_up.trades.to_dict("records") if t.get("side") == "sell"]
    check("持續上漲時，第一次再平衡（第21天）應該賣出部分部位讓權重回到target",
          len(sells) >= 1, f"{len(sells)} 筆賣出交易，共 {len(res_up.trades)} 筆交易")

    # 5. 高成本乘數應該嚴格拉低最終權益（cost_multiplier 3x vs 1x）。
    res_1x = simulate(_synthetic_prices(300), target_w=0.20, cost_multiplier=1.0)
    res_3x = simulate(_synthetic_prices(300), target_w=0.20, cost_multiplier=3.0)
    check("cost_multiplier=3x 最終權益嚴格低於 1x（成本真的有作用）",
          res_3x.final_equity < res_1x.final_equity,
          f"1x={res_1x.final_equity:.2f} vs 3x={res_3x.final_equity:.2f}")

    # 6. 空序列要拋錯，不能安靜回傳假結果。
    try:
        simulate(pd.DataFrame(columns=["date", "adj_close"]), target_w=0.2)
        check("空價格序列必須拋錯", False, "沒有拋錯")
    except ValueError:
        check("空價格序列必須拋錯", True)

    print(f"\n=== self-test {'全部通過' if not failures else f'{len(failures)} 項 FAIL'} ===")
    return 0 if not failures else 1


# ---------------------------------------------------------------- 實跑

def run() -> int:
    from adjust import adjusted_price_series

    print(f"載入 {STOCK_ID} 調整後價格序列（holdout 硬性截在 VAL_END）...")
    raw = adjusted_price_series(STOCK_ID, "2003-01-01")
    if raw.empty or "adj_close" not in raw.columns:
        print(f"！{STOCK_ID} 拿不到可用的調整後價格序列，無法進行模擬")
        return 2
    raw = raw.dropna(subset=["adj_close"]).sort_values("date").reset_index(drop=True)
    holdout.assert_no_holdout_leakage(raw, context="passive_benchmark_tw_v1 raw 0050 series")
    print(f"  {len(raw)} 個交易日，{raw['date'].iloc[0]} ~ {raw['date'].iloc[-1]}")

    train = holdout.cap_to_train(raw)
    val = holdout.validation_slice(raw)
    print(f"  TRAIN {len(train)} 天（<= {holdout.TRAIN_END}）、VAL {len(val)} 天"
          f"（{holdout.TRAIN_END} ~ {holdout.VAL_END}）")

    results: dict[str, dict] = {"stock_id": STOCK_ID, "rebalance_days": REBALANCE_DAYS,
                                 "w_grid": W_GRID, "train_end": holdout.TRAIN_END, "val_end": holdout.VAL_END,
                                 "n_days": {"train": len(train), "val": len(val)}, "phases": {}}
    for label, sub in (("TRAIN", train), ("VAL", val)):
        if len(sub) < REBALANCE_DAYS * 2:
            print(f"  {label} 資料不足兩個再平衡週期，跳過")
            continue
        rows = {}
        for w in W_GRID:
            res = simulate(sub, target_w=w)
            rows[str(w)] = {
                "return_pct": res.total_return_pct,
                "mdd_pct": res.max_drawdown_pct,
                "sortino": res.sortino_ratio,
                "n_trades": res.n_trades,
            }
            print(f"  {label} w={w:.2f}: 報酬={res.total_return_pct:+7.2f}%  "
                  f"MDD={res.max_drawdown_pct:7.2f}%  Sortino={res.sortino_ratio:.3f}  "
                  f"trades={res.n_trades}")
        results["phases"][label] = rows

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n結果寫入 {OUT_PATH.relative_to(RESEARCH_DIR)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.run:
        return run()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
