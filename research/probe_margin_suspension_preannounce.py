"""先.一三五-1i：停資停券預告表端點查證＋歷史起點探測（候選 N9 前置，第 10 關）。

只記錄欄位、筆數與「能不能查歷史」，不讀價格、不算報酬。
請求預算（每端點最多 2 次）：
  - openapi.twse.com.tw robots.txt 1 次、BFI84U 1 次（twse_openapi）
  - www.twse.com.tw rwd BFI84U 帶區間 2 次（twse_rwd；網頁版有日期查詢就能查歷史）
  - www.tpex.org.tw openapi tpex_margin_trading_term 1 次（tpex_openapi）
共用 data/rate_limit_state.json（同源 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。
原始回應存 research/data/raw/margin_suspension_probe/，已存的不重抓。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

OUT = HERE / "data" / "raw" / "margin_suspension_probe"
UA = {"User-Agent": "alpha-research-probe/1.0"}
PROBES = [
    ("twse_openapi_robots", "twse_openapi", "https://openapi.twse.com.tw/robots.txt", None),
    ("twse_openapi_bfi84u", "twse_openapi", "https://openapi.twse.com.tw/v1/exchangeReport/BFI84U", None),
    ("twse_rwd_bfi84u_recent", "twse_rwd", "https://www.twse.com.tw/rwd/zh/marginTrading/BFI84U",
     {"startDate": "20261001", "endDate": "20261027", "response": "json"}),
    ("twse_rwd_bfi84u_2013", "twse_rwd", "https://www.twse.com.tw/rwd/zh/marginTrading/BFI84U",
     {"startDate": "20130601", "endDate": "20130630", "response": "json"}),
    ("tpex_openapi_margin_term", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading_term", None),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name, src, url, params in PROBES:
        f = OUT / f"{name}.txt"
        if f.exists():
            text, code = f.read_text(encoding="utf-8"), "cached"
        else:
            try:
                _rate_limit_wait_or_raise(src)
            except Exception as e:  # noqa: BLE001 -- 封鎖冷卻中就跳過，不硬送
                summary[name] = {"skipped": repr(e)}
                print(f"[{name}] 跳過：{e!r}")
                continue
            try:
                r = requests.get(url, params=params, headers=UA, timeout=30)
            except Exception as e:  # noqa: BLE001
                summary[name] = {"error": repr(e)}
                print(f"[{name}] 失敗：{e!r}")
                continue
            code = r.status_code
            if code in (402, 403, 428, 429):
                _rate_limit_record_block(src, code, "probe_margin_suspension_preannounce.py")
                summary[name] = {"http": code}
                print(f"[{name}] HTTP {code} → 封鎖 2 小時，停止")
                break
            text = r.text
            f.write_text(text, encoding="utf-8")
        info = {"http": code, "bytes": len(text)}
        try:
            j = json.loads(text.lstrip("﻿"))
            if isinstance(j, list):
                info.update(n=len(j), keys=list(j[0].keys()) if j and isinstance(j[0], dict) else None)
            elif isinstance(j, dict):
                info.update(top=list(j.keys())[:12], stat=j.get("stat"), title=j.get("title"),
                            fields=j.get("fields"), n=len(j.get("data") or []),
                            tables=[(t.get("title"), t.get("fields"), len(t.get("data") or []))
                                    for t in (j.get("tables") or [])])
        except ValueError:
            info["not_json_head"] = text[:200]
        summary[name] = info
        print(f"[{name}] {json.dumps(info, ensure_ascii=False)[:900]}")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
