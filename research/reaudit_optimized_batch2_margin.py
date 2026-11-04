# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之五：#249 全市場融資餘額 regime 家族的樣本內最優化（描述性，非判定）。

方針（Cowork 收件匣 039 已定案）：掃參數挑最好的一組，只當描述性總表，不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。
訊號：TWSE MI_MARGN 全市場融資餘額週頻快取（`margin_debt_market_client.load_all_cached()`，與 #249／#26 同序列，2012-05 起），
     k 週成長率對自己的 expanding 百分位（暖身 52 週，PIT）；
     方向「過熱」＝成長率 > 高百分位 → 0050 曝險降到防禦值（#249 原版方向）；
     方向「去槓桿」＝成長率 < 低百分位（1−p）→ 降曝險（原版沒測過的反向，七之三變形方向①）。
     週五收盤後已知的訊號前向填補到日頻，再 shift 1 隔日生效（同 #249）；「月頻」變體只在月底更新。
期間：訊號暖身後才開始（約 2013-05）～2024-12-31；對照 0050 含息同期。
回測、成本、槓桿、止損：完全沿用 `reaudit_optimized_batch1.py` 的 simulate()／metrics()（同 F3／F10）。
掃描：k ∈ {4,8,12,26} 週、p ∈ {0.7,0.8,0.9}、方向 ∈ {過熱,去槓桿}、防禦曝險 ∈ {0,0.25,0.5}、頻率 ∈ {日,月}、
     槓桿 ∈ {1,1.5,2,3}、組合止損 ∈ {無,10%,20%,30%}＝2,304 格。
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_optimized_batch1 as B  # noqa: E402
from margin_debt_market_client import load_all_cached  # noqa: E402

END = "2024-12-31"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_margin.json"
KS = (4, 8, 12, 26)
PS = (0.7, 0.8, 0.9)
DIRS = ("hot", "cold")
DEFS = (0.0, 0.25, 0.5)
FREQS = ("D", "M")
MIN_EXP = 52


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def load_bal() -> pd.Series:
    df = load_all_cached()
    df = df[df["is_trading_day"] == True].copy()  # noqa: E712
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["financing_amount_today_balance_kNTD"]).sort_values("date")
    df = df[df["date"] <= pd.Timestamp(END)]
    s = df.drop_duplicates("date").set_index("date")["financing_amount_today_balance_kNTD"].astype(float)
    assert s.index.max() <= pd.Timestamp(END)
    return s


def flag(bal: pd.Series, k: int, p: float, d: str) -> pd.Series:
    g = bal / bal.shift(k) - 1
    if d == "hot":
        th = g.expanding(min_periods=MIN_EXP).quantile(p)
        f = (g > th).astype(float)
    else:
        th = g.expanding(min_periods=MIN_EXP).quantile(1 - p)
        f = (g < th).astype(float)
    f[th.isna() | g.isna()] = np.nan
    return f


def to_daily(f: pd.Series) -> np.ndarray:
    sig = f.dropna()
    idx = sig.index.searchsorted(B.DATES, side="right") - 1
    return np.where(idx >= 0, sig.to_numpy()[np.clip(idx, 0, None)], np.nan)


def exposure(fd: np.ndarray, de: float, fq: str) -> np.ndarray:
    e = np.where(np.isnan(fd), 1.0, np.where(fd > 0.5, de, 1.0))
    return B.monthly_hold(e) if fq == "M" else B.shift1(e)


def slice_globals(i0: int):
    B.DATES = B.DATES.iloc[i0:].reset_index(drop=True)
    B.N = len(B.DATES)
    B.RF_TW = B.RF_TW[i0:]
    B.RF_US = B.RF_US[i0:]
    B.R = {k: v[i0:] for k, v in B.R.items()}
    B.MONTH_END = B.MONTH_END[i0:]


