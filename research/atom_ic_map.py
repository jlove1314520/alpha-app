# -*- coding: utf-8 -*-
"""原子.二：depth-1表達式（算子(原子,n)）IC地圖（2026-09-19總司令裁示
【原子.一審閱通過（補三個算子）＋#73設上限＋補等待審閱的可見度】二，
原子.一審閱通過後直接接續，不需再等審閱）。

**範圍聲明（事前登記，不得事後增減，誠實揭露排除了什麼）**：
「depth-1表達式」定義為「單一原子餵給一個算子」，本輪只涵蓋三類：
  (A) 需要窗口n的單序列算子：delay/delta/ts_mean/ts_std/ts_max/ts_min/
      ts_rank/ts_sum/ts_argmax/decay_linear（10個）× 24個原子 × 4個窗口
      = **960**
  (B) 不需窗口的單序列純量算子：sign/abs/log1p（3個）× 24個原子
      = **72**
  (C) 相對強度家族：ts_corr(股票原子, 基準原子, n)，14個股票原子×10個
      基準原子×4個窗口 = **560**（這是新增基準原子的主要動機）
**明確排除、留給`原子.三`（深度2/3組合）的部分**：`mul`/`ratio`兩原子
成對組合本身不算進本輪——總司令原文舉的`mul`範例本身就是深度2
（`sign(delta(c,1))×v`，先算`sign(delta(c,1))`這個深度1子表達式，
`mul`是拿去跟`v`組深度2），不是「兩個原始原子直接相乘」這種用法，
硬把`mul`/`ratio`的原子×原子全排列(24×23≈550+)算進「depth-1」不符合
總司令原文舉例的實際用法，留給`原子.三`用已經算過的深度1存活素材去組。

**總計深度1表達式數 = 960+72+560 = 1592**，每個對20日與60日兩個
horizon各測一次，**計入selection_bias_ledger的N = 1592×2 = 3184**。

**判準與誠實邊界**：本輪只跑「原始IC」（train/val各期cross-sectional
Spearman IC取平均），**不跑`factor_ic.py::evaluate_factor()`那一整套
隨機重排null分布+Bonferroni PASS/FAIL判定**——3184個測試每個都跑
1000次shuffle在算力上不成比例（原本的評估流程是給少數候選做認證用的，
不是給大規模掃描用的），本輪只要「零件層級的IC分布長什麼樣子」，
不要「哪些過關」。**禁止報告『最佳素材』**：輸出`ATOM_IC_MAP.md`只給
分布統計（中位數/四分位/正負比例/跟train同號比例），不點名任何具體
表達式的名字當作「這個看起來不錯」，即使數字上剛好落在分布尾端。

**資料源**：`factor_ic.py::sample_universe_ids()`/`load_sample_with_
factors()`既有機制（TRAIN+VAL，HOLDOUT不碰），額外合併`Trading_money`
（`amt`原子需要，`adjusted_price_series()`本身不含這個欄位）。

用法：
    python research/atom_ic_map.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import ATOM_LIBRARY as al
import finmind_client as fc
from factor_ic import (
    SAMPLE_SIZE, START_DATE, build_snapshots, load_sample_with_factors,
    sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

HORIZONS = (20, 60)
OUT_MD = Path(__file__).parent / "ATOM_IC_MAP.md"
OUT_JSON = Path(__file__).parent / "atom_ic_map_result.json"

STOCK_ATOM_NAMES = ["o", "h", "l", "c", "v", "amt", "body", "upper_sh", "lower_sh",
                     "range", "close_loc", "gap", "true_range", "vwap"]
BENCH_ATOM_NAMES = ["b50_o", "b50_h", "b50_l", "b50_c", "b50_v",
                     "btx_o", "btx_h", "btx_l", "btx_c", "btx_v"]
ALL_ATOM_NAMES = STOCK_ATOM_NAMES + BENCH_ATOM_NAMES

TS_WINDOW_OPS = ["delay", "delta", "ts_mean", "ts_std", "ts_max", "ts_min",
                 "ts_rank", "ts_sum", "ts_argmax", "decay_linear"]
SCALAR_UNARY_OPS = ["sign", "abs", "log1p"]


def _merge_amt(px: pd.DataFrame, sid: str) -> pd.DataFrame:
    """幫adjusted_price_series()的輸出補上Trading_money（amt原子需要，
    該函式本身不含這個欄位）。走既有本機快取，找不到就留NaN，不額外
    發即時請求（沿用本專案「零件層級掃描不主動打真實資料源」的既有
    慣例，跟`atom_ic_map.py`本身描述性掃描的定位一致）。"""
    try:
        raw = load_dev("TaiwanStockPrice", sid, START_DATE)
    except Exception:  # noqa: BLE001 -- 描述性掃描，單檔缺amt不影響其他原子
        return px
    if raw.empty or "Trading_money" not in raw.columns:
        return px
    amt_map = raw.set_index("date")["Trading_money"]
    out = px.copy()
    out["amt"] = out["date"].map(amt_map)
    return out


def build_atom_df(px: pd.DataFrame) -> pd.DataFrame:
    """把`adjusted_price_series()`+補amt的輸出轉成ATOM_LIBRARY.py期待的
    欄位慣例：o/h/l/c用還原後OHLC，v/amt用原始量額，date保留供基準
    原子對齊使用。

    **實測發現的schema分歧（誠實記錄，非本函式引入的新問題）**：
    `adjusted_price_series()`內部依股票走yfinance或FinMind回退路徑，
    兩條路徑的欄位名稱不同——yfinance路徑是`volume`（小寫），FinMind
    路徑是`Trading_Volume`/`Trading_money`（且FinMind路徑本身就已經
    帶原始`Trading_money`，不需要`_merge_amt()`另外查）。本函式對兩種
    schema都做防呆，缺哪個欄位就讓對應的原子（`v`/`amt`）誠實回NaN，
    不假裝有資料。"""
    v_col = "volume" if "volume" in px.columns else (
        "Trading_Volume" if "Trading_Volume" in px.columns else None)
    amt_col = "amt" if "amt" in px.columns else (
        "Trading_money" if "Trading_money" in px.columns else None)
    return pd.DataFrame({
        "date": pd.to_datetime(px["date"]),
        "o": px["adj_open"].astype(float), "h": px["adj_high"].astype(float),
        "l": px["adj_low"].astype(float), "c": px["adj_close"].astype(float),
        "v": px[v_col].astype(float) if v_col else np.nan,
        "amt": px[amt_col].astype(float) if amt_col else np.nan,
    })


def compute_all_expressions(atom_df: pd.DataFrame) -> dict[str, pd.Series]:
    """回傳{expression名稱: pd.Series}，index對齊atom_df的列順序。"""
    atom_values = {name: al.ATOMS[name](atom_df) for name in ALL_ATOM_NAMES}
    out: dict[str, pd.Series] = {}

    for op_name in TS_WINDOW_OPS:
        op_fn = al.ALL_OPERATORS[op_name]
        for atom_name in ALL_ATOM_NAMES:
            for n in al.ALLOWED_WINDOWS:
                out[f"{op_name}__{atom_name}__{n}"] = op_fn(atom_values[atom_name], n)

    for op_name in SCALAR_UNARY_OPS:
        op_fn = al.ALL_OPERATORS[op_name]
        for atom_name in ALL_ATOM_NAMES:
            out[f"{op_name}__{atom_name}"] = op_fn(atom_values[atom_name])

    ts_corr = al.ALL_OPERATORS["ts_corr"]
    for stock_atom in STOCK_ATOM_NAMES:
        for bench_atom in BENCH_ATOM_NAMES:
            for n in al.ALLOWED_WINDOWS:
                out[f"ts_corr__{stock_atom}__{bench_atom}__{n}"] = ts_corr(
                    atom_values[stock_atom], atom_values[bench_atom], n)

    return out


def main():
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    print(f"market_df: {len(market_df)}天")

    ids = sample_universe_ids(SAMPLE_SIZE)
    print(f"樣本宇宙: {len(ids)}檔，開始載入價格+補amt...")

    atom_data: dict[str, pd.DataFrame] = {}
    for i, sid in enumerate(ids):
        try:
            from adjust import adjusted_price_series
            px = adjusted_price_series(sid, START_DATE)
        except Exception:  # noqa: BLE001
            continue
        if px.empty or len(px) < 260:
            continue
        px = _merge_amt(px, sid)
        atom_data[sid] = build_atom_df(px)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(ids)}（可用{len(atom_data)}檔）")
    print(f"可用股票: {len(atom_data)}/{len(ids)}")

    print("計算全部depth-1表達式...")
    expr_by_stock: dict[str, dict[str, pd.Series]] = {}
    for i, (sid, df) in enumerate(atom_data.items()):
        try:
            expr_by_stock[sid] = compute_all_expressions(df)
        except Exception as e:  # noqa: BLE001 -- 描述性掃描，單檔算子出錯不中斷整批
            print(f"  [警告] {sid}計算表達式失敗，跳過：{e}")
            continue
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(atom_data)}")

    n_expressions = len(next(iter(expr_by_stock.values())))
    print(f"每檔股票的表達式數：{n_expressions}（事前登記應為1592，"
          f"960+72+560=1592，若不符表示分類算子/原子/窗口計數有誤）")

    # 效能設計：先把每檔股票的表達式值+收盤價用date重新索引成dict of
    # DataFrame，之後每個snapshot只需要一次DataFrame.corrwith()（向量化
    # 跨1592欄同時算Spearman IC），不要對每個表達式各自迴圈——原本逐一
    # expression×snapshot×stock三層迴圈量級太大（1592×~110×250≈4400萬
    # 次），改成「每個snapshot組一次橫斷面表格」把最內層迴圈向量化掉。
    expr_names = list(next(iter(expr_by_stock.values())).keys())
    indexed_exprs: dict[str, pd.DataFrame] = {}
    indexed_close: dict[str, pd.Series] = {}
    for sid, exprs in expr_by_stock.items():
        df = atom_data[sid]
        dates = pd.DatetimeIndex(df["date"])
        wide = pd.DataFrame(exprs)
        wide.index = dates
        indexed_exprs[sid] = wide[~wide.index.duplicated(keep="first")]
        close_s = pd.Series(df["c"].values, index=dates)
        indexed_close[sid] = close_s[~close_s.index.duplicated(keep="first")]

    results = []
    for horizon in HORIZONS:
        # market_df["date"]是純字串（`load_dev()`既有慣例，不是Timestamp，
        # 跟`core_tilt_backtest.py`同一個型別慣例），build_snapshots()本來
        # 就是設計吃字串list，不需要（也不能）呼叫.date()。
        calendar = sorted(market_df["date"].unique())
        snapshots = build_snapshots(calendar, calendar[0], calendar[-1], horizon=horizon)
        snapshots = [(pd.Timestamp(a), pd.Timestamp(f)) for a, f in snapshots]
        print(f"horizon={horizon}日: {len(snapshots)}個snapshot")

        train_ic_rows, val_ic_rows = [], []
        for si, (as_of, fwd) in enumerate(snapshots):
            cross_rows = {}
            ret_map = {}
            for sid in indexed_exprs:
                if (as_of not in indexed_exprs[sid].index or as_of not in indexed_close[sid].index
                        or fwd not in indexed_close[sid].index):
                    continue
                p0 = indexed_close[sid].loc[as_of]
                p1 = indexed_close[sid].loc[fwd]
                if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                    continue
                cross_rows[sid] = indexed_exprs[sid].loc[as_of]
                ret_map[sid] = float(p1 / p0 - 1)
            if len(cross_rows) < 10:
                continue
            cross_df = pd.DataFrame(cross_rows).T  # index=stock_id, columns=expr_names
            ret_s = pd.Series(ret_map)
            ic_row = cross_df.corrwith(ret_s, method="spearman")
            if as_of <= pd.Timestamp(holdout.TRAIN_END):
                train_ic_rows.append(ic_row)
            elif as_of <= pd.Timestamp(holdout.VAL_END):
                val_ic_rows.append(ic_row)
            if (si + 1) % 10 == 0:
                print(f"  horizon={horizon} snapshot {si+1}/{len(snapshots)}")

        train_ic_df = pd.DataFrame(train_ic_rows) if train_ic_rows else pd.DataFrame(columns=expr_names)
        val_ic_df = pd.DataFrame(val_ic_rows) if val_ic_rows else pd.DataFrame(columns=expr_names)
        train_mean = train_ic_df.mean(skipna=True)
        val_mean = val_ic_df.mean(skipna=True)
        n_train = train_ic_df.count()
        n_val = val_ic_df.count()

        for expr_name in expr_names:
            tm = float(train_mean.get(expr_name, np.nan))
            vm = float(val_mean.get(expr_name, np.nan))
            same_sign = (not np.isnan(tm) and not np.isnan(vm)
                         and np.sign(tm) == np.sign(vm) and tm != 0)
            results.append({
                "expression": expr_name, "horizon": horizon,
                "train_mean_ic": tm, "val_mean_ic": vm,
                "n_dates_train": int(n_train.get(expr_name, 0)),
                "n_dates_val": int(n_val.get(expr_name, 0)),
                "same_sign": same_sign,
            })

    res_df = pd.DataFrame(results)
    res_df.to_json(OUT_JSON, orient="records", force_ascii=False, indent=2)
    print(f"已存：{OUT_JSON}（{len(res_df)}列＝{n_expressions}表達式×{len(HORIZONS)}horizon）")
    return res_df


if __name__ == "__main__":
    main()
