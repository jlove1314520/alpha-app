# -*- coding: utf-8 -*-
"""先.一〇三-10b（2026-10-16）：price_history 還原價單日漲跌超過門檻的列逐筆歸類（離線，不發任何請求）。

用法：python scripts/audit_price_jumps.py [--since 2026-06-01] [--threshold 0.105] [--out docs/PRICE_JUMP_AUDIT.json]

歸類（依序，先符合者為準）：
  known_split      已知分割／面額變更（update_price_history.SPLITS，官方 TWTCAU／TWTB8U 有據），套用後應消失
  suspected_split  跌幅 ≥80% 且前後隔多個交易日（停止買賣換股的形狀），官方證據未取得
  multi_day_gap    前一筆與這一筆之間隔超過 1 個交易日（停止買賣、處置或資料缺日），不是單日漲跌
  no_limit_board   興櫃（公司基本資料來源 tpex_t187ap03_R），無漲跌幅限制
  listing_first_days 本檔在檔案內首次出現後 5 個交易日內（新上市櫃前 5 日無漲跌幅）
  market_wide_day  同日 0050 漲跌超過 9%（大盤日），槓桿／反向 ETF 與 ETN 等量放大
  etf_limit_rule   ETF／ETN：國內槓桿反向 ETF 漲跌幅＝10%×倍數；跨境 ETF／ETN 無漲跌幅限制
  ex_event_adj     還原價與收盤價漲跌不同（當日有除權息／現增，官方漲跌停以「減除股利參考價」計，還原後可超過 10%）
  unexplained      以上都不是，需人工查
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import price_history_store as PHS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> int:
    since = _arg("--since", "2026-06-01")
    thr = float(_arg("--threshold", "0.105"))
    out_path = ROOT / _arg("--out", "docs/PRICE_JUMP_AUDIT.json")
    doc = PHS.load(ROOT / "data" / "price_history.json")
    prices = doc.get("prices") or {}
    cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
    closed = {d for y in (cal.get("tw") or {}).values() for d in (y.get("closed") or [])}
    companies = json.loads((ROOT / "data" / "company_info.json").read_text(encoding="utf-8")).get("companies") or {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("uph", ROOT / ".github" / "scripts" / "update_price_history.py")
        uph = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(uph)
        splits = {(s["code"], s["effective"]) for s in uph.SPLITS}
    except Exception as e:  # noqa: BLE001 -- 讀不到分割清單只影響 known_split 一類
        print(f"警告：讀不到 SPLITS（{e!r}）")
        splits = set()

    def tdays(a, b):
        x, y, n = date.fromisoformat(a), date.fromisoformat(b), 0
        while x < y:
            x += timedelta(days=1)
            if x.weekday() < 5 and x.isoformat() not in closed:
                n += 1
        return n

    def moves(code):
        rows = sorted((r for r in prices.get(code, []) if r.get("date", "") >= since and r.get("close")
                       and not r.get("no_trade")), key=lambda r: r["date"])
        for a, b in zip(rows, rows[1:]):
            aa, bb = a.get("adj_close") or a["close"], b.get("adj_close") or b["close"]
            yield a, b, bb / aa - 1, b["close"] / a["close"] - 1

    big_days = {b["date"] for a, b, ra, rc in moves("0050") if abs(ra) > 0.09}
    first_seen = {c: min((r["date"] for r in rows if r.get("close")), default=None) for c, rows in prices.items()}
    items = []
    for code in prices:
        for a, b, ra, rc in moves(code):
            if abs(ra) <= thr:
                continue
            gap = tdays(a["date"], b["date"])
            src = (companies.get(code) or {}).get("industry_source") or ""
            if (code, b["date"]) in splits:
                cls = "known_split"
            elif ra <= -0.8 and gap > 1:
                cls = "suspected_split"
            elif gap > 1:
                cls = "multi_day_gap"
            elif src.endswith("_R"):
                cls = "no_limit_board"
            elif first_seen.get(code) and first_seen[code] > since and tdays(first_seen[code], b["date"]) <= 5:
                cls = "listing_first_days"
            elif b["date"] in big_days:
                cls = "market_wide_day"
            elif code.startswith(("00", "02")):
                cls = "etf_limit_rule"
            elif abs(ra - rc) > 0.005:
                cls = "ex_event_adj"
            else:
                cls = "unexplained"
            items.append({"code": code, "name": (companies.get(code) or {}).get("name"), "from": a["date"],
                          "to": b["date"], "trading_days": gap, "adj_pct": round(ra * 100, 1),
                          "close_pct": round(rc * 100, 1), "class": cls})
    counts = {}
    for it in items:
        counts[it["class"]] = counts.get(it["class"], 0) + 1
    out = {"meta": {"since": since, "threshold": thr, "total": len(items), "counts": counts,
                    "note": "先.一〇三-10b 歸類，見 scripts/audit_price_jumps.py 檔頭"},
           "items": sorted(items, key=lambda x: (x["class"], x["code"], x["to"]))}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"共 {len(items)} 筆：{counts}")
    for it in out["items"]:
        if it["class"] in ("suspected_split", "unexplained"):
            print(it)
    return 0


if __name__ == "__main__":
    sys.exit(main())
