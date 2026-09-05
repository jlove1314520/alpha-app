"""`HYPOTHESIS_QUEUE.md` #40 庫藏股買回公告效應：第1關cheap gate（CAR事件研究）。

經濟理由/完整假設定義見`HYPOTHESIS_QUEUE.md`#40條目。跟`monthly_revenue_event_study.py`
（#14，已FAIL）同一種「事件錨定窗口」設計，但判準改成協定第1節#40條目明訂的
「事件後CAR是否顯著大於0 + 贏過同一批公司隨機挑非公告日當偽事件日的控制組」
（而非cross-sectional Spearman IC，因為這裡沒有一個連續因子值可排序，只有
「有沒有發生事件」這個二元訊號）。

事件定義：以`board_resolution_date`（董事會決議日，公開資訊觀測站公告當下即為
市場最早可觀察時點，天然PIT-safe）為事件日T=0，進場規則沿用#14同一個保守PIT
處理（公告日之後第一個交易日進場，不用公告當天收盤價），持有`FORWARD_HORIZON`
交易日，CAR = 個股報酬 - 台股加權指數同期報酬（超額報酬，非原始報酬）。

樣本：買回事件涵蓋725檔不同股票（`load_all_cached()`），對每檔都抓還原股價
成本過高，第1關cheap gate先抽`SAMPLE_SIZE`檔（`SAMPLE_SEED`固定可重現），
`START_DATE`跟`factor_ic.py`同一個值（2010-01-01）以提高快取命中率。若第1關
過關，deep_dive才值得投入全樣本725檔。

隨機控制組：只在VAL期間（`TRAIN_END`< date <=`VAL_END`）內，對每檔有VAL期
事件的股票，抽跟真實事件數相同數量的隨機非公告日當偽事件日，重算CAR，重複
`N_PERMUTATIONS`次建立null分布，看真實VAL期mean_CAR贏過幾%——percentile>=90.0
才算贏過控制組，跟`monthly_revenue_event_study.py`的洗牌null同一個精神但改用
「隨機日期」而非「洗牌因子值」（因為這是事件研究，不是橫斷面排序）。

2026-09-06 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續（上一輪只完成資料
回補地基，本輪從第1關cheap gate開始）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp, wilcoxon

from adjust import adjusted_price_series
from finmind_client import load_dev
from mops_buyback_client import load_all_cached
from validation import holdout

FORWARD_HORIZON = 20  # trading days，跟#14同一個定義（HYPOTHESIS_QUEUE.md#40「第1關先測N=20交易日」）
SAMPLE_SIZE = 100
SAMPLE_SEED = 20260906
N_PERMUTATIONS = 200
PERM_SEED = 20260906
BASE_ALPHA = 0.10
BONFERRONI_N = 1  # standalone測試（這條佇列項目只測一個訊號）
START_DATE = "2010-01-01"  # 跟factor_ic.py同一個值，提高既有快取命中率


def _roc_to_ad(s: str) -> str | None:
    """民國年'YYY/MM/DD' -> 西元'YYYY-MM-DD'，格式不符回傳None（寧可丟棄不要誤解析）。"""
    try:
        y, m, d = s.split("/")
        y_ad = int(y) + 1911
        return f"{y_ad:04d}-{int(m):02d}-{int(d):02d}"
    except Exception:  # noqa: BLE001 -- 格式異常的原始資料列，丟棄比硬解更安全
        return None


def _load_events_sample() -> tuple[pd.DataFrame, list[str], int]:
    raw = load_all_cached()
    if raw.empty:
        return pd.DataFrame(), [], 0
    raw = raw.copy()
    raw["ad_date"] = raw["board_resolution_date"].apply(_roc_to_ad)
    raw = raw.dropna(subset=["ad_date", "stock_id"])
    all_ids = sorted(raw["stock_id"].unique())
    rng = random.Random(SAMPLE_SEED)
    sample_ids = rng.sample(all_ids, min(SAMPLE_SIZE, len(all_ids)))
    events = raw[raw["stock_id"].isin(sample_ids)].copy()
    return events, sample_ids, len(all_ids)


def _stock_price_map(stock_id: str) -> dict | None:
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟monthly_revenue_event_study.py同一個容錯尺度
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return None
    if px.empty or len(px) < 260:
        return None
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in buyback_car_gate")
    px = px.sort_values("date").reset_index(drop=True)
    return {"dates": px["date"].tolist(), "adj_close": px["adj_close"].to_numpy(dtype=float)}


def _market_map() -> dict:
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in buyback_car_gate")
    m = market_raw.sort_values("date").reset_index(drop=True)
    return {"dates": m["date"].tolist(), "close": m["close"].astype(float).to_numpy()}


def _entry_idx_after(dates: list[str], target: str) -> int | None:
    for i, d in enumerate(dates):
        if d > target:
            return i
    return None


def _car_for(dates, adj_close, mkt_date_idx: dict, mkt_close, entry_idx) -> float | None:
    if entry_idx is None or entry_idx + FORWARD_HORIZON >= len(dates):
        return None
    p0, p1 = adj_close[entry_idx], adj_close[entry_idx + FORWARD_HORIZON]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[entry_idx], dates[entry_idx + FORWARD_HORIZON]
    mi0, mi1 = mkt_date_idx.get(d0), mkt_date_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0:
        return None
    return stock_ret - (m1 / m0 - 1)


def _period_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "mean_car": float("nan"), "median_car": float("nan"),
                "p_ttest": float("nan"), "p_wilcoxon": float("nan")}
    car = df["car"].to_numpy()
    p_t = float(ttest_1samp(car, 0.0).pvalue)
    try:
        p_w = float(wilcoxon(car).pvalue)
    except Exception:  # noqa: BLE001 -- wilcoxon在n太小或全零時會拋錯，退回NaN不中止流程
        p_w = float("nan")
    return {"label": label, "n": n, "mean_car": float(np.mean(car)), "median_car": float(np.median(car)),
            "p_ttest": p_t, "p_wilcoxon": p_w}


def main():
    events, sample_ids, n_all_ids = _load_events_sample()
    print(f"=== 假設#40 庫藏股買回公告效應 CAR事件研究 第1關cheap gate ===")
    print(f"買回事件母體共{n_all_ids}檔不同股票，本輪抽樣{len(sample_ids)}檔"
          f"（SAMPLE_SEED={SAMPLE_SEED}），涉及事件{len(events)}筆，forward_horizon={FORWARD_HORIZON}交易日")

    mkt = _market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}

    price_cache: dict[str, dict] = {}
    rows = []
    n_ok = 0
    for i, sid in enumerate(sample_ids):
        pm = _stock_price_map(sid)
        if pm is None:
            continue
        price_cache[sid] = pm
        n_ok += 1
        sub = events[events["stock_id"] == sid]
        for _, r in sub.iterrows():
            entry_idx = _entry_idx_after(pm["dates"], r["ad_date"])
            car = _car_for(pm["dates"], pm["adj_close"], mkt_date_idx, mkt["close"], entry_idx)
            if car is None:
                continue
            rows.append({"stock_id": sid, "announce_date": r["ad_date"],
                         "entry_date": pm["dates"][entry_idx], "car": car})
        if (i + 1) % 25 == 0:
            print(f"  progress {i+1}/{len(sample_ids)}, {n_ok}檔可用價格, {len(rows)}筆事件可用 so far")

    if not rows:
        print("SANITY FAIL: 零事件可用（不是無訊號，是資料層有問題）。")
        return {"passes": False, "reason": "no_events"}

    ev = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev, date_col="entry_date", context="buyback_car_gate events (final)")
    print(f"\n{n_ok}/{len(sample_ids)}檔股票有可用價格，總可用事件數={len(ev)}")

    train = holdout.cap_to_train(ev, date_col="entry_date")
    val = holdout.validation_slice(ev, date_col="entry_date")

    train_stats = _period_stats(train, "TRAIN")
    val_stats = _period_stats(val, "VAL")
    print(f"\nTRAIN mean_CAR={train_stats['mean_car']:+.4f} median={train_stats['median_car']:+.4f} "
          f"(t-test p={train_stats['p_ttest']:.4f}, wilcoxon p={train_stats['p_wilcoxon']:.4f}, n={train_stats['n']})")
    print(f"VAL   mean_CAR={val_stats['mean_car']:+.4f} median={val_stats['median_car']:+.4f} "
          f"(t-test p={val_stats['p_ttest']:.4f}, wilcoxon p={val_stats['p_wilcoxon']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["mean_car"]) and not pd.isna(val_stats["mean_car"])
        and np.sign(train_stats["mean_car"]) == np.sign(val_stats["mean_car"]) and train_stats["mean_car"] != 0
    )

    # 隨機日期控制組：只在VAL期間內，對每檔有VAL期事件的股票，抽相同數量的隨機
    # 非公告日重算CAR，比照協定第2節精神但控制組維度是「日期」不是「標的」。
    rng = np.random.RandomState(PERM_SEED)
    val_events_by_stock = val.groupby("stock_id").size().to_dict()
    perm_means = []
    for _ in range(N_PERMUTATIONS):
        pseudo_cars = []
        for sid, cnt in val_events_by_stock.items():
            pm = price_cache.get(sid)
            if pm is None:
                continue
            dates = pm["dates"]
            valid_idx = [i for i, d in enumerate(dates)
                         if holdout.TRAIN_END < d <= holdout.VAL_END and i + FORWARD_HORIZON < len(dates)]
            if not valid_idx:
                continue
            picks = rng.choice(valid_idx, size=min(cnt, len(valid_idx)), replace=False)
            for idx in picks:
                car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt["close"], int(idx))
                if car is not None:
                    pseudo_cars.append(car)
        if pseudo_cars:
            perm_means.append(float(np.mean(pseudo_cars)))
    perm_means = np.array(perm_means)

    real_val_mean = val_stats["mean_car"]
    if len(perm_means) > 0 and not pd.isna(real_val_mean):
        null_pct = 100.0 * float(np.mean(perm_means <= real_val_mean))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"\nVAL mean_CAR={real_val_mean:+.4f} vs {len(perm_means)}次隨機日期控制組null分布"
          f"percentile={null_pct:.1f}（需要>={required_pct:.1f}）")
    print(f"same_sign(TRAIN/VAL)={same_sign}")

    reasons = []
    if train_stats["n"] < 30 or val_stats["n"] < 30:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(val_stats["mean_car"]) or val_stats["mean_car"] <= 0:
        reasons.append("VAL期mean_CAR非正（事前綁定方向為正）")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    if pd.isna(val_stats["p_ttest"]) or val_stats["p_ttest"] >= BASE_ALPHA:
        reasons.append(f"VAL t-test p={val_stats['p_ttest']:.4f}未達顯著水準({BASE_ALPHA})")

    passes = len(reasons) == 0
    print(f"\n=== CHEAP GATE {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    return {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign, "n_stocks_usable": n_ok, "n_events_usable": len(ev),
    }


if __name__ == "__main__":
    main()
