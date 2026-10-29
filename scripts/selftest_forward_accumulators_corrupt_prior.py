"""自測：五支前向累積程式「既有累積檔讀壞 → 不得用空資料覆蓋」（先.一三五-1bg）。

這五支的歷史只能往前累積（法人近 60 日落在 holdout、其餘來源不能查歷史），
修正前 `prior = _load(OUT, {})` 把「檔案存在但 JSON 壞掉」當成首跑，寫回只剩當天。
全在暫存目錄、零外部請求，真實 data/ 未動。每支測四件事：
1. 累積檔不存在 → exit 0、寫出（首跑照舊）。
2. 累積檔是壞 JSON → exit 1、檔案位元組不變。
3. 累積檔是 JSON 但不是物件（`[]`）→ exit 1、檔案位元組不變。
4. 累積檔正常 → 換一天再跑，新舊兩天都在。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import accumulate_foreign_holding as FH  # noqa: E402
import accumulate_institutional as INST  # noqa: E402
import accumulate_margin_by_stock as MG  # noqa: E402
import accumulate_securities_lending_sell as SLS  # noqa: E402
import accumulate_short_lending_available as SLA  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def _iso(d8: str) -> str:
    return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"


def inst_inputs(tmp: Path, d8: str) -> None:
    INST.DETAIL = tmp / "stock_detail.json"
    INST.UNIVERSE = tmp / "listed_universe.json"
    INST.DETAIL.write_text(json.dumps({"stocks": {"2330": {"institutional": {
        "date": d8, "foreign_lots": 1, "trust_lots": 2, "dealer_lots": 3}}}}), encoding="utf-8")
    INST.UNIVERSE.write_text(json.dumps({"active": ["2330"] + [str(3000 + i) for i in range(1100)]}), encoding="utf-8")


def fh_inputs(tmp: Path, d8: str) -> None:
    FH.SNAPSHOT = tmp / "foreign_holding.json"
    FH.SNAPSHOT.write_text(json.dumps({"stocks": {"2330": {
        "date": d8, "foreign_holding_ratio": 70.1, "foreign_can_invest_ratio": 29.9,
        "foreign_shares_held": 100}}}), encoding="utf-8")


def sla_inputs(tmp: Path, d8: str) -> None:
    SLA.SNAPSHOT = tmp / "short_lending_available.json"
    SLA.SNAPSHOT.write_text(json.dumps({"twse": {"2330": 1000}, "otc": {"6488": 50},
                                        "fetched_at": f"{_iso(d8)}T18:00:00+08:00"}), encoding="utf-8")


def mg_inputs(tmp: Path, d8: str) -> None:
    MG.SNAPSHOT = tmp / "stock_detail.json"
    MG.SNAPSHOT.write_text(json.dumps({"meta": {"generated_at": f"{_iso(d8)}T18:00:00+08:00"},
                                       "stocks": {"2330": {"margin": {
                                           "date": d8, "margin_balance_today": 10,
                                           "margin_balance_prev": 9, "short_balance_today": 1}}}}),
                           encoding="utf-8")


def sls_inputs(tmp: Path, d8: str) -> None:
    SLS.SNAPSHOT = tmp / "securities_lending_sell.json"
    SLS.SNAPSHOT.write_text(json.dumps({"twse_date": d8, "twse": {"2330": {
        "sbl_prev_balance": 1, "sbl_sell": 2, "sbl_return": 0, "sbl_adjust": 0,
        "sbl_balance": 3, "sbl_next_day_quota": 4}}}), encoding="utf-8")


CASES = [("法人 accumulate_institutional", INST, inst_inputs),
         ("外資持股 accumulate_foreign_holding", FH, fh_inputs),
         ("可融券 accumulate_short_lending_available", SLA, sla_inputs),
         ("融資券 accumulate_margin_by_stock", MG, mg_inputs),
         ("借券賣出 accumulate_securities_lending_sell", SLS, sls_inputs)]


def run(mod) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main()
    return rc, buf.getvalue()


for label, mod, make in CASES:
    print(f"\n[{label}]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        mod.OUT = tmp / "history.json"

        make(tmp, "20261028")
        rc, out = run(mod)
        check("1. 累積檔不存在 → exit 0 且寫出", rc == 0 and mod.OUT.exists(), (rc, out[-200:]))
        first = mod.OUT.read_bytes() if mod.OUT.exists() else b""
        check("1. 首跑內容含 20261028", b"20261028" in first)

        for name, raw in (("2. 壞 JSON", b'{"series": {"2330": '), ("3. JSON 但不是物件", b"[]")):
            mod.OUT.write_bytes(raw)
            rc, out = run(mod)
            check(f"{name} → exit 1", rc == 1, (rc, out[-200:]))
            check(f"{name} → 檔案位元組不變（沒被覆蓋）", mod.OUT.read_bytes() == raw)
            check(f"{name} → 有印中止原因", "中止" in out and "先.一三五-1bg" in out, out[-200:])

        mod.OUT.write_bytes(first)
        make(tmp, "20261029")
        rc, out = run(mod)
        txt = mod.OUT.read_text(encoding="utf-8")
        check("4. 正常累積檔換一天 → exit 0", rc == 0, (rc, out[-200:]))
        check("4. 新舊兩天都在", "20261028" in txt and "20261029" in txt, txt[:200])

print(f"\n結果：{ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
