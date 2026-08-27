# -*- coding: utf-8 -*-
"""抓台股大盤/類股/三大法人/台指期資料，寫成 data/market_tw.json。

2026-08-26 新增（P0-1 架構修正）：App 過去在瀏覽器端直接打 FinMind 抓這些資料，
FinMind 免費層已 402 額度用盡（研究端第79輪已記錄），導致「大盤指數」「類股表現」
「三大法人買賣超」全部顯示連線失敗。改成跟 `fetch_quotes_tw.py` 一樣的模式：
GitHub Actions 排程抓、寫成 JSON、commit 進 repo，App 端只讀檔，不再直接呼叫
任何第三方 API。

資料源（全部官方開放資料，不需要金鑰）：
- 大盤指數/類股表現：TWSE openapi `exchangeReport/MI_INDEX`（一次回傳大盤+
  台灣50+27個TWSE官方分類的類股指數，含漲跌%，實測驗證過）。
- 櫃買（TPEx OTC）指數：TPEx openapi `v1/tpex_index`（歷史日資料，取最後一筆）。
- 台指期：TAIFEX openapi `v1/DailyMarketReportFut`（取 Contract=TX、日盤、近月
  合約那一筆）。
- 三大法人買賣超（全市場加總）：TWSE `rwd/zh/fund/T86`（跟研究端
  `research/twse_t86_client.py` 同一個端點，這裡是獨立、精簡的複製，不跨
  repo/跨目錄 import，維持 GitHub Actions 腳本自成一體的慣例，同
  `fetch_quotes_tw.py`）——**這個端點有反爬蟲封鎖**（研究端已實測記錄在
  `research/twse_t86_client.py`），這支腳本呼叫頻率遠低於研究端的回補腳本
  （這裡一次只抓「今天」一天，不是連續回補歷史），風險低很多，但仍然只抓
  一天不要抓歷史區間，降低觸發封鎖的機會。

排程頻率刻意比 `fetch_quotes_tw.py`低很多（設計上一天跑 1-2 次就夠，不是每
10 分鐘）——大盤指數/類股/法人資料本來就是盤後才會有當日定案數字，也降低
對 T86 端點的呼叫頻率（它有反爬蟲風險，見上）。
"""
from __future__ import annotations

import json
import sys
import time
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "market_tw.json"
TW_TZ = timezone(timedelta(hours=8))

MI_INDEX_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX"
TPEX_INDEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_index"
TAIFEX_FUT_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"  # 上市公司基本資料（含金融股，不含ETF/權證）


