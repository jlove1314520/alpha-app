"""自測：外資持股每日抓取 `.github/scripts/fetch_foreign_holding.py`（先.一三五-1bq）。

`requests.get` 換假回應、節流函式換空函式、輸出路徑換暫存檔：零外部請求，不碰真的 data/。
模擬 O（paper_15）讀 `data/foreign_holding.json`，這裡確認：欄位用名稱對應、壞值 → None、
沒資料往前回退、429 只送 1 次並記封鎖、全部失敗不覆蓋既有檔。
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
import fetch_foreign_holding as F  # noqa: E402

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
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = json.dumps(body, ensure_ascii=False)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# 欄位順序刻意打亂（官方實際順序不同），確認用欄位名對應、不是位置寫死
FIELDS = ["全體外資及陸資持股比率", "證券名稱", "證券代號", "外資及陸資尚可投資比率", "國際證券編碼",
          "全體外資及陸資持有股數", "發行股數"]
ROWS = [
    ["73.12", "台積電", "2330", "26.88", "TW0002330008", "18,962,000,000", "25,932,000,000"],
    ["--", "台泥", "1101 ", "", "TW0001101004", "1,000", "7,000,000,000"],
    ["1.0", "空代號", "", "99", "x", "1", "1"],
]

calls: list = []
blocks: list = []
F._rate_limit_wait_or_raise = lambda src: None
F._rate_limit_record_block = lambda src, code, detail="": blocks.append((src, code))


def install(by_date: dict) -> None:
    """by_date：YYYYMMDD → FakeResp；沒列到的日期回 stat 非 OK。"""
    def fake_get(url, params=None, **kw):
        calls.append(params["date"])
        check_params.append(params)
        return by_date.get(params["date"], FakeResp({"stat": "很抱歉，沒有符合條件的資料!"}))
    F.requests.get = fake_get


check_params: list = []

print("一、fetch_mi_qfiis 解析")
install({"20261029": FakeResp({"stat": "OK", "fields": FIELDS, "data": ROWS})})
got = F.fetch_mi_qfiis("20261029")
check("selectType 用 ALLBUT0999（ALL 會回 0 筆的地雷）", check_params[-1]["selectType"] == "ALLBUT0999")
check("空代號略過、代號去空白", sorted(got) == ["1101", "2330"], sorted(got or {}))
check("名稱對應（打亂順序仍正確）", got["2330"] == {"date": "20261029", "shares_issued": 25_932_000_000.0,
                                         "foreign_shares_held": 18_962_000_000.0,
                                         "foreign_can_invest_ratio": 26.88, "foreign_holding_ratio": 73.12}, got["2330"])
check("`--`／空字串 → None", got["1101"]["foreign_holding_ratio"] is None and got["1101"]["foreign_can_invest_ratio"] is None)
check("stat 非 OK → None", F.fetch_mi_qfiis("20261028") is None)
install({"20261029": FakeResp({"stat": "OK", "fields": FIELDS, "data": []})})
check("data 空 → None", F.fetch_mi_qfiis("20261029") is None)
install({"20261029": FakeResp({"stat": "OK", "fields": FIELDS[:3], "data": ROWS})})
try:
    F.fetch_mi_qfiis("20261029")
    check("欄位缺少要拋錯", False, "沒拋")
except RuntimeError:
    check("欄位缺少要拋錯", True)
blocks.clear()
install({"20261029": FakeResp({"stat": "x"}, status=429)})
try:
    F.fetch_mi_qfiis("20261029")
    check("429 要拋錯", False, "沒拋")
except RuntimeError:
    check("429 要拋錯並記封鎖", blocks == [("twse_mi_qfiis", 429)], blocks)

print("二、main（暫存檔、固定今天）")


class FixedDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 30, 18, 0, tzinfo=tz) if tz else datetime(2026, 10, 30, 18, 0)


F.datetime = FixedDT
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "data").mkdir()
    (td / "data" / "company_info.json").write_text(json.dumps({"companies": {"2330": {"name": "台積電"}}}), encoding="utf-8")
    F.REPO_ROOT = td
    F.OUT_PATH = td / "data" / "foreign_holding.json"

    # 今天 10/30 沒資料、10/29 有 → 回退一天
    calls.clear()
    install({"20261029": FakeResp({"stat": "OK", "fields": FIELDS, "data": ROWS})})
    rc = F.main()
    out = json.loads(F.OUT_PATH.read_text(encoding="utf-8"))
    check("往前回退一天就停", calls == ["20261030", "20261029"], calls)
    check("寫檔 exit 0", rc == 0)
    check("名稱從 company_info 補上（沒有就 None）", out["stocks"]["2330"]["name"] == "台積電" and out["stocks"]["1101"]["name"] is None)
    check("errors 空", out["errors"] == [])

    # 全部無資料、有既有檔 → 不覆蓋
    before = F.OUT_PATH.read_text(encoding="utf-8")
    calls.clear()
    install({})
    rc = F.main()
    check("無資料最多回退 5 天（共 6 次）", calls == [f"202610{d:02d}" for d in range(30, 24, -1)], calls)
    check("有既有檔不覆蓋、exit 0", rc == 0 and F.OUT_PATH.read_text(encoding="utf-8") == before)

    # 429 → 只送 1 次、不再回退、不覆蓋
    calls.clear()
    blocks.clear()
    install({"20261030": FakeResp({"stat": "x"}, status=429)})
    rc = F.main()
    check("429 只送 1 次、不回退", calls == ["20261030"], calls)
    check("429 記封鎖、既有檔不覆蓋", blocks == [("twse_mi_qfiis", 429)] and F.OUT_PATH.read_text(encoding="utf-8") == before)

    # 沒有既有檔、全部失敗 → exit 1（寫出空檔＋errors）
    F.OUT_PATH.unlink()
    calls.clear()
    install({"20261030": FakeResp({"stat": "x"}, status=503)})
    rc = F.main()
    out = json.loads(F.OUT_PATH.read_text(encoding="utf-8"))
    check("沒有既有檔 exit 1", rc == 1, rc)
    check("寫出的空檔有 errors、stocks 空", out["stocks"] == {} and len(out["errors"]) == 1, out)

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
