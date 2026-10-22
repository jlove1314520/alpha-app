"""先.一三〇-3 ③：官方全市場日檔補完後重算 V1 涵蓋率（零請求，只讀本機快取）。

不改母體定義、不改涵蓋定義、不改 95% 門檻——全部沿用 `var1018_v1_prep.coverage()`：
- 母體＝候選（`var1018_v1_prep.candidates()`）中 2007-01-02 前後 10 天有價格列者；
- 涵蓋＝從 t0 到 min(下市日, 2014-12-31)，最後一筆價格距離終點 ≤20 天，且相鄰價格列缺口 ≤10 個交易日（平日計）。
唯一的差別：每檔的「價格日期」＝FinMind 快取日期 ∪ 官方日檔（research/data/v1_official_daily/{twse,tpex}/）
∪ 上櫃逐檔×月（.../tpex_stock/，2007 上半年）裡收盤價是數字的日期。[自行裁量] 官方列收盤為「--」（當天無成交）不算有價格列，與只看有成交價的原定義一致、偏保守。
因為多了資料，原本 2007-01-02 前後沒有 FinMind 價格的候選可能因官方日檔而進入母體（分母會變），兩個數字都列出。

官方日檔還沒抓完時照樣可以跑，輸出標 partial＝true（缺的日期當作沒有資料，涵蓋率只會偏低、不會偏高），
只有 missing＝0 才寫回 shortlist／判 ready_to_register。不讀 holdout（只到 2014-12-31）。
輸出：research/data/var1018_v1_coverage_recompute.json（本機，research/data 已 gitignore）。
用法：python research/var1018_v1_coverage_recompute.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

import finmind_client as F
import var1018_v1_prep as V

OFF = V.D / "v1_official_daily"
DIAG = V.D / "var1018_v1_gap_diagnosis.json"
OUT = V.D / "var1018_v1_coverage_recompute.json"


def official_index() -> tuple[dict[str, set], dict]:
    """代號 → 官方日檔中收盤為數字的日期集合；以及各來源抓取狀態計數（以 ① 診斷的缺口日期為準）。"""
    dates = json.loads(DIAG.read_text(encoding="utf-8"))["weekdays_to_fill"]
    idx: dict[str, set] = defaultdict(set)
    st = {s: {"ok": 0, "no_data": 0, "before_source_start": 0, "missing": 0} for s in ("twse", "tpex")}
    for d in dates:
        for s in ("twse", "tpex"):
            p = OFF / s / f"{d.replace('-', '')}.json"
            if not p.exists():
                st[s]["missing"] += 1
                continue
            j = json.loads(p.read_text(encoding="utf-8"))
            st[s][j["status"]] += 1
            ts = pd.Timestamp(d)
            for code, row in (j.get("rows") or {}).items():
                if row[3] is not None:
                    idx[code].add(ts)
    # ②-b 上櫃 2007 上半年逐檔×月（var1018_v1_tpex_stock_fill.py）
    n_files = 0
    for p in sorted((OFF / "tpex_stock").glob("*/*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        n_files += 1
        for day, row in (j.get("rows") or {}).items():
            if row[3] is not None:
                idx[j["code"]].add(pd.Timestamp(day))
    st["tpex_stock_files"] = n_files
    return idx, st


def tpex_stock_pending() -> int:
    """②-b 還沒抓的（代號, 月）數；B 類 2007-01 探到有資料的，後續月份也算（零請求）。"""
    import var1018_v1_tpex_stock_fill as T
    fixed, probe = T.plan()
    n = sum(1 for x in fixed if not T.cache_path(*x).exists())
    for c in probe:
        p = T.cache_path(c, "200701")
        if not p.exists():
            n += 1
        elif json.loads(p.read_text(encoding="utf-8"))["status"] == "ok":
            n += sum(1 for m in T.MONTHS[2:] if not T.cache_path(c, m).exists())
    return n


def coverage_merged(cands: list[str], dead: set[str], off: dict[str, set]) -> dict:
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    universe, covered, src_added = [], [], 0
    per_year = {y: 0 for y in range(2007, 2015)}
    uncovered = []
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
        t = t[(t >= V.T0 - pd.Timedelta(days=10)) & (t <= V.END)].reset_index(drop=True)
        if t.empty or t.iloc[0] > V.T0 + pd.Timedelta(days=10):
            continue
        universe.append(c)
        fm_t = [x for x in fm if V.T0 - pd.Timedelta(days=10) <= x <= V.T0 + pd.Timedelta(days=10)]
        src_added += int(not fm_t)  # 只因官方日檔才進母體
        end = min(ddate.get(c, V.END), V.END)
        tt = t[t <= end]
        for y in per_year:
            per_year[y] += int((tt.dt.year == y).any())
        bd = pd.bdate_range(tt.iloc[0], tt.iloc[-1])
        gaps = pd.Series(range(len(bd)), index=bd).reindex(tt.values).diff().max() if len(tt) > 1 else 0
        tail_ok = (end - tt.iloc[-1]).days <= 20
        gap_ok = gaps is None or pd.isna(gaps) or gaps <= V.MAX_GAP_TD
        covered.append(tail_ok and gap_ok)
        if not (tail_ok and gap_ok):
            uncovered.append({"code": c, "delisted": c in dead, "last": str(tt.iloc[-1].date()), "end": str(end.date()),
                              "tail_ok": tail_ok, "max_gap_td": None if pd.isna(gaps) else int(gaps)})
    n = len(universe)
    dead_cov = [ok for c, ok in zip(universe, covered) if c in dead]
    uni = sum(covered) / n if n else 0.0
    dr = sum(dead_cov) / len(dead_cov) if dead_cov else 0.0
    return {"n_universe_t0": n, "n_entered_via_official_only": src_added, "n_covered": sum(covered),
            "universe_coverage": round(uni, 4), "n_delisted_in_universe": len(dead_cov),
            "delisted_coverage": round(dr, 4), "per_year_in_market": per_year,
            "meets_95": bool(uni >= 0.95 and dr >= 0.95),
            "uncovered_tail_only": sum(1 for u in uncovered if not u["tail_ok"] and (u["max_gap_td"] or 0) <= V.MAX_GAP_TD),
            "uncovered_gap_only": sum(1 for u in uncovered if u["tail_ok"]),
            "uncovered_both": sum(1 for u in uncovered if not u["tail_ok"] and (u["max_gap_td"] or 0) > V.MAX_GAP_TD),
            "uncovered": uncovered}


def main() -> int:
    cands, dead = V.candidates()
    off, st = official_index()
    res = coverage_merged(cands, dead, off)
    st["tpex_stock_pending"] = tpex_stock_pending()
    partial = any(v["missing"] for v in st.values() if isinstance(v, dict)) or st["tpex_stock_pending"] > 0
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "partial": partial, "official_fetch": st,
           "before_finmind_only": {k: json.loads(DIAG.read_text(encoding="utf-8"))[k]
                                   for k in ("n_universe_t0", "universe_coverage")},
           **res,
           "ready_to_register": bool(res["meets_95"] and not partial),
           "rule": "定義與門檻沿用 var1018_v1_prep.coverage()；partial＝true 時不判定"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=int), encoding="utf-8")
    brief = {k: v for k, v in out.items() if k != "uncovered"}
    print(json.dumps(brief, ensure_ascii=False, indent=1, default=int))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
