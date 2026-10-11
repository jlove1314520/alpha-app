# -*- coding: utf-8 -*-
"""先.七十五 自測：紙.三（paper_3_tracker）、紙.一b（paper_1b_tracker）改為 2026-10-08 月中立即建倉。

全程沙盒、不連網（BAA10Y 用假資料、價格用合成資料），檢查：
①紙.三 10-08 建倉、閘門依據＝2026-09-30 月底、標部分期；10 月 BAA10Y 未到齊也照建（月中建倉不用當月資料）
②紙.三 第一個月底 10-30 照原規則再平衡並判定下月閘門；11 月 BAA 跳高 → 11-30 判關、下一個交易日才切換
③紙.一b 10-08 建倉、45/45/10、標部分期；10-30 月底再平衡
④重跑不重複記帳
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
import paper_1b_tracker as P1B  # noqa: E402

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


def jl(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


tmp = Path(tempfile.mkdtemp())
saved3 = {k: getattr(P3, k) for k in ("PRICE_HISTORY_PATH", "LOG_PATH", "APP_SUMMARY_PATH", "HEARTBEAT_PATH")}
saved1 = {k: getattr(P1B, k) for k in ("PRICE_HISTORY_PATH", "LOG_PATH", "APP_SUMMARY_PATH", "HEARTBEAT_PATH") if hasattr(P1B, k)}
try:
    syms = sorted(set(P3.SYMBOLS) | {"0050", "00646", "00697B"})

    def write_prices(until: date):
        px = {s: [] for s in syms}
        for i, d in enumerate(wdays(date(2026, 8, 3), until)):
            for s in syms:
                c = 100 * (1.002 if s in ("00631L", "00647L") else 1.001) ** i
                px[s].append({"date": d.isoformat(), "close": c, "adj_close": c})
        (tmp / "prices.json").write_text(json.dumps({"prices": px}), encoding="utf-8")

    baa = {d.isoformat(): (3.0 if (d.year, d.month) == (2026, 11) else 2.0) for d in wdays(date(2025, 6, 2), date(2026, 12, 4))}
    sb = tmp / "sb"
    sb.mkdir()
    P3.PRICE_HISTORY_PATH, P3.LOG_PATH, P3.APP_SUMMARY_PATH, P3.HEARTBEAT_PATH = tmp / "prices.json", sb / "p3.jsonl", sb / "p3.json", sb / "hb.jsonl"

    def run3(today, until, baa_over=baa):
        write_prices(until)
        P3._TODAY_OVERRIDE = today
        P3._BAA_OVERRIDE = dict(baa_over)
        return P3.run()

    # ① 10-08 建倉；10 月 BAA 只到 10-07（未到齊）也照建
    run3("2026-10-09", date(2026, 10, 8), {k: v for k, v in baa.items() if k <= "2026-10-07"})
    L = jl(P3.LOG_PATH)
    inc = [e for e in L if e["event"] == "inception"]
    check("紙.三 10-08 建倉（10 月 BAA10Y 未到齊也照建）", len(inc) == 1 and inc[0]["date"] == "2026-10-08")
    check("紙.三 建倉閘門依據＝2026-09-30 月底（開）、標部分期", inc and inc[0]["gate_basis"]["month_end"] == "2026-09-30"
          and inc[0]["gate_open"] is True and inc[0].get("partial_first_period") is True)
    check("紙.三 月中建倉不當場判下月（留給第一個月底）", inc and "gate_decision_for_next" not in inc[0])
    # ② 跑到 12-04：10-30 第一個月底再平衡＋判下月；11-30 判關；12-01 切換
    run3("2026-12-04", date(2026, 12, 4))
    L = jl(P3.LOG_PATH)
    me10 = next((e for e in L if e["date"] == "2026-10-30"), None)
    check("紙.三 第一個月底 10-30 照原規則再平衡並判定下月閘門", me10 and me10["event"] == "month_end" and "gate_decision_for_next" in me10 and "rebalance_cost" in me10)
    me11 = next((e for e in L if e["date"] == "2026-11-30"), None)
    sw = next((e for e in L if e["event"] == "gate_switch"), None)
    check("紙.三 11-30 判關、下一個交易日 12-01 才切換", me11 and me11.get("pending_switch", {}).get("to_open") is False and sw and sw["date"] == "2026-12-01")
    n = len(L)
    run3("2026-12-04", date(2026, 12, 4))
    check("紙.三 重跑不重複記帳", len(jl(P3.LOG_PATH)) == n)

    # ③ 紙.一b
    P1B.PRICE_HISTORY_PATH, P1B.LOG_PATH, P1B.APP_SUMMARY_PATH = tmp / "prices.json", sb / "p1b.jsonl", sb / "p1b.json"
    if hasattr(P1B, "HEARTBEAT_PATH"):
        P1B.HEARTBEAT_PATH = sb / "hb.jsonl"
    today_attr = "_TODAY_OVERRIDE" if hasattr(P1B, "_TODAY_OVERRIDE") else None
    write_prices(date(2026, 10, 8))
    if today_attr:
        setattr(P1B, today_attr, "2026-10-09")
    P1B.run()
    L1 = jl(P1B.LOG_PATH)
    i1 = [e for e in L1 if e["event"] == "inception"]
    check("紙.一b 10-08 建倉 45/45/10、標部分期", len(i1) == 1 and i1[0]["date"] == "2026-10-08"
          and i1[0]["targets"] == {"0050": 0.45, "00646": 0.45, "00697B": 0.1} and i1[0].get("partial_first_period") is True)
    write_prices(date(2026, 11, 4))
    if today_attr:
        setattr(P1B, today_attr, "2026-11-04")
    P1B.run()
    L1 = jl(P1B.LOG_PATH)
    check("紙.一b 第一個月底 10-30 月底再平衡", any(e["event"] == "month_end" and e["date"] == "2026-10-30" for e in L1))
    n1 = len(L1)
    P1B.run()
    check("紙.一b 重跑不重複記帳", len(jl(P1B.LOG_PATH)) == n1)
finally:
    for k, v in saved3.items():
        setattr(P3, k, v)
    for k, v in saved1.items():
        setattr(P1B, k, v)
    P3._TODAY_OVERRIDE = None
    P3._BAA_OVERRIDE = None
    shutil.rmtree(tmp, ignore_errors=True)

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
