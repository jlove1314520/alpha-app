# -*- coding: utf-8 -*-
"""先.八十-9（2026-10-12）：data/price_history.json 全市場缺日補齊。

問題：2026-08-03～08-25 每天只有約 617 檔（當初一次性回補只涵蓋部分股票），9/1、9/7、9/10、9/14、9/15
只有約 1,100～1,500 檔（某一個交易所那天沒抓到）。正常一天約 2,400 檔。

做法（只用官方公開端點，照既有節流）：
- 交易日以 research/data/auto_trading/calendar_{年}.json（官方休市日）為準；只看 START 之後、檔案最後日期以前的開市日。
- 某天檔數 < 全期中位數 × 90% 視為缺日，同時向兩個交易所要那天全市場收盤：
  上市 TWSE rwd MI_INDEX（type=ALLBUT0999，沿用 update_price_history.fetch_twse_rwd，含表頭日期核對）；
  上櫃 TPEx afterTrading/otc（type=EW，上櫃股票每日收盤行情）。
- 只補「price_history 已有的代號、且那天沒有資料」的列，絕不覆蓋既有列、不新增代號。
- 還原收盤 adj_close：取該檔「之後最近一筆既有列」的 adj_close/close 係數，再乘上兩日之間已入帳除權息事件
  （data/ex_dividend_events.json 的 factor_applied）。已知限制：該帳本自 08-26 起才有紀錄，
  ex_date 落在 08-03～08-25 的除權息不在帳本裡，那段期間更早日期的 adj_close 可能少乘一次係數（close 本身正確）。
- 每次請求間隔 ≥3 秒；遇 402/403/428/429 立刻停止（不重試、不換來源），已補的照樣寫檔。
用法：python scripts/backfill_price_history_gaps.py [--dry-run] [--all]（排程每輪最多補 10 天；--all 一次補完，僅互動視窗手動用）
"""
import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[0] / "scripts"))
import price_history_store as PHS  # noqa: E402
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import update_price_history as U  # noqa: E402

PH = ROOT / "data" / "price_history.json"
EXDIV = ROOT / "data" / "ex_dividend_events.json"
START = "2026-06-01"  # 先.八十一-48：由 08-03 往前延到 06-01，涵蓋 90 筆視窗（技術面 60 日計算要連續）
RATIO = 0.9
TPEX_OTC_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"
BLOCK = (402, 403, 428, 429)
MAX_DAYS_PER_RUN = 10  # 排程每輪最多補 10 個缺日（每日 2 個請求），其餘下輪續補，避免大洞一次打太多官方端點


CAL_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear={y}"
_CAL_MEMO: dict = {}


def closed_days(year: int) -> set:
    """官方休市日。優先讀本機快取（research/data/auto_trading/calendar_{年}.json，自動交易引擎維護、不進 repo）；
    雲端沒有快取時改問 TWSE 官方「市場開休市日期」（同一個端點、同一條判定：名稱含開始／最後交易日者為交易日，其餘列出者休市）。"""
    if year in _CAL_MEMO:
        return _CAL_MEMO[year]
    p = ROOT / "research" / "data" / "auto_trading" / f"calendar_{year}.json"
    try:
        out = set(json.loads(p.read_text(encoding="utf-8")).get("closed") or [])
    except (OSError, ValueError):
        r = requests.get(CAL_URL.format(y=year), timeout=20)
        r.raise_for_status()
        doc = r.json()
        if doc.get("stat") != "ok" or not doc.get("data"):
            raise RuntimeError("TWSE holidaySchedule 回傳異常")
        out = {row[0] for row in doc["data"] if not ("開始交易日" in row[1] or "最後交易日" in row[1])}
    # 先.八十一-48：併入 data/trading_calendar.json 的臨時停市日（颱風等，事前休市表沒列；例 2026-07-10）
    try:
        tc = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
        out = set(out) | set(((tc.get("tw") or {}).get(str(year)) or {}).get("unscheduled_closed") or [])
    except (OSError, ValueError):
        pass
    _CAL_MEMO[year] = out
    return out


def open_days(start: str, end: str) -> list:
    closed = closed_days(int(start[:4])) | closed_days(int(end[:4]))
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5 and d.isoformat() not in closed:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def day_counts(prices: dict) -> dict:
    c = {}
    for rows in prices.values():
        for r in rows:
            if r.get("date", "") >= START:
                c[r["date"]] = c.get(r["date"], 0) + 1
    return c


def find_gaps(prices: dict) -> tuple[list, dict, float]:
    counts = day_counts(prices)
    last = max(counts) if counts else START
    days = open_days(START, last)
    med = statistics.median([counts.get(d, 0) for d in days]) if days else 0
    return [d for d in days if counts.get(d, 0) < med * RATIO], counts, med


_last_req = [0.0]


def _get(url, params):
    wait = U.RATE_LIMIT_MIN_INTERVAL_SEC - (time.time() - _last_req[0])
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()
    r = requests.get(url, params=params, timeout=30)
    if r.status_code in BLOCK:
        raise PermissionError(f"HTTP {r.status_code}")
    r.raise_for_status()
    return r


