# -*- coding: utf-8 -*-
"""前向模擬起跑日／判定日三方一致性檢查（先.一三五-1y，零請求、不讀帳本、不讀價格）。

三方：
1. 程式常數：research/paper_5～18 追蹤程式的 START／START_NOT_BEFORE／JUDGE／JUDGE_AFTER（用 ast 讀，不 import、不執行）。
   `START = B.START` 這種別名照 import 對象解析（paper_6 → paper_5）。
2. 候選表：research/FORWARD_CANDIDATES.md「進行中」表的「起跑」「判定」欄（「—」或空＝未填）。
3. PREREG 原文：追蹤程式 docstring 第一個提到的 `docs/PREREG_*.md`；只看含起跑類關鍵字（起跑／起算／建倉／開始／起記）
   或判定類關鍵字（判定／判一次）的行裡出現的日期（YYYY-MM-DD 或 YYYY-MM）。

判斷（每一方對程式常數）：
- OK：該方有日期且含程式常數（只寫到月的「2026-11」對 2026-11-02 算一致）。
- MISMATCH：該方有日期但沒有一個對得上程式常數。PREREG 端是「關鍵字行裡的日期集合」，同一行常夾別的日期
  （例：回測區間、修訂前舊值），所以 PREREG 的 MISMATCH 是「要人工看」的旗標，不是自動判錯。
- UNKNOWN：該方找不到日期（文件沒寫、或找不到 PREREG 檔）——不猜。
輸出 research/data/forward_start_consistency.json。

用法：python research/forward_start_consistency.py run｜selftest
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
OUT = ROOT / "research" / "data" / "forward_start_consistency.json"
CANDS = ROOT / "research" / "FORWARD_CANDIDATES.md"
NUMS = range(5, 19)
START_KEYS = ("START", "START_NOT_BEFORE")
JUDGE_KEYS = ("JUDGE", "JUDGE_AFTER")
START_WORDS = ("起跑", "起算", "建倉", "開始", "起記")
JUDGE_WORDS = ("判定", "判一次")
DATE_RE = re.compile(r"(20\d\d-[01]\d)(?:-([0-3]\d))?")


def tracker_path(n: int, research: Path) -> Path | None:
    hits = sorted(research.glob(f"paper_{n}_*tracker.py"))
    return hits[0] if hits else None


def read_consts(path: Path, research: Path, _depth: int = 0) -> dict:
    """回傳 {常數名: 值 或 None}；別名（X = MOD.Y）照 `import paper_N_xxx as MOD` 解析一層。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
    out = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name not in START_KEYS + JUDGE_KEYS:
            continue
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            out[name] = v.value
        elif isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and _depth < 2:
            mod = aliases.get(v.value.id)
            p = research / f"{mod}.py" if mod else None
            out[name] = read_consts(p, research, _depth + 1).get(v.attr) if p and p.exists() else None
        else:
            out[name] = None
    return out


def prereg_of(path: Path) -> str | None:
    m = re.search(r"docs/PREREG_[A-Za-z0-9_.\-]+?\.md", path.read_text(encoding="utf-8"))
    return m.group(0) if m else None


def dates_in(text: str) -> list[str]:
    return sorted({m.group(1) + (f"-{m.group(2)}" if m.group(2) else "") for m in DATE_RE.finditer(text)})


def prereg_dates(doc: Path) -> dict:
    if not doc.exists():
        return {"start": None, "judge": None}
    s, j = set(), set()
    for line in doc.read_text(encoding="utf-8").splitlines():
        if any(w in line for w in START_WORDS):
            s.update(dates_in(line))
        if any(w in line for w in JUDGE_WORDS):
            j.update(dates_in(line))
    return {"start": sorted(s), "judge": sorted(j)}


def candidate_rows(md: Path) -> dict:
    """回傳 {程式代號: {"start": 原文, "judge": 原文}}（只讀「進行中」那張表）。"""
    out, in_sec = {}, False
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_sec = line.startswith("## 進行中")
            continue
        if not in_sec or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and re.fullmatch(r"paper_\d+", cells[1]):
            out[cells[1]] = {"start": cells[4], "judge": cells[5]}
    return out


def match(prog: str | None, dates: list[str] | None) -> str:
    if not prog:
        return "NO_CONST"
    if not dates:
        return "UNKNOWN"
    return "OK" if any(prog == d or (len(d) == 7 and prog.startswith(d)) for d in dates) else "MISMATCH"


def check(root: Path = ROOT, cands: Path = CANDS) -> dict:
    research = root / "research"
    table = candidate_rows(cands) if cands.exists() else {}
    rows = []
    for n in NUMS:
        tp = tracker_path(n, research)
        if tp is None:
            continue
        key = f"paper_{n}"
        consts = read_consts(tp, research)
        start = next((consts[k] for k in START_KEYS if consts.get(k)), None)
        judge = next((consts[k] for k in JUDGE_KEYS if consts.get(k)), None)
        pr = prereg_of(tp)
        pd = prereg_dates(root / pr) if pr else {"start": None, "judge": None}
        t = table.get(key) or {}
        t_start, t_judge = dates_in(t.get("start") or ""), dates_in(t.get("judge") or "")
        row = {"paper": key, "tracker": tp.relative_to(root).as_posix(), "prereg": pr,
               "prereg_exists": bool(pr and (root / pr).exists()),
               "const_start": start, "const_judge": judge,
               "table_start_raw": t.get("start"), "table_judge_raw": t.get("judge"),
               "prereg_start_dates": pd["start"], "prereg_judge_dates": pd["judge"],
               "start_vs_table": match(start, t_start) if key in table else "NOT_IN_TABLE",
               "start_vs_prereg": match(start, pd["start"]),
               "judge_vs_table": match(judge, t_judge) if key in table else "NOT_IN_TABLE",
               "judge_vs_prereg": match(judge, pd["judge"])}
        rows.append(row)
    flags = [r["paper"] for r in rows if "MISMATCH" in (r["start_vs_table"], r["judge_vs_table"])]
    review = [r["paper"] for r in rows if "MISMATCH" in (r["start_vs_prereg"], r["judge_vs_prereg"])]
    return {"meta": {"generated_at": datetime.now(TW).isoformat(timespec="seconds"),
                     "rule": __doc__.split("判斷（")[1].split("輸出")[0].strip() if "判斷（" in (__doc__ or "") else "",
                     "requests": 0},
            "table_mismatch": flags, "prereg_needs_review": review, "rows": rows}


