# -*- coding: utf-8 -*-
"""先.八十-13：R1／S3 信用利差閘門 1990–2003 台股殺測（單發）。

定義全部事前綁定於 docs/PREREG_R1S3_gate_killtest_1990_2003.md（登記 #435，SHA256 見 PREREG_SHA，commit 3753f7d01）。
**只跑一次；績效數字一律在 JSON 寫完後才印。** 不讀 2003-07 以後任何資料；holdout 未動。

資料：TWSE FMTQIK「發行量加權股價指數」（逐月，間隔 ≥3 秒，快取 research/data/raw/fmtqik_taiex_1990_2003.json）；
FRED 月資料 BAA、GS10（fred_yield_curve_gate.fetch_fred_series，既有金鑰流程，不印金鑰）。
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PREREG = "docs/PREREG_R1S3_gate_killtest_1990_2003.md"
PREREG_SHA = "02cc8b96d7bc6cbc8d3f306787771c0ccfdbfeddcb7503ff1e272c13d75cadcf"
PREREG_TRIAL = 435
OUT = HERE / "data" / "r1s3_gate_killtest_1990_2003_result.json"
CACHE = HERE / "data" / "raw" / "fmtqik_taiex_1990_2003.json"
START, END = "1990-01-01", "2003-06-30"
FMTQIK = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
FIN_PRIMARY, FIN_SENS = 0.08, 0.04
MGMT = 0.01            # #421：2 倍腿年 1%
SELL_TAX = 0.001       # #418：台股 ETF 賣出稅
FEE = 0.001425         # 雙邊手續費（比 #418 保守）
SURVIVAL = -0.50
GROUPS = {"R1-C": {"open": (0.50, 0.50, 0.00), "closed": (0.50, 0.00, 0.50)},
          "R1-A": {"open": (0.70, 0.30, 0.00), "closed": (0.70, 0.00, 0.30)}}
BEAR = {"1990": ("1990-01-01", "1990-12-31"), "1997-1998": ("1997-07-01", "1998-12-31"), "2000-2001": ("2000-02-01", "2001-12-31")}


def prog(m: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def check_prereg() -> None:
    h = hashlib.sha256((ROOT / PREREG).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if h != PREREG_SHA:
        raise SystemExit(f"事前登記文件 SHA256 不符（{h}），拒絕執行")


def fetch_taiex() -> pd.DataFrame:
    if CACHE.exists():
        rows = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        rows, last = [], 0.0
        for y in range(1990, 2004):
            for m in range(1, 13):
                if (y, m) > (2003, 6):
                    break
                w = 3.0 - (time.time() - last)
                if w > 0:
                    time.sleep(w)
                last = time.time()
                r = requests.get(FMTQIK, params={"date": f"{y}{m:02d}01", "response": "json"}, timeout=30)
                if r.status_code in (402, 403, 428, 429):
                    raise SystemExit(f"TWSE 回 HTTP {r.status_code}，停止（不重試）")
                j = r.json()
                if j.get("stat") != "OK":
                    raise SystemExit(f"FMTQIK {y}-{m:02d} 無資料：{j.get('stat')}")
                f = j["fields"]
                i_d, i_x = f.index("日期"), f.index("發行量加權股價指數")
                for row in j["data"]:
                    ry, rm, rd = [int(x) for x in row[i_d].strip().split("/")]
                    rows.append({"date": f"{ry + 1911}-{rm:02d}-{rd:02d}", "close": float(row[i_x].replace(",", ""))})
                prog(f"FMTQIK {y}-{m:02d}：{len(j['data'])} 日")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= START) & (df["date"] <= END)].reset_index(drop=True)
    return df


def fetch_spread() -> pd.Series:
    from fred_yield_curve_gate import fetch_fred_series
    b = fetch_fred_series("BAA", "1989-01-01")
    g = fetch_fred_series("GS10", "1989-01-01")
    sb = pd.Series(b["value"].astype(float).to_numpy(), index=pd.to_datetime(b["date"]).dt.to_period("M"))
    sg = pd.Series(g["value"].astype(float).to_numpy(), index=pd.to_datetime(g["date"]).dt.to_period("M"))
    s = (sb - sg).dropna()
    return s[s.index <= pd.Period(END[:7], "M")]


def gate_by_month(spread: pd.Series, months: list) -> dict:
    """m 月底的閘門：只用 m−1 月以前的利差；S(m−1) > mean(S(m−12..m−1)) → 關（False）。資料不足 12 個月 → 開。"""
    out = {}
    for m in months:
        hist = spread[spread.index <= m - 1]
        if len(hist) < 12:
            out[m] = True
            continue
        last12 = hist.iloc[-12:]
        out[m] = not (last12.iloc[-1] > last12.mean())
    return out


def simulate(df: pd.DataFrame, gate: dict, group: dict, fin: float) -> tuple[np.ndarray, dict]:
    r = df["close"].pct_change().fillna(0.0).to_numpy(float)
    r2 = 2.0 * r - fin / 252.0 - MGMT / 252.0
    per = df["date"].dt.to_period("M").to_numpy()
    n = len(df)
    is_me = np.r_[per[1:] != per[:-1], True]          # 每月最後一個交易日
    # 月底判定 → 隔一個交易日收盤生效；判定前沿用前一個狀態
    state = np.ones(n, bool)
    cur = True
    pending = None
    switches = 0
    for i in range(n):
        if pending is not None:
            if pending != cur:
                switches += 1
            cur = pending
            pending = None
        state[i] = cur
        if is_me[i]:
            pending = gate[per[i]]
    w = np.array(group["open"] if state[0] else group["closed"], float)
    out = np.zeros(n)
    for i in range(1, n):
        g = np.array([r[i], r2[i], 0.0])
        port = float(w @ (1.0 + g))
        out[i] = port - 1.0
        w = w * (1.0 + g) / port                      # 漂移
        tgt = np.array(group["open"] if state[i] else group["closed"], float)
        if is_me[i] or (state[i] != state[i - 1]):
            d = tgt - w
            cost = float(np.sum(np.clip(-d, 0, None)) * (SELL_TAX + FEE) + np.sum(np.clip(d, 0, None)) * FEE)
            out[i] = (1.0 + out[i]) * (1.0 - cost) - 1.0
            w = tgt.copy()
    months_open = int(sum(1 for m in set(per) if gate.get(m, True)))
    return out, {"switches": switches, "months_open_at_month_end": months_open, "months": len(set(per))}


def mdd(r: np.ndarray) -> float:
    v = np.cumprod(1.0 + r)
    return float(np.min(v / np.maximum.accumulate(v) - 1.0))


def cagr(r: np.ndarray) -> float:
    return float(np.prod(1.0 + r) ** (252.0 / max(len(r) - 1, 1)) - 1.0)


def seg_stats(r: np.ndarray, dates: pd.Series) -> dict:
    o = {}
    for k, (a, b) in BEAR.items():
        m = ((dates >= a) & (dates <= b)).to_numpy()
        o[k] = {"ret": float(np.prod(1 + r[m]) - 1), "mdd": mdd(r[m])} if m.sum() > 2 else None
    return o


def registry_v() -> dict:
    sh = []
    for ln in (HERE / "TRIALS_REGISTRY.jsonl").read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        di = (json.loads(ln).get("dsr_inputs") or {})
        s, ppy = di.get("sharpe"), di.get("periods_per_year")
        if isinstance(s, (int, float)) and isinstance(ppy, (int, float)) and ppy > 0 and math.isfinite(s):
            sh.append(s * math.sqrt(ppy / 252.0))
    return {"V_daily": float(np.var(sh, ddof=1)) if len(sh) > 2 else None, "n_sharpes": len(sh),
            "note": "V 取自 TRIALS_REGISTRY.jsonl dsr_inputs（僅有 Sharpe 記錄者，非全體；多為絕對報酬 Sharpe，非超額）"}


def main() -> int:
    check_prereg()
    import selection_bias_ledger as S
    n_total = len(S.parse())
    prog(f"事前登記核對通過；帳本總 N＝{n_total}")
    df = fetch_taiex()
    spread = fetch_spread()
    months = sorted(set(df["date"].dt.to_period("M")))
    gate = gate_by_month(spread, months)
    dates = df["date"]
    bh = df["close"].pct_change().fillna(0.0).to_numpy(float)
    from candidate_report import CandidateStats, deflated_sharpe
    V = registry_v()
    res = {"generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
           "prereg": PREREG, "prereg_sha256": PREREG_SHA, "prereg_trial_id": PREREG_TRIAL,
           "period": {"start": str(dates.iloc[0].date()), "end": str(dates.iloc[-1].date()), "n_days": len(df)},
           "data": {"taiex": "TWSE FMTQIK 發行量加權股價指數（價格指數，不含息）", "spread": "FRED BAA − GS10 月資料（m 月底只用到 m−1 月）",
                    "spread_months": len(spread)},
           "assumptions": {"cash_return": 0.0, "financing_primary": FIN_PRIMARY, "financing_sensitivity": FIN_SENS,
                           "mgmt_2x": MGMT, "sell_tax": SELL_TAX, "fee_each_side": FEE},
           "gate": {"months": len(months), "months_open": int(sum(gate.values())), "months_closed": int(len(months) - sum(gate.values()))},
           "buy_hold": {"cagr": cagr(bh), "mdd": mdd(bh), "bear_segments": seg_stats(bh, dates)},
           "dsr_V": V, "N_total": n_total, "trials": {}}
    for g, grp in GROUPS.items():
        for fin in (FIN_PRIMARY, FIN_SENS):
            r, info = simulate(df, gate, grp, fin)
            ex = r - bh
            sk = float(pd.Series(ex[1:]).skew()); ku = float(pd.Series(ex[1:]).kurt()) + 3.0
            d = None
            if V["V_daily"]:
                d = {}
                for k, mult in (("V", 1.0), ("V×0.5", 0.5), ("V×2", 2.0)):
                    st = CandidateStats(float(ex[1:].mean() / ex[1:].std(ddof=1)), len(ex) - 1, sk, ku, 252)
                    d[k] = deflated_sharpe(st, n_total, V["V_daily"] * mult, var_periods_per_year=252)
            c, m = cagr(r), mdd(r)
            ok_mdd, ok_cagr = m > SURVIVAL, c >= res["buy_hold"]["cagr"]
            res["trials"][f"{g}@fin{int(fin * 100)}%"] = {
                "group": g, "financing": fin, "cagr": c, "mdd": m, "info": info, "bear_segments": seg_stats(r, dates),
                "criteria": {"mdd_gt_-50%": ok_mdd, "cagr_ge_buy_hold": ok_cagr}, "pass": bool(ok_mdd and ok_cagr),
                "dsr_excess_vs_buy_hold": d, "primary": g == "R1-C" and fin == FIN_PRIMARY}
    prim = res["trials"]["R1-C@fin8%"]
    res["verdict"] = "PASS" if prim["pass"] else ("VIOLATES_SURVIVAL" if not prim["criteria"]["mdd_gt_-50%"] else "FAIL")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    prog(f"結果已寫入 {OUT.name}（以下才印績效）")
    print(f"期間 {res['period']['start']}～{res['period']['end']}（{res['period']['n_days']} 日）；閘門開 {res['gate']['months_open']}／{res['gate']['months']} 個月")
    print(f"買進持有：年化 {res['buy_hold']['cagr'] * 100:.2f}%、MDD {res['buy_hold']['mdd'] * 100:.2f}%")
    for k, t in res["trials"].items():
        print(f"{k}：年化 {t['cagr'] * 100:.2f}%、MDD {t['mdd'] * 100:.2f}%、切換 {t['info']['switches']} 次 → {'PASS' if t['pass'] else 'FAIL'}"
              + ("（主判定）" if t["primary"] else ""))
    print("判定：" + res["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
