# -*- coding: utf-8 -*-
"""先.二十-二：長工作（>20 分鐘）每 30 分鐘的進度心跳。

總司令 2026-10-05【先.二十】二：「任何預估超過 20 分鐘的抓取或計算，每 30 分鐘在
research/PROGRESS_HEARTBEAT.jsonl 追加一筆進度（已完成筆數／總筆數、預估剩餘時間）
並 commit＋push；**只 commit 心跳檔，不附帶其他變動**。」

「只 commit 心跳檔」用 `git commit -o <path>`（--only）達成——不帶 pathspec 的
`git commit` 會把整個暫存區一起送出，那正是 2026-09-18 `711a021d` 那次意外吃進
6 個不相干檔案的 bug。

守門員原則（CLAUDE.md 十二）：本腳本自身的任何失敗（計數失敗、git 衝突、push 被拒）
只印一行警告並繼續下一輪，絕不中斷被監看的長工作，也不重試到卡死。
git 操作搶 `research/git_op_lock.py` 那把鎖，避免與自走軌道的 wrapper 互踩。

用法：
  python scripts/long_job_progress_heartbeat.py --label "先.十八-二 SIC 全量" \
      --dir research/data/raw/sec_submissions --total 21315 --interval 1800
  （--dir 改 --count-cmd 可用任意 shell 指令取得已完成數）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _pull_autostash_safe() -> None:
    """先.一〇三-14w：pull --autostash 套回失敗時取回別人未提交的檔（scripts/local_git_commit.py）；匯入失敗退回原本的 pull（十二節）。"""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import local_git_commit as _lgc  # noqa: E402
        _lgc.pull_autostash_safe()
    except Exception as e:  # noqa: BLE001
        print(f"[autostash 取回] 警告：{type(e).__name__}: {e}，退回一般 pull", file=sys.stderr)
        subprocess.run(["git", "pull", "-q", "--rebase", "--autostash"], cwd=ROOT, capture_output=True, timeout=180)
HB = ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"
HB_REL = "research/PROGRESS_HEARTBEAT.jsonl"
LOCK_PY = ROOT / "research" / "git_op_lock.py"


def _count(args) -> int | None:
    try:
        if args.dir:
            d = ROOT / args.dir
            return sum(1 for _ in d.iterdir()) if d.exists() else 0
        if args.count_cmd:
            r = subprocess.run(args.count_cmd, shell=True, cwd=ROOT,
                               capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
            return int(r.stdout.strip().split()[0])
    except Exception as e:  # noqa: BLE001
        print(f"::warning::進度計數失敗（本輪跳過，不影響長工作）：{type(e).__name__}: {e}", flush=True)
    return None


def _git(*a, timeout=120):
    # 一律指定 utf-8：git 輸出含中文時，Windows 預設 cp950 會丟 UnicodeDecodeError
    try:  # 先.一〇三-15ag：改走 local_git_commit.run_git（逾時殺整棵行程樹、禁止互動式認證），匯入失敗退回原寫法（十二節）
        sys.path.insert(0, str(ROOT / "scripts"))
        from local_git_commit import run_git
        return run_git(a, cwd=ROOT, timeout=timeout)
    except ImportError:
        pass
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _commit_push(msg: str) -> str:
    got = False
    try:
        r = subprocess.run([sys.executable, str(LOCK_PY), "acquire"], cwd=ROOT,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        got = (r.returncode == 0)
        m = re.search(r"token=(\w+)", r.stdout or "")  # 先.八十一-34：持有者憑證
        tok = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        got, tok = False, None
    try:
        _git("add", HB_REL)
        c = _git("commit", "-o", HB_REL, "-m", msg)
        if c.returncode != 0:
            return f"commit 無變更或失敗：{(c.stdout + c.stderr).strip()[:120]}"
        _pull_autostash_safe()
        p = _git("push", timeout=180)
        return "已 push" if p.returncode == 0 else f"push 失敗：{(p.stdout + p.stderr).strip()[:120]}"
    except Exception as e:  # noqa: BLE001
        return f"git 例外（已降級，不影響長工作）：{type(e).__name__}: {e}"
    finally:
        if got:
            try:
                subprocess.run([sys.executable, str(LOCK_PY), "release", *(["--token", tok] if tok else [])], cwd=ROOT,
                               capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--dir")
    ap.add_argument("--count-cmd")
    ap.add_argument("--total", type=int, required=True)
    ap.add_argument("--interval", type=float, default=1800.0)
    ap.add_argument("--round", default="先.二十")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    n0 = _count(a) or 0
    while True:
        n = _count(a)
        el = time.time() - t0
        rate = ((n - n0) / el * 60) if (n is not None and el > 1) else None
        eta = ((a.total - n) / rate) if (rate and rate > 0 and n is not None and n < a.total) else None
        rec = {"ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
               "track": "interactive", "round": a.round, "status": "RUNNING",
               "item": (f"{a.label} 進度 {n}/{a.total}"
                        + (f"（{100.0 * n / max(1, a.total):.1f}%）" if n is not None else "（計數失敗）")
                        + (f"，約 {rate:.0f} 筆/分" if rate else "")
                        + (f"，預估剩餘 {eta:.0f} 分鐘" if eta is not None else
                           ("，已完成" if n is not None and n >= a.total else "")))}
        try:
            with open(HB, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out = _commit_push(f"長工作進度心跳：{a.label} {n}/{a.total}（先.二十-二，只 commit 心跳檔）")
        except Exception as e:  # noqa: BLE001
            out = f"寫心跳失敗（降級）：{type(e).__name__}: {e}"
        print(f"[{rec['ts']}] {rec['item']} → {out}", flush=True)
        if a.once or (n is not None and n >= a.total):
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
