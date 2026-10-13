# -*- coding: utf-8 -*-
"""試驗 #441：#49 隔夜／盤中分解 1999–2009 單發（先.八十五-3）。

定稿：docs/PREREG_overnight_intraday_1999_2009_FINAL.md（SHA256 9b5d8e2a…，commit ca087ccf6），登記 cf453c043。
只跑一次；不讀 2010 以後資料。原始檔快取在 research/data/raw/（gitignored）。
用法：python research/overnight_1999_2009.py
"""
import io
import json
import math
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_IDX = ROOT / "research" / "data" / "raw" / "twse_mi_5mins_hist"
RAW_FUT = ROOT / "research" / "data" / "raw" / "taifex_fut_yearly"
OUT = ROOT / "research" / "data" / "overnight_1999_2009_result.json"
YEARS = range(1999, 2010)
UA = {"User-Agent": "Mozilla/5.0"}
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fetch_index():
    RAW_IDX.mkdir(parents=True, exist_ok=True)
    rows = {}
    for y in YEARS:
        for m in range(1, 13):
            f = RAW_IDX / f"{y}{m:02d}.json"
            if not f.exists():
                r = requests.get("https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST",
                                 params={"date": f"{y}{m:02d}01", "response": "json"}, headers=UA, timeout=30)
                if r.status_code in (402, 403, 428, 429):
                    raise SystemExit(f"TWSE {r.status_code}，停止")
                j = r.json()
                f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
                time.sleep(4)
            j = json.loads(f.read_text(encoding="utf-8"))
            for d in j.get("data") or []:
                yy, mm, dd = (int(x) for x in d[0].split("/"))
                dt = date(yy + 1911, mm, dd).isoformat()
                o, c = (float(str(x).replace(",", "")) for x in (d[1], d[4]))
                rows[dt] = (o, c)
    return dict(sorted(rows.items()))


def fetch_fut():
    RAW_FUT.mkdir(parents=True, exist_ok=True)
    tx = {}  # date -> {contract_month: (open, close)}
    for y in YEARS:
        f = RAW_FUT / f"{y}.zip"
        if not f.exists():
            r = requests.post("https://www.taifex.com.tw/cht/3/futDataDown",
                              data={"down_type": "2", "his_year": str(y)}, headers=UA, timeout=60)
            if r.status_code in (402, 403, 428, 429):
                raise SystemExit(f"TAIFEX {r.status_code}，停止")
            f.write_bytes(r.content)
            time.sleep(3)
        z = zipfile.ZipFile(f)
        for n in z.namelist():
            text = z.read(n).decode("big5", errors="replace")
            for ln in text.splitlines()[1:]:
                p = [x.strip() for x in ln.split(",")]
                if len(p) < 7 or p[1] != "TX" or "/" in p[2]:
                    continue
                if len(p) > 17 and p[17] and p[17] != "一般":  # 交易時段欄（若有）只取一般
                    continue
                dt = p[0].replace("/", "-")

                def num(s):
                    try:
                        v = float(s)
                        return v if v > 0 else None
                    except ValueError:
                        return None
                tx.setdefault(dt, {})[p[2]] = (num(p[3]), num(p[6]))
    return dict(sorted(tx.items()))


def ttest_one_sided(xs):
    n = len(xs)
    mu = sum(xs) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
    t = mu / (sd / math.sqrt(n))
    p = 0.5 * math.erfc(t / math.sqrt(2))  # n>2000，常態近似
    return mu, t, p


def tax_rate(dt, ref=False):
    if dt >= "2008-10-06":
        return 0.00004
    if dt >= "2006-01-01":
        return 0.0001
    return 0.00025 if ref else 0.0006


def mdd(rets):
    nav, peak, worst = 1.0, 1.0, 0.0
    for r in rets:
        nav *= 1 + r
        peak = max(peak, nav)
        worst = max(worst, 1 - nav / peak)
    return worst


def sortino(rets):
    mu = sum(rets) / len(rets)
    dn = math.sqrt(sum(min(r, 0) ** 2 for r in rets) / len(rets))
    return mu / dn * math.sqrt(252) if dn else None


