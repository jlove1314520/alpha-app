# -*- coding: utf-8 -*-
"""題材動能榜（scoring-momentum-v1）／未來性濾網（scoring-future-v1）首次
PIT 組合回測——常備.開發-6（2026-10-11 先.六十五 總司令裁示解凍）。

**性質：既有榜單重新驗證（reverification=true），不是新 alpha 試驗。**
裁示原文：「沿用 #390 的新引擎＋新量尺＋0050 含息對照＋全成本跑題材動能榜與
未來性榜；結果只決定 App 標『回測通過／未通過』，不得調因子權重」。所以：

- 權重原樣讀 `weights_frozen_momentum.json`／`weights_frozen_future.json`，
  不掃描、不調整；因子計算**直接 import 上線腳本自己的函式**
  （`generate_scores_momentum._relative_strength()` 等），餵它「as_of 當天
  以前」的歷史視窗，不另寫一份會漂移的複製版。
- 回測框架完全照 #390（`run_value_board_v2_pit_backtest.py`）：同一個
  `backtest/engine.py::run_backtest()`（只呼叫、不改原始碼，十三節）、同一份
  流動性前 500 檔本機快取（`value_board_v2_sample_cache_liquidity500.pkl`，
  486 檔可用，**零 FinMind API 呼叫**）、同一組 TOP_N=20／21 日換股、同一個
  `portfolio_backtest_v2.alpha_significance()`／`buy_and_hold_index_pct()`
  （0050 含息總報酬＋Newey-West HAC＋Dimson beta）、同一套全成本
  （engine 預設手續費＋證交稅＋滑價 5bps）。
- 判定量尺照 #390 最終結案用的那一把（#395 審.三）：VAL 期對 0050 含息的
  Dimson 資訊比率 → 可比試驗 V 點估計 DSR ≥ 0.95 才算通過；另加天條一
  （任一期 MDD 不得超過 −50%）與天條二（VAL 期贏 0050 含息買進持有）。
  三項全過才標「回測通過」，任一不過即「回測未通過」。

**誠實揭露的近似（不是 bug，是歷史資料能做到的上限）**：
1. 宇宙＝#390 同一份「2026 年流動性前 500 檔」清單，固定用在 2015-2024，
   **含前視／存活者偏誤**（今天流動性高＝事後看是贏家），績效系統性高估。
2. `group_breadth`／`sector_capital_flow` 上線版用全市場約 2,800 檔算產業
   統計，回測只能用這 486 檔算（快取只有這些）。
3. 法人買賣超上線版單位是「張」，快取是「股」；因子都是比率或百分位排序，
   單位差 1000 倍不影響排名（`institutional_ownership_pct` 分母同步用
   `CapitalStock/10`＝股數）。
4. 未來性濾網財報（毛利率／營收／非流動資產／股本）走 `pit.py` 法定期限
   PIT 對齊，只讀本機 parquet 快取；快取缺的股票該因子留白（上線版同樣
   以 coverage 加權處理缺值），不打 API。

用法：python research/run_momentum_future_board_pit_backtest.py [--draws N]
"""
from __future__ import annotations

import mem_guard  # 同 #390：多檔全歷史載入的記憶體安全閥
import sys as _sys

# 先.七十-4：開跑前先看可用記憶體（Available）≥4.5GB，不足就不載入任何快取、直接以 exit 3 結束並寫明原因
# （避免載入 500MB 快取途中才被 3GB 安全閥砍掉）。--skip-preflight 只給小樣本邏輯測試用。
if "--skip-preflight" not in _sys.argv:
    _ok, _gb, _msg = mem_guard.preflight()
    print(f"mem_guard.preflight：{_msg}", flush=True)
    if not _ok:
        _sys.exit(3)
mem_guard.install()

import argparse
import json
import pickle
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception as _e:  # noqa: BLE001
        print(f"[警告] stdout/stderr reconfigure 失敗：{_e}")

import numpy as np
import pandas as pd
from scipy import stats as sstats

