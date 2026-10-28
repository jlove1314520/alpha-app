"""先.一三五-1q-a：候選 N12 可轉債「現行轉換價」與重設紀錄的官方開放資料查證（三來源之①②）。

只記錄欄位、筆數、資料日期，不讀價格、不算報酬、不登記試驗。
請求預算（每端點 1 次，已存的不重抓）：
  - www.tpex.org.tw/openapi/v1/bond_ISSBD5_data（tpex_openapi；轉(交)換債發行資料，看是否只有發行時轉換價）
  - openapi.twse.com.tw/v1/swagger.json（twse_openapi；列可轉債／轉換價相關端點）
TPEx robots.txt 轉址錯誤頁（不存在，2026-10-16 已查）；TWSE openapi robots.txt 404（2026-10-28 先.一三五-1i 已查）。
MOPS robots 全站 Disallow，不抓。共用 data/rate_limit_state.json（同源 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。
原始回應存 research/data/raw/cand_n12_cb_probe/。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

OUT = HERE / "data" / "raw" / "cand_n12_cb_probe"
UA = {"User-Agent": "alpha-research-probe/1.0"}
PROBES = [
    ("tpex_bond_ISSBD5_data", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/bond_ISSBD5_data"),
    ("twse_openapi_swagger", "twse_openapi", "https://openapi.twse.com.tw/v1/swagger.json"),
]
CB_RE = re.compile(r"轉換|可轉|轉\(交\)換|公司債|債券", re.I)


def fetch(name: str, src: str, url: str):
    f = OUT / f"{name}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8"), "cached"
    _rate_limit_wait_or_raise(src)
    r = requests.get(url, headers=UA, timeout=60)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block(src, r.status_code, "probe_cb_conversion_price.py")
        raise RuntimeError(f"HTTP {r.status_code} → 封鎖 2 小時")
    r.encoding = "utf-8"
    f.write_text(r.text, encoding="utf-8")
    return r.text, r.status_code


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, src, url in PROBES:
        try:
            text, code = fetch(name, src, url)
        except Exception as e:  # noqa: BLE001 -- 單一端點失敗只略過
            summary[name] = {"error": repr(e)}
            print(f"[{name}] 略過：{e!r}")
            continue
        info = {"http": code, "bytes": len(text)}
        try:
            j = json.loads(text.lstrip("﻿"))
        except ValueError:
            info["not_json_head"] = text[:200]
            summary[name] = info
            continue
        if isinstance(j, list):
            keys = list(j[0].keys()) if j and isinstance(j[0], dict) else []
            info.update(n=len(j), keys=keys,
                        conversion_keys=[k for k in keys if "onversion" in k or "xchange" in k],
                        data_dates=sorted({str(x.get("Date")) for x in j if isinstance(x, dict)})[:5])
            # 同一債券代碼是否出現多列（多列才可能有轉換價歷次變動）
            codes = [x.get("BondCode") for x in j if isinstance(x, dict)]
            info["distinct_bond_codes"] = len(set(codes))
        elif isinstance(j, dict) and "paths" in j:
            eps = []
            for p, v in j["paths"].items():
                for o in v.values():
                    s = f"{o.get('summary', '')} {' '.join(o.get('tags', []))}"
                    if CB_RE.search(s):
                        eps.append({"path": p, "summary": o.get("summary", "")})
            info.update(n_paths=len(j["paths"]), cb_related_endpoints=eps,
                        conversion_price_endpoints=[e for e in eps if "轉換價" in e["summary"]])
        summary[name] = info
        print(f"[{name}] {json.dumps(info, ensure_ascii=False)[:1500]}")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
