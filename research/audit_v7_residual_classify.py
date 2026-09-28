# -*- coding: utf-8 -*-
"""驗.七第二點：驗.六殘留的699筆異常（2007-2014還原價、日期相依門檻）
逐筆分類（2026-09-29總司令裁示【驗.七】二）。**只回報，不修**。

分類（互斥，依下列優先序判定，先命中先歸類）：
  (a) 上市日未知的已下市股（查.三核對出的33檔：查無官方上市/上櫃日 且
      在`universe.delisted_stock_ids()`名單內）
  (d) 上市後5個交易日內（上市日已知，異常日落在該股票序列中「上市日起算
      第1~5個交易日」）——排在(b)/(c)之前，因為這是已知的資料現象類別，
      跟走哪條價格路徑無關
  (b) yfinance路徑（`adjusted_price_series()`回傳`source=='yfinance'`）
  (c) FinMind路徑（`source=='finmind'`，即adjust.py手動還原）
  (e) 其他（上述都不是，例如source欄位缺失）

(b)類抽5筆（固定種子`random.Random(20260929)`，可重現）對照：
  - 原始價(close)當日報酬 vs 還原價(adj_close)當日報酬
  - `TaiwanStockDividendResult`該股票該日期有沒有除權息紀錄；有的話取
    官方`reference_price/before_price`比例當基準
  判斷規則（事前寫死）：
  - 官方有除權息紀錄：|adj_ret − (official_ratio−1)×100| < 0.6pp → yfinance
    還原與官方一致→「真實漲跌(除權息日，還原正確)」；否則→「yfinance自身
    還原錯誤（與官方參考價不符）」
  - 官方無除權息紀錄：|raw_ret − adj_ret| < 0.6pp → 原始價本身就大幅變動
    →「真實漲跌」；否則→「yfinance自身還原錯誤（非除權息日卻被調整）」
  每筆附證據數字，判斷不出來的如實標「無法判定」。

輸出：research/data/diag_v7_residual_classification.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
import random
import time
from pathlib import Path

import pandas as pd
import requests

import audit_v6_anomaly_rescan as v6
import adjust as adjust_current
from universe import listing_date_lookup, delisted_stock_ids

OUT = Path(__file__).parent / "data" / "diag_v7_residual_classification.json"
LO, HI = "2007-01-01", "2014-12-31"
SAMPLE_SEED = 20260929


def _fetch_result_rows(sid: str) -> list[dict]:
    r = requests.get("https://api.finmindtrade.com/api/v4/data", params={
        "dataset": "TaiwanStockDividendResult", "data_id": sid, "start_date": "2000-01-01"}, timeout=40)
    j = r.json()
    if j.get("status") not in (200, "200") and j.get("msg") != "success":
        raise RuntimeError(f"FinMind回應非成功（{j.get('status')} {j.get('msg')}），依裁示五中止不吞錯")
    return j.get("data", [])


def main() -> None:
    sample = v6._build_sample()
    print(f"[驗.七項二] 樣本{len(sample)}檔，重掃2007-2014還原價（日期相依門檻）...", flush=True)
    hits = v6._scan(adjust_current, sample, LO, HI, "adj_close")
    print(f"  命中{len(hits)}筆（驗.六為699筆，應相同或極接近）", flush=True)

    lookup = listing_date_lookup()
    delisted = set(delisted_stock_ids()["stock_id"].astype(str))
    unknown_delisted_33 = {s for s in sample if s not in lookup and s in delisted}
    print(f"  上市日未知且已下市：{len(unknown_delisted_33)}檔（查.三核對值33）", flush=True)

    # 每檔只載一次：source、以及上市後前5個交易日的日期集合、以及close/adj_close序列
    per_stock: dict[str, dict] = {}
    for sid in {h["stock_id"] for h in hits}:
        try:
            px = adjust_current.adjusted_price_series(sid, "2003-01-01")
        except Exception:  # noqa: BLE001
            per_stock[sid] = {"source": None, "first5": set(), "px": None}
            continue
        src = px["source"].iloc[0] if ("source" in px.columns and len(px)) else None
        first5 = set()
        ld = lookup.get(sid)
        if ld is not None:
            after = px[px["date"].astype(str) >= ld].sort_values("date")
            first5 = set(after["date"].astype(str).head(5))
        per_stock[sid] = {"source": src, "first5": first5, "px": px}

    counts = {"(a)上市日未知已下市股": 0, "(b)yfinance路徑": 0, "(c)FinMind路徑": 0,
              "(d)上市後5日內": 0, "(e)其他": 0}
    classified = []
    for h in hits:
        sid = h["stock_id"]
        meta = per_stock[sid]
        if sid in unknown_delisted_33:
            cat = "(a)上市日未知已下市股"
        elif h["date"] in meta["first5"]:
            cat = "(d)上市後5日內"
        elif meta["source"] == "yfinance":
            cat = "(b)yfinance路徑"
        elif meta["source"] == "finmind":
            cat = "(c)FinMind路徑"
        else:
            cat = "(e)其他"
        counts[cat] += 1
        classified.append({**h, "category": cat, "source": meta["source"]})
    print("  分類：", counts, flush=True)

    # (b)類抽5筆對照官方參考價
    b_hits = [c for c in classified if c["category"] == "(b)yfinance路徑"]
    rng = random.Random(SAMPLE_SEED)
    picked = rng.sample(b_hits, min(5, len(b_hits)))
    checks = []
    for c in picked:
        sid, date = c["stock_id"], c["date"]
        px = per_stock[sid]["px"]
        d = px.sort_values("date").reset_index(drop=True)
        d["date"] = d["date"].astype(str)
        i = d.index[d["date"] == date]
        entry = {"stock_id": sid, "date": date, "adj_ret_pct": c["ret_pct"]}
        if len(i) == 0 or i[0] == 0:
            entry["judgement"] = "無法判定（序列裡找不到該日或無前一日）"
            checks.append(entry)
            continue
        i = int(i[0])
        raw_ret = (d.loc[i, "close"] / d.loc[i - 1, "close"] - 1) * 100 if d.loc[i - 1, "close"] else None
        entry["raw_ret_pct"] = round(float(raw_ret), 2) if raw_ret is not None else None
        entry["raw_close_prev"], entry["raw_close"] = float(d.loc[i - 1, "close"]), float(d.loc[i, "close"])
        time.sleep(0.3)
        rows = _fetch_result_rows(sid)
        res = next((r for r in rows if r.get("date") == date), None)
        if res and res.get("before_price") and (res.get("reference_price") or res.get("after_price")):
            ratio = (res.get("reference_price") or res.get("after_price")) / res["before_price"]
            entry["official_reference_ratio"] = round(ratio, 6)
            entry["official_implied_ret_pct"] = round((ratio - 1) * 100, 2)
            diff = abs(c["ret_pct"] - (ratio - 1) * 100)
            entry["judgement"] = ("真實漲跌（除權息日，yfinance還原與官方參考價一致）" if diff < 0.6
                                  else f"yfinance自身還原錯誤（與官方參考價差{diff:.2f}pp）")
        else:
            entry["official_reference_ratio"] = None
            if raw_ret is None:
                entry["judgement"] = "無法判定（無原始價）"
            elif abs(raw_ret - c["ret_pct"]) < 0.6:
                entry["judgement"] = "真實漲跌（非除權息日，原始價本身就大幅變動，還原未改變它）"
            else:
                entry["judgement"] = (f"yfinance自身還原錯誤（非除權息日卻被調整：原始價{raw_ret:+.2f}% "
                                      f"vs 還原價{c['ret_pct']:+.2f}%）")
        checks.append(entry)
        print(f"  抽查 {sid} {date}: {entry['judgement']}", flush=True)

    OUT.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "note": "驗.七項二，只回報不修；分類優先序見腳本docstring",
        "n_hits": len(hits), "n_unknown_delisted_33": len(unknown_delisted_33),
        "counts": counts, "b_class_spot_checks": checks, "hits": classified,
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"已寫入 {OUT}")


if __name__ == "__main__":
    main()
