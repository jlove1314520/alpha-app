# -*- coding: utf-8 -*-
"""先.五十八-C：R2 勝算估計（描述性，不登記為試驗）。

區塊自助法（區塊 12 個月、10,000 次）估計 Bb-90、S3-C6、R1 四組在「任意 10 年期間」：
①年化勝過 0050 全持有的機率 ②最大回撤超過 −50% 的機率；
並以 App 破億路徑卡的**預設示例參數**（repo 內沒有使用者真實參數，真實值只存在本機設定，不讀、不進 repo）
推算「40 歲達 1 億」的機率分布。

資料：2003-07-01～2024-12-31（2025 起保留資料已用盡，不讀）。各策略日報酬沿用：
- 0050 全持有、Bb-90：#418／#421 `leveraged_bb90_backtest.load_all／simulate`
- S3-C6：#424 C6＋S3 閘門，延後一個交易日執行（`crisis_gate_timing_sensitivity.run_lagged`，與紙.三一致）
- R1-A～D：#429／#430 `r1_0050_credit_gate`（延後一日）
輸出：research/data/win_probability_2026_10.json（數字由本檔產生，md 由人工照抄並註明來源）。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import r1_0050_credit_gate as R1  # noqa: E402  （連帶 import #424 模組並設定 #421 公式）
import crisis_gate_timing_sensitivity as TS  # noqa: E402

M, LB, TL = R1.M, R1.LB, R1.TL
OUT = HERE / "data" / "win_probability_2026_10.json"
END = "2024-12-31"
SEED = 20261010
B = 10_000
BLOCK = 12            # 月
WIN_YEARS = 10
# App 破億路徑卡的預設示例參數（index.html placeholder＋scripts/smoke_test.mjs 第 1759 行的示例；非使用者真實值）
EX = {"nw": 6_000_000, "pmt": 300_000, "birth": "1998-01-13", "age": 40, "goal": 1e8, "as_of": "2026-10-10"}


def series() -> tuple[pd.Series, dict]:
    df, _ = LB.load_all()
    df = df[df["date"] <= END].reset_index(drop=True)
    dates = df["date"]
    n = len(df)
    out = {"0050": df["r_0050"].to_numpy(float), "Bb-90": LB.simulate(df, LB.target_418("Bb-90"))}
    sim = M.Sim(df)
    on = M.sig_credit(M.load_baa(dates)[sim.me])
    out["S3-C6"] = TS.run_lagged(sim, M.CONFIGS["C6"], on, on)
    R = np.column_stack([df["r_0050"].to_numpy(float), df["r_ltw"].to_numpy(float), df["r_cash"].to_numpy(float)])
    C = np.vstack([np.ones((1, 3)), np.cumprod(1.0 + R, axis=0)])
    me = R1.month_ends(dates)
    on1 = M.sig_credit(M.load_baa(dates)[me])
    for g, spec in R1.GROUPS.items():
        out[g] = R1.run_fast(R, C, R1.events(n, me, on1, spec["open"], spec["closed"]), spec["open"], R1.SELL_TAX_TW)
    return dates, out


def mdd(path_ret: np.ndarray) -> float:
    eq = np.cumprod(1.0 + path_ret)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def main() -> int:
    dates, S = series()
    names = list(S)
    D = np.column_stack([S[k] for k in names])                       # 日報酬（n × K）
    per = dates.dt.to_period("M")
    months = per.unique()
    mi = per.map({p: i for i, p in enumerate(months)}).to_numpy()
    T = len(months)
    day_idx = [np.flatnonzero(mi == i) for i in range(T)]
    Mret = np.vstack([np.prod(1.0 + D[ix], axis=0) - 1.0 for ix in day_idx])   # 月報酬（T × K）
    k0 = names.index("0050")

    # 歷史滾動 10 年（重疊、每月起點；只是描述，樣本高度相關）
    W = WIN_YEARS * 12
    roll = {k: {"beat_0050": 0, "mdd_lt_-50": 0} for k in names}
    nwin = T - W + 1
    for s in range(nwin):
        ix = np.concatenate(day_idx[s:s + W])
        c = (np.prod(1.0 + D[ix], axis=0)) ** (1.0 / WIN_YEARS) - 1.0
        for j, k in enumerate(names):
            roll[k]["beat_0050"] += int(c[j] > c[k0])
            roll[k]["mdd_lt_-50"] += int(mdd(D[ix, j]) < -0.50)
    hist = {k: {"p_beat_0050": v["beat_0050"] / nwin, "p_mdd_lt_-50": v["mdd_lt_-50"] / nwin} for k, v in roll.items()}

    # 區塊自助法：10 年＝10 個 12 個月區塊；所有策略共用同一組區塊（保留彼此相關性，勝負是配對比較）
    rng = np.random.default_rng(SEED)
    starts_max = T - BLOCK
    nb = W // BLOCK
    beat = np.zeros(len(names))
    deep = np.zeros(len(names))
    cagr_all = np.empty((B, len(names)))
    for b in range(B):
        st = rng.integers(0, starts_max + 1, nb)
        ix = np.concatenate([np.concatenate(day_idx[s:s + BLOCK]) for s in st])
        P = D[ix]
        c = np.prod(1.0 + P, axis=0) ** (1.0 / WIN_YEARS) - 1.0
        cagr_all[b] = c
        beat += c > c[k0]
        eq = np.cumprod(1.0 + P, axis=0)
        dd = (eq / np.maximum.accumulate(eq, axis=0) - 1.0).min(axis=0)
        deep += dd < -0.50
    boot = {k: {"p_beat_0050": float(beat[j] / B), "p_mdd_lt_-50": float(deep[j] / B),
                "cagr_p5_p50_p95": [float(x) for x in np.percentile(cagr_all[:, j], [5, 50, 95])]}
            for j, k in enumerate(names)}

    # 破億：示例參數，月底投入；月報酬以 12 個月區塊自助抽樣
    bd = date.fromisoformat(EX["birth"])
    target = date(bd.year + EX["age"], bd.month, bd.day)
    now = date.fromisoformat(EX["as_of"])
    years = (target - now).days / 365.25
    nmon = int(round(years * 12))
    nblk = -(-nmon // BLOCK)
    rng2 = np.random.default_rng(SEED + 1)
    fin = np.empty((B, len(names)))
    for b in range(B):
        st = rng2.integers(0, T - BLOCK + 1, nblk)
        Rm = np.vstack([Mret[s:s + BLOCK] for s in st])[:nmon]
        w = np.full(len(names), float(EX["nw"]))
        for t in range(nmon):
            w = w * (1.0 + Rm[t]) + EX["pmt"]
        fin[b] = w
    # 對照：App 卡的確定性算法（年化 10.19%，月複利等效、月底投入）
    rate = 0.1019
    m = (1 + rate) ** (1 / 12) - 1
    det = EX["nw"] * (1 + m) ** nmon + EX["pmt"] * (((1 + m) ** nmon - 1) / m)
    bt = {k: {"p_reach_1e8": float((fin[:, j] >= EX["goal"]).mean()),
              "terminal_p5_p25_p50_p75_p95": [float(x) for x in np.percentile(fin[:, j], [5, 25, 50, 75, 95])]}
          for j, k in enumerate(names)}

    res = {"generated_at": datetime.now(timezone.utc).isoformat(), "period": [str(dates.iloc[0].date()), END],
           "n_months": int(T), "strategies": names, "seed": SEED, "B": B, "block_months": BLOCK, "window_years": WIN_YEARS,
           "full_period_cagr": {k: float(TL.cagr(S[k], dates)) for k in names},
           "full_period_mdd": {k: float(TL.mdd(S[k])) for k in names},
           "historical_rolling_10y": {"n_windows": int(nwin), "by_strategy": hist},
           "block_bootstrap_10y": boot,
           "breakthrough_example": {"params": EX, "params_source": "App 破億路徑卡預設示例（index.html placeholder 與 scripts/smoke_test.mjs 示例）；使用者真實參數只存在本機設定，未讀取",
                                    "months": nmon, "years": years, "deterministic_app_card_10.19pct": det,
                                    "by_strategy": bt}}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {"cagr": round(res["full_period_cagr"][k] * 100, 2), "mdd": round(res["full_period_mdd"][k] * 100, 1),
                          "hist_beat": round(hist[k]["p_beat_0050"] * 100, 1), "hist_mdd50": round(hist[k]["p_mdd_lt_-50"] * 100, 1),
                          "boot_beat": round(boot[k]["p_beat_0050"] * 100, 1), "boot_mdd50": round(boot[k]["p_mdd_lt_-50"] * 100, 1),
                          "boot_cagr": [round(x * 100, 1) for x in boot[k]["cagr_p5_p50_p95"]],
                          "p_1e8": round(bt[k]["p_reach_1e8"] * 100, 1),
                          "fin": [round(x / 1e6, 1) for x in bt[k]["terminal_p5_p25_p50_p75_p95"]]} for k in names},
                     ensure_ascii=False, indent=1))
    print("months", nmon, "years", round(years, 2), "det", round(det / 1e6, 1), "nwin", nwin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
