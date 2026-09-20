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

import mem_guard  # 2026-09-20事件001補正：真正的記憶體安全閥（belt-and-suspenders，主要防護已是本檔案自己的日期壓縮設計）
mem_guard.install()

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


def is_degenerate_benchmark_only(expr_name: str) -> bool:
    """2026-09-20總司令裁示【原子.二FAIL採信，轉財報原子家族；補佇列】
    二新增：判斷一個表達式名稱是不是「純基準原子window/scalar轉換、
    沒有結合任何個股原子」——這類表達式在cross-sectional橫斷面上對每
    檔股票取值完全相同，Spearman IC結構性退化（詳見`ATOM_IC_MAP.md`
    第3節，本輪實測3184個測試裡約860個屬於這類）。

    **本函式不回頭套用在`compute_all_expressions()`本身**——原子.二
    的3184個測試已經事前登記、執行、計入`selection_bias_ledger`的N，
    回頭過濾等於竄改已登記的搜尋空間，不做。**這支函式是給未來新的
    表達式產生器（例如原子.五財報版、或任何後續會用到基準原子的
    搜尋空間）在生成階段就排除這類組合用的**，讓結構性退化的組合
    根本不進事前登記的N，不是本檔案自己的產生邏輯要改。"""
    if expr_name.startswith("ts_corr__"):
        return False  # ts_corr(股票原子,基準原子,n)本身結合了個股原子，不退化
    return any(f"__{b}" in expr_name or expr_name.endswith(b) for b in BENCH_ATOM_NAMES)


