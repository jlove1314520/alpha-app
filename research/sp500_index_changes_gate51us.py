"""HYPOTHESIS_QUEUE.md #51-US（強制交易者事件·美股版：S&P/DJ 指數成分納入）
第1關 cheap gate（事件研究，個股層級，比照`fut_settlement_event_gate60.py`/
`cbc_decision_event_gate61.py`同款事件窗口 vs 隨機交易日null框架，但個股
橫斷面用`control_group_standard.evaluate_vs_control()`——`#52-US
us_8k_pead_gate52.py`同款per-ticker配對抽樣控制組，因為這裡事件橫跨數百檔
不同股票，不是單一大盤指數）。

**經濟理由**（見`HYPOTHESIS_QUEUE.md` #51-US條目）：S&P/道瓊指數成分調整——
公告後、生效日前，追蹤該指數的被動基金**不論價格都必須在生效日交易**（法規/
合約義務，非預測性）。文獻（Harris & Gurel 1986、Shleifer 1986等）記載的
「指數效應」典型模式：生效日前因套利者搶跑與被動基金逐步建倉而價格上漲，
生效日後因強制買盤消失、套利者平倉而部分反轉。

**事前綁定（本輪執行前寫死，看到結果後不得調整）**：
- 範圍：僅測`action=="Addition"`（納入=強制買盤，機制方向明確）。`Deletion`
  （強制賣壓，方向對稱但不同資料/流動性特徵）留給未來輪次獨立測試，明確
  記錄為已知限制，不在本輪順帶測。
- 指數範圍：`S&P 500`／`S&P 100`／`S&P MidCap 400`／`S&P SmallCap 600`四個
  市值加權指數，**排除**`Dow Jones Industrial Average`／`Dow Jones
  Transportation Average`——後兩者是**價格加權**而非市值加權，被動資金規模
  也小得多，屬於不同的加權機制，事前排除避免混進去稀釋或混淆訊號方向，
  不是看到結果後才排除。
- 事件錨點：`effective_date`（生效日，非公告日/`article_date_raw`）——比照
  `HYPOTHESIS_QUEUE.md` #51-US章節既有紀錄的「生效日±N日報酬」設計。
- 子測試(a) 生效前壓力：PRE_WINDOW=5個交易日，
  `pre_ret = close[idx-1] / close[idx-1-PRE_WINDOW] - 1`（窗口結束於生效日
  前一交易日，避免跟生效日當天本身的報酬重疊計算），**事前預期方向為正**
  （被動買盤/套利者搶跑推升價格）。
- 子測試(b) 生效後反轉：POST_WINDOW=3個交易日，
  `post_ret = close[idx-1+POST_WINDOW] / close[idx-1] - 1`（窗口起點為生效日
  前一交易日，涵蓋生效日當天的價格衝擊+短期反轉），**事前預期方向為負**
  （強制買盤消失後部分回吐）。
- 控制組：比照`us_8k_pead_gate52.py`同款「per-ticker配對抽樣」——每個真實
  事件的控制組抽樣，從同一檔股票自己的可用交易日池（排除任何真實事件日
  前後CONTROL_EXCLUSION_BUFFER=10個交易日的緩衝區）隨機抽一天，用同樣的
  窗口定義重算指標，2個獨立種子各100次抽樣，透過
  `control_group_standard.evaluate_vs_control()`判定（訊號需嚴格贏過控制組
  所有抽樣的最大值，或配對20/20全勝，贏平均不算）。
- TRAIN/VAL依`validation.holdout`（`TRAIN_END`/`VAL_END`）依`effective_date`
  切分，各期需至少10筆可用事件才進行判定，不足則誠實標記樣本不足並跳過。
- API 預算煞車：資料源`sp500_index_changes_client.py`已本機快取零新增
  HTTP請求；價格資料經由`us_factors.us_price_series()`（`load_dev()`
  VAL_END截斷路徑）逐檔向FinMind拉取，**本輪先跑SAMPLE_SIZE=100檔的抽樣
  試跑**（比照`us_8k_pead_gate52.py`「先跑小樣本再花全額度」的先例），
  不一次對全部~700檔獨立ticker發API request，避免撞到`CLAUDE.md`記載的
  FinMind免費層每小時流量上限。

**已知限制（誠實揭露，事前寫明）**：
1. 價格資料源沿用`us_factors.us_price_series()`（`load_dev("USStockPrice",
   ...)`，實際由FinMind供應）。`CLAUDE.md`「各市場一律使用該市場的原生
   資料源」原則要求美股價格優先用SEC EDGAR／yfinance／Stooq，FinMind僅
   歷史補充；但本專案既有US軌大量已判定試驗（含`#52-US`）皆沿用這個
   既有`us_price_series()`介面，本輪比照HYPOTHESIS_QUEUE_PROTOCOL第2節
   「延續既有腳本，不重新發明」精神繼續使用，不在單一cheap gate輪次內
   片面更換資料源架構（架構變更需依`CLAUDE.md`「提案先於執行」，非
   已交辦事項）。但本假設的樣本股票在納入指數當下皆為現存活躍上市公司，
   跟`CLAUDE.md`「已下市股FinMind覆蓋率」的既有已知缺口（`TWTR`/`SIVB`
   類已下市股）性質不同，緩解但不完全消除疑慮。
2. 只測「納入」單邊，未測「剔除」（強制賣壓）鏡像方向——見上方範圍說明。
3. 樣本為100檔抽樣試跑，非全部~700檔獨立ticker的完整回補；若第1關
   CHEAP_PASS，下一輪應評估是否擴大樣本再進入更深的關卡。
4. 未做產業/大盤中性化調整（跟`us_8k_pead_gate52.py`已知缺口相同，
   `US_MARATHON_STATE.md`記錄的既有gap，本輪比照沿用原始報酬）。

python research/sp500_index_changes_gate51us.py
"""
from __future__ import annotations

