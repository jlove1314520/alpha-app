# -*- coding: utf-8 -*-
"""先.一〇三-10a 自我測試（離線，不發任何請求）：update_price_history.py 的除權息官方計算結果補帳。

用法：python scripts/selftest_exright_official.py [--live]
  --live：另外實打 TWT49U／exDailyQ 各 1 次（最近 10 個交易日），只印解析結果、不寫任何檔。
"""
import importlib.util
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("uph", ROOT / ".github" / "scripts" / "update_price_history.py")
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"：{detail}" if detail else ""))


# 1. 回看起點：10 個交易日，跳過週末與休市日（10/09、10/10 休市）
closed = {"2026-10-09", "2026-10-10"}
start = U.exright_lookback_start("2026-10-16", 10, closed)
check("回看 10 個交易日跳過週末與休市", start == "2026-10-02", start)

# 2. 解析：欄位名對應、民國年、千分位
rows = U._parse_exright_rows(
    ["資料日期", "股票代號", "股票名稱", "除權息前收盤價", "除權息參考價"],
    [["115年09月21日", "00697B ", "元大美債7-10", "1,000.00", "991.10"], ["115年09月21日", "X", "", "--", "1"]],
    "資料日期", "股票代號", "TWSE TWT49U")
check("解析民國年與千分位、略過無效列", len(rows) == 1 and rows[0]["ex_date"] == "2026-09-21"
      and rows[0]["code"] == "00697B" and abs(rows[0]["factor"] - 0.9911) < 1e-9, rows)
try:
    U._parse_exright_rows(["日期"], [], "資料日期", "股票代號", "T")
    check("欄位改版要報錯", False)
except RuntimeError:
    check("欄位改版要報錯", True)

# 3. 合併：已套用不動、未套用掛官方係數、新事件依 covered_through 分流
ledger = {"events": {
    "1203": [{"ex_date": "2026-10-16", "cash": 1.0, "stock_ratio": 0, "rights_ratio": 0, "rights_price": 0,
              "applied": True, "factor_applied": 0.98}],
    "2330": [{"ex_date": "2026-10-16", "cash": 5.0, "stock_ratio": 0, "rights_ratio": 0, "rights_price": 0,
              "applied": False}],
}}
official = [
    {"code": "1203", "ex_date": "2026-10-16", "factor": 0.97, "pre_close": 100, "ref_price": 97, "src": "TWSE TWT49U"},
    {"code": "2330", "ex_date": "2026-10-16", "factor": 0.99, "pre_close": 1000, "ref_price": 990, "src": "TWSE TWT49U"},
    {"code": "6590", "ex_date": "2026-10-08", "factor": 0.9, "pre_close": 10, "ref_price": 9, "src": "TPEx exDailyQ"},
    {"code": "3114", "ex_date": "2026-10-16", "factor": 0.8, "pre_close": 10, "ref_price": 8, "src": "TPEx exDailyQ"},
]
st = U.merge_official_exright(ledger, official, "2026-10-16", "2026-10-15")
check("合併計數", st == {"added": 1, "added_already_folded": 1, "official_factor_attached": 1, "already_applied": 1}, st)
check("已套用、日期晚於重算涵蓋日的事件係數不被改", ledger["events"]["1203"][0]["factor_applied"] == 0.98)
lg2 = {"events": {"6834": [{"ex_date": "2026-10-02", "applied": True, "factor_applied": 0.898}]}}
st2 = U.merge_official_exright(lg2, [{"code": "6834", "ex_date": "2026-10-02", "factor": 0.9664, "pre_close": 119.5,
                                      "ref_price": 115.48, "src": "TWSE TWT49U"}], "2026-10-16", "2026-10-15")
e2 = lg2["events"]["6834"][0]
check("重算涵蓋日以前已套用事件：帳本係數對齊官方、原值留存",
      e2["factor_applied"] == 0.9664 and e2["factor_applied_before_official"] == 0.898 and st2.get("ledger_factor_aligned") == 1, e2)
check("重算涵蓋日以前的新事件只記帳", ledger["events"]["6590"][0]["applied"] is True)

# 4. 套用：官方係數優先、不需要本地定錨；已記帳的不再乘
prices = {
    "2330": [{"date": "2026-10-14", "close": 1000, "adj_close": 1000}, {"date": "2026-10-15", "close": 1000, "adj_close": 1000}],
    "3114": [{"date": "2026-09-01", "close": 10, "adj_close": 10}],  # 前一筆離除息日 >10 天：舊邏輯會 skip，官方係數不受影響
    "6590": [{"date": "2026-10-07", "close": 10, "adj_close": 10}],
}
n = U.apply_dividend_adjustments(prices, ledger, "2026-10-16")
check("套用 2 筆（2330 官方係數、3114 官方係數），6590 不重乘", n == 2, n)
check("2330 用官方 0.99，不是本地前收算的 0.995",
      abs(prices["2330"][0]["adj_close"] - 990) < 1e-6)
check("3114 前一筆距離 >10 天仍用官方係數", abs(prices["3114"][0]["adj_close"] - 8) < 1e-9 and
      ledger["events"]["3114"][0].get("skip_reason") is None)
check("6590 已由重算涵蓋、adj 不變", prices["6590"][0]["adj_close"] == 10)
n2 = U.apply_dividend_adjustments(prices, ledger, "2026-10-16")
check("第二次跑不重複套用", n2 == 0 and abs(prices["2330"][0]["adj_close"] - 990) < 1e-6)

if "--live" in sys.argv:
    import datetime as _dt
    today = _dt.datetime.now(U.TW_TZ).strftime("%Y-%m-%d")
    s = U.exright_lookback_start(today)
    errs = []
    off = U.fetch_official_exright_results(s, today, errs)
    by_src = {}
    for o in off:
        by_src[o["src"]] = by_src.get(o["src"], 0) + 1
    print(f"[live] 區間 {s}～{today}：{len(off)} 筆 {by_src}；錯誤 {errs or '無'}；前 3 筆 {off[:3]}")
    check("[live] 兩個端點都沒有錯誤", not errs, errs)

print(f"=== {sum(results)}/{len(results)} PASS ===")
sys.exit(0 if all(results) else 1)
