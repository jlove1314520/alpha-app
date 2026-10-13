# -*- coding: utf-8 -*-
"""試驗 #443：台指選擇權 VRP（#35）2002–2014 單發（先.九十-1）。

定稿：docs/PREREG_txo_vrp_2002_2014_FINAL.md（SHA256 9291d958…，commit 148c80784），登記 2a457c96d。
第一層直接重用 vrp_gate.py 的函式；compute_forward_rv 的窗口上限改成 2014-12-31（定稿 §2）。只跑一次。
資料全是本機檔：TXO 年度檔（taifex_opt_yearly）、最後結算價（taifex_fsp）、指數（twse_mi_5mins_hist）。
用法：python research/txo_vrp_2002_2014.py
"""
import json
import math
import sys
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vrp_gate as V  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "data" / "raw"
OUT = ROOT / "research" / "data" / "txo_vrp_2002_2014_result.json"
END = "2014-12-31"
SPLIT = "2008-12-31"
YEARS = range(2002, 2015)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _d(s):
    y, m, d = (int(x) for x in s.split("/"))
    return date(y, m, d)


def option_frame():
    """與 vrp_gate.build_option_frame() 同欄位：date, contract_date, strike_price, call_close, put_close, expiry。"""
    rows = []
    for y in YEARS:
        z = zipfile.ZipFile(RAW / "taifex_opt_yearly" / f"{y}.zip")
        for n in z.namelist():
            for ln in z.read(n).decode("big5", errors="replace").splitlines()[1:]:
                p = [x.strip() for x in ln.split(",")]
                if len(p) < 9 or p[1] != "TXO" or not V.MONTHLY_CONTRACT_RE.match(p[2]):
                    continue
                cp = {"買權": "call", "賣權": "put"}.get(p[4])
                try:
                    k, c = float(p[3]), float(p[8])
                except ValueError:
                    continue
                if cp and c > 0:
                    rows.append((pd.Timestamp(_d(p[0])), p[2], k, cp, c))
    df = pd.DataFrame(rows, columns=["date", "contract_date", "strike_price", "call_put", "close"])
    calls = df[df.call_put == "call"].drop(columns="call_put").rename(columns={"close": "call_close"})
    puts = df[df.call_put == "put"].drop(columns="call_put").rename(columns={"close": "put_close"})
    m = calls.merge(puts, on=["date", "contract_date", "strike_price"], how="inner")
    m["expiry"] = m["contract_date"].map(lambda cd: V.third_wednesday(int(cd[:4]), int(cd[4:6])))
    return m


def taiex():
    rows = []
    for f in sorted((RAW / "twse_mi_5mins_hist").glob("*.json")):
        if not ("200201" <= f.stem <= "201412"):
            continue
        for d in json.loads(f.read_text(encoding="utf-8")).get("data") or []:
            yy, mm, dd = (int(x) for x in d[0].split("/"))
            rows.append((date(yy + 1911, mm, dd).isoformat(), float(str(d[4]).replace(",", ""))))
    return pd.DataFrame(sorted(rows), columns=["date", "close"])


def final_settlement():
    out = {}
    for y in YEARS:
        for ln in (RAW / "taifex_fsp" / f"{y}.csv").read_bytes().decode("big5", errors="replace").splitlines()[1:]:
            p = [x.strip() for x in ln.split(",")]
            if len(p) >= 5 and p[2] == "TXO" and V.MONTHLY_CONTRACT_RE.match(p[1]):
                out[p[1]] = float(p[4])
    return out


def tax_rate(d):
    return 0.001 if d >= pd.Timestamp("2006-01-01") else 0.006


def mdd(rets):
    nav = peak = 1.0
    worst = 0.0
    for r in rets:
        nav *= 1 + r
        peak = max(peak, nav)
        worst = max(worst, 1 - nav / peak)
    return worst


def sortino_m(rets):
    rets = list(rets)
    mu = sum(rets) / len(rets)
    dn = math.sqrt(sum(min(r, 0) ** 2 for r in rets) / len(rets))
    return mu / dn * math.sqrt(12) if dn else None


