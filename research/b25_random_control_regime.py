"""B25 隨機對照組「分情境百分位」補算（2026-10-18 總司令【先.一一〇】5 核准 先.一〇九-24）。

要補的欄位：`b25_regime_report.py` 分情境表裡「隨機對照組百分位」一欄（原本誠實標「不提供」，因為 B24-500 的
100 次隨機 draws 只留 final_equity、沒存逐日序列）。

做法（只重算、不改判定、不登記新試驗、不碰 holdout）：
1. 讀既有 500 檔因子快取（`value_board_v2_sample_cache_liquidity500_clean.pkl`）＋本機 TAIEX，零 FinMind 請求。
2. 期間跟 B24／B25 一樣：TRAIN 2015-01-01～holdout.TRAIN_END、VALIDATION 2021-01-01～holdout.VAL_END；
   市場資料先過 `holdout.assert_no_holdout_leakage`，不讀 VAL_END 之後。
3. 隨機 draw 直接用 B24 原腳本的 `make_random_signal_fn`（種子 RANDOM_CONTROL_SEED+i，i＝0～99），
   跟 B24-500 那 100 次是同一組抽法；真實策略用 `b25_regime_report.run_real_strategy_period`。
4. 每個 (期間, draw) 跑完就把「各情境桶的天數／日報酬總和／上漲天數」寫進 checkpoint（JSONL），
   下次啟動略過已完成的；B24 的「每日合格池」快取也存檔，續跑不必重算。
5. 時間預算（--max-minutes，預設 240）用完就在 draw 之間乾淨停下；夜間排程 AlphaB25Control 每晚 00:30 跑，
   約 2～3 晚跑完 100 次×2 期間。全部完成後輸出百分位表，之後再被叫起來就直接結束。

百分位定義：情境桶年化報酬（同 b25_regime_report：(1+平均日報酬)^252−1，TRAIN＋VALIDATION 兩期合併）
真實策略 > 隨機 draw 的比例×100（同 B24 的 final_equity 百分位寫法）。只補這一欄；勝率／MDD 不比。
這是補既有報告欄位，不是新搜尋：不呼叫 register_trial、不計入 N。

⚠️ 引擎差異（2026-10-18 試跑實測）：用現行回測引擎重跑真實策略，TRAIN／VALIDATION 總報酬 +141.31%／+217.32%，
跟 B24_RESULTS.md（+71.79%／+97.71%）與 B25 分情境表（2026-09-02，例：多頭 +29.98%）不同；各情境桶天數完全一致
（多頭 1825／空頭 612…），差異來自 9 月下旬起的引擎與成本修正。本腳本的真實策略與 100 次隨機 draws 都用現行引擎，
彼此可比；百分位表另列「真實策略年化（現行引擎）」，不得拿來對 B25 舊表的數字。
用法：python research/b25_random_control_regime.py [--max-minutes 240] [--max-draws N（測試用）]
"""
from __future__ import annotations

import mem_guard  # 497MB 快取＋全期回測，記憶體安全閥（同 b25_regime_report）
mem_guard.install()

import argparse
import json
import pickle
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import b25_regime_report as b25
import run_value_board_v2_pit_backtest as b24
from backtest.engine import BacktestConfig, run_backtest
from finmind_client import load_dev
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TZ = timezone(timedelta(hours=8))
N_DRAWS = b24.N_RANDOM_DRAWS  # 100，同 B24-500
PERIODS = (("TRAIN", "2015-01-01", holdout.TRAIN_END), ("VALIDATION", "2021-01-01", holdout.VAL_END))
DIMS = (("trend_regime", "多空"), ("range_regime", "盤整"), ("vol_regime", "波動"), ("trend_vol_combo", "多空x波動組合"))
OUT = Path(__file__).parent / "data" / "b25_random_control"
DRAWS = OUT / "draws.jsonl"
REAL = OUT / "real.json"
POOL = OUT / "eligible_pool_cache.pkl"
RESULT_CSV = Path(__file__).parent / "data" / "b25_regime_random_control_percentile.csv"
DONE = OUT / "DONE.json"


def log(msg: str) -> None:
    print(f"[{datetime.now(TZ):%m-%d %H:%M:%S}] {msg}", flush=True)


def bucket_stats(eq: pd.DataFrame, tagged: pd.DataFrame) -> dict:
    """逐日報酬 → {維度|情境: [天數, 日報酬總和, 上漲天數]}（合併兩期時直接相加即可算年化與勝率）。"""
    m = eq.merge(tagged[["date"] + [d for d, _ in DIMS]], on="date", how="left").dropna(subset=["trend_regime"])
    out = {}
    for col, name in DIMS:
        for val, sub in m.groupby(col):
            if str(val).startswith("資料不足"):
                continue
            r = sub["daily_return"]
            out[f"{name}|{val}"] = [int(len(r)), float(r.sum()), int((r > 0).sum())]
    return out


def daily_returns(result, label: str) -> pd.DataFrame:
    eq = result.equity_curve.copy()
    eq["daily_return"] = eq["equity"].pct_change()
    eq["period"] = label
    return eq.dropna(subset=["daily_return"])


def done_keys() -> set:
    if not DRAWS.exists():
        return set()
    keys = set()
    for line in DRAWS.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
            keys.add((d["period"], d["draw"]))
        except (ValueError, KeyError):
            continue  # 中途被砍留下的半行，照沒跑過處理
    return keys


def ann(n: int, s: float) -> float:
    return float((1 + s / n) ** 252 - 1) * 100 if n else float("nan")


