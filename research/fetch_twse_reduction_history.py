# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 017（2026-10-22）：上市減資恢復買賣參考價 2007～2014（V1 時點宇宙還原用）。

來源：TWSE `www.twse.com.tw/rwd/zh/reducation/TWTAUU?startDate&endDate&response=json`（可查區間；每日管線
`.github/scripts/update_price_history.py` 已用同一端點，C:\\alpha\\CLAUDE.md 頻率清單已登記；官方未公布上限）。
一次手動跑：2007～2014 每年上下半年各 1 次＝16 次請求，共用 data/rate_limit_state.json 來源名 `twse_reduction`
（與每日管線同名＝同一份節流：同源 ≥3 秒、402/403/428/429 封鎖 2 小時不重試），已抓的半年存本機不重抓；資料不進公開 repo。
係數＝恢復買賣參考價 ÷ 停止買賣前收盤價（與 adjust.py 對 TaiwanStockCapitalReductionReferencePrice、每日管線同一式）。
上櫃沒有對應的官方減資參考價表（2026-09-30 查 TPEx swagger 225 個端點），不在這支。

跑法：cd research && python fetch_twse_reduction_history.py
輸出：research/data/twse_reduction_2007_2014.csv（date＝恢復買賣日, stock_id, pre_close, ref_price, factor, reason）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

SRC = "twse_reduction"
URL = "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU"
RAW = HERE / "data" / "raw" / "twse_twtauu"
OUT = HERE / "data" / "twse_reduction_2007_2014.csv"
BLOCK = {402, 403, 428, 429}
YEARS = range(2007, 2015)


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def _roc(s: str) -> str | None:
    m = re.match(r"^\s*(\d{2,3})/(\d{1,2})/(\d{1,2})\s*$", str(s))
    return f"{int(m.group(1)) + 1911:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def parse(js: dict) -> list[tuple]:
    fl = js.get("fields") or []
    idx = lambda want: next((i for i, f in enumerate(fl) if want in f), None)  # noqa: E731
    i_d, i_c, i_pre, i_ref, i_why = idx("恢復買賣日期"), idx("股票代號"), idx("停止買賣前收盤價"), idx("恢復買賣參考價"), idx("減資原因")
    if None in (i_d, i_c, i_pre, i_ref):
        return []
    out = []
    for row in js.get("data") or []:
        d, code = _roc(row[i_d]), str(row[i_c]).strip()
        pre, ref = _num(row[i_pre]), _num(row[i_ref])
        if d and code and pre and ref and pre > 0 and ref > 0:
            out.append((d, code, pre, ref, ref / pre, row[i_why] if i_why is not None else ""))
    return out


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    n_req = 0
    for y in YEARS:
        for half, (a, b) in enumerate(((f"{y}0101", f"{y}0630"), (f"{y}0701", f"{y}1231"))):
            f = RAW / f"{y}_{half + 1}.json"
            if f.exists():
                continue
            _rate_limit_wait_or_raise(SRC)
            r = requests.get(URL, params={"startDate": a, "endDate": b, "response": "json"}, timeout=60,
                             headers={"User-Agent": "Mozilla/5.0"})
            n_req += 1
            if r.status_code in BLOCK:
                _rate_limit_record_block(SRC, r.status_code, "TWTAUU")
                print(f"HTTP {r.status_code}，封鎖 2 小時，停止", flush=True)
                return 1
            try:
                js = r.json()
            except ValueError:
                print(f"{y} H{half + 1} 回傳不是 JSON（HTTP {r.status_code}），停止、不寫快取", flush=True)
                return 1
            f.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
            print(f"{y} H{half + 1}: stat={js.get('stat')} {len(js.get('data') or [])} 列", flush=True)
    rows = []
    for f in sorted(RAW.glob("*.json")):
        rows += parse(json.loads(f.read_text(encoding="utf-8")))
    df = pd.DataFrame(rows, columns=["date", "stock_id", "pre_close", "ref_price", "factor", "reason"])
    df = df.drop_duplicates(["date", "stock_id"]).sort_values(["date", "stock_id"])
    df.to_csv(OUT, index=False)
    by_year = df.groupby(df["date"].str[:4]).size().to_dict() if len(df) else {}
    print(f"請求 {n_req} 次；{len(df)} 筆；各年 {by_year} → {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
