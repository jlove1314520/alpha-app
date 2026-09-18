"""隱含市值重建法驗證（`CORE_TILT_SPEC.md` 第2.1節，2026-09-18 Cowork
【裁示】「市值重建：驗證要重做，台積電是最不該當唯一樣本的那一檔」）。

**背景**：v2 SPEC 用單一個股（台積電）驗證
`implied_market_cap = PBR × EquityAttributableToOwnersOfParent`
（下稱路徑1），總司令指出「單檔4.5%不是重點，誤差的結構才是」——
若誤差跟市值或產業相關，會直接系統性污染 core_tilt 的市值加權基底與
0050 產業中性約束，不是隨機雜訊那麼溫和。

**本輪新增第二條獨立重建路徑**（`.github/scripts/update_stock_financials.py`
::fetch_balance() 已經在算 `common_stock_capital`/10 = shares_outstanding_
approx，本檔案沿用同一個推導但額外處理金融業）：

    路徑2：market_cap ≈ close_price × (實收資本額 ÷ 10)
    （台股普通股面額絕大多數為每股新台幣10元）

兩條路徑資料來源完全獨立：
- 路徑1：FinMind `TaiwanStockPER`（PBR）+ FinMind `TaiwanStockBalanceSheet`
  （`EquityAttributableToOwnersOfParent`）
- 路徑2：既有 `adjusted_price_series()`（收盤價）+ TWSE openapi
  `t187ap07_L_ci`（一般業資產負債表-股本）或 `t187ap07_L_fh`（金融業
  資產負債表-股本，一般業端點不含金控/銀行/證券/保險，見下方
  `FIN_HOLDING_IDS`）

**驗證樣本設計**（依總司令裁示，不是自己方便選的）：
1. 強制納入結構複雜的個股：金控（2882/2881）、控股與多子公司（2317，
   非控制權益占比高）、KY股（5871）；特別股另外處理（見下方，PBR
   結構上不存在，不能跟普通股用同一張表比較）。
2. 其餘用路徑2市值分大/中/小三個級距各抽10檔（路徑2作為分級依據，
   避免用路徑1的結果去分級路徑1自己的誤差，那是循環論證）。

執行：python research/implied_market_cap_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import requests

from adjust import adjusted_price_series
from finmind_client import load_dev
from pit import balance_sheet_pit
from score import load_industry_map
from universe import active_stock_ids

OUT_JSON = Path(__file__).parent / "data" / "implied_market_cap_validation.json"

# 2026-09-18查證發現：`.github/scripts/update_stock_financials.py`用的
# TWSE openapi `t187ap07_L_ci`（一般業資產負債表）金控/銀行/證券/保險
# 一律缺值（None）——這幾類公司依規定用「金融業」格式的財報，走另一個
# 端點`t187ap07_L_fh`。這裡列出的是本次驗證樣本裡屬於這一類、需要走
# `t187ap07_L_fh`才拿得到股本的代號（不是全市場金融股清單，只是本次
# 驗證樣本涵蓋到的）。
FIN_HOLDING_IDS = {"2882", "2881", "2891", "2887", "2888", "2886", "2880", "2884", "2885", "2889", "2890", "2892"}

TWSE_BALANCE_GENERAL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
TWSE_BALANCE_FINANCIAL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_fh"

FORCED_STOCKS = {
    "2882": "金控（國泰金）",
    "2881": "金控（富邦金）",
    "2317": "控股與多子公司（鴻海，非控制權益占比高）",
    "5871": "KY股（中租-KY）",
}
PREFERRED_STOCK_CANDIDATES = ["2891A", "2883A", "2888A", "9941A", "6592A"]  # 特別股，見下方單獨處理


def _twse_balance_map(url: str) -> dict[str, dict]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    rows = r.json()
    out = {}
    for row in rows:
        code = row.get("公司代號")
        if not code:
            continue
        out[code] = {
            "common_stock_capital": row.get("股本"),
            "equity_attributable_parent": row.get("歸屬於母公司業主之權益"),
            "equity_total": row.get("權益總額") or row.get("權益總計"),
            "noncontrolling": row.get("非控制權益"),
        }
    return out


def _num(x):
    try:
        if x in (None, ""):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def path2_market_cap(stock_id: str, twse_general: dict, twse_financial: dict) -> dict:
    """路徑2：price × (股本/10)。金控/銀行/證券/保險走financial端點。"""
    src = twse_financial if stock_id in FIN_HOLDING_IDS else twse_general
    row = src.get(stock_id)
    if row is None:
        # 一般業查不到就試金融業，反之亦然——不假設分類永遠正確，實際查得到就用
        row = twse_financial.get(stock_id) or twse_general.get(stock_id)
    if row is None:
        return {"ok": False, "reason": "TWSE股本查無此代號（一般業+金融業兩端點都沒有）"}
    capital = _num(row.get("common_stock_capital"))
    if capital is None or capital <= 0:
        return {"ok": False, "reason": "TWSE股本欄位缺值"}
    shares_thousand = capital / 10.0  # 股本(千元) / 面額10元 = 股數(千股)
    try:
        px = adjusted_price_series(stock_id)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"價格抓取失敗: {e}"}
    if px.empty:
        return {"ok": False, "reason": "無價格資料"}
    last_row = px.sort_values("date").iloc[-1]
    price = float(last_row["close"])
    date = str(last_row["date"])[:10]
    market_cap_thousand = price * shares_thousand  # 單位：千元（跟股本同一個單位量級）
    return {
        "ok": True, "price": price, "date": date, "shares_thousand": shares_thousand,
        "market_cap_thousand": market_cap_thousand,
        "equity_attributable_parent": _num(row.get("equity_attributable_parent")),
        "equity_total": _num(row.get("equity_total")),
        "noncontrolling": _num(row.get("noncontrolling")),
    }


def path1_market_cap(stock_id: str, as_of_date: str) -> dict:
    """路徑1：PBR × EquityAttributableToOwnersOfParent（FinMind）。
    金控類 `EquityAttributableToOwnersOfParent` 常缺值，缺值時退而用
    `Equity`（總權益，含非控制權益）並標記`used_total_equity=True`——
    這正是總司令要查的候選(b)，缺值時退回哪個欄位要誠實記錄，不能
    悄悄選一個能算出數字的欄位就當作跟其他股票同一個定義。"""
    per = load_dev("TaiwanStockPER", stock_id, "2000-01-01")
    if per.empty:
        return {"ok": False, "reason": "無PBR資料（常見於特別股，PBR/PER結構上不適用）"}
    per["date"] = pd.to_datetime(per["date"])
    asof = pd.Timestamp(as_of_date)
    avail = per[per["date"] <= asof]
    if avail.empty:
        avail = per  # 找不到剛好<=asof的就退回用最新一筆，僅供粗略比對
    row = avail.sort_values("date").iloc[-1]
    pbr = _num(row.get("PBR"))
    pbr_date = str(row["date"])[:10]
    if pbr is None or pbr <= 0:
        return {"ok": False, "reason": "PBR欄位缺值或為0"}
    bs = balance_sheet_pit(stock_id)
    if bs.empty:
        return {"ok": False, "reason": "無資產負債表資料"}
    bs_avail = bs[pd.to_datetime(bs["pit_date"]) <= asof]
    if bs_avail.empty:
        return {"ok": False, "reason": "asof日期之前無可得的資產負債表(PIT)"}
    bs_row = bs_avail.sort_values("pit_date").iloc[-1]
    eq_parent = _num(bs_row.get("EquityAttributableToOwnersOfParent"))
    eq_total = _num(bs_row.get("Equity"))
    used_total = False
    equity_used = eq_parent
    if equity_used is None:
        equity_used = eq_total
        used_total = True
    if equity_used is None:
        return {"ok": False, "reason": "EquityAttributableToOwnersOfParent與Equity皆缺值"}
    return {
        "ok": True, "pbr": pbr, "pbr_date": pbr_date,
        "bs_pit_date": str(bs_row["pit_date"])[:10],
        "equity_used": equity_used, "used_total_equity": used_total,
        "eq_parent": eq_parent, "eq_total": eq_total,
        "market_cap": pbr * equity_used,
    }


def build_sample() -> list[str]:
    """依裁示挑樣本：強制納入清單 + 路徑2市值分大/中/小三級距各10檔。"""
    active = active_stock_ids()
    normal = active[active["stock_id"].str.match(r"^\d{4}$")]
    twse_general = _twse_balance_map(TWSE_BALANCE_GENERAL)
    twse_financial = _twse_balance_map(TWSE_BALANCE_FINANCIAL)

    candidates = []
    for sid in normal["stock_id"]:
        if sid in FORCED_STOCKS:
            continue
        row = twse_general.get(sid) or twse_financial.get(sid)
        if row is None:
            continue
        cap = _num(row.get("common_stock_capital"))
        if cap and cap > 0:
            candidates.append(sid)

    print(f"路徑2股本資料可用的候選池：{len(candidates)}檔（排除強制清單後）")

    # 用「股本」本身（不含股價）先粗篩，避免對每一檔都抓價格序列太慢——
    # 股本大小本身就是市值級距的合理代理，抓到候選後才對這90檔精算真正
    # 用股本x最新價的路徑2市值做最終分級。
    cap_series = pd.Series(
        {sid: _num((twse_general.get(sid) or twse_financial.get(sid))["common_stock_capital"]) for sid in candidates}
    ).dropna().sort_values()
    n = len(cap_series)
    small_pool = cap_series.iloc[: n // 3].index.tolist()
    mid_pool = cap_series.iloc[n // 3 : 2 * n // 3].index.tolist()
    large_pool = cap_series.iloc[2 * n // 3 :].index.tolist()

    rng = np.random.default_rng(42)
    picked = []
    for pool in (large_pool, mid_pool, small_pool):
        picked.extend(rng.choice(pool, size=min(10, len(pool)), replace=False).tolist())

    sample = list(FORCED_STOCKS.keys()) + picked
    return sample, twse_general, twse_financial


def main() -> None:
    sample, twse_general, twse_financial = build_sample()
    industry_map = load_industry_map()

    rows = []
    for sid in sample:
        p2 = path2_market_cap(sid, twse_general, twse_financial)
        if not p2.get("ok"):
            rows.append({"stock_id": sid, "ok": False, "stage": "path2", "reason": p2.get("reason"),
                         "forced_reason": FORCED_STOCKS.get(sid)})
            continue
        p1 = path1_market_cap(sid, p2["date"])
        if not p1.get("ok"):
            rows.append({"stock_id": sid, "ok": False, "stage": "path1", "reason": p1.get("reason"),
                         "forced_reason": FORCED_STOCKS.get(sid), "path2_market_cap_thousand": p2["market_cap_thousand"]})
            continue
        # 路徑1的market_cap單位是FinMind Equity的原始單位（近似「元」，見SPEC第2.1節台積電驗證），
        # 路徑2的market_cap_thousand單位是「千元」——先統一成同一單位（都換算成「元」）再比較。
        mc1_yuan = p1["market_cap"]
        mc2_yuan = p2["market_cap_thousand"] * 1000.0
        rel_error = (mc1_yuan - mc2_yuan) / ((mc1_yuan + mc2_yuan) / 2.0)
        rows.append({
            "stock_id": sid, "ok": True,
            "forced_reason": FORCED_STOCKS.get(sid),
            "industry": industry_map.get(sid, "unknown"),
            "as_of_date": p2["date"],
            "path1_market_cap_yuan": mc1_yuan, "path2_market_cap_yuan": mc2_yuan,
            "rel_error_pct": round(rel_error * 100, 2),
            "path1_used_total_equity": p1["used_total_equity"],
            "path1_pbr": p1["pbr"], "path1_pbr_date": p1["pbr_date"], "path1_bs_pit_date": p1["bs_pit_date"],
            "path2_noncontrolling_yuan": (p2.get("noncontrolling") or 0) * 1000.0 if p2.get("noncontrolling") else None,
        })

    ok_rows = [r for r in rows if r["ok"]]
    errs = np.array([abs(r["rel_error_pct"]) for r in ok_rows])
    summary = {
        "n_sample_requested": len(sample), "n_ok": len(ok_rows), "n_failed": len(rows) - len(ok_rows),
        "abs_rel_error_pct": {
            "median": float(np.median(errs)) if len(errs) else None,
            "p90": float(np.percentile(errs, 90)) if len(errs) else None,
            "max": float(np.max(errs)) if len(errs) else None,
        },
    }

    # 特別股：PBR結構上通常查無資料，單獨測試不混進主樣本統計
    pref_rows = []
    for sid in PREFERRED_STOCK_CANDIDATES:
        per = load_dev("TaiwanStockPER", sid, "2024-01-01", "2024-01-10")
        pref_rows.append({"stock_id": sid, "per_rows_found": len(per)})

    out = {"rows": rows, "summary": summary, "preferred_stock_check": pref_rows}
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"寫入 {OUT_JSON}")


if __name__ == "__main__":
    main()
