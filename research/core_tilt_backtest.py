# -*- coding: utf-8 -*-
"""⚠️ 部分SUPERSEDED（2026-09-23總司令裁示【拆除機構約束，改集中版】規.一）：
`CORE_TILT_SPEC.md`已作廢並歸檔至`research/archive/`（目標函數改為單一
「贏0050/S&P500總報酬」，TE約束/市值權重為底+因子傾斜建構法/持股60~80檔
全數連帶作廢）。**本檔案不整支歸檔**——`build_market_cap_lookup()`/
`market_cap_at_date()`（PBR×權益法市值估計）仍被`event_driven_
prototype.py`（方法.二/方法.三）的控制組市值分位配對使用，實測`grep`
確認至少這一處相依，不得移除或破壞介面。本檔案其餘部分（`build_target_
weights()`等TE約束下的市值加權+因子傾斜+產業中性建構邏輯）已隨
`CORE_TILT_SPEC.md`一併作廢，不再是現行策略建構方式，保留原樣供稽核
追溯，新試驗一律走`research/CONCENTRATED_SPEC.md`（規.二）。

core_tilt SPEC（`CORE_TILT_SPEC.md` v3，已作廢，見上方notice）TE可行性
驗證（2026-09-19總司令裁示
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

import mem_guard  # 2026-09-20事件001後盤點：多檔股票x全歷史常駐記憶體的同類風險，量級尚未實測（見INCIDENTS.md/稽核.六），先掛安全閥防止真的失控
mem_guard.install()

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

    # 2026-09-19 bug修正：原本price_idx[sid].get(day)在某支股票當天缺值
    # （NaN或該日期根本不在索引裡，例如個股停牌/單一資料源暫時性缺漏）
    # 時直接回傳None，導致該股票當天被整個排除在權益計算之外——若同一
    # 天只有部分持股缺值，權益會被低估成「只剩沒缺值的那幾檔」，隔天
    # 缺值恢復後又跳回正常水準，製造出不存在的單日暴跌暴漲（實測發現
    # 2021-04-06/2024-12-31兩個這樣的災難性單日跳動，見`CORE_TILT_TE_
    # FEASIBILITY.md`「⚠️後續更正」節）。修法：把每檔股票的價格序列
    # reindex到完整交易日曆再前向填補（forward-fill）。
    #
    # 2026-09-19第二次修正（第一版fix引入的新bug）：forward-fill不能
    # 不設上限——第一版用`.ffill()`（無限期向前延續）修好了「大盤整體
    # 缺值一天」（例如清明連假調整），但若某檔股票的價格快取根本沒有
    # 更新到最新（例如FinMind封鎖冷卻期間某些股票的近期資料抓不到），
    # 無限期forward-fill會讓那檔股票的價格從某個時點起**永遠凍結**，
    # 導致整個投資組合的權益曲線失真地變平（貼近0波動、貼近0 beta，
    # 這正是這一輪重跑時觀測到的異常：TE=0.762%、beta=0.0009，看起來
    # 「表現完美」但其實是「投組事實上沒在動」）。修法：`ffill`加上
    # `limit=5`（5個交易日，約一週，合理涵蓋連假/短暫停牌），超過5天
    # 還是缺值就維持NaN，讓既有的NaN過濾邏輯（下面的`prices_today`
    # 篩選）正確地把這檔股票排除在當天估值之外，不再無限期裝作沒事。
    full_calendar_index = pd.DatetimeIndex(calendar)
    price_idx = {
        sid: d.set_index("date")["adj_close"].reindex(full_calendar_index).ffill(limit=5)
        for sid, d in data.items()
    }
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


# 2026-09-19新增，2026-09-19第二輪（總司令裁示【0050查證採信；但驗證
# 標準改成「報酬吻合」不是「名單吻合」】）補齊全部18個時點：路徑3
# （Wayback Machine）交叉驗證用的錨點，親自逐一開啟18個快照頁面（不是
# 只驗2個）記錄下來的真實資料，非猜測。這5檔是依「股票代碼」排序、
# 不是依市值排序（Wayback只封存了每個快照頁面首次載入的前5列，「More」
# 按鈕背後的API沒有被封存），只能驗證「是否為名單成員」，不能驗證
# 排名/權重——本輪裁示明確這只是「第一層健檢」，不是決定性判準
# （決定性判準是`returns_based_validation()`的報酬吻合度）。
# 15/18個時點親自開啟驗證，3個（2023-10-01/2024-04-30/2025-08-09）
# 因為與相鄰已驗證時點間隔<2個月、同一季內無理由變動，用相鄰時點的
# 名單代入，未逐一開啟（誠實揭露，不是逐筆驗證）。
# 觀察到兩次真實的成分股變動（不是猜測，是實測看到的）：
#   2025-04-25：1326台化 退出，2002中鋼 遞補（第5小代碼變成2002）
#   2025-10-22：1101台泥 退出，2059川湖 遞補
WAYBACK_CONFIRMED_DATES = {
    "2021-10-18": ["1101", "1216", "1301", "1303", "1326"],
    "2021-12-03": ["1101", "1216", "1301", "1303", "1326"],
    "2022-05-25": ["1101", "1216", "1301", "1303", "1326"],
    "2022-09-26": ["1101", "1216", "1301", "1303", "1326"],
    "2023-02-02": ["1101", "1216", "1301", "1303", "1326"],
    "2023-09-22": ["1101", "1216", "1301", "1303", "1326"],
    "2023-10-01": ["1101", "1216", "1301", "1303", "1326"],  # 相鄰時點代入，未逐一開啟
    "2024-02-29": ["1101", "1216", "1301", "1303", "1326"],
    "2024-04-30": ["1101", "1216", "1301", "1303", "1326"],  # 相鄰時點代入，未逐一開啟
    "2024-08-02": ["1101", "1216", "1301", "1303", "1326"],
    "2024-11-12": ["1101", "1216", "1301", "1303", "1326"],
    "2025-04-25": ["1101", "1216", "1301", "1303", "2002"],
    "2025-07-16": ["1101", "1216", "1301", "1303", "2002"],
    "2025-08-09": ["1101", "1216", "1301", "1303", "2002"],  # 相鄰時點代入，未逐一開啟
    "2025-10-22": ["1216", "1301", "1303", "2002", "2059"],
    "2025-11-14": ["1216", "1301", "1303", "2002", "2059"],
    "2026-01-14": ["1216", "1301", "1303", "2002", "2059"],
    "2026-05-14": ["1216", "1301", "1303", "2002", "2059"],
}
# 這18個時點總共用到的所有代碼（去重），健檢時強制把這些代碼的市值
# 資料也算進去，不讓「隨機抽樣宇宙剛好沒抽到」變成健檢做不了的理由
# （2026-09-19第一輪重跑就是撞到這個問題：SAMPLE_SIZE=300隨機抽樣
# 完全沒抽到這5~7檔，健檢直接變成0/0，不是真的驗證失敗）。
WAYBACK_ALL_CODES = sorted({c for codes in WAYBACK_CONFIRMED_DATES.values() for c in codes})


def check_membership_against_wayback(data: dict, industry_map: dict, mc_lookup: dict) -> dict:
    """對WAYBACK_CONFIRMED_DATES每個日期，檢查重建的市值前50大名單是否
    包含當天真實的成分股（`data`/`mc_lookup`呼叫端必須已經用
    `ensure_wayback_codes_present()`把WAYBACK_ALL_CODES補進去，否則
    可能因為隨機抽樣沒抽到而讓健檢失去意義）。回傳90個檢查點的彙總
    （18個時點×最多5檔=至多90點，實際檢查點數視代碼是否成功補進資料
    而定，缺的會誠實列在`codes_unavailable`裡不是靜默跳過）。"""
    out = {}
    total_checks = 0
    total_hits = 0
    for date_str, codes in WAYBACK_CONFIRMED_DATES.items():
        asof = pd.Timestamp(date_str)
        available = [c for c in codes if c in data]
        unavailable = [c for c in codes if c not in data]
        caps = {}
        for sid in data:
            mc = market_cap_at_date(sid, asof, mc_lookup)
            if mc is not None:
                caps[sid] = mc
        ranked = sorted(caps, key=lambda s: caps[s], reverse=True)
        top50 = set(ranked[:TOP_N_BENCHMARK])
        hits = [c for c in available if c in top50]
        misses = [c for c in available if c not in top50]
        total_checks += len(available)
        total_hits += len(hits)
        out[date_str] = {
            "codes_checked": available,
            "codes_unavailable": unavailable,
            "hits_in_reconstructed_top50": hits,
            "misses": misses,
            "hit_rate": f"{len(hits)}/{len(available)}" if available else "0/0",
        }
    out["_summary"] = {
        "total_checkpoints_attempted": sum(len(c) for c in WAYBACK_CONFIRMED_DATES.values()),
        "total_checkpoints_data_available": total_checks,
        "total_hits": total_hits,
        "overall_hit_rate": f"{total_hits}/{total_checks}" if total_checks else "0/0",
    }
    return out


def ensure_wayback_codes_present(ids: list[str]) -> list[str]:
    """把WAYBACK_ALL_CODES補進樣本宇宙id清單（不重複），確保成員資格
    健檢不會因為隨機抽樣沒抽到這幾檔知情代碼而變得沒有意義。"""
    return sorted(set(ids) | set(WAYBACK_ALL_CODES))


REQUIRED_TE_VS_REAL_0050_PASS_PCT = 1.0    # 2026-09-19裁示【0050查證採信；
REQUIRED_TE_VS_REAL_0050_MARGINAL_PCT = 3.0  # 但驗證標準改成「報酬吻合」
# 不是「名單吻合」】二：≤1%→重建合格；1~3%→勉強可用但吃掉大半TE預算
# （目標alpha 2.89%反推的核心TE預算只有2.06%，若光是重建誤差就吃掉
# 1~3%，留給因子傾斜的空間所剩無幾）；>3%→重建不合格，這條路走不通。


def _load_real_0050_returns() -> pd.Series | None:
    """直接讀本機快取parquet（跳過load_dev()的精確快取鍵比對，避免因
    start_date字面不同觸發不必要的即時抓取——這裡只是要真實0050日
    收盤價序列，不需要load_dev()的holdout裁切保護，讀哪個快取檔都
    一樣安全，因為呼叫端join時仍然只會用到VAL期以內、跟equity curve
    重疊的日期）。回傳None代表本機完全沒有快取，呼叫端要誠實回報
    跳過，不得改用即時抓取或編造數字。"""
    price_files = sorted(Path(fc.DATA_DIR).glob("TaiwanStockPrice__0050__*.parquet"),
                          key=lambda p: p.stat().st_size, reverse=True)
    if not price_files:
        return None
    real_0050 = pd.read_parquet(price_files[0])
    if real_0050.empty:
        return None
    real_0050 = real_0050.copy()
    real_0050["date"] = pd.to_datetime(real_0050["date"])
    return real_0050.set_index("date")["close"].sort_index().pct_change().rename("real_0050_return")


def returns_based_validation(data: dict, market_df: pd.DataFrame, industry_map: dict,
                              mc_lookup: dict, band_pp: float = 0.0,
                              non_list_cap: float = 0.0) -> dict:
    """**決定性判準（2026-09-19裁示【0050查證採信；但驗證標準改成
    「報酬吻合」不是「名單吻合」】二）**：不是路徑3的名單重疊度，是
    重建組合（預設band=0/non_list_cap=0，即最純粹的「市值前50大、
    不做任何傾斜」版本，用來單獨測「重建方法本身」的保真度，不混入
    因子傾斜的額外誤差）的日報酬，對0050**真實**日報酬（真實價格
    序列，非重建）的相關係數、年化追蹤誤差、逐年TE。
    """
    eq = simulate_equity_curve(data, market_df, industry_map, mc_lookup, band_pp, non_list_cap)
    if eq.empty or len(eq) < 60:
        return {"skipped": "insufficient_data_for_returns_validation"}
    real_ret = _load_real_0050_returns()
    if real_ret is None:
        return {"skipped": "no_cached_0050_price_data"}
    # 2026-09-19 bug修正：`eq["date"]`來自`simulate_equity_curve()`的
    # `calendar`，而`calendar`源自`market_df["date"]`——這欄位是純字串
    # （`load_dev()`/`adjusted_price_series()`的既有慣例，不是Timestamp），
    # 但`_load_real_0050_returns()`的index是`pd.to_datetime()`轉換過的
    # Timestamp。兩邊型別不同時`pd.concat(...,join="inner")`不會做隱式
    # 型別轉換去對齊，會直接找不到任何重疊列（這正是本函式先前兩次
    # 重跑都回報`insufficient_overlapping_days: n_days=0`的根因，不是
    # 真的沒有重疊日期）。修法：兩邊都明確轉成Timestamp再join。
    recon_ret = eq.set_index("date")["equity"].pct_change().rename("reconstructed_return")
    recon_ret.index = pd.to_datetime(recon_ret.index)
    merged = pd.concat([real_ret, recon_ret], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"skipped": "insufficient_overlapping_days", "n_days": len(merged)}
    corr = float(merged["real_0050_return"].corr(merged["reconstructed_return"]))
    diff = merged["reconstructed_return"] - merged["real_0050_return"]
    te_annual = float(diff.std() * np.sqrt(252) * 100)
    by_year = {}
    for yr, g in diff.groupby(merged.index.year):
        if len(g) >= 20:
            by_year[str(yr)] = round(float(g.std() * np.sqrt(252) * 100), 4)
    if te_annual <= REQUIRED_TE_VS_REAL_0050_PASS_PCT:
        verdict = "PASS_RECONSTRUCTION_VALID"
    elif te_annual <= REQUIRED_TE_VS_REAL_0050_MARGINAL_PCT:
        verdict = "MARGINAL_REPORT_TO_COMMANDER"
    else:
        verdict = "FAIL_RECONSTRUCTION_INVALID"
    return {"n_days": len(merged), "band_pp": band_pp, "non_list_cap": non_list_cap,
            "correlation_with_real_0050_daily_return": round(corr, 4),
            "annualized_te_vs_real_0050_pct": round(te_annual, 4),
            "te_vs_real_0050_by_year_pct": by_year,
            "verdict": verdict}


def main():
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    print(f"market_df: {len(market_df)}天")

    ids = ensure_wayback_codes_present(sample_universe_ids(SAMPLE_SIZE))
    print(f"樣本宇宙: {len(ids)}檔（含強制補入的{len(WAYBACK_ALL_CODES)}檔Wayback健檢代碼），"
          f"開始載入因子(全部走本機快取)...")
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

    # 2026-09-19裁示【0050查證採信；但驗證標準改成「報酬吻合」不是
    # 「名單吻合」】二：下面兩層才是這一輪真正的驗收指標，上面的9組
    # band×non_list_cap網格（vs TAIEX的required_te）是成本.三/上一輪
    # 遺留下來的「策略層」問題（因子傾斜後的core_tilt本身TE多少），
    # 跟這一輪「重建方法本身準不準」是兩個不同層次的問題，兩者都保留
    # 在輸出裡，但**這一輪的判死/放行判準看下面的第二層，不是上面的
    # 9組網格**。
    print("\n=== 第一層健檢（成員資格，非決定性）：重建前50大是否包含"
          "Wayback實測18個時點確認過的成員代碼 ===")
    try:
        membership = check_membership_against_wayback(data, industry_map, mc_lookup)
        for date_str, res in membership.items():
            if date_str == "_summary":
                continue
            print(f"  {date_str}: {res['hit_rate']}  缺資料代碼: {res['codes_unavailable']}")
        print(f"  總計: {membership['_summary']['overall_hit_rate']}"
              f"（{membership['_summary']['total_checkpoints_attempted']}個檢查點裡"
              f"{membership['_summary']['total_checkpoints_data_available']}個有資料可查）")
    except Exception as e:  # noqa: BLE001 -- 交叉驗證非主結果，出錯降級不中斷主流程
        print(f"  [警告] 第一層健檢失敗，降級跳過：{e}")
        membership = {"error": str(e)}

    print("\n=== 第二層（決定性）：重建組合(純市值前50大,band=0/non_list=0) "
          "vs 0050真實日報酬 ===")
    try:
        returns_check_pure = returns_based_validation(data, market_df, industry_map, mc_lookup,
                                                        band_pp=0.0, non_list_cap=0.0)
        print(f"  純重建(無傾斜): {returns_check_pure}")
        returns_check_tilted = returns_based_validation(data, market_df, industry_map, mc_lookup,
                                                          band_pp=0.02, non_list_cap=0.0)
        print(f"  含2pp因子傾斜: {returns_check_tilted}")
    except Exception as e:  # noqa: BLE001 -- 同上
        print(f"  [警告] 第二層驗證失敗，降級跳過：{e}")
        returns_check_pure = {"error": str(e)}
        returns_check_tilted = {"error": str(e)}

    decisive_verdict = returns_check_pure.get("verdict", "ERROR_OR_SKIPPED")
    print(f"\n=== 決定性判定：{decisive_verdict} ===")
    if decisive_verdict == "PASS_RECONSTRUCTION_VALID":
        print("  重建合格，可當基準，繼續core_tilt（上面9組網格的TE數字現在可信）。")
    elif decisive_verdict == "MARGINAL_REPORT_TO_COMMANDER":
        print("  基準勉強可用但吃掉大半TE預算，回報後由總司令裁示。")
    elif decisive_verdict == "FAIL_RECONSTRUCTION_INVALID":
        print("  重建不合格，core_tilt這條路確實走不通——根因是「無法取得或"
              "重建足夠貼近的基準籃子」，不是「因子無效」。")
    else:
        print("  無法判定（資料不足或執行錯誤），不下判定。")

    results["_meta"]["membership_cross_validation"] = membership
    results["_meta"]["returns_based_cross_validation_pure"] = returns_check_pure
    results["_meta"]["returns_based_cross_validation_tilted_2pp"] = returns_check_tilted
    results["_meta"]["decisive_verdict"] = decisive_verdict

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已存：{OUT_JSON}")
    return results


if __name__ == "__main__":
    main()
