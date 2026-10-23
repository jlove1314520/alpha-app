"""補.資料-上櫃 2007-07～12-14 除權息標記：重抓官方日檔原始回應（DevQueue 20261023-160102）。

背景：上櫃 exDailyQ 歷史起點約 2007-12-17；`probe_tpex_exright_2007h2.py` 證實官方每日收盤行情
在除權息當日「漲跌」欄是文字（除權／除息／除權息），對 exDailyQ 重疊 154 筆全中。
`v1_official_daily/tpex/` 快取沒存漲跌欄，所以這裡重抓 2007-07-01～12-16 的完整官方日檔。

只建事件清單、不套用還原、不算報酬。參考價只附「前一交易日次日漲停／跌停」（近似，非官方參考價）。

URL 與節流同 var1018_v1_official_fill.py 的上櫃（`tpex_www`，同源 ≥3 秒、跨行程鎖，402/403/428/429
封鎖 2 小時不重試）。原始回應存 research/data/raw/tpex_daily_2007h2/，已存（或 v1_resume_day 已有）不重抓。
`--deadline HH:MM` 到點就停止送新請求（已抓的保留，下次從缺的日期續）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from var1018_v1_official_fill import BLOCK, SOURCES, UA  # noqa: E402

D = HERE / "data"
CACHE_DAYS = D / "v1_official_daily" / "tpex"
RESUME = D / "raw" / "v1_resume_day" / "tpex"
RAW = D / "raw" / "tpex_daily_2007h2"
OUT = D / "tpex_exright_marks_2007h2.json"
START, END = "20070701", "20071216"  # exDailyQ 自 2007-12-17 起有官方計算結果
MARKS = ("除權息", "除息", "除權")


def _num(s):
    try:
        return float(str(s).replace(",", "").replace(" ", "").replace("+", ""))
    except ValueError:
        return None


def trading_days() -> list[str]:
    return sorted(p.stem for p in CACHE_DAYS.glob("*.json") if START <= p.stem <= END)


def load_raw(ymd: str) -> dict | None:
    for p in (RAW / f"{ymd}.json", RESUME / f"{ymd}.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def fetch(ymd: str) -> dict:
    cfg = SOURCES["tpex"]
    _rate_limit_wait_or_raise(cfg["rl"])
    r = requests.get(cfg["url"], params=cfg["params"](f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"),
                     timeout=60, headers={"User-Agent": UA})
    if r.status_code in BLOCK:
        _rate_limit_record_block(cfg["rl"], r.status_code, f"tpex_exright_marks_2007h2 {ymd}")
        raise SystemExit(f"HTTP {r.status_code}，{cfg['rl']} 封鎖 2 小時，停止（已抓的保留）")
    r.raise_for_status()
    js = r.json()
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{ymd}.json").write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
    return js


def _rows(js: dict) -> dict:
    """回 {代號: {欄位名: 值}}；欄位用名稱對應（2007 年版本多了最後買量／賣量兩欄，位置會跑掉）。"""
    for t in js.get("tables", []):
        f = [x.strip() for x in (t.get("fields") or [])]
        if "漲跌" in f and t.get("data"):
            return {r[0]: dict(zip(f, r)) for r in t["data"]}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", help="HH:MM，到點停止送新請求")
    a = ap.parse_args()
    days = trading_days()
    fetched = 0
    stopped_at = None
    for ymd in days:
        if load_raw(ymd) is not None:
            continue
        if a.deadline and datetime.now().strftime("%H:%M") >= a.deadline:
            stopped_at = ymd
            print(f"到時間上限 {a.deadline}，停在 {ymd}（下次從這裡續）")
            break
        fetch(ymd)
        fetched += 1
    have = [d for d in days if load_raw(d) is not None]
    events, prev, empty = [], {}, []
    for ymd in have:
        rows = _rows(load_raw(ymd))
        if not rows:
            empty.append(ymd)
        for c, r in rows.items():
            s = str(r["漲跌"]).strip()
            if s in MARKS:
                p = prev.get(c)
                up, dn = (_num(p["次日漲停價"]), _num(p["次日跌停價"])) if p else (None, None)
                events.append({"date": ymd, "code": c, "name": r["名稱"].strip(), "kind": s,
                               "close": _num(r["收盤"]), "prev_close": _num(p["收盤"]) if p else None,
                               "prev_next_up": up, "prev_next_down": dn,
                               "approx_ref_mid": round((up + dn) / 2, 2) if up and dn else None})
        if rows:  # 休市日（官方回 0 列）不覆蓋前一交易日
            prev = rows
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "range": [START, END], "trading_days": len(days), "days_with_raw": len(have),
           "missing_days": [d for d in days if d not in have], "empty_days": empty,
           "fetched_this_run": fetched, "stopped_at": stopped_at, "n_events": len(events),
           "note": "標記來自官方每日收盤行情「漲跌」欄文字；approx_ref_mid＝前一交易日次日漲跌停中點，近似、非官方參考價"
                   "（2008～2014 驗證 68 筆中 60 筆距官方 <1%）。前一交易日缺原始檔時 prev_* 為 null。",
           "events": events}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"交易日 {len(days)}、有原始檔 {len(have)}、本次抓 {fetched}、事件 {len(events)}、空檔 {len(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
