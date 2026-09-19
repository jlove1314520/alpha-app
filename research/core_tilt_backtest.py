# -*- coding: utf-8 -*-
"""
core_tilt SPEC（`CORE_TILT_SPEC.md` v3）TE可行性驗證（2026-09-19總司令裁示
【#63邊緣案例＋安全邊際倍數重新錨定】三，成本.二稽核fork執行）。

**問題**：`成本.三`發現12組既有構造（`portfolio_multifactor_v2`）在新統計
關卡下全FAIL（MDE>鎖定目標alpha 2.89%），反推需要TE≈2.06%（見docstring
末尾的反推結果）。但那12組構造的加權方式是equal/ic_weighted/regime_
weighted，**都不是`CORE_TILT_SPEC.md`設計的市值加權為底+主動權重帶**
機制——`core_tilt_backtest.py`（本檔案）至今從未被實際回測過。本腳本
補上這個空缺：用最小但真實的市值加權+因子傾斜+主動權重帶+產業中性
構造，實測不同(持股數,主動權重帶)組合下的實際年化追蹤誤差，回答
「反推出來的TE在實務上做不做得到」。

**為什麼不重用`backtest/engine.py::run_backtest()`**：那支引擎是固定
equal-weight-per-slot設計（`slot_allocation = initial_capital /
max_positions`），結構上無法表示市值加權或主動傾斜權重的組合。本腳本
改寫一個獨立的「月頻換股＋權重隨股價漂移＋換股時扣turnover成本」權益
曲線模擬器，輸出格式跟`power_budget.py::realized_tracking_error()`
期待的`equity_curve`（date,equity兩欄，日頻）相容，兩者可以直接對接。

**市值代理（誠實揭露，非精確市值）**：本機快取沒有股數/精確市值資料集，
用`market_cap_i(t) ≈ PBR_i(t) × Equity_i(t)`（PBR來自`TaiwanStockPER`
快取；Equity來自`TaiwanStockBalanceSheet`的`Equity`列，用同`research/
feature_clustering_v1.py::_capital_stock_asof()`一樣的+45天PIT延遲近似
慣例，避免用到未公告的財報數字）。這是近似值，可能因庫藏股/私募等
股本變動細節而失準，但作為市值加權基底的排序/權重依據，方向性應該
還算穩。

**傾斜訊號**：沿用`portfolio_backtest_v2.py::compute_composite_at_date()`
的A_4pass因子版本、equal加權模式（已通過驗證的既有訊號組合），這裡只
測試「權重機制」本身壓低TE的能力，不重新驗證訊號本身的alpha。

**主動權重帶的訊號映射**：在入選（top-`holdings`）股票內把因子綜合分
做min-max正規化到[-1,+1]，乘上`band`得到每檔的權重偏移`deviation_i`，
`raw_weight_i = max(0, market_cap_weight_i + deviation_i)`後renormalize
——這是「用滿整個允許帶寬」的設計，測的是這個機制在最大幅度傾斜下的
TE，不是某個溫和傾斜下的TE（更保守：真實運作大概率傾斜幅度更小、TE
應該更低，所以本腳本量出來的TE可視為「這個band設定下的上界」）。

**產業中性（簡化版，非完整QP求解，誠實揭露）**：用市值權重本身當0050
產業權重的代理（精確0050成分股權重重建是另一個未解決的SPEC問題，見
`CORE_TILT_SPEC.md`2.1節）。若某產業最終權重偏離代理值超過±3pp，把
該產業內所有股票的權重按比例縮放回界限內，多出/不足的權重差額按其餘
產業原本的市值權重比例分配。這是啟發式調整，不是精確最適化。

**Turnover成本**：跟`equal_weight_rebalance_costs_v1.py`/`min_variance_
portfolio_gate59_costs.py`同一種慣例——`cost = turnover × round_trip_
cost_pct(commission_discount=0.18)`（用`成本.一`更正後的1.8折實際折數，
不是保守的無折扣假設），`turnover = 0.5 × Σ|w_target,i − w_drifted,i|`
（`w_drifted`是上次換股後、隨股價自然漂移到本次換股前一刻的權重）。

**反推所需TE（見`min_detectable_alpha()`反解，`CORE_TILT_TE_FEASIBILITY.md`
有完整推導與所有n_years的表）**：目標alpha=2.89%、n_years=4.0（VAL期
長度，TRAIN_END=2020-12-31/VAL_END=2024-12-31）時，需要TE≈**2.0631%**。

**零新增API呼叫**：全部用`finmind_client`本機parquet快取（`TaiwanStockPrice`/
`TaiwanStockPER`/`TaiwanStockBalanceSheet`/`TaiwanStockInfo`），不重新抓取。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import finmind_client as fc
import portfolio_backtest_v2 as pb2
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids, load_sample_with_factors
from finmind_client import load_dev
from power_budget import realized_tracking_error, min_detectable_alpha, LOCKED_TARGET_ALPHA_PCT
from score import load_industry_map
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
from validation.costs import round_trip_cost_pct

PIT_LAG_DAYS = 45  # 跟feature_clustering_v1.py同一個財報公告延遲近似值
REBALANCE_EVERY_N_DAYS = 21  # 月頻，同portfolio_backtest_v2.py既有慣例
INDUSTRY_BAND_PP = 0.03  # 產業中性 ±3pp（CORE_TILT_SPEC.md第3節）
INITIAL_CAPITAL = 1_000_000.0
COMMISSION_DISCOUNT = 0.18  # 成本.一更正後的1.8折實際折數

HOLDINGS_GRID = [20, 30, 40]
BAND_GRID_PP = [0.01, 0.02, 0.03]  # 主動權重帶 1pp/2pp/3pp

OUT_JSON = Path(__file__).parent / "core_tilt_backtest_result.json"


def _cached_balance_sheet(stock_id: str) -> pd.DataFrame | None:
    for f in sorted(Path(fc.DATA_DIR).glob(f"TaiwanStockBalanceSheet__{stock_id}__*.parquet"),
                     key=lambda p: p.stat().st_size, reverse=True):
        df = pd.read_parquet(f)
        if not df.empty:
            return df
    return None


def _equity_asof(bs: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    eq = bs[bs["type"] == "Equity"].copy()
    if eq.empty:
        return None
    eq["date"] = pd.to_datetime(eq["date"])
    cutoff = asof - pd.Timedelta(days=PIT_LAG_DAYS)
    eq = eq[eq["date"] <= cutoff]
    if eq.empty:
        return None
    return float(eq.sort_values("date").iloc[-1]["value"])


def _cached_per(stock_id: str) -> pd.DataFrame | None:
    best = None
    for f in sorted(Path(fc.DATA_DIR).glob(f"TaiwanStockPER__{stock_id}__*.parquet"),
                     key=lambda p: p.stat().st_size, reverse=True):
        df = pd.read_parquet(f)
        if not df.empty:
            best = df
            break
    return best


def build_market_cap_lookup(stock_ids: list[str]) -> dict[str, dict]:
    """回傳{stock_id: {"per_df":..., "bs":...}}，供build_market_caps_at_date()逐日查。"""
    out = {}
    for sid in stock_ids:
        per = _cached_per(sid)
        bs = _cached_balance_sheet(sid)
        if per is None or bs is None:
            continue
        per = per.copy()
        per["date"] = pd.to_datetime(per["date"])
        out[sid] = {"per": per.sort_values("date"), "bs": bs}
    return out


def market_cap_at_date(sid: str, asof: pd.Timestamp, mc_lookup: dict) -> float | None:
    rec = mc_lookup.get(sid)
    if rec is None:
        return None
    per = rec["per"]
    row = per[per["date"] <= asof]
    if row.empty:
        return None
    pbr = row.iloc[-1]["PBR"]
    if pd.isna(pbr) or pbr <= 0:
        return None
    equity = _equity_asof(rec["bs"], asof)
    if equity is None or equity <= 0:
        return None
    return float(pbr) * float(equity)


def build_target_weights(as_of: str, data: dict, industry_map: dict, mc_lookup: dict,
                          holdings: int, band_pp: float) -> pd.Series | None:
    """回傳{stock_id: weight}（sum=1），或None(資格池不足)。"""
    cs = pb2._eligible(pb2.compute_composite_at_date(
        as_of, data, industry_map, pb2.FACTOR_VERSIONS["A_4pass"], "equal",
        pd.Series(dtype=object), {}))
    if cs.empty:
        return None
    asof_ts = pd.Timestamp(as_of)
    caps = {}
    for sid in cs["stock_id"]:
        mc = market_cap_at_date(sid, asof_ts, mc_lookup)
        if mc is not None:
            caps[sid] = mc
    cs = cs[cs["stock_id"].isin(caps)].copy()
    if len(cs) < max(10, holdings // 2):
        return None
    top = cs.head(holdings).copy()
    top["market_cap"] = top["stock_id"].map(caps)
    total_cap = top["market_cap"].sum()
    if total_cap <= 0:
        return None
    top["w_mktcap"] = top["market_cap"] / total_cap

    comp = top["composite"].astype(float)
    lo, hi = comp.min(), comp.max()
    if hi > lo:
        z = 2 * (comp - lo) / (hi - lo) - 1
    else:
        z = comp * 0.0
    top["deviation"] = z * band_pp
    top["w_raw"] = (top["w_mktcap"] + top["deviation"]).clip(lower=0.0)
    if top["w_raw"].sum() <= 0:
        return None
    top["w_final"] = top["w_raw"] / top["w_raw"].sum()

    # 產業中性簡化調整：industry weight偏離市值權重代理超過INDUSTRY_BAND_PP就縮放。
    w = top.set_index("stock_id")["w_final"]
    ind = top.set_index("stock_id")["industry"]
    w_cap_proxy = top.set_index("stock_id")["w_mktcap"]
    ind_actual = w.groupby(ind).sum()
    ind_proxy = w_cap_proxy.groupby(ind).sum()
    for industry in ind_actual.index:
        dev = ind_actual[industry] - ind_proxy.get(industry, 0.0)
        if abs(dev) > INDUSTRY_BAND_PP:
            members = ind[ind == industry].index
            target_ind_weight = ind_proxy.get(industry, 0.0) + np.sign(dev) * INDUSTRY_BAND_PP
            scale = target_ind_weight / ind_actual[industry] if ind_actual[industry] > 0 else 1.0
            excess = (w.loc[members] * (1 - scale)).sum()
            w.loc[members] = w.loc[members] * scale
            others = w.index.difference(members)
            if len(others) and w.loc[others].sum() > 0:
                w.loc[others] = w.loc[others] + excess * (w.loc[others] / w.loc[others].sum())
    w = w / w.sum()
    return w


def simulate_equity_curve(data: dict, market_df: pd.DataFrame, industry_map: dict,
                           mc_lookup: dict, holdings: int, band_pp: float) -> pd.DataFrame:
    calendar = sorted(d for d in market_df["date"]
                       if holdout.TRAIN_END < d <= holdout.VAL_END)
    if not calendar:
        return pd.DataFrame(columns=["date", "equity"])
    rebalance_days = calendar[::REBALANCE_EVERY_N_DAYS]

    price_idx = {sid: d.set_index("date")["adj_close"] for sid, d in data.items()}
    shares: dict[str, float] = {}
    equity_rows = []
    equity = INITIAL_CAPITAL

    for i, day in enumerate(calendar):
        if day in rebalance_days:
            prices_today = {sid: price_idx[sid].get(day) for sid in shares}
            prices_today = {sid: p for sid, p in prices_today.items() if p is not None and p > 0}
            equity_pre = sum(shares[sid] * prices_today[sid] for sid in prices_today) if prices_today else equity
            if equity_pre <= 0:
                equity_pre = equity
            w_drifted = {sid: shares[sid] * prices_today[sid] / equity_pre for sid in prices_today}

            target = build_target_weights(day, data, industry_map, mc_lookup, holdings, band_pp)
            if target is None:
                target = pd.Series(w_drifted) if w_drifted else pd.Series(dtype=float)

            all_sids = set(w_drifted) | set(target.index)
            turnover = 0.5 * sum(abs(target.get(sid, 0.0) - w_drifted.get(sid, 0.0)) for sid in all_sids)
            cost_pct = turnover * round_trip_cost_pct(commission_discount=COMMISSION_DISCOUNT)
            equity_post = equity_pre * (1 - cost_pct)

            new_shares = {}
            for sid, w in target.items():
                p = price_idx[sid].get(day)
                if p is not None and p > 0 and w > 0:
                    new_shares[sid] = w * equity_post / p
            shares = new_shares
            equity = equity_post

        prices_today = {sid: price_idx[sid].get(day) for sid in shares}
        prices_today = {sid: p for sid, p in prices_today.items() if p is not None and p > 0}
        equity = sum(shares[sid] * prices_today[sid] for sid in prices_today) if prices_today else equity
        equity_rows.append({"date": day, "equity": equity})

    return pd.DataFrame(equity_rows)


def main():
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    print(f"market_df: {len(market_df)}天")

    ids = sample_universe_ids(SAMPLE_SIZE)
    print(f"樣本宇宙: {len(ids)}檔，開始載入因子(全部走本機快取)...")
    data = load_sample_with_factors(ids, market_df)
    print(f"因子資料可用: {len(data)}/{len(ids)}檔")

    mc_lookup = build_market_cap_lookup(list(data.keys()))
    print(f"市值代理(PBR×Equity)可用: {len(mc_lookup)}/{len(data)}檔")

    industry_map = load_industry_map()

    required_te = 2.89 * (4.0 ** 0.5) / (1.959963985 + 0.841621234)
    print(f"\n反推所需TE(target=2.89%, n_years=4): {required_te:.4f}%\n")

    results = {"_meta": {"required_te_pct": round(required_te, 4),
                          "n_universe": len(ids), "n_with_factors": len(data),
                          "n_with_market_cap": len(mc_lookup),
                          "commission_discount": COMMISSION_DISCOUNT}}
    grid_rows = []
    for holdings in HOLDINGS_GRID:
        for band_pp in BAND_GRID_PP:
            key = f"holdings{holdings}_band{int(band_pp*100)}pp"
            print(f"=== {key} ===")
            eq = simulate_equity_curve(data, market_df, industry_map, mc_lookup, holdings, band_pp)
            if eq.empty or len(eq) < 60:
                print("  資料不足，跳過")
                results[key] = {"skipped": "insufficient_data", "n_days": len(eq)}
                continue
            te = realized_tracking_error(eq, market_df)
            mda = min_detectable_alpha(te["annual_te_pct"], te.get("n_years", float("nan")))
            passes = bool(te["annual_te_pct"] <= required_te) if te["annual_te_pct"] == te["annual_te_pct"] else False
            print(f"  realized_TE={te['annual_te_pct']}%  n_years={te.get('n_years')}  "
                  f"beta={te['beta']}  MDE={mda['mde_80pct_power_alpha_pct']}%  "
                  f"達標(TE<={required_te:.4f}%)={passes}")
            results[key] = {"holdings": holdings, "band_pp": band_pp, **te, **mda,
                             "meets_required_te": passes}
            grid_rows.append((holdings, band_pp, te["annual_te_pct"], passes))

    any_pass = any(r[3] for r in grid_rows)
    results["_summary"] = {
        "grid": grid_rows, "any_combination_meets_required_te": any_pass,
        "verdict": "EXPERIMENTAL" if any_pass else "FAIL",
    }
    print(f"\n=== 總結：{'至少一組達標' if any_pass else '沒有任何一組達標'} ===")
    for h, b, t, p in grid_rows:
        print(f"  holdings={h} band={b*100:.0f}pp TE={t}% {'PASS' if p else 'FAIL'}")

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