import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from control_group_standard import evaluate_vs_control
from sp500_index_changes_client import load_all_cached_articles
from us_factors import us_price_series
from validation import holdout

INDEX_SCOPE = ("S&P 500", "S&P 100", "S&P MidCap 400", "S&P SmallCap 600")
PRE_WINDOW = 5
POST_WINDOW = 3
CONTROL_EXCLUSION_BUFFER = 10
N_CONTROL_DRAWS = 100
CONTROL_SEEDS = {"seed_a": 20260909_511, "seed_b": 20260909_512}
SAMPLE_SIZE = 100
SAMPLE_SEED = 20260909_51


def _parse_effective_date(raw: str) -> pd.Timestamp:
    """事前綁定的日期正規化規則（非結果導向調整——這是修復解析器本身的
    格式覆蓋率，跟`#46 IPO listing-age`那次修`_listing_age_days()` str/
    Timestamp相減bug同一種性質：先把解析器修對，再用同一套統計檢定跑，
    不是看到結果後才動這裡）。已知來源格式的變體：
    'Sept. 18, 2023' / 'Sept 21, 2026'（非標準月份縮寫"Sept"，標準縮寫是
    "Sep"）、'March 24,2025'（逗號後缺空白，會被誤解析成年份0001）、
    '23-Sep-24'（DD-Mon-YY，預設解析器已可正確處理）、空字串／'TBA'（
    真的沒有日期，維持NaT丟棄）。"""
    if not isinstance(raw, str):
        return pd.NaT
    s = raw.strip()
    if not s:
        return pd.NaT
    s = s.replace("Sept.", "Sep").replace("Sept ", "Sep ")
    s = re.sub(r",(?=\S)", ", ", s)  # 逗號後補空白，避免'March 24,2025'誤解析
    ts = pd.to_datetime(s, errors="coerce")
    if pd.isna(ts) or ts.year < 2000:
        return pd.NaT
    return ts


def load_addition_events() -> pd.DataFrame:
    """回傳去重後的「納入」事件列表，欄位：ticker/company_name/index_name/
    effective_date（ISO字串）。事前綁定的過濾規則見模組docstring，執行前
    寫死，不因結果調整。"""
    df = load_all_cached_articles()
    if "IndexName" in df.columns:
        df["index_name"] = df["index_name"].where(df["index_name"].notna(), df["IndexName"])
    df = df[df["action"] == "Addition"].copy()
    df = df[df["index_name"].astype(str).apply(lambda s: any(k in s for k in INDEX_SCOPE))]
    df = df.dropna(subset=["ticker", "effective_date_raw", "company_name"])
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["effective_date"] = df["effective_date_raw"].astype(str).apply(_parse_effective_date)
    n_before = len(df)
    df = df.dropna(subset=["effective_date"])
    n_dropped_date = n_before - len(df)
    df["effective_date"] = df["effective_date"].dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates(subset=["ticker", "effective_date"]).reset_index(drop=True)
    if n_dropped_date:
        print(f"（{n_dropped_date}筆effective_date_raw無法解析為日期，已丟棄，"
              f"多為空字串/'TBA'佔位或真正無法辨識的格式）")
    return df[["ticker", "company_name", "index_name", "effective_date"]]


