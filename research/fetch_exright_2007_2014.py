# -*- coding: utf-8 -*-
"""補.資料-官方除權息 2007-07～2014 抓取存本機（只抓不套用；來源：先.一三三-1c 發現 FinMind 2009 股利整年 0 筆）。

端點（C:\\alpha\\CLAUDE.md「除權除息計算結果（歷史區間）」已登記；官方未公布上限）：
  上市 TWT49U：https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json
    2007H2～2012H2 每半年 1 次＝11 次（2013 起 research/fetch_twse_exright_history.py 已抓過，直接讀它的快取，不重抓）。
  上櫃 exDailyQ：https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ?startDate=YYYY/MM/DD&endDate=…&response=json
    2007H2～2014H2 每半年 1 次＝15 次。
節流：共用 data/rate_limit_state.json（twse_exright／tpex_www，同源間隔 ≥3 秒、跨行程鎖，402/403/428/429 封鎖 2 小時不重試）。
回應不是 JSON、或找不到預期欄位 → 停抓（不猜格式）。原始回應存 research/data/raw/exright_2007_2014/（不進公開 repo），已抓的不重抓。
產出（零請求、只數事件，不改 adjust.py、不算任何報酬、不碰 holdout）：
  research/data/official_exright_2007_2014.csv   逐筆官方事件（係數＝除權息參考價 ÷ 除權息前收盤價）
  research/data/exright_official_vs_finmind_2007_2014.json   逐年對照：官方事件 vs FinMind TaiwanStockDividend 本機快取同日事件
    FinMind 只讀本機快取（research/data/raw/TaiwanStockDividend__{代號}__*.parquet，涵蓋 2007-07～2014 的那份），零請求；
    除息日取 CashExDividendTradingDate、除權日取 StockExDividendTradingDate（`date` 欄不是除權息日）。
用法：python research/fetch_exright_2007_2014.py [--no-fetch]（--no-fetch 只用已抓快取重算對照表）
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

RAW = HERE / "data" / "raw" / "exright_2007_2014"
TWSE_2013_CACHE = HERE / "data" / "raw" / "twse_twt49u"  # fetch_twse_exright_history.py 的快取
FM_RAW = HERE / "data" / "raw"
OUT_CSV = HERE / "data" / "official_exright_2007_2014.csv"
OUT_JSON = HERE / "data" / "exright_official_vs_finmind_2007_2014.json"
UA = {"User-Agent": "alpha-research/1.0 (personal research; ex-right history)"}
BLOCK = {402, 403, 428, 429}
START, END = "2007-07-01", "2014-12-31"


def _halves(y0: int, h0: int, y1: int):
    for y in range(y0, y1 + 1):
        for h in (1, 2):
            if (y, h) >= (y0, h0):
                yield y, h


def _span(y: int, h: int) -> tuple[str, str]:
    return (f"{y}-01-01", f"{y}-06-30") if h == 1 else (f"{y}-07-01", f"{y}-12-31")


JOBS = ([("twse", y, h) for y, h in _halves(2007, 2, 2012)] + [("tpex", y, h) for y, h in _halves(2007, 2, 2014)])


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def _roc(s) -> str | None:
    try:
        t = "".join(ch for ch in str(s).replace("年", "/").replace("月", "/").replace("日", "") if ch.isdigit() or ch == "/")
        y, m, d = [int(x) for x in t.split("/")]
        return f"{y + 1911:04d}-{m:02d}-{d:02d}"
    except (ValueError, AttributeError):
        return None


def _table(mkt: str, js: dict) -> tuple[list, list]:
    if mkt == "twse":
        return list(js.get("fields") or []), list(js.get("data") or [])
    t = (js.get("tables") or [{}])[0]
    return list(t.get("fields") or []), list(t.get("data") or [])


def fetch(until: str | None) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    n_req = 0
    for mkt, y, h in JOBS:
        f = RAW / f"{mkt}_{y}_{h}.json"
        if f.exists():
            continue
        if until and datetime.now().strftime("%H:%M") >= until:
            print(f"到 {until}，停止送新請求（下次從 {mkt} {y}H{h} 續）", flush=True)
            break
        a, b = _span(y, h)
        if mkt == "twse":
            src, url, p = "twse_exright", "https://www.twse.com.tw/rwd/zh/exRight/TWT49U", \
                {"startDate": a.replace("-", ""), "endDate": b.replace("-", ""), "response": "json"}
        else:
            src, url, p = "tpex_www", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", \
                {"startDate": a.replace("-", "/"), "endDate": b.replace("-", "/"), "response": "json"}
        _rate_limit_wait_or_raise(src)
        r = requests.get(url, params=p, timeout=60, headers=UA)
        n_req += 1
        if r.status_code in BLOCK:
            _rate_limit_record_block(src, r.status_code, "exright_2007_2014")
            print(f"{mkt} {y}H{h} HTTP {r.status_code}，封鎖 2 小時，停止", flush=True)
            return 1
        try:
            js = r.json()
        except ValueError:
            print(f"{mkt} {y}H{h} 回傳不是 JSON（HTTP {r.status_code}），停止", flush=True)
            return 1
        fl, data = _table(mkt, js)
        if data and not fl:
            print(f"{mkt} {y}H{h} 有資料列但沒有欄位名，停止（不猜格式）", flush=True)
            return 1
        f.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
        print(f"{mkt} {y}H{h}: HTTP {r.status_code}，{len(data)} 列", flush=True)
    print(f"本次請求 {n_req} 次", flush=True)
    return 0


def official_events() -> pd.DataFrame:
    files = [(m, RAW / f"{m}_{y}_{h}.json") for m, y, h in JOBS]
    files += [("twse", TWSE_2013_CACHE / f"{y}_{h}.json") for y in (2013, 2014) for h in (1, 2)]
    rows, missing = [], []
    for mkt, f in files:
        if not f.exists():
            missing.append(str(f.relative_to(HERE)))
            continue
        fl, data = _table(mkt, json.loads(f.read_text(encoding="utf-8")))
        if not data:
            continue
        kd, kc = ("資料日期", "股票代號") if mkt == "twse" else ("除權息日期", "代號")
        for k in (kd, kc, "除權息前收盤價", "除權息參考價"):
            if k not in fl:
                raise RuntimeError(f"{f.name} 找不到欄位「{k}」：{fl}")
        i_d, i_c, i_pc, i_ref = fl.index(kd), fl.index(kc), fl.index("除權息前收盤價"), fl.index("除權息參考價")
        i_k = next((fl.index(k) for k in ("權/息", "權值+息值", "除權息") if k in fl), None)
        for row in data:
            d, c, pc, ref = _roc(row[i_d]), str(row[i_c]).strip(), _num(row[i_pc]), _num(row[i_ref])
            if d and c and pc and ref and pc > 0 and ref > 0:
                rows.append((d, c, mkt, pc, ref, ref / pc, str(row[i_k]).strip() if i_k is not None else ""))
    if missing:
        print(f"⚠️ 快取缺 {len(missing)} 份：{missing}", flush=True)
    df = pd.DataFrame(rows, columns=["ex_date", "stock_id", "market", "prev_close", "ref_price", "factor", "kind"])
    df = df[(df["ex_date"] >= START) & (df["ex_date"] <= END)].drop_duplicates(["ex_date", "stock_id"])
    return df.sort_values(["ex_date", "stock_id"]).reset_index(drop=True), missing


def finmind_ex_dates() -> dict[str, set]:
    """每檔挑一份涵蓋 2007-07-01～2014-12-31 的本機快取（零請求），回傳 {代號: {除權息日}}。"""
    best: dict[str, Path] = {}
    for f in FM_RAW.glob("TaiwanStockDividend__*__*__*.parquet"):
        parts = f.stem.split("__")
        if len(parts) != 4 or not parts[1].isalnum() or not parts[1][:1].isdigit():
            continue
        s, e = parts[2], parts[3]
        if s <= START and (e == "latest" or e >= END):
            best.setdefault(parts[1], f)
    out: dict[str, set] = {}
    for c, f in best.items():
        try:
            d = pd.read_parquet(f)
        except Exception as e:  # noqa: BLE001 — 單檔壞掉只略過該檔
            print(f"⚠️ 讀不到 {f.name}：{type(e).__name__}", flush=True)
            continue
        ds = set()  # FinMind 回空表時快取是沒有欄位的空檔＝有快取、零筆股利
        for col in ("CashExDividendTradingDate", "StockExDividendTradingDate"):
            if col not in d.columns:
                continue
            ds |= {str(x)[:10] for x in d[col].dropna() if str(x).strip()}
        out[c] = {x for x in ds if START <= x <= END}
    return out


def compare() -> int:
    ev, missing = official_events()
    ev.to_csv(OUT_CSV, index=False)
    fm = finmind_ex_dates()
    by_year: dict = defaultdict(lambda: defaultdict(int))
    unmatched_sample: dict = defaultdict(list)
    off_keys = set()
    for r in ev.itertuples():
        y = r.ex_date[:4]
        off_keys.add((r.stock_id, r.ex_date))
        b = by_year[y]
        b[f"official_{r.market}"] += 1
        if r.stock_id not in fm:
            b["official_stock_no_finmind_cache"] += 1
            continue
        b["official_with_finmind_cache"] += 1
        if r.ex_date in fm[r.stock_id]:
            b["finmind_same_day"] += 1
        else:
            b["finmind_missing_same_day"] += 1
            if len(unmatched_sample[y]) < 15:
                unmatched_sample[y].append(f"{r.stock_id} {r.ex_date}")
    for c, ds in fm.items():
        for d in ds:
            if (c, d) not in off_keys:
                by_year[d[:4]]["finmind_only_not_in_official"] += 1
    years = {y: dict(by_year[y]) for y in sorted(by_year)}
    for y, b in years.items():
        n = b.get("official_with_finmind_cache", 0)
        b["finmind_same_day_rate"] = round(b.get("finmind_same_day", 0) / n, 4) if n else None
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "task": "補.資料-官方除權息 2007-07～2014 抓取存本機（只抓不套用；先.一三三-1c 資料缺口）",
        "window": [START, END],
        "sources": {"twse": "TWT49U（2007H2～2012H2 本次抓；2013～2014 讀 research/data/raw/twse_twt49u/）",
                    "tpex": "exDailyQ（2007H2～2014H2 本次抓）",
                    "finmind": "TaiwanStockDividend 本機快取（涵蓋整段的那份），零請求；除息日 CashExDividendTradingDate／除權日 StockExDividendTradingDate"},
        "n_official_events": int(len(ev)),
        "n_finmind_cached_stocks": len(fm),
        "n_finmind_cached_stocks_zero_events_in_window": sum(1 for v in fm.values() if not v),
        "official_cache_missing_files": missing,
        "by_year": years,
        "unmatched_sample_by_year": dict(unmatched_sample),
        "notes": ["只數事件、不改 adjust.py、不算報酬、不碰 holdout；怎麼套用等 先.一三三-1c 定案。",
                  "官方一筆＝同股同日一個除權息事件（權息同日只算一筆）；FinMind 同日除權與除息也只算一個日子。",
                  "上櫃 exDailyQ 歷史起點約 2007-12-17（2007H2 只回 3 列），所以 2007 年 finmind_only_not_in_official 大多是 2007-07～12 的上櫃事件，不是 FinMind 多出來的。",
                  "official_with_finmind_cache 含 FinMind 快取是空表（整段零筆股利）的股票——那些官方有事件就算 FinMind 漏記。",
                  "finmind_only_not_in_official：FinMind 有、官方同日沒有（可能日期差一天、或官方表未收錄、或 FinMind 日期錯）。"],
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"官方事件 {len(ev)} 筆；FinMind 快取 {len(fm)} 檔 → {OUT_JSON.name}", flush=True)
    for y, b in years.items():
        print(y, json.dumps(b, ensure_ascii=False), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--until", default=None, help="HH:MM 到點就不送新請求")
    a = ap.parse_args()
    if not a.no_fetch:
        rc = fetch(a.until)
        if rc:
            return rc
    return compare()


if __name__ == "__main__":
    raise SystemExit(main())
