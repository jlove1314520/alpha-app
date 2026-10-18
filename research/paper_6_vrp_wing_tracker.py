# -*- coding: utf-8 -*-
"""模擬 F-翼（紙.六）：台指選擇權鐵蝴蝶賣方的前進式紙上追蹤（先.一一八-1b）。

規則照 `docs/PREREG_paper_f_wing.md`（參數一次定死）。資料解析、到期日、結算價、節流全部沿用模擬 F 的
`research/paper_5_vrp_tracker.py`（同一份頻率上限狀態），差別只在部位結構（加 ±500 點保護翼）、部位規模（每組最大虧損＝淨值 3%）與停損。
輸出：research/data/paper_6_log.jsonl（帳本，append-only）、data/paper_6.json（App 摘要）。自身失敗只印警告、exit 0。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_5_vrp_tracker as B

ROOT = B.ROOT
LOG = ROOT / "research" / "data" / "paper_6_log.jsonl"
OUT = ROOT / "data" / "paper_6.json"
START = B.START
WING = 500
RISK_FRAC = 0.03
MULT, SLIP, FEE, TAX = B.MULT, B.SLIP_PTS, B.FEE, B.TAX
LABEL = "模擬 F-翼 賣波動（有保護翼）"
NOTE = "紙上追蹤：鐵蝴蝶（賣價平跨式＋買 ±500 點保護翼），每組最大虧損＝淨值 3%；真錢版暫不啟用（本金門檻，先.一一八-1）"


def read_log():
    try:
        return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def append(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"logged_at": datetime.now(B.TW).isoformat(timespec="seconds"), **rec}
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_summary(log, started, extra=None):
    nav = log[-1]["nav"] if log else 100.0
    pos = next((r for r in reversed(log) if r["event"] in ("entry", "settle", "stop")), None)
    peak, mdd = 100.0, 0.0
    for r in log:
        peak = max(peak, r["nav"]); mdd = min(mdd, r["nav"] / peak - 1)
    doc = {"label": LABEL, "started": started, "start": START, "note": NOTE,
           "generated_at": datetime.now(B.TW).isoformat(timespec="seconds"), "nav": round(nav, 4),
           "last_date": log[-1]["date"] if log else None, "max_drawdown_pct": round(mdd * 100, 2),
           "open_position": (pos if pos and pos["event"] == "entry" else None),
           "n_closed": sum(1 for r in log if r["event"] in ("settle", "stop")),
           "n_stops": sum(1 for r in log if r["event"] == "stop"), **(extra or {})}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _px(chain, cm, k, side):
    q = (chain.get(cm, {}).get(k, {}) or {}).get(side) or (None, None)
    return q[0] or q[1]


def _fees_pts(prices) -> float:
    """四腳的手續費＋期交稅換算成點數（每口 50 元/點）。"""
    return (4 * FEE + TAX * sum(prices) * MULT) / MULT


def step(today: date | None = None, opt_text: str | None = None) -> dict:
    today = today or datetime.now(B.TW).date()
    log = read_log()
    if today.isoformat() < START:
        write_summary(log, False, {"why_not_started": f"{START[:7]} 起從當月真實資料開始記，不倒填"})
        return {"state": "NOT_STARTED"}
    text = opt_text if opt_text is not None else B._get("taifex_openapi", "GET", B.OPT_URL).content.decode("utf-8-sig", errors="replace")
    day, chain = B.parse_opt(text)
    if not day or day < START or (log and day <= log[-1]["date"]):
        write_summary(log, bool(log))
        return {"state": "NO_NEW_DAY", "day": day}
    nav = log[-1]["nav"] if log else 100.0
    pos = next((r for r in reversed(log) if r["event"] in ("entry", "settle", "stop")), None)
    op = pos if pos and pos["event"] == "entry" else None
    closed_today = False
    if op:
        cm, k, lots = op["contract"], op["strike"], op["lots"]
        if day > op["expiry"]:
            F = B.final_settlement(cm)
            if F is None:
                write_summary(log, True)
                return {"state": "WAIT_SETTLEMENT", "contract": cm}
            liab_pts = min(abs(F - k), WING)
            pnl = (op["premium_net"] - liab_pts) * MULT * lots - 4 * FEE * lots
            nav_new = op["nav_at_entry"] * (1 + pnl / op["capital"])
            append({"date": day, "event": "settle", "contract": cm, "strike": k, "final_settlement": F, "pnl_ntd": round(pnl, 1), "nav": round(nav_new, 6)})
            nav, op, closed_today = nav_new, None, True
        else:
            legs = [_px(chain, cm, k, "C"), _px(chain, cm, k, "P"), _px(chain, cm, k + WING, "C"), _px(chain, cm, k - WING, "P")]
            if any(v is None for v in legs):
                write_summary(log, True)
                return {"state": "NO_MARK", "day": day}
            liab = legs[0] + legs[1] - legs[2] - legs[3]
            unreal = (op["premium_net"] - liab) * MULT * lots
            S = B.taiex_close(day)
            exp = date.fromisoformat(op["expiry"])
            last_day_before = (exp - date.fromisoformat(day)).days <= 1
            why = None
            if unreal <= -2 * op["premium_net"] * MULT * lots or unreal <= -0.8 * op["max_loss_ntd"]:
                why = "未實現虧損達淨權利金 2 倍或最大虧損 80%"
            elif S and (S > k + WING / 2 or S < k - WING / 2):
                why = f"加權指數收盤 {S} 超出 k±250"
            elif last_day_before and unreal < 0:
                why = "到期前 1 個交易日仍虧損"
            if why:
                close_cost = liab + 4 * SLIP + _fees_pts(legs)
                pnl = (op["premium_net"] - close_cost) * MULT * lots
                nav_new = op["nav_at_entry"] * (1 + pnl / op["capital"])
                append({"date": day, "event": "stop", "contract": cm, "strike": k, "reason": why, "liability_pts": round(liab, 2),
                        "pnl_ntd": round(pnl, 1), "nav": round(nav_new, 6)})
                nav, op, closed_today = nav_new, None, True
            else:
                nav_m = op["nav_at_entry"] * (1 + unreal / op["capital"])
                append({"date": day, "event": "mark", "contract": cm, "strike": k, "liability_pts": round(liab, 2), "nav": round(nav_m, 6)})
                write_summary(read_log(), True)
                return {"state": "MARK", "day": day}
    acted_this_month = any(r["event"] in ("entry",) and r["date"][:7] == day[:7] for r in log)
    if op is None and not acted_this_month and not closed_today:
        S = B.taiex_close(day)
        d0 = date.fromisoformat(day)
        cands = sorted((abs((B.third_wednesday(cm) - d0).days - 30), B.third_wednesday(cm), cm) for cm in chain
                       if 10 <= (B.third_wednesday(cm) - d0).days <= 45)
        if S and cands:
            cm = cands[0][2]
            ok = {k: v for k, v in chain[cm].items() if (v.get("C") or (None,))[0] and (v.get("P") or (None,))[0]}
            if ok:
                k = min(ok, key=lambda x: abs(x - S))
                legs = [_px(chain, cm, k, "C"), _px(chain, cm, k, "P"), _px(chain, cm, k + WING, "C"), _px(chain, cm, k - WING, "P")]
                if all(v is not None and v > 0 for v in legs):
                    prem_net = legs[0] + legs[1] - legs[2] - legs[3] - 4 * SLIP - _fees_pts(legs)
                    max_loss = (WING - prem_net) * MULT
                    if prem_net > 0 and max_loss > 0:
                        capital = max_loss / RISK_FRAC
                        append({"date": day, "event": "entry", "contract": cm, "expiry": B.third_wednesday(cm).isoformat(), "strike": k,
                                "wing": WING, "taiex": S, "legs": {"short_call": legs[0], "short_put": legs[1], "long_call": legs[2], "long_put": legs[3]},
                                "premium_net": round(prem_net, 4), "max_loss_ntd": round(max_loss, 1), "lots": 1, "capital": round(capital, 1),
                                "nav_at_entry": round(nav, 6), "nav": round(nav, 6),
                                "note": "鐵蝴蝶 1 組：賣 k 的 call／put、買 k+500 call／k−500 put；本金＝最大虧損÷3%"})
                        write_summary(read_log(), True)
                        return {"state": "ENTRY", "day": day, "contract": cm, "strike": k}
    if log and not closed_today:
        append({"date": day, "event": "flat", "nav": round(nav, 6)})
    write_summary(read_log(), bool(read_log()))
    return {"state": "FLAT" if not closed_today else "CLOSED", "day": day}


def main() -> int:
    try:
        print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] 模擬 F-翼 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
