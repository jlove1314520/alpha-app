# -*- coding: utf-8 -*-
"""模擬 R：借券賣出餘額大幅回補後漂移 前向紙上追蹤（先.一三六-B7）。

規則照 `docs/PREREG_SBL_COVERING_DRIFT_FORWARD_FINAL.md`（§5-1 甲只做上市；C＝40%、H＝20、M＝20，一次定死）；
共用部分在 research/paper_forward_common.py，本檔只有訊號函式。
- 事件 t0（上市普通股）：5 個交易日前借券賣出餘額 ≥100 萬股、t0 餘額 ÷ 5 個交易日前 −1 ≤ −C；
  t0 前後 10 個交易日內有除權息者排除；同代號 60 個交易日內只算第一個事件。
- t1 收盤買進；t1 漲停鎖死 → 放棄；t0 前 20 日均成交值 ≥1,000 萬；同日超額依代號排序；下市以 −100% 計（同模擬 J）。
- 揭露欄（不判定）：回補量占 t0 前 20 日均量倍數、t0 前 20 個交易日股價報酬。
資料：data/securities_lending_sell_history.json `series_twse`（每日管線既有 TWT93U 呼叫累積）＋data/price_history＋
data/ex_dividend_events.json，零額外外部請求。上櫃 `series_tpex` 沒有餘額欄，不用。
"""
from __future__ import annotations

import paper_forward_common as C
import paper_forward_events as E

ROOT = C.ROOT
C_DROP, H, M = 0.40, 20, 20
LOOKBACK = 5
MIN_BAL_5AGO = 1_000_000.0    # 股
MIN_PRE_TURNOVER = 10_000_000.0
DEDUPE_DAYS = 60
EXDIV_WINDOW = 10
SBL_BALANCE_IDX = 4           # twse_fields: sbl_prev_balance, sbl_sell, sbl_return, sbl_adjust, sbl_balance, ...
START = "2027-01-04"
JUDGE = "2029-01-02"
PREREG = "docs/PREREG_SBL_COVERING_DRIFT_FORWARD_FINAL.md"
TRIAL_NO = 489  # register_trial() #489（2026-10-27 互動視窗 先.一三七-1 登記）
SBL = ROOT / "data" / "securities_lending_sell_history.json"
EXDIV = ROOT / "data" / "ex_dividend_events.json"


def _bal(v):
    try:
        return float(v[SBL_BALANCE_IDX])
    except (TypeError, ValueError, IndexError):
        return None


def raw_events(sbl: dict, px: C.Px, exdiv: dict) -> list:
    cal = px.calendar
    exd = {c: sorted({e.get("ex_date") for e in evs or [] if e.get("ex_date")})
           for c, evs in ((exdiv or {}).get("events") or {}).items()}
    out = []
    for code, ser in ((sbl or {}).get("series_twse") or {}).items():
        if not C.is_common(code):
            continue
        ser = {E.iso(k): v for k, v in (ser or {}).items()}
        for t0, v in ser.items():
            i = E.tindex(px, t0)
            if i < LOOKBACK or cal[i] != t0:
                continue
            b0, b5 = _bal(v), _bal(ser.get(cal[i - LOOKBACK]))
            if b0 is None or b5 is None or b5 < MIN_BAL_5AGO or b0 / b5 - 1 > -C_DROP:
                continue
            lo, hi = E.trading_window(px, t0, EXDIV_WINDOW)
            if any(lo <= x <= hi for x in exd.get(code, [])):
                continue
            out.append({"code": code, "t0": t0, "bal_5ago": b5, "bal_t0": b0, "bal_chg_5d": round(b0 / b5 - 1, 6)})
    return E.dedupe(out, px, DEDUPE_DAYS)


def make_signal(events: list):
    by_t0 = {}
    for ev in events:
        by_t0.setdefault(ev["t0"], []).append(ev)

    def signal(ctx: dict, day: str, uni: dict) -> list:
        px: C.Px = ctx["px"]
        t0 = px.prev_trading_day(day)
        cands, skips = [], []
        for ev in by_t0.get(t0) or []:
            code = ev["code"]
            if code not in uni:
                skips.append({"code": code, "reason": "不在宇宙（非普通股／不在市／t1 無收盤）"})
                continue
            liq = px.avg_turnover(code, t0, inclusive=False)
            if liq is None or liq < MIN_PRE_TURNOVER:
                skips.append({"code": code, "reason": "t0 前 20 日均成交值不足 1,000 萬或資料不滿 20 天"})
                continue
            if E.locked_up(px, code, day):
                skips.append({"code": code, "reason": "t1 漲停鎖死，放棄"})
                continue
            rs = [r for r in px.rows.get(code) or [] if r["date"] < t0]
            vols = [float(r["volume"]) for r in rs if r.get("volume")][-20:]
            p_now, p20 = px.close_on(code, t0), (px.close_le(code, rs[-20]["date"]) if len(rs) >= 20 else None)
            cands.append({**ev, "pre_turnover_20d": round(liq),
                          "cover_vs_avg_vol20": round((ev["bal_5ago"] - ev["bal_t0"]) / (sum(vols) / len(vols)), 3) if len(vols) == 20 and sum(vols) else None,
                          "pre20_ret": round(p_now / p20 - 1, 6) if p_now and p20 else None})
        cands.sort(key=lambda c: c["code"])
        ctx.setdefault("skips", {})[day] = skips
        return cands
    return signal


def spec(events: list) -> C.Spec:
    return C.Spec(key="paper_18", label="模擬 R 借券大幅回補漂移",
                  note="上市股借券賣出餘額 5 日減 ≥40% 的隔天收盤買進、持有 20 個交易日；最多 20 檔、每筆淨值 1/20；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="event",
                  top_n=M, hold_days=H, delist_value="zero", signal=make_signal(events),
                  log_path=ROOT / "research" / "data" / "paper_18_log.jsonl", out_path=ROOT / "data" / "paper_18.json",
                  judge_text=("2029-01-02 後判一次：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20270104）"),
                  known_limit="只做上市；還券也可能是出借人召回（被迫還券），無法逐筆區分；事件數不足 100 筆照判 INCONCLUSIVE",
                  extra_summary={"events_source": "data/securities_lending_sell_history.json series_twse（2026-09-24 起前向累積）"})


def step() -> dict:
    px = C.load_px()
    evs = raw_events(C.load_json(SBL, {}), px, C.load_json(EXDIV, {}))
    return C.step(spec(evs), {"px": px, "summary_extra": {"raw_events_after_dedupe": len(evs)}}, px=px)


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 R"))
