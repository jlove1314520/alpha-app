# -*- coding: utf-8 -*-
"""先.一二一-3：Claude 用量上限時 DevQueue 自動放慢。

背景：10/19 04:14～10/20 04:00 撞到 claude 每週用量上限（429 usage_limit_reached），
之後 39 輪每輪都照樣啟動 claude -p、每輪都白跑。這支讓 run-dev-queue-cycle.ps1：
  - 收尾時 `record <stream-json>`：偵測到真正的用量上限錯誤事件（先.一二二-11：只認 rate_limit_event
    status=rejected 或 result is_error＋usage_limit_reached，工具輸出／檔案內容裡的字串不算）就讀該事件的
    resetsAt（epoch 秒；讀不到就現在＋6 小時），寫進 research/.claude_usage_state.json（隱藏檔名＝落在 dev_queue_runner.MACHINE_WRITTEN 的 research/.[^/]+ 樣式內，CLAUDE.md 十節）；
  - 開工時 `check`：重置時間之前回 exit 1，並印一行「等用量重置到 MM/DD HH:MM」，
    wrapper 只記這一行就結束，不啟動 claude；重置後回 exit 0 照常跑。
  - `week_hit`：最近 7 天撞過上限就印 1（供提示詞決定補件只排 ①資料錯 ②畫面問題 ③研究）。

守門員自身失敗只降級（CLAUDE.md 十二節）：任何例外一律 fail open——check 回 0
（照常啟動 claude）、record 只印警告、exit 0。
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "research" / ".claude_usage_state.json"
DEFAULT_WAIT_SEC = 6 * 3600
WEEK_SEC = 7 * 86400
# 上限：resetsAt 超過現在 8 天視為讀錯，改用預設 6 小時（避免一個怪值把 DevQueue 停一個月）
MAX_WAIT_SEC = 8 * 86400


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:  # noqa: BLE001
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:  # noqa: BLE001
            pass


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(d: dict) -> None:
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")


def _limit_events(text: str):
    """先.一二二-11：只看 stream-json 每行的頂層事件，回傳真正的用量上限錯誤事件。
    算數的只有兩種：①rate_limit_event 且 rate_limit_info.status == "rejected"
    （注意 overageStatus 平常就是 "rejected"，不算）；②result 事件 is_error 為真且
    api_error 為 usage_limit_reached（或 api_error_status 429）。
    工具輸出／讀到的檔案內容（user 事件的 tool_result）、assistant 文字、
    正常狀態（status=allowed）事件帶的 resetsAt 一律不算——10/20 19:12 就是被這些誤判成 10/27 才重置。"""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        typ = ev.get("type")
        if typ == "rate_limit_event":
            info = ev.get("rate_limit_info") or {}
            if isinstance(info, dict) and info.get("status") == "rejected":
                yield "rate_limit_event", info.get("resetsAt")
        elif typ == "result" and ev.get("is_error") is True and (
                ev.get("api_error") == "usage_limit_reached" or ev.get("api_error_status") == 429):
            yield "result", None


def parse_limit(text: str, now: float) -> tuple[float, str] | None:
    """有真正的用量上限錯誤事件就回（重置時間 epoch 秒, 來源），沒有回 None。
    重置時間只取 rejected 那個事件本身的 resetsAt；沒有（或怪值）就現在＋6 小時。"""
    hit = False
    stamps = []
    for _kind, reset in _limit_events(text):
        hit = True
        if isinstance(reset, (int, float)) and now < reset <= now + MAX_WAIT_SEC:
            stamps.append(float(reset))
    if not hit:
        return None
    if stamps:
        return max(stamps), "resetsAt"
    return now + DEFAULT_WAIT_SEC, "預設 6 小時"


def cmd_record(path: str, cycle_id: str) -> int:
    now = time.time()
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    got = parse_limit(text, now)
    if got is None:
        _say("usage_gate: 本輪沒有用量上限錯誤事件")
        return 0
    until, source = got
    st = _load()
    st.update({
        "limited_until": until,
        "limited_until_local": datetime.fromtimestamp(until).strftime("%Y-%m-%d %H:%M"),
        "last_hit_at": now,
        "last_hit_local": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),
        "last_hit_cycle": cycle_id,
        "source": source,
    })
    _save(st)
    _say(f"usage_gate: 撞到 Claude 用量上限，記錄重置時間 {_fmt(until)}（{st['source']}）")
    return 0


def cmd_check() -> int:
    st = _load()
    until = st.get("limited_until")
    if isinstance(until, (int, float)) and time.time() < until:
        _say(f"等用量重置到 {_fmt(until)}")
        return 1
    return 0


def cmd_week_hit() -> int:
    st = _load()
    hit = st.get("last_hit_at")
    _say("1" if isinstance(hit, (int, float)) and time.time() - hit < WEEK_SEC else "0")
    return 0


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        if cmd == "record":
            return cmd_record(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
        if cmd == "check":
            return cmd_check()
        if cmd == "week_hit":
            return cmd_week_hit()
        _say(__doc__ or "")
        return 0
    except Exception as e:  # noqa: BLE001 -- 守門員自己壞掉一律放行（十二節）
        _say(f"usage_gate 警告（只降級、照常放行）：{type(e).__name__}: {e}")
        if cmd == "week_hit":
            _say("0")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
