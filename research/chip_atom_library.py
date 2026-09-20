"""原子.六：籌碼原子表達式庫（規格＝`ATOM_CHIP_IC_MAP_SPEC.md`，事前登記）。

本模組只負責兩件事：(1)把T86／融資融券／借券賣出餘額三個本機快取整成「單一
股票、已lag 1日」的面板；(2)登記規格第3節的89個depth-1表達式（Tier A 67個、
Tier B 22個）。**不算IC、不做任何判定、不碰holdout**——IC地圖是下一個腳本
（`chip_atom_ic_map.py`）的範圍。

硬紀律（都寫在規格裡，這裡只是實作）：
- **所有籌碼欄位＋分母成交量一律lag 1個交易日**（收盤後才公布，PIT必要條件；分母
  也lag，才能讓`nf_n`分子分母的窗口對齊同一批日子）。
- 缺列一律NaN、不補0（規格第10節）。
- **只讀本機快取，絕不呼叫FinMind API**（缺檔就回空表，由呼叫端統計覆蓋）。
- 窗口只准`ALLOWED_WINDOWS`；算子只用`ATOM_LIBRARY`既有`op_*`。

用法：
    python research/chip_atom_library.py --self-test
"""
from __future__ import annotations

import os

# BLAS執行緒數：`MEM_BLAS_THREADS.md`實測建議值4（只影響本行程，不動排程/啟動器）。
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import ATOM_LIBRARY as al  # noqa: E402
from validation import holdout  # noqa: E402

RAW = HERE / "data" / "raw"
T86_DIR = HERE / "data" / "raw_twse_t86"
VAL_END = pd.Timestamp(holdout.VAL_END)

FLOW_T86 = ["foreign", "trust", "dealer", "total"]          # Tier A流量原子
CHIP_COLS = FLOW_T86 + ["margin_bal", "short_bal", "margin_util", "sbl_bal", "sbl_sales"]
STOCK_WINDOWS = (1, 5, 20, 60)
SMOOTH_WINDOWS = (5, 20, 60)


# ---------------------------------------------------------------------------
# 資料載入（只讀本機快取）
# ---------------------------------------------------------------------------

def load_t86_by_stock() -> dict[str, pd.DataFrame]:
    """讀`raw_twse_t86`全部逐日檔，回傳{4位數代號: DataFrame(date, foreign, trust,
    dealer, total)}，日期<=VAL_END。2010-01~2012-04為0列空殼、自然被略過。"""
    parts = []
    for f in sorted(T86_DIR.glob("T86_*.parquet")):
        if f.stat().st_size < 1500:  # 空殼檔
            continue
        d = pd.read_parquet(f)
        if d.empty:
            continue
        parts.append(d)
    t = pd.concat(parts, ignore_index=True)
    t["date"] = pd.to_datetime(t["date"])
    t = t[(t["date"] <= VAL_END) & t["stock_id"].astype(str).str.fullmatch(r"\d{4}")]
    t = t.rename(columns={"foreign_net": "foreign", "trust_net": "trust",
                          "dealer_net": "dealer", "total_net": "total"})
    t = t[["date", "stock_id", "foreign", "trust", "dealer", "total"]]
    for c in FLOW_T86:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype("float64")
    return {sid: g.drop(columns="stock_id").sort_values("date").reset_index(drop=True)
            for sid, g in t.groupby("stock_id")}


def _cached(dataset: str, sid: str) -> pd.DataFrame:
    """讀`data/raw/<dataset>__<sid>__*.parquet`；不存在／空殼回空表。不打API。"""
    fs = glob.glob(str(RAW / f"{dataset}__{sid}__*.parquet"))
    if not fs:
        return pd.DataFrame()
    d = pd.read_parquet(fs[0])
    if d.empty or "date" not in d.columns:
        return pd.DataFrame()
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    return d[d["date"] <= VAL_END]


def load_margin_frame(sid: str) -> pd.DataFrame:
    d = _cached("TaiwanStockMarginPurchaseShortSale", sid)
    if d.empty:
        return d
    need = {"MarginPurchaseTodayBalance", "MarginPurchaseLimit", "ShortSaleTodayBalance"}
    if not need <= set(d.columns):
        return pd.DataFrame()
    out = pd.DataFrame({"date": d["date"]})
    bal = pd.to_numeric(d["MarginPurchaseTodayBalance"], errors="coerce")
    lim = pd.to_numeric(d["MarginPurchaseLimit"], errors="coerce")
    out["margin_bal"] = bal
    out["short_bal"] = pd.to_numeric(d["ShortSaleTodayBalance"], errors="coerce")
    out["margin_util"] = (bal / lim).where(lim > 0)
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def load_sbl_frame(sid: str) -> pd.DataFrame:
    d = _cached("TaiwanDailyShortSaleBalances", sid)
    if d.empty:
        return d
    need = {"SBLShortSalesCurrentDayBalance", "SBLShortSalesShortSales"}
    if not need <= set(d.columns):
        return pd.DataFrame()
    out = pd.DataFrame({"date": d["date"]})
    out["sbl_bal"] = pd.to_numeric(d["SBLShortSalesCurrentDayBalance"], errors="coerce")
    out["sbl_sales"] = pd.to_numeric(d["SBLShortSalesShortSales"], errors="coerce")
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def universe_u() -> list[str]:
    """宇宙U＝融資融券快取4位數代號 ∩ 價格快取（規格第2節，392檔）。"""
    def ids(prefix: str) -> set[str]:
        return {Path(f).name.split("__")[1]
                for f in glob.glob(str(RAW / f"{prefix}__*.parquet"))
                if re.fullmatch(r"\d{4}", Path(f).name.split("__")[1])}
    return sorted(ids("TaiwanStockMarginPurchaseShortSale") & ids("TaiwanStockPrice"))


