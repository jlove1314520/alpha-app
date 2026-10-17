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
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
sys.path.insert(0, str(ROOT / "research"))
OUT = ROOT / "data" / "orphan_scan.json"
OUT_REL = "data/orphan_scan.json"
PUSH_STATE = ROOT / "research" / ".orphan_scan_push.json"
LOCK_PY = ROOT / "research" / "git_op_lock.py"
TZ = timezone(timedelta(hours=8))


def _git(*a, timeout=120):
    try:  # 先.一〇三-15ag：改走 local_git_commit.run_git（逾時殺整棵行程樹、禁止互動式認證），匯入失敗退回原寫法（十二節）
        sys.path.insert(0, str(ROOT / "scripts"))
        from local_git_commit import run_git
        return run_git(a, cwd=ROOT, timeout=timeout)
    except ImportError:
        pass
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _commit_push(msg: str) -> str:
    got = False
    try:
        r = subprocess.run([sys.executable, str(LOCK_PY), "acquire"], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        got = r.returncode == 0
        m = re.search(r"token=(\w+)", r.stdout or "")  # 先.八十一-34：持有者憑證
        tok = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        got, tok = False, None
    try:
        _git("add", OUT_REL)
        c = _git("commit", "-o", OUT_REL, "-m", msg)
        if c.returncode != 0:
            return f"commit 無變更或失敗：{(c.stdout + c.stderr).strip()[:120]}"
        _pull_autostash_safe()
        p = _git("push", timeout=180)
        return "已 push" if p.returncode == 0 else f"push 失敗：{(p.stdout + p.stderr).strip()[:120]}"
    except Exception as e:  # noqa: BLE001
        return f"git 例外（已降級）：{type(e).__name__}: {e}"
    finally:
        if got:
            try:
                subprocess.run([sys.executable, str(LOCK_PY), "release", *(["--token", tok] if tok else [])], cwd=ROOT, capture_output=True, timeout=60)
            except Exception:  # noqa: BLE001
                pass


STUCK_HOURS = 2
_STUCK_NAMES = {"git.exe", "git-remote-https.exe", "git-credential-manager.exe"}


def classify_stuck_git(rows: list[dict], now: datetime, hours: float = STUCK_HOURS) -> list[dict]:
    """先.一〇三-15ah：挑出「跑超過 hours 小時」的 git 系行程與心跳提交 python（10/15 有 17 支卡 30 小時沒人發現，
    見先.一〇三-15ad）。rows＝Get-CimInstance 的 Name／ProcessId／CommandLine／Start（本機時間 ISO）。
    只回 PID、名稱、啟動時間、已跑幾小時、種類，不回命令列；只列出，不結束任何程序。"""
    out = []
    for r in rows or []:
        name = (r.get("Name") or "").lower()
        cmd = r.get("CommandLine") or ""
        if name in _STUCK_NAMES:
            kind = "credential-manager" if "credential" in name or "credential-manager" in cmd else ("push" if " push" in cmd or "remote-https" in cmd else "git")
        elif name.startswith("python") and ("commit_local_heartbeats" in cmd or "local_git_commit" in cmd):
            kind = "heartbeat-python"
        else:
            continue
        try:
            started = datetime.fromisoformat(r.get("Start")).replace(tzinfo=now.tzinfo)
        except (TypeError, ValueError):
            continue
        age = (now - started).total_seconds() / 3600
        if age >= hours:
            out.append({"pid": r.get("ProcessId"), "name": name, "kind": kind, "started": r.get("Start"), "age_hours": round(age, 1)})
    return sorted(out, key=lambda x: x["pid"] or 0)


def find_stuck_git(now: datetime) -> list[dict]:
    if sys.platform != "win32":
        return []
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(git|git-remote-https|git-credential-manager|python[0-9.]*)[.]exe$' } | "
          "Select-Object Name,ProcessId,CommandLine,@{n='Start';e={$_.CreationDate.ToString('yyyy-MM-ddTHH:mm:ss')}} | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout.strip()
    rows = json.loads(out) if out else []
    return classify_stuck_git([rows] if isinstance(rows, dict) else rows, now)


_SHELL_NAMES = {"bash.exe", "sh.exe"}


def classify_orphan_shells(rows: list[dict], now: datetime, hours: float = STUCK_HOURS) -> list[dict]:
    """先.一〇九-11：挑出「父行程已不存在、跑超過 hours 小時」的 Git Bash 外殼。10/16 實測有 5 支，都是舊 Claude 工作階段
    用 `(python -m http.server 8792 &)` 背景啟動冒煙伺服器後，工作階段結束、bash 跟著 http.server 一起留下。
    rows＝Get-CimInstance 的 Name／ProcessId／ParentProcessId／Start（本機時間 ISO），外加全部存活 PID（all_pids）。
    子行程數（children）只算 rows 裡 ParentProcessId 指向它的。只回 PID、父 PID、啟動時間、小時數、子行程數，不回命令列；
    只列出，不結束任何程序。父 PID 被別的行程重用時會漏抓（寧可漏抓，不誤判）。"""
    rows = rows or []
    alive = {r.get("ProcessId") for r in rows}
    out = []
    for r in rows:
        if (r.get("Name") or "").lower() not in _SHELL_NAMES:
            continue
        if r.get("ParentProcessId") in alive:
            continue
        try:
            started = datetime.fromisoformat(r.get("Start")).replace(tzinfo=now.tzinfo)
        except (TypeError, ValueError):
            continue
        age = (now - started).total_seconds() / 3600
        if age >= hours:
            kids = sum(1 for k in rows if k.get("ParentProcessId") == r.get("ProcessId"))
            out.append({"pid": r.get("ProcessId"), "parent_pid": r.get("ParentProcessId"), "name": (r.get("Name") or "").lower(),
                        "started": r.get("Start"), "age_hours": round(age, 1), "children": kids})
    return sorted(out, key=lambda x: x["pid"] or 0)


def find_orphan_shells(now: datetime) -> list[dict]:
    if sys.platform != "win32":
        return []
    ps = ("Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,"
          "@{n='Start';e={if($_.CreationDate){$_.CreationDate.ToString('yyyy-MM-ddTHH:mm:ss')}}} | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90).stdout.strip()
    rows = json.loads(out) if out else []
    return classify_orphan_shells([rows] if isinstance(rows, dict) else rows, now)


def main(commit: bool = True, notify=None) -> int:
    import mem_guard
    now = datetime.now(TZ)
    orphans = mem_guard.find_orphan_python_workers()
    doc = {"checked_at": now.isoformat(timespec="seconds"), "count": len(orphans),
           "total_private_mb": sum(o["private_mb"] for o in orphans), "orphans": orphans,
           "note": "父行程已不存在的 python multiprocessing 工作行程；巡檢只列出與告警，不會自動結束（要結束須總司令核准）",
           "source": "scripts/orphan_process_scan.py（AlphaOrphanScan 每日 03:00）"}
    try:  # 先.一〇三-15ah：卡住的 git／心跳提交行程；量測失敗只降級（十二節）
        stuck = find_stuck_git(now)
    except Exception as e:  # noqa: BLE001
        print(f"WARN 卡住 git 行程量測失敗（{type(e).__name__}），本輪略過")
        stuck = []
    doc["stuck_git"] = stuck
    doc["stuck_git_note"] = f"跑超過 {STUCK_HOURS} 小時的 git／git-credential-manager／心跳提交 python；只列出，不自動結束"
    try:  # 先.一〇九-11：父行程已不在的 Git Bash 外殼（常帶著背景 http.server）；量測失敗只降級（十二節）
        shells = find_orphan_shells(now)
    except Exception as e:  # noqa: BLE001
        print(f"WARN 孤兒 bash 量測失敗（{type(e).__name__}），本輪略過")
        shells = []
    doc["orphan_shells"] = shells
    doc["orphan_shells_note"] = f"父行程已不存在、跑超過 {STUCK_HOURS} 小時的 bash.exe（多半是舊工作階段背景啟動的冒煙伺服器）；只列出，不自動結束"
    old = {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    changed = (sorted(o["pid"] for o in old.get("orphans", [])) != sorted(o["pid"] for o in orphans) or "checked_at" not in old
               or sorted(o["pid"] for o in old.get("stuck_git", [])) != sorted(o["pid"] for o in stuck)
               or sorted(o["pid"] for o in old.get("orphan_shells", [])) != sorted(o["pid"] for o in shells))
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
                PUSH_STATE.write_text(json.dumps({**st, "key": key, "date": now.date().isoformat()}), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                print(f"WARN 推播失敗（{type(e).__name__}）")
    if shells:
        print(f"孤兒 bash 外殼：{len(shells)} 支（最久 {max(o['age_hours'] for o in shells)} 小時；未推播、只列出）：" +
              "、".join(f"PID {o['pid']}（父 {o['parent_pid']}，{o['started']} 起，子行程 {o['children']}）" for o in shells))
    if stuck:
        print(f"卡住的 git／心跳提交行程：{len(stuck)} 支（最久 {max(o['age_hours'] for o in stuck)} 小時）")
        key = "git:" + hashlib.sha1(",".join(str(o["pid"]) for o in stuck).encode()).hexdigest()[:12]
        try:
            st = json.loads(PUSH_STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {}
        if st.get("git_key") != key or st.get("git_date") != now.date().isoformat():
            body = f"有 {len(stuck)} 支 git／心跳提交行程跑超過 {STUCK_HOURS} 小時（可能卡在認證視窗）；未自動結束，請決定是否清除"
            try:
                if notify:
                    notify("git 行程卡住", body)
                else:
                    import web_push
                    web_push.send("git 行程卡住", body, kind="orphan")
                PUSH_STATE.write_text(json.dumps({**st, "git_key": key, "git_date": now.date().isoformat()}), encoding="utf-8")
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
