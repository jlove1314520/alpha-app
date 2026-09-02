"""HYPOTHESIS_QUEUE.md #23 -- Piotroski F-score 當價值榜排雷閘門，第2步：
「原始value_board_v2」vs「+F-score gate」比較（第1關sanity已PASS，見
`piotroski_fscore_sanity.py`／`TRIALS_LEDGER.md`#93）。

**這輪的有界工作單位（不是完整GATE_SEQUENCE一次做完）**：重用既有
`run_value_board_v2_pit_backtest.py`的B24-500快取（`value_board_v2_sample_
cache_liquidity500.pkl`，500檔已算好因子的價量資料，不重抓）+ 既有基準
（`data/value_board_v2_pit_backtest_liquidity500_full.csv`，原始版TRAIN
alpha p=0.2672／VAL alpha p=0.1441，兩期皆不顯著，見`B24_RESULTS.md`），
只新增F-score計算（沿用`piotroski_fscore_sanity.py::_fscore_components()`，
不重寫）+ 在`compute_scores_v2()`的候選池上疊加F-score門檻，跑「真實回測
（非隨機對照組）」的TRAIN+VALIDATION兩期，比較加了gate後alpha顯著性跟
地雷率(mine_rate)有沒有改善。**N_RANDOM_DRAWS=100次隨機對照組本輪刻意跳過
不跑**——500檔規模單次真實回測已知要花數分鐘，加上F-score要對500檔各自
呼叫3個PIT函式（部分股票的CashFlowsStatement/FinancialStatements/
BalanceSheet本機parquet快取可能還沒有，需要新抓，遵守既有3秒節流），
「先確認方向性證據值不值得往下investPIT，再決定要不要投入完整100次隨機
對照組的計算成本」是刻意的分階段設計，不是忘記做，下一輪若這裡的方向性
結果有意義，才值得排隊補隨機控制組（第2關）。

**F-score門檻自適應選擇**：跟`HYPOTHESIS_QUEUE.md` #23「具體假設定義」
明講的「若候選池過薄則測F>=6」一致——先在TRAIN+VAL兩期各抽樣12個再平衡
日（跟REBALANCE_DAYS=21一致的頻率），量測F>=8/F>=7/F>=6三個門檻下，
`compute_scores_v2()`本身已經算好的value_board候選池（`eligible_for_
ranking_v2`過濾流動性不足後）裡還剩幾檔通過F-score門檻，挑選滿足
「平均候選數>=TOP_N(20)」的最嚴格門檻；三個門檻都不到20檔的話，退而
求其次選平均候選數最多的門檻並誠實記錄候選池偏薄這件事，不因為凑不滿
20檔就放寬到不合理的低門檻(F>=0這種形同虛設的閘門)。
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import START_DATE
from factors import _asof_join
from finmind_client import load_dev
from piotroski_fscore_sanity import _fscore_components
from run_value_board_v2_pit_backtest import (
    TOP_N, REBALANCE_DAYS, alpha_significance, compute_moonshot_stats,
    eligible_for_ranking_v2,
)
from score import load_industry_map
from score_v2 import compute_scores_v2
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

CACHE_PATH = Path(__file__).parent / "data" / "backtests" / "value_board_v2_sample_cache_liquidity500.pkl"
BASELINE_CSV = Path(__file__).parent / "data" / "value_board_v2_pit_backtest_liquidity500_full.csv"
THRESHOLD_CANDIDATES = [8, 7, 6]


def load_cache() -> dict[str, pd.DataFrame]:
    print(f"[fscore_gate#23] loading cached factor data from {CACHE_PATH} ...")
    with open(CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"[fscore_gate#23] {len(data)} stocks in cache")
    return data


def compute_fscore_lookup(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """對cache裡每一檔股票，用`piotroski_fscore_sanity.py`同一個
    `_fscore_components()`算逐季F-score，再asof-join回這檔股票自己的日曆
    （沿用cache本身的date欄位，不重新抓價格）。回傳{stock_id: DataFrame(date,
    f_piotroski_fscore, f_piotroski_n_components)}，跟`load_sample()`裡
    的asof-join邏輯一致但獨立成函式，這裡不需要重複抓價格。"""
    out = {}
    n_ok, n_empty, n_err = 0, 0, 0
    for i, (sid, d) in enumerate(data.items()):
        try:
            fs = _fscore_components(sid, START_DATE)
        except Exception as e:  # noqa: BLE001
            n_err += 1
            if n_err <= 5:
                print(f"    [{sid}] fscore ERROR: {e}")
            continue
        if fs.empty:
            n_empty += 1
            continue
        dd = d[["date"]].copy()
        dd = _asof_join(dd, fs, "fscore", "f_piotroski_fscore")
        dd = _asof_join(dd, fs, "n_components", "f_piotroski_n_components")
        out[sid] = dd
        n_ok += 1
        if (i + 1) % 100 == 0:
            print(f"    fscore progress {i+1}/{len(data)} (ok={n_ok} empty={n_empty} err={n_err})")
    print(f"[fscore_gate#23] fscore computed for {n_ok}/{len(data)} stocks "
          f"(empty_financials={n_empty}, errors={n_err})")
    return out


def _fscore_at(fscore_lookup: dict[str, pd.DataFrame], sid: str, as_of: str) -> float:
    d = fscore_lookup.get(sid)
    if d is None:
        return float("nan")
    idx = d.index[d["date"] == as_of]
    if len(idx) == 0:
        return float("nan")
    return float(d.loc[idx[0], "f_piotroski_fscore"]) if pd.notna(d.loc[idx[0], "f_piotroski_fscore"]) else float("nan")


def pick_threshold(data: dict, fscore_lookup: dict, industry_map: dict, sample_dates: list[str]) -> tuple[int, dict]:
    """在給定的抽樣再平衡日上，量測value_board候選池（已扣掉流動性不足）
    在各F-score門檻下還剩幾檔候選，回傳(挑選的門檻, {門檻: 平均候選數})。"""
    stats = {t: [] for t in THRESHOLD_CANDIDATES}
    for as_of in sample_dates:
        cs = compute_scores_v2(as_of, data, industry_map, START_DATE)
        cs = eligible_for_ranking_v2(cs)
        if cs.empty:
            for t in THRESHOLD_CANDIDATES:
                stats[t].append(0)
            continue
        fscores = np.array([_fscore_at(fscore_lookup, sid, as_of) for sid in cs.index])
        for t in THRESHOLD_CANDIDATES:
            stats[t].append(int(np.nansum(fscores >= t)))
    means = {t: float(np.mean(v)) if v else 0.0 for t, v in stats.items()}
    print(f"[fscore_gate#23] 門檻自適應量測（{len(sample_dates)}個抽樣再平衡日，"
          f"value_board已篩流動性後的候選池平均候選數）：{means}")
    viable = [t for t in THRESHOLD_CANDIDATES if means[t] >= TOP_N]
    chosen = max(viable) if viable else max(THRESHOLD_CANDIDATES, key=lambda t: means[t])
    if not viable:
        print(f"[fscore_gate#23] 警告：三個門檻(F>=8/7/6)在抽樣日的平均候選數都不到TOP_N={TOP_N}，"
              f"退而求其次選候選數最多的門檻F>={chosen}（誠實記錄候選池偏薄，"
              f"不代表gate機制有誤，是value_board已篩選過的候選池本身+F-score雙重篩選的必然結果）。")
    else:
        print(f"[fscore_gate#23] 選定門檻：F>={chosen}（平均候選數{means[chosen]:.1f}>=TOP_N={TOP_N}，"
              f"取滿足此條件裡最嚴格的門檻）")
    return chosen, means


def make_gated_signal_fn(industry_map: dict, start_date: str, top_n: int, fscore_lookup: dict, threshold: int):
    def signal_fn(price_data: dict, as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        cs = compute_scores_v2(as_of, price_data, industry_map, start_date)
        cs = eligible_for_ranking_v2(cs)
        if cs.empty or "total_score" not in cs.columns:
            return {}
        fscores = pd.Series({sid: _fscore_at(fscore_lookup, sid, as_of) for sid in cs.index})
        cs = cs[fscores >= threshold]
        if cs.empty:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(top_n)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


def run_period_gated(label: str, data: dict, market_df: pd.DataFrame, industry_map: dict,
                      fscore_lookup: dict, threshold: int, start: str, end: str) -> dict:
    print(f"\n=== {label} (F>={threshold} gate): {start}..{end} ===")
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_fscore_gated")
    fn = make_gated_signal_fn(industry_map, START_DATE, TOP_N, fscore_lookup, threshold)
    result = run_backtest(fn, data, market_df, cfg)
    print(f"  gated: return={result.total_return_pct:+.2f}%  MDD={result.max_drawdown_pct:.2f}%  "
          f"Sortino={result.sortino_ratio:.3f}  trades={result.n_trades}")

    alpha = alpha_significance(result.equity_curve, market_df)
    print(f"  alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta={alpha['beta']:+.3f}  "
          f"p={alpha['alpha_pvalue']:.4f}  顯著={alpha['alpha_significant']}（n={alpha['n_days']}天）")

    moonshot = compute_moonshot_stats(result.trades, data)
    print(f"  翻倍率={moonshot['moonshot_rate']}%  大賺率={moonshot['big_win_rate']}%  "
          f"地雷率={moonshot['mine_rate']}%（{moonshot['n_entries']}次進場事件）")

    return {
        "label": label, "gate_threshold": threshold, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "n_trades": result.n_trades,
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "moonshot_rate": moonshot["moonshot_rate"], "big_win_rate": moonshot["big_win_rate"],
        "mine_rate": moonshot["mine_rate"], "moonshot_n_entries": moonshot["n_entries"],
    }


def main() -> None:
    data = load_cache()
    fscore_lookup = compute_fscore_lookup(data)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in piotroski_fscore_gate_v1")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()

    any_calendar = sorted({d for df in data.values() for d in df["date"].tolist()})
    train_dates = [d for d in any_calendar if "2015-01-01" <= d <= holdout.TRAIN_END][::REBALANCE_DAYS][:12]
    val_dates = [d for d in any_calendar if "2021-01-01" <= d <= holdout.VAL_END][::REBALANCE_DAYS][:12]
    threshold, means = pick_threshold(data, fscore_lookup, industry_map, train_dates + val_dates)

    train_result = run_period_gated("TRAIN", data, market_df, industry_map, fscore_lookup, threshold,
                                     "2015-01-01", holdout.TRAIN_END)
    val_result = run_period_gated("VALIDATION", data, market_df, industry_map, fscore_lookup, threshold,
                                   "2021-01-01", holdout.VAL_END)

    print("\n=== 比較：原始value_board_v2 vs +F-score gate（皆為真實回測，非隨機對照組） ===")
    if BASELINE_CSV.exists():
        base = pd.read_csv(BASELINE_CSV)
        for _, b in base.iterrows():
            g = train_result if b["label"] == "TRAIN" else val_result
            print(f"  {b['label']}: 原始 alpha={b['alpha_ann_pct']:+.2f}%(p={b['alpha_pvalue']:.4f}) "
                  f"mine_rate={b['mine_rate']:.1f}%  return={b['return_pct']:+.2f}%  |  "
                  f"gated(F>={threshold}) alpha={g['alpha_ann_pct']:+.2f}%(p={g['alpha_pvalue']:.4f}) "
                  f"mine_rate={g['mine_rate']}%  return={g['return_pct']:+.2f}%")
    else:
        print(f"  警告：找不到基準檔{BASELINE_CSV}，無法列比較表，只有gated版本的原始輸出")

    out_path = Path(__file__).parent / "data" / "piotroski_fscore_gate_v1_results.csv"
    pd.DataFrame([train_result, val_result]).to_csv(out_path, index=False)
    print(f"\nsaved {out_path}")


if __name__ == "__main__":
    main()
