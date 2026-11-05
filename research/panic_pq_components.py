# -*- coding: utf-8 -*-
"""先.一五〇-2 策略工廠第一題：「恐慌求生日買進 PQ 毛利成長股」——兩個元件（研究帽產物，因子程式碼）。

本支只產生元件、不回測、不判定（做與判分離；回測／優化另一輪做，規格見 research/PANIC_PQ_SPEC.md）。
零網路請求：只讀本機 FinMind 快取 `research/data/raw/*.parquet`，且一律截到 2024-12-31（holdout 不碰）。

元件①恐慌指標（每日）
  - n_limit_down：當天收盤鎖跌停的普通股檔數（4 碼數字代號、成交量>0、收盤＝最低、
    跌幅達漲跌幅限制：2015-06-01 前 7%、之後 10%；參考價＝close − spread，所以除權息日用的是官方參考價）。
    「跌停無買盤」需要委託簿，本機沒有歷史 → 用「收盤＝最低＝跌停」近似「鎖跌停」，照實標註。
  - frac_limit_down：n_limit_down ÷ 當天有成交的普通股檔數。
  - tpex_ret／taiex_ret：櫃買指數、加權指數當日報酬。
  - 融資維持率驟降、停資停券、CB 跌停：本機沒有全市場歷史（融資快取只有 624 檔、停資停券預告表只能每日累積、
    CB 逐日行情屬 FinMind 付費層），本版不納入，SPEC 記為缺口。
元件②PQ 成長名單（每季快照，PIT）
  - 單季毛利率年增（pp）、單季營益率年增（pp）、單季 EPS 年增、近四季 EPS 合計、近 3 個月營收年增。
  - 可得日〔自行裁量，取新舊法規較晚者〕：Q1→05-15、Q2→08-31、Q3→11-14、Q4→次年 04-30；
    月營收：FinMind date（次月 1 日）＋9 天＝次月 10 日。
輸出：research/data/panic_pq/panic_daily.csv、pq_snapshots.csv、build_meta.json。
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from validation import holdout  # noqa: E402

RAW = HERE / "data" / "raw"
OUT = HERE / "data" / "panic_pq"
END = "2024-12-31"
START = "2005-01-01"
LIMIT_SWITCH = "2015-06-01"
STOCK_RE = re.compile(r"^[1-9]\d{3}$")


def _files_by_id(dataset: str) -> dict[str, list[Path]]:
    out = defaultdict(list)
    for p in RAW.glob(f"{dataset}__*.parquet"):
        parts = p.name.split("__")
        if len(parts) >= 2:
            out[parts[1]].append(p)
    return out


def _load(paths: list[Path], cols: list[str] | None, key: list[str]) -> pd.DataFrame:
    frames = []
    for p in paths:
        try:
            frames.append(pd.read_parquet(p, columns=cols))
        except Exception as e:  # 單檔壞掉只略過，記警告
            print(f"[warn] 讀不到 {p.name}：{e}")
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df[(df["date"] <= END) & (df["date"] >= START)]
    return df.drop_duplicates(subset=key, keep="last")


def build_panic() -> tuple[pd.DataFrame, dict]:
    files = _files_by_id("TaiwanStockPrice")
    ids = [s for s in files if STOCK_RE.match(s)]
    cnt_trade = defaultdict(int)
    cnt_ld = defaultdict(int)
    cnt_lu = defaultdict(int)
    last_dates = {}
    cols = ["date", "Trading_Volume", "max", "min", "close", "spread"]
    for i, sid in enumerate(ids):
        d = _load(files[sid], cols, ["date"])
        if d.empty:
            continue
        d = d[d["Trading_Volume"] > 0]
        last_dates[sid] = d["date"].max()
        ref = d["close"] - d["spread"]
        ok = ref > 0
        d, ref = d[ok], ref[ok]
        lim = np.where(d["date"] < LIMIT_SWITCH, 0.07, 0.10)
        ret = d["close"] / ref - 1.0
        # 檔位取整讓實際跌停幅度略小於 7%/10%（例：9.61%），容忍 0.6pp
        is_ld = (ret <= -(lim - 0.006)) & (d["close"] <= d["min"] + 1e-9)
        is_lu = (ret >= (lim - 0.006)) & (d["close"] >= d["max"] - 1e-9)
        for dt in d["date"].values:
            cnt_trade[dt] += 1
        for dt in d.loc[is_ld.values, "date"].values:
            cnt_ld[dt] += 1
        for dt in d.loc[is_lu.values, "date"].values:
            cnt_lu[dt] += 1
        if i % 500 == 0:
            print(f"價格 {i}/{len(ids)}")
    dates = sorted(cnt_trade)
    pan = pd.DataFrame({"date": dates,
                        "n_traded": [cnt_trade[x] for x in dates],
                        "n_limit_down": [cnt_ld.get(x, 0) for x in dates],
                        "n_limit_up": [cnt_lu.get(x, 0) for x in dates]})
    pan["frac_limit_down"] = pan["n_limit_down"] / pan["n_traded"]
    for idx, name in (("TAIEX", "taiex_ret"), ("TPEx", "tpex_ret")):
        f = _files_by_id("TaiwanStockPrice").get(idx, [])
        ix = _load(f, ["date", "close"], ["date"]).sort_values("date")
        ix[name] = ix["close"].pct_change()
        pan = pan.merge(ix[["date", name]], on="date", how="left")
    holdout.assert_no_holdout_leakage(pan, date_col="date", context="panic_pq panic_daily")
    n_dead = sum(1 for v in last_dates.values() if v < "2024-06-01")
    meta = {"price_ids": len(ids), "ids_last_trade_before_2024_06": n_dead}
    return pan, meta


Q_AVAIL = {3: "05-15", 6: "08-31", 9: "11-14", 12: "04-30"}


def _avail_date(qdate: str) -> str:
    y, m = int(qdate[:4]), int(qdate[5:7])
    return f"{y + 1 if m == 12 else y}-{Q_AVAIL[m]}"


def build_pq() -> tuple[pd.DataFrame, dict]:
    ffiles = _files_by_id("TaiwanStockFinancialStatements")
    rfiles = _files_by_id("TaiwanStockMonthRevenue")
    need = {"Revenue", "GrossProfit", "OperatingIncome", "EPS"}
    rows = []
    for i, sid in enumerate(s for s in ffiles if STOCK_RE.match(s)):
        f = _load(ffiles[sid], ["date", "type", "value"], ["date", "type"])
        if f.empty:
            continue
        f = f[f["type"].isin(need)]
        w = f.pivot_table(index="date", columns="type", values="value", aggfunc="last").sort_index()
        if not need.issubset(w.columns):
            continue
        w = w[w.index.str[5:7].isin(["03", "06", "09", "12"])]
        w["gm"] = w["GrossProfit"] / w["Revenue"].where(w["Revenue"] > 0)
        w["om"] = w["OperatingIncome"] / w["Revenue"].where(w["Revenue"] > 0)
        # 同季去年：以日期字串年減 1 對齊（不靠位置，避免缺季錯位）
        prev = w.copy()
        prev.index = [f"{int(x[:4]) + 1}{x[4:]}" for x in prev.index]
        j = w.join(prev[["gm", "om", "EPS"]], rsuffix="_ly", how="left")
        j["eps_ttm"] = w["EPS"].rolling(4, min_periods=4).sum()
        rev = pd.DataFrame()
        if sid in rfiles:
            rev = _load(rfiles[sid], ["date", "revenue", "revenue_year", "revenue_month"], ["date"])
        for qd, r in j.iterrows():
            av = _avail_date(qd)
            rec = {"stock_id": sid, "quarter": qd, "avail": av,
                   "gm": r["gm"], "gm_yoy_pp": (r["gm"] - r["gm_ly"]) * 100,
                   "om": r["om"], "om_yoy_pp": (r["om"] - r["om_ly"]) * 100,
                   "eps": r["EPS"], "eps_ly": r["EPS_ly"], "eps_ttm": r["eps_ttm"]}
            if not rev.empty:
                # 可得日當下已公布的最近 3 個月營收 vs 去年同 3 個月
                rv = rev[(pd.to_datetime(rev["date"]) + pd.Timedelta(days=9)) <= pd.Timestamp(av)]
                rv = rv.assign(ym=rv["revenue_year"] * 100 + rv["revenue_month"]).set_index("ym")["revenue"]
                rv = rv[~rv.index.duplicated(keep="last")].sort_index()
                if len(rv) >= 3:
                    last3 = list(rv.index[-3:])
                    ly3 = [x - 100 for x in last3]
                    if all(x in rv.index for x in ly3) and rv.loc[ly3].sum() > 0:
                        rec["rev3m_yoy"] = rv.loc[last3].sum() / rv.loc[ly3].sum() - 1
            rows.append(rec)
        if i % 500 == 0:
            print(f"財報 {i}")
    pq = pd.DataFrame(rows)
    pq["eps_yoy"] = np.where(pq["eps_ly"] > 0, pq["eps"] / pq["eps_ly"] - 1, np.nan)
    pq = pq[pq["avail"] <= END]
    holdout.assert_no_holdout_leakage(pq.rename(columns={"avail": "date"}), date_col="date", context="panic_pq pq")
    return pq, {"fin_ids": int(pq["stock_id"].nunique()), "rows": int(len(pq))}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    pan, m1 = build_panic()
    pan.to_csv(OUT / "panic_daily.csv", index=False)
    print(f"恐慌日檔 {len(pan)} 天（{time.time()-t0:.0f}s）")
    pq, m2 = build_pq()
    pq.to_csv(OUT / "pq_snapshots.csv", index=False)
    meta = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "end": END, "start": START,
            "network_requests": 0, **m1, **m2, "seconds": round(time.time() - t0)}
    (OUT / "build_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
