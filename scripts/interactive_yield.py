# -*- coding: utf-8 -*-
"""interactive_yield.py — 單發防撞：偵測「〔互動視窗執行中 YYYY-MM-DD HH:MM〕」標記
（先.十六-一，2026-10-05 總司令裁示）。

背景：2026-10-05 01:xx 互動視窗與自走軌道同時動 #409（產業缺貨單發），撞車。
規則：互動視窗開工前在該條目追加標記並 commit＋push；Marathon／DevQueue／
Hypothesis-queue 讀到標記一律跳過並在 cycle log 記「讓行」；完成或中止時移除。

守門員原則（CLAUDE.md 十二）：本模組任何失敗只降級成空清單／一行警告，
絕不讓呼叫端中斷（寧可漏抓，不可癱瘓）。標記超過 STALE_HOURS 小時仍在，
只加註「疑似遺留」警告，仍然讓行（誤跑單發的代價高於多等一輪）。

用法：
    python scripts/interactive_yield.py        # 印出目前所有讓行項目（供 cycle log／簡報用）
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

QUEUE = Path(__file__).resolve().parent.parent / "PENDING_QUEUE.md"
STALE_HOURS = 24.0
MARK_RE = re.compile(r"〔互動視窗執行中\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})〕")
_ENTRY_RE = re.compile(r"^- \[[ !]\]\s*\*\*([^*]+)\*\*")


def has_mark(text: str) -> bool:
    return bool(MARK_RE.search(text))


def active_marks(lines: list[str], now: datetime | None = None) -> list[dict]:
    """回傳 [{line_no, key, since, stale_hours, stale}]。只看「- [ ]」「- [!]」開頭、
    且帶標記的條目行；標記寫在條目後續縮排行的情況不認（規定標記追加在條目行上）。"""
    out: list[dict] = []
    now = now or datetime.now()
    try:
        for i, ln in enumerate(lines):
            if not ln.startswith("- ["):
                continue
            m = MARK_RE.search(ln)
            if not m:
                continue
            km = _ENTRY_RE.match(ln)
            key = (km.group(1).strip() if km else ln[:40])
            since = None
            age = None
            try:
                since = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
                age = (now - since).total_seconds() / 3600.0
            except ValueError:
                pass
            out.append({"line_no": i + 1, "key": key,
                        "since": f"{m.group(1)} {m.group(2)}",
                        "stale_hours": age,
                        "stale": age is not None and age > STALE_HOURS})
    except Exception as e:  # noqa: BLE001 -- 守門員自身失敗只降級
        print(f"WARN_YIELD_DETECTOR_FAILED: {type(e).__name__}: {e}")
        return []
    return out


def report(lines: list[str] | None = None, now: datetime | None = None) -> list[str]:
    """產生 cycle log 用的「讓行」文字行；沒有標記回空清單。"""
    try:
        if lines is None:
            lines = QUEUE.read_text(encoding="utf-8").splitlines()
    except Exception as e:  # noqa: BLE001
        return [f"WARN_YIELD_DETECTOR_FAILED: 讀不到 PENDING_QUEUE.md ({type(e).__name__})"]
    msgs = []
    for a in active_marks(lines, now):
        s = f"讓行：{a['key']}（PENDING_QUEUE.md 第{a['line_no']}行，互動視窗自 {a['since']} 執行中），本輪跳過不碰"
        if a["stale"]:
            s += f"　⚠️ 標記已逾 {STALE_HOURS:.0f} 小時（{a['stale_hours']:.0f}h），疑似遺留，請互動視窗確認是否移除"
        msgs.append(s)
    return msgs


if __name__ == "__main__":
    rows = report()
    if rows:
        for r in rows:
            print(r)
    else:
        print("無互動視窗執行中標記（無需讓行）")
