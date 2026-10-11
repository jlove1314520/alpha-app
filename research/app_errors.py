"""常備.開發-29（2026-10-11）App 錯誤回報：本機累積＋每日彙總。

App 端 recordGlobalError() 收到的錯誤，經 alpha_live_server 的 POST /errors（token 必檢）
送到這裡。原始紀錄存 research/data/app_errors.jsonl（.gitignore 已排除 research/data/，
不進公開 repo）；每日彙總寫 data/app_errors_summary.json（只有日期、筆數、函式標籤，
同樣列入 .gitignore，留在本機）。

去識別化在伺服器端做（App 端也會先做一次，但以伺服器為準，不信任前端）：
網址、email、7 位以上數字（帳號／委託書號）、長 token 字串、Windows 使用者路徑一律換成
佔位標記；label 截 80 字、msg 截 200 字。只收 label／msg／ts／ver 四個欄位，其他一律丟棄
（UA、網址、自選股等不收）。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

TW_TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "research" / "data" / "app_errors.jsonl"
SUMMARY_PATH = ROOT / "data" / "app_errors_summary.json"

MAX_BATCH = 50            # 單次 POST 最多收幾筆，多的丟棄並回報 dropped
MAX_PER_DAY = 2000        # 單日上限，防止某個無限迴圈錯誤把檔案灌爆
KEEP_DAYS = 30            # 原始紀錄保留天數（彙總時順手修剪）
SUMMARY_DAYS = 7

_SCRUB = [
    (re.compile(r"https?://\S+", re.I), "<url>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.I), "<path>"),
    (re.compile(r"\b[A-Za-z0-9_\-]{24,}\b"), "<token>"),
    (re.compile(r"\d{7,}"), "<num>"),
]


def scrub(text, limit: int) -> str:
    s = str(text if text is not None else "")
    for pat, rep in _SCRUB:
        s = pat.sub(rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _parse_ts(raw, now: datetime) -> datetime:
    """用 App 端發生時間（離線排隊後才送達的錯誤仍歸到正確日期）；不合理就用伺服器收到時間。"""
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TW_TZ)
        if now - timedelta(days=8) <= ts <= now + timedelta(hours=1):
            return ts.astimezone(TW_TZ)
    except (TypeError, ValueError):
        pass
    return now


def _iter_log(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("ts"):
                yield rec


def _count_day(path: Path, day: str) -> int:
    return sum(1 for r in _iter_log(path) if str(r.get("ts", ""))[:10] == day)


def ingest(payload, log_path: Path = LOG_PATH, now: datetime | None = None) -> dict:
    now = now or datetime.now(TW_TZ)
    items = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("需要 {errors:[...]}")
    ver = scrub(payload.get("ver"), 40)
    dropped = max(0, len(items) - MAX_BATCH)
    today = now.strftime("%Y-%m-%d")
    room = MAX_PER_DAY - _count_day(log_path, today)
    rows = []
    for it in items[:MAX_BATCH]:
        if not isinstance(it, dict):
            dropped += 1
            continue
        ts = _parse_ts(it.get("ts"), now)
        if ts.strftime("%Y-%m-%d") == today:
            if room <= 0:
                dropped += 1
                continue
            room -= 1
        rows.append({"ts": ts.isoformat(timespec="seconds"), "label": scrub(it.get("label"), 80) or "(無標籤)",
                     "msg": scrub(it.get("msg"), 200), "ver": ver})
    if rows:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"accepted": len(rows), "dropped": dropped}


def build_summary(log_path: Path = LOG_PATH, now: datetime | None = None, prune: bool = True) -> dict:
    now = now or datetime.now(TW_TZ)
    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(SUMMARY_DAYS - 1, -1, -1)]
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    per_day = {d: {"date": d, "count": 0, "labels": {}} for d in days}
    keep = []
    for r in _iter_log(log_path):
        d = str(r["ts"])[:10]
        if d >= cutoff:
            keep.append(r)
        if d in per_day:
            per_day[d]["count"] += 1
            lb = per_day[d]["labels"]
            lb[r.get("label") or "(無標籤)"] = lb.get(r.get("label") or "(無標籤)", 0) + 1
    if prune and log_path.exists():
        tmp = log_path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        tmp.replace(log_path)
    top = {}
    for d in per_day.values():
        for k, v in d["labels"].items():
            top[k] = top.get(k, 0) + v
        d["labels"] = dict(sorted(d["labels"].items(), key=lambda kv: -kv[1])[:5])
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "source": "本機 alpha_live_server /errors（App recordGlobalError，去識別化）",
        "window_days": SUMMARY_DAYS,
        "total_7d": sum(d["count"] for d in per_day.values()),
        "days": list(per_day.values()),
        "top_labels_7d": [{"label": k, "count": v} for k, v in sorted(top.items(), key=lambda kv: -kv[1])[:8]],
    }


def write_summary(summary: dict, path: Path = SUMMARY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def summary_if_stale(log_path: Path = LOG_PATH, path: Path = SUMMARY_PATH, now: datetime | None = None,
                     force: bool = False) -> dict:
    """每日彙總：檔案日期不是今天（或 force）才重建＋修剪原始紀錄；否則讀既有檔。"""
    now = now or datetime.now(TW_TZ)
    if not force and path.exists():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if str(doc.get("generated_at", ""))[:10] == now.strftime("%Y-%m-%d"):
                return doc
        except (json.JSONDecodeError, OSError):
            pass
    doc = build_summary(log_path, now)
    write_summary(doc, path)
    return doc


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    d = summary_if_stale(force=True)
    print(f"近 {d['window_days']} 日錯誤 {d['total_7d']} 筆 → {SUMMARY_PATH}")
