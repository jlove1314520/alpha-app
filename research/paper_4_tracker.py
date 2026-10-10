"""紙.四：R1（0050 核心＋信用利差閘門 × 台股 2 倍腿）前進式紙上追蹤（總司令 2026-10-10【先.五十九】A1）。

**這不是回測，也不是新試驗**——#430 已登記判定（R1-A、R1-C PASS；事前登記 #429）。本檔只在真實日曆時間
往前記帳。初始資金是虛擬值，**不下任何真實單、不接任何下單程式**。與紙.一／紙.一b／紙.三 並行，不取代它們。

兩本帳（參數照事前登記 `docs/PREREG_R1_0050_credit_gate.md`，不改）：

| 帳 | 閘門開 | 閘門關 |
|---|---|---|
| R1-C（主） | 0050 50%＋00631L 50% | 0050 50%＋台幣現金 50% |
| R1-A（並列） | 0050 70%＋00631L 30% | 0050 70%＋台幣現金 30% |

- 閘門、延後一個交易日切換、BAA10Y 到齊才記帳、月末偵測：**直接沿用 `paper_3_tracker.py` 的函式**（同一顆閘門）。
- 槓桿腿用真實 00631L 還原價（回測用合成 2 倍，見草案 `docs/PAPER_4_R1_DRAFT.md` 第 4 節風險 1）。
- **成本照 #430**：只對 0050、00631L 的減碼計賣出證交稅 0.1%（`core_allocation_backtest.TW_SELL_TAX`），
  不計手續費（與紙.三 用 `backtest.engine` 費率不同，這是裁示指定的口徑）。對照組 Bb-90 影子帳用同一套成本。
- 啟動：2026-10 月底（與紙.三 同日）建倉；起始閘門取「建倉日前已知」的最近月底（2026-09-30）判定。
- fail closed：該記帳的日子拿不到 BAA10Y 或價格 → 不記、寫 last_error 與心跳 ERROR，下次排程重試。

輸出：`research/data/paper_4_log.jsonl`（append-only，每列帶 book）、`data/paper_4.json`（App 摘要）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_3_tracker as P3  # noqa: E402  閘門／月末／BAA10Y 函式共用，避免兩套閘門邏輯分岔
from core_allocation_backtest import TW_SELL_TAX  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
LOG_PATH = REPO_ROOT / "research" / "data" / "paper_4_log.jsonl"
APP_SUMMARY_PATH = REPO_ROOT / "data" / "paper_4.json"
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"

CASH = "CASH"
BOOKS = {
    "R1-C": {"open": {"0050": 0.50, "00631L": 0.50}, "closed": {"0050": 0.50, CASH: 0.50}},
    "R1-A": {"open": {"0050": 0.70, "00631L": 0.30}, "closed": {"0050": 0.70, CASH: 0.30}},
}
PRIMARY = "R1-C"
BB90 = {"0050": 0.45, "00646": 0.45, "00697B": 0.10}
SYMBOLS = ("00631L", "0050", "00646", "00697B")
TAXED = {"0050", "00631L", "00646", "00697B"}   # 台股 ETF 減碼一律計賣出稅
INITIAL_VIRTUAL_CAPITAL = 1_000_000.0
START_MONTH = "2026-10"
MAX_STALE_WEEKDAYS = 5
DISCLOSURE = ("回測 2003–2024 年化 15.1%／MDD −36.2%；同一閘門在 2025–26 樣本外 21 個月中有 13 個月關閉"
              "並大幅落後 0050；無樣本外驗證，僅紙上追蹤")


def _now():
    return datetime.now(P3.TZ)


def _today():
    return P3._today()


def _load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _find_duplicate(log: list[dict]) -> str | None:
    seen = set()
    for i, e in enumerate(log):
        k = (e.get("book"), e.get("date"), e.get("event"))
        if k in seen:
            return f"第{i + 1}列 book={k[0]} date={k[1]} event={k[2]} 與先前列重複"
        seen.add(k)
    return None


def _heartbeat(note: str, status: str | None = None) -> None:
    try:
        rec = {"ts": _now().isoformat(), "item": "紙.四", "note": note}
        if status:
            rec["status"] = status
        with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.四 寫心跳失敗：{type(e).__name__}: {e}")


def _read_summary() -> dict:
    try:
        return json.loads(APP_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_summary(summary: dict) -> None:
    summary["generated_at"] = _now().isoformat()
    summary.setdefault("disclaimer", "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。")
    summary["disclosure"] = DISCLOSURE
    summary["books_spec"] = BOOKS
    summary["primary"] = PRIMARY
    APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _abort(status: str, reason: str) -> None:
    print(f"::error::紙.四 中止（{status}）：{reason}")
    try:
        s = _read_summary() or {"started": False}
        s["last_error"] = {"status": status, "reason": reason, "ts": _now().isoformat()}
        _write_summary(s)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.四 寫 last_error 失敗：{type(e).__name__}: {e}")
    _heartbeat(f"中止（{status}）：{reason}", status="ERROR")


def _revalue(prev: dict, d: str, series: dict) -> dict:
    vals = {}
    days = (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(prev["date"], "%Y-%m-%d")).days
    for s, v in prev["values_post"].items():
        if s == CASH:
            rf = P3._rf_annual(d[:7]) or 0.0
            vals[s] = v * (1 + rf / 100.0 * days / 365.0)
        else:
            vals[s] = v * (series[s][d] / prev["prices"][s])
    return vals


def _rebalance(vals: dict, tgt: dict) -> tuple[float, dict, float]:
    """#430 口徑：只有減碼計賣出稅。"""
    nav_pre = sum(vals.values())
    cost = 0.0
    for s in set(vals) | set(tgt):
        if s == CASH or s not in TAXED:
            continue
        diff = nav_pre * tgt.get(s, 0.0) - vals.get(s, 0.0)
        if diff < 0:
            cost += -diff * TW_SELL_TAX
    nav = nav_pre - cost
    return nav, {s: nav * w for s, w in tgt.items()}, cost


