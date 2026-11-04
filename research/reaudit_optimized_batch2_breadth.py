# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之四：#248 全市場廣度 regime 家族的樣本內最優化（描述性，非判定）。

方針（Cowork 收件匣 039 已定案）：掃參數挑最好的一組，只當描述性總表，不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。
訊號：本機 `data/raw` 全部 4 位數代號個股（同 #248，未還原收盤價、今天仍在的名冊＝存活者偏誤未修正，偽影⑦）
     站上 MA 的比例＝廣度；廣度 < 門檻 → 0050 曝險降到防禦值，否則 1。訊號用當天收盤、隔一交易日生效（shift 1）；
     「月頻」變體只在月底收盤更新（#248 原版死在一年切換 9.5 次的成本）。
期間〔自行裁量〕：廣度快取從 2010-01 起，MA 暖身後才有訊號，所以本家族回測期間＝2010-12-31（實際起點）～2024-12-31
     （不用 2003 起、避免 2011 前「沒訊號＝滿倉」灌進買進持有的結果）；對照 0050 含息同期。
回測、成本、槓桿、止損：完全沿用 `reaudit_optimized_batch1.py` 的 simulate()／metrics()（F3 同一套：0050 合成槓桿 #421 公式、
     台股腿滑價＋手續費＋賣出 0.1% ETF 證交稅、止損回落 s 退現金 21 日冷卻）；只把它的全域資料切到上面的期間。
掃描：MA ∈ {100,150,200,250}、門檻 ∈ {0.4,0.5,0.6}、防禦曝險 ∈ {0,0.25,0.5}、訊號頻率 ∈ {日,月}、
     槓桿 ∈ {1,1.5,2,3}、組合止損 ∈ {無,10%,20%,30%}＝1,152 格。
