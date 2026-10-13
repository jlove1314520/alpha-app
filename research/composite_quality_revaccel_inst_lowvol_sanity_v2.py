# -*- coding: utf-8 -*-
"""先.八十三-2b-1：#22 四濾網合取的五因子 TRAIN 覆蓋表（只產覆蓋表，不跑 sanity 判定）。

背景：原腳本 composite_quality_revaccel_inst_lowvol_sanity.py 不在 git，只剩
research/__pycache__/composite_quality_revaccel_inst_lowvol_sanity.cpython-313.pyc
（原始碼時間 2026-09-03 03:52）。本檔照 .pyc 反組譯讀回的定義重寫五個因子的取法：
  - f_quality_roe：quarterly_pit 的 EquityAttributableToOwnersOfParent（歸屬母公司淨利）
    ÷ balance_sheet_pit 的同名欄（歸屬母公司權益），以 fiscal_period_end inner merge，
    用 pit_date 做 as-of join（factors._asof_join）。
  - f_cfo：cash_flow_pit 的 NetCashInflowFromOperatingActivities，沒有就退
    CashFlowsFromOperatingActivities。
  - f_rev_accel／f_inst_streak_days／f_low_vol：factors.prepare_factors 既有欄位。
  - 快照：factor_ic.build_snapshots，每 20 個交易日一期、不重疊；日期要完全對上該股的 date 列。
  - 五個都有值才算「有效」。

跟原腳本刻意不同的地方（都是為了「只看覆蓋、不碰判定、不碰 TRAIN 以後」）：
  1. 只到 TRAIN_END（2020-12-31）；價格與大盤資料先截到 TRAIN_END 再算因子。
  2. 不算四個濾網的通過率、也不算合取候選池——那是 sanity（第 1 關）本身，要在 PREREG 之後。
  3. 樣本 100 檔（TRIALS_LEDGER #92 原試驗口徑「100 檔快取樣本」），種子沿用 factor_ic.SAMPLE_SEED。
  4. 擋網路：只讀本機快取，不打 FinMind／yfinance（不吃每小時額度）；沒快取的股票照實記成不可用。

不登記試驗、不碰 holdout、不改 research/pit.py 等單一寫入者檔。
用法：python research/composite_quality_revaccel_inst_lowvol_sanity_v2.py
輸出：research/data/composite22_v2_train_coverage.csv（research/data 已 gitignore）並印出摘要。
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))


class _NetworkBlocked(OSError):
    pass


def _blocked(*_a, **_k):
    raise _NetworkBlocked("本腳本只讀本機快取，網路已擋")


# 在 import 任何會連網的模組之前就擋掉（requests／yfinance 最後都走 socket）
socket.socket.connect = _blocked  # type: ignore[assignment]
socket.create_connection = _blocked  # type: ignore[assignment]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from adjust import adjusted_price_series  # noqa: E402
from factor_ic import SAMPLE_SEED, START_DATE, build_snapshots, sample_universe_ids  # noqa: E402
from factors import _asof_join, prepare_factors  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from pit import balance_sheet_pit, cash_flow_pit, quarterly_pit  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation.holdout import TRAIN_END  # noqa: E402

SAMPLE_SIZE_V1 = 100
SNAPSHOT_START = "2015-01-01"
FORWARD_HORIZON = 20
FACTORS = ["f_quality_roe", "f_cfo", "f_rev_accel", "f_inst_streak_days", "f_low_vol"]
OUT = Path(__file__).parent / "data" / "composite22_v2_train_coverage.csv"


def _roe_level(stock_id: str, start_date: str) -> pd.DataFrame:
    inc = quarterly_pit(stock_id, start_date)
    bs = balance_sheet_pit(stock_id, start_date)
    col = "EquityAttributableToOwnersOfParent"
    if inc.empty or bs.empty or col not in inc.columns or col not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "roe_level"])
    inc = inc[["fiscal_period_end", "pit_date", col]].rename(columns={col: "net_income"})
    bs = bs[["fiscal_period_end", col]].rename(columns={col: "equity"})
    merged = inc.merge(bs, on="fiscal_period_end", how="inner").sort_values("fiscal_period_end").reset_index(drop=True)
    if merged.empty:
        return pd.DataFrame(columns=["pit_date", "roe_level"])
    merged["roe_level"] = merged["net_income"] / merged["equity"]
    return merged[["pit_date", "roe_level"]]


def _cfo_level(stock_id: str, start_date: str) -> pd.DataFrame:
    cf = cash_flow_pit(stock_id, start_date)
    if cf.empty:
        return pd.DataFrame(columns=["pit_date", "cfo"])
    if "NetCashInflowFromOperatingActivities" in cf.columns:
        col = "NetCashInflowFromOperatingActivities"
    elif "CashFlowsFromOperatingActivities" in cf.columns:
        col = "CashFlowsFromOperatingActivities"
    else:
        return pd.DataFrame(columns=["pit_date", "cfo"])
    out = cf[["fiscal_period_end", "pit_date", col]].rename(columns={col: "cfo"})
    return out.sort_values("fiscal_period_end").reset_index(drop=True)[["pit_date", "cfo"]]


def _cap(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["date"].astype(str) <= TRAIN_END].reset_index(drop=True)


def load_sample(sample_ids: list[str], market_df: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    out: dict[str, pd.DataFrame] = {}
    dropped: dict[str, str] = {}
    for sid in sample_ids:
        try:
            px = _cap(adjusted_price_series(sid, START_DATE))
        except Exception as e:  # 沒快取（網路已擋）或資料壞掉：照實記成不可用
            dropped[sid] = f"價格讀取失敗：{type(e).__name__}"
            continue
        if px.empty or len(px) < 260:
            dropped[sid] = f"價格不足 260 列（{len(px)}）"
            continue
        try:
            d = prepare_factors(sid, px, market_df, START_DATE)
        except Exception as e:
            dropped[sid] = f"因子計算失敗：{type(e).__name__}"
            continue
        for fn, val_col, out_col in ((_roe_level, "roe_level", "f_quality_roe"), (_cfo_level, "cfo", "f_cfo")):
            try:
                p = fn(sid, START_DATE)
                d = _asof_join(d, p, val_col, out_col) if not p.empty else d.assign(**{out_col: np.nan})
            except Exception as e:
                print(f"  [警告] {sid} {out_col} 讀取失敗（{type(e).__name__}），記為缺值")
                d = d.assign(**{out_col: np.nan})
        out[sid] = d
    return out, dropped


def main() -> None:
    sample_ids = sample_universe_ids(SAMPLE_SIZE_V1, SAMPLE_SEED)
    print(f"[#22 v2] 抽 {len(sample_ids)} 檔，seed={SAMPLE_SEED}；只讀快取、資料截到 {TRAIN_END}")
    market_df = prepare_market_data(_cap(load_dev("TaiwanStockPrice", "TAIEX", START_DATE)))
    data, dropped = load_sample(sample_ids, market_df)
    print(f"[#22 v2] 可用 {len(data)}/{len(sample_ids)} 檔；不可用 {len(dropped)} 檔")
    reasons: dict[str, int] = {}
    for r in dropped.values():
        reasons[r.split("：")[0].split("（")[0]] = reasons.get(r.split("：")[0].split("（")[0], 0) + 1
    print(f"[#22 v2] 不可用原因：{reasons}")

    calendar = market_df["date"].astype(str).tolist()
    snapshots = build_snapshots(calendar, SNAPSHOT_START, TRAIN_END, FORWARD_HORIZON)
    print(f"[#22 v2] {len(snapshots)} 期快照，{SNAPSHOT_START}..{TRAIN_END}")

    rows = []
    for as_of, _fwd in snapshots:
        cnt = {f: 0 for f in FACTORS}
        n_all = n_valid = 0
        for d in data.values():
            hit = d.index[d["date"].astype(str) == as_of]
            if len(hit) == 0:
                continue
            r = d.loc[hit[0]]
            n_all += 1
            has = {f: not pd.isna(r.get(f)) for f in FACTORS}
            for f in FACTORS:
                cnt[f] += has[f]
            n_valid += all(has.values())
        rows.append({"as_of": as_of, "n_all": n_all, **{f"n_{f}": cnt[f] for f in FACTORS}, "n_valid_all5": n_valid})

    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"[#22 v2] 已寫入 {OUT}")
    df["year"] = df["as_of"].str[:4]
    summ = df.groupby("year")[["n_all", *[f"n_{f}" for f in FACTORS], "n_valid_all5"]].mean().round(1)
    print(summ.to_string())
    print(f"[#22 v2] 五因子全有值：每期最少 {df['n_valid_all5'].min()}、最多 {df['n_valid_all5'].max()}；"
          f"為 0 的期數 {int((df['n_valid_all5'] == 0).sum())}/{len(df)}")
    print("[#22 v2] 只是覆蓋表：沒有算濾網通過率、沒有算合取候選池、沒有判定")


if __name__ == "__main__":
    main()
