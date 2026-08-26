"""主線 1（2026-08-26 使用者裁示）：情境條件式因子檢驗 (regime-conditional IC)。

背景：`f_foreign_streak`（#3）、`f_rel_strength`（#5）、`f_quality_roe_stability`
深挖最終版（#17）這三個候選在 train/val 兩期出現方向相反的結果。過去的處理方式是
直接判 FAIL（"跨期一致關卡沒過"），但使用者這輪要求先徹底調查：這個方向反轉是不是
可以被「事前可觀測」的市場條件系統性地解釋（例如大盤多頭時方向為正、空頭時方向為
負，train/val 剛好落在不同狀態，才誤判成「不穩定」）。同時對 4 個已通過 IC 檢定的
因子（`f_eps_growth`/`f_eps_surprise`/`f_revenue_surprise`/`f_low_vol`）也各做一次
同樣的分群，檢查它們是否在特定情境下特別強（這是新增的分析，不是重測已知結果）。

**四組事前可觀測條件**：
  (a) 大盤位階：沿用 `strategies/weinstein_stage2.py::prepare_market_data()` 已經在用
      的 200 日均線 gate（TAIEX close > MA200 = 多頭，這個專案原本就把這條線當「年線」
      用，不是這輪新發明的定義）。**市場層級**分組——同一天所有股票共用同一個標籤。
  (b) 波動度環境：TAIEX 20 日已實現波動度（年化）跟「擴張窗中位數」比較，只用當下
      及之前的歷史（`.expanding()`），不看未來，避免用未來資訊定義「現在算高波動」。
      **市場層級**分組。
  (c) 市值規模：個股 PIT-safe 的擴張窗平均成交金額（`Trading_money`，跟 factors.py
      `f_inst_flow` 用的流動性替代市值一致，理由見 factors.py docstring：
      `TaiwanStockMarketValue` 是付費資料集）在每個快照日當天，對樣本內所有股票做
      三等分（大/中/小）。**個股層級**分組——同一天不同股票可能落在不同組。
  (d) 流動性/量能：個股「最近 20 日均量」相對「自己過去 120 日均量」的比值，中位數
      切高/低——這個跟 (c) 刻意選不同構面：(c) 是「這檔股票在同儕裡算大還小」（跨股票
      橫斷面比較），(d) 是「這檔股票現在的量能相對自己平常算高還低」（跟自己比較，
      抓的是量能瞬間放大/萎縮的狀態，不是規模本身）。**個股層級**分組。

**方法**：對每個 (因子, 條件, 組別) 組合，只用落在該組的股票-快照觀測值算 Spearman
IC（橫斷面排序相關），跟 `factor_ic.py` 同一套 20 個交易日遠期報酬定義，橫跨
`SNAPSHOT_START`(2015-01-01)～`VAL_END`(train+val 都算進去，這裡的目的是看「條件」
能不能解釋方向，不是重做 train/val 跨期穩定性檢定，那件事 factor_ic.py 已經做過)。
**樣本 < 100 筆觀測值（不是快照數，是股票-快照配對數）不下結論**（憲法鐵律），標記
「樣本不足，待全市場複驗」。

**判定規則（使用者裁示）**：兩組的 IC 平均值方向相反、且都達到 100 筆觀測值門檻 →
「方向能被這個條件系統性區分」，記進 `LEADS.md` 升格「情境切換策略候選」；不能同時
滿足（樣本不足、或方向其實一致只是量級不同）→ 誠實記錄「這個條件無法解釋方向反轉」，
不是含糊帶過。

執行方式：`python regime_conditions.py`，結果印出後手動整理進 `REGIME_CONDITIONS.md`
（這支腳本不自動寫 .md，維持這個專案一貫「腳本產生數字、人工/後續步驟整理成文件」
的分工，避免自動產生的文字掩蓋掉需要人判斷的地方）。
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from factor_ic import (
    SAMPLE_SEED, SAMPLE_SIZE, SNAPSHOT_START, START_DATE,
    _cross_section, build_snapshots, load_sample_with_factors, sample_universe_ids,
)
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

REGIME_FACTORS = [
    "f_foreign_streak", "f_rel_strength", "f_quality_roe_stability",  # 方向反轉待調查
    "f_eps_growth", "f_eps_surprise", "f_revenue_surprise", "f_low_vol",  # 已通過，新增檢查
]
MIN_OBS_FOR_CONCLUSION = 100  # 憲法鐵律：樣本<100不下結論（這裡指股票-快照配對數）


def _market_regime_labels(market_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    """date -> {'trend': ..., 'vol': ...}. Both are PIT-safe (only use data up
    to and including that date)."""
    d = market_df.sort_values("date").reset_index(drop=True).copy()
    ret = d["close"].pct_change()
    vol20 = ret.rolling(20, min_periods=20).std() * np.sqrt(252)
    expanding_median = vol20.expanding(min_periods=60).median()
    d["vol_regime"] = np.where(vol20 > expanding_median, "high_vol", "low_vol")
    d["trend_regime"] = np.where(d["gate"], "bull_above_ma", "bear_below_ma")
    out = {}
    for _, row in d.iterrows():
        out[row["date"]] = {"trend": row["trend_regime"], "vol": row["vol_regime"]}
    return out


def _stock_size_and_liquidity(d: pd.DataFrame) -> pd.DataFrame:
    """Adds PIT-safe per-date columns: size_proxy (expanding avg Trading_money,
    only past+current data) and liq_ratio (20d/120d avg volume, current regime
    vs own history). Returns d with these two columns added (does not mutate
    the input in place -- copies first)."""
    dd = d.sort_values("date").reset_index(drop=True).copy()
    dd["size_proxy"] = dd["Trading_money"].expanding(min_periods=20).mean()
    vol20 = dd["volume"].rolling(20, min_periods=20).mean() if "volume" in dd.columns \
        else dd["Trading_Volume"].rolling(20, min_periods=20).mean()
    vol120 = dd["volume"].rolling(120, min_periods=120).mean() if "volume" in dd.columns \
        else dd["Trading_Volume"].rolling(120, min_periods=120).mean()
    dd["liq_ratio"] = vol20 / vol120
    return dd


def grouped_ic_market_level(
    factor_col: str, data: dict[str, pd.DataFrame], snapshots: list[tuple[str, str]],
    date_labels: dict[str, dict[str, str]], label_key: str,
) -> dict[str, dict]:
    """Condition (a)/(b): every stock on a given as_of date shares one label."""
    buckets = defaultdict(list)  # label -> list of per-snapshot IC
    obs_n = defaultdict(int)
    for as_of, fwd in snapshots:
        label = date_labels.get(as_of, {}).get(label_key)
        if label is None:
            continue
        ids, fv, ret = _cross_section(factor_col, (as_of, fwd), data)
        if len(fv) < 10:
            continue
        ic, _ = spearmanr(fv, ret)
        if np.isnan(ic):
            continue
        buckets[label].append(ic)
        obs_n[label] += len(fv)
    return {
        g: {"mean_ic": float(np.mean(ics)), "n_snapshots": len(ics), "n_obs": obs_n[g]}
        for g, ics in buckets.items()
    }


def grouped_ic_stock_level(
    factor_col: str, data: dict[str, pd.DataFrame], sized_data: dict[str, pd.DataFrame],
    snapshots: list[tuple[str, str]], proxy_col: str, mode: str,
) -> dict[str, dict]:
    """Condition (c)/(d): each stock's group is decided per-snapshot-date,
    relative to the other stocks present that same date (cross-sectional).

    mode='tercile' -> 3 groups ('large'/'mid'/'small', proxy_col high=large)
    mode='median'  -> 2 groups ('high'/'low', proxy_col high=high)
    """
    buckets = defaultdict(list)
    obs_n = defaultdict(int)
    for as_of, fwd in snapshots:
        ids, fv, ret = _cross_section(factor_col, (as_of, fwd), data)
        if len(ids) < 10:
            continue
        proxies = []
        for sid in ids:
            sd = sized_data[sid]
            idx = sd.index[sd["date"] == as_of]
            proxies.append(float(sd.loc[idx[0], proxy_col]) if len(idx) and pd.notna(sd.loc[idx[0], proxy_col]) else np.nan)
        proxies = np.array(proxies)
        valid = ~np.isnan(proxies)
        if valid.sum() < 10:
            continue
        fv_v, ret_v, proxies_v, ids_v = fv[valid], ret[valid], proxies[valid], [i for i, v in zip(ids, valid) if v]

        if mode == "tercile":
            q1, q2 = np.percentile(proxies_v, [33.33, 66.67])
            group_of = np.where(proxies_v >= q2, "large", np.where(proxies_v <= q1, "small", "mid"))
        else:  # median
            med = np.median(proxies_v)
            group_of = np.where(proxies_v >= med, "high", "low")

        for g in np.unique(group_of):
            mask = group_of == g
            if mask.sum() < 10:
                continue
            ic, _ = spearmanr(fv_v[mask], ret_v[mask])
            if np.isnan(ic):
                continue
            buckets[g].append(ic)
            obs_n[g] += int(mask.sum())

    return {
        g: {"mean_ic": float(np.mean(ics)), "n_snapshots": len(ics), "n_obs": obs_n[g]}
        for g, ics in buckets.items()
    }


def _fmt_group_result(name: str, res: dict) -> str:
    if not res:
        return f"    {name}: 無資料"
    ok = res["n_obs"] >= MIN_OBS_FOR_CONCLUSION
    flag = "" if ok else "  [樣本不足<100，不下結論，待全市場複驗]"
    return f"    {name}: mean_ic={res['mean_ic']:+.4f}  n_snapshots={res['n_snapshots']}  n_obs={res['n_obs']}{flag}"


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in regime_conditions")
    market_df = prepare_market_data(market_raw)

    print("Loading sample + computing factors (cached after first run)...")
    data = load_sample_with_factors(sample_ids, market_df)
    print(f"  {len(data)}/{len(sample_ids)} usable names")

    sized_data = {sid: _stock_size_and_liquidity(d) for sid, d in data.items()}
    date_labels = _market_regime_labels(market_df)

    calendar = sorted(market_df["date"].tolist())
    snapshots = build_snapshots(calendar, SNAPSHOT_START, holdout.VAL_END)
    print(f"  {len(snapshots)} non-overlapping 20-trading-day snapshots, {SNAPSHOT_START}..{holdout.VAL_END}")

    for factor in REGIME_FACTORS:
        print(f"\n=== {factor} ===")
        n_with_factor = sum(1 for d in data.values() if factor in d.columns and d[factor].notna().any())
        print(f"  ({n_with_factor}/{len(data)} 檔有這個因子的非空值 -- FinMind 額度用盡期間，"
              f"依賴財報/月營收的因子可能只有已快取的股票才有值)")

        print("  (a) 大盤位階:")
        res_a = grouped_ic_market_level(factor, data, snapshots, date_labels, "trend")
        for g in ("bull_above_ma", "bear_below_ma"):
            print(_fmt_group_result(g, res_a.get(g, {})))

        print("  (b) 波動度環境:")
        res_b = grouped_ic_market_level(factor, data, snapshots, date_labels, "vol")
        for g in ("high_vol", "low_vol"):
            print(_fmt_group_result(g, res_b.get(g, {})))

        print("  (c) 市值規模 (流動性替代市值三等分):")
        res_c = grouped_ic_stock_level(factor, data, sized_data, snapshots, "size_proxy", "tercile")
        for g in ("large", "mid", "small"):
            print(_fmt_group_result(g, res_c.get(g, {})))

        print("  (d) 流動性/量能 (20日/120日均量比, 中位數切):")
        res_d = grouped_ic_stock_level(factor, data, sized_data, snapshots, "liq_ratio", "median")
        for g in ("high", "low"):
            print(_fmt_group_result(g, res_d.get(g, {})))


if __name__ == "__main__":
    main()
