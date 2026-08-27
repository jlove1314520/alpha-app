"""題材動能榜（scoring-momentum-v1）：JSON-only上線評分路徑，2026-08-27新增。

**背景（使用者裁示，策略層面重要決定，逐字照抄不重新詮釋）**：
「AI供應鏈族群（光通訊/矽光子/CoWoS先進封裝/散熱/PCB/CCL/探針卡/廠務設備/
被動元件/BBU電供/AOI/低軌衛星/伺服器/導線架/連接器/矽晶圓/ASIC-IP/記憶體/
特用化學/電線電纜/BMC/機器人/石英/PMIC）幾乎不上榜。根因不是bug，是權重
設計：財報回顧類（earnings_growth 18%+revenue_momentum 18%+growth_quality
12%）=48%；valuation_adj(PEG) 12%會因為股價漲多、PE升高而扣分→反向懲罰
題材股；合計60%權重在對抗『股價領先財報』的成長題材股；唯二能捕捉這類
股票的analyst(8%)與catalyst(8%)恰好都未實作。」

**決定：拆成兩個獨立榜單，不要用單一分數通吃**——這支腳本是第二個榜單
「題材動能榜」，跟`generate_scores_live.py`（價值成長榜，完全不動）物理
分離、各自版本控管（見`score_live_momentum.py`）。輸出寫`scores_momentum.json`
（repo根目錄，跟`scores.json`分開檔案，不互相覆蓋）。

**因子設計（使用者原話逐條列出，這裡是JSON-only路徑下的具體實作）**：
- `relative_strength`（相對強度/價格動能）：近20/60日報酬率相對大盤
  （`data/market_tw.json`的taiex.sparkline/sparkline_60d），兩個窗口取平均。
- `volume_breakout`（量能突破）：今日成交值相對自身近20日均量倍數
  （`data/price_history.json`的turnover欄位）。
- `chip_concentration`（籌碼集中）：法人連續買超天數+買超張數加總
  （`data/stock_detail.json`的institutional.history，目前每日排程才剛開始
  累積，可能只有1-5天，隨時間自然加深）。**簡化揭露**：用「買超張數」而非
  使用者原話「買超佔股本比」——沒有現成的已發行股數資料源，是刻意的範圍
  縮減，不是忘記做（跟generate_scores_live.py的chips因子同一個既有簡化）。
- `group_breadth`（族群齊漲度）：同產業上漲家數比例，扣掉「漲幅集中前2檔」
  的濃縮度懲罰（用`data/company_info.json`的industry分類+
  `data/quotes_all_tw.json`的change_pct分組計算）。
- `sector_capital_flow`（產業資金流入）：產業成交值佔全市場比例的近期趨勢
  （近5日均值 vs 再前15日均值，用`data/price_history.json`90天turnover
  歷史+company_info.json的industry分組聚合算出）。
- **財報權重大幅調降，只當排除地雷用**：不計入加權總分，改成
  `financial_risk_flag`（最近財報虧損或營收年減劇烈惡化）獨立標記顯示，
  不是加分項。
- **估值不扣分**：完全不計算PE/PEG，題材股本來就貴，用PEG扣分等於自相矛盾
  （使用者原話）。

**【最重要，使用者原話，逐字照抄】**：「在回測完成前，兩個榜單頁面都要
標明：本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。」
`index.html`的題材動能榜UI必須顯示這段話（跟價值成長榜共用同一段警語）。
BACKLOG.md的B16（兩榜回測驗證）已提升為P0，回測完成、使用者同意前，
這支腳本產生的分數不得被宣稱「有效」。

**跟generate_scores_live.py共用的部分**：同一份`data/fundamentals.json`+
`data/stock_detail.json`+`data/price_history.json`+`data/company_info.json`+
`data/quotes_all_tw.json`+`data/market_tw.json`，同一套流動性門檻
（`LIQUIDITY_FLOOR_20D_VALUE`，from score_v2.py，兩榜共用同一個常數，這是
使用者原話「兩榜共用同一份資料與同一套流動性門檻」的字面實作）。因子/權重
完全獨立，不共用score_v2.FACTOR_DEFS。
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

from score_v2 import LIQUIDITY_FLOOR_20D_VALUE, _pct_score, _r
from score_live_momentum import load_frozen_weights_momentum

REPO_ROOT = Path(__file__).parent.parent
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
COMPANY_INFO_PATH = REPO_ROOT / "data" / "company_info.json"
QUOTES_ALL_TW_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"
MARKET_TW_PATH = REPO_ROOT / "data" / "market_tw.json"
OUT_PATH = REPO_ROOT / "scores_momentum.json"
TW_TZ = timezone(timedelta(hours=8))

FACTOR_LABELS = {
    "relative_strength": "相對強度/價格動能",
    "volume_breakout": "量能突破",
    "chip_concentration": "籌碼集中",
    "group_breadth": "族群齊漲度",
    "sector_capital_flow": "產業資金流入",
}
VOL_AVG_WINDOW = 20
SECTOR_FLOW_RECENT_DAYS = 5
SECTOR_FLOW_PRIOR_DAYS = 15
FINANCIAL_RISK_REVENUE_YOY_FLOOR = -0.30  # 營收年減超過這個比例才視為地雷警示
# 2026-08-27新增：company_info.json的industry分類裡，這幾種不是「個股」，是
# ETF/ETN/存託憑證/大盤指數本身等，不該混進個股動能排行榜（實測發現槓桿型
# ETF的量能/動能因子數字特別極端，會洗掉真正的個股）。
NON_STOCK_INDUSTRIES = {
    "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
    "受益證券", "存託憑證", "Index", "大盤", "所有證券",
}
# 2026-08-27新增：有些ETF代碼（例如00411A/00987D）根本不在company_info.json
# 裡（該檔案讀FinMind TaiwanStockInfo快取，可能還沒收錄這些較新上市的ETF），
# 光靠industry分類過濾不夠——台股/上櫃證券代碼慣例：0開頭(00XXX)保留給ETF/
# ETN/受益證券，不是普通股票（普通股從1開頭的4位數代碼開始），用這個代碼
# 格式當補充過濾，不用等company_info.json收錄。
_NON_STOCK_CODE_PATTERN = re.compile(r"^00\d{2,4}[A-Z]?$")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在——這支腳本只讀repo內已commit的JSON，不會自己去產生。")
    return json.loads(path.read_text(encoding="utf-8"))


def _relative_strength(price_rows: list[dict], taiex_20d: list[float], taiex_60d: list[float]) -> float | None:
    """2026-08-27修正（真bug，本機測試親自抓到：0/2374檔算出這個因子）：原本
    要求`len(taiex_20d)>=21`才計算「20日報酬率」，但`market_tw.json`的
    `taiex.sparkline`固定就是20個點（給App畫圖用的既有欄位，不為了這個因子
    改動它的長度）——用index[-1]和[-21]需要21個點，21一定大於20，這個條件
    永遠不成立，60日版本同理(要求61卻只有60個點)。改成用[-1]比[-20]/[-60]，
    即「近19/59個交易日」的報酬率，跟嚴格的「20/60個交易日」差1天，這個
    近似對動能因子的用途來說可忽略，不值得為了這1天去改動taiex.sparkline
    的既有長度定義。"""
    if len(price_rows) < 20:
        return None
    rows = sorted(price_rows, key=lambda r: r["date"])
    closes = [r["close"] for r in rows]
    parts = []
    if len(closes) >= 20 and len(taiex_20d) >= 20 and closes[-20] and taiex_20d[-20]:
        stock_ret20 = closes[-1] / closes[-20] - 1
        mkt_ret20 = taiex_20d[-1] / taiex_20d[-20] - 1
        parts.append(stock_ret20 - mkt_ret20)
    if len(closes) >= 60 and len(taiex_60d) >= 60 and closes[-60] and taiex_60d[-60]:
        stock_ret60 = closes[-1] / closes[-60] - 1
        mkt_ret60 = taiex_60d[-1] / taiex_60d[-60] - 1
        parts.append(stock_ret60 - mkt_ret60)
    if not parts:
        return None
    return sum(parts) / len(parts)


def _volume_breakout(price_rows: list[dict]) -> float | None:
    rows = [r for r in price_rows if r.get("turnover") is not None]
    if len(rows) < 6:
        return None
    rows = sorted(rows, key=lambda r: r["date"])
    today = rows[-1]["turnover"]
    window = rows[-(VOL_AVG_WINDOW + 1):-1] or rows[:-1]
    avg = sum(r["turnover"] for r in window) / len(window)
    if not avg:
        return None
    return today / avg


def _chip_concentration(institutional: dict | None) -> float | None:
    if not institutional:
        return None
    history = institutional.get("history") or [institutional]
    daily_nets = []
    for day in history:
        vals = [day.get(k) for k in ("foreign_lots", "trust_lots", "dealer_lots")]
        vals = [v for v in vals if v is not None]
        if vals:
            daily_nets.append(sum(vals))
    if not daily_nets:
        return None
    streak = 0
    for net in reversed(daily_nets):
        if net > 0:
            streak += 1
        else:
            break
    streak_ratio = streak / len(daily_nets)
    total_net = sum(daily_nets)
    return total_net * (1 + streak_ratio)


def _financial_risk_flag(fin_quarters: list[dict], rev_rows: list[dict]) -> bool:
    if fin_quarters:
        recent = sorted(fin_quarters, key=lambda q: (q["year"], q["quarter"]))[-2:]
        if recent and all((q.get("net_income_parent") or 0) < 0 for q in recent):
            return True
    if rev_rows:
        latest = max(rev_rows, key=lambda r: (r["year"], r["month"]))
        if latest.get("yoy") is not None and latest["yoy"] < FINANCIAL_RISK_REVENUE_YOY_FLOOR:
            return True
    return False


def build_sector_aggregates(price_history: dict, industry_map: dict[str, str]) -> pd.DataFrame:
    """回傳 index=date, columns=industry 的每日產業成交值加總表，供
    sector_capital_flow跟group_breadth共用（後者其實用quotes_all_tw.json的
    當日change_pct，不是這張表，但兩者都需要「這檔股票屬於哪個產業」的
    join，寫在同一個函式方便理解資料流）。"""
    rows = []
    for code, price_rows in price_history.items():
        industry = industry_map.get(code)
        if not industry:
            continue
        for r in price_rows:
            if r.get("turnover") is not None:
                rows.append({"date": r["date"], "industry": industry, "turnover": r["turnover"]})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.groupby(["date", "industry"])["turnover"].sum().unstack(fill_value=0.0)


def compute_sector_flow_trend(sector_daily: pd.DataFrame) -> dict[str, float]:
    """每個產業：近5日均turnover佔全市場比例 vs 再前15日均比例，差值當
    「資金流入趨勢」（正值＝佔比正在提高）。要求至少20天資料才計算，不足
    誠實跳過（回傳的dict不會有該產業的key，呼叫端對應到None）。"""
    if sector_daily.empty or len(sector_daily) < SECTOR_FLOW_RECENT_DAYS + SECTOR_FLOW_PRIOR_DAYS:
        return {}
    market_total = sector_daily.sum(axis=1)
    share = sector_daily.div(market_total.replace(0, np.nan), axis=0)
    recent_avg = share.tail(SECTOR_FLOW_RECENT_DAYS).mean()
    prior = share.iloc[-(SECTOR_FLOW_RECENT_DAYS + SECTOR_FLOW_PRIOR_DAYS):-SECTOR_FLOW_RECENT_DAYS]
    prior_avg = prior.mean()
    trend = (recent_avg - prior_avg).dropna()
    return trend.to_dict()


def compute_group_breadth(quotes_all: dict, industry_map: dict[str, str]) -> dict[str, float]:
    """同產業上漲家數比例，扣掉「漲幅集中前2檔」的濃縮度懲罰。回傳
    {industry: breadth_score}，呼叫端對應各股所屬產業。"""
    by_industry: dict[str, list[float]] = {}
    for code, q in quotes_all.items():
        industry = industry_map.get(code)
        pct = q.get("change_pct")
        if industry and pct is not None:
            by_industry.setdefault(industry, []).append(pct)
    out = {}
    for industry, pcts in by_industry.items():
        if len(pcts) < 3:
            continue
        pct_positive = sum(1 for p in pcts if p > 0) / len(pcts)
        positive_gains = sorted((p for p in pcts if p > 0), reverse=True)
        total_gain = sum(positive_gains)
        top2_gain = sum(positive_gains[:2])
        concentration = (top2_gain / total_gain) if total_gain > 0 else 0.0
        concentration_penalty = max(0.0, concentration - 0.5)  # 前2檔吃掉超過一半漲幅才罰
        out[industry] = pct_positive * (1 - concentration_penalty)
    return out


def build_rows() -> pd.DataFrame:
    fundamentals = _load_json(FUNDAMENTALS_PATH).get("fundamentals", {})
    stock_detail = _load_json(STOCK_DETAIL_PATH).get("stocks", {})
    price_history = _load_json(PRICE_HISTORY_PATH).get("prices", {}) if PRICE_HISTORY_PATH.exists() else {}
    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    quotes_all = _load_json(QUOTES_ALL_TW_PATH).get("quotes", {}) if QUOTES_ALL_TW_PATH.exists() else {}
    market_tw = _load_json(MARKET_TW_PATH) if MARKET_TW_PATH.exists() else {}
    taiex_20d = (market_tw.get("taiex") or {}).get("sparkline") or []
    taiex_60d = (market_tw.get("taiex") or {}).get("sparkline_60d") or []

    industry_map = {code: v.get("industry") for code, v in company_info.items() if v.get("industry")}
    sector_daily = build_sector_aggregates(price_history, industry_map)
    sector_flow_trend = compute_sector_flow_trend(sector_daily)
    group_breadth_by_industry = compute_group_breadth(quotes_all, industry_map)

    # 2026-08-27修正（真bug，本機測試才發現）：一開始沒過濾ETF，導致排行榜前段
    # 幾乎全是ETF代碼（例如00400A「主動國泰動能高息」）——這是題材動能榜「量能
    # 突破」/「相對強度」這類價格類因子對ETF特別友善（槓桿型ETF尤其容易有極端
    # 動能數字，不是真的個股題材強度），不是我們要的東西。用company_info.json
    # 的industry分類過濾掉非個股證券（同一份清單也適用generate_scores_live.py，
    # 那邊也有這個bug，一併修正）。
    candidate_codes = set(fundamentals) | set(stock_detail) | set(price_history)
    non_stock_codes = {code for code, ind in industry_map.items() if ind in NON_STOCK_INDUSTRIES}
    non_stock_codes |= {code for code in candidate_codes if _NON_STOCK_CODE_PATTERN.match(code)}
    all_codes = sorted(candidate_codes - non_stock_codes)
    rows = []
    for code in all_codes:
        sd = stock_detail.get(code, {})
        fd = fundamentals.get(code, {})
        price_rows = price_history.get(code) or []
        industry = industry_map.get(code)

        rel_strength = _relative_strength(price_rows, taiex_20d, taiex_60d)
        vol_breakout = _volume_breakout(price_rows)
        chip_conc = _chip_concentration(sd.get("institutional"))
        group_breadth = group_breadth_by_industry.get(industry) if industry else None
        sector_flow = sector_flow_trend.get(industry) if industry else None
        liquidity_20d = None
        turnover_rows = [r for r in price_rows if r.get("turnover") is not None]
        if turnover_rows:
            recent = sorted(turnover_rows, key=lambda r: r["date"])[-20:]
            liquidity_20d = sum(r["turnover"] for r in recent) / len(recent)
        financial_risk = _financial_risk_flag(
            (sd.get("financials") or {}).get("quarters") or [],
            fd.get("revenue_history_scoring") or fd.get("month_revenue") or [],
        )

        rows.append({
            "stock_id": code,
            "raw_relative_strength": rel_strength,
            "raw_volume_breakout": vol_breakout,
            "raw_chip_concentration": chip_conc,
            "raw_group_breadth": group_breadth,
            "raw_sector_capital_flow": sector_flow,
            "liquidity_20d": liquidity_20d,
            "financial_risk_flag": financial_risk,
        })

    return pd.DataFrame(rows).set_index("stock_id")


def compute_scores_momentum(weights: dict[str, float]) -> pd.DataFrame:
    cs = build_rows()
    if cs.empty:
        return cs

    raw_col = {
        "relative_strength": "raw_relative_strength",
        "volume_breakout": "raw_volume_breakout",
        "chip_concentration": "raw_chip_concentration",
        "group_breadth": "raw_group_breadth",
        "sector_capital_flow": "raw_sector_capital_flow",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], higher_better=True)  # 五項全部「越高越好」，估值不扣分故不需方向反轉
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct

    totals, covs = [], []
    for _, row in cs.iterrows():
        num, den = 0.0, 0.0
        for key, w in weights.items():
            sc = row.get(f"{key}_score")
            if pd.notna(sc):
                num += sc * w
                den += w
        if den == 0:
            totals.append(np.nan)
            covs.append(0.0)
        else:
            totals.append(round(num / den, 1))
            covs.append(round(den, 2))
    cs["total_score"] = totals
    cs["coverage"] = covs
    cs = cs.dropna(subset=["total_score"]).copy()
    return cs


def _raw_dict(key: str, row: pd.Series) -> dict:
    col_map = {
        "relative_strength": "raw_relative_strength",
        "volume_breakout": "raw_volume_breakout",
        "chip_concentration": "raw_chip_concentration",
        "group_breadth": "raw_group_breadth",
        "sector_capital_flow": "raw_sector_capital_flow",
    }
    return {"value": _r(row.get(col_map[key]))}


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = max(1, round((1 - pct) * 100)) if pd.notna(pct) else None
    v = row.get(f"raw_{key}")
    if key == "relative_strength":
        return f"近20/60日報酬率相對大盤 {v*100:+.1f}%（平均），居全市場前 {front}%。"
    if key == "volume_breakout":
        return f"今日成交值為近20日均量的 {v:.2f} 倍，居全市場前 {front}%。"
    if key == "chip_concentration":
        return f"三大法人買超張數×連續買超天數加成指標 {v:+.0f}，居全市場前 {front}%。"
    if key == "group_breadth":
        return f"同產業上漲家數比例（已扣除前2檔濃縮度懲罰）{v*100:.0f}%，居全市場前 {front}%。"
    if key == "sector_capital_flow":
        return f"所屬產業近5日成交值佔全市場比例，較再前15日提升 {v*100:+.2f} 個百分點，居全市場前 {front}%。"
    return ""


def main():
    frozen = load_frozen_weights_momentum()
    weights = frozen["weights"]
    print(f"已套用題材動能榜初始設計權重 weights_frozen_momentum.json"
          f"（frozen_at={frozen['frozen_at']}，sha256={frozen['weights_sha256'][:12]}...，"
          f"**尚未回測驗證**）")

    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    cs = compute_scores_momentum(weights)
    as_of = datetime.now(TW_TZ).strftime("%Y-%m-%d")

    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-momentum-v1", "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW", "weights_hash": frozen["weights_sha256"],
                "backtest_status": "尚未回測驗證",
                "disclaimer": "本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。這次沒有任何股票算出分數。",
            },
            "weights": weights, "stocks": [],
        }
    else:
        cs["liquidity_insufficient"] = (
            cs["liquidity_20d"].isna() | (cs["liquidity_20d"] < LIQUIDITY_FLOOR_20D_VALUE)
        )
        ranked = cs.sort_values(["liquidity_insufficient", "total_score"], ascending=[True, False]).copy()
        liquidity_ok_mask = ~ranked["liquidity_insufficient"]
        ranked.loc[liquidity_ok_mask, "display_rank"] = range(1, int(liquidity_ok_mask.sum()) + 1)

        stocks = []
        for sid, row in ranked.iterrows():
            present = [k for k in FACTOR_LABELS if pd.notna(row.get(f"{k}_score"))]
            missing = [k for k in FACTOR_LABELS if k not in present]
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
            if row.get("financial_risk_flag"):
                flags.append("財報地雷警示（近期虧損或營收年減劇烈惡化）")
            display_rank = row.get("display_rank")
            info = company_info.get(sid) or {}
            stocks.append({
                "code": sid, "name": info.get("name"), "industry": info.get("industry"),
                "rank": int(display_rank) if pd.notna(display_rank) else None,
                "total_score": round(float(row["total_score"]), 1),
                "coverage": round(float(row["coverage"]), 2),
                "missing_factors": missing,
                "liquidity_20d": _r(row.get("liquidity_20d")),
                "data_asof": as_of,
                "factors": factors_obj,
                "flags": flags,
                "news_warning": None,
            })
        payload = {
            "meta": {
                "engine_version": "scoring-momentum-v1",
                "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW",
                "universe_size": len(cs),
                "avg_coverage": round(float(cs["coverage"].mean()), 3),
                "liquidity_floor_20d_value": LIQUIDITY_FLOOR_20D_VALUE,
                "weights_hash": frozen["weights_sha256"],
                "backtest_status": "尚未回測驗證",
                "source": "只讀repo內data/fundamentals.json+data/stock_detail.json+data/price_history.json"
                           "+data/company_info.json+data/quotes_all_tw.json+data/market_tw.json"
                           "（不讀parquet、不呼叫FinMind），供GitHub Actions每日排程使用。",
                "disclaimer": (
                    "⚠ 本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。"
                    "因子設計聚焦股價領先財報的題材動能（相對強度/量能突破/籌碼集中/"
                    "族群齊漲度/產業資金流入），財報只當地雷排除用（financial_risk_flag），"
                    "不計入加權總分；完全不計算PE/PEG估值，題材股本來就貴，用估值扣分"
                    "等於自相矛盾。權重是初始設計值，不是回測最佳化結果，見"
                    "weights_frozen_momentum.json的note欄位。"
                ),
            },
            "weights": weights,
            "stocks": stocks,
        }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=float), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(payload['stocks'])} 檔（樣本共 {len(cs)} 檔有任一因子資料）")
    if not cs.empty:
        print(cs[["total_score", "coverage"]].head(10).to_string())


if __name__ == "__main__":
    main()
