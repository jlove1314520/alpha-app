# -*- coding: utf-8 -*-
"""先.一五五-3 第 4 批 regime→0050 延長到 2025 起（紙上優化軌，描述性，非判定）。

第 4 批（reaudit_batch4_regime.py）的訊號對齊檔只到 2024 底；這支把能用本機資料／極少量請求接上的族延長到最新：
- fred_yield_curve：本機 FRED T10Y2Y 快取（research/data/raw/FRED_T10Y2Y_*.json，取涵蓋最長的那份），零請求；
  起點照原假說 FRED_START=2015-01-01（expanding 百分位暖機與原版一致）。
- copper_gold_ratio：yfinance HG=F／GC=F 各 1 次（2015-01-01 起，快取 research/data/raw_yf/EXT_*.parquet，已有就不重抓）；
  yfinance 官方未公布上限，本管線日常已在用（見 C:\\alpha\\CLAUDE.md 美股篩選資料源節）。
- fx_twd：FinMind TaiwanExchangeRate USD 2025／2026 各 1 次（已有快取就零請求），calls_last_hour() ≥ FX_MAX_USAGE（預設 300、上限 450）就略過此族；2026-11-10 用 450 送 2 次。
- option_pcr_overlay：#31 選擇權成交量 PCR，讀 TXO 整年快取（2025／2026 由 reaudit_batch14_ext2025.py fetch 抓），零請求。

模擬全部呼叫 reaudit_batch4_regime 的 transforms／to_daily／run_sim／stats（只呼叫、不改），0050 延長到 REAUDIT_END。
輸出：(a) 第 4 批挑出的最佳組（best_by_calmar）同參數看全期與 2025 起；(b) 全期重挑；(c) 核對：2024 底前的訊號值與原對齊檔差多少。
結果寫 REAUDIT_OPTIMIZED.md「8a」節（BATCH3-B4X 標記間）與 research/data/reaudit_batch3_batch4_ext2025.json。
參數用全期挑、2025 起分段不是樣本外。非投資建議。
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
_ARGV = sys.argv[1:]
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import reaudit_batch4_regime as B4  # noqa: E402

D = HERE / "data"
RAW, RAW_YF = D / "raw", D / "raw_yf"
OUT_JSON = D / "reaudit_batch3_batch4_ext2025.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B4X-BEGIN -->", "<!-- BATCH3-B4X-END -->"
SEG = pd.Timestamp("2025-01-01")
START = "2015-01-01"
prog = B4.prog


def s_fred():
    best = None
    for p in RAW.glob("FRED_T10Y2Y_*.json"):
        obs = json.loads(p.read_text(encoding="utf-8")).get("observations", [])
        if obs and (best is None or obs[-1]["date"] > best[-1]["date"] or len(obs) > len(best)):
            best = obs if best is None or obs[-1]["date"] >= best[-1]["date"] else best
    df = pd.DataFrame(best)
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").to_numpy(), index=pd.to_datetime(df["date"])).dropna()
    return s[s.index >= START], "本機 FRED T10Y2Y 快取（零請求）"


def _yf(tk):
    p = RAW_YF / f"EXT_{tk}__{START}__2026-11-07.parquet"
    if p.exists():
        return pd.read_parquet(p), 0
    import yfinance as yf
    df = yf.download(tk, start=START, end="2026-11-08", progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance {tk} 空表")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    out = pd.DataFrame({"date": pd.to_datetime(df.index).tz_localize(None).strftime("%Y-%m-%d"), "close": df["Close"].astype(float).to_numpy()})
    out.to_parquet(p, index=False)
    return out, 1


def s_copper_gold():
    (cu, n1), (au, n2) = _yf("HG=F"), _yf("GC=F")
    m = pd.merge(cu.rename(columns={"close": "cu"}), au.rename(columns={"close": "au"}), on="date").dropna()
    m = m[m["au"] > 0]
    s = pd.Series((m["cu"] / m["au"]).to_numpy(), index=pd.to_datetime(m["date"])).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s, f"yfinance HG=F／GC=F（快取 raw_yf/EXT_*；2026-11-08 首次抓 2 次，本次送 {n1 + n2} 次）"


def s_fx():
    files = sorted(RAW.glob("TaiwanExchangeRate__USD__20*.parquet"))
    have25 = any("__2025-" in p.name for p in files) and any("__2026-" in p.name for p in files)
    sent = 0
    if not have25:
        import finmind_client as f
        import os
        cap = int(os.environ.get("FX_MAX_USAGE", "300"))  # 只送 2 次；批次門檻 300 是給一次 150 次設的，可用環境變數放寬（≤450）
        cap = min(cap, 450)
        u = f.calls_last_hour()
        if u >= cap:
            raise RuntimeError(f"FinMind 用量 {u}/hr ≥{cap}，本輪不送 fx 請求")
        for y in (2025, 2026):
            f._fetch("TaiwanExchangeRate", "USD", f"{y}-01-01", f"{y}-12-31")
            sent += 1
        files = sorted(RAW.glob("TaiwanExchangeRate__USD__20*.parquet"))
    fr = []
    for p in files:
        x = pd.read_parquet(p)
        if "spot_sell" in x.columns:
            fr.append(x[["date", "spot_sell"]])
    fx = pd.concat(fr)
    fx["date"] = pd.to_datetime(fx["date"])
    fx["rate"] = pd.to_numeric(fx["spot_sell"], errors="coerce")
    fx = fx.dropna(subset=["rate"])
    fx = fx[(fx["rate"] > 0) & (fx["date"] >= START)].drop_duplicates("date").sort_values("date")
    r = fx.set_index("date")["rate"]
    s = (r / r.shift(20) - 1.0).dropna()  # 同 fx_twd_gate.py N_SIGNAL_DAYS=20
    return s, f"FinMind TaiwanExchangeRate USD spot_sell（本次送 {sent} 次請求）"


def _yfadj(tk, start):
    """同原假說 fetch_yf_index 的取法（yf.Ticker.history auto_adjust=True），只是終點延長；快取 raw_yf/EXT_*。"""
    p = RAW_YF / f"EXT_{tk.lstrip('^')}__{start}__2026-11-07.parquet"
    if p.exists():
        return pd.read_parquet(p), 0
    import yf_price_client as Y
    df = Y._fetch_one_suffix(tk, "", start, "2026-11-08")
    if df is None or df.empty:
        raise RuntimeError(f"yfinance {tk} 空表")
    df = df.reset_index()
    out = pd.DataFrame({"date": pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d"), "close": df["Close"].astype(float)})
    out.to_parquet(p, index=False)
    return out, 1


def _ratio(a, b, start, label):
    (x, n1), (y, n2) = _yfadj(a, start), _yfadj(b, start)
    m = pd.merge(x.rename(columns={"close": "a"}), y.rename(columns={"close": "b"}), on="date").dropna()
    m = m[m["b"] > 0]
    s = pd.Series((m["a"] / m["b"]).to_numpy(), index=pd.to_datetime(m["date"])).sort_index()
    return s[~s.index.duplicated(keep="last")], f"yfinance {label}（快取 raw_yf/EXT_*；本次送 {n1 + n2} 次）"


def s_vix():
    return _ratio("^VIX9D", "^VIX", "2011-01-01", "VIX9D／VIX")


def s_hy():
    return _ratio("HYG", "IEF", "2007-01-01", "HYG／IEF（還原價）")


def s_opt_pcr():
    """#31 台指選擇權成交量 PCR（日盤），口徑照 option_pcr_gate.build_pcr_series()；只讀 TXO 整年快取，零請求
    （2025／2026 由 reaudit_batch14_ext2025.py fetch 抓）。"""
    import reaudit_batch14_ext2025 as X
    s, files = X.txo_pcr("volume")
    return s, f"FinMind TaiwanOptionDaily TXO 日盤成交量（快取 {len(files)} 個整年檔，本次 0 次請求）"


FAMS = {"HQ#76": (s_vix, "vix_term_structure_aligned.csv", "date", "vix_term_ratio"),
        "hy_etf_ratio": (s_hy, "hy_etf_ratio_aligned.csv", "date", "hyg_ief_ratio"),
        "fred_yield_curve": (s_fred, "fred_yield_curve_aligned.csv", "date", "spread_level"),
        "copper_gold_ratio": (s_copper_gold, "copper_gold_ratio_aligned.csv", "date", "copper_gold_ratio"),
        "fx_twd": (s_fx, "fx_twd_aligned.csv", "date", "fx_change_n"),
        "option_pcr_overlay": (s_opt_pcr, "option_pcr_aligned.csv", "signal_date", "pcr")}


def seg_stats(r, i0):
    d = B4.DATES.iloc[i0:].reset_index(drop=True)
    m = (d >= SEG).to_numpy()
    rs = r[m]
    if len(rs) < 20:
        return None
    c = np.cumprod(1 + rs)
    yrs = (d[m].iloc[-1] - d[m].iloc[0]).days / 365.25
    sd = rs.std(ddof=1)
    return {"cagr": float(c[-1] ** (1 / yrs) - 1), "mdd": float((c / np.maximum.accumulate(c) - 1).min()),
            "sharpe": float(rs.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0, "total": float(c[-1] - 1)}


def grid(s):
    i0, res = None, []
    for tname, pct in B4.transforms(s, False):
        p, first = B4.to_daily(pct)
        i0 = first if i0 is None else min(i0, first)
        for direction, q, k in itertools.product((1, -1), (0.7, 0.8, 0.9), (0.0, 0.5)):
            off = (p > q) if direction == 1 else (p < 1 - q)
            e = np.where(np.isnan(p), 1.0, np.where(off, k, 1.0))
            res.append(({"transform": tname, "riskoff_when": "高" if direction == 1 else "低", "pct_threshold": q, "riskoff_exposure": k}, e))
    return res, i0


def main():
    old = {f["family"]: f for f in json.loads((D / "reaudit_batch3_batch4.json").read_text(encoding="utf-8"))["families"]}
    out = []
    for fid, (fn, csv, dcol, vcol) in FAMS.items():
        try:
            s, src = fn()
        except Exception as ex:  # noqa: BLE001 —— 單族失敗只略過該族
            prog(f"::warning::{fid} 略過：{ex!r}")
            out.append({"family": fid, "error": repr(ex)})
            continue
        a = pd.read_csv(D / csv)
        a = pd.Series(a[vcol].astype(float).to_numpy(), index=pd.to_datetime(a[dcol]))
        j = a.index.intersection(s.index)
        diff = float(np.nanmax(np.abs(a.loc[j].to_numpy() - s.loc[j].to_numpy()))) if len(j) else None
        g, i0 = grid(s)
        ob = old[fid]["best_by_calmar"]
        keys = ("transform", "riskoff_when", "pct_threshold", "riskoff_exposure")
        rows, same = [], None
        for (params, e), L, st in itertools.product(g, B4.LEVS, B4.STOPS):
            r, tr = B4.run_sim(e, L, st, i0)
            row = {**params, "L": L, "stop": st, **B4.stats(r, tr, i0), "seg2025": seg_stats(r, i0)}
            rows.append(row)
            if all(params[k] == ob[k] for k in keys) and L == ob["L"] and st == ob["stop"]:
                same = row
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        ok2 = [x for x in ok if x["L"] <= 2.0]
        best2 = max(ok2, key=lambda x: x["calmar"]) if ok2 else None
        bh_r = B4.R0[i0:]
        bh = {**B4.stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], i0), "seg2025": seg_stats(bh_r, i0)}
        rec = {"family": fid, "source": src, "signal_last": str(s.index[-1].date()), "start": str(B4.DATES.iloc[i0].date()),
               "end": str(B4.DATES.iloc[-1].date()), "n_grid": len(rows), "overlap_n": len(j), "max_abs_diff_vs_aligned": diff,
               "old_best_2015_2024": {k: ob[k] for k in (*keys, "L", "stop", "cagr", "mdd", "sharpe")},
               "same_params_full": same, "rebest_full": best, "rebest_full_L2": best2, "buy_hold_0050": bh}
        out.append(rec)
        sg = (same or {}).get("seg2025") or {}
        prog(f"{fid}：訊號到 {rec['signal_last']}，核對差 {diff}；同參數全期 {same['cagr']:+.1%}／{same['mdd']:.1%}，"
             f"2025 起 {sg.get('cagr', float('nan')):+.1%}／{sg.get('mdd', float('nan')):.1%}；重挑 {best['cagr']:+.1%}／{best['mdd']:.1%}")
    res = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(B4.DATES.iloc[-1].date()), "families": out,
           "notes": "參數用全期挑、2025 起分段不是樣本外；0050 含息；3× 超過台股融資上限只當參考。非投資建議。"}
    OUT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(res)
    update_candidates(res)
    prog(f"寫入 {OUT_JSON}")


def _slim(r):
    if not r:
        return None
    o = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("seg2025", "calmar")}
    return o


def update_candidates(res):
    """把延長結果寫回本機候選檔的 B4R- 條目（只改有延長結果的族；讀寫失敗只記警告）。"""
    p = D / "paper_opt_candidates.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        by = {f["family"]: f for f in res["families"] if "error" not in f}
        for c in d.get("candidates", []):
            fid = str(c.get("id", ""))[4:] if str(c.get("id", "")).startswith("B4R-") else None
            if fid not in by:
                continue
            f = by[fid]
            sm, b2 = f["same_params_full"] or {}, f["rebest_full_L2"]
            sg = sm.get("seg2025") or {}
            c["from_2025_same_params"] = {"cagr": round(sg.get("cagr", 0), 4), "mdd": round(sg.get("mdd", 0), 4),
                                          "sharpe": round(sg.get("sharpe", 0), 4), "end": f["end"]}
            c["full_period_same_params"] = {"cagr": round(sm["cagr"], 4), "mdd": round(sm["mdd"], 4), "sharpe": round(sm["sharpe"], 4)}
            c["violates_survival_extended"] = bool(sm.get("violates_survival"))
            c["extended_rebest_L2"] = {**(_slim(b2) or {}), "from_2025": (b2 or {}).get("seg2025")}
            base = c.get("notes", "").replace("；2025 起尚未延長重算（對齊檔只到 2024 底）", "")
            add = f"；2026-11-08 延長到 {f['end']}（reaudit_batch4_ext2025.py）"
            if sm.get("violates_survival"):
                add += f"：同參數全期 MDD {sm['mdd']:.1%} 越過 50%（天條一），上紙上改用 extended_rebest_L2 那組或另加條件"
            c["notes"] = base.split("；2026-11-08 延長")[0] + add
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        prog("候選檔 B4R- 條目已更新")
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::候選檔更新失敗：{ex!r}")


def _p(x):
    return "—" if x is None else f"{x:+.1%}"


def _b(r):
    if not r:
        return "—"
    st = "不設" if r["stop"] is None else f"{r['stop']:.0%}"
    return f"{r['transform']}／{r['riskoff_when']}避險／{r['pct_threshold']:.0%}／避險曝險 {r['riskoff_exposure']}／{r['L']}×／止損 {st}"


def render(res):
    L = [MK_B, f"### 8a. 第 4 批 regime→0050 延長到 2025 起（{res['generated_at'][:16]}，資料到 {res['data_end']}）", "",
         "參數用全期挑、2025 起分段**不是樣本外**；訊號觀察日後第 2 個交易日生效；0050 含息；非投資建議。", "",
         "| 族 | 訊號來源 | 第 4 批最佳組（2015～2024） | 同參數全期 年化／MDD／Sh | 同參數 2025 起 年化／MDD | 全期重挑 | 重挑 年化／MDD／Sh | ≤2× 重挑 年化／MDD／2025 起 | 0050 同期全期／2025 起 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for f in res["families"]:
        if "error" in f:
            L.append(f"| {f['family']} | 略過：{f['error']} | | | | | | | |")
            continue
        sm, rb, bh, b2 = f["same_params_full"] or {}, f["rebest_full"] or {}, f["buy_hold_0050"], f.get("rebest_full_L2") or {}
        sg, bs = sm.get("seg2025") or {}, bh.get("seg2025") or {}
        ob = f["old_best_2015_2024"]
        L.append(f"| {f['family']} | {f['source']}，到 {f['signal_last']}（2024 底前核對最大差 {f['max_abs_diff_vs_aligned']}） | {_b(ob)}：{_p(ob['cagr'])}／{_p(ob['mdd'])} | "
                 f"{_p(sm.get('cagr'))}／{_p(sm.get('mdd'))}／{sm.get('sharpe', 0):.2f}{'（越天條一）' if sm.get('violates_survival') else ''} | {_p(sg.get('cagr'))}／{_p(sg.get('mdd'))} | "
                 f"{_b(rb)} | {_p(rb.get('cagr'))}／{_p(rb.get('mdd'))}／{rb.get('sharpe', 0):.2f} | {_b(b2)}：{_p(b2.get('cagr'))}／{_p(b2.get('mdd'))}／{_p((b2.get('seg2025') or {}).get('cagr'))} | {_p(bh['cagr'])}／{_p(bh['mdd'])}；{_p(bs.get('cagr'))}／{_p(bs.get('mdd'))} |")
    L += ["", MK_E]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if MK_B in txt:
        txt = txt[:txt.index(MK_B)] + block + txt[txt.index(MK_E) + len(MK_E):]
    else:
        anchor = "<!-- BATCH3-B4-END -->"
        txt = txt.replace(anchor, anchor + "\n\n" + block, 1) if anchor in txt else txt + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
