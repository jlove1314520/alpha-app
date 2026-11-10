"""先.一五五-3 第 16 批延長：外資／三大法人台指期淨未平倉 → 0050，訊號延長到 2025 起。

兩個子指令，分開兩個行程跑（run 會 import 第 16 批模組、那裡封鎖網路）：
- `python research/reaudit_batch16_ext2025.py fetch`：FinMind TaiwanFuturesInstitutionalInvestors（TX，2025-01-01～2026-11-09）1 次請求，
  只走 finmind_client._fetch（共用節流＋快取，已有快取就零請求）。未開抓前 calls_last_hour() ≥300 就每分鐘再看，
  REAUDIT_DEADLINE（epoch 秒）到就放棄；只送 1 次，可用 FETCH_MAX_USAGE 放寬門檻（2026-11-10 用 400）。
- `python research/reaudit_batch16_ext2025.py run`：零請求。舊快取（到 2024-12-31）＋新快取合併，
  第 16 批同一套網格（水準／21／63 日變化 × 方向 × 70/80/90 × 避險曝險 × 槓桿 × 止損）、觀察日之後第 2 個交易日才吃報酬，
  訊號一路用到快取最後一天（0050 本機到 2026-10-05）。核對：2024 底前合併序列與舊快取逐值差。
  結果寫 REAUDIT_OPTIMIZED.md 19a 節（BATCH3-B16X 標記間）、`research/data/reaudit_batch3_batch16_ext2025.json`，
  並更新候選檔 B16R- 條目的延長數字。
參數用全期挑、2025 起分段不是樣本外；非投資建議。
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DS, SID, S2, E2 = "TaiwanFuturesInstitutionalInvestors", "TX", "2025-01-01", "2026-11-09"
RAW = HERE / "data" / "raw"
OLD = RAW / f"{DS}__TX__2000-01-01__2024-12-31.parquet"
NEW = RAW / f"{DS}__TX__{S2}__{E2}.parquet"


def fetch():
    if NEW.exists():
        print(f"已有快取 {NEW.name}，零請求")
        return 0
    import finmind_client as f
    dl = float(os.environ.get("REAUDIT_DEADLINE", time.time() + 1200))
    while True:
        u = f.calls_last_hour()
        if u < int(os.environ.get("FETCH_MAX_USAGE", "300")):
            break
        if time.time() + 60 > dl:
            print(f"用量 {u}/hr ≥300 到截止仍未降，0 次請求")
            return 2
        print(f"用量 {u}/hr ≥300，一分鐘後再看", flush=True)
        time.sleep(60)
    df = f._fetch(DS, SID, S2, E2)
    print(f"送 1 次（用量 {u}/hr 時），{len(df)} 列，{df['date'].min()}～{df['date'].max()}")
    return 0


def run():
    sys.argv = [sys.argv[0]]
    import itertools

    import numpy as np
    import pandas as pd

    import reaudit_batch16_inst_regime as B16  # 封鎖網路；B10／B4／B5 一起帶入

    B10, B4, B5 = B16.B10, B16.B4, B16.B5
    old = pd.read_parquet(OLD)
    new = pd.read_parquet(NEW)
    df = pd.concat([old, new], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["date", "institutional_investors"], keep="first")
    df["net_oi"] = df["long_open_interest_balance_volume"].astype(float) - df["short_open_interest_balance_volume"].astype(float)
    sig_last = df["date"].max()
    # 核對：2024 底前用合併序列算的三大法人合計淨未平倉，與舊快取逐值差
    o = old.copy()
    o["date"] = pd.to_datetime(o["date"])
    o["net_oi"] = o["long_open_interest_balance_volume"].astype(float) - o["short_open_interest_balance_volume"].astype(float)
    t_old = o.groupby("date")["net_oi"].sum()
    t_new = df.groupby("date")["net_oi"].sum()
    j = t_old.index.intersection(t_new.index)
    diff = float(np.abs(t_old.loc[j] - t_new.loc[j]).max())
    inst_2025 = sorted(new["institutional_investors"].unique().tolist())
    B4.prog(f"延長：訊號到 {sig_last.date()}，2024 底前核對最大差 {diff}；2025 起法人別 {inst_2025}；0050 到 {B10.DATES.iloc[-1].date()}")

    B16.SIG_END = sig_last  # 訊號一路用到最後一天（之後才不擇時）
    f = df[df["institutional_investors"] == "外資"].set_index("date")["net_oi"]
    t = df.groupby("date")["net_oi"].sum()
    grid, i0 = B16._obs_family({"foreign_net_oi": f, "three_inst_net_oi": t})
    prev = {x["family"]: x for x in json.loads((HERE / "data" / "reaudit_batch3_batch16.json").read_text(encoding="utf-8"))["families"]}
    ob = prev["fut_inst_foreign_oi"]["best_by_calmar"]
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
        bhl = {**B4.stats(rr, tt, i0), "seg2025": B5.seg(rr, "2025-01-01", "2100-01-01"), "seg_sig": B5.seg(rr, "2019-01-01", "2025-01-01")}

    def pack(x):
        if x is None:
            return None
        o_ = {k: v for k, v in x.items() if k != "_r"}
        o_["seg_2019_2024"] = B5.seg(x["_r"], "2019-01-01", "2025-01-01")
        o_["seg2025"] = B5.seg(x["_r"], "2025-01-01", "2100-01-01")
        return o_

    # 2025 起訊號實際減碼天數（同參數那組）
    n_off_2025 = None
    for (params, e) in grid:
        if all(params[k] == ob[k] for k in keys):
            d = B10.DATES.reset_index(drop=True)
            m = (d >= pd.Timestamp("2025-01-01")).to_numpy()
            n_off_2025 = int((e[m] < 1).sum())
            break
    curve = B5.plot("b16x_fut_inst_foreign_oi", "三大法人台指期淨未平倉→0050（延長到 2025 起）", same["_r"], bh_r) if same else None
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(B10.DATES.iloc[-1].date()),
           "signal_last": str(sig_last.date()), "start": str(B10.DATES.iloc[i0].date()), "max_abs_diff_vs_old_2024": diff,
           "n_grid": len(rows), "n_violates": sum(x["violates_survival"] for x in rows),
           "old_best_signal_to_2024": ob, "same_params_extended": pack(same), "rebest_extended": pack(best),
           "rebest_extended_L2": pack(best2), "buy_hold_0050": {**bh, "seg2025": B5.seg(bh_r, "2025-01-01", "2100-01-01")},
           "buy_hold_same_leverage_no_timing": bhl, "riskoff_days_2025_same_params": n_off_2025, "curve_png": curve,
           "notes": "參數用全期挑、2025 起分段不是樣本外；觀察日之後第 2 個交易日才吃報酬；0050 含息；3× 超過台股融資上限只當參考；非投資建議。"}
    (HERE / "data" / "reaudit_batch3_batch16_ext2025.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
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
    MK_B, MK_E = "<!-- BATCH3-B16X-BEGIN -->", "<!-- BATCH3-B16X-END -->"
    L = [MK_B, "", f"### 19a. 第 16 批 三大法人台指期淨未平倉 → 0050 延長到 2025 起（{out['generated_at'][:16]}，`research/reaudit_batch16_ext2025.py`）", "",
         f"訊號 FinMind TaiwanFuturesInstitutionalInvestors（TX）2025 起補抓 1 次，延長到 {out['signal_last']}；0050 到 {out['data_end']}；"
         f"2024 底前合併序列與舊快取最大差 {out['max_abs_diff_vs_old_2024']}。參數用全期挑、2025 起分段**不是樣本外**；觀察日之後第 2 個交易日才吃報酬；非投資建議。", "",
         "| 組 | 參數 | 全期 年化／MDD／Sh／Calmar | 2019～2024 年化／MDD | 2025 起 年化／MDD | 交易 |", "|---|---|---|---|---|---|"]
    for lab, k in (("第 16 批最佳組（同參數）", "same_params_extended"), ("延長後全期重挑", "rebest_extended"), ("延長後 ≤2× 重挑", "rebest_extended_L2")):
        x = out[k]
        if not x:
            L.append(f"| {lab} | — | | | | |")
            continue
        a, b = x["seg_2019_2024"] or {}, x["seg2025"] or {}
        L.append(f"| {lab} | {_fmt(x)} | {p(x['cagr'])}／{p(x['mdd'])}／{x['sharpe']:.2f}／{(x['calmar'] or 0):.2f}{'（越天條一）' if x['violates_survival'] else ''} | "
                 f"{p(a.get('cagr'))}／{p(a.get('mdd'))} | {p(b.get('cagr'))}／{p(b.get('mdd'))} | {x['trades']} |")
    bh, bl = out["buy_hold_0050"], out["buy_hold_same_leverage_no_timing"] or {}
    L.append(f"| 0050 買進持有（同期） | 1× | {p(bh['cagr'])}／{p(bh['mdd'])}／{bh['sharpe']:.2f}／{(bh['calmar'] or 0):.2f} | — | {p((bh.get('seg2025') or {}).get('cagr'))}／{p((bh.get('seg2025') or {}).get('mdd'))} | — |")
    if bl:
        L.append(f"| 同槓桿不擇時（同期） | {out['same_params_extended']['L']}× | {p(bl['cagr'])}／{p(bl['mdd'])}／{bl['sharpe']:.2f}／{(bl['calmar'] or 0):.2f} | "
                 f"{p((bl.get('seg_sig') or {}).get('cagr'))}／{p((bl.get('seg_sig') or {}).get('mdd'))} | {p((bl.get('seg2025') or {}).get('cagr'))}／{p((bl.get('seg2025') or {}).get('mdd'))} | — |")
    L += ["", f"同參數那組 2025 起訊號實際減碼 {out['riskoff_days_2025_same_params']} 個交易日（第 16 批時 2025 起一律不擇時）。", "", MK_E]
    txt = MD.read_text(encoding="utf-8")
    block = "\n".join(L)
    if MK_B in txt:
        txt = txt[:txt.index(MK_B)] + block + txt[txt.index(MK_E) + len(MK_E):]
    else:
        anchor = "<!-- BATCH3-B16-END -->"
        txt = txt.replace(anchor, anchor + "\n\n" + block, 1) if anchor in txt else txt + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def update_candidates(out):
    p = HERE / "data" / "paper_opt_candidates.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        for c in d.get("candidates", []):
            if c.get("id") != "B16R-fut_inst_foreign_oi":
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
            c["notes"] = c.get("notes", "").split("；2026-11-10 訊號延長")[0] + f"；2026-11-10 訊號延長到 {out['signal_last']}（reaudit_batch16_ext2025.py）"
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::候選檔更新失敗：{ex!r}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    sys.exit(fetch() if cmd == "fetch" else (run() or 0))
