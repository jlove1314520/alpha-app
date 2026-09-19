# -*- coding: utf-8 -*-
"""#73 產業金流加速度——階段(b)：歷史版產業級日序列聚合（只建序列，不做任何判定）。

規格見 `research/HYPOTHESIS_QUEUE.md` #73 章節（含「第1輪」母體/PIT 但書）。
本檔本輪只完成「(b)寫聚合腳本」：
  T86（限4碼普通股）× 當日「未還原」收盤價 → est_amount → 依靜態產業分類聚合
  → 產業級日序列 → MA5/MA20 → accel（MA20 近零改差值並記錄天數）。
**不做回測、不做 Gate 判定、不登記 TRIALS**（沒有統計檢定發生）。Gate 1 sanity 是下一輪。

資料紀律
- 只讀本機快取，零網路請求；日期一律截在 VAL_END（validation.holdout），不碰 holdout。
- 價格用 FinMind `TaiwanStockPrice` 快取的 raw close（未還原）：法人淨買超股數 × 當日實際收盤
  才是當日真實金額；yfinance 快取是還原價（close==adj_close），不可用於金額換算。
- 產業分類＝`data/company_info.json` 2026 靜態快照（非 PIT，見 HYPOTHESIS_QUEUE #73 第1輪但書）。
- 母體＝T86（上市）4 碼普通股 `^[1-9][0-9]{3}$`，並排除 NON_INDUSTRY 標籤。上櫃歷史無法人資料。

事前綁定（本輪在看到任何結果之前寫定，[自行裁量]，可被總司令推翻）
- 「MA20 接近零」＝ |MA20| < NEAR_ZERO_FRAC(0.05) × 過去 SCALE_WINDOW(120) 日 |日金額| 均值
  （min_periods=60，只用當下以前資料，無未來函數）；此時 accel 改用 MA5−MA20（差值）並逐產業記天數。
  差值與比值量綱不同，兩者不可混在同一橫斷面排名——下一輪 Gate 1 必須決定處理法
  （本輪只量測近零天數占比，若占比高則該處理法變成必要的事前設計）。
- 核心宇宙穩健性子集＝2012-06-30 前已出現於 T86 且 2024-12 仍出現的股票。

輸出
- research/data/sector_flow_daily_gate73.parquet（gitignore，可重產）：date × sector 寬表 est_amount
- research/data/sector_flow_daily_gate73_core.parquet：同上，僅核心宇宙
- research/sector_rotation_accel_gate73_build.json：覆蓋率與近零天數診斷（進 git）
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation.holdout import VAL_END  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
T86_DIR = DATA / "raw_twse_t86"
PRICE_DIR = DATA / "raw"
COMPANY_INFO = HERE.parent / "data" / "company_info.json"
OUT_ALL = DATA / "sector_flow_daily_gate73.parquet"
OUT_CORE = DATA / "sector_flow_daily_gate73_core.parquet"
OUT_DIAG = HERE / "sector_rotation_accel_gate73_build.json"

STOCK_RE = re.compile(r"^[1-9][0-9]{3}$")
# 與 scripts/build_sector_flow.py::NON_INDUSTRY 同一份排除邏輯（該檔在 scripts/ 不宜 import，複製並註明）
NON_INDUSTRY = {
    "ETF", "上櫃ETF", "ETN", "存託憑證", "受益證券",
    "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
}
NEAR_ZERO_FRAC = 0.05
SCALE_WINDOW = 120
SCALE_MIN_PERIODS = 60
CORE_FIRST_BY = "2012-06-30"
CORE_LAST_AFTER = "2024-12-01"
_PRICE_RE = re.compile(r"^TaiwanStockPrice__(\w+)__(\d{4}-\d\d-\d\d)__(\d{4}-\d\d-\d\d)\.parquet$")


def _price_files() -> dict[str, str]:
    """每檔股票挑「涵蓋區間最寬」的一個快取檔（起日最早者）。"""
    best: dict[str, tuple[str, str]] = {}
    for p in glob.glob(str(PRICE_DIR / "TaiwanStockPrice__*.parquet")):
        m = _PRICE_RE.match(os.path.basename(p))
        if not m:
            continue
        sid, s, _e = m.groups()
        if sid not in best or s < best[sid][0]:
            best[sid] = (s, p)
    return {k: v[1] for k, v in best.items()}


def _load_t86() -> pd.DataFrame:
    frames = []
    for p in sorted(glob.glob(str(T86_DIR / "T86_*.parquet"))):
        d = pd.read_parquet(p)
        if len(d):
            frames.append(d)
    t = pd.concat(frames, ignore_index=True)
    t = t[t["stock_id"].str.match(STOCK_RE)]
    t = t[t["date"] <= VAL_END].copy()
    t["net_shares"] = t["foreign_net"] + t["trust_net"] + t["dealer_net"]
    return t


def _load_industry() -> dict[str, str]:
    comp = json.loads(COMPANY_INFO.read_text(encoding="utf-8"))["companies"]
    out = {}
    for sid, rec in comp.items():
        ind = (rec or {}).get("industry")
        if ind and ind not in NON_INDUSTRY:
            out[sid] = ind
    return out


def _near_zero_stats(wide: pd.DataFrame) -> dict:
    ma5 = wide.rolling(5, min_periods=5).mean()
    ma20 = wide.rolling(20, min_periods=20).mean()
    scale = wide.abs().rolling(SCALE_WINDOW, min_periods=SCALE_MIN_PERIODS).mean()
    valid = ma20.notna() & scale.notna()
    near = valid & (ma20.abs() < NEAR_ZERO_FRAC * scale)
    per_sector = {}
    for c in wide.columns:
        nv = int(valid[c].sum())
        per_sector[c] = {"valid_days": nv, "near_zero_days": int(near[c].sum()),
                         "near_zero_frac": round(float(near[c].sum() / nv), 4) if nv else None}
    tv, tn = int(valid.values.sum()), int(near.values.sum())
    return {"total_valid_sector_days": tv, "total_near_zero_days": tn,
            "near_zero_frac_overall": round(tn / tv, 4) if tv else None,
            "per_sector": per_sector, "ma5_available": bool(ma5.notna().any().any())}


def main() -> int:
    t86 = _load_t86()
    ind = _load_industry()
    pfiles = _price_files()

    # 逐檔載入 raw close（限 T86 出現過的股票）
    closes = []
    for sid in sorted(t86["stock_id"].unique()):
        p = pfiles.get(sid)
        if not p:
            continue
        d = pd.read_parquet(p, columns=["date", "stock_id", "close"])
        d = d[d["date"] <= VAL_END]
        closes.append(d)
    px = pd.concat(closes, ignore_index=True) if closes else pd.DataFrame(columns=["date", "stock_id", "close"])
    px = px.drop_duplicates(["date", "stock_id"])

    m = t86.merge(px, on=["date", "stock_id"], how="left")
    m["sector"] = m["stock_id"].map(ind)
    m["has_close"] = m["close"].notna() & (m["close"] > 0)
    m["has_sector"] = m["sector"].notna()
    m["est_amount"] = m["net_shares"] * m["close"]
    m["year"] = m["date"].str[:4]

    # 覆蓋率：以 |net_shares| 加權（丟掉的資金流占比才是實質損失）＋列數
    cov = {}
    for y, g in m.groupby("year"):
        w = g["net_shares"].abs()
        tot = float(w.sum())
        ok = g["has_close"] & g["has_sector"]
        cov[y] = {
            "rows": int(len(g)), "rows_usable": int(ok.sum()),
            "rows_frac": round(float(ok.mean()), 4),
            "abs_shares_frac_usable": round(float(w[ok].sum() / tot), 4) if tot else None,
            "rows_missing_close": int((~g["has_close"]).sum()),
            "rows_missing_sector_only": int((g["has_close"] & ~g["has_sector"]).sum()),
        }

    use = m[m["has_close"] & m["has_sector"]]

    def _wide(df: pd.DataFrame) -> pd.DataFrame:
        w = df.pivot_table(index="date", columns="sector", values="est_amount", aggfunc="sum")
        return w.sort_index().fillna(0.0)

    wide_all = _wide(use)

    first = t86.groupby("stock_id")["date"].min()
    last = t86.groupby("stock_id")["date"].max()
    core_ids = set(first[first <= CORE_FIRST_BY].index) & set(last[last >= CORE_LAST_AFTER].index)
    wide_core = _wide(use[use["stock_id"].isin(core_ids)])

    wide_all.to_parquet(OUT_ALL)
    wide_core.to_parquet(OUT_CORE)

    diag = {
        "note": "階段(b)聚合腳本產出；純量測，無 Gate 判定，未登記 TRIALS",
        "val_end_cap": VAL_END,
        "t86_rows_4digit": int(len(t86)),
        "t86_dates": [t86["date"].min(), t86["date"].max()],
        "t86_stocks": int(t86["stock_id"].nunique()),
        "price_cache_stocks_for_t86": int(len(set(t86["stock_id"]) & set(pfiles))),
        "industry_labeled_stocks_for_t86": int(len(set(t86["stock_id"]) & set(ind))),
        "sectors": int(wide_all.shape[1]), "sector_days": int(wide_all.shape[0]),
        "core_stocks": len(core_ids),
        "coverage_by_year": cov,
        "near_zero_all": _near_zero_stats(wide_all),
        "near_zero_core": _near_zero_stats(wide_core),
        "params": {"NEAR_ZERO_FRAC": NEAR_ZERO_FRAC, "SCALE_WINDOW": SCALE_WINDOW,
                   "SCALE_MIN_PERIODS": SCALE_MIN_PERIODS},
    }
    # per_sector 太長，只在診斷檔保留，不印
    OUT_DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"T86 4碼列 {len(t86):,}｜股票 {diag['t86_stocks']}｜有價格快取 {diag['price_cache_stocks_for_t86']}"
          f"｜有產業標籤 {diag['industry_labeled_stocks_for_t86']}｜產業數 {diag['sectors']}｜日數 {diag['sector_days']}")
    for y in sorted(cov):
        c = cov[y]
        print(f"  {y}: 列可用 {c['rows_frac']:.1%}｜|股數|加權可用 {c['abs_shares_frac_usable']:.1%}"
              f"｜缺收盤 {c['rows_missing_close']}｜僅缺產業 {c['rows_missing_sector_only']}")
    for k in ("near_zero_all", "near_zero_core"):
        s = diag[k]
        print(f"{k}: 有效產業日 {s['total_valid_sector_days']:,}｜近零 {s['total_near_zero_days']:,}"
              f"（{s['near_zero_frac_overall']:.2%}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 研究腳本失敗要看得見
        print(f"[FAIL] {type(e).__name__}: {e}")
        raise
