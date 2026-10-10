# -*- coding: utf-8 -*-
"""美股財報每週排程：SEC XBRL companyfacts → data/us_financials.json（常備.開發-16）。

取代 2026-09-02 的 6 檔 yfinance 固定快照（research/factors_us_financials.py，
保留作參考，不再寫這個檔）。

資料源：SEC EDGAR 官方公開端點，免金鑰（頻率上限見 C:\\alpha\\CLAUDE.md
「SEC EDGAR」一節：官方 10 req/秒，本腳本每次請求後 sleep 0.2 秒≈5 req/秒）。
1. https://www.sec.gov/files/company_tickers_exchange.json —— 當下申報人名冊
   （ticker／CIK／交易所），也是 research/us_universe_pit.py 的 ticker 來源。
2. https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json —— 經
   research/sec_edgar_client.py 的 get_company_facts()。

宇宙（「us_universe 內有報價的標的」的操作定義，[自行裁量]）：
- 名冊中交易所為 NYSE／Nasdaq 者（OTC／無交易所者排除——沒有交易所報價）。
- 依 SEC 名冊原始排列順序取前 MAX_TICKERS 個不重複 CIK。這個順序觀察上近似
  市值由大到小（NVDA/AAPL/GOOGL/MSFT 在最前面），**但 SEC 官方未文件化此排序
  意義**，如實標註，不宣稱是市值排名。
- 另強制納入 App 自選美股清單（MUST_INCLUDE，跟 fetch_quotes_us.py 同一份），
  即使它們不在前段（例如 20-F 申報的 ADR）。
- 這是「當下」名冊，不是時點宇宙：本檔只給 App 個股頁顯示最新財報，
  **不得拿來做回測**（回測請用 research/us_universe_pit.py 的時點宇宙）。

指標（皆取最近一個「年度」值：fp=FY、form 為 10-K/20-F/40-F（含 /A）、
期間長度 350~380 天；同一期末多次申報取 filed 最新者）：
- revenue / revenue_yoy：營收與年增（同一 tag 的前一年度期末相比）
- eps_diluted：稀釋 EPS（缺則用基本 EPS，標在 warnings）
- gross_margin / operating_margin：毛利率／營益率（分子與營收同期末才算）
- free_cash_flow / fcf_margin：營業現金流 − 資本支出
- debt_ratio：負債比＝總負債／總資產，取最近一份 10-K/10-Q/20-F/40-F 的期末值
  （缺 Liabilities 時用 LiabilitiesAndStockholdersEquity − 股東權益推導，標 warnings）
- 每檔帶 filed（最新年度數字的申報日）與 currency（20-F 公司可能是 TWD 等外幣）

失敗分類寫進 errors（不靜默記 None）；整體失敗（名冊抓不到、成功 < 50 檔）
不覆蓋既有檔案、exit 1。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 主控台不支援 reconfigure 時只降級，不中斷（CLAUDE.md 十二）
    print(f"[warn] reconfigure stdout 失敗：{e}")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "research"))
from sec_edgar_client import get_company_facts  # noqa: E402

OUT_PATH = REPO_ROOT / "data" / "us_financials.json"
HEADERS = {"User-Agent": "AlphaApp-USFinancials contact@alpha-app-project.example"}
EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
LISTED_EXCHANGES = {"NYSE", "Nasdaq"}
MAX_TICKERS = 260
MUST_INCLUDE = ["NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN", "UMC", "ASX", "CHT"]
SLEEP_SEC = 0.2
MIN_OK_TO_WRITE = 50
STALE_DAYS = 800  # 最新年度營收期末早於今天 800 天（約 2 個會計年度＋20-F 申報落後）→ 視為過期不顯示，記進 errors
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT"}
BALANCE_FORMS = ANNUAL_FORMS | {"10-Q", "10-Q/A"}

# 依優先序；同一指標多個 tag 時，取「最新年度期末最晚」的那個 tag（公司常換 tag）。
TAGS = {
    "revenue": [("us-gaap", "Revenues"),
                ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
                ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
                ("us-gaap", "SalesRevenueNet"),
                ("us-gaap", "SalesRevenueGoodsNet"),
                ("us-gaap", "RevenuesNetOfInterestExpense"),
                ("ifrs-full", "Revenue"),
                ("ifrs-full", "RevenueFromContractsWithCustomers")],
    "gross_profit": [("us-gaap", "GrossProfit"), ("ifrs-full", "GrossProfit")],
    "cost_of_revenue": [("us-gaap", "CostOfRevenue"),
                        ("us-gaap", "CostOfGoodsAndServicesSold"),
                        ("ifrs-full", "CostOfSales")],
    "operating_income": [("us-gaap", "OperatingIncomeLoss"),
                         ("ifrs-full", "ProfitLossFromOperatingActivities")],
    "eps_diluted": [("us-gaap", "EarningsPerShareDiluted"),
                    ("ifrs-full", "DilutedEarningsLossPerShare")],
    "eps_basic": [("us-gaap", "EarningsPerShareBasic"),
                  ("ifrs-full", "BasicEarningsLossPerShare")],
    "ocf": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
            ("ifrs-full", "CashFlowsFromUsedInOperatingActivities")],
    "capex": [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
              ("us-gaap", "PaymentsToAcquireProductiveAssets"),
              ("ifrs-full", "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
              ("ifrs-full", "PurchaseOfPropertyPlantAndEquipment")],
    "liabilities": [("us-gaap", "Liabilities"), ("ifrs-full", "Liabilities")],
    "assets": [("us-gaap", "Assets"), ("ifrs-full", "Assets")],
    "liab_and_equity": [("us-gaap", "LiabilitiesAndStockholdersEquity"),
                        ("ifrs-full", "EquityAndLiabilities")],
    "equity": [("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
               ("us-gaap", "StockholdersEquity"),
               ("ifrs-full", "Equity")],
}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _units(units: dict, per_share: bool, currency: str | None) -> list[tuple[str, list]]:
    """候選單位。指定 currency 時只回該幣別（每股值為 {cur}/shares），確保比率分子分母同幣別。"""
    out = []
    for u, rows in (units or {}).items():
        if per_share:
            if not u.endswith("/shares"):
                continue
            if currency and u != f"{currency}/shares":
                continue
        else:
            if not (u.isalpha() and len(u) == 3 and u.isupper()):
                continue
            if currency and u != currency:
                continue
        out.append((u, rows))
    return out


def _annual_series(facts: dict, key: str, per_share: bool = False,
                   currency: str | None = None) -> tuple[dict, str | None, str | None]:
    """回傳 ({period_end: (val, filed)}, tag, unit)，只取年度值；
    挑最新年度期末最晚的 tag／單位（同期末時 USD 優先，再依 TAGS 順序）。"""
    best: tuple[dict, str | None, str | None] = ({}, None, None)
    best_key = None
    for tax, tag in TAGS[key]:
        node = facts.get(tax, {}).get(tag)
        if not node:
            continue
        for unit, rows in _units(node.get("units", {}), per_share, currency):
            series: dict[str, tuple[float, str]] = {}
            for r in rows:
                if r.get("form") not in ANNUAL_FORMS or not r.get("start") or not r.get("end"):
                    continue
                span = (_d(r["end"]) - _d(r["start"])).days
                if not 350 <= span <= 380:
                    continue
                prev = series.get(r["end"])
                if prev is None or r.get("filed", "") > prev[1]:
                    series[r["end"]] = (float(r["val"]), r.get("filed", ""))
            if not series:
                continue
            k = (max(series), unit.startswith("USD"))
            if best_key is None or k > best_key:
                best, best_key = (series, f"{tax}:{tag}", unit), k
    return best


def _instant_latest(facts: dict, key: str, currency: str | None = None) -> tuple[str, float, str, str] | None:
    """最近一份定期報告的期末時點值：(end, val, filed, tag)。"""
    best = None
    for tax, tag in TAGS[key]:
        node = facts.get(tax, {}).get(tag)
        if not node:
            continue
        for r in [r for _, rows in _units(node.get("units", {}), False, currency) for r in rows]:
            if r.get("form") not in BALANCE_FORMS or r.get("start") or not r.get("end"):
                continue
            cand = (r["end"], float(r["val"]), r.get("filed", ""), f"{tax}:{tag}")
            if best is None or (cand[0], cand[2]) > (best[0], best[2]):
                best = cand
    return best


def _prior_end(series: dict, end: str) -> str | None:
    target = _d(end) - timedelta(days=365)
    cands = [e for e in series if e < end and abs((_d(e) - target).days) <= 20]
    return max(cands) if cands else None


def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    return round(a / b, 6)


def compute(facts_payload: dict) -> dict:
    facts = facts_payload.get("facts", {})
    out: dict = {"missing_fields": [], "warnings": []}
    rev, rev_tag, cur = _annual_series(facts, "revenue")
    if not rev:
        out["missing_fields"].append("revenue")
        end = None
        cur = None
    else:
        end = max(rev)
        out["period_end"] = end
        out["filed"] = rev[end][1]
        out["currency"] = cur
        out["revenue"] = rev[end][0]
        out["revenue_tag"] = rev_tag
        pe = _prior_end(rev, end)
        out["prior_period_end"] = pe
        out["revenue_yoy"] = round(rev[end][0] / rev[pe][0] - 1, 6) if pe and rev[pe][0] > 0 else None
        if out["revenue_yoy"] is None:
            out["missing_fields"].append("revenue_yoy")

    def same_period(key: str):
        s, _, _ = _annual_series(facts, key, currency=cur)
        return s.get(end, (None,))[0] if end else None

    gp = same_period("gross_profit")
    if gp is None and end:
        cogs = same_period("cost_of_revenue")
        if cogs is not None:
            gp = out["revenue"] - cogs
    out["gross_margin"] = _ratio(gp, out.get("revenue"))
    out["operating_margin"] = _ratio(same_period("operating_income"), out.get("revenue"))

    eps_s, _, _ = _annual_series(facts, "eps_diluted", per_share=True, currency=cur)
    eps_kind = "diluted"
    if not eps_s:
        eps_s, _, _ = _annual_series(facts, "eps_basic", per_share=True, currency=cur)
        eps_kind = "basic"
    if eps_s:
        eend = end if end in eps_s else max(eps_s)
        out["eps"] = eps_s[eend][0]
        out["eps_kind"] = eps_kind
        out["eps_period_end"] = eend
        if rev_tag and rev_tag.startswith("ifrs-full"):
            out["warnings"].append("IFRS申報（20-F）：EPS為每普通股，非每ADR")
        if eps_kind == "basic":
            out["warnings"].append("無稀釋EPS，改用基本EPS")
        if end and eend != end:
            out["warnings"].append(f"EPS期末{eend}與營收期末{end}不同")
    else:
        out["eps"] = None

    ocf, capex = same_period("ocf"), same_period("capex")
    out["free_cash_flow"] = (ocf - capex) if (ocf is not None and capex is not None) else None
    out["fcf_margin"] = _ratio(out["free_cash_flow"], out.get("revenue"))

    liab, assets = _instant_latest(facts, "liabilities", cur), _instant_latest(facts, "assets", cur)
    debt = None
    if assets:
        if liab and liab[0] == assets[0]:
            debt = _ratio(liab[1], assets[1])
        else:
            le, eq = _instant_latest(facts, "liab_and_equity", cur), _instant_latest(facts, "equity", cur)
            if le and eq and le[0] == eq[0] == assets[0]:
                debt = _ratio(le[1] - eq[1], assets[1])
                out["warnings"].append("無總負債tag，以負債及權益合計−權益推導")
        out["balance_period_end"] = assets[0]
    out["debt_ratio"] = debt

    for k in ("gross_margin", "operating_margin", "eps", "free_cash_flow", "fcf_margin", "debt_ratio"):
        if out.get(k) is None:
            out["missing_fields"].append(k)
    return out


def build_universe() -> list[tuple[str, int, str]]:
    r = requests.get(EXCHANGE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    d = r.json()
    idx = {f: i for i, f in enumerate(d["fields"])}
    rows = [(row[idx["ticker"]], int(row[idx["cik"]]), row[idx["exchange"]]) for row in d["data"]]
    by_ticker = {t: (t, c, x) for t, c, x in rows}
    picked, seen = [], set()
    for t, c, x in rows:
        if len(picked) >= MAX_TICKERS:
            break
        if x in LISTED_EXCHANGES and c not in seen:
            picked.append((t, c, x)); seen.add(c)
    for t in MUST_INCLUDE:
        if t in by_ticker and by_ticker[t][1] not in seen:
            picked.append(by_ticker[t]); seen.add(by_ticker[t][1])
    return picked


def main() -> int:
    try:
        universe = build_universe()
    except Exception as e:
        print(f"錯誤：抓 SEC 名冊 company_tickers_exchange.json 失敗：{e}")
        return 1
    print(f"宇宙 {len(universe)} 檔（NYSE/Nasdaq 前 {MAX_TICKERS} 不重複 CIK＋App 自選）")
    fin, errors = {}, {}
    for i, (t, cik, x) in enumerate(universe, 1):
        try:
            payload = get_company_facts(cik, use_cache=False, headers=HEADERS)
            if not payload:
                errors[t] = "no_companyfacts(404)"
            else:
                rec = compute(payload)
                if rec.get("revenue") is None:
                    errors[t] = "no_annual_revenue_tag"
                elif (date.today() - _d(rec["period_end"])).days > STALE_DAYS:
                    errors[t] = f"stale_annual_revenue(最新年度期末{rec['period_end']}，{rec.get('revenue_tag')})"
                else:
                    rec["cik"] = cik
                    rec["exchange"] = x
                    fin[t] = rec
        except Exception as e:
            errors[t] = f"fetch_or_parse_error: {type(e).__name__}: {str(e)[:120]}"
        time.sleep(SLEEP_SEC)
        if i % 50 == 0:
            print(f"  {i}/{len(universe)}，成功 {len(fin)}")
    if len(fin) < MIN_OK_TO_WRITE:
        print(f"錯誤：成功只有 {len(fin)} 檔（< {MIN_OK_TO_WRITE}），不覆蓋既有檔案")
        return 1
    tpe = timezone(timedelta(hours=8))
    out = {
        "generated_at": datetime.now(tpe).isoformat(timespec="seconds"),
        "update_policy": "每週排程（.github/workflows/us_financials.yml，週六台北 10:17）；也可手動 workflow_dispatch",
        "source": "SEC EDGAR XBRL companyfacts（官方，免金鑰）＋company_tickers_exchange.json 名冊；腳本 .github/scripts/fetch_us_financials_sec.py",
        "universe_rule": f"SEC 當下名冊中 NYSE/Nasdaq 掛牌者，依名冊原始順序（觀察上近似市值由大到小，官方未文件化）取前 {MAX_TICKERS} 個不重複 CIK＋App 自選美股；當下名冊非時點宇宙，不得用於回測",
        "metric_note": "年度值（fp=FY、10-K/20-F/40-F、期間350~380天）；負債比取最近一份定期報告期末；currency 非 USD 者金額為申報幣別",
        "coverage": f"{len(fin)}/{len(universe)} 檔成功",
        "covered_count": len(fin),
        "errors": errors,
        "financials": fin,
    }
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))  # 寫檔前驗
    tmp.replace(OUT_PATH)
    print(f"完成：{out['coverage']}，寫入 {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
