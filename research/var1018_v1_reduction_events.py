# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 017（2026-10-22）：V1 2007～2014 官方確認停牌缺口的減資（恢復買賣參考價）係數。

為什麼要推導：TWSE TWTAUU（減資恢復買賣參考價）只能查 2011-01-01 以後（2007～2010 回「查詢開始日期小於100年1月1日」），
FinMind TaiwanStockCapitalReductionReferencePrice 本機快取 2010 年起且漏 1441 2010-10；上櫃沒有官方減資參考價表。
七節「主來源→備援→由已有欄位推導」第三條路：恢復買賣當天官方每日收盤行情的「漲跌價差」是相對恢復買賣參考價算的，
所以 參考價＝恢復日收盤 − 漲跌（帶正負號），係數＝參考價 ÷ 停止買賣前收盤（與 TWTAUU／adjust.py 同一式）。

做法（零報酬計算、不碰 2015 以後）：
1. 讀 data/var1018_v1_halt_check.json 裡 class=official_absent 的停牌缺口（全市場日檔有資料、這檔兩邊都沒列）。
2. 停牌前收盤、恢復日收盤取自既有快取 data/v1_official_daily/{twse,tpex}/（V1 官方日檔補抓留下的）。
3. 恢復日的完整官方日檔（含漲跌欄）重抓一次存 data/raw/v1_resume_day/{src}/YYYYMMDD.json（已存在不重抓），
   URL／參數／節流與 var1018_v1_official_fill.py 相同（twse_mi_index／tpex_www，同源 ≥3 秒、402/403/428/429 封鎖 2 小時不重試）。
4. 2011 年起 TWTAUU 有的事件，推導值與 TWTAUU 並列核對（方法驗證）；採用值以 TWTAUU 為準。
5. |係數−1| < 0.5% 視為單純停牌（不調整）；前後收盤跳動 >±20% 卻推導不出係數的缺口列清單，不得默默算進報酬。

跑法：cd research && python var1018_v1_reduction_events.py
輸出：data/v1_reduction_events_2007_2014.csv（adjust.py 讀它補減資事件）、data/v1_reduction_events_report.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from var1018_v1_official_fill import BLOCK, SOURCES, UA  # noqa: E402

D = HERE / "data"
HALT = D / "var1018_v1_halt_check.json"
OFF = D / "v1_official_daily"
RAW = D / "raw" / "v1_resume_day"
TWTAUU = D / "twse_reduction_2007_2014.csv"
OUT = D / "v1_reduction_events_2007_2014.csv"
REPORT = D / "v1_reduction_events_report.json"
PURE_HALT_TOL = 0.005
JUMP_LIST = 0.20
CHANGE_COL = {"twse": ("漲跌(+/-)", "漲跌價差"), "tpex": (None, "漲跌")}


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("+", "").strip())
    except ValueError:
        return None


_days: dict[str, list[str]] = {}


def days(src: str) -> list[str]:
    if src not in _days:
        _days[src] = sorted(p.stem for p in (OFF / src).glob("*.json"))
    return _days[src]


_cache: dict[tuple, dict] = {}


def rows_of(src: str, ymd: str) -> dict:
    k = (src, ymd)
    if k not in _cache:
        p = OFF / src / f"{ymd}.json"
        _cache[k] = (json.loads(p.read_text(encoding="utf-8")).get("rows") or {}) if p.exists() else {}
    return _cache[k]


def locate(code: str, a: str, b: str) -> tuple[str, str, float, str, float] | None:
    """(市場, 停牌前日, 停牌前收盤, 恢復日, 恢復日收盤)。兩市場都找不到回 None。
    halt_check 的 from／to 是缺口兩端「有價格的日子」（var1018_v1_halt_check.classify_interval：檢查 a、b 之間），
    所以停牌前日＝≤from 的最後一天、恢復日＝≥to 的第一天（含端點）。"""
    a8, b8 = a.replace("-", ""), b.replace("-", "")
    for src in ("twse", "tpex"):
        ds = days(src)
        pre = next((d for d in reversed(ds) if d <= a8 and code in rows_of(src, d)), None)
        post = next((d for d in ds if d >= b8 and code in rows_of(src, d)), None)
        if pre and post:
            pc, rc = rows_of(src, pre)[code][3], rows_of(src, post)[code][3]
            if pc and rc:
                return src, pre, pc, post, rc
    return None


