"""先.一五五-3 第 14 批延長：#69 台指選擇權未平倉 PCR → 0050，訊號延長到 2025 起。

兩個子指令，分開兩個行程跑（run 會 import 第 14 批模組、那裡封鎖網路）：
- `python research/reaudit_batch14_ext2025.py fetch`：FinMind TaiwanOptionDaily（TXO）2025、2026 各 1 次＝共 2 次請求，
  只走 finmind_client._fetch（共用節流＋快取，已有快取就零請求）。calls_last_hour() ≥ FETCH_MAX_USAGE（預設 300、上限 450）就不送；
  REAUDIT_DEADLINE（epoch 秒）到就放棄。逐年抓同 option_oi_pcr_gate.py（避免跨年單次觸發 502）。
- `python research/reaudit_batch14_ext2025.py run`：零請求。只讀「整年」快取檔（`__YYYY-01-01__YYYY-12-31`），
  口徑逐字照 option_oi_pcr_gate.build_oi_pcr_series()（只用 trading_session==position 日盤；put／call 未平倉量加總相除）；
  2024 底前與 `data/option_oi_pcr_aligned.csv` 逐值核對。第 14 批同一套網格、觀察日之後第 2 個交易日才吃報酬，
  訊號一路用到快取最後一天（0050 本機到 2026-10-05）。
  結果寫 REAUDIT_OPTIMIZED.md 17a 節（BATCH3-B14X 標記間）、`research/data/reaudit_batch3_batch14_ext2025.json`，
  並更新候選檔 B14R-option_oi_pcr_69 條目的延長數字。
`txo_pcr(kind)` 也給 reaudit_batch4_ext2025.py 延長 #31 成交量 PCR（option_pcr_overlay）用。
參數用全期挑、2025 起分段不是樣本外；非投資建議。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DS, SID = "TaiwanOptionDaily", "TXO"
RAW = HERE / "data" / "raw"
YEARS_NEW = ((2025, "2025-01-01", "2025-12-31"), (2026, "2026-01-01", "2026-12-31"))


def fetch():
    import finmind_client as f
    cap = min(int(os.environ.get("FETCH_MAX_USAGE", "300")), 450)
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1200))
    sent = 0
    for yr, s, e in YEARS_NEW:
        p = RAW / f"{DS}__{SID}__{s}__{e}.parquet"
        if p.exists():
            print(f"{yr} 已有快取，零請求")
            continue
        while True:
            u = f.calls_last_hour()
            if u < cap:
                break
            if time.time() + 60 > dl:
                print(f"用量 {u}/hr ≥{cap} 到截止仍未降，本次共送 {sent} 次")
                return 2
            print(f"用量 {u}/hr ≥{cap}，一分鐘後再看", flush=True)
            time.sleep(60)
        df = f._fetch(DS, SID, s, e)
        sent += 1
        print(f"{yr}：送 1 次（用量 {u}/hr 時），{len(df)} 列，{df['date'].min() if len(df) else '—'}～{df['date'].max() if len(df) else '—'}")
    print(f"共送 {sent} 次")
    return 0


def txo_pcr(kind: str = "open_interest"):
    """日盤 put／call 加總比值（kind＝open_interest 照 #69、volume 照 #31）。只讀整年快取檔，零請求。"""
    import pandas as pd
    pat = re.compile(rf"{DS}__{SID}__(\d{{4}})-01-01__\1-12-31\.parquet$")
    files = sorted(p for p in RAW.glob(f"{DS}__{SID}__*.parquet") if pat.search(p.name))
    fr = []
    for p in files:
        x = pd.read_parquet(p, columns=["date", "call_put", "trading_session", kind])
        x = x[x["trading_session"] == "position"]
        x[kind] = pd.to_numeric(x[kind], errors="coerce")
        fr.append(x.dropna(subset=[kind]).groupby(["date", "call_put"])[kind].sum())
    g = pd.concat(fr).groupby(level=[0, 1]).sum().unstack(fill_value=0.0)
    for c in ("put", "call"):
        if c not in g.columns:
            g[c] = 0.0
    g = g[g["call"] > 0]
    s = (g["put"] / g["call"]).astype(float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index(), [p.name for p in files]


def run():
    sys.argv = [sys.argv[0]]
    import itertools

    import numpy as np
    import pandas as pd

    import reaudit_batch14_regime_misc as B14  # 封鎖網路；B10／B4／B5 一起帶入

    B10, B4, B5 = B14.B10, B14.B4, B14.B5
    s, files = txo_pcr("open_interest")
    old = pd.read_csv(HERE / "data" / "option_oi_pcr_aligned.csv", parse_dates=["signal_date"]).set_index("signal_date")["oi_pcr"]
    j = old.index.intersection(s.index)
    diff = float(np.abs(old.loc[j] - s.loc[j]).max())
    sig_last = s.index.max()
    B4.prog(f"延長：訊號到 {sig_last.date()}，2024 底前核對 {len(j)} 日最大差 {diff}；0050 到 {B10.DATES.iloc[-1].date()}")
    if diff > 1e-6:
        raise RuntimeError(f"2024 底前與原對齊檔不一致（最大差 {diff}），不跑")

    B14.SIG_END = sig_last
    grid, i0 = B14._obs_family({"oi_pcr": s})
    prev = {x["family"]: x for x in json.loads((HERE / "data" / "reaudit_batch3_batch14.json").read_text(encoding="utf-8"))["families"]}
    ob = prev["option_oi_pcr_69"]["best_by_calmar"]
    keys = ("series", "transform", "riskoff_when", "pct_threshold", "riskoff_exposure")
    rows, same = [], None
    B5.I0 = i0
    for (params, e), L, st in itertools.product(grid, B4.LEVS, B4.STOPS):
        r, tr = B4.run_sim(e, L, st, i0)
        row = {**params, "L": L, "stop": st, **B4.stats(r, tr, i0), "_r": r}
        rows.append(row)
        if all(params[k] == ob[k] for k in keys) and L == ob["L"] and st == ob["stop"]:
            same = row
    ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
    best = max(ok, key=lambda x: x["calmar"]) if ok else None
    ok2 = [x for x in ok if x["L"] <= 2.0]
    best2 = max(ok2, key=lambda x: x["calmar"]) if ok2 else None
    bh_r = B10.R0[i0:]
    bh = B4.stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], i0)
    bhl = None
    if same:
        rr, tt = B4.run_sim(np.ones(B10.N), same["L"], None, i0)
        bhl = {**B4.stats(rr, tt, i0), "seg2025": B5.seg(rr, "2025-01-01", "2100-01-01"), "seg_sig": B5.seg(rr, "2015-01-01", "2025-01-01")}

    def pack(x):
        if x is None:
            return None
        o_ = {k: v for k, v in x.items() if k != "_r"}
        o_["seg_2015_2024"] = B5.seg(x["_r"], "2015-01-01", "2025-01-01")
        o_["seg2025"] = B5.seg(x["_r"], "2025-01-01", "2100-01-01")
        return o_

    n_off_2025 = None
    for (params, e) in grid:
        if all(params[k] == ob[k] for k in keys):
            d = B10.DATES.reset_index(drop=True)
            m = (d >= pd.Timestamp("2025-01-01")).to_numpy()
            n_off_2025 = int((e[m] < 1).sum())
            break
    curve = B5.plot("b14x_option_oi_pcr_69", "#69 選擇權未平倉 PCR→0050（延長到 2025 起）", same["_r"], bh_r) if same else None
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(B10.DATES.iloc[-1].date()),
           "signal_last": str(sig_last.date()), "start": str(B10.DATES.iloc[i0].date()), "max_abs_diff_vs_old_2024": diff,
           "cache_files": files, "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
           "old_best_signal_to_2024": ob, "same_params_extended": pack(same), "rebest_extended": pack(best),
           "rebest_extended_L2": pack(best2), "buy_hold_0050": {**bh, "seg2025": B5.seg(bh_r, "2025-01-01", "2100-01-01")},
           "buy_hold_same_leverage_no_timing": bhl, "riskoff_days_2025_same_params": n_off_2025, "curve_png": curve,
           "notes": "參數用全期挑、2025 起分段不是樣本外；觀察日之後第 2 個交易日才吃報酬；0050 含息；3× 超過台股融資上限只當參考；非投資建議。"}
    (HERE / "data" / "reaudit_batch3_batch14_ext2025.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out, lambda v: "—" if v is None else f"{v:+.1%}")
    update_candidates(out)
    sm, sg = out["same_params_extended"], out["same_params_extended"]["seg2025"]
    B4.prog(f"同參數全期 {sm['cagr']:+.1%}／{sm['mdd']:.1%}／Sh {sm['sharpe']:.2f}；2025 起 {sg['cagr']:+.1%}／{sg['mdd']:.1%}（減碼 {n_off_2025} 天）；"
            f"重挑 {best['cagr']:+.1%}／{best['mdd']:.1%}；同槓桿不擇時 {bhl['cagr']:+.1%}／{bhl['mdd']:.1%}")


def _fmt(x):
    st = "不設" if x["stop"] is None else f"{x['stop']:.0%}"
    # run_sim 判定：「高」＝百分位 > q；「低」＝百分位 < 1−q（2026-11-10 修標籤，原本「低」也印 q）
    q = x["pct_threshold"] if x["riskoff_when"] == "高" else 1 - x["pct_threshold"]
    return f"{x['series']}／{x['transform']}／{x['riskoff_when']}於 {q:.0%} 百分位減到 {x['riskoff_exposure']}／{x['L']}×／止損 {st}"


def render(out, p):
    MD = HERE / "REAUDIT_OPTIMIZED.md"
    MK_B, MK_E = "<!-- BATCH3-B14X-BEGIN -->", "<!-- BATCH3-B14X-END -->"
    L = [MK_B, "", f"### 17a. 第 14 批 #69 台指選擇權未平倉 PCR → 0050 延長到 2025 起（{out['generated_at'][:16]}，`research/reaudit_batch14_ext2025.py`）", "",
         f"訊號 FinMind TaiwanOptionDaily（TXO，日盤）2025、2026 各補抓 1 次，延長到 {out['signal_last']}；0050 到 {out['data_end']}；"
         f"2024 底前與原對齊檔最大差 {out['max_abs_diff_vs_old_2024']}。參數用全期挑、2025 起分段**不是樣本外**；觀察日之後第 2 個交易日才吃報酬；非投資建議。", "",
         "| 組 | 參數 | 全期 年化／MDD／Sh／Calmar | 2015～2024 年化／MDD | 2025 起 年化／MDD | 交易 |", "|---|---|---|---|---|---|"]
    for lab, k in (("第 14 批最佳組（同參數）", "same_params_extended"), ("延長後全期重挑", "rebest_extended"), ("延長後 ≤2× 重挑", "rebest_extended_L2")):
        x = out[k]
        if not x:
            L.append(f"| {lab} | — | | | | |")
            continue
        a, b = x["seg_2015_2024"] or {}, x["seg2025"] or {}
        L.append(f"| {lab} | {_fmt(x)} | {p(x['cagr'])}／{p(x['mdd'])}／{x['sharpe']:.2f}／{(x['calmar'] or 0):.2f}{'（越天條一）' if x['violates_survival'] else ''} | "
                 f"{p(a.get('cagr'))}／{p(a.get('mdd'))} | {p(b.get('cagr'))}／{p(b.get('mdd'))} | {x['trades']} |")
    bh, bl = out["buy_hold_0050"], out["buy_hold_same_leverage_no_timing"] or {}
    L.append(f"| 0050 買進持有（同期） | 1× | {p(bh['cagr'])}／{p(bh['mdd'])}／{bh['sharpe']:.2f}／{(bh['calmar'] or 0):.2f} | — | {p((bh.get('seg2025') or {}).get('cagr'))}／{p((bh.get('seg2025') or {}).get('mdd'))} | — |")
    if bl:
        L.append(f"| 同槓桿不擇時（同期） | {out['same_params_extended']['L']}× | {p(bl['cagr'])}／{p(bl['mdd'])}／{bl['sharpe']:.2f}／{(bl['calmar'] or 0):.2f} | "
                 f"{p((bl.get('seg_sig') or {}).get('cagr'))}／{p((bl.get('seg_sig') or {}).get('mdd'))} | {p((bl.get('seg2025') or {}).get('cagr'))}／{p((bl.get('seg2025') or {}).get('mdd'))} | — |")
    L += ["", f"同參數那組 2025 起訊號實際減碼 {out['riskoff_days_2025_same_params']} 個交易日（第 14 批時 2025 起一律不擇時）。", "", MK_E]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if MK_B in txt:
        txt = txt[:txt.index(MK_B)] + block + txt[txt.index(MK_E) + len(MK_E):]
    else:
        anchor = "<!-- BATCH3-B14-END -->"
        txt = txt.replace(anchor, anchor + "\n\n" + block, 1) if anchor in txt else txt + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def update_candidates(out):
    p = HERE / "data" / "paper_opt_candidates.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        for c in d.get("candidates", []):
            if c.get("id") != "B14R-option_oi_pcr_69":
                continue
            sm, b2 = out["same_params_extended"], out["rebest_extended_L2"]
            sg = sm["seg2025"] or {}
            c["from_2025_same_params"] = {"cagr": round(sg.get("cagr", 0), 4), "mdd": round(sg.get("mdd", 0), 4),
                                          "sharpe": round(sg.get("sharpe", 0), 4), "end": out["data_end"],
                                          "riskoff_days": out["riskoff_days_2025_same_params"]}
            c["full_period_same_params"] = {"cagr": round(sm["cagr"], 4), "mdd": round(sm["mdd"], 4), "sharpe": round(sm["sharpe"], 4)}
            c["violates_survival_extended"] = bool(sm["violates_survival"])
            c["extended_rebest_L2"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in b2.items()
                                       if k in ("series", "transform", "riskoff_when", "pct_threshold", "riskoff_exposure", "L", "stop", "cagr", "mdd", "sharpe")}
            c["notes"] = c.get("notes", "").split("；2026-11-10 訊號延長")[0] + f"；2026-11-10 訊號延長到 {out['signal_last']}（reaudit_batch14_ext2025.py）"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::候選檔更新失敗：{ex!r}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    sys.exit(fetch() if cmd == "fetch" else (run() or 0))