def main():
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    print(f"market_df: {len(market_df)}天")

    # 記憶體設計（2026-09-20修復：300檔全量跑第一版把每檔股票「全部1592個
    # 表達式×全部交易日」都以float64留在記憶體，實測單一Python行程private
    # memory衝到約19GB，把使用者機器的31GB實體記憶體幾乎耗盡到只剩1.26GB
    # 可用——這是真正發生過的事故，不是理論風險，已在互動視窗裡把那個
    # 行程手動kill掉）。**修法**：cross-sectional IC分析真正需要的只有
    # 每個snapshot的as_of/fwd兩個日期的值，不需要整個歷史序列常駐記憶體。
    # 所以先把兩個horizon全部的snapshot算出來，取as_of∪fwd日期聯集，
    # 每檔股票算完1592個表達式後**立刻reindex到這個聯集日期、丟掉其餘
    # 全部歷史列**，把每檔股票的常駐大小從「全部交易日×1592欄」壓到
    # 「約300個日期×1592欄」，實測記憶體壓力從19GB降到可控範圍。
    needed_dates: set[pd.Timestamp] = set()
    snapshots_by_horizon: dict[int, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for horizon in HORIZONS:
        calendar = sorted(market_df["date"].unique())
        snaps = build_snapshots(calendar, calendar[0], calendar[-1], horizon=horizon)
        snaps = [(pd.Timestamp(a), pd.Timestamp(f)) for a, f in snaps]
        snapshots_by_horizon[horizon] = snaps
        for a, f in snaps:
            needed_dates.add(a)
            needed_dates.add(f)
    needed_dates_idx = pd.DatetimeIndex(sorted(needed_dates))
    print(f"snapshot所需的聯集日期數：{len(needed_dates_idx)}"
          f"（遠小於全部交易日，這是記憶體壓縮的關鍵）")

    ids = sample_universe_ids(SAMPLE_SIZE)
    print(f"樣本宇宙: {len(ids)}檔，開始載入價格+補amt+算表達式（逐檔立即"
          f"壓縮到所需日期，不常駐全歷史）...")

    expr_names: list[str] | None = None
    indexed_exprs: dict[str, pd.DataFrame] = {}
    indexed_close: dict[str, pd.Series] = {}
    n_loaded = 0
    for i, sid in enumerate(ids):
        try:
            from adjust import adjusted_price_series
            px = adjusted_price_series(sid, START_DATE)
        except Exception:  # noqa: BLE001
            continue
        if px.empty or len(px) < 260:
            continue
        px = _merge_amt(px, sid)
        df = build_atom_df(px)
        try:
            exprs = compute_all_expressions(df)
        except Exception as e:  # noqa: BLE001 -- 描述性掃描，單檔算子出錯不中斷整批
            print(f"  [警告] {sid}計算表達式失敗，跳過：{e}")
            continue
        if expr_names is None:
            expr_names = list(exprs.keys())

        dates = pd.DatetimeIndex(df["date"])
        wide = pd.DataFrame(exprs)
        wide.index = dates
        wide = wide[~wide.index.duplicated(keep="first")]
        close_s = pd.Series(df["c"].values, index=dates)
        close_s = close_s[~close_s.index.duplicated(keep="first")]
        # 立刻壓縮到所需日期聯集——這一步做完，wide/close_s的大版本就可以
        # 被垃圾回收，只有壓縮後的小版本留在indexed_exprs/indexed_close裡。
        indexed_exprs[sid] = wide.reindex(needed_dates_idx.intersection(wide.index))
        indexed_close[sid] = close_s.reindex(needed_dates_idx.intersection(close_s.index))
        del df, exprs, wide, close_s, px

        n_loaded += 1
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(ids)}（可用{n_loaded}檔）")
    print(f"可用股票: {n_loaded}/{len(ids)}")

    n_expressions = len(expr_names) if expr_names else 0
    print(f"每檔股票的表達式數：{n_expressions}（事前登記應為1592，"
          f"960+72+560=1592，若不符表示分類算子/原子/窗口計數有誤）")

    results = []
    for horizon in HORIZONS:
        # snapshot序列已在檔案開頭統一算好（見needed_dates_idx那段的說明），
        # 這裡直接取用，不重算，維持跟原本一致的行為。
        snapshots = snapshots_by_horizon[horizon]
        print(f"horizon={horizon}日: {len(snapshots)}個snapshot")

        train_ic_rows, val_ic_rows = [], []
        all_ic_rows_by_date: dict[pd.Timestamp, pd.Series] = {}
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
            all_ic_rows_by_date[as_of] = ic_row  # 快取逐snapshot IC，供年份/牛熊段拆解重跑用，不需要重載300檔資料
            if as_of <= pd.Timestamp(holdout.TRAIN_END):
                train_ic_rows.append(ic_row)
            elif as_of <= pd.Timestamp(holdout.VAL_END):
                val_ic_rows.append(ic_row)
            if (si + 1) % 10 == 0:
                print(f"  horizon={horizon} snapshot {si+1}/{len(snapshots)}")

        # 快取逐snapshot IC矩陣（index=as_of時間戳，columns=expr_names），
        # 讓「分年份/分牛熊段穩定度」這類事後聚合分析可以直接讀這份快取
        # 重算，不需要重跑300檔資料載入+depth-1表達式計算（那才是本腳本
        # 真正耗時的部分，聚合方式本身只是輕量的groupby）。
        if all_ic_rows_by_date:
            snap_df = pd.DataFrame(all_ic_rows_by_date).T.sort_index()
            snap_cache_path = Path(__file__).parent / f"atom_ic_snapshots_h{horizon}.parquet"
            snap_df.to_parquet(snap_cache_path)
            print(f"已存逐snapshot IC快取：{snap_cache_path}（{len(snap_df)}個snapshot×{len(snap_df.columns)}表達式）")

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


# 危機視窗清單，來源：`REGIME_OVERLAY_PROTOCOL.md`第2節（總司令原始指示的
# 6個歷史危機視窗，2008因早於資料起點2010-01-04完全沒有資料排除）。
# 用來把每個snapshot的as_of日期標成「熊市段」或「其餘（常態/牛市）」，
# 這是本專案既有的規範，不是本輪新發明的regime定義。
CRISIS_WINDOWS = [
    ("2011歐債危機", "2011-07-01", "2011-12-31"),
    ("2015中國股災", "2015-06-01", "2015-09-30"),
    ("2018Q4貿易戰", "2018-10-01", "2018-12-31"),
    ("2020Q1新冠崩盤", "2020-02-01", "2020-04-30"),
    ("2022全年空頭", "2022-01-01", "2022-12-31"),
]


