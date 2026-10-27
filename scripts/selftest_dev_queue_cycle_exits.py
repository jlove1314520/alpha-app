# -*- coding: utf-8 -*-
"""收件匣 026 自測：DevQueue 每條出口都寫 cycle end（不准無聲結束）＋cc_push 抓「有 start 沒 end」。

真的跑 C:/alpha/run-dev-queue-cycle.ps1，但用環境變數 ALPHA_DQ_SELFTEST_ROOT 指到暫存假 repo：
裡面的 dev_queue_runner／cc_push／鎖／用量閘門都是假的（照環境變數回指定碼），claude 換成馬上 exit 0 的 claude_stub.cmd。
不碰真 repo、不呼叫 claude、不 push（暫存目錄自己 git init、沒有 remote）。檢查：
①check_collision 印 WARN＋PROCEED（exit 0）→ 走完 lock→prompt→claude→finally released→cycle end reason=OK
②YIELD（exit 1）→ cycle end reason=YIELD exit=0、不搶鎖
③看不懂的回傳碼（exit 7）→ cycle end reason=UNHANDLED_7 exit=7、不往下跑
④鎖被占 → LOCK_BUSY；用量閘門 → USAGE_GATE；佇列空 → QUEUE_EMPTY
⑤cc_push.silent_cycles：連 2 輪有 start 沒 end 才報、附最後一行；最新一輪（正在跑）不算
⑥dev_queue_runner._consecutive_idle_rounds：YIELD／LOCK_BUSY／USAGE_GATE／CRUNCH_GATE 不算也不打斷
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = Path("C:/alpha/run-dev-queue-cycle.ps1")
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import cc_push as C  # noqa: E402
import dev_queue_runner as D  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"｜{detail}" if detail and not ok else ""))


STUB_RUNNER = r'''import os, sys
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "check_collision":
    print("WARN: PENDING_QUEUE.md 內容已 ≥60 分鐘未變、無執行中程序提到它，視為殘留、照常執行；請人工確認後 commit 或還原")
    code = int(os.environ.get("STUB_COLLISION", "0"))
    print("YIELD: 假讓路" if code == 1 else ("PROCEED: 假放行" if code == 0 else "???"))
    sys.exit(code)
if cmd == "prompt":
    open(os.path.join(os.path.dirname(__file__), "..", "research", "DEV_QUEUE_PROMPT.txt"), "w", encoding="utf-8").write("stub")
    print("PROMPT_OK")
    sys.exit(int(os.environ.get("STUB_PROMPT", "0")))
print("stub " + cmd)
'''
STUB_LOCK = r'''import os, sys
if sys.argv[1] == "acquire":
    if os.environ.get("STUB_LOCK", "0") != "0":
        print("LOCK_HELD"); sys.exit(1)
    open(os.path.join(os.path.dirname(__file__), ".devqueue.lock"), "w").write("1|t|" + os.environ["ALPHA_CYCLE_ID"])
    print("LOCK_ACQUIRED")
'''
STUB_USAGE = r'''import os, sys
if sys.argv[1] == "check" and os.environ.get("STUB_USAGE", "0") != "0":
    print("用量上限 假"); sys.exit(1)
'''
STUB_CRUNCH = "import sys\nsys.exit(1)\n"          # active → 不在趕工
STUB_GITLOCK = "print('LOCK token=abc')\n"            # 直接拿到 git 鎖，免得收尾等 2 分鐘
NOOP = "pass\n"


def make_repo(tmp: Path) -> Path:
    (tmp / "scripts").mkdir(parents=True)
    (tmp / "research").mkdir()
    files = {
        "scripts/dev_queue_runner.py": STUB_RUNNER, "scripts/cc_push.py": "print('cc stub')\n",
        "scripts/dev_queue_crunch.py": STUB_CRUNCH, "scripts/claude_usage_gate.py": STUB_USAGE,
        "scripts/claude_auth_classifier.py": NOOP, "scripts/update_claude_launcher_heartbeat.py": NOOP,
        "scripts/local_git_commit.py": NOOP, "research/marathon_lock.py": STUB_LOCK,
        "research/git_op_lock.py": STUB_GITLOCK, "claude_stub.cmd": "@exit /b 0\r\n",
    }
    for rel, body in files.items():
        (tmp / rel).write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    return tmp


def run_cycle(**stub) -> str:
    with tempfile.TemporaryDirectory(prefix="dq_exits_") as d:
        repo = make_repo(Path(d) / "repo")
        env = dict(os.environ, ALPHA_DQ_SELFTEST_ROOT=str(repo), **{f"STUB_{k.upper()}": str(v) for k, v in stub.items()})
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WRAPPER)],
                       env=env, capture_output=True, timeout=240)
        return (repo / "research" / "dev_queue_cycle.log").read_text(encoding="utf-8-sig", errors="replace")


def end_of(log: str):
    m = re.findall(r"DevQueue cycle end: \S+ \S+ cycle_id=\S+ reason=(\S+) exit=(-?\d*) ", log)
    return m[-1] if m else None


if not WRAPPER.exists():
    check("wrapper 存在", False, str(WRAPPER))
else:
    log = run_cycle(collision=0, prompt=0)
    steps = ["check_collision: WARN", "lock: LOCK_ACQUIRED", "prompt: PROMPT_OK", "finally: released .devqueue.lock"]
    pos = [log.find(s) for s in steps]
    check("① WARN＋PROCEED 走完 lock→prompt→claude→finally→cycle end OK",
          all(p >= 0 for p in pos) and pos == sorted(pos) and end_of(log) == ("OK", "0"), log[-600:])
    log = run_cycle(collision=1)
    check("② YIELD → cycle end reason=YIELD exit=0、不搶鎖", end_of(log) == ("YIELD", "0") and "lock:" not in log, log[-400:])
    log = run_cycle(collision=7)
    check("③ 看不懂的碼 7 → UNHANDLED_7、不往下跑", end_of(log) == ("UNHANDLED_7", "7") and "lock:" not in log, log[-400:])
    log = run_cycle(collision=0, lock=1)
    check("④a 鎖被占 → LOCK_BUSY", end_of(log) == ("LOCK_BUSY", "0"), log[-400:])
    log = run_cycle(collision=0, usage=1)
    check("④b 用量閘門 → USAGE_GATE", end_of(log) == ("USAGE_GATE", "0"), log[-400:])
    log = run_cycle(collision=0, prompt=3)
    check("④c 佇列空 → QUEUE_EMPTY", end_of(log) == ("QUEUE_EMPTY", "") and "finally: released" in log, log[-400:])


def start(cid):
    return f"\n===== DevQueue cycle start: 2026-10-27 15:31:02 cycle_id={cid} =====\ncc_push: {{}}\n"


def end(cid, r="OK"):
    return f"===== DevQueue cycle end: 2026-10-27 16:00:00 cycle_id={cid} reason={r} exit=0 duration_min=1 =====\n"


two_silent = start("a") + end("a") + start("b") + "check_collision: WARN: x\n" + start("c") + "check_collision: 卡在這\n" + start("now")
s = C.silent_cycles(two_silent)
check("⑤a 連 2 輪沒 end → 報、附最後一行", [c for c, _ in s] == ["b", "c"] and s[-1][1] == "check_collision: 卡在這", str(s))
check("⑤b 只有 1 輪沒 end → 不報", C.silent_cycles(start("a") + end("a") + start("b") + start("now")) == [])
check("⑤c 最新一輪正在跑不算", C.silent_cycles(start("a") + end("a") + start("b") + end("b", "YIELD") + start("now")) == [])
overlap = start("a") + start("b") + end("b", "LOCK_BUSY") + end("a") + start("now")
check("⑤d 長輪次重疊（end 落在下一輪 start 之後）不誤報", C.silent_cycles(overlap) == [])
check("⑤e CRLF log 也認得", [c for c, _ in C.silent_cycles(two_silent.replace("\n", "\r\n"))] == ["b", "c"])

idle = "".join(end(str(i), r) for i, r in enumerate(["OK", "QUEUE_EMPTY", "LOCK_BUSY", "GATED", "YIELD", "USAGE_GATE", "CRUNCH_GATE"]))
check("⑥ 讓路／閘門／鎖被占不算也不打斷連續空轉", D._consecutive_idle_rounds(idle) == 2, str(D._consecutive_idle_rounds(idle)))

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} PASS")
sys.exit(1 if bad else 0)
