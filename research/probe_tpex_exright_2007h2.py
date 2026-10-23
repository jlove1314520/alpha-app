"""補.資料-上櫃 2007-07～12 除權息官方來源三來源查證（DevQueue 20261023-160102）。

只查來源與推導可行性，不套用、不算報酬。

① TPEx 其他官方頁：舊站 exDailyQ_result.php（區間查詢）1 次、新站 exDailyQ 以外不猜路徑。
② TPEx openapi swagger：1 次，掃描所有路徑描述找「除權／除息」與可帶日期的參數。
③ 由已有欄位推導（零請求）：`research/data/raw/v1_resume_day/tpex/` 官方日檔原始回應，
   除權息當日「漲跌」欄是文字（除權／除息／除權息），拿來對 exDailyQ 官方事件驗證。

節流：共用 data/rate_limit_state.json（tpex_openapi／tpex_www，同源間隔 ≥3 秒、跨行程鎖，
402/403/428/429 封鎖 2 小時不重試）。原始回應存 research/data/raw/tpex_exright_probe/，已存就不重抓。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

RAW = HERE / "data" / "raw" / "tpex_exright_probe"
RESUME = HERE / "data" / "raw" / "v1_resume_day" / "tpex"
EXR = HERE / "data" / "raw" / "exright_2007_2014"
OUT = HERE / "data" / "tpex_exright_2007h2_probe.json"
UA = {"User-Agent": "alpha-research/1.0 (personal research; ex-right history)"}
BLOCK = {402, 403, 428, 429}

PROBES = [
    ("swagger", "tpex_openapi", "https://www.tpex.org.tw/openapi/swagger.json", None),
    ("old_exdailyq", "tpex_www",
     "https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php",
     {"l": "zh-tw", "d": "96/07/01", "ed": "96/12/31"}),
]


def _num(s):
    try:
        return float(str(s).replace(",", "").replace(" ", "").replace("+", ""))
    except ValueError:
        return None


def fetch_probe(name, src, url, params) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.bin"
    meta_path = RAW / f"{name}.meta.json"
    if path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    _rate_limit_wait_or_raise(src)
    r = requests.get(url, params=params, headers=UA, timeout=30, allow_redirects=True)
    if r.status_code in BLOCK:
        _rate_limit_record_block(src, r.status_code, "probe_tpex_exright_2007h2")
    path.write_bytes(r.content)
    meta = {"url": r.url, "status": r.status_code, "content_type": r.headers.get("content-type"),
            "bytes": len(r.content), "history": [h.status_code for h in r.history],
            "fetched_at": datetime.now().isoformat(timespec="seconds")}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def scan_swagger() -> dict:
    p = RAW / "swagger.bin"
    try:
        sw = json.loads(p.read_bytes().decode("utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ swagger 解析失敗：{e}")
        return {"error": str(e)}
    hits = []
    for path, ops in sw.get("paths", {}).items():
        for op in ops.values():
            if not isinstance(op, dict):
                continue
            text = " ".join(str(op.get(k, "")) for k in ("summary", "description", "tags"))
            if any(k in text for k in ("除權", "除息", "權息", "股利")) or "exright" in path.lower() \
                    or "dividend" in path.lower():
                hits.append({"path": path, "summary": op.get("summary"),
                             "params": [q.get("name") for q in op.get("parameters", []) or []]})
    return {"n_paths": len(sw.get("paths", {})), "hits": hits}


def derive_check() -> dict:
    ev = {}
    for f in glob.glob(str(EXR / "tpex_*.json")):
        for t in json.load(open(f, encoding="utf-8")).get("tables", []):
            for r in t["data"]:
                y, m, d = r[0].split("/")
                ev[(f"{int(y) + 1911}{m}{d}", r[1])] = (_num(r[3]), _num(r[4]), r[8])
    days = sorted(os.path.basename(x)[:8] for x in glob.glob(str(RESUME / "*.json")))
    raw = {}
    for day in days:
        t = json.load(open(RESUME / f"{day}.json", encoding="utf-8"))["tables"][0]
        raw[day] = {r[0]: r for r in t["data"]}
    marks = {}
    kinds = Counter()
    for day in days:
        for c, r in raw[day].items():
            s = r[3].strip()
            if _num(s) is None and s not in ("", "--", "---"):
                marks[(day, c)] = s
                kinds[s] += 1
    overlap = {k: v for k, v in ev.items() if k[0] in raw and k[1] in raw[k[0]]}
    hit = [k for k in overlap if k in marks]
    same_kind = [k for k in hit if marks[k] == overlap[k][2]]
    extra = sorted(k for k in marks if k not in ev)
    # 參考價近似：除權息前一日原始檔的「次日漲停／跌停」中點
    idx = {d: i for i, d in enumerate(days)}
    n = ok = 0
    for (day, c), (pc, ref, _) in ev.items():
        i = idx.get(day)
        if not i:
            continue
        r = raw[days[i - 1]].get(c)
        if r is None or _num(r[2]) != pc:
            continue  # 前一個檔案不是真正的前一交易日
        up, dn = _num(r[13]), _num(r[14])
        n += 1
        ok += abs((up + dn) / 2 - ref) / ref < 0.01
    return {
        "raw_days": len(days), "raw_range": [days[0], days[-1]] if days else None,
        "raw_days_2007h2_before_1217": sum(1 for d in days if "20070701" <= d < "20071217"),
        "mark_kinds": dict(kinds),
        "official_events_on_raw_days": len(overlap), "marked": len(hit), "same_kind": len(same_kind),
        "marks_without_official_event": [{"date": d, "code": c, "mark": marks[(d, c)]} for d, c in extra],
        "ref_from_eve_limits_checked": n, "ref_from_eve_limits_within_1pct": ok,
    }


def main() -> int:
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "probes": {}}
    for name, src, url, params in PROBES:
        try:
            out["probes"][name] = fetch_probe(name, src, url, params)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 探測 {name} 失敗：{e}")
            out["probes"][name] = {"error": str(e)}
        print(name, out["probes"][name])
    out["swagger_scan"] = scan_swagger()
    out["derive"] = derive_check()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("swagger_scan", "derive")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
