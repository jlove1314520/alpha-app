# -*- coding: utf-8 -*-
"""模擬 J／K／L（paper_10～12）起跑前事件乾跑（先.一三五-1fn）。

用最近 N 個交易日（預設 20）的真實輸入，逐日呼叫三支追蹤程式自己的訊號函式（不重寫邏輯），
印每日事件數與各輸入檔最後資料日，確認 12/01 起跑前輸入真的在流動。
- 零外部請求、不寫帳本、不算報酬：不呼叫 step()；paper_10 的事件累積與 paper_12 的出現日索引
  都先複製到暫存目錄再更新，正式檔（research/data/paper_10_events.json、paper_12_appearances.json）不動。
- 不寫任何 research/data/paper_1*_log.jsonl。
用法：python scripts/dryrun_paper_10_12_events.py [--days 20] [--json 輸出路徑]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import paper_forward_common as C  # noqa: E402
import paper_10_disposition_tracker as P10  # noqa: E402
import paper_11_tdcc_bigholder_tracker as P11  # noqa: E402
import paper_12_warrant_wave_tracker as P12  # noqa: E402


def _lag(px: C.Px, last: str | None, today: str) -> int | None:
    """last 之後到 today（含）共幾個交易日；last 為 None 回 None。"""
    if not last:
        return None
    return sum(1 for d in px.calendar if last < d <= today)


def holders_last_week(stocks: dict) -> str | None:
    best = None
    for v in stocks.values():
        for h in (v or {}).get("history") or []:
            d = h.get("date")
            if d and h.get("big_holder_ratio") is not None:
                d = d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                best = d if best is None or d > best else best
    return best


def run(days: int) -> dict:
    px = C.load_px()
    today = px.latest_date()
    win = px.calendar[-days:]
    active = set((C.load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    tmp = Path(tempfile.mkdtemp(prefix="dryrun_p10_12_"))
    try:
        # ---- 模擬 J：處置股（事件型；宇宙無成交值門檻，同 _day_event）
        ev_tmp = tmp / "paper_10_events.json"
        if P10.EVENTS.exists():
            shutil.copy(P10.EVENTS, ev_tmp)
        doc10 = P10.accumulate(P10.FLAGS, ev_tmp)
        segs = doc10["segments"]
        sig_main, sig_ctrl = P10.make_signal(segs, control=False), P10.make_signal(segs, control=True)
        flags = C.load_json(P10.FLAGS, {}) or {}
        last10 = max([s["end"] for s in segs] + [s["start"] for s in segs], default=None)
        ctx10 = {"px": px}
        j_days = []
        for d in win:
            uni = C.universe(px, d, active, None)
            a = sig_main(ctx10, d, uni) or []
            b = sig_ctrl({"px": px, "limits": ctx10.get("limits")}, d, uni) or []
            j_days.append({"date": d, "events": len(a), "control_events": len(b),
                           "skips": len(ctx10.get("skips", {}).get(d) or []), "codes": [c["code"] for c in a]})
        # 最近處置公告日（flags 內 announced 最大值）
        ann = max([r.get("announced") or "" for r in (flags.get("disposal") or {}).values() if r] or [""]) or None

        # ---- 模擬 K：集保千張大戶（月頻；乾跑逐日算「若今天再平衡」的入選數）
        stocks = (C.load_json(ROOT / "data" / "holders.json", {}) or {}).get("stocks") or {}
        wk = holders_last_week(stocks)
        k_days = []
        for d in win:
            ctx = {"px": px}
            uni = C.universe(px, d, active, P11.MIN_TURNOVER)
            rows = P11.signal(ctx, d, uni)
            k_days.append({"date": d, "events": None if rows is None else min(len(rows), P11.M),
                           "positive_delta": None if rows is None else len(rows), "skip_reason": ctx.get("skip_reason")})

        # ---- 模擬 L：認購權證發行潮（月頻；出現日索引在暫存目錄重建）
        ap_tmp = tmp / "paper_12_appearances.json"
        if P12.APPEAR.exists():
            shutil.copy(P12.APPEAR, ap_tmp)
        appear = P12.update_appearances(P12.SNAP, ap_tmp)
        snaps = sorted(appear.get("dates_processed") or [])
        start, gate = P12.start_date(px)
        l_days = []
        for d in win:
            ctx = {"px": px, "appear": appear}
            uni = C.universe(px, d, active, P12.MIN_TURNOVER)
            rows = P12.signal(ctx, d, uni)
            new_today = sum(1 for w in (appear.get("warrants") or {}).values() if w.get("first_seen") == d)
            # 僅診斷：記憶體內暫時放寬缺快照上限（不改檔案、用完復原），看計數邏輯在有快照時會不會出候選
            keep, P12.MAX_MISSING = P12.MAX_MISSING, P12.W
            try:
                diag = P12.signal({"px": px, "appear": appear}, d, uni) or []
            finally:
                P12.MAX_MISSING = keep
            l_days.append({"date": d, "snapshot_ok": P12.snapshot_ok(d), "new_calls_first_seen": new_today,
                           "events": None if rows is None else min(len(rows), P12.M),
                           "candidates": None if rows is None else len(rows), "skip_reason": ctx.get("skip_reason"),
                           "diag_candidates_ignoring_missing_gate": len(diag)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    td = date.fromisoformat(today)
    return {
        "today_price_date": today, "window": [win[0], win[-1]], "n_days": len(win),
        "paper_10": {"input": "data/disposal_flags.json", "flags_generated": (flags.get("meta") or {}).get("generated_at")
                     or (flags.get("meta") or {}).get("updated_at"),
                     "latest_announced": ann, "latest_segment_date": last10, "segments": len(segs),
                     "days_with_events": sum(1 for x in j_days if x["events"] > 0), "days": j_days},
        "paper_11": {"input": "data/holders.json", "latest_week": wk,
                     "latest_week_lag_calendar_days": (td - date.fromisoformat(wk)).days if wk else None,
                     "days_with_events": sum(1 for x in k_days if (x["events"] or 0) > 0), "days": k_days},
        "paper_12": {"input": "research/data/warrant_snapshots/", "latest_snapshot": snaps[-1] if snaps else None,
                     "latest_snapshot_lag_trading_days": _lag(px, snaps[-1] if snaps else None, today),
                     "snapshots_in_window": sum(1 for x in l_days if x["snapshot_ok"]), "start_gate": gate, "start": start,
                     "days_with_events": sum(1 for x in l_days if (x["events"] or 0) > 0), "days": l_days},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=20)
    ap.add_argument("--json", type=str, default=None)
    a = ap.parse_args()
    r = run(a.days)
    print(f"價格最新日 {r['today_price_date']}；乾跑區間 {r['window'][0]}～{r['window'][1]}（{r['n_days']} 個交易日）")
    p = r["paper_10"]
    print(f"\n[模擬 J 處置股] 處置段 {p['segments']}、最近公告日 {p['latest_announced']}、最近處置日 {p['latest_segment_date']}；"
          f"有事件天數 {p['days_with_events']}")
    for x in p["days"]:
        print(f"  {x['date']}  主線 {x['events']:>2}  影子 {x['control_events']:>2}  略過 {x['skips']:>2}  {','.join(x['codes'])}")
    p = r["paper_11"]
    print(f"\n[模擬 K 千張大戶] 最新週 {p['latest_week']}（落後 {p['latest_week_lag_calendar_days']} 天）；有事件天數 {p['days_with_events']}")
    for x in p["days"]:
        print(f"  {x['date']}  入選 {x['events']}  Δ>0 {x['positive_delta']}  {x['skip_reason'] or ''}")
    p = r["paper_12"]
    print(f"\n[模擬 L 權證發行潮] 最新快照 {p['latest_snapshot']}（落後 {p['latest_snapshot_lag_trading_days']} 個交易日）、"
          f"區間內快照 {p['snapshots_in_window']} 天；起跑門檻 {p['start_gate']}；有事件天數 {p['days_with_events']}")
    for x in p["days"]:
        print(f"  {x['date']}  快照 {'有' if x['snapshot_ok'] else '缺'}  當日新認購 {x['new_calls_first_seen']:>3}  "
              f"入選 {x['events']}  候選 {x['candidates']}  （診斷：不看缺快照門檻時候選 {x['diag_candidates_ignoring_missing_gate']}）"
              f"  {x['skip_reason'] or ''}")
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
