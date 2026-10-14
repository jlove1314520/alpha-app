# -*- coding: utf-8 -*-
"""先.九十四-1a／1b：core_tilt 量尺（重建 0050）日頻 TE 4.46% 的一輪診斷（只做一輪，不得反覆）。

a. R1～R6 有沒有實際生效：比較「先.八十三-2a-1 每月重排版」與「先.九十三-1b 規則版」每天的持股與權重差異、
   兩版組合彼此的日頻 TE。
b. 三個可能原因各自量化：
   ① 股息：兩邊各算「含息－不含息」的年度差（重建組合 vs 0050），並列出持有期間完全沒有除權息事件快取的成分股權重；
   ② 缺日／舊價：每天有多少權重的成分股當天沒有成交價（用前值頂替），以及 diff 的自我相關、
      跨日彙總（2／5／21 日）後 TE 怎麼變——時間錯位造成的雜訊會在彙總後抵銷；
   ③ 權重差（N1 自由流通市值缺資料）：把 diff 對前 10 大成分股超額報酬做回歸，估「隱含權重差」與可解釋比例。
只讀本機快取、0 次網路請求、不讀 holdout、不登記試驗、不計 N。
輸出：research/data/core_tilt_te_diagnosis.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pit_mktcap_rank as pmr  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

OUT = HERE / "data" / "core_tilt_te_diagnosis.json"
START = "2013-06-01"


def segments_monthly(days: list[str]) -> list[dict]:
    """先.八十三-2a-1 原做法：每月最後交易日總市值前 50 名、隔日起持有。"""
    s = pd.Series(days, index=pd.to_datetime(days))
    rebal = s.groupby([s.index.year, s.index.month]).last().tolist()
    panel = pmr.mktcap_panel(rebal)
    top = panel[panel["rank"] <= 50]
    out = []
    for i, d0 in enumerate(rebal):
        g = top[top["date"] == d0]
        out.append({"base": d0, "start_after": d0, "end": rebal[i + 1] if i + 1 < len(rebal) else days[-1],
                    "cap": dict(zip(g["stock_id"], g["mktcap"]))})
    return out


def segments_rules(days: list[str]) -> list[dict]:
    sched = pmr.taiwan50_schedule(days)
    cap = pmr.mktcap_panel(sorted({s["weight_day"] for s in sched})).set_index(["date", "stock_id"])["mktcap"]
    out = []
    for k, s in enumerate(sched):
        end_excl = sched[k + 1]["effective"] if k + 1 < len(sched) else None
        seg = [d for d in days if d >= s["effective"] and (end_excl is None or d < end_excl)]
        if not seg:
            continue
        c = {m: float(cap.get((s["weight_day"], m), np.nan)) for m in s["members"]}
        out.append({"base": s["weight_day"], "days": seg, "cap": {m: v for m, v in c.items() if v == v and v > 0}})
    return out, sched


def build(days, segs, px_fn, monthly: bool):
    """回傳 (日報酬, 每日持股權重 dict)。px_fn(sid) → 價格序列（含息或不含息）。"""
    port = pd.Series(np.nan, index=pd.Index(days))
    wday = {}
    for sg in segs:
        hold = sg["days"] if not monthly else [d for d in days if sg["start_after"] < d <= sg["end"]]
        if not hold:
            continue
        tot = sum(sg["cap"].values())
        base = sg["base"]
        idx = [base] + hold
        val = pd.Series(0.0, index=idx)
        comp = {}
        for m, cv in sg["cap"].items():
            p = px_fn(m).reindex(idx).ffill(limit=5)
            if pd.isna(p.iloc[0]):
                continue
            p = p.ffill()
            comp[m] = (cv / tot) * (p / p.iloc[0])
            val = val + comp[m]
        port.loc[hold] = ((val / val.shift(1)).iloc[1:] - 1).to_numpy()
        # 每日開盤前權重＝前一日收盤後的漂移權重
        cdf = pd.DataFrame(comp)
        wdf = cdf.div(cdf.sum(axis=1), axis=0).shift(1).iloc[1:]
        for d, row in wdf.iterrows():
            wday[d] = row.to_dict()
    return port, wday


def main() -> int:
    etf_tri = pmr.total_return_index("0050")
    etf_px = pmr.close_series("0050")
    days = [d for d in etf_tri.index if START <= d <= VAL_END]
    etf_ret = etf_tri.reindex(days).pct_change()
    etf_pret = etf_px.reindex(days).pct_change()

    seg_r, sched = segments_rules(days)
    seg_m = segments_monthly(days)
    tri = pmr.total_return_index
    cls = pmr.close_series
    port_r, w_r = build(days, seg_r, tri, monthly=False)
    port_m, w_m = build(days, seg_m, tri, monthly=True)
    port_r_px, _ = build(days, seg_r, cls, monthly=False)

    df = pd.DataFrame({"rules": port_r, "monthly": port_m, "rules_px": port_r_px, "etf": etf_ret, "etf_px": etf_pret}).dropna()
    ann = np.sqrt(252)
    te = lambda a, b: float((df[a] - df[b]).std() * ann)

    # ── a. 修正前後持股差異 ──
    common = [d for d in df.index if d in w_r and d in w_m]
    n_diff, l1 = [], []
    for d in common:
        a, b = w_r[d], w_m[d]
        n_diff.append(len(set(a) ^ set(b)) / 2)
        l1.append(sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b)) / 2)
    n_diff, l1 = np.array(n_diff), np.array(l1)
    part_a = {
        "days_compared": len(common),
        "days_with_different_names": int((n_diff > 0).sum()),
        "avg_names_different": round(float(n_diff.mean()), 2), "max_names_different": float(n_diff.max()),
        "avg_one_way_weight_diff": round(float(l1.mean()), 4), "max_one_way_weight_diff": round(float(l1.max()), 4),
        "te_daily_rules_vs_monthly": round(te("rules", "monthly"), 4),
        "te_daily_rules_vs_etf": round(te("rules", "etf"), 5), "te_daily_monthly_vs_etf": round(te("monthly", "etf"), 5),
        "cum_rules": round(float((1 + df["rules"]).prod() - 1), 4), "cum_monthly": round(float((1 + df["monthly"]).prod() - 1), 4),
        "n_rule_changes": len(sched),
        "sample_day": common[len(common) // 2] if common else None,
    }
    if common:
        sd = part_a["sample_day"]
        a, b = w_r[sd], w_m[sd]
        part_a["sample_only_in_rules"] = sorted(set(a) - set(b))
        part_a["sample_only_in_monthly"] = sorted(set(b) - set(a))
    print("a.", json.dumps(part_a, ensure_ascii=False), flush=True)

    # ── b①. 股息 ──
    yr = pd.to_datetime(df.index).year
    by = {}
    for y, g in df.groupby(yr):
        c = lambda col: float((1 + g[col]).prod() - 1)
        by[int(y)] = {"port_tri": round(c("rules"), 4), "port_px": round(c("rules_px"), 4),
                      "port_div": round(c("rules") - c("rules_px"), 4),
                      "etf_tri": round(c("etf"), 4), "etf_px": round(c("etf_px"), 4),
                      "etf_div": round(c("etf") - c("etf_px"), 4),
                      "gap_tri": round(c("rules") - c("etf"), 4), "gap_px": round(c("rules_px") - c("etf_px"), 4)}
    # 持有期間完全沒有事件快取的成分股（除息日會被當成下跌）
    no_ev = {}
    for d, w in w_r.items():
        for m, wm in w.items():
            if tri(m).attrs.get("no_event_cache"):
                no_ev[m] = max(no_ev.get(m, 0), wm)
    part_1 = {"by_year": by,
              "avg_annual_div_port": round(float(np.mean([v["port_div"] for v in by.values()])), 4),
              "avg_annual_div_etf": round(float(np.mean([v["etf_div"] for v in by.values()])), 4),
              "te_daily_price_only": round(te("rules_px", "etf_px"), 4),
              "holdings_without_event_cache_max_weight": {k: round(v, 4) for k, v in sorted(no_ev.items())}}
    print("①", json.dumps({k: v for k, v in part_1.items() if k != "by_year"}, ensure_ascii=False), flush=True)

    # ── b②. 缺日／舊價 ──
    stale_w = []
    raw_dates = {}
    for d in df.index:
        w = w_r.get(d, {})
        s = 0.0
        for m, wm in w.items():
            if m not in raw_dates:
                raw_dates[m] = set(cls(m).index)
            if d not in raw_dates[m]:
                s += wm
        stale_w.append(s)
    stale_w = pd.Series(stale_w, index=df.index)
    diff = df["rules"] - df["etf"]
    etf_has = set(etf_px.index)
    agg = {}
    for k in (1, 2, 5, 21):
        g = (1 + df[["rules", "etf"]]).groupby(np.arange(len(df)) // k).prod() - 1
        agg[f"{k}d"] = round(float((g["rules"] - g["etf"]).std() * np.sqrt(252 / k)), 4)
    clean = stale_w < 1e-9
    part_2 = {
        "days_with_any_stale_member": int((stale_w > 0).sum()), "n_days": len(df),
        "avg_stale_weight": round(float(stale_w.mean()), 5), "max_stale_weight": round(float(stale_w.max()), 4),
        "te_daily_clean_days_only": round(float(diff[clean].std() * ann), 4),
        "diff_autocorr_lag1": round(float(diff.autocorr(1)), 3),
        "corr_port_t_etf_t_minus_1": round(float(df["rules"].corr(df["etf"].shift(1))), 3),
        "corr_port_t_etf_t_plus_1": round(float(df["rules"].corr(df["etf"].shift(-1))), 3),
        "te_by_aggregation_annualized": agg,
        "etf_days_missing_in_cache": int(sum(1 for d in days if d not in etf_has)),
    }
    print("②", json.dumps(part_2, ensure_ascii=False), flush=True)

    # ── b③. 權重差（N1）：diff 對前 10 大成分股（相對組合）的超額報酬回歸 ──
    big = pd.Series({m: wm for m, wm in w_r[df.index[-1]].items()}).sort_values(ascending=False).head(10).index.tolist()
    X = pd.DataFrame({m: tri(m).reindex(days).pct_change() for m in big}).reindex(df.index)
    Xe = X.sub(df["rules"], axis=0).fillna(0.0)
    res = {}
    for label, msk in (("all", np.ones(len(df), bool)), ("2019_2024", pd.to_datetime(df.index).year >= 2019)):
        A = np.column_stack([np.ones(msk.sum()), Xe[msk].to_numpy()])
        yv = (-diff[msk]).to_numpy()   # etf − port＝Σ(w_true − w_ours)(r_i − r_port)
        coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
        fit = A @ coef
        r2 = 1 - float(((yv - fit) ** 2).sum() / ((yv - yv.mean()) ** 2).sum())
        resid_te = float(np.std(yv - fit) * ann)
        res[label] = {"implied_weight_gap_etf_minus_ours": {m: round(float(c), 4) for m, c in zip(big, coef[1:])},
                      "r2": round(r2, 3), "te_unexplained": round(resid_te, 4), "te_total": round(float(np.std(yv) * ann), 4)}
    tsmc_ours = {d: round(w_r[d].get("2330", 0), 4) for d in [df.index[0], df.index[len(df) // 2], df.index[-1]]}
    part_3 = {"top10_by_our_weight_at_end": big, "regression": res, "tsmc_weight_ours_samples": tsmc_ours}
    print("③", json.dumps(part_3, ensure_ascii=False), flush=True)

    # ── b①補：官方 TWT49U 核對 FinMind 缺列的除權息事件（先.九十四-1b①） ──
    port_r_fix, _ = build(days, seg_r, pmr.total_return_index_patched, monthly=False)
    df["rules_fix"] = port_r_fix.reindex(df.index)
    miss = {}
    for d, w in w_r.items():
        for m, wm in w.items():
            if m not in miss:
                miss[m] = pmr.missing_official_events(m)
    held_miss = {m: v for m, v in miss.items() if v}
    lost = {}
    for m, ev in held_miss.items():
        for d, f in ev:
            if d in w_r:
                y = d[:4]
                lost[y] = lost.get(y, 0.0) + w_r[d].get(m, 0.0) * (1 / f - 1)
    part_1["official_twt49u_check"] = {
        "holdings_with_missing_events": {m: len(v) for m, v in sorted(held_miss.items())},
        "missed_dividend_return_by_year": {y: round(v, 4) for y, v in sorted(lost.items())},
        "etf_0050_missing_events": len(pmr.missing_official_events("0050")),
        "te_daily_after_patch": round(te("rules_fix", "etf"), 5),
        "cum_after_patch": round(float((1 + df["rules_fix"]).prod() - 1), 4),
    }
    print("①補", json.dumps(part_1["official_twt49u_check"], ensure_ascii=False), flush=True)

    # 先.九十五-1：原本這裡用證交所 /rwd/zh/FTSE/TAI50I（官方臺灣50報酬指數）拆解誤差來源；
    # 該路徑與專案禁抓決定衝突，總司令裁示採乙——資料與兩個衍生數字已撤回，本段刪除。

    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "task": "先.九十四-1a／1b",
           "period": [df.index[0], df.index[-1]], "n_days": len(df),
           "a_rules_took_effect": part_a, "b1_dividends": part_1, "b2_stale_prices": part_2, "b3_weights_N1": part_3, "official_index_decomposition": "已撤回（先.九十五-1：資料來源為禁抓的證交所 FTSE 路徑）",
           "requests_made": 0}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("寫入", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
