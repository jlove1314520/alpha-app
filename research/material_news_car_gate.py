"""`HYPOTHESIS_QUEUE.md` #52 事件反應速度 — 第1關cheap gate（8類`type`分類CAR檢定）。

規格見#52條目(g)/(l)段落：對每個`type`（法說會/併購/增減資/人事/財務/訴訟/處分資產/
停復牌，8大類，「其他」類事前排除——分類器混雜多種訊息類型，無明確經濟機制），
比較「事件日當日+次一交易日」累積異常報酬(CAR，用大盤TAIEX當基準)絕對值，是否
顯著大於隨機抽樣同數量非事件日的CAR絕對值分布（單邊null檢定）。

**PIT時間處理**（本假設事前綁定的PIT要求：事件時間戳必須是公告發布時刻，不是
抓取時刻）：`announce_time`欄位是MOPS原始`發言時間`（HH:MM:SS），台股收盤
13:30:00。若公告時間<=13:30:00視為當日盤中/盤前即可能被市場觀察到，
reaction_day=事件曆日對應的（或之後最近的）交易日；若>13:30:00視為盤後
公告，市場當天已收盤無法反應，reaction_day順延一個交易日。CAR窗口=
[reaction_day, reaction_day的次一交易日]，基準價=reaction_day前一個交易日
收盤（不用事件當天或reaction_day當天收盤價當基準，避免用到還沒發生的資訊）。

**零新增API呼叫**：只用本機已快取的`TaiwanStockPrice__{stock_id}__2010-01-01
__2024-12-31.parquet`（跟`factor_ic.py`/`buyback_car_gate.py`同一個快取慣例，
2,444/2,488個既有快取檔命中這個確切檔名，覆蓋事件宇宙2,400檔中的~1,800檔）。
沒有命中這個確切檔名的股票直接跳過（不呼叫`load_dev()`觸發新fetch），確保
這輪/背景job不消耗任何新的FinMind額度——這是刻意的保守設計，不是疏漏。

**控制組（2026-09-07`control_group_standard.py`升級標準，贏平均/90百分位都
不算過）**：兩個參數變體——(a)`matched_stock`：只從「該類別VAL期真的有事件」
的那些股票裡，抽跟真實事件數相同數量的隨機非事件交易日；(b)`unmatched_universe`：
從全部有快取價格的股票（不限定該類別）裡，抽相同數量的隨機(股票,交易日)組合。
各變體N_PERMUTATIONS=200次獨立抽樣，每次算全體pooled mean(|CAR|)，兩個變體
合併成control_draws傳給`evaluate_vs_control()`。通過門檻：訊號（VAL期真實
mean(|CAR|)）嚴格大於全部400次控制組抽樣的最大值，或配對式20/20全勝
（本腳本走量級這條路徑，未做配對式設計）。

2026-09-09 馬拉松TW軌round465新增。因需要載入~1,800檔股票完整歷史股價、
對8類×TRAIN/VAL共16組各跑200次permutation，預估遠超過session內5分鐘等待
上限，用`run_detached.py`背景執行，下一輪收成。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from bisect import bisect_left
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from finmind_client import load_dev
from material_news_classify import PRIORITY_ORDER
from validation import holdout

EVENTS_PATH = Path(__file__).parent / "data" / "mops_material_news_events_classified.parquet"
PRICE_RAW_DIR = Path(__file__).parent / "data" / "raw"
PRICE_START = "2010-01-01"  # 跟factor_ic.py/buyback_car_gate.py同一個值，命中既有快取慣例
CAR_HORIZON = 1  # "事件日當日+次一交易日"：reaction_day 到 reaction_day+1
MARKET_CLOSE_CUTOFF = "13:30:00"
N_PERMUTATIONS = 200
PERM_SEED = 20260909
OUT_JSON = Path(__file__).parent / "data" / "material_news_car_gate_result.json"

CATEGORIES = PRIORITY_ORDER  # 8大類，不含「其他」（PRIORITY_ORDER本身就不含「其他」）


def _eventdate_to_price_date(d: str) -> str:
    """事件表date欄位是'YYYYMMDD'字串，價格快取date欄位是'YYYY-MM-DD'。"""
    d = str(d)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def _cached_price_stock_ids() -> set[str]:
    ids = set()
    for f in glob.glob(str(PRICE_RAW_DIR / f"TaiwanStockPrice__*__{PRICE_START}__2024-12-31.parquet")):
        base = os.path.basename(f)
        parts = base.replace(".parquet", "").split("__")
        ids.add(parts[1])
    return ids


def _load_price_map(stock_id: str) -> dict | None:
    path = PRICE_RAW_DIR / f"TaiwanStockPrice__{stock_id}__{PRICE_START}__2024-12-31.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    df = df[df["date"] <= holdout.VAL_END]  # 防禦性二次確認，跟load_dev()同精神
    if len(df) < 260:
        return None
    dates = df["date"].tolist()
    close = df["close"].astype(float).to_numpy()
    # 事前算好VAL期「可算CAR的index」，permutation迴圈重複用，不要每次重算
    # （原本每個permutation、每檔股票都重掃一次~3700天的list comprehension，
    # 8類x200次permutation x最多~1800檔會慢到無法在detached timeout內跑完）。
    valid_idx_val = np.array(
        [i for i, d in enumerate(dates)
         if holdout.TRAIN_END < d <= holdout.VAL_END and 0 < i and i + CAR_HORIZON < len(dates)],
        dtype=np.int64,
    )
    return {"dates": dates, "close": close, "valid_idx_val": valid_idx_val}


def _market_map() -> dict:
    m = load_dev("TaiwanStockPrice", "TAIEX", PRICE_START)
    holdout.assert_no_holdout_leakage(m, context="market_raw in material_news_car_gate")
    m = m.sort_values("date").reset_index(drop=True)
    return {"dates": m["date"].tolist(), "close": m["close"].astype(float).to_numpy(),
            "idx": {d: i for i, d in enumerate(m["date"].tolist())}}


def _reaction_idx(dates: list[str], event_price_date: str, after_close: bool) -> int | None:
    """回傳reaction_day在dates裡的index。dates已排序遞增。"""
    i = bisect_left(dates, event_price_date)
    if i >= len(dates):
        return None
    if dates[i] == event_price_date:
        return i + 1 if after_close else i
    # event_price_date不是交易日（假日/週末），i已經是"之後第一個交易日"，
    # 不論公告時間是否盤後，市場都只能在那一天才第一次看到
    return i


def _car(dates: list[str], close: np.ndarray, mkt_idx: dict, mkt_close: np.ndarray,
          reaction_idx: int | None) -> float | None:
    if reaction_idx is None:
        return None
    baseline_idx = reaction_idx - 1
    end_idx = reaction_idx + CAR_HORIZON
    if baseline_idx < 0 or end_idx >= len(dates):
        return None
    p0, p1 = close[baseline_idx], close[end_idx]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[baseline_idx], dates[end_idx]
    mi0, mi1 = mkt_idx.get(d0), mkt_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0 or np.isnan(m0) or np.isnan(m1):
        return None
    mkt_ret = m1 / m0 - 1
    return abs(stock_ret - mkt_ret)


def _build_events(max_stocks: int | None = None, max_categories: int | None = None) -> tuple[pd.DataFrame, dict]:
    ev = pd.read_parquet(EVENTS_PATH)
    cats = CATEGORIES if max_categories is None else CATEGORIES[:max_categories]
    ev = ev[ev["type"].isin(cats)].copy()
    cached_ids = _cached_price_stock_ids()
    ev = ev[ev["stock_id"].isin(cached_ids)].copy()
    if max_stocks is not None:
        keep_ids = sorted(ev["stock_id"].unique())[:max_stocks]
        ev = ev[ev["stock_id"].isin(keep_ids)].copy()
    ev["price_date"] = ev["date"].map(_eventdate_to_price_date)
    ev["after_close"] = ev["announce_time"].astype(str) > MARKET_CLOSE_CUTOFF
    return ev, {"cached_ids": cached_ids, "cats": cats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stocks", type=int, default=None, help="限制載入股票數（smoke test用）")
    ap.add_argument("--max-categories", type=int, default=None, help="限制分類數（smoke test用）")
    ap.add_argument("--n-permutations", type=int, default=N_PERMUTATIONS)
    args = ap.parse_args()

    print("=== 假設#52 事件反應速度 CAR事件研究 第1關cheap gate ===")
    ev, meta = _build_events(max_stocks=args.max_stocks, max_categories=args.max_categories)
    print(f"事件表過濾後（8類+已快取股票）：{len(ev)}筆，"
          f"涉及股票{ev['stock_id'].nunique()}檔（快取命中{len(meta['cached_ids'])}檔），"
          f"分類{meta['cats']}")

    holdout.assert_no_holdout_leakage(ev, date_col="price_date", context="material_news_car_gate events (raw)")

    mkt = _market_map()

    price_cache: dict[str, dict] = {}
    stock_ids = sorted(ev["stock_id"].unique())
    for i, sid in enumerate(stock_ids):
        pm = _load_price_map(sid)
        if pm is not None:
            price_cache[sid] = pm
        if (i + 1) % 200 == 0:
            print(f"  價格載入進度 {i+1}/{len(stock_ids)}，{len(price_cache)}檔可用")
    print(f"價格可用股票數：{len(price_cache)}/{len(stock_ids)}")

    rows = []
    for r in ev.itertuples(index=False):
        pm = price_cache.get(r.stock_id)
        if pm is None:
            continue
        ridx = _reaction_idx(pm["dates"], r.price_date, bool(r.after_close))
        car = _car(pm["dates"], pm["close"], mkt["idx"], mkt["close"], ridx)
        if car is None:
            continue
        rows.append({"stock_id": r.stock_id, "type": r.type, "price_date": r.price_date,
                     "reaction_idx_date": pm["dates"][ridx] if ridx is not None else None, "abs_car": car})

    if not rows:
        print("SANITY FAIL：零事件可用CAR（不是無訊號，是資料層有問題）。")
        result = {"sanity_fail": True}
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    car_df = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(car_df, date_col="reaction_idx_date",
                                       context="material_news_car_gate events (final)")
    print(f"\n可用CAR事件總數：{len(car_df)}（{car_df['stock_id'].nunique()}檔股票）")

    train_mask = car_df["reaction_idx_date"] <= holdout.TRAIN_END
    val_mask = (car_df["reaction_idx_date"] > holdout.TRAIN_END) & (car_df["reaction_idx_date"] <= holdout.VAL_END)
    train_df, val_df = car_df[train_mask], car_df[val_mask]

    # 全體有快取價格的股票x VAL期可用交易日index，供unmatched_universe控制組抽樣
    all_valid_pairs = []  # (stock_id, idx) pairs, VAL期、可算CAR（reaction_idx=idx本身即可，允許idx=任意reaction位置)
    for sid, pm in price_cache.items():
        for idx in pm["valid_idx_val"]:
            all_valid_pairs.append((sid, int(idx)))
    print(f"unmatched_universe候選池大小（VAL期可算CAR的(股票,交易日)組合）：{len(all_valid_pairs)}")

    rng = np.random.RandomState(PERM_SEED)
    results = {}
    for cat in meta["cats"]:
        cat_train = train_df[train_df["type"] == cat]
        cat_val = val_df[val_df["type"] == cat]
        n_train, n_val = len(cat_train), len(cat_val)
        if n_val < 20:
            results[cat] = {"n_train": n_train, "n_val": n_val, "skipped": "n_val<20"}
            print(f"\n[{cat}] n_val={n_val}<20，樣本太少，跳過")
            continue
        signal_stat = float(cat_val["abs_car"].mean())
        same_sign_note = "n/a（都是絕對值，恆為正）"

        # 控制組變體(a) matched_stock：只從該類別VAL期真的有事件的股票裡抽
        cat_stock_ids = sorted(cat_val["stock_id"].unique())
        n_pick_by_stock = cat_val["stock_id"].value_counts().to_dict()
        # 事前把每檔股票的(dates, close, valid_idx, n_pick)收斂成一份list，
        # permutation迴圈只做抽樣+CAR計算，不重算valid_idx（見_load_price_map註解）
        stock_plan = []
        for sid in cat_stock_ids:
            pm = price_cache.get(sid)
            if pm is None or len(pm["valid_idx_val"]) == 0:
                continue
            n_pick = max(1, int(n_pick_by_stock.get(sid, 1)))
            stock_plan.append((pm["dates"], pm["close"], pm["valid_idx_val"], min(n_pick, len(pm["valid_idx_val"]))))

        matched_draws = []
        for _ in range(args.n_permutations):
            pseudo = []
            for dates, close, valid_idx, n_pick in stock_plan:
                picks = rng.choice(valid_idx, size=n_pick, replace=False)
                for idx in picks:
                    c = _car(dates, close, mkt["idx"], mkt["close"], int(idx))
                    if c is not None:
                        pseudo.append(c)
            if pseudo:
                matched_draws.append(float(np.mean(pseudo)))

        # 控制組變體(b) unmatched_universe：從全部有快取價格的股票裡抽相同數量的(股票,交易日)組合
        unmatched_draws = []
        if all_valid_pairs:
            pool_idx = np.arange(len(all_valid_pairs))
            for _ in range(args.n_permutations):
                picks = rng.choice(pool_idx, size=min(n_val, len(pool_idx)), replace=False)
                pseudo = []
                for pi in picks:
                    sid, idx = all_valid_pairs[pi]
                    pm = price_cache[sid]
                    c = _car(pm["dates"], pm["close"], mkt["idx"], mkt["close"], idx)
                    if c is not None:
                        pseudo.append(c)
                if pseudo:
                    unmatched_draws.append(float(np.mean(pseudo)))

        control_draws = {}
        if len(matched_draws) >= 20:
            control_draws["matched_stock"] = matched_draws
        if len(unmatched_draws) >= 20:
            control_draws["unmatched_universe"] = unmatched_draws

        if len(control_draws) < 2:
            results[cat] = {"n_train": n_train, "n_val": n_val, "signal_stat": signal_stat,
                             "skipped": f"control_draws變體不足({list(control_draws.keys())})"}
            print(f"\n[{cat}] 控制組變體不足，無法判定：{list(control_draws.keys())}")
            continue

        verdict = evaluate_vs_control(
            signal_stat=signal_stat,
            control_draws=control_draws,
            selection_spec=(f"#52事件反應速度gate1，事前綁定：type={cat}，VAL期(2021-01-01~2024-12-31)"
                             f"mean(|CAR|)，CAR窗口=reaction_day+次一交易日，基準=reaction_day前一交易日收盤，"
                             f"reaction_day依announce_time<=13:30:00判定是否順延一日；唯一選點，"
                             f"不依結果回頭調整窗口或分類。"),
        )
        results[cat] = {
            "n_train": n_train, "n_val": n_val, "signal_stat": signal_stat,
            "train_mean_abs_car": float(cat_train["abs_car"].mean()) if n_train else None,
            "passed": verdict.passed, "reason": verdict.reason,
            "control_max": verdict.control_max, "control_mean": verdict.control_mean,
            "control_percentile": verdict.control_percentile, "n_variants": verdict.n_variants,
            "n_draws_total": verdict.n_draws_total, "selection_sha256": verdict.selection_sha256,
        }
        print(f"\n[{cat}] n_train={n_train} n_val={n_val} "
              f"VAL_mean|CAR|={signal_stat:.4f} TRAIN_mean|CAR|={results[cat]['train_mean_abs_car']:.4f} "
              f"{'PASS' if verdict.passed else 'FAIL'}: {verdict.reason}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存完整結果：{OUT_JSON}")
    n_pass = sum(1 for r in results.values() if r.get("passed"))
    print(f"\n=== 8類中共{n_pass}類PASS ===")
    return results


if __name__ == "__main__":
    main()
