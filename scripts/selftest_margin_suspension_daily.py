"""自測：停資停券每日累積 `.github/scripts/fetch_margin_suspension_daily.py`（先.一三五-1bd）。

候選 N9 唯一資料來源，之前沒有自測。全在暫存目錄、零外部請求（fetch_one 換成假函式）。
1. roc_to_iso：7／6 碼民國日、壞值 → None。
2. snapshot_day：台北 14:00 前歸前一天（先.一四〇-8）。
3. normalize：缺欄警告、非物件略過、非陣列拋錯、非民國日期保留原值＋警告、字串去空白。
4. main：首跑兩邊都寫；重跑零請求；一邊失敗只補那邊；兩邊都失敗不寫檔 exit 0；既有檔壞掉 exit 1 不覆蓋。
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import fetch_margin_suspension_daily as M  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


TW_ROW = {"Code": " 2330 ", "Name": "台積電", "StartDate": "1151102", "EndDate": "1151105", "Reason": "除息"}
TP_ROW = {"SecuritiesCompanyCode": "6488", "CompanyName": "環球晶", "ShortSaleSuspensionStartDate": "1151102",
          "ShortSaleSuspensionEndDate": "1151105", "Reason": "股東會", "Date": "1151029"}

print("1. roc_to_iso")
check("7 碼", M.roc_to_iso("1151102") == "2026-11-02")
check("6 碼", M.roc_to_iso("991231") == "2010-12-31")
check("不存在日期 → None", M.roc_to_iso("1151332") is None)
check("非數字 → None", M.roc_to_iso("abc") is None)
check("空值 → None", M.roc_to_iso("") is None and M.roc_to_iso(None) is None)
check("西元 8 碼 → None（不猜）", M.roc_to_iso("20261102") is None)

print("2. snapshot_day")
check("13:59 歸前一天", M.snapshot_day(datetime(2026, 10, 29, 13, 59)) == "2026-10-28")
check("14:00 算當天", M.snapshot_day(datetime(2026, 10, 29, 14, 0)) == "2026-10-29")
check("00:02（過午夜延班）歸前一天", M.snapshot_day(datetime(2026, 10, 29, 0, 2)) == "2026-10-28")

print("3. normalize")
recs, warns = M.normalize([TW_ROW], "TWSE")
check("上市一列", len(recs) == 1 and not warns, warns)
check("代號去空白", recs[0]["code"] == "2330")
check("start_iso", recs[0]["start_iso"] == "2026-11-02" and recs[0]["end_iso"] == "2026-11-05")
check("raw 原樣保留", recs[0]["raw"] is TW_ROW)
recs, warns = M.normalize([TP_ROW], "TPEX")
check("上櫃 report_date_iso", recs[0]["report_date_iso"] == "2026-10-29" and not warns, warns)
recs, warns = M.normalize([{"Code": "1101"}, "x"], "TWSE")
check("缺欄位 → 警告、仍收", len(recs) == 1 and any("缺欄位" in w for w in warns), warns)
check("非物件 → 略過＋警告", any("不是物件" in w for w in warns))
recs, warns = M.normalize([dict(TW_ROW, StartDate="2026/11/02")], "TWSE")
check("非民國日期 → 保留原值、iso None、警告",
      recs[0]["start"] == "2026/11/02" and recs[0]["start_iso"] is None and any("不是民國日期" in w for w in warns))
try:
    M.normalize({"a": 1}, "TWSE")
    check("非陣列拋錯", False)
except RuntimeError:
    check("非陣列拋錯", True)

print("4. main（暫存目錄、假 fetch）")
calls: list[str] = []
behavior: dict[str, object] = {}


def fake_fetch(market: str):
    calls.append(market)
    b = behavior.get(market)
    if isinstance(b, Exception):
        raise b
    return b


orig = (M.OUT_DIR, M.fetch_one, M.snapshot_day)
with tempfile.TemporaryDirectory() as td:
    try:
        M.OUT_DIR = Path(td) / "margin_suspension_daily"
        M.fetch_one = fake_fetch
        M.snapshot_day = lambda now: "2026-10-29"
        out = M.OUT_DIR / "2026-10-29.json"

        behavior.update(TWSE=RuntimeError("假 HTTP 429"), TPEX=RuntimeError("假逾時"))
        rc = M.main([])
        check("兩邊都失敗 → exit 0、不寫檔", rc == 0 and not out.exists(), (rc, out.exists()))

        calls.clear()
        behavior.update(TWSE=[TW_ROW], TPEX=RuntimeError("假逾時"))
        rc = M.main([])
        doc = json.loads(out.read_text(encoding="utf-8"))
        check("一邊失敗 → 另一邊照存", rc == 0 and doc["markets"]["TWSE"]["ok"] and not doc["markets"]["TPEX"]["ok"])
        check("失敗原因記下", "假逾時" in doc["markets"]["TPEX"].get("error", ""))

        calls.clear()
        behavior.update(TPEX=[TP_ROW])
        rc = M.main([])
        doc = json.loads(out.read_text(encoding="utf-8"))
        check("重跑只補失敗那邊", calls == ["TPEX"], calls)
        check("補完兩邊 ok、上市筆數不變", doc["markets"]["TPEX"]["ok"] and doc["markets"]["TWSE"]["n"] == 1)

        calls.clear()
        before = out.read_bytes()
        rc = M.main([])
        check("兩邊都已存 → 零請求、檔案不變", rc == 0 and calls == [] and out.read_bytes() == before, calls)

        out.write_text('{"markets": {"TWSE": {"ok": tr', encoding="utf-8")
        before = out.read_bytes()
        calls.clear()
        rc = M.main([])
        check("既有檔壞掉 → exit 1、不送請求、不覆蓋", rc == 1 and calls == [] and out.read_bytes() == before, (rc, calls))

        out.unlink()
        calls.clear()
        behavior.update(TWSE=[TW_ROW], TPEX=[TP_ROW])
        rc = M.main(["--dry-run"])
        check("--dry-run 不寫檔", rc == 0 and not out.exists() and calls == ["TWSE", "TPEX"], calls)
    finally:
        M.OUT_DIR, M.fetch_one, M.snapshot_day = orig

print("KNOWN_BEHAVIOR（只記錄不改）：寫檔用 write_text 直寫、不是 tmp＋replace；寫到一半中斷會讓當天檔壞掉，"
      "之後當天每次都 exit 1 不覆蓋（隔天新檔不受影響）。")
print(f"\n{ok} 通過，{fail} 失敗")
sys.exit(1 if fail else 0)
