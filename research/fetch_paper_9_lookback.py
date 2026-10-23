# -*- coding: utf-8 -*-
"""先.一三二-0 ②：模擬 I（#463）252 日回看資料一次性抓取。只抓資料、不算任何報酬或淨值。

依據：docs/PREREG_STOCK_BREAKOUT_252H_FINAL.md §5-1「採甲」（總司令 2026-10-22 13:1x 裁示）。
2025-10-28～2026-10-30 的官方全市場日檔屬 holdout 期間，**只當 252 日最高還原收盤與 20 日均量的訊號回看輸入**；
本腳本與 research/paper_9_breakout_tracker.py 是唯二可讀 research/data/paper_9_lookback/ 的程式
（research/validation/holdout.py ALLOWED_HOLDOUT_READERS／RESTRICTED_LOOKBACK_DIRS；scripts/selftest_display_only_files.py 檢查）。

端點與 V1 官方日檔補價相同（research/var1018_v1_official_fill.py，C:\\alpha\\CLAUDE.md「V1 缺口補價」）：
- 上市：www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999&response=json
- 上櫃：www.tpex.org.tw/www/zh-tw/afterTrading/otc?date=YYYY/MM/DD&type=EW&response=json
官方都未公布次數上限。節流：共用 data/rate_limit_state.json（twse_mi_index／tpex_www，跨行程鎖、同源間隔 ≥3 秒，
402/403/428/429 封鎖 2 小時不重試）；與 V1 補價撞源時由共用鎖自動輪流。回應格式不符就停抓、不猜。
日期：週一～五，扣掉 data/trading_calendar.json 已知休市日；只抓「已收盤」的日子（今天 15:00 以前不抓今天）。

快取：research/data/paper_9_lookback/{twse,tpex}/YYYYMMDD.json
  {"date","source","status": ok|no_data, "rows": {代號: [開,高,低,收,成交股數,成交金額,漲跌]}}
  漲跌＝相對「當日參考價」的帶號數字（除權息日官方以除權息參考價計），解析不到記 None；追蹤程式用
  參考價＝收盤−漲跌 推算還原係數（同 update_price_history.py 的「參考價÷前收」口徑）。
用法：python research/fetch_paper_9_lookback.py [--until HH:MM] [--max-req N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

START, END = "2025-10-28", "2026-10-30"
OUT = HERE / "data" / "paper_9_lookback"
STATUS = OUT / "_status.json"
CAL = ROOT / "data" / "trading_calendar.json"
BLOCK = {402, 403, 428, 429}
UA = "alpha-research/1.0 (personal research; daily-bar lookback)"

SOURCES = {
    "twse": {
        "rl": "twse_mi_index",
        "url": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        "params": lambda d: {"date": d.replace("-", ""), "type": "ALLBUT0999", "response": "json"},
        "title_has": "每日收盤行情",
        "cols": {"code": "證券代號", "open": "開盤價", "high": "最高價", "low": "最低價", "close": "收盤價",
                 "shares": "成交股數", "value": "成交金額", "sign": "漲跌(+/-)", "chg": "漲跌價差"},
    },
    "tpex": {
        "rl": "tpex_www",
        "url": "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc",
        "params": lambda d: {"date": d.replace("-", "/"), "type": "EW", "response": "json"},
        "title_has": "上櫃股票每日收盤行情",
        "cols": {"code": "代號", "open": "開盤", "high": "最高", "low": "最低", "close": "收盤",
                 "shares": "成交股數", "value": "成交金額", "chg": "漲跌"},
    },
}
COL_ORDER = ["open", "high", "low", "close", "shares", "value"]


def _num(v):
    s = str(v or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _col_index(fields: list[str], want: str) -> int | None:
    norm = [str(f).replace(" ", "").split("<br>")[0] for f in fields]
    for i, f in enumerate(norm):
        if f == want:
            return i
    for i, f in enumerate(norm):
        if f.startswith(want):
            return i
    return None


def _signed_change(src: str, r: list, idx: dict):
    if src == "twse":
        mag = _num(r[idx["chg"]])
        sign = re.sub(r"<[^>]+>", "", str(r[idx["sign"]] or "")).strip()
        if mag is None:
            return None
        if mag == 0:
            return 0.0
        if sign == "+":
            return mag
        if sign == "-":
            return -mag
        return None  # X（不比價）等
    s = str(r[idx["chg"]] or "").replace(",", "").strip()
    return _num(s)  # 上櫃帶號（+0.50／-1.20／0.00）；「除息」等文字記 None


def parse(src: str, j: dict) -> tuple[str, dict]:
    cfg = SOURCES[src]
    stat = str(j.get("stat") or "")
    tables = j.get("tables") or []
    tbl = next((t for t in tables if cfg["title_has"] in str(t.get("title") or "")), None)
    if tbl is None:
        if src == "twse" and stat != "OK":
            return "no_data", {}
        if src == "tpex" and not any(t.get("data") for t in tables):
            return "no_data", {}
        raise ValueError(f"stat={stat!r}，找不到含「{cfg['title_has']}」的表格（tables={[t.get('title') for t in tables]}）")
    data = tbl.get("data") or []
    if not data:
        return "no_data", {}
    fields = tbl.get("fields") or []
    idx = {k: _col_index(fields, v) for k, v in cfg["cols"].items()}
    missing = [k for k, v in idx.items() if v is None]
    if missing:
        raise ValueError(f"欄位對不上 {missing}：{fields}")
    rows = {}
    for r in data:
        code = str(r[idx["code"]]).strip()
        if code:
            rows[code] = [_num(r[idx[k]]) for k in COL_ORDER] + [_signed_change(src, r, idx)]
    return "ok", rows


def cache_path(src: str, d: str) -> Path:
    return OUT / src / f"{d.replace('-', '')}.json"


def wanted_dates(now: datetime | None = None) -> list[str]:
    now = now or datetime.now()
    closed = set()
    try:
        for y in json.loads(CAL.read_text(encoding="utf-8")).get("tw", {}).values():
            closed.update(y.get("closed") or [])
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 讀 trading_calendar.json 失敗（{type(e).__name__}），休市日改由官方回 no_data 判斷", flush=True)
    last = now.date() if now.hour >= 15 else now.date() - timedelta(days=1)
    d, end = date.fromisoformat(START), min(date.fromisoformat(END), last)
    out = []
    while d <= end:
        s = d.isoformat()
        if d.weekday() < 5 and s not in closed:
            out.append(s)
        d += timedelta(days=1)
    return out


def write_cache(src: str, d: str, status: str, rows: dict) -> None:
    p = cache_path(src, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"date": d, "source": src, "status": status, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def write_status(dates: list[str], stopped: str, n_req: int) -> dict:
    st = {"generated_at": datetime.now().isoformat(timespec="seconds"), "range": [START, END],
          "n_dates_due": len(dates), "stopped": stopped, "requests_this_run": n_req, "by_source": {}}
    for src in SOURCES:
        c = {"ok": 0, "no_data": 0, "missing": 0}
        for d in dates:
            p = cache_path(src, d)
            c[json.loads(p.read_text(encoding="utf-8"))["status"] if p.exists() else "missing"] += 1
        st["by_source"][src] = c
    OUT.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", help="台北時間 HH:MM 到點就停（不送新請求）")
    ap.add_argument("--max-req", type=int, default=10**9)
    a = ap.parse_args()
    dates = wanted_dates()
    todo = [(s, d) for d in dates for s in SOURCES if not cache_path(s, d).exists()]
    print(f"應抓日期 {len(dates)} 天；尚缺 {len(todo)} 個（來源×日期）", flush=True)
    n_req, stopped = 0, "全部抓完（到目前已收盤日）"
    for src, d in todo:
        if a.until and datetime.now().strftime("%H:%M") >= a.until:
            stopped = f"到 {a.until} 停止；下一個 {src} {d}"
            break
        if n_req >= a.max_req:
            stopped = f"達本次上限 --max-req {a.max_req}；下一個 {src} {d}"
            break
        cfg = SOURCES[src]
        try:
            _rate_limit_wait_or_raise(cfg["rl"])
        except RuntimeError as e:
            stopped = f"節流拒絕（{cfg['rl']}）：{e}"
            break
        try:
            r = requests.get(cfg["url"], params=cfg["params"](d), timeout=60, headers={"User-Agent": UA})
        except requests.RequestException as e:
            stopped = f"{src} {d} 連線失敗 {type(e).__name__}（不重試）"
            break
        n_req += 1
        if r.status_code in BLOCK:
            _rate_limit_record_block(cfg["rl"], r.status_code, f"paper_9_lookback {d}")
            stopped = f"{src} {d} HTTP {r.status_code}，封鎖 2 小時，停止"
            break
        try:
            status, rows = parse(src, r.json())
        except ValueError as e:
            stopped = f"{src} {d}：回應格式不符（HTTP {r.status_code}）：{str(e)[:200]}，停止"
            break
        write_cache(src, d, status, rows)
        if n_req % 25 == 0:
            print(f"  已送 {n_req} 次；最新 {src} {d} {status} {len(rows)} 檔", flush=True)
    st = write_status(dates, stopped, n_req)
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
