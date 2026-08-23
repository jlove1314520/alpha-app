"""Cowork 稽核第 3 點：後 decile（放空腳）多為小型股，台股放空實務上常常「無券
可空」（融券限額為 0 或已滿倉），且台股放空還有融券保證金成數、特殊時期臨時限
空令等額外限制（2025-04 那次限空令是臨時措施，2025-05-26 已撤除，但常態性的
融資融券資格清單限制持續有效——查證方式跟結論見下方 `check_shortability()`）。

**這支腳本做兩件事**：
1. `check_shortability()`：對多空回測裡實際出現過的空頭腳股票，查
   `TaiwanStockMarginPurchaseShortSale` 資料集在對應換股日附近的
   `ShortSaleLimit`（融券限額）跟 `ShortSaleTodayBalance`（已用餘額），
   統計有多少比例「根本沒有融券額度」或「額度已經被用滿」——這兩種情況都代表
   實務上很可能借不到券，無法真的執行放空。
2. `run_long_only_vs_market()`：拿掉放空腳，只做多前 decile（真正可以執行的
   部分，不受融券限制），對照的基準改成**大盤指數本身**（TAIEX 日報酬），不是
   score_topn_v1 那種帶抽樣偏差的「同批買進持有」——這樣才是誠實的「不靠放空，
   到底還有沒有 alpha」的檢驗。一樣算實測 beta、配對隨機對照組。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from finmind_client import load_dev
from long_short_backtest import (
    DECILE_FRACTION, MAX_PLAUSIBLE_DAILY_RETURN, N_RANDOM_DRAWS, RANDOM_CONTROL_SEED,
    START_DATE, _get_scored, capm_beta as _capm_beta_longshort,
)
from validation import costs as costmod
from validation import holdout


def check_shortability(data: dict[str, pd.DataFrame], industry_map: dict, sample_dates: list[str]) -> dict:
    """對 sample_dates（換股日）逐一算空頭腳名單，查每檔的融券限額/餘額，
    回傳統計摘要。全部走 `load_dev()`（自動截斷在 VAL_END），不會碰到 holdout。
    """
    shorts_all = set()
    for d in sample_dates:
        cs = _get_scored(d, data, industry_map)
        n = len(cs)
        if n < 10:
            continue
        k = max(1, int(round(n * DECILE_FRACTION)))
        shorts_all |= set(cs.tail(k)["stock_id"].tolist())

    print(f"多空回測期間，空頭腳總共出現過 {len(shorts_all)} 檔不重複股票，逐一查融券資格...")
    no_margin_list = 0  # 完全查不到融資融券資料（很可能代表不在可融資融券清單上）
    zero_limit = 0      # 有資料，但 ShortSaleLimit 是 0（明確不可融券）
    has_limit = 0        # 有資料且 ShortSaleLimit > 0
    checked = 0

    for sid in shorts_all:
        try:
            raw = load_dev("TaiwanStockMarginPurchaseShortSale", sid, START_DATE)
        except Exception:  # noqa: BLE001
            no_margin_list += 1
            continue
        checked += 1
        if raw.empty or "ShortSaleLimit" not in raw.columns:
            no_margin_list += 1
            continue
        avg_limit = raw["ShortSaleLimit"].replace(0, np.nan).mean()
        if pd.isna(avg_limit) or avg_limit == 0:
            zero_limit += 1
        else:
            has_limit += 1

    print(f"  完全查不到融資融券資料（極可能不可融券）：{no_margin_list}/{len(shorts_all)}")
    print(f"  有資料但融券限額為 0（明確不可融券）：{zero_limit}/{len(shorts_all)}")
    print(f"  有非零融券限額（原則上可融券，仍受當下餘額/借券成本限制）：{has_limit}/{len(shorts_all)}")
    unshortable_pct = (no_margin_list + zero_limit) / len(shorts_all) * 100 if shorts_all else float("nan")
    print(f"  推估「不可空」比例：{unshortable_pct:.1f}%")
    return {
        "total_shorts": len(shorts_all), "no_margin_list": no_margin_list,
        "zero_limit": zero_limit, "has_limit": has_limit, "unshortable_pct": unshortable_pct,
    }


def _longonly_legs(as_of, data, industry_map):
    cs = _get_scored(as_of, data, industry_map)
    n = len(cs)
    if n < 10:
        return []
    k = max(1, int(round(n * DECILE_FRACTION)))
    return cs.head(k)["stock_id"].tolist()


def _random_longonly_legs(as_of, data, industry_map, rng):
    cs = _get_scored(as_of, data, industry_map)
    pool = cs["stock_id"].tolist()
    n = len(pool)
    if n < 10:
        return []
    k = max(1, int(round(n * DECILE_FRACTION)))
    if n < k:
        return []
    return rng.sample(pool, k)


def run_long_only(data, market_df, start, end, rebalance_days, industry_map, leg_fn):
    idx = {sid: d.set_index("date") for sid, d in data.items()}
    calendar = sorted(d for d in market_df["date"] if start <= d <= end)
    if not calendar:
        raise ValueError("空的日曆區間")

    longs = []
    rows = []
    equity = 1.0
    for i, day in enumerate(calendar):
        if i % rebalance_days == 0:
            new_longs = leg_fn(day, data, industry_map)
            if new_longs:
                turnover = 1.0 if not longs else len(set(new_longs) ^ set(longs)) / (2 * len(new_longs))
                cost = turnover * costmod.round_trip_cost_pct(slippage_bps=costmod.DEFAULT_SLIPPAGE_BPS)
                equity *= (1 - cost)
                longs = new_longs
        if i == 0:
            rows.append({"date": day, "port_return": 0.0, "equity": equity})
            continue
        prev_day = calendar[i - 1]
        rets = []
        for sid in longs:
            if sid not in idx:
                continue
            df = idx[sid]
            if day not in df.index or prev_day not in df.index:
                continue
            p0, p1 = df.loc[prev_day, "adj_close"], df.loc[day, "adj_close"]
            if p0 and p0 > 0 and not pd.isna(p0) and not pd.isna(p1):
                r = p1 / p0 - 1
                if abs(r) > MAX_PLAUSIBLE_DAILY_RETURN:
                    continue
                rets.append(r)
        port_ret = float(np.mean(rets)) if rets else 0.0
        equity *= (1 + port_ret)
        rows.append({"date": day, "port_return": port_ret, "equity": equity})
    return pd.DataFrame(rows)


def annualized_return(result: pd.DataFrame) -> float:
    n_days = len(result)
    if n_days < 2:
        return float("nan")
    total_return = result["equity"].iloc[-1] / result["equity"].iloc[0] - 1
    years = n_days / 252.0
    return (1 + total_return) ** (1 / years) - 1 if years > 0 else float("nan")


def sortino_ratio(result: pd.DataFrame) -> float:
    rets = result["equity"].pct_change().iloc[1:]
    if len(rets) < 2:
        return float("nan")
    downside = rets[rets < 0]
    downside_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
    if downside_dev == 0:
        return float("nan")
    return float(rets.mean() / downside_dev * np.sqrt(252))


def capm_beta_vs_market(result: pd.DataFrame, market_df: pd.DataFrame) -> tuple[float, float]:
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = result.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return float("nan"), float("nan")
    beta, alpha_daily = np.polyfit(merged["mkt_return"].values, merged["net_return"].values, 1)
    alpha_annualized = (1 + alpha_daily) ** 252 - 1
    return float(beta), float(alpha_annualized)


def run_period(label, data, market_df, industry_map, start, end, cadence_name, rebalance_days):
    print(f"\n=== {label}（{cadence_name}換股，每{rebalance_days}個交易日）：{start}..{end} ===")
    result = run_long_only(data, market_df, start, end, rebalance_days, industry_map, _longonly_legs)
    ann_ret = annualized_return(result)
    sortino = sortino_ratio(result)
    beta, alpha_ann = capm_beta_vs_market(result, market_df)

    mkt_start = market_df[market_df["date"] >= start].iloc[0]["close"]
    mkt_end = market_df[market_df["date"] <= end].iloc[-1]["close"]
    mkt_total_ret = (mkt_end / mkt_start - 1) * 100
    total_ret_pct = (result["equity"].iloc[-1] / result["equity"].iloc[0] - 1) * 100

    print(f"  純多前decile總報酬(扣成本)：{total_ret_pct:+.2f}%  年化：{ann_ret*100:+.2f}%  Sortino：{sortino:.3f}")
    print(f"  對大盤(TAIEX)實測beta：{beta:+.3f}  年化alpha：{alpha_ann*100:+.2f}%")
    print(f"  同期TAIEX本身報酬：{mkt_total_ret:+.2f}%（超額報酬：{total_ret_pct-mkt_total_ret:+.2f}pp）")

    print(f"  隨機對照組（{N_RANDOM_DRAWS}次重抽，同換股時點/檔數/成本，純多不放空）...")
    random_finals = []
    for i in range(N_RANDOM_DRAWS):
        rng = random.Random(RANDOM_CONTROL_SEED + i)
        rr = run_long_only(data, market_df, start, end, rebalance_days, industry_map,
                            lambda a, d, im, _rng=rng: _random_longonly_legs(a, d, im, _rng))
        random_finals.append(rr["equity"].iloc[-1])
    real_final = result["equity"].iloc[-1]
    pct = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    print(f"  真實策略期末權益 {real_final:.4f} vs 隨機對照組中位數 {np.median(random_finals):.4f} -- 百分位 {pct:.1f}")

    return {
        "label": label, "cadence": cadence_name, "start": start, "end": end,
        "total_return_pct": total_ret_pct, "annualized_return_pct": ann_ret * 100,
        "sortino": sortino, "beta": beta, "annualized_alpha_pct": alpha_ann * 100,
        "market_total_return_pct": mkt_total_ret, "excess_vs_market_pp": total_ret_pct - mkt_total_ret,
        "random_control_percentile": pct,
    }
