# -*- coding: utf-8 -*-
"""先.一三三-1c／收件匣 021（2026-10-23）：官方除權息補充事件 2007-07～2014（給 research/adjust.py 用）。零請求、不算任何報酬。

來源（DevQueue 已抓好存本機）：
- data/official_exright_2007_2014.csv：上市 TWT49U＋上櫃 exDailyQ 除權除息計算結果 7,946 筆（係數＝除權息參考價÷前收盤）；
- data/tpex_exright_2007h2_ref.json：上櫃 2007-07～12-16（exDailyQ 查不到）由日檔漲跌欄標記推出的事件 383 筆——
  341 筆用 FinMind 股利金額推精確參考價（matched）、42 筆沒有 FinMind 股利快取只能用近似參考價（unmatched，source 標 approx）。
輸出：
- data/official_exright_supplement_2007_2014.csv（ex_date, stock_id, market, prev_close, ref_price, factor, source）
- data/official_exright_supplement_report.json：與 FinMind 同日事件係數差 >1% 的清單、FinMind 漏記（官方有、FinMind 沒有）的件數與按年分布。
跑法：cd research && python build_exright_supplement.py
"""
from __future__ import annotations

import json
import socket
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (build_exright_supplement)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import pandas as pd  # noqa: E402

import adjust  # noqa: E402
from finmind_client import _cache_path, load_dev  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

D = Path(__file__).parent / "data"
OUT = D / "official_exright_supplement_2007_2014.csv"
REP = D / "official_exright_supplement_report.json"
START = "2010-01-01"  # 只用來比對 FinMind；V1 本身的價格快取是 2006-01-01 起


def build() -> pd.DataFrame:
    a = pd.read_csv(D / "official_exright_2007_2014.csv", dtype={"stock_id": str})
    a["source"] = a["market"].map({"twse": "twse_twt49u", "tpex": "tpex_exdailyq"})
    rows = [a[["ex_date", "stock_id", "market", "prev_close", "ref_price", "factor", "source"]]]
    j = json.loads((D / "tpex_exright_2007h2_ref.json").read_text(encoding="utf-8"))
    extra = []
    for r in j.get("matched") or []:
        if r.get("ref") and r.get("prev_close"):
            extra.append({"ex_date": f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}", "stock_id": str(r["code"]),
                          "market": "tpex", "prev_close": r["prev_close"], "ref_price": r["ref"],
                          "factor": r["ref"] / r["prev_close"], "source": "tpex_2007h2_finmind_amount"})
    for r in j.get("unmatched") or []:
        if r.get("approx_ref_mid") and r.get("prev_close"):
            extra.append({"ex_date": f"{r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]}", "stock_id": str(r["code"]),
                          "market": "tpex", "prev_close": r["prev_close"], "ref_price": r["approx_ref_mid"],
                          "factor": r["approx_ref_mid"] / r["prev_close"], "source": "tpex_2007h2_approx"})
    rows.append(pd.DataFrame(extra))
    out = pd.concat(rows, ignore_index=True)
    out = out[(out["factor"] > 0) & (out["ex_date"] <= "2014-12-31")]
    # 同日同股只留一筆（官方 TWT49U／exDailyQ 優先於 2007 下半年推導）
    prio = {"twse_twt49u": 0, "tpex_exdailyq": 0, "tpex_2007h2_finmind_amount": 1, "tpex_2007h2_approx": 2}
    out = out.assign(_p=out["source"].map(prio)).sort_values(["stock_id", "ex_date", "_p"])
    out = out.drop_duplicates(["stock_id", "ex_date"]).drop(columns="_p").reset_index(drop=True)
    return out


def compare(sup: pd.DataFrame) -> dict:
    diffs, missing, matched, skipped = [], Counter(), 0, 0
    for sid, g in sup.groupby("stock_id"):
        if not (_cache_path("TaiwanStockDividend", sid, START, VAL_END).exists()
                and _cache_path("TaiwanStockPrice", sid, START, VAL_END).exists()):
            skipped += 1
            continue
        div = load_dev("TaiwanStockDividend", sid, START)
        raw = load_dev("TaiwanStockPrice", sid, START)
        if raw.empty or "date" not in raw.columns or div.empty:
            skipped += 1
            continue
        raw = raw.sort_values("date")
        fm = {e["ex_date"]: e["factor"] for e in adjust._dividend_events_from_df(div, dict(zip(raw["date"], raw["close"])), raw["date"].tolist())}
        for r in g[g["ex_date"] >= START].itertuples():
            f = fm.get(r.ex_date)
            if f is None:
                missing[r.ex_date[:4]] += 1
                continue
            matched += 1
            if abs(r.factor / f - 1) > 0.01:
                diffs.append({"stock_id": sid, "ex_date": r.ex_date, "official": round(r.factor, 6), "finmind": round(f, 6),
                              "diff_pct": round((r.factor / f - 1) * 100, 3), "source": r.source})
    return {"compare_window": f"{START}～2014-12-31（FinMind 比對用快取起點；2007～2009 另見 DevQueue exright_official_vs_finmind_2007_2014.json）",
            "n_matched_same_day": matched, "n_diff_over_1pct": len(diffs), "diffs_over_1pct": diffs,
            "n_finmind_missing": sum(missing.values()), "finmind_missing_by_year": dict(sorted(missing.items())),
            "n_stocks_skipped_no_cache": skipped}


def main() -> int:
    sup = build()
    sup.to_csv(OUT, index=False)
    rep = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"), "n_events": len(sup),
           "by_source": sup["source"].value_counts().to_dict(),
           "by_year": sup.groupby(sup["ex_date"].str[:4]).size().to_dict(), **compare(sup)}
    REP.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "diffs_over_1pct"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
