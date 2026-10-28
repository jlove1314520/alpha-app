# -*- coding: utf-8 -*-
"""候選 N9 前置：除權息停券日由既有除權息事件推導，對照官方預告快照驗證（先.一三五-1v，零請求）。

讀 data/ex_dividend_events.json（只取代號、除權息交易日、類型，**不讀價格**）、data/trading_calendar.json，
與先.一三五-1i 存在本機的停資停券預告快照（research/data/raw/margin_suspension_probe/ 的
twse_openapi_bfi84u.txt、tpex_openapi_margin_term.txt；2026-10-27／28 單日快照）。

推導規則 [自行裁量]：docs／既有程式沒寫過停券起訖與除權息交易日的營業日間隔，以快照反推——
  停券起日＝除權息交易日前第 4 個交易日；停券迄日＝除權息交易日前 1 個交易日（共 4 個交易日）。
比對：
  ① 正向：快照每列找同代號、除權息交易日落在 [迄日+1, 迄日+10 日曆日] 的事件，比推導起訖是否一致。
     沒有對應事件的列分「原因非除權息（減資／現增以外的 ETF 分割、受益人大會）」與「原因為除權息／空白但事件檔沒有」。
  ② 反向：事件檔裡推導停券起日落在快照可見區間（快照最早起日～最晚起日）的事件，快照裡有沒有那一列。
限制：快照只有 1 天、樣本少，屬「單日驗證」；上櫃快照 Reason 欄全空，無法從快照分辨停券原因。
輸出 research/data/cand_n9_exdiv_halt_derive.json。不讀價格、不算報酬、不登記試驗。自身失敗只警告、exit 0。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "data" / "raw" / "margin_suspension_probe"
OUT = ROOT / "research" / "data" / "cand_n9_exdiv_halt_derive.json"
TW = timezone(timedelta(hours=8))
HALT_DAYS = 4
EXDIV_REASONS = {"除息", "除權", "除權息", "分配收益", "現金增資"}  # 現金增資＝除權（認購權）交易日同規則


def _closed() -> set[str]:
    cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8")).get("tw") or {}
    out: set[str] = set()
    for y in cal.values():
        out.update((y or {}).get("closed") or [])
    return out


def _roc(s: str) -> date:
    return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))


def _shift(d: date, n: int, closed: set[str]) -> date:
    """往前（n<0）或往後數 n 個交易日。"""
    step = 1 if n > 0 else -1
    k = 0
    while k != n:
        d += timedelta(days=step)
        if d.weekday() < 5 and d.isoformat() not in closed:
            k += step
    return d


def derive(ex: date, closed: set[str]) -> tuple[date, date]:
    return _shift(ex, -HALT_DAYS, closed), _shift(ex, -1, closed)


def main() -> dict:
    closed = _closed()
    events = json.loads((ROOT / "data" / "ex_dividend_events.json").read_text(encoding="utf-8")).get("events") or {}
    twse = json.loads((RAW / "twse_openapi_bfi84u.txt").read_text(encoding="utf-8"))
    tpex = json.loads((RAW / "tpex_openapi_margin_term.txt").read_text(encoding="utf-8"))
    snap = [{"market": "twse", "code": x["Code"], "start": _roc(x["StartDate"]), "end": _roc(x["EndDate"]), "reason": x["Reason"]}
            for x in twse]
    snap += [{"market": "tpex", "code": x["SecuritiesCompanyCode"], "start": _roc(x["ShortSaleSuspensionStartDate"]),
              "end": _roc(x["ShortSaleSuspensionEndDate"]), "reason": x["Reason"]} for x in tpex]

    match, mismatch, no_event = [], [], []
    for r in snap:
        cands = [e for e in events.get(r["code"]) or []
                 if r["end"] < date.fromisoformat(e["ex_date"]) <= r["end"] + timedelta(days=10)]
        row = {"market": r["market"], "code": r["code"], "reason": r["reason"] or "（空白）",
               "snap_start": r["start"].isoformat(), "snap_end": r["end"].isoformat()}
        if not cands:
            row["why"] = ("原因非除權息" if r["reason"] and r["reason"] not in EXDIV_REASONS
                          else "事件檔沒有對應的除權息交易日（未公告／未收錄，或停券原因非除權息）")
            no_event.append(row)
            continue
        ex = date.fromisoformat(cands[0]["ex_date"])
        s, e = derive(ex, closed)
        row.update(ex_date=ex.isoformat(), event_type=cands[0].get("type"), derived_start=s.isoformat(), derived_end=e.isoformat())
        (match if (s, e) == (r["start"], r["end"]) else mismatch).append(row)

    lo, hi = min(r["start"] for r in snap), max(r["start"] for r in snap)
    snap_codes = {r["code"] for r in snap}
    missing = []
    for code, evs in events.items():
        for ev in evs or []:
            s, e = derive(date.fromisoformat(ev["ex_date"]), closed)
            if lo <= s <= hi and code not in snap_codes:
                missing.append({"code": code, "ex_date": ev["ex_date"], "type": ev.get("type"), "derived_start": s.isoformat()})
    n_cmp = len(match) + len(mismatch)
    doc = {
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "item": "先.一三五-1v",
        "rule": f"停券起日＝除權息交易日前第 {HALT_DAYS} 個交易日；迄日＝前 1 個交易日（[自行裁量] 由快照反推，docs／既有程式未寫過）",
        "snapshot": "research/data/raw/margin_suspension_probe（2026-10-27／28 單日快照，先.一三五-1i）",
        "limits": ["單日驗證：快照只有 1 天、樣本少", "上櫃快照 Reason 欄全空，無法分辨停券原因",
                   "事件檔只收錄已公告且被管線抓到的除權息，未來事件可能還沒進檔"],
        "n_snapshot_rows": len(snap),
        "n_compared": n_cmp, "n_match": len(match), "n_mismatch": len(mismatch),
        "match_rate": round(len(match) / n_cmp, 4) if n_cmp else None,
        "matches": match, "mismatches": mismatch, "snapshot_rows_without_event": no_event,
        "reverse_window": [lo.isoformat(), hi.isoformat()],
        "events_expected_but_not_in_snapshot": missing,
        "note": "零外部請求；不讀價格、不算報酬、不登記試驗",
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {k: doc[k] for k in ("n_snapshot_rows", "n_compared", "n_match", "n_mismatch", "match_rate")} | \
        {"n_without_event": len(no_event), "n_reverse_missing": len(missing)}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節
        print(f"[warn] cand_n9_exdiv_halt_derive 失敗：{type(e).__name__}: {e}")
    raise SystemExit(0)
