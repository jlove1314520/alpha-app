"""美股描述性篩選資料（2026-10-13 先.八十一-33）→ data/us_screener.json。

**定位，先講清楚**：給 App 選股頁美股分頁「依成交額／漲跌幅／市值門檻篩選」用的**描述性資料**，
不是選股訊號、不排名、不登記試驗、不回測，非投資建議。

宇宙：data/us_financials.json 的代號（SEC 當下名冊前段約 260 個 CIK＋App 自選美股），
**不是全市場、也不是時點宇宙**；已下市股不在裡面（存活者偏誤，見 meta.data_quality）。

資料源（美股原生，CLAUDE.md 七節）：
- 價量：yfinance `download(period="1mo")` **一次批次**（日線，未還原收盤＋成交量）。
  只用**已收盤**的交易日：美東當天 16:15 前抓到的當日列（盤中未完成的 K）一律捨棄。
- 流通股數：SEC EDGAR XBRL frames API `dei/EntityCommonStockSharesOutstanding`（申報封面的
  流通股數），近四個季度瞬時值各 1 次請求、同一 CIK 取 end 最新者；每次請求後 sleep 0.2 秒
  （SEC 官方上限 10 req/秒，見 C:\\alpha\\CLAUDE.md「SEC EDGAR」）。
  市值＝流通股數×收盤，**是估算**；多類股公司（GOOGL、BRK-B 等）與外國發行人（20-F／40-F 的 ADR）
  在 frames 裡沒有單一股數 → 市值留空（2026-10-13 實測 253 檔有 184 檔有市值）；
  股數超過 200 天沒更新者 flags 標「流通股數停在 …」。

頻率：market.yml 每班 1 次 yfinance 批次＋4 次 SEC 請求。
失敗處理：yfinance 整批失敗或有收盤的檔數 <50 → 不覆蓋既有輸出（exit 1，workflow 端只警告）；
SEC 失敗只讓市值缺值，不擋價量。
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
FIN_PATH = ROOT / "data" / "us_financials.json"
OUT_PATH = ROOT / "data" / "us_screener.json"
TW_TZ = timezone(timedelta(hours=8))
ET = ZoneInfo("America/New_York")
SEC_HEADERS = {"User-Agent": "AlphaApp-USFinancials contact@alpha-app-project.example"}
SEC_SLEEP_SEC = 0.2
AVG_DAYS = 20
SHARES_STALE_DAYS = 200
MIN_PRICED = 50


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def _recent_instant_frames(today: date, n: int = 4) -> list[str]:
    """CY{年}Q{季}I，從本季往前 n 個（本季常常還沒幾家申報；只交年報者要往前一年才有）。"""
    y, q = today.year, (today.month - 1) // 3 + 1
    out = []
    for _ in range(n):
        out.append(f"CY{y}Q{q}I")
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out


def fetch_shares(ciks: set[int], today: date) -> tuple[dict, dict]:
    """回傳 ({cik: {"shares":, "end":, "accn":}}, meta)。"""
    best: dict[int, dict] = {}
    meta = {"source": "SEC XBRL frames dei/EntityCommonStockSharesOutstanding", "frames": [], "errors": []}
    for fr in _recent_instant_frames(today):
        url = f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{fr}.json"
        try:
            r = requests.get(url, headers=SEC_HEADERS, timeout=30)
            if r.status_code == 404:
                meta["frames"].append({"frame": fr, "rows": 0, "status": 404})
                continue
            r.raise_for_status()
            rows = r.json().get("data", [])
            meta["frames"].append({"frame": fr, "rows": len(rows), "status": 200})
            for x in rows:
                c = x.get("cik")
                v = _num(x.get("val"))
                if c not in ciks or not v or v <= 0:
                    continue
                if c not in best or str(x.get("end", "")) > best[c]["end"]:
                    best[c] = {"shares": v, "end": str(x.get("end", "")), "accn": x.get("accn")}
        except Exception as e:  # noqa: BLE001
            meta["errors"].append(f"{fr}: {type(e).__name__}: {e}")
            print(f"[warn] SEC frames {fr} 失敗：{e}")
        finally:
            time.sleep(SEC_SLEEP_SEC)
    return best, meta


def fetch_bars(tickers: list[str], now_et: datetime):
    """yfinance 一次批次。回傳 (df_close, df_volume, dropped_partial_date)。"""
    import yfinance as yf  # noqa: PLC0415
    to_yf = {t: t.replace(".", "-") for t in tickers}  # yfinance 類股用「-」（BRK.B→BRK-B）；名冊本來就是 BRK-B 的不變
    back = {v: k for k, v in to_yf.items()}
    df = yf.download(sorted(back), period="1mo", auto_adjust=False, progress=False, threads=True, group_by="column")
    close, vol = df["Close"].copy(), df["Volume"].copy()
    close.columns = [back.get(c, c) for c in close.columns]
    vol.columns = [back.get(c, c) for c in vol.columns]
    dropped = None
    if len(close.index):
        last = close.index[-1].date()
        session_closed = now_et.hour > 16 or (now_et.hour == 16 and now_et.minute >= 15)
        if last >= now_et.date() and not session_closed:
            dropped = str(last)
            close, vol = close.iloc[:-1], vol.iloc[:-1]
    return close, vol, dropped


def main() -> int:
    try:
        fin = json.loads(FIN_PATH.read_text(encoding="utf-8"))["financials"]
    except Exception as e:  # noqa: BLE001
        print(f"[error] 讀不到 {FIN_PATH.name}：{e}；不覆蓋既有輸出")
        return 1
    tickers = sorted(fin.keys())
    now_et = datetime.now(ET)
    try:
        close, vol, dropped = fetch_bars(tickers, now_et)
    except Exception as e:  # noqa: BLE001
        print(f"[error] yfinance 批次下載失敗：{type(e).__name__}: {e}；不覆蓋既有輸出")
        return 1
    if not len(close.index):
        print("[error] yfinance 沒有回任何已收盤交易日；不覆蓋既有輸出")
        return 1
    as_of = str(close.dropna(how="all").index.max().date())

    ciks = {int(v["cik"]) for v in fin.values() if v.get("cik")}
    shares, sec_meta = fetch_shares(ciks, now_et.date())

    stocks = []
    for t in tickers:
        f = fin[t]
        row = {"code": t, "name": f.get("name"), "exchange": f.get("exchange"), "flags": []}
        s = close[t].dropna() if t in close else None
        v = vol[t].dropna() if t in vol else None
        if s is None or not len(s):
            row["flags"].append("無價量")
            stocks.append(row)
            continue
        last_date = str(s.index[-1].date())
        c = _num(s.iloc[-1])
        prev = _num(s.iloc[-2]) if len(s) >= 2 else None
        row.update({
            "date": last_date,
            "close": round(c, 4) if c else None,
            "change_pct": round((c / prev - 1) * 100, 2) if c and prev else None,
            "change_5d_pct": round((c / _num(s.iloc[-6]) - 1) * 100, 2) if len(s) >= 6 and _num(s.iloc[-6]) else None,
            "volume": int(v.iloc[-1]) if v is not None and len(v) and _num(v.iloc[-1]) is not None else None,
        })
        if last_date != as_of:
            row["flags"].append(f"價格停在 {last_date}")
        if v is not None and len(v):
            tail_v = v.iloc[-AVG_DAYS:]
            tail_c = s.reindex(tail_v.index)
            dv = (tail_v * tail_c).dropna()
            row["avg_volume_20d"] = int(tail_v.mean())
            row["avg_dollar_volume_20d"] = round(float(dv.mean()), 0) if len(dv) else None
            row["n_days"] = int(len(tail_v))
            if len(tail_v) < 15:
                row["flags"].append(f"近 1 個月只有 {len(tail_v)} 天價量")
        sh = shares.get(int(f["cik"])) if f.get("cik") else None
        if sh and c:
            row["shares_outstanding"] = int(sh["shares"])
            row["shares_end"] = sh["end"]
            row["market_cap_est"] = round(sh["shares"] * c, 0)
            try:
                if (now_et.date() - date.fromisoformat(sh["end"])).days > SHARES_STALE_DAYS:
                    row["flags"].append(f"流通股數停在 {sh['end']}")
            except ValueError:
                pass
        else:
            row["flags"].append("無流通股數（市值缺）")
        stocks.append(row)

    priced = sum(1 for r in stocks if r.get("close"))
    if priced < MIN_PRICED:
        print(f"[error] 有收盤的只有 {priced} 檔（<{MIN_PRICED}）；不覆蓋既有輸出")
        return 1
    with_cap = sum(1 for r in stocks if r.get("market_cap_est"))
    payload = {
        "meta": {
            "market": "US",
            "generated_at": datetime.now(TW_TZ).isoformat(timespec="seconds"),
            "as_of": as_of,
            "dropped_partial_session": dropped,
            "label": "描述性篩選，非選股訊號",
            "disclaimer": "只把現有資料依門檻篩出來，沒有排名、沒有回測、不是選股訊號，非投資建議。",
            "price_source": "yfinance download(period=1mo) 日線一次批次（未還原收盤＋成交量；只用已收盤交易日）",
            "shares_source": sec_meta,
            "universe_note": "SEC 當下名冊前段＋App 自選美股（約 250 檔），非全市場、非時點宇宙。",
            "data_quality": [
                "市值＝SEC 申報封面流通股數×收盤，是估算；多類股公司（例：GOOGL、BRK-B）與外國發行人（ADR，交 20-F／40-F）在 SEC 彙總表裡沒有單一股數，市值留空，設了市值門檻時不會出現。",
                "成交額＝成交量×收盤的近 20 個交易日平均，yfinance 成交量為各交易所合計，與券商畫面可能略有差異。",
                "樣本只含今天還在市的公司，不含已下市股；存活者偏誤未完全修正：已下市股約 97%（抽樣 58／60）無價格來源。",
                "yfinance 非 Yahoo 官方套件、Yahoo 未公布次數上限；抓不到時整份保留上一版並標日期。",
            ],
            "count": len(stocks),
            "priced_count": priced,
            "market_cap_count": with_cap,
        },
        "stocks": stocks,
    }
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"us_screener: {len(stocks)} 檔、有收盤 {priced}、有市值 {with_cap}、資料日 {as_of}"
          f"{'（捨棄盤中未收盤 ' + dropped + '）' if dropped else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
