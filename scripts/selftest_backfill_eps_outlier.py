"""先.一三五-1mu 自測：回補季單季 EPS 偏高（推得股數低於前後兩季 >30%）才改成淨利÷相鄰季平均股數；
持續性股數基準改變、EPS 偏低（特別股股利）、|EPS| 太小、官方列、半年報列一律不動；重跑冪等；壞資料不拋錯。"""
import copy
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
import update_stock_financials as usf  # noqa: E402

BF = usf.SRC_Q_FROM_BACKFILL


def q(y, qq, eps, ni, src=BF, period=None):
    r = {"year": y, "quarter": qq, "eps": eps, "net_income_parent": ni, "source": src}
    if period:
        r["period"] = period
    return r


stocks = {
    # 6667 實值：2025Q3 3.2／154,638 千、2025Q4 7.01／186,968 千、2026Q1 3.63／179,017 千 → Q4 應改約 3.83
    "A": {"financials": {"quarters": [q(2025, 3, 3.2, 154638000.0), q(2025, 4, 7.01, 186968000.0), q(2026, 1, 3.63, 179017000.0)]}},
    # 8937 型：股數 1 億 → 4.2 億持續跳變（前後季股數本身不一致）→ 不動
    "B": {"financials": {"quarters": [q(2025, 3, 0.23, 22725000.0), q(2025, 4, 0.92, 92239000.0), q(2026, 1, 0.5, 210000000.0), q(2026, 2, 0.5, 210000000.0)]}},
    # 金控型：中間季 EPS 偏低（特別股股利）→ 不動
    "C": {"financials": {"quarters": [q(2025, 1, 1.0, 1e9), q(2025, 2, 0.7, 1e9), q(2025, 3, 1.0, 1e9)]}},
    # |EPS| 太小 → 不動
    "D": {"financials": {"quarters": [q(2025, 1, 1.0, 1e8), q(2025, 2, 0.1, 2e7), q(2025, 3, 1.0, 1e8)]}},
    # 官方列偏高 → 不動
    "E": {"financials": {"quarters": [q(2025, 1, 1.0, 1e8), q(2025, 2, 3.0, 1e8, src="mopsfin"), q(2025, 3, 1.0, 1e8)]}},
    # 缺鄰季（不連續）→ 不動
    "F": {"financials": {"quarters": [q(2025, 1, 1.0, 1e8), q(2025, 3, 3.0, 1e8), q(2026, 1, 1.0, 1e8)]}},
    # 壞資料 → 不拋錯
    "G": {"financials": {"quarters": [q(2025, 1, "x", 1e8), q(2025, 2, 3.0, 1e8), q(2025, 3, None, 1e8)]}},
    "H": None,
}
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


orig = copy.deepcopy(stocks)
st = usf.fix_isolated_backfill_eps_outliers(stocks)
a4 = stocks["A"]["financials"]["quarters"][1]
check("A 6667 型 Q4 EPS 改成約 3.83", a4["eps"] == 3.83 and a4["eps_raw"] == 7.01 and a4["eps_basis"] == "net_div_neighbor_shares")
for k in "BCDEFG":
    check(f"{k} 不動", stocks[k] == orig[k])
check("統計只修 1 列", st["fixed_rows"] == 1 and list(st["fixed"]) == ["A"])
st2 = usf.fix_isolated_backfill_eps_outliers(stocks)
check("重跑冪等（0 列）", st2["fixed_rows"] == 0 and a4["eps"] == 3.83 and a4["eps_raw"] == 7.01)
print(f"合計失敗 {fails}")
sys.exit(1 if fails else 0)