from backtest.engine import BacktestConfig, run_backtest
from finmind_client import load_dev
from factor_ic import START_DATE
from score import load_industry_map
from score_v2 import LIQUIDITY_FLOOR_20D_VALUE, _pct_score
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from pit import _pivot_with_statutory_pit
from portfolio_backtest_v2 import _load_0050_total_return_series
from comparable_trial_variance import dimson_ir, v_sensitivity_table, MIN_COMPARABLE_FOR_POINT_ESTIMATE
from candidate_report import CandidateStats, deflated_sharpe, default_n_trials
from run_value_board_v2_pit_backtest import (
    TOP_N, REBALANCE_DAYS, VALUE_BOARD_SAMPLE_SIZE,
    buy_and_hold_index_pct, taiex_mdd_sortino, alpha_significance,
    compute_moonshot_stats, sharpe_ratio, cvar_95,
)
import generate_scores_momentum as gsm
import generate_scores_future as gsf
from score_live_momentum import load_frozen_weights_momentum
from score_live_future import load_frozen_weights_future

RESEARCH = Path(__file__).parent
CACHE_PATH = RESEARCH / "data" / "backtests" / f"value_board_v2_sample_cache_liquidity{VALUE_BOARD_SAMPLE_SIZE}.pkl"
RAW_DIR = RESEARCH / "data" / "raw"
OUT_JSON = RESEARCH / "data" / "momentum_future_board_pit_backtest.json"
RANDOM_CONTROL_SEED = 20261011
PRICE_WINDOW_ROWS = 90   # 上線版 data/price_history.json 每檔保留 90 列
INST_WINDOW_DAYS = 5     # 上線版 data/stock_detail.json institutional.history 為 5 日
FIN_WINDOW_QUARTERS = 8  # 上線版 financials.quarters 為近 8 季
STALE_DAYS = 30          # 上線版「價格落後超過30天剔除」同一門檻
TRAIN = ("2015-01-01", holdout.TRAIN_END)
VAL = ("2021-01-01", holdout.VAL_END)
TW_TZ = timezone(timedelta(hours=8))


# ── 每檔前處理：日期索引、市場日曆對齊 ───────────────────────────────────
def _prep_stock(df: pd.DataFrame) -> pd.DataFrame:
    keep = ["date", "close", "adj_close", "volume", "Trading_money", "foreign_net", "trust_net", "dealer_net"]
    d = df.loc[:, ~df.columns.duplicated()].sort_values("date").reset_index(drop=True)
    # 快取混兩種來源：yfinance 列有 `volume`，FinMind 列只有 `Trading_Volume`（同義：成交股數）
    vol = d["volume"] if "volume" in d.columns else pd.Series(np.nan, index=d.index)
    if "Trading_Volume" in d.columns:
        vol = vol.combine_first(d["Trading_Volume"])
    d = d[[c for c in keep if c in d.columns and c != "volume"]].copy()
    d["volume"] = vol.astype(float)
    for c in ("foreign_net", "trust_net", "dealer_net"):
        if c not in d.columns:
            d[c] = np.nan
    d["date"] = d["date"].astype(str)
    d["turnover"] = d["Trading_money"].astype(float)
    d["chg"] = d["adj_close"].astype(float).pct_change()
    return d


def _price_rows(d: pd.DataFrame, end_idx: int) -> list[dict]:
    w = d.iloc[max(0, end_idx - PRICE_WINDOW_ROWS + 1): end_idx + 1]
    return [
        {"date": r.date, "close": float(r.close), "adj_close": float(r.adj_close),
         "volume": float(r.volume) if pd.notna(r.volume) else None,
         "turnover": float(r.turnover) if pd.notna(r.turnover) else None}
        for r in w.itertuples(index=False)
    ]


def _institutional(d: pd.DataFrame, end_idx: int) -> dict | None:
    """把快取的 foreign/trust/dealer 淨買超（股）包成上線版
    `stock_detail.json` institutional 的形狀（近 5 個交易日 history）。"""
    w = d.iloc[max(0, end_idx - INST_WINDOW_DAYS + 1): end_idx + 1]
    hist = []
    for r in w.itertuples(index=False):
        vals = {"foreign_lots": r.foreign_net, "trust_lots": r.trust_net, "dealer_lots": r.dealer_net}
        if all(pd.isna(v) for v in vals.values()):
            continue
        hist.append({k: (None if pd.isna(v) else float(v)) for k, v in vals.items()})
    return {"history": hist} if hist else None


# ── 未來性濾網財報：只讀本機 parquet，不打 API ──────────────────────────
def _load_local_pit(dataset: str, sid: str) -> pd.DataFrame:
    p = RAW_DIR / f"{dataset}__{sid}__{START_DATE}__2024-12-31.parquet"
    if not p.exists():
        return pd.DataFrame()
    try:
        raw = pd.read_parquet(p)
        return _pivot_with_statutory_pit(raw) if not raw.empty else pd.DataFrame()
    except Exception as e:  # noqa: BLE001
        print(f"  [警告] {p.name} 讀取/樞紐失敗：{type(e).__name__}: {e}（該檔財報因子留白）")
        return pd.DataFrame()


