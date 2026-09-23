# -*- coding: utf-8 -*-
"""驗.一（總司令2026-09-23裁示【三個方法缺陷＋E-c/E-d走正式閘門】）：
`backtest/engine.py`健全性測試組 S1-S4。

**根因**（Cowork讀碼確認）：`run_backtest()`L186
`slot_allocation = config.initial_capital / config.max_positions`只算
一次，L241每筆買進固定用這個額度成交，獲利/虧損不會反映到下一筆買進
的資金基礎——**引擎不複利，獲利留在零息現金**。跟會複利的0050總報酬
比較時，換手越高、被低估越嚴重。`concentrated_backtest.py`(#358)實測
隨機8檔2015-2024總報酬-84.55%、MDD-93.2%，這不是「框架跑得動、隨機
訊號本來就該難看」——隨機組合是虛無假說，理論上應該接近「等權重樣本
減成本」而不是這麼極端的負值，這正是不複利bug的直接後果（見S3/S4）。

**S1-S3任一項不過，就先修引擎，不得往下做**——本檔案先跑S1-S3，若
發現問題會在同一次執行裡先修好`compounding`旗標再繼續，不分兩次跑。

用法：
    python research/backtest_engine_soundness_test.py
"""
from __future__ import annotations

import json
import random
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

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map
from survival_constraint_allocation_test import load_0050_full_history
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = REPO_ROOT / "research" / "data" / "backtest_engine_soundness_test.json"

S1_TOLERANCE_PP = 0.1   # 裁示原文：S1年化差<0.1pp
S2_TOLERANCE_PP = 0.3   # 裁示原文：S2年化差<0.3pp
S3_N_SEEDS = 100
S3_MAX_POSITIONS = 8


def _add_synthetic_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """`load_0050_full_history()`只有date/adj_close，`run_backtest()`的
    漲跌停鎖判斷需要open/max/min/close。0050是ETF、實務上極少鎖漲跌停，
    這裡用adj_close填四欄（open=high=low=close=adj_close）純粹是為了讓
    S1能餵進引擎跑，不是宣稱這是真實日內價——這個簡化本身也在稽核範圍內
    誠實揭露，S1若異常需要回頭檢查是不是這個簡化造成的假鎖單。
    """
    out = df.copy()
    # run_backtest()的行事曆與內部索引一律用字串日期（跟market_df/
    # load_sample_with_factors()的既有慣例一致），load_0050_full_
    # history()回傳的是pd.Timestamp，這裡轉回字串避免"<"比較型別不符。
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    for col in ("open", "max", "min", "close"):
        out[col] = out["adj_close"]
    return out


