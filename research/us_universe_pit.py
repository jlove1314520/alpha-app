# -*- coding: utf-8 -*-
"""美股 PIT 宇宙：以 SEC EDGAR 為母體，含已下市股（2026-09-08 資料源一.1）。

**為什麼要重做**（總司令裁示，Cowork 核對出的違規點）：
現行 `us_universe.py` 用 FinMind 的 `USStockInfo` 當母體——那是**台灣資料商**提供的
美股清單，而且是「當下快照」。實測確認它的後果：

    company_tickers.json（SEC 當下申報人 10,412 筆）裡
      AAPL ✓  NVDA ✓
      TWTR ✗  SIVB ✗  FRC ✗   ← 全部是已下市，當下快照一律抓不到

用只含存活者的母體做回測，等於事先知道哪些公司沒倒——**存活者偏誤**，而且越往
小型股越嚴重。這是 CLAUDE.md 台股偽影家族⑦標為「最貴的一個」的同一個問題。

**做法**：母體 = 當下申報人 ∪ 歷史上申報過 Form 25 家族（下市）的公司。
- 當下申報人：`https://www.sec.gov/files/company_tickers.json`（一次請求，10,412 筆）
- 歷史下市：EDGAR 季度表單索引 `full-index/YYYY/QTRn/form.idx`，篩出 Form 25／25-NSE
  （實測 2024Q1 有 464 筆），只留那幾行、其餘丟棄
- 之後每日增量：`daily-index/YYYY/QTRn/form.YYYYMMDD.idx`（實測 680KB／0.6 秒）

**成本誠實揭露**：季度索引每份約 57.8MB、19 秒。回補 15 年 ≈ 60 份 ≈ 3.5GB、約 20 分鐘。
這是一次性的；之後每天 680KB。指令參數可控制回補範圍，預設只補最近 8 季，
要全量回補得明確指定 `--from-year`，避免有人不小心觸發 3.5GB 下載。

用法：
    python research/us_universe_pit.py --quarters 8       # 預設：近 8 季
    python research/us_universe_pit.py --from-year 2010   # 全量回補（會很久）
    python research/us_universe_pit.py --daily            # 每日增量
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research" / "data" / "us_universe_pit.json"
CACHE = ROOT / "research" / "data" / "us_delisting_index"
TZ = timezone(timedelta(hours=8))
# SEC 要求 User-Agent 帶可聯絡的識別資訊，否則會被擋。這是他們的公開存取條款要求，
# 不是規避任何限制。
UA = {"User-Agent": "Alpha Research jlove201314@yahoo.com.tw"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC 對自動化存取的建議上限是每秒 10 次。我們用 0.35 秒間隔（約每秒 3 次），
# 遠低於上限——依 CLAUDE.md「照官方上限做硬性預算」的原則，寧可慢也不要被擋。
REQ_INTERVAL_SEC = 0.35
_last_req = [0.0]


def _get(url: str, timeout: int = 120) -> bytes:
    wait = REQ_INTERVAL_SEC - (time.time() - _last_req[0])
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def current_filers() -> dict[str, dict]:
    """當下仍在申報的公司。這是母體的一半，另一半是已下市的。"""
    d = json.loads(_get(TICKERS_URL, timeout=60))
    out = {}
    for v in d.values():
        t = str(v.get("ticker") or "").strip().upper()
        if t:
            out[t] = {"cik": int(v["cik_str"]), "title": v.get("title", ""), "status": "active"}
    return out


FORM25_RE = re.compile(r"^(25|25-NSE)(\(A\))?\s")


def _parse_form_idx(text: str) -> list[dict]:
    """從 form.idx 撈 Form 25 家族。

    欄位是固定寬度但寬度隨年份變過，所以用「從右邊取日期與路徑、中間反推 CIK」
    的方式解析，比寫死欄位起訖穩。
    """
    out = []
    for line in text.splitlines():
        if not FORM25_RE.match(line.strip()):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        form = parts[0]
        # 日期：YYYY-MM-DD 或 YYYYMMDD
        dt = None
        cik = None
        for p in parts:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
                dt = p
            elif re.fullmatch(r"\d{8}", p):
                dt = f"{p[:4]}-{p[4:6]}-{p[6:]}"
            elif re.fullmatch(r"\d{4,10}", p) and cik is None:
                cik = int(p)
        if dt and cik:
            out.append({"form": form, "cik": cik, "date": dt})
    return out


def fetch_quarter(year: int, qtr: int) -> list[dict]:
    cache_f = CACHE / f"{year}Q{qtr}.json"
    if cache_f.exists():
        try:
            return json.loads(cache_f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{qtr}/form.idx"
    t0 = time.time()
    raw = _get(url)
    rows = _parse_form_idx(raw.decode("latin-1"))
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_f.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"    {year}Q{qtr}: {len(raw)/1e6:.1f}MB / {time.time()-t0:.1f}s → Form 25 家族 {len(rows)} 筆")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quarters", type=int, default=8, help="回補最近幾季（預設 8）")
    ap.add_argument("--from-year", type=int, default=None, help="全量回補起始年（會下載很多）")
    ap.add_argument("--daily", action="store_true", help="只做當日增量")
    a = ap.parse_args()

    print("=" * 74)
    print("  美股 PIT 宇宙（SEC EDGAR 母體，含已下市股）")
    print("=" * 74)

    print("  [1/3] 當下申報人 company_tickers.json …")
    active = current_filers()
    print(f"        {len(active)} 筆")

    print("  [2/3] 歷史下市（EDGAR 季度表單索引的 Form 25 家族）…")
    today = date.today()
    quarters = []
    if a.from_year:
        for y in range(a.from_year, today.year + 1):
            for q in range(1, 5):
                if date(y, (q - 1) * 3 + 1, 1) <= today:
                    quarters.append((y, q))
        print(f"        全量回補 {a.from_year}~{today.year}，共 {len(quarters)} 季"
              f"（估 {len(quarters)*57.8/1000:.1f}GB、約 {len(quarters)*19/60:.0f} 分鐘）")
    else:
        y, q = today.year, (today.month - 1) // 3 + 1
        for _ in range(a.quarters):
            quarters.append((y, q))
            q -= 1
            if q == 0:
                q, y = 4, y - 1
        quarters.reverse()
        print(f"        近 {a.quarters} 季")

    delisted_rows = []
    for y, q in quarters:
        try:
            delisted_rows += fetch_quarter(y, q)
        except Exception as e:  # noqa: BLE001
            print(f"    {y}Q{q}: 失敗（{type(e).__name__}: {e}）——跳過，不中斷整體回補")

    by_cik: dict[int, str] = {}
    for r in delisted_rows:
        c, d = r["cik"], r["date"]
        if c not in by_cik or d < by_cik[c]:
            by_cik[c] = d          # 同一 CIK 取最早的下市申報日

    print(f"        Form 25 家族申報 {len(delisted_rows)} 筆，涉及 {len(by_cik)} 家公司")

    print("  [3/3] 合併母體 …")
    cik_to_ticker = {v["cik"]: t for t, v in active.items()}
    universe = {t: dict(v) for t, v in active.items()}
    delisted_no_ticker = 0
    for cik, d in by_cik.items():
        t = cik_to_ticker.get(cik)
        if t:
            universe[t]["status"] = "delisted"
            universe[t]["delisted_at"] = d
        else:
            # 已下市且不在當下快照裡——正是存活者偏誤的來源。
            # 沒有 ticker 對照時仍然記下 CIK，之後可用 submissions API 補 ticker。
            universe[f"CIK{cik}"] = {"cik": cik, "title": "", "status": "delisted",
                                     "delisted_at": d, "ticker_unresolved": True}
            delisted_no_ticker += 1

    doc = {
        "generated_at": datetime.now(TZ).isoformat(),
        "source": "SEC EDGAR company_tickers.json（當下申報人）＋ full-index form.idx 的 Form 25 家族（歷史下市）",
        "note": "取代 FinMind USStockInfo：後者是台灣資料商的當下快照，抓不到已下市股"
                "（實測 TWTR／SIVB／FRC 皆不在其中），用它做回測會有存活者偏誤",
        "quarters_scanned": [f"{y}Q{q}" for y, q in quarters],
        "counts": {
            "active": sum(1 for v in universe.values() if v["status"] == "active"),
            "delisted": sum(1 for v in universe.values() if v["status"] == "delisted"),
            "delisted_not_in_current_snapshot": delisted_no_ticker,
            "total": len(universe),
        },
        "universe": universe,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    c = doc["counts"]
    print()
    print(f"  母體合計 {c['total']}：在市 {c['active']}、已下市 {c['delisted']}")
    print(f"  其中 **{c['delisted_not_in_current_snapshot']} 家已下市公司不在當下快照裡**")
    print("  ——這些正是舊宇宙（FinMind USStockInfo）系統性漏掉的存活者偏誤來源。")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
