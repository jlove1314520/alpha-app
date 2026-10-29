"""自測：法人／外資持股／可融券三支前向累積程式的正常路徑（先.一三五-1bh）。

三支之前都沒有 selftest；`institutional_history.json` 是金流一與模擬 H／M 的資料來源。
全在暫存目錄、零外部請求，真實 data/ 未動。壞檔不覆蓋另見 selftest_forward_accumulators_corrupt_prior.py。
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


def run(mod) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main()
    return rc, buf.getvalue()


def wj(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def rj(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


ACTIVE = ["2330", "2317"] + [str(3000 + i) for i in range(1100)]

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)

    print("\n[法人 accumulate_institutional]")
    INST.DETAIL, INST.UNIVERSE, INST.OUT = tmp / "detail.json", tmp / "uni.json", tmp / "inst.json"

    def inst_row(d, f=1, t=2, dl=3):
        return {"date": d, "foreign_lots": f, "trust_lots": t, "dealer_lots": dl}

    wj(INST.UNIVERSE, {"active": ACTIVE[:500]})
    wj(INST.DETAIL, {"stocks": {"2330": {"institutional": inst_row("20261029")}}})
    rc, _ = run(INST)
    check("名冊 <1000 檔 → exit 1、不寫檔", rc == 1 and not INST.OUT.exists())

    wj(INST.UNIVERSE, {"active": ACTIVE})
    wj(INST.DETAIL, {"stocks": {}})
    rc, _ = run(INST)
    check("沒有 stocks → exit 1、不寫檔", rc == 1 and not INST.OUT.exists())

    wj(INST.DETAIL, {"stocks": {
        "2330": {"institutional": dict(inst_row("20261029"), history=[inst_row("20261028", 5, 6, 7)])},
        "0050": {"institutional": inst_row("20261029")},                       # 不在名冊（ETF）
        "2317": {"institutional": {"date": "20261029", "foreign_lots": None, "trust_lots": None, "dealer_lots": None}},
        "3000": {"institutional": inst_row("2026-10-29")},                     # 日期非 8 碼
    }})
    rc, out = run(INST)
    doc = rj(INST.OUT)
    s = doc["series"]
    check("正常 → exit 0", rc == 0, out[-200:])
    check("今天＋history 都併入", s.get("2330") == {"20261029": [1, 2, 3], "20261028": [5, 6, 7]}, s.get("2330"))
    check("不在名冊（0050）排除", "0050" not in s)
    check("三欄全 None 略過", "2317" not in s)
    check("日期非 8 碼略過", "3000" not in s)
    check("dates 與 meta 一致", doc["dates"] == ["20261028", "20261029"] and doc["meta"]["dates_available"] == 2)

    rc, out = run(INST)
    check("同日重跑 → 新增 0 筆", rc == 0 and "新增 0 筆" in out, out[-200:])

    # KEEP_DAYS 滾動：先放 75 天歷史，再跑一天 → 只留最近 70 天
    old = {f"2025{m:02d}{d:02d}": [1, 1, 1] for m in (1, 2, 3) for d in range(1, 26)}
    old_dates = sorted(old)[:75]
    wj(INST.OUT, {"series": {"2330": {d: [1, 1, 1] for d in old_dates}}})
    wj(INST.DETAIL, {"stocks": {"2330": {"institutional": inst_row("20261029")}}})
    rc, _ = run(INST)
    doc = rj(INST.OUT)
    check(f"KEEP_DAYS={INST.KEEP_DAYS} 滾動：只留最近 70 個日期", len(doc["dates"]) == INST.KEEP_DAYS, len(doc["dates"]))
    check("滾動後最新日在、最舊的被丟掉", doc["dates"][-1] == "20261029" and old_dates[0] not in doc["dates"])

    print("\n[外資持股 accumulate_foreign_holding]")
    FH.SNAPSHOT, FH.OUT = tmp / "fh.json", tmp / "fh_hist.json"
    wj(FH.SNAPSHOT, {"stocks": {}})
    rc, _ = run(FH)
    check("沒有 stocks → exit 1、不寫檔", rc == 1 and not FH.OUT.exists())

    wj(FH.SNAPSHOT, {"stocks": {
        "2330": {"date": "20261028", "foreign_holding_ratio": 70.1, "foreign_can_invest_ratio": 29.9, "foreign_shares_held": 100},
        "2317": {"date": "20261028", "foreign_holding_ratio": None, "foreign_can_invest_ratio": None, "foreign_shares_held": None},
        "2454": {"date": "", "foreign_holding_ratio": 1},
    }})
    rc, _ = run(FH)
    s = rj(FH.OUT)["series"]
    check("正常 → exit 0、欄位順序照 FIELDS", rc == 0 and s.get("2330") == {"20261028": [70.1, 29.9, 100]}, s.get("2330"))
    check("全 None 略過、無日期略過", "2317" not in s and "2454" not in s)
    rc, out = run(FH)
    check("同日重跑 → 新增 0 筆", rc == 0 and "新增 0 筆" in out, out[-200:])
    wj(FH.SNAPSHOT, {"stocks": {"2330": {"date": "20261029", "foreign_holding_ratio": 70.2,
                                         "foreign_can_invest_ratio": 29.8, "foreign_shares_held": 101}}})
    run(FH)
    doc = rj(FH.OUT)
    check("隔天累積兩天、不設上限", doc["dates"] == ["20261028", "20261029"] and len(doc["series"]["2330"]) == 2)

    print("\n[可融券 accumulate_short_lending_available]")
    SLA.SNAPSHOT, SLA.OUT = tmp / "sla.json", tmp / "sla_hist.json"
    wj(SLA.SNAPSHOT, {"twse": {}, "otc": {}, "fetched_at": "2026-10-29T18:00:00+08:00"})
    rc, _ = run(SLA)
    check("twse／otc 都空 → exit 1、不寫檔", rc == 1 and not SLA.OUT.exists())
    wj(SLA.SNAPSHOT, {"twse": {"2330": 1000}, "otc": {}})
    rc, _ = run(SLA)
    check("缺 fetched_at → exit 1、不寫檔", rc == 1 and not SLA.OUT.exists())

    wj(SLA.SNAPSHOT, {"twse": {"2330": 1000, "2317": None}, "otc": {"6488": 50},
                      "fetched_at": "2026-10-28T18:00:00+08:00"})
    rc, _ = run(SLA)
    doc = rj(SLA.OUT)
    check("正常 → exit 0、鍵為抓取日 YYYYMMDD", rc == 0 and doc["series_twse"].get("2330") == {"20261028": 1000})
    check("None 略過", "2317" not in doc["series_twse"])
    check("twse／otc 分開累積", doc["series_otc"] == {"6488": {"20261028": 50}} and "6488" not in doc["series_twse"])
    wj(SLA.SNAPSHOT, {"twse": {"2330": 900}, "otc": {}, "fetched_at": "2026-10-29T18:00:00+08:00"})
    run(SLA)
    doc = rj(SLA.OUT)
    check("隔天只有 twse → otc 舊資料保留", doc["series_otc"] == {"6488": {"20261028": 50}})
    check("twse 累積兩天", doc["series_twse"]["2330"] == {"20261028": 1000, "20261029": 900})

print(f"\n結果：{ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
