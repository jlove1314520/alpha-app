# -*- coding: utf-8 -*-
"""自測：模擬 F-翼（paper_6）與模擬 G（paper_7）前向追蹤程式結構（先.一三五-1j）。

全部在暫存目錄進行、只用合成輸入，不碰真實帳本／摘要、不打網路；只檢查結構，**不印任何淨值或報酬**。
1. 正式設定下起跑日前 step() 都是 NOT_STARTED、不寫帳本、摘要 started=false。
2. 輸入讀不到或壞掉時 main() 只印警告、回 0（十二節）。
3. 重跑冪等：同一資料日／同一季再跑一次不新增帳本列。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_5_vrp_tracker as B  # noqa: E402
import paper_6_vrp_wing_tracker as F6  # noqa: E402
import paper_7_revsurprise_tracker as G  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def lines(p: Path) -> int:
    return len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]) if p.exists() else 0


def quiet_main(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


HDR = "日期,契約,到期月份(週別),履約價,買賣權,開盤價,最高價,最低價,最後成交價,成交量,結算價,未沖銷契約量,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段"


def chain(day, rows):
    out = ["﻿" + HDR]
    for cm, k, cp, last in rows:
        out.append(f"{day.replace('-', '')},TXO,{cm},{k},{cp},-,-,-,{last},10,{last},0,-,-,-,-,,一般")
    return "\n".join(out)


td = Path(tempfile.mkdtemp(prefix="paper_6_7_selftest_"))

# ── 模擬 F-翼（paper_6）──
F6.LOG, F6.OUT, B.MARKET = td / "p6_log.jsonl", td / "p6.json", td / "market.json"
real_start6 = F6.START
check(real_start6 == "2026-11-02", "F-翼：正式起跑日 2026-11-02")
r = F6.step(today=date(2026, 10, 28), opt_text="")
check(r["state"] == "NOT_STARTED" and not F6.LOG.exists(), "F-翼：起跑前 NOT_STARTED 且不寫帳本")
s = json.loads(F6.OUT.read_text(encoding="utf-8"))
check(s.get("started") is False and s.get("why_not_started"), "F-翼：起跑前摘要 started=false、有未開始原因")


def _boom(*a, **k):
    raise OSError("合成：期交所讀不到")


orig_get, orig_start = B._get, F6.START
F6.START = "2026-10-01"  # 只在暫存目錄假裝已起跑，測輸入失敗路徑
B._get = _boom
rc, out = quiet_main(F6.main)
check(rc == 0 and "[warn]" in out and lines(F6.LOG) == 0, "F-翼：期交所讀不到 → 只警告、回 0、不寫帳本")


class _Resp:
    content = "這不是 CSV".encode("utf-8")


B._get = lambda *a, **k: _Resp()
rc, out = quiet_main(F6.main)
check(rc == 0 and "[warn]" in out and lines(F6.LOG) == 0, "F-翼：回應格式壞掉 → 只警告、回 0、不寫帳本")
B._get, F6.START = orig_get, orig_start

B.MARKET.write_text(json.dumps({"taiex": {"close": 30020.0, "data_date": "2026-11-02",
                                          "sparkline_dates": ["2026-11-02"], "sparkline": [30020.0]}}), encoding="utf-8")
rows = [("202611", 30000, "買權", 300), ("202611", 30000, "賣權", 280),
        ("202611", 30500, "買權", 80), ("202611", 29500, "賣權", 70)]
r1 = F6.step(today=date(2026, 11, 2), opt_text=chain("2026-11-02", rows))
n1 = lines(F6.LOG)
r2 = F6.step(today=date(2026, 11, 2), opt_text=chain("2026-11-02", rows))
check(r1["state"] == "ENTRY" and n1 == 1, "F-翼：合成鏈起跑日進場、寫 1 列")
check(r2["state"] == "NO_NEW_DAY" and lines(F6.LOG) == n1, "F-翼：同一資料日重跑不新增列（冪等）")

# ── 模擬 G（paper_7）──
G.LOG, G.OUT = td / "p7_log.jsonl", td / "p7.json"
check(G.START_NOT_BEFORE == "2026-11-02" and G.REBAL_MONTHS == (2, 5, 8, 11), "G：正式起跑日 2026-11-02、再平衡 2／5／8／11 月")
dates = [f"2026-10-{d:02d}" for d in range(1, 28)]
codes = [f"{1101 + i}" for i in range(25)]
syn = {c: [{"date": d, "close": 100.0, "adj_close": 100.0, "turnover": 1e8} for d in dates] for c in codes}
orig_load, orig_rank, orig_gap = G.PHS.load, G.ranking, G.load_gap_fill
G.PHS.load = lambda *a, **k: {"prices": syn}
G.ranking = lambda px, day, funds, active, gap=None: [{"code": c, "rank": i + 1, "rev_month": "2026-09"} for i, c in enumerate(codes)]
G.load_gap_fill = lambda: {}

r = G.step()
check(r["state"] == "NOT_STARTED" and not G.LOG.exists(), "G：合成最新日 10/27 早於起跑日 → NOT_STARTED、不寫帳本")
check(json.loads(G.OUT.read_text(encoding="utf-8")).get("started") is False and "nav" not in json.loads(G.OUT.read_text(encoding="utf-8")),
      "G：起跑前摘要 started=false、沒有淨值欄")

G.PHS.load = lambda *a, **k: (_ for _ in ()).throw(OSError("合成：price_history 讀不到"))
rc, out = quiet_main(G.main)
check(rc == 0 and "[warn]" in out and not G.LOG.exists(), "G：price_history 讀不到 → 只警告、回 0、不寫帳本")
G.PHS.load = lambda *a, **k: {"prices": {}}
rc, out = quiet_main(G.main)
check(rc == 0 and "[warn]" in out and not G.LOG.exists(), "G：price_history 是空的 → 只警告、回 0、不寫帳本")

G.PHS.load = lambda *a, **k: {"prices": syn}
orig_start7, orig_months = G.START_NOT_BEFORE, G.REBAL_MONTHS
G.START_NOT_BEFORE, G.REBAL_MONTHS = "2026-10-01", (10,)  # 只在暫存目錄假裝已起跑
r1 = G.step()
n1 = lines(G.LOG)
r2 = G.step()
check(r1["state"] == "INCEPTION" and n1 == 1, "G：假裝已起跑 → 建倉寫 1 列")
check(r2["state"] == "HOLD" and lines(G.LOG) == n1, "G：同一季重跑不新增列（冪等）")
G.START_NOT_BEFORE, G.REBAL_MONTHS = orig_start7, orig_months
G.PHS.load, G.ranking, G.load_gap_fill = orig_load, orig_rank, orig_gap

real_logs = [ROOT / "research" / "data" / "paper_6_log.jsonl", ROOT / "research" / "data" / "paper_7_log.jsonl"]
check(all(F6.LOG != p and G.LOG != p for p in real_logs), "沒有寫到真實帳本路徑")

print("合計", len(fails), "項失敗" if fails else "全過")
sys.exit(1 if fails else 0)
