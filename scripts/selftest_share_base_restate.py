"""先.一三五-1mx 自測：股數基準持續跳變＋官方近四季 EPS 證實才追溯調整舊季 EPS（只改 EPS 不改淨利）；
官方對不上／缺官方／已被其他修正改過的列（6667 型）／金控 Q2 單季偏低一律不動；重跑冪等；壞資料不拋錯。零外部請求。"""
import copy
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
import update_stock_financials as usf  # noqa: E402

BF = usf.SRC_Q_FROM_BACKFILL


def q(y, qq, eps, ni, src=BF, **kw):
    r = {"year": y, "quarter": qq, "eps": eps, "net_income_parent": ni, "source": src}
    r.update(kw)
    return r


# 8937 合騏* 實值（data/stock_detail.json 2026-11-08）：2025 各季約 1 億股、2026 起約 4.2 億股；官方 23.5÷391.67＝0.06
Q8937 = [q(2025, 1, -0.08, -7543000.0), q(2025, 2, -1.79, -181397000.0), q(2025, 3, 0.23, 22725000.0),
         q(2025, 4, 0.92, 92239000.0), q(2026, 1, -0.07, -29371000.0), q(2026, 2, -0.14, -59394000.0)]
stocks = {
    "8937": {"financials": {"quarters": copy.deepcopy(Q8937)}},
    # 同型但官方對不上（真的增資、EPS 不追溯）→ 不動
    "NOMATCH": {"financials": {"quarters": copy.deepcopy(Q8937)}},
    # 同型但沒有官方本益比（虧損或缺）→ 不動
    "NOOFF": {"financials": {"quarters": copy.deepcopy(Q8937)}},
    # 6667 型：舊季其中一列已被離群修正改過（eps_basis=net_div_neighbor_shares）→ 該列不動，其餘照調
    "6667T": {"financials": {"quarters": [q(2025, 1, -0.08, -7543000.0), q(2025, 2, -1.79, -181397000.0),
                                          q(2025, 3, 0.23, 22725000.0, eps_raw=0.5, eps_basis="net_div_neighbor_shares"),
                                          q(2025, 4, 0.92, 92239000.0), q(2026, 1, -0.07, -29371000.0), q(2026, 2, -0.14, -59394000.0)]}},
    # 金控型：Q2 特別股股利 EPS 偏低（推得股數偏高）只一季，之後回原水準 → 不偵測
    "FIN": {"financials": {"quarters": [q(2025, 1, 1.0, 1e9), q(2025, 2, 0.6, 1e9), q(2025, 3, 1.0, 1e9), q(2025, 4, 1.0, 1e9),
                                        q(2026, 1, 1.0, 1e9), q(2026, 2, 0.6, 1e9)]}},
    # 股數穩定 → 不偵測
    "FLAT": {"financials": {"quarters": [q(2025, y, 1.0, 1e8) for y in (1, 2, 3, 4)]}},
    # 壞資料 → 不拋錯
    "BAD": {"financials": {"quarters": [q(2025, 1, "x", 1e8), q(2025, 2, None, None), {"year": None}]}},
    "NONE": None,
}
official = {"8937": 0.06, "NOMATCH": 0.94, "6667T": 0.06 - 0.05 + 0.23, "FIN": 3.2, "FLAT": 4.0}
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


def eps_of(code, y, qq):
    return next(r for r in stocks[code]["financials"]["quarters"] if r["year"] == y and r["quarter"] == qq)


sh = usf.detect_share_base_shift(Q8937)
check("8937 偵測到 2026Q1 跳變、倍數約 4.24", sh and sh["break_at"] == "2026Q1" and 4.1 < sh["factor"] < 4.4)
check("8937 舊基準季含 2025Q1～Q4", sh and set(map(tuple, sh["old_rows"])) == {(2025, 1), (2025, 2), (2025, 3), (2025, 4)})
st = usf.restate_share_base_shift(stocks, official)
r3, r4 = eps_of("8937", 2025, 3), eps_of("8937", 2025, 4)
check("8937 2025Q3 0.23→0.05、Q4 0.92→0.22", r3["eps"] == 0.05 and r4["eps"] == 0.22)
check("8937 原值存 eps_pre_restate、eps_basis=restated_share_base",
      r3["eps_pre_restate"] == 0.23 and r3["eps_basis"] == "restated_share_base" and r3.get("restate_factor"))
check("8937 淨利不變", r3["net_income_parent"] == 22725000.0 and r4["net_income_parent"] == 92239000.0)
ttm = round(sum(r["eps"] for r in stocks["8937"]["financials"]["quarters"][-4:]), 2)
check(f"8937 調整後近四季 EPS {ttm}＝官方 0.06", ttm == 0.06)
check("8937 新基準季 2026Q1／Q2 不動", eps_of("8937", 2026, 1)["eps"] == -0.07 and "eps_basis" not in eps_of("8937", 2026, 2))
check("官方對不上 → 不動並記 not_restated", "eps_basis" not in eps_of("NOMATCH", 2025, 4) and st["not_restated"]["NOMATCH"]["status"] == "old_matches")
check("缺官方 → 不動並記 no_official", "eps_basis" not in eps_of("NOOFF", 2025, 4) and st["not_restated"]["NOOFF"]["status"] == "no_official")
r6 = eps_of("6667T", 2025, 3)
check("6667 型已修列不動（eps_basis 仍 net_div_neighbor_shares、eps 0.23）", r6["eps_basis"] == "net_div_neighbor_shares" and r6["eps"] == 0.23)
check("6667 型同檔其他舊季照調、跳過列有記錄", eps_of("6667T", 2025, 4)["eps"] == 0.22 and any(x.startswith("6667T 2025Q3") for x in st["skipped_rows_with_other_basis"]))
check("金控 Q2 偏低不偵測、不動", usf.detect_share_base_shift(stocks["FIN"]["financials"]["quarters"]) is None
      and all("eps_basis" not in r for r in stocks["FIN"]["financials"]["quarters"]))
Q3583 = [q(2024, 4, 3.11, 249869000.0, src="mops"), q(2025, 1, 3.2, 257326000.0, src="mops"), q(2025, 2, 2.85, 228855000.0, src="mops"),
         q(2025, 3, 3.66, 293908000.0, src="mops"), q(2025, 4, 7.77, 329723000.0, src="mops"), q(2026, 1, 4.14, 332960000.0, src="mops"),
         q(2026, 2, 5.02, 406045000.0, src="mops")]
check("單季孤立離群（3583 實值 2025Q4 7.77）不當成基準改變", usf.detect_share_base_shift(Q3583) is None)
check("股數穩定不偵測", "FLAT" not in st["not_restated"] and "FLAT" not in st["restated_codes"])
check("壞資料不拋錯、無 errors", st["errors"] == [])
snap = copy.deepcopy(stocks)
st2 = usf.restate_share_base_shift(stocks, official)
check("重跑冪等：資料不變、本次 0 列", stocks == snap and st2["restated_rows"] == 0)
check("重跑 meta 仍統計到既有追溯列（restated_rows_present）", st2["restated_rows_present"] == st["restated_rows_present"] and st2["restated_rows_present"] >= 7)
check("讀不到官方檔回空 dict 不拋錯", usf.load_official_ttm_eps_map(Path("Z:/nope.json"), Path("Z:/nope2.json")) == {})
m = usf._share_base_meta(st, "offline")
check("meta 有追溯調整統計欄位", m["restated_this_run"] == 2 and m["mode"] == "offline" and "detected" in m)
print(f"\n{'全部通過' if not fails else f'{fails} 項失敗'}")
sys.exit(1 if fails else 0)
