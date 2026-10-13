# -*- coding: utf-8 -*-
"""先.八十一-49（2026-10-13）：重算 6/1 以後 price_history 的 adj_close（補上 6～8 月除權息、修正帳本漏調）。

背景：先.八十一-48 用官方逐日收盤把 6/1～7/31 缺日補進 price_history，回補列的 adj_close 是拿「之後最近一筆既有列」的
adj/close 比例推回；除權息帳本（data/ex_dividend_events.json）08-26 起才有紀錄，6～8 月除權息沒有乘進去。
查證時另發現：帳本 08-26 起 161 個已套用事件中有 19 個，price_history 在除息日前的列其實沒有調整（每日管線的錯，
根因另立先.八十一-51），而且同一檔「除息日前的列」有的有調、有的沒調——只看前後兩列補乘會重複乘到已調過的列，
所以改成**整段重算**，不再逐事件補乘。

做法（每檔只動 6/1 以後的列；更早的零星舊列不動，會在每日合併截到 90 筆時被擠掉）：
  目標比例(t) ＝ 最後一列的 adj/close × Π{ 事件 e：t < e 日期 ≤ 最後一列日期 } 係數 e
  adj_close(t) ＝ close(t) × 目標比例(t)
事件來源（係數＝參考價 ÷ 前收，全部是官方數字）：
- 6/1～8/25 除權息：TWSE `rwd/zh/exRight/TWT49U?startDate&endDate`、TPEx `www/zh-tw/bulletin/exDailyQ?startDate&endDate`
  （openapi 的 tpex_exright_daily 只有最新一天）
- 08-26 以後除權息：帳本 events 的 factor_applied
- 減資恢復買賣：帳本 reductions（有 factor_applied 用它；沒有就用 ref_price ÷ pre_close，例 2380 6/29）
每次請求間隔 ≥3 秒，402/403/428/429 立刻停止。用法：python scripts/fix_backfill_exdiv.py [--dry-run]
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PH = ROOT / "data" / "price_history.json"
EXDIV = ROOT / "data" / "ex_dividend_events.json"
START, END = "2026-06-01", "2026-08-25"
TWSE_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
TPEX_URL = "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"}
WATCH = ("0050", "00631L", "00646", "00647L", "00697B")  # 紙上／真錢持有標的：變動要特別回報
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def _roc(s: str) -> str:
    s = s.replace("年", "/").replace("月", "/").replace("日", "").strip()
    y, m, d = [int(x) for x in s.split("/")]
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def _get(url, params):
    r = requests.get(url, params=params, headers=UA, timeout=60)
    if r.status_code in (402, 403, 428, 429):
        raise SystemExit(f"{url} HTTP {r.status_code}，停止（不重試）")
    r.raise_for_status()
    time.sleep(3)
    return r.json()


def official_events() -> list:
    out = []
    j = _get(TWSE_URL, {"startDate": START.replace("-", ""), "endDate": END.replace("-", ""), "response": "json"})
    f = j.get("fields") or []
    i_d, i_c, i_pc, i_ref = f.index("資料日期"), f.index("股票代號"), f.index("除權息前收盤價"), f.index("除權息參考價")
    for row in j.get("data") or []:
        pc, ref = _num(row[i_pc]), _num(row[i_ref])
        if pc and ref:
            out.append({"code": str(row[i_c]).strip(), "date": _roc(row[i_d]), "factor": ref / pc, "src": "TWSE TWT49U"})
    j = _get(TPEX_URL, {"startDate": START.replace("-", "/"), "endDate": END.replace("-", "/"), "response": "json"})
    t = (j.get("tables") or [{}])[0]
    f = t.get("fields") or []
    i_d, i_c, i_pc, i_ref = f.index("除權息日期"), f.index("代號"), f.index("除權息前收盤價"), f.index("除權息參考價")
    for row in t.get("data") or []:
        pc, ref = _num(row[i_pc]), _num(row[i_ref])
        if pc and ref:
            out.append({"code": str(row[i_c]).strip(), "date": _roc(row[i_d]), "factor": ref / pc, "src": "TPEx exDailyQ"})
    return out


def ledger_events() -> list:
    try:
        doc = json.loads(EXDIV.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = [{"code": c, "date": e["ex_date"], "factor": e["factor_applied"], "src": "帳本除權息"}
           for c, lst in (doc.get("events") or {}).items() for e in lst if e.get("factor_applied")]
    for c, lst in (doc.get("reductions") or {}).items():
        for e in lst:
            f = e.get("factor_applied")
            if not f and e.get("ref_price") and e.get("pre_close"):
                f = e["ref_price"] / e["pre_close"]
            if f and e.get("resume_date"):
                out.append({"code": c, "date": e["resume_date"], "factor": f, "src": "帳本減資"})
    return out


def recompute(rows: list, events: list) -> int:
    """回傳改動列數。rows 已依日期排序；只改 START 以後的列。"""
    win = [r for r in rows if r.get("date", "") >= START and r.get("close")]
    if not win:
        return 0
    last = win[-1]
    base = (last.get("adj_close") or last["close"]) / last["close"]
    evs = sorted((e for e in events if START < e["date"] <= last["date"]), key=lambda e: e["date"])
    changed = 0
    for r in win:
        ratio = base
        for e in evs:
            if r["date"] < e["date"]:
                ratio *= e["factor"]
        new = round(r["close"] * ratio, 6)
        old = r.get("adj_close")
        if old is None or abs(new - old) > max(1e-6, abs(old) * 1e-6):
            r["adj_close"] = new
            changed += 1
    return changed


def main(dry: bool) -> int:
    doc = json.loads(PH.read_text(encoding="utf-8"))
    prices = doc.get("prices") or {}
    off, led = official_events(), ledger_events()
    print(f"官方除權息 {len(off)} 筆（{START}～{END}）；帳本事件 {len(led)} 筆（08-26 起除權息＋減資）")
    by = {}
    for e in off + led:
        by.setdefault(e["code"], []).append(e)
    codes_changed, rows_changed, watch = 0, 0, {}
    for code, rows in prices.items():
        rows.sort(key=lambda r: r.get("date", ""))
        before = {r["date"]: r.get("adj_close") for r in rows}
        n = recompute(rows, by.get(code, []))
        if n:
            codes_changed += 1
            rows_changed += n
            if code in WATCH:
                diffs = [abs(r["adj_close"] / before[r["date"]] - 1) for r in rows if before.get(r["date"])]
                watch[code] = {"rows": n, "max_rel_change": round(max(diffs) if diffs else 0, 6)}
    print(f"改動 {codes_changed} 檔、{rows_changed} 列；持有標的變動：{watch or '無'}")
    if dry:
        print("--dry-run：未寫檔")
        return 0
    doc.setdefault("meta", {})["adj_recompute_2026_10_13"] = {
        "note": "先.八十一-49：6/1 以後 adj_close 以最後一列為錨、依官方除權息（TWT49U／exDailyQ，6/1～8/25）＋帳本除權息與減資係數整段重算",
        "official_events": len(off), "ledger_events": len(led), "codes_changed": codes_changed, "rows_changed": rows_changed,
        "holdings_watch": watch}
    PH.write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print("寫檔完成")
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv))
