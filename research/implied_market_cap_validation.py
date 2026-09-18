"""隱含市值重建法交叉比對（`CORE_TILT_SPEC.md` 第2.1節，2026-09-18總司令
【裁示】「市值重建——先查一件事，再決定要不要做校正工程」）。

**用詞更正（2026-09-18，總司令裁示，取代原本「誤差」的說法）**：這份
驗證**沒有獨立真值**——34檔算的是兩條重建法互相差多少，不是離真實
市值多遠，兩條可以同時往同一方向偏。全部欄位/變數/輸出一律用
`path1_vs_path2_diff`（兩法差異），不用「誤差」（error）這個字，避免
幾輪後有人誤把這個數字當成精度指標。

**路徑2已升級（2026-09-18，取代先前「股本÷10」的假設10元面額版本）**：
先查證TWSE `t187ap03_L`（上市公司基本資料）有沒有「已發行普通股數」
欄位——**查到了，而且精確**：
    `已發行普通股數或TDR原股發行股數`（直接股數，不用反推）
    `普通股每股面額`（真實面額，不是假設的10元）
驗證：台積電259,323,700,670(實收資本額)÷10=25,932,370,067，跟該欄位
的25,932,370,067**完全相符**；矽力-KY(6415)面額卻是「新台幣2.5000元」
不是10元，直接解釋了上一輪用「股本÷10」算出的120%落差（真實股數是
股本÷2.5，是股本÷10的4倍）；成信實業(6969)面額是「無面額」，股本÷10
這個概念對它結構上不成立。

**涵蓋範圍誠實揭露**：`t187ap03_L`只有查證當下（2026-09-18）的**即時
快照**，swagger規格裡只有`_L`（上市）/`_P`（公開發行）兩個變體，都是
「現在」不是「歷史」——沒有可回溯查詢2015~2024任一天的股數/面額歷史
序列。本檔案的34檔交叉比對用「今天的股數快照」對比「2024-12-30的
價格與財報」，嚴格說不是同一天，但面額（`普通股每股面額`）是公司
結構性、極少變動的常數（不是逐日變動的數字），拿今天查到的面額去
推算歷史股本對應的股數，遠比原本假設「大家都是10元」準確；股數本身
（不是面額）若在2024-12-30到查證日之間有增資/減資才會有落差，本檔案
對此誠實標記，不假裝完全精確。

**歷史回測（`core_tilt_backtest.py`）建議做法（本檔案只驗證，不實作）**：
用「歷史各期的股本（資產負債表PIT序列，本來就有）÷ 今天查到的真實面額」
推算歷史股數，不是用「今天的股數快照套用到全部歷史」——面額變動極罕見
可視為常數，股本本身逐期變動已經被PIT序列捕捉到，這樣兩個問題（面額
錯誤、歷史股本變動）都處理到，不需要另外做「面額比值校正」這類間接
診斷工程（上一輪提的`implied_shares_from_bvps`比值法已經被更直接的
`t187ap03_L`欄位取代，不再需要）。

**核准門檻（2026-09-18總司令裁示，不排除任何個股）**：
    全部34檔（含金融股/KY/面額特殊）：
    path1_vs_path2_diff中位數 ≤5% 且 P90 ≤12% → 核准，可動backtest
    達不到 → 回報最大10檔差異與各自根因，總司令裁示是否降標準或換路線

執行：python research/implied_market_cap_validation.py
"""
from __future__ import annotations

import json
import re
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

TWSE_BASIC_INFO = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"  # 上市公司基本資料（即時快照，見檔頭說明）

# 2026-09-18查證發現：`.github/scripts/update_stock_financials.py`用的
# TWSE openapi `t187ap07_L_ci`（一般業資產負債表）金控/銀行/證券/保險
# 一律缺值（None）——這幾類公司依規定用「金融業」格式的財報，走另一個
# 端點`t187ap07_L_fh`。這裡列出的是本次驗證樣本裡屬於這一類、需要走
# `t187ap07_L_fh`才拿得到股本的代號（不是全市場金融股清單，只是本次
# 驗證樣本涵蓋到的）。**2026-09-18新增**：升級後路徑2優先用
# `t187ap03_L`的直接股數欄位，這份財報端點只在`t187ap03_L`查無資料時
# 當備援（capital/par_value推算），金融股分類判斷仍保留供備援路徑使用。
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