def run() -> int:
    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in doc["rows"]:
        print(f"{r['paper']:9s} 起跑 {r['const_start'] or '-':10s} 表:{r['start_vs_table']:12s} PREREG:{r['start_vs_prereg']:9s} | "
              f"判定 {r['const_judge'] or '-':10s} 表:{r['judge_vs_table']:12s} PREREG:{r['judge_vs_prereg']}")
    print(f"候選表不一致：{doc['table_mismatch'] or '無'}；PREREG 要人工看：{doc['prereg_needs_review'] or '無'}")
    return 0


def selftest() -> int:
    fails = []

    def ok(c, m):
        print(("PASS " if c else "FAIL ") + m)
        if not c:
            fails.append(m)

    td = Path(tempfile.mkdtemp(prefix="fwd_start_selftest_"))
    (td / "research").mkdir()
    (td / "docs").mkdir()
    (td / "research" / "paper_5_x_tracker.py").write_text(
        '"""照 docs/PREREG_A.md"""\nSTART = "2026-11-02"\n', encoding="utf-8")
    (td / "research" / "paper_6_y_tracker.py").write_text(
        '"""照 docs/PREREG_B.md"""\nimport paper_5_x_tracker as B\nSTART = B.START\n', encoding="utf-8")
    (td / "research" / "paper_7_z_tracker.py").write_text(
        '"""照 docs/PREREG_C.md"""\nSTART_NOT_BEFORE = "2026-12-01"\nJUDGE_AFTER = "2028-12-01"\n', encoding="utf-8")
    (td / "research" / "paper_8_w_tracker.py").write_text('"""無 PREREG"""\nSTART = "2027-01-04"\n', encoding="utf-8")
    (td / "docs" / "PREREG_A.md").write_text("回測 2002-01 開始\n", encoding="utf-8")  # 有日期但不對 → MISMATCH
    (td / "docs" / "PREREG_B.md").write_text("- 起算：2026-11-02\n", encoding="utf-8")
    (td / "docs" / "PREREG_C.md").write_text("建倉＝2026-12-01\n判定：2028-12-01 後判一次\n無關行 2030-01-01\n", encoding="utf-8")
    md = td / "cands.md"
    md.write_text("# x\n## 進行中：3\n| 模擬 | 程式代號 | 內容 | 試驗 | 起跑 | 判定 |\n|---|---|---|---|---|---|\n"
                  "| F | paper_5 | a | b | 2026-11 | — |\n| G | paper_6 | a | b | 2026-11-03 | — |\n"
                  "| H | paper_7 | a | b | 2026-12-01 | 2028-12-01 後 |\n## 候選清單\n| X | paper_8 | a | b | 2027-01-04 | — |\n",
                  encoding="utf-8")
    doc = check(td, md)
    r = {x["paper"]: x for x in doc["rows"]}
    ok(r["paper_6"]["const_start"] == "2026-11-02", "別名 START = B.START 解析到 paper_5 的值")
    ok(r["paper_5"]["start_vs_table"] == "OK", "候選表只寫到月（2026-11）對 2026-11-02 算一致")
    ok(r["paper_6"]["start_vs_table"] == "MISMATCH" and doc["table_mismatch"] == ["paper_6"], "候選表差一天 → MISMATCH 並列入 table_mismatch")
    ok(r["paper_5"]["start_vs_prereg"] == "MISMATCH" and "paper_5" in doc["prereg_needs_review"], "PREREG 關鍵字行日期對不上 → 要人工看")
    ok(r["paper_6"]["start_vs_prereg"] == "OK", "PREREG 起算行含程式起跑日 → OK")
    ok(r["paper_7"]["judge_vs_prereg"] == "OK" and r["paper_7"]["judge_vs_table"] == "OK", "判定日三方一致")
    ok("2030-01-01" not in (r["paper_7"]["prereg_start_dates"] or []), "不含關鍵字的行不收日期")
    ok(r["paper_5"]["judge_vs_table"] == "NO_CONST", "程式沒有判定常數 → NO_CONST（不算不一致）")
    ok(r["paper_8"]["start_vs_table"] == "NOT_IN_TABLE" and r["paper_8"]["start_vs_prereg"] == "UNKNOWN",
       "只讀進行中表（候選清單不算）；找不到 PREREG → UNKNOWN")
    print(f"結果：{'全部通過' if not fails else f'{len(fails)} 項失敗'}")
    return 1 if fails else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    raise SystemExit(selftest() if cmd == "selftest" else run())
