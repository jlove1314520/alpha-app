# -*- coding: utf-8 -*-
"""先.一五五-3 第二批第 4 批：regime → 0050 曝險類 10 族的樣本內最優化（描述性，紙上優化軌，非判定）。

零外部請求：訊號全部讀本機既有對齊檔 `research/data/*_aligned.csv`（當初各假說建的，已截到 2024 底），
0050 含息報酬／台灣無風險利率沿用 `reaudit_optimized_batch1`（#418／#421 的 load_all、load_tw_rf_daily）。

做法（每族同一套掃格）：
- 訊號值在觀察日台股收盤後才算看得到，最快隔日收盤調倉、吃觀察日後第 2 個交易日起的報酬；月資料（景氣對策、失業率）用對齊檔的 entry_date。
- 轉換：水位／21 日變化／63 日變化（月資料：水位／1 期變化／3 期變化）；門檻＝到當天為止的 expanding 百分位
  （至少 252 個日資料點或 24 個月資料點，暖機期不擇時、滿曝險），不偷看未來。
- 方向：百分位高＝避險，或百分位低＝避險；避險門檻 70／80／90 百分位；避險時曝險 0 或 0.5。
- 槓桿 1×／1.5×／2×／3×（借款成本＝台灣無風險利率＋年 1% 槓桿費）、組合止損 不設／10%／20%／30%（觸發後 21 日冷卻）。
- 成本：曝險每變動 1 單位 × 槓桿 收 滑價 0.1％＋手續費 0.0855％，減碼另收證交稅（0050 ETF 0.1%）。
- fut 族（#18 等多時間框架趨勢）：0050 自己的 n 日動能投票，達 m 票才滿曝險。
- 評估期間＝訊號實際有值的那段（各族不同）＋0050 買進持有同期對照。
多重比較／DSR 只當參考，不判死；MDD>50% 標 VIOLATES_SURVIVAL。樣本內最優化一定偏樂觀。非投資建議。
"""
from __future__ import annotations

import itertools
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
_ARGV = sys.argv[1:]
sys.argv = [sys.argv[0]]
import reaudit_optimized_batch1 as B1  # noqa: E402  （模組載入時讀 0050／rf，截 2024-12-31）

D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch4.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B4-BEGIN -->", "<!-- BATCH3-B4-END -->"
DATES = B1.DATES
N = B1.N
R0 = B1.R["0050"]
RC = B1.R["CASH"]
RF = B1.RF_TW
COST = B1.SLIP + B1.BROKER
SELL_TAX = 0.001  # 0050 ETF 證交稅
LEVS, STOPS, COOLDOWN = B1.LEVS, B1.STOPS, B1.COOLDOWN


