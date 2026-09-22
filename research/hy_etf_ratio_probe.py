# -*- coding: utf-8 -*-
"""#78 HYG/IEF價格比值代理信用利差regime訊號——資料源歷史起點探測
（七之三第10關）。

零判定、零相關性計算，只確認yfinance `HYG`（iShares iBoxx高收益公司債
ETF）與`IEF`（iShares 7-10年期公債ETF）兩檔的實際歷史起點與涵蓋範圍
是否早於train/val邊界（TRAIN_END=2020-12-31），若任一檔起點晚於邊界則
直接判「只能前向觀察」，不得跳過此步驟直接假設可行
（`HYPOTHESIS_QUEUE.md` #78條目事前明訂）。

只讀yfinance公開端點，不觸碰holdout（不做任何判定運算，只印統計摘要）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TICKERS = ["HYG", "IEF"]
TRAIN_END = "2020-12-31"
VAL_END = "2024-12-31"


def probe(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="max", auto_adjust=False)
        if df is None or df.empty:
            return {"ticker": ticker, "ok": False, "reason": "empty_history"}
        df = df[["Close"]].dropna().reset_index()
        df.rename(columns={"Date": "date", "Close": "close"}, inplace=True)
        # yfinance回傳含時區的Timestamp，統一轉naive方便跟邊界比對
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.sort_values("date").reset_index(drop=True)
        if df.empty:
            return {"ticker": ticker, "ok": False, "reason": "all_values_missing_after_dropna"}

        first_date = str(df["date"].min().date())
        last_date = str(df["date"].max().date())
        n_before_train_end = int((df["date"] <= pd.Timestamp(TRAIN_END)).sum())
        n_train_to_val = int(
            ((df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))).sum()
        )
        starts_before_train_end = df["date"].min() <= pd.Timestamp(TRAIN_END)

        return {
            "ticker": ticker,
            "ok": True,
            "first_date": first_date,
            "last_date": last_date,
            "n_rows_total": int(len(df)),
            "n_rows_train_period": n_before_train_end,
            "n_rows_val_period": n_train_to_val,
            "starts_before_train_end": bool(starts_before_train_end),
        }
    except Exception as e:
        return {"ticker": ticker, "ok": False, "reason": f"exception:{type(e).__name__}:{e}"}


def main():
    series_results = {tk: probe(tk) for tk in TICKERS}

    all_ok = all(r.get("ok") for r in series_results.values())
    all_start_before = all_ok and all(
        r.get("starts_before_train_end") for r in series_results.values()
    )

    result = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "train_end_boundary": TRAIN_END,
        "val_end_boundary": VAL_END,
        "series": series_results,
        "gate7of10_verdict": (
            "PASS_雙腿起點皆早於TRAIN_END可開發完整SPEC"
            if all_start_before
            else "FAIL_至少一腿只能前向觀察或資料不可及"
        ),
    }

    out_path = Path(__file__).parent / "hy_etf_ratio_probe_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
