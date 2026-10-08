# -*- coding: utf-8 -*-
"""先.五十一-2 自我測試：Shioaji 連線事件回呼與缺口狀態。
- event_code=1 記缺口起點、13 記終點並逐檔補 1 分K，補完解除；
- 事件原始訊息（可能含身分證）不得出現在輸出；
- 回呼自身遇到壞輸入只警告不拋（CLAUDE.md 第十二節）；
- alpha_live_server._feed_gap_state()：今天且 in_gap 才回報；非今天／壞檔一律 None。
用法：python scripts/selftest_shioaji_feed_gap.py（純離線，不登入、不連網）。全部通過 exit 0。"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import shioaji_quotes as sq  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


def main() -> int:
    tmpdir = Path(tempfile.mkdtemp(prefix="feedgap_"))
    sq.FEED_GAP_PATH = tmpdir / "gap.json"
    sq.FEED_GAP_FILL_PACE_SEC = 0.0
    filled = []
    h = sq._make_event_handler(lambda: ["2330", "0050"], fill_fn=lambda codes, reason: filled.extend(codes))
    secret = "A123456789"

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        h(0, 1, f"Session down {secret}", f"DOWN {secret}")
    doc = json.loads(sq.FEED_GAP_PATH.read_text(encoding="utf-8"))
    check("event_code=1 → in_gap=True 並記起點", doc.get("in_gap") is True and bool(doc.get("gap_start")), str(doc))

    with contextlib.redirect_stdout(buf):
        h(0, 13, f"Reconnected {secret}", f"RECONNECTED {secret}")
        for _ in range(100):
            try:
                d = json.loads(sq.FEED_GAP_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            if d.get("in_gap") is False:
                break
            time.sleep(0.05)
    doc = json.loads(sq.FEED_GAP_PATH.read_text(encoding="utf-8"))
    check("event_code=13 → 逐檔補 1 分K", filled == ["2330", "0050"], str(filled))
    check("補完 → in_gap=False 且保留起訖時間",
          doc.get("in_gap") is False and doc.get("gap_start") and doc.get("gap_end") and doc.get("filled_at"), str(doc))

    out = buf.getvalue()
    check("輸出只含 event_code 與時間，不含原始訊息／身分證", secret not in out and "event_code=1" in out, out.strip()[:120])
    check("狀態檔不含原始訊息／身分證", secret not in sq.FEED_GAP_PATH.read_text(encoding="utf-8"))

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            h(None, "not-a-number")
        check("壞 event_code 不拋例外（fail open）", True)
    except Exception as e:  # noqa: BLE001
        check("壞 event_code 不拋例外（fail open）", False, type(e).__name__)

    # 13 沒有前置 1（例如 12 重連中直接 13）也要補，起點記 None
    filled.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        h(0, 13, "", "")
        for _ in range(100):
            if len(filled) >= 2:
                break
            time.sleep(0.05)
    check("無前置 1 的 13 也補資料", filled == ["2330", "0050"], str(filled))

    # live server 讀取端
    os.environ["ALPHA_FEED_GAP_PATH"] = str(tmpdir / "srv_gap.json")
    import alpha_live_server as srv  # noqa: E402
    p = Path(os.environ["ALPHA_FEED_GAP_PATH"])
    srv.FEED_GAP_PATH = p
    check("檔案不存在 → None", srv._feed_gap_state() is None)
    p.write_text(json.dumps({"in_gap": True, "gap_start": "2026-10-08T10:00:00+08:00", "gap_end": None}), encoding="utf-8")
    st = srv._feed_gap_state()
    check("今天 in_gap → 回報", isinstance(st, dict) and st.get("in_gap") is True, str(st))
    old = time.time() - 2 * 86400
    os.utime(p, (old, old))
    check("非今天的殘留狀態 → None（不讓中斷永久卡住）", srv._feed_gap_state() is None)
    p.write_text("{壞掉的json", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        bad = srv._feed_gap_state()
    check("壞檔 → None（fail open）", bad is None)
    p.write_text(json.dumps({"in_gap": False}), encoding="utf-8")
    check("in_gap=False → None", srv._feed_gap_state() is None)

    print("失敗：", "、".join(fails) if fails else "無")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
