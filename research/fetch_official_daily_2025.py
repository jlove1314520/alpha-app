# -*- coding: utf-8 -*-
"""先.一五五-3 第 12 批 #54 成交值集中度延長：抓 2025-01-02 起官方全市場日檔（上市＋上櫃）。

為什麼：本機 2025 起逐檔 FinMind 快取名冊不完整（2024-12 有交易 1,946 檔只有 1,378 檔有 2025 起快取，
成交值占 89.6%），直接接會在 2025-01 出現假斷層。改用官方全市場日檔，2025 起名冊才完整、含下市。

端點、解析、節流全部沿用 research/var1018_v1_official_fill.py（只 import，不改）：
- 上市：www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999&response=json
- 上櫃：www.tpex.org.tw/www/zh-tw/afterTrading/otc?date=YYYY/MM/DD&type=EW&response=json
官方都未公布次數上限；共用 data/rate_limit_state.json（twse_mi_index／tpex_www，跨行程鎖、同源間隔 ≥3 秒，
402/403/428/429 封鎖 2 小時不重試）；回應格式不符就停。已抓日期不重抓。
另抓 FMTQIK（市場成交資訊，一次一整月，twse_rwd 節流）2025-01 起，供涵蓋率檢查。

快取：research/data/official_daily_2025/{twse,tpex}/YYYYMMDD.json（格式同 v1_official_daily）
      research/data/raw_twse_market_volume/FMTQIK_YYYYMM.parquet（date, total_value，同既有檔）
用法：python research/fetch_official_daily_2025.py [--until HH:MM] [--max-req N]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import var1018_v1_official_fill as v1  # noqa: E402
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

START, END = "2025-01-02", "2026-11-09"
OUT = HERE / "data" / "official_daily_2025"
MV = HERE / "data" / "raw_twse_market_volume"
CAL = ROOT / "data" / "trading_calendar.json"


def cache_path(src: str, d: str) -> Path:
    return OUT / src / f"{d.replace('-', '')}.json"


def wanted_dates() -> list[str]:
    closed = set()
    try:
        for y in json.loads(CAL.read_text(encoding="utf-8")).get("tw", {}).values():
            closed.update(y.get("closed") or [])
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 讀 trading_calendar.json 失敗（{type(e).__name__}），休市日改由官方回 no_data 判斷", flush=True)
    d, end, out = date.fromisoformat(START), date.fromisoformat(END), []
    while d <= end:
        s = d.isoformat()
        if d.weekday() < 5 and s not in closed:
            out.append(s)
        d += timedelta(days=1)
    return out


def write_cache(src: str, d: str, status: str, fields: list, rows: dict) -> None:
    p = cache_path(src, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"date": d, "source": src, "status": status, "fields": fields, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def _roc_to_iso(s: str) -> str:
    y, m, dd = str(s).strip().split("/")
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(dd):02d}"


def fetch_fmtqik(months: list[str], deadline: str | None) -> str:
    import pandas as pd
    for ym in months:
        p = MV / f"FMTQIK_{ym}.parquet"
        if p.exists():
            continue
        if deadline and datetime.now().strftime("%H:%M") >= deadline:
            return f"FMTQIK 到 {deadline} 停；下一個 {ym}"
        try:
            _rate_limit_wait_or_raise("twse_rwd")
        except RuntimeError as e:
            return f"FMTQIK 節流拒絕：{e}"
        try:
            r = requests.get("https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK",
                             params={"date": f"{ym}01", "response": "json"}, timeout=60, headers={"User-Agent": v1.UA})
        except requests.RequestException as e:
            return f"FMTQIK {ym} 連線失敗 {type(e).__name__}（不重試）"
        if r.status_code in v1.BLOCK:
            _rate_limit_record_block("twse_rwd", r.status_code, f"fetch_official_daily_2025 FMTQIK {ym}")
            return f"FMTQIK {ym} HTTP {r.status_code}，封鎖 2 小時"
        j = r.json()
        fields, data = j.get("fields") or [], j.get("data") or []
        if j.get("stat") != "OK" or not data:
            return f"FMTQIK {ym} stat={j.get('stat')!r}，停"
        try:
            i_d, i_v = fields.index("日期"), fields.index("成交金額")
        except ValueError:
            return f"FMTQIK {ym} 欄位對不上 {fields}，停"
        df = pd.DataFrame({"date": [_roc_to_iso(x[i_d]) for x in data],
                           "total_value": [float(str(x[i_v]).replace(",", "")) for x in data]})
        MV.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)
        print(f"  FMTQIK {ym} {len(df)} 日", flush=True)
    return "FMTQIK 全部抓完"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", help="台北時間 HH:MM 到點就停（不送新請求）")
    ap.add_argument("--max-req", type=int, default=10**9)
    a = ap.parse_args()
    dates = wanted_dates()
    months = sorted({d[:7].replace("-", "") for d in dates})
    todo = [(s, d) for d in dates for s in ("twse", "tpex") if not cache_path(s, d).exists()]
    print(f"應抓日期 {len(dates)} 天；尚缺 {len(todo)} 個（來源×日期）", flush=True)
    n_req, stopped = 0, "全部抓完"
    for src, d in todo:
        if a.until and datetime.now().strftime("%H:%M") >= a.until:
            stopped = f"到 {a.until} 停止；下一個 {src} {d}"
            break
        if n_req >= a.max_req:
            stopped = f"達本次上限 --max-req {a.max_req}；下一個 {src} {d}"
            break
        cfg = v1.SOURCES[src]
        try:
            _rate_limit_wait_or_raise(cfg["rl"])
        except RuntimeError as e:
            stopped = f"節流拒絕（{cfg['rl']}）：{e}"
            break
        try:
            r = requests.get(cfg["url"], params=cfg["params"](d), timeout=60, headers={"User-Agent": v1.UA})
        except requests.RequestException as e:
            stopped = f"{src} {d} 連線失敗 {type(e).__name__}（不重試）"
            break
        n_req += 1
        if r.status_code in v1.BLOCK:
            _rate_limit_record_block(cfg["rl"], r.status_code, f"fetch_official_daily_2025 {d}")
            stopped = f"{src} {d} HTTP {r.status_code}，封鎖 2 小時，停止"
            break
        try:
            status, fields, rows = v1.parse(src, r.json())
        except ValueError as e:
            stopped = f"{src} {d}：回應格式不符（HTTP {r.status_code}）：{str(e)[:200]}，停止"
            break
        write_cache(src, d, status, fields, rows)
        if n_req % 50 == 0:
            print(f"  已送 {n_req} 次；最新 {src} {d} {status} {len(rows)} 檔", flush=True)
    fm = fetch_fmtqik(months, a.until)
    print(fm, flush=True)
    stopped += f"；{fm}"
    have = {s: sum(cache_path(s, d).exists() for d in dates) for s in ("twse", "tpex")}
    st = {"generated_at": datetime.now().isoformat(timespec="seconds"), "range": [START, END], "n_dates": len(dates),
          "have": have, "requests_this_run": n_req, "stopped": stopped}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_status.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
