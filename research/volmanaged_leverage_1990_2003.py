# -*- coding: utf-8 -*-
"""先.八十一-17：可加槓桿的波動管理曝險（0.5–1.5 倍，Moreira & Muir）1990–2003 台股生存檢驗（單發）。

定義全部事前綁定於 docs/PREREG_volmanaged_leverage_1990_2003.md（登記 #439，SHA256 見 PREREG_SHA，commit 4d05ce86b）。
**只跑一次；績效數字一律在 JSON 寫完後才印。** 不讀 2003-07 以後任何資料、不打任何外部端點（只讀 #436 快取）；holdout 未動。
`--selftest`：只用合成報酬檢查機制（曝險換算、重排保持平均曝險、延後一日執行），不讀真實資料、不印任何真實績效。
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PREREG = "docs/PREREG_volmanaged_leverage_1990_2003.md"
PREREG_SHA = "eebb62d51fe9c945fcc2b1678eb21657eb94d094e2dd8c3367fda931539e149a"
PREREG_TRIAL = 439
OUT = HERE / "data" / "volmanaged_leverage_1990_2003_result.json"
CACHE = HERE / "data" / "raw" / "fmtqik_taiex_1990_2003.json"
START, END = "1990-01-01", "2003-06-30"
FIN_PRIMARY, FIN_SENS = 0.08, 0.04
MGMT, SELL_TAX, FEE = 0.01, 0.001, 0.001425
SURVIVAL = -0.50
E_LO, E_HI = 0.5, 1.5
WARMUP_MONTHS = 6
LOOKBACK = 36
N_RANDOM, SEED = 1000, 20261013
BEAR = {"1990": ("1990-01-01", "1990-12-31"), "1997-1998": ("1997-07-01", "1998-12-31"), "2000-2001": ("2000-02-01", "2001-12-31")}


def prog(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def check_prereg() -> None:
    h = hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if h != PREREG_SHA:
        raise SystemExit(f"事前登記文件 SHA256 不符（{h}），拒絕執行")


def load_taiex() -> pd.DataFrame:
    if not CACHE.exists():
        raise SystemExit(f"找不到 #436 快取 {CACHE}（本試驗不打外部端點），拒絕執行")
    df = pd.DataFrame(json.loads(CACHE.read_text(encoding="utf-8"))).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    return df[(df["date"] >= START) & (df["date"] <= END)].reset_index(drop=True)


def decisions(r: np.ndarray, per: np.ndarray, form: str) -> tuple[list, list]:
    """回傳 (月份清單, 每月月底決定的「下個月曝險」)。第 k 個月（0 起算）月底的決定只用到第 0..k 月的 RV。
    前 WARMUP_MONTHS 個月的曝險固定 1.0：第 0..WARMUP_MONTHS-2 月月底的決定＝1.0。"""
    months = list(dict.fromkeys(per))
    rv = {m: float(np.sum(r[per == m] ** 2)) for m in months}
    dec = []
    for k, m in enumerate(months):
        if k + 1 < WARMUP_MONTHS:
            dec.append(1.0)
            continue
        hist = [rv[months[j]] for j in range(max(0, k - LOOKBACK + 1), k + 1)]
        ratio = (float(np.median(hist)) / rv[m]) if rv[m] > 0 else float("inf")
        e = ratio if form == "variance" else math.sqrt(ratio)
        dec.append(float(min(max(e, E_LO), E_HI)))
    return months, dec


def weights(e: float) -> np.ndarray:
    return np.array([e, 0.0, 1.0 - e]) if e <= 1.0 else np.array([2.0 - e, e - 1.0, 0.0])


def simulate(r: np.ndarray, per: np.ndarray, months: list, dec: list, fin: float) -> tuple[np.ndarray, np.ndarray]:
    """月底決定 → 延後一個交易日收盤生效（與 #436 同一套引擎：月中漂移、月底與切換時回到目標權重並扣成本）。
    回傳 (日報酬, 每日生效曝險)。"""
    r2 = 2.0 * r - fin / 252.0 - MGMT / 252.0
    n = len(r)
    is_me = np.r_[per[1:] != per[:-1], True]
    dmap = dict(zip(months, dec))
    expo = np.ones(n)
    cur, pending = 1.0, None
    for i in range(n):
        if pending is not None:
            cur, pending = pending, None
        expo[i] = cur
        if is_me[i]:
            pending = dmap[per[i]]
    w = weights(expo[0])
    out = np.zeros(n)
    for i in range(1, n):
        g = np.array([r[i], r2[i], 0.0])
        port = float(w @ (1.0 + g))
        out[i] = port - 1.0
        w = w * (1.0 + g) / port
        if is_me[i] or expo[i] != expo[i - 1]:
            tgt = weights(expo[i])
            d = tgt - w
            cost = float(np.sum(np.clip(-d, 0, None)) * (SELL_TAX + FEE) + np.sum(np.clip(d, 0, None)) * FEE)
            out[i] = (1.0 + out[i]) * (1.0 - cost) - 1.0
            w = tgt
    return out, expo


def mdd(r: np.ndarray) -> float:
    v = np.cumprod(1.0 + r)
    return float(np.min(v / np.maximum.accumulate(v) - 1.0))


def cagr(r: np.ndarray) -> float:
    return float(np.prod(1.0 + r) ** (252.0 / max(len(r) - 1, 1)) - 1.0)


def sharpe(r: np.ndarray) -> float:
    x = r[1:]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(252)) if x.std(ddof=1) > 0 else 0.0


def seg_stats(r: np.ndarray, dates: pd.Series) -> dict:
    o = {}
    for k, (a, b) in BEAR.items():
        m = ((dates >= a) & (dates <= b)).to_numpy()
        o[k] = {"ret": float(np.prod(1 + r[m]) - 1), "mdd": mdd(r[m])} if m.sum() > 2 else None
    return o


def random_controls(r, per, months, dec, fin) -> dict:
    rng = np.random.default_rng(SEED)
    head, tail = dec[:WARMUP_MONTHS - 1], np.array(dec[WARMUP_MONTHS - 1:])
    sh, cg, dd = [], [], []
    for _ in range(N_RANDOM):
        d2 = head + list(rng.permutation(tail))
        x, _e = simulate(r, per, months, d2, fin)
        sh.append(sharpe(x)); cg.append(cagr(x)); dd.append(mdd(x))
    sh, cg, dd = np.array(sh), np.array(cg), np.array(dd)
    q = lambda a: {"p5": float(np.percentile(a, 5)), "p50": float(np.percentile(a, 50)), "p95": float(np.percentile(a, 95))}
    return {"n": N_RANDOM, "seed": SEED, "sharpe": q(sh), "cagr": q(cg), "mdd": q(dd),
            "share_mdd_gt_-50%": float(np.mean(dd > SURVIVAL)), "_sharpes": sh}


def selftest() -> int:
    """合成資料：檢查機制，不碰真實資料。"""
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2001-01-01", periods=600)
    vol = np.where(np.arange(600) % 120 < 60, 0.01, 0.03)
    r = rng.normal(0, vol)
    r[0] = 0.0
    per = dates.to_period("M").to_numpy()
    months, dec = decisions(r, per, "variance")
    assert dec[:WARMUP_MONTHS - 1] == [1.0] * (WARMUP_MONTHS - 1), "暖身期曝險應固定 1.0"
    assert all(E_LO <= x <= E_HI for x in dec), "曝險越界"
    assert np.allclose(weights(1.3) @ np.array([1, 2, 0]), 1.3) and np.allclose(weights(0.7) @ np.array([1, 2, 0]), 0.7), "權重換算曝險錯"
    _, expo = simulate(r, per, months, dec, FIN_PRIMARY)
    is_me = np.r_[per[1:] != per[:-1], True]
    k = int(np.where(is_me)[0][WARMUP_MONTHS])          # 第 7 個月月底
    assert expo[k + 1] == dec[WARMUP_MONTHS] and expo[k] == dec[WARMUP_MONTHS - 1], "月底決定應延後一個交易日生效"
    tail = np.array(dec[WARMUP_MONTHS - 1:])
    p = np.random.default_rng(SEED).permutation(tail)
    assert math.isclose(p.mean(), tail.mean()) and sorted(p) == sorted(tail), "重排應保持平均曝險與分布"
    hi = [dec[i] for i, m in enumerate(months) if i >= WARMUP_MONTHS - 1]
    print(f"selftest OK：{len(months)} 個月、曝險範圍 {min(hi):.2f}～{max(hi):.2f}（合成資料，非真實績效）")
    return 0


def registry_v() -> dict:
    from r1s3_gate_killtest_1990_2003 import registry_v as rv
    return rv()


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    check_prereg()
    if OUT.exists():
        raise SystemExit(f"結果檔 {OUT.name} 已存在——本試驗只跑一次，拒絕重跑")
    import selection_bias_ledger as S
    n_total = len(S.parse())
    prog(f"事前登記核對通過；帳本總 N＝{n_total}")
    df = load_taiex()
    dates = df["date"]
    r = df["close"].pct_change().fillna(0.0).to_numpy(float)
    per = dates.dt.to_period("M").to_numpy()
    bh = r.copy()
    from candidate_report import CandidateStats, deflated_sharpe
    V = registry_v()
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG, "prereg_sha256": PREREG_SHA, "prereg_trial_id": PREREG_TRIAL,
           "period": {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": len(df)},
           "data": "TWSE FMTQIK 發行量加權股價指數（價格指數，不含息），#436 快取",
           "rule": {"exposure": "clip(median(RV 過去≤36月)/RV(m), 0.5, 1.5)，前 6 月 1.0，延後一交易日", "bounds": [E_LO, E_HI]},
           "assumptions": {"cash_return": 0.0, "financing_primary": FIN_PRIMARY, "financing_sensitivity": FIN_SENS,
                           "mgmt_2x": MGMT, "sell_tax": SELL_TAX, "fee_each_side": FEE},
           "buy_hold": {"cagr": cagr(bh), "mdd": mdd(bh), "sharpe": sharpe(bh), "bear_segments": seg_stats(bh, dates)},
           "dsr_V": V, "N_total": n_total, "trials": {}}
    for form in ("variance", "volatility"):
        months, dec = decisions(r, per, form)
        for fin in (FIN_PRIMARY, FIN_SENS):
            primary = form == "variance" and fin == FIN_PRIMARY
            x, expo = simulate(r, per, months, dec, fin)
            ctl = random_controls(r, per, months, dec, fin) if primary else None
            ex = x - bh
            sk = float(pd.Series(ex[1:]).skew()); ku = float(pd.Series(ex[1:]).kurt()) + 3.0
            dsr = None
            if V["V_daily"]:
                st = CandidateStats(float(ex[1:].mean() / ex[1:].std(ddof=1)), len(ex) - 1, sk, ku, 252)
                dsr = {k: deflated_sharpe(st, n_total, V["V_daily"] * mlt, var_periods_per_year=252) for k, mlt in (("V", 1.0), ("V×0.5", 0.5), ("V×2", 2.0))}
            tail = dec[WARMUP_MONTHS - 1:]
            t = {"form": form, "financing": fin, "primary": primary, "cagr": cagr(x), "mdd": mdd(x), "sharpe": sharpe(x),
                 "exposure": {"mean_monthly": float(np.mean(dec)), "mean_daily": float(np.mean(expo)),
                              "months_at_0.5": int(sum(1 for v in tail if v <= E_LO)), "months_at_1.5": int(sum(1 for v in tail if v >= E_HI)),
                              "months_changed": int(sum(1 for a, b in zip(dec[:-1], dec[1:]) if a != b))},
                 "bear_segments": seg_stats(x, dates), "dsr_excess_vs_buy_hold": dsr,
                 "excess_stats": {"sharpe_daily": float(ex[1:].mean() / ex[1:].std(ddof=1)), "n": len(ex) - 1, "skew": sk, "kurt": ku}}
            if ctl:
                sh = ctl.pop("_sharpes")
                ctl["strategy_sharpe_percentile"] = float(np.mean(sh < t["sharpe"]) * 100)
                t["random_control"] = ctl
                c1, c2, c3 = t["mdd"] > SURVIVAL, t["cagr"] >= res["buy_hold"]["cagr"], t["sharpe"] > ctl["sharpe"]["p95"]
                t["criteria"] = {"mdd_gt_-50%": c1, "cagr_ge_buy_hold": c2, "sharpe_gt_random_p95": c3}
            res["trials"][f"{form}@fin{int(fin * 100)}%"] = t
    p = res["trials"]["variance@fin8%"]
    c = p["criteria"]
    res["verdict"] = "VIOLATES_SURVIVAL" if not c["mdd_gt_-50%"] else ("PASS" if c["cagr_ge_buy_hold"] and c["sharpe_gt_random_p95"] else "FAIL")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    prog(f"結果已寫入 {OUT.name}（以下才印績效）")
    print(f"期間 {res['period']['start']}～{res['period']['end']}（{res['period']['n_days']} 日）")
    b = res["buy_hold"]
    print(f"買進持有：年化 {b['cagr'] * 100:.2f}%、MDD {b['mdd'] * 100:.2f}%、Sharpe {b['sharpe']:.3f}")
    for k, t in res["trials"].items():
        e = t["exposure"]
        print(f"{k}{'（主判定）' if t['primary'] else ''}：年化 {t['cagr'] * 100:.2f}%、MDD {t['mdd'] * 100:.2f}%、Sharpe {t['sharpe']:.3f}；"
              f"平均曝險 {e['mean_daily']:.3f}、觸 0.5 下限 {e['months_at_0.5']} 月、觸 1.5 上限 {e['months_at_1.5']} 月")
    rc = p["random_control"]
    print(f"隨機對照（{rc['n']} 條）Sharpe p5/p50/p95＝{rc['sharpe']['p5']:.3f}/{rc['sharpe']['p50']:.3f}/{rc['sharpe']['p95']:.3f}；策略位於第 {rc['strategy_sharpe_percentile']:.1f} 百分位；"
          f"隨機對照 MDD>−50% 比例 {rc['share_mdd_gt_-50%'] * 100:.1f}%")
    print(f"判準：{c}")
    print("判定：" + res["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
