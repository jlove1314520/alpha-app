# -*- coding: utf-8 -*-
"""先.九十四-1b：抓證交所官方「臺灣50指數歷史資料」（臺灣50指數＋臺灣50報酬指數，每日收盤），
供 core_tilt 量尺診斷區分「0050 市價自身的日間雜訊」與「重建方法的誤差」。不改主判定（仍對 0050 含息）。

端點：https://www.twse.com.tw/rwd/zh/FTSE/TAI50I?date=YYYYMM01&response=json（一次回一個月）
官方未公布次數上限；與 data/rate_limit_state.json 共用節流（來源名 twse_rwd，同源間隔 ≥3 秒，
402/403/428/429 即封鎖 2 小時不重試）。已抓過的月份存在 research/data/raw/twse_tai50i/，不重抓。
只抓到 VAL_END（2024-12），不碰 holdout。輸出 research/data/tai50_index_daily.csv。
用法：python research/fetch_tai50_index.py [--start 2013-01]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

SRC = "twse_rwd"
URL = "https://www.twse.com.tw/rwd/zh/FTSE/TAI50I"
RAW = HERE / "data" / "raw" / "twse_tai50i"
OUT = HERE / "data" / "tai50_index_daily.csv"
BLOCK = {402, 403, 428, 429}


def _roc(s: str) -> str:
    y, m, d = s.split("/")
    return f"{int(y) + 1911}-{int(m):02d}-{int(d):02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2013-01")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    months = pd.period_range(a.start, VAL_END[:7], freq="M")
    n_req = 0
    for p in months:
        f = RAW / f"{p.strftime('%Y%m')}.json"
        if f.exists():
            continue
        _rate_limit_wait_or_raise(SRC)
        r = requests.get(URL, params={"date": p.strftime("%Y%m01"), "response": "json"}, timeout=30,
                         headers={"User-Agent": "Mozilla/5.0"})
        n_req += 1
        if r.status_code in BLOCK:
            _rate_limit_record_block(SRC, r.status_code, "TAI50I")
            print(f"HTTP {r.status_code}，封鎖 2 小時，停止", flush=True)
            break
        try:
            js = r.json()
        except ValueError:
            print(f"{p} 回傳不是 JSON（軟性限流？），停止", flush=True)
            break
        if js.get("stat") != "OK":
            print(f"{p} stat={js.get('stat')}，略過", flush=True)
            continue
        f.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
    rows = []
    for f in sorted(RAW.glob("*.json")):
        js = json.loads(f.read_text(encoding="utf-8"))
        for d, px, tr in js.get("data", []):
            dd = _roc(d)
            if dd <= VAL_END:
                rows.append((dd, float(px.replace(",", "")), float(tr.replace(",", ""))))
    df = pd.DataFrame(rows, columns=["date", "tai50", "tai50_tr"]).drop_duplicates("date").sort_values("date")
    df.to_csv(OUT, index=False)
    print(f"請求 {n_req} 次；{len(df)} 天（{df['date'].iloc[0]}～{df['date'].iloc[-1]}）→ {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
