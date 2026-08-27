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
  檔才能補，目前誠實留白，不是忘記做）。
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
- `technical`（技術型態）：**完全沒有來源**——需要per股票的每日OHLC/成交量
  歷史序列，目前committed的JSON裡沒有任何檔案retained這個（`quotes_tw.json`
  只有自選股當下報價+20筆sparkline，不是全市場歷史），這裡誠實留NaN，用
  coverage重新分配權重機制處理，不是bug。
- `analyst`/`catalyst`：跟研究端一樣，這兩項全市場沒有免費資料源，誠實留NaN。

以上任何一項未來要補，原則不變：先問「有沒有第二條路、能不能從已有欄位推導」，
不是直接放棄——已經在STATUS.json的known_limitations列出，供之後排優先序。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import score_v2
from score_live import apply_frozen_weights, load_frozen_weights
from score_v2 import COVERAGE_MIN_FOR_RANKING, REVENUE_BASE_FLOOR, REVENUE_YOY_HARD_CAP, _pct_score, _r

REPO_ROOT = Path(__file__).parent.parent
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
MARKET_TW_PATH = REPO_ROOT / "data" / "market_tw.json"
QUOTES_TW_PATH = REPO_ROOT / "data" / "quotes_tw.json"
OUT_PATH = REPO_ROOT / "scores.json"
TW_TZ = timezone(timedelta(hours=8))

GROWTH_QUALITY_MONTHS = 24  # 近12個月 vs 再前12個月，24個月起跳，要求視窗內完全連續


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在——這支腳本只讀repo內已commit的JSON，不會自己去產生。")
    return json.loads(path.read_text(encoding="utf-8"))


def _eps_yoy_from_quarters(quarters: list[dict]) -> float | None:
    if not quarters:
        return None
    latest = max(quarters, key=lambda r: (r["year"], r["quarter"]))
    prior = next((r for r in quarters if r["year"] == latest["year"] - 1 and r["quarter"] == latest["quarter"]), None)
    if prior is None:
        return None
    eps_now, eps_prior = latest.get("eps"), prior.get("eps")
    if eps_now is None or eps_prior is None or eps_prior == 0:
        return None
    return (eps_now - eps_prior) / abs(eps_prior)


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
    all_codes = sorted(set(fundamentals) | set(stock_detail))

    rows = []
    for code in all_codes:
        fd = fundamentals.get(code, {})
        sd = stock_detail.get(code, {})
        fin = sd.get("financials", {})

        eps_yoy = _eps_yoy_from_quarters(fin.get("quarters") or [])
        eps_source = "stock_detail_quarters" if eps_yoy is not None else None

        rev_rows = fd.get("revenue_history_scoring") or fd.get("month_revenue") or []
        rev_stats = _revenue_stats(rev_rows)
        rev_grow_12m = _growth_quality(rev_rows)

        chips = _chips_signal(sd.get("institutional"))

        per = (fd.get("ratios") or {}).get("per")
        pe = per if per is not None and per > 0 else None
        peg = (pe / (eps_yoy * 100)) if (pe is not None and eps_yoy is not None and eps_yoy > 0) else None
        if peg is not None and not np.isfinite(peg):
            peg = None

        rows.append({
            "stock_id": code,
            "raw_eps_yoy": eps_yoy, "eps_yoy_source": eps_source,
            "raw_rev_yoy": rev_stats["yoy"],
            "raw_rev_prior_year_revenue": rev_stats["prior_year_revenue"],
            "raw_rev_abs_growth": rev_stats["abs_growth"],
            "raw_rev_grow": rev_grow_12m,
            "raw_inst_flow": chips,
            "raw_pe": pe, "raw_peg": peg,
        })

    cs = pd.DataFrame(rows).set_index("stock_id")
    return cs


def compute_scores_live() -> pd.DataFrame:
    cs = build_rows()
    if cs.empty:
        return cs

    raw_col = {
        "earnings_growth": "raw_eps_yoy",
        "revenue_momentum": "raw_rev_yoy",
        "growth_quality": "raw_rev_grow",
        "chips": "raw_inst_flow",
        "valuation_adj": "raw_peg",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], score_v2.FACTOR_DEFS[key]["higher_better"])
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct

    # technical/analyst/catalyst：JSON-only路徑沒有來源，誠實留NaN，見檔頭說明。
    for key in ("technical", "analyst", "catalyst"):
        cs[f"{key}_score"] = np.nan
        cs[f"{key}_pct"] = np.nan

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