def prog(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def daily_series(fn, dcol, vcol, monthly=False):
    df = pd.read_csv(D / fn)
    s = pd.Series(df[vcol].astype(float).to_numpy(), index=pd.to_datetime(df[dcol])).sort_index()
    s = s[~s.index.duplicated(keep="last")].dropna()
    return s, monthly


FAMS = [
    ("HQ#76", "#76 VIX 期限結構（VIX9D/VIX）", "vix_term_structure_aligned.csv", "date", "vix_term_ratio", False),
    ("fx_twd", "#32 美元兌台幣變化", "fx_twd_aligned.csv", "date", "fx_change_n", False),
    ("option_pcr_overlay", "#31 台指選擇權 PCR 擇時", "option_pcr_aligned.csv", "signal_date", "pcr", False),
    ("copper_gold_ratio", "#34 銅金比", "copper_gold_ratio_aligned.csv", "date", "copper_gold_ratio", False),
    ("fred_yield_curve", "#33 美債 10Y-2Y 利差", "fred_yield_curve_aligned.csv", "date", "spread_level", False),
    ("hy_etf_ratio", "#78 HYG/IEF 信用比值", "hy_etf_ratio_aligned.csv", "date", "hyg_ief_ratio", False),
    ("spillover_overnight", "#19 美股隔夜報酬外溢", "spillover_overnight_aligned.csv", "us_signal_date", "us_ret", False),
    ("cbi_signal", "#81 景氣對策信號分數", "cbi_signal_aligned.csv", "entry_date", "score", True),
    ("dgbas_unemployment", "#80 台灣失業率 YoY", "dgbas_unemployment_aligned.csv", "entry_date", "score", True),
]


def to_daily(s: pd.Series) -> tuple[np.ndarray, int]:
    """把觀察日序列對到交易日。報酬是「前一日收盤→當日收盤」，部位要在前一日收盤就定好；
    觀察日 d 的值多半在台股 d 收盤之後才知道（美股收盤＝台北清晨、央行匯率 16:00、期交所盤後），
    所以最快 d 之後第 1 個交易日收盤調倉、吃第 2 個交易日的報酬（第一版只 shift 1，美股隔夜外溢會偷吃開盤跳空，已修）。"""
    idx = np.searchsorted(DATES.to_numpy(), s.index.to_numpy(), side="right") + 1  # d 之後第 2 個交易日
    v = np.full(N, np.nan)
    for j, i in enumerate(idx):
        if i < N:
            v[i] = s.iloc[j]
    v = pd.Series(v).ffill().to_numpy()
    first = int(np.argmax(~np.isnan(v))) if (~np.isnan(v)).any() else N
    return v, first


def transforms(s: pd.Series, monthly: bool):
    lags = (("level", 0), ("chg1", 1), ("chg3", 3)) if monthly else (("level", 0), ("chg21", 21), ("chg63", 63))
    warm = 24 if monthly else 252
    for name, lag in lags:
        x = s if lag == 0 else s - s.shift(lag)
        x = x.dropna()
        # expanding 百分位（只用到當天為止的觀察值）
        pct = x.expanding(min_periods=warm).apply(lambda a: (a[:-1] < a[-1]).mean() if len(a) > 1 else np.nan, raw=True)
        yield name, pct


def run_sim(e_sig: np.ndarray, L: float, stop, i0: int):
    lev = L * R0 - (L - 1.0) * RF - (B1.FEE_LEV / 252.0 if L > 1 else 0.0)
    out = np.zeros(N)
    eq, peak, cool, prev = 1.0, 1.0, 0, 0.0
    trades, in_pos, entry = [], False, 1.0
    for i in range(i0, N):
        e = e_sig[i]
        if cool > 0:
            cool -= 1
            e = 0.0
        de = e - prev
        cost = abs(de) * L * COST + (abs(de) * L * SELL_TAX if de < 0 else 0.0)
        ret = 0.0 if eq <= 0 else e * lev[i] + (1 - e) * RC[i] - cost
        now_in = e > 0
        if now_in and not in_pos:
            entry = eq
        eq = max(eq * (1 + ret), 0.0)
        if in_pos and (not now_in or e < prev):
            trades.append((entry, eq))
            if now_in:
                entry = eq
        in_pos = now_in
        out[i] = ret
        prev = e
        peak = max(peak, eq) if in_pos else eq
        if stop is not None and in_pos and eq < peak * (1 - stop):
            cool, peak = COOLDOWN, eq
    if in_pos:
        trades.append((entry, eq))
    return out[i0:], trades


def stats(r, trades, i0):
    curve = np.cumprod(1 + r)
    yrs = (DATES.iloc[-1] - DATES.iloc[i0]).days / 365.25
    cagr = curve[-1] ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
    mdd = float((curve / np.maximum.accumulate(curve) - 1).min())
    sd = r.std(ddof=1)
    return {"cagr": float(cagr), "mdd": mdd, "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "trades": len(trades), "win_rate": float(np.mean([b > a for a, b in trades])) if trades else None,
            "calmar": float(cagr / abs(mdd)) if mdd < 0 else None, "violates_survival": bool(mdd < -0.50)}


def gen_signal_family(fn, dcol, vcol, monthly):
    """回傳 (格子清單, i0)；i0＝水位百分位暖機完成、第一天真的在擇時的交易日。"""
    s, _ = daily_series(fn, dcol, vcol, monthly)
    i0, res = None, []
    for tname, pct in transforms(s, monthly):
        p, first = to_daily(pct)
        i0 = first if i0 is None else min(i0, first)
        for direction, q, k in itertools.product((1, -1), (0.7, 0.8, 0.9), (0.0, 0.5)):
            off = (p > q) if direction == 1 else (p < 1 - q)
            e = np.where(np.isnan(p), 1.0, np.where(off, k, 1.0))
            res.append(({"transform": tname, "riskoff_when": "高" if direction == 1 else "低", "pct_threshold": q,
                         "riskoff_exposure": k}, e))
    return res, i0


def fam_fut():
    px = np.cumprod(1 + R0)
    for tfs, m, k in itertools.product(((5, 20, 60), (10, 20, 60), (20, 60, 120), (20, 60, 250)), (2, 3), (0.0, 0.5)):
        votes = sum(np.where(np.arange(N) >= n, (px > np.roll(px, n)).astype(float), 1.0) for n in tfs)
        e = B1.shift1(np.where(votes >= m, 1.0, k))
        yield {"lookbacks": "/".join(map(str, tfs)), "votes_needed": m, "riskoff_exposure": k}, e


def _fmt(b):
    keys = [k for k in b if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")]
    return "，".join(f"{k}={'不設' if b[k] is None else b[k]}" for k in keys)


def main():
    prog("開始")
    fams = []
    specs = [("fut", "#18 等 0050 多時間框架動能投票（fut 家族改做現股 0050）", None)] + [(f[0], f[1], f[2:]) for f in FAMS]
    for fid, title, spec in specs:
        rows = []
        try:
            if spec is None:
                gen, i0 = list(fam_fut()), 250
            else:
                fn, dcol, vcol, monthly = spec
                gen, i0 = gen_signal_family(fn, dcol, vcol, monthly)
            for (params, e), L, st in itertools.product(gen, LEVS, STOPS):
                r, tr = run_sim(e, L, st, i0)
                rows.append({**params, "L": L, "stop": st, **stats(r, tr, i0), "_r": r})
        except Exception as ex:  # noqa: BLE001 —— 單一族失敗不影響其他族
            print(f"::warning::{fid} 失敗：{ex!r}")
            fams.append({"family": fid, "title": title, "error": repr(ex)})
            continue
        bh_r = R0[i0:]
        bh = stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], i0)
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        top = max(ok, key=lambda x: x["cagr"]) if ok else None
        base = [x for x in ok if x["L"] == 1.0 and x["stop"] is None]
        b1 = max(base, key=lambda x: x["calmar"]) if base else None
        png = plot(fid, title, best["_r"], bh_r, i0) if best else None
        bhl = None
        if best:
            rr, tt = run_sim(np.ones(N), best["L"], None, i0)
            bhl = stats(rr, tt, i0)
        clean = lambda x: None if x is None else {k: v for k, v in x.items() if k != "_r"}  # noqa: E731
        fams.append({"family": fid, "title": title, "start": str(DATES.iloc[i0].date()), "end": str(DATES.iloc[-1].date()),
                     "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
                     "buy_hold_0050_same_period": bh, "buy_hold_same_leverage_no_timing": bhl, "best_by_calmar": clean(best), "best_by_cagr_within_mdd50": clean(top),
                     "best_1x_nostop": clean(b1), "curve_png": png})
        prog(f"{fid} {len(rows)} 格；最好 {_fmt(clean(best))} → {best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}；同期 0050 {bh['cagr']:+.1%}／{bh['mdd']:.1%}")
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(DATES.iloc[-1].date()),
           "families": fams, "notes": "樣本內最優化（描述性）；訊號 shift 1、expanding 百分位；0050 含息；3× 超過台股融資上限只當參考（紙上要改槓桿 ETF／期貨）；2025 起延長尚未做（對齊檔只到 2024 底）。"}
    render(out)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_candidates(out)
    prog(f"寫入 {OUT_JSON}")


