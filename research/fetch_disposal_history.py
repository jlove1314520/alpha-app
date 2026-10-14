"""處置有價證券歷史抓取（先.八十六-1a，來源：research/DATA_GAP_PLAN.md 2.12）。

只補資料、不登記試驗。官方公開端點、可查日期區間：
- 上市：www.twse.com.tw/rwd/zh/announcement/punish?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json
- 上櫃：www.tpex.org.tw/www/zh-tw/bulletin/disposal?startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&response=json
逐年 1 次請求；同源間隔 ≥3.5 秒；402/403/428/429 或非 JSON 即停（不重試、不換來源）。
官方未公布次數上限（C:\\alpha\\CLAUDE.md TWSE／TPEx 段）。
輸出 research/data/disposal_history_{twse,tpex}.json，每年附回應筆數、title，供核對。
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent / "data"
UA = {"User-Agent": "alpha-research (contact: research@example.invalid)"}
MIN_INTERVAL = 3.5
STOP_CODES = {402, 403, 428, 429}


def twse_url(y):
    return (f"https://www.twse.com.tw/rwd/zh/announcement/punish?startDate={y}0101"
            f"&endDate={y}1231&response=json")


def tpex_url(y):
    return (f"https://www.tpex.org.tw/www/zh-tw/bulletin/disposal?startDate={y}/01/01"
            f"&endDate={y}/12/31&response=json")


def parse_twse(d):
    if d.get("stat") != "OK":
        return None, d.get("stat")
    return {"title": d.get("title"), "fields": d.get("fields"), "data": d.get("data") or []}, None


def parse_tpex(d):
    tables = d.get("tables") or []
    if not tables:
        return None, d.get("stat") or "no tables"
    t = tables[0]
    return {"title": t.get("title2") or t.get("title"), "subtitle": t.get("subtitle"),
            "fields": t.get("fields"), "data": t.get("data") or []}, None


def run(name, url_fn, parse_fn, years):
    out = {"source": name, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "years": {}, "stopped": None}
    for y in years:
        url = url_fn(y)
        try:
            r = requests.get(url, headers=UA, timeout=30)
        except requests.RequestException as e:
            out["stopped"] = f"{y} 網路錯誤 {type(e).__name__}"
            print(name, out["stopped"])
            break
        if r.status_code in STOP_CODES or r.status_code != 200:
            out["stopped"] = f"{y} HTTP {r.status_code}"
            print(name, out["stopped"])
            break
        try:
            d = r.json()
        except ValueError:
            out["stopped"] = f"{y} 非 JSON（可能軟性限流）"
            print(name, out["stopped"])
            break
        rec, err = parse_fn(d)
        if rec is None:
            out["years"][str(y)] = {"error": err, "data": []}
            print(name, y, "無資料", err)
        else:
            out["years"][str(y)] = rec
            print(name, y, len(rec["data"]), rec.get("title"))
        time.sleep(MIN_INTERVAL)
    return out


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    years = list(range(y0, y1 + 1))
    OUT.mkdir(exist_ok=True)
    for name, uf, pf in (("twse", twse_url, parse_twse), ("tpex", tpex_url, parse_tpex)):
        res = run(name, uf, pf, years)
        p = OUT / f"disposal_history_{name}.json"
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(len(v.get("data", [])) for v in res["years"].values())
        print(f"{name}: {len(res['years'])} 年、{n} 筆 → {p.name}；stopped={res['stopped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
