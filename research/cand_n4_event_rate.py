# -*- coding: utf-8 -*-
"""候選 N4（融資餘額驟減＋大跌後反彈，前向）事件抽取＋事件率量測（先.一三五-1e ①）。

草稿：docs/PREREG_DRAFT_MARGIN_LIQUIDATION_REBOUND_FORWARD.md §2。
- 只量「籌碼條件」：前一交易日融資餘額 ≥ 500 張、單日融資減幅 ≥ 10%、普通股、20 個交易日去重。
- **不讀任何價格、不算任何報酬、零外部請求**；跌幅（t0 ≤ −5%）、除權息排除、流動性門檻、
  t1 漲停放棄都要價格，留給定稿後的追蹤程式 → 這裡數到的是**事件數上限**。
- 只讀 data/margin_by_stock_history.json、data/listed_universe.json（active）、data/trading_calendar.json。
- 輸出 research/data/cand_n4_event_rate.json。

資料形狀的坑（2026-10-27 實測）：`dates` 是**管線執行日**不是資料日——週六、休市日（10/09、10/10、10/23）
也有鍵，而且 TWSE／TPEx 更新時間不同步，某些鍵約一半的股票是前一鍵的原樣複本。
所以不用鍵當交易日，改成「每檔股票逐列去掉與前一列完全相同的複本」，每一筆 [today, prev] 自帶當日變動，
事件日期記該列**第一次出現的鍵**（可能比真實資料日晚一個執行日，照實揭露）。
自測：python research/cand_n4_event_rate.py --selftest
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import cand_n1_event_rate as N1
import cand_n2_event_rate as N2

ROOT = N1.ROOT
SRC = ROOT / "data" / "margin_by_stock_history.json"
OUT = ROOT / "research" / "data" / "cand_n4_event_rate.json"
MIN_PREV_LOTS = 500   # 草稿 §2-1，寫死
D = 0.10              # 草稿 §3，單日融資減幅
DEDUP_TD = 20         # 草稿 §2，同代號 20 個交易日內只算第一個


def iso(k: str) -> str:
    return f"{k[:4]}-{k[4:6]}-{k[6:8]}"


def distinct_rows(series: dict, dates: list[str]) -> tuple[list[tuple[str, float, float]], int]:
    """回傳（[(首次出現日 ISO, today, prev)]、斷鏈次數）。斷鏈＝本列 prev ≠ 上一個不同列的 today（中間漏了資料日）。"""
    out, last, gaps = [], None, 0
    for k in dates:
        row = series.get(k)
        if not row or len(row) < 2 or row[0] is None or row[1] is None:
            continue
        if last is not None and list(row) == list(last):
            continue
        if last is not None and float(row[1]) != float(last[0]):
            gaps += 1
        out.append((iso(k), float(row[0]), float(row[1])))
        last = row
    return out, gaps


def is_signal(today: float, prev: float) -> bool:
    return prev >= MIN_PREV_LOTS and round(today / prev - 1, 9) <= -D  # round：避免 900/1000−1 浮點誤差判成未達 10%


def extract(doc: dict, closed: set[str]) -> tuple[list[dict], dict]:
    dates = list(doc.get("dates") or [])
    hits, n_rows, n_gaps, n_raw_signal_rows = [], 0, 0, 0
    for code, series in (doc.get("series") or {}).items():
        if not N1.is_common_stock(code):
            continue
        rows, gaps = distinct_rows(series, dates)
        n_rows += len(rows)
        n_gaps += gaps
        for d, today, prev in rows:
            if is_signal(today, prev):
                n_raw_signal_rows += 1
                hits.append({"code": code, "date": d, "margin_prev": prev, "margin_today": today,
                             "chg_pct": round((today / prev - 1) * 100, 2)})
    hits.sort(key=lambda x: (x["date"], x["code"]))
    out, last, dropped = [], {}, 0
    for h in hits:
        p = last.get(h["code"])
        if p is not None and N2.trading_days_between(p, h["date"], closed) < DEDUP_TD:
            dropped += 1
            continue
        last[h["code"]] = h["date"]
        out.append(h)
    stats = {"n_distinct_stock_day_rows": n_rows, "n_chain_gaps": n_gaps,
             "n_signal_rows_before_dedup": n_raw_signal_rows, "n_dropped_by_dedup": dropped}
    return out, stats


def summarize(events: list[dict], active: set[str] | None) -> dict:
    weekly: dict[str, int] = {}
    same_day: dict[str, int] = {}
    for e in events:
        w = N1.iso_week(e["date"])
        weekly[w] = weekly.get(w, 0) + 1
        same_day[e["date"]] = same_day.get(e["date"], 0) + 1
    for e in events:
        e["same_day_events"] = same_day[e["date"]]
    dates = sorted(same_day)
    return {
        "n_events": len(events),
        "n_in_active_universe": sum(1 for e in events if e["code"] in active) if active is not None else None,
        "weekly": {k: weekly[k] for k in sorted(weekly)},
        "per_day": {k: same_day[k] for k in dates},
        "max_same_day_events": max(same_day.values()) if same_day else 0,
        "first_event": dates[0] if dates else None,
        "last_event": dates[-1] if dates else None,
    }


def main() -> int:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    try:
        active = set(json.loads(N1.UNIVERSE.read_text(encoding="utf-8")).get("active") or [])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] listed_universe 讀取失敗，在市比例略過：{e}")
        active = None
    closed = N2.load_closed()
    evs, st = extract(doc, closed)
    keys = list(doc.get("dates") or [])
    span_td = (N2.trading_days_between(iso(keys[0]), iso(keys[-1]), closed) + 1) if keys else 0
    s = summarize(evs, active)
    per_year = round(s["n_events"] / span_td * 245, 1) if span_td else None  # 台股一年約 245 個交易日
    out = {
        "generated_at": datetime.now(N1.TW).isoformat(timespec="seconds"),
        "item": "先.一三五-1e ①",
        "prereg_draft": "docs/PREREG_DRAFT_MARGIN_LIQUIDATION_REBOUND_FORWARD.md",
        "source_file": "data/margin_by_stock_history.json",
        "source_generated_at": (doc.get("meta") or {}).get("generated_at"),
        "source_key_range": [keys[0], keys[-1]] if keys else None,
        "source_span_trading_days": span_td,
        "rule": {"common_stock": "4 碼數字、非 0 開頭、排除 91 開頭", "min_prev_margin_lots": MIN_PREV_LOTS,
                 "max_daily_change": -D, "dedup_trading_days": DEDUP_TD,
                 "not_applied_need_price": ["t0 跌幅 ≤ −5%", "t0 除權息日排除", "前 20 日均成交值 ≥ 1,000 萬",
                                            "t1 漲停放棄", "t0 當天在市（用今天的 active 快照近似）"]},
        **st,
        **s,
        "est_events_per_year_upper_bound": per_year,
        "est_events_24m_upper_bound": round(per_year * 2) if per_year is not None else None,
        "events": evs,
        "note": ("只讀融資餘額欄、在市名冊、休市日曆；未讀任何價格、未算報酬、零外部請求。"
                 "數到的是只套籌碼條件的上限，加上跌幅等價格條件後會再少。"
                 "事件日期＝該列在管線執行日鍵中第一次出現的日子，可能比真實資料日晚一個執行日；"
                 "年化＝事件數 ÷ 樣本交易日數 × 245，樣本只有約一個月，誤差大；active 是今天的快照，不是時點名冊。"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {OUT.relative_to(ROOT)}：不同股日列 {st['n_distinct_stock_day_rows']}、斷鏈 {st['n_chain_gaps']}、"
          f"籌碼訊號列 {st['n_signal_rows_before_dedup']}、去重後事件 {s['n_events']}（剔除 {st['n_dropped_by_dedup']}）、"
          f"單日最多 {s['max_same_day_events']}、樣本 {span_td} 交易日、年化上限約 {per_year}、24 個月上限約 {out['est_events_24m_upper_bound']}")
    return 0


def selftest() -> int:
    assert is_signal(450, 500) and is_signal(900, 1000)
    assert not is_signal(400, 499)          # 前日不足 500 張
    assert not is_signal(901, 1000)         # 減 9.9%
    dates = ["20261001", "20261002", "20261003", "20261005", "20261006"]
    s = {"20261001": [1000, 1000, 0], "20261002": [880, 1000, 0], "20261003": [880, 1000, 0],  # 週六複本
         "20261005": [870, 880, 0], "20261006": [700, 800, 0]}  # 10/06 prev≠870 → 斷鏈
    rows, gaps = distinct_rows(s, dates)
    assert [r[0] for r in rows] == ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06"] and gaps == 1, (rows, gaps)
    doc = {"dates": dates + ["20261110"], "series": {
        "2330": {**s, "20261110": [500, 600, 0]},          # 10/02 事件；10/06 在 20 交易日內被去重；11/10 已超過
        "00878": {"20261002": [100, 1000, 0]},              # 非普通股
        "9105": {"20261002": [100, 1000, 0]}}}              # 91 開頭
    ev, st = extract(doc, set())
    assert [(e["code"], e["date"]) for e in ev] == [("2330", "2026-10-02"), ("2330", "2026-11-10")], ev
    assert st["n_signal_rows_before_dedup"] == 3 and st["n_dropped_by_dedup"] == 1, st
    sm = summarize(ev, {"2330"})
    assert sm["n_events"] == 2 and sm["n_in_active_universe"] == 2 and sm["max_same_day_events"] == 1, sm
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
