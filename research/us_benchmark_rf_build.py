# -*- coding: utf-8 -*-
"""先.十八-三：美股基準（SPY 還原價）與無風險利率（3M T-bill）快取建置。

總司令 2026-10-05【先.十八】三：
  SPY 改走 yfinance Adj Close 建快取，**不得再用 FinMind USStockPrice**；
  3M T-bill 用 fred_yield_curve_gate.fetch_fred_series('DTB3')。

為什麼要改：既有 `deep_dive_f_us_low_vol.py::_load_market_df()` 走
`load_dev("USStockPrice","SPY",...)`＝FinMind（台灣資料商），牴觸 CLAUDE.md 七之三
「美股…禁止用台灣資料商作為美股宇宙或價格的主來源」。本腳本建立的快取是
美股原生源，供美股供給緊縮命題（先.十七）使用。

**只建資料，不計任何報酬。** 輸出：
  research/data/us_benchmark_spy.parquet（date, open, high, low, close, adj_close, volume）
  research/data/us_rf_dtb3.parquet（date, dtb3_pct, dtb3_daily）
  research/data/us_benchmark_rf_status.json（覆蓋率與自我檢查，供稽核）

holdout 注意：本腳本抓的是**基準與利率**，不是個股價格，且抓到當日；
任何回測在使用時仍須自行把區間截到該試驗允許的結束日。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPY_OUT = HERE / "data" / "us_benchmark_spy.parquet"
RF_OUT = HERE / "data" / "us_rf_dtb3.parquet"
STATUS = HERE / "data" / "us_benchmark_rf_status.json"
START = "2009-01-01"


def build_spy() -> dict:
    import yfinance as yf
    t = yf.Ticker("SPY")
    # auto_adjust=False 才會同時給 Close 與 Adj Close；要的是含息還原的 Adj Close
    df = t.history(start=START, auto_adjust=False, actions=True)
    if df is None or df.empty:
        return {"ok": False, "error": "yfinance 回傳空表"}
    df = df.reset_index()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    date_col = "date" if "date" in df.columns else df.columns[0]
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col]).dt.tz_localize(None).dt.normalize(),
        "open": df["open"].astype(float), "high": df["high"].astype(float),
        "low": df["low"].astype(float), "close": df["close"].astype(float),
        "adj_close": df["adj_close"].astype(float),
        "volume": df["volume"].astype("int64"),
    }).dropna(subset=["adj_close"]).sort_values("date").reset_index(drop=True)
    out.to_parquet(SPY_OUT, index=False)
    # 自我檢查：還原價與未還原價的總報酬差＝累積配息效果，必須為正且量級合理
    tr_adj = float(out["adj_close"].iloc[-1] / out["adj_close"].iloc[0] - 1)
    tr_raw = float(out["close"].iloc[-1] / out["close"].iloc[0] - 1)
    return {"ok": True, "source": "yfinance SPY（美股原生源；auto_adjust=False 取 Adj Close）",
            "n_rows": len(out), "start": str(out["date"].iloc[0].date()),
            "end": str(out["date"].iloc[-1].date()),
            "total_return_adj_close": round(tr_adj, 4),
            "total_return_close_unadjusted": round(tr_raw, 4),
            "dividend_effect_pp": round((tr_adj - tr_raw) * 100, 1),
            "sanity_adj_ge_close": bool(tr_adj > tr_raw),
            "path": str(SPY_OUT.relative_to(HERE.parent))}


def build_rf() -> dict:
    from fred_yield_curve_gate import fetch_fred_series
    df = fetch_fred_series("DTB3", START)
    if df is None or df.empty:
        return {"ok": False, "error": "FRED DTB3 回傳空表"}
    d = pd.DataFrame({"date": pd.to_datetime(df["date"]).dt.normalize(),
                      "dtb3_pct": df["value"].astype(float)}).dropna().sort_values("date")
    # 年化百分比 → 每日簡單利率（252 交易日），供回測扣無風險或算 Sharpe 用
    d["dtb3_daily"] = d["dtb3_pct"] / 100.0 / 252.0
    d = d.reset_index(drop=True)
    d.to_parquet(RF_OUT, index=False)
    return {"ok": True, "source": "FRED DTB3（3-Month Treasury Bill Secondary Market Rate, Discount Basis）"
                                  "，經 research/fred_yield_curve_gate.fetch_fred_series()",
            "n_rows": len(d), "start": str(d["date"].iloc[0].date()),
            "end": str(d["date"].iloc[-1].date()),
            "min_pct": round(float(d["dtb3_pct"].min()), 3),
            "max_pct": round(float(d["dtb3_pct"].max()), 3),
            "latest_pct": round(float(d["dtb3_pct"].iloc[-1]), 3),
            "daily_conv": "dtb3_daily = dtb3_pct/100/252",
            "path": str(RF_OUT.relative_to(HERE.parent))}


def main() -> int:
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "ruling": "先.十八-三",
           "note": "只建資料，不計任何報酬；SPY 一律走美股原生源，禁用 FinMind USStockPrice（CLAUDE.md 七之三）"}
    print("=== SPY（yfinance Adj Close）===", flush=True)
    res["spy"] = build_spy()
    print(json.dumps(res["spy"], ensure_ascii=False), flush=True)
    print("=== 3M T-bill（FRED DTB3）===", flush=True)
    try:
        res["rf_dtb3"] = build_rf()
    except Exception as e:  # noqa: BLE001
        res["rf_dtb3"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(res["rf_dtb3"], ensure_ascii=False), flush=True)
    STATUS.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {STATUS}", flush=True)
    return 0 if res["spy"].get("ok") and res["rf_dtb3"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