def cagr_from_series(dates: pd.Series, values: pd.Series) -> float:
    dates = pd.to_datetime(dates)
    n_years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    total_return = values.iloc[-1] / values.iloc[0] - 1
    return (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else float("nan")


def run_s1() -> dict:
    """max_positions=1，只持有0050，不換股，risk-control三層全部關閉
    （MA-exit靠不給ma150欄位停用；stop_loss_pct=1.0等於不可能觸發），
    跟`load_0050_full_history()`的總報酬直接比CAGR。"""
    prices = load_0050_full_history()
    prices_ohlc = _add_synthetic_ohlc(prices)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2003-01-01")
    holdout.assert_no_holdout_leakage(market_raw, context="S1 market_raw")
    market_df = prepare_market_data(market_raw)

    start_date = prices["date"].iloc[0].strftime("%Y-%m-%d")
    end_date = holdout.VAL_END

    def signal_fn(price_data, as_of, mkt):
        return {"0050": 1.0}

    # rebalance_every_n_days=1（不用預設的rebalance_weekday=僅週五）：實測發現
    # 預設每週五才檢查訊號，會讓「唯一一次」進場延遲到第一個週五才成交
    # （2003-06-30起跑，實際成交日2003-07-07，價格從18.44漲到20.39，單這
    # 一週的進場延遲價差就佔掉約10%總報酬，跟複利bug是兩回事——複利bug
    # 需要「多筆」交易才會顯現，S1本來就設計成只有一筆交易，用週頻進場
    # 時機去測「複利對不對」會被進場時機本身的落差污染，不是在測本來要
    # 測的東西）。改用每日檢查，讓進場在T+1(第一個可能的交易日)就發生，
    # 才是乾淨隔離複利邏輯本身的比較基準。
    cfg = BacktestConfig(start_date=start_date, end_date=end_date, max_positions=1,
                          rebalance_every_n_days=1,
                          stop_loss_pct=1.0, commission_discount=1.0, slippage_bps=0.0, cost_multiplier=0.0,
                          instrument_type="etf", book_name="S1_single_0050")
    result = run_backtest(signal_fn, {"0050": prices_ohlc}, market_df, cfg)

    engine_cagr = cagr_from_series(result.equity_curve["date"], result.equity_curve["equity"])
    # 公平比較基準：直接算法要用引擎「實際」的進場日/進場價當起點，不是
    # 序列第0天——引擎有EXECUTION_LAG_DAYS=1的T+1成交設計（防未來函數，
    # 不是bug），2003-06-30當天訊號要到2003-07-01才能成交，這一天剛好
    # 有+2.6%的大單日漲幅，若拿day0價格當「直接算」的起點會製造一個
    # 假的落差（這不是複利邏輯的問題，是比較基準本身沒對齊）。
    entry_date = result.trades.iloc[0]["date"] if not result.trades.empty else start_date
    direct_slice = prices[prices["date"] >= entry_date]
    direct_cagr = cagr_from_series(direct_slice["date"], direct_slice["adj_close"])
    diff_pp = abs(engine_cagr - direct_cagr) * 100

    return {
        "engine_cagr_pct": round(engine_cagr * 100, 4), "direct_cagr_pct": round(direct_cagr * 100, 4),
        "diff_pp": round(diff_pp, 4), "tolerance_pp": S1_TOLERANCE_PP,
        "passed": bool(diff_pp < S1_TOLERANCE_PP), "n_trades": result.n_trades,
        "start_date": start_date, "end_date": end_date, "actual_entry_date": str(entry_date),
    }


def run_s2(data: dict, market_df: pd.DataFrame):
    """樣本全體等權重、月頻(21交易日)再平衡，跟pandas直接算的等權重
    報酬比。引擎路徑：signal_fn對全部樣本回傳相同分數，max_positions=
    len(data)（全部都進場），rebalance_every_n_days=21。直接路徑：
    對每一檔算逐日報酬，橫斷面等權重平均，逐日複利。"""
    sids = sorted(data.keys())
    n = len(sids)

    def signal_fn(price_data, as_of, mkt):
        return {sid: 1.0 for sid in price_data}

    # initial_capital調高到1億：實測發現用預設100萬時，240個名額每格只分
    # 到約4,167元，整股(int()無條件捨去股數)在部分較高價股票上會捨去到0股
    # （240檔裡有16檔因此完全沒進場）或留下不小的零股尾數當閒置現金——
    # 這是真實整股交易的限制，不是bug，但會讓「跟pandas無條件複利的直接
    # 算法」比較時混入一個跟複利邏輯無關的額外落差。調高本金讓每格分到的
    # 金額遠大於個股股價，整股捨去的比例趨近可忽略，才能乾淨隔離複利
    # 邏輯本身。
    cfg = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                          max_positions=n, rebalance_every_n_days=21, initial_capital=100_000_000.0,
                          stop_loss_pct=1.0, commission_discount=1.0, slippage_bps=0.0, cost_multiplier=0.0,
                          instrument_type="normal", book_name="S2_equal_weight")
    result = run_backtest(signal_fn, data, market_df, cfg)
    engine_cagr = cagr_from_series(result.equity_curve["date"], result.equity_curve["equity"])

    # 直接路徑：pandas等權重（逐日對齊各檔報酬率，橫斷面平均，逐日複利）。
    # 實測發現真實資料品質問題：樣本裡至少一檔(0060)在2015-01-14出現
    # adj_close=0.0（前後兩天分別是30.6/30.45，明顯是資料錯誤不是真實
    # 跌停或下市），若直接pct_change()會產生-100%接著+inf%的假報酬，
    # 污染整體等權重平均（這不是本測試要驗證的複利bug，是獨立的資料
    # 品質缺陷，這裡防禦性處理：非正值一律視為缺值NaN，不讓它進報酬
    # 計算，也記錄下命中次數供後續稽核）。
    aligned = None
    for sid in sids:
        d = data[sid][["date", "adj_close"]].rename(columns={"adj_close": sid}).set_index("date")
        aligned = d if aligned is None else aligned.join(d, how="outer")
    aligned = aligned.sort_index()
    aligned = aligned[(aligned.index >= "2015-01-01") & (aligned.index <= holdout.VAL_END)]
    n_bad_prices = int((aligned <= 0).sum().sum())
    aligned = aligned.mask(aligned <= 0)
    rets = aligned.pct_change()
    n_inf_or_extreme = int(np.isinf(rets.values).sum())
    rets = rets.replace([np.inf, -np.inf], np.nan)
    daily_mean_ret = rets.mean(axis=1, skipna=True).fillna(0.0)
    direct_equity = (1 + daily_mean_ret).cumprod()
    direct_cagr = cagr_from_series(pd.Series(direct_equity.index), direct_equity)

    diff_pp = abs(engine_cagr - direct_cagr) * 100
    summary = {
        "engine_cagr_pct": round(engine_cagr * 100, 4), "direct_cagr_pct": round(direct_cagr * 100, 4),
        "diff_pp": round(diff_pp, 4), "tolerance_pp": S2_TOLERANCE_PP,
        "passed": bool(diff_pp < S2_TOLERANCE_PP), "n_names": n, "n_trades": result.n_trades,
        "n_bad_prices_found": n_bad_prices, "n_inf_returns_found": n_inf_or_extreme,
    }
    return summary, result


