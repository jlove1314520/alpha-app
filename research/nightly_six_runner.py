"""先.七十七-2（2026-10-11）：常備.開發-6（題材動能榜／未來性榜既有榜單重新驗證回測）夜間自動開跑。

工作排程器 AlphaNightlySix 每晚 02:00～06:00 每 20 分鐘叫一次 `check`：
  - 已有結果檔（research/data/momentum_future_board_pit_backtest.json，含 boards）→ 什麼都不做
  - 已在跑（狀態檔記的 PID 還活著）→ 什麼都不做
  - mem_guard.preflight()（可用記憶體 ≥4.5GB，門檻與執行中 3GB 安全閥都不變）通過 → 另開一個獨立行程 `run`
    （detached，排程結束不會被砍），本次記為「今晚已開跑」
  - 不通過 → 記下今晚最高可用記憶體；最後一次檢查（05:40 以後）仍未開跑＝今晚不足。連續 3 晚不足才推播請總司令關程式
    （同一段連續只推一次）
`run`：跑 run_momentum_future_board_pit_backtest.py --draws 20（約 3～5 小時）→ 讀結果推播兩榜判定 →
  把 PENDING_QUEUE 常備.開發-6 由 [!] 改回 [ ] 並註明「回測已跑完，待登記與 App 標籤」，交給 DevQueue 完成
  TRIALS_LEDGER 登記（reverification=True）與 App「回測通過／未通過」標籤。
不碰真錢自動交易；CybexBot 等其他程序一律不動（只等記憶體夠）。自身失敗只記 log（十二節）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
TZ = timezone(timedelta(hours=8))
STATE = HERE / ".nightly6_state.json"
LOG = HERE / "nightly6.log"
RESULT = HERE / "data" / "momentum_future_board_pit_backtest.json"
SCRIPT = HERE / "run_momentum_future_board_pit_backtest.py"
QUEUE = ROOT / "PENDING_QUEUE.md"
LOCK_PY = HERE / "git_op_lock.py"
DRAWS = 20
LAST_CHECK_HHMM = (5, 40)
SHORT_NIGHTS_ALERT = 3


def log(msg: str) -> None:
    line = f"[{datetime.now(TZ).strftime('%m-%d %H:%M')}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def result_done() -> bool:
    try:
        return bool(json.loads(RESULT.read_text(encoding="utf-8")).get("boards"))
    except (OSError, ValueError):
        return False


def pid_alive(pid) -> bool:
    try:
        import mp_guard
        return bool(pid) and mp_guard._pid_alive(int(pid))
    except Exception:  # noqa: BLE001
        return False


def push(title: str, body: str) -> None:
    try:
        import web_push
        r = web_push.send(title, body, kind="nightly6")
        log(f"推播：{title}（{r}）")
    except Exception as e:  # noqa: BLE001
        log(f"推播失敗（{type(e).__name__}）")


def check(now: datetime | None = None, preflight=None, launcher=None, notify=None) -> str:
    now = now or datetime.now(TZ)
    notify = notify or push
    st = load_state()
    if result_done():
        log("結果檔已存在，-6 已跑完，不再開跑")
        return "DONE"
    if st.get("status") == "running" and pid_alive(st.get("pid")):
        log(f"已在跑（PID {st.get('pid')}，{st.get('started_at')} 開始）")
        return "RUNNING"
    night = (now - timedelta(hours=12)).strftime("%Y-%m-%d")  # 02:00～06:00 歸到前一晚的日期，跨午夜不分裂
    nights = st.setdefault("nights", {})
    n = nights.setdefault(night, {"checks": 0, "max_available_gb": 0.0, "started": False})
    if n["started"]:
        log(f"今晚（{night}）已開跑過，不重複開")
        return "ALREADY_STARTED"
    if preflight is None:
        import mem_guard
        preflight = mem_guard.preflight
    ok, gb, msg = preflight()
    n["checks"] += 1
    n["max_available_gb"] = round(max(n["max_available_gb"], gb if gb == gb else 0.0), 2)
    if ok:
        pid = (launcher or _launch)()
        n["started"] = True
        st.update(status="running", pid=pid, started_at=now.isoformat(timespec="seconds"), short_streak=0, alerted_streak=False)
        save_state(st)
        log(f"記憶體足夠（{msg}）→ 開跑 -6，PID {pid}")
        return "STARTED"
    log(f"記憶體不足（{msg}），等下一次檢查")
    # 只有夜間窗口的最後一次檢查（05:40～07:00）才算「今晚不足」；白天手動執行不算
    if LAST_CHECK_HHMM <= (now.hour, now.minute) < (7, 0) and not n.get("counted_short"):
        n["counted_short"] = True
        prev = (datetime.strptime(night, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        st["short_streak"] = (st.get("short_streak", 0) + 1) if (st.get("last_short_night") == prev) else 1
        st["last_short_night"] = night
        log(f"今晚（{night}）記憶體一直不足，連續第 {st['short_streak']} 晚")
        if st["short_streak"] >= SHORT_NIGHTS_ALERT and not st.get("alerted_streak"):
            st["alerted_streak"] = True
            notify("兩榜回測一直跑不了", f"連續 {st['short_streak']} 晚可用記憶體不到 4.5GB（最高 {n['max_available_gb']}GB），"
                   "請睡前關掉部分瀏覽器分頁或遊戲平台")
    save_state(st)
    return "SHORT"


def _launch() -> int:
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "run"], cwd=str(ROOT), creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return p.pid


def _commit(paths: list[str], msg: str) -> str:
    got, tok = False, None
    try:
        r = subprocess.run([sys.executable, str(LOCK_PY), "acquire"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        got = r.returncode == 0
        m = re.search(r"token=(\w+)", r.stdout or "")  # 先.八十一-34：持有者憑證
        tok = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        pass
    try:
        g = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)  # noqa: E731
        g("add", "-f", *paths)
        c = g("commit", "-o", *paths, "-m", msg)
        if c.returncode != 0:
            return "commit 無變更或失敗"
        g("pull", "--rebase", "--autostash")
        return "已 push" if g("push").returncode == 0 else "push 失敗"
    finally:
        if got:
            subprocess.run([sys.executable, str(LOCK_PY), "release", *(["--token", tok] if tok else [])], cwd=ROOT, capture_output=True, timeout=60)


def reopen_queue_item(summary: str) -> bool:
    try:
        s = QUEUE.read_text(encoding="utf-8")
        pat = re.compile(r"^- \[!\] (\*\*常備\.開發-6 .*)$", re.M)
        if len(pat.findall(s)) != 1:
            return False
        stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
        s = pat.sub(lambda m: "- [ ] " + m.group(1) + f"〔{stamp} 先.七十七-2 夜間自動開跑完成：{summary}；結果檔 research/data/momentum_future_board_pit_backtest.json，"
                    "待 DevQueue 登記 TRIALS_LEDGER（reverification=True）並更新 App 榜單「回測通過／未通過」標籤〕", s, count=1)
        QUEUE.write_text(s, encoding="utf-8", newline="\n")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"改回佇列失敗（{type(e).__name__}）")
        return False


def run() -> int:
    st = load_state()
    st.update(status="running", pid=os.getpid(), started_at=st.get("started_at") or datetime.now(TZ).isoformat(timespec="seconds"))
    save_state(st)
    log(f"開始執行 -6 回測（--draws {DRAWS}）")
    r = subprocess.run([sys.executable, str(SCRIPT), "--draws", str(DRAWS)], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    tail = (r.stdout or "")[-1500:] + (r.stderr or "")[-800:]
    (HERE / "data" / "nightly6_last_run.log").write_text(tail, encoding="utf-8")
    st = load_state()
    if r.returncode == 3:
        st.update(status="idle", pid=None)
        save_state(st)
        log("開跑前檢查：記憶體又不足（exit 3），下一次排程再試")
        return 3
    if r.returncode != 0 or not result_done():
        st.update(status="failed", pid=None, finished_at=datetime.now(TZ).isoformat(timespec="seconds"), exit_code=r.returncode)
        save_state(st)
        push("兩榜回測失敗", f"回測程式結束碼 {r.returncode}（可能被 3GB 安全閥中止）；明晚會再試")
        st["status"] = "idle"
        save_state(st)
        return r.returncode or 1
    res = json.loads(RESULT.read_text(encoding="utf-8"))
    names = {"momentum": "題材動能榜", "future": "未來性榜"}
    summary = "；".join(f"{names.get(b, b)} {v.get('verdict')}" for b, v in (res.get("boards") or {}).items())
    st.update(status="done", pid=None, finished_at=datetime.now(TZ).isoformat(timespec="seconds"), summary=summary)
    save_state(st)
    push("兩榜回測跑完", summary + "（既有榜單重新驗證，不調權重）")
    reopen_queue_item(summary)
    log("提交：" + _commit(["research/data/momentum_future_board_pit_backtest.json", "PENDING_QUEUE.md"],
                           f"常備.開發-6 夜間自動開跑完成：{summary}（先.七十七-2；待登記與 App 標籤）"))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        sys.exit(0 if cmd == "check" and check() else run() if cmd == "run" else 2)
    except Exception as e:  # noqa: BLE001
        log(f"WARN nightly_six_runner {cmd} 失敗（{type(e).__name__}: {e}）")
        sys.exit(0)
