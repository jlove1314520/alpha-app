# -*- coding: utf-8 -*-
"""先.十五-一(2)：合併覆蓋率＋PIT 樣本驗證 20 筆（companyfacts 的 accn → submissions 的 acceptanceDateTime）。只驗資料可得性，不計報酬。"""
import sys, json, time, os, random
import requests
for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
D = os.path.join(os.path.dirname(__file__), "data", "us_supply_feas")
UA = {"User-Agent": "AlphaApp-USSupplyFeasibility contact@alpha-app-project.example"}
fr = json.load(open(os.path.join(D, "frames_coverage.json"), encoding="utf-8"))
C = fr["ciks"]
def S(*keys, y):
    out = set()
    for k in keys: out |= set(C.get(f"{k}|{y}", []))
    return out
rows = {}
for y in range(2010, 2026):
    A = S("總資產", y=y)
    ar = {
        "總資產": len(A),
        "預收(新∪舊)": len(S("合約負債_新", "遞延收入_舊", y=y)),
        "存貨": len(S("存貨", y=y)),
        "銷貨成本(A∪B)": len(S("銷貨成本_A", "銷貨成本_B", y=y)),
        "毛利": len(S("毛利", y=y)),
        "資本支出": len(S("資本支出", y=y)),
        "營收(A∪B∪C)": len(S("營收_A", "營收_B", "營收_C", y=y)),
        # I2 需 存貨＋銷貨成本；I3 需 毛利(或 營收−銷貨成本)；I4 需 資本支出＋營收
        "I2可算(存貨∩銷貨成本)": len(S("存貨", y=y) & S("銷貨成本_A", "銷貨成本_B", y=y)),
        "I3可算(毛利∪(營收∩銷貨成本))": len(S("毛利", y=y) | (S("營收_A", "營收_B", "營收_C", y=y) & S("銷貨成本_A", "銷貨成本_B", y=y))),
        "I4可算(資本支出∩營收)": len(S("資本支出", y=y) & S("營收_A", "營收_B", "營收_C", y=y)),
    }
    rows[y] = ar
json.dump(rows, open(os.path.join(D, "merged_coverage.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for y in (2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024):
    print(y, rows[y])

# PIT 樣本：2018 年有存貨的申報人，固定種子抽 20 家
random.seed(20261005)
pool = sorted(S("存貨", y=2018) & S("總資產", y=2018))
smp = random.sample(pool, 20)
def get(u):
    r = requests.get(u, headers=UA, timeout=60); time.sleep(0.2); r.raise_for_status(); return r.json()
out = []
for cik in smp:
    c10 = f"{cik:010d}"
    rec = {"cik": cik}
    try:
        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c10}.json")
        pts = cf["facts"]["us-gaap"]["InventoryNet"]["units"]["USD"]
        pts = [p for p in pts if p.get("form") in ("10-K", "10-Q") and p["end"] >= "2017-01-01"]
        first = {}
        for p in pts:
            if p["end"] not in first or p["filed"] < first[p["end"]]["filed"]: first[p["end"]] = p
        end = sorted(first)[len(first) // 2]; p = first[end]
        rec.update(name=cf.get("entityName"), end=end, filed=p["filed"], accn=p["accn"], form=p["form"])
        sub = get(f"https://data.sec.gov/submissions/CIK{c10}.json")
        rc = sub["filings"]["recent"]
        if p["accn"] in rc["accessionNumber"]:
            i = rc["accessionNumber"].index(p["accn"])
            rec.update(acceptance=rc["acceptanceDateTime"][i], filingDate=rc["filingDate"][i], src="recent")
        else:
            # 較舊申報在 filings.files[] 分頁檔
            rec["src"] = "未在recent"
            for f in sub["filings"].get("files", []):
                s2 = get("https://data.sec.gov/submissions/" + f["name"])
                if p["accn"] in s2["accessionNumber"]:
                    i = s2["accessionNumber"].index(p["accn"])
                    rec.update(acceptance=s2["acceptanceDateTime"][i], filingDate=s2["filingDate"][i], src="分頁檔"); break
        rec["ok"] = "acceptance" in rec
        rec["filed_eq_filingDate"] = rec.get("filingDate") == rec["filed"]
    except Exception as e:
        rec.update(ok=False, err=f"{type(e).__name__}:{e}"[:120])
    out.append(rec); print(rec, flush=True)
json.dump(out, open(os.path.join(D, "pit_sample20.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("PIT 成功", sum(1 for r in out if r.get("ok")), "/ 20；filed==filingDate", sum(1 for r in out if r.get("filed_eq_filingDate")))
