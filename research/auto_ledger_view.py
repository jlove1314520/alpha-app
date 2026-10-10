# -*- coding: utf-8 -*-
"""先.六十-A2／A4／A5：真錢自動交易的唯讀檢視（給 alpha_live_server 的 /auto/status、/auto/ledger 用）。

只讀本機帳本／狀態／設定檔，不下單、不寫任何檔案、不改引擎（auto_rebalance_bb90.py）一個字。
回傳內容只含去識別化欄位：日期、代號、數量、均價、狀態、批次——不含帳號、委託書號、餘額、
拒單原因的金額細節（只留原因代碼，例如 CASH／CAP）。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import auto_rebalance_bb90 as AB

_PX_CACHE: dict = {"mtime": None, "doc": None}

# 常備.開發-12：績效對照的手續費假設。帳本沒有實際手續費欄位，用公告牌告費率 0.1425%（不打折，偏保守）、
# 每筆最低 1 元（零股常見下限）；只有買進、還沒有賣出，所以沒有證交稅（App 標「含手續費、未含稅」）。
PERF_FEE_RATE = 0.001425
PERF_FEE_MIN = 1.0
PERF_BENCH = "0050"


def _prices(price_doc: dict | None = None) -> dict:
    """price_history.json 很大（約 55MB），依檔案修改時間快取，只在檔案更新時重讀。"""
    if price_doc is not None:
        return price_doc.get("prices") or {}
    p = AB.PRICE_HISTORY
    try:
        m = p.stat().st_mtime
    except OSError:
        return {}
    if _PX_CACHE["mtime"] != m:
        _PX_CACHE["doc"] = AB._read_json(p) or {}
        _PX_CACHE["mtime"] = m
    return (_PX_CACHE["doc"] or {}).get("prices") or {}


def _batch_of(key: str, r: dict) -> str:
    if r.get("reason") == "LIVE_CANCEL_TEST" or str(key).startswith("LIVETEST-"):
        return "撤單測試"
    parts = str(key).split("-")
    return f"{parts[1]}-{parts[2]}" if len(parts) >= 3 else ""


def _close_on_or_before(rows: list, d: str):
    c = None
    for r in rows:
        if r["date"] <= d:
            c = AB._num(r["close"])
        else:
            break
    return c


def ledger_view(base: Path | None = None, price_doc: dict | None = None, today: date | None = None) -> dict:
    """真錢（LIVE 族）帳本的去識別化檢視＋本週／累計損益（以 price_history 收盤估值，未計手續費與稅）。"""
    paths = AB.Paths(base).scoped("LIVE")
    latest = AB._ledger_latest(paths)
    rows = []
    for k, r in latest.items():
        filled = AB._filled(r)
        reasons = r.get("reasons") or []
        rows.append({
            "date": str(r.get("ts", ""))[:10],
            "symbol": r.get("symbol") if r.get("symbol") in AB.WHITELIST else ("全部" if r.get("symbol") in (None, "ALL") else "其他"),
            "qty": int(r.get("qty") or 0),
            "filled_qty": filled,
            "avg_price": (round(AB._num(r.get("avg_price")), 2) if filled and r.get("avg_price") not in (None, "") else None),
            "status": r.get("event"),
            "reason_codes": sorted({str(x).split(":", 1)[0] for x in reasons})[:5] if isinstance(reasons, list) else [],
            "batch": _batch_of(k, r),
        })
    rows.sort(key=lambda x: (x["date"], x["batch"], x["symbol"] or ""), reverse=True)
    fills = [r for r in latest.values() if AB._filled(r) > 0]
    out = {"ok": True, "rows": rows[:200], "n_rows": len(rows), "n_fills": len(fills),
           "first_batch_done": bool(fills),
           "note": "損益只算自動交易買進的股數；以 price_history 收盤估值；未計手續費與稅。"}
    if not fills:
        out["pnl"] = None
        out["perf"] = None
        return out
    px = _prices(price_doc)
    series = {c: sorted(px.get(c) or [], key=lambda r: r["date"]) for c in AB.WHITELIST}
    if any(not series[c] for c in AB.WHITELIST):
        out["pnl"] = {"error": "price_history 缺白名單標的收盤價，無法估值"}
        out["perf"] = {"error": "price_history 缺白名單標的收盤價，無法畫績效對照"}
        return out
    as_of = min(series[c][-1]["date"] for c in AB.WHITELIST)
    asof_d = date.fromisoformat(as_of)
    wk0 = (asof_d - timedelta(days=asof_d.weekday())).isoformat()  # 本週一
    last = {c: _close_on_or_before(series[c], as_of) for c in AB.WHITELIST}
    cost = val = val_wk_prev = cost_wk = 0.0
    for r in fills:
        sym, q, d = r.get("symbol"), AB._filled(r), str(r.get("ts", ""))[:10]
        if sym not in AB.WHITELIST:
            continue
        amt = AB._filled_amount(r)
        cost += amt
        val += q * last[sym]
        if d < wk0:
            prev = _close_on_or_before(series[sym], (date.fromisoformat(wk0) - timedelta(days=1)).isoformat())
            val_wk_prev += q * (prev if prev is not None else AB._num(r.get("avg_price") or r.get("limit_price")))
        else:
            cost_wk += amt
    out["pnl"] = {"as_of": as_of, "week_start": wk0,
                  "total": round(val - cost), "total_pct": round((val / cost - 1) * 100, 2) if cost else None,
                  "week": round(val - val_wk_prev - cost_wk)}
    try:  # 績效對照失敗只影響自己那一塊，不拖累損益與帳本列
        out["perf"] = perf_series(fills, series, as_of)
    except Exception as e:
        out["perf"] = {"error": f"績效對照計算失敗（{type(e).__name__}）"}
    return out


def _fee(amount: float) -> float:
    return max(PERF_FEE_MIN, round(amount * PERF_FEE_RATE)) if amount > 0 else 0.0


def perf_series(fills: list, series: dict, as_of: str) -> dict:
    """常備.開發-12：累計淨值 vs 同期 0050 全持有（逐交易日，以 0050 的交易日為日曆）。

    淨值＝當日持股市值 ÷ 截至當日投入總額（成交金額＋手續費）。
    0050 全持有＝每一筆成交當天，把同樣的投入總額（含手續費）改在當天以 0050 收盤價全數買進 0050（同樣扣手續費）。
    兩邊都只有買進，所以都「含手續費、未含稅」；不算未投入的現金。
    """
    bench = series.get(PERF_BENCH) or []
    ev = []
    for r in fills:
        sym = r.get("symbol")
        if sym not in AB.WHITELIST:
            continue
        amt = AB._filled_amount(r)
        ev.append((str(r.get("ts", ""))[:10], sym, AB._filled(r), amt + _fee(amt)))
    if not ev:
        return {"error": "成交紀錄沒有白名單標的"}
    ev.sort()
    d0 = ev[0][0]
    days = [b["date"] for b in bench if d0 <= b["date"] <= as_of]
    if not days or days[0] != d0:
        days = [d0] + [d for d in days if d != d0]
    units_b = []  # 每筆成交對應的 0050 股數
    for d, _s, _q, c in ev:
        p = _close_on_or_before(bench, d)
        if not p:
            return {"error": f"price_history 缺 {PERF_BENCH} 在 {d} 以前的收盤價"}
        units_b.append((d, (c - _fee(c / (1 + PERF_FEE_RATE))) / p))
    pts = []
    for d in days:
        cost = sum(c for e, _s, _q, c in ev if e <= d)
        val = 0.0
        for e, s_, q, _c in ev:
            if e <= d:
                px_ = _close_on_or_before(series[s_], d)
                if px_ is None:
                    break
                val += q * px_
        else:
            pb = _close_on_or_before(bench, d)
            vb = sum(u for e, u in units_b if e <= d) * (pb or 0)
            pts.append({"date": d, "nav": round(val / cost, 4), "bench": round(vb / cost, 4), "cost": round(cost)})
    if not pts:
        return {"error": "成交日以後沒有收盤價可估值"}
    last = pts[-1]
    return {"bench": PERF_BENCH, "start": pts[0]["date"], "as_of": last["date"], "points": pts[-500:],
            "nav_pct": round((last["nav"] - 1) * 100, 2), "bench_pct": round((last["bench"] - 1) * 100, 2),
            "fee_rate": PERF_FEE_RATE, "fee_min": PERF_FEE_MIN,
            "note": "含手續費（牌告 0.1425% 不打折、每筆最低 1 元）、未含稅；0050 全持有＝同樣的錢在同一天以收盤價全買 0050"}


def limits(cfg: dict) -> dict:
    """引擎實際硬限制（auto_rebalance_bb90.gate_order／常數），唯讀。"""
    return {"whitelist": sorted(AB.WHITELIST), "weights": AB.WEIGHTS,
            "buy_only": True, "cash_only": True,
            "per_order_cap_twd": AB._num(cfg.get("per_order_cap_twd")) or None,
            "max_price_dev_pct": float(cfg.get("max_price_dev_pct", 1.0)),
            "max_data_age_days": int(cfg.get("max_data_age_days", 4)),
            "veto_minutes": AB.VETO_MINUTES}


def _cal(base: Path, year: int) -> dict | None:
    """只讀本機交易日曆快取，不連網（引擎自己會更新快取）。"""
    doc = AB._read_json(Path(base) / f"calendar_{year}.json")
    return doc if isinstance(doc, dict) and doc.get("closed") is not None else None


def next_run(base: Path | None = None, now: datetime | None = None, horizon_days: int = 70) -> dict | None:
    """下一個引擎會動作的交易日（用引擎自己的 should_run 判斷，09:05 那一輪）。讀不到日曆就回 None。"""
    base = Path(base) if base else AB.DEFAULT_DIR
    paths = AB.Paths(base)
    now = (now or datetime.now(AB.TW)).astimezone(AB.TW)
    cfg = AB.load_config(paths)
    d = now.date() if (now.hour, now.minute) < (9, 40) else now.date() + timedelta(days=1)
    for _ in range(horizon_days):
        cal = _cal(base, d.year)
        if cal is None:
            return None
        t = datetime(d.year, d.month, d.day, 9, 5, tzinfo=AB.TW)
        try:
            why = AB.should_run(paths, t, cfg, cal)
        except Exception:
            return None
        if why:
            return {"date": d.isoformat(), "time": "09:05", "reason": why}
        d += timedelta(days=1)
    return None


def last_result(base: Path | None = None) -> dict | None:
    """最近一個批次（不含撤單測試）的結果摘要：日期、批次、各狀態筆數。"""
    v = ledger_view(base, price_doc={"prices": {}})
    rows = [r for r in v["rows"] if r["batch"] != "撤單測試"]
    if not rows:
        return None
    b = rows[0]["batch"]
    sub = [r for r in rows if r["batch"] == b]
    cnt: dict = {}
    for r in sub:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    codes = sorted({c for r in sub for c in r["reason_codes"]})
    return {"date": max(r["date"] for r in sub), "batch": b, "counts": cnt, "reason_codes": codes}


if __name__ == "__main__":
    print(json.dumps({"next_run": next_run(), "last_result": last_result(),
                      "ledger_rows": ledger_view(price_doc={"prices": {}})["n_rows"]}, ensure_ascii=False))
