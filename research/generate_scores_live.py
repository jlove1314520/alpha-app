"""P1「scores.json自動化」：不依賴parquet的上線評分路徑（2026-08-27新增）。

**背景（使用者原話）**：「目前App的核心功能綁在你本機，電腦沒開就靜靜過期，這是
架構風險。」`generate_scores_v2.py` 需要 `research/data/raw/` 底下的 FinMind
parquet 快取（gitignored，只存在互動 session 本機），GitHub Actions runner
每次全新checkout拿不到，沒辦法照原樣掛進排程。

**這支腳本是正確的解法（使用者原話）**：「不是把快取搬上CI，而是讓上線評分不
需要它。上線評分需要的資料已經全部在repo裡：fundamentals.json+stock_detail.json
+market_tw.json。」——只讀這三個已經commit進repo的JSON檔，**不讀任何parquet、
不呼叫FinMind、不呼叫yfinance**，讀凍結權重 `weights_frozen.json`（唯讀，寫入會
被 `score_live.py::_install_no_write_guard()` 攔截），套用進 `score_v2.FACTOR_DEFS`
後，用JSON裡已有的欄位重新算出能算的因子分數，寫回repo根目錄的 `scores.json`。

**跟 generate_scores_v2.py 的分工**：研究端pipeline（`generate_scores_v2.py`/
`factor_ic.py`/`TRIALS_LEDGER.md`那一套）完全維持原樣不動，繼續負責「驗證與鎖定
權重」——這支腳本不動它、不import它的任何調參邏輯。這支腳本只負責「上線套用」，
兩者職責分離，都可以各自把結果寫到同一個 `scores.json`（不衝突：研究端手動跑的
時候用即時FinMind/yfinance資料算出更完整的因子分數，覆蓋掉這支腳本先前寫的版本；
研究端沒跑的日子，這支腳本靠GitHub Actions排程持續產出，不會讓App的選股頁停擺）。

**誠實的因子覆蓋率限制（JSON-only路徑先天做不到跟研究端一樣完整）**：
- `earnings_growth`（財報成長）：`stock_detail.json` 的 `financials.quarters`
  抓「最新季度 vs 去年同季度」EPS年增率，需要兩個季度都在陣列裡（8季視窗，
  2026-08-27已回補歷史，多數常見股票應該有）。**沒有PER反推EPS的備援**——
  那個備援（`score_v2.py::_eps_yoy_derived_from_per()`）需要「約一年前的PER
  快照」，但 `fundamentals.json` 的 `ratios` 只存「最新一筆」，沒有retained
  歷史序列，這條路目前在JSON-only路徑走不通（要日後另外開一份PER歷史累積
  檔才能補，目前誠實留白，不是忘記做）。**2026-08-27修正（使用者P1抽查抓到
  真bug）**：去年同季EPS若非正值（虧損基期），YoY%視為不適用、回傳None，
  不套用「(now-prior)/abs(prior)」這種基期趨近零時會爆出失真巨大百分比的
  算法（實測：2344曾算出+1962%，其實是虧轉盈，不是真的成長19倍）；基期為
  正時仍套用±200%硬上限。
- `revenue_momentum`（營收動能）：`fundamentals.json` 的月營收最新一筆
  `yoy`（TWSE官方已算好），反推去年同月營收金額做基期門檻(3000萬)判斷，
  ±200%硬上限，跟研究端一致。**沒有做規模分層排名**（研究端用近20日均成交
  金額分layer，JSON-only路徑沒有per-股票的每日成交量歷史，只能整批排序，
  是刻意的範圍縮減）。
- `growth_quality`（成長性）：`revenue_history_scoring`（up to 26個月）的
  近12個月合計 vs 再前12個月合計，**要求這24個月視窗內完全連續無缺月**才計算
  （本機FinMind快取本身有缺月的已知情況，缺月的股票這裡誠實回傳None，不用
  有缺口的資料湊近似值）。
- `chips`（籌碼）：`stock_detail.json` 的 `institutional.history`（5日滾動，
  目前才剛開始累積，一開始可能只有1天資料），加總可用天數的三大法人買賣超
  張數當原始訊號，隨每日排程自然增厚到5天。
- `valuation_adj`（PEG）：`fundamentals.json` 的 `ratios.per` × 上面算出的
  `earnings_growth`，本益比<=0（虧損股）視為無效。
- `technical`（技術型態）：2026-08-27新增資料源——`data/price_history.json`
  （`research/build_price_history.py`一次性回補約90個交易日OHLCV歷史，
  `.github/scripts/update_price_history.py`每日累積式append，TWSE
  STOCK_DAY_ALL + TPEx tpex_mainboard_quotes）。算法跟研究端
  `factors.py::prepare_factors()`的`f_ma_breakout`同一個公式：
  `(close/MA60 - 1) * (vol20/vol60)`，**唯一差異是這裡用原始收盤價，
  未還原權息**（除權息當天前後MA60會有跳空失真，是刻意的簡化，不是bug）。
  需要至少60個交易日資料才能算，新股票/剛加入來源的股票資料不足時誠實
  留None，隨每日累積自然補齊。
- `analyst`/`catalyst`：跟研究端一樣，這兩項全市場沒有免費資料源，誠實留NaN。

**公司名稱/產業分類（2026-08-27修正，使用者P1抽查發現）**：原本`name`只讀
`quotes_tw.json`（僅使用者自選股，其餘股票顯示null），`industry`一直寫死
None。改讀`research/build_company_info.py`一次性建置的`data/company_info.json`
（讀FinMind`TaiwanStockInfo`快取，涵蓋全市場），`name`欄位全部有值；
`industry`欄位對約19%（603/3137）在FinMind原始資料裡本身就有同日期多種
分類歧義的股票，誠實留None（不猜可能錯的分類），細節見該腳本檔頭說明。

以上任何一項未來要補，原則不變：先問「有沒有第二條路、能不能從已有欄位推導」，
不是直接放棄——已經在STATUS.json的known_limitations列出，供之後排優先序。

**2026-08-27（P1-新）選股改為「全市場+資料完整度」，取消coverage<0.5硬性排除**
（使用者裁示）：原本用`COVERAGE_MIN_FOR_RANKING`(0.5)排除約一半股票不進
`stocks[]`——改成**全部進榜**，`coverage`（資料完整度）跟`missing_factors`
（缺哪幾項因子）都誠實寫進每筆輸出，由App前端用視覺條+弱化樣式呈現，不是
伺服器端先幫使用者篩選掉。**流動性門檻維持不變**（使用者原話「這條是對的，
不要拿掉」）：這輪新增用`data/price_history.json`的turnover算近20日均成交值，
低於`LIQUIDITY_FLOOR_20D_VALUE`的股票`rank`留`null`+標記「流動性不足」（沿用
研究端score_v2.py既有設計），不是完全從清單移除。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import live_factors
import score_v2
from score_live import apply_frozen_weights, load_frozen_weights
from score_v2 import (
    COVERAGE_MIN_FOR_RANKING, LIQUIDITY_FLOOR_20D_VALUE, REVENUE_BASE_FLOOR,
    REVENUE_YOY_HARD_CAP, _pct_score, _r,
)

REPO_ROOT = Path(__file__).parent.parent
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
MARKET_TW_PATH = REPO_ROOT / "data" / "market_tw.json"
QUOTES_TW_PATH = REPO_ROOT / "data" / "quotes_tw.json"
COMPANY_INFO_PATH = REPO_ROOT / "data" / "company_info.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
EVENTS_PATH = REPO_ROOT / "data" / "events.json"  # 2026-09-05：題材/事件因子的來源（fetch_events.py 產出）
OUT_PATH = REPO_ROOT / "scores.json"
TW_TZ = timezone(timedelta(hours=8))

GROWTH_QUALITY_MONTHS = 24  # 近12個月 vs 再前12個月，24個月起跳，要求視窗內完全連續
MA_WINDOW = 60
VOL_SHORT_WINDOW = 20
VOL_LONG_WINDOW = 60
# 2026-08-27新增：非個股證券（ETF/ETN/存託憑證等），見build_rows()說明。
NON_STOCK_INDUSTRIES = {
    "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
    "受益證券", "存託憑證", "Index", "大盤", "所有證券",
}
# 有些ETF不在company_info.json裡（該檔案讀FinMind快取，可能還沒收錄較新上市
# 的ETF），光靠industry分類濾不掉——00開頭代碼保留給ETF/ETN/受益證券，不是
# 普通股票，用代碼格式當補充過濾。
_NON_STOCK_CODE_PATTERN = re.compile(r"^00\d{2,4}[A-Z]?$")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在——這支腳本只讀repo內已commit的JSON，不會自己去產生。")
    return json.loads(path.read_text(encoding="utf-8"))


EPS_YOY_HARD_CAP = REVENUE_YOY_HARD_CAP  # 跟月營收共用同一個±200%上限，理由相同（見下）


def _eps_yoy_from_quarters(quarters: list[dict]) -> float | None:
    """2026-08-27發現並修正的真bug（使用者P1抽查抓到2344算出EPS年增+1962%）：
    去年同季EPS若是負值（虧損基期），(now-prior)/abs(prior) 這個公式會因為
    分母趨近於零而放大成失真的巨大百分比（實測：2025Q2 eps=-0.29 → 2026Q2
    eps=5.4，算出19.62=1962%），不是「真的成長了19倍」，是虧轉盈這種基期為
    負/趨近零的YoY%本身就沒有意義——跟score_v2.py既有的REVENUE_BASE_FLOOR/
    REVENUE_YOY_HARD_CAP同一類問題，這裡用同一套原則處理：基期(去年同季EPS)
    非正值時，YoY%視為不適用（回傳None，不進這個因子的排名，不是給高分或低
    分），基期為正時仍套用±200%硬上限避免極端值。"""
    if not quarters:
        return None
    latest = max(quarters, key=lambda r: (r["year"], r["quarter"]))
    prior = next((r for r in quarters if r["year"] == latest["year"] - 1 and r["quarter"] == latest["quarter"]), None)
    if prior is None:
        return None
    eps_now, eps_prior = latest.get("eps"), prior.get("eps")
    if eps_now is None or eps_prior is None or eps_prior <= 0:
        return None
    yoy = (eps_now - eps_prior) / eps_prior
    return max(min(yoy, EPS_YOY_HARD_CAP), -EPS_YOY_HARD_CAP)


def _revenue_stats(rev_rows: list[dict]) -> dict:
    """月營收基期門檻+硬上限，跟 score_v2.py::_revenue_yoy_latest() 同一套規則，
    只是這裡改成直接吃JSON已有的 `yoy`（TWSE官方算好的去年同月增減%）反推去年同月
    營收金額，不需要另外查歷史列（JSON裡的revenue_history_scoring本來就有，但反推
    比對再算一次yoy更省，也避免月份對齊的額外bug面）。"""
    if not rev_rows:
        return {"yoy": None, "prior_year_revenue": None, "abs_growth": None}
    latest = max(rev_rows, key=lambda r: (r["year"], r["month"]))
    revenue, yoy = latest.get("revenue"), latest.get("yoy")
    if revenue is None or yoy is None or yoy <= -1:
        return {"yoy": None, "prior_year_revenue": None, "abs_growth": None}
    prior_rev = revenue / (1 + yoy)
    if prior_rev < REVENUE_BASE_FLOOR:
        return {"yoy": None, "prior_year_revenue": prior_rev, "abs_growth": revenue - prior_rev}
    yoy_capped = max(min(yoy, REVENUE_YOY_HARD_CAP), -REVENUE_YOY_HARD_CAP)
    return {"yoy": yoy_capped, "prior_year_revenue": prior_rev, "abs_growth": revenue - prior_rev}


def _growth_quality(rev_rows: list[dict]) -> float | None:
    if len(rev_rows) < GROWTH_QUALITY_MONTHS:
        return None
    rows = sorted(rev_rows, key=lambda r: (r["year"], r["month"]))[-GROWTH_QUALITY_MONTHS:]
    # 連續性檢查：相鄰兩筆的(year,month)必須剛好差一個月，中間不能有缺月——
    # 缺月會讓「近12個月合計」變成「近不到12個月合計」卻誤稱是12個月，寧可
    # 回傳None也不要用有缺口的資料充數。
    for a, b in zip(rows, rows[1:]):
        months_diff = (b["year"] - a["year"]) * 12 + (b["month"] - a["month"])
        if months_diff != 1:
            return None
    recent12 = sum(r["revenue"] for r in rows[-12:])
    prior12 = sum(r["revenue"] for r in rows[:12])
    if not prior12 or prior12 <= 0:
        return None
    return recent12 / prior12 - 1


def _ma_breakout(price_rows: list[dict]) -> float | None:
    """跟 factors.py::prepare_factors() 的 f_ma_breakout 同一個公式：
    (close/MA60 - 1) * (vol20/vol60)。用原始收盤價，未還原權息（見檔頭說明）。
    需要至少 MA_WINDOW(60) 筆資料才算，不足時誠實回傳None。"""
    if len(price_rows) < MA_WINDOW:
        return None
    rows = sorted(price_rows, key=lambda r: r["date"])
    closes = pd.Series([r["close"] for r in rows], dtype=float)
    volumes = pd.Series([r.get("volume") for r in rows], dtype=float)
    ma60 = closes.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean().iloc[-1]
    last_close = closes.iloc[-1]
    if pd.isna(ma60) or ma60 == 0 or pd.isna(last_close):
        return None
    above_ma_pct = last_close / ma60 - 1
    vol20 = volumes.rolling(VOL_SHORT_WINDOW, min_periods=VOL_SHORT_WINDOW).mean().iloc[-1]
    vol60 = volumes.rolling(VOL_LONG_WINDOW, min_periods=VOL_LONG_WINDOW).mean().iloc[-1]
    if pd.isna(vol20) or pd.isna(vol60) or vol60 == 0:
        return None
    result = above_ma_pct * (vol20 / vol60)
    return float(result) if np.isfinite(result) else None


def _liquidity_20d(price_rows: list[dict]) -> float | None:
    """近20日均成交值——2026-08-27新增（使用者P1-新要求「保留流動性門檻」）。
    跟research端score_v2.py的LIQUIDITY_FLOOR_20D_VALUE同一個概念，這裡改用
    data/price_history.json的turnover欄位（2026-08-27才開始累積，可能不足
    20天，有多少算多少，至少要有1天才算，不到1天回傳None）。"""
    rows = [r for r in price_rows if r.get("turnover") is not None]
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["date"])[-20:]
    return sum(r["turnover"] for r in rows) / len(rows)


def _chips_signal(institutional: dict | None) -> float | None:
    if not institutional:
        return None
    history = institutional.get("history") or [institutional]
    total = 0.0
    any_val = False
    for day in history:
        for k in ("foreign_lots", "trust_lots", "dealer_lots"):
            v = day.get(k)
            if v is not None:
                total += v
                any_val = True
    return total if any_val else None


def build_rows() -> pd.DataFrame:
    fundamentals = _load_json(FUNDAMENTALS_PATH).get("fundamentals", {})
    stock_detail = _load_json(STOCK_DETAIL_PATH).get("stocks", {})
    price_history = {}
    if PRICE_HISTORY_PATH.exists():
        try:
            price_history = _load_json(PRICE_HISTORY_PATH).get("prices", {})
        except Exception:
            price_history = {}
    # 2026-08-27修正（真bug，題材動能榜開發時交叉測試才發現）：原本沒有過濾
    # ETF/ETN/存託憑證等非個股證券，導致這些代碼混進評分排行榜（例如00910
    # 「第一金太空衛星」這類ETF曾經出現在scores.json前段）。用company_info.json
    # 的industry分類過濾掉，跟generate_scores_momentum.py用同一份NON_STOCK_
    # INDUSTRIES常數（兩支腳本各自獨立複製，不跨檔案import，同既有慣例）。
    company_info = _company_info()
    candidate_codes = set(fundamentals) | set(stock_detail) | set(price_history)
    non_stock_codes = {code for code, v in company_info.items() if v.get("industry") in NON_STOCK_INDUSTRIES}
    non_stock_codes |= {code for code in candidate_codes if _NON_STOCK_CODE_PATTERN.match(code)}
    all_codes = sorted(candidate_codes - non_stock_codes)

    # 2026-09-05（總司令「八因子全部填上」）：每個因子改成 live_factors.py 的「多子訊號複合」，
    # 有幾個算幾個；並補上原本沒有資料源的兩個因子（analyst→機構行為、catalyst→事件）。
    events_by_code: dict[str, list] = {}
    events_source_available = EVENTS_PATH.exists()
    if events_source_available:
        try:
            events_by_code = _load_json(EVENTS_PATH).get("by_stock", {}) or {}
        except Exception:
            events_by_code = {}

    rows = []
    for code in all_codes:
        fd = fundamentals.get(code, {})
        sd = stock_detail.get(code, {})
        fin = sd.get("financials", {})
        price_rows = price_history.get(code) or []
        liquidity_20d = _liquidity_20d(price_rows)

        quarters = fin.get("quarters") or []
        eg_val, eg_comp = live_factors.earnings_growth(quarters)
        eps_yoy = eg_comp.get("eps_yoy")

        tech_val, tech_comp = live_factors.technical(price_rows)
        ma_breakout = _ma_breakout(price_rows)  # 舊指標保留：既有 index.html/回測都讀這個 key

        rev_rows = fd.get("revenue_history_scoring") or fd.get("month_revenue") or []
        rev_stats = _revenue_stats(rev_rows)
        rev_grow_12m, gq_comp = live_factors.growth_quality(rev_rows)
        if rev_grow_12m is None:
            rev_grow_12m = _growth_quality(rev_rows)  # 舊版嚴格法當備援（完全連續24個月時兩者等價）

        chips = _chips_signal(sd.get("institutional"))
        inst_val, inst_comp = live_factors.inst_behavior(sd.get("institutional"))
        ev_val, ev_comp = live_factors.event_score(events_by_code.get(code))

        ratios = fd.get("ratios") or {}
        per = ratios.get("per")
        pbr = ratios.get("pbr")
        pe = per if per is not None and per > 0 else None
        pb = pbr if pbr is not None and pbr > 0 else None
        peg = (pe / (eps_yoy * 100)) if (pe is not None and eps_yoy is not None and eps_yoy > 0) else None
        if peg is not None and not np.isfinite(peg):
            peg = None

        rows.append({
            "stock_id": code,
            "raw_eps_yoy": eps_yoy, "eps_yoy_source": "stock_detail_quarters" if eps_yoy is not None else None,
            "raw_earnings_growth": eg_val, "eg_components": eg_comp,
            "raw_rev_yoy": rev_stats["yoy"],
            "raw_rev_prior_year_revenue": rev_stats["prior_year_revenue"],
            "raw_rev_abs_growth": rev_stats["abs_growth"],
            "raw_rev_grow": rev_grow_12m, "gq_components": gq_comp,
            "raw_inst_flow": chips,
            "raw_pe": pe, "raw_pb": pb, "raw_peg": peg,
            "raw_ma_breakout": ma_breakout,
            "raw_technical": tech_val, "tech_components": tech_comp,
            "raw_gain_60d": live_factors.gain_60d(price_rows),
            "raw_inst_behavior": inst_val, "inst_components": inst_comp,
            "raw_event": ev_val, "event_components": ev_comp,
            "liquidity_20d": liquidity_20d,
            "industry": (company_info.get(code) or {}).get("industry"),
        })

    cs = pd.DataFrame(rows).set_index("stock_id")
    cs.attrs["events_source_available"] = events_source_available
    return cs


def compute_scores_live() -> pd.DataFrame:
    cs = build_rows()
    if cs.empty:
        return cs

    # 2026-09-05：估值改「同產業百分位」的 PER/PBR/PEG 複合（總司令一.2）。
    # 三個都是越低越便宜，各自在「同產業」內取百分位（不足 8 檔的產業退回全市場），再平均。
    # 這麼做的理由：本益比的合理區間在半導體跟金融保險差很多，跨產業直接比會把整個高本益比
    # 產業判成貴、低本益比產業判成便宜，那不是估值訊號、是產業分類訊號。
    val_parts = []
    for col in ("raw_pe", "raw_pb", "raw_peg"):
        ranks = pd.Series(np.nan, index=cs.index, dtype=float)
        for ind, grp in cs.groupby(cs["industry"].fillna("__NA__"), dropna=False):
            sub = grp[col].dropna()
            if ind != "__NA__" and len(sub) >= 8:
                ranks.loc[sub.index] = sub.rank(pct=True)
        remaining = cs[col].notna() & ranks.isna()
        if remaining.any():
            ranks.loc[remaining] = cs.loc[remaining, col].rank(pct=True)
        val_parts.append(ranks)
    val_df = pd.concat(val_parts, axis=1)
    cs["raw_valuation_pct_in_industry"] = val_df.mean(axis=1, skipna=True)
    cs["raw_valuation_n_signals"] = val_df.notna().sum(axis=1)

    raw_col = {
        "earnings_growth": "raw_earnings_growth",
        "revenue_momentum": "raw_rev_yoy",
        "growth_quality": "raw_rev_grow",
        "chips": "raw_inst_flow",
        "valuation_adj": "raw_valuation_pct_in_industry",
        "technical": "raw_technical",
        "analyst": "raw_inst_behavior",   # 機構「行為」，不是分析師目標價，見 live_factors.py 說明
        "catalyst": "raw_event",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], score_v2.FACTOR_DEFS[key]["higher_better"])
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct

    totals, covs = [], []
    for _, row in cs.iterrows():
        num, den = 0.0, 0.0
        for key, meta in score_v2.FACTOR_DEFS.items():
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


def _nan_safe(obj):
    """把 dict/list 裡的 NaN 換成 None——2026-09-05 新增的複合因子會把子訊號 dict 直接放進
    scores.json，pandas 的缺值是 float('nan')，json.dump(allow_nan=False) 會直接拋
    「Out of range float values are not JSON compliant」。這裡統一在輸出前洗一次。"""
    if isinstance(obj, dict):
        return {k: _nan_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_nan_safe(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    if obj is not None and hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            v = obj.item()
            return None if isinstance(v, float) and v != v else v
        except Exception:
            return obj
    return obj


def _raw_dict(key: str, row: pd.Series) -> dict:
    return _nan_safe(_raw_dict_impl(key, row))


def _raw_dict_impl(key: str, row: pd.Series) -> dict:
    if key == "earnings_growth":
        c = row.get("eg_components") or {}
        return {
            "composite": _r(row["raw_earnings_growth"]), "eps_yoy": _r(row["raw_eps_yoy"]),
            "revenue_yoy": _r(c.get("revenue_yoy")), "gross_margin_yoy_pp": _r(c.get("gross_margin_yoy_pp")),
            "op_margin_yoy_pp": _r(c.get("op_margin_yoy_pp")), "as_of": c.get("as_of"),
            "n_signals": c.get("n_signals"), "eps_yoy_source": row.get("eps_yoy_source"),
        }
    if key == "revenue_momentum":
        return {
            "rev_yoy": _r(row["raw_rev_yoy"]),
            "prior_year_revenue": _r(row["raw_rev_prior_year_revenue"]),
            "abs_growth": _r(row["raw_rev_abs_growth"]),
        }
    if key == "growth_quality":
        c = row.get("gq_components") or {}
        return {"rev_growth_12m_yoy": _r(row["raw_rev_grow"]), "method": c.get("method"),
                "yoy_months": c.get("yoy_months"), "pairs": c.get("pairs"),
                "months_used": (c.get("months_used") or [])[-3:]}
    if key == "chips":
        return {"inst_net_lots_available_days": _r(row["raw_inst_flow"])}
    if key == "valuation_adj":
        return {
            "pe": _r(row["raw_pe"]), "pb": _r(row["raw_pb"]), "peg": _r(row["raw_peg"]),
            "eps_yoy": _r(row["raw_eps_yoy"]), "industry": row.get("industry"),
            "industry_percentile": _r(row["raw_valuation_pct_in_industry"]),
            "n_signals": int(row["raw_valuation_n_signals"]) if pd.notna(row.get("raw_valuation_n_signals")) else 0,
        }
    if key == "technical":
        # 2026-08-27修正（B4冒煙測試check#6抓到真bug）：跟score_v2.py的_raw_dict()
        # 用同一個key名（`ma60_breakout_x_volume_index`）——這是同一個公式算出的
        # 同一個指標，原本這裡取了不同key名，導致index.html的renderReport()
        # （寫死讀score_v2.py那個key名）在這條JSON-only路徑產生的scores.json上
        # 讀到undefined，對undefined呼叫.toFixed()整個拋出unhandledrejection。
        c = row.get("tech_components") or {}
        return {
            "ma60_breakout_x_volume_index": _r(row["raw_ma_breakout"]),
            "composite": _r(row["raw_technical"]), "ma_alignment": _r(c.get("ma_alignment")),
            "range_position_60d": _r(c.get("range_position_60d")), "rsi14": _r(c.get("rsi14_value")),
            "volume_change": _r(c.get("volume_change")), "n_signals": c.get("n_signals"),
            "gain_60d": _r(row["raw_gain_60d"]),
        }
    if key == "analyst":
        c = row.get("inst_components") or {}
        return {
            "composite": _r(row["raw_inst_behavior"]), "foreign_streak_days": c.get("foreign_streak_days"),
            "trust_streak_days": c.get("trust_streak_days"), "net_trend": _r(c.get("net_trend")),
            "history_days": c.get("history_days"), "n_signals": c.get("n_signals"),
            "note": "機構『行為』（法人實際買賣），非分析師目標價／評等——台股無免費目標價資料源",
        }
    if key == "catalyst":
        c = row.get("event_components") or {}
        return {
            "composite": _r(row["raw_event"]), "n_events": c.get("n_events"),
            "types": c.get("types"), "latest_date": c.get("latest_date"),
        }
    return {}


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = max(1, round((1 - pct) * 100)) if pd.notna(pct) else None
    if key == "earnings_growth":
        c = row.get("eg_components") or {}
        bits = []
        if c.get("eps_yoy") is not None:
            bits.append(f"EPS年增 {c['eps_yoy']*100:+.0f}%")
        if c.get("revenue_yoy") is not None:
            bits.append(f"營收年增 {c['revenue_yoy']*100:+.0f}%")
        if c.get("gross_margin_yoy_pp") is not None:
            bits.append(f"毛利率年變化 {c['gross_margin_yoy_pp']:+.1f}個百分點")
        if c.get("op_margin_yoy_pp") is not None:
            bits.append(f"營益率年變化 {c['op_margin_yoy_pp']:+.1f}個百分點")
        return (f"{c.get('as_of', '最新季')} 對去年同季：" + "、".join(bits)
                + f"（{c.get('n_signals', 0)}項可得指標平均，來源 TWSE 官方財報 t187ap06_L_ci/07_L_ci），居全市場前 {front}%。")
    if key == "revenue_momentum":
        return f"最新月營收年增 {row['raw_rev_yoy']*100:+.1f}%（已排除基期<3000萬元樣本、±200%硬上限，未做規模分層），居全市場前 {front}%。"
    if key == "growth_quality":
        c = row.get("gq_components") or {}
        if c.get("method") == "avg_monthly_yoy":
            how = f"近 {c.get('yoy_months')} 個月的月營收年增率平均"
        else:
            how = f"同月配對 {c.get('pairs')} 組的營收合計年增"
        return (f"{how}為 {row['raw_rev_grow']*100:+.1f}%（月營收歷史為「一次性種子快照＋每日累積」，"
                f"中間可能有斷層，故用逐月年增平均而非視窗合計），居全市場前 {front}%。")
    if key == "chips":
        return f"近期（依累積天數，最多5日）三大法人買賣超合計 {row['raw_inst_flow']:+.0f} 張，居全市場前 {front}%。"
    if key == "valuation_adj":
        bits = []
        if pd.notna(row.get("raw_pe")):
            bits.append(f"本益比 {row['raw_pe']:.1f} 倍")
        if pd.notna(row.get("raw_pb")):
            bits.append(f"股價淨值比 {row['raw_pb']:.2f} 倍")
        if pd.notna(row.get("raw_peg")):
            bits.append(f"PEG {row['raw_peg']:.2f}")
        ind = row.get("industry") or "全市場"
        return ("、".join(bits) + f"；在「{ind}」同業內的估值百分位平均為 "
                f"{row['raw_valuation_pct_in_industry']*100:.0f}%（數字越低越便宜），綜合估值居全市場前 {front}%。")
    if key == "technical":
        c = row.get("tech_components") or {}
        bits = []
        if c.get("ma_alignment") is not None:
            bits.append("均線多頭排列" if c["ma_alignment"] > 0 else ("均線空頭排列" if c["ma_alignment"] < 0 else "均線糾結"))
        if c.get("range_position_60d") is not None:
            bits.append(f"位於近60日區間 {((c['range_position_60d'] + 1) / 2 * 100):.0f}% 位置")
        if c.get("rsi14_value") is not None:
            bits.append(f"RSI14={c['rsi14_value']:.0f}")
        if c.get("volume_change") is not None:
            bits.append(f"近5日均量較20日 {c['volume_change']*100:+.0f}%")
        return ("、".join(bits) + f"（{c.get('n_signals', 0)}項可得指標平均，原始收盤價未還原權息），居全市場前 {front}%。")
    if key == "analyst":
        c = row.get("inst_components") or {}
        bits = []
        fs, ts = c.get("foreign_streak_days"), c.get("trust_streak_days")
        if fs:
            bits.append(f"外資連續{'買超' if fs > 0 else '賣超'} {abs(fs)} 天")
        if ts:
            bits.append(f"投信連續{'買超' if ts > 0 else '賣超'} {abs(ts)} 天")
        if c.get("net_trend") is not None:
            bits.append("三大法人淨買超趨勢向上" if c["net_trend"] > 0 else ("趨勢向下" if c["net_trend"] < 0 else "趨勢持平"))
        return ("；".join(bits) + f"（觀察 {c.get('history_days', 0)} 個交易日。**這是機構『行為』不是分析師目標價**"
                f"——台股沒有免費的目標價／評等資料源），居全市場前 {front}%。")
    if key == "catalyst":
        c = row.get("event_components") or {}
        types = "、".join(f"{k}×{v}" for k, v in (c.get("types") or {}).items())
        return (f"近30日 {c.get('n_events', 0)} 則事件（{types}），最新 {c.get('latest_date')}；"
                f"依事件類型權重×新鮮度（半衰期7天）計分，居全市場前 {front}%。")
    return ""


def _summary(row: pd.Series, present: list[str]) -> str:
    if not present:
        return "本檔可用資料不足，暫無總評。"
    ranked = sorted(present, key=lambda k: -row[f"{k}_score"])
    top = ranked[0]
    parts = [f"{score_v2.FACTOR_DEFS[top]['label']}表現較突出（{row[f'{top}_score']:.1f}/10）"]
    worst = ranked[-1]
    if len(ranked) > 1 and row[f"{worst}_score"] <= 4:
        parts.append(f"{score_v2.FACTOR_DEFS[worst]['label']}偏弱")
    return "，".join(parts) + "。"


def _company_info() -> dict[str, dict]:
    """2026-08-27新增：使用者P1抽查發現多數股票name/industry是null（原本只讀
    quotes_tw.json，僅涵蓋自選股）。改讀 research/build_company_info.py 產生的
    data/company_info.json（涵蓋全市場，讀research端FinMind快取整理，一次性
    建置不需要每日排程）。industry對約19%（603/3137）有原始資料歧義的股票
    誠實留None（見build_company_info.py檔頭說明），不是這裡漏接。"""
    if not COMPANY_INFO_PATH.exists():
        return {}
    try:
        return json.loads(COMPANY_INFO_PATH.read_text(encoding="utf-8")).get("companies", {})
    except Exception:
        return {}


def _name_map() -> dict[str, str]:
    """company_info.json優先，quotes_tw.json（自選股報價，可能比company_info.json
    更新，例如新股剛上市還沒進FinMind快取但已經在使用者自選股名單）補缺。"""
    company_info = _company_info()
    names = {code: v.get("name") for code, v in company_info.items() if v.get("name")}
    if QUOTES_TW_PATH.exists():
        try:
            quotes = json.loads(QUOTES_TW_PATH.read_text(encoding="utf-8")).get("quotes", {})
            for code, v in quotes.items():
                if v.get("name") and code not in names:
                    names[code] = v.get("name")
        except Exception:
            pass
    return names


def main():
    frozen = load_frozen_weights()
    apply_frozen_weights(frozen)
    print(f"已套用凍結權重 weights_frozen.json（frozen_at={frozen['frozen_at']}，"
          f"sha256={frozen['weights_sha256'][:12]}...）")

    prior_count = None
    if OUT_PATH.exists():
        try:
            prior_count = len(json.loads(OUT_PATH.read_text(encoding="utf-8")).get("stocks", []))
        except Exception:
            prior_count = None

    cs = compute_scores_live()
    company_info = _company_info()
    name_map = _name_map()
    as_of = datetime.now(TW_TZ).strftime("%Y-%m-%d")

    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-live-json", "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW", "weights_hash": frozen["weights_sha256"],
                "disclaimer": "非投資建議；這次沒有任何股票算出分數（repo內JSON資料可能還太少）。",
            },
            "weights": {k: v["weight"] for k, v in score_v2.FACTOR_DEFS.items()}, "stocks": [],
        }
    else:
        # 2026-08-27修正（使用者P1-新裁示，取代舊的coverage<0.5硬性排除）：
        # 「選股改為全市場+資料完整度，不要用門檻排除」——341/2586檔、平均
        # coverage 0.597，門檻把約一半直接踢掉。改成全部進榜，coverage當成
        # 「資料完整度」揭露欄位（前端用視覺條+弱化樣式呈現，不是伺服器端
        # 藏起來），使用者可以自己用完整度排序/篩選。
        # 流動性門檻維持（使用者原話：「這條是對的，不要拿掉」）——2026-08-27
        # 這輪才新增，用data/price_history.json的turnover算近20日均成交值，
        # 低於LIQUIDITY_FLOOR_20D_VALUE的標記「流動性不足」，不給數字排名
        # （沿用research端score_v2.py的既有設計：流動性不足的股票留在清單
        # 供搜尋，但不進主排行榜的排名）。
        # ── 2026-09-06（稽核.一）先剔除已下市/不在市的代號 ──────────────────
        # 第一份全市場稽核報告抓到：三份榜單合計 69＋69＋23 檔已下市股票還在排名裡，
        # 帶著 2010～2024 年的舊價格（矽品 2325、勝華 2384、康友-KY 6452 甚至是
        # 未來成長榜第 1 名）。價量/財報檔案裡留著舊資料是正常的（歷史就是歷史），
        # 但**排行榜不能推薦一檔已經不存在的股票**，所以在這裡用官方在市名冊擋掉。
        # 名冊由 scripts/build_listed_universe.py 每日更新；檔案不存在或內容明顯不完整
        # 時一律不過濾（寧可多顯示，也不要因為抓取失敗把整個榜單清空）。
        try:
            uni_path = REPO_ROOT / "data" / "listed_universe.json"
            active = set(json.loads(uni_path.read_text(encoding="utf-8")).get("active") or [])
            if len(active) >= 1000:
                before = len(cs)
                cs = cs[cs.index.isin(active)]
                if before != len(cs):
                    print(f"  剔除不在官方在市名冊的代號：{before - len(cs)} 檔（剩 {len(cs)}）")
            else:
                print(f"  ! listed_universe.json 只有 {len(active)} 檔，不完整，跳過下市過濾")
        except FileNotFoundError:
            print("  ! 沒有 data/listed_universe.json，跳過下市過濾（先跑 scripts/build_listed_universe.py）")
        except Exception as e:
            print(f"  ! 下市過濾失敗（{type(e).__name__}: {e}），跳過")

        # 還在名冊、但價格早就停住的也要擋（正峰 1538、永冠-KY 1589 停在 2024-12-31，
        # 卻仍排在榜上顯示一年半前的價格當現價）。用 price_history 的全市場最新日期
        # 當基準，不打網路。
        try:
            per_last = {c: (rows[-1].get("date") or "") for c, rows in price_history.items() if rows}
            latest = max((d for d in per_last.values() if d), default=None)
            if latest:
                from datetime import date as _date
                base = _date(*(int(x) for x in latest.split("-")))
                stale = set()
                for c, d in per_last.items():
                    try:
                        if (base - _date(*(int(x) for x in d.split("-")))).days > 30:
                            stale.add(c)
                    except Exception:
                        continue
                before = len(cs)
                cs = cs[~cs.index.isin(stale)]
                if before != len(cs):
                    print(f"  剔除價格落後超過30天的代號：{before - len(cs)} 檔（剩 {len(cs)}）")
        except Exception as e:
            print(f"  ! 過期價格過濾失敗（{type(e).__name__}: {e}），跳過")

        cs["liquidity_insufficient"] = (
            cs["liquidity_20d"].isna() | (cs["liquidity_20d"] < LIQUIDITY_FLOOR_20D_VALUE)
        )
        ranked = cs.sort_values(["liquidity_insufficient", "total_score"], ascending=[True, False]).copy()
        liquidity_ok_mask = ~ranked["liquidity_insufficient"]
        ranked.loc[liquidity_ok_mask, "display_rank"] = range(1, int(liquidity_ok_mask.sum()) + 1)

        stocks = []
        for sid, row in ranked.iterrows():
            present = [k for k in score_v2.FACTOR_DEFS if pd.notna(row.get(f"{k}_score"))]
            missing = [k for k in score_v2.FACTOR_DEFS if k not in present]
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
            if row["coverage"] < COVERAGE_MIN_FOR_RANKING:
                flags.append("資料稀疏，分數僅供參考")
            display_rank = row.get("display_rank")
            stocks.append({
                "code": sid, "name": name_map.get(sid),
                "industry": (company_info.get(sid) or {}).get("industry"),
                "rank": int(display_rank) if pd.notna(display_rank) else None,
                "total_score": round(float(row["total_score"]), 1),
                "coverage": round(float(row["coverage"]), 2),
                "missing_factors": missing,
                "liquidity_20d": _r(row.get("liquidity_20d")),
                "data_asof": as_of,
                "summary": _summary(row, present),
                "factors": factors_obj,
                "flags": flags,
                "news_warning": None,
            })
        avg_coverage = round(float(cs["coverage"].mean()), 3)
        payload = {
            "meta": {
                "engine_version": "scoring-live-json",
                "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW",
                "universe_size": len(cs),
                "avg_coverage": avg_coverage,
                "liquidity_floor_20d_value": LIQUIDITY_FLOOR_20D_VALUE,
                "weights_hash": frozen["weights_sha256"],
                "source": "只讀repo內data/fundamentals.json+data/stock_detail.json+data/price_history.json"
                           "+data/company_info.json（不讀parquet、不呼叫FinMind），"
                           "供GitHub Actions每日排程使用，見generate_scores_live.py檔頭說明。",
                "disclaimer": (
                    "非投資建議；所有分數只是資料整理與排序，不代表買賣訊號。資料為盤後/延遲資料。"
                    "2026-08-27改版：不再用coverage<0.5排除股票，全市場都進榜——"
                    "總分跟「資料完整度」(coverage)是兩件事，高分低完整度不代表可信，"
                    "請一併參考每檔的coverage數值跟missing_factors清單。"
                    "analyst/catalyst兩項全市場沒有資料源、technical用未還原權息的收盤價"
                    "（除權息前後會失真）、revenue_momentum未做規模分層——已依coverage"
                    "規則重新分配權重，不會把沒資料當成0分，細節見"
                    "generate_scores_live.py檔頭的已知限制說明。"
                ),
            },
            "weights": {k: v["weight"] for k, v in score_v2.FACTOR_DEFS.items()},
            "stocks": stocks,
        }

    new_count = len(payload["stocks"])
    # 2026-08-27修正：移除coverage門檻後，股票數量不太會再暴跌（全部都進榜），
    # 這個安全網原本盯的「合格檔數暴跌」訊號已經不夠敏感——改成盯「平均coverage
    # 暴跌」，一個真的讓多數因子失效的bug還是會讓avg_coverage大幅下降，即使
    # 股票總數沒變。
    prior_avg_coverage = None
    if OUT_PATH.exists():
        try:
            prior_avg_coverage = json.loads(OUT_PATH.read_text(encoding="utf-8")).get("meta", {}).get("avg_coverage")
        except Exception:
            prior_avg_coverage = None
    new_avg_coverage = payload["meta"].get("avg_coverage")
    collapse = (
        prior_avg_coverage is not None and new_avg_coverage is not None
        and prior_avg_coverage > 0 and new_avg_coverage < prior_avg_coverage * 0.5
    )
    payload["meta"]["coverage_collapse_warning"] = collapse
    payload["meta"]["prior_run_stock_count"] = prior_count
    payload["meta"]["prior_run_avg_coverage"] = prior_avg_coverage
    if collapse:
        # 2026-08-27修正：Windows終端機cp950編碼印"⚠"會直接UnicodeEncodeError
        # 崩潰整支腳本（在write_text之前，等於這次分數完全沒寫出去）——跟
        # CLAUDE.md記錄過的"・"同一類地雷，這裡改用純ASCII警告字樣。
        print(f"WARNING: 合格檔數從 {prior_count} 暴跌到 {new_count}（低於前次的50%），"
              f"已寫入 meta.coverage_collapse_warning=true")

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=float), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{new_count} 檔計算出分數（樣本共 {len(cs)} 檔有任一因子資料）")
    if not cs.empty:
        print(cs[["total_score", "coverage", "rank"]].head(10).to_string())


if __name__ == "__main__":
    main()
