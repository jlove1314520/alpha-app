# -*- coding: utf-8 -*-
"""模擬 F 賣波動（紙.五）：台指選擇權價平跨式賣方的紙上追蹤（先.九十一-1）。

依據：試驗 #444（docs/PREREG_txo_vrp_2002_2014_FINAL.md）PASS，但總司令裁示**不提請真錢**
（DSR 算不出、年化約 4.6%、每組名目數百萬元）；只做前進式紙上追蹤。學界已知現象、只是研究。

規則（照 PREREG 第二層，前進式只能用「當天」資料，所以抽樣改成每月第一個可交易日）：
- 2026-11 起才記（START），不得倒填：每次執行只處理期交所最新一個資料日；錯過的日子不補。
- 沒有持倉、且資料日是本月第一個看到的交易日（該月還沒進場過）→ 進場：
  - 月合約（到期月份 6 位數字；週選擇權排除）、一般交易時段；
  - 距到期（第三個星期三）日曆天最接近 30、在 [10,45]；同距離時取較近到期；
  - 價平＝離當日加權指數收盤最近、且 call／put 最後成交價都 > 0 的履約價；
  - 以最後成交價「賣出」call＋put 各 1 口；扣滑價每口 1 點、手續費每口 50 元、期交稅千分之 1（權利金）。
- 持倉中每天用同一合約同一履約價的收盤價（無成交用結算價）重估：負債＝(call＋put)×50。
- 到期後第一次執行：抓期交所官方最後結算價（fSPDataDown，該年 1 次請求）結算，到期再扣手續費 2×50。
- 1 倍名目：本金＝進場日指數 × 50 元；淨值從 100 起算、逐筆複利；同時間只有 1 組持倉。
- 節流：taifex_openapi 與 www.taifex 共用 data/rate_limit_state.json，同源 ≥3 秒、402/403/428/429 封鎖 2 小時。
輸出：research/data/paper_5_log.jsonl（帳本，append-only）、data/paper_5.json（App 摘要）。
自身失敗只印警告、exit 0（不影響其他排程）。
"""
from __future__ import annotations

import calendar
import csv
import io
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "research" / "data" / "paper_5_log.jsonl"
OUT = ROOT / "data" / "paper_5.json"
STATE = ROOT / "data" / "rate_limit_state.json"
MARKET = ROOT / "data" / "market_tw.json"
OPT_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportOpt"
FSP_URL = "https://www.taifex.com.tw/cht/5/fSPDataDown"
START = "2026-11-01"
MULT, SLIP_PTS, FEE, TAX = 50, 1.0, 50.0, 0.001
TW = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaAppPaperTracker/1.0)"}
LABEL = "模擬 F 賣波動"
NOTE = "學界已知現象（選擇權賣方賺波動率風險溢酬）、只是研究；不提請真錢（先.九十一-1）"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── 節流（與 fetch_futures_institutional.py 同一套共用狀態） ──
def _state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sources": {}}


def _get(source, method, url, **kw):
    st = _state()
    src = st.setdefault("sources", {}).setdefault(source, {})
    now = time.time()
    if src.get("blocked_until") and now < src["blocked_until"]:
        raise RuntimeError(f"{source} 封鎖冷卻中，依資料源禮儀不送請求")
    if src.get("last_request_at") and now - src["last_request_at"] < 3.0:
        time.sleep(3.0 - (now - src["last_request_at"]))
    src["last_request_at"] = time.time()
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    r = requests.request(method, url, headers=UA, timeout=60, **kw)
    if r.status_code in (402, 403, 428, 429):
        st = _state()
        s2 = st.setdefault("sources", {}).setdefault(source, {})
        s2["blocked_until"] = time.time() + 2 * 3600
        s2["block_reason"] = f"HTTP {r.status_code}（paper_5_vrp_tracker.py）"
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"HTTP {r.status_code}，已標記封鎖 2 小時")
    r.raise_for_status()
    return r


def third_wednesday(cm: str) -> date:
    y, m = int(cm[:4]), int(cm[4:6])
    weds = [d for wk in calendar.Calendar().monthdatescalendar(y, m) for d in wk if d.weekday() == 2 and d.month == m]
    return weds[2]


def _num(s):
    try:
        v = float(str(s).replace(",", ""))
        return v if v > 0 else None
    except ValueError:
        return None


def parse_opt(text: str):
    """回傳 (資料日, {contract_month: {strike: {'C': (last, settle), 'P': ...}}})，只留 TXO 月合約一般時段。"""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    hdr = rows[0]
    ix = {k: hdr.index(k) for k in ("日期", "契約", "到期月份(週別)", "履約價", "買賣權", "最後成交價", "結算價", "交易時段")}
    out, day = {}, None
    for r in rows[1:]:
        if len(r) < len(hdr) or r[ix["契約"]].strip() != "TXO" or r[ix["交易時段"]].strip() != "一般":
            continue
        cm = r[ix["到期月份(週別)"]].strip()
        if not (len(cm) == 6 and cm.isdigit()):
            continue
        cp = {"買權": "C", "賣權": "P"}.get(r[ix["買賣權"]].strip())
        k = _num(r[ix["履約價"]])
        if cp is None or k is None:
            continue
        d = r[ix["日期"]].strip()
        day = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        out.setdefault(cm, {}).setdefault(k, {})[cp] = (_num(r[ix["最後成交價"]]), _num(r[ix["結算價"]]))
    return day, out


