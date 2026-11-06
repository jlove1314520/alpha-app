# -*- coding: utf-8 -*-
"""先.一五五-2 墓園重審補跑 2025 起：F10 #248 全市場廣度 regime（Cowork 收件匣 039 已定案）。

性質：紙上優化軌描述性，不寫 TRIALS_LEDGER；非投資建議。零新外部請求。
做法：REAUDIT_END 延長 batch1（0050 2025 起由 reaudit_ext2025.extend_0050 接本機快取），呼叫原
`reaudit_optimized_batch2_breadth.py` 的 breadth()／slice_globals() 與 batch1 的 simulate()／metrics()，不改原檔。
廣度面板：原版 `TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet`（未還原收盤、4 位數代號）＋本機
`TaiwanStockPrice__*__2025-01-01__latest.parquet` 同一批代號接上（同樣未還原，與原版口徑一致）。
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

os.environ["REAUDIT_END"] = "2099-12-31"
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_optimized_batch2_breadth as BR  # noqa: E402
import reaudit_ext2025 as EXT  # noqa: E402

B = BR.B
SEG = "2025-01-01"


def load_panel_ext():
    cols = {}
    for f in sorted(glob.glob(str(HERE / "data" / "raw" / "TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet"))):
        sid = re.search(r"TaiwanStockPrice__(\w+)__", f).group(1)
        if not re.fullmatch(r"\d{4}", sid):
            continue
        df = pd.read_parquet(f)
        if df.empty or "close" not in df.columns:
            continue
        parts = [df]
        f2 = HERE / "data" / "raw" / f"TaiwanStockPrice__{sid}__2025-01-01__latest.parquet"
        if f2.exists():
            x = pd.read_parquet(f2)
            if not x.empty and "close" in x.columns:
                parts.append(x[pd.to_datetime(x["date"]) > "2024-12-31"])
        df = pd.concat(parts, ignore_index=True)
        df = df[df["close"] > 0].drop_duplicates("date")
        cols[sid] = df.set_index("date")["close"]
    p = pd.DataFrame(cols).sort_index()
    p.index = pd.to_datetime(p.index.astype(str))
    return p


def main():
    prev = json.loads((HERE / "data" / "reaudit_optimized_batch2_breadth.json").read_text(encoding="utf-8"))
    pb = prev["families"][0]["best_by_calmar"]
    panel = load_panel_ext()
    n25 = int(panel[panel.index >= SEG].notna().any().sum())
    BR.prog(f"廣度宇宙 {panel.shape[1]} 檔（2025 起有價 {n25} 檔），{panel.index.min().date()}～{panel.index.max().date()}")
    br = {n: BR.breadth(panel, n) for n in BR.MAS}
    first = max(s.first_valid_index() for s in br.values())
    i0 = int(np.searchsorted(B.DATES.to_numpy(), np.datetime64(first), side="left")) + 1
    BR.slice_globals(i0)
    end = min(B.DATES.iloc[-1], panel.index.max())
    keep = int((B.DATES <= end).sum())
    B.DATES = B.DATES.iloc[:keep].reset_index(drop=True); B.N = keep
    B.RF_TW = B.RF_TW[:keep]; B.RF_US = B.RF_US[:keep]; B.R = {k: v[:keep] for k, v in B.R.items()}; B.MONTH_END = B.MONTH_END[:keep]
    BR.prog(f"回測期間 {B.DATES.iloc[0].date()}～{B.DATES.iloc[-1].date()}（{B.N} 日）")
    bvals = {n: br[n].reindex(B.DATES, method="ffill").to_numpy(float) for n in BR.MAS}
    best, fixed = None, None
    nviol = 0
    same_sig = []
    for n, th, de, fq, L, st in itertools.product(BR.MAS, BR.THS, BR.DEFS, BR.FREQS, B.LEVS, B.STOPS):
        b = bvals[n]
        e = np.where(np.isnan(b), 1.0, np.where(b < th, de, 1.0))
        e = B.monthly_hold(e) if fq == "M" else B.shift1(e)
        res = B.simulate(np.column_stack([e, 1.0 - e]), ["0050", "CASH"], L, st, False)
        m = B.metrics(res)
        params = {"ma": n, "threshold": th, "def_exposure": de, "freq": fq, "L": L, "stop": st}
        nviol += bool(m["violates_survival"])
        k = (not m["violates_survival"], m["calmar"] if not m["violates_survival"] else -m["mdd"])
        if best is None or k > best[0]:
            best = (k, params, m, res["r"])
        if all(pb[x] == params[x] for x in ("ma", "threshold", "def_exposure", "freq")):
            same_sig.append({"L": L, "stop": st, "full_cagr": m["cagr"], "full_mdd": m["mdd"], "full_sharpe": m["sharpe"],
                             "pre": EXT._seg_metrics(res["r"], B.DATES, "1900-01-01", "2024-12-31"),
                             "seg2025": EXT._seg_metrics(res["r"], B.DATES, SEG)})
        if all((pb[x] == params[x]) if x != "stop" else ((pb["stop"] is None and st is None) or pb["stop"] == st) for x in params):
            fixed = (params, m, res["r"])
    D = B.DATES
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "family": "F10",
           "data_start": str(D.iloc[0].date()), "data_end": str(D.iloc[-1].date()), "n_grid": 1152, "n_violates": nviol,
           "panel_n": int(panel.shape[1]), "panel_n_2025": n25,
           "bench_0050": {"full": EXT._seg_metrics(B.R["0050"], D, "1900-01-01"), "seg2025": EXT._seg_metrics(B.R["0050"], D, SEG)},
           "fixed_params": fixed[0], "fixed_full": fixed[1],
           "fixed_pre2025": EXT._seg_metrics(fixed[2], D, "1900-01-01", "2024-12-31"),
           "fixed_seg2025": EXT._seg_metrics(fixed[2], D, SEG),
           "fixed_signal_by_L_stop": same_sig, "reopt_params": best[1], "reopt_full": best[2], "reopt_seg2025": EXT._seg_metrics(best[3], D, SEG)}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(D, np.cumprod(1 + fixed[2]), color="#2a6fdb", lw=1.6, label="原最優組（2024 底前挑、不重調）")
    ax.plot(D, np.cumprod(1 + best[3]), color="#e8710a", lw=1.1, ls="--", label="全期重新優化")
    ax.plot(D, np.cumprod(1 + B.R["0050"]), color="#9aa0a6", lw=1.1, label="0050 買進持有（含息）")
    ax.axvline(pd.Timestamp(SEG), color="#5f6368", lw=0.8, ls=":")
    ax.set_yscale("log"); ax.grid(alpha=0.25); ax.legend(frameon=False, fontsize=8)
    ax.set_title("F10 #248 全市場廣度 regime（延長到 2025 起，虛線右邊＝沒拿來調參的一段，非投資建議）", fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "data" / "reaudit_curves" / "ext2025_F10.png"); plt.close(fig)
    (HERE / "data" / "reaudit_ext2025_F10.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("data_end", "fixed_params", "fixed_pre2025", "fixed_seg2025", "reopt_params", "reopt_seg2025", "n_violates")}, ensure_ascii=False, default=float))
    print("fixed_full", out["fixed_full"]["cagr"], out["fixed_full"]["mdd"], "reopt_full", out["reopt_full"]["cagr"], out["reopt_full"]["mdd"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
