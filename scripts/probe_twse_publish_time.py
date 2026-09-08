# -*- coding: utf-8 -*-
"""實測 TWSE 各端點的實際發布時間（排程一.1，2026-09-08）。

**為什麼需要這支**：`market.yml` 的台股班次訂在台北 **14:10**，
但實測 2026-09-08 **15:05** 打 T86 與 MI_MARGN 仍回
`stat='很抱歉，沒有符合條件的資料'`、`total=0`——**證交所根本還沒發布**。

也就是說我們每天都在資料發布**之前**去抓，抓不到，然後在 App 上顯示
「資料過舊」——**把證交所還沒發布這件事，講成我們自己故障**。
使用者看到的是我們壞了，實際上是我們排錯時間又用錯文案怪自己。

**總司令裁示：不要用推測，連續三個交易日實測，記錄最早取得成功資料的時刻。**
這支就是那個實測工具：每次執行探測一輪、把結果 append 進 JSONL，
之後用 `--report` 直接算出各端點每日最早成功時間。

排程建議：交易日 13:30~20:00 每 15 分鐘跑一次（`AlphaTwsePublishProbe`）。
探測本身很輕（3 個請求），且**只讀公開端點、不改任何資料**。

用法：
    python scripts/probe_twse_publish_time.py            # 探測一輪
    python scripts/probe_twse_publish_time.py --report   # 彙整已收集的資料
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "research" / "twse_publish_probe.jsonl"
TZ = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0"}


def endpoints(d: str) -> list[tuple[str, str]]:
    return [
        ("T86", f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALL&response=json"),
        ("MI_MARGN", f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d}&selectType=ALL&response=json"),
        ("STOCK_DAY_ALL", "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json"),
    ]


def probe_one(url: str) -> dict:
    """回傳 {ok, rows, stat, note}。**200 不等於有資料**——TWSE 對「還沒發布」
    是回 200 加一句中文 stat，這是 CLAUDE.md 已知地雷的同一形狀。"""
    try:
        r = requests.get(url, timeout=25, headers=UA)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rows": 0, "stat": None, "note": f"{type(e).__name__}"}
    if r.status_code != 200:
        return {"ok": False, "rows": 0, "stat": None, "note": f"HTTP {r.status_code}"}
    try:
        j = r.json()
    except ValueError:
        # STOCK_DAY_ALL 有時回非 JSON（維護中或格式不同），誠實記下來不猜
        return {"ok": False, "rows": 0, "stat": None, "note": "回應非 JSON"}
    if isinstance(j, list):
        return {"ok": len(j) > 0, "rows": len(j), "stat": None, "note": "list 格式"}
    stat = j.get("stat")
    rows = j.get("data") or j.get("aaData") or []
    return {"ok": stat == "OK" and len(rows) > 0, "rows": len(rows),
            "stat": stat, "note": j.get("date") or ""}


def run_probe() -> int:
    now = datetime.now(TZ)
    d = now.strftime("%Y%m%d")
    rec = {"ts": now.isoformat(), "query_date": d, "results": {}}
    print(f"探測 {now.strftime('%Y-%m-%d %H:%M:%S')} 台北｜查詢日 {d}")
    for name, url in endpoints(d):
        r = probe_one(url)
        rec["results"][name] = r
        mark = "✅ 已發布" if r["ok"] else "❌ 尚未發布"
        print(f"  {name:16s} {mark}  筆數={r['rows']}  stat={str(r['stat'])[:24]!r} {r['note']}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0


def report() -> int:
    if not LOG.exists():
        print("尚無探測資料。先跑幾輪 python scripts/probe_twse_publish_time.py")
        return 1
    by_day: dict[str, dict[str, str]] = {}
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        day = r.get("query_date", "")
        hhmm = r["ts"][11:16]
        for name, res in (r.get("results") or {}).items():
            if not res.get("ok"):
                continue
            cur = by_day.setdefault(day, {})
            # 記錄「最早」成功時刻
            if name not in cur or hhmm < cur[name]:
                cur[name] = hhmm
    if not by_day:
        print("已收集探測紀錄，但**還沒有任何一次成功**——代表探測時段都早於發布時間，"
              "或探測還沒跑到發布之後。請讓排程繼續跑。")
        return 0
    print("=" * 60)
    print("  各交易日最早取得成功資料的時刻（台北）")
    print("=" * 60)
    names = sorted({n for v in by_day.values() for n in v})
    print("  日期        " + "".join(f"{n:<17s}" for n in names))
    for day in sorted(by_day):
        row = by_day[day]
        print(f"  {day}    " + "".join(f"{row.get(n, '(未取得)'):<17s}" for n in names))
    print()
    print("  ⚠ 這是**最早探測到**的時刻，不是證交所實際發布的那一秒——")
    print("     真正的發布時間落在「前一次探測」與「這一次」之間，")
    print("     解析度等於探測間隔。要更精確就縮短間隔，但沒有必要：")
    print("     排程只需要訂在穩定晚於發布時間的位置。")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    raise SystemExit(report() if a.report else run_probe())
