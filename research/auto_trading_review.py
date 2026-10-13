# -*- coding: utf-8 -*-
"""常備.開發-23：真錢（LIVE 族）盤後復盤檔。

13:40 盤後結算（auto_rebalance_bb90.py --settle）收尾時呼叫 write_review()，產出
research/data/auto_trading/LIVE/review_YYYYMMDD.json（本機，research/data/ 已在 .gitignore，不進 repo）：
送單、成交、均價 vs 參考價滑價、零股驗證結果、偏離、下期日期。App 日誌頁經 /auto/ledger 的 review 欄位讀取。

只讀帳本／狀態／零股驗證檔，不下單、不改對帳基準；推播摘要只寫百分比（不寫金額、股數）。
失敗只降級成警告（CLAUDE.md 第十二節：守門員／附屬流程不得拖垮結算本身）。

手動重產（不推播）：python research/auto_trading_review.py --date 20261012
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import auto_rebalance_bb90 as AB  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FINAL = ("FILLED", "EXPIRED", "CANCELLED")


def review_path(paths: AB.Paths, day: str) -> Path:
    return paths.base / "LIVE" / f"review_{day.replace('-', '')}.json"


def _records(paths: AB.Paths) -> list:
    out = []
    if paths.ledger.exists():
        for line in paths.ledger.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("key") and AB.mode_family(r.get("mode", "")) == "LIVE":
                out.append(r)
    return out


def _prev_close_before(day: str, sym: str, price_doc: dict) -> float | None:
    """參考價後備：price_history 在 day 之前最後一個收盤（帳本舊紀錄沒有 ref_price 時才用，標 ref_source=prev_close）。"""
    try:
        rows = sorted((price_doc.get("prices") or {}).get(sym) or [], key=lambda r: r["date"])
        c = None
        for r in rows:
            if r["date"] < day:
                c = AB._num(r["close"])
            else:
                break
        return c or None
    except Exception as e:
        print(f"[warn] 復盤：讀昨收失敗 {sym}：{type(e).__name__}", flush=True)
        return None


def _pct(a: float | None, b: float | None) -> float | None:
    return round((a / b - 1) * 100, 3) if a and b else None


def build_review(paths: AB.Paths, day: str, now: datetime | None = None, price_doc: dict | None = None,
                 next_run=None) -> dict | None:
    """day＝YYYY-MM-DD。當日沒有任何 LIVE 帳本紀錄（不含撤單測試）回 None。"""
    paths = AB.Paths(paths.base, paths.heartbeat, "LIVE")
    now = (now or datetime.now(AB.TW)).astimezone(AB.TW)
    recs = [r for r in _records(paths) if not str(r["key"]).startswith("LIVETEST-") and r.get("reason") != "LIVE_CANCEL_TEST"]
    keys_today = {r["key"] for r in recs if str(r.get("ts", ""))[:10] == day}
    if not keys_today:
        return None
    by_key: dict = {}
    for r in recs:
        if r["key"] in keys_today:
            by_key.setdefault(r["key"], []).append(r)
    orders, rejects = [], []
    if price_doc is None and any(r.get("event") == "SUBMITTED" and not r.get("ref_price") for rs in by_key.values() for r in rs):
        try:
            price_doc = AB._read_json_retry(AB.PRICE_HISTORY) or {}   # 約 55MB，只在需要後備參考價時讀一次
        except Exception as e:
            print(f"[warn] 復盤：讀 price_history 失敗：{type(e).__name__}", flush=True)
            price_doc = {}
    for k, rs in sorted(by_key.items()):
        last = rs[-1]
        if last.get("symbol") not in AB.WHITELIST:
            if last.get("event") == "REJECT":
                rejects.append({"key": k, "codes": sorted({str(x).split(":", 1)[0] for x in last.get("reasons") or []})})
            continue
        sub = next((r for r in rs if r.get("event") == "SUBMITTED"), None)
        if sub is None:
            if last.get("event") == "REJECT":
                rejects.append({"key": k, "symbol": last.get("symbol"),
                                "codes": sorted({str(x).split(":", 1)[0] for x in last.get("reasons") or []})})
            continue
        sym, q = last["symbol"], int(last.get("qty") or sub.get("qty") or 0)
        filled = AB._filled(last) if last.get("event") != "SUBMITTED" else 0
        avg = AB._num(last.get("avg_price")) if filled and last.get("avg_price") not in (None, "") else None
        ref, src = AB._num(sub.get("ref_price")) or None, "shioaji_reference"
        if ref is None:
            ref, src = _prev_close_before(day, sym, price_doc), "prev_close"
        lim = AB._num(sub.get("limit_price")) or None
        orders.append({"key": k, "symbol": sym, "lot": "零股" if k.endswith("-O") else "整股",
                       "qty": q, "filled_qty": filled, "fill_rate_pct": round(filled / q * 100, 1) if q else None,
                       "avg_price": avg, "ref_price": ref, "ref_source": src if ref else None, "limit_price": lim,
                       "slippage_pct": _pct(avg, ref), "vs_limit_pct": _pct(avg, lim),
                       "status": last.get("event"), "final": last.get("event") in FINAL})
    q_all = sum(o["qty"] for o in orders)
    f_all = sum(o["filled_qty"] for o in orders)
    slip_w = [(o["slippage_pct"], o["filled_qty"]) for o in orders if o["slippage_pct"] is not None and o["filled_qty"]]
    wslip = round(sum(s * w for s, w in slip_w) / sum(w for _, w in slip_w), 3) if slip_w else None
    odd = None
    ov = AB._read_json(paths.ledger.parent / f"odd_lot_verification_{day.replace('-', '')}.json")
    if isinstance(ov, dict):
        odd = {"status": "MATCH" if ov.get("all_match") else "MISMATCH",
               "per_symbol": {c: {"match": bool(v.get("match")), "filled": v.get("filled_common_plus_odd"),
                                  "position_diff": v.get("position_diff_shares")}
                              for c, v in (ov.get("per_symbol") or {}).items()}}
    elif any(o["lot"] == "零股" for o in orders):
        odd = {"status": "MISSING", "note": "當日有零股委託，但零股驗證檔尚未產生"}
    else:
        odd = {"status": "NO_ODD", "note": "當日沒有零股委託"}
    st = AB._read_json(paths.base / "LIVE" / "status.json") or {}
    dev = st.get("deviation") if isinstance(st.get("deviation"), dict) else None
    deviation = None
    if dev:
        deviation = {"per_symbol": dev, "max_abs_pp": round(max(abs(AB._num(v.get("dev_pp"))) for v in dev.values()), 2),
                     "alert": st.get("drift_alert") or [], "threshold_pp": AB.DRIFT_ALERT_PP}
    try:
        if next_run is None:
            import auto_ledger_view as LV
            next_run = LV.next_run(paths.base, now)
    except Exception as e:
        print(f"[warn] 復盤：下期日期計算失敗：{type(e).__name__}", flush=True)
        next_run = None
    state = AB._read_json(paths.state) or {}
    return {
        "date": day, "generated_at": now.isoformat(timespec="seconds"), "family": "LIVE",
        "batches": sorted({"-".join(str(k).split("-")[1:3]) for k in keys_today}),
        "summary": {"n_orders": len(orders), "n_filled": sum(1 for o in orders if o["status"] == "FILLED"),
                    "n_rejects": len(rejects), "fill_rate_pct": round(f_all / q_all * 100, 1) if q_all else None,
                    "slippage_pct_weighted": wslip, "all_final": all(o["final"] for o in orders)},
        "orders": orders, "rejects": rejects, "odd_lot": odd, "deviation": deviation,
        "next_run": next_run, "next_tranche": state.get("next_tranche"),
        "note": "滑價＝成交均價÷參考價−1（買進，正值＝買貴）；參考價優先用 Shioaji 平盤參考價，舊紀錄無此欄時用前一交易日收盤。非投資建議。",
    }


def push_text(rv: dict) -> str:
    """推播摘要：只寫百分比與日期，不寫金額、股數。"""
    s = rv["summary"]
    sg = lambda v: "—" if v is None else f"{'+' if v > 0 else ''}{v}%"  # noqa: E731
    odd = {"MATCH": "相符", "MISMATCH": "不符", "MISSING": "未產生", "NO_ODD": "無零股"}.get((rv.get("odd_lot") or {}).get("status"), "—")
    dv = rv.get("deviation")
    n = rv.get("next_run") or {}
    parts = [f"成交率 {s['fill_rate_pct'] if s['fill_rate_pct'] is not None else '—'}%",
             f"滑價 {sg(s['slippage_pct_weighted'])}（vs 參考價）",
             f"零股驗證 {odd}",
             f"最大偏離 {dv['max_abs_pp']} 個百分點" if dv else "偏離 —",
             f"下期 {n.get('date', '—')}"]
    return "｜".join(parts)


def write_review(base: Path | None = None, now: datetime | None = None, push: bool = True, day: str | None = None) -> dict | None:
    """盤後結算後呼叫。當日無帳本紀錄回 None；有送單且首次產生時推播一則（重產不重推）。永不拋例外。"""
    try:
        paths = AB.Paths(base)
        now = (now or datetime.now(AB.TW)).astimezone(AB.TW)
        day = day or now.date().isoformat()
        rv = build_review(paths, day, now)
        if rv is None:
            return None
        p = review_path(paths, day)
        old = AB._read_json(p) or {}
        rv["pushed_at"] = old.get("pushed_at")
        if push and not rv["pushed_at"] and rv["summary"]["n_orders"] > 0:
            if AB.push_notify(AB.Paths(paths.base, paths.heartbeat), f"真錢復盤 {day[5:].replace('-', '/')}", push_text(rv), "complete"):
                rv["pushed_at"] = now.isoformat(timespec="seconds")
        AB._write_json(p, rv)
        return rv
    except Exception as e:
        print(f"[warn] 復盤檔產生失敗：{type(e).__name__}（只記警告，不影響結算）", flush=True)
        return None


def latest_review(base: Path | None = None) -> dict | None:
    """最新一份復盤檔（唯讀，給 auto_ledger_view／App）。"""
    d = (Path(base) if base else AB.DEFAULT_DIR) / "LIVE"
    fs = sorted(d.glob("review_*.json")) if d.exists() else []
    return AB._read_json(fs[-1]) if fs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYYMMDD，預設今天")
    ap.add_argument("--push", action="store_true", help="首次產生時推播（預設不推）")
    a = ap.parse_args()
    day = None
    if a.date:
        day = date(int(a.date[:4]), int(a.date[4:6]), int(a.date[6:8])).isoformat()
    rv = write_review(push=a.push, day=day)
    print(json.dumps(rv, ensure_ascii=False, indent=1) if rv else "當日沒有真錢帳本紀錄，不產生復盤檔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
