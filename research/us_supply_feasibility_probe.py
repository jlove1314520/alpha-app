# -*- coding: utf-8 -*-
"""先.十五-一.1／一.2：SEC EDGAR XBRL 欄位覆蓋率與 PIT 可得性實測（只盤點，不計任何報酬）。

依總司令 2026-10-05【先.十五】一：
  1. XBRL Frames／Company Facts 能否取得 2010 起全體美股的合約負債／遞延收入／存貨／
     銷貨成本／毛利／資本支出／營收；逐欄位記錄覆蓋率（有值公司數／全體）與起始年度。
  2. PIT：確認每筆數值可對應到 10-Q／10-K 的 acceptance datetime，列出取得方式與 20 筆樣本驗證。

SEC 流量禮儀（CLAUDE.md「外部 API 頻率上限清單」：官方 10 req/秒）：
  本腳本固定每次請求後 sleep 0.25 秒（約 4 req/秒），且所有回應落地快取到
  research/data/raw/（已整體 gitignore），重跑不會再打 SEC。
  User-Agent 用專案識別用佔位信箱，不送總司令本人 email（CLAUDE.md 既有慣例）。

**不讀任何價格、不算任何報酬、不碰 holdout。** 輸出 research/data/us_supply_feasibility.json。

用法：python research/us_supply_feasibility_probe.py [--frames] [--pit] [--all]
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw" / "sec_frames"
RAW.mkdir(parents=True, exist_ok=True)
OUT = HERE / "data" / "us_supply_feasibility.json"
UNIVERSE = HERE / "data" / "us_universe_pit.json"
HEADERS = {"User-Agent": "AlphaResearch-USTrack contact@alpha-research-project.example",
           "Accept-Encoding": "gzip, deflate"}
SLEEP = 0.25  # 約 4 req/秒，低於 SEC 官方 10 req/秒

# 台版 I1~I4 對應的美股 us-gaap 科目。每個指標列多個候選 tag——美國沒有統一表單格式，
# 同一個經濟量不同公司用不同 tag（例如營收有 Revenues 與 ASC606 後的
# RevenueFromContractWithCustomerExcludingAssessedTax 兩套），覆蓋率必須算「任一候選有值」
# 才是真實可用率，只看單一 tag 會嚴重低估。
# unit: "I"=時點（資產負債表，frames 用 CY2024Q4I），"D"=期間（損益/現金流量，用 CY2024Q4）
CONCEPTS = {
    "I1_合約負債(新)": [("ContractWithCustomerLiabilityCurrent", "I")],
    "I1_遞延收入(舊)": [("DeferredRevenueCurrent", "I")],
    "I2_存貨": [("InventoryNet", "I")],
    "I2I3_銷貨成本": [("CostOfGoodsAndServicesSold", "D"), ("CostOfGoodsSold", "D"), ("CostOfRevenue", "D")],
    "I3_毛利": [("GrossProfit", "D")],
    "I4_資本支出": [("PaymentsToAcquirePropertyPlantAndEquipment", "D")],
    "營收": [("RevenueFromContractWithCustomerExcludingAssessedTax", "D"), ("Revenues", "D")],
    "總資產(分母)": [("Assets", "I")],
}
# 起始年度探測用（每年 Q4）＋覆蓋率趨勢用
YEARS = [2009, 2010, 2011, 2012, 2014, 2016, 2018, 2020, 2022, 2024]


def fetch(url: str, cache_name: str) -> dict | None:
    p = RAW / cache_name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    time.sleep(SLEEP)
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"  [網路失敗] {cache_name}: {type(e).__name__}", flush=True)
        return None
    if r.status_code == 404:
        p.write_text(json.dumps({"_http": 404}), encoding="utf-8")
        return {"_http": 404}
    if r.status_code != 200:
        print(f"  [HTTP {r.status_code}] {cache_name}", flush=True)
        return None
    try:
        d = r.json()
    except Exception:  # noqa: BLE001
        print(f"  [非JSON] {cache_name}", flush=True)
        return None
    # 只留下我們要的欄位再落地，避免幾百 MB 的快取
    slim = {"_http": 200, "ciks": sorted({int(x["cik"]) for x in d.get("data", []) if "cik" in x}),
            "n_raw": len(d.get("data", []))}
    p.write_text(json.dumps(slim), encoding="utf-8")
    return slim


def frames_probe(uni_ciks: set[int]) -> dict:
    out = {}
    for label, tags in CONCEPTS.items():
        per_year = {}
        for y in YEARS:
            union: set[int] = set()
            per_tag = {}
            for tag, kind in tags:
                period = f"CY{y}Q4I" if kind == "I" else f"CY{y}Q4"
                url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
                d = fetch(url, f"{tag}_{period}.json")
                if not d or d.get("_http") != 200:
                    per_tag[tag] = None
                    continue
                ciks = set(d["ciks"])
                per_tag[tag] = {"n_all_filers": len(ciks), "n_in_universe": len(ciks & uni_ciks)}
                union |= ciks
            per_year[y] = {"per_tag": per_tag, "n_all_filers_union": len(union),
                           "n_in_universe_union": len(union & uni_ciks),
                           "cov_in_universe_pct": round(100.0 * len(union & uni_ciks) / max(1, len(uni_ciks)), 1)}
            print(f"  {label} CY{y}Q4: 全體申報人 {len(union)}、落在宇宙內 {len(union & uni_ciks)}"
                  f"（{per_year[y]['cov_in_universe_pct']}%）", flush=True)
        out[label] = per_year
    return out


# ── PIT：20 筆樣本驗證 acceptanceDateTime ──
PIT_SAMPLE = ["AAPL", "MSFT", "NVDA", "INTC", "CSCO", "WMT", "HD", "CAT", "DE", "F",
              "GM", "BA", "MMM", "KO", "PEP", "NKE", "TGT", "LOW", "UPS", "FDX"]


def pit_probe(uni: dict) -> dict:
    rows = []
    for t in PIT_SAMPLE:
        rec = uni.get(t)
        if not rec:
            rows.append({"ticker": t, "error": "不在 us_universe_pit.json"})
            continue
        cik = int(rec["cik"])
        d = fetch_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", f"SUB_{cik}.json")
        if not d:
            rows.append({"ticker": t, "cik": cik, "error": "submissions 取得失敗"})
            continue
        rec_f = d.get("filings", {}).get("recent", {})
        forms = rec_f.get("form", [])
        idx = next((i for i, f in enumerate(forms) if f in ("10-K", "10-Q")), None)
        if idx is None:
            rows.append({"ticker": t, "cik": cik, "error": "recent 視窗內無 10-K/10-Q"})
            continue
        acc = rec_f.get("acceptanceDateTime", [None] * len(forms))[idx]
        fdate = rec_f.get("filingDate", [None] * len(forms))[idx]
        rdate = rec_f.get("reportDate", [None] * len(forms))[idx]
        accn = rec_f.get("accessionNumber", [None] * len(forms))[idx]
        after_close = None
        if acc:
            try:
                # SEC 的 acceptanceDateTime 是美東時間（ET）；16:00 後接受的件，當天收盤已過
                hhmm = acc[11:16]
                after_close = hhmm >= "16:00"
            except Exception:  # noqa: BLE001
                after_close = None
        rows.append({"ticker": t, "cik": cik, "form": forms[idx], "accn": accn,
                     "reportDate": rdate, "filingDate": fdate, "acceptanceDateTime": acc,
                     "accepted_after_1600_ET": after_close})
        print(f"  {t}: {forms[idx]} report={rdate} filed={fdate} accepted={acc} 盤後={after_close}", flush=True)
    ok = [r for r in rows if r.get("acceptanceDateTime")]
    n_after = sum(1 for r in ok if r.get("accepted_after_1600_ET"))
    return {"n_sample": len(rows), "n_with_acceptance_datetime": len(ok),
            "n_accepted_after_1600_ET": n_after, "rows": rows}


def fetch_json(url: str, cache_name: str) -> dict | None:
    """submissions 端點用的原樣快取（不瘦身，因為要讀多個欄位）。"""
    p = RAW / cache_name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    time.sleep(SLEEP)
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            print(f"  [HTTP {r.status_code}] {cache_name}", flush=True)
            return None
        d = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"  [網路失敗] {cache_name}: {type(e).__name__}", flush=True)
        return None
    rec = d.get("filings", {}).get("recent", {})
    keep = {k: rec.get(k) for k in ("form", "accessionNumber", "filingDate", "reportDate", "acceptanceDateTime")}
    slim = {"cik": d.get("cik"), "name": d.get("name"), "sic": d.get("sic"),
            "sicDescription": d.get("sicDescription"), "filings": {"recent": keep}}
    p.write_text(json.dumps(slim), encoding="utf-8")
    return slim


def main() -> int:
    uni_doc = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    uni = uni_doc["universe"]
    uni_ciks = {int(v["cik"]) for v in uni.values() if v.get("cik")}
    print(f"宇宙 {len(uni)} 檔，相異 CIK {len(uni_ciks)}（active {uni_doc['counts']['active']}／"
          f"delisted {uni_doc['counts']['delisted']}）", flush=True)
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "source": "SEC EDGAR XBRL frames + submissions（官方公開端點，約4 req/秒，含識別用 User-Agent）",
           "universe_file": "research/data/us_universe_pit.json",
           "universe_n": len(uni), "universe_distinct_cik": len(uni_ciks),
           "note": "只盤點資料可得性，未讀任何價格、未計算任何報酬、未碰 holdout"}
    args = sys.argv[1:]
    do_all = ("--all" in args) or not args
    if do_all or "--frames" in args:
        print("\n=== XBRL Frames 欄位覆蓋率（每年 Q4）===", flush=True)
        res["frames"] = frames_probe(uni_ciks)
    if do_all or "--pit" in args:
        print("\n=== PIT：acceptanceDateTime 20 筆樣本 ===", flush=True)
        res["pit"] = pit_probe(uni)
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}
    prev.update(res)
    OUT.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已寫入 {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
