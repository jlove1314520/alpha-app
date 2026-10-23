# -*- coding: utf-8 -*-
"""先.一三二-0 ④：模擬 I 追蹤程式（research/paper_9_breakout_tracker.py）規則邏輯自測——只用合成價格，不讀任何真實資料。

把回看資料夾指到空的暫存資料夾、用 2027～2028 的合成日線（全部 > 回看截止日，走前向路徑）餵 _day()，檢查：
1. 252 日新高＋1.5 倍量 → 訊號日當天不進場、t+1 收盤才進場；
2. 從進場後最高還原收盤回落 ≥10% → 隔一交易日收盤賣出，exit_reason=trailing_stop；
3. 持有滿 60 個交易日 → 隔日賣出，exit_reason=hold_days；
4. 量不夠 1.5 倍時不產生訊號；
5. 除權息（adj/close 比值跳動）不會被當成跌破停損。
跑法：python scripts/selftest_paper_9_logic.py
"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paper_9_breakout_tracker as T  # noqa: E402
from paper_forward_common import Px  # noqa: E402


def days(n, start=date(2027, 1, 4)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def run(path_fn, vol_fn, n=330, exdiv_at=None):
    """單一股票 1101 的合成序列；exdiv_at＝該日起現金股利 5 元（adj 往回縮）。"""
    ds = days(n)
    rows = []
    for i, d in enumerate(ds):
        c = path_fn(i)
        rows.append({"date": d, "close": c, "volume": vol_fn(i), "turnover": 1e9})
    if exdiv_at is not None:
        f = None
        for i, r in enumerate(rows):
            if i < exdiv_at:
                f = (rows[exdiv_at - 1]["close"] - 5) / rows[exdiv_at - 1]["close"]
                r["adj_close"] = r["close"] * f
            else:
                r["adj_close"] = r["close"]
    else:
        for r in rows:
            r["adj_close"] = r["close"]
    prices = {"1101": rows}
    px = Px(prices)
    T.LOOKBACK_DIR = Path(tempfile.mkdtemp())
    series = T._series(prices)
    state = {"positions": {}, "cash": T.INITIAL, "started": False, "pending_entries": [], "pending_exits": []}
    recs = []
    for d in ds:
        rec = T._day(px, series, d, state, {"1101"}, 0.001425, 0.004425)
        state = {k: rec[k] for k in ("positions", "cash", "pending_entries", "pending_exits")}
        state["started"] = True
        recs.append(rec)
    return ds, recs


res = []
# 情境 A：平盤 100 元 300 天，第 300 天（索引 299）放量突破到 110，之後漲到 120 再跌到 107（回落 >10%）
def pa(i):
    if i < 299:
        return 100.0
    if i < 305:
        return 110.0 + (i - 299) * 2   # 110→120
    return 107.0
ds, recs = run(pa, lambda i: 3_000_000 if i == 299 else 1_000_000)
sig = [r for r in recs if r["pending_entries"]]
ent = [r for r in recs if r["entered"]]
ext = [c for r in recs for c in r["closed_trades"]]
res.append(("A 訊號日＝突破當天", bool(sig) and sig[0]["date"] == ds[299]))
res.append(("A 進場＝訊號隔一交易日", bool(ent) and ent[0]["date"] == ds[300]))
res.append(("A 停損：跌破高點 10% 隔日賣出", bool(ext) and ext[0]["exit_reason"] == "trailing_stop" and ext[0]["exit_date"] == ds[306]))
res.append(("A 帳本不早於起跑日（合成日期皆 ≥2027）", all(r["date"] >= T.START_NOT_BEFORE for r in recs)))

# 情境 B：量只有 1.4 倍 → 不產生訊號
ds, recs = run(pa, lambda i: 1_400_000 if i == 299 else 1_000_000)
res.append(("B 量不足 1.5 倍不進場", not any(r["entered"] for r in recs)))

# 情境 C：突破後一路緩漲、持有滿 60 日出場
ds, recs = run(lambda i: 100.0 if i < 299 else 110.0 + (i - 299) * 0.1, lambda i: 3_000_000 if i == 299 else 1_000_000, n=400)
ext = [c for r in recs for c in r["closed_trades"]]
res.append(("C 持有滿 60 日隔日賣出", bool(ext) and ext[0]["exit_reason"] == "hold_days" and ext[0]["exit_date"] == ds[300 + 60 + 1]))

# 情境 D：進場後除息 5 元（原始收盤 118→113，還原價不跌）→ 不觸發停損
ds, recs = run(lambda i: 100.0 if i < 299 else (118.0 if i < 320 else 113.0), lambda i: 3_000_000 if i == 299 else 1_000_000,
               n=340, exdiv_at=320)
ext = [c for r in recs for c in r["closed_trades"]]
res.append(("D 除息不被當成跌破停損", not any(c["exit_reason"] == "trailing_stop" for c in ext)))

for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
nb = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {nb}")
sys.exit(1 if nb else 0)
