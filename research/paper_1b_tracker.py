"""紙.一b：核心配置 Bb-90 前進式紙上追蹤（總司令 2026-10-06【先.二十六】一核准）。

**這不是回測，也不是新試驗**——目的與紙.一相同：驗證「每月再平衡＋成本計算＋
資料管線＋排程」在真實日曆時間往前推進時不出錯。績效在 #418 已量過。
初始資金是虛擬值，**不下任何真實單**；真錢閘門規則完全不變（永遠使用者親自按單）。

**與紙.一的關係：並行，不取代。紙.一 70/30 的規則與紀錄完全不動。**

目標配置（#418 勝出組合 Bb-90 的台灣可執行版）：

| 腿 | 標的 | 權重 |
|---|---|---|
| 台股 | 0050 | 45% |
| 美股大盤 | 00646（元大 S&P500） | 45% |
| 美國公債 | 見 `SAFE_LEG`（先.二十六-二 查證後定案） | 10% |

**標的偏離揭露（必須與任何數字一起讀）**：回測 Bb-90 的股票腿是 VTI（美國全市場）、
安全腿是 IEF（7–10 年期）。00646 追蹤 S&P500（大型股，非全市場）；安全腿以存續期
最接近 IEF 者替代。**本追蹤記的是「台灣可執行版」的實際結果，不等於 #418 的回測數字。**

**啟動時間**：2026-11 第一個交易日（用 `data/price_history.json` 的實際成交序列判斷，
不用行事曆猜）。啟動日之前執行一律略過，不建立任何紀錄。

**月末偵測**：沿用紙.一的做法（連續兩筆資料月份不同 → 前一筆是月末），
故本月最後一個交易日要等下一個交易日的資料進來才確認。**不是前視偏誤**：
使用的仍是該月末日當天的收盤價，只是偵測時點延後一個交易日。

**冪等性與防重複**：沿用紙.一的 date+event 唯一鍵檢查（先.十四-三）。
發現重複即寫 `last_error` 與心跳 ERROR、**不計算、不刪除任何列**。

**輸出**：
- `research/data/paper_1b_log.jsonl`（append-only，逐月一筆）。
  **刻意不加 merge=union**——帳本需唯一性，沿用紙.一 2026-10-05 的決定。
- `data/paper_1b.json`（App 端摘要）。
"""
from __future__ import annotations

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
LOG_PATH = REPO_ROOT / "research" / "data" / "paper_1b_log.jsonl"
APP_SUMMARY_PATH = REPO_ROOT / "data" / "paper_1b.json"
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"

#: 安全腿標的。先.二十六-二 查證台灣上市 7–10 年期美債 ETF 後定案；
#: 在定案前為 None，腳本一律不動作並明寫原因（**不得自行改用長天期如 00679B**）。
SAFE_LEG: str | None = "00697B"   # 先.二十六-二 定案：與 IEF 追蹤同一指數（ICE US Treasury 7-10 Year Bond Index）
LEGS = {"0050": 0.45, "00646": 0.45}      # 安全腿於 _targets() 併入
INITIAL_VIRTUAL_CAPITAL = 1_000_000.0
START_ANCHOR = "2026-11-01"
TZ = timezone(timedelta(hours=8))
MAX_STALE_WEEKDAYS = 5

_CFG = BacktestConfig(start_date=START_ANCHOR, end_date=START_ANCHOR,
                      initial_capital=INITIAL_VIRTUAL_CAPITAL,
                      commission_discount=0.18, instrument_type="etf",
                      book_name="paper_1b_tracker")
BUY_RATE = buy_leg_rate(_CFG)
SELL_RATE = sell_leg_rate(_CFG)


def _targets() -> dict:
    t = dict(LEGS)
    if SAFE_LEG:
        t[SAFE_LEG] = 0.10
    return t


def _load_prices() -> dict:
    d = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    return d.get("prices") or {}