def _bench(prev_b: dict, d: str, series: dict, rebalance: bool) -> dict:
    v = {s: prev_b["bb90_values"][s] * (series[s][d] / prev_b["prices"][s]) for s in BB90}
    if rebalance:
        nav, vpost, _ = _rebalance(v, BB90)
    else:
        nav, vpost = sum(v.values()), v
    return {"prices": {s: series[s][d] for s in SYMBOLS}, "bb90_nav": nav, "bb90_values": vpost,
            "hold_0050_nav": prev_b["hold_0050_nav"] * (series["0050"][d] / prev_b["prices"]["0050"])}


def _run_book(book: str, blog: list[dict], series: dict, common: list[str], month_ends: list[str], baa: dict) -> int:
    spec = BOOKS[book]
    tgt_of = lambda is_open: dict(spec["open"] if is_open else spec["closed"])  # noqa: E731
    processed = 0
    if not blog:
        d0 = month_ends[0]
        if not P3.baa_month_complete(baa, P3._calendar_month_ends(d0, 1)[-1]):
            print(f"[紙.四 {book}] {d0} 建倉延後：當月 BAA10Y 尚未公布完整")
            return 0
        prev_me = P3._calendar_month_ends(
            (datetime.strptime(d0, "%Y-%m-%d").replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d"), 14)
        g0 = P3.gate_decision(baa, prev_me[-1], prev_me)
        tgt = tgt_of(g0["gate_open"])
        px = {s: series[s][d0] for s in SYMBOLS}
        nav = INITIAL_VIRTUAL_CAPITAL
        entry = {"book": book, "date": d0, "logged_at": _now().isoformat(), "event": "inception",
                 "gate_open": g0["gate_open"], "gate_basis": g0, "prices": px, "targets": tgt,
                 "values_post": {s: nav * w for s, w in tgt.items()}, "nav": nav, "rebalance_cost": 0.0,
                 "bench": {"prices": px, "bb90_nav": nav, "bb90_values": {s: nav * w for s, w in BB90.items()},
                           "hold_0050_nav": nav},
                 "note": "建倉：以目標權重買入，成本不計（虛擬建倉）"}
        cal0 = P3._calendar_month_ends(d0, 14)
        gn = P3.gate_decision(baa, cal0[-1], cal0)
        entry["gate_decision_for_next"] = gn
        if gn["gate_open"] != g0["gate_open"]:
            entry["pending_switch"] = {"decided_on": d0, "to_open": gn["gate_open"], "basis": gn}
        _append_log(entry)
        blog.append(entry)
        processed += 1

    def _next_td(d: str) -> str | None:
        nxt = [x for x in common if x > d]
        return nxt[0] if nxt else None

    while True:
        last = blog[-1]
        cand = [(me, "month_end") for me in month_ends
                if me > last["date"] and not any(e["date"] == me and e["event"] in ("month_end", "inception") for e in blog)]
        pend = last.get("pending_switch")
        if pend:
            sd = _next_td(pend["decided_on"])
            if sd and sd > last["date"]:
                cand.append((sd, "gate_switch"))
        if not cand:
            break
        d, ev = sorted(cand)[0]
        vals = _revalue(last, d, series)
        bench = _bench(last["bench"], d, series, rebalance=(ev == "month_end"))
        base = {"book": book, "date": d, "logged_at": _now().isoformat(), "event": ev,
                "prices": {s: series[s][d] for s in SYMBOLS}, "nav_pre_rebalance": sum(vals.values()), "bench": bench}
        if ev == "gate_switch":
            gate_open = pend["to_open"]
            nav, vpost, cost = _rebalance(vals, tgt_of(gate_open))
            entry = dict(base, gate_open=gate_open, gate_basis=pend["basis"], targets=tgt_of(gate_open),
                         rebalance_cost=cost, nav=nav, values_post=vpost,
                         note="閘門狀態變更：月底判定、延後一個交易日切換")
        else:
            if not P3.baa_month_complete(baa, P3._calendar_month_ends(d, 1)[-1]):
                print(f"[紙.四 {book}] {d} 月底：當月 BAA10Y 尚未公布完整，本次不記帳（下次排程再試）")
                break
            gate_open = last["gate_open"]
            nav, vpost, cost = _rebalance(vals, tgt_of(gate_open))
            cal = P3._calendar_month_ends(d, 14)
            g = P3.gate_decision(baa, cal[-1], cal)
            entry = dict(base, gate_open=gate_open, gate_decision_for_next=g, targets=tgt_of(gate_open),
                         rebalance_cost=cost, nav=nav, values_post=vpost)
            if g["gate_open"] != gate_open:
                entry["pending_switch"] = {"decided_on": d, "to_open": g["gate_open"], "basis": g}
        _append_log(entry)
        blog.append(entry)
        processed += 1
    return processed


def _book_summary(blog: list[dict]) -> dict:
    last = blog[-1]
    b = last["bench"]
    pct = lambda v: round((v / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2)  # noqa: E731
    closed_months = sum(1 for e in blog if e["event"] in ("month_end", "inception") and not e["gate_open"])
    return {"as_of_date": last["date"], "nav": last["nav"], "total_return_pct": pct(last["nav"]),
            "gate_open": last["gate_open"], "pending_switch": last.get("pending_switch"),
            "weights_post": {s: round(v / last["nav"], 4) for s, v in last["values_post"].items()},
            "bench_bb90_return_pct": pct(b["bb90_nav"]), "bench_0050_return_pct": pct(b["hold_0050_nav"]),
            "inception_date": blog[0]["date"], "rows": len(blog), "gate_closed_month_ends": closed_months}


def run() -> dict:
    log = _load_log()
    dup = _find_duplicate(log)
    if dup:
        _abort("DUPLICATE_LOG_ENTRY", dup)
        return {"aborted": True}
    prices = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8")).get("prices") or {}
    series = {s: P3._closes(prices, s) for s in SYMBOLS}
    missing = [s for s, v in series.items() if not v]
    if missing:
        _abort("MISSING_PRICE_SERIES", f"price_history.json 缺少標的：{missing}")
        return {"aborted": True}
    common = sorted(set.intersection(*(set(v) for v in series.values())))
    if not common:
        _abort("NO_COMMON_DATES", "四檔標的沒有共同交易日")
        return {"aborted": True}
    last_d = datetime.strptime(common[-1], "%Y-%m-%d").date()
    today = _today()
    wd = sum(1 for i in range(1, (today - last_d).days + 1) if (last_d + timedelta(days=i)).weekday() < 5)
    if wd > MAX_STALE_WEEKDAYS:
        _abort("ABORTED_STALE_PRICE", f"最新共同交易日 {common[-1]} 落後今天 {wd} 個平日，價格過期")
        return {"aborted": True}
    try:
        baa = P3.fetch_baa()
    except Exception as e:  # noqa: BLE001
        _abort("BAA10Y_UNAVAILABLE", f"取不到 FRED BAA10Y（{type(e).__name__}）；本次不記帳，下次排程重試")
        return {"aborted": True}
    cal_me = P3._calendar_month_ends((today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d"), 14)
    try:
        cur_gate = P3.gate_decision(baa, cal_me[-1], cal_me)
    except Exception as e:  # noqa: BLE001
        _abort("GATE_UNDECIDABLE", str(e))
        return {"aborted": True}

    month_ends = [d for d in P3._month_ends(common) if d[:7] >= START_MONTH]
    if not month_ends and not log:
        _write_summary({"started": False, "note": f"{START_MONTH} 月底建倉（與紙.三 同日），尚未到啟動日",
                        "gate_now": cur_gate})
        print(f"[紙.四] 尚未到 {START_MONTH} 月底（最新 {common[-1]}），目前閘門 {'開' if cur_gate['gate_open'] else '關'}")
        return {"processed": 0, "started": False, "gate_now": cur_gate}

    processed, books = 0, {}
    for book in BOOKS:
        blog = [e for e in log if e.get("book") == book]
        processed += _run_book(book, blog, series, common, month_ends, baa)
        if blog:
            books[book] = _book_summary(blog)
    if not books:
        _write_summary({"started": False, "note": "建倉日當月 BAA10Y 尚未公布完整，下次排程建倉", "gate_now": cur_gate})
        return {"processed": 0, "started": False, "gate_now": cur_gate}
    _write_summary({"started": True, "gate_now": cur_gate, "books": books,
                    "initial_virtual_capital": INITIAL_VIRTUAL_CAPITAL,
                    "note": "紙.四＝R1（#429／#430）台灣可執行版；槓桿腿用 00631L 真實價；閘門延後一個交易日切換；成本照 #430"})
    if processed:
        _heartbeat(f"處理 {processed} 筆（{'、'.join(k + ' ' + v['as_of_date'] for k, v in books.items())}）")
    print(f"[紙.四] 處理 {processed} 筆：" + "；".join(f"{k} 淨值 {v['nav']:.2f}" for k, v in books.items()))
    return {"processed": processed, "started": True, "gate_now": cur_gate}


def _enter_sandbox(sandbox: str, prices: str, today: str, baa_json: str | None) -> None:
    global PRICE_HISTORY_PATH, LOG_PATH, APP_SUMMARY_PATH, HEARTBEAT_PATH
    sb = Path(sandbox).resolve()
    official = [(REPO_ROOT / "research" / "data").resolve(), (REPO_ROOT / "data").resolve(),
                (REPO_ROOT / "research").resolve()]   # 固定比對正式目錄（不讀可能已被改成沙盒的全域路徑）
    if any(sb == o for o in official):
        raise SystemExit(f"沙盒目錄不得等於正式目錄：{sb}")
    sb.mkdir(parents=True, exist_ok=True)
    PRICE_HISTORY_PATH = Path(prices).resolve()
    LOG_PATH = sb / "paper_4_log.jsonl"
    APP_SUMMARY_PATH = sb / "paper_4.json"
    HEARTBEAT_PATH = sb / "PROGRESS_HEARTBEAT.jsonl"
    P3._TODAY_OVERRIDE = today
    if baa_json:
        P3._BAA_OVERRIDE = json.loads(Path(baa_json).read_text(encoding="utf-8"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sandbox")
    ap.add_argument("--prices")
    ap.add_argument("--today")
    ap.add_argument("--baa-json", help="dry-run 用：{date: value} 的 BAA10Y 檔，不連網")
    a = ap.parse_args()
    if a.dry_run:
        if not (a.sandbox and a.prices and a.today):
            raise SystemExit("--dry-run 必須同時給 --sandbox --prices --today")
        _enter_sandbox(a.sandbox, a.prices, a.today, a.baa_json)
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        import traceback
        print("::error::紙.四 執行失敗，已寫入 last_error 與心跳（不影響其他排程步驟）")
        print(traceback.format_exc())
        _abort("EXCEPTION", f"{type(exc).__name__}: {exc}")
        sys.exit(0)
