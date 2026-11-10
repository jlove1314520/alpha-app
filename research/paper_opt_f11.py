# -*- coding: utf-8 -*-
"""先.一五四-1a ④ 紙上優化軌 F11（全市場融資餘額 regime，0050 曝險，B 崩盤段條件版）每日訊號產生器——研究帽產物，零外部請求。

策略（照 research/DRAWDOWN_FIX.md 1 節 F11 列＋reaudit_optimized_batch2_margin.json best_by_calmar，這裡不調參）：
  訊號：全市場融資餘額（週頻，每週最後一個交易日）8 週成長率，低於自己 expanding 30 百分位（暖身 52 週）＝「去槓桿」
    → 0050 目標曝險 0.25，否則 1.0；只在月底更新（月底收盤決定、下個月第一個交易日起生效）。
  B 崩盤條件（drawdown_fix.cond_series，原生家族用 0050 含息淨值當大盤）：0050 含息 < 120 日均線且距 252 日高點跌 > 20%
    → 曝險再 ×0.5（前一日資訊決定今日）。
  帳戶（照 reaudit_optimized_batch1.simulate()，monthly=False＝每天回到目標權重）：0050 腿＝3×日報酬 −2×無風險 −1%/年槓桿費，
    其餘領無風險利率；換手成本＝|權重變動|×(滑價 0.1%＋手續費 0.1425%×6 折)，賣出另加 ETF 證交稅 0.1%；
    帳戶自高點回撤 30% → 0050 腿清空 21 個交易日。
資料（全部本機）：
  - 融資餘額：2012-05～2024-12 research/data/raw_margin_debt_market（margin_debt_market_client.load_all_cached()，仟元）；
    2026-08-25 起 data/margin_maintenance.json margin_money（每日排程，元→÷1000 成仟元）。
    〔自行裁量〕2025-01～2026-08 本機沒有週資料（要補得另送約 85 次 TWSE MI_MARGN 請求，未做）：成長率在兩段各自計算、
    不跨缺口相除；expanding 百分位用「2012～2024 全部＋2026-08 起新值」，缺口那段就是沒有樣本（照實標註）。
  - 0050 含息日報酬：與 F12 共用 research/data/paper_opt/f12_bars.json（paper_opt_f12.build_bars()）。
  - 無風險利率：data/rf_monthly.json 最新月份。
輸出（append-only）：research/data/paper_opt/ledger_F11.jsonl、state_F11.json；起跑日 2026-11-09。
用法：python research/paper_opt_f11.py [--probe]
非投資建議。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402  （共用價格快取、讀寫工具）

DATA = F12.DATA
OUT = F12.OUT
LEDGER = OUT / "ledger_F11.jsonl"
STATE = OUT / "state_F11.json"

START = "2026-11-09"
K, P, DEF_E, MIN_EXP = 8, 0.7, 0.25, 52
L, STOP, COOLDOWN = 3.0, 0.30, 21
CRASH_N, CRASH_X, CRASH_Y = 120, 0.20, 0.5
FEE_LEV, SLIP, BROKER, ETF_TAX = 0.01, 0.001, 0.001425 * 0.6, 0.001


def weekly_balance() -> list[tuple[list[str], list[float]]]:
    """回傳兩段 (日期, 仟元餘額)：舊段（2012～2024 快取）、新段（margin_maintenance 每週最後一個交易日）。"""
    from datetime import date
    from margin_debt_market_client import load_all_cached
    old = load_all_cached()
    old = old[old["date"] <= "2024-12-31"]
    seg_old = ([str(d)[:10] for d in old["date"]], [float(x) for x in old["financing_amount_today_balance_kNTD"]])
    m = json.loads((DATA / "margin_maintenance.json").read_text(encoding="utf-8"))
    byweek: dict = {}
    for r in m:
        v = r.get("margin_money")
        if not v or not r.get("date"):
            continue
        d = r["date"]
        wk = date.fromisoformat(d).isocalendar()[:2]
        if wk not in byweek or d > byweek[wk][0]:
            byweek[wk] = (d, float(v) / 1000.0)
    new = sorted(byweek.values())
    return [seg_old, ([d for d, _ in new], [v for _, v in new])]


def flags() -> list[tuple[str, float | None]]:
    """[(週日期, 1.0=去槓桿／0.0=否／None=暖身或不足)]，PIT：每週只用當週以前的成長率分布。"""
    g: list[tuple[str, float]] = []
    for ds, vs in weekly_balance():
        for i in range(len(ds)):
            if i >= K and vs[i - K] > 0:
                g.append((ds[i], vs[i] / vs[i - K] - 1.0))
            else:
                g.append((ds[i], None))
    g.sort()
    hist: list[float] = []
    out = []
    for d, x in g:
        if x is not None:
            hist.append(x)
        if x is None or len(hist) < MIN_EXP:
            out.append((d, None))
            continue
        s = sorted(hist)
        q = (1 - P) * (len(s) - 1)  # pandas expanding().quantile 預設線性內插
        lo = int(q)
        th = s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (q - lo)
        out.append((d, 1.0 if x < th else 0.0))
    return out


def exposure_at(fl, day: str) -> float:
    v = None
    for d, f in fl:
        if d <= day:
            v = f
        else:
            break
    return 1.0 if v is None else (DEF_E if v > 0.5 else 1.0)


def crash_factor(levels: dict, day: str) -> tuple[float, bool | None]:
    ds = [d for d in levels if d <= day]
    if len(ds) < CRASH_N:
        return 1.0, None
    px = [levels[d] for d in ds]
    ma = sum(px[-CRASH_N:]) / CRASH_N
    hi = max(px[-252:])
    on = px[-1] < ma and px[-1] / hi - 1.0 < -CRASH_X
    return (CRASH_Y if on else 1.0), on


def side_cost(dw_risky: float) -> float:
    c = abs(dw_risky) * (SLIP + BROKER)
    if dw_risky < 0:
        c += abs(dw_risky) * ETF_TAX
    return c



def _acct(s: dict, target: float, r50: float, rf: float):
    """帳戶一日（照 reaudit_optimized_batch1.simulate()）；s 需有 eq／peak／cool／w。回傳 (日報酬, 實際目標, 成本, 事件)。"""
    t = target
    if s["cool"] > 0:
        s["cool"] -= 1
        t = 0.0
    w0, wc = s["w"]
    cost = side_cost(t - w0)
    w0, wc = t, 1.0 - t
    rl = L * r50 - (L - 1.0) * rf - FEE_LEV / 252.0
    g0, gc = w0 * (1 + rl), wc * (1 + rf)
    tot = g0 + gc
    r = (tot - 1.0) - cost
    if s["eq"] <= 0:
        r = 0.0
    s["eq"] = max(s["eq"] * (1 + r), 0.0)
    s["w"] = [g0 / tot, gc / tot] if tot > 0 else [0.0, 0.0]
    in_pos = w0 > 0
    s["peak"] = max(s["peak"], s["eq"]) if in_pos else s["eq"]
    evt = None
    if in_pos and s["eq"] < s["peak"] * (1 - STOP):
        s["cool"], s["peak"], evt = COOLDOWN, s["eq"], "account_stop"
    return r, t, cost, evt


def _orig_init(s: dict, rf: float) -> dict:
    """原版影子帳戶初始化：用已寫過的帳本列重播（目標＝當天融資旗標曝險 margin_flag_exposure、0050 日報酬 r_0050），
    不乘崩盤係數。舊列不改寫（append-only），重播出的原版日報酬存在 state["orig_backfill"]，組合合成時讀。
    〔自行裁量〕重播用目前的無風險日利率（同月份、差異可忽略）。"""
    o = {"eq": 1.0, "peak": 1.0, "cool": 0, "w": [0.0, 0.0]}
    back = {}
    rows = []
    if LEDGER.exists():
        rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        ro, *_ = _acct(o, float(r["margin_flag_exposure"]), float(r["r_0050"]), rf)
        back[r["date"]] = round(ro, 8)
    s["orig_backfill"] = back
    return o


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    ids = F12.universe()
    bars, calendar = F12.build_bars(ids)
    b50 = bars.get("0050", {})
    ds50, lv50 = F12.adj_levels(b50)
    levels = dict(zip(ds50, lv50))
    rf = F12.rf_daily()
    fl = flags()
    if a.probe:
        day = calendar[-1]
        last = [x for x in fl if x[0] <= day][-6:]
        print("最近 6 週旗標（1＝去槓桿）：", last)
        cf, on = crash_factor(levels, day)
        print(f"{day}：融資旗標曝險 {exposure_at(fl, day)}；0050 崩盤條件 {on}（係數 {cf}）；無風險日利率 {rf:.6%}")
        return 0
    s = F12._rj(STATE, None) or {"start": START, "eq": 1.0, "peak": 1.0, "cool": 0, "w": [0.0, 0.0], "e_cur": None,
                                 "last_date": None}
    if a.start != START:
        s["start"] = a.start
    if "orig" not in s:
        s["orig"] = _orig_init(s, rf)
    done = 0
    for i, day in enumerate(calendar):
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        prev = calendar[i - 1] if i > 0 else None
        if prev is None or day not in b50:
            print(f"[warn] {day} 沒有 0050 價格或前一交易日，跳過")
            continue
        # 月頻訊號：上個月最後一個交易日收盤決定、本月生效
        if s["e_cur"] is None or prev[:7] != day[:7]:
            me = prev if prev[:7] != day[:7] else max(d for d in calendar if d[:7] < day[:7])
            s["e_cur"] = exposure_at(fl, me)
            s["e_from"] = me
        cf, _on = crash_factor(levels, prev)
        r50 = b50[day][4] or 0.0
        r, t, cost, evt = _acct(s, s["e_cur"] * cf, r50, rf)
        # 先.一五四-1a（2026-11-10）原版影子帳戶（不乘崩盤係數；同一套 3×／帳戶停損 30%）——組合 C25 成員用原版曲線
        r_o, _t_o, _c_o, evt_o = _acct(s["orig"], s["e_cur"], r50, rf)
        rec = {"date": day, "ret": round(r, 8), "account": round(s["eq"], 8), "target_0050": round(t, 4),
               "margin_flag_exposure": s["e_cur"], "margin_flag_from": s.get("e_from"), "crash_factor": cf,
               "r_0050": round(r50, 6), "cost": round(cost, 6), "account_event": evt, "cooldown_left": s["cool"],
               "ret_orig": round(r_o, 8), "account_orig": round(s["orig"]["eq"], 8), "orig_account_event": evt_o}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 帳戶 {r:+.2%}　0050 目標 {t:.2f}（融資 {s['e_cur']}×崩盤 {cf}）")
    F12._wj(STATE, s)
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f11 失敗：{e}")
        sys.exit(0)
