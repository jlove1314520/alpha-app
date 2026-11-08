"""先.一五五-3 第二批第 10 批：其餘 regime 族 → 0050 曝險（零新外部請求）。

族：
- var1018_v7_us_unemployment：美國失業率（ALFRED 首次公布值、公布日 d 之後第 2 個交易日才吃報酬）→ 0050 降曝險。
- fut_vol_breakout：原台指期波動突破（0.5 ATR），改 0050；只有收盤價，用 |日報酬|×前收 近似 ATR。
- avg_pairwise_correlation：#133 抽樣 236 檔日報酬的滾動平均兩兩相關（用 Var(Σr) 拆解的閉式近似）→ 水位 expanding 百分位。
- dispersion_53：#53 全市場報酬離散度（236 檔當日橫斷面標準差的滾動平均）→ 水位 expanding 百分位。
模擬沿用第 4 批 run_sim／stats（只呼叫、不改核心檔）；訊號 t 收盤算、t+1 生效；各族從自己暖機完成那天起算。
樣本內最優化（描述性），參數用全期含 2025 起一起挑，2025 起分段不是樣本外；非投資建議。
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

import reaudit_batch5_price_timing as B5  # noqa: E402  （帶入 B4／延長後的 0050）

B4 = B5.B4
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch10.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B10-BEGIN -->", "<!-- BATCH3-B10-END -->"
DATES, N, R0, SHIFT, KS = B5.DATES, B5.N, B5.R0, B5.SHIFT, B5.KS
DT = pd.DatetimeIndex(DATES)


def fam_us_unemployment():
    obs = json.loads((D / "raw" / "ALFRED_UNRATE_initial_release.json").read_text(encoding="utf-8"))["observations"]
    u = pd.DataFrame(obs)
    u = u[u["value"] != "."].copy()
    u["month"] = pd.to_datetime(u["date"])
    u["released"] = pd.to_datetime(u["realtime_start"])
    u["value"] = u["value"].astype(float)
    u = u.sort_values("month").drop_duplicates("month").set_index("month")
    u["yoy"] = u["value"] - u["value"].shift(12)
    u["d3"] = u["value"] - u["value"].shift(3)
    u["sahm"] = u["value"].rolling(3).mean() - u["value"].rolling(3).mean().rolling(12).min()
    u = u.dropna(subset=["yoy", "d3", "sahm"])
    u = u.set_index("released").sort_index()
    u = u[~u.index.duplicated(keep="last")]
    rules = [("yoy", th) for th in (0.0, 0.3, 0.5, 1.0)] + [("d3", th) for th in (0.0, 0.2, 0.3)] + [("sahm", th) for th in (0.3, 0.5)]
    first_all = N
    out = []
    for col, th in rules:
        v, first = B4.to_daily(u[col])  # 公布日 d（美東早上＝台北晚上）→ d 之後第 2 個交易日才吃報酬
        first_all = min(first_all, first)
        for k in KS:
            e = np.where(np.isnan(v), 1.0, np.where(v > th, k, 1.0))
            out.append(({"rule": f"{col}>{th}", "riskoff_exposure": k}, e))
    return out, max(first_all, 250)


def fam_vol_breakout():
    S, RET = B5.S, B5.RET
    out = []
    for n, m, k in itertools.product((10, 20), (0.5, 1.0, 1.5), KS):
        atr = (RET.abs() * S.shift(1)).rolling(n, min_periods=n).mean()
        up = (S - S.shift(1) > m * atr).to_numpy()
        dn = (S.shift(1) - S > m * atr).to_numpy()
        e = B5._hold(up, dn, k)
        out.append(({"atr_days": n, "atr_mult": m, "riskoff_exposure": k}, SHIFT(e)))
    return out, 250


def _cross_section():
    import reaudit_ext2025_engine as E
    ext = E.load_extended()[0]
    px = pd.DataFrame({sid: pd.Series(d["adj_close"].astype(float).to_numpy(), index=pd.to_datetime(d["date"].astype(str).str[:10]))
                       for sid, d in ext.items()}).sort_index()
    px = px[~px.index.duplicated()]
    # 逐檔在自己有價日上算報酬（同第 6／7 批修正）
    return px.apply(lambda s: s.dropna().pct_change().reindex(s.index))


def _pct_family(series_by_name: dict):
    """series_by_name：{名稱: 以交易日為索引、t 收盤已知的日序列}；回傳格子與暖機完成日。"""
    out, i0 = [], N
    for name, s in series_by_name.items():
        for tname, pct in B4.transforms(s.dropna(), monthly=False):
            p = pct.reindex(DT).ffill().to_numpy()
            p = SHIFT(np.where(np.isnan(p), np.nan, p))
            ok = ~np.isnan(p)
            if ok.any():
                i0 = min(i0, int(np.argmax(ok)))
            for direction, q, k in itertools.product((1, -1), (0.7, 0.8, 0.9), KS):
                off = (p > q) if direction == 1 else (p < 1 - q)
                e = np.where(np.isnan(p), 1.0, np.where(off, k, 1.0))
                out.append(({"series": name, "transform": tname, "riskoff_when": "高" if direction == 1 else "低",
                             "pct_threshold": q, "riskoff_exposure": k}, e))
    return out, i0


_RET = None


def _ret():
    global _RET
    if _RET is None:
        _RET = _cross_section()
    return _RET


def fam_corr():
    R = _ret()
    ser = {}
    for w in (20, 60):
        cnt = R.notna().rolling(w).sum()
        valid = cnt.ge(w * 0.9)
        Rv = R.where(valid)
        var_i = Rv.rolling(w, min_periods=int(w * 0.9)).var()
        ssum = Rv.fillna(0.0).sum(axis=1).where(valid.sum(axis=1) > 0)
        n_eff = valid.sum(axis=1)
        var_sum = (Rv.fillna(0.0).where(valid, 0.0).sum(axis=1)).rolling(w).var()
        sd = np.sqrt(var_i)
        num = var_sum - var_i.sum(axis=1)
        den = sd.sum(axis=1) ** 2 - var_i.sum(axis=1)
        rho = (num / den).where(n_eff >= 30)
        del ssum
        ser[f"avgcorr_{w}d"] = rho
    return _pct_family(ser)


def fam_dispersion():
    R = _ret()
    xs = R.std(axis=1).where(R.notna().sum(axis=1) >= 30)
    return _pct_family({f"xsd_{w}d": xs.rolling(w, min_periods=w).mean() for w in (5, 20)})


FAMS = [
    ("var1018_v7_us_unemployment", "美國失業率（ALFRED 首次公布值）→ 0050", fam_us_unemployment),
    ("fut_vol_breakout", "波動突破（原台指期 0.5ATR）→ 0050", fam_vol_breakout),
    ("avg_pairwise_correlation", "236 檔平均兩兩相關水位 → 0050", fam_corr),
    ("dispersion_53", "#53 橫斷面報酬離散度水位 → 0050", fam_dispersion),
]


def main():
    B4.prog(f"第 10 批開始；0050 {DATES.iloc[0].date()}～{DATES.iloc[-1].date()}")
    fams = []
    for fid, title, gen in FAMS:
        try:
            grid, i0 = gen()
            rows = []
            for (params, e), L, st in itertools.product(grid, B4.LEVS, B4.STOPS):
                r, tr = B4.run_sim(e, L, st, i0)
                rows.append({**params, "L": L, "stop": st, **B4.stats(r, tr, i0), "_r": r})
        except Exception as ex:  # noqa: BLE001 —— 單一族失敗不影響其他族
            print(f"::warning::{fid} 失敗：{ex!r}")
            fams.append({"family": fid, "title": title, "error": repr(ex)})
            continue
        bh_r = R0[i0:]
        bh = B4.stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], i0)
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        base = [x for x in ok if x["L"] == 1.0 and x["stop"] is None]
        b1 = max(base, key=lambda x: x["calmar"]) if base else None
        bhl = None
        if best:
            rr, tt = B4.run_sim(np.ones(N), best["L"], None, i0)
            bhl = B4.stats(rr, tt, i0)
        clean = lambda x: None if x is None else {k: v for k, v in x.items() if k != "_r"}  # noqa: E731
        f = {"family": fid, "title": title, "start": str(DATES.iloc[i0].date()), "end": str(DATES.iloc[-1].date()),
             "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
             "buy_hold_0050_same_period": bh, "buy_hold_same_leverage_no_timing": bhl,
             "best_by_calmar": clean(best), "best_1x_nostop": clean(b1)}
        if best:
            B5.I0 = i0  # seg()／plot() 以 I0 對齊日期
            f["best_seg_2015_2024"] = B5.seg(best["_r"], "2015-01-01", "2025-01-01")
            f["best_seg_2025_on"] = B5.seg(best["_r"], "2025-01-01", "2100-01-01")
            f["bh_seg_2025_on"] = B5.seg(bh_r, "2025-01-01", "2100-01-01")
            f["curve_png"] = B5.plot("b10_" + fid, title, best["_r"], bh_r)
            B4.prog(f"{fid} {len(rows)} 格（{f['start']} 起）；最好 {B4._fmt(clean(best))} → {best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}；"
                    f"2025 起 {f['best_seg_2025_on']['cagr']:+.1%}／{f['best_seg_2025_on']['mdd']:.1%}；同期 0050 {bh['cagr']:+.1%}／{bh['mdd']:.1%}")
        fams.append(f)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(DATES.iloc[-1].date()), "families": fams,
           "notes": "樣本內最優化（描述性，全期含 2025 起一起挑參數，2025 起分段不是樣本外）；訊號 t 收盤算、t+1 生效（美國失業率公布日之後第 2 個交易日）；0050 含息；3× 超過台股融資上限只當參考。"}
    render(out)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_candidates(out)
    B4.prog(f"寫入 {OUT_JSON}")


def render(out):
    p = B5._p
    lines = [MK_B, "", "## 13. 第二批第 10 批 其餘 regime 族 → 0050（先.一五五-3 ③，`research/reaudit_batch10_regime_more.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；各族從自己訊號暖機完成那天起算，到 {out['data_end']}（含 2025 起）。訊號 t 收盤算、t+1 生效（美國失業率：公布日之後第 2 個交易日）；"
             "× 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%；0050 含息、成本照實。**參數用全期（含 2025 起）一起挑，2025 起分段不是樣本外**；樣本內最優化偏樂觀；多重比較只當參考；3× 超過融資上限只當參考。"
             "相關／離散度族用 #133 抽樣 236 檔（今天回看的名冊，有存活者偏誤）。非投資建議。", "",
             "| 族 | 期間 | 最好的一組（Calmar，MDD≤50%） | 全期年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 約第幾名 | 2015～2024 | 2025 起 | 同期 0050 | 0050 2025 起 | 同槓桿不擇時 | 1× 不設止損最好 | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        if "error" in f or not f.get("best_by_calmar"):
            lines.append(f"| {f['family']} | 失敗或無合格組：{f.get('error', '')} |" + " |" * 15)
            continue
        b = f["best_by_calmar"]
        wr = "—" if b["win_rate"] is None else f"{b['win_rate']:.0%}"
        f["rank"] = B4._old_rank(b["calmar"])
        lines.append(f"| {f['family']}（{f['title']}） | {f['start']}～ | {B4._fmt(b)} | {b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | {wr} | {b['trades']} | {b['calmar']:.2f} | 約第 {f['rank']} 名 | "
                     f"{p(f['best_seg_2015_2024'])} | {p(f['best_seg_2025_on'])} | {p(f['buy_hold_0050_same_period'])} | {p(f['bh_seg_2025_on'])} | {p(f['buy_hold_same_leverage_no_timing'])} | {p(f['best_1x_nostop'])} | {f['n_violates']} |")
    lines += ["", "「約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族粗比（期間不同，只當粗排）。交易次數＝減碼／出場次數。曲線 `research/data/reaudit_curves/batch3_b5_b10_*.png`（本機）。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates(out):
    """約前 10 名且交易數 ≥20 寫進候選欄（id 前綴 B10R-，重跑只換自己的條目）。"""
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B10R-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or f.get("rank", 99) > 10 or (b.get("trades") or 0) < 20:
            continue
        note = ["樣本內最優化（偏樂觀，參數用全期含 2025 起挑）", "regime→0050"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B10R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 10 批（regime→0050）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～{f['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in (f.get("best_seg_2015_2024") or {}).items()},
                    "from_2025_same_params": {k: round(v, 4) for k, v in (f.get("best_seg_2025_on") or {}).items()} or None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B4.prog(f"候選欄新增第 10 批 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    main()
