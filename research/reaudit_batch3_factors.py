# -*- coding: utf-8 -*-
"""先.一五五-3 第二批 ③：因子家族「前 N 檔等權」最優化（紙上優化軌描述性，非判定；Cowork 收件匣 039 已定案）。

不寫 TRIALS_LEDGER（心跳寫 PROGRESS_HEARTBEAT.jsonl）。零新外部請求。非投資建議。
做法完全沿用 F13（`reaudit_optimized_batch2_roe.py`）：
- 宇宙：#133 抽樣 236 檔快取 `research/data/reaudit_ssu_loaded.pkl`（因子欄由 `factor_ic.load_sample_with_factors()` 算好、PIT）。
- 期間：2015-01～2024-12（本批先跑 2024 底前；2025 起延長要重算財報因子，見 REAUDIT_OPTIMIZED.md 第 5 節待辦）。
- 引擎 `research/backtest/engine.py`（只呼叫、不改）：下一交易日成交、漲跌停不成交、下市照引擎處理、全成本。
- 只做多頭（放空腿硬規則）；方向 dir=+1 挑分數最高、dir=-1 挑分數最低（反向也掃，失敗必附變形方向之一）。
- 引擎格：換股 {21,63} × 大盤 200MA 閘門 {開,關} × N {10,20,30} × 個股停損 {15%,不設} × 方向 {+,-}＝48 格；
  組合層 L {1,1.5,2,3} × 組合止損 {無,10%,20%,30%}（融資 6.5%/年，3× 超過台股融資上限只當參考）。

用法：python research/reaudit_batch3_factors.py run f_eps_surprise f_value_pe ...   （有斷點快取，時間到存檔離開）
     python research/reaudit_batch3_factors.py summarize [1|2]                    （彙總已跑完的族；第 2 批寫第 6 節）
環境變數 REAUDIT_DEADLINE＝epoch 秒，到了就不再開新格。
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import pickle
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

import reaudit_optimized_batch2_sector as S  # noqa: E402  （overlay()／stats() 同一套）

START, END = "2015-01-01", "2024-12-31"
CELLS_DIR = HERE / "data" / "reaudit_batch3_cells"
OUT_JSON = HERE / "data" / "reaudit_batch3_batch1.json"
REBALS, GATES, TOPNS, PSTOPS, DIRS = (21, 63), (1, 0), (10, 20, 30), (0.15, 1.0), (1, -1)
BATCH1 = ["f_eps_surprise", "f_revenue_surprise", "f_eps_growth", "f_value_pe", "f_value_pb", "f_low_vol",
          "f_rel_strength", "f_52w_high_prox", "f_dividend_yield_ttm", "f_gross_profitability"]
# 第 2 批（DevQueue 20261107-060102）：第 4 節清單裡 pkl 已有因子欄的 10 族（曾 PASS／CHEAP_PASS 優先，其餘 FAIL 族補滿）
BATCH2 = ["f_bab", "f_inst_flow", "f_margin_utilization", "f_foreign_streak", "f_idio_vol", "f_ma_breakout",
          "f_short_margin_ratio", "f_residual_momentum", "f_short_reversal_1m", "f_short_term_reversal_1w"]
# 第 3 批（DevQueue 20261107-073102）：pkl 已有因子欄、第 4 節「待做」的 5 族＋人工複核改類的 f_inst_streak_days
# 〔自行裁量：清單自動標「非策略」，但它是 pkl 現成因子欄、可直接轉成前 N 檔等權月換股，人工複核改列入〕
BATCH3 = ["f_accruals", "f_amihud_illiq", "f_asset_growth", "f_gross_margin_stability", "f_listing_age_days",
          "f_inst_streak_days"]
BATCHES = {"1": BATCH1, "2": BATCH2, "3": BATCH3}
prog = S.prog


def grid():
    return list(itertools.product(REBALS, GATES, TOPNS, PSTOPS, DIRS))


def key(c):
    return f"{c[0]}_{c[1]}_{c[2]}_{c[3]}_{c[4]}"


def cells_path(fac):
    return CELLS_DIR / f"{fac}.json"


def prep(data, fac):
    out = {}
    for sid, df in data.items():
        d = df.sort_values("date").reset_index(drop=True).copy()
        px = d["adj_close"] if "adj_close" in d.columns else d["close"]
        d["ma150"] = px.rolling(150, min_periods=150).mean()  # 引擎第一層出場讀這欄（同 F13）
        d["_score"] = d[fac].astype(float)
        out[sid] = d
    return out


def make_fn(look, gate_on, gate_dates, direction):
    def fn(price_data, as_of, market_df):
        a = str(as_of)[:10]
        if gate_on and a not in gate_dates:
            return {}
        sc = {}
        for sid in price_data:
            v = look.get(sid, {}).get(a)
            if v is not None and v == v:
                sc[sid] = direction * float(v)
        return sc
    return fn


def run(facs, deadline):
    from backtest.engine import BacktestConfig, run_backtest
    from factor_ic import START_DATE
    from finmind_client import load_dev
    from strategies.weinstein_stage2 import prepare_market_data
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    market_df = prepare_market_data(load_dev("TaiwanStockPrice", "TAIEX", START_DATE))
    gate_dates = set(market_df.loc[market_df["gate"] == True, "date"].astype(str).str[:10])  # noqa: E712
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    for fac in facs:
        cp = cells_path(fac)
        cache = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
        todo = [c for c in grid() if key(c) not in cache]
        if not todo:
            continue
        p = prep(data, fac)
        look = {sid: dict(zip(d["date"].astype(str).str[:10], d["_score"])) for sid, d in p.items()}
        prog(f"{fac}：待跑 {len(todo)}／{len(grid())} 格")
        for c in todo:
            if time.time() > deadline:
                prog("時間到，存斷點")
                return False
            rb, g, top_n, pstop, dr = c
            t0 = time.time()
            cfg = BacktestConfig(start_date=START, end_date=END, max_positions=top_n, rebalance_every_n_days=rb,
                                 stop_loss_pct=pstop, book_name="reaudit_batch3")
            res = run_backtest(make_fn(look, bool(g), gate_dates, dr), p, market_df, cfg)
            ec, tr = res.equity_curve, res.trades
            sells = tr[tr["side"].isin(["sell", "close"])] if not tr.empty else tr
            cache[key(c)] = {"dates": [str(x)[:10] for x in ec["date"]], "equity": [float(x) for x in ec["equity"]],
                             "n_round_trips": int(len(sells)),
                             "win_rate": float((sells["realized_pnl"] > 0).mean()) if len(sells) else None}
            cp.write_text(json.dumps(cache), encoding="utf-8")
            prog(f"{fac} {key(c)} 完成（{time.time()-t0:.0f}s）")
    return True


def summarize(batch="1"):
    global OUT_JSON, MK_B, MK_E
    if batch != "1":
        OUT_JSON = HERE / "data" / f"reaudit_batch3_batch{batch}.json"
        MK_B, MK_E = f"<!-- BATCH3-B{batch}-BEGIN -->", f"<!-- BATCH3-B{batch}-END -->"
    sys.argv = [sys.argv[0], "--formula", "421"]
    import leveraged_bb90_backtest as LB
    fams, rf_cache = [], {}
    for fac in BATCHES[batch]:
        cp = cells_path(fac)
        if not cp.exists():
            continue
        cache = json.loads(cp.read_text(encoding="utf-8"))
        done = len(cache)
        rows = []
        for k, c in cache.items():
            rb, g, top_n, pstop, dr = k.split("_")
            dates = pd.to_datetime(pd.Series(c["dates"]))
            assert dates.max() <= pd.Timestamp(END)
            eq = np.array(c["equity"], float); eq = eq / eq[0]
            dk = (str(dates.iloc[0]), len(dates))
            if dk not in rf_cache:
                rf_cache[dk] = LB.load_tw_rf_daily(dates)
            for L, stop in itertools.product(S.LEVS, S.STOPS):
                curve, _ = S.overlay(eq, rf_cache[dk], L, stop)
                cagr, mdd, sh = S.stats(curve, dates)
                rows.append({"rebalance_days": int(rb), "market_gate": bool(int(g)), "top_n": int(top_n),
                             "pos_stop": None if float(pstop) >= 1.0 else float(pstop), "direction": int(dr),
                             "L": L, "stop": stop, "cagr": cagr, "mdd": mdd, "sharpe": sh,
                             "calmar": cagr / abs(mdd) if mdd < 0 else None,
                             "win_rate": c["win_rate"], "trades": c["n_round_trips"], "key": k})
        df = pd.DataFrame(rows)
        ok = df[df["mdd"] >= -0.50]

        def pack(b):
            d = {k2: (None if (isinstance(v, float) and v != v) else v) for k2, v in b.items()}
            d["violates_survival"] = bool(b["mdd"] < -0.50)
            return d
        base = df[(df["L"] == 1.0) & df["stop"].isna()]
        fams.append({"factor": fac, "cells_done": done, "cells_total": len(grid()), "n_grid": int(len(df)),
                     "n_violates": int((df["mdd"] < -0.50).sum()),
                     "best_by_calmar": pack(ok.sort_values("calmar", ascending=False).iloc[0].to_dict()) if len(ok) else None,
                     "best_by_cagr_within_mdd50": pack(ok.sort_values("cagr", ascending=False).iloc[0].to_dict()) if len(ok) else None,
                     "best_1x_nostop_forward": pack(base[base["direction"] == 1].sort_values("calmar", ascending=False).iloc[0].to_dict()) if len(base[base["direction"] == 1]) else None,
                     "best_1x_nostop_reverse": pack(base[base["direction"] == -1].sort_values("calmar", ascending=False).iloc[0].to_dict()) if len(base[base["direction"] == -1]) else None})
    from finmind_client import load_dev
    from factor_ic import START_DATE
    m = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    m = m[(m["date"] >= START) & (m["date"] <= END)].sort_values("date")
    mc = m["close"].to_numpy(float)
    bcagr, bmdd, bsh = S.stats(mc / mc[0], pd.to_datetime(m["date"]).reset_index(drop=True))
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_start": START, "data_end": END,
           "benchmark_taiex_price_index": {"cagr": bcagr, "mdd": bmdd, "sharpe": bsh}, "families": fams,
           "notes": "樣本內最優化（描述性）；宇宙為 #133 抽樣 236 檔（今天的名冊抽樣，存活者偏誤未完全排除）；只做多頭；"
                    "3× 超過台股融資上限只當參考；融資追繳以權益歸零近似；交易次數＝個股賣出筆數、勝率＝賣出已實現損益>0 比例。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    out["batch"] = batch
    plot_and_render(out, LB)
    for f in fams:
        b = f["best_by_calmar"]
        prog(f"{f['factor']} {f['cells_done']}/{f['cells_total']}：" + (f"{b['key']} L={b['L']} stop={b['stop']} {b['cagr']:+.1%}／{b['mdd']:.1%}／Sh {b['sharpe']:.2f}" if b else "無"))
    prog(f"TAIEX 價格指數 {bcagr:+.1%}／{bmdd:.1%}")
    return 0


MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B1-BEGIN -->", "<!-- BATCH3-B1-END -->"


def _fmt_params(b):
    st = "無" if b["stop"] is None else f"{b['stop']:.0%}"
    ps = "不設" if b["pos_stop"] is None else f"{b['pos_stop']:.0%}"
    return (f"{'順向（分數高）' if b['direction'] == 1 else '反向（分數低）'}，換股 {b['rebalance_days']} 日，"
            f"大盤閘門 {'開' if b['market_gate'] else '關'}，N={b['top_n']}，個股停損 {ps}，L={b['L']:g}，組合止損 {st}")


def _old_table():
    """讀第 0 節總表（排名、家族、綜合分數），用來算新族會插在第幾名。"""
    rows = []
    for ln in MD.read_text(encoding="utf-8").split("## 1.")[0].splitlines():
        p = [x.strip() for x in ln.split("|")]
        if len(p) > 10 and p[1].isdigit():
            try:
                rows.append((p[2], float(p[9])))
            except ValueError:
                pass
    return rows


def plot_and_render(out, LB):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    curves_dir = HERE / "data" / "reaudit_curves"
    curves_dir.mkdir(parents=True, exist_ok=True)
    old = _old_table()
    lines = [MK_B, "", f"## {4 + int(out.get('batch', '1'))}. 第二批第 {out.get('batch', '1')} 批 {len(out.get('families', [])) or 10} 族結果（先.一五五-3 ③，" "`research/reaudit_batch3_factors.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；期間 {out['data_start']}～{out['data_end']}（**2025 起延長尚未做**，見下方待辦）。"
             "做法同 F13：#133 抽樣 236 檔、`research/backtest/` 引擎（下一交易日成交、漲跌停不成交、全成本）、只做多頭；"
             "順向與反向都掃。引擎 48 格 × 組合層 16 格＝每族 768 格挑最好（多重比較懲罰只當參考，不判死）。"
             "樣本內最優化，一定偏樂觀；宇宙是今天名冊抽樣，存活者偏誤未完全排除；3× 超過台股融資上限只當參考。非投資建議。",
             "",
             f"對照：同期加權價格指數（不含息）年化 {out['benchmark_taiex_price_index']['cagr']:+.1%}、MDD {out['benchmark_taiex_price_index']['mdd']:.1%}、"
             f"Sharpe {out['benchmark_taiex_price_index']['sharpe']:.2f}。", "",
             "| 因子族 | 格數完成 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不加止損：順向最好 年化／MDD | 1× 不加止損：反向最好 年化／MDD | 越線格數 | 曲線 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b = f["best_by_calmar"]
        if not b:
            continue
        c = json.loads(cells_path(f["factor"]).read_text(encoding="utf-8"))[b["key"]]
        dates = pd.to_datetime(pd.Series(c["dates"]))
        eq = np.array(c["equity"], float); eq = eq / eq[0]
        curve, _ = S.overlay(eq, LB.load_tw_rf_daily(dates), b["L"], b["stop"])
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(dates, curve, color="#2a6fdb", label="best (Calmar)")
        ax.set_yscale("log"); ax.legend(); ax.set_title(f"{f['factor']} top-N (in-sample optimized, 2015-2024)")
        fig.tight_layout(); fig.savefig(curves_dir / f"batch3_{f['factor']}.png", dpi=110); plt.close(fig)
        rank = 1 + sum(1 for _, s in old if s > b["calmar"])
        fw, rv = f["best_1x_nostop_forward"], f["best_1x_nostop_reverse"]
        wr = "—" if b["win_rate"] is None else f"{b['win_rate']:.0%}"
        lines.append(f"| {f['factor']} | {f['cells_done']}/{f['cells_total']} | {_fmt_params(b)} | {b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | {wr} | {b['trades']} | {b['calmar']:.2f} | 約第 {rank} 名 | "
                     + (f"{fw['cagr']:+.1%}／{fw['mdd']:.1%}" if fw else "—") + " | " + (f"{rv['cagr']:+.1%}／{rv['mdd']:.1%}" if rv else "—")
                     + f" | {f['n_violates']} | [png](data/reaudit_curves/batch3_{f['factor']}.png) |")
    lines += ["", "「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；期間只到 2024 底，跟第 0 節各族期間不同，只當粗排。"
              "格數未滿 48 的族是本輪時間到、下一輪接續，數字會再變。", "", MK_E]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(lines)
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "summarize":
        sys.exit(summarize(sys.argv[2] if len(sys.argv) > 2 else "1"))
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1800))
    sys.exit(0 if run(sys.argv[2:] or BATCH1, dl) else 2)
