# -*- coding: utf-8 -*-
"""先.一三五-1d（2026-10-27）：重大訊息長期歸檔（N1～N3 共用前置）。

data/events.json 只留 90 天（keep_days），追蹤程式若中斷超過 90 天，舊的重大訊息就永久遺失。
這支把 events.json 裡 source 含「重大訊息」的事件，以（代號、日期、標題）去重，append 到
research/data/mops_events_archive.jsonl（本機檔、不進公開 repo，research/data/ 已在 .gitignore）。

零外部請求：只讀本機工作目錄的 data/events.json，另可用 --git-rev 讀 git 物件（例 origin/main，
需呼叫端已 fetch 過；本身不 fetch）。
掛在本機排程 AlphaNewsFallback（scripts/news_local_fallback.py，每 30 分鐘）開頭。
自身任何失敗只印警告、exit 0（十二節），不影響呼叫它的排程。
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events.json"
ARCHIVE = ROOT / "research" / "data" / "mops_events_archive.jsonl"
TW = timezone(timedelta(hours=8))
KEEP_FIELDS = ("code", "name", "date", "type", "title", "source", "url", "importance")


def _key(e: dict) -> tuple:
    return (str(e.get("code") or ""), str(e.get("date") or ""), str(e.get("title") or ""))


def load_events(rev: str | None = None, path: Path = EVENTS) -> list[dict] | None:
    """讀 events.json 的 events 陣列；讀不到／不是合法 JSON 回 None（呼叫端只警告）。"""
    try:
        if rev:
            r = subprocess.run(["git", "show", f"{rev}:data/events.json"], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=60)
            if r.returncode != 0:
                print(f"[warn] 歸檔：讀不到 {rev}:data/events.json（{r.stderr.strip()[:200]}）", flush=True)
                return None
            txt = r.stdout
        else:
            txt = path.read_text(encoding="utf-8")
        d = json.loads(txt)
        ev = d.get("events") if isinstance(d, dict) else None
        if not isinstance(ev, list):
            print(f"[warn] 歸檔：{rev or path} 沒有 events 陣列", flush=True)
            return None
        return ev
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 歸檔：讀 {rev or path} 失敗（{type(e).__name__}: {e}）", flush=True)
        return None


def existing_keys(archive: Path = ARCHIVE) -> set:
    keys = set()
    if not archive.exists():
        return keys
    with archive.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                keys.add(_key(json.loads(line)))
            except ValueError:
                print(f"[warn] 歸檔：{archive.name} 第 {i} 行不是合法 JSON，略過（不改動原檔）", flush=True)
    return keys


def archive_events(events: list[dict], archive: Path = ARCHIVE, label: str = "") -> int:
    """回傳本次新增筆數。只收 source 含「重大訊息」者，（代號、日期、標題）去重。"""
    seen = existing_keys(archive)
    now = datetime.now(TW).isoformat(timespec="seconds")
    rows = []
    for e in events:
        if not isinstance(e, dict) or "重大訊息" not in str(e.get("source") or ""):
            continue
        k = _key(e)
        if not k[0] or not k[1] or k in seen:
            continue
        seen.add(k)
        row = {f: e.get(f) for f in KEEP_FIELDS}
        row["archived_at"] = now
        rows.append(json.dumps(row, ensure_ascii=False))
    if rows:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with archive.open("a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    print(f"歸檔{('（' + label + '）') if label else ''}：新增 {len(rows)} 筆，累計 {len(seen)} 筆 → {archive.name}", flush=True)
    return len(rows)


def run(revs: list[str] | None = None) -> int:
    """工作目錄版先歸檔，再依序歸檔各 git 版本；任何一步失敗只警告。回傳總新增筆數。"""
    total = 0
    for rev in [None, *(revs or [])]:
        try:
            ev = load_events(rev)
            if ev is not None:
                total += archive_events(ev, label=rev or "工作目錄")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 歸檔（{rev or '工作目錄'}）失敗：{type(e).__name__}: {e}", flush=True)
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--git-rev", action="append", default=[], help="另外歸檔某個 git 版本的 data/events.json（例 origin/main）")
    a = ap.parse_args()
    run(a.git_rev)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"[warn] archive_mops_events 失敗：{type(e).__name__}: {e}", flush=True)
        sys.exit(0)
