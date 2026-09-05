# -*- coding: utf-8 -*-
"""馬拉松輪次「開工簡報」（2026-09-05，提案選項1修法E）：一支指令把這輪開工真正需要知道的事印出來，
**取代開工就 cat 整份 REPORT.md（446KB）／HYPOTHESIS_QUEUE.md（268KB）／TRIALS_LEDGER.md（233KB）／三軌 STATE 全文**
——那些加起來 1.2MB 是每輪預算被 `--max-budget-usd` 砍掉的主因。

印出的內容（總量目標 <60KB）：
1. 上一輪 cycle 的結束方式（`data/marathon_cycle_last.json`：OK / BUDGET / TIMEOUT / ERROR，花了多少錢、讀了多少）
   ——這樣下一輪就不用再猜「上一輪是卡住還是被砍」。
2. 鎖檔狀態、脫離session工作登記簿（`run_detached.py status`）。
3. `MARATHON_PROTOCOL.md` 第 0 節（暫停/維修旗標所在，全文印出，因為它會變）。
4. 三軌 STATE 檔各自**最新 3 則**（state 檔本身也已裁到只留 3 則，舊的在 *_STATE_ARCHIVE.md）。
5. `REPORT.md` 最新 2 個輪次條目（心跳）。
6. `CALIBRATION_PROBE.md` 的「結論」一節（甲.3 要求開工先讀）。

需要更多細節（某個 TRIALS_LEDGER 列、某個假說條目）時，用 grep 抓那一段，不要整份讀。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _section(title: str) -> None:
    print(f"\n{'=' * 8} {title} {'=' * 8}")


def _head_entries(path: Path, n: int) -> str:
    """STATE 檔：標題區 + 前 n 則（以 '**最後更新' / '**上一則保留' 開頭的段落計）。"""
    if not path.exists():
        return f"（{path.name} 不存在）"
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(?m)^(?=\*\*(?:最後更新|上一則保留))", text)
    return "".join(parts[: n + 1]).rstrip()


def _report_last_rounds(path: Path, n: int) -> str:
    if not path.exists():
        return "（REPORT.md 不存在）"
    text = path.read_text(encoding="utf-8", errors="replace")
    heads = [m.start() for m in re.finditer(r"(?m)^## 第\d+輪", text)]
    if not heads:
        return text[:3000]
    # REPORT 是新的在上面：取前 n 個條目
    end = heads[n] if len(heads) > n else len(text)
    return text[heads[0]:end].rstrip()[:20000]


def main() -> None:
    _section("1. 上一輪 cycle 結束方式（marathon_cycle_last.json）")
    last = RESEARCH / "data" / "marathon_cycle_last.json"
    if last.exists():
        d = json.loads(last.read_text(encoding="utf-8"))
        print(json.dumps(d, ensure_ascii=False, indent=1))
        if d.get("reason") in ("BUDGET", "TIMEOUT"):
            print(f"\n>>> 注意：上一輪是被 {d['reason']} 砍掉的（不是卡住）。若鎖檔顯示陳舊，原因就是這個，心跳請照實寫「上一輪被{d['reason']}砍掉」。")
    else:
        print("（尚無紀錄：新版 run-marathon-cycle.ps1 第一次跑之後才會有）")

    _section("2. 鎖檔與脫離session工作登記簿")
    lock = RESEARCH / ".marathon.lock"
    print("鎖檔:", lock.read_text(encoding="utf-8").strip() if lock.exists() else "（無）")
    r = subprocess.run([sys.executable, str(RESEARCH / "run_detached.py"), "status", "--last", "8"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.rstrip() or r.stderr.rstrip())

    _section("3. MARATHON_PROTOCOL.md 第0節（含暫停/維修旗標）")
    proto = (RESEARCH / "MARATHON_PROTOCOL.md").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?ms)\A(.*?)(?=^## 1\. )", proto)
    print((m.group(1) if m else proto[:12000]).rstrip())

    for track in ("TW", "US", "FUT"):
        _section(f"4. {track}_MARATHON_STATE.md 最新3則")
        print(_head_entries(RESEARCH / f"{track}_MARATHON_STATE.md", 3))

    _section("5. REPORT.md 最新2輪心跳")
    print(_report_last_rounds(RESEARCH / "REPORT.md", 2))

    _section("6. CALIBRATION_PROBE.md 結論")
    cp = RESEARCH / "CALIBRATION_PROBE.md"
    if cp.exists():
        t = cp.read_text(encoding="utf-8", errors="replace")
        i = t.find("## 結論")
        print(t[i:].rstrip() if i >= 0 else t[-4000:])

    _section("結束：需要細節請 grep，不要 cat 整份 REPORT/HYPOTHESIS_QUEUE/TRIALS_LEDGER")


if __name__ == "__main__":
    main()
