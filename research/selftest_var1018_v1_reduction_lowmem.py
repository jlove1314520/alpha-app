# -*- coding: utf-8 -*-
"""先.一三二-2 自測（零請求）：var1018_v1_reduction_events 低記憶體版 locate() 與舊版逐筆相同，並記錄峰值記憶體。

舊版 locate()（2026-10-22 版）原樣搬到這裡當對照，但不留整日快取（每次重讀檔），固定種子抽 12 個官方確認停牌缺口
（上市、上櫃都要有）比對 (市場, 停牌前日, 停牌前收盤, 恢復日, 恢復日收盤)。
跑法：cd research && python selftest_var1018_v1_reduction_lowmem.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import var1018_v1_reduction_events as E  # noqa: E402
from var1018_v1_lowmem import peak_mb  # noqa: E402

PEAK_LIMIT_MB = 1500


def _rows(src: str, ymd: str) -> dict:
    p = E.OFF / src / f"{ymd}.json"
    return (json.loads(p.read_text(encoding="utf-8")).get("rows") or {}) if p.exists() else {}


def old_locate(code: str, a: str, b: str):
    a8, b8 = a.replace("-", ""), b.replace("-", "")
    for src in ("twse", "tpex"):
        ds = sorted(p.stem for p in (E.OFF / src).glob("*.json"))
        pre = next((d for d in reversed(ds) if d <= a8 and code in _rows(src, d)), None)
        post = next((d for d in ds if d >= b8 and code in _rows(src, d)), None)
        if pre and post:
            pc, rc = _rows(src, pre)[code][3], _rows(src, post)[code][3]
            if pc and rc:
                return src, pre, pc, post, rc
    return None


def main() -> int:
    halt = json.loads(E.HALT.read_text(encoding="utf-8"))
    ivs = [(r["code"], iv["from"], iv["to"]) for r in halt["rows"] for iv in r.get("intervals") or []
           if iv.get("class") == "official_absent"]
    series = E.build_series({c for c, _, _ in ivs})
    peak_after_index = peak_mb()
    new_all = [E.locate(c, a, b, series) for c, a, b in ivs]
    by_src = {s: [i for i, r in enumerate(new_all) if r and r[0] == s] for s in ("twse", "tpex")}
    rnd = random.Random(20261023)
    pick = rnd.sample(by_src["twse"], min(6, len(by_src["twse"]))) + rnd.sample(by_src["tpex"], min(6, len(by_src["tpex"])))
    none_idx = [i for i, r in enumerate(new_all) if r is None][:2]
    bad = 0
    for i in pick + none_idx:
        c, a, b = ivs[i]
        o = old_locate(c, a, b)
        if o != new_all[i]:
            bad += 1
            print("  不一致", c, a, b, o, new_all[i])
    print(f"缺口 {len(ivs)} 個（上市 {len(by_src['twse'])}、上櫃 {len(by_src['tpex'])}、找不到 {sum(r is None for r in new_all)}）；"
          f"抽 {len(pick) + len(none_idx)} 個與舊版比對，不一致 {bad}")
    print(f"峰值工作集：建索引後 {peak_after_index} MB、最終 {peak_mb()} MB（上限 {PEAK_LIMIT_MB}）")
    ok = bad == 0 and pick and 0 < peak_after_index < PEAK_LIMIT_MB
    print("全部通過" if ok else "失敗")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
