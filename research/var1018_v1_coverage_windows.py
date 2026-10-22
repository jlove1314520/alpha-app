# -*- coding: utf-8 -*-
"""先.一三〇-3／收件匣 017 ②④（2026-10-22）：各窗口的時點宇宙涵蓋率（零請求、只讀本機快取、不算任何報酬）。

定義全部沿用 var1018_v1_coverage_recompute.coverage_merged()（母體＝候選中 t0 前後 10 天有價格列者；涵蓋＝t0 到
min(下市日, 窗口終點) 最後一筆價格距離終點 ≤20 天，且相鄰價格列缺口 ≤10 個交易日），只換窗口 t0／終點，並列兩種缺口定義：
- 原定義：任何缺口都算；
- 主定義（Cowork 017 審查①）：缺口內每個營業日都是「官方確認停牌」（全市場日檔兩邊都有、這檔沒列；
  var1018_v1_halt_check.classify_interval()＝official_absent）或休市 → 不算缺口。
窗口：V1 原 t0 2007-01-02、R1-b t0 2007-07-02（到 2014-12-31）、個股網格 2007-01-02～2009-12-31、ML 價量 2006-01-02～2012-12-31。
⚠️ 官方日檔 TWSE 從 2006-12-26、上櫃從 2007-07 起才有；ML 窗口 2006 年那段只靠 FinMind，官方停牌無法佐證（照原定義算缺口）。

先.一三二-2（2026-10-23）改低記憶體：官方日檔改用 var1018_v1_lowmem 精簡索引（每檔只讀一次、不快取整日 rows），
每個代號的 FinMind parquet 只讀一次、四個窗口一起算；舊版被系統以記憶體不足中止兩次。判斷式不變。

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

import numpy as np
import pandas as pd

import finmind_client as F
import var1018_v1_lowmem as L
import var1018_v1_prep as V

OUT = Path(__file__).parent / "data" / "var1018_v1_coverage_windows.json"
WINDOWS = {
    "V1_t0_20070102": ("2007-01-02", "2014-12-31"),
    "V1_R1b_t0_20070702": ("2007-07-02", "2014-12-31"),
    "GRID_2007_2009": ("2007-01-02", "2009-12-31"),
    "ML_2006_2012": ("2006-01-02", "2012-12-31"),
}


def _code_window(t_all: pd.Series, c: str, t0: pd.Timestamp, end_w: pd.Timestamp, ddate: dict, idx: dict):
    """單一代號、單一窗口：回傳 None（不在母體）或 (orig_ok, main_ok)。判斷式與舊版 coverage_window() 逐行相同。"""
    t = t_all[(t_all >= t0 - pd.Timedelta(days=10)) & (t_all <= end_w)].reset_index(drop=True)
    if t.empty or t.iloc[0] > t0 + pd.Timedelta(days=10):
        return None
    end = min(ddate.get(c, end_w), end_w)
    tt = t[t <= end].reset_index(drop=True)
    if tt.empty:
        return "universe_only"
    tail_ok = (end - tt.iloc[-1]).days <= 20
    bd = pd.bdate_range(tt.iloc[0], tt.iloc[-1])
    pos = pd.Series(range(len(bd)), index=bd).reindex(tt.values).to_numpy()
    gaps = pd.Series(pos).diff().to_numpy() if len(tt) > 1 else []
    big = [i for i, g in enumerate(gaps) if i > 0 and g > V.MAX_GAP_TD]
    orig_ok = tail_ok and not big
    main_big = [i for i in big if L.classify_interval(c, tt.iloc[i - 1], tt.iloc[i], idx) != "official_absent"]
    # 週六補班修正版（先.一三二-2 發現）：上面 reindex 對週六交易日（例 2007-03-03）給 NaN，跨過它的缺口被當成沒缺口。
    # 這裡改用 var1018_v1_halt_check 同一式 len(bdate_range(a, b)) − 1（＝busday_count(a, b+1) − 1）計缺口，並列輸出，不取代舊欄位。
    dn = tt.to_numpy().astype("datetime64[D]")
    fix = (np.busday_count(dn[:-1], dn[1:] + np.timedelta64(1, "D")) - 1) if len(dn) > 1 else np.array([])
    big_fix = [i + 1 for i, g in enumerate(fix) if g > V.MAX_GAP_TD]
    main_big_fix = [i for i in big_fix if L.classify_interval(c, tt.iloc[i - 1], tt.iloc[i], idx) != "official_absent"]
    return orig_ok, tail_ok and not main_big, tail_ok and not big_fix, tail_ok and not main_big_fix


def coverage_all(cands, dead, idx: dict, ddate: dict) -> dict:
    """先.一三二-2：每個代號的 FinMind parquet 只讀一次（舊版每個窗口重讀一次），四個窗口一起算，讀完即丟。"""
    acc = {k: {"universe": 0, "orig": [], "main": [], "orig_satfix": [], "main_satfix": [], "dead": []} for k in WINDOWS}
    off = idx["official"]
    for c in cands:
        if c == "0050":
            continue
        arr = off.get(c, np.array([], dtype="datetime64[D]"))
        if V.cached("TaiwanStockPrice", c):
            d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
            if not d.empty:
                arr = np.union1d(arr, pd.to_datetime(d["date"]).to_numpy().astype("datetime64[D]"))
            del d
        if len(arr) == 0:
            continue
        t_all = pd.Series(pd.to_datetime(np.unique(arr)))
        for k, (a, b) in WINDOWS.items():
            r = _code_window(t_all, c, pd.Timestamp(a), pd.Timestamp(b), ddate, idx)
            if r is None:
                continue
            acc[k]["universe"] += 1
            if r == "universe_only":
                continue
            for j, name in enumerate(("orig", "main", "orig_satfix", "main_satfix")):
                acc[k][name].append(r[j])
            if c in dead:
                acc[k]["dead"].append(r)
    pct = lambda xs: round(sum(xs) / len(xs), 4) if xs else 0.0  # noqa: E731
    out = {}
    for k, v in acc.items():
        du = v["dead"]
        out[k] = {"n_universe_t0": v["universe"], "n_delisted_in_universe": len(du),
                  "orig_universe": pct(v["orig"]), "orig_delisted": pct([x[0] for x in du]),
                  "main_universe": pct(v["main"]), "main_delisted": pct([x[1] for x in du]),
                  "main_meets_95": bool(pct(v["main"]) >= 0.95 and pct([x[1] for x in du]) >= 0.95),
                  "orig_satfix_universe": pct(v["orig_satfix"]), "orig_satfix_delisted": pct([x[2] for x in du]),
                  "main_satfix_universe": pct(v["main_satfix"]), "main_satfix_delisted": pct([x[3] for x in du]),
                  "main_satfix_meets_95": bool(pct(v["main_satfix"]) >= 0.95 and pct([x[3] for x in du]) >= 0.95)}
    return out


def main() -> int:
    cands, dead = V.candidates()
    idx = L.build_index()
    print(f"官方精簡索引建好：{len(idx['day_status'])} 天、{len(idx['official'])} 檔；峰值 {L.peak_mb()} MB", flush=True)
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    del dl
    res = coverage_all(cands, dead, idx, ddate)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "rule": "定義沿用 coverage_merged()；main＝官方確認停牌缺口不算缺口（Cowork 017 審查①）；零請求、未算報酬",
           "satfix_note": "*_satfix＝缺口改用 len(bdate_range(a,b))−1 計（舊式 reindex 遇週六補班交易日給 NaN、跨過它的缺口被略過）；"
                          "先.一三二-2 發現、非 PREREG 定義，要採用哪一組須 Cowork 審",
           "peak_working_set_mb": L.peak_mb(), "windows": {}}
    for k, (a, b) in WINDOWS.items():
        out["windows"][k] = {"t0": a, "end": b, **res[k]}
        print(k, json.dumps(out["windows"][k], ensure_ascii=False), flush=True)
    print(f"峰值工作集 {out['peak_working_set_mb']} MB", flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