def main():
    V.VAL_END = END  # compute_forward_rv 讀模組常數；定稿 §2：窗口上限 2014-12-31
    import vrp_gate
    vrp_gate.VAL_END = END
    opt, tw = option_frame(), taiex()
    atm = V.select_atm_observations(opt, tw)
    res_rv = V.compute_forward_rv(atm, tw)
    sampled = res_rv.iloc[::V.SAMPLE_STRIDE].reset_index(drop=True)
    a = sampled[sampled["date"] <= pd.Timestamp(SPLIT)]
    b = sampled[sampled["date"] > pd.Timestamp(SPLIT)]
    ea, eb = V.evaluate_period(a["spread"], "A_2002_2008"), V.evaluate_period(b["spread"], "B_2009_2014")
    g1 = abs(ea["mean"]) >= 0.01 and abs(eb["mean"]) >= 0.01
    g2 = ea["mean"] > 0 and eb["mean"] > 0
    g3 = ea["t_p"] < 0.05 and eb["t_p"] < 0.05 and ea["wilcoxon_p"] < 0.05 and eb["wilcoxon_p"] < 0.05
    res = {"trial": 443, "prereg": "docs/PREREG_txo_vrp_2002_2014_FINAL.md",
           "layer1": {"n_atm": len(atm), "n_with_rv": len(res_rv), "n_sampled": len(sampled),
                      "A": ea, "B": eb, "gate_magnitude": bool(g1), "gate_same_sign_positive": bool(g2),
                      "gate_significance": bool(g3)}}
    if not (g1 and g2 and g3):
        res["verdict"] = "FAIL"
    else:
        fsp = final_settlement()
        # 每月第一筆抽樣觀測：重新找出當天被選中的合約與履約價（與 select_atm_observations 同規則）
        tw2 = tw.assign(date=pd.to_datetime(tw["date"])).rename(columns={"close": "taiex_close"})
        df = opt.merge(tw2, on="date")
        df["dte"] = (df["expiry"] - df["date"]).dt.days
        firsts = sampled.groupby(sampled["date"].dt.to_period("M")).first().reset_index(drop=True)
        months, nets, missing = [], {1: [], 2: [], 3: []}, 0
        for _, r in firsts.iterrows():
            day = df[(df["date"] == r["date"]) & (df["dte"] == r["dte_calendar"])]
            if day.empty:
                missing += 1
                continue
            row = day.loc[(day["strike_price"] - day["taiex_close"]).abs().idxmin()]
            F = fsp.get(row["contract_date"])
            if F is None:  # 定稿 §3：查不到才用結算日指數開盤代替（實測 156 個月全有）
                missing += 1
                continue
            prem = row["call_close"] + row["put_close"]
            cap = row["taiex_close"] * 50
            gross = (prem - abs(F - row["strike_price"])) * 50
            base_cost = 200 + tax_rate(row["date"]) * prem * 50
            months.append(str(row["date"].date()))
            for s in (1, 2, 3):
                nets[s].append((gross - base_cost - 2 * s * 50) / cap)
        means = {s: float(np.mean(v)) for s, v in nets.items()}
        in08 = [r for d, r in zip(months, nets[1]) if d.startswith("2008")]
        m_all, m_08 = mdd(nets[1]), mdd(in08)
        bench = tw.set_index(pd.to_datetime(tw["date"]))["close"].resample("ME").last().pct_change().dropna()
        gate_c = all(m > 0 for m in means.values())
        gate_d = max(m_all, m_08) <= 0.5
        res["layer2"] = {"n_months": len(months), "missing": missing, "net_mean_by_slippage_pts": means,
                         "mdd_s1_all": m_all, "mdd_s1_2008": m_08, "worst_month_s1": float(min(nets[1])),
                         "sortino_m_s1": sortino_m(nets[1]), "gate_c": gate_c, "gate_d": gate_d,
                         "benchmark_taiex_bh": {"sortino_m": sortino_m(bench), "mdd": mdd(bench)}}
        res["verdict"] = "VIOLATES_SURVIVAL" if not gate_d else ("PASS" if gate_c else "FAIL")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