S2B_INITIAL_CAPITAL = 100_000_000.0  # 必須跟run_s2()的cfg.initial_capital一致，否則現金基準對不上


def run_s2b(data: dict, s2_result) -> dict:
    """驗.一續2（總司令2026-09-23裁示【稽核解封＋S2對等比較＋凍結
    regime家族】）：S2的pandas「直接算」是每日再平衡等權重，但引擎S2
    的實際行為是「買進後不減碼、只在空位時補新股，之後權重自由漂移」——
    這是兩個不同的策略，不是同一策略的兩種算法，每日再平衡另有Blume&
    Stambaugh(1983)紀錄過的向上偏誤(頻繁低買高賣的再平衡溢酬)。

    S2b改用S2引擎自己的成交紀錄(trades)在pandas重建「同一天進場、
    同樣張數、之後不再平衡、權重自由漂移」的市值序列——理論上應該幾乎
    完全等於引擎自己的equity_curve(同一組交易，只是換一個程式算市值)，
    若不一致代表engine.py的equity/mark-to-market計算本身有bug，
    不是基準定義差異。
    """
    trades = s2_result.trades
    buys = trades[trades["side"] == "buy"].sort_values("date")
    sells = trades[trades["side"] == "sell"].sort_values("date")
    n_sells = len(sells)  # S2設定下stop_loss/MA-exit皆停用，理論上應為0，如實記錄若非0

    price_by_sid: dict[str, pd.Series] = {}
    for sid, df in data.items():
        s = df.set_index("date")["adj_close"].astype(float)
        s = s.mask(s <= 0)
        price_by_sid[sid] = s

    eq_dates = s2_result.equity_curve["date"].tolist()
    buys_by_date = {d: g for d, g in buys.groupby("date")}
    sells_by_date = {d: g for d, g in sells.groupby("date")}

    holdings: dict[str, float] = {}
    last_price: dict[str, float] = {}
    cash = S2B_INITIAL_CAPITAL
    mv_rows = []
    for d in eq_dates:
        if d in buys_by_date:
            for _, row in buys_by_date[d].iterrows():
                sid, shares, price = row["stock_id"], float(row["shares"]), float(row["price"])
                holdings[sid] = holdings.get(sid, 0.0) + shares
                cash -= shares * price
        if d in sells_by_date:
            for _, row in sells_by_date[d].iterrows():
                sid, shares, price = row["stock_id"], float(row["shares"]), float(row["price"])
                holdings[sid] = holdings.get(sid, 0.0) - shares
                cash += shares * price
        mv = cash
        for sid, sh in holdings.items():
            if sh == 0:
                continue
            p = price_by_sid.get(sid, pd.Series(dtype=float)).get(d, np.nan)
            if pd.notna(p):
                last_price[sid] = p
            mv += sh * last_price.get(sid, 0.0)
        mv_rows.append(mv)

    direct_df = pd.DataFrame({"date": eq_dates, "equity": mv_rows})
    direct_cagr = cagr_from_series(direct_df["date"], direct_df["equity"])
    engine_cagr = cagr_from_series(s2_result.equity_curve["date"], s2_result.equity_curve["equity"])
    diff_pp = abs(engine_cagr - direct_cagr) * 100
    return {
        "engine_cagr_pct": round(engine_cagr * 100, 4), "direct_cagr_pct": round(direct_cagr * 100, 4),
        "diff_pp": round(diff_pp, 4), "tolerance_pp": S2_TOLERANCE_PP,
        "passed": bool(diff_pp < S2_TOLERANCE_PP), "n_buy_trades": len(buys), "n_sell_trades": n_sells,
        "note": "同一天進場/同樣張數/不再平衡/權重自由漂移，重建自S2引擎自己的trades紀錄",
    }


