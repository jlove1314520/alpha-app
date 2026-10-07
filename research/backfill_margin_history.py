"""先.五十二-3：大盤融資維持率（本站算法）歷史回補。

本站算法（與 .github/scripts/update_margin_maintenance.py 同一定義）：
  分子＝上市（TWSE）逐股融資今日餘額（張）× 1000 × 同日收盤價 加總
  分母＝同一個 TWSE rwd MI_MARGN 回應「信用交易統計」的融資金額（仟元）今日餘額 × 1000
來源（皆官方公開端點，每次請求間隔 ≥4 秒）：
  - https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=YYYYMMDD&selectType=ALL（分子逐股餘額＋分母）
  - 同日收盤價：先用 data/price_history.json；同日涵蓋不到 99% 融資張數時，
    改用 https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999（官方每日收盤行情）。
規則：分子分母必須同一天（同一個 MI_MARGN 回應），收盤價必須是同一天；同日收盤涵蓋 <99% 融資張數 → 標資料不完整、不相除。
原始回應快取在 research/data/margin_backfill_raw/（gitignore），重跑不重抓。輸出 research/data/margin_backfill.json。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "research" / "data" / "margin_backfill_raw"
OUT = REPO / "research" / "data" / "margin_backfill.json"
TW = timezone(timedelta(hours=8))
RANGES = [("2024-07-15", "2024-08-15"), ("2025-03-01", "2025-05-31")]
MIN_INTERVAL = 4.2
COVER_MIN = 0.99
MARGN = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
_last = [0.0]


def _num(v):
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s not in ("", "--", "-", "X") else None
    except Exception:
        return None


def _get(url: str, params: dict, cache: Path) -> dict | None:
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    wait = MIN_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, params={**params, "response": "json"}, timeout=30)
    _last[0] = time.time()
    if r.status_code in (403, 429):
        raise RuntimeError(f"TWSE 回應 HTTP {r.status_code}，停止（不重試、不換來源）")
    r.raise_for_status()
    try:
        body = r.json()
    except ValueError:
        raise RuntimeError("TWSE 回應不是合法 JSON（可能被軟性限流），停止")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return body


def parse_margn(body: dict) -> tuple[str, int, dict] | None:
    if not body or body.get("stat") != "OK" or not body.get("tables"):
        return None
    t0 = body["tables"][0]
    f0 = t0.get("fields", [])
    row = next((r for r in t0.get("data", []) if r and r[0] == "融資金額(仟元)"), None)
    if row is None or "今日餘額" not in f0:
        return None
    money = _num(row[f0.index("今日餘額")])
    lots = {}
    if len(body["tables"]) > 1:
        t1 = body["tables"][1]
        f1 = t1.get("fields", [])
        if "今日餘額" in f1:
            bi = f1.index("今日餘額")      # 第一個「今日餘額」是融資段
            for r in t1.get("data", []):
                v = _num(r[bi]) if r and len(r) > bi else None
                if r and v is not None:
                    lots[str(r[0]).strip()] = v
    d = body["date"]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}", int(round(money * 1000)), lots


def parse_mi_index(body: dict) -> dict:
    out = {}
    if not body or body.get("stat") != "OK":
        return out
    for t in body.get("tables", []):
        f = t.get("fields") or []
        if "證券代號" in f and "收盤價" in f:
            ci, pi = f.index("證券代號"), f.index("收盤價")
            for r in t.get("data", []):
                px = _num(r[pi]) if len(r) > pi else None
                if px:
                    out[str(r[ci]).strip()] = px
    return out


def closes_from_ph(ph: dict, day: str) -> dict:
    out = {}
    for code, rows in ph.items():
        for r in rows:
            if str(r.get("date"))[:10] == day:
                px = _num(r.get("close"))
                if px:
                    out[code] = px
                break
    return out


def compute(day: str, money: int, lots: dict, closes: dict) -> dict:
    tot = sum(lots.values()) or 1
    matched = {c: v for c, v in lots.items() if c in closes}
    cover = sum(matched.values()) / tot
    num = sum(v * 1000 * closes[c] for c, v in matched.items())
    rec = {"date": day, "margin_money": money, "collateral_value": int(round(num)), "matched_stocks": len(matched),
           "lots_coverage": round(cover, 5)}
    if cover < COVER_MIN or money <= 0:
        rec.update(ratio_pct=None, data_incomplete=True,
                   incomplete_reason=f"同日收盤只涵蓋 {cover * 100:.2f}% 融資張數（門檻 {COVER_MIN * 100:.0f}%），不相除")
    else:
        rec.update(ratio_pct=round(num / money * 100, 2), data_incomplete=False)
    return rec


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ph = json.loads((REPO / "data" / "price_history.json").read_text(encoding="utf-8")).get("prices") or {}
    recs, skipped = [], []
    for a, b in RANGES:
        d = date.fromisoformat(a)
        while d <= date.fromisoformat(b):
            if d.weekday() < 5:
                ds = d.strftime("%Y%m%d")
                m = parse_margn(_get(MARGN, {"date": ds, "selectType": "ALL"}, RAW / f"MI_MARGN_{ds}.json"))
                if m is None:
                    skipped.append({"date": d.isoformat(), "reason": "MI_MARGN 查無資料（休市或未發布）"})
                elif m[0] != d.isoformat():
                    skipped.append({"date": d.isoformat(), "reason": f"MI_MARGN 回傳日期 {m[0]} 與查詢日不同，跳過（分子分母須同日）"})
                else:
                    day, money, lots = m
                    closes = closes_from_ph(ph, day)
                    src = "price_history.json"
                    cov = sum(v for c, v in lots.items() if c in closes) / (sum(lots.values()) or 1)
                    if cov < COVER_MIN:
                        closes = parse_mi_index(_get(MI_INDEX, {"date": ds, "type": "ALLBUT0999"}, RAW / f"MI_INDEX_{ds}.json"))
                        src = "TWSE MI_INDEX（同日官方收盤行情）"
                    rec = compute(day, money, lots, closes)
                    rec["close_source"] = src
                    recs.append(rec)
                    print(day, rec.get("ratio_pct"), f"cover={rec['lots_coverage']}", src, flush=True)
            d += timedelta(days=1)
    valid = [r for r in recs if not r["data_incomplete"]]

    def low(prefix):
        xs = [r for r in valid if r["date"].startswith(prefix)]
        if not xs:
            return None
        r = min(xs, key=lambda x: x["ratio_pct"])
        return {"date": r["date"], "ratio_pct": r["ratio_pct"]}
    out = {"generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "definition": "本站算法：上市逐股融資今日餘額×1000×同日收盤 ÷ 同日信用交易統計融資金額（同一 MI_MARGN 回應），與 data/margin_maintenance.json 同定義",
           "sources": [MARGN, MI_INDEX, "data/price_history.json"], "ranges": RANGES, "records": recs, "skipped": skipped,
           "low_2025_04": low("2025-04"), "low_2024_08": low("2024-08"),
           "low_2024_07_08": min(({"date": r["date"], "ratio_pct": r["ratio_pct"]} for r in valid if r["date"] < "2024-08-16"),
                                  key=lambda x: x["ratio_pct"], default=None)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("有效", len(valid), "／資料不完整", len(recs) - len(valid), "／跳過", len(skipped))
    print("2025-04 最低", out["low_2025_04"], "｜2024-08 最低", out["low_2024_08"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
