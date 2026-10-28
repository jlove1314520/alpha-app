"""只能前向累積的資料源缺期看守（先.一三五-1ae，DevQueue 20261028-220102）。

背景：模擬 K（paper_11）、L（paper_12）與候選 N7／N9／N1～N3 依賴的資料源，官方只給「最新一期」，
漏抓一期就永遠補不回。`research/forward_sim_watch.py` 只看 14 支追蹤程式輸出與帳本日期，
沒看這些上游累積檔本身，所以另寫這支。

只讀檔名與檔案內的資料日期欄，**不讀價格數值、零外部請求、不算任何報酬**。
各源（起算日＝該源第一份檔的日期；交易日讀 data/trading_calendar.json，讀不到只排除週末）：
  - tdcc：research/data/tdcc/YYYYMMDD.csv，每週一期（以 ISO 週計；整週休市的週不算；
    該週六之前不算到期）
  - warrant：research/data/warrant_snapshots/YYYY-MM-DD/meta.json，每交易日（台北 18:00 前今天不算到期）
  - margin_suspension：data/margin_suspension_daily/YYYY-MM-DD.json，每交易日（2026-10-29 起才有，之前不算缺）
  - tpex_limit_next：research/data/tpex_limit_next/YYYY-MM-DD.json（scripts/archive_tpex_limit_next.py 展開），
    檔名＝收盤資料日，每交易日
  - mops_events：research/data/mops_events_archive.jsonl 每列 date 欄，每交易日至少一則（休市日的公告不要求；
    今天不算到期）
狀態：OK／GAP（起算日到最近到期日之間有缺期）／NOT_STARTED（還沒有任何一期）／ERROR（本源讀取例外）。
權證另讀 research/data/warrant_snapshot_cycle.log，把缺期當天 launcher 的最後一行 stderr（沒有就 exit／休市行）附成 reason（讀不到就空白）。
看守員自身任何例外 fail open：只印警告、exit 0（CLAUDE.md 十二節）。

用法：python research/forward_source_gap_watch.py   （寫 research/data/forward_source_gap_watch.json）
自測：python scripts/selftest_forward_source_gap_watch.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "data" / "forward_source_gap_watch.json"
READY_HOUR = 18  # 台北時間幾點後「今天」這一期才算到期
MAX_LIST = 30    # 缺期最多列幾個

_D8 = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_D10 = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _parse(s: str) -> date | None:
    m = _D10.match(s) or _D8.match(s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def load_closed(root: Path) -> tuple[set[date], str]:
    """回傳（台股休市日集合, 說明）；讀不到只排除週末。"""
    try:
        doc = json.loads((root / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
        closed: set[date] = set()
        for _y, v in (doc.get("tw") or {}).items():
            for s in v.get("closed") or []:
                d = _parse(str(s))
                if d:
                    closed.add(d)
        if not closed:
            raise ValueError("tw.closed 是空的")
        return closed, "trading_calendar.json"
    except Exception as e:  # noqa: BLE001 — 降級：只排除週末
        print(f"[forward_source_gap_watch] ⚠️ 交易日曆讀不到（{e}），只排除週末")
        return set(), f"只排除週末（日曆讀不到：{type(e).__name__}）"


def is_trading(d: date, closed: set[date]) -> bool:
    return d.weekday() < 5 and d not in closed


def trading_days(a: date, b: date, closed: set[date]) -> list[date]:
    out, d = [], a
    while d <= b:
        if is_trading(d, closed):
            out.append(d)
        d += timedelta(days=1)
    return out


def _dates_from_names(dirpath: Path, want_dir: bool, suffix: str = "") -> set[date] | None:
    if not dirpath.is_dir():
        return None
    out = set()
    for p in dirpath.iterdir():
        if want_dir != p.is_dir():
            continue
        name = p.name[: -len(suffix)] if suffix and p.name.endswith(suffix) else (p.name if not suffix else None)
        if name is None:
            continue
        d = _parse(name)
        if d:
            out.add(d)
    return out


def _warrant_dates(root: Path) -> set[date] | None:
    base = root / "research" / "data" / "warrant_snapshots"
    if not base.is_dir():
        return None
    return {d for p in base.iterdir() if p.is_dir() and (p / "meta.json").exists() and (d := _parse(p.name))}


def _mops_dates(root: Path) -> tuple[set[date] | None, int]:
    f = root / "research" / "data" / "mops_events_archive.jsonl"
    if not f.exists():
        return None, 0
    out, bad = set(), 0
    with f.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                d = _parse(str(json.loads(line).get("date", ""))[:10])
            except Exception:  # noqa: BLE001 — 壞行只計數
                d = None
            if d:
                out.add(d)
            else:
                bad += 1
    return out, bad


def _warrant_reasons(root: Path) -> dict[str, str]:
    """warrant_snapshot_cycle.log：每個 launcher 日期取最後一行 exit／休市／stderr 訊息。"""
    f = root / "research" / "data" / "warrant_snapshot_cycle.log"
    out: dict[str, str] = {}
    try:
        cur = None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r"launcher: (\d{4}-\d{2}-\d{2})", line)
            if m:
                cur = m.group(1)
                continue
            # stderr 行（真正的例外）優先於 exit= 摘要行
            if cur and re.search(r"stderr:|exit=|休市|驗證不過", line):
                if "stderr:" in line or "stderr:" not in out.get(cur, ""):
                    out[cur] = line.strip()[:200]
    except Exception as e:  # noqa: BLE001
        print(f"[forward_source_gap_watch] ⚠️ 權證 log 讀不到（{type(e).__name__}），缺期不附原因")
    return out


def _daily_result(have: set[date], due_end: date, closed: set[date], not_before: date | None = None) -> dict:
    start = min(have)
    if not_before and start < not_before:
        start = not_before
    expected = trading_days(start, due_end, closed) if due_end >= start else []
    missing = [d for d in expected if d not in have]
    return {
        "first": min(have).isoformat(), "last": max(have).isoformat(), "due_through": due_end.isoformat(),
        "expected": len(expected), "have_in_range": len(expected) - len(missing),
        "missing": [d.isoformat() for d in missing],
    }


def _weekly_result(have: set[date], today: date, closed: set[date]) -> dict:
    def wk(d: date) -> date:  # 該週週一
        return d - timedelta(days=d.weekday())
    have_weeks = {wk(d) for d in have}
    w, last_due = wk(min(have)), []
    missing = []
    while w + timedelta(days=5) <= today:  # 該週六已到
        if trading_days(w, w + timedelta(days=4), closed):
            last_due.append(w)
            if w not in have_weeks:
                missing.append(w)
        w += timedelta(days=7)
    return {
        "first": min(have).isoformat(), "last": max(have).isoformat(),
        "due_through_week_of": last_due[-1].isoformat() if last_due else None,
        "expected": len(last_due), "have_in_range": len(last_due) - len(missing),
        "missing": [f"{m.isoformat()} 當週" for m in missing],
    }


def build(root: Path, now: datetime) -> dict:
    closed, cal_note = load_closed(root)
    today = now.date()
    due_today = now.hour >= READY_HOUR
    last_trading = today if due_today else today - timedelta(days=1)
    while not is_trading(last_trading, closed):
        last_trading -= timedelta(days=1)
    yesterday_trading = today - timedelta(days=1)
    while not is_trading(yesterday_trading, closed):
        yesterday_trading -= timedelta(days=1)

    specs = [
        ("tdcc", "TDCC 集保股權分散（週）", "research/data/tdcc/*.csv",
         lambda: _dates_from_names(root / "research" / "data" / "tdcc", False, ".csv"), "weekly", None),
        ("warrant", "權證每日快照", "research/data/warrant_snapshots/<日>/meta.json",
         lambda: _warrant_dates(root), "daily", last_trading),
        ("margin_suspension", "停資停券預告日檔", "data/margin_suspension_daily/*.json",
         lambda: _dates_from_names(root / "data" / "margin_suspension_daily", False, ".json"), "daily", last_trading),
        ("tpex_limit_next", "上櫃次日漲跌停（本機歸檔）", "research/data/tpex_limit_next/*.json",
         lambda: _dates_from_names(root / "research" / "data" / "tpex_limit_next", False, ".json"), "daily", last_trading),
        ("mops_events", "重大訊息歸檔（事件日期分布）", "research/data/mops_events_archive.jsonl",
         None, "daily", yesterday_trading),
    ]
    sources = {}
    for key, label, path, finder, kind, due_end in specs:
        try:
            extra = {}
            if key == "mops_events":
                have, bad = _mops_dates(root)
                extra["bad_lines"] = bad
            else:
                have = finder()
            if have is None or not have:
                sources[key] = {"label": label, "path": path, "status": "NOT_STARTED",
                                "note": "目錄／檔案不存在" if have is None else "還沒有任何一期", **extra}
                continue
            res = (_weekly_result(have, today, closed) if kind == "weekly"
                   else _daily_result(have, due_end, closed, date(2026, 10, 29) if key == "margin_suspension" else None))
            if key == "warrant" and res["missing"]:
                rs = _warrant_reasons(root)
                res["reasons"] = {d: rs.get(d, "") for d in res["missing"]}
            n_miss = len(res["missing"])
            res["missing"] = res["missing"][:MAX_LIST]
            sources[key] = {"label": label, "path": path, "status": "GAP" if n_miss else "OK",
                            "missing_count": n_miss, **res, **extra}
        except Exception as e:  # noqa: BLE001 — 單源失敗只影響自己
            print(f"[forward_source_gap_watch] ⚠️ {key} 讀取失敗：{type(e).__name__}: {e}")
            sources[key] = {"label": label, "path": path, "status": "ERROR", "error": f"{type(e).__name__}: {e}"[:200]}
    sts = [v["status"] for v in sources.values()]
    overall = "ERROR" if "ERROR" in sts else "GAP" if "GAP" in sts else "OK"
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "calendar": cal_note,
        "overall": overall,
        "note": "只讀檔名與資料日期欄、零外部請求；這些源官方只給最新一期，缺期無法回補。",
        "sources": sources,
    }


def main(argv: list[str]) -> int:
    try:
        root = ROOT
        out = OUT
        if "--root" in argv:
            root = Path(argv[argv.index("--root") + 1])
            out = root / "research" / "data" / "forward_source_gap_watch.json"
        now = datetime.now(TZ)
        if "--now" in argv:
            now = datetime.fromisoformat(argv[argv.index("--now") + 1]).replace(tzinfo=TZ)
        doc = build(root, now)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        for k, v in doc["sources"].items():
            print(f"[forward_source_gap_watch] {k}: {v['status']} 缺 {v.get('missing_count', 0)} "
                  f"{v.get('missing', [])[:8]}")
        print(f"[forward_source_gap_watch] overall={doc['overall']} → {out}")
    except Exception as e:  # noqa: BLE001 — 看守員自身失敗 fail open
        print(f"[forward_source_gap_watch] ⚠️ 看守員自身失敗（{type(e).__name__}: {e}），略過")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
