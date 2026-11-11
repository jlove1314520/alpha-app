"""先.一五五-3 第二批 第 32 批：score_topn_v1（AI 選股綜合分數前 N 名，run_score_backtest.py）→前 N 檔等權（DevQueue 20261111-153102，紙上優化軌，零請求）。

原試驗用 score.py 綜合分數＝三個成分的產業內 z 分數平均：EPS 家族（f_eps_growth、f_eps_surprise 各自產業 z 後平均）、
f_revenue_surprise、f_low_vol（score.py 現行版本已改成只用 low_vol 一個成分；這裡照原試驗的三成分版本重審，
low_vol 單一成分已在第 1 批 f_low_vol 做過）。
- 產業 z 分數直接呼叫 score._zscore_within_group（同組 <5 檔退回全樣本 z）；產業別用 pair_trading_sanity.build_industry_groups
  （本機、今日產業別，照實揭露）——score.load_industry_map() 會走 FinMind 請求，這裡不用。
- 〔自行裁量〕三成分至少要有 2 個才給分（原 v1 的 MIN_COMPONENTS 在改 1 之前是 2）。
- 回測完全沿用 reaudit_batch3_factors.py（#133 抽樣 236 檔、research/backtest/ 引擎只呼叫、只做多頭、順反向都掃、48 格×組合層 16 格），
  期間 2015-01～2024-12。不寫 TRIALS_LEDGER。非投資建議。

用法：REAUDIT_DEADLINE=<epoch 秒> python research/reaudit_batch32_score_topn.py run
     python research/reaudit_batch32_score_topn.py summarize
"""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _no_net(*a, **k):
    raise RuntimeError("第 32 批零請求：封鎖網路")


socket.socket.connect = _no_net  # type: ignore[assignment]

import reaudit_batch3_factors as B3  # noqa: E402

FAC = "f_score_v1"
B3.BATCHES["32"] = [FAC]
_orig_prep = B3.prep


def add_composite(data):
    import pair_trading_sanity as pts
    from score import _zscore_within_group
    groups = pts.build_industry_groups(list(data.keys()))
    ind = {sid: g for g, ids in groups.items() for sid in ids}
    cols = ["f_eps_growth", "f_eps_surprise", "f_revenue_surprise", "f_low_vol"]
    frames = []
    for sid, d in data.items():
        x = d[["date"] + cols].copy()
        x["date"] = x["date"].astype(str).str[:10]
        x["stock_id"] = sid
        frames.append(x)
    big = pd.concat(frames, ignore_index=True)
    big["industry"] = big["stock_id"].map(ind)
    out = []
    for dt, cs in big.groupby("date", sort=True):
        cs = cs.reset_index(drop=True)
        g = cs["industry"]
        eps = pd.concat([_zscore_within_group(cs["f_eps_growth"], g), _zscore_within_group(cs["f_eps_surprise"], g)],
                        axis=1).mean(axis=1, skipna=True)
        comp = pd.concat([eps, _zscore_within_group(cs["f_revenue_surprise"], g),
                          _zscore_within_group(cs["f_low_vol"], g)], axis=1)
        val = comp.mean(axis=1, skipna=True).where(comp.notna().sum(axis=1) >= 2)
        out.append(pd.DataFrame({"date": dt, "stock_id": cs["stock_id"], FAC: val}))
    sc = pd.concat(out, ignore_index=True)
    m = {sid: dict(zip(s["date"], s[FAC])) for sid, s in sc.groupby("stock_id")}
    for sid, d in data.items():
        d[FAC] = d["date"].astype(str).str[:10].map(m.get(sid, {})).astype(float)
    n = sc[FAC].notna()
    B3.prog(f"{FAC}：有分數 {int(n.sum())} 列、{sc.loc[n, 'stock_id'].nunique()} 檔；產業 {len(groups)} 群、有產業 {len(ind)} 檔")
    return data


def prep(data, fac):
    if fac == FAC and FAC not in next(iter(data.values())).columns:
        add_composite(data)
    return _orig_prep(data, fac)


B3.prep = prep

