"""紙.一：0050/定存70/30前進式紙上追蹤（2026-09-27總司令裁示【新.二結案＋
紙.一＋查.二放行】第二節）。

**這不是回測，也不是新試驗**——目的是驗證「每月再平衡＋成本計算＋資料
管線＋排程」這一整條流程在真實日曆時間往前推進時不出錯，不是要證明
70/30這個配置的績效（績效數字早就在`SURVIVAL_CONSTRAINT.md`量過）。
初始資金是虛擬值，不下任何真實單，真錢閘門規則完全不變（永遠使用者
親自按單）。

**啟動時間**：2026-10第一個交易日（本檔用`data/price_history.json`的
0050實際成交序列判斷，不用行事曆猜，避免把國定假日/颱風假誤判成交易日）。
在啟動日之前執行本腳本一律略過，不建立任何紀錄。

**月末偵測方式（誠實揭露這裡的簡化，非回測，可接受）**：`data/price_
history.json`只保留最近一段滾動窗口的0050日線（見該檔`meta`欄位），
本腳本用「連續兩筆資料的月份不同」判斷前一筆是月末——這代表「本月最後
一個交易日」只能在**下一個交易日的資料進來之後**才能確認（不是當天就能
確定当天是不是月末，需要多等一個交易日）。這不是前視偏誤：確認之後
使用的還是那個歷史月末日「當天」的實際收盤價,不是用「確認當下」的價格
，只是**偵測時間點**延後一個交易日，對紙上追蹤的目的（驗證流程正確性）
完全不影響。

**再平衡與成本**：比照`survival_constraint_allocation_test.py`同一套
`BacktestConfig`/`buy_leg_rate`/`sell_leg_rate`（ETF證交稅0.1%、手續費
1.8折），股票腿標的0050、債券腿用`cbc_rf_rate_client`定存利率代理，
月複利`(1+rf_annual_pct/100)**(1/12)`（rf_annual_pct本身已是年化定存
利率報價，跟`survival_constraint_allocation_test.py`的日複利
`(1+rf_pct/100)**(1/252)`是同一個年化利率、只是複利頻率配合本腳本
「只逐月推進」的粒度）。

**冪等性**：可重複執行（例如同一天排程跑兩次、或補跑），只會處理「還沒
被記錄過的月末」，已記錄的月份不會重複寫入或重算（見`_load_state()`／
`_pending_month_ends()`）。

**輸出**：
- `research/data/paper_7030_log.jsonl`（append-only，逐月一筆，含日期/
  權重/淨值/再平衡交易/成本，供稽核用完整紀錄）。
- `data/paper_7030.json`（App端讀取用摘要：目前淨值/權重/下次再平衡
  日期/最近幾筆歷史，見`_write_app_summary()`）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate  # noqa: E402
from cbc_rf_rate_client import load_risk_free_rate_series, rf_rate_for_date  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
LOG_PATH = REPO_ROOT / "research" / "data" / "paper_7030_log.jsonl"
APP_SUMMARY_PATH = REPO_ROOT / "data" / "paper_7030.json"
HEARTBEAT_PATH = REPO_ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"

STOCK_ID = "0050"
STOCK_WEIGHT = 0.70
BOND_WEIGHT = 0.30
INITIAL_VIRTUAL_CAPITAL = 1_000_000.0
START_ANCHOR = "2026-10-01"  # 「2026-10第一個交易日」的下限，實際起算日由
# 0050實際成交序列決定（見_first_trading_day_on_or_after()）
REBALANCE_TOLERANCE_FRACTION = 0.0005  # 沿用survival_constraint腳本同一套容忍度
TZ = timezone(timedelta(hours=8))

_CFG = BacktestConfig(start_date=START_ANCHOR, end_date=START_ANCHOR, initial_capital=INITIAL_VIRTUAL_CAPITAL,
                      commission_discount=0.18, instrument_type="etf", book_name="paper_7030_tracker")
BUY_RATE = buy_leg_rate(_CFG)
SELL_RATE = sell_leg_rate(_CFG)


def _load_0050_price_series() -> list[dict]:
    """從data/price_history.json讀0050日線（滾動窗口，非全歷史），按日期
    升冪排序。這是既有排程(update_price_history.py)已經在維護的資料，本
    腳本零額外網路請求。"""
    if not PRICE_HISTORY_PATH.exists():
        return []
    with open(PRICE_HISTORY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("prices", {}).get(STOCK_ID, [])
    return sorted(rows, key=lambda r: r["date"])


MAX_STALE_WEEKDAYS = 5  # 0050最新日期落後今天(台北)超過這麼多個平日就視為停更（長假最多容忍5個平日）


def _check_price_freshness(prices: list[dict], today_iso: str | None = None) -> tuple[bool, str]:
    """紙.一的價格新鮮度閘門（2026-09-30修.八）：0050價格過期時回傳(False,原因)，
    呼叫端必須中止並寫錯誤紀錄，不得用舊價格硬算。三道獨立檢查，任一不過即過期：
    (1) 0050自己沒有任何資料；(2) price_history全市場最新日期比0050新（0050落後別檔，
    正是2026-09上市股價T+1停更的形狀）；(3) 0050最新日期落後今天超過MAX_STALE_WEEKDAYS個平日。
    本函式自己的例外由呼叫端接住降級（十二節），不會中斷其他排程。"""
    if not prices:
        return False, "0050在price_history.json沒有任何資料"
    last = prices[-1]["date"]
    try:
        with open(PRICE_HISTORY_PATH, encoding="utf-8") as f:
            doc = json.load(f)
        others = [rows[-1]["date"] for rows in doc.get("prices", {}).values() if rows]
        market_max = max(others) if others else last
    except Exception as e:  # noqa: BLE001 - 守門員自身失敗只降級，見十二節
        print(f"::warning::紙.一新鮮度閘門讀全市場最新日期失敗（略過此檢查）：{type(e).__name__}: {e}")
        market_max = last
    if market_max > last:
        return False, f"0050最新日期({last})落後全市場最新日期({market_max})，上市股價疑似停更"
    today = today_iso or datetime.now(TZ).strftime("%Y-%m-%d")
    d0 = datetime.strptime(last, "%Y-%m-%d").date()
    d1 = datetime.strptime(today, "%Y-%m-%d").date()
    weekdays = sum(1 for i in range(1, (d1 - d0).days + 1) if (d0 + timedelta(days=i)).weekday() < 5)
    if weekdays > MAX_STALE_WEEKDAYS:
        return False, f"0050最新日期({last})落後今天({today}) {weekdays}個平日（>{MAX_STALE_WEEKDAYS}），價格資料過期"
    return True, ""


def _abort_stale(reason: str, log: list[dict]) -> None:
    """過期中止：不寫紀錄檔、不算任何淨值；把原因寫進心跳(status=ERROR)與App摘要的last_error。"""
    print(f"::warning::紙.一中止：{reason}（不使用舊價格計算）")
    _write_app_summary(log)
    try:
        with open(APP_SUMMARY_PATH, encoding="utf-8") as f:
            summary = json.load(f)
        summary["last_error"] = {"status": "ABORTED_STALE_PRICE", "reason": reason,
                                 "ts": datetime.now(TZ).isoformat()}
        with open(APP_SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::紙.一寫入last_error失敗（不影響中止）：{type(e).__name__}: {e}")
    with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(TZ).isoformat(), "item": "紙.一", "status": "ERROR",
                            "note": f"中止（價格過期）：{reason}"}, ensure_ascii=False) + "\n")


def _first_trading_day_on_or_after(prices: list[dict], anchor: str) -> dict | None:
    for row in prices:
        if row["date"] >= anchor:
            return row
    return None


def _month_end_boundaries(prices: list[dict], after_date: str) -> list[dict]:
    """回傳`after_date`之後、且已能確認是月末的交易日列（見檔頭「月末偵測
    方式」）。用「這筆的月份 != 下一筆的月份」判斷，所以序列最後一筆永遠
    不會被判定為月末（還沒看到下個月第一筆資料，無法確認）。"""
    rows = [r for r in prices if r["date"] > after_date]
    out = []
    for i in range(len(rows) - 1):
        this_month = rows[i]["date"][:7]
        next_month = rows[i + 1]["date"][:7]
        if this_month != next_month:
            out.append(rows[i])
    return out


def _load_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    out = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _bond_monthly_growth(rf_monthly, date_str: str) -> float:
    rf_annual_pct = rf_rate_for_date(datetime.strptime(date_str, "%Y-%m-%d"), rf_monthly)
    return (1.0 + rf_annual_pct / 100.0) ** (1.0 / 12.0)


def _process_inception(price_row: dict, rf_monthly) -> dict:
    stock_value = INITIAL_VIRTUAL_CAPITAL * STOCK_WEIGHT
    bond_value = INITIAL_VIRTUAL_CAPITAL * BOND_WEIGHT
    entry = {
        "date": price_row["date"], "logged_at": datetime.now(TZ).isoformat(), "event": "inception",
        "price_0050": price_row["close"],
        "stock_value_pre": None, "bond_value_pre": None,
        "stock_value_post": round(stock_value, 2), "bond_value_post": round(bond_value, 2),
        "nav": round(stock_value + bond_value, 2),
        "stock_weight_post": STOCK_WEIGHT, "bond_weight_post": BOND_WEIGHT,
        "rebalance_trade": {"direction": "none", "notional": 0.0, "cost": 0.0},
    }
    return entry


def _process_month_end(prev_entry: dict, price_row: dict, rf_monthly) -> dict:
    prev_price = prev_entry["price_0050"]
    stock_value = prev_entry["stock_value_post"] * (price_row["close"] / prev_price)
    bond_value = prev_entry["bond_value_post"] * _bond_monthly_growth(rf_monthly, price_row["date"])

    total = stock_value + bond_value
    target_stock = total * STOCK_WEIGHT
    delta = target_stock - stock_value
    trade = {"direction": "none", "notional": 0.0, "cost": 0.0}
    if abs(delta) > total * REBALANCE_TOLERANCE_FRACTION:
        if delta > 0:
            cost = delta * BUY_RATE
            stock_value += delta
            bond_value -= (delta + cost)
            trade = {"direction": "buy", "notional": round(delta, 2), "cost": round(cost, 2)}
        else:
            sell_notional = -delta
            cost = sell_notional * SELL_RATE
            stock_value -= sell_notional
            bond_value += (sell_notional - cost)
            trade = {"direction": "sell", "notional": round(sell_notional, 2), "cost": round(cost, 2)}

    return {
        "date": price_row["date"], "logged_at": datetime.now(TZ).isoformat(), "event": "monthly_rebalance",
        "price_0050": price_row["close"],
        "stock_value_pre": round(stock_value - (trade["notional"] if trade["direction"] == "buy" else -trade["notional"] if trade["direction"] == "sell" else 0), 2),
        "bond_value_pre": None,
        "stock_value_post": round(stock_value, 2), "bond_value_post": round(bond_value, 2),
        "nav": round(stock_value + bond_value, 2),
        "stock_weight_post": round(stock_value / (stock_value + bond_value), 4),
        "bond_weight_post": round(bond_value / (stock_value + bond_value), 4),
        "rebalance_trade": trade,
    }


def _write_app_summary(log: list[dict]) -> None:
    if not log:
        summary = {"started": False, "note": "尚未到2026-10第一個交易日，紙上追蹤尚未啟動"}
    else:
        last = log[-1]
        summary = {
            "started": True,
            "as_of_date": last["date"],
            "nav": last["nav"],
            "initial_virtual_capital": INITIAL_VIRTUAL_CAPITAL,
            "total_return_pct": round((last["nav"] / INITIAL_VIRTUAL_CAPITAL - 1) * 100, 2),
            "stock_weight": last["stock_weight_post"],
            "bond_weight": last["bond_weight_post"],
            "last_rebalance_trade": last["rebalance_trade"],
            "next_rebalance_note": "下個月最後一個交易日（實際日期依當月交易日曆而定，非固定日）",
            "history_months": len(log),
            "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。",
            "generated_at": datetime.now(TZ).isoformat(),
        }
    APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def run() -> dict:
    prices = _load_0050_price_series()
    log = _load_log()

    fresh, reason = _check_price_freshness(prices)
    if not fresh:
        _abort_stale(reason, log)
        return {"processed": 0, "started": bool(log), "aborted": True, "reason": reason}

    if not log:
        first_row = _first_trading_day_on_or_after(prices, START_ANCHOR)
        if first_row is None:
            print(f"[紙.一] 尚未到{START_ANCHOR}或之後的交易日資料，略過（目前0050最新快取日期："
                  f"{prices[-1]['date'] if prices else '無資料'}）")
            _write_app_summary(log)
            return {"processed": 0, "started": False}
        rf_monthly = load_risk_free_rate_series()
        entry = _process_inception(first_row, rf_monthly)
        _append_log(entry)
        log.append(entry)
        print(f"[紙.一] 帳戶啟動：{entry['date']}，虛擬淨值={entry['nav']:.2f}")

    last_logged_date = log[-1]["date"]
    boundaries = _month_end_boundaries(prices, last_logged_date)
    if not boundaries:
        print(f"[紙.一] 無新的已確認月末（最後已記錄日期：{last_logged_date}），本次不動作")
        _write_app_summary(log)
        return {"processed": 0, "started": True}

    rf_monthly = load_risk_free_rate_series()
    for row in boundaries:
        entry = _process_month_end(log[-1], row, rf_monthly)
        _append_log(entry)
        log.append(entry)
        print(f"[紙.一] 月末再平衡：{entry['date']}，淨值={entry['nav']:.2f}，"
              f"權重0050={entry['stock_weight_post']:.2%}，交易={entry['rebalance_trade']}")

    _write_app_summary(log)
    with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(TZ).isoformat(), "item": "紙.一",
            "note": f"處理{len(boundaries)}個月末，最新紀錄日期{log[-1]['date']}",
        }, ensure_ascii=False) + "\n")
    return {"processed": len(boundaries), "started": True}


def _record_failure(exc: BaseException, tb_text: str) -> None:
    """先.十-一（2026-10-02總司令裁示）：任何例外都要落地到paper_7030.json的last_error與
    心跳status=ERROR，不得只印warning。本函式自己的失敗只降級成警告（十二節）。"""
    reason = f"{type(exc).__name__}: {exc}"
    ts = datetime.now(TZ).isoformat()
    try:
        summary = {"started": False, "note": "紙.一執行失敗，尚未啟動或未更新"}
        if APP_SUMMARY_PATH.exists():
            with open(APP_SUMMARY_PATH, encoding="utf-8") as f:
                summary = json.load(f)
        summary["last_error"] = {"status": "EXCEPTION", "reason": reason,
                                 "traceback_tail": tb_text.strip().splitlines()[-6:], "ts": ts}
        APP_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(APP_SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception as e2:  # noqa: BLE001
        print(f"::warning::紙.一寫入last_error失敗：{type(e2).__name__}: {e2}")
    try:
        with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "item": "紙.一", "status": "ERROR",
                                "note": f"例外中止：{reason}"}, ensure_ascii=False) + "\n")
    except Exception as e3:  # noqa: BLE001
        print(f"::warning::紙.一寫入心跳失敗：{type(e3).__name__}: {e3}")


if __name__ == "__main__":
    try:
        run()
    except Exception as _exc:
        # 十二節：失敗不得讓market.yml其他步驟中斷（呼叫端另有continue-on-error），
        # 但先.十-一起必須把錯誤寫進paper_7030.json last_error＋心跳status=ERROR。
        import traceback
        _tb = traceback.format_exc()
        print("::error::紙.一 paper_7030_tracker.py 執行失敗，已寫入last_error與心跳（不影響其他排程步驟）")
        print(_tb)
        _record_failure(_exc, _tb)
        sys.exit(0)