def run_s3(data: dict, market_df: pd.DataFrame, s2_direct_cagr_pct: float) -> dict:
    """隨機8檔、100個seed，報酬中位數必須落在S2附近（虛無假說：隨機挑
    子集的期望報酬應該約等於全體等權重，只是變異數較大，不該系統性
    偏低一大截）。"""
    sids = sorted(data.keys())
    cagrs = []
    for seed in range(S3_N_SEEDS):
        rng = random.Random(20260923 + seed)
        picks = rng.sample(sids, min(S3_MAX_POSITIONS, len(sids)))
        pick_set = set(picks)

        def signal_fn(price_data, as_of, mkt, _pick_set=pick_set):
            return {sid: 1.0 for sid in price_data if sid in _pick_set}

        cfg = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                              max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21, initial_capital=100_000_000.0,
                              stop_loss_pct=1.0, commission_discount=1.0, slippage_bps=0.0, cost_multiplier=0.0,
                              instrument_type="normal", book_name=f"S3_random8_seed{seed}")
        result = run_backtest(signal_fn, {sid: data[sid] for sid in picks}, market_df, cfg)
        cagr = cagr_from_series(result.equity_curve["date"], result.equity_curve["equity"])
        if cagr == cagr:  # not NaN
            cagrs.append(cagr * 100)

    median_cagr = float(np.median(cagrs)) if cagrs else float("nan")
    return {
        "n_seeds_requested": S3_N_SEEDS, "n_seeds_usable": len(cagrs),
        "median_cagr_pct": round(median_cagr, 4), "p10_cagr_pct": round(float(np.percentile(cagrs, 10)), 4),
        "p90_cagr_pct": round(float(np.percentile(cagrs, 90)), 4),
        "s2_direct_cagr_pct": s2_direct_cagr_pct,
        "diff_from_s2_pp": round(abs(median_cagr - s2_direct_cagr_pct), 4),
    }


