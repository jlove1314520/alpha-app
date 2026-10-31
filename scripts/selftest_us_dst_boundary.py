# -*- coding: utf-8 -*-
"""先.一三五-1gb（2026-11-01）：美股夏令時間切換（2026-11-01 結束、2027-03-14 開始）邊界自測。
既有 selftest_quotes_local_fallback.py 直接餵美東時間，沒測「台北時間 → 美東」換算跨 DST 的那一步；
這支改餵台北時間（本機排程實際給的就是台北時間），確認 main_us 的盤中窗口跟著 EDT／EST 平移一小時。
git／網路／抓取全部換成假的，不碰真檔、不送任何請求；雲端一律假裝「5 分鐘前剛更新」，
所以盤中窗口內的判定一定停在 us_skip_cloud_fresh、窗口外停在 us_skip_outside_window。
用法：python scripts/selftest_us_dst_boundary.py
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import quotes_local_fallback as Q  # noqa: E402

TW = timezone(timedelta(hours=8))
tmp = Path(tempfile.mkdtemp())
(tmp / "data").mkdir()
(tmp / "research").mkdir()
(tmp / "data" / "trading_calendar.json").write_text(json.dumps({"us": {"2026": {"closed": ["2026-11-26"], "early_close": {}}}}), encoding="utf-8")
Q.ROOT, Q.HB = tmp, tmp / "research" / "hb.jsonl"


class FakeG:
    @staticmethod
    def rebase_in_progress():
        return False

    @staticmethod
    def _g(*a, **k):
        if a[0] == "show":
            t = datetime.now(timezone.utc) - timedelta(minutes=5)
            return SimpleNamespace(stdout=json.dumps({"fetched_at": t.isoformat()}), returncode=0)
        return SimpleNamespace(stdout="", returncode=1)

    @staticmethod
    def commit_paths(paths, msg, drop_on_conflict=False):
        raise AssertionError("自測不應走到提交")


def no_run(*a, **k):
    raise AssertionError("自測不應走到抓取")


Q.G = FakeG
Q.subprocess = SimpleNamespace(run=no_run)


def decide(*a):
    Q.main_us(datetime(*a, tzinfo=TW))
    return json.loads(Q.HB.read_text(encoding="utf-8").splitlines()[-1])["decision"]


IN, OUT, CLOSED = "us_skip_cloud_fresh", "us_skip_outside_window", "us_skip_closed"
cases = [
    # (說明, 台北時間, 預期)
    ("EDT 最後一週：10/30(五) 台北 21:35＝美東 09:35 盤中", (2026, 10, 30, 21, 35), IN),
    ("EDT 最後一週：10/31 台北 03:55＝美東 10/30 15:55 盤中", (2026, 10, 31, 3, 55), IN),
    ("EDT 最後一週：10/31 台北 04:05＝美東 10/30 16:05 已收", (2026, 10, 31, 4, 5), OUT),
    ("切換當天：11/01(日) 台北 14:00 → 美東週日休市", (2026, 11, 1, 14, 0), CLOSED),
    ("EST 第一天：11/02(一) 台北 21:35＝美東 08:35 盤前（EDT 時會是盤中）", (2026, 11, 2, 21, 35), OUT),
    ("EST 第一天：11/02 台北 22:35＝美東 09:35 盤中", (2026, 11, 2, 22, 35), IN),
    ("EST 第一天：11/03 台北 04:55＝美東 11/02 15:55 盤中（EDT 時會是已收）", (2026, 11, 3, 4, 55), IN),
    ("EST 第一天：11/03 台北 05:05＝美東 11/02 16:05 已收", (2026, 11, 3, 5, 5), OUT),
    ("EST：11/26 感恩節 台北 23:00 → 休市", (2026, 11, 26, 23, 0), CLOSED),
    ("EDT 重新開始：2027-03-15(一) 台北 21:35＝美東 09:35 盤中（2027 日曆未建、退回只看週末）", (2027, 3, 15, 21, 35), IN),
    ("EDT 重新開始：2027-03-16 台北 04:05＝美東 03/15 16:05 已收", (2027, 3, 16, 4, 5), OUT),
]
res = [(n, decide(*t) == exp) for n, t, exp in cases]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
