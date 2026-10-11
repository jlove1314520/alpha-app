# -*- coding: utf-8 -*-
"""先.七十九-4 自測：auto_rebalance_bb90.flow_verify_close（流程驗證單收尾）。全程暫存目錄、假推播，不連券商、不送單。
①結算未完成且未到 14:30 → WAIT，不開 STOP、不推播
②對帳＋零股三檔都 match → 開 STOP、status 寫 strategy_frozen、推播「流程驗證完成，自動投資已暫停」
③同一天再跑 → DONE_ALREADY，不重複推播
④零股一檔不符 → 仍開 STOP，推播列出差異
⑤14:30 結算仍未完成 → 開 STOP，差異寫「盤後結算沒有完成」
⑥STOP 開著時 gate_order 一律拒單（T2 以後不會送出）
"""
import json
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import auto_rebalance_bb90 as A  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


DAY = "2026-10-12"
T = lambda hm: datetime.fromisoformat(f"{DAY}T{hm}:00+08:00")  # noqa: E731


def setup(tmp, settled=True, match=(True, True, True), applied=True):
    if tmp.exists():
        shutil.rmtree(tmp)
    live = tmp / "LIVE"
    live.mkdir(parents=True)
    (tmp / "config.local.json").write_text(json.dumps({"mode": "LIVE_WITH_VETO"}), encoding="utf-8")
    keys = [f"LIVE-202610-T1-R1-{c}-O" for c in A.WEIGHTS]
    rows = [{"ts": f"{DAY}T09:40:00+08:00", "mode": "LIVE_WITH_VETO", "key": k, "symbol": k.split("-")[4], "event": "FILLED", "qty": 2, "filled_qty": 2}
            for k in keys]
    (live / "orders.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (live / "state.json").write_text(json.dumps({"positions": {}, "applied": keys if applied else [], "next_tranche": 2}), encoding="utf-8")
    st = {"last_error": None}
    if settled:
        st["last_settle"] = f"{DAY}T13:40:20+08:00"
    (live / "status.json").write_text(json.dumps(st), encoding="utf-8")
    per = {c: {"filled_common_plus_odd": 2, "position_diff_shares": 2 if m else 1, "match": m} for c, m in zip(A.WEIGHTS, match)}
    (live / "odd_lot_verification_20261012.json").write_text(json.dumps({"per_symbol": per}), encoding="utf-8")
    return A.Paths(tmp, heartbeat=tmp / "hb.jsonl")


base = Path(tempfile.mkdtemp())
tmp = base / "t"
try:
    pushes = []
    notify = lambda p, t, b, k: pushes.append((t, b, k))  # noqa: E731

    paths = setup(tmp, settled=False)
    r = A.flow_verify_close(paths, T("14:00"), notify=notify)
    check("①結算未完成、14:00 → WAIT，不開 STOP、不推播", r["state"] == "WAIT" and not paths.stop_flag.exists() and not pushes)

    paths = setup(tmp)
    r = A.flow_verify_close(paths, T("14:00"), notify=notify)
    st = json.loads((tmp / "LIVE" / "status.json").read_text(encoding="utf-8"))
    fz = st.get("strategy_frozen") or {}
    check("②全部相符 → OK、開 STOP", r["state"] == "OK" and paths.stop_flag.exists())
    check("②status 寫 strategy_frozen（原因＝等紙上策略打贏 0050、all_ok=True）",
          fz.get("reason") == "等紙上策略打贏 0050" and fz["flow_verification"]["all_ok"] is True)
    check("②推播標題＝流程驗證完成，自動投資已暫停", len(pushes) == 1 and pushes[0][0] == "流程驗證完成，自動投資已暫停")
    r = A.flow_verify_close(paths, T("14:30"), notify=notify)
    check("③同一天再跑 → DONE_ALREADY，不重複推播", r["state"] == "DONE_ALREADY" and len(pushes) == 1)

    pushes.clear()
    paths = setup(tmp, match=(True, False, True))
    r = A.flow_verify_close(paths, T("14:00"), notify=notify)
    check("④00646 零股不符 → MISMATCH、仍開 STOP、推播列出差異",
          r["state"] == "MISMATCH" and paths.stop_flag.exists() and pushes and "00646" in pushes[0][1] and pushes[0][2] == "error")

    pushes.clear()
    paths = setup(tmp, settled=False)
    r = A.flow_verify_close(paths, T("14:30"), notify=notify)
    check("⑤14:30 結算仍未完成 → 開 STOP、差異寫明", r["state"] == "MISMATCH" and paths.stop_flag.exists()
          and any("盤後結算沒有完成" in d for d in r["strategy_frozen"]["flow_verification"]["diffs"]))

    pushes.clear()
    paths = setup(tmp, applied=False)
    r = A.flow_verify_close(paths, T("14:00"), notify=notify)
    check("⑤'成交未併入對帳基準 → 對帳不通過、仍開 STOP", r["state"] == "MISMATCH"
          and r["strategy_frozen"]["flow_verification"]["recon_ok"] is False and paths.stop_flag.exists())

    ctx = {"cfg": {"per_order_cap_twd": 1000, "max_price_dev_pct": 1.0, "max_data_age_days": 4},
           "prev_close": {"0050": (114.95, "2026-10-08")}, "today": date(2026, 11, 2),
           "stopped": A.is_stopped(paths), "reconciled": True}
    why = A.gate_order({"symbol": "0050", "action": "Buy", "cond": "Cash", "limit_price": 115.5, "lot": "IntradayOdd", "qty": 2}, ctx)
    check("⑥STOP 開著 → T2 委託被 gate_order 拒單（STOP_FLAG）", any(w.startswith("STOP_FLAG") for w in why))
finally:
    shutil.rmtree(base, ignore_errors=True)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(0 if all(results) else 1)
