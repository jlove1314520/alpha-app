"""先.一三五-1mz 自測：官方列單季 EPS 孤立偏高，需「偏高幅度＝同年較早季 EPS（舊離散化少減一季）」或
「官方近四季 EPS 用新值對得上、原值對不上」才改；回補列（6667 已修列）、金控 Q2 偏低、再外一季股數亂跳、
無證據、官方對得上原值一律不動；重跑冪等；壞資料不拋錯。"""
import copy
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
import update_stock_financials as usf  # noqa: E402


def q(y, qq, eps, ni, src=None, **kw):
    r = {"year": y, "quarter": qq, "eps": eps, "net_income_parent": ni}
    if src:
        r["source"] = src
    r.update(kw)
    return r


S = 80.4e6  # 3583 型股數
stocks = {
    # 3583 實值型：2025Q4 7.77＝真 Q4 約 4.10＋Q3 3.66（少減一季）；同時在近四季內，官方 16.30
    "A": {"financials": {"quarters": [q(2025, 1, 3.2, 257326000.0), q(2025, 2, 2.85, 228855000.0), q(2025, 3, 3.66, 293908000.0),
                                      q(2025, 4, 7.77, 329723000.0), q(2026, 1, 4.14, 332960000.0), q(2026, 2, 5.02, 406045000.0)]}},
    # 機制證據（不在近四季）：Q2＝真 Q2＋Q1
    "B": {"financials": {"quarters": [q(2025, 1, 2.5, 2.5 * 170e6), q(2025, 2, 5.21, 2.71 * 170e6), q(2025, 3, 2.35, 2.35 * 170e6),
                                      q(2025, 4, 4.38, 4.38 * 170e6), q(2026, 1, 1.0, 1.0 * 170e6), q(2026, 2, 1.0, 1.0 * 170e6),
                                      q(2026, 3, 1.0, 1.0 * 170e6)]}},
    # 無證據（偏高幅度不等於任何較早季，且不在近四季）→ 不動
    "C": {"financials": {"quarters": [q(2024, 2, 1.0, 1e8), q(2024, 3, 1.0, 1e8), q(2024, 4, 1.9, 1e8), q(2025, 1, 1.0, 1e8),
                                      q(2025, 2, 1.0, 1e8), q(2025, 3, 1.0, 1e8), q(2025, 4, 1.0, 1e8), q(2026, 1, 1.0, 1e8)]}},
    # 金控型：Q2 EPS 偏低 → 不動
    "D": {"financials": {"quarters": [q(2025, 1, 1.0, 1e9), q(2025, 2, 0.7, 1e9), q(2025, 3, 1.0, 1e9), q(2025, 4, 1.0, 1e9)]}},
    # 6667 已修回補列（有 eps_basis）＋回補來源 → 不動
    "E": {"financials": {"quarters": [q(2025, 2, 3.42, 3.42 * 48e6, src=usf.SRC_Q_FROM_BACKFILL), q(2025, 3, 3.2, 154638000.0, src=usf.SRC_Q_FROM_BACKFILL),
                                      q(2025, 4, 3.83, 186968000.0, src=usf.SRC_Q_FROM_BACKFILL, eps_raw=7.01, eps_basis="net_div_neighbor_shares"),
                                      q(2026, 1, 3.63, 179017000.0, src=usf.SRC_Q_FROM_BACKFILL)]}},
    # 6514 型：再外一季股數亂跳 → 不動
    "F": {"financials": {"quarters": [q(2023, 2, 1.07, 15363000.0), q(2023, 3, 0.51, 41215000.0), q(2023, 4, 0.8, 24148000.0),
                                      q(2024, 1, 0.55, 42505000.0), q(2024, 2, 1.23, 42833000.0)]}},
    # 在近四季內但官方對得上原值 → 不動（即使機制證據成立）
    "G": {"financials": {"quarters": [q(2025, 1, 1.0, 1e8), q(2025, 2, 1.0, 1e8), q(2025, 3, 1.0, 1e8), q(2025, 4, 2.0, 1e8),
                                      q(2026, 1, 1.0, 1e8), q(2026, 2, 1.0, 1e8)]}},
    # 壞資料 → 不拋錯
    "H": {"financials": {"quarters": [q(2025, 1, "x", 1e8), q(2025, 2, 3.0, 1e8), q(2025, 3, None, 1e8), q(2025, 4, 1.0, 1e8)]}},
    "I": None,
}
official = {"A": 16.3023, "G": 5.0}
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


orig = copy.deepcopy(stocks)
st = usf.fix_isolated_official_eps_outliers(stocks, official)
a = stocks["A"]["financials"]["quarters"][3]
check("A 3583 型 Q4 7.77→4.1（機制＋官方近四季）", a["eps"] == 4.1 and a["eps_raw"] == 7.77
      and a["eps_basis"] == "official_net_div_neighbor_shares" and "official_ttm" in a["eps_fix_evidence"]
      and any(x.startswith("cum_missed_prior:Q3") for x in a["eps_fix_evidence"]))
b = stocks["B"]["financials"]["quarters"][1]
check("B 2072 型 Q2 5.21→2.71（機制證據 Q1）", b["eps"] == 2.71 and b["eps_raw"] == 5.21 and b["eps_fix_evidence"] == ["cum_missed_prior:Q1"])
for k in "CDEFGH":
    check(f"{k} 不動", stocks[k] == orig[k])
check("統計只修 2 列", st["fixed_rows"] == 2 and sorted(st["fixed"]) == ["A", "B"])
check("G 記為官方對得上原值", any(x.startswith("G 2025Q4") and "對得上原值" in x for x in st["left_unverified"]))
check("C 記為無證據", any(x.startswith("C 2024Q4") and "無機制證據" in x for x in st["left_unverified"]))
st2 = usf.fix_isolated_official_eps_outliers(stocks, official)
check("重跑冪等（0 列）", st2["fixed_rows"] == 0 and a["eps"] == 4.1 and b["eps"] == 2.71)
st3 = usf.fix_isolated_official_eps_outliers({"Z": {"financials": {"quarters": "壞"}}}, official)
check("壞結構不拋錯", st3["fixed_rows"] == 0)
print(f"合計失敗 {fails}")
sys.exit(1 if fails else 0)
