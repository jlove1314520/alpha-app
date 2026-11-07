"""先.一五五-3 墓園重審第二批 第 6 批：組合建構類（紙上優化軌，DevQueue 20261108-030102）。

零請求。樣本＝#133 抽樣 236 檔（reaudit_ssu_loaded.pkl，延長價格照 reaudit_ext2025_engine.load_extended() 只呼叫），
期間 2015-01-02～延長價格終點（約 2026-09-24）。三族：
  - equal_weight_rebalance（HQ#29 等權再平衡）
  - inverse_vol（HQ#58 反波動加權）
  - min_variance（HQ#59 最小變異數，只做多、單檔上限 10%；用「收縮共變異數＋閉式解→負權重歸零→重新正規化→上限截斷」近似，
    不是二次規劃精確解，照實揭露）
每族掃：再平衡間隔 × 回看窗 × 大盤閘門（TAIEX 週線 Stage2 閘門＝reaudit 既有 gate，關閉時持現金收無風險利率）
× 槓桿 1/1.5/2/3（融資成本年 6.5%，同 batch2 overlay）× 組合止損 無/10%/15%/20%（同 overlay，冷卻 21 日）。
紀律：權重只用 t 收盤以前的資料算，t+1 起生效；成本＝每次再平衡的換手 × （手續費 0.1425% 不打折＋滑價 5bps；賣方加證交稅 0.3%）；
缺價（2025 起沒有延長價格或下市）那天報酬記 0、下次再平衡剔除（照實揭露，非下市清算模型）。
不改核心檔、不寫試驗帳本；結果寫 REAUDIT_OPTIMIZED.md 第 10 節（BATCH3-B6 標記間）、明細 data/reaudit_batch3_batch6.json。
"""
from __future__ import annotations

import mem_guard  # noqa: F401

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_ext2025_engine as E  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402  overlay()（槓桿＋組合止損）
from validation.costs import COMMISSION_RATE, DEFAULT_SLIPPAGE_BPS, SECURITIES_TX_TAX_NORMAL  # noqa: E402

D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch6.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
START = "2015-01-02"
BUY_C = COMMISSION_RATE + DEFAULT_SLIPPAGE_BPS / 1e4
SELL_C = BUY_C + SECURITIES_TX_TAX_NORMAL
CAP = 0.10


def load():
    ext, mk, miss, jumps, end = E.load_extended()
    px = pd.DataFrame({sid: pd.Series(d["adj_close"].astype(float).to_numpy(), index=pd.to_datetime(d["date"].astype(str).str[:10]))
                       for sid, d in ext.items()}).sort_index()
    px = px[px.index >= pd.Timestamp("2014-01-01")]
    from strategies.weinstein_stage2 import prepare_market_data
    m = prepare_market_data(mk)
    gate = pd.Series(m["gate"].astype(bool).to_numpy(), index=pd.to_datetime(m["date"])).reindex(px.index).ffill().fillna(False)
    rfm = json.loads((HERE.parent / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rs = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in rfm}).sort_index()
    per = px.index.to_period("M")
    rf = pd.Series(per.map(lambda p: rs[rs.index <= p].iloc[-1] if (rs.index <= p).any() else rs.iloc[0]),
                   index=px.index).astype(float) / 100 / 252
    return px, gate, rf, end, miss


def weights(kind, hist):
    """hist：回看窗日報酬（列＝日、欄＝當下可交易股）。回傳權重 Series。"""
    n = hist.shape[1]
    if kind == "equal_weight_rebalance":
        return pd.Series(1.0 / n, index=hist.columns)
    sd = hist.std().replace(0, np.nan)
    if kind == "inverse_vol":
        w = (1 / sd).fillna(0)
        return w / w.sum()
    cov = hist.cov().to_numpy()
    cov = 0.5 * cov + 0.5 * np.diag(np.diag(cov))  # 收縮到對角
    try:
        w = np.linalg.solve(cov + 1e-10 * np.eye(n), np.ones(n))
    except np.linalg.LinAlgError:
        w = 1 / np.diag(cov)
    w = np.clip(w, 0, None)
    if w.sum() <= 0:
        w = np.ones(n)
    w = w / w.sum()
    for _ in range(20):  # 上限截斷，多出的按比例分給未觸頂者
        over = w > CAP
        if not over.any():
            break
        ex = (w[over] - CAP).sum()
        w[over] = CAP
        free = ~over & (w > 0)
        if not free.any():
            break
        w[free] += ex * w[free] / w[free].sum()
    return pd.Series(w, index=hist.columns)


