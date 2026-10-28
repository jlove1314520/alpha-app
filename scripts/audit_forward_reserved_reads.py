# -*- coding: utf-8 -*-
"""先.一三五-1aa：14 支前向追蹤程式讀保留期間資料方式清查（零請求、只讀程式碼與帳本日期欄，不讀任何價格數值）。

逐支列出：
- 起跑日常數（START／START_NOT_BEFORE，paper_6 沿用 paper_5）；
- 起跑守門：本檔自己有「today/day < 起跑日 → NOT_STARTED」，或把起跑日交給 paper_forward_common.step()
  （step() 以 spec.start_not_before 為下限，之前一律 NOT_STARTED、不寫帳本）；
- 讀哪些檔（原始碼裡的資料檔名字面值）、是否用 price_history_store／paper_forward_common 讀價；
- 是否呼叫 research/validation/holdout 的 assert_no_holdout_leakage、是否在 ALLOWED_HOLDOUT_READERS；
- 帳本（research/data/paper_N_log.jsonl）每行的日期欄是否都 ≥ 起跑日（只讀日期，不讀報酬／淨值）。
判定：起跑守門存在且帳本無起跑前日期 → only_signal_input；否則 needs_proposal（守門模組是十三節核心檔，只能互動視窗改）。
輸出 research/data/forward_holdout_read_audit.json。跑法：python scripts/audit_forward_reserved_reads.py
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "research"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TRACKERS = {
    "5": "paper_5_vrp_tracker.py", "6": "paper_6_vrp_wing_tracker.py", "7": "paper_7_revsurprise_tracker.py",
    "8": "paper_8_ml_tracker.py", "9": "paper_9_breakout_tracker.py", "10": "paper_10_disposition_tracker.py",
    "11": "paper_11_tdcc_bigholder_tracker.py", "12": "paper_12_warrant_wave_tracker.py",
    "13": "paper_13_ml_low_beta_tracker.py", "14": "paper_14_grid_range_tracker.py",
    "15": "paper_15_ml_industry_tracker.py", "16": "paper_16_order_win_tracker.py",
    "17": "paper_17_margin_liquidation_tracker.py", "18": "paper_18_sbl_covering_tracker.py",
}
FILE_LIT = re.compile(r"""["']([\w./-]+\.(?:json|jsonl|parquet|csv|pkl|joblib))["']""")


def allowed_readers() -> set[str]:
    src = (R / "validation" / "holdout.py").read_text(encoding="utf-8")
    m = re.search(r"ALLOWED_HOLDOUT_READERS\s*=\s*frozenset\(\{(.*?)\}\)", src, re.S)
    return set(re.findall(r'"([\w.]+\.py)"', m.group(1))) if m else set()


def start_const(src: str) -> str | None:
    for name in ("START_NOT_BEFORE", "START"):
        m = re.search(rf'^{name}\s*=\s*"(\d{{4}}-\d{{2}}-\d{{2}})"', src, re.M)
        if m:
            return m.group(1)
    return None


def own_guard(src: str) -> bool:
    """本檔自己有「< 起跑日」比較，且同一函式回 NOT_STARTED。"""
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        seg = ast.get_source_segment(src, fn) or ""
        if "NOT_STARTED" in seg and re.search(r"<\s*(START_NOT_BEFORE|START)\b", seg):
            return True
    return False


def log_dates(n: str) -> dict:
    p = R / "data" / f"paper_{n}_log.jsonl"
    if not p.exists():
        return {"exists": False, "rows": 0, "min_date": None}
    dates, bad = [], 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            bad += 1
            continue
        v = d.get("date") or d.get("day")
        if v:
            dates.append(str(v)[:10])
    return {"exists": True, "rows": len(dates), "unparsable": bad, "min_date": min(dates) if dates else None}


def main() -> int:
    allowed = allowed_readers()
    common_src = (R / "paper_forward_common.py").read_text(encoding="utf-8")
    common_guard = "start_not_before" in common_src and "NOT_STARTED" in common_src
    p5_start = start_const((R / TRACKERS["5"]).read_text(encoding="utf-8"))
    out, bad = {}, []
    for n, fname in TRACKERS.items():
        src = (R / fname).read_text(encoding="utf-8")
        start = start_const(src) or (p5_start if "B.START" in src else None)
        uses_common = bool(re.search(r"import paper_forward_common", src))
        delegates = uses_common and "start_not_before=START" in src
        guard = own_guard(src) or (delegates and common_guard)
        lg = log_dates(n)
        pre_start_rows = bool(lg["min_date"] and start and lg["min_date"] < start)
        rec = {
            "file": f"research/{fname}", "start": start,
            "start_guard": "own" if own_guard(src) else ("paper_forward_common.step" if delegates and common_guard else None),
            "reads_files": sorted(set(FILE_LIT.findall(src))),
            "reads_price_history": bool(re.search(r"price_history", src)) or uses_common,
            "uses_paper_forward_common": uses_common,
            "uses_load_dev_dev_only": "load_dev(" in src,
            "calls_assert_no_holdout_leakage": "assert_no_holdout_leakage" in src,
            "in_allowed_holdout_readers": fname in allowed,
            "ledger": lg, "ledger_has_pre_start_rows": pre_start_rows,
        }
        rec["verdict"] = "only_signal_input" if (start and guard and not pre_start_rows) else "needs_proposal"
        if rec["verdict"] != "only_signal_input":
            bad.append(n)
        out[f"paper_{n}"] = rec
        print(f"paper_{n:<2} start={start} guard={rec['start_guard']} ledger={lg['rows']}列 min={lg['min_date']} "
              f"holdout守門={rec['calls_assert_no_holdout_leakage']} 白名單={rec['in_allowed_holdout_readers']} → {rec['verdict']}")
    doc = {"generated_by": "scripts/audit_forward_reserved_reads.py（先.一三五-1aa，零請求）",
           "allowed_holdout_readers": sorted(allowed), "paper_forward_common_guard": common_guard,
           "summary": {"total": len(out), "only_signal_input": len(out) - len(bad), "needs_proposal": bad},
           "trackers": out}
    (R / "data" / "forward_holdout_read_audit.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"結論：{len(out) - len(bad)}/{len(out)} 只當訊號輸入、起跑前不算報酬；需提案：{bad or '無'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
