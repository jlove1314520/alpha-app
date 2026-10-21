# -*- coding: utf-8 -*-
"""先.一三〇-2（2026-10-22，收件匣 010）：Cowork 收件匣寫完 .done 後推播到總司令手機。

用法：python scripts/inbox_done_push.py <.done 檔路徑或編號 NNN>
- 讀 .done 第一行判斷狀態：完成→cc_done「✅ 收件匣 NNN 完成：…」；部分完成→cc_done「🟡 收件匣 NNN 部分完成：…」；
  卡住→cc_stuck「⚠️ 收件匣 NNN 卡住：…」。「…」＝.done 第二行前 40 字。
- 推播走 scripts/cc_push.py::_send（research/web_push.py），App 設定頁可個別關閉 cc_done／cc_stuck。
十二節：任何例外只印警告、exit 0，推播失敗不影響收件匣流程。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT.parent / "cowork_inbox"


def find_done(arg: str) -> Path | None:
    p = Path(arg)
    if p.suffix == ".done" and p.exists():
        return p
    if re.fullmatch(r"\d{1,3}", arg):
        hits = sorted(INBOX.glob(f"{int(arg):03d}_*.done"))
        return hits[0] if hits else None
    return None


def build(done: Path) -> tuple[str, str, str]:
    lines = [l.strip() for l in done.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    status = lines[0] if lines else "卡住"
    summary = (lines[1] if len(lines) > 1 else "（.done 沒有第二行）")[:40]
    nnn = done.name[:3]
    if status.startswith("卡住"):
        return f"⚠️ 收件匣 {nnn} 卡住：{summary}", "\n".join(lines[1:4]), "cc_stuck"
    if status.startswith("部分完成"):
        return f"🟡 收件匣 {nnn} 部分完成：{summary}", "\n".join(lines[1:4]), "cc_done"
    return f"✅ 收件匣 {nnn} 完成：{summary}", "\n".join(lines[1:4]), "cc_done"


def main(argv: list[str]) -> int:
    try:
        if len(argv) < 2:
            print("用法：python scripts/inbox_done_push.py <.done 路徑或編號>")
            return 0
        done = find_done(argv[1])
        if done is None:
            print(f"::warning::inbox_done_push 找不到 .done：{argv[1]}")
            return 0
        title, body, kind = build(done)
        sys.path.insert(0, str(ROOT / "scripts"))
        import cc_push  # noqa: PLC0415
        res = cc_push._send(title, body, kind)
        print(f"{kind}｜{title}｜{res}")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::inbox_done_push 推播失敗（已降級）：{e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
