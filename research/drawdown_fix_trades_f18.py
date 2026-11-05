# -*- coding: utf-8 -*-
"""先.一五二-1d F18 零股委託簿失衡度組合：個股層回撤歸因（① 從引擎重跑最優格取 trades）。樣本內描述性，不是判定。

最優格 21_-1_30_0.15（換股 21 日、方向 −1＝高失衡、前 30 檔、個股停損 15%），宇宙／資料同
`reaudit_optimized_batch2_oddlot.py`（factor_ic 抽樣＋load_sample_with_factors 本機快取、score.load_industry_map），
引擎只呼叫不改；歸因函式沿用 `drawdown_fix_trades.attribution()`。產出 research/data/drawdown_fix/trades_F18.json。
零外部請求（只讀本機快取）；資料到 2024-12-31，holdout 未讀。非投資建議。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drawdown_fix_trades as T  # noqa: E402
from drawdown_fix_trades import D, W  # noqa: E402
import reaudit_optimized_batch2_oddlot as OD  # noqa: E402
from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from validation import holdout  # noqa: E402


def main():
    t0 = time.time()
    F = D.load_family("F18")
    stop0 = None if F["stop"] is None or F["stop"] != F["stop"] else float(F["stop"])
    market_raw = OD.load_dev("TaiwanStockPrice", "TAIEX", OD.START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="ddfix F18 market")
    market_df = OD.prepare_market_data(market_raw)
    data = OD.load_sample_with_factors(OD.sample_universe_ids(OD.SAMPLE_SIZE, OD.SAMPLE_SEED), market_df)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"ddfix F18 {sid}")
    industry_map = OD.load_industry_map()
    liquidity = {sid: OD.pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    W.prog(f"F18 資料載入 {len(data)} 檔（{time.time()-t0:.0f}s）")
    cfg = BacktestConfig(start_date=OD.START, end_date=OD.END, max_positions=30, rebalance_every_n_days=21,
                         stop_loss_pct=0.15, book_name="ddfix_oddlot")
    bt = run_backtest(OD.make_fn(industry_map, liquidity, -1, 30), data, market_df, cfg)
    holdout.assert_no_holdout_leakage(bt.trades, date_col="date", context="ddfix F18 trades")
    ec = bt.equity_curve
    dates = pd.to_datetime(ec["date"]).reset_index(drop=True)
    eq = ec["equity"].to_numpy(float)
    r = np.zeros(len(eq))
    r[1:] = eq[1:] / eq[:-1] - 1.0
    rf = D.LB.load_tw_rf_daily(dates)
    cur, _ = D.overlay(r, rf, np.full(len(r), F["L"]), stop0)
    cg, md, sh = D.stats(cur, dates)
    T.TOP_N = 30
    ind = T.industry_map()
    for k, v in (industry_map or {}).items():  # score.load_industry_map 優先補空缺
        ind.setdefault(str(k), v)
    item = {"secs": round(time.time() - t0), "n_trades": int(len(bt.trades)),
            "reproduced": abs(cg - F["cagr0"]) < 0.002 and abs(md - F["mdd0"]) < 0.002,
            "at_orig": {"L": F["L"], "stop": stop0, "cagr": cg, "mdd": md, "sharpe": sh},
            "attribution": T.attribution(bt.trades, data, dates, eq, cur, ind)}
    (D.OUT_DIR / "trades_F18.json").write_text(json.dumps({"base": item}, ensure_ascii=False, indent=1, default=float),
                                              encoding="utf-8")
    W.prog(f"F18 完成（{item['secs']}s）：年化 {cg:+.2%}／MDD {md:.2%}，重建 {'對上' if item['reproduced'] else '對不上'}")


if __name__ == "__main__":
    main()
