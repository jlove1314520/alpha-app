"""先.三十一-二：把去識別化心跳以「單檔 commit」推上公開 repo（不碰工作目錄、不推其他本機 commit）。
來源：research/data/auto_trading/auto_heartbeat.json（git 忽略）。目標：data/auto_heartbeat.json。
流程：逐欄位隱私檢查 -> 與遠端內容相同則略過 -> 以暫時 index 在 origin/main 之上建單檔 commit -> push。
任何失敗只印警告並 exit 0（守門員自己的失敗不得拖垮排程，CLAUDE.md 十二）。"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SRC = REPO / "research" / "data" / "auto_trading" / "auto_heartbeat.json"
DST = "data/auto_heartbeat.json"
TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00")
CODE = re.compile(r"[A-Z_]{2,32}")
TASKS = {"run", "settle"}


def privacy_check(doc) -> str | None:
    """回傳 None 代表通過，否則回傳第一個違規原因。白名單式：只認這幾個欄位與格式。"""
    if not isinstance(doc, dict) or not ({"schema", "updated_at", "events"} <= set(doc) <= {"schema", "updated_at", "events", "installed_at"}):
        return "頂層欄位不是 schema/updated_at/events(/installed_at)"
    if "installed_at" in doc and not (isinstance(doc["installed_at"], str) and TS.fullmatch(doc["installed_at"])):
        return "installed_at 格式不符"
    if doc["schema"] != 1:
        return "schema 不是 1"
    if not (isinstance(doc["updated_at"], str) and TS.fullmatch(doc["updated_at"])):
        return "updated_at 格式不符"
    ev = doc["events"]
    if not isinstance(ev, list) or len(ev) > 100:
        return "events 不是 list 或過長"
    for i, e in enumerate(ev):
        if not isinstance(e, dict) or set(e) != {"ts", "task", "code"}:
            return f"events[{i}] 欄位不是 ts/task/code"
        if not (isinstance(e["ts"], str) and TS.fullmatch(e["ts"])):
            return f"events[{i}].ts 格式不符"
        if e["task"] not in TASKS:
            return f"events[{i}].task 不在白名單"
        if not (isinstance(e["code"], str) and CODE.fullmatch(e["code"])):
            return f"events[{i}].code 格式不符"
    return None


def git(*a, env=None, check=True):
    return subprocess.run(["git", *a], cwd=REPO, env=env, capture_output=True, text=True, timeout=60, check=check)


def main() -> int:
    try:
        if not SRC.exists():
            print("[publish_heartbeat] 沒有來源檔，略過")
            return 0
        raw = SRC.read_text(encoding="utf-8")
        why = privacy_check(json.loads(raw))
        if why:
            print(f"[publish_heartbeat] 隱私檢查未通過，不發布：{why}")
            return 0
        git("fetch", "origin", "main")
        cur = git("show", f"origin/main:{DST}", check=False)
        if cur.returncode == 0 and cur.stdout == raw:
            print("[publish_heartbeat] 與遠端相同，略過")
            return 0
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(td) / "idx"))
            git("read-tree", "origin/main", env=env)
            blob = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"], cwd=REPO, input=raw, capture_output=True, text=True,
                encoding="utf-8", timeout=60, check=True).stdout.strip()
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{DST}", env=env)
            tree = git("write-tree", env=env).stdout.strip()
            msg = ("自動交易排程去識別化心跳（只含時間、任務名、結果代碼）\n\n"
                   "排程步驟會改寫 data/auto_heartbeat.json；已確認 data/ 在 dev_queue_runner.MACHINE_WRITTEN 的 ^data/ 樣式內，"
                   "且此 commit 以暫時 index 建立、不碰本機工作目錄。\n\n"
                   "Co-Authored-By: Claude Code <noreply@anthropic.com>\n"
                   "Claude-Session: https://claude.ai/code/session_01LQWLqXmnXb1bxX6YFEpKr8\n")
            commit = git("-c", "user.name=alpha-auto-heartbeat", "-c", "user.email=noreply@anthropic.com",
                         "commit-tree", tree, "-p", "origin/main", "-m", msg, env=env).stdout.strip()
        r = git("push", "origin", f"{commit}:refs/heads/main", check=False)
        print("[publish_heartbeat] push", "OK" if r.returncode == 0 else f"失敗 rc={r.returncode}")
    except Exception as e:
        print(f"[publish_heartbeat] 降級為警告：{type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
