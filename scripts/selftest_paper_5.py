# -*- coding: utf-8 -*-
"""先.九十一-1 模擬 F 賣波動 自測：全部在暫存資料夾跑，不碰真帳本、不打網路。"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import paper_5_vrp_tracker as T  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HDR = "日期,契約,到期月份(週別),履約價,買賣權,開盤價,最高價,最低價,最後成交價,成交量,結算價,未沖銷契約量,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段"
fails = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def chain(day, rows):
    lines = ["﻿" + HDR]
    for cm, k, cp, last, sess in rows:
        lines.append(f"{day.replace('-', '')},TXO,{cm},{k},{cp},-,-,-,{last},10,{last},0,-,-,-,-,,{sess}")
    return "\n".join(lines)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    T.LOG, T.OUT, T.MARKET = td / "log.jsonl", td / "p5.json", td / "m.json"
    T.final_settlement = lambda cm: 30100.0
    def mkt(day, close):
        T.MARKET.write_text(json.dumps({"taiex": {"close": close, "data_date": day, "sparkline_dates": [day], "sparkline": [close]}}), encoding="utf-8")

    r = T.step(today=date(2026, 10, 14), opt_text="")
    ok(r["state"] == "NOT_STARTED" and json.loads(T.OUT.read_text(encoding="utf-8"))["started"] is False, "11 月前不開始、摘要 started=false")
    ok(not T.LOG.exists(), "11 月前不寫帳本（不倒填）")

    mkt("2026-11-02", 30020.0)
    rows = [("202611", 30000, "買權", 300, "一般"), ("202611", 30000, "賣權", 280, "一般"),
            ("202612", 30000, "買權", 600, "一般"), ("202612", 30000, "賣權", 550, "一般"),
            ("202611W2", 30000, "買權", 100, "一般"), ("202611", 30000, "買權", 999, "盤後")]
    r = T.step(today=date(2026, 11, 2), opt_text=chain("2026-11-02", rows))
    log = T.read_log()
    ok(r["state"] == "ENTRY" and log[-1]["contract"] in ("202611", "202612"), "11/2 進場、只用月合約一般時段")
    # 11/2：202611 到期 11/18（16 天）、202612 到期 12/16（44 天）→ 距 30 各 14 天，同距離取較近到期
    ok(log[-1]["contract"] == "202611" and log[-1]["strike"] == 30000, "同距離取較近到期、價平 30000")
    ok(abs(log[-1]["premium_net"] - (580 - 2 - (100 + 0.001 * 580 * 50) / 50)) < 1e-6, "權利金扣滑價 1 點×2、手續費、期交稅")

    r = T.step(today=date(2026, 11, 2), opt_text=chain("2026-11-02", rows))
    ok(r["state"] == "NO_NEW_DAY" and len(T.read_log()) == 1, "同一資料日重跑不重複記")

    mkt("2026-11-03", 30100.0)
    r = T.step(today=date(2026, 11, 3), opt_text=chain("2026-11-03", [("202611", 30000, "買權", 330, "一般"), ("202611", 30000, "賣權", 240, "一般")]))
    log = T.read_log()
    ok(r["state"] == "MARK" and log[-1]["straddle"] == 570, "持倉每日重估（同合約同履約價）")

    mkt("2026-11-19", 30100.0)
    r = T.step(today=date(2026, 11, 19), opt_text=chain("2026-11-19", [("202612", 30100, "買權", 500, "一般"), ("202612", 30100, "賣權", 480, "一般")]))
    log = T.read_log()
    e = log[0]
    exp_pnl = e["premium_net"] * 50 - 100 * 50 - 100
    ok(log[-1]["event"] == "settle" and abs(log[-1]["pnl_ntd"] - round(exp_pnl, 1)) < 0.11, "到期用官方最後結算價結算、扣到期手續費")
    ok(abs(log[-1]["nav"] - 100 * (1 + exp_pnl / e["capital"])) < 1e-4, "淨值 = 進場淨值 ×(1 + 損益 ÷ 本金)")
    ok(not any(r_["event"] == "entry" and r_["date"] >= "2026-11-03" for r_ in log), "同月已進場過就不再進場")

    mkt("2026-12-01", 30200.0)
    r = T.step(today=date(2026, 12, 1), opt_text=chain("2026-12-01", [("202612", 30200, "買權", 520, "一般"), ("202612", 30200, "賣權", 500, "一般")]))
    ok(r["state"] == "ENTRY" and T.read_log()[-1]["nav_at_entry"] == T.read_log()[-2]["nav"], "下月第一個資料日進場、淨值接續")
    s = json.loads(T.OUT.read_text(encoding="utf-8"))
    ok(s["started"] and s["label"] == "模擬 F 賣波動" and "只是研究" in s["note"], "摘要含標籤與「只是研究」註記")

print("合計", len(fails), "項失敗" if fails else "全過")
sys.exit(1 if fails else 0)