def fetch_resume(src: str, ymd: str) -> dict | None:
    p = RAW / src / f"{ymd}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    cfg = SOURCES[src]
    d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    _rate_limit_wait_or_raise(cfg["rl"])
    r = requests.get(cfg["url"], params=cfg["params"](d), timeout=60, headers={"User-Agent": UA})
    if r.status_code in BLOCK:
        _rate_limit_record_block(cfg["rl"], r.status_code, f"v1_reduction_events {d}")
        raise SystemExit(f"HTTP {r.status_code}，{cfg['rl']} 封鎖 2 小時，停止（已抓的保留）")
    js = r.json()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
    return js


def signed_change(src: str, js: dict, code: str) -> float | None:
    tbl = next((t for t in js.get("tables") or [] if SOURCES[src]["title_has"] in str(t.get("title") or "")), None)
    if tbl is None:
        return None
    fl = tbl.get("fields") or []
    sign_col, val_col = CHANGE_COL[src]
    ic = next((i for i, f in enumerate(fl) if f == SOURCES[src]["cols"]["code"]), None)
    iv = next((i for i, f in enumerate(fl) if f == val_col), None)
    isg = next((i for i, f in enumerate(fl) if f == sign_col), None) if sign_col else None
    if ic is None or iv is None:
        return None
    for row in tbl.get("data") or []:
        if str(row[ic]).strip() != code:
            continue
        v = _num(row[iv])
        if v is None:
            return None
        if isg is not None:
            s = re.sub(r"<[^>]+>", "", str(row[isg])).strip()
            if s == "-":
                v = -abs(v)
            elif s in ("+", ""):
                v = abs(v) if s == "+" else (0.0 if v == 0 else None)
            else:  # 「X」＝不比價等，推導不出
                return None
        return v
    return None


def main() -> int:
    halt = json.loads(HALT.read_text(encoding="utf-8"))
    tw = pd.read_csv(TWTAUU, dtype={"stock_id": str}) if TWTAUU.exists() else pd.DataFrame(columns=["date", "stock_id", "factor"])
    tw_map = {(r.stock_id, r.date): r for r in tw.itertuples()}
    events, unresolved, checks = [], [], []
    for row in halt["rows"]:
        for iv in row.get("intervals") or []:
            if iv.get("class") != "official_absent":
                continue
            code = row["code"]
            loc = locate(code, iv["from"], iv["to"])
            if loc is None:
                unresolved.append({"code": code, "from": iv["from"], "to": iv["to"], "why": "找不到停牌前／恢復日收盤"})
                continue
            src, pre, pc, post, rc = loc
            rd = f"{post[:4]}-{post[4:6]}-{post[6:]}"
            ch = signed_change(src, fetch_resume(src, post), code)
            derived = (rc - ch) / pc if ch is not None and rc - ch > 0 else None
            t = tw_map.get((code, rd))
            if t is not None and derived is not None:
                checks.append({"code": code, "date": rd, "twtauu": round(t.factor, 6), "derived": round(derived, 6),
                               "diff": round(derived - t.factor, 6)})
            factor, source = (t.factor, "twse_twtauu") if t is not None else (derived, f"derived_resume_change_{src}")
            jump = rc / pc - 1
            if factor is None:
                if abs(jump) > JUMP_LIST:
                    unresolved.append({"code": code, "from": iv["from"], "to": iv["to"], "pre_close": pc, "resume_close": rc,
                                       "jump": round(jump, 4), "why": "跳動 >±20% 但恢復日漲跌欄推導不出參考價"})
                continue
            kind = "pure_halt" if abs(factor - 1) < PURE_HALT_TOL else "reduction"
            events.append({"stock_id": code, "market": src, "halt_from": iv["from"], "halt_to": iv["to"],
                           "pre_date": f"{pre[:4]}-{pre[4:6]}-{pre[6:]}", "pre_close": pc, "resume_date": rd,
                           "resume_close": rc, "ref_price": round(factor * pc, 4), "factor": round(factor, 6),
                           "source": source, "kind": kind})
    ev = pd.DataFrame(events)
    ev.to_csv(OUT, index=False)
    rep = {"n_gaps_events": len(ev), "n_reduction": int((ev["kind"] == "reduction").sum()) if len(ev) else 0,
           "n_pure_halt": int((ev["kind"] == "pure_halt").sum()) if len(ev) else 0,
           "by_source": ev["source"].value_counts().to_dict() if len(ev) else {},
           "twtauu_vs_derived": checks, "unresolved": unresolved}
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("twtauu_vs_derived", "unresolved")}, ensure_ascii=False))
    print("TWTAUU vs 推導（方法驗證）：", json.dumps(checks, ensure_ascii=False))
    print(f"推導不出且跳動 >±20%：{len(unresolved)} 筆", json.dumps(unresolved[:10], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
