"""上櫃 2007-07～12-16 除權息標記（383 筆）對 FinMind 股利金額推精確參考價。

零請求：只讀本機既有快取
- 標記：research/data/tpex_exright_marks_2007h2.json（fetch_tpex_exright_marks_2007h2.py 產出）
- 股利：research/data/raw/TaiwanStockDividend__{代號}__{起}__{迄}.parquet
- 前收盤缺漏（07-02 兩筆）：research/data/raw/TaiwanStockPrice__… 快取補，標 source

參考價公式（每股，面額 10 元）：
  基本：(前收盤 − 現金股利) ÷ (1 ＋ 配股元數/10)
  含現增：(前收盤 − 現金股利 ＋ 認購率×認購價) ÷ (1 ＋ 配股元數/10 ＋ 認購率)
只建資料，不套用還原、不算報酬（套用與否見 AWAITING 先.一三三-1c）。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
MARKS = HERE / "data" / "tpex_exright_marks_2007h2.json"
OUT = HERE / "data" / "tpex_exright_2007h2_ref.json"
START, END = "2007-07-01", "2007-12-31"
NEAR_DAYS = 10  # 日期差幾天的容忍範圍（日曆日）


def _pick_cache(prefix: str, code: str) -> Path | None:
    """挑一份涵蓋 START～END 的快取；沒有就回 None。"""
    for f in sorted(RAW.glob(f"{prefix}__{code}__*__*.parquet")):
        parts = f.stem.split("__")
        if len(parts) != 4:
            continue
        s, e = parts[2], parts[3]
        if s <= START and (e == "latest" or e >= END):
            return f
    return None


def _num(x) -> float:
    try:
        v = float(x)
        return 0.0 if v != v else v
    except (TypeError, ValueError):
        return 0.0


def _d(s: str) -> date:
    s = str(s)[:10].replace("-", "")
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def dividend_rows(code: str):
    f = _pick_cache("TaiwanStockDividend", code)
    if f is None:
        return None
    try:
        return pd.read_parquet(f)
    except Exception as e:  # noqa: BLE001 — 單檔壞掉只當沒快取
        print(f"⚠️ 讀不到 {f.name}：{type(e).__name__}", flush=True)
        return None


def prev_close_from_price(code: str, d: date):
    f = _pick_cache("TaiwanStockPrice", code)
    if f is None:
        # 價格快取起點可能早於 2007-07-01 但迄日不同，放寬只要涵蓋事件日
        for g in sorted(RAW.glob(f"TaiwanStockPrice__{code}__*__*.parquet")):
            p = g.stem.split("__")
            if len(p) == 4 and p[2] <= d.isoformat() and (p[3] == "latest" or p[3] >= d.isoformat()):
                f = g
                break
    if f is None:
        return None, None
    try:
        px = pd.read_parquet(f)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ 讀不到 {f.name}：{type(e).__name__}", flush=True)
        return None, None
    px = px[px["date"].astype(str).str[:10] < d.isoformat()]
    px = px[px["close"].astype(float) > 0]
    if px.empty:
        return None, None
    r = px.sort_values("date").iloc[-1]
    return float(r["close"]), f"FinMind TaiwanStockPrice {str(r['date'])[:10]}"


def main() -> int:
    marks = json.loads(MARKS.read_text(encoding="utf-8"))
    out_rows, unmatched = [], []
    cache: dict = {}
    for ev in marks["events"]:
        code, d = ev["code"], _d(ev["date"])
        if code not in cache:
            cache[code] = dividend_rows(code)
        dv = cache[code]
        prev, prev_src = ev.get("prev_close"), "TPEx 官方日檔前一交易日收盤"
        if prev is None:
            prev, prev_src = prev_close_from_price(code, d)
        base = {"date": ev["date"], "code": code, "name": ev["name"], "kind": ev["kind"],
                "close": ev["close"], "prev_close": prev, "prev_close_source": prev_src,
                "approx_ref_mid": ev.get("approx_ref_mid")}
        if dv is None:
            unmatched.append({**base, "reason": "無 FinMind 股利快取"})
            continue
        cash = stock = sub_rate = sub_px = 0.0
        hit = False
        near = []
        for r in dv.itertuples():
            cd, sd = str(r.CashExDividendTradingDate or "")[:10], str(r.StockExDividendTradingDate or "")[:10]
            if cd == d.isoformat():
                cash += _num(r.CashEarningsDistribution) + _num(r.CashStatutorySurplus)
                hit = True
            if sd == d.isoformat():
                stock += _num(r.StockEarningsDistribution) + _num(r.StockStatutorySurplus)
                sub_rate += _num(r.CashIncreaseSubscriptionRate)
                sub_px = max(sub_px, _num(r.CashIncreaseSubscriptionpRrice))
                hit = True
            for x in (cd, sd):
                if len(x) == 10 and x[:4].isdigit() and x != d.isoformat():
                    gap = (_d(x) - d).days
                    if abs(gap) <= NEAR_DAYS:
                        near.append({"finmind_date": x, "gap_days": gap})
        if not hit:
            if near:
                reason = "日期差幾天"
            elif ev["kind"] == "除權":
                reason = "現增除權（FinMind 股利表不收）"
            elif dv.empty:  # FinMind 回空表時快取是沒有欄位的空檔
                reason = "FinMind 漏記（該檔 2006～2014 整段零筆股利）"
            else:
                reason = "FinMind 漏記（有其他股利紀錄、該日前後 10 天沒有）"
            unmatched.append({**base, "reason": reason, "finmind_near": near})
            continue
        if prev is None:
            unmatched.append({**base, "reason": "缺前收盤（官方日檔與 FinMind 價格快取都沒有）",
                              "cash_dividend": cash, "stock_dividend_yuan": stock})
            continue
        if sub_rate > 1:  # FinMind 部分列以百分比或每千股表示，>1 一律視為每千股
            sub_rate = sub_rate / 1000.0
        ref_basic = (prev - cash) / (1 + stock / 10.0)
        ref_full = (prev - cash + sub_rate * sub_px) / (1 + stock / 10.0 + sub_rate)
        ref = ref_full if sub_rate > 0 else ref_basic
        approx = ev.get("approx_ref_mid")
        diff = None if not approx else round((approx / ref - 1) * 100, 3)
        flags = []
        if ev["kind"] in ("除權", "除權息") and stock == 0 and sub_rate == 0:
            flags.append("官方標除權但 FinMind 該日無配股（可能現增或 FinMind 漏記配股）")
        if ev["kind"] == "除息" and stock > 0:
            flags.append("官方標除息但 FinMind 該日有配股")
        if cash == 0 and stock == 0 and sub_rate == 0:
            flags.append("FinMind 該日金額全為 0")
        out_rows.append({**base, "cash_dividend": round(cash, 6), "stock_dividend_yuan": round(stock, 6),
                         "cash_increase_rate": round(sub_rate, 6), "cash_increase_price": sub_px,
                         "ref_basic": round(ref_basic, 4), "ref": round(ref, 4),
                         "ref_formula": "含現增" if sub_rate > 0 else "基本",
                         "approx_vs_ref_pct": diff, "flags": flags})
    diffs = [abs(r["approx_vs_ref_pct"]) for r in out_rows if r["approx_vs_ref_pct"] is not None]
    reasons: dict = {}
    for u in unmatched:
        reasons[u["reason"]] = reasons.get(u["reason"], 0) + 1
    summary = {
        "n_events": len(marks["events"]), "n_matched": len(out_rows), "n_unmatched": len(unmatched),
        "unmatched_by_reason": reasons,
        "n_with_approx": len(diffs),
        "approx_within_1pct": sum(x < 1 for x in diffs),
        "approx_within_3pct": sum(x < 3 for x in diffs),
        "approx_max_abs_pct": max(diffs) if diffs else None,
        "n_flagged": sum(bool(r["flags"]) for r in out_rows),
        "n_cash_increase_formula": sum(r["ref_formula"] == "含現增" for r in out_rows),
    }
    OUT.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_marks": MARKS.name, "requests_sent": 0,
        "note": "參考價＝FinMind 股利金額推算（非官方公告參考價）；只建資料，不套用還原、不算報酬。",
        "summary": summary, "matched": out_rows, "unmatched": unmatched,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
