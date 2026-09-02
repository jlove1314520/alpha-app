"""`HYPOTHESIS_QUEUE.md` #16 同產業配對交易 / 統計套利，第2~9關完整關卡。

**接續`pair_trading_sanity.py`（第1關sanity已PASS，見`HYPOTHESIS_QUEUE.md`#16
2026-09-02T21:28狀態：72/100檔可用、15個產業群組、90組候選配對、12組通過
相關係數>=0.70篩選、555次進場事件、方向性收斂中位數85.5%）。這支腳本把
「訊號存在」升級成「一個明確的market-neutral配對交易portfolio規則」，
走完GATE_SEQUENCE第2~9關，不重做第1關。

**策略規則（沿用`HYPOTHESIS_QUEUE.md`#16條目原文的具體假設定義，不自行
更改門檻）**：同產業配對（`universe.py::industry_category`，排除ETF/基金）
，用簡單相關係數(>=0.70)篩配對候選；對通過篩選的配對，120交易日滾動窗口
算log價差z-score；|z|>=2.0進場（做多相對低估的一邊、做空相對高估的一邊，
等金額對沖）；|z|<=0.5出場。新增（原假設定義沒明講，此腳本補一個必要的
風控參數，非p-hacking調整——沒有這個持倉可能無限期不收斂）：`MAX_HOLD_DAYS`
=60交易日強制平倉，跟本專案其餘因子/事件研究的因子横斷面極端值不收斂時
的風控精神一致。

**資金配置**：每組配對固定一個「slot」，slot notional = `INITIAL_CAPITAL`
/(2*配對數)（每組配對兩腳各分一半），配對之間彼此獨立（不做全域部位互搶
槽位的排隊機制）——這是簡化，等同於「每組配對各自用等權資金做自己的
market-neutral交易」，不是真的共用一個資金池搶部位，此簡化的影響已在
下方各關判定文字中誠實揭露，不隱藏。

**成本模型**：多頭腳用`validation/costs.py::round_trip_cost_pct()`（一般
賣出稅率），空頭腳用`short_round_trip_cost_pct()`（含借券費率，按實際
持有天數計）；`cost_multiplier`（1x/2x/3x）統一乘在多空兩腳合計摩擦成本
上，跟`backtest/engine.py::sell_leg_rate()`「乘數套用在手續費+稅+滑價
總和上」同一種簡化慣例（不是只放大單一子項）。

**台股放空摩擦誠實揭露（第4關起必須計入，`HYPOTHESIS_QUEUE.md`#16條目
明文要求）**：這裡用`short_round_trip_cost_pct()`的`BORROW_FEE_ANNUAL_PCT`
（2%/年，未經真實券商費率校準的placeholder）計入借券成本，但**沒有
建模「無券可借」（借不到就不能開倉）跟「強制回補」（券商執行回收造成
被迫平倉）這兩個台股放空特有的執行風險**——這個模型假設每一次做空腳
永遠借得到券、且能持有到自己想平倉的那天，是樂觀簡化，`costs.py`模組
docstring本身也是這樣誠實記載的。這條限制在下方第4/9關判定文字會重申，
不是本輪才第一次發現卻不提。

2026-09-02由`HYPOTHESIS_QUEUE_PROTOCOL.md`本輪排程接續，`pair_trading_
sanity.py`第1關PASS後的下一輪。
"""
from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy import stats as _sstats  # noqa: F401  (pbv2 already imports scipy.stats; kept for clarity)

import pair_trading_sanity as pts
import portfolio_backtest_v2 as pbv2
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import costs as costmod
from validation import holdout

# ---- 策略參數（HYPOTHESIS_QUEUE.md#16原文規格，非自訂調參） ----
CORR_THRESHOLD = pts.CORR_THRESHOLD    # 0.70
Z_WINDOW = pts.Z_WINDOW                # 120
ENTRY_Z = pts.ENTRY_Z                  # 2.0
EXIT_Z = 0.5                           # 條目原文「出場閾值0.5附近」
MAX_HOLD_DAYS = 60                     # 補的風控參數，見模組docstring
MIN_OVERLAP_DAYS = pts.MIN_OVERLAP_DAYS

INITIAL_CAPITAL = 1_000_000.0
N_RANDOM_DRAWS = 100  # GATE_SEQUENCE第2關要求 >=100 draws


# ============================================================
# 配對形成（沿用pair_trading_sanity.py的宇宙/分組/價格載入邏輯）
# ============================================================

