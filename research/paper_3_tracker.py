"""紙.三：S3-C6（信用利差危機閘門 × 槓桿版 Bb-90 C6）前進式紙上追蹤（總司令 2026-10-07【先.四十七】二）。

**這不是回測，也不是新試驗**——#424 已登記判定（S3-C6 PASS，#426）。本檔只在真實日曆時間往前記帳，
驗證規則、資料管線與排程能正確運作。初始資金是虛擬值，**不下任何真實單、不接任何下單程式**。
與紙.一（70/30）、紙.一b（Bb-90）並行，不取代、不改動它們。

配置（#421 C6 的台灣可執行版；槓桿腿用真實 ETF，不再合成）：

| 狀態 | 00631L（台 2 倍） | 00647L（美 2 倍） | 0050 | 00646 | 00697B | 台幣現金 |
|---|---|---|---|---|---|---|
| 閘門開 | 25% | 25% | 15% | 15% | 20% | 0% |
| 閘門關 | 0% | 0% | 15% | 15% | 20% | 50% |

閘門（#424 S3，參數不變）：每個月底取當日（向前填補）美國 BAA10Y，與「含當月共 12 個月底值」平均比較，
**高於平均＝閘門關**。資料來源 FRED 官方公開 CSV（`fred.stlouisfed.org/graph/fredgraph.csv?id=BAA10Y`，
免金鑰；每次執行一次請求）。

**延後一個交易日切換（避開前視，先.四十五 敏感度採用的版本）**：BAA10Y 月底值要到台北隔天清晨才公布，
所以月底那天照「舊狀態」目標再平衡，**下一個交易日收盤**才切換到新狀態（事件 `gate_switch`）。

現金腿：按 `data/rf_monthly.json` 央行一個月定存利率（年化%）依日數計息；查不到當月利率以 0 計並記錄。

對照（同一天起算、同一套成本）：Bb-90 影子帳（0050 45%／00646 45%／00697B 10%，月底再平衡）、0050 全持有。

**啟動**：2026-10 月底（最後一個交易日）建倉，起始閘門狀態取「建倉日前已知」的最近月底（2026-09-30）判定。
**冪等與防重複、月末偵測、沙盒 dry-run**：沿用紙.一b 的做法。
**fail closed**：該記帳的日子拿不到 BAA10Y 或價格 → 不記、寫 last_error 與心跳 ERROR，下次排程重試。

輸出：`research/data/paper_3_log.jsonl`（append-only）、`data/paper_3.json`（App 摘要）。
"""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
RF_PATH = REPO_ROOT / "data" / "rf_monthly.json"
LOG_PATH = REPO_ROOT / "research" / "data" / "paper_3_log.jsonl"
APP_SUMMARY_PATH = REPO_ROOT / "data" / "paper_3.json"
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAA10Y&cosd={start}"

CASH = "CASH"
TARGETS_OPEN = {"00631L": 0.25, "00647L": 0.25, "0050": 0.15, "00646": 0.15, "00697B": 0.20}
TARGETS_CLOSED = {CASH: 0.50, "0050": 0.15, "00646": 0.15, "00697B": 0.20}
BB90 = {"0050": 0.45, "00646": 0.45, "00697B": 0.10}
SYMBOLS = ("00631L", "00647L", "0050", "00646", "00697B")
INITIAL_VIRTUAL_CAPITAL = 1_000_000.0
START_MONTH = "2026-10"          # 2026-10 月底建倉
GATE_LOOKBACK = 12
TZ = timezone(timedelta(hours=8))
MAX_STALE_WEEKDAYS = 5
_TODAY_OVERRIDE: str | None = None
_BAA_OVERRIDE: dict | None = None   # 僅 dry-run／自測：{date: value}

_CFG = BacktestConfig(start_date="2026-10-01", end_date="2026-10-01",
                      initial_capital=INITIAL_VIRTUAL_CAPITAL,
                      commission_discount=0.18, instrument_type="etf",
                      book_name="paper_3_tracker")
BUY_RATE = buy_leg_rate(_CFG)
SELL_RATE = sell_leg_rate(_CFG)


def _today():
    if _TODAY_OVERRIDE:
        return datetime.strptime(_TODAY_OVERRIDE, "%Y-%m-%d").date()
    return datetime.now(TZ).date()


def _targets(gate_open: bool) -> dict:
    return dict(TARGETS_OPEN if gate_open else TARGETS_CLOSED)


