"""先.一三五-1md 自測：併入回補季後 ROE 重算（零外部請求）。
用法：python scripts/selftest_roe_after_backfill_merge.py"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("usf", ROOT / ".github" / "scripts" / "update_stock_financials.py")
usf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usf)
BF = usf.SRC_Q_FROM_BACKFILL


def q(y, k, ni, src=BF):
    return {"year": y, "quarter": k, "net_income_parent": ni, "source": src}


fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)

stocks = {
    "A": {"financials": {"equity_parent_latest": 1000, "latest_cum": {"year": 2026, "quarter": 2},
                         "roe_ttm_pct": None,
                         "quarters": [q(2024, 4, 1e9, None), q(2025, 3, 25e3), q(2025, 4, 25e3), q(2026, 1, 25e3), q(2026, 2, 25e3)]}},
    # 不連續（缺 2025Q4）→ None
    "B": {"financials": {"equity_parent_latest": 1000, "latest_cum": {"year": 2026, "quarter": 2}, "roe_ttm_pct": 9.9,
                         "quarters": [q(2025, 2, 1), q(2025, 3, 1), q(2026, 1, 1), q(2026, 2, 1)]}},
    # 最後一季對不上 latest_cum → None
    "C": {"financials": {"equity_parent_latest": 1000, "latest_cum": {"year": 2026, "quarter": 1}, "roe_ttm_pct": 9.9,
                         "quarters": [q(2025, 3, 1), q(2025, 4, 1), q(2026, 1, 1), q(2026, 2, 1)]}},
    # 沒權益 → 不動
    "D": {"financials": {"latest_cum": {"year": 2026, "quarter": 2}, "roe_ttm_pct": 5.0,
                         "quarters": [q(2025, 3, 1), q(2025, 4, 1), q(2026, 1, 1), q(2026, 2, 1)]}},
    # 沒回補季 → 不在名單
    "E": {"financials": {"equity_parent_latest": 1000, "latest_cum": {"year": 2026, "quarter": 2}, "roe_ttm_pct": 7.0,
                         "quarters": [q(2025, 3, 1, None)]}},
    "F": "壞資料",
}
codes = usf._codes_with_backfill_quarters(stocks)
check("名單只含帶回補季的檔", sorted(codes) == ["A", "B", "C", "D"])
st = usf.recompute_roe_after_backfill_merge(stocks, codes + ["F", "不存在"])
check("A 重算＝10%（權益仟元→元）", stocks["A"]["financials"]["roe_ttm_pct"] == 10.0)
check("B 不連續 → None", stocks["B"]["financials"]["roe_ttm_pct"] is None)
check("C 最後一季≠latest_cum → None", stocks["C"]["financials"]["roe_ttm_pct"] is None)
check("D 沒權益不動", stocks["D"]["financials"]["roe_ttm_pct"] == 5.0)
check("E 沒回補季不動", stocks["E"]["financials"]["roe_ttm_pct"] == 7.0)
check("壞資料不中斷", st["errors"] == {} or isinstance(st["errors"], dict))

# 實檔：2883 有值
try:
    real = json.loads((ROOT / "data" / "stock_detail.json").read_text(encoding="utf-8"))["stocks"]
    v = real["2883"]["financials"].get("roe_ttm_pct")
    check(f"實檔 2883 roe_ttm_pct 非 None（{v}）", v is not None)
except Exception as e:
    check(f"讀實檔失敗：{e}", False)

print("全部通過" if not fails else f"失敗 {len(fails)} 項")
sys.exit(1 if fails else 0)
