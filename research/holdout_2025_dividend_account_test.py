# -*- coding: utf-8 -*-
"""H.一（2026-09-26總司令裁示【考.一結案確認＋新候選dividend×70/30＋
holdout單次解鎖＋daily_price修正核准】）：holdout單次解鎖，新候選
`dividend_yield_v1_common × 帳戶70/30`（TRIALS_LEDGER #400事前登記）的
一致性檢查，期間2025-01-01~資料最新日。

**ONLY-ONCE 鐵律（裁示原文）**：只跑一次；有結果數字產出後不得重跑。
`validation.holdout.unlock_holdout_once()`本身仍是全域、跨專案唯一一次
（不是「這個候選限定」，是整個repo一次燒毀，見該函式docstring）——這件事
沒有改變。

**2026-09-26 守.一裁示已補上機制層級的收窄**：上一段原本如實記錄的機制
限制（「解鎖後對整個專案永久開放」）已被`validation/holdout.py`的
`ALLOWED_HOLDOUT_READERS`允許清單堵住——`assert_no_holdout_leakage()`
現在額外檢查呼叫堆疊上是否出現本檔案的檔名，不在清單內的任何其他腳本，
即使`is_holdout_consumed()`為True，讀到VAL_END之後的資料一律仍然raise，
效果等同holdout從未解鎖過。也就是說機制上現在**確實只對這支腳本解鎖**，
不再只是政策自律。往後新研究已無回測用的乾淨資料，唯一的樣本外檢定
管道是紙上交易（forward paper trading）。

**只讀既有機制，不重新發明**：`adjust.py::adjustment_events()`的docstring
明講「Callers doing an actual one-time holdout evaluation should use
finmind_client.load_full_history() directly and route the result through
validation.holdout.unlock_holdout_once() themselves」——這支腳本逐字
遵照這個既有的官方指引，複製`adjustment_events()`的還原股價演算法（不
呼叫`adjust.py`本體，因為那支模組全部走`load_dev()`會被cap擋住），
換成uncapped版本。

用法：python research/holdout_2025_dividend_account_test.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mem_guard
mem_guard.install()

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from adjust import _mask_non_positive_adj_prices
from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate, run_backtest
from cbc_rf_rate_client import load_risk_free_rate_series, rf_rate_for_date
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
import factors as factors_mod
from factors import prepare_factors, _is_quota_error
from finmind_client import _fetch, load_full_history
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from universe import classify_security, universe as build_universe
from validation import holdout
import portfolio_backtest_v2 as pbv2
from comparable_trial_variance import dimson_ir
from survival_constraint_allocation_test import compute_mdd, segment_mdd
import dividend_yield_portfolio_v1 as div_mod

LOOKBACK_START = "2024-01-01"  # 給TTM股利率(366天)+流動性代理(20日)足夠緩衝
PERIOD_START = "2025-01-01"
STOCK_WEIGHT = 0.70
BOND_WEIGHT = 0.30
REBALANCE_DAYS = div_mod.REBALANCE_DAYS  # 承接股票部位同一個月頻節奏，帳戶再平衡沿用同一組交易日

OUT_JSON = Path(__file__).parent / "data" / "holdout_2025_dividend_account_result.json"
GATES_JSON = Path(__file__).parent / "data" / "h1_gates.json"  # 乾.一：只印計數/日期，不含任何報酬/IR/MDD


def _info_lookup() -> dict[str, dict]:
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    lookup = info.set_index("stock_id")[["stock_name", "industry_category"]].to_dict("index")
    combined = build_universe()
    for _, row in combined.iterrows():
        sid = row["stock_id"]
        if sid not in lookup:
            lookup[sid] = {"stock_name": row["stock_name"], "industry_category": row.get("industry_category")}
    return lookup


def _dividend_yield_ttm_cash_uncapped(stock_id: str, start_date: str) -> pd.DataFrame:
    """修.五（2026-09-26總司令裁示【緊急：H.一立即暫停重跑，修正兩個bug後
    先做乾跑檢查】）：`factors.py::_dividend_yield_ttm_cash()`的holdout版本
    ——用`load_full_history(allow_holdout=True)`取代`load_dev()`，計算邏輯
    完全共用`factors._dividend_yield_ttm_cash_from_df()`（同一份純函式，
    不是另外複製一份算法）。

    這支函式在`main()`裡透過monkeypatch
    `factors_mod._dividend_yield_ttm_cash = _dividend_yield_ttm_cash_uncapped`
    生效——`prepare_factors()`內部呼叫`_dividend_yield_ttm_cash(...)`是
    module-level的bare name查找，在Python裡是呼叫當下才解析，不是def時
    綁定，所以從外部覆寫`factors`模組的這個名字，`prepare_factors()`
    接下來呼叫到的就是這一版，不需要改`prepare_factors()`本身或重新
    plumb一個新參數穿過整條呼叫鏈。跟同一支腳本裡
    `pbv2._0050_TOTAL_RETURN_SERIES`的既有monkeypatch手法一致。

    證據：`research/audit_h1_dividend_pit_lag.py`（5/5檔的因子pit_date
    停在VAL_END前最後一次除息，跟真實2025+除息日不一致）。
    """
    div = load_full_history("TaiwanStockDividend", stock_id, start_date, allow_holdout=True)
    return factors_mod._dividend_yield_ttm_cash_from_df(div)


def _uncapped_adjustment_events(raw: pd.DataFrame, div: pd.DataFrame) -> pd.DataFrame:
    """逐字複製`adjust.py::adjustment_events()`的演算法，差別只在raw/div
    是呼叫端已經用`load_full_history(allow_holdout=True)`抓好、傳進來的
    uncapped版本，不在這裡重新呼叫`load_dev()`。"""
    if div.empty:
        return pd.DataFrame(columns=["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio"])
    if raw.empty:
        return pd.DataFrame(columns=["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio"])
    raw = raw.sort_values("date").reset_index(drop=True)
    close_by_date = dict(zip(raw["date"], raw["close"]))
    trading_dates = raw["date"].tolist()

    events = []
    for _, row in div.iterrows():
        ex_date = row.get("CashExDividendTradingDate") or row.get("StockExDividendTradingDate")
        if not ex_date:
            continue
        cash = row.get("CashEarningsDistribution") or 0.0
        stock_ratio = row.get("StockEarningsDistribution") or 0.0
        rights_ratio = row.get("CashIncreaseSubscriptionRate") or 0.0
        rights_price = row.get("CashIncreaseSubscriptionpRrice") or 0.0
        if cash == 0 and stock_ratio == 0 and rights_ratio == 0:
            continue
        prior = [d for d in trading_dates if d < ex_date]
        if not prior:
            continue
        prev_date = prior[-1]
        prev_close = close_by_date[prev_date]
        if prev_close in (None, 0) or pd.isna(prev_close):
            continue
        numerator = prev_close - cash + rights_price * rights_ratio
        denominator = 1 + stock_ratio + rights_ratio
        if denominator <= 0 or numerator <= 0:
            continue
        ref_price = numerator / denominator
        factor = ref_price / prev_close
        events.append({"ex_date": ex_date, "prev_trading_date": prev_date, "factor": factor,
                        "cash": cash, "stock_ratio": stock_ratio})
    if not events:
        return pd.DataFrame(columns=["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio"])
    return pd.DataFrame(events).sort_values("ex_date").reset_index(drop=True)


def uncapped_adjusted_price_series(stock_id: str, start_date: str) -> pd.DataFrame:
    """`adjust.py::adjusted_price_series()`FinMind路徑的uncapped版本
    （不用yfinance——`yf_price_client.py`同樣被cap在VAL_END，holdout期
    完全沒有uncapped的yfinance可用，這是現有兩條資料路徑共同的架構限制，
    如實記錄不假裝繞得過去）。"""
    raw = load_full_history("TaiwanStockPrice", stock_id, start_date, allow_holdout=True)
    if raw.empty:
        raw = raw.copy()
        if "source" not in raw.columns:
            raw["source"] = None
        return raw
    raw = raw.sort_values("date").reset_index(drop=True)
    div = load_full_history("TaiwanStockDividend", stock_id, start_date, allow_holdout=True)
    events = _uncapped_adjustment_events(raw, div)

    factor_cum = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        mask = raw["date"] < ev["ex_date"]
        factor_cum.loc[mask] = factor_cum.loc[mask] * ev["factor"]

    out = raw.copy()
    out["adj_close"] = raw["close"].astype(float) * factor_cum
    out["adj_open"] = raw["open"].astype(float) * factor_cum
    out["adj_high"] = raw["max"].astype(float) * factor_cum
    out["adj_low"] = raw["min"].astype(float) * factor_cum
    out["source"] = "finmind_uncapped"
    _mask_non_positive_adj_prices(out)
    return out


def simulate_account(stock_equity: pd.DataFrame, rf_monthly: pd.DataFrame, stock_w: float,
                      *, rebalance_every_n_days: int, initial_capital: float = 1_000_000.0) -> pd.DataFrame:
    """帳戶層級70/30固定配置，逐字比照`survival_constraint_allocation_
    test.py::simulate_fixed_allocation()`的邏輯（月頻再平衡+真實權重
    漂移+定期再平衡照實收成本），差別只在股票腿餵進來的是已經跑完
    `dividend_yield_portfolio_v1`策略的權益曲線（不是buy&hold 0050），
    債券腿一樣是定存代理。"""
    df = stock_equity.sort_values("date").reset_index(drop=True)
    cfg = BacktestConfig(start_date=str(df["date"].iloc[0]), end_date=str(df["date"].iloc[-1]),
                          initial_capital=initial_capital, cost_multiplier=1.0,
                          book_name="holdout_2025_account_7030", instrument_type="etf")
    buy_rate = buy_leg_rate(cfg)
    sell_rate = sell_leg_rate(cfg)

    stock_value = initial_capital * stock_w
    bond_value = initial_capital * (1 - stock_w)
    rows = []
    prev_equity = None
    for i, row in df.iterrows():
        equity_now = float(row["equity"])
        date = row["date"]
        if prev_equity is not None:
            stock_value *= equity_now / prev_equity
        rf_pct = rf_rate_for_date(pd.Timestamp(date), rf_monthly)
        bond_daily_ret = (1.0 + rf_pct / 100.0) ** (1.0 / 252.0) - 1.0
        bond_value *= (1.0 + bond_daily_ret)
        prev_equity = equity_now

        is_rebalance_day = (i == 0) or (i % rebalance_every_n_days == 0)
        if is_rebalance_day and stock_w not in (0.0, 1.0):
            total = stock_value + bond_value
            target_stock = total * stock_w
            diff = target_stock - stock_value
            if diff > 0:
                cost = diff * buy_rate
                stock_value += diff - cost
                bond_value -= diff
            elif diff < 0:
                sell_amt = -diff
                cost = sell_amt * sell_rate
                stock_value -= sell_amt
                bond_value += sell_amt - cost

        rows.append({"date": date, "equity": stock_value + bond_value,
                     "stock_value": stock_value, "bond_value": bond_value})
    return pd.DataFrame(rows)


def compute_2007_2014_account_7030_reference() -> dict:
    """參考值（裁示原文：不作判準，因屬考後計算）：機械式重現考.一
    dividend_yield_portfolio_v1的2007-2014股票部位equity_curve（跟
    single_shot_2007_2014_test.py用同一signal_fn/BacktestConfig，確定性
    重現已登記的#399結果，不是新試驗——比照宇.一稽核先例），套上同一套
    `simulate_account()`70/30邏輯，算出帳戶層級MDD供對照。**全程只用
    2007-2014已核准歷史資料，不觸碰holdout，可安全在unlock_holdout_
    once()之前執行**。"""
    import single_shot_2007_2014_test as s2007

    print("\n=== 參考值：機械式重現考.一2007-2014帳戶70/30 MDD（不作判準）===", flush=True)
    data, market_df, industry_map, liquidity, n_common = s2007.load_common_stock_data_2007_2014()
    signal_fn = div_mod.make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=s2007.OOS_START, end_date=s2007.OOS_END,
                          max_positions=div_mod.TOP_N, rebalance_every_n_days=div_mod.REBALANCE_DAYS,
                          commission_discount=0.18, instrument_type="normal",
                          book_name="reference_2007_2014_dividend_stock_leg")
    result = run_backtest(signal_fn, data, market_df, cfg)
    rf_monthly = load_risk_free_rate_series()
    account_eq = simulate_account(result.equity_curve, rf_monthly, STOCK_WEIGHT,
                                   rebalance_every_n_days=REBALANCE_DAYS)
    ref_mdd = compute_mdd(account_eq["equity"])
    ref_return = float(account_eq["equity"].iloc[-1] / account_eq["equity"].iloc[0] - 1) * 100
    print(f"  2007-2014 股票部位MDD(考.一#399既有值-53.72%對照)={compute_mdd(result.equity_curve['equity']):.2f}%", flush=True)
    print(f"  2007-2014 帳戶(70/30)報酬={ref_return:+.2f}%  帳戶(70/30)MDD={ref_mdd:.2f}%（僅供參考，不作判準）", flush=True)
    return {"stock_leg_return_pct": round(result.total_return_pct, 2),
            "stock_leg_mdd_pct": round(compute_mdd(result.equity_curve["equity"]), 2),
            "account_70_30_return_pct": round(ref_return, 2),
            "account_70_30_mdd_pct": round(ref_mdd, 2),
            "note": "機械式重現考.一#399的股票部位equity_curve(確定性重現既有結果，非新試驗)，"
                    "套用同一套70/30帳戶模擬邏輯，僅供參考不作H.一判準。"}


def main(gates_only: bool = False):
    print("=== H.一：holdout單次解鎖，dividend_yield_v1_common×帳戶70/30一致性檢查 ===", flush=True)
    if gates_only:
        print("**--gates-only模式（乾.一）**：只載入資料＋跑G1~G4檢查，印完就結束，"
              "不執行第5步以後的正式回測，不印任何報酬/IR/MDD。", flush=True)
    already_unlocked = holdout.is_holdout_consumed()
    print(f"is_holdout_consumed() 開工前 = {already_unlocked}"
          f"{'（第一次執行已解鎖過，本次是接續完成崩潰前未跑完的部分，見HOLDOUT_LOG.md）' if already_unlocked else ''}",
          flush=True)

    # ── 0. 參考值（安全，全程2007-2014歷史資料，不觸碰holdout）──
    reference_2007_2014 = compute_2007_2014_account_7030_reference()

    # ── 1. 建普通股宇宙（同考.一sample，251/300檔） ──
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    info_lookup = _info_lookup()
    common_ids = [sid for sid in sample_ids
                  if classify_security(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                        (info_lookup.get(sid) or {}).get("industry_category")) == "普通股"]
    print(f"300檔樣本中普通股={len(common_ids)}檔", flush=True)

    # ── 2. unlock_holdout_once()：只在真的還沒解鎖時才呼叫 ──
    # 2026-09-26第一次執行時已成功呼叫過一次（is_holdout_consumed()全域
    # 燒毀），隨後在載入第27檔個股價格時撞上FinMind額度上限（HTTP 402）
    # 崩潰——依裁示規則3「產出任何結果數字之前崩潰，可以修bug後重跑，
    # 但須在TRIALS_LEDGER記錄崩潰原因與修正內容」：holdout解鎖本身已經
    # 不可逆地完成（unlock_holdout_once()是全專案一次性，不是這支腳本
    # 可以重跑的部分），第一次執行真正沒跑完的是「載入uncapped資料+跑
    # 回測」這段，那段之前沒有印出任何H.一正式結果數字（只有安全的
    # 參考值段落），符合規則3可修bug重跑的條件。這裡把unlock呼叫改成
    # 條件式，已經解鎖就跳過、不重複呼叫（重複呼叫本來就會被
    # unlock_holdout_once()自己拒絕並RuntimeError，這裡是主動避免製造
    # 一次「BLOCKED」的log噪音，邏輯上完全等價）。
    market_raw_uncapped = load_full_history("TaiwanStockPrice", "TAIEX", LOOKBACK_START, allow_holdout=True)
    if not holdout.is_holdout_consumed():
        REASON = ("H.一（2026-09-26總司令裁示【考.一結案確認＋新候選dividend×70/30＋holdout單次解鎖＋"
                  "daily_price修正核准】）：dividend_yield_v1_common×帳戶70/30一致性檢查，"
                  "期間2025-01-01~資料最新日，僅限TRIALS_LEDGER#400這一個候選，only-once。")
        APPROVED_BY = "總司令（PENDING_QUEUE.md 2026-09-26 H.一裁示）"
        market_raw_holdout_slice = holdout.unlock_holdout_once(market_raw_uncapped, REASON, APPROVED_BY)
        print(f"holdout.unlock_holdout_once() 已執行——is_holdout_consumed()現在 = "
              f"{holdout.is_holdout_consumed()}（此後全域解鎖，不可逆）", flush=True)
        print(f"  TAIEX holdout切片：{len(market_raw_holdout_slice)}列，"
              f"{market_raw_holdout_slice['date'].min() if not market_raw_holdout_slice.empty else None} ~ "
              f"{market_raw_holdout_slice['date'].max() if not market_raw_holdout_slice.empty else None}", flush=True)
    else:
        print("holdout已經在先前執行中解鎖過（見HOLDOUT_LOG.md），本次接續執行不重複呼叫"
              "unlock_holdout_once()——直接使用已經全域解鎖的狀態繼續跑資料載入+回測。", flush=True)

    # market_df改用完整uncapped市場資料（TRAIN+VAL+HOLDOUT全段，供prepare_market_data算均線等指標，
    # 不是只用holdout切片本身——跟考.一手法一致，只是這次資料源沒有cap）。
    market_df = prepare_market_data(market_raw_uncapped)

    # ── 2b. 關鍵修正：pbv2.alpha_significance()/buy_and_hold_index_pct()內部
    # 呼叫的_load_0050_total_return_series()走survival_constraint_allocation_
    # test.py::load_0050_full_history()，那支函式明確cap在VAL_END——若不處理，
    # holdout期(2025+)的策略報酬序列會完全對不到任何0050基準日期，Dimson
    # regression直接拿到空DataFrame。這裡用uncapped版的0050還原股價，直接
    # 預填pbv2模組層級的快取變數，讓它跳過內部的capped載入邏輯改用這份——
    # 這不是重新發明alpha_significance()的統計邏輯（那段完全沿用，未改一行），
    # 只是換掉它依賴的0050基準資料來源本身的cap範圍。
    print("\n載入0050 uncapped還原股價，預填pbv2._0050_TOTAL_RETURN_SERIES快取...", flush=True)
    zero050_uncapped = uncapped_adjusted_price_series("0050", "2003-01-01")
    zero050_series = zero050_uncapped.copy()
    zero050_series["date"] = zero050_series["date"].astype(str)
    zero050_series = zero050_series.set_index("date")["adj_close"].sort_index()
    pbv2._0050_TOTAL_RETURN_SERIES = zero050_series
    print(f"  0050 uncapped序列範圍：{zero050_series.index.min()} ~ {zero050_series.index.max()}"
          f"（{len(zero050_series)}筆）", flush=True)

    # 修.五第1點：讓prepare_factors()內部呼叫的股利率因子改用uncapped
    # 資料——見_dividend_yield_ttm_cash_uncapped()docstring，這是
    # module-level bare name monkeypatch，必須在下面的載入迴圈開始「之前」
    # 生效，否則前面已經跑掉的呼叫依然會用到capped版本。
    factors_mod._dividend_yield_ttm_cash = _dividend_yield_ttm_cash_uncapped
    print("已monkeypatch factors._dividend_yield_ttm_cash -> uncapped版本"
          "（修.五第1點，見audit_h1_dividend_pit_lag.py的診斷證據）", flush=True)

    # ── 3. 載入普通股宇宙的uncapped還原股價+因子 ──
    data: dict[str, pd.DataFrame] = {}
    n_price_fail, n_factor_fail = 0, 0
    factor_fail_reasons: dict[str, int] = {}  # 修.五第3點+乾.一G3：失敗原因分類，額度類不計入這裡（往上拋中止）
    for i, sid in enumerate(common_ids):
        px = uncapped_adjusted_price_series(sid, LOOKBACK_START)
        if px.empty or len(px) < 200:
            n_price_fail += 1
            continue
        try:
            d = prepare_factors(sid, px, market_df, LOOKBACK_START)
        except Exception as e:  # noqa: BLE001
            # 修.五第3點：額度類錯誤(FinMind 402/封鎖冷卻)一律往上拋並中止，
            # 不得計入n_factor_fail——舊版的裸except Exception會把
            # prepare_factors()內部因子區塊刻意往上拋的額度錯誤（見
            # factors.py::_is_quota_error()docstring）當成「這一檔資料剛好
            # 缺」的一般失敗吞掉，讓額度用盡後續跑的資料看起來是「乾淨的
            # 全部成功」，其實只是安靜漏掉沒抓到的部分。
            if _is_quota_error(e):
                print(f"\n額度類錯誤，中止載入迴圈（第{i+1}檔 {sid}）：{e}", flush=True)
                raise
            n_factor_fail += 1
            reason = f"{type(e).__name__}: {str(e)[:120]}"
            factor_fail_reasons[reason] = factor_fail_reasons.get(reason, 0) + 1
            continue
        data[sid] = d
        if (i + 1) % 50 == 0:
            print(f"  進度 {i+1}/{len(common_ids)}（累計可用 {len(data)} 檔）", flush=True)
    print(f"資料載入完成：可用{len(data)}檔（價格不足/失敗{n_price_fail}檔、factor失敗{n_factor_fail}檔）"
          f"——holdout期完全無yfinance可用（該路徑同樣被cap在VAL_END），純FinMind覆蓋率"
          f"天生低於考.一的2007-2014段，如實記錄。", flush=True)
    if factor_fail_reasons:
        print(f"  factor失敗原因分類：{factor_fail_reasons}", flush=True)

    industry_map = load_industry_map()
    liquidity = {sid: pbv2._liquidity_proxy_series(d) for sid, d in data.items()}

    # ── 4. 找出資料實際涵蓋到的最新日（不是今天，FinMind latest本身有落後） ──
    all_dates = sorted({d for df_ in data.values() for d in df_["date"].tolist()})
    period_end = max(dt for dt in all_dates if dt >= PERIOD_START) if any(dt >= PERIOD_START for dt in all_dates) else None
    if period_end is None:
        raise RuntimeError("資料完全沒有涵蓋到2025-01-01之後，H.一無法執行")
    print(f"\n資料實際涵蓋的最新日 = {period_end}（不是今天，FinMind本身有發布落後）", flush=True)

    if gates_only:
        print("\n=== 乾.一/乾.二：G1~G5資料診斷（只印計數與日期，不含任何報酬/IR/MDD）===", flush=True)

        # G1：額度相關失敗=0——迴圈設計上額度錯誤會立即raise中止整支腳本
        # （修.五第3點），能執行到這裡代表本次執行過程中沒有遇到任何額度
        # 錯誤，不是「遇到了但吞掉沒算」。
        g1_quota_fail = 0
        print(f"G1 額度相關失敗 = {g1_quota_fail}（能執行到這一行本身就是證據——"
              f"遇到額度錯誤會立即raise中止整支腳本，不會落到這裡）", flush=True)

        # 乾.二背景：既有G2呼叫的是「已被monkeypatch的函式本身」，即使patch
        # 沒生效（呼叫到的還是舊的capped版）G2也會回報0——它只證明「事件
        # 存在」，不證明「這個事件真的進了prepare_factors()吐出來的d」。
        # 拆成G2a(快取新鮮度)/G2b(patch是否真的生效)/G2c(G2b有沒有辨別力)
        # 三層，只有三層都過才算真的驗證到「holdout路徑吃到uncapped股利」。
        g2a_mismatches = []  # 快取新鮮度：股價最後日 < 除息日
        g2b_mismatches = []  # patch生效檢查：d裡實際觀察到的ttm跟uncapped期望值對不上
        g2c_effective = []   # 檢定力對照：X真的跟VAL_END前的舊值不同的檔數
        g2_checked = 0
        for sid, d in data.items():
            div_pit = factors_mod._dividend_yield_ttm_cash(sid, LOOKBACK_START)
            if div_pit.empty:
                continue
            ex_dates_2025 = div_pit[(div_pit["pit_date"] >= "2025-01-01") & (div_pit["pit_date"] <= period_end)]
            if ex_dates_2025.empty:
                continue
            g2_checked += 1
            latest_row = ex_dates_2025.sort_values("pit_date").iloc[-1]
            E = latest_row["pit_date"]
            X = float(latest_row["ttm_cash_dividend"])
            last_data_date = d["date"].max()

            # G2a：跟乾.一原版一樣，股價資料本身有沒有涵蓋到除息日。
            if last_data_date < E:
                g2a_mismatches.append({"stock_id": sid, "latest_ex_date": str(E),
                                        "last_data_date": str(last_data_date)})
                continue  # 裁示明文：股價最後日<E的股票跳過G2b（已在G2a列出）

            # G2b：在d中取第一個date>=E的列，比對obs=f_dividend_yield_ttm×close
            # 是否等於uncapped事件本身算出的X——這是真正檢查patch有沒有讓
            # prepare_factors()的輸出改變的地方，不是再呼叫一次同一個函式。
            on_or_after = d[d["date"] >= E].sort_values("date")
            if on_or_after.empty:
                g2b_mismatches.append({"stock_id": sid, "E": str(E), "X": X, "obs": None,
                                        "reason": "d中找不到date>=E的列（不應該發生，因為last_data_date>=E已通過）"})
                continue
            row0 = on_or_after.iloc[0]
            close0 = row0.get("close")
            fdy0 = row0.get("f_dividend_yield_ttm")
            obs = (float(fdy0) * float(close0)) if pd.notna(fdy0) and pd.notna(close0) else None
            is_mismatch = (obs is None) or (abs(obs - X) > 1e-6 * max(1.0, abs(X)))
            if is_mismatch:
                g2b_mismatches.append({"stock_id": sid, "E": str(E), "X": X, "obs": obs})

            # G2c：檢定力對照——同一檔股票在2024-12-31(或之前最後一個交易日)
            # 的ttm值，是不是真的跟X不同。全部都相同就代表G2b測不出patch
            # 有沒有生效（capped/uncapped剛好算出一樣的值，或patch根本沒動）。
            pre_2025 = d[d["date"] <= "2024-12-31"].sort_values("date")
            if not pre_2025.empty:
                row_pre = pre_2025.iloc[-1]
                fdy_pre = row_pre.get("f_dividend_yield_ttm")
                close_pre = row_pre.get("close")
                pre_ttm = (float(fdy_pre) * float(close_pre)) if pd.notna(fdy_pre) and pd.notna(close_pre) else None
                if pre_ttm is None or abs(pre_ttm - X) > 1e-6 * max(1.0, abs(X)):
                    g2c_effective.append(sid)

        print(f"G2a 快取新鮮度：檢查了{g2_checked}檔有2025+除息紀錄的可用股票，"
              f"不一致{len(g2a_mismatches)}檔（股價最後日 < 除息日）", flush=True)
        if g2a_mismatches:
            print(f"  G2a不一致明細：{g2a_mismatches}", flush=True)
        print(f"G2b patch生效檢查：不一致{len(g2b_mismatches)}檔"
              f"（d實際觀察值obs跟uncapped期望值X對不上，須=0）", flush=True)
        if g2b_mismatches:
            print(f"  G2b不一致明細：{g2b_mismatches}", flush=True)
        print(f"G2c 檢定力對照：{len(g2c_effective)}檔的X真的不同於VAL_END前的舊值"
              f"（須>0，=0代表G2b沒有辨別力，測不出patch有沒有生效）", flush=True)

        # G3：可用檔數/價格失敗檔數/因子失敗檔數（附失敗原因分類）
        print(f"G3 可用檔數={len(data)}　價格失敗檔數={n_price_fail}　"
              f"因子失敗檔數={n_factor_fail}（原因分類：{factor_fail_reasons or '無'}）", flush=True)

        # G4：資料實際涵蓋到的最新交易日
        print(f"G4 資料實際涵蓋到的最新交易日 = {period_end}", flush=True)

        # G5：股價截止日分佈——用all_dates（本次載入的全部股票聯集出的交易日
        # 曆，第4步已算過）找period_end往前數10個「觀察到的交易日」的位置，
        # 早於這個位置的股票視為「最後日明顯落後period_end」。
        last_dates_per_stock = {sid: d["date"].max() for sid, d in data.items()}
        sorted_last_dates = sorted(last_dates_per_stock.values())
        g5_min = sorted_last_dates[0]
        g5_median = sorted_last_dates[len(sorted_last_dates) // 2]
        g5_max = sorted_last_dates[-1]
        try:
            period_end_idx = all_dates.index(period_end)
            cutoff_idx = max(0, period_end_idx - 10)
            g5_cutoff_date = all_dates[cutoff_idx]
        except ValueError:
            g5_cutoff_date = period_end  # 理論上period_end一定在all_dates裡（它本身就是從all_dates算出來的）
        g5_stale = [{"stock_id": sid, "last_data_date": str(dt)}
                    for sid, dt in last_dates_per_stock.items() if dt < g5_cutoff_date]
        g5_stale_pct = (len(g5_stale) / len(data) * 100.0) if data else 0.0
        print(f"G5 股價截止日分佈：最小={g5_min}　中位數={g5_median}　最大={g5_max}"
              f"　10個交易日前的門檻日={g5_cutoff_date}"
              f"　落後檔數={len(g5_stale)}/{len(data)}（{g5_stale_pct:.1f}%，須≤5%）", flush=True)
        if g5_stale:
            print(f"  G5落後清單：{g5_stale}", flush=True)

        gates_pass = (
            g1_quota_fail == 0
            and len(g2a_mismatches) == 0
            and len(g2b_mismatches) == 0
            and len(g2c_effective) > 0
            and g5_stale_pct <= 5.0
        )
        gates_out = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "G1_quota_related_failures": g1_quota_fail,
            "G2a_cache_freshness": {"checked": g2_checked, "mismatches": g2a_mismatches},
            "G2b_patch_effective_check": {"mismatches": g2b_mismatches},
            "G2c_detection_power": {"n_effective": len(g2c_effective), "stock_ids": g2c_effective},
            "G3_counts": {"usable": len(data), "price_fail": n_price_fail,
                          "factor_fail": n_factor_fail, "factor_fail_reasons": factor_fail_reasons},
            "G4_latest_covered_trading_date": period_end,
            "G5_price_cutoff_distribution": {
                "min": str(g5_min), "median": str(g5_median), "max": str(g5_max),
                "cutoff_10_trading_days_before_period_end": str(g5_cutoff_date),
                "n_stale": len(g5_stale), "n_total": len(data), "stale_pct": round(g5_stale_pct, 2),
                "stale_list": g5_stale,
            },
            "gates_pass": gates_pass,
            "note": "乾.一/乾.二：只做資料診斷，不含任何策略結果數字（報酬/IR/MDD）。"
                    "gates_pass為True僅代表資料層面可以放行，仍須由Cowork核對後"
                    "才能執行正式回測，本腳本本身不會自動接著跑。",
        }
        GATES_JSON.parent.mkdir(parents=True, exist_ok=True)
        GATES_JSON.write_text(json.dumps(gates_out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"\n已寫入 {GATES_JSON}", flush=True)
        print(f"\n**乾.一/乾.二結果：{'gates_pass=True，資料層面可以放行' if gates_pass else 'gates_pass=False，尚不可放行'}**"
              f"——停在這裡，等Cowork核對後再另行放行正式回測。", flush=True)
        return gates_out

    # ── 5. 股票部位：dividend_yield_portfolio_v1，參數與考.一完全相同 ──
    signal_fn = div_mod.make_signal_fn(industry_map, liquidity)
    cfg = BacktestConfig(start_date=PERIOD_START, end_date=period_end,
                          max_positions=div_mod.TOP_N, rebalance_every_n_days=div_mod.REBALANCE_DAYS,
                          commission_discount=0.18, instrument_type="normal",
                          book_name="holdout_2025_dividend_stock_leg")
    print(f"\n即將執行H.一正式回測——此行以後印出的任何統計數字，依裁示視為\n已消耗這次only-once資格，不得重跑。", flush=True)
    result = run_backtest(signal_fn, data, market_df, cfg)
    stock_eq = result.equity_curve

    # ── 6. 帳戶層級70/30 ──
    rf_monthly = load_risk_free_rate_series()
    account_eq = simulate_account(stock_eq, rf_monthly, STOCK_WEIGHT, rebalance_every_n_days=REBALANCE_DAYS)

    # ── 7. 統計量 ──
    ir_info = dimson_ir(stock_eq, "HOLDOUT_2025_STOCK_LEG")
    alpha_info = pbv2.alpha_significance(stock_eq, market_df)
    stock_return_pct = result.total_return_pct
    stock_mdd_pct = compute_mdd(stock_eq["equity"])
    bh_0050 = pbv2.buy_and_hold_index_pct(market_df, PERIOD_START, period_end)

    account_return_pct = float(account_eq["equity"].iloc[-1] / account_eq["equity"].iloc[0] - 1) * 100
    account_mdd_pct = compute_mdd(account_eq["equity"])

    gate1_pass = bool(ir_info.get("ok") and ir_info["ir_annualized"] > 0)
    gate2_pass = bool(account_mdd_pct == account_mdd_pct and account_mdd_pct > -50.0)
    overall_pass = gate1_pass and gate2_pass

    # 逐月報酬（股票部位、帳戶）
    stock_eq_i = stock_eq.set_index("date")["equity"]
    acct_eq_i = account_eq.set_index("date")["equity"]
    months = sorted({d[:7] for d in stock_eq["date"].tolist()})
    monthly_rows = []
    for ym in months:
        s_w = stock_eq_i[stock_eq_i.index.str.startswith(ym)]
        a_w = acct_eq_i[acct_eq_i.index.str.startswith(ym)]
        s_ret = float(s_w.iloc[-1] / s_w.iloc[0] - 1) * 100 if len(s_w) >= 2 else None
        a_ret = float(a_w.iloc[-1] / a_w.iloc[0] - 1) * 100 if len(a_w) >= 2 else None
        monthly_rows.append({"month": ym, "stock_leg_return_pct": round(s_ret, 2) if s_ret is not None else None,
                              "account_return_pct": round(a_ret, 2) if a_ret is not None else None})

    print(f"\n========== H.一 結果 ==========", flush=True)
    print(f"  期間：{PERIOD_START} ~ {period_end}（約{len(months)}個月）", flush=True)
    print(f"  股票部位報酬={stock_return_pct:+.2f}%  0050含息總報酬={bh_0050:+.2f}%  trades={result.n_trades}", flush=True)
    print(f"  股票部位IR(年化)={ir_info.get('ir_annualized')}  beta_dimson={alpha_info['beta']:+.3f}  "
          f"alpha年化p值={alpha_info['alpha_pvalue']}（照報，不作判準）", flush=True)
    print(f"  股票部位MDD={stock_mdd_pct:.2f}%", flush=True)
    print(f"  帳戶(70/30)報酬={account_return_pct:+.2f}%  帳戶MDD={account_mdd_pct:.2f}%", flush=True)
    print(f"  判準①IR方向>0：{'PASS' if gate1_pass else 'FAIL'}", flush=True)
    print(f"  判準②帳戶MDD>-50%：{'PASS' if gate2_pass else 'FAIL'}", flush=True)
    print(f"  **綜合判定：{'PASS' if overall_pass else 'FAIL'}**", flush=True)

    out = {
        "generated_for": "H.一（2026-09-26裁示，TRIALS_LEDGER#400）",
        "period": [PERIOD_START, period_end], "n_months": len(months),
        "n_common_stock_universe": len(common_ids), "n_usable_data": len(data),
        "stock_leg": {
            "return_pct": round(stock_return_pct, 2), "mdd_pct": round(stock_mdd_pct, 2),
            "n_trades": result.n_trades,
            "ir_annualized": ir_info.get("ir_annualized"), "ir_daily": ir_info.get("ir_daily"),
            "beta_dimson": alpha_info["beta"], "alpha_ann_pct": alpha_info["alpha_ann_pct"],
            "alpha_pvalue_reported_not_gating": alpha_info["alpha_pvalue"],
            "n_obs": alpha_info["n_days"],
            "benchmark_0050_return_pct": round(bh_0050, 2),
        },
        "account_70_30": {
            "return_pct": round(account_return_pct, 2), "mdd_pct": round(account_mdd_pct, 2),
        },
        "reference_2007_2014_account_7030_mechanically_computed_not_a_gate": reference_2007_2014,
        "monthly_table": monthly_rows,
        "gates": {"gate1_ir_direction_positive": gate1_pass, "gate2_account_mdd_over_neg50": gate2_pass,
                  "overall_verdict": "PASS" if overall_pass else "FAIL"},
        "power_caveat": "期間約21個月，事前宣告檢定力不足以證明顯著，本結果定位為一致性檢查，不是統計顯著性證明。",
        "data_limitation": "holdout期完全無yfinance可用（yf_price_client.py同樣被cap在VAL_END），"
                            "純FinMind覆蓋率天生低於考.一的2007-2014段。",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)
    return out


def _self_test_allowlist_passthrough() -> None:
    """守.一自我測試專用（2026-09-26）：從本檔案（ALLOWED_HOLDOUT_READERS
    允許清單內）直接呼叫assert_no_holdout_leakage()，餵一筆VAL_END之後的
    假資料。因為呼叫堆疊的最上層frame就是這支腳本自己，在holdout已被
    #400合法解鎖過的前提下，這裡應該no-op通過、不得raise。

    不呼叫真正的main()（那會觸發完整的uncapped資料載入，成本高且會被
    FinMind冷卻卡住），只單獨測「呼叫者身分是否被正確識別為允許清單內」
    這一件事，這是#400腳本自身的holdout存取權限有沒有被誤傷的唯一
    需要驗證的點。
    """
    df = pd.DataFrame({"date": ["2025-06-01"]})
    holdout.assert_no_holdout_leakage(df, context="守.一自我測試：#400腳本本身呼叫")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gates-only", action="store_true",
                         help="乾.一：只跑G1~G4資料診斷，印完就結束，不執行正式回測，"
                              "不印任何報酬/IR/MDD（總司令2026-09-26裁示【緊急：H.一"
                              "立即暫停重跑，修正兩個bug後先做乾跑檢查】）")
    args = parser.parse_args()
    main(gates_only=args.gates_only)
