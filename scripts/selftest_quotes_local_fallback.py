# -*- coding: utf-8 -*-
"""先.八十二-4（2026-10-13）：盤中報價本機備援決策自測（git／網路／抓取全部換成假的，不碰真檔、不打 MIS）。
① 週末／休市日只記心跳  ② 盤外只記心跳  ③ 雲端 <15 分鐘略過  ④ 雲端 ≥15 分鐘才抓、標 runner、提交只含 quotes_tw
⑤ 抓完雲端已追上 → 作廢本機  ⑥ 抓取失敗 → 不提交
用法：python scripts/selftest_quotes_local_fallback.py
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
(tmp / "data" / "trading_calendar.json").write_text(json.dumps({"tw": {"2026": {"closed": ["2026-10-26"], "unscheduled_closed": []}},
                                                              "us": {"2026": {"closed": ["2026-11-26"], "early_close": {"2026-11-27": "13:00"}}}}), encoding="utf-8")
Q.ROOT, Q.HB = tmp, tmp / "research" / "hb.jsonl"
state = {"ages": [], "commits": [], "fetch_ok": True}


class FakeG:
    @staticmethod
    def rebase_in_progress():
        return False

    @staticmethod
    def _g(*a, **k):
        if a[0] == "show":
            age = state["ages"].pop(0)
            t = datetime.now(timezone.utc) - timedelta(minutes=age)
            return SimpleNamespace(stdout=json.dumps({"fetched_at": t.isoformat()}), returncode=0)
        return SimpleNamespace(stdout="", returncode=1)

    @staticmethod
    def commit_paths(paths, msg, drop_on_conflict=False):
        state["commits"].append((paths, drop_on_conflict))
        return "已 commit 並 push（假）"


def fake_run(args, **kw):
    if "fetch_quotes_us.py" in " ".join(args):
        state["us_env_key"] = (kw.get("env") or {}).get("FINNHUB_API_KEY")
        (tmp / "data" / "quotes_us.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "quotes": {}}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    if state["fetch_ok"]:
        (tmp / "data" / "quotes_tw.json").write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "meta": {}, "quotes": []}), encoding="utf-8")
    return SimpleNamespace(returncode=0 if state["fetch_ok"] else 1, stdout="", stderr="boom")


Q.G = FakeG
Q.subprocess = SimpleNamespace(run=fake_run)


def last():
    return json.loads(Q.HB.read_text(encoding="utf-8").splitlines()[-1])["decision"]


res = []
Q.main(datetime(2026, 10, 17, 10, 0, tzinfo=TW)); res.append(("①週六→skip_closed", last() == "skip_closed"))
Q.main(datetime(2026, 10, 26, 10, 0, tzinfo=TW)); res.append(("①休市日→skip_closed", last() == "skip_closed"))
Q.main(datetime(2026, 10, 14, 8, 50, tzinfo=TW)); res.append(("②盤前→skip_outside_window", last() == "skip_outside_window"))
state["ages"] = [5]
Q.main(datetime(2026, 10, 14, 10, 0, tzinfo=TW)); res.append(("③雲端 5 分鐘→skip_cloud_fresh、未抓", last() == "skip_cloud_fresh" and not state["commits"]))
state["ages"] = [40, 40]
Q.main(datetime(2026, 10, 14, 10, 0, tzinfo=TW))
q = json.loads((tmp / "data" / "quotes_tw.json").read_text(encoding="utf-8"))
res.append(("④雲端 40 分鐘→抓取並只提交 quotes_tw（衝突作廢）、標 runner", last() == "fetched" and state["commits"] == [(["data/quotes_tw.json"], True)]
            and q["meta"]["runner"]["by"] == "local_fallback"))
state["ages"] = [40, 3]
Q.main(datetime(2026, 10, 14, 10, 10, tzinfo=TW)); res.append(("⑤抓完雲端已追上→作廢本機、不提交", last() == "dropped_cloud_caught_up" and len(state["commits"]) == 1))
state["ages"], state["fetch_ok"] = [40], False
(tmp / "data" / "quotes_tw.json").unlink()
Q.main(datetime(2026, 10, 14, 10, 20, tzinfo=TW)); res.append(("⑥抓取失敗→不提交", last() == "fetch_failed" and len(state["commits"]) == 1))
# ---- 美股分支（先.一四一-3）：盤中／盤外／休市／半日市／無金鑰／雲端已更新／金鑰不外洩／最短間隔 ----
from zoneinfo import ZoneInfo  # noqa: E402
ET = ZoneInfo("America/New_York")
def et(*a):
    return datetime(*a, tzinfo=ET)
n0 = len(state["commits"])
Q.main_us(et(2026, 10, 17, 10, 0)); res.append(("美①週六→us_skip_closed", last() == "us_skip_closed"))
Q.main_us(et(2026, 11, 26, 10, 0)); res.append(("美①感恩節休市→us_skip_closed", last() == "us_skip_closed"))
Q.main_us(et(2026, 10, 14, 9, 20)); res.append(("美②開盤前 09:20→us_skip_outside_window", last() == "us_skip_outside_window"))
Q.main_us(et(2026, 11, 27, 13, 30)); res.append(("美②半日市 13:30 已收→us_skip_outside_window", last() == "us_skip_outside_window"))
state["ages"] = [5]
Q.main_us(et(2026, 10, 14, 10, 0)); res.append(("美③雲端 5 分鐘→us_skip_cloud_fresh", last() == "us_skip_cloud_fresh" and len(state["commits"]) == n0))
state["ages"] = [40]
Q.main_us(et(2026, 11, 27, 12, 30)); res.append(("美④半日市 12:30 盤中、無 .env 金鑰→us_no_key、未抓", last() == "us_no_key" and "us_env_key" not in state))
(tmp / ".env").write_text("OTHER=1" + chr(10) + "FINNHUB_API_KEY=fake_selftest_key_123" + chr(10), encoding="utf-8")
state["ages"] = [40, 40]
Q.main_us(et(2026, 10, 14, 10, 0))
hb_txt = Q.HB.read_text(encoding="utf-8")
uq = json.loads((tmp / "data" / "quotes_us.json").read_text(encoding="utf-8"))
res.append(("美⑤雲端 40 分鐘＋有金鑰→抓取、只提交 quotes_us（衝突作廢）、標 runner", last() == "us_fetched"
            and state["commits"][-1] == (["data/quotes_us.json"], True) and uq["meta"]["runner"]["by"] == "local_fallback"))
res.append(("美⑥金鑰只進子行程環境變數、不進心跳檔與輸出檔", state.get("us_env_key") == "fake_selftest_key_123"
            and "fake_selftest_key_123" not in hb_txt and "fake_selftest_key_123" not in json.dumps(uq)))
state["ages"] = [40]
Q.main_us(et(2026, 10, 14, 10, 5)); res.append(("美⑦距上次抓 <10 分鐘→us_skip_min_gap", last() == "us_skip_min_gap"))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
