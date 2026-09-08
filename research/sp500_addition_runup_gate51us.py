# -*- coding: utf-8 -*-
"""#51-US 強制交易者事件（美股版）第1關cheap gate：S&P指數新增（Addition）
公告日→生效日「搶跑漲幅」（index-effect run-up，Harris & Gurel 1986等文獻
已大量研究的現象，近二十年因套利搶跑而明顯減弱甚至反轉——測試前不預設會過）。

**事前綁定（本檔案寫成後、跑出任何數字之前就定案，不得看到結果回頭改）**：

1. **只測Addition，不測Deletion**：Deletion事件常見成因是被收購/破產下市，
   命中`CLAUDE.md`「下市股資料：取得不等於正確」的已知污染雷（yfinance對
   已下市股覆蓋率極低、殘留OTC空殼報價會混入假報酬）。Addition的公司在
   納入當下必然仍是活躍可交易的實體（否則不會被選入指數），不會踩到這個雷，
   這是選擇「只測Addition」的唯一理由，不是為了讓訊號好看而挑的子集。
2. **事件視窗＝公告日（article_date_raw，新聞稿發布日）→生效日
   （effective_date_raw）**，兩端都用該股票自己的yfinance交易日曆對齊
   （公告日非交易日則取下一個交易日；生效日理論上必為交易日，仍同法防呆）。
   signal＝CAR = close[生效日idx] / close[公告日idx] - 1，事前方向假設為正
   （被動基金搶跑買進推升股價）。
3. **價格來源**：`yf_price_client.fetch_yf_index()`（yfinance，無台股後綴，
   ticker原樣使用）——**不用`us_factors.us_price_series()`**，因為那支走
   FinMind `USStockPrice`，違反`CLAUDE.md`2026-09-08裁示「禁止用台灣資料商
   作為美股宇宙或價格的主來源」。`fetch_yf_index`原本是為了抓大盤指數
   （^TWII）寫的，但它的`_fetch_one_suffix(ticker, "", ...)`本來就是「代碼
   原樣使用、不加任何後綴」，對美股個股一樣適用，本檔案重用它而非另開一支
   幾乎一樣的客戶端。
4. **控制組**（2026-09-07升級標準，兩個獨立變體，各N=200，通過門檻＝訊號
   嚴格大於全部400次抽樣最大值）：
   - `own_ticker_window`：對每個事件，從**同一檔股票自己的**價格歷史裡隨機
     抽一個等長度的窗口（排除所有真事件窗口前後`CONTROL_EXCLUSION_BUFFER`
     個交易日），算同樣定義的報酬。
   - `cross_ticker_window`：從**同一批Addition事件池中隨機挑另一檔股票**
     （而非固定同一檔）的價格歷史裡隨機抽等長度窗口，排除規則同上。這個
     變體用來排除「這批入選S&P的股票本來就處於上升趨勢／同期大盤上漲」
     這種與『被指數基金追蹤』完全無關的偽陽性——只有`own_ticker_window`
     可能還是抓到「這檔股票入選前後剛好在噴出期」的混淆，`cross_ticker_
     window`把這個混淆源換成隨機配對，才是真正獨立的第二個變體（符合
     `control_group_standard.py`「控制組自身參數要掃」的精神，此處掃的是
     「抽樣母體」而非單純換種子）。
5. **TRAIN/VAL切分**依`validation.holdout`（TRAIN_END=2020-12-31，
   VAL_END=2024-12-31），依生效日分期；判定看VAL期。
6. **樣本量下限**：TRAIN或VAL任一期可用事件數<10即整體SKIP（樣本太少沒有
   意義），沿用本佇列既有慣例（`cbc_decision_event_gate61.py`同款門檻）。

執行方式：
    python research/sp500_addition_runup_gate51us.py --max-events 50 --n-draws 25   # smoke test
    python research/sp500_addition_runup_gate51us.py                                 # 正式全量（N=200 x2變體）
輸出：`data/sp500_addition_runup_gate51us_result.json`
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from control_group_standard import evaluate_vs_control
from sp500_index_changes_client import load_all_cached_articles
from validation import holdout
from yf_price_client import fetch_yf_index

RESULT_PATH = Path(__file__).parent / "data" / "sp500_addition_runup_gate51us_result.json"

CONTROL_EXCLUSION_BUFFER = 10  # 交易日，同us_8k_pead_gate52.py既有慣例
N_CONTROL_DRAWS_DEFAULT = 200
CONTROL_SEEDS = {"own_ticker_window": 20260909_511, "cross_ticker_window": 20260909_512}
PRICE_START = "2010-01-01"
MAX_WINDOW_TRADING_DAYS = 60  # 防呆：公告日到生效日超過這麼多交易日視為資料異常，跳過不用


def _clean_ticker(t: str) -> str | None:
    if not isinstance(t, str):
        return None
    t = t.strip().upper()
    if not t or not re.fullmatch(r"[A-Z.\-]{1,10}", t):
        return None
    return t


def build_addition_events() -> pd.DataFrame:
    """從已快取文章彙總出乾淨的Addition事件表：ticker/company_name/index_name/
    announce_date(ISO)/effective_date(ISO)。剔除action非Addition、ticker/日期
    無法解析、生效日早於公告日（資料錯誤，順序不可能反過來）的列。"""
    df = load_all_cached_articles()
    if df.empty:
        return pd.DataFrame(columns=["ticker", "company_name", "index_name",
                                      "announce_date", "effective_date"])
    df = df[df["action"] == "Addition"].copy()
    df["ticker"] = df["ticker"].apply(_clean_ticker)
    df["announce_date"] = pd.to_datetime(df["article_date_raw"], errors="coerce")
    df["effective_date"] = pd.to_datetime(df["effective_date_raw"], errors="coerce")
    df = df.dropna(subset=["ticker", "announce_date", "effective_date"])
    df = df[df["effective_date"] >= df["announce_date"]]
    df["announce_date"] = df["announce_date"].dt.strftime("%Y-%m-%d")
    df["effective_date"] = df["effective_date"].dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates(subset=["ticker", "effective_date"]).reset_index(drop=True)
    return df[["ticker", "company_name", "index_name", "announce_date", "effective_date"]]


def _price_calendar(ticker: str) -> pd.DataFrame | None:
    px = fetch_yf_index(ticker, start_date=PRICE_START, end_date=None)
    if px.empty or len(px) < 30:
        return None
    return px.sort_values("date").reset_index(drop=True)


def _trading_day_idx(dates: list[str], target: str) -> int | None:
    """target非交易日則取下一個交易日；超過序列末端回傳None。"""
    if target in dates:
        return dates.index(target)
    later = [d for d in dates if d > target]
    if not later:
        return None
    return dates.index(later[0])


def process_event(row: pd.Series, calendars: dict[str, pd.DataFrame],
                   skip_summary: dict) -> dict | None:
    ticker = row["ticker"]
    px = calendars.get(ticker)
    if px is None:
        skip_summary["no_price_history"] = skip_summary.get("no_price_history", 0) + 1
        return None
    dates = px["date"].tolist()
    closes = px["close"].tolist()
    idx_a = _trading_day_idx(dates, row["announce_date"])
    idx_e = _trading_day_idx(dates, row["effective_date"])
    if idx_a is None or idx_e is None:
        skip_summary["out_of_price_range"] = skip_summary.get("out_of_price_range", 0) + 1
        return None
    if idx_e <= idx_a:
        skip_summary["effective_not_after_announce"] = skip_summary.get("effective_not_after_announce", 0) + 1
        return None
    if idx_e - idx_a > MAX_WINDOW_TRADING_DAYS:
        skip_summary["window_too_long_suspect_data_error"] = skip_summary.get(
            "window_too_long_suspect_data_error", 0) + 1
        return None
    p0, p1 = closes[idx_a], closes[idx_e]
    if p0 is None or p1 is None or pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        skip_summary["bad_price_value"] = skip_summary.get("bad_price_value", 0) + 1
        return None
    car = p1 / p0 - 1.0
    period = "TRAIN" if row["effective_date"] <= holdout.TRAIN_END else (
        "VAL" if row["effective_date"] <= holdout.VAL_END else "OUT_OF_RANGE")
    return {
        "ticker": ticker, "announce_date": row["announce_date"], "effective_date": row["effective_date"],
        "idx_a": idx_a, "idx_e": idx_e, "window_len": idx_e - idx_a, "car": car, "period": period,
    }


def draw_own_ticker_control(ev: dict, calendars: dict[str, pd.DataFrame],
                             eligible_by_ticker: dict[str, list[int]], rng: random.Random) -> float | None:
    win = ev["window_len"]
    pool = eligible_by_ticker.get(ev["ticker"])
    if not pool:
        return None
    n = len(calendars[ev["ticker"]])
    starts = [i for i in pool if i + win < n]
    if not starts:
        return None
    start = rng.choice(starts)
    closes = calendars[ev["ticker"]]["close"].tolist()
    if start + win >= len(closes):
        return None
    p0, p1 = closes[start], closes[start + win]
    if p0 is None or pd.isna(p0) or p0 <= 0 or p1 is None or pd.isna(p1):
        return None
    return p1 / p0 - 1.0


def draw_cross_ticker_control(ev: dict, all_tickers: list[str], calendars: dict[str, pd.DataFrame],
                               eligible_by_ticker: dict[str, list[int]], rng: random.Random) -> float | None:
    win = ev["window_len"]
    for _ in range(5):  # 最多重試5次找一檔有足夠eligible天數的股票，避免無限迴圈
        other = rng.choice(all_tickers)
        pool = eligible_by_ticker.get(other)
        closes = calendars[other]["close"].tolist() if other in calendars else []
        starts = [i for i in pool if i + win < len(closes)] if pool else []
        if starts:
            start = rng.choice(starts)
            p0, p1 = closes[start], closes[start + win]
            if p0 and not pd.isna(p0) and p0 > 0 and p1 is not None and not pd.isna(p1):
                return p1 / p0 - 1.0
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-events", type=int, default=None, help="smoke test用：限制事件數")
    ap.add_argument("--n-draws", type=int, default=N_CONTROL_DRAWS_DEFAULT)
    args = ap.parse_args()

    if holdout.is_holdout_consumed():
        print("ABORT: holdout already consumed, refusing to run")
        return 1

    events_df = build_addition_events()
    print(f"=== #51-US cheap gate: S&P Addition 公告→生效日搶跑漲幅 ===")
    print(f"乾淨Addition事件表：{len(events_df)}筆（{events_df['ticker'].nunique()}個不重複ticker）")
    if args.max_events:
        events_df = events_df.head(args.max_events)
        print(f"smoke test模式，限制前{args.max_events}筆")

    tickers = sorted(events_df["ticker"].unique().tolist())
    calendars: dict[str, pd.DataFrame] = {}
    for t in tickers:
        px = _price_calendar(t)
        if px is not None:
            calendars[t] = px
    print(f"{len(calendars)}/{len(tickers)} ticker取得yfinance價格歷史（>=30個交易日）")

    skip_summary: dict = {}
    rows = []
    for _, row in events_df.iterrows():
        r = process_event(row, calendars, skip_summary)
        if r is not None:
            rows.append(r)
    print(f"可用事件數={len(rows)}（skip原因: {skip_summary}）")
    events = pd.DataFrame(rows)
    if events.empty:
        print("SANITY FAIL: 無可用事件")
        return {"passes": False, "reason": "no_usable_events"}

    holdout.assert_no_holdout_leakage(events, date_col="effective_date",
                                       context="sp500_addition_runup_gate51us events (final)")

    eligible_by_ticker: dict[str, list[int]] = {}
    real_idx_by_ticker: dict[str, set[int]] = {}
    for r in rows:
        real_idx_by_ticker.setdefault(r["ticker"], set()).update(range(r["idx_a"], r["idx_e"] + 1))
    for t, px in calendars.items():
        n = len(px)
        excluded = set()
        for center in real_idx_by_ticker.get(t, set()):
            for off in range(-CONTROL_EXCLUSION_BUFFER, CONTROL_EXCLUSION_BUFFER + 1):
                excluded.add(center + off)
        eligible_by_ticker[t] = [i for i in range(0, n) if i not in excluded]

    usable_tickers = [t for t in calendars if eligible_by_ticker.get(t)]

    results = {}
    for period in ("TRAIN", "VAL"):
        period_events = [r for r in rows if r["period"] == period]
        n_ev = len(period_events)
        print(f"\n--- {period} ---")
        print(f"n_events={n_ev}")
        if n_ev < 10:
            print(f"SKIP: {period}事件數<10，樣本太少")
            results[period] = {"skipped": True, "n_events": n_ev}
            continue
        signal_stat = float(np.mean([r["car"] for r in period_events]))
        print(f"real CAR(公告→生效) mean = {signal_stat:.4%} (n={n_ev})")

        control_draws = {}
        for name, seed in CONTROL_SEEDS.items():
            rng = random.Random(seed)
            draws = []
            for _ in range(args.n_draws):
                vals = []
                for ev in period_events:
                    if name == "own_ticker_window":
                        v = draw_own_ticker_control(ev, calendars, eligible_by_ticker, rng)
                    else:
                        v = draw_cross_ticker_control(ev, usable_tickers, calendars, eligible_by_ticker, rng)
                    if v is not None:
                        vals.append(v)
                if vals:
                    draws.append(float(np.mean(vals)))
            control_draws[name] = draws
            if draws:
                print(f"  control[{name}]: n_draws={len(draws)} mean={np.mean(draws):.4%} "
                      f"max={max(draws):.4%}")
            else:
                print(f"  control[{name}]: n_draws=0 (無法抽出任何draw)")

        control_draws = {k: v for k, v in control_draws.items() if len(v) >= 20}
        if len(control_draws) < 2:
            print(f"  {period}: 控制組變體不足2個(有效抽樣數<20)，無法判定")
            results[period] = {"passes": False, "reason": "insufficient_control_variants",
                                "n_events": n_ev, "signal_stat": signal_stat}
            continue

        verdict = evaluate_vs_control(
            signal_stat=signal_stat,
            control_draws=control_draws,
            selection_spec=(
                f"事前綁定：#51-US S&P Addition 公告日→生效日CAR搶跑漲幅，"
                f"僅Addition（排除Deletion避開下市股價格污染），{period}期mean(CAR)，"
                f"控制組own_ticker_window/cross_ticker_window兩變體各N={args.n_draws}，"
                "見sp500_addition_runup_gate51us.py模組docstring事前綁定第1-6點，非事後選點"
            ),
        )
        print(f"  PASSES cheap gate: {verdict.passed}")
        print(f"  {verdict.reason}")
        results[period] = {
            "passes": verdict.passed, "reason": verdict.reason, "n_events": n_ev,
            "signal_stat": signal_stat, "control_max": verdict.control_max,
            "control_mean": verdict.control_mean, "control_percentile": verdict.control_percentile,
            "n_variants": verdict.n_variants, "n_draws_total": verdict.n_draws_total,
        }

    out = {
        "n_events_total": len(events_df), "n_events_usable": len(rows),
        "n_tickers_with_price": len(calendars), "skip_summary": skip_summary,
        "results": results,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n結果已寫入 {RESULT_PATH}")
    return out


if __name__ == "__main__":
    main()
