# -*- coding: utf-8 -*-
"""IBKR (Interactive Brokers) 即時報價擷取（2026-09-01新增，使用者原話：
「接IBKR即時報價進App（只讀，paper，禁止任何下單）」；同日改版：改成
「台股維持TWSE來源，IBKR只抓美股（自選股+四大指數），因為IBKR對這個
paper帳戶只有美股是REALTIME、台股是DELAYED，沒有增益」）。

**2026-09-01改版重點**：拿掉台股（`_qualify_tw_stock`/`DEFAULT_TW_
WATCHLIST`），實測證實TW部分抓到的全是DELAYED（見`git log`裡改版前的
commit紀錄），跟App現有TWSE來源比沒有新增價值，換成美股自選股
（`DEFAULT_US_WATCHLIST`）+原有的四大美股指數。美股股票合約用
`Stock(symbol, 'SMART', 'USD')`（IBKR官方文件標準寫法，讓IBKR自己SMART
路由選最佳交易所，跟指數合約需要指定精確exchange不同）。

**這支腳本只做一件事：連本機IB Gateway，抓報價，寫JSON。不下單、不改單、
不查/改帳戶設定。** 沿用專案既有「本機腳本→JSON→App」模式（跟研究馬拉松
一樣是本機排程觸發，不是`.github/scripts/`那種GitHub Actions排程——
**刻意放在`research/`不放`.github/scripts/`，因為GitHub Actions的runner
連不到使用者本機的IB Gateway**，這支只能在本機跑）。

**三層安全防護（鐵律：只讀報價，絕不下單，見`CLAUDE.md`「安全紅線」）**：
1. 連線時傳`readonly=True`給`ib.connect()`——這是IBKR API本身的唯讀模式，
   即使程式碼哪裡不小心呼叫了下單函式，Gateway端也會直接拒絕。
2. Gateway端使用者要自己勾選「Read-Only API」（見使用者操作提醒，這支
   腳本沒辦法從程式碼強制對方勾選，只能檢查連線後回報的能力旗標）。
3. **連線後第一件事就是檢查帳戶ID是否為paper帳戶**（IBKR慣例：paper
   帳戶ID以"DU"開頭，真實帳戶不會）——**不是paper帳戶就立刻斷線、
   不抓任何報價、不寫任何檔案**，印清楚的警告，這是本腳本自己的安全閥，
   不只是相信使用者有設定對。

**已知限制，誠實揭露**：
- 「自選股」是`index.html`用`localStorage`存的前端狀態（見`CLAUDE.md`
  「自選股存在localStorage」），這支在使用者電腦上跑的Python腳本**沒有
  辦法讀瀏覽器的localStorage**——這是純前端PWA架構的既有取捨（見
  `CLAUDE.md`「重要決策與原因」），不是這次的疏漏。這裡改用
  `DEFAULT_US_WATCHLIST`（幾檔常見大型美股當代表，不是`index.html`裡
  `WL`真正的內容，`WL`是台股/美股混合的單一清單）當代表，
  如果使用者實際自選股不一樣，抓到的標的會對不上——**這點已经先在對話裡
  跟使用者說明，若之後要做到「抓使用者真正的自選股」，需要另外設計一個
  讓Python腳本讀到localStorage內容的機制（例如App端主動把自選股清單也
  寫出一份到repo，但那樣就違背「自選股只存本機」的既有隱私/簡單性決策，
  要使用者自己決定要不要那樣改）**。
- 美股四大指數的IBKR合約（`Index`類型，需要指定正確的exchange）**已用
  使用者本機真實Gateway實測**：S&P500(CBOE)/那斯達克(COMP,NASDAQ)成功
  解析且拿到REALTIME報價；道瓊(INDU,CME)/費城半導體(SOX,PHLX)合約能
  解析成功（有conId）但這個帳戶對這兩個交易所沒有市場數據訂閱權限，
  多次重測結果一致——**這是IBKR帳戶市場數據訂閱層級的問題，不是程式碼
  bug**，`last`會誠實是`None`，App端會自動退回Yahoo Finance顯示。若要
  修，需要使用者自己到IBKR Account Management確認/申請對應的市場數據
  訂閱。
- 美股個股（`DEFAULT_US_WATCHLIST`）用`Stock(symbol,'SMART','USD')`，
  比台股合約更單純（不用指定精確交易所，IBKR SMART路由自動選），但
  **這份預設清單本身還沒有實測過**（2026-09-01改版當下沒有現成的美股
  自選股可以測，只測過美股指數），需要下一次使用者開著Gateway時實際
  跑一次確認每檔都能正確qualify。
- 連不到Gateway（IB Gateway沒開/port不對/防火牆擋）：誠實寫
  `{"connected": false, "error": "..."}`到JSON，不寫任何報價欄位，
  不留舊資料造成App顯示過期數字誤導使用者（沿用`build_picks_ledger.py`
  「查不到就記null，不塞錯資料」同一個原則，這裡更進一步整份JSON都標
  失敗狀態，因為連線本身失敗代表所有報價都不可信）。

**掛排程**：跟`run-marathon-cycle.ps1`/`run-hypothesis-queue-cycle.ps1`
同一個機制，但**這支不透過`claude.exe -p`（不需要LLM判斷，是純機械式
抓資料寫檔案），直接排程呼叫`python research/ibkr_quotes.py`本身**，
盤中每1~5分鐘一次（頻率跟盤中報價敏感度直接相關，不需要像研究馬拉松
那樣30分鐘一次）。排程檔案本身另外建立，不是這支腳本的職責。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ib_async import IB, Index, Stock

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_ibkr.json"
TW_TZ = timezone(timedelta(hours=8))

IB_HOST = "127.0.0.1"
IB_PAPER_PORT = 4002  # IB Gateway paper trading預設port（真實帳戶是4001，TWS另有7496/7497，這支只認4002）
IB_CLIENT_ID = 47     # 任意選定但要唯一，若使用者同時開其他IBKR API連線要避開這個ID
CONNECT_TIMEOUT_SEC = 8
TICK_WAIT_SEC = 3      # 訂閱報價後等多久讓tick資料進來，太短可能抓到還沒更新的初始None

# 美股自選股代表清單（見模組docstring「已知限制」：Python腳本讀不到
# index.html用localStorage存的真實自選股，這裡用5檔常見大型美股當代表）。
DEFAULT_US_WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"]

# 美股四大指數，跟.github/scripts/fetch_market_us.py同一組指數（道瓊/S&P500/那斯達克/費半），
# 但改用IBKR的Index合約定義（symbol, 候選exchange清單——依序嘗試qualifyContracts()，
# 見模組docstring「已知限制」，這份清單需要使用者實測驗證）。
US_INDICES = {
    "^DJI": {"label": "道瓊工業指數", "symbol": "INDU", "candidate_exchanges": ["CME", "CBOT"]},
    "^GSPC": {"label": "S&P 500", "symbol": "SPX", "candidate_exchanges": ["CBOE"]},
    "^IXIC": {"label": "那斯達克綜合指數", "symbol": "COMP", "candidate_exchanges": ["NASDAQ"]},
    "^SOX": {"label": "費城半導體指數", "symbol": "SOX", "candidate_exchanges": ["PHLX"]},
}

MARKET_DATA_TYPE_LABEL = {1: "REALTIME", 2: "FROZEN", 3: "DELAYED", 4: "DELAYED_FROZEN"}

_CURRENT_MKT_DATA_TYPE = 1  # 全域追蹤目前連線設定的市場數據類型，見_request_market_data_with_fallback()


def _write_failure(reason: str) -> None:
    """連線/帳戶檢查失敗時統一走這裡——整份JSON標失敗，不留舊報價、不塞假資料。"""
    payload = {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": False,
        "error": reason,
        "quotes": {},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入失敗狀態到 {OUT_PATH}：{reason}")


def _qualify_us_stock(ib: IB, symbol: str):
    contract = Stock(symbol, "SMART", "USD")
    qualified = ib.qualifyContracts(contract)
    return qualified[0] if qualified else None


def _qualify_us_index(ib: IB, symbol: str, candidate_exchanges: list[str]):
    """依序嘗試候選exchange，第一個能成功qualify的就用——回退鏈設計，
    不是單點依賴任何一個exchange猜測值（見模組docstring「已知限制」）。"""
    for exch in candidate_exchanges:
        contract = Index(symbol, exch)
        try:
            qualified = ib.qualifyContracts(contract)
        except Exception as e:
            print(f"    [qualify] Index({symbol},{exch}) 失敗：{e}")
            continue
        if qualified:
            return qualified[0], exch
    return None, None


def _request_market_data_with_fallback(ib: IB, contract):
    """先試即時(type=1)，等TICK_WAIT_SEC秒沒拿到有效的last就退回延遲數據
    (type=3)重試一次——2026-09-01實測發現這個paper帳戶對所有測試標的都
    回報Error 354「未訂閱即時市場數據，但延遲數據可用」，證實paper帳戶
    預設沒有即時報價權限，這個回退鏈不是理論上的防呆，是實測會用到的
    真實路徑。`reqMarketDataType()`是整個連線的全域設定（不是逐檔請求
    參數），所以第一檔如果就退回延遲，之後的請求會沿用同一個全域設定，
    不用每檔都重新試一次即時（省時間+避免重複觸發同樣的Error 354）。"""
    global _CURRENT_MKT_DATA_TYPE
    ticker = ib.reqMktData(contract, "", False, False)
    ib.sleep(TICK_WAIT_SEC)
    last = ticker.last
    # 排除None/NaN(NaN != NaN)，另外2026-09-01實測發現SOX(PHLX)這個指數合約
    # 即使「有回應」也是回傳0.0這種明顯不是真報價的佔位值——一併排除，不然
    # 會被誤判成「已經拿到資料」而略過退回延遲數據這個補救動作。
    got_data = last is not None and last == last and last > 0
    if not got_data and _CURRENT_MKT_DATA_TYPE == 1:
        ib.cancelMktData(contract)
        ib.reqMarketDataType(3)
        _CURRENT_MKT_DATA_TYPE = 3
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(TICK_WAIT_SEC)
    return ticker


def _extract_quote(ticker) -> dict:
    def _clean(v):
        # ib_async對「沒有值」用NaN不是None，NaN不能直接塞進json.dumps（會產生非法JSON
        # 除非allow_nan=True，這裡刻意统一轉成None，讓前端判斷邏輯統一用null語意）
        if v is None:
            return None
        try:
            if v != v:  # NaN != NaN 恆真，這是判斷NaN的標準寫法，不用額外import math
                return None
        except TypeError:
            return None
        return float(v)

    def _clean_positive(v):
        # IBKR對「沒有值」除了None/NaN，還會用0.0或-1.0這類佔位值（2026-09-01
        # 實測抓到：SOX指數的last回傳0.0、幾乎所有標的的bid/ask在盤後回傳
        # -1.0），這裡統一視為無效——這幾個欄位本質上不可能是零或負值，跟
        # `_clean()`分開處理是因為change_pct等衍生欄位允許正常的None，
        # 不该跟「數值上不合理」的0/-1混為一談。
        v = _clean(v)
        return v if (v is not None and v > 0) else None

    last = _clean_positive(ticker.last)
    close = _clean_positive(ticker.close)
    change_pct = None
    if last is not None and close is not None:
        change_pct = round((last - close) / close * 100.0, 4)
    return {
        "last": last,
        "bid": _clean_positive(ticker.bid),
        "ask": _clean_positive(ticker.ask),
        "close": close,
        "change_pct": change_pct,
        "data_type": MARKET_DATA_TYPE_LABEL.get(ticker.marketDataType, "UNKNOWN"),
    }


def main():
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PAPER_PORT, clientId=IB_CLIENT_ID, timeout=CONNECT_TIMEOUT_SEC, readonly=True)
    except Exception as e:
        _write_failure(f"連線失敗（IB Gateway可能沒開，或port/防火牆設定不對）：{type(e).__name__}: {e}")
        sys.exit(1)

    try:
        accounts = ib.managedAccounts()
        if not accounts:
            _write_failure("連線成功但查不到任何帳戶（managedAccounts()回傳空），不確定是否為paper帳戶，安全起見不抓報價")
            return
        non_paper = [a for a in accounts if not a.startswith("DU")]
        if non_paper:
            _write_failure(
                f"偵測到非paper帳戶（{non_paper}，paper帳戶慣例以'DU'開頭），"
                f"這支腳本鐵律只能連paper，立即中止不抓任何報價——請確認IB Gateway登入的是Paper Trading帳戶"
            )
            return
        print(f"帳戶檢查通過，確認為paper帳戶：{accounts}")

        ib.reqMarketDataType(1)  # 優先要求即時，實際核准的類型由每檔ticker.marketDataType回報

        quotes: dict[str, dict] = {}

        for symbol in DEFAULT_US_WATCHLIST:
            contract = _qualify_us_stock(ib, symbol)
            if contract is None:
                print(f"  [US] {symbol} 合約無法解析（qualifyContracts失敗），跳過")
                continue
            ticker = _request_market_data_with_fallback(ib, contract)
            q = _extract_quote(ticker)
            q["exchange"] = "SMART"
            quotes[symbol] = q
            ib.cancelMktData(contract)
            print(f"  [US] {symbol}: last={q['last']} ({q['data_type']})")

        for us_key, meta in US_INDICES.items():
            contract, used_exchange = _qualify_us_index(ib, meta["symbol"], meta["candidate_exchanges"])
            if contract is None:
                print(f"  [US指數] {meta['label']}({meta['symbol']}) 所有候選exchange都無法解析，跳過"
                      f"（見模組docstring「已知限制」，需要使用者實測後更新candidate_exchanges）")
                continue
            ticker = _request_market_data_with_fallback(ib, contract)
            q = _extract_quote(ticker)
            q["exchange"] = used_exchange
            q["label"] = meta["label"]
            quotes[us_key] = q
            ib.cancelMktData(contract)
            print(f"  [US指數] {meta['label']}: last={q['last']} ({q['data_type']}, exchange={used_exchange})")

        payload = {
            "fetched_at": datetime.now(TW_TZ).isoformat(),
            "connected": True,
            "account_type": "paper",
            "error": None,
            "quotes": quotes,
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"寫入 {OUT_PATH}：{len(quotes)} 檔報價")
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
