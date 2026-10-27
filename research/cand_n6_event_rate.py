# -*- coding: utf-8 -*-
"""候選 N6（內部人申報「一般交易」有效期滿賣壓解除後反彈，前向）事件抽取＋事件率量測（先.一三五-1g ①）。

草稿：docs/PREREG_DRAFT_INSIDER_SALE_OVERHANG_FORWARD.md §2。
- 只量「申報條件」：普通股、transfer_method 以「一般交易」開頭；同代號有效期重疊的申報合併成一個事件
  （股數相加、有效期取最晚結束日）；股數用 transfer_shares_on_market，空白改用 planned_own。
- **不讀任何價格／成交量、不算任何報酬、零外部請求**；份量門檻（≥0.5 倍 20 日均量）、申報期間報酬 ≤ 0、
  流動性門檻都要行情，留給定稿後追蹤程式 → 事件數是**上限**。
- 只讀 data/insider_transfer_tw_history.json、data/listed_universe.json。輸出 research/data/cand_n6_event_rate.json。
自測：python research/cand_n6_event_rate.py --selftest
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime

import cand_n1_event_rate as N1

ROOT = N1.ROOT
SRC = ROOT / "data" / "insider_transfer_tw_history.json"
OUT = ROOT / "research" / "data" / "cand_n6_event_rate.json"


def roc_to_iso(s: str) -> str:
    s = s.strip()
    return date(int(s[:-4]) + 1911, int(s[-4:-2]), int(s[-2:])).isoformat()


def parse_period(p: str) -> tuple[str, str]:
    a, b = str(p).split("~")
    return roc_to_iso(a), roc_to_iso(b)


def shares(r: dict) -> float:
    for k in ("transfer_shares_on_market", "planned_own"):
        v = str(r.get(k) or "").replace(",", "").strip()
        if v:
            try:
                return float(v)
            except ValueError:
                continue
    return 0.0


def extract(records: list[dict]) -> tuple[list[dict], dict]:
    seen, rows, n_bad = set(), [], 0
    for r in records:
        rid = r.get("id") or (r.get("code"), r.get("report_date"), r.get("valid_period"), r.get("planned_own"), r.get("role"))
        if rid in seen:
            continue
        seen.add(rid)
        code = str(r.get("code") or "")
        if not N1.is_common_stock(code) or not str(r.get("transfer_method") or "").startswith("一般交易"):
            continue
        try:
            start, end = parse_period(r["valid_period"])
        except Exception:  # noqa: BLE001 —— 有效期格式壞掉就不收，照實計數
            n_bad += 1
            continue
        rows.append({"code": code, "start": start, "end": end, "shares": shares(r),
                     "report_date": f"{r['report_date'][:4]}-{r['report_date'][4:6]}-{r['report_date'][6:]}",
                     "role": r.get("role"), "market": r.get("market")})
    rows.sort(key=lambda x: (x["code"], x["start"], x["end"]))
    events: list[dict] = []
    for x in rows:
        e = events[-1] if events else None
        if e and e["code"] == x["code"] and x["start"] <= e["valid_end"]:   # 有效期重疊 → 合併
            e["shares"] += x["shares"]
            e["valid_end"] = max(e["valid_end"], x["end"])
            e["n_filings"] += 1
            e["roles"] = sorted(set(e["roles"]) | {x["role"]})
            e["first_report_date"] = min(e["first_report_date"], x["report_date"])
            continue
        events.append({"code": x["code"], "market": x["market"], "first_report_date": x["report_date"],
                       "valid_start": x["start"], "valid_end": x["end"], "shares": x["shares"],
                       "n_filings": 1, "roles": [x["role"]]})
    events.sort(key=lambda e: (e["valid_end"], e["code"]))
    return events, {"n_general_trade_filings": len(rows), "n_bad_period": n_bad,
                    "n_merged_away": len(rows) - len(events)}


def main() -> int:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    meta = doc.get("meta") or {}
    try:
        active = set(json.loads(N1.UNIVERSE.read_text(encoding="utf-8")).get("active") or [])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] listed_universe 讀取失敗，在市比例略過：{e}")
        active = None
    evs, st = extract(doc.get("records") or [])
    rd = meta.get("report_dates") or {}
    covered = sorted(set(rd.get("TWSE") or []) | set(rd.get("TPEX") or []))
    per_year = round(len(evs) / len(covered) * 245, 1) if covered else None
    out = {
        "generated_at": datetime.now(N1.TW).isoformat(timespec="seconds"),
        "item": "先.一三五-1g ①",
        "prereg_draft": "docs/PREREG_DRAFT_INSIDER_SALE_OVERHANG_FORWARD.md",
        "source_file": "data/insider_transfer_tw_history.json",
        "source_record_count": len(doc.get("records") or []),
        "source_report_dates": rd,
        "covered_report_days_union": len(covered),
        "rule": {"common_stock": "4 碼數字、非 0 開頭、排除 91 開頭", "transfer_method_prefix": "一般交易",
                 "merge": "同代號有效期重疊合併、股數相加、結束日取最晚",
                 "not_applied_need_market_data": ["申報股數 ≥ 0.5 倍申報日前 20 日均量", "申報前一日到 te 報酬 ≤ 0",
                                                  "前 20 日均成交值 ≥ 1,000 萬", "當天在市（用今天的 active 快照近似）"]},
        **st,
        "n_events": len(evs),
        "n_in_active_universe": sum(1 for e in evs if e["code"] in active) if active is not None else None,
        "est_events_per_year_upper_bound": per_year,
        "est_events_24m_upper_bound": round(per_year * 2) if per_year is not None else None,
        "est_events_36m_upper_bound": round(per_year * 3) if per_year is not None else None,
        "events": evs,
        "note": ("只讀申報欄位與在市名冊；未讀任何價格／成交量、未算報酬、零外部請求。份量門檻等行情條件未套，事件數是上限。"
                 "年化＝事件數 ÷ 有申報快照的日子（TWSE∪TPEx 聯集）× 245；TPEx 比 TWSE 少 2 天快照，樣本只有約兩週，誤差極大。"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {OUT.relative_to(ROOT)}：一般交易申報 {st['n_general_trade_filings']} 筆 → 合併後事件 {len(evs)}（合併掉 {st['n_merged_away']}）、"
          f"快照 {len(covered)} 天、年化上限約 {per_year}、24 個月上限約 {out['est_events_24m_upper_bound']}、36 個月上限約 {out['est_events_36m_upper_bound']}")
    return 0


def selftest() -> int:
    assert roc_to_iso("1151023") == "2026-10-23" and parse_period("1151023~1151122") == ("2026-10-23", "2026-11-22")
    assert shares({"transfer_shares_on_market": "", "planned_own": "1,000"}) == 1000.0
    base = {"transfer_method": "一般交易(每日得轉讓股數限制)", "role": "董事本人", "market": "TWSE"}
    recs = [
        {**base, "id": "a", "code": "2884", "valid_period": "1151022~1151121", "transfer_shares_on_market": "650000", "report_date": "20261019"},
        {**base, "id": "b", "code": "2884", "valid_period": "1151023~1151122", "transfer_shares_on_market": "154000", "report_date": "20261020"},
        {**base, "id": "b", "code": "2884", "valid_period": "1151023~1151122", "transfer_shares_on_market": "154000", "report_date": "20261020"},  # 重覆
        {**base, "id": "c", "code": "2884", "valid_period": "1151201~1151230", "transfer_shares_on_market": "1", "report_date": "20261128"},   # 不重疊
        {**base, "id": "d", "code": "3260", "transfer_method": "信託", "valid_period": "1151013~1151015", "report_date": "20261013"},
        {**base, "id": "e", "code": "00878", "valid_period": "1151013~1151015", "report_date": "20261013"},
        {**base, "id": "f", "code": "1773", "valid_period": "壞掉", "report_date": "20261021"},
    ]
    ev, st = extract(recs)
    assert [(e["code"], e["valid_end"], e["shares"]) for e in ev] == [("2884", "2026-11-22", 804000.0), ("2884", "2026-12-30", 1.0)], ev
    assert st == {"n_general_trade_filings": 3, "n_bad_period": 1, "n_merged_away": 1}, st
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
