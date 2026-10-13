# -*- coding: utf-8 -*-
"""前瞻選股台帳的回填腳本（2026-08-28骨架新增，2026-09-01完整實作）。

跟`build_picks_ledger.py`（負責「快照」）分工明確：這支腳本只負責【回填】
——對`data/picks_ledger.json`裡每個快照的每一檔股票，檢查是否到了
T+5/T+20/T+60/T+120交易日，到了就查當時的收盤價+大盤指數，算出報酬率跟
超額報酬填進`returns.t5`(或t20/t60/t120)，**只寫還沒填過的欄位，已經填過
的欄位永遠不再更動**（鐵律：「只能事前快照，嚴禁事後補建」的延伸——回填
本身是被容許的『事後』動作，但同一個(snapshot, T+N)只能被回填一次，寫過
就不能因為之後想「調整」而改動，那樣會失去前瞻驗證的公信力）。

**填入後的`returns.tN`欄位形狀**（原本是`null`，回填後變成物件，不是單一
數字——因為同時要放報酬率跟超額報酬跟出場日期，前端才能誠實標示「這個
數字是哪一天算出來的」）：
    {"return_pct": 12.34, "excess_vs_taiex_pct": 5.67, "exit_date": "2026-09-05",
     "filled_at": "2026-09-05T13:35:00+08:00"}

**三個關鍵函式的設計取捨（2026-09-01完整實作時定案，之前只有骨架）**：

1. `_trading_days_after()`：交易日曆用`data/price_history.json`裡
   **2330（台積電）**的實際`date`序列近似（全市場流動性最高、幾乎不會
   停牌，比挑加權指數本身更可靠——見下一點）。查過`price_history.json`
   的`prices["TAIEX"]`鍵，發現那份快取**是2024-08~12月的舊資料，長期沒
   被日常更新任務碰過**（跟股票代碼各自獨立更新，TAIEX那把鑰匙從一開始
   加入後就沒人維護），拿來當日曆或查歷史收盤都是錯的，改用yfinance
   `^TWII`即時抓（見第3點），不依賴這個過期快取。

2. `_lookup_price_on()`：查`price_history.json`該股票在指定日期的
   `close`（**刻意不用`adj_close`還原股價**——因為快照當時記錄的
   `close_price`本身就是`quotes_all_tw.json`的原始收盤價，不是還原股價，
   兩端要用同一種價格基準做除法，混用會在除息日附近製造虛假的報酬率
   跳動，比不還原股價本身的失真更糟）。精確比對找不到就往前找最近一筆，
   沿用`build_picks_ledger.py`既有的`price_stale`守門邏輯：找到的日期
   跟目標日期差超過10天就視為過期，回傳null不塞錯價。

3. `_fetch_taiex_history()`：改用yfinance `^TWII`（跟
   `fetch_market_tw.py::fetch_taiex_sparkline()`同一個資料源，不是新
   依賴，`market.yml`已經裝了`yfinance`），一次抓「最早快照日期至今」
   整段區間的歷史收盤，同時拿來當大盤超額報酬的分母，也拿來補強交易日曆
   （大盤指數本身沒有個股停牌問題，理論上比任何單一個股都更貼近真正的
   交易日集合，但因為抓取成本較低就沒有另外拿它取代2330當主要日曆來源，
   維持用個股序列當日曆、大盤序列只用於超額報酬計算這個分工）。抓取失敗
   （網路/yfinance問題）就整個跳過本輪所有超額報酬計算，不猜、不用舊值
   頂替。

4. **掛進`market.yml`**：在`build_picks_ledger.py`快照之後、
   `update_strategy_performance.py`之前執行（不影響互不相關的策略前向
   模擬那條線），`continue-on-error: true`跟其他步驟一致（單一資料源
   失敗不該擋住整個workflow）。
"""
from __future__ import annotations

import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[2] / "scripts"))
import price_history_store as PHS  # noqa: E402
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "picks_ledger.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
TW_TZ = timezone(timedelta(hours=8))

