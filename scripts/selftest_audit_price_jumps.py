# -*- coding: utf-8 -*-
"""先.一三五-1ff 自測：price_history 跳動歸類（audit_price_jumps.main），守 1al 的臨時休市修正。

ROOT 換暫存目錄（假 price_history／trading_calendar／company_info，沒有 update_price_history → SPLITS 走降級警告）；
零外部請求、不覆蓋 docs/PRICE_JUMP_AUDIT.json。
用法：python scripts/selftest_audit_price_jumps.py
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import audit_price_jumps as A  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def series(pairs):
    # since 之前補兩列與第一個值同價（不算新上市、也不產生跨長空窗的跳動）
    if pairs[0][0] >= "2026-06-01":
        pairs = [("2026-05-28", pairs[0][1]), ("2026-05-29", pairs[0][1])] + pairs
    return [{"date": d, "close": c, "adj_close": c} for d, c in pairs]


PRICES = {
    "0050": series([("2026-10-22", 100.0), ("2026-10-26", 101.0), ("2026-10-27", 100.5)]),
    # 10/22（四）→10/26（一）：中間 10/23 臨時休市、10/24-25 週末 → 只隔 1 個交易日
    "3691": series([("2026-10-22", 50.0), ("2026-10-26", 56.0)]),
    # 10/20（二）→10/26（一）：中間缺 10/21、10/22 → 隔 3 個交易日
    "1111": series([("2026-10-20", 30.0), ("2026-10-26", 36.0)]),
    "7777": series([("2026-10-22", 20.0), ("2026-10-26", 26.0)]),   # 興櫃
    "00631L": series([("2026-10-22", 200.0), ("2026-10-26", 225.0)]),
    "2222": series([("2026-05-01", 10.0), ("2026-05-04", 13.0)]),     # since 之前的大跳不算
}
CAL = {"tw": {"2026": {"closed": ["2026-10-10"], "unscheduled_closed": ["2026-10-23"]}}}
COMP = {"companies": {"7777": {"name": "興櫃股", "industry_source": "tpex_t187ap03_R"},
                      "3691": {"name": "碩禾", "industry_source": "twse_t187ap03_L"}}}

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / "data").mkdir()
    (root / "docs").mkdir()
    (root / "data" / "price_history.json").write_text(json.dumps({"meta": {}, "prices": PRICES}), encoding="utf-8")
    (root / "data" / "trading_calendar.json").write_text(json.dumps(CAL), encoding="utf-8")
    (root / "data" / "company_info.json").write_text(json.dumps(COMP, ensure_ascii=False), encoding="utf-8")
    A.ROOT = root
    sys.argv = ["audit_price_jumps.py", "--since", "2026-05-28", "--out", "docs/out.json"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = A.main()
    out = json.loads((root / "docs" / "out.json").read_text(encoding="utf-8"))
    by = {it["code"]: it for it in out["items"]}
    check("exit 0、輸出寫到 --out（暫存）", rc == 0)
    check("跨臨時休市 10/23＋週末只算 1 個交易日（1al 回歸）", by.get("3691", {}).get("trading_days") == 1)
    check("跨臨時休市的一般單日大漲 → 不是 multi_day_gap", by.get("3691", {}).get("class") == "unexplained")
    check("真的缺 2 天 → trading_days=3、multi_day_gap", by.get("1111", {}).get("trading_days") == 3
          and by["1111"]["class"] == "multi_day_gap")
    check("興櫃（_R）→ no_limit_board", by.get("7777", {}).get("class") == "no_limit_board")
    check("00 開頭 ETF → etf_limit_rule", by.get("00631L", {}).get("class") == "etf_limit_rule")
    check("since 之前的跳動不列入", "2222" not in by)
    check("門檻內的 0050 小漲不列入、total 對得上", "0050" not in by and out["meta"]["total"] == len(out["items"]) == 4)
    check("讀不到 SPLITS 只降級警告", "警告：讀不到 SPLITS" in buf.getvalue())

print(f"\n{sum(results)}/{len(results)} PASS")
sys.exit(0 if all(results) else 1)
