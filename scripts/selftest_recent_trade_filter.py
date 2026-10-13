# -*- coding: utf-8 -*-
"""先.八十二-3（2026-10-13）：選股榜「近期無成交」判定自測。
① 近 5 交易日無成交 → 剔除  ② 不在最新快照（快照完整）→ 剔除  ③ 上櫃整批晚一天（最新日檔數不足 90%）→ 不因快照剔除
④ 正常成交 → 不剔除  ⑤ 資料日早於生效日 2026-10-14 → 不剔除、只回報會剔除幾檔  ⑥ 真資料：3085、8183 會被剔除
用法：python scripts/selftest_recent_trade_filter.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import price_history_store as S  # noqa: E402
import recent_trade_filter as F  # noqa: E402

D = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21"]


def rows(dates, vol=1000):
    return [{"date": d, "close": 10.0, "volume": vol} for d in dates]


def market(extra, n_fill=40, last_ok=True):
    p = {"0050": rows(D)}
    for i in range(n_fill):  # 填充全市場檔數（讓中位數有意義）
        p[f"9{i:03d}"] = rows(D if last_ok or i < n_fill // 2 else D[:-1])
    p.update(extra)
    return p


res = []
out, info = F.evaluate(market({"1111": rows(D[:1]) + rows(D[1:], vol=0)}))
res.append(("①近 5 交易日無成交→剔除", "1111" in out and "無成交" in out["1111"] and info["applied"]))
out, info = F.evaluate(market({"2222": rows(D[:-1])}))
res.append(("②不在最新快照（快照完整）→剔除", "2222" in out and "不在官方最新快照" in out["2222"]))
out, info = F.evaluate(market({"3333": rows(D[:-1])}, last_ok=False))
res.append(("③最新日檔數不足 90%（上櫃整批晚一天）→不因快照剔除", "3333" not in out and not info["snapshot_check"]))
out, info = F.evaluate(market({"4444": rows(D)}))
res.append(("④正常成交→不剔除", "4444" not in out))
early = [d.replace("2026-10", "2026-09") for d in D]
p = {"0050": rows(early), "5555": rows(early[:1])}
out, info = F.evaluate(p)
res.append(("⑤資料日早於 2026-10-14→不剔除、只回報會剔除", out == {} and info["applied"] is False and info["would_exclude"] == 1))
real = S.load(codes=["0050", "3085", "8183"])["prices"]
F.EFFECTIVE_DATE = "2000-01-01"  # 只為驗證真實資料的判定，不影響正式程式
out, info = F.evaluate(real)
res.append((f"⑥真資料 3085／8183 會被剔除（{out.get('3085')}；{out.get('8183')}）", "3085" in out and "8183" in out))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
