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
"""
from __future__ import annotations

import json
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCORES_PATH = REPO_ROOT / "scores.json"
OUT_PATH = REPO_ROOT / "data" / "quotes_tw.json"

DEFAULT_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


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


def fetch_batch(codes: list[str]) -> list[dict]:
    """MIS 一次能查的檔數有限，分批查（每批 50 檔，經驗值，避免單次 URL 過長被拒）。
    每一檔前面不知道是上市(tse)還是上櫃(otc)，兩種都查一次最保險（查不到的那個會被
    MIS 回傳空陣列，不會報錯）。

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
        ex_ch = "|".join([f"tse_{c}.tw" for c in batch] + [f"otc_{c}.tw" for c in batch])
        r = requests.get(MIS_URL, params={"ex_ch": ex_ch, "json": "1", "delay": "0"}, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("msgArray", []))
    return out


def main():
    codes = load_universe_codes()
    print(f"查詢 {len(codes)} 檔台股代號（預設自選股 + scores.json 樣本）")
    raw = fetch_batch(codes)
    print(f"MIS 回傳 {len(raw)} 筆")

    quotes = {}
    for r in raw:
        code = r.get("c")
        z = r.get("z")  # 成交價；有些非交易時段/當日無成交會是 "-" 或空字串
        if not code or not z or z == "-":
            continue
        try:
            price = float(z)
            prev_close = float(r.get("y")) if r.get("y") not in (None, "", "-") else None
        except ValueError:
            continue
        chg = round(price - prev_close, 4) if prev_close else None
        pct = round(chg / prev_close * 100, 3) if (chg is not None and prev_close) else None
        quotes[code] = {
            "name": r.get("n"),
            "price": price,
            "prev_close": prev_close,
            "change": chg,
            "change_pct": pct,
            "time": r.get("t"),  # 當日成交時刻 HH:MM:SS
            "date": r.get("d"),  # YYYYMMDD
        }

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "TWSE MIS（mis.twse.com.tw，證交所公開即時行情端點）",
        "quotes": quotes,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(quotes)} 檔有報價")

    if not quotes:
        print("警告：一檔報價都沒抓到，可能是端點格式變了或被擋——回傳非0結束碼讓 workflow 標記失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
