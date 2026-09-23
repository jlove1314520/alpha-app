# -*- coding: utf-8 -*-
"""驗.四(資料一品質)（總司令2026-09-24裁示【候選名單定案＋抓取程式修正＋
開考前資料品質閘門】驗.四，與更早已完成的同名「驗.四」E-c/E-d regime
overlay無關，見PENDING_QUEUE.md消歧註記）：已抓132檔（已修.三修正抓取
程式之後、續抓剩餘168檔之前）的股利率資料品質稽核。

**驗證Cowork的推論**：`factors.py`舊版（修.三之前）`prepare_factors()`
用`except RuntimeError`把額度錯誤跟真正的資料缺失錯誤混在一起吞掉，導致
FinMind額度用盡時該檔股票的股利率被誤記成「已處理，股利率為NaN」而不是
「額度問題，該重抓」。本腳本檢查這個推論在實際checkpoint資料上是否成立。

**零額外API呼叫（安全設計）**：全程只讀本機既有parquet快取檔案
（`research/data/raw/*.parquet`），不呼叫`load_dev()`／不呼叫
`prepare_factors()`——這兩者都可能在快取缺失時觸發網路請求，而FinMind
目前仍在額度封鎖中，本稽核腳本必須在封鎖期間也能安全執行。**直接讀
parquet檔案本身就是本稽核最重要的證據**：一檔股票的`TaiwanStockDividend`
快取檔案存不存在，直接反映當初`load_dev()`呼叫有沒有真正成功過（成功
才會寫入快取，見`finmind_client.py::_fetch()`——命中額度時在寫入快取
之前就raise，不會留下任何快取檔案）。

用法：python research/audit_f52w_2007_data_quality.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids

CHECKPOINT_PATH = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"
DATA_DIR = Path(__file__).parent / "data" / "raw"
EXTENDED_START = "2006-01-01"
VAL_END_CAP = "2024-12-31"  # load_dev()一律用VAL_END當effective_end，見finmind_client.py
OOS_START, OOS_END = "2007-01-01", "2014-12-31"
DIVIDEND_YIELD_TRAILING_DAYS = 366  # 跟factors.py::_dividend_yield_ttm_cash()一致
OUT_JSON = Path(__file__).parent / "data" / "audit_f52w_2007_data_quality.json"


def _cache_path(dataset: str, data_id: str, start_date: str, end_date: str) -> Path:
    """跟finmind_client.py::_cache_path()逐行一致的重建（不import該函式是
    因為它是私有函式`_cache_path`，這裡改用同一套公式獨立重建路徑字串，
    避免import私有API；公式來源：finmind_client.py `_cache_path()`）。"""
    safe = lambda s: str(s).replace("/", "-").replace("\\", "-")
    return DATA_DIR / f"{safe(dataset)}__{safe(data_id)}__{safe(start_date)}__{safe(end_date)}.parquet"


def _price_cache_path(stock_id: str) -> Path:
    return _cache_path("TaiwanStockPrice", stock_id, EXTENDED_START, VAL_END_CAP)


def _dividend_cache_path(stock_id: str) -> Path:
    return _cache_path("TaiwanStockDividend", stock_id, EXTENDED_START, VAL_END_CAP)


def _compute_ttm_dividend_series(div_df: pd.DataFrame) -> pd.DataFrame:
    """跟factors.py::_dividend_yield_ttm_cash()完全一致的邏輯，獨立重寫一份
    （不import factors.py，避免任何觸發prepare_factors()週邊import鏈的
    可能性，維持本稽核腳本零副作用）。"""
    if div_df.empty or "CashExDividendTradingDate" not in div_df.columns:
        return pd.DataFrame(columns=["pit_date", "ttm_cash_dividend"])
    events = div_df[["CashExDividendTradingDate", "CashEarningsDistribution"]].copy()
    events = events.rename(columns={"CashExDividendTradingDate": "ex_date",
                                     "CashEarningsDistribution": "cash"})
    events["ex_date"] = events["ex_date"].replace("", np.nan)
    events = events.dropna(subset=["ex_date"])
    events["cash"] = pd.to_numeric(events["cash"], errors="coerce").fillna(0.0)
    events = events[events["cash"] > 0].sort_values("ex_date").reset_index(drop=True)
    if events.empty:
        return pd.DataFrame(columns=["pit_date", "ttm_cash_dividend"])
    ex_dates = pd.to_datetime(events["ex_date"])
    ttm = []
    for i in range(len(events)):
        window_start = ex_dates.iloc[i] - pd.Timedelta(days=DIVIDEND_YIELD_TRAILING_DAYS)
        mask = (ex_dates <= ex_dates.iloc[i]) & (ex_dates > window_start)
        ttm.append(events.loc[mask, "cash"].sum())
    events["ttm_cash_dividend"] = ttm
    events["pit_date"] = events["ex_date"]
    return events[["pit_date", "ttm_cash_dividend"]]


def audit_one_stock(sid: str) -> dict:
    row = {"stock_id": sid}

    div_path = _dividend_cache_path(sid)
    row["dividend_cache_exists"] = div_path.exists()
    price_path = _price_cache_path(sid)
    row["price_cache_exists"] = price_path.exists()

    if not div_path.exists():
        row["verdict"] = "DIVIDEND_CACHE_MISSING"
        row["has_dividend_records_2007_2014"] = None
        row["yield_nan_ratio_2007_2014"] = None
        return row

    div_df = pd.read_parquet(div_path)
    # 2007-2014期間是否確實有除息紀錄（不論股利率算不算得出來，這是Ground truth）
    has_records = False
    if not div_df.empty and "CashExDividendTradingDate" in div_df.columns:
        ex_dates_all = pd.to_datetime(div_df["CashExDividendTradingDate"].replace("", pd.NA)).dropna()
        cash_all = pd.to_numeric(div_df.get("CashEarningsDistribution", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        in_window = (ex_dates_all >= pd.Timestamp(OOS_START)) & (ex_dates_all <= pd.Timestamp(OOS_END))
        has_records = bool(((cash_all.reindex(ex_dates_all.index).fillna(0.0) > 0) & in_window).any())
    row["has_dividend_records_2007_2014"] = has_records

    if not price_path.exists():
        row["verdict"] = "PRICE_CACHE_MISSING（無法對齊算NaN比例）"
        row["yield_nan_ratio_2007_2014"] = None
        return row

    price_df = pd.read_parquet(price_path)
    if price_df.empty or "date" not in price_df.columns or "close" not in price_df.columns:
        row["verdict"] = "PRICE_CACHE_EMPTY_OR_MALFORMED"
        row["yield_nan_ratio_2007_2014"] = None
        return row
    price_df = price_df[["date", "close"]].copy()
    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df["close"] = pd.to_numeric(price_df["close"], errors="coerce")
    window_px = price_df[(price_df["date"] >= pd.Timestamp(OOS_START)) & (price_df["date"] <= pd.Timestamp(OOS_END))].copy()
    if window_px.empty:
        row["verdict"] = "NO_PRICE_ROWS_IN_2007_2014_WINDOW"
        row["yield_nan_ratio_2007_2014"] = None
        return row

    ttm_df = _compute_ttm_dividend_series(div_df)
    if ttm_df.empty:
        window_px["ttm_cash_dividend"] = np.nan
    else:
        ttm_df = ttm_df.sort_values("pit_date")
        ttm_df["pit_date"] = pd.to_datetime(ttm_df["pit_date"])
        window_px = window_px.sort_values("date")
        window_px = pd.merge_asof(window_px, ttm_df.rename(columns={"pit_date": "date"}),
                                   on="date", direction="backward")
    window_px["yield"] = np.where(window_px["close"] > 0,
                                   window_px["ttm_cash_dividend"] / window_px["close"], np.nan)
    n = len(window_px)
    n_nan = int(window_px["yield"].isna().sum())
    nan_ratio = n_nan / n if n else float("nan")
    row["n_price_rows_2007_2014"] = n
    row["yield_nan_ratio_2007_2014"] = round(nan_ratio, 4)

    if has_records and nan_ratio >= 0.999:
        row["verdict"] = "有除息紀錄但股利率全為NaN——推論成立，需移除重抓"
    elif has_records:
        row["verdict"] = f"有除息紀錄，股利率NaN比例={nan_ratio:.1%}（非全NaN，正常）"
    else:
        row["verdict"] = "本期無除息紀錄，股利率NaN為預期行為（非缺陷）"
    return row


def main():
    ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    ckpt = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    fetched = ckpt["fetched_ids"]
    failed = ckpt.get("failed_ids", {})
    successful = [sid for sid in fetched if sid not in failed]
    print(f"checkpoint: fetched={len(fetched)}  failed={len(failed)}  successful(需稽核)={len(successful)}", flush=True)

    assert fetched == ids[:len(fetched)], (
        "fetched_ids與sample_universe_ids()的前綴不吻合，索引重建法可能因為某次並發寫入"
        "事故而失去順序保證，回退為僅用successful清單逐檔稽核（不依賴索引推斷round分界）"
    )

    rows = [audit_one_stock(sid) for sid in successful]
    df = pd.DataFrame(rows)

    n_dividend_cache_missing = int((~df["dividend_cache_exists"]).sum())
    flagged = df[df["verdict"].astype(str).str.contains("推論成立", na=False)]
    print(f"\ndividend cache缺失（連快取檔都不存在，最強證據）：{n_dividend_cache_missing}/{len(df)}檔", flush=True)
    if n_dividend_cache_missing:
        print("  " + ", ".join(df[~df["dividend_cache_exists"]]["stock_id"].tolist()), flush=True)
    print(f"\n「有除息紀錄但股利率全為NaN」（需移除重抓）：{len(flagged)}檔", flush=True)
    if len(flagged):
        print("  " + ", ".join(flagged["stock_id"].tolist()), flush=True)

    # 三次撞額度斷點的股票（索引重建，見docstring/PENDING_QUEUE.md原始推導）
    stop_points = {"round1_stop_at_idx42": ids[42] if len(ids) > 42 else None,
                    "round2_stop_at_idx89": ids[89] if len(ids) > 89 else None,
                    "round3_stop_at_idx132": ids[132] if len(ids) > 132 else None}
    print(f"\n三次撞額度斷點股票：{stop_points}", flush=True)
    for label, sid in stop_points.items():
        if sid is None:
            continue
        hit = df[df["stock_id"] == sid]
        if hit.empty:
            print(f"  {label}={sid}：不在successful清單內（該檔本身就是斷點/或已知失敗，非本次稽核範圍）", flush=True)
        else:
            print(f"  {label}={sid}：{hit.iloc[0]['verdict']}", flush=True)

    to_requeue = flagged["stock_id"].tolist() + df[~df["dividend_cache_exists"]]["stock_id"].tolist()
    to_requeue = sorted(set(to_requeue))
    print(f"\n**排入重抓清單（{len(to_requeue)}檔）**：{to_requeue}", flush=True)

    out = {
        "n_successful_audited": len(df), "n_dividend_cache_missing": n_dividend_cache_missing,
        "n_flagged_has_records_all_nan": len(flagged), "stop_points": stop_points,
        "to_requeue": to_requeue, "rows": df.to_dict("records"),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)
    return out


if __name__ == "__main__":
    main()