def candidates():
    """綜合分數 Calmar ≥0.6、交易 ≥100 才進候選欄（同第 6／15 批門檻）；2025 起延長未做，照實標註。"""
    import json
    from datetime import datetime
    cand = HERE / "data" / "paper_opt_candidates.json"
    out = json.loads((HERE / "data" / "reaudit_batch3_batch32.json").read_text(encoding="utf-8"))
    d = json.loads(cand.read_text(encoding="utf-8")) if cand.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B32F-")]
    new = []
    old = B3._old_table()
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or (b.get("calmar") or 0) < 0.6 or (b.get("trades") or 0) < 100 or f["cells_done"] < f["cells_total"]:
            continue
        note = ["樣本內最優化（偏樂觀）", "#133 抽樣 236 檔宇宙（今天名冊抽樣，存活者偏誤未完全排除）", "只做多頭",
                "綜合分數＝EPS 家族／月營收意外／低波動 三成分產業 z 平均（原 score_topn_v1）", "2025 起延長尚未做"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，只當參考")
        xp = HERE / "data" / "reaudit_batch3_batch32_ext2025.json"
        x = json.loads(xp.read_text(encoding="utf-8")) if xp.exists() else None
        seg = (x or {}).get("segments", {}).get("prev_best")
        if seg:
            note[-1] = f"2025 起延長已做（同參數到 {seg['end']}）"
        new.append({"id": f"B32F-{f['factor']}", "factor": f["factor"], "source": "先.一五五-3 第二批第 32 批（score_topn_v1）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）",
                    "rank_in_table": 1 + sum(1 for _, s in old if s > b["calmar"]),
                    "params": {"direction": b["direction"], "rebalance_days": b["rebalance_days"], "market_gate": b["market_gate"],
                               "top_n": b["top_n"], "pos_stop": b["pos_stop"], "leverage": b["L"], "portfolio_stop": b["stop"]},
                    "backtest_2015_2024": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                           "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "from_2025_same_params": seg["from2025"] if seg else None,
                    "full_period_same_params": seg["full"] if seg else None,
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c.get("rank_in_table", 99))
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    cand.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B3.prog(f"候選欄第 32 批 {len(new)} 支；總數 {len(d['candidates'])}")


COMPS = ["f_eps_growth", "f_eps_surprise", "f_revenue_surprise", "f_low_vol"]


def ext_run(deadline):
    """（DevQueue 20261111-203102）延長到 2025 起：四成分照 reaudit_batch3_ext2025.recompute 各自重算
    （財報類 2024 底前沿用 pkl、2025 起用本機快取重算；低波動照原公式），再算綜合分數，48 格延長到本機資料終點。零請求。"""
    import reaudit_batch3_ext2025 as X
    orig = X.recompute

    def rec(ext, mk, fac):
        if fac != FAC:
            return orig(ext, mk, fac)
        worst = 0.0
        for c in COMPS:
            n0 = len(X.FIN_MISMATCH)
            w = orig(ext, mk, c)
            B3.prog(f"成分 {c}：2024 底前與 pkl 最大差 {w:.2e}、不一致 {len(X.FIN_MISMATCH) - n0} 檔")
            worst = max(worst, w)
        if len(X.FIN_MISMATCH) > 0.05 * len(ext):
            B3.prog(f"財報成分不一致 {len(X.FIN_MISMATCH)} 檔超過 5%，停止")
            return 1.0
        add_composite(ext)
        return worst

    X.recompute = rec
    return X.run(FAC, deadline)


def ext_summarize():
    """延長後：第 32 批挑出的同一組（全期／2015～2024／2025 起），與全期重挑（MDD≤50%、Calmar 最高）。"""
    import itertools
    import json
    from datetime import datetime
    import reaudit_batch3_ext2025 as X
    import reaudit_optimized_batch2_sector as S
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    LB.END = "2099-12-31"
    ob = json.loads((HERE / "data" / "reaudit_batch3_batch32.json").read_text(encoding="utf-8"))["families"][0]["best_by_calmar"]
    cache = json.loads((X.CELLS_DIR / f"{FAC}.json").read_text(encoding="utf-8"))
    rows, rf = [], None
    for k, c in cache.items():
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float); eq = eq / eq[0]
        if rf is None or len(rf) != len(dates):
            rf = LB.load_tw_rf_daily(dates)
        for L, stop in itertools.product(S.LEVS, S.STOPS):
            curve, _ = S.overlay(eq, rf, L, stop)
            g, mdd, sh = S.stats(curve, dates)
            rows.append({"key": k, "L": L, "stop": stop, "cagr": g, "mdd": mdd, "sharpe": sh,
                         "calmar": g / abs(mdd) if mdd < 0 else None, "trades": c["n_round_trips"]})
    df = pd.DataFrame(rows)
    best = df[df["mdd"] >= -0.50].sort_values("calmar", ascending=False).iloc[0].to_dict()
    segs = {}
    for tag, pick in (("prev_best", ob), ("new_best", best)):
        if pick["key"] not in cache:
            segs[tag] = None
            continue
        c = cache[pick["key"]]
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float); eq = eq / eq[0]
        curve, _ = S.overlay(eq, LB.load_tw_rf_daily(dates), pick["L"], pick["stop"])
        full = S.stats(curve, dates)
        segs[tag] = {"key": pick["key"], "L": float(pick["L"]), "stop": float(pick["stop"]),
                     "full": {"cagr": full[0], "mdd": full[1], "sharpe": full[2]},
                     "pre2025": X._seg(curve, dates, pd.Timestamp("2015-01-01"), pd.Timestamp("2024-12-31")),
                     "from2025": X._seg(curve, dates, pd.Timestamp("2024-12-31"), dates.max()),
                     "end": str(dates.max().date())}
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "factor": FAC, "cells_done": len(cache),
           "n_violates": int((df["mdd"] < -0.50).sum()), "segments": segs}
    (HERE / "data" / "reaudit_batch3_batch32_ext2025.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    for tag, v in segs.items():
        if v:
            B3.prog(f"{tag} {v['key']} L={v['L']:g} stop={v['stop']:g} 全期 {v['full']['cagr']:+.1%}/{v['full']['mdd']:.1%} Sh {v['full']['sharpe']:.2f}"
                    f"｜2015～2024 {v['pre2025']['cagr']:+.1%}/{v['pre2025']['mdd']:.1%}｜2025 起 {v['from2025']['cagr']:+.1%}/{v['from2025']['mdd']:.1%}（到 {v['end']}）")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "ext":
        sys.exit(0 if ext_run(float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1500))) else 2)
    if len(sys.argv) >= 2 and sys.argv[1] == "extsum":
        sys.exit(ext_summarize())
    if len(sys.argv) >= 2 and sys.argv[1] == "candidates":
        sys.exit(candidates())
    if len(sys.argv) >= 2 and sys.argv[1] == "summarize":
        sys.exit(B3.summarize("32"))
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1800))
    sys.exit(0 if B3.run([FAC], dl) else 2)
