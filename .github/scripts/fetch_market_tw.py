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
# 2026-08-27新增（P1-新，使用者要求補齊TPEx上櫃三大法人缺口）：TPEx官方對應
# 端點，全市場單日快照（免金鑰，不像T86_URL有反爬蟲風險）。跟fundamentals.json
# 的TPEx補充（fetch_ratios_tpex()/fetch_revenue_tpex()）同一個慣例：不額外
# 過濾ETF/權證（那份也沒過濾），這裡的取捨一致，已知限制寫進STATUS.json。
TPEX_INSTITUTIONAL_URL = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"

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
    """同 update_stock_financials.py 的 _get_retry()——自成一體複製，不跨檔案
    import（既有慣例）。2026-08-27新增：端點逾時要重試，不能靜靜跳過。
    **刻意不用在T86_URL**：T86有反爬蟲風險（見下方fetch_institutional_aggregate
    docstring），重試可能加重被封鎖的機率，那裡維持單次嘗試（但一樣會過
    2026-08-28新增的跨process節流/斷路檢查，見`fetch_institutional_aggregate()`
    內直接呼叫`_rate_limit_wait_or_raise()`的地方）。"""
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


def load_tse_company_codes() -> set[str] | None:
    """回傳全部TWSE上市「公司」代號（含金融股，T86/MI_MARGN涵蓋的範圍跟財報
    「一般業」分類不同——金融股有融資融券/三大法人資料，只是財報格式不同，
    2026-08-27修正前這裡錯用「financials已建立的代碼」當篩選門檻，誤把金融股
    的三大法人資料也濾掉了，這裡改用官方公司清單當篩選門檻才正確）。抓不到
    就回傳None，呼叫端應該退回不篩選（寧可讓ETF/權證雜訊進來，也不要誤刪
    真正的股票資料）。"""
    try:
        r = _get_retry(TSE_LIST_URL, "twse_openapi", timeout=15)
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
    r = _get_retry(MI_INDEX_URL, "twse_openapi", timeout=15)
    r.raise_for_status()
    rows = r.json()
    headline = None
    sectors = []
    for row in rows:
        name = row.get("指數")
        close = _num(row.get("收盤指數"))
        chg_pct = _num(row.get("漲跌百分比"))
        # 2026-10-12 先.八十-1 修正：MI_INDEX 的「漲跌百分比」本身已帶正負號（實測 -0.99），舊寫法再乘一次
        # 「漲跌」欄的 -1，跌變漲（加權 -0.99% 顯示成 +0.99%、類股全部變非負）。改為：正負號只取「漲跌」欄
        # （'+'／'-'），幅度取百分比絕對值；漲跌欄缺漏時才退回百分比本身的正負號。
        mark = (row.get("漲跌") or "").strip()
        if chg_pct is None:
            signed = None
        elif mark == "-":
            signed = -abs(chg_pct)
        elif mark == "+":
            signed = abs(chg_pct)
        else:
            signed = chg_pct
        if close is None or not name:
            continue
        item = {"name": name, "close": close, "change_pct": signed, "data_date": _roc_to_iso(row.get("日期"))}
        if name in HEADLINE_NAMES:
            headline = item
        elif name.endswith("類指數"):
            sectors.append(item)
    return headline, sectors


# ───────── 先.八十一-1（2026-10-13）資料日核對與備援 ─────────
# 根因（實測）：10/13 04:03 這輪抓到的 TWSE openapi MI_INDEX 與 TAIFEX openapi 都還是 10/08（openapi 隔日早上才刷新），
# 走勢線用的 yfinance ^TWII 到 10/13 早上仍缺 10/12。price_history（STOCK_DAY_ALL）卻已有 10/12。
# 做法：①每筆標 data_date ②資料日落後「應有的最後交易日」時，改問證交所 rwd MI_INDEX（帶日期參數、官方）
# ③走勢線改以證交所 FMTQIK（官方逐月）為主、yfinance 為備援 ④仍落後就寫 stale_note，App 顯示「大盤資料停在 MM/DD」。
TWSE_RWD_MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TWSE_FMTQIK = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
PUBLISH_HOUR = 15  # 收盤資料當天 15:00 後才算「應該有」


