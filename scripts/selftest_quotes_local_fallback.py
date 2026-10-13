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
(tmp / "data" / "trading_calendar.json").write_text(json.dumps({"tw": {"2026": {"closed": ["2026-10-26"], "unscheduled_closed": []}}}), encoding="utf-8")
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
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
