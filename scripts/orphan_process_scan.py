"""先.七十一-2／-4（2026-10-11）：孤兒 python 工作行程巡檢——只列出與告警，絕不結束任何程序。

由工作排程器 AlphaOrphanScan 每日 03:00 執行（也可手動跑）。
- 用 research/mem_guard.find_orphan_python_workers() 找「父行程已不存在」的 multiprocessing worker。
- 結果寫 data/orphan_scan.json（只有 PID、父 PID、啟動時間、私有記憶體 MB；無命令列、無帳號路徑）。
  雲端 local_schedule_watchdog 每 30 分鐘寫 STATUS.json 時把它併進頂層 orphan_processes（App 設定頁可看）。
  只有「狀態改變」（孤兒數或 PID 集合變了）才 commit＋push，用 research/git_op_lock.py 的鎖＋git commit -o 只送本檔。
- 有孤兒 → Web Push 一則（同一組 PID 一天最多一則；kind=orphan 不受通知偏好靜音）。
- 自身任何失敗只印警告、exit 0（十二節：守門員失敗只降級）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
OUT = ROOT / "data" / "orphan_scan.json"
OUT_REL = "data/orphan_scan.json"
PUSH_STATE = ROOT / "research" / ".orphan_scan_push.json"
LOCK_PY = ROOT / "research" / "git_op_lock.py"
TZ = timezone(timedelta(hours=8))


def _git(*a, timeout=120):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _commit_push(msg: str) -> str:
    got = False
    try:
        r = subprocess.run([sys.executable, str(LOCK_PY), "acquire"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        got = r.returncode == 0
    except Exception:  # noqa: BLE001
        got = False
    try:
        _git("add", OUT_REL)
        c = _git("commit", "-o", OUT_REL, "-m", msg)
        if c.returncode != 0:
            return f"commit 無變更或失敗：{(c.stdout + c.stderr).strip()[:120]}"
        _git("pull", "--rebase", "--autostash", timeout=180)
        p = _git("push", timeout=180)
        return "已 push" if p.returncode == 0 else f"push 失敗：{(p.stdout + p.stderr).strip()[:120]}"
    except Exception as e:  # noqa: BLE001
        return f"git 例外（已降級）：{type(e).__name__}: {e}"
    finally:
        if got:
            try:
                subprocess.run([sys.executable, str(LOCK_PY), "release"], cwd=ROOT, capture_output=True, timeout=60)
            except Exception:  # noqa: BLE001
                pass


def main(commit: bool = True, notify=None) -> int:
    import mem_guard
    now = datetime.now(TZ)
    orphans = mem_guard.find_orphan_python_workers()
    doc = {"checked_at": now.isoformat(timespec="seconds"), "count": len(orphans),
           "total_private_mb": sum(o["private_mb"] for o in orphans), "orphans": orphans,
           "note": "父行程已不存在的 python multiprocessing 工作行程；巡檢只列出與告警，不會自動結束（要結束須總司令核准）",
           "source": "scripts/orphan_process_scan.py（AlphaOrphanScan 每日 03:00）"}
    old = {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    changed = sorted(o["pid"] for o in old.get("orphans", [])) != sorted(o["pid"] for o in orphans) or "checked_at" not in old
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"孤兒 python worker：{len(orphans)} 支，合計私有記憶體約 {doc['total_private_mb']}MB" +
          ("" if not orphans else "：" + "、".join(f"PID {o['pid']}（父 {o['parent_pid']}，{o['started']} 起）" for o in orphans)))
    if orphans:
        key = hashlib.sha1(",".join(str(o["pid"]) for o in sorted(orphans, key=lambda o: o["pid"])).encode()).hexdigest()[:12]
        try:
            st = json.loads(PUSH_STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {}
        if st.get("key") != key or st.get("date") != now.date().isoformat():
            body = f"發現 {len(orphans)} 支孤兒 python 程序，約佔 {doc['total_private_mb'] / 1024:.1f}GB；未自動結束，請決定是否清除"
            try:
                if notify:
                    notify("孤兒程序告警", body)
                else:
                    import web_push
                    web_push.send("孤兒程序告警", body, kind="orphan")
                PUSH_STATE.write_text(json.dumps({"key": key, "date": now.date().isoformat()}), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                print(f"WARN 推播失敗（{type(e).__name__}）")
    if commit and changed:
        print("data/orphan_scan.json：" + _commit_push(f"孤兒程序巡檢：{len(orphans)} 支（先.七十一-4，只列出不結束）"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(commit="--no-commit" not in sys.argv))
    except Exception as e:  # noqa: BLE001
        print(f"WARN orphan_process_scan 失敗（{type(e).__name__}: {e}），只降級")
        sys.exit(0)
