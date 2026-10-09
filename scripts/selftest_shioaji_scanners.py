# -*- coding: utf-8 -*-
"""先.五十一-4 自我測試：排行榜查詢（api.scanners）。
- 4 類各查一次、每次先扣共用 10 秒窗；被拒的類別記原因、不重試、不呼叫 API；
- 單一類別 API 例外只影響該類別；漲跌幅由 close／change_price 推算；
- _rate_window_take 不扣 kbars 每日額度；
- alpha_live_server /live/scanners：今天的檔才回 available=True。
用法：python scripts/selftest_shioaji_scanners.py（純離線，假 api）。全部通過 exit 0。"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import shioaji_quotes as sq  # noqa: E402

TZ = timezone(timedelta(hours=8))
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


class FakeApi:
    def __init__(self, boom=None):
        self.calls = []
        self.boom = boom

    def scanners(self, scanner_type, ascending=True, count=100):
        self.calls.append((scanner_type, ascending, count))
        if self.boom == (scanner_type, ascending):
            raise RuntimeError("x")
        return [SimpleNamespace(code="2330", name="台積電", close=1100.0, change_price=100.0,
                                total_volume=50000, total_amount=55_000_000_000)]


FakeSj = SimpleNamespace(ScannerType=SimpleNamespace(ChangePercentRank="CPR", VolumeRank="VR", AmountRank="AR"))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="scan_"))
    now = lambda: datetime(2026, 10, 9, 10, 0, tzinfo=TZ)  # noqa: E731

    api = FakeApi()
    out = sq._poll_scanners(api, FakeSj, take=lambda: (True, ""), now_fn=now, path=tmp / "s.json")
    check("4 類各查一次、count=50", len(api.calls) == 4 and all(c[2] == 50 for c in api.calls), str(api.calls))
    check("漲幅降冪、跌幅升冪", api.calls[0][:2] == ("CPR", False) and api.calls[1][:2] == ("CPR", True))
    row = out["lists"]["change_pct_up"][0]
    check("漲跌幅由 close／change_price 推算", row["change_pct"] == 10.0, str(row))
    check("結果寫檔", json.loads((tmp / "s.json").read_text(encoding="utf-8"))["lists"]["amount"][0]["code"] == "2330")

    api = FakeApi()
    n = {"i": 0}

    def take():
        n["i"] += 1
        return (n["i"] <= 2, "" if n["i"] <= 2 else "10 秒內已查 40 次")
    out = sq._poll_scanners(api, FakeSj, take=take, now_fn=now, path=tmp / "s2.json")
    check("額度被拒的類別不呼叫 API、記原因", len(api.calls) == 2 and set(out["errors"]) == {"volume", "amount"}, str(out["errors"]))

    api = FakeApi(boom=("VR", False))
    out = sq._poll_scanners(api, FakeSj, take=lambda: (True, ""), now_fn=now, path=tmp / "s3.json")
    check("單一類別例外只影響該類別", "volume" in out["errors"] and len(out["lists"]) == 3, str(out["errors"]))

    before = sq.kbars_calls_today()
    sq._kbars_budget["window"] = []
    sq._rate_window_take()
    check("_rate_window_take 不扣 kbars 每日額度", sq.kbars_calls_today() == before)
    sq._kbars_budget["window"] = [__import__("time").time()] * sq.KBARS_RATE_MAX
    ok, why = sq._rate_window_take()
    check("共用 10 秒窗滿了就拒絕", ok is False and "上限" in why, why)
    sq._kbars_budget["window"] = []

    check("盤中窗：09:00 是、13:30 否、週六否",
          sq._is_scanner_window(datetime(2026, 10, 9, 9, 0)) and not sq._is_scanner_window(datetime(2026, 10, 9, 13, 30))
          and not sq._is_scanner_window(datetime(2026, 10, 10, 10, 0)))

    os.environ["ALPHA_SCANNERS_PATH"] = str(tmp / "srv.json")
    import alpha_live_server as srv  # noqa: E402
    srv.SCANNERS_PATH = tmp / "srv.json"
    tok = srv.LOCAL_TOKEN
    check("檔案不存在 → available=False", srv.live_scanners(tok)["available"] is False)
    (tmp / "srv.json").write_text(json.dumps({"generated_at": datetime.now(TZ).isoformat(), "lists": {"volume": [1]}}), encoding="utf-8")
    check("今天的檔 → available=True", srv.live_scanners(tok)["available"] is True)
    (tmp / "srv.json").write_text(json.dumps({"generated_at": "2020-01-01T10:00:00+08:00", "lists": {}}), encoding="utf-8")
    check("舊日期 → available=False", srv.live_scanners(tok)["available"] is False)
    try:
        srv.live_scanners("wrong-token")
        check("token 錯誤要拒絕", False)
    except Exception as e:  # noqa: BLE001
        check("token 錯誤要拒絕", True, type(e).__name__)

    print("失敗：", "、".join(fails) if fails else "無")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
