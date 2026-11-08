"""先.一五五-3 第二批第 13 批：台股跨年事件（var1018_v5 一月反轉、反向＝年底作帳延續），零新外部請求。

規則：12 月倒數第 k 個交易日收盤，用 #133 抽樣 236 檔（延長價格到 2026-10-02，`reaudit_ext2025_engine.load_extended()` 只呼叫）
算當年至今報酬（上一年最後收盤起），挑最差（反轉）或最好（延續）N 檔；下一個交易日收盤等權買進（當日漲 ≥9.5% 視為買不到、略過），
持有 H 個交易日後收盤賣。成本：買 手續費 0.1425%＋滑價 5bps；賣再加證交稅 0.3%（`validation.costs` 常數）。
其餘時間現金（收台灣無風險利率）。槓桿／組合止損沿用 batch2 overlay（空手日也照付融資成本，偏保守）。
事件一年一次（2015-12～2025-12 共 11 次）；樣本內最優化（描述性）、有存活者偏誤（今天回看的抽樣名冊）；非投資建議。
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
sys.argv = [sys.argv[0]]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import reaudit_batch6_portfolio as B6  # noqa: E402

S = B6.S
D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch13.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
MK_B, MK_E = "<!-- BATCH3-B13-BEGIN -->", "<!-- BATCH3-B13-END -->"


def main():
    px, gate, rf, end, miss = B6.load()
    px = px[px.index >= pd.Timestamp("2014-01-01")]
    dates = px.index
    R = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))
    Rv, Pv = R.to_numpy(), px.to_numpy()
    rfv = rf.reindex(dates).fillna(0.0).to_numpy()
    yr = dates.year.to_numpy()
    dec_idx = {y: np.where((yr == y) & (dates.month == 12))[0] for y in np.unique(yr)}
    rows = []
    i_start = int(np.argmax(dates >= pd.Timestamp("2014-12-01")))
    for side, k, n, h in itertools.product(("losers", "winners"), (1, 5, 10), (10, 20, 30), (5, 10, 21, 42)):
        base = rfv.copy()
        events, trades, ev_rets = 0, 0, []
        for y, di in dec_idx.items():
            if len(di) < k or y < 2014:
                continue
            i = di[-k]
            prev_end = np.where(yr == y - 1)[0]
            if len(prev_end) == 0:
                continue
            p0 = Pv[prev_end[-1]]
            ytd = Pv[i] / p0 - 1
            ok = np.where(~np.isnan(ytd) & ~np.isnan(Pv[i]))[0]
            if len(ok) < n or i + 1 >= len(dates):
                continue
            order = ok[np.argsort(ytd[ok])]
            pick = order[:n] if side == "losers" else order[::-1][:n]
            pick = pick[~(np.nan_to_num(Rv[i + 1, pick]) >= 0.095)]  # 進場日漲停附近買不到
            if len(pick) == 0:
                continue
            events += 1
            trades += len(pick)
            w = np.full(len(pick), 1.0 / len(pick))
            end_t = min(i + 1 + h, len(dates) - 1)
            v = 1.0 - B6.BUY_C
            base[i + 1] = -B6.BUY_C  # i+1 收盤買：當天只付買進成本
            for t in range(i + 2, end_t + 1):
                rt = np.nan_to_num(Rv[t, pick])
                day = float(w @ rt)
                w = w * (1 + rt) / (1 + day) if 1 + day > 0 else w
                base[t] = day - (B6.SELL_C if t == end_t else 0.0)
                v *= 1 + base[t]
            ev_rets.append(v - 1)
        r = base[i_start:]
        eq = np.cumprod(1 + r)
        d = dates[i_start:]
        rfa = rfv[i_start:]
        for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
            c, n_stop = S.overlay(eq, rfa, L, stop)
            s = B6.st(d, c)
            rows.append({"side": side, "dec_kth_last": k, "N": n, "hold_days": h, "L": L, "stop": stop, **s,
                         "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else None, "violates_survival": s["mdd"] < -0.5,
                         "events": events, "trades": trades,
                         "event_ret_median": float(np.median(ev_rets)) if ev_rets else None,
                         "event_win_rate": float(np.mean(np.array(ev_rets) > 0)) if ev_rets else None,
                         "seg_2025": B6.seg(d, c, "2025-01-01", "2026-12-31")})
    fams = []
    for side, title in (("losers", "var1018_v5 一月反轉（年底輸家）"), ("winners", "年底作帳延續（年底贏家，反向）")):
        rr = [x for x in rows if x["side"] == side]
        ok = [x for x in rr if not x["violates_survival"] and x["calmar"] is not None]
        best = max(ok, key=lambda x: x["calmar"]) if ok else None
        b1 = max([x for x in ok if x["L"] == 1.0 and x["stop"] is None], key=lambda x: x["calmar"], default=None)
        fams.append({"family": f"tw_january_{side}", "title": title, "n_grid": len(rr), "n_violates": sum(x["violates_survival"] for x in rr),
                     "best_by_calmar": best, "best_1x_nostop": b1})
        if best:
            print(f"{title}：{len(rr)} 格；最好 k={best['dec_kth_last']} N={best['N']} H={best['hold_days']} L={best['L']} stop={best['stop']} → "
                  f"{best['cagr']:+.1%}／{best['mdd']:.1%}／Sh {best['sharpe']:.2f}；事件 {best['events']} 次、中位數 {best['event_ret_median']:+.1%}、勝率 {best['event_win_rate']:.0%}；"
                  f"1× 不止損最好 {b1['cagr']:+.1%}／{b1['mdd']:.1%}（事件中位數 {b1['event_ret_median']:+.1%}）")
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "period": [str(dates[i_start].date()), str(dates[-1].date())],
           "families": fams, "notes": "每年 1 次事件、其餘時間現金，Calmar 因長期空手偏高；存活者偏誤（抽樣名冊）；樣本內最優化；非投資建議。"}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)


def render(out):
    pc = lambda x: "—" if x is None else f"{x:+.1%}"  # noqa: E731
    lines = [MK_B, "", "## 16. 第二批第 13 批 台股跨年事件（先.一五五-3 ③，`research/reaudit_batch13_january.py`，零新外部請求）", "",
             f"> 產生：{out['generated_at']}；期間 {out['period'][0]}～{out['period'][1]}。12 月倒數第 k 個交易日收盤挑 #133 抽樣 236 檔當年至今最差／最好 N 檔，"
             "下一交易日收盤等權買（漲 ≥9.5% 略過）、持有 H 日；成本照實（買 0.1425%＋5bps、賣再加證交稅 0.3%）；其餘時間收無風險利率；槓桿／止損同 batch2 overlay。"
             "**每年只 1 次事件（2015～2025 共 11 次），Calmar 因長期空手偏高、不和整年持有的族直接比**；有存活者偏誤；樣本內最優化；非投資建議。", "",
             "| 族 | 最好的一組（Calmar，MDD≤50%） | 年化 | MDD | Sharpe | 事件數 | 筆數 | 事件報酬中位數 | 事件勝率 | 2025 起 | 1× 不止損最好 | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b, b1 = f["best_by_calmar"], f["best_1x_nostop"]
        if not b:
            lines.append(f"| {f['family']} | 無合格組 |" + " |" * 10)
            continue
        s25 = b.get("seg_2025")
        lines.append(f"| {f['family']}（{f['title']}） | k={b['dec_kth_last']}，N={b['N']}，H={b['hold_days']}，L={b['L']:g}，stop={b['stop']} | {b['cagr']:+.1%} | {b['mdd']:.1%} | {b['sharpe']:.2f} | "
                     f"{b['events']} | {b['trades']} | {pc(b['event_ret_median'])} | {b['event_win_rate']:.0%} | {'—' if not s25 else pc(s25['cagr'])} | "
                     f"{b1['cagr']:+.1%}／{b1['mdd']:.1%}（k={b1['dec_kth_last']}，N={b1['N']}，H={b1['hold_days']}） | {f['n_violates']} |")
    lines += ["", "不進候選欄：每年 1 次、事件數 11 太少（候選門檻交易數 ≥20 指的是進出場次數）。", "", MK_E]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    txt = (txt.split(MK_B)[0] + block + txt.split(MK_E, 1)[1]) if MK_B in txt else txt.rstrip("\n") + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
