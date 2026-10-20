# -*- coding: utf-8 -*-
"""先.一二二-14（2026-10-21）：CC 做完一件事就推播到總司令手機（取代「工作進度卡」方案）。

三個推播類別（research/web_push.py，可在 App 設定頁「通知」個別關閉）：
- cc_done：PROGRESS_HEARTBEAT.jsonl 新增一行、且該條在 PENDING_QUEUE 已是 `- [x]` → 推「✅ 做完：<條目一句話>」，
  點開到 App 日誌頁（./#journal）。分批類（V1 補資料等）每批寫心跳但條目仍是 `- [ ]`，所以不會逐批推，整條打勾才推一次。
  DevQueue 自己補入的條目（標題含「自走補入」）不推。
- cc_stuck：超過 3 小時沒有任何進度心跳（且佇列還有未完成項）、被用量閘門擋住、或 DevQueue 連 3 輪錯誤結束
  → 推「⚠️ CC 停住：<原因>」；同一原因 6 小時內只推一次。
- cc_daily：每天 22:00 後第一次 tick 推「今天做完 N 件、還剩 M 件、等你決定 K 件」。

用法：python scripts/cc_push.py tick   （run-dev-queue-cycle.ps1 每輪開頭呼叫：scan＋stuck＋daily）
      python scripts/cc_push.py scan   （互動視窗標完 - [x] 後可立刻呼叫）
      python scripts/cc_push.py test   （送一則「✅ 測試：CC 推播已上線」）
狀態檔 research/.cc_push_state.json（dev_queue_runner.MACHINE_WRITTEN 的 research/.[^/]+ 樣式內，CLAUDE.md 十節）。
push_log 只記類別與成功數，不記內容（web_push 既有行為）。
十二節：本程式任何例外只印警告、exit 0，推播失敗只降級，不得影響 DevQueue 主流程。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
STATE = ROOT / "research" / ".cc_push_state.json"
HB = ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"
PQ = ROOT / "PENDING_QUEUE.md"
AWAIT = ROOT / "research" / "AWAITING_REVIEW.md"
USAGE = ROOT / "research" / ".claude_usage_state.json"
DQ_LOG = ROOT / "research" / "dev_queue_cycle.log"
STUCK_SEC = 3 * 3600
STUCK_REPEAT_SEC = 6 * 3600
DAILY_HM = (22, 0)
URL = "./#journal"


def _warn(msg: str) -> None:
    try:
        print(f"::warning::cc_push {msg}")
    except Exception:  # noqa: BLE001
        pass


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_state() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_state(st: dict) -> None:
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def _send(title: str, body: str, kind: str) -> dict:
    sys.path.insert(0, str(ROOT / "research"))
    import web_push  # noqa: PLC0415
    return web_push.notify(title, body[:220], kind=kind, url=URL)


def item_id(raw: str) -> str:
    return (raw or "").strip().split()[0] if (raw or "").strip() else ""


def done_titles(pq_text: str) -> dict:
    """{條目編號: 標題一句話}，只收 `- [x] **編號 標題**` 的行。同編號重複時取第一個（同 markitem）。"""
    out = {}
    for m in re.finditer(r"^- \[x\] \*\*(\S+) (.+?)\*\*", pq_text, re.M):
        out.setdefault(m.group(1), m.group(2).strip())
    return out


def scan(st: dict, send=_send) -> int:
    """推新完成的交辦。第一次執行只記位置不推（避免把歷史心跳一次全推出去）。回傳推了幾則。"""
    data = HB.read_bytes() if HB.exists() else b""
    off = st.get("hb_offset")
    if not isinstance(off, int) or off > len(data):
        st["hb_offset"] = len(data)
        return 0
    new = data[off:]
    cut = new.rfind(b"\n") + 1  # 只處理完整的行，半行留到下一輪
    st["hb_offset"] = off + cut
    titles = done_titles(_read(PQ))
    pushed = st.setdefault("pushed_items", [])
    n = 0
    for line in new[:cut].decode("utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        iid = item_id(str(rec.get("item", "")))
        title = titles.get(iid)
        if not title or iid in pushed or "自走補入" in title:
            continue
        short = re.sub(r"[（(\[【].*$", "", title).strip() or title
        r = send(f"✅ 做完：{iid} {short}"[:80], str(rec.get("summary") or rec.get("note") or short), "cc_done")
        pushed.append(iid)
        n += 1
        if not r.get("ok") and not r.get("muted"):
            _warn(f"cc_done 未送達 {iid}：{(r.get('errors') or ['?'])[0]}")
    st["pushed_items"] = pushed[-300:]
    return n


def _last_progress_ts(now: datetime) -> datetime | None:
    last = None
    for line in _read(HB).splitlines()[-200:]:
        try:
            ts = datetime.fromisoformat(json.loads(line)["ts"])
        except Exception:  # noqa: BLE001
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TW)
        if ts <= now and (last is None or ts > last):
            last = ts
    return last


def stuck_reasons(now: datetime) -> list[tuple[str, str]]:
    """[(原因鍵, 給人看的原因)]。"""
    out = []
    try:
        u = json.loads(USAGE.read_text(encoding="utf-8"))
        until = u.get("limited_until")
        if isinstance(until, (int, float)) and now.timestamp() < until:
            out.append(("usage_gate", f"Claude 用量上限，等到 {datetime.fromtimestamp(until, TW):%m/%d %H:%M} 重置才繼續"))
    except Exception:  # noqa: BLE001
        pass
    ends = re.findall(r"DevQueue cycle end: \S+ \S+ cycle_id=\S+ reason=(\S+) exit=(-?\d+)", _read(DQ_LOG))[-3:]
    if len(ends) == 3 and all(e[1] != "0" for e in ends):
        out.append(("dq_errors", f"DevQueue 連續 3 輪錯誤結束（最後一輪 {ends[-1][0]}）"))
    last = _last_progress_ts(now)
    open_items = len(re.findall(r"^- \[ \] \*\*", _read(PQ), re.M))
    if open_items and last and (now - last).total_seconds() > STUCK_SEC:
        out.append(("no_progress", f"超過 3 小時沒有任何進度（最後一次 {last.astimezone(TW):%m/%d %H:%M}），佇列還有 {open_items} 件"))
    return out


def stuck(st: dict, now: datetime, send=_send) -> int:
    seen = st.setdefault("stuck", {})
    n = 0
    for key, text in stuck_reasons(now):
        if now.timestamp() - float(seen.get(key, 0)) < STUCK_REPEAT_SEC:
            continue
        r = send(f"⚠️ CC 停住：{text}"[:80], text, "cc_stuck")
        seen[key] = now.timestamp()
        n += 1
        if not r.get("ok") and not r.get("muted"):
            _warn(f"cc_stuck 未送達 {key}：{(r.get('errors') or ['?'])[0]}")
    return n


def awaiting_count() -> int:
    t = _read(AWAIT)
    m = re.search(r"## 等待中.*?\n\|.*?\n\|[-| ]+\|\n(.*?)(?:\n\n|\n## |\Z)", t, re.S)
    if not m:
        return 0
    return sum(1 for l in m.group(1).splitlines() if l.startswith("|"))


def daily_counts(now: datetime) -> tuple[int, int, int]:
    today = now.date().isoformat()
    titles = done_titles(_read(PQ))
    done = set()
    for line in _read(HB).splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if str(rec.get("ts", ""))[:10] == today:
            iid = item_id(str(rec.get("item", "")))
            if iid in titles:
                done.add(iid)
    remain = len(re.findall(r"^- \[ \] \*\*", _read(PQ), re.M))
    return len(done), remain, awaiting_count()


def daily(st: dict, now: datetime, send=_send) -> int:
    today = now.date().isoformat()
    if (now.hour, now.minute) < DAILY_HM or st.get("daily_date") == today:
        return 0
    n, m, k = daily_counts(now)
    st["daily_date"] = today
    r = send(f"CC 今日摘要（{now:%m/%d}）", f"今天做完 {n} 件、還剩 {m} 件、等你決定 {k} 件", "cc_daily")
    if not r.get("ok") and not r.get("muted"):
        _warn(f"cc_daily 未送達：{(r.get('errors') or ['?'])[0]}")
    return 1


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "tick"
    try:
        if cmd == "test":
            r = _send("✅ 測試：CC 推播已上線", "收到這則代表 CC 做完／停住／每日摘要推播可以送到這支手機。", "cc_done")
            print(json.dumps({k: r.get(k) for k in ("ok", "failed", "subscriptions", "muted", "errors")}, ensure_ascii=False))
            return 0
        now = datetime.now(TW)
        st = load_state()
        res = {"done": scan(st)}
        if cmd == "tick":
            res["stuck"] = stuck(st, now)
            res["daily"] = daily(st, now)
        save_state(st)
        print("cc_push: " + json.dumps(res, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：只降級
        _warn(f"自身失敗（不影響主流程）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
