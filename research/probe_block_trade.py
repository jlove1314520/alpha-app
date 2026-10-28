"""先.一三五-1l：鉅額交易日成交資訊端點查證＋歷史起點探測（候選 N10 前置，第 10 關）。

只記錄欄位、筆數、資料日期與「能不能查歷史」，不讀價格數值、不算報酬。
請求預算（每端點 1 次）：
  - www.twse.com.tw rwd BFIAUU 帶 2005-01-03（twse_rwd；既有快取已證明 2015 起可查，此次只探更早起點）
  - www.tpex.org.tw openapi tpex_daily_qutoes_block、tpex_daily_trade_block_day（tpex_openapi；swagger 無參數）
TWSE robots.txt（2026-10-14 已查）只禁 /epaper/、/FTSE/；TPEx robots.txt 轉址錯誤頁（不存在，2026-10-16 已查）。
共用 data/rate_limit_state.json（同源 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。
原始回應存 research/data/raw/block_trade_probe/，已存的不重抓。
先.一三五-1z（2026-10-28）：加 `--latest`＝只對最近一個已收盤交易日（照 data/trading_calendar.json 扣休市、
台北 15:00 前不算今天）送 1 次 BFIAUU，確認現行欄位；只記 fields／title／列數／交易別種類，不讀價格數值。
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

OUT = HERE / "data" / "raw" / "block_trade_probe"
UA = {"User-Agent": "alpha-research-probe/1.0"}
PROBES = [
    ("twse_rwd_bfiauu_20050103", "twse_rwd", "https://www.twse.com.tw/rwd/zh/block/BFIAUU",
     {"date": "20050103", "response": "json"}),
    ("tpex_openapi_daily_qutoes_block", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_daily_qutoes_block", None),
    ("tpex_openapi_daily_trade_block_day", "tpex_openapi", "https://www.tpex.org.tw/openapi/v1/tpex_daily_trade_block_day", None),
]


def latest_closed_day() -> str:
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415
    now = datetime.now(timezone(timedelta(hours=8)))
    cal = json.loads((HERE.parent / "data" / "trading_calendar.json").read_text(encoding="utf-8")).get("tw") or {}
    closed = set()
    for y in cal.values():
        closed.update((y or {}).get("closed") or [])
        closed.update((y or {}).get("unscheduled_closed") or [])
    d = now.date() if now.hour >= 15 else now.date() - timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in closed:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8")) if (OUT / "summary.json").exists() else {}
    probes = PROBES
    if "--latest" in sys.argv:
        day = latest_closed_day()
        probes = [(f"twse_rwd_bfiauu_{day}", "twse_rwd", "https://www.twse.com.tw/rwd/zh/block/BFIAUU",
                   {"date": day, "response": "json"})]
    for name, src, url, params in probes:
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
                _rate_limit_record_block(src, code, "probe_block_trade.py")
                summary[name] = {"http": code}
                print(f"[{name}] HTTP {code} → 封鎖 2 小時，停止")
                break
            text = r.text
            f.write_text(text, encoding="utf-8")
        info = {"http": code, "bytes": len(text)}
        try:
            j = json.loads(text.lstrip("﻿"))
            if isinstance(j, list):
                info.update(n=len(j), keys=list(j[0].keys()) if j and isinstance(j[0], dict) else None,
                            dates=sorted({str(x.get('Date') or x.get('TradingDate')) for x in j if isinstance(x, dict)})[:10])
            elif isinstance(j, dict):
                ti = (j.get("fields") or []).index("交易別") if "交易別" in (j.get("fields") or []) else None
                if ti is not None:
                    info["trade_types"] = sorted({str(row[ti]) for row in j.get("data") or [] if len(row) > ti})
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
