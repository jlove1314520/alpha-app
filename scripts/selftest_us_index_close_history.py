# -*- coding: utf-8 -*-
"""自測：美股四大指數收盤累積（先.一三八-5）。零外部請求，只寫暫存目錄。"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
import us_index_close_history as H  # noqa: E402
import backfill_us_index_close_history as B  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "h.json"
    mu = {"fetched_at": "2026-10-28T21:43:00+00:00", "indices": {
        "^SOX": {"name": "費城半導體指數", "close": 11450.71, "as_of": "2026-10-27", "intraday": False},
        "^DJI": {"name": "道瓊", "close": 1.0, "as_of": "2026-10-28", "intraday": True},
    }}
    check("盤中值不寫、收盤寫一列", H.append_from_market_us(mu, path=p) == 1)
    d = json.loads(p.read_text(encoding="utf-8"))
    check("^DJI 盤中沒有寫入", "^DJI" not in d["series"])
    check("同日同值重跑不變動", H.append_from_market_us(mu, path=p) == 0)
    mu["indices"]["^SOX"]["close"] = 11460.0
    check("同日新值覆蓋、不重複", H.append_from_market_us(mu, path=p) == 1
          and len(json.loads(p.read_text(encoding="utf-8"))["series"]["^SOX"]) == 1)
    p.write_text("{壞檔", encoding="utf-8")
    try:
        H.append_from_market_us(mu, path=p)
        check("壞檔丟例外（不覆蓋）", False)
    except RuntimeError:
        check("壞檔丟例外（不覆蓋）", p.read_text(encoding="utf-8") == "{壞檔")

check("交易日計算跳過週末與 Labor Day",
      B._trading_days_between("2026-09-04", "2026-09-09") == ["2026-09-08"])

# sparkline 錨定：a=09-11、b=09-17 之間缺 14/15/16
best = {
    ("^X", "2026-09-11"): (1, 10.0, None, []),
    ("^X", "2026-09-17"): (2, 14.0, None, []),
    ("^X", "2026-09-18"): (3, 15.0, None, [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0]),
}
f = B.sparkline_fill(best)
check("錨定吻合才補三天", f == {("^X", "2026-09-14"): 11.0, ("^X", "2026-09-15"): 12.0, ("^X", "2026-09-16"): 13.0})
best[("^X", "2026-09-18")] = (3, 15.0, None, [9.0, 10.0, 11.0, 12.0, 14.0, 15.0])  # 少一點 → 對不上
check("點數對不上就不補", B.sparkline_fill(best) == {})

print(f"\n{'全部通過' if not fails else f'{fails} 項失敗'}")
sys.exit(1 if fails else 0)