def finish(real: dict) -> None:
    rows_by_key: dict[str, list] = {}
    per_draw: dict[int, dict] = {}
    for line in DRAWS.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        acc = per_draw.setdefault(d["draw"], {})
        for k, (n, s, up) in d["buckets"].items():
            a = acc.setdefault(k, [0, 0.0, 0])
            a[0] += n; a[1] += s; a[2] += up
    real_acc: dict = {}
    for p in real["periods"].values():
        for k, (n, s, up) in p.items():
            a = real_acc.setdefault(k, [0, 0.0, 0])
            a[0] += n; a[1] += s; a[2] += up
    for k, (n, s, _up) in sorted(real_acc.items()):
        rand = [ann(*per_draw[i][k][:2]) for i in sorted(per_draw) if k in per_draw[i] and per_draw[i][k][0]]
        real_ann = ann(n, s)
        insufficient = n < b25.SAMPLE_MIN_DAYS
        rows_by_key[k] = {
            "dimension": k.split("|")[0], "regime": k.split("|")[1], "n_days": n,
            "real_annualized_return_pct": None if insufficient else round(real_ann, 2),
            "random_median_annualized_pct": None if insufficient or not rand else round(float(np.median(rand)), 2),
            "random_control_percentile": None if insufficient or not rand else round(100.0 * float(np.mean([real_ann > x for x in rand])), 1),
            "random_draws_used": len(rand),
            "note": f"樣本不足<{b25.SAMPLE_MIN_DAYS}天不算" if insufficient else "",
        }
    df = pd.DataFrame(list(rows_by_key.values()))
    df.to_csv(RESULT_CSV, index=False, encoding="utf-8-sig")
    DONE.write_text(json.dumps({"finished_at": datetime.now(TZ).isoformat(timespec="seconds"), "draws": len(per_draw),
                                "result_csv": str(RESULT_CSV.name),
                                "engine_note": "真實策略與隨機組都用現行引擎；與 B24／B25（2026-09-02）舊數字不同，不得混比（見 docstring）"},
                               ensure_ascii=False), encoding="utf-8")
    log(f"全部完成：{len(per_draw)} 次 draws，百分位表 → {RESULT_CSV}")
    print(df.to_string(index=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=240.0)
    ap.add_argument("--max-draws", type=int, default=None, help="測試用：本次最多跑幾個 (期間, draw)")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if DONE.exists():
        log(f"已完成過（{DONE.read_text(encoding='utf-8')}），本次直接結束")
        return 0
    t0 = time.time()
    budget = a.max_minutes * 60

    log("載入因子快取（零 FinMind 請求）…")
    with open(b25.CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", "2010-01-01")
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in b25_random_control_regime")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    tagged = b25.tag_market_regimes(market_raw)
    log(f"載入完成 {len(data)} 檔，{time.time() - t0:.0f} 秒")

    if POOL.exists():
        try:
            b24._eligible_pool_cache.update(pickle.loads(POOL.read_bytes()))
            log(f"讀回合格池快取 {len(b24._eligible_pool_cache)} 天")
        except Exception as e:  # noqa: BLE001 —— 快取壞掉就重算，不影響結果
            log(f"合格池快取讀取失敗，重算：{type(e).__name__}")

    if REAL.exists():
        real = json.loads(REAL.read_text(encoding="utf-8"))
    else:
        log("真實策略逐日報酬（兩期）…")
        real = {"periods": {}}
        for label, start, end in PERIODS:
            eq = b25.run_real_strategy_period(label, data, market_df, industry_map, start, end)
            real["periods"][label] = bucket_stats(eq, tagged)
        real["computed_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        REAL.write_text(json.dumps(real, ensure_ascii=False), encoding="utf-8")

    done = done_keys()
    todo = [(lab, s, e, i) for i in range(N_DRAWS) for (lab, s, e) in PERIODS if (lab, i) not in done]
    log(f"已完成 {len(done)}／{N_DRAWS * len(PERIODS)}，本次待跑 {len(todo)}，預算 {a.max_minutes:.0f} 分鐘")
    ran = 0
    for lab, start, end, i in todo:
        if a.max_draws is not None and ran >= a.max_draws:
            break
        if time.time() - t0 > budget:
            log("時間預算用完，乾淨停下（下次從這裡續跑）")
            break
        t1 = time.time()
        cfg = BacktestConfig(start_date=start, end_date=end, max_positions=b24.TOP_N,
                             rebalance_every_n_days=b24.REBALANCE_DAYS, book_name="value_board_v2_random_control_b25")
        rfn = b24.make_random_signal_fn(industry_map, b24.START_DATE, b24.TOP_N, seed=b24.RANDOM_CONTROL_SEED + i)
        rr = run_backtest(rfn, data, market_df, cfg)
        rec = {"period": lab, "draw": i, "seed": b24.RANDOM_CONTROL_SEED + i, "final_equity": rr.final_equity,
               "buckets": bucket_stats(daily_returns(rr, lab), tagged), "secs": round(time.time() - t1, 1),
               "at": datetime.now(TZ).isoformat(timespec="seconds")}
        with open(DRAWS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            POOL.write_bytes(pickle.dumps(dict(b24._eligible_pool_cache)))
        except Exception as e:  # noqa: BLE001
            log(f"合格池快取存檔失敗（不影響結果）：{type(e).__name__}")
        ran += 1
        log(f"{lab} draw {i} 完成，{rec['secs']} 秒（本次第 {ran} 個）")

    if len(done_keys()) >= N_DRAWS * len(PERIODS):
        finish(real)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