def _roc_to_iso(s: str | None) -> str | None:
    s = str(s or "").strip().replace("/", "")
    if len(s) == 7 and s.isdigit():
        return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None


def expected_last_trading_day(now_tw: datetime) -> str | None:
    """官方休市日以外的最近一個交易日（今天 15:00 前不算今天）。日曆讀取失敗回 None（不做比對，不擋流程）。"""
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import backfill_price_history_gaps as B  # 同一份官方休市日判定（本機快取優先，雲端改問 TWSE holidaySchedule）
        d = now_tw.date()
        if now_tw.hour < PUBLISH_HOUR:
            d -= timedelta(days=1)
        for _ in range(15):
            if d.weekday() < 5 and d.isoformat() not in B.closed_days(d.year):
                return d.isoformat()
            d -= timedelta(days=1)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 交易日曆判定失敗（不做資料日比對）：{e}")
    return None


def _sign_from_html(v) -> int:
    t = str(v or "")
    return -1 if "-" in t else (1 if "+" in t else 0)


def fetch_mi_index_rwd(date_iso: str) -> tuple[dict | None, list[dict]]:
    """證交所 rwd MI_INDEX（type=IND，帶日期）——openapi 落後時的官方備援。正負號取「漲跌(+/-)」欄、幅度取百分比絕對值。"""
    r = _get_retry(TWSE_RWD_MI_INDEX, "twse_rwd", params={"date": date_iso.replace("-", ""), "type": "IND", "response": "json"}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("stat") != "OK" or _roc_to_iso(j.get("date")) != date_iso:
        return None, []
    tbl = next((t for t in j.get("tables") or [] if "價格指數(臺灣證券交易所)" in (t.get("title") or "")), None)
    if not tbl:
        return None, []
    f = tbl["fields"]
    i_n, i_c, i_s, i_p = f.index("指數"), f.index("收盤指數"), f.index("漲跌(+/-)"), f.index("漲跌百分比(%)")
    headline, sectors = None, []
    for row in tbl.get("data") or []:
        name, close, pct = row[i_n], _num(row[i_c]), _num(row[i_p])
        if close is None or not name:
            continue
        sg = _sign_from_html(row[i_s])
        signed = None if pct is None else (abs(pct) * sg if sg else pct)
        item = {"name": name, "close": close, "change_pct": signed}
        if name in HEADLINE_NAMES:
            headline = item
        elif name.endswith("類指數"):
            sectors.append(item)
    return headline, sectors


def fetch_taiex_history_twse(months: int = 4) -> tuple[list[float], list[str]]:
    """證交所 FMTQIK 逐月的「發行量加權股價指數」日收盤（官方），近 months 個月。"""
    now = datetime.now(TW_TZ)
    ys = []
    y, m = now.year, now.month
    for _ in range(months):
        ys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    rows = {}
    for y, m in reversed(ys):
        r = _get_retry(TWSE_FMTQIK, "twse_rwd", params={"date": f"{y}{m:02d}01", "response": "json"}, timeout=30)
        r.raise_for_status()
        j = r.json()
        if j.get("stat") != "OK":
            continue
        f = j["fields"]
        i_d, i_x = f.index("日期"), f.index("發行量加權股價指數")
        for row in j.get("data") or []:
            d = _roc_to_iso(row[i_d])
            v = _num(row[i_x])
            if d and v is not None:
                rows[d] = v
    ds = sorted(rows)
    return [rows[d] for d in ds], ds


def fetch_taiex_sparkline() -> tuple[list[float], list[str]]:
    """MI_INDEX 只給當天單一數字，沒有歷史區間——近20日收盤序列改用 yfinance
    `^TWII`（實測驗證過跟 MI_INDEX 同一天的收盤值一致，例如 2026-08-25 兩邊都是
    45169.46），只用來畫App的sparkline走勢線，headline的close/change_pct仍然
    以MI_INDEX為準（見上面fetch_mi_index），這裡不覆蓋。

    **2026-09-17（總司令裁示【稽核.四.3】）新增日期輸出**：原本只回傳數值，
    `research/generate_scores_momentum.py::_relative_strength()`只能用位置
    索引對齊個股價格序列，遇到個股資料落後大盤（混日期bug）時會算出「拿
    昨天的自己比今天的大盤」這種錯誤比較。改回傳(values, dates)，dates跟
    values等長、一一對應（yfinance history()的DatetimeIndex本身就是交易日
    日期，直接轉ISO字串，不用另外查）。"""
    h = yf.Ticker("^TWII").history(period="1mo")
    if h.empty:
        return [], []
    tail = h.tail(20)
    values = [round(float(c), 2) for c in tail["Close"].tolist()]
    dates = [d.strftime("%Y-%m-%d") for d in tail.index]
    return values, dates


def fetch_taiex_sparkline_60d() -> tuple[list[float], list[str]]:
    """2026-08-27新增（題材動能榜，relative_strength因子需要近60日大盤收盤序列，
    原本的 fetch_taiex_sparkline() 只留20天給App畫圖用，這裡改用period='3mo'
    抓足夠天數，跟上面那支各自獨立、不互相影響——不是修改既有sparkline的長度，
    是新增一個給評分引擎用的較長版本，避免動到App現有的sparkline顯示範圍。
    2026-09-17同步補上日期輸出，理由同fetch_taiex_sparkline()。"""
    h = yf.Ticker("^TWII").history(period="3mo")
    if h.empty:
        return [], []
    tail = h.tail(60)
    values = [round(float(c), 2) for c in tail["Close"].tolist()]
    dates = [d.strftime("%Y-%m-%d") for d in tail.index]
    return values, dates


def fetch_tpex_index() -> dict | None:
    # 已知風險（2026-08-26 本機測試發現，不確定 GitHub Actions Ubuntu runner 是否也
    # 會遇到）：這台 Windows 機器的 Python/OpenSSL 對 TPEx 網站憑證的驗證會噴
    # `CERTIFICATE_VERIFY_FAILED: Missing Subject Key Identifier`（TPEx 憑證本身
    # 疑似缺欄位，不是我們這端設定錯）。main() 已經把每個資料源包在各自的 try/except
    # 裡，這裡失敗只會讓 out["tpex"]=None，不會讓整支腳本連台股大盤/期貨都抓不到，
    # 是設計內的優雅降級，不是需要特別處理的例外。
    r = _get_retry(TPEX_INDEX_URL, "tpex_openapi", timeout=15)
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
    r = _get_retry(TAIFEX_FUT_URL, "taifex_openapi", timeout=15)
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
            "date": chosen.get("Date"),
        }
    return out


