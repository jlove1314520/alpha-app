"""紙上追蹤看守員（先.二十七-三，總司令 2026-10-06）。

監看兩件事，任一未寫入就判 ERROR：
  (1) 紙.一 2026-10 月底首次記帳（event=monthly_rebalance、date 屬於 2026-10）
  (2) 紙.一b 2026-11-02 inception
另對任何已確認但尚未入帳的月底（資料已到、紀錄沒寫）、以及兩支追蹤腳本寫下的 last_error 一併回報。

判定兩路並行：
  A. 資料確認式：價格資料已到、紀錄卻沒有 -> 立即 ERROR（不等死線）。
  B. 死線式：到 DEADLINE 之後（台北時間）紀錄仍缺 -> ERROR（即使價格資料根本沒來）。

輸出：data/paper_tracking_watch.json（App 紅橫幅讀它）；狀態改變時才往
research/PROGRESS_HEARTBEAT.jsonl 追加一行 status=ERROR（避免每個排程時段重複洗版）。
看守員自身任何例外：fail open，只印警告、exit 0，不影響主流程（CLAUDE.md 十二）；
App 端另檢查 generated_at 是否過舊（監控的監控，CLAUDE.md 十一）。

用法：python research/paper_tracking_watchdog.py            （正式）
      python research/paper_tracking_watchdog.py --selftest （情境自測，用暫存目錄，不寫正式檔）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent

P1_FIRST_MONTH = "2026-10"
P1B_START_ANCHOR = "2026-11-01"
DEADLINE = datetime(2026, 11, 2, 20, 0, tzinfo=TZ)  # 11/2 當日最後一個排程時段(18:41)之後
SAFE_LEG = "00697B"


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _read_log(p: Path) -> list[dict]:
    out = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def _dates(prices: dict, sym: str) -> list[str]:
    return sorted(r["date"] for r in (prices.get("prices", {}).get(sym) or []))


def _last_weekday_of_month(d: str) -> bool:
    x = datetime.strptime(d, "%Y-%m-%d").date()
    n = x + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n.month != x.month


def _confirmed_month_ends(dates: list[str], after: str, same_day: bool) -> list[str]:
    """same_day=False：紙.一規則（下個月第一筆到才確認）；True：紙.一b規則（月底最後平日當日即確認）。"""
    out = [a for a, b in zip(dates, dates[1:]) if a[:7] != b[:7] and a > after]
    if same_day and dates and dates[-1] > after and _last_weekday_of_month(dates[-1]) and dates[-1] not in out:
        out.append(dates[-1])
    return out


def evaluate(root: Path, now: datetime) -> dict:
    items: list[dict] = []
    prices = _read_json(root / "data" / "price_history.json") or {}
    log1 = _read_log(root / "research" / "data" / "paper_7030_log.jsonl")
    log1b = _read_log(root / "research" / "data" / "paper_1b_log.jsonl")
    s1 = _read_json(root / "data" / "paper_7030.json") or {}
    s1b = _read_json(root / "data" / "paper_1b.json") or {}
    past_deadline = now >= DEADLINE

    d0050 = _dates(prices, "0050")
    p1_first = any(e.get("event") == "monthly_rebalance" and str(e.get("date", "")).startswith(P1_FIRST_MONTH)
                   for e in log1)
    if log1:
        pend = _confirmed_month_ends(d0050, log1[-1]["date"], False)
        if pend:
            items.append({"id": "p1_pending", "track": "紙.一",
                          "msg": "紙.一 有已確認月底尚未入帳：" + ", ".join(pend) + "（價格資料已到、紀錄未寫）"})
    if not p1_first and past_deadline:
        items.append({"id": "p1_first_month_end", "track": "紙.一",
                      "msg": "紙.一 2026-10 首次月底記帳（10/30）逾期未寫入（死線 2026-11-02 20:00）"})
    if (s1.get("last_error") or {}).get("status"):
        items.append({"id": "p1_last_error", "track": "紙.一",
                      "msg": "紙.一 last_error：" + str(s1["last_error"].get("status"))})

    p1b_incep = any(e.get("event") == "inception" for e in log1b)
    if not p1b_incep:
        if any(d >= P1B_START_ANCHOR for d in _dates(prices, SAFE_LEG)):
            items.append({"id": "p1b_pending", "track": "紙.一b",
                          "msg": "紙.一b 起算日後的價格資料已到，但 inception 尚未寫入"})
        if past_deadline:
            items.append({"id": "p1b_inception", "track": "紙.一b",
                          "msg": "紙.一b 2026-11-02 啟動紀錄逾期未寫入（死線 2026-11-02 20:00）"})
    else:
        pend = _confirmed_month_ends(_dates(prices, SAFE_LEG), log1b[-1]["date"], True)
        if pend:
            items.append({"id": "p1b_pending_me", "track": "紙.一b",
                          "msg": "紙.一b 有已確認月底尚未入帳：" + ", ".join(pend)})
    if (s1b.get("last_error") or {}).get("status"):
        items.append({"id": "p1b_last_error", "track": "紙.一b",
                      "msg": "紙.一b last_error：" + str(s1b["last_error"].get("status"))})

    return {"status": "ERROR" if items else "OK", "items": items,
            "checked": {"p1_first_month_end_done": p1_first, "p1b_inception_done": p1b_incep,
                        "deadline": DEADLINE.isoformat()},
            "generated_at": now.isoformat()}


def _signature(w: dict | None) -> str:
    if not w:
        return "OK"
    return "|".join(sorted(i["id"] for i in w.get("items", []))) or "OK"


def run(root: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    result = evaluate(root, now)
    out = root / "data" / "paper_tracking_watch.json"
    try:
        prev = _read_json(out)
    except Exception:  # noqa: BLE001
        prev = None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] == "ERROR" and _signature(prev) != _signature(result):
        hb = root / "research" / "PROGRESS_HEARTBEAT.jsonl"
        rec = {"ts": now.isoformat(), "track": "interactive", "round": "先.二十七",
               "item": "紙上追蹤看守", "status": "ERROR",
               "note": "；".join(i["msg"] for i in result["items"])}
        with open(hb, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("[紙上追蹤看守] " + result["status"] + "  " + str(len(result["items"])) + " 項")
    for i in result["items"]:
        print("  - " + i["msg"])
    return result


def _selftest() -> int:
    import tempfile
    fails = []

    def chk(name, cond):
        print(("PASS " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    def mk(td, d0050, d697, log1, log1b, s1=None, s1b=None):
        (td / "data").mkdir(parents=True)
        (td / "research" / "data").mkdir(parents=True)

        def rows(ds):
            return [{"date": d, "close": 1, "adj_close": 1} for d in ds]

        (td / "data" / "price_history.json").write_text(json.dumps(
            {"prices": {"0050": rows(d0050), SAFE_LEG: rows(d697)}}), encoding="utf-8")
        for name, rs in (("paper_7030_log.jsonl", log1), ("paper_1b_log.jsonl", log1b)):
            (td / "research" / "data" / name).write_text(
                "".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")
        if s1 is not None:
            (td / "data" / "paper_7030.json").write_text(json.dumps(s1), encoding="utf-8")
        if s1b is not None:
            (td / "data" / "paper_1b.json").write_text(json.dumps(s1b), encoding="utf-8")

    inc1 = {"date": "2026-10-01", "event": "inception"}
    me1 = {"date": "2026-10-30", "event": "monthly_rebalance"}
    inc1b = {"date": "2026-11-02", "event": "inception"}
    oct_ = ["2026-10-01", "2026-10-29", "2026-10-30"]

    def t(s):
        return datetime.fromisoformat(s).replace(tzinfo=TZ)

    def ids(r):
        return {i["id"] for i in r["items"]}

    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_, oct_, [inc1], [])
        chk("1 11/2 之前、無新資料 -> OK", evaluate(a, t("2026-10-31T12:00:00"))["status"] == "OK")
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_ + ["2026-11-02"], oct_ + ["2026-11-02"], [inc1, me1], [inc1b])
        chk("2 兩者皆已入帳 -> OK", evaluate(a, t("2026-11-02T21:00:00"))["status"] == "OK")
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_ + ["2026-11-02"], oct_ + ["2026-11-02"], [inc1], [])
        chk("3 資料已到未入帳（死線前）-> ERROR",
            ids(evaluate(a, t("2026-11-02T13:00:00"))) == {"p1_pending", "p1b_pending"})
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_, oct_, [inc1], [])
        chk("4 資料沒來、過死線 -> ERROR",
            ids(evaluate(a, t("2026-11-02T20:30:00"))) == {"p1_first_month_end", "p1b_inception"})
        chk("4b 死線前一小時不誤報", evaluate(a, t("2026-11-02T19:00:00"))["status"] == "OK")
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_ + ["2026-11-02"], oct_ + ["2026-11-02"], [inc1, me1], [])
        r = evaluate(a, t("2026-11-02T21:00:00"))
        chk("5 僅紙.一b缺 -> 只報紙.一b", {i["track"] for i in r["items"]} == {"紙.一b"})
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_, oct_, [inc1], [], s1b={"started": False, "last_error": {"status": "ABORTED_STALE_PRICE"}})
        chk("6 追蹤腳本 last_error -> ERROR", ids(evaluate(a, t("2026-10-20T12:00:00"))) == {"p1b_last_error"})
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        nov = ["2026-11-02", "2026-11-27", "2026-11-30"]
        mk(a, oct_ + nov, oct_ + nov, [inc1, me1], [inc1b])
        r = ids(evaluate(a, t("2026-11-30T21:00:00")))
        chk("7 11/30 紙.一b 月底漏記 -> ERROR（紙.一須等12月資料，不誤報）", r == {"p1b_pending_me"})
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_, oct_, [inc1], [])
        hb = a / "research" / "PROGRESS_HEARTBEAT.jsonl"
        hb.write_text("", encoding="utf-8")
        run(a, t("2026-11-02T20:30:00"))
        run(a, t("2026-11-02T20:45:00"))
        chk("8 持續 ERROR 只寫 1 行心跳", len(hb.read_text(encoding="utf-8").splitlines()) == 1)
        chk("8b 看守檔已寫", (a / "data" / "paper_tracking_watch.json").exists())
    with tempfile.TemporaryDirectory() as a:
        a = Path(a)
        mk(a, oct_, oct_, [inc1], [])
        (a / "data" / "price_history.json").write_text("{bad", encoding="utf-8")
        try:
            evaluate(a, t("2026-11-02T21:00:00"))
            raised = False
        except Exception:  # noqa: BLE001
            raised = True
        chk("9 壞價格檔丟例外（由 __main__ 的 try 降級為警告）", raised)
    print("ALL PASS" if not fails else "FAILED: " + str(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    try:
        run()
    except Exception as e:  # noqa: BLE001
        print("::warning::紙上追蹤看守員自身失敗（不影響主流程）：" + type(e).__name__ + ": " + str(e))
    sys.exit(0)
