"""先.一五五-3 第二批第 11 批：台指期盤別／跳空 4 族（零新外部請求）。

資料：fut_cheap_gate._load_series()／_load_session_pair()（本機 FinMind TaiwanFuturesDaily TX 快取、近月連續、
夜盤 2017-05-16 起；同一日期標籤的夜盤在日盤之前，見 round 63）；只呼叫、不改。
族（原試驗都是 1a 便宜關卡、不含成本）：
- HQ#55 night→day：夜盤 T 自身報酬方向 → 交易日盤 T（開盤進、收盤出）。
- HQ#65 night_gap：日盤 T-1 收盤 → 夜盤 T 開盤跳空方向 → 交易夜盤 T（開盤進、收盤出）。
- HQ#70 day_gap：夜盤 T 收盤 → 日盤 T 開盤跳空方向 → 交易日盤 T（開盤進、收盤出）。
- day→night：日盤 T-1 自身報酬方向 → 交易夜盤 T。
掃：順勢／反向 × 訊號絕對值門檻（只用過去資料的 expanding 百分位 0／50／75／90）× 槓桿（名目÷權益）1／1.5／2／3。
成本（每邊，照實偏保守）：期交稅 0.002%＋手續費 0.002%＋滑價 2 點（開盤撮合）。保證金現金不計利息（偏保守）。
當沖部位不留倉，沒有隔夜跳空風險，但 MDD 照日報酬複利算。樣本內最優化（描述性）；2025 起本機無快取，未延長。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fut_cheap_gate as G  # noqa: E402

D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch11.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B11-BEGIN -->", "<!-- BATCH3-B11-END -->"
TAX, FEE, SLIP_PT = 0.00002, 0.00002, 2.0
LEVS = (1.0, 1.5, 2.0, 3.0)
QS = (0.0, 0.5, 0.75, 0.9)


def stats(r: np.ndarray, dates, trades: int, wins: int):
    c = np.cumprod(1 + r)
    yrs = (dates[-1] - dates[0]).days / 365.25
    cagr = float(c[-1] ** (1 / yrs) - 1) if c[-1] > 0 else -1.0
    mdd = float((c / np.maximum.accumulate(c) - 1).min())
    sd = r.std(ddof=1)
    return {"cagr": cagr, "mdd": mdd, "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "calmar": cagr / abs(mdd) if mdd < 0 else None, "trades": int(trades),
            "win_rate": None if trades == 0 else wins / trades, "violates_survival": mdd < -0.5}


def main():
    s = G._load_series()
    m = G._load_session_pair(s)
    raw = s[["date", "close"]].rename(columns={"close": "raw_close"}) if "close" in s.columns else None
    m["prev_day_close"] = m["adj_close"].shift(1)
    m["prev_day_ret"] = m["day_ret"].shift(1)
    m["gap_night"] = m["night_open"] / m["prev_day_close"] - 1.0
    m["gap_day"] = m["adj_open"] / m["night_close"] - 1.0
    if raw is not None:
        m = m.merge(raw, on="date", how="left")
        lvl = m["raw_close"].shift(1).bfill()
    else:
        lvl = m["adj_close"].shift(1).bfill()
    cost_rt = 2 * (TAX + FEE) + 2 * SLIP_PT / lvl.to_numpy()  # 每筆來回成本（佔名目）
    m = m.dropna(subset=["prev_day_close", "prev_day_ret"]).reset_index(drop=True)
    cost_rt = cost_rt[-len(m):]
    dates = pd.to_datetime(m["date"]).to_numpy()
    dts = pd.DatetimeIndex(dates)
    fams = {
        "HQ#55_night_to_day": ("夜盤 T 報酬方向 → 日盤 T", m["night_ret"], m["day_ret"]),
        "HQ#65_night_gap": ("日收→夜開跳空方向 → 夜盤 T", m["gap_night"], m["night_ret"]),
        "HQ#70_day_gap": ("夜收→日開跳空方向 → 日盤 T", m["gap_day"], m["day_ret"]),
        "day_to_night": ("日盤 T-1 報酬方向 → 夜盤 T", m["prev_day_ret"], m["night_ret"]),
    }
    out_f = []
    for fid, (title, sig, tr) in fams.items():
        sig = sig.to_numpy()
        tr = tr.to_numpy()
        a = pd.Series(np.abs(sig))
        rows = []
        for q in QS:
            thr = a.expanding(min_periods=60).quantile(q).shift(1).to_numpy() if q > 0 else np.zeros(len(a))
            for d_, L in itertools.product((1, -1), LEVS):
                pos = np.where((np.abs(sig) > np.nan_to_num(thr, nan=np.inf)) & (sig != 0), d_ * np.sign(sig), 0.0)
                r = L * (pos * tr - np.abs(pos) * cost_rt)
                n = int((pos != 0).sum())
                w = int(((pos * tr - np.abs(pos) * cost_rt) > 0)[pos != 0].sum())
                rows.append({"direction": "順勢" if d_ == 1 else "反向", "abs_signal_pctile": q, "L": L,
                             **stats(r, dts, n, w), "_r": r})
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None and x["cagr"] > 0]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        nocost = None
        if best:
            pos_best = best  # 同參數不扣成本版本（對照原便宜關卡口徑）
            q, L = pos_best["abs_signal_pctile"], pos_best["L"]
            d_ = 1 if pos_best["direction"] == "順勢" else -1
            thr = a.expanding(min_periods=60).quantile(q).shift(1).to_numpy() if q > 0 else np.zeros(len(a))
            pos = np.where((np.abs(sig) > np.nan_to_num(thr, nan=np.inf)) & (sig != 0), d_ * np.sign(sig), 0.0)
            nocost = stats(L * pos * tr, dts, 0, 0)
        gross_best = max(rows, key=lambda x: x["cagr"])
        clean = lambda x: None if x is None else {k: v for k, v in x.items() if k != "_r"}  # noqa: E731
        f = {"family": fid, "title": title, "start": str(dts[0].date()), "end": str(dts[-1].date()), "n_grid": len(rows),
             "n_violates": sum(x["violates_survival"] for x in rows), "best_by_calmar": clean(best),
             "best_same_params_no_cost": nocost, "best_cagr_any": clean(gross_best),
             "avg_cost_roundtrip_pct": float(np.mean(cost_rt) * 100)}
        print(f"{fid}: " + (f"最好 {best['direction']} 門檻 {best['abs_signal_pctile']} L={best['L']} → {best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}／{best['trades']} 筆；不扣成本 {nocost['cagr']:+.1%}"
                            if best else f"扣成本後沒有正報酬組；年化最高 {gross_best['cagr']:+.1%}／{gross_best['mdd']:.1%}（{gross_best['direction']} 門檻 {gross_best['abs_signal_pctile']} L={gross_best['L']}）"))
        out_f.append(f)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "families": out_f,
           "cost_per_side": {"tax": TAX, "fee": FEE, "slippage_points": SLIP_PT}}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def _p(x):
    return "—" if not x else f"{x['cagr']:+.1%}／{x['mdd']:.1%}"


def render(out):
    lines = [MK_B, "", "## 14. 第二批第 11 批 台指期盤別／跳空 4 族（先.一五五-3 ③，`research/reaudit_batch11_tx_session.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；台指期近月連續（本機快取），夜盤 2017-05-16 起～2024-12-31（2025 起本機無快取、未延長）。"
             "當沖：開盤進、同盤收盤出，不留倉。成本每邊：期交稅 0.002%＋手續費 0.002%＋滑價 2 點。訊號門檻只用過去資料（expanding 百分位）。"
             "原試驗（1a 便宜關卡）不扣成本；本表同時列不扣成本版。樣本內最優化、多重比較只當參考；非投資建議。", "",
             "| 族 | 期間 | 最好的一組（Calmar，扣成本後年化>0） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 同參數不扣成本 | 平均來回成本 | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b = f["best_by_calmar"]
        if not b:
            g = f["best_cagr_any"]
            lines.append(f"| {f['family']}（{f['title']}） | {f['start']}～{f['end']} | 扣成本後沒有正報酬組（年化最高 {g['direction']}／門檻 {g['abs_signal_pctile']}／{g['L']:g}× {_p(g)}） | | | | | | | {f['avg_cost_roundtrip_pct']:.3f}% | {f['n_violates']} |")
            continue
        wr = "—" if b["win_rate"] is None else f"{b['win_rate']:.0%}"
        lines.append(f"| {f['family']}（{f['title']}） | {f['start']}～{f['end']} | {b['direction']}，|訊號|>過去 {b['abs_signal_pctile']:.0%} 分位，{b['L']:g}× | "
                     f"{b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | {wr} | {b['trades']} | {_p(f['best_same_params_no_cost'])} | {f['avg_cost_roundtrip_pct']:.3f}% | {f['n_violates']} |")
    lines += ["", "讀法：這幾族都是每天進出的當沖，成本佔比大；勝率＝扣成本後當筆賺錢比例。槓桿＝名目÷權益（大台一口保證金約名目 7～10%，3× 仍在保證金內）。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
