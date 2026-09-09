"""`HYPOTHESIS_QUEUE.md` #66 美股年末稅損收割賣壓／一月效應：第1關 cheap gate。

經濟理由完整版見`HYPOTHESIS_QUEUE.md` `### 66.`小節。本腳本是設計文件寫完後
第一支實際程式碼，2026-09-09 hypothesis_queue排程接續新增。

**對設計文件的一處操作化澄清（跑任何數字之前先寫清楚，不是看到結果後才改）**：
設計文件原文字「訊號窗口：每年11月初至12月最後交易日的個股累積報酬」若直接
拿來當「今年表現」排序變數、同時又拿12月報酬當測試窗口，會有機械性重疊——12月
本身就是訊號窗口的一部分，losers組定義上12月報酬本來就比較低，這樣測(a)會是
套套邏輯（tautology），不是真的稅損賣壓證據。改採文獻標準作法
（Poterba & Weisbenner 2001「用去年一整年報酬排序，分別測12月跟次年1月」的
精神，但用YTD 1-10月避免跟12月測試窗口重疊）：
  - `signal_ret`：當年1月初至10月最後交易日累積報酬（YTD-through-Oct，排序
    變數，跟12月/次年1月測試窗口完全不重疊）。
  - `dec_ret`：當年12月報酬（稅損賣壓測試窗口）。
  - `jan_ret`：次年1月報酬（反轉測試窗口）。
最差十分位（YTD-through-Oct表現最差）定義為losers，事前假設losers在12月跑輸
其餘股票（賣壓）、在次年1月跑贏其餘股票（反轉解除）。

沿用既有元件（不重新發明）：
- `us_factors.us_price_series()`——既有美股價格快取（FinMind USStockPrice，
  跟`us_factor_ic.py`/`us_portfolio_gross_profitability_v1.py`等現行仍在用的
  US track腳本同一套資料源，本輪零新增外部資料源整合成本，符合設計文件宣稱）。
- `us_factor_ic_value_clean_universe.load_clean_universe_tickers()`——既有
  248檔clean universe（已排除contamination blacklist），跟`us_factor_ic_
  quality_clean_universe.py`等既有腳本同一份樣本，避免重新抽樣。
- `validation.holdout`（TRAIN_END/VAL_END切分+holdout洩漏斷言）。

**已知限制（沿用設計文件，此處重申）**：
1. 存活者偏誤但書：此樣本來自現存/近期下市股（clean universe），若某年「真正
   最慘」的輸家已經下市消失，losers組會系統性遺漏那些股票，低估效應強度。
2. 只能測美股，不可泛化到台股（台灣個人證券交易無資本利得稅）。
3. 文獻記載現代市場此效應已減弱，先驗上偏向FAIL或邊緣顯著。

判定範圍（第1關cheap gate，非最終判定）：對(a) losers vs 其餘 12月報酬差、
(b) losers vs 其餘次年1月報酬差，各自用洗牌置換檢定（打亂losers標籤，保留
組別大小），percentile>=90.0視為單項過關；(a)方向須為負（losers跑輸）、
(b)方向須為正（losers跑贏）才符合事前假設。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from us_factor_ic_value_clean_universe import load_clean_universe_tickers
from us_factors import us_price_series
from validation import holdout

N_PERMUTATIONS = 500  # 沿用 #24 同一個規模，池化年度層級事件計算便宜
PERM_SEED = 20260909
LOSER_DECILE = 0.10  # 最差十分位


def _year_events(stock_id: str, px: pd.DataFrame) -> pd.DataFrame:
    """單一股票的逐年事件表：year, signal_ret(YTD 1-10月), dec_ret(12月),
    jan_ret(次年1月)。三個窗口彼此不重疊，避免訊號窗口跟測試窗口機械性重疊。
    """
    if px.empty or len(px) < 260:
        return pd.DataFrame()
    px = px.sort_values("date").reset_index(drop=True)
    px["dt"] = pd.to_datetime(px["date"])
    px["year"] = px["dt"].dt.year
    px["month"] = px["dt"].dt.month
    px = px.dropna(subset=["adj_close"])
    if px.empty:
        return pd.DataFrame()

    rows = []
    years = sorted(px["year"].unique())
    for y in years:
        # signal_ret: 1月初~10月最後交易日累積報酬
        sig = px[(px["year"] == y) & (px["month"] <= 10)]
        if len(sig) < 2:
            continue
        p0, p1 = sig["adj_close"].iloc[0], sig["adj_close"].iloc[-1]
        if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        signal_ret = p1 / p0 - 1.0

        # dec_ret: 12月報酬（用11月最後交易日收盤當起點，12月最後交易日收盤當終點）
        nov = px[(px["year"] == y) & (px["month"] == 11)]
        dec = px[(px["year"] == y) & (px["month"] == 12)]
        if nov.empty or dec.empty:
            continue
        p_nov_end = nov["adj_close"].iloc[-1]
        p_dec_end = dec["adj_close"].iloc[-1]
        if pd.isna(p_nov_end) or pd.isna(p_dec_end) or p_nov_end <= 0:
            continue
        dec_ret = p_dec_end / p_nov_end - 1.0

        # jan_ret: 次年1月報酬（用當年12月最後交易日收盤當起點，次年1月最後交易日收盤當終點）
        jan_next = px[(px["year"] == y + 1) & (px["month"] == 1)]
        if jan_next.empty:
            continue
        p_jan_end = jan_next["adj_close"].iloc[-1]
        if pd.isna(p_jan_end) or p_dec_end <= 0:
            continue
        jan_ret = p_jan_end / p_dec_end - 1.0

        rows.append({
            "stock_id": stock_id, "year": int(y),
            "signal_ret": signal_ret, "dec_ret": dec_ret, "jan_ret": jan_ret,
        })
    return pd.DataFrame(rows)


def _cross_sectional_losers(events: pd.DataFrame) -> pd.DataFrame:
    """依年度做橫斷面分組：每年signal_ret最差十分位=loser=True，其餘False。
    需要每年至少10檔才能有意義地定義十分位（跟本佇列既有cheap gate的n>=10
    cross-section門檻一致）。
    """
    out = []
    for y, grp in events.groupby("year"):
        if len(grp) < 10:
            continue
        thresh = grp["signal_ret"].quantile(LOSER_DECILE)
        grp = grp.copy()
        grp["is_loser"] = grp["signal_ret"] <= thresh
        out.append(grp)
    if not out:
        return pd.DataFrame()
    return pd.concat(out, ignore_index=True)


def _permutation_group_diff(df: pd.DataFrame, y_col: str, real_diff: float,
                             n_perm: int, seed: int) -> float:
    """打亂is_loser標籤（每年內部各自重新洗牌、保留該年組別大小），計算
    losers組跟其餘組在y_col上的差距，看真實差距打贏幾%的洗牌null分布。
    """
    rng = np.random.RandomState(seed)
    beaten = 0
    years = df["year"].unique()
    y_by_year = {y: df[df["year"] == y][[y_col, "is_loser"]].to_numpy() for y in years}
    for _ in range(n_perm):
        diffs_loser, diffs_other = [], []
        for y, arr in y_by_year.items():
            vals = arr[:, 0].astype(float)
            n = len(vals)
            n_loser = int((arr[:, 1] == True).sum())  # noqa: E712
            if n_loser == 0 or n_loser == n:
                continue
            perm_idx = rng.permutation(n)
            loser_idx = perm_idx[:n_loser]
            other_idx = perm_idx[n_loser:]
            diffs_loser.extend(vals[loser_idx].tolist())
            diffs_other.extend(vals[other_idx].tolist())
        if not diffs_loser or not diffs_other:
            continue
        perm_diff = float(np.mean(diffs_loser)) - float(np.mean(diffs_other))
        if abs(perm_diff) <= abs(real_diff):
            beaten += 1
    return 100.0 * beaten / n_perm


def _evaluate_window(df: pd.DataFrame, y_col: str, expected_sign: int, label: str) -> dict:
    d = df.dropna(subset=[y_col, "is_loser"])
    losers = d[d["is_loser"]][y_col]
    others = d[~d["is_loser"]][y_col]
    if len(losers) < 10 or len(others) < 10:
        return {"label": label, "passes": False, "reasons": [f"樣本數過少 (losers_n={len(losers)}, others_n={len(others)})"]}
    real_diff = float(losers.mean()) - float(others.mean())
    pct = _permutation_group_diff(d, y_col, real_diff, N_PERMUTATIONS, PERM_SEED)
    sign_ok = (real_diff < 0) if expected_sign < 0 else (real_diff > 0)
    reasons = []
    if not sign_ok:
        reasons.append(f"方向與事前假設不符 (real_diff={real_diff:+.4f}, 預期符號={'負' if expected_sign<0 else '正'})")
    if pct < 90.0:
        reasons.append(f"null percentile={pct:.1f}未過門檻90.0")
    passes = len(reasons) == 0
    print(f"[{label}] losers(n={len(losers)}) mean={losers.mean():+.4f}  "
          f"others(n={len(others)}) mean={others.mean():+.4f}  diff={real_diff:+.4f}  "
          f"vs {N_PERMUTATIONS}次洗牌null percentile={pct:.1f} (需要>=90.0, 預期符號={'負' if expected_sign<0 else '正'})")
    print(f"[{label}] {'CHEAP_PASS' if passes else 'FAIL'}" + (f"  reasons: {reasons}" if reasons else ""))
    return {"label": label, "passes": passes, "reasons": reasons, "real_diff": real_diff,
            "null_percentile": pct, "n_losers": len(losers), "n_others": len(others)}


def main():
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    tickers = load_clean_universe_tickers()
    print(f"=== 美股年末稅損收割賣壓/一月效應 gate1 (HYPOTHESIS_QUEUE.md #66) ===")
    print(f"Universe: {len(tickers)} clean-universe names, LOSER_DECILE={LOSER_DECILE}")

    all_events = []
    n_ok = 0
    for i, sid in enumerate(tickers):
        try:
            px = us_price_series(sid)
        except Exception as e:  # noqa: BLE001 -- 跟本佇列既有腳本同一個容錯尺度
            print(f"  [{sid}] price ERROR ({e}), dropping")
            continue
        ev = _year_events(sid, px)
        if not ev.empty:
            all_events.append(ev)
            n_ok += 1
        if (i + 1) % 50 == 0:
            print(f"  progress {i+1}/{len(tickers)}, {n_ok} usable so far")

    if not all_events:
        print("SANITY FAIL: 零事件，資料層級有問題（不是無訊號，是抓取/解析有誤）。")
        return {"passes": False, "reason": "no_events"}

    events = pd.concat(all_events, ignore_index=True)
    holdout.assert_no_holdout_leakage(
        events.assign(date=events["year"].astype(str) + "-12-31"),
        date_col="date", context="us_tax_loss_selling_gate66 events (year-level, using Dec31 as year marker)",
    )
    print(f"\n{n_ok}/{len(tickers)} 檔股票有可用逐年事件，總事件數={len(events)}，"
          f"年份範圍 {events['year'].min()}~{events['year'].max()}")

    # 年份切TRAIN/VAL：year<=2020(對應TRAIN_END)算TRAIN，2021<=year<=2023算VAL
    # （year=2024的話jan_ret需要2025-01資料，超過VAL_END=2024-12-31，_year_events
    # 已經因jan_next.empty而自動排除，這裡的邊界只是雙重確認、非唯一防線）。
    train_years = [y for y in events["year"].unique() if y <= 2020]
    val_years = [y for y in events["year"].unique() if 2021 <= y <= 2023]
    train = events[events["year"].isin(train_years)]
    val = events[events["year"].isin(val_years)]
    print(f"TRAIN年份={sorted(train_years)} ({len(train)}筆) | VAL年份={sorted(val_years)} ({len(val)}筆)")

    if len(train) < 50 or len(val) < 50:
        print("SANITY FAIL: TRAIN或VAL事件數過少，無法做橫斷面十分位分組+洗牌檢定。")
        return {"passes": False, "reason": "insufficient_train_val_events",
                "n_events": len(events), "n_stocks_usable": n_ok}

    train_grouped = _cross_sectional_losers(train)
    val_grouped = _cross_sectional_losers(val)
    if train_grouped.empty or val_grouped.empty:
        print("SANITY FAIL: 某一期每年橫斷面樣本數不足10檔，無法定義十分位。")
        return {"passes": False, "reason": "insufficient_cross_section",
                "n_events": len(events), "n_stocks_usable": n_ok}

    print(f"\nTRAIN: {train_grouped['year'].nunique()}個年度可用橫斷面 | "
          f"VAL: {val_grouped['year'].nunique()}個年度可用橫斷面")

    print("\n--- (a) 12月報酬（稅損賣壓期，事前假設losers跑輸） ---")
    train_dec = _evaluate_window(train_grouped, "dec_ret", expected_sign=-1, label="TRAIN 12月報酬")
    val_dec = _evaluate_window(val_grouped, "dec_ret", expected_sign=-1, label="VAL 12月報酬")

    print("\n--- (b) 次年1月報酬（反轉期，事前假設losers跑贏） ---")
    train_jan = _evaluate_window(train_grouped, "jan_ret", expected_sign=+1, label="TRAIN 次年1月報酬")
    val_jan = _evaluate_window(val_grouped, "jan_ret", expected_sign=+1, label="VAL 次年1月報酬")

    both_val_pass = val_dec["passes"] and val_jan["passes"]
    both_train_pass = train_dec["passes"] and train_jan["passes"]
    overall_passes = both_val_pass and both_train_pass
    print(f"\n=== 第1關 CHEAP GATE 判定：{'CHEAP_PASS' if overall_passes else 'FAIL'} ===")
    print("（判準：(a)12月與(b)次年1月兩個窗口，TRAIN跟VAL都要方向符合事前假設"
          "且贏過洗牌null percentile>=90.0，缺一不算過關——跟#24除權息季節同一把尺）")

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {'False (OK)' if holdout_ok else 'TRUE -- VIOLATION'}")
    assert holdout_ok, "holdout must remain untouched (after)"

    return {
        "overall_passes": overall_passes, "n_events": len(events), "n_stocks_usable": n_ok,
        "n_train_years": train_grouped["year"].nunique(), "n_val_years": val_grouped["year"].nunique(),
        "train_dec": train_dec, "val_dec": val_dec, "train_jan": train_jan, "val_jan": val_jan,
    }


if __name__ == "__main__":
    main()
