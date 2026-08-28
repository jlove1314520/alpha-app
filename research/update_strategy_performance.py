# -*- coding: utf-8 -*-
"""策略監控台升級：前向紙上模擬引擎（forward paper，2026-08-29新增）。

**使用者原話（鐵律，決定這支腳本的每一個設計選擇）**：「一律用『每個開盤日
前向模擬』(forward paper)，不用復盤」「forward paper嚴禁事後補建，只能
逐日往前累積」。

**這代表什麼**：這支腳本每次執行只能往`data/strategy_performance.json`
的`equity_curve`/`ledger`**append今天這一筆**，不能用歷史資料回頭重建
過去的軌跡——第一次執行的那天就是這個策略前向紀錄的起點（inception），
累積歷史只能靠之後每天（掛在`market.yml`排程）真的執行一次才會變長，
沒有任何捷徑。**這是刻意的設計，不是偷懶**：復盤（用歷史資料重跑）永遠
可以挑到「看起來厲害」的區間，前向模擬沒有這個作弊空間。

**追蹤對象**：只有已經有「每日更新的正式評分引擎」的策略才能前向模擬
（`STRATEGY_SCORE_FILES`）——`value_board_v2`/`momentum_board`/
`future_board`各自對應`scores.json`/`scores_momentum.json`/
`scores_future.json`。`fut_track`（期貨假說篩選帳本，不是單一組合策略）
跟兩個`草稿`baseline候選（`weinstein_stage2_baseline`/
`cta_trend_following_baseline`，根本沒有實作）都沒有每日選股輸出，
不追蹤，不製造假資料。

**持股/再平衡規則**：Top20等權（跟`build_picks_ledger.py`同一個
`rank<=20`篩選邏輯），月度再平衡（21個交易日，跟B24-500回測同一個
慣例）。全成本：換手部位套用`validation.costs.round_trip_cost_pct()`
（跟`backtest/engine.py`同一套費率常數，不是另外發明一套）。

**資料來源**：`data/price_history.json`（每日排程累積的OHLCV），不是
另外呼叫任何外部API——這支腳本本身零網路請求，符合資料源禮儀（不需要
節流/斷路器，沒有東西可以打爆）。

跑法：`python update_strategy_performance.py`，寫`data/
strategy_performance.json`；跑完建議接著跑`generate_strategies_json.py`
把這份資料併進`data/strategies.json`（App實際讀的檔案）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validation.costs import round_trip_cost_pct  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PRICE_HISTORY_PATH = DATA_DIR / "price_history.json"
PERF_PATH = DATA_DIR / "strategy_performance.json"

TOP_N = 20
REBALANCE_TRADING_DAYS = 21
ROUND_TRIP_COST_PCT = round_trip_cost_pct()  # 全成本：commission×2+tax+slippage×2，跟engine.py同一套費率

STRATEGY_SCORE_FILES = {
    "value_board_v2": REPO_ROOT / "scores.json",
    "momentum_board": REPO_ROOT / "scores_momentum.json",
    "future_board": REPO_ROOT / "scores_future.json",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_price_history() -> dict:
    if not PRICE_HISTORY_PATH.exists():
        return {}
    return json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8")).get("prices", {})


def all_trading_dates(prices: dict) -> list[str]:
    """近似市場交易日曆——用price_history.json所有股票出現過的日期聯集，
    不是官方交易日曆，但涵蓋率夠高（486+檔），實務上等同。"""
    dates: set[str] = set()
    for rows in prices.values():
        for r in rows:
            dates.add(r["date"])
    return sorted(dates)


def close_on(prices: dict, code: str, date: str) -> float | None:
    rows = prices.get(code)
    if not rows:
        return None
    for r in reversed(rows):
        if r["date"] == date:
            return r.get("adj_close") or r.get("close")
    return None


def top20_from_scores(path: Path) -> list[str]:
    """跟build_picks_ledger.py完全同一份邏輯：rank不是null才算數、依rank
    排序取前20——刻意跟既有的Top20台帳用同一套規則，不是另外發明一種。"""
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    ranked = sorted(
        (s for s in d.get("stocks", []) if s.get("rank") is not None),
        key=lambda s: s["rank"],
    )[:TOP_N]
    return [s["code"] for s in ranked]


def trading_days_since(calendar: list[str], since_date: str, today: str) -> int:
    """calendar裡日期嚴格大於since_date、小於等於today的個數。"""
    return sum(1 for d in calendar if since_date < d <= today)


def update_one_strategy(score_path: Path, prices: dict, calendar: list[str], today: str, state: dict | None) -> dict | None:
    equity_curve = list(state["equity_curve"]) if state else []
    ledger = list(state["ledger"]) if state else []
    holdings = list(state["holdings"]) if state else []

    if equity_curve and equity_curve[-1]["date"] == today:
        return state  # 今天已經處理過，不重複append（同一天重跑這支腳本要是idempotent的）

    if not state:
        # 第一次執行：這是inception day，只能從「今天」開始累積，不回填任何
        # 過去的日期——這正是「forward paper嚴禁事後補建」鐵律的具體實作。
        top20 = top20_from_scores(score_path)
        new_holdings = [c for c in top20 if close_on(prices, c, today) is not None]
        if not new_holdings:
            return None  # 查無可用資料，誠實不產生任何紀錄，不是bug是資料還沒到位
        equity_curve.append({"date": today, "cum_return_pct": 0.0})
        ledger.append({
            "date": today, "buys": new_holdings, "sells": [],
            "daily_pnl_pct": 0.0, "n_holdings": len(new_holdings),
        })
        return {
            "inception_date": today, "last_rebalance_date": today,
            "holdings": new_holdings, "equity_curve": equity_curve, "ledger": ledger,
        }

    last_date = equity_curve[-1]["date"]
    rets = []
    for c in holdings:
        p0, p1 = close_on(prices, c, last_date), close_on(prices, c, today)
        if p0 and p1:
            rets.append(p1 / p0 - 1)
    daily_ret = (sum(rets) / len(rets)) if rets else 0.0
    prev_cum = equity_curve[-1]["cum_return_pct"] / 100.0
    new_cum = (1 + prev_cum) * (1 + daily_ret) - 1

    buys, sells = [], []
    last_rebalance_date = state["last_rebalance_date"]
    is_rebalance = trading_days_since(calendar, last_rebalance_date, today) >= REBALANCE_TRADING_DAYS
    if is_rebalance:
        new_top20 = top20_from_scores(score_path)
        new_holdings = [c for c in new_top20 if close_on(prices, c, today) is not None]
        if new_holdings:
            sells = [c for c in holdings if c not in new_holdings]
            buys = [c for c in new_holdings if c not in holdings]
            # 換手成本：以「賣出檔數/20」近似換手比例(等權配置下每檔佔1/20)，
            # 乘上全成本費率，直接扣在當天累積報酬上——跟engine.py的成本模型
            # 精神一致（費率相同），但這裡是組合層級近似不是逐股逐筆記帳。
            turnover_frac = len(sells) / TOP_N
            cost = turnover_frac * ROUND_TRIP_COST_PCT
            new_cum = (1 + new_cum) * (1 - cost) - 1
            holdings = new_holdings
            last_rebalance_date = today

    equity_curve.append({"date": today, "cum_return_pct": round(new_cum * 100, 4)})
    ledger.append({
        "date": today, "buys": buys, "sells": sells,
        "daily_pnl_pct": round(daily_ret * 100, 4), "n_holdings": len(holdings),
    })
    return {
        "inception_date": state["inception_date"], "last_rebalance_date": last_rebalance_date,
        "holdings": holdings, "equity_curve": equity_curve, "ledger": ledger,
    }


def main():
    prices = load_price_history()
    if not prices:
        print("data/price_history.json查無資料，無法更新前向績效，略過")
        return
    calendar = all_trading_dates(prices)
    today = calendar[-1]
    print(f"今天（最新交易日）：{today}，交易日曆共{len(calendar)}天")

    existing = json.loads(PERF_PATH.read_text(encoding="utf-8")) if PERF_PATH.exists() else {"strategies": {}}
    existing.setdefault("strategies", {})

    for strategy_id, score_path in STRATEGY_SCORE_FILES.items():
        state = existing["strategies"].get(strategy_id)
        new_state = update_one_strategy(score_path, prices, calendar, today, state)
        if new_state is None:
            print(f"  {strategy_id}: 略過（{score_path.name}查無資料或今日無可用收盤價）")
            continue
        new_state["forward_return_todate_pct"] = new_state["equity_curve"][-1]["cum_return_pct"]
        new_state["trading_days_count"] = len(new_state["equity_curve"])
        existing["strategies"][strategy_id] = new_state
        print(f"  {strategy_id}: forward_return={new_state['forward_return_todate_pct']:+.2f}%  "
              f"trading_days={new_state['trading_days_count']}  持股數={len(new_state['holdings'])}")

    existing["generated_at"] = _now_iso()
    existing["as_of_trading_date"] = today
    PERF_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {PERF_PATH}")


if __name__ == "__main__":
    main()
