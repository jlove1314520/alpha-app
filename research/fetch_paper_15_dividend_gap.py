"""先.一三六-B7 模擬 O 面板缺口：補抓 adjust.py FinMind 路徑要的快取（2012-01-01～2024-12-31）。

背景：`paper_15_ml_industry_tracker.py build-panel` 有 101 檔因本機沒有
`TaiwanStockDividend/{代號}/2012-01-01/2024-12-31` 快取而失敗（多數只有 2006～2014 與 2025+ 兩段鍵，
中間 2015～2024 空白，湊不出來）。補完股利後同一批又缺 SplitPrice／CapitalReductionReferencePrice
（adjust.py 每檔三個都要）＋全市場 ParValueChange。這支只補那幾檔、只抓到 2024-12-31（不碰 holdout）。

頻率（C:\\alpha\\CLAUDE.md「FinMind（免費層）」）：走 finmind_client._fetch 的共用節流
（同源間隔 ≥3 秒、402/403/428/429 封鎖 2 小時不重試），已有快取就不送請求。
用法：python research/fetch_paper_15_dividend_gap.py [--until HH:MM]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from finmind_client import _cache_path, _fetch  # noqa: E402

TW = timezone(timedelta(hours=8))
PANEL_DIR = Path(__file__).parent / "data" / "paper_15_stock_daily"
START, END = "2012-01-01", "2024-12-31"
PER_STOCK = ("TaiwanStockDividend", "TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice")


def gap_ids() -> list[str]:
    out = []
    for p in sorted(PANEL_DIR.glob("*.json")):
        err = json.loads(p.read_text(encoding="utf-8")).get("error") or ""
        if "本機無快取" in err and f"/{p.stem}/{START}/{END}" in err and "TaiwanStockPrice/" not in err:
            out.append(p.stem)
    return out


def main(argv: list[str]) -> int:
    until = argv[argv.index("--until") + 1] if "--until" in argv else None
    ids = gap_ids()
    todo = [("TaiwanStockParValueChange", "")] + [(ds, s) for s in ids for ds in PER_STOCK]
    todo = [t for t in todo if not _cache_path(t[0], t[1], START, END).exists()]
    print(f"快取缺口 {len(ids)} 檔；尚未抓 {len(todo)} 個（資料集×代號）")
    n_ok = n_fail = 0
    for ds, sid in todo:
        if until and datetime.now(TW).strftime("%H:%M") >= until:
            print(f"到 {until} 停止；下一批從 {ds}/{sid} 開始")
            break
        try:
            df = _fetch(ds, sid, START, END)
            n_ok += 1
            print(f"  {ds}/{sid or 'ALL'}: {len(df)} 列")
        except RuntimeError as e:
            n_fail += 1
            print(f"  {ds}/{sid}: 失敗 {str(e)[:160]}")
            if "封鎖" in str(e) or "HTTP 4" in str(e):
                print("額度／封鎖類錯誤，整批停止、不重試")
                break
    left = [(ds, s) for s in ids for ds in PER_STOCK if not _cache_path(ds, s, START, END).exists()]
    print(json.dumps({"gap_n": len(ids), "fetched_ok": n_ok, "failed": n_fail, "remaining": len(left)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
