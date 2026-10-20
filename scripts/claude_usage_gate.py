# -*- coding: utf-8 -*-
"""先.一二一-3：Claude 用量上限時 DevQueue 自動放慢。

背景：10/19 04:14～10/20 04:00 撞到 claude 每週用量上限（429 usage_limit_reached），
之後 39 輪每輪都照樣啟動 claude -p、每輪都白跑。這支讓 run-dev-queue-cycle.ps1：
  - 收尾時 `record <stream-json>`：偵測到 usage_limit_reached 就讀回應裡的
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


def parse_limit(text: str, now: float) -> tuple[float, str] | None:
    """有 usage_limit_reached 就回（重置時間 epoch 秒, 來源），沒有回 None。"""
    if "usage_limit_reached" not in text:
        return None
    stamps = [int(x) for x in re.findall(r'"resetsAt"\s*:\s*(\d{9,11})', text)]
    future = [s for s in stamps if now < s <= now + MAX_WAIT_SEC]
    if future:
        return float(max(future)), "resetsAt"
    return now + DEFAULT_WAIT_SEC, "預設 6 小時"


def cmd_record(path: str, cycle_id: str) -> int:
    now = time.time()
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    got = parse_limit(text, now)
    if got is None:
        _say("usage_gate: 本輪沒有 usage_limit_reached")
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
