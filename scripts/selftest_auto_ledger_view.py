# -*- coding: utf-8 -*-
"""先.六十-A2／A4／A5 自測：research/auto_ledger_view.py（/auto/ledger、/auto/status 附加欄位）與
research/web_push.py 推播類別偏好。全程沙盒、不連網、不送任何推播（假發送器）、不碰正式帳本。

檢查：①帳本只回去識別化欄位（不含 key／order_id／帳號／金額細節）②拒單原因只留代碼
③累計／本週損益算法 ④沒有成交時 first_batch_done=False、pnl=None ⑤next_run 用引擎 should_run 判斷
⑥limits 讀本機設定檔實際值 ⑦否決窗推播永遠不能被關閉 ⑧拒單類被關閉時不送、偏好檔壞掉時照送。
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
import auto_rebalance_bb90 as AB  # noqa: E402
import auto_ledger_view as LV  # noqa: E402
import web_push as WP  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


tmp = Path(tempfile.mkdtemp())
try:
    base = tmp / "auto"
    (base / "LIVE").mkdir(parents=True)
    (base / "config.local.json").write_text(json.dumps({"mode": "LIVE_WITH_VETO", "per_order_cap_twd": 300000, "max_price_dev_pct": 1.0,
                                                        "max_data_age_days": 4, "tranche": 1, "tranche_total": 4}), encoding="utf-8")
    led = base / "LIVE" / "orders.jsonl"

    def w(rows):
        led.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    rej = {"ts": "2026-10-08T09:05:10+08:00", "event": "REJECT", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-ALL",
           "symbol": "ALL", "qty": 0, "limit_price": None, "reasons": ["INSUFFICIENT_CASH:可用 123456 元，不足 999999 元"]}
    w([rej])
    v = LV.ledger_view(base, price_doc={"prices": {}})
    check("無成交 → first_batch_done=False、pnl=None、perf=None", v["first_batch_done"] is False and v["pnl"] is None and v.get("perf", 0) is None and v["n_rows"] == 1)
    r0 = v["rows"][0]
    check("拒單原因只留代碼（不含金額）", r0["reason_codes"] == ["INSUFFICIENT_CASH"] and "123456" not in json.dumps(v, ensure_ascii=False))
    check("代號 ALL 顯示為「全部」、批次 202610-T1", r0["symbol"] == "全部" and r0["batch"] == "202610-T1")

    # 有成交：上週一筆 0050 1000 股 @100、本週一筆 00646 500 股 @50（零股）
    fills = [
        {"ts": "2026-10-02T09:40:00+08:00", "event": "FILLED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T1-R1-0050-C",
         "symbol": "0050", "qty": 1000, "filled_qty": 1000, "avg_price": 100.0, "limit_price": 101, "order_id": "SECRET123", "amount": 100000},
        {"ts": "2026-10-07T09:40:00+08:00", "event": "FILLED", "mode": "LIVE_WITH_VETO", "key": "LIVE-202610-T2-R1-00646-O",
         "symbol": "00646", "qty": 500, "filled_qty": 500, "avg_price": 50.0, "limit_price": 50.5, "order_id": "SECRET456"},
    ]
    w([rej] + fills)
    px = {"prices": {
        "0050": [{"date": "2026-10-02", "close": 100}, {"date": "2026-10-03", "close": 102}, {"date": "2026-10-08", "close": 105}],
        "00646": [{"date": "2026-10-03", "close": 49}, {"date": "2026-10-08", "close": 52}],
        "00697B": [{"date": "2026-10-08", "close": 30}]}}
    v = LV.ledger_view(base, price_doc=px)
    allowed = {"date", "symbol", "qty", "filled_qty", "avg_price", "status", "reason_codes", "batch"}
    check("帳本列只含去識別化欄位", all(set(r) == allowed for r in v["rows"]))
    check("不含 order_id／key", "SECRET" not in json.dumps(v) and "LIVE-202610" not in json.dumps(v))
    p = v["pnl"]
    # 累計：0050 1000×105 + 00646 500×52 − (100000 + 25000) = 105000 + 26000 − 125000 = 6000
    # 本週（10-05 起）：0050 上週末 102 → 105 = +3000；00646 本週買 25000 → 26000 = +1000；合計 4000
    check(f"累計損益 6000（{p['total']}）、本週 4000（{p['week']}）、週一 2026-10-05", p["total"] == 6000 and p["week"] == 4000 and p["week_start"] == "2026-10-05")
    check("first_batch_done=True、n_fills=2", v["first_batch_done"] and v["n_fills"] == 2)
    # 常備.開發-12：績效對照。手續費 0.1425%（最低 1 元）：0050 100000→142、00646 25000→36；投入 100142＋25036＝125178
    # 10-08：持股 1000×105＋500×52＝131000 → 淨值 131000/125178＝1.0465；0050 全持有：第一筆 1000 股、
    # 第二筆在 10-07 以 ≤10-07 收盤 102 買 (25036−36)/102＝245.098 股 → 1245.098×105/125178＝1.0444
    pf = v["perf"]
    check(f"perf 有序列、起點＝首筆成交日 10-02、終點＝估值日 10-08（{pf.get('start')}～{pf.get('as_of')}）",
          pf.get("points") and pf["start"] == "2026-10-02" and pf["as_of"] == "2026-10-08" and [x["date"] for x in pf["points"]] == ["2026-10-02", "2026-10-03", "2026-10-08"])
    last = pf["points"][-1]
    check(f"perf 末點淨值 1.0465、0050 全持有 1.0444、投入 125178（{last}）", last["nav"] == 1.0465 and last["bench"] == 1.0444 and last["cost"] == 125178)
    check(f"perf 首日含手續費（淨值＜1：{pf['points'][0]['nav']}）、與 0050 首日相同", pf["points"][0]["nav"] == 0.9986 and pf["points"][0]["bench"] == 0.9986)
    check("perf note 標「含手續費」「未含稅」", "含手續費" in pf["note"] and "未含稅" in pf["note"])
    v0 = LV.ledger_view(base, price_doc={"prices": {"0050": px["prices"]["0050"], "00646": px["prices"]["00646"], "00697B": []}})
    check("缺白名單收盤價 → perf 回 error、不丟例外", "error" in (v0.get("perf") or {}))
    lr = LV.last_result(base)
    check(f"last_result 取最近日期的批次（10-08 的 202610-T1，含該批全部紀錄）（{lr}）", lr and lr["batch"] == "202610-T1" and lr["counts"] == {"REJECT": 1, "FILLED": 1} and lr["date"] == "2026-10-08")

    lim = LV.limits(AB.load_config(AB.Paths(base)))
    check("limits 讀本機設定檔實際值", lim["per_order_cap_twd"] == 300000 and lim["max_price_dev_pct"] == 1.0
          and lim["veto_minutes"] == AB.VETO_MINUTES and lim["whitelist"] == sorted(AB.WHITELIST))

    # next_run：日曆快取只放 2026，10-09 國慶補假休市；狀態 last_done=202610（10 月已做過）→ 下一次是 11 月最後交易日（月底再平衡）
    (base / "calendar_2026.json").write_text(json.dumps({"year": 2026, "closed": ["2026-10-09"]}), encoding="utf-8")
    (base / "LIVE" / "state.json").write_text(json.dumps({"next_tranche": 2, "last_done": "202610"}), encoding="utf-8")
    nr = LV.next_run(base, now=datetime(2026, 10, 10, 22, 0, tzinfo=AB.TW))
    check(f"10 月已做過 → next_run＝11 月最後交易日 2026-11-30 月底再平衡（{nr}）", nr and nr["date"] == "2026-11-30" and nr["reason"] == "month_end")
    (base / "LIVE" / "state.json").write_text(json.dumps({"next_tranche": 1}), encoding="utf-8")
    nr = LV.next_run(base, now=datetime(2026, 10, 10, 22, 0, tzinfo=AB.TW))
    check(f"首批未執行 → next_run＝下一個交易日 2026-10-12 首批（{nr}）", nr and nr["date"] == "2026-10-12" and nr["reason"] == "first_tranche")
    (base / "calendar_2026.json").unlink()
    check("讀不到日曆 → next_run=None（不猜）", LV.next_run(base, now=datetime(2026, 10, 10, 22, 0, tzinfo=AB.TW)) is None)

    # 推播偏好：假發送器，不連網
    sent = []
    env = tmp / ".env"
    env.write_text("", encoding="utf-8")
    orig_vapid = WP.load_vapid
    WP.load_vapid = lambda *_a, **_k: {"private": "x", "subject": "y"}
    WP._save_subs(base, [{"endpoint": "https://push.invalid/1", "keys": {"p256dh": "a", "auth": "b"}}])

    def fake(sub, payload, vapid, ttl, urgency):
        sent.append(json.loads(payload)["tag"])
        return 201
    try:
        WP.save_prefs(base, {"reject": False, "complete": False, "missed": False, "veto": False})
        check("save_prefs 強制否決窗為開", WP.load_prefs(base)["veto"] is True)
        r = WP.send("t", "b", kind="veto_start", base=base, sender=fake)
        check("否決窗推播即使其他類別全關也照送", r["ok"] == 1 and "veto_start" in sent)
        r = WP.send("t", "b", kind="error", base=base, sender=fake)
        check("拒單類被關閉 → 不送、標 PREF_OFF", r["ok"] == 0 and r.get("muted") and "error" not in sent)
        r = WP.send("t", "b", kind="test", base=base, sender=fake)
        check("測試推播不受偏好影響", r["ok"] == 1)
        (base / WP.PREFS_NAME).write_text("{壞掉的 json", encoding="utf-8")
        r = WP.send("t", "b", kind="error", base=base, sender=fake)
        check("偏好檔壞掉 → fail open 照送", r["ok"] == 1 and "error" in sent)
    finally:
        WP.load_vapid = orig_vapid
finally:
    shutil.rmtree(tmp, ignore_errors=True)

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