# ---------- 資料 ----------
def _closes(prices: dict, sym: str) -> dict:
    out = {}
    for r in prices.get(sym) or []:
        v = r.get("adj_close")
        if v is None:
            v = r.get("close")
        if v is not None:
            out[r["date"]] = float(v)
    return out


def fetch_baa(start: str = "2024-06-01") -> dict:
    """{YYYY-MM-DD: value}。失敗拋例外（呼叫端 fail closed）。"""
    if _BAA_OVERRIDE is not None:
        return dict(_BAA_OVERRIDE)
    import requests
    # 用 requests 預設 User-Agent：2026-10-07 實測自訂 UA（含瀏覽器字串）會被 FRED 延遲到逾時，預設值 0.3 秒回應。
    r = requests.get(FRED_CSV.format(start=start), timeout=30)
    r.raise_for_status()
    out = {}
    for row in csv.reader(io.StringIO(r.text)):
        if len(row) < 2 or not row[0][:4].isdigit():
            continue
        try:
            out[row[0]] = float(row[1])
        except ValueError:
            continue      # "." = 當日無觀測值
    if not out:
        raise RuntimeError("FRED BAA10Y 回傳沒有任何數值")
    return out


def _baa_on(baa: dict, d: str) -> float | None:
    ks = [k for k in baa if k <= d]
    return baa[max(ks)] if ks else None


def baa_month_complete(baa: dict, month_end_cal: str) -> bool:
    """該日曆月的 BAA10Y 已到齊：有該月最後一個平日的值，或已出現下個月的值（月底逢美國假日時）。
    FRED 約隔一天公布，台股月底當晚跑時美國當天值通常還沒有——此時不記帳，避免默默用前一天的值。"""
    d = datetime.strptime(month_end_cal, "%Y-%m-%d")
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    last_wd = d.strftime("%Y-%m-%d")
    return last_wd in baa or any(k > month_end_cal for k in baa)


def gate_decision(baa: dict, month_end: str, month_ends_hist: list[str]) -> dict:
    """#424 S3：month_end 的 BAA10Y 與含當月共 12 個月底值平均比較；高於平均＝閘門關。
    month_ends_hist 為「日曆月底」清單（含 month_end 本月，共 ≥12 個）。"""
    me = [m for m in month_ends_hist if m <= month_end][-GATE_LOOKBACK:]
    vals = [_baa_on(baa, m) for m in me]
    if len(me) < GATE_LOOKBACK or any(v is None for v in vals):
        raise RuntimeError(f"BAA10Y 月底值不足 {GATE_LOOKBACK} 個（{month_end}）")
    cur, avg = vals[-1], sum(vals) / len(vals)
    return {"month_end": month_end, "baa10y": cur, "avg12": round(avg, 4), "gate_open": not (cur > avg),
            "baa_data_date": max(k for k in baa if k <= month_end)}


def _calendar_month_ends(upto: str, n: int = 14) -> list[str]:
    """回傳 upto 所在月（含）往前 n 個日曆月的最後一天（YYYY-MM-DD）。BAA10Y 以 <= 該日最近值向前填補。"""
    y, m = int(upto[:4]), int(upto[5:7])
    out = []
    for _ in range(n):
        nxt = datetime(y + (m == 12), (m % 12) + 1, 1)
        out.append((nxt - timedelta(days=1)).strftime("%Y-%m-%d"))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return sorted(out)


def _rf_annual(month: str) -> float | None:
    try:
        d = json.loads(RF_PATH.read_text(encoding="utf-8"))
        rows = {r["date"][:7]: r.get("rf_rate_pct") for r in d.get("monthly") or []}
        v = rows.get(month)
        if v is None and rows:  # 當月尚未公布→沿用最近一個月（記錄）
            prev = [k for k in rows if k <= month]
            v = rows[max(prev)] if prev else None
        return None if v is None else float(v)
    except Exception:
        return None


# ---------- 帳本 ----------
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
        k = (e.get("date"), e.get("event"))
        if k in seen:
            return f"第{i + 1}列 date={k[0]} event={k[1]} 與先前列重複"
        seen.add(k)
    return None


def _heartbeat(note: str, status: str | None = None) -> None:
    try:
        rec = {"ts": datetime.now(TZ).isoformat(), "item": "紙.三", "note": note}
        if status:
            rec["status"] = status
        with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.三 寫心跳失敗：{type(e).__name__}: {e}")


