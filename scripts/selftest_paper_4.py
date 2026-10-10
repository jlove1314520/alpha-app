# -*- coding: utf-8 -*-
"""先.五十九-A1 自測：紙.四 前進式紙上追蹤（research/paper_4_tracker.py）。

全程沙盒、不連網（BAA10Y 用假資料），檢查：①10 月底兩本帳同日建倉、權重照事前登記
②月底照舊狀態再平衡、閘門判關後「下一個交易日」才切換 ③成本＝只對減碼計 0.1% 賣出稅（#430 口徑）
④重跑不重複記帳 ⑤BAA10Y 當月未到齊不記帳 ⑥帳本重複列 → 中止寫 last_error ⑦摘要含固定揭露文字。
"""
import json
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_3_tracker as P3  # noqa: E402
import paper_4_tracker as P4  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def wdays(a, b):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


tmp = Path(tempfile.mkdtemp())
try:
    # 價格：每檔每天 +0.1%（00631L +0.2%）
    px = {s: [] for s in P4.SYMBOLS}
    for i, d in enumerate(wdays(date(2026, 8, 3), date(2026, 12, 4))):
        for s in P4.SYMBOLS:
            c = 100 * (1.002 if s == "00631L" else 1.001) ** i
            px[s].append({"date": d.isoformat(), "close": c, "adj_close": c})
    (tmp / "prices.json").write_text(json.dumps({"prices": px}), encoding="utf-8")
    # BAA10Y：2025-06～2026-10 平穩 2.0，11 月跳到 3.0 → 11 月底判「關」
    baa = {d.isoformat(): (3.0 if (d.year, d.month) == (2026, 11) else 2.0) for d in wdays(date(2025, 6, 2), date(2026, 12, 4))}

    def go(today, baa_over=baa):
        P4._enter_sandbox(str(tmp / "sb"), str(tmp / "prices.json"), today, None)
        P3._BAA_OVERRIDE = dict(baa_over)
        return P4.run()

    def log():
        p = tmp / "sb" / "paper_4_log.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    # ⑤ BAA 10 月未到齊（只到 10-29）→ 不建倉
    r = go("2026-10-30", {k: v for k, v in baa.items() if k <= "2026-10-29"})
    check("BAA10Y 當月未到齊不建倉", not log())
    # ① 建倉
    r = go("2026-11-02")
    L = log()
    inc = [e for e in L if e["event"] == "inception"]
    check("10 月底兩本帳同日建倉（2026-10-30）", sorted(e["book"] for e in inc) == ["R1-A", "R1-C"] and all(e["date"] == "2026-10-30" for e in inc))
    check("R1-C 建倉權重 0050 50%／00631L 50%", next(e for e in inc if e["book"] == "R1-C")["targets"] == {"0050": 0.5, "00631L": 0.5})
    # ② 跑到 12 月：11-30 月底照舊（開）、12-01 切換到關
    go("2026-12-04")
    L = log()
    c = [e for e in L if e["book"] == "R1-C"]
    me = next(e for e in c if e["date"] == "2026-11-30")
    sw = next((e for e in c if e["event"] == "gate_switch"), None)
    check("11-30 月底照舊狀態（開）再平衡並判下月關", me["gate_open"] and me.get("pending_switch", {}).get("to_open") is False)
    check("下一個交易日 12-01 才切換為關（00631L→現金）", sw and sw["date"] == "2026-12-01" and sw["targets"] == {"0050": 0.5, "CASH": 0.5})
    # ③ 成本：切換時賣掉 00631L 部位 × 0.1%（0050 部位幾乎不動）
    prev = me
    vals = P4._revalue(prev, "2026-12-01", {s: {r["date"]: r["close"] for r in px[s]} for s in P4.SYMBOLS})
    nav_pre = sum(vals.values())
    expect = sum(max(0.0, vals.get(s, 0) - nav_pre * sw["targets"].get(s, 0)) for s in ("0050", "00631L")) * 0.001
    check(f"切換成本＝減碼×0.1%（{sw['rebalance_cost']:.2f} ≈ {expect:.2f}）", abs(sw["rebalance_cost"] - expect) < 0.01)
    # ④ 冪等
    n = len(L)
    go("2026-12-04")
    check("重跑不重複記帳", len(log()) == n)
    s = json.loads((tmp / "sb" / "paper_4.json").read_text(encoding="utf-8"))
    check("摘要含固定揭露文字", s.get("disclosure") == P4.DISCLOSURE and "13 個月關閉" in s["disclosure"])
    check("摘要兩本帳都有對照 0050／Bb-90", all("bench_0050_return_pct" in v and "bench_bb90_return_pct" in v for v in s["books"].values()))
    # ⑥ 重複列 → 中止
    with open(tmp / "sb" / "paper_4_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(L[0], ensure_ascii=False) + "\n")
    r = go("2026-12-04")
    s = json.loads((tmp / "sb" / "paper_4.json").read_text(encoding="utf-8"))
    check("帳本重複列 → 中止並寫 last_error", r.get("aborted") and s.get("last_error", {}).get("status") == "DUPLICATE_LOG_ENTRY")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    P3._BAA_OVERRIDE = None
    P3._TODAY_OVERRIDE = None

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
