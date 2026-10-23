# -*- coding: utf-8 -*-
"""先.一三三-1b（2026-10-23，DevQueue）：V1 PREREG 修訂 R2 的涵蓋率重算（零請求、只讀本機快取、不算任何報酬）。

R2 資料定義（Cowork 收件匣 020 B1「採甲」）：
1. 價格列只採「當天在 TWSE／TPEx 官方日檔有列」的日子：兩市場官方日檔當天都是 ok（可核對）時，這檔不在任一邊就丟掉那一列
   （多為興櫃期間，無漲跌幅限制，不屬於「上市＋上櫃普通股」母體）；任一邊官方檔不存在或非 ok 的日子沿用 FinMind（無法核對）。
2. 母體＝t0 前後 10 天內在官方日檔有列（任一市場）的候選股，且 R2 價格列在窗口內（同舊定義）。
3. 涵蓋率判斷式沿用 var1018_v1_coverage_windows._code_window()（原定義／主定義＝官方確認停牌不算缺口／satfix），只換價格日期集合。
窗口：V1 R1-b（2007-07-02～2014-12-31）＋先.一三三-2b 會用到的個股網格 B、ML 甲（同一定義，供下一項直接引用）。

跑法：cd research && python var1018_v1_r2_coverage.py            # 主結果（同 PREREG 涵蓋率定義：FinMind 有列就算，含收盤 0 的無成交列）
      cd research && python var1018_v1_r2_coverage.py --close-gt0 # 揭露變體：收盤 ≤0 不算價格列（＝單發程式實際可交易價）
輸出：research/data/var1018_v1_r2_coverage.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd

import finmind_client as F
import var1018_v1_coverage_windows as C
import var1018_v1_lowmem as L
import var1018_v1_prep as V

POSITIVE_CLOSE_ONLY = "--close-gt0" in sys.argv
OUT = Path(__file__).parent / "data" / ("var1018_v1_r2_coverage_close_gt0.json" if POSITIVE_CLOSE_ONLY else "var1018_v1_r2_coverage.json")
WINDOWS = {
    "V1_R1b_t0_20070702": ("2007-07-02", "2014-12-31"),
    "GRID_B_20071001_20091231": ("2007-10-01", "2009-12-31"),
    "ML_A_20080102_20121231": ("2008-01-02", "2012-12-31"),
}


def checkable_days(idx: dict) -> np.ndarray:
    """兩市場官方日檔當天都是 ok 的日子（可核對「這檔當天有沒有列」）。"""
    return np.array(sorted(d for d, (tw, tp) in idx["day_status"].items() if tw == "ok" and tp == "ok"), dtype="datetime64[D]")


def r2_filter(arr: np.ndarray, listed: np.ndarray | None, chk: np.ndarray) -> tuple[np.ndarray, int]:
    """R2：可核對日子只留官方有列者；回傳 (留下的日期, 丟掉幾列)。"""
    is_chk = np.isin(arr, chk)
    on_list = np.isin(arr, listed) if listed is not None and len(listed) else np.zeros(len(arr), bool)
    keep = ~is_chk | on_list
    return arr[keep], int((~keep).sum())


def in_official_near(listed: np.ndarray | None, t0: pd.Timestamp) -> bool:
    if listed is None or not len(listed):
        return False
    a = np.datetime64((t0 - pd.Timedelta(days=10)).date(), "D")
    b = np.datetime64((t0 + pd.Timedelta(days=10)).date(), "D")
    return bool(((listed >= a) & (listed <= b)).any())


def main() -> int:
    cands, dead = V.candidates()
    idx = L.build_index()
    chk = checkable_days(idx)
    print(f"官方索引：{len(idx['day_status'])} 天、可核對 {len(chk)} 天（{chk[0]}～{chk[-1]}）；峰值 {L.peak_mb()} MB", flush=True)
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    del dl
    acc = {k: {"universe": [], "orig": [], "main": [], "orig_satfix": [], "main_satfix": [], "dead": [],
               "excluded_not_official_near_t0": [], "dropped_rows": 0} for k in WINDOWS}
    for c in cands:
        if c == "0050":
            continue
        arr = idx["official"].get(c, np.array([], dtype="datetime64[D]"))
        if V.cached("TaiwanStockPrice", c):
            d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
            if not d.empty:
                if POSITIVE_CLOSE_ONLY:  # 變體：收盤 ≤0（FinMind 無成交日）不算價格列；主結果同 PREREG 涵蓋率定義＝有列就算
                    d = d[pd.to_numeric(d["close"], errors="coerce") > 0]
                arr = np.union1d(arr, pd.to_datetime(d["date"]).to_numpy().astype("datetime64[D]"))
            del d
        if len(arr) == 0:
            continue
        lst = idx["listed"].get(c)
        kept, dropped = r2_filter(np.unique(arr), lst, chk)
        if len(kept) == 0:
            continue
        t_all = pd.Series(pd.to_datetime(kept))
        for k, (a, b) in WINDOWS.items():
            t0, end_w = pd.Timestamp(a), pd.Timestamp(b)
            r = C._code_window(t_all, c, t0, end_w, ddate, idx)
            if r is None:
                continue
            if not in_official_near(lst, t0):
                acc[k]["excluded_not_official_near_t0"].append(c)
                continue
            acc[k]["universe"].append(c)
            gone = np.setdiff1d(np.unique(arr), kept)
            acc[k]["dropped_rows"] += int(((gone >= np.datetime64(a)) & (gone <= np.datetime64(b))).sum()) if dropped else 0
            if r == "universe_only":
                continue
            for j, name in enumerate(("orig", "main", "orig_satfix", "main_satfix")):
                acc[k][name].append(r[j])
            if c in dead:
                acc[k]["dead"].append((c, r))
    pct = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0  # noqa: E731
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "positive_close_only": POSITIVE_CLOSE_ONLY, "rule": "R2：可核對日（兩市場官方日檔皆 ok）只留官方有列的價格列；母體需 t0±10 天官方有列；涵蓋判斷式同 coverage_windows._code_window()",
           "zero_requests": True, "returns_computed": False, "n_checkable_days": int(len(chk)),
           "peak_working_set_mb": L.peak_mb(), "windows": {}}
    for k, (a, b) in WINDOWS.items():
        v = acc[k]
        du = [x[1] for x in v["dead"]]
        out["windows"][k] = {
            "t0": a, "end": b, "n_universe_t0": len(v["universe"]), "n_delisted_in_universe": len(du),
            "orig_universe": pct(v["orig"]), "orig_delisted": pct([x[0] for x in du]),
            "main_universe": pct(v["main"]), "main_delisted": pct([x[1] for x in du]),
            "orig_satfix_universe": pct(v["orig_satfix"]), "orig_satfix_delisted": pct([x[2] for x in du]),
            "main_satfix_universe": pct(v["main_satfix"]), "main_satfix_delisted": pct([x[3] for x in du]),
            "main_satfix_meets_95": bool(pct(v["main_satfix"]) >= 0.95 and pct([x[3] for x in du]) >= 0.95),
            "delisted_not_covered_main_satfix": [c for c, r in v["dead"] if not r[3]],
            "n_excluded_not_official_near_t0": len(v["excluded_not_official_near_t0"]), "n_rows_dropped_in_window": v["dropped_rows"],
            "excluded_not_official_near_t0": v["excluded_not_official_near_t0"],
            "universe": v["universe"],
        }
        print(k, json.dumps({kk: vv for kk, vv in out["windows"][k].items() if kk not in ("universe", "excluded_not_official_near_t0")},
                            ensure_ascii=False), flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"峰值工作集 {L.peak_mb()} MB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
