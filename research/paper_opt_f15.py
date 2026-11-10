# -*- coding: utf-8 -*-
"""先.一五四-1a ⑤ 紙上優化軌 F15（美股低波動 f_us_low_vol，只做多，原版）每日訊號產生器——研究帽產物，零外部請求。

F15 只是組合 C25／C20 的成員（組合用各家族「原版」曲線，見 research/DRAWDOWN_FIX.md 3 節），所以這裡照原版、不調參：
  reaudit_optimized_batch2_us_lowvol.json best_by_calmar＝vol_window 20、N 50、rebalance_days 21、L 1.0、stop 0.10。
  底層（1× 無停損）：第 t 日收盤以前 20 日日報酬樣本標準差（20 日須完整、當日須有報酬），挑最低 50 檔等權；
    t 日收盤決定、t+1 日收盤成交（換手×0.10% 成本，報酬從 t+2 起算）；持股權重每日漂移；缺價當天以 0 計。
  帳戶：L＝1，帳戶自高點回落 10% → 退現金（領 DTB3）21 個美股交易日後再進場（同原腳本 overlay）。
  換股相位〔自行裁量〕：原版從 2011-01-03 起每 21 日；紙上版從起跑日（2026-11-09 後第一個美股交易日）起每 21 日。
資料（全部本機）：research/data/paper_opt/us_returns.json（research/fetch_paper_opt_us_prices.py 每日 1 次 yfinance 批次）、
  research/data/us_rf_dtb3.parquet 最新一筆（現金利率）。
換匯：ledger 同時記美元報酬 ret_usd 與台幣報酬 ret（＝(1+ret_usd)×匯率比−1），匯率用當天以前最新的央行牌告
  （fetch 腳本從 data/fx.json 及其 git 歷史還原）；缺匯率當天比值記 1 並標 fx_missing。
**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 宇宙為今天還在的 248 檔分層抽樣，偏樂觀。
輸出（append-only，日期＝美股交易日）：research/data/paper_opt/ledger_F15.jsonl、state_F15.json；起跑日 2026-11-09。
用法：python research/paper_opt_f15.py [--probe]
十二節：失敗只印警告、exit 0。非投資建議。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "paper_opt"
SRC = OUT / "us_returns.json"
LEDGER = OUT / "ledger_F15.jsonl"
STATE = OUT / "state_F15.json"
START = "2026-11-09"
W, N, REB, L, STOP, COOLDOWN, COST = 20, 50, 21, 1.0, 0.10, 21, 0.0010


def rf_daily() -> float:
    try:
        import pandas as pd
        d = pd.read_parquet(HERE / "data" / "us_rf_dtb3.parquet").sort_values("date")
        return float(d["dtb3_pct"].iloc[-1]) / 100.0 / 252.0
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 讀 DTB3 失敗，現金利率記 0：{e}")
        return 0.0


def fx_at(fx: dict, day: str) -> float | None:
    ks = [k for k in fx if k <= day]
    return fx[max(ks)] if ks else None


def vol_pick(rets: dict, dates: list[str], i: int) -> list[str]:
    win = dates[i - W + 1:i + 1] if i - W + 1 >= 0 else None
    if not win:
        return []
    today = rets[dates[i]]
    vols = []
    for t in today:
        if t == "SPY":
            continue
        xs = [rets[d].get(t) for d in win]
        if any(x is None for x in xs):
            continue
        m = sum(xs) / W
        vols.append((math.sqrt(sum((x - m) ** 2 for x in xs) / (W - 1)), t))
    if len(vols) < N:
        return []
    vols.sort()
    return [t for _, t in vols[:N]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    src = json.loads(SRC.read_text(encoding="utf-8"))
    rets, fx = src["returns"], src.get("fx_usd_twd", {})
    dates = sorted(d for d in rets if "SPY" in rets[d])
    rf = rf_daily()
    if a.probe:
        pk = vol_pick(rets, dates, len(dates) - 1)
        print(f"最後美股交易日 {dates[-1]}，低波動前 {N} 檔（{len(pk)}）：{pk[:10]}…；DTB3 日利率 {rf:.6%}")
        return 0
    s = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {
        "start": START, "k": 0, "w": {}, "pending": None, "eq": 1.0, "peak": 1.0, "cool": 0, "in_pos": False,
        "last_date": None, "holdings_from": None}
    done = 0
    for i, day in enumerate(dates):
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        prev = dates[i - 1]
        r = rets[day]
        # 底層 1×：持股今天報酬→漂移→執行前一日的換股
        w = s["w"]
        base_day = sum(wt * (r.get(t) or 0.0) for t, wt in w.items())
        if w:
            g = {t: wt * (1 + (r.get(t) or 0.0)) for t, wt in w.items()}
            w = {t: v / (1 + base_day) for t, v in g.items()} if (1 + base_day) > 0 else g
        cost = 0.0
        if s["pending"] is not None:
            tgt = s["pending"]
            cost = sum(abs(tgt.get(t, 0.0) - w.get(t, 0.0)) for t in set(tgt) | set(w)) * COST
            w, s["pending"], s["holdings_from"] = tgt, None, day
        base = base_day - cost
        rebal = s["k"] % REB == 0
        if rebal:
            pk = vol_pick(rets, dates, i)
            if pk:
                s["pending"] = {t: 1.0 / N for t in pk}
            else:
                print(f"[warn] {day} 可選檔數不足 {N}（20 日資料不完整），本期不換股")
        s["k"] += 1
        s["w"] = w
        # 帳戶層（L=1）
        e = L
        if s["cool"] > 0:
            s["cool"] -= 1
            e = 0.0
        if s["eq"] <= 0:
            ret_usd = 0.0
        elif e > 0:
            ret_usd = L * base - (L - 1.0) * rf
        else:
            ret_usd = rf
        now_in = e > 0
        s["eq"] = max(s["eq"] * (1 + ret_usd), 0.0)
        s["in_pos"] = now_in
        s["peak"] = max(s["peak"], s["eq"]) if now_in else s["eq"]
        evt = None
        if now_in and s["eq"] < s["peak"] * (1 - STOP):
            s["cool"], s["peak"], evt = COOLDOWN, s["eq"], "account_stop"
        f1, f0 = fx_at(fx, day), fx_at(fx, prev)
        if s["last_date"] is None:  # 起跑當天才把台幣換成美元，前一日匯率變動不算進帳
            f0 = f1
        ratio = (f1 / f0) if (f1 and f0) else 1.0
        ret = (1 + ret_usd) * ratio - 1.0
        rec = {"date": day, "ret": round(ret, 8), "ret_usd": round(ret_usd, 8), "fx": f1, "fx_ratio": round(ratio, 6),
               "fx_missing": not (f1 and f0), "base_1x": round(base, 8), "cost": round(cost, 6),
               "n_hold": len(w), "rebalance_decided": rebal, "account_usd": round(s["eq"], 8),
               "account_event": evt, "cooldown_left": s["cool"]}
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 美元 {ret_usd:+.2%}／台幣 {ret:+.2%}　持股 {len(w)} 檔{'　換股已決定' if rebal else ''}")
    STATE.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f15 失敗：{e}")
        sys.exit(0)
