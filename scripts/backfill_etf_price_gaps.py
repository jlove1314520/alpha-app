"""先.五十七-A2：補齊 data/price_history.json 中 Bb-90 白名單 ETF（00646、00697B，順帶 0050）的近期缺日。

官方來源優先：
- 上市（0050、00646）：TWSE rwd afterTrading/STOCK_DAY（單一個股月資料）
- 上櫃（00697B）：TPEx www/zh-tw/afterTrading/tradingStock（單一個股月資料，量額單位為仟股／仟元）
官方查不到才用 FinMind TaiwanStockPrice 補充，並在該筆標 source。
只補「缺的日期」，絕不覆蓋既有資料；每次請求間隔 ≥4 秒（C:\\alpha\\CLAUDE.md 頻率上限）。
adj_close 先設為 close 並標 adj_note：除權息回溯調整仍由 update_price_history.py 的既有流程負責。

用法：python scripts/backfill_etf_price_gaps.py [--months 4] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
PH = REPO / "data" / "price_history.json"
CODES = {"0050": "twse", "00646": "twse", "00697B": "tpex"}
SLEEP = 4.2


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def _roc(d: str) -> str:
    y, m, dd = d.strip().split("/")
    return f"{int(y) + 1911:04d}-{int(m):02d}-{int(dd):02d}"


def fetch_twse(code: str, ym: date, s) -> list[dict]:
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={ym:%Y%m}01&stockNo={code}&response=json"
    j = s.get(url, timeout=20).json()
    if j.get("stat") != "OK":
        return []
    out = []
    for r in j.get("data") or []:      # 日期, 成交股數, 成交金額, 開, 高, 低, 收, 漲跌, 筆數
        o, h, lo, c = (_num(x) for x in r[3:7])
        if c is None:
            continue
        out.append({"date": _roc(r[0]), "open": o, "high": h, "low": lo, "close": c, "adj_close": c,
                    "volume": _num(r[1]), "turnover": _num(r[2]), "source": "twse_stock_day",
                    "adj_note": "backfill：adj_close＝close，除權息回溯由 update_price_history 處理"})
    return out


def fetch_tpex(code: str, ym: date, s) -> list[dict]:
    url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code={code}&date={ym:%Y/%m}/01&response=json"
    j = s.get(url, timeout=20).json()
    t = (j.get("tables") or [{}])[0]
    out = []
    for r in t.get("data") or []:      # 日期, 成交仟股, 成交仟元, 開, 高, 低, 收, 漲跌, 筆數
        o, h, lo, c = (_num(x) for x in r[3:7])
        if c is None:
            continue
        vol, amt = _num(r[1]), _num(r[2])
        out.append({"date": _roc(r[0]), "open": o, "high": h, "low": lo, "close": c, "adj_close": c,
                    "volume": vol * 1000 if vol is not None else None, "turnover": amt * 1000 if amt is not None else None,
                    "source": "tpex_tradingStock",
                    "adj_note": "backfill：adj_close＝close，除權息回溯由 update_price_history 處理"})
    return out


def months_back(n: int) -> list[date]:
    t = date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(t)
        t = (t.replace(day=1) - __import__("datetime").timedelta(days=1)).replace(day=1)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    doc = json.loads(PH.read_text(encoding="utf-8"))
    px = doc["prices"]
    s = requests.Session()
    added = {}
    for code, mkt in CODES.items():
        have = {r["date"] for r in px.get(code, [])}
        new = []
        for ym in months_back(a.months):
            try:
                rows = (fetch_twse if mkt == "twse" else fetch_tpex)(code, ym, s)
            except Exception as e:
                print(f"[warn] {code} {ym:%Y-%m} 官方查詢失敗：{type(e).__name__}", flush=True)
                rows = []
            new += [r for r in rows if r["date"] not in have and r["date"] <= date.today().isoformat()]
            time.sleep(SLEEP)
        added[code] = sorted({r["date"] for r in new})
        if new and not a.dry_run:
            merged = {r["date"]: r for r in px.get(code, [])}
            for r in new:
                merged.setdefault(r["date"], r)          # 只補缺，不覆蓋
            px[code] = [merged[d] for d in sorted(merged)]
        print(f"{code}：補 {len(added[code])} 天", flush=True)
    if not a.dry_run and any(added.values()):
        doc.setdefault("meta", {})["etf_gap_backfill_note"] = (
            "2026-10-10 先.五十七-A2：0050／00646（TWSE STOCK_DAY）、00697B（TPEx tradingStock）官方單股月資料補缺日，"
            "只補不覆蓋，逐筆標 source；adj_close 暫等於 close。")
        tmp = PH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        for i in range(10):                          # Windows：目標檔可能被讀取中，短暫重試
            try:
                tmp.replace(PH)
                break
            except PermissionError:
                time.sleep(1.0)
        else:
            raise PermissionError("price_history.json 被佔用，重試 10 次仍無法寫回")
    print(json.dumps({k: len(v) for k, v in added.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
