# -*- coding: utf-8 -*-
"""先.一一九-4／先.一〇二-2b：第一批 6 支「不論登入與否都執行」排程，逐交易日核對有沒有正常跑（只讀，不改任何排程）。

每支看三件事：排程器 LastTaskResult（只有最後一次）、心跳／日誌（當天有沒有跑、結果）、資料落地（當天產出檔）。
用法：python scripts/check_password_batch1.py 2026-10-16 2026-10-19 2026-10-20
自己失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

APP = Path(__file__).resolve().parent.parent
ALPHA = APP.parent
TASKS = ["AlphaMarketCatchup", "AlphaMarketCatchupLate", "AlphaData", "AlphaQuotesFallback", "AlphaWarrantSnapshot", "AlphaDevQueue"]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def task_info() -> dict:
    ps = ("Get-ScheduledTask -TaskName " + ",".join(TASKS) + " | ForEach-Object { $i = Get-ScheduledTaskInfo $_; "
          "[pscustomobject]@{n=$_.TaskName; logon=[string]$_.Principal.LogonType; last=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm'); rc=$i.LastTaskResult} } | ConvertTo-Json")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        rows = json.loads(r.stdout)
        return {x["n"]: x for x in (rows if isinstance(rows, list) else [rows])}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::讀排程資訊失敗：{type(e).__name__}: {e}")
        return {}


def jsonl(p: Path) -> list:
    out = []
    for l in _read(p).splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def check_day(d: str) -> dict:
    res = {}
    cu = [e for e in jsonl(APP / "research" / "market_local_catchup.jsonl") if e.get("date") == d]
    early = [e for e in cu if e.get("ts", "")[11:16] < "19:00"]
    late = [e for e in cu if e.get("ts", "")[11:16] >= "19:00"]
    landed = any((e.get("market_tw_data_date_after") or e.get("market_tw_data_date")) == d for e in cu)
    res["AlphaMarketCatchup"] = {"ok": bool(early) and landed, "evidence": f"17:30 班 {len(early)} 筆；當天 market_tw 落地={landed}"}
    res["AlphaMarketCatchupLate"] = {"ok": bool(late), "evidence": f"19:30 班 {len(late)} 筆" + (f"，殘缺 {late[-1].get('gaps')}" if late and late[-1].get("gaps") else "")}
    log = _read(ALPHA / "alpha-data" / "run.log")
    m = re.search(r"=== Alpha Data 每日抓取 · " + d + r" ===(.*?)(?==== Alpha Data 每日抓取 · |\Z)", log, re.S)
    body = m.group(1) if m else ""
    res["AlphaData"] = {"ok": bool(m) and "=== 完成" in body,
                        "evidence": ("有當天段落" if m else "沒有當天段落") + ("、有「完成」" if "=== 完成" in body else "") +
                                    (f"、失敗 {body.count('失敗')} 處" if "失敗" in body else "")}
    qf = [e for e in jsonl(APP / "research" / "quotes_local_fallback.jsonl") if str(e.get("ts", ""))[:10] == d]
    res["AlphaQuotesFallback"] = {"ok": len(qf) >= 20, "evidence": f"心跳 {len(qf)} 筆（09:05～13:45 每 10 分鐘約 29 筆）"}
    wl = _read(APP / "research" / "data" / "warrant_snapshot_cycle.log")
    seg = wl.split(f"===== warrant_snapshot launcher: {d} ")
    # 同一天重跑過（例：10/20 17:30 來源斷線、19:33 補抓成功）以當天最後一次為準
    wseg = seg[-1].split("===== warrant_snapshot launcher:")[0] if len(seg) > 1 else ""
    has_dir = (APP / "research" / "data" / "warrant_snapshots" / d).exists()
    rc = re.search(r"warrant_snapshot\.py exit=(\d+)", wseg)
    res["AlphaWarrantSnapshot"] = {"ok": has_dir and bool(rc) and rc.group(1) == "0",
                                   "evidence": ("有啟動紀錄" if wseg else "沒有啟動紀錄") + (f"、程式 exit={rc.group(1)}" if rc else "") +
                                               f"、快照資料夾{'有' if has_dir else '沒有'}" +
                                               ("（來源連線被中斷）" if "ConnectionResetError" in wseg or "ChunkedEncodingError" in wseg else "")}
    dq = re.findall(r"DevQueue cycle end: " + d + r" (\d\d:\d\d):\d\d cycle_id=(\S+) reason=(\S+) exit=(-?\d+)", _read(APP / "research" / "dev_queue_cycle.log"))
    bad = [x for x in dq if x[3] != "0"]
    # exit≠0 若是 claude 用量上限（429 usage_limit_reached），屬帳號額度、不是排程身分問題，分開算
    quota = [x for x in bad if "usage_limit_reached" in _read(APP / "research" / "data" / "dev_cycles" / f"{x[1]}.jsonl")]
    other = [x for x in bad if x not in quota]
    res["AlphaDevQueue"] = {"ok": bool(dq) and not other,
                            "evidence": f"當天結束 {len(dq)} 輪，exit≠0 {len(bad)} 輪（其中用量上限 429 {len(quota)} 輪，排程照常啟動）"
                                        + (f"；其他錯誤 {[(x[0], x[1]) for x in other[:3]]}" if other else "")}
    return res


def main(argv: list[str]) -> int:
    try:
        days = argv or []
        info = task_info()
        out = {"tasks": info, "days": {d: check_day(d) for d in days}}
        for n in TASKS:
            i = info.get(n, {})
            print(f"{n}（{i.get('logon', '?')}，最後 {i.get('last', '?')} rc={i.get('rc', '?')}）")
            for d in days:
                r = out["days"][d][n]
                print(f"  {d} {'OK ' if r['ok'] else 'NG '} {r['evidence']}")
        print(json.dumps({d: all(v["ok"] for v in r.values()) for d, r in out["days"].items()}, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::check_password_batch1 自身失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