def taiex_close(day: str):
    t = (json.loads(MARKET.read_text(encoding="utf-8")).get("taiex") or {})
    for d, c in zip(t.get("sparkline_dates") or [], t.get("sparkline") or []):
        if d == day:
            return float(c)
    return float(t["close"]) if t.get("data_date") == day and t.get("close") else None


def final_settlement(cm: str):
    y = cm[:4]
    r = _get("taifex_www", "POST", FSP_URL, data={"start_year": y, "start_month": "01", "end_year": y,
                                                    "end_month": "12", "dlFileType": "3"})
    for ln in r.content.decode("big5", errors="replace").splitlines()[1:]:
        p = [x.strip() for x in ln.split(",")]
        if len(p) >= 5 and p[2] == "TXO" and p[1] == cm:
            return _num(p[4])
    return None


def read_log():
    try:
        return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def append(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"logged_at": datetime.now(TW).isoformat(timespec="seconds"), **rec}
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_summary(log, started, extra=None):
    nav = log[-1]["nav"] if log else 100.0
    pos = next((r for r in reversed(log) if r["event"] in ("entry", "settle")), None)
    doc = {"label": LABEL, "started": started, "start": START, "note": NOTE,
           "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "nav": round(nav, 4), "last_date": log[-1]["date"] if log else None,
           "open_position": (pos if pos and pos["event"] == "entry" else None),
           "n_settled": sum(1 for r in log if r["event"] == "settle"), **(extra or {})}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def step(today: date | None = None, opt_text: str | None = None) -> dict:
    today = today or datetime.now(TW).date()
    log = read_log()
    if today.isoformat() < START:
        write_summary(log, False, {"why_not_started": f"{START[:7]} 起從當月真實資料開始記，不倒填"})
        return {"state": "NOT_STARTED"}
    text = opt_text if opt_text is not None else _get("taifex_openapi", "GET", OPT_URL).content.decode("utf-8-sig", errors="replace")
    day, chain = parse_opt(text)
    if not day or day < START or (log and day <= log[-1]["date"]):
        write_summary(log, bool(log))
        return {"state": "NO_NEW_DAY", "day": day}
    nav = log[-1]["nav"] if log else 100.0
    pos = next((r for r in reversed(log) if r["event"] in ("entry", "settle")), None)
    open_pos = pos if pos and pos["event"] == "entry" else None
    settled_today = False
    if open_pos:
        cm, k = open_pos["contract"], open_pos["strike"]
        if day > open_pos["expiry"]:
            F = final_settlement(cm)
            if F is None:
                write_summary(log, True)
                return {"state": "WAIT_SETTLEMENT", "contract": cm}
            pnl = open_pos["premium_net"] * MULT - abs(F - k) * MULT - 2 * FEE
            nav_new = open_pos["nav_at_entry"] * (1 + pnl / open_pos["capital"])
            append({"date": day, "event": "settle", "contract": cm, "strike": k, "final_settlement": F,
                    "pnl_ntd": round(pnl, 1), "nav": round(nav_new, 6),
                    "note": "到期以期交所官方最後結算價現金結算"})
            nav, open_pos = nav_new, None
            settled_today = True
        else:
            q = chain.get(cm, {}).get(k, {})
            c = (q.get("C") or (None, None))
            p = (q.get("P") or (None, None))
            cv, pv = c[0] or c[1], p[0] or p[1]
            if cv is None or pv is None:
                write_summary(log, True)
                return {"state": "NO_MARK", "day": day}
            liab = (cv + pv) * MULT
            nav_m = open_pos["nav_at_entry"] * (1 + (open_pos["premium_net"] * MULT - liab) / open_pos["capital"])
            append({"date": day, "event": "mark", "contract": cm, "strike": k, "straddle": round(cv + pv, 2),
                    "nav": round(nav_m, 6)})
            write_summary(read_log(), True)
            return {"state": "MARK", "day": day}
    entered_this_month = any(r["event"] == "entry" and r["date"][:7] == day[:7] for r in log)
    if open_pos is None and not entered_this_month:
        S = taiex_close(day)
        d0 = date.fromisoformat(day)
        cands = sorted((abs((third_wednesday(cm) - d0).days - 30), third_wednesday(cm), cm) for cm in chain
                       if 10 <= (third_wednesday(cm) - d0).days <= 45)
        if S and cands:
            cm = cands[0][2]
            ok = {k: v for k, v in chain[cm].items() if (v.get("C") or (None,))[0] and (v.get("P") or (None,))[0]}
            if ok:
                k = min(ok, key=lambda x: abs(x - S))
                prem = ok[k]["C"][0] + ok[k]["P"][0]
                prem_net = prem - 2 * SLIP_PTS - (2 * FEE + TAX * prem * MULT) / MULT
                append({"date": day, "event": "entry", "contract": cm, "expiry": third_wednesday(cm).isoformat(),
                        "strike": k, "taiex": S, "call": ok[k]["C"][0], "put": ok[k]["P"][0], "premium": prem,
                        "premium_net": round(prem_net, 4), "capital": S * MULT, "nav_at_entry": round(nav, 6),
                        "nav": round(nav, 6), "note": "賣出價平跨式 1 組（1 倍名目、持有到期、滑價每口 1 點）"})
                write_summary(read_log(), True)
                return {"state": "ENTRY", "day": day, "contract": cm, "strike": k}
    if log and not settled_today:  # 空手日記一筆，讓淨值曲線每天有點；結算當天已有 settle 紀錄
        append({"date": day, "event": "flat", "nav": round(nav, 6)})
    write_summary(read_log(), bool(read_log()))
    return {"state": "FLAT", "day": day}


def main() -> int:
    try:
        print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 模擬 F 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
