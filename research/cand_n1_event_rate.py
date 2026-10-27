# -*- coding: utf-8 -*-
"""候選 N1（重大訊息反應過度後反轉，前向）事件抽取＋事件率量測（先.一三五-1a ①）。

草稿：docs/PREREG_DRAFT_MATERIAL_NEWS_REVERSAL_FORWARD.md §2。
- 只讀 data/events.json 的 code／date／type／source／title 與 data/listed_universe.json 的 active 名冊；
  **不讀任何價格、不算任何報酬、零外部請求**。
- 輸出 research/data/cand_n1_event_rate.json：每週事件數、4 類分布、普通股比例。
- 「事件」＝（代號、公告日）合併同日多則；草稿的「同一 t1 合併」需要交易日曆，留給定稿後的追蹤程式，
  這裡只做同日合併（同代號跨日公告會被多算，偏高估事件率，照實標在 note）。
自測：python research/cand_n1_event_rate.py --selftest
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # noqa: BLE001 —— 主控台不支援 reconfigure 時只警告
    print(f"[warn] reconfigure 失敗：{e}")

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events.json"
UNIVERSE = ROOT / "data" / "listed_universe.json"
OUT = ROOT / "research" / "data" / "cand_n1_event_rate.json"
TYPES = ("併購", "增減資", "財務", "人事")  # #52-TW gate1 通過的 4 類，事前固定
TW = timezone(timedelta(hours=8))


def is_common_stock(code: str) -> bool:
    """普通股：4 碼數字、非 0 開頭、排除 91 開頭（草稿 §2）。"""
    c = str(code or "")
    return len(c) == 4 and c.isdigit() and c[0] != "0" and not c.startswith("91")


def extract_events(raw_events: list[dict]) -> list[dict]:
    """篩出 4 類重大訊息，依（代號、公告日）合併；回傳事件清單（含合併前則數與類別集合）。"""
    groups: dict[tuple[str, str], dict] = {}
    for r in raw_events:
        if "重大訊息" not in str(r.get("source") or ""):
            continue
        t = r.get("type")
        if t not in TYPES:
            continue
        code, d = str(r.get("code") or ""), str(r.get("date") or "")
        if not code or not d:
            continue
        g = groups.setdefault((code, d), {"code": code, "date": d, "types": set(), "n_notices": 0, "titles": set()})
        title = str(r.get("title") or "")
        if title in g["titles"]:  # 同代號同日同標題重覆抓到的只算一則
            continue
        g["titles"].add(title)
        g["types"].add(t)
        g["n_notices"] += 1
    out = []
    for g in groups.values():
        out.append({"code": g["code"], "date": g["date"], "types": sorted(g["types"]), "n_notices": g["n_notices"],
                    "common_stock": is_common_stock(g["code"])})
    return sorted(out, key=lambda x: (x["date"], x["code"]))


def iso_week(d: str) -> str:
    y, w, _ = date.fromisoformat(d).isocalendar()
    return f"{y}-W{w:02d}"


def summarize(events: list[dict], active: set[str] | None = None) -> dict:
    weekly = defaultdict(lambda: {"events": 0, "common_stock": 0})
    type_cnt, type_cnt_common = Counter(), Counter()
    n_common = n_common_active = n_notices = 0
    for e in events:
        w = weekly[iso_week(e["date"])]
        w["events"] += 1
        n_notices += e["n_notices"]
        for t in e["types"]:
            type_cnt[t] += 1
        if e["common_stock"]:
            n_common += 1
            w["common_stock"] += 1
            for t in e["types"]:
                type_cnt_common[t] += 1
            if active is not None and e["code"] in active:
                n_common_active += 1
    n = len(events)
    weeks = sorted(weekly)
    # 頭尾兩週可能不完整（events.json 只保留 90 天、最新一週未過完），完整週另算平均
    full = weeks[1:-1] if len(weeks) > 2 else []
    avg_full = round(sum(weekly[w]["common_stock"] for w in full) / len(full), 2) if full else None
    return {
        "n_events": n,
        "n_notices": n_notices,
        "n_common_stock_events": n_common,
        "common_stock_ratio": round(n_common / n, 4) if n else None,
        "n_common_stock_in_active_universe": n_common_active if active is not None else None,
        "type_distribution": {t: type_cnt.get(t, 0) for t in TYPES},
        "type_distribution_common_stock": {t: type_cnt_common.get(t, 0) for t in TYPES},
        "weekly": {w: weekly[w] for w in weeks},
        "avg_common_stock_events_per_full_week": avg_full,
        "est_common_stock_events_24m": round(avg_full * 104) if avg_full is not None else None,
    }


def main() -> int:
    doc = json.loads(EVENTS.read_text(encoding="utf-8"))
    raw = doc.get("events") or []
    try:
        active = set(json.loads(UNIVERSE.read_text(encoding="utf-8")).get("active") or [])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] listed_universe 讀取失敗，在市比例略過：{e}")
        active = None
    evs = extract_events(raw)
    s = summarize(evs, active)
    dates = [e["date"] for e in evs]
    out = {
        "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
        "item": "先.一三五-1a ①",
        "prereg_draft": "docs/PREREG_DRAFT_MATERIAL_NEWS_REVERSAL_FORWARD.md",
        "source_file": "data/events.json",
        "source_fetched_at": doc.get("fetched_at"),
        "source_keep_days": doc.get("keep_days"),
        "date_range": [min(dates), max(dates)] if dates else None,
        "types": list(TYPES),
        **s,
        "note": ("只讀事件標題／類別與在市名冊，未讀任何價格、未算報酬、零外部請求。事件＝（代號、公告日）合併；"
                 "草稿的 t1 合併需交易日曆，此處未做（跨日連續公告多算 → 事件率偏高估）。"
                 "AR ≤ −5% 的比例未知（需價格，定稿後前向才量）；24 個月估計只是事件數上限，不是交易數。"
                 "active 名冊是今天的快照，不是事件當天的時點名冊。"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {OUT.relative_to(ROOT)}：事件 {s['n_events']}（{s['n_notices']} 則）、普通股 {s['n_common_stock_events']}"
          f"（{s['common_stock_ratio']}）、完整週平均普通股事件 {s['avg_common_stock_events_per_full_week']}")
    print("4 類（普通股）：", s["type_distribution_common_stock"])
    return 0


def selftest() -> int:
    raw = [
        {"code": "2330", "date": "2026-10-05", "type": "人事", "title": "A", "source": "TWSE 重大訊息"},
        {"code": "2330", "date": "2026-10-05", "type": "財務", "title": "B", "source": "TWSE 重大訊息"},
        {"code": "2330", "date": "2026-10-05", "type": "財務", "title": "B", "source": "TWSE 重大訊息"},  # 重覆
        {"code": "2330", "date": "2026-10-06", "type": "其他", "title": "C", "source": "TWSE 重大訊息"},  # 類別不在 4 類
        {"code": "0050", "date": "2026-10-06", "type": "併購", "title": "D", "source": "TWSE 重大訊息"},  # 非普通股
        {"code": "9105", "date": "2026-10-13", "type": "增減資", "title": "E", "source": "TWSE 重大訊息"},  # 91 開頭
        {"code": "6488", "date": "2026-10-13", "type": "增減資", "title": "F", "source": "TPEx 重大訊息"},
        {"code": "6488", "date": "2026-10-13", "type": "增減資", "title": "G", "source": "TWSE 月營收"},  # 非重訊
        {"code": "", "date": "2026-10-13", "type": "人事", "title": "H", "source": "TWSE 重大訊息"},  # 缺代號
    ]
    ev = extract_events(raw)
    assert [(e["code"], e["date"]) for e in ev] == [("2330", "2026-10-05"), ("0050", "2026-10-06"), ("6488", "2026-10-13"), ("9105", "2026-10-13")], ev
    e2330 = next(e for e in ev if e["code"] == "2330")
    assert e2330["n_notices"] == 2 and e2330["types"] == ["人事", "財務"], e2330
    assert is_common_stock("2330") and is_common_stock("6488")
    assert not is_common_stock("0050") and not is_common_stock("9105") and not is_common_stock("00878") and not is_common_stock("2330A")
    s = summarize(ev, {"2330"})
    assert s["n_events"] == 4 and s["n_common_stock_events"] == 2 and s["n_common_stock_in_active_universe"] == 1, s
    assert s["type_distribution_common_stock"] == {"併購": 0, "增減資": 1, "財務": 1, "人事": 1}, s
    assert s["weekly"]["2026-W41"] == {"events": 2, "common_stock": 1}, s["weekly"]
    assert summarize([], None)["common_stock_ratio"] is None
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
