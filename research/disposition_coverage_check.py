"""先.一三二-4：處置股反彈草稿（docs/PREREG_DRAFT_DISPOSITION_RELEASE_REBOUND.md §1.1）涵蓋率前置檢查。

只算涵蓋率、不算報酬：只看「某一天有沒有收盤價（>0）」，不讀價格高低、不算任何價格變化。
零外部請求、不登記試驗、不讀 holdout（價格日期一律截在 validation.holdout.VAL_END＝2024-12-31）。

事件（照草稿 §2）：
- 上市 research/data/disposal_history_twse.json、上櫃 disposal_history_tpex.json；
- 普通股：4 碼數字、非 0 開頭、排除 91 開頭；
- 以（公布日期、代號、處置起迄）去重；同一檔處置期間重疊或首尾相接（下一段起日 ≤ 上一段迄日的下一個交易日）合併，解除日取最後一段迄日；
- 只留解除日 r 落在 2008-01-01～2024-12-31 的事件。

涵蓋（逐事件）：窗口＝處置起日前一交易日 ～ r 之後第 21 個交易日（草稿 r+1 進場、持有 20 日出場；[自行裁量] 比條目寫的「解除後 20 交易日」多一天，讓出場日也被檢查，偏嚴）。
- 嚴格版（主判定）：窗口內每一個交易日都有收盤；若窗口內下市（FinMind TaiwanStockDelisting 日期），只檢查到下市日前一交易日（草稿規則：下市無後續價以 −100% 計，不需要價格）。
- 窗口跨進 2025（holdout）的事件：不讀 2025 價格，只檢查到 2024-12-31，另計數 window_crosses_holdout（草稿待修點，交 Cowork）。
- 另報：關鍵點版（只要求 起日前一日、r、r+1、出場日 四點有收盤），與窗口前 20 交易日（流動性門檻用）收盤齊全率，皆只供參考。
價格來源＝FinMind 研究快取 research/data/raw/TaiwanStockPrice__{代號}__*.parquet（所有起迄版本取聯集）
∪ V1 官方日檔 research/data/v1_official_daily/{twse,tpex}/（收盤為數字者）∪ tpex_stock/（2007 上半年逐檔×月）。
交易日曆＝FinMind 2330／1101／2317 價格日期聯集（2008～2024 這三檔皆在市）。
輸出 research/data/disposition_coverage_check.json（research/data 已 gitignore 的話只在本機）。
用法：python research/disposition_coverage_check.py
"""
from __future__ import annotations

import json
import re
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

from validation.holdout import VAL_END

D = Path(__file__).parent / "data"
RAW = D / "raw"
OFF = D / "v1_official_daily"
OUT = D / "disposition_coverage_check.json"
R_START, R_END = pd.Timestamp("2008-01-01"), pd.Timestamp("2024-12-31")
CAP = pd.Timestamp(VAL_END)
H_EXIT = 21  # r 之後第 21 個交易日＝r+1 進場、持有 20 日的出場日
PRE_LIQ = 20