# T+N交易日視窗名稱 → 交易日數（不是日曆天數）
RETURN_WINDOWS = {"t5": 5, "t20": 20, "t60": 60, "t120": 120}
# 2026-10-11 總司令【先.七十七】第 4 點：進場點更正。
#   舊規則：進場價＝快照當下記錄的 close_price（price_date 常早於 taken_at——用的是「快照前就已知」的價格，
#   但出場日卻從 snapshot_date 往後數，實際持有 5～8 個交易日；更嚴重的是 price_date 早於 taken_at 的價格
#   在快照當下並不是「之後才買得到」的價格，屬未來函數）。
#   新規則：進場＝taken_at 之後第一個收盤（交易日 13:30 收盤時間晚於 taken_at 的第一天）的收盤價，
#   出場＝其後第 N 個交易日收盤，持有恰為 N 個交易日；大盤超額報酬用同一個進出場日。
#   首次以新規則執行時（meta.returns_anchor_rule 不是本規則）清空並重算所有已回填欄位（本裁示即授權，一次性）；
#   之後恢復「已回填欄位永遠不再更動」的鐵律。
ANCHOR_RULE = "taken_at_next_close_v2"
TW_CLOSE_HHMM = (13, 30)
STALE_DAYS_THRESHOLD = 10  # 跟build_picks_ledger.py同一套「價格過期」判斷門檻
CALENDAR_PROXY_CODE = "2330"  # 台積電：全市場流動性最高，幾乎不會停牌，拿來近似交易日曆


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"讀 {path} 失敗（不中止，這輪就不回填任何東西）：{e}")
        return {}


def _fetch_taiex_history(start_date: str) -> dict[str, float]:
    """用yfinance `^TWII`抓從start_date到今天的歷史收盤序列，回傳
    {日期字串: 收盤}。抓失敗回傳空dict——呼叫端據此跳過所有超額報酬計算，
    不用猜測值頂替（見模組docstring第3點）。"""
    try:
        h = yf.Ticker("^TWII").history(start=start_date)
    except Exception as e:
        print(f"  [taiex history] yfinance抓取失敗，本輪跳過所有大盤超額報酬計算：{e}")
        return {}
    if h is None or h.empty:
        print("  [taiex history] yfinance回傳空資料，本輪跳過所有大盤超額報酬計算")
        return {}
    return {ts.strftime("%Y-%m-%d"): float(row["Close"]) for ts, row in h.iterrows()}


_WARNED_MISSING_ANCHORS: set[str] = set()  # 同一個anchor_date只警告一次，避免每檔股票每個窗口都重印


def _trading_days_after(anchor_date: str, n: int, trading_calendar: list[str]) -> str | None:
    """從交易日曆裡找anchor_date之後第n個交易日。anchor_date當天不算，從
    下一個交易日開始數第1天。anchor_date不在曆表裡（例如快照當天本身就是
    非交易日的髒資料——已知案例：picks_ledger.json裡有一筆snapshot_date
    是2026-08-29，那天是星期六，是build_picks_ledger.py快照端的既有問題，
    不在這支腳本的職責範圍——或者anchor是「今天」，日曆資料還沒涵蓋到這天）
    或還沒到那個交易日，都回傳None，呼叫端跳過、留到之後這個範圍的資料
    存在了再回填，不能用日曆天數估算頂替。"""
    try:
        idx = trading_calendar.index(anchor_date)
    except ValueError:
        if anchor_date not in _WARNED_MISSING_ANCHORS:
            _WARNED_MISSING_ANCHORS.add(anchor_date)
            print(f"    [trading_calendar] {anchor_date} 不在交易日曆裡（可能是快照端的髒資料，"
                  f"或日曆資料還沒涵蓋到這天），這個anchor下所有股票/窗口都跳過")
        return None
    target_idx = idx + n
    if target_idx >= len(trading_calendar):
        return None  # 還沒到那個交易日，之後資料累積夠了再回填（正常情況，不印警告）
    return trading_calendar[target_idx]


def _entry_day_after(taken_at: str | None, trading_calendar: list[str]) -> str | None:
    """先.七十七-4：taken_at（含時區的 ISO 時間）之後第一個收盤的交易日（台北 13:30 收盤時間 > taken_at）。"""
    if not taken_at:
        return None
    try:
        t = datetime.fromisoformat(taken_at)
        if t.tzinfo is None:
            t = t.replace(tzinfo=TW_TZ)
    except ValueError:
        return None
    for d in trading_calendar:
        close_at = datetime.strptime(d, "%Y-%m-%d").replace(hour=TW_CLOSE_HHMM[0], minute=TW_CLOSE_HHMM[1], tzinfo=TW_TZ)
        if close_at > t:
            return d
    return None


