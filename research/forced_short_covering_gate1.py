"""`HYPOTHESIS_QUEUE.md` #51 子事件1（融券強制回補）第1關cheap gate。

**經濟機制（跟已測過的#30/#36不同，這是事件條件式交互作用，不是重測）**：
`#30`(`f_margin_utilization`)、`#36`(`f_short_sale_utilization`)測的是「融資/融券
使用率」對**未來所有時點**報酬的橫斷面預測力——那是連續、無條件的訊號。這裡測的
是完全不同的機制：融券餘額只有在股票即將進入**強制回補視窗**（除權息停止過戶
前，法規強制放空者回補）時才會轉成被迫買盤，其他時間融券餘額高低不代表任何
強制交易壓力。**預測：同樣是「事件窗口內的超額報酬」，融券餘額（部位大小）越高
的股票，窗口內超額報酬應該越高**——因為回補的buying pressure跟需要回補的股數
成正比。這是`#51`「有一群人不管價格都必須交易，且日期事前已知」的核心主張，
不是重新包裝已FAIL/PASS的無條件融券使用率因子。

**反推公式（`TW_MARATHON_STATE.md`第420/421輪、`HYPOTHESIS_QUEUE.md`#51條目(b)(c)
已用2330/1808兩檔真實個股核對通過，本檔第一次寫成可重複執行的函式）**：
`停止過戶日 = CashExDividendTradingDate 之後第2個交易日`
`強制回補視窗 = [停止過戶日的前6個交易日, 停止過戶日的前3個交易日]`（4個交易日，
含頭尾）。交易日一律用該股票自己的價格序列（`adjusted_price_series`）當日曆，
不用一般行事曆營業日——除息日、停止過戶日都是以「該市場的實際交易日」計數，
用一般行事曆日會在遇到國定假日時算錯。

只涵蓋**現金股利**除息事件（`CashExDividendTradingDate`），股票股利/減資版
（`StockExDividendTradingDate`）尚未驗證，不在本輪範圍內（同`HYPOTHESIS_QUEUE.md`
#51條目(c)第4點的既定限制）。

**控制組/顯著性檢定**：沿用`buyback_car_gate.py`（#40）同一種「事件錨定CAR」
框架，但預測變數是連續的（`short_ratio`＝事件窗口開始前最近一筆
`ShortSaleTodayBalance/ShortSaleLimit`），改用Spearman IC（跟`factor_ic.py`
同一種判準）而非單樣本CAR>0檢定——因為這裡要驗證的是「短天期融券部位大小
是否預測窗口內超額報酬」這個橫斷面關係，不是「窗口內平均超額報酬是否>0」
（後者可能混雜除息本身的其他已知效應，不是我們宣稱的機制）。
Null分布：VAL期把`short_ratio`標籤洗牌N次重算Spearman IC，percentile>=90.0
才算贏過隨機控制組（跟其餘cheap gate同一個alpha=0.10單邊門檻，
standalone測試不做Bonferroni）。

宇宙：`factor_ic.py::sample_universe_ids(SAMPLE_SIZE)`同一個300檔樣本
（`SAMPLE_SEED`不變），跟`#30`/`#36`同一個宇宙以利跨因子比較，248/300已有
本機融券快取，其餘52檔本輪會新抓（正常FinMind免費層呼叫量，非批次濫用）。

2026-09-07 馬拉松第422輪(TW軌)，接續round420「下一步(iii)」設計#51第1關
cheap gate（先以子事件1強制回補，因子事件1已在round419/420/421確認公式
可行且用真實個股驗證通過）。
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
from finmind_client import load_dev
from validation import holdout

N_PERMUTATIONS = 200
PERM_SEED = 20260907
BASE_ALPHA = 0.10
MIN_EVENTS_PER_PERIOD = 30


def _stop_transfer_and_window(dates: list[str], ex_date: str) -> tuple[int, int] | None:
    """回傳(window_start_idx, window_end_idx)，皆為dates的index，若資料不足回傳None。"""
    try:
        ex_idx = dates.index(ex_date)
    except ValueError:
        return None
    stop_transfer_idx = ex_idx + 2
    window_start_idx = stop_transfer_idx - 6
    window_end_idx = stop_transfer_idx - 3
    if window_start_idx < 0 or window_end_idx >= len(dates) or window_end_idx <= window_start_idx:
        return None
    return window_start_idx, window_end_idx


def _stock_price_map(stock_id: str) -> dict | None:
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟buyback_car_gate.py同一個容錯尺度
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return None
    if px.empty or len(px) < 260:
        return None
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in forced_short_covering_gate1")
    px = px.sort_values("date").reset_index(drop=True)
    return {"dates": px["date"].tolist(), "adj_close": px["adj_close"].to_numpy(dtype=float)}


def _dividend_events(stock_id: str) -> list[str]:
    raw = load_dev("TaiwanStockDividend", stock_id, START_DATE)
    if raw.empty or "CashExDividendTradingDate" not in raw.columns:
        return []
    ex_dates = raw["CashExDividendTradingDate"].replace("", None).dropna().unique().tolist()
    return sorted(ex_dates)


def _short_ratio_series(stock_id: str) -> pd.DataFrame:
    raw = load_dev("TaiwanStockMarginPurchaseShortSale", stock_id, START_DATE)
    if raw.empty:
        return pd.DataFrame(columns=["date", "short_ratio"])
    needed = {"date", "ShortSaleTodayBalance", "ShortSaleLimit"}
    if not needed.issubset(raw.columns):
        return pd.DataFrame(columns=["date", "short_ratio"])
    d = raw[["date", "ShortSaleTodayBalance", "ShortSaleLimit"]].copy()
    d["ShortSaleTodayBalance"] = pd.to_numeric(d["ShortSaleTodayBalance"], errors="coerce")
    d["ShortSaleLimit"] = pd.to_numeric(d["ShortSaleLimit"], errors="coerce")
    d = d[d["ShortSaleLimit"] > 0]
    if d.empty:
        return pd.DataFrame(columns=["date", "short_ratio"])
    d["short_ratio"] = d["ShortSaleTodayBalance"] / d["ShortSaleLimit"]
    return d[["date", "short_ratio"]].sort_values("date").reset_index(drop=True)


def _short_ratio_as_of(short_df: pd.DataFrame, as_of_date: str) -> float | None:
    """最近一筆日期 <= as_of_date的short_ratio，PIT安全（事件窗口開始前已知的部位大小）。"""
    if short_df.empty:
        return None
    prior = short_df[short_df["date"] <= as_of_date]
    if prior.empty:
        return None
    return float(prior.iloc[-1]["short_ratio"])


def _market_map() -> dict:
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in forced_short_covering_gate1")
    m = market_raw.sort_values("date").reset_index(drop=True)
    return {"dates": m["date"].tolist(), "close": m["close"].astype(float).to_numpy()}


def _car_for(dates, adj_close, mkt_date_idx, mkt_close, i0: int, i1: int) -> float | None:
    p0, p1 = adj_close[i0], adj_close[i1]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[i0], dates[i1]
    mi0, mi1 = mkt_date_idx.get(d0), mkt_date_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0:
        return None
    return stock_ret - (m1 / m0 - 1)


def _ic_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p": float("nan")}
    rho, p = spearmanr(df["short_ratio"], df["car"])
    return {"label": label, "n": n, "ic": float(rho), "p": float(p)}


def main():
    universe = sample_universe_ids(SAMPLE_SIZE)
    print("=== 假設#51子事件1(融券強制回補) 事件條件式短天期IC 第1關cheap gate ===")
    print(f"宇宙: factor_ic同一個{len(universe)}檔樣本 (SAMPLE_SEED={SAMPLE_SEED})")

    mkt = _market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}

    rows = []
    n_price_ok = 0
    n_events_total = 0
    for i, sid in enumerate(universe):
        pm = _stock_price_map(sid)
        if pm is None:
            continue
        n_price_ok += 1
        ex_dates = _dividend_events(sid)
        if not ex_dates:
            continue
        short_df = _short_ratio_series(sid)
        dates = pm["dates"]
        for ex_date in ex_dates:
            n_events_total += 1
            win = _stop_transfer_and_window(dates, ex_date)
            if win is None:
                continue
            i0, i1 = win
            short_ratio = _short_ratio_as_of(short_df, dates[i0])
            if short_ratio is None:
                continue
            car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt["close"], i0, i1)
            if car is None:
                continue
            rows.append({
                "stock_id": sid, "ex_date": ex_date,
                "window_start": dates[i0], "window_end": dates[i1],
                "short_ratio": short_ratio, "car": car,
            })
        if (i + 1) % 50 == 0:
            print(f"  progress {i+1}/{len(universe)}, {n_price_ok}檔有價格, {len(rows)}筆事件可用 so far")

    if not rows:
        print("SANITY FAIL: 零事件可用（不是無訊號，是資料層有問題）。")
        return {"passes": False, "reason": "no_events"}

    ev = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev, date_col="window_end", context="forced_short_covering_gate1 events (final)")
    print(f"\n{n_price_ok}/{len(universe)}檔股票有可用價格，現金股利除息事件共{n_events_total}筆，"
          f"其中窗口+融券資料皆可用事件數={len(ev)}")
    print(f"short_ratio: mean={ev['short_ratio'].mean():.5f} median={ev['short_ratio'].median():.5f} "
          f"share_zero={(ev['short_ratio'] == 0).mean():.1%}")

    train = holdout.cap_to_train(ev, date_col="window_end")
    val = holdout.validation_slice(ev, date_col="window_end")

    train_stats = _ic_stats(train, "TRAIN")
    val_stats = _ic_stats(val, "VAL")
    print(f"\nTRAIN IC={train_stats['ic']:+.4f} (p={train_stats['p']:.4f}, n={train_stats['n']})")
    print(f"VAL   IC={val_stats['ic']:+.4f} (p={val_stats['p']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )

    rng = np.random.RandomState(PERM_SEED)
    val_short = val["short_ratio"].to_numpy()
    val_car = val["car"].to_numpy()
    perm_ics = []
    if len(val) >= 10:
        for _ in range(N_PERMUTATIONS):
            shuffled = rng.permutation(val_short)
            rho, _ = spearmanr(shuffled, val_car)
            if not np.isnan(rho):
                perm_ics.append(float(rho))
    perm_ics = np.array(perm_ics)

    real_val_ic = val_stats["ic"]
    if len(perm_ics) > 0 and not pd.isna(real_val_ic):
        null_pct = 100.0 * float(np.mean(perm_ics <= real_val_ic))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA)
    print(f"\nVAL IC={real_val_ic:+.4f} vs {len(perm_ics)}次洗牌控制組null分布"
          f"percentile={null_pct:.1f}（需要>={required_pct:.1f}）")
    print(f"same_sign(TRAIN/VAL)={same_sign}")

    # 額外經濟解讀：VAL期短ratio四分位分組的mean_car（不是判準，供判讀用）
    if len(val) >= 20:
        val_q = val.copy()
        val_q["q"] = pd.qcut(val_q["short_ratio"].rank(method="first"), 4, labels=False)
        q_means = val_q.groupby("q")["car"].mean()
        print(f"VAL四分位mean_CAR (q0最低short_ratio -> q3最高): {q_means.to_dict()}")

    reasons = []
    if train_stats["n"] < MIN_EVENTS_PER_PERIOD or val_stats["n"] < MIN_EVENTS_PER_PERIOD:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(val_stats["ic"]) or val_stats["ic"] <= 0:
        reasons.append("VAL期IC非正（事前綁定方向為正：短天期融券部位越大，強制回補窗口內超額報酬應越高）")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    if pd.isna(val_stats["p"]) or val_stats["p"] >= BASE_ALPHA:
        reasons.append(f"VAL Spearman p={val_stats['p']:.4f}未達顯著水準({BASE_ALPHA})")

    passes = len(reasons) == 0
    print(f"\n=== CHEAP GATE {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    return {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign, "n_stocks_usable": n_price_ok, "n_events_usable": len(ev),
    }


if __name__ == "__main__":
    main()
