"""B25：回測regime標記與分情境報告（2026-09-02新增，BACKLOG.md B25規格）。

**任務範疇**（逐字對照BACKLOG.md「B25：回測regime標記與分情境報告」）：
1. 為B24回測框架的每個交易日標記市場情境：TAIEX收盤vs 200日均線判多空
   （上=多頭、下=空頭）；20日報酬絕對值<3%判盤整；60日滾動波動率落在
   歷史前20%判高波動（可與多空並存，形成組合標籤）。
2. B24報告新增「分情境績效表」：三個板（價值成長/題材動能/未來性）各自
   在每種情境下的年化報酬、勝率、MDD、隨機對照組百分位。
3. **只做報告，不做任何權重調整或情境切換邏輯**——這支腳本只算數字、
   只寫報告，不改`score_v2.py`/`generate_scores_live.py`任何權重或
   切換邏輯，也不新增任何「依情境切換選股」的程式碼路徑。

**範疇修正（沿用B24-500既有揭露，見`B24_RESULTS.md`）**：三個板只有「價值
成長板」（`score_v2.py`/`run_value_board_v2_pit_backtest.py`）有可回測的
逐日報酬序列可以套regime標籤。題材動能榜/未來性濾網（`score_live_
momentum.py`/`score_live_future.py`）只能讀今天的JSON快照算分數，沒有
PIT（point-in-time）回測引擎，沒辦法對歷史任意日期算分數——這不是這支
腳本要解決的問題（移植/新建PIT引擎是另一筆大工程，超出B25範疇），下面
報告對這兩板誠實記錄「無PIT引擎、暫不適用」。

**逐日序列從哪裡來（查證結果，見任務指示第1步）**：`run_value_board_v2_
pit_backtest.py`跑完後只把「彙總數字」（報酬%/MDD/Sharpe/alpha等）存進
`research/data/value_board_v2_pit_backtest_liquidity500_*_full.csv`，
逐日equity curve（`BacktestResult.equity_curve`）本身**沒有存檔**，用完
即丟；100次隨機對照組也只留每次draw的`final_equity`算百分位，同樣沒有
存逐日序列，甚至連100次的list本身都沒存檔。**但**500檔的因子資料本身
（`load_sample_with_factors()`的輸出，抓資料+算因子最貴的那一步，原本
約20分鐘＋依賴FinMind即時額度）已經快取成pickle
（`data/backtests/value_board_v2_sample_cache_liquidity500_clean.pkl`，
"clean"版是B24-500最終判定結論引用的post-atomic-write-fix版本，見
`B24_RESULTS.md`「供generate_strategies_json.py解析」區塊）。這支腳本
**直接複用這份既有因子快取**（不重新打FinMind、不重新跑`load_sample_
with_factors()`），只重跑`backtest.engine.run_backtest()`那層純計算
（真實策略訊號，不含隨機對照組），换取真正的逐日equity curve——這一步
是純本地計算（無網路請求），實測TRAIN+VALIDATION兩期合計約幾分鐘等級，
遠低於「重新整個回測一次」的規模。

**隨機對照組的誠實限制（任務指示明講的例外情況）**：如上一段所述，B24-500
的100次隨機draws**沒有存下任何逐日或逐次的報酬序列**，只留了最終的
彙總百分位數字（TRAIN/VALIDATION各100.0）。要拿到「隨機對照組在各情境下
的百分位」，必須重新完整跑一次100次draws並且這次要逐日存下每次draw的
equity curve（不能只存final_equity）——這跟B24-500原本100次draws的運算
量同等級（docstring記載約102秒/draw，100次×2期間先前實測約需數小時
等級），**超過任務指示「預期超過1小時，先如实記錄規模，做到能做的部分後
停在乾淨中繼點」的門檻，這支腳本刻意不做這一步**，分情境表的「隨機對照
組百分位」欄位一律誠實標記「不提供（原因見下方方法說明第4點）」，不假裝
算出數字。

**PIT限制誠實揭露（任務指示第2步明講要記錄）**：
- 200日均線多空、20日報酬盤整、60日滾動波動率**本身**（逐日算出的值）
  都只用當天以前的歷史資料，是因果（causal）、PIT安全的。
- 但「60日滾動波動率的歷史前20%」這個**門檻值**，是用整個樣本期間
  （2015-2024，橫跨TRAIN+VALIDATION兩期）的分布算80百分位數決定的——
  這代表對2015年當下來說，這個門檻其實用到了2024年才會出現的資訊，
  是non-PIT的簡化。這跟B24-500已有的「流動性排序用現在(2026-08)排序，
  固定套用全程回測」屬於同一等級的簡化，誠實揭露、不宣稱是嚴格PIT。
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from backtest.engine import BacktestConfig, run_backtest
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

# 沿用run_value_board_v2_pit_backtest.py同一組常數，確保這裡重跑出來的
# equity curve跟B24_RESULTS.md報告的彙總數字是同一套設定算出來的，不是
# 另外用一套參數對不上。
TOP_N = 20
REBALANCE_DAYS = 21
VALUE_BOARD_SAMPLE_SIZE = 500
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = Path(__file__).parent / "data" / "backtests" / \
    f"value_board_v2_sample_cache_liquidity{VALUE_BOARD_SAMPLE_SIZE}_clean.pkl"
START_DATE_FACTORS = "2010-01-01"  # factor_ic.START_DATE，跟因子快取內部一致

MARKET_MA_WINDOW = 200
RANGE_LOOKBACK_DAYS = 20
RANGE_THRESHOLD_PCT = 3.0
VOL_LOOKBACK_DAYS = 60
VOL_HIGH_PERCENTILE = 0.80  # 「歷史前20%」＝取60日波動率分布的第80百分位數為門檻
SAMPLE_MIN_DAYS = 20  # 少於這個天數的情境桶，誠實標「樣本不足」不硬湊數字


def compute_scores_v2_signal_fn(industry_map: dict[str, str], start_date: str, top_n: int = TOP_N):
    """跟run_value_board_v2_pit_backtest.py::make_score_v2_signal_fn()逐行
    一致，這裡自成一體複製一份（B25只讀不改B24腳本，避免耦合兩支腳本的
    生命週期）。"""
    from score_v2 import compute_scores_v2

    def signal_fn(price_data, as_of, market_df):
        cs = compute_scores_v2(as_of, price_data, industry_map, start_date)
        if "liquidity_insufficient" in cs.columns:
            cs = cs[~cs["liquidity_insufficient"]]
        if cs.empty or "total_score" not in cs.columns:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(top_n)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


def tag_market_regimes(market_df: pd.DataFrame) -> pd.DataFrame:
    """對TAIEX逐日算三個regime維度。輸入市場資料應已跑過holdout cap
    （<=VAL_END），這裡不重新抓資料。"""
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    d["close"] = d["close"].astype(float)

    # 1) 多空：收盤 vs 200日均線（PIT安全：只用當天以前的歷史）
    d["ma200"] = d["close"].rolling(MARKET_MA_WINDOW, min_periods=MARKET_MA_WINDOW).mean()
    d["trend_regime"] = np.where(
        d["ma200"].isna(), "資料不足前200日",
        np.where(d["close"] > d["ma200"], "多頭", "空頭"),
    )

    # 2) 盤整：20日報酬絕對值<3%（PIT安全）
    d["ret_20d"] = d["close"].pct_change(RANGE_LOOKBACK_DAYS) * 100
    d["range_regime"] = np.where(
        d["ret_20d"].isna(), "資料不足前20日",
        np.where(d["ret_20d"].abs() < RANGE_THRESHOLD_PCT, "盤整", "非盤整"),
    )

    # 3) 高波動：60日滾動波動率落在歷史前20%
    #    逐日的60日滾動波動率本身PIT安全（只用當天以前的日報酬算標準差），
    #    但「前20%」的門檻用整個樣本期間（2015-2024）的分布算，見模組
    #    docstring「PIT限制誠實揭露」——這一步用到了未來資料才能定門檻。
    daily_ret = d["close"].pct_change()
    d["vol_60d"] = daily_ret.rolling(VOL_LOOKBACK_DAYS, min_periods=VOL_LOOKBACK_DAYS).std() * np.sqrt(252) * 100
    sample_mask = (d["date"] >= "2015-01-01") & (d["date"] <= "2024-12-31")
    vol_threshold = d.loc[sample_mask, "vol_60d"].quantile(VOL_HIGH_PERCENTILE)
    d["vol_threshold_used"] = vol_threshold
    d["vol_regime"] = np.where(
        d["vol_60d"].isna(), "資料不足前60日",
        np.where(d["vol_60d"] >= vol_threshold, "高波動", "非高波動"),
    )

    # 組合標籤（多空 x 高波動，規格明講「可與多空並存」）
    def combo(row):
        if row["trend_regime"].startswith("資料不足") or row["vol_regime"].startswith("資料不足"):
            return "資料不足"
        return f"{row['trend_regime']}+{row['vol_regime']}"
    d["trend_vol_combo"] = d.apply(combo, axis=1)

    return d


def annualized_return_from_daily(returns: pd.Series) -> float:
    """年化報酬＝(1+平均日報酬)^252 - 1。這是用「這個情境桶裡所有天的
    平均日報酬」推算年化，不是這些天剛好連續發生的複利——因為情境桶的
    天數本來就不連續（例如「高波動」的天可能分散在2015跟2022），沒有
    連續複利的物理意義，用平均日報酬年化是這類條件式績效分析的標準做法，
    這裡明講公式，不含糊。"""
    if returns.empty:
        return float("nan")
    mean_r = returns.mean()
    return float((1 + mean_r) ** 252 - 1) * 100


def synthetic_mdd(returns_in_order: pd.Series) -> float:
    """情境桶MDD：把屬於這個情境的天數，依原始時間順序串接（跳過不屬於
    這個情境的天），算累積報酬曲線的最大回撤。**誠實揭露簡化**：這不是
    「策略在這個情境裡連續曝險的最大回撤」（因為天數本來就不連續，中間
    可能跳過大量不屬於這個情境的日子），而是「把這個情境的所有天，依
    發生順序串在一起會呈現的最大回撤」，是條件式風險的近似指標，不是
    嚴格意義的即時最大回撤。"""
    if returns_in_order.empty:
        return float("nan")
    curve = (1 + returns_in_order).cumprod()
    running_max = curve.cummax()
    dd = (curve - running_max) / running_max
    return float(dd.min() * 100)


def win_rate_from_daily(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    return float((returns > 0).mean() * 100)


def regime_bucket_stats(df: pd.DataFrame, label: str) -> dict:
    """df: 已依日期排序、篩到屬於這個情境的列，含daily_return欄位。"""
    n = len(df)
    if n < SAMPLE_MIN_DAYS:
        return {
            "regime": label, "n_days": n, "insufficient": True,
            "annualized_return_pct": None, "win_rate_pct": None, "mdd_pct": None,
            "random_control_percentile": "不提供（樣本不足<%d天，不硬湊數字）" % SAMPLE_MIN_DAYS,
        }
    rets = df.sort_values("date")["daily_return"]
    return {
        "regime": label, "n_days": n, "insufficient": False,
        "annualized_return_pct": round(annualized_return_from_daily(rets), 2),
        "win_rate_pct": round(win_rate_from_daily(rets), 1),
        "mdd_pct": round(synthetic_mdd(rets), 2),
        "random_control_percentile": "不提供（見腳本docstring「隨機對照組的誠實限制」：B24-500的100次draws未存逐日序列，重新產生規模達數小時等級，超出本次任務範圍）",
    }


def run_real_strategy_period(label: str, data: dict, market_df: pd.DataFrame,
                              industry_map: dict, start: str, end: str) -> pd.DataFrame:
    """重跑真實價值成長榜策略（不含隨機對照組），只為了拿到逐日equity
    curve。跟B24原始腳本用同一套BacktestConfig（TOP_N/REBALANCE_DAYS/
    預設成本模型），這樣算出來的日報酬序列跟B24_RESULTS.md的彙總數字
    是同一套方法論下的產物。"""
    t0 = time.time()
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_b25_regime")
    signal_fn = compute_scores_v2_signal_fn(industry_map, START_DATE_FACTORS, TOP_N)
    result = run_backtest(signal_fn, data, market_df, cfg)
    elapsed = time.time() - t0
    eq = result.equity_curve.copy()
    eq["daily_return"] = eq["equity"].pct_change()
    eq["period"] = label
    print(f"  [{label}] 重跑完成，耗時{elapsed:.1f}秒，"
          f"{len(eq)}個交易日，總報酬{result.total_return_pct:+.2f}%（應與B24_RESULTS.md對照一致或極接近）")
    return eq.dropna(subset=["daily_return"])


def main():
    print("=== B25 regime分情境報告：載入既有因子快取（不重新打FinMind）===")
    t0 = time.time()
    with open(CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    print(f"  載入 {CACHE_PATH.name}：{len(data)}檔，耗時{time.time()-t0:.1f}秒")

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2010-01-01")
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in b25_regime_report")
    market_df = prepare_market_data(market_raw)  # 附帶ma200/gate，跟B24同一套
    industry_map = load_industry_map()

    # 1) regime標記（用整段2010起的TAIEX資料算滾動指標，門檻限定在2015-2024樣本）
    tagged = tag_market_regimes(market_raw)
    vol_threshold = tagged["vol_threshold_used"].iloc[0]
    print(f"  高波動門檻（2015-2024樣本60日波動率第80百分位）＝{vol_threshold:.2f}%（年化）")

    # 2) 重跑真實策略拿逐日equity curve（TRAIN + VALIDATION，跟B24同期間）
    print("=== 重跑真實價值成長榜策略以取得逐日equity curve（不含隨機對照組）===")
    train_eq = run_real_strategy_period("TRAIN", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END)
    val_eq = run_real_strategy_period("VALIDATION", data, market_df, industry_map, "2021-01-01", holdout.VAL_END)
    combined = pd.concat([train_eq, val_eq], ignore_index=True)

    # 3) 併入regime標籤
    merged = combined.merge(
        tagged[["date", "trend_regime", "range_regime", "vol_regime", "trend_vol_combo"]],
        on="date", how="left",
    )
    n_missing_tag = merged["trend_regime"].isna().sum()
    if n_missing_tag:
        print(f"  警告：{n_missing_tag}天在策略equity curve裡但regime標記缺失（TAIEX當天無資料？），排除這些天")
        merged = merged.dropna(subset=["trend_regime"])

    # 4) 分情境算指標
    rows = []
    for dim_col, dim_name in [
        ("trend_regime", "多空"), ("range_regime", "盤整"),
        ("vol_regime", "波動"), ("trend_vol_combo", "多空x波動組合"),
    ]:
        for regime_value, sub in merged.groupby(dim_col):
            if str(regime_value).startswith("資料不足"):
                continue
            stats = regime_bucket_stats(sub, regime_value)
            stats["dimension"] = dim_name
            rows.append(stats)

    report_df = pd.DataFrame(rows)
    out_csv = Path(__file__).parent / "data" / "b25_regime_report_value_board.csv"
    report_df.to_csv(out_csv, index=False)
    print(f"\n已存檔：{out_csv}")
    print(report_df.to_string(index=False))

    return report_df, tagged, vol_threshold, merged


if __name__ == "__main__":
    main()