def _lookup_price_on(code: str, date: str, price_history: dict[str, list[dict]]) -> tuple[float | None, str | None, bool]:
    """回傳(close, 實際取用的日期, 是否過期)。優先找精確符合date的收盤；
    找不到（該股票當天停牌/下市）就找不晚於date的最近一筆，若跟目標日期
    相差超過STALE_DAYS_THRESHOLD天，視為過期，回傳(None, None, True)——
    沿用`build_picks_ledger.py`同一套price_stale邏輯，避免用太舊的價格
    污染報酬率計算。刻意用`close`（原始收盤價）不用`adj_close`（還原
    股價），理由見模組docstring第2點。"""
    rows = price_history.get(code)
    if not rows:
        return None, None, True
    exact = next((r for r in rows if r["date"] == date), None)
    if exact is not None and exact.get("close") is not None:
        return exact["close"], date, False
    candidates = [r for r in rows if r["date"] <= date and r.get("close") is not None]
    if not candidates:
        return None, None, True
    best = max(candidates, key=lambda r: r["date"])
    try:
        age_days = (datetime.strptime(date, "%Y-%m-%d") - datetime.strptime(best["date"], "%Y-%m-%d")).days
    except ValueError:
        return None, None, True
    if age_days > STALE_DAYS_THRESHOLD:
        return None, None, True
    return best["close"], best["date"], False


def _lookup_taiex_on(date: str, taiex_history: dict[str, float]) -> float | None:
    """精確比對，找不到就不猜——yfinance的`^TWII`歷史序列理論上涵蓋每個
    交易日，找不到代表資料缺口，誠實回傳None，呼叫端只會跳過這筆超額
    報酬（不影響同一筆的return_pct本身，那個只靠個股價格就能算）。"""
    return taiex_history.get(date)


def _compute_return_pct(entry: float, exit_price: float) -> float:
    return (exit_price - entry) / entry * 100.0


