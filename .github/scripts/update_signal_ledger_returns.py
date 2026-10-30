# -*- coding: utf-8 -*-
"""B19 前瞻訊號台帳的回填腳本：只填 data/signal_ledger.json 裡還是 null 的 T+5/T+20/T+60。

交易日曆、查價、^TWII 抓取全部沿用 update_picks_ledger_returns.py 的同名函式（同一套
price_stale 守門與「找不到就不猜」規則），這裡不重寫。已填欄位永不更動。
規格：research/B19_SIGNAL_LEDGER_SPEC.md 第 5 節。
"""
from __future__ import annotations

import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[2] / "scripts"))
import price_history_store as PHS  # noqa: E402
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_picks_ledger_returns as upl  # noqa: E402

LEDGER_PATH = upl.REPO_ROOT / "data" / "signal_ledger.json"
WINDOWS = {"t5": 5, "t20": 20, "t60": 60}
ENTRY_SKIP_REASON = "進場日無收盤（停牌／無成交／未掛牌）"


def main() -> None:
    ledger = upl._load_json(LEDGER_PATH)
    all_sigs = ledger.get("signals", [])
    if not all_sigs:
        print(f"{LEDGER_PATH} 沒有訊號，結束")
        return
    try:
        prices = (PHS.load(upl.PRICE_HISTORY_PATH) if PHS.exists(upl.PRICE_HISTORY_PATH) else {}).get("prices", {})
    except Exception as e:  # noqa: BLE001
        # 先.一三五-1cj：價格檔讀不出來就整輪不回填、不寫檔（原本拋未處理例外）
        raise SystemExit(f"讀 {upl.PRICE_HISTORY_PATH} 失敗，本輪不回填也不寫檔：{e}")
    ledger.setdefault("meta", {})  # 先.一三五-1cj：缺 meta 原本在寫 entry_skipped 時 KeyError
    cal_rows = prices.get(upl.CALENDAR_PROXY_CODE) or max(prices.values(), key=len, default=[])
    calendar = sorted(r["date"] for r in cal_rows)
    if not calendar:
        print("交易日曆是空的，本輪不回填")
        return

    # 第一步：進場價（只填一次）＝寫入日之後第一個交易日的收盤。寫入日當天收盤不算——
    # 排程 17:13 寫入時當天已收盤，那個價格寫入當下買不到。
    # 先.一四〇-1（2026-10-28，Cowork 收件匣 029 定案丙→甲）：進場日該股沒有列、但之後已有列＝那天真的沒有收盤
    # （停牌／無成交／未掛牌，不是資料還沒到）→ 寫 entry_skip_reason，之後不再列入回填候選、統計分母排除。
    # 進場規則不變（不改用「之後第一個有收盤的日子」，那會把停牌復牌跳空算進訊號報酬）。
    # 10/28 首批 10 筆已用 TPEx 個股日成交資訊逐筆查證都不是漏抓（research/probe_signal_ledger_entry_gaps.py）；
    # 日後若懷疑漏抓，重跑那支探測即可對照官方列。
    entry_filled = skip_new = 0
    for s in all_sigs:
        if s.get("entry_close") is not None or s.get("entry_skip_reason"):
            continue
        rec_day = s["recorded_at"][:10]
        nxt = next((d for d in calendar if d > rec_day), None)
        if nxt is None:
            continue
        px, actual, stale = upl._lookup_price_on(s["code"], nxt, prices)
        if stale or px is None or actual != nxt:
            own_days = {r["date"] for r in prices.get(s["code"]) or []}
            if own_days and max(own_days) > nxt and nxt not in own_days:
                s["entry_skip_reason"] = ENTRY_SKIP_REASON
                s["entry_skip_marked_at"] = datetime.now(upl.TW_TZ).isoformat()
                skip_new += 1
            continue  # 資料未到就留 null 下輪再試；不拿別天的價格頂替
        s["entry_close"], s["entry_date"] = px, nxt
        entry_filled += 1
    skipped_all = [s for s in all_sigs if s.get("entry_skip_reason")]
    ledger["meta"]["entry_skipped"] = {
        "count": len(skipped_all), "reason": ENTRY_SKIP_REASON,
        "note": "這些訊號進場日沒有收盤、不回填報酬，任何勝率／平均報酬統計的分母都要排除並揭露這個筆數（先.一四〇-1）"}
    sigs = [s for s in all_sigs if s.get("entry_close") and s.get("entry_date")]
    for s in sigs:
        if not isinstance(s.get("returns"), dict):
            s["returns"] = {k: None for k in WINDOWS}  # 先.一三五-1cj：缺 returns 鍵原本 KeyError 拖垮整輪

    pending = [s for s in sigs if any(s["returns"].get(k) is None for k in WINDOWS)]
    due = [s for s in pending if upl._trading_days_after(s["entry_date"], 5, calendar)]
    # 先.一四〇-6：報酬已填、但當輪大盤抓取失敗導致超額報酬留 null 的，之後每輪補算（報酬本身不重填）
    need_excess = [s for s in sigs if any(isinstance(s["returns"].get(k), dict)
                                          and s["returns"][k].get("excess_vs_taiex_pct") is None for k in WINDOWS)]
    if not due and not need_excess:
        if entry_filled or skip_new:
            ledger["meta"]["last_returns_backfill_at"] = datetime.now(upl.TW_TZ).isoformat()
            LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
        print(f"進場價新填 {entry_filled} 筆、進場日無收盤新標 {skip_new} 筆（累計 {len(skipped_all)}）；沒有訊號到達 T+5（待回填 {len(pending)} 筆）")
        return
    taiex = upl._fetch_taiex_history(min(s["entry_date"] for s in due + need_excess))

    filled = skipped = excess_fixed = 0
    for s in need_excess:
        for key, n in WINDOWS.items():
            w = s["returns"].get(key)
            if not isinstance(w, dict) or w.get("excess_vs_taiex_pct") is not None:
                continue
            target = upl._trading_days_after(s["entry_date"], n, calendar)  # 同下面首次回填：大盤取目標交易日
            t0, t1 = taiex.get(s["entry_date"]), (taiex.get(target) if target else None)
            if t0 and t1 is not None:
                w["excess_vs_taiex_pct"] = round(w["return_pct"] - upl._compute_return_pct(t0, t1), 4)
                excess_fixed += 1
    for s in due:
        for key, n in WINDOWS.items():
            if s["returns"].get(key) is not None:
                continue
            target = upl._trading_days_after(s["entry_date"], n, calendar)
            if target is None:
                continue
            px, actual, stale = upl._lookup_price_on(s["code"], target, prices)
            if stale or px is None:
                skipped += 1
                continue
            ret = upl._compute_return_pct(s["entry_close"], px)
            t0, t1 = taiex.get(s["entry_date"]), taiex.get(target)
            excess = ret - upl._compute_return_pct(t0, t1) if (t0 and t1 is not None) else None
            s["returns"][key] = {"return_pct": round(ret, 4),
                                 "excess_vs_taiex_pct": round(excess, 4) if excess is not None else None,
                                 "exit_date": actual, "filled_at": datetime.now(upl.TW_TZ).isoformat()}
            filled += 1

    if filled or entry_filled or skip_new or excess_fixed:
        ledger["meta"]["last_returns_backfill_at"] = datetime.now(upl.TW_TZ).isoformat()
        LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"signal_ledger 回填：進場價新填 {entry_filled} 筆、進場日無收盤新標 {skip_new} 筆（累計 {len(skipped_all)}）、報酬新填 {filled} 欄、超額報酬補算 {excess_fixed} 欄、出場價缺失/過期跳過 {skipped} 欄")


if __name__ == "__main__":
    main()