def build_fin_tables(ids: list[str]) -> dict[str, dict]:
    out, n_inc, n_bs = {}, 0, 0
    for sid in ids:
        inc = _load_local_pit("TaiwanStockFinancialStatements", sid)
        bs = _load_local_pit("TaiwanStockBalanceSheet", sid)
        q = pd.DataFrame()
        if not inc.empty and {"Revenue", "GrossProfit"} <= set(inc.columns):
            q = inc[["fiscal_period_end", "pit_date", "Revenue", "GrossProfit"]].sort_values("fiscal_period_end")
            n_inc += 1
        b = pd.DataFrame()
        if not bs.empty and "fiscal_period_end" in bs.columns:
            cols = [c for c in ("NoncurrentAssets", "CapitalStock", "OrdinaryShare") if c in bs.columns]
            if cols:
                b = bs[["fiscal_period_end", "pit_date"] + cols].sort_values("fiscal_period_end")
                n_bs += 1
        out[sid] = {"q": q, "b": b}
    print(f"  財報本機快取：損益表 {n_inc}/{len(ids)} 檔、資產負債表 {n_bs}/{len(ids)} 檔（缺者因子留白）")
    return out


def _fin_quarters(fin: dict, as_of: str) -> list[dict]:
    q = fin["q"]
    if q.empty:
        return []
    q = q[q["pit_date"] <= as_of].tail(FIN_WINDOW_QUARTERS)
    rows = []
    for r in q.itertuples(index=False):
        fpe = pd.Timestamp(r.fiscal_period_end)
        rev = float(r.Revenue) if pd.notna(r.Revenue) else None
        gm = (float(r.GrossProfit) / rev * 100) if (rev and pd.notna(r.GrossProfit)) else None
        rows.append({"year": fpe.year, "quarter": (fpe.month - 1) // 3 + 1, "revenue": rev, "gross_margin_pct": gm})
    return rows


def _fin_bs_latest(fin: dict, as_of: str) -> tuple[float | None, float | None]:
    b = fin["b"]
    if b.empty:
        return None, None
    b = b[b["pit_date"] <= as_of]
    if b.empty:
        return None, None
    last = b.iloc[-1]
    nca = float(last["NoncurrentAssets"]) if "NoncurrentAssets" in b.columns and pd.notna(last["NoncurrentAssets"]) else None
    cap = None
    for c in ("CapitalStock", "OrdinaryShare"):
        if c in b.columns and pd.notna(last[c]) and last[c]:
            cap = float(last[c]) / 10.0  # 面額 10 元 → 股數（與快取法人淨買超「股」同單位）
            break
    return nca, cap


# ── 截面計算（每個換股日算一次，結果快取給隨機對照組共用）────────────────
class BoardCrossSection:
    def __init__(self, data: dict, market_df: pd.DataFrame, industry_map: dict, fin: dict):
        # 上線版同一套非個股過濾（ETF/ETN/存託憑證等 industry ＋ 00 開頭代碼格式）
        self.excluded = sorted(sid for sid in data
                               if industry_map.get(sid) in gsm.NON_STOCK_INDUSTRIES
                               or gsm._NON_STOCK_CODE_PATTERN.match(sid))
        if self.excluded:
            print(f"  排除非個股代號 {len(self.excluded)} 檔：{self.excluded[:10]}")
        self.d = {sid: _prep_stock(df) for sid, df in data.items() if sid not in set(self.excluded)}
        self.dates = {sid: d["date"].to_numpy() for sid, d in self.d.items()}
        m = market_df.sort_values("date")
        self.mkt_dates = m["date"].astype(str).to_numpy()
        self.mkt_close = m["close"].astype(float).to_numpy()
        self.industry_map = industry_map
        self.fin = fin
        self.cache: dict[tuple[str, str], pd.DataFrame] = {}

    def _end_idx(self, sid: str, as_of: str) -> int | None:
        arr = self.dates[sid]
        i = int(np.searchsorted(arr, as_of, side="right")) - 1
        if i < 0:
            return None
        last = datetime.strptime(str(arr[i]), "%Y-%m-%d")
        if (datetime.strptime(as_of, "%Y-%m-%d") - last).days > STALE_DAYS:
            return None  # 上線版同一條規則：價格落後超過30天剔除
        return i

    def _liquidity(self, d: pd.DataFrame, i: int) -> float | None:
        t = d["turnover"].iloc[max(0, i - 19): i + 1].dropna()
        return float(t.mean()) if len(t) else None

    def momentum(self, as_of: str, weights: dict) -> pd.DataFrame:
        key = ("momentum", as_of)
        if key in self.cache:
            return self.cache[key]
        j = int(np.searchsorted(self.mkt_dates, as_of, side="right")) - 1
        tx20, tx20d = list(self.mkt_close[max(0, j - 19): j + 1]), list(self.mkt_dates[max(0, j - 19): j + 1])
        tx60, tx60d = list(self.mkt_close[max(0, j - 59): j + 1]), list(self.mkt_dates[max(0, j - 59): j + 1])
        gsm._reset_relative_strength_stats()
        rows, sector_rows, chg_by_ind = [], [], {}
        for sid, d in self.d.items():
            i = self._end_idx(sid, as_of)
            if i is None:
                continue
            pr = _price_rows(d, i)
            ind = self.industry_map.get(sid)
            rs = gsm._relative_strength(pr, tx20, tx20d, tx60, tx60d)
            vb = gsm._volume_breakout(pr)
            nh = gsm._new_high_breakout(pr)
            vp, _ = gsm._volume_price_coordination(pr)
            if nh is not None and nh > 0 and vp is not None and vp < 0:
                nh = nh * 0.3  # 上線版 build_rows() 同一條「無量創高打折」規則
            cc = gsm._chip_concentration(_institutional(d, i))
            if ind:
                for r in pr:
                    if r["turnover"] is not None:
                        sector_rows.append((r["date"], ind, r["turnover"]))
                if str(d["date"].iloc[i]) == as_of and pd.notna(d["chg"].iloc[i]):
                    chg_by_ind.setdefault(ind, []).append(float(d["chg"].iloc[i]) * 100)
            rows.append({"stock_id": sid, "industry": ind,
                         "raw_relative_strength": rs, "raw_volume_breakout": vb,
                         "raw_new_high_breakout": nh, "raw_volume_price_coordination": vp,
                         "raw_chip_concentration": cc, "liquidity_20d": self._liquidity(d, i)})
        if not rows:
            self.cache[key] = pd.DataFrame()
            return self.cache[key]
        cs = pd.DataFrame(rows).set_index("stock_id")
        # 產業資金流（上線版 build_sector_aggregates()+compute_sector_flow_trend()）
        flow = {}
        if sector_rows:
            sdf = pd.DataFrame(sector_rows, columns=["date", "industry", "turnover"])
            sdf = sdf[sdf["date"] <= as_of]
            sector_daily = sdf.groupby(["date", "industry"])["turnover"].sum().unstack(fill_value=0.0)
            mkt_set = set(self.mkt_dates[max(0, j - PRICE_WINDOW_ROWS * 2): j + 1])
            sector_daily = sector_daily.loc[[x for x in sector_daily.index if x in mkt_set]]
            flow = gsm.compute_sector_flow_trend(sector_daily.tail(PRICE_WINDOW_ROWS))
        # 族群齊漲度（上線版 compute_group_breadth()，餵當日漲跌幅）
        quotes = {}
        for ind, pcts in chg_by_ind.items():
            for k, p in enumerate(pcts):
                quotes[f"{ind}#{k}"] = {"change_pct": p}
        ind_map_q = {f"{ind}#{k}": ind for ind, pcts in chg_by_ind.items() for k in range(len(pcts))}
        breadth = gsm.compute_group_breadth(quotes, ind_map_q)
        cs["raw_group_breadth"] = cs["industry"].map(breadth)
        cs["raw_sector_capital_flow"] = cs["industry"].map(flow)
        cs = _score(cs, weights, gsm)
        self.cache[key] = cs
        return cs

    def future(self, as_of: str, weights: dict) -> pd.DataFrame:
        key = ("future", as_of)
        if key in self.cache:
            return self.cache[key]
        rows = []
        for sid, d in self.d.items():
            i = self._end_idx(sid, as_of)
            if i is None:
                continue
            inst = _institutional(d, i)
            fin = self.fin.get(sid) or {"q": pd.DataFrame(), "b": pd.DataFrame()}
            quarters = _fin_quarters(fin, as_of)
            nca, shares = _fin_bs_latest(fin, as_of)
            rows.append({"stock_id": sid,
                         "raw_institutional_buying_streak": gsf._institutional_buying_streak(inst),
                         "raw_institutional_ownership_pct": gsf._institutional_ownership_pct(inst, shares),
                         "raw_institutional_buying_concentration": gsf._institutional_buying_concentration(inst),
                         "raw_gross_margin_level_stability": gsf._gross_margin_level_stability(quarters),
                         "raw_capacity_utilization_proxy": gsf._capacity_utilization_proxy(quarters, nca),
                         "liquidity_20d": self._liquidity(d, i)})
        cs = pd.DataFrame(rows).set_index("stock_id") if rows else pd.DataFrame()
        if not cs.empty:
            cs = _score(cs, weights, gsf)
        self.cache[key] = cs
        return cs


def _score(cs: pd.DataFrame, weights: dict, mod) -> pd.DataFrame:
    """上線版 compute_scores_momentum()/compute_scores_future() 的計分段：
    每個因子 _pct_score(higher_better=True) → 有值因子的權重加權平均（coverage
    加權）→ 流動性門檻 LIQUIDITY_FLOOR_20D_VALUE 以下不進排名。"""
    for key in weights:
        sc, pct = _pct_score(cs[f"raw_{key}"], higher_better=True)
        cs[f"{key}_score"] = sc
    num = sum(cs[f"{k}_score"].fillna(0) * w for k, w in weights.items())
    den = sum(cs[f"{k}_score"].notna() * w for k, w in weights.items())
    cs["total_score"] = (num / den.replace(0, np.nan)).round(1)
    cs["coverage"] = den.round(2)
    cs = cs.dropna(subset=["total_score"]).copy()
    cs["liquidity_insufficient"] = cs["liquidity_20d"].isna() | (cs["liquidity_20d"] < LIQUIDITY_FLOOR_20D_VALUE)
    return cs[~cs["liquidity_insufficient"]]


def make_signal_fn(xs: BoardCrossSection, board: str, weights: dict):
    def signal_fn(price_data, as_of, market_df):
        cs = getattr(xs, board)(as_of, weights)
        if cs.empty:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(TOP_N)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


def make_random_fn(xs: BoardCrossSection, board: str, weights: dict, seed: int):
    rng = random.Random(seed)

    def signal_fn(price_data, as_of, market_df):
        pool = getattr(xs, board)(as_of, weights).index.tolist()
        picks = pool if len(pool) <= TOP_N else rng.sample(pool, TOP_N)
        return {sid: 1.0 for sid in picks}
    return signal_fn


def run_period(board, label, period, xs, weights, data, market_df, n_draws):
    start, end = period
    t0 = time.time()
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=REBALANCE_DAYS, book_name=f"{board}_board_pit")
    res = run_backtest(make_signal_fn(xs, board, weights), data, market_df, cfg)
    bh = buy_and_hold_index_pct(market_df, start, end)
    bh_stats = taiex_mdd_sortino(market_df, start, end)
    alpha = alpha_significance(res.equity_curve, market_df)
    moon = compute_moonshot_stats(res.trades, data)
    print(f"[{board} {label}] 報酬={res.total_return_pct:+.2f}% MDD={res.max_drawdown_pct:.2f}% "
          f"Sortino={res.sortino_ratio:.3f} trades={res.n_trades} | 0050含息買進持有={bh:+.2f}% | "
          f"alpha={alpha['alpha_ann_pct']:+.2f}% beta={alpha['beta']:+.3f} p={alpha['alpha_pvalue']:.4f} "
          f"（{time.time()-t0:.0f}s）", flush=True)
    finals = []
    t1 = time.time()
    for k in range(n_draws):
        rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                              rebalance_every_n_days=REBALANCE_DAYS, book_name=f"{board}_board_random_control")
        rr = run_backtest(make_random_fn(xs, board, weights, RANDOM_CONTROL_SEED + k), data, market_df, rcfg)
        finals.append(rr.final_equity)
        if (k + 1) % 10 == 0:
            print(f"    隨機對照 {k+1}/{n_draws}（{time.time()-t1:.0f}s）", flush=True)
    pctl = 100.0 * float(np.mean([res.final_equity > f for f in finals])) if finals else None
    return res, {
        "label": label, "start": start, "end": end,
        "return_pct": res.total_return_pct, "mdd_pct": res.max_drawdown_pct,
        "sortino": res.sortino_ratio, "n_trades": res.n_trades,
        "sharpe_raw": sharpe_ratio(res.equity_curve), "cvar_95_daily_pct": cvar_95(res.equity_curve),
        "buy_and_hold_0050_tr_pct": bh, "bh_mdd_pct": bh_stats["mdd_pct"],
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "random_control_percentile": pctl, "random_draws": n_draws,
        "moonshot_rate": moon["moonshot_rate"], "big_win_rate": moon["big_win_rate"], "mine_rate": moon["mine_rate"],
    }