def main():
    idx = fetch_index()
    days = [d for d in idx if "1999-01-01" <= d <= "2009-12-31"]
    on, idr, by_year = [], [], {}
    for a, b in zip(days, days[1:]):
        o, c = idx[b]
        x = math.log(o / idx[a][1])
        on.append(x)
        idr.append(math.log(c / o))
        by_year.setdefault(b[:4], {"on": [], "id": []})
        by_year[b[:4]]["on"].append(x)
        by_year[b[:4]]["id"].append(math.log(c / o))
    mu, t, p = ttest_one_sided(on)
    yr = {y: {"overnight_mean": sum(v["on"]) / len(v["on"]), "intraday_mean": sum(v["id"]) / len(v["id"]),
              "n": len(v["on"])} for y, v in sorted(by_year.items())}
    pos_years = sum(1 for v in yr.values() if v["overnight_mean"] > 0)
    gate_a, gate_b = (mu > 0 and p < 0.05), pos_years >= 10
    res = {"trial": 441, "prereg": "docs/PREREG_overnight_intraday_1999_2009_FINAL.md",
           "layer1": {"n_days": len(on), "overnight_mean_log": mu, "t": t, "p_one_sided": p,
                      "intraday_mean_log": sum(idr) / len(idr), "pos_years": pos_years, "years": len(yr),
                      "by_year": yr, "gate_a": gate_a, "gate_b": gate_b}}
    verdict = None
    if not (gate_a and gate_b):
        verdict = "FAIL"
    else:
        tx = fetch_fut()
        fdays = [d for d in tx if "1999-01-01" <= d <= "2009-12-31"]
        last_seen = {}
        for d in fdays:
            for cm in tx[d]:
                last_seen[cm] = d
        if len(fdays) < 0.9 * len(days):
            verdict = "DATA_UNAVAILABLE"
            res["layer2"] = {"note": f"期貨交易日 {len(fdays)} 遠少於指數 {len(days)}"}
        else:
            nets = {1: [], 2: [], 3: []}
            ref1, gross, missing, pairs = [], [], 0, []
            for a, b in zip(fdays, fdays[1:]):
                cms = sorted(cm for cm in tx[a] if last_seen[cm] != a)
                if not cms:
                    missing += 1
                    continue
                cm = cms[0]
                pc = tx[a][cm][1]
                op = (tx[b].get(cm) or (None, None))[0]
                if not pc or not op:
                    missing += 1
                    continue
                g = (op - pc) / pc
                fee = 2 * 50 / (pc * 200)
                gross.append(g)
                pairs.append(b)
                for s in (1, 2, 3):
                    nets[s].append(g - 2 * tax_rate(b) - fee - 2 * s / pc)
                ref1.append(g - 2 * tax_rate(b, ref=True) - fee - 2 / pc)
            seg = lambda lo, hi: mdd([r for d, r in zip(pairs, nets[1]) if lo <= d <= hi])
            means = {s: sum(v) / len(v) for s, v in nets.items()}
            gate_c = all(m > 0 for m in means.values())
            m_all, m_0001, m_2008 = mdd(nets[1]), seg("2000-01-01", "2001-12-31"), seg("2008-01-01", "2008-12-31")
            gate_d = max(m_all, m_0001, m_2008) <= 0.5
            bench = [idx[b][1] / idx[a][1] - 1 for a, b in zip(days, days[1:])]
            res["layer2"] = {"n_pairs": len(gross), "missing": missing, "gross_mean": sum(gross) / len(gross),
                             "net_mean_by_slippage_pts": means, "ref_tax_0.025pct_s1_mean": sum(ref1) / len(ref1),
                             "mdd_s1_all": m_all, "mdd_s1_2000_2001": m_0001, "mdd_s1_2008": m_2008,
                             "sortino_s1": sortino(nets[1]), "gate_c": gate_c, "gate_d": gate_d,
                             "benchmark_taiex_bh": {"sortino": sortino(bench), "mdd": mdd(bench)}}
            verdict = "VIOLATES_SURVIVAL" if not gate_d else ("PASS" if gate_c else "FAIL")
    res["verdict"] = verdict
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
