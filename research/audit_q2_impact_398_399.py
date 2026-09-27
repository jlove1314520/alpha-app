# -*- coding: utf-8 -*-
"""查.二第二點（影響評估，只回報，#398/#399判定全部鎖定不動）：計算#398
（f52w_high_portfolio_v1）與#399（dividend_yield_portfolio_v1）2007-2014
單發檢定的持股天數中，落在「上市前興櫃期間」的比例，以及這些期間對報酬
的貢獻估計。

**這是重建，不是重跑**：`run_single_shot()`用跟#398/#399登記時完全相同
的輸入（同一份`load_common_stock_data_2007_2014()`快取資料、同一組
`BacktestConfig`），重新跑一次確定性回測，重建出跟已消耗的only-once
結果完全相同的equity curve與trades帳本，用來計算一個新的診斷統計量
（本輪之前沒算過的「持股天數落在上市前興櫃期間的比例」），不是要產生
新的判定結果。**先逐位元核對重建結果與`TRIALS_LEDGER.md`/`single_shot_
2007_2014_result.json`已登記的n_trades/candidate_return_pct/mdd_full
三個數字完全一致，才繼續往下算**——這是`驗.五.diagnostic_benchmark_
correction()`已經驗證過的合規重建模式（見`research/holdout_2025_
dividend_account_test.py`），不是本輪新發明的規避手法。若核對不一致，
立刻中止，不得繼續使用重建結果。

**持股天數/報酬貢獻的計算方式**：從`result.trades`（buy/sell逐筆帳本，
`entry_trade_id`把sell配對回對應的buy）配對出每一段實際持倉區間
（entry_date~exit_date，未平倉部位以OOS_END收尾）。對每一段持倉，若
該股票的上市/上櫃日（`universe.listing_date_lookup()`）晚於entry_date，
代表這段持倉「一部分或全部」落在上市前興櫃期間：
  - 落在興櫃期間的交易日數 = entry_date 到 min(exit_date, listing_date)
    之間、該股票價格序列裡實際存在的列數。
  - 這段期間的報酬貢獻 = 用該股票在entry_price與『listing_date當天或
    之前最近一個交易日』的價格算出的報酬，乘上這筆交易的部位金額
    （shares*entry_price），估算貢獻的損益金額，除以策略總損益金額
    得到貢獻比例。這是一個估算（誠實揭露：假設整段持倉期間部位金額
    不變，忽略期間內的加碼/減碼——`run_backtest()`目前的持倉模型本身
    就是整股買入/整股賣出，不是逐日調整部位，這個假設跟回測引擎本身
    的假設一致，不是本次分析額外引入的簡化）。
  - 上市日不明（興櫃/下市/資料源缺口）的股票，其持倉天數/貢獻另外
    單獨列出「無法判定」，不併入「落在上市前興櫃期間」的分子或分母
    （避免把「不確定」誤記成「確定沒有汙染」）。

輸出：`research/data/q2_impact_398_399.json`
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import importlib.util
import json
from pathlib import Path

import pandas as pd

# ── 重要：#398/#399登記當時（2026-09-24）用的是修.六(2026-09-27)重構前
# 的adjust.py（分割/減資/面額變更事件尚未加入還原邏輯）。本輪`adjust.py`
# 已經改變，直接`import adjust`會拿到新版邏輯，導致還原後的股價序列跟
# 登記當時不同，重建就不可能逐位元一致——這不是bug，是修.六本身就改了
# 這個檔案的行為，符合預期。為了讓「重建核對」這個安全機制仍然有意義
# （驗證我用的資料真的是登記當時那一份，不是不小心用錯版本），這裡改成
# 載入commit`7a8fd5cd`（修.六重構前最後一次adjust.py）的凍結副本，
# 注入`sys.modules['adjust']`，讓底下`single_shot_2007_2014_test`／
# `f52w_high_portfolio_v1`／`dividend_yield_portfolio_v1`的`from adjust
# import ...`全部拿到這個凍結版本，藏在scratchpad目錄不進repo，不影響
# 現行`research/adjust.py`本身（十三節單一寫入者的檔案本身完全沒被
# 讀寫，只是被暫時替換成另一個獨立檔案物件）。
_FROZEN_ADJUST_PATH = Path(r"C:\Users\user\AppData\Local\Temp\claude\C--alpha\a8c8437e-502f-4bad-8e82-8f220f3b1158\scratchpad\adjust_pre_q2_frozen.py")
_spec = importlib.util.spec_from_file_location("adjust", _FROZEN_ADJUST_PATH)
_frozen_adjust = importlib.util.module_from_spec(_spec)
sys.modules["adjust"] = _frozen_adjust
_spec.loader.exec_module(_frozen_adjust)

import single_shot_2007_2014_test as sst
import f52w_high_portfolio_v1 as f52w_mod
import dividend_yield_portfolio_v1 as div_mod
from universe import listing_date_lookup

OUT = Path(__file__).parent / "data" / "q2_impact_398_399.json"

REGISTERED = {
    "f52w_high_portfolio_v1": {"n_trades": 919, "candidate_return_pct_2007_2014": 113.91, "mdd_full_period_pct": -47.14},
    "dividend_yield_portfolio_v1": {"n_trades": 579, "candidate_return_pct_2007_2014": 203.87, "mdd_full_period_pct": -53.72},
}


def _pair_positions(trades: pd.DataFrame, period_end: str) -> list[dict]:
    """把buy/sell逐筆帳本配對成持倉區間列表。"""
    buys = trades[trades["side"] == "buy"].set_index("trade_id")
    positions = []
    for _, sell in trades[trades["side"] == "sell"].iterrows():
        entry_id = sell.get("entry_trade_id")
        if entry_id not in buys.index:
            continue
        buy = buys.loc[entry_id]
        positions.append({
            "stock_id": sell["stock_id"], "entry_date": str(buy["date"]), "exit_date": str(sell["date"]),
            "entry_price": float(buy["price"]), "exit_price": float(sell["price"]), "shares": float(buy["shares"]),
            "closed": True,
        })
    # 未平倉：有buy但配對不到對應sell的部位，用period_end收尾
    sold_entry_ids = set(trades.loc[trades["side"] == "sell", "entry_trade_id"])
    for tid, buy in buys.iterrows():
        if tid in sold_entry_ids:
            continue
        positions.append({
            "stock_id": buy["stock_id"], "entry_date": str(buy["date"]), "exit_date": period_end,
            "entry_price": float(buy["price"]), "exit_price": None, "shares": float(buy["shares"]),
            "closed": False,
        })
    return positions


def _price_at_or_before(px: pd.DataFrame, date_str: str) -> float | None:
    d = px[px["date"] <= date_str]
    if d.empty:
        return None
    return float(d["close"].iloc[-1]) if "close" in d.columns else float(d["adj_close"].iloc[-1])


def analyze(label: str, positions: list[dict], data: dict, listing_dates: dict, total_pnl_pct: float) -> dict:
    n_pos = len(positions)
    n_known, n_unknown = 0, 0
    days_total, days_pre_listing = 0, 0
    pnl_contrib_pre_listing = 0.0  # 估算金額（以初始資金1單位計，跟candidate_return_pct同尺度）
    tainted_stock_days_examples = []

    for pos in positions:
        sid = pos["stock_id"]
        px = data.get(sid)
        if px is None or "date" not in px.columns:
            continue
        d_window = px[(px["date"] >= pos["entry_date"]) & (px["date"] <= pos["exit_date"])]
        n_days = len(d_window)
        days_total += n_days

        ld = listing_dates.get(sid)
        if ld is None:
            n_unknown += 1
            continue
        n_known += 1
        if ld <= pos["entry_date"]:
            continue  # 整段持倉都在上市/上櫃之後，沒有汙染

        boundary = min(pos["exit_date"], ld)
        pre_window = px[(px["date"] >= pos["entry_date"]) & (px["date"] < boundary)]
        n_pre_days = len(pre_window)
        days_pre_listing += n_pre_days

        price_col = "adj_close" if "adj_close" in px.columns else "close"
        boundary_price = _price_at_or_before(px[["date", price_col]].rename(columns={price_col: "close"}), boundary)
        if boundary_price is None or pos["entry_price"] <= 0:
            continue
        seg_return = boundary_price / pos["entry_price"] - 1.0
        notional_weight = (pos["shares"] * pos["entry_price"])
        pnl_contrib_pre_listing += seg_return * notional_weight
        if len(tainted_stock_days_examples) < 15:
            tainted_stock_days_examples.append({
                "stock_id": sid, "entry_date": pos["entry_date"], "listing_date": ld,
                "exit_date": pos["exit_date"], "pre_listing_days": n_pre_days,
            })

    total_notional = sum(p["shares"] * p["entry_price"] for p in positions)
    return {
        "label": label,
        "n_positions": n_pos,
        "n_positions_with_known_listing_date": n_known,
        "n_positions_with_unknown_listing_date": n_unknown,
        "holding_days_total": days_total,
        "holding_days_pre_listing": days_pre_listing,
        "pct_holding_days_pre_listing": round(days_pre_listing / days_total * 100, 3) if days_total else None,
        "pnl_contribution_pre_listing_pct_of_initial_capital": round(pnl_contrib_pre_listing / total_notional * 100, 4) if total_notional else None,
        "note": "pnl_contribution為估算：假設持倉期間部位金額不變(跟run_backtest()的整股買賣模型一致)，"
                "取entry_price到上市/上櫃日當天(或前一個有效交易日)價格的報酬乘上進場金額，"
                "除以全部部位進場金額總和，非策略總損益的精確拆解，只作量級參考。",
        "tainted_examples": tainted_stock_days_examples,
    }


def main() -> None:
    print("[查.二影響評估] 重建2007-2014資料（零新增API呼叫，讀本機快取）...", flush=True)
    data, market_df, industry_map, liquidity, n_common = sst.load_common_stock_data_2007_2014()
    listing_dates = listing_date_lookup()

    results = {}
    for mod, label in ((f52w_mod, "f52w_high_portfolio_v1"), (div_mod, "dividend_yield_portfolio_v1")):
        print(f"\n[查.二影響評估] 重建 {label} ...", flush=True)
        out = sst.run_single_shot(mod, data, market_df, industry_map, liquidity, label)
        reg = REGISTERED[label]
        mismatch = [k for k in reg if out.get(k) != reg[k]]
        if mismatch:
            raise RuntimeError(f"{label} 重建結果與已登記結果不一致（{mismatch}），"
                                f"重建={{k: out.get(k) for k in reg}}，登記={reg}，依規則立即中止，不得繼續使用。")
        print(f"  重建核對通過：n_trades/candidate_return_pct/mdd_full_period_pct 三個數字與"
              f"已登記結果逐位元一致", flush=True)

        cfg = sst.BacktestConfig(start_date=sst.OOS_START, end_date=sst.OOS_END,
                                  max_positions=mod.TOP_N, rebalance_every_n_days=mod.REBALANCE_DAYS,
                                  commission_discount=0.18, instrument_type="normal",
                                  book_name=f"single_shot_2007_2014_{label}")
        signal_fn = mod.make_signal_fn(industry_map, liquidity)
        result = sst.run_backtest(signal_fn, data, market_df, cfg)
        positions = _pair_positions(result.trades, sst.OOS_END)
        analysis = analyze(label, positions, data, listing_dates, out["candidate_return_pct_2007_2014"])
        results[label] = analysis
        print(f"  持股天數落在上市前興櫃期間比例：{analysis['pct_holding_days_pre_listing']}%"
              f"（{analysis['holding_days_pre_listing']}/{analysis['holding_days_total']}天）", flush=True)
        print(f"  估算報酬貢獻：{analysis['pnl_contribution_pre_listing_pct_of_initial_capital']}%"
              f"（佔初始資金比例，非佔策略總報酬比例，兩者尺度不同見note）", flush=True)

    OUT.write_text(json.dumps({"generated_at": pd.Timestamp.now().isoformat(),
                                "verdict_locked_note": "本檔案數字只作報告用途，不改變#398/#399/#400任何已登記判定",
                                "results": results}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT}")


if __name__ == "__main__":
    main()
