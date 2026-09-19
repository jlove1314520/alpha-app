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

**2026-09-19選股邏輯更正（總司令裁示【0050成分股：查證不足，重做，
且需求規格放寬】二，取代下面這段原本「取因子分數前holdings名」的
錯誤設計）**：原設計先用因子分數排序取前N名、才在這個已經被因子篩選
過的子集內做市值加權——這不是「貼齊基準、小幅傾斜」，是重新選股，
結構上保證TE壓不下來（實測驗證：9組holdings×band網格全部FAIL，beta
持續1.35~1.42，band幾乎不影響TE）。改成：先按重建市值排序取前50大
（`TOP_N_BENCHMARK`，近似0050成分股名單，理由與四條查證路徑見
`CORE_TILT_SPEC.md`「2.1.3」節），保留全部50檔，只在這50檔「內部」
用因子綜合分做被`band_pp`限制住的小幅權重偏移（min-max正規化到
[-1,+1]乘上band，再clip到±band_pp），`raw_weight_i = max(0,
w_mktcap_i + deviation_i)`後renormalize；可選允許少數非名單股（市值
前50大以外、因子分數最高的一批）加入，總權重上限`non_list_cap`
（網格{0%,5%,10%}），0%時退化成「純前50大，無例外」，是這個更正
設計最乾淨的測試點。

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