def fetch_tpex_day(d: str) -> dict | None:
    r = _get(TPEX_OTC_URL, {"date": d.replace("-", "/"), "type": "EW", "response": "json"})
    body = r.json()
    if body.get("stat") not in ("ok", "OK"):
        return None
    t = (body.get("tables") or [{}])[0]
    fields = [f.strip() for f in t.get("fields") or []]
    data = t.get("data") or []
    if not data:
        return None
    rd = str(body.get("date") or "")
    if rd and rd.replace("/", "-") != d and rd != d.replace("-", ""):
        raise RuntimeError(f"TPEx 回傳日期 {rd} 與請求 {d} 不符")

    def ix(name):
        if name not in fields:
            raise RuntimeError(f"TPEx 欄位缺「{name}」：{fields}")
        return fields.index(name)

    i_code, i_close, i_open, i_high, i_low = ix("代號"), ix("收盤"), ix("開盤"), ix("最高"), ix("最低")
    i_vol = ix("成交股數")
    i_val = next(i for i, f in enumerate(fields) if f.startswith("成交金額"))
    out = {}
    for row in data:
        code, close = str(row[i_code]).strip(), U._num(row[i_close])
        if not code or close is None:
            continue
        out[code] = {"date": d, "open": U._num(row[i_open]), "high": U._num(row[i_high]), "low": U._num(row[i_low]),
                     "close": close, "adj_close": close, "volume": U._num(row[i_vol]), "turnover": U._num(row[i_val])}
    return out


def adj_factor(rows: list, d: str, events: list) -> float:
    nxt = next((r for r in rows if r["date"] > d and r.get("close")), None)
    if not nxt:
        return 1.0
    f = (nxt.get("adj_close") or nxt["close"]) / nxt["close"]
    for ev in events or []:
        if ev.get("applied") and ev.get("factor_applied") and d < ev["ex_date"] <= nxt["date"]:
            f *= ev["factor_applied"]
    return f


def main(dry: bool) -> int:
    doc = PHS.load(PH)
    prices = doc["prices"]
    gaps, counts, med = find_gaps(prices)
    print(f"開市日中位數 {med:.0f} 檔；缺日（<{RATIO:.0%}）：{[(d, counts.get(d, 0)) for d in gaps]}")
    if dry or not gaps:
        return 0
    if len(gaps) > MAX_DAYS_PER_RUN and '--all' not in sys.argv:
        print(f"缺日 {len(gaps)} 天，本輪只補前 {MAX_DAYS_PER_RUN} 天（--all 可一次補完）")
        gaps = gaps[:MAX_DAYS_PER_RUN]
    try:
        exdiv = json.loads(EXDIV.read_text(encoding="utf-8")).get("events") or {}
    except (OSError, ValueError):
        exdiv = {}
    added, errors = 0, []
    for d in gaps:
        for name, fn in (("TWSE", lambda d=d: U.fetch_twse_rwd(d)), ("TPEx", lambda d=d: fetch_tpex_day(d))):
            try:
                if name == "TWSE":
                    w = U.RATE_LIMIT_MIN_INTERVAL_SEC - (time.time() - _last_req[0])
                    if w > 0:
                        time.sleep(w)
                    _last_req[0] = time.time()
                rows = fn()
            except PermissionError as e:
                errors.append(f"{name} {d} 被限流（{e}），停止本輪")
                print(errors[-1])
                return finish(doc, added, errors, gaps)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name} {d}：{type(e).__name__}: {e}")
                print("[warn]", errors[-1])
                continue
            if not rows:
                print(f"{name} {d}：無資料")
                continue
            n = 0
            for code, row in rows.items():
                cur = prices.get(code)
                if not cur or any(r.get("date") == d for r in cur):
                    continue
                cur.sort(key=lambda r: r["date"])
                row = dict(row)
                row["adj_close"] = round(row["close"] * adj_factor(cur, d, exdiv.get(code)), 4)
                cur.append(row)
                cur.sort(key=lambda r: r["date"])
                n += 1
            added += n
            print(f"{name} {d}：官方 {len(rows)} 檔，補入 {n} 列")
    return finish(doc, added, errors, gaps)


def finish(doc, added, errors, gaps) -> int:
    doc.setdefault("meta", {})["gap_backfill_2026_10_12"] = {
        "note": "先.八十-9 全市場缺日補齊：TWSE MI_INDEX＋TPEx afterTrading/otc 官方逐日收盤，只補缺的（代號,日期），不覆蓋既有列；"
                "adj_close 以後一筆既有列係數×其間已入帳除權息係數推回（08-03～08-25 期間除權息不在帳本，可能少乘一次）",
        "days": gaps, "rows_added": added, "errors": errors}
    PHS.save(doc, PH)  # 與 update_price_history.py 相同格式（先.八十二-1 拆檔）
    print(f"寫檔完成：補入 {added} 列；錯誤 {len(errors)} 筆")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
