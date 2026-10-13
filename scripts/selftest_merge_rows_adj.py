# -*- coding: utf-8 -*-
"""先.八十一-51（2026-10-13）：merge_rows 取代同日列時保留還原比例的自測（重現當初的錯）。

情境（2614 實例）：10/06 除息、係數約 0.9065。排程 A 已把 10/06 之前的列乘上係數（事件標 applied）；
排程 B 因 OpenAPI T+1 落後又拿到 10/05 的資料再 merge 一次——修正前 10/05 被蓋回 adj＝close。
① 修正後重 merge 10/05：adj_close 仍＝新 close × 原比例
② 新日期（原本沒有的列）照舊 adj＝close
③ 原本比例＝1 的列被取代後仍是 adj＝close
④ 保留最後 90 筆的行為不變
用法：python scripts/selftest_merge_rows_adj.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import update_price_history as U  # noqa: E402


def row(d, c):
    return {"date": d, "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1, "turnover": c}


res = []
prices = {"2614": [row("2026-10-02", 19.25), row("2026-10-05", 19.1)]}
prices["2614"] = U.merge_rows(prices["2614"], row("2026-10-06", 15.95))
ledger = {"events": {"2614": [{"ex_date": "2026-10-06", "cash": 1.785, "stock_ratio": 0.0, "rights_ratio": 0.0,
                               "rights_price": 0.0, "type": "息", "first_seen": "2026-08-26", "applied": False}]}}
n = U.apply_dividend_adjustments(prices, ledger, "2026-10-06")
f = ledger["events"]["2614"][0].get("factor_applied")
r05 = next(r for r in prices["2614"] if r["date"] == "2026-10-05")
ok_apply = n == 1 and f and abs(r05["adj_close"] - 19.1 * f) < 1e-6
res.append(("前置：除權息係數套用到 10/05", bool(ok_apply)))
prices["2614"] = U.merge_rows(prices["2614"], row("2026-10-05", 19.1))  # 排程 B：落後的 10/05 再 merge
r05 = next(r for r in prices["2614"] if r["date"] == "2026-10-05")
res.append(("①重 merge 10/05 後仍保留還原比例", abs(r05["adj_close"] - 19.1 * f) < 1e-5))
prices["2614"] = U.merge_rows(prices["2614"], row("2026-10-07", 15.45))
r07 = next(r for r in prices["2614"] if r["date"] == "2026-10-07")
res.append(("②新日期 adj＝close", r07["adj_close"] == 15.45))
prices["2614"] = U.merge_rows(prices["2614"], row("2026-10-06", 15.96))
r06 = next(r for r in prices["2614"] if r["date"] == "2026-10-06")
res.append(("③比例＝1 的列取代後仍 adj＝close", r06["adj_close"] == 15.96))
# ⑤（先.八十一-52）除息日前一天的列在事件套用「之後」才第一次插入：fix_inserted_rows 補上係數、移除 _ins
p2 = {"6108": [row("2026-10-02", 25.0)]}
p2["6108"] = U.merge_rows(p2["6108"], row("2026-10-07", 25.95))
lg2 = {"events": {"6108": [{"ex_date": "2026-10-07", "cash": 1.0, "stock_ratio": 0.0, "rights_ratio": 0.0,
                             "rights_price": 0.0, "type": "息", "first_seen": "2026-08-26", "applied": False}]}}
for r in p2["6108"]:
    r.pop("_ins", None)  # 視為前幾輪就已存在的列
U.apply_dividend_adjustments(p2, lg2, "2026-10-07")
f2 = lg2["events"]["6108"][0]["factor_applied"]
p2["6108"] = U.merge_rows(p2["6108"], row("2026-10-06", 25.4))  # 晚到的 10/06（除息日前一天）
p2["6108"] = U.merge_rows(p2["6108"], row("2026-10-08", 26.0))  # 今天最新一筆
n5 = U.fix_inserted_rows(p2, lg2)
r06 = next(r for r in p2["6108"] if r["date"] == "2026-10-06")
r08 = next(r for r in p2["6108"] if r["date"] == "2026-10-08")
res.append(("⑤晚到的除息日前一天列補上係數", n5 == 1 and abs(r06["adj_close"] - 25.4 * f2) < 1e-5))
res.append(("⑤最新一筆維持 adj＝close、標記已移除", r08["adj_close"] == 26.0 and not any("_ins" in r for r in p2["6108"])))
long = [row(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", 10.0) for i in range(95)]
res.append(("④保留最後 90 筆", len(U.merge_rows(long, row("2026-12-31", 10.0))) == U.PRICE_HISTORY_DAYS))
for n_, ok in res:
    print(("PASS " if ok else "FAIL ") + n_)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
