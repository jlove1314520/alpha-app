"""`.github/scripts/update_stock_financials.py` 季度還原與 ROE 合成自測（2026-10-30 先.一三五-1cc）。

零外部請求、不讀真實資料檔；只測純函式：discretize_quarter、discretize_from_cum、merge_quarters、
compute_roe_ttm（含 1cc 修正：四季不連續回 None）、_roc_year_quarter、_num。
另核對 research/build_stock_financials_history.py 的同名 compute_roe_ttm 行為一致。

跑法：python scripts/selftest_stock_financials.py
"""
import importlib.util
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 十二節：守門員自身失敗只降級成警告
    print(f"[警告] reconfigure 失敗：{e}")

ROOT = Path(__file__).resolve().parent.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load(".github/scripts/update_stock_financials.py", "usf_selftest")
fails = []
total = 0


def check(name, cond):
    global total
    total += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def cum(y, q, rev, gross, op, net, eps):
    return {"year": y, "quarter": q, "revenue_cum": rev, "gross_cum": gross, "op_cum": op,
            "net_income_parent_cum": net, "eps_cum": eps}


# _num／_roc_year_quarter
check("_num 千分位", m._num("1,234.5") == 1234.5)
check("_num 壞值 None", m._num("-") is None and m._num("abc") is None)
check("民國年季", m._roc_year_quarter({"年度": "115", "季別": "2"}) == (2026, 2))
check("民國年季缺欄 None", m._roc_year_quarter({"年度": "115"}) is None)

# discretize_quarter
q1 = m.discretize_quarter([], cum(2026, 1, 100.0, 40.0, 20.0, 10.0, 1.0))
check("Q1 累計即單季", q1["revenue"] == 100.0 and q1["gross_margin_pct"] == 40.0 and q1["eps"] == 1.0)
q2 = m.discretize_quarter([q1], cum(2026, 2, 250.0, 100.0, 50.0, 25.0, 2.5))
check("Q2 減 Q1", q2["revenue"] == 150.0 and q2["gross_margin_pct"] == 40.0 and q2["net_income_parent"] == 15.0 and q2["eps"] == 1.5)
check("缺較早季度回 None", m.discretize_quarter([q1], cum(2026, 3, 400.0, 160.0, 80.0, 40.0, 4.0)) is None)
q1_no_net = dict(q1, net_income_parent=None, eps=None)
q2b = m.discretize_quarter([q1_no_net], cum(2026, 2, 250.0, 100.0, 50.0, 25.0, 2.5))
check("較早季淨利 None → 單季淨利/EPS 留空不當累計", q2b["net_income_parent"] is None and q2b["eps"] is None and q2b["revenue"] == 150.0)

# discretize_from_cum
d = m.discretize_from_cum(cum(2026, 1, 100.0, 40.0, 20.0, 10.0, 1.0), cum(2026, 2, 250.0, 100.0, 50.0, 25.0, 2.5))
check("用上一季累計還原", d["revenue"] == 150.0 and d["net_income_parent"] == 15.0 and d["eps"] == 1.5)
check("上一季不是 q-1 回 None", m.discretize_from_cum(cum(2026, 1, 1, 1, 1, 1, 1), cum(2026, 3, 2, 2, 2, 2, 2)) is None)
check("跨年回 None", m.discretize_from_cum(cum(2025, 4, 1, 1, 1, 1, 1), cum(2026, 1, 2, 2, 2, 2, 2)) is None)

# merge_quarters
rows = [{"year": 2024 + i // 4, "quarter": i % 4 + 1, "revenue": i} for i in range(8)]
merged = m.merge_quarters(rows, {"year": 2026, "quarter": 1, "revenue": 99})
check("merge 保留 8 季且新到最後", len(merged) == m.QUARTERS_TO_KEEP and merged[-1]["revenue"] == 99 and merged[0]["year"] == 2024 and merged[0]["quarter"] == 2)
merged2 = m.merge_quarters(merged, {"year": 2026, "quarter": 1, "revenue": 100})
check("同季覆蓋不重複", len(merged2) == 8 and [r["revenue"] for r in merged2].count(100) == 1 and 99 not in [r["revenue"] for r in merged2])


# compute_roe_ttm
def qs(pairs):
    return [{"year": y, "quarter": q, "net_income_parent": n} for y, q, n in pairs]


ok4 = qs([(2025, 3, 10), (2025, 4, 10), (2026, 1, 10), (2026, 2, 10)])
check("連續四季 ROE", m.compute_roe_ttm(ok4, 400) == 10.0)
check("不足四季 None", m.compute_roe_ttm(ok4[1:], 400) is None)
check("權益缺 None", m.compute_roe_ttm(ok4, None) is None)
gap = qs([(2025, 2, 10), (2025, 3, None), (2025, 4, 10), (2026, 1, 10), (2026, 2, 10)])
check("中間缺一季不跨缺口湊四季（1cc）", m.compute_roe_ttm(gap, 400) is None)
gap_far = qs([(2023, 4, 5), (2024, 4, 5), (2026, 1, 10), (2026, 2, 10)])
check("跨年缺口（7822 型）None（1cc）", m.compute_roe_ttm(gap_far, 400) is None)
check("最舊一季缺不影響後四季連續", m.compute_roe_ttm(qs([(2025, 2, None)]) + ok4, 400) == 10.0)

# research 副本行為一致
try:
    h = load("research/build_stock_financials_history.py", "bsfh_selftest")
    same = all(h.compute_roe_ttm(x, 400) == m.compute_roe_ttm(x, 400) for x in (ok4, gap, gap_far, ok4[1:]))
    check("research 副本 compute_roe_ttm 一致", same)
except Exception as e:
    check(f"research 副本載入（{e}）", False)

print(f"\n{'全過' if not fails else '失敗 ' + str(len(fails)) + ' 項'}（共 {total} 項）")
sys.exit(1 if fails else 0)