"""
from __future__ import annotations

import glob
import itertools
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_optimized_batch1 as B  # noqa: E402  （載入 0050／現金／無風險利率，已截至 2024-12-31）

END = "2024-12-31"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_breadth.json"
MAS = (100, 150, 200, 250)
THS = (0.4, 0.5, 0.6)
DEFS = (0.0, 0.25, 0.5)
FREQS = ("D", "M")


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def load_panel() -> pd.DataFrame:
    cols = {}
    for f in sorted(glob.glob(str(HERE / "data" / "raw" / "TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet"))):
        sid = re.search(r"TaiwanStockPrice__(\w+)__", f).group(1)
        if not re.fullmatch(r"\d{4}", sid):
            continue
        df = pd.read_parquet(f)
        if df.empty or "close" not in df.columns:
            continue
        df = df[df["close"] > 0].drop_duplicates("date")
        cols[sid] = df.set_index("date")["close"]
    p = pd.DataFrame(cols).sort_index()
    p.index = pd.to_datetime(p.index.astype(str))
    p = p[p.index <= END]
    assert p.index.max() <= pd.Timestamp(END)
    return p


def breadth(panel: pd.DataFrame, n: int) -> pd.Series:
    ma = panel.rolling(n, min_periods=n).mean()
    valid = ma.notna() & panel.notna()
    return ((panel > ma) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)


def slice_globals(i0: int):
    """把 batch1 的全域資料切到 i0 之後（simulate／metrics 都讀模組全域）。"""
    B.DATES = B.DATES.iloc[i0:].reset_index(drop=True)
    B.N = len(B.DATES)
    B.RF_TW = B.RF_TW[i0:]
    B.RF_US = B.RF_US[i0:]
    B.R = {k: v[i0:] for k, v in B.R.items()}
    B.MONTH_END = B.MONTH_END[i0:]


def main():
    panel = load_panel()
    prog(f"廣度宇宙 {panel.shape[1]} 檔，{panel.index.min().date()}～{panel.index.max().date()}")
    br = {n: breadth(panel, n) for n in MAS}
    first = max(s.first_valid_index() for s in br.values())
    i0 = int(np.searchsorted(B.DATES.to_numpy(), np.datetime64(first), side="left")) + 1
    slice_globals(i0)
    prog(f"回測期間 {B.DATES.iloc[0].date()}～{B.DATES.iloc[-1].date()}（{B.N} 日）")
    bvals = {n: br[n].reindex(B.DATES, method="ffill").to_numpy(float) for n in MAS}
    rows, best = [], {}
    for n, th, de, fq, L, st in itertools.product(MAS, THS, DEFS, FREQS, B.LEVS, B.STOPS):
        b = bvals[n]
        e = np.where(np.isnan(b), 1.0, np.where(b < th, de, 1.0))
        e = B.monthly_hold(e) if fq == "M" else B.shift1(e)
        T = np.column_stack([e, 1.0 - e])
        m = B.metrics(B.simulate(T, ["0050", "CASH"], L, st, False))
        rows.append({"ma": n, "threshold": th, "def_exposure": de, "freq": fq, "L": L, "stop": st, **m})
    df = pd.DataFrame(rows)
    ok = df[~df["violates_survival"]]
    pcols = ["ma", "threshold", "def_exposure", "freq", "L", "stop"]

    def pack(r):
        d = {k: (None if (k == "stop" and (r[k] is None or r[k] != r[k])) else
                 (r[k] if k == "freq" else float(r[k]) if k != "ma" else int(r[k]))) for k in pcols}
        d.update({"cagr": float(r["cagr"]), "mdd": float(r["mdd"]), "sharpe": float(r["sharpe"]),
                  "trades": int(r["trades"]), "win_rate": None if r["win_rate"] != r["win_rate"] else float(r["win_rate"]),
                  "calmar": float(r["calmar"]), "violates_survival": bool(r["violates_survival"])})
        return d
    bc = pack(ok.sort_values("calmar", ascending=False).iloc[0])
    br_ = pack(ok.sort_values("cagr", ascending=False).iloc[0])
    bench = B.metrics({"r": B.R["0050"], "trades": [(1.0, float(np.prod(1 + B.R["0050"])))]})
    # 曲線
    b = bvals[bc["ma"]]
    e = np.where(np.isnan(b), 1.0, np.where(b < bc["threshold"], bc["def_exposure"], 1.0))
    e = B.monthly_hold(e) if bc["freq"] == "M" else B.shift1(e)
    best_r = B.simulate(np.column_stack([e, 1.0 - e]), ["0050", "CASH"], bc["L"], bc["stop"], False)["r"]
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(B.DATES, np.cumprod(1 + best_r), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(B.DATES, np.cumprod(1 + B.R["0050"]), color="#9aa0a6", lw=1.2, label="0050 買進持有（含息）")
    ax.set_yscale("log")
    ax.set_title("F10 #248 全市場廣度 regime（樣本內最優化，2011～2024，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    png = HERE / "data" / "reaudit_curves" / "batch2_F10.png"
    fig.savefig(png)
    plt.close(fig)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "data_start": str(B.DATES.iloc[0].date()), "data_end": END,
           "benchmark_0050_same_period": bench,
           "families": [{"id": "F10", "title": "#248 全市場廣度 regime（0050 曝險，2011～2024）", "source_trials": [248],
                         "n_grid": int(len(df)), "n_violates": int(df["violates_survival"].sum()),
                         "best_by_calmar": bc, "best_by_cagr_within_mdd50": br_,
                         "curve_png": "research/data/reaudit_curves/batch2_F10.png"}],
           "notes": "樣本內最優化（描述性）；廣度宇宙＝今天仍在的 4 位數代號、未還原價（存活者偏誤未修正）；期間 2011 起。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    prog(f"最佳（Calmar）{bc}")
    prog(f"MDD≤50% 年化最高 {br_}")
    prog(f"0050 同期 {bench['cagr']:+.1%}／{bench['mdd']:.1%}，Calmar {bench['calmar']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