def roc(s: str) -> pd.Timestamp | None:
    m = re.match(r"^\s*(\d{2,3})/(\d{1,2})/(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return pd.Timestamp(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def common_stock(code: str) -> bool:
    return bool(re.fullmatch(r"[1-9]\d{3}", code)) and not code.startswith("91")


def raw_rows() -> tuple[list[dict], Counter]:
    bad = Counter()
    out = []
    for mkt, period_col in (("twse", "處置起迄時間"), ("tpex", "處置起訖時間")):
        j = json.loads((D / f"disposal_history_{mkt}.json").read_text(encoding="utf-8"))
        for y in j["years"].values():
            f = y["fields"]
            ic, ip, ia = f.index("證券代號"), f.index(period_col), f.index("公布日期")
            for r in y["data"]:
                code = str(r[ic] or "").strip()
                if not code:
                    continue
                if not common_stock(code):
                    bad[f"{mkt}_not_common_stock"] += 1
                    continue
                parts = re.split(r"[～~]", str(r[ip]))
                s, e = (roc(parts[0]), roc(parts[1])) if len(parts) == 2 else (None, None)
                if s is None or e is None or e < s:
                    bad[f"{mkt}_period_unparsable"] += 1
                    continue
                out.append({"mkt": mkt, "code": code, "ann": str(r[ia]).strip(), "start": s, "end": e})
    return out, bad


def calendar() -> list[pd.Timestamp]:
    days: set = set()
    for c in ("2330", "1101", "2317"):
        for p in RAW.glob(f"TaiwanStockPrice__{c}__*.parquet"):
            d = pd.read_parquet(p)
            if "date" in d:
                days |= set(pd.to_datetime(d["date"]))
    return sorted(d for d in days if pd.Timestamp("2007-01-01") <= d <= CAP)


def merge_events(rows: list[dict], cal: list[pd.Timestamp]) -> tuple[list[dict], int]:
    seen, uniq = set(), []
    for r in rows:
        k = (r["ann"], r["code"], r["start"], r["end"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    n_dedup = len(uniq)
    by = defaultdict(list)
    for r in uniq:
        by[(r["mkt"], r["code"])].append(r)
    ev = []
    for (mkt, code), rs in by.items():
        rs.sort(key=lambda x: (x["start"], x["end"]))
        cur = None
        for r in rs:
            if cur is not None:
                i = bisect_left(cal, cur["end"])
                nxt = cal[i + 1] if i + 1 < len(cal) and cal[i] == cur["end"] else (cal[i] if i < len(cal) else cur["end"])
                if r["start"] <= nxt:
                    cur["end"] = max(cur["end"], r["end"])
                    cur["n_segments"] += 1
                    continue
                ev.append(cur)
            cur = {"mkt": mkt, "code": code, "start": r["start"], "end": r["end"], "n_segments": 1}
        ev.append(cur)
    return ev, n_dedup


def price_days(codes: set[str]) -> tuple[dict[str, set], Counter]:
    idx: dict[str, set] = defaultdict(set)
    src = Counter()
    for c in codes:
        for p in RAW.glob(f"TaiwanStockPrice__{c}__*.parquet"):
            d = pd.read_parquet(p)
            if d.empty or "date" not in d or "close" not in d:
                src["finmind_files_empty"] += 1
                continue
            d = d[pd.to_numeric(d["close"], errors="coerce") > 0]
            t = pd.to_datetime(d["date"])
            idx[c] |= set(t[t <= CAP])
            src["finmind_files"] += 1
    for s in ("twse", "tpex"):
        for p in sorted((OFF / s).glob("*.json")):
            j = json.loads(p.read_text(encoding="utf-8"))
            ts = pd.Timestamp(j["date"])
            if ts > CAP:
                continue
            src[f"official_{s}_files"] += 1
            for code, row in (j.get("rows") or {}).items():
                if code in codes and row[3] is not None:
                    idx[code].add(ts)
    for p in sorted((OFF / "tpex_stock").glob("*/*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        if j.get("code") not in codes:
            continue
        src["official_tpex_stock_files"] += 1
        for day, row in (j.get("rows") or {}).items():
            if row[3] is not None:
                idx[j["code"]].add(pd.Timestamp(day))
    return idx, src


def main() -> int:
    t_start = datetime.now()
    rows, bad = raw_rows()
    cal = calendar()
    ev, n_dedup = merge_events(rows, cal)
    ev = [e for e in ev if R_START <= e["end"] <= R_END]
    dl = pd.read_parquet(RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"].astype(str), dl["date"]))
    px, src = price_days({e["code"] for e in ev})
    pos = {d: i for i, d in enumerate(cal)}

    def nth_after(d, n):
        i = bisect_left(cal, d)
        if i < len(cal) and cal[i] == d:
            i += n
        else:
            i += n - 1
        return i  # 可能 ≥ len(cal)（跨進 holdout）

    recs = []
    for e in ev:
        i0 = bisect_left(cal, e["start"]) - 1  # 處置起日前一交易日
        if i0 < 0:
            continue
        ir = bisect_left(cal, e["end"])
        if ir >= len(cal) or cal[ir] != e["end"]:
            ir = min(ir, len(cal) - 1)  # 解除日非交易日時取下一交易日
        ix = nth_after(cal[ir], H_EXIT)
        crosses = ix >= len(cal)
        d_dl = ddate.get(e["code"])
        delisted_3y = d_dl is not None and e["end"] < d_dl <= e["end"] + pd.DateOffset(years=3)
        hi = min(ix, len(cal) - 1)
        if d_dl is not None and cal[i0] < d_dl <= cal[hi]:
            hi = bisect_left(cal, d_dl) - 1
        win = cal[i0:hi + 1]
        have = px.get(e["code"], set())
        miss = [d for d in win if d not in have]
        keys = [cal[i0], cal[ir]] + ([cal[ir + 1]] if ir + 1 < len(cal) else []) + ([cal[ix]] if not crosses else [])
        if d_dl is not None:
            keys = [k for k in keys if k < d_dl]
        pre = cal[max(0, i0 - PRE_LIQ + 1):i0 + 1]
        recs.append({"mkt": e["mkt"], "code": e["code"], "start": str(e["start"].date()), "release": str(e["end"].date()),
                     "year": e["end"].year, "n_segments": e["n_segments"], "delisted_within_3y": bool(delisted_3y),
                     "window_crosses_holdout": crosses, "n_window_days": len(win), "n_missing": len(miss),
                     "covered": len(miss) == 0, "key_points_covered": all(k in have for k in keys),
                     "pre20_covered": all(d in have for d in pre), "no_price_at_all": not have,
                     "first_missing": str(miss[0].date()) if miss else None})

    def rate(xs, k="covered"):
        return round(sum(x[k] for x in xs) / len(xs), 4) if xs else None

    def grp(key):
        g = defaultdict(list)
        for r in recs:
            g[key(r)].append(r)
        return {str(k): {"n": len(v), "covered": rate(v), "delisted_3y_n": sum(x["delisted_within_3y"] for x in v),
                         "delisted_3y_covered": rate([x for x in v if x["delisted_within_3y"]])} for k, v in sorted(g.items())}

    dead = [r for r in recs if r["delisted_within_3y"]]
    cov, dcov = rate(recs), rate(dead)
    ok = cov is not None and dcov is not None and cov >= 0.95 and dcov >= 0.90
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "item": "先.一三二-4", "draft": "docs/PREREG_DRAFT_DISPOSITION_RELEASE_REBOUND.md §1.1",
           "external_requests": 0, "returns_computed": False, "trial_registered": False, "price_cap": VAL_END,
           "raw_rows_common_stock": len(rows), "skipped_rows": dict(bad), "after_dedup_rows": n_dedup,
           "n_events": len(recs), "n_events_by_mkt": dict(Counter(r["mkt"] for r in recs)),
           "event_coverage_strict": cov, "n_delisted_within_3y": len(dead), "delisted_3y_coverage_strict": dcov,
           "threshold": {"event": 0.95, "delisted_3y": 0.90}, "precondition_met": ok,
           "key_points_coverage": rate(recs, "key_points_covered"),
           "delisted_3y_key_points_coverage": rate(dead, "key_points_covered"),
           "pre20_coverage": rate(recs, "pre20_covered"),
           "n_no_price_at_all": sum(r["no_price_at_all"] for r in recs),
           "n_window_crosses_holdout": sum(r["window_crosses_holdout"] for r in recs),
           "by_mkt": grp(lambda r: r["mkt"]), "by_year": grp(lambda r: r["year"]),
           "by_mkt_year": grp(lambda r: f"{r['mkt']}_{r['year']}"),
           "uncovered_breakdown": {m: dict(Counter(
               ("whole_window_missing" if r["n_missing"] == r["n_window_days"] else
                "missing_1_2_days" if r["n_missing"] <= 2 else "missing_3plus_days")
               for r in recs if r["mkt"] == m and not r["covered"])) for m in ("twse", "tpex")},
           "price_sources": dict(src),
           "definition": "嚴格版＝處置起日前一交易日～r後第21交易日每個交易日都有收盤(>0)；窗口內下市只查到下市前一日；不讀2025價格",
           "uncovered_examples": [r for r in recs if not r["covered"]][:60],
           "elapsed_sec": round((datetime.now() - t_start).total_seconds(), 1)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: v for k, v in out.items() if k not in ("by_mkt_year", "uncovered_examples")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
