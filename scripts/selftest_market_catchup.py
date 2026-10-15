# -*- coding: utf-8 -*-
"""先.一〇三-9 自測：market_local_catchup.py 的判斷邏輯（全程替換 git／子行程／提交，不碰 repo、不連網）。
①16:30 前 → skip_outside_window，不 fetch
②最近 5 個交易日都齊 → landed，不跑任何步驟
③只有過去兩天缺 price_history／融資維持率 → 不整批跑 market.yml，只跑兩支補缺腳本，commit 帶缺日
④今天 market_tw 沒落地 → 整批跑，融資維持率當天不另外補（market.yml 自己會產）
⑤commit 標題用資料日、不是執行當天
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import market_local_catchup as C  # noqa: E402

results, beats, ran, commits, shs = [], [], [], [], []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


class FakeDT(datetime):
    fixed = None

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


DAYS = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
saved = (C.datetime, C.heartbeat, C.sh, C.gap_check, C.recent_trading_days, C.is_trading_day, C.load_steps,
         C.prepare_worktree, C.run_steps, C.commit_push, C.cloud_running, sys.argv)
try:
    C.datetime = FakeDT
    C.heartbeat = lambda rec, commit=True: beats.append(rec)
    C.sh = lambda args, **k: shs.append(args) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    C.recent_trading_days = lambda d, n=5: DAYS
    C.is_trading_day = lambda d: True
    C.load_steps = lambda: ([{"name": "台股主班步驟", "run": "echo"}], "git add -A data/")
    C.prepare_worktree = lambda: None
    C.run_steps = lambda steps, bash: ran.append([s["name"] + "|" + s["run"] for s in steps]) or []
    C.commit_push = lambda add, backfilled=(): commits.append(list(backfilled)) or {"note": "無變動"}
    C.cloud_running = lambda *a: None
    C.bash_exe = lambda: "bash"
    sys.argv = ["x"]

    FakeDT.fixed = datetime(2026, 10, 16, 7, 50, tzinfo=C.TW)
    C.gap_check = lambda days: ("2026-10-15", {"2026-10-16": ["market_tw"]})
    C.main()
    check("①07:50 → skip_outside_window 且沒 fetch", beats[-1]["result"] == "skip_outside_window" and not shs and not ran)

    FakeDT.fixed = datetime(2026, 10, 16, 17, 30, tzinfo=C.TW)
    C.gap_check = lambda days: ("2026-10-16", {})
    C.main()
    check("②都齊 → landed、不跑步驟", beats[-1]["result"] == "landed" and not ran)

    C.gap_check = lambda days: ("2026-10-16", {"2026-10-13": ["price_history(600/2139)", "margin_maintenance"],
                                               "2026-10-14": ["margin_maintenance"]})
    C.main()
    names = ran[-1] if ran else []
    check("③只缺過去 → 不跑主班、只跑兩支補缺",
          len(names) == 2 and "backfill_price_history_gaps" in names[0]
          and names[1].endswith("backfill_margin_maintenance.py 2026-10-13 2026-10-14"))
    check("③commit 帶缺日", commits[-1] == ["2026-10-13", "2026-10-14"])

    C.gap_check = lambda days: ("2026-10-15", {"2026-10-16": ["market_tw", "margin_maintenance"],
                                               "2026-10-14": ["margin_maintenance"]})
    C.main()
    names = ran[-1]
    check("④今天沒落地 → 整批跑＋只補 10/14 融資維持率",
          names[0].startswith("台股主班步驟") and names[-1].endswith("backfill_margin_maintenance.py 2026-10-14")
          and not any("backfill_price_history_gaps" in n for n in names))
finally:
    (C.datetime, C.heartbeat, C.sh, C.gap_check, C.recent_trading_days, C.is_trading_day, C.load_steps,
     C.prepare_worktree, C.run_steps, C.commit_push, C.cloud_running, sys.argv) = saved

t = C.commit_title("2026-10-15", ["2026-10-13"], 3)
check("⑤標題用資料日", "資料日 2026-10-15" in t and "10/13" in t)
print(f"{sum(results)}/{len(results)} PASS")
sys.exit(0 if all(results) else 1)