def run_s4(data: dict, market_df: pd.DataFrame) -> dict:
    """在S3的隨機8檔設定上逐項加回，找出#358(-84.55%)是哪一項造成的。
    用單一固定種子（seed=0，跟S3第一個seed一致，非挑選過的漂亮結果）：
    ①baseline（同S3條件：零成本零停損，固定8檔不重抽）
    ②baseline+成本（1.8折commission+5bps滑價，ETF... 個股用normal稅率）
    ③②+15%停損
    ④③+產業曝險上限(同一產業最多2檔，靜態8檔選取時先過濾，不影響本已
      固定的8檔——這裡改用「重抽時套用產業上限」更貼近#358的實際做法)
    ⑤複製#358實際設計：每次rebalance都重新隨機抽8檔（不是固定8檔不變），
      這是#358真正的訊號設計，拿來跟①~④固定8檔版本對照，量化「持續
      重抽本身」造成的額外殺傷力。
    """
    sids = sorted(data.keys())
    rng_fixed = random.Random(20260923)
    fixed_picks = rng_fixed.sample(sids, min(S3_MAX_POSITIONS, len(sids)))
    fixed_pick_set = set(fixed_picks)
    fixed_data = {sid: data[sid] for sid in fixed_picks}
    industry_map = load_industry_map()

    def fixed_signal_fn(price_data, as_of, mkt):
        return {sid: 1.0 for sid in price_data if sid in fixed_pick_set}

    steps = {}

    cfg1 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                           max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                           stop_loss_pct=1.0, commission_discount=1.0, slippage_bps=0.0, cost_multiplier=0.0,
                           instrument_type="normal", book_name="S4_1_baseline")
    r1 = run_backtest(fixed_signal_fn, fixed_data, market_df, cfg1)
    steps["1_baseline_no_cost_no_stop"] = round(
        cagr_from_series(r1.equity_curve["date"], r1.equity_curve["equity"]) * 100, 4)

    cfg2 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                           max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                           stop_loss_pct=1.0, commission_discount=0.18, slippage_bps=5.0,
                           instrument_type="normal", book_name="S4_2_plus_cost")
    r2 = run_backtest(fixed_signal_fn, fixed_data, market_df, cfg2)
    steps["2_plus_cost_1p8discount"] = round(
        cagr_from_series(r2.equity_curve["date"], r2.equity_curve["equity"]) * 100, 4)

    cfg3 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                           max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                           stop_loss_pct=0.15, commission_discount=0.18, slippage_bps=5.0,
                           instrument_type="normal", book_name="S4_3_plus_stoploss")
    r3 = run_backtest(fixed_signal_fn, fixed_data, market_df, cfg3)
    steps["3_plus_15pct_stoploss"] = round(
        cagr_from_series(r3.equity_curve["date"], r3.equity_curve["equity"]) * 100, 4)

    # ④產業上限：固定8檔選取時就先過濾同產業最多2檔重抽（跟concentrated_
    # backtest.py同一種上限精神，這裡套用在「選出這8檔」這一步，不是逐日）
    rng_cap = random.Random(20260923)
    rng_cap.shuffle(sids)
    capped_picks = []
    industry_count = {}
    for sid in sids:
        if len(capped_picks) >= S3_MAX_POSITIONS:
            break
        ind = industry_map.get(sid, "未知")
        if industry_count.get(ind, 0) >= 2:
            continue
        capped_picks.append(sid)
        industry_count[ind] = industry_count.get(ind, 0) + 1
    capped_set = set(capped_picks)
    capped_data = {sid: data[sid] for sid in capped_picks}

    def capped_signal_fn(price_data, as_of, mkt):
        return {sid: 1.0 for sid in price_data if sid in capped_set}

    cfg4 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                           max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                           stop_loss_pct=0.15, commission_discount=0.18, slippage_bps=5.0,
                           instrument_type="normal", book_name="S4_4_plus_industry_cap")
    r4 = run_backtest(capped_signal_fn, capped_data, market_df, cfg4)
    steps["4_plus_industry_cap"] = round(
        cagr_from_series(r4.equity_curve["date"], r4.equity_curve["equity"]) * 100, 4)

    # ⑤複製#358：每次rebalance都重新隨機抽8檔+產業上限（不是固定8檔），
    # 這是#358(concentrated_backtest.py)實際的訊號設計，weekly(預設
    # rebalance_weekday)重抽，用全樣本300檔池不是固定8檔子集。
    rng5 = random.Random(20260923)

    def reshuffle_signal_fn(price_data, as_of, mkt):
        eligible = [sid for sid, d in price_data.items() if not d[d["date"] <= as_of].empty]
        rng5.shuffle(eligible)
        picks, ind_count = [], {}
        for sid in eligible:
            if len(picks) >= S3_MAX_POSITIONS:
                break
            ind = industry_map.get(sid, "未知")
            if ind_count.get(ind, 0) >= 2:
                continue
            picks.append(sid)
            ind_count[ind] = ind_count.get(ind, 0) + 1
        return {sid: 1.0 for sid in picks}

    cfg5 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                           max_positions=S3_MAX_POSITIONS,
                           stop_loss_pct=0.15, commission_discount=0.18, slippage_bps=5.0,
                           instrument_type="normal", book_name="S4_5_replicate_358_weekly_reshuffle")
    r5 = run_backtest(reshuffle_signal_fn, data, market_df, cfg5)
    steps["5_replicate_358_weekly_reshuffle_full_universe"] = round(
        cagr_from_series(r5.equity_curve["date"], r5.equity_curve["equity"]) * 100, 4)

    return {"fixed_picks_used_1to4": fixed_picks, "steps_cagr_pct": steps,
            "n_trades_by_step": {"1": r1.n_trades, "2": r2.n_trades, "3": r3.n_trades,
                                  "4": r4.n_trades, "5": r5.n_trades}}