def _get_retry(url: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """同 update_stock_financials.py 的 _get_retry()——自成一體複製，不跨檔案
    import（既有慣例）。2026-08-27新增：端點逾時要重試，不能靜靜跳過。
    **刻意不用在T86_URL**：T86有反爬蟲風險（見下方fetch_institutional_aggregate
    docstring），重試可能加重被封鎖的機率，那裡維持單次嘗試。"""
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


def load_tse_company_codes() -> set[str] | None:
    """回傳全部TWSE上市「公司」代號（含金融股，T86/MI_MARGN涵蓋的範圍跟財報
    「一般業」分類不同——金融股有融資融券/三大法人資料，只是財報格式不同，
    2026-08-27修正前這裡錯用「financials已建立的代碼」當篩選門檻，誤把金融股
    的三大法人資料也濾掉了，這裡改用官方公司清單當篩選門檻才正確）。抓不到
    就回傳None，呼叫端應該退回不篩選（寧可讓ETF/權證雜訊進來，也不要誤刪
    真正的股票資料）。"""
    try:
        r = _get_retry(TSE_LIST_URL, timeout=15)
        r.raise_for_status()
        rows = r.json()
        codes = {row.get("公司代號") for row in rows if row.get("公司代號")}
        return codes if codes else None
    except Exception as e:
        print(f"抓上市公司清單失敗（改回不篩選代碼，不影響正確性只影響ETF/權證噪音多寡）：{e}")
        return None

# TWSE MI_INDEX 裡「大盤」跟少數幾個大盤變體指數的名稱，跟其餘 27 個類股指數分開處理。
HEADLINE_NAMES = {"發行量加權股價指數"}


def _num(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except ValueError:
        return None


def fetch_mi_index() -> tuple[dict | None, list[dict]]:
    """回傳 (大盤, 類股清單)。`MI_INDEX` 一次回傳 273 筆，混合大盤/台灣50/公司治理
    等主題式指數跟真正的產業分類指數——只有名稱以「類指數」結尾的才是 TWSE 官方
    28 類產業分類（實測 2026-08-26：37 筆符合，比 App 原本示範資料的 8 大類更完整），
    其餘主題式指數不放進「類股表現」清單，避免混淆。"""
    r = _get_retry(MI_INDEX_URL, timeout=15)
    r.raise_for_status()
    rows = r.json()
    headline = None
    sectors = []
    for row in rows:
        name = row.get("指數")
        close = _num(row.get("收盤指數"))
        chg_pct = _num(row.get("漲跌百分比"))
        sign = -1 if row.get("漲跌") == "-" else 1
        if close is None or not name:
            continue
        item = {"name": name, "close": close, "change_pct": (chg_pct * sign) if chg_pct is not None else None}
        if name in HEADLINE_NAMES:
            headline = item
        elif name.endswith("類指數"):
            sectors.append(item)
    return headline, sectors


def fetch_taiex_sparkline() -> list[float]:
    """MI_INDEX 只給當天單一數字，沒有歷史區間——近20日收盤序列改用 yfinance
    `^TWII`（實測驗證過跟 MI_INDEX 同一天的收盤值一致，例如 2026-08-25 兩邊都是
    45169.46），只用來畫App的sparkline走勢線，headline的close/change_pct仍然
    以MI_INDEX為準（見上面fetch_mi_index），這裡不覆蓋。"""
    h = yf.Ticker("^TWII").history(period="1mo")
    if h.empty:
        return []
    return [round(float(c), 2) for c in h["Close"].tail(20).tolist()]


def fetch_tpex_index() -> dict | None:
    # 已知風險（2026-08-26 本機測試發現，不確定 GitHub Actions Ubuntu runner 是否也
    # 會遇到）：這台 Windows 機器的 Python/OpenSSL 對 TPEx 網站憑證的驗證會噴
    # `CERTIFICATE_VERIFY_FAILED: Missing Subject Key Identifier`（TPEx 憑證本身
    # 疑似缺欄位，不是我們這端設定錯）。main() 已經把每個資料源包在各自的 try/except
    # 裡，這裡失敗只會讓 out["tpex"]=None，不會讓整支腳本連台股大盤/期貨都抓不到，
    # 是設計內的優雅降級，不是需要特別處理的例外。
    r = _get_retry(TPEX_INDEX_URL, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return None
    last, prev = rows[-1], (rows[-2] if len(rows) >= 2 else None)
    close = _num(last.get("Close"))
    change = _num(last.get("Change"))
    prev_close = _num(prev.get("Close")) if prev else None
    change_pct = (change / (close - change) * 100) if (close is not None and change is not None and (close - change)) else None
    # 這個端點本來就回傳歷史區間（見上面docstring），近20日收盤序列直接從同一份
    # 回應取，不需要另外呼叫，用來畫App的sparkline走勢線。
    sparkline = [c for c in (_num(r.get("Close")) for r in rows[-20:]) if c is not None]
    return {"date": last.get("Date"), "close": close, "change": change, "change_pct": change_pct, "sparkline": sparkline}


TAIFEX_CONTRACTS = ("TX", "MTX", "TE", "TF")  # 台指期/小型台指期/電子期/金融期，市場頁「期貨」分頁需要全部四種


def fetch_taifex_contracts() -> dict[str, dict]:
    """一次呼叫涵蓋 TAIFEX_CONTRACTS 全部合約（TAIFEX 這個端點本來就回傳全市場
    所有合約，不是只有 TX，這裡只是從同一份回應多篩幾種代碼，不需要多打幾次
    API）。回傳 {contract_code: {...}}，抓不到的代碼不會出現在結果字典裡。"""
    r = _get_retry(TAIFEX_FUT_URL, timeout=15)
    r.raise_for_status()
    rows = r.json()
    out: dict[str, dict] = {}
    for code in TAIFEX_CONTRACTS:
        code_rows = [row for row in rows if row.get("Contract") == code]
        if not code_rows:
            continue
        # 近月合約：ContractMonth(Week) 字串由小到大排序取最小的（近月）；同一近月裡
        # 優先取日盤（一般）那一筆，盤後(夜盤)那一筆的 SettlementPrice 常是 "NULL"。
        code_rows.sort(key=lambda r: r.get("ContractMonth(Week)", ""))
        front_month = code_rows[0]["ContractMonth(Week)"]
        same_month = [r for r in code_rows if r.get("ContractMonth(Week)") == front_month]
        day_session = [r for r in same_month if "盤後" not in (r.get("TradingSession") or "")]
        chosen = day_session[0] if day_session else same_month[0]
        out[code] = {
            "contract_month": front_month, "last": _num(chosen.get("Last")),
            "change": _num(chosen.get("Change")), "change_pct": _num(chosen.get("%")),
            "settlement_price": _num(chosen.get("SettlementPrice")),
            "trading_session": chosen.get("TradingSession"),
        }
    return out


def fetch_institutional_aggregate(date_str: str) -> tuple[dict, dict | None]:
    """T86 全市場加總（見模組 docstring 的封鎖風險說明，這裡只抓一天）。回傳
    (per_stock字典, 全市場加總dict或None)——per_stock固定回傳{}（不會是None），
    呼叫端不需要另外判斷None。"""
    headers = {
        "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
    }
    r = requests.get(T86_URL, params={"response": "json", "date": date_str, "selectType": "ALL"},
                      headers=headers, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return {}, None
    fields = body["fields"]

    def _idx(*subs):
        for want in subs:
            for i, f in enumerate(fields):
                if want in f:
                    return i
        return None

    i_foreign = _idx("外陸資買賣超股數(不含外資自營商)", "外資買賣超")
    i_trust = _idx("投信買賣超股數")
    i_total = _idx("三大法人買賣超股數合計", "三大法人買賣超股數")
    foreign_sum = trust_sum = total_sum = 0.0
    for row in body["data"]:
        f = _num(row[i_foreign]) if i_foreign is not None else None
        t = _num(row[i_trust]) if i_trust is not None else None
        tot = _num(row[i_total]) if i_total is not None else None
        if f: foreign_sum += f
        if t: trust_sum += t
        if tot: total_sum += tot
    dealer_sum = total_sum - foreign_sum - trust_sum

    # 2026-08-27 新增：順便從同一份T86回應抽出逐股三大法人買賣超，給個股頁「籌碼」
    # 分頁用（見 update_stock_detail_institutional，寫進 data/stock_detail.json）——
    # 不多打一次T86（這個端點有反爬蟲風險，見模組docstring），同一次回應多榨一點用途。
    def _idx_exact(want):
        return fields.index(want) if want in fields else None

    i_code = _idx("證券代號")
    # 用exact match不用_idx()的substring比對——"自營商買賣超股數"是
    # "外資自營商買賣超股數"的substring，會撞到，見上面2026-08-27發現的bug。
    i_foreign_dealer = _idx_exact("外資自營商買賣超股數")
    i_dealer_direct = _idx_exact("自營商買賣超股數")
    per_stock = {}
    if i_code is not None:
        for row in body["data"]:
            code = (row[i_code] or "").strip()
            if not code:
                continue
            fd = _num(row[i_foreign_dealer]) if i_foreign_dealer is not None else None
            f = (_num(row[i_foreign]) or 0) + (fd or 0)
            t = _num(row[i_trust]) or 0
            d = _num(row[i_dealer_direct]) if i_dealer_direct is not None else None
            per_stock[code] = {
                "date": date_str,
                "foreign_lots": round(f / 1000, 1),
                "trust_lots": round(t / 1000, 1),
                "dealer_lots": round(d / 1000, 1) if d is not None else None,
            }

    # 股數轉「億元」需要價格加權，這裡沒有股數×價格的逐股資料，只回報「淨買賣股數」
    # （單位：張，股數/1000），不假裝換算成金額——誠實揭露這個簡化，App 端顯示要標
    # 清楚單位是「淨買賣張數」不是金額。
    return per_stock, {
        "date": date_str,
        "foreign_net_lots": round(foreign_sum / 1000, 1),
        "trust_net_lots": round(trust_sum / 1000, 1),
        "dealer_net_lots": round(dealer_sum / 1000, 1),
        "total_net_lots": round(total_sum / 1000, 1),
    }


def main():
    now_tw = datetime.now(TW_TZ)
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errors": []}

    try:
        headline, sectors = fetch_mi_index()
        out["taiex"] = headline
        out["sectors"] = sectors
    except Exception as e:
        print(f"MI_INDEX 失敗：{e}")
        out["errors"].append(f"taiex/sectors: {e}")

    if out.get("taiex"):
        try:
            out["taiex"]["sparkline"] = fetch_taiex_sparkline()
        except Exception as e:
            print(f"TAIEX sparkline(^TWII) 失敗：{e}")
            out["errors"].append(f"taiex_sparkline: {e}")

    try:
        out["tpex"] = fetch_tpex_index()
    except Exception as e:
        print(f"tpex_index 失敗：{e}")
        out["errors"].append(f"tpex: {e}")

    try:
        contracts = fetch_taifex_contracts()
        out["tx_futures"] = contracts.get("TX")  # 保留舊欄位名給既有呼叫端相容
        out["futures"] = contracts  # 新欄位：TX/MTX/TE/TF 全部
    except Exception as e:
        print(f"TAIFEX 失敗：{e}")
        out["errors"].append(f"futures: {e}")

    per_stock_institutional = {}
    try:
        date_str = now_tw.strftime("%Y%m%d")
        per_stock_institutional, inst = fetch_institutional_aggregate(date_str)
        if inst is None:  # 今天可能還沒收盤定案，退回抓昨天
            prev_str = (now_tw - timedelta(days=1)).strftime("%Y%m%d")
            per_stock_institutional, inst = fetch_institutional_aggregate(prev_str)
        out["institutional"] = inst
        # 「近5日」買賣超需要歷史，但這支腳本一次只抓一天（T86 反爬蟲風險，見模組
        # docstring）——用「讀取上次委進 repo 的 JSON、把今天併進去、去重、只留最近
        # 10 天」的方式，跨多次執行自然累積出歷史，不需要一次補歷史區間。
        history = []
        if OUT_PATH.exists():
            try:
                prior = json.loads(OUT_PATH.read_text(encoding="utf-8"))
                history = prior.get("institutional_history", [])
            except Exception:
                history = []
        if inst:
            history = [h for h in history if h.get("date") != inst["date"]] + [inst]
            history.sort(key=lambda h: h["date"])
            history = history[-10:]
        out["institutional_history"] = history
    except Exception as e:
        print(f"T86 三大法人 失敗：{e}")
        out["errors"].append(f"institutional: {e}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：taiex={out.get('taiex')}，"
          f"sectors={len(out.get('sectors') or [])}筆，tpex={out.get('tpex')}，"
          f"tx={out.get('tx_futures')}，institutional={out.get('institutional')}")

    # 2026-08-27 新增：把同一次T86回應多榨出來的逐股三大法人買賣超，merge進
    # data/stock_detail.json（個股頁「籌碼」分頁用，見STATUS.json的P1項目）。
    # 這裡只動"institutional"這個key，不覆寫update_stock_financials.py/
    # update_margin_maintenance.py各自負責的其他key。
    if per_stock_institutional:
        detail_path = REPO_ROOT / "data" / "stock_detail.json"
        detail = {"meta": {}, "stocks": {}}
        if detail_path.exists():
            try:
                detail = json.loads(detail_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        stocks = detail.setdefault("stocks", {})
        # T86（selectType=ALL）涵蓋所有證券（股票+ETF+權證+可轉債...等），不是只有
        # 股票——實測發現高達17576筆，遠超過台股實際上市公司數。
        # **2026-08-27修正**：原本用「已經存在於stocks的代碼」（由
        # update_stock_financials.py建立）當篩選門檻，結果誤把金融股也濾掉了——
        # 金融股(如2881富邦金)雖然不在t187ap06_L_ci「一般業」財報名單裡，但T86
        # 三大法人資料本來就有涵蓋，不該因為財報名單沒有就連這個也濾掉。改用
        # 官方「上市公司清單」(t187ap03_L，含金融股，不含ETF/權證)當篩選門檻，
        # 這樣setdefault也可以放心新增entry（不會混進ETF/權證）。
        tse_codes = load_tse_company_codes()
        matched = 0
        for code, row in per_stock_institutional.items():
            if tse_codes is not None and code not in tse_codes:
                continue
            entry = stocks.setdefault(code, {})
            prior_hist = (entry.get("institutional") or {}).get("history", [])
            hist = [h for h in prior_hist if h.get("date") != row["date"]] + [row]
            hist.sort(key=lambda h: h["date"])
            hist = hist[-5:]
            entry["institutional"] = {**row, "history": hist}
            matched += 1
        detail.setdefault("meta", {})["institutional_source"] = "TWSE T86（同一次呼叫，跟market_tw.json共用，不額外打）；只保留官方上市公司清單(t187ap03_L)內的代碼，濾掉ETF/權證等非股票證券"
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(f"併入 {detail_path}：T86回應{len(per_stock_institutional)}筆證券，"
              f"跟官方上市公司清單比對後合併 {matched} 檔（其餘為ETF/權證等非股票，已濾掉）")

    # 全部主要區塊都失敗才視為故障；任何一塊成功就算這輪有價值，不要因為 T86
    # 反爬蟲封鎖這種已知風險就讓整支腳本 exit 1 拖累其他已經抓到的資料被 commit。
    if not out.get("taiex") and not out.get("tpex") and not out.get("tx_futures"):
        print("錯誤：大盤/櫃買/期貨全部都沒抓到，判定為真故障")
        sys.exit(1)


if __name__ == "__main__":
    main()
