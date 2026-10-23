# -*- coding: utf-8 -*-
"""盤中台股報價本機備援（2026-10-13 總司令【先.八十二】4 裁示③，提案 docs/PROPOSAL_QUOTES_LOCAL_FALLBACK.md）。

根因：quotes.yml 排了盤中每 10 分鐘一班，但 GitHub 對高頻 schedule 是 best-effort（10/13 上午 0 班），
data/quotes_tw.json 停在開盤前。做法（照裁示：只做台股、雲端落後門檻 15 分鐘、雲端已更新就略過）：
  本機排程 AlphaQuotesFallback 交易日 09:05～13:45 每 10 分鐘叫一次 →
  ① 休市日（data/trading_calendar.json）或盤外 → 只記心跳結束
  ② 看 origin/main 的 data/quotes_tw.json fetched_at，距今 <15 分鐘 → 雲端有在跑，略過
  ③ 落後 ≥15 分鐘 → 本機跑同一支 .github/scripts/fetch_quotes_tw.py（同一套 MIS 節流／封鎖紀錄）
  ④ 提交前再看一次雲端，已更新就作廢本機這輪；否則只提交 data/quotes_tw.json（取鎖帶 token、衝突作廢本機）
每輪在 research/quotes_local_fallback.jsonl 記一行心跳（決策、雲端落後分鐘、結果）。自身失敗只記 log（十二節）。
不讀任何金鑰（MIS 是免金鑰公開端點）。
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import local_git_commit as G  # noqa: E402

TW = timezone(timedelta(hours=8))
STALE_MIN = 15
WINDOW = ("09:05", "13:45")
OUT = "data/quotes_tw.json"
HB = ROOT / "research" / "quotes_local_fallback.jsonl"


def heartbeat(decision: str, **kw) -> None:
    row = {"ts": datetime.now(TW).isoformat(timespec="seconds"), "decision": decision, **kw}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    try:
        with HB.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def is_trading_day(d: str) -> bool | None:
    try:
        cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))["tw"][d[:4]]
    except Exception:  # noqa: BLE001
        return None  # 日曆讀不到：只用週末判斷
    return d not in set(cal.get("closed") or []) | set(cal.get("unscheduled_closed") or []) | _suspected_today(cal, d)


def _suspected_today(y: dict, d: str) -> set:
    """先.一三二-10b：盤中零請求判的「今天疑似臨時休市」（detect_suspected_closure.py）也當休市；
    只認 date＝今天（台北）且收盤確認沒有記成「疑似卻有成交」的。"""
    s, m = y.get("suspected_closed_today"), y.get("suspected_closed_mismatch")
    if isinstance(s, dict) and s.get("date") == d == datetime.now(TW).strftime("%Y-%m-%d")             and not (isinstance(m, dict) and m.get("date") == d):
        return {d}
    return set()


def _age(txt: str | None) -> float | None:
    try:
        t = datetime.fromisoformat(json.loads(txt)["fetched_at"])
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(TW) - t).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return None


def origin_age_min() -> float | None:
    G._g("fetch", "-q", "origin", "main", timeout=120)
    return _age(G._g("show", f"origin/main:{OUT}", timeout=60).stdout)


def main(now: datetime | None = None) -> int:
    now = now or datetime.now(TW)
    day, hm = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
    td = is_trading_day(day)
    if now.weekday() >= 5 or td is False:
        heartbeat("skip_closed", day=day)
        return 0
    if not (WINDOW[0] <= hm <= WINDOW[1]):
        heartbeat("skip_outside_window", hm=hm)
        return 0
    if G.rebase_in_progress():
        heartbeat("skip_rebase_in_progress")
        return 0
    age = origin_age_min()
    if age is not None and age < STALE_MIN:
        heartbeat("skip_cloud_fresh", cloud_age_min=round(age, 1))
        return 0
    t0 = time.time()
    env = dict(__import__("os").environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, ".github/scripts/fetch_quotes_tw.py"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=600)
    took = round(time.time() - t0)
    local_age = _age((ROOT / OUT).read_text(encoding="utf-8")) if (ROOT / OUT).exists() else None
    if r.returncode != 0 or local_age is None or local_age > 5:
        if G._g("ls-files", "--error-unmatch", OUT).returncode == 0:
            G._g("checkout", "-q", "HEAD", "--", OUT)
        heartbeat("fetch_failed", cloud_age_min=None if age is None else round(age, 1), exit=r.returncode, seconds=took,
                  tail=(r.stderr or r.stdout)[-200:].replace("\n", " "))
        return 0
    try:  # 標明這份是本機補的（App／人工排查看得出來）
        doc = json.loads((ROOT / OUT).read_text(encoding="utf-8"))
        doc.setdefault("meta", {})["runner"] = {"by": "local_fallback", "cloud_age_min": None if age is None else round(age, 1),
                                               "note": "雲端排程落後 ≥15 分鐘，由本機備援補抓（先.八十二-4）"}
        (ROOT / OUT).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 標註 runner 失敗：{type(e).__name__}")
    age2 = origin_age_min()
    if age2 is not None and age2 < STALE_MIN:
        G._g("checkout", "-q", "HEAD", "--", OUT)
        heartbeat("dropped_cloud_caught_up", cloud_age_min=round(age2, 1), seconds=took)
        return 0
    res = G.commit_paths([OUT], f"盤中報價：本機備援補抓（雲端 {'未知' if age is None else f'{age:.0f} 分鐘'}未更新，先.八十二-4）",
                         drop_on_conflict=True)
    heartbeat("fetched", cloud_age_min=None if age is None else round(age, 1), seconds=took, commit=res)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        heartbeat("error", err=f"{type(e).__name__}: {e}"[:200])
        sys.exit(0)
