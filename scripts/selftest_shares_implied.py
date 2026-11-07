"""先.一三五-1my 自測：shares_outstanding_approx（股本÷10）比最近兩季淨利÷EPS 推得股數少 >30%（面額小於 10 元）時改用推得股數；
推得股數較少只記錄不改；兩季推得股數不一致（金控 Q2）不改；回到 30% 內還原；重跑冪等；壞資料不拋錯。零外部請求。"""
import copy
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
import update_stock_financials as usf  # noqa: E402


def q(y, qq, eps, ni):
    return {"year": y, "quarter": qq, "eps": eps, "net_income_parent": ni}


def fin(shares, quarters):
    return {"financials": {"shares_outstanding_approx": shares, "quarters": quarters}}


stocks = {
    # 8937 實值：股本÷10＝107,920 仟股；2026Q1 −0.07／−29,371 千、Q2 −0.14／−59,394 千 → 推得約 42 萬仟股
    "8937": fin(107920.0, [q(2025, 4, 0.92, 92239000.0), q(2026, 1, -0.07, -29371000.0), q(2026, 2, -0.14, -59394000.0)]),
    # 面額 10 元、推得一致 → 不動
    "NORMAL": fin(100000.0, [q(2026, 1, 1.0, 1.0e8), q(2026, 2, 1.1, 1.1e8)]),
    # 推得比股本少 >30%（6669 型）→ 只記錄不改
    "LOWER": fin(584337.0, [q(2026, 1, 10.0, 1.86e9), q(2026, 2, 10.0, 1.86e9)]),
    # 金控 Q2 特別股股利：兩季推得股數不一致 → 不改
    "FIN": fin(100000.0, [q(2026, 1, 0.5, 2.0e8), q(2026, 2, 0.2, 2.0e8)]),
    # |EPS| 太小推不出 → 不改
    "TINY": fin(10000.0, [q(2026, 1, 0.01, 1e8), q(2026, 2, 0.02, 2e8)]),
    "BAD": fin("x", [q(2026, 1, "x", None)]),
    "NONE": None,
}
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


st = usf.fix_shares_by_implied_eps(stocks)
f8 = stocks["8937"]["financials"]
check(f"8937 改用推得股數（{f8['shares_outstanding_approx']} 仟股，約 4.2 億股）", 415000 <= f8["shares_outstanding_approx"] <= 425000)
check("8937 標 shares_basis=implied_from_eps、原值存 shares_from_capital_div10",
      f8["shares_basis"] == "implied_from_eps" and f8["shares_from_capital_div10"] == 107920.0)
check("面額 10 元正常股不動", stocks["NORMAL"]["financials"]["shares_outstanding_approx"] == 100000.0 and "shares_basis" not in stocks["NORMAL"]["financials"])
check("推得較少只記錄不改", stocks["LOWER"]["financials"]["shares_outstanding_approx"] == 584337.0 and any(x.startswith("LOWER") for x in st["unverifiable_large_gap"]))
check("金控兩季不一致不改", stocks["FIN"]["financials"]["shares_outstanding_approx"] == 100000.0)
check("|EPS| 太小不改", stocks["TINY"]["financials"]["shares_outstanding_approx"] == 10000.0)
check("壞資料不拋錯", st["errors"] == [])
snap = copy.deepcopy(stocks)
st2 = usf.fix_shares_by_implied_eps(stocks)
check("重跑冪等：資料不變、本次無變動、implied_present 仍 1", stocks == snap and st2["changed"] == {} and st2["implied_present"] == 1)
# 之後公司 EPS 回到股本÷10 水準（例如資料修正）→ 還原
stocks["8937"]["financials"]["quarters"] += [q(2026, 3, 0.5, 5.4e7), q(2026, 4, 0.5, 5.4e7)]
st3 = usf.fix_shares_by_implied_eps(stocks)
check("回到 30% 內還原成股本÷10、拿掉標記", f8["shares_outstanding_approx"] == 107920.0 and "shares_basis" not in f8 and "8937" in st3["reverted"])
m = usf._shares_meta(st, "offline")
check("meta 欄位齊", m["mode"] == "offline" and "8937" in m["changed_this_run"] and m["lower_than_capital_not_changed"])
print(f"\n{'全部通過' if not fails else f'{fails} 項失敗'}")
sys.exit(1 if fails else 0)
