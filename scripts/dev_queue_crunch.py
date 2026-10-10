# -*- coding: utf-8 -*-
"""先.六十四（2026-10-11）DevQueue 趕工模式。

總司令裁示原文：「每 30 分鐘就繼續動作馬拉松趕工直到交辦的事都做完為止」。

一輪（run）啟動後循環：取下一項 → `claude -p` 只做這一項 → 結算（settle）→ 推播＋心跳 → 立刻取下一項，
直到：佇列沒有 DevQueue 能做的 `- [ ]`、碰到停下白名單（守門員擋下的項目標 [!] 後換下一項）、
Claude 額度用盡／登入過期、和其他軌道撞車、或本輪時間上限。同一項連續失敗兩次 → 標 [!]、換下一項。

心跳＝鎖檔 `research/.devqueue.lock` 的時間欄（pid|ts|cycle_id）：迴圈每 30 秒刷新一次，
執行中的 claude 若連續 20 分鐘沒有任何輸出就整棵行程樹砍掉（算該項失敗一次）。
所以「鎖存在但心跳超過 20 分鐘沒動」只可能是 wrapper 本身已經死掉（重開機、被砍），下一次排程
gate() 會清鎖重開，從佇列裡第一個未完成項續做。

不碰自動交易：不切換模式、不觸發真錢委託（提示詞照舊明列停下條件；本模組只排程、不下單）。
十二節：本模組任何偵測／推播／寫紀錄自身失敗都只降級成 log，不讓迴圈崩潰。

指令（wrapper 呼叫）：
    python scripts/dev_queue_crunch.py active            # exit 0＝趕工中（常備.開發還有 - [ ]），1＝否
    python scripts/dev_queue_crunch.py gate              # exit 0＝可以開新一輪（必要時已清掉中斷的鎖），1＝有輪次在跑、略過
    python scripts/dev_queue_crunch.py run               # 跑一輪趕工迴圈；exit 碼見 EXIT_*
    python scripts/dev_queue_crunch.py schedule crunch|normal   # 切換工作排程器頻率（30 分鐘／15 分鐘）
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(RESEARCH))
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
import dev_queue_runner as R  # noqa: E402

TZ = timezone(timedelta(hours=8))
LOCK = RESEARCH / ".devqueue.lock"
LOG = RESEARCH / "dev_queue_cycle.log"
CYCLES_DIR = RESEARCH / "data" / "dev_cycles"
HEARTBEAT = RESEARCH / "PROGRESS_HEARTBEAT.jsonl"
PROGRESS = ROOT / "PROGRESS.md"
CRUNCH_STATE = RESEARCH / "data" / "devqueue_crunch_state.json"
CLAUDE_EXE = Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "claude.exe"
MCP_EMPTY = RESEARCH / "mcp_empty.json"

SKIP_FRESH_MIN = 10      # 鎖的心跳 10 分鐘內有更新 → 有輪次在跑，略過
STALE_MIN = 20           # 鎖的心跳超過 20 分鐘沒動 → 視為中斷，清鎖重開（10～20 分鐘之間保守略過）
SILENT_KILL_MIN = 20     # claude 連續 20 分鐘沒有輸出 → 砍掉、算該項失敗一次
ITEM_MAX_MIN = 90        # 單一項目上限（含跑冒煙約 12 分鐘）
ROUND_MAX_HOURS = 10     # 一輪上限；工作排程器 ExecutionTimeLimit 趕工期間設 12 小時
MAX_ITEMS = 60           # 一輪最多派幾次（防呆，正常會先把佇列做完）
BUDGET_USD = 12          # 每一項 claude -p 的預算（沿用原本每輪 12 美元）
POLL_SEC = 30

EXIT_DONE, EXIT_ERROR, EXIT_AUTH, EXIT_QUOTA, EXIT_YIELD, EXIT_TIME = 0, 1, 10, 11, 12, 13
CRUNCH_LINE = re.compile(r"^- \[ \] \*\*常備\.開發-")
TASK_NAME = "AlphaDevQueue"
SCHEDULE = {"crunch": ("PT30M", "PT12H"), "normal": ("PT15M", "PT1H10M")}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"[crunch {datetime.now(TZ).strftime('%H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(LOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


# ---------- 趕工是否進行中 ----------
def crunch_active(lines: list[str] | None = None) -> bool:
    """趕工結束條件（裁示第 6 點）：常備.開發 的 - [ ] 數量＝0（Cowork 有補件就會再變成 > 0）。"""
    try:
        lines = lines if lines is not None else R._lines()
        return any(CRUNCH_LINE.match(ln) for ln in lines)
    except Exception as e:  # noqa: BLE001
        log(f"WARN crunch_active 判斷失敗（{type(e).__name__}），視為非趕工、走原本模式")
        return False


# ---------- 鎖＝心跳 ----------
def _read_lock() -> tuple[str, float, str] | None:
    try:
        p = LOCK.read_text(encoding="utf-8").strip().split("|")
        return p[0], float(p[1]), (p[2] if len(p) > 2 else "unknown")
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return "unknown", 0.0, "unknown"


def gate(now: float | None = None) -> tuple[int, str]:
    now = time.time() if now is None else now
    lk = _read_lock()
    if lk is None:
        return 0, "NO_LOCK：沒有輪次在跑"
    pid, ts, cyc = lk
    age = (now - ts) / 60 if ts else STALE_MIN + 1
    if age <= SKIP_FRESH_MIN:
        return 1, f"RUNNING：cycle {cyc} 心跳 {age:.1f} 分鐘前更新（≤{SKIP_FRESH_MIN}）→ 本次略過"
    if age <= STALE_MIN:
        return 1, f"RUNNING?：cycle {cyc} 心跳 {age:.1f} 分鐘前（介於 {SKIP_FRESH_MIN}～{STALE_MIN}，保守略過）"
    try:
        LOCK.unlink()
    except FileNotFoundError:
        pass
    _git_status_note()
    return 0, f"STALE：cycle {cyc}（pid {pid}）心跳已 {age:.1f} 分鐘沒動 → 視為中斷，清鎖重開，從第一個未完成項續做"


def _git_status_note() -> None:
    """中斷重開前記一次工作目錄狀態；有未 commit 改動交給既有 check_collision 規則處理（殘局 60 分鐘判定）。"""
    try:
        out = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout
        n = len([x for x in out.splitlines() if x.strip()])
        log(f"中斷重開：git status 有 {n} 個未 commit 路徑（依 check_collision 既有規則處理）")
    except Exception as e:  # noqa: BLE001
        log(f"WARN git status 失敗（{type(e).__name__}）")


def refresh_lock(cycle_id: str) -> None:
    """只刷新自己這輪的鎖；鎖被別人拿走或不見就不動（不搶）。"""
    try:
        lk = _read_lock()
        if lk is not None and lk[2] == cycle_id:
            LOCK.write_text(f"{lk[0]}|{time.time()}|{cycle_id}", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log(f"WARN 刷新鎖心跳失敗（{type(e).__name__}）")


# ---------- 真的執行 claude ----------
def claude_executor(prompt_path: Path, jsonl_path: Path, on_alive) -> int:
    cmd = (f'chcp 65001>nul & type "{prompt_path}" | "{CLAUDE_EXE}" -p --dangerously-skip-permissions '
           f'--max-budget-usd {BUDGET_USD} --strict-mcp-config --mcp-config "{MCP_EMPTY}" '
           f'--output-format stream-json --verbose > "{jsonl_path}" 2>&1')
    p = subprocess.Popen(f'cmd.exe /S /C "{cmd}"', cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    start = last_growth = time.time()
    last_size = -1
    while True:
        try:
            return p.wait(timeout=POLL_SEC)
        except subprocess.TimeoutExpired:
            pass
        try:
            size = jsonl_path.stat().st_size if jsonl_path.exists() else 0
        except OSError:
            size = last_size
        if size != last_size:
            last_size, last_growth = size, time.time()
        silent = (time.time() - last_growth) / 60
        total = (time.time() - start) / 60
        if silent > SILENT_KILL_MIN or total > ITEM_MAX_MIN:
            log(f"砍掉 claude（pid {p.pid}）：{'沒有輸出 %.0f 分鐘' % silent if silent > SILENT_KILL_MIN else '單項超過 %d 分鐘' % ITEM_MAX_MIN}")
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            return -9
        on_alive()


def classify(jsonl_path: Path) -> dict:
    try:
        import claude_auth_classifier as C
        out = C.classify_file(str(jsonl_path))
    except Exception as e:  # noqa: BLE001
        return {"status": "UNKNOWN", "error": type(e).__name__}
    # 單項 --max-budget-usd 用完不是帳號額度用盡：算這一項失敗，不停整輪
    if out.get("status") == "QUOTA_EXCEEDED" and "budget" in str(out.get("matched") or ""):
        out = {"status": "ITEM_BUDGET", "matched": out.get("matched")}
    return out


def _quota_reset_hint(jsonl_path: Path) -> str:
    try:
        txt = jsonl_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"reset[s]?\s*(?:at\s*)?([0-9][^\"\\\n]{0,30})", txt, re.I)
        if m:
            return f"訊息寫「resets {m.group(1).strip()}」"
    except Exception:  # noqa: BLE001
        pass
    return "訊息未附恢復時間；每 30 分鐘排程會自動重試，恢復後自動續跑"


# ---------- 結算一項 ----------
def _find_line(key: str) -> tuple[int, str] | None:
    for i, ln in enumerate(R._lines()):
        if ln.startswith("- [") and R.item_key(ln) == key:
            return i, ln
    return None


def _commit_for(key: str, since: float) -> str | None:
    try:
        out = subprocess.run(["git", "log", f"--since={int(since)}", "--format=%h", "-F", f"--grep={key}", "-1"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip()
        if out:
            return out
        out = subprocess.run(["git", "log", f"--since={int(since)}", "--format=%h", "-1"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip()
        return out or None
    except Exception:  # noqa: BLE001
        return None


def _heartbeat_has(key: str, since_iso: str) -> bool:
    try:
        for ln in HEARTBEAT.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                d = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if str(d.get("round", "")).startswith(key.split()[0]) and str(d.get("ts", "")) >= since_iso:
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def push(title: str, body: str) -> None:
    try:
        import web_push
        r = web_push.send(title, body, kind="devqueue")
        if not r.get("ok"):
            log(f"推播未送達：{'；'.join(r.get('errors', [])[:2]) or '未知'}")
    except Exception as e:  # noqa: BLE001
        log(f"WARN 推播失敗（{type(e).__name__}）")


def settle(key: str, started: float, notify=push) -> dict:
    """看這一項在佇列裡變成什麼：[x]/[~]＝完成、[!]＝已標阻塞、仍 [ ]＝失敗一次（連兩次→標 [!]）。"""
    hit = _find_line(key)
    st = R._load_state()
    if hit is None:
        return {"key": key, "result": "missing"}
    idx, ln = hit
    started_iso = datetime.fromtimestamp(started, TZ).isoformat(timespec="seconds")
    if ln.startswith("- [x]") or ln.startswith("- [~]"):
        st.pop(key, None)
        R._save_state(st)
        sha = _commit_for(key.split()[0], started) or "（找不到 commit）"
        short = key.split()[0]
        if not _heartbeat_has(short, started_iso):
            try:
                with open(HEARTBEAT, "a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps({"ts": now_iso(), "track": "devqueue", "round": short,
                                        "note": f"趕工迴圈自動記錄：完成，commit {sha}"}, ensure_ascii=False) + "\n")
            except Exception as e:  # noqa: BLE001
                log(f"WARN 寫心跳失敗（{type(e).__name__}）")
        notify("DevQueue 完成一項", f"{key[:40]}（{sha}）")
        return {"key": key, "result": "done", "commit": sha}
    if ln.startswith("- [!]"):
        st.pop(key, None)
        R._save_state(st)
        why = ln.split("⛔", 1)[1][:80] if "⛔" in ln else "（見佇列）"
        return {"key": key, "result": "blocked", "why": why}
    ent = st.setdefault(key, {"fails": 0})
    ent["fails"] += 1
    ent["last_at"] = now_iso()
    R._save_state(st)
    if ent["fails"] >= R.MAX_CONSECUTIVE_FAILS:
        lines = R._lines()
        stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
        lines[idx] = ln.replace("- [ ]", "- [!]", 1) + f"　**⛔ 自走中止（{stamp}）**：趕工迴圈：連續 {ent['fails']} 次沒有完成，換下一項；需要看一眼再決定怎麼走"
        R.QUEUE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        st.pop(key, None)
        R._save_state(st)
        return {"key": key, "result": "fail_blocked", "fails": ent["fails"]}
    return {"key": key, "result": "fail", "fails": ent["fails"]}


# ---------- 一輪 ----------
def run_round(cycle_id: str, executor=claude_executor, classifier=classify, notify=push,
              collision=None, max_items: int = MAX_ITEMS, round_max_hours: float = ROUND_MAX_HOURS) -> tuple[int, dict]:
    collision = collision or R.check_collision
    os.environ["ALPHA_DEVQUEUE_CRUNCH"] = "1"
    os.environ["ALPHA_CYCLE_ID"] = cycle_id
    CYCLES_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    summary = {"cycle_id": cycle_id, "started_at": now_iso(), "items": [], "stop": None}
    code = EXIT_DONE
    for n in range(max_items):
        if time.time() - t0 > round_max_hours * 3600:
            summary["stop"], code = "本輪時間上限", EXIT_TIME
            break
        refresh_lock(cycle_id)
        try:
            if collision() != 0:
                summary["stop"], code = "讓路：其他軌道持鎖或有人正在改檔（check_collision）", EXIT_YIELD
                break
        except Exception as e:  # noqa: BLE001
            log(f"WARN check_collision 失敗（{type(e).__name__}），照常繼續")
        pc = R.build_prompt()
        if pc == 2:
            summary["items"].append({"key": "（守門員擋下的項目，已標 [!]）", "result": "blocked", "why": "守門員：需總司令或不可逆"})
            continue
        if pc in (3, 6):
            summary["stop"] = "佇列沒有 DevQueue 能做的 - [ ]" if pc == 3 else "剩下的都是時間閘／BLOCKED"
            break
        if pc != 0:
            summary["stop"], code = f"提示詞產生失敗（exit {pc}）", EXIT_ERROR
            break
        key = R._load_state().get("_current")
        if not key:
            nxt = R.find_next()
            if nxt is None:
                summary["stop"] = "佇列沒有 DevQueue 能做的 - [ ]"
                break
            key = R.item_key(nxt[1])
        started = time.time()
        jsonl = CYCLES_DIR / f"{cycle_id}-{n:02d}.jsonl"
        log(f"派工 #{n + 1}：{key[:50]}")
        rc = executor(R.PROMPT_OUT, jsonl, lambda: refresh_lock(cycle_id))
        if rc != 0:
            cls = classifier(jsonl)
            if cls.get("status") == "AUTH_EXPIRED":
                summary["stop"], code = "Claude 登入過期（需總司令重新登入，恢復後每 30 分鐘排程自動續跑）", EXIT_AUTH
                summary["items"].append({"key": key, "result": "interrupted", "why": "登入過期，不算失敗"})
                break
            if cls.get("status") == "QUOTA_EXCEEDED":
                summary["stop"], code = "Claude 額度用盡：" + _quota_reset_hint(jsonl), EXIT_QUOTA
                summary["items"].append({"key": key, "result": "interrupted", "why": "額度用盡，不算失敗"})
                break
        res = settle(key, started, notify=notify)
        res["rc"] = rc
        summary["items"].append(res)
        log(f"結算：{key[:40]} → {res['result']}{('（' + res.get('commit', '') + '）') if res.get('commit') else ''}")
    else:
        summary["stop"] = f"本輪派工次數上限 {max_items}"
    summary["ended_at"] = now_iso()
    summary["remaining_crunch_items"] = sum(1 for ln in R._lines() if CRUNCH_LINE.match(ln))
    _write_state(summary)
    if summary["items"]:
        write_progress(summary)
    return code, summary


def _write_state(summary: dict) -> None:
    try:
        CRUNCH_STATE.parent.mkdir(parents=True, exist_ok=True)
        CRUNCH_STATE.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log(f"WARN 寫趕工狀態失敗（{type(e).__name__}）")


def write_progress(summary: dict) -> None:
    """裁示第 5 點：每輪收工寫 PROGRESS 一段（完成清單、BLOCKED 與原因、剩餘項數）。"""
    try:
        done = [i for i in summary["items"] if i["result"] == "done"]
        blk = [i for i in summary["items"] if i["result"] in ("blocked", "fail_blocked")]
        fail = [i for i in summary["items"] if i["result"] in ("fail", "interrupted", "missing")]
        body = [f"## {summary['ended_at'][:16].replace('T', ' ')}（DevQueue 趕工迴圈，cycle {summary['cycle_id']}）先.六十四", "",
                f"- **完成 {len(done)} 項**：" + ("；".join(f"{i['key'][:30]}（{i.get('commit', '?')}）" for i in done) or "無"),
                f"- **BLOCKED {len(blk)} 項**：" + ("；".join(f"{i['key'][:30]}——{i.get('why') or '連續失敗兩次'}" for i in blk) or "無"),
                f"- **未完成待重試 {len(fail)} 項**：" + ("；".join(f"{i['key'][:30]}（{i.get('why') or '失敗 %s 次' % i.get('fails', '?')}）" for i in fail) or "無"),
                f"- **收工原因**：{summary.get('stop') or '—'}",
                f"- **常備.開發剩餘 `- [ ]`**：{summary.get('remaining_crunch_items', '?')} 項", ""]
        s = PROGRESS.read_text(encoding="utf-8")
        nl = "\r\n" if "\r\n" in s[:3000] else "\n"
        i = s.find("\n## ")
        i = i + 1 if i >= 0 else len(s)
        s = s[:i] + nl.join(body) + nl + s[i:]
        PROGRESS.write_text(s, encoding="utf-8", newline="")
    except Exception as e:  # noqa: BLE001
        log(f"WARN 寫 PROGRESS 失敗（{type(e).__name__}）")


# ---------- 工作排程器頻率 ----------
def set_schedule(mode: str, runner=None) -> bool:
    interval, limit = SCHEDULE[mode]
    ps = (f"$t=Get-ScheduledTask -TaskName {TASK_NAME} -ErrorAction Stop; "
          f"foreach($x in $t.Triggers){{ if($x.Repetition -and $x.Repetition.Interval){{ $x.Repetition.Interval='{interval}' }} }}; "
          f"$t.Settings.ExecutionTimeLimit='{limit}'; Set-ScheduledTask -InputObject $t -ErrorAction Stop | Out-Null; 'OK'")
    try:
        if runner:
            out = runner(ps)
        else:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=60).stdout
        ok = "OK" in (out or "")
        log(f"排程切換為 {mode}（每 {interval}、上限 {limit}）：{'成功' if ok else '失敗：' + (out or '')[:120]}")
        return ok
    except Exception as e:  # noqa: BLE001
        log(f"WARN 排程切換失敗（{type(e).__name__}）")
        return False


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "active":
        on = crunch_active()
        print("CRUNCH_ACTIVE" if on else "CRUNCH_OFF")
        return 0 if on else 1
    if cmd == "gate":
        c, msg = gate()
        log("gate：" + msg)
        return c
    if cmd == "run":
        cyc = os.environ.get("ALPHA_CYCLE_ID") or datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
        code, s = run_round(cyc)
        log(f"本輪收工：{s.get('stop')}；處理 {len(s['items'])} 項；常備.開發剩 {s.get('remaining_crunch_items')} 項")
        if not crunch_active():
            log("趕工結束條件成立（常備.開發 - [ ]＝0）→ 排程恢復原本模式")
            set_schedule("normal")
        return code
    if cmd == "schedule" and len(sys.argv) > 2 and sys.argv[2] in SCHEDULE:
        return 0 if set_schedule(sys.argv[2]) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
