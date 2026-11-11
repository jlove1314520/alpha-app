# -*- coding: utf-8 -*-
"""先.一五九-1 自測：research/paper_opt_stock.py（個股 S1～S4＋S1 1.5×／2×＋S1S3F14）。零外部請求，不動正式帳本。

① 回測基準線：bt_stock.json 的 S1～S4 2025 起段跟 REAUDIT §5a 表逐位對上（paper_opt_stock_seed.py 寫）；
   因子核對：紙上因子 vs 回測延長資料，S2／S3／S4 每個核對日前 N 名重疊 ≥90%；S1 在兩邊營收月份相同的日子（06-24、07-24）100%。
② 暫存目錄試跑（--start 2026-11-03）：每個帳戶每個交易日一列、起跑日報酬 0、S1／S1x15／S1x2 底層報酬相同、
   沒停損時 S1x2 報酬＝2×底層−融資、組合＝三成員權益平均、第二次跑不重寫。
③ 引擎只往回看：截到前一天重跑，重疊日權益逐位相同（每天從起跑日重跑、帳本只追加的前提）。
用法：python scripts/selftest_paper_opt_stock.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_opt_stock as P  # noqa: E402

ok_all = True


def check(name: str, cond: bool, info: str = "") -> None:
    global ok_all
    ok_all &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'} {name} {info}")


# ①
bt = json.loads((P.OUT / "bt_stock.json").read_text(encoding="utf-8"))
for k in ("S1", "S2", "S3", "S4"):
    c = bt["check"][k]
    check(f"①{k} 2025 起對上 §5a", c["ok"] is True, f"{c['from2025']['cagr']:+.1%}／{c['from2025']['mdd']:.1%}")
fc = bt.get("factor_check", {}).get("result", {})
for k in ("S2", "S3", "S4"):
    ov = [r["top_overlap"] for r in fc.get(k, [])]
    check(f"①{k} 因子前 N 名重疊 ≥90%", bool(ov) and min(ov) >= 0.9, str(ov))
s1 = {r["date"]: r["top_overlap"] for r in fc.get("S1", [])}
check("①S1 營收月份相同日 100%", s1.get("2026-06-24") == 1.0 and s1.get("2026-07-24") == 1.0, str(s1))

# ②
real_out = P.OUT
tmp = Path(tempfile.mkdtemp())
try:
    shutil.copy(real_out / "ledger_F14.jsonl", tmp / "ledger_F14.jsonl")
    P.OUT, P.STATE = tmp, tmp / "state_stock.json"
    sys.argv = ["x", "--start", "2026-11-03"]
    P.main()
    rows = {a: [json.loads(x) for x in (tmp / f"ledger_{a}.jsonl").read_text(encoding="utf-8").splitlines()]
            for a in list(P.ACCTS) + [P.COMBO[0]]}
    cal = [d for d in json.loads(P.BARS.read_text(encoding="utf-8"))["calendar"] if d >= "2026-11-03"]
    check("②每帳戶每交易日一列", all(len(rows[a]) == len(cal) for a in P.ACCTS), f"{[len(rows[a]) for a in P.ACCTS]}/{len(cal)}")
    check("②起跑日報酬 0、無持股", all(rows[a][0]["ret"] == 0 and rows[a][0]["n_holdings"] == 0 for a in P.ACCTS))
    check("②起跑隔天有成交", all(rows[a][1]["fills"] for a in ("S1", "S2", "S3")) if len(cal) > 1 else True)
    r1 = [r["ret_1x"] for r in rows["S1"]]
    check("②S1／S1x15／S1x2 底層相同", r1 == [r["ret_1x"] for r in rows["S1x15"]] == [r["ret_1x"] for r in rows["S1x2"]])
    eq2 = np.array([r["equity"] for r in rows["S1x2"]])
    nostop = (eq2 / np.maximum.accumulate(eq2)).min() > 0.9
    print(f"   S1x2 期間最大回撤 {(eq2 / np.maximum.accumulate(eq2)).min() - 1:.2%}（>−10% 才核對 2× 公式）")
    if nostop:
        exp = [2 * x - P.F12.MARGIN_RATE for x in r1[1:]]
        check("②S1x2＝2×底層−融資（未停損）", np.allclose([r["ret"] for r in rows["S1x2"][1:]], exp, atol=1e-7))
    f14 = [json.loads(x) for x in (tmp / "ledger_F14.jsonl").read_text(encoding="utf-8").splitlines()]
    src = {**{m: rows[m] for m in ("S1", "S3")}, "F14": f14}
    cd = [r["date"] for r in rows[P.COMBO[0]]]
    lv = {m: np.prod([1 + r["ret"] for r in src[m] if r["date"] in cd]) for m in P.COMBO[1]}
    check("②組合＝三成員權益平均（共同日起算）", bool(cd) and abs(rows[P.COMBO[0]][-1]["equity"] / P.F12.INIT - np.mean(list(lv.values()))) < 1e-6,
          f"{len(cd)} 列（F14 帳本 11-09 起）")
    P.main()
    check("②第二次跑不重寫", all(len((tmp / f"ledger_{a}.jsonl").read_text(encoding="utf-8").splitlines()) == len(rows[a])
                               for a in rows))
    # ③
    import paper_opt_f17 as F17
    ids = P.universe()
    bars, calendar = P.F14.build_bars(ids)
    F17.REV_CACHE = real_out / "stock_rev_pre2025.json"
    fr = P.frames(ids, bars, P.foreign_shares(ids), F17.rev_frames(ids))
    mk = P.market_frame(calendar)
    for eid in ("S2", "S4"):
        a, _ = P.run_engine(eid, fr, mk, "2026-11-03", calendar[-1])
        b, _ = P.run_engine(eid, fr, mk, "2026-11-03", calendar[-2])
        ea, eb = a.equity_curve["equity"].to_numpy(), b.equity_curve["equity"].to_numpy()
        check(f"③{eid} 截到前一天重跑重疊日相同", np.array_equal(ea[:len(eb)], eb))
finally:
    P.OUT = real_out
    shutil.rmtree(tmp, ignore_errors=True)

print("\n結果：" + ("全部通過" if ok_all else "有 FAIL"))
sys.exit(0 if ok_all else 1)
