# -*- coding: utf-8 -*-
"""先.八十一-22（2026-10-13）：每檔月底收盤 data/monthly_close.json（repo 為主，個股營收圖的月底股價用）。

背景：個股頁營收圖要「每個營收月份的月底收盤」，原本每開一檔就向 FinMind 要 430 天日線。
查證過的替代來源都不能直接用（2026-10-13）：
- TWSE openapi `exchangeReport/FMSRFK_ALL`（上市個股月成交資訊）只有最新一個月、沒有收盤價（只有最高／最低／加權均價），
  而且回應約 7MB 以上、兩次下載都在中途被斷線。
- 本機 FinMind 快取（research/data/raw）只到 2024-12-31；alpha.db 的 daily_price 只有幾天。
所以改成**往前累積**：每次排程從 data/price_history.json（約 90 個交易日）取每檔「市場當月最後一個交易日」的收盤
（市場當月最後交易日＝所有個股該月最大日期；某檔當天沒有收盤（停牌、或 price_history 只有零星舊資料）就不收那個月，
避免把月中的收盤冒充月底——實測 1,936 檔的 90 筆裡夾著 2019～2024 年的零星舊列），
併進既有檔（同月份以新算的為準），保留最近 24 個月。目前從 2026-06 起有資料，之後每月自然變長；
更早的月份 App 仍向 FinMind 補（見 app-stock.js loadRevenueChart）。
資料月份的最後一筆若是「當月尚未結束」，標在 meta.partial_month。零外部請求、內容沒變不重寫。
用法：python scripts/build_monthly_close.py
"""
import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[0] / "scripts"))
import price_history_store as PHS  # noqa: E402
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "monthly_close.json"
KEEP_MONTHS = 24
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        ph = PHS.load(DATA / "price_history.json").get("prices") or {}
    except (OSError, ValueError) as e:
        print(f"[warn] 讀不到 price_history.json（{type(e).__name__}），monthly_close.json 維持原狀")
        return 0
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    closes = old.get("closes") or {}
    # 市場每月最後交易日：只看至少 500 檔都有的日期（排除只有少數檔的零星舊列）
    cnt = {}
    for rows in ph.values():
        for r in rows:
            if r.get("date"):
                cnt[r["date"]] = cnt.get(r["date"], 0) + 1
    month_end = {}
    for d, n in cnt.items():
        if n >= 500 and d > month_end.get(d[:7], ""):
            month_end[d[:7]] = d
    last_day = max(month_end.values()) if month_end else ""
    for code, rows in ph.items():
        by_date = {r.get("date"): r.get("close") for r in rows if r.get("date") and r.get("close") is not None}
        mm = {m: by_date[d] for m, d in month_end.items() if d in by_date}
        if not mm:
            continue
        cur = closes.setdefault(code, {})
        for m, c in mm.items():
            cur[m] = c
        for m in sorted(cur)[:-KEEP_MONTHS]:
            del cur[m]
    today = datetime.now(TW).date().isoformat()
    partial = last_day[:7] if last_day and last_day[:7] == today[:7] else None
    doc = {"meta": {"source": "data/price_history.json 每月最後一個交易日收盤（原始未還原），往前累積；scripts/build_monthly_close.py",
                    "keep_months": KEEP_MONTHS, "last_trading_day": last_day, "partial_month": partial,
                    "note": "partial_month＝該月尚未結束，數值是目前最後一個交易日的收盤"},
           "closes": {k: closes[k] for k in sorted(closes)}}
    txt = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    try:
        if OUT.read_text(encoding="utf-8") == txt:
            print("monthly_close：內容沒變")
            return 0
    except OSError:
        pass
    OUT.write_text(txt, encoding="utf-8")
    months = sorted({m for v in closes.values() for m in v})
    print(f"monthly_close：{len(closes)} 檔、月份 {months[0] if months else '—'}～{months[-1] if months else '—'}（未完整月 {partial}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