# 核准門檻（2026-09-18總司令裁示，全部34檔一起算，不排除問題股）
DIFF_MEDIAN_THRESHOLD_PCT = 5.0
DIFF_P90_THRESHOLD_PCT = 12.0


def _num(x):
    try:
        if x in (None, ""):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _parse_par_value(raw: str | None) -> float | None:
    """解析`普通股每股面額`欄位（例如"新台幣                 10.0000元"），
    "無面額"回傳None（結構上不適用capital/par推算，見檔頭說明）。"""
    if not raw or "無面額" in raw:
        return None
    m = re.search(r"([\d.]+)", raw)
    return float(m.group(1)) if m else None


def _twse_basic_info_map() -> dict[str, dict]:
    r = requests.get(TWSE_BASIC_INFO, timeout=30)
    r.raise_for_status()
    rows = r.json()
    out = {}
    for row in rows:
        code = row.get("公司代號")
        if not code:
            continue
        out[code] = {
            "issued_shares": _num(row.get("已發行普通股數或TDR原股發行股數")),
            "par_value": _parse_par_value(row.get("普通股每股面額")),
            "capital": _num(row.get("實收資本額")),
            "foreign_registration": (row.get("外國企業註冊地國") or "－").strip(),
        }
    return out


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
            "equity_attributable_parent": row.get("歸屬於母公司業主之權益合計") or row.get("歸屬於母公司業主之權益"),
            "equity_total": row.get("權益總額") or row.get("權益總計"),
            "noncontrolling": row.get("非控制權益"),
        }
    return out


def path2_market_cap(stock_id: str, twse_basic: dict, twse_general: dict, twse_financial: dict) -> dict:
    """路徑2（2026-09-18升級版）：優先用`t187ap03_L`的直接股數欄位
    （`已發行普通股數`），查無資料才退回capital/par_value（用真實面額，
    不是假設10元）。"""
    try:
        px = adjusted_price_series(stock_id)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"價格抓取失敗: {e}"}
    if px.empty:
        return {"ok": False, "reason": "無價格資料"}
    last_row = px.sort_values("date").iloc[-1]
    price = float(last_row["close"])
    date = str(last_row["date"])[:10]

    basic = twse_basic.get(stock_id)
    method = None
    shares = None
    if basic and basic.get("issued_shares"):
        shares = basic["issued_shares"]
        method = "t187ap03_L直接股數"
    elif basic and basic.get("par_value") and basic.get("capital"):
        shares = basic["capital"] / basic["par_value"]
        method = f"t187ap03_L capital/par_value（面額{basic['par_value']}元）"
    else:
        # 備援：t187ap03_L查無資料（理論上不該發生，34檔驗證樣本全數命中），
        # 退回舊版capital(千元，注意單位跟t187ap03_L的capital不同)/10 假設
        row = (twse_financial if stock_id in FIN_HOLDING_IDS else twse_general).get(stock_id) \
            or twse_financial.get(stock_id) or twse_general.get(stock_id)
        if row is None:
            return {"ok": False, "reason": "t187ap03_L與資產負債表端點皆查無此代號"}
        capital_thousand = _num(row.get("common_stock_capital"))
        if not capital_thousand:
            return {"ok": False, "reason": "備援路徑股本欄位仍缺值"}
        shares = capital_thousand * 1000.0 / 10.0  # 假設面額10元，明確標記為備援假設
        method = "備援：資產負債表股本(千元)/10（假設面額10元，未經t187ap03_L確認）"

    market_cap_yuan = price * shares
    basic_row = twse_basic.get(stock_id, {})
    return {
        "ok": True, "price": price, "date": date, "shares": shares, "method": method,
        "market_cap_yuan": market_cap_yuan,
        "par_value": basic_row.get("par_value"),
        "foreign_registration": basic_row.get("foreign_registration"),
    }


def path1_market_cap(stock_id: str, as_of_date: str) -> dict:
    """路徑1：PBR × EquityAttributableToOwnersOfParent（FinMind）。
    金控類 `EquityAttributableToOwnersOfParent` 常缺值，缺值時退而用
    `Equity`（總權益，含非控制權益）並標記`used_total_equity=True`——
    這正是候選(b)，缺值時退回哪個欄位要誠實記錄。"""
    per = load_dev("TaiwanStockPER", stock_id, "2000-01-01")
    if per.empty:
        return {"ok": False, "reason": "無PBR資料（常見於特別股，PBR/PER結構上不適用）"}
    per["date"] = pd.to_datetime(per["date"])
    asof = pd.Timestamp(as_of_date)
    avail = per[per["date"] <= asof]
    if avail.empty:
        avail = per
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


