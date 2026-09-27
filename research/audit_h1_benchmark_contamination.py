# -*- coding: utf-8 -*-
"""驗.五（2026-09-27總司令裁示【驗.五＋修.六：H.一基準汙染診斷】）：
只做診斷，不是重跑。#400判定鎖定FAIL，本檔案任何輸出都不得改變判定。

背景：0050於2025-06以1拆4分割，`adjust.py`的FinMind還原路徑（以及
`holdout_2025_dividend_account_test.py`逐字複製的`_uncapped_adjustment_
events()`）目前只處理現金股利/股票股利/現金增資，**沒有處理分割**，
導致0050 uncapped adj_close在2025-06-18出現約-75%的假跌（收盤價從
188.65直接變成47.57，未經任何分割因子調整）。這筆假跌會直接汙染
`alpha_significance()`用來算判準(a) IR的0050基準報酬序列。

跑法：python research/audit_h1_benchmark_contamination.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json

import numpy as np
import pandas as pd

import holdout_2025_dividend_account_test as h1
import portfolio_backtest_v2 as pbv2
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from universe import classify_security
from finmind_client import load_full_history, load_dev
from adjust import adjusted_price_series

ANOMALY_THRESHOLD_PCT = 11.0
MIN_TRADING_DAYS_AFTER_LISTING = 5

OUT_PATH = Path(__file__).parent / "data" / "h1_benchmark_contamination_diagnosis.json"


def _scan_anomalies(px: pd.DataFrame, label: str) -> list[dict]:
    """對一檔股票的uncapped adj_close序列掃單日|報酬|>11%，排除上市前
    MIN_TRADING_DAYS_AFTER_LISTING個交易日。回傳每一筆異常的明細
    （不含分類——分類在呼叫端做，因為需要交叉比對FinMind事件資料集）。
    """
    if px.empty or "adj_close" not in px.columns or len(px) <= MIN_TRADING_DAYS_AFTER_LISTING:
        return []
    d = px.sort_values("date").reset_index(drop=True)
    d["ret_pct"] = d["adj_close"].pct_change() * 100
    out = []
    for i in range(MIN_TRADING_DAYS_AFTER_LISTING, len(d)):
        r = d.loc[i, "ret_pct"]
        if pd.notna(r) and abs(r) > ANOMALY_THRESHOLD_PCT:
            out.append({
                "label": label, "date": str(d.loc[i, "date"]), "ret_pct": round(float(r), 2),
                "prev_date": str(d.loc[i - 1, "date"]),
                "prev_close": float(d.loc[i - 1, "close"]), "close": float(d.loc[i, "close"]),
                "prev_adj_close": float(d.loc[i - 1, "adj_close"]), "adj_close": float(d.loc[i, "adj_close"]),
            })
    return out


def _classify_anomaly(stock_id: str, hit: dict) -> dict:
    """交叉比對FinMind的分割/減資/面額變更相關資料集，判斷這筆異常的
    可能歸類。修.六之前這裡先用現有可及的資料源嘗試判斷，判斷不出來的
    誠實標「其他/待查」，不猜測。"""
    date = hit["date"]
    ratio = hit["close"] / hit["prev_close"] if hit["prev_close"] else None
    evidence = {}
    category = "其他/待查"

    # 先用最直接的證據：價格比值是否接近常見分割比例的倒數（1:2, 1:4, 1:5, 1:10）
    if ratio is not None:
        for split_n in (2, 4, 5, 10):
            if abs(ratio - 1.0 / split_n) < 0.05:
                category = f"疑似分割(1拆{split_n})"
                evidence["price_ratio"] = round(ratio, 4)
                evidence["expected_ratio_if_split"] = round(1.0 / split_n, 4)
                break
        else:
            if ratio < 0.85:
                category = "疑似減資或其他大幅價格調整"
                evidence["price_ratio"] = round(ratio, 4)

    hit["category"] = category
    hit["evidence"] = evidence
    return hit


def main() -> None:
    print("=" * 78, flush=True)
    print("驗.五：H.一基準汙染診斷（只做診斷，不改變#400/#399判定）", flush=True)
    print("=" * 78, flush=True)

    result: dict = {"generated_at": pd.Timestamp.now().isoformat()}

    # ── 一：0050在2025-06-05~06-25的逐日價格與日報酬 ──
    print("\n=== 一：0050 uncapped 2025-06-05~06-25 逐日價格與日報酬 ===", flush=True)
    px_0050 = h1.uncapped_adjusted_price_series("0050", "2003-01-01")
    window = px_0050[(px_0050["date"] >= "2025-06-05") & (px_0050["date"] <= "2025-06-25")].sort_values("date").copy()
    window["ret_close_pct"] = window["close"].pct_change() * 100
    window["ret_adj_close_pct"] = window["adj_close"].pct_change() * 100
    rows_0050_window = window[["date", "close", "adj_close", "ret_close_pct", "ret_adj_close_pct"]].to_dict("records")
    for r in rows_0050_window:
        print(f"  {r['date']}  close={r['close']:.2f}  adj_close={r['adj_close']:.2f}  "
              f"ret_close%={r['ret_close_pct']}  ret_adj_close%={r['ret_adj_close_pct']}", flush=True)
    confirmed_fake_drop = any(
        r["date"] == "2025-06-18" and r["ret_adj_close_pct"] is not None and r["ret_adj_close_pct"] < -70
        for r in rows_0050_window
    )
    print(f"  結論：2025-06-18 假跌{'確認存在' if confirmed_fake_drop else '未觀察到（需人工複核）'}"
          f"（0050於2025-06以1拆4分割，6/10為分割前最後交易日，6/18恢復交易）", flush=True)
    result["item1_0050_window"] = {"rows": rows_0050_window, "confirmed_fake_drop_2025_06_18": confirmed_fake_drop}

    # ── 二：holdout期間0050+214檔可用股票的漲跌幅合理性掃描 ──
    print("\n=== 二：holdout期間漲跌幅合理性掃描（單日|報酬|>11%）===", flush=True)
    anomalies_0050 = [_classify_anomaly("0050", h) for h in _scan_anomalies(
        px_0050[px_0050["date"] >= h1.LOOKBACK_START], "0050")]
    print(f"  0050：{len(anomalies_0050)}筆", flush=True)
    for a in anomalies_0050:
        print(f"    {a['date']}  {a['prev_close']:.2f}->{a['close']:.2f}  "
              f"ret={a['ret_pct']}%  歸類={a['category']}  證據={a['evidence']}", flush=True)

    # 重建214檔可用股票清單：跟holdout_2025_dividend_account_test.py::main()
    # 第3步完全相同的篩選邏輯（sample_ids -> common_stock分類 -> uncapped
    # px非空且>=200列 -> 截斷至H1_PERIOD_END -> 再次>=200列），但只載入
    # 價格，不算因子（本次只需要價格序列做漲跌幅掃描，零額外新API呼叫，
    # 全部走cache）。
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    info_lookup = h1._info_lookup()
    common_ids = [sid for sid in sample_ids
                  if classify_security(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                        (info_lookup.get(sid) or {}).get("industry_category")) == "普通股"]
    usable_ids = []
    for sid in common_ids:
        px = h1.uncapped_adjusted_price_series(sid, h1.LOOKBACK_START)
        if px.empty or len(px) < 200:
            continue
        px = px[px["date"] <= h1.H1_PERIOD_END].reset_index(drop=True)
        if px.empty or len(px) < 200:
            continue
        usable_ids.append(sid)
    print(f"  重建可用股票清單：{len(usable_ids)}檔（H.一實際執行為214檔，供交叉核對）", flush=True)

    anomalies_stocks: list[dict] = []
    for sid in usable_ids:
        px = h1.uncapped_adjusted_price_series(sid, h1.LOOKBACK_START)
        px = px[px["date"] <= h1.H1_PERIOD_END].reset_index(drop=True)
        hits = _scan_anomalies(px, sid)
        for h in hits:
            anomalies_stocks.append(_classify_anomaly(sid, h))
    print(f"  214檔可用股票：共{len(anomalies_stocks)}筆異常", flush=True)
    for a in anomalies_stocks:
        print(f"    {a['label']} {a['date']}  {a['prev_close']:.2f}->{a['close']:.2f}  "
              f"ret={a['ret_pct']}%  歸類={a['category']}  證據={a['evidence']}", flush=True)

    result["item2_holdout_period_scan"] = {
        "usable_stock_count": len(usable_ids),
        "anomalies_0050": anomalies_0050,
        "anomalies_stocks": anomalies_stocks,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
