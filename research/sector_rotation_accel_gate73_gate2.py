# -*- coding: utf-8 -*-
"""#73 產業金流加速度——GATE_SEQUENCE 第2關：配對式隨機控制組（驗證帽）。

配對方式：訊號組每個再平衡月挑 accel 前20%產業（k = round(0.2×有效產業數)，至少1）；
控制組同一個月、同一批「當月有效產業」、同樣的 k，但隨機挑產業。其餘構造完全相同
（月頻、等權重產業、產業內等權重、靜態2026成分股、還原價 yfinance 快取），
所以差異只來自「是不是用了 accel 排序」——排除「產業輪動本身就有效果」的混淆。

**判準（在看到任何結果之前寫定，不得事後改）**
- 統計量：月頻毛報酬（不含成本）算術平均（該月每檔股票 adj_close 從再平衡日收盤到下個再平衡日收盤）。
- 控制組 N_DRAWS=500（>=100），seed 固定=73。
- 訊號組統計量在控制組分布的百分位（嚴格小於訊號值的比例，含 0.5×平手）。
- PASS 條件（全部同時成立）：
  (1) TRAIN(<=2020-12-31) 百分位 >= 95 且 VAL(2021-01-01~2024-12-31) 百分位 >= 95；
  (2) TRAIN 與 VAL 的訊號組平均月報酬與控制組中位數的差同號（皆為正）；
  (3) VAL 月數 >= 30。
  任一不成立=FAIL。多重比較：本假設 accel 排序、前20%、月頻皆事前綁定，1 個參數點，登記 N=1。
- 進場時點：訊號日=再平衡日前一交易日（T86 盤後才公布），進場價=再平衡日收盤（再延遲一天，保守，[自行裁量]）。
- 中途下市/缺價：股票在再平衡日或下個再平衡日缺價則該月排除（訊號與控制組同一規則）。
- 只讀 <=VAL_END 資料；不碰 holdout。成本：本關比較毛報酬，另附訊號組淨值（實際換手×0.18折一趟成本0.3013%）僅供參考，不參與判定。
輸出：research/sector_rotation_accel_gate73_gate2.json（進 git）
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sector_rotation_accel_gate73_sanity as S  # noqa: E402
from validation.holdout import TRAIN_END, VAL_END  # noqa: E402

HERE = Path(__file__).resolve().parent
YF_DIR = HERE / "data" / "raw_yf"
OUT = HERE / "sector_rotation_accel_gate73_gate2.json"
N_DRAWS = 500
SEED = 73
RT_COST = 0.003013  # breakeven_alpha_table.json t20 0.18折 roundtrip_cost_pct_with_slippage 0.3013%
_YF_RE = re.compile(r"^(\w+)__(\d{4}-\d\d-\d\d)__(\d{4}-\d\d-\d\d)\.parquet$")


def load_adj_close(ids: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """每檔取起點最早、終點<=VAL_END 的 yf 快取檔；回傳 date×stock 還原收盤與缺檔清單。"""
    best: dict[str, tuple[str, str]] = {}
    for p in glob.glob(str(YF_DIR / "*.parquet")):
        m = _YF_RE.match(os.path.basename(p))
        if not m or m.group(1) not in ids:
            continue
        sid, st, en = m.groups()
        if en > VAL_END:
            continue
        if sid not in best or st < best[sid][0]:
            best[sid] = (st, p)
    cols, missing = {}, []
    for sid in ids:
        if sid not in best:
            missing.append(sid)
            continue
        d = pd.read_parquet(best[sid][1], columns=["date", "close"])
        if d.empty:
            missing.append(sid)
            continue
        d = d[d["date"] <= VAL_END].drop_duplicates("date").set_index("date")["close"].astype(float)
        cols[sid] = d
    return pd.DataFrame(cols).sort_index(), missing


def main() -> int:
    wide = pd.read_parquet(S.ALL)
    assert wide.index.max() <= VAL_END
    acc = S.accel_frame(wide)
    comp = json.loads(S.COMPANY_INFO.read_text(encoding="utf-8"))["companies"]
    members: dict[str, list[str]] = {}
    for sid, rec in comp.items():
        ind = (rec or {}).get("industry")
        if ind and re.match(r"^[1-9][0-9]{3}$", sid) and ind in wide.columns:
            members.setdefault(ind, []).append(sid)
    all_ids = sorted({s for v in members.values() for s in v})
    px, missing = load_adj_close(all_ids)
    px = px.reindex(wide.index)  # 對齊 T86 交易日曆（<=VAL_END）
    ret_ok = px.notna()

    rebs = S.month_first_signal_dates(wide.index)
    rebs = [(r, s) for r, s in rebs if s in acc.index]
    rows = []  # (reb, next_reb, sig_ret, ctrl_matrix_row, k, turnover)
    rng = np.random.default_rng(SEED)
    prev_w: dict[str, float] = {}
    sig_ret, ctrl_ret, dates, turns, ks = [], [], [], [], []
    for i in range(len(rebs) - 1):
        reb, sig = rebs[i]
        nxt = rebs[i + 1][0]
        avail = px.loc[reb].notna() & px.loc[nxt].notna()
        r_stock = (px.loc[nxt] / px.loc[reb] - 1.0)[avail]
        sec_ret = {}
        for sec, ids in members.items():
            v = [r_stock[s] for s in ids if s in r_stock.index]
            if v:
                sec_ret[sec] = float(np.mean(v))
        row = acc.loc[sig].dropna()
        valid = [s for s in row.index if s in sec_ret]
        if len(valid) < 5:
            continue
        k = max(1, round(S.TOP_FRAC * len(valid)))
        top = list(row[valid].sort_values(ascending=False, kind="mergesort").index[:k])
        sig_ret.append(float(np.mean([sec_ret[s] for s in top])))
        vr = np.array([sec_ret[s] for s in valid])
        draws = np.array([vr[rng.choice(len(valid), size=k, replace=False)].mean() for _ in range(N_DRAWS)])
        ctrl_ret.append(draws)
        dates.append(reb)
        ks.append(k)
        w: dict[str, float] = {}
        for s in top:
            ids = [x for x in members[s] if x in r_stock.index]
            for st in ids:
                w[st] = w.get(st, 0.0) + 1.0 / (len(top) * len(ids))
        if prev_w:
            keys = set(w) | set(prev_w)
            turns.append(0.5 * sum(abs(w.get(x, 0.0) - prev_w.get(x, 0.0)) for x in keys))
        else:
            turns.append(float("nan"))
        prev_w = w

    sig = np.array(sig_ret)
    ctrl = np.vstack(ctrl_ret)  # months × draws
    dts = pd.Series(dates)
    tr = (dts <= TRAIN_END).values
    va = (dts > TRAIN_END).values

    def seg(mask: np.ndarray) -> dict:
        s = float(sig[mask].mean())
        c = ctrl[mask].mean(axis=0)  # 各 draw 的段內平均月報酬
        pct = 100.0 * (float((c < s).sum()) + 0.5 * float((c == s).sum())) / len(c)
        return {"months": int(mask.sum()), "signal_mean_monthly_pct": round(s * 100, 4),
                "control_median_pct": round(float(np.median(c)) * 100, 4),
                "control_p95_pct": round(float(np.quantile(c, 0.95)) * 100, 4),
                "control_max_pct": round(float(c.max()) * 100, 4),
                "diff_vs_median_pct": round((s - float(np.median(c))) * 100, 4),
                "percentile": round(pct, 2),
                "signal_annualized_geo_pct": round((float(np.prod(1 + sig[mask])) ** (12 / mask.sum()) - 1) * 100, 2),
                "control_median_annualized_geo_pct": None}

    full = np.ones(len(sig), dtype=bool)
    res = {"note": "Gate 2 配對式隨機控制組；判準事前寫死於腳本docstring", "n_draws": N_DRAWS, "seed": SEED,
           "months_total": int(len(sig)), "date_range": [dates[0], dates[-1]],
           "k_median": int(np.median(ks)),
           "stock_coverage": {"universe_ids": len(all_ids), "yf_missing": len(missing),
                              "yf_missing_frac": round(len(missing) / len(all_ids), 4)},
           "TRAIN": seg(tr), "VAL": seg(va), "FULL": seg(full)}
    # 對照組年化（用每個 draw 的幾何年化取中位數）
    for name, m in (("TRAIN", tr), ("VAL", va), ("FULL", full)):
        g = np.prod(1 + ctrl[m], axis=0) ** (12 / m.sum()) - 1
        res[name]["control_median_annualized_geo_pct"] = round(float(np.median(g)) * 100, 2)
    t = np.array(turns)
    net = sig - np.nan_to_num(t, nan=0.0) * RT_COST
    res["signal_net_annualized_geo_pct_0.18折_參考"] = {
        "TRAIN": round((float(np.prod(1 + net[tr])) ** (12 / tr.sum()) - 1) * 100, 2),
        "VAL": round((float(np.prod(1 + net[va])) ** (12 / va.sum()) - 1) * 100, 2)}
    # 逐年：訊號組 vs 控制組中位數
    yrs = dts.str[:4].values
    by_year = {}
    for y in sorted(set(yrs)):
        m = yrs == y
        by_year[y] = {"signal_pct": round((float(np.prod(1 + sig[m])) - 1) * 100, 2),
                      "control_median_pct": round(float(np.median(np.prod(1 + ctrl[m], axis=0) - 1)) * 100, 2)}
    res["by_year_geo_return"] = by_year
    res["years_signal_beats_control_median"] = sum(v["signal_pct"] > v["control_median_pct"] for v in by_year.values())
    res["years_total"] = len(by_year)
    ok1 = res["TRAIN"]["percentile"] >= 95 and res["VAL"]["percentile"] >= 95
    ok2 = res["TRAIN"]["diff_vs_median_pct"] > 0 and res["VAL"]["diff_vs_median_pct"] > 0
    ok3 = res["VAL"]["months"] >= 30
    res["criteria"] = {"pct_ge95_both": bool(ok1), "same_sign_positive": bool(ok2), "val_months_ge30": bool(ok3)}
    res["verdict"] = "PASS" if (ok1 and ok2 and ok3) else "FAIL"
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
