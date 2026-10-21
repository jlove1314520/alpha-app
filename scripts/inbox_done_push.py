# -*- coding: utf-8 -*-
"""先.一三〇-2（2026-10-22，收件匣 010）：Cowork 收件匣寫完 .done 後推播到總司令手機。

用法：python scripts/inbox_done_push.py <.done 檔路徑或編號 NNN>
- 讀 .done 第一行判斷狀態：完成→cc_done「✅ 收件匣 NNN 完成：…」；部分完成→cc_done「🟡 收件匣 NNN 部分完成：…」；
  卡住→cc_stuck「⚠️ 收件匣 NNN 卡住：…」。「…」＝.done 第二行前 40 字。
- 推播走 scripts/cc_push.py::_send（research/web_push.py），App 設定頁可個別關閉 cc_done／cc_stuck。
十二節：任何例外只印警告、exit 0，推播失敗不影響收件匣流程。
先.一二九-1（2026-10-22）：防重複——同一份 .done（檔名＋修改時間）只推一次，記在
research/.inbox_done_push_state.json；channel（cowork_inbox_channel/server.mjs）偵測到 .done 會自動呼叫本程式當保底，
視窗手動呼叫過就不會再推第二次。.done 改寫（例如部分完成→完成）修改時間變了，會再推一次。
"""
from __future__ import annotations

import json
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
STATE = ROOT / "research" / ".inbox_done_push_state.json"


def _key(done: Path) -> str:
    return f"{done.name}|{done.stat().st_mtime_ns}"


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 讀不到就當沒推過（十二節 fail open）
        return {}


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
        state = _load_state()
        key = _key(done)
        if key in state.get("pushed", {}):
            print(f"已推過，略過：{done.name}（{state['pushed'][key]}）")
            return 0
        title, body, kind = build(done)
        sys.path.insert(0, str(ROOT / "scripts"))
        import cc_push  # noqa: PLC0415
        res = cc_push._send(title, body, kind)
        print(f"{kind}｜{title}｜{res}")
        try:
            from datetime import datetime  # noqa: PLC0415
            pushed = state.get("pushed", {})
            pushed[key] = f"{datetime.now().isoformat(timespec='seconds')} {kind}"
            STATE.write_text(json.dumps({"pushed": dict(list(pushed.items())[-200:])}, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::inbox_done_push 狀態檔寫入失敗（不影響推播）：{e!r}")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::inbox_done_push 推播失敗（已降級）：{e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
