"""先.一五五-3 第二批 第 33 批：value_board_v2（HQ#390，價值成長榜 score_v2 八因子加權總分）→前 N 檔等權（DevQueue 20261111-213102，紙上優化軌，零請求）。

原試驗（run_value_board_v2_pit_backtest.py）逐再平衡日呼叫 score_v2.compute_scores_v2()，這裡改成向量化重算同一套公式：
- earnings_growth 0.18：f_eps_growth；缺值時用 收盤÷PER 反推 TTM EPS、跟 252 個交易日前比（照 _eps_yoy_derived_from_per）。
- revenue_momentum 0.18：月營收 YoY（基期 ≥3,000 萬元、夾 ±200%）與絕對成長金額，各在規模三分層（近 20 日均成交值）內百分位，取兩者較小。
- growth_quality 0.12：近 12 個月營收合計÷前 12 個月 −1（要 ≥24 個月）。
- chips 0.14：f_inst_flow；technical 0.10：f_ma_breakout；valuation_adj 0.12：PEG＝PER÷(EPS 年增×100)，EPS 年增 >0 才有，越低越好。
- analyst／catalyst 原本就沒資料（NaN），權重照原公式按有分數的因子重新分配。
- 百分位：當日橫斷面 1%／99% 去極值後排名（_pct_score），分數＝百分位×10 四捨五入到 0.1（照原式）。
- 覆蓋率（有分數因子權重和）<0.5 不進排名（App 榜單 COVERAGE_MIN_FOR_RANKING 同規則，原回測腳本沒套，〔自行裁量〕）。
- 流動性：近 20 日均成交值 <2,000 萬元不進排名（照 eligible_for_ranking_v2）；百分位照原式在含不足者的全體上算。
- **照實修一個原試驗的未來函數**：原 _revenue_yoy_latest／_revenue_growth_12m 取「快取裡最後一個月」，沒有依 as_of 截斷，
  回測時會看到未來月營收；這裡改成只用 pit_date ≤ 當日的月份（pit.month_revenue_pit 只呼叫）。
- 宇宙：#133 抽樣 236 檔（原試驗是今日流動性前 500 名，本機沒有那份 pkl；照實揭露兩者都有存活者偏誤）。
- 回測沿用 reaudit_batch3_factors.py（research/backtest/ 引擎只呼叫、只做多頭、48 格×組合層 16 格），2015-01～2024-12。
  不寫 TRIALS_LEDGER。非投資建議。

用法：REAUDIT_DEADLINE=<epoch 秒> python research/reaudit_batch33_value_board_v2.py run
     python research/reaudit_batch33_value_board_v2.py summarize
     python research/reaudit_batch33_value_board_v2.py candidates
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
    raise RuntimeError("第 33 批零請求：封鎖網路")


socket.socket.connect = _no_net  # type: ignore[assignment]

import reaudit_batch3_factors as B3  # noqa: E402

FAC = "f_score_v2"
B3.BATCHES["33"] = [FAC]
_orig_prep = B3.prep

W = {"earnings_growth": 0.18, "revenue_momentum": 0.18, "growth_quality": 0.12, "chips": 0.14,
     "technical": 0.10, "valuation_adj": 0.12}
REV_FLOOR, REV_CAP, LIQ_FLOOR = 30_000_000, 2.0, 20_000_000


def _rev_daily(sid, dates):
    """回傳與 dates 對齊的 (yoy, abs_growth, grow12)，只用 pit_date ≤ 當日的月份。"""
    from pit import month_revenue_pit
    from factor_ic import START_DATE
    try:
        rev = month_revenue_pit(sid, START_DATE)
    except Exception as e:  # noqa: BLE001
        B3.prog(f"{sid} 月營收讀不到：{e}")
        rev = pd.DataFrame()
    nan = pd.Series(np.nan, index=range(len(dates)))
    if rev.empty:
        return nan, nan, nan
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    rev = rev.merge(prior.rename(columns={"revenue": "rp"}), on=["revenue_year", "revenue_month"], how="left")
    rev["yoy_raw"] = (rev["revenue"] - rev["rp"]) / rev["rp"].abs()
    rev["abs_g"] = rev["revenue"] - rev["rp"]
    s12 = rev["revenue"].rolling(12, min_periods=12).sum()
    p12 = s12.shift(12)
    rev["grow12"] = np.where(p12 > 0, s12 / p12 - 1, np.nan)
    rev["pit"] = pd.to_datetime(rev["pit_date"].astype(str).str[:10], errors="coerce")
    rev = rev.dropna(subset=["pit"])
    # 同一 pit 日可能公布多個月份，取月份最新的那筆（等同「當下快取裡最後一列」）
    d = pd.DataFrame({"date": pd.to_datetime(pd.Series(dates).astype(str).str[:10])}).reset_index()
    a = rev.sort_values(["pit", "revenue_year", "revenue_month"]).drop_duplicates("pit", keep="last")
    # yoy／abs：取「最後一個 yoy 有限的月份」（照原式 last = rev[isfinite(yoy)]）
    fin = rev[np.isfinite(rev["yoy_raw"])].copy()
    fin = fin.sort_values(["pit", "revenue_year", "revenue_month"])
    fin["ym"] = fin["revenue_year"] * 100 + fin["revenue_month"]
    fin["ym_max"] = fin["ym"].cummax()
    fin = fin[fin["ym"] == fin["ym_max"]].drop_duplicates("pit", keep="last")
    m1 = pd.merge_asof(d.sort_values("date"), fin[["pit", "yoy_raw", "abs_g", "rp"]].rename(columns={"pit": "date"}),
                       on="date", direction="backward").sort_values("index")
    a = a.copy()
    a["ym"] = a["revenue_year"] * 100 + a["revenue_month"]
    a = a[a["ym"] == a["ym"].cummax()]
    m2 = pd.merge_asof(d.sort_values("date"), a[["pit", "grow12"]].rename(columns={"pit": "date"}),
                       on="date", direction="backward").sort_values("index")
    yoy = m1["yoy_raw"].where(m1["rp"] >= REV_FLOOR).clip(-REV_CAP, REV_CAP)
    return yoy.reset_index(drop=True), m1["abs_g"].reset_index(drop=True), m2["grow12"].reset_index(drop=True)


def _pct(raw, by, higher=True):
    """當日（by）橫斷面 1%／99% 去極值後排名百分位；有效樣本 <3 給 NaN（照 _pct_score）。"""
    g = raw.groupby(by)
    lo, hi, n = g.transform(lambda s: s.quantile(0.01)), g.transform(lambda s: s.quantile(0.99)), g.transform("count")
    c = raw.clip(lower=lo, upper=hi)
    p = c.groupby(by).rank(pct=True)
    if not higher:
        p = 1 - p
    return p.where(n >= 3)


def add_composite(data):
    frames = []
    for sid, d in data.items():
        d = d.sort_values("date").reset_index(drop=True)
        data[sid] = d
        x = pd.DataFrame({"date": d["date"].astype(str).str[:10], "stock_id": sid})
        eps = d["f_eps_growth"].astype(float)
        per = -d["f_value_pe"].astype(float)
        dep = d["close"].astype(float) / per.where(per > 0)
        dep_prior = dep.shift(252)
        eps_der = ((dep - dep_prior) / dep_prior.abs()).where(dep_prior != 0)
        eps = eps.where(eps.notna(), eps_der.replace([np.inf, -np.inf], np.nan))
        x["eps"] = eps
        x["peg"] = (per / (eps * 100)).where((eps > 0) & per.notna()).replace([np.inf, -np.inf], np.nan)
        x["chips"] = d["f_inst_flow"].astype(float).values
        x["tech"] = d["f_ma_breakout"].astype(float).values
        x["liq"] = d["Trading_money"].astype(float).rolling(20, min_periods=20).mean().values
        yoy, absg, g12 = _rev_daily(sid, d["date"])
        x["yoy"], x["absg"], x["g12"] = yoy.values, absg.values, g12.values
        frames.append(x)
    big = pd.concat(frames, ignore_index=True)
    by = big["date"]
    sc = {}
    sc["earnings_growth"] = _pct(big["eps"], by)
    sc["growth_quality"] = _pct(big["g12"], by)
    sc["chips"] = _pct(big["chips"], by)
    sc["technical"] = _pct(big["tech"], by)
    sc["valuation_adj"] = _pct(big["peg"], by, higher=False)
    # 規模三分層（當日有效 ≥10 筆才分）
    q1 = big.groupby(by)["liq"].transform(lambda s: s.quantile(1 / 3))
    q2 = big.groupby(by)["liq"].transform(lambda s: s.quantile(2 / 3))
    nl = big.groupby(by)["liq"].transform("count")
    tier = pd.Series(np.where(big["liq"] <= q1, "s", np.where(big["liq"] <= q2, "m", "l")), index=big.index)
    tier = tier.where(big["liq"].notna() & (nl >= 10))
    key = by + "|" + tier.fillna("")
    py = _pct(big["yoy"].where(tier.notna()), key)
    pa = _pct(big["absg"].where(tier.notna()), key)
    sc["revenue_momentum"] = pd.concat([py, pa], axis=1).min(axis=1, skipna=False)
    num = pd.Series(0.0, index=big.index)
    den = pd.Series(0.0, index=big.index)
    for k, w in W.items():
        s = (sc[k].round(2) * 10).round(1)  # 照原式：pct 先 round(2)、分數×10 round(1)
        ok = s.notna()
        num += s.fillna(0) * w
        den += ok * w
    tot = (num / den).where(den > 0).round(1)
    tot = tot.where(big["liq"] >= LIQ_FLOOR)  # 流動性不足不進排名
    tot = tot.where(den.round(2) >= 0.5)  # 〔自行裁量〕覆蓋率 <0.5 不進排名（score_v2.COVERAGE_MIN_FOR_RANKING，App 榜單同規則；否則 ETF 只靠籌碼＋技術兩項會被權重重分配推上榜）
    big[FAC] = tot
    m = {sid: dict(zip(s["date"], s[FAC])) for sid, s in big.groupby("stock_id")}
    for sid, d in data.items():
        d[FAC] = d["date"].astype(str).str[:10].map(m.get(sid, {})).astype(float)
    n = big[FAC].notna()
    B3.prog(f"{FAC}：有分數 {int(n.sum())} 列、{big.loc[n, 'stock_id'].nunique()} 檔；"
            f"EPS 反推補值 {int((big['eps'].notna()).sum() - sum(int(d['f_eps_growth'].notna().sum()) for d in data.values()))} 列")
    return data


def prep(data, fac):
    if fac == FAC and FAC not in next(iter(data.values())).columns:
        add_composite(data)
    return _orig_prep(data, fac)


B3.prep = prep


def candidates():
    """Calmar ≥0.6、交易 ≥100 才進候選欄（同第 6／15／32 批門檻）。"""
    import json
    from datetime import datetime
    cand = HERE / "data" / "paper_opt_candidates.json"
    out = json.loads((HERE / "data" / "reaudit_batch3_batch33.json").read_text(encoding="utf-8"))
    d = json.loads(cand.read_text(encoding="utf-8")) if cand.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B33F-")]
    new = []
    old = B3._old_table()
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or (b.get("calmar") or 0) < 0.6 or (b.get("trades") or 0) < 100 or f["cells_done"] < f["cells_total"]:
            continue
        note = ["樣本內最優化（偏樂觀）", "#133 抽樣 236 檔宇宙（今天名冊抽樣，存活者偏誤未完全排除）", "只做多頭",
                "價值成長榜 score_v2 六因子加權（analyst／catalyst 無資料、權重重分配）；月營收改 PIT（修原試驗未來函數）",
                "2025 起延長尚未做"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，只當參考")
        new.append({"id": f"B33F-{f['factor']}", "factor": f["factor"], "source": "先.一五五-3 第二批第 33 批（value_board_v2，HQ#390）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）",
                    "rank_in_table": 1 + sum(1 for _, s in old if s > b["calmar"]),
                    "params": {"direction": b["direction"], "rebalance_days": b["rebalance_days"], "market_gate": b["market_gate"],
                               "top_n": b["top_n"], "pos_stop": b["pos_stop"], "leverage": b["L"], "portfolio_stop": b["stop"]},
                    "backtest_2015_2024": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                           "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "from_2025_same_params": None, "full_period_same_params": None,
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c.get("rank_in_table", 99))
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    cand.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B3.prog(f"候選欄第 33 批 {len(new)} 支；總數 {len(d['candidates'])}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "candidates":
        sys.exit(candidates())
    if len(sys.argv) >= 2 and sys.argv[1] == "summarize":
        sys.exit(B3.summarize("33"))
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        import pickle
        data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
        add_composite(data)
        allv = pd.concat([d[["date", FAC]].assign(sid=s) for s, d in data.items()])
        print(allv[FAC].describe())
        dd = allv[allv["date"].astype(str).str[:10] == "2020-06-30"].sort_values(FAC, ascending=False).head(10)
        print(dd)
        sys.exit(0)
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1800))
    sys.exit(0 if B3.run([FAC], dl) else 2)
