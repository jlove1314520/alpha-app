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


def main() -> None:
    ledger = upl._load_json(LEDGER_PATH)
    all_sigs = ledger.get("signals", [])
    if not all_sigs:
        print(f"{LEDGER_PATH} 沒有訊號，結束")
        return
    prices = (PHS.load(upl.PRICE_HISTORY_PATH) if PHS.exists(upl.PRICE_HISTORY_PATH) else {}).get("prices", {})
    cal_rows = prices.get(upl.CALENDAR_PROXY_CODE) or max(prices.values(), key=len, default=[])
    calendar = sorted(r["date"] for r in cal_rows)
    if not calendar:
        print("交易日曆是空的，本輪不回填")
        return

    # 第一步：進場價（只填一次）＝寫入日之後第一個交易日的收盤。寫入日當天收盤不算——
    # 排程 17:13 寫入時當天已收盤，那個價格寫入當下買不到。
    entry_filled = 0
    for s in all_sigs:
        if s.get("entry_close") is not None:
            continue
        rec_day = s["recorded_at"][:10]
        nxt = next((d for d in calendar if d > rec_day), None)
        if nxt is None:
            continue
        px, actual, stale = upl._lookup_price_on(s["code"], nxt, prices)
        if stale or px is None or actual != nxt:
            continue  # 該股當天無成交/資料未到，留 null 下輪再試；不拿別天的價格頂替
        s["entry_close"], s["entry_date"] = px, nxt
        entry_filled += 1
    sigs = [s for s in all_sigs if s.get("entry_close") and s.get("entry_date")]

    pending = [s for s in sigs if any(s["returns"].get(k) is None for k in WINDOWS)]
    due = [s for s in pending if upl._trading_days_after(s["entry_date"], 5, calendar)]
    if not due:
        if entry_filled:
            ledger["meta"]["last_returns_backfill_at"] = datetime.now(upl.TW_TZ).isoformat()
            LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
        print(f"進場價新填 {entry_filled} 筆；沒有訊號到達 T+5（待回填 {len(pending)} 筆）")
        return
    taiex = upl._fetch_taiex_history(min(s["entry_date"] for s in due))

    filled = skipped = 0
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

    if filled or entry_filled:
        ledger["meta"]["last_returns_backfill_at"] = datetime.now(upl.TW_TZ).isoformat()
        LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"signal_ledger 回填：進場價新填 {entry_filled} 筆、報酬新填 {filled} 欄、出場價缺失/過期跳過 {skipped} 欄")


if __name__ == "__main__":
    main()