def _closes(prices: dict, sym: str) -> dict:
    """{date: adj_close}。adj_close 缺值時退回 close 並記錄（不靜默）。"""
    out = {}
    for r in prices.get(sym) or []:
        v = r.get("adj_close")
        if v is None:
            v = r.get("close")
        if v is not None:
            out[r["date"]] = float(v)
    return out


def _find_duplicate(log: list[dict]) -> str | None:
    """沿用紙.一 的 date+event 唯一鍵檢查（先.十四-三）。"""
    seen = set()
    for i, e in enumerate(log):
        k = (e.get("date"), e.get("event"))
        if k in seen:
            return f"第{i + 1}列 date={k[0]} event={k[1]} 與先前列重複"
        seen.add(k)
    return None


def _load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    out = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _heartbeat(note: str, status: str | None = None) -> None:
    try:
        rec = {"ts": datetime.now(TZ).isoformat(), "item": "紙.一b", "note": note}
        if status:
            rec["status"] = status
        with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.一b 寫心跳失敗：{type(e).__name__}: {e}")


def _abort(status: str, reason: str) -> None:
    """中止：不計算、不寫紀錄、不刪任何列；寫 last_error 與心跳 ERROR。"""
    print(f"::error::紙.一b 中止（{status}）：{reason}")
    try:
        summary = {"started": False, "note": f"紙.一b 中止：{status}"}
        if APP_SUMMARY_PATH.exists():
            summary = json.loads(APP_SUMMARY_PATH.read_text(encoding="utf-8"))
        summary["last_error"] = {"status": status, "reason": reason,
                                 "ts": datetime.now(TZ).isoformat()}
        APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        APP_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.一b 寫 last_error 失敗（不影響中止）：{type(e).__name__}: {e}")
    _heartbeat(f"中止（{status}）：{reason}", status="ERROR")


def _month_ends(dates: list[str], after: str | None) -> list[str]:
    """回傳已確認的月末日（連續兩筆月份不同 → 前一筆是月末），只取 after 之後者。"""
    out = []
    for a, b in zip(dates, dates[1:]):
        if a[:7] != b[:7] and (after is None or a > after):
            out.append(a)
    return out