def build_chip_frame(px: pd.DataFrame, t86: pd.DataFrame | None,
                     margin: pd.DataFrame | None, sbl: pd.DataFrame | None) -> pd.DataFrame:
    """以價格日曆（`px`需含date與v）為骨架，left-join三個籌碼來源，**然後把全部
    籌碼欄與v一起shift(1)**（規格第2節PIT紀律）。回傳index=價格日曆的DataFrame，
    欄位＝`v`＋`CHIP_COLS`（缺來源的欄全NaN）。`date`欄保留供呼叫端切snapshot。"""
    base = pd.DataFrame({"date": pd.to_datetime(px["date"]).values,
                         "v": px["v"].astype(float).values})
    for src in (t86, margin, sbl):
        if src is not None and len(src):
            base = base.merge(src, on="date", how="left")
    for c in CHIP_COLS:
        if c not in base.columns:
            base[c] = np.nan
    lagged = base[["v"] + CHIP_COLS].shift(1)  # lag 1個交易日（價格日曆上的列）
    lagged.insert(0, "date", base["date"].values)
    return lagged


# ---------------------------------------------------------------------------
# 表達式登記（規格第3節）
# ---------------------------------------------------------------------------

def _nf(col: str, n: int):
    return lambda d: al.op_ratio(al.op_ts_sum(d[col], n), al.op_ts_sum(d["v"], n))


def _streak(col: str, n: int):
    return lambda d: al.op_ts_sum(al.op_sign(d[col]), n)


def _decay(col: str, n: int):
    return lambda d: al.op_decay_linear(al.op_ratio(d[col], d["v"]), n)


def _growth(col: str, n: int):
    return lambda d: al.op_ratio(d[col], al.op_delay(d[col], n)) - 1.0


def _rank(col: str, n: int):
    return lambda d: al.op_ts_rank(d[col], n)


def _dov(col: str):
    return lambda d: al.op_ratio(d[col], al.op_ts_mean(d["v"], 20))


def _delta(col: str, n: int):
    return lambda d: al.op_delta(d[col], n)


def build_expression_specs() -> list[dict]:
    """回傳89個表達式規格：{name, tier, family, needs, fn}。順序固定、名稱唯一。"""
    specs: list[dict] = []

    def add(name, tier, family, needs, fn):
        specs.append({"name": name, "tier": tier, "family": family,
                      "needs": tuple(needs), "fn": fn})

    def flow_block(col: str, tier: str, family: str):
        for n in STOCK_WINDOWS:
            add(f"nf__{col}__{n}", tier, family, [col], _nf(col, n))
        for n in SMOOTH_WINDOWS:
            add(f"streak__{col}__{n}", tier, family, [col], _streak(col, n))
        for n in SMOOTH_WINDOWS:
            add(f"decay__{col}__{n}", tier, family, [col], _decay(col, n))

    def stock_block(col: str, tier: str, family: str):
        for n in STOCK_WINDOWS:
            add(f"growth__{col}__{n}", tier, family, [col], _growth(col, n))
        for n in SMOOTH_WINDOWS:
            add(f"rank__{col}__{n}", tier, family, [col], _rank(col, n))
        add(f"dov__{col}", tier, family, [col], _dov(col))

    for col in FLOW_T86:                       # 4×10 = 40
        flow_block(col, "A", "inst_flow")
    for col in ("margin_bal", "short_bal"):    # 2×8 = 16
        stock_block(col, "A", "margin_short_level")
    add("level__margin_util", "A", "margin_util", ["margin_util"], lambda d: d["margin_util"])  # 7
    for n in SMOOTH_WINDOWS:
        add(f"delta__margin_util__{n}", "A", "margin_util", ["margin_util"], _delta("margin_util", n))
    for n in SMOOTH_WINDOWS:
        add(f"rank__margin_util__{n}", "A", "margin_util", ["margin_util"], _rank("margin_util", n))
    add("level__short_margin", "A", "short_margin", ["short_bal", "margin_bal"],
        lambda d: al.op_ratio(d["short_bal"], d["margin_bal"]))                                  # 4
    for n in SMOOTH_WINDOWS:
        add(f"delta__short_margin__{n}", "A", "short_margin", ["short_bal", "margin_bal"],
            lambda d, n=n: al.op_delta(al.op_ratio(d["short_bal"], d["margin_bal"]), n))

    flow_block("sbl_sales", "B", "sbl_flow")   # 10
    stock_block("sbl_bal", "B", "sbl_level")   # 8
    add("level__sbl_short", "B", "sbl_short", ["sbl_bal", "short_bal"],
        lambda d: al.op_ratio(d["sbl_bal"], d["short_bal"]))                                     # 4
    for n in SMOOTH_WINDOWS:
        add(f"delta__sbl_short__{n}", "B", "sbl_short", ["sbl_bal", "short_bal"],
            lambda d, n=n: al.op_delta(al.op_ratio(d["sbl_bal"], d["short_bal"]), n))

    names = [s["name"] for s in specs]
    assert len(names) == len(set(names)), "表達式名稱重複"
    assert len(specs) == 89, f"表達式數{len(specs)}≠規格89"
    assert sum(s["tier"] == "A" for s in specs) == 67, "Tier A≠67"
    assert sum(s["tier"] == "B" for s in specs) == 22, "Tier B≠22"
    return specs


