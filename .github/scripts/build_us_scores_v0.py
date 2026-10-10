"""美股評分 v0（2026-10-11 常備.開發-17）：價值／成長／品質三分項 → data/us_scores_v0.json。

**定位，先講清楚**：這是 App 選股頁美股分頁的「資料整理與排序」展示，**v0，未經回測驗證**。
受 CLAUDE.md 第十四節「凍結.二」限制：**不登記為試驗、不做回測**，也不得被任何研究腳本拿去
當訊號用（宇宙是 SEC 當下名冊，不是時點宇宙，見 fetch_us_financials_sec.py 說明）。

資料源（皆美股原生，符合 CLAUDE.md 七節「各市場一律使用該市場的原生資料源」）：
- 財報：data/us_financials.json（SEC XBRL companyfacts 年度值，fetch_us_financials_sec.py 產出）
- 股價：yfinance 一次批次下載近 5 日收盤（只用來算本益比）；失敗時退回 data/quotes_us.json
  （Finnhub，僅自選 9 檔）；都沒有就「價值」分項缺值，不猜。

三分項公式（「公式沿用台股 score_v2 的同名因子，只改資料源」的對應方式）：
- 成長 ← 台股 `earnings_growth`（research/live_factors.py::earnings_growth()）：
  EPS 年增、營收年增、毛利率年變化、營益率年變化四個子訊號有幾個算幾個取平均；
  EPS 年增公式、±200% 硬上限照抄。差異：台股是「最新一季 vs 去年同季」，這裡是「最新年度 vs
  前一年度」（SEC companyfacts 年度值，季度值未接）。
- 價值 ← 台股 `valuation_adj`（generate_scores_live.py）：PER、PBR、PEG 各取百分位再平均，
  越低越便宜。差異：PBR 缺（us_financials.json 沒有每股淨值）；產業分類只有 9 檔
  （data/us_sic.json），台股規則「同產業不足 8 檔退回全市場」→ 這裡等於全部全市場排名。
  申報幣別非 USD、或 IFRS 申報（EPS 為每普通股非每 ADR）者 PER 口徑對不上，排除不算。
- 品質 ← **台股 score_v2 沒有同名因子**（score_v2 的 growth_quality 實際是營收成長，已併入
  上面的「成長」）。v0 自訂：毛利率、營益率、FCF 利潤率、負債比（反向）四個水準值的全市場
  百分位平均——[自行裁量] 選這四個是因為 us_financials.json 現成就有，不新增資料源。
- 每個分項最後都走 score_v2._pct_score() 同一套：去極值 1%/99% → rank 百分位 → 方向 → ×10。
- 總分：三分項等權（1/3），缺項重新分配權重；coverage＝有值分項數/3，< 0.5 不進排名
  （同 score_v2 COVERAGE_MIN_FOR_RANKING）。[自行裁量] 等權：score_v2 沒有品質權重可沿用。

非投資建議。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
FIN_PATH = ROOT / "data" / "us_financials.json"
QUOTES_PATH = ROOT / "data" / "quotes_us.json"
SIC_PATH = ROOT / "data" / "us_sic.json"
OUT_PATH = ROOT / "data" / "us_scores_v0.json"

YOY_HARD_CAP = 2.0  # 同 live_factors.YOY_HARD_CAP
COVERAGE_MIN_FOR_RANKING = 0.5  # 同 score_v2.COVERAGE_MIN_FOR_RANKING
PILLARS = {
    "value": {"label": "價值", "higher_better": False, "tw_source": "valuation_adj（PER/PEG 百分位，PBR 缺）"},
    "growth": {"label": "成長", "higher_better": True, "tw_source": "earnings_growth（年度版）"},
    "quality": {"label": "品質", "higher_better": True, "tw_source": "台股無同名因子，v0 自訂"},
}


def _cap(x):
    if x is None:
        return None
    return max(-YOY_HARD_CAP, min(YOY_HARD_CAP, x))


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _rank_pct(values: dict) -> dict:
    """pandas rank(pct=True) 的等價（同值取平均名次），None 保持 None。"""
    items = sorted((v, k) for k, v in values.items() if v is not None)
    n = len(items)
    out = {k: None for k in values}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][0] == items[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for t in range(i, j + 1):
            out[items[t][1]] = avg_rank / n
        i = j + 1
    return out


def _quantile(sorted_vals: list, q: float) -> float:
    """pandas Series.quantile 預設 linear 插值。"""
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def pct_score(raw: dict, higher_better: bool) -> tuple[dict, dict]:
    """score_v2._pct_score() 的純 Python 版：去極值(1%/99%) → rank 百分位 → 方向 → ×10。"""
    valid = sorted(v for v in raw.values() if v is not None)
    if len(valid) < 3:
        return {k: None for k in raw}, {k: None for k in raw}
    lo, hi = _quantile(valid, 0.01), _quantile(valid, 0.99)
    clipped = {k: (None if v is None else min(max(v, lo), hi)) for k, v in raw.items()}
    pct = _rank_pct(clipped)
    if not higher_better:
        pct = {k: (None if p is None else 1 - p) for k, p in pct.items()}
    score = {k: (None if p is None else round(p * 10, 1)) for k, p in pct.items()}
    return score, {k: (None if p is None else round(p, 2)) for k, p in pct.items()}


def eps_yoy(now, prev):
    """照抄 live_factors.earnings_growth() 的 EPS 年增寫法（含負基期處理與硬上限）。"""
    if now is None or prev is None or abs(prev) <= 0.05:
        return None
    return _cap(now / abs(prev) - (1 if prev > 0 else -1) if prev < 0 else now / prev - 1)


def growth_raw(f: dict) -> tuple[float | None, dict]:
    comp = {"eps_yoy": eps_yoy(f.get("eps"), f.get("eps_prior")),
            "revenue_yoy": _cap(f.get("revenue_yoy")),
            "gross_margin_yoy_pp": None, "op_margin_yoy_pp": None}
    if f.get("gross_margin") is not None and f.get("gross_margin_prior") is not None:
        comp["gross_margin_yoy_pp"] = round((f["gross_margin"] - f["gross_margin_prior"]) * 100, 2)
    if f.get("operating_margin") is not None and f.get("operating_margin_prior") is not None:
        comp["op_margin_yoy_pp"] = round((f["operating_margin"] - f["operating_margin_prior"]) * 100, 2)
    parts = [comp["eps_yoy"], comp["revenue_yoy"]]
    parts += [v / 100.0 for v in (comp["gross_margin_yoy_pp"], comp["op_margin_yoy_pp"]) if v is not None]
    comp["n_signals"] = sum(1 for k in ("eps_yoy", "revenue_yoy", "gross_margin_yoy_pp", "op_margin_yoy_pp")
                            if comp[k] is not None)
    return _mean(parts), comp


def fetch_prices(tickers: list[str]) -> tuple[dict, dict]:
    """回傳 ({ticker: close}, meta)。yfinance 批次一次；失敗退回 quotes_us.json。"""
    prices: dict[str, float] = {}
    meta = {"primary": "yfinance download(period=5d) 最近收盤", "as_of": None, "fallback_used": [], "error": None}
    try:
        import yfinance as yf  # noqa: PLC0415
        df = yf.download(tickers, period="5d", auto_adjust=False, progress=False, threads=True,
                         group_by="column")
        close = df["Close"] if "Close" in df else None
        if close is not None:
            for t in tickers:
                if t in close:
                    s = close[t].dropna()
                    if len(s):
                        prices[t] = float(s.iloc[-1])
            if len(close.index):
                meta["as_of"] = str(close.dropna(how="all").index.max())[:10]
    except Exception as e:  # noqa: BLE001
        meta["error"] = f"{type(e).__name__}: {e}"
        print(f"[warn] yfinance 批次下載失敗：{meta['error']}")
    try:
        q = json.loads(QUOTES_PATH.read_text(encoding="utf-8")).get("quotes", {})
        for t, row in q.items():
            if t in tickers and t not in prices and row.get("price"):
                prices[t] = float(row["price"])
                meta["fallback_used"].append(t)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] quotes_us.json 備援讀取失敗：{e}")
    return prices, meta


def main() -> int:
    try:
        fin_doc = json.loads(FIN_PATH.read_text(encoding="utf-8"))
        fin = fin_doc["financials"]
    except Exception as e:  # noqa: BLE001
        print(f"[error] 讀不到 {FIN_PATH.name}：{e}；不覆蓋既有輸出")
        return 1
    if len(fin) < 50:
        print(f"[error] 財報只有 {len(fin)} 檔（<50），不覆蓋既有輸出")
        return 1
    try:
        sic = json.loads(SIC_PATH.read_text(encoding="utf-8")).get("tickers", {})
    except Exception:  # noqa: BLE001
        sic = {}

    tickers = sorted(fin)
    prices, price_meta = fetch_prices(tickers)
    print(f"股價取得 {len(prices)}/{len(tickers)} 檔（備援 {len(price_meta['fallback_used'])} 檔）")

    pe, peg, g_raw, g_comp, warns = {}, {}, {}, {}, {}
    for t in tickers:
        f = fin[t]
        w = []
        g_raw[t], g_comp[t] = growth_raw(f)
        e = f.get("eps")
        ifrs = any("IFRS" in x for x in f.get("warnings", []))
        pe[t] = None
        if f.get("currency") != "USD":
            w.append(f"申報幣別 {f.get('currency')}，本益比口徑對不上，不算價值")
        elif ifrs:
            w.append("IFRS 申報 EPS 為每普通股非每 ADR，不算價值")
        elif t not in prices:
            w.append("無股價，不算價值")
        elif e is not None and e > 0:
            pe[t] = prices[t] / e
        else:
            w.append("EPS ≤ 0 或缺，本益比無意義")
        gy = g_comp[t]["eps_yoy"]
        peg[t] = (pe[t] / (gy * 100)) if (pe[t] is not None and gy is not None and gy > 0) else None
        warns[t] = w

    # 價值：PER、PEG 各自全市場百分位（越低越便宜）再平均——同 generate_scores_live 估值寫法。
    pe_r, peg_r = _rank_pct(pe), _rank_pct(peg)
    v_raw = {t: _mean([pe_r[t], peg_r[t]]) for t in tickers}

    # 品質（v0 自訂）：四個水準值全市場百分位平均，負債比取反向。
    q_parts = {
        "gross_margin": _rank_pct({t: fin[t].get("gross_margin") for t in tickers}),
        "operating_margin": _rank_pct({t: fin[t].get("operating_margin") for t in tickers}),
        "fcf_margin": _rank_pct({t: fin[t].get("fcf_margin") for t in tickers}),
        "low_debt": _rank_pct({t: (None if fin[t].get("debt_ratio") is None else -fin[t]["debt_ratio"])
                               for t in tickers}),
    }
    q_raw = {t: _mean([q_parts[k][t] for k in q_parts]) for t in tickers}

    raws = {"value": v_raw, "growth": g_raw, "quality": q_raw}
    scored = {k: pct_score(raws[k], PILLARS[k]["higher_better"]) for k in PILLARS}

    stocks = []
    for t in tickers:
        f = fin[t]
        pillars = {}
        for k in PILLARS:
            sc, pc = scored[k][0][t], scored[k][1][t]
            if sc is None:
                continue
            if k == "value":
                raw = {"pe": None if pe[t] is None else round(pe[t], 2),
                       "peg": None if peg[t] is None else round(peg[t], 2), "pb": None,
                       "price": round(prices[t], 2) if t in prices else None}
            elif k == "growth":
                raw = g_comp[t]
            else:
                raw = {"gross_margin": f.get("gross_margin"), "operating_margin": f.get("operating_margin"),
                       "fcf_margin": f.get("fcf_margin"), "debt_ratio": f.get("debt_ratio"),
                       "n_signals": sum(1 for kk in q_parts if q_parts[kk][t] is not None)}
            pillars[k] = {"score": sc, "pct": pc, "raw": raw}
        coverage = round(len(pillars) / len(PILLARS), 2)
        total = round(sum(p["score"] for p in pillars.values()) / len(pillars), 1) if pillars else None
        stocks.append({
            "code": t, "name": (sic.get(t) or {}).get("entity_name"), "exchange": f.get("exchange"),
            "total_score": total, "coverage": coverage, "pillars": pillars,
            "period_end": f.get("period_end"), "filed": f.get("filed"), "currency": f.get("currency"),
            "warnings": warns[t] + list(f.get("warnings", [])),
        })
    ranked = sorted((s for s in stocks if s["total_score"] is not None and s["coverage"] >= COVERAGE_MIN_FOR_RANKING),
                    key=lambda s: -s["total_score"])
    for i, s in enumerate(ranked, 1):
        s["rank"] = i
    for s in stocks:
        s.setdefault("rank", None)
    stocks.sort(key=lambda s: (s["rank"] is None, s["rank"] or 0, s["code"]))

    payload = {
        "meta": {
            "market": "US", "version": "us-score-v0",
            "label": "v0，未經回測驗證",
            "disclaimer": "資料整理與排序，未經回測驗證、未登記為試驗（受凍結.二限制），非投資建議。",
            "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
            "financials_generated_at": fin_doc.get("generated_at"),
            "financials_source": fin_doc.get("source"),
            "price_source": price_meta,
            "pillars": {k: {"label": v["label"], "tw_source": v["tw_source"], "weight": round(1 / 3, 4)}
                        for k, v in PILLARS.items()},
            "method": "三分項各自經 score_v2._pct_score 同法（去極值1%/99%→百分位→×10），總分等權、缺項重分配；"
                      "coverage<0.5 不排名。成長＝台股 earnings_growth 年度版；價值＝台股 valuation_adj（PBR 缺、"
                      "產業不足退全市場）；品質＝v0 自訂（毛利率/營益率/FCF利潤率/負債比反向）。",
            "universe_note": "SEC 當下名冊前段＋自選股，非時點宇宙，不得用於回測。",
            "count": len(stocks), "ranked_count": len(ranked),
            "pillar_coverage": {k: sum(1 for s in stocks if k in s["pillars"]) for k in PILLARS},
        },
        "stocks": stocks,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫 {OUT_PATH.name}：{len(stocks)} 檔，排名 {len(ranked)} 檔，分項涵蓋 {payload['meta']['pillar_coverage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
