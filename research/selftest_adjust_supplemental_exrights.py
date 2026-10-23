# -*- coding: utf-8 -*-
"""先.一三三-1c／收件匣 021（2026-10-23）自測：adjust.py 官方除權息補充事件。離線（擋網路、只讀本機快取），不算任何報酬。

1. 案例（自動挑、各 3 檔，優先原始價除息日跌幅大的）：
   a. 2009 年 FinMind 漏記（FinMind 2009 整年缺漏；官方有、FinMind 同日沒有）；
   b. FinMind 股利快取整段零筆的股票；
   檢查：補充後除息日還原報酬＝收盤÷官方參考價−1（逐值，1e-9），且與補充前不同（補充前是原始跌幅）。
2. 回歸：所有有補充事件的股票（2010 起快取）＋固定種子 30 檔沒有補充事件的股票，「有／沒有補充檔」比對：
   2015-01-01 以後 adj_close 逐列完全相同；沒有補充事件的股票全期完全相同。
跑法：cd research && python selftest_adjust_supplemental_exrights.py
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
    raise RuntimeError("network blocked (selftest_adjust_supplemental_exrights)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import adjust  # noqa: E402
from finmind_client import _cache_path  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

CASE_START, REG_START = "2006-01-01", "2010-01-01"
_real_load_dev = adjust.load_dev


def _load_dev_offline(ds, sid, *a, **k):
    st = a[0] if a else REG_START
    if ds in ("TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice", "TaiwanStockParValueChange") \
            and not _cache_path(ds, sid, st, VAL_END).exists():
        return pd.DataFrame()
    # V1 抓的 2006 起快取迄日是 2014-12-31（不是 VAL_END）；測 2009 案例時改讀那份（只在自測裡，不影響 adjust.py）
    if not a[1:] and "end_date" not in k and not _cache_path(ds, sid, st, VAL_END).exists()             and _cache_path(ds, sid, st, "2014-12-31").exists():
        return _real_load_dev(ds, sid, st, "2014-12-31")
    return _real_load_dev(ds, sid, *a, **k)


adjust.load_dev = _load_dev_offline
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def frame(sid, start, with_supp):
    real = adjust.SUPPLEMENTAL_EXRIGHTS
    adjust._SUPP_X_CACHE = None
    if not with_supp:
        adjust.SUPPLEMENTAL_EXRIGHTS = real.with_name("__none__.csv")
    try:
        return adjust._finmind_adjusted_frame(sid, start)
    finally:
        adjust.SUPPLEMENTAL_EXRIGHTS = real
        adjust._SUPP_X_CACHE = None


def cached(sid, start):
    return all(_cache_path(ds, sid, start, VAL_END).exists() or _cache_path(ds, sid, start, "2014-12-31").exists()
               for ds in ("TaiwanStockPrice", "TaiwanStockDividend"))


sup = pd.read_csv(adjust.SUPPLEMENTAL_EXRIGHTS, dtype={"stock_id": str})
off = sup[sup["source"].isin(["twse_twt49u", "tpex_exdailyq"])]


def finmind_div(sid, start):
    d = _load_dev_offline("TaiwanStockDividend", sid, start)
    if d.empty:
        return set(), True
    s = set(d.get("CashExDividendTradingDate", pd.Series(dtype=str)).dropna().astype(str)) | \
        set(d.get("StockExDividendTradingDate", pd.Series(dtype=str)).dropna().astype(str))
    return s, False


cands = {"a 2009 FinMind 漏記": [], "b FinMind 股利整段零筆": []}
for r in off.sort_values("factor").itertuples():  # factor 小＝跌幅大
    if not cached(r.stock_id, CASE_START):
        continue
    fm, empty = finmind_div(r.stock_id, CASE_START)
    key = "b FinMind 股利整段零筆" if empty else ("a 2009 FinMind 漏記" if r.ex_date[:4] == "2009" and r.ex_date not in fm else None)
    if key and len(cands[key]) < 3 and all(c.stock_id != r.stock_id for c in cands[key]):
        cands[key].append(r)
    if all(len(v) >= 3 for v in cands.values()):
        break

for key, rows in cands.items():
    if len(rows) < 3:
        check(f"1{key[0]} 找到 3 個案例", False, f"只找到 {len(rows)}")
    for r in rows:
        try:
            out = {}
            for w in (False, True):
                f = frame(r.stock_id, CASE_START, w).set_index("date")
                i = f.index.get_loc(r.ex_date)
                out[w] = (f["adj_close"].iloc[i] / f["adj_close"].iloc[i - 1] - 1, f["close"].iloc[i])
            want = out[True][1] / r.ref_price - 1
            ok = abs(out[True][0] - want) < 1e-9 and abs(out[False][0] - out[True][0]) > 1e-6
            check(f"1{key} {r.stock_id} {r.ex_date}", ok,
                  f"補充前 {out[False][0]:+.2%} → 補充後 {out[True][0]:+.2%}（＝收盤÷官方參考價 {r.ref_price} −1 {want:+.2%}）")
        except Exception as e:  # noqa: BLE001
            check(f"1{key} {r.stock_id} {r.ex_date}", False, f"{type(e).__name__}: {e}")

with_ev = sorted({s for s in sup["stock_id"] if cached(s, REG_START)})
pool = sorted({p.name.split("__")[1] for p in (Path(adjust.__file__).parent / "data" / "raw").glob(f"TaiwanStockPrice__*__{REG_START}__*.parquet")}
              - set(sup["stock_id"]))
random.seed(20261023)
others = random.sample([s for s in pool if len(s) == 4 and cached(s, REG_START)], 30)
bad_post, bad_other, n_ev, skipped = [], [], 0, 0
for sid in with_ev + others:
    try:
        a, b = frame(sid, REG_START, False), frame(sid, REG_START, True)
    except Exception:  # noqa: BLE001
        skipped += 1
        continue
    if a.empty or b.empty:
        skipped += 1
        continue
    m = a[["date", "adj_close"]].merge(b[["date", "adj_close"]], on="date", suffixes=("_o", "_n"))
    post = m[m["date"] >= "2015-01-01"]
    if not np.array_equal(post["adj_close_o"].to_numpy(), post["adj_close_n"].to_numpy(), equal_nan=True):
        bad_post.append(sid)
    if sid in others and not np.array_equal(m["adj_close_o"].to_numpy(), m["adj_close_n"].to_numpy(), equal_nan=True):
        bad_other.append(sid)
    n_ev += sid in with_ev
check(f"2a 有補充事件的 {n_ev} 檔：2015 以後 adj_close 完全不變", not [s for s in bad_post if s in with_ev], str(bad_post[:10]))
check(f"2b 沒有補充事件的 {len(others)} 檔：全期完全不變", not bad_other, str(bad_other[:10]))
print(f"     略過（快取不全／空表）{skipped} 檔")
print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
