# -*- coding: utf-8 -*-
"""先.九十四-1b①：抓證交所官方「除權除息計算結果表」（TWT49U）2013～2024 逐年，
供 core_tilt 量尺診斷核對「重建組合是否少算股息」（FinMind 對部分成分股沒有任何除權息列）。

端點：https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json
（CLAUDE.md「除權除息計算結果（歷史區間）」已登記；官方未公布上限）。與 data/rate_limit_state.json 共用節流
（來源名 twse_exright，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。只抓到 VAL_END，不碰 holdout。
係數＝除權息參考價 ÷ 除權息前收盤價。輸出 research/data/twse_exright_2013_2024.csv。
"""
from __future__ import annotations

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

SRC = "twse_exright"
URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
RAW = HERE / "data" / "raw" / "twse_twt49u"
OUT = HERE / "data" / "twse_exright_2013_2024.csv"
BLOCK = {402, 403, 428, 429}


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def _roc(s: str) -> str:
    s = s.replace("年", "/").replace("月", "/").replace("日", "").strip()
    y, m, d = [int(x) for x in s.split("/")]
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    n_req = 0
    for y in range(2013, int(VAL_END[:4]) + 1):
        for half, (a, b) in enumerate(((f"{y}0101", f"{y}0630"), (f"{y}0701", f"{y}1231"))):
            f = RAW / f"{y}_{half + 1}.json"
            if f.exists():
                continue
            _rate_limit_wait_or_raise(SRC)
            r = requests.get(URL, params={"startDate": a, "endDate": b, "response": "json"}, timeout=60,
                             headers={"User-Agent": "Mozilla/5.0"})
            n_req += 1
            if r.status_code in BLOCK:
                _rate_limit_record_block(SRC, r.status_code, "TWT49U")
                print(f"HTTP {r.status_code}，封鎖 2 小時，停止", flush=True)
                return 1
            try:
                js = r.json()
            except ValueError:
                print(f"{y} H{half + 1} 回傳不是 JSON，停止", flush=True)
                return 1
            f.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
            print(f"{y} H{half + 1}: {len(js.get('data') or [])} 列", flush=True)
    rows = []
    for f in sorted(RAW.glob("*.json")):
        js = json.loads(f.read_text(encoding="utf-8"))
        fl = js.get("fields") or []
        if not fl:
            continue
        i_d, i_c, i_pc, i_ref = fl.index("資料日期"), fl.index("股票代號"), fl.index("除權息前收盤價"), fl.index("除權息參考價")
        i_k = fl.index("權/息") if "權/息" in fl else None
        for row in js.get("data") or []:
            pc, ref = _num(row[i_pc]), _num(row[i_ref])
            if pc and ref:
                rows.append((_roc(row[i_d]), str(row[i_c]).strip(), pc, ref, ref / pc, row[i_k] if i_k is not None else ""))
    df = pd.DataFrame(rows, columns=["date", "stock_id", "prev_close", "ref_price", "factor", "kind"])
    df = df[df["date"] <= VAL_END].drop_duplicates(["date", "stock_id"]).sort_values(["date", "stock_id"])
    df.to_csv(OUT, index=False)
    print(f"請求 {n_req} 次；{len(df)} 筆（{df['date'].min()}～{df['date'].max()}）→ {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
