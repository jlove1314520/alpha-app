# -*- coding: utf-8 -*-
"""每日排程更新 data/stock_detail.json 的「財報」區塊（EPS/毛利率/營益率/ROE），
取代個股頁財報分頁的 client-side FinMind 呼叫（STATUS.json列的P1項目）。

資料源（TWSE官方開放資料，免金鑰，跟fundamentals.json/margin_maintenance.json
同一套「最新一期全市場快照」模式）：
- `t187ap06_L_ci`：上市公司綜合損益表(一般業)——給營業收入/毛利/營業利益/
  歸屬母公司淨利/基本每股盈餘(EPS)。
- `t187ap07_L_ci`：上市公司資產負債表(一般業)——給歸屬母公司權益合計(ROE分母)。

**已知限制，誠實揭露**：
1. 這兩個端點的 `_ci` 後綴是「一般業」分類，不含金融控股(_bd)/證券(_fh)/
   保險(_ins)/其他金融(_mim)——這些特殊產業的財報格式跟一般業不同，TWSE
   分開發布，這支腳本目前只處理一般業，金融股的財報分頁會維持FinMind路徑
   （見index.html的降級邏輯），不是這裡漏抓。
2. TWSE官方沒有現金流量表的對應開放資料端點（已查證swagger完整清單，沒有
   任何路徑含「現金流量」），FCF（自由現金流）無法比照這裡的做法遷移，
   個股頁財報分頁的FCF維持FinMind，這是永久性限制不是暫時沒做。
3. 跟月營收/PER一樣，這兩個端點只給「最新一期」全市場快照，用累積式寫回
   （每季只會新增一筆，讀repo裡已commit的stock_detail.json當底merge）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "stock_detail.json"
TW_TZ = timezone(timedelta(hours=8))

INCOME_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
BALANCE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
QUARTERS_TO_KEEP = 8


def _num(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_year_quarter(row: dict) -> tuple[int, int] | None:
    try:
        return int(row["年度"]) + 1911, int(row["季別"])
    except (KeyError, ValueError):
        return None


def load_existing() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "stocks": {}}


def fetch_income() -> dict[str, dict]:
    r = requests.get(INCOME_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap06_L_ci 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("公司代號")
        yq = _roc_year_quarter(row)
        revenue = _num(row.get("營業收入"))
        if not code or not yq or revenue is None:
            continue
        gross = _num(row.get("營業毛利（毛損）淨額"))
        op = _num(row.get("營業利益（損失）"))
        net_parent = _num(row.get("淨利（淨損）歸屬於母公司業主"))
        eps = _num(row.get("基本每股盈餘（元）"))
        out[code] = {
            "year": yq[0], "quarter": yq[1],
            "revenue": revenue,
            "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
            "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
            "net_income_parent": net_parent,
            "eps": eps,
        }
    return out


def fetch_balance() -> dict[str, dict]:
    r = requests.get(BALANCE_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap07_L_ci 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("公司代號")
        equity = _num(row.get("歸屬於母公司業主之權益合計"))
        if code and equity is not None:
            out[code] = equity
    return out


def merge_quarters(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = list(existing or [])
    rows = [r for r in rows if not (r.get("year") == latest["year"] and r.get("quarter") == latest["quarter"])]
    rows.append(latest)
    rows.sort(key=lambda r: (r["year"], r["quarter"]))
    return rows[-QUARTERS_TO_KEEP:]


def compute_roe_ttm(quarters: list[dict], equity_latest: float | None) -> float | None:
    last4 = [q for q in quarters if q.get("net_income_parent") is not None][-4:]
    if len(last4) < 4 or not equity_latest:
        return None
    ttm_ni = sum(q["net_income_parent"] for q in last4)
    return round(ttm_ni / equity_latest * 100, 2)


def main():
    payload = load_existing()
    stocks = payload.setdefault("stocks", {})

    errors = []
    income_updated = 0
    try:
        income = fetch_income()
        equity = fetch_balance()
        for code, latest in income.items():
            entry = stocks.setdefault(code, {})
            fin = entry.setdefault("financials", {})
            fin["quarters"] = merge_quarters(fin.get("quarters"), latest)
            eq = equity.get(code)
            fin["equity_parent_latest"] = eq
            fin["roe_ttm_pct"] = compute_roe_ttm(fin["quarters"], eq)
        income_updated = len(income)
    except Exception as e:
        print(f"財報(income/balance) 更新失敗：{e}")
        errors.append(f"financials: {e}")

    payload.setdefault("meta", {})
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["financials_source"] = "TWSE openapi t187ap06_L_ci(綜合損益表-一般業) + t187ap07_L_ci(資產負債表-一般業)"
    payload["meta"]["financials_updated_count"] = income_updated
    payload["meta"].setdefault("errors", [])
    payload["meta"]["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：財報更新 {income_updated} 檔（合計 {len(stocks)} 檔有任何資料）")
    if errors:
        print(f"部分失敗（不中止）：{errors}")


if __name__ == "__main__":
    main()
