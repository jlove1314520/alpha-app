# -*- coding: utf-8 -*-
"""先.八十二-5（2026-10-13）：美股連結 ETF（00646）限價偏離 1%、其他維持 0.5%，且都不超過 max_price_dev_pct 硬限制。
用法：python scripts/selftest_us_linked_dev.py（純計算，不連券商、不送單）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import auto_rebalance_bb90 as A  # noqa: E402

res = []
d = A.dev_by_code({"max_price_dev_pct": 1.0})
res.append(("①00646＝1%，0050／00697B＝0.5%", d == {"0050": 0.5, "00646": 1.0, "00697B": 0.5}))
pc = {"0050": 100.0, "00646": 78.35, "00697B": 30.0}
o = {x["symbol"]: x["limit_price"] for x in A.plan_orders(pc, {}, 300_000, True, 0.5, d)}
res.append((f"②00646 限價在 0.5%～1% 之間（78.35→{o['00646']}）", 1.005 < o["00646"] / pc["00646"] <= 1.01 + 1e-9))
res.append(("③其他標的限價 ≤0.5%", all(o[c] / pc[c] <= 1.005 + 1e-9 for c in ("0050", "00697B"))))
res.append(("④硬限制調低（0.6%）時 00646 跟著被壓到 0.6%", A.dev_by_code({"max_price_dev_pct": 0.6})["00646"] == 0.6))
res.append(("⑤設定檔 us_linked_dev_pct 可覆寫且不超過硬限制",
            A.dev_by_code({"max_price_dev_pct": 1.0, "us_linked_dev_pct": 2.0})["00646"] == 1.0))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