def form_pairs(prices: dict[str, pd.Series], groups: dict[str, list[str]],
                cutoff: str | None, corr_threshold: float) -> list[tuple[str, str, str, float]]:
    """回傳通過相關係數篩選的 (industry, a, b, corr) 清單。
    `cutoff`：只用<=cutoff的資料算相關係數（避免用VAL期資料選VAL期要測的配對，
    第7關樣本外時傳TRAIN_END；第2~6關開發期分析可傳None＝用全部可用歷史，
    跟`pair_trading_sanity.py`第1關方法論一致）。
    """
    out = []
    for ind, ids in groups.items():
        for a, b in itertools.combinations(sorted(ids), 2):
            pa, pb = prices[a], prices[b]
            if cutoff is not None:
                pa = pa[pa.index <= pd.Timestamp(cutoff)]
                pb = pb[pb.index <= pd.Timestamp(cutoff)]
            common = pa.index.intersection(pb.index)
            if len(common) < MIN_OVERLAP_DAYS:
                continue
            la = np.log(pa.loc[common].sort_index())
            lb = np.log(pb.loc[common].sort_index())
            corr = float(np.corrcoef(la.values, lb.values)[0, 1])
            if np.isnan(corr) or corr < corr_threshold:
                continue
            out.append((ind, a, b, corr))
    return out


