# -*- coding: utf-8 -*-
"""單發程式用的 Bonferroni 全體 N（先.一三三-2e，DevQueue 20261023-233101）。

為什麼有這支：`research/stock_grid_oneshot.py::current_N()` 用 `TRIALS_REGISTRY.jsonl` 的列數（289）當 N，
但帳本的全體 N 來自 `TRIALS_LEDGER.md`（含 JSONL 之前的舊列），扣掉框架驗證列、事前登記併入結果列後是 453
（`research/SELECTION_BIAS_LEDGER.md` 標頭「全體（總N）」）。兩者差了 164，門檻百分位就不同。
之後的單發程式一律 `from bonferroni_n import total_n, required_percentile`，不要自己數列。

口徑與 `selection_bias_ledger.main()` 完全相同（直接呼叫它的 parse()／merged_prereg_pairs()，不另寫一套）：
1. 去掉 FRAMEWORK_CHECK／FRAMEWORK_CHECK_FAILED 列（不計入 N）；
2. 事前登記列被後面的結果列以「事前登記 #編號」引用時兩列算 1 筆（先.一〇三-15）。

用法：python research/bonferroni_n.py          → 印出 N 與門檻
      python research/bonferroni_n.py selftest → 與 SELECTION_BIAS_LEDGER.md 標頭的 N 比對
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import selection_bias_ledger as sbl  # noqa: E402

required_percentile = sbl.required_percentile


def total_n() -> int:
    rows = [r for r in sbl.parse() if r["verdict"] not in ("FRAMEWORK_CHECK", "FRAMEWORK_CHECK_FAILED")]
    merged = sbl.merged_prereg_pairs(rows)
    return sum(1 for r in rows if r["id"] not in merged)


def ledger_header_n() -> int | None:
    """讀 SELECTION_BIAS_LEDGER.md「全體（總N…）」那一列的 N；讀不到回 None。"""
    p = HERE / "SELECTION_BIAS_LEDGER.md"
    if not p.exists():
        return None
    m = re.search(r"^\| \*\*全體（總N[^|]*\| (\d+) \|", p.read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else None


def selftest() -> int:
    n, h = total_n(), ledger_header_n()
    ok = h is not None and n == h
    print(f"total_n()={n}；SELECTION_BIAS_LEDGER.md 標頭={h} → {'PASS' if ok else 'FAIL（先重跑 selection_bias_ledger.py 再比）'}")
    print(f"Bonferroni 門檻（α=0.05 單邊）：{required_percentile(n):.4f} 百分位")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    n = total_n()
    print(f"N={n}　門檻 {required_percentile(n):.4f} 百分位")
