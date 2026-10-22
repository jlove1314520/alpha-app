# -*- coding: utf-8 -*-
"""先.一三〇-3 ②-b：上櫃 2007 上半年缺口改用 TPEx「個股日成交資訊」逐檔×月補。只抓資料、不回測、不碰 holdout。

為什麼需要：上櫃全市場日檔 afterTrading/otc 歷史起點約 2007-06 下旬（2026-10-22 實測），而 ① 診斷的 2007Q1 大空洞
（2006-12-29～2007-04-23 共 90 檔）有 87 檔當時是上櫃股——全市場日檔補不到。
端點：www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code=代號&date=YYYY/MM/01&response=json
  2026-10-22 08:1x 探測 1 次：2059 川湖 2007/02 回「個股日成交資訊」12 列（欄位：日期(民國)／成交仟股／成交仟元／開高低收／漲跌／筆數）。
robots：www.tpex.org.tw/robots.txt 不存在；官方未公布次數上限。節流共用 data/rate_limit_state.json 來源名 tpex_www
（同源間隔 ≥3 秒、跨行程鎖，與 var1018_v1_official_fill.py 共用；402/403/428/429 封鎖 2 小時不重試）。

要抓的（代號, 月份），只限 2006-12～2007-06：
  A. ① 診斷「未涵蓋」且問題落在 2007-07-02 以前的股票：缺口（或尾端早停的最後價格到下市日）跨到的月份；
  B. ① 診斷「前段缺」裡板別為上櫃／未知、未在期初前下市的股票：先抓 2007-01（判斷 t0 當時在不在市）；
     有資料才補抓 2007-02～2007-06（之後由全市場日檔接手）。
  上市股（2007 上半年出現在 TWSE MI_INDEX 快取裡的）一律跳過——上市的缺口由全市場日檔補。
回應檢查：不是 JSON、或找不到「個股日成交資訊」表、或回傳列的日期不在要求的月份 → 停抓（不猜格式；防「回最新一日」那種舊端點行為）。
  JSON 但沒有資料列 → no_data（也算已抓）。
快取：research/data/v1_official_daily/tpex_stock/{代號}/{YYYYMM}.json
  {"code","month","status": ok|no_data, "rows": {"YYYY-MM-DD": [開,高,低,收,成交股數,成交金額]}}（成交仟股、仟元已換成股、元）
用法：python research/var1018_v1_tpex_stock_fill.py [--until HH:MM] [--max-req N] [--plan]（--plan 只印要抓幾個，零請求）
      python research/var1018_v1_tpex_stock_fill.py --check（與 FinMind 重疊日核對收盤，零請求）
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
DAILY = HERE / "data" / "v1_official_daily"
OUT = DAILY / "tpex_stock"
URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
UA = {"User-Agent": "alpha-research/1.0 (personal research; daily-bar backfill)"}
BLOCK = {402, 403, 428, 429}
MONTHS = ["200612", "200701", "200702", "200703", "200704", "200705", "200706"]
LAST_DAY = "2007-07-01"


def _num(v):
    s = str(v or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _roc(s: str) -> str | None:
    p = "".join(ch for ch in str(s) if ch.isdigit() or ch == "/").split("/")  # 官方會在日期後加「*」註記
    if len(p) != 3:
        return None
    try:
        return f"{int(p[0]) + 1911:04d}-{int(p[1]):02d}-{int(p[2]):02d}"
    except ValueError:
        return None


def _months_between(a: str, b: str) -> list[str]:
    """a、b 為 YYYY-MM-DD；回 MONTHS 裡落在 [a 的月, b 的月] 的月份。"""
    lo, hi = a[:7].replace("-", ""), b[:7].replace("-", "")
    return [m for m in MONTHS if lo <= m <= hi]


def twse_codes_2007h1() -> set[str]:
    out: set[str] = set()
    for p in sorted((DAILY / "twse").glob("2007*.json")) + sorted((DAILY / "twse").glob("200612*.json")):
        if p.stem <= "20070630":
            out |= set(json.loads(p.read_text(encoding="utf-8")).get("rows") or {})
    return out


def plan() -> tuple[list[tuple[str, str]], list[str]]:
    """回 (A 類固定要抓的 (代號, 月)), B 類要先探 2007-01 的代號)。"""
    d = json.loads(DIAG.read_text(encoding="utf-8"))
    listed = twse_codes_2007h1()
    a: set[tuple[str, str]] = set()
    for u in d["uncovered"]:
        if u["code"] in listed:
            continue
        for g in u.get("gaps") or []:
            if g[0] < LAST_DAY:
                a |= {(u["code"], m) for m in _months_between(g[0], min(g[1], LAST_DAY))}
        if u["kind"] != "中段缺口" and u["last_price"] < LAST_DAY:
            end = min(u.get("delist_date") or LAST_DAY, LAST_DAY)
            a |= {(u["code"], m) for m in _months_between(u["last_price"], end)}
    b = sorted(f["code"] for f in d["front_missing"]
               if f["board"] in ("上櫃", "未知") and f["code"] not in listed
               and not (f.get("delist_date") and f["delist_date"] < "2007-01-02"))
    return sorted(a), b


def cache_path(code: str, month: str) -> Path:
    return OUT / code / f"{month}.json"


def parse(code: str, month: str, j: dict) -> tuple[str, dict]:
    tbl = next((t for t in (j.get("tables") or []) if "個股日成交資訊" in str(t.get("title") or "")), None)
    if tbl is None:
        if not j.get("tables"):
            return "no_data", {}
        raise ValueError(f"找不到「個股日成交資訊」表：{[t.get('title') for t in j['tables']]}")
    data = tbl.get("data") or []
    if not data:
        return "no_data", {}
    f = [str(x).replace(" ", "") for x in (tbl.get("fields") or [])]
    need = {"date": "日期", "shares": "成交仟股", "value": "成交仟元", "open": "開盤", "high": "最高", "low": "最低", "close": "收盤"}
    idx = {k: f.index(v) if v in f else None for k, v in need.items()}
    if any(v is None for v in idx.values()):
        raise ValueError(f"欄位對不上：{f}")
    rows = {}
    for r in data:
        day = _roc(r[idx["date"]])
        if day is None or day[:7].replace("-", "") != month:
            raise ValueError(f"回傳日期 {r[idx['date']]!r} 不在要求的月份 {month}（停抓，不猜）")
        sh, va = _num(r[idx["shares"]]), _num(r[idx["value"]])
        rows[day] = [_num(r[idx["open"]]), _num(r[idx["high"]]), _num(r[idx["low"]]), _num(r[idx["close"]]),
                     sh * 1000 if sh is not None else None, va * 1000 if va is not None else None]
    return "ok", rows


def fetch(code: str, month: str) -> str:
    _rate_limit_wait_or_raise("tpex_www")
    r = requests.get(URL, params={"code": code, "date": f"{month[:4]}/{month[4:]}/01", "response": "json"},
                     headers=UA, timeout=30)
    if r.status_code in BLOCK:
        _rate_limit_record_block("tpex_www", r.status_code)
        raise RuntimeError(f"HTTP {r.status_code}，封鎖 2 小時、停抓")
    r.raise_for_status()
    status, rows = parse(code, month, r.json())
    p = cache_path(code, month)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"code": code, "month": month, "status": status, "rows": rows},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)
    return status


def cross_check() -> dict:
    """零請求：已抓的逐檔快取與 FinMind 本機快取重疊日比對收盤（差 >0.5% 計為不一致）。"""
    import pandas as pd

    import finmind_client as F
    import var1018_v1_prep as V
    n_cmp = n_bad = 0
    bad = []
    for d in sorted(OUT.glob("*")):
        code = d.name
        if not V.cached("TaiwanStockPrice", code):
            continue
        fm = F.load_dev("TaiwanStockPrice", code, V.FETCH_START, V.FETCH_END)
        if fm.empty:
            continue
        fmc = dict(zip(pd.to_datetime(fm["date"]).dt.strftime("%Y-%m-%d"), fm["close"]))
        for p in d.glob("*.json"):
            for day, row in (json.loads(p.read_text(encoding="utf-8")).get("rows") or {}).items():
                if row[3] is None or day not in fmc or not fmc[day]:
                    continue
                n_cmp += 1
                if abs(row[3] / float(fmc[day]) - 1) > 0.005:
                    n_bad += 1
                    bad.append((code, day, row[3], float(fmc[day])))
    return {"n_compared": n_cmp, "n_diff_gt_0.5pct": n_bad, "examples": bad[:10]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until")
    ap.add_argument("--max-req", type=int, default=10**9)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--check", action="store_true", help="零請求：與 FinMind 重疊日核對收盤")
    a = ap.parse_args()
    if a.check:
        print(json.dumps(cross_check(), ensure_ascii=False, indent=1))
        return 0
    fixed, probe = plan()
    todo = [x for x in fixed if not cache_path(*x).exists()]
    for c in probe:  # B 類：2007-01 有資料才補 02～06
        p = cache_path(c, "200701")
        if not p.exists():
            todo.append((c, "200701"))
        elif json.loads(p.read_text(encoding="utf-8"))["status"] == "ok":
            todo += [(c, m) for m in MONTHS[2:] if not cache_path(c, m).exists()]
    print(f"A 類 {len(fixed)} 個（代號×月）、B 類探測 {len(probe)} 檔；本次待抓 {len(todo)}（B 類後續月份要等 2007-01 探到才列入）")
    if a.plan:
        return 0
    n = 0
    for code, month in todo:
        if n >= a.max_req or (a.until and datetime.now().strftime("%H:%M") >= a.until):
            print(f"到上限／時間，停在 {code} {month}")
            break
        try:
            st = fetch(code, month)
        except Exception as e:  # noqa: BLE001
            print(f"停抓：{code} {month}：{e}")
            break
        n += 1
        if n % 25 == 0 or n <= 3:
            print(f"  已送 {n} 次；{code} {month} {st}")
    print(f"本次送出 {n} 次")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
