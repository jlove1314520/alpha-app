# -*- coding: utf-8 -*-
"""美股財報/FCF基本面因子管線（B29，2026-09-02完成實作）。

## 為什麼選這幾個指標
`BACKLOG.md` B29條目只登錄規格、沒人實測過yfinance目前版本的欄位長相。
本檔案是接線前先實測（見下方「yfinance實測發現」）後，挑選「所有追蹤股票
都穩定拿得到、公式簡單不需要多欄位交叉推導」的4個指標：

1. `gross_margin`  毛利率 = Gross Profit / Total Revenue
2. `operating_margin` 營業利益率 = Operating Income / Total Revenue
3. `revenue_yoy`  營收年增率 = 最新年度Total Revenue / 前一年度Total Revenue - 1
4. `fcf_margin`  自由現金流利潤率 = Free Cash Flow / Total Revenue
   （同時原始金額 `free_cash_flow` 也一併輸出，不是只給比率）

## yfinance實測發現（2026-09-02，對AAPL/MSFT/NVDA/TSM/GOOGL/AMZN六檔實測）
- `Ticker.financials`（年度損益表）的DataFrame，index（欄位名稱）在六檔
  之間**命名不完全一致**（例如MSFT/NVDA有`Total Unusual Items`、AAPL沒有），
  但`Total Revenue`、`Gross Profit`、`Operating Income`四檔六檔都穩定存在。
- `Ticker.cashflow`（年度現金流量表）六檔都有`Free Cash Flow`這個欄位，
  是yfinance自己算好的現成欄位，不需要自己拿Operating Cash Flow減
  Capital Expenditure再組一次（避免正負號搞錯的風險）。
- `Ticker.balance_sheet` 六檔都能拿到但本檔案沒用到（先只做損益表+現金
  流量表的4個指標，資產負債表相關因子留給以後有需要再加）。
- columns（各年度期別）是`pandas.Timestamp`，**由新到舊排序**，但
  `financials`跟`cashflow`兩個DataFrame的欄位集合不保證完全一樣（實測
  GOOGL的cashflow比financials多一年舊資料），所以不能單純假設兩個
  DataFrame用同一個位置索引對應同一個期別——本檔案用「先取
  financials最新兩期的實際日期，再拿這個日期去cashflow裡找同一欄」
  的方式對齊，不用位置假設。
- 最新一欄（index 0）觀察到的六檔資料都是完整數字（非NaN），但更舊的
  欄位（例如AAPL/NVDA/TSM的第5欄）出現過NaN——這代表yfinance回傳的
  歷史深度不保證每欄都有值，本檔案任何用到的欄位都會先檢查
  `pandas.isna()`，缺值就誠實留`None`，不當作0。

## 已知限制（誠實揭露，不要當成無限制的資料源）
- yfinance不是官方API，是爬雅虎財經網頁/內部端點包裝而成，欄位命名
  跟可得性可能隨時間變動、也可能無預警回傳空DataFrame或拋例外——本檔案
  每檔股票都包在try/except裡，單檔失敗不影響其他檔案。
- 只用「年度」財報（`.financials`/`.cashflow`預設回傳年度資料，不是
  `.quarterly_financials`），所以`revenue_yoy`是「最近兩個財年」的年增率，
  不是最近一季的年增率，且更新頻率是一年一次（隨財報公布），不是每日。
- `Free Cash Flow`是yfinance自己算的衍生欄位，算法細節（例如是否扣除
  租賃相關資本支出）沒有公開文件，不保證跟公司自己財報揭露的FCF數字
  逐分逐毫一致，僅供參考排序用，不是精確會計數字。
- 追蹤範圍跟着`data/earnings_calendar.json`裡`earnings`的keys走，目前
  是6檔美股（AAPL/MSFT/NVDA/TSM/GOOGL/AMZN），這份清單以後如果變動，
  本檔案會自動跟著抓新清單，不用改程式碼。

## 執行方式
本機手動跑：`python research/factors_us_financials.py`
（尚未掛GitHub Actions排程，是否掛排程留給下一輪決定，不在這次任務範圍內，
理由見`BACKLOG.md` B29條目最新更新）。
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parent.parent
EARNINGS_CALENDAR_PATH = REPO_ROOT / "data" / "earnings_calendar.json"
OUT_PATH = REPO_ROOT / "data" / "us_financials.json"

# 節流：yfinance呼叫之間至少間隔這麼多秒，避免短時間內炸資料源
# （比照 .github/scripts/fetch_market_us.py 的風格：單檔失敗記錄、不整包中斷）。
THROTTLE_SECONDS = 1.5

# 這4個指標所需的原始欄位——用來檢查缺值時知道是哪個環節缺的。
REQUIRED_FIN_FIELDS = ["Total Revenue", "Gross Profit", "Operating Income"]
REQUIRED_CF_FIELDS = ["Free Cash Flow"]


def _safe_float(value) -> float | None:
    """把pandas純量轉成float，NaN/缺值一律回傳None（不得用0頂替）。"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_latest_two_periods(financials: pd.DataFrame) -> list[pd.Timestamp]:
    """回傳financials欄位（期別）由新到舊排序後的前兩個非全空期別。"""
    periods: list[pd.Timestamp] = []
    for col in financials.columns:  # yfinance慣例：由新到舊排序
        series = financials[col]
        if series.isna().all():
            continue
        periods.append(col)
        if len(periods) == 2:
            break
    return periods