def plot(fid, title, r, bh, i0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    dt = DATES.iloc[i0:]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(dt, np.cumprod(1 + r), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(dt, np.cumprod(1 + bh), color="#9aa0a6", lw=1.2, label="0050 買進持有（含息）")
    ax.set_yscale("log")
    ax.set_title(f"{fid} {title}（樣本內最優化，至 2024-12，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    p = D / "reaudit_curves" / f"batch3_b4_{fid.replace('#', '')}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p)
    plt.close(fig)
    return p.relative_to(HERE).as_posix()


def _old_rank(calmar):
    sys.argv = [sys.argv[0]]
    import reaudit_batch3_factors as BF
    old = BF._old_table()
    return 1 + sum(1 for _, sc in old if sc > calmar)


def render(out):
    lines = [MK_B, "", "## 8. 第二批第 4 批 regime→0050 類 10 族結果（先.一五五-3 ③，`research/reaudit_batch4_regime.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；期間＝各族訊號實際有值起～{out['data_end']}（對齊檔只到 2024 底，**2025 起延長尚未做**）。"
             "做法：訊號觀察日後第 2 個交易日起生效（隔日收盤調倉）、expanding 百分位門檻（不偷看未來）；轉換（水位／變化）×方向×門檻 70/80/90×避險曝險 0/0.5 × 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%。"
             "0050 含息、成本照實（滑價＋手續費＋賣出證交稅）、槓桿借款＝台灣無風險利率＋年 1%。樣本內最優化一定偏樂觀；多重比較只當參考。3× 超過台股融資上限只當參考。非投資建議。", "",
             "| 族 | 期間起 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 1× 不設止損最好 年化／MDD | 同期 0050 年化／MDD | 同槓桿不擇時 年化／MDD | 越線格數 | 曲線 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        if "error" in f:
            lines.append(f"| {f['family']} | — | 失敗：{f['error']} | | | | | | | | | | | | |")
            continue
        b, b1, bh = f["best_by_calmar"], f["best_1x_nostop"], f["buy_hold_0050_same_period"]
        wr = "—" if b["win_rate"] is None else f"{b['win_rate']:.0%}"
        f["rank"] = _old_rank(b["calmar"])
        lines.append(f"| {f['family']}（{f['title']}） | {f['start']} | {_fmt(b)} | {b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | {wr} | {b['trades']} | {b['calmar']:.2f} | 約第 {f['rank']} 名 | "
                     + (f"{b1['cagr']:+.1%}／{b1['mdd']:.1%}" if b1 else "—") + f" | {bh['cagr']:+.1%}／{bh['mdd']:.1%} | {f['buy_hold_same_leverage_no_timing']['cagr']:+.1%}／{f['buy_hold_same_leverage_no_timing']['mdd']:.1%} | {f['n_violates']} | [png]({f['curve_png']}) |")
    lines += ["", "「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；各族期間不同（2003～2016 起不等），只當粗排。"
              "交易次數＝減碼／出場次數；勝率＝每段持有期間結束時淨值高於進場時的比例。",
              "**讀法提醒**：2016～2024 是大多頭，「同槓桿不擇時」本身年化就很高、但 MDD 多半越過 50%；這批最好的組合主要價值是把回撤壓回 50% 內，"
              "年化贏過同槓桿不擇時的只有少數族（看最後兩欄）。fut 族（多時間框架動能）改在 0050 現股上做，期間含 2008。"
              "第一版訊號只 shift 1 天，美股隔夜外溢族因此偷吃到台股開盤跳空（年化 +91.9%），已改成觀察日後第 2 個交易日生效並重跑。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates(out):
    """前 10 名寫進 paper_opt_candidates.json（id 前綴 B4R-，重跑時只換掉自己的條目，不動因子族候選）。"""
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B4R-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or f.get("rank", 99) > 10:
            continue
        note = ["樣本內最優化（偏樂觀）", "regime 訊號 → 0050 曝險", "2025 起尚未延長重算（對齊檔只到 2024 底）"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B4R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 4 批（regime→0050）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～{f['end']}",
                    "backtest_2015_2024": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                           "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "from_2025_same_params": None, "full_period_same_params": None, "violates_survival_extended": False,
                    "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    prog(f"候選欄新增 regime {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    main()