TX_HISTORY_PATH = REPO_ROOT / "data" / "tx_futures_history.json"
TX_HISTORY_KEEP = 60


def update_tx_history(tx: dict | None) -> dict | None:
    """2026-10-12 先.八十-8：台指期近月日線歷史（首頁「台指期近月」膠囊走勢線用）。
    TAIFEX openapi DailyMarketReportFut 只給最新一天；官方歷史下載頁需要表單工作階段，依取得方式鐵律不模擬，
    改成每次排程把當天近月日盤收盤併進 data/tx_futures_history.json（去重、只留最近 60 個交易日），跨日自然累積。
    近月連續序列、未做轉倉調整（換月那天會有價差跳動），檔內與 App 都照實標示。自身失敗只回 None（十二節）。"""
    try:
        if not tx or tx.get("last") is None or not tx.get("date"):
            return None
        try:
            doc = json.loads(TX_HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        rows = {r["date"]: r for r in (doc.get("rows") or []) if r.get("date")}
        d = str(tx["date"])
        d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
        rows[d] = {"date": d, "contract_month": tx.get("contract_month"), "close": tx["last"]}
        keep = [rows[k] for k in sorted(rows)][-TX_HISTORY_KEEP:]
        doc = {"source": "TAIFEX openapi DailyMarketReportFut（每次排程累積當日近月日盤收盤）",
               "note": "近月連續序列，未做轉倉調整", "rows": keep}
        TX_HISTORY_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        return doc
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 台指期歷史累積失敗：{type(e).__name__}: {e}")
        return None


def fetch_institutional_aggregate(date_str: str) -> tuple[dict, dict | None]:
    """T86 全市場加總（見模組 docstring 的封鎖風險說明，這裡只抓一天）。回傳
    (per_stock字典, 全市場加總dict或None)——per_stock固定回傳{}（不會是None），
    呼叫端不需要另外判斷None。"""
    headers = {
        "Referer": "https://www.twse.com.tw/zh/trading/foreign/t86.html",
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)",
    }
    # 2026-08-28新增：跟其他端點一樣先過跨process節流/斷路檢查，但維持「單次
    # 嘗試不重試」的既有設計（見上面_get_retry() docstring說明），只是這裡是
    # 直接requests.get()不經過_get_retry()，所以節流/斷路邏輯要手動呼叫一次。
    _rate_limit_wait_or_raise("twse_t86")
    r = requests.get(T86_URL, params={"response": "json", "date": date_str, "selectType": "ALL"},
                      headers=headers, timeout=20)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block("twse_t86", r.status_code, r.text[:200])
        raise RuntimeError(f"twse_t86回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
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


def fetch_institutional_tpex(date_str: str) -> dict[str, dict]:
    """TPEx（上櫃）三大法人買賣超逐股資料，2026-08-27新增（使用者P1-新：
    「stock_detail法人資料僅1,083檔，但價量有2,823檔——缺口很可能是上櫃股票」，
    查證確認：T86_URL(TWSE)只涵蓋上市，這裡補上TPEx官方對應端點。
    tpex_3insti_daily_trading這個端點回傳的Date是「當次執行當下最新一期」
    （不支援指定日期查詢，date_str參數只用來對齊輸出裡的date欄位，不是查詢
    參數——這點跟fetch_institutional_aggregate()的T86_URL不同，T86支援
    date查詢參數）。欄位名很長且不一致（有些前後有多餘空白），用exact match
    找需要的三個淨額欄位，找不到就跳過那檔（不要用substring比對猜錯欄位，
    上一輪T86那邊就踩過這個坑）。"""
    r = _get_retry(TPEX_INSTITUTIONAL_URL, "tpex_openapi", timeout=20)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list):
        raise RuntimeError("tpex_3insti_daily_trading 回傳非預期格式（可能是無效路徑回傳的HTML）")
    per_stock = {}
    for row in rows:
        code = row.get("SecuritiesCompanyCode")
        if not code:
            continue
        foreign = _num(row.get("ForeignInvestorsIncludeMainlandAreaInvestors-Difference"))
        trust = _num(row.get("SecuritiesInvestmentTrustCompanies-Difference"))
        dealer = _num(row.get("Dealers-Difference"))
        actual_date = row.get("Date")
        date_iso = date_str
        if actual_date and len(actual_date) == 7 and actual_date.isdigit():
            date_iso = f"{int(actual_date[:3]) + 1911}{actual_date[3:5]}{actual_date[5:7]}"
        per_stock[code] = {
            "date": date_iso,
            "foreign_lots": round(foreign / 1000, 1) if foreign is not None else None,
            "trust_lots": round(trust / 1000, 1) if trust is not None else None,
            "dealer_lots": round(dealer / 1000, 1) if dealer is not None else None,
        }
    return per_stock


