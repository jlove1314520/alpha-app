# -*- coding: utf-8 -*-
"""模擬 K：集保千張大戶持股比 4 週增幅 前向紙上追蹤（先.一三二-5）。

規則照 `docs/PREREG_TDCC_BIGHOLDER_FORWARD_FINAL.md`（L=4、M=20、R=60，一次定死）；共用部分在
research/paper_forward_common.py，本檔只有訊號函式。
- 訊號：每檔 Δ＝千張大戶持股比（15 級）最新一週 − L 週前（兩期相隔 ≥L 週且 ≤L+2 週，否則該檔當期無訊號、不補值），
  只用資料日期早於再平衡日的週（PIT）；Δ>0 且排前 M 進場、跌出前 R（或 Δ≤0）出場；全市場算不出 → 該月不調倉。
- 每筆入選另記 etf_0050_006208_member（只揭露、不剔除、不作判定）：讀 data/tw50_constituents.json，沒有這份檔就記 null。
資料：data/holders.json（本機 AlphaTdccHolders 每日 09:00、同週略過）＋data/price_history，零額外外部請求。
"""
from __future__ import annotations

from datetime import date

import paper_forward_common as C

ROOT = C.ROOT
L_WEEKS, M, R = 4, 20, 60
MIN_TURNOVER = 30_000_000.0
START = "2026-12-01"
JUDGE = "2028-12-01"
PREREG = "docs/PREREG_TDCC_BIGHOLDER_FORWARD_FINAL.md"
TRIAL_NO = 465  # register_trial() 2026-10-23


def _d(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if "-" not in s else date.fromisoformat(s)


def delta_for(history: list, day: str):
    """回傳 (Δ 百分點, 最新週, 對照週)；條件不符回 None。"""
    rows = [h for h in history or [] if h.get("big_holder_ratio") is not None and _d(h["date"]) < _d(day)]
    if not rows:
        return None
    rows.sort(key=lambda h: h["date"])
    last = rows[-1]
    lo_days, hi_days = 7 * L_WEEKS, 7 * (L_WEEKS + 2)
    prior = [h for h in rows[:-1] if lo_days <= (_d(last["date"]) - _d(h["date"])).days <= hi_days]
    if not prior:
        return None
    p = prior[-1]  # 往前找最近的一週（相隔最接近 L 週）
    return float(last["big_holder_ratio"]) - float(p["big_holder_ratio"]), last["date"], p["date"]


def tw50_members():
    doc = C.load_json(ROOT / "data" / "tw50_constituents.json", None)
    if not doc:
        return None
    return set(doc.get("codes") or [])


def signal(ctx: dict, day: str, uni: dict):
    stocks = (C.load_json(ROOT / "data" / "holders.json", {}) or {}).get("stocks") or {}
    members = tw50_members()
    rows, computable = [], 0
    for code, liq in uni.items():
        d = delta_for((stocks.get(code) or {}).get("history"), day)
        if d is None:
            continue
        computable += 1
        dv, wk, pk = d
        if dv <= 0:
            continue
        rows.append({"code": code, "delta_pp": round(dv, 4), "week": wk, "prior_week": pk, "turnover_20d": round(liq or 0),
                     "etf_0050_006208_member": (code in members) if members is not None else None})
    if computable == 0:
        ctx["skip_reason"] = "TDCC 缺週：全市場算不出 L 週變化，本月不調倉"
        return None
    rows.sort(key=lambda r: (-r["delta_pp"], r["code"]))
    return rows


def spec() -> C.Spec:
    return C.Spec(key="paper_11", label="模擬 K 集保千張大戶增持",
                  note="每月第一個交易日：千張大戶持股比 4 週增幅排名前 20 進場、跌出前 60 出場、等權；近 20 日均成交值 ≥3,000 萬；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="monthly",
                  top_n=M, exit_rank=R, min_turnover=MIN_TURNOVER, delist_value="last", signal=signal,
                  log_path=ROOT / "research" / "data" / "paper_11_log.jsonl", out_path=ROOT / "data" / "paper_11.json",
                  judge_text=("2028-12-01 後判一次：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20261201）"),
                  known_limit="千張大戶含 ETF 發行人／政府基金／保管帳戶；ETF 申贖造成的機械變動只揭露不剔除；24 個月檢定力弱",
                  extra_summary={"etf_member_source": "data/tw50_constituents.json（未建檔前記 null）"})


def step() -> dict:
    px = C.load_px()
    return C.step(spec(), {"px": px}, px=px)


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 K"))