S4_SEED_SENSITIVITY_N_SEEDS = 20
S4_SEED_SENSITIVITY_DIFF_THRESHOLD_PP = 2.0


def run_s4_step34_seed_sensitivity(data: dict, market_df: pd.DataFrame) -> dict:
    """驗.一續2（總司令2026-09-23裁示）：S4單一種子下第3步(9.82%)到
    第4步(2.96%)的落差是「加了產業上限」造成，還是「兩步驟選股方法
    本身不同」造成？——原版第1-3步用`rng.sample()`固定8檔，第4步卻換
    成`rng.shuffle()+逐一貪婪填格`的不同抽樣程序，即使種子數字相同，
    抽出來的8檔通常也不是同一組股票，這本身就是一個混淆變因。這裡把
    「有無產業上限」單獨隔離：兩種選法在20個seed下、其餘設定完全相同
    (成本+15%停損，跟原S4第3/4步一致)分別跑一輪，比較CAGR中位數差。
    """
    sids = sorted(data.keys())
    industry_map = load_industry_map()
    step3_cagrs, step4_cagrs, per_seed = [], [], []

    for seed in range(S4_SEED_SENSITIVITY_N_SEEDS):
        rng3 = random.Random(20260923 + seed)
        picks3 = rng3.sample(sids, min(S3_MAX_POSITIONS, len(sids)))
        pick3_set = set(picks3)
        data3 = {sid: data[sid] for sid in picks3}

        def sig3(price_data, as_of, mkt, _s=pick3_set):
            return {sid: 1.0 for sid in price_data if sid in _s}

        cfg3 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                               max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                               stop_loss_pct=0.15, commission_discount=0.18, slippage_bps=5.0,
                               instrument_type="normal", book_name=f"S4sens_3_seed{seed}")
        r3 = run_backtest(sig3, data3, market_df, cfg3)
        c3 = cagr_from_series(r3.equity_curve["date"], r3.equity_curve["equity"]) * 100
        step3_cagrs.append(c3)

        # 第4步的選法：同一顆種子，但改用跟原run_s4()一致的shuffle+貪婪
        # 填格法（每產業最多2檔），刻意保留「選法本身不同」這個變因，
        # 才是在複現原本第3/4步之間真正存在的差異來源，不是另外發明
        # 一個新的比較基準。
        rng4 = random.Random(20260923 + seed)
        shuffled = sids[:]
        rng4.shuffle(shuffled)
        picks4, ind_count = [], {}
        for sid in shuffled:
            if len(picks4) >= S3_MAX_POSITIONS:
                break
            ind = industry_map.get(sid, "未知")
            if ind_count.get(ind, 0) >= 2:
                continue
            picks4.append(sid)
            ind_count[ind] = ind_count.get(ind, 0) + 1
        pick4_set = set(picks4)
        data4 = {sid: data[sid] for sid in picks4}

        def sig4(price_data, as_of, mkt, _s=pick4_set):
            return {sid: 1.0 for sid in price_data if sid in _s}

        cfg4 = BacktestConfig(start_date="2015-01-01", end_date=holdout.VAL_END,
                               max_positions=S3_MAX_POSITIONS, rebalance_every_n_days=21,
                               stop_loss_pct=0.15, commission_discount=0.18, slippage_bps=5.0,
                               instrument_type="normal", book_name=f"S4sens_4_seed{seed}")
        r4 = run_backtest(sig4, data4, market_df, cfg4)
        c4 = cagr_from_series(r4.equity_curve["date"], r4.equity_curve["equity"]) * 100
        step4_cagrs.append(c4)

        per_seed.append({
            "seed": seed, "step3_cagr_pct": round(c3, 4), "step4_cagr_pct": round(c4, 4),
            "step3_picks": picks3, "step4_picks": picks4,
            "picks_overlap_n": len(pick3_set & pick4_set),
        })

    median3 = float(np.median(step3_cagrs))
    median4 = float(np.median(step4_cagrs))
    median_diff_pp = round(median3 - median4, 4)
    return {
        "n_seeds": S4_SEED_SENSITIVITY_N_SEEDS,
        "median_step3_cagr_pct": round(median3, 4), "median_step4_cagr_pct": round(median4, 4),
        "median_diff_pp": median_diff_pp,
        "flag_investigate_industry_cap_impl": bool(abs(median_diff_pp) > S4_SEED_SENSITIVITY_DIFF_THRESHOLD_PP),
        "threshold_pp": S4_SEED_SENSITIVITY_DIFF_THRESHOLD_PP,
        "per_seed": per_seed,
    }