def _read_summary() -> dict:
    try:
        return json.loads(APP_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_summary(summary: dict) -> None:
    summary["generated_at"] = datetime.now(TZ).isoformat()
    summary.setdefault("disclaimer", "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。")
    APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _abort(status: str, reason: str) -> None:
    print(f"::error::紙.三 中止（{status}）：{reason}")
    try:
        s = _read_summary() or {"started": False}
        s["last_error"] = {"status": status, "reason": reason, "ts": datetime.now(TZ).isoformat()}
        _write_summary(s)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.三 寫 last_error 失敗：{type(e).__name__}: {e}")
    _heartbeat(f"中止（{status}）：{reason}", status="ERROR")


def _is_last_weekday_of_month(d: str) -> bool:
    x = datetime.strptime(d, "%Y-%m-%d").date()
    nxt = x + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt.month != x.month


def _month_ends(dates: list[str]) -> list[str]:
    """已確認的月末交易日（沿用紙.一b：連續兩筆月份不同，或最新一筆即該月最後平日）。"""
    out = [a for a, b in zip(dates, dates[1:]) if a[:7] != b[:7]]
    if dates and _is_last_weekday_of_month(dates[-1]) and dates[-1] not in out:
        out.append(dates[-1])
    return out


def _revalue(prev: dict, d: str, series: dict) -> dict:
    """把上一筆 values_post 推進到 d 的收盤；現金依日數計息。"""
    vals = {}
    days = (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(prev["date"], "%Y-%m-%d")).days
    for s, v in prev["values_post"].items():
        if s == CASH:
            rf = _rf_annual(d[:7]) or 0.0
            vals[s] = v * (1 + rf / 100.0 * days / 365.0)
        else:
            vals[s] = v * (series[s][d] / prev["prices"][s])
    return vals


def _rebalance(vals: dict, tgt: dict) -> tuple[float, dict, float]:
    nav_pre = sum(vals.values())
    cost = 0.0
    keys = set(vals) | set(tgt)
    for s in keys:
        if s == CASH:
            continue
        diff = nav_pre * tgt.get(s, 0.0) - vals.get(s, 0.0)
        cost += abs(diff) * (BUY_RATE if diff > 0 else SELL_RATE)
    nav = nav_pre - cost
    return nav, {s: nav * w for s, w in tgt.items()}, cost


def _bench_step(prev_b: dict, d: str, series: dict) -> dict:
    """Bb-90 影子帳月底再平衡、0050 全持有。"""
    v = {s: prev_b["bb90_values"][s] * (series[s][d] / prev_b["prices"][s]) for s in BB90}
    nav_pre = sum(v.values())
    cost = sum(abs(nav_pre * w - v[s]) * (BUY_RATE if nav_pre * w > v[s] else SELL_RATE) for s, w in BB90.items())
    nav = nav_pre - cost
    return {"prices": {s: series[s][d] for s in SYMBOLS}, "bb90_nav": nav,
            "bb90_values": {s: nav * w for s, w in BB90.items()},
            "hold_0050_nav": prev_b["hold_0050_nav"] * (series["0050"][d] / prev_b["prices"]["0050"])}


def run() -> dict:
    log = _load_log()
    dup = _find_duplicate(log)
    if dup:
        _abort("DUPLICATE_LOG_ENTRY", dup)
        return {"aborted": True}

    prices = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8")).get("prices") or {}
    series = {s: _closes(prices, s) for s in SYMBOLS}
    missing = [s for s, v in series.items() if not v]
    if missing:
        _abort("MISSING_PRICE_SERIES", f"price_history.json 缺少標的：{missing}")
        return {"aborted": True}
    common = sorted(set.intersection(*(set(v) for v in series.values())))
    if not common:
        _abort("NO_COMMON_DATES", "五檔標的沒有共同交易日")
        return {"aborted": True}
    last_d = datetime.strptime(common[-1], "%Y-%m-%d").date()
    today = _today()
    wd = sum(1 for i in range(1, (today - last_d).days + 1) if (last_d + timedelta(days=i)).weekday() < 5)
    if wd > MAX_STALE_WEEKDAYS:
        _abort("ABORTED_STALE_PRICE", f"最新共同交易日 {common[-1]} 落後今天 {wd} 個平日，價格過期")
        return {"aborted": True}

    try:
        baa = fetch_baa()
    except Exception as e:  # noqa: BLE001
        _abort("BAA10Y_UNAVAILABLE", f"取不到 FRED BAA10Y（{type(e).__name__}）；本次不記帳，下次排程重試")
        return {"aborted": True}

    # 目前閘門狀態（給 App 顯示）：最近一個「已過」的日曆月底
    cal_me = _calendar_month_ends((today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d"), 14)
    try:
        cur_gate = gate_decision(baa, cal_me[-1], cal_me)
    except Exception as e:  # noqa: BLE001
        _abort("GATE_UNDECIDABLE", str(e))
        return {"aborted": True}

    month_ends = [d for d in _month_ends(common) if d[:7] >= START_MONTH]
    processed = 0

    if not log:
        if not month_ends:
            _write_summary({"started": False, "note": f"{START_MONTH} 月底建倉，尚未到啟動日",
                            "gate_now": cur_gate, "targets_open": TARGETS_OPEN, "targets_closed": TARGETS_CLOSED})
            print(f"[紙.三] 尚未到 {START_MONTH} 月底（最新 {common[-1]}），目前閘門 {'開' if cur_gate['gate_open'] else '關'}")
            return {"processed": 0, "started": False, "gate_now": cur_gate}
        d0 = month_ends[0]
        if not baa_month_complete(baa, _calendar_month_ends(d0, 1)[-1]):
            _write_summary({"started": False, "note": f"{d0} 建倉日：當月 BAA10Y 尚未公布完整，下次排程建倉",
                            "gate_now": cur_gate, "targets_open": TARGETS_OPEN, "targets_closed": TARGETS_CLOSED})
            print(f"[紙.三] {d0} 建倉延後：當月 BAA10Y 尚未公布完整")
            return {"processed": 0, "started": False, "gate_now": cur_gate}
        prev_me = _calendar_month_ends((datetime.strptime(d0, "%Y-%m-%d").replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d"), 14)
        g0 = gate_decision(baa, prev_me[-1], prev_me)          # 建倉日前已知的最近月底
        tgt = _targets(g0["gate_open"])
        px = {s: series[s][d0] for s in SYMBOLS}
        nav = INITIAL_VIRTUAL_CAPITAL
        entry = {"date": d0, "logged_at": datetime.now(TZ).isoformat(), "event": "inception",
                 "gate_open": g0["gate_open"], "gate_basis": g0, "prices": px, "targets": tgt,
                 "values_post": {s: nav * w for s, w in tgt.items()}, "nav": nav, "rebalance_cost": 0.0,
                 "bench": {"prices": px, "bb90_nav": nav, "bb90_values": {s: nav * w for s, w in BB90.items()},
                           "hold_0050_nav": nav},
                 "note": "建倉：以目標權重買入，成本不計（虛擬建倉）"}
        cal0 = _calendar_month_ends(d0, 14)
        gn = gate_decision(baa, cal0[-1], cal0)                 # 建倉日本身也是月底：判定下月狀態
        entry["gate_decision_for_next"] = gn
        if gn["gate_open"] != g0["gate_open"]:
            entry["pending_switch"] = {"decided_on": d0, "to_open": gn["gate_open"], "basis": gn}
        _append_log(entry)
        log.append(entry)
        processed += 1

    def _next_trading_day(d: str) -> str | None:
        nxt = [x for x in common if x > d]
        return nxt[0] if nxt else None

    # 依時間順序處理：月底（照舊狀態再平衡＋判定新狀態）與月底後下一個交易日的切換
    while True:
        last = log[-1]
        cand = []
        for me in month_ends:
            if me > last["date"] and not any(e["date"] == me and e["event"] in ("month_end", "inception") for e in log):
                cand.append((me, "month_end"))
        pend = last.get("pending_switch")
        if pend:
            sd = _next_trading_day(pend["decided_on"])
            if sd and sd > last["date"]:
                cand.append((sd, "gate_switch"))
        if not cand:
            break
        d, ev = sorted(cand)[0]
        vals = _revalue(last, d, series)
        bench = _bench_step(last["bench"], d, series) if ev == "month_end" else _bench_carry(last["bench"], d, series)
        if ev == "gate_switch":
            gate_open = last["pending_switch"]["to_open"]
            tgt = _targets(gate_open)
            nav, vpost, cost = _rebalance(vals, tgt)
            entry = {"date": d, "logged_at": datetime.now(TZ).isoformat(), "event": "gate_switch",
                     "gate_open": gate_open, "gate_basis": last["pending_switch"]["basis"],
                     "prices": {s: series[s][d] for s in SYMBOLS}, "targets": tgt, "nav_pre_rebalance": sum(vals.values()),
                     "rebalance_cost": cost, "nav": nav, "values_post": vpost, "bench": bench,
                     "note": "閘門狀態變更：月底判定、延後一個交易日切換"}
        else:
            if not baa_month_complete(baa, _calendar_month_ends(d, 1)[-1]):
                print(f"[紙.三] {d} 月底：當月 BAA10Y 尚未公布完整，本次不記帳（下次排程再試）")
                break
            gate_open = last["gate_open"]
            tgt = _targets(gate_open)                                   # 月底照「舊狀態」再平衡
            nav, vpost, cost = _rebalance(vals, tgt)
            cal = _calendar_month_ends(d, 14)
            g = gate_decision(baa, cal[-1], cal)
            entry = {"date": d, "logged_at": datetime.now(TZ).isoformat(), "event": "month_end",
                     "gate_open": gate_open, "gate_decision_for_next": g,
                     "prices": {s: series[s][d] for s in SYMBOLS}, "targets": tgt, "nav_pre_rebalance": sum(vals.values()),
                     "rebalance_cost": cost, "nav": nav, "values_post": vpost, "bench": bench}
            if g["gate_open"] != gate_open:
                entry["pending_switch"] = {"decided_on": d, "to_open": g["gate_open"], "basis": g}
        _append_log(entry)
        log.append(entry)
        processed += 1

    last = log[-1]
    b = last["bench"]
    _write_summary({
        "started": True, "as_of_date": last["date"], "nav": last["nav"],
        "initial_virtual_capital": INITIAL_VIRTUAL_CAPITAL,
        "total_return_pct": round((last["nav"] / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2),
        "gate_open": last["gate_open"], "pending_switch": last.get("pending_switch"), "gate_now": cur_gate,
        "weights_post": {s: round(v / last["nav"], 4) for s, v in last["values_post"].items()},
        "bench_bb90_return_pct": round((b["bb90_nav"] / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2),
        "bench_0050_return_pct": round((b["hold_0050_nav"] / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2),
        "history_rows": len(log), "history_months": len(log),
        "note": "紙.三＝S3-C6（#424／#426）台灣可執行版；槓桿腿用 00631L／00647L 真實價；閘門延後一個交易日切換；與紙.一／紙.一b 並行",
    })
    if processed:
        _heartbeat(f"處理 {processed} 筆，最新紀錄 {last['date']}（閘門{'開' if last['gate_open'] else '關'}）")
    print(f"[紙.三] 處理 {processed} 筆，最新 {last['date']}，淨值 {last['nav']:.2f}")
    return {"processed": processed, "started": True, "gate_now": cur_gate}


def _bench_carry(prev_b: dict, d: str, series: dict) -> dict:
    """非月底事件（閘門切換日）：對照組只推進市值、不再平衡。"""
    v = {s: prev_b["bb90_values"][s] * (series[s][d] / prev_b["prices"][s]) for s in BB90}
    return {"prices": {s: series[s][d] for s in SYMBOLS}, "bb90_nav": sum(v.values()), "bb90_values": v,
            "hold_0050_nav": prev_b["hold_0050_nav"] * (series["0050"][d] / prev_b["prices"]["0050"])}


def _enter_sandbox(sandbox: str, prices: str, today: str, baa_json: str | None) -> None:
    global PRICE_HISTORY_PATH, LOG_PATH, APP_SUMMARY_PATH, HEARTBEAT_PATH, _TODAY_OVERRIDE, _BAA_OVERRIDE
    sb = Path(sandbox).resolve()
    official = [(REPO_ROOT / "research" / "data").resolve(), (REPO_ROOT / "data").resolve(),
                HEARTBEAT_PATH.resolve().parent]
    if any(sb == o for o in official):
        raise SystemExit(f"沙盒目錄不得等於正式目錄：{sb}")
    sb.mkdir(parents=True, exist_ok=True)
    PRICE_HISTORY_PATH = Path(prices).resolve()
    LOG_PATH = sb / "paper_3_log.jsonl"
    APP_SUMMARY_PATH = sb / "paper_3.json"
    HEARTBEAT_PATH = sb / "PROGRESS_HEARTBEAT.jsonl"
    _TODAY_OVERRIDE = today
    if baa_json:
        _BAA_OVERRIDE = json.loads(Path(baa_json).read_text(encoding="utf-8"))


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
        print("::error::紙.三 執行失敗，已寫入 last_error 與心跳（不影響其他排程步驟）")
        print(traceback.format_exc())
        _abort("EXCEPTION", f"{type(exc).__name__}: {exc}")
        sys.exit(0)