def sim(px, gate, rf, kind, rb, look, use_gate):
    # 逐檔在自己有價日上算（pandas 3 的 pct_change 不補值，日期聯集裡的個股零星缺日會丟掉跨缺口報酬；DevQueue 20261108-060101 修）
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    idx = px.index
    i0 = int(np.searchsorted(idx, pd.Timestamp(START)))
    eq = np.ones(len(idx) - i0)
    w = pd.Series(dtype=float)
    v, n_reb, turn_sum = 1.0, 0, 0.0
    for k, i in enumerate(range(i0, len(idx))):
        if k > 0:
            r = ret.iloc[i]
            if len(w):
                pr = float((w * r.reindex(w.index).fillna(0.0)).sum())
                v *= 1 + pr
                # 權重隨價格漂移
                g = w * (1 + r.reindex(w.index).fillna(0.0))
                w = g / g.sum() if g.sum() > 0 else g
            else:
                v *= 1 + float(rf.iloc[i])
        if k % rb == 0:  # t 收盤算權重，t+1 起生效
            on = (not use_gate) or bool(gate.iloc[i])
            if on:
                win = ret.iloc[max(0, i - look + 1): i + 1]
                ok = px.iloc[i].notna() & (win.notna().sum() >= int(look * 0.8))
                hist = win.loc[:, ok].fillna(0.0)
                nw = weights(kind, hist) if hist.shape[1] >= 5 else pd.Series(dtype=float)
            else:
                nw = pd.Series(dtype=float)
            allk = w.index.union(nw.index)
            dw = nw.reindex(allk).fillna(0) - w.reindex(allk).fillna(0)
            cost = float(dw.clip(lower=0).sum() * BUY_C + (-dw).clip(lower=0).sum() * SELL_C)
            v *= 1 - cost
            turn_sum += float(dw.abs().sum()) / 2
            n_reb += 1
            w = nw
        eq[k] = v
    return idx[i0:], eq, n_reb, turn_sum


def st(dates, c):
    yrs = (dates[-1] - dates[0]).days / 365.25
    r = np.diff(c) / c[:-1]
    sd = r.std()
    return {"cagr": float(c[-1] ** (1 / yrs) - 1) if c[-1] > 0 else -1.0,
            "mdd": float((c / np.maximum.accumulate(c) - 1).min()),
            "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0}


def seg(dates, c, a, b):
    m = (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))
    if m.sum() < 30:
        return None
    x = c[m] / c[m][0]
    return st(dates[m], x)


FAMS = [("equal_weight_rebalance", "HQ#29 等權再平衡"), ("inverse_vol", "HQ#58 反波動加權"),
        ("min_variance", "HQ#59 最小變異數（近似解）")]
RBS = (5, 21, 63)
LOOKS = (60, 120, 252)