def main():
    now_tw = datetime.now(TW_TZ)
    out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errors": []}

    expected = expected_last_trading_day(now_tw)
    out["expected_trading_day"] = expected
    try:
        headline, sectors = fetch_mi_index()
        out["taiex"] = headline
        out["sectors"] = sectors
        if headline:
            headline["source"] = "TWSE openapi MI_INDEX"
    except Exception as e:
        print(f"MI_INDEX 失敗：{e}")
        out["errors"].append(f"taiex/sectors: {e}")
    # 先.八十一-1：openapi 資料日落後應有的最後交易日 → 改問 rwd MI_INDEX（帶日期）
    cur = (out.get("taiex") or {}).get("data_date")
    if expected and (not cur or cur < expected):
        try:
            h2, s2 = fetch_mi_index_rwd(expected)
            if h2:
                h2["data_date"], h2["source"] = expected, "TWSE rwd MI_INDEX（openapi 落後，改用帶日期官方端點）"
                for x in s2:
                    x["data_date"] = expected
                print(f"openapi MI_INDEX 資料日 {cur} 落後 {expected}，改用 rwd MI_INDEX")
                out["taiex"], out["sectors"] = h2, s2
        except Exception as e:  # noqa: BLE001
            print(f"rwd MI_INDEX 備援失敗：{e}")
            out["errors"].append(f"taiex_rwd_fallback: {e}")

    if out.get("taiex"):
        hist_v, hist_d = [], []
        try:
            hist_v, hist_d = fetch_taiex_history_twse(4)
            out["taiex"]["sparkline_source"] = "TWSE FMTQIK（官方逐月）"
        except Exception as e:  # noqa: BLE001
            print(f"FMTQIK 走勢失敗，改用 yfinance：{e}")
            out["errors"].append(f"taiex_fmtqik: {e}")
        if len(hist_v) >= 20:
            out["taiex"]["sparkline"], out["taiex"]["sparkline_dates"] = hist_v[-20:], hist_d[-20:]
            out["taiex"]["sparkline_60d"], out["taiex"]["sparkline_60d_dates"] = hist_v[-60:], hist_d[-60:]
        else:
            try:
                out["taiex"]["sparkline"], out["taiex"]["sparkline_dates"] = fetch_taiex_sparkline()
                out["taiex"]["sparkline_source"] = "yfinance ^TWII（備援）"
            except Exception as e:
                print(f"TAIEX sparkline(^TWII) 失敗：{e}")
                out["errors"].append(f"taiex_sparkline: {e}")
            try:
                out["taiex"]["sparkline_60d"], out["taiex"]["sparkline_60d_dates"] = fetch_taiex_sparkline_60d()
            except Exception as e:
                print(f"TAIEX sparkline_60d(^TWII) 失敗：{e}")
                out["errors"].append(f"taiex_sparkline_60d: {e}")

    try:
        out["tpex"] = fetch_tpex_index()
    except Exception as e:
        print(f"tpex_index 失敗：{e}")
        out["errors"].append(f"tpex: {e}")

    try:
        contracts = fetch_taifex_contracts()
        out["tx_futures"] = contracts.get("TX")  # 保留舊欄位名給既有呼叫端相容
        out["futures"] = contracts  # 新欄位：TX/MTX/TE/TF 全部
        if out["tx_futures"] is not None:
            out["tx_futures"]["data_date"] = _roc_to_iso(out["tx_futures"].get("date"))
        hist = update_tx_history(out["tx_futures"])  # 先.八十-8：近月日線累積，給首頁膠囊畫走勢線
        if hist and out["tx_futures"] is not None:
            tail = hist["rows"][-20:]
            out["tx_futures"]["sparkline"] = [r["close"] for r in tail]
            out["tx_futures"]["sparkline_dates"] = [r["date"] for r in tail]
            out["tx_futures"]["sparkline_note"] = hist["note"]
    except Exception as e:
        print(f"TAIFEX 失敗：{e}")
        out["errors"].append(f"futures: {e}")

    # 先.八十一-1：最後的資料日核對——仍落後就寫 stale_note，App 顯示「大盤資料停在 MM/DD」
    out["data_date"] = (out.get("taiex") or {}).get("data_date")
    lag = []
    if expected:
        if not out["data_date"] or out["data_date"] < expected:
            lag.append(("大盤", out["data_date"]))
        fd = (out.get("tx_futures") or {}).get("data_date")
        if not fd or fd < expected:
            lag.append(("台指期", fd))
    out["stale_note"] = "；".join(f"{k}資料停在 {(d or '—')[5:].replace('-', '/')}" for k, d in lag) if lag else None

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

    # 2026-08-27新增（P1-新，補TPEx上櫃三大法人缺口）：獨立try/except，TPEx
    # 失敗不影響上面TWSE(T86)已經抓到的結果，也不影響market_tw.json本身
    # 的"institutional"(全市場加總，只涵蓋上市，這裡刻意不動這個既有欄位
    # 的定義，只補per-stock字典)。
    tpex_institutional_codes = set()
    try:
        per_stock_tpex = fetch_institutional_tpex(now_tw.strftime("%Y%m%d"))
        per_stock_institutional = {**per_stock_institutional, **per_stock_tpex}
        tpex_institutional_codes = set(per_stock_tpex.keys())
    except Exception as e:
        print(f"TPEx 三大法人 失敗：{e}")
        out["errors"].append(f"institutional_tpex: {e}")

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
            # 2026-08-27修正：tse_codes只涵蓋TWSE上市，TPEx上櫃代碼本來就不在
            # 裡面——原本這條filter會把所有TPEx代碼一併濾掉，等於補了資料源
            # 卻在merge這一步自己擋掉。改成：TWSE來源的代碼仍用官方上市清單
            # 過濾掉ETF/權證；TPEx來源的代碼不套用這個（本來就不適用的）過濾，
            # 跟fundamentals.json的TPEx補充（fetch_ratios_tpex等）同一個取捨
            # ——已知限制（TPEx這裡也還沒有自己的ETF/權證過濾清單）寫進
            # STATUS.json。
            is_tpex = code in tpex_institutional_codes
            if not is_tpex and tse_codes is not None and code not in tse_codes:
                continue
            entry = stocks.setdefault(code, {})
            prior_hist = (entry.get("institutional") or {}).get("history", [])
            hist = [h for h in prior_hist if h.get("date") != row["date"]] + [row]
            hist.sort(key=lambda h: h["date"])
            hist = hist[-5:]
            entry["institutional"] = {**row, "history": hist}
            matched += 1
        detail.setdefault("meta", {})["institutional_source"] = (
            "TWSE T86（同一次呼叫，跟market_tw.json共用，不額外打；只保留官方上市公司"
            "清單(t187ap03_L)內的代碼，濾掉ETF/權證等非股票證券)+TPEx "
            "tpex_3insti_daily_trading（2026-08-27新增，上櫃股票，此端點未做"
            "ETF/權證過濾，是已知限制）"
        )
        detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(f"併入 {detail_path}：TWSE+TPEx回應共{len(per_stock_institutional)}筆證券"
              f"（TPEx {len(tpex_institutional_codes)}筆），合併 {matched} 檔")

    # 全部主要區塊都失敗才視為故障；任何一塊成功就算這輪有價值，不要因為 T86
    # 反爬蟲封鎖這種已知風險就讓整支腳本 exit 1 拖累其他已經抓到的資料被 commit。
    if not out.get("taiex") and not out.get("tpex") and not out.get("tx_futures"):
        print("錯誤：大盤/櫃買/期貨全部都沒抓到，判定為真故障")
        sys.exit(1)


if __name__ == "__main__":
    main()
