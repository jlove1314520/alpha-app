# -*- coding: utf-8 -*-
"""先.九十-1／先.八十三-3d-1：B4 台指 VRP（#35）2002–2014 定稿前的資料前置檢查。

只做兩件事，**不算任何 IV、RV 或報酬**（那是試驗本身，要定稿登記後才准跑）：
1. 補加權指數 2010–2014 開收盤（TWSE MI_5MINS_HIST，每月 1 次、間隔 ≥4 秒；1999–2009 已由 #441 快取）。
2. 流動性：照 `vrp_gate.py` 的抽樣規則（每 5 個交易日、只用月合約、距到期最接近 30 天且在 [10,45] 天），
   每個抽樣日取離指數收盤最近的履約價，看 call／put 兩邊成交量是否都 > 0。比例 < 80% → 草稿改判資料不足、不登記。
資料：research/data/raw/taifex_opt_yearly/YYYY.zip（期交所 optDataDown 年度檔，先.八十六-2c）。
輸出：research/data/txo_vrp_prereq_2002_2014.json
"""
import calendar
import json
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_IDX = ROOT / "research" / "data" / "raw" / "twse_mi_5mins_hist"
RAW_OPT = ROOT / "research" / "data" / "raw" / "taifex_opt_yearly"
OUT = ROOT / "research" / "data" / "txo_vrp_prereq_2002_2014.json"
YEARS = range(2002, 2015)
THRESHOLD = 0.80
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def index_closes():
    RAW_IDX.mkdir(parents=True, exist_ok=True)
    out = {}
    for y in YEARS:
        for m in range(1, 13):
            f = RAW_IDX / f"{y}{m:02d}.json"
            if not f.exists():
                r = requests.get("https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST",
                                 params={"date": f"{y}{m:02d}01", "response": "json"},
                                 headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
                if r.status_code in (402, 403, 428, 429):
                    raise SystemExit(f"TWSE {r.status_code}，停止")
                f.write_text(json.dumps(r.json(), ensure_ascii=False), encoding="utf-8")
                time.sleep(4)
            for d in json.loads(f.read_text(encoding="utf-8")).get("data") or []:
                yy, mm, dd = (int(x) for x in d[0].split("/"))
                out[date(yy + 1911, mm, dd).isoformat()] = float(str(d[4]).replace(",", ""))
    return dict(sorted(out.items()))


def third_wednesday(ym):
    y, m = int(ym[:4]), int(ym[4:6])
    c = calendar.Calendar().monthdatescalendar(y, m)
    weds = [d for wk in c for d in wk if d.weekday() == 2 and d.month == m]
    return weds[2]


def load_opt():
    """{date: {contract_month: {strike: {'C': vol, 'P': vol}}}}，只留月合約。"""
    opt = {}
    for y in YEARS:
        z = zipfile.ZipFile(RAW_OPT / f"{y}.zip")
        for n in z.namelist():
            for ln in z.read(n).decode("big5", errors="replace").splitlines()[1:]:
                p = [x.strip() for x in ln.split(",")]
                if len(p) < 10 or p[1] != "TXO" or not (len(p[2]) == 6 and p[2].isdigit()):
                    continue
                cp = "C" if p[4] in ("買權", "Call", "C") else ("P" if p[4] in ("賣權", "Put", "P") else None)
                if cp is None:
                    continue
                try:
                    k, vol = float(p[3]), float(p[9] or 0)
                except ValueError:
                    continue
                y_, m_, d_ = (int(x) for x in p[0].split("/"))  # 年度檔日期不補零（2002/1/2）
                dt = date(y_, m_, d_).isoformat()
                opt.setdefault(dt, {}).setdefault(p[2], {}).setdefault(k, {})[cp] = vol
    return opt


def main():
    idx = index_closes()
    opt = load_opt()
    days = [d for d in sorted(opt) if d in idx]
    sampled = days[::5]
    rows, skipped = [], 0
    for d in sampled:
        dd = date.fromisoformat(d)
        cands = []
        for cm in opt[d]:
            dte = (third_wednesday(cm) - dd).days
            if 10 <= dte <= 45:
                cands.append((abs(dte - 30), cm))
        if not cands:
            skipped += 1
            continue
        cm = min(cands)[1]
        strikes = opt[d][cm]
        k = min(strikes, key=lambda x: abs(x - idx[d]))
        v = strikes[k]
        rows.append({"date": d, "both_traded": v.get("C", 0) > 0 and v.get("P", 0) > 0})
    by_year = {}
    for r in rows:
        y = r["date"][:4]
        by_year.setdefault(y, [0, 0])
        by_year[y][0] += r["both_traded"]
        by_year[y][1] += 1
    share = sum(r["both_traded"] for r in rows) / len(rows)
    res = {"generated_for": "先.九十-1 B4 定稿前置（不含任何 IV／RV／報酬）",
           "option_trading_days": len(days), "sampled_days": len(sampled), "usable_samples": len(rows),
           "skipped_no_contract_in_10_45d": skipped,
           "both_sides_traded_share": round(share, 4), "threshold": THRESHOLD, "pass": share >= THRESHOLD,
           "by_year": {y: {"both": a, "n": b, "share": round(a / b, 3)} for y, (a, b) in sorted(by_year.items())},
           "index_days_2002_2014": sum(1 for d in idx if "2002-01-01" <= d <= "2014-12-31")}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
