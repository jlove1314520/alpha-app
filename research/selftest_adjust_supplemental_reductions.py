# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 017（2026-10-22）自測：adjust.py 官方減資補充事件。離線（擋網路、只讀本機快取），不算任何報酬。

1. 四個案例（1441／1506／1526 2010-10、1413 2014-11）：FinMind 路徑還原後，停牌前最後一天→恢復日的還原報酬
   落在物理上可能的範圍（|報酬| < 11%）；不補時原本跳 18%～66%。
2. 回歸：所有有補充事件的股票＋固定種子抽 30 檔沒有補充事件的股票，「有補充檔」與「沒有補充檔（＝舊行為）」比對：
   2015-01-01 以後 adj_close 逐列完全相同；沒有補充事件的股票全期完全相同。
跑法：cd research && python selftest_adjust_supplemental_reductions.py [--n-other 30]
"""
import random
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (selftest_adjust_supplemental_reductions)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import adjust  # noqa: E402
from finmind_client import _cache_path  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

START = "2010-01-01"

# 離線：本機沒有快取的「分割／減資」表當成空表（有快取就照讀）。有補充檔與沒補充檔兩次計算用同一套，比對仍公平。
_real_load_dev = adjust.load_dev


def _load_dev_offline(ds, sid, *a, **k):
    if ds in ("TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice") and sid and             not _cache_path(ds, sid, a[0] if a else START, VAL_END).exists():
        return pd.DataFrame()
    return _real_load_dev(ds, sid, *a, **k)


adjust.load_dev = _load_dev_offline
CASES = {"1441": "2010-10", "1506": "2010-10", "1526": "2010-10", "1413": "2014-11"}
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def frame(sid: str, with_supp: bool) -> pd.DataFrame:
    real = adjust.SUPPLEMENTAL_REDUCTIONS
    adjust._SUPP_CACHE = None
    if not with_supp:
        adjust.SUPPLEMENTAL_REDUCTIONS = real.with_name("__none__.csv")
    try:
        return adjust._finmind_adjusted_frame(sid, START)
    finally:
        adjust.SUPPLEMENTAL_REDUCTIONS = real
        adjust._SUPP_CACHE = None


def cached(sid: str) -> bool:
    need = ["TaiwanStockPrice", "TaiwanStockDividend"]
    return all(_cache_path(ds, sid, START, VAL_END).exists() for ds in need)


ev = pd.read_csv(adjust.SUPPLEMENTAL_REDUCTIONS, dtype={"stock_id": str})
red = ev[ev["kind"].isin(["reduction", "reduction_assumed"])]

# 1. 四個案例
for sid, ym in CASES.items():
    e = red[(red["stock_id"] == sid) & (red["resume_date"].str[:7] == ym)]
    if e.empty or not cached(sid):
        check(f"1 {sid} {ym}", False, "補充檔沒有這個事件或本機快取不全")
        continue
    r = e.iloc[0]
    out = {}
    for w in (False, True):
        f = frame(sid, w).set_index("date")
        out[w] = f.loc[r["resume_date"], "adj_close"] / f.loc[r["pre_date"], "adj_close"] - 1
    check(f"1 {sid} {r['pre_date']}→{r['resume_date']} 還原後不再跳價", abs(out[True]) < 0.11,
          f"不補 {out[False]:+.1%} → 補 {out[True]:+.1%}（係數 {r['factor']:.4f}，{r['source']}）")

# 2. 回歸
with_ev = sorted(set(red["stock_id"]))
pool = sorted({p.name.split("__")[1] for p in (Path(adjust.__file__).parent / "data" / "raw").glob(f"TaiwanStockPrice__*__{START}__*.parquet")}
              - set(with_ev))
n_other = int(sys.argv[sys.argv.index("--n-other") + 1]) if "--n-other" in sys.argv else 30
random.seed(20261022)
others = random.sample([s for s in pool if len(s) == 4 and cached(s)], n_other)
bad_post, bad_other, n_ok_ev, skipped = [], [], 0, []
for sid in [s for s in with_ev if cached(s)] + others:
    try:
        a, b = frame(sid, False), frame(sid, True)
    except Exception as e:  # noqa: BLE001
        skipped.append(f"{sid}:{type(e).__name__}")
        continue
    if a.empty or b.empty or "adj_close" not in a.columns or "adj_close" not in b.columns:
        skipped.append(f"{sid}:empty")
        continue
    m = a[["date", "adj_close"]].merge(b[["date", "adj_close"]], on="date", suffixes=("_old", "_new"))
    post = m[m["date"] >= "2015-01-01"]
    if not np.array_equal(post["adj_close_old"].to_numpy(), post["adj_close_new"].to_numpy(), equal_nan=True):
        bad_post.append(sid)
    if sid in others and not np.array_equal(m["adj_close_old"].to_numpy(), m["adj_close_new"].to_numpy(), equal_nan=True):
        bad_other.append(sid)
    n_ok_ev += sid in with_ev
check(f"2a 有補充事件的 {n_ok_ev} 檔：2015 以後 adj_close 完全不變", not [s for s in bad_post if s in with_ev], str(bad_post[:10]))
check(f"2b 沒有補充事件的 {len(others)} 檔：全期完全不變", not bad_other, str(bad_other[:10]))
if skipped:
    print(f"     略過（本機快取不全或讀取失敗）{len(skipped)} 檔：{skipped[:10]}")
print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
