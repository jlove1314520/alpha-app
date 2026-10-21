"""先.一二五-4：高股息 ETF 換股事件（個股層級）單發事件研究。

規格全部寫死在 docs/PREREG_ETF_REBALANCE_HIGH_DIVIDEND_FINAL.md（含「定稿補充」13 點），本程式只照做、不另加參數。
- 事件：research/data/etf_rebalance_events.csv（本機，不進公開 repo），只取生效日 2022～2024、公告日與生效日都有日期的列。
- 價格：var1018_twdata.daily()（只讀本機 FinMind 快取、股利還原、截到 holdout.VAL_END），零外部請求。
- 市值：pit_mktcap_rank.shares_on × close_on（法定公告日 PIT）。產業：本機 TaiwanStockInfo。
- 只跑一次：結果檔已存在就拒絕重跑（同 bb90_oos_2025.py 的做法）。

用法：python research/etf_rebalance_event_study.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import numpy as np
import pandas as pd

import pit_mktcap_rank as pmr
import var1018_twdata as tw
from validation import holdout
from validation.costs import limit_status, round_trip_cost_pct

R = Path(__file__).parent
EVENTS_CSV = R / "data" / "etf_rebalance_events.csv"
INFO_PATH = R / "data" / "raw" / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet"
OUT = R / "data" / "etf_rebalance_event_study_result.json"
PREREG = "docs/PREREG_ETF_REBALANCE_HIGH_DIVIDEND_FINAL.md"

YEARS = ("2022", "2023", "2024")
LIQ_MIN = 30_000_000          # 公告日前 20 個交易日平均成交值（元）
LIQ_DAYS = 20
N_CTRL = 3
N_BOOT = 1000
SEED = 20261021
MIN_GROUPS, MIN_PER_SIDE, MIN_GROUPS_PER_HALF = 10, 30, 3   # 定稿補充第 2 點
GENERIC_IND = {"電子工業", "其他", "其他電子業", ""}
COST1 = round_trip_cost_pct()


def industry_map() -> dict[str, str]:
    info = pd.read_parquet(INFO_PATH)
    info["date"] = info["date"].astype(str).str[:10]
    out = {}
    for sid, g in info.groupby("stock_id"):
        g2 = g[g["date"] <= holdout.VAL_END]
        g2 = g2 if not g2.empty else g
        last = g2[g2["date"] == g2["date"].max()]
        cats = [c for c in last["industry_category"].astype(str) if c not in GENERIC_IND]
        out[str(sid)] = cats[0] if cats else str(last["industry_category"].iloc[0])
    return out


def main() -> int:
    if OUT.exists():
        print(f"拒絕重跑：{OUT} 已存在（單發）")
        return 2
    rows = list(csv.DictReader(open(EVENTS_CSV, encoding="utf-8-sig")))
    in_years = [r for r in rows if r["effective_date"][:4] in YEARS]
    dated = [r for r in in_years if r["announce_date"][:4].isdigit() and r["effective_date"][:4].isdigit()]
    counts = {"rows_2022_2024": len(in_years), "rows_missing_date": len(in_years) - len(dated),
              "events_2022_2024": len({(r["etf"], r["announce_date"], r["effective_date"]) for r in in_years}),
              "events_with_dates": len({(r["etf"], r["announce_date"], r["effective_date"]) for r in dated})}

    cal = sorted(set(tw.daily("0050")["date"]) | set(tw.daily("2330")["date"]))
    cal = [d for d in cal if d <= pd.Timestamp(holdout.VAL_END)]

    def td_on_or_before(s: str):
        t = pd.Timestamp(s)
        c = [d for d in cal if d <= t]
        return c[-1] if c else None

    def prev_td(t):
        c = [d for d in cal if d < t]
        return c[-1] if c else None

    # 定稿補充 3／4：群組＝公告日＋生效日；同一股票同一生效日只算一次，同日一加一刪兩筆都剔除
    groups: dict[tuple, dict] = defaultdict(lambda: {"etfs": set(), "codes": defaultdict(set)})
    for r in dated:
        g = groups[(r["announce_date"], r["effective_date"])]
        g["etfs"].add(r["etf"])
        g["codes"][r["stock_code"]].add(r["action"])
    eff_actions: dict[tuple, set] = defaultdict(set)
    for (ann, eff), g in groups.items():
        for c, acts in g["codes"].items():
            eff_actions[(eff, c)] |= acts
    ind = industry_map()
    ctrl_pool = tw.codes_with_price()  # 4 碼普通股
    drop = defaultdict(int)
    recs = []
    seen = set()
    for (ann, eff), g in sorted(groups.items(), key=lambda kv: kv[0][1]):
        t0, t1 = td_on_or_before(ann), td_on_or_before(eff)
        if t0 is None or t1 is None or t1 <= t0:
            drop["區間無效（公告日≥生效日）"] += len(g["codes"])
            continue
        tprev = prev_td(t0)
        d0 = t0.strftime("%Y-%m-%d")
        dprev = tprev.strftime("%Y-%m-%d")
        group_codes = set(g["codes"])
        bench = tw.cum_return(tw.daily("0050"), t0, t1)

        def liq_ok(code: str) -> bool:
            d = tw.daily(code)
            w = d[d["date"] < t0].tail(LIQ_DAYS)
            return len(w) == LIQ_DAYS and float(w["money"].mean()) >= LIQ_MIN

        def mcap(code: str):
            sh, px = pmr.shares_on(code, dprev), pmr.close_on(code, dprev)
            return sh * px if sh and px else None

        cand_cache = None
        for code, acts in sorted(g["codes"].items()):
            if (eff, code) in seen:
                drop["同股同生效日重複"] += 1
                continue
            seen.add((eff, code))
            if len(eff_actions[(eff, code)]) > 1:
                drop["同日一加一刪"] += 1
                continue
            act = next(iter(acts))
            d = tw.daily(code)
            ret = tw.cum_return(d, t0, t1)
            if ret is None:
                drop["事件股區間缺價"] += 1
                continue
            if not liq_ok(code):
                drop["事件股流動性不足"] += 1
                continue
            row0 = d[d["date"] == t0]
            prevrow = d[d["date"] < t0].tail(1)
            locked_up = locked_dn = False
            if not row0.empty and not prevrow.empty:
                o, h, l, c = (float(row0[k].iloc[0]) for k in ("open", "high", "low", "close"))
                locked_up = limit_status(o, h, l, c, float(prevrow["close"].iloc[0])).limit_up
            row1 = d[d["date"] == t1]
            prev1 = d[d["date"] < t1].tail(1)
            if not row1.empty and not prev1.empty:
                o, h, l, c = (float(row1[k].iloc[0]) for k in ("open", "high", "low", "close"))
                locked_dn = limit_status(o, h, l, c, float(prev1["close"].iloc[0])).limit_down
            if act == "ADD" and locked_up:
                drop["ADD 公告日鎖漲停"] += 1
                continue
            m = mcap(code)
            if not m:
                drop["事件股無市值"] += 1
                continue
            if cand_cache is None:
                cand_cache = {}
                for cc in ctrl_pool:
                    if cc in group_codes:
                        continue
                    r_ = tw.cum_return(tw.daily(cc), t0, t1)
                    if r_ is None or not liq_ok(cc):
                        continue
                    mc = mcap(cc)
                    if mc:
                        cand_cache[cc] = (ind.get(cc), mc, r_)
            same = [(abs(math.log(mc / m)), cc, r_) for cc, (ic, mc, r_) in cand_cache.items()
                    if ic and ic == ind.get(code) and cc != code]
            same.sort()
            ctrl = same[:N_CTRL]
            if not ctrl:
                drop["沒有同產業控制組"] += 1
                continue
            cret = float(np.mean([x[2] for x in ctrl]))
            raw_diff = ret - cret
            sign_cost = -COST1 if act == "ADD" else COST1
            recs.append({
                "group": f"{ann}→{eff}", "etfs": sorted(g["etfs"]), "code": code, "action": act,
                "t0": d0, "t1": t1.strftime("%Y-%m-%d"), "half": "2022-2023" if eff[:4] in ("2022", "2023") else "2024",
                "ret": ret, "bench_0050": bench, "excess_0050": (ret - bench) if bench is not None else None,
                "ctrl": [x[1] for x in ctrl], "ctrl_ret": cret, "raw_diff": raw_diff,
                "net_diff_1x": raw_diff + sign_cost, "net_diff_2x": raw_diff + 2 * sign_cost, "net_diff_3x": raw_diff + 3 * sign_cost,
                "del_locked_down_on_t1": bool(act == "DEL" and locked_dn), "n_ctrl": len(ctrl),
            })
    df = pd.DataFrame(recs)
    res = {"prereg": PREREG, "counts": counts, "dropped": dict(drop), "cost_1x": COST1,
           "n_records": len(df)}
    if df.empty:
        res.update(verdict="資料不足", reason="沒有任何可用筆數")
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    n_groups = df["group"].nunique()
    per_side = df["action"].value_counts().to_dict()
    gph = df.groupby("half")["group"].nunique().to_dict()
    res.update(n_groups=n_groups, per_side=per_side, groups_per_half=gph,
               del_locked_down_on_t1=int(df["del_locked_down_on_t1"].sum()),
               ctrl_size_hist=df["n_ctrl"].value_counts().sort_index().to_dict())
    insufficient = (n_groups < MIN_GROUPS or per_side.get("ADD", 0) < MIN_PER_SIDE or per_side.get("DEL", 0) < MIN_PER_SIDE
                    or min(gph.get("2022-2023", 0), gph.get("2024", 0)) < MIN_GROUPS_PER_HALF)
    if insufficient:
        res.update(verdict="資料不足", reason=f"門檻：群組≥{MIN_GROUPS}、每邊≥{MIN_PER_SIDE} 筆、每半≥{MIN_GROUPS_PER_HALF} 群組（定稿補充第 2 點）；未檢定")
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
        return 0

    rng = np.random.RandomState(SEED)
    glist = sorted(df["group"].unique())
    by_g = {g: df[df["group"] == g] for g in glist}

    def side_stats(act: str, sign: int) -> dict:
        sub = df[df["action"] == act]
        out = {"n": int(len(sub)), "n_groups": int(sub["group"].nunique())}
        for k in ("raw_diff", "net_diff_1x", "net_diff_2x", "net_diff_3x", "excess_0050", "ret", "ctrl_ret"):
            out[f"mean_{k}"] = float(sub[k].mean())
        boots = []
        for _ in range(N_BOOT):
            pick = rng.choice(glist, size=len(glist), replace=True)
            parts = [by_g[g][by_g[g]["action"] == act]["net_diff_1x"] for g in pick]
            vals = pd.concat(parts) if parts else pd.Series(dtype=float)
            if len(vals):
                boots.append(float(vals.mean()))
        boots = np.array(boots)
        out["boot_percentile"] = float(((boots > 0) if sign > 0 else (boots < 0)).mean() * 100) if len(boots) else None
        out["halves_net_1x"] = {h: float(s["net_diff_1x"].mean()) for h, s in sub.groupby("half")}
        out["halves_same_sign"] = all((v > 0) if sign > 0 else (v < 0) for v in out["halves_net_1x"].values()) and len(out["halves_net_1x"]) == 2
        out["pass_mean"] = (out["mean_net_diff_1x"] > 0) if sign > 0 else (out["mean_net_diff_1x"] < 0)
        out["pass_boot"] = out["boot_percentile"] is not None and out["boot_percentile"] >= 95
        return out

    h1, h2 = side_stats("ADD", +1), side_stats("DEL", -1)
    # 天條一：依生效日連乘每個群組 ADD 等權絕對報酬（扣 1× 成本）
    nav, peak, mdd, worst = 1.0, 1.0, 0.0, None
    path = []
    for g in sorted(glist, key=lambda x: x.split("→")[1]):
        a = by_g[g][by_g[g]["action"] == "ADD"]
        if a.empty:
            continue
        r = float(a["ret"].mean()) - COST1
        worst = r if worst is None else min(worst, r)
        nav *= 1 + r
        peak = max(peak, nav)
        mdd = max(mdd, 1 - nav / peak)
        path.append({"group": g, "ret_net": r, "nav": nav})
    survival = {"mdd": mdd, "worst_group": worst, "path": path, "violates": mdd > 0.5}
    passed = h1["pass_mean"] and h1["pass_boot"] and h2["pass_mean"] and h2["pass_boot"] and h1["halves_same_sign"] and h2["halves_same_sign"]
    verdict = "VIOLATES_SURVIVAL" if survival["violates"] else ("PASS" if passed else "FAIL")
    res.update(H1_ADD=h1, H2_DEL=h2, survival=survival, verdict=verdict,
               note="DEL 方為事件研究超額報酬，不是放空損益；放空數字未接借券資料（CLAUDE.md 七之三 ⑩）")
    res["records"] = recs
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    slim = {k: v for k, v in res.items() if k != "records"}
    slim["survival"] = {k: v for k, v in survival.items() if k != "path"}
    print(json.dumps(slim, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
