# -*- coding: utf-8 -*-
"""實測 TWSE 各端點的實際發布時間（排程一.1，2026-09-08；2026-09-17補測正確端點）。

**為什麼需要這支**：`market.yml` 的台股班次訂在台北 **14:10**，
但實測 2026-09-08 **15:05** 打 T86 與 MI_MARGN 仍回
`stat='很抱歉，沒有符合條件的資料'`、`total=0`——**證交所根本還沒發布**。

也就是說我們每天都在資料發布**之前**去抓，抓不到，然後在 App 上顯示
「資料過舊」——**把證交所還沒發布這件事，講成我們自己故障**。
使用者看到的是我們壞了，實際上是我們排錯時間又用錯文案怪自己。

**總司令裁示：不要用推測，連續三個交易日實測，記錄最早取得成功資料的時刻。**
這支就是那個實測工具：每次執行探測一輪、把結果 append 進 JSONL，
之後用 `--report` 直接算出各端點每日最早成功時間。

**2026-09-17（總司令裁示【稽核.四.2】量清楚，不要猜）補測：這支原本探測
的`www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL`，跟`update_price_
history.py`實際使用的`openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`
是不同主機——43輪探測全部白做，量的是我們沒在用的那個端點。已補上
`STOCK_DAY_ALL_OPENAPI`探測管線實際使用的那一支，舊的`STOCK_DAY_ALL`
（www.twse.com.tw版本）保留做對照，不刪除。openapi版本回傳格式不是
`{stat,data}`信封，是純list，且每一列自帶`Date`欄位（民國年7位數字，
跟`update_price_history.py::_roc_date_to_iso()`同一種格式）——這支腳本
要量的不是「HTTP成功與否」（openapi版本結構上幾乎永遠回200+list，只是
Date欄位的值可能還停在前一個交易日），是**payload裡Date欄位的實際值
什麼時候真的翻到當天**，所以每輪額外記錄`payload_date`（openapi版本
從第一筆的Date欄位算出；舊版本沒有對應欄位，維持None，不硬湊）。**排程
視窗也依裁示改為交易日15:00~隔日10:00每30分鐘一輪，連測三個交易日**
（原本13:30~20:00只有6.5小時、15分鐘一輪，涵蓋不到「23:10仍是前一天」
這個實測發現的時段）——這個排程視窗異動本身也需要修改既有的
`AlphaTwsePublishProbe`排程工作，跟2026-09-17新增`AlphaIbkrGateway`那次
一樣，本session的PowerShell環境沒有Task Scheduler寫入權限，待總司令
親自執行，見`docs/LOCAL_SCHEDULED_TASKS.md`。

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


def _roc_date_to_iso(s) -> str | None:
    """跟 .github/scripts/update_price_history.py::_roc_date_to_iso() 同一種
    格式（民國年7位數字），這裡獨立複製一份（既有慣例：跨檔案不 import，
    避免探測工具依賴管線腳本、管線腳本改了連帶影響探測結果的準確性）。"""
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def endpoints(d: str) -> list[tuple[str, str, str]]:
    """(name, url, kind)。kind 決定 probe_one() 怎麼解析回應：
    "envelope" = www.twse.com.tw 那種 {stat, data} 包法；
    "list" = openapi.twse.com.tw 那種直接回一個 list，且每列自帶 Date 欄位。
    """
    return [
        ("T86", f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALL&response=json", "envelope"),
        ("MI_MARGN", f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d}&selectType=ALL&response=json", "envelope"),
        ("STOCK_DAY_ALL", "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json", "envelope"),
        # 2026-09-17（總司令裁示【稽核.四.2】）：管線（update_price_history.py::
        # fetch_twse()）實際使用的端點，前三個探測的都是「另一個主機」，這一個
        # 才是真正要量的。
        ("STOCK_DAY_ALL_OPENAPI", "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", "list"),
    ]


def probe_one(url: str, kind: str) -> dict:
    """回傳 {ok, rows, stat, note, payload_date}。**200 不等於有資料**——TWSE
    對「還沒發布」是回 200 加一句中文 stat，這是 CLAUDE.md 已知地雷的同一形狀；
    openapi 版本更隱蔽：結構上幾乎永遠回 200+非空 list，`ok` 看不出發布與否，
    真正該看的是 `payload_date`（見檔頭 2026-09-17 補記）。"""
    try:
        r = requests.get(url, timeout=25, headers=UA)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rows": 0, "stat": None, "note": f"{type(e).__name__}", "payload_date": None}
    if r.status_code != 200:
        return {"ok": False, "rows": 0, "stat": None, "note": f"HTTP {r.status_code}", "payload_date": None}
    try:
        j = r.json()
    except ValueError:
        # STOCK_DAY_ALL 有時回非 JSON（維護中或格式不同），誠實記下來不猜
        return {"ok": False, "rows": 0, "stat": None, "note": "回應非 JSON", "payload_date": None}
    if kind == "list":
        rows = j if isinstance(j, list) else []
        payload_date = _roc_date_to_iso(rows[0].get("Date")) if rows and isinstance(rows[0], dict) else None
        return {"ok": len(rows) > 0, "rows": len(rows), "stat": None,
                "note": "list 格式", "payload_date": payload_date}
    if isinstance(j, list):
        return {"ok": len(j) > 0, "rows": len(j), "stat": None, "note": "list 格式", "payload_date": None}
    stat = j.get("stat")
    rows = j.get("data") or j.get("aaData") or []
    return {"ok": stat == "OK" and len(rows) > 0, "rows": len(rows),
            "stat": stat, "note": j.get("date") or "", "payload_date": None}


def run_probe() -> int:
    now = datetime.now(TZ)
    d = now.strftime("%Y%m%d")
    rec = {"ts": now.isoformat(), "query_date": d, "results": {}}
    print(f"探測 {now.strftime('%Y-%m-%d %H:%M:%S')} 台北｜查詢日 {d}")
    for name, url, kind in endpoints(d):
        r = probe_one(url, kind)
        rec["results"][name] = r
        mark = "✅ 已發布" if r["ok"] else "❌ 尚未發布"
        pd = f"  payload_date={r['payload_date']}" if r.get("payload_date") else ""
        print(f"  {name:20s} {mark}  筆數={r['rows']}  stat={str(r['stat'])[:24]!r} {r['note']}{pd}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0


def report() -> int:
    if not LOG.exists():
        print("尚無探測資料。先跑幾輪 python scripts/probe_twse_publish_time.py")
        return 1
    by_day: dict[str, dict[str, str]] = {}
    # 2026-09-17（總司令裁示【稽核.四.2】）：openapi版本結構上幾乎永遠ok=True，
    # 真正要量的是payload_date什麼時候「追上」query_date（探測當下的日期）——
    # 這裡另外算一份「每個查詢日，payload_date第一次等於query_date的時刻」，
    # 跟舊的「第一次ok=True」分開報告，不要混在一起。
    openapi_catchup: dict[str, str] = {}
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        day = r.get("query_date", "")
        hhmm = r["ts"][11:16]
        for name, res in (r.get("results") or {}).items():
            if res.get("ok"):
                cur = by_day.setdefault(day, {})
                # 記錄「最早」成功時刻
                if name not in cur or hhmm < cur[name]:
                    cur[name] = hhmm
            if name == "STOCK_DAY_ALL_OPENAPI":
                pd = res.get("payload_date")
                q_iso = f"{day[:4]}-{day[4:6]}-{day[6:]}" if len(day) == 8 else None
                if pd and q_iso and pd == q_iso:
                    if day not in openapi_catchup or hhmm < openapi_catchup[day]:
                        openapi_catchup[day] = hhmm
    if not by_day and not openapi_catchup:
        print("已收集探測紀錄，但**還沒有任何一次成功**——代表探測時段都早於發布時間，"
              "或探測還沒跑到發布之後。請讓排程繼續跑。")
        return 0
    print("=" * 60)
    print("  各交易日最早取得成功資料的時刻（台北）")
    print("=" * 60)
    names = sorted({n for v in by_day.values() for n in v})
    col_w = max(24, max((len(n) for n in names), default=0) + 2)
    print("  日期        " + "".join(f"{n:<{col_w}s}" for n in names))
    for day in sorted(by_day):
        row = by_day[day]
        print(f"  {day}    " + "".join(f"{row.get(n, '(未取得)'):<{col_w}s}" for n in names))
    print()
    print("  ⚠ 這是**最早探測到 ok=True** 的時刻，不是證交所實際發布的那一秒——")
    print("     真正的發布時間落在「前一次探測」與「這一次」之間，")
    print("     解析度等於探測間隔。")
    print()
    print("=" * 60)
    print("  STOCK_DAY_ALL_OPENAPI（管線實際使用的端點）：payload_date")
    print("  第一次「追上」查詢當天日期的時刻（這才是真正的發布時間指標）")
    print("=" * 60)
    if not openapi_catchup:
        print("  尚未觀察到payload_date追上查詢日的任何一筆——目前累積的樣本"
              "都還停在「payload_date < 查詢日」，繼續讓排程跑。")
    else:
        for day in sorted(openapi_catchup):
            print(f"  {day}    {openapi_catchup[day]}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    raise SystemExit(report() if a.report else run_probe())
