# -*- coding: utf-8 -*-
"""#76 VIX期限結構regime訊號——資料源歷史起點探測（七之三第10關）。

零判定、零IC，只確認 ^VIX / ^VIX9D 兩個yfinance ticker的歷史起點是否早於
train/val邊界（TRAIN_END），若起點晚於邊界則直接判「只能前向觀察」。

只讀公開yfinance資料，不碰holdout（VAL_END之後不下載）。
"""
import json
import sys
from datetime import datetime, timezone

import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VAL_END = "2024-12-31"  # 既有框架的holdout邊界，不下載此日之後的資料


def probe(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(start="1990-01-01", end=VAL_END, auto_adjust=False)
        if hist.empty:
            return {"ticker": ticker, "ok": False, "reason": "empty_history"}
        first_date = str(hist.index.min().date())
        last_date = str(hist.index.max().date())
        n_rows = int(len(hist))
        return {
            "ticker": ticker,
            "ok": True,
            "first_date": first_date,
            "last_date": last_date,
            "n_rows": n_rows,
        }
    except Exception as e:
        return {"ticker": ticker, "ok": False, "reason": f"exception:{type(e).__name__}:{e}"}


def main():
    result = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "val_end_boundary": VAL_END,
        "tickers": {},
    }
    for tk in ["^VIX", "^VIX9D"]:
        result["tickers"][tk] = probe(tk)

    out_path = "vix_term_structure_probe_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
