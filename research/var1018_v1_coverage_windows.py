# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 017 ②④（2026-10-22）：各窗口的時點宇宙涵蓋率（零請求、只讀本機快取、不算任何報酬）。

定義全部沿用 var1018_v1_coverage_recompute.coverage_merged()（母體＝候選中 t0 前後 10 天有價格列者；涵蓋＝t0 到
min(下市日, 窗口終點) 最後一筆價格距離終點 ≤20 天，且相鄰價格列缺口 ≤10 個交易日），只換窗口 t0／終點，並列兩種缺口定義：
- 原定義：任何缺口都算；
- 主定義（Cowork 017 審查①）：缺口內每個營業日都是「官方確認停牌」（全市場日檔兩邊都有、這檔沒列；
  var1018_v1_halt_check.classify_interval()＝official_absent）或休市 → 不算缺口。
窗口：V1 原 t0 2007-01-02、R1-b t0 2007-07-02（到 2014-12-31）、個股網格 2007-01-02～2009-12-31、ML 價量 2006-01-02～2012-12-31。
⚠️ 官方日檔 TWSE 從 2006-12-26、上櫃從 2007-07 起才有；ML 窗口 2006 年那段只靠 FinMind，官方停牌無法佐證（照原定義算缺口）。

跑法：cd research && python var1018_v1_coverage_windows.py
輸出：research/data/var1018_v1_coverage_windows.json
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

import pandas as pd

import finmind_client as F
import var1018_v1_coverage_recompute as R
import var1018_v1_halt_check as H
import var1018_v1_prep as V

OUT = Path(__file__).parent / "data" / "var1018_v1_coverage_windows.json"
WINDOWS = {
    "V1_t0_20070102": ("2007-01-02", "2014-12-31"),
    "V1_R1b_t0_20070702": ("2007-07-02", "2014-12-31"),
    "GRID_2007_2009": ("2007-01-02", "2009-12-31"),
    "ML_2006_2012": ("2006-01-02", "2012-12-31"),
}


def coverage_window(cands, dead, off, t0: pd.Timestamp, end_w: pd.Timestamp, ddate: dict, halt_cache: dict) -> dict:
    res = {"orig": [], "main": []}
    universe, dead_u = [], []
    for c in cands:
        if c == "0050":
            continue
        fm = set()
        if V.cached("TaiwanStockPrice", c):
            d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
            if not d.empty:
                fm = set(pd.to_datetime(d["date"]))
        allt = fm | off.get(c, set())
        if not allt:
            continue
        t = pd.Series(sorted(allt))
        t = t[(t >= t0 - pd.Timedelta(days=10)) & (t <= end_w)].reset_index(drop=True)
        if t.empty or t.iloc[0] > t0 + pd.Timedelta(days=10):
            continue
        universe.append(c)
        end = min(ddate.get(c, end_w), end_w)
        tt = t[t <= end].reset_index(drop=True)
        if tt.empty:
            continue
        tail_ok = (end - tt.iloc[-1]).days <= 20
        bd = pd.bdate_range(tt.iloc[0], tt.iloc[-1])
        pos = pd.Series(range(len(bd)), index=bd).reindex(tt.values).to_numpy()
        gaps = pd.Series(pos).diff().to_numpy() if len(tt) > 1 else []
        big = [i for i, g in enumerate(gaps) if i > 0 and g > V.MAX_GAP_TD]
        orig_ok = tail_ok and not big
        main_big = [i for i in big if H.classify_interval(c, tt.iloc[i - 1], tt.iloc[i], halt_cache) != "official_absent"]
        main_ok = tail_ok and not main_big
        res["orig"].append(orig_ok)
        res["main"].append(main_ok)
        if c in dead:
            dead_u.append((orig_ok, main_ok))
    n, nd = len(universe), len(dead_u)
    pct = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0  # noqa: E731
    return {"n_universe_t0": n, "n_delisted_in_universe": nd,
            "orig_universe": pct(res["orig"]), "orig_delisted": pct([a for a, _ in dead_u]),
            "main_universe": pct(res["main"]), "main_delisted": pct([b for _, b in dead_u]),
            "main_meets_95": bool(pct(res["main"]) >= 0.95 and pct([b for _, b in dead_u]) >= 0.95)}


def main() -> int:
    cands, dead = V.candidates()
    off, _st = R.official_index()
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    halt_cache: dict = {}
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "rule": "定義沿用 coverage_merged()；main＝官方確認停牌缺口不算缺口（Cowork 017 審查①）；零請求、未算報酬",
           "windows": {}}
    for k, (a, b) in WINDOWS.items():
        out["windows"][k] = {"t0": a, "end": b, **coverage_window(cands, dead, off, pd.Timestamp(a), pd.Timestamp(b), ddate, halt_cache)}
        print(k, json.dumps(out["windows"][k], ensure_ascii=False), flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
