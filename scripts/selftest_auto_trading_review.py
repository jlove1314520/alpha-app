# -*- coding: utf-8 -*-
"""常備.開發-23 自測：research/auto_trading_review.py（暫存目錄、假帳本，不碰真錢帳本、不送推播）。"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import auto_rebalance_bb90 as AB  # noqa: E402
import auto_trading_review as RV  # noqa: E402
import auto_ledger_view as LV  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS {name}")
    else:
        fail += 1
        print(f"FAIL {name} {detail}")


pushed = []
AB.push_send = lambda paths, title, body, kind: (pushed.append((title, body, kind)) or {"ok": 1})

with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    live = base / "LIVE"
    live.mkdir()
    (base / "config.local.json").write_text(json.dumps({"mode": "LIVE_WITH_VETO", "tranche_total": 4}), encoding="utf-8")
    (base / "calendar_2026.json").write_text(json.dumps({"year": 2026, "closed": []}), encoding="utf-8")
    day = "2026-10-12"
    ts = day + "T09:40:01+08:00"
    st_ = day + "T13:40:05+08:00"
    L = [
        {"ts": "2026-10-08T09:05:02+08:00", "event": "REJECT", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-ALL", "symbol": "ALL", "reasons": ["INSUFFICIENT_CASH:x"]},
        {"ts": ts, "event": "SUBMITTED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-C", "symbol": "0050", "qty": 1000, "limit_price": 100.5, "order_id": "a", "amount": 100500, "ref_price": 100.0},
        {"ts": ts, "event": "FILLED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-C", "symbol": "0050", "qty": 1000, "limit_price": 100.5, "filled_qty": 1000, "avg_price": 100.2},
        {"ts": ts, "event": "SUBMITTED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-O", "symbol": "0050", "qty": 200, "limit_price": 100.5, "order_id": "b", "amount": 20100, "ref_price": 100.0},
        {"ts": ts, "event": "OPEN", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-O", "symbol": "0050", "qty": 200, "limit_price": 100.5, "filled_qty": 0},
        {"ts": st_, "event": "PARTIAL", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-O", "symbol": "0050", "qty": 200, "limit_price": 100.5, "filled_qty": 100, "avg_price": 99.8, "settled": True},
        {"ts": st_, "event": "EXPIRED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-O", "symbol": "0050", "qty": 200, "limit_price": 100.5, "filled_qty": 100, "avg_price": 99.8, "remaining": 100, "settled": True},
        {"ts": ts, "event": "REJECT", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-00697B-C", "symbol": "00697B", "qty": 1000, "reasons": ["CAP:x"]},
        {"ts": ts, "event": "FILLED", "mode": "SIMULATION", "key": "SIM-202610-T1-R1-0050-C", "symbol": "0050", "qty": 1000, "filled_qty": 1000, "avg_price": 1},
        {"ts": ts, "event": "SUBMITTED", "mode": "LIVE_WITH_VETO", "key": "LIVETEST-x", "symbol": "0050", "qty": 1, "order_id": "z", "reason": "LIVE_CANCEL_TEST"},
    ]
    (live / "orders.jsonl").write_text("\n".join(json.dumps(r) for r in L) + "\n", encoding="utf-8")
    (live / "state.json").write_text(json.dumps({"positions": {}, "next_tranche": 2}), encoding="utf-8")
    (live / "status.json").write_text(json.dumps({"deviation": {"0050": {"dev_pp": 3.5}, "00646": {"dev_pp": -6.2}, "00697B": {"dev_pp": 2.7}}, "drift_alert": ["00646"]}), encoding="utf-8")
    (live / "odd_lot_verification_20261012.json").write_text(json.dumps({"all_match": True, "per_symbol": {"0050": {"match": True, "filled_common_plus_odd": 1100, "position_diff_shares": 1100}}}), encoding="utf-8")

    now = datetime(2026, 10, 12, 13, 40, 30, tzinfo=AB.TW)
    rv = RV.write_review(base, now)
    check("產出復盤檔", rv is not None and (live / "review_20261012.json").exists())
    s = rv["summary"]
    check("只算當日 LIVE 委託（排除 SIM／撤單測試／他日）", s["n_orders"] == 2, s)
    check("成交率按股數＝1100/1200", s["fill_rate_pct"] == 91.7, s)
    o0 = [o for o in rv["orders"] if o["lot"] == "整股"][0]
    check("整股滑價＝100.2/100−1＝+0.2%", o0["slippage_pct"] == 0.2, o0)
    check("參考價來源＝shioaji_reference", o0["ref_source"] == "shioaji_reference", o0)
    oo = [o for o in rv["orders"] if o["lot"] == "零股"][0]
    check("零股最終狀態 EXPIRED、成交 100", oo["status"] == "EXPIRED" and oo["filled_qty"] == 100, oo)
    check("加權滑價＝(0.2×1000−0.2×100)/1100", s["slippage_pct_weighted"] == round((0.2 * 1000 - 0.2 * 100) / 1100, 3), s)
    check("當日拒單收錄（代碼 CAP）", any(r.get("codes") == ["CAP"] for r in rv["rejects"]), rv["rejects"])
    check("零股驗證 MATCH", rv["odd_lot"]["status"] == "MATCH")
    check("最大偏離 6.2pp", rv["deviation"]["max_abs_pp"] == 6.2)
    check("下期日期有值", bool(rv.get("next_run") and rv["next_run"].get("date")), rv.get("next_run"))
    check("推播一則且只含百分比（無股數金額）", len(pushed) == 1 and "1100" not in pushed[0][1] and "100.2" not in pushed[0][1] and "%" in pushed[0][1], pushed)
    RV.write_review(base, now)
    check("重產不重推", len(pushed) == 1, pushed)
    v = LV.ledger_view(base, price_doc={"prices": {}})
    check("ledger_view 帶 review 且去掉冪等鍵", v.get("review", {}).get("date") == day and all("key" not in o for o in v["review"]["orders"]))
    check("當日無紀錄回 None", RV.write_review(base, datetime(2026, 10, 13, 13, 40, tzinfo=AB.TW)) is None)
    # 只有拒單的日子：產檔但不推播
    rv2 = RV.write_review(base, datetime(2026, 10, 8, 13, 40, tzinfo=AB.TW))
    check("只有拒單日：產檔、0 筆送單、不推播", rv2 is not None and rv2["summary"]["n_orders"] == 0 and len(pushed) == 1, rv2 and rv2["summary"])
    # 舊紀錄沒有 ref_price → 後備昨收
    L2 = [dict(r) for r in L]
    for r in L2:
        r.pop("ref_price", None)
    (live / "orders.jsonl").write_text("\n".join(json.dumps(r) for r in L2) + "\n", encoding="utf-8")
    rv3 = RV.build_review(AB.Paths(base), day, now, price_doc={"prices": {"0050": [{"date": "2026-10-08", "close": 99.0}, {"date": "2026-10-09", "close": 100.0}, {"date": "2026-10-12", "close": 120.0}]}}, next_run={"date": "x"})
    o3 = [o for o in rv3["orders"] if o["lot"] == "整股"][0]
    check("缺 ref_price 時用前一交易日收盤（不用當日）", o3["ref_price"] == 100.0 and o3["ref_source"] == "prev_close", o3)
    # 讀檔失敗降級
    (live / "orders.jsonl").write_text("not json\n", encoding="utf-8")
    check("帳本壞行不拋例外", RV.write_review(base, now) is None or True)
    orig = RV.build_review
    RV.build_review = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    check("內部例外降級為 None（不拖累結算）", RV.write_review(base, now) is None)
    RV.build_review = orig

print(f"合計 PASS {ok}／FAIL {fail}")
sys.exit(1 if fail else 0)
