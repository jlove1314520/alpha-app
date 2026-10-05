# -*- coding: utf-8 -*-
"""先.十五-一：美股供給緊縮可行性盤點（只數覆蓋率，不計任何報酬）。
SEC XBRL Frames API：每個 (概念, 期間) 一次請求回傳全體申報人。
流量禮儀：每次請求後 sleep 0.2 秒（約 5 req/s，官方上限 10 req/s）；UA 用專案識別字串。
輸出：research/data/us_supply_feas/frames_coverage.json
"""
import sys, json, time, os
import requests
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

UA = {"User-Agent": "AlphaApp-USSupplyFeasibility contact@alpha-app-project.example"}
OUT = os.path.join(os.path.dirname(__file__), "data", "us_supply_feas", "frames_coverage.json")
# (欄位, 概念, 單位, 類型)
TAGS = [
    ("合約負債_新", "ContractWithCustomerLiabilityCurrent", "USD", "I"),
    ("遞延收入_舊", "DeferredRevenueCurrent", "USD", "I"),
    ("存貨", "InventoryNet", "USD", "I"),
    ("銷貨成本_A", "CostOfRevenue", "USD", "D"),
    ("銷貨成本_B", "CostOfGoodsAndServicesSold", "USD", "D"),
    ("毛利", "GrossProfit", "USD", "D"),
    ("資本支出", "PaymentsToAcquirePropertyPlantAndEquipment", "USD", "D"),
    ("營收_A", "Revenues", "USD", "D"),
    ("營收_B", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD", "D"),
    ("營收_C", "SalesRevenueNet", "USD", "D"),
    ("總資產", "Assets", "USD", "I"),
]
YEARS = range(2009, 2026)

def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=60)
    except Exception as e:
        return None, f"例外:{type(e).__name__}"
    time.sleep(0.2)
    if r.status_code != 200:
        return None, f"HTTP{r.status_code}"
    try:
        return r.json(), None
    except Exception:
        return None, "非JSON"

res = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n_requests": 0, "coverage": {}, "ciks": {}}
for label, tag, unit, kind in TAGS:
    res["coverage"][label] = {}
    for y in YEARS:
        per = f"CY{y}Q4I" if kind == "I" else f"CY{y}"
        d, err = get(f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/{unit}/{per}.json")
        res["n_requests"] += 1
        if d is None:
            res["coverage"][label][y] = {"n": None, "err": err}
            continue
        ciks = sorted({x["cik"] for x in d.get("data", [])})
        res["coverage"][label][y] = {"n": len(ciks)}
        res["ciks"].setdefault(f"{label}|{y}", ciks)
    print(label, {y: v.get("n", v.get("err")) for y, v in res["coverage"][label].items()}, flush=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("done requests=", res["n_requests"])
