"""經濟部統計處開放資料 A（製造業存貨率）、C（外銷訂單貨品別）每日快照。

先.十-五.6（總司令 2026-10-02）：只存檔，不構成試驗、不計算任何報酬。
來源檔為覆寫式、無 vintage；本腳本每日抓一次，內容雜湊（SHA256）與上一份相同就不再存，
因此只有資料真的更新時才新增一份快照，累積成真 PIT 紀錄。
官方端點為靜態 CSV，未公布次數上限；每檔間隔 1.5 秒、每日全部抓一次（共 12 檔），不重試。
失敗只記錄、不中斷（規則十二）：永遠 exit 0。
"""
import csv
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "moea_pit"
MANIFEST = OUT / "manifest.jsonl"
STATUS = ROOT / "research" / "data" / "moea_pit_status.json"
BASE = "https://service.moea.gov.tw/EE520/opendata/"
UA = "alpha-app-research/1.0 (daily PIT snapshot of public MOEA open data)"

COMMODITIES = ["電子產品", "光學器材", "電機產品", "基本金屬", "機械", "塑橡膠製品",
               "化學品", "運輸工具", "礦產品", "紡織品"]
SOURCES = [("A", "製造業存貨率", "經濟部統計處_製造業存貨率.csv")]
SOURCES += [("C", "外銷訂單_" + n, ("統計處外銷訂單_運輸工具.csv" if n == "運輸工具" else f"經濟部統計處_外銷訂單_{n}.csv"))
            for n in COMMODITIES]
SOURCES += [("C", "外銷訂單_按地區分", "經濟部統計處_外銷訂單_按地區分.csv")]


def last_sha(name):
    last = None
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("name") == name:
                last = r.get("sha256")
    return last


def summarize(text):
    rows = list(csv.reader(io.StringIO(text)))
    h = rows[0]
    pi = next(i for i, x in enumerate(h) if "資料期" in x)
    periods = sorted({r[pi] for r in rows[1:] if len(r) > pi})
    return len(rows) - 1, (periods[0] if periods else None), (periods[-1] if periods else None)


def fetch_one(grp, name, fname, now):
    r = requests.get(BASE + fname, timeout=90, headers={"User-Agent": UA})
    if r.status_code != 200:
        return {"name": name, "result": f"http_{r.status_code}"}
    body = r.content
    text = body.decode("utf-8-sig", errors="strict")
    head = text[:300].lower()
    if "<html" in head or "資料期" not in text.splitlines()[0]:
        return {"name": name, "result": "not_csv_or_changed_format"}
    sha = hashlib.sha256(body).hexdigest()
    nrows, p0, p1 = summarize(text)
    prev = last_sha(name)
    if prev == sha:
        return {"name": name, "result": "unchanged", "last_period": p1}
    d = OUT / grp / name
    d.mkdir(parents=True, exist_ok=True)
    fn = f"{now:%Y%m%d}_{sha[:8]}.csv"
    (d / fn).write_bytes(body)
    rec = {"name": name, "group": grp, "fetched_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "sha256": sha, "bytes": len(body), "rows": nrows, "first_period": p0, "last_period": p1,
           "last_modified": r.headers.get("Last-Modified"), "file": f"{grp}/{name}/{fn}",
           "baseline": prev is None}
    with MANIFEST.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"name": name, "result": "new_snapshot" if prev else "baseline", "last_period": p1}


def main():
    now = datetime.now(timezone.utc)
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for i, (grp, name, fname) in enumerate(SOURCES):
        if i:
            time.sleep(1.5)
        try:
            results.append(fetch_one(grp, name, fname, now))
        except Exception as e:
            results.append({"name": name, "result": "error:" + type(e).__name__})
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps({"run_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "results": results},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print("[warn] status write failed:", type(e).__name__)
    for r in results:
        print(r["name"], r["result"], r.get("last_period", ""))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("[warn] snapshot_moea_pit failed:", type(e).__name__, e)
        sys.exit(0)
