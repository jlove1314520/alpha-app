# -*- coding: utf-8 -*-
"""資料.一（總司令2026-09-23裁示【DSR單位錯誤修正＋f52w改用資訊比率
重審＋2008延伸】核准執行）：f52w樣本延伸到2007年，涵蓋2008年金融
海嘯，讓天條一(MDD<=50%)能被實測。

設計（執行前凍結，跟f52w現有TRAIN=2015-2020/VAL=2021-2024完全獨立）：
- 樣本沿用`factor_ic.sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)`
  同一組300檔stock_id——`universe.universe()`本身已是survivorship-
  bias-mitigated(合併2003年至今的active+delisted，見universe.py)，
  跟日期範圍無關，同一組seed在任何時候呼叫都是同一份候選池，所以
  「延伸樣本」不需要重新抽樣，只需要對同一批stock_id抓更久的價格
  歷史——**這正是「延伸後的樣本必須包含2007-2008年間下市的股票，
  不得存活者偏差」這條要求已經被universe()滿足的證據，不是另外
  新增的機制**。
- 價格歷史起點=2006-01-01（f_52w_high_prox需要252交易日回看視窗，
  2007-01-01往前推252個交易日落在2006年上半年，抓整個2006年當緩衝）。
- 新樣本外期間=2007-01-01~2014-12-31（在既有TRAIN=2015起之前，不重疊，
  不會污染既有TRAIN/VAL），只跑一次，參數完全沿用f52w_high_portfolio_
  v1.py既有值（TOP_N=20/REBALANCE_DAYS=21），不得調整。
- 只用官方API（FinMind，`finmind_client.py`既有節流機制），遇到402/
  配額上限時`finmind_client._fetch()`會拋RuntimeError並把來源標記
  封鎖（`RATE_LIMIT_BLOCK_SECONDS=2小時`）——這裡在每檔股票的抓取
  外包一層try/except，遇到就停在斷點、把已完成的存進checkpoint，
  下次重跑`finmind_client.py`本身的parquet快取會讓已抓到的不必重抓，
  不繞過節流機制。

用法：python research/f52w_2007_extension.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids, prepare_factors
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

import portfolio_backtest_v2 as pbv2
from f52w_high_portfolio_v1 import TOP_N, REBALANCE_DAYS, make_signal_fn

EXTENDED_START = "2006-01-01"
OOS_START, OOS_END = "2007-01-01", "2014-12-31"
CHECKPOINT_PATH = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"
RESULT_JSON = Path(__file__).parent / "data" / "f52w_2007_extension_result.json"


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"fetched_ids": [], "failed_ids": {}}


def _save_checkpoint(ckpt: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(ckpt, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_extended_sample(sample_ids: list[str], market_df: pd.DataFrame) -> tuple[dict, dict]:
    """回傳(data, meta)。data是{stock_id: factor_df}，meta記錄成功/失敗/
    是否因額度中斷。中斷時data只含已完成的，呼叫端可以判斷是否要繼續
    往下跑（不足量就先誠實回報，不強行湊數）。"""
    ckpt = _load_checkpoint()
    data: dict[str, pd.DataFrame] = {}
    rate_limited = False
    for i, sid in enumerate(sample_ids):
        if sid in ckpt["fetched_ids"]:
            continue  # 上次已經跑過(成功或已知失敗都跳過重試，失敗原因見failed_ids)
        try:
            px = adjusted_price_series(sid, EXTENDED_START)
        except RuntimeError as e:
            msg = str(e)
            if "額度" in msg or "封鎖" in msg or "402" in msg or "429" in msg or "428" in msg:
                print(f"  [{i+1}/{len(sample_ids)}] {sid}: 命中額度/封鎖，停在斷點——{msg[:150]}", flush=True)
                rate_limited = True
                break
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: 價格抓取錯誤(非額度問題)，記為失敗跳過——{msg[:150]}", flush=True)
            ckpt["fetched_ids"].append(sid)
            ckpt["failed_ids"][sid] = msg[:200]
            continue
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: 未預期錯誤，記為失敗跳過——{e!r}", flush=True)
            ckpt["fetched_ids"].append(sid)
            ckpt["failed_ids"][sid] = repr(e)[:200]
            continue

        if px.empty or len(px) < 260:
            ckpt["fetched_ids"].append(sid)
            ckpt["failed_ids"][sid] = f"資料不足(len={len(px)})，2006年附近可能尚未上市或無資料"
            continue
        try:
            d = prepare_factors(sid, px, market_df, EXTENDED_START)
        except Exception as e:  # noqa: BLE001
            ckpt["fetched_ids"].append(sid)
            ckpt["failed_ids"][sid] = f"factor準備錯誤：{e!r}"[:200]
            continue

        data[sid] = d
        ckpt["fetched_ids"].append(sid)
        if (i + 1) % 20 == 0:
            _save_checkpoint(ckpt)
            print(f"  進度 {i+1}/{len(sample_ids)}（累計可用 {len(data)} 檔）", flush=True)

    _save_checkpoint(ckpt)
    meta = {
        "n_requested": len(sample_ids), "n_attempted": len(ckpt["fetched_ids"]),
        "n_failed": len(ckpt["failed_ids"]), "rate_limited": rate_limited,
    }
    return data, meta


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"樣本池 {len(sample_ids)} 檔（沿用SAMPLE_SEED={SAMPLE_SEED}，跟既有f52w分析同一組）", flush=True)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", EXTENDED_START)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in f52w_2007_extension")
    market_df = prepare_market_data(market_raw)

    print(f"開始抓取延伸價格歷史（起點{EXTENDED_START}）...", flush=True)
    data, meta = fetch_extended_sample(sample_ids, market_df)
    print(f"\n抓取完成：{json.dumps(meta, ensure_ascii=False)}", flush=True)

    if meta["rate_limited"]:
        print("\n**已命中FinMind額度/封鎖，停在斷點，不繞過**——"
              "重跑本腳本會用finmind_client.py的parquet快取續跑已完成部分，"
              "本次先不執行後續回測（資料不完整，跑出來的數字沒有意義）。", flush=True)
        RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
        RESULT_JSON.write_text(json.dumps({"status": "rate_limited", "meta": meta},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in f52w_2007_extension")

    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}
    n_usable = len(data)
    print(f"\n可用樣本 {n_usable}/{len(sample_ids)} 檔（延伸期間資料不足/未上市/抓取失敗的已排除，"
          f"詳見{CHECKPOINT_PATH.name}的failed_ids）", flush=True)

    signal_fn = make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=OOS_START, end_date=OOS_END, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="f52w_2007_extension_oos",
                          instrument_type="normal")
    result = run_backtest(signal_fn, data, market_df, cfg)

    alpha = pbv2.alpha_significance(result.equity_curve, market_df)
    bh_pct = pbv2.buy_and_hold_index_pct(market_df, OOS_START, OOS_END)

    eq = result.equity_curve.set_index("date")["equity"]
    yearly_return = {}
    for yr in range(2007, 2015):
        window = eq[(eq.index >= f"{yr}-01-01") & (eq.index <= f"{yr}-12-31")]
        if len(window) >= 2:
            yearly_return[yr] = float(window.iloc[-1] / window.iloc[0] - 1) * 100

    print(f"\n=== 2007-2014新樣本外結果（TOP_N={TOP_N}/REBALANCE_DAYS={REBALANCE_DAYS}，參數未調整）===", flush=True)
    print(f"  報酬={result.total_return_pct:+.2f}%  MDD={result.max_drawdown_pct:.2f}%  "
          f"Sortino={result.sortino_ratio:.3f}  trades={result.n_trades}", flush=True)
    print(f"  alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta_dimson={alpha['beta']:+.3f}  "
          f"p={alpha['alpha_pvalue']:.4f}  大盤(0050含息)={bh_pct:+.2f}%", flush=True)
    print(f"  逐年報酬：{yearly_return}", flush=True)
    print(f"  **天條一檢驗（MDD<=50%）**：{'PASS' if result.max_drawdown_pct > -50.0 else 'FAIL'}"
          f"（MDD={result.max_drawdown_pct:.2f}%）", flush=True)

    out = {
        "n_usable": n_usable, "n_requested": len(sample_ids),
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "n_trades": result.n_trades,
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta_dimson": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "buy_and_hold_index_pct": bh_pct,
        "yearly_return_pct": yearly_return, "tiantiao1_pass": bool(result.max_drawdown_pct > -50.0),
        "oos_start": OOS_START, "oos_end": OOS_END, "meta": meta,
    }
    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {RESULT_JSON}", flush=True)


if __name__ == "__main__":
    main()
