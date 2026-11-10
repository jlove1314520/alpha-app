# -*- coding: utf-8 -*-
"""先.一五四-1d 甲②（已定案（Cowork 11/10）：照甲執行）：紙上優化軌 F18（零股委託簿失衡度）每日抓 TWSE TWTC7U。

外部請求（照 C:\\alpha\\CLAUDE.md 頻率上限清單補登）：
  - `www.twse.com.tw/rwd/zh/afterTrading/TWTC7U?date=YYYYMMDD&response=json`，**每次執行最多 1 次**：
    只抓「最近一個已收盤的台股交易日」（台北 16:00 後算今天，之前算前一個交易日；休市日依 data/trading_calendar.json），
    本機已有那天的快取就零請求。官方未公布上限。
  - 共用 data/rate_limit_state.json 節流（來源名 `twse_rwd`，同源間隔 ≥3 秒；402/403/428/429 即封鎖 2 小時不重試），
    `fetch_odd_lot_day(max_retries=1)`＝不重試；封鎖頁（FOR SECURITY REASONS）立刻停。
存法：沿用 research/twse_odd_lot_client.py 的快取 research/data/raw_twse_odd_lot/TWTC7U_YYYYMMDD.parquet（只在本機）。
漏掉的日子不回頭補（每次只送 1 次）；F18 的訊號是單日 as-of 值，缺一天就沿用前一個值（同回測的 _asof_join）。
用法：python research/fetch_paper_opt_odd_lot.py
十二節：失敗只印警告、exit 0。非投資建議。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
TW = timezone(timedelta(hours=8))
SRC = "twse_rwd"
BLOCK = {402, 403, 428, 429}


def closed_days() -> set[str]:
    cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for y in (cal.get("tw") or {}).values():
        out.update((y or {}).get("closed") or [])
    return out


def target_day(now: datetime) -> str:
    closed = closed_days()
    d = now.date() if now.hour >= 16 else now.date() - timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in closed:
        d -= timedelta(days=1)
    return d.isoformat()


def main() -> int:
    from twse_odd_lot_client import _cache_path, fetch_odd_lot_day
    from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise
    day = target_day(datetime.now(TW))
    ds = day.replace("-", "")
    if _cache_path(ds).exists():
        print(f"{day} TWTC7U 已有快取，零請求")
        return 0
    try:
        _rate_limit_wait_or_raise(SRC)
    except Exception as e:  # noqa: BLE001  封鎖中就不送
        print(f"[warn] {SRC} 節流／封鎖中，今天不送：{e}")
        return 0
    try:
        df = fetch_odd_lot_day(ds, max_retries=1)
        print(f"{day} TWTC7U 1 次請求：{len(df)} 檔")
        if len(df) == 0:
            # 空表也被快取了（client 行為）；若其實是還沒公布，刪掉讓下一次再抓
            p = _cache_path(ds)
            if p.exists() and datetime.now(TW).date().isoformat() == day:
                p.unlink()
                print("[warn] 當日空表（可能尚未公布），已刪快取、下次再抓")
    except Exception as e:  # noqa: BLE001
        m = re.search(r"\b(402|403|428|429)\b", str(e))
        if m:
            _rate_limit_record_block(SRC, int(m.group(1)), "TWTC7U")
            print(f"[warn] HTTP {m.group(1)}，{SRC} 封鎖 2 小時、不重試")
        else:
            print(f"[warn] TWTC7U 失敗（不重試，下次再抓）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[warn] fetch_paper_opt_odd_lot 失敗：{e}")
        sys.exit(0)
