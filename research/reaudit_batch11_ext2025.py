"""先.一五五-3 第二批第 11 批延長：台指期盤別／跳空 4 族延長到 2025 起。

子指令：
- `fetch`：FinMind TaiwanFuturesDaily TX 2025-01-01～2026-11-09，**1 次請求**，只走 finmind_client._fetch（共用節流＋快取，
  已有快取就零請求）。calls_last_hour() ≥ FETCH_MAX_USAGE（預設 300、上限 450）就不送。
- `run`：零請求。把本機全歷史快取（2000～2024）與 2025 起快取接起來，近月連續邏輯照 continuous_contract.build_continuous_series
  （只呼叫，透過替換該模組的 load_dev 讀兩份快取），訊號／成本／掃格照 reaudit_batch11_tx_session.py 逐字沿用。
  輸出：第 11 批挑出的同參數「全期／2015～2024 段／2025 起段」＋全期重挑；寫 REAUDIT_OPTIMIZED.md 14a 節（BATCH3-B11X 標記間）、
  明細 research/data/reaudit_batch3_batch11_ext2025.json。核心檔不改。樣本內描述性；非投資建議。
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import finmind_client as F  # noqa: E402

DS, SID = "TaiwanFuturesDaily", "TX"
EXT_S, EXT_E = "2025-01-01", "2026-11-09"
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch11_ext2025.json"
B11_JSON = D / "reaudit_batch3_batch11.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B11X-BEGIN -->", "<!-- BATCH3-B11X-END -->"


def fetch():
    cap = min(int(os.environ.get("FETCH_MAX_USAGE", "300")), 450)
    if F._cache_path(DS, SID, EXT_S, EXT_E).exists():
        print("已有快取，零請求")
        return
    u = F.calls_last_hour()
    if u >= cap:
        print(f"FinMind 過去一小時 {u} 次 ≥ {cap}，不送")
        return
    print(f"送 1 次（用量 {u}/hr）")
    df = F._fetch(DS, SID, EXT_S, EXT_E)
    print(f"回 {len(df)} 列，日期 {df['date'].min()}～{df['date'].max()}")


def _patched_load_dev(dataset, data_id, start_date=None, end_date=None, **kw):
    assert dataset == DS and data_id == SID
    old = F._fetch(DS, SID, "2000-01-01", "2024-12-31")  # 本機快取，零請求
    p = F._cache_path(DS, SID, EXT_S, EXT_E)
    if not p.exists():
        raise SystemExit("2025 起快取不存在，先跑 fetch")
    new = F._fetch(DS, SID, EXT_S, EXT_E)
    new = new[pd.to_datetime(new["date"]) > pd.to_datetime(old["date"]).max()]
    return pd.concat([old, new[old.columns.intersection(new.columns)]], ignore_index=True)


def _seg(r, dts, lo, hi, stats):
    m = (dts >= pd.Timestamp(lo)) & (dts <= pd.Timestamp(hi))
    if m.sum() < 20:
        return None
    s = stats(r[m], dts[m], 0, 0)
    return {k: s[k] for k in ("cagr", "mdd", "sharpe", "calmar")}


def run():
    import continuous_contract as CC
    CC.load_dev = _patched_load_dev
    import fut_cheap_gate as G
    import reaudit_batch11_tx_session as B
    stats = B.stats
    s = G._load_series()
    m = G._load_session_pair(s)
    # 核對：2024 底前近月原始收盤與舊序列一致（調整比率會因後續轉倉改變，只比原始價）
    CC.load_dev = lambda *a, **k: F._fetch(DS, SID, "2000-01-01", "2024-12-31")
    s_old, _ = CC.build_continuous_series()
    CC.load_dev = _patched_load_dev  # add_raw_gaps 會再讀夜盤，要用延長版
    chk = s_old[["date", "close", "contract_date"]].merge(s[["date", "close", "contract_date"]], on="date", suffixes=("_o", "_n"))
    n_diff = int(((chk["close_o"] - chk["close_n"]).abs() > 1e-9).sum() + (chk["contract_date_o"] != chk["contract_date_n"]).sum())
    print(f"核對 2024 底前日盤近月原始收盤／合約：{len(chk)} 日，不一致 {n_diff}")
    m["prev_day_close"] = m["adj_close"].shift(1)
    m["prev_day_ret"] = m["day_ret"].shift(1)
    B.add_raw_gaps(m)  # 跳空用原始價、同一合約才算（第 11 批 2026-11-10 修正，同一函式）
    raw = s[["date", "close"]].rename(columns={"close": "raw_close"})
    m = m.merge(raw, on="date", how="left")
    lvl = m["raw_close"].shift(1).bfill()
    cost_rt = (2 * (B.TAX + B.FEE) + 2 * B.SLIP_PT / lvl.to_numpy())
    keep = m[["prev_day_close", "prev_day_ret"]].notna().all(axis=1).to_numpy()
    m = m[keep].reset_index(drop=True)
    cost_rt = cost_rt[keep]
    dts = pd.DatetimeIndex(pd.to_datetime(m["date"]))
    prev = {f["family"]: f for f in json.loads(B11_JSON.read_text(encoding="utf-8"))["families"]}
    fams = {
        "HQ#55_night_to_day": ("夜盤 T 報酬方向 → 日盤 T", m["night_ret"], m["day_ret"]),
        "HQ#65_night_gap": ("日收→夜開跳空方向 → 夜盤 T", m["gap_night"], m["night_ret"]),
        "HQ#70_day_gap": ("夜收→日開跳空方向 → 日盤 T", m["gap_day"], m["day_ret"]),
        "day_to_night": ("日盤 T-1 報酬方向 → 夜盤 T", m["prev_day_ret"], m["night_ret"]),
    }
    out_f = []
    for fid, (title, sig, tr) in fams.items():
        sig, tr = sig.to_numpy(), tr.to_numpy()
        a = pd.Series(np.abs(sig))
        rows = []
        for q in B.QS:
            thr = a.expanding(min_periods=60).quantile(q).shift(1).to_numpy() if q > 0 else np.zeros(len(a))
            for d_, L in itertools.product((1, -1), B.LEVS):
                pos = np.where((np.abs(sig) > np.nan_to_num(thr, nan=np.inf)) & (sig != 0), d_ * np.sign(sig), 0.0)
                net = pos * tr - np.abs(pos) * cost_rt
                r = L * net
                n = int((pos != 0).sum())
                w = int((net > 0)[pos != 0].sum())
                rows.append({"direction": "順勢" if d_ == 1 else "反向", "abs_signal_pctile": q, "L": L,
                             **stats(r, dts, n, w),
                             "seg_2017_2024": _seg(r, dts, "2000-01-01", "2024-12-31", stats),
                             "seg_2025_on": _seg(r, dts, "2025-01-01", "2099-12-31", stats)})
        clean = lambda x: None if x is None else {k: v for k, v in x.items()}  # noqa: E731
        pb = (prev.get(fid) or {}).get("best_by_calmar")
        same = None
        if pb:
            same = next(x for x in rows if x["direction"] == pb["direction"] and x["abs_signal_pctile"] == pb["abs_signal_pctile"] and x["L"] == pb["L"])
        ok = [x for x in rows if not x["violates_survival"] and x["calmar"] is not None and x["cagr"] > 0]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        ok2 = [x for x in ok if x["L"] <= 2.0]
        best2 = max(ok2, key=lambda x: x["calmar"]) if ok2 else None
        f = {"family": fid, "title": title, "start": str(dts[0].date()), "end": str(dts[-1].date()), "n_grid": len(rows),
             "n_violates": sum(x["violates_survival"] for x in rows), "batch11_params": None if not pb else
             {k: pb[k] for k in ("direction", "abs_signal_pctile", "L")}, "same_params": clean(same),
             "rebest_full": clean(best), "rebest_full_L2": clean(best2), "avg_cost_roundtrip_pct": float(np.mean(cost_rt) * 100)}
        def _s(x):
            return "—" if not x else f"{x['cagr']:+.1%}／{x['mdd']:.1%}"
        print(f"{fid}: 同參數全期 {_s(same)}、2025 起 {_s(same and same['seg_2025_on'])}；重挑 "
              + ("無正報酬組" if not best else f"{best['direction']} {best['abs_signal_pctile']} {best['L']:g}× {_s(best)}（2025 起 {_s(best['seg_2025_on'])}）"))
        out_f.append(f)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "check_pre2025_mismatch": n_diff,
           "check_pre2025_days": len(chk), "families": out_f}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def _p(x):
    return "—" if not x else f"{x['cagr']:+.1%}／{x['mdd']:.1%}"


def render(out):
    lines = [MK_B, "", "### 14a. 第 11 批延長到 2025 起（`research/reaudit_batch11_ext2025.py`，FinMind 1 次請求）", "",
             f"> 產生：{out['generated_at']}；TX 近月連續＝本機 2000～2024 快取＋2025-01-01～2026-11-09 新快取（照 continuous_contract 只呼叫）。"
             f"2024 底前日盤近月原始收盤／合約核對 {out['check_pre2025_days']} 日、不一致 {out['check_pre2025_mismatch']}。"
             "訊號、成本、掃格照第 11 批逐字沿用；全期重挑是用含 2025 的全期挑的，2025 起分段不是樣本外。非投資建議。", "",
             "| 族 | 期間 | 第 11 批參數 | 同參數全期 | 2024 底前 | 2025 起 | 全期重挑 | 重挑 2025 起 | 全期重挑（≤2×） | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        bp, sm, rb = f["batch11_params"], f["same_params"], f["rebest_full"]
        bps = "扣成本後無正報酬組" if not bp else f"{bp['direction']}／>{bp['abs_signal_pctile']:.0%} 分位／{bp['L']:g}×"
        rbs = "無正報酬組" if not rb else f"{rb['direction']}／>{rb['abs_signal_pctile']:.0%}／{rb['L']:g}× {_p(rb)}（Sh {rb['sharpe']:.2f}，{rb['trades']} 筆）"
        r2 = f["rebest_full_L2"]
        r2s = "—" if not r2 else f"{r2['direction']}／>{r2['abs_signal_pctile']:.0%}／{r2['L']:g}× {_p(r2)}（2025 起 {_p(r2['seg_2025_on'])}）"
        lines.append(f"| {f['family']}（{f['title']}） | {f['start']}～{f['end']} | {bps} | {_p(sm)} | {_p(sm and sm['seg_2017_2024'])} | "
                     f"{_p(sm and sm['seg_2025_on'])} | {rbs} | {_p(rb and rb['seg_2025_on'])} | {r2s} | {f['n_violates']} |")
    lines += ["", "⚠️ 2026-11-10 修正：第 11 批第一版的兩個跳空訊號（#65／#70）用日盤、夜盤各自還原後的價格相除，兩條序列轉倉比率不同、"
              "累積後還原跳空中位數逐年 −2%～−5%（原始價約 0），訊號被假位移主導；已改成原始價、同一合約才算（`add_raw_gaps`），第 14 節同步重跑。"
              "#70 修正後由 +0.8% 變成 3× +27.6%（2017～2024），要注意：進場價＝定義訊號的日盤開盤價本身（開盤撮合價，滑價只計 2 點），紙上要以實際開盤後成交驗證。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        anchor = "<!-- BATCH3-B11-END -->"
        txt = txt.replace(anchor, anchor + "\n\n" + block, 1)
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
