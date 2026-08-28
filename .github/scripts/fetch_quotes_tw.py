# -*- coding: utf-8 -*-
"""抓台股盤中近即時報價，寫成 data/quotes_tw.json。

資料源：TWSE 官方 MIS 即時行情端點（mis.twse.com.tw，證交所自己的股票查詢頁面用的
公開端點，不需要 API key）。這個端點沒有官方文件保證穩定，是實測可用、業界常見的
用法——如果哪天格式變了或被擋，這支腳本要失敗要明確失敗（非 0 結束碼），不能默默
吞掉錯誤生出空的/假的 JSON。

涵蓋範圍：預設自選股（跟 index.html 的 WL 預設值一致）+ scores.json 目前的樣本
（跟著回補進度自動增加，不用手動維護清單）。不是全市場 3196 檔——這是刻意的範圍限制，
一次抓全市場對 MIS 端點不禮貌、也超出這個功能真正需要的範圍（使用者會看盤中報價的
就是自選股+選股頁看到的這些）。

**2026-08-26 修正（使用者實測手動觸發回報）：** 原本的根因是把「休市」誤判成
「端點壞掉」——台北 08:02（盤前）手動觸發時，MIS 回傳 148 筆（74 檔 × tse/otc 兩種
前綴）但每一筆的 z（成交價）都是 "-"（盤前本來就沒有成交），舊版邏輯直接把這種
「z 不是數字」的列跳過，導致 0 檔有報價、腳本用非0結束碼收場，workflow 被標記失敗，
但這其實是正常的「還沒開盤」，不是故障。這次修正三件事：
  1. 價格解析改成有回退順序（z → 委買/委賣第一檔 → 昨收，見 `resolve_price()`），
     昨收這一檔會標記 `stale: true`，不是直接跳過整檔。
  2. 明確區分「休市」跟「真故障」：粗略用台北時間週一至五 09:00–13:30 判斷是否在
     交易時段（見 `is_tw_trading_window()` 的揭露：沒有扣除國定假日，因為找不到
     現成可信的台股假日行事曆資料源——但這個粗略判斷只是拿來決定 exit code，假日
     當天即使誤判成「應該在交易」，MIS 實際上還是會回傳昨收可用，`quotes` 不會是
     空的，所以不會真的觸發失敗，這個簡化在實務上不影響結果，只是誠實揭露）。
     交易時段內卻真的一檔都抓不到才視為故障（exit 1）；非交易時段一律 exit 0。
  3. JSON 多寫 `meta` 區塊（是否交易時段、查詢/成功/即時檔數、資料型態），方便
     App 端或人工排查判斷這批資料的性質，不用自己重新猜。

**2026-08-27 新增自選股sparkline，已知限制**：每檔額外用 `STOCK_DAY` 端點抓近
20日收盤（見 `fetch_sparkline_20d()`），**只涵蓋TWSE上市股票**——實測本輪
scores.json樣本裡約24檔持續回428（不是間歇性，同一檔重試/隔幾秒再測都一樣），
查證這些代號都不在 `t187ap03_L`（上市公司清單）裡，是上櫃（TPEx）股票，
`www.twse.com.tw/exchangeReport/STOCK_DAY` 本來就是TWSE專屬端點，沒有涵蓋
TPEx——這是永久性限制不是bug，上櫃股票的sparkline會缺，`quotes[code]`裡就是
沒有`sparkline`欄位，App端要當成「暫無走勢圖」處理，不是誤判成故障。
"""
from __future__ import annotations

import json
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCORES_PATH = REPO_ROOT / "scores.json"
OUT_PATH = REPO_ROOT / "data" / "quotes_tw.json"

# 2026-08-28新增（使用者裁示「428是我們自己打出來的」，「資料源禮儀」規則，
# 跟research/finmind_client.py同一套schema/同一份共用狀態檔，各自複製一份
# 邏輯——跨repo/跨目錄不import是既有慣例）：STOCK_DAY_URL（單股歷史日線）
# 是這支腳本裡實測過會428的端點（見fetch_stock_day_month() docstring），
# 用跨process共用的狀態檔節流+斷路，不是只有這個process自己記得。MIS即時
# 報價端點目前沒有觀察到同樣的問題，這輪先不動它，只保護有實測過會出事的
# STOCK_DAY_URL。
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


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    from datetime import timezone as _tz
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(_tz.utc).isoformat()
    _save_rate_limit_state(state)