def dsr_on_val(val_res, label: str) -> dict:
    """#395 審.三同一把量尺：VAL 期對 0050 含息 Dimson IR → 可比試驗 V 點估計 DSR。"""
    ir = dimson_ir(val_res.equity_curve, label)
    out = {"val_ir": ir}
    cached = json.loads((RESEARCH / "data" / "comparable_trial_variance.json").read_text(encoding="utf-8"))
    v_comp, n_comp = cached["comparable_variance"], cached["n_comparable"]
    out.update(comparable_v=v_comp, n_comparable=n_comp)
    if not ir.get("ok"):
        out["dsr"] = None
        return out
    mkt = _load_0050_total_return_series()
    net = val_res.equity_curve.set_index("date")["equity"].pct_change().rename("net")
    m = pd.concat([net, mkt.pct_change().rename("mkt")], axis=1, join="inner").dropna()
    active = m["net"] - ir["beta_dimson"] * m["mkt"]
    skew = float(sstats.skew(active, bias=False))
    kurt = float(sstats.kurtosis(active, bias=False, fisher=False))
    n_trials, n_src = default_n_trials()
    cst = CandidateStats(sharpe=ir["ir_daily"], n_obs=ir["n_obs"], skew=skew, kurtosis=kurt, periods_per_year=252)
    d = deflated_sharpe(cst, n_trials, v_comp, var_periods_per_year=252)
    out.update(skew=skew, kurtosis=kurt, n_trials=n_trials, n_trials_source=n_src, dsr=d)
    if n_comp is None or n_comp < MIN_COMPARABLE_FOR_POINT_ESTIMATE:
        sens = v_sensitivity_table(n_trials)
        for row in sens:
            row["dsr_at_this_v"] = deflated_sharpe(cst, n_trials, row["v_daily"], var_periods_per_year=252)["dsr"]
        out["sensitivity_table"] = sens
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=30)
    ap.add_argument("--boards", default="momentum,future")
    args = ap.parse_args()

    print(f"讀取本機快取 {CACHE_PATH.name}（零 API 呼叫）...", flush=True)
    with open(CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    for sid, df in data.items():
        holdout.assert_no_holdout_leakage(df, date_col="date", context=f"data[{sid}] momentum/future board backtest")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw momentum/future board backtest")
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()
    fin = build_fin_tables(list(data))
    xs = BoardCrossSection(data, market_df, industry_map, fin)
    print(f"  {len(data)} 檔；industry_map {len(industry_map)} 筆", flush=True)

    weights_by_board = {"momentum": load_frozen_weights_momentum(), "future": load_frozen_weights_future()}
    out = {"generated_at": datetime.now(TW_TZ).isoformat(), "reverification": True,
           "random_draws": args.draws, "universe": f"#390 同一份流動性前{VALUE_BOARD_SAMPLE_SIZE}檔快取（{len(data)}檔可用）",
           "boards": {}}
    for board in args.boards.split(","):
        frozen = weights_by_board[board]
        w = frozen["weights"]
        print(f"\n===== {board}（權重 sha256={frozen['weights_sha256'][:12]}，原樣不調整）=====", flush=True)
        tr_res, tr = run_period(board, "TRAIN", TRAIN, xs, w, data, market_df, args.draws)
        va_res, va = run_period(board, "VALIDATION", VAL, xs, w, data, market_df, args.draws)
        dsr = dsr_on_val(va_res, f"{board}_board_VAL")
        dsr_val = (dsr.get("dsr") or {}).get("dsr")
        gates = {
            "天條一_MDD不超過-50%": bool(tr["mdd_pct"] > -50 and va["mdd_pct"] > -50),
            "天條二_VAL贏0050含息買進持有": bool(va["return_pct"] > va["buy_and_hold_0050_tr_pct"]),
            "DSR_VAL_IR_可比試驗V點估計>=0.95": bool(dsr_val is not None and dsr_val >= 0.95),
        }
        verdict = "回測通過" if all(gates.values()) else "回測未通過"
        print(f"  DSR={dsr_val}  關卡={gates}  → {verdict}", flush=True)
        out["boards"][board] = {"weights_sha256": frozen["weights_sha256"], "train": tr, "val": va,
                                "dsr": dsr, "gates": gates, "verdict": verdict}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
