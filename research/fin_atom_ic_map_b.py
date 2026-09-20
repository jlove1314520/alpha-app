# -*- coding: utf-8 -*-
"""原子.五B：財報通道B（結構型算子）重掃——計算層（研究帽，2026-09-20）。

規格＝`ATOM_FIN_CHANNEL_B_SPEC.md`（事前登記）：132個表達式（Tier A 45＋Tier B 87）
×2 horizon＝264測試。宇宙、snapshot、IC、記憶體紀律、holdout隔離全部**重用**
`fin_atom_ic_map.py`（原子.五）；本檔只替換其模組層級的`REGISTRY`／`_A`／`_B`，
輸出強制加`_chB`後綴，不覆蓋原子.五的結果檔。

用法：
    python research/fin_atom_ic_map_b.py --tier A --n 15 --tag _chBsmoke   # 小樣本煙霧
    python research/fin_atom_ic_map_b.py --tier A                      # Tier A全量
    python research/fin_atom_ic_map_b.py --tier B                      # Tier B全量
"""
from __future__ import annotations

import sys
from itertools import combinations

import numpy as np
import pandas as pd

import fin_atom_ic_map as base  # 會 mem_guard.install()、設好 sys.path
import FIN_ATOM_LIBRARY as fal

TAG = "_chB"

FLOW_AND_STOCK = ("revenue", "eps", "gross_profit", "op_income", "net_income", "ocf", "shares",
                  "total_assets", "equity", "inventory", "receivable")
TIER_A_ATOMS = {"revenue", "eps", "gross_profit", "op_income", "net_income", "shares"}

# R組：11個比率（名稱, 分子, 分母）；Tier A＝只需損益表者
RATIOS = (
    ("gross_margin", "gross_profit", "revenue"), ("op_margin", "op_income", "revenue"),
    ("net_margin", "net_income", "revenue"), ("roa", "net_income", "total_assets"),
    ("roe", "net_income", "equity"), ("asset_turnover", "revenue", "total_assets"),
    ("inventory_to_rev", "inventory", "revenue"), ("receivable_to_rev", "receivable", "revenue"),
    ("earnings_quality", "ocf", "net_income"), ("ocf_to_rev", "ocf", "revenue"),
    ("equity_ratio", "equity", "total_assets"),
)
TIER_A_RATIOS = {"gross_margin", "op_margin", "net_margin"}


def zscore_ts8(s: pd.Series) -> pd.Series:
    """(x − ts_mean(x,8)) / ts_std(x,8)：含當季的8個曆法連續季須齊全且非NaN，std==0→NaN。
    （SPEC第2節：zscore_ts窗口綁定為8季，ddof=1與庫內surprise的ts_std一致）"""
    lags = np.column_stack([fal._lag(s, k).values for k in range(8)])
    ok = ~np.isnan(lags).any(axis=1)
    mu = np.full(len(s), np.nan)
    sd = np.full(len(s), np.nan)
    mu[ok] = lags[ok].mean(axis=1)
    sd[ok] = lags[ok].std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (s.values - mu) / sd
    z = np.where(sd > 0, z, np.nan)
    return pd.Series(z, index=s.index, name=s.name)


def _apply(series_fn, op: str):
    def f(fr: pd.DataFrame) -> pd.Series:
        s = series_fn(fr)
        if op == "surprise_naive":
            return fal.fin_surprise(s, fal.expected_seasonal_naive(s))
        if op == "surprise_drift":
            return fal.fin_surprise(s, fal.expected_seasonal_drift(s))
        if op == "zscore8":
            return zscore_ts8(s)
        if op == "accel":
            return fal.fin_delta_yoy(s)
        raise ValueError(op)
    return f


def build_registry_b() -> dict[str, dict]:
    reg: dict[str, dict] = {}
    for name, x, y in RATIOS:
        tier = "A" if name in TIER_A_RATIOS else "B"
        rf = (lambda fr, x=x, y=y: fal.fin_ratio(fr[x], fr[y]))
        for op in ("surprise_naive", "surprise_drift", "zscore8", "accel"):
            reg[f"{op}({name})"] = {"fn": _apply(rf, op), "tier": tier}
    for a in FLOW_AND_STOCK:
        tier = "A" if a in TIER_A_ATOMS else "B"
        gf = (lambda fr, a=a: fal.fin_yoy(fr[a]))
        for op in ("surprise_naive", "surprise_drift", "zscore8"):
            reg[f"{op}(yoy({a}))"] = {"fn": _apply(gf, op), "tier": tier}
    for x, y in combinations(FLOW_AND_STOCK, 2):  # 無序配對：x−y與y−x只差正負號
        tier = "A" if (x in TIER_A_ATOMS and y in TIER_A_ATOMS) else "B"
        reg[f"spread(yoy({x}),yoy({y}))"] = {
            "fn": (lambda fr, x=x, y=y: fal.fin_yoy(fr[x]) - fal.fin_yoy(fr[y])), "tier": tier}
    return reg


REGISTRY_B = build_registry_b()
_A = [k for k, v in REGISTRY_B.items() if v["tier"] == "A"]
_B = [k for k, v in REGISTRY_B.items() if v["tier"] == "B"]
assert len(REGISTRY_B) == 132 and len(_A) == 45 and len(_B) == 87, (len(REGISTRY_B), len(_A), len(_B))
assert not set(REGISTRY_B) & set(base.REGISTRY), "與原子.五表達式重疊，違反SPEC第1節"


def main() -> int:
    # 只替換模組層級登記；base.main()於呼叫時才讀這三個全域名稱
    base.REGISTRY, base._A, base._B = REGISTRY_B, _A, _B
    if "--tag" not in sys.argv:
        sys.argv += ["--tag", TAG]
    elif not any(TAG in t for t in sys.argv):
        raise SystemExit("--tag請含_chB，避免覆蓋原子.五結果")
    return base.main()


if __name__ == "__main__":
    sys.exit(main())
