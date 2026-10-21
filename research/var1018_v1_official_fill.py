# -*- coding: utf-8 -*-
"""先.一三〇-3 ②：用官方全市場日檔補 V1（2006～2014）價格缺口。只抓資料、不寫 PREREG、不登記試驗、不回測、不碰 holdout。

缺口日期來自 research/data/var1018_v1_gap_diagnosis.json 的 weekdays_to_fill（① 診斷，零請求產出）。
以「日期」為單位抓，一次拿到當天所有在市股票（含日後下市者）：
- 上市：www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999&response=json
  取「每日收盤行情(全部(不含權證、牛熊證、可展延牛熊證))」表；2026-10-22 實測 2007-01-02 回 705 檔。
- 上櫃：www.tpex.org.tw/www/zh-tw/afterTrading/otc?date=YYYY/MM/DD&type=EW&response=json
  取「上櫃股票每日收盤行情(不含定價)」表。2026-10-22 起點探測：2007-01-02／01-03／04-02／05-02／06-01／06-15 皆 0 列，
  2007-07-02 有 826 列 → 此端點歷史起點約 2007-06 下旬（第 10 關）。[自行裁量] 2007-06-15（含）以前不送上櫃請求，記為 before_source_start。
  （舊版 web/stock/aftertrading/daily_close_quotes/stk_quote_result.php 帶 d=96/01/02 會回最新一日，不可用。）
robots：www.twse.com.tw 只禁 /epaper/、/FTSE/；www.tpex.org.tw/robots.txt 不存在。兩邊官方都未公布次數上限。
節流：共用 data/rate_limit_state.json（twse_mi_index／tpex_www，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）；
上市與上櫃交錯送出，兩個來源各自計間隔。回應不是 JSON 或找不到預期表格 → 停抓（不猜格式）。

快取（精簡，不存原始回應）：research/data/v1_official_daily/{twse,tpex}/YYYYMMDD.json
  {"date","source","status": ok|no_data|before_source_start, "fields": [...], "rows": {代號: [開,高,低,收,成交股數,成交金額]}}
  休市日官方回「沒有符合條件的資料」或空表 → status=no_data（也算已抓，不重抓）。
用法：python research/var1018_v1_official_fill.py [--until HH:MM] [--max-req N]
      python research/var1018_v1_official_fill.py --check   （與 FinMind 重疊日抽 50 檔核對收盤，零請求）
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

DIAG = HERE / "data" / "var1018_v1_gap_diagnosis.json"
OUT = HERE / "data" / "v1_official_daily"
STATUS = HERE / "data" / "var1018_v1_official_fill_status.json"
BLOCK = {402, 403, 428, 429}
UA = "alpha-research/1.0 (personal research; daily-bar backfill)"
TPEX_FIRST_TRY = "2007-06-18"  # 起點探測：06-15 空、07-02 有

SOURCES = {
    "twse": {
        "rl": "twse_mi_index",
        "url": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        "params": lambda d: {"date": d.replace("-", ""), "type": "ALLBUT0999", "response": "json"},
        "title_has": "每日收盤行情",
        "cols": {"code": "證券代號", "open": "開盤價", "high": "最高價", "low": "最低價", "close": "收盤價",
                 "shares": "成交股數", "value": "成交金額"},
    },
    "tpex": {
        "rl": "tpex_www",
        "url": "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc",
        "params": lambda d: {"date": d.replace("-", "/"), "type": "EW", "response": "json"},
        "title_has": "上櫃股票每日收盤行情",
        "cols": {"code": "代號", "open": "開盤", "high": "最高", "low": "最低", "close": "收盤",
                 "shares": "成交股數", "value": "成交金額"},
    },
}
COL_ORDER = ["open", "high", "low", "close", "shares", "value"]


def _num(v):
    s = str(v or "").replace(",", "").strip()
    if s in ("", "--", "---", "----", "X", "除權", "除息"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _col_index(fields: list[str], want: str) -> int | None:
    """欄位名去空白後比對（上櫃欄位名帶尾端空白與 <br>）；找第一個以 want 開頭的欄位。"""
    norm = [str(f).replace(" ", "").split("<br>")[0] for f in fields]
    for i, f in enumerate(norm):
        if f == want:
            return i
    for i, f in enumerate(norm):
        if f.startswith(want):
            return i
    return None


def parse(src: str, j: dict) -> tuple[str, list, dict]:
    """回 (status, fields, rows)。找不到預期表格且也不是官方「無資料」→ 拋 ValueError（停抓，不猜）。"""
    cfg = SOURCES[src]
    stat = str(j.get("stat") or "")
    tables = j.get("tables") or []
    tbl = next((t for t in tables if cfg["title_has"] in str(t.get("title") or "")), None)
    if tbl is None:
        if src == "twse" and stat != "OK":
            return "no_data", [], {}  # 休市日：stat=「很抱歉，沒有符合條件的資料!」
        raise ValueError(f"stat={stat!r}，找不到含「{cfg['title_has']}」的表格（tables={[t.get('title') for t in tables]}）")
    data = tbl.get("data") or []
    if not data:
        return "no_data", tbl.get("fields") or [], {}
    fields = tbl.get("fields") or []
    idx = {k: _col_index(fields, v) for k, v in cfg["cols"].items()}
    missing = [k for k, v in idx.items() if v is None]
    if missing:
        raise ValueError(f"欄位對不上 {missing}：{fields}")
    rows = {}
    for r in data:
        code = str(r[idx["code"]]).strip()
        if code:
            rows[code] = [_num(r[idx[k]]) for k in COL_ORDER]
    return "ok", fields, rows


def cache_path(src: str, d: str) -> Path:
    return OUT / src / f"{d.replace('-', '')}.json"


def todo_list(dates: list[str]) -> list[tuple[str, str]]:
    out = []
    for d in dates:
        for src in ("twse", "tpex"):
            if not cache_path(src, d).exists():
                out.append((src, d))
    return out


def write_cache(src: str, d: str, status: str, fields: list, rows: dict) -> None:
    p = cache_path(src, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"date": d, "source": src, "status": status, "fields": fields, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def write_status(dates: list[str], stopped: str, n_req: int) -> dict:
    st = {"generated_at": datetime.now().isoformat(timespec="seconds"), "n_dates": len(dates), "stopped": stopped,
          "requests_this_run": n_req, "by_source": {}}
    for src in ("twse", "tpex"):
        c = {"ok": 0, "no_data": 0, "before_source_start": 0, "missing": 0}
        for d in dates:
            p = cache_path(src, d)
            if not p.exists():
                c["missing"] += 1
            else:
                c[json.loads(p.read_text(encoding="utf-8"))["status"]] += 1
        st["by_source"][src] = c
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return st


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", help="台北時間 HH:MM 到點就停（不送新請求）")
    ap.add_argument("--max-req", type=int, default=10**9)
    a = ap.parse_args()
    dates = json.loads(DIAG.read_text(encoding="utf-8"))["weekdays_to_fill"]
    # 上櫃起點前的日期直接記 before_source_start（零請求）
    for d in dates:
        if d < TPEX_FIRST_TRY and not cache_path("tpex", d).exists():
            write_cache("tpex", d, "before_source_start", [], {})
    todo = todo_list(dates)
    # 交錯：同一天先上市再上櫃，兩個來源各自節流
    print(f"缺口日期 {len(dates)} 天；尚缺 {len(todo)} 個（來源×日期）", flush=True)
    n_req = 0
    stopped = "全部抓完"
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
            _rate_limit_record_block(cfg["rl"], r.status_code, f"v1_official_fill {d}")
            stopped = f"{src} {d} HTTP {r.status_code}，封鎖 2 小時，停止"
            break
        try:
            status, fields, rows = parse(src, r.json())
        except ValueError as e:
            stopped = f"{src} {d}：回應格式不符（HTTP {r.status_code}）：{str(e)[:200]}，停止"
            break
        write_cache(src, d, status, fields, rows)
        if n_req % 50 == 0:
            print(f"  已送 {n_req} 次；最新 {src} {d} {status} {len(rows)} 檔", flush=True)
    st = write_status(dates, stopped, n_req)
    print(json.dumps(st, ensure_ascii=False), flush=True)
    return 0




def cross_check(n_codes: int = 50, seed: int = 20261022) -> dict:
    """與 FinMind 本機快取（var1018_v1_prep 抓的 2006～2014 原始收盤）重疊日比對收盤價；零請求。
    固定亂數種子從「官方日檔與 FinMind 都有值」的代號中抽 n_codes 檔，逐日比對，差 >0.5% 算不一致。"""
    import random

    import pandas as pd
    raw = HERE / "data" / "raw"
    off: dict[str, dict[str, float]] = {}
    for src in ("twse", "tpex"):
        for p in sorted((OUT / src).glob("*.json")):
            j = json.loads(p.read_text(encoding="utf-8"))
            for c, v in (j.get("rows") or {}).items():
                if v[3] is not None:
                    off.setdefault(c, {})[j["date"]] = v[3]
    cand = sorted(c for c in off if (raw / f"TaiwanStockPrice__{c}__2006-01-01__2014-12-31.parquet").exists())
    pick = random.Random(seed).sample(cand, min(n_codes, len(cand)))
    n_cmp = n_bad = 0
    bad = []
    for c in pick:
        df = pd.read_parquet(raw / f"TaiwanStockPrice__{c}__2006-01-01__2014-12-31.parquet")
        fm = dict(zip(df["date"].astype(str).str[:10], df["close"].astype(float)))
        for d, v in off[c].items():
            if d in fm and fm[d] > 0:
                n_cmp += 1
                if abs(v / fm[d] - 1) > 0.005:
                    n_bad += 1
                    if len(bad) < 20:
                        bad.append({"code": c, "date": d, "official": v, "finmind": fm[d]})
    return {"n_codes_candidates": len(cand), "n_codes_checked": len(pick), "n_compared": n_cmp,
            "n_mismatch": n_bad, "mismatch_rate": round(n_bad / n_cmp, 6) if n_cmp else None, "examples": bad}


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        print(json.dumps(cross_check(), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    raise SystemExit(main())
