# -*- coding: utf-8 -*-
"""先.一三二-0b（2026-10-23，收件匣 023 B 採甲）：模擬 I 本機排程 AlphaPaper9 的啟動程式（週一～五 18:30）。

回看資料（research/data/ 底下模擬 I 回看資料夾）只在本機，雲端 market.yml 讀不到，所以模擬 I 走本機排程。
做法：跑 research/paper_9_breakout_tracker.py 的 step()（2026-11-02 前一律 NOT_STARTED、不寫帳本；休市日由 tracker 自己判斷），
有變動才用 scripts/local_git_commit.commit_paths() 只提交 data/paper_9.json 與 research/data/paper_9_log.jsonl（後者在
research/data/ 被 gitignore，第一次用 git add -f 加入追蹤）。零外部請求。十節：兩個檔都在 dev_queue_runner.MACHINE_WRITTEN 樣式內
（^data/、^research/data/[^/]+\\.jsonl$）。十二節：任何失敗只印警告、exit 0。
跑法：python scripts/run_paper_9.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

SUMMARY = "data/paper_9.json"
LEDGER = "research/data/paper_9_log.jsonl"


def main() -> int:
    try:
        import paper_9_breakout_tracker as T  # noqa: PLC0415
        res = T.step()
        print(json.dumps(res, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 模擬 I step 失敗：{type(e).__name__}: {e}")
        return 0
    try:
        if (ROOT / LEDGER).exists():
            subprocess.run(["git", "-C", str(ROOT), "add", "-f", "--", LEDGER], capture_output=True, timeout=60)
        import local_git_commit as G  # noqa: PLC0415
        msg = (f"模擬 I（#463）本機排程更新 {datetime.now():%Y-%m-%d %H:%M}\n\n"
               "scripts/run_paper_9.py（AlphaPaper9）只提交 data/paper_9.json 與 research/data/paper_9_log.jsonl（git add -f）；"
               "兩檔在 MACHINE_WRITTEN 樣式內（十節）。前向紙上追蹤，非投資建議。")
        print(G.commit_paths([SUMMARY, LEDGER], msg))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 模擬 I 提交失敗（下一輪再試）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
