# -*- coding: utf-8 -*-
"""先.一五五-3 第二批第 5 批：只用 0050 自己價格的擇時規則 10 族（描述性，紙上優化軌，非判定）。

零外部請求：0050 含息報酬／台灣無風險利率沿用 `reaudit_optimized_batch1`（REAUDIT_END 延長到 2025 起，
走 `reaudit_ext2025.extend_0050` 本機快取），模擬／成本／統計沿用第 4 批 `reaudit_batch4_regime.run_sim`（只呼叫）。

10 族（TRIALS_LEDGER 原試驗多為台指期或 TAIEX 層級，這裡一律改在 0050 現股曝險上做）：
  exit_trailing（exit_rule_lab E-c 移動停利）、exit_ma（E-d MA200 regime）、vol_targeting（#15）、
  volmanaged_leverage（#436/#439 變異數管理）、donchian_turtle（海龜／唐奇安）、keltner（收盤版 ATR 通道）、
  cta_momentum（12 月 CTA 動能）、cta_multi_tf_voltarget（多時間框架投票×波動目標）、
  drawdown_breaker（回撤斷路器，overlay 候選 5）、turn_of_month（#25 月轉效應）。
時點：訊號只用到 t 日收盤（含）為止的價格，t+1 日起生效（B1.shift1）；波動估計用 rolling／expanding，不偷看未來。
每族 × 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%（同第 4 批）。全期＝0050 起＋暖機 250 日～延長終點；另列 2015～2024 與 2025 起分段。
樣本內最優化一定偏樂觀；多重比較只當參考。MDD>50% 標 VIOLATES_SURVIVAL。3× 超過台股融資上限只當參考。非投資建議。
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("REAUDIT_END", "2026-12-31")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.argv = [sys.argv[0]]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import reaudit_batch4_regime as B4  # noqa: E402  （會帶入延長後的 B1）

B1 = B4.B1
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch5.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B5-BEGIN -->", "<!-- BATCH3-B5-END -->"
DATES, N, R0 = B4.DATES, B4.N, B4.R0
PX = np.cumprod(1 + R0)
I0 = 250
S = pd.Series(PX)
RET = pd.Series(R0)
IDX = np.arange(N)
SHIFT = B1.shift1
KS = (0.0, 0.5)


def _hold(on_entry: np.ndarray, on_exit: np.ndarray, k: float) -> np.ndarray:
    """進場條件成立就滿曝險，出場條件成立就降到 k，兩者都不成立維持前一天狀態（遲滯）。"""
    e = np.empty(N)
    st = 1.0
    for i in range(N):
        if on_entry[i]:
            st = 1.0
        elif on_exit[i]:
            st = k
        e[i] = st
    return e


def fam_exit_trailing():
    for x, n, k in itertools.product((0.05, 0.08, 0.10, 0.15, 0.20), (60, 120, 250), KS):
        dd = (S / S.rolling(n, min_periods=1).max() - 1).to_numpy()
        reent = (S >= S.rolling(20, min_periods=1).max()).to_numpy()  # 創 20 日新高才回場
        e = _hold(reent, dd < -x, k)
        yield {"trail_pct": x, "peak_window": n, "reentry": "20日新高", "riskoff_exposure": k}, SHIFT(e)


def fam_exit_ma():
    for n, band, k in itertools.product((50, 100, 150, 200, 250), (0.0, 0.01, 0.03), KS):
        ma = S.rolling(n, min_periods=n).mean().to_numpy()
        up, dn = PX > ma * (1 + band), PX < ma * (1 - band)
        e = _hold(up | np.isnan(ma), dn, k)
        yield {"ma_days": n, "band": band, "riskoff_exposure": k}, SHIFT(e)


def _rv(n):
    return (RET.rolling(n, min_periods=n).std() * np.sqrt(252)).to_numpy()


def fam_vol_targeting():
    for tgt, n in itertools.product((0.10, 0.15, 0.20, 0.25), (20, 60, 120)):
        rv = _rv(n)
        e = np.where(np.isnan(rv), 1.0, np.minimum(1.0, tgt / np.maximum(rv, 1e-6)))
        yield {"target_vol": tgt, "vol_window": n}, SHIFT(e)


def fam_volmanaged():
    for n, c in itertools.product((21, 63), (0.5, 0.75, 1.0, 1.5)):
        var = RET.rolling(n, min_periods=n).var()
        med = var.expanding(min_periods=252).median()  # 只用到當天為止的變異數分佈
        e = np.where(med.isna().to_numpy(), 1.0, np.minimum(1.0, c * (med / var).to_numpy()))
        yield {"var_window": n, "scale_c": c}, SHIFT(e)


def fam_donchian():
    for (n, m), k in itertools.product(((20, 10), (55, 20), (100, 50), (250, 100), (20, 55), (60, 20)), KS):
        hi = S.shift(1).rolling(n, min_periods=n).max().to_numpy()
        lo = S.shift(1).rolling(m, min_periods=m).min().to_numpy()
        e = _hold(np.isnan(hi) | (PX > hi), PX < lo, k)
        yield {"entry_high_days": n, "exit_low_days": m, "riskoff_exposure": k}, SHIFT(e)


def fam_keltner():
    atr = (RET.abs() * S.shift(1)).rolling(20, min_periods=20).mean()  # 只有收盤價，用 |日報酬|×前收 近似 ATR
    for n, kk, k in itertools.product((20, 50, 100), (0.0, 1.0, 2.0), KS):
        ema = S.ewm(span=n, adjust=False).mean()
        up = (S > ema + kk * atr).to_numpy()
        dn = (S < ema).to_numpy()
        e = _hold(up | (IDX < n), dn, k)
        yield {"ema_days": n, "atr_mult": kk, "riskoff_exposure": k}, SHIFT(e)


def fam_cta_momentum():
    for n, skip, k in itertools.product((63, 126, 189, 252), (0, 21), KS):
        past = S.shift(n).to_numpy()
        near = S.shift(skip).to_numpy() if skip else PX
        e = np.where(np.isnan(past), 1.0, np.where(near > past, 1.0, k))
        yield {"lookback": n, "skip_recent": skip, "riskoff_exposure": k}, SHIFT(e)


def fam_cta_multi_tf_voltarget():
    for tfs, m, tgt in itertools.product(((20, 60, 250), (10, 60, 120), (20, 120, 250)), (2, 3), (0.15, 0.20, 1.0)):
        votes = sum(np.where(IDX >= n, (PX > np.roll(PX, n)).astype(float), 1.0) for n in tfs)
        rv = _rv(60)
        scale = np.where(np.isnan(rv), 1.0, np.minimum(1.0, tgt / np.maximum(rv, 1e-6)))
        e = np.where(votes >= m, scale, 0.0)
        yield {"lookbacks": "/".join(map(str, tfs)), "votes_needed": m, "target_vol": "不設" if tgt >= 1 else tgt}, SHIFT(e)


def fam_drawdown_breaker():
    """0050 自己距歷史高點的回撤 ≥x → 降到 k；回撤收斂到 y 以內才解除（解除條件＝價格回升，數學上可滿足，非吸收態）。"""
    dd = (S / S.cummax() - 1).to_numpy()
    for x, yr, k in itertools.product((0.10, 0.15, 0.20, 0.25, 0.30), (0.25, 0.5, 0.75), KS):
        y = x * yr
        e = _hold(dd > -y, dd <= -x, k)
        yield {"trigger_dd": x, "release_dd": round(y, 4), "riskoff_exposure": k}, SHIFT(e)


def fam_turn_of_month():
    per = DATES.dt.to_period("M")
    pos = per.groupby(per).cumcount().to_numpy()  # 當月第幾個交易日（0 起）
    rem = per.groupby(per).cumcount(ascending=False).to_numpy()  # 距月底還有幾個交易日（0＝最後一天）
    for before, after, k in itertools.product((1, 2, 3), (2, 3, 4, 5), KS):
        # 報酬 i 的部位在 i-1 收盤決定：日 i 落在「月底前 before 日～下月第 after 日」窗口內就持有（日曆事先已知，不偷看）
        win = (rem < before) | (pos < after)
        yield {"days_before_month_end": before, "days_after_month_start": after, "out_exposure": k}, np.where(win, 1.0, k)


FAMS = [
    ("exit_trailing", "exit_rule_lab E-c 移動停利（20 日新高回場）", fam_exit_trailing),
    ("exit_ma", "exit_rule_lab E-d 均線 regime（含遲滯帶）", fam_exit_ma),
    ("vol_targeting", "#15 波動度目標化", fam_vol_targeting),
    ("volmanaged_leverage", "#436/#439 變異數管理曝險", fam_volmanaged),
    ("donchian_turtle", "唐奇安／海龜通道", fam_donchian),
    ("keltner", "Keltner 通道突破（收盤近似 ATR）", fam_keltner),
    ("cta_momentum", "#2 CTA 時間序列動能（12 月等）", fam_cta_momentum),
    ("cta_multi_tf_voltarget", "多時間框架投票×波動目標", fam_cta_multi_tf_voltarget),
    ("drawdown_breaker", "overlay 候選 5 回撤斷路器", fam_drawdown_breaker),
    ("turn_of_month", "#25 月轉效應", fam_turn_of_month),
]


def seg(r_full, lo, hi):
    """r_full 從 I0 起；回傳 [lo, hi) 日期區間的年化／MDD／Sharpe。"""
    d = DATES.iloc[I0:].reset_index(drop=True)
    m = ((d >= pd.Timestamp(lo)) & (d < pd.Timestamp(hi))).to_numpy()
    r = r_full[m]
    if len(r) < 20:
        return None
    c = np.cumprod(1 + r)
    yrs = len(r) / 252
    sd = r.std(ddof=1)
    return {"cagr": float(c[-1] ** (1 / yrs) - 1) if c[-1] > 0 else -1.0, "mdd": float((c / np.maximum.accumulate(c) - 1).min()),
            "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0}


def main():
    B4.prog(f"開始；0050 {DATES.iloc[0].date()}～{DATES.iloc[-1].date()}，評估自 {DATES.iloc[I0].date()}")
    fams = []
    bh_r = R0[I0:]
    bh = B4.stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], I0)
    for fid, title, gen in FAMS:
        rows = []
        try:
            for (params, e), L, st in itertools.product(list(gen()), B4.LEVS, B4.STOPS):
                r, tr = B4.run_sim(e, L, st, I0)
                rows.append({**params, "L": L, "stop": st, **B4.stats(r, tr, I0), "_r": r})
        except Exception as ex:  # noqa: BLE001 —— 單一族失敗不影響其他族
            print(f"::warning::{fid} 失敗：{ex!r}")
            fams.append({"family": fid, "title": title, "error": repr(ex)})
            continue
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        base = [x for x in ok if x["L"] == 1.0 and x["stop"] is None]
        b1 = max(base, key=lambda x: x["calmar"]) if base else None
        bhl = None
        if best:
            rr, tt = B4.run_sim(np.ones(N), best["L"], None, I0)
            bhl = B4.stats(rr, tt, I0)
        clean = lambda x: None if x is None else {k: v for k, v in x.items() if k != "_r"}  # noqa: E731
        f = {"family": fid, "title": title, "start": str(DATES.iloc[I0].date()), "end": str(DATES.iloc[-1].date()),
             "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
             "buy_hold_0050_same_period": bh, "buy_hold_same_leverage_no_timing": bhl,
             "best_by_calmar": clean(best), "best_1x_nostop": clean(b1)}
        if best:
            f["best_seg_2015_2024"] = seg(best["_r"], "2015-01-01", "2025-01-01")
            f["best_seg_2025_on"] = seg(best["_r"], "2025-01-01", "2100-01-01")
            f["curve_png"] = plot(fid, title, best["_r"], bh_r)
            B4.prog(f"{fid} {len(rows)} 格；最好 {B4._fmt(clean(best))} → {best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}；"
                    f"2025 起 {f['best_seg_2025_on']['cagr']:+.1%}／{f['best_seg_2025_on']['mdd']:.1%}")
        fams.append(f)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(DATES.iloc[-1].date()),
           "buy_hold_0050": bh, "buy_hold_seg_2015_2024": seg(bh_r, "2015-01-01", "2025-01-01"),
           "buy_hold_seg_2025_on": seg(bh_r, "2025-01-01", "2100-01-01"), "families": fams,
           "notes": "樣本內最優化（描述性，全期含 2025 起一起挑參數，2025 起分段不是樣本外）；訊號 t 收盤算、t+1 生效；0050 含息；3× 超過台股融資上限只當參考。"}
    render(out)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_candidates(out)
    B4.prog(f"寫入 {OUT_JSON}")


def plot(fid, title, r, bh):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    dt = DATES.iloc[I0:]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.plot(dt, np.cumprod(1 + r), color="#2a6fdb", lw=1.6, label="最優化版本")
    ax.plot(dt, np.cumprod(1 + bh), color="#9aa0a6", lw=1.2, label="0050 買進持有（含息）")
    ax.axvline(pd.Timestamp("2025-01-01"), color="#c0392b", lw=0.8, ls="--")
    ax.set_yscale("log")
    ax.set_title(f"{fid} {title}（樣本內最優化，非投資建議）", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    p = D / "reaudit_curves" / f"batch3_b5_{fid}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p)
    plt.close(fig)
    return p.relative_to(HERE).as_posix()


def _p(x):
    return "—" if not x else f"{x['cagr']:+.1%}／{x['mdd']:.1%}"


def render(out):
    lines = [MK_B, "", "## 9. 第二批第 5 批 0050 價格擇時類 10 族結果（先.一五五-3 ③，`research/reaudit_batch5_price_timing.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；期間＝{out['families'][0].get('start', '—')}～{out['data_end']}（含 2025 起，保留資料已開放）。"
             "原試驗多在台指期／TAIEX 上，這裡一律改成 0050 現股曝險；訊號只用 t 日收盤以前的價格、t+1 生效；"
             "× 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%。0050 含息、成本照實（滑價＋手續費＋賣出證交稅 0.1%）、槓桿借款＝台灣無風險利率＋年 1%。"
             "**參數是用全期（含 2025 起）一起挑的，2025 起分段不是樣本外**；樣本內最優化一定偏樂觀；多重比較只當參考。3× 超過台股融資上限只當參考。非投資建議。", "",
             f"同期 0050 買進持有：全期 {_p(out['buy_hold_0050'])}；2015～2024 {_p(out['buy_hold_seg_2015_2024'])}；2025 起 {_p(out['buy_hold_seg_2025_on'])}。", "",
             "| 族 | 最好的一組（Calmar，MDD≤50%） | 全期年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 併入總表約第幾名 | 2015～2024 | 2025 起 | 1× 不設止損最好 | 同槓桿不擇時 | 越線格數 | 曲線 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        if "error" in f or not f.get("best_by_calmar"):
            lines.append(f"| {f['family']} | 失敗或無合格組：{f.get('error', '')} | | | | | | | | | | | | | |")
            continue
        b = f["best_by_calmar"]
        wr = "—" if b["win_rate"] is None else f"{b['win_rate']:.0%}"
        f["rank"] = B4._old_rank(b["calmar"])
        lines.append(f"| {f['family']}（{f['title']}） | {B4._fmt(b)} | {b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | {wr} | {b['trades']} | {b['calmar']:.2f} | 約第 {f['rank']} 名 | "
                     f"{_p(f['best_seg_2015_2024'])} | {_p(f['best_seg_2025_on'])} | {_p(f['best_1x_nostop'])} | {_p(f['buy_hold_same_leverage_no_timing'])} | {f['n_violates']} | [png]({f['curve_png']}) |")
    lines += ["", "「併入總表約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族比；本批期間 2004 起含 2008，跟第 0 節期間不同，只當粗排。"
              "交易次數＝減碼／出場次數；勝率＝每段持有期間結束時淨值高於進場時的比例。turn_of_month 換手極高，成本已照實扣。",
              "**讀法提醒**：0050 買進持有全期 MDD 本身越過天條一（2008）；本批最好的組合幾乎都是 1×、主要價值是把全期 MDD 壓到約 15～26%，"
              "代價是年化比買進持有低 2～6 個百分點；2025 起大多頭，所有擇時版本都落後買進持有。槓桿版（1.5× 以上）在全期多半越過 50%（見越線格數）。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates(out):
    """約前 10 名寫進 paper_opt_candidates.json（id 前綴 B5P-，重跑只換自己的條目）。"""
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B5P-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or f.get("rank", 99) > 10:
            continue
        note = ["樣本內最優化（偏樂觀，參數用全期含 2025 起挑）", "0050 價格擇時"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        s25 = f.get("best_seg_2025_on") or {}
        new.append({"id": f"B5P-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 5 批（0050 價格擇時）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～{f['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in (f.get("best_seg_2015_2024") or {}).items()},
                    "from_2025_same_params": {k: round(v, 4) for k, v in s25.items()} or None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B4.prog(f"候選欄新增價格擇時 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    main()
