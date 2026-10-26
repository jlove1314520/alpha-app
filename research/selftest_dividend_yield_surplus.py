# -*- coding: utf-8 -*-
"""先.一三五-3④（2026-10-27，收件匣 024）：f_dividend_yield_ttm 分子補資本公積配息的自測＋2015 後影響清單。
離線（擋網路、只讀本機快取）、只讀 load_dev（截在 VAL_END，不碰 holdout）、不跑回測、不計 N。

1. 合成資料：只配公積的年度要算進分子；盈餘＋公積同列要相加；沒有 CashStatutorySurplus 欄位時與舊算法逐值相同。
2. 2331 實際資料：2012-08-15（盈餘 0.35＋公積 2.12）分子＝2.47。
3. 影響清單：adjust_surplus_fix_impact.json 列出的有公積配發股票，逐檔比對新舊分子（舊＝把公積欄位拿掉重算），
   2015-01-01 以後有變動的 pit_date 寫進 research/data/factor_dividend_yield_surplus_impact.json。

跑法：cd research && python selftest_dividend_yield_surplus.py
"""
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (先.一三五-3 selftest)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import pandas as pd  # noqa: E402

import factors  # noqa: E402
from finmind_client import load_dev  # noqa: E402

HERE = Path(__file__).parent
fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def ttm(df):
    return factors._dividend_yield_ttm_cash_from_df(df)


# 1. 合成資料
syn = pd.DataFrame({
    "CashExDividendTradingDate": ["2016-07-01", "2017-07-01", "2018-07-01"],
    "CashEarningsDistribution": [1.0, 0.0, 0.5],
    "CashStatutorySurplus": [0.0, 1.2, 0.3],
    "year": ["104年", "105年", "106年"],
})
r = ttm(syn).set_index("pit_date")["ttm_cash_dividend"]
check("1a 只配公積的年度算進分子", abs(r.get("2017-07-01", -1) - 1.2) < 1e-9, f"2017={r.get('2017-07-01')}")
check("1b 盈餘＋公積同列相加", abs(r.get("2018-07-01", -1) - 0.8) < 1e-9, f"2018={r.get('2018-07-01')}")
no_col = syn.drop(columns=["CashStatutorySurplus"])
old_like = syn.assign(CashStatutorySurplus=0.0)
check("1c 無公積欄位＝公積填 0", ttm(no_col).equals(ttm(old_like)))

# 2. 2331 實際資料
d2331 = load_dev("TaiwanStockDividend", "2331", "2010-01-01")
r = ttm(d2331).set_index("pit_date")["ttm_cash_dividend"]
v = r.get("2012-08-15")
check("2 2331 2012-08-15 分子＝0.35＋2.12", v is not None and abs(v - 2.47) < 1e-6, f"值={v}")

# 3. 影響清單
imp = json.loads((HERE / "data" / "adjust_surplus_fix_impact.json").read_text(encoding="utf-8"))
codes = sorted({s["stock_id"] for s in imp["stocks"]})
rows, n_checked, n_err = [], 0, 0
for code in codes:
    try:
        div = load_dev("TaiwanStockDividend", code, "2010-01-01")
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {code} 讀不到股利快取：{e}")
        n_err += 1
        continue
    if div is None or div.empty or "CashStatutorySurplus" not in div.columns:
        continue
    n_checked += 1
    new = ttm(div).set_index("pit_date")["ttm_cash_dividend"]
    old = ttm(div.drop(columns=["CashStatutorySurplus"])).set_index("pit_date")["ttm_cash_dividend"]
    for pit in sorted(set(new.index) | set(old.index)):
        if str(pit) < "2015-01-01":
            continue
        a = old.get(pit)
        b = new.get(pit)
        a = None if a is None or pd.isna(a) else float(a)
        b = None if b is None or pd.isna(b) else float(b)
        if a is None or b is None or abs(a - b) > 1e-9:
            rows.append({"stock_id": code, "pit_date": str(pit), "ttm_old": a, "ttm_new": b,
                         "rel_change": (None if not a else round(b / a - 1, 6)) if b is not None else None})
out = {
    "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    "source": "research/selftest_dividend_yield_surplus.py（先.一三五-3④）",
    "scope": "load_dev（截在 VAL_END），2015-01-01 以後 pit_date；股票母體＝adjust_surplus_fix_impact.json 有公積配發者",
    "n_stocks_checked": n_checked, "n_read_errors": n_err,
    "n_stocks_changed": len({x["stock_id"] for x in rows}),
    "n_pit_dates_changed": len(rows),
    "n_new_nonzero_where_old_missing": sum(1 for x in rows if x["ttm_old"] is None),
    "median_rel_change": (float(pd.Series([x["rel_change"] for x in rows if x["rel_change"] is not None]).median())
                          if rows else None),
    "rows": rows,
}
(HERE / "data" / "factor_dividend_yield_surplus_impact.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"3 影響清單：檢查 {n_checked} 檔、變動 {out['n_stocks_changed']} 檔／{len(rows)} 個 pit_date"
      f"（舊算法沒有值 {out['n_new_nonzero_where_old_missing']}），相對變動中位 {out['median_rel_change']}")
check("3 影響清單有產出且讀檔錯誤為 0", n_err == 0 and n_checked > 0)

print("\n結果：" + ("全部通過" if not fails else f"失敗 {fails}"))
sys.exit(1 if fails else 0)