def main():
    bal = load_bal()
    prog(f"融資餘額週頻 {len(bal)} 筆，{bal.index.min().date()}～{bal.index.max().date()}")
    flags = {(k, p, d): flag(bal, k, p, d) for k, p, d in itertools.product(KS, PS, DIRS)}
    first = max(f.first_valid_index() for f in flags.values())
    i0 = int(np.searchsorted(B.DATES.to_numpy(), np.datetime64(first), side="left")) + 1
    slice_globals(i0)
    prog(f"回測期間 {B.DATES.iloc[0].date()}～{B.DATES.iloc[-1].date()}（{B.N} 日）")
    fd = {key: to_daily(f) for key, f in flags.items()}
    rows = []
    for (k, p, d), de, fq, L, st in itertools.product(flags.keys(), DEFS, FREQS, B.LEVS, B.STOPS):
        e = exposure(fd[(k, p, d)], de, fq)
        m = B.metrics(B.simulate(np.column_stack([e, 1.0 - e]), ["0050", "CASH"], L, st, False))
        rows.append({"k_weeks": k, "pctile": p, "direction": d, "def_exposure": de, "freq": fq, "L": L, "stop": st, **m})
    df = pd.DataFrame(rows)
    ok = df[~df["violates_survival"]]
    pcols = ["k_weeks", "pctile", "direction", "def_exposure", "freq", "L", "stop"]

    def pack(r):
        d = {}
        for c in pcols:
            v = r[c]
            if c == "stop":
                d[c] = None if (v is None or v != v) else float(v)
            elif c in ("direction", "freq"):
                d[c] = v
            elif c == "k_weeks":
                d[c] = int(v)
            else:
                d[c] = float(v)
        d.update({"cagr": float(r["cagr"]), "mdd": float(r["mdd"]), "sharpe": float(r["sharpe"]),
                  "trades": int(r["trades"]), "win_rate": None if r["win_rate"] != r["win_rate"] else float(r["win_rate"]),
                  "calmar": float(r["calmar"]), "violates_survival": bool(r["violates_survival"])})
        return d
    bc = pack(ok.sort_values("calmar", ascending=False).iloc[0])
    br_ = pack(ok.sort_values("cagr", ascending=False).iloc[0])
    bench = B.metrics({"r": B.R["0050"], "trades": [(1.0, float(np.prod(1 + B.R["0050"])))]})
    # 只開 1×、無止損的「純訊號」最佳，看訊號本身有沒有東西（不靠槓桿）
    pure = df[(df["L"] == 1.0) & (df["stop"].isna())]
    bp = pack(pure.sort_values("calmar", ascending=False).iloc[0])
    e = exposure(fd[(bc["k_weeks"], bc["pctile"], bc["direction"])], bc["def_exposure"], bc["freq"])
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
    ax.set_title(f"F11 #249 全市場融資餘額 regime（樣本內最優化，{B.DATES.iloc[0].year}～2024，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    png = HERE / "data" / "reaudit_curves" / "batch2_F11.png"
    fig.savefig(png)
    plt.close(fig)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "data_start": str(B.DATES.iloc[0].date()), "data_end": END,
           "benchmark_0050_same_period": bench,
           "families": [{"id": "F11", "title": f"#249 全市場融資餘額 regime（0050 曝險，{B.DATES.iloc[0].year}～2024）",
                         "source_trials": [249], "n_grid": int(len(df)), "n_violates": int(df["violates_survival"].sum()),
                         "best_by_calmar": bc, "best_by_cagr_within_mdd50": br_, "best_1x_no_stop": bp,
                         "curve_png": "research/data/reaudit_curves/batch2_F11.png"}],
           "notes": "樣本內最優化（描述性）；融資餘額 TWSE MI_MARGN 週頻（2012-05 起），暖身 52 週後才有訊號。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    prog(f"最佳（Calmar）{bc}")
    prog(f"MDD≤50% 年化最高 {br_}")
    prog(f"1×無止損最佳 {bp}")
    prog(f"0050 同期 {bench['cagr']:+.1%}／{bench['mdd']:.1%}，Calmar {bench['calmar']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
