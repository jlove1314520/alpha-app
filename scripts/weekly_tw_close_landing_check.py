# -*- coding: utf-8 -*-
"""先.一四一-2：每週一核對上週每個台股交易日的收盤資料是否「當晚」落地，有漏就推播（零外部資料請求，只讀 git）。

「收盤資料」＝下面兩個檔，兩個都落地才算該日落地（落地時間取兩者較晚那個）：
  1. data/market_tw.json 的 `data_date`（market.yml 台股收盤輸出：大盤／類股／法人）
  2. data/price_history/_meta.json 的 `meta.twse_latest_check.actual_0050_last_date`
     （update_price_history.py 寫的全市場日K最新日期，以 0050 為代表）
做法：`git log origin/main` 由舊到新逐版讀出上述日期欄，某交易日 D 的「首次落地」＝第一個日期欄 ≥ D 的 commit（committer 時間）。
判定：台北時間 D 當天 23:59 前落地＝OK；之後才落地＝LATE；至今沒落地＝MISSING。休市日（trading_calendar.json
`closed`＋`unscheduled_closed`）與週末不算。

結果一週一行 append 到 research/data/weekly_tw_close_landing.jsonl；有 LATE／MISSING 就推播一則（scripts/cc_push._send，
類別 cc_stuck）。只在台北週一 09:00 後、且本週還沒跑過才執行（狀態 research/.weekly_tw_close_landing_state.json）。
掛在本機 run-connectivity-check.ps1（AlphaConnectivity 每 5 分鐘）裡，不新建排程。
用法：python scripts/weekly_tw_close_landing_check.py [--force] [--week YYYY-MM-DD(該週週一)] [--no-push]
十二節：任何例外只印警告、exit 0。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 —— 主控台不支援時照舊輸出
        pass

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
CAL = ROOT / "data" / "trading_calendar.json"
OUT = ROOT / "research" / "data" / "weekly_tw_close_landing.jsonl"
STATE = ROOT / "research" / ".weekly_tw_close_landing_state.json"
FILES = {
    "data/market_tw.json": lambda d: d.get("data_date"),
    "data/price_history/_meta.json": lambda d: ((d.get("meta") or {}).get("twse_latest_check") or {}).get("actual_0050_last_date"),
}
RANK = {"OK": 0, "LATE": 1, "MISSING": 2}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8", "replace")


def closed_days(cal: dict) -> set:
    out = set()
    for y in (cal.get("tw") or {}).values():
        out |= set(y.get("closed") or []) | set(y.get("unscheduled_closed") or [])
    return out


def week_trading_days(monday: date, closed: set) -> list[str]:
    return [(monday + timedelta(days=i)).isoformat() for i in range(5) if (monday + timedelta(days=i)).isoformat() not in closed]


def versions(path: str, since: date, extract) -> list[tuple[datetime, str]]:
    """[(committer 時間, 日期欄)]，由舊到新；讀不到的版本略過。"""
    out = []
    log = _git("log", "origin/main", "--reverse", "--format=%H\t%cI", f"--since={since.isoformat()}", "--", path)
    for line in log.splitlines():
        sha, _, ts = line.partition("\t")
        try:
            v = extract(json.loads(_git("show", f"{sha}:{path}")))
            if v:
                out.append((datetime.fromisoformat(ts), str(v)[:10]))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {sha[:10]} {path} 讀不到：{e!r}")
    return out


def first_landing(day: str, vers: list[tuple[datetime, str]]) -> datetime | None:
    for ts, v in vers:
        if v >= day:
            return ts
    return None


def classify(day: str, ts: datetime | None) -> str:
    if ts is None:
        return "MISSING"
    return "OK" if ts.astimezone(TW).date().isoformat() <= day else "LATE"


def evaluate(days: list[str], vers_by_file: dict) -> list[dict]:
    rows = []
    for d in days:
        per = {}
        for f, vers in vers_by_file.items():
            ts = first_landing(d, vers)
            per[f] = {"landed_at": ts.astimezone(TW).isoformat(timespec="minutes") if ts else None, "status": classify(d, ts)}
        status = max((p["status"] for p in per.values()), key=RANK.get) if per else "MISSING"
        rows.append({"date": d, "status": status, "files": per})
    return rows


def last_monday(now: datetime) -> date:
    return now.astimezone(TW).date() - timedelta(days=now.astimezone(TW).weekday() + 7)


def run(now: datetime, monday: date | None = None, force: bool = False, push: bool = True) -> dict:
    tw_now = now.astimezone(TW)
    week_key = tw_now.date().isocalendar()
    week_key = f"{week_key[0]}-W{week_key[1]:02d}"
    state = {}
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not force:
        if tw_now.weekday() != 0 or tw_now.hour < 9:
            return {"decision": "not_monday_morning"}
        if state.get("last_week") == week_key:
            return {"decision": "already_ran", "week": week_key}
    monday = monday or last_monday(now)
    cal = json.loads(CAL.read_text(encoding="utf-8"))
    days = week_trading_days(monday, closed_days(cal))
    since = monday - timedelta(days=3)
    try:
        _git("fetch", "-q", "origin", "main")  # 只更新 origin/main（GitHub，不是資料源請求）；失敗就用本機現有的
    except Exception as e:  # noqa: BLE001
        print(f"[warn] git fetch 失敗，改用本機 origin/main：{e!r}")
    vers = {f: versions(f, since, ex) for f, ex in FILES.items()}
    rows = evaluate(days, vers)
    bad = [r for r in rows if r["status"] != "OK"]
    rec = {"checked_at": tw_now.isoformat(timespec="seconds"), "week_monday": monday.isoformat(), "trading_days": days,
           "rows": rows, "n_ok": len(rows) - len(bad), "n_late": sum(r["status"] == "LATE" for r in rows),
           "n_missing": sum(r["status"] == "MISSING" for r in rows), "files": list(FILES)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if bad and push:
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            import cc_push  # noqa: PLC0415
            body = "、".join(f"{r['date'][5:]} {r['status']}" for r in bad)
            cc_push._send("⚠️ 上週台股收盤資料沒有當晚落地", f"週 {monday.isoformat()}：{body}", "cc_stuck")
            rec["pushed"] = True
        except Exception as e:  # noqa: BLE001 —— 推播失敗只降級
            print(f"[warn] 推播失敗：{e!r}")
    if not force or monday == last_monday(now):
        STATE.write_text(json.dumps({"last_week": week_key, "ran_at": rec["checked_at"]}, ensure_ascii=False), encoding="utf-8")
    return {"decision": "ran", **rec}


def main(argv: list[str]) -> int:
    try:
        monday = None
        if "--week" in argv:
            monday = date.fromisoformat(argv[argv.index("--week") + 1])
        res = run(datetime.now(TW), monday=monday, force="--force" in argv, push="--no-push" not in argv)
        if res.get("decision") == "ran":
            print(f"[weekly_close_landing] 週 {res['week_monday']}：交易日 {len(res['trading_days'])}、OK {res['n_ok']}、"
                  f"LATE {res['n_late']}、MISSING {res['n_missing']}")
            for r in res["rows"]:
                print(f"  {r['date']} {r['status']}  " + "  ".join(f"{Path(f).name}={p['landed_at']}" for f, p in r["files"].items()))
        elif "--quiet" not in argv:
            print(f"[weekly_close_landing] {res.get('decision')}")
    except Exception as e:  # noqa: BLE001 —— 十二節
        print(f"[warn] weekly_tw_close_landing_check 失敗：{e!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