def _label_regime(as_of: pd.Timestamp) -> str:
    for name, start, end in CRISIS_WINDOWS:
        if pd.Timestamp(start) <= as_of <= pd.Timestamp(end):
            return name
    return "常態/牛市"


def aggregate_by_year_and_regime() -> pd.DataFrame:
    """讀`main()`已經存好的逐snapshot IC快取（`atom_ic_snapshots_h{horizon}
    .parquet`），對每個表達式分年份與分牛熊段算平均IC與同號穩定度，不需要
    重新載入300檔股票資料——這是原子.二規格要求的「分年份與分牛熊段的
    穩定度」最後一步，`main()`本身只算了TRAIN/VAL兩段聚合，這支函式補上
    更細的顆粒度。"""
    rows = []
    for horizon in HORIZONS:
        cache_path = Path(__file__).parent / f"atom_ic_snapshots_h{horizon}.parquet"
        if not cache_path.exists():
            print(f"[警告] 找不到{cache_path}，horizon={horizon}無法拆解，"
                  f"需先跑一次`python atom_ic_map.py`產生快取")
            continue
        snap_df = pd.read_parquet(cache_path)
        snap_df.index = pd.to_datetime(snap_df.index)
        years = snap_df.index.year
        regimes = pd.Series([_label_regime(ts) for ts in snap_df.index], index=snap_df.index)

        for expr_name in snap_df.columns:
            s = snap_df[expr_name]
            by_year = s.groupby(years).mean(numeric_only=True)
            by_year_n = s.groupby(years).count()
            by_regime = s.groupby(regimes).mean(numeric_only=True)
            by_regime_n = s.groupby(regimes).count()
            year_signs = np.sign(by_year.dropna())
            year_signs = year_signs[year_signs != 0]
            year_same_sign_rate = (float((year_signs == year_signs.mode().iloc[0]).mean())
                                    if len(year_signs) else np.nan)
            crisis_regimes = [n for n, _, _ in CRISIS_WINDOWS]
            crisis_vals = by_regime.reindex(crisis_regimes).dropna()
            crisis_signs = np.sign(crisis_vals)
            crisis_signs = crisis_signs[crisis_signs != 0]
            crisis_same_sign = bool(crisis_signs.nunique() <= 1) if len(crisis_signs) else False
            rows.append({
                "expression": expr_name, "horizon": horizon,
                "by_year_ic": {int(y): (None if pd.isna(v) else float(v)) for y, v in by_year.items()},
                "by_year_n": {int(y): int(n) for y, n in by_year_n.items()},
                "year_same_sign_rate": (None if pd.isna(year_same_sign_rate) else year_same_sign_rate),
                "by_regime_ic": {k: (None if pd.isna(v) else float(v)) for k, v in by_regime.items()},
                "by_regime_n": {k: int(n) for k, n in by_regime_n.items()},
                "n_crisis_windows_with_data": int(len(crisis_vals)),
                "crisis_windows_same_sign": crisis_same_sign,
            })

    out_df = pd.DataFrame(rows)
    out_path = Path(__file__).parent / "atom_ic_map_year_regime.json"
    out_df.to_json(out_path, orient="records", force_ascii=False, indent=2)
    print(f"已存：{out_path}（{len(out_df)}列＝表達式×horizon，"
          f"含分年份/分牛熊段IC與同號穩定度）")
    return out_df


if __name__ == "__main__":
    import sys
    if "--aggregate-only" in sys.argv:
        aggregate_by_year_and_regime()
    else:
        main()
        aggregate_by_year_and_regime()
