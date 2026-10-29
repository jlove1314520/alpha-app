"""自測：可借券賣出股數抓取＋累積日期鍵（先.一三五-1bs／1bt）。

1bs：`.github/scripts/fetch_short_lending_available.py` 的 `requests.get` 換假回應、`OUT_PATH` 換暫存檔，
零外部請求，不碰真的 data/。確認上市／上櫃兩個清單各自獨立（同一列的兩個代號不是同一家）、
"_"／"-"／逗號數字處理、HTML 或空陣列或解析不到任何一檔時 exit 1 且不覆蓋既有檔。
1bt：`accumulate_short_lending_available.date_key_for()` 用合成行事曆，確認鍵＝數字適用的交易時段日。
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
import accumulate_short_lending_available as A  # noqa: E402
import fetch_short_lending_available as F  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class FakeResp:
    def __init__(self, body=None, bad_json=False, status=200):
        self._body, self._bad, self.status_code = body, bad_json, status

    def json(self):
        if self._bad:
            raise ValueError("Expecting value")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


calls: list = []


def run_fetch(resp) -> tuple[int, str]:
    F.requests.get = lambda *a, **k: (calls.append(a), resp)[1]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = F.main()
    return rc, buf.getvalue()


print("[1bs fetch_short_lending_available]")
check("_to_int：逗號數字", F._to_int("1,234,567") == 1234567)
check("_to_int：_／-／空／非數字 → None",
      [F._to_int(x) for x in ("_", "-", "", None, "abc")] == [None] * 5)
check("_to_int：0 保留為 0（不是 None）", F._to_int("0") == 0)

with tempfile.TemporaryDirectory() as td:
    F.OUT_PATH = Path(td) / "sla.json"
    rows = [
        {"TWSECode": "2330", "TWSEAvailableVolume": "6,000", "GRETAICode": "6488", "GRETAIAvailableVolume": "50"},
        {"TWSECode": "2317", "TWSEAvailableVolume": "0", "GRETAICode": "_", "GRETAIAvailableVolume": "_"},
        {"TWSECode": "", "TWSEAvailableVolume": "", "GRETAICode": "5347", "GRETAIAvailableVolume": "1,200"},
        {"TWSECode": "1101", "TWSEAvailableVolume": "-", "GRETAICode": "8069", "GRETAIAvailableVolume": "x"},
    ]
    rc, out = run_fetch(FakeResp(rows))
    doc = json.loads(F.OUT_PATH.read_text(encoding="utf-8")) if F.OUT_PATH.exists() else {}
    check("正常 → exit 0、只送 1 次請求", rc == 0 and len(calls) == 1, (rc, out))
    check("上市清單：2330／2317（0 保留），壞值 1101 略過", doc.get("twse") == {"2330": 6000, "2317": 0}, doc.get("twse"))
    check("上櫃清單：6488／5347，'_' 與壞值略過", doc.get("otc") == {"6488": 50, "5347": 1200}, doc.get("otc"))
    check("同一列上市上櫃不當同一檔（2330 不在上櫃、6488 不在上市）",
          "2330" not in doc.get("otc", {}) and "6488" not in doc.get("twse", {}))
    check("fetched_at 帶時區（累積器靠它換算台北時間）", str(doc.get("fetched_at", "")).endswith("+00:00"))
    good = F.OUT_PATH.read_bytes()

    for name, resp in (("HTML（不是 JSON）", FakeResp(bad_json=True)),
                       ("空陣列", FakeResp([])),
                       ("回物件不是陣列", FakeResp({"error": "x"})),
                       ("欄位名改了、兩邊都解析不到", FakeResp([{"Code": "2330", "Vol": "1"}]))):
        rc, out = run_fetch(resp)
        check(f"{name} → exit 1", rc == 1, (rc, out))
        check(f"{name} → 既有檔位元組不變", F.OUT_PATH.read_bytes() == good)

print("\n[1bt accumulate_short_lending_available.date_key_for]")
# 合成行事曆：10/09（五）、10/26（一）休市，10/23（五）臨時休市
CAL = {"tw": {"2026": {"closed": ["2026-10-09", "2026-10-26"], "unscheduled_closed": ["2026-10-23"]}}}
cases = [
    ("平日 17:13 台北（UTC 09:13）→ 當天", "2026-10-29T09:13:00+00:00", "20261029"),
    ("平日 05:43 台北（UTC 前一天 21:43）→ 不記", "2026-10-28T21:43:00+00:00", None),
    ("平日 08:59 台北 → 不記", "2026-10-29T00:59:00+00:00", None),
    ("平日 09:00 台北 → 當天", "2026-10-29T01:00:00+00:00", "20261029"),
    ("00:30 台北（週四）→ 前一天 10/28", "2026-10-28T16:30:00+00:00", "20261028"),
    ("00:59 台北 → 前一天", "2026-10-28T16:59:00+00:00", "20261028"),
    ("01:00 台北 → 不記", "2026-10-28T17:00:00+00:00", None),
    ("週六 09:18 → 下週一", "2026-10-17T01:18:00+00:00", "20261019"),
    ("假日 10/09 09:29 → 10/12（跳過 10/10、11）", "2026-10-09T01:29:00+00:00", "20261012"),
    ("10/10 週六 00:11 → 前一天 10/09 休市 → 10/12（不是 10/08）", "2026-10-09T16:11:00+00:00", "20261012"),
    ("10/24 週六 00:08 → 10/23 臨時休市、10/26 休市 → 10/27", "2026-10-23T16:08:00+00:00", "20261027"),
    ("臨時休市日 10/23 20:57 → 10/27", "2026-10-23T12:57:00+00:00", "20261027"),
    ("帶 +08:00 的時間也照台北算", "2026-10-28T18:00:00+08:00", "20261028"),
    ("沒有時區當 UTC", "2026-10-29T09:13:00", "20261029"),
]
for name, fa, want in cases:
    got, why = A.date_key_for(fa, CAL)
    check(name, got == want, (got, why))
got, why = A.date_key_for("昨天", CAL)
check("格式不對 → None＋原因", got is None and "格式" in why)
check("行事曆沒有該年度 → 只排除週末", A.date_key_for("2027-01-04T09:13:00+00:00", CAL)[0] == "20270104")

print(f"\n結果：{ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
