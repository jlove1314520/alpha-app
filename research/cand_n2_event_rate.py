# -*- coding: utf-8 -*-
"""候選 N2（董事會決議買回庫藏股，前向）事件抽取＋事件率量測（先.一三五-1b ①）。

草稿：docs/PREREG_DRAFT_BUYBACK_ANNOUNCEMENT_FORWARD.md §2（標題規則與排除字照草稿原文寫死）。
- 只讀 data/events.json 的 code／date／source／title、data/listed_universe.json 的 active 名冊、
  data/trading_calendar.json 的休市日；**不讀任何價格、不算任何報酬、零外部請求**。
- 輸出 research/data/cand_n2_event_rate.json：每週事件數、普通股比例、每則標題。
自測：python research/cand_n2_event_rate.py --selftest
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import cand_n1_event_rate as N1

ROOT = N1.ROOT
CAL = ROOT / "data" / "trading_calendar.json"
OUT = ROOT / "research" / "data" / "cand_n2_event_rate.json"
INCLUDE = re.compile(r"(董事會)?決議.*(買回|庫藏)")
EXCLUDE = ("執行完畢", "期滿", "註銷", "轉讓", "變更", "未執行", "子公司")
DEDUP_TD = 60  # 同一代號 60 個交易日內只算第一則


def load_closed(cal_path: Path = CAL) -> set[str]:
    try:
        tw = json.loads(cal_path.read_text(encoding="utf-8")).get("tw") or {}
        return {d for y in tw.values() for d in (y.get("closed") or [])}
    except Exception as e:  # noqa: BLE001 —— 讀不到日曆就只排週末（偏多算交易日 → 去重窗口偏寬）
        print(f"[warn] trading_calendar 讀取失敗，只排除週末：{e}")
        return set()


def trading_days_between(a: str, b: str, closed: set[str]) -> int:
    """a 之後到 b（含 b）之間的交易日數；a == b 回 0。"""
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    n, d = 0, da
    while d < db:
        d += timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in closed:
            n += 1
    return n


def match_title(title: str, include: re.Pattern = INCLUDE, exclude: tuple[str, ...] = EXCLUDE) -> bool:
    return bool(include.search(title)) and not any(x in title for x in exclude)


def extract(raw_events: list[dict], closed: set[str], include=INCLUDE, exclude=EXCLUDE, dedup_td=DEDUP_TD) -> tuple[list[dict], int]:
    """回傳（去重後事件、被去重剔除的則數）。同代號同日同標題只算一則。"""
    hits, seen = [], set()
    for r in raw_events:
        if "重大訊息" not in str(r.get("source") or ""):
            continue
        code, d, title = str(r.get("code") or ""), str(r.get("date") or ""), str(r.get("title") or "")
        if not code or not d or (code, d, title) in seen or not match_title(title, include, exclude):
            continue
        seen.add((code, d, title))
        hits.append({"code": code, "date": d, "title": title, "common_stock": N1.is_common_stock(code)})
    hits.sort(key=lambda x: (x["date"], x["code"], x["title"]))
    out, last, dropped = [], {}, 0
    for h in hits:
        p = last.get(h["code"])
        if p is not None and trading_days_between(p, h["date"], closed) < dedup_td:
            dropped += 1
            continue
        last[h["code"]] = h["date"]
        out.append(h)
    return out, dropped


def summarize(events: list[dict], active: set[str] | None) -> dict:
    weekly: dict[str, dict] = {}
    for e in events:
        w = weekly.setdefault(N1.iso_week(e["date"]), {"events": 0, "common_stock": 0})
        w["events"] += 1
        w["common_stock"] += int(e["common_stock"])
    n = len(events)
    nc = sum(e["common_stock"] for e in events)
    dates = sorted(e["date"] for e in events)
    return {
        "n_events": n,
        "n_common_stock_events": nc,
        "common_stock_ratio": round(nc / n, 4) if n else None,
        "n_common_stock_in_active_universe": (sum(1 for e in events if e["common_stock"] and e["code"] in active)
                                              if active is not None else None),
        "weekly": {k: weekly[k] for k in sorted(weekly)},
        "first_event": dates[0] if dates else None,
        "last_event": dates[-1] if dates else None,
    }


def run(out_path: Path, include, exclude, dedup_td, item: str, prereg: str, extra_note: str) -> dict:
    doc = json.loads(N1.EVENTS.read_text(encoding="utf-8"))
    raw = doc.get("events") or []
    try:
        active = set(json.loads(N1.UNIVERSE.read_text(encoding="utf-8")).get("active") or [])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] listed_universe 讀取失敗，在市比例略過：{e}")
        active = None
    closed = load_closed()
    evs, dropped = extract(raw, closed, include, exclude, dedup_td)
    src_dates = sorted(str(r.get("date")) for r in raw if "重大訊息" in str(r.get("source") or "") and r.get("date"))
    span_days = ((date.fromisoformat(src_dates[-1]) - date.fromisoformat(src_dates[0])).days + 1) if src_dates else 0
    s = summarize(evs, active)
    per_year = round(s["n_common_stock_events"] / span_days * 365, 1) if span_days else None
    out = {
        "generated_at": datetime.now(N1.TW).isoformat(timespec="seconds"),
        "item": item,
        "prereg_draft": prereg,
        "source_file": "data/events.json",
        "source_fetched_at": doc.get("fetched_at"),
        "source_material_news_range": [src_dates[0], src_dates[-1]] if src_dates else None,
        "source_span_calendar_days": span_days,
        "rule": {"include": include.pattern, "exclude": list(exclude), "dedup_trading_days": dedup_td},
        "n_dropped_by_dedup": dropped,
        **s,
        "est_common_stock_events_per_year": per_year,
        "est_common_stock_events_24m": round(per_year * 2) if per_year is not None else None,
        "events": evs,
        "note": ("只讀事件標題與在市名冊、休市日曆，未讀任何價格、未算報酬、零外部請求。"
                 "active 名冊是今天的快照，不是事件當天的時點名冊；年化估計＝樣本期間普通股事件數 ÷ 日曆天數 × 365，"
                 "樣本期間短（events.json 只留 90 天），估計誤差大。" + extra_note),
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {out_path.relative_to(ROOT)}：事件 {s['n_events']}（去重剔除 {dropped}）、普通股 {s['n_common_stock_events']}、"
          f"期間 {span_days} 天、年化約 {per_year}、24 個月約 {out['est_common_stock_events_24m']}")
    return out


def main() -> int:
    run(OUT, INCLUDE, EXCLUDE, DEDUP_TD, "先.一三五-1b ①", "docs/PREREG_DRAFT_BUYBACK_ANNOUNCEMENT_FORWARD.md",
        "揭露欄「預定買回股數占已發行股數比例」要讀內文，events.json 只有標題，定稿後的追蹤程式再處理。")
    return 0


def selftest() -> int:
    closed = {"2026-10-09"}
    assert trading_days_between("2026-10-08", "2026-10-12", closed) == 1  # 10/09 休市、10/10～11 週末
    assert trading_days_between("2026-10-05", "2026-10-05", closed) == 0
    assert match_title("本公司董事會決議買回庫藏股")
    assert match_title("公告本公司決議實施庫藏股")
    assert not match_title("公告本公司買回庫藏股執行完畢")
    assert not match_title("子公司董事會決議買回本公司股份")
    assert not match_title("董事會決議發放股利")
    raw = [
        {"code": "2330", "date": "2026-09-07", "title": "董事會決議買回庫藏股", "source": "TWSE 重大訊息"},
        {"code": "2330", "date": "2026-09-07", "title": "董事會決議買回庫藏股", "source": "TWSE 重大訊息"},  # 重覆
        {"code": "2330", "date": "2026-09-20", "title": "補充董事會決議買回庫藏股", "source": "TWSE 重大訊息"},  # 60 交易日內
        {"code": "2330", "date": "2026-12-31", "title": "董事會決議買回庫藏股", "source": "TWSE 重大訊息"},  # 60 交易日後
        {"code": "6488", "date": "2026-09-08", "title": "決議買回庫藏股", "source": "TWSE 月營收"},  # 非重訊
        {"code": "00878", "date": "2026-09-08", "title": "決議買回庫藏股", "source": "TWSE 重大訊息"},  # 非普通股
    ]
    ev, dropped = extract(raw, set())
    assert [(e["code"], e["date"]) for e in ev] == [("2330", "2026-09-07"), ("00878", "2026-09-08"), ("2330", "2026-12-31")], ev
    assert dropped == 1
    s = summarize(ev, {"2330"})
    assert s["n_events"] == 3 and s["n_common_stock_events"] == 2 and s["n_common_stock_in_active_universe"] == 2, s
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
