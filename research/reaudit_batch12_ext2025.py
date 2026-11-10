# -*- coding: utf-8 -*-
"""先.一五五-3 第 12 批 #54 成交值集中度 → 0050，訊號延長到 2025 起（零請求）。

資料：
- 2024 底前：原 `data/turnover_concentration_gate54.csv`（FinMind 逐檔 Trading_money，名冊＝
  `TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet` 數字開頭代號 2,532 個）原值，不重算。
- 2025 起：官方全市場日檔 `research/data/official_daily_2025/{twse,tpex}/`（`fetch_official_daily_2025.py` 抓），
  **只取同一份 2,532 代號名冊**當日有成交者——〔自行裁量〕2010／2013 年 494 個重疊日核對：官方日檔套原名冊
  前 20 檔占比與原 csv 平均差 −0.4pp，套全市場四碼則差 −5.1pp（原 csv 不是全市場），所以照原名冊才不會在 2025-01 出現假斷層；
  代價＝2025 起新上市股不納入（照實揭露）。
- 篩選照原公式（turnover_concentration_gate54.build_concentration_series）：n_t<300 或 FMTQIK 涵蓋率 <80%（或無 FMTQIK）→ 該日 NaN。
- 只延長到「兩個來源都已抓到」的最後連續交易日；之後沒有訊號 → 不擇時（曝險 1），不拿舊值頂替。
模擬只呼叫第 12 批 `_obs_family`／第 4 批 run_sim／stats、第 5 批 seg／plot（不改核心檔）。
用法：python research/reaudit_batch12_ext2025.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OFF = HERE / "data" / "official_daily_2025"
MV = HERE / "data" / "raw_twse_market_volume"
FAM = "turnover_concentration_54"
CID = "B12R-turnover_concentration_54"


def universe() -> set[str]:
    out = set()
    for f in (HERE / "data" / "raw").glob("TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet"):
        sid = f.name.split("__")[1]
        if re.match(r"^[0-9]", sid):
            out.add(sid)
    return out


def series_2025():
    import numpy as np
    import pandas as pd
    try:
        st = json.loads((OFF / "_status.json").read_text(encoding="utf-8"))
    except Exception as ex:  # noqa: BLE001 -- 狀態檔只是揭露用，讀不到不影響計算
        print(f"⚠ 讀 _status.json 失敗（{type(ex).__name__}），略過")
        st = None
    uni = universe()
    mv = []
    for p in sorted(MV.glob("FMTQIK_202[56]*.parquet")):
        mv.append(pd.read_parquet(p, columns=["date", "total_value"]))
    mkt = pd.concat(mv).assign(date=lambda x: pd.to_datetime(x["date"])).set_index("date")["total_value"] if mv else pd.Series(dtype=float)
    rows, last_ok = [], None
    for p in sorted((OFF / "twse").glob("*.json")):
        q = OFF / "tpex" / p.name
        if not q.exists():
            break  # 只用兩邊都抓到的連續日期
        a, b = (json.loads(x.read_text(encoding="utf-8")) for x in (p, q))
        d = pd.Timestamp(a["date"])
        last_ok = d
        if a["status"] != "ok":
            continue  # 休市
        allrows = {**(b["rows"] if b["status"] == "ok" else {}), **a["rows"]}
        m = np.array([v[5] for c, v in allrows.items() if c in uni and v[5] and v[5] > 0], float)
        if len(m) == 0:
            continue
        w = m / m.sum()
        rows.append({"date": d, "conc": float((w ** 2).sum()), "top20_share": float(np.sort(w)[::-1][:20].sum()),
                     "n_t": len(m), "sample_total_money": float(m.sum())})
    df = pd.DataFrame(rows).set_index("date")
    df["total_value"] = mkt.reindex(df.index)
    df["coverage_ratio"] = df["sample_total_money"] / df["total_value"]
    bad = (df["n_t"] < 300) | df["coverage_ratio"].isna() | (df["coverage_ratio"] < 0.80)
    df.loc[bad, "conc"] = np.nan
    return df, last_ok, st, int(bad.sum())


def main():
    sys.argv = [sys.argv[0]]
    import itertools

    import numpy as np
    import pandas as pd

    import reaudit_batch12_market_internals as B12  # 封鎖網路；B10／B4／B5 一起帶入

    B10, B4, B5 = B12.B10, B12.B4, B12.B5
    old = pd.read_csv(HERE / "data" / "turnover_concentration_gate54.csv", parse_dates=["date"]).set_index("date")
    old = old[old.index <= "2024-12-31"]
    new, last_ok, fst, n_bad = series_2025()
    if last_ok is None or new.empty:
        raise RuntimeError("2025 起官方日檔還沒有資料，不跑")
    cols = ["conc", "top20_share"]
    full = pd.concat([old[cols], new[cols]]).sort_index()
    top20 = full["top20_share"].where(full["conc"].notna()).astype(float)
    hhi = full["conc"].astype(float)
    # 斷層檢查：2024-12 vs 2025-01 前 20 檔占比月均
    lv24 = float(old["top20_share"].loc["2024-12"].mean())
    lv25 = float(new["top20_share"].loc["2025-01"].mean()) if len(new.loc["2025-01"]) else None
    B4.prog(f"延長：訊號到 {last_ok.date()}（2025 起 {len(new)} 日、篩掉 {n_bad} 日）；前 20 檔占比 2024-12 均 {lv24:.4f}、2025-01 均 {lv25}")

    B12.SIG_END = last_ok
    grid, i0 = B12._obs_family({"turnover_hhi": hhi, "turnover_top20": top20})
    prev = {x["family"]: x for x in json.loads((HERE / "data" / "reaudit_batch3_batch12.json").read_text(encoding="utf-8"))["families"]}
    ob = prev[FAM]["best_by_calmar"]
    keys = ("series", "transform", "riskoff_when", "pct_threshold", "riskoff_exposure")
    rows, same, e_same = [], None, None
    B5.I0 = i0
    for (params, e), L, st in itertools.product(grid, B4.LEVS, B4.STOPS):
        r, tr = B4.run_sim(e, L, st, i0)
        row = {**params, "L": L, "stop": st, **B4.stats(r, tr, i0), "_r": r}
        rows.append(row)
        if all(params[k] == ob[k] for k in keys) and L == ob["L"] and st == ob["stop"]:
            same, e_same = row, e
    ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None]
    best = max(ok, key=lambda x: x["calmar"]) if ok else None
    ok2 = [x for x in ok if x["L"] <= 2.0]
    best2 = max(ok2, key=lambda x: x["calmar"]) if ok2 else None
    bh_r = B10.R0[i0:]
    bh = B4.stats(bh_r, [(1.0, float(np.prod(1 + bh_r)))], i0)
    rr, tt = B4.run_sim(np.ones(B10.N), same["L"], None, i0)
    bhl = {**B4.stats(rr, tt, i0), "seg2025": B5.seg(rr, "2025-01-01", "2100-01-01"), "seg_sig": B5.seg(rr, "2015-01-01", "2025-01-01")}

    def pack(x):
        if x is None:
            return None
        o_ = {k: v for k, v in x.items() if k != "_r"}
        o_["seg_2015_2024"] = B5.seg(x["_r"], "2015-01-01", "2025-01-01")
        o_["seg2025"] = B5.seg(x["_r"], "2025-01-01", "2100-01-01")
        return o_

    d = B10.DATES.reset_index(drop=True)
    n_off_2025 = int((e_same[(d >= pd.Timestamp("2025-01-01")).to_numpy()] < 1).sum())
    curve = B5.plot("b12x_turnover_concentration_54", "#54 成交值集中度→0050（延長到 2025 起）", same["_r"], bh_r)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(B10.DATES.iloc[-1].date()),
           "signal_last": str(last_ok.date()), "start": str(B10.DATES.iloc[i0].date()),
           "n_days_2025": int(len(new)), "n_filtered_2025": n_bad, "top20_mean_2024_12": lv24, "top20_mean_2025_01": lv25,
           "fetch_status": fst, "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
           "old_best_signal_to_2024": ob, "same_params_extended": pack(same), "rebest_extended": pack(best),
           "rebest_extended_L2": pack(best2), "buy_hold_0050": {**bh, "seg2025": B5.seg(bh_r, "2025-01-01", "2100-01-01")},
           "buy_hold_same_leverage_no_timing": bhl, "riskoff_days_2025_same_params": n_off_2025, "curve_png": curve,
           "notes": "2025 起名冊＝原 FinMind 快取 2,532 代號（不含 2025 起新上市）；參數用全期挑、2025 起分段不是樣本外；"
                    "觀察日之後第 2 個交易日才吃報酬；0050 含息；3× 超過台股融資上限只當參考；非投資建議。"}
    (HERE / "data" / "reaudit_batch3_batch12_ext2025.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out, lambda v: "—" if v is None else f"{v:+.1%}")
    update_candidates(out)
    sm, sg = out["same_params_extended"], out["same_params_extended"]["seg2025"]
    B4.prog(f"同參數全期 {sm['cagr']:+.1%}／{sm['mdd']:.1%}／Sh {sm['sharpe']:.2f}／Calmar {sm['calmar']:.2f}；2025 起 {sg['cagr']:+.1%}／{sg['mdd']:.1%}（減碼 {n_off_2025} 天）；"
            f"重挑 {best['cagr']:+.1%}／{best['mdd']:.1%}（{_fmt(best)}）；同槓桿不擇時 {bhl['cagr']:+.1%}／{bhl['mdd']:.1%}；0050 {bh['cagr']:+.1%}／{bh['mdd']:.1%}")


def _fmt(x):
    st = "不設" if x["stop"] is None else f"{x['stop']:.0%}"
    # run_sim 判定：「高」＝百分位 > q；「低」＝百分位 < 1−q（2026-11-10 修標籤，原本「低」也印 q）
    q = x["pct_threshold"] if x["riskoff_when"] == "高" else 1 - x["pct_threshold"]
    return f"{x['series']}／{x['transform']}／{x['riskoff_when']}於 {q:.0%} 百分位減到 {x['riskoff_exposure']}／{x['L']}×／止損 {st}"


def render(out, p):
    MD = HERE / "REAUDIT_OPTIMIZED.md"
    MK_B, MK_E = "<!-- BATCH3-B12X-BEGIN -->", "<!-- BATCH3-B12X-END -->"
    L = [MK_B, "", f"### 15a. 第 12 批 #54 成交值集中度 → 0050 延長到 2025 起（{out['generated_at'][:16]}，`research/reaudit_batch12_ext2025.py`）", "",
         f"2025 起訊號改由官方全市場日檔（上市 MI_INDEX＋上櫃 otc，`fetch_official_daily_2025.py`）照原名冊（FinMind 快取 2,532 代號）重算，延長到 {out['signal_last']}"
         f"（2025 起 {out['n_days_2025']} 日，n<300 或 FMTQIK 涵蓋率不足篩掉 {out['n_filtered_2025']} 日）；0050 到 {out['data_end']}。"
         f"前 20 檔占比月均 2024-12 {out['top20_mean_2024_12']:.3f}、2025-01 {out['top20_mean_2025_01'] if out['top20_mean_2025_01'] is None else round(out['top20_mean_2025_01'], 3)}"
         "（2010／2013 共 494 個重疊日核對：官方日檔套原名冊與原 csv 平均差 −0.4pp）。不含 2025 起新上市股。參數用全期挑、2025 起分段**不是樣本外**；非投資建議。", "",
         "| 組 | 參數 | 全期 年化／MDD／Sh／Calmar | 2015～2024 年化／MDD | 2025 起 年化／MDD | 交易 |", "|---|---|---|---|---|---|"]
    for lab, k in (("第 12 批最佳組（同參數）", "same_params_extended"), ("延長後全期重挑", "rebest_extended"), ("延長後 ≤2× 重挑", "rebest_extended_L2")):
        x = out[k]
        if not x:
            L.append(f"| {lab} | — | | | | |")
            continue
        a, b = x["seg_2015_2024"] or {}, x["seg2025"] or {}
        L.append(f"| {lab} | {_fmt(x)} | {p(x['cagr'])}／{p(x['mdd'])}／{x['sharpe']:.2f}／{(x['calmar'] or 0):.2f}{'（越天條一）' if x['violates_survival'] else ''} | "
                 f"{p(a.get('cagr'))}／{p(a.get('mdd'))} | {p(b.get('cagr'))}／{p(b.get('mdd'))} | {x['trades']} |")
    bh, bl = out["buy_hold_0050"], out["buy_hold_same_leverage_no_timing"] or {}
    L.append(f"| 0050 買進持有（同期） | 1× | {p(bh['cagr'])}／{p(bh['mdd'])}／{bh['sharpe']:.2f}／{(bh['calmar'] or 0):.2f} | — | {p((bh.get('seg2025') or {}).get('cagr'))}／{p((bh.get('seg2025') or {}).get('mdd'))} | — |")
    L.append(f"| 同槓桿不擇時（同期） | {out['same_params_extended']['L']}× | {p(bl['cagr'])}／{p(bl['mdd'])}／{bl['sharpe']:.2f}／{(bl['calmar'] or 0):.2f} | "
             f"{p((bl.get('seg_sig') or {}).get('cagr'))}／{p((bl.get('seg_sig') or {}).get('mdd'))} | {p((bl.get('seg2025') or {}).get('cagr'))}／{p((bl.get('seg2025') or {}).get('mdd'))} | — |")
    L += ["", f"同參數那組 2025 起訊號實際減碼 {out['riskoff_days_2025_same_params']} 個交易日（第 12 批時 2025 起一律不擇時）。", "", MK_E]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if MK_B in txt:
        txt = txt[:txt.index(MK_B)] + block + txt[txt.index(MK_E) + len(MK_E):]
    else:
        anchor = "<!-- BATCH3-B12-END -->"
        txt = txt.replace(anchor, anchor + "\n\n" + block, 1) if anchor in txt else txt + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def update_candidates(out):
    p = HERE / "data" / "paper_opt_candidates.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        for c in d.get("candidates", []):
            if c.get("id") != CID:
                continue
            sm, b2 = out["same_params_extended"], out["rebest_extended_L2"]
            sg = sm["seg2025"] or {}
            c["from_2025_same_params"] = {"cagr": round(sg.get("cagr", 0), 4), "mdd": round(sg.get("mdd", 0), 4),
                                          "sharpe": round(sg.get("sharpe", 0), 4), "end": out["data_end"],
                                          "signal_last": out["signal_last"], "riskoff_days": out["riskoff_days_2025_same_params"]}
            c["full_period_same_params"] = {"cagr": round(sm["cagr"], 4), "mdd": round(sm["mdd"], 4), "sharpe": round(sm["sharpe"], 4)}
            c["violates_survival_extended"] = bool(sm["violates_survival"])
            c["extended_rebest_L2"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in b2.items()
                                       if k in ("series", "transform", "riskoff_when", "pct_threshold", "riskoff_exposure", "L", "stop", "cagr", "mdd", "sharpe")}
            c["notes"] = c.get("notes", "").split("；2026-11-10 訊號延長")[0] + f"；2026-11-10 訊號延長到 {out['signal_last']}（reaudit_batch12_ext2025.py）"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::候選檔更新失敗：{ex!r}")


if __name__ == "__main__":
    sys.exit(main() or 0)
