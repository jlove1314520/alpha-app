# -*- coding: utf-8 -*-
"""先.一五四-1a ⑥ 紙上優化軌 F17（core_tilt v2 成分內 A_4pass 傾斜）每日訊號產生器——研究帽產物，零外部請求。

策略（照 reaudit_optimized_batch2_coretilt.json best_by_calmar，不調參）：
  順向、傾斜 ±2pp、產業偏離上限 3pp、每 63 個交易日再平衡、1×、帳戶停損 10%（停 21 日、期間領無風險利率）。
  構造照 core_tilt_v2_stage1.simulate()：
    - 不傾斜臂權重：成分異動時重設、之後隨價格漂移；傾斜再平衡日以「漂移後的不傾斜權重」為基準。
    - 傾斜：直接呼叫 core_tilt_v2_stage1.tilt()（min-max→[-1,1]×2pp、截 0、產業偏離 >3pp 縮放）。
    - 分數：直接呼叫 portfolio_backtest_v2.compute_composite_at_date()＋_eligible()（A_4pass equal、產業內 z、流動性門檻）。
    - 成本：單邊換手 × validation.costs.round_trip_cost_pct()，扣在再平衡後的第一個交易日（同 simulate()）。
    - 帳戶層：照 reaudit_optimized_batch2_sector.overlay()（L=1、stop=10%、COOLDOWN 21、停損中領 rf）。
  與回測口徑的差異（照實揭露）：
    ① 成分與權重：回測＝重建臺灣50＋成分異動日以總市值定權；紙上＝元大官方 0050 持股權重（data/tw50_constituents.json，
       每週 1 次、history 只在異動時新增），台積電官方權重約 58%，回測重建版約低 7pp。
    ② 價格：回測＝總報酬指數；紙上＝官方日檔還原日報酬（收盤÷(收盤−漲跌)−1）＋之後 price_history 還原收盤比值（同 F12／F14）。
    ③ EPS：2024 以前用本機 FinMind 季報快取（EPS），2025 起用 data/stock_detail.json＋financials_backfill.json 官方季報；
       可得日一律 pit.statutory_quarterly_pit_date()（法定期限）。月營收＝2024 以前 FinMind 快取＋revenue_backfill.json＋fundamentals.json（官方檔 2024-12～2025-04 有缺口，
       單用官方檔 12 個月滾動標準差會全是缺值），可得日＝次月 10 日（回測有 create_time 時用實際公告日）。
  因子公式：直接呼叫 factors._eps_yoy_growth／_eps_surprise_sue（把 quarterly_pit 換成上面合併的 EPS 表）、
    factors._revenue_surprise_sue（換 month_revenue_pit）、f_low_vol＝−60 日日報酬標準差（同 factors.py）。
輸出（append-only）：research/data/paper_opt/ledger_F17.jsonl、state_F17.json。
用法：python research/paper_opt_f17.py [--probe]
非投資建議。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402
import paper_opt_f14 as F14  # noqa: E402

OUT = F12.OUT
LEDGER = OUT / "ledger_F17.jsonl"
STATE = OUT / "state_F17.json"
BARS = OUT / "f17_bars.json"
EPS_CACHE = OUT / "f17_eps_pre2025.json"
REV_CACHE = OUT / "f17_rev_pre2025.json"
TW50 = F12.DATA / "tw50_constituents.json"
START = F12.START
TILT_PP, BAND, REBAL, STOP, COOLDOWN, L = 0.02, 0.03, 63, 0.10, 21, 1.0
COMPONENTS = ["eps_family", "revenue_surprise", "low_vol"]
Q_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def tw50() -> tuple[str, dict[str, float]]:
    d = F12._rj(TW50, {})
    w = {r["code"]: float(r["weight_pct"]) for r in d.get("weights") or [] if r.get("weight_pct")}
    tot = sum(w.values())
    return d.get("as_of", ""), {k: v / tot for k, v in w.items()} if tot else {}


# ------------------------------------------------------------------ EPS（舊段 FinMind 快取＋新段官方季報）
def _eps_pre2025(ids: list[str]) -> dict[str, dict[str, float]]:
    c = F12._rj(EPS_CACHE, {})
    miss = [s for s in ids if s not in c]
    if miss:
        import pandas as pd
        raw = HERE / "data" / "raw"
        for sid in miss:
            fs = sorted(raw.glob(f"TaiwanStockFinancialStatements__{sid}__*__2024-12-31.parquet"))
            got: dict[str, float] = {}
            for p in fs:  # 檔名起日由早到晚；同期別後讀覆蓋（內容應相同）
                try:
                    f = pd.read_parquet(p, columns=["date", "type", "value"])
                except Exception:
                    continue
                f = f[(f["type"] == "EPS") & (f["date"] <= "2024-12-31")]
                got.update({str(dt)[:10]: float(v) for dt, v in zip(f["date"], f["value"])})
            c[sid] = got
        F12._wj(EPS_CACHE, c)
    return {s: c.get(s, {}) for s in ids}


def eps_frames(ids: list[str]):
    import pandas as pd
    from pit import statutory_quarterly_pit_date
    old = _eps_pre2025(ids)
    new: dict[str, dict] = {}
    for sid, qq in F12_quarters().items():
        if sid in ids:
            for (y, q), r in qq.items():
                if r.get("eps") is not None and y >= 2025:
                    new.setdefault(sid, {})[f"{y}-{Q_END[q]}"] = float(r["eps"])
    out = {}
    for sid in ids:
        m = dict(old.get(sid, {}))
        m.update(new.get(sid, {}))
        rows = [{"fiscal_period_end": k, "EPS": v,
                 "pit_date": statutory_quarterly_pit_date(pd.Timestamp(k)).strftime("%Y-%m-%d")} for k, v in sorted(m.items())]
        out[sid] = pd.DataFrame(rows, columns=["pit_date", "fiscal_period_end", "EPS"])
    return out


def _rev_pre2025(ids: list[str]) -> dict[str, dict[str, float]]:
    c = F12._rj(REV_CACHE, {})
    miss = [s for s in ids if s not in c]
    if miss:
        import pandas as pd
        raw = HERE / "data" / "raw"
        for sid in miss:
            got: dict[str, float] = {}
            for p in sorted(raw.glob(f"TaiwanStockMonthRevenue__{sid}__*__2024-12-31.parquet")):
                try:
                    f = pd.read_parquet(p, columns=["revenue", "revenue_year", "revenue_month"])
                except Exception:
                    continue
                for y, m, v in zip(f["revenue_year"], f["revenue_month"], f["revenue"]):
                    if int(y) * 100 + int(m) <= 202412 and v == v:
                        got[str(int(y) * 100 + int(m))] = float(v)
            c[sid] = got
        F12._wj(REV_CACHE, c)
    return {s: c.get(s, {}) for s in ids}


def rev_frames(ids: list[str]):
    """月營收：2024 以前 FinMind 快取＋revenue_backfill.json＋fundamentals.json（後者覆蓋前者）；pit_date＝次月 10 日。"""
    import pandas as pd
    import paper_opt_pq as PQ
    from pit import _next_month_10th
    old, new = _rev_pre2025(ids), PQ._revenues()
    out = {}
    for sid in ids:
        m = {int(k): v for k, v in old.get(sid, {}).items()}
        m.update({int(k): float(v) for k, v in (new.get(sid) or {}).items()})
        out[sid] = pd.DataFrame([{"revenue_year": ym // 100, "revenue_month": ym % 100, "revenue": v,
                                  "pit_date": _next_month_10th(ym // 100, ym % 100)} for ym, v in sorted(m.items())],
                                columns=["revenue_year", "revenue_month", "revenue", "pit_date"])
    return out


def F12_quarters():
    import paper_opt_pq as PQ
    return PQ._quarters()


# ------------------------------------------------------------------ 分數
def scores_at(day: str, members: list[str], bars: dict, epsf: dict, revf: dict, industry: dict):
    import numpy as np
    import pandas as pd
    import factors as F
    import portfolio_backtest_v2 as pb2
    data, liq = {}, {}
    for sid in members:
        b = bars.get(sid) or {}
        if day not in b:
            continue
        ds, lv = F12.adj_levels({d: v[:5] for d, v in b.items()})
        d = pd.DataFrame({"date": ds, "adj_close": lv,
                          "Trading_money": [float(b[x][6]) if b[x][6] is not None else np.nan for x in ds]})
        d = d[d["date"] <= day].reset_index(drop=True)
        d["f_low_vol"] = -d["adj_close"].pct_change().rolling(F.LOW_VOL_WINDOW, min_periods=F.LOW_VOL_WINDOW).std()
        orig = F.quarterly_pit
        F.quarterly_pit = lambda *_a, _q=epsf.get(sid): (_q.copy() if _q is not None else pd.DataFrame())
        try:
            d = F._asof_join(d, F._eps_yoy_growth(sid, ""), "eps_yoy", "f_eps_growth")
            d = F._asof_join(d, F._eps_surprise_sue(sid, ""), "eps_sue", "f_eps_surprise")
        finally:
            F.quarterly_pit = orig
        orig = F.month_revenue_pit
        F.month_revenue_pit = lambda *_a, _r=revf.get(sid): (_r.copy() if _r is not None else pd.DataFrame())
        try:
            d = F._asof_join(d, F._revenue_surprise_sue(sid, ""), "revenue_sue", "f_revenue_surprise")
        finally:
            F.month_revenue_pit = orig
        data[sid] = d.iloc[[-1]].reset_index(drop=True)
        liq[sid] = pb2._liquidity_proxy_series(d)
    if not data:
        return {}, {}
    cs = pb2._eligible(pb2.compute_composite_at_date(day, data, industry, COMPONENTS, "equal", pd.Series(dtype=object), liq))
    cs = cs[cs["composite"].notna()]
    cov = {c: round(sum(1 for x in data.values() if x[col].notna().iloc[0]) / len(data), 4)
           for c, col in (("eps_growth", "f_eps_growth"), ("eps_surprise", "f_eps_surprise"),
                          ("revenue_surprise", "f_revenue_surprise"), ("low_vol", "f_low_vol"))}
    return dict(zip(cs["stock_id"], cs["composite"].astype(float))), cov


def tilt(w: dict, comp: dict, industry: dict) -> dict:
    import pandas as pd
    import core_tilt_v2_stage1 as C
    C.TILT_PP, C.INDUSTRY_BAND_PP = TILT_PP, BAND
    s = pd.Series(w, dtype=float)
    out = C.tilt(s / s.sum(), pd.Series(comp, dtype=float), industry)
    return {k: float(v) for k, v in out.items()}


# ------------------------------------------------------------------ 一日
def step(day: str, s: dict, bars: dict, ctx: dict) -> dict:
    e = s["engine"]
    log: dict = {}
    # ① 前一日收盤權重 × 今日報酬（沒價格＝當日 0，同 simulate() 的 ffill）
    r = 0.0
    if e["w_t"]:
        rets = {k: (bars.get(k, {}).get(day) or [None] * 5)[4] or 0.0 for k in e["w_t"]}
        r = sum(e["w_t"][k] * rets[k] for k in e["w_t"])
        for key in ("w_u", "w_t"):
            g = {k: v * (1 + rets.get(k, 0.0)) for k, v in e[key].items()}
            t = sum(g.values())
            e[key] = {k: v / t for k, v in g.items()} if t > 0 else g
    r -= e.pop("pending_cost", 0.0)
    e["v_u"] *= 1 + r
    # ② 帳戶層（overlay 同一套）
    a = s["acct"]
    if a["in_pos"]:
        a["v"] *= 1 + L * r - (L - 1) * F12.MARGIN_RATE
        a["v"] = max(a["v"], 0.0)
        a["peak"] = max(a["peak"], a["v"])
        if a["v"] < a["peak"] * (1 - STOP):
            a.update(in_pos=False, cool=COOLDOWN, n_stop=a["n_stop"] + 1)
            log["account_stop"] = True
    else:
        a["v"] *= 1 + ctx["rf"]
        a["cool"] -= 1
        if a["cool"] <= 0:
            a.update(in_pos=True, peak=a["v"])
    # ③ 收盤：成分異動或每 63 日 → 重設權重（隔日生效）
    as_of, off = ctx["tw50"]
    kind = None
    key = ",".join(sorted(off))  # 只比對成分代號集合（as_of 每週都會更新，權重不同不算異動）
    if e.get("members_key") != key:
        kind = "change"
    elif e["day_i"] % REBAL == 0:
        kind = "tilt"
    if kind:
        have = [k for k in (off if kind == "change" else e["w_u"]) if (bars.get(k) or {}).get(day)]
        if kind == "change":
            new_u = {k: off[k] for k in have}
        else:  # 漂移後的不傾斜權重；當天沒價的成分沿用（同 simulate() 不因再平衡日剛好沒價而剔除）
            new_u = dict(e["w_u"])
        tot = sum(new_u.values())
        new_u = {k: v / tot for k, v in new_u.items()}
        comp, cov = scores_at(day, list(new_u), bars, ctx["eps"], ctx["rev"], ctx["industry"])
        new_t = tilt(new_u, comp, ctx["industry"])
        turn = 0.5 * sum(abs(new_t.get(k, 0.0) - e["w_t"].get(k, 0.0)) for k in set(new_t) | set(e["w_t"])) if e["w_t"] else 0.0
        e["pending_cost"] = turn * ctx["cost_rt"]
        e["w_u"], e["w_t"] = new_u, new_t
        if kind == "change":
            e["members_key"], e["members_as_of"] = key, as_of
        cw = sum(new_u.get(k, 0.0) for k in comp)
        log["rebalance"] = {"kind": kind, "n_members": len(new_u), "n_scored": len(comp), "coverage_w": round(cw, 4),
                            "factor_coverage": cov, "turnover": round(turn, 4),
                            "top_tilt": sorted(((k, round(new_t[k] - new_u.get(k, 0), 4)) for k in new_t), key=lambda x: -x[1])[:5]}
    e["day_i"] += 1
    return {"date": day, "ret": round(a["v"] / s["last_v"] - 1, 8), "ret_1x": round(r, 8), "equity": round(a["v"] * F12.INIT, 2),
            "exposure": L if a["in_pos"] else 0.0, "n_holdings": len(e["w_t"]), **log}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    from score import load_industry_map
    from validation.costs import round_trip_cost_pct
    as_of, off = tw50()
    if not off:
        print("[warn] 讀不到 tw50_constituents.json 權重，本次不記帳")
        return 0
    ids = sorted(off)
    F14.BARS = BARS
    bars, calendar = F14.build_bars(ids)
    ctx = {"tw50": (as_of, off), "eps": eps_frames(ids), "rev": rev_frames(ids), "industry": load_industry_map(),
           "cost_rt": round_trip_cost_pct(), "rf": F12.rf_daily()}
    if a.probe:
        day = calendar[-1]
        comp, cov = scores_at(day, ids, bars, ctx["eps"], ctx["rev"], ctx["industry"])
        t = tilt({k: off[k] for k in ids if (bars.get(k) or {}).get(day)}, comp, ctx["industry"])
        print(f"成分 {len(ids)} 檔（官方 as_of {as_of}）；最新交易日 {day}；日曆 {calendar[0]}～{day} 共 {len(calendar)} 天")
        print(f"有分數 {len(comp)} 檔；因子覆蓋率 {cov}；來回成本 {ctx['cost_rt']:.4%}")
        d = sorted(((k, t[k] - off.get(k, 0)) for k in t), key=lambda x: -x[1])
        print("加碼前 5：", [f"{k}:{v:+.2%}" for k, v in d[:5]], "減碼前 5：", [f"{k}:{v:+.2%}" for k, v in d[-5:]])
        print(f"傾斜後權重和 {sum(t.values()):.6f}；台積電 官方 {off.get('2330', 0):.2%} → {t.get('2330', 0):.2%}")
        return 0
    s = F12._rj(STATE, None) or {"start": START, "last_date": None, "last_v": 1.0,
                                  "engine": {"w_u": {}, "w_t": {}, "members_key": None, "members_as_of": None, "day_i": 0, "v_u": 1.0},
                                  "acct": {"v": 1.0, "peak": 1.0, "in_pos": True, "cool": 0, "n_stop": 0}}
    if a.start != START:
        s["start"] = a.start
    done = 0
    for day in calendar:
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        rec = step(day, s, bars, ctx)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"], s["last_v"] = day, s["acct"]["v"]
        done += 1
        print(f"{day} {rec['ret']:+.2%}　曝險 {rec['exposure']}" + ("　再平衡" if "rebalance" in rec else ""))
    F12._wj(STATE, s)
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f17 失敗：{e}")
        sys.exit(0)