def build_sample(twse_general: dict, twse_financial: dict) -> list[str]:
    """依裁示挑樣本：強制納入清單 + 路徑2市值分大/中/小三級距各10檔。"""
    active = active_stock_ids()
    normal = active[active["stock_id"].str.match(r"^\d{4}$")]

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

    print(f"股本資料可用的候選池：{len(candidates)}檔（排除強制清單後）")

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

    return list(FORCED_STOCKS.keys()) + picked


def main() -> None:
    twse_basic = _twse_basic_info_map()
    twse_general = _twse_balance_map(TWSE_BALANCE_GENERAL)
    twse_financial = _twse_balance_map(TWSE_BALANCE_FINANCIAL)
    sample = build_sample(twse_general, twse_financial)
    industry_map = load_industry_map()

    rows = []
    for sid in sample:
        p2 = path2_market_cap(sid, twse_basic, twse_general, twse_financial)
        if not p2.get("ok"):
            rows.append({"stock_id": sid, "ok": False, "stage": "path2", "reason": p2.get("reason"),
                         "forced_reason": FORCED_STOCKS.get(sid)})
            continue
        p1 = path1_market_cap(sid, p2["date"])
        if not p1.get("ok"):
            rows.append({"stock_id": sid, "ok": False, "stage": "path1", "reason": p1.get("reason"),
                         "forced_reason": FORCED_STOCKS.get(sid), "path2_market_cap_yuan": p2["market_cap_yuan"]})
            continue
        mc1 = p1["market_cap"]
        mc2 = p2["market_cap_yuan"]
        diff = (mc1 - mc2) / ((mc1 + mc2) / 2.0)
        rows.append({
            "stock_id": sid, "ok": True,
            "forced_reason": FORCED_STOCKS.get(sid),
            "industry": industry_map.get(sid, "unknown"),
            "as_of_date": p2["date"],
            "path1_market_cap_yuan": mc1, "path2_market_cap_yuan": mc2,
            "path2_method": p2["method"], "path2_par_value": p2.get("par_value"),
            "path2_foreign_registration": p2.get("foreign_registration"),
            "path1_vs_path2_diff_pct": round(diff * 100, 2),
            "path1_used_total_equity": p1["used_total_equity"],
            "path1_pbr": p1["pbr"], "path1_pbr_date": p1["pbr_date"], "path1_bs_pit_date": p1["bs_pit_date"],
        })

    ok_rows = [r for r in rows if r["ok"]]
    diffs = np.array([abs(r["path1_vs_path2_diff_pct"]) for r in ok_rows])
    diffs_sorted = np.sort(diffs)
    median_diff = float(np.median(diffs)) if len(diffs) else None
    p90_diff = float(diffs_sorted[int(0.9 * (len(diffs_sorted) - 1))]) if len(diffs) else None
    max_diff = float(np.max(diffs)) if len(diffs) else None
    approved = (median_diff is not None and median_diff <= DIFF_MEDIAN_THRESHOLD_PCT
                and p90_diff is not None and p90_diff <= DIFF_P90_THRESHOLD_PCT)
    summary = {
        "n_sample_requested": len(sample), "n_ok": len(ok_rows), "n_failed": len(rows) - len(ok_rows),
        "path1_vs_path2_diff_pct": {"median": median_diff, "p90": p90_diff, "max": max_diff},
        "approval_threshold": {"median_max": DIFF_MEDIAN_THRESHOLD_PCT, "p90_max": DIFF_P90_THRESHOLD_PCT},
        "approved_all_34_no_exclusion": approved,
    }

    pref_rows = []
    for sid in PREFERRED_STOCK_CANDIDATES:
        per = load_dev("TaiwanStockPER", sid, "2024-01-01", "2024-01-10")
        pref_rows.append({"stock_id": sid, "per_rows_found": len(per)})

    out = {"rows": rows, "summary": summary, "preferred_stock_check": pref_rows}
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not approved:
        worst = sorted(ok_rows, key=lambda r: -abs(r["path1_vs_path2_diff_pct"]))[:10]
        print("未達門檻，最大10檔差異：")
        for r in worst:
            print(f"  {r['stock_id']}: {r['path1_vs_path2_diff_pct']}% ({r.get('industry')}, {r.get('path2_method')})")
    print(f"寫入 {OUT_JSON}")


if __name__ == "__main__":
    main()