@dataclass
class EventRow:
    ticker: str
    effective_date: str
    period: str
    pre_ret: float
    post_ret: float


def period_of(date_str: str) -> str:
    if date_str <= holdout.TRAIN_END:
        return "TRAIN"
    if date_str <= holdout.VAL_END:
        return "VAL"
    return "OUT_OF_RANGE"


def process_ticker(ticker: str, event_dates: list[str]) -> tuple[list[EventRow], list[int], list[str], dict]:
    """回傳(真實事件列表, 可用控制組交易日index池, 該檔股票交易日曆,
    跳過原因統計)。跟`us_8k_pead_gate52.py::process_ticker`同款結構。"""
    skips: dict = {}
    px = us_price_series(ticker)
    if px.empty or len(px) < 30:
        skips["no_price_history"] = 1
        return [], [], [], skips
    calendar = px["date"].tolist()
    closes = px["adj_close"].tolist()
    n = len(calendar)
    date_to_idx = {d: i for i, d in enumerate(calendar)}

    rows: list[EventRow] = []
    seen_idx: set[int] = set()
    skipped_not_trading_day = 0
    skipped_oob = 0
    for ed in event_dates:
        idx = date_to_idx.get(ed)
        if idx is None:
            skipped_not_trading_day += 1
            continue
        if idx in seen_idx:
            continue
        idx_prev = idx - 1
        idx_pre_start = idx_prev - PRE_WINDOW
        idx_post_end = idx_prev + POST_WINDOW
        if idx_pre_start < 0 or idx_post_end >= n:
            skipped_oob += 1
            continue
        p_pre0, p_pre1 = closes[idx_pre_start], closes[idx_prev]
        p_post0, p_post1 = closes[idx_prev], closes[idx_post_end]
        if any(pd.isna(x) or x <= 0 for x in (p_pre0, p_pre1, p_post0, p_post1)):
            continue
        seen_idx.add(idx)
        rows.append(EventRow(
            ticker=ticker, effective_date=ed, period=period_of(ed),
            pre_ret=p_pre1 / p_pre0 - 1.0, post_ret=p_post1 / p_post0 - 1.0,
        ))
    if skipped_not_trading_day:
        skips["effective_date_not_a_trading_day"] = skipped_not_trading_day
    if skipped_oob:
        skips["out_of_range_for_window"] = skipped_oob

    excluded = set()
    for idx in seen_idx:
        for off in range(-CONTROL_EXCLUSION_BUFFER, CONTROL_EXCLUSION_BUFFER + 1):
            excluded.add(idx + off)
    lo, hi = PRE_WINDOW + 1, n - POST_WINDOW - 1
    eligible = [i for i in range(lo, hi) if i not in excluded]
    return rows, eligible, calendar, skips