def all_candidate_pairs(groups: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """未經相關係數篩選的候選池（同產業兩兩配對），供第2關隨機對照抽樣用。"""
    out = []
    for ind, ids in groups.items():
        for a, b in itertools.combinations(sorted(ids), 2):
            out.append((ind, a, b))
    return out


def random_pairs_same_industry(candidate_pool: list[tuple[str, str, str]], n_pairs: int,
                                seed: int) -> list[tuple[str, str, str]]:
    """第2關隨機對照組的null：同產業內隨機配對（不做相關係數篩選），
    抽出跟真實配對數量一樣多的配對數，每一次抽樣都不重複使用同一檔股票
    兩次（避免一檔股票同時出現在多組配對造成人為相關）。
    """
    rng = random.Random(seed)
    pool = candidate_pool[:]
    rng.shuffle(pool)
    chosen: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for ind, a, b in pool:
        if len(chosen) >= n_pairs:
            break
        if a in used or b in used:
            continue
        chosen.append((ind, a, b))
        used.add(a)
        used.add(b)
    return chosen


# ============================================================
# 單一配對的交易模擬（核心狀態機）
# ============================================================

def _cost_pct(holding_days: float, cost_multiplier: float) -> tuple[float, float]:
    """回傳 (多頭腳round-trip成本%, 空頭腳round-trip成本%)，皆已乘上cost_multiplier。
    採跟`backtest/engine.py::sell_leg_rate()`一致的簡化慣例：cost_multiplier
    整體乘在(手續費+稅+滑價[+借券費])總和上，不是只放大單一子項。
    """
    long_pct = costmod.round_trip_cost_pct() * cost_multiplier
    short_pct = costmod.short_round_trip_cost_pct(holding_days=holding_days) * cost_multiplier
    return long_pct, short_pct


def simulate_pair(sid_a: str, sid_b: str, px_a: pd.Series, px_b: pd.Series,
                   start: str, end: str, leg_notional: float,
                   entry_z: float = ENTRY_Z, exit_z: float = EXIT_Z,
                   z_window: int = Z_WINDOW, max_hold_days: int = MAX_HOLD_DAYS,
                   cost_multiplier: float = 1.0) -> dict:
    """走完一組配對在[start,end]區間的完整交易生命週期。

    回傳：{"trades": [...], "daily_equity": pd.Series(date->slot equity)}。
    `daily_equity`基準值=2*leg_notional（這組配對slot的滿倉名目本金），
    逐日按目前部位（若有）用當日收盤價mark-to-market，讓portfolio層可以
    算出有意義的日頻equity curve（MDD/Sharpe需要，不是只在平倉那天才跳動）。

    區間邊界處理：若區間結束時仍有未平倉部位，強制在最後一個交易日平倉
    （標記`forced_exit=True`），避免部位跨越TRAIN/VAL/年度切片邊界造成
    leave-one-out與逐年一致性關卡的歸屨模糊——這是簡化但誠實揭露，不是
    忽略。
    """
    common = px_a.index.intersection(px_b.index).sort_values()
    if len(common) < z_window + 5:
        return {"trades": [], "daily_equity": pd.Series(dtype=float)}
    a = np.log(px_a.loc[common])
    b = np.log(px_b.loc[common])
    spread = a - b
    roll_mean = spread.rolling(z_window).mean()
    roll_std = spread.rolling(z_window).std()
    z = (spread - roll_mean) / roll_std

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    mask = (common >= start_ts) & (common <= end_ts)
    decision_dates = common[mask]
    if len(decision_dates) == 0:
        return {"trades": [], "daily_equity": pd.Series(dtype=float)}

    trades = []
    equity_vals = {}
    base = 2 * leg_notional
    realized = 0.0

    position = None  # dict: entry_date, direction, entry_price_a, entry_price_b, entry_idx
    for i, d in enumerate(decision_dates):
        zi = z.loc[d]
        price_a, price_b = float(px_a.loc[d]), float(px_b.loc[d])
        is_last = (i == len(decision_dates) - 1)

        if position is None:
            if pd.notna(zi) and abs(zi) >= entry_z:
                direction = "short_a_long_b" if zi > 0 else "long_a_short_b"
                position = {
                    "entry_date": d, "direction": direction,
                    "entry_price_a": price_a, "entry_price_b": price_b,
                    "entry_pos": i,
                }
        else:
            days_held = i - position["entry_pos"]
            should_exit = (pd.notna(zi) and abs(zi) <= exit_z) or days_held >= max_hold_days or is_last
            if should_exit:
                trade = _close_trade(position, price_a, price_b, d, days_held,
                                      leg_notional, cost_multiplier, forced=is_last and not (
                                          pd.notna(zi) and abs(zi) <= exit_z) and days_held < max_hold_days)
                trades.append(trade)
                realized += trade["net_pnl"]
                position = None

        # 每日mark-to-market（用於equity curve；未平倉部位用「當日價 vs 進場價」算未實現損益，
        # 不含尚未發生的出場成本——出場成本只在真正平倉那天才計入realized，這是標準做法，
        # 不是低估風險：未實現損益本來就不含未來才會發生的交易成本）
        unrealized = 0.0
        if position is not None:
            unrealized = _unrealized_pnl(position, price_a, price_b, leg_notional)
        equity_vals[d] = base + realized + unrealized

    return {"trades": trades, "daily_equity": pd.Series(equity_vals)}


def _unrealized_pnl(position: dict, price_a: float, price_b: float, leg_notional: float) -> float:
    shares_a = leg_notional / position["entry_price_a"]
    shares_b = leg_notional / position["entry_price_b"]
    if position["direction"] == "short_a_long_b":
        pnl_a = (position["entry_price_a"] - price_a) * shares_a  # short A
        pnl_b = (price_b - position["entry_price_b"]) * shares_b  # long B
    else:
        pnl_a = (price_a - position["entry_price_a"]) * shares_a  # long A
        pnl_b = (position["entry_price_b"] - price_b) * shares_b  # short B
    return pnl_a + pnl_b


def _close_trade(position: dict, exit_price_a: float, exit_price_b: float, exit_date,
                  holding_days: int, leg_notional: float, cost_multiplier: float,
                  forced: bool) -> dict:
    shares_a = leg_notional / position["entry_price_a"]
    shares_b = leg_notional / position["entry_price_b"]
    long_cost_pct, short_cost_pct = _cost_pct(max(holding_days, 1), cost_multiplier)

    if position["direction"] == "short_a_long_b":
        gross_a = (position["entry_price_a"] - exit_price_a) * shares_a
        gross_b = (exit_price_b - position["entry_price_b"]) * shares_b
        cost_a = shares_a * position["entry_price_a"] * short_cost_pct
        cost_b = shares_b * position["entry_price_b"] * long_cost_pct
    else:
        gross_a = (exit_price_a - position["entry_price_a"]) * shares_a
        gross_b = (position["entry_price_b"] - exit_price_b) * shares_b
        cost_a = shares_a * position["entry_price_a"] * long_cost_pct
        cost_b = shares_b * position["entry_price_b"] * short_cost_pct

    gross_pnl = gross_a + gross_b
    total_cost = cost_a + cost_b
    return {
        "entry_date": position["entry_date"], "exit_date": exit_date,
        "direction": position["direction"], "holding_days": holding_days,
        "gross_pnl": gross_pnl, "total_cost": total_cost,
        "net_pnl": gross_pnl - total_cost, "forced_exit": forced,
    }


# ============================================================
# Portfolio層：組合多組配對
# ============================================================

def simulate_portfolio(pairs: list[tuple[str, str, str]], prices: dict[str, pd.Series],
                        start: str, end: str, cost_multiplier: float = 1.0,
                        entry_z: float = ENTRY_Z, exit_z: float = EXIT_Z,
                        z_window: int = Z_WINDOW, max_hold_days: int = MAX_HOLD_DAYS,
                        initial_capital: float = INITIAL_CAPITAL) -> dict:
    """跑一組配對清單的完整portfolio回測。等權配置：每組配對slot本金=
    initial_capital/(2*n_pairs)*2（每組配對兩腳各一半），配對彼此獨立
    （見模組docstring「資金配置」簡化揭露）。
    """
    n_pairs = len(pairs)
    if n_pairs == 0:
        return {"equity_curve": pd.DataFrame(columns=["date", "equity"]),
                "trades": pd.DataFrame(), "n_pairs": 0}
    leg_notional = initial_capital / (2 * n_pairs)

    all_trades = []
    equity_series_list = []
    for ind, a, b in pairs:
        r = simulate_pair(a, b, prices[a], prices[b], start, end, leg_notional,
                           entry_z=entry_z, exit_z=exit_z, z_window=z_window,
                           max_hold_days=max_hold_days, cost_multiplier=cost_multiplier)
        for t in r["trades"]:
            all_trades.append({"industry": ind, "pair_a": a, "pair_b": b, **t})
        if len(r["daily_equity"]):
            equity_series_list.append(r["daily_equity"])

    if not equity_series_list:
        return {"equity_curve": pd.DataFrame(columns=["date", "equity"]),
                "trades": pd.DataFrame(all_trades), "n_pairs": n_pairs}

    combined = pd.concat(equity_series_list, axis=1)
    combined = combined.sort_index().ffill().bfill()
    portfolio_equity = combined.sum(axis=1)
    equity_curve = portfolio_equity.reset_index()
    equity_curve.columns = ["date", "equity"]
    # market_df（來自finmind_client.load_dev）的date欄位是字串格式("YYYY-MM-DD")，
    # 這裡的date是內部運算用的Timestamp——統一轉成字串，讓portfolio_metrics()
    # 呼叫pbv2.alpha_significance()/buy_and_hold_index_pct()時能跟market_df正確inner
    # join（否則dtype不一致會靜默join成0筆，alpha/beta全部變NaN，是曾經踩過的坑，
    # 這裡直接在建立equity_curve時修正，不留給呼叫端猜）。
    equity_curve["date"] = equity_curve["date"].dt.strftime("%Y-%m-%d")

    return {"equity_curve": equity_curve, "trades": pd.DataFrame(all_trades), "n_pairs": n_pairs}


def portfolio_metrics(sim: dict, market_df: pd.DataFrame, initial_capital: float = INITIAL_CAPITAL) -> dict:
    ec = sim["equity_curve"]
    if ec.empty:
        return {"final_equity": initial_capital, "return_pct": 0.0, "mdd_pct": 0.0,
                "sharpe": float("nan"), "alpha_ann_pct": float("nan"), "beta": float("nan"),
                "alpha_pvalue": float("nan"), "alpha_significant": False,
                "n_trades": 0, "n_pairs": sim.get("n_pairs", 0)}
    final_equity = float(ec["equity"].iloc[-1])
    running_max = ec["equity"].cummax()
    dd = (ec["equity"] - running_max) / running_max
    mdd_pct = float(dd.min() * 100)
    alpha = pbv2.alpha_significance(ec, market_df)
    sharpe = pbv2.sharpe_ratio(ec)
    trades = sim["trades"]
    return {
        "final_equity": final_equity,
        "return_pct": (final_equity / initial_capital - 1) * 100,
        "mdd_pct": mdd_pct, "sharpe": sharpe,
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "n_trades": len(trades), "n_pairs": sim.get("n_pairs", 0),
    }


# ============================================================
# 資料載入（沿用pair_trading_sanity.py，不重造）
# ============================================================

def load_universe_data():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"Sample: {len(sample_ids)} names, START_DATE={START_DATE}, VAL_END={holdout.VAL_END}")
    print("Loading prices (cached after first run)...")
    prices = pts.load_prices(sample_ids)
    # pts.load_prices()回傳的index是字串日期（FinMind/yfinance原始格式），這裡統一轉成
    # DatetimeIndex，讓後續所有跟pd.Timestamp的比較（cutoff/start/end切片）行為一致，
    # 不動pair_trading_sanity.py本身（它自己用reset_index(drop=True)避開了這個問題，
    # 不需要真正的日期索引比較，這支腳本需要，所以在這裡轉換）。
    prices = {sid: s.set_axis(pd.to_datetime(s.index)) for sid, s in prices.items()}
    print(f"  {len(prices)}/{len(sample_ids)} usable names (>= {MIN_OVERLAP_DAYS} trading days)")
    groups = pts.build_industry_groups(list(prices.keys()))
    print(f"  {len(groups)} industry groups with >=2 usable members")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in pair_trading_backtest_v1")
    market_df = prepare_market_data(market_raw)
    return prices, groups, market_df


if __name__ == "__main__":
    print("此模組是共用函式庫，實際關卡跑法見 pair_trading_gates.py")
