"""自測：2027 年台股休市日尚未公布（trading_calendar.json tw.2027.published=false）時，
前向模擬看守員 research/forward_sim_watch.py 的行為（先.一三五-1af）。

合成情境（暫存目錄，零外部請求、不讀任何價格／報酬）：
  帳本 2027-01-04～2027-02-26 每個平日一列，但春節假設休市 2027-02-08～02-12（5 個平日）沒有列。
  ①2027 未公布：這 5 天（加元旦共 6 個平日）不得報 LEDGER_GAP，要記成「日曆未公布、待核」（unverified_gap_days）
  ②同時真的漏記 2026-12-30（2026 已公布）→ 仍要報 LEDGER_GAP
  ③2027 改成已公布且 closed 含春節 → 不報任何缺；已公布但 closed 不含 02-10 → 該日報 LEDGER_GAP
  ④STALE／晚起跑跨到未公布年份 → issues 要附「2027 年官方休市日未公布」說明
  ⑤日曆壞檔 → 不崩（只排除週末，fail open）
另：paper_13～18 共用的 research/paper_forward_common.py 不讀 trading_calendar（交易日由價格資料日決定），
所以本測試只測看守員；那支不需另寫提案。
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import forward_sim_watch as fsw  # noqa: E402

TZ = timezone(timedelta(hours=8))
SPRING = {f"2027-02-{d:02d}" for d in range(8, 13)}
ok = fail = 0


def check(name: str, cond: bool, detail="") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} {detail}")


def setup(root: Path, cal: dict | str, skip: set[str]) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "research" / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "trading_calendar.json").write_text(
        cal if isinstance(cal, str) else json.dumps(cal), encoding="utf-8")
    rows, d = [], date(2026, 12, 28)
    while d <= date(2027, 2, 26):
        if d.weekday() < 5 and d.isoformat() not in skip and d.isoformat() not in {"2027-01-01"}:
            rows.append(json.dumps({"date": d.isoformat()}))
        d += timedelta(days=1)
    (root / "research" / "data" / "paper_13_log.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (root / "data" / "paper_13.json").write_text(json.dumps(
        {"generated_at": "2027-02-26T18:00:00+08:00", "started": True, "start_not_before": "2027-01-04"}), encoding="utf-8")
    # paper_14：2027-02-05 之後沒再更新、也還沒起跑（測 STALE／晚起跑的說明文字）
    (root / "data" / "paper_14.json").write_text(json.dumps(
        {"generated_at": "2027-02-05T18:00:00+08:00", "started": False, "start_not_before": "2027-02-01"}), encoding="utf-8")


def row_of(doc: dict, name: str) -> dict:
    return next(r for r in doc["items"] if r["file"] == name)


CAL_2026 = {"published": True, "closed": ["2026-12-25"]}
NOW = datetime(2027, 2, 26, 20, 0, tzinfo=TZ)

with tempfile.TemporaryDirectory() as td:
    print("情境①②④：2027 未公布＋春節 5 天沒列＋真漏記 2026-12-30")
    r = Path(td) / "a"
    setup(r, {"tw": {"2026": CAL_2026, "2027": {"published": False, "closed": []}}}, SPRING | {"2026-12-30"})
    doc = fsw.evaluate(r, NOW)
    p13 = row_of(doc, "paper_13.json")
    led = p13["ledger"]
    check("春節 5 天＋元旦進 unverified、不進 gap", led["n_unverified_gap_days"] == 6 and not (set(led["gap_days"]) & SPRING), led)
    check("真漏記 2026-12-30 仍報 LEDGER_GAP", p13["status"] == "LEDGER_GAP" and led["gap_days"] == ["2026-12-30"], p13)
    check("issues 說明「日曆未公布、待核」", any("日曆未公布、待核" in s for s in p13["issues"]), p13["issues"])
    p14 = row_of(doc, "paper_14.json")
    check("STALE 附未公布說明", p14["status"] == "STALE"
          and any("2027 年官方休市日未公布" in s for s in p14["issues"] if "generated_at" in s), p14["issues"])
    check("晚起跑附未公布說明", any("2027 年官方休市日未公布" in s for s in p14["issues"] if "started=false" in s), p14["issues"])

    print("情境①b：只有春節沒列（無真漏記）→ paper_13 主狀態 OK")
    r = Path(td) / "b"
    setup(r, {"tw": {"2026": CAL_2026, "2027": {"published": False, "closed": []}}}, SPRING)
    p13 = row_of(fsw.evaluate(r, NOW), "paper_13.json")
    check("主狀態 OK、不誤報", p13["status"] == "OK", p13)

    print("情境③：2027 已公布")
    r = Path(td) / "c"
    setup(r, {"tw": {"2026": CAL_2026, "2027": {"published": True, "closed": sorted(SPRING | {"2027-01-01"})}}}, SPRING)
    p13 = row_of(fsw.evaluate(r, NOW), "paper_13.json")
    check("closed 含春節 → OK、無 unverified", p13["status"] == "OK" and p13["ledger"]["n_unverified_gap_days"] == 0, p13)
    r = Path(td) / "d"
    setup(r, {"tw": {"2026": CAL_2026, "2027": {"published": True, "closed": sorted((SPRING - {"2027-02-10"}) | {"2027-01-01"})}}}, SPRING)
    p13 = row_of(fsw.evaluate(r, NOW), "paper_13.json")
    check("closed 不含 02-10 → 報 LEDGER_GAP 02-10", p13["status"] == "LEDGER_GAP" and p13["ledger"]["gap_days"] == ["2027-02-10"], p13)

    print("情境⑤：日曆壞檔 → 不崩")
    r = Path(td) / "e"
    setup(r, "{壞掉", SPRING)
    try:
        doc = fsw.evaluate(r, NOW)
        check("evaluate 不崩、春節當成漏記（只排除週末，已知降級）",
              row_of(doc, "paper_13.json")["status"] == "LEDGER_GAP")
    except Exception as e:  # noqa: BLE001
        check("evaluate 不崩", False, repr(e))

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
