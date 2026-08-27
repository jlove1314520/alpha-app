"""未來性濾網（scoring-future-v1）：JSON-only上線評分路徑，2026-08-27新增。

**背景（使用者裁示，第三個獨立濾網，逐字照抄不重新詮釋）**：「濾網架構：
三個獨立引擎，不要用單一分數通吃。1.價值濾網（現行引擎）2.題材動能濾網
（上一輪已規格化）3.未來性濾網（新增，因子分三類，取得難度不同，分階段
做）：(a)現在就能算 (b)需事件資料（等新聞管線）(c)質性研判（AI閱讀後給
結論）。」這支腳本是(a)類的實作，(b)/(c)見`BACKLOG.md`的B18/B20。

**(a)類因子（使用者原話逐條列出，這裡是JSON-only路徑下的具體實作）**：
- `institutional_buying_streak`（法人連續買超天數）：
  `data/stock_detail.json`的institutional.history。
- `institutional_ownership_pct`（買超佔股本比）：買超張數加總 ÷
  股本反推的約略在外流通股數（`data/stock_detail.json`的
  `financials.shares_outstanding_approx`，2026-08-27新增，見
  `.github/scripts/update_stock_financials.py`：股本(仟元)÷10股面額=約略
  在外流通張數，因為台股普通股面額統一為每股10元）。
- `institutional_buying_concentration`（買超集中度）：外資佔三大法人買超
  總量的比例（只在買超總量為正時才有意義，這是刻意的簡化——「集中度」
  可以有很多種定義，這裡選「外資主導程度」，理由是外資在台股常被視為
  較有國際視野的資金，不是唯一合理的定義）。
- `gross_margin_level_stability`（毛利率水準與穩定度，供應鏈議價力代理）：
  `data/stock_detail.json`的financials.quarters（近8季，2026-08-27已回補
  歷史），取平均水準+穩定度（標準差的倒數，波動小=穩定）綜合。
- `capacity_utilization_proxy`（產能利用率代理：營收/固定資產比）：
  **簡化揭露**——原本使用者要的是「趨勢」，但
  `.github/scripts/update_stock_financials.py`目前只保留最新一筆
  `financials.non_current_assets_latest`（沒有retained歷史序列），這裡
  改成算「目前水準」（近4季營收合計÷最新一期非流動資產），不是趨勢；
  且「非流動資產」不是精確的「固定資產」（還包含商譽/長期投資等），是
  TWSE官方資產負債表(t187ap07_L_ci)沒有單獨固定資產欄位下的近似代理。
- **`customer_concentration`（營收客戶集中度）：這一版未實作**——沒有
  現成的免費資料源（需要財報附註揭露的前五大客戶占比，公開資料沒有
  結構化格式可抓），不是忘記做，見`BACKLOG.md`已知限制。

**(b)/(c)類因子見BACKLOG.md的B18（事件資料，需先完成新聞/訊號管線）跟
B20（AI質性研判，使用者規則：不計入量化總分，另闢區塊呈現，本腳本不觸碰）**。

**跟另外兩個濾網共用的部分**：同一份`data/stock_detail.json`（含新增的
`shares_outstanding_approx`/`non_current_assets_latest`欄位），同一套
流動性門檻（`LIQUIDITY_FLOOR_20D_VALUE`，from score_v2.py）+ 同一套ETF
過濾（`NON_STOCK_INDUSTRIES`/代碼格式，跟另外兩支腳本各自獨立複製）。
因子/權重完全獨立，見`score_live_future.py`。
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
from score_live_future import load_frozen_weights_future

REPO_ROOT = Path(__file__).parent.parent
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
COMPANY_INFO_PATH = REPO_ROOT / "data" / "company_info.json"
OUT_PATH = REPO_ROOT / "scores_future.json"
TW_TZ = timezone(timedelta(hours=8))

FACTOR_LABELS = {
    "institutional_buying_streak": "法人連續買超天數",
    "institutional_ownership_pct": "買超佔股本比",
    "institutional_buying_concentration": "買超集中度（外資主導程度）",
    "gross_margin_level_stability": "毛利率水準與穩定度",
    "capacity_utilization_proxy": "產能利用率代理",
}
NON_STOCK_INDUSTRIES = {
    "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
    "受益證券", "存託憑證", "Index", "大盤", "所有證券",
}
_NON_STOCK_CODE_PATTERN = re.compile(r"^00\d{2,4}[A-Z]?$")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在——這支腳本只讀repo內已commit的JSON，不會自己去產生。")
    return json.loads(path.read_text(encoding="utf-8"))


def _daily_nets(institutional: dict | None) -> list[float]:
    if not institutional:
        return []
    history = institutional.get("history") or [institutional]
    out = []
    for day in history:
        vals = [day.get(k) for k in ("foreign_lots", "trust_lots", "dealer_lots")]
        vals = [v for v in vals if v is not None]
        if vals:
            out.append(sum(vals))
    return out


def _institutional_buying_streak(institutional: dict | None) -> float | None:
    nets = _daily_nets(institutional)
    if not nets:
        return None
    streak = 0
    for net in reversed(nets):
        if net > 0:
            streak += 1
        else:
            break
    return streak / len(nets)  # 0~1，1代表可觀察到的天數裡全部都在買超


def _institutional_ownership_pct(institutional: dict | None, shares_outstanding: float | None) -> float | None:
    nets = _daily_nets(institutional)
    if not nets or not shares_outstanding:
        return None
    total_net = sum(nets)
    return total_net / shares_outstanding  # 兩者都是「張/仟股」單位，見檔頭說明，不需要再轉換


def _institutional_buying_concentration(institutional: dict | None) -> float | None:
    if not institutional:
        return None
    history = institutional.get("history") or [institutional]
    foreign_sum = sum(d.get("foreign_lots") or 0 for d in history)
    total_sum = sum((d.get("foreign_lots") or 0) + (d.get("trust_lots") or 0) + (d.get("dealer_lots") or 0) for d in history)
    if total_sum <= 0:
        return None  # 只在買超總量為正時才有意義，見檔頭說明
    return foreign_sum / total_sum


def _gross_margin_level_stability(quarters: list[dict]) -> float | None:
    margins = [q.get("gross_margin_pct") for q in quarters if q.get("gross_margin_pct") is not None]
    if len(margins) < 3:
        return None
    level = float(np.mean(margins))
    std = float(np.std(margins))
    stability = 1 / (1 + std)  # std越小，穩定度越接近1；std越大，穩定度趨近0
    return level * stability  # 水準×穩定度的綜合指標，水準高但波動大會被打折


def _capacity_utilization_proxy(quarters: list[dict], non_current_assets: float | None) -> float | None:
    if not non_current_assets or non_current_assets <= 0:
        return None
    recent = [q for q in quarters if q.get("revenue") is not None]
    recent = sorted(recent, key=lambda q: (q["year"], q["quarter"]))[-4:]
    if len(recent) < 4:
        return None
    ttm_revenue = sum(q["revenue"] for q in recent)
    return ttm_revenue / non_current_assets


def build_rows() -> pd.DataFrame:
    stock_detail = _load_json(STOCK_DETAIL_PATH).get("stocks", {})
    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    price_history = _load_json(PRICE_HISTORY_PATH).get("prices", {}) if PRICE_HISTORY_PATH.exists() else {}

    non_stock_codes = {code for code, v in company_info.items() if v.get("industry") in NON_STOCK_INDUSTRIES}
    non_stock_codes |= {code for code in stock_detail if _NON_STOCK_CODE_PATTERN.match(code)}
    all_codes = sorted(set(stock_detail) - non_stock_codes)

    rows = []
    for code in all_codes:
        sd = stock_detail.get(code, {})
        fin = sd.get("financials") or {}
        quarters = fin.get("quarters") or []
        institutional = sd.get("institutional")

        streak = _institutional_buying_streak(institutional)
        ownership_pct = _institutional_ownership_pct(institutional, fin.get("shares_outstanding_approx"))
        concentration = _institutional_buying_concentration(institutional)
        margin_stability = _gross_margin_level_stability(quarters)
        capacity = _capacity_utilization_proxy(quarters, fin.get("non_current_assets_latest"))

        price_rows = [r for r in (price_history.get(code) or []) if r.get("turnover") is not None]
        liquidity_20d = None
        if price_rows:
            recent = sorted(price_rows, key=lambda r: r["date"])[-20:]
            liquidity_20d = sum(r["turnover"] for r in recent) / len(recent)

        rows.append({
            "stock_id": code,
            "raw_institutional_buying_streak": streak,
            "raw_institutional_ownership_pct": ownership_pct,
            "raw_institutional_buying_concentration": concentration,
            "raw_gross_margin_level_stability": margin_stability,
            "raw_capacity_utilization_proxy": capacity,
            "liquidity_20d": liquidity_20d,
        })

    return pd.DataFrame(rows).set_index("stock_id")


def compute_scores_future(weights: dict[str, float]) -> pd.DataFrame:
    cs = build_rows()
    if cs.empty:
        return cs
    raw_col = {
        "institutional_buying_streak": "raw_institutional_buying_streak",
        "institutional_ownership_pct": "raw_institutional_ownership_pct",
        "institutional_buying_concentration": "raw_institutional_buying_concentration",
        "gross_margin_level_stability": "raw_gross_margin_level_stability",
        "capacity_utilization_proxy": "raw_capacity_utilization_proxy",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], higher_better=True)
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
        "institutional_buying_streak": "raw_institutional_buying_streak",
        "institutional_ownership_pct": "raw_institutional_ownership_pct",
        "institutional_buying_concentration": "raw_institutional_buying_concentration",
        "gross_margin_level_stability": "raw_gross_margin_level_stability",
        "capacity_utilization_proxy": "raw_capacity_utilization_proxy",
    }
    return {"value": _r(row.get(col_map[key]))}


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = max(1, round((1 - pct) * 100)) if pd.notna(pct) else None
    v = row.get(f"raw_{key}")
    if key == "institutional_buying_streak":
        return f"可觀察天數中有 {v*100:.0f}% 是連續買超，居全市場前 {front}%。"
    if key == "institutional_ownership_pct":
        return f"三大法人買超累積張數約當股本的 {v*100:+.3f}%，居全市場前 {front}%。"
    if key == "institutional_buying_concentration":
        return f"外資佔三大法人買超總量的 {v*100:.0f}%，居全市場前 {front}%。"
    if key == "gross_margin_level_stability":
        return f"近8季毛利率水準×穩定度綜合指標 {v:.1f}，居全市場前 {front}%（供應鏈議價力代理，非嚴謹驗證）。"
    if key == "capacity_utilization_proxy":
        return f"近4季營收合計/最新一期非流動資產比值 {v:.2f}，居全市場前 {front}%（產能利用率代理，非精確固定資產週轉率）。"
    return ""


def main():
    frozen = load_frozen_weights_future()
    weights = frozen["weights"]
    print(f"已套用未來性濾網初始設計權重 weights_frozen_future.json"
          f"（frozen_at={frozen['frozen_at']}，sha256={frozen['weights_sha256'][:12]}...，"
          f"**尚未回測驗證**）")

    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    cs = compute_scores_future(weights)
    as_of = datetime.now(TW_TZ).strftime("%Y-%m-%d")

    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-future-v1", "generated_at": datetime.now(TW_TZ).isoformat(),
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
                "qualitative_notes": None,  # (c)類AI質性研判區塊預留欄位，見BACKLOG.md B20，這輪未實作
                "news_warning": None,
            })
        payload = {
            "meta": {
                "engine_version": "scoring-future-v1",
                "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW",
                "universe_size": len(cs),
                "avg_coverage": round(float(cs["coverage"].mean()), 3),
                "liquidity_floor_20d_value": LIQUIDITY_FLOOR_20D_VALUE,
                "weights_hash": frozen["weights_sha256"],
                "backtest_status": "尚未回測驗證",
                "source": "只讀repo內data/stock_detail.json+data/company_info.json+data/price_history.json"
                           "（不讀parquet、不呼叫FinMind），供GitHub Actions每日排程使用。",
                "disclaimer": (
                    "⚠ 本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。"
                    "這是「未來性濾網」(a)類因子（現在就能算的部分：法人籌碼行為+"
                    "毛利率品質+產能利用率代理），(b)類（事件資料）/(c)類（AI質性"
                    "研判）尚未實作，見BACKLOG.md B18/B20。customer_concentration"
                    "（營收客戶集中度）無現成資料源，這一版未實作。權重是初始設計值，"
                    "不是回測最佳化結果，見weights_frozen_future.json的note欄位。"
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
