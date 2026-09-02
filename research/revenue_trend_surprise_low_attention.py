"""`HYPOTHESIS_QUEUE.md` #21 月營收「意外」漂移 x 低關注度：第1關 sanity（事件研究，分組）。

經濟理由見`HYPOTHESIS_QUEUE.md`#21完整說明。這條是`#14`（台股月營收公布事件效應，
純YoY意外，已FAIL，`TRIALS_LEDGER.md`#80）的改造版，**不是同一個假設重跑**，
兩處刻意做出的區隔：
①意外定義從「去年同月YoY」改成「相對trailing 12個月線性趨勢外推值的殘差」
（排除單純基期效應，更貼近PEAD文獻常用的「季節調整後意外」）；
②樣本切成「低關注度」/「高關注度」兩組分開跑cheap gate（用近20個交易日均成交值
[volume*close]分位當關注度代理——選這個而非法人持股比例，因為價格/成交量資料
已經是`adjusted_price_series()`現成欄位，法人持股比例需要額外抓`TaiwanStockShareholding`
或`TaiwanStockInstitutionalInvestorsBuySell`累計，第1關sanity先用最省成本的代理，
若這關過了、要往後面關卡走，才考慮換更精確的代理）。

判定邏輯（`HYPOTHESIS_QUEUE.md`#21原話）：若假設成立，應該**只有低關注度組
顯著、高關注度組不顯著或顯著較弱**——這個「分組差異」本身就是驗證證據。若兩組
都不顯著或都顯著（沒有分組差異），視同「改造沒有解決#14的根本問題」，依快殺
標準判FAIL，不需要勉強找理由續命。

沿用既有元件（不重新發明，跟`monthly_revenue_event_study.py`#14同一套骨架）：
`factor_ic.py::sample_universe_ids()`（同一個100檔快取樣本）、
`pit.py::month_revenue_pit()`（既有PIT邏輯）、
`adjust.py::adjusted_price_series()`（既有還原股價+VAL_END自動截斷）、
`validation.holdout`（TRAIN_END/VAL_END切分+holdout洩漏斷言）。

2026-09-03 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#21第1關起跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from pit import month_revenue_pit
from validation import holdout

FORWARD_HORIZON = 20  # trading days，跟#14同一個窗口，方便對照比較
TREND_TRAILING_MONTHS = 12  # trailing窗口，跟假設定義一致
N_PERMUTATIONS = 500
PERM_SEED = 20260903
BASE_ALPHA = 0.10
BONFERRONI_N = 1  # 每組分開跑standalone判準，不是額外新增比較次數（見docstring說明）
ATTENTION_WINDOW = 20  # 近20個交易日均成交值，關注度代理


def _revenue_trend_surprise(stock_id: str, start_date: str) -> pd.DataFrame:
    """相對trailing 12個月線性趨勢外推值的營收意外。

    對每個月t，用t-12..t-1這12個月的營收值做簡單線性迴歸（x=0..11），外推到
    第12步（即月t）得到trend_pred，意外=(實際-trend_pred)/|trend_pred|。跟
    `factors.py::_revenue_surprise_sue()`的YoY標準化是不同構造：那個比較「跟
    去年同月比較、再除以自身YoY歷史波動度標準化」，這個是「跟自身近期趨勢線
    外推值比較」，兩者對同一次營收公布給出的意外分數通常不同。
    """
    rev = month_revenue_pit(stock_id, start_date)
    if rev.empty:
        return pd.DataFrame(columns=["pit_date", "trend_surprise"])
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    revenue = rev["revenue"].to_numpy(dtype=float)
    n = len(revenue)
    surprise = np.full(n, np.nan)
    x = np.arange(TREND_TRAILING_MONTHS, dtype=float)
    for i in range(TREND_TRAILING_MONTHS, n):
        window = revenue[i - TREND_TRAILING_MONTHS:i]
        if np.any(np.isnan(window)):
            continue
        # 簡單線性迴歸外推：slope, intercept = polyfit(0..11, window, 1)；
        # 外推到第12步(x=12)當trend_pred。
        try:
            slope, intercept = np.polyfit(x, window, 1)
        except (np.linalg.LinAlgError, ValueError):
            continue
        trend_pred = slope * TREND_TRAILING_MONTHS + intercept
        actual = revenue[i]
        if trend_pred == 0 or np.isnan(trend_pred) or np.isnan(actual):
            continue
        surprise[i] = (actual - trend_pred) / abs(trend_pred)
    rev["trend_surprise"] = surprise
    return rev[["pit_date", "trend_surprise"]]


def _attention_proxy_at(px: pd.DataFrame, entry_idx: int) -> float:
    """近`ATTENTION_WINDOW`個交易日（entry之前，不含entry當天，避免用進場當下
    才知道的資訊）均成交值(volume*close)，關注度代理。低值=低關注度。

    `adjusted_price_series()`的volume欄位名依資料來源分岔（見該函式docstring）：
    yfinance路徑用小寫`volume`，FinMind回退路徑保留原始`Trading_Volume`欄位名
    （沒有重新命名，`factors.py`裡直接用`Trading_Volume`存取的既有慣例同理）。
    這裡兩種都要接受，不能只認其中一種，否則走FinMind路徑的股票會被整批丟棄。
    """
    start = entry_idx - ATTENTION_WINDOW
    if start < 0:
        return float("nan")
    window = px.iloc[start:entry_idx]
    if window.empty:
        return float("nan")
    vol_col = "volume" if "volume" in window.columns else "Trading_Volume"
    if vol_col not in window.columns or window[vol_col].isna().all() or window["close"].isna().all():
        return float("nan")
    dollar_vol = (window[vol_col].astype(float) * window["close"].astype(float)).mean()
    return float(dollar_vol) if pd.notna(dollar_vol) else float("nan")


def _stock_events(stock_id: str) -> pd.DataFrame:
    """單一股票的月營收公布事件表：pit_date, entry_date, trend_surprise,
    attention_proxy, fwd_ret。進場規則跟`monthly_revenue_event_study.py`#14
    同一個保守PIT處理：公布日之後第一個交易日進場（不是公布當天收盤價）。
    """
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟#14同一個容錯尺度，個股層級失敗不外溢
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return pd.DataFrame()
    if px.empty or len(px) < 260:
        return pd.DataFrame()
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in revenue_trend_surprise_low_attention")

    try:
        rev = _revenue_trend_surprise(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        print(f"  [{stock_id}] revenue ERROR ({e}), dropping")
        return pd.DataFrame()
    if rev.empty:
        return pd.DataFrame()

    px = px.sort_values("date").reset_index(drop=True)
    dates = px["date"].tolist()
    adj_close = px["adj_close"].tolist()

    rows = []
    for _, r in rev.iterrows():
        pit = r["pit_date"]
        surprise = r["trend_surprise"]
        if pd.isna(surprise) or pd.isna(pit):
            continue
        entry_idx = None
        for i, d in enumerate(dates):
            if d > pit:
                entry_idx = i
                break
        if entry_idx is None or entry_idx + FORWARD_HORIZON >= len(dates):
            continue
        p0 = adj_close[entry_idx]
        p1 = adj_close[entry_idx + FORWARD_HORIZON]
        if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        attn = _attention_proxy_at(px, entry_idx)
        if pd.isna(attn):
            continue
        rows.append({
            "stock_id": stock_id, "pit_date": pit, "entry_date": dates[entry_idx],
            "trend_surprise": float(surprise), "attention_proxy": attn,
            "fwd_ret": float(p1 / p0 - 1),
        })
    return pd.DataFrame(rows)


def _period_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p_value": float("nan")}
    rho, p = spearmanr(df["trend_surprise"], df["fwd_ret"])
    return {"label": label, "n": n, "ic": float(rho), "p_value": float(p)}


def _quintile_spread(df: pd.DataFrame) -> dict:
    if len(df) < 25:
        return {"n": len(df), "q_top_mean": float("nan"), "q_bottom_mean": float("nan"), "spread": float("nan")}
    d = df.copy()
    d["quintile"] = pd.qcut(d["trend_surprise"], 5, labels=False, duplicates="drop")
    top = d[d["quintile"] == d["quintile"].max()]["fwd_ret"].mean()
    bottom = d[d["quintile"] == d["quintile"].min()]["fwd_ret"].mean()
    return {"n": len(df), "q_top_mean": float(top), "q_bottom_mean": float(bottom), "spread": float(top - bottom)}


def _permutation_null_percentile(df: pd.DataFrame, real_ic: float, n_perm: int, seed: int) -> float:
    if len(df) < 10 or pd.isna(real_ic):
        return float("nan")
    rng = np.random.RandomState(seed)
    surprise = df["trend_surprise"].to_numpy()
    ret = df["fwd_ret"].to_numpy()
    abs_real = abs(real_ic)
    beaten = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(surprise)
        rho, _ = spearmanr(shuffled, ret)
        if pd.isna(rho):
            continue
        if abs(rho) <= abs_real:
            beaten += 1
    return 100.0 * beaten / n_perm


def _evaluate_group(events: pd.DataFrame, label: str) -> dict:
    """對一個子樣本（低關注度或高關注度）分別跑TRAIN/VAL cheap gate，
    跟`monthly_revenue_event_study.py`#14的`main()`同一套判準邏輯。
    """
    train = holdout.cap_to_train(events, date_col="entry_date")
    val = holdout.validation_slice(events, date_col="entry_date")

    train_stats = _period_stats(train, f"{label}/TRAIN")
    val_stats = _period_stats(val, f"{label}/VAL")

    train_q = _quintile_spread(train)
    val_q = _quintile_spread(val)

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )

    null_pct = _permutation_null_percentile(val, val_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)

    reasons = []
    if train_stats["n"] < 30 or val_stats["n"] < 30:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")

    passes = len(reasons) == 0

    print(f"\n--- {label} ---")
    print(f"TRAIN pooled Spearman IC={train_stats['ic']:+.4f} (p={train_stats['p_value']:.4f}, n={train_stats['n']})")
    print(f"VAL   pooled Spearman IC={val_stats['ic']:+.4f} (p={val_stats['p_value']:.4f}, n={val_stats['n']})")
    print(f"TRAIN quintile spread={train_q['spread']:+.4f} | VAL quintile spread={val_q['spread']:+.4f}")
    print(f"VAL |IC| vs {N_PERMUTATIONS}次洗牌null percentile={null_pct:.1f} (需要>={required_pct:.1f})")
    print(f"same_sign={same_sign} -> {label} {'PASS' if passes else 'FAIL'}" + (f" reasons: {reasons}" if reasons else ""))

    return {
        "label": label, "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "train_quintile": train_q, "val_quintile": val_q,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== 月營收「意外」漂移x低關注度 sanity (HYPOTHESIS_QUEUE.md#21, standalone bonferroni_n={BONFERRONI_N}) ===")
    print(f"Sample: {len(sample_ids)} names (SAMPLE_SEED={SAMPLE_SEED}), forward_horizon={FORWARD_HORIZON}交易日, "
          f"trend_trailing_months={TREND_TRAILING_MONTHS}, attention_window={ATTENTION_WINDOW}交易日")

    all_events = []
    n_ok = 0
    for i, sid in enumerate(sample_ids):
        ev = _stock_events(sid)
        if not ev.empty:
            all_events.append(ev)
            n_ok += 1
        if (i + 1) % 20 == 0:
            print(f"  progress {i+1}/{len(sample_ids)}, {n_ok} usable so far")

    if not all_events:
        print("SANITY FAIL: 零事件，資料層級有問題（不是無訊號，是抓取/解析有誤）。")
        return {"passes": False, "reason": "no_events"}

    events = pd.concat(all_events, ignore_index=True)
    holdout.assert_no_holdout_leakage(events, date_col="entry_date", context="revenue_trend_surprise_low_attention events (final)")
    print(f"\n{n_ok}/{len(sample_ids)} 檔股票有可用事件，總事件數={len(events)}")

    if events["trend_surprise"].isna().all() or events["fwd_ret"].isna().all():
        print("SANITY FAIL: trend_surprise或fwd_ret全部NaN。")
        return {"passes": False, "reason": "all_nan"}

    # 關注度分組：用全池事件的attention_proxy中位數做median split（sanity階段先
    # 用最簡單的切法，不分年度/不分期間再切，一次切到底）。
    median_attn = events["attention_proxy"].median()
    low_attn = events[events["attention_proxy"] <= median_attn].copy()
    high_attn = events[events["attention_proxy"] > median_attn].copy()
    print(f"\n關注度median split: median_dollar_volume_20d={median_attn:,.0f} "
          f"低關注度組n={len(low_attn)} | 高關注度組n={len(high_attn)}")

    low_result = _evaluate_group(low_attn, "低關注度")
    high_result = _evaluate_group(high_attn, "高關注度")

    # 分組差異判定（`HYPOTHESIS_QUEUE.md`#21明訂的核心驗證邏輯）：
    # 若假設成立，低關注度組應該通過cheap gate、高關注度組不通過或明顯較弱。
    differentiation = low_result["passes"] and not high_result["passes"]
    no_differentiation = low_result["passes"] == high_result["passes"]

    print("\n=== 分組差異判定 ===")
    print(f"低關注度組: {'PASS' if low_result['passes'] else 'FAIL'} | 高關注度組: {'PASS' if high_result['passes'] else 'FAIL'}")
    if differentiation:
        verdict = "CHEAP_PASS（分組差異符合假設：僅低關注度組通過）"
    elif no_differentiation:
        verdict = "FAIL（兩組判定相同，沒有分組差異，改造未解決#14根本問題）"
    else:
        verdict = "FAIL（高關注度組通過但低關注度組未通過，方向與假設相反）"
    print(f"最終判定: {verdict}")

    return {
        "differentiation": differentiation,
        "verdict": verdict,
        "low_attention": low_result,
        "high_attention": high_result,
        "n_events_total": len(events),
        "n_stocks_usable": n_ok,
        "median_attention": float(median_attn),
    }


if __name__ == "__main__":
    main()
