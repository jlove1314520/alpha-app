"""Cybex.債務5 相位敏感度掃描——把「固定週期重平衡的起始相位」從隱含常數變成可掃參數。

**問題是什麼**：固定週期重平衡（每 21 個交易日換一次股）的**起始相位是任意選的**。
`backtest/engine.py` 原本寫死 `day_i % N == 0`，等於永遠從回測第一天開始算，
這個「第一天」本身沒有任何經濟意義——換一個起始日就是另一組換股日、另一組價格，
績效可能差很多。Cybex 第 315 輪實測跨相位 Calmar 1.006～2.084，**同一個策略差近兩倍**。

所以「只報告單一相位的數字」＝ 報告了一個運氣成分未知的數字。本腳本的存在意義是
把那個運氣量出來：對每個既有的週頻／月頻回測，把相位平移 0..N-1 全部重跑，
**回報跨相位全距**（最好與最差差多少）。

**這支腳本不做判定**。它只產生數字與全距，PASS/FAIL 由對應的關卡腳本依
`MARATHON_PROTOCOL.md` 的門檻決定。誠實限制：跨相位全距大**不直接等於策略無效**，
它代表「單一相位的數字不可單獨採信」——要主張 edge，必須是**整片相位**都站得住，
比照參數高原的邏輯。

**執行方式**：
    python phase_sensitivity.py --self-test      # 不碰資料，驗證相位邏輯本身
    python phase_sensitivity.py --run            # 跑真實回測，可續跑（checkpoint）
    python phase_sensitivity.py --report         # 只從 checkpoint 產生報告，不跑回測

`--run` 有時間預算（環境變數 `PHASE_TIME_BUDGET_SECONDS`，預設 1200 秒）。
跑不完會落盤 checkpoint，下次接續，**不重算已完成的格子**。未跑完的目標在報告裡
明標「未完成」，不得拿未完成的部分算全距。

holdout 紀律：資料一律走 `finmind_client.load_dev()`（硬性截在 VAL_END），
每個回測結束後對 trades 跑 `assert_no_holdout_leakage`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import pandas as pd

from backtest.engine import BacktestConfig, run_backtest

CHECKPOINT_PATH = RESEARCH_DIR / "data" / "phase_sensitivity_checkpoint.json"
CSV_PATH = RESEARCH_DIR / "data" / "phase_sensitivity_grid.csv"
REPORT_PATH = RESEARCH_DIR / "PHASE_SENSITIVITY.md"

# 每個目標＝一個既有的 portfolio 層回測。`signal` 是「拿到共用 context 後怎麼組出
# signal_fn」，因為各腳本的 make_signal_fn 簽章不同（有的要 industry_map，有的要
# regime_lookup）——這裡用 adapter 對齊，**不改動那些既有腳本**。
TARGETS = [
    {
        "key": "f52w_high_portfolio_v1",
        "module": "f52w_high_portfolio_v1",
        "desc": "#17 52週高點接近度 Top20 月頻",
        "signal": lambda M, ctx: M.make_signal_fn(ctx["industry_map"], ctx["liquidity"]),
    },
    {
        "key": "dividend_yield_portfolio_v1",
        "module": "dividend_yield_portfolio_v1",
        "desc": "#4 股利率 carry Top20 月頻",
        "signal": lambda M, ctx: M.make_signal_fn(ctx["industry_map"], ctx["liquidity"]),
    },
    {
        "key": "pead_portfolio_v1",
        "module": "pead_portfolio_v1",
        "desc": "#3 PEAD 盈餘公告後漂移 Top20 月頻",
        "signal": lambda M, ctx: M.make_signal_fn(ctx["industry_map"], ctx["liquidity"]),
    },
    {
        "key": "short_sale_utilization_portfolio_v1",
        "module": "short_sale_utilization_portfolio_v1",
        "desc": "#36 融券使用率 Top20 月頻",
        "signal": lambda M, ctx: M.make_signal_fn(ctx["liquidity"]),
    },
    {
        "key": "margin_utilization_regime_portfolio_v1",
        "module": "margin_utilization_regime_portfolio_v1",
        "desc": "#30 融資使用率 regime-conditional Top20 月頻",
        "signal": lambda M, ctx: M.make_signal_fn(ctx["liquidity"], M.build_regime_lookup()),
    },
]


# ---------------------------------------------------------------- self-test

class _Recorder:
    """記錄 signal_fn 被呼叫在哪些日期；回傳空 dict 讓引擎不開任何部位
    （我們只要換股日的集合，不要績效）。"""

    def __init__(self) -> None:
        self.days: list[str] = []

    def __call__(self, price_data, as_of, market_df):
        self.days.append(as_of)
        return {}


def _synthetic_market(n_days: int = 60) -> pd.DataFrame:
    days = pd.bdate_range("2015-01-05", periods=n_days).strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({"date": days, "close": [100.0] * n_days, "adj_close": [100.0] * n_days})


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(name)

    market = _synthetic_market(60)
    calendar = list(market["date"])
    start, end = calendar[0], calendar[-1]

    # 1. n_days 模式：相位 p 的換股日必須恰好是日曆序位 ≡ p (mod N) 的那些天。
    N = 7
    for phase in range(N):
        rec = _Recorder()
        cfg = BacktestConfig(start_date=start, end_date=end, rebalance_every_n_days=N,
                             rebalance_phase=phase, book_name="phase_self_test")
        run_backtest(rec, {}, market, cfg)
        expected = [d for i, d in enumerate(calendar) if (i - phase) % N == 0]
        check(f"n_days 模式 phase={phase} 換股日集合正確", rec.days == expected,
              f"{len(rec.days)} 天")

    # 2. phase=0 必須跟「完全不設 phase」位元級相同（既有呼叫端行為不變）。
    rec_a, rec_b = _Recorder(), _Recorder()
    run_backtest(rec_a, {}, market, BacktestConfig(start_date=start, end_date=end,
                                                   rebalance_every_n_days=N, book_name="a"))
    run_backtest(rec_b, {}, market, BacktestConfig(start_date=start, end_date=end,
                                                   rebalance_every_n_days=N, rebalance_phase=0,
                                                   book_name="b"))
    check("phase=0 與不設 phase 完全相同（既有呼叫端行為不變）", rec_a.days == rec_b.days)

    # 3. 不同相位必須真的產生不同的換股日集合（否則這個參數是假的）。
    sets = []
    for phase in range(N):
        rec = _Recorder()
        run_backtest(rec, {}, market, BacktestConfig(start_date=start, end_date=end,
                                                     rebalance_every_n_days=N,
                                                     rebalance_phase=phase, book_name="c"))
        sets.append(tuple(rec.days))
    check("N 個相位產生 N 個互不相同的換股日集合", len(set(sets)) == N, f"{len(set(sets))}/{N}")

    # 4. weekday 模式：相位平移星期幾。
    for phase in range(5):
        rec = _Recorder()
        cfg = BacktestConfig(start_date=start, end_date=end, rebalance_weekday=4,
                             rebalance_phase=phase, book_name="d")
        run_backtest(rec, {}, market, cfg)
        want = (4 + phase) % 5
        got_weekdays = {pd.Timestamp(d).weekday() for d in rec.days}
        check(f"weekday 模式 phase={phase} → 星期 {want}", got_weekdays == {want}, str(sorted(got_weekdays)))

    # 5. 全距計算：空/單點/未完成一律不得回傳看起來像結論的數字。
    check("未完成的格子不算全距（None）", summarize_phases({}) is None)
    check("只有一個相位不算全距（None）", summarize_phases({"0": {"return_pct": 1.0}}) is None)
    s = summarize_phases({"0": {"return_pct": 1.0, "mdd_pct": -10.0, "n_trades": 5},
                          "1": {"return_pct": 3.0, "mdd_pct": -20.0, "n_trades": 7}})
    check("全距＝最大值減最小值", s is not None and abs(s["return_pct"]["range"] - 2.0) < 1e-9,
          f"range={s['return_pct']['range'] if s else None}")

    print(f"\n=== self-test {'全部通過' if not failures else f'{len(failures)} 項 FAIL'} ===")
    return 0 if not failures else 1


# ---------------------------------------------------------------- 統計

METRICS = ("return_pct", "mdd_pct", "sortino", "n_trades")


def summarize_phases(phase_rows: dict) -> dict | None:
    """phase_rows: {phase_str: {metric: value}}。**少於兩個相位一律回傳 None**
    ——一個點算不出全距，回一個 0 會被誤讀成「完全不敏感」。"""
    if len(phase_rows) < 2:
        return None
    out = {}
    for m in METRICS:
        vals = [r[m] for r in phase_rows.values() if r.get(m) is not None]
        if len(vals) < 2:
            continue
        out[m] = {
            "min": min(vals), "max": max(vals), "range": max(vals) - min(vals),
            "mean": sum(vals) / len(vals), "n_phases": len(vals),
        }
    return out or None


# ---------------------------------------------------------------- 實跑

def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_checkpoint(ck: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(ck, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CHECKPOINT_PATH)


def build_context() -> dict:
    """載入五個目標共用的那一份 300 檔樣本面板（各腳本 main() 的載入路徑一致，
    這裡集中做一次，不重複載入五遍）。"""
    from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from validation import holdout
    import portfolio_backtest_v2 as pbv2

    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in phase_sensitivity")
    market_df = prepare_market_data(market_raw)
    data = load_sample_with_factors(ids, market_df)
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in phase_sensitivity")
    return {
        "data": data,
        "market_df": market_df,
        "industry_map": load_industry_map(),
        "liquidity": {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()},
        "holdout": holdout,
    }


def run(time_budget: float) -> int:
    deadline = time.time() + time_budget
    ck = _load_checkpoint()

    print("載入共用樣本面板（五個目標共用同一份 300 檔樣本）...")
    t0 = time.time()
    ctx = build_context()
    holdout = ctx["holdout"]
    print(f"  {len(ctx['data'])} 檔可用，耗時 {time.time() - t0:.0f} 秒")

    labels = (("TRAIN", "2015-01-01", holdout.TRAIN_END),
              ("VALIDATION", "2021-01-01", holdout.VAL_END))

    for tgt in TARGETS:
        key = tgt["key"]
        M = __import__(tgt["module"])
        n_phase = M.REBALANCE_DAYS
        node = ck.setdefault(key, {"desc": tgt["desc"], "rebalance_days": n_phase,
                                   "top_n": M.TOP_N, "phases": {}})
        node["desc"], node["rebalance_days"], node["top_n"] = tgt["desc"], n_phase, M.TOP_N
        signal_fn = None

        for label, start, end in labels:
            done = node["phases"].setdefault(label, {})
            for phase in range(n_phase):
                if str(phase) in done:
                    continue
                if time.time() >= deadline:
                    print(f"  時間預算用盡，{key}/{label} 停在 phase={phase}（已落盤，下次接續）")
                    _save_checkpoint(ck)
                    write_report(ck)
                    return 0
                if signal_fn is None:
                    signal_fn = tgt["signal"](M, ctx)
                cfg = BacktestConfig(start_date=start, end_date=end, max_positions=M.TOP_N,
                                     rebalance_every_n_days=n_phase, rebalance_phase=phase,
                                     book_name=f"phase_sensitivity_{key}")
                t = time.time()
                res = run_backtest(signal_fn, ctx["data"], ctx["market_df"], cfg)
                holdout.assert_no_holdout_leakage(res.trades, date_col="date",
                                                  context=f"phase_sensitivity {key} {label} p{phase}")
                done[str(phase)] = {
                    "return_pct": res.total_return_pct,
                    "mdd_pct": res.max_drawdown_pct,
                    "sortino": res.sortino_ratio,
                    "n_trades": res.n_trades,
                }
                print(f"  {key} {label} phase={phase:2d}/{n_phase - 1}: "
                      f"報酬={res.total_return_pct:+7.2f}%  MDD={res.max_drawdown_pct:7.2f}%  "
                      f"trades={res.n_trades:4d}  ({time.time() - t:.0f}s)")
                _save_checkpoint(ck)

    _save_checkpoint(ck)
    write_report(ck)
    return 0


# ---------------------------------------------------------------- 報告

def write_report(ck: dict) -> None:
    rows = []
    lines = [
        "# 相位敏感度掃描（Cybex.債務5）",
        "",
        "本檔由 `research/phase_sensitivity.py` 產生，**不要手動編輯**。",
        "",
        "## 這份報告在回答什麼",
        "",
        "固定週期重平衡（每 N 個交易日換股）的**起始相位是任意選的**——回測從哪一天開始算",
        "第一次換股，沒有任何經濟意義，但會決定整條換股日序列。只報告單一相位的績效，",
        "等於報告了一個運氣成分未知的數字。這裡把相位平移 0..N-1 全部重跑，量出**跨相位全距**。",
        "",
        "**判讀規則（事前寫死）**：全距大不直接等於策略無效，它代表**單一相位的數字不可單獨採信**。",
        "要主張 edge，必須整片相位都站得住（比照參數高原的邏輯）；只有某幾個相位好＝相位挑選，",
        "屬於偽影。**未跑完的目標不得拿已完成的部分算全距**——本報告一律標「未完成」。",
        "",
    ]
    for tgt in TARGETS:
        key = tgt["key"]
        node = ck.get(key)
        lines.append(f"## {key}")
        lines.append("")
        lines.append(f"- 說明：{tgt['desc']}")
        if not node:
            lines += ["- **狀態：尚未跑**（checkpoint 無此目標）", ""]
            continue
        n_phase = node["rebalance_days"]
        lines.append(f"- 換股週期 N＝{n_phase} 個交易日 → 相位格子 0..{n_phase - 1}，Top{node['top_n']}")
        for label in ("TRAIN", "VALIDATION"):
            ph = node["phases"].get(label, {})
            s = summarize_phases(ph)
            if len(ph) < n_phase:
                lines.append(f"- **{label}：未完成（{len(ph)}/{n_phase} 個相位）——不計算全距**")
                continue
            lines.append(f"- **{label}（{len(ph)}/{n_phase} 個相位全部完成）**")
            lines.append("")
            lines.append("  | 指標 | 最小 | 最大 | **全距** | 平均 |")
            lines.append("  |---|---|---|---|---|")
            for m in METRICS:
                if s and m in s:
                    d = s[m]
                    lines.append(f"  | `{m}` | {d['min']:+.2f} | {d['max']:+.2f} | "
                                 f"**{d['range']:.2f}** | {d['mean']:+.2f} |")
            lines.append("")
            for p, r in sorted(ph.items(), key=lambda kv: int(kv[0])):
                rows.append({"target": key, "label": label, "phase": int(p), **r})
        lines.append("")

    lines += ["## 逐格資料", "", f"完整逐相位數字見 `{CSV_PATH.name}`（同一次執行產生）。", ""]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    if rows:
        pd.DataFrame(rows).to_csv(CSV_PATH, index=False)
    print(f"報告已寫入 {REPORT_PATH.name}（{len(rows)} 個完成的相位格子）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.report:
        write_report(_load_checkpoint())
        return 0
    if args.run:
        budget = float(os.environ.get("PHASE_TIME_BUDGET_SECONDS", "1200"))
        return run(budget)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
