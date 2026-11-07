# -*- coding: utf-8 -*-
"""ADR 溢價卡：quotes_us × fx.json ÷ ADR 比率，對 quotes_tw，算溢價 %（建置一.3）。

寫成 data/adr_premium.json。純計算腳本，不打任何外部 API——三個輸入檔
（data/quotes_us.json／data/quotes_all_tw.json／data/fx.json）都已經由
quotes.yml 的其他步驟抓好，這裡只做除法，零額外請求，可以安心放進10分鐘
一次的高頻迴圈。

溢價％定義：implied_tw_price = 美股ADR現價(USD) × 美元/台幣匯率 ÷ ADR比率
            premium_pct = (implied_tw_price − 台股現價) ÷ 台股現價 × 100

ADR 比率是固定值（公司股本結構變動才會改，不是每天變的資料），寫死在這裡
並附官方來源，不是憑印象猜的數字（2026-09-10 三來源查證紀錄）：

- TSM（台積電2330）：1 ADS＝5股普通股。
  來源1（SEC EDGAR官方）：CIK 1046179 20-F系列申報
  （https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001046179&type=20-F）。
  來源2：多筆Form 4內部人申報换算一致確認5:1（stocktitan.net彙整之SEC filings）。
  來源3：市場慣例引用（FXBrokerTrust等第三方說明頁）與1997年ADR掛牌以來比率
  未變的公開紀錄一致。
- UMC（聯電2303）：1 ADS＝5股普通股。
  來源1（公司官方）：UMC官方FAQ（https://www.umc.com/en/Html/faqs）揭露
  總ADS數117,228,617對應普通股數586,143,085，586,143,085÷117,228,617≈5。
  來源2（SEC EDGAR官方）：CIK 1033767 20-F系列申報，J.P. Morgan為存託機構。
  來源3：市場資料頁（Morningstar等）一致列為NYSE:UMC對應5股普通股。
- ASX（日月光投控3711，ASE Technology Holding）：1 ADS＝2股普通股。
  來源1（Nasdaq官方）：上市名稱本身即為「American Depositary Shares (each
  representing Two Common Shares)」。
  來源2（SEC EDGAR官方）：CIK 1122411 申報文件（S-8等）一致。
  來源3：Nasdaq市場資料頁（financials/earnings等分頁標題）一致標註。
- CHT（中華電信2412）：1 ADS＝10股普通股。
  來源1（SEC EDGAR官方）：CIK 1132924 歷年20-F申報
  （https://www.sec.gov/Archives/edgar/data/1132924/）一致揭露
  「each ADS represents ten common shares」，JPMorgan Chase Bank為存託機構。
  來源2：第三方新聞頁（ad-hoc-news.de等）轉述一致。
  來源3：2018/2021/2024多個年度20-F封面比率一致，未變動過。

**已知限制誠實揭露**：比率寫死，若未來發生存託比率調整（歷史上部分ADR
確曾發生過比率變更），這裡不會自動反映，需要人工比對官方公告後手動改
常數——SEC沒有一個「即時回傳目前比率」的官方端點，每次重新核對官方申報
文件比每天打一次高成本查詢更符合「取得方式鐵律」。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001 — 沒有時區資料就不判斷錯開（fail open，只少一個旗標）
    _ET = None

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "adr_premium.json"

ADR_RATIOS = {
    "TSM": {
        "tw_code": "2330", "ratio": 5,
        "source": "SEC EDGAR 20-F CIK 1046179；1 ADS＝5股普通股（1997年掛牌以來未變）",
    },
    "UMC": {
        "tw_code": "2303", "ratio": 5,
        "source": "UMC官方FAQ（umc.com/en/Html/faqs）+ SEC EDGAR 20-F CIK 1033767；1 ADS＝5股普通股",
    },
    "ASX": {
        "tw_code": "3711", "ratio": 2,
        "source": "Nasdaq官方上市名稱 + SEC EDGAR CIK 1122411；1 ADS＝2股普通股",
    },
    "CHT": {
        "tw_code": "2412", "ratio": 10,
        "source": "SEC EDGAR 20-F CIK 1132924；1 ADS＝10股普通股",
    },
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pos(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 < v < float("inf")


def _us_quote_date(qt) -> date | None:
    """美股報價時間 → 美東日期。epoch 秒（Finnhub）或 ISO 字串都接受；認不得回 None。"""
    try:
        if isinstance(qt, (int, float)) and not isinstance(qt, bool) and qt > 0:
            if _ET is None:
                return None
            return datetime.fromtimestamp(qt, tz=timezone.utc).astimezone(_ET).date()
        if isinstance(qt, str) and len(qt) >= 10:
            return date.fromisoformat(qt[:10])
    except Exception:  # noqa: BLE001
        return None
    return None


def _tw_trading_lag(tw_date_s, us_date: date | None, calendar: dict):
    """先.一三五-1mi：台股收盤日比「美股報價日（美東）當天或之前最近一個台股交易日」晚幾個台股交易日。

    回傳 (落後交易日數, 應對齊的台股交易日 ISO)；落後 0 回 (0, …)；日曆缺該年份／日期認不得 → (None, None)，
    不判斷（fail open）。台北比美東早 12～13 小時，美東 D 日任何報價時點台股 D 日都已收盤，故同日即對齊。
    """
    try:
        if us_date is None or not tw_date_s:
            return None, None
        tw_d = date.fromisoformat(_norm_date(tw_date_s))  # 先.一三五-1mn：YYYYMMDD 也認得
        tw_cal = (calendar or {}).get("tw") or {}

        def closed_set(y):
            yr = tw_cal.get(str(y))
            if not isinstance(yr, dict) or not isinstance(yr.get("closed"), list):
                return None
            return set(yr["closed"])

        def is_trading(d):
            if d.weekday() >= 5:
                return False
            cs = closed_set(d.year)
            if cs is None:
                raise LookupError(d.year)
            return d.isoformat() not in cs

        target = us_date
        for _ in range(30):
            if is_trading(target):
                break
            target -= timedelta(days=1)
        else:
            return None, None
        if tw_d >= target:
            return 0, target.isoformat()
        lag, d = 0, target
        while d > tw_d and lag < 60:
            if is_trading(d):
                lag += 1
            d -= timedelta(days=1)
        return lag, target.isoformat()
    except Exception:  # noqa: BLE001 — 日曆缺年份或格式不對：不判斷，不擋計算
        return None, None


def _norm_date(v) -> str | None:
    """先.一三五-1mn：日期字串正規化成 ISO（10 月初部分版本台股日期是 YYYYMMDD）；認不得回 None。"""
    try:
        t = str(v or "").strip()
        if len(t) >= 8 and t[:8].isdigit():
            return f"{t[:4]}-{t[4:6]}-{t[6:8]}"
        return date.fromisoformat(t[:10]).isoformat()
    except Exception:  # noqa: BLE001
        return None


def _fx_trading_lag(fx_date_s, tw_date_s, calendar: dict):
    """先.一三五-1mn：匯率日期比台股收盤日落後幾個台股交易日（沿用 _tw_trading_lag）；不判斷 → None。

    央行 FTDOpenData015 台北傍晚（實測約 17:30 後）才有當日值，台股 13:30 收盤後到那之前的班次會拿前一日匯率。
    """
    tw_iso = _norm_date(tw_date_s)
    fx_iso = _norm_date(fx_date_s)
    if not tw_iso or not fx_iso:
        return None
    lag, _ = _tw_trading_lag(fx_iso, date.fromisoformat(tw_iso), calendar)
    return lag


def main():
    quotes_us = load_json(DATA_DIR / "quotes_us.json")
    # 先.八十一-13：台股價改讀 quotes_all_tw.json（全市場盤後收盤，四檔都涵蓋）。原本讀 quotes_tw.json 只涵蓋
    # 少數自選代號，2303／3711 長期顯示「台股報價缺失」；且盤中小檔與美股收盤時點不一致。
    quotes_tw = load_json(DATA_DIR / "quotes_all_tw.json")
    fx = load_json(DATA_DIR / "fx.json")
    calendar = load_json(DATA_DIR / "trading_calendar.json")

    us_quotes = quotes_us.get("quotes", {})
    tw_quotes = quotes_tw.get("quotes", {})
    usd_twd = fx.get("usd_twd", {})
    fx_rate = usd_twd.get("rate")
    fx_date = usd_twd.get("date")

    rows = {}
    errors = []
    for us_ticker, info in ADR_RATIOS.items():
        tw_code = info["tw_code"]
        ratio = info["ratio"]
        us_q = us_quotes.get(us_ticker)
        tw_q = tw_quotes.get(tw_code)
        # 先.一三五-1cf：價格／匯率必須是正有限數——台股當天無成交收盤記 0（no_trade）時原本會除以零整支崩潰。
        if not us_q or not _pos(us_q.get("price")):
            errors.append({"ticker": us_ticker, "reason": "美股報價缺失（data/quotes_us.json 未涵蓋此檔或尚未抓到）"})
            print(f"  ・{us_ticker}: 美股報價缺失")
            continue
        if not tw_q or not _pos(tw_q.get("close")):
            errors.append({"ticker": us_ticker, "reason": f"台股 {tw_code} 報價缺失"})
            print(f"  ・{us_ticker}: 台股 {tw_code} 報價缺失")
            continue
        # 先.一三五-1mg（2026-11-07）：quotes_all_tw 會照常輸出落後股（is_stale=true，例 2024-12-31 的舊列），
        # 不得拿舊台股收盤對新美股價算溢價——落後就不寫 rows（溢價視同 null），原因寫進 errors 給 App 顯示。
        if tw_q.get("is_stale"):
            reason = (f"台股 {tw_code} 收盤落後（資料停在 {tw_q.get('as_of') or tw_q.get('date')}"
                      f"，落後 {tw_q.get('stale_days')} 天），不計算溢價")
            errors.append({"ticker": us_ticker, "reason": reason})
            print(f"  ・{us_ticker}: {reason}")
            continue
        if not _pos(fx_rate):
            errors.append({"ticker": us_ticker, "reason": "匯率缺失（data/fx.json）"})
            print(f"  ・{us_ticker}: 匯率缺失")
            continue
        us_price = us_q["price"]
        tw_price = tw_q["close"]
        implied_tw_price = us_price * fx_rate / ratio
        premium_pct = (implied_tw_price - tw_price) / tw_price * 100
        tw_quote_date = tw_q.get("as_of") or tw_q.get("date")
        lag, tw_expected = _tw_trading_lag(tw_quote_date, _us_quote_date(us_q.get("quote_time")), calendar)
        row = {
            "tw_code": tw_code,
            "ratio": ratio,
            "source": info["source"],
            "us_price": us_price,
            "us_quote_time": us_q.get("quote_time"),
            "tw_price": tw_price,
            "tw_quote_date": tw_quote_date,
            "tw_price_kind": "台股盤後收盤（quotes_all_tw.json）",
            "fx_rate": fx_rate,
            "fx_date": fx_date,
            "implied_tw_price": round(implied_tw_price, 3),
            "premium_pct": round(premium_pct, 3),
        }
        # 先.一三五-1mi：整份 quotes_all_tw 還沒更新到美股報價日對應的台股交易日（10/14、10/28 兩次實例），
        # 溢價照算但標明非同日，App 在 % 後灰字標「台股 MM/DD」。
        if lag:
            row["tw_date_mismatch"] = True
            row["tw_lag_trading_days"] = lag
            row["tw_expected_date"] = tw_expected
            print(f"  ・{us_ticker}: 台股收盤日 {tw_quote_date} 比對齊日 {tw_expected} 晚 {lag} 個台股交易日（非同日）")
        # 先.一三五-1mn：匯率日期早於台股收盤日 ≥1 個台股交易日 → 溢價用的是舊匯率，標旗標，App 在 % 後灰字標「匯率 MM/DD」。
        fx_lag = _fx_trading_lag(fx_date, tw_quote_date, calendar)
        if fx_lag:
            row["fx_date_lag_trading_days"] = fx_lag
            print(f"  ・{us_ticker}: 匯率日期 {fx_date} 比台股收盤日 {tw_quote_date} 晚 {fx_lag} 個台股交易日（舊匯率）")
        rows[us_ticker] = row
        print(f"  ・{us_ticker}: implied={implied_tw_price:.2f} tw={tw_price} premium={premium_pct:.2f}%")

    if not rows:
        # 先.一三五-1cf：四檔全算不出來（輸入讀不到／全缺價）時不覆寫既有檔——上一份每列都帶報價日期與匯率日期，
        # App 照舊顯示有日期的上次結果；原本會用空 rows 蓋掉。quotes.yml 這步 continue-on-error。
        raise SystemExit(f"四檔 ADR 全部算不出溢價——不覆寫既有 {OUT_PATH.name}：{errors}")

    out = {
        "computed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "quotes_us.json × fx.json ÷ ADR比率，對 quotes_all_tw.json（台股盤後收盤）計算溢價（比率來源見各檔ADR_RATIOS/rows.source，三來源查證紀錄見本檔檔頭docstring）",
        "rows": rows,
        "errors": errors,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(rows)}/{len(ADR_RATIOS)} 檔成功" + (f"，缺漏：{errors}" if errors else ""))


if __name__ == "__main__":
    main()
