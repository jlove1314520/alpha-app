# -*- coding: utf-8 -*-
"""研究室.一 自測：檢查 data/research.json／research_radar.json 的結構與誠實揭露。
用法：python scripts/selftest_research.py   （全部 PASS 才算完成；自身失敗只警告、exit 0 由呼叫端決定）
"""
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ALPHA_ROOT") or Path(__file__).resolve().parent.parent)
OUT = Path(os.environ.get("RESEARCH_OUT", ROOT / "data"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


r = json.loads((OUT / "research.json").read_text(encoding="utf-8"))
rd = json.loads((OUT / "research_radar.json").read_text(encoding="utf-8"))
m, S = r["meta"], r["stocks"]
check("1 schema 與免責聲明", m.get("schema") == "research-v2" and "非投資建議" in m.get("disclaimer", ""))
check("2 標明不是因子（凍結.二）", "凍結.二" in m.get("not_a_factor", ""))
check("3 全市場涵蓋 ≥95%", m["coverage"]["built"] >= 0.95 * m["coverage"]["universe"], str(m["coverage"]))
check("4 無例外錯誤", m["n_errors"] == 0, str(m["errors"][:3]))
try:
    json.dumps(r, allow_nan=False); json.dumps(rd, allow_nan=False); nan_ok = True
except ValueError:
    nan_ok = False
check("5 無 NaN／Inf", nan_ok)
silent = [c for c, s in S.items() if s["rev"].get("rev3_yoy") is None and not s["rev"].get("reason")]
check("6 營收算不出來都有 reason", not silent, ",".join(silent[:5]))
silent_q = [c for c, s in S.items() if s["q"].get("q_stale") and not s["q"].get("reason")]
check("7 季報過期都有 reason", not silent_q, ",".join(silent_q[:5]))
bad_tag = [c for c, s in S.items() for t in s["change_tags"] if t not in m["rules"]]
check("8 每個 change_tag 都有規則文字", not bad_tag, ",".join(bad_tag[:5]))
liq_fail = [x["code"] for lst in rd["lists"].values() for x in lst if not S[x["code"]]["liquid"]]
check("9 雷達名單都過流動性門檻", not liq_fail, ",".join(liq_fail[:5]))
deep_bad = []
for c, s in S.items():
    d = s.get("deep")
    if not d:
        continue
    sc = d["scenario"]
    for row in sc["rows"]:
        if row["eps"] is None:
            continue
        eps = sc["base_revenue"] * (1 + row["growth"]) * (row["gm"] - row["opex"]) * (1 - sc["tax"]) / sc["shares"]
        if not math.isclose(eps, row["eps"], abs_tol=0.011):
            deep_bad.append(f"{c}/{row['name']}")
    for g in d["guidance"]["records"]:
        if g["asof"] > g["recorded_at"]:
            deep_bad.append(f"{c} guidance PIT")
    if d["guidance"]["errors"]:
        deep_bad.append(f"{c} guidance 格式")
check("10 深度情境公式與說法 PIT", not deep_bad, ",".join(deep_bad[:5]))
size = (OUT / "research_radar.json").stat().st_size
check("11 雷達檔 < 120KB（首頁可載）", size < 120_000, f"{size}")
print(f"\n{len(fails)} FAIL" if fails else "\n全部 PASS")
print(f"涵蓋：{m['coverage']}")
sys.exit(1 if fails else 0)