def _draw_control_means(events: list[EventRow], pools: dict[str, list[int]],
                         closes_by_ticker: dict[str, list[float]], metric: str,
                         rng: random.Random) -> float:
    vals = []
    for ev in events:
        pool = pools.get(ev.ticker)
        if not pool:
            continue
        idx = rng.choice(pool)
        closes = closes_by_ticker[ev.ticker]
        idx_prev = idx - 1
        if metric == "pre_ret":
            p0, p1 = closes[idx_prev - PRE_WINDOW], closes[idx_prev]
        else:
            p0, p1 = closes[idx_prev], closes[idx_prev + POST_WINDOW]
        if p0 <= 0 or pd.isna(p0) or pd.isna(p1):
            continue
        vals.append(p1 / p0 - 1.0)
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _run_subtest(label: str, metric: str, expect_positive: bool, period_events: list[EventRow],
                  pools: dict[str, list[int]], closes_by_ticker: dict[str, list[float]],
                  period: str) -> None:
    n_ev = len(period_events)
    print(f"\n--- {period} / {label} ---")
    print(f"n_events={n_ev}")
    if n_ev < 10:
        print(f"SKIP: {period}期可用事件數<10（樣本不足），不做判定")
        return
    real_vals = [getattr(e, metric) for e in period_events]
    real_mean = sum(real_vals) / len(real_vals)
    print(f"real mean({metric})={real_mean:+.4%}（事前預期方向：{'正' if expect_positive else '負'}）")
    signal_stat = real_mean if expect_positive else -real_mean

    control_draws = {}
    for name, seed in CONTROL_SEEDS.items():
        rng = random.Random(seed)
        draws = [_draw_control_means(period_events, pools, closes_by_ticker, metric, rng)
                 for _ in range(N_CONTROL_DRAWS)]
        draws = [d for d in draws if d == d]
        signed_draws = draws if expect_positive else [-d for d in draws]
        control_draws[name] = signed_draws
        print(f"  control[{name}]: n_draws={len(draws)} raw_mean={sum(draws)/len(draws):+.4%}")

    verdict = evaluate_vs_control(
        signal_stat=signal_stat,
        control_draws=control_draws,
        selection_spec=(
            f"事前綁定：#51-US round（hypothesis_queue接續）{label}，metric={metric}，"
            f"expect_positive={expect_positive}，PRE_WINDOW={PRE_WINDOW}/POST_WINDOW={POST_WINDOW}，"
            f"僅Addition/僅四個市值加權指數(排除DJIA/DJTA)，{period}期，"
            f"per-ticker配對抽樣控制組(buffer={CONTROL_EXCLUSION_BUFFER})，SAMPLE_SIZE={SAMPLE_SIZE} "
            f"seed={SAMPLE_SEED}，非事後選點"
        ),
    )
    print(f"  PASSES cheap gate: {verdict.passed}")
    print(f"  {verdict.reason}")


def main() -> int:
    if holdout.is_holdout_consumed():
        print("ABORT: holdout already consumed, refusing to run")
        return 1

    events_df = load_addition_events()
    all_tickers = sorted(events_df["ticker"].unique().tolist())
    print(f"=== #51-US cheap gate: 指數成分納入(Addition)事件研究 ===")
    print(f"去重後全部候選事件數={len(events_df)}, 全部候選ticker數={len(all_tickers)}")

    rng = random.Random(SAMPLE_SEED)
    sample_tickers = rng.sample(all_tickers, min(SAMPLE_SIZE, len(all_tickers)))
    print(f"本輪抽樣ticker數={len(sample_tickers)}（seed={SAMPLE_SEED}，先小樣本試跑）")

    events_by_ticker: dict[str, list[str]] = {}
    for t, grp in events_df.groupby("ticker"):
        if t in sample_tickers:
            events_by_ticker[t] = grp["effective_date"].tolist()

    all_events: list[EventRow] = []
    pools: dict[str, list[int]] = {}
    closes_by_ticker: dict[str, list[float]] = {}
    skip_summary: dict = {}
    usable = 0
    for t in sample_tickers:
        rows, eligible, calendar, skips = process_ticker(t, events_by_ticker.get(t, []))
        for k, v in skips.items():
            skip_summary[k] = skip_summary.get(k, 0) + v
        if rows or eligible:
            usable += 1
        all_events.extend(rows)
        if eligible:
            px = us_price_series(t)
            pools[t] = eligible
            closes_by_ticker[t] = px["adj_close"].tolist()

    print(f"\n{usable}/{len(sample_tickers)} ticker可用（有價格資料），"
          f"共{len(all_events)}筆可用事件")
    print(f"跳過原因彙總：{skip_summary}")

    holdout.assert_no_holdout_leakage(
        pd.DataFrame({"effective_date": [e.effective_date for e in all_events]}),
        date_col="effective_date", context="sp500_index_changes_gate51us all_events (final)",
    )

    for period in ("TRAIN", "VAL"):
        period_events = [e for e in all_events if e.period == period]
        _run_subtest(f"子測試(a) 生效前{PRE_WINDOW}日壓力", "pre_ret", True,
                     period_events, pools, closes_by_ticker, period)
        _run_subtest(f"子測試(b) 生效後{POST_WINDOW}日反轉", "post_ret", False,
                     period_events, pools, closes_by_ticker, period)

    return 0


if __name__ == "__main__":
    sys.exit(main())
