# -*- coding: utf-8 -*-
"""美股四大指數每日收盤累積檔 data/us_index_close_history.json（先.一三八-5，Cowork 收件匣 027 已定案）。

為什麼要有這份：data/market_us.json 每班覆寫、sparkline 不帶日期，前向研究（候選 N8）
需要逐日 SOX 收盤。這裡只做「合併寫檔」，零外部請求：
- fetch_market_us.py 抓完後呼叫 append_from_market_us()（source=yfinance）
- scripts/backfill_us_index_close_history.py 從 market_us.json 的 git 歷史回填（source=git_backfill）

規則：
- 日期一律用資料自帶的收盤日（as_of，美東日期），不用抓取時間。
- 盤中值（intraday=True）不是收盤，不寫。
- 同一指數同一日只留一列：新寫入覆蓋舊值（同日後抓的版本較接近最終收盤）。
只用標準函式庫，給 GitHub Actions 與本機回填腳本共用。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_PATH = REPO_ROOT / "data" / "us_index_close_history.json"

NOTE = ("美股四大指數每日收盤累積（資料源 yfinance，非 Yahoo 官方；美股原生來源）。"
        "date＝收盤日（美東），只收收盤、不收盤中值；source=yfinance 為每日管線寫入，"
        "source=git_backfill 為從 data/market_us.json git 歷史回填（每日取該日最後一版）。非投資建議。")


def load(path: Path = HISTORY_PATH) -> dict:
    if path.exists():
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("series"), dict):
                return d
        except Exception as e:  # 壞檔不覆蓋（下方 save 前會擋），只警告
            raise RuntimeError(f"讀 {path} 失敗，不覆蓋：{e}")
    return {"note": NOTE, "names": {}, "series": {}}


def merge(hist: dict, ticker: str, name: str | None, date: str, close: float, source: str,
          fetched_at: str | None = None) -> bool:
    """把一筆收盤併進 hist；回傳是否有變動。"""
    if not date or close is None:
        return False
    datetime.strptime(date, "%Y-%m-%d")  # 日期格式不對直接丟例外，由呼叫端處理
    if name:
        hist.setdefault("names", {})[ticker] = name
    rows = hist.setdefault("series", {}).setdefault(ticker, [])
    new = {"date": date, "close": round(float(close), 2), "source": source}
    if fetched_at:
        new["fetched_at"] = fetched_at
    for i, r in enumerate(rows):
        if r.get("date") == date:
            if r.get("close") == new["close"] and r.get("source") == source:
                return False
            rows[i] = new
            return True
    rows.append(new)
    rows.sort(key=lambda r: r["date"])
    return True


def save(hist: dict, path: Path = HISTORY_PATH) -> None:
    hist["note"] = NOTE
    hist["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hist["row_count"] = {t: len(v) for t, v in hist.get("series", {}).items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def append_from_market_us(market_us: dict, source: str = "yfinance", path: Path = HISTORY_PATH) -> int:
    """從一份 market_us.json 內容併入非盤中收盤；回傳變動列數。"""
    hist = load(path)
    changed = 0
    fetched_at = market_us.get("fetched_at")
    for ticker, v in (market_us.get("indices") or {}).items():
        if not isinstance(v, dict) or v.get("intraday") is True:
            continue
        if merge(hist, ticker, v.get("name"), v.get("as_of"), v.get("close"), source, fetched_at):
            changed += 1
    if changed:
        save(hist, path)
    return changed
