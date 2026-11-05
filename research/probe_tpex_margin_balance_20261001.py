# -*- coding: utf-8 -*-
"""先.一三五-1jt-b：上櫃融資融券逐股餘額 2026-10-01 向 TPEx 官方補一次（一次性探測）。

背景：`data/margin_by_stock_history.json` 的 `by_data_date.tpex` 從沒抓到過 20261001（git 歷史也沒有，1jz）。
openapi `tpex_mainboard_margin_balance` 沒有參數（只有最新一天，讀本機 swagger 零請求確認），
所以試網頁版 `www.tpex.org.tw/www/zh-tw/margin/balance?date=YYYY/MM/DD&response=json`。

請求：robots.txt 1 次＋候選端點最多 2 次，共用 data/rate_limit_state.json `tpex_www` 節流
（同源 ≥3 秒、跨行程鎖，402/403/428/429 封鎖 2 小時不重試）。原始回應存
`research/data/raw/tpex_margin_balance_probe/`，已存就不重抓。
本支只探測＋存原始檔；驗證與寫入另由 `--apply` 執行（零請求）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

RAW = HERE / "data" / "raw" / "tpex_margin_balance_probe"
UA = {"User-Agent": "alpha-research/1.0 (personal research; margin balance history)"}
BLOCK = {402, 403, 428, 429}

PROBES = [
    ("robots", "tpex_www", "https://www.tpex.org.tw/robots.txt", None),
    ("balance_20261001", "tpex_www", "https://www.tpex.org.tw/www/zh-tw/margin/balance",
     {"date": "2026/10/01", "response": "json"}),
]


def fetch(name, src, url, params) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.bin"
    meta_path = RAW / f"{name}.meta.json"
    if path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    _rate_limit_wait_or_raise(src)
    r = requests.get(url, params=params, headers=UA, timeout=30, allow_redirects=True)
    if r.status_code in BLOCK:
        _rate_limit_record_block(src, r.status_code, "probe_tpex_margin_balance_20261001")
    path.write_bytes(r.content)
    meta = {"url": r.url, "status": r.status_code, "content_type": r.headers.get("content-type"),
            "bytes": len(r.content), "history": [h.status_code for h in r.history],
            "fetched_at": datetime.now().isoformat(timespec="seconds")}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


HIST = ROOT / "data" / "margin_by_stock_history.json"
DAY, PREV_DAY, NEXT_DAY = "20261001", "20260930", "20261002"
SRC_TAG = "official:www.tpex.org.tw/www/zh-tw/margin/balance"


def _n(s):
    return float(str(s).replace(",", "").strip())


def apply() -> int:
    """零請求：讀已存原始回應，驗前後日鏈結 ≥95% 才寫進 by_data_date.tpex.20261001（已有就不覆寫）。"""
    j = json.loads((RAW / "balance_20261001.bin").read_bytes())
    tb = j["tables"][0]
    if j.get("date") != DAY or tb.get("date") != "115/10/01":
        print("回應日期不是 2026-10-01，不寫", j.get("date"), tb.get("date"))
        return 1
    f = tb["fields"]
    ia, ip, isb = f.index("資餘額"), f.index("前資餘額(張)"), f.index("券餘額")
    new = {r[0].strip(): [_n(r[ia]), _n(r[ip]), _n(r[isb])] for r in tb["data"]}
    doc = json.loads(HIST.read_text(encoding="utf-8"))
    t = doc["by_data_date"]["tpex"]
    if DAY in t:
        print("by_data_date.tpex.20261001 已存在，先到先存、不覆寫")
        return 0
    a, b = t[PREV_DAY], t[NEXT_DAY]
    c1 = [c for c in new if c in a]
    c2 = [c for c in new if c in b]
    r1 = sum(new[c][1] == a[c][0] for c in c1) / len(c1)
    r2 = sum(new[c][0] == b[c][1] for c in c2) / len(c2)
    print(f"前日餘額＝9/30 今日：{r1:.4f}（{len(c1)} 檔）；今日餘額＝10/02 前日：{r2:.4f}（{len(c2)} 檔）")
    if min(r1, r2) < 0.95:
        print("鏈結不足 95%，不寫")
        return 1
    tpex_codes = set(doc.get("tpex_codes") or [])
    keep = {c: v for c, v in new.items() if c in tpex_codes}
    print(f"官方 {len(new)} 檔，寫入 tpex_codes 內 {len(keep)} 檔；未寫：{sorted(set(new) - set(keep))}")
    t[DAY] = keep
    doc["by_data_date"]["tpex"] = dict(sorted(t.items()))
    s = doc["by_data_date_src"]["tpex"]
    s[DAY] = SRC_TAG
    doc["by_data_date_src"]["tpex"] = dict(sorted(s.items()))
    HIST.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return 0


def main() -> int:
    if "--apply" in sys.argv:
        return apply()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, src, url, params in PROBES:
        if only and name != only:
            continue
        m = fetch(name, src, url, params)
        print(name, json.dumps(m, ensure_ascii=False))
        if m["status"] in BLOCK:
            print("被擋，停止")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
