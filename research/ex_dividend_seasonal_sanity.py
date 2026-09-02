"""`HYPOTHESIS_QUEUE.md` #24 除權息季節行為效應：第1關 sanity（事件研究設計）。

經濟理由：台股7-9月除權息旺季存在散戶「填息」信念+稅制驅動的棄息/參與行為
（股利所得併入綜合所得稅+二代健保補充保費，高稅率族群傾向棄息賣出）。詳見
`HYPOTHESIS_QUEUE.md` #24完整說明。

**跟既有pipeline的關鍵差異（必須注意，這是這條假設的方法論核心）**：這裡刻意
用`load_dev("TaiwanStockPrice", ...)`的**原始未還原收盤價**，不是
`adjust.py::adjusted_price_series()`的還原股價——還原股價會把除息當天的價格
缺口用因子倒推「補平」，讓「填息/棄息」這個現象在資料上直接消失（定義上就是
還原股價存在的目的），如果誤用還原股價，這整條假設會變成結構性no-op（觀測不到
任何缺口，因為缺口已經被還原掉了）。務必用原始收盤價才能觀察到真實的除息缺口
與填息過程。

沿用既有元件（不重新發明）：
- `adjust.py::adjustment_events()`——已經算好每個除權息事件的`ex_date`/
  `prev_trading_date`/`factor`/`cash`/`stock_ratio`，本腳本直接複用這個既有
  函式取得事件清單，不重新解析`TaiwanStockDividend`。
- `factor_ic.py::sample_universe_ids()`（同一個100檔快取樣本，SAMPLE_SEED=
  20260822，沿用既有快取節省重抓）。
- `validation.holdout`（TRAIN_END/VAL_END切分+holdout洩漏斷言）。

判定範圍（第1關sanity，非最終判定）：
1. 事件數量與月份分布是否合理（不是零事件、且7-9月應明顯集中，這是台股已知的
   結構性事實，若資料呈現的分布跟這個已知事實不符，代表資料/解析有問題）。
2. 除息當日觀測跌幅是否跟理論殖利率（cash/pre_close）正相關（資料完整性
   sanity，不是策略訊號本身）。
3. 兩個cheap IC測試（各自TRAIN/VAL同號+贏過洗牌null percentile>=90.0，
   standalone bonferroni_n=1，跟本佇列既有cheap gate腳本同一把尺）：
   (a) 殖利率 → 除息前PRE_WINDOW個交易日報酬（測試「棄息殺盤」：高殖利率/
       高稅負股票除息前是否有更明顯的賣壓）。
   (b) 殖利率 → 除息後FORWARD_HORIZON個交易日報酬（測試「填息」：高殖利率
       股票除息後是否有更強/更弱的價格漂移）。
4. 填息率描述統計（多個horizon：20/60/120交易日，全樣本+依季節分組），純
   描述性、本輪不對填息率本身做統計檢定（若第1關過關、值得投入portfolio層
   follow-up時再做）。

2026-09-03 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#24第1關起跑。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjustment_events
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from finmind_client import load_dev
from validation import holdout

PRE_WINDOW = 5  # trading days before ex_date，測試棄息殺盤
FORWARD_HORIZON = 20  # trading days after ex_date，測試填息漂移（跟#14/#21同一個窗口方便比較）
FILL_HORIZONS = (20, 60, 120)  # trading days，填息率描述統計用的多個視窗
N_PERMUTATIONS = 500  # 沿用#14同一個規模，池化事件層級相關性計算便宜
PERM_SEED = 20260903
BASE_ALPHA = 0.10
BONFERRONI_N = 1  # standalone測試
IN_SEASON_MONTHS = {7, 8, 9}  # 台股除權息旺季


def _stock_events(stock_id: str) -> pd.DataFrame:
    """單一股票的除權息事件表：ex_date, div_yield, pre_ret, fwd_ret, fill_days_*,
    month, in_season。刻意只保留純現金股利事件（stock_ratio==0），避免股票股利/
    減資混在一起稀釋殖利率的經濟意義（`HYPOTHESIS_QUEUE.md`#24原始定義本身就是
    「現金股利/股價」）。
    """
    try:
        events = adjustment_events(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟本佇列既有腳本同一個容錯尺度
        print(f"  [{stock_id}] adjustment_events ERROR ({e}), dropping")
        return pd.DataFrame()
    if events.empty:
        return pd.DataFrame()
    events = events[(events["cash"] > 0) & (events["stock_ratio"] == 0)]
    if events.empty:
        return pd.DataFrame()

    try:
        raw = load_dev("TaiwanStockPrice", stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return pd.DataFrame()
    if raw.empty or len(raw) < 260:
        return pd.DataFrame()
    raw = raw.sort_values("date").reset_index(drop=True)
    holdout.assert_no_holdout_leakage(raw, context=f"raw price {stock_id} in ex_dividend_seasonal_sanity")
    dates = raw["date"].tolist()
    closes = raw["close"].astype(float).tolist()
    date_to_idx = {d: i for i, d in enumerate(dates)}

    rows = []
    for _, r in events.iterrows():
        ex_date = r["ex_date"]
        prev_date = r["prev_trading_date"]
        cash = float(r["cash"])
        ex_idx = date_to_idx.get(ex_date)
        prev_idx = date_to_idx.get(prev_date)
        if ex_idx is None or prev_idx is None:
            continue
        pre_close = closes[prev_idx]
        ex_close = closes[ex_idx]
        if pd.isna(pre_close) or pd.isna(ex_close) or pre_close <= 0:
            continue
        div_yield = cash / pre_close
        observed_drop = (pre_close - ex_close) / pre_close

        # 除息前PRE_WINDOW個交易日報酬（棄息殺盤測試）
        pre_window_idx = prev_idx - PRE_WINDOW
        if pre_window_idx < 0:
            pre_ret = float("nan")
        else:
            p0 = closes[pre_window_idx]
            pre_ret = (pre_close / p0 - 1) if (p0 and p0 > 0 and not pd.isna(p0)) else float("nan")

        # 除息後FORWARD_HORIZON個交易日報酬（填息漂移測試）
        fwd_idx = ex_idx + FORWARD_HORIZON
        if fwd_idx >= len(closes):
            fwd_ret = float("nan")
        else:
            p1 = closes[fwd_idx]
            fwd_ret = (p1 / ex_close - 1) if (p1 and p1 > 0 and not pd.isna(p1)) else float("nan")

        # 多視窗填息天數：從ex_idx往後找第一個raw close >= pre_close的交易日
        fill_flags = {}
        max_h = max(FILL_HORIZONS)
        filled_day = None
        for h in range(1, max_h + 1):
            idx = ex_idx + h
            if idx >= len(closes):
                break
            c = closes[idx]
            if not pd.isna(c) and c >= pre_close:
                filled_day = h
                break
        for h in FILL_HORIZONS:
            fill_flags[f"filled_{h}d"] = bool(filled_day is not None and filled_day <= h)

        month = int(ex_date[5:7])
        rows.append({
            "stock_id": stock_id, "ex_date": ex_date, "div_yield": div_yield,
            "observed_drop": observed_drop, "pre_ret": pre_ret, "fwd_ret": fwd_ret,
            "month": month, "in_season": month in IN_SEASON_MONTHS,
            "filled_day": filled_day,
            **fill_flags,
        })
    return pd.DataFrame(rows)


def _pooled_ic(df: pd.DataFrame, x_col: str, y_col: str, label: str) -> dict:
    d = df.dropna(subset=[x_col, y_col])
    n = len(d)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p_value": float("nan")}
    rho, p = spearmanr(d[x_col], d[y_col])
    return {"label": label, "n": n, "ic": float(rho), "p_value": float(p)}


def _permutation_null_percentile(df: pd.DataFrame, x_col: str, y_col: str, real_ic: float,
                                  n_perm: int, seed: int) -> float:
    d = df.dropna(subset=[x_col, y_col])
    if len(d) < 10 or pd.isna(real_ic):
        return float("nan")
    rng = np.random.RandomState(seed)
    x = d[x_col].to_numpy()
    y = d[y_col].to_numpy()
    abs_real = abs(real_ic)
    beaten = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(x)
        rho, _ = spearmanr(shuffled, y)
        if pd.isna(rho):
            continue
        if abs(rho) <= abs_real:
            beaten += 1
    return 100.0 * beaten / n_perm


def _evaluate_relationship(train: pd.DataFrame, val: pd.DataFrame, x_col: str, y_col: str, label: str) -> dict:
    train_stats = _pooled_ic(train, x_col, y_col, "TRAIN")
    val_stats = _pooled_ic(val, x_col, y_col, "VAL")
    print(f"\n[{label}] TRAIN IC={train_stats['ic']:+.4f} (p={train_stats['p_value']:.4f}, n={train_stats['n']})")
    print(f"[{label}] VAL   IC={val_stats['ic']:+.4f} (p={val_stats['p_value']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )
    null_pct = _permutation_null_percentile(val, x_col, y_col, val_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"[{label}] VAL |IC| vs {N_PERMUTATIONS}次洗牌null percentile={null_pct:.1f} (需要>={required_pct:.1f}), same_sign={same_sign}")

    reasons = []
    if train_stats["n"] < 30 or val_stats["n"] < 30:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    passes = len(reasons) == 0
    print(f"[{label}] {'CHEAP_PASS' if passes else 'FAIL'}" + (f"  reasons: {reasons}" if reasons else ""))
    return {
        "label": label, "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct, "same_sign": same_sign,
    }


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== 除權息季節行為效應 sanity (HYPOTHESIS_QUEUE.md#24, standalone bonferroni_n={BONFERRONI_N}) ===")
    print(f"Sample: {len(sample_ids)} names (SAMPLE_SEED={SAMPLE_SEED}), "
          f"pre_window={PRE_WINDOW}交易日, forward_horizon={FORWARD_HORIZON}交易日, 用原始未還原收盤價")

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
    holdout.assert_no_holdout_leakage(events, date_col="ex_date", context="ex_dividend_seasonal_sanity events (final)")
    print(f"\n{n_ok}/{len(sample_ids)} 檔股票有可用現金股利除息事件，總事件數={len(events)}")

    # --- sanity 1: 月份分布，7-9月應明顯集中（台股已知結構事實） ---
    month_counts = events["month"].value_counts().sort_index()
    season_frac = events["in_season"].mean()
    print(f"\n月份分布：\n{month_counts.to_string()}")
    print(f"7-9月旺季事件佔比={season_frac:.1%}")

    # --- sanity 2: 除息當日觀測跌幅 vs 理論殖利率，資料完整性檢查 ---
    drop_yield_rho, drop_yield_p = spearmanr(events["div_yield"], events["observed_drop"])
    print(f"\n除息觀測跌幅 vs 理論殖利率 Spearman rho={drop_yield_rho:+.4f} (p={drop_yield_p:.4f}, n={len(events)}) "
          f"[資料完整性sanity，非策略訊號本身，應強正相關]")

    train = holdout.cap_to_train(events, date_col="ex_date")
    val = holdout.validation_slice(events, date_col="ex_date")
    n_years_train = train["ex_date"].str.slice(0, 4).nunique() if not train.empty else 0
    n_years_val = val["ex_date"].str.slice(0, 4).nunique() if not val.empty else 0
    print(f"\nTRAIN: {len(train)}筆事件跨{n_years_train}年 | VAL: {len(val)}筆事件跨{n_years_val}年")

    if len(train) < 10 or len(val) < 10:
        print("SANITY FAIL: TRAIN或VAL事件數過少，無法做後續cheap gate測試。")
        return {"passes": False, "reason": "insufficient_train_val_events",
                "n_events": len(events), "n_stocks_usable": n_ok,
                "month_counts": month_counts.to_dict(), "season_frac": float(season_frac)}

    # --- cheap gate (a): 殖利率 → 除息前報酬（棄息殺盤） ---
    pre_result = _evaluate_relationship(train, val, "div_yield", "pre_ret", "殖利率→除息前報酬(棄息殺盤)")
    # --- cheap gate (b): 殖利率 → 除息後報酬（填息漂移） ---
    fwd_result = _evaluate_relationship(train, val, "div_yield", "fwd_ret", "殖利率→除息後報酬(填息漂移)")

    # --- 填息率：旺季 vs 非旺季，本佇列#24最核心的季節性主張，用洗牌置換檢定
    #     （打亂in_season標籤、保留filled標籤邊際分布，測真實的旺季/非旺季填息率差
    #     贏過幾%的隨機分組——比單純的div_yield IC測試更直接對應#24的經濟理由本身，
    #     不是「殖利率大小」而是「時間點是否落在稅制驅動的旺季」） ---
    print("\n填息率：旺季(7-9月) vs 非旺季，洗牌置換檢定（N=" + str(N_PERMUTATIONS) + "）：")
    season_gates = {}
    rng = np.random.RandomState(PERM_SEED)
    in_season_mask = events["in_season"].to_numpy()
    for h in FILL_HORIZONS:
        col = f"filled_{h}d"
        filled = events[col].to_numpy().astype(float)
        in_rate = filled[in_season_mask].mean()
        off_rate = filled[~in_season_mask].mean()
        real_diff = in_rate - off_rate
        beaten = 0
        for _ in range(N_PERMUTATIONS):
            shuffled_mask = rng.permutation(in_season_mask)
            perm_diff = filled[shuffled_mask].mean() - filled[~shuffled_mask].mean()
            if abs(perm_diff) <= abs(real_diff):
                beaten += 1
        pct = 100.0 * beaten / N_PERMUTATIONS
        n_off = int((~in_season_mask).sum())
        season_gates[h] = {"in_rate": float(in_rate), "off_rate": float(off_rate),
                            "diff": float(real_diff), "percentile": float(pct), "n_off": n_off}
        print(f"  {h}交易日內填息率：旺季={in_rate:.1%}  非旺季={off_rate:.1%}(n={n_off})  "
              f"差距={real_diff:+.1%}  vs洗牌null percentile={pct:.1f} (需要>=90.0)")

    season_gate_passes = any(g["percentile"] >= 90.0 for g in season_gates.values())

    passes = drop_yield_rho > 0.3 and not pd.isna(drop_yield_rho) and season_frac > 0.5
    print(f"\n=== 第1關 SANITY {'PASS' if passes else 'FAIL'} ===")
    print("（sanity只驗證資料完整性與事件分布合理性；上面兩個cheap gate各自獨立判定"
          "CHEAP_PASS/FAIL，是否進入第2關以後由兩者結果+使用者裁示的「稅後淨alpha」"
          "前置條件共同決定，不是sanity PASS就自動晉級）")

    return {
        "sanity_passes": passes, "n_events": len(events), "n_stocks_usable": n_ok,
        "month_counts": month_counts.to_dict(), "season_frac": float(season_frac),
        "drop_yield_rho": float(drop_yield_rho), "drop_yield_p": float(drop_yield_p),
        "pre_ret_gate": pre_result, "fwd_ret_gate": fwd_result,
        "season_fill_gates": season_gates, "season_gate_passes": season_gate_passes,
        "n_train": len(train), "n_val": len(val),
    }


if __name__ == "__main__":
    main()
