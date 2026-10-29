# -*- coding: utf-8 -*-
"""自測：模擬 G（paper_7）`revenue_sue()` 與模擬 M（paper_13）`beta_of()` 兩個核心訊號函式（先.一三五-1av）。

背景：先.一三五-1au 自測涵蓋表發現這兩支追蹤程式的「選股訊號本體」沒有被任何 selftest 直接呼叫過；
模擬 G 2026-11-02 起跑，先補。全部用合成資料，不讀真實價格／營收檔、不算任何策略報酬、零網路請求。

paper_7 revenue_sue：
1. 24 個連續月份 → SUE 等於「pandas rolling(12).std()（ddof=1）」照 factors._revenue_surprise_sue 同式重算的值，月份標籤正確。
2. 只有 23 個月 → None（不滿 24 個連續月份）。
3. 最近 12 個 YoY 視窗內缺一個月 → None。
4. 去年同月營收 0 → None。
5. YoY 全部相同（標準差 0）→ None。
6. 官方檔與回補檔同年月 → 官方優先；回補檔只補官方沒有的月份，補上後才算得出來。
paper_13 beta_of：
7. 個股日報酬＝1.5×指數日報酬＋常數 → beta＝1.5。
8. 指數日不足 BETA_DAYS+1 → None；視窗內個股缺一天 → None；`before` 當天不算進視窗（嚴格小於）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd  # noqa: E402

import paper_7_revsurprise_tracker as G  # noqa: E402
import paper_13_ml_low_beta_tracker as M  # noqa: E402
import paper_forward_common as C  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def months(n: int, y0: int = 2023, m0: int = 1):
    out, y, m = [], y0, m0
    for _ in range(n):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def rev_rows(n: int, seed_mult: float = 1.0):
    # 營收：基數 100、每月不同成長（確保 YoY 有離散度）
    rows = []
    for i, (y, m) in enumerate(months(n)):
        rows.append({"year": y, "month": m, "revenue": 100.0 * seed_mult * (1 + 0.01 * i + 0.03 * ((i * 7) % 5))})
    return rows


def pandas_sue(rows):
    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    prior = df.copy()
    prior["year"] += 1
    prior = prior.rename(columns={"revenue": "prior"})
    df = df.merge(prior, on=["year", "month"], how="left")
    df["yoy"] = (df["revenue"] - df["prior"]) / df["prior"].abs()
    df["sd"] = df["yoy"].rolling(12, min_periods=12).std()
    return float(df["yoy"].iloc[-1] / df["sd"].iloc[-1])


def test_revenue_sue():
    check(G.SUE_WINDOW == 12, f"SUE_WINDOW＝12（實際 {G.SUE_WINDOW}）")
    r24 = rev_rows(24)
    got = G.revenue_sue({"month_revenue": r24})
    want = pandas_sue(r24)
    check(got is not None and math.isclose(got[0], want, rel_tol=1e-9), f"24 個月 SUE 與 pandas 同式重算一致（{got and round(got[0], 6)} vs {round(want, 6)}）")
    check(got is not None and got[1] == "2024-12", f"月份標籤＝最後一個月 2024-12（實際 {got and got[1]}）")

    check(G.revenue_sue({"month_revenue": rev_rows(23)}) is None, "只有 23 個月 → None")

    gap = [r for r in rev_rows(30) if not (r["year"] == 2025 and r["month"] == 2)]
    check(G.revenue_sue({"month_revenue": gap}) is None, "最近 12 個 YoY 視窗內缺 2025-02 → None")

    z = rev_rows(24)
    z[0]["revenue"] = 0.0  # 2023-01＝2024-01 的去年同月
    check(G.revenue_sue({"month_revenue": z}) is None, "去年同月營收 0 → None")

    flat = [{"year": y, "month": m, "revenue": 100.0 * (1.1 ** (y - 2023))} for (y, m) in months(24)]
    check(G.revenue_sue({"month_revenue": flat}) is None, "YoY 全部相同（標準差 0）→ None")

    official = rev_rows(24)
    missing = [r for r in official if not (r["year"] == 2024 and r["month"] == 6)]
    check(G.revenue_sue({"month_revenue": missing}) is None, "官方缺 2024-06 → None（前提）")
    filler = [{"year": 2024, "month": 6, "revenue": next(r["revenue"] for r in official if (r["year"], r["month"]) == (2024, 6))}]
    got2 = G.revenue_sue({"month_revenue": missing}, gap_rows=filler)
    check(got2 is not None and math.isclose(got2[0], want, rel_tol=1e-9), "回補檔補上 2024-06 後與完整序列同值")
    bad_gap = [dict(r, revenue=r["revenue"] * 3) for r in official]
    got3 = G.revenue_sue({"month_revenue": official}, gap_rows=bad_gap)
    check(got3 is not None and math.isclose(got3[0], want, rel_tol=1e-9), "官方與回補檔同年月 → 官方優先（回補檔值被覆蓋）")


def test_beta_of():
    n = M.BETA_DAYS + 1
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-01-05", periods=n + 1)]
    before = days[-1]
    mkt, px_rows, m_lvl, s_lvl = {}, [], 10000.0, 50.0
    for i, d in enumerate(days):
        rm = 0.004 * math.sin(i * 1.3) + 0.002 * ((i % 3) - 1)
        if i:
            m_lvl *= 1 + rm
            s_lvl *= 1 + 1.5 * rm + 0.0003
        mkt[d] = m_lvl
        px_rows.append({"date": d, "close": s_lvl})
    px = C.Px({"9999": px_rows})
    b = M.beta_of(px, "9999", mkt, before)
    check(b is not None and math.isclose(b, 1.5, rel_tol=1e-9), f"個股報酬＝1.5×指數＋常數 → beta＝1.5（實際 {b and round(b, 9)}）")

    # before 當天的價格改成極端值，不得影響結果（視窗嚴格小於 before）
    px_rows2 = [dict(r) for r in px_rows]
    px_rows2[-1]["close"] *= 5
    b2 = M.beta_of(C.Px({"9999": px_rows2}), "9999", mkt, before)
    check(b2 is not None and math.isclose(b2, 1.5, rel_tol=1e-9), "before 當天不進視窗（改它的價格不影響 beta）")

    check(M.beta_of(px, "9999", mkt, days[-2]) is None, f"指數日只剩 {M.BETA_DAYS} 天 → None")
    hole = [r for r in px_rows if r["date"] != days[10]]
    check(M.beta_of(C.Px({"9999": hole}), "9999", mkt, before) is None, "視窗內個股缺一天 → None")
    check(M.beta_of(px, "0000", mkt, before) is None, "無此代號 → None")


def main() -> int:
    test_revenue_sue()
    test_beta_of()
    print(f"\n結果：{'全部通過' if not FAILS else f'{len(FAILS)} 項 FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
