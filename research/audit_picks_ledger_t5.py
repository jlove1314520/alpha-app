"""先.六十八-5：估值榜 2026-08-27～09-04 快照中 t5 ≤ −15% 的紀錄，逐筆核對 picks_ledger 的
進場價（price_date 收盤）與出場價（t5.exit_date 收盤）vs 官方收盤（上市 TWSE STOCK_DAY、上櫃 TPEx
tradingStock）。只讀，不改任何資料；壞價時由呼叫者另行修正回填。

官方端點同源請求間隔 ≥3 秒（CLAUDE.md TWSE/TPEx 節）；每檔每月一次，結果快取在記憶體。
用法：python research/audit_picks_ledger_t5.py  → 印出 JSON 並寫 research/data/picks_ledger_audit_2026-10-11.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "picks_ledger.json"
PRICES = ROOT / "data" / "price_history.json"
OUT = ROOT / "research" / "data" / "picks_ledger_audit_2026-10-11.json"
NAMED = ["3081", "3450", "2491", "7711", "3661", "2464", "6446", "1815"]  # 總司令列出的八檔
UA = {"User-Agent": "Mozilla/5.0 (alpha-app audit)"}
_last = {"twse": 0.0, "tpex": 0.0}
_cache: dict[tuple[str, str], dict[str, float] | None] = {}


def _wait(src: str) -> None:
    gap = time.time() - _last[src]
    if gap < 3.0:
        time.sleep(3.0 - gap)
    _last[src] = time.time()


def _num(x) -> float | None:
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _twse_month(code: str, ym: str) -> dict[str, float] | None:
    _wait("twse")
    r = requests.get("https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY",
                     params={"date": ym.replace("-", "") + "01", "stockNo": code, "response": "json"}, headers=UA, timeout=20)
    try:
        d = r.json()
    except ValueError:
        return None
    if d.get("stat") != "OK" or not d.get("data"):
        return None
    f = d["fields"]
    i_date, i_close = f.index("日期"), f.index("收盤價")
    out = {}
    for row in d["data"]:
        y, m, dd = row[i_date].split("/")
        out[f"{int(y) + 1911}-{m}-{dd}"] = _num(row[i_close])
    return out


def _tpex_month(code: str, ym: str) -> dict[str, float] | None:
    _wait("tpex")
    r = requests.get("https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
                     params={"code": code, "date": ym.replace("-", "/") + "/01", "response": "json"}, headers=UA, timeout=20)
    try:
        d = r.json()
    except ValueError:
        return None
    tables = d.get("tables") or []
    if not tables or not tables[0].get("data"):
        return None
    t = tables[0]
    f = t["fields"]
    i_date = 0
    i_close = next(i for i, x in enumerate(f) if "收盤" in x)
    out = {}
    for row in t["data"]:
        y, m, dd = row[i_date].split("/")
        out[f"{int(y) + 1911}-{m}-{dd}"] = _num(row[i_close])
    return out


def official_close(code: str, date: str) -> tuple[float | None, str]:
    ym = date[:7]
    for src, fn in (("TWSE", _twse_month), ("TPEx", _tpex_month)):
        key = (src + code, ym)
        if key not in _cache:
            try:
                _cache[key] = fn(code, ym)
            except requests.RequestException:
                _cache[key] = None
        m = _cache[key]
        if m and date in m:
            return m[date], src
    return None, "查無"


def main() -> int:
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    ph = json.loads(PRICES.read_text(encoding="utf-8"))["prices"]
    cal = sorted({r["date"] for r in ph.get("0050", [])})
    rows = []
    for s in led["snapshots"]:
        if s["board"] != "value" or not ("2026-08-27" <= s["snapshot_date"] <= "2026-09-04"):
            continue
        for p in s["picks"]:
            t5 = (p.get("returns") or {}).get("t5") or {}
            if t5.get("return_pct") is None or t5["return_pct"] > -15:
                continue
            e_off, e_src = official_close(p["code"], p["price_date"])
            x_off, x_src = official_close(p["code"], t5["exit_date"])
            hold = (cal.index(t5["exit_date"]) - cal.index(p["price_date"])) if p["price_date"] in cal and t5["exit_date"] in cal else None
            ok_e = e_off is not None and abs(e_off - p["close_price"]) < 1e-6
            ok_x = None
            x_led = None
            if t5["exit_date"]:
                x_led = round(p["close_price"] * (1 + t5["return_pct"] / 100), 4)
                ok_x = x_off is not None and abs(x_off - x_led) <= max(0.01, x_off * 0.0005)
            rows.append({"snapshot_date": s["snapshot_date"], "code": p["code"], "name": p["name"],
                         "entry_date": p["price_date"], "entry_ledger": p["close_price"], "entry_official": e_off, "entry_src": e_src,
                         "exit_date": t5["exit_date"], "exit_ledger_implied": x_led, "exit_official": x_off, "exit_src": x_src,
                         "t5_pct": t5["return_pct"], "t5_official_pct": round((x_off / e_off - 1) * 100, 4) if e_off and x_off else None,
                         "hold_trading_days": hold, "entry_ok": ok_e, "exit_ok": ok_x, "named": p["code"] in NAMED})
    named_seen = {r["code"] for r in rows}
    missing = [c for c in NAMED if c not in named_seen]
    res = {"rows": rows, "named_not_in_range": missing}
    # 名單內但不在 8/27～9/04 範圍或未達 −15% 的，列出其實際最差 t5 供核對
    extra = []
    for c in missing:
        for s in led["snapshots"]:
            for p in s["picks"]:
                t5 = (p.get("returns") or {}).get("t5") or {}
                if p["code"] == c and t5.get("return_pct") is not None and t5["return_pct"] <= -15:
                    e_off, _ = official_close(c, p["price_date"])
                    x_off, _ = official_close(c, t5["exit_date"])
                    extra.append({"board": s["board"], "snapshot_date": s["snapshot_date"], "code": c, "name": p["name"],
                                  "entry_date": p["price_date"], "entry_ledger": p["close_price"], "entry_official": e_off,
                                  "exit_date": t5["exit_date"], "exit_official": x_off, "t5_pct": t5["return_pct"]})
    res["named_outside_range"] = extra
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
