# -*- coding: utf-8 -*-
"""原子.六：籌碼depth-1原子IC地圖——計算層（研究帽，2026-09-20）。

**規格完全以`ATOM_CHIP_IC_MAP_SPEC.md`為準（事前登記，看結果後不得改）**：89個表達式
（Tier A 67＋Tier B 22）×2 horizon(20/60日)＝178測試。本檔只負責「算出逐snapshot IC並存檔」，
**不做任何策略判定、不報告最佳素材**；分年份/牛熊段/樸素基準/共線分群在聚合腳本（下一步）。

事前綁定（都來自規格第4節）：
- snapshot＝`factor_ic.build_snapshots(calendar, 2010起首個交易日, VAL_END, horizon)`，不重疊；
  籌碼欄位與成交量分母已在`chip_atom_library.build_chip_frame`整體lag 1日。
- 前瞻報酬＝還原收盤價自snapshot日起算h個交易日；橫斷面Spearman IC。
- 每個(表達式,snapshot)有效配對<`MIN_VALID`(30)者IC記NaN並計數（規格第4節「入樣規則」）。
- `n_snap`<8者標「樣本不足」（原子.五門檻）。
- 記憶體：逐檔只保留「表達式×snapshot日」小表；掛`mem_guard`；只讀本機快取，**不發任何API請求**。
- Tier B需要借券賣出餘額快取，覆蓋率（`data/backfill_sbl_cache_status.json`的
  `coverage_of_U`）達60%前**不得執行**（規格第7/9節：未達門檻記「未檢驗」不記FAIL）；
  2026-09-22覆蓋率達69.39%後解除此限制，本腳本改為動態讀覆蓋率狀態檔判斷。
- 全程不碰holdout（快取層截在VAL_END；開工前檢查`is_holdout_consumed()`）。

用法：
    python research/chip_atom_ic_map.py --tier A --n 15 --tag _smoke   # 15檔煙霧
    python research/chip_atom_ic_map.py --tier A --n 30 --tag _mem30    # 30檔記憶體驗證
    python research/chip_atom_ic_map.py --tier A                        # Tier A全量（宇宙U）
    python research/chip_atom_ic_map.py --tier B --n 15 --tag _smoke   # Tier B 15檔煙霧
    python research/chip_atom_ic_map.py --tier B                        # Tier B全量（覆蓋率達門檻才會跑）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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
import mem_guard  # 事件001補正
mem_guard.install()

import chip_atom_library as cal  # noqa: E402
from factor_ic import build_snapshots  # noqa: E402
from finmind_client import load_dev  # noqa: E402
from validation import holdout  # noqa: E402

HORIZONS = (20, 60)
MIN_VALID = 30      # 規格第4節：橫斷面有效檔數<30該snapshot跳過
MIN_SNAP = 8        # 規格第4節：n_snap<8標「樣本不足」
SNAP_START = "2010-01-01"


def peak_private_mb() -> float | None:
    """本行程峰值private commit（Windows PeakPagefileUsage，MB）；量不到回None（不影響主流程）。"""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        c = PMC(); c.cb = ctypes.sizeof(c)
        ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.PeakPagefileUsage / 1e6
    except Exception:  # noqa: BLE001 -- 量測失敗只降級
        return None


def cross_ic(cross: pd.DataFrame, ret: pd.Series) -> pd.Series:
    """橫斷面Spearman IC；有效配對<MIN_VALID者記NaN。"""
    ic = cross.corrwith(ret, method="spearman")
    valid = cross.notna().mul(ret.notna(), axis=0).sum()
    return ic.where(valid >= MIN_VALID)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=("A", "B"), required=True)
    ap.add_argument("--n", type=int, default=0, help="只跑前N檔（煙霧/記憶體驗證；0=全量）")
    ap.add_argument("--tag", default="", help="輸出檔名後綴（避免蓋掉全量結果）")
    a = ap.parse_args()
    print(f"is_holdout_consumed()開工前檢查：{holdout.is_holdout_consumed()}", flush=True)
    assert not holdout.is_holdout_consumed(), "holdout已解鎖，中止"
    if a.tier == "B":
        # 規格第7/9節：借券賣出餘額覆蓋率達U的60%才可執行Tier B。
        status_path = HERE / "data" / "backfill_sbl_cache_status.json"
        try:
            coverage = json.loads(status_path.read_text(encoding="utf-8")).get("coverage_of_U")
        except Exception as e:  # noqa: BLE001 -- 讀不到狀態檔就保守擋下，不猜測
            print(f"讀不到借券快取覆蓋率狀態檔（{status_path}）：{e}，Tier B不執行", flush=True)
            return 2
        print(f"借券賣出餘額快取覆蓋率coverage_of_U={coverage}", flush=True)
        if coverage is None or coverage < 0.6:
            print("覆蓋率未達60%門檻（規格第7節），Tier B不執行", flush=True)
            return 2

    specs = cal.build_expression_specs()
    names = [s["name"] for s in specs if s["tier"] == a.tier]
    expect_n = {"A": 67, "B": 22}[a.tier]
    assert len(names) == expect_n, (a.tier, len(names))

    market = load_dev("TaiwanStockPrice", "TAIEX", SNAP_START)
    holdout.assert_no_holdout_leakage(market, context="TAIEX in chip_atom_ic_map")
    calendar = sorted(pd.to_datetime(market["date"]).dt.strftime("%Y-%m-%d").unique())
    snaps = {h: build_snapshots(calendar, calendar[0], calendar[-1], horizon=h) for h in HORIZONS}
    for h in HORIZONS:
        print(f"horizon={h}：snapshot數={len(snaps[h])}（{snaps[h][0][0]}~{snaps[h][-1][0]}）", flush=True)
    need_dates = sorted({pd.Timestamp(d) for h in HORIZONS for pair in snaps[h] for d in pair})

    ids = cal.universe_u()
    if a.n:
        ids = ids[: a.n]
    print(f"宇宙U：{len(ids)}檔；表達式={len(names)}（Tier {a.tier}）", flush=True)

    from adjust import adjusted_price_series  # noqa: E402
    t86_all = cal.load_t86_by_stock()
    print(f"T86逐股載入：{len(t86_all)}檔", flush=True)

    expr_tab: dict[str, pd.DataFrame] = {}
    px_tab: dict[str, pd.Series] = {}
    fail = {"no_price": 0}
    n_with_t86 = 0
    t0 = time.time()
    for i, sid in enumerate(ids, 1):
        try:
            p = adjusted_price_series(sid, SNAP_START)
            vcol = "volume" if "volume" in p.columns else "Trading_Volume"
            px = pd.DataFrame({"date": pd.to_datetime(p["date"]), "v": p[vcol].astype(float).values})
            ps = pd.Series(p["adj_close"].astype(float).values, index=pd.to_datetime(p["date"]))
            ps = ps[~ps.index.duplicated(keep="first")]
        except Exception as e:  # noqa: BLE001
            fail["no_price"] += 1
            print(f"  [{sid}] 價格載入失敗：{str(e)[:100]}", flush=True)
            continue
        px = px[px["date"] <= cal.VAL_END].reset_index(drop=True)
        t86 = t86_all.get(sid)
        n_with_t86 += int(t86 is not None and len(t86) > 0)
        sbl = cal.load_sbl_frame(sid) if a.tier == "B" else None
        fr = cal.build_chip_frame(px, t86, cal.load_margin_frame(sid), sbl)
        out = cal.compute_expressions(fr, specs, tiers=(a.tier,))
        out.index = pd.DatetimeIndex(fr["date"])
        out = out[~out.index.duplicated(keep="first")]
        expr_tab[sid] = out.reindex(need_dates)
        px_tab[sid] = ps.reindex(need_dates)
        del p, px, ps, fr, out
        if i % 25 == 0 or i == len(ids):
            print(f"  {i}/{len(ids)}（可用{len(expr_tab)}檔，{time.time()-t0:.0f}s）", flush=True)
    print(f"可用股票 {len(expr_tab)}/{len(ids)}；有T86者{n_with_t86}；失敗={fail}", flush=True)

    train_end, val_end = pd.Timestamp(holdout.TRAIN_END), pd.Timestamp(holdout.VAL_END)
    results = []
    skipped_snap: dict[int, int] = {}
    for h in HORIZONS:
        ic_rows = {}
        skipped = 0
        for as_of, fwd in snaps[h]:
            s0, s1 = pd.Timestamp(as_of), pd.Timestamp(fwd)
            rows, rets = {}, {}
            for sid, tab in expr_tab.items():
                p0, p1 = px_tab[sid].get(s0, np.nan), px_tab[sid].get(s1, np.nan)
                if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                    continue
                rows[sid] = tab.loc[s0]
                rets[sid] = float(p1 / p0 - 1)
            if len(rows) < MIN_VALID:
                skipped += 1
                continue
            ic_rows[s0] = cross_ic(pd.DataFrame(rows).T.astype(float), pd.Series(rets))
        skipped_snap[h] = skipped
        if not ic_rows:
            print(f"horizon={h}：無任何snapshot可算IC", flush=True)
            continue
        snap_df = pd.DataFrame(ic_rows).T.sort_index()
        snap_df.to_parquet(HERE / f"chip_atom_ic_snapshots_{a.tier}_h{h}{a.tag}.parquet")
        tr = snap_df[snap_df.index <= train_end]
        va = snap_df[(snap_df.index > train_end) & (snap_df.index <= val_end)]
        for n in names:
            tm, vm = float(tr[n].mean()), float(va[n].mean())
            ntr, nva = int(tr[n].count()), int(va[n].count())
            results.append({
                "expression": n, "tier": a.tier, "horizon": h,
                "train_mean_ic": None if np.isnan(tm) else tm,
                "val_mean_ic": None if np.isnan(vm) else vm,
                "n_snap_train": ntr, "n_snap_val": nva,
                "insufficient": bool(ntr < MIN_SNAP or nva < MIN_SNAP),
                "same_sign": bool(not np.isnan(tm) and not np.isnan(vm) and tm != 0 and np.sign(tm) == np.sign(vm))})
        print(f"horizon={h}：{len(snap_df)}個snapshot有IC（TRAIN {len(tr)}／VAL {len(va)}；橫斷面<{MIN_VALID}檔跳過{skipped}）", flush=True)

    out = HERE / f"chip_atom_ic_map_result_{a.tier}{a.tag}.json"
    out.write_text(json.dumps({"tier": a.tier, "n_stocks_used": len(expr_tab), "n_stocks_requested": len(ids),
                               "n_with_t86": n_with_t86, "fail": fail, "skipped_snapshots": skipped_snap,
                               "n_snapshots": {str(h): len(snaps[h]) for h in HORIZONS}, "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已存：{out.name}（{len(results)}列）；峰值private commit={peak_private_mb()}MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
