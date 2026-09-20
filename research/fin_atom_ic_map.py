# -*- coding: utf-8 -*-
"""原子.五：財報depth-1素材IC地圖——計算層（研究帽，2026-09-20）。

**規格完全以`ATOM_FIN_IC_MAP_SPEC.md`為準（事前登記，看結果後不得改）**：
145個表達式（Tier A 57＋Tier B 88）×2 horizon(20/60日)＝290測試。
本檔只負責「算出逐snapshot IC並存檔」，**不做任何策略判定、不報告最佳素材**；
分年份/牛熊段聚合、樸素基準並列、共線分群在`fin_atom_ic_map_aggregate.py`（下一步）。

**關鍵設計（都來自SPEC第4節，事前綁定）**：
- Snapshot＝各法定期限（5/15、8/14、11/14、次年3/31）之後的**第一個交易日**
  （嚴格晚於期限日），每年約4個，避免同一份財報在密集snapshot重複貢獻。
- 表達式值＝「pit_date<=snapshot日」的最新一季（PIT，pit_date為法定期限，
  由`FIN_ATOM_LIBRARY`提供）；報酬＝還原收盤價自snapshot日起算20/60個交易日。
- 每個snapshot：橫斷面Spearman IC；單一表達式當日有效配對<`MIN_PAIRS`者IC記NaN
  （`[自行裁量]`：沿用原子.二「橫斷面<10檔不算」的同一把尺，SPEC未另訂）。
- 記憶體：逐檔算完只留「表達式×snapshot日」的小表（~145×60個數字），
  不常駐任何全歷史序列（`INCIDENTS.md`事件001教訓）；另掛`mem_guard`。
- Tier A只讀損益表快取（不觸發任何資產負債表/現金流量表的網路請求）；
  Tier B只取「三表齊全」者，且**只在本機快取內找，不發任何FinMind請求**。
- 全程不碰holdout：資料走`finmind_client.load_dev`（擷取層截在VAL_END），
  開工前檢查`is_holdout_consumed()`。

用法：
    python research/fin_atom_ic_map.py --tier A --n 15 --tag smoke   # 小樣本煙霧
    python research/fin_atom_ic_map.py --tier A                      # Tier A全量（≤300檔）
    python research/fin_atom_ic_map.py --tier B                      # Tier B全量（三表齊全者）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

try:  # 守門員自身失敗只降級（CLAUDE.md第十二節）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mem_guard  # 事件001補正：全市場批次腳本的記憶體安全閥
mem_guard.install()

import FIN_ATOM_LIBRARY as fal  # noqa: E402
from factor_ic import SAMPLE_SIZE, START_DATE, sample_universe_ids  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from validation import holdout  # noqa: E402

HORIZONS = (20, 60)
MIN_PAIRS = 10
RAW = HERE / "data" / "raw"
SUFFIX = "__2010-01-01__2024-12-31.parquet"
DEADLINES = ((3, 31), (5, 15), (8, 14), (11, 14))  # 法定申報期限（月,日）

# --- 表達式登記（SPEC第3節；數量在模組載入時斷言，與SPEC不符即失敗）---------
FLOW_NO_SHARES = ("revenue", "eps", "gross_profit", "op_income", "net_income", "ocf")
STOCK_ATOMS = ("total_assets", "equity", "inventory", "receivable")
RATIO_ATOMS = ("revenue", "gross_profit", "op_income", "net_income", "ocf",
               "total_assets", "equity", "inventory", "receivable")
TIER_B_ATOMS = {"ocf", "total_assets", "equity", "inventory", "receivable"}
TIER_A_RATIO_ATOMS = {"revenue", "gross_profit", "op_income", "net_income"}


def _unary(atom: str, op: str):
    def f(fr: pd.DataFrame) -> pd.Series:
        s = fr[atom]
        if op == "yoy":
            return fal.fin_yoy(s)
        if op == "qoq":
            return fal.fin_qoq(s)
        if op == "ttm":
            return fal.fin_ttm(s)
        if op == "slope4":
            return fal.fin_slope(s, 4)
        if op == "slope8":
            return fal.fin_slope(s, 8)
        if op == "delta_yoy":
            return fal.fin_delta_yoy(s)
        if op == "surprise_naive":
            return fal.fin_surprise(s, fal.expected_seasonal_naive(s))
        if op == "surprise_drift":
            return fal.fin_surprise(s, fal.expected_seasonal_drift(s))
        raise ValueError(op)
    return f


def _ratio(x: str, y: str):
    return lambda fr: fal.fin_ratio(fr[x], fr[y])


def build_registry() -> dict[str, dict]:
    reg: dict[str, dict] = {}
    for a in FLOW_NO_SHARES:
        for op in ("yoy", "qoq", "ttm", "slope4", "slope8", "delta_yoy", "surprise_naive", "surprise_drift"):
            reg[f"{op}({a})"] = {"fn": _unary(a, op), "tier": "B" if a in TIER_B_ATOMS else "A"}
    for op in ("yoy", "qoq", "slope4", "slope8", "delta_yoy"):
        reg[f"{op}(shares)"] = {"fn": _unary("shares", op), "tier": "A"}
    for a in STOCK_ATOMS:
        for op in ("yoy", "qoq", "slope4", "slope8", "delta_yoy"):
            reg[f"{op}({a})"] = {"fn": _unary(a, op), "tier": "B"}
    for x in RATIO_ATOMS:
        for y in RATIO_ATOMS:
            if x == y:
                continue
            tier = "A" if (x in TIER_A_RATIO_ATOMS and y in TIER_A_RATIO_ATOMS) else "B"
            reg[f"ratio({x},{y})"] = {"fn": _ratio(x, y), "tier": tier}
    return reg


REGISTRY = build_registry()
_A = [k for k, v in REGISTRY.items() if v["tier"] == "A"]
_B = [k for k, v in REGISTRY.items() if v["tier"] == "B"]
assert len(REGISTRY) == 145 and len(_A) == 57 and len(_B) == 88, (len(REGISTRY), len(_A), len(_B))


# --- Snapshot日期 -----------------------------------------------------------
def snapshot_dates(calendar: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """各法定期限「之後的第一個交易日」（嚴格晚於期限日），2010~VAL_END。"""
    out = []
    for y in range(2010, pd.Timestamp(holdout.VAL_END).year + 1):
        for m, d in DEADLINES:
            dl = pd.Timestamp(year=y, month=m, day=d)
            pos = calendar.searchsorted(dl, side="right")
            if pos < len(calendar):
                out.append(calendar[pos])
    return sorted(set(out))


# --- 宇宙 -------------------------------------------------------------------
def _has(dataset: str, code: str) -> bool:
    """快取存在且**列數>0**（空parquet也有檔案大小，不能用size判斷；實測用size會把407檔
    誤算成549檔，列數口徑才重現SPEC登記的407檔）。"""
    import pyarrow.parquet as pq
    p = RAW / f"{dataset}__{code}{SUFFIX}"
    if not p.exists():
        return False
    try:
        return pq.ParquetFile(p).metadata.num_rows > 0
    except Exception:  # noqa: BLE001 -- 讀不了就當沒有
        return False


def tier_universe(tier: str) -> list[str]:
    inc = sorted(c for c in {p.name.split("__")[1] for p in RAW.glob("TaiwanStockFinancialStatements__*" + SUFFIX)}
                 if _has("TaiwanStockFinancialStatements", c))
    if tier == "A":
        pool = set(inc)
        return [s for s in sample_universe_ids(SAMPLE_SIZE) if s in pool]
    # Tier B：三表齊全（僅本機快取，不發請求）。以「列數>0」判定，實測＝407檔，
    # 與SPEC登記數一致（`財報原子.補快取`補回來的檔案實測皆為空表，不改變宇宙）。
    return [c for c in inc if _has("TaiwanStockBalanceSheet", c) and _has("TaiwanStockCashFlowsStatement", c)]


def load_frame(code: str, tier: str) -> pd.DataFrame:
    start = "2010-01-01"
    inc = load_dev("TaiwanStockFinancialStatements", code, start)
    if tier == "A":
        return fal.build_quarter_frame(inc, None, None)
    return fal.build_quarter_frame(inc, load_dev("TaiwanStockBalanceSheet", code, start),
                                   load_dev("TaiwanStockCashFlowsStatement", code, start))


def expr_at_snapshots(frame: pd.DataFrame, names: list[str], snaps: pd.DatetimeIndex) -> pd.DataFrame:
    """回傳index=snapshot日、columns=表達式名的表；值＝pit_date<=snapshot日的最新一季。"""
    wide = {}
    for n in names:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                wide[n] = REGISTRY[n]["fn"](frame).values
        except Exception:  # noqa: BLE001 -- 單一表達式算不出來只讓該欄NaN，不中斷整檔
            wide[n] = np.full(len(frame), np.nan)
    right = pd.DataFrame(wide)
    right["pit_date"] = pd.to_datetime(frame["pit_date"].values).astype("datetime64[ns]")  # 兩側時間單位須一致（pandas 2+ merge_asof）
    right = right.sort_values("pit_date")
    left = pd.DataFrame({"date": pd.DatetimeIndex(snaps).astype("datetime64[ns]")}).sort_values("date")
    merged = pd.merge_asof(left, right, left_on="date", right_on="pit_date", direction="backward")
    out = merged[names]
    out.index = pd.DatetimeIndex(merged["date"])
    return out


def spearman_ic(cross: pd.DataFrame, ret: pd.Series) -> pd.Series:
    ic = cross.corrwith(ret, method="spearman")
    valid = cross.notna().mul(ret.notna(), axis=0).sum()
    return ic.where(valid >= MIN_PAIRS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=("A", "B"), required=True)
    ap.add_argument("--n", type=int, default=0, help="只跑前N檔（煙霧/記憶體驗證用；0=全量）")
    ap.add_argument("--tag", default="", help="輸出檔名後綴（煙霧測試用，避免蓋掉全量結果）")
    a = ap.parse_args()

    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}", flush=True)
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"

    names = _A if a.tier == "A" else _B
    market = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market, context="TAIEX in fin_atom_ic_map")
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(market["date"]).unique()))
    snaps = pd.DatetimeIndex(snapshot_dates(calendar))
    pos = {d: i for i, d in enumerate(calendar)}
    fwd = {h: {s: (calendar[pos[s] + h] if pos[s] + h < len(calendar) else pd.NaT) for s in snaps} for h in HORIZONS}
    print(f"snapshot數={len(snaps)}（{snaps[0].date()}~{snaps[-1].date()}）；表達式={len(names)}（Tier {a.tier}）", flush=True)

    ids = tier_universe(a.tier)
    if a.n:
        ids = ids[: a.n]
    print(f"Tier {a.tier}宇宙：{len(ids)}檔（tier_universe，僅本機快取）", flush=True)

    from adjust import adjusted_price_series  # noqa: E402

    expr_tab: dict[str, pd.DataFrame] = {}
    px_tab: dict[str, pd.Series] = {}
    fail: dict[str, int] = {"no_price": 0, "no_frame": 0}
    t0 = time.time()
    for i, sid in enumerate(ids, 1):
        try:
            frame = load_frame(sid, a.tier)
        except Exception as e:  # noqa: BLE001
            fail["no_frame"] += 1
            print(f"  [{sid}] 財報載入失敗：{str(e)[:100]}", flush=True)
            continue
        try:
            px = adjusted_price_series(sid, START_DATE)
            ps = pd.Series(px["adj_close"].astype(float).values, index=pd.to_datetime(px["date"]))
            ps = ps[~ps.index.duplicated(keep="first")]
        except Exception as e:  # noqa: BLE001
            fail["no_price"] += 1
            print(f"  [{sid}] 價格載入失敗：{str(e)[:100]}", flush=True)
            continue
        need = pd.DatetimeIndex(sorted(set(snaps) | {d for h in HORIZONS for d in fwd[h].values() if pd.notna(d)}))
        px_tab[sid] = ps.reindex(need)
        expr_tab[sid] = expr_at_snapshots(frame, names, snaps)
        del frame, px, ps
        if i % 25 == 0 or i == len(ids):
            print(f"  {i}/{len(ids)}（可用{len(expr_tab)}檔，{time.time()-t0:.0f}s）", flush=True)
    print(f"可用股票 {len(expr_tab)}/{len(ids)}；失敗={fail}", flush=True)

    results = []
    for h in HORIZONS:
        ic_rows: dict[pd.Timestamp, pd.Series] = {}
        for s in snaps:
            f = fwd[h][s]
            if pd.isna(f):
                continue
            rows, rets = {}, {}
            for sid, tab in expr_tab.items():
                p0, p1 = px_tab[sid].get(s, np.nan), px_tab[sid].get(f, np.nan)
                if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                    continue
                rows[sid] = tab.loc[s]
                rets[sid] = float(p1 / p0 - 1)
            if len(rows) < MIN_PAIRS:
                continue
            ic_rows[s] = spearman_ic(pd.DataFrame(rows).T.astype(float), pd.Series(rets))
        if not ic_rows:
            print(f"horizon={h}：無任何snapshot可算IC", flush=True)
            continue
        snap_df = pd.DataFrame(ic_rows).T.sort_index()
        snap_df.to_parquet(HERE / f"fin_atom_ic_snapshots_{a.tier}_h{h}{a.tag}.parquet")
        tr = snap_df[snap_df.index <= pd.Timestamp(holdout.TRAIN_END)]
        va = snap_df[(snap_df.index > pd.Timestamp(holdout.TRAIN_END)) & (snap_df.index <= pd.Timestamp(holdout.VAL_END))]
        for n in names:
            tm, vm = float(tr[n].mean()), float(va[n].mean())
            results.append({"expression": n, "tier": a.tier, "horizon": h,
                            "train_mean_ic": None if np.isnan(tm) else tm,
                            "val_mean_ic": None if np.isnan(vm) else vm,
                            "n_snap_train": int(tr[n].count()), "n_snap_val": int(va[n].count()),
                            "same_sign": bool(not np.isnan(tm) and not np.isnan(vm) and tm != 0 and np.sign(tm) == np.sign(vm))})
        print(f"horizon={h}：{len(snap_df)}個snapshot有IC（TRAIN {len(tr)}／VAL {len(va)}）", flush=True)

    out = HERE / f"fin_atom_ic_map_result_{a.tier}{a.tag}.json"
    out.write_text(json.dumps({"tier": a.tier, "n_stocks_used": len(expr_tab), "n_stocks_requested": len(ids),
                               "fail": fail, "n_snapshots": len(snaps), "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已存：{out.name}（{len(results)}列）", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
