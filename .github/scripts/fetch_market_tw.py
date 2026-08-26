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
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "market_tw.json"
TW_TZ = timezone(timedelta(hours=8))

MI_INDEX_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX"
TPEX_INDEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_index"
TAIFEX_FUT_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"

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
    r = requests.get(MI_INDEX_URL, timeout=15)
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


def fetch_tpex_index() -> dict | None:
    # 已知風險（2026-08-26 本機測試發現，不確定 GitHub Actions Ubuntu runner 是否也
    # 會遇到）：這台 Windows 機器的 Python/OpenSSL 對 TPEx 網站憑證的驗證會噴
    # `CERTIFICATE_VERIFY_FAILED: Missing Subject Key Identifier`（TPEx 憑證本身
    # 疑似缺欄位，不是我們這端設定錯）。main() 已經把每個資料源包在各自的 try/except
    # 裡，這裡失敗只會讓 out["tpex"]=None，不會讓整支腳本連台股大盤/期貨都抓不到，
    # 是設計內的優雅降級，不是需要特別處理的例外。
    r = requests.get(TPEX_INDEX_URL, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return None
    last, prev = rows[-1], (rows[-2] if len(rows) >= 2 else None)
    close = _num(last.get("Close"))
    change = _num(last.get("Change"))
    prev_close = _num(prev.get("Close")) if prev else None
    change_pct = (change / (close - change) * 100) if (close is not None and change is not None and (close - change)) else None
    return {"date": last.get("Date"), "close": close, "change": change, "change_pct": change_pct}


TAIFEX_CONTRACTS = ("TX", "MTX", "TE", "TF")  # 台指期/小型台指期/電子期/金融期，市場頁「期貨」分頁需要全部四種


def fetch_taifex_contracts() -> dict[str, dict]:
    """一次呼叫涵蓋 TAIFEX_CONTRACTS 全部合約（TAIFEX 這個端點本來就回傳全市場
    所有合約，不是只有 TX，這裡只是從同一份回應多篩幾種代碼，不需要多打幾次
    API）。回傳 {contract_code: {...}}，抓不到的代碼不會出現在結果字典裡。"""
    r = requests.get(TAIFEX_FUT_URL, timeout=15)
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


def fetch_institutional_aggregate(date_str: str) -> dict | None:
    """T86 全市場加總（見模組 docstring 的封鎖風險說明，這裡只抓一天）。"""
    headers = {
        "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
    }
    r = requests.get(T86_URL, params={"response": "json", "date": date_str, "selectType": "ALL"},
                      headers=headers, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return None
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
    # 股數轉「億元」需要價格加權，這裡沒有股數×價格的逐股資料，只回報「淨買賣股數」
    # （單位：張，股數/1000），不假裝換算成金額——誠實揭露這個簡化，App 端顯示要標
    # 清楚單位是「淨買賣張數」不是金額。
    return {
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

    try:
        date_str = now_tw.strftime("%Y%m%d")
        inst = fetch_institutional_aggregate(date_str)
        if inst is None:  # 今天可能還沒收盤定案，退回抓昨天
            prev_str = (now_tw - timedelta(days=1)).strftime("%Y%m%d")
            inst = fetch_institutional_aggregate(prev_str)
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

    # 全部主要區塊都失敗才視為故障；任何一塊成功就算這輪有價值，不要因為 T86
    # 反爬蟲封鎖這種已知風險就讓整支腳本 exit 1 拖累其他已經抓到的資料被 commit。
    if not out.get("taiex") and not out.get("tpex") and not out.get("tx_futures"):
        print("錯誤：大盤/櫃買/期貨全部都沒抓到，判定為真故障")
        sys.exit(1)


if __name__ == "__main__":
    main()
