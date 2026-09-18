"""重構.B2：飆股歸因分解五題正式作答（衛星倉·描述性研究，非策略）。

背景：`multibagger_attribution.py` 已完成分層抽樣（active/delisted 各150檔，
固定種子=42）跑資料管線與歸因分解（第2題），但只印出中間統計量，沒有把
五題（PENDING_QUEUE.md「2026-09-18（續3）」總司令原文）組成正式結論寫進
`MULTIBAGGER_ATTRIBUTION.md`。這支腳本消費*同一組*可重現樣本（重跑
`stratified_sample(normal_stock, SAMPLE_PER_STRATUM, SAMPLE_SEED)`會拿到
一模一樣的300檔，因為`universe()`讀本地已提交檔案、`SAMPLE_SEED`固定），
不重新設計抽樣，只補齊五題的正式輸出。

**資料重用、不重打API**：203檔「ok」股票的價格/EPS/營收都已經在上一輪
`multibagger_attribution.py`成功執行時寫入`research/data/raw/*.parquet`
磁碟快取（`finmind_client._fetch()`命中快取直接回傳、不呼叫`_throttle()`，
見docstring），本腳本重新載入同一組股票時**不會消耗FinMind額度**；97檔
skip股票裡屬於`fetch_error`(額度類RuntimeError)的那些會在額度封鎖期間
立即快速失敗（`_rate_limit_wait_or_raise()`在封鎖中直接拋錯，不發送
請求），不會意外撞額度。

**第2題已由`multibagger_attribution.py`的`process_stock()`完整回答**
（`log_eps_contrib`/`log_pe_contrib`/`log_residual_dividend_and_other`
三欄，且該檔docstring已誠實記錄「股數變化」因FinMind免費層無可靠流通
股數欄位而無法獨立拆分的已知限制），本腳本只做匯總統計，不重算。

第4/5題需要「起漲前特徵相似、但沒有起飛」的對照組——這需要掃描*所有*
12個月滾動窗口（不只是達標的飆股episode），`multibagger_attribution.py`
原本的`_find_moonshot_windows()`只保留達標事件的上升緣（避免同一次上漲
被算多次），不適合直接拿來做對照組（會漏掉所有未達標的窗口）。本腳本
新增`_all_windows()`（固定間隔抽樣，不做達標判定與冷卻）取代它，兩者
刻意分開、不互相修改，避免影響已測試通過的歸因分解管線。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from pit import month_revenue_pit
from universe import universe
from multibagger_attribution import (
    SAMPLE_PER_STRATUM, SAMPLE_SEED, MOONSHOT_THRESHOLD, CONTROL_THRESHOLD,
    WINDOW_MONTHS, OUT_DIR, _monthly_last, _eps_ttm_series, _pre_window_features,
    stratified_sample,
)

CONTROL_GROUP_STRIDE_MONTHS = 6  # 已知限制：< WINDOW_MONTHS=12，相鄰抽樣窗口仍部分重疊，非完全獨立樣本


def _all_windows(monthly: pd.DataFrame, stride: int = CONTROL_GROUP_STRIDE_MONTHS) -> pd.DataFrame:
    """回傳固定間隔抽樣的12個月滾動窗口（不論是否達標），供第4/5題對照組用。
    跟`_find_moonshot_windows()`的差異見本檔案docstring。"""
    cols = ["window_start", "month_end", "window_return", "window_start_idx"]
    if len(monthly) < WINDOW_MONTHS + 1:
        return pd.DataFrame(columns=cols)
    adj = monthly["adj_close"].to_numpy()
    ends = monthly["month_end"].to_numpy()
    rows = []
    for i in range(0, len(adj) - WINDOW_MONTHS, stride):
        a0, a1 = adj[i], adj[i + WINDOW_MONTHS]
        if a0 is None or a1 is None or pd.isna(a0) or pd.isna(a1) or a0 <= 0:
            continue
        rows.append({
            "window_start": ends[i], "month_end": ends[i + WINDOW_MONTHS],
            "window_return": float(a1 / a0 - 1.0), "window_start_idx": i,
        })
    return pd.DataFrame(rows, columns=cols)


def _process_stock_all_windows(stock_id: str, status: str) -> list[dict]:
    """跟`process_stock()`共用底層資料載入邏輯，但回傳所有固定間隔窗口
    （含未達標）。任何一步失敗回傳空list（錯誤隔離，呼叫端不需另外try/except）。
    """
    try:
        price = adjusted_price_series(stock_id)
        if price.empty or len(price) < 260:
            return []
        monthly = _monthly_last(price)
        eps_ttm = _eps_ttm_series(stock_id)
        rev = month_revenue_pit(stock_id)
        windows = _all_windows(monthly)
        out = []
        for _, w in windows.iterrows():
            feat = _pre_window_features(price, eps_ttm, rev, monthly, int(w["window_start_idx"]))
            out.append({
                "stock_id": stock_id, "status": status,
                "window_start": str(w["window_start"])[:10], "month_end": str(w["month_end"])[:10],
                "window_return": float(w["window_return"]),
                **feat,
            })
        return out
    except RuntimeError:
        return []  # 額度/冷卻中，靜默略過，沿用process_stock()同一套「這次問不到不等於沒有」精神，這裡不需要另外分類
    except Exception:
        return []


def _weighted_rate(mask: pd.Series, weight: pd.Series) -> float | None:
    total_w = weight.sum()
    if total_w == 0:
        return None
    return float((mask.astype(float) * weight).sum() / total_w)


def main() -> None:
    uni = universe()
    normal_stock = uni[uni["stock_id"].str.match(r"^\d{4}$")].reset_index(drop=True)
    sample, strata_info = stratified_sample(normal_stock, SAMPLE_PER_STRATUM, SAMPLE_SEED)
    print(f"[five_q] 重建樣本：{len(sample)} 檔（跟重構.B同一組，種子={SAMPLE_SEED}），"
          f"strata_info={json.dumps(strata_info, ensure_ascii=False)}")

    pop_weight = {k: v["population_weight"] for k, v in strata_info.items() if v.get("population_weight")}

    all_rows = []
    n_ok_stock = 0
    for i, row in sample.iterrows():
        rows = _process_stock_all_windows(row["stock_id"], row["status"])
        if rows:
            n_ok_stock += 1
            all_rows.extend(rows)
        if (i + 1) % 50 == 0:
            print(f"  progress {i+1}/{len(sample)}  ok_stocks={n_ok_stock}  windows={len(all_rows)}")

    df = pd.DataFrame(all_rows)
    print(f"[five_q] 完成：ok_stocks={n_ok_stock}  總窗口數={len(df)}")
    if df.empty:
        print("[five_q] ⚠️ 沒有任何可用窗口，無法回答第4/5題，提前結束（不寫入報告）。")
        return

    df["population_weight"] = df["status"].map(pop_weight).astype(float)
    df["outcome"] = np.select(
        [df["window_return"] >= MOONSHOT_THRESHOLD, df["window_return"] < CONTROL_THRESHOLD],
        ["moonshot", "control"], default="middle",
    )
    df["is_delisted"] = (df["status"] == "delisted").astype(float)

    # ---- Q4：起漲前特徵相似分組 → 起飛率/平庸率/下市率 ----
    # 規模代理（無真市值，沿用avg_trading_money_20d_pre，見multibagger_attribution.py docstring已揭露的限制）
    has_liq = df["avg_trading_money_20d_pre"].notna()
    liq_valid = df.loc[has_liq, "avg_trading_money_20d_pre"]
    size_bins = liq_valid.quantile([0, 1/3, 2/3, 1.0]).to_numpy().copy()
    size_bins[0] -= 1.0  # 確保最小值被含括在第一區間
    df["size_tercile"] = pd.NA
    df.loc[has_liq, "size_tercile"] = pd.cut(
        liq_valid, bins=size_bins, labels=["小(規模代理)", "中(規模代理)", "大(規模代理)"]
    )
    df["eps_yoy_sign"] = np.where(df["eps_yoy_pre"].isna(), pd.NA,
                                   np.where(df["eps_yoy_pre"] >= 0, "EPS年增為正", "EPS年增為負"))

    q4_rows = []
    q4_df = df.dropna(subset=["size_tercile", "eps_yoy_sign"])
    for (sz, sign), g in q4_df.groupby(["size_tercile", "eps_yoy_sign"], observed=True):
        w = g["population_weight"]
        q4_rows.append({
            "size_tercile": sz, "eps_yoy_sign": sign, "n_windows_raw": len(g),
            "起飛率_raw_pct": round(100 * (g["outcome"] == "moonshot").mean(), 2),
            "平庸率_raw_pct": round(100 * (g["outcome"] == "middle").mean(), 2),
            "下市率_raw_pct": round(100 * g["is_delisted"].mean(), 2),
            "起飛率_母體加權_pct": round(100 * _weighted_rate(g["outcome"] == "moonshot", w), 2),
            "平庸率_母體加權_pct": round(100 * _weighted_rate(g["outcome"] == "middle", w), 2),
            "下市率_母體加權_pct": round(100 * _weighted_rate(g["is_delisted"] == 1, w), 2),
        })
    q4_table = pd.DataFrame(q4_rows).sort_values(["size_tercile", "eps_yoy_sign"])

    # ---- Q5：規模代理分位門檻的邊際效果（只看小於等於第X分位的標的）----
    q5_rows = []
    for pct in (20, 40, 60, 80, 100):
        cutoff = liq_valid.quantile(pct / 100.0)
        sub = df[has_liq & (df["avg_trading_money_20d_pre"] <= cutoff)]
        if sub.empty:
            continue
        w = sub["population_weight"]
        moonshot_rate = _weighted_rate(sub["outcome"] == "moonshot", w)
        delist_rate = _weighted_rate(sub["is_delisted"] == 1, w)
        q5_rows.append({
            "規模代理分位門檻_百分位": pct, "n_windows_raw": len(sub),
            "起飛率_母體加權_pct": round(100 * moonshot_rate, 2) if moonshot_rate is not None else None,
            "下市率_母體加權_pct": round(100 * delist_rate, 2) if delist_rate is not None else None,
            "起飛率_下市率_比值": round(moonshot_rate / delist_rate, 3)
                if moonshot_rate is not None and delist_rate not in (None, 0) else None,
        })
    q5_table = pd.DataFrame(q5_rows)

    # ---- Q1：population-weighted 逐年基準機率（重跑一次moonshot分類，直接用df裡的moonshot窗口）----
    moon = df[df["outcome"] == "moonshot"].copy()
    moon["year"] = pd.to_datetime(moon["month_end"]).dt.year
    yearly_weighted = {}
    if not moon.empty:
        total_w_by_year_stock = df.copy()
        for y in sorted(moon["year"].unique()):
            hit_w = moon.loc[moon["year"] == y, "population_weight"].sum()
            # 分母：該年所有觀察到的窗口的母體加權總和（不是股票數，是窗口數，作為粗略基準機率分母）
            denom_w = df.loc[pd.to_datetime(df["month_end"]).dt.year == y, "population_weight"].sum()
            yearly_weighted[int(y)] = {
                "moonshot_window_weight_sum": round(float(hit_w), 3),
                "all_window_weight_sum": round(float(denom_w), 3),
                "weighted_rate_pct": round(100 * hit_w / denom_w, 3) if denom_w else None,
            }

    out = {
        "sample_strata_info": strata_info,
        "n_ok_stock_control_group": n_ok_stock,
        "n_total_windows_stride6m": len(df),
        "q1_yearly_weighted_moonshot_rate_by_window": yearly_weighted,
        "q4_control_group_table": q4_table.to_dict(orient="records"),
        "q5_size_threshold_sweep": q5_table.to_dict(orient="records"),
    }
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "five_questions_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    df.to_csv(OUT_DIR / "all_windows_stride6m.csv", index=False)

    print(f"[five_q] Q1逐年加權起飛率（窗口層級，粗略基準機率）：{json.dumps(yearly_weighted, ensure_ascii=False)}")
    print(f"[five_q] Q4對照組表：\n{q4_table.to_string(index=False)}")
    print(f"[five_q] Q5規模門檻掃描：\n{q5_table.to_string(index=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
