# -*- coding: utf-8 -*-
"""先.一三二-2（2026-10-23）：V1 官方日檔的低記憶體精簡索引（零請求、只讀本機快取）。

背景：收件匣 017 的 var1018_v1_coverage_windows.py／var1018_v1_reduction_events.py 兩次被系統以記憶體嚴重不足中止。
根因是兩支都把每天官方日檔整份 rows（約 1,500 檔×6 欄的 dict）留在快取裡不釋放，4,184 個日檔（磁碟 154MB）
載入成 Python 物件後是好幾 GB。這裡改成「每個檔只讀一次、讀完即丟，只留需要的欄位」：
- day_status：日期 → (上市狀態, 上櫃狀態)（檔案不存在＝None），供停牌分類用；
- listed：代號 → 有列出的日期（numpy datetime64[D]，兩市場合併），供停牌分類用；
- official：代號 → 收盤為數字的日期（numpy），日期範圍與 var1018_v1_coverage_recompute.official_index() 完全相同
  （① 診斷的缺口日期＋上櫃 2007 上半年逐檔×月）。
判斷邏輯與 var1018_v1_halt_check.classify_interval() 逐行對應，自測拿 halt_check.json 既有分類結果比對。
"""
from __future__ import annotations

import ctypes
import json
from collections import defaultdict
from ctypes import wintypes
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OFF = HERE / "data" / "v1_official_daily"
DIAG = HERE / "data" / "var1018_v1_gap_diagnosis.json"


def peak_mb() -> float:
    """本行程的峰值工作集（MB，Windows GetProcessMemoryInfo）；非 Windows 回 resource 的 ru_maxrss。"""
    try:
        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(c)
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        f = ctypes.windll.psapi.GetProcessMemoryInfo
        f.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        f.restype = wintypes.BOOL
        if not f(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return -1.0
        return round(c.PeakWorkingSetSize / 2**20, 1)
    except Exception:  # noqa: BLE001
        try:
            import resource
            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
        except Exception:  # noqa: BLE001
            return -1.0


def _arr(d: dict) -> dict[str, np.ndarray]:
    return {k: np.array(sorted(v), dtype="datetime64[D]") for k, v in d.items()}


def build_index() -> dict:
    """單次串流掃描全部官方日檔；回傳 {"day_status", "listed", "official"}。"""
    diag_days = {d.replace("-", "") for d in json.loads(DIAG.read_text(encoding="utf-8"))["weekdays_to_fill"]}
    day_status: dict[np.datetime64, list] = defaultdict(lambda: [None, None])
    listed: dict[str, set] = defaultdict(set)
    official: dict[str, set] = defaultdict(set)
    for si, src in enumerate(("twse", "tpex")):
        for p in sorted((OFF / src).glob("*.json")):
            j = json.loads(p.read_text(encoding="utf-8"))
            ymd = p.stem
            d = np.datetime64(f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}", "D")
            day_status[d][si] = j.get("status")
            in_diag = ymd in diag_days
            for code, row in (j.get("rows") or {}).items():
                listed[code].add(d)
                if in_diag and row[3] is not None:
                    official[code].add(d)
            del j
    for p in sorted((OFF / "tpex_stock").glob("*/*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        for day, row in (j.get("rows") or {}).items():
            if row[3] is not None:
                official[j["code"]].add(np.datetime64(pd.Timestamp(day).date(), "D"))
    return {"day_status": {k: tuple(v) for k, v in day_status.items()}, "listed": _arr(listed), "official": _arr(official)}


def classify_interval(code: str, a, b, idx: dict) -> str:
    """與 var1018_v1_halt_check.classify_interval() 同義：a、b 為缺口兩端，檢查兩者之間的營業日。"""
    kinds = set()
    lst = idx["listed"].get(code)
    for d in pd.bdate_range(pd.Timestamp(a) + pd.Timedelta(days=1), pd.Timestamp(b) - pd.Timedelta(days=1)):
        dd = np.datetime64(d.date(), "D")
        tw, tp = idx["day_status"].get(dd, (None, None))
        if tw is None or tp is None:
            kinds.add("pending")
            continue
        if tw != "ok" and tp != "ok":
            continue
        listed_here = lst is not None and (i := np.searchsorted(lst, dd)) < len(lst) and lst[i] == dd
        if listed_here:
            kinds.add("listed_no_price")
        elif tw == "ok" and tp == "ok":
            kinds.add("official_absent")
        else:
            kinds.add("no_official_source")
    if not kinds:
        return "official_absent"
    for k in ("pending", "listed_no_price", "no_official_source"):
        if k in kinds:
            return k
    return "official_absent"