DEFAULT_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"  # 上市公司基本資料，公司代號清單
STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"  # 個股歷史日線（一次一檔一個月）
TW_TZ = timezone(timedelta(hours=8))


def load_universe_codes() -> list[str]:
    codes = set(DEFAULT_WATCHLIST)
    if SCORES_PATH.exists():
        try:
            data = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
            for row in data.get("stocks", []):
                code = row.get("code")
                if code:
                    codes.add(code)
        except Exception as e:
            print(f"讀 scores.json 失敗（不影響繼續跑，只是少了這批代號）：{e}")
    return sorted(codes)


def load_tse_code_set() -> set[str] | None:
    """回傳上市（TSE）公司代號集合，用來把查詢前綴縮成只查對的那一個
    （2026-08-26 新增，減少 MIS 請求量）。抓不到就回傳 None——呼叫端看到 None
    要退回「兩個前綴都查」的舊行為，不能因為這個優化本身失敗就讓整支腳本失敗，
    這只是效率優化，不是必要路徑。"""
    try:
        r = requests.get(TSE_LIST_URL, timeout=15)
        r.raise_for_status()
        rows = r.json()
        codes = {row.get("公司代號") for row in rows if row.get("公司代號")}
        return codes if codes else None
    except Exception as e:
        print(f"抓上市公司清單失敗（改回兩個前綴都查，不影響正確性只影響效率）：{e}")
        return None


def fetch_batch(codes: list[str], tse_codes: set[str] | None) -> list[dict]:
    """MIS 一次能查的檔數有限，分批查（每批 50 檔，經驗值，避免單次 URL 過長被拒）。

    **前綴優化（2026-08-26）**：已知是上市（在 `tse_codes` 裡）的代號只查 `tse_`
    前綴；不確定的（`tse_codes` 是 None，或代號不在裡面——可能是上櫃、也可能是
    ETF/TDR等 `t187ap03_L` 沒收錄的類型）維持舊行為兩個前綴都查，不賭它一定是
    上櫃，避免查漏。

    用 requests 不用 urllib：TWSE 的憑證在 Python 內建 urllib 上會 SSL 驗證失敗
    （這個專案 alpha-data/fetch.py 已經踩過這個坑、寫在 CLAUDE.md「已知地雷」裡，
    這裡沿用同樣的教訓，改用 requests 就正常）。"""
    out = []
    batch_size = 50
    headers = {
        "Referer": "https://mis.twse.com.tw/stock/index.jsp",
        "User-Agent": "Mozilla/5.0 (compatible; AlphaAppQuoteFetcher/1.0)",
    }
    for i in range(0, len(codes), batch_size):
        batch = codes[i : i + batch_size]
        parts = []
        for c in batch:
            if tse_codes is not None and c in tse_codes:
                parts.append(f"tse_{c}.tw")
            else:
                parts.append(f"tse_{c}.tw")
                parts.append(f"otc_{c}.tw")
        ex_ch = "|".join(parts)
        r = requests.get(MIS_URL, params={"ex_ch": ex_ch, "json": "1", "delay": "0"}, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("msgArray", []))
    return out


def _num(v) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_level(raw) -> float | None:
    """b（委買）/a（委賣）欄位格式是底線分隔的多檔價格字串（例如 "72.1_72.2_..."），
    取第一個能轉成數字的值。這兩個欄位在盤前/休市時可能整個不存在（`r.get()`
    會拿到 None，下面直接回傳 None，呼叫端會繼續往下一層回退）。"""
    if not raw:
        return None
    for part in str(raw).split("_"):
        v = _num(part)
        if v is not None:
            return v
    return None


def resolve_price(r: dict) -> tuple[float | None, bool]:
    """回傳 (price, is_stale)。優先序：z(成交價) → b/a 第一檔(委買/委賣) → y(昨收，
    標記 stale=True)。三層都拿不到才回傳 (None, True)（呼叫端應該跳過這檔）。"""
    z = _num(r.get("z"))
    if z is not None:
        return z, False
    b = _first_level(r.get("b"))
    if b is not None:
        return b, False
    a = _first_level(r.get("a"))
    if a is not None:
        return a, False
    y = _num(r.get("y"))
    if y is not None:
        return y, True
    return None, True


