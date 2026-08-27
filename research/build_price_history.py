"""一次性（可重複執行、merge-safe）建置/回補 data/price_history.json（2026-08-27）。

背景：`generate_scores_live.py`（P1，JSON-only上線評分路徑）的 `technical`
（技術型態）因子原本完全沒有資料源——需要per股票的每日OHLCV歷史才能算
「站上60日均線 × 20/60日均量比」（跟研究端 `factors.py::prepare_factors()`
的 `f_ma_breakout` 同一個公式，只是這裡用未還原權息的收盤價，是刻意的
簡化，見 `generate_scores_live.py` 檔頭說明）。

跟 `build_fundamentals_json.py`/`build_stock_financials_history.py` 同一個
解法：讀research端已經合法快取的FinMind `TaiwanStockPrice` 本機parquet
（2417檔），一次回補約90個交易日的OHLCV歷史，寫進 `data/price_history.json`，
之後由 `.github/scripts/update_price_history.py` 每日排程（TWSE STOCK_DAY_ALL
+ TPEx tpex_mainboard_quotes，全市場單日快照）累積式append，滾動保留最近
`PRICE_HISTORY_DAYS` 個交易日。

**merge-safe，不是覆寫**（吸取build_fundamentals_json.py重跑時砍掉502檔的
教訓）：只補既有沒有的股票/日期，既有資料不會被覆蓋，股票數只會增加不會
減少，減少就中止不寫檔。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_PATH = Path(__file__).parent.parent / "data" / "price_history.json"
SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "quotes_all_tw.json"
PRICE_HISTORY_DAYS = 90  # MA60需要60個交易日，多留緩衝給20/60日均量比計算


def _codes_from_cache(dataset: str) -> set[str]:
    codes = set()
    for p in RAW_DIR.glob(f"{dataset}__*.parquet"):
        m = re.match(rf"^{dataset}__(.+?)__\d{{4}}-\d{{2}}-\d{{2}}", p.name)
        if m:
            codes.add(m.group(1))
    return codes


def _load_concat(dataset: str, code: str) -> pd.DataFrame:
    frames = []
    for p in RAW_DIR.glob(f"{dataset}__{code}__*.parquet"):
        try:
            df = pd.read_parquet(p)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_price_rows(code: str) -> list[dict]:
    df = _load_concat("TaiwanStockPrice", code)
    if df.empty or "close" not in df.columns:
        return []
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    df = df.tail(PRICE_HISTORY_DAYS)
    out = []
    for _, row in df.iterrows():
        close = row.get("close")
        if pd.isna(close):
            continue
        out.append({
            "date": str(row["date"]),
            "open": float(row["open"]) if pd.notna(row.get("open")) else None,
            "high": float(row["max"]) if pd.notna(row.get("max")) else None,
            "low": float(row["min"]) if pd.notna(row.get("min")) else None,
            "close": float(close),
            "volume": float(row["Trading_Volume"]) if pd.notna(row.get("Trading_Volume")) else None,
            "turnover": float(row["Trading_money"]) if pd.notna(row.get("Trading_money")) else None,
        })
    return out


def merge_rows(existing: list[dict] | None, backfill: list[dict]) -> list[dict]:
    """既有(daily排程，較即時)欄位優先，但2026-08-27改成「欄位級」合併，不是
    整列取代——新增turnover欄位時，既有列缺這個欄位可以從backfill補上，不會
    因為那一天已經有(舊schema、沒有turnover的)紀錄就整列忽略backfill帶來的
    新欄位。"""
    by_date = {r["date"]: dict(r) for r in backfill}
    for r in (existing or []):
        date = r["date"]
        merged = dict(by_date.get(date, {}))
        merged.update(r)  # 既有值優先覆蓋，但backfill獨有的key（如turnover缺漏時）保留
        by_date[date] = merged
    rows = sorted(by_date.values(), key=lambda r: r["date"])
    return rows[-PRICE_HISTORY_DAYS:]


def main():
    codes = _codes_from_cache("TaiwanStockPrice")
    print(f"快取涵蓋：價量 {len(codes)} 檔")

    payload = {"meta": {}, "prices": {}}
    if OUT_PATH.exists():
        try:
            payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    prices = payload.setdefault("prices", {})
    prior_count = len(prices)

    backfilled = 0
    for code in sorted(codes):
        rows = build_price_rows(code)
        if not rows:
            continue
        before_len = len(prices.get(code, []))
        prices[code] = merge_rows(prices.get(code), rows)
        if len(prices[code]) > before_len:
            backfilled += 1

    new_count = len(prices)
    if new_count < prior_count:
        raise RuntimeError(
            f"覆蓋率不應該在merge之後下降，但從 {prior_count} 變成 {new_count}——"
            "已中止寫入，不要用這份結果覆蓋既有檔案。"
        )

    payload.setdefault("meta", {})
    payload["meta"]["backfill_note"] = (
        "2026-08-27一次性回補：讀research端FinMind歷史parquet快取"
        "（TaiwanStockPrice）補上約90個交易日OHLCV歷史，供generate_scores_live.py"
        "的technical因子(站上60日均線×20/60日均量比)使用。收盤價為原始收盤價，"
        "未還原權息（有除權息的股票，MA60在除權息當天附近會有跳空失真，是刻意"
        "的簡化，見generate_scores_live.py檔頭說明）。merge-safe，既有較新資料"
        "不會被覆蓋。"
    )
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{new_count} 檔有資料（merge前既有 {prior_count} 檔，"
          f"{backfilled} 檔補進更多天數歷史）")

    # 跟update_price_history.py同一套輕量快照(見該腳本說明)，這裡也寫一份，
    # 讓B4類股清單功能不需要等下一次daily排程才有資料可用。
    snapshot = {}
    for code, rows in prices.items():
        if not rows:
            continue
        last = rows[-1]
        prev = rows[-2] if len(rows) >= 2 else None
        change_pct = None
        if prev and prev.get("close") not in (None, 0):
            change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100, 2)
        snapshot[code] = {
            "date": last["date"], "close": last["close"],
            "change_pct": change_pct, "turnover": last.get("turnover"),
        }
    from datetime import datetime, timezone, timedelta
    tw_tz = timezone(timedelta(hours=8))
    SNAPSHOT_PATH.write_text(json.dumps({
        "meta": {"generated_at": datetime.now(tw_tz).isoformat(),
                 "note": "從data/price_history.json每檔最後兩筆算出的輕量快照，見"
                         "update_price_history.py同名邏輯說明。"},
        "quotes": snapshot,
    }, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {SNAPSHOT_PATH}：{len(snapshot)} 檔輕量快照")


if __name__ == "__main__":
    main()