def compute_expressions(frame: pd.DataFrame, specs: list[dict], tiers=("A",)) -> pd.DataFrame:
    """對單一股票的chip frame算指定tier的全部表達式，回傳與frame同index的DataFrame。
    來源欄全NaN（例如上櫃股沒有T86）的表達式整欄NaN（不補、不丟）。"""
    cols = {}
    for s in specs:
        if s["tier"] not in tiers:
            continue
        if all(frame[c].isna().all() for c in s["needs"]):
            cols[s["name"]] = pd.Series(np.nan, index=frame.index)
            continue
        cols[s["name"]] = s["fn"](frame).astype(float)
    return pd.DataFrame(cols, index=frame.index)


# ---------------------------------------------------------------------------
# 自我測試
# ---------------------------------------------------------------------------

def _self_test() -> None:
    specs = build_expression_specs()
    print(f"OK 表達式數={len(specs)}（A=67, B=22），名稱唯一")

    # (1) lag1：合成資料，t日表達式輸入必須等於原始t−1日值
    dates = pd.bdate_range("2020-01-01", periods=10)
    px = pd.DataFrame({"date": dates, "v": np.arange(1.0, 11.0)})
    t86 = pd.DataFrame({"date": dates, "foreign": np.arange(10.0, 20.0),
                        "trust": 0.0, "dealer": 0.0, "total": np.arange(10.0, 20.0)})
    f = build_chip_frame(px, t86, None, None)
    assert np.isnan(f["foreign"].iloc[0]) and f["foreign"].iloc[1] == 10.0 and f["foreign"].iloc[9] == 18.0
    assert f["v"].iloc[1] == 1.0 and f["v"].iloc[9] == 9.0
    print("OK lag1（籌碼欄與v皆延遲1列）")

    # (2) 缺列不補0：刪掉t86中間一天
    f2 = build_chip_frame(px, t86.drop(index=[4]), None, None)
    assert np.isnan(f2["foreign"].iloc[5]) and f2["foreign"].iloc[6] == 15.0
    print("OK 缺列保持NaN、不補0")

    # (3) nf__foreign__5在合成資料上手算核對
    d = compute_expressions(f, specs, tiers=("A",))
    exp = (10 + 11 + 12 + 13 + 14) / (1 + 2 + 3 + 4 + 5)
    assert abs(d["nf__foreign__5"].iloc[5] - exp) < 1e-12, d["nf__foreign__5"].iloc[5]
    assert d["level__margin_util"].isna().all()  # 沒有融資來源→整欄NaN
    print("OK nf__foreign__5手算一致；無來源欄整欄NaN")

    # (4) 真實資料煙霧測試：2330（上市、有T86＋融資融券快取；SBL僅2330一檔）
    from adjust import adjusted_price_series
    sid = "2330"
    p = adjusted_price_series(sid)
    vcol = "volume" if "volume" in p.columns else "Trading_Volume"
    px = pd.DataFrame({"date": p["date"], "v": p[vcol]})
    t86_all = load_t86_by_stock()
    fr = build_chip_frame(px, t86_all.get(sid), load_margin_frame(sid), load_sbl_frame(sid))
    out = compute_expressions(fr, specs, tiers=("A", "B"))
    nn = out.notna().sum()
    print(f"2330：價格列數{len(fr)}，89個表達式非NaN列數 min={nn.min()} median={int(nn.median())} max={nn.max()}")
    assert (nn > 0).all(), f"有表達式在2330全NaN：{list(nn[nn == 0].index)}"
    assert fr["date"].max() <= VAL_END
    print(f"OK 日期上界={fr['date'].max().date()}<=VAL_END；is_holdout_consumed={holdout.is_holdout_consumed()}")
    U = universe_u()
    print(f"宇宙U={len(U)}檔（規格預期392）")
    assert len(U) == 392, f"宇宙U={len(U)}≠392"
    print("ALL PASS")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
