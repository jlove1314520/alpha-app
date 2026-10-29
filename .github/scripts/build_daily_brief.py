"""盤前日報與週覆盤（規則摘要）產生器。

2026-10-11 常備.開發-2：App 今日頁「AI 盤前日報」與日誌頁「AI 週覆盤」原本是
誠實空狀態（佔位文案）。這支用**固定規則**把既有排程產物整理成摘要，
不呼叫任何語言模型、不做市場判斷、不發出外部請求（只讀 repo 內既有檔案），
輸出 data/daily_brief.json。

讀取（全部是既有排程產物，本檔不額外打任何 API）：
  data/market_us.json   昨夜美股四大指數（fetch_market_us.py）
  data/market_tw.json   台指期／加權指數（fetch_market_tw.py）
  data/events.json      重大訊息／法說會／除權息事件日曆（fetch_news_events.py）
  data/news.json        新聞索引（只用 codes 欄位計數）
  data/strategy_curves.json  紙上追蹤（週覆盤用，與首頁「跟 0050 比」同一份；先.一〇三-5）

自選股存在使用者手機 localStorage，排程端看不到，所以這裡只輸出
「每檔代號 → 近一日重大訊息／新聞則數」對照表，由 App 端用自選股清單過濾。
真錢帳本（/auto/ledger）只在本機伺服器，同理由 App 端補上本週委託筆數，
不進公開 repo。

失敗隔離（CLAUDE.md 十二）：任何一塊讀不到只在該塊標 error，其他塊照出；
整支程式永遠 exit 0，不中斷 market.yml 後續步驟。
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "daily_brief.json"
TPE = timezone(timedelta(hours=8))
DISCLAIMER = "規則摘要，非 AI 判斷、非投資建議"
# 「重大訊息」類事件（不含每月例行的月營收與除權息，那兩類另外計數）
MATERIAL_SOURCES = ("TWSE 重大訊息", "TPEx 重大訊息")
UPCOMING_DAYS = 3


def _load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def _pct(v):
    return None if v is None else round(float(v), 2)


def _sign(v):
    return "—" if v is None else ("+" if v > 0 else "") + f"{v:.2f}%"


def block_us():
    d = _load("market_us.json")
    rows = []
    for sym, v in (d.get("indices") or {}).items():
        rows.append({"symbol": sym, "name": v.get("name"), "close": v.get("close"),
                     "change_pct": _pct(v.get("change_pct")), "as_of": v.get("as_of")})
    return {"fetched_at": d.get("fetched_at"), "indices": rows}


def block_tw():
    d = _load("market_tw.json")
    fut = (d.get("futures") or {}).get("TX") or d.get("tx_futures") or {}
    tx = d.get("taiex") or {}
    dates = tx.get("sparkline_dates") or []
    return {
        "fetched_at": d.get("fetched_at"),
        "taiex": {"close": tx.get("close"), "change_pct": _pct(tx.get("change_pct")),
                  "as_of": dates[-1] if dates else None},
        "tx_futures": {"contract_month": fut.get("contract_month"), "last": fut.get("last"),
                       "change_pct": _pct(fut.get("change_pct")), "session": fut.get("trading_session"),
                       # 先.一〇四-6：台指期自己的資料日（晚班可能落後現貨一天），App 用來把落後的那行變灰
                       "as_of": fut.get("data_date") or (f"{fut['date'][:4]}-{fut['date'][4:6]}-{fut['date'][6:8]}" if str(fut.get("date") or "").isdigit() and len(str(fut.get("date"))) == 8 else None)},
    }


def block_events(today):
    ev = _load("events.json").get("events") or []
    end = (today + timedelta(days=UPCOMING_DAYS)).isoformat()
    t = today.isoformat()
    upcoming = [e for e in ev if t <= str(e.get("date") or "") <= end and e.get("type") in ("法說會", "除權息")]
    upcoming.sort(key=lambda e: (e.get("date"), e.get("type"), e.get("code")))
    material = [e for e in ev if e.get("source") in MATERIAL_SOURCES and str(e.get("date") or "") < t]
    last_day = max((e["date"] for e in material), default=None)
    latest = [e for e in material if e.get("date") == last_day]
    by_code = Counter(e.get("code") for e in latest if e.get("code"))
    return {
        "upcoming_window_days": UPCOMING_DAYS,
        "upcoming_counts": dict(Counter(e["type"] for e in upcoming)),
        "upcoming": [{k: e.get(k) for k in ("date", "type", "code", "name", "title")} for e in upcoming[:30]],
        "material_date": last_day,
        "material_total": len(latest),
        "material_type_counts": dict(Counter(e.get("type") for e in latest)),
        "material_by_code": dict(by_code),
    }


def block_news():
    # 先.一〇五-3：個股新聞則數改讀存檔索引（近 7 天），news.json 只是首頁最新小檔（約 2 天份）
    try:
        idx = _load("news_by_code/_index.json")
        codes = idx.get("codes") or {}
        if codes:
            by7 = {c: v.get("d7", 0) for c, v in codes.items() if v.get("d7")}
            return {"fetched_at": idx.get("generated_at"), "total": sum(by7.values()), "by_code": by7,
                    "window": "近 7 天（data/news_by_code/_index.json）"}
    except Exception as e:  # noqa: BLE001 -- 讀不到存檔就退回原本算法
        print(f"::warning::news_by_code 索引讀取失敗，改用 news.json：{type(e).__name__}: {e}")
    d = _load("news.json")
    by_code = Counter()
    for n in d.get("news") or []:
        for c in n.get("codes") or []:
            by_code[c] += 1
    return {"fetched_at": d.get("fetched_at"), "total": len(d.get("news") or []), "by_code": dict(by_code)}


def block_paper():
    """先.一〇三-5：週覆盤的紙上追蹤改讀 strategy_curves.json（與首頁「跟 0050 比」、交易頁同一份數字與名稱），
    不再各自讀 paper_*.json——舊做法名稱用內部代號（紙.一b…）、報酬口徑也跟首頁不同。"""
    sc = _load("strategy_curves.json")
    rows = []
    for ln in sc.get("lines") or []:
        if ln.get("group") != "paper":
            continue
        m = ln.get("metrics") or {}
        rows.append({"id": ln.get("id"), "label": ln.get("label"), "started": bool(ln.get("started")),
                     "start_date": ln.get("start_date"), "note": None if ln.get("started") else (ln.get("inception_note") or ln.get("note")),
                     "as_of": ln.get("as_of"), "total_return_pct": _pct(m.get("cum_pct")),
                     "bench_return_pct": _pct(m.get("bench_cum_pct")), "source": "data/strategy_curves.json"})
    return rows


def taiex_week_change(tw, week_start):
    """以 market_tw.json 的 sparkline 算本週漲跌：上週最後收盤 → 最新收盤。"""
    d = _load("market_tw.json").get("taiex") or {}
    closes, dates = d.get("sparkline") or [], d.get("sparkline_dates") or []
    if len(closes) != len(dates) or not dates:
        return None
    prev = [c for c, dt in zip(closes, dates) if dt < week_start.isoformat()]
    this = [dt for dt in dates if dt >= week_start.isoformat()]
    if not prev or not this:
        return None
    return {"from_close": prev[-1], "to_close": closes[-1], "to_date": dates[-1],
            "change_pct": round((closes[-1] / prev[-1] - 1) * 100, 2), "days": len(this)}


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f"[warn] {fn.__name__} 失敗：{e}", file=sys.stderr)
        return {"error": f"{type(e).__name__}: {e}"}


def main():
    now = datetime.now(TPE)
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    us, tw, evs, news = _safe(block_us), _safe(block_tw), _safe(block_events, today), _safe(block_news)

    lines = []
    # 先.一〇四-6：line_dates／line_markets 跟 lines 一一對應（非行情行為 None），App 比對各市場最後交易日決定要不要變灰
    line_dates: list = []
    line_markets: list = []
    if "error" not in us and us.get("indices"):
        asof = us["indices"][0].get("as_of")
        lines.append(f"美股（{asof}）：" + "、".join(f"{r['name']} {_sign(r['change_pct'])}" for r in us["indices"]))
        line_dates.append(asof); line_markets.append("us")
    if "error" not in tw:
        f = tw["tx_futures"]
        if f.get("last") is not None:
            lines.append(f"台指期 {f.get('contract_month')}（{f.get('session') or '—'}盤）{f['last']:,.0f}，{_sign(f.get('change_pct'))}")
            line_dates.append(f.get("as_of")); line_markets.append("tw")
        t = tw["taiex"]
        if t.get("close") is not None:
            lines.append(f"加權指數前收（{t.get('as_of')}）{t['close']:,.2f}，{_sign(t.get('change_pct'))}")
            line_dates.append(t.get("as_of")); line_markets.append("tw")
    if "error" not in evs:
        uc = evs["upcoming_counts"]
        lines.append(f"未來 {UPCOMING_DAYS} 天事件：法說會 {uc.get('法說會', 0)} 場、除權息 {uc.get('除權息', 0)} 檔")
        if evs.get("material_date"):
            tc = "、".join(f"{k} {v}" for k, v in sorted(evs["material_type_counts"].items(), key=lambda x: -x[1]))
            lines.append(f"{evs['material_date']} 上市櫃重大訊息 {evs['material_total']} 則（{tc}）")

    tw_wk = _safe(taiex_week_change, tw, week_start)
    if tw_wk is None:  # 週一盤前本週還沒有收盤 → 改報上一週，週起日一併改，避免標錯週
        week_start -= timedelta(days=7)
        tw_wk = _safe(taiex_week_change, tw, week_start)
    weekly = {"week_start": week_start.isoformat(), "taiex_week": tw_wk, "paper": _safe(block_paper)}
    wl = []
    if tw_wk and "error" not in tw_wk:
        wl.append(f"加權指數 {week_start.isoformat()} 當週 {tw_wk['days']} 個交易日 {_sign(tw_wk['change_pct'])}（{tw_wk['from_close']:,.2f}→{tw_wk['to_close']:,.2f}）")
    if isinstance(weekly["paper"], list):
        started = [p for p in weekly["paper"] if p.get("started")]
        wl.append(f"紙上追蹤：{len(started)}／{len(weekly['paper'])} 條已啟動" +
                  ("（" + "、".join(f"{p['label']} 累計 {_sign(p.get('total_return_pct'))}" for p in started) + "）" if started else ""))

    if not lines and not wl:
        # 先.一三五-1cg：所有輸入都讀不到（盤前、週覆盤都沒有一行）→ 不覆寫既有 daily_brief.json，App 照舊顯示上一份有日期的摘要。
        print("[warn] 盤前與週覆盤都沒有可寫的內容（輸入全讀不到）——不覆寫既有 daily_brief.json", file=sys.stderr)
        return
    try:
        data_asof = ((_load("market_tw.json").get("taiex") or {}).get("sparkline_dates") or [None])[-1]
    except Exception as e:  # noqa: BLE001 -- 先.一三五-1cg：market_tw 讀不到只讓資料日留空，其他塊照出（本檔檔頭失敗隔離）
        print(f"[warn] data_asof 讀 market_tw.json 失敗：{type(e).__name__}: {e}", file=sys.stderr)
        data_asof = None
    out = {
        "generated_at": now.isoformat(timespec="seconds"),
        "date": today.isoformat(),
        # 先.八十-10：前台顯示「資料日＝最後交易日」，不顯示產生時間（取加權指數走勢最後一個交易日）
        "data_asof": data_asof,
        "method": "固定規則摘要（不呼叫語言模型、不做市場判斷）；只讀 repo 內既有排程產物，不額外請求外部 API",
        "disclaimer": DISCLAIMER,
        "premarket": {"lines": lines, "line_dates": line_dates + [None] * (len(lines) - len(line_dates)),
                      "line_markets": line_markets + [None] * (len(lines) - len(line_markets)),
                      "us": us, "tw": tw, "events": evs, "news": news},
        "weekly": dict(weekly, lines=wl),
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[ok] daily_brief.json：盤前 {len(lines)} 行、週覆盤 {len(wl)} 行")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 守門：自身失敗只警告，不中斷排程（CLAUDE.md 十二）
        print(f"[warn] build_daily_brief 失敗：{e}", file=sys.stderr)
    sys.exit(0)
