# -*- coding: utf-8 -*-
"""先.一五〇-1 第 2 批之十一：#446 core_tilt v2 成分內傾斜的樣本內最優化（描述性，非判定）。

方針（Cowork 收件匣 039 已定案）：掃參數挑最好的一組，只當描述性總表，不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。
構造：完全沿用 `core_tilt_v2_stage1.py` 的量尺（重建臺灣50、總報酬指數、成分異動以總市值定權、之後漂移）與
     A_4pass 成分內綜合分數、tilt() 映射、成本（round_trip_cost_pct() 按單邊換手）；只把三個原本寫死的常數拿來掃：
     傾斜幅度 TILT_PP ∈ {2,5,10,20}pp、產業偏離上限 ∈ {3pp, 不設}、再平衡間隔 ∈ {21,63} 日，
     另加方向 ∈ {順向（分數高加碼）, 反向}〔自行裁量：#446 原版順向超額為負，補測反向〕＝32 格＋不傾斜臂。
     組合層槓桿 L ∈ {1,1.5,2,3}×組合止損 ∈ {無,10%,20%,30%}（同 F8：融資 6.5%/年〔自行裁量〕，3× 只當參考）。
期間：量尺起點（2013-06）～2024-12-31（VAL_END），不讀 2025+。只讀本機快取、0 次網路請求。
`core_tilt_v2_stage1.py` 只 import 呼叫、不改原始碼（它不在十三節核心清單，但為了不動已登記試驗的程式，用模組屬性覆寫常數）。
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import core_tilt_v2_stage1 as C  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402  （overlay()／stats() 同一套）
from validation.costs import round_trip_cost_pct  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

END = "2024-12-31"
assert str(VAL_END)[:10] <= END
CACHE = HERE / "data" / "reaudit_optimized_batch2_coretilt_cells.json"
OUT_JSON = HERE / "data" / "reaudit_optimized_batch2_coretilt.json"
TILTS = (0.02, 0.05, 0.10, 0.20)
BANDS = (0.03, 1.0)       # 1.0＝不設產業偏離上限
REBALS = (21, 63)
SIGNS = (1, -1)
prog = S.prog


def main():
    budget = float(os.environ.get("REAUDIT_BUDGET_SEC", "1500"))
    deadline = time.time() + budget
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    grid = list(itertools.product(TILTS, BANDS, REBALS, SIGNS))
    key = lambda c: f"{c[0]}_{c[1]}_{c[2]}_{c[3]}"
    todo = [c for c in grid if key(c) not in cache] + ([] if "untilted" in cache else ["untilted"])
    if todo:
        t0 = time.time()
        inp = C.load_inputs()
        prog(f"載入完成 {time.time()-t0:.0f}s：成分聯集 {len(inp['members'])}、有因子 {len(inp['data'])}")
        assert max(inp["days"]) <= END
        cost_rt = round_trip_cost_pct()
        sc_cache: dict = {}

        def scores(b, m):
            k = (b, tuple(m))
            if k not in sc_cache:
                sc_cache[k] = C.scores_at(b, m, inp)
            return sc_cache[k]
        seg_cache = {}
        for c in todo:
            if time.time() > deadline:
                prog("時間到，存斷點")
                break
            t1 = time.time()
            if c == "untilted":
                C.REBAL_EVERY = 21
                segs = seg_cache.setdefault(21, C.segments(inp))
                _, un, _, _, log = C.simulate(inp, segs, None, cost_rt)
                r = un
            else:
                tp, band, reb, sign = c
                C.TILT_PP, C.INDUSTRY_BAND_PP, C.REBAL_EVERY = tp, band, reb
                if reb not in seg_cache:
                    seg_cache[reb] = C.segments(inp)
                fn = (lambda b, m: scores(b, m)) if sign > 0 else (lambda b, m: -scores(b, m))
                _, _, _, r, log = C.simulate(inp, seg_cache[reb], fn, cost_rt)
            r = r.dropna()
            r = r[r.index <= END]
            # 換股期報酬（勝率用）：每段起點切
            bases = [x["base"] for x in log]
            eq = (1 + r).cumprod()
            per = []
            pts = [d for d in bases if d in eq.index] + [eq.index[-1]]
            for a, b in zip(pts[:-1], pts[1:]):
                per.append(float(eq[b] / eq[a] - 1))
            cache[c if c == "untilted" else key(c)] = {
                "dates": [str(x)[:10] for x in r.index], "ret": [float(x) for x in r],
                "n_rebalances": len(log), "win_rate": float(np.mean([p > 0 for p in per])) if per else None,
                "mean_turnover": float(np.mean([x["turnover_tilted"] for x in log])) if log else None}
            CACHE.write_text(json.dumps(cache), encoding="utf-8")
            prog(f"{c} 完成（{time.time()-t1:.0f}s）")
    n_grid = len(grid) + 1
    if len(cache) < n_grid:
        prog(f"格子未跑完：{len(cache)}／{n_grid}，下次接續")
        return 2
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    rows = []
    for k, c in cache.items():
        dates = pd.to_datetime(pd.Series(c["dates"]))
        assert dates.max() <= pd.Timestamp(END)
        eq = np.concatenate([[1.0], np.cumprod(1 + np.array(c["ret"], float))])
        d2 = pd.concat([pd.Series([dates.iloc[0] - pd.Timedelta(days=1)]), dates], ignore_index=True)
        rf = LB.load_tw_rf_daily(d2)
        for L, stop in itertools.product(S.LEVS, S.STOPS):
            curve, _ = S.overlay(eq, rf, L, stop)
            cagr, mdd, sh = S.stats(curve, d2)
            if k == "untilted":
                tp = band = reb = sign = None
            else:
                tp, band, reb, sign = k.split("_")
            rows.append({"key": k, "tilt_pp": None if tp is None else float(tp), "band": None if band is None else float(band),
                         "rebalance_days": None if reb is None else int(reb), "sign": None if sign is None else int(sign),
                         "L": L, "stop": stop, "cagr": cagr, "mdd": mdd, "sharpe": sh,
                         "calmar": cagr / abs(mdd) if mdd < 0 else None,
                         "win_rate": c["win_rate"], "n_trades": c["n_rebalances"]})
    df = pd.DataFrame(rows)
    tilted = df[df["key"] != "untilted"]
    ok = tilted[tilted["mdd"] >= -0.50]

    def pack(b):
        st = b["stop"]
        st = None if st is None or st != st else float(st)
        return {"tilt_pp": float(b["tilt_pp"]), "industry_band": None if b["band"] >= 1.0 else float(b["band"]),
                "rebalance_days": int(b["rebalance_days"]), "direction": "順向" if int(b["sign"]) > 0 else "反向",
                "L": float(b["L"]), "stop": st, "cagr": float(b["cagr"]), "mdd": float(b["mdd"]), "sharpe": float(b["sharpe"]),
                "trades": int(b["n_trades"]), "win_rate": b["win_rate"], "calmar": float(b["calmar"]),
                "violates_survival": bool(b["mdd"] < -0.50)}
    best = ok.sort_values("calmar", ascending=False).iloc[0]
    best_ret = ok.sort_values("cagr", ascending=False).iloc[0]
    u1 = df[(df["key"] == "untilted") & (df["L"] == 1.0) & (df["stop"].isna())].iloc[0]
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_start": cache["untilted"]["dates"][0], "data_end": END,
           "benchmark_untilted_rebuilt_0050": {"cagr": float(u1["cagr"]), "mdd": float(u1["mdd"]), "sharpe": float(u1["sharpe"])},
           "families": [{"id": "F17", "title": "#446 core_tilt v2 成分內傾斜（重建臺灣50 總報酬量尺）",
                         "source_trials": [445, 446], "n_grid": int(len(tilted)),
                         "best_by_calmar": pack(best), "best_by_cagr_within_mdd50": pack(best_ret),
                         "n_violates": int((tilted["mdd"] < -0.50).sum()),
                         "curve_png": "research/data/reaudit_curves/batch2_F17.png"}],
           "notes": "樣本內最優化（描述性）；量尺＝重建臺灣50（缺自由流通係數、台積電權重偏低約 7pp）；總報酬（含息）；"
                    "成本＝round_trip_cost_pct() 按單邊換手；交易次數＝權重重設次數（成分異動＋傾斜再平衡）、勝率＝重設期間報酬>0 比例；"
                    "3× 超過台股融資上限只當參考；融資追繳以權益歸零近似。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for k, lab, col, L, st in ((best["key"], "best (Calmar)", "#2a6fdb", best["L"], best["stop"]),
                               ("untilted", "untilted rebuilt 0050 (1x)", "#999999", 1.0, None)):
        c = cache[k]
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.concatenate([[1.0], np.cumprod(1 + np.array(c["ret"], float))])
        d2 = pd.concat([pd.Series([dates.iloc[0] - pd.Timedelta(days=1)]), dates], ignore_index=True)
        st = None if st is None or st != st else st
        curve, _ = S.overlay(eq, LB.load_tw_rf_daily(d2), L, st)
        ax.plot(d2, curve, label=lab, color=col)
    ax.set_yscale("log"); ax.legend(); ax.set_title("F17 core_tilt v2 in-constituent tilt (in-sample optimized, 2013-2024)")
    fig.tight_layout()
    fig.savefig(HERE / "data" / "reaudit_curves" / "batch2_F17.png", dpi=110)
    prog(f"最佳 {pack(best)}")
    prog(f"MDD≤50% 年化最高 {pack(best_ret)}")
    prog(f"不傾斜臂 1× {u1['cagr']:+.1%}／{u1['mdd']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