STOCK_DAY_HEADERS = {
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
    "User-Agent": "Mozilla/5.0 (compatible; AlphaAppQuoteFetcher/1.0)",
}


def fetch_stock_day_month(code: str, yyyymm: str) -> list[float]:
    """個股單月日線（`www.twse.com.tw/exchangeReport/STOCK_DAY`，業界常見用法的
    官方端點，非openapi但長年穩定）。回傳該月每個交易日的收盤價（依日期由舊到新）。
    stat不是OK（例如該檔當月完全沒交易、代號不存在）就回傳空list，不拋例外。

    **實測發現（2026-08-27）**：不帶 Referer/User-Agent 連續呼叫會間歇性回
    428（本機測試40檔用同樣節奏，不帶header時約6-7成失敗，帶了header後
    40/40全部成功）——這不是主要靠放慢節奏解決的頻率限制，是需要瀏覽器風格
    header 才會放行，類似T86的反爬蟲邏輯（見fetch_market_tw.py docstring）。
    但實測92檔的完整批次（前面小樣本測試沒觸發）仍間歇性出現428（約25%），
    看起來是有額外的流量閾值——**2026-08-28升級**：不再只靠單次重試，改成
    跨process共用節流（同一來源兩次請求間隔至少3秒）+ 斷路器（收到428/403
    就標記這個來源封鎖2小時，見模組開頭的`_rate_limit_wait_or_raise()`）。
    封鎖中會直接RuntimeError，呼叫端的try/except接住、不影響其他檔。"""
    _rate_limit_wait_or_raise("twse_stock_day")
    r = requests.get(STOCK_DAY_URL, params={"response": "json", "date": f"{yyyymm}01", "stockNo": code},
                      headers=STOCK_DAY_HEADERS, timeout=15)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block("twse_stock_day", r.status_code, r.text[:200])
        raise RuntimeError(f"twse_stock_day回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
    r.raise_for_status()
    d = r.json()
    if d.get("stat") != "OK":
        return []
    return [c for c in (_num(row[6]) for row in d.get("data", [])) if c is not None]


def fetch_sparkline_20d(code: str, now_tw: datetime) -> list[float]:
    """近20日收盤（畫sparkline用）。當月不夠20天（月初）就補抓上個月銜接。"""
    closes = fetch_stock_day_month(code, now_tw.strftime("%Y%m"))
    if len(closes) < 20:
        prev_month = (now_tw.replace(day=1) - timedelta(days=1))
        closes = fetch_stock_day_month(code, prev_month.strftime("%Y%m")) + closes
    return closes[-20:]


def load_sparkline_cache(codes: list[str], today_str: str) -> dict[str, list[float]]:
    """讀舊quotes_tw.json裡「今天已經抓過」的sparkline快取。這支腳本每10分鐘跑
    一次（盤中報價），但個股歷史日線一天只會多一筆、不需要每次都重打
    STOCK_DAY——沒有官方文件保證的頻率限制，保守起見一天只在第一次執行時對
    每檔各打1-2次，其餘9次/10分鐘的執行直接沿用當天稍早抓到的快取，不重複打。"""
    if not OUT_PATH.exists():
        return {}
    try:
        prior = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for code, q in prior.get("quotes", {}).items():
        sp = q.get("sparkline")
        if sp and q.get("sparkline_date") == today_str:
            out[code] = sp
    return out


def is_tw_trading_window(now: datetime) -> bool:
    """粗略判斷：週一至五 09:00–13:30 台北時間。**已知簡化，誠實揭露**：沒有扣除
    國定假日（找不到現成、可信賴的台股假日行事曆免費資料源）。這個簡化在實務上
    影響有限，見模組 docstring 的說明——假日當天即使被誤判成「應該在交易」，
    `quotes` 仍然會有昨收可用，不會觸發誤判的失敗。"""
    wd = now.weekday()  # 0=Mon .. 6=Sun
    minutes = now.hour * 60 + now.minute
    return wd <= 4 and 9 * 60 <= minutes < 13 * 60 + 30


def main():
    now_tw = datetime.now(TW_TZ)
    trading_window = is_tw_trading_window(now_tw)

    codes = load_universe_codes()
    tse_codes = load_tse_code_set()
    print(f"查詢 {len(codes)} 檔台股代號（預設自選股 + scores.json 樣本）"
          f"，上市清單{'取得成功 ' + str(len(tse_codes)) + ' 檔' if tse_codes else '取得失敗，兩前綴都查'}")
    raw = fetch_batch(codes, tse_codes)
    print(f"MIS 回傳 {len(raw)} 筆，目前{'在' if trading_window else '不在'}交易時段"
          f"（台北時間 {now_tw.strftime('%Y-%m-%d %H:%M:%S')}）")

    quotes = {}
    n_live = 0  # 真正有成交/委買委賣的檔數（非 stale）
    for r in raw:
        code = r.get("c")
        if not code:
            continue
        price, stale = resolve_price(r)
        if price is None:
            continue
        prev_close = _num(r.get("y"))
        chg = round(price - prev_close, 4) if prev_close else None
        pct = round(chg / prev_close * 100, 3) if (chg is not None and prev_close) else None
        if not stale:
            n_live += 1
        # 同一代號可能因為 tse/otc 兩前綴都查而重複出現；優先保留非 stale 的那筆
        if code in quotes and quotes[code]["stale"] and stale:
            continue
        if code in quotes and not quotes[code]["stale"] and stale:
            continue
        quotes[code] = {
            "name": r.get("n"),
            "price": price,
            "prev_close": prev_close,
            "change": chg,
            "change_pct": pct,
            "time": r.get("t"),  # 當日成交時刻 HH:MM:SS（stale 時是查詢當下時刻，不是真正成交時刻）
            "date": r.get("d"),  # YYYYMMDD
            "stale": stale,
        }

    # 2026-08-27 新增：自選股sparkline走勢（STATUS.json列的最後一個P0缺口）。
    # 見load_sparkline_cache()docstring：一天只在第一次執行時對每檔各打
    # STOCK_DAY，其餘同一天的執行沿用快取，不會每10分鐘打好幾百次。
    today_str = now_tw.strftime("%Y-%m-%d")
    cache = load_sparkline_cache(list(quotes.keys()), today_str)
    fetched = cached = failed_sp = 0
    for code in quotes:
        if code in cache:
            quotes[code]["sparkline"] = cache[code]
            quotes[code]["sparkline_date"] = today_str
            cached += 1
            continue
        try:
            sp = fetch_sparkline_20d(code, now_tw)
            if sp:
                quotes[code]["sparkline"] = sp
                quotes[code]["sparkline_date"] = today_str
                fetched += 1
            time.sleep(0.15)  # 實測穩定節奏（見fetch_stock_day_month docstring），主要靠header不是靠慢
        except Exception as e:
            failed_sp += 1
            # 這裡故意不用「・」（U+30FB）：本機Windows主控台cp950編碼曾經在這裡
            # 讓整支腳本直接crash（print本身丟UnicodeEncodeError，不是被try/except
            # 接住的那個例外）——GitHub Actions是UTF-8不會有事，但本機測試會，改用
            # 純ASCII的"-"比較保險，不影響其他地方原本就在用的「・」（那些沒出過事）。
            print(f"  - {code} sparkline 失敗（不影響報價本身）：{e}")
    print(f"sparkline：沿用快取 {cached} 檔、新抓 {fetched} 檔、失敗 {failed_sp} 檔")

    data_type = "intraday" if n_live > 0 else ("prev_close" if quotes else "none")
    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "TWSE MIS（mis.twse.com.tw，證交所公開即時行情端點）",
        "meta": {
            "trading_window": trading_window,
            "queried": len(codes),
            "matched": len(quotes),
            "live": n_live,
            "data_type": data_type,
        },
        "quotes": quotes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(quotes)} 檔有報價（{n_live} 檔即時，"
          f"{len(quotes) - n_live} 檔用昨收頂替），data_type={data_type}")

    if not quotes and trading_window:
        print("錯誤：交易時段內卻一檔報價都沒抓到，判定為真故障——回傳非0結束碼讓 workflow 標記失敗")
        sys.exit(1)
    if not quotes:
        print("非交易時段且一檔報價都沒抓到（含昨收都沒有）——理論上不該發生，"
              "但既然發生了仍誠實回報非0結束碼，不假裝成功")
        sys.exit(1)
    # 非交易時段、有拿到資料（即使全部是昨收頂替）：正常結束，不讓 workflow 變紅。


if __name__ == "__main__":
    main()
