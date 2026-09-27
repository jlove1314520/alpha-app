# -*- coding: utf-8 -*-
"""查.二 第一、二點（查證段，唯讀）：選股宇宙是否混入「上市前興櫃期間」。

**只讀既有快取，零新API呼叫、不新增爬取來源**（裁示原文）。上市日來源＝
`research/data/twse_listing_dates.json`（TWSE t187ap03_L，#46時期已存的既有
檔案，只涵蓋「現存TWSE上市公司」）；TPEx／興櫃／已下市公司沒有上市日，
如實標「上市日不明」，不猜測。這是資料源本身的缺口，不是查證偷懶。

異常＝**原始收盤價**(raw close)單日變動超過日期相依門檻
（2015-06-01前±7.5%、之後±10.5%）。歸類：
  (c) 除權息／分割／減資／面額變更事件日（用快取的TaiwanStockDividend／
      SplitPrice／CapitalReductionReferencePrice／ParValueChange日期比對）
  (a) 上市日已知，且異常日 < 上市日
  (b) 上市日已知，且異常日在上市後前5個交易日內
  (u) 上市日不明（TPEx/興櫃/下市），且不是(c)——無法在既有來源內判定(a)/(b)/(d)
  (d) 上市日已知，異常日在上市5日之後，且非(c)——其他

輸出：research/data/q2_ipo_pre_listing_contamination.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from pathlib import Path

import pandas as pd

import holdout_2025_dividend_account_test as h1
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from universe import classify_security

RAW = Path(__file__).parent / "data" / "raw"
OUT = Path(__file__).parent / "data" / "q2_ipo_pre_listing_contamination.json"
LISTING = json.loads((Path(__file__).parent / "data" / "twse_listing_dates.json").read_text(encoding="utf-8"))["listing_dates"]
REGIME_CUT = "2015-06-01"


def thr(date: str) -> float:
    return 7.5 if date < REGIME_CUT else 10.5


def raw_price(sid: str) -> pd.DataFrame:
    """合併該檔所有已快取的TaiwanStockPrice檔（只讀，不呼叫API）。"""
    fs = sorted(RAW.glob(f"TaiwanStockPrice__{sid}__*.parquet"))
    if not fs:
        return pd.DataFrame(columns=["date", "close"])
    parts = [x for x in (pd.read_parquet(f) for f in fs) if "date" in x.columns and "close" in x.columns]
    if not parts:
        return pd.DataFrame(columns=["date", "close"])
    d = pd.concat(parts, ignore_index=True)
    d["date"] = d["date"].astype(str)
    d = d.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)
    return d[d["close"] > 0].reset_index(drop=True)


def event_dates(sid: str) -> set[str]:
    out: set[str] = set()
    for ds, cols in (("TaiwanStockDividend", ["StockExDividendTradingDate", "CashExDividendTradingDate"]),
                     ("TaiwanStockSplitPrice", ["date"]),
                     ("TaiwanStockCapitalReductionReferencePrice", ["date"]),
                     ("TaiwanStockParValueChange", ["date"])):
        for f in RAW.glob(f"{ds}__{sid}__*.parquet"):
            try:
                x = pd.read_parquet(f)
            except Exception:  # noqa: BLE001
                continue
            for c in cols:
                if c in x.columns:
                    out.update(str(v)[:10] for v in x[c].dropna() if str(v) not in ("", "None", "NaT"))
    # ParValueChange是ALL檔，另外處理
    for f in RAW.glob("TaiwanStockParValueChange__ALL__*.parquet"):
        x = pd.read_parquet(f)
        x = x[x["stock_id"].astype(str) == sid]
        out.update(str(v)[:10] for v in x["date"])
    return out


def scan(sids: list[str], lo: str, hi: str) -> tuple[list[dict], dict]:
    hits = []
    n_known = 0
    for sid in sids:
        d = raw_price(sid)
        d = d[(d["date"] >= lo) & (d["date"] <= hi)].reset_index(drop=True)
        if len(d) < 6:
            continue
        ld = LISTING.get(sid)
        list_date = f"{ld[:4]}-{ld[4:6]}-{ld[6:]}" if ld else None
        if list_date:
            n_known += 1
        ev = event_dates(sid)
        ret = d["close"].pct_change() * 100
        for i in range(1, len(d)):
            dt = d.loc[i, "date"]
            r = ret.iloc[i]
            if pd.isna(r) or abs(r) <= thr(dt):
                continue
            if dt in ev or any(dt == e for e in ev):
                cat = "(c)除權息/分割/減資/面額變更事件日"
            elif list_date is None:
                cat = "(u)上市日不明，無法判定"
            elif dt < list_date:
                cat = "(a)上市前興櫃期間"
            else:
                # 上市後第幾個交易日
                k = int((d["date"] >= list_date).values[:i + 1].sum())
                cat = "(b)上市後前5個交易日" if k <= 5 else "(d)其他"
            hits.append({"stock_id": sid, "date": dt, "ret_pct": round(float(r), 2),
                         "threshold": thr(dt), "category": cat, "series_start": d.loc[0, "date"],
                         "listing_date": list_date})
    return hits, {"stocks_scanned": len(sids), "stocks_with_listing_date": n_known}


def summarize(hits: list[dict]) -> dict:
    df = pd.DataFrame(hits)
    if df.empty:
        return {}
    return {"by_category": df["category"].value_counts().to_dict(),
            "top_stocks": df["stock_id"].value_counts().head(10).to_dict()}


def main() -> None:
    info = h1._info_lookup()
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    common = [s for s in sample_ids
              if classify_security(s, (info.get(s) or {}).get("stock_name"),
                                   (info.get(s) or {}).get("industry_category")) == "普通股"]
    print(f"抽樣{len(sample_ids)}→普通股{len(common)}", flush=True)

    # 兩個宇宙（近似重建：與H.一/考.一同一抽樣種子，「≥200列」以原始價快取為準）
    def usable(lo: str, hi: str) -> list[str]:
        out = []
        for s in common:
            d = raw_price(s)
            if len(d[(d["date"] >= lo) & (d["date"] <= hi)]) >= 200:
                out.append(s)
        return out

    u_old = usable("2007-01-01", "2014-12-31")
    u_hold = usable("2025-01-01", "2026-09-24")
    print(f"2007-2014可用{len(u_old)}檔（原判定208）、holdout可用{len(u_hold)}檔（原判定214）", flush=True)

    res = {"generated_at": pd.Timestamp.now().isoformat(),
           "note": "近似重建宇宙；上市日僅TWSE現存公司；零API呼叫",
           "info_type_counts_for_common": pd.Series(
               [ (pd.read_parquet(next(RAW.glob('TaiwanStockInfo__ALL__2000-01-01__latest.parquet'))).drop_duplicates('stock_id',keep='last').set_index('stock_id')['type'].get(s)) for s in common]
           ).value_counts(dropna=False).to_dict()}
    for name, sids, lo, hi in (("universe_2007_2014", u_old, "2007-01-01", "2014-12-31"),
                                ("universe_holdout", u_hold, "2025-01-01", "2026-09-24")):
        hits, meta = scan(sids, lo, hi)
        res[name] = {**meta, "n_hits_date_dependent_threshold": len(hits), **summarize(hits), "hits": hits}
        print(name, meta, len(hits), summarize(hits), flush=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("已寫入", OUT)


if __name__ == "__main__":
    main()
