# -*- coding: utf-8 -*-
"""先.一五八-1 自測：research/paper_opt_regime.py（F3／F5／F2／F3F5 每日產生器）。零外部請求，不動正式帳本。

① 逐日重播：用種子（batch1 同一份 0050 資料）在聯集日曆上跑產生器的 sig_f3／sig_f5／step()，
   2025-01-02 起累積報酬要跟 bt_regime.json 回測曲線差 <0.5 個百分點（差異來源：起跑建倉成本、無風險利率用常數）。
② 暫存目錄試跑（--start 2026-11-03）：F3／F5 每個交易日各一列、F3F5＝兩帳戶權益平均、
   美股檔沒有 VTI／IEF 時 F2 一列都不寫（不拿 0 頂替）、第二次跑不重寫。
③ step() 停損：合成一路下跌 → 觸發 account_stop、冷卻 21 天內 0050 權重歸零。
用法：python scripts/selftest_paper_opt_regime.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_opt_regime as G  # noqa: E402
import paper_opt_f12 as F12  # noqa: E402

ok_all = True


def check(name: str, cond: bool, info: str = "") -> None:
    global ok_all
    ok_all &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'} {name} {info}")


# ①
seed = json.loads(G.SEED.read_text(encoding="utf-8"))
bt = json.loads((G.OUT / "bt_regime.json").read_text(encoding="utf-8"))
ds, rs = seed["dates"], seed["r_0050"]
px, vols, rf = G.levels(rs), G.vol_hist(rs), F12.rf_daily()
i0 = ds.index("2025-01-02")
for fid in ("F3", "F5"):
    s, sp, a = G.new_acct(), G.SPEC[fid], []
    for i in range(i0, len(ds)):
        e = G.sig_f3(px, i - 1) if fid == "F3" else G.sig_f5(vols, i - 1)
        r, _, _ = G.step(s, sp, {"0050": e, "CASH": 1 - e}, {"0050": G.lev(rs[i], sp["L"], rf), "CASH": rf},
                         ds[i - 1][:7] != ds[i][:7])
        a.append((r, bt["curves"][fid][i]))
    a = np.array(a)
    p, b = np.prod(1 + a[:, 0]) - 1, np.prod(1 + a[:, 1]) - 1
    check(f"①{fid} 重播對回測", abs(p - b) < 0.005, f"重播 {p:+.2%}／回測 {b:+.2%}")

# ②
tmp = Path(tempfile.mkdtemp())
try:
    G.OUT, G.STATE = tmp, tmp / "state_regime.json"
    us_tmp = tmp / "us_returns.json"
    us = json.loads((F12.OUT / "us_returns.json").read_text(encoding="utf-8"))
    for d in us["returns"]:
        us["returns"][d].pop("VTI", None)
        us["returns"][d].pop("IEF", None)
    us_tmp.write_text(json.dumps(us), encoding="utf-8")
    G.US = us_tmp
    sys.argv = ["x", "--start", "2026-11-03"]
    G.main()
    rows = {k: [json.loads(x) for x in (tmp / f"ledger_{k}.jsonl").read_text(encoding="utf-8").splitlines()]
            if (tmp / f"ledger_{k}.jsonl").exists() else [] for k in ("F3", "F5", "F2", "F3F5")}
    cal = [d for d in json.loads(F12.BARS.read_text(encoding="utf-8"))["calendar"] if d >= "2026-11-03"]
    check("②F3／F5 每個交易日一列", len(rows["F3"]) == len(cal) == len(rows["F5"]), f"{len(rows['F3'])}/{len(rows['F5'])}/{len(cal)}")
    last = rows["F3F5"][-1] if rows["F3F5"] else {}
    check("②F3F5＝兩帳戶平均", bool(last) and abs(last["account"] - 0.5 * (rows["F3"][-1]["account"] + rows["F5"][-1]["account"])) < 1e-6)
    check("②缺 VTI／IEF 時 F2 不寫", rows["F2"] == [])
    G.main()
    n2 = len((tmp / "ledger_F3.jsonl").read_text(encoding="utf-8").splitlines())
    check("②第二次跑不重寫", n2 == len(rows["F3"]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ③
s, sp = G.new_acct(), G.SPEC["F3"]
evts, ws = [], []
for k in range(40):
    r50 = -0.02 if k < 10 else 0.0
    _, _, e = G.step(s, sp, {"0050": 1.0, "CASH": 0.0}, {"0050": G.lev(r50, 3.0, 0.0), "CASH": 0.0}, False)
    evts.append(e)
    ws.append(s["w"].get("0050", 0.0))
k = evts.index("account_stop") if "account_stop" in evts else -1
check("③停損觸發", k >= 0, f"第 {k + 1} 天")
check("③冷卻期 0050 歸零、21 天後回來", k >= 0 and all(w == 0 for w in ws[k + 1:k + 22]) and ws[k + 22] > 0)

print("\n結果：" + ("全部通過" if ok_all else "有 FAIL"))
sys.exit(0 if ok_all else 1)
