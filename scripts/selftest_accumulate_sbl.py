"""自測：借券賣出累積程式 `.github/scripts/accumulate_securities_lending_sell.py`（先.一三五-1bc）。

模擬 R（paper_18）唯一資料來源，之前沒有自測。全在暫存目錄、零外部請求、不讀真實數值。
1. _roc_to_iso_compact：7 碼／6 碼民國日、壞值 → None。
2. 空快照 → exit 1、不覆寫既有累積。
3. 上市／上櫃資料日不同 → 各記各的鍵；全欄 None 的列不建鍵。
4. 同資料日重跑 → 只覆寫該日、新增計數 0、日期數不變；舊日期保留。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import accumulate_securities_lending_sell as A  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def tw(v: float) -> dict:
    return {f: v for f in A.TWSE_FIELDS}


def tp(v: float) -> dict:
    return {f: v for f in A.TPEX_FIELDS}


print("1. 民國日轉換")
check("1151028 → 20261028", A._roc_to_iso_compact("1151028") == "20261028")
check("991231（6 碼）→ 20101231", A._roc_to_iso_compact("991231") == "20101231")
check("空字串 → None", A._roc_to_iso_compact("") is None)
check("8 碼 → None", A._roc_to_iso_compact("20261028") is None)
check("非數字年 → None", A._roc_to_iso_compact("abc1028") is None)

with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    A.SNAPSHOT = d / "securities_lending_sell.json"
    A.OUT = d / "securities_lending_sell_history.json"

    print("2. 空快照不覆寫")
    A.OUT.write_text('{"series_twse":{"2330":{"20261027":[1]}}}', encoding="utf-8")
    before = A.OUT.read_text(encoding="utf-8")
    A.SNAPSHOT.write_text(json.dumps({"twse": {}, "tpex": {}}), encoding="utf-8")
    rc = A.main()
    check("exit 1", rc == 1, rc)
    check("既有累積原封不動", A.OUT.read_text(encoding="utf-8") == before)

    print("3. 上市／上櫃資料日不同、全 None 列")
    A.SNAPSHOT.write_text(json.dumps({
        "fetched_at": "2026-10-29T01:18:04+00:00", "twse_date": "20261028", "tpex_date": "1151027",
        "twse": {"2330": tw(5.0), "2317": {f: None for f in A.TWSE_FIELDS}},
        "tpex": {"6488": tp(7.0)}}), encoding="utf-8")
    rc = A.main()
    doc = json.loads(A.OUT.read_text(encoding="utf-8"))
    check("exit 0", rc == 0, rc)
    check("上市 2330 有 20261027（舊）與 20261028（新）", sorted(doc["series_twse"]["2330"]) == ["20261027", "20261028"], doc["series_twse"])
    check("上市值照欄位順序", doc["series_twse"]["2330"]["20261028"] == [5.0] * len(A.TWSE_FIELDS))
    check("全 None 的 2317 不建鍵", "2317" not in doc["series_twse"], doc["series_twse"].keys())
    check("上櫃鍵＝民國日轉的 20261027", list(doc["series_tpex"]["6488"]) == ["20261027"], doc["series_tpex"])
    check("meta 日期範圍", doc["meta"]["twse_date_range"] == ["20261027", "20261028"]
          and doc["meta"]["tpex_date_range"] == ["20261027", "20261027"], doc["meta"])

    print("4. 同資料日重跑只覆寫該日")
    A.SNAPSHOT.write_text(json.dumps({
        "twse_date": "20261028", "tpex_date": "1151027",
        "twse": {"2330": tw(6.0)}, "tpex": {"6488": tp(7.0)}}), encoding="utf-8")
    rc = A.main()
    doc2 = json.loads(A.OUT.read_text(encoding="utf-8"))
    check("exit 0", rc == 0, rc)
    check("日期數不變", doc2["meta"]["twse_dates_available"] == 2 and doc2["meta"]["tpex_dates_available"] == 1, doc2["meta"])
    check("20261028 被本班值覆寫", doc2["series_twse"]["2330"]["20261028"] == [6.0] * len(A.TWSE_FIELDS))
    check("舊日 20261027 保留", doc2["series_twse"]["2330"]["20261027"] == [1])
    series, added = A._accumulate(doc2["series_twse"], {"2330": tw(6.0)}, A.TWSE_FIELDS, "20261028")
    check("_accumulate 同日新增計數 0", added == 0, added)

    print("5. 上市日期壞（長度不對）→ 上市不寫、上櫃照寫")
    A.SNAPSHOT.write_text(json.dumps({
        "twse_date": "1151029", "tpex_date": "1151029",
        "twse": {"2330": tw(9.0)}, "tpex": {"6488": tp(8.0)}}), encoding="utf-8")
    rc = A.main()
    doc3 = json.loads(A.OUT.read_text(encoding="utf-8"))
    check("exit 0", rc == 0, rc)
    check("上市沒有多出壞鍵", sorted(doc3["series_twse"]["2330"]) == ["20261027", "20261028"], doc3["series_twse"]["2330"].keys())
    check("上櫃多 20261029", "20261029" in doc3["series_tpex"]["6488"])

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
