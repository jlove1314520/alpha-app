# -*- coding: utf-8 -*-
"""holdout 洩漏自查（2026-09-07 Cybex.債務2）。

**為什麼要有這支**
Cybex 專案最貴的一課：它把「post-2024」當成安全的樣本外檢查，跑了上百輪才有人
發現那個日期邊界**逐字等於 holdout 邊界**——所謂的樣本外，一直是在偷看 holdout。
`validation/holdout.py` 的模組 docstring 就是在講這件事：holdout 污染不是紀律問題，
是**可得性問題**，只要程式碼讓人拿得到，人終究會去看。

`validation/holdout.py` 已經有兩道防線（`load_dev()` 在抓取層 cap、
`assert_no_holdout_leakage()` 在使用點擋）。這支是第三道，而且是**靜態**的：
不必真的跑回測，直接掃原始碼，找出所有「自稱樣本外但邊界踩到 VAL_END 之後」的
切片，以及所有繞過 cap 的直接抓取呼叫。靜態掃描抓得到那兩道動態防線抓不到的東西
——例如一段從來沒被執行過、但寫死了 2025 日期的分析程式碼。

**掃四件事**
1. `AFTER_VAL_END`：原始碼裡出現晚於 `VAL_END` 的硬編日期字面值。這是最直接的
   訊號：dev 期的程式碼不該有任何 2025 之後的日期。
2. `OOS_LABEL_NEAR_BOUNDARY`：名字帶「樣本外／oos／out_of_sample／post20xx」的
   東西，附近有日期字面值 —— 這就是 Cybex 踩到的形狀，要逐一人工確認。
3. `UNCAPPED_LOADER`：直接呼叫 `_fetch()` / `load_full_history()`（繞過 cap）的
   位置。允許清單寫在 `SANCTIONED_UNCAPPED` 裡，每一條都要有理由。
4. `HOLDOUT_STATE`：holdout 目前有沒有被解鎖過（`HOLDOUT_LOCK.json`）。

**這支自己絕不碰 holdout 資料**：它只讀 `.py` 原始碼文字，不載入任何行情、
不呼叫任何 loader、不 import 被掃描的模組（import 會執行模組層程式碼）。

跑法：
    python research/holdout_leak_audit.py            # 印報告
    python research/holdout_leak_audit.py --json     # 只印 JSON（給程式讀）
結束碼：0＝沒有需要人工確認的發現；1＝有發現（不是當掉，是要人去看）。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = RESEARCH_DIR.parent
REPORT_PATH = RESEARCH_DIR / "data" / "holdout_leak_audit.json"

sys.path.insert(0, str(RESEARCH_DIR))
from validation.holdout import TRAIN_END, VAL_END, HOLDOUT_LOCK  # noqa: E402

DATE_RE = re.compile(r"(?<![\d-])(20\d{2})-(\d{2})-(\d{2})(?![\d-])")
# 「自稱樣本外」的命名慣例。post20xx 是 Cybex 的原案：它的 post2024 逐字等於
# holdout 邊界，名字看起來像「之後」、實際上就是 holdout。
OOS_RE = re.compile(r"樣本外|out[_\-]?of[_\-]?sample|\boos\b|post_?20\d{2}", re.IGNORECASE)
UNCAPPED_RE = re.compile(r"(?<![\w.])(?:finmind_client\.)?(_fetch|load_full_history)\s*\(")

# 允許直接用未 cap loader 的位置。每一條都要有理由——這份清單就是「我們知道這裡
# 繞過了 cap，而且知道為什麼」的白紙黑字，不是為了讓掃描結果變好看。
SANCTIONED_UNCAPPED = {
    "finmind_client.py": "定義 _fetch/load_dev/load_full_history 本身",
    "validation/holdout.py": "docstring 提到函式名，不是呼叫",
    "universe.py": "TaiwanStockInfo／TaiwanStockDelisting 是非時序的名冊快照，沒有 date 欄可 cap（檔內已有說明）",
    "score.py": "TaiwanStockInfo 產業別對照表，同上",
    "us_universe.py": "USStockInfo 名冊快照，同上",
    "us_probe_milestone1.py": "USStockInfo 名冊快照，同上",
    "us_survivorship_probe.py": "USStockInfo 名冊快照，同上",
    "fut_stock_futures_liquidity_screen.py": "註解提到 _fetch 的節流，不是呼叫",
    "fut_probe_institutional_encoding.py": "註解說明刻意繞過快取，不是呼叫",
    "fut_probe_rollover_h1_h2.py": "註解提到快取鍵，不是呼叫",
    "backtest/engine.py": "註解聲明引擎不該知道 _fetch，不是呼叫",
    "determinism_self_test.py": "註解提到三個快取層的 _fetch，不是呼叫",
    "us_factor_ic.py": "註解提到 _fetch 的配額錯誤標記，不是呼叫",
    "adjust.py": "docstring 說明呼叫端該怎麼做，不是呼叫",
    "backfill_price_history_gaps.py": "docstring 說明為什麼不走這條，不是呼叫",
    "benchmark_taiex_stats.py": "docstring 提到函式名，不是呼叫",
    "holdout_leak_audit.py": "本檔（掃描用的正規表示式字面值）",
    "holdout_guard_test.py": "護欄本身的單元測試，呼叫前已把 fc._fetch 換成假函式，不連網不碰任何真實資料",
}


def _rel(p: Path) -> str:
    return p.relative_to(RESEARCH_DIR).as_posix()


def _iter_sources():
    for p in sorted(RESEARCH_DIR.rglob("*.py")):
        if "__pycache__" in p.parts or p.parts[len(RESEARCH_DIR.parts):][:1] == ("data",):
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


def _docstring_nodes(tree):
    """模組/類別/函式的 docstring 節點集合。

    **為什麼要排掉 docstring 與註解**：第一版用純文字掃描，591 筆命中裡幾乎全部是
    「2026-09-06 新增…」這種註解裡的日期戳記。591 筆假警報比沒有報告更糟——沒有人
    會去讀，真正的洩漏就藏在裡面。改用 AST 之後註解天生就不在樹裡，docstring 再手動
    排掉，剩下的才是**程式碼真的拿來當日期用的字串**。
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)                     and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _identifiers(tree):
    """所有識別字（變數名、函式名、參數名、關鍵字引數名、屬性名）。

    自稱樣本外的東西通常是**名字**（`oos_start`、`post2024_slice`），Cybex 的
    `post2024` 就是這個形狀，所以要掃名字而不是掃註解。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id, node.lineno
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.arg, node.value.lineno if hasattr(node.value, "lineno") else 0
        elif isinstance(node, ast.Attribute):
            yield node.attr, node.lineno


def audit() -> dict:
    findings = []
    scanned = 0
    unparsable = []
    for path, src in _iter_sources():
        scanned += 1
        rel = _rel(path)
        lines = src.splitlines()

        def _text(ln):
            return lines[ln - 1].strip()[:200] if 0 < ln <= len(lines) else ""

        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            # 解析不了就誠實記下來，不要靜默跳過——跳過等於在報告裡假裝掃過了
            unparsable.append({"file": rel, "error": str(e)})
            continue
        docs = _docstring_nodes(tree)

        # 1. 程式碼裡（非 docstring、非註解）晚於 VAL_END 的日期字串
        code_dates = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                # 「整個字串就是一個日期」跟「一段話裡剛好提到日期」風險完全不同：
                # 前者才可能被當成期間邊界（`start_date="2026-04-01"`），後者是印給人看的
                # 訊息文字（`f"2026-08-27一次性回補…"`）。不分開的話 49 筆裡有 40 幾筆
                # 是訊息文字，真的邊界又被埋掉——這是第一版 591 筆假警報的同一個病。
                is_pure_date = DATE_RE.fullmatch(node.value.strip()) is not None
                for m in DATE_RE.finditer(node.value):
                    code_dates.append((m.group(0), node.lineno))
                    if m.group(0) > VAL_END:
                        findings.append({
                            "kind": "AFTER_VAL_END" if is_pure_date else "AFTER_VAL_END_IN_PROSE",
                            "file": rel, "line": node.lineno,
                            "date": m.group(0), "text": _text(node.lineno),
                            "why": ("字串本身就是一個日期且晚於 VAL_END("
                                    + VAL_END + ")，可能被當成期間邊界，必須逐一確認")
                            if is_pure_date else
                            ("訊息文字裡提到晚於 VAL_END(" + VAL_END + ") 的日期，"
                             "風險低但一併列出，不隱藏"),
                        })

        # 2. 自稱樣本外的識別字，附近（±3 行）有沒有跨界日期
        for name, ln in _identifiers(tree):
            if not OOS_RE.search(name):
                continue
            near = sorted({d for d, dl in code_dates if abs(dl - ln) <= 3})
            findings.append({
                "kind": "OOS_LABEL_NEAR_BOUNDARY", "file": rel, "line": ln,
                "name": name, "nearby_code_dates": near,
                "crosses_boundary": any(d > VAL_END for d in near),
                "text": _text(ln),
                "why": "自稱樣本外的識別字，要人工確認它的期間邊界不是 holdout",
            })

        # 3. 繞過 cap 的直接抓取（呼叫節點，不是註解裡提到函式名）
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else None)
            if fname in ("_fetch", "load_full_history") and rel not in SANCTIONED_UNCAPPED:
                findings.append({
                    "kind": "UNCAPPED_LOADER", "file": rel, "line": node.lineno,
                    "callee": fname, "text": _text(node.lineno),
                    "why": "實際呼叫未 cap 的 loader，且不在允許清單內",
                })

    consumed = HOLDOUT_LOCK.exists()
    return {
        "train_end": TRAIN_END, "val_end": VAL_END,
        "holdout_consumed": consumed,
        "holdout_lock": json.loads(HOLDOUT_LOCK.read_text(encoding="utf-8")) if consumed else None,
        "files_scanned": scanned,
        "unparsable": unparsable,
        "counts": {k: sum(1 for f in findings if f["kind"] == k)
                   for k in ("AFTER_VAL_END", "AFTER_VAL_END_IN_PROSE", "OOS_LABEL_NEAR_BOUNDARY", "UNCAPPED_LOADER")},
        "findings": findings,
    }


def main() -> int:
    rep = audit()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 1 if rep["findings"] else 0

    print(f"holdout 洩漏自查　TRAIN_END={rep['train_end']}　VAL_END={rep['val_end']}")
    print(f"holdout 已解鎖？{'是（' + str(rep['holdout_lock']) + '）' if rep['holdout_consumed'] else '否（尚未動過）'}")
    print(f"掃描 {rep['files_scanned']} 個 .py，發現 {len(rep['findings'])} 筆需人工確認：{rep['counts']}")
    for kind in ("UNCAPPED_LOADER", "AFTER_VAL_END", "OOS_LABEL_NEAR_BOUNDARY", "AFTER_VAL_END_IN_PROSE"):
        items = [f for f in rep["findings"] if f["kind"] == kind]
        if not items:
            print(f"\n── {kind}：0 筆")
            continue
        print(f"\n── {kind}：{len(items)} 筆")
        for f in items:
            extra = ""
            if kind.startswith("AFTER_VAL_END"):
                extra = f"  日期={f['date']}"
            elif kind == "OOS_LABEL_NEAR_BOUNDARY":
                extra = f"  {f['name']}　鄰近程式碼日期={f['nearby_code_dates']} 跨界={f['crosses_boundary']}"
            print(f"  {f['file']}:{f['line']}{extra}\n      {f['text']}")
    print(f"\n報告已寫入 {REPORT_PATH}")
    return 1 if rep["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
