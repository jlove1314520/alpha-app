"""先.十三-三：產業缺貨回測用流動性代理（§7.5 `[自行裁量]`）。

只讀 `research/data/raw/TaiwanStockPrice__{code}__*__2024-12-31.parquet`（絕不讀 `*__latest.parquet`），
對每個 mapped 個股計算「近 60 個交易日 Trading_money 日均值」（依該股自己的交易日序列），
輸出 research/data/industry_shortage_liquidity.pkl：{code: {"dates": np.datetime64[D] 陣列, "roll60": float 陣列}}。
不讀任何報酬／收盤價變動，只用成交金額，純粹作截斷用的規模代理。
"""
from __future__ import annotations

import os
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "data" / "raw"
STOCK_MAP = ROOT / "docs" / "industry_shortage_stock_map.csv"
OUT = ROOT / "research" / "data" / "industry_shortage_liquidity.pkl"
PAT = re.compile(r"^TaiwanStockPrice__(\d{4})__(\d{4}-\d{2}-\d{2})__(\S+)\.parquet$")
CUTOFF = "2024-12-31"
WINDOW = 60


def main():
    sm = pd.read_csv(STOCK_MAP, dtype=str)
    mapped = sm[(sm.status == "mapped") & (sm.stock_id.str.len() == 4)]
    codes = mapped["stock_id"].tolist()

    by_code: dict[str, list[tuple[str, str]]] = {}
    for f in os.listdir(RAW):
        m = PAT.match(f)
        if not m:
            continue
        code, start, end = m.groups()
        if end == CUTOFF:
            by_code.setdefault(code, []).append((start, f))

    out: dict[str, dict] = {}
    n_missing_file, n_read_error, n_ok = 0, 0, 0
    for c in codes:
        fl = by_code.get(c)
        if not fl:
            n_missing_file += 1
            continue
        fl.sort()  # 取最早起始日（覆蓋最長）
        f = fl[0][1]
        try:
            df = pd.read_parquet(RAW / f, columns=["date", "Trading_money"])
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 讀取失敗 {c} {f}: {type(e).__name__}: {e}", flush=True)
            n_read_error += 1
            continue
        df = df.dropna(subset=["date"]).sort_values("date")
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates(subset=["date"], keep="last")
        roll = df["Trading_money"].rolling(WINDOW, min_periods=WINDOW).mean()
        out[c] = {"dates": df["date"].values.astype("datetime64[D]"), "roll60": roll.values.astype(float)}
        n_ok += 1

    meta = {"n_mapped_codes": len(codes), "n_ok": n_ok, "n_missing_file": n_missing_file,
            "n_read_error": n_read_error, "window": WINDOW, "cutoff": CUTOFF}
    with open(OUT, "wb") as fh:
        pickle.dump({"data": out, "meta": meta}, fh)
    print(f"寫入 {OUT}：{meta}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
