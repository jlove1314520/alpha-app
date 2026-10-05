# -*- coding: utf-8 -*-
"""先.十八-二：研究用美股 SIC／ticker 全量抓取（只建資料，不計任何報酬）。

總司令 2026-10-05【先.十八】二：「執行 fetch_us_sic.py 覆蓋全名冊……產出排除金融
（6000–6799）／SPAC（6770）／20-F 後的普通股母體檔數逐年表」。

**[自行裁量] 為什麼不直接改 `.github/scripts/fetch_us_sic.py`**：那支是維運帽擁有的
App 端腳本（CLAUDE.md 九「帽子規則」檔案歸屬），寫的是**會進 repo 的** `data/us_sic.json`，
且掛在 `market.yml` 每日最多跑 3 次、清單只有 9 檔。把它擴成 21,315 檔會變成
「每天對 SEC 發 6 萬次請求、repo 裡多一個 21,315 筆的 committed 檔案」，
那不是本裁示要的東西（本裁示要的是一張研究用的逐年母體表）。
故改為研究帽自己的腳本，輸出到 `research/data/`（整體 gitignore）；
**`.github/scripts/fetch_us_sic.py` 與 `data/us_sic.json` 刻意維持 9 檔不動**，
日後若有人想「順手修好」它，請先讀這一段。

一次請求取齊 sic／sicDescription／tickers／exchanges／formerNames／name——
先.十九-一 需要每個已下市 CIK 的 ticker，若只取 sic 會再多跑一輪 21,315 次請求。

SEC 禮儀：全域限速器沿用 us_universe_rebuild（5 req/秒，官方上限的一半），落地快取可續跑。

用法：python research/us_sic_universe_fetch.py [--fetch] [--table]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import us_universe_rebuild as U  # noqa: E402  （沿用其限速器與快取慣例）

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
SUB = HERE / "data" / "raw" / "sec_submissions"
SUB.mkdir(parents=True, exist_ok=True)
UNI = HERE / "data" / "us_universe_pit.json"
OUT = HERE / "data" / "us_sic_universe.json"
REPORT = HERE / "data" / "us_universe_filtered_report.json"

# SIC 區間：金融 6000–6799（含 SPAC 慣用的 6770 Blank Checks）。
FIN_LO, FIN_HI = 6000, 6799
SPAC_SIC = 6770


def _one(cik: int) -> tuple[int, dict]:
    p = SUB / f"CIK{cik:010d}.json"
    if p.exists():
        try:
            return cik, json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    U._acquire_slot()
    import requests
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                         headers=U.HEADERS, timeout=60)
    except Exception as e:  # noqa: BLE001
        return cik, {"_err": f"{type(e).__name__}"}
    if r.status_code != 200:
        d = {"_http": r.status_code}
        p.write_text(json.dumps(d), encoding="utf-8")
        return cik, d
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return cik, {"_err": "non-json"}
    rec = {"sic": j.get("sic"), "sicDescription": j.get("sicDescription"),
           "name": j.get("name"), "tickers": j.get("tickers") or [],
           "exchanges": j.get("exchanges") or [],
           "formerNames": [x.get("name") for x in (j.get("formerNames") or [])][:5],
           "entityType": j.get("entityType")}
    # 20-F／40-F 申報人（ADR／外國私人發行人）：看近期申報表單別
    forms = set((j.get("filings", {}) or {}).get("recent", {}).get("form") or [])
    rec["files_20f_or_40f"] = bool({f for f in forms if str(f).startswith(("20-F", "40-F"))})
    rec["files_10k_or_10q"] = bool({f for f in forms if str(f).startswith(("10-K", "10-Q"))})
    p.write_text(json.dumps(rec), encoding="utf-8")
    return cik, rec


def fetch_all(ciks: list[int], workers: int = 6) -> dict:
    out = {}
    import time
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (cik, rec) in enumerate(ex.map(_one, ciks), 1):
            out[str(cik)] = rec
            if n % 2000 == 0:
                el = time.time() - t0
                print(f"  {n}/{len(ciks)}（{n / max(el, 1e-9) * 60:.0f} 筆/分，{el / 60:.1f} 分）", flush=True)
    return out


def build_table(sicmap: dict) -> dict:
    uni = json.loads(UNI.read_text(encoding="utf-8"))["universe"]
    years = [str(y) for y in range(2010, 2025)]
    rows = {}
    excl_reasons = {"financial_6000_6799": 0, "spac_6770": 0, "foreign_20f_40f": 0,
                    "no_sic": 0, "no_periodic_report": 0}
    keep = set()
    for cik, v in uni.items():
        s = sicmap.get(cik) or {}
        sic = s.get("sic")
        try:
            sic_i = int(sic) if sic not in (None, "", "0000") else None
        except Exception:  # noqa: BLE001
            sic_i = None
        if not v.get("first_periodic_report"):
            excl_reasons["no_periodic_report"] += 1
            continue
        if sic_i is None:
            excl_reasons["no_sic"] += 1
            continue
        if sic_i == SPAC_SIC:
            excl_reasons["spac_6770"] += 1
            continue
        if FIN_LO <= sic_i <= FIN_HI:
            excl_reasons["financial_6000_6799"] += 1
            continue
        if s.get("files_20f_or_40f") and not s.get("files_10k_or_10q"):
            excl_reasons["foreign_20f_40f"] += 1
            continue
        keep.add(cik)
    for y in years:
        n_live = n_del = n_stop = 0
        for cik in keep:
            v = uni[cik]
            f = (v.get("first_periodic_report") or "9999")[:4]
            if f > y:
                continue                       # 該年還沒開始申報（避免把後來才 IPO 的算進早年）
            end = None
            if v["status"] == "delisted":
                end = (v.get("delisted_at") or "")[:4]
            elif v["status"] == "stopped_filing":
                end = (v.get("stopped_filing_since") or "")[:4]
            if end and end < y:
                continue                       # 該年之前就已退出
            n_live += 1
            if end == y:
                if v["status"] == "delisted":
                    n_del += 1
                else:
                    n_stop += 1
        rows[y] = {"universe_in_year": n_live, "delisted_in_year": n_del,
                   "stopped_filing_in_year": n_stop}
    return {"filtered_universe_total": len(keep), "excluded": excl_reasons, "by_year": rows}


def main() -> int:
    args = sys.argv[1:] or ["--fetch", "--table"]
    uni = json.loads(UNI.read_text(encoding="utf-8"))["universe"]
    ciks = sorted(int(k) for k in uni)
    sicmap = {}
    if OUT.exists():
        try:
            sicmap = json.loads(OUT.read_text(encoding="utf-8")).get("sic", {})
        except Exception:  # noqa: BLE001
            sicmap = {}
    if "--fetch" in args:
        print(f"=== 抓 SIC／ticker：{len(ciks)} 個 CIK ===", flush=True)
        sicmap = fetch_all(ciks)
        OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                                   "source": "SEC submissions 端點（sic/tickers/formerNames/exchanges）",
                                   "n": len(sicmap), "sic": sicmap}, ensure_ascii=False), encoding="utf-8")
        got = sum(1 for v in sicmap.values() if v.get("sic"))
        tk = sum(1 for v in sicmap.values() if v.get("tickers"))
        print(f"取得 SIC {got}/{len(sicmap)}；有 ticker {tk}", flush=True)
    if "--table" in args and sicmap:
        rep = build_table(sicmap)
        rep["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        rep["note"] = ("排除金融 SIC 6000–6799（含 SPAC 6770）與僅申報 20-F／40-F 的外國發行人；"
                       "逐年母體以 first_periodic_report 為起點、delisted_at／stopped_filing_since 為終點，"
                       "避免把後來才 IPO 的公司算進早年。**SIC 取自 submissions 端點，是最近一次申報時的分類，"
                       "非時點資料**（存活者為今日分類、已下市者為當年分類，年份混雜），見 FEASIBILITY 揭露。")
        rep["app_file_untouched"] = (".github/scripts/fetch_us_sic.py 與 data/us_sic.json 刻意維持 9 檔不動，"
                                     "理由見 research/us_sic_universe_fetch.py 檔頭 [自行裁量]")
        REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: rep[k] for k in ("filtered_universe_total", "excluded")}, ensure_ascii=False), flush=True)
        print(f"已寫入 {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
