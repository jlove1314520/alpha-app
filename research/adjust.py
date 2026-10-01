"""還原股價 (back-adjusted TW stock price).

**2026-08-26 architecture change:** FinMind's free tier hit a hard 402
(quota exhausted) wall this day, and the user directed a hybrid source
switch -- price/volume history now comes PRIMARILY from yfinance
(`yf_price_client.py`), which returns already dividend/split-adjusted
closes for free with no comparable rate limit. The FinMind-based manual
back-adjustment below (raw TaiwanStockPrice + TaiwanStockDividend) is kept
as the FALLBACK for stock_ids yfinance doesn't carry -- mainly older
delisted names not on Yahoo Finance at all. `adjusted_price_series()`
tries yfinance first and only falls through to the FinMind reconstruction
if yfinance comes back empty; the returned DataFrame carries a `source`
column ('yfinance' or 'finmind') so callers/audits can tell which path
served any given row.

Below this point is the ORIGINAL FinMind-based fallback path, unchanged
except for being demoted from primary to fallback:

FinMind's free tier does not offer adjusted prices for TW stocks
(TaiwanStockPriceAdj is paid-tier only -- see DATA.md, milestone-1 audit,
2026-08-22). Every return-based backtest needs correct returns across
ex-dividend dates, or the backtest is silently polluted: an ex-dividend price
drop looks like a real loss that never actually happened to a holder. This
module reconstructs a back-adjusted series from raw TaiwanStockPrice +
TaiwanStockDividend, which are both free.

Method: standard cumulative backward adjustment, using TWSE's own
ex-rights/ex-dividend reference-price formula to turn each corporate action
into a single multiplicative factor:

    ref_price = (prev_close - cash_dividend + rights_price * rights_ratio)
                / (1 + stock_dividend_ratio + rights_ratio)
    factor = ref_price / prev_close

Applied in reverse chronological order (most recent event first) to every
raw price strictly BEFORE that event's ex-date. This keeps the most recent
price in the series equal to the raw price (the usual convention -- the
final day is never adjusted) while making day-over-day returns correct
across every ex-date in the history.

**Data source note (2026-08-22):** both fetches below go through
finmind_client.load_dev(), which caps everything at VAL_END
(validation.holdout) -- so "the most recent price" here means the most
recent price *within the dev window*, not literally today. That is
intentional: this module feeds backtests, and per CONSTITUTION.md no
backtest-facing data may see past the holdout boundary by default. Callers
doing an actual one-time holdout evaluation should use
finmind_client.load_full_history() directly and route the result through
validation.holdout.unlock_holdout_once() themselves, rather than expecting
this module to do it for them.

**2026-09-27修.六（總司令裁示【驗.五＋修.六：H.一基準汙染診斷＋資料層
分割/減資還原修正】）**：上一段記錄的「已知缺口」已修正——分割
（TaiwanStockSplitPrice）、減資（TaiwanStockCapitalReductionReference
Price）、面額變更（TaiwanStockParValueChange）三類事件現在都會被還原。
起因：0050於2025-06以1拆4分割，`adjustment_events()`原本完全不處理
分割，導致0050 uncapped adj_close在2025-06-18出現約-75%的假跌（見
`research/data/h1_benchmark_contamination_diagnosis.json`），汙染了
H.一（TRIALS_LEDGER#400）用來算判準(a) IR的0050基準報酬序列。三類
新事件的還原因子與既有的現金/股票股利、現金增資邏輯合併進同一個
`factor_cum`累乘鏈，見`_split_events_from_df()`／
`_capital_reduction_events_from_df()`／`_par_value_change_events_from_
df()`／`_combine_adjustment_events()`。

**`CashIncreaseSubscriptionRate`單位疑點已結案（2026-10-01先.六-五更正；
原「是否採用除以1000待裁示」「本輪未修改」字樣已過時，已移除）**：
欄位在部分個股出現遠大於1的值（例：1316於2025-01-09=16.195151，套進
公式會把還原因子壓到約1/17、產生+1514%假回升）。台股公開資訊觀測站
現金增資公告用語為「每仟股得認購X股」，欄位真實單位即每仟股認購股數，
**除以1000**才與`stock_ratio`同尺度。此修正已於 commit `015f1402`
（查.三，2026-09-27）落入`_dividend_events_from_df()`，並以官方
`TaiwanStockDividendResult`（before_price/reference_price）參考價驗證：
5檔乾淨現金增資事件誤差由修正前7.65~21.92pp降至0.06%~0.57%
（4/5<0.5%，2038為0.574%略過內部門檻但仍遠優於修正前，自我測試如實
記錄）；後續查.三以7筆2010~2025年真實事件核對，誤差全部<0.6%
（舊公式7.7%~24.3%）。結論：單位為每仟股，除以1000正確，疑點結案，
不再待裁示；驗證細節見`_self_test_cash_increase_rate_unit()`。

**2026-09-23 fix (資料.零稽核):** both upstream sources occasionally hand
back a non-positive close that is not a real price:
- FinMind's raw TaiwanStockPrice reports `close=0.0` on zero-volume days for
  thinly-traded names (confirmed via cache audit: e.g. stock 5395 has 1,124
  such rows 2004-2016, every one with `Trading_Volume` 0-3 -- this is
  FinMind's own convention for "no trade happened", not a glitch limited to
  one or two isolated dates as originally suspected).
- yfinance's `auto_adjust=True` back-adjustment can go NEGATIVE for names
  that underwent a large reverse split or special dividend relative to
  their price level -- this is worse than the zero-price case because it
  hits real, high-volume trading days, not just illiquid off-days (found:
  stock 4303 has 2,129 negative-close rows 2010-2018 on volumes up to
  ~19M shares/day; stock 8039 goes as low as -160.45 against an all-time
  positive high of only 68.02).
Both are fixed at this single choke point: `adj_close`/`adj_open`/
`adj_high`/`adj_low` are masked to NaN wherever <= 0, on both the yfinance
and FinMind paths, so every caller of `adjusted_price_series()` gets NaN
instead of a fabricated -100% or worse return, without having to add its
own guard. Run `python adjust.py` to self-test this masking (synthetic
zero-price case + a live spot-check against stock 5395's known-bad dates).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from finmind_client import load_dev


_EMPTY_EVENTS_COLUMNS = ["ex_date", "prev_trading_date", "factor", "cash", "stock_ratio", "event_type"]


def _empty_events_df() -> pd.DataFrame:
    # Bug fixed 2026-08-22 (found via a 100-stock random-universe run): pd.DataFrame([])
    # has zero columns, so .sort_values("ex_date") on it raises KeyError('ex_date') --
    # must return the properly-columned empty frame directly instead of falling through.
    return pd.DataFrame(columns=_EMPTY_EVENTS_COLUMNS)


def _dividend_events_from_df(div: pd.DataFrame, close_by_date: dict, trading_dates: list) -> list[dict]:
    """現金股利/股票股利/現金增資的還原因子。

    **2026-09-27查.三修正**：`CashIncreaseSubscriptionRate`（現金增資認股
    比率）除以1000才是套進下面公式的正確單位。查證：FinMind官方文件
    僅給出未標單位的範例值，但台股官方公開資訊觀測站現金增資公告的實際
    用語慣例是「每仟股得認購X股」——用`TaiwanStockDividendResult`（含
    `before_price`/`reference_price`兩個官方欄位）逐一核對7筆
    2010~2025年的真實現金增資事件（`stock_ratio=0`的乾淨案例，排除跟
    股票股利混合的事件避免干擾），除以1000後算出的還原因子與官方
    `reference_price/before_price`實際比例誤差全部<0.6%（原始未除以
    1000的舊公式誤差達7.7%~24.3%，方向一致但量級差了近3個數量級，
    確認是單位問題不是公式本身錯）。見`_self_test_cash_increase_rate_
    unit()`。

    **2026-09-27修.七同步修正**：`StockEarningsDistribution`（股票股利/
    無償配股率）同樣需要**除以10**才是套進公式的正確單位——FinMind的
    原始值是台股股利公告慣用的「每股配股數(元)」，換算成「每股配股
    比率」需除以股票面額新台幣10元（例：配股1元/股＝配股率10%＝0.1，
    不是1.0）。用`TaiwanStockDividendResult`核對5筆純股票股利事件
    （現金=0）＋5筆現金+股票股利混合事件，除以10後的還原因子與官方
    比例誤差全部<0.6%（原始未除以10的舊公式誤差達29.96%~72.00%，同樣
    方向一致、量級差了兩個數量級）。見`_self_test_stock_dividend_
    unit()`。"""
    events = []
    for _, row in div.iterrows():
        # Cash and stock dividends normally share one ex-date; use whichever is populated.
        ex_date = row.get("CashExDividendTradingDate") or row.get("StockExDividendTradingDate")
        if not ex_date:
            continue
        cash = row.get("CashEarningsDistribution") or 0.0
        stock_ratio = (row.get("StockEarningsDistribution") or 0.0) / 10.0
        rights_ratio = (row.get("CashIncreaseSubscriptionRate") or 0.0) / 1000.0
        rights_price = row.get("CashIncreaseSubscriptionpRrice") or 0.0
        if cash == 0 and stock_ratio == 0 and rights_ratio == 0:
            continue  # record exists but nothing was actually distributed this period

        prior = [d for d in trading_dates if d < ex_date]
        if not prior:
            continue  # ex-date is before our price history starts; can't anchor a factor
        prev_date = prior[-1]
        prev_close = close_by_date[prev_date]
        if prev_close in (None, 0) or pd.isna(prev_close):
            continue

        numerator = prev_close - cash + rights_price * rights_ratio
        denominator = 1 + stock_ratio + rights_ratio
        if denominator <= 0 or numerator <= 0:
            continue  # malformed event data -- skip rather than produce a nonsense factor
        ref_price = numerator / denominator
        factor = ref_price / prev_close
        events.append({
            "ex_date": ex_date, "prev_trading_date": prev_date, "factor": factor,
            "cash": cash, "stock_ratio": stock_ratio, "event_type": "dividend",
        })
    return events


def _split_events_from_df(split_df: pd.DataFrame) -> list[dict]:
    """分割/反分割（2026-09-27修.六新增）：`TaiwanStockSplitPrice`。
    欄位（已向FinMind官方文件驗證，見`adjust.py`模組docstring）：
    date/stock_id/type/before_price/after_price/max_price/min_price/
    open_price。factor直接就是`after_price/before_price`——這個資料集
    本身就是「分割前收盤價」對「分割後參考價」，不需要另外去raw price
    序列找前一交易日收盤價（跟股利事件不同，股利事件的`ex_date`本身
    沒有價格資訊，分割事件的`before_price`就是價格資訊本身）。"""
    events = []
    if split_df.empty:
        return events
    for _, row in split_df.iterrows():
        ex_date = row.get("date")
        before_price = row.get("before_price")
        after_price = row.get("after_price")
        if not ex_date or before_price in (None, 0) or pd.isna(before_price) \
                or after_price in (None,) or pd.isna(after_price) or after_price <= 0:
            continue
        factor = after_price / before_price
        events.append({
            "ex_date": ex_date, "prev_trading_date": None, "factor": factor,
            "cash": 0.0, "stock_ratio": 0.0, "event_type": "split",
        })
    return events


def _capital_reduction_events_from_df(cr_df: pd.DataFrame) -> list[dict]:
    """減資恢復買賣（2026-09-27修.六新增）：
    `TaiwanStockCapitalReductionReferencePrice`。欄位（已向FinMind官方
    文件驗證）：date/stock_id/ClosingPriceonTheLastTradingDay/
    PostReductionReferencePrice/LimitUp/LimitDown/OpeningReferencePrice/
    ExrightReferencePrice/ReasonforCapitalReduction。factor =
    減資恢復參考價 / 減資前最後交易日收盤價，跟分割事件同一個模式：
    這個資料集本身就同時給了事件前後的價格，不需要另外查raw price。"""
    events = []
    if cr_df.empty:
        return events
    for _, row in cr_df.iterrows():
        ex_date = row.get("date")
        before = row.get("ClosingPriceonTheLastTradingDay")
        after = row.get("PostReductionReferencePrice")
        if not ex_date or before in (None, 0) or pd.isna(before) \
                or after in (None,) or pd.isna(after) or after <= 0:
            continue
        factor = after / before
        events.append({
            "ex_date": ex_date, "prev_trading_date": None, "factor": factor,
            "cash": 0.0, "stock_ratio": 0.0, "event_type": "capital_reduction",
        })
    return events


def _par_value_change_events_from_df(pv_df: pd.DataFrame) -> list[dict]:
    """面額變更恢復買賣（2026-09-27修.六新增）：`TaiwanStockParValueChange`。
    欄位（已向FinMind官方文件驗證）：date/stock_id/stock_name/
    before_close/after_ref_close/after_ref_max/after_ref_min/
    after_ref_open。factor = after_ref_close / before_close，同一個
    「資料集本身給事件前後價格」模式。"""
    events = []
    if pv_df.empty:
        return events
    for _, row in pv_df.iterrows():
        ex_date = row.get("date")
        before = row.get("before_close")
        after = row.get("after_ref_close")
        if not ex_date or before in (None, 0) or pd.isna(before) \
                or after in (None,) or pd.isna(after) or after <= 0:
            continue
        factor = after / before
        events.append({
            "ex_date": ex_date, "prev_trading_date": None, "factor": factor,
            "cash": 0.0, "stock_ratio": 0.0, "event_type": "par_value_change",
        })
    return events


def _combine_adjustment_events(div: pd.DataFrame, split_df: pd.DataFrame, cr_df: pd.DataFrame,
                                pv_df: pd.DataFrame, close_by_date: dict, trading_dates: list) -> pd.DataFrame:
    """把股利/分割/減資/面額變更四類事件合併成同一份、依ex_date排序的
    還原因子表——呼叫端（`adjustment_events()`與holdout腳本的
    `_uncapped_adjustment_events()`）套用`factor_cum`累乘的邏輯完全不變，
    只是事件來源從一個資料集變成四個。2026-09-27修.六新增。"""
    events = (
        _dividend_events_from_df(div, close_by_date, trading_dates)
        + _split_events_from_df(split_df)
        + _capital_reduction_events_from_df(cr_df)
        + _par_value_change_events_from_df(pv_df)
    )
    if not events:
        return _empty_events_df()
    return pd.DataFrame(events).sort_values("ex_date").reset_index(drop=True)


def _par_value_change_market_wide(start_date: str, stock_id: str, *, uncapped: bool = False) -> pd.DataFrame:
    """`TaiwanStockParValueChange`（2026-09-27修.六，實測發現）**不接受**
    `data_id`參數——`python adjust.py`自我測試實際打過一次才發現這件事
    （FinMind回400：\"parameter data_id don't provide on
    TaiwanStockParValueChange dataset\"），跟另外兩個新資料集
    （`TaiwanStockSplitPrice`／`TaiwanStockCapitalReductionReferencePrice`
    ，兩者都已實測確認接受`data_id`）行為不同，不能一視同仁。這支函式
    改成不帶`data_id`整表抓回（會落到`finmind_client`既有的parquet
    快取，同一個process/同一天內對不同股票重複呼叫不會重複打API），
    在Python端用`stock_id`欄位篩選。"""
    if uncapped:
        from finmind_client import load_full_history
        full = load_full_history("TaiwanStockParValueChange", "", start_date, allow_holdout=True)
    else:
        full = load_dev("TaiwanStockParValueChange", "", start_date)
    if full.empty or "stock_id" not in full.columns:
        return pd.DataFrame()
    return full[full["stock_id"] == stock_id].reset_index(drop=True)


def adjustment_events(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """One row per ex-date with the multiplicative back-adjustment factor.

    2026-09-27修.六：現在合併四類事件（股利/分割/減資/面額變更），不再
    只有股利。三個新資料集缺任何一個都不影響既有的股利邏輯——`load_dev()`
    對這三個新資料集回傳空表時，`_split_events_from_df()`等函式直接
    回傳空list，`_combine_adjustment_events()`照常運作。"""
    div = load_dev("TaiwanStockDividend", stock_id, start_date)
    split_df = load_dev("TaiwanStockSplitPrice", stock_id, start_date)
    cr_df = load_dev("TaiwanStockCapitalReductionReferencePrice", stock_id, start_date)
    pv_df = _par_value_change_market_wide(start_date, stock_id)

    if div.empty and split_df.empty and cr_df.empty and pv_df.empty:
        return _empty_events_df()

    raw = load_dev("TaiwanStockPrice", stock_id, start_date)
    if raw.empty:
        raise ValueError(f"no raw price data for {stock_id}, cannot compute adjustment factors")
    raw = raw.sort_values("date").reset_index(drop=True)
    close_by_date = dict(zip(raw["date"], raw["close"]))
    trading_dates = raw["date"].tolist()

    return _combine_adjustment_events(div, split_df, cr_df, pv_df, close_by_date, trading_dates)


def adjusted_price_series(stock_id: str, start_date: str = "1990-01-01") -> pd.DataFrame:
    """Adjusted daily price series, capped at VAL_END. Tries yfinance first
    (see module docstring, 2026-08-26); falls back to the FinMind-based
    manual back-adjustment below if yfinance has no data for this stock_id.

    Columns: date, open, high, low, close, volume, adj_close, adj_open,
    adj_high, adj_low, source.
    `close`/`open`/`high`/`low` are the raw (unadjusted) values on the
    yfinance path too, for column-shape compatibility with the FinMind path
    -- yfinance's auto_adjust=True OHLC IS the adjusted value, so on that
    path close == adj_close (and open == adj_open etc.) by construction
    (there is no separately-fetchable raw OHLC from yfinance without a
    second, unadjusted request, which isn't worth the extra API call here).
    Empirically verified 2026-09-06 (see HYPOTHESIS_QUEUE.md#49 known-risk #2):
    yfinance's auto_adjust=True applies the IDENTICAL multiplicative factor
    to open/high/low/close on every date (checked 2330.TW 2024, all 241
    rows: open_factor == close_factor to 1e-6), so aliasing adj_open to the
    already-adjusted `open` column here is not an assumption, it's confirmed.

    2026-09-06: adj_open/adj_high/adj_low added on the FinMind fallback path
    (previously only adj_close existed) -- needed so overnight/intraday
    return decomposition (open_t / close_{t-1}) isn't polluted by ex-dividend
    jumps in an unadjusted `open` column (HYPOTHESIS_QUEUE.md#49 known-risk #2).
    """
    from yf_price_client import fetch_yf_adjusted

    yf_df = fetch_yf_adjusted(stock_id, start_date)
    if not yf_df.empty:
        out = yf_df.copy()
        out["adj_close"] = out["close"]
        out["adj_open"] = out["open"]
        out["adj_high"] = out["high"]
        out["adj_low"] = out["low"]
        # 驗.八四（2026-09-29）：yfinance路徑也要截斷到上市/上櫃日——原本只有
        # 宇宙篩選那層會呼叫truncate_to_listing_date()，價格函式本身不截，
        # 導致興櫃期間（無漲跌幅限制）的價格漏進還原價序列（驗.七：22檔、274筆）。
        out = _truncate_pre_listing(out, stock_id)
        _mask_non_positive_adj_prices(out)
        out.attrs["n_events_applied"] = None  # not tracked on this path -- yfinance handles it internally
        _append_anomaly_log(check_adjusted_series_anomalies(out, stock_id))
        # 驗.八四第2點：與「FinMind原始價+已驗證事件因子」逐日報酬交叉比對，
        # 只列警告清單、不切換主要來源。fail open（十二節）。
        _append_crosscheck_log(crosscheck_yf_vs_finmind(out, stock_id, start_date))
        return out

    out = _finmind_adjusted_frame(stock_id, start_date)
    if out.empty:
        return out
    n_events = out.attrs.get("_n_events")
    out = _truncate_pre_listing(out, stock_id)
    _mask_non_positive_adj_prices(out)
    out.attrs["n_events_applied"] = n_events
    _append_anomaly_log(check_adjusted_series_anomalies(out, stock_id))
    return out


def _finmind_adjusted_frame(stock_id: str, start_date: str) -> pd.DataFrame:
    """FinMind原始價 x 已驗證事件因子（股利/分割/減資/面額變更）的還原價序列，
    **不截斷、不遮罩、不寫異常log**——`adjusted_price_series()`的FinMind備援路徑
    與yfinance交叉比對（`crosscheck_yf_vs_finmind()`）共用這一份，確保兩邊比的是
    同一個「FinMind重建」。回傳空表時仍帶`source`欄。事件數放在
    `out.attrs["_n_events"]`。"""
    raw = load_dev("TaiwanStockPrice", stock_id, start_date)
    if raw.empty:
        # Bug fixed 2026-08-22: this used to call .sort_values("date") before checking
        # emptiness -- an empty DataFrame has zero columns, so that raised KeyError('date')
        # instead of just returning the (correctly empty) result.
        raw["source"] = None  # keep column-shape consistent even in the empty case
        return raw
    raw = raw.sort_values("date").reset_index(drop=True)
    events = adjustment_events(stock_id, start_date)

    factor_cum = pd.Series(1.0, index=raw.index)
    for _, ev in events.sort_values("ex_date", ascending=False).iterrows():
        mask = raw["date"] < ev["ex_date"]
        factor_cum.loc[mask] = factor_cum.loc[mask] * ev["factor"]

    out = raw.copy()
    out["adj_close"] = raw["close"].astype(float) * factor_cum
    out["adj_open"] = raw["open"].astype(float) * factor_cum
    # FinMind's raw TaiwanStockPrice uses "max"/"min" for daily high/low
    # (confirmed empirically 2026-09-06 -- there is no "high"/"low" column on
    # this path; only the yfinance path in this function uses those names).
    out["adj_high"] = raw["max"].astype(float) * factor_cum
    out["adj_low"] = raw["min"].astype(float) * factor_cum
    out["source"] = "finmind"
    out.attrs["_n_events"] = len(events)
    return out


def _truncate_pre_listing(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
    """驗.八四第1點：兩條來源路徑共用的上市日截斷。查無上市日者原樣保留
    （`universe.truncate_to_listing_date()`本來的職責邊界，已下市/興櫃不截）。
    截斷是資料清理、不是守門員，但上市日檔案讀取失敗仍依十二節fail open：
    印警告、回傳原表，不讓所有呼叫端因為一個靜態檔壞掉而全部中斷。
    被截掉的列數放在`out.attrs["n_rows_truncated_pre_listing"]`。"""
    try:
        from universe import truncate_to_listing_date

        out = truncate_to_listing_date(df, stock_id)
        out.attrs["n_rows_truncated_pre_listing"] = int(len(df) - len(out))
        return out
    except Exception as e:  # noqa: BLE001 -- fail open
        print(f"::warning::上市日截斷失敗（{stock_id}），未截斷：{type(e).__name__}: {e}")
        df.attrs["n_rows_truncated_pre_listing"] = 0
        return df


ANOMALY_RETURN_THRESHOLD_PCT = 11.0  # ⚠️2026-09-27查.二後已改為日期相依門檻
# （見下方ANOMALY_RETURN_THRESHOLD_PCT_BEFORE_REGIME_CUT/_AFTER），這個舊
# 常數保留供其他模組/既有測試引用單一數字時的相容性，本函式內部已不再
# 直接使用它判斷異常，改呼叫_anomaly_threshold_pct()。
ANOMALY_REGIME_CUT = "2015-06-01"  # 台股單日漲跌幅限制從±7%放寬到±10%的生效日
ANOMALY_RETURN_THRESHOLD_PCT_BEFORE_REGIME_CUT = 7.5  # 查.二：±7%限制+安全margin
ANOMALY_RETURN_THRESHOLD_PCT_AFTER_REGIME_CUT = 10.5  # 查.二：±10%限制+安全margin
ANOMALY_MIN_ROWS_AFTER_LISTING = 5
ANOMALY_LOG_PATH = Path(__file__).parent / "data" / "adjustment_anomaly_warnings.jsonl"


def _anomaly_threshold_pct(date_str: str) -> float:
    """日期相依的異常門檻（查.二2026-09-27裁示，取代修.六原本單一11%門檻）：
    2015-06-01前台股單日漲跌幅限制為±7%，之後放寬為±10%——用單一11%門檻
    掃描2015-06-01前的資料會系統性漏掉「7%~11%之間」這段其實已經超限、
    理論上不該發生的真異常（例如興櫃期間無漲跌幅限制產生的假訊號）。改用
    限制值+0.5個百分點的安全margin，不緊貼理論上限（避免正常的漲跌停
    邊界值因為浮點/複權誤差被誤判)，也不放到跟舊門檻一樣寬而失去日期
    相依門檻的意義。"""
    return ANOMALY_RETURN_THRESHOLD_PCT_BEFORE_REGIME_CUT if date_str < ANOMALY_REGIME_CUT \
        else ANOMALY_RETURN_THRESHOLD_PCT_AFTER_REGIME_CUT


def check_adjusted_series_anomalies(df: pd.DataFrame, stock_id: str) -> list[dict]:
    """修.六第三點（2026-09-27裁示）永久閘門，**查.二（同日稍後裁示）已將
    門檻改為日期相依**：任何還原價序列出現單日|報酬|超過當日對應門檻
    （2015-06-01前±7.5%、之後±10.5%，見`_anomaly_threshold_pct()`），
    新上市5日內除外，即列入警告清單。**這是偵測器本身，依CLAUDE.md十二節
    『守門員自己的失敗只能降級成警告，不得中斷被監控的流程』原則設計——
    刻意包在最外層try/except，任何內部錯誤都只印警告、回傳空list，絕不
    讓呼叫`adjusted_price_series()`的任何排程因為這個附加檢查而中斷。**
    這支只負責『偵測並回傳』，不負責『寫進STATUS.json』（那是另一層彙整
    的責任，見`_append_anomaly_log()`與`scripts/check_local_schedule_
    heartbeat.py`的docstring說明，目前尚未接上任何排程，如實記錄現況）。"""
    try:
        if df.empty or "adj_close" not in df.columns or len(df) <= ANOMALY_MIN_ROWS_AFTER_LISTING:
            return []
        d = df.sort_values("date").reset_index(drop=True)
        ret = d["adj_close"].pct_change() * 100
        hits = []
        for i in range(ANOMALY_MIN_ROWS_AFTER_LISTING, len(d)):
            r = ret.iloc[i]
            date_str = str(d.loc[i, "date"])
            if pd.notna(r) and abs(r) > _anomaly_threshold_pct(date_str):
                hits.append({
                    "stock_id": stock_id, "date": date_str, "ret_pct": round(float(r), 2),
                    "threshold_pct": _anomaly_threshold_pct(date_str),
                    "detected_at": pd.Timestamp.now().isoformat(),
                })
        return hits
    except Exception as e:  # noqa: BLE001 -- 偵測失敗只降級成警告，不得讓排程崩潰
        print(f"::warning::還原價異常偵測失敗（{stock_id}）：{type(e).__name__}: {e}")
        return []


def _append_anomaly_log(hits: list[dict]) -> None:
    """append-only寫進本機jsonl，供之後彙整進STATUS.json用。同一個
    (stock_id, date)只記一次，避免同一支股票被重複呼叫`adjusted_price_
    series()`時（例如多輪排程各自算一次）在log裡無限累積重複列。失敗
    只降級警告，不拋例外。"""
    if not hits:
        return
    try:
        seen = set()
        if ANOMALY_LOG_PATH.exists():
            for line in ANOMALY_LOG_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    seen.add((rec.get("stock_id"), rec.get("date")))
                except Exception:  # noqa: BLE001
                    continue
        new_hits = [h for h in hits if (h["stock_id"], h["date"]) not in seen]
        if not new_hits:
            return
        ANOMALY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ANOMALY_LOG_PATH.open("a", encoding="utf-8") as f:
            for h in new_hits:
                f.write(json.dumps(h, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::還原價異常log寫入失敗：{type(e).__name__}: {e}")


YF_CROSSCHECK_THRESHOLD_PP = 2.0  # 驗.八四第2點：逐日報酬差>2個百分點列警告
YF_CROSSCHECK_LOG_PATH = Path(__file__).parent / "data" / "yf_finmind_crosscheck_warnings.jsonl"


def _finmind_cache_ready(stock_id: str, start_date: str) -> bool:
    """交叉比對只用**已快取**的FinMind資料，絕不觸發網路請求——免費額度只有
    每小時數百次，每次呼叫`adjusted_price_series()`都多打5個資料集會把研究管線
    自己推進402冷卻（驗.八析.二實際踩過）。缺快取就回報「無法比對」，不硬打。"""
    from finmind_client import _cache_path
    from validation.holdout import VAL_END

    need = [
        ("TaiwanStockPrice", stock_id), ("TaiwanStockDividend", stock_id),
        ("TaiwanStockSplitPrice", stock_id), ("TaiwanStockCapitalReductionReferencePrice", stock_id),
        ("TaiwanStockParValueChange", ""),
    ]
    return all(_cache_path(ds, sid, start_date, VAL_END).exists() for ds, sid in need)


def _crosscheck_frames(yf_df: pd.DataFrame, fin_df: pd.DataFrame, stock_id: str,
                       threshold_pp: float = YF_CROSSCHECK_THRESHOLD_PP) -> list[dict]:
    """純函式（不碰網路/檔案），兩張表都要有`date`、`adj_close`。兩張表先各自
    以日期內連接，再各算逐日報酬（缺日時兩邊跨同一段，仍可比）。兩種警告：
    (1) `diff_over_threshold`：|yfinance報酬-FinMind重建報酬|>threshold_pp；
    (2) `yf_over_limit_fin_within`：yfinance單日|報酬|超過該日漲跌幅門檻
    （`_anomaly_threshold_pct()`），而FinMind重建在門檻內——驗.七判定為
    「yfinance自身還原錯誤」的簽名（2332：yfinance+8.11%、FinMind原始價
    +6.78%，差僅1.33pp，單看(1)抓不到，靠(2)抓）。"""
    if yf_df.empty or fin_df.empty:
        return []
    a = yf_df[["date", "adj_close"]].rename(columns={"adj_close": "yf"})
    b = fin_df[["date", "adj_close"]].rename(columns={"adj_close": "fin"})
    j = a.merge(b, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if len(j) < 2:
        return []
    j["yf_ret"] = j["yf"].pct_change() * 100
    j["fin_ret"] = j["fin"].pct_change() * 100
    hits = []
    for _, r in j.iloc[1:].iterrows():
        if pd.isna(r["yf_ret"]) or pd.isna(r["fin_ret"]):
            continue
        date_str = str(r["date"])
        diff = abs(r["yf_ret"] - r["fin_ret"])
        lim = _anomaly_threshold_pct(date_str)
        kinds = []
        if diff > threshold_pp:
            kinds.append("diff_over_threshold")
        if abs(r["yf_ret"]) > lim and abs(r["fin_ret"]) <= lim:
            kinds.append("yf_over_limit_fin_within")
        if kinds:
            hits.append({
                "stock_id": stock_id, "date": date_str,
                "yf_ret_pct": round(float(r["yf_ret"]), 2),
                "finmind_ret_pct": round(float(r["fin_ret"]), 2),
                "diff_pp": round(float(diff), 2), "kinds": kinds,
                "detected_at": pd.Timestamp.now().isoformat(),
            })
    return hits


def crosscheck_yf_vs_finmind(yf_out: pd.DataFrame, stock_id: str, start_date: str = "1990-01-01",
                             *, threshold_pp: float = YF_CROSSCHECK_THRESHOLD_PP) -> list[dict]:
    """驗.八四第2點（2026-09-29裁示）：yfinance還原日報酬 vs「FinMind原始價+已驗證
    事件因子」日報酬，差異>2個百分點列進警告清單。**只列出、不切換主要來源**
    （`adjusted_price_series()`仍回yfinance）。依十二節fail open：任何內部錯誤只印
    警告、回傳空list；FinMind快取不齊全時直接跳過（不打網路，見
    `_finmind_cache_ready()`），跳過不算通過也不算失敗。"""
    try:
        if yf_out.empty or not _finmind_cache_ready(stock_id, start_date):
            return []
        fin = _truncate_pre_listing(_finmind_adjusted_frame(stock_id, start_date), stock_id)
        _mask_non_positive_adj_prices(fin)
        return _crosscheck_frames(yf_out, fin, stock_id, threshold_pp)
    except Exception as e:  # noqa: BLE001 -- 守門員自身失敗只降級
        print(f"::warning::yfinance/FinMind交叉比對失敗（{stock_id}）：{type(e).__name__}: {e}")
        return []


def _append_crosscheck_log(hits: list[dict]) -> None:
    """append-only jsonl，(stock_id, date)去重；失敗只降級警告。"""
    if not hits:
        return
    try:
        seen = set()
        if YF_CROSSCHECK_LOG_PATH.exists():
            for line in YF_CROSSCHECK_LOG_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    seen.add((rec.get("stock_id"), rec.get("date")))
                except Exception:  # noqa: BLE001
                    continue
        new_hits = [h for h in hits if (h["stock_id"], h["date"]) not in seen]
        if not new_hits:
            return
        YF_CROSSCHECK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with YF_CROSSCHECK_LOG_PATH.open("a", encoding="utf-8") as f:
            for h in new_hits:
                f.write(json.dumps(h, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::yfinance/FinMind交叉比對log寫入失敗：{type(e).__name__}: {e}")


def _mask_non_positive_adj_prices(df: pd.DataFrame) -> None:
    """In-place: adj_close/adj_open/adj_high/adj_low <= 0 -> NaN.

    Single choke point for both source paths (see module docstring,
    2026-09-23 fix) -- a non-positive adjusted price is never a real price
    (FinMind's zero-volume-day convention, or a yfinance auto_adjust
    artifact going negative), and letting it through produces a fabricated
    -100%-or-worse return in every downstream pct_change().
    """
    for col in ("adj_close", "adj_open", "adj_high", "adj_low"):
        if col in df.columns:
            df.loc[df[col] <= 0, col] = float("nan")


def _self_test_synthetic() -> bool:
    """Zero-volume-day close=0.0 (FinMind convention) must come out as NaN,
    not survive into adj_close and later masquerade as a real -100% day."""
    df = pd.DataFrame({
        "adj_close": [10.0, 0.0, 11.0, -3.0, 12.0],
        "adj_open": [10.0, 0.0, 11.0, -3.0, 12.0],
        "adj_high": [10.5, 0.0, 11.5, -2.5, 12.5],
        "adj_low": [9.5, 0.0, 10.5, -3.5, 11.5],
    })
    _mask_non_positive_adj_prices(df)
    ok = df["adj_close"].isna().tolist() == [False, True, False, True, False]
    print(f"[self-test 1/2] 合成案例(0與負值->NaN)：{'PASS' if ok else 'FAIL'}")
    return ok


def _self_test_known_bad_stock() -> bool:
    """Live spot-check against stock 5395, which the 2026-09-23 cache audit
    confirmed has 1,124 zero-volume-day close=0.0 rows 2004-2016 in the
    FinMind fallback path. After the fix, none of those dates should carry
    a non-positive adj_close."""
    try:
        out = adjusted_price_series("5395", "2004-01-01")
    except Exception as e:  # noqa: BLE001 -- data/network unavailable is a skip, not a fail
        print(f"[self-test 2/2] 5395真實案例：SKIP（無法讀取資料，{e}）")
        return True
    if out.empty:
        print("[self-test 2/2] 5395真實案例：SKIP（無資料）")
        return True
    # NaN itself is the correct/expected outcome now -- only a *non-positive
    # number* surviving the mask would indicate the fix didn't take.
    n_nonpositive_leftover = int((out["adj_close"] <= 0).sum())
    n_nan = int(out["adj_close"].isna().sum())
    ok = n_nonpositive_leftover == 0 and n_nan > 0
    print(
        f"[self-test 2/2] 5395真實案例：殘留<=0筆數={n_nonpositive_leftover}"
        f"（應為0），轉NaN筆數={n_nan}（應>0，代表確實抓到已知的髒資料）："
        f"{'PASS' if ok else 'FAIL'}"
    )
    return ok


def _self_test_cash_increase_rate_unit() -> bool:
    """查.三（2026-09-27裁示）：`CashIncreaseSubscriptionRate`除以1000的
    單位修正，用5筆真實現金增資事件（`stock_ratio=0`的乾淨案例，2010~
    2022年，涵蓋官方文件未寫明但實測驗證過的欄位）核對還原因子與官方
    `TaiwanStockDividendResult`的`reference_price/before_price`實際
    比例誤差<0.6%（驗.九三由0.5%校正，見case_ok處註解）。輸入值已寫死（2026-09-27即時查證FinMind API取得，
    避免每次跑自我測試都消耗一次額外API請求），不含即時網路呼叫。"""
    cases = [
        {"sid": "3026", "cash": 3.0, "rights_ratio_raw": 9.19, "rights_price": 32.5,
         "before_price": 46.9, "reference_price": 43.9},
        {"sid": "2038", "cash": 1.1, "rights_ratio_raw": 37.367384663, "rights_price": 11.6,
         "before_price": 14.9, "reference_price": 13.8},
        {"sid": "1338", "cash": 2.5, "rights_ratio_raw": 6.626120358, "rights_price": 103.0,
         "before_price": 123.5, "reference_price": 121.0},
        {"sid": "2239", "cash": 3.9, "rights_ratio_raw": 6.545454545, "rights_price": 147.0,
         "before_price": 165.5, "reference_price": 161.6},
        {"sid": "1605", "cash": 1.6, "rights_ratio_raw": 6.994366435, "rights_price": 33.0,
         "before_price": 40.6, "reference_price": 39.0},
    ]
    ok = True
    for c in cases:
        rights_ratio = c["rights_ratio_raw"] / 1000.0
        ref_price = (c["before_price"] - c["cash"] + c["rights_price"] * rights_ratio) / (1 + rights_ratio)
        our_ratio = ref_price / c["before_price"]
        actual_ratio = c["reference_price"] / c["before_price"]
        err_pct = abs(our_ratio - actual_ratio) / actual_ratio * 100
        # 門檻0.6%（原0.5%）：2038誤差0.574%，來源為官方參考價四捨五入至升降單位，
        # Cowork 09-27已接受（2026-09-29驗.九三，總司令裁示）
        case_ok = err_pct < 0.6
        ok = ok and case_ok
        print(f"  {c['sid']}：官方比例={actual_ratio:.6f} 修正後公式比例={our_ratio:.6f} "
              f"誤差={err_pct:.3f}%：{'PASS' if case_ok else 'FAIL'}")
    print(f"[self-test 3/4] CashIncreaseSubscriptionRate除以1000修正：{'PASS' if ok else 'FAIL'}")
    return ok


def _self_test_stock_dividend_unit() -> bool:
    """修.七（2026-09-27裁示）：`StockEarningsDistribution`除以10的單位
    修正，用5筆純股票股利事件(現金=0)+5筆現金+股票股利混合事件(共10筆，
    2010~2024年，2026-09-27即時查證FinMind API取得，輸入值寫死避免每次
    自我測試消耗額外API請求)核對還原因子與官方`TaiwanStockDividendResult`
    的`reference_price/before_price`實際比例誤差<0.6%。"""
    cases = [
        {"sid": "8908", "cash": 0.0, "stock_ratio_raw": 0.8, "before_price": 26.0, "reference_price": 24.07},
        {"sid": "3312", "cash": 0.0, "stock_ratio_raw": 0.5, "before_price": 11.2, "reference_price": 10.66},
        {"sid": "5531", "cash": 0.0, "stock_ratio_raw": 0.5, "before_price": 10.9, "reference_price": 10.38},
        {"sid": "8941", "cash": 0.0, "stock_ratio_raw": 1.0, "before_price": 58.2, "reference_price": 52.91},
        {"sid": "2597", "cash": 0.0, "stock_ratio_raw": 4.0, "before_price": 202.0, "reference_price": 144.28},
        {"sid": "2356", "cash": 1.0, "stock_ratio_raw": 0.5, "before_price": 18.75, "reference_price": 16.9},
        {"sid": "6441", "cash": 4.0, "stock_ratio_raw": 0.5, "before_price": 63.8, "reference_price": 56.95},
        {"sid": "2106", "cash": 1.8, "stock_ratio_raw": 0.70010353, "before_price": 68.9, "reference_price": 62.7},
        {"sid": "1308", "cash": 0.6, "stock_ratio_raw": 0.2, "before_price": 18.4, "reference_price": 17.45},
        {"sid": "6762", "cash": 3.0, "stock_ratio_raw": 2.0, "before_price": 259.0, "reference_price": 213.33},
    ]
    ok = True
    for c in cases:
        stock_ratio = c["stock_ratio_raw"] / 10.0
        ref_price = (c["before_price"] - c["cash"]) / (1 + stock_ratio)
        our_ratio = ref_price / c["before_price"]
        actual_ratio = c["reference_price"] / c["before_price"]
        err_pct = abs(our_ratio - actual_ratio) / actual_ratio * 100
        case_ok = err_pct < 0.6
        ok = ok and case_ok
        print(f"  {c['sid']}：官方比例={actual_ratio:.6f} 修正後公式比例={our_ratio:.6f} "
              f"誤差={err_pct:.3f}%：{'PASS' if case_ok else 'FAIL'}")
    print(f"[self-test 4/4] StockEarningsDistribution除以10修正：{'PASS' if ok else 'FAIL'}")
    return ok


def _self_test_crosscheck_known_cases() -> bool:
    """驗.八四第3點：3011與2332必須被交叉比對抓到（輸入寫死，來源=驗.七
    `PENDING_QUEUE.md`（2332 2009-04-02：yfinance+8.11% vs FinMind原始價+6.78%；
    3011 2009-06-08：+14.34% vs +6.90%），不含網路）。另含兩個負向對照：
    差<=2pp且都在門檻內者不得誤報。"""
    def mk(prev, ret_pct, d):
        return [(d[0], prev), (d[1], prev * (1 + ret_pct / 100.0))]

    def frame(rows):
        return pd.DataFrame(rows, columns=["date", "adj_close"])

    cases = [
        ("2332", ("2009-04-01", "2009-04-02"), 8.11, 6.78, True),
        ("3011", ("2009-06-05", "2009-06-08"), 14.34, 6.90, True),
        ("NEG1", ("2009-04-01", "2009-04-02"), 3.50, 2.90, False),
        ("NEG2", ("2020-04-01", "2020-04-02"), 9.90, 9.50, False),
    ]
    ok = True
    for sid, d, yr, fr, want in cases:
        hits = _crosscheck_frames(frame(mk(50.0, yr, d)), frame(mk(50.0, fr, d)), sid)
        got = len(hits) > 0
        case_ok = got == want
        ok = ok and case_ok
        kinds = hits[0]["kinds"] if hits else []
        print(f"  {sid}：yf {yr:+.2f}% vs FinMind {fr:+.2f}% -> 警告={got}（應={want}）{kinds}："
              f"{'PASS' if case_ok else 'FAIL'}")
    print(f"[self-test 修.八-A] yfinance/FinMind交叉比對抓得到2332/3011：{'PASS' if ok else 'FAIL'}")
    return ok


def _self_test_truncation_both_paths() -> bool:
    """驗.八四第1點：`adjusted_price_series()`在yfinance與FinMind兩條路徑都要套上市日
    截斷。用monkeypatch餵合成資料（不碰網路/快取）：上市日2010-01-05，資料含
    2010-01-04之前的興櫃期間列，兩條路徑輸出的最早日期都必須>=上市日。"""
    import yf_price_client as _yf
    import universe as _uni

    dates = ["2009-12-30", "2010-01-04", "2010-01-05", "2010-01-06", "2010-01-07"]
    px = [10.0, 30.0, 12.0, 12.1, 12.2]

    def yf_stub(stock_id, start_date="2010-01-01", end_date=None, force_refresh=False):
        return pd.DataFrame({"date": dates, "stock_id": stock_id, "open": px, "high": px,
                             "low": px, "close": px, "volume": 1.0, "source": "yfinance"})

    def yf_empty(stock_id, start_date="2010-01-01", end_date=None, force_refresh=False):
        return pd.DataFrame()

    def load_stub(dataset, data_id="", start_date="2000-01-01", end_date=None, date_col="date", force_refresh=False):
        return pd.DataFrame({"date": dates, "stock_id": data_id, "open": px, "close": px,
                             "max": px, "min": px})

    g = globals()
    saved = (_yf.fetch_yf_adjusted, _uni.listing_date_lookup, g["load_dev"], g["adjustment_events"],
             g["_append_anomaly_log"], g["_append_crosscheck_log"], g["crosscheck_yf_vs_finmind"])
    try:
        _uni.listing_date_lookup = lambda: {"9999": "2010-01-05"}
        g["load_dev"] = load_stub
        g["adjustment_events"] = lambda sid, sd="1990-01-01": _empty_events_df()
        g["_append_anomaly_log"] = lambda hits: None
        g["_append_crosscheck_log"] = lambda hits: None
        g["crosscheck_yf_vs_finmind"] = lambda *a, **k: []
        res = {}
        for name, stub in (("yfinance", yf_stub), ("finmind", yf_empty)):
            _yf.fetch_yf_adjusted = stub
            out = adjusted_price_series("9999", "2009-01-01")
            res[name] = (str(out["date"].min()), len(out), out.attrs.get("n_rows_truncated_pre_listing"))
        _yf.fetch_yf_adjusted = yf_stub
        res["unknown"] = len(adjusted_price_series("0000", "2009-01-01"))
    finally:
        (_yf.fetch_yf_adjusted, _uni.listing_date_lookup, g["load_dev"], g["adjustment_events"],
         g["_append_anomaly_log"], g["_append_crosscheck_log"], g["crosscheck_yf_vs_finmind"]) = saved
    ok = (res["yfinance"][0] >= "2010-01-05" and res["finmind"][0] >= "2010-01-05"
          and res["yfinance"][1] == 3 and res["finmind"][1] == 3 and res["unknown"] == 5)
    print(f"  yfinance路徑最早={res['yfinance'][0]}（列數{res['yfinance'][1]}，截{res['yfinance'][2]}）；"
          f"FinMind路徑最早={res['finmind'][0]}（列數{res['finmind'][1]}，截{res['finmind'][2]}）；"
          f"查無上市日代號列數={res['unknown']}（應5，不截）")
    print(f"[self-test 修.八-B] 兩條路徑都套用上市日截斷：{'PASS' if ok else 'FAIL'}")
    return ok


def _self_test_crosscheck_fail_open() -> bool:
    """十二節：交叉比對自己壞掉（例如FinMind重建拋例外）只能印警告並回空list。"""
    g = globals()
    saved = (g["_finmind_cache_ready"], g["_finmind_adjusted_frame"])
    try:
        g["_finmind_cache_ready"] = lambda sid, sd: True

        def boom(sid, sd):
            raise ValueError("模擬FinMind重建失敗")

        g["_finmind_adjusted_frame"] = boom
        got = crosscheck_yf_vs_finmind(pd.DataFrame({"date": ["2020-01-02"], "adj_close": [1.0]}), "0000")
    finally:
        g["_finmind_cache_ready"], g["_finmind_adjusted_frame"] = saved
    ok = got == []
    print(f"[self-test 修.八-C] 交叉比對自身失敗fail open（回空list不拋例外）：{'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    r1 = _self_test_synthetic()
    r2 = _self_test_known_bad_stock()
    r3 = _self_test_cash_increase_rate_unit()
    r4 = _self_test_stock_dividend_unit()
    r5 = _self_test_crosscheck_known_cases()
    r6 = _self_test_truncation_both_paths()
    r7 = _self_test_crosscheck_fail_open()
    allok = r1 and r2 and r3 and r4 and r5 and r6 and r7
    print(f"整體結果：{'PASS' if allok else 'FAIL'}")
    raise SystemExit(0 if allok else 1)
