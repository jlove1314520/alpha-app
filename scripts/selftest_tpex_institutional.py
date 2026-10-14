# -*- coding: utf-8 -*-
"""研究室.二（2026-10-15）：上櫃三大法人解析自測（離線，0 次網路請求）。
官方 tpex_3insti_daily_trading 欄位名夾空白（"ForeignInvestorsInclude MainlandAreaInvestors-Difference"），
舊程式照無空白名稱取值 → 上櫃外資全部 None。這裡用假回應確認：外資、投信、自營都取得到，且不會誤取
「(Foreign Dealers excluded)」那組欄位。用法：python scripts/selftest_tpex_institutional.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fetch_market_tw as F  # noqa: E402

ROW = {"Date": "1151014", "SecuritiesCompanyCode": "9999", "CompanyName": "測試",
       "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)-Difference": "-63013",
       "ForeignDealers-Difference": "1000",
       "ForeignInvestorsInclude MainlandAreaInvestors-Difference": "-62013",
       "SecuritiesInvestmentTrustCompanies-Difference": "2000",
       "Dealers-Difference": "-43261", "TotalDifference": "-103274"}


class _R:
    def raise_for_status(self):
        pass

    def json(self):
        return [ROW]


F._get_retry = lambda *a, **k: _R()
out = F.fetch_institutional_tpex("20261014")["9999"]
res = [("外資取得到（欄位名夾空白）", out["foreign_lots"] == -62.0),
       ("外資用含外資自營的總額，不是 excluded 那組", out["foreign_lots"] != -63.0),
       ("投信", out["trust_lots"] == 2.0), ("自營", out["dealer_lots"] == -43.3),
       ("日期民國轉西元", out["date"] == "20261014")]
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