def _raw_dict(key: str, row: pd.Series) -> dict:
    if key == "earnings_growth":
        return {"eps_yoy": _r(row["raw_eps_yoy"]), "eps_yoy_source": row.get("eps_yoy_source")}
    if key == "revenue_momentum":
        return {
            "rev_yoy": _r(row["raw_rev_yoy"]),
            "prior_year_revenue": _r(row["raw_rev_prior_year_revenue"]),
            "abs_growth": _r(row["raw_rev_abs_growth"]),
        }
    if key == "growth_quality":
        return {"rev_growth_12m_yoy": _r(row["raw_rev_grow"])}
    if key == "chips":
        return {"inst_net_lots_available_days": _r(row["raw_inst_flow"])}
    if key == "valuation_adj":
        return {"pe": _r(row["raw_pe"]), "eps_yoy": _r(row["raw_eps_yoy"]), "peg": _r(row["raw_peg"])}
    return {}


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = max(1, round((1 - pct) * 100)) if pd.notna(pct) else None
    if key == "earnings_growth":
        return f"最新季度EPS年增 {row['raw_eps_yoy']*100:+.0f}%（季度資料來自stock_detail.json），居全市場前 {front}%。"
    if key == "revenue_momentum":
        return f"最新月營收年增 {row['raw_rev_yoy']*100:+.1f}%（已排除基期<3000萬元樣本、±200%硬上限，未做規模分層），居全市場前 {front}%。"
    if key == "growth_quality":
        return f"近12個月營收合計年增 {row['raw_rev_grow']*100:+.1f}%（要求24個月視窗內無缺月），居全市場前 {front}%。"
    if key == "chips":
        return f"近期（依累積天數，最多5日）三大法人買賣超合計 {row['raw_inst_flow']:+.0f} 張，居全市場前 {front}%。"
    if key == "valuation_adj":
        return f"本益比 {row['raw_pe']:.1f} 倍，PEG={row['raw_peg']:.2f}，估值居全市場前 {front}%。"
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


def _name_map() -> dict[str, str]:
    if not QUOTES_TW_PATH.exists():
        return {}
    try:
        quotes = json.loads(QUOTES_TW_PATH.read_text(encoding="utf-8")).get("quotes", {})
    except Exception:
        return {}
    return {code: v.get("name") for code, v in quotes.items() if v.get("name")}


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
        eligible = cs[cs["coverage"] >= COVERAGE_MIN_FOR_RANKING].copy()
        eligible = eligible.sort_values("total_score", ascending=False)
        eligible["display_rank"] = range(1, len(eligible) + 1)
        stocks = []
        for sid, row in eligible.iterrows():
            present = [k for k in score_v2.FACTOR_DEFS if pd.notna(row.get(f"{k}_score"))]
            factors_obj = {
                k: {
                    "score": round(float(row[f"{k}_score"]), 1),
                    "percentile": round(float(row[f"{k}_pct"]), 2),
                    "raw": _raw_dict(k, row),
                    "reason": _reason(k, row),
                } for k in present
            }
            stocks.append({
                "code": sid, "name": name_map.get(sid),
                "industry": None,  # JSON-only路徑沒有產業對照表來源，見檔頭說明
                "rank": int(row["display_rank"]),
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
                "engine_version": "scoring-live-json",
                "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW",
                "universe_size": len(cs),
                "weights_hash": frozen["weights_sha256"],
                "source": "只讀repo內data/fundamentals.json+data/stock_detail.json（不讀parquet、"
                           "不呼叫FinMind），供GitHub Actions每日排程使用，見generate_scores_live.py檔頭說明。",
                "disclaimer": (
                    "非投資建議；所有分數只是資料整理與排序，不代表買賣訊號。資料為盤後/延遲資料。"
                    "這是JSON-only上線評分路徑，technical/analyst/catalyst三項全市場沒有資料源、"
                    "revenue_momentum未做規模分層——已依coverage規則重新分配權重，不會把沒資料當成0分，"
                    "細節見generate_scores_live.py檔頭的已知限制說明。"
                ),
            },
            "weights": {k: v["weight"] for k, v in score_v2.FACTOR_DEFS.items()},
            "stocks": stocks,
        }

    new_count = len(payload["stocks"])
    collapse = prior_count is not None and prior_count > 0 and new_count < prior_count * 0.5
    payload["meta"]["coverage_collapse_warning"] = collapse
    payload["meta"]["prior_run_stock_count"] = prior_count
    if collapse:
        print(f"⚠ 警告：合格檔數從 {prior_count} 暴跌到 {new_count}（低於前次的50%），"
              f"已寫入 meta.coverage_collapse_warning=true")

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=float), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{new_count} 檔計算出分數（樣本共 {len(cs)} 檔有任一因子資料）")
    if not cs.empty:
        print(cs[["total_score", "coverage", "rank"]].head(10).to_string())


if __name__ == "__main__":
    main()
