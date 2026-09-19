# -*- coding: utf-8 -*-
"""#75續5(a)：DERA 內部人交易批次檔資料品質抽樣＋CIK→ticker→宇宙對應核對。

只做「資料地基核對」，不算 IC、不做任何績效判定、不登記 TRIALS_REGISTRY。
輸出：research/insider_dera_quality_result.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

try:  # 避免 cp950 主控台編碼崩潰（CLAUDE.md 第十二節）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
DERA = HERE / "data" / "dera_insider"
UNIV = HERE / "data" / "us_universe_pit.json"
OUT = HERE / "insider_dera_quality_result.json"
VAL_END = pd.Timestamp("2024-12-31")


def parse_dates(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%d-%b-%Y", errors="coerce")


def main() -> None:
    frames = []
    per_q = {}
    for f in sorted(DERA.glob("*.csv")):
        df = pd.read_csv(f, dtype=str)
        df["q"] = f.stem
        frames.append(df)
        n = len(df)
        fd = parse_dates(df["filing_date"])
        td = parse_dates(df["trans_date"])
        price = pd.to_numeric(df["price"], errors="coerce")
        sh = pd.to_numeric(df["shares"], errors="coerce")
        lag = (fd - td).dt.days
        per_q[f.stem] = {
            "rows": n,
            "filing_date_bad": float(fd.isna().mean()),
            "trans_date_bad": float(td.isna().mean()),
            "ticker_missing": float((df["ticker"].fillna("").str.strip() == "").mean()),
            "price_missing_or_le0": float((price.isna() | (price <= 0)).mean()),
            "shares_missing_or_le0": float((sh.isna() | (sh <= 0)).mean()),
            "lag_negative": float((lag < 0).mean()),
            "lag_gt_30d": float((lag > 30).mean()),
            "acq_disp_bad": float((~df["acq_disp"].isin(["A", "D"])).mean()),
            "max_filing_date": str(fd.max().date()) if fd.notna().any() else None,
        }
    df = pd.concat(frames, ignore_index=True)
    df["fd"] = parse_dates(df["filing_date"])
    df["price_n"] = pd.to_numeric(df["price"], errors="coerce")
    df["shares_n"] = pd.to_numeric(df["shares"], errors="coerce")
    df["cik_i"] = pd.to_numeric(df["issuer_cik"], errors="coerce")

    total = len(df)
    over_val_end = int((df["fd"] > VAL_END).sum())

    # ---- 重複列（同一 accession 多筆完全相同 → 可能是真的分批成交，也可能是修正申報重複）
    dup_full = int(df.duplicated(["accession", "trans_date", "code", "shares", "price", "acq_disp", "owner_cik"]).sum())
    form_counts = df["form"].value_counts().to_dict()  # 4 vs 4/A（修正申報）

    # ---- 極端值
    px = df["price_n"]
    ext = {
        "price_gt_10000": int((px > 10000).sum()),
        "price_lt_0.01_pos": int(((px > 0) & (px < 0.01)).sum()),
        "notional_gt_1e9": int((df["shares_n"] * px > 1e9).sum()),
    }

    # ---- CIK→ticker 一致性
    g = df.dropna(subset=["cik_i"]).groupby("cik_i")["ticker"].agg(lambda s: sorted(set(x for x in s.dropna() if str(x).strip())))
    multi = g[g.map(len) > 1]
    no_tk = g[g.map(len) == 0]

    # ---- 對應宇宙（CIK 級）
    uni = json.loads(UNIV.read_text(encoding="utf-8"))["universe"]
    cik2 = {}
    for tk, v in uni.items():
        cik2.setdefault(int(v["cik"]), []).append((tk, v.get("status")))
    ciks = set(int(c) for c in g.index)
    in_uni = {c for c in ciks if c in cik2}
    rows_in = int(df["cik_i"].isin(in_uni).sum())
    # 名目金額加權覆蓋
    notional = (df["shares_n"] * px).fillna(0)
    cov_notional = float(notional[df["cik_i"].isin(in_uni)].sum() / notional.sum()) if notional.sum() > 0 else None
    # 依申報年覆蓋
    df["yr"] = df["fd"].dt.year
    yr_cov = (df.assign(hit=df["cik_i"].isin(in_uni)).groupby("yr")["hit"].mean().round(4)).to_dict()
    yr_rows = df.groupby("yr").size().to_dict()
    # 未對上宇宙的 CIK 中，資料內 ticker 樣本
    miss = [c for c in ciks if c not in in_uni]
    miss_sample = [(int(c), g[c][:2]) for c in sorted(miss, key=lambda c: -int((df["cik_i"] == c).sum()))[:15]]

    # ---- 宇宙側問題：同 CIK 多 ticker 且狀態互相矛盾（AAPL 被標 delisted 即此類）
    conflict = {c: v for c, v in cik2.items() if len({s for _, s in v}) > 1}

    res = {
        "total_rows": total,
        "rows_filing_after_VAL_END": over_val_end,
        "duplicate_rows_same_key": dup_full,
        "form_counts": form_counts,
        "extreme": ext,
        "issuer_ciks": len(ciks),
        "ciks_with_multiple_tickers": len(multi),
        "ciks_with_no_ticker": len(no_tk),
        "multi_ticker_examples": {str(int(k)): v for k, v in list(multi.items())[:8]},
        "ciks_in_universe": len(in_uni),
        "row_cov_in_universe": rows_in / total,
        "notional_cov_in_universe": cov_notional,
        "row_cov_by_filing_year": {int(k): v for k, v in yr_cov.items() if pd.notna(k)},
        "rows_by_filing_year": {int(k): int(v) for k, v in yr_rows.items() if pd.notna(k)},
        "top_uncovered_ciks_by_rows": miss_sample,
        "universe_ciks_with_conflicting_status": len(conflict),
        "universe_conflict_examples": {str(k): v for k, v in list(conflict.items())[:6]},
        "per_quarter": per_q,
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    slim = {k: v for k, v in res.items() if k not in ("per_quarter", "row_cov_by_filing_year", "rows_by_filing_year", "multi_ticker_examples", "universe_conflict_examples")}
    print(json.dumps(slim, ensure_ascii=False, indent=1, default=str))
    print("row_cov_by_filing_year:", res["row_cov_by_filing_year"])
    bad = {q: v for q, v in per_q.items() if v["filing_date_bad"] > 0.01 or v["trans_date_bad"] > 0.01 or v["ticker_missing"] > 0.2 or v["price_missing_or_le0"] > 0.3}
    print("問題季度(日期壞>1%/ticker缺>20%/價缺>30%):", {q: {k: round(x, 3) if isinstance(x, float) else x for k, x in v.items() if k in ("rows", "filing_date_bad", "trans_date_bad", "ticker_missing", "price_missing_or_le0")} for q, v in bad.items()})


if __name__ == "__main__":
    main()
