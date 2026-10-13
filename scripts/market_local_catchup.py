# -*- coding: utf-8 -*-
"""先.八十四-1（2026-10-13）：台股主班（market.yml 17:13／18:41）沒落地時，本機補跑同一批腳本。

背景：2026-10-13 GitHub 的 17:13 主班與 18:41 補救班都沒有觸發（gh run list 當天只有 10:43 那班），
market_tw 停在 10/12。不是程式壞掉，是 GitHub schedule 沒觸發。

做法（不改 market.yml 任何步驟，直接讀它）：
1. 今天不是交易日 → 記心跳「略過」。
2. `git fetch` 後看 origin/main 的 data/market_tw.json：data_date 已是今天 → 記心跳「已落地」。
3. 雲端 market.yml 今天 09:00Z 後有一班正在排隊／執行 → 記心跳「雲端執行中」，不搶。
4. 否則在 repo 外的獨立 worktree（從 origin/main 乾淨簽出，跟雲端一樣）依序執行 market.yml
   每個 `run:` 步驟（略過 pip install 與最後的 commit 步驟）；沒標 continue-on-error 的步驟失敗，
   後面的一般步驟就不跑（同 GitHub 行為），只跑 commit。
5. commit：schema 守門員 → 用 market.yml 自己那一行 `git add -A ...` 清單（直接從 yml 擷取，不另抄一份）
   → commit → push（失敗 fetch+rebase 重試 5 次）。持有 research/git_op_lock.py 的鎖。
   不改 git config（worktree 共用 .git/config，雲端那步的 `git config user.name` 會改到本機身分，故不照抄）。
6. 心跳：research/data/market_local_catchup.jsonl（一行一次，含每步 rc／秒數）。

用法：
  python scripts/market_local_catchup.py            # 排程用：沒落地才補跑
  python scripts/market_local_catchup.py --check    # 只檢查、不補跑
  python scripts/market_local_catchup.py --force    # 不管有沒有落地都補跑（手動用）
排程：AlphaMarketCatchup 平日 17:30（run-market-catchup.ps1／.vbs）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "market.yml"
WT = ROOT.parent / "_market_catchup_wt"
HB = ROOT / "research" / "data" / "market_local_catchup.jsonl"
TW = timezone(timedelta(hours=8))
STEP_TIMEOUT = 1800
os.environ.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")  # 子行程（守門員、各步驟）一律 UTF-8 輸出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sh(args, cwd=ROOT, timeout=600, check=False):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f"{args[:3]} rc={r.returncode} {r.stderr[-300:]}")
    return r


def heartbeat(rec):
    rec = {"ts": datetime.now(TW).isoformat(timespec="seconds"), **rec}
    HB.parent.mkdir(parents=True, exist_ok=True)
    with HB.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False))


def is_trading_day(d):
    if d.weekday() >= 5:
        return False
    try:
        cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
        y = (cal.get("tw") or {}).get(str(d.year)) or {}
        closed = set(y.get("closed") or []) | set(y.get("unscheduled_closed") or [])
        return d.isoformat() not in closed
    except Exception as e:  # 日曆讀不到時寧可當作交易日（多跑一次無害，漏跑才有害）
        print("warn: trading_calendar 讀取失敗", e)
        return True


def landed_date():
    sh(["git", "fetch", "-q", "origin", "main"], check=True, timeout=300)
    r = sh(["git", "show", "origin/main:data/market_tw.json"], check=True)
    return json.loads(r.stdout).get("data_date")


def cloud_running(today_utc_start):
    r = sh(["gh", "run", "list", "--workflow=market.yml", "-L", "5", "--json", "status,createdAt,databaseId"])
    if r.returncode:
        return None
    for run in json.loads(r.stdout or "[]"):
        if run["createdAt"] >= today_utc_start and run["status"] in ("queued", "in_progress", "waiting", "pending"):
            return run["databaseId"]
    return None


def bash_exe():
    for c in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")):
        if c and Path(c).exists():
            return c
    raise RuntimeError("找不到 bash")


def load_steps():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    steps = doc["jobs"]["fetch-market"]["steps"]
    run_steps, commit = [], None
    for s in steps:
        if "run" not in s:
            continue
        if s.get("name", "").startswith("Commit"):
            commit = s["run"]
        elif not s["run"].strip().startswith("pip install"):
            run_steps.append(s)
    m = re.search(r"^\s*(git add -A .+)$", commit or "", re.M)
    if not m:
        raise RuntimeError("market.yml commit 步驟找不到 git add -A 清單")
    return run_steps, m.group(1).strip()


def prepare_worktree():
    if WT.exists():
        sh(["git", "worktree", "remove", "--force", str(WT)])
        if WT.exists():
            shutil.rmtree(WT, ignore_errors=True)
    sh(["git", "worktree", "prune"])
    sh(["git", "worktree", "add", "--detach", str(WT), "origin/main"], check=True, timeout=1800)


def run_steps(steps, bash):
    # 雲端 runner 是 UTF-8；本機主控台預設 cp950，印「・」這類字元會 UnicodeEncodeError（10/13 首跑 6 個美股步驟因此失敗）
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    results, broken = [], False
    for s in steps:
        name = s.get("name", "?")
        coe = bool(s.get("continue-on-error"))
        if broken:
            results.append({"step": name, "rc": None, "skipped": True})
            continue
        t0 = time.time()
        try:
            r = subprocess.run([bash, "-c", s["run"]], cwd=WT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=STEP_TIMEOUT, env=env)
            rc, tail = r.returncode, (r.stdout + r.stderr)[-400:]
        except subprocess.TimeoutExpired:
            rc, tail = -9, "timeout"
        results.append({"step": name, "rc": rc, "sec": round(time.time() - t0, 1)})
        print(f"[{rc}] {name} ({results[-1]['sec']}s)")
        if rc:
            print("   ", tail.replace("\n", " | ")[-300:])
            if not coe:
                broken = True
    return results


def commit_push(add_line, today):
    bash = bash_exe()
    guard = ("python scripts/data_schema_guard.py guard --report data/schema_guard/market.json --label market || true; "
             "git add -- data/schema_guard/market.json 2>/dev/null || true; " + add_line + "; "
             "for f in paper_7030 paper_1b paper_3 paper_4; do git add -f research/data/${f}_log.jsonl 2>/dev/null || true; done")
    sh([bash, "-c", guard], cwd=WT, timeout=900)
    if sh(["git", "diff", "--cached", "--quiet"], cwd=WT).returncode == 0:
        return {"commit": None, "note": "無變動"}
    ql = len([x for x in sh(["git", "diff", "--cached", "--name-only", "--", "data/quote_lite"], cwd=WT).stdout.splitlines() if x])
    msg = (f"本機補跑 market.yml 台股主班 {today}（先.八十四-1；GitHub schedule 未觸發；quote_lite 變動 {ql} 檔）\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01WSVJewi85aswAiTfLEXm9n")
    sh(["git", "commit", "-q", "-m", msg], cwd=WT, check=True)
    tok = None
    for _ in range(60):
        r = sh([sys.executable, "research/git_op_lock.py", "acquire"])
        if r.returncode == 0:
            m = re.search(r"token=([0-9a-f]+)", r.stdout)
            tok = m.group(1) if m else None
            break
        time.sleep(5)
    try:
        for i in range(5):
            if sh(["git", "push", "origin", "HEAD:main"], cwd=WT, timeout=600).returncode == 0:
                return {"commit": sh(["git", "rev-parse", "--short", "HEAD"], cwd=WT).stdout.strip(), "push_try": i + 1}
            sh(["git", "fetch", "-q", "origin", "main"], cwd=WT, timeout=300)
            if sh(["git", "rebase", "origin/main"], cwd=WT, timeout=600).returncode:
                sh(["git", "rebase", "--abort"], cwd=WT)
                return {"commit": None, "note": "rebase 衝突，放棄"}
            time.sleep(5)
        return {"commit": None, "note": "push 重試 5 次失敗"}
    finally:
        if tok:
            sh([sys.executable, "research/git_op_lock.py", "release", "--token", tok])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", action="append", default=[], help="只跑步驟名稱含此字串者（可多次；補跑失敗步驟用）")
    a = ap.parse_args()
    now = datetime.now(TW)
    today = now.date().isoformat()
    if not a.force and not is_trading_day(now.date()):
        return heartbeat({"date": today, "result": "skip_non_trading_day"})
    got = landed_date()
    if got == today and not a.force:
        return heartbeat({"date": today, "result": "landed", "market_tw_data_date": got})
    start_utc = (datetime(now.year, now.month, now.day, tzinfo=TW).astimezone(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rid = cloud_running(start_utc)
    if rid and not a.force:
        return heartbeat({"date": today, "result": "cloud_running", "run_id": rid, "market_tw_data_date": got})
    if a.check:
        return heartbeat({"date": today, "result": "not_landed_check_only", "market_tw_data_date": got})
    steps, add_line = load_steps()
    if a.only:
        steps = [x for x in steps if any(k in x.get("name", "") for k in a.only)]
    t0 = time.time()
    prepare_worktree()
    res = run_steps(steps, bash_exe())
    out = commit_push(add_line, today)
    after = None
    try:
        after = json.loads((WT / "data" / "market_tw.json").read_text(encoding="utf-8")).get("data_date")
    except Exception as e:
        print("warn: 讀 market_tw 失敗", e)
    fails = [r["step"] for r in res if r.get("rc")]
    heartbeat({"date": today, "result": "catchup_ran", "market_tw_data_date_before": got,
               "market_tw_data_date_after": after, "steps": len(res), "failed_steps": fails,
               "minutes": round((time.time() - t0) / 60, 1), **out})
    sh(["git", "worktree", "remove", "--force", str(WT)])
    return 0 if out.get("commit") or out.get("note") == "無變動" else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
