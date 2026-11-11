# -*- coding: utf-8 -*-
"""先.一五九-1（收件匣 043）紙上優化軌：個股因子 S1～S4（＋S1 1.5×／2×、S1＋S3＋F14 各三分之一）每日產生器——零外部請求。

策略（照 REAUDIT_OPTIMIZED.md §5a「舊最優」＝2024 底前挑的那一格，2025 起不重調；參數格式＝換股日數_大盤閘門_N_個股停損_方向）：
  S1    f_revenue_surprise（月營收驚喜 SUE）     21_0_20_0.15_+1，1×，組合停損 10%
  S1x15 同 S1 引擎，1.5×；S1x2 同 S1 引擎，2×（收件匣 043 加碼版；⚠️ 回測 2025 起反而比 1× 差，見 bt_stock.json）
  S2    f_short_term_reversal_1w（−5 日報酬）   21_0_30_1.0_−1，3×，組合停損 10%（方向 −1＝買「因子值低」＝近 5 日漲最多的 30 檔）
  S3    f_ma_breakout（均線突破×量比）          21_0_10_0.15_+1，1.5×，組合停損 10%
  S4    f_foreign_streak（外資連買強度）        21_1_30_0.15_+1（大盤 >200 日均線才換股進場），1×，組合停損 20%
  S1S3F14  S1、S3、F14（paper_opt_f14.py 原版 1×）起跑日各 1/3，之後不再平衡。
構造（跟回測同一套程式，不重寫）：
  - 底層：直接呼叫 research/backtest/engine.py run_backtest()（訊號 t 收盤、t+1 收盤成交、漲跌停鎖住順延、全成本、
    ma150 跌破出場、個股停損、複利額度）；宇宙＝#133 抽樣 236 檔扣掉回測 2025 起段就不給分數的 71 檔（stock_universe.json）。
    每次執行都從起跑日 START 重跑到最新交易日（引擎只往回看，同一份資料重跑結果相同），帳本只追加還沒寫過的日子。
  - 帳戶層：reaudit_optimized_batch2_sector.overlay()（L 倍、融資 6.5%/年、組合停損後冷卻 21 個交易日領無風險利率）。
  - 因子：公式照 reaudit_batch3_ext2025._factor_series／reaudit_ext2025_fin_factors（=factors.py 原公式）。
與回測口徑的差異（照實揭露）：
  ① 價格：回測 2025 起＝FinMind 快取「漲跌」欄還原；紙上＝模擬 I 回看期官方日檔＋data/price_history 還原收盤比值（同 F12／F14／F17），
     除權息日 0 報酬已用 paper_opt_exright_fix 補正。
  ② 月營收：回測有 FinMind create_time 就用實際公告日；紙上一律「次月 10 日」可得（官方檔沒有公告時間），
     來源＝2024 以前 FinMind 快取＋data/revenue_backfill.json＋fundamentals.json（同 F17）。官方檔更新落後時，換股日只用得到更早的月份。
  ③ 外資買賣超：本機 FinMind 快取（回測同一份，到 2026-09-30）之後接 data/institutional_history.json foreign_lots（T86／TPEx，張×1000）；
     9 月重疊日兩邊只差 0.1 張四捨五入。往後 institutional_history 若漏某天，那天當 0（同回測 fillna(0)），連買天數會被斷一次。
  ④ 大盤閘門：回測＝FinMind 加權指數；紙上＝paper_opt_f12 的 taiex_closes.json（官方收盤，最早一段用 0050 往前接）。
  ⑤ 換股相位：回測從 2015-01-01 起每 21 個交易日；紙上從起跑日 2026-11-11 起算（相位任意，照實揭露）。
  ⑥ 無風險利率（停損冷卻期）：回測＝央行逐日；紙上＝data/rf_monthly.json 最新一個月的常數。
輸出（append-only，只在本機）：research/data/paper_opt/ledger_{S1,S1x15,S1x2,S2,S3,S4,S1S3F14}.jsonl、stock_bars.json、state_stock.json。
用法：python research/paper_opt_stock.py [--probe] [--start YYYY-MM-DD（只給自測用）]
非投資建議。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402
import paper_opt_f14 as F14  # noqa: E402

OUT = F12.OUT
START = "2026-11-11"
UNIV = OUT / "stock_universe.json"
STATE = OUT / "state_stock.json"
BARS = OUT / "stock_bars.json"
INST = F12.DATA / "institutional_history.json"

# 引擎格：id -> (因子, 換股日數, 大盤閘門, N, 個股停損(1.0＝不設), 方向)
ENGINES = {
    "S1": ("f_revenue_surprise", 21, False, 20, 0.15, 1),
    "S2": ("f_short_term_reversal_1w", 21, False, 30, 1.0, -1),
    "S3": ("f_ma_breakout", 21, False, 10, 0.15, 1),
    "S4": ("f_foreign_streak", 21, True, 30, 0.15, 1),
}
# 帳戶：id -> (引擎, L, 組合停損)
ACCTS = {
    "S1": ("S1", 1.0, 0.1), "S1x15": ("S1", 1.5, 0.1), "S1x2": ("S1", 2.0, 0.1),
    "S2": ("S2", 3.0, 0.1), "S3": ("S3", 1.5, 0.1), "S4": ("S4", 1.0, 0.2),
}
COMBO = ("S1S3F14", ["S1", "S3", "F14"])


# ------------------------------------------------------------------ 資料
def universe() -> list[str]:
    u = F12._rj(UNIV, {})
    if not u.get("ids"):
        raise SystemExit("找不到 stock_universe.json，先跑 python research/paper_opt_stock_seed.py")
    ex = set(u.get("excluded_no_2025_price") or [])
    return [s for s in u["ids"] if s not in ex]


def foreign_shares(ids: list[str]) -> dict[str, dict[str, float]]:
    """{代號: {YYYY-MM-DD: 外資買賣超（股）}}。
    先用本機 FinMind 快取（TaiwanStockInstitutionalInvestorsBuySell Foreign_Investor，回測同一份，到 2026-09-30），
    之後的日子用 data/institutional_history.json（T86／TPEx 外資，單位張×1000；2026-08-26 起累積）。
    兩邊在 9 月重疊日實測只差四捨五入（0.1 張）；institutional_history 缺 09-10、09-15 兩天，靠 FinMind 補上，連買天數才不會被假斷。"""
    import reaudit_ext2025_fin_factors as R
    d = F12._rj(INST, {})
    ser = d.get("series") or {}
    out: dict[str, dict[str, float]] = {}
    for sid in ids:
        m: dict[str, float] = {}
        try:
            w = R._inst_wide(sid)
            m = {str(k)[:10]: float(v) for k, v in zip(w["date"], w["foreign_net"])}
        except Exception as e:  # noqa: BLE001 — 單檔讀不到只用 T86
            print(f"[warn] {sid} FinMind 法人快取讀不到：{e}")
        last = max(m) if m else ""
        for k, v in (ser.get(sid) or {}).items():
            dd = f"{k[:4]}-{k[4:6]}-{k[6:]}"
            if dd > last and v and v[0] is not None:
                m[dd] = float(v[0]) * 1000.0
        out[sid] = m
    return out


def frames(ids: list[str], bars: dict, fx: dict, revf: dict) -> dict[str, pd.DataFrame]:
    import factors as F
    out = {}
    for sid in ids:
        b = bars.get(sid) or {}
        if len(b) < 2:
            continue
        ds, lv = F12.adj_levels({d: v[:5] for d, v in b.items()})
        num = lambda i: [float(b[d][i]) if b[d][i] is not None else np.nan for d in ds]  # noqa: E731
        d = pd.DataFrame({"date": ds, "open": num(0), "max": num(1), "min": num(2), "close": num(3), "adj_close": lv,
                          "Trading_Volume": num(5), "Trading_money": num(6)})
        px, r = d["adj_close"].astype(float), d["adj_close"].astype(float).pct_change()
        d["ma150"] = px.rolling(150, min_periods=150).mean()  # 引擎第一層出場讀這欄（同 reaudit_batch3_factors.prep）
        d["f_short_term_reversal_1w"] = -(px / px.shift(F.SHORT_TERM_REVERSAL_1W_WINDOW) - 1)
        ma = px.rolling(F.MA_WINDOW, min_periods=F.MA_WINDOW).mean()
        v = d["Trading_Volume"].astype(float)
        d["f_ma_breakout"] = (px / ma - 1) * (v.rolling(F.VOL_SHORT_WINDOW, min_periods=F.VOL_SHORT_WINDOW).mean()
                                              / v.rolling(F.VOL_LONG_WINDOW, min_periods=F.VOL_LONG_WINDOW).mean())
        net = d["date"].map(fx.get(sid, {})).fillna(0.0).astype(float).to_numpy()
        avg20 = v.rolling(F.FOREIGN_STREAK_VOL_WINDOW, min_periods=1).mean().to_numpy()
        d["f_foreign_streak"] = F._foreign_streak_strength(net, avg20)
        orig = F.month_revenue_pit
        F.month_revenue_pit = lambda *_a, _r=revf.get(sid): (_r.copy() if _r is not None else pd.DataFrame())
        try:
            d = F._asof_join(d, F._revenue_surprise_sue(sid, ""), "revenue_sue", "f_revenue_surprise")
        except Exception:  # noqa: BLE001 — 沒營收資料＝這檔沒有 S1 分數
            d["f_revenue_surprise"] = np.nan
        finally:
            F.month_revenue_pit = orig
        del r
        out[sid] = d
    return out


def market_frame(calendar: list[str]) -> pd.DataFrame:
    cl = F12._rj(F12.TAIEX, {}).get("closes") or {}
    s = pd.Series({d: float(v[0]) for d, v in cl.items()}).sort_index()
    ma = s.rolling(200, min_periods=200).mean()
    gate = (s > ma)
    m = pd.DataFrame({"date": calendar})
    m["close"] = m["date"].map(s)
    m["gate"] = m["date"].map(gate).fillna(False).astype(bool)  # 缺加權收盤＝閘門關（不進場）〔自行裁量〕
    return m


def make_fn(fac: str, frames_: dict, gate_on: bool, gate_dates: set, direction: int):
    look = {sid: dict(zip(d["date"], d[fac])) for sid, d in frames_.items()}

    def fn(price_data, as_of, market_df):
        a = str(as_of)[:10]
        if gate_on and a not in gate_dates:
            return {}
        sc = {}
        for sid in price_data:
            v = look.get(sid, {}).get(a)
            if v is not None and v == v:
                sc[sid] = direction * float(v)
        return sc
    return fn


# ------------------------------------------------------------------ 引擎＋帳戶層
def run_engine(eid: str, fr: dict, mk: pd.DataFrame, start: str, end: str):
    from backtest.engine import BacktestConfig, run_backtest
    fac, rb, g, n, pstop, dr = ENGINES[eid]
    gate_dates = set(mk.loc[mk["gate"], "date"])
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=n, rebalance_every_n_days=rb,
                         stop_loss_pct=pstop, book_name=f"paper_opt_{eid}")
    fn = make_fn(fac, fr, g, gate_dates, dr)
    res = run_backtest(fn, fr, mk, cfg)
    return res, fn


def holdings_by_day(trades: pd.DataFrame, days: list[str]) -> dict[str, int]:
    held, out = set(), {}
    by = {d: g for d, g in trades.groupby("date")} if len(trades) else {}
    for d in days:
        if d in by:
            for _, t in by[d].iterrows():
                if t["side"] == "buy":
                    held.add(t["stock_id"])
                else:
                    held.discard(t["stock_id"])
        out[d] = len(held)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    import paper_opt_f17 as F17
    import reaudit_optimized_batch2_sector as S
    ids = universe()
    F14.BARS = BARS
    bars, calendar = F14.build_bars(ids)
    F17.REV_CACHE = OUT / "stock_rev_pre2025.json"
    fr = frames(ids, bars, foreign_shares(ids), F17.rev_frames(ids))
    mk = market_frame(calendar)
    day = calendar[-1]
    if a.probe:
        cov = {e: sum(1 for d in fr.values() if not d.empty and d["date"].iloc[-1] == day and d[ENGINES[e][0]].iloc[-1] == d[ENGINES[e][0]].iloc[-1])
               for e in ENGINES}
        print(f"宇宙 {len(ids)} 檔、有日線 {len(fr)} 檔；最新交易日 {day}；大盤閘門 {'開' if bool(mk['gate'].iloc[-1]) else '關'}；各因子當日有值：{cov}")
        for e, (fac, rb, g, n, pstop, dr) in ENGINES.items():
            sc = sorted(((sid, dr * float(d[fac].iloc[-1])) for sid, d in fr.items()
                         if d["date"].iloc[-1] == day and d[fac].iloc[-1] == d[fac].iloc[-1]), key=lambda x: -x[1])[:n]
            print(f"{e} {fac} 前 {n}：{[s for s, _ in sc]}")
        return 0
    st = F12._rj(STATE, None) or {"start": a.start, "last": {}}
    if a.start != START:
        st["start"] = a.start
    start = st["start"]
    if day < start:
        print(f"最新交易日 {day} 早於起跑日 {start}，不記帳")
        return 0
    days = [d for d in calendar if d >= start]
    rf = F12.rf_daily()
    eq1x, logs = {}, {}
    for eid in ENGINES:
        res, fn = run_engine(eid, fr, mk, start, day)
        ec = res.equity_curve
        eq1x[eid] = ec["equity"].to_numpy(float) / res.config.initial_capital
        tr = res.trades
        hold = holdings_by_day(tr, days)
        fills = {d: [{"sid": t["stock_id"], "side": t["side"], "px_adj": round(float(t["price"]), 4), "reason": t["note"]}
                     for _, t in g.iterrows()] for d, g in tr.groupby("date")} if len(tr) else {}
        rb_days = {d for i, d in enumerate(days) if i % ENGINES[eid][1] == 0}
        top = {}
        for d in rb_days:
            sc = fn(fr, d, mk)
            top[d] = [s for s, _ in sorted(sc.items(), key=lambda kv: -kv[1])[:ENGINES[eid][3]]]
        logs[eid] = (hold, fills, top)
    done = {}
    for aid, (eid, L, stop) in ACCTS.items():
        e = eq1x[eid]
        curve, _ = S.overlay(e / e[0], np.full(len(e), rf), L, stop)
        lp = OUT / f"ledger_{aid}.jsonl"
        last = st["last"].get(aid)
        hold, fills, top = logs[eid]
        n = 0
        with lp.open("a", encoding="utf-8") as f:
            for i, d in enumerate(days):
                if last and d <= last:
                    continue
                r = curve[i] / curve[i - 1] - 1.0 if i > 0 else 0.0
                r1 = e[i] / e[i - 1] - 1.0 if i > 0 else 0.0
                rec = {"date": d, "ret": round(float(r), 8), "ret_1x": round(float(r1), 8), "equity": round(float(curve[i]) * F12.INIT, 2),
                       "L": L, "n_holdings": hold.get(d, 0), "fills": fills.get(d, [])}
                if d in top:
                    rec["rebalance_top"] = top[d]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                st["last"][aid] = d
                n += 1
        done[aid] = n
    # 組合 S1＋S3＋F14：起跑日各 1/3、不再平衡
    cid, mem = COMBO
    rets = {}
    for m in mem:
        lp = OUT / f"ledger_{m}.jsonl"
        rows = [json.loads(x) for x in lp.read_text(encoding="utf-8").splitlines()] if lp.exists() else []
        rets[m] = {r["date"]: float(r["ret"]) for r in rows if r["date"] >= start}
    common = [d for d in days if all(d in rets[m] for m in mem)]
    lv = {m: 1.0 for m in mem}
    prev = 1.0
    n = 0
    with (OUT / f"ledger_{cid}.jsonl").open("a", encoding="utf-8") as f:
        for d in common:
            for m in mem:
                lv[m] *= 1.0 + rets[m][d]
            v = sum(lv.values()) / len(mem)
            if not st["last"].get(cid) or d > st["last"][cid]:
                f.write(json.dumps({"date": d, "ret": round(v / prev - 1.0, 8), "equity": round(v * F12.INIT, 2),
                                    "members": {m: round(lv[m] / v / len(mem), 4) for m in mem}}, ensure_ascii=False) + "\n")
                st["last"][cid] = d
                n += 1
            prev = v
    done[cid] = n
    F12._wj(STATE, st)
    print(f"起跑 {start}，最新 {day}；本次寫入：{done}；大盤閘門 {'開' if bool(mk['gate'].iloc[-1]) else '關'}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_stock 失敗：{e}")
        sys.exit(0)