def main() -> dict:
    print("=== S1: max_positions=1, 單押0050 vs load_0050_full_history() ===")
    s1 = run_s1()
    print(json.dumps(s1, ensure_ascii=False, indent=2))
    print(f"S1 {'PASS' if s1['passed'] else 'FAIL'}：引擎CAGR={s1['engine_cagr_pct']}% "
          f"vs 直接CAGR={s1['direct_cagr_pct']}%，差={s1['diff_pp']}pp（門檻<{s1['tolerance_pp']}pp）")

    print("\n載入樣本（既有快取，零新增API呼叫）...")
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="S2/S3 market_raw")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} 檔可用")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in S2/S3")

    print("\n=== S2: 樣本全體等權重、月頻再平衡 vs pandas直接算(每日再平衡) ===")
    s2, s2_result = run_s2(data, market_df)
    print(json.dumps(s2, ensure_ascii=False, indent=2))
    print(f"S2 {'PASS' if s2['passed'] else 'FAIL'}：引擎CAGR={s2['engine_cagr_pct']}% "
          f"vs 直接CAGR={s2['direct_cagr_pct']}%，差={s2['diff_pp']}pp（門檻<{s2['tolerance_pp']}pp）")

    print("\n=== S2b: 對等比較(同一天進場/同樣張數/不再平衡) vs 引擎自己的trades重建 ===")
    s2b = run_s2b(data, s2_result)
    print(json.dumps(s2b, ensure_ascii=False, indent=2))
    print(f"S2b {'PASS' if s2b['passed'] else 'FAIL'}：引擎CAGR={s2b['engine_cagr_pct']}% "
          f"vs 對等直接CAGR={s2b['direct_cagr_pct']}%，差={s2b['diff_pp']}pp（門檻<{s2b['tolerance_pp']}pp）")

    print(f"\n=== S3: 隨機8檔、{S3_N_SEEDS}個seed vs S2附近 ===")
    s3 = run_s3(data, market_df, s2["direct_cagr_pct"])
    print(json.dumps(s3, ensure_ascii=False, indent=2))
    print(f"S3：中位數CAGR={s3['median_cagr_pct']}%（P10={s3['p10_cagr_pct']}%,P90={s3['p90_cagr_pct']}%）"
          f" vs S2直接算={s3['s2_direct_cagr_pct']}%，差={s3['diff_from_s2_pp']}pp")

    print("\n=== S4: 逐項加回，找出#358(-84.55%)是哪一項造成的 ===")
    s4 = run_s4(data, market_df)
    print(json.dumps(s4, ensure_ascii=False, indent=2))

    print(f"\n=== S4續：第3步vs第4步 {S4_SEED_SENSITIVITY_N_SEEDS}個seed敏感度分析 ===")
    s4_sens = run_s4_step34_seed_sensitivity(data, market_df)
    print(json.dumps({k: v for k, v in s4_sens.items() if k != "per_seed"}, ensure_ascii=False, indent=2))
    print(f"中位數CAGR：第3步(無產業上限)={s4_sens['median_step3_cagr_pct']}% vs "
          f"第4步(有產業上限，不同選股法)={s4_sens['median_step4_cagr_pct']}%，"
          f"差={s4_sens['median_diff_pp']}pp（>{s4_sens['threshold_pp']}pp才需查產業上限實作："
          f"{'是' if s4_sens['flag_investigate_industry_cap_impl'] else '否'}）")

    out = {
        "generated_at": datetime.now(TZ).isoformat(),
        "s1": s1, "s2": s2, "s2b": s2b, "s3": s3, "s4": s4, "s4_seed_sensitivity": s4_sens,
        "s1_s2_both_passed": bool(s1["passed"] and s2["passed"]),
        "s2b_passed": bool(s2b["passed"]),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n寫入 {OUT_JSON}")
    return out


if __name__ == "__main__":
    main()