def compute_ticker_factors(symbol: str) -> dict:
    """對單一美股代碼實際呼叫yfinance並算出4個財報因子，缺值誠實留None。"""
    missing_fields: list[str] = []
    warnings: list[str] = []
    result = {
        "period_end": None,
        "prior_period_end": None,
        "gross_margin": None,
        "operating_margin": None,
        "revenue_yoy": None,
        "free_cash_flow": None,
        "fcf_margin": None,
        "missing_fields": missing_fields,
        "warnings": warnings,
    }

    ticker = yf.Ticker(symbol)
    financials = ticker.financials
    cashflow = ticker.cashflow

    if financials is None or financials.empty:
        warnings.append("financials為空DataFrame，yfinance目前抓不到這檔的損益表")
        return result

    periods = _get_latest_two_periods(financials)
    if not periods:
        warnings.append("financials所有欄位都是全空，無法取得任何期別")
        return result

    latest = periods[0]
    result["period_end"] = latest.strftime("%Y-%m-%d")
    if len(periods) >= 2:
        prior = periods[1]
        result["prior_period_end"] = prior.strftime("%Y-%m-%d")
    else:
        prior = None
        warnings.append("只有1個可用期別，revenue_yoy無法計算（需要至少2期）")

    def fin_value(field: str, period: pd.Timestamp | None):
        if period is None:
            return None
        if field not in financials.index:
            if field not in missing_fields:
                missing_fields.append(field)
            return None
        v = _safe_float(financials.loc[field, period])
        if v is None and field not in missing_fields:
            missing_fields.append(f"{field}@{period.strftime('%Y-%m-%d')}")
        return v

    revenue_latest = fin_value("Total Revenue", latest)
    gross_profit_latest = fin_value("Gross Profit", latest)
    operating_income_latest = fin_value("Operating Income", latest)
    revenue_prior = fin_value("Total Revenue", prior) if prior is not None else None

    if revenue_latest is not None and revenue_latest != 0:
        if gross_profit_latest is not None:
            result["gross_margin"] = round(gross_profit_latest / revenue_latest, 6)
        if operating_income_latest is not None:
            result["operating_margin"] = round(operating_income_latest / revenue_latest, 6)
    elif revenue_latest == 0:
        warnings.append("Total Revenue為0，毛利率/營業利益率分母為0，無法計算")

    if revenue_latest is not None and revenue_prior is not None and revenue_prior != 0:
        result["revenue_yoy"] = round(revenue_latest / revenue_prior - 1, 6)
    elif revenue_prior == 0:
        warnings.append("前一期Total Revenue為0，revenue_yoy分母為0，無法計算")

    # Free Cash Flow：不假設cashflow跟financials欄位位置對齊，用日期比對。
    if cashflow is None or cashflow.empty:
        warnings.append("cashflow為空DataFrame，yfinance目前抓不到這檔的現金流量表")
    else:
        if "Free Cash Flow" not in cashflow.index:
            missing_fields.append("Free Cash Flow")
        elif latest in cashflow.columns:
            fcf = _safe_float(cashflow.loc["Free Cash Flow", latest])
            if fcf is None:
                missing_fields.append(f"Free Cash Flow@{latest.strftime('%Y-%m-%d')}")
            else:
                result["free_cash_flow"] = fcf
                if revenue_latest is not None and revenue_latest != 0:
                    result["fcf_margin"] = round(fcf / revenue_latest, 6)
        else:
            warnings.append(
                f"cashflow沒有跟financials同一個最新期別({latest.strftime('%Y-%m-%d')})的欄位，"
                "跳過free_cash_flow/fcf_margin"
            )

    return result


def main() -> int:
    if not EARNINGS_CALENDAR_PATH.exists():
        print(f"錯誤：找不到 {EARNINGS_CALENDAR_PATH}，無法決定追蹤範圍，中止")
        return 1

    calendar = json.loads(EARNINGS_CALENDAR_PATH.read_text(encoding="utf-8"))
    symbols = list(calendar.get("earnings", {}).keys())
    if not symbols:
        print("錯誤：earnings_calendar.json的earnings是空的，沒有追蹤範圍，中止")
        return 1

    print(f"追蹤範圍（來自earnings_calendar.json）：{symbols}")

    financials_out: dict = {}
    errors: dict = {}

    for i, symbol in enumerate(symbols):
        print(f"[{i + 1}/{len(symbols)}] 抓 {symbol} 財報因子...")
        try:
            factors = compute_ticker_factors(symbol)
            financials_out[symbol] = factors
            if factors["missing_fields"]:
                print(f"  ・{symbol} 缺欄位：{factors['missing_fields']}")
            if factors["warnings"]:
                for w in factors["warnings"]:
                    print(f"  ・{symbol} 警告：{w}")
        except Exception as e:  # noqa: BLE001 - 單檔失敗要記錄、不能整包中斷
            print(f"  ・{symbol} 失敗：{e}")
            traceback.print_exc()
            errors[symbol] = str(e)
        if i < len(symbols) - 1:
            time.sleep(THROTTLE_SECONDS)

    out = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": (
            "yfinance Ticker.financials（年度損益表）+ Ticker.cashflow（年度現金流量表），"
            "免金鑰。指標定義見本檔案docstring。"
        ),
        "coverage": f"{len(financials_out) - len(errors)}/{len(symbols)} 檔成功"
        if financials_out
        else f"0/{len(symbols)} 檔成功",
        "errors": errors,
        "financials": financials_out,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    print(f"完成：{len(financials_out)}/{len(symbols)} 檔取得資料，{len(errors)} 檔失敗")

    if not financials_out:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
