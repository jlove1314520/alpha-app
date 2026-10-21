"""先.一三〇-3 ①：V1 涵蓋率不足的逐檔診斷（零請求，只讀本機 FinMind 快取與官方上市日期快取）。

沿用 `var1018_v1_prep.py` 的母體與涵蓋定義（不改定義、不改門檻），把「在 t0 母體但未涵蓋」的股票逐檔分類：
- 尾端早停：最後一筆價格比 min(下市日, 2014-12-31) 早超過 20 天（下市前斷）；
- 中段缺口：相鄰價格列之間缺口 > 10 個交易日（以平日計，含國定假日，與原定義相同）；
- 兩者皆有。
另外列「前段缺」：候選（官方上市／上櫃日或成立日 ≤ 2007-01-02、或期間下市）但 2007-01-02 前後 10 天沒有價格、
因而根本沒進 t0 母體的股票（不在涵蓋率分母裡，但代表母體本身可能漏人）。
每一類按年（缺口起始年／最後價格年）、按板別（上市／上櫃／未知）列表，並列出每段缺口的起訖日（給 ② 用官方全市場日檔補）。
輸出：research/data/var1018_v1_gap_diagnosis.json（本機，research/data 已 gitignore 的部分不進 repo；摘要寫 PROGRESS）。
用法：python research/var1018_v1_gap_diagnosis.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

import finmind_client as F
import var1018_v1_prep as V

OUT = V.D / "var1018_v1_gap_diagnosis.json"


def board_map() -> dict[str, str]:
    """代號 → 上市／上櫃／興櫃。官方基本資料快取優先，其次 FinMind TaiwanStockInfo 快取（下市股多半只在這裡）。"""
    out: dict[str, str] = {}
    for p in sorted(V.RAW.glob("TaiwanStockInfo__ALL__*.parquet")):
        d = pd.read_parquet(p)
        for sid, t in zip(d["stock_id"], d["type"]):
            out.setdefault(str(sid), {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}.get(str(t), str(t)))
    for k, name in (("L", "上市"), ("O", "上櫃")):
        cache = V.RAW / f"official_basic_{k}_20261018.json"
        if not cache.exists():
            continue
        cf = V.OFFICIAL[k][1]
        for row in json.loads(cache.read_text(encoding="utf-8")):
            code = str(row.get(cf) or "").strip()
            if code:
                out[code] = name
    return out


def gaps_of(tt: pd.Series) -> list[tuple[str, str, int]]:
    """相鄰價格列之間 > MAX_GAP_TD 個平日的缺口：(前一筆日期, 下一筆日期, 缺口平日數)。"""
    if len(tt) < 2:
        return []
    bd = pd.bdate_range(tt.iloc[0], tt.iloc[-1])
    pos = pd.Series(range(len(bd)), index=bd).reindex(tt.values)
    diff = pos.diff()
    out = []
    for i in range(1, len(tt)):
        g = diff.iloc[i]
        if pd.notna(g) and g > V.MAX_GAP_TD:
            out.append((tt.iloc[i - 1].date().isoformat(), tt.iloc[i].date().isoformat(), int(g)))
    return out


def main() -> int:
    cands, dead = V.candidates()  # 只讀快取（官方日期快取已存在則零請求）
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    boards = board_map()
    rows, front_missing = [], []
    n_universe = n_cov = 0
    for c in cands:
        if c == "0050":
            continue
        if not V.cached("TaiwanStockPrice", c):
            front_missing.append({"code": c, "reason": "無價格快取", "board": boards.get(c, "未知"), "delisted": c in dead})
            continue
        d = F.load_dev("TaiwanStockPrice", c, V.FETCH_START, V.FETCH_END)
        t = pd.to_datetime(d["date"]) if not d.empty else pd.Series([], dtype="datetime64[ns]")
        t = t[(t >= V.T0 - pd.Timedelta(days=10)) & (t <= V.END)].sort_values().reset_index(drop=True)
        if t.empty or t.iloc[0] > V.T0 + pd.Timedelta(days=10):
            first = None if d.empty else str(pd.to_datetime(d["date"]).min().date())
            front_missing.append({"code": c, "reason": "FinMind 價格起點晚於 2007-01-12" if first else "FinMind 回空表",
                                  "first_price": first, "board": boards.get(c, "未知"), "delisted": c in dead,
                                  "delist_date": str(ddate[c].date()) if c in ddate else None})
            continue
        n_universe += 1
        end = min(ddate.get(c, V.END), V.END)
        tt = t[t <= end].reset_index(drop=True)
        tail_days = int((end - tt.iloc[-1]).days)
        gl = gaps_of(tt)
        tail_bad, mid_bad = tail_days > 20, bool(gl)
        if not tail_bad and not mid_bad:
            n_cov += 1
            continue
        kind = "兩者皆有" if tail_bad and mid_bad else ("尾端早停" if tail_bad else "中段缺口")
        rows.append({"code": c, "kind": kind, "board": boards.get(c, "未知"), "delisted": c in dead,
                     "delist_date": str(ddate[c].date()) if c in ddate else None,
                     "last_price": str(tt.iloc[-1].date()), "tail_days": tail_days,
                     "gaps": gl, "max_gap_td": max((g[2] for g in gl), default=0)})
    # 分類統計
    by_kind = Counter(r["kind"] for r in rows)
    by_board = defaultdict(Counter)
    by_year = defaultdict(Counter)
    for r in rows:
        by_board[r["kind"]][r["board"]] += 1
        if r["kind"] in ("尾端早停", "兩者皆有"):
            by_year["尾端早停（最後價格年）"][r["last_price"][:4]] += 1
        for g in r["gaps"]:
            by_year["中段缺口（缺口起始年，按段計）"][g[0][:4]] += 1
    gap_len = Counter()
    for r in rows:
        for g in r["gaps"]:
            gap_len["11～20" if g[2] <= 20 else "21～60" if g[2] <= 60 else "61～250" if g[2] <= 250 else ">250"] += 1
    # 補缺口需要的交易日（② 用）：所有缺口段內的平日聯集，及尾端早停段
    need_days: set[str] = set()
    for r in rows:
        for a, b, _ in r["gaps"]:
            need_days.update(x.date().isoformat() for x in pd.bdate_range(pd.Timestamp(a) + pd.Timedelta(days=1), pd.Timestamp(b) - pd.Timedelta(days=1)))
        if r["tail_days"] > 20:
            end = pd.Timestamp(r["delist_date"]) if r["delist_date"] and pd.Timestamp(r["delist_date"]) <= V.END else V.END
            need_days.update(x.date().isoformat() for x in pd.bdate_range(pd.Timestamp(r["last_price"]) + pd.Timedelta(days=1), end))
    out = {
        "generated_from": "var1018_v1_prep 同一母體／涵蓋定義，零請求",
        "n_universe_t0": n_universe, "n_covered": n_cov, "n_uncovered": len(rows),
        "universe_coverage": round(n_cov / n_universe, 4) if n_universe else None,
        "uncovered_by_kind": dict(by_kind),
        "uncovered_by_kind_board": {k: dict(v) for k, v in by_board.items()},
        "uncovered_by_year": {k: dict(sorted(v.items())) for k, v in by_year.items()},
        "mid_gap_length_td": dict(gap_len),
        "uncovered_delisted": sum(r["delisted"] for r in rows),
        "front_missing_n": len(front_missing),
        "front_missing_by_reason": dict(Counter(f["reason"] for f in front_missing)),
        "front_missing_by_board": dict(Counter(f["board"] for f in front_missing)),
        "front_missing_delisted": sum(f["delisted"] for f in front_missing),
        "weekdays_to_fill_n": len(need_days),
        "weekdays_to_fill_by_year": dict(sorted(Counter(x[:4] for x in need_days).items())),
        "uncovered": rows, "front_missing": front_missing,
        "weekdays_to_fill": sorted(need_days),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("uncovered", "front_missing", "weekdays_to_fill")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
