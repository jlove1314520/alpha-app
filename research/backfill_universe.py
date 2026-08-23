"""全市場歷史資料一次性回補（2026-08-24，Cowork 稽核第 1 點）。

背景：`long_short_backtest.py` 的多空中性回測目前只覆蓋 universe.py 全市場
3,196 檔中的 170 檔（≈5.3%），是這次 session 內反覆撞到 FinMind 流量限制
（先是 30 分鐘硬性 IP 封鎖，之後又持續撞到較軟的每小時額度上限）下的產物。
Cowork 明確指出：decile（前後各 10%）多空在這麼小的宇宙上不可信——170 檔的
10% 只有 17 檔，樣本太小，任何結論都可能是巧合。

**這支腳本不是一次跑完的東西**，而是設計成可以被重複呼叫、每次做一個有界批次、
遇到真正的流量牆就乾淨停止、進度落地成本機檔案（不進 git，`research/data/`
底下）、下次呼叫自動接續未完成的部分。這正是「分批跑數小時/數日」的意思——
FinMind 免費層額度重置週期短（觀察到約每小時數百次），要真正覆蓋 3,196 檔
（每檔需要 4 個資料集：價格/股利/財報/月營收）需要遠超過一次 session 的時間，
所以設計成可以被馬拉松（`MARATHON_PROTOCOL.md`）在未來的每一輪裡持續呼叫，
而不是期待這次就能跑完。

**只落地資料，不算因子**：跟 `long_short_backtest.py` 的
`load_universe_with_factors()` 不同，這裡刻意只呼叫 `adjusted_price_series()`
（連帶抓 `TaiwanStockPrice`/`TaiwanStockDividend`）跟 `load_dev()` 抓
`TaiwanStockFinancialStatements`/`TaiwanStockMonthRevenue`，不呼叫
`prepare_score_factors()` 做實際的因子計算——回補階段的目標只是把資料落地成
parquet 快取，因子計算是之後回測時的事，混在一起做只會拖慢回補速度。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adjust import adjusted_price_series
from finmind_client import load_dev
from universe import universe as build_universe

STATE_PATH = Path(__file__).parent / "data" / "backfill_state.json"  # 不進 git（research/data/），
# 純本機進度狀態，內容是 {stock_id: "done"|"skip"} 的字典
START_DATE = "2010-01-01"
MAX_CONSECUTIVE_RATE_LIMITS = 15  # 連續遇到這麼多次限流就判斷「額度真的用盡了」，
# 不再空轉浪費時間逐一嘗試剩下的名字（它們大概率也會失敗），直接停止這一批次


def _load_state() -> dict[str, str]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict[str, str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_rate_limit_error(e: Exception) -> bool:
    s = str(e)
    return any(tok in s for tok in ("402", "403", "upper limit", "ip banned"))


def _try_fetch_one(stock_id: str) -> tuple[bool, bool]:
    """回傳 (是否成功, 是否為限流失敗)。成功的定義：價格序列有 >=260 個交易日
    （跟 long_short_backtest.py 的可用性門檻一致），且財報/月營收兩個資料集
    都至少成功呼叫過一次（不要求非空——某些代碼本來就沒有月營收，例如債券型ETF，
    這種情況記成 done 而非 skip，因為資料集本身有正確抓到，只是這檔股票真的沒有
    這類資料，跟「額度被擋」是不同情況）。
    """
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        return False, _is_rate_limit_error(e)
    if px.empty or len(px) < 260:
        return False, False  # 資料太短，不是限流問題，判定為永久跳過

    try:
        load_dev("TaiwanStockFinancialStatements", stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        return False, _is_rate_limit_error(e)

    try:
        load_dev("TaiwanStockMonthRevenue", stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        return False, _is_rate_limit_error(e)

    return True, False


def run_batch(batch_size: int = 300, seed: int = 20260824) -> dict:
    import random

    u = build_universe()
    all_ids = u["stock_id"].tolist()
    rng = random.Random(seed)
    rng.shuffle(all_ids)  # 跟 long_short_backtest.py 用同一顆種子，順序一致，方便對照進度

    state = _load_state()
    pending = [sid for sid in all_ids if state.get(sid) not in ("done", "skip")]
    print(f"全市場 {len(all_ids)} 檔，已完成 {sum(1 for v in state.values() if v == 'done')}，"
          f"已跳過 {sum(1 for v in state.values() if v == 'skip')}，待處理 {len(pending)}")

    attempted = 0
    newly_done = 0
    newly_skipped = 0
    consecutive_rate_limits = 0

    for sid in pending:
        if attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 檔，停止")
            break
        if consecutive_rate_limits >= MAX_CONSECUTIVE_RATE_LIMITS:
            print(f"連續 {consecutive_rate_limits} 次限流，判斷額度已用盡，提前停止本批次")
            break

        attempted += 1
        ok, rate_limited = _try_fetch_one(sid)
        if ok:
            state[sid] = "done"
            newly_done += 1
            consecutive_rate_limits = 0
        elif rate_limited:
            consecutive_rate_limits += 1
            # 不寫入 state，維持 pending，下次批次會重試
        else:
            state[sid] = "skip"
            newly_skipped += 1
            consecutive_rate_limits = 0

        if attempted % 50 == 0:
            _save_state(state)  # 定期存檔，避免中途被中斷（例如超過馬拉松25分鐘執行上限）時整批進度歸零
            done_count = sum(1 for v in state.values() if v == "done")
            print(f"  ...已嘗試 {attempted}/{min(batch_size, len(pending))}，"
                  f"本批新完成 {newly_done}，本批新跳過 {newly_skipped}，"
                  f"累積完成 {done_count}/{len(all_ids)}（{done_count/len(all_ids)*100:.1f}%）")

    _save_state(state)
    done_count = sum(1 for v in state.values() if v == "done")
    skip_count = sum(1 for v in state.values() if v == "skip")
    coverage_pct = done_count / len(all_ids) * 100
    print(f"\n本批次結束：嘗試 {attempted} 檔，新完成 {newly_done}，新跳過 {newly_skipped}，"
          f"因限流中止 {'是' if consecutive_rate_limits >= MAX_CONSECUTIVE_RATE_LIMITS else '否'}")
    print(f"累積總覆蓋率：{done_count}/{len(all_ids)}（{coverage_pct:.1f}%），累積永久跳過 {skip_count} 檔")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_skipped": newly_skipped,
        "total_done": done_count, "total_skip": skip_count, "total_universe": len(all_ids),
        "coverage_pct": coverage_pct,
        "hit_rate_limit_wall": consecutive_rate_limits >= MAX_CONSECUTIVE_RATE_LIMITS,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260824)
    args = parser.parse_args()
    run_batch(batch_size=args.batch_size, seed=args.seed)
