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


# ══════ 額外的兩個原始指標（revenue_momentum 的當月 YoY／growth_quality 的 12個月滾動年增）══════
# 這兩個不在 factors.py::prepare_factors() 既有的欄位裡，用 pit.py 的 month_revenue_pit()
# 重新算（跟 factors.py::_revenue_yoy_acceleration() 用同一套 PIT 對齊邏輯，只是這裡要的是
# yoy 本身，不是 yoy 的加速度）。month_revenue_pit() 底層走 load_dev() 的 parquet 快取，
# 這裡重複呼叫不會真的多打 FinMind API。

def _revenue_yoy_latest(stock_id: str, start_date: str) -> float | None:
    rev = month_revenue_pit(stock_id, start_date)
    if rev.empty:
        return None
    rev = rev.sort_values(["revenue_year", "revenue_month"]).reset_index(drop=True)
    prior = rev[["revenue_year", "revenue_month", "revenue"]].copy()
    prior["revenue_year"] += 1
    prior = prior.rename(columns={"revenue": "revenue_prior_year"})
    rev = rev.merge(prior, on=["revenue_year", "revenue_month"], how="left")
    rev["yoy"] = (rev["revenue"] - rev["revenue_prior_year"]) / rev["revenue_prior_year"].abs()
    last = rev.dropna(subset=["yoy"])
    return float(last.iloc[-1]["yoy"]) if not last.empty else None


def _revenue_growth_12m(stock_id: str, start_date: str) -> float | None:
    rev = month_revenue_pit(stock_id, start_date)
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


def _r(x):
    """NaN-safe round，寫進 raw dict 用（None 代表沒有這個數字，不是 0）。"""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), 4)


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
        pe = -r["f_value_pe"] if pd.notna(r.get("f_value_pe")) else np.nan
        peg = pe / (eps_yoy * 100) if pd.notna(pe) and pd.notna(eps_yoy) and eps_yoy > 0 else np.nan
        rows.append({
            "stock_id": sid,
            "industry": industry_map.get(sid, "UNKNOWN"),
            "raw_eps_yoy": eps_yoy,
            "raw_inst_flow": r.get("f_inst_flow", np.nan),
            "raw_ma_breakout": r.get("f_ma_breakout", np.nan),
            "raw_pe": pe,
            "raw_peg": peg,
        })
    cs = pd.DataFrame(rows).set_index("stock_id")
    if cs.empty:
        return cs

    # 這兩個要另外抓（見檔案最上面說明），逐檔查 -- 都走 parquet 快取，不會真的多打 API。
    cs["raw_rev_yoy"] = pd.Series({sid: _revenue_yoy_latest(sid, start_date) for sid in cs.index})
    cs["raw_rev_grow"] = pd.Series({sid: _revenue_growth_12m(sid, start_date) for sid in cs.index})

    raw_col = {
        "earnings_growth": "raw_eps_yoy", "revenue_momentum": "raw_rev_yoy",
        "growth_quality": "raw_rev_grow", "chips": "raw_inst_flow",
        "technical": "raw_ma_breakout", "valuation_adj": "raw_peg",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], FACTOR_DEFS[key]["higher_better"])
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct
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
        return {"eps_yoy": _r(row["raw_eps_yoy"])}
    if key == "revenue_momentum":
        return {"rev_yoy": _r(row["raw_rev_yoy"])}
    if key == "growth_quality":
        return {"rev_growth_12m_yoy": _r(row["raw_rev_grow"])}
    if key == "chips":
        return {"inst_net_pct_of_20d_trading_value": _r(row["raw_inst_flow"])}
    if key == "technical":
        return {"ma60_breakout_x_volume_index": _r(row["raw_ma_breakout"])}
    if key == "valuation_adj":
        return {"pe": _r(row["raw_pe"]), "eps_yoy": _r(row["raw_eps_yoy"]), "peg": _r(row["raw_peg"])}
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
        return f"最新月營收年增 {v*100:+.1f}%，居全市場前 {front}%。"
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
) -> pd.DataFrame:
    """寫出符合小抄第五節格式的 scores.json（`code`/`total_score`/`coverage`/
    `factors{score,percentile,raw,reason}`/`flags`/`news_warning`）。
    """
    cs = compute_scores_v2(as_of, data, industry_map, start_date)
    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-v2", "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW", "universe_size": universe_size,
                "disclaimer": "非投資建議；資料為盤後/延遲資料。這次沒有任何股票算出分數（樣本可能太小）。",
            },
            "weights": {k: v["weight"] for k, v in FACTOR_DEFS.items()}, "stocks": [],
        }
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return cs

    eligible = cs[cs["coverage"] >= COVERAGE_MIN_FOR_RANKING].sort_values("total_score", ascending=False)
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
        stocks.append({
            "code": sid,
            "name": name_map.get(sid) if name_map else None,
            "industry": row["industry"],
            "rank": int(row["rank"]),
            "total_score": round(float(row["total_score"]), 1),
            "coverage": round(float(row["coverage"]), 2),
            "data_asof": as_of,
            "summary": _summary(row, present),
            "factors": factors_obj,
            "flags": [],
            "news_warning": None,
        })

    payload = {
        "meta": {
            "engine_version": "scoring-v2",
            "generated_at": datetime.now(TW_TZ).isoformat(),
            "data_asof": as_of,
            "market": "TW",
            "universe_size": universe_size,
            "disclaimer": (
                "非投資建議；所有分數只是資料整理與排序，不代表買賣訊號。資料為盤後/延遲資料。"
                "analyst（機構觀點）台股暫無免費目標價資料源、catalyst（題材/事件）本輪尚未實作"
                "（下一輪接新聞/供應鏈），這兩項對全部股票都缺資料，已依 coverage 規則重新分配"
                "權重，不會把沒資料當成 0 分。coverage < 0.5 的股票不進本清單（僅供參考名單）。"
            ),
        },
        "weights": {k: v["weight"] for k, v in FACTOR_DEFS.items()},
        "stocks": stocks,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False, default=float)
    return cs
