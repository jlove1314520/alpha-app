# -*- coding: utf-8 -*-
"""JSON-only 評分管線的八因子計算（2026-09-05，總司令裁示「八因子全部填上」）。

**為什麼獨立成一支**：`generate_scores_live.py` 原本每個因子只用單一訊號，缺一個欄位整個因子就是
NaN，導致全市場覆蓋率低到誇張（實測 4 位數普通股 2320 檔裡：財報成長 25.4%、成長性 13.3%、
估值 11.2%、機構觀點 0%、題材事件 0%），排行第一的永擎 7711 只有 32% 完整度卻顯示 9.9 分。
這支把每個因子改成「多個子訊號、有幾個算幾個」的複合，並補上原本沒有資料源的兩個因子，
邏輯獨立可測（`research/live_factors_test.py`），不跟 I/O 混在一起。

**八因子的真實資料依賴**（沒有一項需要新聞以外的付費資料）：
| 因子 | 子訊號 | 來源 |
|---|---|---|
| earnings_growth 財報成長 | EPS年增、營收年增、毛利率年變化、營益率年變化 | stock_detail.json financials.quarters |
| revenue_momentum 營收動能 | 最新月營收年增 | fundamentals.json month_revenue |
| growth_quality 成長性 | 近12個月營收合計 vs 前12個月 | fundamentals.json revenue_history_scoring |
| chips 籌碼 | 三大法人近5日淨買超合計 | stock_detail.json institutional |
| technical 技術型態 | MA多空排列、20/60日相對位置、RSI14、量能變化 | price_history.json |
| valuation_adj 估值(成長調整) | PER、PBR、PEG 的同產業百分位 | fundamentals.json ratios + EPS年增 |
| analyst 機構行為 | 外資/投信連續買賣天數＋近期淨買超趨勢 | stock_detail.json institutional.history |
| catalyst 題材/事件 | 事件類型權重×新鮮度衰減 | data/events.json（`fetch_events.py` 產出） |

**analyst 的誠實說明**：台股沒有免費的分析師目標價／評等資料源，所以這個因子**不是**「機構觀點」，
是**「機構行為」**——用法人實際的買賣行為（連續買超天數、淨買超趨勢）當代理。標籤與說明都要
講清楚這件事，不能讓使用者以為是分析師評等。美股路徑（yfinance targetMeanPrice）另外實作。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

TW_TZ = timezone(timedelta(hours=8))
YOY_HARD_CAP = 2.0  # ±200%，跟既有 REVENUE_YOY_HARD_CAP 一致（低基期會製造無意義的極端值）


def _f(v: Any) -> float | None:
    """寬鬆轉 float：None/空字串/非數字都回 None，不拋例外。"""
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _cap(x: float | None, cap: float = YOY_HARD_CAP) -> float | None:
    return None if x is None else max(min(x, cap), -cap)


def _mean(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


# ─────────────────────────────── 財報成長 ───────────────────────────────
def earnings_growth(quarters: list[dict] | None) -> tuple[float | None, dict]:
    """EPS年增、營收年增、毛利率年變化(百分點)、營益率年變化(百分點) 的平均。

    只要 4 個子訊號有任何一個算得出來就給值（原本必須有 EPS 年增才給，
    害財報覆蓋 1944 檔的資料只換到 589 檔有分數）。年變化都是「最新一季 vs 去年同季」。
    毛利率/營益率是百分點差，除以 100 讓量級跟年增率可比後再平均。
    """
    comp: dict[str, float | None] = {"eps_yoy": None, "revenue_yoy": None,
                                     "gross_margin_yoy_pp": None, "op_margin_yoy_pp": None}
    if not quarters:
        return None, comp
    rows = [q for q in quarters if q.get("year") and q.get("quarter")]
    if not rows:
        return None, comp
    rows.sort(key=lambda q: (q["year"], q["quarter"]))
    latest = rows[-1]
    prior = next((q for q in rows if q["year"] == latest["year"] - 1 and q["quarter"] == latest["quarter"]), None)
    if prior is None:
        return None, comp

    eps_now, eps_prev = _f(latest.get("eps")), _f(prior.get("eps"))
    if eps_now is not None and eps_prev is not None and abs(eps_prev) > 0.05:
        comp["eps_yoy"] = _cap(eps_now / abs(eps_prev) - (1 if eps_prev > 0 else -1) if eps_prev < 0 else eps_now / eps_prev - 1)
    rev_now, rev_prev = _f(latest.get("revenue")), _f(prior.get("revenue"))
    if rev_now is not None and rev_prev and rev_prev > 0:
        comp["revenue_yoy"] = _cap(rev_now / rev_prev - 1)
    gm_now, gm_prev = _f(latest.get("gross_margin_pct")), _f(prior.get("gross_margin_pct"))
    if gm_now is not None and gm_prev is not None:
        comp["gross_margin_yoy_pp"] = gm_now - gm_prev
    om_now, om_prev = _f(latest.get("op_margin_pct")), _f(prior.get("op_margin_pct"))
    if om_now is not None and om_prev is not None:
        comp["op_margin_yoy_pp"] = om_now - om_prev

    parts = [comp["eps_yoy"], comp["revenue_yoy"]]
    parts += [v / 100.0 for v in (comp["gross_margin_yoy_pp"], comp["op_margin_yoy_pp"]) if v is not None]
    val = _mean([p for p in parts if p is not None])
    comp["as_of"] = f"{latest['year']}Q{latest['quarter']}"
    comp["n_signals"] = sum(1 for k in ("eps_yoy", "revenue_yoy", "gross_margin_yoy_pp", "op_margin_yoy_pp") if comp[k] is not None)
    return val, comp


# ─────────────────────────────── 技術型態 ───────────────────────────────
def _closes(price_rows: list[dict] | None, field: str = "close") -> list[float]:
    if not price_rows:
        return []
    out = []
    for r in price_rows:
        v = _f(r.get(field))
        if v is not None and v > 0:
            out.append(v)
    return out


def rsi(closes: list[float], window: int = 14) -> float | None:
    """Wilder RSI。資料不足回 None。"""
    if len(closes) < window + 1:
        return None
    gains, losses = [], []
    for a, b in zip(closes[-window - 1:-1], closes[-window:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain, avg_loss = sum(gains) / window, sum(losses) / window
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def technical(price_rows: list[dict] | None) -> tuple[float | None, dict]:
    """四個子訊號平均（都正規化到大約 -1~+1）：
    1. MA 多空排列：MA5>MA20>MA60 給 +1，完全空頭排列 -1，其餘按滿足的條件數線性。
    2. 20/60 日相對位置：收盤價在近 60 日高低區間的位置，轉成 -1~+1。
    3. RSI14：(RSI-50)/50。
    4. 量能變化：近 5 日均量 / 近 20 日均量 - 1，上下限 ±1。
    有幾個算幾個（例如只有 20 天資料時 MA60 那項不算），全部算不出來才回 None。
    """
    comp: dict[str, Any] = {"ma_alignment": None, "range_position_60d": None, "rsi14": None, "volume_change": None}
    closes = _closes(price_rows)
    if len(closes) < 6:
        return None, comp

    def ma(n: int) -> float | None:
        return sum(closes[-n:]) / n if len(closes) >= n else None

    ma5, ma20, ma60 = ma(5), ma(20), ma(60)
    conds = [(ma5, ma20), (ma20, ma60)]
    got = [(a, b) for a, b in conds if a is not None and b is not None]
    if got:
        comp["ma_alignment"] = sum(1 if a > b else -1 for a, b in got) / len(got)

    window = closes[-60:] if len(closes) >= 20 else []
    if window:
        lo, hi = min(window), max(window)
        if hi > lo:
            comp["range_position_60d"] = (closes[-1] - lo) / (hi - lo) * 2 - 1

    r = rsi(closes)
    if r is not None:
        comp["rsi14"] = (r - 50.0) / 50.0
        comp["rsi14_value"] = round(r, 1)

    vols = [v for v in (_f(r_.get("turnover")) for r_ in (price_rows or [])) if v is not None and v > 0]
    if len(vols) >= 20:
        v5, v20 = sum(vols[-5:]) / 5, sum(vols[-20:]) / 20
        if v20 > 0:
            comp["volume_change"] = max(min(v5 / v20 - 1, 1.0), -1.0)

    val = _mean([comp["ma_alignment"], comp["range_position_60d"], comp["rsi14"], comp["volume_change"]])
    comp["n_signals"] = sum(1 for k in ("ma_alignment", "range_position_60d", "rsi14", "volume_change") if comp[k] is not None)
    return val, comp


def gain_60d(price_rows: list[dict] | None) -> float | None:
    """近 60 個交易日漲幅（極端走勢防呆用，見 index.html renderExtremeMoveWarning）。"""
    closes = _closes(price_rows)
    if len(closes) < 60:
        return None
    base = closes[-60]
    return (closes[-1] / base - 1) if base > 0 else None


# ─────────────────────────────── 機構行為 ───────────────────────────────
def inst_behavior(institutional: dict | None) -> tuple[float | None, dict]:
    """**不是分析師評等**（台股沒有免費目標價源），是法人實際買賣行為：
    1. 外資連續買/賣超天數（連買為正、連賣為負，除以觀察天數正規化）。
    2. 投信連續買/賣超天數（同上）。
    3. 近期淨買超趨勢：後半段平均 vs 前半段平均的方向（+1/-1/0）。
    history 只有 1 天時只有第 3 項算不出來，仍會給值（用當日方向）。
    """
    comp: dict[str, Any] = {"foreign_streak_days": None, "trust_streak_days": None,
                            "net_trend": None, "history_days": 0}
    if not institutional:
        return None, comp
    hist = [h for h in (institutional.get("history") or []) if isinstance(h, dict)]
    hist.sort(key=lambda h: str(h.get("date") or ""))
    comp["history_days"] = len(hist)
    if not hist:
        return None, comp

    def streak(field: str) -> int | None:
        vals = [_f(h.get(field)) for h in hist]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        sign = 1 if vals[-1] > 0 else (-1 if vals[-1] < 0 else 0)
        if sign == 0:
            return 0
        n = 0
        for v in reversed(vals):
            if (v > 0 and sign > 0) or (v < 0 and sign < 0):
                n += 1
            else:
                break
        return n * sign

    fs, ts = streak("foreign_lots"), streak("trust_lots")
    comp["foreign_streak_days"], comp["trust_streak_days"] = fs, ts
    days = max(len(hist), 1)
    parts = [fs / days if fs is not None else None, ts / days if ts is not None else None]

    totals = []
    for h in hist:
        vals = [_f(h.get(k)) for k in ("foreign_lots", "trust_lots", "dealer_lots")]
        vals = [v for v in vals if v is not None]
        if vals:
            totals.append(sum(vals))
    if len(totals) >= 2:
        half = len(totals) // 2
        early, late = totals[:half] or totals[:1], totals[half:]
        e, l = sum(early) / len(early), sum(late) / len(late)
        comp["net_trend"] = 1.0 if l > e else (-1.0 if l < e else 0.0)
        parts.append(comp["net_trend"])

    val = _mean([p for p in parts if p is not None])
    comp["n_signals"] = sum(1 for k in ("foreign_streak_days", "trust_streak_days", "net_trend") if comp[k] is not None)
    return val, comp


# ─────────────────────────────── 題材/事件 ───────────────────────────────
EVENT_WEIGHTS = {
    "mops_material": 1.0,       # MOPS 重大訊息
    "earnings_call": 0.8,       # 法說會
    "monthly_revenue": 0.6,     # 月營收公布
    "ex_dividend": 0.4,         # 除權息
    "news": 0.3,                # 一般新聞（RSS）
}
EVENT_HALF_LIFE_DAYS = 7.0


def event_score(events: list[dict] | None, as_of: date | None = None) -> tuple[float | None, dict]:
    """事件類型權重 × 新鮮度指數衰減（半衰期 7 天）的加總。

    `events` 是 `data/events.json` 裡屬於這檔股票的事件清單，每筆要有 `type` 與 `date`。
    沒有事件資料（檔案還沒建、或這檔近期沒事件）就回 None——**「沒有事件」跟「沒有資料源」
    在這裡分不出來，所以呼叫端要用「events.json 存不存在」來決定要不要標成缺資料源**。
    """
    comp: dict[str, Any] = {"n_events": 0, "types": {}, "latest_date": None}
    if not events:
        return None, comp
    today = as_of or datetime.now(TW_TZ).date()
    total = 0.0
    for e in events:
        t = str(e.get("type") or "news")
        w = EVENT_WEIGHTS.get(t, EVENT_WEIGHTS["news"])
        ds = str(e.get("date") or "")[:10]
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        age = (today - d).days
        if age < 0 or age > 30:
            continue
        total += w * (0.5 ** (age / EVENT_HALF_LIFE_DAYS))
        comp["n_events"] += 1
        comp["types"][t] = comp["types"].get(t, 0) + 1
        if comp["latest_date"] is None or ds > comp["latest_date"]:
            comp["latest_date"] = ds
    return (total if comp["n_events"] else None), comp

# ─────────────────────────────── 成長性（月營收12個月趨勢） ───────────────────────────────
GROWTH_MIN_PAIRS = 6  # 至少要湊出幾組「同月配對」才給值


def growth_quality(rev_rows: list[dict] | None) -> tuple[float | None, dict]:
    """近12個月營收 vs 去年同月的成長率，用**同月配對**計算。

    為什麼是配對而不是「近12個月合計 vs 前12個月合計」：實測 `revenue_history_scoring` 是
    「一次性種子快照 ＋ 每日累積」拼起來的，中間有斷層——例如 2330 有 26 個月資料，卻是
    2024-01~2024-11 加上 2025-05~2026-07，中間缺 5 個月。用視窗合計比，分子分母的月數不一樣，
    會把「缺月」誤讀成「衰退」；原本的實作要求 24 個月完全連續，2597 檔裡只有 308 檔算得出來。

    同月配對法：對近 12 個月裡的每一個月，找去年同月，兩邊都有才成對；至少 `GROWTH_MIN_PAIRS`
    對才給值。這樣不但對缺月免疫，還順便消掉月營收本來就有的季節性（台股電子業 Q4 旺季效應）。
    """
    comp: dict[str, Any] = {"pairs": 0, "recent_sum": None, "prior_sum": None, "months_used": [],
                            "method": None, "yoy_months": 0}
    rows = [r for r in (rev_rows or []) if r.get("year") and r.get("month") and _f(r.get("revenue")) is not None]
    if not rows:
        return None, comp

    # 方法一（覆蓋率高，優先）：直接用資料源逐月提供的年增率取近 12 個月平均。
    # 實測 2597 檔裡有 1650 檔的 revenue_history_scoring 帶了 13 個月以上的 yoy，
    # 但自行配對同月只有 311 檔算得出來（因為那份歷史是「舊種子快照＋最近才開始的每日累積」，
    # 中間有斷層）。逐月 yoy 是來源直接給的，不受斷層影響。
    yoy_rows = sorted([r for r in rows if _f(r.get("yoy")) is not None], key=lambda r: (r["year"], r["month"]))
    if len(yoy_rows) >= GROWTH_MIN_PAIRS:
        recent = yoy_rows[-12:]
        vals = [_cap(_f(r["yoy"])) for r in recent]
        comp["method"] = "avg_monthly_yoy"
        comp["yoy_months"] = len(vals)
        comp["months_used"] = [f"{r['year']}-{r['month']:02d}" for r in recent]
        return _cap(_mean(vals)), comp
    by_ym = {(int(r["year"]), int(r["month"])): _f(r["revenue"]) for r in rows}
    latest = max(by_ym)
    latest_idx = latest[0] * 12 + latest[1]
    recent_sum = prior_sum = 0.0
    used = []
    for back in range(12):
        idx = latest_idx - back
        y, m = divmod(idx - 1, 12)
        cur = (y, m + 1)
        prev = (y - 1, m + 1)
        a, b = by_ym.get(cur), by_ym.get(prev)
        if a is None or b is None or b <= 0:
            continue
        recent_sum += a
        prior_sum += b
        used.append(f"{cur[0]}-{cur[1]:02d}")
    comp["pairs"] = len(used)
    comp["method"] = "same_month_pairs"  # 方法二：來源沒給 yoy 時自行配對同月
    comp["months_used"] = list(reversed(used))
    if len(used) < GROWTH_MIN_PAIRS or prior_sum <= 0:
        return None, comp
    comp["recent_sum"], comp["prior_sum"] = recent_sum, prior_sum
    return _cap(recent_sum / prior_sum - 1), comp
