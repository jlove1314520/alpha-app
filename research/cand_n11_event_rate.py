"""先.一三五-1r 候選 N11 前置：重大訊息歸檔中「現金減資」事件率量測（零請求）。

只讀本機 research/data/mops_events_archive.jsonl（先.一三五-1d 歸檔），只數標題，
不送網路請求、不讀價格、不算報酬、不登記試驗。
輸出：research/data/cand_n11_event_rate.json（欄位比照 cand_n4_event_rate.json）
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "research/data/mops_events_archive.jsonl"
OUT = ROOT / "research/data/cand_n11_event_rate.json"
NEED_EVENTS_24M = 100

SUBSIDIARY = re.compile(r"^(\(補充說明[^)]*\)-?)?(本公司)?(更正)?代(重要)?(子|孫)公司|子公司.*減資")
CANCELLED = re.compile(r"撤銷|取消")
CASH = re.compile(r"現金減資|退還股款")
LOSS = re.compile(r"彌補虧損")
TREASURY_RSA = re.compile(r"庫藏股|限制員工權利新股")
DECISION = re.compile(r"董事會決議|股東會決議")


def classify(title: str) -> str:
    t = re.sub(r"\s+", "", title)
    if SUBSIDIARY.search(t):
        return "其他_子公司減資"
    if CANCELLED.search(t):
        return "其他_撤銷取消"
    if LOSS.search(t):
        return "彌補虧損減資"
    if CASH.search(t):
        return "現金減資_董事會決議" if DECISION.search(t) else "現金減資_後續公告"
    if TREASURY_RSA.search(t):
        return "其他_庫藏股或限制股註銷"
    return "其他_未標減資類型"


def common_stock(code: str) -> bool:
    return bool(re.fullmatch(r"[1-9]\d{3}", code)) and not code.startswith("91")


def main() -> None:
    rows = [json.loads(l) for l in ARCHIVE.open(encoding="utf-8") if l.strip()]
    dates = sorted(r["date"] for r in rows)
    span_days = (datetime.fromisoformat(dates[-1]) - datetime.fromisoformat(dates[0])).days + 1
    n_type_rows = sum(1 for r in rows if r.get("type") == "增減資")

    hits, seen = [], set()
    for r in rows:
        if "減資" not in r["title"] or not common_stock(r["code"]):
            continue
        key = (r["code"], r["date"], re.sub(r"\s+", "", r["title"]))
        if key in seen:
            continue
        seen.add(key)
        hits.append({"date": r["date"], "code": r["code"], "source": r["source"],
                     "title": r["title"], "class": classify(r["title"])})
    by_class = Counter(h["class"] for h in hits)

    # 事件＝同代號＋同決議日只算一件
    decisions = sorted({(h["code"], h["date"]) for h in hits if h["class"] == "現金減資_董事會決議"})
    # 代理上界：期間內出現任何現金減資公告（含後續）的不同公司數；每件現金減資最終都會發後續公告
    cash_codes = sorted({h["code"] for h in hits if h["class"].startswith("現金減資")})
    # 寬上界：再加上標題沒寫現金／彌補虧損的本公司減資（可能是現金減資，也可能是彌補虧損）
    loss_codes = {h["code"] for h in hits if h["class"] == "彌補虧損減資"}
    wide_codes = sorted(set(cash_codes) | ({h["code"] for h in hits if h["class"] == "其他_未標減資類型"} - loss_codes))
    monthly = lambda n: round(n / span_days * 30.4, 2)  # noqa: E731
    need_monthly = round(NEED_EVENTS_24M / 24, 2)
    m_dec, m_proxy = monthly(len(decisions)), monthly(len(cash_codes))

    def months_needed(m: float):
        return round(NEED_EVENTS_24M / m, 1) if m > 0 else None

    samples = [h["title"] for h in hits if h["class"].startswith("現金減資")][:5]
    out = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "item": "先.一三五-1r",
        "network_requests": 0,
        "source_file": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"),
        "source_rows": len(rows),
        "source_date_range": [dates[0], dates[-1]],
        "source_span_days": span_days,
        "rows_type_增減資": n_type_rows,
        "rows_title_含減資_普通股去重": len(hits),
        "rule": {
            "common_stock": "4 碼數字、非 0 開頭、排除 91 開頭",
            "dedup": "同代號＋同公告日＋同標題（去空白）只算一列；事件＝同代號＋同決議日只算一件",
            "classes": "子公司代公告→其他；撤銷／取消→其他；含「彌補虧損」→彌補虧損減資；含「現金減資／退還股款」且含「董事會／股東會決議」→現金減資_董事會決議（N11 事件）；"
                       "其餘現金減資→後續公告（換股、發放股款、變更登記）；庫藏股／限制員工權利新股註銷→其他；其餘→未標減資類型",
            "title_only": True,
        },
        "by_class": dict(by_class),
        "n_events_cash_decision": len(decisions),
        "events_cash_decision": [{"code": c, "date": d} for c, d in decisions],
        "n_codes_any_cash_reduction_announcement": len(cash_codes),
        "codes_any_cash_reduction_announcement": cash_codes,
        "n_codes_wide_upper_bound": len(wide_codes),
        "codes_wide_upper_bound": wide_codes,
        "monthly_avg_wide_upper_bound": monthly(len(wide_codes)),
        "months_needed_for_100_wide_upper_bound": months_needed(monthly(len(wide_codes))),
        "monthly_avg_cash_decision": m_dec,
        "monthly_avg_proxy_distinct_codes": m_proxy,
        "need_monthly_for_100_in_24m": need_monthly,
        "months_needed_for_100_decision": months_needed(m_dec),
        "months_needed_for_100_proxy": months_needed(m_proxy),
        "enough_24m": m_dec >= need_monthly,
        "sample_titles": samples,
        "notes": [
            f"歸檔只從先.一三五-1d 建檔起，樣本 {span_days} 天，月均外推誤差大。",
            "條目原寫『標題含減資 402 列』，實為 type＝增減資的列數（含現金增資）；標題含減資的普通股列見 rows_title_含減資_普通股去重。",
            "董事會決議現金減資常以「董事會決議減資」不寫現金／彌補虧損的標題公告，被歸進未標類型；決議數是下界，不同公司數代理是較寬口徑。",
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("source_span_days", "rows_title_含減資_普通股去重", "by_class",
                                          "n_events_cash_decision", "n_codes_any_cash_reduction_announcement",
                                          "monthly_avg_cash_decision", "monthly_avg_proxy_distinct_codes",
                                          "months_needed_for_100_proxy", "n_codes_wide_upper_bound",
                                          "monthly_avg_wide_upper_bound", "months_needed_for_100_wide_upper_bound", "enough_24m")}, ensure_ascii=False))
    for h in hits:
        if h["class"] in ("現金減資_董事會決議", "現金減資_後續公告", "其他_未標減資類型"):
            print(h["class"], h["date"], h["code"], h["title"][:60])


if __name__ == "__main__":
    main()