def _write_app_summary(log: list[dict]) -> None:
    if not log:
        summary = {"started": False, "note": f"尚未到 {START_ANCHOR} 之後的第一個交易日，紙.一b 尚未啟動"}
    else:
        last = log[-1]
        summary = {"started": True, "as_of_date": last["date"], "nav": last["nav"],
                   "initial_virtual_capital": INITIAL_VIRTUAL_CAPITAL,
                   "total_return_pct": round((last["nav"] / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2),
                   "weights_post": last["weights_post"], "targets": _targets(),
                   "history_months": len(log),
                   "note": "紙.一b＝#418 勝出組合 Bb-90 的台灣可執行版；與紙.一 70/30 並行，不取代",
                   "deviation_note": ("回測股票腿為 VTI（全市場）、安全腿為 IEF（7–10 年期）；"
                                      "本追蹤以 00646（S&P500）與台灣上市美債 ETF 替代，標的不完全相同"),
                   "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。",
                   "generated_at": datetime.now(TZ).isoformat()}
    APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> dict:
    if SAFE_LEG is None:
        msg = ("安全腿標的尚未定案（先.二十六-二 查證中）。依裁示「不得自行改用長天期」，"
               "在定案前不建立任何紀錄。")
        print(f"[紙.一b] {msg}")
        _write_app_summary([])
        return {"processed": 0, "started": False, "reason": "safe_leg_undecided"}

    log = _load_log()
    dup = _find_duplicate(log)
    if dup:
        _abort("DUPLICATE_LOG_ENTRY", dup)
        return {"processed": 0, "started": bool(log), "aborted": True, "reason": dup}

    prices = _load_prices()
    tgt = _targets()
    series = {s: _closes(prices, s) for s in tgt}
    missing = [s for s, v in series.items() if not v]
    if missing:
        _abort("MISSING_PRICE_SERIES", f"price_history.json 缺少標的：{missing}")
        return {"processed": 0, "started": bool(log), "aborted": True, "reason": "missing_series"}

    common = sorted(set.intersection(*(set(v) for v in series.values())))
    if not common:
        _abort("NO_COMMON_DATES", "三檔標的沒有共同交易日")
        return {"processed": 0, "started": bool(log), "aborted": True, "reason": "no_common_dates"}

    # 新鮮度：最新共同交易日不得落後今天超過 MAX_STALE_WEEKDAYS 個平日
    last_d = datetime.strptime(common[-1], "%Y-%m-%d").date()
    today = datetime.now(TZ).date()
    wd = sum(1 for i in range(1, (today - last_d).days + 1)
             if (last_d + timedelta(days=i)).weekday() < 5)
    if wd > MAX_STALE_WEEKDAYS:
        _abort("ABORTED_STALE_PRICE",
               f"最新共同交易日 {common[-1]} 落後今天 {wd} 個平日（>{MAX_STALE_WEEKDAYS}），價格過期")
        return {"processed": 0, "started": bool(log), "aborted": True, "reason": "stale"}

    if not log:
        first = next((d for d in common if d >= START_ANCHOR), None)
        if first is None:
            print(f"[紙.一b] 尚未到 {START_ANCHOR} 之後的交易日（最新 {common[-1]}），略過")
            _write_app_summary(log)
            return {"processed": 0, "started": False}
        px = {s: series[s][first] for s in tgt}
        entry = {"date": first, "logged_at": datetime.now(TZ).isoformat(), "event": "inception",
                 "prices": px, "targets": tgt,
                 "values_post": {s: INITIAL_VIRTUAL_CAPITAL * w for s, w in tgt.items()},
                 "nav": INITIAL_VIRTUAL_CAPITAL, "weights_post": dict(tgt),
                 "rebalance_cost": 0.0,
                 "note": "建倉：以目標權重買入，成本於此筆不計（虛擬建倉）"}
        _append_log(entry)
        log.append(entry)
        print(f"[紙.一b] 帳戶啟動：{first}，虛擬淨值={entry['nav']:.2f}")

    last_logged = log[-1]["date"]
    pend = _month_ends(common, last_logged)
    if not pend:
        print(f"[紙.一b] 無新的已確認月末（最後紀錄 {last_logged}），本次不動作")
        _write_app_summary(log)
        return {"processed": 0, "started": True}

    for d in pend:
        prev = log[-1]
        vals = {}
        for s in tgt:
            p0 = prev["prices"][s]
            p1 = series[s][d]
            vals[s] = prev["values_post"][s] * (p1 / p0)
        nav_pre = sum(vals.values())
        tgt_vals = {s: nav_pre * w for s, w in tgt.items()}
        cost = 0.0
        for s in tgt:
            diff = tgt_vals[s] - vals[s]
            cost += abs(diff) * (BUY_RATE if diff > 0 else SELL_RATE)
        nav = nav_pre - cost
        entry = {"date": d, "logged_at": datetime.now(TZ).isoformat(), "event": "month_end",
                 "prices": {s: series[s][d] for s in tgt}, "targets": tgt,
                 "nav_pre_rebalance": nav_pre, "rebalance_cost": cost, "nav": nav,
                 "values_post": {s: nav * w for s, w in tgt.items()},
                 "weights_post": dict(tgt)}
        _append_log(entry)
        log.append(entry)
        print(f"[紙.一b] 月末再平衡：{d}，淨值={nav:.2f}（再平衡成本 {cost:.2f}）")

    _write_app_summary(log)
    _heartbeat(f"處理 {len(pend)} 個月末，最新紀錄 {log[-1]['date']}")
    return {"processed": len(pend), "started": True}


if __name__ == "__main__":
    try:
        run()
    except Exception as _exc:  # noqa: BLE001
        import traceback
        _tb = traceback.format_exc()
        print("::error::紙.一b 執行失敗，已寫入 last_error 與心跳（不影響其他排程步驟）")
        print(_tb)
        _abort("EXCEPTION", f"{type(_exc).__name__}: {_exc}")
        sys.exit(0)
