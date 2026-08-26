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
"""
from __future__ import annotations

import json
import sys
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCORES_PATH = REPO_ROOT / "scores.json"
OUT_PATH = REPO_ROOT / "data" / "quotes_tw.json"

DEFAULT_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"  # 上市公司基本資料，公司代號清單
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
