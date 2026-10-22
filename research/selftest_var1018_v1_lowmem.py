# -*- coding: utf-8 -*-
"""先.一三二-2 自測（零請求、不算報酬）：低記憶體版與舊版結果一致，並記錄峰值記憶體。

1. var1018_v1_lowmem.classify_interval() 對 data/var1018_v1_halt_check.json 全部 497 個缺口區間，
   分類要與舊版 var1018_v1_halt_check.classify_interval() 當時寫下的 class 逐筆相同。
2. var1018_v1_coverage_windows.coverage_all() 只跑 V1 原窗口（2007-01-02～2014-12-31）：
   原定義要重現 var1018_v1_coverage_recompute.json（母體 1,247、涵蓋 79.79%、下市股 90 檔 63.33%）；
   主定義要重現 halt_check.json 的輔助數字（停牌不算缺口 91.18%／86.67%）。
3. 峰值工作集 < 1,500 MB（舊版被系統以記憶體不足中止；本機實體 31.4GB、10/23 00:3x 可用約 4.3GB）。
跑法：cd research && python selftest_var1018_v1_lowmem.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import var1018_v1_coverage_windows as W  # noqa: E402
import var1018_v1_lowmem as L  # noqa: E402

D = Path(__file__).resolve().parent / "data"
PEAK_LIMIT_MB = 1500


def main() -> int:
    fails = []
    idx = L.build_index()
    print(f"索引建好：峰值 {L.peak_mb()} MB")
    halt = json.loads((D / "var1018_v1_halt_check.json").read_text(encoding="utf-8"))
    n = bad = 0
    for r in halt["rows"]:
        for iv in r.get("intervals") or []:
            n += 1
            got = L.classify_interval(r["code"], iv["from"], iv["to"], idx)
            if got != iv["class"]:
                bad += 1
                if bad <= 5:
                    print("  不一致", r["code"], iv, got)
    print(f"[1] 停牌分類 {n} 筆，不一致 {bad}")
    if bad or n == 0:
        fails.append("classify")

    rec = json.loads((D / "var1018_v1_coverage_recompute.json").read_text(encoding="utf-8"))
    aux = halt["coverage_if_official_halt_not_gap_AUXILIARY"]
    W.WINDOWS = {"V1": ("2007-01-02", "2014-12-31")}
    cands, dead = W.V.candidates()
    dl = W.pd.read_parquet(W.V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = W.pd.to_datetime(dl["date"])
    res = W.coverage_all(cands, dead, idx, dict(zip(dl["stock_id"], dl["date"])))["V1"]
    print("[2] V1 原窗口：", json.dumps(res, ensure_ascii=False))
    print("    舊版 recompute：", rec["n_universe_t0"], rec["universe_coverage"], rec["n_delisted_in_universe"], rec["delisted_coverage"])
    print("    舊版輔助（停牌不算缺口）：", json.dumps(aux, ensure_ascii=False))
    exp = (rec["n_universe_t0"], rec["universe_coverage"], rec["n_delisted_in_universe"], rec["delisted_coverage"])
    if (res["n_universe_t0"], res["orig_universe"], res["n_delisted_in_universe"], res["orig_delisted"]) != exp:
        fails.append("orig_coverage")
    peak = L.peak_mb()
    print(f"[3] 峰值工作集 {peak} MB（上限 {PEAK_LIMIT_MB}）")
    if not (0 < peak < PEAK_LIMIT_MB):
        fails.append("peak")
    print("全部通過" if not fails else f"失敗：{fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
