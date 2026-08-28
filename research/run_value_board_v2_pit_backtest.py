"""價值成長榜（`score_v2.py`/`generate_scores_live.py`同一套FACTOR_DEFS）
PIT組合回測（2026-08-28新增，B24第一步，骨架＋機制驗證跑）。

**背景**：BACKLOG.md B24第一項要求「PIT回測（正式開工，凍結權重）：月度
再平衡、持股20檔、全成本、動態隨機對照組1000次、對大盤回歸alpha顯著性、
Sortino/MDD優先」，先做價值成長榜。這支腳本重用既有、已經跑過的驗證框架
（`run_score_backtest.py`同一套`backtest/engine.py::run_backtest()`機制、
`portfolio_backtest_v2.py`同一套alpha/beta回歸+Sharpe公式、
`benchmark_taiex_stats.py`同一套TAIEX買進持有MDD/Sortino公式），只是把
訊號函式換成`score_v2.py::compute_scores_v2()`（=App目前正式上線的價值
成長榜FACTOR_DEFS八大因子組合，跟另外兩支腳本用的是完全不同的因子集合，
不能混用既有結果）。

**重要澄清（跟使用者原話「目前只夠回測約12-18個月」的認知落差）**：
使用者原話假設的12-18個月，指的可能是App即時JSON路徑（`price_history.json`
90天/`fundamentals.json`26個月營收）的資料深度——但這支腳本走的是research端
既有的`factor_ic.py`樣本，2010年起、FinMind歷史parquet快取，已經有長達
10年以上的可用歷史，**不受那個12-18個月限制**。這是好消息：可以測的期間
比使用者原本以為的長很多，統計檢定力也更高。

**2026-08-28第二次修訂：樣本擴大到500檔（使用者核准「回測樣本擴大：核准
擴到500檔（一次性）」，見`VALUE_BOARD_SAMPLE_SIZE`）**——第一次機制驗證跑
（100檔）發現嚴重方法論問題：扣掉流動性門檻後合格股票池平均只有約11.5檔，
從未達到20檔持股目標，代表約40-45%資金整個回測期間閒置在現金，這對「策略
vs 100%投入的買進持有大盤」是結構性不公平比較。500檔樣本應該能大幅改善
這個問題（更大的池子，流動性門檻後仍有機會穩定湊到20檔）。**遵守「資料源
禮儀」規則（見BACKLOG.md，2026-08-28同一天新增的全域速率限制）**：
`research/finmind_client.py`現在對FinMind的請求嚴格3秒節流+斷路器，500檔
裡任何一檔如果本機parquet快取沒有涵蓋到的資料（institutional/revenue等），
第一次抓取都要付這個代價——**這是刻意的、已經跟使用者說明過的取捨，寧可
慢也不要再觸發封鎖**，載入階段可能要數小時，不是這支腳本的bug，是誠實
遵守速率限制的必然結果。

**新增翻倍率/大賺率/地雷率統計（使用者原話，見`compute_moonshot_stats()`）**：
對每一次「買進」事件往後看12個月(252個交易日)的價格路徑，取期間內曾經
達到過的最高/最低報酬率（不是只看最後平倉報酬），算出翻倍率(曾達+100%)/
大賺率(曾達+50%)/地雷率(曾跌破-30%)，並對隨機對照組的每一次draw也算同一
組指標取平均，當作「亂槍打鳥」的對照基準。

**Holdout紀律（本輪嚴格遵守，未經使用者同意不解鎖）**：全程只用
`finmind_client.load_dev()`（自動cap在`VAL_END=2024-12-31`），`backtest/
engine.py::run_backtest()`本身在每個price DataFrame跑`assert_no_holdout_
leakage()`，結構性擋掉任何holdout洩漏——就算這支腳本想不小心看到2025-2026
的資料也做不到。**這代表這次回測回答的是「這套因子組合在2015-2024historical
資料上，是否能穩定打敗大盤」，不是「App現在正式上線後這幾個月的實際表現」
——後者需要動用holdout，必須先取得使用者明確同意才能做（見BACKLOG.md
B16/B24條目、CLAUDE.md安全紅線）。**

**這輪只是機制驗證跑，不是最終結果（使用者原話「這是大工程，這一輪先把
回測執行腳本的骨架/資料準備部分做出來，不用一次做完整套統計檢定」）**：
- 隨機對照組這輪先用`N_RANDOM_DRAWS_QUICK`（30次，跟run_score_backtest.py
  第一版同樣的可行性考量：每次draw都要重跑一次完整多年期週期回測，1000次
  在這輪要驗證機制是否work的階段太慢，等機制確認正確後再視實際跑一次
  1000次draws要多久決定要不要維持1000或誠實揭露降級數字，跟
  run_score_backtest.py docstring說明的200→60降級同一個誠實揭露慣例）。
- 尚未寫進`TRIALS_LEDGER.md`（那裡的紀律要求完整的Bonferroni累積校正跟
  正式判定，這輪的機制驗證跑不算一次正式試驗，等真正用1000 draws+正式
  判定跑完才登錄）。
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy import stats

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import SAMPLE_SEED, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from score import load_industry_map
from score_v2 import compute_scores_v2
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 20  # 使用者規格：持股20檔
REBALANCE_DAYS = 21  # 月度再平衡（21個交易日近似一個月，跟portfolio_backtest_v2.py同一個慣例）
N_RANDOM_DRAWS_QUICK = 30  # 機制驗證用，見模組docstring「這輪只是機制驗證跑」說明
RANDOM_CONTROL_SEED = 20260828
# 2026-08-28新增（使用者核准「回測樣本擴大：核准擴到500檔（一次性）」）：
# 刻意**不**改`factor_ic.py`的全域`SAMPLE_SIZE`常數（那會影響其他既有試驗
# 對「100檔樣本」的既有引用/可重現性），只在這支腳本內用一個獨立的本地
# 常數，呼叫`sample_universe_ids(VALUE_BOARD_SAMPLE_SIZE, SAMPLE_SEED)`——
# 同一個seed但不同sample_size，Python的`random.Random(seed).sample()`
# 內部消耗隨機數的方式跟k有關，500檔集合**不保證**是100檔集合的超集，
# 是一個全新、獨立的500檔隨機樣本，不是「舊100+新400」的疊加，誠實記錄
# 這個技術細節。
VALUE_BOARD_SAMPLE_SIZE = 500


def eligible_for_ranking_v2(cs: pd.DataFrame) -> pd.DataFrame:
    """跟generate_scores_live.py/App端同一個定義：流動性不足的不進數字排名。"""
    if cs.empty:
        return cs
    return cs[~cs["liquidity_insufficient"]] if "liquidity_insufficient" in cs.columns else cs


def make_score_v2_signal_fn(industry_map: dict[str, str], start_date: str, top_n: int = TOP_N):
    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        cs = compute_scores_v2(as_of, price_data, industry_map, start_date)
        cs = eligible_for_ranking_v2(cs)
        # 2026-08-28修正（sanity check親自抓到的真bug）：compute_scores_v2()在
        # 完全沒有任何股票有資料的as_of日期會回傳零欄位的空DataFrame（跟
        # adjust.py/build_price_history.py之前修過的同一種「空DataFrame沒有
        # 欄位」陷阱），這裡沒擋住的話cs.sort_values("total_score",...)會
        # KeyError整支腳本中止。改成這種情況誠實回傳空dict（=這個再平衡日
        # 沒有任何新持倉建議，不是硬湊一個假結果）。
        if cs.empty or "total_score" not in cs.columns:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(top_n)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


_eligible_pool_cache: dict[str, list[str]] = {}


def make_random_signal_fn(industry_map: dict[str, str], start_date: str, top_n: int, seed: int):
    import random
    rng = random.Random(seed)

    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        if as_of not in _eligible_pool_cache:
            cs = eligible_for_ranking_v2(compute_scores_v2(as_of, price_data, industry_map, start_date))
            _eligible_pool_cache[as_of] = cs.index.tolist()
        pool = _eligible_pool_cache[as_of]
        picks = pool if len(pool) <= top_n else rng.sample(pool, top_n)
        return {sid: 1.0 for sid in picks}
    return signal_fn


def buy_and_hold_index_pct(market_df: pd.DataFrame, start: str, end: str) -> float:
    """對照組(b)：買進持有加權指數，零成本不換股——跟portfolio_backtest_v2.py同一個公式。"""
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    if len(window) < 2:
        return float("nan")
    p0, p1 = window.iloc[0]["close"], window.iloc[-1]["close"]
    return float(p1 / p0 - 1) * 100


def taiex_mdd_sortino(market_df: pd.DataFrame, start: str, end: str) -> dict:
    """大盤本身同期的MDD/Sortino——跟benchmark_taiex_stats.py同一個公式，
    讓策略端的MDD/Sortino有量化基準可以對照，不是只有質化描述。"""
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    closes = window["close"].astype(float)
    if len(closes) < 2:
        return {"mdd_pct": float("nan"), "sortino": float("nan")}
    running_max = closes.cummax()
    drawdown = (closes - running_max) / running_max
    mdd_pct = float(drawdown.min() * 100)
    rets = closes.pct_change().dropna()
    downside = rets[rets < 0]
    sortino = float("nan")
    if len(downside) and downside.std() != 0:
        sortino = float(rets.mean() / downside.std() * np.sqrt(252))
    return {"mdd_pct": mdd_pct, "sortino": sortino}


def alpha_significance(equity_curve: pd.DataFrame, market_df: pd.DataFrame) -> dict:
    """跟portfolio_backtest_v2.py::alpha_significance()逐行一致的公式，這裡
    自成一體複製一份（不同因子引擎，各自獨立，不跨檔案import）。"""
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"alpha_ann_pct": float("nan"), "beta": float("nan"), "alpha_pvalue": float("nan"),
                "alpha_significant": False, "n_days": len(merged)}
    reg = stats.linregress(merged["mkt_return"], merged["net_return"])
    alpha_ann_pct = ((1 + reg.intercept) ** 252 - 1) * 100
    pvalue = (2 * stats.t.sf(abs(reg.intercept / reg.intercept_stderr), len(merged) - 2)
              if reg.intercept_stderr else float("nan"))
    return {
        "alpha_ann_pct": float(alpha_ann_pct), "beta": float(reg.slope),
        "alpha_pvalue": float(pvalue) if pvalue == pvalue else float("nan"),
        "alpha_significant": bool(reg.intercept > 0 and pvalue == pvalue and pvalue < 0.05),
        "n_days": len(merged),
    }


def compute_moonshot_stats(trades: pd.DataFrame, price_data: dict[str, pd.DataFrame], horizon_days: int = 252) -> dict:
    """使用者核心關切的「翻倍率/大賺率/地雷率」指標（2026-08-28新增，B24
    任務2使用者原話：「翻倍率=Top20中12個月內最高漲幅曾達+100%的檔數比例；
    大賺率=曾達+50%的比例...同時報告反面——12個月跌超過-30%的比例（地雷率）」）。

    對每一次「買進」事件（不是每檔獨立股票，同一檔股票在回測期間多次
    進出各自算一次entry），往後看最多`horizon_days`個交易日（約12個月）
    的adj_close價格路徑，取這段期間內**曾經達到過的最高/最低報酬率**
    （不是只看最後平倉報酬——用意是回答「有沒有翻倍過」而不是「最後有
    沒有賺」，這兩個問題答案可能不同：曾經翻倍又跌回來，仍然算「翻倍
    率」裡的一次命中）。entry太靠近回測結束、可用天數不足`horizon_days`
    的，用「已有的最長天數」代替，不強制排除（否則會系統性剔除近期表現
    最好/最差的entry，造成倖存者偏誤），但用`truncated_entries`誠實記錄
    有幾筆是截斷的。"""
    if trades.empty:
        return {"n_entries": 0, "moonshot_rate": None, "big_win_rate": None, "mine_rate": None, "truncated_entries": 0}
    buys = trades[trades["side"] == "buy"]
    moonshot, big_win, mine, truncated, n = 0, 0, 0, 0, 0
    for _, row in buys.iterrows():
        sid, entry_date, entry_price = row["stock_id"], row["date"], row["price"]
        df = price_data.get(sid)
        if df is None or entry_price in (None, 0) or pd.isna(entry_price):
            continue
        future = df[df["date"] > entry_date].sort_values("date").head(horizon_days)
        if future.empty or "adj_close" not in future.columns:
            continue
        if len(future) < horizon_days:
            truncated += 1
        max_ret = float(future["adj_close"].max()) / entry_price - 1
        min_ret = float(future["adj_close"].min()) / entry_price - 1
        n += 1
        if max_ret >= 1.0:
            moonshot += 1
        if max_ret >= 0.5:
            big_win += 1
        if min_ret <= -0.3:
            mine += 1
    if n == 0:
        return {"n_entries": 0, "moonshot_rate": None, "big_win_rate": None, "mine_rate": None, "truncated_entries": 0}
    return {
        "n_entries": n,
        "moonshot_rate": round(moonshot / n * 100, 1),
        "big_win_rate": round(big_win / n * 100, 1),
        "mine_rate": round(mine / n * 100, 1),
        "truncated_entries": truncated,
    }


def run_period(label: str, data: dict, market_df: pd.DataFrame, industry_map: dict, start: str, end: str) -> dict:
    print(f"\n=== {label}: {start}..{end} ===")
    _eligible_pool_cache.clear()

    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_pit")
    result = run_backtest(make_score_v2_signal_fn(industry_map, START_DATE, TOP_N), data, market_df, cfg)
    print(f"  價值成長榜v2 Top{TOP_N}(月度再平衡): return={result.total_return_pct:+.2f}%  "
          f"MDD={result.max_drawdown_pct:.2f}%  Sortino={result.sortino_ratio:.3f}  trades={result.n_trades}")

    bh = buy_and_hold_index_pct(market_df, start, end)
    bh_stats = taiex_mdd_sortino(market_df, start, end)
    print(f"  買進持有加權指數: {bh:+.2f}%  MDD={bh_stats['mdd_pct']:.2f}%  Sortino={bh_stats['sortino']:.3f}")

    alpha = alpha_significance(result.equity_curve, market_df)
    print(f"  alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta={alpha['beta']:+.3f}  "
          f"p={alpha['alpha_pvalue']:.4f}  顯著={alpha['alpha_significant']}（n={alpha['n_days']}天）")

    moonshot = compute_moonshot_stats(result.trades, data)
    print(f"  翻倍率(12個月內曾達+100%)={moonshot['moonshot_rate']}%  "
          f"大賺率(曾達+50%)={moonshot['big_win_rate']}%  地雷率(曾跌破-30%)={moonshot['mine_rate']}%  "
          f"（{moonshot['n_entries']}次進場事件，{moonshot['truncated_entries']}筆因接近回測尾端資料不足12個月而截斷）")

    print(f"  隨機對照組（{N_RANDOM_DRAWS_QUICK}次，機制驗證用，非最終1000次）...")
    random_finals = []
    random_moonshot_rates, random_big_win_rates, random_mine_rates = [], [], []
    for i in range(N_RANDOM_DRAWS_QUICK):
        rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                              rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_random_control")
        rfn = make_random_signal_fn(industry_map, START_DATE, TOP_N, seed=RANDOM_CONTROL_SEED + i)
        rr = run_backtest(rfn, data, market_df, rcfg)
        random_finals.append(rr.final_equity)
        rm = compute_moonshot_stats(rr.trades, data)
        if rm["moonshot_rate"] is not None:
            random_moonshot_rates.append(rm["moonshot_rate"])
            random_big_win_rates.append(rm["big_win_rate"])
            random_mine_rates.append(rm["mine_rate"])
    real_final = result.final_equity
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    print(f"  真實策略終值 {real_final:,.0f} vs 隨機對照組中位數 {np.median(random_finals):,.0f}"
          f"（百分位 {percentile:.1f}，{N_RANDOM_DRAWS_QUICK}次draws，非最終1000次）")
    rand_moonshot_avg = round(float(np.mean(random_moonshot_rates)), 1) if random_moonshot_rates else None
    rand_big_win_avg = round(float(np.mean(random_big_win_rates)), 1) if random_big_win_rates else None
    rand_mine_avg = round(float(np.mean(random_mine_rates)), 1) if random_mine_rates else None
    print(f"  隨機對照組翻倍率/大賺率/地雷率平均：{rand_moonshot_avg}% / {rand_big_win_avg}% / {rand_mine_avg}%"
          f"（真實策略 {moonshot['moonshot_rate']}% / {moonshot['big_win_rate']}% / {moonshot['mine_rate']}% ——"
          f"「選中比例」是否顯著高於「亂槍打鳥」看這兩組數字的差距）")

    return {
        "label": label, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "n_trades": result.n_trades,
        "buy_and_hold_pct": bh, "bh_mdd_pct": bh_stats["mdd_pct"], "bh_sortino": bh_stats["sortino"],
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "random_control_percentile_quick": percentile, "random_draws_quick": N_RANDOM_DRAWS_QUICK,
        "moonshot_rate": moonshot["moonshot_rate"], "big_win_rate": moonshot["big_win_rate"],
        "mine_rate": moonshot["mine_rate"], "moonshot_n_entries": moonshot["n_entries"],
        "random_moonshot_rate_avg": rand_moonshot_avg, "random_big_win_rate_avg": rand_big_win_avg,
        "random_mine_rate_avg": rand_mine_avg,
    }


def main():
    sample_ids = sample_universe_ids(VALUE_BOARD_SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_value_board_v2_pit_backtest")
    market_df = prepare_market_data(market_raw)

    # 2026-08-28新增：load_sample_with_factors()對100檔樣本本身要約22分鐘
    # （prepare_factors()真實運算，不是網路請求，見BACKLOG.md記錄），這支
    # 腳本之後還會反覆重跑（sanity check/拉高random draws次數），每次都
    # 重付22分鐘不划算——這裡加一層pickle本地快取（只快取這支腳本自己用，
    # 不動factor_ic.py本身，不影響其他呼叫端）。
    cache_path = Path(__file__).parent / "data" / "backtests" / f"value_board_v2_sample_cache_{VALUE_BOARD_SAMPLE_SIZE}.pkl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        print(f"Loading sample + factors from local cache ({cache_path})...")
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
    else:
        print("Loading sample + factors (no local cache yet, first run takes ~20min)...")
        data = load_sample_with_factors(sample_ids, market_df)
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        print(f"  cached to {cache_path} for next run")
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in run_value_board_v2_pit_backtest")

    industry_map = load_industry_map()
    print(f"  industry_map: {len(industry_map)} entries")

    train_result = run_period("TRAIN", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END)
    val_result = run_period("VALIDATION", data, market_df, industry_map, "2021-01-01", holdout.VAL_END)

    print(f"\n=== SUMMARY（{VALUE_BOARD_SAMPLE_SIZE}檔樣本，機制驗證跑，尚未登錄TRIALS_LEDGER.md）===")
    for r in (train_result, val_result):
        print(f"  {r['label']}: 策略={r['return_pct']:+.2f}% vs 買進持有={r['buy_and_hold_pct']:+.2f}%  "
              f"MDD策略/大盤={r['mdd_pct']:.2f}%/{r['bh_mdd_pct']:.2f}%  "
              f"Sortino策略/大盤={r['sortino']:.3f}/{r['bh_sortino']:.3f}  "
              f"alpha={r['alpha_ann_pct']:+.2f}%(顯著={r['alpha_significant']})  "
              f"隨機對照百分位={r['random_control_percentile_quick']:.1f}(僅{r['random_draws_quick']}次)  "
              f"翻倍率/大賺率/地雷率：策略{r['moonshot_rate']}%/{r['big_win_rate']}%/{r['mine_rate']}% "
              f"vs 隨機{r['random_moonshot_rate_avg']}%/{r['random_big_win_rate_avg']}%/{r['random_mine_rate_avg']}%")

    out_path = Path(__file__).parent / "data" / f"value_board_v2_pit_backtest_{VALUE_BOARD_SAMPLE_SIZE}_quicklook.csv"
    pd.DataFrame([train_result, val_result]).to_csv(out_path, index=False)
    print(f"saved {out_path}")
    return train_result, val_result


if __name__ == "__main__":
    main()
