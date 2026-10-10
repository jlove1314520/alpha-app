# -*- coding: utf-8 -*-
"""每日排程更新 data/price_history.json 的個股OHLCV歷史，累積式寫回（2026-08-27）。

背景：`research/generate_scores_live.py`（P1，JSON-only上線評分路徑）的
`technical`（技術型態）因子需要per股票的每日價量歷史才能算「站上60日均線×
20/60日均量比」——起始種子由 `research/build_price_history.py` 讀research端
FinMind歷史parquet快取一次回補（2101檔、90個交易日），這支腳本負責之後
每天累積式append「今天的最新一筆」，跟 `update_fundamentals_daily.py`/
`update_stock_financials.py` 同一套「累積式寫回」模式。

資料源（全部官方開放資料，免金鑰）：
- TWSE：`openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`——全市場上市
  股票最新一個交易日的OHLCV快照（含ETF/權證等非股票證券，這裡不特別過濾，
  跟fundamentals.json的做法一致：多存不影響評分，評分端只查有股票資料的代碼）。
- TPEx：`www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes`——上櫃股票對應版本，
  欄位命名不同（`Close`/`Open`/`High`/`Low`/`TradingShares`），語意對應。

**2026-08-27修正（P0 bug，使用者回報）：新增還原權息調整（`adj_close`）**。
背景：`close`是原始收盤價，除息當天會跳空下跌，被
`generate_scores_momentum.py`的`relative_strength`（相對強度/價格動能）因子
誤判成真實下跌，除息季會系統性扭曲題材動能榜排名。修法：每天呼叫TWSE官方
`rwd/zh/exRight/TWT48U`（除權除息預告表，免金鑰，跟T86同一個端點家族），
把新出現的除權息事件累積寫進`data/ex_dividend_events.json`；當某事件的
除權息日<=今天且尚未套用過，用TWSE官方參考價公式（跟`research/adjust.py`
同一條公式，來源改成這個官方端點，不必依賴FinMind——刻意維持「JSON-only
每日排程不呼叫FinMind」的既有架構原則）回溯調整該股在此日期之前所有列的
`adj_close`欄位。`close`本身永遠不變（保留原始值，供其他用途／稽核比對），
新增的`adj_close`才是還原權息後的收盤價，供動能榜等報酬率類因子改用。

**已知限制（實測發現，2026-08-27）**：TWT48U是「預告表」，只回傳當下未來
約5週內的事件，不支援歷史區間查詢——所以還原調整是「事件發生後才回溯套用」
的漸進累積過程，剛上線那幾週涵蓋率會逐漸提高，不是一次全部到位；對這支
腳本啟用之前就已經發生、且已經滾出90天視窗之外的除權息事件無法補回溯
（`adj_close`退回等於`close`，等同未還原，跟修正前狀態相同，不會更糟）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "price_history.json"
SNAPSHOT_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"
EX_DIVIDEND_EVENTS_PATH = REPO_ROOT / "data" / "ex_dividend_events.json"
TW_TZ = timezone(timedelta(hours=8))

STOCK_DAY_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
EX_RIGHT_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT48U"
# 2026-09-30（修.八）：TWSE官方rwd每日收盤行情（含歷史日期），STOCK_DAY_ALL
# OpenAPI檔案是「隔天清晨才更新」的快照（見fetch_twse()診斷），夜間排程時上市
# 永遠比上櫃慢一個交易日；這個端點同日收盤後即有資料，當補洞／備援用。
REDUCTION_URL = "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU"  # 減資恢復買賣參考價（TWSE官方，免金鑰）
REDUCTION_SOURCE = "twse_reduction"
REDUCTION_ANCHOR_TOL = 0.005  # 前一筆close需貼近「停止買賣前收盤價」（0.5%），否則視為定錨失敗
REDUCTION_ALREADY_TOL = 0.01  # 前後兩筆adj/close比值已相差約factor（1%內）＝來源已含此次調整
MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
MI_INDEX_SOURCE = "twse_mi_index"  # 獨立節流名稱，不跟其他腳本的twse_rwd互相拖累
MI_INDEX_MAX_DATES_PER_RUN = 8
MI_INDEX_MIN_ROWS = 800  # 少於此筆數判定為異常回應（正常約1380）
PRICE_HISTORY_DAYS = 90
# 2026-10-10（先.五十八-A2）：Bb-90 自動交易白名單。全市場端點（STOCK_DAY_ALL／tpex_mainboard_quotes）
# 實測會漏掉個別 ETF 的當日列（00646 缺 42 天、00697B 缺 41 天，先.五十七-A2 才回補），
# 這裡在全市場端點缺漏時改用官方單股月資料端點補當日收盤，補不到就寫狀態檔讓 App／推播警告。
WHITELIST_CODES = {"0050": "twse", "00646": "twse", "00697B": "tpex"}
WHITELIST_STATUS_PATH = REPO_ROOT / "data" / "whitelist_price_status.json"
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TPEX_TRADING_STOCK_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
WHITELIST_RECENT_DAYS = 5      # 除了當日，也檢查最近幾個交易日有沒有缺
WHITELIST_SLEEP_SEC = 4.2      # 單股端點每次請求間隔（C:\alpha\CLAUDE.md 頻率上限：TWSE rwd 未公布上限，保守值）

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）。
RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        try:
            return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    state = _load_rate_limit_state()
    src = state["sources"].get(source, {})
    now = time.time()
    blocked_until = src.get("blocked_until")
    if blocked_until and now < blocked_until:
        remain_min = round((blocked_until - now) / 60, 1)
        raise RuntimeError(
            f"{source} 目前處於封鎖冷卻中（還剩約{remain_min}分鐘，"
            f"原因：{src.get('block_reason', '未知')}），依「資料源禮儀」規則拒絕發送請求"
        )
    last = src.get("last_request_at")
    if last and (now - last) < RATE_LIMIT_MIN_INTERVAL_SEC:
        time.sleep(RATE_LIMIT_MIN_INTERVAL_SEC - (now - last))
    src["last_request_at"] = time.time()
    state["sources"][source] = src
    _save_rate_limit_state(state)


import re as _re_secret

_SECRET_KEYS = r"token_tail|token|api_key|apikey|api_token|access_token|secret|password|authorization"
_SECRET_FIELD_RE = _re_secret.compile(
    r'"?(?:' + _SECRET_KEYS + r')"?\s*[:=]\s*(?:"(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^,}\s]*)',
    _re_secret.IGNORECASE,
)
_SECRET_FRAGMENT_RES = (
    _re_secret.compile(r"Bearer\s+\S+", _re_secret.IGNORECASE),
    _re_secret.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}(?:\.[\w-]*)?"),
    _re_secret.compile(r"[A-Za-z0-9_\-]{32,}"),
)


def _redact_secrets(text: str) -> str:
    """寫進會被commit的共用狀態檔（或任何log／例外訊息）前，先過濾 token_tail、
    金鑰欄位（含被 [:200] 截斷到沒有結尾引號的）與疑似金鑰片段（Bearer／JWT／32字元以上
    連續英數）。2026-10-02【先.十-四】：rate_limit_state.json 曾把 FinMind 402 回應的
    token_tail（金鑰末8碼）原文存進 block_reason 並 commit 進公開 repo。失敗一律 fail open
    成「整段遮蔽」，不得讓過濾本身中斷主流程（CLAUDE.md 十二節）。"""
    try:
        out = text or ""
        for rx in _SECRET_FRAGMENT_RES:
            out = rx.sub("[redacted-secret]", out)
        out = _SECRET_FIELD_RE.sub("[redacted-secret]", out)
        return out
    except Exception:  # noqa: BLE001
        return "[redacted-unparseable]"


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    detail = _redact_secrets(detail) if detail else detail
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _get_retry(url: str, source: str, max_retries: int = 3, backoff_base: float = 1.0, **kwargs):
    """同 update_fundamentals_daily.py 的 _get_retry()，自成一體複製（既有慣例）。
    2026-08-28新增`source`參數：發送前先過跨process共用的節流/斷路檢查，
    收到額度/封鎖類狀態碼立刻標記封鎖、不重試（重試只會讓封鎖更久）。"""
    _rate_limit_wait_or_raise(source)
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff_base * (2 ** attempt))
            continue
        if r.status_code in (402, 403, 428, 429):
            _rate_limit_record_block(source, r.status_code, r.text[:200])
            raise RuntimeError(f"{source}回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
        if 500 <= r.status_code < 600 and attempt < max_retries - 1:
            time.sleep(backoff_base * (2 ** attempt))
            continue
        return r
    raise last_err if last_err else RuntimeError(f"GET {url} failed after {max_retries} attempts")


def _num(v):
    if v in (None, "", "-", "N/A"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _roc_date_to_iso(s: str) -> str | None:
    s = str(s).strip()
    if len(s) != 7 or not s.isdigit():
        return None
    year = int(s[:3]) + 1911
    return f"{year}-{s[3:5]}-{s[5:7]}"


def _roc_ymd_to_iso(s: str) -> str | None:
    """解析「115年09月01日」格式（TWT48U除權息預告表專用，跟上面
    `_roc_date_to_iso()`的7位數字格式(STOCK_DAY_ALL用)是不同來源的不同
    格式，故意不合併成一個函式，避免跨格式誤用）。"""
    m = re.match(r"^(\d{2,3})年(\d{2})月(\d{2})日$", str(s).strip())
    if not m:
        return None
    year = int(m.group(1)) + 1911
    return f"{year}-{m.group(2)}-{m.group(3)}"


def fetch_twse() -> dict[str, dict]:
    r = _get_retry(STOCK_DAY_ALL_URL, "twse_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("STOCK_DAY_ALL 回傳非預期格式（可能是無效路徑回傳的HTML，已知地雷）")
    # 2026-09-30（修.八）：診斷輸出，讓CI log直接看得到「上游檔案是不是舊的」，
    # 不用再靠事後推測（Last-Modified是伺服器產生這份靜態JSON的時間）。
    date_dist: dict[str, int] = {}
    for row in rows:
        d = str(row.get("Date", ""))
        date_dist[d] = date_dist.get(d, 0) + 1
    row_0050 = next((row for row in rows if row.get("Code") == "0050"), None)
    print(f"[診斷] STOCK_DAY_ALL：{len(rows)}筆，Last-Modified={r.headers.get('Last-Modified')}，"
          f"Date分布={dict(sorted(date_dist.items()))}，0050={row_0050}")
    out = {}
    for row in rows:
        code = row.get("Code")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("ClosingPrice"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("OpeningPrice")),
            "high": _num(row.get("HighestPrice")),
            "low": _num(row.get("LowestPrice")),
            "close": close,
            "adj_close": close,  # 當天(最新一筆)永遠等於原始收盤，還原調整只回溯套用到更早的日期
            "volume": _num(row.get("TradeVolume")),
            "turnover": _num(row.get("TradeValue")),  # 2026-08-27新增：類股成分股清單功能要用
        }
    return out


def fetch_tpex() -> dict[str, dict]:
    r = _get_retry(TPEX_QUOTES_URL, "tpex_openapi", timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_mainboard_quotes 回傳非預期格式（可能是無效路徑回傳的HTML）")
    out = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        date_iso = _roc_date_to_iso(row.get("Date", ""))
        close = _num(row.get("Close"))
        if not code or not date_iso or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row.get("Open")),
            "high": _num(row.get("High")),
            "low": _num(row.get("Low")),
            "close": close,
            "adj_close": close,  # 同上：當天永遠等於原始收盤
            "volume": _num(row.get("TradingShares")),
            "turnover": _num(row.get("TransactionAmount")),
        }
    return out


def fetch_twse_rwd(date_iso: str) -> dict[str, dict] | None:
    """TWSE官方rwd每日收盤行情（MI_INDEX，type=ALLBUT0999＝全部不含權證等）。
    回傳None＝該日無資料（休市，或當日尚未發布——「很抱歉，沒有符合條件的資料!」）；
    抓取／格式異常則raise，由呼叫端降級成警告（十二節）。輸出格式與fetch_twse()相同。
    2026-09-30（修.八）實測：115-09-24這天1380筆，與STOCK_DAY_ALL逐檔比對，
    開高低收量額在1369檔完全一致，其餘11檔都是當日無成交（兩邊收盤皆空，本來就跳過）。"""
    r = _get_retry(MI_INDEX_URL, MI_INDEX_SOURCE,
                   params={"date": date_iso.replace("-", ""), "type": "ALLBUT0999", "response": "json"},
                   timeout=30)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, dict):
        raise RuntimeError("MI_INDEX 回傳非預期格式（非JSON物件）")
    if body.get("stat") != "OK":
        return None
    tbl = next((t for t in body.get("tables") or [] if "每日收盤行情" in (t.get("title") or "")), None)
    if not tbl or not tbl.get("data"):
        return None
    title_date = _roc_ymd_to_iso((tbl.get("title") or "").split(" ")[0])
    if title_date != date_iso:
        raise RuntimeError(f"MI_INDEX 表頭日期({title_date})與請求日期({date_iso})不符，拒絕採用")
    fields = tbl["fields"]

    def _ix(name):
        if name not in fields:
            raise RuntimeError(f"MI_INDEX 欄位缺少「{name}」：{fields}")
        return fields.index(name)

    i_code, i_vol, i_val = _ix("證券代號"), _ix("成交股數"), _ix("成交金額")
    i_open, i_high, i_low, i_close = _ix("開盤價"), _ix("最高價"), _ix("最低價"), _ix("收盤價")
    out = {}
    for row in tbl["data"]:
        code = str(row[i_code]).strip()
        close = _num(row[i_close])
        if not code or close is None:
            continue
        out[code] = {
            "date": date_iso,
            "open": _num(row[i_open]),
            "high": _num(row[i_high]),
            "low": _num(row[i_low]),
            "close": close,
            "adj_close": close,
            "volume": _num(row[i_vol]),
            "turnover": _num(row[i_val]),
        }
    if len(tbl["data"]) < MI_INDEX_MIN_ROWS:
        raise RuntimeError(f"MI_INDEX {date_iso} 只有{len(tbl['data'])}筆（<{MI_INDEX_MIN_ROWS}），判定回應異常")
    return out


def weekdays_after(start_iso: str | None, end_iso: str) -> list[str]:
    """(start_iso, end_iso] 之間的週一到週五日期（ISO字串）。start為None時只回傳end本身（若為平日）。"""
    end = datetime.strptime(end_iso, "%Y-%m-%d")
    if start_iso is None:
        return [end_iso] if end.weekday() < 5 else []
    d = datetime.strptime(start_iso, "%Y-%m-%d") + timedelta(days=1)
    out = []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def backfill_twse_gap(prices: dict, twse_codes: set, openapi_date: str | None, today_tw: str,
                      errors: list) -> tuple[dict[str, dict[str, dict]], list[str], list[str]]:
    """上市補洞：找出「已存最後上市日」之後、到今天為止的每個平日，OpenAPI那天（openapi_date）
    以外的日子改問MI_INDEX。休市日／尚未發布的日子MI_INDEX回「無資料」＝跳過（官方休市日曆
    holidaySchedule可佐證，例：2026-09-25中秋、09-28教師節）。單輪最多問MI_INDEX_MAX_DATES_PER_RUN天，
    每次請求過既有_get_retry節流（3秒間隔、429/403封鎖2小時）。回傳(各日期資料, 有資料日期, 無資料日期)。
    任何一天抓取失敗只記errors並繼續（fail open，維持既有資料）。"""
    stored_last = max((prices[c][-1]["date"] for c in twse_codes if prices.get(c)), default=None)
    candidates = [d for d in weekdays_after(stored_last, today_tw) if d != openapi_date]
    fetched: dict[str, dict[str, dict]] = {}
    no_data: list[str] = []
    for d in candidates[:MI_INDEX_MAX_DATES_PER_RUN]:
        try:
            rows = fetch_twse_rwd(d)
        except Exception as e:
            print(f"上市補洞(MI_INDEX {d}) 失敗（不中止）：{e}")
            errors.append(f"twse_mi_index_{d}: {e}")
            continue
        if rows is None:
            no_data.append(d)
        else:
            fetched[d] = rows
    if len(candidates) > MI_INDEX_MAX_DATES_PER_RUN:
        print(f"[補洞] 待補平日共{len(candidates)}天，本輪只處理前{MI_INDEX_MAX_DATES_PER_RUN}天，其餘下輪續補")
    print(f"[補洞] 已存上市最後日={stored_last}，OpenAPI日={openapi_date}，今天(台北)={today_tw}；"
          f"MI_INDEX有資料={sorted(fetched)}，無資料(休市或未發布)={no_data}")
    return fetched, sorted(fetched), no_data


def fetch_twse_stock_day_month(code: str, ym: str) -> list[dict]:
    """TWSE 單一個股月資料（ym='YYYY-MM'）。stat 非 OK 回空清單；回傳非 JSON 會拋例外由呼叫端記錄。"""
    url = f"{TWSE_STOCK_DAY_URL}?date={ym.replace('-', '')}01&stockNo={code}&response=json"
    r = _get_retry(url, "twse_rwd_stock_day", timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK":
        return []
    out = []
    for row in j.get("data") or []:   # 日期(民國 y/m/d), 成交股數, 成交金額, 開, 高, 低, 收, 漲跌, 筆數
        y, m, d = str(row[0]).strip().split("/")
        o, h, lo, c = (_num(x) for x in row[3:7])
        if c is None:
            continue
        out.append({"date": f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}", "open": o, "high": h, "low": lo,
                    "close": c, "adj_close": c, "volume": _num(row[1]), "turnover": _num(row[2]),
                    "source": "twse_stock_day"})
    return out


def fetch_tpex_trading_stock_month(code: str, ym: str) -> list[dict]:
    """TPEx 單一個股月資料（量額單位為仟股／仟元，這裡換算成股／元，與 tpex_mainboard_quotes 同單位）。"""
    url = f"{TPEX_TRADING_STOCK_URL}?code={code}&date={ym.replace('-', '/')}/01&response=json"
    r = _get_retry(url, "tpex_www_trading_stock", timeout=20)
    r.raise_for_status()
    t = (r.json().get("tables") or [{}])[0]
    out = []
    for row in t.get("data") or []:
        y, m, d = str(row[0]).strip().split("/")
        o, h, lo, c = (_num(x) for x in row[3:7])
        if c is None:
            continue
        vol, amt = _num(row[1]), _num(row[2])
        out.append({"date": f"{int(y) + 1911:04d}-{int(m):02d}-{int(d):02d}", "open": o, "high": h, "low": lo,
                    "close": c, "adj_close": c,
                    "volume": vol * 1000 if vol is not None else None,
                    "turnover": amt * 1000 if amt is not None else None,
                    "source": "tpex_trading_stock"})
    return out


def fill_whitelist_gaps(prices: dict, target_dates: dict, recent_dates: list[str],
                        fetchers: dict | None = None, sleep_sec: float = WHITELIST_SLEEP_SEC) -> dict:
    """先.五十八-A2：白名單三檔在全市場端點缺漏時，用官方單股月資料補「當日＋最近幾個交易日」的收盤。

    target_dates：{"twse": 上市本輪最新交易日, "tpex": 上櫃本輪最新交易日}（None＝本輪查不到，不檢查當日）。
    recent_dates：最近幾個已確認有開市的交易日（取自大盤代表股的既有歷史），只補缺、不覆蓋既有列。
    回傳狀態 dict（寫進 data/whitelist_price_status.json）。本函式任何例外都只記進狀態，不往外拋
    （CLAUDE.md 十二節：守門員自身失敗只降級成警告）。"""
    fetchers = fetchers or {"twse": fetch_twse_stock_day_month, "tpex": fetch_tpex_trading_stock_month}
    status = {"generated_at": datetime.now(TW_TZ).isoformat(), "target_dates": target_dates,
              "codes": {}, "all_ok": True}
    first_request = True
    for code, mkt in WHITELIST_CODES.items():
        info = {"market": mkt, "filled": [], "missing": [], "errors": []}
        try:
            have = {r.get("date") for r in prices.get(code) or []}
            want = set(recent_dates)
            if target_dates.get(mkt):
                want.add(target_dates[mkt])
            last_have = max(have) if have else None
            # 只檢查「這檔已有資料之後」與「要求範圍內」的日子，避免把上市前的日子當缺漏
            need = sorted(d for d in want if d not in have and (last_have is None or d > min(have)))
            if need:
                months = sorted({d[:7] for d in need})
                got: dict[str, dict] = {}
                for ym in months:
                    if not first_request:
                        time.sleep(sleep_sec)
                    first_request = False
                    try:
                        for row in fetchers[mkt](code, ym):
                            got[row["date"]] = row
                    except Exception as e:  # noqa: BLE001
                        info["errors"].append(f"{ym}: {type(e).__name__}: {_redact_secrets(str(e))[:160]}")
                for d in need:
                    row = got.get(d)
                    if row is None:
                        info["missing"].append(d)
                        continue
                    row = dict(row, fill_note="先.五十八-A2：全市場端點缺漏，改用官方單股端點補")
                    prices[code] = merge_rows(prices.get(code), row)
                    info["filled"].append(d)
            rows = prices.get(code) or []
            info["last_date"] = rows[-1]["date"] if rows else None
            info["last_source"] = (rows[-1].get("source") or "all_market_endpoint") if rows else None
        except Exception as e:  # noqa: BLE001
            info["errors"].append(f"internal: {type(e).__name__}: {e}")
            info.setdefault("last_date", None)
        target = target_dates.get(mkt)
        info["ok"] = (not info["missing"]) and not (target and (info.get("last_date") or "") < target) \
            and not any(x.startswith("internal") for x in info["errors"])
        if not info["ok"]:
            status["all_ok"] = False
        status["codes"][code] = info
        print(f"[白名單補缺] {code}：補 {len(info['filled'])} 天{info['filled'] or ''}，"
              f"仍缺 {info['missing'] or '無'}，最新 {info.get('last_date')}，{'OK' if info['ok'] else '⚠ 警告'}")
    bad = [c for c, i in status["codes"].items() if not i["ok"]]
    status["warning"] = (f"白名單 ETF 價格缺漏：{'、'.join(bad)}（官方單股端點也補不到），"
                         "自動交易的價格新鮮度檢查可能擋單") if bad else None
    return status


def merge_rows(existing: list[dict] | None, latest: dict) -> list[dict]:
    rows = [r for r in (existing or []) if r.get("date") != latest["date"]]
    rows.append(latest)
    rows.sort(key=lambda r: r["date"])
    return rows[-PRICE_HISTORY_DAYS:]


def fetch_ex_dividend_announcements() -> list[dict]:
    """TWSE官方除權除息預告表（免金鑰，跟T86同一個www.twse.com.tw/rwd/家族
    端點）。**已知限制（實測發現，2026-08-27）**：這是「預告表」，只回傳
    當下未來約5週內的事件（實測：今天到約1個月後），不支援歷史區間查詢
    （試過startDate/endDate參數，回傳的107筆資料完全不變）——所以設計成
    「每天呼叫、累積寫進ex_dividend_events.json」，靠時間讓每一檔除權息
    事件至少在發生前幾週內被記錄到一次，不是一次性回補歷史。"""
    r = _get_retry(EX_RIGHT_URL, "twse_exright", params={"response": "json"}, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return []
    fields = body["fields"]

    def _idx(want):
        for i, f in enumerate(fields):
            if want in f:
                return i
        return None

    i_date = _idx("除權除息日期")
    i_code = _idx("股票代號")
    i_stock_ratio = _idx("無償配股率")
    i_rights_ratio = _idx("現金增資配股率")
    i_rights_price = _idx("現金增資認購價")
    i_cash = _idx("現金股利")
    i_type = _idx("除權息")
    if None in (i_date, i_code, i_cash, i_stock_ratio, i_rights_ratio, i_rights_price):
        raise RuntimeError("TWT48U 欄位對應失敗（TWSE可能改版了欄位名稱），已知欄位名找不到")

    out = []
    for row in body["data"]:
        ex_date = _roc_ymd_to_iso(row[i_date])
        code = (row[i_code] or "").strip()
        if not ex_date or not code:
            continue
        cash = _num(row[i_cash]) or 0.0
        stock_ratio = _num(row[i_stock_ratio]) or 0.0
        rights_ratio = _num(row[i_rights_ratio]) or 0.0
        rights_price = _num(row[i_rights_price]) or 0.0
        if cash == 0 and stock_ratio == 0 and rights_ratio == 0:
            continue  # 預告表裡「純股票分割/減資」等其他列，這裡只處理現金股利/股票股利/現增
        out.append({
            "code": code, "ex_date": ex_date,
            "cash": cash, "stock_ratio": stock_ratio,
            "rights_ratio": rights_ratio, "rights_price": rights_price,
            "type": row[i_type] if i_type is not None else None,
        })
    return out


def load_ex_dividend_ledger() -> dict:
    if EX_DIVIDEND_EVENTS_PATH.exists():
        try:
            return json.loads(EX_DIVIDEND_EVENTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "events": {}}


def merge_ex_dividend_events(ledger: dict, announcements: list[dict], today_iso: str) -> int:
    """新事件併入ledger，已存在的(code, ex_date)不覆寫（保留原本的applied
    狀態，不能因為預告表重複回傳同一筆就讓已套用的事件被重置）。回傳新增筆數。"""
    events_by_code = ledger.setdefault("events", {})
    added = 0
    for ann in announcements:
        bucket = events_by_code.setdefault(ann["code"], [])
        if any(e["ex_date"] == ann["ex_date"] for e in bucket):
            continue
        bucket.append({
            "ex_date": ann["ex_date"], "cash": ann["cash"],
            "stock_ratio": ann["stock_ratio"], "rights_ratio": ann["rights_ratio"],
            "rights_price": ann["rights_price"], "type": ann["type"],
            "first_seen": today_iso, "applied": False,
        })
        added += 1
    return added


def _days_between(iso_a: str, iso_b: str) -> int:
    a = datetime.strptime(iso_a, "%Y-%m-%d")
    b = datetime.strptime(iso_b, "%Y-%m-%d")
    return abs((b - a).days)


MAX_PREV_CLOSE_GAP_DAYS = 10  # research端FinMind快取可能對少數股票已經過期很久（實測發現，見下）


def apply_dividend_adjustments(prices: dict, ledger: dict, today_iso: str) -> int:
    """對 ex_date<=today_iso 且尚未applied的事件，用TWSE官方除權息參考價公式
    （跟research/adjust.py同一條公式：ref_price=(前一日收盤-現金股利+現金增資
    認購價×認股比率)/(1+股票股利比率+認股比率)，factor=ref_price/前一日收盤）
    算出調整係數，回溯乘進該股所有date<ex_date列的adj_close。

    重要：factor永遠用「原始close」當前一日收盤的錨點（不是adj_close）——
    這樣不管每天累積套用的順序為何，多筆事件複合起來的結果都跟一次性從最新
    到最舊反向套用（research/adjust.py的做法）等價，見該模組docstring。

    **2026-08-27實測發現的真bug，這裡的守門是修正**：少數股票（例如2420）的
    research端FinMind parquet快取已經停在很久以前（實測發現停在2024-12-31），
    daily排程當天新增的一筆(2026-08-26)緊接在那筆stale資料後面，導致
    `date<ex_date`找到的「前一筆」其實是1年8個月前的舊資料，用它當
    prev_close錨點算出的factor完全不對(算出0.95但實際上下跌是完全不相干的
    兩個價格區間)。修法：前一筆資料的日期離除權息日超過`MAX_PREV_CLOSE_GAP_DAYS`
    天就判定「快取缺口過大、無法安全定錨」，不套用（adj_close維持=close，
    不會比修正前更差），並記錄skip_reason、標記applied=True避免每天重算。
    回傳這輪新套用的事件數。"""
    applied_count = 0
    for code, events in ledger.get("events", {}).items():
        rows = prices.get(code)
        if not rows:
            continue
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        for ev in events:
            if ev.get("applied") or ev["ex_date"] > today_iso:
                continue
            prior = [r for r in rows_sorted if r["date"] < ev["ex_date"]]
            if not prior:
                continue  # 這檔股票的歷史還沒涵蓋到除權息日前一天，等之後累積夠了再套用
            prior_date = prior[-1]["date"]
            if _days_between(prior_date, ev["ex_date"]) > MAX_PREV_CLOSE_GAP_DAYS:
                ev["applied"] = True
                ev["skip_reason"] = (
                    f"前一筆可用資料({prior_date})距離除權息日({ev['ex_date']})"
                    f"超過{MAX_PREV_CLOSE_GAP_DAYS}天，research端FinMind快取對這檔"
                    "股票可能已經過期太久，無法安全定錨調整係數，不套用。"
                )
                continue
            prev_close = prior[-1].get("close")
            if prev_close in (None, 0):
                continue
            numerator = prev_close - ev["cash"] + ev["rights_price"] * ev["rights_ratio"]
            denominator = 1 + ev["stock_ratio"] + ev["rights_ratio"]
            if denominator <= 0 or numerator <= 0:
                ev["applied"] = True
                ev["skip_reason"] = "numerator/denominator 非正值，判定資料異常，不套用"
                continue
            factor = (numerator / denominator) / prev_close
            for r in rows:
                if r["date"] < ev["ex_date"]:
                    base = r.get("adj_close")
                    if base is None:
                        base = r.get("close")
                    if base is not None:
                        r["adj_close"] = base * factor
            ev["applied"] = True
            ev["factor_applied"] = factor
            applied_count += 1
    return applied_count


def fetch_capital_reductions(today_iso: str) -> list[dict]:
    """TWSE官方減資恢復買賣參考價表（rwd/zh/reducation/TWTAUU，免金鑰，支援
    startDate/endDate區間查詢，實測2026-09-30）。每日抓「今天前120天～後60天」，
    已知參考價的事件才回傳（未來事件參考價欄位為「-」，等公布後下一輪才會進來）。
    調整係數=恢復買賣參考價/停止買賣前收盤價（彌補虧損/退還股款/現金減資皆同一式，
    與research/adjust.py對TaiwanStockCapitalReductionReferencePrice的用法一致）。
    **已知範圍**：只涵蓋上市（TWSE）；上櫃（TPEx）swagger 225個端點中沒有對應的
    減資參考價表（2026-09-30查證），上櫃減資由下一輪的異常跳空稽核列出、不在此調整。"""
    today = datetime.strptime(today_iso, "%Y-%m-%d")
    params = {"response": "json",
              "startDate": (today - timedelta(days=120)).strftime("%Y%m%d"),
              "endDate": (today + timedelta(days=60)).strftime("%Y%m%d")}
    r = _get_retry(REDUCTION_URL, REDUCTION_SOURCE, params=params, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return []
    fields = body["fields"]

    def _idx(want):
        for i, f in enumerate(fields):
            if want in f:
                return i
        return None

    i_date, i_code = _idx("恢復買賣日期"), _idx("股票代號")
    i_pre, i_ref, i_why = _idx("停止買賣前收盤價"), _idx("恢復買賣參考價"), _idx("減資原因")
    if None in (i_date, i_code, i_pre, i_ref):
        raise RuntimeError("TWTAUU 欄位對應失敗（TWSE可能改版了欄位名稱）")
    out = []
    for row in body["data"]:
        m = re.match(r"^(\d{2,3})/(\d{2})/(\d{2})$", str(row[i_date]).strip())
        code = (row[i_code] or "").strip()
        pre, ref = _num(row[i_pre]), _num(row[i_ref])
        if not (m and code and pre and ref and pre > 0 and ref > 0):
            continue
        out.append({"code": code, "resume_date": f"{int(m.group(1)) + 1911}-{m.group(2)}-{m.group(3)}",
                    "pre_close": pre, "ref_price": ref,
                    "reason": row[i_why] if i_why is not None else None})
    return out


def merge_reductions(ledger: dict, items: list[dict], today_iso: str) -> int:
    bucket_all = ledger.setdefault("reductions", {})
    added = 0
    for it in items:
        bucket = bucket_all.setdefault(it["code"], [])
        if any(e["resume_date"] == it["resume_date"] for e in bucket):
            continue
        bucket.append({**it, "first_seen": today_iso, "applied": False})
        added += 1
    return added


def apply_reduction_adjustments(prices: dict, ledger: dict, today_iso: str) -> int:
    """對 resume_date<=today_iso 且未處理的減資事件，把date<resume_date的列的
    adj_close乘上factor=ref_price/pre_close。三道守門（任一不過就不套用並記
    skip_reason，adj_close維持原狀，不會比修正前更差）：
    1. 定錨：resume_date前一筆的close必須貼近pre_close（REDUCTION_ANCHOR_TOL），
       擋掉快取缺口（例如停在2024-12-31的股票）；
    2. 冪等：resume_date當天或之後第一筆若存在，且前一筆adj/close÷該筆adj/close
       已約等於factor，代表來源（research端還原）已含此次調整，不重複乘；
    3. factor必須為正有限值。
    事件在資料窗內尚無前一筆（新上市/歷史不足）時不標applied，等資料累積。"""
    applied = 0
    for code, events in ledger.get("reductions", {}).items():
        rows = prices.get(code)
        if not rows:
            continue
        rows_sorted = sorted(rows, key=lambda r: r["date"])
        for ev in events:
            if ev.get("applied") or ev["resume_date"] > today_iso:
                continue
            prior = [r for r in rows_sorted if r["date"] < ev["resume_date"]]
            if not prior:
                continue
            anchor = prior[-1]
            factor = ev["ref_price"] / ev["pre_close"]
            if anchor.get("close") in (None, 0) or abs(anchor["close"] / ev["pre_close"] - 1) > REDUCTION_ANCHOR_TOL:
                ev["applied"] = True
                ev["skip_reason"] = (f"定錨失敗：前一筆({anchor['date']})close={anchor.get('close')}"
                                     f"與停止買賣前收盤價{ev['pre_close']}不符，快取缺口或資料異常，不套用")
                continue
            post = [r for r in rows_sorted if r["date"] >= ev["resume_date"]]
            if post and post[0].get("close") and anchor.get("adj_close") and post[0].get("adj_close"):
                ratio = (anchor["adj_close"] / anchor["close"]) / (post[0]["adj_close"] / post[0]["close"])
                if abs(ratio / factor - 1) <= REDUCTION_ALREADY_TOL:
                    ev["applied"] = True
                    ev["skip_reason"] = "來源adj_close已含此次減資調整（前後比值≈factor），不重複套用"
                    continue
            if not (factor > 0 and factor == factor and factor != float("inf")):
                ev["applied"] = True
                ev["skip_reason"] = "factor非正有限值，資料異常，不套用"
                continue
            for r in rows:
                if r["date"] < ev["resume_date"]:
                    base = r.get("adj_close")
                    if base is None:
                        base = r.get("close")
                    if base is not None:
                        r["adj_close"] = base * factor
            ev["applied"] = True
            ev["factor_applied"] = factor
            applied += 1
    return applied


def main():
    if not OUT_PATH.exists():
        print(f"錯誤：{OUT_PATH} 不存在——這支腳本設計上只做累積更新，"
              "第一次的完整快照要用 research/build_price_history.py 手動產生並 commit。")
        raise SystemExit(1)

    payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    prices = payload.setdefault("prices", {})

    errors = []
    twse_updated = tpex_updated = 0

    # 2026-08-27新增：除權息回溯調整必須在「今天的原始收盤」merge進prices之前
    # 做——這樣factor的錨點(prev_close)才會是「昨天」已經存好的收盤，不會被
    # 今天還沒merge進去的資料影響（today_iso用twse抓到的實際交易日期，抓失敗
    # 才退回now()，處理假日補跑等邊界情況）。
    ex_div_applied = 0
    ex_div_added = 0
    twse = {}
    today_tw = datetime.now(TW_TZ).strftime("%Y-%m-%d")
    openapi_date = None
    try:
        twse = fetch_twse()
        openapi_date = next(iter(twse.values()))["date"] if twse else None
    except Exception as e:
        print(f"價量(TWSE OpenAPI) 抓取失敗（改靠MI_INDEX補洞／備援）：{e}")
        errors.append(f"price_twse: {e}")

    # 2026-09-30（修.八）：STOCK_DAY_ALL是隔天清晨才更新的快照，夜間排程時上市比上櫃
    # 慢一個交易日；另外若排程漏跑或OpenAPI落後多日，這裡用官方MI_INDEX把「已存最後上市日」
    # 之後的交易日補齊（休市日無資料自動跳過）。OpenAPI整個失敗時，用0050當上市代表找已存最後日。
    twse_gap: dict[str, dict[str, dict]] = {}
    twse_gap_dates: list[str] = []
    twse_no_data_dates: list[str] = []
    try:
        gap_codes = set(twse) if twse else ({"0050"} if prices.get("0050") else set())
        if gap_codes:
            twse_gap, twse_gap_dates, twse_no_data_dates = backfill_twse_gap(
                prices, gap_codes, openapi_date, today_tw, errors)
    except Exception as e:
        print(f"上市補洞整體失敗（不中止，維持既有資料）：{e}")
        errors.append(f"twse_gap_backfill: {e}")

    # 上市各日資料先全部merge進prices（含補洞的日期），再處理除權息——這樣補洞日期(<除權息日)
    # 的列也會被回溯調整到；除權息日當天及之後的列不受影響（factor只乘進date<ex_date的列）。
    for d in sorted(twse_gap):
        for code, latest in twse_gap[d].items():
            prices[code] = merge_rows(prices.get(code), latest)
    if twse:
        for code, latest in twse.items():
            prices[code] = merge_rows(prices.get(code), latest)
        twse_updated = len(twse)

    # 已存最後上市日也算「查得到資料的日子」：OpenAPI落後(T+1)、且當天MI_INDEX尚未發布時，
    # 前一輪已補好的日期不在本輪twse_gap_dates裡，不納入會讓自我測試誤判FAIL（2026-09-30實測）。
    stored_last_twse = max((prices[c][-1]["date"] for c in (set(twse) or {"0050"}) if prices.get(c)), default=None)
    twse_dates_with_data = sorted(set(twse_gap_dates) | ({openapi_date} if openapi_date else set())
                                  | ({stored_last_twse} if stored_last_twse else set()))
    twse_latest_date = twse_dates_with_data[-1] if twse_dates_with_data else None
    today_iso = twse_latest_date or today_tw

    # 2026-09-17（總司令裁示【稽核.四.1】先封鎖，再修）：twse/tpex是兩個獨立
    # 請求，openapi.twse.com.tw的STOCK_DAY_ALL實測會在台北23:10仍回前一個
    # 交易日（發布時間比想像中晚），tpex_mainboard_quotes卻已經是當天——
    # 兩邊payload日期對不上時，若照舊直接merge，下游（quotes_all_tw.json
    # 現價快照／sparklines.json）會把「昨天的收盤」當「今天的現價」顯示，
    # 使用者看不出這個落差。這裡只負責偵測並把兩邊各自的payload日期記進
    # meta，供下游決定要不要相信；不在這裡猜「應該用哪一天」或硬改資料，
    # 那是下游依落後與否各自決定要不要輸出現價的事。twse_payload_date取自
    # 上面已經抓到的today_iso（twse抓取失敗時為None，代表這次比對做不了）。
    twse_payload_date = twse_latest_date

    try:
        ledger = load_ex_dividend_ledger()
        announcements = fetch_ex_dividend_announcements()
        ex_div_added = merge_ex_dividend_events(ledger, announcements, today_iso)
        ex_div_applied = apply_dividend_adjustments(prices, ledger, today_iso)
        ledger.setdefault("meta", {})
        ledger["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
        ledger["meta"]["last_fetch_count"] = len(announcements)
        EX_DIVIDEND_EVENTS_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    except Exception as e:
        print(f"除權息預告表(TWT48U) 更新失敗（不影響價量本身，adj_close退回等於close）：{e}")
        errors.append(f"ex_dividend: {e}")

    reductions_added = reductions_applied = 0
    try:
        ledger = load_ex_dividend_ledger()
        reductions_added = merge_reductions(ledger, fetch_capital_reductions(today_iso), today_iso)
        reductions_applied = apply_reduction_adjustments(prices, ledger, today_iso)
        ledger.setdefault("meta", {})["reductions_generated_at"] = datetime.now(TW_TZ).isoformat()
        EX_DIVIDEND_EVENTS_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    except Exception as e:
        print(f"減資參考價表(TWTAUU) 更新失敗（不影響價量本身，減資調整略過）：{e}")
        errors.append(f"capital_reduction: {e}")

    tpex_payload_date = None
    try:
        tpex = fetch_tpex()
        tpex_payload_date = next(iter(tpex.values()))["date"] if tpex else None
        for code, latest in tpex.items():
            prices[code] = merge_rows(prices.get(code), latest)
        tpex_updated = len(tpex)
    except Exception as e:
        print(f"價量(TPEx) 更新失敗：{e}")
        errors.append(f"price_tpex: {e}")

    # 2026-09-17（總司令裁示【稽核.四.1】）：兩邊payload都抓到才能比較；任一邊
    # 失敗（本輪errors已有記錄）就不做這個比較，避免用「抓不到」誤判成「日期
    # 不同」。相等或任一邊缺席都清掉舊的警告——警告只反映「這一輪」的狀態，
    # 不該讓上一輪的警告卡住不放（那樣下游會一直以為在停擺）。
    if twse_payload_date and tpex_payload_date and twse_payload_date != tpex_payload_date:
        d1 = datetime.strptime(twse_payload_date, "%Y-%m-%d")
        d2 = datetime.strptime(tpex_payload_date, "%Y-%m-%d")
        mixed_date_warning = {
            "twse_date": twse_payload_date,
            "tpex_date": tpex_payload_date,
            "delta_days": abs((d2 - d1).days),
        }
        print(f"⚠ 混日期：TWSE payload日期={twse_payload_date}，TPEx payload日期={tpex_payload_date}"
              f"（差{mixed_date_warning['delta_days']}天）——下游build_sparklines.py/本腳本自己的"
              "quotes_all_tw.json快照會對落後的那一邊停止輸出現價")
    else:
        mixed_date_warning = None

    # 2026-10-10（先.五十八-A2）：白名單三檔補缺。整段 fail open，失敗只記警告（十二節）。
    whitelist_status = None
    try:
        ref = [r["date"] for r in (prices.get("2330") or [])[-WHITELIST_RECENT_DAYS:]]
        whitelist_status = fill_whitelist_gaps(
            prices, {"twse": twse_latest_date, "tpex": tpex_payload_date or twse_latest_date}, ref)
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 白名單補缺整體失敗（不中止）：{e}")
        errors.append(f"whitelist_fill: {e}")
        whitelist_status = {"generated_at": datetime.now(TW_TZ).isoformat(), "all_ok": False, "codes": {},
                            "warning": f"白名單 ETF 價格檢查本身失敗：{type(e).__name__}（無法確認三檔是否最新）"}
    try:
        WHITELIST_STATUS_PATH.write_text(json.dumps(whitelist_status, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 寫 whitelist_price_status.json 失敗（不中止）：{e}")

    payload.setdefault("meta", {})
    payload["meta"]["generated_at"] = datetime.now(TW_TZ).isoformat()
    payload["meta"]["source"] = "TWSE STOCK_DAY_ALL（上市）+ TPEx tpex_mainboard_quotes（上櫃）每日累積式寫回；adj_close由TWSE TWT48U除權息事件回溯調整；起始種子=research/build_price_history.py（FinMind快取）"  # 2026-09-03（P0三-三.3）
    payload["meta"]["twse_updated_count"] = twse_updated
    payload["meta"]["tpex_updated_count"] = tpex_updated
    payload["meta"]["errors"] = errors
    payload["meta"]["ex_dividend_events_added"] = ex_div_added
    payload["meta"]["ex_dividend_events_applied"] = ex_div_applied
    payload["meta"]["capital_reduction_events_added"] = reductions_added
    payload["meta"]["capital_reduction_events_applied"] = reductions_applied
    payload["meta"]["mixed_date_warning"] = mixed_date_warning
    payload["meta"]["twse_openapi_date"] = openapi_date
    payload["meta"]["twse_gap_filled_dates"] = twse_gap_dates
    payload["meta"]["twse_no_data_dates"] = twse_no_data_dates
    payload["meta"]["whitelist_fill"] = whitelist_status
    # 自我測試（修.八）：0050最新日期必須等於本輪查得到資料的最近一個上市交易日。
    # 只記錄結果、不中止（守門員自身失敗不得拖垮主流程，十二節）；同時印出讓CI log可見。
    row_0050 = prices.get("0050") or []
    actual_0050 = row_0050[-1]["date"] if row_0050 else None
    check_ok = bool(twse_latest_date) and actual_0050 == twse_latest_date
    payload["meta"]["twse_latest_check"] = {
        "expected_latest_trading_day": twse_latest_date, "actual_0050_last_date": actual_0050, "ok": check_ok}
    print(f"[自我測試] 0050最新日期={actual_0050}，本輪查得到的最近上市交易日={twse_latest_date}："
          f"{'PASS' if check_ok else 'FAIL'}")
    if not check_ok:
        errors.append(f"self_check_0050_latest: 0050最新日期={actual_0050} != 最近上市交易日={twse_latest_date}")
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：TWSE {twse_updated} 檔+TPEx {tpex_updated} 檔（合計 {len(prices)} 檔有資料），"
          f"除權息事件本輪新增 {ex_div_added} 筆、套用回溯調整 {ex_div_applied} 筆")
    if errors:
        print(f"部分失敗（不中止，維持既有資料）：{errors}")

    # 2026-08-27新增：類股成分股清單功能（B4）需要「全市場（不只自選股）最新
    # 一天的收盤價/漲跌%/成交值」，但price_history.json整份90天歷史太大
    # （32MB+），不適合每次client-side抓整份只為了取最新一天。這裡從剛更新
    # 的prices取每檔最後兩筆算出這個輕量快照，單獨寫一個小檔。
    #
    # 2026-09-17（總司令裁示【稽核.四.1修正版】(a)顯示層）：上一版在這裡把
    # 落後大盤最新日期的股票整檔排除，實測後果是2839檔裡1845檔（58%）在App
    # 上完全空白（含2330/2317/2454/2412/2882/1301），總司令親自更正：
    # 「一個標著『09-15收盤』的舊價，比一片空白有用得多；藏起來不叫誠實」。
    # 改成全部照常輸出，只是落後的那些額外標is_stale/stale_days/as_of，
    # 讓下游（index.html）決定要不要顯示、怎麼顯示——這裡不再做「要不要給」
    # 的判斷，只誠實標記「這是不是最新的」。change_pct在is_stale時仍照算
    # （是這檔股票自己前後兩個交易日的真實漲跌，不是跟別檔比出來的假訊號），
    # 是否顯示交給前端；但quotes_all_tw.json本身的欄位語意保持單純，change_pct
    # 一律照算，is_stale旗標另外標，不混在一起。
    max_date = max((rows[-1]["date"] for rows in prices.values() if rows), default=None)
    snapshot = {}
    stale_count = 0
    for code, rows in prices.items():
        if not rows:
            continue
        last = rows[-1]
        is_stale = bool(max_date and last["date"] < max_date)
        prev = rows[-2] if len(rows) >= 2 else None
        change_pct = None
        if prev and prev.get("close") not in (None, 0):
            change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100, 2)
        entry = {
            "date": last["date"], "as_of": last["date"], "close": last["close"],
            "change_pct": change_pct, "turnover": last.get("turnover"),
        }
        if is_stale:
            stale_count += 1
            entry["is_stale"] = True
            d_max = datetime.strptime(max_date, "%Y-%m-%d")
            d_last = datetime.strptime(last["date"], "%Y-%m-%d")
            entry["stale_days"] = (d_max - d_last).days
        snapshot[code] = entry
    # 2026-09-06（實測.一.2）：top-level 補 fetched_at 與 source。
    # App 端的報價回退鏈把這一份當第三層，要判斷「這個價格有多舊」就得知道抓取時間；
    # 其他報價檔（quotes_tw.json / quotes_us.json）的欄位名就是 fetched_at/source，
    # 這裡跟著用同一組名字，前端才不用為每個檔案各寫一套讀法。meta 保留不動，
    # 既有讀 meta 的程式（build_picks_ledger.py 等）不受影響。
    now_iso = datetime.now(TW_TZ).isoformat()
    src_label = "TWSE STOCK_DAY_ALL + TPEx tpex_mainboard_quotes（經 data/price_history.json 衍生）"
    print(f"quotes_all_tw快照：{len(snapshot)} 檔輸出現價（含{stale_count}檔標is_stale，"
          f"最後一筆日期落後大盤最新日期{max_date}）")
    SNAPSHOT_PATH.write_text(json.dumps({
        "fetched_at": now_iso,
        "source": src_label,
        "meta": {"generated_at": datetime.now(TW_TZ).isoformat(),
                 "source": "從data/price_history.json衍生（TWSE STOCK_DAY_ALL + TPEx tpex_mainboard_quotes）",  # 2026-09-03（P0三-三.3）
                 "note": "從data/price_history.json每檔最後兩筆算出的輕量快照（收盤/漲跌%/成交值），"
                         "供類股成分股清單等只需要「今天」資料的功能用，不用載入整份90天歷史。",
                 "data_asof": max_date,
                 "stale_count": stale_count,
                 "stale_note": "2026-09-17（稽核.四.1修正版）：不再排除落後股票，全部照常輸出，"
                               "改標每筆的as_of/is_stale/stale_days，前端決定顯示方式，"
                               "不得把is_stale=true的close當『現價』顯示。"},
        "quotes": snapshot,
    }, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"寫入 {SNAPSHOT_PATH}：{len(snapshot)} 檔輕量快照")


if __name__ == "__main__":
    main()
