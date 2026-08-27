"""一次性（可重複執行、merge-safe）回補 data/stock_detail.json 的財報季度歷史（2026-08-27）。

背景：跟 build_fundamentals_json.py 同一個問題——
`.github/scripts/update_stock_financials.py` 用 TWSE openapi t187ap06_L_ci/
t187ap07_L_ci 每日排程更新，但這兩個端點只給「最新一期全市場快照」，沒有
歷史區間查詢，導致目前 data/stock_detail.json 每檔只累積到 1 季（2026 Q2）。
score_live.py 的 earnings_growth 因子要算EPS年增率至少需要「今年同季 vs
去年同季」，也就是至少 5 季（含當季）以上的歷史，光靠每日累積要再等超過
一年才會自然長出來——這裡直接讀研究端已經合法快取的 FinMind
`TaiwanStockFinancialStatements`（損益表，含EPS/營收/毛利/營業利益/歸屬母公司
淨利）+ `TaiwanStockBalanceSheet`（資產負債表，歸屬母公司權益，ROE分母）
本機 parquet 快取，一次回補歷史季度，不對 FinMind 打任何新請求。

**merge-safe，不是覆寫**（吸取 build_fundamentals_json.py 重跑時砍掉502檔
的教訓）：只在缺漏的地方補資料，既有（daily排程來源、較新）的季度/ROE/權益
不會被本機快取覆蓋；股票數只會增加不會減少，減少就中止不寫檔。

**FinMind命名地雷**：`TaiwanStockFinancialStatements`（損益表）跟
`TaiwanStockBalanceSheet`（資產負債表）兩個資料集都有一個叫
`EquityAttributableToOwnersOfParent` 的 type，但語意完全不同——損益表裡的
這個type其實是「淨利（淨損）歸屬於母公司業主」（用origin_name確認過），
資產負債表裡的才是真正的「歸屬於母公司業主之權益合計」。兩邊絕對不能混用，
已用origin_name交叉確認過。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_PATH = Path(__file__).parent.parent / "data" / "stock_detail.json"
QUARTERS_TO_KEEP = 8  # 跟 update_stock_financials.py 的 QUARTERS_TO_KEEP 一致


def _codes_from_cache(dataset: str) -> set[str]:
    codes = set()
    for p in RAW_DIR.glob(f"{dataset}__*.parquet"):
        m = re.match(rf"^{dataset}__(.+?)__\d{{4}}-\d{{2}}-\d{{2}}", p.name)
        if m:
            codes.add(m.group(1))
    return codes


def _load_concat(dataset: str, code: str) -> pd.DataFrame:
    frames = []
    for p in RAW_DIR.glob(f"{dataset}__{code}__*.parquet"):
        try:
            df = pd.read_parquet(p)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _quarter_from_date(date_str: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d{4})-(\d{2})-\d{2}$", str(date_str))
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    return year, (month - 1) // 3 + 1


def build_income_quarters(code: str) -> list[dict]:
    df = _load_concat("TaiwanStockFinancialStatements", code)
    if df.empty:
        return []
    out = []
    for date, g in df.groupby("date"):
        yq = _quarter_from_date(date)
        if not yq:
            continue
        vals = dict(zip(g["type"], g["value"]))
        revenue = vals.get("Revenue")
        if revenue is None or pd.isna(revenue) or revenue == 0:
            continue
        gross = vals.get("GrossProfit")
        op = vals.get("OperatingIncome")
        # 注意：這是損益表資料集，這個type語意是「淨利歸屬於母公司業主」，
        # 跟資產負債表資料集裡同名type（權益合計）不是同一件事，見檔頭說明。
        net_parent = vals.get("EquityAttributableToOwnersOfParent")
        eps = vals.get("EPS")
        out.append({
            "year": yq[0], "quarter": yq[1],
            "revenue": float(revenue),
            "gross_margin_pct": round(float(gross) / float(revenue) * 100, 2) if gross is not None and pd.notna(gross) else None,
            "op_margin_pct": round(float(op) / float(revenue) * 100, 2) if op is not None and pd.notna(op) else None,
            "net_income_parent": float(net_parent) if net_parent is not None and pd.notna(net_parent) else None,
            "eps": float(eps) if eps is not None and pd.notna(eps) else None,
        })
    out.sort(key=lambda r: (r["year"], r["quarter"]))
    return out


def build_equity_latest(code: str) -> float | None:
    df = _load_concat("TaiwanStockBalanceSheet", code)
    if df.empty:
        return None
    last_date = df["date"].max()
    sub = df[df["date"] == last_date]
    vals = dict(zip(sub["type"], sub["value"]))
    eq = vals.get("EquityAttributableToOwnersOfParent")
    return float(eq) if eq is not None and pd.notna(eq) else None


def merge_quarters(existing: list[dict] | None, backfill: list[dict]) -> list[dict]:
    """既有(daily排程，較即時)優先——同一(year,quarter)以existing為準，
    backfill只補existing沒有的季度。"""
    by_key = {(r["year"], r["quarter"]): r for r in backfill}
    for r in (existing or []):
        by_key[(r["year"], r["quarter"])] = r  # existing 覆蓋 backfill，不是反過來
    rows = sorted(by_key.values(), key=lambda r: (r["year"], r["quarter"]))
    return rows[-QUARTERS_TO_KEEP:]


def compute_roe_ttm(quarters: list[dict], equity_latest: float | None) -> float | None:
    last4 = [q for q in quarters if q.get("net_income_parent") is not None][-4:]
    if len(last4) < 4 or not equity_latest:
        return None
    ttm_ni = sum(q["net_income_parent"] for q in last4)
    return round(ttm_ni / equity_latest * 100, 2)


def main():
    income_codes = _codes_from_cache("TaiwanStockFinancialStatements")
    balance_codes = _codes_from_cache("TaiwanStockBalanceSheet")
    print(f"快取涵蓋：損益表 {len(income_codes)} 檔、資產負債表 {len(balance_codes)} 檔")

    payload = {"meta": {}, "stocks": {}}
    if OUT_PATH.exists():
        try:
            payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    stocks = payload.setdefault("stocks", {})
    prior_count = len(stocks)

    backfilled = 0
    for code in sorted(income_codes):
        backfill_q = build_income_quarters(code)
        if not backfill_q:
            continue
        entry = stocks.setdefault(code, {})
        fin = entry.setdefault("financials", {})
        before_len = len(fin.get("quarters", []))
        fin["quarters"] = merge_quarters(fin.get("quarters"), backfill_q)
        if len(fin["quarters"]) > before_len:
            backfilled += 1
        if "equity_parent_latest" not in fin or fin.get("equity_parent_latest") is None:
            eq = build_equity_latest(code)
            if eq is not None:
                fin["equity_parent_latest"] = eq
        if fin.get("roe_ttm_pct") is None:
            fin["roe_ttm_pct"] = compute_roe_ttm(fin["quarters"], fin.get("equity_parent_latest"))

    new_count = len(stocks)
    if new_count < prior_count:
        raise RuntimeError(
            f"覆蓋率不應該在merge之後下降，但從 {prior_count} 變成 {new_count}——"
            "已中止寫入，不要用這份結果覆蓋既有檔案。"
        )

    payload.setdefault("meta", {})
    payload["meta"]["financials_history_backfill_note"] = (
        "2026-08-27一次性回補：讀research端FinMind歷史parquet快取"
        "（TaiwanStockFinancialStatements+TaiwanStockBalanceSheet）補上"
        "季度歷史（原本daily排程只有最新一期，YoY EPS比較需要至少5季）。"
        "merge-safe：既有較新的季度資料不會被覆蓋，只補缺漏。"
    )
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(stocks)} 檔有資料（merge前既有 {prior_count} 檔，"
          f"{backfilled} 檔補進更多季度歷史）")


if __name__ == "__main__":
    main()