def main():
    t0 = time.time()
    px, gate, rf, end, miss = load()
    print(f"樣本 {px.shape[1]} 檔、{px.index[0].date()}～{px.index[-1].date()}，2025 起缺價 {len(miss)} 檔")
    out = {"meta": {"cycle": "20261108-030102", "start": START, "end": str(px.index[-1].date()), "n_stocks": int(px.shape[1]),
                    "missing_2025": len(miss), "cost": {"buy": BUY_C, "sell": SELL_C}}, "families": []}
    for fid, title in FAMS:
        rows = []
        looks = (60,) if fid == "equal_weight_rebalance" else LOOKS
        for rb, look, g in itertools.product(RBS, looks, (False, True)):
            dates, eq, n_reb, turn = sim(px, gate, rf, fid, rb, look, g)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, n_stop = S.overlay(eq, rfa, L, stop)
                s = st(dates, c)
                rows.append({"rb": rb, "look": look, "gate": g, "L": L, "stop": stop, **s, "n_rebalance": n_reb,
                             "avg_turnover": turn / max(n_reb, 1), "n_stop": n_stop,
                             "seg_2015_2024": seg(dates, c, "2015-01-01", "2024-12-31"),
                             "seg_2025": seg(dates, c, "2025-01-01", "2026-12-31"),
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
            print(f"{fid} rb={rb} look={look} gate={g} 完成（累計 {time.time()-t0:.0f}s）", flush=True)
        ok = [r for r in rows if r["mdd"] > -0.5]
        best = max(ok or rows, key=lambda r: r["calmar"])
        best_l2 = max([r for r in ok if r["L"] <= 2.0] or rows, key=lambda r: r["calmar"])
        base = next(r for r in rows if r["L"] == 1.0 and r["stop"] is None and not r["gate"])
        out["families"].append({"family": fid, "title": title, "n_cells": len(rows), "best": best, "best_L2": best_l2,
                                "baseline_1x_nogate": base,
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)
    print(f"完成 {time.time()-t0:.0f}s")


def _p(x):
    return "—" if x is None else f"{x*100:+.1f}%"


def render(out):
    m = out["meta"]
    lines = ["<!-- BATCH3-B6-BEGIN -->", "", "## 10. 第二批 第 6 批：組合建構類（DevQueue 20261108-030102）", "",
             f"樣本＝#133 抽樣 {m['n_stocks']} 檔（延長價格到 {m['end']}；2025 起缺價 {m['missing_2025']} 檔，缺價日報酬記 0、下次再平衡剔除），"
             f"期間 {m['start']}～{m['end']}，參數用全期挑（含 2025 起，2025 起分段不是樣本外）。成本：買 {m['cost']['buy']*100:.4f}%、"
             f"賣 {m['cost']['sell']*100:.4f}%（手續費不打折＋滑價 5bps＋證交稅 0.3%）。權重 t 收盤算、t+1 生效；槓桿融資年 6.5%。",
             "最小變異數是近似解（收縮共變異數閉式解→負權重歸零→單檔上限 10%），不是二次規劃精確解。", "",
             "| 族 | 最佳組（Calmar，MDD 在 50% 內） | 年化 | MDD | Sharpe | 2015～2024 | 2025 起 | ≤2× 最佳 | 1× 不擇時基準 | 越過天條一的格數 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b, b2, base = f["best"], f["best_L2"], f["baseline_1x_nogate"]
        pr = f"再平衡 {b['rb']} 日、回看 {b['look']}、{'大盤閘門' if b['gate'] else '不擇時'}、{b['L']}×、止損 {b['stop'] or '無'}"
        s1, s2 = b["seg_2015_2024"] or {}, b["seg_2025"] or {}
        lines.append(f"| {f['title']} | {pr} | {_p(b['cagr'])} | {_p(b['mdd'])} | {b['sharpe']:.2f} | "
                     f"{_p(s1.get('cagr'))}／{_p(s1.get('mdd'))} | {_p(s2.get('cagr'))}／{_p(s2.get('mdd'))} | "
                     f"{b2['L']}× {_p(b2['cagr'])}／{_p(b2['mdd'])} | {_p(base['cagr'])}／{_p(base['mdd'])} | "
                     f"{f['violates_survival_cells']}／{f['n_cells']} |")
    lines += ["", "明細 `research/data/reaudit_batch3_batch6.json`。3× 超過融資上限只當參考。", "", "<!-- BATCH3-B6-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if "<!-- BATCH3-B6-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B6-BEGIN -->")
        z = txt.index("<!-- BATCH3-B6-END -->") + len("<!-- BATCH3-B6-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip() + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates():
    """〔自行裁量〕Calmar 約 0.70（高於第 5 批進榜的 exit_ma 0.56、接近第 1 名 f_52w_high_prox 0.69）的族寫進候選欄，
    rank_in_table 暫記 8（綜合分數跟第 0 節表同一尺度要另算，先放中段）；id 前綴 B6W-，重跑只換自己的條目。"""
    from datetime import datetime
    out = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B6W-")]
    new = []
    for f in out["families"]:
        b = f["best"]
        if b["calmar"] < 0.6:
            continue
        note = ["樣本內最優化（偏樂觀，參數用全期含 2025 起挑）", "#133 抽樣 236 檔組合建構，2025 起缺價 45 檔報酬記 0"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B6W-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 6 批（組合建構）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": 8,
                    "params": {k: b[k] for k in ("rb", "look", "gate", "L", "stop")},
                    "backtest_period": f"{out['meta']['start']}～{out['meta']['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in (b["seg_2015_2024"] or {}).items()},
                    "from_2025_same_params": {k: round(v, 4) for k, v in (b["seg_2025"] or {}).items()} or None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None, "trades": b["n_rebalance"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候選欄新增 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    if sys.argv[1:] == ["candidates"]:
        write_candidates()
    else:
        main()
