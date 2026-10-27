"""前向模擬看守員（先.一三五-1k，DevQueue 20261028-043102）。

背景：`research/paper_tracking_watchdog.py` 只看紙.一／紙.一b，`data/seed/pipeline_registry.json`
也沒有任何一個 `data/paper_5.json`～`paper_18.json`；模擬 G／I 11/02 起跑、H／J／K／L 12/01、
M～R 2027-01-04，任何一支追蹤程式安靜停跑都只能等人肉眼發現（CLAUDE.md 十一節）。

只讀每個檔的 `generated_at`／`started`／`start_not_before`（缺時退回 `start`）／`last_error`，
**不讀 nav、不讀報酬**。判定（台股交易日，休市日讀 data/trading_calendar.json，讀不到只排除週末）：
  ① `generated_at` 之後到今天（含）已過 >2 個交易日 → STALE
  ② 今天 ≥ 起跑日，且起跑日到昨天（含）已過 ≥1 個交易日仍 `started=false` → NOT_STARTED_LATE
  ③ 有 `last_error` → ERROR
  起跑有前置閘門者（含 `snapshot_streak_need`，目前只有 paper_12）閘門未達成前不判②，達成後以 `streak_achieved_on` 起算。
  另：檔案不存在 → MISSING；不是合法 JSON／不是物件 → UNREADABLE；都沒事 → OK。
輸出 `data/forward_sim_watch.json`。看守員自身任何例外 fail open：只印警告、exit 0（CLAUDE.md 十二節）。
本程式零外部請求；尚未掛排程（掛 market.yml＋pipeline_registry 屬提案，待互動視窗核准）。

用法：python research/forward_sim_watch.py             （正式，寫 data/forward_sim_watch.json）
      python research/forward_sim_watch.py --selftest  （暫存目錄＋合成檔，不寫正式檔）
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
PAPER_IDS = list(range(5, 19))  # paper_5 ～ paper_18
STALE_TRADING_DAYS = 2
LATE_TRADING_DAYS = 1
OUT_REL = Path("data") / "forward_sim_watch.json"


def _tw_closed(root: Path) -> set[str]:
    """台股休市日；讀不到回空集合（只排除週末），並印警告。"""
    try:
        cal = json.loads((root / "data" / "trading_calendar.json").read_text(encoding="utf-8")).get("tw") or {}
        out: set[str] = set()
        for y in cal.values():
            out.update((y or {}).get("closed") or [])
        return out
    except Exception as e:
        print(f"[warn] forward_sim_watch：trading_calendar 讀取失敗，只排除週末：{e}")
        return set()


def _is_trading(d: date, closed: set[str]) -> bool:
    return d.weekday() < 5 and d.isoformat() not in closed


def _count_trading(start: date, end: date, closed: set[str]) -> int:
    """[start, end] 兩端都含的交易日數；start > end 回 0。"""
    n, d = 0, start
    while d <= end:
        if _is_trading(d, closed):
            n += 1
        d += timedelta(days=1)
    return n


def _parse_date(s) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_ts(s) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=TZ)


def check_one(path: Path, today: date, closed: set[str]) -> dict:
    row: dict = {"file": path.name, "status": "OK", "issues": []}
    if not path.exists():
        row.update(status="MISSING", issues=["檔案不存在"])
        return row
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("頂層不是物件")
    except Exception as e:
        row.update(status="UNREADABLE", issues=[f"讀取/解析失敗：{type(e).__name__}"])
        return row

    gen = _parse_ts(d.get("generated_at"))
    started = d.get("started") is True
    start_s = d.get("start_not_before") or d.get("start")
    start = _parse_date(start_s)
    # 先.一三五-1n：起跑有前置閘門的（paper_12 權證快照需連續 N 日成功，C.step start_override 順延），
    # 摘要檔的 start_not_before 仍是 PREREG 原值；閘門未達成前不判晚起跑，達成後以達成日為起算。
    gated = "snapshot_streak_need" in d
    if gated:
        achieved = _parse_date(d.get("streak_achieved_on"))
        row["gate"] = {"streak_achieved_on": d.get("streak_achieved_on"), "gate_deadline": d.get("gate_deadline")}
        if achieved is None:
            start = None
        elif start is None or achieved > start:
            start = achieved
    err = d.get("last_error")
    row.update(generated_at=d.get("generated_at"), started=started, start_not_before=start_s)

    statuses: list[str] = []
    if err:
        statuses.append("ERROR")
        row["issues"].append(f"last_error：{str(err)[:200]}")
    if gen is None:
        statuses.append("STALE")
        row["issues"].append("沒有可解析的 generated_at")
    else:
        gd = gen.astimezone(TZ).date()
        lag = _count_trading(gd + timedelta(days=1), today, closed)
        row["trading_days_since_generated"] = lag
        if lag > STALE_TRADING_DAYS:
            statuses.append("STALE")
            row["issues"].append(f"generated_at 之後已過 {lag} 個交易日未更新（上限 {STALE_TRADING_DAYS}）")
    if not started and start is not None and today >= start:
        passed = _count_trading(start, today - timedelta(days=1), closed)
        row["trading_days_since_start"] = passed
        if passed >= LATE_TRADING_DAYS:
            statuses.append("NOT_STARTED_LATE")
            row["issues"].append(f"起跑日 {start_s} 已過 {passed} 個交易日仍 started=false")
    # 多個狀態時取最嚴重的當主狀態，其餘留在 issues
    for s in ("ERROR", "STALE", "NOT_STARTED_LATE"):
        if s in statuses:
            row["status"] = s
            break
    return row


def evaluate(root: Path, now: datetime) -> dict:
    today = now.astimezone(TZ).date()
    closed = _tw_closed(root)
    rows = [check_one(root / "data" / f"paper_{i}.json", today, closed) for i in PAPER_IDS]
    bad = [r for r in rows if r["status"] != "OK"]
    return {
        "generated_at": now.astimezone(TZ).isoformat(timespec="seconds"),
        "note": "前向模擬追蹤檔新鮮度＋起跑日檢查；只讀 generated_at／started／start_not_before／last_error，不讀淨值與報酬",
        "rules": {"stale_trading_days_gt": STALE_TRADING_DAYS, "late_start_trading_days_ge": LATE_TRADING_DAYS},
        "overall": "OK" if not bad else "ALERT",
        "n_checked": len(rows),
        "n_alert": len(bad),
        "items": rows,
    }


def run(root: Path = ROOT, now: datetime | None = None) -> dict | None:
    try:
        res = evaluate(root, now or datetime.now(TZ))
        out = root / OUT_REL
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(out)
        print(f"[forward_sim_watch] overall={res['overall']} 檢查 {res['n_checked']} 檔、警示 {res['n_alert']}")
        for r in res["items"]:
            if r["status"] != "OK":
                print(f"  - {r['file']}: {r['status']}；{'；'.join(r['issues'])}")
        return res
    except Exception as e:  # 十二節：看守員自己壞掉只警告
        print(f"[warn] forward_sim_watch 自身失敗（fail open）：{type(e).__name__}: {e}")
        return None


def _selftest() -> int:
    ok = fail = 0

    def check(name, cond):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
        print(f"{'PASS' if cond else 'FAIL'} {name}")

    now = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)  # 週四
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "data").mkdir()
        (root / "data" / "trading_calendar.json").write_text(
            json.dumps({"tw": {"2026": {"closed": ["2026-11-03"]}}}), encoding="utf-8")

        def w(i, obj):
            (root / "data" / f"paper_{i}.json").write_text(
                obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")

        fresh = "2026-11-05T00:06:00+08:00"
        w(5, {"generated_at": fresh, "started": True, "start": "2026-11-02"})                    # OK
        w(6, {"generated_at": "2026-10-30T00:06:00+08:00", "started": False,
              "start_not_before": "2026-12-01"})                                                 # 10/30 後：11/02、11/04、11/05＝3 → STALE
        w(7, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-02"})        # 11/02 已過 → LATE
        w(8, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-05"})        # 今天起跑 → OK
        w(9, {"generated_at": fresh, "started": True, "last_error": "boom"})                    # ERROR
        w(10, "{not json")                                                                      # UNREADABLE
        w(11, "[1,2]")                                                                          # UNREADABLE
        # paper_12 不寫 → MISSING
        w(13, {"generated_at": "2026-11-02T00:06:00+08:00", "started": True})                   # 11/02 後：11/04、11/05＝2（11/03 休市）→ OK
        w(14, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-04"})       # 11/04 已過 1 日 → LATE
        w(15, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-03"})       # 11/03 休市、11/04 交易 → LATE
        w(16, {"generated_at": None, "started": False, "start_not_before": "2027-01-04"})        # 無 generated_at → STALE
        w(17, {"generated_at": fresh, "started": False, "start_not_before": "2027-01-04", "nav": "勿讀"})  # OK
        w(18, {"generated_at": "2026-10-20T00:00:00+08:00", "started": False,
               "start_not_before": "2026-11-02", "last_error": "x"})                            # ERROR 優先，issues 含 STALE+LATE

        res = run(root, now)
        st = {r["file"]: r for r in (res or {}).get("items", [])}
        check("run 有回傳且寫檔", res is not None and (root / OUT_REL).exists())
        check("共 14 檔", res and res["n_checked"] == 14)
        check("paper_5 OK", st["paper_5.json"]["status"] == "OK")
        check("paper_6 STALE（3 交易日）", st["paper_6.json"]["status"] == "STALE")
        check("paper_7 NOT_STARTED_LATE", st["paper_7.json"]["status"] == "NOT_STARTED_LATE")
        check("paper_8 今天起跑不算晚", st["paper_8.json"]["status"] == "OK")
        check("paper_9 ERROR", st["paper_9.json"]["status"] == "ERROR")
        check("paper_10 壞 JSON → UNREADABLE", st["paper_10.json"]["status"] == "UNREADABLE")
        check("paper_11 非物件 → UNREADABLE", st["paper_11.json"]["status"] == "UNREADABLE")
        check("paper_12 不存在 → MISSING", st["paper_12.json"]["status"] == "MISSING")
        check("paper_13 休市日不計 → OK", st["paper_13.json"]["status"] == "OK")
        check("paper_14 LATE", st["paper_14.json"]["status"] == "NOT_STARTED_LATE")
        check("paper_15 起跑日休市後 LATE", st["paper_15.json"]["status"] == "NOT_STARTED_LATE")
        check("paper_16 無 generated_at → STALE", st["paper_16.json"]["status"] == "STALE")
        check("paper_17 OK 且輸出不含 nav", st["paper_17.json"]["status"] == "OK"
              and "nav" not in json.dumps(res, ensure_ascii=False).replace("淨值", ""))
        check("paper_18 ERROR 且 issues 有 3 條", st["paper_18.json"]["status"] == "ERROR"
              and len(st["paper_18.json"]["issues"]) == 3)
        check("overall=ALERT", res and res["overall"] == "ALERT")

        # 閘門順延（paper_12 型）：未達成不判晚、達成後照達成日起算
        w(12, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-02",
               "snapshot_streak_need": 10, "streak_achieved_on": None})
        r12 = check_one(root / "data" / "paper_12.json", now.date(), set())
        check("閘門未達成 → 不判晚起跑", r12["status"] == "OK")
        w(12, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-02",
               "snapshot_streak_need": 10, "streak_achieved_on": "2026-11-05"})
        r12 = check_one(root / "data" / "paper_12.json", now.date(), set())
        check("閘門今天達成 → 不判晚起跑", r12["status"] == "OK")
        w(12, {"generated_at": fresh, "started": False, "start_not_before": "2026-11-02",
               "snapshot_streak_need": 10, "streak_achieved_on": "2026-11-03"})
        r12 = check_one(root / "data" / "paper_12.json", now.date(), set())
        check("閘門達成後已過交易日仍未起跑 → LATE", r12["status"] == "NOT_STARTED_LATE")
        (root / "data" / "paper_12.json").unlink()

        # 日曆讀不到：只排除週末，仍跑完
        (root / "data" / "trading_calendar.json").write_text("壞", encoding="utf-8")
        res2 = run(root, now)
        check("日曆壞掉仍跑完", res2 is not None and res2["n_checked"] == 14)

        # 自身失敗 fail open：data 是檔案而非目錄 → 例外被吞、回 None
        root2 = Path(td) / "x"
        root2.mkdir()
        (root2 / "data").write_text("not a dir", encoding="utf-8")
        check("自身例外 fail open 回 None", run(root2, now) is None)

    print(f"selftest：{ok} 過、{fail} 失敗")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    run()
    sys.exit(0)
