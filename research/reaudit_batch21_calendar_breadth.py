"""先.一五五-3 第二批第 21 批：結算日事件／廣度背離／除權息季節 → 0050 曝險（零新外部請求）。

族：
- fut_settlement_event_60：台指期結算日（HQ#60）前後窗口。2024 底前讀既有 `research/data/fut_settlement_dates_derived_tx.csv`
  （官方資料反推）；2025 起照期交所規則推算（每月第三個星期三，遇休市順延到下一個交易日，以 0050 交易日判定）。
  結算日是事先公布的日曆，第 i 日曝險在 i−1 收盤前就知道，不需要再位移。
- breadth_divergence_28：#28 廣度背離。236 檔（#133 抽樣）站上自身 MA 的比例＝廣度；0050 m 日報酬 >0 且廣度 c 日變化 <0
  → 背離，連續 d 日成立才算；t 收盤算、t+1 生效。
- exdiv_season_24：#24 除權息季節改成 0050 月份曝險（指定月份減碼或只在指定月份持有）。日曆事先已知、不位移。
HQ#49 隔夜／盤中分解：第 11 批（台指期盤別，#70 夜收→日開、#55 夜盤→日盤）已做同一機制，這批不重做。
模擬沿用第 4 批 run_sim／stats、第 5 批 seg／plot（只呼叫、不改核心檔）。
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

import reaudit_batch10_regime_more as B10  # noqa: E402  （帶入 B5／B4 與 236 檔延長價格）

B5, B4 = B10.B5, B10.B4
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch21.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B21-BEGIN -->", "<!-- BATCH3-B21-END -->"
DATES, N, R0, SHIFT, KS = B5.DATES, B5.N, B5.R0, B5.SHIFT, B5.KS
DT = pd.DatetimeIndex(DATES)


def settlement_index():
    """回傳結算日在 DATES 中的位置（排序、去重）與 2025 起推算的筆數。"""
    old = pd.to_datetime(pd.read_csv(D / "fut_settlement_dates_derived_tx.csv")["settlement_date"])
    sd = list(old[old <= "2024-12-31"])
    n_new = 0
    for y, m in itertools.product(range(2025, 2027), range(1, 13)):
        first = pd.Timestamp(y, m, 1)
        wed = first + pd.Timedelta(days=(2 - first.weekday()) % 7 + 14)
        if wed > DT[-1]:
            continue
        sd.append(wed)
        n_new += 1
    pos = sorted({int(DT.searchsorted(d)) for d in sd if DT[0] <= d <= DT[-1]})
    return np.array(pos), n_new


def fam_settlement():
    pos, _ = settlement_index()
    out = []
    for a, b, mode, k in itertools.product((1, 2, 3, 5), (0, 1, 2), ("避開窗口", "只持有窗口"), KS):
        w = np.zeros(N, dtype=bool)
        for s in pos:
            w[max(s - a + 1, 0):min(s + b + 1, N)] = True  # 從結算日前 a 日收盤持有到結算日後 b 日收盤
        e = np.where(w, k, 1.0) if mode == "避開窗口" else np.where(w, 1.0, k)
        out.append(({"pre_days": a, "post_days": b, "mode": mode, "other_exposure": k}, e))
    return out, max(int(pos[0]) - 5, 250)


def fam_breadth_div():
    R = B10._ret()
    px = (1 + R.fillna(0.0)).cumprod().where(R.notna() | R.shift(-1).notna())
    S = pd.Series(B5.PX, index=DT)
    out, i0 = [], N
    for ma in (100, 200):
        m_ = px.rolling(ma, min_periods=ma).mean()
        above = (px > m_).astype(float).where(m_.notna() & px.notna())
        cnt = above.notna().sum(axis=1)
        br = (above.sum(axis=1) / cnt.where(cnt >= 100)).reindex(DT)
        for mom, chg, d, k in itertools.product((20, 60), (20, 60), (1, 5), KS):
            flag = (S.pct_change(mom) > 0) & (br.diff(chg) < 0)
            if d > 1:
                flag = flag.rolling(d, min_periods=d).sum() >= d
            valid = br.diff(chg).notna().to_numpy()
            if valid.any():
                i0 = min(i0, int(np.argmax(valid)))
            e = SHIFT(np.where(valid & flag.to_numpy(), k, 1.0))
            out.append(({"ma": ma, "mom_days": mom, "breadth_chg_days": chg, "persist_days": d, "riskoff_exposure": k}, e))
    return out, max(i0 + 1, 250)


def fam_exdiv_season():
    mon = DT.month.to_numpy()
    sets = {"7-9 月": (7, 8, 9), "7-8 月": (7, 8), "8-9 月": (8, 9), "6-9 月": (6, 7, 8, 9), "5-6 月": (5, 6), "11-4 月": (11, 12, 1, 2, 3, 4)}
    out = []
    for (name, ms), mode, k in itertools.product(sets.items(), ("該月份減碼", "只在該月份持有"), KS):
        inm = np.isin(mon, ms)
        e = np.where(inm, k, 1.0) if mode == "該月份減碼" else np.where(inm, 1.0, k)
        out.append(({"months": name, "mode": mode, "other_exposure": k}, e))
    return out, 250


FAMS = [
    ("fut_settlement_event_60", "HQ#60 台指期結算日前後窗口 → 0050", fam_settlement),
    ("breadth_divergence_28", "#28 廣度背離（指數漲、廣度縮）→ 0050", fam_breadth_div),
    ("exdiv_season_24", "#24 除權息季節（月份曝險）→ 0050", fam_exdiv_season),
]


def main():
    B4.prog(f"第 21 批開始；0050 {DATES.iloc[0].date()}～{DATES.iloc[-1].date()}")
    pos, n_new = settlement_index()
    B4.prog(f"結算日 {len(pos)} 個（2025 起推算 {n_new} 個）")
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
            B5.I0 = i0
            f["best_seg_2015_2024"] = B5.seg(best["_r"], "2015-01-01", "2025-01-01")
            f["best_seg_2025_on"] = B5.seg(best["_r"], "2025-01-01", "2100-01-01")
            f["bh_seg_2025_on"] = B5.seg(bh_r, "2025-01-01", "2100-01-01")
            f["curve_png"] = B5.plot("b21_" + fid, title, best["_r"], bh_r)
            B4.prog(f"{fid} {len(rows)} 格（{f['start']} 起）；最好 {B4._fmt(clean(best))} → {best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}／Calmar {best['calmar']:.2f}；"
                    f"2025 起 {f['best_seg_2025_on']['cagr']:+.1%}／{f['best_seg_2025_on']['mdd']:.1%}；同期 0050 {bh['cagr']:+.1%}／{bh['mdd']:.1%}；"
                    f"同槓桿不擇時 {bhl['cagr']:+.1%}／{bhl['mdd']:.1%}")
        fams.append(f)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "data_end": str(DATES.iloc[-1].date()), "families": fams,
           "n_settlement": len(pos), "n_settlement_2025_derived": n_new,
           "notes": "樣本內最優化（描述性，全期含 2025 起一起挑參數，2025 起分段不是樣本外）；結算日／月份是事先已知的日曆、不位移；廣度背離 t 收盤算、t+1 生效；0050 含息；3× 超過台股融資上限只當參考。"}
    render(out)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_candidates(out)
    B4.prog(f"寫入 {OUT_JSON}")


def _calmar(x):
    return None if not x or x.get("calmar") is None else x["calmar"]


def render(out):
    p = B5._p
    lines = [MK_B, "", "## 24. 第二批第 21 批 結算日事件／廣度背離／除權息季節 → 0050（先.一五五-3 ③，`research/reaudit_batch21_calendar_breadth.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；到 {out['data_end']}（含 2025 起）。結算日 {out['n_settlement']} 個（2024 底前讀官方反推檔、2025 起照「第三個星期三、遇休市順延」推算 {out['n_settlement_2025_derived']} 個）；"
             "結算日與月份是事先已知的日曆、不位移；廣度背離用 #133 抽樣 236 檔（今天回看的名冊，有存活者偏誤），t 收盤算、t+1 生效。"
             "× 槓桿 1/1.5/2/3 × 組合止損 不設/10/20/30%；0050 含息、成本照實。**參數用全期（含 2025 起）一起挑，2025 起分段不是樣本外**；多重比較只當參考；3× 超過融資上限只當參考。"
             "HQ#49 隔夜／盤中分解已由第 11 批（台指期盤別）涵蓋，不重做。非投資建議。", "",
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
    lines += ["", "「約第幾名」＝綜合分數（年化÷|MDD|）跟第 0 節 18 族粗比（期間不同，只當粗排）。交易次數＝減碼／出場次數。"
              "候選門檻（沿用第 12 批起）：約前 10 名、交易 ≥20、Calmar 同時贏同期 0050 與同槓桿不擇時。曲線 `research/data/reaudit_curves/batch3_b5_b21_*.png`（本機）。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if MK_B in txt:
        txt = txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates(out):
    """約前 10 名、交易數 ≥20、Calmar 贏同期 0050 與同槓桿不擇時 → 寫進候選欄（id 前綴 B21R-，重跑只換自己的條目）。"""
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B21R-")]
    new = []
    for f in out["families"]:
        b = f.get("best_by_calmar")
        if not b or f.get("rank", 99) > 10 or (b.get("trades") or 0) < 20:
            continue
        if b["calmar"] <= (_calmar(f["buy_hold_0050_same_period"]) or 0) or b["calmar"] <= (_calmar(f["buy_hold_same_leverage_no_timing"]) or 0):
            continue
        note = ["樣本內最優化（偏樂觀，參數用全期含 2025 起挑）", "→0050"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        new.append({"id": f"B21R-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 21 批",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": f["rank"],
                    "params": {k: v for k, v in b.items() if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")},
                    "backtest_period": f"{f['start']}～{f['end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in (f.get("best_seg_2015_2024") or {}).items()},
                    "from_2025_same_params": {k: round(v, 4) for k, v in (f.get("best_seg_2025_on") or {}).items()} or None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": None if b["win_rate"] is None else round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c.get("rank_in_table", 99))
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    B4.prog(f"候選欄第 21 批 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    main()
