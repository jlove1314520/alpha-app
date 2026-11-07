"""先.一三五-1ms 自測：H2 列 EPS 是全年累計時改成全年−上半年；單期不動；證據不足不動；重跑不重複扣；單檔壞資料不拋錯。"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
import update_stock_financials as usf  # noqa: E402


def q(y, qq, period, eps, ni):
    return {"year": y, "quarter": qq, "period": period, "eps": eps, "net_income_parent": ni}


stocks = {
    # 股數 1 億：H1 淨利 1 億→EPS 1.00；H2 淨利 1.2 億，EPS 存成全年累計 2.20 → 應改 1.20
    "A": {"financials": {"quarters": [q(2025, 2, "H1", 1.00, 1e8), q(2025, 4, "H2", 2.20, 1.2e8)]}},
    # H2 已是單期 1.20 → 不動
    "B": {"financials": {"quarters": [q(2025, 2, "H1", 1.00, 1e8), q(2025, 4, "H2", 1.20, 1.2e8)]}},
    # H1 EPS 太小（0.05），股數不可靠 → 不動
    "C": {"financials": {"quarters": [q(2025, 2, "H1", 0.05, 5e6), q(2025, 4, "H2", 0.20, 1e7)]}},
    # 沒有 H1 → 不動
    "D": {"financials": {"quarters": [q(2024, 4, "H2", 2.20, 1.2e8), q(2025, 1, None, 0.5, 5e7)]}},
    # 壞資料（eps 是字串）→ 不拋錯、不動
    "E": {"financials": {"quarters": [q(2025, 2, "H1", "x", 1e8), q(2025, 4, "H2", 2.2, 1.2e8)]}},
    "F": None,
}
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


st = usf.fix_h2_cumulative_eps(stocks)
a2 = stocks["A"]["financials"]["quarters"][1]
check("A 全年累計改成全年−上半年", a2["eps"] == 1.20 and a2["eps_annual_cum"] == 2.20 and a2["eps_basis"] == "annual_minus_h1")
check("B 單期不動", stocks["B"]["financials"]["quarters"][1]["eps"] == 1.20 and "eps_basis" not in stocks["B"]["financials"]["quarters"][1])
check("C 證據不足不動", stocks["C"]["financials"]["quarters"][1]["eps"] == 0.20)
check("D 沒有 H1 不動", stocks["D"]["financials"]["quarters"][0]["eps"] == 2.20)
check("E 壞資料不動", stocks["E"]["financials"]["quarters"][1]["eps"] == 2.2)
check("統計 1 列、1 檔", st["fixed_rows"] == 1 and st["fixed_codes"] == ["A"])
st2 = usf.fix_h2_cumulative_eps(stocks)
check("重跑不重複扣", st2["fixed_rows"] == 0 and a2["eps"] == 1.20)
print("全部通過" if not fails else f"{fails} 項失敗")
sys.exit(1 if fails else 0)
