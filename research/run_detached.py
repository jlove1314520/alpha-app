# -*- coding: utf-8 -*-
"""馬拉松重度工作的「脫離 session」執行器（2026-09-05，總司令核准提案選項1的修法A＋B）。

**為什麼需要這支**：馬拉松每輪是一個 `claude -p` session，session 會被 `--max-budget-usd` 或
wall-clock 超時砍掉；砍掉時 Bash 工具的子行程一起陪葬——這就是第356輪「背景回測消失、無CSV、
無錯誤訊息」的機制（見 `PROPOSAL_2026-09-05_marathon_process_hardening.md`）。
這支把重度工作（回測、隨機對照組、大樣本載入）交給一個**跟 session 完全脫鉤**的看門狗行程去跑，
session 只負責「投遞」與「下一輪收成」，session 死掉工作照樣跑完。

**用法（輪次裡只會用到這幾個）**：
    python research/run_detached.py submit --name loo_no_low_vol --timeout-min 40 --expect data/x.csv -- python -u research/deep_dive_x.py
    python research/run_detached.py status            # 列出所有工作（running/finished/failed/timeout/orphaned）
    python research/run_detached.py status --json     # 給 marathon_brief.py 用
    python research/run_detached.py wait <job_id> --max-min 4   # session 內最多等4分鐘，沒完就先收工
    python research/run_detached.py reap              # 把「看門狗 pid 已死但狀態還是 running」的標成 orphaned（重開機後用）
    python research/run_detached.py log <job_id> --tail 40      # 看工作 log 尾巴

**登記簿** `research/data/jobs.json`（gitignore）：每筆 {job_id, name, cmd, cwd, pid(看門狗), child_pid, started_at,
ended_at, timeout_min, status, exit_code, log, expect, expect_exists, submitted_by}。狀態機：
running → finished（exit 0）/ failed（exit≠0）/ timeout（超過 timeout_min 被看門狗砍）/ orphaned（看門狗本身死了）。

**脫鉤的實作**：`submit` 用 `subprocess.Popen(..., creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP|CREATE_BREAKAWAY_FROM_JOB,
close_fds=True, stdin/stdout/stderr 全部不繼承)` 啟動一個 `python run_detached.py _watchdog <job_id>` 看門狗；看門狗再啟動真正
的指令並等它結束或逾時。`CREATE_BREAKAWAY_FROM_JOB` 是關鍵：Claude Code 的 Bash 工具把子行程放在會「關閉即殺」的 Windows Job
物件裡，不 breakaway 的話 session 一死看門狗也死。若 Job 不允許 breakaway（權限），退回不帶該旗標並在登記簿標
`breakaway=False`（誠實記錄「這個工作可能會陪葬」）。

**不做的事**：不會自動重跑失敗的工作、不會自己決定要跑什麼——那是輪次（協定第1節）的事。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = RESEARCH_DIR.parent
JOBS_PATH = RESEARCH_DIR / "data" / "jobs.json"
JOBS_LOG_DIR = RESEARCH_DIR / "data" / "jobs"
TW_TZ = timezone(timedelta(hours=8))

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000


def _now() -> str:
    return datetime.now(TW_TZ).isoformat(timespec="seconds")


def _load() -> list[dict]:
    if not JOBS_PATH.exists():
        return []
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save(jobs: list[dict]) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    for _ in range(5):  # Windows：另一個行程剛好在讀時 replace 會被拒，重試
        try:
            tmp.replace(JOBS_PATH)
            return
        except PermissionError:
            time.sleep(0.05)
    tmp.replace(JOBS_PATH)


def _update(job_id: str, **fields) -> dict | None:
    jobs = _load()
    for j in jobs:
        if j["job_id"] == job_id:
            j.update(fields)
            _save(jobs)
            return j
    return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=10).stdout
        return str(pid) in out
    except Exception:
        return False


# ----------------------------------------------------------------------------- submit
def cmd_submit(args: argparse.Namespace) -> int:
    if not args.cmd:
        print("submit 需要在 -- 之後給指令，例如：submit --name x -- python -u research/foo.py", file=sys.stderr)
        return 2
    job_id = datetime.now(TW_TZ).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    JOBS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = JOBS_LOG_DIR / f"{job_id}.log"
    job = {
        "job_id": job_id, "name": args.name, "cmd": args.cmd, "cwd": str(Path(args.cwd or REPO_ROOT).resolve()),
        "pid": None, "child_pid": None, "started_at": _now(), "ended_at": None,
        "timeout_min": args.timeout_min, "status": "running", "exit_code": None,
        "log": str(log_path), "expect": args.expect, "expect_exists": None,
        "submitted_by": args.submitted_by or os.environ.get("ALPHA_ROUND", "unknown"), "breakaway": None,
    }
    jobs = _load()
    running = [j for j in jobs if j["status"] == "running"]
    if running and not args.allow_concurrent:
        print(f"REFUSED: 已有 {len(running)} 個工作在跑（{[j['name'] for j in running]}），協定規定不並行重度工作；"
              f"要硬跑加 --allow-concurrent（會搶CPU，請寫明理由）")
        return 3
    jobs.append(job)
    _save(jobs)

    watchdog_cmd = [sys.executable, str(Path(__file__).resolve()), "_watchdog", job_id]
    flags_full = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB | CREATE_NO_WINDOW
    flags_fallback = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    breakaway = True
    try:
        p = subprocess.Popen(watchdog_cmd, cwd=job["cwd"], creationflags=flags_full, close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        breakaway = False
        p = subprocess.Popen(watchdog_cmd, cwd=job["cwd"], creationflags=flags_fallback, close_fds=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _update(job_id, pid=p.pid, breakaway=breakaway)
    print(f"SUBMITTED {job_id} name={args.name} watchdog_pid={p.pid} breakaway={breakaway} timeout={args.timeout_min}min log={log_path}")
    if not breakaway:
        print("WARNING: 這個環境不允許 CREATE_BREAKAWAY_FROM_JOB，看門狗仍在 session 的 Job 裡，session 被砍時可能陪葬", file=sys.stderr)
    return 0


# ----------------------------------------------------------------------------- watchdog（脫鉤行程）
def cmd_watchdog(args: argparse.Namespace) -> int:
    job = next((j for j in _load() if j["job_id"] == args.job_id), None)
    if not job:
        return 2
    log_path = Path(job["log"])
    with open(log_path, "ab", buffering=0) as logf:
        logf.write(f"[run_detached] {_now()} start job={job['job_id']} name={job['name']} cmd={job['cmd']} timeout={job['timeout_min']}min\n".encode("utf-8"))
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUNBUFFERED", "1")
        try:
            child = subprocess.Popen(job["cmd"], cwd=job["cwd"], stdout=logf, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, env=env, creationflags=CREATE_NO_WINDOW)
        except Exception as e:  # noqa: BLE001
            logf.write(f"[run_detached] {_now()} 啟動失敗: {type(e).__name__}: {e}\n".encode("utf-8"))
            _update(job["job_id"], status="failed", ended_at=_now(), exit_code=-1)
            return 1
        _update(job["job_id"], child_pid=child.pid)
        deadline = time.time() + job["timeout_min"] * 60
        status, code = "finished", None
        while True:
            code = child.poll()
            if code is not None:
                status = "finished" if code == 0 else "failed"
                break
            if time.time() > deadline:
                logf.write(f"[run_detached] {_now()} TIMEOUT 超過 {job['timeout_min']} 分鐘，taskkill /T /F {child.pid}\n".encode("utf-8"))
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
                status, code = "timeout", -9
                break
            time.sleep(2)
        expect_exists = None
        if job.get("expect"):
            expect_exists = (Path(job["cwd"]) / job["expect"]).exists()
        logf.write(f"[run_detached] {_now()} end status={status} exit_code={code} expect_exists={expect_exists}\n".encode("utf-8"))
        _update(job["job_id"], status=status, exit_code=code, ended_at=_now(), expect_exists=expect_exists)
    return 0


# ----------------------------------------------------------------------------- status / wait / reap / log
def _fmt_age(started: str, ended: str | None) -> str:
    try:
        s = datetime.fromisoformat(started)
        e = datetime.fromisoformat(ended) if ended else datetime.now(TW_TZ)
        return f"{(e - s).total_seconds() / 60:.1f}min"
    except Exception:
        return "?"


def cmd_status(args: argparse.Namespace) -> int:
    jobs = _load()
    if args.json:
        print(json.dumps(jobs, ensure_ascii=False, indent=1))
        return 0
    if not jobs:
        print("（登記簿是空的：目前沒有任何脫離session的工作）")
        return 0
    recent = jobs[-args.last:] if args.last else jobs
    for j in recent:
        alive = _pid_alive(j.get("pid")) if j["status"] == "running" else None
        print(f"{j['job_id']}  {j['status']:8}  {j['name']:<32} 耗時={_fmt_age(j['started_at'], j.get('ended_at')):>8}  "
              f"exit={j.get('exit_code')}  expect_exists={j.get('expect_exists')}  watchdog_alive={alive}  breakaway={j.get('breakaway')}")
    running = [j for j in jobs if j["status"] == "running"]
    print(f"— running={len(running)}  total={len(jobs)}")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    deadline = time.time() + args.max_min * 60
    while time.time() < deadline:
        job = next((j for j in _load() if j["job_id"] == args.job_id), None)
        if not job:
            print("NOT_FOUND")
            return 2
        if job["status"] != "running":
            print(f"DONE status={job['status']} exit={job.get('exit_code')} expect_exists={job.get('expect_exists')} log={job['log']}")
            return 0 if job["status"] == "finished" else 1
        time.sleep(5)
    print(f"STILL_RUNNING（已等{args.max_min}分鐘，session不要再等，寫進state下一輪收成）")
    return 4


def cmd_reap(args: argparse.Namespace) -> int:
    jobs = _load()
    n = 0
    for j in jobs:
        if j["status"] == "running" and not _pid_alive(j.get("pid")):
            j["status"] = "orphaned"
            j["ended_at"] = _now()
            if j.get("expect"):
                j["expect_exists"] = (Path(j["cwd"]) / j["expect"]).exists()
            n += 1
    if n:
        _save(jobs)
    print(f"reaped orphaned={n}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    job = next((j for j in _load() if j["job_id"] == args.job_id), None)
    if not job:
        print("NOT_FOUND")
        return 2
    p = Path(job["log"])
    if not p.exists():
        print("（log檔尚未產生）")
        return 0
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(lines[-args.tail:]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="馬拉松重度工作脫離session執行器（見檔頭docstring）")
    sub = ap.add_subparsers(dest="sub", required=True)
    s = sub.add_parser("submit"); s.add_argument("--name", required=True); s.add_argument("--timeout-min", type=int, default=40)
    s.add_argument("--expect", default=None, help="預期產出檔案（相對cwd），結束時記錄是否存在")
    s.add_argument("--cwd", default=None); s.add_argument("--submitted-by", default=None); s.add_argument("--allow-concurrent", action="store_true")
    s.add_argument("cmd", nargs=argparse.REMAINDER, help="-- 之後的實際指令")
    s.set_defaults(fn=cmd_submit)
    w = sub.add_parser("_watchdog"); w.add_argument("job_id"); w.set_defaults(fn=cmd_watchdog)
    st = sub.add_parser("status"); st.add_argument("--json", action="store_true"); st.add_argument("--last", type=int, default=15); st.set_defaults(fn=cmd_status)
    wt = sub.add_parser("wait"); wt.add_argument("job_id"); wt.add_argument("--max-min", type=float, default=4); wt.set_defaults(fn=cmd_wait)
    rp = sub.add_parser("reap"); rp.set_defaults(fn=cmd_reap)
    lg = sub.add_parser("log"); lg.add_argument("job_id"); lg.add_argument("--tail", type=int, default=40); lg.set_defaults(fn=cmd_log)
    args = ap.parse_args()
    if args.sub == "submit" and args.cmd and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
