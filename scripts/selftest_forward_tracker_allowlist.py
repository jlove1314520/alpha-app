# -*- coding: utf-8 -*-
"""前向模擬追蹤程式輸出檔 ↔ 提交清單一致性自測（先.一三五-1fk，十節，零外部請求、不讀帳本內容）。

為什麼：雲端 runner 每班都是全新環境，追蹤程式寫了帳本但檔名不在 market.yml 的 `git add` 清單裡，
帳本就每班憑空消失、下一班從零開始——而且畫面上看不出來（摘要檔還在）。本機兩支（模擬 I／L）同理，
要在各自 launcher 的提交清單裡。

做法：
1. 讀 .github/workflows/market.yml，找出 `python research/paper_N_*.py` 的追蹤程式。
2. 每支用 ast 讀出所有 `paper_N…json(l)` 字串常數（只認自己編號，不 import、不執行）。
3. 每個檔名都要出現在 market.yml 的 `git add` 行（含 `for f in …; do git add` 迴圈）。
4. 本機：scripts/run_paper_9.py、scripts/run_warrant_snapshot.ps1 的提交清單同理。
排除（刻意不進提交清單，理由寫在 EXCLUDE）。

用法：python scripts/selftest_forward_tracker_allowlist.py（全過 exit 0；任一 FAIL exit 1）
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
MARKET_YML = ROOT / ".github" / "workflows" / "market.yml"
EXCLUDE = {
    # 只讀：滿 60 則時由 DevQueue 人工判定後寫入，追蹤程式自己不寫（paper_16 檔頭第 10 行）
    "paper_16_precision_audit.json": "唯讀（DevQueue 人工判定寫入）",
    # 本機快照推導的快取，可由 research/data/warrant_snapshots/ 重建，快照本身就不進 repo（paper_12 檔頭第 10 行）
    "paper_12_appearances.json": "本機可重建快取（快照不進 repo）",
}
LOCAL = {
    9: ROOT / "scripts" / "run_paper_9.py",
    12: ROOT / "scripts" / "run_warrant_snapshot.ps1",
}

results: list[tuple[bool, str]] = []


def check(ok: bool, name: str) -> None:
    results.append((bool(ok), name))
    print(("PASS " if ok else "FAIL ") + name)


def trackers_in_yml(text: str) -> list[str]:
    return sorted(set(re.findall(r"python\s+research/(paper_\d+_[A-Za-z0-9_]+\.py)", text)))


def add_text(text: str) -> str:
    """只取會把檔案加進 commit 的行（git add 行，及含 git add 的 for 迴圈行）。
    註解行（# 開頭，常寫「已加進下方 git add 清單」）不算，否則漏列也會被註解冒充過關。"""
    return "\n".join(l for l in text.splitlines() if "git add" in l and not l.lstrip().startswith("#"))


def output_names(src: str, num: int) -> set[str]:
    pat = re.compile(rf"^paper_{num}(?:_[A-Za-z0-9_]+)?\.jsonl?$")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and pat.match(node.value):
            names.add(node.value)
    return names


def missing(names: set[str], commit_text: str) -> list[str]:
    return sorted(n for n in names if n not in EXCLUDE and not re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", commit_text))


def audit(yml_text: str, read_src) -> dict:
    out = {}
    commit = add_text(yml_text)
    for t in trackers_in_yml(yml_text):
        num = int(re.match(r"paper_(\d+)_", t).group(1))
        out[t] = missing(output_names(read_src(t), num), commit)
    return out


def synthetic() -> None:
    yml = ("      - run: python research/paper_98_fake_tracker.py\n"
           "      - run: python research/paper_99_fake_tracker.py\n"
           "          git add -A data/paper_98.json data/paper_99.json\n"
           "          for f in paper_98_log.jsonl; do git add -f research/data/$f; done\n"
           "          # 已加進下方 git add 清單：paper_99_log.jsonl（註解冒充）\n")
    srcs = {
        "paper_98_fake_tracker.py": 'OUT="paper_98.json"\nLOG="paper_98_log.jsonl"\nX="paper_9.json"\n',
        "paper_99_fake_tracker.py": 'OUT="paper_99.json"\nLOG="paper_99_log.jsonl"\nA="paper_16_precision_audit.json"\n',
    }
    r = audit(yml, lambda t: srcs[t])
    check(r.get("paper_98_fake_tracker.py") == [], "合成：清單都有 → 無缺（別的編號 paper_9.json 不誤算）")
    check(r.get("paper_99_fake_tracker.py") == ["paper_99_log.jsonl"], "合成：只在註解出現、不在 git add 行 → 抓到缺")
    check(missing({"paper_16_precision_audit.json"}, "") == [], "合成：EXCLUDE 檔不算缺")
    check(missing({"paper_1.json"}, "git add data/paper_10.json") == ["paper_1.json"], "合成：paper_10.json 不能冒充 paper_1.json")
    check(trackers_in_yml("python research/paper_7030_tracker.py") == ["paper_7030_tracker.py"], "合成：舊紙上追蹤 paper_7030 也納入（同受十節約束）")


def real() -> None:
    yml = MARKET_YML.read_text(encoding="utf-8")
    trackers = trackers_in_yml(yml)
    check(len(trackers) >= 12, f"真檔：market.yml 找到 {len(trackers)} 支前向追蹤程式（預期 ≥12：前向 5,6,7,8,10,11,13～18＋舊紙上追蹤）")
    r = audit(yml, lambda t: (ROOT / "research" / t).read_text(encoding="utf-8"))
    for t, miss in r.items():
        check(not miss, f"真檔：{t} 輸出檔都在 git add 清單" + (f"（缺 {miss}）" if miss else ""))
    for num, launcher in LOCAL.items():
        tracker = next((ROOT / "research").glob(f"paper_{num}_*tracker.py"), None)
        if tracker is None or not launcher.exists():
            check(False, f"真檔：模擬 paper_{num} 本機 launcher／追蹤程式存在")
            continue
        text = launcher.read_text(encoding="utf-8")
        miss = missing(output_names(tracker.read_text(encoding="utf-8"), num), text)
        check(not miss, f"真檔：paper_{num} 輸出檔都在本機 launcher（{launcher.name}）提交清單" + (f"（缺 {miss}）" if miss else ""))


def main() -> int:
    synthetic()
    try:
        real()
    except Exception as e:  # noqa: BLE001
        check(False, f"真檔讀取失敗：{type(e).__name__}: {e}")
    n_ok = sum(ok for ok, _ in results)
    print(f"\n{n_ok}/{len(results)} PASS")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
