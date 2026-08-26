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
跟 `load_dev()` 抓 `TaiwanStockFinancialStatements`/`TaiwanStockMonthRevenue`，
不呼叫 `prepare_score_factors()` 做實際的因子計算——回補階段的目標只是把資料
落地成 parquet 快取，因子計算是之後回測時的事，混在一起做只會拖慢回補速度。

**2026-08-26 混合資料源架構變更（解除 FinMind 402 額度瓶頸）：**
`adjusted_price_series()`（`adjust.py`）已改為優先呼叫 yfinance，價格/成交量
歷史不再依賴 FinMind 額度。財報/月營收目前仍走 FinMind（TWSE openapi
`t187ap05_L` 等端點只提供最新月份快照、無歷史區間查詢，MOPS 歷史月營收需要
另外做 HTML 抓取，這次還沒做，誠實記錄在 `DATA.md`）——**因此「done」的判定
從這天起改成只看價格是否成功**（>=260 個交易日），財報/月營收變成盡力而為、
額度用盡就跳過但不影響 done 判定、不再讓整批回補因為 FinMind 402 而提早停止。
見 `_try_fetch_one()` 的說明。三大法人買賣超（`f_foreign_streak`/`f_inst_flow`
等因子用到的資料）也已改用 TWSE T86 端點為主，見 `twse_t86_client.py`／
`backfill_t86.py`（獨立的、按日期快取的回補腳本，不在這支腳本的範圍內）。
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
# 2026-08-26 從 15 調高到 60：這個計數器現在幾乎只會被「yfinance 兩個後綴都沒有
# （通常是較舊的下市股，Yahoo Finance 沒收錄）→ 退回 FinMind 價格→ 撞 402」這條路徑
# 觸發，不再是「FinMind IP 被封需要冷卻」那種系統性問題（因為多數股票的價格已經不
# 靠 FinMind 了）。舊門檻 15 太容易被「隨機洗牌後剛好連續一串較舊下市股」誤觸發，
# 讓整批提早停止、浪費了本來還抓得到的其餘股票。
MAX_CONSECUTIVE_RATE_LIMITS = 60


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


# 2026-08-26 使用者裁示（資料源瓶頸解除）：價量歷史已改用 yfinance（見 adjust.py），
# 不再依賴 FinMind 額度。財報/月營收目前仍走 FinMind（TWSE/MOPS 官方端點只提供最新
# 快照、無歷史區間查詢，尚未有替代方案，見 DATA.md 誠實揭露），改成「盡力而為、
# 不擋 done 判定」——額度用盡時這兩個資料集直接跳過記錄，不再讓整批回補因為 FinMind
# 402 而提早停止（過去的行為：財報/月營收任一失敗就整檔判定「限流、待重試」，等於
# 只要 FinMind 額度用盡，即使 yfinance 價格明明抓得到，整批也會在遇到
# MAX_CONSECUTIVE_RATE_LIMITS 次後停擺）。
_finmind_side_channel_dead = False  # 一批次內只要偵測到一次限流，之後同一批次不再浪費呼叫


def _try_fetch_one(stock_id: str) -> tuple[bool, bool, bool]:
    """回傳 (是否成功, 是否為限流失敗, 財報/月營收是否本次也拿到)。

    成功（可計入宇宙覆蓋率）的定義從 2026-08-26 起改為：**只看價格**——
    價格序列有 >=260 個交易日（跟 long_short_backtest.py 的可用性門檻一致）。
    財報/月營收是「加分」欄位，能拿到就存，拿不到（FinMind 額度用盡）也不影響
    這檔股票被記成 done，之後任何一批只要 FinMind 額度恢復，都可以之後單獨補。
    """
    global _finmind_side_channel_dead

    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        return False, _is_rate_limit_error(e), False
    if px.empty or len(px) < 260:
        return False, False, False  # 資料太短，不是限流問題，判定為永久跳過

    got_financials_or_revenue = False
    if not _finmind_side_channel_dead:
        try:
            load_dev("TaiwanStockFinancialStatements", stock_id, START_DATE)
            load_dev("TaiwanStockMonthRevenue", stock_id, START_DATE)
            got_financials_or_revenue = True
        except Exception as e:  # noqa: BLE001
            if _is_rate_limit_error(e):
                _finmind_side_channel_dead = True
                print("  （偵測到 FinMind 額度用盡，本批次剩餘股票的財報/月營收改為跳過，"
                      "不影響價格覆蓋率判定；下一批次會重新嘗試）")
            # 非限流的個別失敗（例如這檔真的沒有財報）不擴散判定，繼續往下走

    return True, False, got_financials_or_revenue


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
    newly_done_with_finrev = 0
    consecutive_rate_limits = 0

    for sid in pending:
        if attempted >= batch_size:
            print(f"達到本批次上限 {batch_size} 檔，停止")
            break
        if consecutive_rate_limits >= MAX_CONSECUTIVE_RATE_LIMITS:
            print(f"連續 {consecutive_rate_limits} 次限流，判斷額度已用盡，提前停止本批次")
            break

        attempted += 1
        ok, rate_limited, got_finrev = _try_fetch_one(sid)
        if ok:
            state[sid] = "done"
            newly_done += 1
            if got_finrev:
                newly_done_with_finrev += 1
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
    print(f"\n本批次結束：嘗試 {attempted} 檔，新完成 {newly_done}（其中 {newly_done_with_finrev} 檔財報/月營收也成功，"
          f"{newly_done - newly_done_with_finrev} 檔財報/月營收因 FinMind 額度跳過待補），新跳過 {newly_skipped}，"
          f"因限流中止 {'是' if consecutive_rate_limits >= MAX_CONSECUTIVE_RATE_LIMITS else '否'}")
    print(f"累積總覆蓋率（僅計價格，2026-08-26起新定義）：{done_count}/{len(all_ids)}（{coverage_pct:.1f}%），累積永久跳過 {skip_count} 檔")

    return {
        "attempted": attempted, "newly_done": newly_done, "newly_skipped": newly_skipped,
        "newly_done_with_finrev": newly_done_with_finrev,
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
