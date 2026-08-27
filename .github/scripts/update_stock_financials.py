# -*- coding: utf-8 -*-
"""每日排程更新 data/stock_detail.json 的「財報」區塊（EPS/毛利率/營益率/ROE），
取代個股頁財報分頁的 client-side FinMind 呼叫（STATUS.json列的P1項目）。

資料源（TWSE官方開放資料，免金鑰，跟fundamentals.json/margin_maintenance.json
同一套「最新一期全市場快照」模式）：
- `t187ap06_L_ci`：上市公司綜合損益表(一般業)——給營業收入/毛利/營業利益/
  歸屬母公司淨利/基本每股盈餘(EPS)。
- `t187ap07_L_ci`：上市公司資產負債表(一般業)——給歸屬母公司權益合計(ROE分母)。

**2026-08-27發現並修正的資料正確性問題（重要，不是外部限制，是這支腳本的bug）**：
1. `t187ap06_L_ci` 回傳的數值單位是「仟元」（跟月營收端點同一慣例），但原本
   這裡沒有乘1000——用回補歷史季度時交叉比對月營收總和才發現這個bug（見
   `research/build_stock_financials_history.py` 檔頭說明）。已修正：revenue/
   gross/op/net_income_parent全部乘1000對齊NT元，EPS本身是每股金額不用轉換。
2. **更關鍵**：TWSE官方季報格式對Q2/Q3是「累計數」（第二季報表其實是上半年
   累計、第三季報表是前三季累計），不是單季數字——用月營收交叉驗證發現：
   這支腳本原本直接把Q2的原始回傳值當成「單季」存進quarters陣列，實際上
   那是H1累計值（跟FinMind第三方整理過的單季數字混在同一個陣列裡會兜不起來，
   YoY/成長率計算會整個錯）。已修正：`main()`改成用「本次累計數 − 陣列裡
   已有的同年較早季度加總」還原成單季數字，同年較早季度缺的話就跳過不merge
   （寧可这一季暫時沒有，也不要塞一個算錯的單季數字進去）。
**已知限制，誠實揭露**：
1. 這兩個端點的 `_ci` 後綴是「一般業」分類，不含金融控股(_bd)/證券(_fh)/
   保險(_ins)/其他金融(_mim)——這些特殊產業的財報格式跟一般業不同，TWSE
   分開發布，這支腳本目前只處理一般業，金融股的財報分頁會維持FinMind路徑
   （見index.html的降級邏輯），不是這裡漏抓。
2. FCF（自由現金流）：TWSE/TPEx openapi都沒有現金流量表的開放資料端點（已
   查證兩邊swagger完整清單確認）；MOPS(mops.twse.com.tw)網頁查詢雖然有現金
   流量表，但2026-08-27重新實測其查詢端點(ajax_t164sb04)仍回傳「FOR SECURITY
   REASONS」反爬蟲阻擋，需要先走表單頁拿session/cookie才能過關——**這是重新
   驗證過的現況，不是沒查證就寫「永遠不可能」**，若之後要投入時間做這件事，
   需要處理MOPS的session/cookie流程，是可行但需要額外工程投入的方向，不是
   資料源不存在。個股頁財報分頁的FCF目前維持FinMind。
3. 跟月營收/PER一樣，這兩個端點只給「最新一期」全市場快照，用累積式寫回
   （每季只會新增一筆，讀repo裡已commit的stock_detail.json當底merge）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "stock_detail.json"
TW_TZ = timezone(timedelta(hours=8))

INCOME_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
BALANCE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
QUARTERS_TO_KEEP = 8


def _get_retry(url: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """official端點逾時/暫時性錯誤重試(指數退避)，2026-08-27新增——使用者指出
    「TWSE端點逾時目前是靜靜跳過」。4xx（含反爬蟲/IP封鎖）不重試，直接把該次
    response交給呼叫端自己的raise_for_status()處理，重試那類錯誤不會成功。"""
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


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
    """回傳「TWSE官方原始回傳值」，**Q2/Q3是累計數（見檔頭2026-08-27說明），
    這裡先不做單季還原**——單季還原需要陣列裡已有的同年較早季度資料，
    要在 main() 裡跟既有 quarters 合併時才能做，這裡只負責忠實抓值+單位轉換
    （仟元→元）。回傳的key統一叫 `*_cum`，提醒呼叫端這是累計數，不能直接當
    單季用。"""
    r = _get_retry(INCOME_URL, timeout=30)
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
        # 2026-08-27修正：官方單位是仟元（跟月營收端點同慣例），原本沒乘1000。
        out[code] = {
            "year": yq[0], "quarter": yq[1],
            "revenue_cum": revenue * 1000,
            "gross_cum": gross * 1000 if gross is not None else None,
            "op_cum": op * 1000 if op is not None else None,
            "net_income_parent_cum": net_parent * 1000 if net_parent is not None else None,
            "eps_cum": eps,  # 每股金額本身不用轉換
        }
    return out


def discretize_quarter(existing_quarters: list[dict], cum: dict) -> dict | None:
    """把TWSE官方回傳的「累計數」(cum)還原成單季數字。Q1本身就是單季（累計==單季），
    Q2/Q3/Q4要減掉陣列裡已有的同年較早季度加總才是真正的單季數。如果較早季度
    缺資料（陣列裡同年份的季度數不夠），寧可回傳None跳過這次merge，也不要塞一個
    算錯的單季數字進去——這是2026-08-27用月營收交叉驗證抓到的真bug修正，不是
    自己憑空猜的邊界情況。"""
    y, q = cum["year"], cum["quarter"]
    if q == 1:
        revenue = cum["revenue_cum"]
        gross, op = cum["gross_cum"], cum["op_cum"]
        return {
            "year": y, "quarter": 1,
            "revenue": revenue,
            "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
            "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
            "net_income_parent": cum["net_income_parent_cum"],
            "eps": cum["eps_cum"],
        }
    prior = [r for r in existing_quarters if r.get("year") == y and r.get("quarter", 0) < q]
    if len(prior) < q - 1:
        return None  # 同年較早季度資料不齊，沒辦法安全還原成單季數
    prior_revenue = sum(r["revenue"] for r in prior)
    # gross/op只存了百分比，用「百分比x當季revenue」還原絕對值來加總——這是
    # 近似（受限於百分比只存到小數點後2位），但誤差在還原單季用途上可忽略。
    prior_gross = sum((r.get("revenue") or 0) * (r.get("gross_margin_pct") or 0) / 100 for r in prior)
    prior_op = sum((r.get("revenue") or 0) * (r.get("op_margin_pct") or 0) / 100 for r in prior)
    prior_net = sum(r.get("net_income_parent") or 0 for r in prior)
    prior_eps = sum(r.get("eps") or 0 for r in prior)
    revenue = cum["revenue_cum"] - prior_revenue
    gross = (cum["gross_cum"] - prior_gross) if cum["gross_cum"] is not None else None
    op = (cum["op_cum"] - prior_op) if cum["op_cum"] is not None else None
    net = (cum["net_income_parent_cum"] - prior_net) if cum["net_income_parent_cum"] is not None else None
    eps = (cum["eps_cum"] - prior_eps) if cum["eps_cum"] is not None else None
    return {
        "year": y, "quarter": q,
        "revenue": revenue,
        "gross_margin_pct": round(gross / revenue * 100, 2) if gross is not None and revenue else None,
        "op_margin_pct": round(op / revenue * 100, 2) if op is not None and revenue else None,
        "net_income_parent": net,
        "eps": round(eps, 2) if eps is not None else None,
    }


def fetch_balance() -> dict[str, dict]:
    """2026-08-27新增（B17未來性濾網(a)類因子需要）：除了既有的
    `equity`（ROE分母），額外抓`common_stock_capital`（股本，台股普通股
    面額統一為每股新台幣10元，approx shares_outstanding = 股本/10，t187ap03_L
    的「已發行普通股數」只涵蓋部分公司，用股本反推更穩定）+
    `non_current_assets`（非流動資產，當「產能利用率」的分母代理——這個
    endpoint沒有單獨的「固定資產/不動產廠房及設備」欄位，非流動資產包含
    固定資產但也包含商譽/長期投資等，是刻意的簡化近似，不是精確的固定
    資產數字，誠實揭露）。回傳結構從原本`{code: equity}`改成
    `{code: {equity, common_stock_capital, non_current_assets}}`，呼叫端
    要跟著改。"""
    r = _get_retry(BALANCE_URL, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("t187ap07_L_ci 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    out = {}
    for row in rows:
        code = row.get("公司代號")
        equity = _num(row.get("歸屬於母公司業主之權益合計"))
        if code and equity is not None:
            out[code] = {
                "equity": equity,
                "common_stock_capital": _num(row.get("股本")),
                "non_current_assets": _num(row.get("非流動資產")),
            }
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
    skipped_no_baseline = 0
    try:
        income = fetch_income()
        equity = fetch_balance()
        for code, cum in income.items():
            entry = stocks.setdefault(code, {})
            fin = entry.setdefault("financials", {})
            existing_quarters = fin.get("quarters", [])
            discrete = discretize_quarter(existing_quarters, cum)
            if discrete is None:
                skipped_no_baseline += 1
                continue
            fin["quarters"] = merge_quarters(existing_quarters, discrete)
            bal = equity.get(code) or {}
            eq = bal.get("equity")
            fin["equity_parent_latest"] = eq
            fin["roe_ttm_pct"] = compute_roe_ttm(fin["quarters"], eq)
            capital = bal.get("common_stock_capital")
            fin["shares_outstanding_approx"] = round(capital / 10, 0) if capital else None
            fin["non_current_assets_latest"] = bal.get("non_current_assets")
        income_updated = len(income) - skipped_no_baseline
    except Exception as e:
        print(f"財報(income/balance) 更新失敗：{e}")
        errors.append(f"financials: {e}")

    payload.setdefault("meta", {})
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["financials_source"] = "TWSE openapi t187ap06_L_ci(綜合損益表-一般業) + t187ap07_L_ci(資產負債表-一般業)"
    payload["meta"]["financials_updated_count"] = income_updated
    payload["meta"]["financials_skipped_no_baseline_count"] = skipped_no_baseline
    payload["meta"].setdefault("errors", [])
    payload["meta"]["errors"] = errors

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：財報更新 {income_updated} 檔，{skipped_no_baseline} 檔因缺同年較早季度"
          f"基準無法安全還原單季數字而跳過（合計 {len(stocks)} 檔有任何資料）")
    if errors:
        print(f"部分失敗（不中止）：{errors}")


if __name__ == "__main__":
    main()