def main():
    ledger = _load_json(LEDGER_PATH)
    if not ledger.get("snapshots"):
        print(f"{LEDGER_PATH} 沒有快照可以回填，結束")
        return

    price_history = (PHS.load(PRICE_HISTORY_PATH) if PHS.exists(PRICE_HISTORY_PATH) else {}).get("prices", {})
    calendar_series = price_history.get(CALENDAR_PROXY_CODE)
    if not calendar_series:
        print(f"  price_history.json裡沒有{CALENDAR_PROXY_CODE}，退而求其次挑資料筆數最多的任一檔當日曆代表")
        calendar_series = max(price_history.values(), key=len, default=[])
    trading_calendar = [r["date"] for r in calendar_series]
    if not trading_calendar:
        print("交易日曆是空的（price_history.json可能還沒有任何資料），本輪不回填，結束")
        return

    earliest_snapshot_date = min(s["snapshot_date"] for s in ledger["snapshots"])
    taiex_history = _fetch_taiex_history(earliest_snapshot_date)

    meta = ledger.setdefault("meta", {})
    recompute_all = meta.get("returns_anchor_rule") != ANCHOR_RULE
    wiped = 0
    if recompute_all:
        # 先.七十七-4 一次性重算：清空所有已回填欄位，下面依新規則重填
        for snap in ledger["snapshots"]:
            for pick in snap["picks"]:
                for k in RETURN_WINDOWS:
                    if (pick.get("returns") or {}).get(k) is not None:
                        wiped += 1
                    pick.setdefault("returns", {})[k] = None
                pick.pop("entry_date", None)
                pick.pop("entry_price", None)
        print(f"先.七十七-4：進場點規則改為 {ANCHOR_RULE}，清空 {wiped} 個已回填欄位後依新規則重算")

    filled = 0
    skipped_stale_or_missing = 0
    skipped_no_entry = 0
    for snap in ledger["snapshots"]:
        entry_day = _entry_day_after(snap.get("taken_at"), trading_calendar)
        if entry_day is None:
            continue  # 快照之後還沒有收盤（或 taken_at 缺漏）：還不能進場，之後再回填
        taiex_entry = _lookup_taiex_on(entry_day, taiex_history)
        for pick in snap["picks"]:
            # 進場價＝taken_at 之後第一個收盤；快照記錄的 close_price／price_date 早於 taken_at，一律不用（未來函數）
            entry_price, entry_actual, entry_stale = _lookup_price_on(pick["code"], entry_day, price_history)
            if entry_stale or entry_price is None or entry_actual != entry_day:
                skipped_no_entry += 1  # 進場日當天沒有收盤（停牌／資料缺）：不拿別天的價格頂替
                continue
            pick["entry_date"], pick["entry_price"] = entry_day, entry_price
            for window_key, n in RETURN_WINDOWS.items():
                if pick["returns"].get(window_key) is not None:
                    continue  # 已經回填過，鐵律：永遠不再更動
                target_date = _trading_days_after(entry_day, n, trading_calendar)
                if target_date is None:
                    continue  # 還沒到那個交易日，之後再回填
                exit_price, actual_date, stale = _lookup_price_on(pick["code"], target_date, price_history)
                # 先.七十七-4：持有必須恰為 N 個交易日——出場日當天沒有收盤（停牌／資料缺）就留 null，不拿前一天頂替
                if stale or exit_price is None or actual_date != target_date:
                    skipped_stale_or_missing += 1
                    continue  # 資料還沒到位/過期，寧可留null也不塞錯價
                return_pct = _compute_return_pct(entry_price, exit_price)
                excess_pct = None
                taiex_exit = _lookup_taiex_on(target_date, taiex_history)
                if taiex_entry and taiex_exit is not None:
                    taiex_return_pct = _compute_return_pct(taiex_entry, taiex_exit)
                    excess_pct = return_pct - taiex_return_pct
                pick["returns"][window_key] = {
                    "return_pct": round(return_pct, 4),
                    "excess_vs_taiex_pct": round(excess_pct, 4) if excess_pct is not None else None,
                    "entry_date": entry_day,
                    "exit_date": actual_date,
                    "holding_trading_days": n,
                    "anchor_rule": ANCHOR_RULE,
                    "filled_at": datetime.now(TW_TZ).isoformat(),
                }
                filled += 1

    # 先.八十-9（2026-10-12）：資料不完整的批次要標註。每個快照算一次 data_status：
    #   missing_entry＝進場日已到、卻沒有進場日收盤的檔數；missing_exit＝出場日已到、卻沒有出場日收盤的(檔,期別)數；
    #   market_gap_days＝進場／出場日當天全市場檔數 < 中位數 90% 的日子（price_history 全市場缺日）。
    # 只標註、不改任何已回填欄位；資料補齊後下一輪自動回填 null 欄位並改標 complete=true。
    day_count: dict[str, int] = {}
    for rows in price_history.values():
        for r in rows:
            if r.get("date", "") >= earliest_snapshot_date:
                day_count[r["date"]] = day_count.get(r["date"], 0) + 1
    med = sorted(day_count.values())[len(day_count) // 2] if day_count else 0
    gap_days = {d for d, n in day_count.items() if n < med * 0.9}
    last_day = trading_calendar[-1] if trading_calendar else None
    n_incomplete = 0
    for snap in ledger["snapshots"]:
        entry_day = _entry_day_after(snap.get("taken_at"), trading_calendar)
        if entry_day is None:
            snap.pop("data_status", None)
            continue
        miss_entry = sum(1 for pk in snap["picks"] if pk.get("entry_price") is None)
        miss_exit, used_days = 0, {entry_day}
        for pk in snap["picks"]:
            for window_key, n in RETURN_WINDOWS.items():
                t = _trading_days_after(entry_day, n, trading_calendar)
                if t is None or (last_day and t > last_day):
                    continue
                used_days.add(t)
                if pk.get("entry_price") is not None and (pk.get("returns") or {}).get(window_key) is None:
                    miss_exit += 1
        gd = sorted(used_days & gap_days)
        complete = miss_entry == 0 and miss_exit == 0 and not gd
        snap["data_status"] = {"complete": complete, "missing_entry": miss_entry, "missing_exit": miss_exit,
                               "market_gap_days": gd, "checked_at": datetime.now(TW_TZ).isoformat(timespec="seconds")}
        n_incomplete += 0 if complete else 1
    meta["incomplete_batches"] = n_incomplete
    meta["incomplete_rule"] = "data_status.complete=false：進場或已到期出場缺收盤（停牌／資料缺），或該日全市場檔數 < 中位數 90%"

    if recompute_all:
        meta["returns_anchor_rule"] = ANCHOR_RULE
        meta["returns_anchor_note"] = ("2026-10-11 先.七十七-4 更正進場點：進場＝快照 taken_at 之後第一個交易日收盤，"
                                       "出場＝其後第 N 個交易日收盤（持有恰 N 日）；舊規則用快照前的 price_date 收盤進場，已全部重算")
        meta["returns_recomputed_at"] = datetime.now(TW_TZ).isoformat()
    # 先.八十-9：data_status 每輪都會更新，所以每輪都寫檔；last_returns_backfill_at 只在真的有回填／重算時更新
    if filled or recompute_all:
        meta["last_returns_backfill_at"] = datetime.now(TW_TZ).isoformat()
    meta["generated_at"] = datetime.now(TW_TZ).isoformat()  # 2026-09-03（P0三-三.3）回填／標註也算一次寫入
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"本輪新填 {filled} 個(snapshot, code, tN)欄位（{skipped_stale_or_missing}個因出場價過期/缺失跳過、"
          f"{skipped_no_entry}個因進場日當天沒有收盤跳過，留null等下次）；資料不完整批次 {n_incomplete} 個")


if __name__ == "__main__":
    main()
