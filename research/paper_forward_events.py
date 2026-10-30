# -*- coding: utf-8 -*-
"""事件型前向模擬（模擬 P／Q／R，先.一三六-B7）共用的小工具；組合／帳本／成本仍全在 paper_forward_common.py。

- t1 漲停鎖死判斷：官方檔位版 `research/official_limit.py`（`OfficialLimits.limits()`＋`lock_status()`，原始開高低收；
  上櫃先用前一交易日 TPEx 公告次日漲停價，除權息日／減資恢復日換基準）。收件匣 032（先.一三五-1ar-a 採甲，模擬 Q／R PREREG 修訂 R1）
  起取代原本的核心檔 `costs.limit_status()` ±10% 近似（核心檔本身不動）。
- 同代號 N 個交易日內只算第一個事件（依事件 t0 先後，與是否成交無關）。
- 交易日距離用 price_history 日曆；超出日曆的未來日期以「週一～五」近似（只用在除權息前後窗）。
"""
from __future__ import annotations

from datetime import date, timedelta

import paper_forward_common as C
from official_limit import OfficialLimits, lock_status

_OL: OfficialLimits | None = None  # 第一次用到才讀本機公告檔／除權息檔；自測可直接指定


def _ol() -> OfficialLimits:
    global _OL
    if _OL is None:
        _OL = OfficialLimits()
    return _OL


def iso(d: str) -> str:
    """'20261027' 或 '2026-10-27' → '2026-10-27'。"""
    d = str(d)
    return d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def row_on(px: C.Px, code: str, d: str):
    i = (px.idx.get(code) or {}).get(d)
    return None if i is None else px.rows[code][i]


def prev_row(px: C.Px, code: str, d: str):
    i = (px.idx.get(code) or {}).get(d)
    if i is None:
        return None
    rs = px.rows[code]
    return rs[i - 1] if i > 0 else None


def raw_ret(px: C.Px, code: str, d: str):
    """官方收盤（未還原）當日報酬；缺資料回 None。"""
    r, p = row_on(px, code, d), prev_row(px, code, d)
    if not r or not p or not r.get("close") or not p.get("close"):
        return None
    return float(r["close"]) / float(p["close"]) - 1


def locked_up(px: C.Px, code: str, d: str, ol: OfficialLimits | None = None) -> bool:
    """原始開高低收全在官方漲停價（含）以上＝鎖漲停。算不出官方價 → 不算鎖（十二節，official_limit 已警告）。"""
    r, p = row_on(px, code, d), prev_row(px, code, d)
    if not r or not p or p.get("close") in (None, 0):
        return False
    try:
        lim = (ol or _ol()).limits(code, d, p.get("date"), float(p["close"]))
        return lock_status(lim, r.get("open"), r.get("high"), r.get("low"), r.get("close"))[0]
    except (TypeError, ValueError, KeyError):
        return False


def tindex(px: C.Px, d: str) -> int:
    """d 在日曆中的位置（d 不是交易日時回傳「≤d 的最後交易日」的位置；早於日曆回 -1）。"""
    cal = px.calendar
    lo, hi = 0, len(cal)
    while lo < hi:
        m = (lo + hi) // 2
        if cal[m] <= d:
            lo = m + 1
        else:
            hi = m
    return lo - 1


def dedupe(events: list, px: C.Px, gap_days: int) -> list:
    """events 需含 code、t0；同代號在前一個被採計事件之後 gap_days 個交易日內的事件剔除。"""
    out, last = [], {}
    for ev in sorted(events, key=lambda e: (e["t0"], e["code"])):
        i = tindex(px, ev["t0"])
        j = last.get(ev["code"])
        if j is not None and i - j < gap_days:
            continue
        last[ev["code"]] = i
        out.append(ev)
    return out


def weekday_shift(d: str, n: int) -> str:
    """從 d 往後（n>0）或往前數 n 個週一～五（日曆外近似用）。"""
    x, step, k = date.fromisoformat(d), (1 if n > 0 else -1), abs(n)
    while k:
        x += timedelta(days=step)
        if x.weekday() < 5:
            k -= 1
    return x.isoformat()


def trading_window(px: C.Px, d: str, n: int) -> tuple[str, str]:
    """d 前後各 n 個交易日的 [起, 迄]（超出日曆的那一側用週一～五近似）。"""
    cal, i = px.calendar, tindex(px, d)
    lo = cal[i - n] if i - n >= 0 else weekday_shift(d, -n)
    if i + n < len(cal):
        hi = cal[i + n]
    else:  # 右側超出日曆：從日曆最後一天再往後數不足的交易日；d 本身在日曆之後時從 d 起算
        base = max(cal[-1], d) if cal else d
        hi = weekday_shift(base, n - (len(cal) - 1 - i) if base == cal[-1] else n)
    return lo, hi