# 2026-09-19總司令裁示【0050成分股：查證不足，重做，且需求規格放寬】二：
# 選股邏輯更正——從「因子分數排序取前N名」改成「重建市值前50大（近似
# 0050成分股名單）保留全部成員、只調整權重」，holdings不再是自由參數
# （固定50，對應台灣50指數本身的定義），band與非名單股權重上限才是
# 真正的自由參數網格。見CORE_TILT_SPEC.md「2.1.3」節的四條查證路徑。
TOP_N_BENCHMARK = 50
BAND_GRID_PP = [0.01, 0.02, 0.03]  # 主動權重帶 1pp/2pp/3pp
NON_LIST_WEIGHT_CAP_GRID = [0.0, 0.05, 0.10]  # 非名單股（前50大以外）總權重上限
NON_LIST_CANDIDATE_POOL = 20  # 非名單候選：市值排名50名以外，因子分數最高的前20檔裡面選

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
                          band_pp: float, non_list_cap: float) -> pd.Series | None:
    """回傳{stock_id: weight}（sum=1），或None(資格池不足)。

    2026-09-19選股邏輯更正：不再用因子分數排序取前N名。改成先按重建
    市值排序取前50大（近似0050成分股名單，保留全部成員），只在這50檔
    「內部」用因子分數做被band_pp限制住的小幅權重傾斜；可選的非名單股
    （市值前50大以外、因子分數最高的一批）總權重上限non_list_cap。
    """
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
    if len(cs) < max(10, TOP_N_BENCHMARK // 2):
        return None
    cs["market_cap"] = cs["stock_id"].map(caps)
    cs = cs.sort_values("market_cap", ascending=False).reset_index(drop=True)

    top = cs.iloc[:TOP_N_BENCHMARK].copy()
    rest = cs.iloc[TOP_N_BENCHMARK:].copy()

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
    top["deviation"] = (z * band_pp).clip(-band_pp, band_pp)
    top["w_raw"] = (top["w_mktcap"] + top["deviation"]).clip(lower=0.0)
    if top["w_raw"].sum() <= 0:
        return None
    top["w_final"] = top["w_raw"] / top["w_raw"].sum() * (1.0 - non_list_cap)

    # 產業中性簡化調整：industry weight偏離市值權重代理超過INDUSTRY_BAND_PP就縮放。
    w = top.set_index("stock_id")["w_final"]
    ind = top.set_index("stock_id")["industry"]
    w_cap_proxy = top.set_index("stock_id")["w_mktcap"] * (1.0 - non_list_cap)
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
    w = w * (1.0 - non_list_cap) / w.sum()

    # 非名單股（市值前50大以外，因子分數最高的一批），總權重固定non_list_cap，
    # 按因子分數(z-score, 只取正值, 全負則等權)比例分配——簡化版，不做最適化。
    if non_list_cap > 0 and not rest.empty:
        cand = rest.sort_values("composite", ascending=False).head(NON_LIST_CANDIDATE_POOL).copy()
        if not cand.empty:
            c = cand["composite"].astype(float)
            c_mean, c_std = c.mean(), c.std(ddof=0)
            cz = (c - c_mean) / c_std if c_std > 0 else c * 0.0
            cz_pos = cz.clip(lower=0.0)
            if cz_pos.sum() > 0:
                cand_w = cz_pos / cz_pos.sum() * non_list_cap
            else:
                cand_w = pd.Series(non_list_cap / len(cand), index=cand.index)
            cand_series = pd.Series(cand_w.values, index=cand["stock_id"].values)
            w = pd.concat([w, cand_series])

    w = w / w.sum()
    return w


def simulate_equity_curve(data: dict, market_df: pd.DataFrame, industry_map: dict,
                           mc_lookup: dict, band_pp: float, non_list_cap: float) -> pd.DataFrame:
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

            target = build_target_weights(day, data, industry_map, mc_lookup, band_pp, non_list_cap)
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


# 2026-09-19新增：路徑3（Wayback Machine）交叉驗證用的錨點。這5檔是
# 依「股票代碼」排序、不是依市值排序（Wayback只封存了每個快照頁面
# 首次載入的前5列，「More」按鈕背後的API沒有被封存），只能驗證「是否
# 為名單成員」，不能驗證排名/權重。見CORE_TILT_SPEC.md「2.1.3」節。
WAYBACK_CONFIRMED_DATES = {
    "2021-10-18": ["1101", "1216", "1301", "1303", "1326"],
    "2022-09-26": ["1101", "1216", "1301", "1303", "1326"],
}


def check_membership_against_wayback(data: dict, industry_map: dict, mc_lookup: dict) -> dict:
    """對WAYBACK_CONFIRMED_DATES每個日期，檢查重建的市值前50大名單是否
    包含那5檔真實成分股（僅能檢查剛好落在SAMPLE_SIZE隨機抽樣宇宙內的
    代碼，這是繼承自factor_ic.sample_universe_ids()的既有限制，不是
    本次新增的簡化）。"""
    out = {}
    for date_str, codes in WAYBACK_CONFIRMED_DATES.items():
        asof = pd.Timestamp(date_str)
        in_sample = [c for c in codes if c in data]
        not_in_sample = [c for c in codes if c not in data]
        caps = {}
        for sid in data:
            mc = market_cap_at_date(sid, asof, mc_lookup)
            if mc is not None:
                caps[sid] = mc
        ranked = sorted(caps, key=lambda s: caps[s], reverse=True)
        top50 = set(ranked[:TOP_N_BENCHMARK])
        hits = [c for c in in_sample if c in top50]
        misses = [c for c in in_sample if c not in top50]
        out[date_str] = {
            "checked_codes_in_random_sample": in_sample,
            "codes_not_in_random_sample_of_300": not_in_sample,
            "hits_in_reconstructed_top50": hits,
            "misses": misses,
            "hit_rate": f"{len(hits)}/{len(in_sample)}" if in_sample else "0/0 (無代碼落在隨機抽樣宇宙內)",
        }
    return out


def returns_based_validation(data: dict, market_df: pd.DataFrame, industry_map: dict,
                              mc_lookup: dict) -> dict:
    """路徑4（交叉驗證，非主來源）：用band=2pp/non_list_cap=0%這組代表性
    構造的日報酬，跟0050真實日報酬（真實價格序列，非重建）比對相關係數。
    """
    eq = simulate_equity_curve(data, market_df, industry_map, mc_lookup, 0.02, 0.0)
    if eq.empty or len(eq) < 60:
        return {"skipped": "insufficient_data_for_returns_validation"}
    # 直接讀本機快取parquet（跳過load_dev()的精確快取鍵比對，避免因
    # start_date字面不同觸發不必要的即時抓取——這裡只是要真實0050日
    # 收盤價序列，不需要load_dev()的holdout裁切保護，讀哪個快取檔都
    # 一樣安全，因為下面join時仍然只會用到VAL期以內、跟equity curve
    # 重疊的日期）。
    price_files = sorted(Path(fc.DATA_DIR).glob("TaiwanStockPrice__0050__*.parquet"),
                          key=lambda p: p.stat().st_size, reverse=True)
    if not price_files:
        return {"skipped": "no_cached_0050_price_data"}
    real_0050 = pd.read_parquet(price_files[0])
    if real_0050.empty:
        return {"skipped": "no_cached_0050_price_data"}
    real_0050 = real_0050.copy()
    real_0050["date"] = pd.to_datetime(real_0050["date"])
    real_ret = real_0050.set_index("date")["close"].sort_index().pct_change().rename("real_0050_return")
    recon_ret = eq.set_index("date")["equity"].pct_change().rename("reconstructed_return")
    merged = pd.concat([real_ret, recon_ret], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"skipped": "insufficient_overlapping_days", "n_days": len(merged)}
    corr = float(merged["real_0050_return"].corr(merged["reconstructed_return"]))
    te_vs_real_0050 = float((merged["reconstructed_return"] - merged["real_0050_return"]).std()
                             * np.sqrt(252) * 100)
    return {"n_days": len(merged), "correlation_with_real_0050_daily_return": round(corr, 4),
            "annualized_diff_std_pct_vs_real_0050": round(te_vs_real_0050, 4)}


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
                          "commission_discount": COMMISSION_DISCOUNT,
                          "top_n_benchmark": TOP_N_BENCHMARK}}
    grid_rows = []
    for band_pp in BAND_GRID_PP:
        for non_list_cap in NON_LIST_WEIGHT_CAP_GRID:
            key = f"band{int(band_pp*100)}pp_nonlist{int(non_list_cap*100)}pct"
            print(f"=== {key} ===")
            eq = simulate_equity_curve(data, market_df, industry_map, mc_lookup, band_pp, non_list_cap)
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
            results[key] = {"band_pp": band_pp, "non_list_cap": non_list_cap, **te, **mda,
                             "meets_required_te": passes}
            grid_rows.append((band_pp, non_list_cap, te["annual_te_pct"], passes))

    any_pass = any(r[3] for r in grid_rows)
    best_te = min((r[2] for r in grid_rows if r[2] == r[2]), default=float("nan"))
    if any_pass:
        branch = "LE_REQUIRED"
    elif best_te == best_te and best_te <= 5.0:
        branch = "BETWEEN_REQUIRED_AND_5PCT"
    else:
        branch = "GT_5PCT"
    results["_summary"] = {
        "grid": grid_rows, "any_combination_meets_required_te": any_pass,
        "best_te_pct": best_te, "branch": branch,
        "verdict": "EXPERIMENTAL" if any_pass else "FAIL",
    }
    print(f"\n=== 總結：{'至少一組達標' if any_pass else '沒有任何一組達標'}（最佳TE={best_te}%，分支={branch}） ===")
    for b, n, t, p in grid_rows:
        print(f"  band={b*100:.0f}pp non_list_cap={n*100:.0f}% TE={t}% {'PASS' if p else 'FAIL'}")

    # 主要網格結果已經算完並存進results——下面兩個交叉驗證失敗也不能讓
    # 已經拿到的主結果不見，各自包一層try/except，出錯只降級成警告字串。
    print("\n=== 路徑3交叉驗證：重建前50大是否包含Wayback確認過的成員代碼 ===")
    try:
        membership = check_membership_against_wayback(data, industry_map, mc_lookup)
        for date_str, res in membership.items():
            print(f"  {date_str}: {res['hit_rate']}  未落在隨機抽樣宇宙內: {res['codes_not_in_random_sample_of_300']}")
    except Exception as e:  # noqa: BLE001 -- 交叉驗證非主結果，出錯降級不中斷主流程
        print(f"  [警告] 路徑3交叉驗證失敗，降級跳過：{e}")
        membership = {"error": str(e)}

    print("\n=== 路徑4交叉驗證：重建組合(band2pp/non_list0%) vs 0050真實日報酬 ===")
    try:
        returns_check = returns_based_validation(data, market_df, industry_map, mc_lookup)
        print(f"  {returns_check}")
    except Exception as e:  # noqa: BLE001 -- 同上
        print(f"  [警告] 路徑4交叉驗證失敗，降級跳過：{e}")
        returns_check = {"error": str(e)}

    results["_meta"]["membership_cross_validation"] = membership
    results["_meta"]["returns_based_cross_validation"] = returns_check

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
