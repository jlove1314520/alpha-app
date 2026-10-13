# -*- coding: utf-8 -*-
"""先.八十二-11（2026-10-13）：融資維持率與籌碼K 每日校準自測（暫存檔＋假推播＋假重估，不碰真讀數、不打網路）。
① 登錄讀數：同日取代、格式錯擋下  ② 誤差 ≤2pp → 不推不重估  ③ 誤差 >2pp → 推播一次＋重估一次
④ 同一筆讀數第二天不再處理  ⑤ 10/07 以前的讀數不拿來比（方法不同）  ⑥ 讀數超過 8 天 → 提醒，7 天內不重複
用法：python scripts/selftest_margin_ck_check.py
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ck_reading as R  # noqa: E402
import margin_ck_check as C  # noqa: E402

tmp = Path(tempfile.mkdtemp())
R.EXT = tmp / "ext.json"
C.LOCAL, C.STATE, C.LOG, C.CAL = tmp, tmp / "st.json", tmp / "log.jsonl", tmp / "cal.json"
C.CAL.write_text(json.dumps({"mode": "linear", "alpha": 0.0, "beta": 0.9, "k": 0.9}), encoding="utf-8")
pushes, reest = [], []
P = lambda t, b: (pushes.append(t), {"ok": 1})[1]  # noqa: E731
E = lambda: (reest.append(1), "已 commit 並 push（假）")[1]  # noqa: E731
mm = [{"date": "2026-10-05", "ratio_pct": 190.0}, {"date": "2026-10-16", "ratio_pct": 190.0}]  # 本站估＝171.0
res = []
R.add("2026-10-16", 3400.0, 172.0, R.EXT); R.add("2026-10-16", 3400.0, 172.5, R.EXT)
try:
    R.add("2026-10-17", 3400.0, 9999.0, R.EXT); bad_ok = False
except ValueError:
    bad_ok = True
res.append(("①同日取代、離譜數字擋下", R.load(R.EXT)["points"] == [["2026-10-16", 3400.0, 172.5]] and bad_ok))
r = C.main(today=date(2026, 10, 16), push=P, reestimate=E, margin=mm)
res.append(("②誤差 1.5pp（≤2）→不推不重估", r["decision"] == "within_2pp" and r["err_pp"] == -1.5 and not pushes and not reest))
R.add("2026-10-16", 3400.0, 174.0, R.EXT)
r = C.main(today=date(2026, 10, 16), push=P, reestimate=E, margin=mm)
res.append(("③誤差 3pp → 推播＋重估各一次", r["decision"] == "over_2pp_reestimated" and len(pushes) == 1 and len(reest) == 1))
r = C.main(today=date(2026, 10, 17), push=P, reestimate=E, margin=mm)
res.append(("④同一筆第二天不再處理", r["decision"] == "already_handled" and len(pushes) == 1 and len(reest) == 1))
R.EXT.write_text(json.dumps({"points": [["2026-10-05", 3400.0, 180.0]]}), encoding="utf-8")
C.STATE.write_text("{}", encoding="utf-8")
r = C.main(today=date(2026, 10, 6), push=P, reestimate=E, margin=mm)
res.append(("⑤10/07 以前的讀數不拿來比", r["decision"] == "no_comparable_reading" and len(reest) == 1))
n0 = len(pushes)
C.main(today=date(2026, 10, 20), push=P, reestimate=E, margin=mm)
C.main(today=date(2026, 10, 22), push=P, reestimate=E, margin=mm)
C.main(today=date(2026, 10, 27), push=P, reestimate=E, margin=mm)
res.append(("⑥讀數超過 8 天→提醒，7 天內不重複", pushes[n0:] == ["請貼本週籌碼K讀數", "請貼本週籌碼K讀數"]))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
