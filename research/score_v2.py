"""AI 選股引擎 -- 十分制評分（scoring-v2）。

實作規格：`C:\\alpha\\docs\\Alpha_評分引擎_10分制設計小抄.md`（使用者 2026-08-24 提供，
本模組完全依這份文件為準，函式/欄位/公式都對照小抄章節寫在下面的註解裡）。

**跟 `score.py` 的關係，先講清楚**：`score.py` 是研究端「哪些因子通過統計檢定」的產物
（factor_ic.py 的 IC 檢定 + Bonferroni 累積校正 + 同產業 peer z-score，目的是驗證「這個
訊號是不是真的有選股能力」，非常嚴謹但只有 3 個訊號通過檢定）。這裡是使用者要的另一種、
定位不同的東西：「資料整理與排序」的消費端呈現產品（橫斷面百分位、8 大類別，不宣稱統計
顯著性，App 上明確標「非投資建議」）——兩者不是互相替代，這個檔案完全獨立新增，**沒有
動 score.py 原本任何一個函式**（`run_score_backtest.py`/`long_short_backtest.py` 等研究
腳本都還在用 score.py 原本的東西，不能動）。

八大因子（小抄第三節）：財報成長/營收動能/成長性/籌碼/技術型態/估值(PEG)/機構觀點/題材事件。
其中 `analyst`（機構觀點，台股暫無免費目標價資料源）跟 `catalyst`（題材/事件，使用者這輪
明確指示「不要碰新聞/供應鏈，那是下一輪」）**這輪對每一檔股票都是缺資料**，不是 bug，是
刻意留白，由小抄第四節的「重新分配權重」機制誠實處理（coverage 會低於 1，但通常還在
0.5 門檻之上）。

`growth_quality`（成長性/未來性）簡化揭露：小抄建議「營收 CAGR、毛利率趨勢」，這裡只做了
「近 12 個月營收合計 vs 前 12 個月合計」的年增率（用滾動 12 個月加總平滑掉單月雜訊，跟
`revenue_momentum`的當月 YoY 不同角度，但仍然是營收成長，不是真正跨年度的 CAGR，也沒有
毛利率趨勢——這是刻意的範圍縮減，不是假裝做了更多，`reason`字串裡會誠實寫清楚）。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from pit import month_revenue_pit

# 小抄第三節「因子清單」表格，權重原文照抄，加總必須 = 1.0（下面 assert 檢查）。
FACTOR_DEFS = {
    "earnings_growth":  {"label": "財報成長",       "weight": 0.18, "higher_better": True},
    "revenue_momentum": {"label": "營收動能",       "weight": 0.18, "higher_better": True},
    "growth_quality":   {"label": "成長性/未來性",   "weight": 0.12, "higher_better": True},
    "chips":            {"label": "籌碼",           "weight": 0.14, "higher_better": True},
    "technical":        {"label": "技術型態",       "weight": 0.10, "higher_better": True},
    "valuation_adj":    {"label": "估值(成長調整)",  "weight": 0.12, "higher_better": False},
    "analyst":          {"label": "機構觀點",       "weight": 0.08, "higher_better": True},
    "catalyst":         {"label": "題材/事件",       "weight": 0.08, "higher_better": True},
}
assert abs(sum(f["weight"] for f in FACTOR_DEFS.values()) - 1.0) < 1e-9, "權重加總必須是 1.0"

COVERAGE_MIN_FOR_RANKING = 0.5  # 小抄第四節：低於這個門檻標「資料不足」，預設不進前段推薦
TW_TZ = timezone(timedelta(hours=8))

# 2026-08-26（晚）使用者回報榜單品質問題後新增的常數，逐條對應使用者原話：
REVENUE_BASE_FLOOR = 30_000_000  # 問題1a：去年同月營收基期門檻（新台幣元）。低於這個
# 金額時 YoY% 視為無效（不計入營收動能），不是給高分——基期趨近於零會讓任何小額
# 成長都變成幾百%甚至幾千%的數學假象，這是使用者指出的最嚴重問題。
REVENUE_YOY_HARD_CAP = 2.0  # 問題1b：YoY 成長率硬上限 ±200%，通過基期門檻後仍要夾這個界線。
LIQUIDITY_FLOOR_20D_VALUE = 20_000_000  # 問題2：近20日均成交值門檻（新台幣元），低於此
# 視為「沒人玩的地方漲不了」，不進榜單排名（可留在搜尋結果，標「流動性不足」）。
SIZE_TIER_LABELS = ("small", "mid", "large")  # 問題1d：分層排名的三個規模級距（以近20日均
# 成交值當市值/營收規模的流動性替代指標，跟 factors.py f_inst_flow 用的替代邏輯一致：
# TaiwanStockMarketValue 是付費資料集，這裡沒有另外新增付費依賴）。


# ══════ 額外的兩個原始指標（revenue_momentum 的當月 YoY／growth_quality 的 12個月滾動年增）══════
# 這兩個不在 factors.py::prepare_factors() 既有的欄位裡，用 pit.py 的 month_revenue_pit()
# 重新算（跟 factors.py::_revenue_yoy_acceleration() 用同一套 PIT 對齊邏輯，只是這裡要的是
# yoy 本身，不是 yoy 的加速度）。month_revenue_pit() 底層走 load_dev() 的 parquet 快取，
# 這裡重複呼叫不會真的多打 FinMind API。

def _revenue_yoy_latest(stock_id: str, start_date: str) -> dict:
    """回傳 dict：`yoy`（基期門檻+硬上限後的營收年增率，未通過基期門檻時是 None，
    代表「無效，不計入」而不是 0 分——這是使用者 2026-08-26 指出的最嚴重問題的修正：
    去年同月營收基期趨近於零時，任何小額成長都會變成幾百/幾千%的數學假象，之前
    這裡直接把這個假象數字拿去排名，讓微型股必然佔滿榜首）、`prior_year_revenue`
    （基期本身，NT$，用來判斷是否過門檻，也回傳給呼叫端做「絕對成長金額」比較）、
    `abs_growth`（本月營收 - 去年同月營收，NT$，問題1c 的「絕對成長金額」比較基準）、
    `yoy_uncapped`（未夾上限的原始值，只用於除錯/揭露，不進任何排名計算）。
    """
    empty = {"yoy": None, "prior_year_revenue": None, "abs_growth": None, "yoy_uncapped": None}
    try:
        rev = month_revenue_pit(stock_id, start_date)
    except RuntimeError:
        # 2026-08-26：FinMind 額度用盡等錯誤在這裡也要降級成「沒有這個數字」，
        # 不能讓一檔股票的月營收抓不到就讓整批 compute_scores_v2() 全部崩潰
        # （跟 factors.py 那批因子的降級處理同一個修法）。
        return empty
    if rev.empty:
        return empty
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    prior = prior.rename(columns={"revenue": "revenue_prior_year"})
    rev = rev.merge(prior, on=["revenue_year", "revenue_month"], how="left")
    rev["yoy"] = (rev["revenue"] - rev["revenue_prior_year"]) / rev["revenue_prior_year"].abs()
    # 前一年同月營收是 0（或缺值）時，(x-0)/0 會產生 inf/-inf/nan，不是合法的成長率——
    # 用 np.isfinite() 一併篩掉 inf 和 nan，不要只篩 nan（json 不接受 inf，之前在較大樣本
    # 裡撞到真的有 0 元月營收的股票才發現這個漏洞）。
    last = rev[np.isfinite(rev["yoy"])]
    if last.empty:
        return empty
    row = last.iloc[-1]
    prior_rev = float(row["revenue_prior_year"])
    abs_growth = float(row["revenue"] - row["revenue_prior_year"])
    yoy_uncapped = float(row["yoy"])
    if prior_rev < REVENUE_BASE_FLOOR:
        # 問題1a：基期太小，YoY% 視為無效——不計入營收動能，不是給 0 分或高分，
        # `yoy` 保持 None 讓下游的 _pct_score()/覆蓋率機制正確處理成「這項缺資料」。
        return {"yoy": None, "prior_year_revenue": prior_rev, "abs_growth": abs_growth, "yoy_uncapped": yoy_uncapped}
    yoy_capped = max(min(yoy_uncapped, REVENUE_YOY_HARD_CAP), -REVENUE_YOY_HARD_CAP)  # 問題1b：硬上限
    return {"yoy": yoy_capped, "prior_year_revenue": prior_rev, "abs_growth": abs_growth, "yoy_uncapped": yoy_uncapped}


def _revenue_growth_12m(stock_id: str, start_date: str) -> float | None:
    try:
        rev = month_revenue_pit(stock_id, start_date)
    except RuntimeError:
        return None  # same degrade-not-crash rationale as _revenue_yoy_latest() above
    if rev.empty or len(rev) < 24:
        return None
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    recent12 = rev.tail(12)["revenue"].sum()
    prior12 = rev.iloc[-24:-12]["revenue"].sum()
    if not prior12 or prior12 <= 0:
        return None
    return float(recent12 / prior12 - 1)


def _pct_score(raw: pd.Series, higher_better: bool) -> tuple[pd.Series, pd.Series]:
    """小抄第二節五步驟：去極值(1%/99%) → rank 百分位(0~1) → 方向調整 → ×10。
    樣本數 < 3 時百分位沒有意義，全部回傳 NaN（誠實：資料太少排不出百分位）。
    """
    valid = raw.dropna()
    if len(valid) < 3:
        nan_s = pd.Series(np.nan, index=raw.index)
        return nan_s, nan_s
    lo, hi = valid.quantile(0.01), valid.quantile(0.99)
    clipped = raw.clip(lower=lo, upper=hi)
    pct = clipped.rank(pct=True)  # NaN 自動保持 NaN，1.0 = 最好
    if not higher_better:
        pct = 1 - pct
    score = (pct * 10).round(1)
    return score, pct.round(2)


def _pct_score_within_group(raw: pd.Series, groups: pd.Series, higher_better: bool) -> tuple[pd.Series, pd.Series]:
    """問題1d 的分層排名：跟 `_pct_score()` 同一套去極值(1%/99%)→rank百分位→方向調整
    →×10流程，但改成**在每個 group（規模級距）內部**分別做，不讓小市值/微型股跟
    大型股在同一個池子裡比成長率。組內樣本 < 3 時該組全部回傳 NaN（跟 `_pct_score()`
    一致的「樣本太少排不出百分位」規則），不會用組外的樣本硬湊。"""
    score = pd.Series(np.nan, index=raw.index)
    pct = pd.Series(np.nan, index=raw.index)
    for g in groups.dropna().unique():
        idx = groups[groups == g].index
        sub_score, sub_pct = _pct_score(raw.loc[idx], higher_better)
        score.loc[idx] = sub_score
        pct.loc[idx] = sub_pct
    return score, pct


def _size_tier(liquidity: pd.Series) -> pd.Series:
    """問題1d 用的規模分層：以近20日均成交金額（`liquidity`，PIT-safe，見
    `compute_scores_v2()` 呼叫端如何算）在當下樣本內做三等分（small/mid/large）。
    樣本太少（<10筆有效值）時分層沒有意義，全部歸一組（回傳全部 NaN，等於不分層，
    退回 `_pct_score_within_group()` 的行為近似整批一起排，但仍誠實留下 NaN 而不是
    假裝分好了層）。"""
    valid = liquidity.dropna()
    tier = pd.Series(np.nan, index=liquidity.index, dtype=object)
    if len(valid) < 10:
        return tier
    q1, q2 = valid.quantile([1 / 3, 2 / 3])
    tier.loc[valid.index] = np.where(valid <= q1, "small", np.where(valid <= q2, "mid", "large"))
    return tier


def _r(x):
    """NaN/inf-safe round，寫進 raw dict 用（None 代表沒有這個數字，不是 0）。
    inf 也要擋：json.dump(allow_nan=False) 連 inf 都不接受，跟 NaN 一樣要當成缺值處理。"""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return round(float(x), 4)


EPS_YOY_LOOKBACK_TRADING_DAYS = 252  # 約一年的交易日數，用來抓「去年同期」的反推EPS基準點


def _eps_yoy_derived_from_per(d: pd.DataFrame, as_of: str) -> tuple[float | None, str | None]:
    """earnings_growth的備援來源（2026-08-27新增，使用者指正「單點依賴FinMind
    TaiwanStockFinancialStatements」後的修正）：用 收盤價÷本益比 反推TTM EPS，
    分別在 as_of 跟約252個交易日前（近似一年前）兩個時點各反推一次，比較兩者
    算出「TTM EPS年增率」的替代值。**完全不需要任何新的網路請求**——`d`裡的
    `f_value_pe`（來自factors.py既有的`load_dev("TaiwanStockPER",...)`，已經
    是本地parquet快取）跟`close`都已經在記憶體裡，只是重新利用既有資料換一種
    算法，不是新資料源、不受FinMind目前IP封鎖影響。

    回傳 (eps_yoy_derived, "derived_from_per_ttm")，任一步驟拿不到就回傳
    (None, None)，呼叫端會維持原本「不可得」的處理，不會假裝有值。

    **已知限制，誠實揭露**：這是「TTM反推」不是「單季年增率」，跟FinMind
    TaiwanStockFinancialStatements算的季度年增率概念不完全相同（TTM會被過去
    4季的整體表現平滑掉單季波動）——两者不是同一個東西的精確替代，只是同一個
    「獲利成長方向」問題的另一種合理估計，這也是為什麼要在輸出標記
    source="derived_from_per_ttm"，不能讓使用者誤以為兩者可以直接比較。
    """
    if "f_value_pe" not in d.columns or "close" not in d.columns:
        return None, None
    d2 = d.sort_values("date").reset_index(drop=True)
    idx = d2.index[d2["date"] == as_of]
    if len(idx) == 0:
        return None, None
    i_now = int(idx[0])
    i_prior = i_now - EPS_YOY_LOOKBACK_TRADING_DAYS
    if i_prior < 0:
        return None, None  # 上市不到一年，沒有「去年同期」可比較，誠實回傳不可得

    def _derived_eps(i: int) -> float | None:
        per = d2.loc[i, "f_value_pe"]  # factors.py 裡是 -PER（方向調整過），這裡要還原成原始正值PER
        close = d2.loc[i, "close"]
        if pd.isna(per) or pd.isna(close):
            return None
        per_raw = -per
        if per_raw <= 0:
            return None  # 虧損公司的PER沒有意義，跟factors.py原本排除負/零PER的邏輯一致
        return float(close) / per_raw

    eps_now = _derived_eps(i_now)
    eps_prior = _derived_eps(i_prior)
    if eps_now is None or eps_prior is None or eps_prior == 0:
        return None, None
    yoy = (eps_now - eps_prior) / abs(eps_prior)
    if not np.isfinite(yoy):
        return None, None
    return float(yoy), "derived_from_per_ttm"


def compute_scores_v2(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str], start_date: str,
) -> pd.DataFrame:
    """回傳每檔股票一列的 DataFrame（index=stock_id），欄位包含每個因子的
    raw_*／*_score／*_pct，以及最終的 total_score／coverage／rank。`data` 是
    factor_ic.py::load_sample_with_factors() 的輸出（已經含 prepare_factors()
    算好的 f_eps_growth/f_inst_flow/f_ma_breakout/f_value_pe 等欄位）。
    """
    rows = []
    for sid, d in data.items():
        idx = d.index[d["date"] == as_of]
        if len(idx) == 0:
            continue
        r = d.loc[idx[0]]
        eps_yoy = r.get("f_eps_growth", np.nan)
        eps_source = "finmind_statements" if pd.notna(eps_yoy) else None
        # 2026-08-27新增：主來源(FinMind財報季度年增率)失效時的備援——用PER反推
        # TTM EPS年增率，不是另外多打新的資料源，見_eps_yoy_derived_from_per()
        # docstring。使用者原話：「單點依賴視為架構缺陷，不是外部限制」。
        if pd.isna(eps_yoy):
            eps_yoy, eps_source = _eps_yoy_derived_from_per(d, as_of)
        pe = -r["f_value_pe"] if pd.notna(r.get("f_value_pe")) else np.nan
        peg = pe / (eps_yoy * 100) if pd.notna(pe) and pd.notna(eps_yoy) and eps_yoy > 0 else np.nan
        if not np.isfinite(peg):
            peg = np.nan
        # 問題2/1d：近20日均成交金額，PIT-safe（只用當下及之前的資料）——同時是
        # 流動性門檻（問題2）的判斷依據，也是規模分層（問題1d）的替代市值指標
        # （`TaiwanStockMarketValue` 是付費資料集，這裡沿用 factors.py 既有的替代邏輯，
        # 不是這輪新發明的簡化）。
        tm20 = d["Trading_money"].rolling(20, min_periods=20).mean()
        liquidity_20d = float(tm20.loc[idx[0]]) if pd.notna(tm20.loc[idx[0]]) else np.nan
        rows.append({
            "stock_id": sid,
            "industry": industry_map.get(sid, "UNKNOWN"),
            "raw_eps_yoy": eps_yoy,
            "eps_yoy_source": eps_source,
            "raw_inst_flow": r.get("f_inst_flow", np.nan),
            "raw_ma_breakout": r.get("f_ma_breakout", np.nan),
            "raw_pe": pe,
            "raw_peg": peg,
            "liquidity_20d": liquidity_20d,
        })
    if not rows:
        # Bug fixed 2026-08-26 (surfaced by an all-FinMind-402 test run): pd.DataFrame([])
        # has zero columns, so .set_index("stock_id") on it raises KeyError('stock_id')
        # instead of returning the (correctly empty) result -- same class of bug as the
        # one already fixed in adjust.py's adjustment_events()/adjusted_price_series().
        return pd.DataFrame()
    cs = pd.DataFrame(rows).set_index("stock_id")
    if cs.empty:
        return cs

    # 問題1d：規模分層（用近20日均成交金額當市值/營收規模替代指標），revenue_momentum
    # 要在這個分層內部排名，不是整批一起排。
    cs["size_tier"] = _size_tier(cs["liquidity_20d"])

    # 問題2：流動性門檻——近20日均成交金額低於 LIQUIDITY_FLOOR_20D_VALUE 就標記
    # 「流動性不足」，不進榜單排名（`export_scores_v2_json()` 會依這個欄位過濾），
    # 但這裡仍然算出它的分數/百分位，讓搜尋查詢結果還查得到（使用者原話：可保留在
    # 搜尋查詢結果，只是標「流動性不足」，不是完全藏起來）。
    cs["liquidity_insufficient"] = cs["liquidity_20d"].isna() | (cs["liquidity_20d"] < LIQUIDITY_FLOOR_20D_VALUE)

    # 問題1a/1b：這兩個要另外抓（見檔案最上面說明），逐檔查 -- 都走 parquet 快取，不會真的多打 API。
    # _revenue_yoy_latest() 現在回傳 dict（yoy 已經過基期門檻+硬上限處理），展開成獨立欄位。
    rev_stats = pd.DataFrame(
        {sid: _revenue_yoy_latest(sid, start_date) for sid in cs.index}
    ).T.reindex(cs.index)
    cs["raw_rev_yoy"] = rev_stats["yoy"]  # 基期門檻+硬上限後的值，None=基期太小/無資料
    cs["raw_rev_yoy_uncapped"] = rev_stats["yoy_uncapped"]  # 只供除錯/揭露，不進任何排名
    cs["raw_rev_prior_year_revenue"] = rev_stats["prior_year_revenue"]
    cs["raw_rev_abs_growth"] = rev_stats["abs_growth"]  # 問題1c：絕對成長金額(NT$)
    cs["raw_rev_grow"] = pd.Series({sid: _revenue_growth_12m(sid, start_date) for sid in cs.index})

    raw_col = {
        "earnings_growth": "raw_eps_yoy",
        "growth_quality": "raw_rev_grow", "chips": "raw_inst_flow",
        "technical": "raw_ma_breakout", "valuation_adj": "raw_peg",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], FACTOR_DEFS[key]["higher_better"])
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct

    # revenue_momentum（問題1的核心修正）：分層內部排名(1d) + 相對成長%(1a/1b已處理)
    # 跟絕對成長金額(1c)兩個百分位取較保守者（elementwise min），不是只看其中一個。
    yoy_score, yoy_pct = _pct_score_within_group(cs["raw_rev_yoy"], cs["size_tier"], True)
    abs_score, abs_pct = _pct_score_within_group(cs["raw_rev_abs_growth"], cs["size_tier"], True)
    combined_pct = pd.concat([yoy_pct, abs_pct], axis=1).min(axis=1, skipna=False)
    cs["revenue_momentum_pct"] = combined_pct
    cs["revenue_momentum_score"] = (combined_pct * 10).round(1)

    # analyst/catalyst：這輪對每一檔都沒有資料來源（見檔案最上面說明），誠實留 NaN，
    # 不是漏寫 -- 靠下面 _total_and_coverage() 的重新分配權重機制處理，不會被當成 0 分。
    cs["analyst_score"] = np.nan
    cs["analyst_pct"] = np.nan
    cs["catalyst_score"] = np.nan
    cs["catalyst_pct"] = np.nan

    totals, covs = [], []
    for _, row in cs.iterrows():
        num, den = 0.0, 0.0
        for key, meta in FACTOR_DEFS.items():
            sc = row.get(f"{key}_score")
            if pd.notna(sc):
                num += sc * meta["weight"]
                den += meta["weight"]
        if den == 0:
            totals.append(np.nan)
            covs.append(0.0)
        else:
            totals.append(round(num / den, 1))
            covs.append(round(den, 2))
    cs["total_score"] = totals
    cs["coverage"] = covs
    cs = cs.dropna(subset=["total_score"]).copy()
    cs["rank"] = cs["total_score"].rank(ascending=False, method="min").astype(int)
    return cs.sort_values("rank")


def _raw_dict(key: str, row: pd.Series) -> dict:
    if key == "earnings_growth":
        return {"eps_yoy": _r(row["raw_eps_yoy"]), "eps_yoy_source": row.get("eps_yoy_source")}
    if key == "revenue_momentum":
        return {
            "rev_yoy": _r(row["raw_rev_yoy"]),  # 已過基期門檻+硬上限，None=基期太小/無效
            "rev_yoy_uncapped": _r(row["raw_rev_yoy_uncapped"]),  # 原始未夾值，只供核對，不是排名依據
            "prior_year_revenue": _r(row["raw_rev_prior_year_revenue"]),
            "abs_growth": _r(row["raw_rev_abs_growth"]),
            "size_tier": row.get("size_tier") if pd.notna(row.get("size_tier")) else None,
            "liquidity_20d": _r(row.get("liquidity_20d")),
        }
    if key == "growth_quality":
        return {"rev_growth_12m_yoy": _r(row["raw_rev_grow"])}
    if key == "chips":
        return {"inst_net_pct_of_20d_trading_value": _r(row["raw_inst_flow"])}
    if key == "technical":
        return {"ma60_breakout_x_volume_index": _r(row["raw_ma_breakout"])}
    if key == "valuation_adj":
        return {"pe": _r(row["raw_pe"]), "eps_yoy": _r(row["raw_eps_yoy"]), "eps_yoy_source": row.get("eps_yoy_source"), "peg": _r(row["raw_peg"])}
    return {}


def _front_pct(pct: float) -> int:
    """pct 是「贏過全市場多少比例」(1.0=最好)，換算成「排在前面百分之幾」給人話用。"""
    return max(1, round((1 - pct) * 100))


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = _front_pct(pct) if pd.notna(pct) else None
    if key == "earnings_growth":
        v = row["raw_eps_yoy"]
        return f"最新一季 EPS 年增 {v*100:+.0f}%，居全市場前 {front}%。"
    if key == "revenue_momentum":
        v = row["raw_rev_yoy"]
        tier = row.get("size_tier")
        tier_txt = {"small": "小型股", "mid": "中型股", "large": "大型股"}.get(tier, "同規模級距")
        abs_g = row.get("raw_rev_abs_growth")
        abs_txt = f"、絕對成長金額約 {abs_g/1e8:+.2f} 億元" if pd.notna(abs_g) else ""
        return (f"最新月營收年增 {v*100:+.1f}%（已排除基期<3000萬元的失真樣本、"
                f"且±200%硬上限){abs_txt}，在{tier_txt}同儕中居前 {front}%"
                f"（相對成長%與絕對成長金額兩者取較保守者）。")
    if key == "growth_quality":
        v = row["raw_rev_grow"]
        return (f"近 12 個月營收合計年增 {v*100:+.1f}%（簡化版成長性代理指標，"
                f"用滾動 12 個月平滑單月雜訊；未含毛利率趨勢，非嚴格多年 CAGR），居全市場前 {front}%。")
    if key == "chips":
        v = row["raw_inst_flow"]
        return (f"三大法人近 20 日買超金額約當 20 日均成交值的 {v*100:+.1f}%"
                f"（以成交值取代股本/市值作分母，市值資料為 FinMind 付費層，見 factors.py 揭露），"
                f"居全市場前 {front}%。")
    if key == "technical":
        v = row["raw_ma_breakout"]
        return (f"價格相對 60 日均線乖離 × 近 20/60 日均量比綜合指標為 {v:+.3f}"
                f"（正值代表站上均線且量能放大），居全市場前 {front}%。")
    if key == "valuation_adj":
        pe, eps_yoy, peg = row["raw_pe"], row["raw_eps_yoy"], row["raw_peg"]
        return (f"本益比 {pe:.1f} 倍，近一季 EPS 年增 {eps_yoy*100:.0f}%，"
                f"PEG（本益比÷盈餘成長率）= {peg:.2f}（PEG<1通常視為便宜、>2偏貴，"
                f"用成長調整後的估值，避免高成長股被純本益比殺錯），估值居全市場前 {front}%。")
    return ""


def _summary(row: pd.Series, present: list[str]) -> str:
    if not present:
        return "本檔可用資料不足，暫無總評。"
    ranked = sorted(present, key=lambda k: -row[f"{k}_score"])
    top = ranked[0]
    parts = [f"{FACTOR_DEFS[top]['label']}表現較突出（{row[f'{top}_score']:.1f}/10）"]
    if len(ranked) > 1 and row[f"{ranked[1]}_score"] >= 6:
        parts.append(f"{FACTOR_DEFS[ranked[1]]['label']}也不弱")
    worst = ranked[-1]
    if len(ranked) > 1 and row[f"{worst}_score"] <= 4:
        parts.append(f"{FACTOR_DEFS[worst]['label']}偏弱")
    return "，".join(parts) + "。"


def export_scores_v2_json(
    as_of: str, data: dict[str, pd.DataFrame], industry_map: dict[str, str],
    name_map: dict[str, str], out_path: str, start_date: str,
    top_n: int | None = 30, universe_size: int | None = None,
    weights_hash: str | None = None,
) -> pd.DataFrame:
    """寫出符合小抄第五節格式的 scores.json（`code`/`total_score`/`coverage`/
    `factors{score,percentile,raw,reason}`/`flags`/`news_warning`）。

    `weights_hash`（2026-08-26 新增，`score_live.py`稽核軌跡用）：呼叫端如果是
    走凍結權重上線路徑（`score_live.py::apply_frozen_weights()`），把
    `weights_frozen.json`算出的sha256傳進來，會原樣寫進`meta.weights_hash`，
    讓日後任何人打開`scores.json`都能回頭核對「這批分數當時用的是哪一版凍結權重」。
    預設`None`（不寫這個欄位）保留給其他既有呼叫端，不強制它們也要提供這個值。
    """
    cs = compute_scores_v2(as_of, data, industry_map, start_date)
    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-v2", "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW", "universe_size": universe_size,
                "weights_hash": weights_hash,
                "disclaimer": "非投資建議；資料為盤後/延遲資料。這次沒有任何股票算出分數（樣本可能太小）。",
            },
            "weights": {k: v["weight"] for k, v in FACTOR_DEFS.items()}, "stocks": [],
        }
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return cs

    # 問題4：篩選漏斗統計——使用者要求「說明篩選條件與被排除原因的統計」，逐級記錄，
    # 不是只丟出最終清單讓人猜門檻鬆緊。
    n_total = len(cs)
    coverage_ok = cs["coverage"] >= COVERAGE_MIN_FOR_RANKING
    n_coverage_excluded = int((~coverage_ok).sum())
    eligible = cs[coverage_ok].copy()
    n_liquidity_excluded = int(eligible["liquidity_insufficient"].sum())
    n_final_ranked = int((~eligible["liquidity_insufficient"]).sum())
    funnel = {
        "total_scored": n_total,
        "excluded_low_coverage": n_coverage_excluded,
        "excluded_low_liquidity": n_liquidity_excluded,
        "final_ranked": n_final_ranked,
        "coverage_min_for_ranking": COVERAGE_MIN_FOR_RANKING,
        "liquidity_floor_20d_value": LIQUIDITY_FLOOR_20D_VALUE,
    }

    # 問題2：流動性不足的股票排到清單最後面（仍然留在 stocks[] 裡給搜尋用，不是被拿掉），
    # 且 rank 只在「流動性合格」的子集合裡重算——不能讓一檔流動性不足的股票因為 raw
    # total_score 高就顯示 rank=1，那等於沒有真的「排除於排行榜之外」。
    eligible = eligible.sort_values(["liquidity_insufficient", "total_score"], ascending=[True, False])
    liquidity_ok_mask = ~eligible["liquidity_insufficient"]
    eligible.loc[liquidity_ok_mask, "display_rank"] = range(1, liquidity_ok_mask.sum() + 1)
    head = eligible.head(top_n) if top_n else eligible

    stocks = []
    for sid, row in head.iterrows():
        present = [k for k in FACTOR_DEFS if pd.notna(row.get(f"{k}_score"))]
        factors_obj = {
            k: {
                "score": round(float(row[f"{k}_score"]), 1),
                "percentile": round(float(row[f"{k}_pct"]), 2),
                "raw": _raw_dict(k, row),
                "reason": _reason(k, row),
            } for k in present
        }
        flags = []
        if row["liquidity_insufficient"]:
            flags.append("流動性不足")
        display_rank = row.get("display_rank")
        stocks.append({
            "code": sid,
            "name": name_map.get(sid) if name_map else None,
            "industry": row["industry"],
            "rank": int(display_rank) if pd.notna(display_rank) else None,
            "total_score": round(float(row["total_score"]), 1),
            "coverage": round(float(row["coverage"]), 2),
            "liquidity_20d": _r(row.get("liquidity_20d")),
            "data_asof": as_of,
            "summary": _summary(row, present),
            "factors": factors_obj,
            "flags": flags,
            "news_warning": None,
        })

    payload = {
        "meta": {
            "engine_version": "scoring-v2",
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "data_asof": as_of,
            "market": "TW",
            "universe_size": universe_size,
            "weights_hash": weights_hash,
            "filter_funnel": funnel,
            "disclaimer": (
                "非投資建議；所有分數只是資料整理與排序，不代表買賣訊號。資料為盤後/延遲資料。"
                "本期分數主要由財報成長與營收動能驅動——analyst（機構觀點）台股暫無免費目標價"
                "資料源、catalyst（題材/事件）本輪尚未實作（下一輪接新聞/供應鏈），這兩項對全部"
                "股票都缺資料，不是八大類別的真實綜合結果，已依 coverage 規則重新分配權重，不會把"
                "沒資料當成 0 分。coverage < 0.5 或近20日均成交金額低於門檻（流動性不足）的股票"
                "不進本排行榜（仍可被搜尋查到，並標示原因）。"
            ),
        },
        "weights": {k: v["weight"] for k, v in FACTOR_DEFS.items()},
        "stocks": stocks,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False, default=float)
    return cs
