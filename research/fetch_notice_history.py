"""注意有價證券歷史抓取（先.九十四-5c，來源：research/DATA_GAP_PLAN.md 甲類 #47）。

比照 research/fetch_disposal_history.py（處置股）。只補資料、不登記試驗。官方公開端點、可查日期區間
（2026-10-14 DevQueue 20261014-170102 實測）：
- 上市：www.twse.com.tw/rwd/zh/announcement/notice?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json
- 上櫃：www.tpex.org.tw/www/zh-tw/bulletin/attention?startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&response=json
逐年 1 次請求；同源間隔 ≥3.5 秒；402/403/428/429 或非 JSON 即停（不重試、不換來源）。
官方未公布次數上限（C:\\alpha\\CLAUDE.md TWSE／TPEx 段）。
輸出 research/data/notice_history_{twse,tpex}.json，每年附回應筆數、title；每抓完一年就寫檔（斷點續抓：
已抓過、沒有 error 的年份不重抓）。

用法：python research/fetch_notice_history.py 2000 2024
      python research/fetch_notice_history.py --check-quarters 2020   # 核對單次筆數有無上限（全年 vs 四季合計）
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
_last = {}


def twse_url(a, b):  # a, b = "YYYYMMDD"
    return f"https://www.twse.com.tw/rwd/zh/announcement/notice?startDate={a}&endDate={b}&response=json"


def tpex_url(a, b):
    return (f"https://www.tpex.org.tw/www/zh-tw/bulletin/attention?startDate={a[:4]}/{a[4:6]}/{a[6:]}"
            f"&endDate={b[:4]}/{b[4:6]}/{b[6:]}&response=json")


def parse_twse(d):
    if d.get("stat") != "OK":
        return None, d.get("stat")
    return {"title": d.get("title"), "fields": d.get("fields"), "data": d.get("data") or []}, None


def parse_tpex(d):
    tables = d.get("tables") or []
    if not tables:
        return None, d.get("stat") or "no tables"
    t = tables[0]
    return {"title": t.get("title"), "range": d.get("date"), "fields": t.get("fields"),
            "data": t.get("data") or []}, None


def get(name, url):
    """回 (json 或 None, 停止原因或 None)。"""
    wait = MIN_INTERVAL - (time.time() - _last.get(name, 0))
    if wait > 0:
        time.sleep(wait)
    _last[name] = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=60)
    except requests.RequestException as e:
        return None, f"網路錯誤 {type(e).__name__}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        return r.json(), None
    except ValueError:
        return None, "非 JSON（可能軟性限流）"


SITES = (("twse", twse_url, parse_twse), ("tpex", tpex_url, parse_tpex))


def run_years(years):
    OUT.mkdir(exist_ok=True)
    for name, uf, pf in SITES:
        p = OUT / f"notice_history_{name}.json"
        out = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"source": name, "years": {}}
        out["stopped"] = None
        for y in years:
            if str(y) in out["years"] and "error" not in out["years"][str(y)]:
                continue
            d, stop = get(name, uf(f"{y}0101", f"{y}1231"))
            if stop:
                out["stopped"] = f"{y} {stop}"
                print(name, out["stopped"], flush=True)
                break
            rec, err = pf(d)
            out["years"][str(y)] = rec if rec is not None else {"error": err, "data": []}
            print(name, y, len(out["years"][str(y)]["data"]), (rec or {}).get("title") or err, flush=True)
            out["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")  # 每年落檔＝斷點
        n = sum(len(v.get("data", [])) for v in out["years"].values())
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(out['years'])} 年、{n} 列 → {p.name}；stopped={out['stopped']}", flush=True)
        if out["stopped"] and out["stopped"].split(" ", 1)[1].startswith(tuple(f"HTTP {c}" for c in STOP_CODES)):
            return 1
    return 0


def check_quarters(y):
    """同一年：全年一次 vs 四季分查，比較唯一列數（判斷單次查詢有沒有筆數上限）。"""
    qs = [("0101", "0331"), ("0401", "0630"), ("0701", "0930"), ("1001", "1231")]
    for name, uf, pf in SITES:
        p = OUT / f"notice_history_{name}.json"
        full = json.loads(p.read_text(encoding="utf-8"))["years"][str(y)]["data"]
        # 去掉「編號」流水號與「累計次數」（實測：累計次數是按查詢區間重算的，全年查與分季查同一列數字不同）
        key = lambda row: tuple(str(x) for i, x in enumerate(row) if i not in (0, 3))
        parts = []
        for a, b in qs:
            d, stop = get(name, uf(f"{y}{a}", f"{y}{b}"))
            if stop:
                print(name, "核對中止", stop, flush=True)
                return 1
            rec, err = pf(d)
            parts += (rec or {}).get("data") or []
        s_full, s_q = {key(r) for r in full}, {key(r) for r in parts}
        print(f"{name} {y}: 全年 {len(s_full)} 唯一列、四季合計 {len(s_q)} 唯一列、差集 {len(s_full ^ s_q)}", flush=True)
    return 0


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--check-quarters":
        return check_quarters(int(sys.argv[2]))
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    return run_years(list(range(y0, y1 + 1)))


if __name__ == "__main__":
    sys.exit(main())
