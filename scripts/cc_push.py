# -*- coding: utf-8 -*-
"""先.一二二-14（2026-10-21）：CC 做完一件事就推播到總司令手機（取代「工作進度卡」方案）。

三個推播類別（research/web_push.py，可在 App 設定頁「通知」個別關閉）：
- cc_done：PROGRESS_HEARTBEAT.jsonl 新增一行、且該條在 PENDING_QUEUE 已是 `- [x]` → 推「✅ 做完：<條目一句話>」，
  點開到 App 日誌頁（./#journal）。分批類（V1 補資料等）每批寫心跳但條目仍是 `- [ ]`，所以不會逐批推，整條打勾才推一次。
  DevQueue 自己補入的條目（標題含「自走補入」）不推。
- cc_stuck：超過 3 小時沒有任何進度心跳（且佇列還有未完成項）、被用量閘門擋住、DevQueue 連 3 輪錯誤結束、
  或 DevQueue 連 2 輪「有 cycle start、沒 cycle end」（收件匣 026：wrapper 每條出口都會寫 cycle end，沒寫＝中途死掉）
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
    """心跳檔最後一筆（舊介面，保留給其他呼叫端）。"""
    r = _hb_last(now)
    return r[0] if r else None


def _hb_last(now: datetime) -> tuple[datetime, str] | None:
    last = None
    for line in _read(HB).splitlines()[-200:]:
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(rec["ts"])
        except Exception:  # noqa: BLE001
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TW)
        if ts <= now and (last is None or ts > last[0]):
            last = (ts, f"心跳：{str(rec.get('item', ''))[:30]}")
    return last


# 2026-10-23 先.一三四-1（收件匣 022）：「停住」誤報——心跳只在有心跳指示的編號條目完成時才寫，補.資料／收件匣／DevQueue 分段進度
# 都不寫，11:46～17:20 有十幾個 commit 仍被報「超過 3 小時沒有任何進度」。最後進度改取三者最晚：心跳、最後一個非機器自動提交的
# commit、收件匣最後一個 .done。機器自動提交用訊息關鍵字排除（心跳／自動更新／cycle log／新聞與事件／探測／連通／盤中報價…）。
MACHINE_COMMIT = re.compile(r"心跳|自動更新|cycle log|新聞與事件|探測|連通|盤中報價|停擺告警|本機補班|本機備援|補抓|DevQueue-Cycle")
INBOX = ROOT.parent / "cowork_inbox"


def _git_last_manual(now: datetime) -> tuple[datetime, str] | None:
    try:
        import subprocess  # noqa: PLC0415
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-200", "--format=%ct\t%s"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60).stdout
        for ln in out.splitlines():
            ct, _, subj = ln.partition("\t")
            if subj and not MACHINE_COMMIT.search(subj):
                ts = datetime.fromtimestamp(int(ct), TW)
                if ts <= now:
                    return ts, f"commit：{subj[:30]}"
    except Exception as e:  # noqa: BLE001 — 十二節：只降級
        _warn(f"讀 git log 失敗：{e}")
    return None


def _inbox_last_done(now: datetime) -> tuple[datetime, str] | None:
    try:
        best = None
        for p in INBOX.glob("*.done"):
            ts = datetime.fromtimestamp(p.stat().st_mtime, TW)
            if ts <= now and (best is None or ts > best[0]):
                best = (ts, f"收件匣：{p.stem[:30]}")
        return best
    except Exception as e:  # noqa: BLE001
        _warn(f"讀收件匣 .done 失敗：{e}")
        return None


def _last_progress(now: datetime) -> tuple[datetime, str] | None:
    cands = [c for c in (_hb_last(now), _git_last_manual(now), _inbox_last_done(now)) if c]
    return max(cands, key=lambda c: c[0]) if cands else None


def _queue_executable() -> bool:
    """DevQueue 最後一輪的結束原因是 QUEUE_EMPTY／GATED＝沒有可執行項目（剩下的都在等審／等條件）。讀不到就照舊看 - [ ] 數。"""
    ends = re.findall(r"DevQueue cycle end: \S+ \S+ cycle_id=\S+ reason=(\S+)", _read(DQ_LOG))
    if ends:
        return ends[-1] not in ("QUEUE_EMPTY", "GATED")
    return bool(re.findall(r"^- \[ \] \*\*", _read(PQ), re.M))


def silent_cycles(log_text: str, need: int = 2) -> list[tuple[str, str]]:
    """收件匣 026：最近 need 輪（不含最新一輪＝正在跑、tick 就是它開頭呼叫的）都「有 cycle start、沒 cycle end」
    → [(cycle_id, 該輪 log 最後一行)]；否則 []。end 行可能落在下一輪 start 之後（長輪次重疊），所以 end 全檔比對。"""
    parts = re.split(r"^===== DevQueue cycle start: \S+ \S+ cycle_id=(\S+) =====\r?$", log_text, flags=re.M)
    cycles = list(zip(parts[1::2], parts[2::2]))[:-1][-need:]
    if len(cycles) < need:
        return []
    ended = set(re.findall(r"DevQueue cycle end: \S+ \S+ cycle_id=(\S+) ", log_text))
    if any(cid in ended for cid, _ in cycles):
        return []
    return [(cid, ([ln.strip() for ln in body.splitlines() if ln.strip()] or ["（沒有任何後續紀錄）"])[-1]) for cid, body in cycles]


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
    try:
        sil = silent_cycles(_read(DQ_LOG))
        if sil:
            out.append(("dq_silent", f"DevQueue 連 {len(sil)} 輪沒有結束紀錄（{'、'.join(c for c, _ in sil)}），"
                                     f"最後停在：{sil[-1][1][:120]}"))
    except Exception as e:  # noqa: BLE001
        _warn(f"silent_cycles 失敗（{type(e).__name__}），本輪略過")
    last = _last_progress(now)
    open_items = len(re.findall(r"^- \[ \] \*\*", _read(PQ), re.M))
    if last and (now - last[0]).total_seconds() > STUCK_SEC:
        when = f"{last[0].astimezone(TW):%m/%d %H:%M}"
        if _queue_executable():
            out.append(("no_progress", f"超過 3 小時沒有任何進度（最後一次 {when}，{last[1]}），佇列還有 {open_items} 件"))
        else:
            out.append(("queue_idle", f"佇列都在等審／等條件，沒有可做的（最後進度 {when}，{last[1]}）"))
    return out


def stuck(st: dict, now: datetime, send=_send) -> int:
    seen = st.setdefault("stuck", {})
    n = 0
    for key, text in stuck_reasons(now):
        if now.timestamp() - float(seen.get(key, 0)) < STUCK_REPEAT_SEC:
            continue
        title = f"⏸ {text}" if key == "queue_idle" else f"⚠️ CC 停住：{text}"
        r = send(title[:80], text, "cc_stuck")
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
